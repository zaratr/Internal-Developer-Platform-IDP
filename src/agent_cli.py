"""Agentic CLI for the Internal Developer Platform.

Usage:

    python -m agent_cli --intent "I need a redis cache for the permit service in staging"

By default the CLI prints the resolved provisioning plan as JSON
(``--dry-run``). Pass ``--apply`` to POST the plan to a running IDP
API instance. The plan is produced by the NL agent (Ollama) and
validated against the platform's pydantic schemas and guardrails
before anything is printed or sent.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Optional

# Allow running as `python src/agent_cli.py` by ensuring the repo root
# (parent of this src/ dir) is on sys.path so the `app` package imports.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _REPO_ROOT not in sys.path:
    sys.path.insert(0, _REPO_ROOT)

import httpx  # noqa: E402  (import after path bootstrap)

from app.agent import PlannerError, plan_provisioning
from app.core.config import get_settings


def _emit(plan_dict: dict) -> int:
    json.dump(plan_dict, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")
    return 0


def _apply(plan_dict: dict, api_base: str, token: Optional[str]) -> int:
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with httpx.Client(base_url=api_base, timeout=30.0) as client:
        svc = client.post("/services", json=plan_dict["service"], headers=headers)
        if svc.status_code >= 400 and svc.status_code != 400:
            sys.stderr.write(f"service create failed: {svc.status_code} {svc.text}\n")
            return 1
        if svc.status_code == 201:
            service_id = svc.json().get("id")
        else:
            # Service may already exist; look it up by name.
            name = plan_dict["service"]["name"]
            lookup = client.get(f"/services", params={"name": name}, headers=headers)
            found = None
            try:
                body = lookup.json()
                found = next(
                    (s for s in (body if isinstance(body, list) else body.get("items", []))
                     if s.get("name") == name),
                    None,
                )
            except ValueError:
                pass
            if not found:
                sys.stderr.write(
                    f"service create returned {svc.status_code} and lookup failed\n"
                )
                return 1
            service_id = found["id"]

        env_payload = dict(plan_dict["environment"])
        env = client.post(
            f"/services/{service_id}/environments", json=env_payload, headers=headers
        )
        if env.status_code >= 400:
            sys.stderr.write(f"environment provision failed: {env.status_code} {env.text}\n")
            return 1

    json.dump(
        {"service_id": service_id, "environment": env.json()},
        sys.stdout,
        indent=2,
        sort_keys=True,
    )
    sys.stdout.write("\n")
    return 0


def main(argv: Optional[list] = None) -> int:
    settings = get_settings()
    parser = argparse.ArgumentParser(
        prog="agent-cli",
        description="Turn natural language into an IDP provisioning plan.",
    )
    parser.add_argument(
        "--intent",
        required=True,
        help='Natural-language request, e.g. "I need a redis cache for the permit service"',
    )
    parser.add_argument(
        "--no-fallback",
        action="store_true",
        help="Fail hard if the LLM is unreachable instead of using the fallback planner",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="POST the plan to the IDP API (default: dry-run, print JSON only)",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="IDP API base URL when --apply is used",
    )
    parser.add_argument("--token", default=None, help="Bearer token for the IDP API")
    args = parser.parse_args(argv)

    try:
        plan = plan_provisioning(
            args.intent, allow_fallback=not args.no_fallback
        )
    except PlannerError as exc:
        sys.stderr.write(f"could not plan provisioning: {exc}\n")
        return 2

    plan_dict = plan.to_dict()
    plan_dict["model"] = settings.ollama_model

    if args.apply:
        return _apply(plan_dict, args.api_base, args.token)
    return _emit(plan_dict)


if __name__ == "__main__":
    sys.exit(main())
