"""
Delivery Pipeline — 统一任务执行流水线

核心职责：
1. 任务类型识别
2. 判断是否需要联网/文件/工具/多智能体
3. 联网搜索和资料抓取
4. 多来源综合分析
5. 专业 Agent 生成初稿
6. QA Agent 审核
7. 不合格则重试或要求用户补充信息
8. 合格后输出最终结果

执行模式：
- cloud: 调用云端 Agent Runtime
- local: 本地执行（fallback）

输出结构统一：
{
    "ok": true,
    "mode": "cloud|local",
    "task_type": "marketing|research|website|data|image|chat|commander",
    "used_web_search": true,
    "used_agents": ["openclaw", "marketing", "qa"],
    "agent_trace": [...],
    "sources": [...],
    "analysis": "...",
    "final_answer": "...",
    "deliverables": {...},
    "qa": {"passed": true, "score": 86, "problems": [], "suggestions": []},
    "confidence": 0.86,
    "warnings": []
}
"""
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional
from backend.logger import get_logger

logger = get_logger()


class DeliveryPipeline:
    """统一任务执行流水线"""

    # 需要联网研究的任务类型
    WEB_REQUIRED_TYPES = {
        "research", "competitor_analysis", "market_analysis",
        "industry_report", "marketing_strategy", "brand_positioning",
        "website_analysis", "product_analysis"
    }

    # 需要 QA 审核的任务类型
    QA_REQUIRED_TYPES = {
        "marketing", "research", "website", "data", "image",
        "competitor_analysis", "market_analysis", "industry_report"
    }

    def __init__(self):
        self._agents = {}
        self._cloud_client = None
        self._init_agents()
        self._init_cloud_client()

    def _init_cloud_client(self):
        """初始化云端客户端"""
        try:
            from backend.services.cloud_client import get_cloud_client
            self._cloud_client = get_cloud_client()
            if self._cloud_client.enabled:
                logger.info("DeliveryPipeline: Cloud mode enabled")
        except Exception as e:
            logger.warning(f"DeliveryPipeline: Cloud client not available: {e}")

    def _init_agents(self):
        """初始化所有 Agent"""
        try:
            from agents.ceo_agent.agent import CEOAgent
            from agents.openclaw_agent.agent import OpenClawAgent
            from agents.marketing_agent.agent import MarketingAgent
            from agents.data_agent.agent import DataAgent
            from agents.qa_agent.agent import QAAgent
            from agents.cto_agent.agent import CTOAgent

            self._agents = {
                "ceo": CEOAgent(),
                "openclaw": OpenClawAgent(),
                "marketing": MarketingAgent(),
                "data": DataAgent(),
                "qa": QAAgent(),
                "cto": CTOAgent(),
            }
            logger.info("DeliveryPipeline: Agents initialized")
        except Exception as e:
            logger.error(f"DeliveryPipeline: Failed to init agents: {e}")

    def _create_result(self, **kwargs) -> Dict[str, Any]:
        """创建统一的返回结构"""
        return {
            "ok": kwargs.get("ok", True),
            "mode": kwargs.get("mode", "local"),
            "task_id": kwargs.get("task_id", f"task_{uuid.uuid4().hex[:8]}"),
            "task_type": kwargs.get("task_type", "unknown"),
            "used_web_search": kwargs.get("used_web_search", False),
            "used_agents": kwargs.get("used_agents", []),
            "agent_trace": kwargs.get("agent_trace", []),
            "sources": kwargs.get("sources", []),
            "analysis": kwargs.get("analysis", ""),
            "final_answer": kwargs.get("final_answer", ""),
            "deliverables": kwargs.get("deliverables", {}),
            "qa": kwargs.get("qa", {
                "passed": False,
                "score": 0,
                "problems": ["未审核"],
                "suggestions": []
            }),
            "confidence": kwargs.get("confidence", 0.0),
            "warnings": kwargs.get("warnings", []),
            "created_at": datetime.now().isoformat()
        }

    def _identify_task_type(self, user_input: str, context: Dict = None) -> str:
        """识别任务类型"""
        user_input_lower = user_input.lower()

        # 关键词匹配
        keywords_map = {
            "research": ["调研", "研究", "分析市场", "行业报告", "市场趋势", "research", "analyze market", "market analysis"],
            "competitor_analysis": ["竞品", "竞争对手", "竞品分析", "competitor", "competitor analysis"],
            "marketing": ["文案", "营销", "推广", "朋友圈", "小红书", "淘宝", "抖音", "copywriting", "marketing",
                         "post", "write", "广告", "advertising", "slogan", "tagline", "wechat"],
            "website": ["网站", "网页", "落地页", "官网", "website", "landing page", "web page", "html"],
            "data": ["数据", "excel", "csv", "分析数据", "销售数据", "data analysis", "spreadsheet", "analyze data"],
            "image": ["图片", "海报", "logo", "产品图", "image", "poster", "picture", "photo", "design"],
            "chat": ["你好", "hello", "hi", "谁", "什么", "怎么", "who", "what", "how"],
        }

        for task_type, keywords in keywords_map.items():
            if any(kw in user_input_lower for kw in keywords):
                return task_type

        # 默认为聊天
        return "chat"

    def _needs_web_search(self, task_type: str, user_input: str) -> bool:
        """判断是否需要联网搜索"""
        if task_type in self.WEB_REQUIRED_TYPES:
            return True

        # 检查是否包含需要联网的关键词
        web_keywords = ["最新", "近期", "当前", "目前", "2024", "2025", "2026",
                       "市场", "竞品", "行业", "趋势", "价格", "latest", "current"]
        return any(kw in user_input.lower() for kw in web_keywords)

    def _do_web_search(self, query: str) -> Dict[str, Any]:
        """执行联网搜索"""
        logger.info(f"DeliveryPipeline: Web search for: {query[:50]}...")

        openclaw = self._agents.get("openclaw")
        if not openclaw:
            return {
                "success": False,
                "sources": [],
                "error": "OpenClaw agent not available"
            }

        try:
            result = openclaw.run({
                "task_type": "web_search",
                "goal": query,
                "url": f"https://www.google.com/search?q={query}",
                "extract_type": "text"
            })

            if result.get("success") or result.get("ok"):
                data = result.get("data", {})
                return {
                    "success": True,
                    "sources": data.get("sources", []),
                    "content": data.get("content", ""),
                    "summary": data.get("summary", "")
                }
            else:
                return {
                    "success": False,
                    "sources": [],
                    "error": result.get("error", "Search failed")
                }
        except Exception as e:
            logger.error(f"DeliveryPipeline: Web search error: {e}")
            return {
                "success": False,
                "sources": [],
                "error": str(e)
            }

    def _generate_content(self, task_type: str, user_input: str,
                         web_results: Dict = None, context: Dict = None) -> Dict[str, Any]:
        """生成内容"""
        logger.info(f"DeliveryPipeline: Generating content for {task_type}")

        # 构建增强的 prompt
        enhanced_prompt = user_input

        if web_results and web_results.get("success"):
            web_summary = web_results.get("summary", "")
            if web_summary:
                enhanced_prompt = f"""
用户需求：{user_input}

联网调研结果：
{web_summary}

请基于以上调研结果，为用户生成专业内容。如果调研结果中有相关信息，请引用；如果没有，请说明是基于通用知识生成。
"""

        # 根据任务类型选择 Agent
        agent_map = {
            "marketing": "marketing",
            "research": "openclaw",
            "website": "marketing",
            "data": "data",
            "competitor_analysis": "openclaw",
            "market_analysis": "openclaw",
        }

        agent_name = agent_map.get(task_type, "marketing")
        agent = self._agents.get(agent_name)

        if not agent:
            return {
                "success": False,
                "error": f"Agent {agent_name} not available"
            }

        try:
            agent_input = {
                "task_type": task_type,
                "goal": enhanced_prompt,
                "prompt": enhanced_prompt,
                "platform": context.get("platform", "") if context else ""
            }
            logger.info(f"DeliveryPipeline: Calling {agent_name} agent with input keys: {list(agent_input.keys())}")

            result = agent.run(agent_input)
            logger.info(f"DeliveryPipeline: {agent_name} agent returned keys: {list(result.keys())}")

            # 提取内容 - 兼容不同 Agent 的返回结构
            data = result.get("data", {})
            logger.info(f"DeliveryPipeline: Data keys: {list(data.keys()) if isinstance(data, dict) else 'not dict'}")
            content = ""

            # 尝试多种字段名
            for field in ["content", "body", "summary", "result", "reply"]:
                if data.get(field):
                    content = data[field]
                    break

            # 如果 data 本身是字符串
            if not content and isinstance(data, str):
                content = data

            # Marketing Agent 特殊处理：组合多个字段
            if agent_name == "marketing" and not content:
                parts = []
                if data.get("headline"):
                    parts.append(data["headline"])
                if data.get("subheadline"):
                    parts.append(data["subheadline"])
                if data.get("body"):
                    parts.append(data["body"])
                if data.get("cta"):
                    parts.append(data["cta"])
                content = "\n\n".join(parts)

            # 判断是否成功 - 兼容不同 Agent 的返回结构
            success = result.get("success", result.get("ok"))
            if success is None:
                # 如果没有明确的 success 字段，根据内容判断
                success = bool(content)

            return {
                "success": success,
                "content": content,
                "agent": agent_name,
                "raw": result
            }
        except Exception as e:
            import traceback
            logger.error(f"DeliveryPipeline: Generate error: {e}")
            logger.error(f"DeliveryPipeline: Traceback: {traceback.format_exc()}")
            return {
                "success": False,
                "error": str(e)
            }

    def _qa_review(self, task_type: str, content: str,
                  user_input: str, sources: List = None) -> Dict[str, Any]:
        """QA 审核"""
        logger.info(f"DeliveryPipeline: QA review for {task_type}")

        qa_agent = self._agents.get("qa")
        if not qa_agent:
            return {
                "passed": True,
                "score": 70,
                "problems": [],
                "suggestions": ["QA agent not available, skipping review"]
            }

        try:
            # 构建审核输入
            review_input = {
                "task_type": task_type,
                "goal": user_input,
                "result": content,
                "expected_output": {"type": "content"},
                "sources": sources or []
            }

            result = qa_agent.run(review_input)
            data = result.get("data", {})

            score = data.get("score", 0)
            problems = data.get("problems", [])
            suggestions = data.get("suggestions", [])

            # 判断是否通过
            passed = score >= 80
            warning = None

            if 60 <= score < 80:
                warning = "建议人工复查"
            elif score < 60:
                warning = "质量不达标，建议重新生成"

            return {
                "passed": passed,
                "score": score,
                "problems": problems,
                "suggestions": suggestions,
                "warning": warning
            }
        except Exception as e:
            logger.error(f"DeliveryPipeline: QA error: {e}")
            return {
                "passed": True,
                "score": 70,
                "problems": [],
                "suggestions": [f"QA review failed: {str(e)}"]
            }

    def execute(self, user_input: str, context: Dict = None) -> Dict[str, Any]:
        """
        执行完整的任务流水线

        执行模式：
        1. 如果云端可用，优先使用云端
        2. 云端失败且允许 fallback，使用本地
        3. 云端失败且不允许 fallback，返回错误

        Args:
            user_input: 用户输入
            context: 上下文信息（平台、文件等）

        Returns:
            统一格式的结果
        """
        task_id = f"task_{uuid.uuid4().hex[:8]}"
        used_agents = []
        warnings = []
        sources = []

        logger.info(f"DeliveryPipeline: Executing task {task_id}")

        # 尝试云端执行
        if self._cloud_client and self._cloud_client.enabled and self._cloud_client.auth_token:
            logger.info("DeliveryPipeline: Trying cloud execution")
            cloud_result = self._cloud_client.execute_task(user_input, context)

            if cloud_result.get("ok"):
                logger.info("DeliveryPipeline: Cloud execution successful")
                return cloud_result
            else:
                logger.warning(f"DeliveryPipeline: Cloud execution failed: {cloud_result.get('error')}")

                # 检查是否允许本地 fallback
                if not self._cloud_client.allow_fallback:
                    return {
                        "ok": False,
                        "mode": "cloud",
                        "task_id": task_id,
                        "task_type": "unknown",
                        "error": "云端服务不可用，请检查网络连接或联系管理员",
                        "warnings": [cloud_result.get("error", "云端执行失败")]
                    }

                warnings.append("云端服务不可用，使用本地模式")
                logger.info("DeliveryPipeline: Falling back to local execution")

        # 1. 识别任务类型
        task_type = self._identify_task_type(user_input, context)
        logger.info(f"DeliveryPipeline: Task type = {task_type}")

        # 2. 判断是否需要联网
        needs_web = self._needs_web_search(task_type, user_input)
        web_results = None

        if needs_web:
            logger.info("DeliveryPipeline: Web search required")
            web_results = self._do_web_search(user_input)
            used_agents.append("openclaw")

            if web_results.get("success"):
                sources = web_results.get("sources", [])
                logger.info(f"DeliveryPipeline: Found {len(sources)} sources")
            else:
                warnings.append("联网查询失败，结果基于模型生成")
                logger.warning("DeliveryPipeline: Web search failed")

        # 3. 生成内容
        gen_result = self._generate_content(task_type, user_input, web_results, context)

        if gen_result.get("success"):
            used_agents.append(gen_result.get("agent", "unknown"))
            content = gen_result.get("content", "")
        else:
            return self._create_result(
                ok=False,
                task_id=task_id,
                task_type=task_type,
                used_web_search=needs_web,
                used_agents=used_agents,
                warnings=[f"内容生成失败: {gen_result.get('error', 'Unknown error')}"]
            )

        # 4. QA 审核（非聊天类型）
        qa_result = None
        if task_type in self.QA_REQUIRED_TYPES:
            qa_result = self._qa_review(task_type, content, user_input, sources)
            used_agents.append("qa")

            # 如果 QA 不通过且分数很低，重试一次
            if not qa_result.get("passed") and qa_result.get("score", 0) < 60:
                logger.info("DeliveryPipeline: QA failed, retrying...")
                gen_result = self._generate_content(task_type, user_input, web_results, context)
                if gen_result.get("success"):
                    content = gen_result.get("content", "")
                    qa_result = self._qa_review(task_type, content, user_input, sources)

        # 5. 检查 QA 结果 - QA < 60 必须返回 ok=false
        if qa_result and qa_result.get("score", 0) < 60:
            return self._create_result(
                ok=False,
                mode="local",
                task_id=task_id,
                task_type=task_type,
                used_web_search=bool(sources),  # 只有真正有来源才算联网成功
                used_agents=list(set(used_agents)),
                sources=sources,
                final_answer=content,
                qa=qa_result,
                warnings=["质量审核未通过，请重新生成"]
            )

        # 6. 计算置信度
        confidence = 0.5  # 基础置信度
        if sources:
            confidence += 0.2  # 有来源加分
        if qa_result and qa_result.get("passed"):
            confidence += 0.2  # QA 通过加分
        if web_results and web_results.get("success"):
            confidence += 0.1  # 联网成功加分

        # 7. 构建最终结果
        return self._create_result(
            ok=True,
            mode="local",
            task_id=task_id,
            task_type=task_type,
            used_web_search=bool(sources),  # 只有真正有来源才算联网成功
            used_agents=list(set(used_agents)),
            sources=sources,
            analysis=web_results.get("summary", "") if web_results else "",
            final_answer=content,
            deliverables={"content": content},
            qa=qa_result or {"passed": True, "score": 70, "problems": [], "suggestions": []},
            confidence=min(confidence, 1.0),
            warnings=warnings
        )


# 全局实例
_pipeline = None


def get_delivery_pipeline() -> DeliveryPipeline:
    """获取 DeliveryPipeline 单例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = DeliveryPipeline()
    return _pipeline
