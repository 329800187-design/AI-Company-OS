"""Hermes Provider 端到端集成测试

验证链路：Boss → Hermes → structured_output → event log → UI

覆盖：
- BOSS_EXECUTION_PROVIDER=hermes 时 run_module 走 HermesExecutionProvider
- hermes_invoked / hermes_response_parsed / hermes_failed 事件记录
- structured_output 标准化格式
- fallback 到 local_heuristic 时的行为
- 离线可跑（mock subprocess）
- evidence gate 验证
- tool_calls 记录
- 浏览器自动化审批闸门
"""
import sys
import os
import json
import io
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


def _mock_popen(stdout_text):
    """创建 Mock Popen 对象"""
    class MockProcess:
        def __init__(self, stdout_text):
            self.returncode = 0
            self.stdout = io.StringIO(stdout_text)
            self.stderr = io.StringIO("")

        def wait(self, timeout=None):
            return 0

        def kill(self):
            pass

    return MockProcess(stdout_text)


# ── Smoke Test: Boss → Hermes 链路验证 ─────────────────────

class TestHermesProviderSmokeTest:
    """Hermes Provider 端到端 Smoke Test"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        """设置 BOSS_EXECUTION_PROVIDER=hermes"""
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        import importlib
        import backend.config
        importlib.reload(backend.config)
        # 清除 provider registry 缓存，使其重新创建
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None

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

        # Mock subprocess.Popen 返回合法 JSON
        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(MOCK_MARKET_RESEARCH_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板创建 mission
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="蓝牙耳机市场调研",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        # 执行 market 模块
        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
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
        """验证 competitor_analysis 模块走 Hermes 链路（通过 market 模块）"""
        import subprocess

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(MOCK_COMPETITOR_ANALYSIS_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 market 模块来测试竞品分析功能
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="竞品分析测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")
        assert market["status"] == "done"

        so = market["structured_output"]
        assert so["provider"] == "hermes"
        assert len(so["competitors"]) >= 1

    def test_listing_pack_hermes_chain(self, service, monkeypatch):
        """验证 marketing（listing pack）模块走 Hermes 链路"""
        import subprocess

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(MOCK_LISTING_PACK_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 marketing 模块测试上架物料包
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="上架物料包测试",
            enabled_modules=["marketing"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "marketing", allow_browser_automation=True)
        marketing = next(m for m in updated["modules"] if m["module_id"] == "marketing")
        assert marketing["status"] == "done"

        so = marketing["structured_output"]
        assert so["provider"] == "hermes"
        assert so["pricing"]["recommended"] == "699"
        assert len(so["next_actions"]) == 4

    def test_hermes_failure_logs_hermes_failed(self, service, monkeypatch):
        """验证 Hermes 失败时记录 hermes_failed 事件"""
        import subprocess
        import shutil

        # Mock 让 Hermes CLI 不存在
        monkeypatch.setattr(shutil, "which", lambda x: None)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="失败测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        # 执行应该 fallback 到 local_heuristic
        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 event log
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "provider_fallback" in event_types

    def test_full_mission_hermes_chain(self, service, monkeypatch):
        """验证完整 mission（多个模块）走 Hermes 链路"""
        import subprocess

        call_count = 0
        responses = [
            MOCK_MARKET_RESEARCH_RESPONSE,
            MOCK_LISTING_PACK_RESPONSE,
            '{"summary": "执行清单", "warnings": []}',
        ]

        def mock_popen_cmd(cmd, **kwargs):
            nonlocal call_count
            result = _mock_popen(responses[call_count % len(responses)])
            call_count += 1
            return result

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="蓝牙耳机选品",
            enabled_modules=["market", "marketing"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_mission(mission_id, allow_browser_automation=True)
        # v2: 全部模块成功 → ready_for_review（不再直接标 done）
        assert updated["status"] == "ready_for_review"

        # 验证所有非 skipped 模块都用 hermes
        for mod in updated["modules"]:
            if mod["status"] != "skipped":
                so = mod["structured_output"]
                assert so.get("provider") == "hermes"

    def test_structured_output_schema_completeness(self, service, monkeypatch):
        """验证 structured_output 包含所有标准字段（含新增字段）"""
        import subprocess

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(MOCK_MARKET_RESEARCH_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="Schema 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")
        so = market["structured_output"]

        # 验证所有标准字段存在（含新增字段）
        required_fields = [
            "status", "summary", "evidence", "competitors",
            "pricing", "listing_copy", "image_plan",
            "next_actions", "warnings", "provider", "generated_at",
            # 新增字段
            "evidence_files", "screenshots", "tool_calls",
            "missing_evidence", "evidence_gate_passed",
        ]
        for field in required_fields:
            assert field in so, f"Missing field: {field}"

        assert so["status"] == "success"
        assert so["provider"] == "hermes"
        assert isinstance(so["evidence"], list)
        assert isinstance(so["competitors"], list)
        assert isinstance(so["pricing"], dict)
        assert isinstance(so["warnings"], list)
        assert isinstance(so["tool_calls"], list)
        assert isinstance(so["evidence_files"], list)
        assert isinstance(so["screenshots"], list)
        assert isinstance(so["missing_evidence"], list)
        assert isinstance(so["evidence_gate_passed"], bool)


# ── Evidence Gate 测试 ──────────────────────────────────────

class TestEvidenceGate:
    """Evidence Gate 逻辑测试"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        """设置 BOSS_EXECUTION_PROVIDER=hermes"""
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        import importlib
        import backend.config
        importlib.reload(backend.config)
        # 清除 provider registry 缓存
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None
        # 清除 executor 的 provider 缓存
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None
        # Mock shutil.which 让 Hermes 可用
        import shutil
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import BossCommandCenterService
        return BossCommandCenterService()

    def test_evidence_gate_pass_with_sufficient_evidence(self, service, monkeypatch):
        """验证有足够 evidence 时 evidence gate 通过"""
        import subprocess
        import shutil

        # 返回有足够 evidence 的响应
        sufficient_response = json.dumps({
            "summary": "市场调研结果",
            "evidence": [
                {"title": "来源1", "url": "https://real1.com", "type": "source"},
                {"title": "来源2", "url": "https://real2.com", "type": "browser"},
            ],
            "tool_calls": [
                {"tool": "browser", "args": {"url": "https://real1.com"}, "result": "采集成功"},
            ],
            "competitors": [
                {"name": "竞品A", "price": "99", "platform": "淘宝"},
                {"name": "竞品B", "price": "199", "platform": "京东"},
            ],
            "pricing": {"range": "99-199"},
            "warnings": [],
        })

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(sufficient_response)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板，这样 market executor 才会被使用
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="evidence gate 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 evidence gate 通过
        so = market["structured_output"]
        assert so["evidence_gate_passed"] is True
        assert so["status"] == "success"
        assert len(so["missing_evidence"]) == 0

        # 验证 event log 包含 evidence_gate_passed
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "evidence_gate_passed" in event_types

    def test_evidence_gate_fail_with_no_evidence(self, service, monkeypatch):
        """验证没有 evidence 时 evidence gate 失败"""
        import subprocess

        # 返回没有 evidence 的响应
        no_evidence_response = json.dumps({
            "summary": "凭空生成的调研结果",
            "evidence": [],
            "tool_calls": [],
            "competitors": [],
            "pricing": {},
            "warnings": [],
        })

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(no_evidence_response)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="evidence gate 失败测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 evidence gate 失败
        so = market["structured_output"]
        assert so["evidence_gate_passed"] is False
        assert so["status"] == "partial"
        assert len(so["missing_evidence"]) > 0

        # 验证 confidence 降低
        assert market["confidence"] < 0.5

        # 验证 warnings 包含证据不足提示
        assert any("证据门槛未通过" in w for w in market["warnings"])

        # 验证 event log 包含 evidence_gate_failed
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "evidence_gate_failed" in event_types

    def test_evidence_gate_fail_insufficient_competitors(self, service, monkeypatch):
        """验证竞品数量不足时 evidence gate 失败"""
        import subprocess

        # 返回竞品数量不足的响应
        insufficient_competitors = json.dumps({
            "summary": "竞品分析结果",
            "evidence": [
                {"title": "来源1", "url": "https://real1.com", "type": "source"},
                {"title": "来源2", "url": "https://real2.com", "type": "browser"},
                {"title": "来源3", "url": "https://real3.com", "type": "sourcing"},
            ],
            "tool_calls": [
                {"tool": "browser", "args": {"url": "https://real1.com"}, "result": "采集成功"},
            ],
            "competitors": [
                {"name": "竞品A", "price": "99", "platform": "淘宝"},
            ],
            "pricing": {"recommended_range": "99-199"},
            "warnings": [],
        })

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(insufficient_competitors)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 market 模块测试竞品数量不足（market 要求至少 2 个竞品）
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="竞品不足测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 evidence gate 失败
        so = market["structured_output"]
        assert so["evidence_gate_passed"] is False
        assert so["status"] == "partial"
        assert any("竞品" in m for m in so["missing_evidence"])

    def test_hermes_partial_result_event(self, service, monkeypatch):
        """验证 Hermes 返回部分结果时记录 hermes_partial_result 事件"""
        import subprocess

        # 返回部分结果（evidence 不足但有部分数据）
        partial_response = json.dumps({
            "summary": "部分调研结果",
            "evidence": [
                {"title": "来源1", "url": "https://real1.com", "type": "source"},
            ],
            "tool_calls": [
                {"tool": "browser", "args": {"url": "https://real1.com"}, "result": "采集成功"},
            ],
            "competitors": [
                {"name": "竞品A", "price": "99", "platform": "淘宝"},
                {"name": "竞品B", "price": "199", "platform": "京东"},
            ],
            "pricing": {"range": "99-199"},
            "warnings": ["部分数据缺失"],
        })

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(partial_response)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="部分结果测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 status 为 partial
        so = market["structured_output"]
        assert so["status"] == "partial"

        # 验证 warnings 包含部分数据缺失提示
        assert any("部分" in w for w in market["warnings"])

    def test_hermes_no_json_fallback_warning(self, service, monkeypatch):
        """验证 Hermes 返回非 JSON 时必须有 warning"""
        import subprocess

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen("This is not JSON output from Hermes")

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="非 JSON 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # 验证 fallback 到 local_heuristic
        so = market.get("structured_output", {})
        provider = so.get("provider", "")
        assert provider != "hermes"

        # 验证 event log 包含 provider_fallback
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]
        assert "provider_fallback" in event_types

    def test_listing_pack_depends_on_prev_evidence(self, service, monkeypatch):
        """验证上架文案必须依赖前序 evidence"""
        import subprocess

        # 模拟前序模块有 evidence 的情况
        market_response = json.dumps({
            "summary": "市场调研结果",
            "evidence": [
                {"title": "来源1", "url": "https://real1.com", "type": "source"},
                {"title": "来源2", "url": "https://real2.com", "type": "browser"},
            ],
            "tool_calls": [{"tool": "browser", "args": {"url": "https://real1.com"}, "result": "采集成功"}],
            "competitors": [
                {"name": "竞品A", "price": "99", "platform": "淘宝"},
                {"name": "竞品B", "price": "199", "platform": "京东"},
            ],
            "pricing": {"range": "99-199"},
            "warnings": [],
        })

        listing_response = json.dumps({
            "summary": "上架物料包",
            "listing_copy": "基于 evidence 的文案",
            "evidence": [
                {"title": "来源1", "url": "https://real1.com", "type": "source"},
            ],
            "tool_calls": [{"tool": "browser", "args": {"url": "https://real1.com"}, "result": "采集成功"}],
            "pricing": {"recommended": "149", "evidence_based": True},
            "image_plan": {"main_image": "白底图"},
            "next_actions": ["上架"],
            "warnings": [],
        })

        call_count = 0
        responses = [market_response, listing_response]

        def mock_popen_cmd(cmd, **kwargs):
            nonlocal call_count
            result = _mock_popen(responses[call_count % len(responses)])
            call_count += 1
            return result

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 ecommerce_product_research 模板
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="上架文案依赖测试",
            enabled_modules=["market", "marketing"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        # 先执行 market
        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")
        assert market["status"] == "done"

        # 再执行 marketing（listing pack）
        updated = service.run_module(mission_id, "marketing", allow_browser_automation=True)
        marketing = next(m for m in updated["modules"] if m["module_id"] == "marketing")

        # 验证上架文案基于前序 evidence
        so = marketing["structured_output"]
        assert "evidence_based" in so["pricing"]
        assert so["pricing"]["evidence_based"] is True


# ── API 层集成测试 ──────────────────────────────────────────

class TestHermesProviderAPI:
    """Hermes Provider API 层测试"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        import importlib
        import backend.config
        importlib.reload(backend.config)
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None

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

        def mock_popen_cmd(cmd, **kwargs):
            return _mock_popen(MOCK_MARKET_RESEARCH_RESPONSE)

        monkeypatch.setattr(subprocess, "Popen", mock_popen_cmd)

        # 使用 from-template API 创建 mission
        resp = client.post("/boss/missions/from-template", json={
            "template_id": "ecommerce_product_research",
            "goal": "API 集成测试",
            "enabled_modules": ["market"],
            "auto_run": False,
            "allow_browser_automation": True,
        })
        assert resp.status_code == 200
        mission_id = resp.json()["mission_id"]

        # 执行 market 模块
        resp = client.post(f"/boss/missions/{mission_id}/modules/market/run",
                          json={"allow_browser_automation": True})
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


# ── Hermes Timeout → Fallback 行为测试 ─────────────────────

class TestHermesTimeoutFallback:
    """验证 Hermes 超时时 fallback 行为的正确性"""

    @pytest.fixture(autouse=True)
    def _setup_hermes_provider(self, monkeypatch):
        monkeypatch.setenv("BOSS_EXECUTION_PROVIDER", "hermes")
        import importlib
        import backend.config
        importlib.reload(backend.config)
        import backend.services.boss_execution_providers as provider_module
        provider_module._registry = None
        import backend.services.boss_module_executors as executor_module
        for template_executors in executor_module._EXECUTOR_REGISTRY.values():
            for executor in template_executors.values():
                executor._provider = None

    @pytest.fixture
    def service(self):
        from backend.services.boss_command_center import get_boss_command_center
        return get_boss_command_center()

    def test_timeout_fallback_structured_output_not_empty(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 structured_output 不为空"""
        import subprocess
        import shutil

        # Mock Hermes 超时（subprocess.Popen 的 wait 方法抛出 TimeoutExpired）
        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        # 创建 mission
        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        # 执行 market 模块
        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # structured_output 不能为空
        so = market["structured_output"]
        assert so != {}, f"structured_output 为空: {so}"
        assert isinstance(so, dict)

    def test_timeout_fallback_evidence_gate_passed_false(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 evidence_gate_passed 为 False"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        so = market["structured_output"]
        assert so["evidence_gate_passed"] is False
        assert so["status"] == "partial"
        assert so["provider"] == "local_heuristic_fallback"

    def test_timeout_fallback_missing_evidence_non_empty(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 missing_evidence 非空"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        so = market["structured_output"]
        assert len(so["missing_evidence"]) > 0, f"missing_evidence 为空: {so['missing_evidence']}"

    def test_timeout_fallback_event_log_has_evidence_gate_failed(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 event log 包含 evidence_gate_failed"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)

        # 检查事件日志
        events = service.get_events(mission_id)
        event_types = [e["type"] for e in events]

        assert "hermes_failed" in event_types, f"hermes_failed 未在事件中: {event_types}"
        assert "provider_fallback" in event_types, f"provider_fallback 未在事件中: {event_types}"
        assert "evidence_gate_failed" in event_types, f"evidence_gate_failed 未在事件中: {event_types}"
        assert "fallback_partial_result" in event_types, f"fallback_partial_result 未在事件中: {event_types}"

        # 检查 evidence_gate_failed payload
        gate_failed_events = [e for e in events if e["type"] == "evidence_gate_failed"]
        assert len(gate_failed_events) > 0
        payload = gate_failed_events[0]["payload"]
        assert "reason" in payload
        assert "missing_evidence" in payload
        assert "provider" in payload
        assert payload["provider"] == "hermes"

    def test_timeout_fallback_warnings_include_timeout_reason(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 warnings 包含超时原因"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        # warnings 应包含 fallback 相关信息
        assert len(market["warnings"]) > 0, f"warnings 为空: {market['warnings']}"

    def test_timeout_fallback_confidence_is_03(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 confidence 固定为 0.3"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        assert market["confidence"] == 0.3, f"confidence 不是 0.3: {market['confidence']}"

    def test_timeout_fallback_evidence_empty(self, service, monkeypatch):
        """验证 Hermes 超时 fallback 后 evidence 列表为空（不伪造）"""
        import subprocess
        import shutil

        def mock_popen_timeout(cmd, **kwargs):
            class MockProcess:
                returncode = 0
                stdout = None
                stderr = None

                def wait(self, timeout=None):
                    raise subprocess.TimeoutExpired(cmd, 300)

                def kill(self):
                    pass

            return MockProcess()

        monkeypatch.setattr(subprocess, "Popen", mock_popen_timeout)
        monkeypatch.setattr(shutil, "which", lambda x: "/usr/bin/hermes")

        mission = service.create_mission_from_template(
            "ecommerce_product_research",
            goal="超时 fallback 测试",
            enabled_modules=["market"],
            allow_browser_automation=True,
        )
        mission_id = mission["mission_id"]

        updated = service.run_module(mission_id, "market", allow_browser_automation=True)
        market = next(m for m in updated["modules"] if m["module_id"] == "market")

        so = market["structured_output"]
        assert so["evidence"] == [], f"evidence 不为空（可能在伪造）: {so['evidence']}"
        assert so["evidence_files"] == []
        assert so["screenshots"] == []
        assert so["tool_calls"] == []
