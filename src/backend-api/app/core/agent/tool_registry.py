"""Agent tool registry — central registration and permission-filtered access."""

from __future__ import annotations

from typing import Any

import structlog

from app.core.agent.tool_interface import ToolDefinition, ToolResult

log = structlog.get_logger()


class AgentToolRegistry:
    """Registry for agent tools with permission-based filtering."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolDefinition] = {}

    def register(self, tool: ToolDefinition) -> None:
        """Register a tool definition."""
        self._tools[tool.name] = tool
        log.info("agent_tool_registered", tool_name=tool.name)

    def list_tools(self, user_permissions: list[str] | None = None) -> list[ToolDefinition]:
        """List tools, optionally filtered by user permissions."""
        if user_permissions is None:
            return list(self._tools.values())

        return [
            t
            for t in self._tools.values()
            if not t.required_permissions
            or any(p in user_permissions for p in t.required_permissions)
        ]

    def get_tool(self, name: str) -> ToolDefinition | None:
        """Get a specific tool by name."""
        return self._tools.get(name)

    def get_tools_for_llm(
        self, user_permissions: list[str] | None = None
    ) -> list[dict[str, Any]]:
        """Get tool definitions in OpenAI function-calling format for LLM prompts."""
        tools = self.list_tools(user_permissions)
        return [
            {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters_schema,
            }
            for t in tools
        ]

    async def execute_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> ToolResult:
        """Execute a tool by name with given arguments.

        Arguments from the LLM are validated against the tool's parameters_schema
        (only declared keys are kept). Context is passed separately so LLM-supplied
        values cannot override trusted orchestrator values like tenant_id / session.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(error=f"Tool '{name}' not found", confidence="low")

        if tool.handler is None:
            return ToolResult(error=f"Tool '{name}' has no handler", confidence="low")

        # B-H6: If the tool requires confirmation, return a prompt instead of executing
        if tool.requires_confirmation:
            if not (context or {}).get("user_confirmed"):
                return ToolResult(
                    data={
                        "requires_confirmation": True,
                        "tool_name": name,
                        "arguments": arguments,
                        "confirmation_prompt": (
                            f"A ferramenta '{name}' requer confirmacao do usuario. "
                            "Por favor confirme antes de prosseguir."
                        ),
                    },
                    confidence="high",
                )

        try:
            # B-H2: Strip LLM arguments to only keys declared in parameters_schema
            allowed_keys = set(
                tool.parameters_schema.get("properties", {}).keys()
            )
            validated_args = {
                k: v for k, v in arguments.items() if k in allowed_keys
            }

            # Inject context separately — context keys take precedence
            if context:
                validated_args.update(context)

            result = await tool.handler(**validated_args)
            return result
        except Exception as exc:
            log.error("tool_execution_error", tool_name=name, error=str(exc))
            return ToolResult(error=f"Tool execution failed: {str(exc)}", confidence="low")


# Global registry instance
_registry = AgentToolRegistry()


def get_tool_registry() -> AgentToolRegistry:
    """Get the global tool registry."""
    return _registry
