"""Canonical runtime capability contract."""
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class ResourceType(StrEnum):
    AGENT = "agent"
    LLM_PROVIDER = "llm_provider"
    LOCAL_TOOL = "local_tool"
    BROWSER = "browser"
    LOCAL_SERVICE = "local_service"


class AuthorizationState(StrEnum):
    NOT_REQUIRED = "not_required"
    REQUIRED = "required"
    APPROVED = "approved"
    DENIED = "denied"


class CapabilityResource(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    resource_id: str
    resource_type: ResourceType
    display_name: str
    provider_type: str = ""
    discovered: bool = False
    available: bool = False
    configured: bool = False
    verified: bool = False
    execution_unavailable: bool = False
    requires_configuration: bool = False
    requires_verification: bool = False
    requires_adapter: bool = False
    requires_llm: bool = False
    bound_provider_id: str | None = None
    dependency_readiness_reasons: list[str] = Field(default_factory=list)
    adapter_id: str | None = None
    authorization: AuthorizationState = AuthorizationState.NOT_REQUIRED
    last_scanned_at: str = ""
    machine_id: str = ""
    source: str = ""
    metadata: dict[str, Any] = Field(default_factory=dict)

    @property
    def readiness_reasons(self) -> list[str]:
        reasons: list[str] = []
        if not self.discovered or not self.available:
            reasons.append("resource_unavailable")
        if self.requires_configuration and not self.configured:
            reasons.append("not_configured")
        if self.requires_verification and not self.verified:
            reasons.append("not_verified")
        if self.authorization == AuthorizationState.REQUIRED:
            reasons.append("approval_required")
        elif self.authorization == AuthorizationState.DENIED:
            reasons.append("approval_denied")
        if self.requires_adapter and not self.adapter_id:
            reasons.append("execution_unavailable")
        if self.execution_unavailable:
            reasons.append("execution_unavailable")
        reasons.extend(self.dependency_readiness_reasons)
        return list(dict.fromkeys(reasons))

    def with_provider_dependency(self, provider: "CapabilityResource | None") -> "CapabilityResource":
        """Return this resource with its bound provider readiness folded in."""
        if not self.requires_llm:
            return self
        if provider is None:
            return self.model_copy(update={"dependency_readiness_reasons": ["llm_provider_missing"]})
        reasons = list(self.readiness_reasons)
        if not provider.ready:
            if not provider.configured and provider.requires_configuration:
                reason = "llm_provider_not_configured"
            elif not provider.verified and provider.requires_verification:
                reason = "llm_provider_not_verified"
            else:
                reason = "llm_provider_not_ready"
            reasons.append(reason)
        return self.model_copy(update={"dependency_readiness_reasons": reasons if not provider.ready else []})

    @property
    def ready(self) -> bool:
        return not self.readiness_reasons

    def safe_dict(self) -> dict[str, Any]:
        def redact(value: Any, key: str = "") -> Any:
            sensitive = ("key", "token", "secret", "password", "authorization", "cookie", "credential")
            lowered = key.lower()
            if any(part in lowered for part in sensitive):
                if lowered == "authorization" and isinstance(value, str) and value in {s.value for s in AuthorizationState}:
                    return value
                return "[REDACTED]"
            if isinstance(value, dict):
                return {str(k): redact(v, str(k)) for k, v in value.items()}
            if isinstance(value, list):
                return [redact(v, key) for v in value]
            return value

        result = redact(self.model_dump(mode="json"))
        result["ready"] = self.ready
        result["readiness_reasons"] = self.readiness_reasons
        result["readiness_reasons"] = self.readiness_reasons
        result["ready"] = not result["readiness_reasons"]
        return result
