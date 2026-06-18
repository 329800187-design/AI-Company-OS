"""
共享 HTTP 客户端 — 连接池复用，避免每个 Agent 重复创建 TLS 连接
"""
import httpx

_client: httpx.Client | None = None

def get_shared_client() -> httpx.Client:
    """获取全局共享的 httpx Client（连接池 + keep-alive）"""
    global _client
    if _client is None or _client.is_closed:
        _client = httpx.Client(
            timeout=httpx.Timeout(60),
            proxy=None,
            trust_env=False,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20),
        )
    return _client

def close_shared_client():
    """关闭共享客户端"""
    global _client
    if _client and not _client.is_closed:
        _client.close()
    _client = None
