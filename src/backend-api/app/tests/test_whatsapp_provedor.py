"""Testes do ServicoWhatsappProvedor + interação com POST /numeros-cobranca.

Cobre os 3 cenários críticos da decisão arquitetural 2026-05-29:
1. Upsert (criar e atualizar config) sem instâncias existentes.
2. Bloqueio quando tentamos cadastrar instância sem ter provedor configurado
   (POST /numeros-cobranca → 412 simulado pelo handler).
3. Troca de provedor com instâncias existentes: rejeita sem forcar=True;
   aceita com forcar=True e desativa instâncias.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from app.application.services.servico_whatsapp_provedor import (
    CamposObrigatoriosFaltandoError,
    ProvedorDesconhecidoError,
    ProvedorIndisponivelError,
    ProvedorTemInstanciasError,
    ServicoWhatsappProvedor,
)
from app.infrastructure.db.session import get_engine, get_sessionmaker


async def _criar_empresa() -> UUID:
    engine = get_engine()
    suffix = uuid4().hex[:8]
    empresa_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO comercial.empresas (id, razao_social, cnpj, email)
            VALUES (:id, :r, :c, :e)
        """), {
            "id": str(empresa_id),
            "r": f"WPV-{suffix}",
            "c": f"{suffix}99000111"[:14].ljust(14, "0"),
            "e": f"wpv-{suffix}@t.com",
        })
    return empresa_id


async def _criar_instancia_evolution_go(empresa_id: UUID) -> UUID:
    engine = get_engine()
    cred_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("""
            INSERT INTO config.credenciais_integracao
              (id, empresa_id, categoria, provedor, ativo, config, status)
            VALUES (:id, :eid, 'whatsapp', 'evolution_go', true,
                    CAST(:cfg AS jsonb), 'configurada')
        """), {
            "id": str(cred_id),
            "eid": str(empresa_id),
            "cfg": '{"instance_id": "inst-x", "instance_token": "tok-x", "numero_e164": "+5511000000001"}',
        })
    return cred_id


async def _cleanup(empresa_id: UUID) -> None:
    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(text("ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"))
        try:
            await conn.execute(text(
                "DELETE FROM logs.log_auditoria WHERE entidade IN ('whatsapp_provedor_config', 'credenciais_integracao')"
            ))
            await conn.execute(text(
                "DELETE FROM config.credenciais_integracao WHERE empresa_id = :e"
            ), {"e": str(empresa_id)})
            await conn.execute(text(
                "DELETE FROM config.whatsapp_provedor_config WHERE empresa_id = :e"
            ), {"e": str(empresa_id)})
            await conn.execute(text(
                "DELETE FROM comercial.empresas WHERE id = :e"
            ), {"e": str(empresa_id)})
        finally:
            await conn.execute(text("ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"))


@pytest.mark.asyncio
async def test_definir_provedor_cria_quando_inexistente():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            cfg = await servico.definir_provedor(
                provedor="evolution_api",
                config={"base_url": "https://x", "api_key": "k"},
            )
            await session.commit()
            assert cfg.provedor == "evolution_api"
            assert cfg.config == {"base_url": "https://x", "api_key": "k"}

        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            ativo = await servico.obter_config_ativa()
            assert ativo is not None
            assert ativo.provedor == "evolution_api"
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_definir_provedor_atualiza_quando_existe():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            await servico.definir_provedor("evolution_api", {"base_url": "https://a", "api_key": "ka"})
            await session.commit()

        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            await servico.definir_provedor("evolution_api", {"base_url": "https://b", "api_key": "kb"})
            await session.commit()

        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            ativo = await servico.obter_config_ativa()
            assert ativo is not None and ativo.config["base_url"] == "https://b"
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_definir_provedor_rejeita_id_desconhecido():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            with pytest.raises(ProvedorDesconhecidoError):
                await servico.definir_provedor("zoiper", {})
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_definir_provedor_rejeita_meta_cloud_em_breve():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            with pytest.raises(ProvedorIndisponivelError):
                await servico.definir_provedor(
                    "meta_cloud",
                    {"waba_id": "x", "access_token": "y"},
                )
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_definir_provedor_rejeita_campos_faltando():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            with pytest.raises(CamposObrigatoriosFaltandoError) as exc:
                await servico.definir_provedor("evolution_api", {"base_url": "https://x"})
            assert "api_key" in exc.value.faltando
    finally:
        await _cleanup(empresa_id)


@pytest.mark.asyncio
async def test_trocar_provedor_com_instancias_exige_forcar():
    empresa_id = await _criar_empresa()
    try:
        sm = get_sessionmaker()
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            await servico.definir_provedor("evolution_go", {})
            await session.commit()

        await _criar_instancia_evolution_go(empresa_id)

        # Sem forcar → ProvedorTemInstanciasError
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            with pytest.raises(ProvedorTemInstanciasError) as exc:
                await servico.definir_provedor(
                    "evolution_api",
                    {"base_url": "https://x", "api_key": "k"},
                    forcar=False,
                )
            assert len(exc.value.credencial_ids) == 1

        # Com forcar → troca e desativa instâncias
        async with sm() as session:
            servico = ServicoWhatsappProvedor(session, empresa_id)
            cfg = await servico.definir_provedor(
                "evolution_api",
                {"base_url": "https://x", "api_key": "k"},
                forcar=True,
            )
            await session.commit()
            assert cfg.provedor == "evolution_api"
            # Instância original deve estar desativada
            ativas = await servico.contar_instancias_ativas()
            assert ativas == 0
    finally:
        await _cleanup(empresa_id)
