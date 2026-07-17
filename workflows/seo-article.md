---
name: SEO文章生成
description: Marketing SEO → CTO审查 → QA验收的完整SEO内容流水线
version: "1.0"
triggers: [SEO文章, 内容营销, 博客文章, 长文]
steps:
  - id: seo-draft
    agent: marketing_agent
    task_type: seo_article
    description: 生成 SEO 优化文章
    input:
      prompt: "Topic: {{inputs.topic}}. Target keywords: {{inputs.keywords}}. Word count: {{inputs.word_count}}"
    retry: 1
  - id: cto-review
    agent: cto_agent
    task_type: code_review
    description: 内容质量审查
    depends_on: [seo-draft]
    input:
      goal: "审查以下 SEO 文章的内容质量和结构"
      code: "{{steps.seo-draft.data.content}}"
      context: "这是一篇关于 {{inputs.topic}} 的 SEO 文章，目标关键词: {{inputs.keywords}}"
    retry: 1
  - id: qa-check
    agent: qa_agent
    task_type: qa_review
    description: 最终验收
    depends_on: [seo-draft, cto-review]
    condition: "steps.cto-review.status != 'failed'"
    input:
      goal: "验收 SEO 文章质量，评分 >= 70 为合格"
outputs:
  article_data: "{{steps.seo-draft.data}}"
  cto_findings: "{{steps.cto-review.data}}"
  final_verdict: "{{steps.qa-check.summary}}"
---

# SEO 文章生成工作流

## 输入
- `topic`: 文章主题
- `keywords`: 目标关键词（逗号分隔）
- `word_count`: 字数要求

## 流程
1. Marketing SEO Agent 生成初稿
2. CTO Agent 审查内容质量和 SEO 合规性
3. QA Agent 最终验收
