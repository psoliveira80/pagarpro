"""Agent configuration and internal chat endpoints (Epic 6)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from app.api.deps import CurrentUserDep, SessionDep
from app.application.shared.audit_logger import AuditLogger
from app.core.agent.conversation_store import ConversationStore
from app.core.agent.orchestrator import AgentOrchestrator
from app.core.agent.tool_registry import get_tool_registry
from app.infrastructure.adapters.llm.llm_factory import get_llm_provider
from app.infrastructure.db.models.agent import AgentConfig

log = structlog.get_logger()

router = APIRouter(prefix="/agent", tags=["agent"])


# --- Schemas ---

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: str | None = None


class ChatResponse(BaseModel):
    reply: str
    conversation_id: str


class AgentConfigResponse(BaseModel):
    id: str
    name: str
    channel: str
    system_prompt: str
    llm_provider: str | None = None
    llm_model: str | None = None
    whatsapp_provider: str | None = None
    tools_enabled: dict | None = None
    rate_limit_per_hour: int
    budget_limit_monthly: float | None = None
    is_active: bool
    persona_config: dict | None = None
    policy_config: dict | None = None

    model_config = {"from_attributes": True}


class AgentConfigUpdateRequest(BaseModel):
    name: str | None = None
    system_prompt: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    whatsapp_provider: str | None = None
    tools_enabled: dict | None = None
    rate_limit_per_hour: int | None = None
    budget_limit_monthly: float | None = None
    is_active: bool | None = None
    persona_config: dict | None = None
    policy_config: dict | None = None


class ToolInfo(BaseModel):
    name: str
    description: str
    parameters_schema: dict
    required_permissions: list[str]


def _config_to_response(c: AgentConfig) -> AgentConfigResponse:
    return AgentConfigResponse(
        id=str(c.id),
        name=c.nome,
        channel=c.tipo,
        system_prompt=c.instrucoes_sistema or "",
        llm_provider=c.provedor_llm,
        llm_model=c.modelo_llm,
        whatsapp_provider=None,  # removed in migration 0015
        tools_enabled=None,      # removed in migration 0015
        rate_limit_per_hour=0,   # removed in migration 0015
        budget_limit_monthly=None,  # removed in migration 0015
        is_active=c.ativo,
        persona_config={"nome": c.persona_nome} if c.persona_nome else None,
        policy_config=None,  # removed in migration 0015
    )


# --- Endpoints ---

@router.post("/chat", response_model=ChatResponse)
async def agent_chat(
    body: ChatRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> ChatResponse:
    """Internal AI chat — send a message and get a response."""
    store = ConversationStore(session)

    # Get or create conversation
    if body.conversation_id:
        conversation_id = UUID(body.conversation_id)
    else:
        conv = await store.get_or_create_conversation(
            channel="in_app",
            user_id=user.id,
        )
        conversation_id = conv.id

    # Persist user message
    await store.append_message(
        conversation_id,
        role="user",
        content_text=body.message,
        sent_by=f"human:{user.id}",
    )

    # Get agent config for in_app channel
    config_stmt = select(AgentConfig).where(
        AgentConfig.tipo == "in_app",
        AgentConfig.ativo.is_(True),
    ).limit(1)
    config_result = await session.execute(config_stmt)
    agent_config = config_result.scalar_one_or_none()

    # Get LLM provider
    llm = await get_llm_provider(session)

    # Get user permissions
    user_permissions = [p.codigo for perfil in user.perfis for p in perfil.permissoes]

    # Run agent turn
    registry = get_tool_registry()
    orchestrator = AgentOrchestrator(
        llm=llm,
        tool_registry=registry,
        session=session,
        empresa_id=user.empresa_id,
        agent_config=agent_config,
    )

    reply = await orchestrator.run_turn(
        conversation_id,
        body.message,
        user_permissions=user_permissions,
        context={"session": session, "empresa_id": user.empresa_id},
    )

    await session.commit()

    return ChatResponse(reply=reply, conversation_id=str(conversation_id))


@router.get("/configs", response_model=list[AgentConfigResponse])
async def list_agent_configs(
    session: SessionDep,
    user: CurrentUserDep,
) -> list[AgentConfigResponse]:
    """List all agent configurations."""
    stmt = select(AgentConfig).order_by(AgentConfig.nome)
    result = await session.execute(stmt)
    configs = result.scalars().all()
    return [_config_to_response(c) for c in configs]


@router.post("/configs", response_model=AgentConfigResponse, status_code=201)
async def create_agent_config(
    body: AgentConfigUpdateRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> AgentConfigResponse:
    """Create a new agent configuration."""
    config = AgentConfig(
        nome=body.name or "new_config",
        tipo="in_app",
        instrucoes_sistema=body.system_prompt or "",
        provedor_llm=body.llm_provider,
        modelo_llm=body.llm_model,
        ativo=body.is_active if body.is_active is not None else True,
        persona_nome=body.persona_config.get("nome") if body.persona_config else None,
    )
    session.add(config)

    audit = AuditLogger(session)
    await audit.record(
        action="agent_config.create",
        user_id=str(user.id),
        entity="agent_config",
        payload_after={"name": config.nome, "channel": config.tipo},
    )

    await session.commit()
    await session.refresh(config)
    return _config_to_response(config)


@router.put("/configs/{config_id}", response_model=AgentConfigResponse)
async def update_agent_config(
    config_id: UUID,
    body: AgentConfigUpdateRequest,
    session: SessionDep,
    user: CurrentUserDep,
) -> AgentConfigResponse:
    """Update an agent configuration."""
    stmt = select(AgentConfig).where(AgentConfig.id == config_id)
    result = await session.execute(stmt)
    config = result.scalar_one_or_none()

    if config is None:
        raise HTTPException(status_code=404, detail="Agent config not found")

    before = {"name": config.nome, "system_prompt": config.instrucoes_sistema}

    # Map API fields to model fields
    if body.name is not None:
        config.nome = body.name
    if body.system_prompt is not None:
        config.instrucoes_sistema = body.system_prompt
    if body.llm_provider is not None:
        config.provedor_llm = body.llm_provider
    if body.llm_model is not None:
        config.modelo_llm = body.llm_model
    if body.is_active is not None:
        config.ativo = body.is_active
    if body.persona_config is not None:
        config.persona_nome = body.persona_config.get("nome")

    update_data = body.model_dump(exclude_none=True)

    audit = AuditLogger(session)
    await audit.record(
        action="agent_config.update",
        user_id=str(user.id),
        entity="agent_config",
        entity_id=str(config_id),
        payload_before=before,
        payload_after=update_data,
    )

    await session.commit()
    await session.refresh(config)
    return _config_to_response(config)


@router.get("/tools", response_model=list[ToolInfo])
async def list_agent_tools(
    session: SessionDep,
    user: CurrentUserDep,
) -> list[ToolInfo]:
    """List all registered agent tools."""
    registry = get_tool_registry()
    tools = registry.list_tools()

    return [
        ToolInfo(
            name=t.name,
            description=t.description,
            parameters_schema=t.parameters_schema,
            required_permissions=t.required_permissions,
        )
        for t in tools
    ]
