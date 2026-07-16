---
title: 文档生成
description: 自动生成技术文档、API 文档、项目 README、周报总结、会议纪要
category: content
capabilities: [document_generation, writing, summarization, markdown]
triggers: [文档, 报告, 总结, 写文章, README, 周报, 会议纪要, 说明文档]
---

# 文档生成指南

## 文档类型与模板

### 项目 README
```markdown
# 项目名称

一句话描述项目。

## 快速开始

git clone ...
pip install -r requirements.txt
python main.py

## 功能

- 功能 1
- 功能 2

## 技术栈

- Python 3.12
- FastAPI
- SQLite

## 项目结构

src/
├── main.py
└── ...
```

### API 文档
- FastAPI 自动生成 Swagger: `/docs`
- 确保 docstring 和 Field description 完整
- 在 response_model 中定义返回结构

### 周报模板
```markdown
# 周报 (YYYY-MM-DD ~ YYYY-MM-DD)

## 本周完成
- [x] 任务 1
- [x] 任务 2

## 遇到的问题
- 问题 1: 描述 + 解决方案

## 下周计划
- [ ] 计划 1
- [ ] 计划 2
```

### 技术方案文档
```markdown
# 技术方案: [标题]

## 背景与问题
## 方案对比
| 方案 | 优势 | 劣势 | 成本 |
|------|------|------|------|
| A    | ...  | ...  | ...  |

## 推荐方案
## 实施计划
## 风险与缓解
```

## 写作原则
- 用中文写，技术术语保留英文
- 先结论后细节（倒金字塔）
- 代码示例优先于文字描述
- 使用 Mermaid 画架构图
- 每段不超过 5 行，方便扫读
