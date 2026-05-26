"""Ollama LLM adapter using httpx (local/self-hosted)."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from app.domain.ports.llm_provider import ILlmProvider, LlmChunk, LlmResponse, ToolCall

log = structlog.get_logger()


class OllamaAdapter:
    """Ollama adapter for local/self-hosted models."""

    def __init__(self, model: str = "llama3.1", base_url: str = "http://localhost:11434"):
        self.model = model
        self.base_url = base_url.rstrip("/")

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LlmResponse:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]

        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(f"{self.base_url}/api/chat", json=body)
            resp.raise_for_status()
            data = resp.json()

        message = data.get("message", {})
        tool_calls = []

        if message.get("tool_calls"):
            for tc in message["tool_calls"]:
                fn = tc.get("function", {})
                tool_calls.append(
                    ToolCall(
                        id=fn.get("name", ""),
                        name=fn.get("name", ""),
                        arguments=fn.get("arguments", {}),
                    )
                )

        return LlmResponse(
            content=message.get("content"),
            tool_calls=tool_calls,
            prompt_tokens=data.get("prompt_eval_count", 0),
            completion_tokens=data.get("eval_count", 0),
            total_tokens=data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
            model=self.model,
            finish_reason="stop" if data.get("done") else "",
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[LlmChunk]:
        body: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
        }
        if tools:
            body["tools"] = [{"type": "function", "function": t} for t in tools]

        async with httpx.AsyncClient(timeout=300) as client:
            async with client.stream(
                "POST", f"{self.base_url}/api/chat", json=body
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    message = data.get("message", {})
                    done = data.get("done", False)
                    yield LlmChunk(
                        delta_content=message.get("content"),
                        finish_reason="stop" if done else None,
                    )
