"""Base para motores do Epic 13 (Story 13.5).

`ExecucaoMotorTracker` é um context manager que:
- Cria uma linha em `motor.execucoes_motor` com situação='executando'.
- No exit normal: marca 'concluido', preenche `finalizado_em`,
  `total_registros`, `total_erros`, `detalhes`.
- No exit por exceção: marca 'erro' com a mensagem em `detalhes`.

Uso típico:

    async with ExecucaoMotorTracker(
        session, "alertar_vencimentos_proximos", empresa_id
    ) as tracker:
        for titulo in titulos:
            try:
                await processar(titulo)
                tracker.registrar_sucesso()
            except Exception as e:
                tracker.registrar_erro(detalhes={"titulo_id": str(titulo.id), "erro": str(e)})
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.execucao_motor import ExecucaoMotor


log = structlog.get_logger()


class ExecucaoMotorTracker:
    """Gerencia o ciclo de vida de uma execução de motor."""

    def __init__(
        self,
        session: AsyncSession,
        nome_tarefa: str,
        empresa_id: UUID | None = None,
    ) -> None:
        self.session = session
        self.nome_tarefa = nome_tarefa
        self.empresa_id = empresa_id
        self.total_registros = 0
        self.total_erros = 0
        self.erros_detalhe: list[dict] = []
        self.execucao: ExecucaoMotor | None = None

    async def __aenter__(self) -> "ExecucaoMotorTracker":
        self.execucao = ExecucaoMotor(
            nome_tarefa=self.nome_tarefa,
            empresa_id=self.empresa_id,
            situacao="executando",
        )
        self.session.add(self.execucao)
        await self.session.flush()
        log.info(
            "motor_iniciado",
            execucao_id=str(self.execucao.id),
            nome_tarefa=self.nome_tarefa,
            empresa_id=str(self.empresa_id) if self.empresa_id else None,
        )
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        if self.execucao is None:
            return
        self.execucao.finalizado_em = datetime.now(timezone.utc)
        self.execucao.total_registros = self.total_registros
        self.execucao.total_erros = self.total_erros

        if exc_type is not None:
            self.execucao.situacao = "erro"
            self.execucao.detalhes = {
                "erros": self.erros_detalhe,
                "excecao": str(exc_val),
                "traceback": traceback.format_exception(exc_type, exc_val, exc_tb)[-5:],
            }
            log.error(
                "motor_erro",
                execucao_id=str(self.execucao.id),
                nome_tarefa=self.nome_tarefa,
                erro=str(exc_val),
            )
        else:
            self.execucao.situacao = "concluido"
            if self.erros_detalhe:
                self.execucao.detalhes = {"erros": self.erros_detalhe}
            log.info(
                "motor_concluido",
                execucao_id=str(self.execucao.id),
                nome_tarefa=self.nome_tarefa,
                total_registros=self.total_registros,
                total_erros=self.total_erros,
            )

        try:
            await self.session.flush()
        except Exception:
            log.exception("motor_finalize_flush_failed")

    def registrar_sucesso(self) -> None:
        self.total_registros += 1

    def registrar_erro(self, detalhes: dict[str, Any]) -> None:
        self.total_registros += 1
        self.total_erros += 1
        if len(self.erros_detalhe) < 50:  # cap pra não estourar JSONB
            self.erros_detalhe.append(detalhes)
