"""
Agent Runtime — 多 Agent 协作执行引擎

流程：
1. identify_task_type() - 识别任务类型
2. decide_required_capabilities() - 决定需要的能力
3. run_research_if_needed() - 按需联网搜索
4. run_specialist_agent() - 执行专业 Agent
5. run_qa() - QA 审核
6. package_delivery() - 打包交付结果
"""
import uuid
from datetime import datetime
from typing import List, Dict, Optional


class AgentRuntime:
    """Agent 运行时"""

    def __init__(self, model_client, search_service, qa_service):
        self.model_client = model_client
        self.search_service = search_service
        self.qa_service = qa_service

    def execute(self, message: str, context: dict, user_id: str) -> dict:
        """执行完整的 Agent 流水线"""

        task_id = f"task_{uuid.uuid4().hex[:8]}"
        agent_trace = []
        warnings = []
        sources = []
        used_agents = []

        # 1. 识别任务类型
        task_type = self._identify_task_type(message, context)
        agent_trace.append({
            "agent": "System",
            "action": "任务识别",
            "status": "done",
            "summary": f"识别为 {task_type} 类型任务"
        })

        # 2. 决定需要的能力
        capabilities = self._decide_required_capabilities(task_type, message)
        agent_trace.append({
            "agent": "System",
            "action": "能力规划",
            "status": "done",
            "summary": f"需要: {', '.join(capabilities)}"
        })

        # 3. 联网搜索（如果需要）
        used_web_search = False
        if "search" in capabilities:
            search_result = self._run_research(message, task_type)
            used_web_search = search_result["ok"]
            sources = search_result.get("sources", [])

            agent_trace.append({
                "agent": "ResearchAgent",
                "action": "联网搜索",
                "status": "done" if search_result["ok"] else "failed",
                "summary": f"找到 {len(sources)} 个来源" if search_result["ok"] else search_result.get("error", "搜索失败")
            })

            if not search_result["ok"]:
                warnings.append("联网搜索失败，结果基于模型生成")

            if search_result.get("warning"):
                warnings.append(search_result["warning"])

            used_agents.append("ResearchAgent")

        # 4. 执行专业 Agent
        specialist_result = self._run_specialist_agent(task_type, message, sources, context)
        used_agents.append(specialist_result.get("agent", "SpecialistAgent"))

        agent_trace.append({
            "agent": specialist_result.get("agent", "SpecialistAgent"),
            "action": "生成内容",
            "status": "done" if specialist_result["ok"] else "failed",
            "summary": specialist_result.get("summary", "")
        })

        if not specialist_result["ok"]:
            return {
                "ok": False,
                "mode": "cloud",
                "task_id": task_id,
                "task_type": task_type,
                "final_answer": "",
                "deliverables": {},
                "used_agents": used_agents,
                "agent_trace": agent_trace,
                "used_web_search": used_web_search,
                "sources": sources,
                "qa": {},
                "confidence": 0.0,
                "usage": {},
                "warnings": warnings + [specialist_result.get("error", "内容生成失败")]
            }

        final_answer = specialist_result.get("content", "")
        deliverables = specialist_result.get("deliverables", {})

        # 5. QA 审核（非 chat 类型）
        qa_result = None
        if task_type != "chat":
            qa_result = self.qa_service.review(
                task_type=task_type,
                content=final_answer,
                sources=sources,
                goal=message
            )
            used_agents.append("QAAgent")

            agent_trace.append({
                "agent": "QAAgent",
                "action": "质量审核",
                "status": "done",
                "summary": f"得分 {qa_result['score']}，{qa_result['status']}"
            })

            # QA 不通过时的处理
            if not qa_result["passed"]:
                if qa_result["score"] < 60:
                    return {
                        "ok": False,
                        "mode": "cloud",
                        "task_id": task_id,
                        "task_type": task_type,
                        "final_answer": final_answer,
                        "deliverables": deliverables,
                        "used_agents": used_agents,
                        "agent_trace": agent_trace,
                        "used_web_search": used_web_search,
                        "sources": sources,
                        "qa": qa_result,
                        "confidence": 0.0,
                        "usage": {},
                        "warnings": warnings + ["质量审核未通过，请重新生成"]
                    }
                else:
                    warnings.append("建议人工复查")

        # 6. 计算置信度
        confidence = self._calculate_confidence(
            task_type=task_type,
            has_sources=len(sources) > 0,
            qa_passed=qa_result["passed"] if qa_result else True,
            qa_score=qa_result["score"] if qa_result else 100,
            used_web_search=used_web_search
        )

        # 7. 打包返回
        return {
            "ok": True,
            "mode": "cloud",
            "task_id": task_id,
            "task_type": task_type,
            "final_answer": final_answer,
            "deliverables": deliverables,
            "used_agents": list(set(used_agents)),
            "agent_trace": agent_trace,
            "used_web_search": used_web_search,
            "sources": sources,
            "qa": qa_result or {"passed": True, "score": 100, "status": "passed", "problems": [], "suggestions": []},
            "confidence": confidence,
            "usage": {},
            "warnings": warnings
        }

    def _identify_task_type(self, message: str, context: dict) -> str:
        """识别任务类型"""
        message_lower = message.lower()

        # 关键词映射
        keywords = {
            "marketing": ["文案", "营销", "推广", "朋友圈", "小红书", "淘宝", "抖音", "广告", "slogan",
                         "post", "write", "copywriting", "marketing", "wechat"],
            "research": ["调研", "研究", "分析市场", "行业报告", "竞品", "市场趋势", "research",
                        "analyze", "market analysis", "competitor"],
            "website": ["网站", "网页", "落地页", "官网", "html", "website", "landing page"],
            "data": ["数据", "excel", "csv", "分析数据", "data", "spreadsheet"],
            "image": ["图片", "海报", "logo", "产品图", "image", "poster", "photo"],
        }

        for task_type, kws in keywords.items():
            if any(kw in message_lower for kw in kws):
                return task_type

        return "chat"

    def _decide_required_capabilities(self, task_type: str, message: str) -> List[str]:
        """决定需要的能力"""
        capabilities = ["model"]  # 所有任务都需要模型

        # 需要搜索的任务类型
        search_types = {"research"}

        # 可能需要搜索的任务类型（看关键词）
        maybe_search_types = {"marketing"}

        if task_type in search_types:
            capabilities.append("search")
        elif task_type in maybe_search_types:
            # 检查是否包含需要搜索的关键词
            search_keywords = ["市场", "竞品", "趋势", "价格", "最新", "当前",
                             "market", "competitor", "trend", "price", "latest"]
            if any(kw in message.lower() for kw in search_keywords):
                capabilities.append("search")

        return capabilities

    def _run_research(self, query: str, task_type: str) -> dict:
        """执行联网搜索"""
        return self.search_service.search(query, limit=5)

    def _run_specialist_agent(self, task_type: str, message: str,
                              sources: List[dict], context: dict) -> dict:
        """执行专业 Agent"""

        # 构建增强的 prompt
        enhanced_prompt = message

        if sources:
            sources_text = "\n".join([f"- {s['title']}: {s['summary']}" for s in sources[:3]])
            enhanced_prompt = f"""
用户需求：{message}

参考资料：
{sources_text}

请基于以上资料，为用户生成专业内容。如果资料中有相关信息，请引用；如果没有，请说明是基于通用知识生成。
"""

        # 根据任务类型选择系统 prompt
        system_prompts = {
            "marketing": """你是一个专业的营销文案专家。请根据用户需求生成高质量的营销文案。
要求：
1. 文案要吸引人，有感染力
2. 适合目标平台的风格
3. 包含明确的行动号召
4. 如果有参考资料，请引用""",
            "website": """你是一个专业的网页设计师。请根据用户需求生成完整的 HTML 页面。
要求：
1. 必须输出完整的 HTML 代码
2. 使用现代 CSS 样式
3. 响应式设计
4. 可以直接在浏览器中打开""",
            "research": """你是一个专业的市场研究员。请根据搜索结果进行分析。
要求：
1. 基于事实和数据
2. 引用信息来源
3. 提供可操作的建议
4. 区分事实和推断""",
            "chat": "你是一个友好的 AI 助手，请帮助用户解答问题。",
            "data": "你是一个数据分析专家，请帮助用户分析数据。",
            "image": "你是一个创意设计师，请帮助用户生成图片描述。"
        }

        system = system_prompts.get(task_type, system_prompts["chat"])

        # 调用模型
        result = self.model_client.chat(
            message=enhanced_prompt,
            system=system,
            temperature=0.7,
            max_tokens=2000
        )

        if not result["ok"]:
            return {
                "ok": False,
                "error": result.get("error", "模型调用失败"),
                "agent": "ModelAgent"
            }

        content = result["reply"]

        # 构建 deliverables
        deliverables = {}
        if task_type == "website":
            deliverables["html"] = content
        elif task_type == "marketing":
            deliverables["content"] = content

        return {
            "ok": True,
            "content": content,
            "deliverables": deliverables,
            "agent": self._get_agent_name(task_type),
            "summary": content[:100] + "..." if len(content) > 100 else content
        }

    def _get_agent_name(self, task_type: str) -> str:
        """获取 Agent 名称"""
        names = {
            "marketing": "MarketingAgent",
            "research": "ResearchAgent",
            "website": "WebsiteAgent",
            "data": "DataAgent",
            "image": "ImageAgent",
            "chat": "ChatAgent"
        }
        return names.get(task_type, "Agent")

    def _calculate_confidence(self, task_type: str, has_sources: bool,
                              qa_passed: bool, qa_score: int, used_web_search: bool) -> float:
        """计算置信度"""
        confidence = 0.5  # 基础置信度

        if has_sources:
            confidence += 0.2
        if used_web_search:
            confidence += 0.1
        if qa_passed:
            confidence += 0.15
        if qa_score >= 90:
            confidence += 0.05

        return min(confidence, 1.0)
