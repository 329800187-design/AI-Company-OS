"""导出路由器 — 将 Commander 执行结果导出为 PDF / CSV / JSON / HTML"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse, HTMLResponse
from fastapi.responses import JSONResponse
from backend.database.database import init_db, SessionDB, StepDB
from backend.services.export_service import (
    export_session_as_html,
    export_session_as_csv,
    export_session_as_json,
)

router = APIRouter(prefix="/export", tags=["导出 / Export"])


@router.get("/session/{session_id}", summary="导出执行结果",
            description="将指定会话的执行结果导出为 HTML / CSV / JSON 格式")
def export_session(
    session_id: str,
    format: str = Query("html", pattern="^(html|csv|json)$"),
):
    """导出指定 session 的执行结果"""
    session = SessionDB.get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session 不存在")

    steps = StepDB.list_by_session(session_id)
    summary = session.get("summary", "")

    if format == "html":
        html = export_session_as_html(session, steps, summary)
        return HTMLResponse(content=html, headers={
            "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.html"',
        })
    elif format == "csv":
        csv_text = export_session_as_csv(session, steps, summary)
        return PlainTextResponse(content=csv_text, headers={
            "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.csv"',
        }, media_type="text/csv; charset=utf-8")
    elif format == "json":
        json_text = export_session_as_json(session, steps, summary)
        return PlainTextResponse(content=json_text, headers={
            "Content-Disposition": f'attachment; filename="report_{session_id[:8]}.json"',
        }, media_type="application/json; charset=utf-8")

    raise HTTPException(status_code=400, detail="不支持的导出格式")
