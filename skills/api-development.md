---
title: API 开发
description: 使用 FastAPI/Flask 开发 RESTful API，含路由设计、参数验证、错误处理、文档生成
category: development
capabilities: [api_development, fastapi, flask, restful, backend]
triggers: [API, FastAPI, Flask, 接口, endpoint, REST, 后端, 路由, swagger]
---

# API 开发规范

## FastAPI 项目结构

```
backend/
├── app.py              # FastAPI 入口
├── config.py           # 配置中心
├── routers/            # 路由模块
│   ├── user_router.py
│   └── item_router.py
├── schemas/            # Pydantic 模型
├── services/           # 业务逻辑
├── database/           # 数据库
└── middleware/         # 中间件
```

## 路由设计原则

- RESTful 风格：GET/POST/PUT/DELETE 语义正确
- 版本化：`/api/v1/users`
- 复数资源名：`/users` 不是 `/user`
- 嵌套资源：`/users/{id}/posts`
- 查询参数：过滤、排序、分页

## 代码模板

```python
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/items", tags=["物品管理"])

class ItemCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    price: float = Field(..., gt=0)
    category: Optional[str] = None

class ItemResponse(BaseModel):
    id: int
    name: str
    price: float

@router.get("/", response_model=list[ItemResponse])
def list_items(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    category: Optional[str] = None,
):
    """分页查询物品列表"""
    ...

@router.post("/", response_model=ItemResponse, status_code=201)
def create_item(item: ItemCreate):
    """创建新物品"""
    ...

@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int):
    """获取单个物品详情"""
    ...
```

## 注意事项
- 始终校验用户输入（Pydantic）
- 使用 HTTP 标准状态码
- 异常用 HTTPException 抛出
- 自动生成 OpenAPI 文档（FastAPI 内置）
