"""Governance 路由器 — 框架约束层 API"""
import json
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from pathlib import Path
from pydantic import BaseModel, Field
from typing import Optional

from backend.governance.classifier import classify_goal
from backend.governance.execution_plan import build_execution_plan
from backend.governance.run_record import (
    create_run_record, load_run_record, load_run_events,
    update_run_status, append_run_event, list_run_records,
    OUTPUT_ROOT,
)
from backend.governance.route_policy import (
    list_route_policies, routes_requiring_guard, routes_high_risk_without_guard,
    routes_deprecated_without_guard, routes_unprotected_execution,
    routes_controlled_entrypoints,
    find_unclassified_routes,
)

router = APIRouter(prefix="/governance", tags=["Governance / 框架约束层"])


def _build_collaboration_step_defs(detected_caps: list) -> list:
    """根据检测到的能力组合，构建协同步骤定义列表"""
    steps = []

    if "copywriting" in detected_caps:
        steps.append({
            "name": "生成文案",
            "task_type": "copywriting",
            "required_capability": "copywriting",
        })

    if "image" in detected_caps:
        steps.append({
            "name": "生成图片",
            "task_type": "image_generate",
            "required_capability": "image",
            "input_from": f"step_{len(steps)}" if steps else None,
        })

    if "research" in detected_caps:
        steps.append({
            "name": "执行调研",
            "task_type": "research",
            "required_capability": "copywriting",
        })

    if "data" in detected_caps:
        steps.append({
            "name": "数据分析",
            "task_type": "data_analyze",
            "required_capability": "data",
        })

    # Fallback: no specific capabilities detected
    if not steps:
        steps.append({
            "name": "执行任务",
            "task_type": "general",
            "required_capability": "copywriting",
        })

    return steps


class ClassifyRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=500)
    platform: Optional[str] = None


class PlanRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=500)
    platform: Optional[str] = None


class RunRequest(BaseModel):
    goal: str = Field(..., min_length=2, max_length=500)
    platform: Optional[str] = None
    execute: bool = False


@router.post("/classify", summary="目标分类",
             description="判断用户目标是否在系统受控能力范围内")
def api_classify(request: ClassifyRequest):
    result = classify_goal(request.goal, explicit_platform=request.platform)
    return result.model_dump()


@router.post("/plan", summary="构建执行计划",
             description="基于分类结果构建结构化执行计划")
def api_plan(request: PlanRequest):
    classification = classify_goal(request.goal, explicit_platform=request.platform)
    plan = build_execution_plan(request.goal, classification)
    return plan.model_dump()


@router.post("/run", summary="执行任务",
             description="分类 → 计划 → 执行（可选） → 记录")
def api_run(request: RunRequest):
    # Step 1: 分类
    classification = classify_goal(request.goal, explicit_platform=request.platform)

    # Step 2: 构建计划
    plan = build_execution_plan(request.goal, classification)

    # Step 3: 创建运行记录
    record = create_run_record(request.goal, plan)

    # Step 3.5: 记录分类事件
    append_run_event(record.run_id, "classification_done", {
        "ok": classification.ok,
        "capability_id": classification.capability_id,
        "confidence": classification.confidence,
        "needs_clarification": classification.needs_clarification,
        "reason": classification.reason,
    })

    # Step 4: 如果分类不通过，直接返回
    if not classification.ok:
        append_run_event(record.run_id, "run_rejected", {
            "reason": classification.reason,
            "needs_clarification": classification.needs_clarification,
        })
        return {
            "run_id": record.run_id,
            "status": plan.status,
            "plan_id": plan.plan_id,
            "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
            "plan": plan.model_dump(),
            "classification": classification.model_dump(),
        }

    # Step 5: 如果 execute=false，只返回计划
    if not request.execute:
        return {
            "run_id": record.run_id,
            "status": plan.status,
            "plan_id": plan.plan_id,
            "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
            "plan": plan.model_dump(),
            "classification": classification.model_dump(),
        }

    # Step 6: 执行
    cap_id = classification.capability_id
    platform = classification.normalized_inputs.get("platform", "xiaohongshu")

    if cap_id in ("copy_pack.xiaohongshu", "copy_pack.douyin"):
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.minidelivery.pipeline import run_copy_pack_pipeline
            result = run_copy_pack_pipeline(request.goal, platform=platform)

            update_run_status(
                record.run_id, "succeeded",
                artifact_path=result.artifact_path,
                result_ref=result.json_path,
            )
            append_run_event(record.run_id, "execution_succeeded", {
                "task_id": result.task_id,
                "artifact_path": result.artifact_path,
            })

            return {
                "run_id": record.run_id,
                "status": "succeeded",
                "plan_id": plan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
                "artifact_path": result.artifact_path,
                "json_path": result.json_path,
                "task_id": result.task_id,
                "mode": result.mode,
                "summary": result.summary,
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "result": result.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    if cap_id == "image_prompt_pack":
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.minidelivery.pipeline import run_image_prompt_pack_pipeline
            result = run_image_prompt_pack_pipeline(request.goal)

            update_run_status(
                record.run_id, "succeeded",
                artifact_path=result.artifact_path,
                result_ref=result.json_path,
            )
            append_run_event(record.run_id, "execution_succeeded", {
                "task_id": result.task_id,
                "artifact_path": result.artifact_path,
            })

            return {
                "run_id": record.run_id,
                "status": "succeeded",
                "plan_id": plan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
                "artifact_path": result.artifact_path,
                "json_path": result.json_path,
                "task_id": result.task_id,
                "mode": result.mode,
                "summary": result.summary,
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "result": result.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    if cap_id == "research_brief":
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.minidelivery.pipeline import run_research_brief_pipeline
            result = run_research_brief_pipeline(request.goal)

            update_run_status(
                record.run_id, "succeeded",
                artifact_path=result.artifact_path,
                result_ref=result.json_path,
            )
            append_run_event(record.run_id, "execution_succeeded", {
                "task_id": result.task_id,
                "artifact_path": result.artifact_path,
            })

            return {
                "run_id": record.run_id,
                "status": "succeeded",
                "plan_id": plan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
                "artifact_path": result.artifact_path,
                "json_path": result.json_path,
                "task_id": result.task_id,
                "mode": result.mode,
                "summary": result.summary,
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "result": result.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    if cap_id == "landing_page_copy":
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.minidelivery.pipeline import run_landing_page_copy_pipeline
            result = run_landing_page_copy_pipeline(request.goal)

            update_run_status(
                record.run_id, "succeeded",
                artifact_path=result.artifact_path,
                result_ref=result.json_path,
            )
            append_run_event(record.run_id, "execution_succeeded", {
                "task_id": result.task_id,
                "artifact_path": result.artifact_path,
            })

            return {
                "run_id": record.run_id,
                "status": "succeeded",
                "plan_id": plan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
                "artifact_path": result.artifact_path,
                "json_path": result.json_path,
                "task_id": result.task_id,
                "mode": result.mode,
                "summary": result.summary,
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "result": result.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    if cap_id == "data_report":
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.minidelivery.pipeline import run_data_report_pipeline
            result = run_data_report_pipeline(request.goal)

            update_run_status(
                record.run_id, "succeeded",
                artifact_path=result.artifact_path,
                result_ref=result.json_path,
            )
            append_run_event(record.run_id, "execution_succeeded", {
                "task_id": result.task_id,
                "artifact_path": result.artifact_path,
            })

            return {
                "run_id": record.run_id,
                "status": "succeeded",
                "plan_id": plan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
                "artifact_path": result.artifact_path,
                "json_path": result.json_path,
                "task_id": result.task_id,
                "mode": result.mode,
                "summary": result.summary,
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "result": result.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"执行失败: {str(e)}")

    if cap_id == "collaboration.controlled":
        append_run_event(record.run_id, "execution_started", {"capability_id": cap_id})

        try:
            from backend.services.collaboration_planner import build_collaboration_plan as build_cplan
            from backend.services.collaboration_executor import execute_collaboration_plan as exec_cplan

            # 1. 构建步骤定义（基于检测到的能力组合）
            detected_caps = classification.normalized_inputs.get("detected_capabilities", [])
            step_defs = _build_collaboration_step_defs(detected_caps)

            # 2. 构建协同计划
            cplan = build_cplan(request.goal, step_defs)
            append_run_event(record.run_id, "collaboration_plan_built", {
                "plan_id": cplan.plan_id,
                "steps_count": len(cplan.steps),
                "assigned_count": sum(1 for s in cplan.steps if s.status == "assigned"),
            })

            # 3. 执行协同计划
            cplan = exec_cplan(cplan)

            # 4. 持久化协同计划结果
            collab_path = OUTPUT_ROOT / record.run_id / "collaboration_result.json"
            collab_path.parent.mkdir(parents=True, exist_ok=True)
            collab_path.write_text(
                json.dumps(cplan.model_dump(), ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            collab_ref = str(collab_path)

            if cplan.status == "succeeded":
                update_run_status(record.run_id, "succeeded",
                                  collaboration_result_ref=collab_ref)
                append_run_event(record.run_id, "execution_succeeded", {
                    "plan_id": cplan.plan_id,
                    "steps_succeeded": sum(1 for s in cplan.steps if s.status == "succeeded"),
                })
            else:
                failed_steps = [s.id for s in cplan.steps if s.status == "failed"]
                update_run_status(record.run_id, "failed",
                                  failure_reason=f"协同步骤失败: {failed_steps}",
                                  collaboration_result_ref=collab_ref)
                append_run_event(record.run_id, "execution_failed", {
                    "failed_steps": failed_steps,
                })

            return {
                "run_id": record.run_id,
                "status": cplan.status,
                "plan_id": cplan.plan_id,
                "steps": [{"step_id": s.id, "name": s.name, "status": s.status,
                           "assigned_agent_id": s.assigned_agent_id} for s in cplan.steps],
                "plan": plan.model_dump(),
                "classification": classification.model_dump(),
                "collaboration_plan": cplan.model_dump(),
            }
        except Exception as e:
            update_run_status(record.run_id, "failed", failure_reason=str(e))
            append_run_event(record.run_id, "execution_failed", {"error": str(e)})
            raise HTTPException(status_code=500, detail=f"协同执行失败: {str(e)}")

    # 不支持的 capability → 不进入旧系统
    append_run_event(record.run_id, "run_rejected", {
        "reason": f"不支持的 capability: {cap_id}",
    })
    return {
        "run_id": record.run_id,
        "status": "rejected",
        "plan_id": plan.plan_id,
        "steps": [{"step_id": s.id, "name": s.name, "status": "planned"} for s in plan.steps],
        "plan": plan.model_dump(),
        "classification": classification.model_dump(),
    }


@router.get("/runs", summary="最近运行记录",
            description="返回最近 N 条运行记录列表，默认 limit=20")
def api_list_runs(limit: int = 20, offset: int = 0):
    all_records = list_run_records(limit=10000)
    total = len(all_records)
    page = all_records[offset : offset + limit]
    return {
        "total": total,
        "records": [r.model_dump() for r in page],
    }


@router.get("/runs/{run_id}", summary="查询运行记录")
def api_get_run(run_id: str):
    record = load_run_record(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"运行记录 {run_id} 不存在")
    data = record.model_dump()
    # 如果有协同计划结果，附加到响应中
    if record.collaboration_result_ref:
        ref_path = Path(record.collaboration_result_ref)
        if ref_path.exists():
            try:
                data["collaboration_plan"] = json.loads(
                    ref_path.read_text(encoding="utf-8")
                )
            except Exception:
                pass
    return data


@router.get("/runs/{run_id}/events", summary="查询运行事件")
def api_get_run_events(run_id: str):
    record = load_run_record(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"运行记录 {run_id} 不存在")
    events = load_run_events(run_id)
    return {"run_id": run_id, "events": events}


@router.get("/runs/{run_id}/artifact", summary="读取运行产物内容")
def api_get_run_artifact(run_id: str):
    """读取运行产物的 Markdown 内容

    安全限制：只允许读取 output/minidelivery 下的文件
    """
    record = load_run_record(run_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"运行记录 {run_id} 不存在")

    if not record.artifact_path:
        raise HTTPException(status_code=404, detail=f"运行记录 {run_id} 没有关联的产物文件")

    # 安全检查：只允许读取 output/minidelivery 下的文件
    artifact_path = Path(record.artifact_path)
    allowed_root = Path(__file__).resolve().parents[2] / "output" / "minidelivery"

    try:
        # resolve() 解析符号链接和 .. 等，防止路径穿越
        resolved_path = artifact_path.resolve()
        resolved_allowed = allowed_root.resolve()

        # 使用 relative_to 精确判断是否在允许的目录下
        resolved_path.relative_to(resolved_allowed)
    except ValueError:
        # relative_to 失败说明不在允许目录下
        raise HTTPException(status_code=403, detail="不允许读取该路径的文件")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"路径解析错误: {str(e)}")

    if not resolved_path.exists():
        raise HTTPException(status_code=404, detail=f"产物文件不存在: {artifact_path}")

    try:
        content = resolved_path.read_text(encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"读取文件失败: {str(e)}")

    return {
        "run_id": run_id,
        "artifact_path": str(artifact_path),
        "content": content,
    }


# ── Route Policy 查询接口 ──────────────────────────────────

@router.get("/routes", summary="查询所有路由策略",
            description="返回 Route Governance Inventory 中所有已登记的路由策略")
def api_list_routes():
    policies = list_route_policies()
    return {
        "total": len(policies),
        "policies": [p.model_dump() for p in policies],
    }


@router.get("/routes/high-risk", summary="查询高风险路由",
            description="返回 category=high_risk 且 requires_governance=true 且 has_guard=false 的路由")
def api_high_risk_routes():
    high_risk = routes_high_risk_without_guard()
    return {
        "total": len(high_risk),
        "policies": [p.model_dump() for p in high_risk],
    }


@router.get("/routes/unclassified", summary="查询未登记路由",
            description="扫描 FastAPI app 当前 routes，找出未在 registry 中登记的路由")
def api_unclassified_routes(request: Request):
    app = request.app
    unclassified = find_unclassified_routes(app)
    return {
        "total": len(unclassified),
        "routes": unclassified,
    }


@router.get("/routes/summary", summary="治理路由统计摘要",
            description="返回路由治理面板所需的汇总信息：分类统计、未治理执行入口、受控入口、治理完成状态")
def api_routes_summary():
    policies = list_route_policies()

    # 按 category 统计
    by_category: dict[str, int] = {}
    for p in policies:
        by_category[p.category] = by_category.get(p.category, 0) + 1

    unprotected = routes_unprotected_execution()
    high_risk = routes_high_risk_without_guard()
    deprecated = routes_deprecated_without_guard()
    controlled = routes_controlled_entrypoints()

    governance_complete = (
        len(unprotected) == 0
        and len(high_risk) == 0
        and len(deprecated) == 0
    )

    return {
        "total": len(policies),
        "by_category": by_category,
        "unprotected_execution_count": len(unprotected),
        "unprotected_execution": [p.model_dump() for p in unprotected],
        "high_risk_without_guard_count": len(high_risk),
        "deprecated_without_guard_count": len(deprecated),
        "controlled_entrypoints": [p.path for p in controlled],
        "governance_complete": governance_complete,
    }


# ── 推荐入口说明 ────────────────────────────────────────────

@router.get("/entrypoints", summary="推荐执行入口说明",
            description="返回推荐主入口、底层 capability 入口和推荐测试流程")
def api_entrypoints():
    return {
        "primary": {
            "path": "/governance/run",
            "method": "POST",
            "description": "推荐主入口：分类 → 计划 → 执行 → 记录",
            "example": {
                "goal": "帮我为手工耳环生成小红书种草文案",
                "platform": "xiaohongshu",
                "execute": True,
            },
        },
        "capability_endpoints": [
            {
                "path": "/minidelivery/copy-pack",
                "method": "POST",
                "description": "底层文案包能力入口，供 Governance 调用或兼容测试使用",
            },
            {
                "path": "/minidelivery/xhs-copy-pack",
                "method": "POST",
                "description": "旧小红书文案包兼容入口",
            },
        ],
        "deprecated_execution": "旧 workflow/template/commander continue 执行入口已返回 410，不应再直接调用",
        "test_page": {
            "path": "/governance/test-page",
            "method": "GET",
            "description": "浏览器测试页，直接调用 /governance/run",
        },
        "recommended_test_flow": [
            "POST /governance/classify",
            "POST /governance/plan",
            "POST /governance/run with execute=true",
            "GET /governance/runs/{run_id}",
            "GET /governance/runs/{run_id}/events",
        ],
    }


# ── 浏览器测试页 ─────────────────────────────────────────────

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


@router.get("/test-page", summary="Governance 主入口浏览器测试页",
            description="返回一个 HTML 页面，可直接在浏览器中测试 POST /governance/run")
def api_governance_test_page():
    page = _PROJECT_ROOT / "docs" / "governance_test_page.html"
    if not page.exists():
        raise HTTPException(status_code=404, detail="Governance test page not found")
    return HTMLResponse(page.read_text(encoding="utf-8"), media_type="text/html; charset=utf-8")
