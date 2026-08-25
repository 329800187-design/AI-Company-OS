"""
Result Verifier — 结果验证器（v2：advisory 模式）

验证原则（v2 改动）：
- QA 不再决定"商业方案好不好"，只做基础结构检查
- 有内容但缺来源 → QA partial，不阻断输出
- 有内容但缺 CTA → QA partial，不阻断输出
- 空结果或执行异常 → QA failed，才是真正的失败
- 结构完整 → QA pass

QA 输出状态：
  - pass：结构完整，内容充足
  - partial：有内容但缺来源/证据/字段
  - needs_input：缺用户输入
  - failed：空结果或执行异常
"""
import re
import os
from typing import Dict, Any, List
from backend.logger import get_logger

logger = get_logger()


class ResultVerifier:
    """结果验证器（v2：advisory 模式 — 不阻挡，只建议）"""

    def verify(self, task_type: str, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证结果

        Args:
            task_type: 任务类型
            result: 待验证结果
            strict: 严格模式（pipeline 消费者使用）。strict=True 时 partial 视为未通过。
        """
        if task_type == "research":
            return self._verify_research(result, strict=strict)
        elif task_type == "website":
            return self._verify_website(result, strict=strict)
        elif task_type == "image":
            return self._verify_image(result, strict=strict)
        elif task_type == "data":
            return self._verify_data(result, strict=strict)
        elif task_type == "code":
            return self._verify_code(result, strict=strict)
        elif task_type == "marketing":
            return self._verify_marketing(result, strict=strict)
        else:
            return {"passed": True, "qa_status": "pass", "score": 100, "issues": []}

    def _verify_research(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证调研结果 — v2 advisory 模式"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")
        sources = result.get("sources", [])

        # 检查是否有内容（只有真正空结果才 failed）
        if not content or len(content.strip()) < 50:
            failure_issues = ["内容为空或过短"]
            if not sources:
                failure_issues.append("缺少信息来源")
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": failure_issues,
                "has_sources": False,
                "source_count": 0,
            }

        # 检查来源 — v2: 缺来源不阻断，只标记 partial
        has_sources = bool(sources and len(sources) > 0)
        if not has_sources:
            issues.append("没有信息来源 - 结果基于模型已有知识，非实时数据")
            score -= 25
        elif len(sources) < 2:
            issues.append("信息来源不足（建议至少 2 个）")
            score -= 20

        # 检查内容是否包含结论
        conclusion_keywords = ["结论", "总结", "建议", "综上", "因此", "所以", "conclusion", "summary"]
        if not any(kw in content.lower() for kw in conclusion_keywords):
            issues.append("内容缺少结论")
            score -= 10

        # v2: passed 只判断是否有内容，qa_status 反映结构质量
        qa_status = "pass" if score >= 80 else "partial"

        return {
            "passed": qa_status == "pass" if strict else True,   # v2: 有内容就算通过; strict: partial 视为未通过
            "qa_status": qa_status,
            "score": max(0, score),
            "issues": issues,
            "has_sources": has_sources,
            "source_count": len(sources)
        }

    def _verify_website(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证网站结果 — v2 advisory 模式"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")

        if not content:
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["内容为空"],
                "is_html": False,
            }

        content_lower = content.lower()

        # 检查是否是 HTML
        if "<!doctype" not in content_lower and "<html" not in content_lower:
            # 不是 HTML — 任务要求网站但返回了纯文本，视为失败
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["不是完整的 HTML 文档 - 缺少 <!doctype 或 <html>，网站任务要求 HTML 输出"],
                "is_html": False,
            }

        if "<head" not in content_lower:
            # 缺少 <head> — 结构不完整，视为失败
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["缺少 <head> 标签 - HTML 结构不完整"],
                "is_html": True,
            }
        if "<body" not in content_lower:
            # 缺少 <body> — 结构不完整，视为失败
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["缺少 <body> 标签 - HTML 结构不完整"],
                "is_html": True,
            }
        if "<style" not in content_lower and "stylesheet" not in content_lower:
            issues.append("缺少样式")
            score -= 10

        qa_status = "pass" if score > 90 else "partial"

        return {
            "passed": qa_status == "pass" if strict else True,
            "qa_status": qa_status,
            "score": max(0, score),
            "issues": issues,
            "is_html": True,
        }

    def _verify_image(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证图片结果 — v2 advisory 模式"""
        issues = []
        score = 100

        deliverables = result.get("deliverables", {})
        image_url = deliverables.get("image_url", "")
        image_path = deliverables.get("image_path", "")
        image_base64 = deliverables.get("image_base64", "")

        if not image_url and not image_path and not image_base64:
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["没有生成图片文件"],
                "has_image": False,
            }

        if image_path:
            if not os.path.exists(image_path):
                issues.append("图片文件不存在")
                score -= 50
            elif os.path.getsize(image_path) < 10240:
                issues.append("图片文件过小（< 10KB）")
                score -= 30

        qa_status = "pass" if score >= 80 else "partial"

        return {
            "passed": qa_status == "pass" if strict else True,
            "qa_status": qa_status,
            "score": max(0, score),
            "issues": issues,
            "has_image": bool(image_url or image_path or image_base64),
        }

    def _verify_data(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证数据分析结果 — v2 advisory 模式"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")
        deliverables = result.get("deliverables", {})

        if not content or len(content.strip()) < 50:
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["分析结果为空"],
                "has_input_data": False,
            }

        has_input_data = deliverables.get("rows", 0) > 0 and deliverables.get("columns", 0) > 0
        if not has_input_data:
            # v2: 有分析文本但没有数据输入 → partial，不阻断
            issues.append("没有真实数据输入 — 分析基于文字而非数据表格")
            score -= 50

        stats_keywords = ["平均", "总计", "最大", "最小", "mean", "sum", "max", "min", "count", "行", "列"]
        if not any(kw in content.lower() for kw in stats_keywords):
            issues.append("缺少统计摘要")
            score -= 20

        qa_status = "pass" if score >= 80 else ("partial" if score >= 30 else "failed")

        return {
            "passed": (qa_status == "pass") if strict else (score >= 30),   # v2: 只有极低分才 fail; strict: partial 也视为未通过
            "qa_status": qa_status,
            "score": max(0, score),
            "issues": issues,
            "has_input_data": has_input_data,
            "parsed_rows": deliverables.get("rows", 0),
            "parsed_columns": deliverables.get("columns", 0),
        }

    def _verify_code(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证代码结果 — v2 advisory 模式"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")

        if not content or len(content.strip()) < 20:
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["代码为空"],
                "has_code": False,
            }

        code_patterns = [r"def\s+\w+", r"function\s+\w+", r"class\s+\w+", r"import\s+", r"const\s+", r"let\s+", r"return\s+"]
        has_code = any(re.search(p, content) for p in code_patterns)

        if not has_code:
            # 有文本但不是代码 — 任务要求代码但返回了纯文本，视为失败
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["内容不像是代码 - 没有函数/类/import 等代码结构，代码任务要求代码输出"],
                "has_code": False,
            }

        env_indicators = ["安装", "配置", "环境", "setup", "install", "configure"]
        if any(ind in content.lower() for ind in env_indicators) and len(content) < 200:
            if not any(re.search(p, content) for p in [r"def\s+\w+", r"class\s+\w+"]):
                return {
                    "passed": False,
                    "qa_status": "failed",
                    "score": 0,
                    "issues": ["内容是环境说明，不是实际代码，代码任务要求代码输出"],
                    "has_code": False,
                }

        return {
            "passed": True,
            "qa_status": "pass",
            "score": score,
            "issues": issues,
            "has_code": True,
        }

    def _verify_marketing(self, result: Dict[str, Any], strict: bool = False) -> Dict[str, Any]:
        """验证营销文案结果 — v2 advisory 模式"""
        issues = []
        score = 100

        content = result.get("final_answer", "") or result.get("content", "")
        sources = result.get("sources", [])

        if not content or len(content.strip()) < 30:
            return {
                "passed": False,
                "qa_status": "failed",
                "score": 0,
                "issues": ["文案为空或过短"],
                "has_sources": bool(sources),
            }

        # v2: 缺 CTA 只是 warning，不阻断。但 qa_status 应反映为 partial
        cta_keywords = ["购买", "下单", "点击", "链接", "扫码", "关注", "了解更多", "立即", "buy", "order", "click"]
        if not any(kw in content.lower() for kw in cta_keywords):
            issues.append("缺少行动号召（CTA）")
            score -= 25  # 降分足够触发 partial

        # v2: 没有来源只是提示，不阻断
        if not sources or len(sources) == 0:
            issues.append("未联网，仅模型推断")
            score -= 5   # 微小降分，不触发 partial

        qa_status = "pass" if score >= 80 else "partial"

        return {
            "passed": qa_status == "pass" if strict else True,   # v2: 有内容就算通过; strict: partial 视为未通过
            "qa_status": qa_status,
            "score": max(0, score),
            "issues": issues,
            "has_sources": bool(sources),
        }


# 全局实例
_verifier = None


def get_result_verifier() -> ResultVerifier:
    """获取结果验证器单例"""
    global _verifier
    if _verifier is None:
        _verifier = ResultVerifier()
    return _verifier
