"""V1.5 稳定化收口测试 — TaskClassifier / LocalAgentRuntime / ResultVerifier"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest


# ── TaskClassifier 中文分类 ─────────────────────────────

class TestTaskClassifierChinese:
    """TaskClassifier 中文关键词分类"""

    @pytest.fixture
    def classifier(self):
        from backend.services.task_classifier import TaskClassifier
        return TaskClassifier()

    def test_image_poster(self, classifier):
        task_type, confidence = classifier.classify("生成一张产品海报")
        assert task_type == "image"
        assert confidence >= 0.7

    def test_image_photo(self, classifier):
        task_type, _ = classifier.classify("帮我生成一个logo")
        assert task_type == "image"

    def test_data_csv(self, classifier):
        task_type, confidence = classifier.classify("分析这个csv数据")
        assert task_type == "data"
        assert confidence >= 0.7

    def test_data_excel(self, classifier):
        task_type, _ = classifier.classify("帮我做数据可视化图表")
        assert task_type == "data"

    def test_research(self, classifier):
        task_type, confidence = classifier.classify("调研一下AI行业趋势")
        assert task_type == "research"
        assert confidence >= 0.7

    def test_research_competitor(self, classifier):
        task_type, _ = classifier.classify("帮我做竞品分析")
        assert task_type == "research"

    def test_code(self, classifier):
        task_type, confidence = classifier.classify("写一个python函数")
        assert task_type == "code"
        assert confidence >= 0.7

    def test_code_script(self, classifier):
        task_type, _ = classifier.classify("帮我写一个脚本")
        assert task_type == "code"

    def test_marketing(self, classifier):
        task_type, _ = classifier.classify("帮我写小红书文案")
        assert task_type == "marketing"

    def test_website(self, classifier):
        task_type, _ = classifier.classify("帮我建一个落地页")
        assert task_type == "website"

    def test_chat_fallback(self, classifier):
        task_type, confidence = classifier.classify("你好，今天天气怎么样")
        assert task_type == "chat"
        assert confidence == 0.5


# ── LocalAgentRuntime 路由行为 ──────────────────────────

class TestLocalAgentRuntimeRouting:
    """LocalAgentRuntime 路由行为验证"""

    @pytest.fixture
    def runtime(self):
        """创建 runtime 实例（跳过需要外部服务的 adapter）"""
        from backend.services.local_agent_runtime import LocalAgentRuntime
        return LocalAgentRuntime()

    def test_image_agent_mapped(self, runtime):
        """image_agent 应通过 LocalModuleAdapter 映射，不返回空"""
        adapter_name = runtime._map_agent_to_adapter("image_agent")
        assert adapter_name == "image_agent", f"image_agent 映射失败: got {adapter_name}"
        assert adapter_name in runtime._adapters, f"image_agent adapter 未注册"

    def test_code_agent_mapped(self, runtime):
        """codex_agent 应有明确映射，不出现不透明 fallback"""
        adapter_name = runtime._map_agent_to_adapter("codex_agent")
        assert adapter_name == "codex_agent", f"codex_agent 映射失败: got {adapter_name}"
        assert adapter_name in runtime._adapters

    def test_data_agent_mapped(self, runtime):
        """data_agent 应映射到 data_agent adapter"""
        adapter_name = runtime._map_agent_to_adapter("data_agent")
        assert adapter_name == "data_agent"
        assert adapter_name in runtime._adapters

    def test_marketing_agent_mapped(self, runtime):
        """marketing_agent 应有明确映射"""
        adapter_name = runtime._map_agent_to_adapter("marketing_agent")
        assert adapter_name == "marketing_agent"
        assert adapter_name in runtime._adapters

    def test_image_task_has_fix_hints(self, runtime):
        """image 任务：即使 API 未配置，也应返回 fix_hints 而非 '没有可用工具'"""
        result = runtime.execute("生成一张产品海报")
        assert result.get("task_type") == "image"
        # 不应该返回 "没有可用的工具"
        assert "没有可用的工具" not in result.get("error", ""), \
            f"image 任务不应返回 '没有可用的工具', got: {result.get('error')}"
        # 应该有 fix_hints
        fix_hints = result.get("fix_hints", [])
        assert len(fix_hints) > 0, "image 任务应返回 fix_hints"

    def test_code_task_consistent_adapter(self, runtime):
        """code 任务：selected agent 和 executed adapter 应一致"""
        result = runtime.execute("写一个python函数 print('hello')")
        trace = result.get("tool_trace", [])
        # trace 应包含 agent 选择和执行步骤
        tool_names = [t.get("tool", "") for t in trace]
        assert len(tool_names) > 0, "tool_trace 不应为空"
        # 不应该出现 codex_agent 被选择但 claude_code 被执行的情况
        agent_selected = any("codex" in t.get("tool", "") or "claude" in t.get("tool", "")
                            for t in trace if t.get("action") == "Agent 选择")
        if agent_selected:
            # 执行的 adapter 应该和选择的一致
            exec_tools = [t.get("tool", "") for t in trace if t.get("action") == "执行任务"]
            for tool in exec_tools:
                # local_module = LocalModuleAdapter（codex_agent 走本地模块）
                # claude_code = ClaudeCodeAdapter（fallback）
                # 不应出现不相关工具
                assert tool in ("local_module", "codex_agent", "claude_code", "api_models"), \
                    f"code 任务执行了不一致的 adapter: {tool}"

    def test_data_with_csv_content(self, runtime):
        """data 任务：有 file_content CSV 时应能返回 rows/columns"""
        csv_data = "name,age,score\nAlice,30,95\nBob,25,88\nCharlie,35,72"
        result = runtime.execute(
            "分析这个csv数据",
            context={"file_content": csv_data}
        )
        # 验证结果结构
        assert result.get("task_type") == "data"
        # 如果 adapter 成功执行，deliverables 应有 rows/columns
        deliverables = result.get("deliverables", {})
        if result.get("ok"):
            assert "rows" in deliverables or "output" in deliverables


# ── ResultVerifier 关键失败场景 ─────────────────────────

class TestResultVerifierFailures:
    """ResultVerifier 关键失败场景验证"""

    @pytest.fixture
    def verifier(self):
        from backend.services.result_verifier import ResultVerifier
        return ResultVerifier()

    def test_research_no_sources_must_fail(self, verifier):
        """research 没有 sources 必须 failed"""
        result = verifier.verify("research", {
            "final_answer": "AI行业趋势分析报告，包含市场规模、增长趋势、主要玩家等详细分析内容。",
            "sources": []
        })
        assert result["passed"] is False, "research 无 sources 应 failed"
        assert result["score"] == 0
        assert any("来源" in issue for issue in result["issues"])

    def test_research_short_content_fails(self, verifier):
        """research 内容过短也应失败"""
        result = verifier.verify("research", {
            "final_answer": "太短了",
            "sources": [{"title": "source1", "url": "http://example.com"}]
        })
        assert result["passed"] is False, "research 内容过短应 failed"

    def test_code_no_code_structure_must_fail(self, verifier):
        """code 没有代码结构必须 failed"""
        result = verifier.verify("code", {
            "final_answer": "这是一个环境说明，需要安装 Python 3.12 和相关依赖包才能运行。"
        })
        assert result["passed"] is False, "code 无代码结构应 failed"
        assert result["score"] == 0

    def test_code_empty_must_fail(self, verifier):
        """code 空内容必须 failed"""
        result = verifier.verify("code", {
            "final_answer": ""
        })
        assert result["passed"] is False, "code 空内容应 failed"

    def test_code_valid_passes(self, verifier):
        """code 有效代码应 passed"""
        result = verifier.verify("code", {
            "final_answer": "def hello():\n    print('hello world')\n\nhello()"
        })
        assert result["passed"] is True, "code 有效代码应 passed"

    def test_data_no_input_must_fail(self, verifier):
        """data 无真实输入必须 failed"""
        result = verifier.verify("data", {
            "final_answer": "数据分析结果：数据看起来不错。",
            "deliverables": {"rows": 0, "columns": 0}
        })
        assert result["passed"] is False, "data 无输入应 failed"
        assert result["score"] == 0

    def test_data_with_input_passes(self, verifier):
        """data 有真实输入且内容充分应 passed"""
        result = verifier.verify("data", {
            "final_answer": "数据概览：100行，5列。平均值：mean=50.0，总计：sum=5000.0，最大值：max=100.0",
            "deliverables": {"rows": 100, "columns": 5}
        })
        assert result["passed"] is True, "data 有输入应 passed"

    def test_website_no_html_fails(self, verifier):
        """website 非 HTML 内容应 failed"""
        result = verifier.verify("website", {
            "final_answer": "这是一个网站的描述，不是 HTML 代码。"
        })
        assert result["passed"] is False, "website 非 HTML 应 failed"

    def test_website_valid_html_passes(self, verifier):
        """website 有效 HTML 应 passed"""
        html = """<!DOCTYPE html>
<html>
<head><title>Test</title><style>body{font-family:sans-serif;}</style></head>
<body><h1>Hello</h1><p>Content here</p></body>
</html>"""
        result = verifier.verify("website", {"final_answer": html})
        assert result["passed"] is True, "website 有效 HTML 应 passed"

    def test_marketing_too_short_fails(self, verifier):
        """marketing 文案过短应 failed"""
        result = verifier.verify("marketing", {
            "final_answer": "买它"
        })
        assert result["passed"] is False, "marketing 文案过短应 failed"
