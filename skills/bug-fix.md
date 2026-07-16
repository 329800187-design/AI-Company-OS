---
title: Bug 修复
description: 系统化的 Bug 诊断和修复流程：复现、定位、修复、验证、预防
category: development
capabilities: [bug_fix, debugging, troubleshooting, root_cause_analysis]
triggers: [bug, 修复, 报错, 调试, debug, 故障, error, 崩溃, 异常, 问题]
---

# Bug 修复流程

## 标准步骤

### 1. 复现（Reproduce）
- 记录精确的复现步骤
- 确认环境信息（OS, Python 版本, 依赖版本）
- 最小化复现用例（去掉无关代码）

### 2. 定位（Diagnose）
- 读错误堆栈（从最底部的用户代码开始）
- 添加日志/断点缩小范围
- 二分法排除：注释掉一半代码看问题是否存在
- 检查最近变更（git diff / git bisect）

### 3. 修复（Fix）
- 理解根本原因，不是修表面现象
- 写最小化修复代码
- 确保不引入新问题

### 4. 验证（Verify）
- 确认原复现步骤不再报错
- 跑现有测试套件
- 加回归测试防止复发

### 5. 预防（Prevent）
- 如果测试能提前发现问题，补充测试
- 如果是常见模式问题，添加 lint 规则
- 记录到文档/wiki

## Python 调试技巧

```python
# 打印变量
print(f"DEBUG: var={var}, type={type(var)}")

# 条件断点
if suspicious_condition:
    import pdb; pdb.set_trace()

# 异常追踪
import traceback
traceback.print_exc()

# 检查对象
print(dir(obj))
print(vars(obj))
```

## 常见问题速查

| 症状 | 可能原因 | 检查 |
|------|----------|------|
| ImportError | 路径/PYTHONPATH | `sys.path` |
| AttributeError | None 值/拼写错误 | 变量值 + 类型 |
| KeyError | 字典键不存在 | `.get()` 代替 `[]` |
| Timeout | 网络/死锁/死循环 | 加超时参数 |
| MemoryError | 大文件/内存泄漏 | `sys.getsizeof()` |
