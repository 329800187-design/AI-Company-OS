"""MiniDelivery 路由器 — 最小可交付闭环 API"""
import json
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import PlainTextResponse, FileResponse

from backend.minidelivery.models import XHSCopyRequest, CopyPackRequest, SaveFromAgentRequest
from backend.minidelivery.pipeline import run_pipeline, run_copy_pack_pipeline
from backend.minidelivery.artifact_writer import OUTPUT_ROOT, ensure_output_dir

router = APIRouter(prefix="/minidelivery", tags=["MiniDelivery / 最小交付闭环"])


# ── 旧接口（兼容保留）──────────────────────────────────────

@router.post("/xhs-copy-pack", summary="小红书文案包生成（旧接口）",
             description="输入业务目标，生成完整的小红书种草文案包 Markdown 文件并严格验收")
def create_xhs_copy_pack(request: XHSCopyRequest):
    result = run_pipeline(request.goal)
    return result.model_dump()


# ── 新通用接口 ─────────────────────────────────────────────

@router.post("/copy-pack", summary="通用文案包生成",
             description="输入业务目标，支持小红书/抖音平台，生成文案包 Markdown 文件并严格验收")
def create_copy_pack(request: CopyPackRequest):
    result = run_copy_pack_pipeline(
        goal=request.goal,
        platform=request.platform,
        artifact_type=request.artifact_type,
    )
    return result.model_dump()


# ── Agent 结果保存（Phase 1A）──────────────────────────────

# 每个 agent_id 对应的中文标签
_AGENT_LABELS: Dict[str, str] = {
    "marketing": "营销文案包",
    "image": "图片提示词 / 视觉 Brief",
    "data": "数据分析报告",
    "research": "调研简报",
    "website": "落地页草稿",
}


def _render_marketing(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 marketing agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '营销文案包'}", "", f"> 目标：{goal}", ""]

    headline = so.get("headline") or so.get("title", "")
    if headline:
        lines += ["## 标题", "", headline, ""]

    body = so.get("body") or so.get("content", "")
    if body:
        lines += ["## 正文", "", body, ""]

    cta = so.get("cta") or so.get("call_to_action", "")
    if cta:
        lines += ["## 行动号召", "", cta, ""]

    hashtags = so.get("hashtags") or so.get("tags", [])
    if hashtags:
        tag_str = " ".join(f"#{t}" if not t.startswith("#") else t for t in hashtags)
        lines += ["## 标签", "", tag_str, ""]

    keywords = so.get("keywords", [])
    if keywords:
        lines += ["## 关键词", "", ", ".join(keywords), ""]

    # 保留 warnings/errors/metadata
    _append_meta(lines, result)
    return "\n".join(lines)


def _render_image(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 image agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '图片提示词 / 视觉 Brief'}", "", f"> 目标：{goal}", ""]

    for key, label in [
        ("main_prompt", "主提示词"),
        ("detail_prompt", "细节提示词"),
        ("scene_prompt", "场景提示词"),
        ("negative_prompt", "负向提示词"),
    ]:
        val = so.get(key, "")
        if val:
            lines += [f"## {label}", "", val, ""]

    # 如果以上都没有，尝试通用 content
    if not any(so.get(k) for k in ["main_prompt", "detail_prompt", "scene_prompt", "negative_prompt"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    tips = so.get("usage_tips") or so.get("tips", "")
    if tips:
        lines += ["## 使用建议", "", tips, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_data(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 data agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '数据分析报告'}", "", f"> 目标：{goal}", ""]

    for key, label in [
        ("analysis_goal", "分析目标"),
        ("data_scope", "数据范围"),
        ("core_metrics", "核心指标"),
        ("trend_observations", "趋势观察"),
        ("anomaly_checks", "异常检查"),
        ("business_interpretation", "业务解读"),
        ("action_recommendations", "行动建议"),
    ]:
        val = so.get(key, "")
        if val:
            val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
            lines += [f"## {label}", "", val_str, ""]

    if not any(so.get(k) for k in ["analysis_goal", "data_scope", "core_metrics"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_research(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 research agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '调研简报'}", "", f"> 目标：{goal}", ""]

    for key, label in [
        ("research_goal", "调研目标"),
        ("target_users", "目标用户"),
        ("competitor_dimensions", "竞品维度"),
        ("pain_points", "痛点分析"),
        ("content_opportunities", "内容机会"),
        ("risk_warnings", "风险提示"),
        ("next_steps", "下一步"),
    ]:
        val = so.get(key, "")
        if val:
            val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
            lines += [f"## {label}", "", val_str, ""]

    if not any(so.get(k) for k in ["research_goal", "target_users"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_website(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """渲染 website agent 的 Markdown 交付物"""
    so = result.get("structured_output") or result.get("output") or {}
    lines = [f"# {title or '落地页草稿'}", "", f"> 目标：{goal}", ""]

    for key, label in [
        ("page_positioning", "页面定位"),
        ("hero_title", "主标题"),
        ("subtitle", "副标题"),
        ("selling_points", "卖点"),
        ("page_structure", "页面结构"),
        ("cta", "行动号召"),
        ("faq", "常见问题"),
        ("visual_suggestions", "视觉建议"),
    ]:
        val = so.get(key, "")
        if val:
            val_str = json.dumps(val, ensure_ascii=False) if isinstance(val, (dict, list)) else str(val)
            lines += [f"## {label}", "", val_str, ""]

    if not any(so.get(k) for k in ["hero_title", "page_positioning"]):
        content = so.get("content", "")
        if content:
            lines += ["## 内容", "", content, ""]

    _append_meta(lines, result)
    return "\n".join(lines)


def _render_generic(result: Dict, goal: str, title: Optional[str] = None) -> str:
    """通用渲染：未知 agent_id 时使用"""
    agent_id = result.get("agent_id", "unknown")
    label = _AGENT_LABELS.get(agent_id, agent_id)
    lines = [f"# {title or f'{label} 交付物'}", "", f"> 目标：{goal}", ""]

    so = result.get("structured_output") or result.get("output") or {}
    if so:
        lines += ["## 结构化产出", "", "```json"]
        lines.append(json.dumps(so, ensure_ascii=False, indent=2))
        lines += ["```", ""]

    artifacts = result.get("artifacts", [])
    if artifacts:
        lines += ["## 产物路径", ""]
        for a in artifacts:
            lines.append(f"- `{a}`")
        lines.append("")

    _append_meta(lines, result)
    return "\n".join(lines)


def _append_meta(lines: list, result: Dict) -> None:
    """追加 warnings/errors/metadata 到 Markdown 末尾"""
    warnings = result.get("warnings", [])
    errors = result.get("errors", [])
    metadata = result.get("metadata", {})

    if warnings:
        lines += ["## ⚠️ 警告", ""]
        for w in warnings:
            lines.append(f"- {w}")
        lines.append("")

    if errors:
        lines += ["## ❌ 错误", ""]
        for e in errors:
            lines.append(f"- {e}")
        lines.append("")

    if metadata:
        lines += ["## 元数据", "", "```json"]
        lines.append(json.dumps(metadata, ensure_ascii=False, indent=2))
        lines += ["```", ""]


_RENDERER_MAP = {
    "marketing": _render_marketing,
    "image": _render_image,
    "data": _render_data,
    "research": _render_research,
    "website": _render_website,
}


@router.post("/save-from-agent", summary="保存 Agent 结果到交付中心",
             description="将 AgentRunResult 转为可保存的交付物，不调用任何生产 pipeline")
def save_from_agent(request: SaveFromAgentRequest):
    agent_id = request.agent_id
    result = request.agent_result

    # 渲染 Markdown 交付物
    renderer = _RENDERER_MAP.get(agent_id, _render_generic)
    artifact_md = renderer(result, request.goal, request.title)

    # 生成 task_id 并保存
    task_id = f"agent_{uuid.uuid4().hex[:12]}"
    task_dir = ensure_output_dir(task_id)

    # 写入 artifact.md
    md_path = task_dir / "artifact.md"
    md_path.write_text(artifact_md, encoding="utf-8")

    # 写入 raw_agent_result.json
    raw_path = task_dir / "raw_agent_result.json"
    raw_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 写入 result.json（完整元数据）
    result_json = {
        "task_id": task_id,
        "goal": request.goal,
        "agent_id": agent_id,
        "artifact_type": request.artifact_type or agent_id,
        "title": request.title,
        "source_page": request.source_page,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "ok": result.get("ok", False),
        "mode": "agent_save",
        "summary": result.get("summary", ""),
        "artifact_path": str(md_path),
        "raw_agent_result_path": str(raw_path),
    }
    json_path = task_dir / "result.json"
    json_path.write_text(
        json.dumps(result_json, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return {
        "task_id": task_id,
        "artifact_path": str(md_path),
        "result_path": str(json_path),
        "agent_id": agent_id,
        "artifact_type": request.artifact_type or agent_id,
    }


# ── 列表接口（Phase 2A）─────────────────────────────────────

@router.get("/tasks", summary="交付物列表",
            description="扫描 output/minidelivery/*/result.json，返回列表，支持搜索、筛选与分页")
def list_tasks(
    q: Optional[str] = Query(None, description="搜索关键词，匹配 goal/task_id/agent_id/artifact_type/source_page，大小写不敏感"),
    agent_id: Optional[str] = Query(None, description="按 agent_id 筛选"),
    artifact_type: Optional[str] = Query(None, description="按 artifact_type 筛选"),
    source_page: Optional[str] = Query(None, description="按 source_page 筛选"),
    limit: int = Query(50, ge=1, le=100, description="每页条数，默认 50，最大 100"),
    offset: int = Query(0, ge=0, description="跳过前 N 条，默认 0"),
):
    tasks: List[Dict[str, Any]] = []
    warnings: List[str] = []

    minidelivery_root = OUTPUT_ROOT / "minidelivery"
    if not minidelivery_root.exists():
        return {"tasks": [], "warnings": [], "total": 0, "limit": limit, "offset": 0, "has_more": False}

    for task_dir in sorted(minidelivery_root.iterdir()):
        if not task_dir.is_dir():
            continue
        result_path = task_dir / "result.json"
        if not result_path.exists():
            continue
        try:
            with open(result_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            warnings.append(f"跳过损坏的 result.json: {task_dir.name} ({exc})")
            continue

        # 构建摘要（不读取 artifact.md 全文）
        task_id = data.get("task_id", task_dir.name)
        entry = {
            "task_id": task_id,
            "goal": data.get("goal", ""),
            "agent_id": data.get("agent_id", ""),
            "artifact_type": data.get("artifact_type", ""),
            "source_page": data.get("source_page", ""),
            "created_at": data.get("created_at", ""),
            "artifact_path": data.get("artifact_path", ""),
            "result_path": str(result_path),
        }

        # 如果 result.json 没有 created_at，用文件修改时间兜底
        if not entry["created_at"]:
            import os as _os
            mtime = _os.path.getmtime(result_path)
            from datetime import datetime, timezone
            entry["created_at"] = datetime.fromtimestamp(mtime, tz=timezone.utc).isoformat()

        # 精确筛选
        if agent_id and entry["agent_id"] != agent_id:
            continue
        if artifact_type and entry["artifact_type"] != artifact_type:
            continue
        if source_page and entry["source_page"] != source_page:
            continue

        # 关键词搜索（大小写不敏感，匹配 result.json 元数据字段）
        if q:
            q_lower = q.lower()
            searchable = " ".join([
                entry.get("goal", ""),
                entry.get("task_id", ""),
                entry.get("agent_id", ""),
                entry.get("artifact_type", ""),
                entry.get("source_page", ""),
            ]).lower()
            if q_lower not in searchable:
                continue

        tasks.append(entry)

    # 按 created_at 倒序
    tasks.sort(key=lambda t: t.get("created_at", ""), reverse=True)

    # 分页
    total = len(tasks)
    page = tasks[offset: offset + limit]
    has_more = (offset + limit) < total

    return {
        "tasks": page,
        "warnings": warnings,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": has_more,
    }


# ── 读取接口 ───────────────────────────────────────────────

@router.get("/tasks/{task_id}", summary="查询任务结果",
            description="返回 result.json 内容，含 raw_agent_result 摘要信息")
def get_task_result(task_id: str):
    json_path = OUTPUT_ROOT / task_id / "result.json"
    if not json_path.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")
    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 补充 raw_agent_result 信息
    raw_path = OUTPUT_ROOT / task_id / "raw_agent_result.json"
    data["has_raw_agent_result"] = raw_path.exists()
    if raw_path.exists():
        try:
            with open(raw_path, "r", encoding="utf-8") as f:
                raw = json.load(f)
            # 提取摘要：优先 summary，否则取 structured_output 前 200 字
            summary = raw.get("summary", "")
            if not summary:
                so = raw.get("structured_output") or raw.get("output") or {}
                summary = json.dumps(so, ensure_ascii=False)[:200] if so else ""
            data["agent_result_summary"] = summary
        except (json.JSONDecodeError, UnicodeDecodeError):
            data["agent_result_summary"] = ""

    return data


@router.get("/tasks/{task_id}/artifact", summary="读取产物内容",
            description="返回 Markdown 产物原文",
            response_class=PlainTextResponse)
def get_task_artifact(task_id: str):
    task_dir = OUTPUT_ROOT / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 优先查找 xiaohongshu_pack.md，再查找 copy_pack.md，再查找 artifact.md
    for name in ["xiaohongshu_pack.md", "copy_pack.md", "artifact.md"]:
        md_path = task_dir / name
        if md_path.exists():
            return PlainTextResponse(md_path.read_text(encoding="utf-8"))

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 产物文件不存在")


# ── 下载接口（Phase 2B）─────────────────────────────────────

def _validate_task_id(task_id: str) -> bool:
    """验证 task_id 防止路径穿越"""
    # 只允许字母、数字、下划线、连字符
    import re
    return bool(re.match(r'^[a-zA-Z0-9_-]+$', task_id))


@router.get("/tasks/{task_id}/download", summary="下载产物文件",
            description="下载指定任务的 artifact.md 文件",
            response_class=FileResponse)
def download_task_artifact(task_id: str):
    """下载指定任务的 artifact.md 文件"""
    # 防路径穿越
    if not _validate_task_id(task_id):
        raise HTTPException(status_code=400, detail="无效的 task_id")

    task_dir = OUTPUT_ROOT / task_id
    if not task_dir.exists():
        raise HTTPException(status_code=404, detail=f"任务 {task_id} 不存在")

    # 优先查找 xiaohongshu_pack.md，再查找 copy_pack.md，再查找 artifact.md
    for name in ["xiaohongshu_pack.md", "copy_pack.md", "artifact.md"]:
        md_path = task_dir / name
        if md_path.exists():
            # 安全检查：确保文件在预期目录内
            resolved_path = md_path.resolve()
            resolved_task_dir = task_dir.resolve()
            if not str(resolved_path).startswith(str(resolved_task_dir)):
                raise HTTPException(status_code=403, detail="路径越权")

            # 构建下载文件名
            download_filename = f"{task_id}.md"

            return FileResponse(
                path=str(md_path),
                media_type="text/markdown; charset=utf-8",
                filename=download_filename,
            )

    raise HTTPException(status_code=404, detail=f"任务 {task_id} 产物文件不存在")
