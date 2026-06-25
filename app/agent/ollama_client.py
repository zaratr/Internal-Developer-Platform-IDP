"""Minimal Ollama HTTP client.

Talks to a local Ollama server (default http://localhost:11434) using
the /api/generate endpoint with JSON mode so the model returns a JSON
object we can validate. No SDK dependency — only httpx, which is
already in the project's requirements.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings


class OllamaUnavailable(RuntimeError):
    """Raised when the Ollama server is unreachable or errors out."""


def generate_json(
    prompt: str,
    *,
    system: Optional[str] = None,
    base_url: Optional[str] = None,
    model: Optional[str] = None,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """Ask the model for a JSON object and return the parsed dict.

    Raises OllamaUnavailable if the server is not reachable or the
    response cannot be parsed as JSON.
    """
    settings = get_settings()
    base = (base_url or settings.ollama_base_url).rstrip("/")
    model = model or settings.ollama_model
    url = f"{base}/api/generate"

    payload: Dict[str, Any] = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {"temperature": 0},
    }
    if system:
        payload["system"] = system

    try:
        with httpx.Client(timeout=timeout) as client:
            resp = client.post(url, json=payload)
    except httpx.HTTPError as exc:
        raise OllamaUnavailable(f"cannot reach Ollama at {base}: {exc}") from exc

    if resp.status_code != 200:
        raise OllamaUnavailable(
            f"Ollama returned HTTP {resp.status_code}: {resp.text[:200]}"
        )

    try:
        outer = resp.json()
    except json.JSONDecodeError as exc:
        raise OllamaUnavailable(f"Ollama returned non-JSON body: {exc}") from exc

    raw = outer.get("response", "")
    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        raise OllamaUnavailable(
            f"model did not return valid JSON (got: {raw[:120]!r}): {exc}"
        ) from exc
