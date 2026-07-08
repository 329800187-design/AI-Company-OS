"""
Image Generation Service — 可替换图片生成 Provider 接口

Phase 4.8 新增:
  - ImageProvider: 抽象基类，定义 generate() 接口
  - MockImageProvider: 默认 mock 实现，返回模拟数据
  - OpenAIImageProvider: 预留，用 OPENAI_API_KEY 启用
  - get_image_provider(): 工厂方法，根据环境变量选择 provider

设计原则:
  - 不破坏现有 /agents/image/execute API
  - Image Agent 可选调用 provider 生成真实图片
  - 默认 mock，不强依赖真实 API key
"""
import logging
import os
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class ImageProvider(ABC):
    """图片生成 Provider 抽象基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """Provider 名称，如 'mock', 'openai', 'stability'"""
        ...

    @abstractmethod
    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        size: str = "1024x1024",
        style: str = "natural",
        n: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        生成图片。

        Args:
            prompt: 图片提示词
            negative_prompt: 负面提示词
            size: 图片尺寸，如 "1024x1024"
            style: 风格
            n: 生成数量
            **kwargs: 扩展参数

        Returns:
            {
                "ok": bool,
                "provider": str,           # provider 名称
                "generated_images": [      # 生成的图片列表
                    {
                        "url": str,        # 图片 URL (mock 或真实)
                        "revised_prompt": str,  # 修订后的提示词
                        "size": str,
                        "index": int,
                    }
                ],
                "error": str | None,
            }
        """
        ...

    def is_available(self) -> bool:
        """检查 provider 是否可用（如 API key 是否存在）"""
        return True


class MockImageProvider(ImageProvider):
    """Mock 图片生成 Provider — 返回模拟数据，不调用真实 API"""

    @property
    def name(self) -> str:
        return "mock"

    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        size: str = "1024x1024",
        style: str = "natural",
        n: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """返回模拟图片数据"""
        images = []
        width, height = _parse_size(size)
        for i in range(min(n, 4)):  # 最多 4 张
            images.append({
                "url": f"https://placehold.co/{width}x{height}/EEE/666.png?text=Mock+Image+{i + 1}",
                "revised_prompt": prompt,
                "size": size,
                "index": i,
                "is_mock": True,
            })

        return {
            "ok": True,
            "provider": "mock",
            "generated_images": images,
            "error": None,
        }


def _parse_size(size: str) -> tuple[int, int]:
    """?? 1024x1024 ???????????? 1024x1024"""
    try:
        width, height = str(size).lower().split("x", 1)
        return max(1, int(width)), max(1, int(height))
    except Exception:
        return 1024, 1024


class OpenAIImageProvider(ImageProvider):
    """
    OpenAI DALL-E 图片生成 Provider — 预留实现。

    需要 OPENAI_API_KEY 环境变量。
    """

    def __init__(self, api_key: Optional[str] = None):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", "")

    @property
    def name(self) -> str:
        return "openai"

    def is_available(self) -> bool:
        return bool(self._api_key)

    def generate(
        self,
        prompt: str,
        *,
        negative_prompt: str = "",
        size: str = "1024x1024",
        style: str = "natural",
        n: int = 1,
        **kwargs,
    ) -> Dict[str, Any]:
        """调用 OpenAI DALL-E API 生成图片"""
        if not self._api_key:
            return {
                "ok": False,
                "provider": "openai",
                "generated_images": [],
                "error": "OPENAI_API_KEY 未配置",
            }

        try:
            import httpx

            response = httpx.post(
                "https://api.openai.com/v1/images/generations",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "dall-e-3",
                    "prompt": prompt,
                    "n": min(n, 1),  # DALL-E 3 最多 1 张
                    "size": size,
                    "style": style,
                    "quality": "standard",
                },
                timeout=120,
            )
            response.raise_for_status()
            data = response.json()

            images = []
            for i, item in enumerate(data.get("data", [])):
                images.append({
                    "url": item.get("url", ""),
                    "revised_prompt": item.get("revised_prompt", prompt),
                    "size": size,
                    "index": i,
                    "is_mock": False,
                })

            return {
                "ok": True,
                "provider": "openai",
                "generated_images": images,
                "error": None,
            }

        except ImportError:
            return {
                "ok": False,
                "provider": "openai",
                "generated_images": [],
                "error": "httpx 未安装，无法调用 OpenAI API",
            }
        except Exception as e:
            logger.error(f"[OpenAIImageProvider] 调用失败: {e}")
            return {
                "ok": False,
                "provider": "openai",
                "generated_images": [],
                "error": str(e),
            }


# ── 工厂方法 ──────────────────────────────────────────────────────

_PROVIDER_MAP: Dict[str, type] = {
    "mock": MockImageProvider,
    "openai": OpenAIImageProvider,
}


def get_image_provider(name: Optional[str] = None) -> ImageProvider:
    """
    工厂方法：根据名称或环境变量选择 provider。

    优先级:
      1. 显式传入 name
      2. IMAGE_PROVIDER 环境变量
      3. 如果 OPENAI_API_KEY 存在 → openai
      4. 默认 → mock
    """
    provider_name = name or os.getenv("IMAGE_PROVIDER", "")

    if not provider_name:
        # 自动检测
        if os.getenv("OPENAI_API_KEY"):
            provider_name = "openai"
        else:
            provider_name = "mock"

    provider_name = provider_name.lower()

    cls = _PROVIDER_MAP.get(provider_name)
    if cls is None:
        logger.warning(f"未知 image provider '{provider_name}'，回退到 mock")
        cls = MockImageProvider

    instance = cls()

    if not instance.is_available():
        logger.warning(f"Provider '{provider_name}' 不可用，回退到 mock")
        return MockImageProvider()

    return instance
