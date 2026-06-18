---
title: 浏览器自动化
description: 使用 Playwright 控制浏览器：截图、抓取内容、填写表单、页面测试
category: agent
capabilities:
  - browser_screenshot
  - browser_scrape
  - browser_form_fill
  - browser_test
triggers:
  - 浏览器
  - 网页
  - 截图
  - 抓取
  - 爬虫
  - URL
  - http
  - 网址
  - 百度
  - 谷歌
  - 搜索
---

# 浏览器自动化 Agent (OpenClaw)

## 能力
- 网页截图（全页或可视区域）
- 内容抓取（文本、链接、HTML）
- 表单填写和提交
- 页面功能测试

## 最佳实践
1. 提供完整 URL（含 https://）
2. 抓取时指定提取类型（text/links/html）
3. 可用 CSS 选择器精确提取
4. 超时默认 30s，复杂页面适当延长
