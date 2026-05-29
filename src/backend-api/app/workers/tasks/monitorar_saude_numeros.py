"""Worker `monitorar_saude_numeros` — Story 13.21.

Roda a cada 15 minutos. Para cada número WhatsApp (categoria=`whatsapp`,
provedor=`evolution_go`) cadastrado em qualquer empresa:

1. Chama `health_check()` do adapter.
2. Atualiza `config.ultimo_health_check` no JSONB.
3. Se o adapter detectou ban (HTTP 401/403) → chama
   `ServicoRoteamentoNumeros.marcar_numero_banido` automaticamente.
4. Persiste resumo em `motor.execucoes_motor` para a tela de observabilidade.

NÃO é fan-out por empresa (system-level): vista global de todos os números
de todos os clientes do SaaS porque o monitoramento é responsabilidade do
provedor (Pablo), não de cada empresa cliente.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from uuid import UUID

import structlog
from sqlalchemy import select, text

from app.workers import celery_app


log = structlog.get_logger()


@celery_app.task(name="app.workers.tasks.monitorar_saude_numeros.executar")
def executar() -> dict:
    """Entry point Celery. System-wide (sem empresa_id)."""
    return asyncio.run(_run())


async def _run() -> dict:
    from app.application.services.servico_roteamento_numeros import (
        ServicoRoteamentoNumeros,
    )
    from app.infrastructure.adapters.whatsapp.evolution_go_adapter import (
        EvolutionGoAdapter,
        EvolutionGoBanidoError,
    )
    from app.infrastructure.db.models.config import CredencialIntegracao
    from app.infrastructure.db.models.execucao_motor import ExecucaoMotor
    from app.infrastructure.db.session import get_sessionmaker
    from app.infrastructure.settings import get_settings

    settings = get_settings()
    session_factory = get_sessionmaker()

    # Tracker em session dedicada (system-level — empresa_id NULL)
    tracker_session = session_factory()
    # System-wide: desabilita RLS pra ver todas as empresas
    await tracker_session.execute(text("SET LOCAL row_security = off"))

    execucao = ExecucaoMotor(
        nome_tarefa="monitorar_saude_numeros",
        empresa_id=None,  # system-wide
        situacao="executando",
    )
    tracker_session.add(execucao)
    await tracker_session.flush()
    await tracker_session.commit()
    execucao_id = execucao.id

    total_verificados = 0
    total_banidos_detectados = 0
    total_erros = 0
    detalhes_erros: list[dict] = []

    try:
        async with session_factory() as session:
            await session.execute(text("SET LOCAL row_security = off"))

            # Lista TODOS os números evolution_go de todas as empresas
            creds = list((await session.execute(
                select(CredencialIntegracao).where(
                    CredencialIntegracao.categoria == "whatsapp",
                    CredencialIntegracao.provedor == "evolution_go",
                    CredencialIntegracao.ativo.is_(True),
                )
            )).scalars().all())

            for cred in creds:
                config_atual = cred.config or {}
                token = config_atual.get("instance_token", "")
                instance_id = config_atual.get("instance_id", "")

                if not token:
                    log.warning(
                        "saude_credencial_sem_token",
                        credencial_id=str(cred.id),
                        empresa_id=str(cred.empresa_id),
                    )
                    total_erros += 1
                    detalhes_erros.append({
                        "credencial_id": str(cred.id),
                        "erro": "sem_instance_token",
                    })
                    continue

                adapter = EvolutionGoAdapter(
                    api_url=settings.EVOLUTION_GO_API_URL,
                    instance_token=token,
                    instance_id=instance_id,
                )

                # Tenta health check
                try:
                    resultado = await adapter.health_check()
                    banido = bool(resultado.get("banido"))
                    conectado = resultado.get("connected", True)
                except EvolutionGoBanidoError:
                    banido = True
                    conectado = False
                    resultado = {"erro": "ban_detectado_via_excecao"}
                except Exception as exc:
                    log.exception(
                        "saude_check_excecao",
                        credencial_id=str(cred.id),
                    )
                    total_erros += 1
                    detalhes_erros.append({
                        "credencial_id": str(cred.id),
                        "erro": str(exc)[:200],
                    })
                    continue

                total_verificados += 1

                # Atualiza ultimo_health_check no JSONB
                novo_config = dict(config_atual)
                novo_config["ultimo_health_check"] = datetime.now(timezone.utc).isoformat()
                if banido:
                    novo_config["status_whatsapp"] = "banido"
                elif not conectado:
                    novo_config["status_whatsapp"] = "desconectado"
                cred.config = novo_config

                # Se banido, dispara migração via ServicoRoteamentoNumeros
                if banido:
                    total_banidos_detectados += 1
                    servico = ServicoRoteamentoNumeros(session, cred.empresa_id)
                    try:
                        # Chamada interna ao servico que atualiza status e
                        # migra clientes. O servico também escreve auditoria.
                        await servico.marcar_numero_banido(
                            cred.id,
                            motivo="Detectado automaticamente via health_check (HTTP 401/403)",
                            ator_id=None,  # system
                        )
                    except Exception as exc:
                        log.exception(
                            "ban_detectado_migracao_falhou",
                            credencial_id=str(cred.id),
                        )
                        total_erros += 1
                        detalhes_erros.append({
                            "credencial_id": str(cred.id),
                            "erro_migracao": str(exc)[:200],
                        })

            await session.commit()

        # Finaliza tracker
        execucao_session = session_factory()
        await execucao_session.execute(text("SET LOCAL row_security = off"))
        execucao = (await execucao_session.execute(
            select(ExecucaoMotor).where(ExecucaoMotor.id == execucao_id)
        )).scalar_one()
        execucao.finalizado_em = datetime.now(timezone.utc)
        execucao.total_registros = total_verificados
        execucao.total_erros = total_erros
        execucao.situacao = "concluido"
        execucao.detalhes = {
            "verificados": total_verificados,
            "banidos_detectados": total_banidos_detectados,
            "erros": detalhes_erros[:50],  # cap pro JSONB
        }
        await execucao_session.commit()
        await execucao_session.close()

        log.info(
            "saude_numeros_complete",
            verificados=total_verificados,
            banidos=total_banidos_detectados,
            erros=total_erros,
        )

        return {
            "verificados": total_verificados,
            "banidos_detectados": total_banidos_detectados,
            "erros": total_erros,
        }

    except Exception as exc:
        log.exception("saude_numeros_falha_geral")
        try:
            execucao_session = session_factory()
            await execucao_session.execute(text("SET LOCAL row_security = off"))
            execucao = (await execucao_session.execute(
                select(ExecucaoMotor).where(ExecucaoMotor.id == execucao_id)
            )).scalar_one()
            execucao.situacao = "erro"
            execucao.detalhes = {"erro": str(exc)[:500]}
            execucao.finalizado_em = datetime.now(timezone.utc)
            await execucao_session.commit()
            await execucao_session.close()
        except Exception:
            log.exception("saude_numeros_tracker_falhou_finalizar")
        raise

    finally:
        await tracker_session.close()
