---
name: 图片营销活动
description: Marketing Agent 生成文案 → Image Agent 生成配图 → QA 验收
version: "1.0"
triggers: [图片营销, 宣传图, 海报, 广告图]
steps:
  - id: marketing-copy
    agent: marketing_agent
    task_type: copywriting
    description: 生成产品营销文案
    input:
      prompt: "{{inputs.product_description}}"
    retry: 1
  - id: generate-image
    agent: image_agent
    task_type: image_generate
    description: 根据文案生成宣传图片
    depends_on: [marketing-copy]
    input:
      prompt: "{{steps.marketing-copy.data.headline}} - {{steps.marketing-copy.data.body}}"
      style: "{{inputs.image_style}}"
    retry: 1
    timeout: 90
  - id: qa-check
    agent: qa_agent
    task_type: qa_review
    description: 验收文案和图片质量
    depends_on: [marketing-copy, generate-image]
    condition: "steps.generate-image.status != 'failed'"
    input:
      goal: "验证营销文案和配图是否匹配、质量是否达到发布标准"
      expected_output:
        type: marketing_assets
        description: 文案+图片+综合评分 >= 70
outputs:
  copy_result: "{{steps.marketing-copy.data}}"
  image_result: "{{steps.generate-image.data}}"
  final_verdict: "{{steps.qa-check.summary}}"
---

# 图片营销活动工作流

## 输入
- `product_description`: 产品描述
- `image_style`: 图片风格偏好（默认 vivid）

## 流程
1. Marketing Agent 将产品描述转化为营销文案
2. Image Agent 根据文案关键词生成宣传图
3. QA Agent 验收文案×图片一致性和发布质量

## 适用场景
- 新品上市宣传图+文案
- 社交媒体广告素材
- 电商主图+详情页文案
