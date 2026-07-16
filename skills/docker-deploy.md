---
title: Docker 部署
description: 使用 Docker/Docker Compose 容器化部署应用，含 Dockerfile 编写、多阶段构建、健康检查
category: devops
capabilities: [docker, deployment, container, devops, ci_cd]
triggers: [Docker, 部署, 容器, container, docker-compose, 上线, 发布, k8s]
---

# Docker 部署指南

## 标准 Dockerfile

```dockerfile
FROM python:3.12-slim

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000
CMD ["uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
```

## Docker Compose 模板

```yaml
services:
  app:
    build: .
    ports:
      - "8000:8000"
    env_file:
      - .env
    volumes:
      - ./logs:/app/logs
      - ./data:/app/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 3s
      retries: 3
```

## 常用命令

```bash
# 构建并启动
docker compose up -d --build

# 查看日志
docker compose logs -f --tail=100

# 进入容器
docker compose exec app bash

# 停止并清理
docker compose down -v

# 查看资源使用
docker stats
```

## 最佳实践
- 使用 `.dockerignore` 排除 `.venv/`, `__pycache__/`, `.git/`
- 多阶段构建减小镜像体积
- 敏感信息通过环境变量传入，不要写入镜像
- 健康检查覆盖关键端点
- 配置日志驱动避免磁盘写满
- 非 root 用户运行（安全性）
