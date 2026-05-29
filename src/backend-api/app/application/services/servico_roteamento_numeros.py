"""ServicoRoteamentoNumeros — atribuição estável e balanceamento de números
de WhatsApp por empresa (Story 13.21).

Regras de negócio consolidadas:
- Cliente fica fixo num número da empresa após primeiro contato outbound
  (atribuição estável).
- Cliente novo é atribuído ao número com menor contagem de clientes ativos
  entre os números com status `ativo` (distribuição de carga proativa).
- Quando empate na contagem, prefere o número marcado como `eh_principal`.
- Quando número é marcado como `banido`, todos os clientes atribuídos a ele
  são reatribuídos automaticamente entre os ativos restantes (audit log
  obrigatório por cliente).
- Categoria fixa: `whatsapp` (provedor `evolution_go` na 13.21; outros
  provedores futuros seguem mesma estrutura).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.audit_logger import AuditLogger
from app.infrastructure.db.models.cadastro import Cliente
from app.infrastructure.db.models.config import CredencialIntegracao


log = structlog.get_logger()


# Status válidos de uma credencial WhatsApp na coluna config.status_whatsapp
STATUS_ATIVO = "ativo"
STATUS_INATIVO = "inativo"          # gestor desligou voluntariamente
STATUS_BANIDO = "banido"            # WhatsApp baniu (detectado)
STATUS_DESCONECTADO = "desconectado"  # sessão caiu, recuperável


class NenhumNumeroAtivoError(Exception):
    """Levantada quando a empresa não tem nenhum número WhatsApp ativo
    pra atender. Caller decide se notifica gestor ou silencia (ex.:
    inbound de cliente cujo número da empresa foi banido).
    """


class ServicoRoteamentoNumeros:
    """Roteador estável de números WhatsApp por cliente."""

    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    # ── Atribuição (primeira mensagem outbound) ───────────────────────

    async def atribuir_numero(self, cliente_id: UUID) -> UUID:
        """Garante que o cliente tem um número atribuído. Idempotente.

        Se cliente já tem `numero_origem_id` apontando para um número ativo,
        retorna o existente sem mudar nada. Se o número está banido ou
        inativo, força reatribuição.

        Retorna o `credencial_id` do número escolhido.

        Levanta `NenhumNumeroAtivoError` se a empresa não tem nenhum número
        ativo no momento.
        """
        cliente = await self._carregar_cliente(cliente_id)

        # Já tem atribuição? Verifica se ainda é válida (ativo).
        if cliente.numero_origem_id is not None:
            cred_existente = await self._carregar_credencial(cliente.numero_origem_id)
            if cred_existente is not None and self._status_credencial(cred_existente) == STATUS_ATIVO:
                return cred_existente.id
            # Caso contrário, vai reatribuir abaixo.
            log.info(
                "cliente_perdeu_numero_anterior",
                cliente_id=str(cliente_id),
                credencial_anterior=str(cliente.numero_origem_id),
                motivo="status_invalido_ou_excluido",
            )

        # Escolhe número entre ativos
        nova_cred_id = await self._escolher_numero_para_novo_cliente()
        cliente.numero_origem_id = nova_cred_id
        await self.session.flush()
        return nova_cred_id

    async def credencial_para_outbound(self, cliente_id: UUID) -> CredencialIntegracao:
        """Retorna a credencial completa do número atribuído ao cliente para
        envio outbound. Atribui sob demanda se ainda não foi atribuído.

        Se número atribuído ficou `banido` desde a última mensagem, reatribui
        automaticamente (transparente).
        """
        cred_id = await self.atribuir_numero(cliente_id)
        cred = await self._carregar_credencial(cred_id)
        if cred is None:
            raise NenhumNumeroAtivoError(
                f"Credencial {cred_id} desapareceu após atribuição — caso de corrida raro"
            )
        return cred

    # ── Banimento (detecção automática ou manual) ─────────────────────

    async def marcar_numero_banido(
        self,
        credencial_id: UUID,
        motivo: str,
        ator_id: UUID | None = None,
    ) -> int:
        """Marca número como banido + reatribui todos os clientes vinculados.

        Retorna a quantidade de clientes migrados. Notifica via audit log.
        """
        cred = await self._carregar_credencial(credencial_id)
        if cred is None:
            raise ValueError(f"Credencial {credencial_id} não encontrada")

        # Atualiza status no JSONB
        config_atual = dict(cred.config or {})
        config_atual["status_whatsapp"] = STATUS_BANIDO
        config_atual["motivo_banimento"] = motivo
        config_atual["banido_em"] = datetime.now(timezone.utc).isoformat()
        cred.config = config_atual
        await self.session.flush()

        # Reatribui clientes ainda apontando para este número
        afetados = list((await self.session.execute(
            select(Cliente).where(
                Cliente.empresa_id == self.empresa_id,
                Cliente.numero_origem_id == credencial_id,
                Cliente.excluido_em.is_(None),
            )
        )).scalars().all())

        migrados = 0
        if afetados:
            # Pega novos números ativos uma única vez (a escolha balanceia
            # dinamicamente conforme contagens — recalculamos por cliente
            # pra distribuir uniformemente entre os ativos).
            for cliente in afetados:
                try:
                    nova_cred = await self._escolher_numero_para_novo_cliente(
                        excluir=credencial_id,
                    )
                except NenhumNumeroAtivoError:
                    log.warning(
                        "migracao_sem_destino",
                        empresa_id=str(self.empresa_id),
                        cliente_id=str(cliente.id),
                        motivo="nenhum_outro_numero_ativo",
                    )
                    # Deixa cliente sem número atribuído — será corrigido
                    # quando empresa ativar outro número.
                    cliente.numero_origem_id = None
                    continue
                cliente.numero_origem_id = nova_cred
                migrados += 1

        await self.session.flush()

        # Audit log da migração agregada
        audit = AuditLogger(self.session)
        await audit.record(
            action="numero_whatsapp.banido",
            user_id=str(ator_id) if ator_id else None,
            entity="credenciais_integracao",
            entity_id=str(credencial_id),
            payload_after={
                "motivo": motivo,
                "clientes_migrados": migrados,
                "clientes_afetados_total": len(afetados),
            },
            module="comunicacao",
            category="comunicacao",
        )

        log.info(
            "numero_whatsapp_banido",
            empresa_id=str(self.empresa_id),
            credencial_id=str(credencial_id),
            migrados=migrados,
            total_afetados=len(afetados),
        )
        return migrados

    async def marcar_numero_ativo(
        self, credencial_id: UUID, ator_id: UUID | None = None
    ) -> None:
        """Reativa um número (gestor confirmou reconexão manualmente ou
        ativou um número novo). Não reatribui clientes — distribuição
        balanceia apenas em novos atendimentos.
        """
        cred = await self._carregar_credencial(credencial_id)
        if cred is None:
            raise ValueError(f"Credencial {credencial_id} não encontrada")
        config_atual = dict(cred.config or {})
        config_atual["status_whatsapp"] = STATUS_ATIVO
        config_atual.pop("motivo_banimento", None)
        config_atual.pop("banido_em", None)
        cred.config = config_atual
        cred.ativo = True
        await self.session.flush()

        audit = AuditLogger(self.session)
        await audit.record(
            action="numero_whatsapp.reativado",
            user_id=str(ator_id) if ator_id else None,
            entity="credenciais_integracao",
            entity_id=str(credencial_id),
            payload_after={"status": STATUS_ATIVO},
            module="comunicacao",
            category="comunicacao",
        )

    async def definir_numero_principal(
        self, credencial_id: UUID, ator_id: UUID | None = None
    ) -> None:
        """Marca um número como principal (preferido no empate da atribuição).

        Limpa a flag dos outros números da mesma empresa — só 1 principal
        por empresa.
        """
        # Remove flag dos outros
        outras = list((await self.session.execute(
            select(CredencialIntegracao).where(
                CredencialIntegracao.empresa_id == self.empresa_id,
                CredencialIntegracao.categoria == "whatsapp",
                CredencialIntegracao.id != credencial_id,
            )
        )).scalars().all())
        for outra in outras:
            config_atual = dict(outra.config or {})
            if config_atual.get("eh_principal"):
                config_atual["eh_principal"] = False
                outra.config = config_atual

        # Marca a escolhida
        cred = await self._carregar_credencial(credencial_id)
        if cred is None:
            raise ValueError(f"Credencial {credencial_id} não encontrada")
        config_atual = dict(cred.config or {})
        config_atual["eh_principal"] = True
        cred.config = config_atual
        await self.session.flush()

        audit = AuditLogger(self.session)
        await audit.record(
            action="numero_whatsapp.principal_definido",
            user_id=str(ator_id) if ator_id else None,
            entity="credenciais_integracao",
            entity_id=str(credencial_id),
            payload_after={"eh_principal": True},
            module="comunicacao",
            category="comunicacao",
        )

    # ── Consultas utilitárias (usadas por endpoints e workers) ────────

    async def listar_numeros(self) -> list[dict[str, Any]]:
        """Lista números da empresa com contagem de clientes atribuídos.

        Retorna lista de dicts prontos para serialização REST:
        `[{ credencial_id, instance_id, numero_e164, status, eh_principal,
            clientes_atribuidos, ultimo_health_check, motivo_banimento }, ...]`
        """
        creds = list((await self.session.execute(
            select(CredencialIntegracao).where(
                CredencialIntegracao.empresa_id == self.empresa_id,
                CredencialIntegracao.categoria == "whatsapp",
            )
        )).scalars().all())

        if not creds:
            return []

        # Contagem de clientes por número (uma query agregada)
        contagens_stmt = (
            select(
                Cliente.numero_origem_id,
                func.count(Cliente.id).label("total"),
            )
            .where(
                Cliente.empresa_id == self.empresa_id,
                Cliente.excluido_em.is_(None),
                Cliente.numero_origem_id.in_([c.id for c in creds]),
            )
            .group_by(Cliente.numero_origem_id)
        )
        contagens = {
            row[0]: row[1]
            for row in (await self.session.execute(contagens_stmt)).all()
        }

        return [
            {
                "credencial_id": str(c.id),
                "provedor": c.provedor,
                "instance_id": (c.config or {}).get("instance_id"),
                "numero_e164": (c.config or {}).get("numero_e164"),
                "status_whatsapp": (c.config or {}).get(
                    "status_whatsapp", STATUS_ATIVO
                ),
                "eh_principal": (c.config or {}).get("eh_principal", False),
                "clientes_atribuidos": int(contagens.get(c.id, 0)),
                "ultimo_health_check": (c.config or {}).get("ultimo_health_check"),
                "motivo_banimento": (c.config or {}).get("motivo_banimento"),
            }
            for c in creds
        ]

    # ── Helpers privados ──────────────────────────────────────────────

    async def _carregar_cliente(self, cliente_id: UUID) -> Cliente:
        cliente = (await self.session.execute(
            select(Cliente).where(
                Cliente.id == cliente_id,
                Cliente.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()
        if cliente is None:
            raise ValueError(
                f"Cliente {cliente_id} não encontrado para empresa {self.empresa_id}"
            )
        return cliente

    async def _carregar_credencial(
        self, credencial_id: UUID
    ) -> CredencialIntegracao | None:
        return (await self.session.execute(
            select(CredencialIntegracao).where(
                CredencialIntegracao.id == credencial_id,
                CredencialIntegracao.empresa_id == self.empresa_id,
            )
        )).scalar_one_or_none()

    def _status_credencial(self, cred: CredencialIntegracao) -> str:
        """Lê status_whatsapp do JSONB, default `ativo` se ausente."""
        return (cred.config or {}).get("status_whatsapp", STATUS_ATIVO)

    async def _escolher_numero_para_novo_cliente(
        self, excluir: UUID | None = None,
    ) -> UUID:
        """Implementa o algoritmo de balanceamento por carga.

        1. Lista credenciais ativas da empresa (categoria='whatsapp').
        2. Calcula contagem de clientes por credencial via subquery.
        3. Ordena: menor contagem primeiro; em caso de empate, `eh_principal=true`
           primeiro; em segundo desempate, ordem alfabética de `instance_id`
           pra determinismo.
        """
        # Pega ativas e em ordem alfabética por instance_id pra estabilidade
        # nos testes.
        stmt = select(CredencialIntegracao).where(
            CredencialIntegracao.empresa_id == self.empresa_id,
            CredencialIntegracao.categoria == "whatsapp",
            CredencialIntegracao.ativo.is_(True),
        )
        if excluir is not None:
            stmt = stmt.where(CredencialIntegracao.id != excluir)

        candidatos = list((await self.session.execute(stmt)).scalars().all())

        # Filtra por status_whatsapp='ativo' no JSONB (não tem como filtrar
        # eficientemente na query sem expressão; em volume baixo (poucos
        # números por empresa) filtrar em Python é OK).
        candidatos = [
            c for c in candidatos
            if self._status_credencial(c) == STATUS_ATIVO
        ]
        if not candidatos:
            raise NenhumNumeroAtivoError(
                f"Empresa {self.empresa_id} sem número WhatsApp ativo"
            )

        # Contagens em batch
        ids = [c.id for c in candidatos]
        contagens_stmt = (
            select(
                Cliente.numero_origem_id,
                func.count(Cliente.id).label("total"),
            )
            .where(
                Cliente.empresa_id == self.empresa_id,
                Cliente.excluido_em.is_(None),
                Cliente.numero_origem_id.in_(ids),
            )
            .group_by(Cliente.numero_origem_id)
        )
        contagens = {
            row[0]: row[1]
            for row in (await self.session.execute(contagens_stmt)).all()
        }

        def _chave_ordenacao(cred: CredencialIntegracao) -> tuple:
            cnt = int(contagens.get(cred.id, 0))
            eh_principal = (cred.config or {}).get("eh_principal", False)
            instance_id = (cred.config or {}).get("instance_id", "") or ""
            return (cnt, 0 if eh_principal else 1, instance_id)

        candidatos.sort(key=_chave_ordenacao)
        escolhido = candidatos[0]
        log.debug(
            "numero_escolhido",
            empresa_id=str(self.empresa_id),
            credencial_id=str(escolhido.id),
            contagem=int(contagens.get(escolhido.id, 0)),
            eh_principal=(escolhido.config or {}).get("eh_principal", False),
        )
        return escolhido.id
