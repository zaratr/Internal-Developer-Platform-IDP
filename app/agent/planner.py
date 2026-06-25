"""Intent → provisioning plan.

The planner turns a natural-language request like

    "I need a redis cache for the permit service in staging"

into a validated :class:`ProvisioningPlan` that the IDP API can
execute directly: a ``ServiceCreate`` plus one
``EnvironmentProvisionRequest``. The plan is validated against the
same pydantic schemas the API uses and run through the
``GuardrailEngine`` so the agent cannot bypass policy.

Two backends:

* ``llm``  — default; asks a local Ollama model for a JSON plan.
* ``fallback`` — deterministic keyword-based planner used when no
  model is reachable (or when ``allow_fallback`` is explicitly
  requested). Keeps the CLI/tests usable without a GPU.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, Optional, Tuple

from pydantic import ValidationError

from fastapi import HTTPException

from app.agent.ollama_client import OllamaUnavailable, generate_json
from app.core.config import get_settings
from app.models.models import EnvironmentTier
from app.platform.guardrails import GuardrailEngine
from app.schemas.domain import (
    EnvironmentProvisionRequest,
    ServiceCreate,
)

# Resource keywords the fallback planner recognises. Kept intentionally
# small — this is a safety net, not the primary path.
_FALLBACK_RESOURCES = {
    "redis": ("redis-cache", "Managed Redis cache for session and hot-path data"),
    "postgres": ("postgres-db", "Managed PostgreSQL database for service state"),
    "postgresql": ("postgres-db", "Managed PostgreSQL database for service state"),
    "queue": ("message-queue", "Managed message queue for decoupled processing"),
    "servicebus": ("message-queue", "Managed message queue for decoupled processing"),
    "bucket": ("object-store", "Object storage bucket for artifacts and blobs"),
    "storage": ("object-store", "Object storage bucket for artifacts and blobs"),
    "function": ("function-app", "Serverless function app for event-driven workloads"),
}


class PlannerError(ValueError):
    """The intent could not be turned into a valid plan."""


class ProvisioningPlan:
    """A validated, guardrail-checked provisioning plan.

    Attributes:
        service: a ``ServiceCreate``-shaped dict.
        environment: an ``EnvironmentProvisionRequest``-shaped dict.
        source: ``"llm"`` or ``"fallback"`` — which backend produced it.
        raw: the raw dict the model emitted (None for fallback).
    """

    def __init__(
        self,
        service: Dict[str, Any],
        environment: Dict[str, Any],
        *,
        source: str,
        raw: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.service = service
        self.environment = environment
        self.source = source
        self.raw = raw

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "service": self.service,
            "environment": self.environment,
        }

    def __repr__(self) -> str:  # pragma: no cover - debug aid
        return (
            f"ProvisioningPlan(source={self.source!r}, "
            f"service={self.service['name']!r}, "
            f"tier={self.environment['tier']!r})"
        )


_SYSTEM_PROMPT = (
    "You are an infrastructure planning assistant for an Internal Developer "
    "Platform. Given a developer's natural-language request, produce the JSON "
    "needed to register a service and provision one environment for it.\n\n"
    "Return STRICT JSON with this shape and nothing else:\n"
    "{\n"
    '  "service_name": "<kebab-case-name>",\n'
    '  "description": "<one short sentence>",\n'
    '  "owner": "<team or individual>",\n'
    '  "data_sensitivity": "public" | "internal" | "confidential",\n'
    '  "environment_name": "<kebab-case>",\n'
    '  "tier": "dev" | "staging" | "prod",\n'
    '  "config": { "<string-key>": "<string-value>" }\n'
    "}\n\n"
    "Rules:\n"
    "- data_sensitivity MUST be one of public, internal, confidential.\n"
    "- tier MUST be one of dev, staging, prod.\n"
    "- Never put secrets in config; config keys password/secret/token are rejected.\n"
    "- Derive sensible kebab-case names from the request; do not invent a cloud vendor.\n"
)


def _build_prompt(intent: str) -> str:
    return (
        "Map the following developer request to the provisioning JSON schema.\n\n"
        f"Request: \"\"\"{intent.strip()}\"\"\"\n\n"
        "Respond with only the JSON object."
    )


def _coerce_plan(
    candidate: Dict[str, Any], *, source: str, raw: Optional[Dict[str, Any]]
) -> ProvisioningPlan:
    """Validate a raw candidate dict into a ProvisioningPlan.

    Runs pydantic validation on both the service and the environment,
    then re-checks the service through the GuardrailEngine so the agent
    is bound by the same policy as a human operator.
    """
    try:
        owner = str(candidate.get("owner", "platform-team")).strip() or "platform-team"
        sensitivity = (
            str(candidate.get("data_sensitivity", "internal"))
            .strip()
            .lower()
            or "internal"
        )
        tags = {"owner": owner, "data_sensitivity": sensitivity}

        service_create = ServiceCreate(
            name=candidate["service_name"],
            description=candidate.get("description"),
            tags=tags,
        )
        env_create = EnvironmentProvisionRequest(
            name=candidate["environment_name"],
            tier=EnvironmentTier(candidate["tier"]),
            config=candidate.get("config", {}) or {},
        )
    except (KeyError, ValueError, TypeError) as exc:
        raise PlannerError(f"model output missing/invalid fields: {exc}") from exc
    except ValidationError as exc:
        raise PlannerError(f"model output failed schema validation: {exc}") from exc

    # Enforce platform policy up front (tags + config). Environment
    # promotion ordering is intentionally NOT enforced here — it depends
    # on existing service state which the planner does not have. A
    # guardrail violation means the plan is invalid, which is a
    # PlannerError (so the caller can fall back), not an HTTP error.
    try:
        GuardrailEngine().validate_service_tags(service_create.tags)
        GuardrailEngine().validate_config(env_create.config)
    except HTTPException as exc:
        raise PlannerError(f"plan violates a guardrail: {exc.detail}") from exc

    return ProvisioningPlan(
        service=service_create.model_dump(),
        environment=env_create.model_dump(),
        source=source,
        raw=raw,
    )


def _fallback_plan(intent: str) -> ProvisioningPlan:
    """Deterministic planner used when the LLM is unavailable.

    Picks the first recognised resource keyword; defaults tier to dev.
    This exists so the CLI is demonstrable without a model running.
    """
    lowered = intent.lower()
    slug_name = None
    description = "Provisioned via fallback planner"
    for keyword, (name, desc) in _FALLBACK_RESOURCES.items():
        if keyword in lowered:
            slug_name = name
            description = desc
            break
    if slug_name is None:
        raise PlannerError(
            "fallback planner did not recognise a resource in the intent; "
            "run Ollama for general-purpose intent mapping"
        )

    tier = "prod" if "prod" in lowered or "production" in lowered else (
        "staging" if "staging" in lowered else "dev"
    )
    sensitivity = "confidential" if "confidential" in lowered else "internal"
    owner_match = re.search(
        r"\b(?:for|owner[:\s]+)\s+(?:(?:the|a|an)\s+)?([a-z0-9][a-z0-9-]*)", lowered
    )
    owner = owner_match.group(1) if owner_match else "platform-team"

    env_name = f"{slug_name}-{tier}"
    candidate = {
        "service_name": slug_name,
        "description": description,
        "owner": owner,
        "data_sensitivity": sensitivity,
        "environment_name": env_name,
        "tier": tier,
        "config": {"replicas": "1"},
    }
    return _coerce_plan(candidate, source="fallback", raw=None)


def plan_provisioning(
    intent: str,
    *,
    allow_fallback: Optional[bool] = None,
) -> ProvisioningPlan:
    """Map ``intent`` to a :class:`ProvisioningPlan`.

    Tries the LLM backend first. If Ollama is unreachable and
    ``allow_fallback`` is true (default: controlled by settings), the
    deterministic fallback planner is used. Otherwise the
    ``OllamaUnavailable`` error propagates.
    """
    settings = get_settings()
    use_fallback = settings.agent_allow_fallback if allow_fallback is None else allow_fallback

    try:
        raw = generate_json(_build_prompt(intent), system=_SYSTEM_PROMPT)
    except OllamaUnavailable:
        if not use_fallback:
            raise
        return _fallback_plan(intent)

    try:
        return _coerce_plan(raw, source="llm", raw=raw)
    except PlannerError:
        # A malformed model response should not hard-fail the CLI if a
        # deterministic plan is available and permitted.
        if not use_fallback:
            raise
        return _fallback_plan(intent)
