# 第二阶段 Boss Lite 最终验收文档

> 阶段名称：Boss Lite — 一句话目标 → 多 Agent 协同执行
> 验收日期：2026-07-07
> 版本：v1.5.0
> 分支：codex/current-progress-20260705
> 状态：**第二阶段核心闭环已完成，可进入第三阶段**

---

## 一、阶段目标（一句话）

用户输入一句话业务目标，系统自动拆解为 5 个业务 Agent，并行执行（含 Handoff 上下文传递），生成可读作战报告，自动保存到交付中心，支持历史工作台回溯。

核心理念：**一句话 → 多部门协同（含 Handoff） → 一份可执行的作战包 → 历史可查可复用**。

---

## 二、最终能力清单

### 2.1 Boss Lite 核心闭环

| # | 能力 | 说明 | 状态 |
|---|------|------|------|
| 1 | 一句话目标输入 | Textarea 输入业务目标，支持示例快速填入 | ✅ |
| 2 | 8 个常用作战模板 | 一键填入目标，可继续编辑 | ✅ |
| 3 | 5 个业务 Agent 拆解 | 自动映射到 research / marketing / image / data / website | ✅ |
| 4 | 并行执行 | ThreadPoolExecutor，max_workers=5 | ✅ |
| 5 | Handoff v1 | research / data 上游洞察自动传递给 marketing / image / website | ✅ |
| 6 | 可读 Boss 作战报告 | Markdown 格式，含总目标、执行计划、各部门结论、Boss 建议 | ✅ |
| 7 | 自动保存 MiniDelivery | artifact.md + raw_agent_result.json + result.json | ✅ |
| 8 | Delivery 搜索/预览/详情/下载 | 按 task_id 搜索，预览 artifact.md，详情页正常，下载 HTTP 200 | ✅ |
| 9 | 进度 UI | 4 阶段动画（拆解 → 并行执行 → 汇总 → 保存） | ✅ |
| 10 | 总耗时 + 单 Agent 耗时 | 汇总 banner 显示总耗时，每个 Agent 卡片显示独立耗时 | ✅ |

### 2.2 Handoff 协同能力

| # | 能力 | 说明 | 状态 |
|---|------|------|------|
| 1 | 两波执行模式 | Wave 1: research/data → Wave 2: marketing/image/website | ✅ |
| 2 | 上游洞察提取 | 从 research/data 的 structured_output 中提取关键洞察 | ✅ |
| 3 | 下游 Agent 接收 | marketing/image/website 的 task context 附带上游洞察 | ✅ |
| 4 | Handoff 状态字段 | handoff_enabled / execution_mode / used_handoff / handoff_sources | ✅ |
| 5 | 前端 Handoff 可视化 | Summary Banner 显示 flow，下游卡片显示「已参考上游洞察」 | ✅ |
| 6 | 部分 Agent Handoff | 仅执行部分 Agent 时，handoff 自动适配 | ✅ |

### 2.3 Boss Lite 历史工作台

| # | 能力 | 说明 | 状态 |
|---|------|------|------|
| 1 | 历史面板 | 列出所有 Boss Lite 历史执行记录 | ✅ |
| 2 | 搜索 | 支持按 task_id / goal / artifact_type / source_page / execution_mode 搜索 | ✅ |
| 3 | 排序 | newest / oldest / task_id 三种排序 | ✅ |
| 4 | 加载更多 | 分步加载（每次 5 条），支持 has_more 判断 | ✅ |
| 5 | 隐藏与恢复 | 单条隐藏（localStorage），支持恢复全部 | ✅ |
| 6 | 复制目标 | 一键复制历史任务的 goal 文本 | ✅ |
| 7 | 复用目标 | 一键将历史 goal 填入输入框，重新执行 | ✅ |
| 8 | 查看交付物 | 跳转到 Delivery 详情页 | ✅ |
| 9 | 复盘 Badge | 成功率、耗时、Handoff 标记、execution_mode | ✅ |

### 2.4 运行环境说明

| 项 | 说明 |
|----|------|
| 后端 | FastAPI，端口 8000 |
| 前端 | Vite dev server，端口 5173，代理到 8000 |
| 数据库 | SQLite（WAL 模式） |
| AI Provider | DeepSeek / OpenAI / Claude 可切换 |
| 模板 fallback | 未配置 API Key 时使用模板产出 |

---

## 三、已验证的关键 task_id

| task_id | 验证内容 | 创建时间 |
|---------|----------|----------|
| `boss_91329f9f810d` | 浏览器验收：搜索/预览/详情/下载，goal: "browser acceptance: handmade silver jewelry launch plan" | 2026-07-06 |
| `boss_9c21dac31fae` | Handoff 验证：5 Agent 完整执行，下游 used_handoff=true | 2026-07-06 |
| `boss_932d0b352f0e` | Handoff 验证：artifact.md 包含上游洞察传递 | 2026-07-06 |
| `boss_c7dba8f25408` | Handoff 验证：部分 Agent 执行，handoff_sources 正确 | 2026-07-06 |
| `boss_27654a577ba5` | 历史工作台验证：列表/搜索/排序/隐藏/恢复/复制目标/复用目标 | 2026-07-06 |
| `boss_b8241c004c4d` | 早期验收：搜索、预览、详情、下载 | 2026-07-05 |
| `boss_0fbb4623b07b` | 早期验收：搜索、预览、详情、下载 | 2026-07-05 |
| `boss_d93dae73ab76` | 早期验收：搜索、预览、详情、下载 | 2026-07-05 |

---

## 四、API 级验收

### 4.1 Boss Lite 执行

```
POST /boss/lite/execute
```

**请求体：**
```json
{
  "goal": "业务目标文本（2-5000 字符）",
  "agents": null,
  "save_to_delivery": true
}
```

**响应关键字段：**

| 字段 | 类型 | 说明 |
|------|------|------|
| `ok` | bool | 执行是否成功 |
| `task_id` | string | 任务 ID（格式：`boss_lite_{hex8}`） |
| `goal` | string | 用户输入的目标 |
| `handoff_enabled` | bool | 是否启用了 Handoff |
| `execution_mode` | string | `"two_wave_handoff"` 或 `"parallel"` |
| `results` | array | 5 个 Agent 的执行结果 |
| `results[i].used_handoff` | bool | 该 Agent 是否使用了上游洞察 |
| `results[i].handoff_sources` | string[] | 上游来源 Agent 列表 |
| `results[i].duration_ms` | number | 单 Agent 耗时（毫秒） |
| `summary.succeeded` | int | 成功 Agent 数 |
| `summary.failed` | int | 失败 Agent 数 |
| `summary.total_duration_ms` | number | 总耗时（毫秒） |
| `delivery_task_id` | string | 保存到 MiniDelivery 的 task_id（格式：`boss_{hex12}`） |

**验证命令：**
```bash
curl -X POST http://localhost:8000/boss/lite/execute \
  -H "Content-Type: application/json" \
  -d '{"goal": "test goal", "save_to_delivery": true}'
```

### 4.2 MiniDelivery 查询

```
GET /minidelivery/tasks?agent_id=boss&limit=1
```

返回 Boss Lite 最近执行记录，包含 total_duration_ms / handoff_enabled / execution_mode 等复盘字段。

**验证命令：**
```bash
curl "http://localhost:5173/minidelivery/tasks?agent_id=boss&limit=1"
```

### 4.3 MiniDelivery 详情

```
GET /minidelivery/tasks/{task_id}
```

返回完整交付物元信息，包括 goal / agent_id / artifact_type / created_at / ok 等字段。

**验证命令：**
```bash
curl "http://localhost:5173/minidelivery/tasks/boss_91329f9f810d"
```

### 4.4 MiniDelivery Artifact

```
GET /minidelivery/tasks/{task_id}/artifact
```

返回 artifact.md 的 Markdown 内容。

**验证命令：**
```bash
curl "http://localhost:5173/minidelivery/tasks/boss_91329f9f810d/artifact"
```

### 4.5 MiniDelivery 下载

```
GET /minidelivery/tasks/{task_id}/download
```

返回 HTTP 200，文件内容为 artifact.md。

**验证命令：**
```bash
curl -o /dev/null -w "%{http_code}" "http://localhost:5173/minidelivery/tasks/boss_91329f9f810d/download"
```

### 4.6 Handoff 相关字段

| 字段 | 位置 | 说明 |
|------|------|------|
| `handoff_enabled` | 响应顶层 | 是否实际启用 handoff |
| `execution_mode` | 响应顶层 | `"two_wave_handoff"` 或 `"parallel"` |
| `results[i].used_handoff` | 每个 Agent 结果 | 该 Agent 是否使用了上游洞察 |
| `results[i].handoff_sources` | 每个 Agent 结果 | 上游来源 Agent 列表 |
| `structured_output.handoff_context` | Boss 汇总层 | 上游洞察结构 |
| `structured_output.handoff_sources` | Boss 汇总层 | 实际传递的上游来源 |
| `structured_output.handoff_targets` | Boss 汇总层 | 实际接收 handoff 的下游目标 |

**Handoff 规则：**

| Agent | used_handoff | handoff_sources | 角色 |
|-------|-------------|-----------------|------|
| research | false | [] | 上游（生产者） |
| data | false | [] | 上游（生产者） |
| marketing | true | [research, data] | 下游（消费者） |
| image | true | [research, data] | 下游（消费者） |
| website | true | [research, data] | 下游（消费者） |

---

## 五、浏览器验收

### 5.1 Boss Lite 核心交互

| # | 验收项 | 操作 | 预期结果 | 状态 |
|---|--------|------|----------|------|
| 1 | 打开 Boss 页面 | 访问 `/app?page=boss` | 页面正常加载 | ✅ |
| 2 | 默认 Boss Lite 模式 | 观察模式切换按钮 | Boss Lite 按钮为选中状态 | ✅ |
| 3 | 模板填入 | 点击 8 个模板中的任意一个 | Textarea 自动填入目标文本 | ✅ |
| 4 | 一键执行 | 点击「一键执行」按钮 | 按钮变为「执行中，约需1分钟...」 | ✅ |
| 5 | 进度 UI | 观察执行过程 | 4 阶段进度动画显示 | ✅ |
| 6 | 5/5 Agent 成功 | 等待执行完成 | 汇总 banner 显示「5/5 个 Agent 成功」 | ✅ |
| 7 | 总耗时 | 查看汇总 banner | 显示总耗时（如 18.5s） | ✅ |
| 8 | 单 Agent 耗时 | 查看 Agent 卡片 | 每个卡片显示独立耗时 | ✅ |
| 9 | Handoff flow | 查看 Summary Banner | 显示 handoff flow（如 research/data → marketing/image/website） | ✅ |
| 10 | 下游 Agent 标记 | 查看下游 Agent 卡片 | 显示「已参考上游洞察」 | ✅ |
| 11 | 保存到交付中心 | 查看汇总 banner | 显示「已保存到交付中心」和 task_id | ✅ |

### 5.2 历史工作台

| # | 验收项 | 操作 | 预期结果 | 状态 |
|---|--------|------|----------|------|
| 1 | 历史面板显示 | 点击历史按钮 | 列出 Boss Lite 历史执行记录 | ✅ |
| 2 | 搜索 task_id | 输入 task_id | 过滤出匹配的记录 | ✅ |
| 3 | 搜索 goal | 输入 goal 关键词 | 过滤出匹配的记录 | ✅ |
| 4 | 搜索 artifact_type | 输入 `boss_lite` | 过滤出匹配的记录 | ✅ |
| 5 | 搜索 source_page | 输入 `boss` | 过滤出匹配的记录 | ✅ |
| 6 | 搜索 execution_mode | 输入 `two_wave_handoff` | 过滤出匹配的记录 | ✅ |
| 7 | 排序 newest | 选择 newest | 按创建时间倒序排列 | ✅ |
| 8 | 排序 oldest | 选择 oldest | 按创建时间正序排列 | ✅ |
| 9 | 排序 task_id | 选择 task_id | 按 task_id 字母排序 | ✅ |
| 10 | 加载更多 | 点击「加载更多」按钮 | 加载下一批记录 | ✅ |
| 11 | 隐藏 | 点击单条记录的「隐藏」按钮 | 记录从列表消失 | ✅ |
| 12 | 恢复全部 | 点击「恢复全部」按钮 | 已隐藏的记录重新显示 | ✅ |
| 13 | 复制目标 | 点击「复制目标」按钮 | goal 文本复制到剪贴板，按钮显示「已复制」 | ✅ |
| 14 | 复用目标 | 点击「复用目标」按钮 | goal 填入输入框，可重新执行 | ✅ |
| 15 | 查看交付物 | 点击「查看交付物」按钮 | 跳转到 Delivery 详情页 | ✅ |
| 16 | 复盘 Badge | 查看历史记录卡片 | 显示成功率、耗时、Handoff、execution_mode | ✅ |

### 5.3 Delivery 页面验收

| # | 验收项 | 操作 | 预期结果 | 状态 |
|---|--------|------|----------|------|
| 1 | 搜索 task_id | 搜索 `boss_91329f9f810d` | 找到对应交付物 | ✅ |
| 2 | 预览 artifact.md | 点击预览 | 显示 Markdown 作战报告 | ✅ |
| 3 | 详情页 | 点击详情 | 显示完整交付物信息 | ✅ |
| 4 | 下载 | 点击下载 | HTTP 200，文件内容正确 | ✅ |

---

## 六、剩余边界（本阶段不做）

以下能力属于第三阶段增强，不阻塞第二阶段完成标记：

| 边界 | 说明 | 原因 |
|------|------|------|
| 真实联网调研 | Research Agent 接入实时搜索 | 需接入 OpenClaw 或外部搜索 API |
| 真实图片生成 | Image Agent 接入图片生成 API | 需接入 DALL-E / Midjourney 等 |
| 真实数据源接入 | Data Agent 接入真实数据库/API | 需定义数据源配置和连接逻辑 |
| PDF 导出 | 作战报告一键导出 PDF | 需引入 PDF 渲染库 |
| 历史 Mission 对比 | 多条历史记录对比分析 | 需设计对比 UI 和差异算法 |
| 后端删除交付物 | MiniDelivery 删除功能 | 需确认删除策略（软删/硬删） |
| 多用户权限隔离 | 不同用户看到不同历史 | 需引入用户认证和权限系统 |
| 多轮对话优化 | 对单个 Agent 结果追问迭代 | 需设计对话上下文管理 |

---

## 七、第二阶段完成度判断

### 核心闭环：✅ 完成

- [x] 一句话目标输入
- [x] 5 Agent 并行执行
- [x] Handoff v1（research/data → marketing/image/website）
- [x] 可读作战报告
- [x] 自动保存 MiniDelivery
- [x] Delivery 搜索/预览/详情/下载

### 历史工作台：✅ 完成

- [x] 历史面板显示
- [x] 搜索（task_id / goal / artifact_type / source_page / execution_mode）
- [x] 排序（newest / oldest / task_id）
- [x] 加载更多
- [x] 隐藏与恢复
- [x] 复制目标
- [x] 复用目标
- [x] 查看交付物跳转
- [x] 复盘 Badge（成功率、耗时、Handoff、execution_mode）

### 结论

**第二阶段 Boss Lite 核心闭环 + 历史工作台：已完成。**

当前剩余能力（真实联网、真实图片生成、真实数据源、PDF 导出、历史对比、多用户权限）均为第三阶段增强项，不阻塞进入下一阶段。

---

## 八、第三阶段建议方向

| 优先级 | 方向 | 说明 |
|--------|------|------|
| **P0** | Agent 协作通用化 / Collaboration Graph | 把 Boss Lite 的 handoff 扩展成通用 Agent 协作链，支持任意 Agent 间传递上下文，支持有向无环图（DAG）编排 |
| **P1** | Research 接联网搜索 | Research Agent 接入 OpenClaw 或外部搜索 API，获取实时信息 |
| **P1** | Data 接真实数据源 | Data Agent 支持连接数据库 / API，获取真实数据进行分析 |
| **P2** | Image 接真实图片生成 | Image Agent 接入 DALL-E / Midjourney 等图片生成 API |
| **P2** | 作战报告 PDF 导出 | 一键导出 PDF 格式的作战报告，支持品牌定制 |
| **P2** | 历史 Mission 对比 | 多条历史记录的结构化对比分析 |

---

## 九、验证命令

### 9.1 后端导入验证

```bash
python -c "import backend.app; print('ok')"
# 预期输出：ok
```

**本次执行结果：✅ ok**

### 9.2 前端构建验证

```bash
cd frontend-new && npm run build
# 预期输出：✓ built in X.XXs
```

**本次执行结果：✅ built in 3.42s**

### 9.3 API 代理验证

```bash
curl "http://localhost:5173/minidelivery/tasks?agent_id=boss&limit=1"
# 预期：返回 JSON，包含 total_duration_ms / handoff_enabled / execution_mode 字段
```

**注意：** 需要后端和 Vite dev server 同时运行。如看不到复盘字段，确认后端在 8000 端口启动，重启 Vite dev server。

---

## 十、与第一阶段的关系

| 项目 | 第一阶段（业务 Agent MVP） | 第二阶段（Boss Lite） |
|------|---------------------------|----------------------|
| 入口 | 5 个独立业务页面 | Boss 页面一句话入口 |
| 执行方式 | 单 Agent 单次执行 | 5 Agent 并行执行（含 Handoff） |
| 输出 | 各页面独立展示 | 统一作战报告 |
| 保存 | 各页面自行保存 | 自动批量保存 |
| 模板 | 无 | 8 个常用作战模板 |
| 耗时统计 | 无 | 总耗时 + 单 Agent 耗时 |
| 上游洞察传递 | 无 | research/data → marketing/image/website |
| 历史记录 | 无 | 历史工作台（搜索/排序/隐藏/复用） |

第一阶段的 5 个业务页面仍然独立可用，Boss Lite 是更高层的编排入口。

---

## 十一、5 个业务 Agent 定义

| Agent ID | 标题 | 任务类型 | 用途 |
|----------|------|----------|------|
| research | 市场调研 | research_brief | 调研市场趋势、目标用户、竞品和机会 |
| marketing | 营销方案 | copywriting | 生成营销策略、卖点、渠道打法和文案 |
| image | 视觉方案 | image_prompt | 生成视觉方向、图片提示词和拍摄建议 |
| data | 数据分析 | data_report | 分析关键指标、趋势和行动建议 |
| website | 落地页方案 | landing_page_copy | 生成落地页结构、首屏、卖点和 CTA |

---

## 十二、8 个作战模板

| 模板 ID | 名称 | 说明 |
|---------|------|------|
| new-product | 新品上线 | 市场定位 + 种草文案 + 视觉方向 + 数据指标 + 落地页框架 |
| cold-start | 品牌冷启动 | 用户画像 + 竞品差异 + 获客渠道 + 内容方向 + 视觉调性 |
| xiaohongshu | 小红书种草 | 5 条种草文案 + 封面方向 + 关键词策略 + 达人建议 + 数据指标 |
| douyin | 抖音短视频增长 | 5 条脚本 + 选题方向 + 投流策略 + 人设建议 + 转化指标 |
| seo | SEO 内容增长 | 关键词矩阵 + 10 篇选题 + 页面结构 + 内链策略 + 排名跟踪 |
| landing-page | 落地页转化 | 首屏文案 + 卖点排序 + 信任证明 + CTA 策略 + A/B 测试建议 |
| competitor | 竞品调研 | 5 个竞品分析 + 差异化机会 + 可借鉴打法 |
| data-review | 数据复盘 | 指标分析 + 增长归因 + 问题诊断 + 优化建议 + 行动计划 |

---

*由 AI Company OS 收口验收生成 · 2026-07-07*
