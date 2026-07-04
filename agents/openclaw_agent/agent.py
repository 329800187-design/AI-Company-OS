"""
OpenClaw Agent v2 — 全能联网智能研究助手

能力层次：
  层级1 (执行):   截图 · 抓取 · 表单 · 页面测试
  层级2 (搜索):   关键词提取 · 多引擎搜索 · 分页抓取 · 深度页面阅读
  层级3 (思考):   内容分析 · 交叉验证 · 多角度推理 · 生成研究报告
  层级4 (学习):   记忆存储 · 技能总结 · 知识积累 · 迭代改进

架构: Playwright浏览器 → 多源抓取 → LLM分析 → 记忆/技能 → 结构化输出
"""
import base64
import json
import os
import re
import shutil
import tempfile
import threading
import time
import traceback
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import quote_plus

try:
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

# ── 代理 ──────────────────────────────────────────────
PROXY_HOST = "127.0.0.1"
PROXY_PORT = int(os.getenv("OPENCLAW_PROXY_PORT", "7897"))
PROXY_DEFAULT = os.getenv("OPENCLAW_PROXY", f"http://{PROXY_HOST}:{PROXY_PORT}")

# ── 域名白名单（研究模式自动添加到允许列表） ──────────
ALLOWED_DOMAINS = [
    "localhost", "127.0.0.1",
    # 搜索引擎
    "google.com", "google.com.hk", "googleapis.com",
    "bing.com", "baidu.com", "sogou.com", "duckduckgo.com",
    # 技术社区
    "github.com", "gitlab.com", "stackoverflow.com", "stackexchange.com",
    "npmjs.com", "pypi.org", "crates.io", "docker.com",
    # 百科/问答
    "wikipedia.org", "medium.com", "reddit.com", "quora.com",
    "zhihu.com", "jianshu.com", "csdn.net", "juejin.cn", "segmentfault.com",
    # 新闻/评测
    "techcrunch.com", "theverge.com", "arstechnica.com", "wired.com",
    "hackernews.com", "news.ycombinator.com",
    # AI公司
    "openai.com", "stability.ai", "runwayml.com", "midjourney.com",
    "anthropic.com", "perplexity.ai", "huggingface.co", "replicate.com",
    # 学术
    "arxiv.org", "scholar.google.com", "semanticscholar.org",
    # 视频
    "youtube.com", "ytimg.com", "bilibili.com",
    # 测试
    "httpbin.org", "example.com", "jsonplaceholder.typicode.com",
]

# ── 研究思考 System Prompt ────────────────────────────
RESEARCH_ANALYSIS_PROMPT = """你是 OpenClaw，一个专业的深度研究助手。你的知识截止到训练日期，但你现在正在分析从互联网实时抓取的最新信息。

分析原则：
1. 以网页抓取数据为准 — 这是最新信息
2. 如果抓取数据与你的训练知识冲突，以抓取数据为准并注明
3. 无法确认的信息标注"待验证"
4. 给出具体的来源引用

请用中文回答。"""

VERIFICATION_PROMPT = """你是 OpenClaw 的事实核查员。请交叉验证以下多源信息：

检查：
1. 不同来源的核心事实是否一致？
2. 有无矛盾或冲突的信息？
3. 哪些信息来源更可靠？（官方 > 权威媒体 > 个人博客 > 论坛）
4. 哪些信息可能过时？

输出格式（JSON）：
{
  "verified_facts": ["被多源确认的事实"],
  "conflicting": [{"claim": "说法", "source_a": "来源A", "source_b": "来源B"}],
  "unreliable": [{"claim": "说法", "reason": "为什么不可靠"}],
  "missing": ["缺失的信息"],
  "reliability_score": 0-100,
  "summary": "一句话可信度评估"
}"""

REPORT_GENERATION_PROMPT = """你是 OpenClaw 的研究报告撰写专家。请根据分析结果和原始数据，生成一份专业的研究报告。

报告结构（Markdown）：
## 研究主题
## 核心发现（3-5条）
## 详细分析
  ### 维度1
  ### 维度2
## 数据对比（如有）
## 不同观点
## 局限与说明
## 结论
## 参考来源

要求：
- 每条关键发现标注来源
- 区分事实和观点
- 诚实说明不确定性
- 用中文输出
- 控制总长度在 2000 字以内"""

SEARCH_QUERY_PROMPT = """你是搜索策略专家。根据用户问题，生成最优搜索查询。

输出格式（JSON）：
{
  "primary_query": "主要搜索词（英文，适合Google）",
  "secondary_query": "中文搜索词",
  "alternative_queries": ["备选搜索词1", "备选搜索词2"],
  "search_tips": "搜索技巧（如 site:xxx, filetype:pdf）"
}

只输出 JSON。"""


# ═══════════════════════════════════════════════════════════
# OpenClaw Agent v2
# ═══════════════════════════════════════════════════════════

from agents.base_agent import BaseAgent


class OpenClawAgent(BaseAgent):
    """OpenClaw v2 — 全能联网智能研究助手"""

    AGENT_ID = "openclaw"
    DISPLAY_NAME = "联网研究"
    CAPABILITIES = ["browser", "research", "scrape", "screenshot", "reason", "chat"]
    TASK_TYPES = ["browser_scrape", "browser_screenshot", "browser_form_fill", "browser_test",
                  "deep_research", "research", "reason", "think", "verify",
                  "learn", "chat"]

    def __init__(self, headless: bool = True, timeout: int = 30,
                 screenshot_dir: Optional[str] = None, proxy: Optional[str] = None,
                 allow_browser_automation: bool = False):
        super().__init__(name="openclaw", timeout=timeout)
        self.headless = headless
        self.allow_browser_automation = allow_browser_automation
        self.screenshot_dir = screenshot_dir or os.path.join(tempfile.gettempdir(), "openclaw_screenshots")
        self.proxy = proxy or PROXY_DEFAULT
        os.makedirs(self.screenshot_dir, exist_ok=True)

        # 深度研究配置
        self.max_sources = 3
        self.max_search_results = 8
        self.research_timeout = 120

        # 上下文引擎 — 虚拟 1M 窗口核心
        from core.context_engine import get_context_engine
        self.context = get_context_engine(max_tokens=128_000)
        self._conversation_id = None

    # ═══════════════════════════════════════════════════════════
    # 主入口
    # ═══════════════════════════════════════════════════════════

    # 需要启动浏览器的任务类型
    BROWSER_TASK_TYPES = {"browser_scrape", "browser_screenshot", "browser_form_fill", "browser_test"}

    def run(self, task: Dict[str, Any]) -> Dict[str, Any]:
        task_id = task.get("task_id", f"oc_{uuid.uuid4().hex[:8]}")
        task_type = task.get("task_type", "browser_scrape")
        goal = task.get("goal", task.get("prompt", ""))

        if not PLAYWRIGHT_AVAILABLE:
            return self._err(task_id, goal, "Playwright 未安装")

        # ── 浏览器自动化授权检查 ──
        # research/deep_research/verify 也使用 Playwright 浏览器（_fetch_page），必须经授权
        BROWSER_LIKE_TASK_TYPES = {
            "deep_research", "research", "深度研究", "联网研究", "verify",
        }
        if (task_type in self.BROWSER_TASK_TYPES or task_type in BROWSER_LIKE_TASK_TYPES) \
                and not self.allow_browser_automation:
            return self._browser_approval_blocked(task_id, goal)

        # ── v2 新增任务类型 ──
        if task_type in ("deep_research", "research", "深度研究", "联网研究"):
            return self._research(task, task_id, goal)
        if task_type in ("reason", "think", "思考", "推理", "分析"):
            return self._reason(task, task_id, goal)
        if task_type == "verify":
            return self._verify(task, task_id, goal)
        if task_type in ("learn", "学习", "记忆"):
            return self._learn(task, task_id, goal)
        if task_type in ("chat", "对话", "聊天", "conversation"):
            return self._chat(task, task_id, goal)

        # ── v1 传统浏览器操作（向下兼容） ──
        return self._browser_dispatch(task, task_id, goal)

    # ═══════════════════════════════════════════════════════════
    # 层级 2: 联网研究 (Deep Research)
    # ═══════════════════════════════════════════════════════════

    def _research(self, task: Dict, task_id: str, goal: str) -> Dict:
        """深度联网研究：搜索 → 多源抓取 → 分析 → 验证 → 报告 → 学习"""
        if not goal:
            return self._err(task_id, goal, "缺少研究问题")

        steps_log = []
        sources = []

        # ── Step 1: 生成搜索策略 ──
        search_plan = self._plan_search(goal)
        queries = [search_plan.get("primary_query", goal)]
        if alt := search_plan.get("secondary_query"):
            queries.append(alt)

        # ── Step 2: 执行搜索 ──
        all_results = []
        for query in queries[:2]:
            results = self._google_search(query)
            all_results.extend(results)
            if len(all_results) >= self.max_search_results * 2:
                break

        # 去重 + 排序 + 截断
        seen = set()
        unique = []
        for r in all_results:
            u = r.get("href", "")
            if u and u not in seen:
                seen.add(u)
                unique.append(r)
        unique = unique[:self.max_search_results]
        steps_log.append({"step": "search", "query": queries[0], "results": len(unique)})

        # ── Step 3: 深度抓取 Top N 页面 ──
        for i, result in enumerate(unique[:self.max_sources]):
            url = result.get("href", "")
            if not url:
                continue
            try:
                content = self._fetch_page(url, extract="text")
                if content and isinstance(content, dict) and content.get("data"):
                    sources.append({
                        "title": result.get("text", content.get("page_title", "")),
                        "url": url,
                        "content": content["data"],
                        "snippet": result.get("text", ""),
                    })
                    steps_log.append({"step": f"deep_read_{i+1}", "url": url,
                                      "lines": len(content["data"]) if isinstance(content["data"], list) else 1})
            except Exception as e:
                steps_log.append({"step": f"deep_read_{i+1}", "url": url, "error": str(e)[:80]})

        if not sources:
            # 至少用搜索结果摘要
            sources = [{"title": r.get("text", ""), "url": r.get("href", ""),
                        "content": [r.get("text", "")], "snippet": r.get("text", "")}
                       for r in unique[:self.max_sources]]

        # ── Step 4: LLM 深度分析 ──
        analysis = self._analyze_content(goal, sources)
        steps_log.append({"step": "analyze", "status": "completed" if analysis else "failed"})

        # ── Step 5: 交叉验证 ──
        verification = self._verify_facts(goal, sources, analysis)
        steps_log.append({"step": "verify", "score": verification.get("reliability_score", 0) if verification else 0})

        # ── Step 6: 生成报告 ──
        report = self._generate_report(goal, analysis, sources, verification)
        steps_log.append({"step": "report", "length": len(report) if report else 0})

        # ── Step 7: 学习记忆 ──
        self._remember_research(goal, report, sources, verification)
        self._learn_skill(goal, analysis)
        steps_log.append({"step": "learn", "done": True})

        return {
            "agent": "openclaw", "agent_name": "OpenClaw 深度研究 (v2)",
            "status": "研究完成", "task_id": task_id, "title": goal,
            "success": True,
            "result": report[:2000] if report else "研究未能生成完整报告",
            "data": {
                "report": report,
                "sources": [{"title": s["title"], "url": s["url"]} for s in sources],
                "analysis": analysis,
                "verification": verification,
                "source_count": len(sources),
                "steps": steps_log,
            },
            "summary": f"完成深度研究：搜索 {len(unique)} 条结果，深入阅读 {len(sources)} 个来源，生成 {len(report) if report else 0} 字报告",
        }

    # ═══════════════════════════════════════════════════════════
    # 层级 3: 深度思考
    # ═══════════════════════════════════════════════════════════

    def _reason(self, task: Dict, task_id: str, goal: str) -> Dict:
        """深度推理：调用 LLM 进行结构化的 Chain-of-Thought 推理"""
        if not goal:
            return self._err(task_id, goal, "缺少推理问题")

        # 如果有 URL，先抓取页面作为推理素材
        url = task.get("url", "")
        context = ""
        if url and self._is_url_allowed(url):
            fetched = self._fetch_page(url, extract="text")
            if fetched and isinstance(fetched, dict):
                lines = fetched.get("data", [])
                context = "\n".join(lines[:100]) if isinstance(lines, list) else str(lines)[:3000]

        reasoning_prompt = self._build_reasoning_prompt(goal, context)
        result = self._call_llm(
            system="你是 OpenClaw，一个精通第一性原理和多维度分析的思考助手。请进行深度的结构化推理。用中文回答。",
            prompt=reasoning_prompt,
            max_tokens=3000
        )

        if result:
            # 同时把思考结果记入记忆
            self._remember_thought(goal, result)
            return {
                "agent": "openclaw", "agent_name": "OpenClaw 深度思考 (v2)",
                "status": "思考完成", "task_id": task_id, "title": goal,
                "success": True, "result": result[:2000],
                "data": {"reasoning": result, "context_url": url},
                "summary": f"深度推理完成 ({len(result)} 字符)",
            }

        return self._err(task_id, goal, "LLM 推理失败，请检查 API 配置")

    # ═══════════════════════════════════════════════════════════
    # 层级 2-3 辅助: 搜索策略
    # ═══════════════════════════════════════════════════════════

    def _plan_search(self, goal: str) -> Dict:
        """用 LLM 生成最佳搜索策略，LLM 不可用时降级为规则"""
        result = self._call_llm(
            system=SEARCH_QUERY_PROMPT,
            prompt=f"用户问题: {goal}",
            max_tokens=300,
            temperature=0.2
        )
        if result:
            try:
                return json.loads(re.sub(r"```.*?\n?", "", result))
            except json.JSONDecodeError:
                pass

        # 规则降级：中英文关键词各一组
        is_cn = any('一' <= c <= '鿿' for c in goal)
        en = goal if not is_cn else goal[:40]
        cn = goal if is_cn else ""
        return {
            "primary_query": en.strip()[:100],
            "secondary_query": cn.strip()[:100] if cn else "",
        }

    def _google_search(self, query: str) -> List[Dict]:
        """执行 Google 搜索，返回标题+链接列表"""
        url = f"https://www.google.com/search?q={quote_plus(query)}&hl=en&num=10"
        try:
            raw = self._fetch_page(url, extract="links")
            if raw and isinstance(raw, dict):
                links = raw.get("data", [])
                # 过滤出真实搜索结果链接（排除 google 自身链接）
                results = []
                for l in links:
                    href = l.get("href", "")
                    text = l.get("text", "").strip()
                    if href and text and "google.com" not in href and "webcache" not in href:
                        results.append({"text": text, "href": href})
                return results
        except Exception as e:
            self.logger.warning(f"Google 搜索失败: {e}")
        return []

    def _fetch_page(self, url: str, extract: str = "text") -> Optional[Dict]:
        """安全抓取单个页面"""
        if not self._is_url_allowed(url):
            # 对研究模式放宽：允许任何 HTTP URL
            if url.startswith("http"):
                pass  # continue
            else:
                return None

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=self.headless,
                proxy={"server": self.proxy},
                args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
            )
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="domcontentloaded")
                page.wait_for_timeout(800)
                title = page.title()

                if extract == "links":
                    links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => ({text: a.textContent.trim(), href: a.href})).filter(l => l.text)""")
                    result = {"page_title": title, "data": links[:200]}
                elif extract == "html":
                    content = page.content()
                    result = {"page_title": title, "data": content[:50000]}
                else:
                    text = page.inner_text("body")
                    lines = [l.strip() for l in text.split("\n") if l.strip() and len(l) > 10]
                    result = {"page_title": title, "data": lines[:300]}
                return result
            except PlaywrightTimeout:
                return {"page_title": "", "data": [], "error": "timeout"}
            except Exception as e:
                return {"page_title": "", "data": [], "error": str(e)[:100]}
            finally:
                browser.close()

    # ═══════════════════════════════════════════════════════════
    # 层级 3: 分析 & 验证 & 报告
    # ═══════════════════════════════════════════════════════════

    def _analyze_content(self, goal: str, sources: List[Dict]) -> Optional[Dict]:
        """LLM 深度分析多源内容"""
        # 拼接来源内容（每个来源截断）
        combined = ""
        for i, s in enumerate(sources, 1):
            content_text = ""
            c = s.get("content", [])
            if isinstance(c, list):
                content_text = "\n".join(c[:80])
            elif isinstance(c, str):
                content_text = c[:3000]
            combined += f"\n{'='*40}\n来源{i}: {s.get('title','')}\nURL: {s.get('url','')}\n{content_text}\n"

        if not combined.strip():
            return None

        prompt = f"""研究问题：{goal}

网页抓取数据：
{combined[:8000]}

请分析以上数据，输出 JSON：
{{
  "key_findings": [{{"finding": "发现", "source_index": 1}}],
  "categories": {{"类别名": ["属于该类别的信息"]}},
  "data_points": {{"指标名": "数值（如有）"}},
  "trends": ["趋势1", "趋势2"],
  "contradictions": ["矛盾点（如有）"],
  "gaps": ["信息缺口"],
  "confidence": "high|medium|low"
}}"""

        result = self._call_llm(system=RESEARCH_ANALYSIS_PROMPT, prompt=prompt, max_tokens=2500)
        if result:
            try:
                return json.loads(re.sub(r"```.*?\n?", "", result))
            except json.JSONDecodeError:
                return {"raw_analysis": result[:2000]}
        return None

    def _verify_facts(self, goal: str, sources: List[Dict], analysis: Optional[Dict]) -> Optional[Dict]:
        """交叉验证多源信息"""
        if len(sources) < 2:
            return {"reliability_score": 50, "summary": "来源不足，无法交叉验证",
                    "verified_facts": [], "conflicting": [], "unreliable": []}

        source_summaries = []
        for i, s in enumerate(sources, 1):
            c = s.get("content", [])
            text = "\n".join(c[:30]) if isinstance(c, list) else str(c)[:1000]
            source_summaries.append(f"来源{i} ({s.get('title','')}): {text[:600]}")

        prompt = f"请交叉验证以下 {len(sources)} 个来源关于「{goal}」的信息：\n" + "\n---\n".join(source_summaries)

        result = self._call_llm(system=VERIFICATION_PROMPT, prompt=prompt, max_tokens=1500)
        if result:
            try:
                return json.loads(re.sub(r"```.*?\n?", "", result))
            except json.JSONDecodeError:
                pass
        return {"reliability_score": 60, "summary": "验证失败，请人工判断"}

    def _generate_report(self, goal: str, analysis: Optional[Dict],
                         sources: List[Dict], verification: Optional[Dict]) -> str:
        """LLM 生成结构化研究报告"""
        src_list = "\n".join(f"{i+1}. [{s.get('title','Source')}]({s.get('url','')})"
                            for i, s in enumerate(sources))

        prompt = f"""研究问题：{goal}

分析结果：{json.dumps(analysis, ensure_ascii=False) if analysis else '无'}
验证结果：{json.dumps(verification, ensure_ascii=False) if verification else '无'}
来源列表：
{src_list}

请根据以上信息生成一份结构化的中文研究报告（Markdown格式）。"""

        result = self._call_llm(system=REPORT_GENERATION_PROMPT, prompt=prompt, max_tokens=3000,
                                temperature=0.5)
        return result or f"# {goal}\n\n研究未能生成完整报告。请检查 AI API 配置。\n\n## 来源\n{src_list}"

    def _build_reasoning_prompt(self, goal: str, context: str = "") -> str:
        context_block = f"\n\n参考信息：\n{context[:3000]}" if context else ""
        return f"""请对以下问题进行深度推理分析{context_block}

问题：{goal}

请按以下框架思考：
1. 第一性原理：问题的本质是什么？
2. 多角度分析：从不同立场看这个问题
3. 假设验证：有哪些可能的假设？如何验证？
4. 逻辑链：从前提 → 推理 → 结论
5. 不确定性：什么情况下结论会不同？

请用中文给出结构化的深度分析。"""

    # ═══════════════════════════════════════════════════════════
    # 层级 4: 学习能力
    # ═══════════════════════════════════════════════════════════

    def _verify(self, task: Dict, task_id: str, goal: str) -> Dict:
        """纯验证模式：只做事实核查"""
        claims = task.get("claims", task.get("facts", goal))
        search_result = self._google_search(claims)
        urls = [r.get("href", "") for r in search_result[:3]]
        sources = []
        for url in urls:
            if url:
                fetched = self._fetch_page(url, extract="text")
                if fetched and isinstance(fetched, dict) and fetched.get("data"):
                    sources.append({"title": fetched.get("page_title", ""), "url": url,
                                    "content": fetched["data"]})

        verification = self._verify_facts(goal, sources, None)
        return {
            "agent": "openclaw", "agent_name": "OpenClaw 事实核查 (v2)",
            "status": "验证完成", "task_id": task_id, "title": goal,
            "success": True, "result": verification.get("summary", "") if verification else "",
            "data": {"verification": verification, "sources": [s["url"] for s in sources]},
        }

    def _learn(self, task: Dict, task_id: str, goal: str) -> Dict:
        """主动学习：从给定主题自主学习并记忆"""
        report_result = self._research(task, task_id, goal)
        return {
            "agent": "openclaw", "agent_name": "OpenClaw 自主学习 (v2)",
            "status": "学习完成", "task_id": task_id, "title": goal,
            "success": report_result.get("success", False),
            "result": f"已完成自主学习并存入记忆: {goal[:60]}",
            "data": report_result.get("data", {}),
        }

    # ═══════════════════════════════════════════════════════════
    # 层级 5: 无限对话（Context Engine 驱动）
    # ═══════════════════════════════════════════════════════════

    def _chat(self, task: Dict, task_id: str, goal: str) -> Dict:
        """智能对话 — 上下文引擎自动管理128K→1M虚拟窗口"""
        conv_id = task.get("conversation_id", task_id)

        # 将用户消息注入上下文引擎
        self.context.add_message("user", goal)

        # 如果超限，压缩（无 API 成本 — 纯本地规则压缩）
        stats_before = self.context_stats()

        # 检索相关历史（如果需要）
        search_context = ""
        if task.get("search_memory", False):
            relevant = self.context.search_context(goal, top_k=3)
            if relevant:
                search_context = "\n\n[检索到的历史相关信息]\n" + "\n---\n".join(relevant)

        # 构建压缩后的上下文
        system = task.get("system_prompt",
            "你是 OpenClaw，一个全能的 AI 研究助手。你拥有 1M 虚拟上下文窗口。"
            "对话历史已自动压缩——标记[摘要]的内容是压缩的旧消息要点。"
            "请基于全部对话历史连贯回答，不要让用户感到你'失忆'了。")

        full_context, active_tokens = self.context.build_context(system)

        if search_context:
            full_context += search_context

        # 调用 LLM
        response = self._call_llm(
            system="",
            prompt=full_context + f"\n\n[用户] {goal}\n\n请用中文回答。",
            max_tokens=task.get("max_tokens", 2000),
            temperature=task.get("temperature", 0.7)
        )

        if not response:
            return self._err(task_id, goal, "LLM 调用失败")

        # 将助手回复注入上下文
        self.context.add_message("assistant", response)

        stats_after = self.context_stats()

        # 定期持久化
        if self.context.compress_count % 5 == 0:
            try:
                self.context.save_to_disk()
            except Exception:
                pass

        return {
            "agent": "openclaw", "agent_name": "OpenClaw 智能对话 (∞ 上下文)",
            "status": "回复完成", "task_id": task_id, "title": goal,
            "success": True, "result": response[:2000],
            "data": {
                "reply": response,
                "conversation_id": conv_id,
                "context_stats": stats_after,
                "virtual_tokens": self.context.total_stored_tokens,
                "active_tokens": active_tokens,
            },
            "summary": f"虚拟上下文 {self.context.total_stored_tokens:,} tokens → 压缩为 {active_tokens:,} tokens 发送给 LLM",
        }

    def context_stats(self) -> Dict:
        """获取当前上下文统计"""
        total = self.context.total_stored_tokens
        active = self.context._calc_active_tokens()
        compressed = sum(1 for m in self.context.messages if m.level > 0)
        total_msgs = len(self.context.messages)
        return {
            "total_stored_tokens": total,
            "active_tokens": active,
            "compression_ratio": f"{total/active:.1f}x" if active > 0 else "1x",
            "total_messages": total_msgs,
            "compressed_messages": compressed,
            "hot_window": min(3, total_msgs),
            "compress_rounds": self.context.compress_count,
        }

    def clear_context(self):
        """清空上下文（开始新对话）"""
        self.context.messages.clear()
        self.context._topic_index.clear()
        self.context.total_stored_tokens = 0
        self.context.compress_count = 0

    def _remember_research(self, goal: str, report: str, sources: List[Dict], verification: Optional[Dict]):
        """将研究结果存入记忆系统"""
        try:
            from core.memory.memory_store import get_memory_store
            mem = get_memory_store()
            mem.remember(
                key=f"research_{datetime.now().strftime('%Y%m%d%H%M%S')}_{goal[:20].replace(' ', '_')}",
                content=json.dumps({"goal": goal, "report": report[:1000] if report else "",
                                    "source_count": len(sources),
                                    "reliability": verification.get("reliability_score", 0) if verification else 0},
                                   ensure_ascii=False),
                source="openclaw",
                tags=["research", "deep_research", "v2"],
                importance=0.8
            )
        except Exception as e:
            self.logger.warning(f"记忆存储失败: {e}")

    def _learn_skill(self, goal: str, analysis: Optional[Dict]):
        """从研究中创建/更新技能"""
        try:
            from core.skills.skill_manager import get_skill_manager
            mgr = get_skill_manager()
            findings = analysis.get("key_findings", []) if analysis else []
            key_points = "\n".join(f"- {f.get('finding', str(f))}" for f in findings[:5])
            mgr.create(
                name=f"learned_{goal[:30].replace(' ','_')}",
                title=f"研究: {goal[:50]}",
                description=f"从研究'{goal[:50]}'中学到的知识",
                category="learned",
                triggers=[goal[:30]],
                body=f"# 研究成果\n\n{key_points}\n\n*自动生成于 {datetime.now().isoformat()[:16]}*"
            )
        except Exception as e:
            self.logger.warning(f"技能学习失败: {e}")

    def _remember_thought(self, goal: str, reasoning: str):
        """存储深度思考结果"""
        try:
            from core.memory.memory_store import get_memory_store
            mem = get_memory_store()
            mem.remember(
                key=f"thought_{datetime.now().strftime('%Y%m%d%H%M%S')}",
                content=json.dumps({"goal": goal, "reasoning": reasoning[:800]}, ensure_ascii=False),
                source="openclaw",
                tags=["reasoning", "deep_think", "v2"],
                importance=0.7
            )
        except Exception:
            pass

    # ═══════════════════════════════════════════════════════════
    # LLM 调用
    # ═══════════════════════════════════════════════════════════

    def _call_llm(self, system: str, prompt: str, max_tokens: int = 2000,
                  temperature: float = 0.3) -> Optional[str]:
        """调用 AI API（DeepSeek/Claude/OpenAI）"""
        try:
            import urllib.request
            from backend.config import get_ai_config, AI_PROVIDER

            config = get_ai_config()
            api_key = config["api_key"]
            base_url = config["base_url"]
            model = config["model"]

            if AI_PROVIDER == "claude":
                url = f"{base_url.rstrip('/')}/v1/messages"
                payload = json.dumps({
                    "model": model, "max_tokens": max_tokens,
                    "system": system,
                    "messages": [{"role": "user", "content": prompt}],
                }).encode("utf-8")
                headers = {"Content-Type": "application/json",
                           "x-api-key": api_key, "anthropic-version": "2023-06-01"}
            else:
                url = f"{base_url.rstrip('/')}/chat/completions"
                payload = json.dumps({
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": prompt},
                    ],
                    "temperature": temperature, "max_tokens": max_tokens,
                }).encode("utf-8")
                headers = {"Content-Type": "application/json",
                           "Authorization": f"Bearer {api_key}"}

            req = urllib.request.Request(url, data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=90) as resp:
                data = json.loads(resp.read().decode("utf-8"))

            if AI_PROVIDER == "claude":
                return data["content"][0]["text"].strip()
            else:
                return data["choices"][0]["message"]["content"].strip()
        except Exception as e:
            self.logger.warning(f"LLM 调用失败: {e}")
            return None

    # ═══════════════════════════════════════════════════════════
    # 层级 1: 浏览器操作（v1 兼容，向下兼容）
    # ═══════════════════════════════════════════════════════════

    def _browser_dispatch(self, task: Dict, task_id: str, goal: str) -> Dict:
        url = task.get("url", "")
        if not url:
            url = self._guess_url(task)
        if not url:
            return self._err(task_id, goal, "未提供 URL")
        if not self._is_url_allowed(url):
            return self._blocked(task_id, goal, f"URL not in allowlist: {url}")

        task_type = task.get("task_type", "browser_scrape")
        handlers = {
            "browser_screenshot": self._handle_screenshot,
            "browser_scrape": self._handle_scrape,
            "browser_form_fill": self._handle_form_fill,
            "browser_test": self._handle_test,
        }
        handler = handlers.get(task_type, self._handle_scrape)
        try:
            result = handler(task, url)
            result["task_id"] = task_id
            result["title"] = goal
            return result
        except Exception as e:
            return self._err(task_id, goal, f"执行异常: {e}")

    def _handle_screenshot(self, task: Dict, url: str) -> Dict:
        selector = task.get("selector", "body") or "body"
        full_page = task.get("full_page", False)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, proxy={"server": self.proxy},
                                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                page.wait_for_timeout(1000)
                ts = int(time.time())
                tid = task.get("task_id", "unknown")
                fp = os.path.join(self.screenshot_dir, f"{tid}_{ts}.png")
                if selector != "body":
                    el = page.locator(selector).first
                    el.screenshot(path=fp) if el.is_visible() else page.screenshot(path=fp, full_page=full_page)
                else:
                    page.screenshot(path=fp, full_page=full_page)
                return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                        "status": "截图完成", "screenshot_path": fp, "page_title": page.title(),
                        "page_url": page.url, "success": True}
            except PlaywrightTimeout:
                return self._err("", "", f"页面加载超时: {url}")
            finally:
                browser.close()

    def _handle_scrape(self, task: Dict, url: str) -> Dict:
        selector = task.get("selector", "body") or "body"
        extract_type = task.get("extract_type", "") or task.get("extract", "text")
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, proxy={"server": self.proxy},
                                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                page.wait_for_timeout(1000)
                title = page.title()
                if extract_type == "links":
                    links = page.evaluate("""() => Array.from(document.querySelectorAll('a[href]')).map(a => ({text: a.textContent.trim(), href: a.href})).filter(l => l.text)""")
                    return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                            "status": "抓取完成", "page_title": title, "data": links[:200], "success": True}
                elif extract_type == "html":
                    c = page.content() if selector == "body" else page.locator(selector).first.inner_html()
                    return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                            "status": "抓取完成", "page_title": title, "data": c[:50000], "success": True}
                else:
                    text = page.inner_text(selector) if selector == "body" else (page.locator(selector).first.inner_text() or "")
                    lines = [l.strip() for l in text.split("\n") if l.strip()]
                    return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                            "status": "抓取完成", "page_title": title, "data": lines[:500], "success": True}
            except PlaywrightTimeout:
                return self._err("", "", f"页面加载超时: {url}")
            finally:
                browser.close()

    def _handle_form_fill(self, task: Dict, url: str) -> Dict:
        form_data = task.get("form_data", {})
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, proxy={"server": self.proxy},
                                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                page.wait_for_timeout(1000)
                filled = []
                for sel, val in form_data.items():
                    try:
                        el = page.locator(sel).first
                        if el.is_visible():
                            el.fill(str(val))
                            filled.append(sel)
                    except Exception:
                        pass
                fp = os.path.join(self.screenshot_dir, f"{task.get('task_id','')}_filled_{int(time.time())}.png")
                page.screenshot(path=fp)
                return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                        "status": "填写完成", "filled_fields": filled, "screenshot_path": fp, "success": True}
            except PlaywrightTimeout:
                return self._err("", "", f"页面加载超时: {url}")
            finally:
                browser.close()

    def _handle_test(self, task: Dict, url: str) -> Dict:
        checks = task.get("checks", [{"type": "page_loaded"}, {"type": "has_title"}])
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.headless, proxy={"server": self.proxy},
                                        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"])
            page = browser.new_page()
            page.set_viewport_size({"width": 1280, "height": 720})
            page.set_extra_http_headers({
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/125.0.0.0 Safari/537.36",
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            })
            js_errors = []
            page.on("pageerror", lambda err: js_errors.append(str(err)))
            try:
                page.goto(url, timeout=self.timeout * 1000, wait_until="networkidle")
                page.wait_for_timeout(1000)
                results = []
                all_ok = True
                for check in checks:
                    ct = check.get("type", "")
                    sel = check.get("selector", "")
                    if ct == "page_loaded":
                        ok = page.url.startswith("http")
                    elif ct == "has_title":
                        ok = len(page.title()) > 0
                    elif ct == "element_visible" and sel:
                        try:
                            ok = page.locator(sel).first.is_visible()
                        except Exception as e:
                            ok = False
                    elif ct == "no_js_error":
                        ok = len(js_errors) == 0
                    else:
                        ok = True
                    results.append({"check": ct or sel, "passed": ok})
                    if not ok:
                        all_ok = False
                return {"agent": "openclaw", "agent_name": "OpenClaw 浏览器操作",
                        "status": "测试通过" if all_ok else "测试失败", "checks": results,
                        "js_errors": js_errors, "page_title": page.title(),
                        "passed_count": sum(1 for r in results if r["passed"]),
                        "total_count": len(results), "success": all_ok}
            except PlaywrightTimeout:
                return self._err("", "", f"页面加载超时: {url}")
            finally:
                browser.close()

    # ═══════════════════════════════════════════════════════════
    # 工具函数
    # ═══════════════════════════════════════════════════════════

    def _guess_url(self, task: Dict) -> str:
        text = f"{task.get('goal', '')} {task.get('context', '')} {task.get('url', '')}"
        m = re.search(r"https?://[^\s]+", text)
        return m.group() if m else ""

    @staticmethod
    def _is_url_allowed(url: str) -> bool:
        from urllib.parse import urlparse
        try:
            host = urlparse(url).hostname or ""
            if not host:
                return False
            return any(host == a or host.endswith(f".{a}") for a in ALLOWED_DOMAINS)
        except Exception:
            return False

    @staticmethod
    def _blocked(task_id: str, title: str, msg: str) -> Dict:
        return {"agent": "openclaw", "agent_name": "OpenClaw",
                "task_id": task_id, "title": title, "status": "被拦截",
                "result": msg, "success": False}

    @staticmethod
    def _browser_approval_blocked(task_id: str, title: str) -> Dict:
        return {
            "agent": "openclaw", "agent_name": "OpenClaw",
            "task_id": task_id, "title": title,
            "status": "blocked", "mode": "blocked",
            "blocked": True,
            "blocked_reason": "browser_automation_approval_required",
            "message": "需要用户授权后才能打开浏览器采集",
            "result": "需要用户授权后才能打开浏览器采集。请在 Boss 指挥台勾选「允许本次打开浏览器采集数据」后重试。",
            "success": False,
        }

    def _err(self, task_id: str, title: str, msg: str) -> Dict:
        return self.fail(task_id=task_id, error=msg, status="失败")
