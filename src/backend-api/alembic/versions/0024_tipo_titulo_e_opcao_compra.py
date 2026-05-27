"""Tipo de Título e Opção de Compra — Story 13.3.

Revision ID: 0024
Revises: 0023
Create Date: 2026-05-27

Adiciona:
- Coluna `tipo` em `financeiro.titulos_receber` com CHECK constraint
  validando os 5 tipos (`parcela`, `opcao_compra`, `multa`, `taxa`,
  `ajuste`). A coluna já existia desde 0015 com default `'regular'`;
  esta migration normaliza para `'parcela'` e adiciona a CHECK.
- Colunas auxiliares `numero_parcela` (SMALLINT), `total_parcelas` (SMALLINT).
- Índice único parcial: apenas 1 título `opcao_compra` por contrato.
- Coluna `valor_opcao_compra` em `contrato.contratos` (NULLABLE — locação pura
  sem opção de compra fica NULL).
- Coluna `proprietario_id` em `veiculos.veiculos` (FK para clientes;
  preenchida pelo handler de OpcaoCompraPaga).
- Valor `alienado` aceito na coluna `status` de `veiculos.veiculos`
  (sem CHECK constraint nova — o domínio valida).

Não usa `CREATE TYPE` enum porque o modelo já usa `Text` + default; CHECK
constraint é mais simples de evoluir.
"""

from alembic import op


revision = "0024"
down_revision = "0023"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ───────────────────────────────────────────────────────────────
    # titulos_receber
    # ───────────────────────────────────────────────────────────────

    # Normaliza valores legados ('regular' → 'parcela')
    op.execute("""
        UPDATE financeiro.titulos_receber
        SET tipo = 'parcela'
        WHERE tipo = 'regular'
    """)

    # Default para parcela
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ALTER COLUMN tipo SET DEFAULT 'parcela'
    """)

    # CHECK constraint
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ADD CONSTRAINT ck_titulo_tipo_valido CHECK (
            tipo IN ('parcela', 'opcao_compra', 'multa', 'taxa', 'ajuste')
        )
    """)

    # Colunas auxiliares de numeração de parcelas
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ADD COLUMN IF NOT EXISTS numero_parcela SMALLINT
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ADD COLUMN IF NOT EXISTS total_parcelas SMALLINT
    """)

    # Único título de opção de compra por contrato (partial unique index)
    op.execute("""
        CREATE UNIQUE INDEX uniq_opcao_compra_por_contrato
        ON financeiro.titulos_receber (contrato_id)
        WHERE tipo = 'opcao_compra'
    """)

    # ───────────────────────────────────────────────────────────────
    # contratos
    # ───────────────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE contrato.contratos
        ADD COLUMN IF NOT EXISTS valor_opcao_compra NUMERIC(15, 2)
    """)

    # ───────────────────────────────────────────────────────────────
    # veiculos
    # ───────────────────────────────────────────────────────────────
    op.execute("""
        ALTER TABLE veiculos.veiculos
        ADD COLUMN IF NOT EXISTS proprietario_id UUID REFERENCES cadastro.clientes(id)
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE veiculos.veiculos DROP COLUMN IF EXISTS proprietario_id
    """)
    op.execute("""
        ALTER TABLE contrato.contratos DROP COLUMN IF EXISTS valor_opcao_compra
    """)
    op.execute("DROP INDEX IF EXISTS financeiro.uniq_opcao_compra_por_contrato")
    op.execute("""
        ALTER TABLE financeiro.titulos_receber DROP COLUMN IF EXISTS total_parcelas
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber DROP COLUMN IF EXISTS numero_parcela
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        DROP CONSTRAINT IF EXISTS ck_titulo_tipo_valido
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ALTER COLUMN tipo SET DEFAULT 'regular'
    """)
    op.execute("""
        UPDATE financeiro.titulos_receber
        SET tipo = 'regular'
        WHERE tipo = 'parcela'
    """)
