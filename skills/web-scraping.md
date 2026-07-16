---
title: 网页抓取
description: 使用 Playwright/httpx 进行网页数据抓取、内容提取、动态页面处理
category: browser
capabilities: [web_scraping, data_extraction, browser_automation]
triggers: [抓取, 爬虫, scrape, 网页数据, 提取内容, 网页采集, crawler]
---

# 网页抓取指南

## 工具选择

| 场景 | 推荐工具 | 原因 |
|------|----------|------|
| 静态页面/API | httpx + BeautifulSoup | 快速、低资源 |
| 动态渲染页面 | Playwright (OpenClaw) | 支持 JS 渲染 |
| 需要登录 | Playwright | 支持 Cookie/Session |
| 大量数据 | httpx + 异步 | 并发请求 |

## 抓取流程

1. **分析目标**：打开 F12 查看网络请求，找 API 接口
2. **选择策略**：优先 API 直接请求，其次页面抓取
3. **编写代码**：处理分页、反爬、限速
4. **数据清洗**：提取结构化数据、去重、验证
5. **存储导出**：JSON/CSV/数据库

## 常用 Playwright 代码模板

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto("https://example.com")
    # 等待元素加载
    page.wait_for_selector(".content")
    # 提取文本
    text = page.inner_text("body")
    # 提取多条数据
    items = page.query_selector_all(".item")
    data = []
    for item in items:
        data.append({
            "title": item.query_selector(".title").inner_text(),
            "link": item.query_selector("a").get_attribute("href"),
        })
    browser.close()
```

## 注意事项
- 遵守 robots.txt
- 设置合理请求间隔（至少 1-3 秒）
- 使用真实的 User-Agent
- 处理好异常和重试
