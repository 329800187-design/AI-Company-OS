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
from datetime import datetime, timedelta
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
                access_count INTEGER DEFAULT 0,
                retention_class TEXT DEFAULT 'standard',
                expires_at TEXT,
                deleted_at TEXT,
                deletion_reason TEXT DEFAULT ''
            )
        """)
        # Backward-compatible migration for existing project databases.
        for column in (
            "retention_class TEXT DEFAULT 'standard'",
            "expires_at TEXT",
            "deleted_at TEXT",
            "deletion_reason TEXT DEFAULT ''",
        ):
            try:
                conn.execute(f"ALTER TABLE memories ADD COLUMN {column}")
            except sqlite3.OperationalError:
                pass
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_key ON memories(key)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance DESC)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_memories_active_expiry ON memories(deleted_at, expires_at)")
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
        row = conn.execute(
            "SELECT * FROM memories WHERE key=? AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?)",
            (key, datetime.now().isoformat()),
        ).fetchone()
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
                f"SELECT * FROM memories WHERE deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?) AND ({' OR '.join(like_clauses)}) "
                "ORDER BY importance DESC, accessed_at DESC LIMIT ?",
                (datetime.now().isoformat(), *params, max(limit * 10, 100))
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM memories WHERE deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?) ORDER BY importance DESC, accessed_at DESC LIMIT ?",
                (datetime.now().isoformat(), limit * 5)
            ).fetchall()

        candidates = [self._row_to_dict(r) for r in rows]

        # TF-IDF 语义重排序
        if candidates and query:
            candidates = self._rerank_semantic(query, candidates)

        return candidates[:limit]

    def search_by_source_tags(self, query: str, *, source: str,
                              required_tags: List[str] = None,
                              limit: int = 10) -> List[dict]:
        """Search a scoped subset of memories.

        Long-lived operating knowledge should not be mixed blindly with every
        transient agent trace.  Callers can therefore restrict recall to one
        producer and a small set of required tags before semantic re-ranking.
        """
        conn = self._get_conn()
        clauses = ["source = ?", "deleted_at IS NULL", "(expires_at IS NULL OR expires_at > ?)"]
        params: List[Any] = [source, datetime.now().isoformat()]
        for tag in required_tags or []:
            clauses.append("tags LIKE ?")
            params.append(f'%"{tag}"%')

        rows = conn.execute(
            f"SELECT * FROM memories WHERE {' AND '.join(clauses)} "
            "ORDER BY importance DESC, accessed_at DESC LIMIT ?",
            (*params, max(limit * 10, 100)),
        ).fetchall()
        candidates = [self._row_to_dict(row) for row in rows]
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
                "SELECT * FROM memories WHERE source != 'system' AND deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?) "
                "ORDER BY accessed_at DESC LIMIT ?",
                (datetime.now().isoformat(), limit)
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
                data = {}
                goal_text = m["content"][:100]
            if data.get("record_type") == "accepted_boss_mission":
                lines.append(f"- [Boss 已验收] {goal_text}")
                comment = str(data.get("review_comment", "")).strip()
                if comment:
                    lines.append(f"  - 验收意见：{comment[:240]}")
                for module in data.get("modules", [])[:2]:
                    summary = str(module.get("summary", "")).strip()
                    if summary:
                        title = module.get("title") or module.get("module_id") or "模块结论"
                        lines.append(f"  - {title}：{summary[:360]}")
                outcome = data.get("outcome", {})
                if outcome:
                    lines.append(f"  - 后续结果：{outcome.get('status', 'inconclusive')}")
                    if outcome.get("metrics"):
                        lines.append(f"  - 观测指标：{json.dumps(outcome['metrics'], ensure_ascii=False)[:360]}")
                    if outcome.get("note"):
                        lines.append(f"  - 复盘备注：{str(outcome['note'])[:360]}")
            else:
                lines.append(f"- [{m['source']}] {goal_text}")

        return "\n".join(lines)

    def recent(self, limit: int = 10) -> List[dict]:
        """��取最近的记忆"""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM memories WHERE deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?) ORDER BY accessed_at DESC LIMIT ?",
            (datetime.now().isoformat(), limit)
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

    def delete_by_key(self, key: str) -> bool:
        """按 key 删除单条记忆，返回是否成功"""
        conn = self._get_conn()
        cursor = conn.execute("DELETE FROM memories WHERE key=?", (key,))
        conn.commit()
        return cursor.rowcount > 0

    def retire_by_key(self, key: str, reason: str = "") -> bool:
        """Soft-delete a memory so it can no longer be recalled or injected."""
        conn = self._get_conn()
        cursor = conn.execute(
            """UPDATE memories SET deleted_at=?, deletion_reason=?
               WHERE key=? AND deleted_at IS NULL""",
            (datetime.now().isoformat(), str(reason or "")[:500], key),
        )
        conn.commit()
        return cursor.rowcount > 0

    def set_retention(self, key: str, retention_days: Optional[int] = None,
                      retention_class: str = "standard") -> bool:
        """Set an explicit retention policy for an active memory.

        ``retention_days=None`` means the memory has no scheduled expiry, but
        it remains subject to explicit soft deletion by a human.
        """
        if retention_days is not None and retention_days < 1:
            raise ValueError("retention_days must be positive when specified")
        retention_class = str(retention_class or "standard").strip()[:80] or "standard"
        expires_at = (
            (datetime.now() + timedelta(days=int(retention_days))).isoformat()
            if retention_days is not None else None
        )
        conn = self._get_conn()
        cursor = conn.execute(
            """UPDATE memories SET retention_class=?, expires_at=?
               WHERE key=? AND deleted_at IS NULL""",
            (retention_class, expires_at, key),
        )
        conn.commit()
        return cursor.rowcount > 0

    def cleanup_expired(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Soft-delete records whose explicit retention period has expired."""
        conn = self._get_conn()
        now = datetime.now().isoformat()
        clauses = ["deleted_at IS NULL", "expires_at IS NOT NULL", "expires_at <= ?"]
        params: List[Any] = [now]
        if source:
            clauses.append("source = ?")
            params.append(source)
        cursor = conn.execute(
            f"UPDATE memories SET deleted_at=?, deletion_reason='retention_expired' WHERE {' AND '.join(clauses)}",
            (now, *params),
        )
        conn.commit()
        return {"retired_count": cursor.rowcount, "cleaned_at": now, "source": source}

    def governance_summary(self, source: Optional[str] = None) -> Dict[str, Any]:
        """Return only factual retention/deletion counters, never memory content."""
        conn = self._get_conn()
        clauses = []
        params: List[Any] = []
        if source:
            clauses.append("source = ?")
            params.append(source)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        now = datetime.now().isoformat()
        row = conn.execute(
            f"""SELECT
                    COUNT(*) AS total_count,
                    SUM(CASE WHEN deleted_at IS NULL AND (expires_at IS NULL OR expires_at > ?) THEN 1 ELSE 0 END) AS active_count,
                    SUM(CASE WHEN deleted_at IS NOT NULL THEN 1 ELSE 0 END) AS retired_count,
                    SUM(CASE WHEN deleted_at IS NULL AND expires_at IS NOT NULL THEN 1 ELSE 0 END) AS expiring_count
                FROM memories {where}""",
            (now, *params),
        ).fetchone()
        return {
            "source": source,
            "total_count": int(row["total_count"] or 0),
            "active_count": int(row["active_count"] or 0),
            "retired_count": int(row["retired_count"] or 0),
            "expiring_count": int(row["expiring_count"] or 0),
        }

    def update_by_key(self, key: str, content: Optional[str] = None,
                      source: Optional[str] = None, tags: Optional[List[str]] = None,
                      importance: Optional[float] = None) -> bool:
        """按 key 更新单条记忆的部分字段，返回是否成功"""
        conn = self._get_conn()
        existing = conn.execute(
            "SELECT id FROM memories WHERE key=? AND deleted_at IS NULL", (key,)
        ).fetchone()
        if not existing:
            return False
        updates = []
        params = []
        if content is not None:
            updates.append("content=?")
            params.append(content)
        if source is not None:
            updates.append("source=?")
            params.append(source)
        if tags is not None:
            updates.append("tags=?")
            params.append(json.dumps(tags, ensure_ascii=False))
        if importance is not None:
            updates.append("importance=?")
            params.append(importance)
        if not updates:
            return False
        updates.append("accessed_at=?")
        params.append(datetime.now().isoformat())
        params.append(key)
        conn.execute(f"UPDATE memories SET {', '.join(updates)} WHERE key=?", params)
        conn.commit()
        return True

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
            "retention_class": row["retention_class"],
            "expires_at": row["expires_at"],
            "deleted_at": row["deleted_at"],
            "deletion_reason": row["deletion_reason"],
        }


# 全局单例
_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _store
    if _store is None:
        _store = MemoryStore()
    return _store
