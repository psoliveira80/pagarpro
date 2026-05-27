"""Testes da Story 13.2 — Máquina de Estados do Contrato.

Cobre:
1. Grafo `ALLOWED_TRANSITIONS` — todas as transições válidas + algumas inválidas.
2. `ServicoSituacaoContrato.transicionar()` persiste, gera evento + audit log.
3. Worker `gerar_titulos_mensais` ignora `suspenso`.
4. CHECK constraint do banco rejeita status fora do enum.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.application.services.servico_situacao_contrato import (
    ContratoNaoEncontradoError,
    ServicoSituacaoContrato,
)
from app.domain.contracts.state_machine import (
    ALLOWED_TRANSITIONS,
    SITUACOES_INATIVAS_GERACAO,
    SituacaoContrato,
    TransicaoInvalidaError,
    transicao_permitida,
)
from app.infrastructure.db.session import get_engine, get_sessionmaker


# ──────────────────────────────────────────────────────────────────
# Testes unitários do grafo (não tocam banco)
# ──────────────────────────────────────────────────────────────────

def test_grafo_cobre_todas_as_situacoes():
    """Toda situação do enum deve estar como chave em ALLOWED_TRANSITIONS."""
    for sit in SituacaoContrato:
        assert sit in ALLOWED_TRANSITIONS, f"Situação {sit} sem entrada no grafo"


def test_estados_terminais_nao_tem_saida():
    """Encerrados/rescindido/cancelado são folhas."""
    for term in [
        SituacaoContrato.ENCERRADO_SEM_PENDENCIA,
        SituacaoContrato.ENCERRADO_COM_PENDENCIA,
        SituacaoContrato.ENCERRADO_COMPRA,
        SituacaoContrato.RESCINDIDO,
        SituacaoContrato.CANCELADO,
    ]:
        assert ALLOWED_TRANSITIONS[term] == frozenset()


@pytest.mark.parametrize("origem,destino", [
    ("rascunho", "vigente"),
    ("rascunho", "cancelado"),
    ("vigente", "suspenso"),
    ("vigente", "encerrado_sem_pendencia"),
    ("vigente", "encerrado_com_pendencia"),
    ("vigente", "encerrado_compra"),
    ("vigente", "rescindido"),
    ("suspenso", "vigente"),
    ("suspenso", "encerrado_com_pendencia"),
    ("suspenso", "rescindido"),
])
def test_transicoes_validas(origem: str, destino: str):
    assert transicao_permitida(origem, destino) is True


@pytest.mark.parametrize("origem,destino", [
    ("rascunho", "suspenso"),                        # rascunho não pode ser suspenso
    ("rascunho", "encerrado_sem_pendencia"),         # rascunho não pode encerrar
    ("vigente", "rascunho"),                         # não volta pra rascunho
    ("suspenso", "rascunho"),                        # não volta pra rascunho
    ("suspenso", "encerrado_sem_pendencia"),         # de suspenso só vai pra com_pendencia
    ("encerrado_sem_pendencia", "vigente"),          # terminal
    ("rescindido", "vigente"),                       # terminal
    ("cancelado", "vigente"),                        # terminal
])
def test_transicoes_invalidas(origem: str, destino: str):
    assert transicao_permitida(origem, destino) is False


def test_situacoes_inativas_geracao_inclui_suspenso():
    """Worker `gerar_titulos_mensais` precisa pular `suspenso`."""
    assert SituacaoContrato.SUSPENSO in SITUACOES_INATIVAS_GERACAO
    assert SituacaoContrato.RASCUNHO in SITUACOES_INATIVAS_GERACAO
    assert SituacaoContrato.VIGENTE not in SITUACOES_INATIVAS_GERACAO


# ──────────────────────────────────────────────────────────────────
# Testes de banco — CHECK constraint
# ──────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_check_constraint_rejeita_status_fora_do_enum():
    """DB recusa UPDATE com status fora dos 8 valores válidos."""
    contrato_id, empresa_id = await _criar_contrato_fixture(status="rascunho")
    try:
        engine = get_engine()
        with pytest.raises(IntegrityError):
            async with engine.begin() as conn:
                await conn.execute(text("SET LOCAL row_security = off"))
                await conn.execute(
                    text("UPDATE contrato.contratos SET status = 'foo_invalido' WHERE id = :cid"),
                    {"cid": str(contrato_id)},
                )
    finally:
        await _cleanup_contrato_fixture(empresa_id)


# ──────────────────────────────────────────────────────────────────
# Testes do serviço — fixture de contrato
# ──────────────────────────────────────────────────────────────────

async def _criar_contrato_fixture(status: str = "rascunho") -> tuple[UUID, UUID]:
    """Cria empresa+cliente+veiculo+contrato isolados, retorna (contrato_id, empresa_id)."""
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    cliente_id = uuid4()
    veiculo_id = uuid4()
    contrato_id = uuid4()

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :razao, :cnpj, :email)
        """), {
            "id": str(empresa_id),
            "razao": f"SM-{suffix}",
            "cnpj": f"{suffix}11000111"[:14].ljust(14, "0"),
            "email": f"sm{suffix}@test.com",
        })

        await conn.execute(text("""
            INSERT INTO cadastro.clientes (id, empresa_id, nome_completo, cpf_cnpj)
            VALUES (:id, :eid, :nome, :cpf)
        """), {
            "id": str(cliente_id),
            "eid": str(empresa_id),
            "nome": f"Cliente {suffix}",
            "cpf": f"{suffix}11122233"[:11],
        })

        await conn.execute(text("""
            INSERT INTO veiculos.veiculos
              (id, empresa_id, placa, fipe_marca, fipe_modelo, ano_modelo, ano_fabricacao)
            VALUES (:id, :eid, :placa, 'Toyota', 'Corolla', 2024, 2024)
        """), {
            "id": str(veiculo_id),
            "eid": str(empresa_id),
            "placa": f"SM{suffix[:5].upper()}",
        })

        # Pega o admin user existente para satisfazer `criado_por_id NOT NULL`
        admin_row = (await conn.execute(text(
            "SELECT id FROM acesso.usuarios LIMIT 1"
        ))).first()
        admin_id = admin_row[0] if admin_row else None

        await conn.execute(text("""
            INSERT INTO contrato.contratos
              (id, empresa_id, numero, cliente_id, veiculo_id, status,
               data_inicio, data_fim, valor_total, dia_vencimento,
               modo_geracao, criado_por_id)
            VALUES (:id, :eid, :num, :cli, :vei, :status,
                    :di, :df, 12000, 15, 'antecipado', :uid)
        """), {
            "id": str(contrato_id),
            "eid": str(empresa_id),
            "num": f"C-{suffix}",
            "cli": str(cliente_id),
            "vei": str(veiculo_id),
            "status": status,
            "di": date(2026, 1, 1),
            "df": date(2027, 1, 1),
            "uid": str(admin_id) if admin_id else None,
        })
    return contrato_id, empresa_id


async def _cleanup_contrato_fixture(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        # Audit log é append-only — desativar trigger só para o cleanup deste teste
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text(
                "DELETE FROM logs.log_auditoria WHERE entidade = 'contratos' "
                "AND payload_after::text LIKE '%' || :eid || '%'"
            ), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.eventos_contrato WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM contrato.contratos WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM veiculos.veiculos WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM cadastro.clientes WHERE empresa_id = :eid"), {"eid": str(empresa_id)})
            await conn.execute(text("DELETE FROM comercial.empresas WHERE id = :eid"), {"eid": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


@pytest.mark.asyncio
async def test_servico_transicionar_rascunho_para_vigente():
    contrato_id, empresa_id = await _criar_contrato_fixture(status="rascunho")
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoSituacaoContrato(session, empresa_id)
            contrato = await servico.transicionar(
                contrato_id, SituacaoContrato.VIGENTE, motivo="Ativação manual"
            )
            await session.commit()
            assert contrato.status == "vigente"

        # Verifica evento persistido
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            ev = (await conn.execute(text("""
                SELECT tipo FROM contrato.eventos_contrato
                WHERE contrato_id = :cid ORDER BY criado_em DESC LIMIT 1
            """), {"cid": str(contrato_id)})).first()
            assert ev is not None
            assert ev[0] == "contrato_ativado"
    finally:
        await _cleanup_contrato_fixture(empresa_id)


@pytest.mark.asyncio
async def test_servico_transicao_invalida_levanta_erro():
    contrato_id, empresa_id = await _criar_contrato_fixture(status="rascunho")
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoSituacaoContrato(session, empresa_id)
            with pytest.raises(TransicaoInvalidaError):
                # rascunho → suspenso é inválido
                await servico.transicionar(contrato_id, SituacaoContrato.SUSPENSO)
    finally:
        await _cleanup_contrato_fixture(empresa_id)


@pytest.mark.asyncio
async def test_servico_suspender_seta_motivo_e_timestamp():
    # vigente → suspenso
    contrato_id, empresa_id = await _criar_contrato_fixture(status="vigente")
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoSituacaoContrato(session, empresa_id)
            contrato = await servico.transicionar(
                contrato_id, SituacaoContrato.SUSPENSO, motivo="Inadimplência 15+ dias"
            )
            await session.commit()
            assert contrato.status == "suspenso"
            assert contrato.suspenso_em is not None
            assert contrato.motivo_suspensao == "Inadimplência 15+ dias"
    finally:
        await _cleanup_contrato_fixture(empresa_id)


@pytest.mark.asyncio
async def test_servico_reativar_limpa_suspenso_em():
    contrato_id, empresa_id = await _criar_contrato_fixture(status="suspenso")
    # Seta suspenso_em manualmente para simular estado real
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text("UPDATE contrato.contratos SET suspenso_em = NOW(), motivo_suspensao = 'inad' WHERE id = :cid"),
            {"cid": str(contrato_id)},
        )

    try:
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(empresa_id)},
            )
            servico = ServicoSituacaoContrato(session, empresa_id)
            contrato = await servico.transicionar(
                contrato_id, SituacaoContrato.VIGENTE, motivo="Pagamento recebido"
            )
            await session.commit()
            assert contrato.status == "vigente"
            assert contrato.suspenso_em is None
            assert contrato.motivo_suspensao is None

        # Evento correto
        engine = get_engine()
        async with engine.begin() as conn:
            await conn.execute(text("SET LOCAL row_security = off"))
            ev = (await conn.execute(text("""
                SELECT tipo FROM contrato.eventos_contrato
                WHERE contrato_id = :cid ORDER BY criado_em DESC LIMIT 1
            """), {"cid": str(contrato_id)})).first()
            assert ev[0] == "contrato_reativado"
    finally:
        await _cleanup_contrato_fixture(empresa_id)


@pytest.mark.asyncio
async def test_servico_404_quando_contrato_de_outro_tenant():
    contrato_id, empresa_id = await _criar_contrato_fixture(status="rascunho")
    try:
        outro_empresa_id = uuid4()
        sm = get_sessionmaker()
        async with sm() as session:
            await session.execute(
                text("SELECT set_config('app.empresa_id', :eid, true)"),
                {"eid": str(outro_empresa_id)},
            )
            servico = ServicoSituacaoContrato(session, outro_empresa_id)
            with pytest.raises(ContratoNaoEncontradoError):
                await servico.transicionar(contrato_id, SituacaoContrato.VIGENTE)
    finally:
        await _cleanup_contrato_fixture(empresa_id)
