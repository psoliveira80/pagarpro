# Messaging Channels — Architecture Guide

## Overview

O sistema usa uma arquitetura de **canais plugáveis** para mensageria. Cada canal (WhatsApp, Email, SMS, Telegram) é um adapter que implementa a interface `IMessageChannel`.

## Interface: `IMessageChannel`

**Arquivo:** `src/backend-api/app/domain/ports/message_channel.py`

```python
class IMessageChannel(Protocol):
    @property
    def channel_type(self) -> str:
        """'whatsapp', 'email', 'sms', 'telegram'"""

    @property
    def provider_name(self) -> str:
        """'zapi', 'evolution_api', 'smtp', 'twilio'"""

    @property
    def display_name(self) -> str:
        """'WhatsApp (Z-API)', 'E-mail (SMTP)'"""

    async def send_text(self, to: str, text: str) -> MessageReceipt
    async def send_media(self, to: str, media_url: str, caption: str) -> MessageReceipt
    async def parse_webhook(self, payload: dict) -> InboundMessage
    async def health_check(self) -> ChannelHealth
```

## Como adicionar um novo canal

### 1. Crie o adapter

```python
# src/backend-api/app/infrastructure/adapters/sms/twilio_adapter.py

class TwilioSmsChannel:
    channel_type = "sms"
    provider_name = "twilio"
    display_name = "SMS (Twilio)"

    def __init__(self, account_sid: str, auth_token: str, from_number: str):
        self._sid = account_sid
        self._token = auth_token
        self._from = from_number

    async def send_text(self, to: str, text: str) -> MessageReceipt:
        # Implementar chamada à API Twilio
        ...

    async def send_media(self, to: str, media_url: str, caption: str) -> MessageReceipt:
        # Implementar MMS ou fallback
        ...

    async def parse_webhook(self, payload: dict) -> InboundMessage:
        # Normalizar webhook do Twilio
        ...

    async def health_check(self) -> ChannelHealth:
        # GET https://api.twilio.com/2010-04-01/Accounts/{sid}.json
        # Retorna ChannelHealth com is_healthy e latency_ms
        ...
```

### 2. Registre no startup

```python
# src/backend-api/app/main.py (lifespan)

from app.core.channels.registry import channel_registry
from app.infrastructure.adapters.sms.twilio_adapter import TwilioSmsChannel

# Lê credenciais do integration_credentials ou settings
channel_registry.register(TwilioSmsChannel(
    account_sid="...",
    auth_token="...",
    from_number="+55...",
))
```

### 3. O canal aparece automaticamente

- **API:** `GET /broadcasts/channels` retorna o novo canal com status
- **Frontend:** O Step 2 do wizard de envio mostra o canal como opção selecionável
- **Health:** `GET /broadcasts/channel-status` inclui o novo canal

## Channel Registry

**Arquivo:** `src/backend-api/app/core/channels/registry.py`

```python
from app.core.channels.registry import channel_registry

# Registrar
channel_registry.register(my_adapter)

# Buscar por tipo
whatsapp_channels = channel_registry.get_channels_by_type("whatsapp")

# Health check de todos
statuses = await channel_registry.health_check_all()

# Tipos disponíveis
types = channel_registry.list_available_types()  # ["whatsapp"]
```

## Canais implementados (V1)

| Canal | Provider | Adapter | Status |
|-------|----------|---------|--------|
| WhatsApp | Z-API | `ZapiAdapter` → `WhatsAppChannelWrapper` | Implementado |
| WhatsApp | Uazapi | `UazapiAdapter` → `WhatsAppChannelWrapper` | Implementado |
| WhatsApp | Evolution API | `EvolutionApiAdapter` → `WhatsAppChannelWrapper` | Implementado |
| E-mail | SMTP | — | Planejado |
| SMS | — | — | Planejado |
| Telegram | — | — | Planejado |

## Data Types

```python
@dataclass(frozen=True)
class MessageReceipt:
    provider_message_id: str
    channel_type: str
    sent_at: datetime

@dataclass(frozen=True)
class InboundMessage:
    channel_type: str
    provider: str
    from_address: str       # telefone, email, etc
    to_address: str
    body: str
    media_url: str | None
    message_id: str
    timestamp: datetime
    raw_payload: dict

@dataclass(frozen=True)
class ChannelHealth:
    channel_type: str
    provider: str
    is_healthy: bool
    latency_ms: float | None
    message: str
    checked_at: datetime
```

## Segurança

- Credenciais armazenadas em `integration_credentials.config` (JSONB) — nunca em código
- Health check roda no máximo a cada 60s (cache)
- Webhooks validam assinatura/token do provider antes de processar
