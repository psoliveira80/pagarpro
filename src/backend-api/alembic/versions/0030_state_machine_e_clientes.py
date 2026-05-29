"""State machine + campos de cliente para fluxo WhatsApp — Story 13.22.

Revision ID: 0030
Revises: 0029
Create Date: 2026-05-28

Acrescenta:
- `cobranca.conversas.estado_maquina` (varchar, default `idle`)
- `cobranca.conversas.aguardando_comprovante_ate` (timestamptz, null)
  → Story 13.23 usa para identificar mídia inbound como comprovante.
- `cobranca.conversas.confirmacao_recebimento_em` (timestamptz, null)
  → Story 13.25 usa para adiar lembrete quando cliente confirma.
- `cobranca.conversas.confirmacao_recebimento_titulo_id` (uuid, null).
- `cadastro.clientes.na_blacklist_comprovantes` (boolean, default false)
- `cadastro.clientes.motivo_blacklist` (text)
- `cadastro.clientes.adiamentos_usados_no_periodo` (integer, default 0)
- `cadastro.clientes.desbloqueios_confianca_usados_no_periodo` (integer, default 0)
- `cadastro.clientes.inicio_periodo_acoes` (date, null) — reset automático
  por worker de limpeza.
"""

from alembic import op


revision = "0030"
down_revision = "0029"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversas ─────────────────────────────────────────────
    op.execute("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS estado_maquina VARCHAR(40)
            NOT NULL DEFAULT 'idle'
    """)
    op.execute("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS aguardando_comprovante_ate TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS confirmacao_recebimento_em TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE cobranca.conversas
        ADD COLUMN IF NOT EXISTS confirmacao_recebimento_titulo_id UUID
            REFERENCES financeiro.titulos_receber(id) ON DELETE SET NULL
    """)

    # ── clientes ──────────────────────────────────────────────
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS na_blacklist_comprovantes BOOLEAN
            NOT NULL DEFAULT false
    """)
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS motivo_blacklist TEXT
    """)
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS adiamentos_usados_no_periodo INTEGER
            NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS desbloqueios_confianca_usados_no_periodo INTEGER
            NOT NULL DEFAULT 0
    """)
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS inicio_periodo_acoes DATE
    """)


def downgrade() -> None:
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS inicio_periodo_acoes")
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS desbloqueios_confianca_usados_no_periodo")
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS adiamentos_usados_no_periodo")
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS motivo_blacklist")
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS na_blacklist_comprovantes")
    op.execute("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS confirmacao_recebimento_titulo_id")
    op.execute("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS confirmacao_recebimento_em")
    op.execute("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS aguardando_comprovante_ate")
    op.execute("ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS estado_maquina")
