---
title: 系统操作
description: 执行命令行、读写文件、启动程序、管理进程、调用本地 AI
category: agent
capabilities:
  - shell_execute
  - file_read
  - file_write
  - run_program
  - process_list
  - local_ai_inference
triggers:
  - 系统
  - 命令
  - 文件
  - 进程
  - 程序
  - 打开
  - 启动
  - ollama
  - 本地
  - cmd
  - terminal
---

# 系统操作 Agent (System)

## 能力
- 执行 shell 命令（cmd/powershell/bash）
- 读写本地文件
- 启动桌面程序
- 管理进程
- 检测和调用本地 AI（Ollama/LM Studio/llama.cpp）

## 安全规则
- 危险命令自动拦截（format、rm -rf 等）
- 文件操作可限制目录
- 命令执行有超时保护
