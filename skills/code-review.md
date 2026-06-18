---
title: 代码审查
description: 审查代码质量、发现 bug、提出改进建议。适用于 Pull Request Review、代码走查。
category: development
capabilities: [code_review, bug_detection, quality, security]
triggers: [code review, 代码审查, PR review, 审查代码, 代码检查, review code]
---

# 代码审查流程

## 审查维度

### 1. 代码质量
- 命名是否清晰、符合约定（Python PEP8, JS camelCase 等）
- 函数长度是否合理（建议 < 50 行）
- 嵌套深度是否过深（建议 < 4 层）
- 是否有冗余的注释或无注释的复杂逻辑

### 2. 安全性
- SQL 注入：是否使用参数化查询
- XSS：用户输入是否正确转义
- 敏感信息：是否有硬编码的密码、Token、Key
- 命令注入：是否对系统命令参数做了校验
- 路径遍历：是否限制了文件访问范围

### 3. 性能
- 是否有不必要的循环嵌套（N+1 查询）
- 是否正确使用了缓存
- 资源是否及时释放（文件句柄、数据库连接）
- 大型数据是否做了分页/流式处理

### 4. 可维护性
- 错误处理是否完善（不吞异常）
- 是否有足够的类型提示（Python）或类型定义（TS）
- 依赖是否最小化
- 是否可测试（纯函数 vs 副作用）

## 审查输出格式

发现问题使用以下模板：
- 🔴 Critical: 必须修复（安全漏洞、数据丢失风险）
- 🟠 High: 强烈建议修复（性能严重下降、可维护性大问题）
- 🟡 Medium: 建议修复（违反最佳实践）
- 🟢 Low: 可选修复（代码风格、命名建议）
