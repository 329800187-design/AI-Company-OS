"""
Task Classifier — 统一任务分类器

优先级：image > data > research > website > code > marketing > chat

UTF-8 编码，中文关键词正确识别
"""
import re
from typing import Dict, Tuple
from backend.logger import get_logger

logger = get_logger()


class TaskClassifier:
    """任务分类器"""

    # 关键词映射（按优先级排序）
    KEYWORDS = {
        "image": {
            "zh": ["图片", "海报", "插画", "封面", "商品图", "生成图", "照片", "设计图",
                   "产品图", "logo", "配图", "宣传图", "banner"],
            "en": ["image", "poster", "illustration", "cover", "photo", "picture",
                   "design", "logo", "banner", "generate image", "create image"]
        },
        "data": {
            "zh": ["数据", "表格", "数据分析", "统计", "报表", "excel", "csv",
                   "销售数据", "用户数据", "数据可视化", "图表"],
            "en": ["data", "csv", "excel", "spreadsheet", "analyze data",
                   "statistics", "report", "visualization", "chart"]
        },
        "research": {
            "zh": ["联网", "搜索", "调研", "市场分析", "竞品", "趋势", "行业",
                   "竞品分析", "市场调研", "行业报告", "用户画像", "市场机会"],
            "en": ["research", "search", "market analysis", "competitor",
                   "trend", "industry", "market research", "survey"]
        },
        "website": {
            "zh": ["网页", "官网", "落地页", "网站", "html", "生成网页",
                   "建网站", "产品页", "预约页", "着陆页"],
            "en": ["website", "webpage", "landing page", "html", "web page",
                   "create website", "build website"]
        },
        "code": {
            "zh": ["代码", "脚本", "python", "函数", "程序", "编程",
                   "写代码", "开发", "写一个函数", "写一个脚本"],
            "en": ["code", "script", "python", "function", "program",
                   "programming", "develop", "write code", "write a function"]
        },
        "marketing": {
            "zh": ["文案", "营销", "推广", "小红书", "闲鱼", "朋友圈", "抖音",
                   "广告", "slogan", "宣传语", "商品描述", "产品介绍"],
            "en": ["copywriting", "marketing", "promotion", "advertising",
                   "slogan", "product description", "write a post"]
        }
    }

    def classify(self, message: str, context: Dict = None) -> Tuple[str, float]:
        """
        分类任务

        Returns:
            (task_type, confidence)
        """
        message_lower = message.lower().strip()

        # 按优先级检查
        for task_type in ["image", "data", "research", "website", "code", "marketing"]:
            keywords = self.KEYWORDS[task_type]
            all_keywords = keywords["zh"] + keywords["en"]

            for keyword in all_keywords:
                if keyword in message_lower:
                    # 计算置信度
                    confidence = self._calculate_confidence(message_lower, keyword, task_type)
                    logger.info(f"TaskClassifier: '{message[:30]}...' -> {task_type} (keyword: {keyword})")
                    return task_type, confidence

        # 默认为 chat
        logger.info(f"TaskClassifier: '{message[:30]}...' -> chat (no keyword match)")
        return "chat", 0.5

    def _calculate_confidence(self, message: str, keyword: str, task_type: str) -> float:
        """计算置信度"""
        confidence = 0.7  # 基础置信度

        # 关键词越长，置信度越高
        if len(keyword) >= 4:
            confidence += 0.1

        # 如果有多个同类型关键词，置信度更高
        keywords = self.KEYWORDS[task_type]
        all_keywords = keywords["zh"] + keywords["en"]
        match_count = sum(1 for kw in all_keywords if kw in message)
        if match_count > 1:
            confidence += 0.1

        # 如果关键词在开头，置信度更高
        if message.startswith(keyword):
            confidence += 0.05

        return min(confidence, 1.0)

    def get_all_keywords(self) -> Dict[str, Dict[str, list]]:
        """获取所有关键词（用于测试）"""
        return self.KEYWORDS


# 全局实例
_classifier = None


def get_task_classifier() -> TaskClassifier:
    """获取任务分类器单例"""
    global _classifier
    if _classifier is None:
        _classifier = TaskClassifier()
    return _classifier
