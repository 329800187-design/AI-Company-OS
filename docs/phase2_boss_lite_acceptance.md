# 第二阶段验收清单：Boss Lite

> 阶段名称：Boss Lite — 一句话目标 → 多 Agent 协同执行
> 验收日期：2026-07-07
> 版本：v1.5.0
> 分支：codex/current-progress-20260705

---

## 一、阶段目标

用户输入一句话业务目标，系统自动拆解为多个业务 Agent 任务，并行执行，生成可读的作战报告，自动保存到交付中心。

核心理念：**一句话 → 多部门协同 → 一份可执行的作战包**。

---

## 二、已完成能力

| # | 能力 | 说明 | 状态 |
|---|------|------|------|
| 1 | 一句话目标输入 | 用户在 Textarea 输入业务目标，支持示例快速填入 | ✅ |
| 2 | 5 个业务 Agent 拆解 | 自动映射到 research / marketing / image / data / website | ✅ |
| 3 | 并行执行 | ThreadPoolExecutor，最多 5 worker，全部 Agent 同时跑 | ✅ |
| 4 | 可读 Boss 作战报告 | Markdown 格式，含总目标、执行计划、各部门结论、Boss 建议 | ✅ |
| 5 | 自动保存 MiniDelivery | 生成 artifact.md + raw_agent_result.json + result.json | ✅ |
| 6 | Delivery 搜索/预览/详情/下载 | 按 task_id 搜索，预览 artifact.md，详情页正常，下载 HTTP 200 | ✅ |
| 7 | 进度 UI | 4 阶段进度条（拆解 → 并行执行 → 汇总 → 保存） | ✅ |
| 8 | 总耗时显示 | 汇总 banner 显示总耗时（秒） | ✅ |
| 9 | 单 Agent 耗时 | 每个 Agent 卡片显示独立耗时 | ✅ |
| 10 | 8 个常用作战模板 | 一键填入目标，可继续编辑 | ✅ |

---

## 三、8 个作战模板

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

## 四、用户流程

```
1. 打开 /app?page=boss
2. 默认进入 Boss Lite 模式
3. （可选）点击 8 个模板之一，自动填入目标
4. 编辑或直接使用目标文本
5. 点击「一键执行」按钮
6. 等待进度 UI 完成（约 15-30 秒）
7. 查看汇总 banner（成功数、总耗时）
8. 点击左侧 Agent 卡片，查看各部门详细产出
9. 产出自动保存到交付中心
10. 打开 Delivery 页面，按 task_id 搜索验证
```

---

## 五、API 流程

### 5.1 Boss Lite 执行

```
POST /boss/lite/execute
```

**请求体：**
```json
{
  "goal": "业务目标文本",
  "agents": null,
  "save_to_delivery": true
}
```

- `goal`：必填，2-5000 字符
- `agents`：可选，指定 Agent 列表；null 表示全部 5 个
- `save_to_delivery`：可选，默认 true

**响应：**
```json
{
  "ok": true,
  "task_id": "boss_lite_xxxx",
  "goal": "...",
  "plan": [...],
  "results": [
    {
      "agent_id": "research",
      "title": "市场调研",
      "ok": true,
      "summary": "...",
      "structured_output": {...},
      "warnings": [],
      "errors": [],
      "duration_ms": 5234.1
    }
  ],
  "summary": {
    "text": "Boss Lite 执行完成：5/5 个 Agent 成功",
    "succeeded": 5,
    "failed": 0,
    "total": 5,
    "total_duration_ms": 12345.6
  },
  "structured_output": {...},
  "delivery_task_id": "boss_b8241c004c4d"
}
```

### 5.2 执行链路

```
用户目标
  → input_validator.validate_message()
  → rate_limiter.check("boss_lite")
  → 构建 5 个 AgentTask（research / marketing / image / data / website）
  → ThreadPoolExecutor 并行执行（max_workers=5）
  → 每个 Agent 调用 execute_agent(agent_id, task)
  → 收集 structured_output
  → 渲染 Markdown 作战报告
  → 保存到 MiniDelivery（artifact.md + raw_agent_result.json + result.json）
  → 返回结果
```

### 5.3 相关端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/boss/lite/execute` | POST | Boss Lite 主入口 |
| `/boss/templates` | GET | 获取内置模板列表 |
| `/boss/missions` | POST | 指挥台模式创建 Mission |
| `/boss/missions/{id}/run` | POST | 指挥台模式执行 Mission |
| `/minidelivery/tasks?q={task_id}` | GET | 搜索交付物 |
| `/minidelivery/tasks/{task_id}` | GET | 获取交付物详情 |
| `/minidelivery/tasks/{task_id}/artifact` | GET | 获取 artifact.md 内容 |

---

## 六、前端页面行为

### 6.1 模式切换

Boss 页面有两种模式，默认为 **Boss Lite**：

- **Boss Lite**：一句话目标 → 5 Agent 并行 → 作战报告（轻量、快速）
- **指挥台**：两阶段流程（生成计划 → 确认执行），支持模块选择、浏览器授权、事件日志

### 6.2 Boss Lite 模式交互

| 行为 | 说明 |
|------|------|
| 默认模式 | Boss Lite（`useState("boss-lite")`） |
| 模板点击 | 填入 goal 到 Textarea，可继续编辑 |
| 一键执行 | 调用 `POST /boss/lite/execute` |
| 进度 UI | 4 阶段动画：拆解 → 并行执行 → 汇总 → 保存 |
| 汇总 banner | 显示成功/失败数、总耗时、交付物 ID |
| Agent 卡片 | 左侧 5 个卡片，点击切换右侧详情 |
| 详情面板 | 摘要、关键信息、原始 JSON（滚动查看） |
| 新任务按钮 | 重置状态，回到初始输入 |

### 6.3 Agent 详情展示

每个 Agent 详情包含：

- **摘要**：从 structured_output 提取的 80-120 字可读摘要
- **关键信息**：按 Agent 类型提取的结构化字段
- **原始 JSON**：可滚动查看的完整 structured_output
- **警告**：warnings 列表
- **错误**：error 信息（如有）
- **耗时**：单 Agent 执行时间

---

## 七、MiniDelivery 保存逻辑

Boss Lite 执行完成后，自动保存到 MiniDelivery：

### 7.1 保存的文件

```
{OUTPUT_ROOT}/{task_id}/
├── artifact.md           # Boss 作战报告（Markdown）
├── raw_agent_result.json # 完整 structured_output
└── result.json           # 交付物元信息
```

### 7.2 task_id 格式

```
boss_{uuid_hex_12}
```

示例：`boss_b8241c004c4d`

### 7.3 result.json 结构

```json
{
  "task_id": "boss_b8241c004c4d",
  "goal": "用户输入的目标",
  "agent_id": "boss",
  "artifact_type": "boss_lite",
  "title": "Boss Lite: 目标前50字",
  "source_page": "boss",
  "created_at": "2026-07-06T...",
  "ok": true,
  "mode": "boss_lite",
  "summary": "Boss Lite 执行完成：5/5 个 Agent 成功",
  "artifact_path": "...",
  "raw_agent_result_path": "..."
}
```

### 7.4 artifact.md 内容结构

```markdown
# Boss Lite 作战报告

## 总目标
{用户目标}

**总耗时：X.X 秒**

---

## 一、执行计划
- ✅ **市场调研** — 调研市场趋势...（耗时 X.Xs）
- ✅ **营销方案** — 生成营销策略...（耗时 X.Xs）
...

---

## 二、各部门结论

### ✅ 市场调研（耗时 X.Xs）
- **摘要：** ...
- **关键发现：** ...
- **机会：** ...
- **风险：** ...

### ✅ 营销方案（耗时 X.Xs）
- **核心文案：** ...
- **CTA：** ...
...

---

## 三、Boss 最终建议
- **先做什么：** ...
- **再做什么：** ...
- **数据追踪：** ...
- **风险提醒：** ...
- **下一步行动：** ...

---

*由 AI Company OS Boss Lite 生成 · 2026-07-06T...*
```

---

## 八、验收清单

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
| 9 | 可读摘要 | 查看 Agent 详情 | 摘要、关键信息可读 | ✅ |
| 10 | 保存到交付中心 | 查看汇总 banner | 显示「已保存到交付中心」和 task_id | ✅ |
| 11 | Delivery 搜索 | 打开 Delivery 页面，搜索 task_id | 能找到对应交付物 | ✅ |
| 12 | 预览 artifact.md | 点击预览 | 显示 Markdown 作战报告 | ✅ |
| 13 | 详情页 | 点击详情 | 显示完整交付物信息 | ✅ |
| 14 | 下载 | 点击下载 | HTTP 200，文件内容正确 | ✅ |
| 15 | 构建通过 | `npm run build` | 无报错，exit 0 | ✅ |

---

## 九、已验证 task_id 示例

以下 task_id 已在浏览器验收中验证通过：

| task_id | 验收项 |
|---------|--------|
| `boss_b8241c004c4d` | 搜索、预览、详情、下载 |
| `boss_0fbb4623b07b` | 搜索、预览、详情、下载 |
| `boss_d93dae73ab76` | 搜索、预览、详情、下载 |

---

## 十、5 个业务 Agent 定义

| Agent ID | 标题 | 任务类型 | 用途 |
|----------|------|----------|------|
| research | 市场调研 | research_brief | 调研市场趋势、目标用户、竞品和机会 |
| marketing | 营销方案 | copywriting | 生成营销策略、卖点、渠道打法和文案 |
| image | 视觉方案 | image_prompt | 生成视觉方向、图片提示词和拍摄建议 |
| data | 数据分析 | data_report | 分析关键指标、趋势和行动建议 |
| website | 落地页方案 | landing_page_copy | 生成落地页结构、首屏、卖点和 CTA |

---

## 十一、已知限制

| 限制 | 影响 | 缓解方案 |
|------|------|----------|
| 无真实图片生成 | image Agent 只产出提示词，不生成实际图片 | 提示词可用于第三方图片生成工具 |
| 无真实数据源 | data Agent 基于 LLM 推理，不接真实数据库 | 产出分析框架，用户自行填充真实数据 |
| 无联网调研 | research Agent 基于 LLM 知识，不爬取实时数据 | 产出调研框架，用户可补充最新数据 |
| 模板 fallback | 未配置 API Key 时使用模板产出 | 配置 API Key 后自动切换为 LLM 生成 |
| 顺序保存 | 5 个 Agent 并行执行，但保存到 MiniDelivery 是单次写入 | 不影响功能，仅影响极端高并发场景 |
| 中文终端乱码 | PowerShell 输出可能乱码 | artifact.md 文件本身为 UTF-8，不受影响 |

---

## 十二、与第一阶段的关系

| 项目 | 第一阶段（业务 Agent MVP） | 第二阶段（Boss Lite） |
|------|---------------------------|----------------------|
| 入口 | 5 个独立业务页面 | Boss 页面一句话入口 |
| 执行方式 | 单 Agent 单次执行 | 5 Agent 并行执行 |
| 输出 | 各页面独立展示 | 统一作战报告 |
| 保存 | 各页面自行保存 | 自动批量保存 |
| 模板 | 无 | 8 个常用作战模板 |
| 耗时统计 | 无 | 总耗时 + 单 Agent 耗时 |

第一阶段的 5 个业务页面仍然独立可用，Boss Lite 是更高层的编排入口。

---

## 十三、下一阶段建议

基于 Boss Lite 已完成的能力，下一步可选方向：

| 方向 | 说明 | 优先级 |
|------|------|--------|
| Collaboration / Agent Handoff | Agent 之间传递上下文，一个 Agent 的输出作为另一个的输入 | 高 |
| 真实数据源接入 | Data Agent 接入真实数据库/API | 中 |
| OpenClaw 联网调研 | Research Agent 接入实时搜索 | 中 |
| 真实图片生成 | Image Agent 接入图片生成 API | 中 |
| 作战报告 PDF 导出 | 一键导出 PDF 格式的作战报告 | 低 |
| 历史 Mission 回顾 | Boss Lite 历史记录查看和对比 | 低 |
| 多轮对话优化 | 支持对单个 Agent 结果进行追问和迭代 | 低 |

---

## 十四、验证命令

```bash
# 后端导入验证
python -c "import backend.app; print('ok')"

# 前端构建验证
cd frontend-new && npm run build
```
