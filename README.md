# Internal Developer Platform (IDP)

An enterprise-ready FastAPI backend for self-service platform capabilities including service registration, environment provisioning, deployment orchestration, and enforceable guardrails.

## Architecture
- **FastAPI** with async SQLAlchemy 2.0 and PostgreSQL for service metadata
- **Redis** and background workers for async job execution and retries
- **Alembic** for schema migrations
- **JWT** authentication with role-based authorization (PLATFORM_ADMIN, TEAM_ADMIN, DEVELOPER)
- **Structured JSON logging** with correlation/request IDs
- **Prometheus metrics** surfaced on `/api/metrics`

## Core Concepts
- **Service**: registered workload with mandatory tags (owner, data_sensitivity)
- **Team**: ownership unit; services can be assigned to teams
- **Environment**: dev/staging/prod with promotion rules
- **Deployment**: asynchronous history per environment with approvals for prod
- **PlatformPolicy**: persisted guardrail definitions for future expansion
- **AuditLog**: all state-changing events are recorded

## Guardrails & Policies
- Mandatory tags enforced at registration and update
- `data_sensitivity` restricted to approved values
- Promotion order enforced: dev → staging → prod
- Production deployments require approvals
- Restricted configuration keys (`password`, `secret`, `token`) are blocked
- Violations return actionable 400 responses and are auditable

## Async Execution Model
- Long-running provisioning/deployment tasks are scheduled via background tasks with retry-friendly job registry
- Job status is tracked in-memory for the prototype and can be backed by Redis/Celery
- Deployment triggers return a `job_id` for idempotent retries

## Security Model
- JWT-based auth with required roles per endpoint
- Least-privilege RBAC for admin/developer personas
- Correlation IDs added to every response and structured log

## Running Locally
```bash
docker-compose up --build
```
FastAPI will be available on `http://localhost:8000`.

Run database migrations:
```bash
docker-compose run --rm web alembic upgrade head
```

## Testing & Tooling
```bash
pip install -r requirements.txt
pytest
black .
isort .
```

## Example Usage
1. Register a service
```bash
curl -X POST http://localhost:8000/api/services \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"payments","tags":{"owner":"payments","data_sensitivity":"internal"}}'
```
2. Provision an environment
```bash
curl -X POST http://localhost:8000/api/services/1/environments \
  -H "Authorization: Bearer <token>" \
  -d '{"name":"dev","tier":"dev"}'
```
3. Trigger a deployment
```bash
curl -X POST http://localhost:8000/api/services/1/environments/1/deployments \
  -H "Authorization: Bearer <token>" \
  -d '{"version":"1.0.0","initiated_by":"deploy-bot"}'
```

## How Teams Use This System
- **Platform admins** bootstrap teams, policies, and oversee audit trails.
- **Team admins** register services, provision environments, and enforce ownership metadata.
- **Developers** trigger deployments and review history, subject to guardrails.
