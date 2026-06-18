"""
Lightweight RBAC — roles, permissions, resource scoping.

Roles: admin, operator, user, viewer
Permissions: agent_run, config_write, user_manage, system_manage, read_only
"""
from typing import Dict, List, Optional, Set

ROLES: Dict[str, Dict] = {
    "admin": {
        "permissions": {"agent_run", "config_write", "user_manage", "system_manage", "read_only"},
        "max_sessions_per_day": 999,
        "max_tokens_per_month": 10_000_000,
    },
    "operator": {
        "permissions": {"agent_run", "config_write", "read_only"},
        "max_sessions_per_day": 200,
        "max_tokens_per_month": 1_000_000,
    },
    "user": {
        "permissions": {"agent_run", "read_only"},
        "max_sessions_per_day": 50,
        "max_tokens_per_month": 200_000,
    },
    "viewer": {
        "permissions": {"read_only"},
        "max_sessions_per_day": 0,
        "max_tokens_per_month": 0,
    },
}


def has_permission(user_info: dict, permission: str) -> bool:
    """Check if user has a specific permission"""
    if not user_info:
        return False
    role = user_info.get("role", user_info.get("tier", "user"))
    perms = ROLES.get(role, ROLES["viewer"]).get("permissions", set())
    return permission in perms


def require_permission(user_info: dict, permission: str):
    """Raise PermissionError if user lacks permission"""
    if not has_permission(user_info, permission):
        raise PermissionError(f"需要 {permission} 权限，当前角色: {user_info.get('role', '?')}")


def get_role_limits(user_info: dict) -> dict:
    role = user_info.get("role", user_info.get("tier", "user")) if user_info else "viewer"
    return ROLES.get(role, ROLES["viewer"])
