# Agent Protocol

## 1. 协议目标

本协议用于规范 AI Company OS 中所有 Agent 的任务输入、执行过程、结果输出和验收标准。

所有 Agent 必须使用统一任务格式，避免不同 Agent 之间无法协作。

---

## 2. Agent 角色

### CEO Agent

负责目标理解、任务拆解、结果验收和重新规划。

### CTO Agent

负责技术方案设计、代码任务拆分和技术审核。

### Codex Agent

负责代码编写、Bug 修复、项目重构和测试执行。

### OpenClaw Agent

负责浏览器操作、网页自动化、页面测试和数据采集。

### QA Agent

负责结果检测、评分、问题反馈和是否通过验收。

### Image Agent

负责图片生成、图片修改、视觉素材输出。

### Video Agent

负责视频生成、视频修改、广告视频输出。

---

## 3. 任务标准格式

所有任务必须使用以下 JSON 格式：

```json
{
  "task_id": "task_001",
  "project_id": "project_001",
  "created_by": "ceo_agent",
  "assigned_to": "codex_agent",
  "task_type": "code_fix",
  "priority": "high",
  "goal": "修复登录页面报错",
  "context": "用户反馈登录按钮点击后没有反应",
  "input": {
    "project_path": "E:/AI-company-os",
    "files": [],
    "links": [],
    "requirements": []
  },
  "expected_output": {
    "type": "code_change",
    "description": "登录按钮可以正常触发登录逻辑"
  },
  "constraints": {
    "do_not_delete_files": true,
    "do_not_change_database": true,
    "require_backup": true
  },
  "status": "todo",
  "result": null,
  "score": null,
  "created_at": "",
  "updated_at": ""
}