"""Port for LLM providers."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, runtime_checkable


@dataclass
class ToolCall:
    """A tool call requested by the LLM."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass
class LlmResponse:
    """Response from an LLM completion call."""

    content: str | None = None
    tool_calls: list[ToolCall] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    model: str = ""
    finish_reason: str = ""


@dataclass
class LlmChunk:
    """Streaming chunk from an LLM."""

    delta_content: str | None = None
    delta_tool_call: dict[str, Any] | None = None
    finish_reason: str | None = None


@runtime_checkable
class ILlmProvider(Protocol):
    """Interface for LLM provider adapters."""

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LlmResponse:
        """Send a chat completion request."""
        ...

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[LlmChunk]:
        """Stream a chat completion request."""
        ...
