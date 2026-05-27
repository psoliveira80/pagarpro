"""Comprovantes de pagamento — Story 13.19.

Revision ID: 0026
Revises: 0025
Create Date: 2026-05-27

Tabela `financeiro.comprovantes_pagamento` armazena cada upload de
comprovante (imagem ou PDF) analisado pelo pipeline multi-camada
(BR Code → PDF texto → OCR PaddleOCR).

Idempotência por SHA-256 do arquivo: enviar 2× o mesmo arquivo retorna
o registro existente. RLS estrita por `empresa_id`.

Campos auditáveis (`texto_bruto_ocr`, `avisos`) registram o que o motor
extraiu — útil para gestor entender por que score ficou baixo.
"""

from alembic import op


revision = "0026"
down_revision = "0025"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
        CREATE TABLE financeiro.comprovantes_pagamento (
            id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            empresa_id               UUID NOT NULL REFERENCES comercial.empresas(id) ON DELETE CASCADE,
            titulo_id                UUID REFERENCES financeiro.titulos_receber(id) ON DELETE SET NULL,
            cliente_id               UUID REFERENCES cadastro.clientes(id) ON DELETE SET NULL,

            -- Storage do arquivo (S3/MinIO)
            arquivo_url              TEXT NOT NULL,
            arquivo_hash             VARCHAR(64) NOT NULL,  -- SHA-256 hex
            tipo_arquivo             VARCHAR(20) NOT NULL,  -- 'image/png', 'image/jpeg', 'application/pdf'
            tamanho_bytes            INTEGER,

            -- Resultado da análise
            metodo_analise           VARCHAR(20),           -- 'br_code'|'pdf_texto'|'ocr'|'ia'
            score_confianca          NUMERIC(3,2) NOT NULL DEFAULT 0.00 CHECK (score_confianca >= 0 AND score_confianca <= 1),
            valor_detectado          NUMERIC(15,2),
            data_detectada           TIMESTAMPTZ,
            pix_txid                 TEXT,
            pix_e2e_id               TEXT,
            banco_emissor            VARCHAR(50),
            beneficiario_cnpj        VARCHAR(20),
            beneficiario_nome        TEXT,
            pagador_nome             TEXT,
            pagador_documento        VARCHAR(20),
            chave_pix_usada          TEXT,
            texto_bruto_ocr          TEXT,                  -- auditoria — só quando metodo='ocr'
            avisos                   JSONB DEFAULT '[]',    -- array de strings com problemas detectados

            -- Status do comprovante
            status                   VARCHAR(30) NOT NULL DEFAULT 'analisado',
            homologado_por_id        UUID REFERENCES acesso.usuarios(id),
            homologado_em            TIMESTAMPTZ,
            rejeitado_por_id         UUID REFERENCES acesso.usuarios(id),
            rejeitado_em             TIMESTAMPTZ,
            motivo_rejeicao          TEXT,

            -- Origem
            origem                   VARCHAR(30) NOT NULL DEFAULT 'upload',  -- 'upload'|'whatsapp'|'email'
            telefone_remetente       VARCHAR(20),           -- quando origem='whatsapp'

            criado_em                TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            atualizado_em            TIMESTAMPTZ NOT NULL DEFAULT NOW(),

            CONSTRAINT ck_comprovante_status CHECK (
                status IN ('analisado', 'homologado', 'rejeitado', 'erro_analise')
            ),
            CONSTRAINT ck_comprovante_metodo CHECK (
                metodo_analise IS NULL OR metodo_analise IN ('br_code', 'pdf_texto', 'ocr', 'ia')
            ),
            CONSTRAINT ck_comprovante_origem CHECK (
                origem IN ('upload', 'whatsapp', 'email')
            )
        )
    """)

    # Idempotência: 1 hash por empresa.
    op.execute("""
        CREATE UNIQUE INDEX uniq_comprovante_empresa_hash
            ON financeiro.comprovantes_pagamento (empresa_id, arquivo_hash)
    """)

    # Lookups frequentes
    op.execute("""
        CREATE INDEX idx_comprovante_empresa_status
            ON financeiro.comprovantes_pagamento (empresa_id, status, criado_em DESC)
    """)
    op.execute("""
        CREATE INDEX idx_comprovante_titulo
            ON financeiro.comprovantes_pagamento (titulo_id)
            WHERE titulo_id IS NOT NULL
    """)
    op.execute("""
        CREATE INDEX idx_comprovante_e2e
            ON financeiro.comprovantes_pagamento (pix_e2e_id)
            WHERE pix_e2e_id IS NOT NULL
    """)

    # RLS estrita
    op.execute("ALTER TABLE financeiro.comprovantes_pagamento ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE financeiro.comprovantes_pagamento FORCE ROW LEVEL SECURITY")
    op.execute("""
        CREATE POLICY tenant_isolation ON financeiro.comprovantes_pagamento
        USING (
            empresa_id = NULLIF(
                current_setting('app.empresa_id', true), ''
            )::uuid
        )
    """)


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS financeiro.comprovantes_pagamento CASCADE")
