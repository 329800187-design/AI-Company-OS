"""Commander 路由器 — 指挥官主脑接口"""
import uuid
import asyncio
from typing import Any, Callable, Dict, List, Optional
from pydantic import Field

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from backend.database.database import init_db, SessionDB
from backend.commander.commander import CommanderAgent
from backend.task_queue.queue import BackgroundTaskManager

router = APIRouter(prefix="/commander", tags=["指挥官 / Commander"])

# 注意：不再使用全局单例 CommanderAgent，每个请求创建新实例以避免跨请求状态泄露


class RunGoalRequest(BaseModel):
    """提交目标请求"""
    目标: str = ""


# ── 同步端点（保持向后兼容）───────────────────────────────

@router.post("/run", summary="提交目标，启动自主执行（同步）",
             description="输入一个高层目标，Commander 会自动拆解、执行、决策，直到完成或需要你介入。")
def commander_run(request: RunGoalRequest):
    """启动 Commander 自主执行（同步模式，HTTP 请求会等待执行完成）"""
    goal = request.目标
    if not goal:
        raise HTTPException(status_code=400, detail="目标不能为空")

    # Governance Guard: 拦截不在受控能力范围内的目标
    from backend.governance.guard import should_block_goal, governance_block_response
    blocked, classification = should_block_goal(goal)
    if blocked:
        return governance_block_response(classification)

    init_db()
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    # 创建 session
    SessionDB.create(session_id, goal)
    SessionDB.update(session_id, status="decomposing")

    # 拆解目标（每请求新建 Commander，避免跨请求状态泄露）
    cmdr = CommanderAgent()
    steps = cmdr.decompose_goal(goal, session_id)
    if not steps:
        SessionDB.update(session_id, status="failed", summary="拆解目标失败")
        return {"session_id": session_id, "status": "失败", "message": "无法拆解该目标"}

    # 执行
    result = cmdr.execute_session(session_id)
    result["session_id"] = session_id
    result["goal"] = goal
    return result


# ── 异步端点（新）────────────────────────────────────────

def _make_progress_callback(task_id: str, manager: BackgroundTaskManager) -> Callable:
    """创建同步的进度回调函数

    Commander 的 execute_session 是同步代码，无法直接 await。
    这个包装器接收 Commander 的进度事件，通过 asyncio 的事件循环推送给 WebSocket 客户端。

    Args:
        task_id: 后台任务 ID
        manager: BackgroundTaskManager 实例

    Returns:
        一个同步回调函数，签名 conforms to Callable[[dict], None]
    """
    # 捕获创建时的事件循环（主线程的 loop）
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        _main_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(_main_loop)

    def sync_cb(data: dict):
        """同步包装器 — 在 ThreadPoolExecutor 线程中调用"""
        try:
            if _main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    manager.push_progress(task_id, data), _main_loop
                )
            # event loop 未运行时不推送（测试环境正常现象）
        except RuntimeError:
            pass  # Event loop 已关闭，测试环境正常
        except Exception as e:
            if "Event loop is closed" not in str(e):
                print(f"[TaskQueue] 进度回调出错: {e}")

    return sync_cb


@router.post("/run-async", summary="提交目标，后台异步执行（推荐）",
             description="提交目标后立即返回 task_id，后台异步执行进度通过 WebSocket 实时推送。")
async def commander_run_async(request: RunGoalRequest, fastapi_request: Request):
    """异步启动 Commander 自主执行

    流程：
    1. 创建 session 并拆解目标（同步）
    2. 提交后台任务到 ThreadPoolExecutor
    3. 立即返回 task_id，前端通过 WebSocket 接收进度

    相比 /commander/run 同步模式的优势：
    - HTTP 请求不会卡住
    - 前端可通过 WebSocket 实时看到每步执行进度
    - 适合执行时间较长的复杂目标
    """
    goal = request.目标
    if not goal:
        raise HTTPException(status_code=400, detail="目标不能为空")

    # Governance Guard: 拦截不在受控能力范围内的目标
    from backend.governance.guard import should_block_goal, governance_block_response
    blocked, classification = should_block_goal(goal)
    if blocked:
        return governance_block_response(classification)

    # 获取 BackgroundTaskManager 实例（挂载在 app.state）
    manager: BackgroundTaskManager = fastapi_request.app.state.manager

    init_db()
    session_id = f"session_{uuid.uuid4().hex[:8]}"

    # 创建 session
    SessionDB.create(session_id, goal)
    SessionDB.update(session_id, status="decomposing")

    # 拆解目标（同步执行，通常很快；每请求新建 Commander）
    cmdr_async = CommanderAgent()
    steps = cmdr_async.decompose_goal(goal, session_id)
    if not steps:
        SessionDB.update(session_id, status="failed", summary="拆解目标失败")
        return {"session_id": session_id, "status": "失败", "message": "无法拆解该目标"}

    # 生成任务 ID
    task_id = f"commander_{uuid.uuid4().hex[:12]}"

    # 创建带进度回调的 Commander 实例
    progress_cb = _make_progress_callback(task_id, manager)
    async_commander = CommanderAgent(progress_callback=progress_cb)

    # 定义后台执行函数（同步，在 ThreadPoolExecutor 中运行）
    def run_commander_task():
        try:
            result = async_commander.execute_session(session_id)
            result["session_id"] = session_id
            result["goal"] = goal
            return result
        except Exception as e:
            import traceback
            error_detail = traceback.format_exc()
            SessionDB.update(session_id, status="failed", summary=f"执行异常: {str(e)[:200]}")
            return {"status": "failed", "session_id": session_id, "error": str(e)}

    # 提交到后台任务队列
    manager.submit(task_id, run_commander_task)

    return {
        "task_id": task_id,
        "session_id": session_id,
        "status": "queued",
        "message": "任务已提交，通过 WebSocket /ws/task/{task_id} 实时查看进度",
    }


# ── 任务状态查询 ──────────────────────────────────────────

@router.get("/tasks/{task_id}", summary="查看后台任务状态",
            description="查看异步任务的执行状态（queued/running/completed/failed）")
async def get_task_status(task_id: str, fastapi_request: Request):
    """查看后台任务的当前状态"""
    manager: BackgroundTaskManager = fastapi_request.app.state.manager
    task = manager.get_task(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task


@router.get("/tasks", summary="列出所有后台任务",
            description="列出所有异步执行的后台任务列表")
async def list_tasks(fastapi_request: Request):
    """列出所有后台任务"""
    manager: BackgroundTaskManager = fastapi_request.app.state.manager
    tasks = manager.list_tasks(limit=50)
    return {"tasks": tasks, "count": len(tasks)}


# ── 已有端点（保持兼容）───────────────────────────────────

@router.get("/sessions", summary="查看所有执行记录",
            description="返回所有 Commander 执行会话列表。")
def list_sessions():
    """列出所有执行记录"""
    init_db()
    sessions = SessionDB.list_all(20)
    return {"sessions": sessions, "count": len(sessions)}


@router.get("/sessions/{session_id}", summary="查看执行详情",
            description="查看一次 Commander 执行的完整步骤、状态和结果。")
def get_session(session_id: str):
    """查看某次执行的详细状态"""
    init_db()
    result = CommanderAgent().get_session_status(session_id)
    if result.get("status") == "error":
        raise HTTPException(status_code=404, detail="Session 不存在")
    return result


@router.delete("/sessions/{session_id}", summary="删除执行记录",
               description="删除某次 Commander 执行的所有记录（级联删除 steps + tasks）。")
def delete_session(session_id: str):
    """删除单条执行记录"""
    init_db()
    SessionDB.delete(session_id)
    return {"status": "ok", "message": "已删除"}


class ContinueRequest(BaseModel):
    """继续执行请求"""
    用户输入: Optional[str] = ""


@router.post("/sessions/{session_id}/continue", summary="继续暂停的执行",
             description="当 Commander 需要用户确认时卡住了，从这里回复继续。")
def continue_session(session_id: str, request: ContinueRequest):
    """继续被暂停的 Commander 执行"""
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        f"/commander/sessions/{session_id}/continue",
        reason="Commander 旧会话继续执行已停用，避免恢复旧编排绕过 Governance。",
    )


# ── 纯 AI 对话（不经过 Commander 任务编排）───────────────


class ChatMessage(BaseModel):
    """对话消息"""
    role: str = "user"  # "user" 或 "assistant"
    content: str = ""


class ChatRequest(BaseModel):
    """AI 对话请求"""
    message: str = ""
    history: List[ChatMessage] = Field(default_factory=list, description="历史对话记录")
    temperature: float = 0.7
    max_tokens: int = 4096


class ChatResponse(BaseModel):
    """AI 对话响应"""
    reply: str = ""
    model: str = ""
    provider: str = ""
    thinking: Optional[str] = None


@router.post("/chat/send", summary="AI 纯对话（不经过任务编排）",
             description="直接调用 AI 模型进行对话，不走 Commander 任务编排流水线，适合聊天问答。")
def chat_send(request: ChatRequest):
    """直接 AI 对话，支持上下文"""
    from core.brain_manager import get_brain_manager
    from backend.security import input_validator, rate_limiter

    # 输入验证
    is_valid, error_msg = input_validator.validate_message(request.message)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    # 速率限制
    is_allowed, rate_msg = rate_limiter.check("chat", max_requests=60, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    system_prompt = """你是 AI Company OS 的主脑助手。你负责理解用户目标、补充必要信息、解释系统能力，并协助用户把业务目标推进为可验收的计划。

系统是通用业务流程平台，不默认属于任何行业或渠道。不要把用户目标改写成电商、营销或其他特定行业任务；具体行业只来自用户输入。
回复使用中文，优先给出清晰、可执行的下一步。涉及高风险外部操作时，必须说明需要人工确认。"""
    history = [{"role": msg.role, "content": msg.content} for msg in request.history[-20:]]
    manager = get_brain_manager()
    result = manager.chat(
        request.message,
        system=system_prompt,
        temperature=request.temperature,
        max_tokens=request.max_tokens,
        history=history,
    )
    if not result.get("ok"):
        raise HTTPException(status_code=400, detail=result.get("error", "当前没有可用 AI 主脑"))
    current = manager.get_current()
    return ChatResponse(
        reply=result.get("reply", ""),
        model=result.get("model", current.get("model", "")),
        provider=result.get("brain", current.get("provider", "")),
        thinking=result.get("thinking"),
    )
