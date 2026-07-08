"""Provider Health API 测试

测试 GET /config/providers/health 端点：
- 返回结构完整性
- 不暴露 API Key 值
- Mock/真实 provider 状态正确
"""
import os
import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient


@pytest.fixture
def client():
    """创建测试客户端"""
    from backend.app import app
    return TestClient(app)


# ── 返回结构测试 ──────────────────────────────────────────

def test_providers_health_returns_200(client):
    """端点应返回 200"""
    resp = client.get("/config/providers/health")
    assert resp.status_code == 200


def test_providers_health_has_search_and_image(client):
    """返回应包含 search 和 image 两个 section"""
    resp = client.get("/config/providers/health")
    data = resp.json()
    assert "search" in data
    assert "image" in data


def test_search_section_structure(client):
    """search section 应包含必要字段"""
    resp = client.get("/config/providers/health")
    search = resp.json()["search"]
    assert "name" in search
    assert "is_mock" in search
    assert "has_api_key" in search
    assert "env_provider" in search
    assert "available" in search
    assert "providers" in search
    assert isinstance(search["providers"], list)


def test_image_section_structure(client):
    """image section 应包含必要字段"""
    resp = client.get("/config/providers/health")
    image = resp.json()["image"]
    assert "name" in image
    assert "is_mock" in image
    assert "has_api_key" in image
    assert "env_provider" in image
    assert "available" in image
    assert "providers" in image
    assert isinstance(image["providers"], list)


def test_provider_list_item_structure(client):
    """providers 列表中每项应有 name/has_key/env_var"""
    resp = client.get("/config/providers/health")
    data = resp.json()
    for section in ["search", "image"]:
        for p in data[section]["providers"]:
            assert "name" in p
            assert "has_key" in p
            assert "env_var" in p


# ── 安全测试：不暴露 Key ──────────────────────────────────

def test_no_api_key_values_exposed(client):
    """确保响应中不包含任何 API Key 值"""
    resp = client.get("/config/providers/health")
    data = resp.json()
    resp_str = str(data)
    # 这些 key 的值不应出现在响应中
    sensitive_keys = ["sk-", "SERPAPI_API_KEY=", "BING_SEARCH_API_KEY=", "OPENAI_API_KEY="]
    for key in sensitive_keys:
        assert key not in resp_str, f"Response should not contain {key}"


def test_provider_items_only_have_name_and_has_key(client):
    """provider items 只应有 name/has_key/env_var，不应有 key/value 字段"""
    resp = client.get("/config/providers/health")
    data = resp.json()
    for section in ["search", "image"]:
        for p in data[section]["providers"]:
            allowed_keys = {"name", "has_key", "env_var"}
            assert set(p.keys()) <= allowed_keys, f"Unexpected keys: {set(p.keys()) - allowed_keys}"


def test_endpoint_reports_key_presence_without_leaking_values(client):
    """配置真实 key 时，端点只返回 has_key/has_api_key，不返回 key 值"""
    with patch.dict(os.environ, {
        "SERPAPI_API_KEY": "serpapi-secret-123",
        "BING_SEARCH_API_KEY": "bing-secret-456",
        "OPENAI_API_KEY": "sk-test-secret-789",
        "WEB_SEARCH_PROVIDER": "auto",
        "IMAGE_PROVIDER": "auto",
    }, clear=False):
        resp = client.get("/config/providers/health")

    assert resp.status_code == 200
    data = resp.json()
    assert data["search"]["has_api_key"] is True
    assert data["image"]["has_api_key"] is True
    assert any(p["name"] == "serpapi" and p["has_key"] is True for p in data["search"]["providers"])
    assert any(p["name"] == "bing" and p["has_key"] is True for p in data["search"]["providers"])
    assert any(p["name"] == "openai" and p["has_key"] is True for p in data["image"]["providers"])

    response_text = str(data)
    assert "serpapi-secret-123" not in response_text
    assert "bing-secret-456" not in response_text
    assert "sk-test-secret-789" not in response_text


# ── Mock/真实 Provider 状态测试 ────────────────────────────

def test_search_provider_default_to_mock(client):
    """无 API Key 时应默认使用 mock"""
    with patch.dict(os.environ, {
        "SERPAPI_API_KEY": "",
        "BING_SEARCH_API_KEY": "",
        "WEB_SEARCH_PROVIDER": "auto",
    }, clear=False):
        # 需要重新导入以获取最新的 provider
        from backend.services.web_search_service import get_provider_info
        info = get_provider_info()
        assert "Mock" in info["provider"] or info["has_api_key"] is False


def test_search_provider_with_serpapi_key(client):
    """配置 SERPAPI_API_KEY 后应使用 SerpAPI"""
    with patch.dict(os.environ, {
        "SERPAPI_API_KEY": "test-key-123",
        "BING_SEARCH_API_KEY": "",
        "WEB_SEARCH_PROVIDER": "auto",
    }, clear=False):
        from backend.services.web_search_service import get_provider_info
        info = get_provider_info()
        assert info["has_api_key"] is True
        assert "SerpAPI" in info["provider"]


def test_search_provider_with_bing_key(client):
    """配置 BING_SEARCH_API_KEY 后应使用 Bing"""
    with patch.dict(os.environ, {
        "SERPAPI_API_KEY": "",
        "BING_SEARCH_API_KEY": "test-key-456",
        "WEB_SEARCH_PROVIDER": "bing",
    }, clear=False):
        from backend.services.web_search_service import get_provider_info
        info = get_provider_info()
        assert info["has_api_key"] is True
        assert "Bing" in info["provider"]


def test_image_provider_default_to_mock(client):
    """无 API Key 时应默认使用 mock"""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "",
        "IMAGE_PROVIDER": "",
    }, clear=False):
        from backend.services.image_generation_service import get_image_provider
        provider = get_image_provider()
        assert provider.name == "mock"


def test_image_provider_with_openai_key(client):
    """配置 OPENAI_API_KEY 后应使用 openai"""
    with patch.dict(os.environ, {
        "OPENAI_API_KEY": "test-key-789",
        "IMAGE_PROVIDER": "openai",
    }, clear=False):
        from backend.services.image_generation_service import get_image_provider
        provider = get_image_provider()
        assert provider.name == "openai"
