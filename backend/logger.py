"""
Logger Module — 统一日志记录

功能：
1. 统一日志格式
2. 日志级别管理
3. 日志文件轮转
4. 敏感信息脱敏
"""
import logging
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler


class SensitiveFilter(logging.Filter):
    """敏感信息过滤器"""

    # 敏感信息模式
    PATTERNS = [
        (r'api[_-]?key["\s:=]+["\']?([a-zA-Z0-9_-]{20,})', 'api_key=***'),
        (r'token["\s:=]+["\']?([a-zA-Z0-9_.-]{20,})', 'token=***'),
        (r'password["\s:=]+["\']?([^\s"\']{8,})', 'password=***'),
        (r'secret["\s:=]+["\']?([^\s"\']{8,})', 'secret=***'),
        (r'Bearer\s+([a-zA-Z0-9_.-]{20,})', 'Bearer ***'),
    ]

    def filter(self, record):
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = re.sub(pattern, replacement, record.msg, flags=re.IGNORECASE)
        return True


class ColoredFormatter(logging.Formatter):
    """彩色日志格式化器"""

    COLORS = {
        'DEBUG': '\033[36m',    # Cyan
        'INFO': '\033[32m',     # Green
        'WARNING': '\033[33m',  # Yellow
        'ERROR': '\033[31m',    # Red
        'CRITICAL': '\033[35m', # Magenta
    }
    RESET = '\033[0m'

    def format(self, record):
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        return super().format(record)


class Logger:
    """统一日志管理器"""

    _instance: Optional['Logger'] = None
    _initialized: bool = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 创建 logger
        self.logger = logging.getLogger('ai_company_os')
        self.logger.setLevel(logging.DEBUG)

        # 防止重复添加 handler
        if self.logger.handlers:
            return

        # 控制台 handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_formatter = ColoredFormatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(message)s',
            datefmt='%H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)

        # 文件 handler
        log_dir = os.getenv('LOG_DIR', './logs')
        log_dir = Path(log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_dir / 'app.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_formatter = logging.Formatter(
            '%(asctime)s | %(levelname)s | %(name)s | %(funcName)s:%(lineno)d | %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        file_handler.setFormatter(file_formatter)

        # 错误日志 handler
        error_handler = RotatingFileHandler(
            log_dir / 'error.log',
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_formatter)

        # 添加敏感信息过滤器
        sensitive_filter = SensitiveFilter()
        console_handler.addFilter(sensitive_filter)
        file_handler.addFilter(sensitive_filter)
        error_handler.addFilter(sensitive_filter)

        # 添加 handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)

    def debug(self, msg: str, **kwargs):
        """调试日志"""
        self.logger.debug(msg, **kwargs)

    def info(self, msg: str, **kwargs):
        """信息日志"""
        self.logger.info(msg, **kwargs)

    def warning(self, msg: str, **kwargs):
        """警告日志"""
        self.logger.warning(msg, **kwargs)

    def error(self, msg: str, **kwargs):
        """错误日志"""
        self.logger.error(msg, **kwargs)

    def critical(self, msg: str, **kwargs):
        """严重错误日志"""
        self.logger.critical(msg, **kwargs)

    def exception(self, msg: str, **kwargs):
        """异常日志（包含堆栈）"""
        self.logger.exception(msg, **kwargs)

    def log_api_request(self, method: str, path: str, status: int, duration_ms: int, user: str = ""):
        """记录 API 请求"""
        self.info(f"API Request | {method} {path} | Status: {status} | Duration: {duration_ms}ms | User: {user}")

    def log_agent_call(self, agent_name: str, task_type: str, status: str, duration_ms: int):
        """记录 Agent 调用"""
        self.info(f"Agent Call | {agent_name} | Task: {task_type} | Status: {status} | Duration: {duration_ms}ms")

    def log_error(self, error: Exception, context: str = ""):
        """记录错误"""
        self.error(f"Error | Context: {context} | Type: {type(error).__name__} | Message: {str(error)}")


# 全局 logger 实例
logger = Logger()


# 便捷函数
def get_logger() -> Logger:
    """获取 logger 实例"""
    return logger
