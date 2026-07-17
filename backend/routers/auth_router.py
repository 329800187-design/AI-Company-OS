"""OAuth + Auth routing — GitHub/Google login + callback"""
import os
from fastapi import APIRouter, Request, Query
from fastapi.responses import RedirectResponse, JSONResponse, HTMLResponse
from backend.auth.oauth import get_github_auth_url, handle_github_callback, get_google_auth_url, handle_google_callback

router = APIRouter(prefix="/auth", tags=["Auth / 认证"], include_in_schema=False)

OAUTH_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8"><title>OAuth Login</title>
<style>body{font-family:system-ui;display:flex;align-items:center;justify-content:center;min-height:100vh;background:#0a0a0a;color:#fff}
.card{background:#111;padding:40px;border-radius:12px;text-align:center;max-width:320px}
.btn{display:block;width:100%;padding:12px;margin:8px 0;border:none;border-radius:8px;font-size:14px;cursor:pointer;text-decoration:none;color:#fff}
.btn-gh{background:#24292e} .btn-google{background:#4285f4} p{color:#888;font-size:12px}</style></head>
<body><div class="card"><h2>🔐 AIOS Login</h2><p>Choose a login method</p>"""

def _oauth_page(gh_url: str, google_url: str) -> str:
    html = OAUTH_HTML
    if gh_url:
        html += f'<a href="{gh_url}" class="btn btn-gh">🐙 GitHub Login</a>'
    if google_url:
        html += f'<a href="{google_url}" class="btn btn-google">🔵 Google Login</a>'
    if not gh_url and not google_url:
        html += '<p style="color:#f55">No OAuth providers configured.<br>Set GITHUB_CLIENT_ID or GOOGLE_CLIENT_ID in .env</p>'
    html += '</div></body></html>'
    return html


@router.get("/oauth/login")
def oauth_login():
    return HTMLResponse(
        _oauth_page(get_github_auth_url(), get_google_auth_url()))

@router.get("/oauth/github/callback")
def github_callback(code: str = Query(...), state: str = Query("")):
    result = handle_github_callback(code, state)
    if not result:
        return JSONResponse({"ok": False, "error": "GitHub OAuth failed"}, status_code=400)
    return {"ok": True, "token": result["token"], "user": result["username"]}

@router.get("/oauth/google/callback")
def google_callback(code: str = Query(...), state: str = Query("")):
    result = handle_google_callback(code, state)
    if not result:
        return JSONResponse({"ok": False, "error": "Google OAuth failed"}, status_code=400)
    return {"ok": True, "token": result["token"], "user": result["username"]}

@router.get("/login")
def auth_login_page():
    return HTMLResponse(
        _oauth_page(get_github_auth_url(), get_google_auth_url()))
