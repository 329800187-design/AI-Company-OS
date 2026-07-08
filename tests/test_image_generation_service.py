"""
Image Generation Service 测试 — Phase 4.8

测试:
  - MockImageProvider
  - OpenAIImageProvider (mock)
  - get_image_provider() 工厂方法
  - Image Agent metadata.image_provider
  - MiniDelivery artifact 渲染 generated_images
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from backend.services.image_generation_service import (
    MockImageProvider,
    OpenAIImageProvider,
    get_image_provider,
    ImageProvider,
)


class TestMockImageProvider:
    """测试 MockImageProvider"""

    def test_name(self):
        provider = MockImageProvider()
        assert provider.name == "mock"

    def test_is_available(self):
        provider = MockImageProvider()
        assert provider.is_available() is True

    def test_generate_returns_ok(self):
        provider = MockImageProvider()
        result = provider.generate("test prompt")
        assert result["ok"] is True
        assert result["provider"] == "mock"
        assert result["error"] is None

    def test_generate_returns_images(self):
        provider = MockImageProvider()
        result = provider.generate("test prompt", n=2)
        assert len(result["generated_images"]) == 2

    def test_generate_max_4_images(self):
        provider = MockImageProvider()
        result = provider.generate("test prompt", n=10)
        assert len(result["generated_images"]) <= 4

    def test_generate_image_fields(self):
        provider = MockImageProvider()
        result = provider.generate("test prompt", n=1)
        img = result["generated_images"][0]
        assert "url" in img
        assert img["url"].startswith("https://placehold.co/")
        assert img["revised_prompt"] == "test prompt"
        assert img["size"] == "1024x1024"
        assert img["index"] == 0
        assert img["is_mock"] is True

    def test_generate_custom_size(self):
        provider = MockImageProvider()
        result = provider.generate("test prompt", size="1792x1024")
        assert result["generated_images"][0]["size"] == "1792x1024"
        assert "1792x1024" in result["generated_images"][0]["url"]


class TestOpenAIImageProvider:
    """测试 OpenAIImageProvider (mock API key)"""

    def test_name(self):
        provider = OpenAIImageProvider(api_key="test-key")
        assert provider.name == "openai"

    def test_is_available_with_key(self):
        provider = OpenAIImageProvider(api_key="test-key")
        assert provider.is_available() is True

    def test_is_available_without_key(self):
        provider = OpenAIImageProvider(api_key="")
        assert provider.is_available() is False

    @patch.dict(os.environ, {"OPENAI_API_KEY": ""})
    def test_generate_without_key_returns_error(self):
        provider = OpenAIImageProvider()
        result = provider.generate("test prompt")
        assert result["ok"] is False
        assert "OPENAI_API_KEY" in result["error"]

    @patch("httpx.post")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_generate_success(self, mock_post):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": [
                {
                    "url": "https://example.com/image.png",
                    "revised_prompt": "revised prompt",
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = OpenAIImageProvider(api_key="test-key")
        result = provider.generate("test prompt")

        assert result["ok"] is True
        assert result["provider"] == "openai"
        assert len(result["generated_images"]) == 1
        assert result["generated_images"][0]["url"] == "https://example.com/image.png"
        assert result["generated_images"][0]["is_mock"] is False

    @patch("httpx.post")
    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_generate_api_error(self, mock_post):
        mock_post.side_effect = Exception("API Error")

        provider = OpenAIImageProvider(api_key="test-key")
        result = provider.generate("test prompt")

        assert result["ok"] is False
        assert "API Error" in result["error"]


class TestGetImageProvider:
    """测试 get_image_provider() 工厂方法"""

    @patch.dict(os.environ, {"IMAGE_PROVIDER": "", "OPENAI_API_KEY": ""})
    def test_default_returns_mock(self):
        provider = get_image_provider()
        assert isinstance(provider, MockImageProvider)

    @patch.dict(os.environ, {"IMAGE_PROVIDER": "mock"})
    def test_explicit_mock(self):
        provider = get_image_provider("mock")
        assert isinstance(provider, MockImageProvider)

    @patch.dict(os.environ, {"IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": "test-key"})
    def test_explicit_openai(self):
        provider = get_image_provider("openai")
        assert isinstance(provider, OpenAIImageProvider)

    @patch.dict(os.environ, {"OPENAI_API_KEY": "test-key"})
    def test_auto_detect_openai(self):
        provider = get_image_provider()
        assert isinstance(provider, OpenAIImageProvider)

    @patch.dict(os.environ, {"IMAGE_PROVIDER": "unknown", "OPENAI_API_KEY": ""})
    def test_unknown_falls_back_to_mock(self):
        provider = get_image_provider()
        assert isinstance(provider, MockImageProvider)

    @patch.dict(os.environ, {"IMAGE_PROVIDER": "openai", "OPENAI_API_KEY": ""})
    def test_openai_unavailable_falls_back_to_mock(self):
        provider = get_image_provider()
        assert isinstance(provider, MockImageProvider)


class TestImageAgentProviderIntegration:
    """测试 Image Agent 与 provider 的集成"""

    def test_agent_has_image_provider_property(self):
        from agents.image_agent.agent import ImageAgent
        agent = ImageAgent()
        assert hasattr(agent, "image_provider")

    def test_agent_metadata_has_image_provider(self):
        """测试 Agent 执行后 metadata 包含 image_provider"""
        from agents.image_agent.agent import ImageAgent

        # 使用 mock provider
        mock_provider = MockImageProvider()
        agent = ImageAgent(image_provider=mock_provider)

        task = {
            "task_id": "test_001",
            "goal": "test goal",
            "task_type": "image_generate",
            "prompt": "test prompt",
        }

        result = agent.run(task)
        assert result["ok"] is True
        assert "image_provider" in result["meta"]
        assert result["meta"]["image_provider"] == "mock"

    def test_agent_structured_output_has_generated_images(self):
        """测试 Agent 执行后 structured_output 包含 generated_images"""
        from agents.image_agent.agent import ImageAgent

        mock_provider = MockImageProvider()
        agent = ImageAgent(image_provider=mock_provider)

        task = {
            "task_id": "test_002",
            "goal": "test goal",
            "task_type": "image_generate",
            "prompt": "test prompt",
        }

        result = agent.run(task)
        data = result.get("data") or result.get("output") or {}
        assert "generated_images" in data
        assert len(data["generated_images"]) > 0
        assert data["generated_images"][0]["is_mock"] is True

    def test_agent_skip_image_generation(self):
        """测试 generate_images=False 时跳过图片生成"""
        from agents.image_agent.agent import ImageAgent

        mock_provider = MockImageProvider()
        agent = ImageAgent(image_provider=mock_provider)

        task = {
            "task_id": "test_003",
            "goal": "test goal",
            "task_type": "image_generate",
            "prompt": "test prompt",
            "generate_images": False,
        }

        result = agent.run(task)
        data = result.get("data") or result.get("output") or {}
        assert "generated_images" not in data


class TestMiniDeliveryImageArtifact:
    """测试 MiniDelivery artifact 渲染 generated_images"""

    def test_render_image_with_generated_images(self):
        """测试 _render_image 包含 generated_images"""
        from backend.routers.minidelivery_router import _render_image

        result = {
            "structured_output": {
                "image_prompt": "test prompt",
                "negative_prompt": "blurry",
                "style": "photorealistic",
                "generated_images": [
                    {
                        "url": "https://example.com/image1.png",
                        "revised_prompt": "revised prompt 1",
                        "size": "1024x1024",
                        "index": 0,
                        "is_mock": False,
                    },
                    {
                        "url": "https://placeholder.ai/image/abc123.png",
                        "revised_prompt": "revised prompt 2",
                        "size": "1024x1024",
                        "index": 1,
                        "is_mock": True,
                    },
                ],
            },
            "meta": {
                "image_provider": "openai",
            },
        }

        md = _render_image(result, "test goal")
        assert "生成图片" in md
        assert "Provider: openai" in md
        assert "图片 1" in md
        assert "图片 2" in md
        assert "模拟" in md
        assert "https://example.com/image1.png" in md

    def test_render_image_without_generated_images(self):
        """测试 _render_image 不包含 generated_images 时正常渲染"""
        from backend.routers.minidelivery_router import _render_image

        result = {
            "structured_output": {
                "image_prompt": "test prompt",
                "negative_prompt": "blurry",
                "style": "photorealistic",
            },
            "meta": {},
        }

        md = _render_image(result, "test goal")
        assert "生成图片" not in md
        assert "图片提示词" in md


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
