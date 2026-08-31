"""Provider verification cache persisted across runtime restarts.

Verification is considered valid only when runtime credentials/config for the
provider remain unchanged since the last successful verification.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any, Dict

from backend.runtime_paths import USER_DATA_DIR

_PROVIDER_FIELDS = {
    "deepseek": {
        "api_key_env": "DEEPSEEK_API_KEY",
        "base_url_env": "DEEPSEEK_BASE_URL",
        "model_env": "DEEPSEEK_MODEL",
    },
    "openai": {
        "api_key_env": "OPENAI_API_KEY",
        "base_url_env": "OPENAI_BASE_URL",
        "model_env": "OPENAI_MODEL",
    },
    "claude": {
        "api_key_env": "CLAUDE_API_KEY",
        "alt_api_key_env": "ANTHROPIC_API_KEY",
        "base_url_env": "CLAUDE_BASE_URL",
        "model_env": "CLAUDE_MODEL",
    },
}

_VERIFICATION_FILE = USER_DATA_DIR / "provider_verification.json"


def _safe_id(provider: str) -> str:
    return str(provider).strip().lower()


def _provider_fields(provider: str) -> Dict[str, str]:
    normalized = _safe_id(provider)
    fields = _PROVIDER_FIELDS.get(normalized)
    if not fields:
        raise ValueError(f"Unsupported provider: {provider}")
    return fields


def _read_state() -> Dict[str, Dict[str, Any]]:
    if not _VERIFICATION_FILE.exists():
        return {}
    try:
        raw = _VERIFICATION_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
        if isinstance(data, dict):
            return {k: v for k, v in data.items() if isinstance(v, dict)}
    except Exception:
        pass
    return {}


def _write_state(state: Dict[str, Dict[str, Any]]) -> None:
    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    data = json.dumps(state, ensure_ascii=False, indent=2, sort_keys=True)
    tmp = _VERIFICATION_FILE.with_suffix(".json.tmp")
    tmp.write_text(data, encoding="utf-8")
    tmp.replace(_VERIFICATION_FILE)


def _env_value(env_name: str) -> str:
    return os.getenv(env_name, "") or ""


def _api_key_hash(provider: str) -> str:
    fields = _provider_fields(provider)
    key = _env_value(fields["api_key_env"]) or _env_value(fields.get("alt_api_key_env", ""))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def _has_api_key(provider: str) -> bool:
    fields = _provider_fields(provider)
    return bool(_env_value(fields["api_key_env"]) or _env_value(fields.get("alt_api_key_env", "")))


def provider_signature(provider: str) -> str:
    fields = _provider_fields(provider)
    payload = {
        "provider": _safe_id(provider),
        "api_key_hash": _api_key_hash(provider),
        "base_url": _env_value(fields["base_url_env"]),
        "model": _env_value(fields["model_env"]),
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def get_provider_verification(provider: str) -> Dict[str, Any]:
    normalized = _safe_id(provider)
    fields = _provider_fields(normalized)
    state = _read_state()
    signature = provider_signature(normalized)
    raw = state.get(normalized) or {}
    cached_verified = bool(raw.get("verified"))
    cached_signature = raw.get("signature", "")

    verified = bool(cached_verified and cached_signature == signature)

    if cached_signature and cached_signature != signature:
        state[normalized] = {
            **raw,
            "verified": False,
            "signature": signature,
            "updated_at": raw.get("updated_at", time.time()),
            "message": "配置变更后验证失效",
            "provider": normalized,
        }
        _write_state(state)

    return {
        "provider": normalized,
        "configured": _has_api_key(normalized),
        "signature": signature,
        "verified": verified,
        "message": raw.get("message", "") if not verified else raw.get("message", "").replace("配置变更后验证失效", "") or "已通过测试",
        "checked_at": raw.get("checked_at", 0.0),
    }


def set_provider_verification(provider: str, *, verified: bool, message: str = "") -> Dict[str, Any]:
    normalized = _safe_id(provider)
    _provider_fields(normalized)
    state = _read_state()

    entry = {
        "provider": normalized,
        "verified": bool(verified),
        "signature": provider_signature(normalized),
        "checked_at": time.time(),
        "message": message or ("已通过测试" if verified else "未通过测试"),
    }

    state[normalized] = entry
    _write_state(state)
    return entry


def invalidate_provider(provider: str, reason: str = "配置变更") -> Dict[str, Any]:
    normalized = _safe_id(provider)
    _provider_fields(normalized)
    existing = get_provider_verification(normalized)
    return set_provider_verification(
        normalized,
        verified=False,
        message=reason,
    )


def ensure_provider_record_matches_config(provider: str) -> Dict[str, Any]:
    """Refresh stored verification state when provider config signature changes."""
    normalized = _safe_id(provider)
    _provider_fields(normalized)
    state = _read_state()
    current_signature = provider_signature(normalized)
    raw = state.get(normalized) or {}
    if raw.get("signature") == current_signature:
        return get_provider_verification(normalized)

    entry = {
        **raw,
        "provider": normalized,
        "verified": False,
        "signature": current_signature,
        "checked_at": time.time(),
        "message": "配置变更后验证失效",
    }
    state[normalized] = entry
    _write_state(state)
    return {
        "provider": normalized,
        "configured": _has_api_key(normalized),
        "signature": current_signature,
        "verified": False,
        "message": entry.get("message", ""),
        "checked_at": entry.get("checked_at", 0.0),
    }


def normalize_provider_list() -> list[str]:
    return list(_PROVIDER_FIELDS.keys())
