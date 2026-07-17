"""
Cloud API — AI Company OS 云端服务

提供：
1. 用户认证和激活
2. 额度管理
3. 多 Agent 流水线执行
4. 联网搜索
5. QA 审核
"""
import os
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

from services.auth_service import AuthService
from services.usage_service import UsageService
from services.agent_runtime import AgentRuntime
from services.model_client import ModelClient
from services.search_service import SearchService
from services.qa_service import QAService

# 初始化服务
app = FastAPI(
    title="AI Company OS Cloud API",
    description="云端 Agent 协作服务",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 服务实例
auth_service = AuthService()
usage_service = UsageService()
model_client = ModelClient()
search_service = SearchService()
qa_service = QAService()
agent_runtime = AgentRuntime(model_client, search_service, qa_service)


# ── 依赖注入 ──────────────────────────────────────────────

async def get_current_user(authorization: Optional[str] = Header(None)):
    """从 Header 中获取当前用户"""
    if not authorization:
        raise HTTPException(status_code=401, detail="未提供认证信息")

    token = authorization.replace("Bearer ", "")
    user = auth_service.validate_token(token)

    if not user:
        raise HTTPException(status_code=401, detail="无效的 token")

    return user


# ── 请求/响应模型 ──────────────────────────────────────────

class ActivateRequest(BaseModel):
    """激活码请求"""
    activation_code: str


class PipelineRequest(BaseModel):
    """流水线执行请求"""
    message: str
    context: Optional[dict] = None


class PipelineResponse(BaseModel):
    """流水线执行响应"""
    ok: bool
    mode: str = "cloud"
    task_id: str
    task_type: str
    final_answer: str = ""
    deliverables: dict = {}
    used_agents: List[str] = []
    agent_trace: List[dict] = []
    used_web_search: bool = False
    sources: List[dict] = []
    qa: dict = {}
    confidence: float = 0.0
    usage: dict = {}
    warnings: List[str] = []


# ── 健康检查 ──────────────────────────────────────────────

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "ok",
        "service": "AI Company OS Cloud API",
        "version": "1.0.0",
        "timestamp": datetime.now().isoformat()
    }


# ── 认证接口 ──────────────────────────────────────────────

@app.post("/auth/activate")
async def activate(request: ActivateRequest):
    """使用激活码激活"""
    result = auth_service.activate(request.activation_code)

    if not result["ok"]:
        raise HTTPException(status_code=400, detail=result["error"])

    return result


# ── 使用量查询 ──────────────────────────────────────────────

@app.get("/usage")
async def get_usage(user=Depends(get_current_user)):
    """获取当前用户使用量"""
    return usage_service.get_usage(user["user_id"])


# ── 流水线执行 ──────────────────────────────────────────────

@app.post("/pipeline/execute", response_model=PipelineResponse)
async def execute_pipeline(request: PipelineRequest, user=Depends(get_current_user)):
    """执行多 Agent 流水线"""

    # 检查额度
    usage = usage_service.get_usage(user["user_id"])
    if usage["remaining"] <= 0:
        raise HTTPException(status_code=403, detail="额度已用完，请升级套餐")

    # 执行流水线
    result = agent_runtime.execute(
        message=request.message,
        context=request.context or {},
        user_id=user["user_id"]
    )

    # 扣除额度
    usage_service.use_quota(user["user_id"])

    # 添加使用量信息
    result["usage"] = usage_service.get_usage(user["user_id"])

    return result


# ── 启动 ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
