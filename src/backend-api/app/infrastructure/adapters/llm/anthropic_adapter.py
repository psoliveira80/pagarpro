"""Anthropic (Claude) LLM adapter using httpx."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from app.domain.ports.llm_provider import ILlmProvider, LlmChunk, LlmResponse, ToolCall

log = structlog.get_logger()


class AnthropicAdapter:
    """Anthropic Claude adapter via raw HTTP calls."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str = "https://api.anthropic.com",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        """Extract system prompt and convert to Anthropic message format."""
        system_prompt = None
        converted = []
        for msg in messages:
            if msg["role"] == "system":
                system_prompt = msg["content"]
            elif msg["role"] == "tool":
                converted.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.get("tool_call_id", ""),
                            "content": msg["content"],
                        }
                    ],
                })
            else:
                converted.append({"role": msg["role"], "content": msg["content"]})
        return system_prompt, converted

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert OpenAI-style tools to Anthropic format."""
        return [
            {
                "name": t["name"],
                "description": t.get("description", ""),
                "input_schema": t.get("parameters", {}),
            }
            for t in tools
        ]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LlmResponse:
        system_prompt, converted_msgs = self._convert_messages(messages)

        body: dict[str, Any] = {
            "model": self.model,
            "messages": converted_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        content_text = None
        tool_calls = []

        for block in data.get("content", []):
            if block["type"] == "text":
                content_text = block["text"]
            elif block["type"] == "tool_use":
                tool_calls.append(
                    ToolCall(
                        id=block["id"],
                        name=block["name"],
                        arguments=block.get("input", {}),
                    )
                )

        usage = data.get("usage", {})
        return LlmResponse(
            content=content_text,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("input_tokens", 0),
            completion_tokens=usage.get("output_tokens", 0),
            total_tokens=usage.get("input_tokens", 0) + usage.get("output_tokens", 0),
            model=data.get("model", self.model),
            finish_reason=data.get("stop_reason", ""),
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[LlmChunk]:
        system_prompt, converted_msgs = self._convert_messages(messages)

        body: dict[str, Any] = {
            "model": self.model,
            "messages": converted_msgs,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True,
        }
        if system_prompt:
            body["system"] = system_prompt
        if tools:
            body["tools"] = self._convert_tools(tools)

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/v1/messages",
                headers=self._headers(),
                json=body,
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        event = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    if event.get("type") == "content_block_delta":
                        delta = event.get("delta", {})
                        if delta.get("type") == "text_delta":
                            yield LlmChunk(delta_content=delta.get("text"))
                    elif event.get("type") == "message_stop":
                        yield LlmChunk(finish_reason="stop")
