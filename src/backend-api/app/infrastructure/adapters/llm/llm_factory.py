"""Factory for LLM provider adapters."""

from __future__ import annotations

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.ports.llm_provider import ILlmProvider
from app.infrastructure.adapters.llm.anthropic_adapter import AnthropicAdapter
from app.infrastructure.adapters.llm.gemini_adapter import GeminiAdapter
from app.infrastructure.adapters.llm.groq_adapter import GroqAdapter
from app.infrastructure.adapters.llm.ollama_adapter import OllamaAdapter
from app.infrastructure.adapters.llm.openai_adapter import OpenAiAdapter
from app.infrastructure.settings import get_settings

log = structlog.get_logger()


async def get_llm_provider(
    session: AsyncSession | None = None,
    provider_name: str | None = None,
) -> ILlmProvider:
    """Get an LLM provider adapter.

    Priority:
    1. Look up integration_credentials for the specified or active LLM provider.
    2. Fall back to environment variable settings (LLM_PROVIDER, LLM_API_KEY, LLM_MODEL).
    """
    settings = get_settings()

    # Try DB credentials first
    if session is not None:
        try:
            from app.infrastructure.db.models.payable import IntegrationCredential

            stmt = select(IntegrationCredential).where(
                IntegrationCredential.categoria == "llm",
                IntegrationCredential.ativo.is_(True),
            )
            if provider_name:
                stmt = stmt.where(IntegrationCredential.provedor == provider_name)
            stmt = stmt.limit(1)

            result = await session.execute(stmt)
            cred = result.scalar_one_or_none()

            if cred is not None:
                return _create_adapter(
                    provider=cred.provedor,
                    api_key=cred.config.get("api_key", ""),
                    model=cred.config.get("model", ""),
                    base_url=cred.config.get("base_url"),
                )
        except Exception:
            log.warning("llm_db_credentials_lookup_failed", exc_info=True)

    # Fall back to env settings
    return _create_adapter(
        provider=provider_name or getattr(settings, "LLM_PROVIDER", "openai"),
        api_key=getattr(settings, "LLM_API_KEY", ""),
        model=getattr(settings, "LLM_MODEL", "gpt-4o"),
    )


def _create_adapter(
    provider: str,
    api_key: str,
    model: str,
    base_url: str | None = None,
) -> ILlmProvider:
    """Create the appropriate LLM adapter."""
    if provider == "openai":
        kwargs: dict = {"api_key": api_key, "model": model or "gpt-4o"}
        if base_url:
            kwargs["base_url"] = base_url
        return OpenAiAdapter(**kwargs)

    if provider == "anthropic":
        kwargs = {"api_key": api_key, "model": model or "claude-sonnet-4-20250514"}
        if base_url:
            kwargs["base_url"] = base_url
        return AnthropicAdapter(**kwargs)

    if provider == "groq":
        return GroqAdapter(api_key=api_key, model=model or "llama-3.1-70b-versatile")

    if provider == "gemini":
        return GeminiAdapter(api_key=api_key, model=model or "gemini-2.0-flash")

    if provider == "ollama":
        return OllamaAdapter(
            model=model or "llama3.1",
            base_url=base_url or "http://localhost:11434",
        )

    raise ValueError(f"Unknown LLM provider: {provider}")
