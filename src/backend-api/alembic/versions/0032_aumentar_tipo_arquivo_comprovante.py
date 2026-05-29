"""Aumenta financeiro.comprovantes_pagamento.tipo_arquivo varchar(20) → varchar(64).

Revision ID: 0032
Revises: 0031
Create Date: 2026-05-29

Auditoria 2026-05-29 (bug B8): comprovantes JPEG cujo MIME caiu em
`application/octet-stream` (24 chars) estouravam a constraint varchar(20).
Mesmo MIMEs legítimos como `image/jpeg; charset=binary` (28 chars) ou
PDFs anexados via WhatsApp com content-type estendido não cabiam. Subir
pra 64 cobre todos os casos reais e ainda deixa margem.
"""

import sqlalchemy as sa
from alembic import op


revision = "0032"
down_revision = "0031"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "comprovantes_pagamento",
        "tipo_arquivo",
        type_=sa.String(64),
        existing_type=sa.String(20),
        existing_nullable=True,
        schema="financeiro",
    )


def downgrade() -> None:
    op.alter_column(
        "comprovantes_pagamento",
        "tipo_arquivo",
        type_=sa.String(20),
        existing_type=sa.String(64),
        existing_nullable=True,
        schema="financeiro",
    )
