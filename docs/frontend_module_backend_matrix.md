# 前端模块接入清单

Last updated: 2026-07-01

## 概述

本文档盘点左侧导航栏所有模块的当前状态，明确每个模块是否可用、对应前端文件、后端接口、接入状态。

---

## 模块清单

### 1. 首页 (Home)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `home` |
| **前端页面文件** | `frontend-new/src/pages/home/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ❌ 无后端调用 |
| **使用的后端接口** | 无 |
| **接口类型** | N/A |
| **当前状态** | 仅 UI |
| **推荐下一步** | 无需改造，纯展示页面 |

---

### 2. 老板指挥台 (Boss Command Center)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `boss` |
| **前端页面文件** | `frontend-new/src/pages/boss/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /boss/missions` (创建任务)<br>`POST /boss/missions/{id}/run` (执行任务)<br>`GET /boss/missions` (列表)<br>`GET /boss/missions/{id}` (详情)<br>`POST /boss/missions/{id}/accept` (接受结果)<br>`GET /boss/missions/{id}/events` (事件日志)<br>`GET /boss/templates` (模板列表)<br>`POST /boss/missions/from-template` (从模板创建)<br>`GET /boss/missions/{id}/export` (导出) |
| **接口类型** | governed_execute (通过 boss 路由) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证完整流程，确保所有模块正常执行 |

---

### 3. AI 助手 (Chat)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `chat` |
| **前端页面文件** | `frontend-new/src/pages/chat/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /commander/chat/send` (发送消息) |
| **接口类型** | safe_read (聊天接口) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证聊天功能正常 |

---

### 4. 写文案 (Marketing)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `marketing` |
| **前端页面文件** | `frontend-new/src/pages/marketing/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 5. 做图片 (Image)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `image` |
| **前端页面文件** | `frontend-new/src/pages/image/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 生成 `image_prompt_pack` Markdown 产物，不直接调用图片模型 |

---

### 6. 看数据 (Data)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `data` |
| **前端页面文件** | `frontend-new/src/pages/data/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 7. 做调研 (Research)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `research` |
| **前端页面文件** | `frontend-new/src/pages/research/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 8. 建网站 (Website)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `website` |
| **前端页面文件** | `frontend-new/src/pages/website/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 9. 场景模板 (Templates)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `templates` |
| **前端页面文件** | `frontend-new/src/pages/templates/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 10. 智能任务 (Commander)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `commander` |
| **前端页面文件** | `frontend-new/src/pages/commander/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/run` (执行任务)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | governed_execute (通过 Governance 闭环) |
| **当前状态** | ✅ 已接入 Governance 闭环 |
| **推荐下一步** | 无需改造，已通过 Governance 路由 |

---

### 11. 任务中心 (Missions)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `missions` |
| **前端页面文件** | `frontend-new/src/pages/missions/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /boss/missions` (任务列表)<br>`GET /boss/missions/{id}` (任务详情)<br>`POST /boss/missions/{id}/run` (执行任务) |
| **接口类型** | governed_execute (通过 boss 路由) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证任务列表和执行功能 |

---

### 12. 报告中心 (Reports)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `reports` |
| **前端页面文件** | `frontend-new/src/pages/reports/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /governance/runs` (运行记录列表)<br>`GET /governance/runs/{run_id}/artifact` (读取产物) |
| **接口类型** | safe_read (Governance 只读) |
| **当前状态** | ✅ 已接入 Governance 产物列表 |
| **推荐下一步** | 无需改造，已展示 Governance 产物历史 |

---

### 13. 知识库 (Memory)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `memory` |
| **前端页面文件** | `frontend-new/src/pages/memory/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /memory/search` (搜索记忆)<br>`GET /memory/recent` (最近记忆)<br>`POST /memory/remember` (保存记忆)<br>`DELETE /memory/clear` (清空记忆)<br>`DELETE /memory/{key}` (删除记忆)<br>`PUT /memory/{key}` (更新记忆) |
| **接口类型** | safe_read (记忆 CRUD) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证记忆管理功能 |

---

### 14. 技能库 (Skills)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `skills` |
| **前端页面文件** | `frontend-new/src/pages/skills/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /skills/list` (技能列表)<br>`GET /skills/match` (技能匹配)<br>`POST /skills/create` (创建技能) |
| **接口类型** | safe_read (技能 CRUD) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证技能管理和匹配功能 |

---

### 15. 工作流 (Workflows)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `workflows` |
| **前端页面文件** | `frontend-new/src/pages/workflows/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /workflows/dag/list` (工作流列表)<br>`GET /workflows/dag/{name}` (工作流详情)<br>`POST /workflows/dag/run` (执行工作流) |
| **接口类型** | governed_execute (通过 workflow 路由) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证工作流执行功能 |

---

### 16. Governance

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `governance` |
| **前端页面文件** | `frontend-new/src/pages/governance/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /governance/classify` (分类)<br>`POST /governance/plan` (规划)<br>`POST /governance/run` (执行)<br>`GET /governance/runs/{id}` (查询)<br>`GET /governance/runs/{id}/events` (事件)<br>`GET /governance/runs/{id}/artifact` (产物)<br>`GET /governance/routes` (路由策略)<br>`GET /governance/routes/summary` (统计摘要) |
| **接口类型** | governed_execute (Governance 核心) |
| **当前状态** | 已接入 |
| **推荐下一步** | 作为开发验证入口，保持现状 |

---

### 17. 用量统计 (Usage)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `usage` |
| **前端页面文件** | `frontend-new/src/pages/usage/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /usage/stats` (用量统计)<br>`GET /usage/total` (总用量)<br>`GET /usage/recent` (最近用量) |
| **接口类型** | safe_read (只读接口) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证统计数据展示 |

---

### 18. Agent 控制台 (Agent Console)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `agent-console` |
| **前端页面文件** | `frontend-new/src/pages/agent-console/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `POST /agents/{agent_name}/run` (执行 Agent)<br>`GET /agents/{agent_name}/status` (Agent 状态) |
| **接口类型** | high_risk (Agent 执行路由) |
| **当前状态** | ⚠️ 不应开放 |
| **推荐下一步** | 应迁移到 Governance 闭环，或标记为高风险 |

---

### 19. 系统状态 (Dashboard)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `dashboard` |
| **前端页面文件** | `frontend-new/src/pages/dashboard/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /system/metrics` (系统指标)<br>`GET /system/health` (健康检查) |
| **接口类型** | safe_read (只读接口) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证系统状态展示 |

---

### 20. 设置 (Settings)

| 项目 | 内容 |
|------|------|
| **Sidebar ID** | `settings` |
| **前端页面文件** | `frontend-new/src/pages/settings/index.tsx` |
| **当前是否能打开** | ✅ 可以 |
| **当前是否调用后端** | ✅ 是 |
| **使用的后端接口** | `GET /config/status` (配置状态)<br>`GET /config/providers` (Provider 列表)<br>`POST /config/save` (保存配置)<br>`POST /config/test` (测试连接)<br>`GET /brain/list` (Brain 列表)<br>`POST /brain/switch` (切换 Brain) |
| **接口类型** | safe_read (配置 CRUD) |
| **当前状态** | 已接入 |
| **推荐下一步** | 验证配置管理功能 |

---

## 统计汇总

| 状态 | 数量 | 模块 |
|------|------|------|
| ✅ 已接入 Governance 闭环 | 7 | 写文案、做图片、智能任务、做调研、建网站、场景模板、看数据 |
| ✅ 已接入 (其他路由) | 11 | 老板指挥台、AI 助手、任务中心、报告中心、知识库、技能库、工作流、Governance、用量统计、系统状态、设置 |
| ✅ 已接入 Governance 产物列表 | 1 | 报告中心 |
| ⚠️ 不应开放 | 1 | Agent 控制台 (high_risk) |
| 仅 UI | 1 | 首页 |

**模块总数**: 20

**已接入模块**: 19

**待接入模块**: 1 (Agent 控制台)

**高风险模块**: 1 (Agent 控制台)

---

## 推荐入口

**首页推荐路径**：

| 用户意图 | 推荐页面 | 入口路由 |
|----------|----------|----------|
| 写文案 | 智能任务 / 写文案 | `/governance/run` |
| 做图片 | 做图片 | `/governance/run` |
| 做调研 | 做调研 | `/governance/run` |
| 建网站 | 建网站 | `/governance/run` |
| 启用 Agent | Agent 控制台 | `/agent-console/discovered` |
| 查看历史 | 报告中心 | Governance/Collaboration 历史 |

**Legacy/Protected 模块**（保留但不推荐）：

| 模块 | 路由 | 标记 |
|------|------|------|
| 老板指挥台 | `/boss/*` | ⚠️ 旧版 |
| 工作流 | `/workflow/*` | ⚠️ 旧版 |
| 任务中心 | `/missions` | ⚠️ 旧版 |
| Agent 旧执行 | `/agents/*/run` | ⚠️ 旧版 |

---

## 注意事项

1. **Governance 是唯一受控执行入口**: 所有新功能应通过 `/governance/run` 执行
2. **Legacy 模块保留但不推荐**: Boss/Workflow/Missions 页面保留，但 sidebar 中标记为"旧版"
3. **产物安全限制**: 只允许读取 `output/minidelivery` 下的文件，防止路径穿越攻击
