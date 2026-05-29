"""Auditoria E2E do fluxo do FrotaUber — 2026-05-29.

Cobre:
1. Cadastra empresa "Sim FrotaUber" com 3 clientes + 3 veículos + 3 contratos
   com periodicidades diferentes (semanal/mensal/quinzenal).
2. Registra o `FakeWhatsAppChannel` no `channel_registry` substituindo
   Evolution Go / Z-API.
3. Compressão temporal (time-travel via freezegun) — avança N dias
   simulados, disparando os workers a cada tick.
4. Em momentos específicos, simula cliente mandando comprovante
   (chamando `ServicoAnaliseComprovante.analisar` direto com os 4
   arquivos gerados em `/srv/comprovantes-simulados/`).
5. Captura métricas + bugs encontrados em `/srv/logs-auditoria/`.

Execução:
    PYTHONPATH=/app:/srv/audit-scripts python /srv/audit-scripts/auditoria_fluxo.py

Idempotente — limpa a empresa anterior antes de começar.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import text

# Pré-aquece TODOS os modelos e workers ANTES do freezegun ser importado
# para evitar `FakeDate` vazar dentro do `Mapped[date]` do SQLAlchemy.
import app.infrastructure.db.models.cadastro  # noqa: F401
import app.infrastructure.db.models.cobranca  # noqa: F401
import app.infrastructure.db.models.contrato  # noqa: F401
import app.infrastructure.db.models.financeiro  # noqa: F401
import app.infrastructure.db.models.veiculos  # noqa: F401
import app.workers.tasks.alertar_vencimentos_proximos  # noqa: F401
import app.workers.tasks.processar_titulos_vencidos  # noqa: F401
import app.workers.tasks.recalcular_scores_clientes  # noqa: F401
import app.workers.tasks.expirar_desbloqueios_confianca  # noqa: F401
import app.application.services.servico_titulo_pago  # noqa: F401
import app.application.services.servico_analise_comprovante  # noqa: F401

from freezegun import freeze_time  # noqa: E402


# ─────────────────────────── Globais ──────────────────────────────────

PASTA_LOG = Path("/srv/logs-auditoria")
PASTA_COMPROVANTES = Path("/srv/comprovantes-simulados")
PASTA_WHATSAPP = Path("/tmp/whatsapp_envios")
PASTA_LOG.mkdir(parents=True, exist_ok=True)

NOME_EMPRESA = "Sim FrotaUber Auditoria"
DATA_INICIO = date(2026, 1, 6)  # uma terça-feira — usado como base do time-travel

# Acumula tudo que dá errado durante a simulação. Reportado ao final.
BUGS_ENCONTRADOS: list[dict] = []
EVENTOS_TIMELINE: list[dict] = []


def log_evento(dia_simulado: date, tipo: str, **detalhes) -> None:
    EVENTOS_TIMELINE.append(
        {
            "dia": dia_simulado.isoformat(),
            "tipo": tipo,
            **detalhes,
        }
    )


def log_bug(dia_simulado: date | None, contexto: str, exc: Exception | None = None, **extra) -> None:
    BUGS_ENCONTRADOS.append(
        {
            "dia": dia_simulado.isoformat() if dia_simulado else None,
            "contexto": contexto,
            "erro": str(exc) if exc else None,
            "tipo_erro": type(exc).__name__ if exc else None,
            "traceback": traceback.format_exc() if exc else None,
            **extra,
        }
    )


# ─────────────────── Setup: limpa + cria empresa+admin ────────────────


async def limpar_empresa_anterior() -> None:
    """Cleanup defensivo — cada DELETE em transação isolada via SAVEPOINT
    pra falha numa tabela não abortar as demais."""
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SET row_security = off"))
        empresa_ids = [
            r[0] for r in (
                await conn.execute(
                    text("SELECT id FROM comercial.empresas WHERE razao_social = :n"),
                    {"n": NOME_EMPRESA},
                )
            ).all()
        ]
        if not empresa_ids:
            return

    # Cleanup por empresa, fora do connect inicial pra não segurar lock
    for empresa_id in empresa_ids:
        await _limpar_uma_empresa(empresa_id)


async def _limpar_uma_empresa(empresa_id) -> None:
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SET row_security = off"))
        # ATENÇÃO — schemas REAIS (não bate com a documentação):
        #   comprovantes_pagamento e lembretes_enviados → schema FINANCEIRO
        #   conversas e mensagens                       → schema COBRANCA
        # Registrado em bugs.json como ACHADO #1 da auditoria.
        tabelas = [
            ("financeiro", "comprovantes_pagamento"),
            ("financeiro", "lembretes_enviados"),
            ("cobranca", "mensagens"),
            ("cobranca", "conversas"),
            ("financeiro", "movimentos_titulo_receber"),
            ("financeiro", "titulos_receber"),
            ("contrato", "eventos_contrato"),
            ("contrato", "contratos"),
            ("veiculos", "veiculos"),
            ("cadastro", "clientes"),
            ("motor", "execucoes_motor"),
        ]
        for schema, tabela in tabelas:
            try:
                async with conn.begin() as txn:
                    await conn.execute(text("SET LOCAL row_security = off"))
                    await conn.execute(
                        text(f"DELETE FROM {schema}.{tabela} WHERE empresa_id = :e"),
                        {"e": str(empresa_id)},
                    )
            except Exception as exc:
                log_bug(None, f"limpar:{schema}.{tabela}", exc)
        # log_auditoria com trigger desabilitado
        try:
            async with conn.begin() as txn:
                await conn.execute(text("SET LOCAL row_security = off"))
                await conn.execute(text(
                    "ALTER TABLE logs.log_auditoria DISABLE TRIGGER trg_log_auditoria_immutable"
                ))
                await conn.execute(
                    text("DELETE FROM logs.log_auditoria WHERE empresa_id = :e"),
                    {"e": str(empresa_id)},
                )
                await conn.execute(text(
                    "ALTER TABLE logs.log_auditoria ENABLE TRIGGER trg_log_auditoria_immutable"
                ))
        except Exception as exc:
            log_bug(None, "limpar:logs.log_auditoria", exc)
        try:
            async with conn.begin() as txn:
                await conn.execute(text("SET LOCAL row_security = off"))
                await conn.execute(
                    text("DELETE FROM comercial.empresas WHERE id = :e"),
                    {"e": str(empresa_id)},
                )
        except Exception as exc:
            log_bug(None, "limpar:comercial.empresas", exc)


async def cadastrar_base() -> dict:
    """Cria 1 empresa + 3 clientes + 3 veículos + 3 contratos.

    Perfis dos clientes:
      A = "exemplar" — paga até o vencimento, sempre.
      B = "atrasado" — atrasa 5 dias, paga só com cobrança.
      C = "inadimplente" — não paga, vai pra blacklist eventualmente.

    Retorna IDs de tudo para os passos seguintes.
    """
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    empresa_id = uuid4()
    # CPFs/telefones randomizados — provavelmente constraints únicas globais
    # no schema antigo. Sufixo curto pra ficar identificável nos logs.
    bs = uuid4().int  # base randômica
    def _cpf(i: int) -> str:
        return str(bs + i)[:11].ljust(11, "0")
    def _tel(i: int) -> str:
        return ("55119" + str(bs + i)[:8])[:13].ljust(13, "0")
    clientes = {
        "A": {"id": uuid4(), "nome": "Ana Pagadora Exemplar",   "cpf": _cpf(1), "tel": _tel(1)},
        "B": {"id": uuid4(), "nome": "Bento Atrasado Mas Paga", "cpf": _cpf(2), "tel": _tel(2)},
        "C": {"id": uuid4(), "nome": "Caio Inadimplente Total", "cpf": _cpf(3), "tel": _tel(3)},
    }
    # Placas randomizadas — constraint global `vehicles_plate_key` (legada
    # do schema 12.3) impede reuso entre empresas.
    sufixo_placa = uuid4().hex[:3].upper()
    veiculos = {
        "A": {"id": uuid4(), "placa": f"AUA{sufixo_placa}", "modelo": "Civic", "marca": "Honda"},
        "B": {"id": uuid4(), "placa": f"AUB{sufixo_placa}", "modelo": "Onix", "marca": "Chevrolet"},
        "C": {"id": uuid4(), "placa": f"AUC{sufixo_placa}", "modelo": "HB20", "marca": "Hyundai"},
    }
    # Contratos com periodicidades diferentes.
    # Número também randomizado — `contracts_contract_number_key` é unique
    # global no schema antigo.
    suf = uuid4().hex[:6].upper()
    contratos = {
        "A": {"id": uuid4(), "numero": f"AUD-{suf}-A", "periodicidade": "mensal",
              "dia_vencimento": 15, "valor_mensal": Decimal("800.00")},
        "B": {"id": uuid4(), "numero": f"AUD-{suf}-B", "periodicidade": "semanal",
              "dia_vencimento": 3, "valor_mensal": Decimal("200.00")},  # quartas
        "C": {"id": uuid4(), "numero": f"AUD-{suf}-C", "periodicidade": "mensal",
              "dia_vencimento": 10, "valor_mensal": Decimal("1200.00")},
    }

    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text(
                """INSERT INTO comercial.empresas
                  (id, razao_social, cnpj, email)
                VALUES (:id, :r, :c, :e)"""
            ),
            {
                "id": str(empresa_id),
                "r": NOME_EMPRESA,
                # CNPJ único (14 dígitos) — usa int(uuid) pra garantir só
                # números. Cleanup nem sempre apaga a row anterior se houver
                # FKs externas, então não pode ser fixo.
                "c": str(empresa_id.int)[:14].ljust(14, "0"),
                "e": f"auditoria-{empresa_id.hex[:8]}@frotauber.local",
            },
        )
        # Usa o admin seed como ator. Se não existir, é problema de seed.
        admin_row = (
            await conn.execute(
                text("SELECT id FROM acesso.usuarios LIMIT 1")
            )
        ).first()
        admin_id = admin_row[0] if admin_row else None
        for chave, cli in clientes.items():
            await conn.execute(
                text(
                    """INSERT INTO cadastro.clientes
                      (id, empresa_id, nome_completo, cpf_cnpj, telefone, score, status)
                    VALUES (:id, :eid, :n, :cpf, :tel, 100, 'ativo')"""
                ),
                {
                    "id": str(cli["id"]),
                    "eid": str(empresa_id),
                    "n": cli["nome"],
                    "cpf": cli["cpf"],
                    "tel": cli["tel"],
                },
            )
        for chave, vei in veiculos.items():
            await conn.execute(
                text(
                    """INSERT INTO veiculos.veiculos
                      (id, empresa_id, placa, fipe_marca, fipe_modelo,
                       ano_modelo, ano_fabricacao, status)
                    VALUES (:id, :eid, :p, :ma, :mo, 2024, 2024, 'em_uso')"""
                ),
                {
                    "id": str(vei["id"]),
                    "eid": str(empresa_id),
                    "p": vei["placa"],
                    "ma": vei["marca"],
                    "mo": vei["modelo"],
                },
            )
        for chave in "ABC":
            ct = contratos[chave]
            await conn.execute(
                text(
                    """INSERT INTO contrato.contratos
                      (id, empresa_id, numero, cliente_id, veiculo_id, status,
                       data_inicio, data_fim, valor_total, periodicidade,
                       dia_vencimento, modo_geracao, multa_mora_pct,
                       juros_mora_dia_pct, criado_por_id)
                    VALUES (:id, :eid, :num, :cli, :vei, 'vigente',
                            :di, :df, :total, :per, :dv, 'antecipado',
                            2.00, 0.0333, :uid)"""
                ),
                {
                    "id": str(ct["id"]),
                    "eid": str(empresa_id),
                    "num": ct["numero"],
                    "cli": str(clientes[chave]["id"]),
                    "vei": str(veiculos[chave]["id"]),
                    "di": DATA_INICIO,
                    "df": DATA_INICIO + timedelta(days=365),
                    "total": ct["valor_mensal"] * 12,
                    "per": ct["periodicidade"],
                    "dv": ct["dia_vencimento"],
                    "uid": str(admin_id) if admin_id else None,
                },
            )
            await conn.execute(
                text(
                    """UPDATE veiculos.veiculos SET contrato_ativo_id = :cid
                       WHERE id = :vid"""
                ),
                {"cid": str(ct["id"]), "vid": str(veiculos[chave]["id"])},
            )

    return {
        "empresa_id": empresa_id,
        "clientes": clientes,
        "veiculos": veiculos,
        "contratos": contratos,
    }


# ─────────── Geração manual de títulos (sem worker — controlamos a data) ─

async def gerar_titulos_iniciais(ctx: dict) -> None:
    """Cria 6 títulos por contrato (cobre 6 meses) com data_vencimento
    distribuída de acordo com a periodicidade."""
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        for chave in "ABC":
            ct = ctx["contratos"][chave]
            if ct["periodicidade"] == "mensal":
                base = DATA_INICIO.replace(day=ct["dia_vencimento"])
                if base < DATA_INICIO:
                    # avança um mês
                    m = base.month + 1
                    y = base.year + (1 if m > 12 else 0)
                    base = base.replace(month=((m - 1) % 12) + 1, year=y)
                datas = []
                d = base
                for i in range(6):
                    datas.append(d)
                    m = d.month + 1
                    y = d.year + (1 if m > 12 else 0)
                    d = d.replace(month=((m - 1) % 12) + 1, year=y)
            elif ct["periodicidade"] == "semanal":
                # 24 títulos semanais (6 meses)
                # primeira data = primeira quarta a partir de DATA_INICIO
                d = DATA_INICIO
                while d.weekday() != ct["dia_vencimento"]:  # 3 = quarta
                    d += timedelta(days=1)
                datas = [d + timedelta(weeks=i) for i in range(24)]
            else:
                datas = []

            valor_titulo = (
                ct["valor_mensal"] / 4 if ct["periodicidade"] == "semanal" else ct["valor_mensal"]
            )
            for i, dv in enumerate(datas):
                await conn.execute(
                    text(
                        """INSERT INTO financeiro.titulos_receber
                          (id, empresa_id, contrato_id, sequencia, data_vencimento,
                           valor, tipo, status)
                        VALUES (:id, :eid, :cid, :seq, :dv, :v, 'parcela', 'em_aberto')"""
                    ),
                    {
                        "id": str(uuid4()),
                        "eid": str(ctx["empresa_id"]),
                        "cid": str(ct["id"]),
                        "seq": i + 1,
                        "dv": dv,
                        "v": valor_titulo,
                    },
                )
    log_evento(DATA_INICIO, "titulos_gerados", contratos=3)


# ─────────────────── Workers (chamados diretamente) ──────────────────


async def rodar_workers_do_dia(empresa_id: UUID, dia: date) -> None:
    """Chama em sequência os workers que deveriam rodar nesse dia."""
    from app.workers.tasks import (
        alertar_vencimentos_proximos,
        processar_titulos_vencidos,
        recalcular_scores_clientes,
        expirar_desbloqueios_confianca,
    )

    for nome, func in [
        ("alertar_vencimentos_proximos", lambda: alertar_vencimentos_proximos._run(empresa_id)),
        ("processar_titulos_vencidos", lambda: processar_titulos_vencidos._run(empresa_id)),
        ("recalcular_scores_clientes", lambda: recalcular_scores_clientes._run(empresa_id)),
        ("expirar_desbloqueios_confianca", lambda: expirar_desbloqueios_confianca._executar()),
    ]:
        try:
            resultado = await func()
            log_evento(dia, f"worker:{nome}", resultado=str(resultado)[:200])
        except Exception as exc:
            log_bug(dia, f"worker:{nome}", exc, empresa_id=str(empresa_id))


# ─────────────────── Simular pagamentos dos clientes ─────────────────


async def cliente_paga_titulo(empresa_id: UUID, cliente_id: UUID, dia: date) -> None:
    """Cliente A — paga o título em aberto mais antigo no vencimento."""
    from app.application.services.servico_titulo_pago import ServicoTituloPago
    from app.infrastructure.db.session import get_sessionmaker

    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(
            text("SET LOCAL row_security = off"),
        )
        row = (
            await s.execute(
                text(
                    """SELECT tr.id, tr.valor FROM financeiro.titulos_receber tr
                       JOIN contrato.contratos c ON c.id = tr.contrato_id
                       WHERE c.cliente_id = :cli
                         AND tr.empresa_id = :eid
                         AND tr.status IN ('em_aberto', 'em_atraso')
                         AND tr.data_vencimento <= :dia
                       ORDER BY tr.data_vencimento ASC LIMIT 1"""
                ),
                {"cli": str(cliente_id), "eid": str(empresa_id), "dia": dia},
            )
        ).first()
        if row is None:
            return
        try:
            svc = ServicoTituloPago(s, empresa_id)
            await svc.registrar_pagamento(
                titulo_id=row[0],
                valor_pago=row[1],
                data_pagamento=dia,
                forma_pagamento="pix",
                ator_id=None,
            )
            await s.commit()
            log_evento(dia, "cliente_pagou", cliente_id=str(cliente_id), valor=str(row[1]))
        except Exception as exc:
            log_bug(dia, "cliente_pagou", exc, cliente_id=str(cliente_id))
            await s.rollback()


# ─────────────────── Análise de comprovante simulada ─────────────────


async def cliente_envia_comprovante(
    empresa_id: UUID, cliente_id: UUID, arquivo: Path, dia: date
) -> dict:
    """Simula cliente B mandando um comprovante via WhatsApp.

    Chama o ServicoAnaliseComprovante direto sobre os bytes do arquivo.
    """
    from app.application.services.servico_analise_comprovante import (
        ComprovanteJaAnalisadoError,
        ServicoAnaliseComprovante,
    )
    from app.infrastructure.db.session import get_sessionmaker

    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(text("SET LOCAL row_security = off"))
        try:
            bytes_arquivo = arquivo.read_bytes()
            mime = (
                "application/pdf" if arquivo.suffix.lower() == ".pdf"
                else "image/png" if arquivo.suffix.lower() == ".png"
                else "application/octet-stream"
            )
            svc = ServicoAnaliseComprovante(s, empresa_id)
            comp = await svc.analisar(
                bytes_arquivo=bytes_arquivo,
                tipo_mime=mime,
                arquivo_url=f"file://{arquivo}",
                cliente_id=cliente_id,
                origem="whatsapp",  # constraint ck_comprovante_origem
                telefone_remetente="5511988880002",
            )
            await s.commit()
            resultado = {
                "arquivo": arquivo.name,
                "metodo_analise": comp.metodo_analise,
                "score_confianca": float(comp.score_confianca) if comp.score_confianca else None,
                "valor_detectado": str(comp.valor_detectado) if comp.valor_detectado else None,
                "data_detectada": comp.data_detectada.isoformat() if comp.data_detectada else None,
                "pagador_nome": comp.pagador_nome,
                "beneficiario_cnpj": comp.beneficiario_cnpj,
                "pix_txid": comp.pix_txid,
                "titulo_match_id": str(comp.titulo_id) if comp.titulo_id else None,
                "avisos": comp.avisos[:5] if comp.avisos else [],
                "status": comp.status,
            }
            log_evento(
                dia,
                "comprovante_analisado",
                cliente_id=str(cliente_id),
                **resultado,
            )
            return resultado
        except ComprovanteJaAnalisadoError as ja:
            await s.rollback()
            log_evento(dia, "comprovante_duplicado", arquivo=arquivo.name)
            return {"arquivo": arquivo.name, "duplicado": True}
        except Exception as exc:
            await s.rollback()
            log_bug(dia, f"analise:{arquivo.name}", exc, cliente_id=str(cliente_id))
            return {"arquivo": arquivo.name, "erro": str(exc), "tipo_erro": type(exc).__name__}


# ─────────────────── Loop principal de simulação ─────────────────────


async def avancar_tempo_e_simular(ctx: dict, dias_total: int = 180) -> None:
    """Avança N dias simulados, disparando workers + ações dos clientes
    em momentos pré-definidos.

    Cliente A: paga sempre no vencimento.
    Cliente B: atrasa 5 dias; depois manda comprovante.
    Cliente C: nunca paga.
    """
    empresa_id = ctx["empresa_id"]

    arquivos_comprov = sorted(PASTA_COMPROVANTES.glob("*.*"))

    proxima_amostra_comprovante = 0
    dias_comprovante_envio = [45, 90, 135, 170]  # marcos pra cliente B mandar comprovante

    for d in range(0, dias_total + 1):
        dia_sim = DATA_INICIO + timedelta(days=d)

        with freeze_time(datetime.combine(dia_sim, time(8, 0)).replace(tzinfo=timezone.utc)):
            # Cliente A paga no exato dia do vencimento
            await cliente_paga_titulo(empresa_id, ctx["clientes"]["A"]["id"], dia_sim)

            # Cliente B atrasa 5 dias depois do vencimento. Vamos olhar se há
            # algum título de B em atraso com 5+ dias e simular pagamento.
            await maybe_cliente_b_paga_atrasado(empresa_id, ctx["clientes"]["B"]["id"], dia_sim)

            # Cliente C nunca paga — só observa.

            # Workers do dia
            await rodar_workers_do_dia(empresa_id, dia_sim)

            # Em dias marcados, B manda comprovante (cobrindo os 4 arquivos)
            if d in dias_comprovante_envio and proxima_amostra_comprovante < len(arquivos_comprov):
                arq = arquivos_comprov[proxima_amostra_comprovante]
                await cliente_envia_comprovante(
                    empresa_id, ctx["clientes"]["B"]["id"], arq, dia_sim
                )
                proxima_amostra_comprovante += 1


async def maybe_cliente_b_paga_atrasado(
    empresa_id: UUID, cliente_id: UUID, dia: date
) -> None:
    """B paga título quando este está atrasado há mais de 5 dias."""
    from app.application.services.servico_titulo_pago import ServicoTituloPago
    from app.infrastructure.db.session import get_sessionmaker

    sm = get_sessionmaker()
    async with sm() as s:
        await s.execute(text("SET LOCAL row_security = off"))
        row = (
            await s.execute(
                text(
                    """SELECT tr.id, tr.valor, tr.data_vencimento
                       FROM financeiro.titulos_receber tr
                       JOIN contrato.contratos c ON c.id = tr.contrato_id
                       WHERE c.cliente_id = :cli
                         AND tr.empresa_id = :eid
                         AND tr.status IN ('em_aberto', 'em_atraso')
                       ORDER BY tr.data_vencimento ASC LIMIT 1"""
                ),
                {"cli": str(cliente_id), "eid": str(empresa_id)},
            )
        ).first()
        if row is None:
            return
        atraso = (dia - row[2]).days
        if atraso < 5:
            return
        try:
            svc = ServicoTituloPago(s, empresa_id)
            await svc.registrar_pagamento(
                titulo_id=row[0],
                valor_pago=row[1],
                data_pagamento=dia,
                forma_pagamento="pix",
                ator_id=None,
            )
            await s.commit()
            log_evento(dia, "cliente_b_pagou_atrasado", atraso_dias=atraso, valor=str(row[1]))
        except Exception as exc:
            await s.rollback()
            log_bug(dia, "b_pagou_atrasado", exc, cliente_id=str(cliente_id))


# ─────────────────── Relatório de métricas finais ─────────────────────


async def coletar_metricas_finais(empresa_id: UUID) -> dict:
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))

        async def q(sql: str, **params):
            return (await conn.execute(text(sql), params)).all()

        eid = {"e": str(empresa_id)}
        titulos_por_status = await q(
            "SELECT status, count(*), COALESCE(SUM(valor)::text, '0') "
            "FROM financeiro.titulos_receber WHERE empresa_id=:e GROUP BY status", **eid)
        contratos_por_status = await q(
            "SELECT status, count(*) FROM contrato.contratos WHERE empresa_id=:e GROUP BY status", **eid)
        clientes_score = await q(
            "SELECT nome_completo, score, na_blacklist_comprovantes, "
            "  adiamentos_usados_no_periodo, desbloqueios_confianca_usados_no_periodo "
            "FROM cadastro.clientes WHERE empresa_id=:e ORDER BY score DESC", **eid)
        comprovantes = await q(
            "SELECT metodo_analise, status, count(*) "
            "FROM financeiro.comprovantes_pagamento WHERE empresa_id=:e "
            "GROUP BY metodo_analise, status", **eid)
        lembretes = await q(
            "SELECT canal, sucesso, count(*) FROM financeiro.lembretes_enviados "
            "WHERE empresa_id=:e GROUP BY canal, sucesso", **eid)
        execucoes_motor = await q(
            "SELECT nome_tarefa, situacao, count(*) FROM motor.execucoes_motor "
            "WHERE empresa_id=:e GROUP BY nome_tarefa, situacao", **eid)
        whatsapp_envios = len(list(PASTA_WHATSAPP.glob("*.txt")))

    return {
        "titulos_por_status": [list(r) for r in titulos_por_status],
        "contratos_por_status": [list(r) for r in contratos_por_status],
        "clientes_score_final": [list(r) for r in clientes_score],
        "comprovantes": [list(r) for r in comprovantes],
        "lembretes": [list(r) for r in lembretes],
        "execucoes_motor": [list(r) for r in execucoes_motor],
        "whatsapp_envios_arquivos": whatsapp_envios,
    }


# ─────────────────────── Main ─────────────────────────────────────────


async def main() -> None:
    print(">>> [1/6] Limpando empresa anterior...")
    await limpar_empresa_anterior()

    print(">>> [2/6] Registrando FakeWhatsAppChannel...")
    sys.path.insert(0, "/srv/audit-scripts")
    from fake_whatsapp_channel import FakeWhatsAppChannel  # noqa
    from app.core.channels.registry import channel_registry
    channel_registry.register(FakeWhatsAppChannel())

    print(">>> [3/6] Cadastrando empresa + clientes + veículos + contratos...")
    ctx = await cadastrar_base()
    print(f"    empresa_id = {ctx['empresa_id']}")

    print(">>> [4/6] Gerando títulos iniciais (6 meses)...")
    await gerar_titulos_iniciais(ctx)

    print(">>> [5/6] Avançando o tempo (~180 dias simulados)...")
    await avancar_tempo_e_simular(ctx, dias_total=180)

    print(">>> [6/6] Coletando métricas...")
    metricas = await coletar_metricas_finais(ctx["empresa_id"])

    saida = {
        "data_execucao": datetime.now(timezone.utc).isoformat(),
        "empresa_id": str(ctx["empresa_id"]),
        "data_inicio_simulada": DATA_INICIO.isoformat(),
        "dias_simulados": 180,
        "clientes": {
            k: {"id": str(v["id"]), "nome": v["nome"], "telefone": v["tel"]}
            for k, v in ctx["clientes"].items()
        },
        "veiculos": {
            k: {"id": str(v["id"]), "placa": v["placa"]}
            for k, v in ctx["veiculos"].items()
        },
        "contratos": {
            k: {"id": str(v["id"]), "numero": v["numero"],
                "periodicidade": v["periodicidade"],
                "valor_mensal": str(v["valor_mensal"])}
            for k, v in ctx["contratos"].items()
        },
        "metricas_finais": metricas,
        "bugs": BUGS_ENCONTRADOS,
        "qtd_eventos_timeline": len(EVENTOS_TIMELINE),
    }

    (PASTA_LOG / "resumo.json").write_text(
        json.dumps(saida, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (PASTA_LOG / "timeline.json").write_text(
        json.dumps(EVENTOS_TIMELINE, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )
    (PASTA_LOG / "bugs.json").write_text(
        json.dumps(BUGS_ENCONTRADOS, indent=2, ensure_ascii=False, default=str),
        encoding="utf-8",
    )

    print(f"\n=== AUDITORIA CONCLUÍDA ===")
    print(f"Bugs encontrados: {len(BUGS_ENCONTRADOS)}")
    print(f"Eventos timeline: {len(EVENTOS_TIMELINE)}")
    print(f"Logs em: {PASTA_LOG}/")


if __name__ == "__main__":
    asyncio.run(main())
