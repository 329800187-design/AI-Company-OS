---
title: AI 图片生成
description: 使用 DALL-E 3 / Midjourney / Stable Diffusion 生成高质量图片，掌握提示词工程
category: creative
capabilities: [image_generation, prompt_engineering, dalle]
triggers: [图片生成, 生成图片, 文生图, DALL-E, 画一张, 画一个, image generate, generate image]
---

# AI 图片生成指南

## 提示词工程（Prompt Engineering）

### 核心公式
```
[主体] + [风格] + [构图] + [光线] + [色彩] + [氛围]
```

### 示例
```
A cute orange tabby cat, digital illustration style,
sitting on a windowsill, golden hour sunlight,
warm orange and cream tones, cozy peaceful mood
```

## 常用风格关键词

| 风格 | 关键词 |
|------|--------|
| 摄影写实 | photorealistic, 8K, detailed, natural lighting, Canon EOS |
| 3D 渲染 | 3D render, octane render, ray tracing, studio lighting |
| 插画 | digital illustration, concept art, trending on artstation |
| 动漫 | anime style, manga, studio ghibli inspired |
| 极简 | minimalist, clean, simple, white background |
| 油画 | oil painting, textured, classical, masterwork |

## 负面提示词
```
blurry, low quality, distorted, watermark, text, signature,
bad anatomy, extra limbs, disfigured, ugly, pixelated
```

## DALL-E 3 参数

- size: 1024x1024, 1792x1024 (横版), 1024x1792 (竖版)
- style: vivid (生动) / natural (自然)
- quality: standard / hd
- n: 1 (DALL-E 3 每次一张)
