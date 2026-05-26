"""Tests for the AgentOrchestrator ReAct loop."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from app.core.agent.orchestrator import AgentOrchestrator, MAX_ITERATIONS
from app.core.agent.tool_interface import ToolDefinition, ToolResult
from app.core.agent.tool_registry import AgentToolRegistry
from app.domain.ports.llm_provider import LlmChunk, LlmResponse, ToolCall


# --- Helpers ---

class MockLlm:
    """Mock LLM that returns pre-configured responses in sequence."""

    def __init__(self, responses: list[LlmResponse]):
        self._responses = list(responses)
        self._call_count = 0

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LlmResponse:
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = LlmResponse(content="Fallback response", total_tokens=10)
        self._call_count += 1
        return resp

    async def stream_chat(self, *args: Any, **kwargs: Any) -> AsyncIterator[LlmChunk]:
        yield LlmChunk(delta_content="streamed", finish_reason="stop")


async def _dummy_tool(**kwargs: Any) -> ToolResult:
    return ToolResult(data={"result": "tool_executed"}, confidence="high")


async def _failing_tool(**kwargs: Any) -> ToolResult:
    raise RuntimeError("Tool exploded")


# --- Tests ---


class TestAgentOrchestrator:
    """Test the ReAct loop orchestrator."""

    @pytest.fixture
    def registry(self) -> AgentToolRegistry:
        reg = AgentToolRegistry()
        reg.register(
            ToolDefinition(
                name="test_tool",
                description="A test tool",
                parameters_schema={"type": "object", "properties": {}},
                required_permissions=[],
                handler=_dummy_tool,
            )
        )
        return reg

    @pytest.fixture
    def conversation_id(self):
        return uuid4()

    @pytest.mark.asyncio
    async def test_simple_text_response_no_tools(self, registry, conversation_id):
        """LLM returns text immediately without tool calls."""
        llm = MockLlm([
            LlmResponse(content="Hello there!", total_tokens=50),
        ])

        session = AsyncMock()
        session.execute = AsyncMock(return_value=MagicMock(scalars=MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))))
        session.flush = AsyncMock()
        session.add = MagicMock()

        with patch("app.core.agent.orchestrator.ConversationStore") as MockStore:
            store_instance = AsyncMock()
            store_instance.get_messages = AsyncMock(return_value=[])
            store_instance.append_message = AsyncMock()
            MockStore.return_value = store_instance

            orchestrator = AgentOrchestrator(
                llm=llm,
                tool_registry=registry,
                session=session,
                empresa_id=uuid4(),
                agent_config=None,
            )

            result = await orchestrator.run_turn(conversation_id, "Hi")

        assert result == "Hello there!"
        assert llm._call_count == 1

    @pytest.mark.asyncio
    async def test_single_tool_call_then_response(self, registry, conversation_id):
        """LLM calls one tool, then returns a text response."""
        llm = MockLlm([
            LlmResponse(
                content=None,
                tool_calls=[
                    ToolCall(id="call_1", name="test_tool", arguments={}),
                ],
                total_tokens=100,
            ),
            LlmResponse(content="Here is the result!", total_tokens=50),
        ])

        session = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()

        with patch("app.core.agent.orchestrator.ConversationStore") as MockStore:
            store_instance = AsyncMock()
            store_instance.get_messages = AsyncMock(return_value=[])
            store_instance.append_message = AsyncMock()
            MockStore.return_value = store_instance

            orchestrator = AgentOrchestrator(
                llm=llm,
                tool_registry=registry,
                session=session,
                empresa_id=uuid4(),
            )

            result = await orchestrator.run_turn(conversation_id, "Run the tool")

        assert result == "Here is the result!"
        assert llm._call_count == 2

    @pytest.mark.asyncio
    async def test_max_iterations_cap(self, registry, conversation_id):
        """When LLM keeps requesting tools, cap at MAX_ITERATIONS."""
        # Create responses that always request a tool call
        responses = [
            LlmResponse(
                content=None,
                tool_calls=[ToolCall(id=f"call_{i}", name="test_tool", arguments={})],
                total_tokens=10,
            )
            for i in range(MAX_ITERATIONS + 5)
        ]
        llm = MockLlm(responses)

        session = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()

        with patch("app.core.agent.orchestrator.ConversationStore") as MockStore:
            store_instance = AsyncMock()
            store_instance.get_messages = AsyncMock(return_value=[])
            store_instance.append_message = AsyncMock()
            MockStore.return_value = store_instance

            orchestrator = AgentOrchestrator(
                llm=llm,
                tool_registry=registry,
                session=session,
                empresa_id=uuid4(),
            )

            result = await orchestrator.run_turn(conversation_id, "Loop forever")

        assert "nao consegui completar" in result.lower()
        assert llm._call_count == MAX_ITERATIONS

    @pytest.mark.asyncio
    async def test_permission_filtering(self, conversation_id):
        """Tools are filtered by user permissions."""
        registry = AgentToolRegistry()
        registry.register(
            ToolDefinition(
                name="restricted_tool",
                description="Needs special permission",
                parameters_schema={"type": "object"},
                required_permissions=["special.access"],
                handler=_dummy_tool,
            )
        )
        registry.register(
            ToolDefinition(
                name="open_tool",
                description="No permissions needed",
                parameters_schema={"type": "object"},
                required_permissions=[],
                handler=_dummy_tool,
            )
        )

        # Without special.access permission
        tools_no_perm = registry.get_tools_for_llm(user_permissions=["basic.access"])
        assert len(tools_no_perm) == 1
        assert tools_no_perm[0]["name"] == "open_tool"

        # With special.access permission
        tools_with_perm = registry.get_tools_for_llm(user_permissions=["special.access"])
        assert len(tools_with_perm) == 2

    @pytest.mark.asyncio
    async def test_tool_execution_error_handled(self, conversation_id):
        """Tool execution errors are caught and returned gracefully."""
        registry = AgentToolRegistry()
        registry.register(
            ToolDefinition(
                name="bad_tool",
                description="A tool that fails",
                parameters_schema={"type": "object"},
                handler=_failing_tool,
            )
        )

        result = await registry.execute_tool("bad_tool", {})
        assert result.error is not None
        assert "Tool exploded" in result.error
        assert result.confidence == "low"

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_error(self):
        """Calling an unknown tool returns an error result."""
        registry = AgentToolRegistry()
        result = await registry.execute_tool("nonexistent", {})
        assert result.error is not None
        assert "not found" in result.error
