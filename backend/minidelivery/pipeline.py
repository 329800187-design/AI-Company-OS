"""管线 — 可复用的最小文案交付内核"""
import json
import os
import sys
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple

# 确保项目根目录在 sys.path 中
_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent)
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from backend.minidelivery.models import MiniDeliveryResult, VerificationChecks
from backend.minidelivery.spec import DeliverySpec, parse_delivery_spec
from backend.minidelivery.verifier import verify_artifact, verify_image_prompt_pack, verify_research_brief, verify_landing_page_copy, verify_data_report
from backend.minidelivery.artifact_writer import write_artifact
from backend.minidelivery.template_generator import (
    generate_copy_pack_template,
    generate_xhs_copy_pack_template,
    generate_image_prompt_pack_template,
    generate_research_brief_template,
    generate_landing_page_copy_template,
    generate_data_report_template,
)

# ── 平台 → md 文件名映射 ──────────────────────────────────

_PLATFORM_MD_NAMES = {
    "xiaohongshu": "xiaohongshu_pack.md",
    "douyin": "copy_pack.md",
}


def _build_api_prompt(spec: DeliverySpec) -> str:
    """基于 spec 构建严格约束的 API prompt。"""
    platform_name = "小红书" if spec.platform == "xiaohongshu" else "抖音"
    product = spec.product

    base = (
        f"【严格约束】你必须且只能围绕以下产品生成{platform_name}文案，禁止替换、改写、联想扩展为其他产品或品类。\n"
        f"产品/品类：{product}\n"
        f"业务目标原文：{spec.original_goal}\n\n"
        f"【产品锁定】生成的所有内容必须且只能围绕「{product}」。"
        f"严禁将其替换为任何其他产品。\n\n"
    )

    if spec.platform == "xiaohongshu":
        base += (
            "【输出格式】必须严格按以下 Markdown 结构输出，不要添加额外章节：\n\n"
            "## 标题方案\n### 标题 1\n(标题内容)\n### 标题 2\n(标题内容)\n### 标题 3\n(标题内容)\n\n"
            "## 目标人群\n(目标人群分析)\n\n"
            "## 正文文案\n(种草正文，至少 120 个中文字符)\n\n"
            "## 话题标签\n(至少 5 个话题标签，格式: #标签名)\n\n"
            "## 行动号召\n(引导用户行动的 CTA)\n\n"
            "## 发布建议\n(发布时间、频率、封面、排版等建议)\n"
        )
    else:
        base += (
            "【输出格式】必须严格按以下 Markdown 结构输出，不要添加额外章节：\n\n"
            "## 开头钩子\n(前 3 秒钩子文案)\n\n"
            "## 视频脚本 / 分镜\n(分镜 1-5，每镜包含画面、口播、字幕)\n\n"
            "## 卖点介绍\n(产品核心卖点)\n\n"
            "## 使用场景\n(使用/佩戴场景)\n\n"
            "## 互动引导\n(评论区互动话题)\n\n"
            "## 行动号召\n(CTA)\n\n"
            "## 发布建议\n(发布时间、BGM、投放建议等)\n"
        )

    return base


def _try_api_generation(spec: DeliverySpec) -> Dict[str, Any] | None:
    """尝试通过 API 生成内容。成功返回 dict，失败返回 None。"""
    try:
        from backend.adapters.api_model_adapter import ApiModelAdapter

        adapter = ApiModelAdapter()
        health = adapter.health_check()
        if not health.get("available"):
            return None

        prompt = _build_api_prompt(spec)
        task = {"goal": prompt, "task_type": "marketing"}

        result = adapter.run(task)
        if result.get("ok"):
            output_text = result.get("result", {}).get("output", "")
            if output_text and len(output_text) > 200:
                import uuid
                prefix = "xhs" if spec.platform == "xiaohongshu" else "dy"
                task_id = f"{prefix}_{uuid.uuid4().hex[:12]}"
                return {"markdown": output_text, "task_id": task_id}

        return None
    except Exception:
        return None


def _generate_fallback(spec: DeliverySpec) -> Tuple[str, str]:
    """Template fallback 生成。返回 (markdown_content, task_id)。"""
    tmpl = generate_copy_pack_template(spec)
    return tmpl["markdown"], tmpl["task_id"]


def _verify_and_build_result(
    goal: str,
    task_id: str,
    mode: str,
    markdown_content: str,
    spec: DeliverySpec,
    *,
    md_filename: Optional[str] = None,
    api_failed_checks: Optional[List[str]] = None,
    api_rejected_reason: Optional[str] = None,
    original_mode_attempted: Optional[str] = None,
) -> MiniDeliveryResult:
    """写入文件 → 验收 → 构建结果。"""
    md_name = md_filename or _PLATFORM_MD_NAMES.get(spec.platform, "copy_pack.md")

    result_json = {
        "task_id": task_id,
        "task_type": f"{spec.platform}_copy_pack",
        "goal": goal,
        "mode": mode,
    }
    paths = write_artifact(task_id, markdown_content, result_json, md_filename=md_name)

    checks, failed_checks = verify_artifact(paths["md_path"], goal, spec)
    ok = len(failed_checks) == 0

    platform_label = "小红书" if spec.platform == "xiaohongshu" else "抖音"
    if ok:
        summary = f"{platform_label}文案包生成成功（{mode}），所有验收检查通过。"
    else:
        summary = f"验收失败（{mode}），{len(failed_checks)} 项检查未通过：{', '.join(failed_checks)}"

    final_result = MiniDeliveryResult(
        ok=ok,
        task_id=task_id,
        mode=mode,
        artifact_path=paths["md_path"],
        json_path=paths["json_path"],
        checks=checks,
        failed_checks=failed_checks,
        summary=summary,
        api_failed_checks=api_failed_checks,
        api_rejected_reason=api_rejected_reason,
        original_mode_attempted=original_mode_attempted,
        spec=spec.model_dump(),
    )

    # 用完整结果覆盖 result.json
    with open(paths["json_path"], "w", encoding="utf-8") as f:
        f.write(json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2))

    return final_result


# ── 核心入口 ──────────────────────────────────────────────

def run_copy_pack_pipeline(
    goal: str,
    platform: Optional[str] = None,
    artifact_type: Optional[str] = None,
) -> MiniDeliveryResult:
    """
    通用文案包生成管线。

    1. parse_delivery_spec
    2. 尝试 API 生成
    3. 验收
    4. API 失败则 fallback 到 template
    5. 返回结果
    """
    spec = parse_delivery_spec(goal, platform=platform, artifact_type=artifact_type)

    # Step 1: 尝试 API 生成
    api_result = _try_api_generation(spec)

    if api_result is not None:
        api_md = api_result["markdown"]
        api_tid = api_result["task_id"]
        md_name = _PLATFORM_MD_NAMES.get(spec.platform, "copy_pack.md")
        api_check_result = _verify_and_build_result(
            goal, api_tid, "api", api_md, spec, md_filename=md_name,
        )

        if api_check_result.ok:
            return api_check_result

        api_failed = api_check_result.failed_checks
        api_reason = api_check_result.summary
    else:
        api_failed = None
        api_reason = None

    # Step 2: Template fallback
    md_content, task_id = _generate_fallback(spec)

    return _verify_and_build_result(
        goal, task_id, "template_fallback", md_content, spec,
        api_failed_checks=api_failed,
        api_rejected_reason=api_reason,
        original_mode_attempted="api" if api_result is not None else None,
    )


def run_pipeline(goal: str) -> MiniDeliveryResult:
    """旧接口兼容 — 内部调用 run_copy_pack_pipeline。"""
    return run_copy_pack_pipeline(goal, platform="xiaohongshu")


# ── 图片提示词包管线 ────────────────────────────────────────

def run_image_prompt_pack_pipeline(
    goal: str,
) -> MiniDeliveryResult:
    """
    图片提示词包生成管线。

    1. 解析 goal
    2. 生成提示词包 Markdown（template fallback）
    3. 验收
    4. 返回结果
    """
    from backend.minidelivery.spec import parse_delivery_spec

    spec = parse_delivery_spec(goal, artifact_type="image_prompt_pack")

    # 生成提示词包
    tmpl = generate_image_prompt_pack_template(spec)
    md_content = tmpl["markdown"]
    task_id = tmpl["task_id"]

    # 写入文件
    result_json = {
        "task_id": task_id,
        "task_type": "image_prompt_pack",
        "goal": goal,
        "mode": "template_fallback",
    }
    paths = write_artifact(task_id, md_content, result_json, md_filename="image_prompt_pack.md")

    # 验收
    checks, failed_checks = verify_image_prompt_pack(paths["md_path"], goal, spec)
    ok = len(failed_checks) == 0

    if ok:
        summary = "图片提示词包生成成功，所有验收检查通过。"
    else:
        summary = f"验收失败，{len(failed_checks)} 项检查未通过：{', '.join(failed_checks)}"

    final_result = MiniDeliveryResult(
        ok=ok,
        task_id=task_id,
        mode="template_fallback",
        artifact_path=paths["md_path"],
        json_path=paths["json_path"],
        checks=checks,
        failed_checks=failed_checks,
        summary=summary,
        spec=spec.model_dump(),
    )

    # 用完整结果覆盖 result.json
    with open(paths["json_path"], "w", encoding="utf-8") as f:
        f.write(json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2))

    return final_result


# ── 调研简报管线 ──────────────────────────────────────────────

def run_research_brief_pipeline(
    goal: str,
) -> MiniDeliveryResult:
    """
    调研简报生成管线（template_fallback）。

    1. 解析 goal
    2. 生成调研简报 Markdown（template fallback）
    3. 验收
    4. 返回结果
    """
    from backend.minidelivery.spec import parse_delivery_spec

    spec = parse_delivery_spec(goal, artifact_type="research_brief")

    # 生成调研简报
    tmpl = generate_research_brief_template(spec)
    md_content = tmpl["markdown"]
    task_id = tmpl["task_id"]

    # 写入文件
    result_json = {
        "task_id": task_id,
        "task_type": "research_brief",
        "goal": goal,
        "mode": "template_fallback",
    }
    paths = write_artifact(task_id, md_content, result_json, md_filename="research_brief.md")

    # 验收
    checks, failed_checks = verify_research_brief(paths["md_path"], goal, spec)
    ok = len(failed_checks) == 0

    if ok:
        summary = "调研简报生成成功，所有验收检查通过。"
    else:
        summary = f"验收失败，{len(failed_checks)} 项检查未通过：{', '.join(failed_checks)}"

    final_result = MiniDeliveryResult(
        ok=ok,
        task_id=task_id,
        mode="template_fallback",
        artifact_path=paths["md_path"],
        json_path=paths["json_path"],
        checks=checks,
        failed_checks=failed_checks,
        summary=summary,
        spec=spec.model_dump(),
    )

    # 用完整结果覆盖 result.json
    with open(paths["json_path"], "w", encoding="utf-8") as f:
        f.write(json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2))

    return final_result


# ── 落地页文案管线 ──────────────────────────────────────────────

def run_landing_page_copy_pipeline(
    goal: str,
) -> MiniDeliveryResult:
    """
    落地页文案生成管线（template_fallback）。

    1. 解析 goal
    2. 生成落地页文案 Markdown（template fallback）
    3. 验收
    4. 返回结果
    """
    from backend.minidelivery.spec import parse_delivery_spec

    spec = parse_delivery_spec(goal, artifact_type="landing_page_copy")

    # 生成落地页文案
    tmpl = generate_landing_page_copy_template(spec)
    md_content = tmpl["markdown"]
    task_id = tmpl["task_id"]

    # 写入文件
    result_json = {
        "task_id": task_id,
        "task_type": "landing_page_copy",
        "goal": goal,
        "mode": "template_fallback",
    }
    paths = write_artifact(task_id, md_content, result_json, md_filename="landing_page_copy.md")

    # 验收
    checks, failed_checks = verify_landing_page_copy(paths["md_path"], goal, spec)
    ok = len(failed_checks) == 0

    if ok:
        summary = "落地页文案生成成功，所有验收检查通过。"
    else:
        summary = f"验收失败，{len(failed_checks)} 项检查未通过：{', '.join(failed_checks)}"

    final_result = MiniDeliveryResult(
        ok=ok,
        task_id=task_id,
        mode="template_fallback",
        artifact_path=paths["md_path"],
        json_path=paths["json_path"],
        checks=checks,
        failed_checks=failed_checks,
        summary=summary,
        spec=spec.model_dump(),
    )

    # 用完整结果覆盖 result.json
    with open(paths["json_path"], "w", encoding="utf-8") as f:
        f.write(json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2))

    return final_result


# ── 数据分析报告管线 ──────────────────────────────────────────────

def run_data_report_pipeline(
    goal: str,
) -> MiniDeliveryResult:
    """
    数据分析报告生成管线（template_fallback）。

    1. 解析 goal
    2. 生成数据分析报告 Markdown（template fallback）
    3. 验收
    4. 返回结果
    """
    from backend.minidelivery.spec import parse_delivery_spec

    spec = parse_delivery_spec(goal, artifact_type="data_report")

    # 生成数据分析报告
    tmpl = generate_data_report_template(spec)
    md_content = tmpl["markdown"]
    task_id = tmpl["task_id"]

    # 写入文件
    result_json = {
        "task_id": task_id,
        "task_type": "data_report",
        "goal": goal,
        "mode": "template_fallback",
    }
    paths = write_artifact(task_id, md_content, result_json, md_filename="data_report.md")

    # 验收
    checks, failed_checks = verify_data_report(paths["md_path"], goal, spec)
    ok = len(failed_checks) == 0

    if ok:
        summary = "数据分析报告生成成功，所有验收检查通过。"
    else:
        summary = f"验收失败，{len(failed_checks)} 项检查未通过：{', '.join(failed_checks)}"

    final_result = MiniDeliveryResult(
        ok=ok,
        task_id=task_id,
        mode="template_fallback",
        artifact_path=paths["md_path"],
        json_path=paths["json_path"],
        checks=checks,
        failed_checks=failed_checks,
        summary=summary,
        spec=spec.model_dump(),
    )

    # 用完整结果覆盖 result.json
    with open(paths["json_path"], "w", encoding="utf-8") as f:
        f.write(json.dumps(final_result.model_dump(), ensure_ascii=False, indent=2))

    return final_result
