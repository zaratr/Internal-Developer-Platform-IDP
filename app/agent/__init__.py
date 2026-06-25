"""Natural-language provisioning agent.

Maps developer intent (free text) to IDP provisioning payloads
(`ServiceCreate` + `EnvironmentProvisionRequest`) using a local LLM
via Ollama. Falls back to a deterministic planner when no model is
reachable so the CLI and tests stay usable offline.
"""

from app.agent.planner import (
    ProvisioningPlan,
    PlannerError,
    plan_provisioning,
)

__all__ = ["ProvisioningPlan", "PlannerError", "plan_provisioning"]
