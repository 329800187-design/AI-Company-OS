# ============================================
# AI Company OS — Docker 镜像 v0.5.0
# ============================================
FROM python:3.12

LABEL org.opencontainers.image.title="AI Company OS"
LABEL org.opencontainers.image.description="AI-powered multi-agent collaboration system"
LABEL org.opencontainers.image.version="0.5.0"

WORKDIR /app

# 安装系统依赖 + Chromium（Playwright 用完整 python 镜像确保 --with-deps 成功）
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 安装 Playwright + Chromium（完整 python 镜像有足够系统库）
RUN playwright install --with-deps chromium

# 复制应用代码
COPY . .

# 创建非 root 用户
RUN useradd --create-home --shell /bin/bash appuser && chown -R appuser:appuser /app
USER appuser

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
  CMD curl -f http://localhost:8000/health || exit 1

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "backend.app:app", "--host", "0.0.0.0", "--port", "8000"]
