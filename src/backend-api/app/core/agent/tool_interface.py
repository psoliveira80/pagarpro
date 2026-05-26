"""Agent tool interface and result types."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Protocol, runtime_checkable


@dataclass
class ToolResult:
    """Result returned by an agent tool execution."""

    data: Any = None
    error: str | None = None
    confidence: str = "high"  # high | medium | low
    truncated: bool = False
    total_count: int | None = None


@dataclass
class ToolDefinition:
    """Registration metadata for an agent tool."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    required_permissions: list[str] = field(default_factory=list)
    handler: Callable[..., Coroutine[Any, Any, ToolResult]] | None = None
    requires_confirmation: bool = False
