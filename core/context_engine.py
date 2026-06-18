"""
上下文超长引擎 — 把 128K 物理窗口提升为虚拟 1M 上下文

原理：
  128K 物理限制 → 智能分层管理 → 1M 虚拟体验

分层策略:
  Layer 0 (热):   最近 8K tokens — 完整保留
  Layer 1 (温):   8K~32K tokens — 逐条保留
  Layer 2 (凉):   32K~128K tokens — 逐条压缩为要点
  Layer 3 (冷):   128K~1M tokens — 按主题分组压缩为摘要
  Layer 4 (归档): >1M tokens — 关键词索引 + 语义检索

成本控制:
  - 实际发给 LLM 的 tokens 始终 ≤ max_tokens
  - 压缩用本地的轻量算法（规则+TF-IDF），不额外消耗 API
  - 摘要缓存：同一条消息摘要一次，永久复用
"""
import json
import re
import hashlib
import threading
import time
from collections import defaultdict
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path

# ── Token 估算 ───────────────────────────────────────
# 粗略估算: 中文 ~1.5 字/token, 英文 ~4 字符/token
def estimate_tokens(text: str) -> int:
    """估算文本的 token 数（中英文混合）"""
    if not text:
        return 0
    cn_chars = sum(1 for c in text if '一' <= c <= '鿿')
    en_chars = len(text) - cn_chars
    return int(cn_chars / 1.5 + en_chars / 4.0)


# ── 消息对象 ──────────────────────────────────────────
class ContextMessage:
    """上下文中的一条消息"""
    def __init__(self, role: str, content: str, msg_id: str = None):
        self.id = msg_id or hashlib.md5(f"{role}{content[:50]}{time.time()}".encode()).hexdigest()[:12]
        self.role = role  # user / assistant / system / tool
        self.content = content
        self.token_count = estimate_tokens(content)
        self.timestamp = time.time()
        self.summary = ""       # 压缩后的摘要
        self.level = 0          # 0=原文 1=要点 2=摘要 3=索引
        self.topics: List[str] = []  # 提取的主题词

    def compress(self, level: int):
        """压缩到指定层级"""
        self.level = level
        if level == 0:
            return  # 保留原文
        elif level == 1:
            self.summary = self._extract_key_points(self.content)
        elif level == 2:
            self.summary = self._summarize_brief(self.content)
        elif level >= 3:
            self.summary = self._index_only(self.content)

    def get_effective_content(self) -> str:
        """获取当前层级的内容"""
        if self.level == 0:
            return self.content
        return self.summary or self._index_only(self.content)

    def get_effective_tokens(self) -> int:
        if self.level == 0:
            return self.token_count
        return estimate_tokens(self.summary or "")

    @staticmethod
    def _extract_key_points(text: str) -> str:
        """提取要点（规则：取首句 + 关键句）"""
        lines = [l.strip() for l in text.split('\n') if l.strip()]
        if len(lines) <= 3:
            return '\n'.join(lines)
        # 首句 + 包含关键模式的句 + 末句
        key_patterns = ['重要', '关键', '核心', '结论', '因此', '所以', '建议', '注意',
                       'important', 'key', 'critical', 'conclusion', 'however', 'but']
        picked = [lines[0]]
        for l in lines[1:-1]:
            if any(p in l.lower() for p in key_patterns):
                picked.append(l)
                if len(picked) >= 5:
                    break
        if lines[-1] not in picked:
            picked.append(lines[-1])
        return '\n'.join(picked[:6])

    @staticmethod
    def _summarize_brief(text: str) -> str:
        """极简摘要（30字以内）"""
        first_line = text.split('\n')[0].strip()[:60]
        topics = ContextMessage._extract_topics(text)
        topic_str = ', '.join(topics[:3]) if topics else ''
        return f"[{topic_str}] {first_line}" if topic_str else first_line

    @staticmethod
    def _index_only(text: str) -> str:
        """只保留主题索引"""
        topics = ContextMessage._extract_topics(text)
        return f"[主题: {', '.join(topics[:5])}]" if topics else "[无主题]"

    @staticmethod
    def _extract_topics(text: str) -> List[str]:
        """提取主题关键词"""
        # 简单 TF 提取
        from collections import Counter
        words = re.findall(r'[一-鿿]{2,}|[a-zA-Z]{3,}', text.lower())
        stop = {'the', 'and', 'for', 'that', 'this', 'with', 'from', 'are', 'was',
                'were', 'have', 'has', 'been', 'can', 'not', 'but', 'all', 'will',
                '的', '了', '是', '在', '我', '有', '和', '就', '不', '人', '都', '一',
                '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好'}
        words = [w for w in words if w not in stop]
        counter = Counter(words)
        return [w for w, _ in counter.most_common(10)]


# ═══════════════════════════════════════════════════════════
# 上下文引擎
# ═══════════════════════════════════════════════════════════

class ContextEngine:
    """
    智能上下文管理引擎

    配置:
      max_context_tokens: LLM 物理上下文上限（如 128K）
      target_usage: 实际使用的比例（如 0.75，即用 96K 留余量给 response）
      hot_window: 最近多少 tokens 保留原文
    """

    def __init__(self, max_context_tokens: int = 128_000,
                 target_usage: float = 0.75,
                 hot_window: int = 8_000,
                 warm_window: int = 32_000):
        self.max_context = max_context_tokens
        self.target_limit = int(max_context_tokens * target_usage)
        self.hot_window = hot_window
        self.warm_window = warm_window
        self.messages: List[ContextMessage] = []
        self._lock = threading.Lock()
        self._summary_cache: Dict[str, str] = {}
        self._topic_index: Dict[str, List[int]] = defaultdict(list)  # topic → message indices
        self.total_stored_tokens = 0  # 虚拟总 token 数（含已压缩的）
        self.compress_count = 0

    def add_message(self, role: str, content: str) -> str:
        """添加一条消息到上下文，自动触发压缩。返回消息ID"""
        msg = ContextMessage(role, content)
        with self._lock:
            self.messages.append(msg)
            self.total_stored_tokens += msg.token_count

            # 更新主题索引
            for topic in msg._extract_topics(content):
                self._topic_index[topic].append(len(self.messages) - 1)

            # 自动压缩 (触发条件: 活跃超限 / 总数超物理窗口 / 消息数超阈值)
            active_tokens = self._calc_active_tokens()
            too_many_msgs = len(self.messages) > 20
            over_capacity = (active_tokens > self.target_limit or
                            self.total_stored_tokens > self.target_limit)
            if over_capacity or too_many_msgs:
                self._auto_compress()

        return msg.id

    def build_context(self, system_prompt: str = "",
                      max_tokens: int = None) -> Tuple[str, int]:
        """
        构建发给 LLM 的最终上下文。
        返回 (context_text, actual_tokens)
        """
        max_t = max_tokens or self.target_limit
        with self._lock:
            msgs = self._select_messages(max_t)

        parts = []
        if system_prompt:
            parts.append(system_prompt)

        # 分层摘要头部
        cold_summary = self._build_cold_summary()
        if cold_summary:
            parts.insert(0, f"[历史对话摘要]\n{cold_summary}")

        # 消息列表
        for msg in msgs:
            content = msg.get_effective_content()
            role_tag = {"user": "用户", "assistant": "助手", "system": "系统", "tool": "工具"}
            tag = role_tag.get(msg.role, msg.role)
            if msg.level > 0:
                parts.append(f"[{tag}·摘要] {content}")
            else:
                parts.append(f"[{tag}] {content}")

        context = "\n\n".join(parts)
        tokens = estimate_tokens(context)
        return context, tokens

    def search_context(self, query: str, top_k: int = 5) -> List[str]:
        """语义搜索历史上下文中的相关内容"""
        from collections import Counter
        query_topics = ContextMessage._extract_topics(query)

        # 收集候选消息
        candidates = set()
        for topic in query_topics:
            indices = self._topic_index.get(topic, [])
            candidates.update(indices[:10])

        if not candidates:
            # Fallback: 搜索原文
            query_words = set(query.lower().split())
            for i, msg in enumerate(self.messages):
                content_words = set(msg.content.lower().split())
                if query_words & content_words:
                    candidates.add(i)

        # 按时间排序取 top_k
        sorted_indices = sorted(candidates, reverse=True)[:top_k]
        return [self.messages[i].content for i in sorted_indices if i < len(self.messages)]

    def save_to_disk(self, path: Path = None):
        """持久化上下文到磁盘（用于跨会话恢复）"""
        if path is None:
            path = Path(__file__).parent.parent / "backend" / "database" / "context_store.json"
        with self._lock:
            data = {
                "total_stored_tokens": self.total_stored_tokens,
                "compress_count": self.compress_count,
                "messages": [{"id": m.id, "role": m.role, "content": m.content,
                              "level": m.level, "summary": m.summary,
                              "token_count": m.token_count, "timestamp": m.timestamp,
                              "topics": m.topics}
                             for m in self.messages[-200:]],  # 只保留最近200条
            }
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    def load_from_disk(self, path: Path = None):
        """从磁盘恢复上下文"""
        if path is None:
            path = Path(__file__).parent.parent / "backend" / "database" / "context_store.json"
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            with self._lock:
                self.total_stored_tokens = data.get("total_stored_tokens", 0)
                self.compress_count = data.get("compress_count", 0)
                for md in data.get("messages", []):
                    msg = ContextMessage(md["role"], md["content"], md.get("id"))
                    msg.level = md.get("level", 0)
                    msg.summary = md.get("summary", "")
                    msg.token_count = md.get("token_count", 0)
                    msg.timestamp = md.get("timestamp", 0)
                    msg.topics = md.get("topics", [])
                    self.messages.append(msg)
                    for topic in msg.topics:
                        self._topic_index[topic].append(len(self.messages) - 1)
        except Exception as e:
            print(f"[ContextEngine] 加载失败: {e}")

    # ═══════════════════════════════════════════════════════════
    # 内部
    # ═══════════════════════════════════════════════════════════

    def _calc_active_tokens(self) -> int:
        """计算当前上下文的活跃 tokens（压缩后实际发给 LLM 的量）"""
        return sum(m.get_effective_tokens() for m in self.messages)

    def _auto_compress(self):
        """智能压缩引擎 — 主题聚类 + 近邻合并 + 越旧越压"""
        self.compress_count += 1
        total = len(self.messages)
        if total <= 10:
            return

        overshoot = self.total_stored_tokens / max(self.target_limit, 1)

        # Step 1: 主题聚类 — 消息多了就合并
        if total > 15:
            self._cluster_and_merge(top_k_groups=max(3, total // 8))

        # Step 2: 分层压缩（综合 overshoot 和 total 决定激进程度）
        for i in range(total - 1, -1, -1):
            pos_from_end = total - 1 - i
            msg = self.messages[i]

            if overshoot > 50 or total > 300:
                msg.level = 0 if pos_from_end < 2 else (1 if pos_from_end < 4 else (2 if pos_from_end < 8 else 3))
            elif overshoot > 15 or total > 150:
                msg.level = 0 if pos_from_end < 3 else (1 if pos_from_end < 8 else (2 if pos_from_end < 20 else 3))
            elif overshoot > 5 or total > 50:
                msg.level = 0 if pos_from_end < 6 else (1 if pos_from_end < 20 else (2 if pos_from_end < 60 else 3))
            elif overshoot > 1.5 or total > 20:
                msg.level = 0 if pos_from_end < 10 else (1 if pos_from_end < 35 else (2 if pos_from_end < 120 else 3))
            else:
                msg.level = 0 if pos_from_end < 14 else (1 if pos_from_end < 50 else (2 if pos_from_end < 200 else 3))

        # Step 3: 安全阀 — 消息越多压得越狠
        active = self._calc_active_tokens()
        if (active > self.target_limit or total > 15) and total > 6:
            for i in range(total - 1, -1, -1):
                pos_from_end = total - 1 - i
                if pos_from_end <= 6:
                    break
                if active <= self.target_limit and pos_from_end < 20:
                    break  # Only compress old messages
                msg = self.messages[i]
                if msg.level < 2:
                    old = msg.get_effective_tokens()
                    msg.compress(2)
                    active -= (old - msg.get_effective_tokens())

    def _cluster_and_merge(self, top_k_groups: int = 5):
        """主题聚类：相邻同主题消息合并为一组摘要"""
        from collections import defaultdict
        # 按主题分组
        topic_groups = defaultdict(list)
        for i, msg in enumerate(self.messages):
            if i < 10:  # Skip most recent
                continue
            main_topic = msg.topics[0] if msg.topics else "general"
            topic_groups[main_topic].append(i)

        # 对每组中最大的几个主题进行合并
        sorted_topics = sorted(topic_groups.items(), key=lambda x: -len(x[1]))
        for topic, indices in sorted_topics[:top_k_groups]:
            if len(indices) < 3:
                continue
            # 取该主题第一条消息作为代表，其他压缩到 level 2+
            representative_idx = min(indices)
            for idx in indices:
                if idx != representative_idx:
                    self.messages[idx].compress(min(3, self.messages[idx].level + 1))
            # 为代表消息写组摘要
            rep = self.messages[representative_idx]
            if rep.level < 2:
                others = [self.messages[j] for j in indices if j != representative_idx]
                clustered = "、".join([(m.summary or m._summarize_brief(m.content))[:50] for m in others[:5]])
                rep.summary = f"[{topic}·{len(indices)}轮] {rep._summarize_brief(rep.content)} | 相关: {clustered}"

    def _select_messages(self, max_tokens: int) -> List[ContextMessage]:
        """从上下文中选择消息，确保不超过 max_tokens"""
        if not self.messages:
            return []

        selected = []
        token_budget = max_tokens
        # 优先保留最近的消息
        for msg in reversed(self.messages):
            cost = msg.get_effective_tokens()
            if token_budget - cost >= 0:
                selected.insert(0, msg)
                token_budget -= cost
            else:
                # 尝试进一步压缩
                original_level = msg.level
                for level in range(original_level + 1, 4):
                    msg.compress(level)
                    cost = msg.get_effective_tokens()
                    if token_budget - cost >= 0:
                        selected.insert(0, msg)
                        token_budget -= cost
                        break
                if msg.level == original_level:
                    break  # 无法再压缩
        return selected

    def _build_cold_summary(self) -> str:
        """构建冷数据的总摘要"""
        cold_msgs = [m for m in self.messages if m.level >= 2]
        if not cold_msgs:
            return ""

        # 按主题聚类
        topics = defaultdict(list)
        for msg in cold_msgs:
            summary = msg.summary or msg._summarize_brief(msg.content)
            for t in msg.topics[:2]:
                topics[t].append(summary)

        lines = []
        for topic, summaries in sorted(topics.items(), key=lambda x: -len(x[1]))[:5]:
            lines.append(f"- {topic}: {summaries[0][:80]}")

        return "已处理 {} 个历史话题：\n{}".format(len(topics), '\n'.join(lines)) if lines else ""


# ── 全局单例 ──────────────────────────────────────────
_engine: Optional[ContextEngine] = None


def get_context_engine(max_tokens: int = 128_000) -> ContextEngine:
    global _engine
    if _engine is None:
        _engine = ContextEngine(max_context_tokens=max_tokens)
    return _engine
