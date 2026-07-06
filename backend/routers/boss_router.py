"""Boss Router — 老板运营指挥台 API"""
import uuid
import json
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field
from backend.services.boss_command_center import get_boss_command_center, MODULE_ORDER
from backend.security import input_validator, rate_limiter

router = APIRouter(prefix="/boss", tags=["Boss / 老板指挥台"])


class MissionCreateRequest(BaseModel):
    """创建 Mission 请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    auto_run: bool = Field(default=False, description="创建后立即执行")
    enabled_modules: Optional[List[str]] = Field(default=None, description="启用的模块 ID 列表，None 表示全部")
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionFromTemplateRequest(BaseModel):
    """从模板创建 Mission 请求"""
    template_id: str = Field(..., description="模板 ID")
    goal: Optional[str] = Field(default=None, description="覆盖模板默认目标")
    auto_run: bool = Field(default=False, description="创建后立即执行")
    enabled_modules: Optional[List[str]] = Field(default=None, description="覆盖模板默认模块")
    inputs: Optional[Dict[str, str]] = Field(default=None, description="补充输入信息")
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionRunRequest(BaseModel):
    """执行 Mission 请求"""
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class ModuleRunRequest(BaseModel):
    """执行单个模块请求"""
    allow_browser_automation: bool = Field(default=False, description="是否允许浏览器自动化采集（需显式授权）")


class MissionAcceptRequest(BaseModel):
    """用户接受 Mission 结果请求"""
    comment: str = Field(default="", description="用户备注")


@router.get("/templates", summary="模板列表")
def list_templates():
    """返回所有内置任务模板"""
    service = get_boss_command_center()
    templates = service.get_templates()
    return {"templates": templates, "total": len(templates)}


@router.post("/missions/from-template", summary="从模板创建 Mission")
def create_mission_from_template(request: MissionFromTemplateRequest):
    """根据模板创建 Mission"""
    # Governance Guard: 有 goal 时检查，只有 template_id 无 goal 时不 block
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    is_allowed, rate_msg = rate_limiter.check("boss", max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    service = get_boss_command_center()
    mission = service.create_mission_from_template(
        template_id=request.template_id,
        goal=request.goal,
        enabled_modules=request.enabled_modules,
        inputs=request.inputs,
        auto_run=request.auto_run,
        allow_browser_automation=request.allow_browser_automation,
    )
    if not mission:
        raise HTTPException(status_code=404, detail=f"模板 {request.template_id} 不存在")
    return mission


@router.post("/missions", summary="创建 Mission")
def create_mission(request: MissionCreateRequest):
    """创建一个新 Mission，拆成模块（默认 5 个，可选部分）"""
    # Governance Guard: 拦截不支持的目标
    from backend.governance.guard import guard_payload, governance_block_response
    blocked, classification = guard_payload(request.model_dump())
    if blocked:
        return governance_block_response(classification)

    is_valid, error_msg = input_validator.validate_message(request.goal)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    is_allowed, rate_msg = rate_limiter.check("boss", max_requests=10, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 验证 enabled_modules
    if request.enabled_modules is not None:
        valid_ids = set(MODULE_ORDER)
        invalid = [m for m in request.enabled_modules if m not in valid_ids]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"无效的模块 ID: {', '.join(invalid)}，可选: {', '.join(MODULE_ORDER)}"
            )
        if not request.enabled_modules:
            raise HTTPException(status_code=400, detail="enabled_modules 不能为空")

    service = get_boss_command_center()
    mission = service.create_mission(
        request.goal,
        auto_run=request.auto_run,
        enabled_modules=request.enabled_modules,
        allow_browser_automation=request.allow_browser_automation,
    )
    return mission


@router.get("/missions", summary="Mission 列表")
def list_missions(limit: int = 20, offset: int = 0):
    """返回 Mission 列表"""
    service = get_boss_command_center()
    missions = service.list_missions(limit=limit, offset=offset)
    return {"missions": missions, "total": len(missions)}


@router.get("/missions/{mission_id}", summary="Mission 详情")
def get_mission(mission_id: str):
    """返回 Mission 详情（含各模块结果）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")
    return mission


@router.get("/missions/{mission_id}/events", summary="Mission 事件日志")
def get_mission_events(mission_id: str):
    """返回 Mission 的事件列表（时间升序）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    events = service.get_events(mission_id)
    return {"mission_id": mission_id, "events": events, "total": len(events)}


@router.get("/missions/{mission_id}/export", summary="导出 Mission 报告")
def export_mission(mission_id: str, format: str = Query(default="json", pattern="^(json|markdown)$")):
    """导出 Mission 为 JSON 或 Markdown"""
    service = get_boss_command_center()
    exported = service.export_mission(mission_id, fmt=format)
    if not exported:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    return Response(
        content=exported["content"],
        media_type=exported["content_type"],
        headers={
            "Content-Disposition": f'attachment; filename="{exported["filename"]}"'
        }
    )


@router.post("/missions/{mission_id}/run", summary="执行 Mission")
def run_mission(mission_id: str, request: MissionRunRequest = MissionRunRequest()):
    """执行完整 Mission（顺序执行模块，跳过 skipped）"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    # Governance Guard: 读取 mission goal 后检查
    from backend.governance.guard import guard_payload, governance_block_response
    mission_goal = mission.get("goal", "")
    if mission_goal:
        blocked, classification = guard_payload({"goal": mission_goal})
        if blocked:
            return governance_block_response(classification)

    if mission["status"] == "running":
        raise HTTPException(status_code=409, detail="Mission 正在执行中，请勿重复提交")

    mission = service.run_mission(mission_id, allow_browser_automation=request.allow_browser_automation)
    return mission


@router.post("/missions/{mission_id}/modules/{module_id}/run", summary="重跑单个模块")
def run_module(mission_id: str, module_id: str, request: ModuleRunRequest = ModuleRunRequest()):
    """单独重跑某个模块"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    # Governance Guard: 读取 mission goal 后检查
    from backend.governance.guard import guard_payload, governance_block_response
    mission_goal = mission.get("goal", "")
    if mission_goal:
        blocked, classification = guard_payload({"goal": mission_goal})
        if blocked:
            return governance_block_response(classification)

    # 验证 module_id 合法
    valid_modules = {m["module_id"] for m in mission.get("modules", [])}
    if module_id not in valid_modules:
        raise HTTPException(
            status_code=400,
            detail=f"无效的 module_id: {module_id}，可选: {', '.join(sorted(valid_modules))}"
        )

    mission = service.run_module(mission_id, module_id, allow_browser_automation=request.allow_browser_automation)
    return mission


@router.post("/missions/{mission_id}/accept", summary="用户接受 Mission 结果")
def accept_mission(mission_id: str, request: MissionAcceptRequest = MissionAcceptRequest()):
    """用户确认接受 Mission 结果，状态改为 done"""
    service = get_boss_command_center()
    mission = service.get_mission(mission_id)
    if not mission:
        raise HTTPException(status_code=404, detail=f"Mission {mission_id} 不存在")

    mission = service.accept_mission(mission_id, comment=request.comment)
    return mission


@router.get("/modules/definitions", summary="模块定义")
def get_module_definitions():
    """返回 5 个模块的定义（供前端渲染）"""
    from backend.services.boss_command_center import MODULE_DEFINITIONS
    return {
        "modules": [
            {
                "id": module_id,
                **MODULE_DEFINITIONS[module_id],
            }
            for module_id in MODULE_ORDER
        ]
    }


# ── Boss Lite ──────────────────────────────────────────────

# 业务 Agent 定义：每个 agent 对应的任务类型和目的
BOSS_LITE_AGENTS = [
    {
        "agent_id": "research",
        "title": "市场调研",
        "task_type": "research_brief",
        "purpose": "调研市场趋势、目标用户、竞品和机会",
        "prompt_tpl": "请围绕以下业务目标做一份市场调研简报：\n\n{goal}\n\n要求：\n1. 市场趋势与机会\n2. 目标用户画像\n3. 竞品分析（至少 3 个）\n4. 差异化切入点\n5. 风险提示\n6. 下一步建议",
    },
    {
        "agent_id": "marketing",
        "title": "营销方案",
        "task_type": "copywriting",
        "purpose": "生成营销策略、卖点、渠道打法和文案",
        "prompt_tpl": "请围绕以下业务目标制定一套营销方案：\n\n{goal}\n\n要求：\n1. 品牌定位与目标受众\n2. 核心卖点（3-5 个）\n3. 渠道策略（小红书/抖音/微信等）\n4. 内容选题方向（5 个以上）\n5. 3 条可直接使用的推广文案\n6. 推荐发布时间与互动钩子",
    },
    {
        "agent_id": "image",
        "title": "视觉方案",
        "task_type": "image_prompt",
        "purpose": "生成视觉方向、图片提示词和拍摄建议",
        "prompt_tpl": "请围绕以下业务目标制定视觉方案：\n\n{goal}\n\n要求：\n1. 视觉风格方向\n2. 主色调与色彩方案\n3. 3 组可用的 AI 图片生成提示词\n4. 拍摄/制图建议\n5. 适配平台（小红书/淘宝/官网等）的尺寸建议",
    },
    {
        "agent_id": "data",
        "title": "数据分析",
        "task_type": "data_report",
        "purpose": "分析关键指标、趋势和行动建议",
        "prompt_tpl": "请围绕以下业务目标做一份数据分析框架：\n\n{goal}\n\n要求：\n1. 需要关注的核心指标（KPI）\n2. 数据采集渠道与方法\n3. 基准值与目标值建议\n4. 关键趋势判断\n5. 数据驱动的行动建议\n6. 风险与限制说明",
    },
    {
        "agent_id": "website",
        "title": "落地页方案",
        "task_type": "landing_page_copy",
        "purpose": "生成落地页结构、首屏、卖点和 CTA",
        "prompt_tpl": "请围绕以下业务目标设计一个落地页方案：\n\n{goal}\n\n要求：\n1. 页面定位与目标受众\n2. Hero 区域（标题 + 副标题 + CTA）\n3. 3-5 个卖点板块\n4. 信任证明（案例/数据/背书）\n5. FAQ 区域\n6. SEO 建议\n7. 页面结构说明",
    },
]


class BossLiteRequest(BaseModel):
    """Boss Lite 一句话执行请求"""
    goal: str = Field(..., min_length=2, max_length=5000, description="业务目标")
    agents: Optional[List[str]] = Field(default=None, description="指定执行的 Agent 列表，None 表示全部 5 个")
    save_to_delivery: bool = Field(default=True, description="是否自动保存到交付中心")


@router.post("/lite/execute", summary="Boss Lite — 一句话目标 → 多 Agent 协同执行")
def boss_lite_execute(request: BossLiteRequest):
    """
    Boss Lite 最小闭环:
    1. 接收一句话业务目标
    2. 拆解为 3-5 个业务任务，映射到 marketing/image/data/research/website
    3. 顺序执行每个 agent（通过 /agents/{agent_id}/execute）
    4. 收集 structured_output
    5. 生成 Boss 汇总报告
    6. 保存到 MiniDelivery（可选）
    """
    # Note: Boss Lite is a meta-capability that orchestrates other agents.
    # Each agent has its own governance check, so we skip the top-level guard here.

    is_valid, error_msg = input_validator.validate_message(request.goal)
    if not is_valid:
        raise HTTPException(status_code=400, detail=error_msg)

    is_allowed, rate_msg = rate_limiter.check("boss_lite", max_requests=5, window_seconds=60)
    if not is_allowed:
        raise HTTPException(status_code=429, detail=rate_msg)

    # 确定要执行的 agents
    selected_agents = request.agents or [a["agent_id"] for a in BOSS_LITE_AGENTS]
    invalid = [a for a in selected_agents if a not in {x["agent_id"] for x in BOSS_LITE_AGENTS}]
    if invalid:
        raise HTTPException(status_code=400, detail=f"不支持的 Agent: {', '.join(invalid)}")

    agent_defs = [a for a in BOSS_LITE_AGENTS if a["agent_id"] in selected_agents]

    # 构建执行计划
    plan = []
    for i, agent_def in enumerate(agent_defs, 1):
        plan.append({
            "step": i,
            "agent_id": agent_def["agent_id"],
            "task_type": agent_def["task_type"],
            "title": agent_def["title"],
            "prompt": agent_def["prompt_tpl"].format(goal=request.goal),
            "purpose": agent_def["purpose"],
            "status": "pending",
        })

    # 顺序执行每个 agent
    from backend.services.agent_executor import execute_agent
    from backend.schemas.agent_protocol import AgentTask

    results: List[Dict[str, Any]] = []
    for task in plan:
        try:
            agent_task = AgentTask(
                task_id=f"boss_lite_{uuid.uuid4().hex[:8]}",
                goal=request.goal,
                task_type=task["task_type"],
                context={"source": "boss_lite", "prompt": task["prompt"]},
                input={"prompt": task["prompt"]},
            )
            result = execute_agent(task["agent_id"], agent_task)
            result_dict = result.model_dump(by_alias=False)
            task["status"] = "done" if result_dict.get("ok") else "failed"
            results.append({
                "agent_id": task["agent_id"],
                "title": task["title"],
                "ok": result_dict.get("ok", False),
                "summary": result_dict.get("summary", ""),
                "structured_output": result_dict.get("structured_output") or result_dict.get("output") or {},
                "warnings": result_dict.get("warnings", []),
                "errors": result_dict.get("errors", []),
                "error": result_dict.get("error"),
            })
        except Exception as e:
            task["status"] = "failed"
            results.append({
                "agent_id": task["agent_id"],
                "title": task["title"],
                "ok": False,
                "summary": "",
                "structured_output": {},
                "warnings": [],
                "errors": [str(e)],
                "error": str(e),
            })

    # 生成汇总
    succeeded = sum(1 for r in results if r["ok"])
    failed = len(results) - succeeded
    summary_text = f"Boss Lite 执行完成：{succeeded}/{len(results)} 个 Agent 成功"
    if failed > 0:
        summary_text += f"，{failed} 个失败"

    # 构建 Boss 汇总 structured_output
    boss_structured_output = {
        "goal": request.goal,
        "plan": plan,
        "results_summary": [
            {
                "agent_id": r["agent_id"],
                "title": r["title"],
                "ok": r["ok"],
                "summary": r["summary"],
            }
            for r in results
        ],
        "succeeded": succeeded,
        "failed": failed,
        "total": len(results),
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }

    # 保存到 MiniDelivery
    delivery_task_id = None
    if request.save_to_delivery:
        try:
            from backend.minidelivery.artifact_writer import ensure_output_dir

            # 渲染 Boss 汇总 Markdown
            artifact_md = _render_boss_lite_md(request.goal, plan, results, boss_structured_output)

            task_id = f"boss_{uuid.uuid4().hex[:12]}"
            task_dir = ensure_output_dir(task_id)

            # 写入 artifact.md
            md_path = task_dir / "artifact.md"
            md_path.write_text(artifact_md, encoding="utf-8")

            # 写入 raw_agent_result.json
            raw_path = task_dir / "raw_agent_result.json"
            raw_path.write_text(
                json.dumps(boss_structured_output, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )

            # 写入 result.json
            result_json = {
                "task_id": task_id,
                "goal": request.goal,
                "agent_id": "boss",
                "artifact_type": "boss_lite",
                "title": f"Boss Lite: {request.goal[:50]}",
                "source_page": "boss",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ok": succeeded > 0,
                "mode": "boss_lite",
                "summary": summary_text,
                "artifact_path": str(md_path),
                "raw_agent_result_path": str(raw_path),
            }
            json_path = task_dir / "result.json"
            json_path.write_text(
                json.dumps(result_json, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            delivery_task_id = task_id
        except Exception as e:
            # 保存失败不影响返回结果
            pass

    return {
        "ok": succeeded > 0,
        "task_id": delivery_task_id or f"boss_lite_{uuid.uuid4().hex[:8]}",
        "goal": request.goal,
        "plan": plan,
        "results": results,
        "summary": {
            "text": summary_text,
            "succeeded": succeeded,
            "failed": failed,
            "total": len(results),
        },
        "structured_output": boss_structured_output,
        "delivery_task_id": delivery_task_id,
    }


def _render_boss_lite_md(goal: str, plan: list, results: list, boss_so: dict) -> str:
    """渲染 Boss Lite 汇总报告为 Markdown — 老板可直接阅读的作战简报"""
    lines = [
        "# Boss Lite 作战报告",
        "",
        "## 总目标",
        "",
        goal,
        "",
        "---",
        "",
        "## 一、执行计划",
        "",
    ]

    for task in plan:
        status_icon = "✅" if task["status"] == "done" else "❌" if task["status"] == "failed" else "⏳"
        lines.append(f"- {status_icon} **{task['title']}** — {task['purpose']}")
    lines.append("")

    lines += ["---", "", "## 二、各部门结论", ""]

    for r in results:
        so = r.get("structured_output") or {}
        agent_id = r["agent_id"]
        status_icon = "✅" if r["ok"] else "❌"

        lines.append(f"### {status_icon} {r['title']}")
        lines.append("")

        # 按 agent 类型提取关键信息
        if agent_id == "research":
            _render_research_section(lines, r, so)
        elif agent_id == "marketing":
            _render_marketing_section(lines, r, so)
        elif agent_id == "image":
            _render_image_section(lines, r, so)
        elif agent_id == "data":
            _render_data_section(lines, r, so)
        elif agent_id == "website":
            _render_website_section(lines, r, so)
        else:
            _render_generic_section(lines, r, so)

        if r.get("error"):
            lines.append(f"⚠️ 错误: {r['error']}")
            lines.append("")

    # Boss 最终建议 — 基于实际结果动态生成
    lines += ["---", "", "## 三、Boss 最终建议", ""]

    succeeded_agents = [r["agent_id"] for r in results if r["ok"]]
    failed_agents = [r["agent_id"] for r in results if not r["ok"]]

    if "research" in succeeded_agents:
        lines.append("- **先做什么：** 确认市场调研的核心发现，验证目标用户需求和竞品差距")
    elif "marketing" in succeeded_agents:
        lines.append("- **先做什么：** 基于营销方案准备第一批推广素材和文案")
    elif "data" in succeeded_agents:
        lines.append("- **先做什么：** 先建立关键指标看板，用数据确认最值得投入的方向")
    elif "website" in succeeded_agents:
        lines.append("- **先做什么：** 先把落地页核心结构搭出来，验证转化路径是否顺畅")
    elif "image" in succeeded_agents:
        lines.append("- **先做什么：** 先统一视觉方向，产出第一批可用于测试的素材")
    else:
        lines.append("- **先做什么：** 先重新执行 Boss Lite，补齐可用的部门输出")

    if "marketing" in succeeded_agents and "image" in succeeded_agents:
        lines.append("- **再做什么：** 结合营销文案和视觉方案，制作可用于投放的图文素材")
    elif "website" in succeeded_agents:
        lines.append("- **再做什么：** 参考落地页方案搭建转化页面，配合营销节奏上线")

    if "data" in succeeded_agents:
        lines.append("- **数据追踪：** 按数据分析框架建立效果追踪体系，每周复盘关键指标")

    if failed_agents:
        failed_titles = [r["title"] for r in results if not r["ok"]]
        lines.append(f"- **风险提醒：** {', '.join(failed_titles)} 执行失败，建议手动补充或重新执行")

    lines.append("- **下一步行动：** 选择 1-2 个最可行的方向，先跑最小可行版本（MVP），根据数据反馈迭代")
    lines.append("")

    lines += [
        "---",
        "",
        f"*由 AI Company OS Boss Lite 生成 · {boss_so.get('generated_at', '')}*",
    ]

    return "\n".join(lines)


def _render_research_section(lines: list, r: dict, so: dict):
    """渲染市场调研结论"""
    summary = r.get("summary") or so.get("summary") or so.get("market_summary", "")
    if summary:
        lines.append(f"- **摘要：** {summary[:200]}")
        lines.append("")

    key_findings = so.get("key_findings") or so.get("findings", [])
    if key_findings and isinstance(key_findings, list):
        lines.append("- **关键发现：**")
        for item in key_findings[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    opportunities = so.get("opportunities", [])
    if opportunities and isinstance(opportunities, list):
        lines.append("- **机会：**")
        for item in opportunities[:3]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    risks = so.get("risks", [])
    if risks and isinstance(risks, list):
        lines.append("- **风险：**")
        for item in risks[:3]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")


def _render_marketing_section(lines: list, r: dict, so: dict):
    """渲染营销方案结论"""
    headline = so.get("headline", "")
    if headline:
        lines.append(f"- **核心文案：** {headline}")
        lines.append("")

    body = so.get("body", "")
    if body and isinstance(body, str):
        lines.append(f"- **文案正文：** {body[:300]}")
        lines.append("")

    cta = so.get("cta", "")
    if cta:
        lines.append(f"- **CTA：** {cta}")
        lines.append("")

    selling_points = so.get("selling_points") or so.get("key_findings", [])
    if selling_points and isinstance(selling_points, list):
        lines.append("- **核心卖点：**")
        for item in selling_points[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    keywords = so.get("keywords") or so.get("hashtags", [])
    if keywords and isinstance(keywords, list):
        lines.append(f"- **关键词：** {', '.join(_format_boss_value(k) for k in keywords[:8])}")
        lines.append("")


def _render_image_section(lines: list, r: dict, so: dict):
    """渲染视觉方案结论"""
    style = so.get("style", "")
    if style:
        lines.append(f"- **视觉风格：** {style}")
        lines.append("")

    image_prompt = so.get("image_prompt", "")
    if image_prompt:
        lines.append(f"- **图片提示词：** {image_prompt[:200]}")
        lines.append("")

    color_palette = so.get("color_palette", "")
    if color_palette:
        lines.append(f"- **色彩方案：** {_format_boss_value(color_palette)}")
        lines.append("")

    usage = so.get("usage_suggestions", "")
    if usage:
        lines.append(f"- **使用建议：** {_format_boss_value(usage)[:200]}")
        lines.append("")


def _render_data_section(lines: list, r: dict, so: dict):
    """渲染数据分析结论"""
    question = so.get("analysis_question", "")
    if question:
        lines.append(f"- **分析主题：** {question}")
        lines.append("")

    metrics = so.get("key_metrics", [])
    if metrics and isinstance(metrics, list):
        lines.append("- **关键指标：**")
        for item in metrics[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    findings = so.get("findings", [])
    if findings and isinstance(findings, list):
        lines.append("- **发现：**")
        for item in findings[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")

    recommendations = so.get("recommendations", [])
    if recommendations and isinstance(recommendations, list):
        lines.append("- **建议：**")
        for item in recommendations[:5]:
            lines.append(f"  - {_format_boss_value(item)}")
        lines.append("")


def _render_website_section(lines: list, r: dict, so: dict):
    """渲染落地页方案结论"""
    page_goal = so.get("page_goal", "")
    if page_goal:
        lines.append(f"- **页面目标：** {page_goal}")
        lines.append("")

    hero = so.get("hero", {})
    if hero and isinstance(hero, dict):
        hero_headline = hero.get("headline", "")
        hero_sub = hero.get("subheadline", "")
        hero_cta = hero.get("cta", "")
        if hero_headline:
            lines.append(f"- **首屏标题：** {hero_headline}")
        if hero_sub:
            lines.append(f"  - 副标题：{hero_sub}")
        if hero_cta:
            lines.append(f"  - CTA：{hero_cta}")
        lines.append("")

    sections = so.get("sections", [])
    if sections and isinstance(sections, list):
        lines.append("- **页面板块：**")
        for item in sections[:5]:
            if isinstance(item, dict):
                lines.append(f"  - {item.get('title', item.get('name', str(item)))}")
            else:
                lines.append(f"  - {item}")
        lines.append("")

    ctas = so.get("ctas", [])
    if ctas and isinstance(ctas, list):
        lines.append(f"- **CTA：** {', '.join(_format_boss_value(c) for c in ctas[:3])}")
        lines.append("")

    seo = so.get("seo", {})
    if seo and isinstance(seo, dict):
        lines.append("- **SEO 建议：**")
        for k, v in list(seo.items())[:3]:
            lines.append(f"  - {k}: {v}")
        lines.append("")


def _render_generic_section(lines: list, r: dict, so: dict):
    """渲染通用结论（未知 agent 类型）"""
    summary = r.get("summary") or so.get("summary", "")
    if summary:
        lines.append(f"- **摘要：** {summary[:200]}")
        lines.append("")

    # 提取常见字段
    for key in ["headline", "title", "content", "body", "recommendations", "findings"]:
        val = so.get(key)
        if val and isinstance(val, str):
            lines.append(f"- **{key}：** {val[:200]}")
            lines.append("")
        elif val and isinstance(val, list):
            lines.append(f"- **{key}：**")
            for item in val[:5]:
                lines.append(f"  - {_format_boss_value(item)}")
            lines.append("")


def _format_boss_value(value: Any) -> str:
    """把字符串、数组或对象压成适合 Markdown 摘要展示的一行文本。"""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    if isinstance(value, (int, float, bool)):
        return str(value)
    if isinstance(value, list):
        return "；".join(_format_boss_value(item) for item in value if item is not None)
    if isinstance(value, dict):
        name = value.get("name") or value.get("title") or value.get("metric") or value.get("label")
        description = value.get("description") or value.get("summary") or value.get("value")
        formula = value.get("formula")
        parts = [str(part) for part in [name, description] if part]
        if formula:
            parts.append(f"公式：{formula}")
        if parts:
            return " — ".join(parts)
        return "；".join(f"{key}: {_format_boss_value(val)}" for key, val in list(value.items())[:4])
    return str(value)
