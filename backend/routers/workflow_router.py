"""工作流路由 - 多智能体协作流水线 + DAG 引擎"""
import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from backend.services.agent_loader import load_agent, load_agent_instance
from backend.schemas.task_schema import TaskCreate
from backend.services.task_service import task_service
from backend.ai_registry.registry import get_registry
from core.workflow.engine import get_workflow_engine
from backend.task_queue.queue import BackgroundTaskManager

router = APIRouter(prefix="/workflows", tags=["工作流 / Workflows"])


@router.post("/ceo-create-task", summary="CEO 拆解 → 存入任务中心",
             description="接收一个用户目标，由 CEO Agent 拆解为多个任务并存入任务中心")
def ceo_create_task(user_request: Dict[str, Any]):
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        "/workflows/ceo-create-task",
        reason="CEO 拆解旧入口已停用，避免绕过受控能力目录。",
    )

    ceo_agent = load_agent_instance("agents.ceo_agent.agent", "CEOAgent")
    if ceo_agent is None:
        raise HTTPException(status_code=503, detail="CEO Agent unavailable")
    ceo_result = ceo_agent.run(user_request)

    created_tasks_data = ceo_result.get("output", {}).get("created_tasks", [])
    saved_tasks = []

    for task_data in created_tasks_data:
        task_create = TaskCreate(**task_data)
        saved_task = task_service.create_task(task_create)
        saved_tasks.append(saved_task)

    return {
        "workflow": "ceo_create_task",
        "status": "done",
        "ceo_result": ceo_result,
        "saved_tasks": saved_tasks,
        "saved_count": len(saved_tasks),
    }


@router.post("/ceo-codex-task", summary="CEO 拆解 → Codex/OpenClaw 执行 → QA 验收（全流程）",
             description="""
一键完成完整工作流：
1. CEO Agent 拆解目标为任务列表
2. 自动分配给 Codex Agent（代码）或 OpenClaw Agent（浏览器）执行
3. QA Agent 验收评分
4. 所有结果写入任务中心
             """)
def ceo_codex_task(user_request: Dict[str, Any]):
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        "/workflows/ceo-codex-task",
        reason="CEO+Codex 多 Agent 旧流程已停用，避免绕过 Governance。",
    )

    ceo_agent = load_agent_instance("agents.ceo_agent.agent", "CEOAgent")
    codex_agent = load_agent_instance("agents.codex_agent.agent", "CodexAgent", timeout=30)
    allow_browser = user_request.get("allow_browser_automation", False)
    openclaw_agent = load_agent_instance(
        "agents.openclaw_agent.agent", "OpenClawAgent",
        headless=True, timeout=30, allow_browser_automation=allow_browser
    )
    system_agent = load_agent_instance("agents.system_agent.agent", "SystemAgent", timeout=120)
    qa_agent = load_agent_instance("agents.qa_agent.agent", "QAAgent")

    # 检查所有 agent 是否可用
    if not all([ceo_agent, codex_agent, openclaw_agent, system_agent, qa_agent]):
        unavailable = []
        if not ceo_agent: unavailable.append("CEO")
        if not codex_agent: unavailable.append("Codex")
        if not openclaw_agent: unavailable.append("OpenClaw")
        if not system_agent: unavailable.append("System")
        if not qa_agent: unavailable.append("QA")
        raise HTTPException(status_code=503, detail=f"Agents unavailable: {', '.join(unavailable)}")

    # Step 1: CEO 拆解
    ceo_result = ceo_agent.run(user_request)
    created_tasks_data = ceo_result.get("output", {}).get("created_tasks", [])

    if not created_tasks_data:
        return {
            "workflow": "ceo_codex_task",
            "status": "failed",
            "error": "CEO 未生成任何任务",
            "ceo_result": ceo_result,
        }

    results = []
    saved_tasks = []

    for task_data in created_tasks_data:
        task_create = TaskCreate(**task_data)
        saved_task = task_service.create_task(task_create)
        saved_tasks.append(saved_task)

        assigned_to = task_data.get("assigned_to", "")
        task_type = task_data.get("task_type", "")

        agent_task = {
            "task_id": saved_task.task_id,
            "task_type": task_type,
            "title": task_data.get("goal", ""),
            "goal": task_data.get("goal", ""),
            "code": task_data.get("code", ""),
            "files": task_data.get("files", {}),
            "url": task_data.get("url", ""),
            "selector": task_data.get("selector", ""),
            "expected_output": task_data.get("expected_output", {}),
        }

        # Step 2: 执行
        exec_result = None
        if assigned_to == "codex_agent":
            exec_result = codex_agent.run(agent_task)
        elif assigned_to == "openclaw_agent":
            exec_result = openclaw_agent.run(agent_task)
        elif assigned_to == "system_agent":
            exec_result = system_agent.run(agent_task)
        elif assigned_to in ("cc-switch", "chatgpt", "kimi"):
            # 通过 AI Registry 调用外部 AI 服务
            registry = get_registry()
            registry.scan_all()
            exec_result = registry.execute(assigned_to, {
                "prompt": task_data.get("goal", ""),
                "目标": task_data.get("goal", ""),
            })
        else:
            exec_result = {
                "agent": "skipped",
                "status": "skipped",
                "task_id": saved_task.task_id,
                "result": f"无匹配执行器: {assigned_to}",
            }

        # Step 3: QA 验收
        qa_input = {
            **agent_task,
            "result": exec_result.get("result", str(exec_result)) if exec_result else "",
        }
        qa_result = qa_agent.run(qa_input)
        qa_status = qa_result.get("status", "")
        # QA 中文状态 → TaskStatus 枚举值映射
        status_map = {"已完成": "done", "需复查": "review", "需重试": "retry"}
        mapped_status = status_map.get(qa_status, qa_status)

        # Step 4: 更新任务中心
        task_service.update_task(
            saved_task.task_id,
            status=mapped_status if mapped_status != saved_task.status else None,
            result={assigned_to: exec_result, "qa": qa_result},
            score=qa_result.get("score", 0),
        )

        results.append({
            "task": saved_task.model_dump(),
            "exec_result": exec_result,
            "qa_result": qa_result,
        })

    return {
        "workflow": "ceo_codex_task",
        "status": "done",
        "ceo_mode": "AI" if "AI" in ceo_result.get("summary", "") else "rule",
        "ceo_summary": ceo_result.get("summary", ""),
        "results": results,
        "task_count": len(results),
        "saved_count": len(saved_tasks),
    }


# ═══════════════════════════════════════════════════════════
# DAG 工作流引擎端点（v0.5.0）
# ═══════════════════════════════════════════════════════════

class RunWorkflowDAGRequest(BaseModel):
    workflow: str = Field(..., description="工作流名称")
    inputs: dict = Field(default_factory=dict, description="输入变量")


@router.get("/dag/list", summary="列出所有 DAG 工作流")
def dag_list():
    engine = get_workflow_engine()
    return {"workflows": engine.list_all(), "count": len(engine.list_all())}


@router.get("/dag/{name}", summary="查看 DAG 工作流详情")
def dag_detail(name: str):
    engine = get_workflow_engine()
    wf = engine.get(name)
    if not wf:
        raise HTTPException(status_code=404, detail=f"工作流不存在: {name}")
    return {
        "name": wf.name, "title": wf.title, "description": wf.description,
        "version": wf.version, "triggers": wf.triggers,
        "steps": [{"id": s.id, "agent": s.agent, "task_type": s.task_type,
                    "description": s.description, "depends_on": s.depends_on,
                    "condition": s.condition or "无"} for s in wf.steps],
    }


@router.post("/dag/run", summary="执行 DAG 工作流（同步）")
def dag_run(request: RunWorkflowDAGRequest):
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        "/workflows/dag/run",
        reason="DAG 同步执行旧入口已停用，避免绕过 Governance。",
    )

    engine = get_workflow_engine()
    result = engine.run(request.workflow, inputs=request.inputs)
    if result.get("status") == "error":
        raise HTTPException(status_code=400, detail=result.get("message", ""))
    return result


@router.post("/dag/run-async", summary="执行 DAG 工作流（异步）")
async def dag_run_async(request: RunWorkflowDAGRequest, fastapi_request: Request):
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        "/workflows/dag/run-async",
        reason="DAG 异步执行旧入口已停用，避免绕过 Governance。",
    )

    manager: BackgroundTaskManager = fastapi_request.app.state.manager
    task_id = f"wfdag_{uuid.uuid4().hex[:12]}"
    engine = get_workflow_engine()
    import asyncio

    def _make_cb(tid: str):
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            _loop = asyncio.new_event_loop()
            asyncio.set_event_loop(_loop)
        def cb(data: dict):
            try:
                if _loop.is_running():
                    asyncio.run_coroutine_threadsafe(
                        manager.push_progress(tid, {"type": "wf_dag_step", **data}), _loop
                    )
            except RuntimeError:
                pass
        return cb

    def _run():
        cb = _make_cb(task_id)
        return engine.run(request.workflow, inputs=request.inputs, progress_callback=cb)

    manager.submit(task_id, _run)
    return {"task_id": task_id, "workflow": request.workflow, "status": "queued"}
