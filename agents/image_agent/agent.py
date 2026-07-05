"""
Image Agent — 图片提示词智能体 (LLM-first)

Phase A3 核心变更:
  - run(task) 执行链路: _try_llm() → _rule_fallback()
  - LLM 成功: ok(fallback=false, source=llm), structured_output 包含完整图片提示词字段
  - LLM 失败: ok(fallback=true, source=template), warnings 非空, limitations 明确
  - 本阶段只生成图片提示词，不生成真实图片文件
  - 不接真实图片生成 API (DALL-E / SD / Midjourney)
  - 不改 MiniDelivery / Boss / Governance / Collaboration

结构化产出字段:
  image_prompt, negative_prompt, style, aspect_ratio, composition,
  lighting, color_palette, subject, background, usage_suggestions,
  variations, limitations, content_type: "image_prompt"
"""
import json
import uuid
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent

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
    """Image Agent — LLM-first 图片提示词生成"""

    AGENT_ID = "image"
    DISPLAY_NAME = "图片生成"
    CAPABILITIES = ["image", "prompt_engineering"]
    TASK_TYPES = ["image_generate", "image_analyze"]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 90):
        super().__init__(name="image", timeout=timeout)
        self.api_key = api_key or ""

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
        """执行链路: _try_llm() → _rule_fallback()"""
        # 第一步: 尝试 LLM 生成
        llm_result = self._try_llm(task_id, prompt)
        if llm_result is not None:
            return llm_result

        # 第二步: 模板/规则降级
        return self._rule_fallback(task_id, prompt)

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
                "本阶段只生成图片提示词，不生成真实图片文件",
                "当前为模板/规则降级产物，非真实 LLM 生成",
            ],
            "content_type": "image_prompt",
        }

        warnings = [
            "当前为模板/规则降级产物，非真实 LLM 生成",
            "未配置 LLM API 或 LLM 调用失败，使用本地规则增强",
            "本阶段只生成图片提示词，不生成真实图片文件",
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
