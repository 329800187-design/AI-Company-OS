"""
OAuth2 authentication — GitHub + Google

Config env vars:
  GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET
  GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET
  OAUTH_REDIRECT_BASE=http://localhost:8000
"""
import json, os, secrets, urllib.request, urllib.parse
from typing import Dict, Optional
from backend.auth.user_system import get_user_manager

REDIRECT_BASE = os.getenv("OAUTH_REDIRECT_BASE", "http://localhost:8000")

# ── GitHub ──────────────────────────────────────────

def get_github_auth_url() -> str:
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    if not client_id: return ""
    state = secrets.token_hex(16)
    return f"https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={REDIRECT_BASE}/auth/oauth/github/callback&scope=user:email&state={state}"

def handle_github_callback(code: str, state: str = "") -> Optional[Dict]:
    client_id = os.getenv("GITHUB_CLIENT_ID", "")
    client_secret = os.getenv("GITHUB_CLIENT_SECRET", "")
    if not client_id or not client_secret: return None

    # Exchange code for access token
    token_url = "https://github.com/login/oauth/access_token"
    req = urllib.request.Request(token_url, data=json.dumps({
        "client_id": client_id, "client_secret": client_secret, "code": code
    }).encode(), headers={"Content-Type": "application/json", "Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        token_data = json.loads(r.read().decode())
    access_token = token_data.get("access_token", "")
    if not access_token: return None

    # Get user info
    user_req = urllib.request.Request("https://api.github.com/user",
        headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AIOS/1.2"})
    with urllib.request.urlopen(user_req, timeout=10) as r:
        user = json.loads(r.read().decode())

    # Get email (may need separate call)
    email = user.get("email", "")
    if not email:
        email_req = urllib.request.Request("https://api.github.com/user/emails",
            headers={"Authorization": f"Bearer {access_token}", "User-Agent": "AIOS/1.2"})
        with urllib.request.urlopen(email_req, timeout=10) as r:
            emails = json.loads(r.read().decode())
            primary = [e for e in emails if e.get("primary")]
            if primary: email = primary[0].get("email", "")

    username = user.get("login", f"gh_{user.get('id','')}")
    email = email or f"{username}@github.user"

    return _login_or_register(username, email, f"github_{user.get('id','')}")

# ── Google ──────────────────────────────────────────

def get_google_auth_url() -> str:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    if not client_id: return ""
    state = secrets.token_hex(16)
    params = urllib.parse.urlencode({
        "client_id": client_id, "redirect_uri": f"{REDIRECT_BASE}/auth/oauth/google/callback",
        "response_type": "code", "scope": "openid email profile", "state": state
    })
    return f"https://accounts.google.com/o/oauth2/v2/auth?{params}"

def handle_google_callback(code: str, state: str = "") -> Optional[Dict]:
    client_id = os.getenv("GOOGLE_CLIENT_ID", "")
    client_secret = os.getenv("GOOGLE_CLIENT_SECRET", "")
    if not client_id or not client_secret: return None

    # Exchange code for tokens
    token_url = "https://oauth2.googleapis.com/token"
    req = urllib.request.Request(token_url, data=urllib.parse.urlencode({
        "client_id": client_id, "client_secret": client_secret,
        "code": code, "grant_type": "authorization_code",
        "redirect_uri": f"{REDIRECT_BASE}/auth/oauth/google/callback"
    }).encode(), headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(req, timeout=10) as r:
        token_data = json.loads(r.read().decode())
    access_token = token_data.get("access_token", "")
    if not access_token: return None

    # Get user info
    user_req = urllib.request.Request("https://www.googleapis.com/oauth2/v2/userinfo",
        headers={"Authorization": f"Bearer {access_token}"})
    with urllib.request.urlopen(user_req, timeout=10) as r:
        user = json.loads(r.read().decode())

    username = user.get("name", f"g_{user.get('id','')}").replace(" ", "_").lower()
    email = user.get("email", f"{username}@google.user")
    return _login_or_register(username, email, f"google_{user.get('id','')}")

# ── Shared ──────────────────────────────────────────

def _login_or_register(username: str, email: str, oauth_id: str) -> Dict:
    mgr = get_user_manager()
    try:
        # Try register with OAuth password
        mgr.register(username, email, f"oauth_{secrets.token_hex(16)}")
    except ValueError:
        pass  # Already exists, login instead
    result = mgr.login(username, f"oauth_{secrets.token_hex(16)}")  # Won't work
    # Actually need to login via special OAuth token
    from backend.auth.user_system import UserManager
    # Direct login by finding user and creating session
    import sqlite3
    db_path = __import__('pathlib').Path(__file__).parent.parent / "database" / "company_os.db"
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    user_row = conn.execute("SELECT * FROM users WHERE username=? OR email=?", (username, email)).fetchone()
    conn.close()
    if not user_row:
        return {"ok": False, "error": "OAuth user not found"}
    user_id = user_row["user_id"]
    # Create session token
    token = f"at_{secrets.token_hex(32)}"
    from datetime import datetime, timedelta
    expires = (datetime.now() + timedelta(days=7)).isoformat()
    conn = sqlite3.connect(str(db_path))
    conn.execute("INSERT INTO sessions_tokens (token,user_id,tenant_id,expires_at) VALUES (?,?,?,?)",
                 (token, user_id, user_row["tenant_id"], expires))
    conn.execute("UPDATE users SET last_login_at=datetime('now','localtime') WHERE user_id=?", (user_id,))
    conn.commit()
    conn.close()
    return {
        "token": token, "user_id": user_id,
        "username": user_row["username"], "email": user_row["email"],
        "tenant_id": user_row["tenant_id"], "tier": user_row["tier"],
        "expires_at": expires,
    }
