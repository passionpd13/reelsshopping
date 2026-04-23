"""LLM client factory.

Returns an Anthropic client (either direct API or Vertex AI) plus the
right model id, so service modules don't need to know which backend is
configured. Both clients share the same `messages.create(...)` surface.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

from app.core.config import get_settings
from app.core.logging import get_logger

log = get_logger(__name__)


@dataclass
class LLM:
    client: Any
    model: str


def get_llm() -> LLM:
    s = get_settings()
    provider = (s.llm_provider or "anthropic").lower()

    if provider == "vertex":
        try:
            from anthropic import AnthropicVertex  # type: ignore[attr-defined]
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "anthropic[vertex] is not installed. Run `pip install 'anthropic[vertex]'`."
            ) from e

        if not s.vertex_project_id:
            raise RuntimeError("VERTEX_PROJECT_ID is required when LLM_PROVIDER=vertex")

        if s.google_application_credentials and not os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = s.google_application_credentials

        log.info(
            "LLM: Vertex AI project=%s region=%s model=%s",
            s.vertex_project_id, s.vertex_region, s.vertex_model,
        )
        client = AnthropicVertex(project_id=s.vertex_project_id, region=s.vertex_region)
        return LLM(client=client, model=s.vertex_model)

    # default: direct Anthropic API
    from anthropic import Anthropic

    if not s.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is required when LLM_PROVIDER=anthropic")
    log.info("LLM: Anthropic direct, model=%s", s.anthropic_model)
    client = Anthropic(api_key=s.anthropic_api_key)
    return LLM(client=client, model=s.anthropic_model)
