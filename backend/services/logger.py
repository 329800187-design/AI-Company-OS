"""结构化日志系统 — 基于 loguru 的 JSON 格式日志

提供:
- 统一日志格式（JSON + 中文友好）
- 每个 API 请求自动记录
- Agent 调用自动跟踪
- 日志轮转/压缩
"""
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from backend.config import LOG_LEVEL, LOG_DIR, LOG_MAX_DAYS


# ── 尝试加载 loguru，失败则降级为标准 logging ──────────────

try:
    from loguru import logger as _logger

    # 移除默认处理器
    _logger.remove()

    # 确保日志目录存在
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)

    # 控制台输出（彩色）
    _logger.add(
        sys.stderr,
        format="<green>{time:HH:mm:ss}</green> | <level>{level:<7}</level> | <cyan>{extra[source]:<12}</cyan> | {message}",
        level=LOG_LEVEL,
        colorize=True,
    )

    # 文件输出（JSON 格式）
    log_file = log_dir / "aco_{time:YYYY-MM-DD}.log"
    _logger.add(
        str(log_file),
        format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {extra[source]:<12} | {message}",
        level=LOG_LEVEL,
        rotation=f"{LOG_MAX_DAYS}d",
        compression="gz",
        encoding="utf-8",
        retention="30 days",
    )

    HAS_LOGURU = True

except ImportError:
    import logging

    _logger = logging.getLogger("aco")
    _logger.setLevel(getattr(logging, LOG_LEVEL.upper(), logging.INFO))

    # Console handler
    ch = logging.StreamHandler()
    ch.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s"))
    _logger.addHandler(ch)

    # File handler
    log_dir = Path(LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    fh = logging.FileHandler(log_dir / "aco.log", encoding="utf-8")
    fh.setFormatter(logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)-12s | %(message)s"))
    _logger.addHandler(fh)

    HAS_LOGURU = False


# ── 快捷函数 ──────────────────────────────────────────────


def get_logger(source: str = "system"):
    """获取带 source 标签的 logger

    Args:
        source: 日志来源标识（如 commander, ceo, codex, openclaw, api, system）

    Returns:
        绑定了 source 的 logger 实例
    """
    if HAS_LOGURU:
        return _logger.bind(source=source)
    else:
        return logging.getLogger(f"aco.{source}")


def log_api_request(method: str, path: str, status: int, duration_ms: int, user: str = ""):
    """记录 API 请求

    Args:
        method: HTTP 方法
        path: 请求路径
        status: HTTP 状态码
        duration_ms: 耗时（毫秒）
        user: 用户标识（可选）
    """
    log = get_logger("api")
    data = {
        "type": "api_request",
        "method": method,
        "path": path,
        "status": status,
        "duration_ms": duration_ms,
        "user": user,
    }
    if status >= 500:
        log.error(json.dumps(data, ensure_ascii=False))
    elif status >= 400:
        log.warning(json.dumps(data, ensure_ascii=False))
    else:
        log.info(json.dumps(data, ensure_ascii=False))


def log_agent_call(agent: str, action: str, duration_ms: int, success: bool, detail: str = ""):
    """记录 Agent 调用

    Args:
        agent: Agent 名称（ceo/codex/openclaw/qa/commander）
        action: 操作描述
        duration_ms: 耗时（毫秒）
        success: 是否成功
        detail: 补充细节
    """
    log = get_logger(f"agent.{agent}")
    data = {
        "type": "agent_call",
        "agent": agent,
        "action": action,
        "duration_ms": duration_ms,
        "success": success,
    }
    if detail:
        data["detail"] = detail[:200]

    if success:
        log.info(json.dumps(data, ensure_ascii=False))
    else:
        log.error(json.dumps(data, ensure_ascii=False))


def log_error(source: str, message: str, exc_info: bool = True):
    """记录错误

    Args:
        source: 错误来源
        message: 错误描述
        exc_info: 是否包含详细异常栈
    """
    log = get_logger(source)
    if exc_info:
        log.error(f"{message}\n{traceback.format_exc()}")
    else:
        log.error(message)


def log_info(source: str, message: str, **extra):
    """记录一般信息"""
    log = get_logger(source)
    if extra:
        log.info(f"{message} | {json.dumps(extra, ensure_ascii=False)}")
    else:
        log.info(message)


def log_warning(source: str, message: str, **extra):
    """记录警告"""
    log = get_logger(source)
    if extra:
        log.warning(f"{message} | {json.dumps(extra, ensure_ascii=False)}")
    else:
        log.warning(message)
