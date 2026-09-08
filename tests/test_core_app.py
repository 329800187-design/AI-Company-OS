"""Core App 最小测试 — 验证 Core 分发版路由和导入"""
import pytest
import os
from fastapi.testclient import TestClient


def test_core_app_import():
    """验证 import backend.core_app 成功"""
    import backend.core_app
    assert backend.core_app is not None
    assert backend.core_app.app is not None


def test_core_app_has_required_routes():
    """验证 core_app 包含所有必需的路由"""
    from backend.core_app import app
    client = TestClient(app)

    assert client.get("/health").status_code == 200
    assert client.get("/boss/templates").status_code == 200
    assert client.get("/agents/discovered").status_code == 200


def test_core_app_excludes_legacy_routes():
    """验证 core_app 不包含旧系统路由"""
    from backend.core_app import app

    client = TestClient(app)

    assert client.post("/pipeline/execute", json={}).status_code == 404


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
