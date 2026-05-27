"""Configurações tipadas — restructure `config.configuracoes_sistema`.

Revision ID: 0021
Revises: 0020
Create Date: 2026-05-27

Epic 13, Story 13.4 — Sistema de Configurações Tipadas.

A tabela `config.configuracoes_sistema` foi criada na 0015 com `chave` (Text)
+ `valor` (JSONB). Esta story restrutura para o modelo tipado do PRD:

    modulo VARCHAR(50)    -- ex.: 'financeiro', 'frota', 'comunicacao'
    slug   VARCHAR(100)   -- ex.: 'percentual_multa'
    tipo_valor VARCHAR(20) IN ('string','inteiro','decimal','booleano','json')
    valor  TEXT           -- serializado conforme tipo_valor (CHECK valida)

Benefícios:
- CHECK constraint no banco rejeita lixo (ex.: `tipo_valor='inteiro'` + `valor='abc'`).
- `empresa_id` agora é NULLABLE — NULL = default global do sistema, não-NULL = override por tenant.
- Filtragem por módulo é direta (índice composto `(empresa_id, modulo)`).

A tabela está vazia neste momento (verificado antes da migration), então
recriamos do zero. RLS é recriada para permitir leitura de configs globais
(empresa_id NULL) por qualquer tenant.
"""

from alembic import op


revision = "0021"
down_revision = "0020"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove a tabela antiga (vazia em dev) — recreate do zero é mais limpo
    # que ALTER em coluna JSONB → TEXT + adição de várias colunas.
    op.execute("DROP TABLE IF EXISTS config.configuracoes_sistema CASCADE")

    op.execute("""
        CREATE TABLE config.configuracoes_sistema (
            id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id      UUID REFERENCES comercial.empresas(id) ON DELETE CASCADE,
            modulo          VARCHAR(50)  NOT NULL,
            slug            VARCHAR(100) NOT NULL,
            tipo_valor      VARCHAR(20)  NOT NULL,
            valor           TEXT         NOT NULL,
            descricao       TEXT,
            atualizado_em   TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            atualizado_por_id UUID REFERENCES acesso.usuarios(id),

            CONSTRAINT uniq_config_empresa_slug UNIQUE (empresa_id, slug),

            CONSTRAINT ck_tipo_valor_aceito CHECK (
                tipo_valor IN ('string','inteiro','decimal','booleano','json')
            ),

            CONSTRAINT ck_valor_combina_com_tipo CHECK (
                (tipo_valor = 'inteiro'  AND valor ~ '^-?\\d+$')                    OR
                (tipo_valor = 'decimal'  AND valor ~ '^-?\\d+(\\.\\d+)?$')           OR
                (tipo_valor = 'booleano' AND valor IN ('true','false'))             OR
                (tipo_valor = 'string')                                             OR
                (tipo_valor = 'json'     AND valor::jsonb IS NOT NULL)
            )
        )
    """)

    op.execute("CREATE INDEX idx_config_modulo ON config.configuracoes_sistema(modulo)")
    op.execute("CREATE INDEX idx_config_empresa_modulo ON config.configuracoes_sistema(empresa_id, modulo)")

    # RLS — agora permissiva (lê configs globais NULL + configs do próprio tenant)
    op.execute("ALTER TABLE config.configuracoes_sistema ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE config.configuracoes_sistema FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON config.configuracoes_sistema
        USING (
            empresa_id IS NULL
            OR
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS config.configuracoes_sistema CASCADE")
    # Recreate na forma antiga (compat com 0015)
    op.execute("""
        CREATE TABLE config.configuracoes_sistema (
            id                UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
            empresa_id        UUID        NOT NULL REFERENCES comercial.empresas(id),
            chave             TEXT        NOT NULL,
            valor             JSONB       NOT NULL,
            descricao         TEXT,
            atualizado_por_id UUID        REFERENCES acesso.usuarios(id),
            atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (empresa_id, chave)
        )
    """)
    op.execute("ALTER TABLE config.configuracoes_sistema ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE config.configuracoes_sistema FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON config.configuracoes_sistema
        USING (
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)
