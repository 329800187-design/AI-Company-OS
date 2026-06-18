---
name: Web 深度研究
description: 联网搜索 → 多源抓取 → AI深度分析 → 生成带来源的完整研究报告
version: "1.0"
triggers: [research, 研究, 调研, 深度分析, 查一下, 联网搜索]
steps:
  - id: search-web
    agent: openclaw_agent
    task_type: browser_scrape
    description: Google 搜索并提取结果摘要
    input:
      goal: "搜索: {{inputs.topic}}"
      url: "https://www.google.com/search?q={{inputs.topic}}"
      extract_type: text
    retry: 1
    timeout: 30
  - id: deep-search
    agent: openclaw_agent
    task_type: browser_scrape
    description: 深入抓取 Top 2 个结果页面的详细内容
    depends_on: [search-web]
    condition: "steps.search-web.status == 'completed'"
    input:
      goal: "深入抓取关于 {{inputs.topic}} 的详细信息"
      url: "{{inputs.deep_url}}"
      extract_type: text
    retry: 1
    timeout: 30
  - id: analyze
    agent: cto_agent
    task_type: code_review
    description: 深度分析抓取的信息
    depends_on: [deep-search]
    input:
      goal: "分析以下关于 {{inputs.topic}} 的网页数据，提炼关键信息、分类归纳、标注来源可靠性"
      code: "{{steps.deep-search.data}}"
      context: "研究主题: {{inputs.topic}}。请根据网页内容做结构化分析"
    retry: 1
  - id: generate-report
    agent: marketing_agent
    task_type: copywriting
    description: 生成结构化研究报告
    depends_on: [deep-search, analyze]
    condition: "steps.analyze.status == 'completed'"
    input:
      prompt: "根据以下分析结果，生成一份关于「{{inputs.topic}}」的结构化研究报告。要求: 关键发现+详细分析+数据对比+来源标注+局限说明"
    retry: 1
  - id: qa-final
    agent: qa_agent
    task_type: qa_review
    description: 最终质量验收
    depends_on: [generate-report]
    input:
      goal: "验收研究报告质量: 信息准确性、来源可靠性、逻辑完整性、可读性"

outputs:
  search_results: "{{steps.search-web.data}}"
  deep_content: "{{steps.deep-search.data}}"
  analysis: "{{steps.analyze.data}}"
  report: "{{steps.generate-report.data}}"
  final_score: "{{steps.qa-final.summary}}"
---

# Web 深度研究 DAG 工作流

## 输入
- `topic`: 研究主题（中英文皆可，自动 Google 搜索）
- `deep_url`: 可选，深入抓取的特定 URL

## 流程
1. OpenClaw Google 搜索 → 提取 Top 10 结果摘要
2. OpenClaw 深入抓取 Top 页面详细内容
3. CTO Agent 深度分析抓取数据
4. Marketing Agent 生成结构化报告
5. QA Agent 验收报告质量

## 产出
一份包含来源、数据、分析、局限说明的完整研究报告
