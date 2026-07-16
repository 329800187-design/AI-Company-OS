"""
AI Company OS — 后端运行验收脚本 (Smoke Check)

用法:
    python scripts/backend_smoke_check.py                    # 检查 localhost:8000
    python scripts/backend_smoke_check.py --port 8000        # 指定端口
    python scripts/backend_smoke_check.py --host 127.0.0.1   # 指定主机

不依赖 AI API Key，不触发长任务或浏览器自动化。
"""

import argparse
import json
import sys
import time
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

# ── 配置 ──────────────────────────────────────────────────────────────────────

ENDPOINTS = [
    # (描述, 方法, 路径, 预期状态码)
    ("Health Check", "GET", "/health", 200),
    ("Auth Info", "GET", "/auth/info", 200),
    ("System Info", "GET", "/system/info", 200),
    ("Memory Recent", "GET", "/memory/recent?limit=3", 200),
    ("Memory Search", "GET", "/memory/search?q=test&limit=3", 200),
    ("Boss Missions List", "GET", "/boss/missions?limit=3&offset=0", 200),
    ("Boss Templates", "GET", "/boss/templates", 200),
    ("Boss Module Definitions", "GET", "/boss/modules/definitions", 200),
]

# 需要前置数据的端点，在 mission_id 获取后追加
MISSION_ENDPOINTS = [
    ("Boss Mission Detail", "GET", "/boss/missions/{id}", 200),
    ("Boss Mission Export JSON", "GET", "/boss/missions/{id}/export?format=json", 200),
    ("Boss Mission Events", "GET", "/boss/missions/{id}/events", 200),
]


# ── 工具函数 ──────────────────────────────────────────────────────────────────

class Colors:
    PASS = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    INFO = "\033[96m"
    RESET = "\033[0m"
    BOLD = "\033[1m"


def _c(color: str, text: str) -> str:
    try:
        return f"{color}{text}{Colors.RESET}"
    except Exception:
        return text


def _request(base_url: str, path: str, method: str = "GET", timeout: int = 5):
    """发送 HTTP 请求，返回 (status_code, body_text, error_msg)。"""
    url = f"{base_url}{path}"
    req = Request(url, method=method, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, body, None
    except HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, body, str(e)
    except URLError as e:
        return 0, "", f"Connection failed: {e.reason}"
    except Exception as e:
        return 0, "", str(e)


def _parse_json(text: str):
    """尝试解析 JSON，失败返回 None。"""
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


# ── 主逻辑 ──────────────────────────────────────────────────────────────────

def run_smoke_check(host: str, port: int) -> bool:
    base_url = f"http://{host}:{port}"
    passed = 0
    failed = 0
    warnings = 0
    mission_id = None

    print()
    print(_c(Colors.BOLD, f"  AI Company OS — Smoke Check"))
    print(_c(Colors.INFO, f"  Target: {base_url}"))
    print()

    # ── 1. 基础端点检查 ──
    print(_c(Colors.BOLD, "  ── 基础端点 ──"))
    for desc, method, path, expected_status in ENDPOINTS:
        status, body, err = _request(base_url, path, method)
        data = _parse_json(body)

        if err:
            print(f"  {_c(Colors.FAIL, 'FAIL')}  {desc}")
            print(f"        {err}")
            failed += 1
        elif status != expected_status:
            print(f"  {_c(Colors.FAIL, 'FAIL')}  {desc}")
            print(f"        Expected {expected_status}, got {status}")
            failed += 1
        else:
            print(f"  {_c(Colors.PASS, 'PASS')}  {desc}")
            passed += 1

            # 从 missions 列表中提取第一个 mission_id
            if path.startswith("/boss/missions") and "limit=" in path and data:
                missions = data.get("missions", [])
                if missions and isinstance(missions, list) and len(missions) > 0:
                    mission_id = missions[0].get("mission_id")

    # ── 2. Mission 详情端点（需要 mission_id）──
    if mission_id:
        print()
        print(_c(Colors.BOLD, f"  ── Mission 详情 (id={mission_id[:8]}...) ──"))
        for desc, method, tpl, expected_status in MISSION_ENDPOINTS:
            path = tpl.replace("{id}", mission_id)
            status, body, err = _request(base_url, path, method)
            data = _parse_json(body)

            if err:
                print(f"  {_c(Colors.FAIL, 'FAIL')}  {desc}")
                print(f"        {err}")
                failed += 1
            elif status != expected_status:
                print(f"  {_c(Colors.FAIL, 'FAIL')}  {desc}")
                print(f"        Expected {expected_status}, got {status}")
                failed += 1
            else:
                print(f"  {_c(Colors.PASS, 'PASS')}  {desc}")
                passed += 1

                # 检查 export 返回 JSON
                if "export" in path and "json" in path:
                    export_data = _parse_json(body)
                    if export_data and "mission_id" in export_data:
                        print(f"        {_c(Colors.PASS, 'OK')}  Export contains mission_id")
                    else:
                        print(f"        {_c(Colors.WARN, 'WARN')}  Export response may be blob, not JSON object")
                        warnings += 1
    else:
        print()
        print(_c(Colors.WARN, "  SKIP  Mission 详情端点 — 无可用 mission"))

    # ── 3. 响应结构校验 ──
    print()
    print(_c(Colors.BOLD, "  ── 响应结构校验 ──"))

    # 检查 memory/recent 结构
    _, body, _ = _request(base_url, "/memory/recent?limit=1")
    data = _parse_json(body)
    if data and "memories" in data and "count" in data:
        print(f"  {_c(Colors.PASS, 'PASS')}  /memory/recent — 含 memories + count")
        passed += 1
    else:
        print(f"  {_c(Colors.FAIL, 'FAIL')}  /memory/recent — 缺少 memories 或 count 字段")
        failed += 1

    # 检查 boss/missions 结构
    _, body, _ = _request(base_url, "/boss/missions?limit=1")
    data = _parse_json(body)
    if data and "missions" in data and "total" in data:
        print(f"  {_c(Colors.PASS, 'PASS')}  /boss/missions — 含 missions + total")
        passed += 1
    else:
        print(f"  {_c(Colors.FAIL, 'FAIL')}  /boss/missions — 缺少 missions 或 total 字段")
        failed += 1

    # 检查 templates 结构
    _, body, _ = _request(base_url, "/boss/templates")
    data = _parse_json(body)
    if data and "templates" in data and "total" in data:
        tpl_count = len(data["templates"])
        print(f"  {_c(Colors.PASS, 'PASS')}  /boss/templates — 含 {tpl_count} 个模板")
        passed += 1
    else:
        print(f"  {_c(Colors.FAIL, 'FAIL')}  /boss/templates — 缺少 templates 或 total 字段")
        failed += 1

    # ── 汇总 ──
    total = passed + failed + warnings
    print()
    print(_c(Colors.BOLD, "  ── 汇总 ──"))
    print(f"  {_c(Colors.PASS, f'PASS: {passed}')}  {_c(Colors.FAIL, f'FAIL: {failed}')}  {_c(Colors.WARN, f'WARN: {warnings}')}  Total: {total}")
    print()

    if failed == 0:
        print(_c(Colors.PASS + Colors.BOLD, "  [OK] 所有检查通过"))
    else:
        print(_c(Colors.FAIL + Colors.BOLD, f"  [FAIL] {failed} 项检查失败"))

    print()
    return failed == 0


# ── 入口 ──────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="AI Company OS 后端运行验收")
    parser.add_argument("--host", default="127.0.0.1", help="后端主机 (默认 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="后端端口 (默认 8000)")
    args = parser.parse_args()

    success = run_smoke_check(args.host, args.port)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
