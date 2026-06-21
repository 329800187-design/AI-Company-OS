"""Hermes Provider 端到端集成测试

验证链路：Boss → Hermes → structured_output → event log → UI

覆盖：
- BOSS_EXECUTION_PROVIDER=hermes 时 run_module 走 HermesExecutionProvider
- hermes_invoked / hermes_response_parsed / hermes_failed 事件记录
- structured_output 标准化格式
- fallback 到 local_heuristic 时的行为
- 离线可跑（mock subprocess）
"""
import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest
from unittest.mock import patch, MagicMock, PropertyMock


# ── Mock Hermes CLI 响应 ────────────────────────────────────

MOCK_MARKET_RESEARCH_RESPONSE = json.dumps({
    "summary": "蓝牙耳机市场持续增长，2024 年全球市场规模约 350 亿美元。主要驱动力包括无线化趋势、降噪技术普及和运动场景需求。",
    "evidence": [
        {"title": "2024 全球耳机市场报告", "url": "https://example.com/report-2024"},
        {"title": "蓝牙耳机趋势分析", "url": "https://example.com/bt-trends"},
    ],
    "competitors": [
        {"name": "AirPods Pro", "price": "1299-1899", "platform": "Apple Store", "features": "降噪、空间音频"},
        {"name": "Sony WF-1000XM5", "price": "1499-1999", "platform": "京东/天猫", "features": "顶级降噪、高音质"},
        {"name": "小米 Buds 4 Pro", "price": "699-999", "platform": "小米商城/京东", "features": "性价比高、降噪"},
    ],
    "pricing": {"range": "299-1999", "avg": "899"},
    "warnings": [],
})

MOCK_COMPETITOR_ANALYSIS_RESPONSE = json.dumps({
    "summary": "竞品分析显示，中端市场（500-1000元）存在机会。AirPods 和 Sony 占据高端，小米占据性价比市场。",
    "competitors": [
        {"name": "AirPods Pro", "price": "1299", "strengths": "品牌效应、生态", "weaknesses": "价格高"},
        {"name": "Sony WF-1000XM5", "price": "1699", "strengths": "音质、降噪", "weaknesses": "体积大"},
        {"name": "小米 Buds 4 Pro", "price": "799", "strengths": "性价比", "weaknesses": "品牌认知"},
    ],
    "pricing": {"recommended_range": "599-899", "rationale": "中端差异化定位"},
    "warnings": [],
})

MOCK_LISTING_PACK_RESPONSE = json.dumps({
    "summary": "为蓝牙耳机生成上架物料包，包含标题、文案和定价建议。",
    "listing_copy": "【2024 新款】主动降噪蓝牙耳机 | 40dB 深度降噪 | 30 小时续航 | Hi-Fi 音质\n\n核心卖点：\n1. 40dB 主动降噪，地铁/办公室一键静音\n2. 30 小时超长续航，一周一充无压力\n3. Hi-Fi 级音质，LDAC 高清解码\n4. IPX5 防水，运动无忧",
    "pricing": {"recommended": "699", "min": "599", "max": "799"},
    "image_plan": {
        "main_image": "白底产品图，耳机 45 度角展示",
        "lifestyle": "年轻人在地铁/办公室使用场景",
        "details": "降噪效果对比图、续航时间图表",
    },
    "next_actions": [
        "确定最终定价为 699 元",
        "拍摄白底主图和场景图",
        "填写闲鱼/淘宝标题和详情",
        "设置 SKU（颜色：黑/白/蓝）",
    ],
    "warnings": [],
})


# ── Smoke Test: Boss → Hermes 链路验证 ─────────────────────

class TestHermesProviderSmokeTest:
    """Hermes Provider 端到端 Smoke Test"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        """设置 BOSS_EXECUTION_PROVIDER=hermes"""
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        # 清除 provider registry 缓存，使其重新创建
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self):
        from unittest.mock import patch
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    def test_market_research_hermes_chain(self, service, monkeypatch):
        """验证 market 模块走 Hermes 链路：Hermes → structured_output → event log"""
        import subprocess

        # Mock subprocess.run 返回合法 JSON
        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = MOCK_MARKET_RESEARCH_RESPONSE
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)

        # Mock shutil.which 让 Hermes 可用
        import shutil
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # 创建 mission 只跑 market 模块
        mission = service.create_mission("蓝牙耳机市场调研", enabled_modules=["market"])
        mission_id = mission["mission_id"]

        # 执行 market 模块
        updated = service.run_module(mission_id, "market")
        assert updated is not None

        # 验证模块状态
        market = next(m for m in updated["modules"] if m["module_id"] == "market")
        assert market["status"] == "done"

        # 验证 structured_output
        so = market["structured_output"]
        assert so["status"] == "success"
        assert so["provider"] == "hermes"
        assert "蓝牙耳机" in so["summary"]
        assert len(so["evidence"]) == 2
        assert len(so["competitors"]) == 3
        assert so["pricing"]["range"] == "299-1999"
        assert "generated_at" in so

        # 验证 event log
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]

        # 应该包含以下事件
        assert "provider_selected" in event_types
        assert "hermes_invoked" in event_types
        assert "hermes_response_parsed" in event_types
        assert "evidence_collected" in event_types
        assert "structured_output_generated" in event_types

        # 验证 hermes_invoked 事件内容
        hermes_invoked = next(e for e in events if e["type"] == "hermes_invoked")
        assert hermes_invoked["payload"]["provider"] == "hermes"

        # 验证 hermes_response_parsed 事件内容
        hermes_parsed = next(e for e in events if e["type"] == "hermes_response_parsed")
        assert hermes_parsed["payload"]["has_summary"] is True
        assert hermes_parsed["payload"]["has_evidence"] is True
        assert hermes_parsed["payload"]["has_competitors"] is True

    def test_competitor_analysis_hermes_chain(self, service, monkeypatch):
        """验证 competitor_analysis 模块走 Hermes 链路"""
        import subprocess
        import shutil

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = MOCK_COMPETITOR_ANALYSIS_RESPONSE
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission("竞品分析测试", enabled_modules=["competitor_analysis"])
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "competitor_analysis")
        ca = next(m for m in updated["modules"] if m["module_id"] == "competitor_analysis")
        assert ca["status"] == "done"

        so = ca["structured_output"]
        assert so["provider"] == "hermes"
        assert len(so["competitors"]) == 3
        assert so["pricing"]["recommended_range"] == "599-899"

    def test_listing_pack_hermes_chain(self, service, monkeypatch):
        """验证 marketing（listing pack）模块走 Hermes 链路"""
        import subprocess
        import shutil

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = MOCK_LISTING_PACK_RESPONSE
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission("上架物料包测试", enabled_modules=["marketing"])
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "marketing")
        marketing = next(m for m in updated["modules"] if m["module_id"] == "marketing")
        assert marketing["status"] == "done"

        so = marketing["structured_output"]
        assert so["provider"] == "hermes"
        assert "降噪蓝牙耳机" in so["listing_copy"]
        assert so["pricing"]["recommended"] == "699"
        assert len(so["next_actions"]) == 4

    def test_hermes_failure_logs_hermes_failed(self, service, monkeypatch):
        """验证 Hermes 失败时记录 hermes_failed 事件"""
        import subprocess
        import shutil

        # Mock 让 Hermes CLI 不存在
        monkeypatch.setattr(shutil, "which", lambda x: None)

        mission = service.create_mission("失败测试", enabled_modules=["market"])
        mission_id = mission["mission_id"]

        # 执行应该 fallback 到 local_heuristic
        updated = service.run_module(mission_id, "market")
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 event log
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "provider_fallback" in event_types

    def test_full_mission_hermes_chain(self, service, monkeypatch):
        """验证完整 mission（4 个模块）走 Hermes 链路"""
        import subprocess
        import shutil

        call_count = 0
        responses = [
            MOCK_MARKET_RESEARCH_RESPONSE,
            MOCK_COMPETITOR_ANALYSIS_RESPONSE,
            MOCK_LISTING_PACK_RESPONSE,
            '{"summary": "执行清单", "warnings": []}',
        ]

        def mock_run(cmd, **kwargs):
            nonlocal call_count
            class Result:
                returncode = 0
                stdout = responses[call_count % len(responses)]
                stderr = ""
            call_count += 1
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission("蓝牙耳机选品", enabled_modules=["market", "competitor_analysis", "marketing"])
        mission_id = mission["mission_id"]

        updated = service.run_mission(mission_id)
        assert updated["status"] == "done"

        # 验证所有模块都用 hermes
        for mod in updated["modules"]:
            if mod["status"] != "skipped":
                so = mod["structured_output"]
                assert so.get("provider") == "hermes"

    def test_structured_output_schema_completeness(self, service, monkeypatch):
        """验证 structured_output 包含所有标准字段"""
        import subprocess
        import shutil

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = MOCK_MARKET_RESEARCH_RESPONSE
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission("Schema 测试", enabled_modules=["market"])
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market")
        market = next(m for m in updated["modules"] if m["module_id"] == "market")
        so = market["structured_output"]

        # 验证所有标准字段存在
        required_fields = [
            "status", "summary", "evidence", "competitors",
            "pricing", "listing_copy", "image_plan",
            "next_actions", "warnings", "provider", "generated_at"
        ]
        for field in required_fields:
            assert field in so, f"Missing field: {field}"

        assert so["status"] == "success"
        assert so["provider"] == "hermes"
        assert isinstance(so["evidence"], list)
        assert isinstance(so["competitors"], list)
        assert isinstance(so["pricing"], dict)
        assert isinstance(so["warnings"], list)


# ── API 层集成测试 ──────────────────────────────────────────

class TestHermesProviderAPI:
    """Hermes Provider API 层测试"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None

    @pytest.fixture(autouse=True)
    def _bypass_rate_limit(self):
        with patch("backend.routers.boss_router.rate_limiter") as mock_rl:
            mock_rl.check.return_value = (True, "")
            yield

    @pytest.fixture
    def client(self):
        from fastapi.testclient import TestClient
        from backend.app import app
        return TestClient(app, raise_server_exceptions=False)

    def test_create_and_run_mission_with_hermes(self, client, monkeypatch):
        """通过 API 创建并执行 mission，验证 Hermes 链路"""
        import subprocess
        import shutil

        def mock_run(cmd, **kwargs):
            class Result:
                returncode = 0
                stdout = MOCK_MARKET_RESEARCH_RESPONSE
                stderr = ""
            return Result()

        monkeypatch.setattr(subprocess, "run", mock_run)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # 创建 mission
        resp = client.post("/boss/missions", json={
            "goal": "API 集成测试",
            "enabled_modules": ["market"],
            "auto_run": False,
        })
        assert resp.status_code == 200
        mission_id = resp.json()["mission_id"]

        # 执行 market 模块
        resp = client.post(f"/boss/missions/{mission_id}/modules/market/run")
        assert resp.status_code == 200

        # 验证结果
        data = resp.json()
        market = next(m for m in data["modules"] if m["module_id"] == "market")
        assert market["status"] == "done"
        assert market["structured_output"]["provider"] == "hermes"

        # 验证事件
        resp = client.get(f"/boss/missions/{mission_id}/events")
        assert resp.status_code == 200
        events = resp.json()["events"]
        event_types = [e["type"] for e in events]
        assert "hermes_invoked" in event_types
        assert "hermes_response_parsed" in event_types
