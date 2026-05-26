"""Agent orchestrator — ReAct loop with tool execution."""

from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.agent.conversation_store import ConversationStore
from app.core.agent.tool_interface import ToolResult
from app.core.agent.tool_registry import AgentToolRegistry
from app.domain.ports.llm_provider import ILlmProvider, LlmResponse
from app.infrastructure.db.models.agent import AgentConfig, AgentRun

log = structlog.get_logger()

MAX_ITERATIONS = 10


class AgentOrchestrator:
    """ReAct-loop agent orchestrator.

    Reason -> Act -> Observe, max 10 iterations per turn.
    """

    def __init__(
        self,
        llm: ILlmProvider,
        tool_registry: AgentToolRegistry,
        session: AsyncSession,
        empresa_id: UUID,
        agent_config: AgentConfig | None = None,
    ):
        self.llm = llm
        self.tool_registry = tool_registry
        self.session = session
        self.empresa_id = empresa_id
        self.agent_config = agent_config
        self.conversation_store = ConversationStore(session, empresa_id)


    async def run_turn(
        self,
        conversation_id: UUID,
        user_message: str,
        *,
        user_permissions: list[str] | None = None,
        context: dict[str, Any] | None = None,
        system_prompt: str | None = None,
    ) -> str:
        """Run a single agent turn (may involve multiple LLM calls with tool use).

        Returns the final assistant text response.
        """
        context = context or {}
        start_time = time.time()

        # Create agent run record (story 12.3 will complete the field migration)
        agent_run = AgentRun(
            conversa_id=conversation_id,
            ferramentas_chamadas=[],
        )
        self.session.add(agent_run)
        await self.session.flush()

        # Gather conversation history
        history_msgs = await self.conversation_store.get_messages(
            conversation_id, limit=20
        )
        # Reverse to chronological order
        history_msgs = list(reversed(history_msgs))

        # Build messages list
        messages: list[dict[str, Any]] = []

        # System prompt
        prompt = system_prompt
        if not prompt and self.agent_config:
            prompt = self.agent_config.system_prompt
        if not prompt:
            prompt = "You are a helpful assistant."

        # Template substitution
        now = datetime.now(timezone.utc)
        prompt = prompt.replace("{{current_date}}", now.strftime("%Y-%m-%d"))

        messages.append({"role": "system", "content": prompt})

        # Add history
        for msg in history_msgs:
            messages.append({
                "role": msg.role,
                "content": msg.content_text or "",
                **({"tool_call_id": msg.tool_call_id} if msg.tool_call_id else {}),
                **({"name": msg.tool_name} if msg.tool_name else {}),
            })

        # Add current user message
        messages.append({"role": "user", "content": user_message})

        # Get available tools
        tools = self.tool_registry.get_tools_for_llm(user_permissions)

        total_tokens = 0
        tools_chamadas_log: list[dict[str, Any]] = []
        iterations = 0
        final_response = ""
        run_status = "running"

        try:
            for iteration in range(MAX_ITERATIONS):
                iterations = iteration + 1

                # Call LLM
                llm_response: LlmResponse = await self.llm.chat(
                    messages=messages,
                    tools=tools if tools else None,
                    temperature=0.7,
                    max_tokens=2048,
                )

                total_tokens += llm_response.total_tokens

                # No tool calls — we have the final response
                if not llm_response.tool_calls:
                    final_response = llm_response.content or ""
                    run_status = "completed"
                    break

                # Process tool calls
                assistant_content = llm_response.content or ""
                messages.append({
                    "role": "assistant",
                    "content": assistant_content,
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.name,
                                "arguments": json.dumps(tc.arguments),
                            },
                        }
                        for tc in llm_response.tool_calls
                    ],
                })

                for tc in llm_response.tool_calls:
                    log.info(
                        "agent_tool_call",
                        tool=tc.name,
                        args=tc.arguments,
                        conversation_id=str(conversation_id),
                    )

                    result: ToolResult = await self.tool_registry.execute_tool(
                        tc.name, tc.arguments, context
                    )

                    result_str = json.dumps(
                        {
                            "data": result.data,
                            "error": result.error,
                            "confidence": result.confidence,
                            "truncated": result.truncated,
                        },
                        default=str,
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc.id,
                        "content": result_str,
                        "name": tc.name,
                    })

                    tools_chamadas_log.append({
                        "name": tc.name,
                        "arguments": tc.arguments,
                        "result_confidence": result.confidence,
                        "error": result.error,
                    })

                    await self.conversation_store.append_message(
                        conversation_id,
                        role="tool",
                        content_text=result_str,
                        tool_call_id=tc.id,
                        tool_name=tc.name,
                        sent_by="agent",
                    )
            else:
                # Max iterations reached
                final_response = (
                    "Desculpe, nao consegui completar esta solicitacao. "
                    "Tente reformular sua pergunta."
                )
                run_status = "max_iterations"

        except Exception as exc:
            log.error("agent_turn_error", error=str(exc), exc_info=True)
            final_response = "Desculpe, ocorreu um erro ao processar sua solicitacao."
            run_status = "failed"
            agent_run.erro = str(exc)

        # Persist final assistant message
        await self.conversation_store.append_message(
            conversation_id,
            role="assistant",
            content_text=final_response,
            sent_by="agent",
        )

        # Update agent run — story 12.3 will add latencia_ms, tokens_entrada/saida
        elapsed_ms = int((time.time() - start_time) * 1000)
        agent_run.acao_final = run_status
        agent_run.ferramentas_chamadas = tools_chamadas_log
        agent_run.latencia_ms = elapsed_ms

        await self.session.flush()

        return final_response
