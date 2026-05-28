"""Matches de conciliação bancária — Story 13.20.

Revision ID: 0027
Revises: 0026
Create Date: 2026-05-28

Cria `conta_bancaria.matches_conciliacao` para registrar cada vínculo
aplicado entre uma transação bancária importada e um título a receber.
Permite **desfazer** em até 30 dias (auditoria + reabertura do título).

Adiciona colunas em `sessoes_conciliacao`:
- `nome_arquivo_origem`: nome do arquivo importado (extrato.ofx, etc.)
- `hash_arquivo`: SHA-256 do arquivo para idempotência (mesmo extrato 2×
  não cria sessão duplicada).
- `formato_origem`: 'ofx' | 'pdf' | 'csv'.

Cross-reference com Story 13.19: `comprovante_id` na transação permite
identificar quando um pagamento foi conciliado via comprovante PIX
antes de aparecer no extrato — evita dupla contagem.
"""

from alembic import op


revision = "0027"
down_revision = "0026"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Colunas extras em sessoes_conciliacao
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao
        ADD COLUMN IF NOT EXISTS nome_arquivo_origem TEXT
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao
        ADD COLUMN IF NOT EXISTS hash_arquivo VARCHAR(64)
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao
        ADD COLUMN IF NOT EXISTS formato_origem VARCHAR(10)
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao
        ADD CONSTRAINT ck_sessao_formato CHECK (
            formato_origem IS NULL OR formato_origem IN ('ofx', 'pdf', 'csv', 'manual')
        )
    """)
    # Idempotência: mesmo extrato (mesmo hash) na mesma conta = mesma sessão
    op.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS uniq_sessao_conta_hash
        ON conta_bancaria.sessoes_conciliacao (conta_id, hash_arquivo)
        WHERE hash_arquivo IS NOT NULL
    """)

    # Cross-reference com comprovantes da 13.19
    op.execute("""
        ALTER TABLE conta_bancaria.transacoes_bancarias
        ADD COLUMN IF NOT EXISTS comprovante_id UUID
            REFERENCES financeiro.comprovantes_pagamento(id) ON DELETE SET NULL
    """)

    # Tabela principal de matches
    op.execute("""
        CREATE TABLE conta_bancaria.matches_conciliacao (
            id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id          UUID NOT NULL REFERENCES comercial.empresas(id) ON DELETE CASCADE,
            sessao_id           UUID NOT NULL REFERENCES conta_bancaria.sessoes_conciliacao(id) ON DELETE CASCADE,
            transacao_id        UUID NOT NULL REFERENCES conta_bancaria.transacoes_bancarias(id) ON DELETE CASCADE,
            titulo_id           UUID NOT NULL REFERENCES financeiro.titulos_receber(id) ON DELETE CASCADE,
            score_match         NUMERIC(3,2) NOT NULL CHECK (score_match >= 0 AND score_match <= 1),
            motivo_match        TEXT,                  -- "valor exato + data exata + CNPJ"
            aplicado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            aplicado_por_id     UUID REFERENCES acesso.usuarios(id) ON DELETE SET NULL,
            desfeito_em         TIMESTAMPTZ,           -- NULL = match vigente
            desfeito_por_id     UUID REFERENCES acesso.usuarios(id) ON DELETE SET NULL,
            motivo_desfazer     TEXT,
            ja_existia_via_comprovante BOOLEAN NOT NULL DEFAULT false  -- cross-check 13.19
        )
    """)

    # 1 match vigente por transação (após desfeito_em fica liberado pra novo match)
    op.execute("""
        CREATE UNIQUE INDEX uniq_match_transacao_vigente
        ON conta_bancaria.matches_conciliacao (transacao_id)
        WHERE desfeito_em IS NULL
    """)
    op.execute("""
        CREATE INDEX idx_match_sessao
        ON conta_bancaria.matches_conciliacao (sessao_id, aplicado_em DESC)
    """)
    op.execute("""
        CREATE INDEX idx_match_titulo
        ON conta_bancaria.matches_conciliacao (titulo_id)
        WHERE desfeito_em IS NULL
    """)

    # RLS estrita
    op.execute("ALTER TABLE conta_bancaria.matches_conciliacao ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE conta_bancaria.matches_conciliacao FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON conta_bancaria.matches_conciliacao
        USING (
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS conta_bancaria.matches_conciliacao CASCADE")
    op.execute("""
        ALTER TABLE conta_bancaria.transacoes_bancarias DROP COLUMN IF EXISTS comprovante_id
    """)
    op.execute("DROP INDEX IF EXISTS conta_bancaria.uniq_sessao_conta_hash")
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao
        DROP CONSTRAINT IF EXISTS ck_sessao_formato
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao DROP COLUMN IF EXISTS formato_origem
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao DROP COLUMN IF EXISTS hash_arquivo
    """)
    op.execute("""
        ALTER TABLE conta_bancaria.sessoes_conciliacao DROP COLUMN IF EXISTS nome_arquivo_origem
    """)
