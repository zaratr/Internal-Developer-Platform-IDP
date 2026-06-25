# Agentic Internal Developer Platform (IDP)

A self-service platform backend (FastAPI) that lets developers register
services, provision environments, and trigger deployments — with
programmatic guardrails (mandatory tags, data-sensitivity policy,
environment promotion ordering, restricted config keys) enforced
server-side. On top of it sits a **natural-language provisioning agent**
that turns free-text intent into a validated, guardrail-checked
provisioning plan via a local LLM (Ollama).

**Skills demonstrated:** FastAPI · async SQLAlchemy · alembic migrations ·
programmatic policy/guardrails · audit logging · LLM agentic workflows ·
Ollama · pydantic schema validation

> Can this engineer turn developer intent into running infrastructure
> without giving up governance?

---

## Architecture

```
Developer (NL intent)
        │
        ▼
   agent_cli.py ──► app.agent.plan_provisioning(intent)
        │                   │
        │                   ├─► Ollama (local Gemma) ──► raw JSON plan
        │                   │         │
        │                   │         └─ (unreachable) ──► fallback planner
        │                   │
        │                   ▼
        │            pydantic validation (ServiceCreate, EnvironmentProvisionRequest)
        │                   │
        │                   ▼
        │            GuardrailEngine.validate (tags + config)
        │                   │
        │                   ▼
        │            ProvisioningPlan  ──► --dry-run: print JSON
        │                              └─► --apply: POST /services, /services/{id}/environments
        ▼
   IDP FastAPI API (Postgres-backed)
```

The agent is **bound by the same guardrails as a human operator**: it
cannot create a service missing the mandatory `owner` / `data_sensitivity`
tags, and it cannot place `password` / `secret` / `token` keys into an
environment config. Invalid model output is rejected at the schema layer.

---

## The agentic layer

`app/agent/` contains:

- **`ollama_client.py`** — stateless HTTP client for Ollama's
  `/api/generate` endpoint using JSON mode (`format: "json"`) and
  temperature 0. No SDK dependency; uses `httpx`.
- **`planner.py`** — `plan_provisioning(intent)`:
  1. Builds a system + user prompt constrained to the platform schema.
  2. Calls the local model for a JSON plan.
  3. Validates the response into `ServiceCreate` + `EnvironmentProvisionRequest`
     via pydantic.
  4. Runs `GuardrailEngine.validate_service_tags` and `.validate_config`.
  5. Returns a `ProvisioningPlan`.
- A **deterministic fallback planner** kicks in when Ollama is
  unreachable (or returns a malformed plan) so the CLI and the test
  suite stay usable offline. Disable with `--no-fallback`.

### Why the fallback exists

A portfolio demo should run on a reviewer's laptop without a GPU. The
fallback recognises a small, honest set of resource keywords (redis,
postgres, queue, storage, function) and produces the same validated plan
shape the LLM would. It is a safety net, not a substitute for the model.

---

## Quickstart

### 1. Backend

```bash
pip install -r requirements.txt
docker-compose up -d db redis
alembic upgrade head
uvicorn app.main:app --reload
```

API at `http://localhost:8000`.

### 2. Agent CLI (dry-run)

```bash
python src/agent_cli.py \
  --intent "I need a redis cache for the permit service in staging"
```

Prints the resolved plan as JSON. Without Ollama running this uses the
fallback planner and labels `"source": "fallback"`.

### 3. Agent CLI (apply to the API)

```bash
python src/agent_cli.py \
  --intent "provision a postgres-db for billing in production" \
  --apply --api-base http://localhost:8000 --token "$IDP_TOKEN"
```

### 4. (Optional) Real LLM via Ollama

```bash
ollama pull gemma2
ollama serve   # default http://localhost:11434
```

With Ollama up, the same CLI call returns `"source": "llm"` and accepts
arbitrary intent (not just the fallback keyword set).

### Configuration

Environment / `.env`:

| var | default | purpose |
|---|---|---|
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama server URL |
| `OLLAMA_MODEL` | `gemma2` | Model used by the agent |
| `AGENT_ALLOW_FALLBACK` | `true` | Use deterministic planner when the LLM is unavailable |

---

## Running tests

```bash
pytest
```

`tests/test_agent.py` exercises the fallback planner, schema/guardrail
enforcement, and the LLM path (with the Ollama call mocked) — no model
required.

---

## Repository layout

```
Internal-Developer-Platform-IDP/
├── app/
│   ├── agent/              # NL provisioning agent (Ollama + fallback)
│   ├── api/                # FastAPI routes + middleware
│   ├── core/               # config, logging, security, request context
│   ├── db/                 # async session
│   ├── models/             # SQLAlchemy models
│   ├── platform/           # GuardrailEngine (policy enforcement)
│   ├── schemas/            # pydantic domain schemas
│   └── services/           # service/environment/deployment/audit logic
├── alembic/                # migrations
├── src/agent_cli.py        # agentic CLI entrypoint
├── tests/
├── docker-compose.yml
└── pyproject.toml
```

## Design scope

The control plane uses async Postgres for state and a small set of
programmatic guardrails. Production extensions (documented, not built):
Backstage frontend, Crossplane/Kratix as the provisioning substrate,
OPA/Gatekeeper for policy, Argo CD/Flux for GitOps, and OIDC federation
for keyless deploy. The agent → plan → guardrail → API contract is
stable; those extensions swap in behind it without changing the CLI.
