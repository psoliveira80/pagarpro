"""State machine do número rígido — Story 13.22.

Funções puras, sem I/O. State machine simples baseada em estados e
transições disparadas por inbound (clique de botão, mídia, texto).

Estados:
- `idle` — conversa em estado normal; cliente vê menu adaptativo ao mandar
  qualquer coisa.
- `aguardando_comprovante` — cliente clicou "Enviar comprovante". Mídia
  inbound nessa janela vira comprovante.
- `confirmando_adiamento` — cliente clicou "Adiar"; sistema pediu
  confirmação ([Sim] / [Não]).
- `confirmando_desbloqueio_confianca` — análogo.
- `confirmando_pagamento_parcial` — sistema pediu o valor do pagamento.

Eventos (entrada):
- `botao_clicado` (id do botão)
- `texto_livre` (qualquer texto)
- `midia_recebida` (foto/PDF)
- `timeout` (sistema percebeu expiração da janela aguardando_comprovante)

Saídas (decisão da máquina):
- `enviar_menu_principal`
- `enviar_qr_pix`
- `enviar_extrato`
- `iniciar_captura_comprovante`
- `processar_midia_como_comprovante`
- `aplicar_adiamento`
- `pedir_confirmacao_adiamento`
- `aplicar_desbloqueio_confianca`
- `pedir_confirmacao_desbloqueio`
- `aplicar_pagamento_parcial`
- `pedir_valor_parcial`
- `nao_entendeu` (responde com mensagem padrão + reenvia menu)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class EstadoMaquina(StrEnum):
    IDLE = "idle"
    AGUARDANDO_COMPROVANTE = "aguardando_comprovante"
    CONFIRMANDO_ADIAMENTO = "confirmando_adiamento"
    CONFIRMANDO_DESBLOQUEIO = "confirmando_desbloqueio_confianca"
    AGUARDANDO_VALOR_PARCIAL = "aguardando_valor_parcial"


class AcaoMaquina(StrEnum):
    ENVIAR_MENU = "enviar_menu"
    ENVIAR_QR_PIX = "enviar_qr_pix"
    ENVIAR_EXTRATO = "enviar_extrato"
    INICIAR_CAPTURA_COMPROVANTE = "iniciar_captura_comprovante"
    PROCESSAR_COMPROVANTE = "processar_comprovante"
    PEDIR_CONFIRMACAO_ADIAMENTO = "pedir_confirmacao_adiamento"
    APLICAR_ADIAMENTO = "aplicar_adiamento"
    PEDIR_CONFIRMACAO_DESBLOQUEIO = "pedir_confirmacao_desbloqueio"
    APLICAR_DESBLOQUEIO_CONFIANCA = "aplicar_desbloqueio_confianca"
    PEDIR_VALOR_PARCIAL = "pedir_valor_parcial"
    APLICAR_PAGAMENTO_PARCIAL = "aplicar_pagamento_parcial"
    REGISTRAR_CONFIRMACAO_RECEBIMENTO = "registrar_confirmacao_recebimento"
    INICIAR_ATENDIMENTO_IA = "iniciar_atendimento_ia"
    NAO_ENTENDEU = "nao_entendeu"
    IGNORAR = "ignorar"


# Prefixos de IDs de botão (state machine reconhece para decidir ação)
PREFIXO_MENU = "menu_"
ID_MENU_EXTRATO = "menu_extrato"
ID_MENU_PAGAR = "menu_pagar"
ID_MENU_COMPROVANTE = "menu_comprovante"
ID_MENU_ADIAR = "menu_adiar"
ID_MENU_DESBLOQUEIO = "menu_desbloqueio"
ID_MENU_PARCIAL = "menu_parcial"
ID_MENU_ATENDENTE = "menu_atendente"

PREFIXO_CONFIRMA = "confirma_"
ID_CONFIRMA_ADIAR_SIM = "confirma_adiar_sim"
ID_CONFIRMA_ADIAR_NAO = "confirma_adiar_nao"
ID_CONFIRMA_DESBLOQUEIO_SIM = "confirma_desbloqueio_sim"
ID_CONFIRMA_DESBLOQUEIO_NAO = "confirma_desbloqueio_nao"

PREFIXO_RECEBIMENTO = "confirma_recebimento_"


@dataclass(frozen=True)
class EntradaEvento:
    """Encapsula o que o sistema recebeu como entrada (inbound)."""
    tipo: str  # 'botao' | 'texto' | 'midia'
    botao_id: str | None = None
    texto: str | None = None
    tem_midia: bool = False
    midia_url: str | None = None


@dataclass(frozen=True)
class DecisaoMaquina:
    """Resultado puro da decisão da state machine."""
    acao: AcaoMaquina
    proximo_estado: EstadoMaquina
    parametros: dict | None = None


def decidir(
    estado_atual: EstadoMaquina,
    evento: EntradaEvento,
    ia_atendente_ativa: bool = False,
    aguardando_comprovante_valido: bool = False,
) -> DecisaoMaquina:
    """Decide próxima ação + estado a partir do estado atual + evento.

    Função pura. Não acessa banco. Caller (`process_inbound_whatsapp`) é
    quem aplica os efeitos (chama service, persiste estado).
    """

    # ── Mídia ────────────────────────────────────────────────────────
    if evento.tipo == "midia" and evento.tem_midia:
        if estado_atual == EstadoMaquina.AGUARDANDO_COMPROVANTE and aguardando_comprovante_valido:
            return DecisaoMaquina(
                acao=AcaoMaquina.PROCESSAR_COMPROVANTE,
                proximo_estado=EstadoMaquina.IDLE,
                parametros={"midia_url": evento.midia_url},
            )
        # Cliente mandou mídia fora do contexto — manda reenviar
        return DecisaoMaquina(
            acao=AcaoMaquina.ENVIAR_MENU,
            proximo_estado=EstadoMaquina.IDLE,
            parametros={"explicacao": "Use o botão *Enviar comprovante* antes de mandar a foto 👇"},
        )

    # ── Clique em botão ──────────────────────────────────────────────
    if evento.tipo == "botao" and evento.botao_id:
        bid = evento.botao_id

        # Confirmação de recebimento (lembrete — Story 13.25)
        if bid.startswith(PREFIXO_RECEBIMENTO):
            titulo_id = bid[len(PREFIXO_RECEBIMENTO):]
            return DecisaoMaquina(
                acao=AcaoMaquina.REGISTRAR_CONFIRMACAO_RECEBIMENTO,
                proximo_estado=EstadoMaquina.IDLE,
                parametros={"titulo_id": titulo_id},
            )

        # Botões do menu principal
        if bid == ID_MENU_EXTRATO:
            return DecisaoMaquina(AcaoMaquina.ENVIAR_EXTRATO, EstadoMaquina.IDLE)
        if bid == ID_MENU_PAGAR:
            return DecisaoMaquina(AcaoMaquina.ENVIAR_QR_PIX, EstadoMaquina.IDLE)
        if bid == ID_MENU_COMPROVANTE:
            return DecisaoMaquina(
                AcaoMaquina.INICIAR_CAPTURA_COMPROVANTE,
                EstadoMaquina.AGUARDANDO_COMPROVANTE,
            )
        if bid == ID_MENU_ADIAR:
            return DecisaoMaquina(
                AcaoMaquina.PEDIR_CONFIRMACAO_ADIAMENTO,
                EstadoMaquina.CONFIRMANDO_ADIAMENTO,
            )
        if bid == ID_MENU_DESBLOQUEIO:
            return DecisaoMaquina(
                AcaoMaquina.PEDIR_CONFIRMACAO_DESBLOQUEIO,
                EstadoMaquina.CONFIRMANDO_DESBLOQUEIO,
            )
        if bid == ID_MENU_PARCIAL:
            return DecisaoMaquina(
                AcaoMaquina.PEDIR_VALOR_PARCIAL,
                EstadoMaquina.AGUARDANDO_VALOR_PARCIAL,
            )
        if bid == ID_MENU_ATENDENTE and ia_atendente_ativa:
            return DecisaoMaquina(
                AcaoMaquina.INICIAR_ATENDIMENTO_IA,
                EstadoMaquina.IDLE,
            )

        # Confirmações
        if estado_atual == EstadoMaquina.CONFIRMANDO_ADIAMENTO:
            if bid == ID_CONFIRMA_ADIAR_SIM:
                return DecisaoMaquina(
                    AcaoMaquina.APLICAR_ADIAMENTO, EstadoMaquina.IDLE
                )
            if bid == ID_CONFIRMA_ADIAR_NAO:
                return DecisaoMaquina(AcaoMaquina.ENVIAR_MENU, EstadoMaquina.IDLE)

        if estado_atual == EstadoMaquina.CONFIRMANDO_DESBLOQUEIO:
            if bid == ID_CONFIRMA_DESBLOQUEIO_SIM:
                return DecisaoMaquina(
                    AcaoMaquina.APLICAR_DESBLOQUEIO_CONFIANCA,
                    EstadoMaquina.IDLE,
                )
            if bid == ID_CONFIRMA_DESBLOQUEIO_NAO:
                return DecisaoMaquina(AcaoMaquina.ENVIAR_MENU, EstadoMaquina.IDLE)

        # Botão desconhecido
        return DecisaoMaquina(AcaoMaquina.ENVIAR_MENU, EstadoMaquina.IDLE)

    # ── Texto livre ──────────────────────────────────────────────────
    if evento.tipo == "texto" and evento.texto:
        # Sistema só aceita texto livre no estado AGUARDANDO_VALOR_PARCIAL
        # (cliente digita o valor) ou quando IA atendente está ativa.
        if estado_atual == EstadoMaquina.AGUARDANDO_VALOR_PARCIAL:
            return DecisaoMaquina(
                AcaoMaquina.APLICAR_PAGAMENTO_PARCIAL,
                EstadoMaquina.IDLE,
                parametros={"texto_valor": evento.texto},
            )
        # IA está ativa? Encaminha
        if ia_atendente_ativa:
            return DecisaoMaquina(
                AcaoMaquina.INICIAR_ATENDIMENTO_IA, EstadoMaquina.IDLE
            )
        # Sem IA — texto livre vira "não entendi" + reenvia menu
        return DecisaoMaquina(AcaoMaquina.NAO_ENTENDEU, EstadoMaquina.IDLE)

    # ── Evento desconhecido ──────────────────────────────────────────
    return DecisaoMaquina(AcaoMaquina.IGNORAR, estado_atual)
