"""FakeWhatsAppChannel — adapter que escreve cada mensagem em arquivo.

Substitui Z-API/Evolution/Uazapi durante a auditoria. Cada `send_text`,
`send_media`, `send_buttons_reply`, `send_button_pix` gera um arquivo
único em `/tmp/whatsapp_envios/{timestamp}-{numero}-{tipo}.txt`.

Permite auditar a cobrança sem Evolution Go ativo. Implementa o port
`IMessageChannel` + os métodos extras que o EvolutionGoAdapter expõe
(usados pelo lembrete com botão "Confirmo recebimento").
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.domain.ports.message_channel import (
    ChannelHealth,
    InboundMessage,
    MessageReceipt,
)


PASTA_ENVIOS = Path("/tmp/whatsapp_envios")


@dataclass(frozen=True)
class BotaoReply:
    id: str
    titulo: str


@dataclass(frozen=True)
class BotaoPix:
    nome_recebedor: str
    chave_pix: str
    tipo_chave: str
    moeda: str = "BRL"


@dataclass(frozen=True)
class SecaoLista:
    titulo: str
    linhas: list[dict[str, str]]


class FakeWhatsAppChannel:
    """Drop-in pra IMessageChannel + métodos do EvolutionGoAdapter."""

    channel_type = "whatsapp"
    provider_name = "fake_whatsapp"
    display_name = "WhatsApp (Fake — auditoria)"

    def __init__(self, instance_id: str = "fake-instance-001") -> None:
        self.instance_id = instance_id
        self.instance_token = "fake-token"
        os.makedirs(PASTA_ENVIOS, exist_ok=True)

    # ── helpers ─────────────────────────────────────────────────

    def _gravar(self, telefone: str, tipo: str, conteudo: str) -> str:
        msg_id = str(uuid4())
        agora = datetime.now(timezone.utc)
        carimbo = agora.strftime("%Y-%m-%d_%H-%M-%S-%f")
        nome = f"{carimbo}_{telefone}_{tipo}_{msg_id[:8]}.txt"
        path = PASTA_ENVIOS / nome
        cabecalho = (
            f"=== ENVIO WHATSAPP ===\n"
            f"timestamp_utc: {agora.isoformat()}\n"
            f"para:          {telefone}\n"
            f"tipo:          {tipo}\n"
            f"message_id:    {msg_id}\n"
            f"instance_id:   {self.instance_id}\n"
            f"---\n"
        )
        path.write_text(cabecalho + conteudo, encoding="utf-8")
        return msg_id

    # ── IMessageChannel ─────────────────────────────────────────

    async def send_text(self, to: str, text: str) -> MessageReceipt:
        msg_id = self._gravar(to, "texto", text)
        return MessageReceipt(
            provider_message_id=msg_id,
            channel_type=self.channel_type,
            sent_at=datetime.now(timezone.utc),
        )

    async def send_media(
        self,
        to: str,
        media_url: str,
        caption: str = "",
        mime_type: str = "application/octet-stream",
    ) -> MessageReceipt:
        conteudo = (
            f"media_url:  {media_url}\n"
            f"mime_type:  {mime_type}\n"
            f"caption:\n{caption}\n"
        )
        msg_id = self._gravar(to, "midia", conteudo)
        return MessageReceipt(
            provider_message_id=msg_id,
            channel_type=self.channel_type,
            sent_at=datetime.now(timezone.utc),
        )

    async def parse_webhook(self, payload: dict[str, Any]) -> InboundMessage | None:
        return None  # auditoria não recebe webhook

    async def health_check(self) -> ChannelHealth:
        return ChannelHealth(
            channel_type=self.channel_type,
            provider=self.provider_name,
            is_healthy=True,
            latency_ms=0.0,
            message="fake — auditoria",
            checked_at=datetime.now(timezone.utc),
        )

    # ── métodos do EvolutionGoAdapter (Story 13.22) ────────────

    async def send_buttons_reply(
        self,
        phone: str,
        descricao: str,
        botoes: list[BotaoReply],
        titulo: str = "",
        rodape: str = "",
    ) -> dict[str, Any]:
        botoes_txt = "\n".join(
            f"  [{b.id}] {b.titulo}" for b in botoes
        )
        conteudo = (
            f"titulo:    {titulo}\n"
            f"descricao:\n{descricao}\n"
            f"botoes:\n{botoes_txt}\n"
            f"rodape:    {rodape}\n"
        )
        msg_id = self._gravar(phone, "botoes_reply", conteudo)
        return {"ok": True, "msg_id": msg_id}

    async def send_button_pix(
        self,
        phone: str,
        descricao: str,
        botao_pix: BotaoPix,
        titulo: str = "Pagamento PIX",
        rodape: str = "",
    ) -> dict[str, Any]:
        conteudo = (
            f"titulo:    {titulo}\n"
            f"descricao:\n{descricao}\n"
            f"botao_pix:\n"
            f"  recebedor:    {botao_pix.nome_recebedor}\n"
            f"  chave:        {botao_pix.chave_pix}\n"
            f"  tipo_chave:   {botao_pix.tipo_chave}\n"
            f"  moeda:        {botao_pix.moeda}\n"
            f"rodape:    {rodape}\n"
        )
        msg_id = self._gravar(phone, "botao_pix", conteudo)
        return {"ok": True, "msg_id": msg_id}

    async def send_list(
        self,
        phone: str,
        descricao: str,
        secoes: list[SecaoLista],
        titulo: str = "",
        texto_botao: str = "Ver opções",
        rodape: str = "",
    ) -> dict[str, Any]:
        secoes_txt = []
        for s in secoes:
            linhas_txt = "\n".join(
                f"    [{l.get('id')}] {l.get('title')}" for l in s.linhas
            )
            secoes_txt.append(f"  {s.titulo}:\n{linhas_txt}")
        conteudo = (
            f"titulo:       {titulo}\n"
            f"descricao:\n{descricao}\n"
            f"botao_acao:   {texto_botao}\n"
            f"secoes:\n"
            + "\n".join(secoes_txt)
            + f"\nrodape:       {rodape}\n"
        )
        msg_id = self._gravar(phone, "lista", conteudo)
        return {"ok": True, "msg_id": msg_id}
