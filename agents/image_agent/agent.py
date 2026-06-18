"""
Image Agent — 图片生成智能体

能力：
1. image_generate: AI 图片生成 (DALL-E / DeepSeek / CC-Switch)
2. image_analyze: 图片分析（多模态模型）
3. image_edit: 图片编辑/变体

支持 AI 模式（OpenAI Images API / Claude vision）和规则降级模式。
"""
import base64
import json
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from agents.base_agent import BaseAgent
from backend.config import get_ai_config, AI_PROVIDER

# 图片输出目录
OUTPUT_DIR = Path(__file__).parent.parent.parent / "output" / "image_agent"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 图片生成 System Prompt
IMAGE_GEN_PROMPT = """You are an expert image generation prompt engineer.
Convert user requests into detailed, high-quality image generation prompts.

Rules:
1. Output in English (most image models work best with English prompts)
2. Include: subject, style, lighting, composition, color palette, mood
3. Be specific but concise (50-200 words)
4. Add negative prompt suggestions when relevant
5. Suggest the best aspect ratio for the scene

Output JSON:
{
  "enhanced_prompt": "detailed prompt...",
  "negative_prompt": "things to avoid...",
  "style": "photorealistic|illustration|3d_render|anime|oil_painting|vector",
  "aspect_ratio": "1:1|16:9|9:16|4:3|3:4",
  "model_suggestion": "dalle3|sd-xl|midjourney"
}"""

IMAGE_ANALYZE_PROMPT = """You are a visual analysis expert. Describe the image content in detail.

Output JSON:
{
  "summary": "one-line description",
  "objects": ["list of objects detected"],
  "colors": ["dominant colors"],
  "style": "photorealistic|illustration|abstract|etc",
  "text_in_image": "any text visible",
  "mood": "cheerful|serious|dark|etc",
  "quality_assessment": "assessment of image quality"
}"""


class ImageAgent(BaseAgent):
    """Image Agent — AI 图片生成与分析"""

    AGENT_ID = "image"
    DISPLAY_NAME = "图片生成"
    CAPABILITIES = ["image", "dalle", "vision"]
    TASK_TYPES = ["image_generate", "image_analyze"]

    def __init__(self, api_key: Optional[str] = None, timeout: int = 90):
        super().__init__(name="image", timeout=timeout)
        try:
            config = get_ai_config()
            self.api_key = api_key or config["api_key"]
            self.api_base = config["base_url"]
            self.model = config["model"]
        except RuntimeError:
            self.api_key = ""
            self.api_base = "https://api.openai.com/v1"
            self.model = "dall-e-3"

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"img_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "image_generate")
        goal = task.get("goal", "")
        prompt = task.get("prompt", task.get("image_prompt", goal))

        if not prompt:
            return self._result(task_id, "失败", "缺少图片生成 prompt", success=False)

        handlers = {
            "image_generate": self._handle_generate,
            "image_analyze": self._handle_analyze,
            "image_edit": self._handle_edit,
        }
        handler = handlers.get(task_type, self._handle_generate)
        return handler(task, task_id, prompt)

    # ── 图片生成 ──────────────────────────────────────────

    def _handle_generate(self, task: Dict, task_id: str, prompt: str) -> Dict:
        size = task.get("size", "1024x1024")
        style = task.get("style", "vivid")  # vivid or natural (DALL-E)
        n_images = task.get("n", task.get("n_images", 1))

        if self.api_key:
            result = self._call_dalle(prompt, size, style, n_images)
            if result and result.get("images"):
                self._save_images(result["images"], task_id)
                return self._result(
                    task_id, "生成完成",
                    f"成功生成 {len(result['images'])} 张图片",
                    success=True,
                    data={
                        "images": result["images"],
                        "prompt_used": result.get("revised_prompt", prompt),
                        "model": result.get("model", "dall-e-3"),
                        "output_dir": str(OUTPUT_DIR / task_id),
                    }
                )

        # 规则降级 — 返回增强后的提示词
        enhanced = self._enhance_prompt(prompt)
        return self._result(
            task_id, "提示词已优化（离线模式）",
            "未配置图片生成 API，已生成优化的提示词供手动使用",
            success=False,
            data={
                "enhanced_prompt": enhanced.get("enhanced_prompt", prompt),
                "negative_prompt": enhanced.get("negative_prompt", ""),
                "style": enhanced.get("style", ""),
                "aspect_ratio": enhanced.get("aspect_ratio", "1:1"),
                "note": "请在支持图片生成的工具中使用以上提示词"
            }
        )

    def _handle_analyze(self, task: Dict, task_id: str, prompt: str) -> Dict:
        image_url = task.get("image_url", task.get("url", ""))
        image_path = task.get("image_path", task.get("path", ""))

        image_data = None
        if image_path and os.path.exists(image_path):
            with open(image_path, "rb") as f:
                image_data = base64.b64encode(f.read()).decode("utf-8")
        elif image_url:
            image_data = image_url  # 传 URL
        else:
            return self._result(task_id, "跳过", "未提供图片 URL 或路径", success=False)

        if self.api_key and AI_PROVIDER == "claude":
            result = self._call_claude_vision(prompt or "描述这张图片", image_data, image_url)
            if result:
                return self._result(task_id, "分析完成", result.get("summary", ""),
                                    success=True, data=result)

        return self._result(
            task_id, "图片分析（离线模式）",
            "图片分析需要 Claude vision 或 GPT-4V 能力。当前 Provider 不支持",
            success=False,
            suggestions=["切换 AI Provider 到 Claude 或 OpenAI 以使用图片分析"]
        )

    def _handle_edit(self, task: Dict, task_id: str, prompt: str) -> Dict:
        return self._result(
            task_id, "跳过",
            "图片编辑功能需要 DALL-E 2 edit API。DALL-E 3 暂不支持直接编辑，请使用 image_generate 重新生成",
            success=False
        )

    # ── API 调用 ──────────────────────────────────────────

    def _call_dalle(self, prompt: str, size: str = "1024x1024",
                    style: str = "vivid", n: int = 1) -> Optional[Dict]:
        """智能路由图片生成 — 自动选择可用的图片 API"""
        import urllib.request

        provider = AI_PROVIDER
        results = []

        # ── 路由表 ──
        # 1. OpenAI → 直接调 DALL-E 3
        if provider == "openai":
            result = self._call_openai_images(prompt, size, style, n)
            if result:
                return result
            results.append(("openai", False))

        # 2. Claude → 不支持图片生成，尝试 CC Switch
        # 3. DeepSeek → 不支持 /images/generations，尝试 CC Switch → 再尝试 OpenAI
        if provider in ("deepseek", "claude"):
            # DeepSeek Janus (通过 CC Switch 或直连)
            result = self._call_deepseek_janus(prompt, size)
            if result:
                return result
            results.append(("deepseek", False))

            # Fallback: 用 CC Switch → OpenAI 兼容路由
            result = self._call_ccswitch_images(prompt, size, style)
            if result:
                return result
            results.append(("ccswitch", False))

        # 4. 最终 fallback: 如果有 OpenAI key，直接走 OpenAI
        openai_key = os.getenv("OPENAI_API_KEY", "")
        if openai_key and provider != "openai":
            result = self._call_openai_images(prompt, size, style, n, api_key=openai_key)
            if result:
                return result

        # 全部失败 → 返回 None
        return None

    def _call_openai_images(self, prompt: str, size: str, style: str,
                            n: int, api_key: str = None) -> Optional[Dict]:
        """调用 OpenAI DALL-E 3 API"""
        try:
            import urllib.request
            key = api_key or self.api_key
            url = "https://api.openai.com/v1/images/generations"
            payload = json.dumps({
                "model": "dall-e-3",
                "prompt": prompt,
                "n": min(n, 1),
                "size": size,
                "style": style,
                "response_format": "url",
            }).encode("utf-8")
            headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            images = []
            for item in data.get("data", []):
                images.append({
                    "url": item.get("url", ""),
                    "revised_prompt": item.get("revised_prompt", prompt),
                })
            return {
                "images": images,
                "revised_prompt": data.get("data", [{}])[0].get("revised_prompt", prompt) if data.get("data") else prompt,
                "model": "dall-e-3",
                "created": data.get("created", 0),
            }
        except Exception as e:
            print(f"[Image Agent] OpenAI DALL-E 调用失败: {e}")
            return None

    def _call_deepseek_janus(self, prompt: str, size: str = "1024x1024") -> Optional[Dict]:
        """尝试 DeepSeek Janus 多模态模型生成图片"""
        try:
            import urllib.request
            # DeepSeek Janus 走 chat/completions + 特殊 system prompt
            # 返回 base64 图片或 URL
            url = f"{self.api_base.rstrip('/')}/chat/completions"
            janus_prompt = f"Generate an image: {prompt}. Style: photorealistic. Output as base64 or URL."
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [
                    {"role": "system", "content": "You are an image generation model. Generate images based on descriptions."},
                    {"role": "user", "content": janus_prompt},
                ],
                "max_tokens": 4096,
            }).encode("utf-8")
            headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = data["choices"][0]["message"]["content"]

            # Check if response contains base64 image or URL
            if "data:image" in text or "![image]" in text or text.startswith("http"):
                return {"images": [{"url": text.strip()}], "model": "deepseek-janus", "revised_prompt": prompt}
            return None
        except Exception as e:
            print(f"[Image Agent] DeepSeek Janus 调用失败: {e}")
            return None

    def _call_ccswitch_images(self, prompt: str, size: str = "1024x1024",
                              style: str = "vivid") -> Optional[Dict]:
        """通过 CC Switch 代理调用图片生成"""
        try:
            import urllib.request
            cc_url = os.getenv("CC_SWITCH_URL", "http://127.0.0.1:15721")
            url = f"{cc_url.rstrip('/')}/v1/images/generations"
            payload = json.dumps({
                "model": "dall-e-3",
                "prompt": prompt,
                "n": 1,
                "size": size,
                "style": style,
                "response_format": "url",
            }).encode("utf-8")
            headers = {
                "Content-Type": "application/json",
                "x-api-key": self.api_key,
            }
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                data = json.loads(resp.read().decode("utf-8"))
            images = [{"url": item.get("url", ""), "revised_prompt": item.get("revised_prompt", prompt)}
                      for item in data.get("data", [])]
            return {"images": images, "model": "dall-e-3 (via CC Switch)", "revised_prompt": prompt} if images else None
        except Exception as e:
            print(f"[Image Agent] CC Switch 图片调用失败: {e}")
            return None

    def _call_claude_vision(self, prompt: str, image_data: str, is_url: bool = True):
        """调用 Claude Vision 分析图片"""
        try:
            import urllib.request

            content = []
            if is_url:
                content.append({
                    "type": "image",
                    "source": {"type": "url", "url": image_data}
                })
            else:
                content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": image_data,
                    }
                })
            content.append({"type": "text", "text": prompt})

            payload = json.dumps({
                "model": self.model,
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": content}],
            }).encode("utf-8")

            url = f"{self.api_base.rstrip('/')}/v1/messages"
            headers = {
                "x-api-key": self.api_key,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01",
            }
            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                text = body["content"][0]["text"]
                return self._extract_json(text) or {"summary": text[:500]}

        except Exception as e:
            print(f"[Image Agent] Vision 调用失败: {e}")
            return None

    # ── Prompt 增强 ────────────────────────────────────────

    def _enhance_prompt(self, raw_prompt: str) -> Dict:
        """本地规则增强提示词"""
        # 检测语言：中文 → 加风格建议
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

        enhanced = raw_prompt if is_chinese else raw_prompt
        if is_chinese:
            enhanced = f"{raw_prompt}, {detected_style}"

        return {
            "enhanced_prompt": enhanced,
            "negative_prompt": "blurry, low quality, distorted, watermark, text",
            "style": "photorealistic",
            "aspect_ratio": "1:1",
        }

    # ── 辅助方法 ──────────────────────────────────────────

    def _save_images(self, images: List[Dict], task_id: str):
        """下载并保存图片"""
        import urllib.request as _ur

        task_dir = OUTPUT_DIR / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        for i, img in enumerate(images):
            url = img.get("url", "")
            if not url:
                continue
            try:
                ext = ".png"
                if "jpg" in url.lower() or "jpeg" in url.lower():
                    ext = ".jpg"
                elif "webp" in url.lower():
                    ext = ".webp"
                filepath = task_dir / f"image_{i+1}{ext}"
                _ur.urlretrieve(url, str(filepath))
                img["local_path"] = str(filepath)
            except Exception as e:
                print(f"[Image Agent] 保存图片失败: {e}")

    @staticmethod
    def _extract_json(text: str) -> Optional[Dict]:
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

    def _result(self, task_id: str, status: str, summary: str,
                success: bool = True, data: Dict = None,
                suggestions: List = None) -> Dict:
        return {
            "task_id": task_id,
            "agent": "image_agent",
            "agent_name": "Image 图片生成",
            "status": status,
            "summary": summary,
            "success": success,
            "result": summary,
            "data": data or {},
            "suggestions": suggestions or [],
            "output": data or {},
        }
