"""Core App 最小测试 — 验证 Core 分发版路由和导入"""
import pytest
import os
from fastapi.testclient import TestClient


def test_core_console_html_contains_echo_endpoint():
    """验证 core_console.html 包含 Echo Agent 端点"""
    html_path = os.path.join(
        os.path.dirname(__file__), '..',
        'dist', 'ai-company-os-core-v0.1-alpha', 'docs', 'core_console.html'
    )
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert '/agents/example_echo/execute' in content, "HTML should contain /agents/example_echo/execute endpoint"


def test_core_console_html_contains_governance_endpoint():
    """验证 core_console.html 包含 Governance 端点"""
    html_path = os.path.join(
        os.path.dirname(__file__), '..',
        'dist', 'ai-company-os-core-v0.1-alpha', 'docs', 'core_console.html'
    )
    with open(html_path, 'r', encoding='utf-8') as f:
        content = f.read()

    assert '/governance/run' in content, "HTML should contain /governance/run endpoint"


def test_core_app_import():
    """验证 import backend.core_app 成功"""
    import backend.core_app
    assert backend.core_app is not None
    assert backend.core_app.app is not None


def test_core_app_has_required_routes():
    """验证 core_app 包含所有必需的路由"""
    from backend.core_app import app

    route_paths = [route.path for route in app.routes]

    # 必需的 Core 路由
    assert "/health" in route_paths, "Missing /health"
    assert "/governance/run" in route_paths, "Missing /governance/run"
    assert "/agents/discovered" in route_paths, "Missing /agents/discovered"
    assert "/agents/{agent_id}/execute" in route_paths, "Missing /agents/{agent_id}/execute"
    assert "/collaboration/plan" in route_paths, "Missing /collaboration/plan"


def test_core_app_excludes_legacy_routes():
    """验证 core_app 不包含旧系统路由"""
    from backend.core_app import app

    route_paths = [route.path for route in app.routes]

    # 不应包含的旧路由；Boss Command Center 已在 Core 入口中保留。
    assert "/pipeline/execute" not in route_paths, "Should not include /pipeline/execute"


def test_health_endpoint():
    """验证 /health 端点正常工作"""
    from backend.core_app import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["mode"] == "core"
    assert "version" in data
    assert "timestamp" in data


def test_agents_discovered_endpoint():
    """验证 /agents/discovered 端点正常工作"""
    from backend.core_app import app

    client = TestClient(app)
    response = client.get("/agents/discovered")

    assert response.status_code == 200
    data = response.json()
    assert "agents" in data
    assert "total" in data
    assert "enabled_count" in data


def test_collaboration_plan_endpoint():
    """验证 /collaboration/plan 端点正常工作"""
    from backend.core_app import app

    client = TestClient(app)
    response = client.post("/collaboration/plan", json={
        "goal": "测试目标",
        "steps": [
            {
                "name": "步骤1",
                "task_type": "copywriting",
                "required_capability": "copywriting"
            }
        ]
    })

    assert response.status_code == 200
    data = response.json()
    assert "plan_id" in data
    assert "steps" in data
    assert "status" in data
