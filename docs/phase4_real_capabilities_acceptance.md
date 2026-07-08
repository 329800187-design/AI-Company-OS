# Phase 4：真实能力接入 — 最终验收文档

> 状态：**核心闭环完成**（2026-07-09）  
> 范围：三条主线 — Research Web Search / Data Real Data Source / Image Generation Provider

---

## 总览

Phase 4 目标是将 Agent 从「纯 LLM / 模板框架」升级为「具备真实外部能力」。三条主线均采用 **Provider 模式**：统一接口 + 可替换实现 + mock 默认 fallback，确保无 API key 时系统仍可正常运行。

| 主线 | 子阶段 | 状态 | 真实能力 | Mock 能力 |
|------|--------|------|----------|-----------|
| A. Research Web Search | 4.1 | ✅ MVP 完成 | SerpAPI / Bing（代码就绪，key 未验收） | MockSearchProvider ✅ |
| B. Data Real Data Source | 4.4 | ✅ MVP 完成 | CSV/JSON/inline/URL 真实读取 ✅ | 无需 mock（读真实文件） |
| C. Image Generation | 4.8 | ✅ 骨架完成 | OpenAI DALL-E（代码就绪，key 未验收） | MockImageProvider ✅ |

---

## A. Research Web Search（Phase 4.1）

### 目标

Research Agent 从「纯 LLM 调研」升级为「先搜索、再分析」。

### 修改文件

| 文件 | 说明 |
|------|------|
| `backend/services/web_search_service.py` | **新增** — 可替换搜索服务层（203 行） |
| `agents/research_agent/agent.py` | **修改** — 执行前调用 `search_web()`，结果注入 LLM prompt |
| `tests/test_web_search_service.py` | **新增** — 搜索服务单元测试 |
| `tests/test_research_execute.py` | **新增** — Research 搜索集成测试 |
| `tests/test_minidelivery.py` | **修改** — Research sources 渲染测试 |

### API 变化

- **不改变** `/agents/research/execute` 请求格式
- **增量返回**：
  - `structured_output.sources` — 已规范化的搜索来源列表（`string[]`，如 `标题 — URL`）
  - `metadata.search_provider` — 当前搜索 provider 类名（如 `MockSearchProvider` / `SerpAPIProvider` / `BingSearchProvider`）
  - `metadata.has_search_results` — fallback 路径下可选返回，表示是否拿到搜索结果

### 新增字段

| 字段 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `sources` | `list[str]` | `structured_output` | 搜索来源列表，已统一为可直接渲染的字符串 |
| `search_provider` | `str` | `metadata` | provider 类名 |
| `has_search_results` | `bool` | `metadata` | fallback 路径可选字段 |

### 前端展示

Research 页面结果区自动显示搜索来源状态：

| Provider | 显示 | 图标 |
|----------|------|------|
| `MockSearchProvider` | ⚠️ 模拟搜索 | 数据库图标（黄色） |
| `SerpAPIProvider` | ✅ SerpAPI 实时搜索 | 地球图标（绿色） |
| `BingSearchProvider` | ✅ Bing 实时搜索 | 地球图标（绿色） |

搜索结果数量以 `N 条来源` 形式展示。

### MiniDelivery artifact 展示

```markdown
## 信息来源

1. [搜索结果标题](https://example.com/report)
   > 摘要内容
```

### 验证命令

```bash
# 检查当前 provider
python -c "from backend.services.web_search_service import get_provider_info; print(get_provider_info())"

# 测试搜索
python -c "from backend.services.web_search_service import search_web; print(search_web('test', max_results=2))"

# 后端 import 验证
python -c "import backend.app; print('ok')"

# 前端构建验证
cd frontend-new && npm run build
```

### Provider 配置

| Provider | 环境变量 | 说明 |
|----------|----------|------|
| `auto` | `WEB_SEARCH_PROVIDER=auto` | 默认，自动检测 API key |
| `mock` | `WEB_SEARCH_PROVIDER=mock` | 本地 fallback，无需 API key |
| `serpapi` | `SERPAPI_API_KEY=...` | SerpAPI Google Search（免费 100 次/月） |
| `bing` | `BING_SEARCH_API_KEY=...` | Bing Web Search API |

### 当前状态

- ✅ Provider 模式完整实现（Mock / SerpAPI / Bing）
- ✅ Mock provider 已验收
- ⚠️ **SerpAPI / Bing provider 代码就绪，未用真实 API key 做端到端验收**
- ✅ 前端展示逻辑完成
- ✅ MiniDelivery sources 渲染完成

### 剩余风险

1. Mock provider 返回模拟数据，正式使用需配置真实搜索 API key
2. 真实搜索 API 的延迟、限流、费用需单独评估
3. LLM 可能改写 sources 格式，当前实现会在 sources 缺失时用搜索结果兜底
4. 当前不是浏览器爬虫 / OpenClaw 深度抓取，只是 Web Search Service MVP

---

## B. Data Real Data Source（Phase 4.4）

### 目标

Data Agent 从「只写数据分析框架」升级为「能基于真实表格数据做初步分析」。

### 修改文件

| 文件 | 说明 |
|------|------|
| `backend/services/data_source_service.py` | **新增** — 统一数据源读取服务（386 行） |
| `agents/data_agent/agent.py` | **修改** — 接入 `detect_and_load()` 真实数据源检测 |
| `backend/routers/minidelivery_router.py` | **修改** — Data artifact 展示数据来源 |
| `tests/test_data_source_service.py` | **新增** — 数据源服务测试 |

### API 变化

- **不改变** `/agents/data/execute` 请求格式
- **增量返回**：
  - `metadata.data_source_type` — `"csv"` / `"json"` / `"inline"` / `"none"`
  - `metadata.sample_rows` — 样本行数

### 新增字段

| 字段 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `data_source_type` | `str` | `metadata` | 数据来源类型 |
| `sample_rows` | `int` | `metadata` | 样本行数 |

### 支持的数据源

| 来源 | 传入字段 | 状态 |
|------|----------|------|
| CSV 文件 | `file_path` / `path` | ✅ 已验收 |
| JSON 文件 | `file_path` / `path` | ✅ 已验收 |
| inline JSON 字符串 | `data` / `content` / `rows` | ✅ 已验收 |
| inline CSV 字符串 | `data` / `content` | ✅ 已验收 |
| inline `list[dict]` | `data` / `rows` | ✅ 已验收 |
| URL CSV / JSON | `url` | ✅ 服务层测试覆盖 |
| TSV 文件 | `file_path` | ✅ 服务层支持 |
| Parquet 文件 | `file_path` | ✅ 服务层支持 |
| Excel / xlsx | 原 DataAgent 路径 | 兼容保留 |

### 前端展示

Data 页面支持无数据、粘贴数据、文件路径、远程 URL 四种入口，结果区展示数据来源和样本行数。

### MiniDelivery artifact 展示

```markdown
## 数据来源

- **来源类型**: CSV 文件
- **文件名**: sales.csv
- **样本行数**: 100
- **列名**: date, sales, channel
```

无真实数据时：

```markdown
- **来源类型**: 无真实数据（框架建议）
- **样本行数**: 无
```

### 验证命令

```bash
# 后端 import 验证
python -c "import backend.app; print('ok')"

# 数据源服务验证
python -c "from backend.services.data_source_service import detect_and_load; print(detect_and_load({'data': [{'a': 1}, {'a': 2}]}).ok)"

# 前端构建验证
cd frontend-new && npm run build
```

### 当前状态

- ✅ Data Source Service 完整实现
- ✅ CSV / JSON / inline / URL 核心路径已验收
- ✅ TSV / Parquet 服务层支持，保留为增强数据源
- ✅ 有真实数据时走 pandas 分析路径
- ✅ 无真实数据时保持 LLM-first / template fallback
- ✅ 前端展示逻辑完成
- ✅ MiniDelivery 数据来源展示完成

### 剩余风险

1. CSV 编码目前尝试 utf-8 和 gbk，其他编码可能失败
2. 超大本地 CSV 未做分块读取，后续可增加 `nrows` / streaming
3. Excel 路径仍由 DataAgent 原逻辑处理，尚未统一进 Data Source Service
4. URL 数据源只做轻量读取，不做重试、鉴权和私有网络访问控制

---

## C. Image Generation Provider（Phase 4.8）

### 目标

Image Agent 从「只生成图片提示词」升级为「具备图片生成 Provider 接口」。

### 修改文件

| 文件 | 说明 |
|------|------|
| `backend/services/image_generation_service.py` | **新增** — Image Provider 接口、Mock、OpenAI（255 行） |
| `agents/image_agent/agent.py` | **修改** — 接入 provider，返回 `image_provider` 和 `generated_images` |
| `backend/routers/minidelivery_router.py` | **修改** — Image artifact 展示生成图片 |
| `frontend-new/src/pages/image/index.tsx` | **修改** — Image 页面展示生成图片卡片 |
| `tests/test_image_generation_service.py` | **新增** — Provider、Agent、artifact 测试 |

### API 变化

- **不改变** `/agents/image/execute` 请求格式
- **增量返回**：
  - `metadata.image_provider` — `"mock"` / `"openai"`
  - `structured_output.generated_images` — 生成图片列表
  - `structured_output.generated_images[].url` — 图片 URL
  - `structured_output.generated_images[].revised_prompt` — 修订后的提示词
  - `structured_output.generated_images[].is_mock` — 是否为 mock 图片

### 新增字段

| 字段 | 类型 | 位置 | 说明 |
|------|------|------|------|
| `image_provider` | `str` | `metadata` | provider 名称 |
| `generated_images` | `list[dict]` | `structured_output` | 生成图片列表 |
| `generated_images[].url` | `str` | `structured_output` | 图片 URL |
| `generated_images[].revised_prompt` | `str` | `structured_output` | 修订后提示词 |
| `generated_images[].is_mock` | `bool` | `structured_output` | 是否 mock |
| `generated_images[].size` | `str` | `structured_output` | 图片尺寸 |
| `generated_images[].index` | `int` | `structured_output` | 序号 |

### 前端展示

Image 页面结果区展示生成图片卡片，包含图片预览（mock 时为占位图）、provider 标记、尺寸信息。

### MiniDelivery artifact 展示

```markdown
## 生成图片

> Provider: mock

### 图片 1 (模拟)

![图片](https://placehold.co/1024x1024/EEE/666.png?text=Mock+Image+1)

URL: https://placehold.co/1024x1024/EEE/666.png?text=Mock+Image+1
```

### 验证命令

```bash
# 后端 import 验证
python -c "import backend.app; print('ok')"

# Provider 验证
python -c "from backend.services.image_generation_service import get_image_provider; p = get_image_provider(); print(p.name, p.is_available())"

# 前端构建验证
cd frontend-new && npm run build
```

### Provider 配置

| Provider | 环境变量 | 说明 |
|----------|----------|------|
| `mock` | `IMAGE_PROVIDER=mock` | 默认，返回占位图 |
| `openai` | `OPENAI_API_KEY=...` + `IMAGE_PROVIDER=openai` | DALL-E 3 |

选择优先级：
1. 显式传入 provider 名称
2. `IMAGE_PROVIDER` 环境变量
3. 检测到 `OPENAI_API_KEY` 时使用 `openai`
4. 默认回退到 `mock`

### 当前状态

- ✅ Provider 模式完整实现（Mock / OpenAI）
- ✅ Mock provider 已验收
- ⚠️ **OpenAI DALL-E provider 代码就绪，未用真实 API key 做端到端验收**
- ✅ 前端展示逻辑完成
- ✅ MiniDelivery 生成图片展示完成

### 剩余风险

1. `OpenAIImageProvider` 未使用真实 API key 做端到端验收
2. OpenAI provider 依赖 `httpx`，缺失时会返回 provider error
3. Mock 图片是占位图，不代表真实图片生成质量
4. 当前只接 OpenAI 预留 provider，未接 Stability / Midjourney

---

## 能力状态汇总

### ✅ 真实能力（已验收）

| 能力 | 说明 |
|------|------|
| CSV 文件读取 | utf-8 / gbk 编码自动检测 |
| JSON 文件读取 | 数组 / 嵌套结构自动解析 |
| inline 数据读取 | JSON 字符串 / CSV 字符串 / list[dict] |
| URL 数据读取 | 远程 CSV / JSON，带 timeout 和大小限制 |
| 数据源自动检测 | `detect_and_load()` 按优先级自动选择 |
| Provider 模式架构 | 统一接口 + 可替换实现 + mock fallback |

### ⚙️ 服务层支持（未作为核心浏览器验收项）

| 能力 | 说明 |
|------|------|
| TSV 文件读取 | Tab 分隔文件 |
| Parquet 文件读取 | Apache Parquet 格式 |

### ⚠️ Provider 骨架（代码就绪，真实 key 未验收）

| 能力 | Provider | 需要配置 |
|------|----------|----------|
| Web 搜索 | SerpAPI | `SERPAPI_API_KEY` |
| Web 搜索 | Bing | `BING_SEARCH_API_KEY` |
| 图片生成 | OpenAI DALL-E 3 | `OPENAI_API_KEY` + `IMAGE_PROVIDER=openai` |

### 📝 Mock 能力（本地开发/测试用）

| 能力 | 说明 |
|------|------|
| MockSearchProvider | 返回模拟搜索结果，用于无 API key 场景 |
| MockImageProvider | 返回 placehold.co 占位图，用于无 API key 场景 |

---

## 下一步建议

Phase 4 核心闭环完成，建议进入 **Phase 5：产品化**：

1. **PDF 导出** — 作战报告一键导出 PDF 格式
2. **历史 Mission 对比** — Boss Lite 历史记录对比分析
3. **真实 API key 验收** — 用 SerpAPI / OpenAI key 做端到端验收
4. **前端 DAG 编辑器** — 从表单编辑升级为图形化配置 nodes/edges
5. **多用户权限** — 用户认证、团队协作
6. **部署优化** — Docker 生产环境配置、CI/CD
