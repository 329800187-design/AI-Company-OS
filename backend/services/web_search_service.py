"""
Web Search Service — 可替换的联网搜索服务层

设计原则：
  1. 统一接口：所有 provider 实现 search(query, max_results) -> list[SearchResult]
  2. 可替换：通过环境变量 WEB_SEARCH_PROVIDER 切换 provider
  3. Fallback：无 API key 时自动降级为 mock provider
  4. 零侵入：Research Agent 只依赖此服务，不直接依赖任何搜索 API

支持的 provider：
  - mock: 模拟搜索结果（默认 fallback）
  - serpapi: SerpAPI Google Search（需 SERPAPI_API_KEY）
  - bing: Bing Web Search API（需 BING_SEARCH_API_KEY）

使用方式：
  from backend.services.web_search_service import search_web
  results = search_web("手工耳环市场分析", max_results=5)
"""
import json
import logging
import os
from dataclasses import dataclass, field, asdict
from typing import List, Optional, Protocol

logger = logging.getLogger(__name__)


# ── 数据模型 ────────────────────────────────────────────

@dataclass
class SearchResult:
    """单条搜索结果"""
    title: str
    url: str
    snippet: str
    source: str = ""  # 来源域名
    published_date: str = ""  # 发布日期（如有）

    def to_dict(self) -> dict:
        return asdict(self)


# ── Provider 接口 ──────────────────────────────────────

class SearchProvider(Protocol):
    """搜索 provider 接口"""
    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        ...


# ── Mock Provider ─────────────────────────────────────

class MockSearchProvider:
    """模拟搜索 provider — 无 API key 时的 fallback"""

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        logger.info("[WebSearch] Using mock provider for query: %s", query)
        results = []
        for i in range(min(max_results, 3)):
            results.append(SearchResult(
                title=f"【模拟结果{i+1}】{query} — 相关分析报告",
                url=f"https://example.com/report/{i+1}",
                snippet=f"这是关于「{query}」的模拟搜索结果。配置真实搜索 API 后将返回实时数据。",
                source="example.com",
                published_date="2025-01-01",
            ))
        return results


# ── SerpAPI Provider ──────────────────────────────────

class SerpAPIProvider:
    """SerpAPI Google Search provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.warning("[WebSearch] requests not installed, falling back to mock")
            return MockSearchProvider().search(query, max_results)

        try:
            resp = requests.get(
                "https://serpapi.com/search",
                params={
                    "q": query,
                    "api_key": self.api_key,
                    "engine": "google",
                    "num": max_results,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("organic_results", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("title", ""),
                    url=item.get("link", ""),
                    snippet=item.get("snippet", ""),
                    source=item.get("displayed_link", ""),
                    published_date=item.get("date", ""),
                ))
            return results
        except Exception as e:
            logger.error("[WebSearch] SerpAPI error: %s", e)
            return MockSearchProvider().search(query, max_results)


# ── Bing Search Provider ─────────────────────────────

class BingSearchProvider:
    """Bing Web Search API provider"""

    def __init__(self, api_key: str):
        self.api_key = api_key

    def search(self, query: str, max_results: int = 5) -> List[SearchResult]:
        try:
            import requests
        except ImportError:
            logger.warning("[WebSearch] requests not installed, falling back to mock")
            return MockSearchProvider().search(query, max_results)

        try:
            resp = requests.get(
                "https://api.bing.microsoft.com/v7.0/search",
                headers={"Ocp-Apim-Subscription-Key": self.api_key},
                params={"q": query, "count": max_results},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("webPages", {}).get("value", [])[:max_results]:
                results.append(SearchResult(
                    title=item.get("name", ""),
                    url=item.get("url", ""),
                    snippet=item.get("snippet", ""),
                    source=item.get("displayUrl", ""),
                ))
            return results
        except Exception as e:
            logger.error("[WebSearch] Bing API error: %s", e)
            return MockSearchProvider().search(query, max_results)


# ── Provider 工厂 ─────────────────────────────────────

def _get_provider() -> SearchProvider:
    """根据环境变量选择搜索 provider"""
    provider_name = os.getenv("WEB_SEARCH_PROVIDER", "auto").lower()

    if provider_name == "serpapi" or (provider_name == "auto" and os.getenv("SERPAPI_API_KEY")):
        key = os.getenv("SERPAPI_API_KEY", "")
        if key:
            logger.info("[WebSearch] Using SerpAPI provider")
            return SerpAPIProvider(api_key=key)

    if provider_name == "bing" or (provider_name == "auto" and os.getenv("BING_SEARCH_API_KEY")):
        key = os.getenv("BING_SEARCH_API_KEY", "")
        if key:
            logger.info("[WebSearch] Using Bing provider")
            return BingSearchProvider(api_key=key)

    logger.info("[WebSearch] No API key found, using mock provider")
    return MockSearchProvider()


# ── 公共接口 ──────────────────────────────────────────

def search_web(query: str, max_results: int = 5) -> List[dict]:
    """联网搜索入口 — 返回 dict 列表，方便直接注入 prompt

    Args:
        query: 搜索关键词
        max_results: 最大返回结果数

    Returns:
        list[dict]: 搜索结果列表，每个包含 title/url/snippet/source/published_date
    """
    if not query or not query.strip():
        return []

    provider = _get_provider()
    results = provider.search(query.strip(), max_results=max_results)
    return [r.to_dict() for r in results]


def get_provider_info() -> dict:
    """获取当前搜索 provider 信息（用于健康检查/诊断）"""
    provider = _get_provider()
    provider_type = type(provider).__name__
    has_real_key = bool(os.getenv("SERPAPI_API_KEY") or os.getenv("BING_SEARCH_API_KEY"))
    return {
        "provider": provider_type,
        "has_api_key": has_real_key,
        "env_provider": os.getenv("WEB_SEARCH_PROVIDER", "auto"),
    }
