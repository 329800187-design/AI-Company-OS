# Phase 4.1：Research Agent 联网搜索 MVP

> 状态：已完成 MVP  
> 范围：Research Agent 接入可替换搜索服务，保留 sources，并在 MiniDelivery 产物中展示来源。

## 一、目标

让 Research Agent 从「纯 LLM / 模板式调研」升级为「先搜索、再分析」：

1. 用户提交调研目标。
2. Research Agent 调用 Web Search Service 获取搜索结果。
3. 搜索结果注入 LLM prompt。
4. `structured_output.sources` 保留来源。
5. MiniDelivery `artifact.md` 展示「信息来源」。

## 二、改动文件

| 文件 | 说明 |
| --- | --- |
| `backend/services/web_search_service.py` | 新增可替换搜索服务层 |
| `agents/research_agent/agent.py` | Research Agent 执行前搜索，并将 sources 注入输出 |
| `tests/test_web_search_service.py` | 搜索服务单元测试 |
| `tests/test_research_execute.py` | Research 搜索集成测试 |
| `tests/test_minidelivery.py` | Research sources 渲染测试 |

## 三、搜索服务设计

统一入口：

```python
from backend.services.web_search_service import search_web

results = search_web("手工耳环市场分析", max_results=5)
```

统一返回：

```json
[
  {
    "title": "搜索结果标题",
    "url": "https://example.com/report",
    "snippet": "摘要",
    "source": "example.com",
    "published_date": "2025-01-01"
  }
]
```

## 四、Provider 配置

| Provider | 环境变量 | 说明 |
| --- | --- | --- |
| `auto` | `WEB_SEARCH_PROVIDER=auto` | 默认，自动检测 API key |
| `mock` | `WEB_SEARCH_PROVIDER=mock` | 本地 fallback，无需 API key |
| `serpapi` | `SERPAPI_API_KEY=...` | SerpAPI Google Search |
| `bing` | `BING_SEARCH_API_KEY=...` | Bing Web Search API |

无真实 API key 时，系统自动降级为 `MockSearchProvider`。

## 五、Research Agent 执行链路

```mermaid
flowchart LR
  A["用户调研目标"] --> B["search_web()"]
  B --> C["搜索结果格式化为 search_context"]
  C --> D["注入 Research prompt"]
  D --> E["LLM 分析或模板 fallback"]
  E --> F["structured_output.sources"]
  F --> G["MiniDelivery artifact.md 信息来源"]
```

## 六、配置真实搜索 API

### 6.1 SerpAPI（推荐）

1. 注册 [SerpAPI](https://serpapi.com/) 账号（免费额度 100 次/月）。
2. 在控制台获取 API Key。
3. 设置环境变量：

```bash
# Linux / macOS
export SERPAPI_API_KEY="your_api_key_here"

# Windows PowerShell
$env:SERPAPI_API_KEY = "your_api_key_here"

# .env 文件（推荐）
SERPAPI_API_KEY=your_api_key_here
WEB_SEARCH_PROVIDER=auto
```

### 6.2 Bing Web Search API

1. 注册 [Azure](https://azure.microsoft.com/) 账号。
2. 创建 Bing Search v7 资源，获取 Subscription Key。
3. 设置环境变量：

```bash
# Linux / macOS
export BING_SEARCH_API_KEY="your_api_key_here"

# Windows PowerShell
$env:BING_SEARCH_API_KEY = "your_api_key_here"

# .env 文件（推荐）
BING_SEARCH_API_KEY=your_api_key_here
WEB_SEARCH_PROVIDER=auto
```

### 6.3 强制指定 Provider

```bash
# 强制使用 SerpAPI（即使也配了 Bing key）
WEB_SEARCH_PROVIDER=serpapi

# 强制使用 Bing
WEB_SEARCH_PROVIDER=bing

# 强制使用 mock（本地调试用）
WEB_SEARCH_PROVIDER=mock
```

### 6.4 验证配置

```bash
# 检查当前 provider
python -c "from backend.services.web_search_service import get_provider_info; print(get_provider_info())"

# 测试搜索
python -c "from backend.services.web_search_service import search_web; print(search_web('test', max_results=2))"
```

返回示例：

```json
{"provider": "SerpAPIProvider", "has_api_key": true, "env_provider": "auto"}
```

### 6.5 前端展示

Research 页面结果区会自动显示搜索来源状态：

| Provider | 显示 | 图标 |
|---|---|---|
| `MockSearchProvider` | ⚠️ 模拟搜索 | 数据库图标（黄色） |
| `SerpAPIProvider` | ✅ SerpAPI 实时搜索 | 地球图标（绿色） |
| `BingSearchProvider` | ✅ Bing 实时搜索 | 地球图标（绿色） |

搜索结果数量也会以 `N 条来源` 的形式展示。

## 七、验收结果

已验证：

- `python -c "import backend.app; print('ok')"` 通过。
- `tests/test_web_search_service.py` 通过。
- Research 搜索相关单元测试通过。
- MiniDelivery Research sources 渲染测试通过。
- `frontend-new && npm run build` 通过。

已知非本轮问题：

- `tests/test_research_execute.py` 中 2 个旧用例仍失败：
  - Governance Guard 对「帮我赚钱」未拦截。
  - `/governance/run` 端点当前返回 404。
- `tests/test_minidelivery.py` 中部分列表分页测试依赖旧的 `OUTPUT_ROOT` patch 方式，和本轮 sources 渲染无关。

## 八、剩余风险

1. Mock provider 返回模拟数据，正式使用需要配置真实搜索 API key。
2. 真实搜索 API 的延迟、限流、费用需要单独评估。
3. LLM 可能改写 sources 格式，当前实现会在 sources 缺失时用搜索结果兜底。
4. 当前不是浏览器爬虫/OpenClaw 深度抓取，只是 Web Search Service MVP。
