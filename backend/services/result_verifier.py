"""
Result Verifier — 结果验证器

不同任务的成功标准：
1. research: 必须有 sources，至少 2 个有效来源
2. website: 必须生成可保存的 HTML 文件
3. image: 必须生成真实图片文件
4. data: 必须成功读取文件，返回字段摘要
5. code: 必须返回代码文件或 patch
6. marketing: 必须说明目标用户、卖点
"""
import re
from typing import Dict, Any, List
from backend.logger import get_logger

logger = get_logger()


class ResultVerifier:
    """结果验证器"""

    def verify(self, task_type: str, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证结果"""
        if task_type == "research":
            return self._verify_research(result)
        elif task_type == "website":
            return self._verify_website(result)
        elif task_type == "image":
            return self._verify_image(result)
        elif task_type == "data":
            return self._verify_data(result)
        elif task_type == "code":
            return self._verify_code(result)
        elif task_type == "marketing":
            return self._verify_marketing(result)
        else:
            return {"passed": True, "score": 100, "issues": []}

    def _verify_research(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证调研结果"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")
        sources = result.get("sources", [])

        # 检查是否有内容
        if not content or len(content.strip()) < 50:
            issues.append("内容过短")
            score -= 30

        # 检查是否有来源
        if not sources or len(sources) == 0:
            issues.append("没有信息来源")
            score -= 60
        elif len(sources) < 2:
            issues.append("信息来源不足（至少需要 2 个）")
            score -= 20

        # 检查内容是否包含结论
        conclusion_keywords = ["结论", "总结", "建议", "综上", "因此", "所以", "conclusion", "summary"]
        if not any(kw in content.lower() for kw in conclusion_keywords):
            issues.append("内容缺少结论")
            score -= 10

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues,
            "has_sources": len(sources) > 0,
            "source_count": len(sources)
        }

    def _verify_website(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证网站结果"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")

        # 检查是否是 HTML
        if not content:
            issues.append("内容为空")
            return {"passed": False, "score": 0, "issues": issues, "is_html": False}

        # 检查 HTML 结构
        content_lower = content.lower()
        if "<html" not in content_lower and "<!doctype" not in content_lower:
            issues.append("不是完整的 HTML 文档")
            score -= 50

        if "<body" not in content_lower:
            issues.append("缺少 body 标签")
            score -= 20

        if "<head" not in content_lower:
            issues.append("缺少 head 标签")
            score -= 10

        # 检查是否有 CSS
        if "<style" not in content_lower and "stylesheet" not in content_lower:
            issues.append("缺少样式")
            score -= 10

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues,
            "is_html": "<html" in content_lower or "<!doctype" in content_lower
        }

    def _verify_image(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证图片结果"""
        issues = []
        score = 100

        # 检查是否有图片文件
        deliverables = result.get("deliverables", {})
        image_url = deliverables.get("image_url", "")
        image_path = deliverables.get("image_path", "")
        image_base64 = deliverables.get("image_base64", "")

        if not image_url and not image_path and not image_base64:
            issues.append("没有生成图片文件")
            return {"passed": False, "score": 0, "issues": issues, "has_image": False}

        # 如果是文件路径，检查文件是否存在
        if image_path:
            import os
            if not os.path.exists(image_path):
                issues.append("图片文件不存在")
                score -= 50
            elif os.path.getsize(image_path) < 10240:  # 10KB
                issues.append("图片文件过小（< 10KB）")
                score -= 30

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues,
            "has_image": bool(image_url or image_path or image_base64)
        }

    def _verify_data(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证数据分析结果"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")
        deliverables = result.get("deliverables", {})

        # 检查是否有内容
        if not content or len(content.strip()) < 50:
            issues.append("分析结果过短")
            score -= 30

        # 检查是否有统计摘要
        stats_keywords = ["平均", "总计", "最大", "最小", "mean", "sum", "max", "min", "count"]
        if not any(kw in content.lower() for kw in stats_keywords):
            issues.append("缺少统计摘要")
            score -= 20

        # 检查是否有结论
        if not deliverables.get("summary") and not deliverables.get("conclusion"):
            if len(content) < 100:
                issues.append("缺少分析结论")
                score -= 20

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues
        }

    def _verify_code(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证代码结果"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")

        # 检查是否有代码
        if not content or len(content.strip()) < 20:
            issues.append("代码为空")
            return {"passed": False, "score": 0, "issues": issues}

        # 检查是否包含代码特征
        code_patterns = [r"def\s+\w+", r"function\s+\w+", r"class\s+\w+", r"import\s+", r"const\s+", r"let\s+"]
        has_code = any(re.search(p, content) for p in code_patterns)

        if not has_code:
            issues.append("内容不像是代码")
            score -= 40

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues,
            "has_code": has_code
        }

    def _verify_marketing(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """验证营销文案结果"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")

        # 检查是否有内容
        if not content or len(content.strip()) < 30:
            issues.append("文案过短")
            score -= 40

        # 检查是否有行动号召
        cta_keywords = ["购买", "下单", "点击", "链接", "扫码", "关注", "了解更多", "立即", "buy", "order", "click"]
        if not any(kw in content.lower() for kw in cta_keywords):
            issues.append("缺少行动号召")
            score -= 10

        return {
            "passed": score >= 60,
            "score": max(0, score),
            "issues": issues
        }


# 全局实例
_verifier = None


def get_result_verifier() -> ResultVerifier:
    """获取结果验证器单例"""
    global _verifier
    if _verifier is None:
        _verifier = ResultVerifier()
    return _verifier
