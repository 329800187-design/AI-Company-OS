"""Web Search Service 测试 — mock provider、search_web 接口、provider 信息"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock

from backend.services.web_search_service import (
    SearchResult,
    MockSearchProvider,
    search_web,
    get_provider_info,
)


class TestSearchResult:
    """SearchResult 数据模型测试"""

    def test_search_result_creation(self):
        """SearchResult 可以正常创建"""
        r = SearchResult(
            title="测试标题",
            url="https://example.com",
            snippet="测试摘要",
            source="example.com",
            published_date="2025-01-01",
        )
        assert r.title == "测试标题"
        assert r.url == "https://example.com"
        assert r.snippet == "测试摘要"
        assert r.source == "example.com"

    def test_search_result_to_dict(self):
        """to_dict 序列化正确"""
        r = SearchResult(title="t", url="u", snippet="s")
        d = r.to_dict()
        assert isinstance(d, dict)
        assert d["title"] == "t"
        assert d["url"] == "u"
        assert d["snippet"] == "s"
        assert "source" in d
        assert "published_date" in d


class TestMockSearchProvider:
    """MockSearchProvider 测试"""

    def test_mock_returns_results(self):
        """Mock provider 应返回结果列表"""
        provider = MockSearchProvider()
        results = provider.search("手工耳环市场", max_results=3)
        assert isinstance(results, list)
        assert len(results) == 3

    def test_mock_results_have_correct_structure(self):
        """Mock 结果包含正确字段"""
        provider = MockSearchProvider()
        results = provider.search("test", max_results=1)
        r = results[0]
        assert isinstance(r, SearchResult)
        assert "test" in r.title
        assert r.url.startswith("https://")
        assert len(r.snippet) > 0

    def test_mock_respects_max_results(self):
        """Mock provider 尊重 max_results 参数"""
        provider = MockSearchProvider()
        results = provider.search("test", max_results=2)
        assert len(results) == 2

    def test_mock_max_results_capped_at_3(self):
        """Mock provider 最多返回 3 条"""
        provider = MockSearchProvider()
        results = provider.search("test", max_results=10)
        assert len(results) == 3


class TestSearchWeb:
    """search_web 公共接口测试"""

    def test_search_web_returns_list_of_dicts(self):
        """search_web 返回 dict 列表"""
        results = search_web("手工耳环市场分析")
        assert isinstance(results, list)
        assert len(results) > 0
        assert isinstance(results[0], dict)

    def test_search_web_result_has_required_fields(self):
        """搜索结果包含必要字段"""
        results = search_web("test query")
        r = results[0]
        assert "title" in r
        assert "url" in r
        assert "snippet" in r
        assert "source" in r

    def test_search_web_empty_query_returns_empty(self):
        """空查询返回空列表"""
        assert search_web("") == []
        assert search_web("   ") == []
        assert search_web(None) == []

    def test_search_web_default_provider_is_mock(self):
        """无 API key 时默认使用 mock provider"""
        with patch.dict(os.environ, {}, clear=True):
            # 清除所有搜索相关环境变量
            os.environ.pop("WEB_SEARCH_PROVIDER", None)
            os.environ.pop("SERPAPI_API_KEY", None)
            os.environ.pop("BING_SEARCH_API_KEY", None)
            results = search_web("test")
            # mock provider 返回包含"模拟结果"的结果
            assert any("模拟" in r.get("title", "") for r in results)


class TestGetProviderInfo:
    """get_provider_info 测试"""

    def test_provider_info_has_required_fields(self):
        """provider 信息包含必要字段"""
        info = get_provider_info()
        assert "provider" in info
        assert "has_api_key" in info
        assert "env_provider" in info

    def test_provider_info_default_no_key(self):
        """无 API key 时 has_api_key 为 False"""
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("WEB_SEARCH_PROVIDER", None)
            os.environ.pop("SERPAPI_API_KEY", None)
            os.environ.pop("BING_SEARCH_API_KEY", None)
            info = get_provider_info()
            assert info["has_api_key"] is False


class TestSerpAPIProvider:
    """SerpAPI Provider 测试"""

    def test_serpapi_provider_init(self):
        """SerpAPIProvider 可以初始化"""
        from backend.services.web_search_service import SerpAPIProvider
        provider = SerpAPIProvider(api_key="test_key")
        assert provider.api_key == "test_key"

    def test_serpapi_provider_calls_api(self):
        """SerpAPI provider 调用正确的 API"""
        import requests as req_module
        from backend.services.web_search_service import SerpAPIProvider
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "organic_results": [
                {"title": "Result 1", "link": "https://a.com", "snippet": "s1", "displayed_link": "a.com"},
                {"title": "Result 2", "link": "https://b.com", "snippet": "s2", "displayed_link": "b.com"},
            ]
        }
        with patch.object(req_module, "get", return_value=mock_resp):
            provider = SerpAPIProvider(api_key="test_key")
            results = provider.search("test", max_results=2)
            assert len(results) == 2
            assert results[0].title == "Result 1"


class TestBingSearchProvider:
    """Bing Search Provider 测试"""

    def test_bing_provider_init(self):
        """BingSearchProvider 可以初始化"""
        from backend.services.web_search_service import BingSearchProvider
        provider = BingSearchProvider(api_key="test_key")
        assert provider.api_key == "test_key"

    def test_bing_provider_calls_api(self):
        """Bing provider 调用正确的 API"""
        import requests as req_module
        from backend.services.web_search_service import BingSearchProvider
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.raise_for_status = MagicMock()
        mock_resp.json.return_value = {
            "webPages": {
                "value": [
                    {"name": "R1", "url": "https://a.com", "snippet": "s1", "displayed_link": "a.com"},
                ]
            }
        }
        with patch.object(req_module, "get", return_value=mock_resp):
            provider = BingSearchProvider(api_key="test_key")
            results = provider.search("test", max_results=1)
            assert len(results) == 1
            assert results[0].title == "R1"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
