"""Conversations, messages, agent configs, agent runs, customer scores, broadcast campaigns

Revision ID: 0008
Revises: 0007
Create Date: 2026-05-15
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, TIMESTAMP

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- conversations ---
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="SET NULL"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("phone_e164", sa.Text(), nullable=True),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'active'")),
        sa.Column("last_message_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("unread_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("agent_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("agent_paused_until", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conversations_customer_id", "conversations", ["customer_id"])
    op.create_index("idx_conversations_channel_status", "conversations", ["channel", "status"])
    op.create_index("idx_conversations_phone", "conversations", ["phone_e164"])
    op.create_index("idx_conversations_last_msg", "conversations", ["channel", "last_message_at"])

    # --- conversation_messages ---
    op.create_table(
        "conversation_messages",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=True),
        sa.Column("media_url", sa.Text(), nullable=True),
        sa.Column("media_mime", sa.Text(), nullable=True),
        sa.Column("transcription", sa.Text(), nullable=True),
        sa.Column("tool_call_id", sa.Text(), nullable=True),
        sa.Column("tool_name", sa.Text(), nullable=True),
        sa.Column("sent_by", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=True),
        sa.Column("metadata_extra", JSONB, nullable=True),
        sa.Column("sent_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("delivered_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("read_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_conv_messages_conv_sent", "conversation_messages", ["conversation_id", "sent_at"])
    op.create_unique_constraint("uq_conv_messages_external_id", "conversation_messages", ["external_id"])

    # --- agent_configs ---
    op.create_table(
        "agent_configs",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("channel", sa.Text(), nullable=False),
        sa.Column("system_prompt", sa.Text(), nullable=False, server_default=sa.text("''")),
        sa.Column("llm_provider", sa.Text(), nullable=True),
        sa.Column("llm_model", sa.Text(), nullable=True),
        sa.Column("whatsapp_provider", sa.Text(), nullable=True),
        sa.Column("tools_enabled", JSONB, nullable=True),
        sa.Column("rate_limit_per_hour", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("budget_limit_monthly", sa.Numeric(15, 2), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("persona_config", JSONB, nullable=True),
        sa.Column("policy_config", JSONB, nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    # --- agent_runs ---
    op.create_table(
        "agent_runs",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_config_id", sa.Uuid(), sa.ForeignKey("agent_configs.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("completed_at", TIMESTAMP(timezone=True), nullable=True),
        sa.Column("iterations", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("tools_called", JSONB, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'running'")),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=True),
    )
    op.create_index("idx_agent_runs_conv", "agent_runs", ["conversation_id"])

    # --- customer_scores ---
    op.create_table(
        "customer_scores",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("factors", JSONB, nullable=True),
        sa.Column("calculated_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("idx_customer_scores_cust_calc", "customer_scores", ["customer_id", "calculated_at"])

    # --- broadcast_campaigns ---
    op.create_table(
        "broadcast_campaigns",
        sa.Column("id", sa.Uuid(), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("template", sa.Text(), nullable=False),
        sa.Column("audience_filter", JSONB, nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default=sa.text("'draft'")),
        sa.Column("total_recipients", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("sent_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_by", sa.Uuid(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", TIMESTAMP(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("scheduled_at", TIMESTAMP(timezone=True), nullable=True),
    )

    # Seed agent permissions
    op.execute("""
        INSERT INTO permissions (code, description) VALUES
        ('agent.config.read', 'View agent configuration'),
        ('agent.config.write', 'Edit agent configuration'),
        ('agent.chat', 'Use internal AI chat'),
        ('agent.conversations.read', 'View conversations'),
        ('agent.conversations.write', 'Send messages in conversations'),
        ('agent.broadcast.read', 'View broadcast campaigns'),
        ('agent.broadcast.write', 'Create/send broadcast campaigns'),
        ('agent.tools.billing', 'Access billing BI tools via agent'),
        ('agent.tools.fleet', 'Access fleet tools via agent')
        ON CONFLICT (code) DO NOTHING
    """)

    # Seed default agent configs
    op.execute("""
        INSERT INTO agent_configs (name, channel, system_prompt, is_active) VALUES
        ('collection_agent', 'whatsapp', 'Voce e um agente de cobranca amigavel. Ajude o cliente a resolver pendencias financeiras.', true),
        ('internal_assistant', 'in_app', 'Voce e um assistente interno de BI. Responda perguntas sobre o negocio usando as ferramentas disponiveis.', true)
    """)


def downgrade() -> None:
    op.drop_table("broadcast_campaigns")
    op.drop_table("customer_scores")
    op.drop_table("agent_runs")
    op.drop_table("agent_configs")
    op.drop_table("conversation_messages")
    op.drop_table("conversations")

    op.execute("""
        DELETE FROM permissions WHERE code IN (
            'agent.config.read', 'agent.config.write', 'agent.chat',
            'agent.conversations.read', 'agent.conversations.write',
            'agent.broadcast.read', 'agent.broadcast.write',
            'agent.tools.billing', 'agent.tools.fleet'
        )
    """)
