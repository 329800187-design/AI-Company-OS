# AI Company OS Progress Snapshot — 2026-07-04

## Current Position

AI Company OS 当前已经从“框架先行”转回“Agent 真正产出能力优先”。

系统主线保持不变：

> 多业务入口 → Agent-first 产出 → 统一 AgentRunResult → 保存到 MiniDelivery → 交付中心查看/下载

Boss 工作台仍只是一个高层入口，不是系统全部。当前重点不是继续加大框架，而是让各业务 Agent 真正能调用 LLM 产出结构化结果，同时保留框架、风控、测试和交付约束。

## Stable Foundation

截至本快照，以下基础能力已相对稳定：

- 五个业务入口已接入 Agent-first：Marketing / Image / Data / Research / Website。
- MiniDelivery v1 已冻结：保存、列表、详情、预览、下载、搜索、筛选、分页可用。
- `/delivery` 已有侧边栏入口，首页也显示最近交付物。
- `AgentRunResult` 已作为前后端统一结果结构。
- Governance 继续作为风险/分类/拦截层，不接管普通业务 Agent 的生产链路。
- Collaboration / sandbox / Boss 暂不作为当前主线扩展点。

## Agent Capability Phase A

当前阶段目标：

> 释放 Agent 的真实产出能力：优先调用 `BaseAgent.call_ai()` / `BrainManager`，失败时明确模板 fallback，并通过测试约束结构。

### A1 — Marketing Agent LLM-first

状态：完成。

关键结果：

- `agents/marketing_agent/agent.py` 已从自建 AI 调用改为复用 `BaseAgent.call_ai()`。
- LLM 成功时：
  - `metadata.fallback=false`
  - `metadata.source="llm"`
  - `warnings` 不带 fallback 语义
- LLM 不可用、异常、无效 JSON 时：
  - 走模板 fallback
  - `metadata.fallback=true`
  - `metadata.source="template"`
  - `metadata.fallback_reason` 独立保存原因
  - 顶层 `warnings` 明确说明是模板/规则降级产物

### A2 — Research Agent LLM-first

状态：完成。

关键结果：

- `agents/research_agent/agent.py` 已迁移到 `BaseAgent.call_ai()` / `BrainManager`。
- 不接浏览器、不接 OpenClaw、不做真实联网搜索。
- 当前定位是“LLM 结构化研究简报”，不是实时联网调研。
- `structured_output` 已规范为研究简报结构，包括：
  - `research_question`
  - `market_summary`
  - `key_findings`
  - `competitors`
  - `opportunities`
  - `risks`
  - `recommended_actions`
  - `limitations`
  - `sources`
  - `content_type`
- 已专项验收 `metadata.source`：
  - LLM 成功固定为 `"llm"`
  - fallback 固定为 `"template"`
  - `fallback_reason` 不混入 `source`

### A3 — Image Agent LLM-first

状态：完成。

关键结果：

- `agents/image_agent/agent.py` 已从模板/规则产出升级为 LLM-first 图片提示词与创意 brief 生成。
- 本阶段明确不做真实生图：
  - 不接 DALL-E / Stable Diffusion / Midjourney
  - 不生成图片文件
  - 不调用旧图片 pipeline
  - 不接 browser / OpenClaw
- `structured_output` 重点字段：
  - `image_prompt`
  - `negative_prompt`
  - `style`
  - `aspect_ratio`
  - `composition`
  - `lighting`
  - `color_palette`
  - `subject`
  - `background`
  - `usage_suggestions`
  - `variations`
  - `limitations`
  - `content_type="image_prompt"`
- fallback 时顶层 `warnings` 会说明：
  - 当前为模板/规则降级产物
  - 非真实 LLM 生成
  - 本阶段只生成图片提示词，不生成真实图片文件

### A5 — Website Agent LLM-first

状态：完成。

关键结果：

- `agents/website_agent/agent.py` 已从自建 urllib.request AI 调用迁移到 `BaseAgent.call_ai()` / `BrainManager`。
- 旧的 `_call_ai()` 方法（直接 HTTP 调用）已移除，统一走 BrainManager 路由。
- LLM 成功时：
  - `metadata.fallback=false`
  - `metadata.source="llm"`
  - `warnings` 不带 fallback 语义
- LLM 不可用、异常、无效 JSON 时：
  - 走模板 fallback
  - `metadata.fallback=true`
  - `metadata.source="template"`
  - `metadata.fallback_reason` 独立保存原因
  - 顶层 `warnings` 明确说明是模板/规则降级产物
- `structured_output` 已规范为落地页文案结构，包括：
  - `page_goal`
  - `target_audience`
  - `hero` (headline / subheadline / primary_cta)
  - `sections` (title / content / cta)
  - `ctas` (primary / secondary / exit_intent)
  - `trust_elements`
  - `seo` (title / description / keywords)
  - `design_direction`
  - `risks`
  - `recommendations`
  - `assumptions`
  - `limitations`
  - `content_type: "landing_page_copy"`
- 本阶段不做真实建站、不生成前端项目、不部署、不调用浏览器/OpenClaw。
- 已专项验收 `metadata.source`：
  - LLM 成功固定为 `"llm"`
  - fallback 固定为 `"template"`
  - `fallback_reason` 不混入 `source`

## Reported Validation

以下为 Claude 本轮报告的测试结果，尚未由 Codex 本地重新跑全量验证：

- Marketing LLM integration：28 passed
- Research LLM integration：29 passed
- Image LLM integration：19 passed
- Image execute：17 passed
- AgentRunResult schema：15 passed
- MiniDelivery：146 passed
- Phase A3 合计报告：177 passed
- Phase A4 合计报告：207 passed
- Website LLM integration：21 passed
- Website execute：19 passed
- AgentRunResult schema：15 passed
- MiniDelivery：149 passed
- Phase A5 合计报告：204 passed
- Frontend build：通过，约 833ms

## Current Architectural Meaning

按”大汉集团”类比，现在的状态是：

- Marketing Agent：市场文案部，已经能调用谋士写文案。
- Research Agent：情报研究部，已经能写结构化研究简报，但不是实时侦察队。
- Image Agent：美术总监部，已经能产出图片创意 brief 和提示词，但还不是画师工坊。
- Data Agent：数据分析部，已经能产出结构化数据分析报告，但不是实时数据计算引擎。
- Website Agent：网站策划部，已经能产出结构化落地页文案和页面方案，但不是建站工坊。
- MiniDelivery：萧何后勤，负责把产物归档、展示、下载。
- Governance：御史台，只做风险拦截和秩序约束，不抢业务部门的活。
- Boss 工作台：董事长办公室入口之一，不是整个公司本体。

## Important Boundaries

当前不要做：

- 不要继续扩 MiniDelivery v1 功能。
- 不要做真实图片生成。
- 不要接浏览器/爬虫/OpenClaw 到 Research。
- 不要把普通业务 Agent 再绕回 Governance 生产链路。
- 不要改 Boss / Collaboration / sandbox，除非后续明确进入高风险执行阶段。
- 不要把 fallback 伪装成真实 AI 产出。

## Next Recommended Step

下一步建议进入：

> 前端展示验收阶段

5 个业务 Agent 已全部完成 LLM-first 改造（Marketing / Research / Image / Data / Website）。建议下一步验证各 Agent 的 LLM-first 产物在前端页面的展示效果，确保 structured_output 在前端正确渲染。

验收重点：

- 各业务页能显示 `structured_output` 的关键字段，而不是只展示原始 JSON。
- fallback / source / warnings 在前端可见，避免把模板产物误认为真实 LLM 产物。
- 产物保存到 MiniDelivery 后，预览和下载内容与页面展示一致。
- 不新增 MiniDelivery 功能，只修展示、字段映射和空状态。

## Sleep Note

今晚保存点：

- MiniDelivery v1 已冻结。
- Agent 能力强化 Phase A1-A5 全部完成：Marketing / Research / Image / Data / Website。
- 下一步进入前端展示验收阶段，不要跑偏到框架扩建。
