---
name: 产品发布营销
description: CEO拆解 → Marketing文案 + Image图片 + QA验收的完整产品发布流程
version: "1.0"
triggers: [产品发布, 新品上市, 产品推广, 发布会]
steps:
  - id: ceo-plan
    agent: ceo_agent
    task_type: goal_decompose
    description: 拆解产品发布任务
    input:
      goal: "为 {{inputs.product_name}} 制定产品发布计划。产品描述: {{inputs.product_description}}"
    retry: 1
  - id: marketing-campaign
    agent: marketing_agent
    task_type: campaign_plan
    description: 生成完整营销活动方案
    depends_on: [ceo-plan]
    input:
      prompt: "产品名称: {{inputs.product_name}}，产品描述: {{inputs.product_description}}，发布渠道: {{inputs.channels}}"
    retry: 1
  - id: marketing-copy
    agent: marketing_agent
    task_type: copywriting
    description: 生成产品文案
    depends_on: [ceo-plan]
    input:
      prompt: "为 {{inputs.product_name}} 写产品宣传文案。特点: {{inputs.product_description}}"
    retry: 1
  - id: marketing-social
    agent: marketing_agent
    task_type: social_media
    description: 生成社媒内容
    depends_on: [ceo-plan]
    input:
      prompt: "为 {{inputs.product_name}} 生成社交媒体发布内容，平台: {{inputs.channels}}"
    retry: 1
  - id: product-image
    agent: image_agent
    task_type: image_generate
    description: 生成产品宣传图
    depends_on: [marketing-copy]
    input:
      prompt: "Product promotional image for {{inputs.product_name}}: {{steps.marketing-copy.data.headline}}"
      style: vivid
    retry: 1
    timeout: 90
  - id: qa-verify
    agent: qa_agent
    task_type: qa_review
    description: 最终验收
    depends_on: [marketing-campaign, marketing-copy, marketing-social, product-image]
    input:
      goal: "产品发布素材齐套检查：活动方案+文案+社媒+宣传图。评分 >= 70 视为通过"
outputs:
  campaign_plan: "{{steps.marketing-campaign.data}}"
  copy: "{{steps.marketing-copy.data}}"
  social_content: "{{steps.marketing-social.data}}"
  product_image: "{{steps.product-image.data}}"
  review: "{{steps.qa-verify.summary}}"
---

# 产品发布营销工作流

## 输入
- `product_name`: 产品名称
- `product_description`: 产品描述
- `channels`: 发布渠道（如 "小红书+抖音+Twitter"）

## 执行计划
1. CEO 拆解发布任务
2. Marketing 并行生成：活动方案 + 产品文案 + 社媒内容
3. Image 根据文案生成宣传图
4. QA 验收全部素材
