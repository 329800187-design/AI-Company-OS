"""记忆存储 — AI Company OS 的持久化记忆系统

记忆系统让 AI Company OS 拥有"记忆"和"判断力"：
- 每次执行后自动记录关键信息
- 根据当前目标自动检索相关记忆
- 支持遗忘（过期清理）和优先级排序
"""

import json
import sqlite3
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


class MemoryStore:
    """持久化记忆存储"""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent.parent / "backend" / "database" / "company_os.db"
        self.db_path = Path(db_path)
        self._local = threading.local()
        self._init_table()

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程安全的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(str(self.db_path))
            self._local.conn.row_factory = sqlite3.Row
            self._local.conn.execute("PRAGMA journal_mode=WAL")
        return self._local.conn

    def _init_table(self):
        """初始化记忆表"""
        conn = self._get_conn()
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                key TEXT NOT NULL,
                content TEXT NOT NULL,
                source TEXT DEFAULT 'system',
                tags TEXT DEFAULT '[]',
                importance REAL DEFAULT 0.5,
                created_at TEXT DEFAULT (datetime('now')),
                accessed_at TEXT DEFAULT (datetime('now')),
                access_count INTEGER DEFAULT 0
            )
        """)
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)")
        conn.commit()

    # ── 写入 ──────────────────────────────────────────────

    def remember(self, key: str, content: str, source: str = "system",
                 tags: List[str] = None, importance: float = 0.5):
        """记录一条记忆"""
        conn = self._get_conn()
        tags_json = json.dumps(tags or [], ensure_ascii=False)
        now = datetime.now().isoformat()
        # 如果 key 已存在，更新
        existing = conn.execute(
            "SELECT id FROM memories WHERE key=?", (key,)
        ).fetchone()
        if existing:
            conn.execute(
                "UPDATE memories SET content=?, tags=?, importance=?, accessed_at=? WHERE key=?",
                (content, tags_json, importance, now, key)
            )
        else:
            conn.execute(
                "INSERT INTO memories (key, content, source, tags, importance, created_at, accessed_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (key, content, source, tags_json, importance, now, now)
            )
        conn.commit()

    def remember_result(self, goal: str, result: dict, summary: str, agent: str = "commander"):
        """从执行结果中自动记忆"""
        status = result.get("status", "?")
        key = f"exec_{datetime.now().strftime('%Y%m%d%H%M%S')}_{agent}"
        content = json.dumps({
            "goal": goal,
            "summary": summary[:500],
            "status": status,
            "agent": agent,
            "timestamp": datetime.now().isoformat(),
        }, ensure_ascii=False)

        importance = 0.7 if status == "completed" else 0.3
        tags = [agent, status, "execution"]

        self.remember(key=key, content=content, source=agent,
                      tags=tags, importance=importance)

    # ── 读取 ──────────────────────────────────────────────

    def recall(self, key: str) -> Optional[dict]:
        """按 key 精确查��"""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM memories WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        return self._row_to_dict(row)

    def search(self, query: str, limit: int = 10) -> List[dict]:
        """搜索记忆（TF-IDF 语义搜索 + SQLite 回退）"""
        conn = self._get_conn()
        # 用单个关键词做 LIKE 粗筛（避免多词精确匹配失败）
        keywords = query.split()
        like_clauses = []
        params = []
        for kw in keywords[:5]:
            p = f"%{kw}%"
            like_clauses.append("(content LIKE ? OR key LIKE ? OR tags LIKE ?)")
            params.extend([p, p, p])

        if like_clauses:
            rows = conn.execute(
                f"SELECT * FROM memories WHERE {' OR '.join(like_clauses)} "
                "ORDER BY importance DESC, accessed_at DESC LIMIT ?",
                (*params, max(limit * 10, 100))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories ORDER BY importance DESC, accessed_at DESC LIMIT ?",
                (limit * 5,)
            ).fetchall()

        candidates = [self._row_to_dict(r) for r in rows]

        # TF-IDF 语义重排序
        if candidates and query:
            candidates = self._rerank_semantic(query, candidates)

        return candidates[:limit]

    @staticmethod
    def _rerank_semantic(query: str, candidates: List[dict]) -> List[dict]:
        """用 TF-IDF 余弦相似度对候选记忆重排序"""
        import math
        from collections import Counter

        def tokenize(text: str) -> List[str]:
            tokens = []
            for word in text.lower().split():
                if any('一' <= c <= '鿿' for c in word):
                    tokens.extend(list(word))
                else:
                    tokens.append(word)
            return tokens

        query_tokens = tokenize(query)
        q_counter = Counter(query_tokens)
        norm_q = math.sqrt(sum(v**2 for v in q_counter.values()))

        if norm_q == 0:
            return sorted(candidates, key=lambda c: c.get("importance", 0), reverse=True)

        scored = []
        for c in candidates:
            content = c.get("content", "")
            try:
                data = json.loads(content)
                text = data.get("goal", content)
            except Exception:
                text = content

            doc_tokens = tokenize(text)
            d_counter = Counter(doc_tokens)
            norm_d = math.sqrt(sum(v**2 for v in d_counter.values()))

            if norm_d == 0:
                score = 0.0
            else:
                common = set(q_counter.keys()) & set(d_counter.keys())
                dot = sum(q_counter[t] * d_counter[t] for t in common)
                tfidf = dot / (norm_q * norm_d) if norm_d > 0 else 0

            # 混合分数：TF-IDF 50% + importance 50%
            score = tfidf * 0.5 + (c.get("importance", 0.5)) * 0.5
            scored.append((score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]

    def get_context(self, goal: str, limit: int = 5) -> str:
        """获取与目标相关的记忆上下文（注入 AI prompt）"""
        memories = self.search(goal, limit)
        if not memories:
            # 如果没找到相关记忆，返回最近的执行记录
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT * FROM memories WHERE source != 'system' "
                "ORDER BY accessed_at DESC LIMIT ?",
                (limit,)
            ).fetchall()
            memories = [self._row_to_dict(r) for r in rows]

        if not memories:
            return ""

        lines = ["## 相关记忆\n"]
        for m in memories:
            try:
                data = json.loads(m["content"])
                goal_text = data.get("goal", m["content"][:100])
            except Exception:
                goal_text = m["content"][:100]
            lines.append(f"- [{m['source']}] {goal_text}")

        return "\n".join(lines)

    def recent(self, limit: int = 10) -> List[dict]:
        """��取最近的记忆"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories ORDER BY accessed_at DESC LIMIT ?",
            (limit,)
        ).fetchall()
        return [self._row_to_dict(r) for r in rows]

    # ── 维护 ──────────────────────────────────────────────

    def forget_old(self, days: int = 30):
        """遗忘过期的低重要性记忆"""
        conn = self._get_conn()
        cutoff = (datetime.now() - timedelta(days=days)).isoformat()
        conn.execute(
            "DELETE FROM memories WHERE importance < 0.3 AND created_at < ?",
            (cutoff,)
        )
        conn.commit()

    def clear(self):
        """清空所有记忆"""
        conn = self._get_conn()
        conn.execute("DELETE FROM memories")
        conn.commit()

    # ── 辅助 ──────────────────────────────────────────────

    def _row_to_dict(self, row) -> dict:
        return {
            "id": row["id"],
            "key": row["key"],
            "content": row["content"],
            "source": row["source"],
            "tags": json.loads(row["tags"]) if row["tags"] else [],
            "importance": row["importance"],
            "created_at": row["created_at"],
            "accessed_at": row["accessed_at"],
            "access_count": row["access_count"],
        }


# 全局单例
_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
