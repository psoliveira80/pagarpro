"""Adapter Evolution Go + multi-número com atribuição estável — Story 13.21.

Revision ID: 0028
Revises: 0027
Create Date: 2026-05-28

Adiciona infraestrutura para:
- Múltiplos números de WhatsApp por empresa (modelo "topologia A": provedor SaaS
  hospeda 1 Evolution Go central; cada empresa tem 1+ instâncias dentro dele).
- Atribuição estável de cliente a um número (cliente só migra se número for banido).
- Distribuição de carga (cliente novo vai para o número com menor contagem).

Mudanças:
- `cobranca.mensagens` ganha `numero_origem_id` (FK opcional para
  `config.credenciais_integracao`) — qual número da empresa enviou/recebeu.
- `cadastro.clientes` ganha `numero_origem_id` (FK opcional) — número fixo
  atribuído ao cliente.

A categoria nova de integração é `whatsapp_evolution_go` e o JSONB `config`
armazena: instance_id, instance_token, numero_e164, eh_principal,
status_whatsapp, motivo_banimento, ultimo_health_check.
"""

from alembic import op


revision = "0028"
down_revision = "0027"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── cobranca.mensagens: numero_origem_id ───────────────────────────
    op.execute("""
        ALTER TABLE cobranca.mensagens
        ADD COLUMN IF NOT EXISTS numero_origem_id UUID
            REFERENCES config.credenciais_integracao(id) ON DELETE SET NULL
    """)
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_mensagens_numero_origem
            ON cobranca.mensagens (numero_origem_id)
            WHERE numero_origem_id IS NOT NULL
    """)

    # ── cadastro.clientes: numero_origem_id ────────────────────────────
    op.execute("""
        ALTER TABLE cadastro.clientes
        ADD COLUMN IF NOT EXISTS numero_origem_id UUID
            REFERENCES config.credenciais_integracao(id) ON DELETE SET NULL
    """)
    # Índice usado pelo algoritmo de balanceamento (contagem de clientes por número).
    op.execute("""
        CREATE INDEX IF NOT EXISTS idx_clientes_numero_origem
            ON cadastro.clientes (empresa_id, numero_origem_id)
            WHERE numero_origem_id IS NOT NULL AND excluido_em IS NULL
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS cadastro.idx_clientes_numero_origem")
    op.execute("ALTER TABLE cadastro.clientes DROP COLUMN IF EXISTS numero_origem_id")
    op.execute("DROP INDEX IF EXISTS cobranca.idx_mensagens_numero_origem")
    op.execute("ALTER TABLE cobranca.mensagens DROP COLUMN IF EXISTS numero_origem_id")
