"""Permite múltiplas credenciais por empresa+categoria+provedor — Story 13.21.

Revision ID: 0029
Revises: 0028
Create Date: 2026-05-28

A constraint original `uq_credenciais_empresa_categoria_provedor` impede uma
empresa de ter 2+ números de WhatsApp do mesmo provedor (Evolution Go).
Como múltiplos números por empresa é requisito explícito (redundância contra
banimento + distribuição de carga), substituímos a unique por:

    UNIQUE (empresa_id, categoria, provedor, COALESCE(config->>'instance_id', '__single__'))

Categorias single-instance (FIPE, BCB) não usam `config->>'instance_id'`
→ fallback `'__single__'` → mantém comportamento antigo (1 row por empresa).

Categorias multi-instance (Evolution Go) preenchem `instance_id` no JSONB
→ cada instância vira uma linha distinta.
"""

from alembic import op


revision = "0029"
down_revision = "0028"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        ALTER TABLE config.credenciais_integracao
        DROP CONSTRAINT IF EXISTS uq_credenciais_empresa_categoria_provedor
    """)
    # Reaplica como índice único com expressão (PostgreSQL não aceita expressão
    # dentro de constraint, mas aceita índice único — equivalente funcional).
    op.execute("""
        CREATE UNIQUE INDEX uq_credenciais_empresa_categoria_provedor_instance
        ON config.credenciais_integracao (
            empresa_id,
            categoria,
            provedor,
            COALESCE(config->>'instance_id', '__single__')
        )
    """)


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS config.uq_credenciais_empresa_categoria_provedor_instance")
    op.execute("""
        ALTER TABLE config.credenciais_integracao
        ADD CONSTRAINT uq_credenciais_empresa_categoria_provedor
        UNIQUE (empresa_id, categoria, provedor)
    """)
