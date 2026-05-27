"""Observabilidade e idempotência dos motores — Story 13.5.

Revision ID: 0025
Revises: 0024
Create Date: 2026-05-27

Cria tabelas de observabilidade (`execucoes_motor`) e idempotência
(`lembretes_enviados`), além de colunas auxiliares em `titulos_receber`:

- `proxima_acao_em` — timestamp da próxima ação de cobrança permitida
  (motor 13.8 usa pra obedecer `intervalo_tentativas_horas`).
- `acoes_de_cobranca` — contador de tentativas já realizadas (motor 13.8
  para de cobrar quando atinge `limite_tentativas_cobranca`).

A idempotência principal continua sendo `SELECT FOR UPDATE SKIP LOCKED`
no Postgres + Redis lock pra coordenação entre workers em paralelo. Estas
tabelas adicionam: histórico de execução visível ao gestor e prevenção de
reenvio duplicado de mensagem no mesmo dia.

Schema escolhido: `motor` (novo, system-level — sem RLS) para execuções
agnósticas a tenant; `financeiro` para `lembretes_enviados` (tenant-scoped
via empresa_id).
"""

from alembic import op


revision = "0025"
down_revision = "0024"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE SCHEMA IF NOT EXISTS motor")

    # ── execucoes_motor: histórico observável de cada rodada ──
    op.execute("""
        CREATE TABLE motor.execucoes_motor (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            nome_tarefa     VARCHAR(100) NOT NULL,
            empresa_id      UUID REFERENCES comercial.empresas(id) ON DELETE SET NULL,
            iniciado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            finalizado_em   TIMESTAMPTZ,
            total_registros INTEGER NOT NULL DEFAULT 0,
            total_erros     INTEGER NOT NULL DEFAULT 0,
            situacao        VARCHAR(20) NOT NULL DEFAULT 'executando',
            detalhes        JSONB,

            CONSTRAINT ck_execucao_situacao CHECK (
                situacao IN ('executando', 'concluido', 'erro')
            )
        )
    """)
    op.execute("CREATE INDEX idx_execucao_nome_iniciado ON motor.execucoes_motor (nome_tarefa, iniciado_em DESC)")
    op.execute("CREATE INDEX idx_execucao_empresa_iniciado ON motor.execucoes_motor (empresa_id, iniciado_em DESC)")

    # RLS permissiva — admins de qualquer tenant veem execuções globais (NULL) + suas próprias.
    op.execute("ALTER TABLE motor.execucoes_motor ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE motor.execucoes_motor FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON motor.execucoes_motor
        USING (
            empresa_id IS NULL
            OR
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)

    # ── lembretes_enviados: idempotência por (titulo, tipo, dia) ──
    # A idempotência diária é garantida via índice ÚNICO sobre uma expressão
    # `DATE(enviado_em)`. A app verifica antes de inserir, e o índice é a
    # defesa em profundidade (race condition entre 2 workers).
    op.execute("""
        CREATE TABLE financeiro.lembretes_enviados (
            id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id  UUID NOT NULL REFERENCES comercial.empresas(id) ON DELETE CASCADE,
            titulo_id   UUID NOT NULL REFERENCES financeiro.titulos_receber(id) ON DELETE CASCADE,
            tipo        VARCHAR(30) NOT NULL,
            canal       VARCHAR(30) NOT NULL,
            enviado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            sucesso     BOOLEAN NOT NULL DEFAULT true,
            erro        TEXT
        )
    """)
    op.execute("CREATE UNIQUE INDEX uniq_lembrete_titulo_tipo_dia ON financeiro.lembretes_enviados (titulo_id, tipo, ((enviado_em AT TIME ZONE 'UTC')::date))")
    op.execute("CREATE INDEX idx_lembrete_titulo ON financeiro.lembretes_enviados (titulo_id, enviado_em DESC)")
    op.execute("CREATE INDEX idx_lembrete_empresa_data ON financeiro.lembretes_enviados (empresa_id, enviado_em DESC)")

    # RLS estrita
    op.execute("ALTER TABLE financeiro.lembretes_enviados ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE financeiro.lembretes_enviados FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON financeiro.lembretes_enviados
        USING (
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)

    # ── colunas auxiliares de cobrança em titulos_receber ──
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ADD COLUMN IF NOT EXISTS proxima_acao_em TIMESTAMPTZ
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber
        ADD COLUMN IF NOT EXISTS acoes_de_cobranca INTEGER NOT NULL DEFAULT 0
    """)


def downgrade() -> None:
    op.execute("""
        ALTER TABLE financeiro.titulos_receber DROP COLUMN IF EXISTS acoes_de_cobranca
    """)
    op.execute("""
        ALTER TABLE financeiro.titulos_receber DROP COLUMN IF EXISTS proxima_acao_em
    """)
    op.execute("DROP TABLE IF EXISTS financeiro.lembretes_enviados CASCADE")
    op.execute("DROP TABLE IF EXISTS motor.execucoes_motor CASCADE")
    op.execute("DROP SCHEMA IF EXISTS motor")
