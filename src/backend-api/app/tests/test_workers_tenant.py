"""Testes para os workers refatorados na story 12-6.

Cobre:
- `dispatch_por_empresa`: dispara child task uma vez por empresa ativa,
  pula inativas.
- `gerar_despesas_recorrentes`: cria `TituloPagar` com `status='rascunho'`,
  é idempotente (avança `proxima_geracao_em`), e respeita isolamento
  tenant (não cria nada quando empresa_id passado não tem template).
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.infrastructure.db.session import get_engine
from app.workers.dispatcher import _listar_empresas_ativas, dispatch_por_empresa
from app.workers.tasks.gerar_despesas_recorrentes import _run as run_gerar_despesas

TEST_EMAIL_DESP = "worker-desp-test@example.com"


# ─── dispatch_por_empresa ──────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_listar_empresas_ativas_filtra_inativas():
    """O orquestrador só deve listar empresas com ativo=true."""
    engine = get_engine()
    empresa_extra_id = str(uuid4())
    empresa_inativa_id = str(uuid4())

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO comercial.empresas "
                "(id, razao_social, cnpj, email, ativo) "
                "VALUES (:id, 'Tester Extra', :cnpj, 'extra@test.com', true)"
            ),
            {"id": empresa_extra_id, "cnpj": f"99{empresa_extra_id[:12].replace('-', '')}"},
        )
        await conn.execute(
            text(
                "INSERT INTO comercial.empresas "
                "(id, razao_social, cnpj, email, ativo) "
                "VALUES (:id, 'Tester Inativa', :cnpj, 'inativa@test.com', false)"
            ),
            {"id": empresa_inativa_id, "cnpj": f"88{empresa_inativa_id[:12].replace('-', '')}"},
        )

    try:
        ids = await _listar_empresas_ativas()
        assert empresa_extra_id in ids, "empresa ativa não foi listada"
        assert empresa_inativa_id not in ids, "empresa inativa foi listada — vazamento"
    finally:
        async with engine.begin() as conn:
            await conn.execute(
                text("DELETE FROM comercial.empresas WHERE id IN (:a, :b)"),
                {"a": empresa_extra_id, "b": empresa_inativa_id},
            )


def test_dispatch_por_empresa_envia_send_task_por_id():
    """Wrapper da task Celery: para cada id retornado, chama send_task uma vez."""
    fake_ids = ["aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa", "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"]

    with patch(
        "app.workers.dispatcher._listar_empresas_ativas",
        new=AsyncMock(return_value=fake_ids),
    ), patch("app.workers.dispatcher.celery_app.send_task") as mock_send:
        resultado = dispatch_por_empresa("app.workers.tasks.fake.executar")

    assert resultado == {"dispatched": 2, "failed": 0, "skipped": 0}
    assert mock_send.call_count == 2
    args_passados = {tuple(call.kwargs.get("args", [])) for call in mock_send.call_args_list}
    assert (fake_ids[0],) in args_passados
    assert (fake_ids[1],) in args_passados


# ─── gerar_despesas_recorrentes ────────────────────────────────────────────


async def _criar_template_recorrente(
    user_id: str,
    empresa_id: str,
    descricao: str,
    proxima: date,
    valor: Decimal,
) -> str:
    """Cria um DespesaRecorrente template no DB e retorna o id."""
    template_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        # Pre-cleanup do usuário teste
        for tbl in ("financeiro.titulos_pagar", "financeiro.despesas_recorrentes"):
            await conn.execute(
                text(
                    f"UPDATE {tbl} SET criado_por_id = NULL "
                    f"WHERE criado_por_id IN (SELECT id FROM acesso.usuarios WHERE email = :e)"
                ),
                {"e": TEST_EMAIL_DESP},
            )
        await conn.execute(
            text("DELETE FROM acesso.usuarios WHERE email = :e"),
            {"e": TEST_EMAIL_DESP},
        )
        await conn.execute(
            text(
                "INSERT INTO acesso.usuarios "
                "(id, email, senha_hash, nome_completo, ativo, mfa_ativo, empresa_id) "
                "VALUES (:id, :email, 'x', 'Desp Tester', true, false, :eid)"
            ),
            {"id": user_id, "email": TEST_EMAIL_DESP, "eid": empresa_id},
        )
        await conn.execute(
            text(
                "INSERT INTO financeiro.despesas_recorrentes "
                "(id, empresa_id, descricao, valor, periodicidade, dia_do_mes, "
                " data_inicio, ativo, proxima_geracao_em, criado_por_id) "
                "VALUES (:id, :eid, :desc, :val, 'mensal', :dom, "
                " :di, true, :prox, :uid)"
            ),
            {
                "id": template_id,
                "eid": empresa_id,
                "desc": descricao,
                "val": valor,
                "dom": proxima.day,
                "di": date(2026, 1, 1),
                "prox": proxima,
                "uid": user_id,
            },
        )
    return template_id


async def _cleanup_template(template_id: str, user_id: str) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(
            text(
                "DELETE FROM financeiro.titulos_pagar WHERE template_id = :id"
            ),
            {"id": template_id},
        )
        await conn.execute(
            text("DELETE FROM financeiro.despesas_recorrentes WHERE id = :id"),
            {"id": template_id},
        )
        for tbl in ("financeiro.titulos_pagar", "financeiro.despesas_recorrentes"):
            await conn.execute(
                text(
                    f"UPDATE {tbl} SET criado_por_id = NULL WHERE criado_por_id = :uid"
                ),
                {"uid": user_id},
            )
        await conn.execute(
            text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable")
        )
        await conn.execute(
            text("UPDATE logs.log_auditoria SET user_id = NULL WHERE user_id = :uid"),
            {"uid": user_id},
        )
        await conn.execute(
            text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable")
        )
        await conn.execute(
            text("DELETE FROM acesso.usuarios WHERE id = :uid"), {"uid": user_id}
        )


@pytest.mark.asyncio
async def test_gerar_despesas_recorrentes_cria_titulo_rascunho_e_avanca_data():
    """Caminho feliz: cria TituloPagar com status='rascunho' e avança template."""
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None
        empresa_id = str(empresa_row[0])

    hoje = date.today()
    template_id = await _criar_template_recorrente(
        user_id, empresa_id, "Aluguel garagem", hoje, Decimal("1500.00")
    )

    try:
        sumario = await run_gerar_despesas(UUID(empresa_id))
        assert sumario["generated"] == 1

        async with engine.begin() as conn:
            titulo = (
                await conn.execute(
                    text(
                        "SELECT status, valor, data_vencimento "
                        "FROM financeiro.titulos_pagar WHERE template_id = :id"
                    ),
                    {"id": template_id},
                )
            ).one()
            tpl_row = (
                await conn.execute(
                    text(
                        "SELECT proxima_geracao_em FROM financeiro.despesas_recorrentes "
                        "WHERE id = :id"
                    ),
                    {"id": template_id},
                )
            ).one()

        assert titulo.status == "rascunho"
        assert titulo.valor == Decimal("1500.00")
        assert titulo.data_vencimento == hoje
        # Template avançou pra próximo mês (mesmo dia).
        assert tpl_row.proxima_geracao_em > hoje

        # Idempotência: re-rodar não cria duplicata.
        sumario2 = await run_gerar_despesas(UUID(empresa_id))
        assert sumario2["generated"] == 0

        async with engine.begin() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM financeiro.titulos_pagar "
                        "WHERE template_id = :id"
                    ),
                    {"id": template_id},
                )
            ).scalar_one()
        assert count == 1
    finally:
        await _cleanup_template(template_id, user_id)


@pytest.mark.asyncio
async def test_gerar_despesas_recorrentes_isola_por_empresa():
    """Passar empresa_id diferente não gera títulos do template da empresa real."""
    user_id = str(uuid4())
    engine = get_engine()
    async with engine.begin() as conn:
        empresa_row = (await conn.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
        assert empresa_row is not None
        empresa_real = str(empresa_row[0])

    hoje = date.today()
    template_id = await _criar_template_recorrente(
        user_id, empresa_real, "Internet", hoje, Decimal("200.00")
    )

    # UUID válido mas que não tem template — simulando outro tenant.
    empresa_fake = uuid4()

    try:
        sumario = await run_gerar_despesas(empresa_fake)
        assert sumario["generated"] == 0

        async with engine.begin() as conn:
            count = (
                await conn.execute(
                    text(
                        "SELECT COUNT(*) FROM financeiro.titulos_pagar "
                        "WHERE template_id = :id"
                    ),
                    {"id": template_id},
                )
            ).scalar_one()
        # Nenhum título criado porque o filtro `empresa_id = empresa_fake` exclui
        # o template da empresa real.
        assert count == 0
    finally:
        await _cleanup_template(template_id, user_id)
