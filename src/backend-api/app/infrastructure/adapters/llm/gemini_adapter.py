"""Google Gemini LLM adapter using httpx."""

from __future__ import annotations

import json
from typing import Any, AsyncIterator

import httpx
import structlog

from app.domain.ports.llm_provider import ILlmProvider, LlmChunk, LlmResponse, ToolCall

log = structlog.get_logger()


class GeminiAdapter:
    """Google Gemini adapter via generativelanguage.googleapis.com."""

    def __init__(self, api_key: str, model: str = "gemini-2.0-flash"):
        self.api_key = api_key
        self.model = model
        self.base_url = "https://generativelanguage.googleapis.com/v1beta"

    def _convert_messages(
        self, messages: list[dict[str, Any]]
    ) -> tuple[str | None, list[dict[str, Any]]]:
        system_instruction = None
        contents = []
        for msg in messages:
            if msg["role"] == "system":
                system_instruction = msg["content"]
            elif msg["role"] == "tool":
                contents.append({
                    "role": "function",
                    "parts": [
                        {
                            "functionResponse": {
                                "name": msg.get("name", ""),
                                "response": {"result": msg["content"]},
                            }
                        }
                    ],
                })
            else:
                role = "user" if msg["role"] == "user" else "model"
                contents.append({"role": role, "parts": [{"text": msg["content"]}]})
        return system_instruction, contents

    def _convert_tools(self, tools: list[dict[str, Any]]) -> list[dict[str, Any]]:
        declarations = []
        for t in tools:
            declarations.append({
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {}),
            })
        return [{"functionDeclarations": declarations}]

    async def chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> LlmResponse:
        system_instruction, contents = self._convert_messages(messages)

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            body["tools"] = self._convert_tools(tools)

        url = f"{self.base_url}/models/{self.model}:generateContent"

        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                url,
                json=body,
                headers={"x-goog-api-key": self.api_key},
            )
            resp.raise_for_status()
            data = resp.json()

        candidates = data.get("candidates", [{}])
        candidate = candidates[0] if candidates else {}
        parts = candidate.get("content", {}).get("parts", [])

        content_text = None
        tool_calls = []

        for part in parts:
            if "text" in part:
                content_text = part["text"]
            elif "functionCall" in part:
                fc = part["functionCall"]
                tool_calls.append(
                    ToolCall(
                        id=fc.get("name", ""),
                        name=fc["name"],
                        arguments=fc.get("args", {}),
                    )
                )

        usage = data.get("usageMetadata", {})
        return LlmResponse(
            content=content_text,
            tool_calls=tool_calls,
            prompt_tokens=usage.get("promptTokenCount", 0),
            completion_tokens=usage.get("candidatesTokenCount", 0),
            total_tokens=usage.get("totalTokenCount", 0),
            model=self.model,
            finish_reason=candidate.get("finishReason", ""),
        )

    async def stream_chat(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
        temperature: float = 0.7,
        max_tokens: int = 2048,
    ) -> AsyncIterator[LlmChunk]:
        system_instruction, contents = self._convert_messages(messages)

        body: dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            },
        }
        if system_instruction:
            body["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        if tools:
            body["tools"] = self._convert_tools(tools)

        url = (
            f"{self.base_url}/models/{self.model}:streamGenerateContent"
            f"?alt=sse"
        )

        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                url,
                json=body,
                headers={"x-goog-api-key": self.api_key},
            ) as resp:
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    try:
                        chunk = json.loads(line[6:])
                    except json.JSONDecodeError:
                        continue
                    parts = (
                        chunk.get("candidates", [{}])[0]
                        .get("content", {})
                        .get("parts", [])
                    )
                    for part in parts:
                        if "text" in part:
                            yield LlmChunk(delta_content=part["text"])
