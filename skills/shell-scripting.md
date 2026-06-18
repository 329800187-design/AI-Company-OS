---
title: Shell 脚本
description: 编写跨平台 Shell 脚本（Bash/PowerShell），自动化运维任务、文件处理、系统管理
category: system
capabilities: [shell_scripting, automation, system_administration, devops]
triggers: [shell, bash, 脚本, 命令行, 自动化, script, 批处理, batch, 定时任务]
---

# Shell 脚本指南

## 跨平台注意事项

本系统运行在 Windows + Git Bash 环境，注意：
- 优先使用 Git Bash 兼容语法（避免 bash 专有特性）
- Windows 路径用正斜杠 `/c/Users/...`
- 避免使用 `/dev/null`，用 `NUL`（cmd）或 `/dev/null`（bash）
- PowerShell 脚本需要单独编写（语法不兼容）

## Bash 模板

```bash
#!/usr/bin/env bash
set -euo pipefail  # 严格模式

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

log_info() { echo -e "${GREEN}[INFO]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# 参数检查
if [ $# -lt 1 ]; then
    echo "用法: $0 <输入文件>"
    exit 1
fi

INPUT="$1"
if [ ! -f "$INPUT" ]; then
    log_error "文件不存在: $INPUT"
    exit 1
fi

log_info "处理中: $INPUT"
# 主逻辑...
log_info "完成"
```

## 常用操作

### 批量重命名
```bash
for f in *.txt; do
    mv "$f" "${f%.txt}.md"
done
```

### 查找并操作文件
```bash
# 用 rg (ripgrep) 比 grep 快
rg "TODO" --type py -l | while read f; do
    echo "处理: $f"
done
```

### Git 批处理
```bash
# 批量 clone
while read repo; do
    git clone "https://github.com/$repo.git"
done < repos.txt
```

## 安全规则
- 始终检查返回值（`set -e`）
- 引用变量（`"$VAR"` 不是 `$VAR`）
- 不硬编码密码
- 危险操作前确认（`rm -rf` 用前检查路径）
