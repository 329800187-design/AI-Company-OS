"""
Phase 5.5 — 本地部署体检脚本 (Local Healthcheck)

用法:
    python scripts/healthcheck_local.py                     # 默认检查 localhost:8000 + 前端 5173
    python scripts/healthcheck_local.py --port 8001         # 指定后端端口
    python scripts/healthcheck_local.py --frontend-port 3000 # 指定前端端口
    python scripts/healthcheck_local.py --skip-frontend      # 跳过前端检查
    python scripts/healthcheck_local.py --with-providers     # 同时运行 verify_real_providers.py
    python scripts/healthcheck_local.py --json               # 仅输出 JSON

退出码:
    0 — 所有必须检查通过（skipped 算通过）
    1 — 有检查失败
"""
import argparse
import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError


# ── 颜色 ──────────────────────────────────────────────────────────────

class C:
    OK = "\033[92m"
    FAIL = "\033[91m"
    WARN = "\033[93m"
    INFO = "\033[96m"
    DIM = "\033[2m"
    BOLD = "\033[1m"
    R = "\033[0m"


def _c(color, text):
    try:
        return f"{color}{text}{C.R}"
    except Exception:
        return text


# ── HTTP 工具 ─────────────────────────────────────────────────────────

def _get(url, timeout=8):
    """GET 请求，返回 (status, json_data, error)"""
    req = Request(url, headers={"Accept": "application/json"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, _parse_json(raw), None
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, _parse_json(raw), str(e)
    except URLError as e:
        return 0, None, f"Connection refused: {e.reason}"
    except Exception as e:
        return 0, None, str(e)


def _parse_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def _port_open(host, port, timeout=2):
    """检查端口是否可连接"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, socket.timeout):
        return False


# ── 检查项 ────────────────────────────────────────────────────────────

def check_backend_health(base_url):
    """检查 GET /health"""
    t0 = time.time()
    status, data, err = _get(f"{base_url}/health", timeout=5)
    elapsed = round(time.time() - t0, 2)

    if err:
        return {
            "name": "backend_health",
            "status": "fail",
            "detail": err,
            "fix": "后端未启动。运行: uvicorn backend.app:app --reload --port 8000",
        }

    if status == 200:
        return {
            "name": "backend_health",
            "status": "pass",
            "detail": f"HTTP {status} ({elapsed}s)",
        }

    return {
        "name": "backend_health",
        "status": "fail",
        "detail": f"HTTP {status} ({elapsed}s)",
        "fix": "后端返回异常状态码，检查日志",
    }


def check_providers_health(base_url):
    """检查 GET /config/providers/health"""
    status, data, err = _get(f"{base_url}/config/providers/health", timeout=5)

    if err:
        return {
            "name": "providers_health",
            "status": "fail",
            "detail": err,
            "fix": "确保后端已启动且 /config 路由已注册",
        }

    if status != 200:
        return {
            "name": "providers_health",
            "status": "fail",
            "detail": f"HTTP {status}",
        }

    search = data.get("search", {})
    image = data.get("image", {})
    search_mock = search.get("is_mock", True)
    image_mock = image.get("is_mock", True)

    detail_parts = []
    if search_mock:
        detail_parts.append("搜索=mock")
    else:
        detail_parts.append(f"搜索={search.get('name', '?')}")
    if image_mock:
        detail_parts.append("图片=mock")
    else:
        detail_parts.append(f"图片={image.get('name', '?')}")

    return {
        "name": "providers_health",
        "status": "pass",
        "detail": "，".join(detail_parts),
        "search_mock": search_mock,
        "image_mock": image_mock,
    }


def check_frontend(host, port):
    """检查前端 dev server 是否在运行"""
    if not _port_open(host, port):
        return {
            "name": "frontend_dev_server",
            "status": "skip",
            "detail": f"端口 {port} 未监听，前端未启动（非必须）",
        }

    # 端口开了，尝试 GET /
    url = f"http://{host}:{port}/"
    try:
        req = Request(url, headers={"Accept": "text/html"})
        with urlopen(req, timeout=5) as resp:
            if resp.status == 200:
                return {
                    "name": "frontend_dev_server",
                    "status": "pass",
                    "detail": f"Vite dev server 运行中 (port {port})",
                }
    except Exception:
        pass

    return {
        "name": "frontend_dev_server",
        "status": "warn",
        "detail": f"端口 {port} 已监听但无法获取页面",
    }


def check_minidelivery_list(base_url):
    """检查 GET /minidelivery/tasks"""
    # An upgraded installation may need to create its incremental metadata
    # index from historical result.json files on the first request only.
    status, data, err = _get(f"{base_url}/minidelivery/tasks?limit=1", timeout=120)

    if err:
        return {
            "name": "minidelivery_list",
            "status": "fail",
            "detail": err,
            "fix": "确保后端已启动且 /minidelivery 路由已注册",
        }

    if status != 200:
        return {
            "name": "minidelivery_list",
            "status": "fail",
            "detail": f"HTTP {status}",
        }

    total = data.get("total", 0)
    return {
        "name": "minidelivery_list",
        "status": "pass",
        "detail": f"共 {total} 个交付物",
    }


def check_pdf_endpoint(base_url):
    """检查 GET /minidelivery/tasks/{fake_id}/pdf — 预期 404 而非 500"""
    fake_id = "_healthcheck_probe_"
    status, data, err = _get(f"{base_url}/minidelivery/tasks/{fake_id}/pdf", timeout=5)

    if err and "Connection refused" in str(err):
        return {
            "name": "pdf_endpoint",
            "status": "fail",
            "detail": err,
            "fix": "确保后端已启动",
        }

    # 预期 404（task 不存在），说明路由正常
    if status == 404:
        if isinstance(data, dict) and data.get("detail") == "Not Found":
            return {
                "name": "pdf_endpoint",
                "status": "fail",
                "detail": "HTTP 404 Not Found（PDF 路由未注册）",
                "fix": "确认已部署 Phase 5.1 的 /minidelivery/tasks/{task_id}/pdf 路由",
            }
        return {
            "name": "pdf_endpoint",
            "status": "pass",
            "detail": "路由可达（404 = task 不存在，符合预期）",
        }

    # 500 说明路由有 bug
    if status == 500:
        return {
            "name": "pdf_endpoint",
            "status": "fail",
            "detail": "PDF 端点返回 500 内部错误",
            "fix": "检查 backend/services/pdf_service.py 依赖是否安装",
        }

    return {
        "name": "pdf_endpoint",
        "status": "pass",
        "detail": f"HTTP {status}（路由可达）",
    }


def run_provider_verification(base_url, timeout):
    """可选：运行 verify_real_providers.py 并汇总"""
    script = Path(__file__).parent / "verify_real_providers.py"
    parsed = urlparse(base_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 8000
    if not script.exists():
        return {
            "name": "provider_verification",
            "status": "skip",
            "detail": "verify_real_providers.py 不存在",
        }

    try:
        result = subprocess.run(
            [sys.executable, str(script), "--json", "--host", host, "--port", str(port)],
            capture_output=True, text=True, timeout=timeout + 10,
            cwd=str(script.parent.parent),
        )
        output = _parse_json(result.stdout)
        if output and "summary" in output:
            s = output["summary"]
            return {
                "name": "provider_verification",
                "status": "pass" if s.get("all_passed") else "fail",
                "detail": f"PASS:{s['passed']} FAIL:{s['failed']} SKIP:{s['skipped']}",
                "raw": output,
            }
        return {
            "name": "provider_verification",
            "status": "fail",
            "detail": f"脚本输出异常: {result.stderr[:200]}",
        }
    except subprocess.TimeoutExpired:
        return {
            "name": "provider_verification",
            "status": "fail",
            "detail": "verify_real_providers.py 超时",
        }
    except Exception as e:
        return {
            "name": "provider_verification",
            "status": "fail",
            "detail": str(e),
        }


# ── 汇总与输出 ───────────────────────────────────────────────────────

def build_summary(results):
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    warned = sum(1 for r in results if r["status"] == "warn")
    skipped = sum(1 for r in results if r["status"] == "skip")
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "warned": warned,
        "skipped": skipped,
        "all_passed": failed == 0,
    }


def print_report(results, summary):
    print()
    print(_c(C.BOLD, "  ═══ Phase 5.5 — 本地部署体检 ═══"))
    print()

    for r in results:
        icon = {
            "pass": _c(C.OK, "  ✓ PASS"),
            "fail": _c(C.FAIL, "  ✗ FAIL"),
            "warn": _c(C.WARN, "  ⚠ WARN"),
            "skip": _c(C.DIM, "  – SKIP"),
        }.get(r["status"], "  ?")

        name = r["name"]
        detail = r.get("detail", "")
        print(f"{icon}  {name}")
        if detail:
            print(f"        {detail}")
        if r.get("fix"):
            print(f"        {_c(C.WARN, '→ 修复:')} {r['fix']}")

    print()
    print(_c(C.BOLD, "  ── 汇总 ──"))
    p = _c(C.OK, f"PASS:{summary['passed']}")
    f = _c(C.FAIL, f"FAIL:{summary['failed']}")
    w = _c(C.WARN, f"WARN:{summary['warned']}")
    s = _c(C.DIM, f"SKIP:{summary['skipped']}")
    print(f"  {p}  {f}  {w}  {s}  Total:{summary['total']}")
    print()

    if summary["all_passed"]:
        print(_c(C.OK + C.BOLD, "  [OK] 本地部署正常"))
    else:
        print(_c(C.FAIL + C.BOLD, f"  [FAIL] {summary['failed']} 项异常"))
    print()


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Phase 5.5 — 本地部署体检")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000, help="后端端口 (默认 8000)")
    parser.add_argument("--frontend-port", type=int, default=5173, help="前端端口 (默认 5173)")
    parser.add_argument("--skip-frontend", action="store_true", help="跳过前端检查")
    parser.add_argument("--with-providers", action="store_true", help="同时运行 verify_real_providers.py")
    parser.add_argument("--timeout", type=int, default=30, help="Provider 验证超时秒数")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON")
    args = parser.parse_args()

    base_url = f"http://{args.host}:{args.port}"
    results = []

    # 1. 后端 /health
    results.append(check_backend_health(base_url))

    # 2. /config/providers/health
    if results[-1]["status"] == "pass":
        results.append(check_providers_health(base_url))
    else:
        results.append({
            "name": "providers_health",
            "status": "skip",
            "detail": "后端未就绪，跳过",
        })

    # 3. 前端 dev server
    if not args.skip_frontend:
        results.append(check_frontend(args.host, args.frontend_port))

    # 4. MiniDelivery list
    if results[0]["status"] == "pass":
        results.append(check_minidelivery_list(base_url))
    else:
        results.append({
            "name": "minidelivery_list",
            "status": "skip",
            "detail": "后端未就绪，跳过",
        })

    # 5. PDF endpoint
    if results[0]["status"] == "pass":
        results.append(check_pdf_endpoint(base_url))
    else:
        results.append({
            "name": "pdf_endpoint",
            "status": "skip",
            "detail": "后端未就绪，跳过",
        })

    # 6. 可选：运行 verify_real_providers.py
    if args.with_providers and results[0]["status"] == "pass":
        results.append(run_provider_verification(base_url, args.timeout))

    summary = build_summary(results)

    if args.json:
        print(json.dumps({"results": results, "summary": summary}, ensure_ascii=False, indent=2))
    else:
        print_report(results, summary)

    sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
