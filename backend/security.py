"""
Security Module — 输入验证、防护、安全工具

功能：
1. 输入验证（长度、类型、格式）
2. SQL注入防护
3. 文件上传安全检查
4. XSS防护
5. Rate limiting
6. 敏感信息脱敏
"""
import re
import hashlib
import secrets
from typing import Any, Optional
from pathlib import Path

# ── 输入验证 ──────────────────────────────────────────────────

class InputValidator:
    """输入验证器"""

    # 最大长度限制
    MAX_MESSAGE_LENGTH = 10000
    MAX_GOAL_LENGTH = 5000
    MAX_FILENAME_LENGTH = 255
    MAX_PATH_LENGTH = 4096

    # 允许的文件扩展名
    ALLOWED_DATA_EXTENSIONS = {'.csv', '.xlsx', '.xls', '.json', '.tsv', '.parquet'}
    ALLOWED_IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.webp'}

    # 危险文件扩展名
    DANGEROUS_EXTENSIONS = {
        '.exe', '.bat', '.cmd', '.com', '.msi', '.scr', '.pif',
        '.vbs', '.vbe', '.js', '.jse', '.ws', '.wsf', '.wsc',
        '.ps1', '.psm1', '.psd1', '.ps1xml', '.pssc', '.psrc',
        '.reg', '.inf', '.lnk', '.url', '.hta', '.cpl', '.msc',
        '.dll', '.sys', '.drv'
    }

    @staticmethod
    def validate_message(message: str) -> tuple[bool, str]:
        """验证消息输入"""
        if not message or not message.strip():
            return False, "消息不能为空"

        if len(message) > InputValidator.MAX_MESSAGE_LENGTH:
            return False, f"消息长度不能超过 {InputValidator.MAX_MESSAGE_LENGTH} 字符"

        # 检查是否有潜在的注入攻击
        suspicious_patterns = [
            r'<script[^>]*>',  # XSS
            r'javascript:',  # JavaScript协议
            r'on\w+\s*=',  # 事件处理器
            r'union\s+select',  # SQL注入
            r'drop\s+table',  # SQL注入
            r';\s*drop\s+',  # SQL注入
        ]

        for pattern in suspicious_patterns:
            if re.search(pattern, message, re.IGNORECASE):
                return False, "消息包含不允许的内容"

        return True, ""

    @staticmethod
    def validate_goal(goal: str) -> tuple[bool, str]:
        """验证目标输入"""
        if not goal or not goal.strip():
            return False, "目标不能为空"

        if len(goal) > InputValidator.MAX_GOAL_LENGTH:
            return False, f"目标长度不能超过 {InputValidator.MAX_GOAL_LENGTH} 字符"

        return True, ""

    @staticmethod
    def validate_filename(filename: str) -> tuple[bool, str]:
        """验证文件名"""
        if not filename:
            return False, "文件名不能为空"

        if len(filename) > InputValidator.MAX_FILENAME_LENGTH:
            return False, f"文件名长度不能超过 {InputValidator.MAX_FILENAME_LENGTH} 字符"

        # 检查路径遍历攻击
        if '..' in filename or '/' in filename or '\\' in filename:
            return False, "文件名包含非法字符"

        # 检查空字节
        if '\x00' in filename:
            return False, "文件名包含非法字符"

        return True, ""

    @staticmethod
    def validate_file_extension(filename: str, allowed_extensions: set) -> tuple[bool, str]:
        """验证文件扩展名"""
        ext = Path(filename).suffix.lower()

        if ext in InputValidator.DANGEROUS_EXTENSIONS:
            return False, f"不允许上传 {ext} 类型的文件"

        if ext not in allowed_extensions:
            return False, f"不支持的文件类型: {ext}，支持: {', '.join(sorted(allowed_extensions))}"

        return True, ""

    @staticmethod
    def sanitize_input(text: str) -> str:
        """清理输入，防止XSS"""
        if not text:
            return ""

        # 移除HTML标签
        text = re.sub(r'<[^>]+>', '', text)

        # 转义特殊字符
        text = text.replace('&', '&amp;')
        text = text.replace('<', '&lt;')
        text = text.replace('>', '&gt;')
        text = text.replace('"', '&quot;')
        text = text.replace("'", '&#x27;')

        return text.strip()


# ── SQL注入防护 ──────────────────────────────────────────────

class SQLSanitizer:
    """SQL注入防护"""

    # 危险的SQL关键词
    DANGEROUS_KEYWORDS = {
        'drop', 'delete', 'truncate', 'alter', 'create', 'insert',
        'update', 'exec', 'execute', 'union', 'select', 'from',
        'where', 'or', 'and', 'not', 'in', 'like', 'between',
        'having', 'group', 'order', 'by', 'limit', 'offset'
    }

    @staticmethod
    def sanitize_identifier(identifier: str) -> str:
        """清理标识符（表名、列名）"""
        # 只允许字母、数字、下划线
        if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]*$', identifier):
            raise ValueError(f"无效的标识符: {identifier}")
        return identifier

    @staticmethod
    def sanitize_value(value: Any) -> Any:
        """清理值"""
        if isinstance(value, str):
            # 转义单引号
            value = value.replace("'", "''")
            # 移除空字节
            value = value.replace('\x00', '')
        return value

    @staticmethod
    def validate_query(query: str) -> tuple[bool, str]:
        """验证查询是否安全"""
        query_lower = query.lower()

        # 检查是否有多个语句
        if ';' in query and any(kw in query_lower for kw in ['drop', 'delete', 'insert', 'update']):
            return False, "查询包含多个语句"

        # 检查是否有注释
        if '--' in query or '/*' in query:
            return False, "查询包含注释"

        return True, ""


# ── 文件安全 ──────────────────────────────────────────────────

class FileSecurity:
    """文件安全检查"""

    # 文件大小限制（字节）
    MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB
    MAX_IMAGE_SIZE = 10 * 1024 * 1024  # 10MB

    # 文件头魔数
    FILE_SIGNATURES = {
        '.csv': [b'\xef\xbb\xbf', b'\xff\xfe', b'\xfe\xff'],  # BOM
        '.xlsx': [b'PK\x03\x04'],  # ZIP格式
        '.xls': [b'\xd0\xcf\x11\xe0'],  # OLE2格式
        '.json': [b'{', b'['],  # JSON格式
        '.png': [b'\x89PNG'],
        '.jpg': [b'\xff\xd8\xff'],
        '.gif': [b'GIF87a', b'GIF89a'],
    }

    @staticmethod
    def check_file_size(size: int, max_size: int = None) -> tuple[bool, str]:
        """检查文件大小"""
        max_size = max_size or FileSecurity.MAX_FILE_SIZE

        if size > max_size:
            return False, f"文件大小超过限制: {size / 1024 / 1024:.1f}MB > {max_size / 1024 / 1024:.1f}MB"

        if size == 0:
            return False, "文件为空"

        return True, ""

    @staticmethod
    def check_file_content(content: bytes, expected_ext: str) -> tuple[bool, str]:
        """检查文件内容是否匹配扩展名"""
        if expected_ext not in FileSecurity.FILE_SIGNATURES:
            return True, ""  # 没有签名检查，跳过

        signatures = FileSecurity.FILE_SIGNATURES[expected_ext]

        # 检查文件头
        for sig in signatures:
            if content.startswith(sig):
                return True, ""

        # 对于CSV和JSON，可能没有明确的文件头
        if expected_ext in ('.csv', '.json'):
            try:
                # 尝试解码
                content.decode('utf-8')
                return True, ""
            except UnicodeDecodeError:
                pass

        return False, f"文件内容与扩展名 {expected_ext} 不匹配"


# ── Token安全 ──────────────────────────────────────────────────

class TokenSecurity:
    """Token安全管理"""

    @staticmethod
    def generate_token(length: int = 32) -> str:
        """生成安全的随机Token"""
        return secrets.token_urlsafe(length)

    @staticmethod
    def hash_token(token: str) -> str:
        """对Token进行哈希"""
        return hashlib.sha256(token.encode()).hexdigest()

    @staticmethod
    def mask_sensitive(value: str, show_chars: int = 4) -> str:
        """脱敏敏感信息"""
        if not value:
            return ""

        if len(value) <= show_chars:
            return "*" * len(value)

        return value[:show_chars] + "*" * (len(value) - show_chars)


# ── Rate Limiting ──────────────────────────────────────────────

class RateLimiter:
    """简单的速率限制器"""

    def __init__(self):
        self._requests = {}  # {ip: [(timestamp, count), ...]}

    def check(self, key: str, max_requests: int = 100, window_seconds: int = 60) -> tuple[bool, str]:
        """检查速率限制"""
        import time

        now = time.time()

        if key not in self._requests:
            self._requests[key] = []

        # 清理过期记录
        self._requests[key] = [
            (ts, count) for ts, count in self._requests[key]
            if now - ts < window_seconds
        ]

        # 计算当前窗口内的请求数
        total_requests = sum(count for _, count in self._requests[key])

        if total_requests >= max_requests:
            return False, f"请求过于频繁，请稍后再试"

        # 记录本次请求
        self._requests[key].append((now, 1))

        return True, ""


# ── 全局实例 ──────────────────────────────────────────────────

input_validator = InputValidator()
sql_sanitizer = SQLSanitizer()
file_security = FileSecurity()
token_security = TokenSecurity()
rate_limiter = RateLimiter()
