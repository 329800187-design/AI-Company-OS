# AI Company OS

这是一个私有项目：一人公司 AI 操作系统。

## 最初目标

这个项目不是普通聊天机器人，而是希望做成一个“AI 公司操作系统”：

- 用户只说目标，系统负责理解、拆解、分配、执行、验收和归档。
- 不同业务入口对应不同“部门”：市场、图片、数据、调研、网站、老板工作台。
- Agent 不只是聊天回复，而要产出可保存、可预览、可下载的交付物。
- 普通业务 Agent 直接生产，高风险任务由 Governance 做风控。
- Boss 工作台只是高层入口，不是整个系统本体。

## 当前完整代码在哪里

完整项目进度已推送到分支：

`codex/current-progress-20260705`

完整代码链接：

https://github.com/329800187-design/AI-Company-OS/tree/codex/current-progress-20260705

## 当前进度

截至 2026-07-05，项目推进到：

> 前端展示验收 + 业务 Agent 链路打通阶段

已经完成：

- MiniDelivery v1 已冻结：保存、列表、详情、预览、下载、归档。
- Marketing / Image / Data / Research / Website 五个业务 Agent 已完成 LLM-first + template fallback。
- 前端五个业务页开始按 structured_output 展示结构化产物。
- 保存到交付中心的 404 已修复。
- Marketing 页已从“小红书/抖音平台限制”扩展为文案类型选择。
- 普通业务 Agent 已避免被 Governance Guard 误拦截。

## 下一步

下一步不是扩新功能，而是端到端验收：

1. 逐页测试 Marketing / Image / Data / Research / Website。
2. 确认每页能生成、能展示结构化字段、能显示 fallback/source/warnings。
3. 每页点击“保存到交付中心”。
4. 到 Delivery 页面确认预览和下载内容没有丢关键字段。
5. 如果保存后的 Markdown 丢字段，只修字段映射，不扩 MiniDelivery 功能。

## 关键文档

完整分支中重点看：

- `docs/project_progress_snapshot_2026-07-05.md`
- `docs/project_progress_snapshot_2026-07-04.md`
- `docs/VISION.md`
- `README.md`
