"""Templates de mensagem — Story 13.10.

Revision ID: 0022
Revises: 0021
Create Date: 2026-05-27

Tabela `comunicacao.templates_mensagem` — armazena modelos personalizáveis por
empresa com fallback para template padrão do sistema (empresa_id NULL).
"""

from alembic import op


revision = "0022"
down_revision = "0021"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS comunicacao")

    op.execute("""
        CREATE TABLE comunicacao.templates_mensagem (
            id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id    UUID REFERENCES comercial.empresas(id) ON DELETE CASCADE,
            nome          VARCHAR(100) NOT NULL,
            canal         VARCHAR(30)  NOT NULL DEFAULT 'whatsapp',
            conteudo      TEXT         NOT NULL,
            descricao     TEXT,
            ativo         BOOLEAN      NOT NULL DEFAULT true,
            criado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW(),

            CONSTRAINT uniq_template_empresa_nome_canal
                UNIQUE (empresa_id, nome, canal),

            CONSTRAINT ck_canal_aceito CHECK (
                canal IN ('whatsapp','email','sms','telegram')
            )
        )
    """)

    op.execute("CREATE INDEX idx_template_nome ON comunicacao.templates_mensagem(nome)")
    op.execute("CREATE INDEX idx_template_empresa_nome ON comunicacao.templates_mensagem(empresa_id, nome)")

    # RLS permissiva (templates globais visíveis a todos os tenants)
    op.execute("ALTER TABLE comunicacao.templates_mensagem ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE comunicacao.templates_mensagem FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON comunicacao.templates_mensagem
        USING (
            empresa_id IS NULL
            OR
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS comunicacao.templates_mensagem CASCADE")
