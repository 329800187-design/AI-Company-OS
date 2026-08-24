"""监控面板路由 — Agent健康/用量/缓存/支付一览"""
from fastapi import APIRouter, Query

router = APIRouter(prefix="/system", tags=["监控 / Monitoring"], include_in_schema=False)


@router.get("/metrics", summary="监控面板数据")
def metrics():
    import datetime
    m = {"timestamp": datetime.datetime.now().isoformat()}

    # 1. Usage (24h + all-time)
    try:
        from backend.services.usage_stats import get_usage_stats, get_all_time_stats
        s24 = get_usage_stats(hours=24)
        at = get_all_time_stats()
        m["usage"] = {
            "24h_calls": s24["total_calls"], "24h_tokens": s24["total_tokens"],
            "all_calls": at["total_calls"], "all_tokens": at["total_tokens"],
            "cost_yuan": at["estimated_cost_yuan"],
        }
    except Exception:
        pass

    # 2. Agent health
    agents = {
        "ceo": "agents.ceo_agent.agent", "codex": "agents.codex_agent.agent",
        "qa": "agents.qa_agent.agent", "cto": "agents.cto_agent.agent",
        "system": "agents.system_agent.agent", "openclaw": "agents.openclaw_agent.agent",
        "image": "agents.image_agent.agent", "marketing": "agents.marketing_agent.agent",
        "video": "agents.video_agent.agent", "data": "agents.data_agent.agent",
    }
    m["agents"] = {}
    for name, mod in agents.items():
        try:
            __import__(mod)
            m["agents"][name] = "ok"
        except Exception:
            m["agents"][name] = "err"

    # 3. Cache
    try:
        from core.cache_store import cache
        m["cache"] = cache.stats()
    except Exception:
        pass

    # 4. Payment
    try:
        from backend.services.payment_service import get_payment_service
        ps = get_payment_service()
        m["payment"] = {"active": ps.available, "tx_count": len(ps.get_payment_history())}
    except Exception:
        pass

    # 5. DB row counts
    try:
        from backend.database.database import get_db
        with get_db() as db:
            m["db"] = {
                "sessions": db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0],
                "steps": db.execute("SELECT COUNT(*) FROM steps").fetchone()[0],
                "memories": db.execute("SELECT COUNT(*) FROM memories").fetchone()[0],
                "audit_logs": db.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0],
            }
    except Exception:
        pass

    # 6. Boss operating loop (human acceptance + observed outcomes)
    try:
        from backend.services.boss_command_center import get_boss_command_center
        m["boss"] = get_boss_command_center().get_operating_summary()
    except Exception:
        pass

    return m


@router.get("/health", summary="Agent详细健康")
def agent_health():
    agents = {}
    for name in ["ceo", "codex", "qa", "cto", "system", "openclaw", "image", "marketing", "video", "data"]:
        try:
            __import__(f"agents.{name}_agent.agent")
            agents[name] = "healthy"
        except Exception as e:
            agents[name] = str(e)[:60]
    return {"agents": agents}


@router.get("/doctor", summary="Runtime self-check")
def doctor(deep: bool = Query(False, description="Run slower checks such as browser launch and forced AI service scan")):
    from backend.services.doctor import run_doctor

    return run_doctor(deep=deep)


@router.get("/capabilities", summary="Capability readiness matrix")
def capabilities():
    from backend.services.doctor import get_capability_matrix

    return get_capability_matrix()
