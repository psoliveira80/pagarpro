"""Port para provedor de IA Vision (Story 13.19).

Permite que o pipeline de análise de comprovantes acione um LLM com
visão (OpenAI Vision, Claude Vision, Gemini) como **reforço** ou
**primário**, conforme configuração do tenant.

Esta story define só o Protocol. Adapters concretos (OpenAIVisionAdapter,
ClaudeVisionAdapter) ficam para story de integração separada, quando
tenant pedir explicitamente o feature.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from app.domain.finance.comprovante import EntidadesExtraidas


@runtime_checkable
class IProvedorIAVision(Protocol):
    """Provedor de visão computacional via LLM externo (custo por uso)."""

    @property
    def nome(self) -> str:
        """Identificador: 'openai-vision', 'claude-vision', 'gemini'."""
        ...

    async def analisar_comprovante(
        self,
        bytes_arquivo: bytes,
        tipo_mime: str,
        prompt_extra: str | None = None,
    ) -> EntidadesExtraidas:
        """Submete arquivo ao LLM e retorna entidades extraídas.

        Custo por chamada varia por provedor. O caller (orquestrador) só chama
        quando `modo_analise` configurado pelo tenant exigir.
        """
        ...


# Alias EN para compat com outras integrations da arquitetura
IVisionAIProvider = IProvedorIAVision
