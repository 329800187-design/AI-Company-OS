# AI Company OS Progress Snapshot - 2026-07-05

## Current Position

AI Company OS 当前已经进入：

> 前端展示验收 + 业务 Agent 链路打通阶段

不是继续扩框架，也不是继续扩 MiniDelivery。当前主线是确认：

> 前端业务页 -> 业务 Agent LLM-first 产出 -> AgentRunResult 结构化展示 -> 保存到 MiniDelivery -> 交付中心查看/下载

## Stable Foundation

截至本快照，以下内容已经成立：

- MiniDelivery v1 已冻结，继续只负责保存、列表、详情、预览、下载、归档。
- Marketing / Image / Data / Research / Website 五个业务 Agent 已完成 LLM-first + template fallback。
- 五个业务页已经开始按 `structured_output` 做前端展示验收。
- `metadata.source`、`metadata.fallback`、`metadata.fallback_reason`、`warnings` 已进入前端可见范围。
- `backend/app.py` 已注册 `minidelivery_router`，`/minidelivery/save-from-agent` 和 `/minidelivery/tasks` 当前可用。
- `/agents/{agent_id}/execute` 对普通业务 Agent 已跳过 Governance Guard，保留 Agent-first 直连生产链路。

普通业务 Agent 当前定义为：

```text
marketing / image / data / research / website
```

这批 Agent 应由自身完成 LLM-first 或 template fallback，不应在进入 Agent 前被 Governance 当作 unsupported workflow 拦截。

## Work Completed Today

### 1. Frontend structured output display

Claude 完成了 5 个业务页面的展示修补，Codex 做了复核和 TypeScript 修正。

涉及页面：

- `frontend-new/src/pages/marketing/index.tsx`
- `frontend-new/src/pages/image/index.tsx`
- `frontend-new/src/pages/data/index.tsx`
- `frontend-new/src/pages/research/index.tsx`
- `frontend-new/src/pages/website/index.tsx`

关键修复：

- Image 页从旧字段 `enhanced_prompt` 对齐到当前后端字段 `image_prompt`。
- Data 页补齐 LLM-first 数据分析字段展示，例如 `analysis_question`、`data_summary`、`key_metrics`、`findings`、`charts_suggested`。
- Website 页从旧字段 `page_type/design_notes` 对齐到 `page_goal/design_direction`，并补齐 `ctas`、`trust_elements`、`risks`、`recommendations`、`assumptions`。
- Marketing / Research / Image / Data / Website 页面均补充 fallback reason 展示。
- 前端 JSX 中 `unknown` 直接渲染导致的 TS2322 已修复。

验证：

```text
cd frontend-new
npm run build
```

结果：通过。

### 2. Marketing page scope correction

用户指出“写文案”不应只限制小红书/抖音平台。

当前 Marketing 页已经从“平台选择”改为“文案类型选择”：

```text
通用文案 -> copywriting
小红书 -> social_media + platform=xiaohongshu
抖音 -> social_media + platform=douyin
SEO 长文 -> seo_article
邮件营销 -> email_campaign
品牌策略 -> brand_strategy
活动方案 -> campaign_plan
```

这符合 Marketing Agent 当前能力列表：

```text
copywriting / social_media / seo_article / email_campaign / brand_strategy / campaign_plan
```

### 3. MiniDelivery save route fixed

问题：

```text
保存到交付中心 -> Not Found
```

根因：

```text
backend/core_app.py 注册了 minidelivery_router，
但当前实际运行入口是 backend/app.py，backend/app.py 漏注册。
```

修复：

- `backend/app.py` 引入并注册 `backend.routers.minidelivery_router`。

验证：

```text
GET /minidelivery/tasks -> 200
POST /minidelivery/save-from-agent -> 可写入
```

### 4. Governance over-blocking fixed for business execute route

问题：

Marketing 页选择“品牌策略”，输入：

```text
关于设计一个蓝牙耳机的品牌策略
```

旧行为：

```json
{
  "ok": false,
  "blocked_by_governance": true,
  "classification": {
    "capability_id": "unsupported.complex_agent_workflow"
  }
}
```

判断：

这不是 Marketing Agent 不能执行，而是 `/agents/{agent_id}/execute` 在进入 Agent 前被 Governance Guard 误拦截。

当前修复：

- `backend/routers/agent_router.py` 新增 `BUSINESS_AGENT_IDS`。
- `marketing/image/data/research/website` 走业务 Agent 直连。
- 非业务 Agent 继续受 Governance Guard 约束。

验证请求：

```text
POST /agents/marketing/execute
task_type=brand_strategy
goal=关于设计一个蓝牙耳机的品牌策略
```

当前结果：

```text
ok=true
metadata.source=llm
blocked_by_governance 不再出现
```

注意：如果用户仍看到旧行为，通常是旧 8000 后端进程未重启或浏览器缓存未刷新。

## Current Running State

本轮最后验证：

```text
python -c "import backend.app; print('ok')"
```

结果：通过。

```text
cd frontend-new
npm run build
```

结果：通过。

当前已重启本地服务：

```text
http://127.0.0.1:8000/app?page=marketing
```

如浏览器仍旧显示旧 chunk，使用 Ctrl + F5 强刷。

## Important Boundaries

当前不要做：

- 不要继续扩 MiniDelivery v1 功能。
- 不要做真实图片生成。
- 不要接浏览器、爬虫、OpenClaw 到 Research。
- 不要让 Governance 接管普通业务 Agent 的生产链路。
- 不要改 Boss / Collaboration / sandbox，除非明确进入高风险执行阶段。
- 不要把 fallback 伪装成真实 LLM 产出。

## Remaining Risks

- `/agents/{agent_id}/run` 旧端点仍有 Governance Guard。正式前端当前应走 `/agents/{agent_id}/execute`，但如果其他旧调用方还用 `/run`，可能仍被拦截。
- Marketing 页已支持更多 `task_type`，但前端结构化展示仍偏通用，品牌策略/活动方案/SEO/邮件的专属字段展示还可以继续优化。
- MiniDelivery 的 agent result Markdown renderer 仍有旧字段倾向，例如 image/data/website 保存时可能没有完全覆盖 LLM-first 新字段，需要后续专项验收。
- 当前工作区仍有大量未提交改动，不宜直接整体提交；需要分批审查和分组提交。

## Next Recommended Step

下一步建议继续做：

> 业务 Agent 端到端手动验收

验收顺序：

1. Marketing：通用文案、小红书、抖音、品牌策略各跑一次。
2. Image：确认只生成图片提示词，不误导为真实生图。
3. Data：确认生成分析报告框架/简报，不误导为真实文件解析。
4. Research：确认结构化研究简报展示正常。
5. Website：确认落地页文案字段展示正常。
6. 每页都点击“保存到交付中心”，检查 `/delivery` 中预览/下载内容是否语义一致。

## Handoff Prompt For Claude

```text
请先阅读：
1. docs/project_progress_snapshot_2026-07-05.md
2. docs/project_progress_snapshot_2026-07-04.md
3. docs/claude_working_rules.md

当前阶段：
项目已进入“前端展示验收 + 业务 Agent 端到端链路打通”阶段。
MiniDelivery v1 已冻结；Marketing / Image / Data / Research / Website 五个业务 Agent 已完成 LLM-first + template fallback。

当前已修复：
- backend/app.py 已注册 minidelivery_router。
- /agents/{agent_id}/execute 对 marketing/image/data/research/website 跳过 Governance Guard。
- Marketing 页已从平台限制改为文案类型选择。
- frontend-new npm run build 已通过。

请继续做端到端手动验收，不要扩框架：

1. 在正式前端逐页测试 Marketing / Image / Data / Research / Website。
2. 每页至少生成一次 LLM-first 或 template fallback 产物。
3. 检查 structured_output 是否以人类可读方式展示。
4. 检查 source / fallback / fallback_reason / warnings 是否可见。
5. 点击“保存到交付中心”，检查 /delivery 中预览和下载是否与页面展示语义一致。
6. 如发现保存后的 Markdown 丢字段，只修 minidelivery agent-result renderer 的字段映射，不扩 MiniDelivery 功能。

验证要求：
- python -c "import backend.app; print('ok')"
- cd frontend-new && npm run build
- 至少一个 /agents/marketing/execute brand_strategy 请求返回 ok=true 或 template fallback ok=true，不能 blocked_by_governance=true。

输出：
A. 每个页面验收结果
B. 修改了哪些文件
C. 是否改变 API
D. 是否影响 Governance / MiniDelivery / Collaboration
E. 跑了哪些测试
F. 剩余风险
```

