# AI Company OS Progress Snapshot - 2026-07-06

## 当前阶段

AI Company OS 已完成本轮核心收口：

> 五个业务页 + MiniDelivery 交付中心端到端闭环验收完成

本阶段确认的主链路是：

```text
业务页面输入
-> /agents/{agent_id}/execute
-> structured_output 前端展示
-> 保存到 MiniDelivery
-> Delivery 搜索 / 预览 / 详情 / 下载
```

验收对象：

```text
Marketing / Image / Data / Research / Website
```

## 今日结论

### 1. Marketing 页面完成 7 种模式浏览器验收

Marketing 页面当前支持：

```text
copywriting
social_media + platform=xiaohongshu
social_media + platform=douyin
seo_article
email_campaign
brand_strategy
campaign_plan
```

已验证：

- 页面可真实点击生成。
- 每种模式都能展示对应结构化字段。
- 复制按钮可用。
- 保存到交付中心成功。
- Delivery 中可搜索 task_id。
- 预览、详情、下载可用。

代表性 task_id：

```text
agent_70897dbc4433  # copywriting
agent_99474116f461  # xiaohongshu
agent_6c08483d2e4b  # douyin
agent_3e9d927fd65d  # seo_article
agent_852d55290695  # email_campaign
agent_87ea624ae821  # brand_strategy
agent_c48541fe9985  # campaign_plan
```

### 2. Image / Data / Research / Website 浏览器验收完成

四个业务页均已真实浏览器验收：

| 页面 | 生成 | 展示 | 保存 | Delivery 搜索/预览/详情/下载 |
| --- | --- | --- | --- | --- |
| Image | 通过 | 通过 | 通过 | 通过 |
| Data | 通过 | 通过 | 通过 | 通过 |
| Research | 通过 | 通过 | 通过 | 通过 |
| Website | 通过 | 通过 | 通过 | 通过 |

代表性 task_id：

```text
agent_62cd2a397a1b  # Image
agent_610f77bb6f4f  # Data
agent_d392ae683bc0  # Research
agent_bcb36e2e21da  # Website
```

### 3. Delivery 页面闭环完成

Delivery 页面已验证：

- 列表正常加载。
- 搜索 task_id 正常返回卡片。
- 空搜索结果显示空状态。
- 预览 artifact.md 正常。
- 详情页可打开。
- 下载 URL 返回 HTTP 200。
- agent_id 筛选可用。

当前本地验证中，`/minidelivery/tasks?limit=1` 可返回已有交付记录，数量级约 4400+。

## 今日关键修复

### 1. MiniDelivery Markdown 字段映射补齐

文件：

```text
backend/routers/minidelivery_router.py
```

完成：

- Marketing 支持 7 种模式字段保存。
- Image 支持 `image_prompt / negative_prompt / style / aspect_ratio / composition / lighting / color_palette / variations / limitations`。
- Data 支持 `analysis_question / data_summary / key_metrics / trends / findings / risks / recommendations / assumptions / limitations / charts_suggested`。
- Research 支持 `research_question / market_summary / key_findings / competitors / opportunities / risks / recommended_actions / limitations / sources`。
- Website 支持 `page_goal / target_audience / hero / sections / ctas / trust_elements / seo / design_direction / risks / recommendations / assumptions / limitations`。
- 兼容 Marketing Agent 返回顶层字段或嵌套对象两种形态。

### 2. Delivery 列表路径修复

文件：

```text
backend/routers/minidelivery_router.py
```

修复：

```text
OUTPUT_ROOT / "minidelivery" -> OUTPUT_ROOT
```

原因：

`OUTPUT_ROOT` 本身已经指向 `output/minidelivery`，旧逻辑多拼了一层，导致列表为空。

### 3. Delivery 搜索 None 防御

文件：

```text
backend/routers/minidelivery_router.py
```

修复搜索拼接时部分字段为 `None` 导致的异常：

```text
str(v or "")
```

### 4. 前端 Vite 代理补齐

文件：

```text
frontend-new/vite.config.ts
```

修复：

```text
/minidelivery
```

加入 Vite dev server proxy，避免前端开发模式下保存或读取 Delivery API 失败。

### 5. Delivery artifact 预览修复

文件：

```text
frontend-new/src/api/client.ts
```

修复：

```text
artifact.md 是 text/markdown，不是 JSON
```

因此预览接口改为使用 `response.text()`。

### 6. Delivery hooks 顺序修复

文件：

```text
frontend-new/src/pages/delivery/index.tsx
```

修复 React hooks 在条件 return 之后声明的问题，避免详情页/列表页切换时 hooks 顺序不稳定。

### 7. Marketing 多模式展示补齐

文件：

```text
frontend-new/src/pages/marketing/index.tsx
```

完成：

- 按不同 `task_type` 展示专属字段。
- 对数组、对象、多行文本做更可读展示。
- 修复对象字段复制时变成 `[object Object]` 的问题。
- 支持 `seo_article.keywords` 为对象或数组。

## 验证命令

今日多轮验证通过：

```bash
python -c "import backend.app; print('ok')"
cd frontend-new && npm run build
```

关键接口验证：

```text
GET /minidelivery/tasks
GET /minidelivery/tasks?q={task_id}
GET /minidelivery/tasks/{task_id}
GET /minidelivery/tasks/{task_id}/artifact
GET /minidelivery/tasks/{task_id}/download
POST /agents/{agent_id}/execute
POST /minidelivery/save-from-agent
```

## 当前边界

以下事项仍然不要在当前阶段扩展：

- 不接真实图片生成。
- 不接真实数据源。
- 不接 OpenClaw / 爬虫。
- 不扩 MiniDelivery v1。
- 不让 Governance 接管普通业务 Agent 的生产链路。
- 不改 Boss / Collaboration / sandbox，除非明确进入下一阶段。
- 不把 template fallback 伪装成真实 LLM 输出。

## 已知风险

### 1. 旧进程问题

如果浏览器看到旧行为，优先检查：

```text
localhost:8000 后端是否重启
localhost:5173 Vite dev server 是否重启
```

今日曾出现过旧后端进程导致 `/minidelivery/tasks` 仍返回 0 的情况，重启后恢复。

### 2. 浏览器自动化等待问题

Playwright 脚本容易因为以下原因误判失败：

- Agent 执行时间超过 30s。
- Delivery 搜索有 300ms debounce。
- 结果卡片渲染晚于 API 返回。

建议后续脚本等待具体网络响应或页面文本出现，不要只固定 sleep。

### 3. 中文终端乱码

PowerShell / Git Bash 输出中可能出现中文乱码，但 artifact.md 文件本身为 UTF-8，内容可正常保存和读取。

## 当前 Git 状态

主进度分支：

```text
codex/current-progress-20260705
```

关键提交：

```text
2eff3ca fix: stabilize delivery browser preview flow
cd49f53 fix: proxy minidelivery routes in dev server
316fb3c fix: render marketing task fields by type
a3592b2 fix: list saved delivery tasks from output root
6764c38 fix: preserve agent fields in delivery markdown
```

## 下一步建议

下一阶段建议进入：

> 业务页验收冻结 + 首页/导航/新手路径整理

优先级建议：

1. 写一份用户可读的“如何使用五个业务页 + 交付中心”的短文档。
2. 在 README 中更新当前已完成状态。
3. 清理或归档旧端点 `/agents/{agent_id}/run` 的使用说明，避免误用旧 Governance 路径。
4. 如要继续产品化，先做 UI 细节和空状态，不要马上扩展真实图片/爬虫/数据源。
5. 若要自动化验收，整理一份正式 Playwright e2e，不提交临时脚本和截图产物。

## Handoff Prompt

```text
请先阅读：
1. docs/project_progress_snapshot_2026-07-06.md
2. docs/project_progress_snapshot_2026-07-05.md
3. docs/claude_working_rules.md

当前阶段：
五个业务页 + MiniDelivery 交付中心端到端闭环已经验收完成。

已经完成：
- Marketing 7 种模式真实浏览器验收通过。
- Image / Data / Research / Website 真实浏览器验收通过。
- Delivery 列表、搜索、预览、详情、下载通过。
- MiniDelivery 保存 Markdown 字段映射已补齐。
- Vite dev server 已代理 /minidelivery。

下一步不要扩 Agent 能力。
请优先做“阶段冻结与产品可用性整理”：

1. 更新 README 当前进度。
2. 写用户使用说明：如何进入五个业务页、生成、保存、到 Delivery 查看。
3. 检查首页/导航是否能让用户找到这些入口。
4. 如发现小 UI/文案问题，可修；不要接真实图片生成、真实数据源、OpenClaw。

验证要求：
- python -c "import backend.app; print('ok')"
- cd frontend-new && npm run build

输出：
A. 修改了哪些文件
B. 是否改变 API
C. 是否影响 Governance / MiniDelivery / Collaboration
D. 验证结果
E. 剩余风险
```
