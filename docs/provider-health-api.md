# Provider Health API

> Phase 5.3 新增 — 真实 Provider Key 验收面板 MVP

## 端点

```
GET /config/providers/health
```

**认证**: 需要（遵循系统全局认证配置）

## 返回结构

```json
{
  "search": {
    "name": "MockSearchProvider",
    "is_mock": true,
    "has_api_key": false,
    "env_provider": "auto",
    "available": true,
    "providers": [
      {"name": "serpapi", "has_key": false, "env_var": "SERPAPI_API_KEY"},
      {"name": "bing", "has_key": false, "env_var": "BING_SEARCH_API_KEY"}
    ]
  },
  "image": {
    "name": "mock",
    "is_mock": true,
    "has_api_key": false,
    "env_provider": "auto",
    "available": true,
    "providers": [
      {"name": "openai", "has_key": false, "env_var": "OPENAI_API_KEY"}
    ]
  }
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | 当前使用的 provider 类名或标识 |
| `is_mock` | boolean | 是否为 mock 模式（未配置真实 API Key） |
| `has_api_key` | boolean | 是否检测到至少一个 API Key |
| `env_provider` | string | 环境变量 `WEB_SEARCH_PROVIDER` / `IMAGE_PROVIDER` 的值 |
| `available` | boolean | provider 是否可用（mock 始终为 true） |
| `providers` | array | 所有支持的真实 provider 及其 key 状态 |

### providers 数组元素

| 字段 | 类型 | 说明 |
|------|------|------|
| `name` | string | provider 名称（serpapi / bing / openai） |
| `has_key` | boolean | 对应 API Key 是否已配置 |
| `env_var` | string | 对应的环境变量名（不含值） |

## 安全说明

- **不暴露 API Key 值**：只返回 `has_key: boolean`，不返回 key 内容
- `env_var` 字段只包含变量名，不包含变量值
- 响应中不会出现 `sk-`、`SERPAPI_API_KEY=` 等敏感信息

## 配置方式

### Search Provider

| Provider | 环境变量 | 自动检测条件 |
|----------|----------|--------------|
| SerpAPI | `SERPAPI_API_KEY` | key 存在时自动启用 |
| Bing | `BING_SEARCH_API_KEY` | key 存在时自动启用 |
| Mock | 无 | 默认 fallback |

选择器环境变量：`WEB_SEARCH_PROVIDER`（默认 `auto`）

### Image Provider

| Provider | 环境变量 | 自动检测条件 |
|----------|----------|--------------|
| OpenAI DALL-E | `OPENAI_API_KEY` | key 存在时自动启用 |
| Mock | 无 | 默认 fallback |

选择器环境变量：`IMAGE_PROVIDER`（默认 `auto`）

## 前端使用

### API Client

```typescript
const health = await api.getProvidersHealth()
console.log(health.search.is_mock)  // true / false
console.log(health.image.name)      // "mock" / "openai"
```

### Settings 页面

Provider 状态卡片显示在「系统健康」卡片下方，包含：

- **联网搜索**：当前搜索 provider 状态（Mock / SerpAPI / Bing）
- **图片生成**：当前图片 provider 状态（Mock / DALL-E）
- 缺失 API Key 时显示修复提示
- 支持手动刷新

## 测试

```bash
cd /e/AI-company-os
python -m pytest backend/tests/test_provider_health.py -v
```

## 相关文件

| 文件 | 说明 |
|------|------|
| `backend/routers/config_router.py` | API 端点实现 |
| `backend/services/web_search_service.py` | Search Provider 服务 |
| `backend/services/image_generation_service.py` | Image Provider 服务 |
| `frontend-new/src/api/client.ts` | 前端 API Client |
| `frontend-new/src/pages/settings/index.tsx` | Settings 页面 UI |
| `backend/tests/test_provider_health.py` | 测试文件 |
