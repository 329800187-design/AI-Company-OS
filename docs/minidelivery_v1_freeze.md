# MiniDelivery v1 阶段冻结文档

> 版本：v1.0  
> 日期：2026-07-03  
> 状态：阶段冻结，不再新增功能  
> 定位：Agent 产物的保存 / 查看 / 下载通道，不负责生产

---

## 1. 定位

MiniDelivery 是 AI Company OS 的"萧何后勤"——负责把 Agent 已经生产出来的结果保存下来、管理起来、让人能查看和下载。

**核心原则：MiniDelivery 不生产内容，只管交付。**

内容生产由 5 个业务 Agent 完成：
- Marketing Agent → 营销文案
- Image Agent → 图片提示词
- Data Agent → 数据分析
- Research Agent → 调研报告
- Website Agent → 落地页文案

MiniDelivery 的职责是：
1. 接收 Agent 执行结果（save-from-agent）
2. 将结构化结果渲染为 Markdown 产物
3. 持久化到磁盘（artifact.md + result.json + raw_agent_result.json）
4. 提供列表查看、详情查看、预览、下载

---

## 2. 已完成能力

### 2.1 核心管道（Core Pipeline）

| 能力 | 说明 |
|------|------|
| 目标解析 | 从中文自然语言提取产品、平台、需求标签 |
| 模板生成 | 6 种产物类型各有一套确定性模板 |
| 验证网关 | 40+ 项检查规则，确保产物质量 |
| API 生成 | 通过 ApiModelAdapter 尝试 LLM 生成，失败自动降级到模板 |
| 文件写入 | artifact.md + result.json + raw_agent_result.json |

### 2.2 Agent 产物保存（Phase 1A）

| 能力 | 说明 |
|------|------|
| save-from-agent | 统一入口，任意 Agent 可调用 |
| 5 种渲染器 | marketing / image / data / research / website / generic |
| 产物持久化 | artifact.md（Markdown）+ result.json（元数据）+ raw_agent_result.json（原始结果） |
| source_page 来源标记 | 记录产物来自哪个业务页面 |

### 2.3 交付中心（Phase 2A/2B/3B/4A）

| 能力 | 说明 |
|------|------|
| /delivery 列表页 | 分页浏览所有交付产物 |
| 搜索 | 按 goal / task_id / agent_id 元数据搜索（不搜全文） |
| 筛选 | 按 agent_id / artifact_type / source_page 筛选 |
| 详情页 | 查看产物元数据 + Markdown 内容 + 原始 Agent 结果 |
| 预览 | 在列表页内联预览 Markdown 内容 |
| 下载 | 以文件附件形式下载产物 |
| 分页 | limit/offset 分页，has_more 标记 |
| 路径安全 | 防路径遍历攻击，task_id 白名单校验 |

### 2.4 五个业务页面集成

| 页面 | 文件 | agentId | sourcePage |
|------|------|---------|------------|
| 营销文案 | `pages/marketing/index.tsx` | `"marketing"` | `"marketing"` |
| 图片提示词 | `pages/image/index.tsx` | `"image"` | `"image"` |
| 数据分析 | `pages/data/index.tsx` | `"data"` | `"data"` |
| 调研分析 | `pages/research/index.tsx` | `"research"` | `"research"` |
| 网站落地页 | `pages/website/index.tsx` | `"website"` | `"website"` |

每个页面在 Agent 执行成功后显示"保存到交付中心"按钮，调用 `POST /minidelivery/save-from-agent`。

---

## 3. 明确不包含（v1 冻结边界）

以下功能在 v1 阶段**不做**，留待后续阶段：

| 功能 | 说明 | 候选阶段 |
|------|------|----------|
| 编辑产物 | 不支持在线编辑已保存的 Markdown | v2 |
| 删除产物 | 不支持删除 | v2 |
| 分享产物 | 不支持生成分享链接 | v2+ |
| 版本管理 | 不支持同一产物的版本追踪 | v2+ |
| 标签系统 | 不支持自定义标签分类 | v2 |
| 批量导出 | 不支持多产物打包下载 | v2+ |
| artifact 全文搜索 | 当前只搜元数据，不搜 Markdown 内容 | v2+ |
| Templates 迁移 | 不迁移已有模板系统 | v2 |
| Collaboration 集成 | 不与协作计划系统打通 | v2 |
| /execution/run | 不新增执行运行端点 | v2 |

---

## 4. 后端接口清单

基础路径：`/minidelivery`

| 方法 | 路径 | 阶段 | 说明 |
|------|------|------|------|
| POST | `/xhs-copy-pack` | Core | 旧版小红书文案包生成（兼容保留） |
| POST | `/copy-pack` | Core | 通用文案包生成（指定平台/类型） |
| POST | `/save-from-agent` | Phase 1A | 保存 Agent 执行结果到交付中心 |
| GET | `/tasks` | Phase 2A | 列出所有交付任务，支持搜索/筛选/分页 |
| GET | `/tasks/{task_id}` | Phase 2A | 获取任务详情 |
| GET | `/tasks/{task_id}/artifact` | Phase 2A | 获取产物 Markdown 原文 |
| GET | `/tasks/{task_id}/download` | Phase 2B | 下载产物文件 |

---

## 5. 前端页面/组件清单

### 页面

| 路由 | 文件 | 说明 |
|------|------|------|
| `/delivery` | `pages/delivery/index.tsx` | 交付中心列表页（搜索/筛选/分页/预览/下载） |
| `/delivery?taskId=xxx` | `pages/delivery/index.tsx` | 详情视图（同页面，pushState 切换） |

### 组件

| 组件 | 文件 | 说明 |
|------|------|------|
| SaveToDeliveryButton | `components/features/save-to-delivery-button.tsx` | "保存到交付中心"按钮，5 个业务页面复用 |

### API 客户端方法

| 方法 | 对应接口 |
|------|----------|
| `api.saveAgentResultToDelivery(payload)` | POST `/minidelivery/save-from-agent` |
| `api.listMiniDeliveryTasks(filters)` | GET `/minidelivery/tasks` |
| `api.getMiniDeliveryTaskDetail(taskId)` | GET `/minidelivery/tasks/{taskId}` |
| `api.getMiniDeliveryArtifact(taskId)` | GET `/minidelivery/tasks/{taskId}/artifact` |
| `api.getMiniDeliveryDownloadUrl(taskId)` | 生成下载 URL 字符串 |

---

## 6. 数据目录结构

```
output/minidelivery/
├── agent_{task_id}/
│   ├── artifact.md              # Markdown 产物（可读、可下载）
│   ├── result.json              # 元数据（task_id, agent_id, goal, checks, created_at, ...）
│   └── raw_agent_result.json    # 原始 Agent 返回的结构化结果（save-from-agent 时写入）
```

产物命名优先级（下载时按此顺序查找）：
1. `xiaohongshu_pack.md`
2. `copy_pack.md`
3. `artifact.md`

---

## 7. 支持的产物类型

| 类型 | 平台 | 模板前缀 | 验证规则 |
|------|------|----------|----------|
| `copy_pack` | xiaohongshu | `xhs_` | 标题 ≥3、标签 ≥5、正文 ≥120 字、含产品名、无占位符 |
| `copy_pack` | douyin | `cp_` | 开头钩子、分镜脚本、卖点、使用场景、互动引导 |
| `image_prompt_pack` | — | `img_` | 主提示词、细节提示词、场景提示词、负面提示词 |
| `research_brief` | — | `rb_` | 调研目标、目标用户、竞品维度、痛点假设、风险提示 |
| `landing_page_copy` | — | `lp_` | 页面定位、主标题、副标题、卖点、页面结构、CTA、FAQ |
| `data_report` | — | `dr_` | 分析目标、数据范围、核心指标、趋势观察、异常检查 |

---

## 8. 测试覆盖

### test_minidelivery.py（~120 测试用例）

| 测试类 | 用例数 | 覆盖范围 |
|--------|--------|----------|
| TestDeliverySpec | 7 | 目标解析：平台/产品/需求提取 |
| TestTemplateGenerator | 11 | 模板生成：格式、章节、字数、占位符检查 |
| TestArtifactWriter | 3 | 文件写入：正确性、嵌套目录、自定义文件名 |
| TestVerifier | 6 | 验证器：通过/失败/占位符/抖音 |
| TestPipeline | 9 | 管道：降级路径、API 路径、result.json、一致性 |
| TestCopyPackPipeline | 5 | 文案包管道：小红书/抖音/占位符降级 |
| TestResultJson | 6 | result.json 结构：必需字段、一致性、诊断字段 |
| TestModels | 5 | 请求模型：校验、拒绝空输入 |
| TestSmoke | 3 | E2E 冒烟测试 |
| TestImagePromptPack* | 14 | 图片提示词包：模板/验证器/管道 |
| TestResearchBrief* | 13 | 调研简报：模板/验证器/管道 |
| TestLandingPageCopy* | 13 | 落地页文案：模板/验证器/管道 |
| TestSaveFromAgent | 17 | Agent 保存：5 种渲染器/文件创建/元数据 |
| TestListTasks | 14+ | 列表：排序/筛选/分页/搜索/容错 |
| TestDownloadArtifact | 10 | 下载：正确性/安全/优先级文件名 |
| TestGetTaskDetail | 5 | 详情：原始结果/容错/元数据 |

### 其他测试套件

| 文件 | 测试范围 |
|------|----------|
| test_marketing_execute.py | Marketing Agent `/execute` 端点 + Governance 守卫 |
| test_image_execute.py | Image Agent `/execute` 端点 + Governance 守卫 |
| test_data_execute.py | Data Agent `/execute` 端点 + 分析场景 |
| test_research_execute.py | Research Agent `/execute` 端点 + 模板模式 |
| test_website_execute.py | Website Agent `/execute` 端点 + 模板降级 |

---

## 9. 当前状态

- 五个业务入口均已接入 Agent-first 流程
- MiniDelivery v1 可用：Agent 执行 → 保存 → 查看 → 下载
- 测试通过（2026-07-03 回归确认）
- Frontend build 通过

---

## 10. 下一阶段候选项

按优先级排序：

1. **产物编辑** — 支持在线编辑已保存的 Markdown
2. **产物删除** — 支持删除不需要的交付物
3. **标签系统** — 自定义标签分类，支持按标签筛选
4. **全文搜索** — 搜索 Markdown 内容（而非仅元数据）
5. **版本管理** — 同一目标的多次执行版本追踪
6. **分享链接** — 生成可分享的只读链接
7. **批量导出** — 多产物打包为 ZIP 下载
8. **Collaboration 集成** — 与多步骤协作计划打通
9. **Templates 迁移** — 统一模板管理系统

---

> **冻结说明**：此文档标记 MiniDelivery v1 的功能边界。在此之后新增的任何功能都属于 v2 范畴，需要重新评估优先级和设计。
