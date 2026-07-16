---
title: 代码执行
description: 在安全沙箱中执行 Python 代码，生成脚本、运行测试、处理数据
category: agent
capabilities:
  - code_execute
  - code_write_and_run
  - code_test
triggers:
  - 代码
  - 脚本
  - 运行
  - 执行
  - 计算
  - Python
  - 编程
  - 写一个
---

# 代码执行 Agent (Codex)

## 能力
- 安全沙箱执行 Python 代码
- 自动生成代码来完成任务
- 运行测试并返回结果

## 最佳实践
1. 明确指定输入、输出和预期行为
2. 使用 `print()` 输出关键结果
3. 错误处理用 try/except
4. 给超时设置合理值（默认 30s）

## 安全限制
- 无网络访问
- 文件操作限制在临时目录
- 禁止执行危险命令
- 输出截断为 100KB
