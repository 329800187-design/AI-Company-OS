"""
Workflow DAG Engine — 工作流有向无环图执行引擎

解析 workflows/*.md 中的 YAML frontmatter 工作流定义，构建 DAG 依赖图，
按拓扑顺序执行步骤，支持条件分支、并行执行、步骤间数据传递。

Format: 每个 .md 文件的 YAML frontmatter 定义 steps
Each step: id, agent, task_type, depends_on, condition, input, retry
"""
import json
import re
import time
import yaml
from collections import deque
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple
from copy import deepcopy


class WorkflowStep:
    """工作流中的单个步骤"""

    def __init__(self, data: Dict[str, Any]):
        self.id: str = data.get("id", "")
        self.agent: str = data.get("agent", "")
        self.task_type: str = data.get("task_type", "qa_review")
        self.description: str = data.get("description", "")
        self.depends_on: List[str] = data.get("depends_on", [])
        self.condition: str = data.get("condition", "")
        self.input_template: Dict[str, Any] = data.get("input", {})
        self.retry: int = data.get("retry", 1)
        self.timeout: int = data.get("timeout", 60)

    def evaluate_condition(self, context: Dict) -> bool:
        """评估条件表达式，支持 == 和 != 比较"""
        if not self.condition:
            return True
        try:
            cond = self.condition.strip()
            # 用 _safe_get 解析两侧，然后比较
            if '!=' in cond:
                left, right = cond.split('!=', 1)
                lv = WorkflowStep._safe_get(left.strip(), context)
                rv = right.strip().strip("'").strip('"')
                return lv != rv
            elif '==' in cond:
                left, right = cond.split('==', 1)
                lv = WorkflowStep._safe_get(left.strip(), context)
                rv = right.strip().strip("'").strip('"')
                return lv == rv
            # Fallback: Python eval
            return bool(eval(cond, {"__builtins__": {}}, context))
        except Exception:
            return True  # 条件解析失败默认执行

    def build_input(self, context: Dict) -> Dict:
        """根据模板和上下文构建步骤的实际输入"""
        resolved = {}
        for key, value in self.input_template.items():
            resolved[key] = self._resolve_value(value, context)
        return resolved

    @staticmethod
    def _safe_get(expr: str, context: Dict) -> str:
        """解析路径表达式 (如 inputs.topic 或 steps.step-id.data.key)，返回字符串值"""
        try:
            # 分割路径（. 和 ['key'] 和 ["key"]）
            parts = re.split(r'\.|\["?\'?|\'?"?\]', expr)
            parts = [p.strip() for p in parts if p.strip()]
            val = context
            for part in parts:
                if isinstance(val, dict):
                    val = val.get(part, val.get(str(part)))
                elif hasattr(val, part):
                    val = getattr(val, part)
                else:
                    return ""
                if val is None:
                    return ""
            return str(val) if val is not None else ""
        except Exception:
            return ""

    def _resolve_value(self, value: Any, context: Dict) -> Any:
        """递归解析模板变量 {{...}}"""
        if isinstance(value, str):
            return WorkflowStep._resolve_template(value, context)
        elif isinstance(value, dict):
            return {k: self._resolve_value(v, context) for k, v in value.items()}
        elif isinstance(value, list):
            return [self._resolve_value(v, context) for v in value]
        return value

    @staticmethod
    def _resolve_template(text: str, context: Dict) -> str:
        """解析 {{variables}} 模板，支持 .key 和 ['key'] 及 step-id 访问"""
        pattern = re.compile(r"\{\{(.+?)\}\}")
        def replacer(m):
            val = WorkflowStep._safe_get(m.group(1).strip(), context)
            return val if val else f"{{{{{m.group(1).strip()}}}}}"
        return pattern.sub(replacer, text)


class WorkflowDefinition:
    """工作流定义"""

    def __init__(self, path: Path):
        self.path = path
        self.name = path.stem
        self.title: str = path.stem
        self.description: str = ""
        self.version: str = "1.0"
        self.triggers: List[str] = []
        self.steps: List[WorkflowStep] = []
        self._outputs_raw: Dict[str, str] = {}
        self._parsed = False
        self._parse()

    def _parse(self):
        """解析 YAML frontmatter"""
        try:
            text = self.path.read_text(encoding="utf-8")
        except Exception:
            return

        fm_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', text, re.DOTALL)
        if not fm_match:
            return

        try:
            fm = yaml.safe_load(fm_match.group(1))
        except Exception:
            return

        if not isinstance(fm, dict):
            return

        self.title = fm.get("name", fm.get("title", self.name))
        self.description = fm.get("description", "")
        self.version = str(fm.get("version", "1.0"))
        self.triggers = fm.get("triggers", [])

        steps_data = fm.get("steps", [])
        if isinstance(steps_data, list):
            self.steps = [WorkflowStep(s) for s in steps_data]

        self._outputs_raw = fm.get("outputs", {})
        self._parsed = True

    @property
    def step_ids(self) -> List[str]:
        return [s.id for s in self.steps]

    def get_step(self, step_id: str) -> Optional[WorkflowStep]:
        for s in self.steps:
            if s.id == step_id:
                return s
        return None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "version": self.version,
            "triggers": self.triggers,
            "steps": len(self.steps),
            "step_ids": self.step_ids,
        }


class DAGBuilder:
    """DAG 构建器 — 拓扑排序 + 并行度检测"""

    @staticmethod
    def build(steps: List[WorkflowStep]) -> Tuple[List[List[str]], Dict[str, List[str]]]:
        """
        返回:
          layers: 按拓扑序排列的执行层（每层内的步骤可并行）
          dependencies: step_id -> 依赖的 step_id 列表
        """
        # 构建邻接表
        graph: Dict[str, List[str]] = {}  # from -> to
        in_degree: Dict[str, int] = {}
        all_ids = {s.id for s in steps}

        for sid in all_ids:
            graph[sid] = []
            in_degree[sid] = 0

        for step in steps:
            for dep in step.depends_on:
                if dep in all_ids:
                    graph.setdefault(dep, []).append(step.id)
                    in_degree[step.id] = in_degree.get(step.id, 0) + 1

        # Kahn's algorithm (BFS) 分层
        layers = []
        queue = deque([sid for sid, deg in in_degree.items() if deg == 0])
        processed = set()

        while queue:
            layer = []
            for _ in range(len(queue)):
                node = queue.popleft()
                if node in processed:
                    continue
                processed.add(node)
                layer.append(node)
                for neighbor in graph.get(node, []):
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)
            if layer:
                layers.append(layer)

        if len(processed) != len(all_ids):
            # 存在环 → fallback: 逐层加入
            remaining = all_ids - processed
            for sid in remaining:
                layers.append([sid])

        deps = {s.id: s.depends_on for s in steps}
        return layers, deps


class WorkflowEngine:
    """工作流执行引擎"""

    def __init__(self, workflows_dir: Optional[Path] = None):
        if workflows_dir is None:
            workflows_dir = Path(__file__).parent.parent.parent / "workflows"
        self.workflows_dir = Path(workflows_dir)
        self._definitions: Dict[str, WorkflowDefinition] = {}
        self._loaded = False
        self._agent_cache: Dict[str, Any] = {}  # 懒加载 agent 实例

    def load_all(self) -> List[WorkflowDefinition]:
        """加载所有工作流定义"""
        self._definitions = {}
        for md_file in self.workflows_dir.rglob("*.md"):
            wf = WorkflowDefinition(md_file)
            if wf._parsed and wf.steps:
                self._definitions[wf.name] = wf
        self._loaded = True
        return list(self._definitions.values())

    def list_all(self) -> List[dict]:
        if not self._loaded:
            self.load_all()
        return [wf.to_dict() for wf in self._definitions.values()]

    def get(self, name: str) -> Optional[WorkflowDefinition]:
        if not self._loaded:
            self.load_all()
        return self._definitions.get(name)

    def run(self, workflow_name: str, inputs: Dict[str, Any] = None,
            progress_callback=None) -> Dict[str, Any]:
        """
        执行完整工作流

        Args:
            workflow_name: 工作流名称
            inputs: 外部输入变量
            progress_callback: 可选, 每完成一步调用 callback({"step": id, "status": ..., "result": ...})

        Returns:
            {"status": "completed|partial|failed", "results": {...}, "outputs": {...}}
        """
        inputs = inputs or {}
        wf = self.get(workflow_name)
        if not wf:
            return {"status": "error", "message": f"工作流不存在: {workflow_name}"}

        layers, deps = DAGBuilder.build(wf.steps)
        context = {
            "inputs": inputs,
            "steps": {},       # step_id -> step 执行结果
            "results": {},     # step_id -> agent 返回的完整结果
        }

        all_results = {}
        session_id = f"wf_{workflow_name}_{int(time.time())}"

        for layer_idx, layer in enumerate(layers):
            # 并行执行同层步骤
            layer_results = {}
            with ThreadPoolExecutor(max_workers=min(len(layer), 4)) as pool:
                futures = {}
                for step_id in layer:
                    step = wf.get_step(step_id)
                    if not step:
                        continue
                    # 检查条件
                    if not step.evaluate_condition(context):
                        layer_results[step_id] = {"status": "skipped", "reason": "condition"}
                        continue
                    futures[pool.submit(self._execute_step, step, context)] = step_id

                for future in as_completed(futures):
                    step_id = futures[future]
                    try:
                        result = future.result(timeout=300)
                    except Exception as e:
                        result = {"status": "failed", "error": str(e)}
                    layer_results[step_id] = result
                    context["steps"][step_id] = result
                    context["results"][step_id] = result.get("data", result)

                    if progress_callback:
                        progress_callback({
                            "step": step_id,
                            "layer": layer_idx,
                            "total_layers": len(layers),
                            "status": result.get("status", "?"),
                            "result": str(result.get("summary", ""))[:200],
                        })

            all_results.update(layer_results)

        # 评估输出
        outputs = self._resolve_outputs(wf, context)
        failed = sum(1 for r in all_results.values() if r.get("status") == "failed")

        return {
            "session_id": session_id,
            "status": "completed" if failed == 0 else "partial" if failed < len(all_results) else "failed",
            "workflow": workflow_name,
            "results": all_results,
            "outputs": outputs,
            "summary": f"完成 {len(all_results) - failed}/{len(all_results)} 步骤",
        }

    def _execute_step(self, step: WorkflowStep, context: Dict) -> Dict[str, Any]:
        """执行单个步骤 — 调用对应 Agent"""
        task_input = step.build_input(context)
        task_input["task_type"] = step.task_type
        task_input["task_id"] = f"wfstep_{step.id}_{int(time.time())}"
        if "goal" not in task_input:
            task_input["goal"] = step.description

        agent = self._get_agent(step.agent)
        if not agent:
            return {"status": "failed", "error": f"Agent not found: {step.agent}"}

        try:
            result = agent.run(task_input)
            return {
                "status": "completed" if result.get("status") not in ("失败", "failed") else "failed",
                "agent": step.agent,
                "summary": result.get("summary", result.get("result", "")),
                "data": result.get("data", result.get("output", result)),
            }
        except Exception as e:
            return {"status": "failed", "error": str(e), "agent": step.agent}

    def _get_agent(self, agent_name: str):
        """懒加载 Agent 实例"""
        if agent_name in self._agent_cache:
            return self._agent_cache[agent_name]

        mapping = {
            "ceo_agent": ("agents.ceo_agent.agent", "CEOAgent"),
            "codex_agent": ("agents.codex_agent.agent", "CodexAgent"),
            "qa_agent": ("agents.qa_agent.agent", "QAAgent"),
            "cto_agent": ("agents.cto_agent.agent", "CTOAgent"),
            "system_agent": ("agents.system_agent.agent", "SystemAgent"),
            "openclaw_agent": ("agents.openclaw_agent.agent", "OpenClawAgent"),
            "image_agent": ("agents.image_agent.agent", "ImageAgent"),
            "marketing_agent": ("agents.marketing_agent.agent", "MarketingAgent"),
            "video_agent": ("agents.video_agent.agent", "VideoAgent"),
        }

        mod_path, cls_name = mapping.get(agent_name, (None, None))
        if not mod_path:
            return None

        try:
            mod = __import__(mod_path, fromlist=[cls_name])
            agent_cls = getattr(mod, cls_name)
            agent = agent_cls()
            self._agent_cache[agent_name] = agent
            return agent
        except Exception as e:
            print(f"[WorkflowEngine] Agent {agent_name} 加载失败: {e}")
            return None

    def _resolve_outputs(self, wf: WorkflowDefinition, context: Dict) -> Dict:
        """解析工作流的 outputs 模板"""
        outputs = {}
        for key, template in wf._outputs_raw.items():
            if isinstance(template, str):
                outputs[key] = WorkflowStep._resolve_template(template, context)
            else:
                outputs[key] = template
        return outputs


# 全局单例
_engine: Optional[WorkflowEngine] = None


def get_workflow_engine() -> WorkflowEngine:
    global _engine
    if _engine is None:
        _engine = WorkflowEngine()
        _engine.load_all()
    return _engine
