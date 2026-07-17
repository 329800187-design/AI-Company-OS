"""
QA 服务 — 质量审核

规则：
- QA >= 80: passed
- 60 <= QA < 80: needs_review
- QA < 60: failed
"""
from typing import List, Dict


class QAService:
    """QA 审核服务"""

    def review(self, task_type: str, content: str, sources: List[dict] = None, goal: str = "") -> dict:
        """审核内容质量"""

        score = 100
        problems = []
        suggestions = []

        # 1. 基础检查
        if not content or len(content.strip()) < 10:
            score -= 50
            problems.append("内容过短或为空")

        # 2. 任务类型特定检查
        if task_type == "research":
            if not sources or len(sources) == 0:
                score -= 60
                problems.append("调研类任务必须有信息来源")
            elif len(sources) < 2:
                score -= 20
                problems.append("信息来源不足，建议至少 2 个")

        elif task_type == "website":
            if "<html" not in content.lower() and "<!doctype" not in content.lower():
                score -= 40
                problems.append("网站类任务必须返回 HTML 代码")

        elif task_type == "image":
            # 图片类任务需要有实际的图片数据
            score -= 30
            problems.append("图片服务暂未开通")

        elif task_type == "marketing":
            # 营销类检查
            if len(content) < 50:
                score -= 20
                suggestions.append("文案内容较短，建议丰富产品描述")

        # 3. 通用质量检查
        if "抱歉" in content or "无法" in content or "不能" in content:
            score -= 15
            problems.append("内容包含消极表述")

        if len(content) > 5000:
            suggestions.append("内容较长，建议精简")

        # 4. 来源检查
        if sources and len(sources) > 0:
            score = min(score + 10, 100)  # 有来源加分

        # 确保分数在 0-100 范围内
        score = max(0, min(100, score))

        # 判断状态
        if score >= 80:
            status = "passed"
            passed = True
        elif score >= 60:
            status = "needs_review"
            passed = True
            suggestions.append("建议人工复查")
        else:
            status = "failed"
            passed = False

        return {
            "passed": passed,
            "score": score,
            "status": status,
            "problems": problems,
            "suggestions": suggestions
        }
