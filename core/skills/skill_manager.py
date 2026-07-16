"""技能管理器 — 插件化能力系统

AI Company OS 的技能系统：
- 每个技能是一个 .md 文件，包含 frontmatter 元数据和 Markdown 正文
- 技能定义 Agent 的能力、模板、学习到的经验
- 系统可根据任务自动匹配并加载相关技能
- 支持运行时创建新技能（学习能力）
"""

import hashlib
import os
import re
import time
import yaml
from pathlib import Path
from datetime import datetime
from typing import Any, Dict, List, Optional


class Skill:
    """单个技能"""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem
        self.title = path.stem
        self.description = ""
        self.category = "general"
        self.capabilities: List[str] = []
        self.triggers: List[str] = []  # 触发关键词
        self.body = ""
        self.created_at = ""
        self.updated_at = ""
        self._parse()

    def _parse(self):
        """解析技能文件（frontmatter + Markdown）"""
        try:
            text = self.path.read_text(encoding="utf-8")
        except Exception:
            self.body = ""
            return

        # 提取 YAML frontmatter
        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if fm_match:
            try:
                fm = yaml.safe_load(fm_match.group(1))
                if isinstance(fm, dict):
                    self.title = fm.get("title", self.name)
                    self.description = fm.get("description", "")
                    self.category = fm.get("category", "general")
                    self.capabilities = fm.get("capabilities", [])
                    self.triggers = fm.get("triggers", [])
            except Exception:
                pass
            self.body = text[fm_match.end():].strip()
        else:
            self.body = text.strip()

        # 文件时间
        stat = self.path.stat()
        self.created_at = datetime.fromtimestamp(stat.st_ctime).isoformat()
        self.updated_at = datetime.fromtimestamp(stat.st_mtime).isoformat()

    def match_score(self, goal: str) -> float:
        """计算技能与目标的匹配度 (0.0 ~ 1.0)，使用 TF-IDF 增强匹配"""
        if not self.triggers:
            return 0.0
        goal_lower = goal.lower()

        # 精确匹配
        exact_matches = sum(1 for t in self.triggers if t.lower() in goal_lower)
        exact_score = min(exact_matches / max(len(self.triggers), 1), 1.0) * 0.6

        # TF-IDF 风格的部分匹配：用 body 文本做词频加权
        tfidf_score = self._tfidf_similarity(goal_lower) * 0.4

        return exact_score + tfidf_score

    def _tfidf_similarity(self, query: str) -> float:
        """计算 query 与技能 body 的 TF-IDF 相似度（纯 Python 实现）"""
        import math
        from collections import Counter

        if not self.body:
            return 0.0

        # 分词（简单空格/中文字符分词）
        def tokenize(text: str) -> List[str]:
            # 中英文混合：中文按字，英文按空格
            tokens = []
            for word in text.lower().split():
                if any('一' <= c <= '鿿' for c in word):
                    tokens.extend(list(word))
                else:
                    tokens.append(word)
            return tokens

        query_tokens = tokenize(query)
        doc_tokens = tokenize(self.body)

        if not query_tokens or not doc_tokens:
            return 0.0

        # TF (query)
        q_counter = Counter(query_tokens)
        # TF (doc)
        d_counter = Counter(doc_tokens)

        # Cosine similarity between query and doc
        common = set(q_counter.keys()) & set(d_counter.keys())
        if not common:
            return 0.0

        dot = sum(q_counter[t] * d_counter[t] for t in common)
        norm_q = math.sqrt(sum(v**2 for v in q_counter.values()))
        norm_d = math.sqrt(sum(v**2 for v in d_counter.values()))

        if norm_q == 0 or norm_d == 0:
            return 0.0

        return min(dot / (norm_q * norm_d), 1.0)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "category": self.category,
            "capabilities": self.capabilities,
            "triggers": self.triggers,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }

    def get_context(self, max_chars: int = 2000) -> str:
        """获取技能上下文（用于注入到 AI prompt）"""
        header = f"## 技能: {self.title}\n{self.description}\n"
        body = self.body[:max_chars - len(header)]
        return header + body


class SkillManager:
    """技能管理器"""

    def __init__(self, skills_dir: Optional[Path] = None):
        if skills_dir is None:
            skills_dir = Path(__file__).parent.parent.parent / "skills"
        self.skills_dir = Path(skills_dir)
        self.skills_dir.mkdir(parents=True, exist_ok=True)
        self._skills: Dict[str, Skill] = {}
        self._loaded = False
        self._last_mtime_check: float = 0.0  # 上次检查时间
        self._known_mtimes: Dict[str, float] = {}  # 文件→mtime

    def _check_stale(self) -> bool:
        """检测技能文件是否有变化（30s 缓存窗口）"""
        now = __import__('time').time()
        if now - self._last_mtime_check < 30:
            return False
        self._last_mtime_check = now

        current: Dict[str, float] = {}
        for md_file in self.skills_dir.rglob("*.md"):
            try:
                current[str(md_file)] = md_file.stat().st_mtime
            except OSError:
                continue

        # 新文件 / 删除文件 / 修改时间变化 → 需要重载
        if set(current.keys()) != set(self._known_mtimes.keys()):
            self._known_mtimes = current
            return True
        for path, mtime in current.items():
            if abs(mtime - self._known_mtimes.get(path, 0)) > 1.0:
                self._known_mtimes = current
                return True

        self._known_mtimes = current
        return False

    def load_all(self) -> List[Skill]:
        """加载所有技能（支持热重载：检测到 .md 文件变化自动刷新）"""
        if self._loaded and not self._check_stale():
            return list(self._skills.values())

        self._skills = {}
        for md_file in self.skills_dir.rglob("*.md"):
            skill = Skill(md_file)
            if skill.body:  # 只加载有内容的技能
                self._skills[skill.name] = skill
        self._loaded = True
        return list(self._skills.values())

    def list_all(self) -> List[dict]:
        """列出所有技能"""
        if not self._loaded:
            self.load_all()
        return [s.to_dict() for s in self._skills.values()]

    def get(self, name: str) -> Optional[Skill]:
        """按名称获取技能"""
        if not self._loaded:
            self.load_all()
        return self._skills.get(name)

    def match(self, goal: str, top_k: int = 3) -> List[Skill]:
        """匹配与目标最相关的技能（带缓存）"""
        from core.cache_store import cache
        import hashlib
        ck = f"skill_match:{hashlib.md5(goal.encode()).hexdigest()[:12]}:{top_k}"
        cached = cache.get(ck)
        if cached is not None:
            return cached
        if not self._loaded:
            self.load_all()
        scored = [(s, s.match_score(goal)) for s in self._skills.values()]
        scored.sort(key=lambda x: x[1], reverse=True)
        result = [s for s, score in scored if score > 0][:top_k]
        cache.set(ck, result, ttl=30)
        return result

    def get_context_for_goal(self, goal: str, max_skills: int = 3) -> str:
        """获取与目标相关的技能上下文（注入 AI prompt）"""
        matched = self.match(goal, max_skills)
        if not matched:
            # 返回默认通用技能
            general = [s for s in self._skills.values() if s.category == "general"]
            if general:
                return general[0].get_context()
            return ""
        return "\n\n".join(s.get_context() for s in matched)

    def create(self, name: str, title: str, description: str,
               category: str = "learned", capabilities: List[str] = None,
               triggers: List[str] = None, body: str = "") -> Skill:
        """创建新技能（学习能力）"""
        # 生成文件名
        safe_name = re.sub(r'[^\w\-]', '_', name)
        filepath = self.skills_dir / f"{safe_name}.md"

        fm = {
            "title": title,
            "description": description,
            "category": category,
            "capabilities": capabilities or [],
            "triggers": triggers or [],
        }

        content = "---\n"
        content += yaml.dump(fm, allow_unicode=True, default_flow_style=False)
        content += "---\n\n"
        content += body or f"# {title}\n\n{description}\n"

        filepath.write_text(content, encoding="utf-8")

        skill = Skill(filepath)
        self._skills[skill.name] = skill
        return skill

    def learn_from_result(self, goal: str, result: dict, summary: str):
        """从执行结果中学习 — 创建或更新技能"""
        status = result.get("status", "")
        if status != "completed":
            return None

        # 提取关键信息
        agent_used = result.get("agent", "unknown")
        results = result.get("results", [])

        # 生成学习内容
        learn_body = f"# 从执行中学习\n\n"
        learn_body += f"## 原始目标\n{goal}\n\n"
        learn_body += f"## 使用的 Agent\n{agent_used}\n\n"
        if results:
            learn_body += "## 执行步骤\n"
            for r in results[:5]:
                learn_body += f"- {r.get('status', '?')}: {str(r.get('result', ''))[:100]}\n"

        clean_goal = re.sub(r'[^\w]', '_', goal[:30])
        skill_name = f"learned_{clean_goal}"

        return self.create(
            name=skill_name,
            title=f"学习: {goal[:50]}",
            description=f"从执行「{goal[:50]}」中学到的经验",
            category="learned",
            capabilities=[agent_used],
            triggers=[goal[:20]],
            body=learn_body,
        )


# 全局单例
_manager: Optional[SkillManager] = None


def get_skill_manager() -> SkillManager:
    global _manager
    if _manager is None:
        _manager = SkillManager()
        _manager.load_all()
    return _manager
