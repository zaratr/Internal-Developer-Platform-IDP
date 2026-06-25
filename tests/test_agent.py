"""Tests for the NL provisioning agent.

These exercise the deterministic fallback path and the schema/guardrail
validation, so they run without an Ollama server. The LLM path is
covered by patching ``generate_json`` to return a canned response.
"""

import json

import pytest

from app.agent import PlannerError, plan_provisioning
from app.agent import planner as planner_mod
from app.models.models import EnvironmentTier


# --- fallback planner ------------------------------------------------------

def test_fallback_recognises_redis():
    plan = plan_provisioning("I need a redis cache for the permit service")
    assert plan.source == "fallback"
    assert plan.service["name"] == "redis-cache"
    assert plan.service["tags"]["owner"] == "permit"
    assert plan.service["tags"]["data_sensitivity"] == "internal"
    assert plan.environment["tier"] == EnvironmentTier.dev


def test_fallback_promotes_tier_from_intent():
    plan = plan_provisioning("provision a postgres-db for billing in production")
    assert plan.environment["tier"] == EnvironmentTier.prod


def test_fallback_unknown_resource_raises():
    with pytest.raises(PlannerError):
        plan_provisioning("just make the internet faster")


# --- schema + guardrail enforcement ---------------------------------------

def test_plan_has_mandatory_tags():
    plan = plan_provisioning("I need a redis cache")
    tags = plan.service["tags"]
    assert "owner" in tags
    assert "data_sensitivity" in tags


def test_environment_config_rejects_secrets_via_guardrails():
    # The guardrail engine bans password/secret/token config keys; a
    # model output containing one must be rejected even though the
    # pydantic schema would otherwise accept arbitrary config dicts.
    bad_model_output = {
        "service_name": "redis-cache",
        "description": "x",
        "owner": "team",
        "data_sensitivity": "internal",
        "environment_name": "redis-cache-dev",
        "tier": "dev",
        "config": {"password": "hunter2"},
    }
    monkeypatch_generate(bad_model_output)
    # Fallback is allowed, so the bad LLM output is dropped in favour
    # of a clean fallback plan rather than surfacing the secret.
    plan = plan_provisioning("I need a redis cache", allow_fallback=True)
    assert "password" not in plan.environment["config"]


def test_bad_tier_rejected_when_no_fallback():
    bad_model_output = {
        "service_name": "x",
        "description": "x",
        "owner": "t",
        "data_sensitivity": "internal",
        "environment_name": "x",
        "tier": "prod-pre",  # invalid enum value
        "config": {},
    }
    monkeypatch_generate(bad_model_output)
    with pytest.raises(PlannerError):
        plan_provisioning("x", allow_fallback=False)


# --- LLM path (mocked) -----------------------------------------------------

def test_llm_path_emits_valid_plan(monkeypatch):
    good = {
        "service_name": "payments-api",
        "description": "Card payments service",
        "owner": "payments-team",
        "data_sensitivity": "confidential",
        "environment_name": "payments-api-staging",
        "tier": "staging",
        "config": {"region": "us-west"},
    }
    monkeypatch_generate(good)
    plan = plan_provisioning("set up payments-api in staging", allow_fallback=False)
    assert plan.source == "llm"
    assert plan.service["name"] == "payments-api"
    assert plan.environment["tier"] == EnvironmentTier.staging
    assert plan.environment["config"] == {"region": "us-west"}
    assert plan.raw == good


# --- helpers ---------------------------------------------------------------

def monkeypatch_generate(return_value):
    """Patch the planner's generate_json reference to return a dict.

    Planner imports generate_json by name, so patch it on the planner
    module. A dict return value bypasses the Ollama HTTP path entirely.
    """
    from app.agent import planner as p

    p.generate_json = lambda *a, **k: return_value
