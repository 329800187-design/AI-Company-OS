"""
Phase 5.4 — 真实 Provider E2E 验收脚本

用法:
    python scripts/verify_real_providers.py                     # 默认 localhost:8000
    python scripts/verify_real_providers.py --port 8001         # 指定端口
    python scripts/verify_real_providers.py --json              # 仅输出 JSON
    python scripts/verify_real_providers.py --timeout 30        # 自定义超时

环境变量（在 .env 中配置）:
    SERPAPI_API_KEY       — SerpAPI 搜索 key（有则自动验证 research agent）
    BING_SEARCH_API_KEY   — Bing 搜索 key（有则自动验证 research agent）
    OPENAI_API_KEY        — OpenAI key（有则自动验证 image agent）

退出码:
    0 — 所有检查通过（含 skipped）
    1 — 有检查失败
"""
import argparse
import json
import os
import sys
import time
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

def _request(base_url, path, method="GET", body=None, timeout=15):
    """发送 HTTP 请求，返回 (status, json_data, error)"""
    url = f"{base_url}{path}"
    headers = {"Accept": "application/json", "Content-Type": "application/json"}
    data = json.dumps(body).encode() if body else None
    req = Request(url, method=method, headers=headers, data=data)
    try:
        with urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            return resp.status, _parse_json(raw), None
    except HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, _parse_json(raw), str(e)
    except URLError as e:
        return 0, None, f"Connection failed: {e.reason}"
    except Exception as e:
        return 0, None, str(e)


def _parse_json(text):
    try:
        return json.loads(text)
    except (json.JSONDecodeError, ValueError):
        return None


def load_dotenv(path=".env"):
    """Load simple KEY=VALUE pairs from .env without overriding existing env vars."""
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def _first_dict(*values):
    """Return the first dict among provided values."""
    for value in values:
        if isinstance(value, dict):
            return value
    return {}


def _extract_structured_output(data):
    """Extract structured output from unified Agent responses and legacy shapes."""
    if not isinstance(data, dict):
        return {}
    return _first_dict(
        data.get("structured_output"),
        data.get("output"),
        data.get("data"),
    )


def _source_to_url(source):
    """Extract URL from source entries that may be dicts or normalized strings."""
    if isinstance(source, dict):
        return str(source.get("url", ""))
    if isinstance(source, str):
        for part in source.replace("—", " ").split():
            if part.startswith("http://") or part.startswith("https://"):
                return part.strip("),.;")
    return ""


# ── 检查项 ────────────────────────────────────────────────────────────

def check_providers_health(base_url, timeout):
    """Step 1: 检查 /config/providers/health，判断 mock/real 状态"""
    status, data, err = _request(base_url, "/config/providers/health", timeout=timeout)
    if err or status != 200:
        return {
            "name": "providers_health",
            "status": "fail",
            "detail": err or f"HTTP {status}",
            "search": None,
            "image": None,
        }

    search = data.get("search", {})
    image = data.get("image", {})

    return {
        "name": "providers_health",
        "status": "pass",
        "detail": "健康检查端点正常",
        "search": {
            "provider": search.get("name", "unknown"),
            "is_mock": search.get("is_mock", True),
            "has_api_key": search.get("has_api_key", False),
        },
        "image": {
            "provider": image.get("name", "unknown"),
            "is_mock": image.get("is_mock", True),
            "has_api_key": image.get("has_api_key", False),
        },
    }


def check_research_real_sources(base_url, timeout):
    """Step 2: 如果有搜索 key，调用 research agent 验证真实 sources"""
    has_serpapi = bool(os.getenv("SERPAPI_API_KEY"))
    has_bing = bool(os.getenv("BING_SEARCH_API_KEY"))

    if not has_serpapi and not has_bing:
        return {
            "name": "research_real_sources",
            "status": "skipped",
            "detail": "无 SERPAPI_API_KEY / BING_SEARCH_API_KEY，跳过真实搜索验证",
            "sources": [],
        }

    provider_used = "serpapi" if has_serpapi else "bing"
    goal = "2025年手工耳环市场趋势"
    body = {
        "task_id": "",
        "goal": goal,
        "task_type": "research_brief",
        "context": {},
        "input": {"goal": goal, "max_results": 3},
    }

    t0 = time.time()
    status, data, err = _request(base_url, "/agents/research/execute", method="POST", body=body, timeout=timeout)
    elapsed = round(time.time() - t0, 2)

    if err or status != 200:
        return {
            "name": "research_real_sources",
            "status": "fail",
            "detail": err or f"HTTP {status}",
            "elapsed_s": elapsed,
            "provider": provider_used,
            "sources": [],
        }

    # 检查返回的 sources 是否为真实数据（非 mock）
    structured_output = _extract_structured_output(data)
    sources = structured_output.get("sources", data.get("sources", []))
    has_real = any(
        (url := _source_to_url(s)).startswith("http") and "example.com" not in url
        for s in sources
    ) if sources else False

    if has_real:
        return {
            "name": "research_real_sources",
            "status": "pass",
            "detail": f"provider={provider_used}，返回 {len(sources)} 条真实来源",
            "elapsed_s": elapsed,
            "provider": provider_used,
            "sources": [_source_to_url(s) for s in sources[:3]],
        }
    else:
        return {
            "name": "research_real_sources",
            "status": "fail",
            "detail": f"provider={provider_used}，但返回的 sources 仍为 mock 或空",
            "elapsed_s": elapsed,
            "provider": provider_used,
            "sources": sources,
        }


def check_image_generation(base_url, timeout):
    """Step 3: 如果有 OPENAI_API_KEY，调用 image agent 验证 generated_images"""
    has_openai = bool(os.getenv("OPENAI_API_KEY"))

    if not has_openai:
        return {
            "name": "image_generation",
            "status": "skipped",
            "detail": "无 OPENAI_API_KEY，跳过图片生成验证",
            "generated_images": [],
        }

    body = {
        "task_id": "",
        "goal": "生成一张简单的蓝色圆形白底图片",
        "task_type": "image_generate",
        "context": {},
        "input": {
            "prompt": "a simple blue circle on white background",
            "size": "1024x1024",
            "style": "natural",
        },
    }

    t0 = time.time()
    status, data, err = _request(base_url, "/agents/image/execute", method="POST", body=body, timeout=timeout)
    elapsed = round(time.time() - t0, 2)

    if err or status != 200:
        return {
            "name": "image_generation",
            "status": "fail",
            "detail": err or f"HTTP {status}",
            "elapsed_s": elapsed,
            "generated_images": [],
        }

    structured_output = _extract_structured_output(data)
    images = structured_output.get("generated_images", data.get("generated_images", []))
    has_real = any(
        img.get("url", "").startswith("http") and "placehold.co" not in img.get("url", "")
        for img in images
    ) if images else False

    if has_real:
        return {
            "name": "image_generation",
            "status": "pass",
            "detail": f"返回 {len(images)} 张真实图片",
            "elapsed_s": elapsed,
            "generated_images": [img.get("url", "") for img in images[:2]],
        }
    else:
        return {
            "name": "image_generation",
            "status": "fail",
            "detail": "返回的图片仍为 mock 或空",
            "elapsed_s": elapsed,
            "generated_images": images,
        }


# ── 汇总 ─────────────────────────────────────────────────────────────

def build_summary(results):
    """构建人类可读 summary"""
    passed = sum(1 for r in results if r["status"] == "pass")
    failed = sum(1 for r in results if r["status"] == "fail")
    skipped = sum(1 for r in results if r["status"] == "skipped")
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "all_passed": failed == 0,
    }


def print_report(results, summary):
    """打印人类可读报告"""
    print()
    print(_c(C.BOLD, "  ═══ Phase 5.4 — 真实 Provider E2E 验收 ═══"))
    print()

    for r in results:
        icon = {
            "pass": _c(C.OK, "  ✓ PASS"),
            "fail": _c(C.FAIL, "  ✗ FAIL"),
            "skipped": _c(C.DIM, "  – SKIP"),
        }.get(r["status"], "  ?")

        name = r["name"]
        detail = r.get("detail", "")
        elapsed = f'  ({r["elapsed_s"]}s)' if "elapsed_s" in r else ""

        print(f"{icon}  {name}{elapsed}")
        if detail:
            print(f"        {detail}")

        # 额外信息
        if r.get("sources"):
            for s in r["sources"][:3]:
                print(f"        → {s}")
        if r.get("generated_images"):
            for img in r["generated_images"][:2]:
                print(f"        → {img}")

    print()
    print(_c(C.BOLD, "  ── 汇总 ──"))
    p = _c(C.OK, f"PASS: {summary['passed']}")
    f = _c(C.FAIL, f"FAIL: {summary['failed']}")
    s = _c(C.DIM, f"SKIP: {summary['skipped']}")
    print(f"  {p}  {f}  {s}  Total: {summary['total']}")
    print()

    if summary["all_passed"]:
        print(_c(C.OK + C.BOLD, "  [OK] 所有检查通过"))
    else:
        print(_c(C.FAIL + C.BOLD, f"  [FAIL] {summary['failed']} 项检查失败"))
    print()


# ── 入口 ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Phase 5.4 — 真实 Provider E2E 验收")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--timeout", type=int, default=30, help="请求超时秒数")
    parser.add_argument("--json", action="store_true", help="仅输出 JSON（适合 CI）")
    args = parser.parse_args()

    load_dotenv()

    base_url = f"http://{args.host}:{args.port}"
    timeout = args.timeout

    results = [
        check_providers_health(base_url, timeout),
        check_research_real_sources(base_url, timeout),
        check_image_generation(base_url, timeout),
    ]

    summary = build_summary(results)
    output = {"results": results, "summary": summary}

    if args.json:
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print_report(results, summary)

    sys.exit(0 if summary["all_passed"] else 1)


if __name__ == "__main__":
    main()
