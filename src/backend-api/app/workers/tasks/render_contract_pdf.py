"""Celery task: render contract PDF with WeasyPrint + Jinja2, upload to MinIO."""

from __future__ import annotations

import io
import structlog
from datetime import datetime, timezone

from app.workers import celery_app

log = structlog.get_logger()

CONTRACT_HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="utf-8">
<style>
  body { font-family: Arial, sans-serif; font-size: 12px; margin: 40px; color: #333; }
  h1 { text-align: center; font-size: 18px; margin-bottom: 5px; }
  h2 { font-size: 14px; margin-top: 20px; border-bottom: 1px solid #999; padding-bottom: 4px; }
  .header { text-align: center; margin-bottom: 30px; }
  .header .contract-number { font-size: 14px; color: #666; }
  table { width: 100%; border-collapse: collapse; margin-top: 10px; }
  table th, table td { border: 1px solid #ccc; padding: 6px 8px; text-align: left; }
  table th { background: #f0f0f0; font-weight: bold; }
  .info-row { margin: 4px 0; }
  .info-label { font-weight: bold; display: inline-block; width: 160px; }
  .signatures { margin-top: 60px; display: flex; justify-content: space-between; }
  .sig-block { text-align: center; width: 40%; }
  .sig-line { border-top: 1px solid #333; margin-top: 60px; padding-top: 5px; }
  .clauses { white-space: pre-wrap; margin-top: 10px; }
  .footer { margin-top: 40px; text-align: center; font-size: 10px; color: #999; }
</style>
</head>
<body>
  <div class="header">
    <h1>CONTRATO DE PRESTAÇÃO DE SERVIÇOS</h1>
    <div class="contract-number">Contrato nº {{ contract.contract_number }}</div>
  </div>

  <h2>1. Partes</h2>
  <div class="info-row"><span class="info-label">Cliente:</span> {{ customer_name }}</div>
  <div class="info-row"><span class="info-label">Documento:</span> {{ customer_doc }}</div>

  <h2>2. Objeto</h2>
  <div class="info-row"><span class="info-label">Início:</span> {{ contract.start_date }}</div>
  <div class="info-row"><span class="info-label">Término:</span> {{ contract.end_date }}</div>
  <div class="info-row"><span class="info-label">Valor Total:</span> R$ {{ "%.2f"|format(contract.total_value) }}</div>

  {% if contract.clauses %}
  <h2>3. Cláusulas</h2>
  <div class="clauses">{{ contract.clauses }}</div>
  {% endif %}

  {% if contract.notes %}
  <h2>4. Observações</h2>
  <p>{{ contract.notes }}</p>
  {% endif %}

  <h2>5. Parcelas</h2>
  <table>
    <thead>
      <tr>
        <th>#</th>
        <th>Vencimento</th>
        <th>Valor (R$)</th>
        <th>Status</th>
      </tr>
    </thead>
    <tbody>
      {% for inst in installments %}
      <tr>
        <td>{{ inst.number }}</td>
        <td>{{ inst.due_date }}</td>
        <td>{{ "%.2f"|format(inst.current_value) }}</td>
        <td>{{ inst.status }}</td>
      </tr>
      {% endfor %}
    </tbody>
  </table>

  <div class="signatures">
    <div class="sig-block">
      <div class="sig-line">Contratante</div>
    </div>
    <div class="sig-block">
      <div class="sig-line">Contratado</div>
    </div>
  </div>

  <div class="footer">
    Documento gerado em {{ generated_at }} — Versão {{ version }}
  </div>
</body>
</html>
"""


@celery_app.task(name="app.workers.tasks.render_contract_pdf.render_contract_pdf", bind=True, max_retries=3)
def render_contract_pdf(self, contract_id: str) -> dict:  # type: ignore[no-untyped-def]
    """Render contract PDF synchronously (Celery worker context)."""
    import asyncio

    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(_render(contract_id))
    finally:
        loop.close()


async def _render(contract_id: str) -> dict:
    from uuid import UUID

    from jinja2 import Template
    from weasyprint import HTML
    import boto3
    from botocore.config import Config as BotoConfig
    from sqlalchemy import select, text
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.infrastructure.db.session import get_sessionmaker
    from app.infrastructure.db.models.contract import Contract, Installment
    from app.infrastructure.db.models.customer import Customer
    from app.infrastructure.settings import get_settings

    settings = get_settings()
    session_factory = get_sessionmaker()

    async with session_factory() as session:
        # Load contract
        result = await session.execute(
            select(Contract).where(Contract.id == UUID(contract_id))
        )
        contract = result.scalar_one_or_none()
        if not contract:
            raise ValueError(f"Contract {contract_id} not found")

        # Load customer
        cust_result = await session.execute(
            select(Customer).where(Customer.id == contract.customer_id)
        )
        customer = cust_result.scalar_one_or_none()
        customer_name = customer.nome_completo if customer else "N/A"
        customer_doc = customer.cpf_cnpj if customer else "N/A"

        # Load installments
        inst_result = await session.execute(
            select(Installment)
            .where(Installment.contract_id == contract.id)
            .order_by(Installment.number)
        )
        installments = list(inst_result.scalars().all())

        version = contract.pdf_version + 1

        # Render HTML
        template = Template(CONTRACT_HTML_TEMPLATE)
        html_content = template.render(
            contract=contract,
            customer_name=customer_name,
            customer_doc=customer_doc,
            installments=installments,
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            version=version,
        )

        # Generate PDF
        pdf_bytes = HTML(string=html_content).write_pdf()

        # Upload to MinIO
        s3_key = f"contracts/{contract_id}/contract_v{version}.pdf"
        s3 = boto3.client(
            "s3",
            endpoint_url=settings.S3_ENDPOINT_URL,
            aws_access_key_id=settings.S3_ACCESS_KEY,
            aws_secret_access_key=settings.S3_SECRET_KEY,
            region_name=settings.S3_REGION,
            config=BotoConfig(signature_version="s3v4"),
        )
        s3.put_object(
            Bucket=settings.S3_BUCKET,
            Key=s3_key,
            Body=pdf_bytes,
            ContentType="application/pdf",
        )
        s3.close()

        pdf_url = f"{settings.S3_ENDPOINT_URL}/{settings.S3_BUCKET}/{s3_key}"

        # Update contract
        contract.pdf_url = pdf_url
        contract.pdf_version = version
        await session.commit()

    log.info("contract_pdf_generated", contract_id=contract_id, version=version)
    return {"contract_id": contract_id, "pdf_url": pdf_url, "version": version}
