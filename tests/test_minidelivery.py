"""MiniDelivery 测试 — 覆盖成功、fallback、验收失败路径 + 多平台支持"""
import os
import sys
import json
import shutil
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from backend.minidelivery.models import XHSCopyRequest, CopyPackRequest, MiniDeliveryResult, VerificationChecks
from backend.minidelivery.spec import DeliverySpec, parse_delivery_spec
from backend.minidelivery.verifier import verify_artifact
from backend.minidelivery.artifact_writer import write_artifact, OUTPUT_ROOT
from backend.minidelivery.template_generator import (
    generate_xhs_copy_pack_template,
    generate_copy_pack_template,
    generate_image_prompt_pack_template,
    generate_research_brief_template,
    generate_landing_page_copy_template,
)
from backend.minidelivery.pipeline import run_pipeline, run_copy_pack_pipeline, run_image_prompt_pack_pipeline, run_research_brief_pipeline, run_landing_page_copy_pipeline
from backend.minidelivery.verifier import verify_image_prompt_pack, verify_research_brief, verify_landing_page_copy


# ── Fixtures ─────────────────────────────────────────────────

@pytest.fixture
def sample_goal():
    return "帮我为手工耳环生成小红书种草文案"


@pytest.fixture
def douyin_goal():
    return "生成一个抖音文案模板，用于推广手工耳环"


@pytest.fixture
def tmp_task_dir(tmp_path):
    """提供一个临时任务目录，测试后自动清理"""
    task_id = "test_xhs_001"
    task_dir = tmp_path / task_id
    task_dir.mkdir()
    yield task_dir, task_id
    if task_dir.exists():
        shutil.rmtree(task_dir)


# ── DeliverySpec 测试 ────────────────────────────────────────

class TestDeliverySpec:
    def test_parse_xiaohongshu_goal(self, sample_goal):
        """从小红书 goal 提取 platform=xiaohongshu, product=手工耳环"""
        spec = parse_delivery_spec(sample_goal)
        assert spec.platform == "xiaohongshu"
        assert "手工耳环" in spec.product

    def test_parse_douyin_goal(self, douyin_goal):
        """从抖音 goal 提取 platform=douyin, product=手工耳环"""
        spec = parse_delivery_spec(douyin_goal)
        assert spec.platform == "douyin"
        assert "手工耳环" in spec.product

    def test_explicit_platform_overrides_goal(self):
        """显式 platform 参数优先于 goal 推断"""
        goal = "帮我为手工耳环生成小红书种草文案"
        spec = parse_delivery_spec(goal, platform="douyin")
        assert spec.platform == "douyin"

    def test_douyin_keyword_in_goal(self):
        """goal 包含 '短视频' 应识别为 douyin"""
        spec = parse_delivery_spec("帮我为手工耳环生成短视频推广文案")
        assert spec.platform == "douyin"

    def test_product_fallback(self):
        """无法识别 product 时使用 fallback"""
        spec = parse_delivery_spec("请帮我生成一份推广文案")
        assert len(spec.product) >= 2

    def test_requirements_extraction(self):
        spec = parse_delivery_spec("帮我生成包含开头钩子和卖点的文案")
        assert "hook" in spec.requirements
        assert "selling_points" in spec.requirements

    def test_spec_model_fields(self):
        spec = DeliverySpec(
            platform="douyin", product="手工耳环",
            artifact_type="copy_pack", requirements=["hook"],
            original_goal="test",
        )
        d = spec.model_dump()
        assert d["platform"] == "douyin"
        assert d["product"] == "手工耳环"


# ── 模板生成器测试 ──────────────────────────────────────────

class TestTemplateGenerator:
    def test_generates_valid_markdown(self, sample_goal):
        result = generate_xhs_copy_pack_template(sample_goal)

        assert "markdown" in result
        assert "task_id" in result
        assert result["task_id"].startswith("xhs_")
        assert len(result["markdown"]) > 500

    def test_markdown_contains_required_sections(self, sample_goal):
        md = generate_xhs_copy_pack_template(sample_goal)["markdown"]

        assert "标题" in md
        assert "人群" in md
        assert "文案" in md or "正文" in md
        assert "#" in md
        assert "行动" in md or "CTA" in md
        assert "发布" in md

    def test_has_at_least_3_titles(self, sample_goal):
        md = generate_xhs_copy_pack_template(sample_goal)["markdown"]
        import re
        titles = re.findall(r"(?:^#{1,3}\s+.+|^\*\*.+\*\*$)", md, re.MULTILINE)
        assert len(titles) >= 3

    def test_has_at_least_5_hashtags(self, sample_goal):
        md = generate_xhs_copy_pack_template(sample_goal)["markdown"]
        import re
        hashtags = re.findall(r"#\S+", md)
        assert len(hashtags) >= 5

    def test_body_has_enough_chinese_chars(self, sample_goal):
        md = generate_xhs_copy_pack_template(sample_goal)["markdown"]
        import re
        chinese = re.findall(r"[一-鿿]", md)
        assert len(chinese) >= 120

    def test_xhs_template_contains_product(self):
        """小红书模板必须包含实际产品名，不允许占位符"""
        spec = parse_delivery_spec("帮我为手工耳环生成小红书文案", platform="xiaohongshu")
        result = generate_copy_pack_template(spec)
        assert "手工耳环" in result["markdown"]
        assert "{{产品}}" not in result["markdown"]

    def test_douyin_template_structure(self, douyin_goal):
        """抖音模板必须包含：开头钩子、分镜/脚本、卖点、场景、互动、行动号召"""
        spec = parse_delivery_spec(douyin_goal)
        result = generate_copy_pack_template(spec)
        md = result["markdown"]

        assert "手工耳环" in md
        assert "钩子" in md
        assert "分镜" in md or "脚本" in md
        assert "卖点" in md
        assert "场景" in md
        assert "互动" in md
        assert "行动" in md or "CTA" in md
        assert "发布" in md

    def test_douyin_template_no_placeholder(self, douyin_goal):
        """抖音模板不允许占位符"""
        spec = parse_delivery_spec(douyin_goal)
        result = generate_copy_pack_template(spec)
        assert "{{产品}}" not in result["markdown"]
        assert "{product}" not in result["markdown"]


# ── 产物写入器测试 ──────────────────────────────────────────

class TestArtifactWriter:
    def test_writes_files(self, tmp_path):
        task_id = "test_write_001"
        md_content = "# 测试\n\n这是一个测试文件。"
        result_json = {"task_id": task_id, "mode": "test"}

        with patch("backend.minidelivery.artifact_writer.OUTPUT_ROOT", tmp_path):
            paths = write_artifact(task_id, md_content, result_json)

        assert os.path.exists(paths["md_path"])
        assert os.path.exists(paths["json_path"])

        with open(paths["md_path"], "r", encoding="utf-8") as f:
            assert f.read() == md_content

        with open(paths["json_path"], "r", encoding="utf-8") as f:
            data = json.load(f)
            assert data["task_id"] == task_id

    def test_creates_nested_directory(self, tmp_path):
        task_id = "nested/deep/task"
        with patch("backend.minidelivery.artifact_writer.OUTPUT_ROOT", tmp_path):
            paths = write_artifact(task_id, "content", {})
        assert os.path.exists(paths["md_path"])

    def test_custom_md_filename(self, tmp_path):
        """支持自定义 md 文件名"""
        with patch("backend.minidelivery.artifact_writer.OUTPUT_ROOT", tmp_path):
            paths = write_artifact("t1", "content", {}, md_filename="copy_pack.md")
        assert "copy_pack.md" in paths["md_path"]
        assert os.path.exists(paths["md_path"])


# ── 验收器测试 ──────────────────────────────────────────────

class TestVerifier:
    def test_template_passes_verification(self, sample_goal, tmp_path):
        tmpl = generate_xhs_copy_pack_template(sample_goal)
        md_path = str(tmp_path / "xiaohongshu_pack.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(tmpl["markdown"])

        checks, failed = verify_artifact(md_path, sample_goal)

        assert checks.file_exists is True
        assert checks.file_size_ok is True
        assert checks.has_titles is True
        assert checks.has_target_audience is True
        assert checks.has_body_text is True
        assert checks.has_hashtags is True
        assert checks.has_cta is True
        assert checks.has_publish_tips is True
        assert checks.contains_goal_keyword is True
        assert checks.no_placeholders is True
        assert checks.title_count_ok is True
        assert checks.hashtag_count_ok is True
        assert checks.body_length_ok is True
        assert len(failed) == 0

    def test_missing_file_fails(self, tmp_path):
        fake_path = str(tmp_path / "nonexistent.md")
        checks, failed = verify_artifact(fake_path, "test")

        assert checks.file_exists is False
        assert "file_not_found" in failed

    def test_short_content_fails(self, tmp_path):
        md_path = str(tmp_path / "short.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write("# 短\n\n太短了")

        checks, failed = verify_artifact(md_path, "test")

        assert checks.file_size_ok is False
        assert checks.body_length_ok is False

    def test_placeholder_fails(self, sample_goal, tmp_path):
        """包含未替换占位符时验收必须失败"""
        spec = parse_delivery_spec(sample_goal)
        content = (
            "# 小红书文案包\n\n## 标题方案\n\n### 标题1\n{{产品}}推荐\n\n"
            "### 标题2\n{{产品}}种草\n\n### 标题3\n必买清单\n\n"
            "## 目标人群\n\n年轻女性\n\n## 正文文案\n\n"
            + "这是一段足够长的中文内容用来测试验收是否通过的正文。" * 5
            + "\n\n## 话题标签\n\n#种草 #好物 #推荐 #分享 #必买 #品质\n\n"
            "## 行动号召\n\n快来收藏\n\n## 发布建议\n\n建议晚上发布"
        )
        md_path = str(tmp_path / "placeholder.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        checks, failed = verify_artifact(md_path, sample_goal, spec)
        assert checks.no_placeholders is False
        assert any("placeholder" in f for f in failed)

    def test_douyin_template_passes_verification(self, douyin_goal, tmp_path):
        """抖音模板产物必须通过验收"""
        spec = parse_delivery_spec(douyin_goal)
        result = generate_copy_pack_template(spec)
        md_path = str(tmp_path / "copy_pack.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(result["markdown"])

        checks, failed = verify_artifact(md_path, douyin_goal, spec)

        assert checks.file_exists is True
        assert checks.has_body_text is True
        assert checks.contains_goal_keyword is True
        assert checks.no_placeholders is True
        assert checks.has_cta is True
        assert checks.has_publish_tips is True
        assert checks.has_hook is True
        assert checks.has_script is True
        assert checks.has_selling_points is True
        assert checks.has_use_scenarios is True
        assert checks.has_engagement is True
        assert len(failed) == 0

    def test_douyin_missing_hook_fails(self, douyin_goal, tmp_path):
        """抖音产物缺少钩子必须失败"""
        spec = parse_delivery_spec(douyin_goal)
        content = (
            "# 抖音文案\n\n## 视频脚本\n\n### 分镜1\n画面+口播\n\n"
            "## 卖点介绍\n产品很好\n\n## 使用场景\n日常使用\n\n"
            "## 互动引导\n评论互动\n\n## 行动号召\n立即购买\n\n## 发布建议\n晚上发布\n\n"
            + "这是一段足够长的中文内容。" * 10
        )
        md_path = str(tmp_path / "no_hook.md")
        with open(md_path, "w", encoding="utf-8") as f:
            f.write(content)

        checks, failed = verify_artifact(md_path, douyin_goal, spec)
        assert checks.has_hook is False
        assert any("hook" in f for f in failed)


# ── Pipeline 测试（fallback 路径） ─────────────────────────

class TestPipeline:
    def test_fallback_generates_valid_output(self, sample_goal):
        """API 不可用时，fallback 应该生成有效产物"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        assert isinstance(result, MiniDeliveryResult)
        assert result.mode == "template_fallback"
        assert os.path.exists(result.artifact_path)
        assert os.path.exists(result.json_path)
        assert result.ok is True
        assert len(result.failed_checks) == 0

    def test_api_path_when_available(self, sample_goal):
        """Mock API 可用时，应走 API 路径"""
        fake_md = "# 小红书文案包\n\n## 标题方案\n\n### 标题1\n手工耳环好物推荐\n\n### 标题2\n手工耳环种草分享\n\n### 标题3\n手工耳环必买清单\n\n## 目标人群\n\n年轻女性，热爱生活\n\n## 正文文案\n\n" + "这是一段关于手工耳环的中文内容用来测试验收是否通过。" * 10 + "\n\n## 话题标签\n\n#手工耳环 #种草 #好物 #推荐 #分享 #必买 #品质 #生活\n\n## 行动号召\n\n快来收藏关注吧！立即下单体验\n\n## 发布建议\n\n建议发布时间：晚上8点"
        mock_result = {
            "markdown": fake_md,
            "task_id": "xhs_api_mock",
        }

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=mock_result):
            result = run_pipeline(sample_goal)

        assert result.mode == "api"
        assert result.ok is True

    def test_result_json_is_valid(self, sample_goal):
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["task_id"] == result.task_id
        assert data["mode"] == "template_fallback"
        assert data["ok"] == result.ok
        assert isinstance(data["checks"], dict)
        assert isinstance(data["failed_checks"], list)
        assert "summary" in data

    def test_artifact_is_real_file_not_just_text(self, sample_goal):
        """确保产物是真实文件，不是仅仅返回文本"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        assert os.path.isfile(result.artifact_path)
        size = os.path.getsize(result.artifact_path)
        assert size > 300

    def test_api_offtopic_fallback_to_template(self, sample_goal):
        """API 返回跑题内容（标题不够）时必须 fallback 到 template"""
        offtopic_md = (
            "标题方案\n"
            "标题 1：智能投影仪推荐\n\n"
            "目标人群是年轻用户，热爱科技产品。\n\n"
            "正文内容：这是一段关于投影仪的无关内容，用来模拟 API 跑题的情况。"
            "需要足够多的中文字符来通过正文长度验收检查。"
            "投影仪是一种非常实用的家庭影院设备，可以投射出大画面。"
            "智能投影仪集成了操作系统，可以安装各种应用。\n\n"
            "#投影仪 #好物 #推荐 #种草 #分享 #生活\n\n"
            "行动号召：立即购买体验\n\n"
            "发布建议：建议晚上发布"
        )
        api_result = {"markdown": offtopic_md, "task_id": "xhs_offtopic"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_pipeline(sample_goal)

        assert result.mode == "template_fallback"
        assert result.ok is True
        assert result.original_mode_attempted == "api"
        assert result.api_rejected_reason is not None

    def test_api_bad_titles_fallback(self, sample_goal):
        """API 返回标题格式不合格（少于 3 个）时必须 fallback"""
        bad_titles_md = (
            "标题方案\n"
            "标题 1：唯一标题\n\n"
            "目标人群：女性用户，热爱生活。\n\n"
            "正文内容：正文内容足够长用于验收通过的中文文案内容。"
            "这是一段很长的正文，用来确保中文字符数量达标。"
            "小红书文案需要真实感，不能太营销化。"
            "种草文案的核心是真实体验分享。\n\n"
            "#种草 #好物 #推荐 #分享 #必买 #品质\n\n"
            "行动号召：快来收藏\n\n"
            "发布建议：建议晚上发布"
        )
        api_result = {"markdown": bad_titles_md, "task_id": "xhs_bad_titles"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_pipeline(sample_goal)

        assert result.mode == "template_fallback"
        assert result.ok is True
        assert result.original_mode_attempted == "api"

    def test_api_structured_offtopic_fallback(self, sample_goal):
        """API 结构合格但品类跑偏时，也必须 fallback"""
        structured_offtopic_md = (
            "# 小红书文案包\n\n"
            "## 标题方案\n\n"
            "### 标题1\n氨基酸洗护套装推荐\n\n"
            "### 标题2\n洗发水种草分享\n\n"
            "### 标题3\n控油蓬松必买清单\n\n"
            "## 目标人群\n\n年轻女性，热爱生活，关注头发护理。\n\n"
            "## 正文文案\n\n"
            + "这是一段关于洗护产品的中文内容，用来测试 API 结构合格但品类跑偏的情况。"
            * 10
            + "\n\n## 话题标签\n\n#洗护 #控油 #蓬松 #好物 #推荐 #种草\n\n"
            "## 行动号召\n\n快来收藏关注吧！立即下单体验\n\n"
            "## 发布建议\n\n建议发布时间：晚上8点"
        )
        api_result = {"markdown": structured_offtopic_md, "task_id": "xhs_structured_offtopic"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_pipeline(sample_goal)

        assert result.mode == "template_fallback"
        assert result.ok is True
        assert result.original_mode_attempted == "api"
        assert result.api_failed_checks is not None

    def test_fallback_ok_true_after_api_failure(self, sample_goal):
        """API 失败后 fallback 产物必须 ok=true"""
        offtopic_md = "短内容，没有标题格式"
        api_result = {"markdown": offtopic_md, "task_id": "xhs_fail"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_pipeline(sample_goal)

        assert result.ok is True
        assert result.mode == "template_fallback"

    def test_artifact_contains_goal_keyword(self, sample_goal):
        """产物内容必须包含用户 goal 中的核心词"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "手工耳环" in content, "产物未包含 goal 核心词 '手工耳环'"


# ── 通用文案包管线测试 ──────────────────────────────────────

class TestCopyPackPipeline:
    def test_xiaohongshu_fallback(self, sample_goal):
        """小红书 fallback 产物通过验收"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_copy_pack_pipeline(sample_goal, platform="xiaohongshu")

        assert result.ok is True
        assert result.spec["platform"] == "xiaohongshu"
        assert "手工耳环" in result.spec["product"]

    def test_douyin_fallback(self, douyin_goal):
        """抖音 fallback 产物通过验收"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_copy_pack_pipeline(douyin_goal, platform="douyin")

        assert result.ok is True
        assert result.spec["platform"] == "douyin"
        assert "手工耳环" in result.spec["product"]

    def test_douyin_artifact_has_required_sections(self, douyin_goal):
        """抖音产物包含：开头钩子、分镜/脚本、卖点、场景、互动、行动号召"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_copy_pack_pipeline(douyin_goal, platform="douyin")

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "钩子" in content
        assert "分镜" in content or "脚本" in content
        assert "卖点" in content
        assert "场景" in content
        assert "互动" in content
        assert "行动" in content

    def test_api_placeholders_fallback(self, sample_goal):
        """API 返回占位符未替换时必须 fallback"""
        placeholder_md = (
            "## 标题方案\n\n### 标题1\n{{产品}}推荐\n\n### 标题2\n{{产品}}种草\n\n"
            "### 标题3\n必买清单\n\n## 目标人群\n\n年轻女性\n\n## 正文文案\n\n"
            + "这是一段足够长的中文内容用来测试验收。" * 10
            + "\n\n## 话题标签\n\n#种草 #好物 #推荐 #分享 #必买 #品质\n\n"
            "## 行动号召\n\n快来收藏\n\n## 发布建议\n\n晚上发布"
        )
        api_result = {"markdown": placeholder_md, "task_id": "xhs_ph"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_copy_pack_pipeline(sample_goal, platform="xiaohongshu")

        assert result.mode == "template_fallback"
        assert result.ok is True

    def test_result_json_contains_spec(self, sample_goal):
        """result.json 包含 spec"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_copy_pack_pipeline(sample_goal, platform="xiaohongshu")

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert "spec" in data
        assert data["spec"]["platform"] == "xiaohongshu"
        assert "手工耳环" in data["spec"]["product"]


# ── result.json 完整性测试 ──────────────────────────────────

class TestResultJson:
    REQUIRED_KEYS = {
        "ok", "task_id", "mode", "artifact_path", "json_path",
        "checks", "failed_checks", "summary",
        "api_failed_checks", "api_rejected_reason", "original_mode_attempted",
        "spec",
    }

    def test_result_json_contains_full_fields_fallback(self, sample_goal):
        """fallback 路径：result.json 必须包含完整验收结果字段"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert self.REQUIRED_KEYS.issubset(data.keys()), f"缺少字段: {self.REQUIRED_KEYS - data.keys()}"

    def test_result_json_contains_full_fields_api(self, sample_goal):
        """API 路径：result.json 必须包含完整验收结果字段"""
        fake_md = "# 小红书文案包\n\n## 标题方案\n\n### 标题1\n手工耳环好物推荐\n\n### 标题2\n手工耳环种草分享\n\n### 标题3\n手工耳环必买清单\n\n## 目标人群\n\n年轻女性，热爱生活\n\n## 正文文案\n\n" + "这是一段关于手工耳环的中文内容用来测试验收是否通过。" * 10 + "\n\n## 话题标签\n\n#手工耳环 #种草 #好物 #推荐 #分享 #必买 #品质 #生活\n\n## 行动号召\n\n快来收藏关注吧！立即下单体验\n\n## 发布建议\n\n建议发布时间：晚上8点"
        with patch("backend.minidelivery.pipeline._try_api_generation",
                   return_value={"markdown": fake_md, "task_id": "xhs_api_test"}):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert self.REQUIRED_KEYS.issubset(data.keys()), f"缺少字段: {self.REQUIRED_KEYS - data.keys()}"

    def test_result_json_ok_matches_pipeline_result(self, sample_goal):
        """result.json 的 ok 必须与 pipeline 返回的 ok 一致"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ok"] == result.ok

    def test_result_json_checks_is_dict(self, sample_goal):
        """result.json 的 checks 必须是字典结构"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert isinstance(data["checks"], dict)
        assert isinstance(data["failed_checks"], list)

    def test_api_fallback_diagnostic_fields_present(self, sample_goal):
        """API 跑题导致 fallback 时，result.json 必须包含诊断字段"""
        offtopic_md = (
            "标题方案\n"
            "标题 1：投影仪推荐\n\n"
            "目标人群：年轻用户。\n\n"
            "正文内容：跑题的投影仪内容，需要足够多的中文字符。"
            "投影仪是家庭影院的核心设备，智能投影仪更是如此。"
            "这是一段模拟跑题的文案内容，用来触发验收失败。\n\n"
            "#投影仪 #推荐 #好物 #种草 #分享\n\n"
            "行动号召：立即购买\n\n"
            "发布建议：晚上发布"
        )
        api_result = {"markdown": offtopic_md, "task_id": "xhs_diag"}

        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=api_result):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["original_mode_attempted"] == "api"
        assert data["api_rejected_reason"] is not None
        assert data["api_failed_checks"] is not None
        assert isinstance(data["api_failed_checks"], list)

    def test_pure_fallback_no_api_diagnostic(self, sample_goal):
        """纯 fallback（API 不可用）时，诊断字段应为 None"""
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(sample_goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["original_mode_attempted"] is None
        assert data["api_failed_checks"] is None
        assert data["api_rejected_reason"] is None


# ── Pydantic 模型测试 ──────────────────────────────────────

class TestModels:
    def test_request_validation(self):
        req = XHSCopyRequest(goal="测试目标")
        assert req.goal == "测试目标"

    def test_request_rejects_empty(self):
        with pytest.raises(Exception):
            XHSCopyRequest(goal="")

    def test_copy_pack_request(self):
        req = CopyPackRequest(goal="测试", platform="douyin")
        assert req.platform == "douyin"

    def test_copy_pack_request_optional_platform(self):
        req = CopyPackRequest(goal="测试")
        assert req.platform is None

    def test_result_model(self):
        result = MiniDeliveryResult(
            ok=True,
            task_id="test",
            mode="template_fallback",
            artifact_path="/tmp/test.md",
            json_path="/tmp/test.json",
            checks=VerificationChecks(),
            failed_checks=[],
            summary="成功",
            spec={"platform": "xiaohongshu", "product": "手工耳环"},
        )
        d = result.model_dump()
        assert d["ok"] is True
        assert "checks" in d
        assert d["spec"]["platform"] == "xiaohongshu"


# ── Smoke 测试（端到端轻量验证） ────────────────────────────

class TestSmoke:
    def test_e2e_endpoint_returns_valid_result(self):
        """直接调用 run_pipeline 并断言产物真实存在"""
        goal = "手工耳环种草文案"
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(goal)

        assert os.path.isfile(result.artifact_path), f"Markdown 文件不存在: {result.artifact_path}"
        assert os.path.isfile(result.json_path), f"JSON 文件不存在: {result.json_path}"
        assert os.path.getsize(result.artifact_path) > 300
        assert result.ok is True

    def test_smoke_result_json_readable(self):
        """result.json 必须可读且为合法 JSON"""
        goal = "耳环种草"
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_pipeline(goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ok"] is True
        assert data["task_id"] == result.task_id
        assert "checks" in data
        assert "summary" in data

    def test_smoke_douyin_e2e(self):
        """抖音端到端：产物真实存在且通过验收"""
        goal = "帮我为手工耳环生成抖音推广文案"
        with patch("backend.minidelivery.pipeline._try_api_generation", return_value=None):
            result = run_copy_pack_pipeline(goal, platform="douyin")

        assert os.path.isfile(result.artifact_path)
        assert os.path.getsize(result.artifact_path) > 300
        assert result.ok is True
        assert result.spec["platform"] == "douyin"


# ── 图片提示词包测试 ──────────────────────────────────────────

class TestImagePromptPackTemplate:
    def test_generates_valid_markdown(self):
        """生成有效的提示词包 Markdown"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)

        assert "markdown" in result
        assert "task_id" in result
        assert result["task_id"].startswith("img_")

    def test_contains_required_sections(self):
        """必须包含所有必需章节"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)
        md = result["markdown"]

        assert "主图提示词" in md
        assert "细节图提示词" in md
        assert "场景图提示词" in md
        assert "风格关键词" in md
        assert "负面提示词" in md
        assert "尺寸" in md
        assert "使用建议" in md

    def test_contains_product(self):
        """必须包含产品名"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)
        assert "手工耳环" in result["markdown"]

    def test_no_placeholders(self):
        """不允许包含占位符"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)
        md = result["markdown"]

        assert "{{产品}}" not in md
        assert "{product}" not in md
        assert "{{品类}}" not in md

    def test_has_negative_prompts(self):
        """必须包含负面提示词"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)
        assert "negative" in result["markdown"].lower() or "负面提示词" in result["markdown"]

    def test_markdown_length(self):
        """Markdown 长度足够"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)
        assert len(result["markdown"]) > 500


class TestImagePromptPackVerifier:
    def test_verifier_passes(self):
        """验收器对有效产物通过"""
        spec = parse_delivery_spec("帮我为手工耳环生成产品图提示词", artifact_type="image_prompt_pack")
        result = generate_image_prompt_pack_template(spec)

        # 写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(result["markdown"])
            tmp_path = f.name

        try:
            checks, failed = verify_image_prompt_pack(tmp_path, "帮我为手工耳环生成产品图提示词", spec)
            assert len(failed) == 0, f"Unexpected failures: {failed}"
            assert checks.file_exists is True
            assert checks.contains_goal_keyword is True
            assert checks.no_placeholders is True
            assert checks.has_main_prompt is True
            assert checks.has_detail_prompt is True
            assert checks.has_scene_prompt is True
            assert checks.has_negative_prompt is True
            assert checks.has_usage_tips is True
        finally:
            os.unlink(tmp_path)

    def test_verifier_fails_missing_file(self):
        """验收器对不存在的文件失败"""
        checks, failed = verify_image_prompt_pack("/tmp/nonexistent.md", "test")
        assert checks.file_exists is False
        assert "file_not_found" in failed

    def test_verifier_fails_short_content(self):
        """验收器对过短内容失败"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("短内容")
            tmp_path = f.name

        try:
            checks, failed = verify_image_prompt_pack(tmp_path, "test")
            assert checks.file_size_ok is False
        finally:
            os.unlink(tmp_path)


class TestImagePromptPackPipeline:
    def test_pipeline_e2e(self):
        """端到端管线测试"""
        goal = "帮我为手工耳环生成产品图提示词"
        result = run_image_prompt_pack_pipeline(goal)

        assert os.path.isfile(result.artifact_path), f"文件不存在: {result.artifact_path}"
        assert os.path.isfile(result.json_path), f"JSON 不存在: {result.json_path}"
        assert os.path.getsize(result.artifact_path) > 300
        assert result.ok is True
        assert result.task_id.startswith("img_")
        assert result.mode == "template_fallback"
        assert "手工耳环" in result.summary or result.ok

    def test_pipeline_result_json(self):
        """result.json 必须合法且包含必要字段"""
        goal = "帮我为手工耳环生成产品图提示词"
        result = run_image_prompt_pack_pipeline(goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ok"] is True
        assert data["task_id"] == result.task_id
        assert "checks" in data
        assert "summary" in data
        assert "spec" in data

    def test_pipeline_no_placeholders(self):
        """产物不允许包含占位符"""
        goal = "帮我为手工耳环生成产品图提示词"
        result = run_image_prompt_pack_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "{{产品}}" not in content
        assert "{product}" not in content

    def test_pipeline_contains_product(self):
        """产物必须包含产品名"""
        goal = "帮我为手工耳环生成产品图提示词"
        result = run_image_prompt_pack_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "手工耳环" in content

    def test_pipeline_all_sections(self):
        """产物必须包含所有必需章节"""
        goal = "帮我为手工耳环生成产品图提示词"
        result = run_image_prompt_pack_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "主图提示词" in content
        assert "细节图提示词" in content
        assert "场景图提示词" in content
        assert "负面提示词" in content
        assert "使用建议" in content


# ── 调研简报测试 ──────────────────────────────────────────────

class TestResearchBriefTemplate:
    def test_generates_valid_markdown(self):
        """生成有效的调研简报 Markdown"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)

        assert "markdown" in result
        assert "task_id" in result
        assert result["task_id"].startswith("rb_")

    def test_contains_required_sections(self):
        """必须包含所有必需章节"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)
        md = result["markdown"]

        assert "调研目标" in md
        assert "目标用户" in md
        assert "竞品维度" in md
        assert "痛点" in md
        assert "内容机会" in md
        assert "风险" in md
        assert "下一步" in md

    def test_contains_product(self):
        """必须包含产品名"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)
        assert "手工耳环" in result["markdown"]

    def test_no_placeholders(self):
        """不允许包含占位符"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)
        md = result["markdown"]

        assert "{{产品}}" not in md
        assert "{product}" not in md
        assert "{{品类}}" not in md

    def test_markdown_length(self):
        """Markdown 长度足够"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)
        assert len(result["markdown"]) > 500


class TestResearchBriefVerifier:
    def test_verifier_passes(self):
        """验收器对有效产物通过"""
        spec = parse_delivery_spec("帮我为手工耳环做一份竞品调研简报", artifact_type="research_brief")
        result = generate_research_brief_template(spec)

        # 写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(result["markdown"])
            tmp_path = f.name

        try:
            checks, failed = verify_research_brief(tmp_path, "帮我为手工耳环做一份竞品调研简报", spec)
            assert len(failed) == 0, f"Unexpected failures: {failed}"
            assert checks.file_exists is True
            assert checks.contains_goal_keyword is True
            assert checks.no_placeholders is True
            assert checks.has_research_goal is True
            assert checks.has_target_users is True
            assert checks.has_competitor_dimensions is True
            assert checks.has_pain_points is True
            assert checks.has_content_opportunities is True
            assert checks.has_risk_warnings is True
            assert checks.has_next_steps is True
        finally:
            os.unlink(tmp_path)

    def test_verifier_fails_missing_file(self):
        """验收器对不存在的文件失败"""
        checks, failed = verify_research_brief("/tmp/nonexistent.md", "test")
        assert checks.file_exists is False
        assert "file_not_found" in failed

    def test_verifier_fails_short_content(self):
        """验收器对过短内容失败"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("短内容")
            tmp_path = f.name

        try:
            checks, failed = verify_research_brief(tmp_path, "test")
            assert checks.file_size_ok is False
        finally:
            os.unlink(tmp_path)


class TestResearchBriefPipeline:
    def test_pipeline_e2e(self):
        """端到端管线测试"""
        goal = "帮我为手工耳环做一份竞品调研简报"
        result = run_research_brief_pipeline(goal)

        assert os.path.isfile(result.artifact_path), f"文件不存在: {result.artifact_path}"
        assert os.path.isfile(result.json_path), f"JSON 不存在: {result.json_path}"
        assert os.path.getsize(result.artifact_path) > 300
        assert result.ok is True
        assert result.task_id.startswith("rb_")
        assert result.mode == "template_fallback"
        assert "手工耳环" in result.summary or result.ok

    def test_pipeline_result_json(self):
        """result.json 必须合法且包含必要字段"""
        goal = "帮我为手工耳环做一份竞品调研简报"
        result = run_research_brief_pipeline(goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ok"] is True
        assert data["task_id"] == result.task_id
        assert "checks" in data
        assert "summary" in data
        assert "spec" in data

    def test_pipeline_no_placeholders(self):
        """产物不允许包含占位符"""
        goal = "帮我为手工耳环做一份竞品调研简报"
        result = run_research_brief_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "{{产品}}" not in content
        assert "{product}" not in content

    def test_pipeline_contains_product(self):
        """产物必须包含产品名"""
        goal = "帮我为手工耳环做一份竞品调研简报"
        result = run_research_brief_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "手工耳环" in content

    def test_pipeline_all_sections(self):
        """产物必须包含所有必需章节"""
        goal = "帮我为手工耳环做一份竞品调研简报"
        result = run_research_brief_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "调研目标" in content
        assert "目标用户" in content
        assert "竞品" in content
        assert "痛点" in content
        assert "内容机会" in content
        assert "风险" in content
        assert "下一步" in content


# ── 落地页文案测试 ──────────────────────────────────────────────

class TestLandingPageCopyTemplate:
    def test_generates_valid_markdown(self):
        """生成有效的落地页文案 Markdown"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)

        assert "markdown" in result
        assert "task_id" in result
        assert result["task_id"].startswith("lp_")

    def test_contains_required_sections(self):
        """必须包含所有必需章节"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)
        md = result["markdown"]

        assert "页面定位" in md
        assert "首屏标题" in md
        assert "副标题" in md
        assert "核心卖点" in md
        assert "目标用户" in md
        assert "页面结构" in md
        assert "CTA" in md
        assert "FAQ" in md
        assert "视觉建议" in md

    def test_contains_product(self):
        """必须包含产品名"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)
        assert "手工耳环" in result["markdown"]

    def test_no_placeholders(self):
        """不允许包含占位符"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)
        md = result["markdown"]

        assert "{{产品}}" not in md
        assert "{product}" not in md
        assert "{{品类}}" not in md

    def test_markdown_length(self):
        """Markdown 长度足够"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)
        assert len(result["markdown"]) > 500


class TestLandingPageCopyVerifier:
    def test_verifier_passes(self):
        """验收器对有效产物通过"""
        spec = parse_delivery_spec("帮我为手工耳环生成一个落地页文案", artifact_type="landing_page_copy")
        result = generate_landing_page_copy_template(spec)

        # 写入临时文件
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write(result["markdown"])
            tmp_path = f.name

        try:
            checks, failed = verify_landing_page_copy(tmp_path, "帮我为手工耳环生成一个落地页文案", spec)
            assert len(failed) == 0, f"Unexpected failures: {failed}"
            assert checks.file_exists is True
            assert checks.contains_goal_keyword is True
            assert checks.no_placeholders is True
            assert checks.has_page_positioning is True
            assert checks.has_hero_title is True
            assert checks.has_subtitle is True
            assert checks.has_selling_points is True
            assert checks.has_target_users is True
            assert checks.has_page_structure is True
            assert checks.has_cta is True
            assert checks.has_faq is True
            assert checks.has_visual_suggestions is True
        finally:
            os.unlink(tmp_path)

    def test_verifier_fails_missing_file(self):
        """验收器对不存在的文件失败"""
        checks, failed = verify_landing_page_copy("/tmp/nonexistent.md", "test")
        assert checks.file_exists is False
        assert "file_not_found" in failed

    def test_verifier_fails_short_content(self):
        """验收器对过短内容失败"""
        import tempfile
        with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False, encoding="utf-8") as f:
            f.write("短内容")
            tmp_path = f.name

        try:
            checks, failed = verify_landing_page_copy(tmp_path, "test")
            assert checks.file_size_ok is False
        finally:
            os.unlink(tmp_path)


class TestLandingPageCopyPipeline:
    def test_pipeline_e2e(self):
        """端到端管线测试"""
        goal = "帮我为手工耳环生成一个落地页文案"
        result = run_landing_page_copy_pipeline(goal)

        assert os.path.isfile(result.artifact_path), f"文件不存在: {result.artifact_path}"
        assert os.path.isfile(result.json_path), f"JSON 不存在: {result.json_path}"
        assert os.path.getsize(result.artifact_path) > 300
        assert result.ok is True
        assert result.task_id.startswith("lp_")
        assert result.mode == "template_fallback"
        assert "手工耳环" in result.summary or result.ok

    def test_pipeline_result_json(self):
        """result.json 必须合法且包含必要字段"""
        goal = "帮我为手工耳环生成一个落地页文案"
        result = run_landing_page_copy_pipeline(goal)

        with open(result.json_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        assert data["ok"] is True
        assert data["task_id"] == result.task_id
        assert "checks" in data
        assert "summary" in data
        assert "spec" in data

    def test_pipeline_no_placeholders(self):
        """产物不允许包含占位符"""
        goal = "帮我为手工耳环生成一个落地页文案"
        result = run_landing_page_copy_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "{{产品}}" not in content
        assert "{product}" not in content

    def test_pipeline_contains_product(self):
        """产物必须包含产品名"""
        goal = "帮我为手工耳环生成一个落地页文案"
        result = run_landing_page_copy_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "手工耳环" in content

    def test_pipeline_all_sections(self):
        """产物必须包含所有必需章节"""
        goal = "帮我为手工耳环生成一个落地页文案"
        result = run_landing_page_copy_pipeline(goal)

        with open(result.artifact_path, "r", encoding="utf-8") as f:
            content = f.read()

        assert "页面定位" in content
        assert "首屏标题" in content
        assert "核心卖点" in content
        assert "目标用户" in content
        assert "页面结构" in content
        assert "CTA" in content
        assert "FAQ" in content
        assert "视觉建议" in content


# ═══════════════════════════════════════════════════════════════
# Phase 1A: save-from-agent 单元测试
# ═══════════════════════════════════════════════════════════════

from fastapi.testclient import TestClient
from backend.app import app
from backend.routers.minidelivery_router import (
    _render_marketing, _render_image, _render_data,
    _render_research, _render_website, _render_generic,
)

client = TestClient(app)


class TestSaveFromAgent:
    """POST /minidelivery/save-from-agent 测试"""

    # ── 辅助 ──────────────────────────────────────────────────

    @staticmethod
    def _make_result(agent_id="marketing", ok=True):
        """构造最小 AgentRunResult"""
        return {
            "ok": ok,
            "mode": "single_agent",
            "agent_id": agent_id,
            "task_type": "copywriting",
            "summary": "生成完成",
            "structured_output": {
                "headline": "手工耳环推荐",
                "body": "这是一段正文内容，描述手工耳环的精美工艺。",
                "cta": "立即购买",
                "hashtags": ["手工", "耳环", "饰品"],
                "keywords": ["手工耳环", "饰品推荐"],
            },
            "output": {},
            "artifacts": [],
            "warnings": [],
            "errors": [],
            "metadata": {"task_id": "test_001"},
        }

    # ── 渲染函数单元测试 ────────────────────────────────────

    def test_render_marketing(self):
        result = self._make_result("marketing")
        md = _render_marketing(result, "手工耳环推广")
        assert "手工耳环推广" in md
        assert "手工耳环推荐" in md
        assert "立即购买" in md
        assert "#手工" in md

    def test_render_image(self):
        result = self._make_result("image")
        result["structured_output"] = {
            "main_prompt": "a beautiful earring",
            "negative_prompt": "blurry",
        }
        md = _render_image(result, "生成耳环图")
        assert "生成耳环图" in md
        assert "a beautiful earring" in md

    def test_render_data(self):
        result = self._make_result("data")
        result["structured_output"] = {
            "analysis_goal": "销售趋势",
            "core_metrics": "转化率 5%",
        }
        md = _render_data(result, "数据分析")
        assert "数据分析" in md
        assert "销售趋势" in md

    def test_render_research(self):
        result = self._make_result("research")
        result["structured_output"] = {
            "research_goal": "竞品分析",
            "target_users": "年轻女性",
        }
        md = _render_research(result, "市场调研")
        assert "市场调研" in md
        assert "竞品分析" in md

    def test_render_research_with_sources(self):
        """research 渲染应展示 sources 信息来源"""
        result = self._make_result("research")
        result["structured_output"] = {
            "research_question": "手工耳环市场分析",
            "market_summary": "市场规模约 50 亿",
            "key_findings": ["发现1", "发现2"],
            "competitors": [],
            "opportunities": ["机会1"],
            "risks": ["风险1"],
            "recommended_actions": ["建议1"],
            "limitations": ["框架型调研"],
            "sources": [
                "2025 手工饰品市场报告 — https://example.com/report1",
                "竞品分析数据 — https://example.com/report2",
            ],
        }
        md = _render_research(result, "手工耳环市场调研")
        assert "信息来源" in md
        assert "2025 手工饰品市场报告" in md
        assert "https://example.com/report1" in md
        assert "竞品分析数据" in md
        assert "https://example.com/report2" in md

    def test_render_research_sources_empty(self):
        """sources 为空时不展示信息来源章节"""
        result = self._make_result("research")
        result["structured_output"] = {
            "research_question": "测试",
            "market_summary": "概况",
            "key_findings": [],
            "competitors": [],
            "opportunities": [],
            "risks": [],
            "recommended_actions": [],
            "limitations": [],
            "sources": [],
        }
        md = _render_research(result, "测试调研")
        assert "信息来源" not in md

    def test_render_website(self):
        result = self._make_result("website")
        result["structured_output"] = {
            "hero_title": "手工耳环商城",
            "page_positioning": "品牌官网",
        }
        md = _render_website(result, "落地页设计")
        assert "落地页设计" in md
        assert "手工耳环商城" in md

    def test_render_generic_unknown_agent(self):
        result = self._make_result("unknown_agent")
        md = _render_generic(result, "通用测试")
        assert "通用测试" in md
        assert "unknown_agent" in md

    def test_render_preserves_warnings(self):
        result = self._make_result()
        result["warnings"] = ["模型响应偏慢"]
        md = _render_marketing(result, "测试 warnings")
        assert "模型响应偏慢" in md

    def test_render_preserves_errors(self):
        result = self._make_result(ok=False)
        result["errors"] = ["API 超时"]
        md = _render_marketing(result, "测试 errors")
        assert "API 超时" in md

    def test_render_preserves_metadata(self):
        result = self._make_result()
        result["metadata"] = {"duration_ms": 1200, "model": "qwen"}
        md = _render_marketing(result, "测试 metadata")
        assert "duration_ms" in md
        assert "qwen" in md

    # ── API 端到端测试 ──────────────────────────────────────

    def test_save_marketing_success(self):
        """marketing agent_result 保存成功"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "手工耳环推广",
            "agent_id": "marketing",
            "agent_result": self._make_result("marketing"),
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["agent_id"] == "marketing"
        assert data["artifact_type"] == "marketing"
        assert "task_id" in data
        assert "artifact_path" in data
        assert "result_path" in data

    def test_save_image_rendering(self):
        """image agent_result 保存成功"""
        result = self._make_result("image")
        result["structured_output"] = {"main_prompt": "a shiny earring"}
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "耳环图片",
            "agent_id": "image",
            "agent_result": result,
        })
        assert resp.status_code == 200
        assert resp.json()["artifact_type"] == "image"

    def test_save_data_rendering(self):
        """data agent_result 保存成功"""
        result = self._make_result("data")
        result["structured_output"] = {"analysis_goal": "趋势分析"}
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "数据报告",
            "agent_id": "data",
            "agent_result": result,
        })
        assert resp.status_code == 200
        assert resp.json()["artifact_type"] == "data"

    def test_save_research_rendering(self):
        """research agent_result 保存成功"""
        result = self._make_result("research")
        result["structured_output"] = {"research_goal": "竞品调研"}
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "竞品调研",
            "agent_id": "research",
            "agent_result": result,
        })
        assert resp.status_code == 200
        assert resp.json()["artifact_type"] == "research"

    def test_save_website_rendering(self):
        """website agent_result 保存成功"""
        result = self._make_result("website")
        result["structured_output"] = {"hero_title": "品牌官网"}
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "落地页",
            "agent_id": "website",
            "agent_result": result,
        })
        assert resp.status_code == 200
        assert resp.json()["artifact_type"] == "website"

    def test_save_unknown_agent_uses_generic(self):
        """未知 agent_id 使用通用保存"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "测试未知",
            "agent_id": "custom_bot",
            "agent_result": self._make_result("custom_bot"),
        })
        assert resp.status_code == 200
        assert resp.json()["artifact_type"] == "custom_bot"

    def test_save_missing_goal_returns_400(self):
        """缺少 goal 返回 422"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "agent_id": "marketing",
            "agent_result": self._make_result(),
        })
        assert resp.status_code == 422

    def test_save_missing_agent_result_returns_400(self):
        """缺少 agent_result 返回 422"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "测试",
            "agent_id": "marketing",
        })
        assert resp.status_code == 422

    def test_save_creates_output_files(self):
        """保存后 output 目录下有 result.json、artifact.md、raw_agent_result.json"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "文件验证",
            "agent_id": "marketing",
            "agent_result": self._make_result(),
        })
        task_id = resp.json()["task_id"]
        task_dir = OUTPUT_ROOT / task_id

        assert (task_dir / "result.json").exists()
        assert (task_dir / "artifact.md").exists()
        assert (task_dir / "raw_agent_result.json").exists()

        # result.json 包含完整元数据
        with open(task_dir / "result.json", "r", encoding="utf-8") as f:
            rj = json.load(f)
        assert rj["task_id"] == task_id
        assert rj["agent_id"] == "marketing"
        assert rj["goal"] == "文件验证"

        # artifact.md 是可读 Markdown
        md_content = (task_dir / "artifact.md").read_text(encoding="utf-8")
        assert "文件验证" in md_content

        # raw_agent_result.json 是原始 AgentRunResult
        with open(task_dir / "raw_agent_result.json", "r", encoding="utf-8") as f:
            raw = json.load(f)
        assert raw["ok"] is True
        assert raw["agent_id"] == "marketing"

    def test_save_with_title(self):
        """title 参数覆盖默认标题"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "自定义标题",
            "agent_id": "marketing",
            "agent_result": self._make_result(),
            "title": "我的营销方案",
        })
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        md_content = (OUTPUT_ROOT / task_id / "artifact.md").read_text(encoding="utf-8")
        assert "我的营销方案" in md_content

    def test_save_with_source_page(self):
        """source_page 字段正确保存到 result.json"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "来源页面测试",
            "agent_id": "marketing",
            "agent_result": self._make_result(),
            "source_page": "marketing",
        })
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        with open(OUTPUT_ROOT / task_id / "result.json", "r", encoding="utf-8") as f:
            rj = json.load(f)
        assert rj["source_page"] == "marketing"

    def test_save_does_not_call_pipeline(self):
        """确保 save-from-agent 不调用原 MiniDelivery 生产 pipeline"""
        with patch("backend.routers.minidelivery_router.run_pipeline") as mock_pipe, \
             patch("backend.routers.minidelivery_router.run_copy_pack_pipeline") as mock_copy:
            resp = client.post("/minidelivery/save-from-agent", json={
                "goal": "不调用 pipeline",
                "agent_id": "marketing",
                "agent_result": self._make_result(),
            })
            assert resp.status_code == 200
            mock_pipe.assert_not_called()
            mock_copy.assert_not_called()

    def test_save_result_json_mode(self):
        """result.json 的 mode 字段为 agent_save"""
        resp = client.post("/minidelivery/save-from-agent", json={
            "goal": "mode 验证",
            "agent_id": "marketing",
            "agent_result": self._make_result(),
        })
        task_id = resp.json()["task_id"]
        with open(OUTPUT_ROOT / task_id / "result.json", "r", encoding="utf-8") as f:
            rj = json.load(f)
        assert rj["mode"] == "agent_save"


# ── Phase 2A: GET /minidelivery/tasks 列表接口测试 ───────────

class TestListTasks:
    """GET /minidelivery/tasks 列表接口"""

    @staticmethod
    def _create_task(base: Path, task_id: str, goal: str, agent_id: str,
                     artifact_type: str = "", source_page: str = "",
                     created_at: str = ""):
        """在指定目录下创建模拟任务目录和 result.json"""
        task_dir = base / "minidelivery" / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "goal": goal,
            "agent_id": agent_id,
            "artifact_type": artifact_type or agent_id,
            "source_page": source_page,
            "created_at": created_at,
            "artifact_path": str(task_dir / "artifact.md"),
            "result_path": str(task_dir / "result.json"),
        }
        (task_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        (task_dir / "artifact.md").write_text(f"# {goal}", encoding="utf-8")
        return result

    def test_empty_directory(self, tmp_path):
        """空目录返回空列表"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []
        assert data["warnings"] == []

    def test_created_at_descending(self, tmp_path):
        """多条记录按 created_at 倒序"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "最早", "marketing",
                              created_at="2026-07-01T10:00:00Z")
            self._create_task(tmp_path, "t2", "中间", "image",
                              created_at="2026-07-02T10:00:00Z")
            self._create_task(tmp_path, "t3", "最新", "data",
                              created_at="2026-07-03T10:00:00Z")
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 3
        assert tasks[0]["task_id"] == "t3"
        assert tasks[1]["task_id"] == "t2"
        assert tasks[2]["task_id"] == "t1"

    def test_filter_agent_id(self, tmp_path):
        """按 agent_id 筛选"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "营销", "marketing")
            self._create_task(tmp_path, "t2", "图片", "image")
            resp = client.get("/minidelivery/tasks?agent_id=marketing")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["agent_id"] == "marketing"

    def test_filter_artifact_type(self, tmp_path):
        """按 artifact_type 筛选"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "A", "marketing", artifact_type="copywriting")
            self._create_task(tmp_path, "t2", "B", "image", artifact_type="visual_brief")
            resp = client.get("/minidelivery/tasks?artifact_type=visual_brief")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["artifact_type"] == "visual_brief"

    def test_filter_source_page(self, tmp_path):
        """按 source_page 筛选"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "A", "marketing", source_page="marketing")
            self._create_task(tmp_path, "t2", "B", "image", source_page="image")
            resp = client.get("/minidelivery/tasks?source_page=image")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["source_page"] == "image"

    def test_corrupted_json_skipped(self, tmp_path):
        """损坏的 result.json 跳过并在 warnings 中说明"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            # 正常任务
            self._create_task(tmp_path, "t1", "正常", "marketing")
            # 损坏的任务
            bad_dir = tmp_path / "minidelivery" / "t_bad"
            bad_dir.mkdir(parents=True, exist_ok=True)
            (bad_dir / "result.json").write_text("NOT VALID JSON {{{", encoding="utf-8")
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 1
        assert data["tasks"][0]["task_id"] == "t1"
        assert len(data["warnings"]) == 1
        assert "t_bad" in data["warnings"][0]

    def test_no_artifact_dir(self, tmp_path):
        """minidelivery 目录不存在时返回空列表"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        assert resp.json()["tasks"] == []

    def test_result_json_without_created_at(self, tmp_path):
        """result.json 没有 created_at 时用文件修改时间兜底"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "无时间", "marketing", created_at="")
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["created_at"] != ""  # 应该有兜底时间

    # ── Phase 3B: 分页测试 ──────────────────────────────────

    def test_pagination_default_limit(self, tmp_path):
        """默认 limit=50 生效"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(60):
                self._create_task(tmp_path, f"t{i:03d}", f"任务{i}", "marketing",
                                  created_at=f"2026-07-01T{10+i//10:02d}:{i%60:02d}:00Z")
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 50
        assert data["total"] == 60
        assert data["limit"] == 50
        assert data["offset"] == 0
        assert data["has_more"] is True

    def test_pagination_limit_max(self, tmp_path):
        """limit 最大值限制为 100"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "任务", "marketing")
            resp = client.get("/minidelivery/tasks?limit=200")
        assert resp.status_code == 422  # FastAPI validation error

    def test_pagination_offset(self, tmp_path):
        """offset 生效"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(10):
                self._create_task(tmp_path, f"t{i}", f"任务{i}", "marketing",
                                  created_at=f"2026-07-01T10:00:{i:02d}Z")
            resp = client.get("/minidelivery/tasks?offset=8")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 2
        assert data["offset"] == 8
        assert data["has_more"] is False

    def test_pagination_has_more(self, tmp_path):
        """has_more 正确"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(5):
                self._create_task(tmp_path, f"t{i}", f"任务{i}", "marketing",
                                  created_at=f"2026-07-01T10:00:{i:02d}Z")
            resp = client.get("/minidelivery/tasks?limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["tasks"]) == 3
        assert data["total"] == 5
        assert data["has_more"] is True

    def test_pagination_filter_plus_paging(self, tmp_path):
        """过滤 + 分页同时生效"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(8):
                agent = "marketing" if i % 2 == 0 else "image"
                self._create_task(tmp_path, f"t{i}", f"任务{i}", agent,
                                  created_at=f"2026-07-01T10:00:{i:02d}Z")
            resp = client.get("/minidelivery/tasks?agent_id=marketing&limit=3")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 4  # 4 marketing tasks
        assert len(data["tasks"]) == 3
        assert data["has_more"] is True
        assert all(t["agent_id"] == "marketing" for t in data["tasks"])

    def test_pagination_empty_offset(self, tmp_path):
        """offset 超过总数返回空列表"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(3):
                self._create_task(tmp_path, f"t{i}", f"任务{i}", "marketing",
                                  created_at=f"2026-07-01T10:00:{i:02d}Z")
            resp = client.get("/minidelivery/tasks?offset=10")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tasks"] == []
        assert data["total"] == 3
        assert data["has_more"] is False

    def test_pagination_response_structure(self, tmp_path):
        """响应包含 total/limit/offset/has_more 字段"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "limit" in data
        assert "offset" in data
        assert "has_more" in data

    # ── Phase 4A: 搜索测试 ──────────────────────────────────

    def test_search_by_goal(self, tmp_path):
        """q 搜索 goal 字段"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "手工耳环种草文案", "marketing")
            self._create_task(tmp_path, "t2", "数据分析报告", "data")
            resp = client.get("/minidelivery/tasks?q=耳环")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "t1"

    def test_search_by_task_id(self, tmp_path):
        """q 搜索 task_id 字段"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "agent_abc123def456", "目标A", "marketing")
            self._create_task(tmp_path, "agent_xyz789ghi012", "目标B", "image")
            resp = client.get("/minidelivery/tasks?q=abc123")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "agent_abc123def456"

    def test_search_by_agent_id(self, tmp_path):
        """q 搜索 agent_id 字段"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "营销文案", "marketing")
            self._create_task(tmp_path, "t2", "图片描述", "image")
            resp = client.get("/minidelivery/tasks?q=marketing")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["agent_id"] == "marketing"

    def test_search_case_insensitive(self, tmp_path):
        """q 搜索大小写不敏感"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "Hello World", "marketing")
            self._create_task(tmp_path, "t2", "其他内容", "data")
            resp = client.get("/minidelivery/tasks?q=hello")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "t1"

    def test_search_combined_with_artifact_type(self, tmp_path):
        """q + artifact_type 组合过滤"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "手工耳环文案", "marketing", artifact_type="copywriting")
            self._create_task(tmp_path, "t2", "手工耳环图片", "image", artifact_type="visual_brief")
            self._create_task(tmp_path, "t3", "数据分析", "data", artifact_type="copywriting")
            resp = client.get("/minidelivery/tasks?q=耳环&artifact_type=copywriting")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "t1"

    def test_search_with_pagination(self, tmp_path):
        """q + limit/offset 分页正确"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            for i in range(5):
                self._create_task(tmp_path, f"t{i}", f"手工耳环任务{i}", "marketing",
                                  created_at=f"2026-07-01T10:00:{i:02d}Z")
            self._create_task(tmp_path, "t_other", "其他任务", "data",
                              created_at="2026-07-01T10:01:00Z")
            resp = client.get("/minidelivery/tasks?q=耳环&limit=3&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 5
        assert len(data["tasks"]) == 3
        assert data["has_more"] is True
        assert all("耳环" in t["goal"] for t in data["tasks"])

    def test_search_no_artifact_md_read(self, tmp_path):
        """搜索不读取 artifact.md 全文也能通过测试"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            # 创建任务但不写 artifact.md
            task_dir = tmp_path / "minidelivery" / "t_no_md"
            task_dir.mkdir(parents=True, exist_ok=True)
            result = {
                "task_id": "t_no_md",
                "goal": "测试无 artifact.md 的搜索",
                "agent_id": "marketing",
                "artifact_type": "marketing",
                "source_page": "",
                "created_at": "2026-07-01T10:00:00Z",
                "artifact_path": "",
                "result_path": str(task_dir / "result.json"),
            }
            (task_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks?q=无 artifact")
        assert resp.status_code == 200
        tasks = resp.json()["tasks"]
        assert len(tasks) == 1
        assert tasks[0]["task_id"] == "t_no_md"


# ── Phase 2B: GET /minidelivery/tasks/{task_id}/download 下载接口测试 ───

class TestDownloadArtifact:
    """GET /minidelivery/tasks/{task_id}/download 下载接口"""

    @staticmethod
    def _create_task(base: Path, task_id: str, goal: str, agent_id: str,
                     artifact_type: str = "", source_page: str = "",
                     created_at: str = "", md_content: str = None):
        """在指定目录下创建模拟任务目录和 result.json"""
        task_dir = base / task_id  # OUTPUT_ROOT 已经是 minidelivery 目录
        task_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "goal": goal,
            "agent_id": agent_id,
            "artifact_type": artifact_type or agent_id,
            "source_page": source_page,
            "created_at": created_at,
            "artifact_path": str(task_dir / "artifact.md"),
            "result_path": str(task_dir / "result.json"),
        }
        (task_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        # 写入 artifact.md
        if md_content is None:
            md_content = f"# {goal}\n\n这是测试内容。"
        (task_dir / "artifact.md").write_text(md_content, encoding="utf-8")
        return result

    def test_download_success(self, tmp_path):
        """成功下载 artifact.md"""
        md_content = "# 测试文案\n\n这是一个测试文件。"
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试目标", "marketing", md_content=md_content)
            resp = client.get("/minidelivery/tasks/t1/download")
        assert resp.status_code == 200
        assert resp.headers["content-type"] == "text/markdown; charset=utf-8"
        assert resp.headers["content-disposition"] == 'attachment; filename="t1.md"'
        # Windows 换行符可能不同，只检查内容包含关键部分
        assert "测试文案" in resp.text
        assert "测试文件" in resp.text

    def test_download_task_not_found(self, tmp_path):
        """task_id 不存在返回 404"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks/nonexistent/download")
        assert resp.status_code == 404
        assert "不存在" in resp.json()["detail"]

    def test_download_artifact_missing(self, tmp_path):
        """artifact.md 不存在返回 404"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            # 创建任务目录但不创建 artifact.md
            task_dir = tmp_path / "t_no_md"
            task_dir.mkdir(parents=True, exist_ok=True)
            result = {
                "task_id": "t_no_md",
                "goal": "无产物",
                "agent_id": "marketing",
                "artifact_type": "marketing",
                "source_page": "",
                "created_at": "",
                "artifact_path": str(task_dir / "artifact.md"),
                "result_path": str(task_dir / "result.json"),
            }
            (task_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks/t_no_md/download")
        assert resp.status_code == 404
        assert "产物文件不存在" in resp.json()["detail"]

    def test_download_path_traversal_rejected(self, tmp_path):
        """路径穿越被拒绝（FastAPI 会规范化路径，返回 404）"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks/../etc/passwd/download")
        # FastAPI 会规范化路径，所以返回 404 而不是 400
        assert resp.status_code == 404

    def test_download_special_chars_rejected(self, tmp_path):
        """特殊字符 task_id 被拒绝"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks/test%20space/download")
        assert resp.status_code == 400
        assert "无效的 task_id" in resp.json()["detail"]

    def test_download_content_type(self, tmp_path):
        """Content-Type 正确"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试", "marketing")
            resp = client.get("/minidelivery/tasks/t1/download")
        assert resp.status_code == 200
        assert "text/markdown" in resp.headers["content-type"]
        assert "charset=utf-8" in resp.headers["content-type"]

    def test_download_content_disposition(self, tmp_path):
        """Content-Disposition 正确"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试", "marketing")
            resp = client.get("/minidelivery/tasks/t1/download")
        assert resp.status_code == 200
        assert "attachment" in resp.headers["content-disposition"]
        assert "t1.md" in resp.headers["content-disposition"]

    def test_download_xiaohongshu_pack_filename(self, tmp_path):
        """优先下载 xiaohongshu_pack.md"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            task_dir = tmp_path / "t1"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "xiaohongshu_pack.md").write_text("# 小红书文案", encoding="utf-8")
            (task_dir / "result.json").write_text(
                json.dumps({"task_id": "t1", "goal": "测试", "agent_id": "marketing"}), encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks/t1/download")
        assert resp.status_code == 200
        assert resp.text == "# 小红书文案"

    def test_download_copy_pack_filename(self, tmp_path):
        """优先下载 copy_pack.md"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            task_dir = tmp_path / "t1"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "copy_pack.md").write_text("# 通用文案包", encoding="utf-8")
            (task_dir / "result.json").write_text(
                json.dumps({"task_id": "t1", "goal": "测试", "agent_id": "marketing"}), encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks/t1/download")
        assert resp.status_code == 200
        assert resp.text == "# 通用文案包"

    def test_download_preserves_preview(self, tmp_path):
        """下载不影响预览功能"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试", "marketing", md_content="# 预览内容")
            # 先下载
            download_resp = client.get("/minidelivery/tasks/t1/download")
            assert download_resp.status_code == 200
            # 再预览
            preview_resp = client.get("/minidelivery/tasks/t1/artifact")
            assert preview_resp.status_code == 200
            assert preview_resp.text == "# 预览内容"


class TestGetTaskDetail:
    """GET /minidelivery/tasks/{task_id} 增强：raw_agent_result 信息"""

    @staticmethod
    def _create_task(base: Path, task_id: str, goal: str, agent_id: str,
                     has_raw: bool = False, raw_content: dict = None):
        task_dir = base / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "goal": goal,
            "agent_id": agent_id,
            "artifact_type": agent_id,
            "source_page": "",
            "created_at": "2026-07-03T10:00:00+00:00",
            "ok": True,
            "mode": "agent_save",
            "summary": "生成完成",
            "artifact_path": str(task_dir / "artifact.md"),
            "raw_agent_result_path": str(task_dir / "raw_agent_result.json"),
        }
        (task_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        (task_dir / "artifact.md").write_text("# 测试交付物", encoding="utf-8")
        if has_raw:
            raw = raw_content or {
                "ok": True,
                "summary": "营销文案生成成功",
                "structured_output": {"headline": "手工耳环"},
            }
            (task_dir / "raw_agent_result.json").write_text(
                json.dumps(raw, ensure_ascii=False), encoding="utf-8"
            )

    def test_no_raw_agent_result(self, tmp_path):
        """无 raw_agent_result 时 has_raw_agent_result=False"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试", "marketing", has_raw=False)
            resp = client.get("/minidelivery/tasks/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_raw_agent_result"] is False
        assert "agent_result_summary" not in data

    def test_has_raw_agent_result(self, tmp_path):
        """有 raw_agent_result 时 has_raw_agent_result=True"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试", "marketing", has_raw=True)
            resp = client.get("/minidelivery/tasks/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_raw_agent_result"] is True
        assert data["agent_result_summary"] == "营销文案生成成功"

    def test_raw_summary_fallback_to_structured_output(self, tmp_path):
        """raw 无 summary 时，取 structured_output 前 200 字"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            raw = {"ok": True, "structured_output": {"headline": "测试标题", "body": "正文内容"}}
            self._create_task(tmp_path, "t1", "测试", "marketing", has_raw=True, raw_content=raw)
            resp = client.get("/minidelivery/tasks/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_raw_agent_result"] is True
        assert "测试标题" in data["agent_result_summary"]

    def test_raw_corrupted_graceful(self, tmp_path):
        """raw_agent_result.json 损坏时优雅降级"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            task_dir = tmp_path / "t1"
            task_dir.mkdir(parents=True, exist_ok=True)
            result = {
                "task_id": "t1", "goal": "测试", "agent_id": "marketing",
                "artifact_type": "marketing", "source_page": "",
                "created_at": "", "ok": True, "mode": "agent_save",
                "summary": "", "artifact_path": "", "raw_agent_result_path": "",
            }
            (task_dir / "result.json").write_text(
                json.dumps(result, ensure_ascii=False), encoding="utf-8"
            )
            (task_dir / "raw_agent_result.json").write_text("NOT JSON!!!", encoding="utf-8")
            resp = client.get("/minidelivery/tasks/t1")
        assert resp.status_code == 200
        data = resp.json()
        assert data["has_raw_agent_result"] is True
        assert data["agent_result_summary"] == ""

    def test_save_from_agent_includes_created_at(self, tmp_path):
        """save-from-agent 生成的 result.json 包含 created_at"""
        with patch("backend.minidelivery.artifact_writer.OUTPUT_ROOT", tmp_path):
            resp = client.post("/minidelivery/save-from-agent", json={
                "goal": "测试时间戳",
                "agent_id": "marketing",
                "agent_result": {
                    "ok": True,
                    "mode": "single_agent",
                    "agent_id": "marketing",
                    "task_type": "copywriting",
                    "summary": "完成",
                    "structured_output": {"headline": "标题"},
                    "output": {},
                    "artifacts": [],
                    "warnings": [],
                    "errors": [],
                    "metadata": {},
                },
            })
        assert resp.status_code == 200
        task_id = resp.json()["task_id"]
        # 读取 result.json 验证 created_at
        result_path = tmp_path / task_id / "result.json"
        assert result_path.exists()
        with open(result_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert "created_at" in data
        assert data["created_at"]  # 非空


# ═══════════════════════════════════════════════════════════════
# Phase 5.1: PDF 导出测试
# ═══════════════════════════════════════════════════════════════

from backend.services.pdf_service import export_artifact_pdf, REPORTLAB_OK


class TestPdfExportFunction:
    """export_artifact_pdf 单元测试"""

    def test_generates_pdf_file(self, tmp_path):
        """生成 PDF 文件（reportlab 可用时）"""
        md = "# 测试报告\n\n## 第一章\n\n这是一段中文内容。\n\n- 要点1\n- 要点2\n\n## 第二章\n\n**粗体**和*斜体*测试。"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_001", md, title="测试报告")

        assert os.path.exists(result_path)
        if REPORTLAB_OK:
            assert result_path.endswith(".pdf")
            assert os.path.getsize(result_path) > 500
        else:
            assert result_path.endswith(".html")

    def test_auto_title_from_h1(self, tmp_path):
        """未提供 title 时从首个 H1 提取"""
        md = "# 自动标题\n\n内容"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_002", md)
        assert os.path.exists(result_path)

    def test_chinese_content(self, tmp_path):
        """中文内容正确生成"""
        md = "# 手工耳环推广方案\n\n## 目标人群\n\n年轻女性，热爱手工饰品。\n\n## 核心卖点\n\n- 纯手工制作\n- 独特设计\n- 材质安全"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_cn", md, title="手工耳环推广方案")
        assert os.path.exists(result_path)
        if REPORTLAB_OK:
            assert os.path.getsize(result_path) > 500

    def test_code_block(self, tmp_path):
        """代码块正确渲染"""
        md = "# 代码示例\n\n```python\nprint('hello')\n```\n\n普通段落。"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_code", md)
        assert os.path.exists(result_path)

    def test_table(self, tmp_path):
        """表格正确渲染"""
        md = "# 数据表\n\n| 指标 | 数值 |\n|---|---|\n| 转化率 | 5% |\n| 点击率 | 12% |"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_table", md)
        assert os.path.exists(result_path)

    def test_ordered_list(self, tmp_path):
        """有序列表正确渲染"""
        md = "# 步骤\n\n1. 第一步\n2. 第二步\n3. 第三步"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_ol", md)
        assert os.path.exists(result_path)

    def test_blockquote(self, tmp_path):
        """引用块正确渲染"""
        md = "# 引用\n\n> 这是一段引用内容\n\n普通段落。"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_bq", md)
        assert os.path.exists(result_path)

    def test_horizontal_rule(self, tmp_path):
        """分隔线正确渲染"""
        md = "# 上半部分\n\n内容1\n\n---\n\n# 下半部分\n\n内容2"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_hr", md)
        assert os.path.exists(result_path)

    def test_inline_formatting(self, tmp_path):
        """行内格式（粗体、斜体、行内代码）正确渲染"""
        md = "# 格式测试\n\n**粗体** *斜体* `代码` ***粗斜体***"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_inline", md)
        assert os.path.exists(result_path)

    def test_link_simplification(self, tmp_path):
        """链接简化为文本"""
        md = "# 链接\n\n访问 [Google](https://google.com) 搜索"
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_link", md)
        assert os.path.exists(result_path)

    def test_empty_content(self, tmp_path):
        """空内容不崩溃"""
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_empty", "")
        assert os.path.exists(result_path)

    def test_large_markdown(self, tmp_path):
        """大文件不崩溃"""
        md = "# 大文件\n\n" + "\n\n".join(
            [f"## 章节 {i}\n\n" + "这是内容。" * 50 for i in range(20)]
        )
        with patch("backend.services.pdf_service.OUTPUT_DIR", tmp_path):
            result_path = export_artifact_pdf("test_large", md)
        assert os.path.exists(result_path)
        if REPORTLAB_OK:
            assert os.path.getsize(result_path) > 2000


class TestPdfExportEndpoint:
    """GET /minidelivery/tasks/{task_id}/pdf 端点测试"""

    @staticmethod
    def _create_task(base: Path, task_id: str, goal: str, agent_id: str,
                     md_content: str = None):
        task_dir = base / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "goal": goal,
            "agent_id": agent_id,
            "artifact_type": agent_id,
            "source_page": "",
            "created_at": "2026-07-09T10:00:00+00:00",
            "ok": True,
            "mode": "agent_save",
            "summary": "生成完成",
            "artifact_path": str(task_dir / "artifact.md"),
            "result_path": str(task_dir / "result.json"),
        }
        (task_dir / "result.json").write_text(
            json.dumps(result, ensure_ascii=False), encoding="utf-8"
        )
        if md_content is None:
            md_content = f"# {goal}\n\n## 概述\n\n这是测试内容。\n\n- 要点1\n- 要点2"
        (task_dir / "artifact.md").write_text(md_content, encoding="utf-8")

    def test_pdf_success(self, tmp_path):
        """成功导出 PDF"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试报告", "marketing")
            resp = client.get("/minidelivery/tasks/t1/pdf")
        assert resp.status_code == 200
        if REPORTLAB_OK:
            assert resp.headers["content-type"] == "application/pdf"
            assert "t1.pdf" in resp.headers["content-disposition"]
        else:
            assert "text/html" in resp.headers["content-type"]

    def test_pdf_task_not_found(self, tmp_path):
        """task_id 不存在返回 404"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks/nonexistent/pdf")
        assert resp.status_code == 404

    def test_pdf_artifact_missing(self, tmp_path):
        """artifact.md 不存在返回 404"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            task_dir = tmp_path / "t_no_md"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "result.json").write_text(
                json.dumps({"task_id": "t_no_md", "goal": "测试"}), encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks/t_no_md/pdf")
        assert resp.status_code == 404

    def test_pdf_path_traversal_rejected(self, tmp_path):
        """路径穿越被拒绝"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.get("/minidelivery/tasks/test%20space/pdf")
        assert resp.status_code == 400
        assert "无效的 task_id" in resp.json()["detail"]

    def test_pdf_with_chinese_content(self, tmp_path):
        """中文内容 PDF 导出成功"""
        md = (
            "# 手工耳环推广方案\n\n"
            "## 目标人群\n\n年轻女性，热爱手工饰品。\n\n"
            "## 核心卖点\n\n"
            "- 纯手工制作，独一无二\n"
            "- 天然材质，安全无刺激\n"
            "- 精美包装，送礼首选\n\n"
            "## 推广策略\n\n"
            "1. 小红书种草笔记\n"
            "2. 抖音短视频展示\n"
            "3. 微信朋友圈分享"
        )
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t_cn", "手工耳环推广", "marketing", md_content=md)
            resp = client.get("/minidelivery/tasks/t_cn/pdf")
        assert resp.status_code == 200

    def test_pdf_xiaohongshu_pack_priority(self, tmp_path):
        """优先使用 xiaohongshu_pack.md"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            task_dir = tmp_path / "t1"
            task_dir.mkdir(parents=True, exist_ok=True)
            (task_dir / "xiaohongshu_pack.md").write_text("# 小红书文案\n\n优先使用此文件", encoding="utf-8")
            (task_dir / "artifact.md").write_text("# artifact\n\n不应使用此文件", encoding="utf-8")
            (task_dir / "result.json").write_text(
                json.dumps({"task_id": "t1", "goal": "测试优先级", "agent_id": "marketing"}),
                encoding="utf-8"
            )
            resp = client.get("/minidelivery/tasks/t1/pdf")
        assert resp.status_code == 200

    def test_pdf_does_not_break_existing_download(self, tmp_path):
        """PDF 导出不影响现有下载接口"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "t1", "测试兼容", "marketing")
            # 先调 PDF
            pdf_resp = client.get("/minidelivery/tasks/t1/pdf")
            assert pdf_resp.status_code == 200
            # 再调下载
            dl_resp = client.get("/minidelivery/tasks/t1/download")
            assert dl_resp.status_code == 200
            assert "text/markdown" in dl_resp.headers["content-type"]
            # 再调预览
            preview_resp = client.get("/minidelivery/tasks/t1/artifact")
            assert preview_resp.status_code == 200


# ── 任务对比测试 ──────────────────────────────────────────────

class TestTaskCompare:
    """POST /minidelivery/tasks/compare 测试"""

    def _create_task(self, base_dir: Path, task_id: str, goal: str, agent_id: str = "boss",
                     succeeded: int = 3, failed: int = 0, total: int = 5,
                     duration_ms: int = 10000, handoff: bool = True,
                     mode: str = "two_wave_handoff", has_raw: bool = True):
        """在 base_dir 下创建一个模拟 task 目录"""
        task_dir = base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)
        result = {
            "task_id": task_id,
            "goal": goal,
            "agent_id": agent_id,
            "artifact_type": "boss_lite",
            "source_page": "boss",
            "created_at": "2025-07-01T10:00:00+00:00",
            "ok": True,
            "mode": "boss_lite",
            "summary": f"摘要-{task_id}",
            "artifact_path": str(task_dir / "artifact.md"),
            "raw_agent_result_path": str(task_dir / "raw_agent_result.json"),
        }
        (task_dir / "result.json").write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        (task_dir / "artifact.md").write_text(f"# {goal}\n\n内容", encoding="utf-8")

        if has_raw:
            raw = {
                "succeeded": succeeded,
                "failed": failed,
                "total": total,
                "total_duration_ms": duration_ms,
                "handoff_enabled": handoff,
                "execution_mode": mode,
            }
            (task_dir / "raw_agent_result.json").write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")

    def test_compare_success(self, tmp_path):
        """两个不同 task 对比返回正确 diff"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "boss_aaa111", "目标A", succeeded=4, failed=1, duration_ms=12000)
            self._create_task(tmp_path, "boss_bbb222", "目标B", succeeded=5, failed=0, duration_ms=8000)

            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111", "boss_bbb222"]
            })
        assert resp.status_code == 200
        data = resp.json()
        assert data["ok"] is True
        assert len(data["tasks"]) == 2
        assert data["tasks"][0]["task_id"] == "boss_aaa111"
        assert data["tasks"][1]["task_id"] == "boss_bbb222"

        diff = data["diff"]
        assert diff["goal_changed"] is True
        assert diff["succeeded_diff"] == 1  # 5 - 4
        assert diff["failed_diff"] == -1  # 0 - 1
        assert diff["total_duration_ms_diff"] == -4000  # 8000 - 12000
        assert diff["handoff_changed"] is False
        assert diff["execution_mode_changed"] is False

    def test_compare_same_task_rejected(self, tmp_path):
        """同一个 task 对比被拒绝"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "boss_aaa111", "目标A")
            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111", "boss_aaa111"]
            })
        assert resp.status_code == 400
        assert "不同" in resp.json()["detail"]

    def test_compare_not_found(self, tmp_path):
        """task 不存在返回 404"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "boss_aaa111", "目标A")
            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111", "boss_nonexist"]
            })
        assert resp.status_code == 404

    def test_compare_wrong_count(self, tmp_path):
        """传 1 个或 3 个返回 400"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp1 = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111"]
            })
            resp3 = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["a", "b", "c"]
            })
        assert resp1.status_code == 400
        assert resp3.status_code == 400

    def test_compare_missing_raw_result(self, tmp_path):
        """一个 task 没有 raw_agent_result.json，对应字段为 null"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            self._create_task(tmp_path, "boss_aaa111", "目标A", has_raw=True)
            self._create_task(tmp_path, "boss_bbb222", "目标B", has_raw=False)

            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111", "boss_bbb222"]
            })
        assert resp.status_code == 200
        data = resp.json()
        # 第一个 task 有值
        assert data["tasks"][0]["succeeded"] == 3
        # 第二个 task 字段为 null
        assert data["tasks"][1]["succeeded"] is None
        assert data["tasks"][1]["total_duration_ms"] is None

    def test_compare_diff_fields(self, tmp_path):
        """验证所有 diff 字段的计算"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            # 使用相同 goal 和相同 summary（通过相同 task_id 前缀确保 summary 不影响）
            self._create_task(tmp_path, "boss_aaa111", "相同目标",
                              succeeded=3, failed=1, total=5, duration_ms=10000,
                              handoff=True, mode="two_wave_handoff")
            self._create_task(tmp_path, "boss_bbb222", "相同目标",
                              succeeded=3, failed=1, total=5, duration_ms=10000,
                              handoff=True, mode="parallel")

            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["boss_aaa111", "boss_bbb222"]
            })
        assert resp.status_code == 200
        diff = resp.json()["diff"]
        assert diff["goal_changed"] is False
        assert diff["succeeded_diff"] == 0
        assert diff["failed_diff"] == 0
        assert diff["total_duration_ms_diff"] == 0
        assert diff["handoff_changed"] is False
        assert diff["execution_mode_changed"] is True
        assert diff["artifact_type_changed"] is False
        # summary 因 task_id 不同而不同，这是预期的
        assert diff["summary_changed"] is True

    def test_compare_invalid_task_id(self, tmp_path):
        """无效 task_id 返回 400"""
        with patch("backend.routers.minidelivery_router.OUTPUT_ROOT", tmp_path):
            resp = client.post("/minidelivery/tasks/compare", json={
                "task_ids": ["../etc/passwd", "boss_bbb222"]
            })
        assert resp.status_code == 400
