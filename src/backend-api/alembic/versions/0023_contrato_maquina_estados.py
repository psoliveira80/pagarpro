"""Máquina de estados do contrato — Story 13.2.

Revision ID: 0023
Revises: 0022
Create Date: 2026-05-27

Adiciona colunas `suspenso_em` e `motivo_suspensao` à tabela `contrato.contratos`
e introduz CHECK constraint validando o `status` contra os 8 estados do enum
`SituacaoContrato`.

Migração de dados legados:
- `encerrado` → `encerrado_sem_pendencia` (default seguro — preserva semântica
  de "terminou sem pendência" que era o uso mais comum).
- `ativo` → `vigente` (caso algum registro tenha sido criado com nome alternativo).

Nomenclatura: mantemos `status` (já em uso) em vez de renomear para `situacao`
para evitar churn em ~10 routes + tests que referenciam a coluna pelo nome.
"""

from alembic import op


revision = "0023"
down_revision = "0022"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1) Adiciona colunas auxiliares
    op.execute("""
        ALTER TABLE contrato.contratos
        ADD COLUMN IF NOT EXISTS suspenso_em TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE contrato.contratos
        ADD COLUMN IF NOT EXISTS motivo_suspensao VARCHAR(255)
    """)

    # 2) Normaliza status legados para os 8 estados oficiais
    op.execute("""
        UPDATE contrato.contratos SET status = 'encerrado_sem_pendencia'
        WHERE status = 'encerrado'
    """)
    op.execute("""
        UPDATE contrato.contratos SET status = 'vigente'
        WHERE status = 'ativo'
    """)

    # 3) CHECK constraint validando os 8 estados
    op.execute("""
        ALTER TABLE contrato.contratos
        ADD CONSTRAINT ck_contrato_status_valido CHECK (
            status IN (
                'rascunho',
                'vigente',
                'suspenso',
                'encerrado_sem_pendencia',
                'encerrado_com_pendencia',
                'encerrado_compra',
                'rescindido',
                'cancelado'
            )
        )
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE contrato.contratos
        DROP CONSTRAINT IF EXISTS ck_contrato_status_valido
    """)
    op.execute("""
        ALTER TABLE contrato.contratos
        DROP COLUMN IF EXISTS motivo_suspensao
    """)
    op.execute("""
        ALTER TABLE contrato.contratos
        DROP COLUMN IF EXISTS suspenso_em
    """)
    # Reverte os UPDATEs do upgrade — perde info de subtipo de encerramento
    op.execute("""
        UPDATE contrato.contratos SET status = 'encerrado'
        WHERE status IN ('encerrado_sem_pendencia', 'encerrado_com_pendencia', 'encerrado_compra')
    """)
