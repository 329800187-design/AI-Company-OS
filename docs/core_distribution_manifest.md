# AI Company OS Core v0.1-alpha — 分发清单

本文档定义 Core v0.1-alpha 发布包的完整文件清单，作为打包依据。

---

## Core 必须包含的文件

### 1. 核心入口

| 文件 | 说明 |
|------|------|
| `backend/core_app.py` | Core 轻量应用入口（不含完整项目路由） |

### 2. Governance 模块

| 文件 | 说明 |
|------|------|
| `backend/governance/` | 治理模块目录（含 __init__.py 及子模块） |

### 3. MiniDelivery 模块

| 文件 | 说明 |
|------|------|
| `backend/minidelivery/` | 轻量交付模块目录 |

### 4. Core 路由

| 文件 | 说明 |
|------|------|
| `backend/routers/core_agent_router.py` | Agent 注册/发现路由 |
| `backend/routers/governance_router.py` | Governance API 路由 |
| `backend/routers/collaboration_router.py` | 协作任务路由 |
| `backend/routers/minidelivery_router.py` | MiniDelivery 路由 |

### 5. 数据模型

| 文件 | 说明 |
|------|------|
| `backend/schemas/agent_manifest.py` | Agent 清单 schema |
| `backend/schemas/agent_protocol.py` | Agent 协议 schema |
| `backend/schemas/collaboration_plan.py` | 协作计划 schema |

### 6. 服务层

| 文件 | 说明 |
|------|------|
| `backend/services/agent_loader.py` | Agent 加载器 |
| `backend/services/agent_executor.py` | Agent 执行器 |
| `backend/services/agent_discovery.py` | Agent 发现服务 |
| `backend/services/collaboration_planner.py` | 协作计划生成 |
| `backend/services/collaboration_executor.py` | 协作任务执行 |

### 7. 示例 Agent

| 文件 | 说明 |
|------|------|
| `agents/installed/example_echo_agent/` | 示例 echo agent（用于验证插件机制） |

### 8. 依赖与文档

| 文件 | 说明 |
|------|------|
| `requirements-core.txt` | Core 最小依赖列表 |
| `docs/core_quickstart.md` | Core 快速启动指南 |
| `docs/agent_plugin_spec.md` | Agent 插件规范 |
| `docs/core_clean_install_checklist.md` | 干净安装验证清单 |

### 9. 测试

| 文件 | 说明 |
|------|------|
| `tests/test_core_app.py` | Core 应用测试 |
| `tests/test_governance.py` | Governance 模块测试 |
| `tests/test_minidelivery.py` | MiniDelivery 模块测试 |
| `tests/test_collaboration_plan.py` | 协作计划测试 |

---

## Core 不包含的文件（排除清单）

| 类别 | 排除内容 | 原因 |
|------|----------|------|
| 完整项目入口 | `backend/app.py` | 含全部路由，Core 不需要 |
| 老旧路由 | `boss/workflow/pipeline/commander/` 相关 | 已被 Core 取代 |
| 业务模块 | `payment/`, `user/`, `oauth/`, `cron/`, `admin/` | 非 Core 核心功能 |
| 前端 | `frontend/` legacy 文件 | Core 只含后端 |
| 根目录调试文件 | `test_*.py`, `read_code*.py`, `debug*.py` | 开发调试用，不入发布包 |
| 用户数据 | `user_data/`, `.profiles/`, `output/` | 运行时数据，不含代码 |
| 完整依赖 | `requirements.txt`（全量） | Core 只用 `requirements-core.txt` |
| Docker/CI | `Dockerfile`, `.github/`, `docker/` | Core 交付物不含部署配置 |
| 文档草稿 | 其他 docs 文件（VISION.md 等） | 非 Core 运行必需 |

---

## 分发前验证命令

打包完成后，执行以下命令验证 Core 可用：

```bash
# 1. 安装 Core 依赖
pip install -r requirements-core.txt

# 2. 验证 Core 入口可导入
python -c "import backend.core_app; print('ok')"

# 3. 运行 Core 测试套件
pytest tests/test_core_app.py tests/test_governance.py tests/test_minidelivery.py tests/test_collaboration_plan.py -q
```

**验收标准：**
- [ ] 三条命令全部通过
- [ ] 无代码改动（仅新增本文档）
- [ ] 清单可作为打包脚本的输入依据

---

*文档版本：v0.1-alpha | 更新日期：2026-07-02*
