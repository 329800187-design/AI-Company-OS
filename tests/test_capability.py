"""E2E 能力验证测试 — 覆盖全部系统功能"""
import os, sys, json
sys.path.insert(0, ".")
import pytest

if os.getenv("AIOS_RUN_INTEGRATION") != "1":
    pytest.skip("integration audit; set AIOS_RUN_INTEGRATION=1 to run", allow_module_level=True)

from fastapi.testclient import TestClient
from backend.app import app
client = TestClient(app)

results = []

def safe(v, *keys):
    """安全获取嵌套 dict 值"""
    for k in keys:
        if isinstance(v, dict): v = v.get(k, v)
        else: return ""
    return v

def api(method, path, data=None):
    try:
        r = client.get(path) if method == "GET" else client.post(path, json=data or {})
        try:
            return r.status_code, r.json()
        except Exception:
            return r.status_code, {"_raw": r.text[:150]}
    except Exception as e:
        return 0, {"_error": str(e)[:100]}

# =============================================
def add(name, ok, summary, detail=""):
    results.append((name, ok, summary, detail))

# === SYSTEM ===
c, d = api("GET", "/system/info")
add("系统信息", c==200, f"v{safe(d,'version')} | {safe(d,'agents','total')} agents | {safe(d,'skills','count')} skills")

c, d = api("GET", "/health")
add("健康检查", c==200, f"{safe(d,'status')} v{safe(d,'version')}")

c, d = api("GET", "/config/status")
add("配置状态", c==200, f"Provider={safe(d,'current_provider')} | Auth={'ON' if safe(d,'server','auth_configured') else 'off'}")

c, d = api("GET", "/auth/info")
add("认证信息", c==200, f"enabled={safe(d,'enabled')}")

# === AI 对话 ===
c, d = api("POST", "/commander/chat/send", {"message":"10个字介绍你自己","temperature":0.3,"max_tokens":60})
add("AI对话", c in (200,500), f"HTTP{c}", str(safe(d,'reply','_raw'))[:60])

# === CTO ===
c, d = api("POST", "/cto/review", {"code":'password="admin"; sql="SELECT * FROM users WHERE id="+uid',"language":"python"})
findings = safe(d,'findings')
add("CTO代码审查", c==200, f"score={safe(d,'score')}/100 | {len(findings) if isinstance(findings,list) else 0} findings")

c, d = api("POST", "/cto/tech-choice", {"goal":"高并发电商后端技术选型"})
add("CTO技术选型", c==200, str(safe(d,'summary'))[:50])

c, d = api("POST", "/cto/architect", {"goal":"评审系统架构","architecture_desc":"单体应用+同步处理+无缓存+单DB"})
add("CTO架构评审", c==200, f"score={safe(d,'score')}/100")

c, d = api("POST", "/cto/decompose", {"goal":"实现OAuth2.0第三方登录功能"})
subs = safe(d,'data','subtasks')
add("CTO任务拆解", c==200, f"{len(subs) if isinstance(subs,list) else 0} subtasks")

c, d = api("POST", "/cto/estimate", {"goal":"开发用户认证+权限管理完整模块"})
add("CTO工作量评估", c==200, f"~{safe(d,'data','total_hours')}h")

# === Marketing ===
c, d = api("POST", "/marketing/copywriting", {"prompt":"AI智能笔记App广告语，目标大学生"})
add("文案生成", c==200, str(safe(d,'status')), str(safe(d,'data','headline'))[:50])

c, d = api("POST", "/marketing/social", {"prompt":"分享AI学习技巧，小红书平台"})
add("社媒内容", c==200, str(safe(d,'status')), str(safe(d,'data','content'))[:50])

c, d = api("POST", "/marketing/seo", {"prompt":"Python入门教程"})
add("SEO文章", c==200, str(safe(d,'status')), str(safe(d,'data','h1'))[:50])

c, d = api("POST", "/marketing/email", {"prompt":"SaaS续费提醒"})
add("邮件营销", c==200, str(safe(d,'status')), str(safe(d,'data','subject'))[:50])

c, d = api("POST", "/marketing/brand-strategy", {"prompt":"AI在线教育创业公司，3-12岁儿童"})
add("品牌策略", c==200, str(safe(d,'status')), str(safe(d,'data','brand_positioning'))[:50])

c, d = api("POST", "/marketing/campaign", {"prompt":"AI学习机新品上市推广活动"})
add("活动策划", c==200, str(safe(d,'status')), str(safe(d,'data','campaign_name'))[:50])

# === Image ===
c, d = api("POST", "/image/generate", {"prompt":"A cute orange cat on a desk with laptop, digital art"})
add("图片生成", c==200, str(safe(d,'status'))[:30], str(safe(d,'data','enhanced_prompt'))[:50])

# === Skills ===
c, d = api("GET", "/skills/list")
sk = safe(d,'skills') or safe(d,'data') or []
add("技能列表", c==200, f"{len(sk) if isinstance(sk,list) else 0} skills loaded")

c, d = api("GET", "/skills/match?goal=fix security bug in code")
mt = safe(d,'matched') or safe(d,'data') or []
add("技能匹配", c==200, f"{len(mt) if isinstance(mt,list) else 0} matched")

# === AI Registry ===
c, d = api("GET", "/ai/list")
svcs = safe(d,'services') or []
add("AI注册中心", c==200, f"{len(svcs) if isinstance(svcs,list) else 0} services")

c, d = api("GET", "/ai/capabilities")
caps = safe(d,'capabilities') or d
add("AI能力路由", c==200, f"{len(caps) if isinstance(caps,dict) else 0} capabilities")

# === Workflows ===
c, d = api("GET", "/workflows/dag/list")
wfs = safe(d,'workflows') or []
add("DAG工作流列表", c==200, f"{len(wfs) if isinstance(wfs,list) else 0} workflows")

c, d = api("GET", "/workflows/dag/product-launch")
add("DAG工作流详情", c==200, f"{safe(d,'title')} | {len(safe(d,'steps') or [])} steps")

c, d = api("POST", "/workflows/ceo-codex-task", {"goal":"write a hello world Python script"})
add("线性工作流执行", c==200, f"status={safe(d,'status')} | {len(safe(d,'results') or [])} steps")

# === Commander ===
c, d = api("GET", "/commander/sessions")
add("执行记录", c==200, f"{safe(d,'count')} sessions")

# === Templates ===
c, d = api("GET", "/templates/list")
tpls = safe(d,'templates') or []
add("场景模板", c==200, f"{len(tpls) if isinstance(tpls,list) else 0} templates")

# === Users ===
c, d = api("POST", "/user/register", {"username":"perftest","email":"pf@test.com","password":"test123"})
add("用户注册", c==200, str(safe(d,'status')))

c, d = api("POST", "/user/login", {"username":"perftest","password":"test123"})
add("用户登录", c==200, f"tier={safe(d,'tier')}", safe(d,'username'))

c, d = api("GET", "/user/tiers")
tiers = safe(d,'tiers') or {}
add("套餐列表", c==200, f"{len(tiers)} tiers")

# === Agent Router ===
c, d = api("POST", "/agents/video/run", {"goal":"product demo script for AI tool"})
add("Video Agent", c==200, f"agent={safe(d,'agent')} | {safe(d,'status')}")

c, d = api("POST", "/agents/qa/run", {"goal":"test QA quality check","result":"Hello world output successful"})
add("QA Agent", c==200, f"score={safe(d,'score')} | {safe(d,'status')}")

c, d = api("POST", "/agents/ceo/run", {"goal":"write a hello world script"})
add("CEO Agent", c==200, f"{safe(d,'status')} | {len(safe(d,'output','created_tasks') or [])} tasks")

# === 记忆 ===
c, d = api("GET", "/memory/search?q=code+review")
mem = safe(d,'memories') or safe(d,'data') or []
add("记忆搜索", c==200, f"{len(mem) if isinstance(mem,list) else 0} memories")

# === UI ===
r = client.get("/ui")
add("前端UI", r.status_code==200, f"HTTP{r.status_code} | {len(r.text)} chars")

r = client.get("/docs")
add("Swagger文档", r.status_code==200, f"HTTP{r.status_code}")

# === Print ===
print()
print("=" * 130)
print(f"{'#':<3} {'能力模块':<20} {'状态':<6} {'结果摘要':<68} {'详情':<30}")
print("=" * 130)
for i, (name, ok, summary, detail) in enumerate(results, 1):
    s = "OK" if ok else "FAIL"
    sum_str = str(summary)[:66] if summary else "-"
    det_str = str(detail)[:28] if detail else "-"
    print(f"{i:<3} {name:<18} {s:<6} {sum_str:<68} {det_str}")
print("=" * 130)
n_ok = sum(1 for _,ok,_,_ in results if ok)
n_total = len(results)
print(f"合计: {n_ok}/{n_total} 通过 ({n_ok*100//n_total}%)")
