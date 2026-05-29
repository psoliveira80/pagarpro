"""Adapter Evolution Go (Story 13.21).

Evolution Go (https://evo-go.megaflow.work/) é um gateway WhatsApp em Go que
abstrai o protocolo via biblioteca `whatsmeow`. Topologia A: o provedor SaaS
(Pablo) hospeda 1 Evolution Go central; cada empresa cliente do FrotaUber tem
1+ instâncias dentro desse Evolution Go.

Endpoints utilizados:
- `POST /send/text` — texto simples (usa `instance_token`)
- `POST /send/button` — botões interativos (reply / pix / url / call / copy)
- `POST /send/list` — menu em formato de lista (até N rows)
- `POST /send/media` — imagem / vídeo / áudio / documento via URL
- `POST /message/downloadmedia` — fallback para baixar mídia inbound
- `GET /instance/status` — health check da instância (usa `instance_token`)

Autenticação: header `apikey`. Para enviar mensagens usa o `instance_token`
específico da empresa. Para administração de instâncias (não implementado
neste adapter; fica fora do escopo do FrotaUber por decisão arquitetural)
usaria o `EVOLUTION_GO_ADMIN_TOKEN` global.

Webhook recebido em `/api/v1/webhooks/whatsapp/evolution_go` é processado por
`parse_webhook`, que converte o payload do Evolution Go (estrutura
`{event, data: {Info, Message}, instanceId, instanceToken}`) em
`ReceivedMessage` ou `MessageStatusUpdate`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import httpx
import structlog

from app.domain.ports.whatsapp_gateway import (
    MessageStatusUpdate,
    ReceivedMessage,
)


log = structlog.get_logger()


# ───────────────────────── Erros específicos ──────────────────────────


class EvolutionGoBanidoError(Exception):
    """Levantada quando o Evolution Go indica que a instância foi banida
    ou a sessão foi forçadamente desconectada por violação. O caller
    (`ServicoRoteamentoNumeros`) usa isso para marcar a credencial como
    `status_whatsapp='banido'` e migrar os clientes.
    """

    def __init__(self, mensagem: str, codigo_http: int | None = None):
        super().__init__(mensagem)
        self.codigo_http = codigo_http


class EvolutionGoErroEnvio(Exception):
    """Erro genérico de envio (timeout, 5xx, payload inválido)."""


# ─────────────────────── DTOs internos ────────────────────────────────


@dataclass(frozen=True)
class BotaoReply:
    """Botão tipo `reply` no Evolution Go (até 3 por mensagem)."""
    id: str
    titulo: str  # max 20 chars (Evolution Go trunca)


@dataclass(frozen=True)
class BotaoPix:
    """Botão tipo `pix` que renderiza QR Code nativo no WhatsApp.

    **Regra:** botão `pix` precisa ser o ÚNICO botão da mensagem
    (não mistura com `reply`/`url`/`call`/`copy`).
    """
    nome_recebedor: str
    chave_pix: str
    tipo_chave: str  # phone | email | cpf | cnpj | random
    moeda: str = "BRL"


@dataclass(frozen=True)
class SecaoLista:
    """Seção de uma mensagem `/send/list`."""
    titulo: str
    linhas: list[dict[str, str]]  # [{ id, title, description }]


# ─────────────────────────── Adapter ──────────────────────────────────


class EvolutionGoAdapter:
    """Implementa `IWhatsAppGateway` para o gateway Evolution Go.

    Cada instância do adapter representa **uma** instância do Evolution Go
    (= um número de telefone da empresa cliente).
    """

    def __init__(
        self,
        api_url: str,
        instance_token: str,
        instance_id: str | None = None,
        timeout_segundos: float = 15.0,
    ):
        self.api_url = api_url.rstrip("/")
        self.instance_token = instance_token
        self.instance_id = instance_id
        self.timeout = timeout_segundos

    # ── Helpers HTTP ───────────────────────────────────────────────

    def _headers(self) -> dict[str, str]:
        return {
            "apikey": self.instance_token,
            "Content-Type": "application/json",
        }

    async def _post(self, path: str, body: dict[str, Any]) -> dict[str, Any]:
        """POST autenticado; trata 401/403 como ban."""
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(
                    f"{self.api_url}{path}",
                    headers=self._headers(),
                    json=body,
                )
            except httpx.RequestError as exc:
                raise EvolutionGoErroEnvio(
                    f"Falha de rede ao chamar Evolution Go: {exc}"
                ) from exc

        if response.status_code in (401, 403):
            # Sessão inválida / instância banida — caller decide reatribuir.
            raise EvolutionGoBanidoError(
                f"Evolution Go retornou {response.status_code}: {response.text[:200]}",
                codigo_http=response.status_code,
            )
        if response.status_code >= 500:
            raise EvolutionGoErroEnvio(
                f"Erro {response.status_code} no Evolution Go: {response.text[:200]}"
            )
        if response.status_code >= 400:
            raise EvolutionGoErroEnvio(
                f"Payload rejeitado por Evolution Go ({response.status_code}): {response.text[:200]}"
            )

        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    async def _get(self, path: str) -> dict[str, Any]:
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(
                    f"{self.api_url}{path}",
                    headers=self._headers(),
                )
            except httpx.RequestError as exc:
                raise EvolutionGoErroEnvio(
                    f"Falha de rede no GET {path}: {exc}"
                ) from exc

        if response.status_code in (401, 403):
            raise EvolutionGoBanidoError(
                f"GET {path} retornou {response.status_code}",
                codigo_http=response.status_code,
            )
        if response.status_code >= 400:
            raise EvolutionGoErroEnvio(
                f"GET {path} falhou {response.status_code}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError:
            return {"raw": response.text}

    @staticmethod
    def _so_digitos(numero: str) -> str:
        """Evolution Go espera número apenas com dígitos (sem +)."""
        return "".join(c for c in numero if c.isdigit())

    # ── Envio ──────────────────────────────────────────────────────

    async def send_text(self, phone: str, text: str) -> dict[str, Any]:
        """Envia mensagem de texto. Compatível com `IWhatsAppGateway`."""
        body = {
            "number": self._so_digitos(phone),
            "text": text,
            "delay": 0,
        }
        return await self._post("/send/text", body)

    async def send_template(
        self, phone: str, template_name: str, params: dict[str, str]
    ) -> dict[str, Any]:
        """Evolution Go não tem templates externos do WhatsApp Business API.

        O sistema renderiza templates internamente (Story 13.10 — `RenderizadorTemplate`)
        e envia como texto puro via `send_text`. Esta função existe para satisfazer
        `IWhatsAppGateway`; renderiza placeholder simples e delega.
        """
        texto = (template_name + "\n" + "\n".join(
            f"{k}={v}" for k, v in (params or {}).items()
        )).strip()
        return await self.send_text(phone, texto)

    async def send_media(
        self,
        phone: str,
        media_url: str,
        mime_type: str,
        caption: str | None = None,
    ) -> dict[str, Any]:
        """Envia mídia via URL. Evolution Go aceita imagem/vídeo/áudio/documento."""
        # Detecta o tipo a partir do mime
        if mime_type.startswith("image/"):
            tipo = "image"
        elif mime_type.startswith("video/"):
            tipo = "video"
        elif mime_type.startswith("audio/"):
            tipo = "audio"
        else:
            tipo = "document"

        body: dict[str, Any] = {
            "number": self._so_digitos(phone),
            "mediaUrl": media_url,
            "mediatype": tipo,
            "delay": 0,
        }
        if caption:
            body["caption"] = caption
        return await self._post("/send/media", body)

    async def send_buttons_reply(
        self,
        phone: str,
        descricao: str,
        botoes: list[BotaoReply],
        titulo: str = "",
        rodape: str = "",
    ) -> dict[str, Any]:
        """Envia mensagem com botões de resposta (`reply`).

        Limite WhatsApp: 3 botões. Se vier mais, trunca os primeiros 3.
        Story 13.22 (state machine) usa para o menu rígido.
        """
        if not botoes:
            raise ValueError("send_buttons_reply requer ao menos 1 botão")
        if len(botoes) > 3:
            log.warning("send_buttons_reply.truncando_para_3", originais=len(botoes))
            botoes = botoes[:3]

        body = {
            "number": self._so_digitos(phone),
            "title": titulo,
            "description": descricao,
            "footer": rodape,
            "buttons": [
                {
                    "type": "reply",
                    "displayText": b.titulo[:20],  # WhatsApp trunca em 20
                    "id": b.id,
                }
                for b in botoes
            ],
            "delay": 0,
        }
        return await self._post("/send/button", body)

    async def send_button_pix(
        self,
        phone: str,
        descricao: str,
        botao_pix: BotaoPix,
        titulo: str = "Pagamento PIX",
        rodape: str = "",
    ) -> dict[str, Any]:
        """Envia botão PIX nativo do Evolution Go.

        **CRÍTICO:** botão PIX é o único botão da mensagem (regra do WhatsApp).
        Story 13.22 usa quando cliente clica "💰 Gerar QR Code".
        """
        body = {
            "number": self._so_digitos(phone),
            "title": titulo,
            "description": descricao,
            "footer": rodape,
            "buttons": [
                {
                    "type": "pix",
                    "currency": botao_pix.moeda,
                    "name": botao_pix.nome_recebedor,
                    "keyType": botao_pix.tipo_chave,
                    "key": botao_pix.chave_pix,
                }
            ],
            "delay": 0,
        }
        return await self._post("/send/button", body)

    async def send_list(
        self,
        phone: str,
        descricao: str,
        secoes: list[SecaoLista],
        titulo: str = "",
        texto_botao: str = "Ver opções",
        rodape: str = "",
    ) -> dict[str, Any]:
        """Envia menu em lista (mais de 3 opções). Cada seção tem N linhas."""
        body = {
            "number": self._so_digitos(phone),
            "title": titulo,
            "description": descricao,
            "buttonText": texto_botao,
            "footerText": rodape,
            "sections": [
                {"title": s.titulo, "rows": s.linhas}
                for s in secoes
            ],
            "delay": 0,
        }
        return await self._post("/send/list", body)

    # ── Webhook (inbound) ─────────────────────────────────────────

    async def parse_webhook(
        self, headers: dict[str, str], body: dict[str, Any]
    ) -> ReceivedMessage | MessageStatusUpdate | None:
        """Converte payload Evolution Go em DTO normalizado.

        Estrutura do payload:
        ```
        {
          "event": "Message" | "Receipt" | "PairSuccess" | "LoggedOut",
          "instanceId": "...",
          "instanceToken": "...",
          "data": {
            "Info": { ID, Chat, Sender, IsFromMe, IsGroup, PushName, Type, Timestamp },
            "Message": { conversation | extendedTextMessage | imageMessage | ... }
            "mediaUrl": "https://...?"
          }
        }
        ```
        """
        evento = body.get("event")

        if evento == "Receipt":
            data = body.get("data") or {}
            return MessageStatusUpdate(
                external_id=data.get("messageId") or data.get("ID", ""),
                status=_normalizar_status(data.get("status")),
                timestamp=data.get("timestamp"),
            )

        if evento != "Message":
            # PairSuccess, LoggedOut, etc. — não são mensagens
            return None

        data = body.get("data") or {}
        info = data.get("Info") or {}
        message = data.get("Message") or {}

        if not info or not message:
            return None

        # Ignora mensagens de grupo (FrotaUber só atende 1:1)
        if info.get("IsGroup"):
            return None

        # Ignora mensagens enviadas pelo próprio número
        if info.get("IsFromMe"):
            return None

        jid = info.get("Chat") or info.get("Sender") or ""
        sender_phone = _telefone_de_jid(jid)
        if not sender_phone:
            return None

        # Extrai texto (vários formatos possíveis)
        texto = _extrair_texto(message)

        # Mídia já vem processada na raiz do data (mediaUrl)
        media_url = data.get("mediaUrl") or _extrair_media_url(message)
        media_mime = _extrair_mime(message)

        eh_audio = bool(message.get("audioMessage"))

        return ReceivedMessage(
            sender_phone=sender_phone,
            text=texto,
            media_url=media_url,
            media_mime=media_mime,
            timestamp=info.get("Timestamp"),
            external_id=info.get("ID"),
            is_audio=eh_audio,
            raw_payload=body,
        )

    # ── Health check ──────────────────────────────────────────────

    async def health_check(self) -> dict[str, Any]:
        """Consulta status da instância no Evolution Go.

        Retorna dict com `connected: bool` e detalhes. Caller decide se
        precisa marcar como `banido` ou `desconectado`.
        """
        try:
            return await self._get("/instance/status")
        except EvolutionGoBanidoError:
            return {"connected": False, "banido": True}
        except EvolutionGoErroEnvio as exc:
            return {"connected": False, "erro": str(exc)}


# ──────────────────────── Helpers ─────────────────────────────────────


def _telefone_de_jid(jid: str) -> str:
    """Extrai número do JID Evolution Go: `5511987654321@s.whatsapp.net`."""
    if not jid:
        return ""
    parte = jid.split("@", 1)[0]
    # Remove sufixo de device opcional (`:N`)
    if ":" in parte:
        parte = parte.split(":", 1)[0]
    # Só dígitos
    return "".join(c for c in parte if c.isdigit())


def _extrair_texto(message: dict[str, Any]) -> str | None:
    """Extrai texto da mensagem em qualquer formato."""
    # Texto simples
    if isinstance(message.get("conversation"), str):
        return message["conversation"]
    # Texto estendido (com formatação/menções)
    ext = message.get("extendedTextMessage")
    if isinstance(ext, dict) and ext.get("text"):
        return ext["text"]
    # Caption de mídia
    for tipo in ("imageMessage", "videoMessage", "documentMessage"):
        m = message.get(tipo)
        if isinstance(m, dict) and m.get("caption"):
            return m["caption"]
    # Clique em botão (Story 13.22 usa o ID retornado aqui)
    btn = message.get("buttonsResponseMessage")
    if isinstance(btn, dict) and btn.get("selectedButtonId"):
        return f"__btn__:{btn['selectedButtonId']}"
    # Clique em row de lista
    lst = message.get("listResponseMessage")
    if isinstance(lst, dict):
        single = lst.get("singleSelectReply") or {}
        if single.get("selectedRowId"):
            return f"__row__:{single['selectedRowId']}"
    return None


def _extrair_media_url(message: dict[str, Any]) -> str | None:
    for tipo in (
        "imageMessage",
        "videoMessage",
        "audioMessage",
        "documentMessage",
        "stickerMessage",
    ):
        m = message.get(tipo)
        if isinstance(m, dict) and m.get("mediaUrl"):
            return m["mediaUrl"]
    return None


def _extrair_mime(message: dict[str, Any]) -> str | None:
    for tipo in (
        "imageMessage",
        "videoMessage",
        "audioMessage",
        "documentMessage",
    ):
        m = message.get(tipo)
        if isinstance(m, dict) and m.get("mimetype"):
            return m["mimetype"]
    return None


def _normalizar_status(raw: str | None) -> str:
    if not raw:
        return "sent"
    raw = raw.lower()
    if "deliver" in raw:
        return "delivered"
    if "read" in raw or "lid" in raw:
        return "read"
    if "fail" in raw or "error" in raw:
        return "failed"
    return "sent"
