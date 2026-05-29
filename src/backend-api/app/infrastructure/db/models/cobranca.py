from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, Integer, Numeric, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP
from sqlalchemy.orm import Mapped, mapped_column, relationship, synonym

from app.infrastructure.db.base import Base, UUIDPrimaryKeyMixin, TimestampMixin


class Conversa(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "conversas"
    __table_args__ = {"schema": "cobranca"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    cliente_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cadastro.clientes.id", ondelete="SET NULL"), nullable=True
    )
    usuario_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id", ondelete="SET NULL"), nullable=True
    )
    telefone: Mapped[str | None] = mapped_column(Text, nullable=True)
    ultima_mensagem_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    nao_lidas: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    arquivada: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    agente_ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )
    agente_pausado_ate: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    canal: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'whatsapp'")
    )
    situacao: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'ativa'")
    )

    mensagens: Mapped[list["Mensagem"]] = relationship(
        back_populates="conversa",
        lazy="selectin",
        order_by="Mensagem.enviado_em.desc()",
    )

    # --- Compat aliases (Story 12.3 transition) ---
    customer_id = synonym("cliente_id")
    user_id = synonym("usuario_id")
    phone_e164 = synonym("telefone")
    last_message_at = synonym("ultima_mensagem_em")
    unread_count = synonym("nao_lidas")
    is_archived = synonym("arquivada")
    agent_active = synonym("agente_ativo")
    agent_paused_until = synonym("agente_pausado_ate")
    channel = synonym("canal")
    status = synonym("situacao")
    messages = synonym("mensagens")


class Mensagem(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "mensagens"
    __table_args__ = (
        # Multi-tenant unique: include empresa_id so different tenants can store
        # rows with the same upstream provider external_id. See migration 0016.
        UniqueConstraint("empresa_id", "external_id", name="uq_mensagens_empresa_external"),
        {"schema": "cobranca"},
    )

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    conversa_id: Mapped[UUID] = mapped_column(
        ForeignKey("cobranca.conversas.id"), nullable=False
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    direcao: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    conteudo_texto: Mapped[str | None] = mapped_column(Text, nullable=True)
    midia_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    midia_mime: Mapped[str | None] = mapped_column(Text, nullable=True)
    enviado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), nullable=False
    )
    entregue_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    lido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    enviado_por: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    contexto: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    transcricao: Mapped[str | None] = mapped_column(Text, nullable=True)
    perfil: Mapped[str | None] = mapped_column(Text, nullable=True)
    tool_call_id: Mapped[str | None] = mapped_column(Text, nullable=True)  # restored in migration 0018
    tool_name: Mapped[str | None] = mapped_column(Text, nullable=True)  # restored in migration 0018
    # Story 13.21 — qual número (credencial Evolution Go da empresa) processou
    # esta mensagem. Permite timeline unificada com filtro por número.
    numero_origem_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("config.credenciais_integracao.id", ondelete="SET NULL"),
        nullable=True,
    )
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )

    conversa: Mapped["Conversa"] = relationship(back_populates="mensagens")

    # --- Compat aliases (Story 12.3 transition) ---
    conversation_id = synonym("conversa_id")
    role = synonym("perfil")
    metadata_extra = synonym("contexto")
    direction = synonym("direcao")
    kind = synonym("tipo")
    content_text = synonym("conteudo_texto")
    media_url = synonym("midia_url")
    media_mime = synonym("midia_mime")
    sent_at = synonym("enviado_em")
    delivered_at = synonym("entregue_em")
    read_at = synonym("lido_em")
    sent_by = synonym("enviado_por")
    context = synonym("contexto")
    transcription = synonym("transcricao")
    created_at = synonym("criado_em")
    conversation = synonym("conversa")


class ConfiguracaoAgente(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "configuracoes_agente"
    __table_args__ = {"schema": "cobranca"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    tipo: Mapped[str] = mapped_column(Text, nullable=False)
    provedor_llm: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo_llm: Mapped[str | None] = mapped_column(Text, nullable=True)
    temperatura: Mapped[Decimal] = mapped_column(
        Numeric(4, 2), nullable=False, server_default=text("0.70")
    )
    max_tokens: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1000")
    )
    persona_nome: Mapped[str | None] = mapped_column(Text, nullable=True)
    tom: Mapped[str | None] = mapped_column(Text, nullable=True)
    instrucoes_sistema: Mapped[str | None] = mapped_column(Text, nullable=True)
    ativo: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("true")
    )


class ExecucaoAgente(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "execucoes_agente"
    __table_args__ = {"schema": "cobranca"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    conversa_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cobranca.conversas.id"), nullable=True
    )
    mensagem_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("cobranca.mensagens.id"), nullable=True
    )
    provedor: Mapped[str | None] = mapped_column(Text, nullable=True)
    modelo: Mapped[str | None] = mapped_column(Text, nullable=True)
    tokens_entrada: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tokens_saida: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latencia_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    ferramentas_chamadas: Mapped[list] = mapped_column(
        JSONB, nullable=False, server_default=text("'[]'")
    )
    acao_final: Mapped[str | None] = mapped_column(Text, nullable=True)
    erro: Mapped[str | None] = mapped_column(Text, nullable=True)
    custo_usd: Mapped[Decimal | None] = mapped_column(Numeric(10, 6), nullable=True)
    criado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class ScoreCliente(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "scores_clientes"
    __table_args__ = {"schema": "cobranca"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    cliente_id: Mapped[UUID] = mapped_column(
        ForeignKey("cadastro.clientes.id", ondelete="CASCADE"), nullable=False
    )
    score: Mapped[int] = mapped_column(nullable=False)
    pontualidade_pct: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    dias_atraso_medio: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), nullable=True)
    tempo_relacionamento_meses: Mapped[int | None] = mapped_column(Integer, nullable=True)
    valor_total_pago: Mapped[Decimal | None] = mapped_column(Numeric(15, 2), nullable=True)
    detalhamento: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    calculado_em: Mapped[datetime] = mapped_column(
        TIMESTAMP(timezone=True), server_default=func.now(), nullable=False
    )


class CampanhaDisparo(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "campanhas_disparo"
    __table_args__ = {"schema": "cobranca"}

    empresa_id: Mapped[UUID] = mapped_column(
        ForeignKey("comercial.empresas.id"), nullable=False
    )
    nome: Mapped[str] = mapped_column(Text, nullable=False)
    mensagem: Mapped[str] = mapped_column(Text, nullable=False)
    filtros: Mapped[dict] = mapped_column(
        JSONB, nullable=False, server_default=text("'{}'")
    )
    total_destinatarios: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("0")
    )
    enviadas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    entregues: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    lidas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    falhas: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("0"))
    status: Mapped[str] = mapped_column(
        Text, nullable=False, server_default=text("'rascunho'")
    )
    agendado_para: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    iniciado_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    concluido_em: Mapped[datetime | None] = mapped_column(
        TIMESTAMP(timezone=True), nullable=True
    )
    criado_por_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("acesso.usuarios.id"), nullable=True
    )
