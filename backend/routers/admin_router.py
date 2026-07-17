"""Admin Panel Routes — user management, tier changes, system stats"""
from fastapi import APIRouter, HTTPException, Request, Query
from backend.auth.rbac import has_permission
from backend.database.database import get_db

router = APIRouter(prefix="/admin", tags=["Admin / 管理"])

def _require_admin(request: Request):
    user = getattr(request.state, "user", None)
    if not user: raise HTTPException(401, "请先登录")
    if not has_permission(user, "system_manage") and not has_permission(user, "user_manage"):
        raise HTTPException(403, "需要管理员权限")
    return user

@router.get("/users", summary="列出所有用户")
def list_users(request: Request, limit: int = Query(50, le=200)):
    _require_admin(request)
    with get_db() as db:
        rows = db.execute("""SELECT u.user_id,u.username,u.email,u.tier,u.created_at,u.last_login_at,
            COALESCE((SELECT SUM(tokens_used) FROM usage_billing WHERE user_id=u.user_id),0) as total_tokens,
            COALESCE((SELECT COUNT(*) FROM sessions WHERE sessions.session_id LIKE '%'),0) as session_count
            FROM users u ORDER BY u.created_at DESC LIMIT ?""", (limit,)).fetchall()
    return {"users": [{"user_id":r[0],"username":r[1],"email":r[2],"tier":r[3],"created_at":r[4],"last_login":r[5],"tokens_used":r[6],"sessions":r[7]} for r in rows],
            "count": len(rows)}

@router.put("/users/{user_id}/tier", summary="修改用户套餐")
def set_user_tier(user_id: str, tier: str = Query(...), request: Request = None):
    _require_admin(request)
    if tier not in ("free","pro","enterprise"):
        raise HTTPException(400, f"无效套餐: {tier}")
    with get_db() as db:
        db.execute("UPDATE users SET tier=? WHERE user_id=?", (tier, user_id))
    return {"status":"ok","user_id":user_id,"tier":tier}

@router.put("/users/{user_id}/disable", summary="禁用/启用用户")
def toggle_user(user_id: str, disabled: bool = Query(False), request: Request = None):
    _require_admin(request)
    # Simple implementation: if disabled, set tier to a restricted level
    with get_db() as db:
        if disabled:
            db.execute("UPDATE users SET tier='disabled' WHERE user_id=?", (user_id,))
        else:
            db.execute("UPDATE users SET tier='free' WHERE user_id=?", (user_id,))
    return {"status":"ok","user_id":user_id,"disabled":disabled}

@router.get("/stats", summary="管理后台统计")
def admin_stats(request: Request):
    _require_admin(request)
    with get_db() as db:
        total_users = db.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        paying = db.execute("SELECT COUNT(*) FROM users WHERE tier IN ('pro','enterprise')").fetchone()[0]
        total_sessions = db.execute("SELECT COUNT(*) FROM sessions").fetchone()[0]
        total_tokens = db.execute("SELECT COALESCE(SUM(total_tokens),0) FROM usage_billing").fetchone()[0]
        revenue = db.execute("SELECT COALESCE(SUM(cost_yuan),0) FROM usage_billing").fetchone()[0]
    return {"users":{"total":total_users,"paying":paying},"sessions":total_sessions,"tokens":total_tokens,"revenue_yuan":round(revenue,2)}
