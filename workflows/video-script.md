---
name: 视频脚本生成
description: Video生成脚本 → Marketing优化文案 → CTO审查 → QA验收
version: "1.0"
triggers: [视频脚本, 拍摄脚本, 短视频, 宣传片]
steps:
  - id: script-draft
    agent: video_agent
    task_type: video_script
    description: 生成视频脚本初稿
    input:
      prompt: "Topic: {{inputs.topic}}. Platform: {{inputs.platform}}. Duration: {{inputs.duration}}. Format: {{inputs.format}}"
    retry: 1
  - id: polish-script
    agent: marketing_agent
    task_type: copywriting
    description: 优化脚本台词和节奏
    depends_on: [script-draft]
    condition: "steps.script-draft.status == 'completed'"
    input:
      prompt: "优化以下视频脚本，让台词更有感染力，hook更抓人: 标题: {{steps.script-draft.data.title}}，剧本概要: {{steps.script-draft.data.hook}}"
    retry: 1
  - id: cto-check
    agent: cto_agent
    task_type: code_review
    description: 技术可行性审查
    depends_on: [script-draft]
    input:
      goal: "审查视频脚本的技术可行性"
      code: "{{steps.script-draft.data}}"
      context: "拍摄平台: {{inputs.platform}}，时长: {{inputs.duration}}秒"
    retry: 1
  - id: qa-verify
    agent: qa_agent
    task_type: qa_review
    description: 最终验收
    depends_on: [script-draft, polish-script, cto-check]
    input:
      goal: "验收视频脚本质量"

outputs:
  script: "{{steps.script-draft.data}}"
  polished: "{{steps.polish-script.data}}"
  tech_review: "{{steps.cto-check.data}}"
  final_rating: "{{steps.qa-verify.summary}}"
---

# 视频脚本生成工作流

## 输入
- `topic`: 视频主题
- `platform`: 目标平台（抖音/YouTube/B站）
- `duration`: 时长（秒）
- `format`: 类型（tutorial/vlog/review/short）

## 流程
1. Video Agent 生成脚本初稿和分镜
2. Marketing Agent 优化台词和节奏
3. CTO Agent 审查拍摄可行性
4. QA Agent 最终验收
