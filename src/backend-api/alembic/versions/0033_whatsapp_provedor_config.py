"""Cria config.whatsapp_provedor_config — provedor WhatsApp por empresa (1:1).

Revision ID: 0033
Revises: 0032
Create Date: 2026-05-29

Separa "qual API WhatsApp e suas chaves globais" (1 por empresa, vive em
Integrações) das "instâncias/números" (N por empresa, vive em Canais).
Antes ficavam misturados em `config.credenciais_integracao` com JSONB
contendo tudo.

Data migration: pra cada empresa com >=1 credencial WhatsApp existente,
extrai provedor + (base_url, api_key) — quando aplicáveis — pra primeira
linha de provider config. As credenciais antigas continuam intactas
(rollback fácil). O `whatsapp_factory._build_adapter` faz merge dos dois.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql


revision = "0033"
down_revision = "0032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "whatsapp_provedor_config",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True,
                  server_default=sa.text("gen_random_uuid()")),
        sa.Column("empresa_id", postgresql.UUID(as_uuid=True),
                  sa.ForeignKey("comercial.empresas.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("provedor", sa.Text(), nullable=False),
        sa.Column("config", postgresql.JSONB(), nullable=False,
                  server_default=sa.text("'{}'::jsonb")),
        sa.Column("ativo", sa.Boolean(), nullable=False,
                  server_default=sa.text("true")),
        sa.Column("criado_em", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("atualizado_em", sa.TIMESTAMP(timezone=True), nullable=False,
                  server_default=sa.text("now()")),
        sa.Column("atualizado_por_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.UniqueConstraint("empresa_id", name="uq_whatsapp_provedor_config_empresa"),
        schema="config",
    )

    # Data migration — extrai provider-level config da primeira credencial
    # WhatsApp ativa de cada empresa, criando a entry de provedor.
    # Pra evolution_api/uazapi pega base_url + api_key do JSONB; pros demais
    # cria config vazia (Evolution Go usa env; Z-API só tem campos de instância).
    op.execute("""
        INSERT INTO config.whatsapp_provedor_config (empresa_id, provedor, config, ativo)
        SELECT DISTINCT ON (c.empresa_id)
            c.empresa_id,
            c.provedor,
            CASE
                WHEN c.provedor IN ('evolution_api', 'uazapi') THEN
                    jsonb_build_object(
                        'base_url', COALESCE(c.config->>'base_url', ''),
                        'api_key', COALESCE(c.config->>'api_key', '')
                    )
                ELSE '{}'::jsonb
            END AS config,
            true
        FROM config.credenciais_integracao c
        WHERE c.categoria = 'whatsapp' AND c.ativo = true
        ORDER BY c.empresa_id, c.criado_em ASC
        ON CONFLICT (empresa_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table("whatsapp_provedor_config", schema="config")
