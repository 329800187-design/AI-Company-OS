# Phase 5.4 — 真实 Provider E2E 验收脚本

## 概述

`scripts/verify_real_providers.py` 用于验证 AI Company OS 的**真实外部 Provider**集成是否正常工作。

脚本会自动检测 `.env` 中的 API Key，有 key 就跑真实调用，没 key 就跳过（不报错）。

## 检查项

| 检查 | 触发条件 | 验证内容 |
|------|----------|----------|
| providers_health | 始终执行 | `/config/providers/health` 端点可达，返回 search + image 结构 |
| research_real_sources | `SERPAPI_API_KEY` 或 `BING_SEARCH_API_KEY` 存在 | 调用 `/agents/research/execute`，验证返回的 sources 是真实 URL（非 example.com） |
| image_generation | `OPENAI_API_KEY` 存在 | 调用 `/agents/image/execute`，验证返回的 generated_images 是真实 URL（非 placehold.co） |

## 配置 API Key

在项目根目录 `.env` 文件中添加：

```bash
# 搜索 Provider（二选一即可）
SERPAPI_API_KEY=your_serpapi_key_here
# 或
BING_SEARCH_API_KEY=your_bing_key_here

# 图片生成 Provider
OPENAI_API_KEY=sk-your-openai-key-here
```

### 获取 Key

- **SerpAPI**: https://serpapi.com — 注册后免费 100 次/月
- **Bing Search**: https://portal.azure.com → Cognitive Services → Bing Search v7
- **OpenAI**: https://platform.openai.com/api-keys — 需有 DALL-E 权限

## 运行

```bash
# 确保后端已启动
cd /e/AI-company-os
uvicorn backend.app:app --reload --port 8000

# 另一个终端运行验收
python scripts/verify_real_providers.py

# 指定端口
python scripts/verify_real_providers.py --port 8001

# 仅输出 JSON（适合 CI）
python scripts/verify_real_providers.py --json

# 自定义超时
python scripts/verify_real_providers.py --timeout 60
```

## 输出示例

### 无 API Key（全部 skipped）

```
  ═══ Phase 5.4 — 真实 Provider E2E 验收 ═══

  ✓ PASS  providers_health
        健康检查端点正常
  – SKIP  research_real_sources
        无 SERPAPI_API_KEY / BING_SEARCH_API_KEY，跳过真实搜索验证
  – SKIP  image_generation
        无 OPENAI_API_KEY，跳过图片生成验证

  ── 汇总 ──
  PASS: 1  FAIL: 0  SKIP: 2  Total: 3

  [OK] 所有检查通过
```

### 有 API Key（真实验证）

```
  ═══ Phase 5.4 — 真实 Provider E2E 验收 ═══

  ✓ PASS  providers_health
        健康检查端点正常
  ✓ PASS  research_real_sources  (2.31s)
        provider=serpapi，返回 3 条真实来源
        → https://www.example-report.com/earring-trends
        → https://market-analysis.com/handmade-2025
  ✓ PASS  image_generation  (8.42s)
        返回 1 张真实图片
        → https://oaidalleapiprodscus.blob.core.windows.net/...

  ── 汇总 ──
  PASS: 3  FAIL: 0  SKIP: 0  Total: 3

  [OK] 所有检查通过
```

## 退出码

| 退出码 | 含义 |
|--------|------|
| 0 | 所有检查通过（含 skipped） |
| 1 | 至少一项检查失败 |

## 设计原则

- **无 key 不失败** — skipped 算通过，不影响 CI
- **不改业务 API** — 脚本只调用现有端点，不修改任何后端代码
- **安全** — 不打印 API Key，不写入日志
- **可扩展** — 新增 provider 只需添加新的 check 函数
