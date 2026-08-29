from backend.ai_registry.contracts import (
    AuthorizationState,
    CapabilityResource,
    ResourceType,
)


def test_ready_requires_all_execution_prerequisites():
    resource = CapabilityResource(
        resource_id="openclaw",
        resource_type=ResourceType.AGENT,
        display_name="OpenClaw",
        discovered=True,
        available=True,
        configured=True,
        verified=True,
        adapter_id="openclaw_gateway_adapter",
        authorization=AuthorizationState.NOT_REQUIRED,
    )
    assert resource.ready is True
    assert resource.readiness_reasons == []


def test_available_resource_without_adapter_is_not_ready():
    resource = CapabilityResource(
        resource_id="openclaw",
        resource_type=ResourceType.AGENT,
        display_name="OpenClaw",
        discovered=True,
        available=True,
        configured=True,
        verified=True,
    )
    assert resource.ready is False
    assert "execution_unavailable" in resource.readiness_reasons


def test_unconfigured_agent_exposes_reason():
    resource = CapabilityResource(
        resource_id="research",
        resource_type=ResourceType.AGENT,
        display_name="Research",
        discovered=True,
        available=True,
        requires_configuration=True,
        adapter_id="project_agent_adapter",
    )
    assert resource.ready is False
    assert "not_configured" in resource.readiness_reasons


def test_provider_is_not_an_agent():
    resource = CapabilityResource(
        resource_id="deepseek",
        resource_type=ResourceType.LLM_PROVIDER,
        display_name="DeepSeek",
        discovered=True,
        available=True,
        configured=True,
        verified=False,
        requires_verification=True,
    )
    assert resource.ready is False
    assert resource.resource_type == ResourceType.LLM_PROVIDER


def test_safe_dict_redacts_credential_like_values():
    resource = CapabilityResource(
        resource_id="provider",
        resource_type=ResourceType.LLM_PROVIDER,
        display_name="Provider",
        metadata={"authorization": "Bearer secret", "api_key": "secret"},
    )
    assert "secret" not in str(resource.safe_dict())
