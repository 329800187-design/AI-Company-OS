"""
定时任务调度器 — 内置 Cron 引擎

用法:
  sched = get_scheduler()
  sched.add_task("hourly_report", "0 * * * *", monthly_report, user_id="xxx")
  sched.start()
"""
import hashlib
import json
import sqlite3
import threading
import time
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional


class CronParser:
    """解析 5-字段 Cron 表达式 (minute hour dom month dow)"""

    RANGES = [(0, 59), (0, 23), (1, 31), (1, 12), (0, 6)]

    @classmethod
    def matches(cls, expr: str, dt: datetime) -> bool:
        fields = expr.strip().split()
        if len(fields) != 5:
            return False
        values = [dt.minute, dt.hour, dt.day, dt.month, (dt.weekday() + 1) % 7]
        for i, field in enumerate(fields):
            if not cls._field_matches(field, values[i], *cls.RANGES[i]):
                return False
        return True

    @classmethod
    def _field_matches(cls, field: str, value: int, lo: int, hi: int) -> bool:
        if field == '*':
            return True
        for part in field.split(','):
            part = part.strip()
            if '/' in part:
                base, step = part.split('/')
                step = int(step)
                base_lo, base_hi = (lo, hi) if base == '*' else cls._parse_range(base, lo, hi)
                return value >= base_lo and value <= base_hi and (value - base_lo) % step == 0
            elif '-' in part:
                plo, phi = cls._parse_range(part, lo, hi)
                return plo <= value <= phi
            else:
                try:
                    return int(part) == value
                except ValueError:
                    return False
        return False

    @staticmethod
    def _parse_range(s: str, lo: int, hi: int) -> tuple:
        parts = s.split('-')
        return (int(parts[0]), int(parts[1]))

    @classmethod
    def next_fire(cls, expr: str, from_dt: datetime = None) -> Optional[datetime]:
        dt = (from_dt or datetime.now()).replace(second=0, microsecond=0) + timedelta(minutes=1)
        for _ in range(366 * 24 * 60):
            if cls.matches(expr, dt):
                return dt
            dt += timedelta(minutes=1)
        return None


class CronScheduler:
    """定时任务调度器 — SQLite 持久化 + 后台线程"""

    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = Path(__file__).parent.parent / "backend" / "database" / "company_os.db"
        self.db_path = str(db_path)
        self._jobs: Dict[str, Dict] = {}
        self._running = False
        self._thread = None
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cron_jobs (
                id TEXT PRIMARY KEY,
                name TEXT,
                cron_expr TEXT NOT NULL,
                task_type TEXT NOT NULL,
                task_params TEXT DEFAULT '{}',
                user_id TEXT DEFAULT '',
                enabled INTEGER DEFAULT 1,
                last_run TEXT,
                next_run TEXT,
                run_count INTEGER DEFAULT 0,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cron_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                run_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'completed',
                result TEXT,
                duration_ms INTEGER DEFAULT 0,
                FOREIGN KEY (job_id) REFERENCES cron_jobs(id)
            )
        """)
        conn.commit()
        conn.close()

    def add_task(self, name: str, cron_expr: str, task_type: str,
                 task_params: Dict = None, user_id: str = "",
                 task_id: str = None) -> str:
        jid = task_id or hashlib.md5(f"{name}{cron_expr}{time.time()}".encode()).hexdigest()[:12]
        next_run = CronParser.next_fire(cron_expr)
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute(
                "INSERT OR REPLACE INTO cron_jobs (id, name, cron_expr, task_type, task_params, user_id, next_run) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (jid, name, cron_expr, task_type, json.dumps(task_params or {}, ensure_ascii=False),
                 user_id, next_run.isoformat() if next_run else None)
            )
            conn.commit()
            conn.close()
            self._jobs[jid] = {
                "name": name, "cron_expr": cron_expr, "task_type": task_type,
                "task_params": task_params or {}, "user_id": user_id, "enabled": True,
                "next_run": next_run,
            }
        return jid

    def remove_task(self, job_id: str):
        with self._lock:
            conn = sqlite3.connect(self.db_path)
            conn.execute("DELETE FROM cron_jobs WHERE id = ?", (job_id,))
            conn.commit()
            conn.close()
            self._jobs.pop(job_id, None)

    def list_tasks(self) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        rows = conn.execute(
            "SELECT * FROM cron_jobs WHERE enabled=1 ORDER BY next_run"
        ).fetchall()
        conn.close()
        return [{
            "id": r[0], "name": r[1], "cron_expr": r[2], "task_type": r[3],
            "task_params": json.loads(r[4]) if r[4] else {},
            "user_id": r[5], "enabled": bool(r[6]),
            "last_run": r[7], "next_run": r[8], "run_count": r[9],
        } for r in rows]

    def get_logs(self, job_id: str = "", limit: int = 50) -> List[Dict]:
        conn = sqlite3.connect(self.db_path)
        if job_id:
            rows = conn.execute(
                "SELECT * FROM cron_logs WHERE job_id = ? ORDER BY id DESC LIMIT ?",
                (job_id, limit)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM cron_logs ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
        conn.close()
        return [{"id": r[0], "job_id": r[1], "run_at": r[2], "status": r[3],
                 "result": str(r[4])[:200] if r[4] else "", "duration_ms": r[5]} for r in rows]

    def start(self, tick_seconds: int = 30):
        """启动后台调度线程"""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, args=(tick_seconds,), daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False

    def _loop(self, tick: int):
        while self._running:
            now = datetime.now()
            conn = sqlite3.connect(self.db_path)
            rows = conn.execute(
                "SELECT * FROM cron_jobs WHERE enabled=1 AND next_run <= ?",
                (now.isoformat(),)
            ).fetchall()
            conn.close()

            for row in rows:
                jid = row[0]
                name = row[1]
                task_type = row[3]
                params = json.loads(row[4]) if row[4] else {}

                # Execute in thread
                t = threading.Thread(target=self._execute, args=(jid, name, task_type, params), daemon=True)
                t.start()

            time.sleep(tick)

    def _execute(self, jid: str, name: str, task_type: str, params: Dict):
        start = time.time()
        status = "completed"
        result = ""

        try:
            from agents.ceo_agent.agent import CEOAgent
            from agents.marketing_agent.agent import MarketingAgent
            from agents.data_agent.agent import DataAgent
            from agents.qa_agent.agent import QAAgent
            from backend.commander.commander import CommanderAgent

            agent_map = {
                "ceo": CEOAgent, "marketing": MarketingAgent,
                "data_explore": DataAgent, "qa": QAAgent,
                "commander": CommanderAgent,
            }
            agent_cls = agent_map.get(task_type)
            if agent_cls:
                agent = agent_cls()
                res = agent.run({"task_id": f"cron_{jid}", "task_type": task_type, **params})
                result = json.dumps(res.get("result", res.get("summary", "")), ensure_ascii=False)[:500]
            else:
                status = "failed"
                result = f"未知任务类型: {task_type}"
        except Exception as e:
            status = "failed"
            result = f"{e}\n{traceback.format_exc()[-300:]}"

        duration_ms = int((time.time() - start) * 1000)

        # Log + update
        conn = sqlite3.connect(self.db_path)
        conn.execute(
            "INSERT INTO cron_logs (job_id, status, result, duration_ms) VALUES (?, ?, ?, ?)",
            (jid, status, result, duration_ms)
        )
        next_run = CronParser.next_fire(conn.execute(
            "SELECT cron_expr FROM cron_jobs WHERE id = ?", (jid,)
        ).fetchone()[0])
        conn.execute(
            "UPDATE cron_jobs SET last_run = datetime('now'), next_run = ?, run_count = run_count + 1 WHERE id = ?",
            (next_run.isoformat() if next_run else None, jid)
        )
        conn.commit()
        conn.close()


# 全局单例
_scheduler: Optional[CronScheduler] = None


def get_scheduler() -> CronScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = CronScheduler()
        _scheduler.start()
    return _scheduler
