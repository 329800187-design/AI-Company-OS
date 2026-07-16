"""
Image Agent — 图片提示词智能体 (LLM-first)

Phase 4.8 核心变更:
  - run(task) 执行链路: _try_llm() → _rule_fallback()
  - LLM 成功: ok(fallback=false, source=llm), structured_output 包含完整图片提示词字段
  - LLM 失败: ok(fallback=true, source=template), warnings 非空, limitations 明确
  - 接入 ImageGenerationService (可替换 provider 接口)
  - metadata 增加 image_provider
  - structured_output 可选增加 generated_images

结构化产出字段:
  image_prompt, negative_prompt, style, aspect_ratio, composition,
  lighting, color_palette, subject, background, usage_suggestions,
  variations, limitations, content_type: "image_prompt"
  generated_images: [{url, revised_prompt, size, index, is_mock}]
"""
import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

logger = logging.getLogger(__name__)

# ── LLM System Prompt ────────────────────────────────────────────

IMAGE_LLM_SYSTEM = """You are an expert image prompt engineer.
Convert user requests into detailed, structured image generation prompts.

You MUST output valid JSON with these fields:
{
  "image_prompt": "detailed prompt in English for image generation (50-200 words)",
  "negative_prompt": "things to avoid in the image",
  "style": "photorealistic|illustration|3d_render|anime|oil_painting|vector|minimalist",
  "aspect_ratio": "1:1|16:9|9:16|4:3|3:4",
  "composition": "description of visual composition and framing",
  "lighting": "lighting description (natural, studio, dramatic, etc.)",
  "color_palette": "dominant colors and mood",
  "subject": "main subject of the image",
  "background": "background description",
  "usage_suggestions": ["list of suggested use cases for this image"],
  "variations": ["2-3 alternative prompt variations"],
  "limitations": ["any limitations or caveats about this prompt"]
}

Rules:
1. Output in English (most image models work best with English)
2. image_prompt must be 50-200 words, specific and detailed
3. All fields must be present even if brief
4. Output ONLY the JSON object, no extra text"""


# ── 标准化模板字段 ──────────────────────────────────────────────

IMAGE_OUTPUT_FIELDS = {
    "image_prompt": "",
    "negative_prompt": "blurry, low quality, distorted, watermark, text, deformed",
    "style": "photorealistic",
    "aspect_ratio": "1:1",
    "composition": "centered subject with balanced framing",
    "lighting": "natural soft lighting",
    "color_palette": "warm neutral tones",
    "subject": "",
    "background": "clean simple background",
    "usage_suggestions": ["product listing", "social media post", "marketing material"],
    "variations": [],
    "limitations": ["本阶段只生成图片提示词，不生成真实图片文件"],
    "content_type": "image_prompt",
}


class ImageAgent(BaseAgent):
    """Image Agent — LLM-first 图片提示词生成 + 可选图片生成"""

    AGENT_ID = "image"
    DISPLAY_NAME = "图片生成"
    CAPABILITIES = ["image", "prompt_engineering"]
    TASK_TYPES = ["image_generate", "image_analyze"]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 90,
                 image_provider=None):
        super().__init__(name="image", timeout=timeout)
        self.api_key = api_key or ""
        self._image_provider = image_provider  # 延迟加载

    @property
    def image_provider(self):
        """延迟加载 image provider"""
        if self._image_provider is None:
            from backend.services.image_generation_service import get_image_provider
            self._image_provider = get_image_provider()
        return self._image_provider

    # ── 主入口 ──────────────────────────────────────────────────

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"img_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "image_generate")
        goal = task.get("goal", "")
        prompt = task.get("prompt", task.get("image_prompt", goal))

        if not prompt:
            return self.fail(task_id, "缺少图片生成 prompt")

        if task_type == "image_generate":
            return self._handle_generate(task, task_id, prompt)
        elif task_type == "image_analyze":
            return self._handle_analyze(task, task_id, prompt)
        else:
            return self._handle_generate(task, task_id, prompt)

    # ── 图片生成 (LLM-first) ───────────────────────────────────

    def _handle_generate(self, task: Dict, task_id: str, prompt: str) -> Dict:
        """执行链路: _try_llm() → _rule_fallback() → 可选图片生成"""
        # 第一步: 尝试 LLM 生成提示词
        llm_result = self._try_llm(task_id, prompt)
        if llm_result is not None:
            # 可选: 调用 provider 生成真实图片
            return self._maybe_generate_images(llm_result, task)

        # 第二步: 模板/规则降级
        fallback_result = self._rule_fallback(task_id, prompt)
        return self._maybe_generate_images(fallback_result, task)

    def _maybe_generate_images(self, result: Dict, task: Dict) -> Dict:
        """可选步骤: 调用 image provider 生成图片"""
        # 检查是否需要生成图片 (默认启用)
        generate_images = task.get("generate_images", True)
        if not generate_images:
            return result

        # 提取提示词
        data = result.get("data") or result.get("output") or {}
        image_prompt = data.get("image_prompt", "")
        if not image_prompt:
            return result

        # 调用 provider
        try:
            provider = self.image_provider
            provider_result = provider.generate(
                prompt=image_prompt,
                negative_prompt=data.get("negative_prompt", ""),
                size=self._aspect_to_size(data.get("aspect_ratio", "1:1")),
                style=data.get("style", "natural"),
                n=task.get("n", 1),
            )

            if provider_result.get("ok"):
                # 注入 generated_images 到 structured_output
                data["generated_images"] = provider_result["generated_images"]
                # 更新 metadata
                if "meta" not in result:
                    result["meta"] = {}
                result["meta"]["image_provider"] = provider_result["provider"]
            else:
                logger.warning(f"[Image Agent] Provider 生成失败: {provider_result.get('error')}")
                if "meta" not in result:
                    result["meta"] = {}
                result["meta"]["image_provider"] = provider_result.get("provider", "unknown")
                result["meta"]["image_provider_error"] = provider_result.get("error", "")

        except Exception as e:
            logger.error(f"[Image Agent] Provider 异常: {e}")
            if "meta" not in result:
                result["meta"] = {}
            result["meta"]["image_provider"] = "error"
            result["meta"]["image_provider_error"] = str(e)

        return result

    @staticmethod
    def _aspect_to_size(aspect_ratio: str) -> str:
        """将宽高比转换为图片尺寸"""
        ratio_map = {
            "1:1": "1024x1024",
            "16:9": "1792x1024",
            "9:16": "1024x1792",
            "4:3": "1024x768",
            "3:4": "768x1024",
        }
        return ratio_map.get(aspect_ratio, "1024x1024")

    def _try_llm(self, task_id: str, prompt: str) -> Optional[Dict]:
        """尝试通过 LLM 生成图片提示词"""
        try:
            resp = self.call_ai(
                message=f"Generate image prompt for: {prompt}",
                system=IMAGE_LLM_SYSTEM,
                temperature=0.7,
                max_tokens=2048,
            )

            if not resp.get("ok"):
                self.logger.warning(f"[Image Agent] LLM 调用失败: {resp.get('error')}")
                return None

            reply = resp.get("reply", "")
            parsed = self._extract_json(reply)

            if parsed is None:
                self.logger.warning("[Image Agent] LLM 返回无效 JSON，使用 fallback")
                return None

            # 规范化: 补齐缺失字段
            normalized = self._normalize_llm_output(parsed)

            # 构建 AgentRunResult 格式
            return self.ok(
                task_id,
                status="LLM 提示词生成完成",
                data=normalized,
                meta={
                    "fallback": False,
                    "source": "llm",
                    "model": resp.get("model", ""),
                },
            )

        except Exception as e:
            self.logger.error(f"[Image Agent] LLM 异常: {e}")
            return None

    def _rule_fallback(self, task_id: str, prompt: str) -> Dict:
        """模板/规则降级 — 本地规则生成提示词框架"""
        enhanced = self._enhance_prompt(prompt)

        output = {
            "image_prompt": enhanced.get("enhanced_prompt", prompt),
            "negative_prompt": enhanced.get("negative_prompt", IMAGE_OUTPUT_FIELDS["negative_prompt"]),
            "style": enhanced.get("style", "photorealistic"),
            "aspect_ratio": enhanced.get("aspect_ratio", "1:1"),
            "composition": "centered subject with balanced framing",
            "lighting": "natural soft lighting",
            "color_palette": "warm neutral tones",
            "subject": prompt,
            "background": "clean simple background",
            "usage_suggestions": ["product listing", "social media post"],
            "variations": [],
            "limitations": [
                "当前为模板/规则降级产物，非真实 LLM 生成",
            ],
            "content_type": "image_prompt",
        }

        warnings = [
            "当前为模板/规则降级产物，非真实 LLM 生成",
            "未配置 LLM API 或 LLM 调用失败，使用本地规则增强",
        ]

        return self.ok(
            task_id,
            status="模板降级生成完成",
            data=output,
            meta={
                "fallback": True,
                "source": "template",
                "fallback_reason": "LLM 不可用或返回无效结果",
            },
        ) | {"warnings": warnings}

    # ── 图片分析 (保持原有逻辑) ─────────────────────────────────

    def _handle_analyze(self, task: Dict, task_id: str, prompt: str) -> Dict:
        """图片分析 — 保持原有逻辑，本阶段不重点改造"""
        return self.fail(
            task_id,
            "图片分析功能需要多模态模型支持，本阶段暂不开放",
        )

    # ── 辅助方法 ────────────────────────────────────────────────

    def _normalize_llm_output(self, parsed: Dict) -> Dict:
        """规范化 LLM 输出，补齐缺失字段"""
        output = dict(IMAGE_OUTPUT_FIELDS)
        for key in IMAGE_OUTPUT_FIELDS:
            if key in parsed and parsed[key]:
                output[key] = parsed[key]
        # 确保 content_type 固定
        output["content_type"] = "image_prompt"
        return output

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
        """从 LLM 回复中提取 JSON"""
        import re
        text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            match = re.search(r"\{[\s\S]*\}", text)
            if match:
                try:
                    return json.loads(match.group())
                except json.JSONDecodeError:
                    pass
        return None

    def _enhance_prompt(self, raw_prompt: str) -> Dict:
        """本地规则增强提示词 (fallback 专用)"""
        is_chinese = any('一' <= c <= '鿿' for c in raw_prompt)
        style_keywords = {
            "真实": "photorealistic, 8K, detailed, natural lighting",
            "卡通": "cartoon style, vibrant colors, clean lines",
            "3D": "3D render, octane render, ray tracing, studio lighting",
            "插画": "digital illustration, concept art, trending on artstation",
            "极简": "minimalist, clean, simple, white background",
            "油画": "oil painting, textured, classical, masterwork",
            "动漫": "anime style, manga, studio ghibli inspired",
        }
        detected_style = "photorealistic, 8K, detailed"
        for kw, desc in style_keywords.items():
            if kw in raw_prompt:
                detected_style = desc
                break

        enhanced = raw_prompt
        if is_chinese:
            enhanced = f"{raw_prompt}, {detected_style}"

        return {
            "enhanced_prompt": enhanced,
            "negative_prompt": "blurry, low quality, distorted, watermark, text",
            "style": "photorealistic",
            "aspect_ratio": "1:1",
        }
