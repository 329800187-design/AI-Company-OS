"""
搜索服务 — 联网搜索和页面抓取

支持：
- 真实搜索（Bing/SerpAPI）
- Mock 模式（开发测试）
"""
import os
from typing import List, Dict


class SearchService:
    """搜索服务"""

    def __init__(self):
        self.mock_mode = os.getenv("MOCK_SEARCH_MODE", "true").lower() == "true"
        self.bing_api_key = os.getenv("BING_API_KEY", "")

    def search(self, query: str, limit: int = 5) -> dict:
        """搜索"""

        if self.mock_mode:
            return self._mock_search(query, limit)

        if self.bing_api_key:
            return self._bing_search(query, limit)

        return {
            "ok": False,
            "mode": "none",
            "error": "未配置搜索服务",
            "sources": []
        }

    def fetch_page(self, url: str) -> dict:
        """抓取页面内容"""

        if self.mock_mode:
            return self._mock_fetch(url)

        try:
            import httpx
            with httpx.Client(timeout=30, follow_redirects=True) as client:
                response = client.get(url)
                return {
                    "ok": True,
                    "url": url,
                    "status": response.status_code,
                    "content": response.text[:5000],
                    "title": self._extract_title(response.text)
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _mock_search(self, query: str, limit: int) -> dict:
        """Mock 搜索（开发测试用）"""
        mock_results = [
            {
                "title": f"关于「{query}」的市场分析报告",
                "url": "https://example.com/report1",
                "summary": f"这是一份关于{query}的详细市场分析，包含市场规模、增长趋势、主要玩家等信息。"
            },
            {
                "title": f"「{query}」行业趋势 2024",
                "url": "https://example.com/trend1",
                "summary": f"2024年{query}行业最新趋势分析，包括消费者偏好变化、技术创新、竞争格局等。"
            },
            {
                "title": f"如何做好{query}营销",
                "url": "https://example.com/marketing1",
                "summary": f"专业营销指南：如何针对{query}制定有效的营销策略，包括社交媒体、内容营销、KOL合作等。"
            }
        ]

        return {
            "ok": True,
            "mode": "mock",
            "query": query,
            "sources": mock_results[:limit],
            "warning": "当前为模拟搜索模式，结果仅供参考"
        }

    def _bing_search(self, query: str, limit: int) -> dict:
        """Bing 搜索"""
        try:
            import httpx
            with httpx.Client(timeout=30) as client:
                response = client.get(
                    "https://api.bing.microsoft.com/v7.0/search",
                    params={"q": query, "count": limit},
                    headers={"Ocp-Apim-Subscription-Key": self.bing_api_key}
                )

                if response.status_code != 200:
                    return {"ok": False, "error": f"Bing API error: {response.status_code}"}

                data = response.json()
                sources = []

                for item in data.get("webPages", {}).get("value", [])[:limit]:
                    sources.append({
                        "title": item.get("name", ""),
                        "url": item.get("url", ""),
                        "summary": item.get("snippet", "")
                    })

                return {
                    "ok": True,
                    "mode": "live",
                    "query": query,
                    "sources": sources
                }
        except Exception as e:
            return {"ok": False, "error": str(e)}

    def _mock_fetch(self, url: str) -> dict:
        """Mock 页面抓取"""
        return {
            "ok": True,
            "mode": "mock",
            "url": url,
            "content": f"这是从 {url} 抓取的模拟内容。实际部署时会获取真实页面内容。",
            "title": "模拟页面标题"
        }

    def _extract_title(self, html: str) -> str:
        """从 HTML 中提取标题"""
        import re
        match = re.search(r"<title>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
        return match.group(1).strip() if match else ""
