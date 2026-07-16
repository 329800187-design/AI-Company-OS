"""Template Router — 场景化模板系统

将多个 Agent 能力打包成"客户能理解的模板"，一键执行产出可用结果。
不新建任何 Agent，纯上层封装。
"""
import json
import os
import uuid
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.services.agent_loader import load_agent_instance

router = APIRouter(prefix="/templates", tags=["模板 / Templates"])

# ── Agent 懒加载 ──────────────────────────────────────────

_agents = {}

# Agent 配置：name -> (entrypoint, class_name, kwargs)
_AGENT_CONFIG = {
    "ceo": ("agents.ceo_agent.agent", "CEOAgent", {}),
    "codex": ("agents.codex_agent.agent", "CodexAgent", {"timeout": 30}),
    "openclaw": ("agents.openclaw_agent.agent", "OpenClawAgent", {"headless": True, "timeout": 30}),
    "qa": ("agents.qa_agent.agent", "QAAgent", {}),
    "system": ("agents.system_agent.agent", "SystemAgent", {"timeout": 120}),
}

def _get_agent(name: str):
    if name not in _agents:
        config = _AGENT_CONFIG.get(name)
        if config:
            entrypoint, class_name, kwargs = config
            _agents[name] = load_agent_instance(entrypoint, class_name, **kwargs)
    return _agents.get(name)


# ── 模板定义 ──────────────────────────────────────────────

TEMPLATES: List[Dict[str, Any]] = [
    # ── 原有 4 个模板 ──────────────────────────────────
    {
        "id": "ecommerce-copy",
        "name": "电商文案生成",
        "emoji": "🛍️",
        "description": "输入产品名，自动生成商品描述、卖点文案、广告语，适合电商卖家一键出文案。",
        "inputs": [
            {"key": "product_name", "label": "产品名称", "type": "text", "placeholder": "例如：智能蓝牙耳机 / 手工真皮钱包"},
            {"key": "product_desc", "label": "产品特点（可选）", "type": "textarea", "placeholder": "例如：降噪、续航24小时、IPX5防水"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "为产品【{product_name}】生成一套完整电商文案，包括：1) 200字商品描述  2) 3条卖点文案  3) 3条广告语  4) 5个SEO关键词。产品特点：{product_desc}"},
            {"agent": "codex", "mode": "code_execute", "code": "result = {\n  '产品描述': 'description_placeholder',\n  '卖点文案': ['point1', 'point2', 'point3'],\n  '广告语': ['tagline1', 'tagline2', 'tagline3'],\n  'SEO关键词': ['kw1', 'kw2', 'kw3', 'kw4', 'kw5']\n}\nprint(json.dumps(result, ensure_ascii=False, indent=2))"},
            {"agent": "qa", "review": "检查文案质量"},
        ],
        "output_hint": "可直接复制粘贴使用的电商文案包（含商品描述、卖点、广告语、SEO词）",
    },
    {
        "id": "competitor-analysis",
        "name": "竞品分析报告",
        "emoji": "🔍",
        "description": "输入竞争对手网站URL，自动爬取页面内容并生成结构化竞品分析报告。",
        "inputs": [
            {"key": "url", "label": "竞品网站URL", "type": "url", "placeholder": "例如：https://example.com"},
            {"key": "industry", "label": "所属行业（可选）", "type": "text", "placeholder": "例如：电商 / SaaS / 教育"},
        ],
        "steps": [
            {"agent": "openclaw", "mode": "browser_scrape", "url": "{url}", "extract": "text"},
            {"agent": "ceo", "goal": "基于以下网站内容，输出竞品分析报告(中文)，包含：1) 公司定位  2) 核心产品/服务  3) 目标客户  4) 商业模式  5) 优劣势分析  6) 差异化建议。内容：{prev_output}"},
            {"agent": "qa", "review": "检查分析报告完整度"},
        ],
        "output_hint": "结构化的竞品分析报告（Markdown格式），可直接阅读或导出",
    },
    {
        "id": "quick-website",
        "name": "快速建站",
        "emoji": "🌐",
        "description": "一句话描述想要的网站，自动生成完整的HTML页面，可直接在浏览器打开。",
        "inputs": [
            {"key": "description", "label": "网站描述", "type": "textarea", "placeholder": "例如：一个现代风格的咖啡店官网，配色温暖"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "基于以下需求，规划网站结构和设计风格：{description}。输出JSON格式的页面结构、配色方案、字体、布局。"},
            {"agent": "codex", "mode": "code_write_and_run",
             "code": "通过CEO输出的规划生成一个完整的HTML单页网站，包含所有样式内联，可直接在浏览器打开。"},
            {"agent": "qa", "review": "检查HTML是否完整、可打开"},
        ],
        "output_hint": "可直接保存为 .html 文件并在浏览器打开的完整网站源码",
    },
    {
        "id": "social-content",
        "name": "社交媒体内容生成",
        "emoji": "📱",
        "description": "生成小红书/微博/抖音等平台的营销内容，含标题、正文、话题标签。",
        "inputs": [
            {"key": "topic", "label": "内容主题", "type": "text", "placeholder": "例如：夏季护肤推荐 / 新手烹饪技巧"},
            {"key": "platform", "label": "目标平台", "type": "select", "options": ["小红书", "微博", "抖音", "微信公众号", "全部"],
             "default": "小红书"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "为【{platform}】平台生成关于【{topic}】的营销内容，包含：1) 吸引眼球的标题(3个)  2) 正文文案(300-500字)  3) 互动引导  4) 热门话题标签(5-10个)  5) 发布时间建议"},
            {"agent": "codex", "mode": "code_execute", "code": "result = {'title': ['title1','title2','title3'], 'body': '...', 'hashtags': ['#tag1','#tag2']}\nprint('内容生成完成')"},
            {"agent": "qa", "review": "检查内容相关性、平台适配度"},
        ],
        "output_hint": "可直接发布的社交媒体文案包，含标题、正文、标签",
    },

    # ── 新增 8 个模板 ──────────────────────────────────
    {
        "id": "data-insight",
        "name": "数据洞察分析",
        "emoji": "📊",
        "description": "描述你的数据情况和分析需求，AI自动写Python代码分析数据，输出可视化图表和结论。",
        "inputs": [
            {"key": "data_desc", "label": "数据描述", "type": "textarea", "placeholder": "例如：我有100条客户订单数据，字段包括订单金额、地区、日期，想分析各地区销售额趋势"},
            {"key": "analysis_goal", "label": "分析目标", "type": "text", "placeholder": "例如：找出销售额最高的Top5地区、季度增长趋势"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "数据分析任务：数据描述={data_desc}，分析目标={analysis_goal}。输出：1) Python分析代码  2) 预期输出说明"},
            {"agent": "codex", "mode": "code_execute", "code": "# AI生成的分析代码将在此执行\n# 数据描述：{data_desc}\n# 分析目标：{analysis_goal}\nprint('数据分析完成，结果如下：')\nprint('请查看上方CEO的输出作为执行参考')"},
            {"agent": "qa", "review": "检查分析结果是否回答了用户的问题"},
        ],
        "output_hint": "数据分析代码 + 执行结果 + 业务洞察结论",
    },
    {
        "id": "seo-article",
        "name": "SEO 文章生成",
        "emoji": "✍️",
        "description": "输入核心关键词和目标受众，自动生成一篇SEO优化文章（标题、正文、Meta描述、内链建议）。",
        "inputs": [
            {"key": "keyword", "label": "核心关键词", "type": "text", "placeholder": "例如：家用跑步机推荐"},
            {"key": "audience", "label": "目标读者", "type": "text", "placeholder": "例如：健身新手 / 家庭用户"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "生成一篇围绕关键词【{keyword}】的SEO优化文章，目标读者【{audience}】。包含：1) SEO标题（含关键词） 2) Meta描述（<160字） 3) 文章正文（800-1000字，含H2/H3分段） 4) 内链建议（3条） 5) 关键词密度分析"},
            {"agent": "codex", "mode": "code_execute", "code": "print('SEO文章已由CEO生成，请查看上一步输出。')"},
            {"agent": "qa", "review": "检查文章是否包含核心关键词、结构是否合理"},
        ],
        "output_hint": "可直接发布的SEO优化文章，含标题、Meta描述、正文、内链建议",
    },
    {
        "id": "contract-summary",
        "name": "合同摘要提取",
        "emoji": "📄",
        "description": "输入合同/协议文本或URL，自动提取签署方、金额、期限、违约责任等关键条款。",
        "inputs": [
            {"key": "contract_text", "label": "合同文本或URL", "type": "textarea", "placeholder": "粘贴合同文本，或输入合同PDF页面的URL"},
            {"key": "extract_points", "label": "重点关注（可选）", "type": "text", "placeholder": "例如：赔偿条款、保密协议、终止条件"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "从以下合同/协议文本中提取关键条款，重点关注：{extract_points}。输出结构化摘要：1) 合同类型 2) 签署方 3) 金额/对价 4) 期限 5) 续约条件 6) 违约责任 7) 终止条款 8) 保密条款 9) 争议解决。合同文本：{contract_text}"},
            {"agent": "qa", "review": "检查提取的关键条款是否完整、准确"},
        ],
        "output_hint": "结构化合同摘要，一目了然的关键条款列表",
    },
    {
        "id": "job-description",
        "name": "招聘JD生成器",
        "emoji": "💼",
        "description": "输入职位名称和岗位要求，自动生成完整的招聘JD（岗位描述、任职要求、面试题）。",
        "inputs": [
            {"key": "position", "label": "职位名称", "type": "text", "placeholder": "例如：高级前端工程师"},
            {"key": "requirements", "label": "岗位要求（关键词）", "type": "textarea", "placeholder": "例如：React经验3年以上、熟悉TypeScript、有团队管理经验"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "为【{position}】职位生成完整招聘JD。要求：{requirements}。输出包含：1) 岗位标题 2) 部门/汇报线 3) 岗位职责（5-8条） 4) 任职要求（必备+加分） 5) 薪资范围建议 6) 面试题（3-5道技术题+2道软技能题） 7) 团队介绍"},
            {"agent": "codex", "mode": "code_execute", "code": "result = {'position': '{position}', 'title': '高级工程师', 'responsibilities': ['...']}\nprint('JD生成完成，请查看上一步CEO的输出')"},
            {"agent": "qa", "review": "检查JD是否完整、职责和要求是否匹配"},
        ],
        "output_hint": "完整招聘JD（可直接复制到招聘平台）+ 配套面试题",
    },
    {
        "id": "email-reply",
        "name": "客户邮件回复",
        "emoji": "📧",
        "description": "输入客户发来的原始邮件，自动生成专业、得体的回复文案，支持多种语气。",
        "inputs": [
            {"key": "original_email", "label": "客户原始邮件", "type": "textarea", "placeholder": "粘贴客户发来的邮件内容..."},
            {"key": "tone", "label": "回复语气", "type": "select", "options": ["专业正式", "友好亲切", "紧急处理", "拒绝委婉"], "default": "专业正式"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "为以下客户邮件撰写【{tone}】语气的回复。原始邮件：{original_email}。输出：1) 回复主题 2) 正文（含问候、回应要点、下一步行动、结束语） 3) 附件建议（如有） 4) 回复时机建议"},
            {"agent": "qa", "review": "检查回复是否解决了客户的核心问题、语气是否恰当"},
        ],
        "output_hint": "可直接复制发送的邮件回复文案",
    },
    {
        "id": "product-manual",
        "name": "产品说明书生成",
        "emoji": "📖",
        "description": "输入产品名称和核心功能，自动生成图文并茂的产品说明书/用户手册。",
        "inputs": [
            {"key": "product_name", "label": "产品名称", "type": "text", "placeholder": "例如：智能体脂秤 X100"},
            {"key": "features", "label": "核心功能与参数", "type": "textarea", "placeholder": "例如：蓝牙5.0连接、15项身体数据、App同步、支持8人共用"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "为产品【{product_name}】生成中文用户说明书，核心功能：{features}。包含：1) 产品概览 2) 开箱清单 3) 快速入门指南（分步骤） 4) 功能介绍 5) 参数规格表 6) 常见问题FAQ（5条） 7) 安全注意事项 8) 售后服务说明"},
            {"agent": "qa", "review": "检查说明书是否覆盖了所有功能点、FAQ是否实用"},
        ],
        "output_hint": "完整产品说明书（可直接复制到文档/PDF中）",
    },
    {
        "id": "translation-proofread",
        "name": "多语言翻译校对",
        "emoji": "🌍",
        "description": "输入原文和目标语言，AI翻译后进行语法校对、语气优化，输出双语对照版本。",
        "inputs": [
            {"key": "source_text", "label": "原文", "type": "textarea", "placeholder": "粘贴要翻译的原文（支持中/英/日/韩等）"},
            {"key": "target_lang", "label": "目标语言", "type": "text", "placeholder": "例如：英语 / 日语 / 韩语 / 法语"},
            {"key": "style", "label": "风格", "type": "select", "options": ["正式", "口语", "营销", "学术"], "default": "正式"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "将以下原文翻译为【{target_lang}】，风格要求：【{style}】。输出：1) 双语对照表（逐段对照） 2) 译文 3) 翻译说明（解释关键术语/文化差异的翻译选择） 4) 语气/风格优化建议。原文：{source_text}"},
            {"agent": "qa", "review": "检查翻译准确性、语法正确性、风格一致性"},
        ],
        "output_hint": "双语对照翻译稿 + 翻译说明",
    },
    {
        "id": "meeting-minutes",
        "name": "会议纪要生成",
        "emoji": "📝",
        "description": "输入会议录音转文字或会议笔记，自动生成结构化会议纪要（议题、结论、待办事项）。",
        "inputs": [
            {"key": "notes", "label": "会议记录/笔记", "type": "textarea", "placeholder": "粘贴会议记录或录音转文字内容..."},
            {"key": "format", "label": "纪要风格", "type": "select", "options": ["详细版（含讨论过程）", "精简版（仅结论和待办）"], "default": "精简版（仅结论和待办）"},
        ],
        "steps": [
            {"agent": "ceo", "goal": "将以下会议记录整理为【{format}】格式的会议纪要。输出：1) 会议信息（时间/参与者/主题） 2) 议题列表 3) 每项议题的讨论摘要 4) 结论/决议 5) 待办事项（责任人+DDL） 6) 下次会议建议。记录：{notes}"},
            {"agent": "qa", "review": "检查纪要是否涵盖了所有议题、待办事项是否清晰"},
        ],
        "output_hint": "结构化会议纪要，可直接分享给参会者",
    },
]


# ── Schema ─────────────────────────────────────────────────

class RunTemplateRequest(BaseModel):
    """执行模板请求"""
    template_id: str
    inputs: Dict[str, str] = {}
    async_mode: bool = False


class TemplateInput(BaseModel):
    key: str
    label: str
    type: str = "text"
    placeholder: str = ""
    options: List[str] = []
    default: str = ""


class TemplateStep(BaseModel):
    agent: str
    goal: str = ""
    mode: str = ""
    code: str = ""
    url: str = ""
    extract: str = ""
    review: str = ""
    files: List[Dict[str, str]] = []


class TemplateDefinition(BaseModel):
    id: str
    name: str
    emoji: str
    description: str
    inputs: List[Dict[str, Any]]
    steps: List[Dict[str, Any]]
    output_hint: str


# ── 路由 ───────────────────────────────────────────────────

@router.get("/list", summary="获取模板列表",
            description="返回所有可用模板的定义，包括输入字段、执行步骤、输出描述。")
def list_templates():
    """返回所有模板"""
    return {"templates": TEMPLATES, "count": len(TEMPLATES)}


@router.get("/{template_id}", summary="获取模板详情",
            description="查看单个模板的完整定义，包括输入字段说明和执行步骤。")
def get_template(template_id: str):
    """查看单个模板详情"""
    for t in TEMPLATES:
        if t["id"] == template_id:
            return {"template": t}
    raise HTTPException(status_code=404, detail="模板不存在")


@router.post("/run/{template_id}", summary="执行模板",
             description="选择一个模板，填入参数后执行。系统会自动调用多个 Agent 完成任务，返回最终可用结果。")
def run_template(template_id: str, request: RunTemplateRequest):
    """执行模板工作流"""
    from backend.governance.deprecated import deprecated_route_response
    return deprecated_route_response(
        f"/templates/run/{template_id}",
        replacement=None,
        reason="模板多 Agent 执行旧入口已停用，请先迁移为受控能力后再执行。",
    )

    # 找到模板
    template = None
    for t in TEMPLATES:
        if t["id"] == template_id:
            template = t
            break
    if not template:
        raise HTTPException(status_code=404, detail="模板不存在")

    run_id = uuid.uuid4().hex[:8]
    inputs = request.inputs or {}
    results = []
    step_outputs = {}

    # 遍历执行步骤
    for i, step_def in enumerate(template["steps"]):
        agent_name = step_def["agent"]
        agent = _get_agent(agent_name)
        if not agent:
            results.append({"step": i + 1, "status": "失败", "error": f"Agent {agent_name} 不可用"})
            continue

        # 格式化 goal / code / url（替换 {xxx} 和 {prev_output}）
        goal = step_def.get("goal", "")
        code = step_def.get("code", "")
        url = step_def.get("url", "")

        # 替换输入占位符
        for k, v in inputs.items():
            goal = goal.replace(f"{{{k}}}", v)
            code = code.replace(f"{{{k}}}", v)
            url = url.replace(f"{{{k}}}", v)

        # 替换上一轮输出
        for prev_key, prev_val in step_outputs.items():
            goal = goal.replace("{prev_output}", str(prev_val)[:2000])
            code = code.replace("{prev_output}", str(prev_val)[:2000])

        # 构建任务
        task = {
            "task_id": f"tpl_{run_id}_{i}",
            "goal": goal,
        }

        # 不同 Agent 不同参数
        if agent_name == "ceo":
            task["task_type"] = "goal_decompose"
        elif agent_name == "codex":
            task["task_type"] = step_def.get("mode", "code_execute")
            task["code"] = code
            if step_def.get("files"):
                task["files"] = step_def["files"]
        elif agent_name == "openclaw":
            task["task_type"] = step_def.get("mode", "browser_scrape")
            task["url"] = url
            task["extract"] = step_def.get("extract", "text")
        elif agent_name == "qa":
            task["task_type"] = "qa_review"
            task["goal"] = step_def.get("review", goal)
        elif agent_name == "system":
            task["task_type"] = "shell_execute"
            task["command"] = step_def.get("command", "")

        try:
            result = agent.run(task)
            status = "已完成"
            step_outputs[f"step_{i}"] = result
            results.append({
                "step": i + 1,
                "agent": agent_name,
                "status": "已完成",
                "summary": str(result)[:300],
                "raw": result,
            })
        except Exception as e:
            results.append({
                "step": i + 1,
                "agent": agent_name,
                "status": "失败",
                "error": str(e),
            })
            # 出错不中断，继续执行下一步
            step_outputs[f"step_{i}"] = {"error": str(e)}

    # 汇总输出
    success_count = sum(1 for r in results if r["status"] == "已完成")
    total_count = len(results)

    # 提取最终产出
    final_output = ""
    for r in reversed(results):
        if r["status"] == "已完成" and r.get("summary"):
            final_output = r["summary"]
            break

    return {
        "run_id": run_id,
        "template_id": template_id,
        "template_name": template["name"],
        "status": "全部完成" if success_count == total_count else f"部分完成（{success_count}/{total_count}）",
        "success_count": success_count,
        "total_count": total_count,
        "results": results,
        "final_output": final_output,
        "output_hint": template["output_hint"],
    }
