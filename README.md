# Agentic Internal Developer Platform (IDP)

## ?? 2026 Architecture Modernization
Developer portals have evolved from static dashboards to **Agentic Workflows**. This enterprise IDP backend now features a natural-language CLI agent that translates developer intent into infrastructure reality.

### Key Features
1. **Agentic CLI Provisioning:** Developers type natural language (e.g., "I need a Redis cache for the permit service"). The local LLM processes the intent and outputs the exact JSON payload required by the IDP.
2. **Self-Service Guardrails:** Enforces compliance and security policies programmatically before infrastructure is provisioned.
3. **Service Orchestration:** Automates environment setup, deployment pipelines, and service registration.

## ??? Tech Stack
*   **Backend:** FastAPI, Python
*   **CLI Interface:** Argparse / Typer
*   **AI Agent:** Local LLM mapping (Ollama)
