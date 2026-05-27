"""Máquina de estados do contrato (Story 13.2).

Define o enum `SituacaoContrato` e o grafo de transições válidas. Esta é a
fonte da verdade — qualquer mudança de `status` deve passar por
`ServicoSituacaoContrato.transicionar()` para validar contra este grafo.

**Nota terminológica:** o glossário (`docs/glossario-ptbr.md`) define que
"contrato ativo" → `vigente` (não "ativo") para evitar ambiguidade com
`ativo` (asset, no sentido de "ativo financeiro"). Por isso mantemos
`vigente` aqui, divergindo da nomenclatura genérica da Story 13.2.

Os 8 estados:

- `rascunho`              — contrato criado mas ainda não ativado
- `vigente`               — em uso, gerando títulos
- `suspenso`              — pausado por inadimplência; reversível
- `encerrado_sem_pendencia` — finalizado regularmente (sem dívidas)
- `encerrado_com_pendencia` — finalizado com dívida residual
- `encerrado_compra`      — terminou pela opção de compra (parcela final paga)
- `rescindido`            — terminado por rescisão formal
- `cancelado`             — cancelamento de rascunho (nunca foi ativado)
"""

from __future__ import annotations

from enum import StrEnum


class SituacaoContrato(StrEnum):
    RASCUNHO = "rascunho"
    VIGENTE = "vigente"
    SUSPENSO = "suspenso"
    ENCERRADO_SEM_PENDENCIA = "encerrado_sem_pendencia"
    ENCERRADO_COM_PENDENCIA = "encerrado_com_pendencia"
    ENCERRADO_COMPRA = "encerrado_compra"
    RESCINDIDO = "rescindido"
    CANCELADO = "cancelado"


# Grafo de transições válidas. Chave = origem; valor = set de destinos permitidos.
ALLOWED_TRANSITIONS: dict[SituacaoContrato, frozenset[SituacaoContrato]] = {
    SituacaoContrato.RASCUNHO: frozenset({
        SituacaoContrato.VIGENTE,         # ativação
        SituacaoContrato.CANCELADO,       # descarte do rascunho
    }),
    SituacaoContrato.VIGENTE: frozenset({
        SituacaoContrato.SUSPENSO,                  # motor 13.8 ou ação humana
        SituacaoContrato.ENCERRADO_SEM_PENDENCIA,   # cancelamento limpo
        SituacaoContrato.ENCERRADO_COM_PENDENCIA,   # cancelamento com dívida
        SituacaoContrato.ENCERRADO_COMPRA,          # opção de compra exercida
        SituacaoContrato.RESCINDIDO,                # rescisão formal
    }),
    SituacaoContrato.SUSPENSO: frozenset({
        SituacaoContrato.VIGENTE,                   # pagamento ou desbloqueio em confiança
        SituacaoContrato.ENCERRADO_COM_PENDENCIA,   # inadimplência crônica
        SituacaoContrato.RESCINDIDO,                # rescisão durante suspensão
    }),
    # Estados terminais — nada sai deles
    SituacaoContrato.ENCERRADO_SEM_PENDENCIA: frozenset(),
    SituacaoContrato.ENCERRADO_COM_PENDENCIA: frozenset(),
    SituacaoContrato.ENCERRADO_COMPRA: frozenset(),
    SituacaoContrato.RESCINDIDO: frozenset(),
    SituacaoContrato.CANCELADO: frozenset(),
}


SITUACOES_ATIVAS: frozenset[SituacaoContrato] = frozenset({
    SituacaoContrato.VIGENTE,
})


SITUACOES_TERMINAIS: frozenset[SituacaoContrato] = frozenset({
    SituacaoContrato.ENCERRADO_SEM_PENDENCIA,
    SituacaoContrato.ENCERRADO_COM_PENDENCIA,
    SituacaoContrato.ENCERRADO_COMPRA,
    SituacaoContrato.RESCINDIDO,
    SituacaoContrato.CANCELADO,
})


# Estados em que o motor `gerar_titulos_mensais` NÃO deve gerar novas parcelas.
# Inclui rascunho, suspenso, e todos os terminais.
SITUACOES_INATIVAS_GERACAO: frozenset[SituacaoContrato] = (
    SITUACOES_TERMINAIS | frozenset({SituacaoContrato.RASCUNHO, SituacaoContrato.SUSPENSO})
)


class TransicaoInvalidaError(Exception):
    """Levantada quando uma transição não é permitida pelo grafo."""

    def __init__(self, origem: str, destino: str):
        super().__init__(
            f"Transição inválida: '{origem}' → '{destino}'. "
            f"Permitidas de '{origem}': "
            f"{sorted(s.value for s in ALLOWED_TRANSITIONS.get(SituacaoContrato(origem), frozenset()))}"
        )
        self.origem = origem
        self.destino = destino


def transicao_permitida(origem: str, destino: str) -> bool:
    """Checa se a transição é válida. Aceita string ou enum nos dois lados.

    Levanta `ValueError` (não `TransicaoInvalidaError`) se algum dos valores
    não for uma situação reconhecida — diferente de "transição inválida".
    """
    try:
        o = SituacaoContrato(origem)
        d = SituacaoContrato(destino)
    except ValueError as e:
        raise ValueError(f"Situação desconhecida: {e}") from e
    return d in ALLOWED_TRANSITIONS.get(o, frozenset())
