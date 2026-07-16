"""DAG Workflow Engine unit tests"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.workflow.engine import WorkflowStep, DAGBuilder, get_workflow_engine

def test_step_evaluate_condition():
    s = WorkflowStep({"id":"test","agent":"qa","task_type":"qa_review","condition":"steps.cto-review.status != 'failed'"})
    assert s.evaluate_condition({"steps":{"cto-review":{"status":"completed"}}}) == True
    assert s.evaluate_condition({"steps":{"cto-review":{"status":"failed"}}}) == False
    # No condition = always pass
    s2 = WorkflowStep({"id":"test2","agent":"qa","task_type":"qa_review"})
    assert s2.evaluate_condition({}) == True

def test_step_build_input():
    s = WorkflowStep({"id":"test","agent":"qa","task_type":"qa_review","input":{"prompt":"{{inputs.topic}}"}})
    resolved = s.build_input({"inputs":{"topic":"Python async"}})
    assert "Python async" in resolved.get("prompt", "")

def test_dag_builder_linear():
    steps = [
        WorkflowStep({"id":"a","agent":"ceo","task_type":"goal_decompose"}),
        WorkflowStep({"id":"b","agent":"codex","task_type":"code_execute","depends_on":["a"]}),
        WorkflowStep({"id":"c","agent":"qa","task_type":"qa_review","depends_on":["b"]}),
    ]
    layers, deps = DAGBuilder.build(steps)
    assert len(layers) == 3
    assert layers[0] == ["a"]
    assert layers[1] == ["b"]
    assert layers[2] == ["c"]

def test_dag_builder_parallel():
    steps = [
        WorkflowStep({"id":"a","agent":"ceo","task_type":"goal_decompose"}),
        WorkflowStep({"id":"b","agent":"codex","task_type":"code_execute","depends_on":["a"]}),
        WorkflowStep({"id":"c","agent":"cto","task_type":"code_review","depends_on":["a"]}),
        WorkflowStep({"id":"d","agent":"qa","task_type":"qa_review","depends_on":["b","c"]}),
    ]
    layers, deps = DAGBuilder.build(steps)
    assert len(layers) == 3
    assert set(layers[1]) == {"b", "c"}

def test_all_workflows_load():
    wf = get_workflow_engine()
    wfs = wf.list_all()
    assert len(wfs) >= 4
    for w in wfs:
        name = w["name"]
        wf_def = wf.get(name)
        assert wf_def is not None
        layers, _ = DAGBuilder.build(wf_def.steps)
        assert len(layers) > 0

def test_template_nested():
    s = WorkflowStep({"id":"t","agent":"qa","task_type":"qa_review","input":{"msg":"{{steps.a.data.result}}"}})
    ctx = {"steps":{"a":{"data":{"result":"hello world"}}}}
    resolved = s.build_input(ctx)
    assert "hello world" in resolved.get("msg", "")

if __name__ == "__main__":
    test_step_evaluate_condition(); print("[OK] evaluate condition")
    test_step_build_input(); print("[OK] build input")
    test_dag_builder_linear(); print("[OK] DAG linear")
    test_dag_builder_parallel(); print("[OK] DAG parallel")
    test_all_workflows_load(); print("[OK] all workflows load")
    test_template_nested(); print("[OK] template nested")
    print("\nALL DAG TESTS PASSED")
