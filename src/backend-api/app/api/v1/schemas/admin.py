from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator


# --- Integrations ---
class IntegrationOut(BaseModel):
    id: str
    category: str
    provider: str
    is_active: bool
    config: dict = {}
    status: str
    last_health_check: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class IntegrationCreate(BaseModel):
    category: str
    provider: str
    config: dict = {}
    is_active: bool = True

    @field_validator("category")
    @classmethod
    def _bloqueia_whatsapp_no_endpoint_generico(cls, v: str) -> str:
        """WhatsApp tem endpoint dedicado (`POST /numeros-cobranca`) porque
        cada credencial é uma INSTÂNCIA (número), não um provedor único.
        Cadastrar via `/admin/integrations` mistura responsabilidades."""
        if v == "whatsapp":
            raise ValueError(
                "Use POST /numeros-cobranca para cadastrar números WhatsApp. "
                "A tela Integrações trata provedores singulares (LLM, GPS, "
                "Pagamento etc.); WhatsApp tem tela dedicada em Canais."
            )
        return v


class IntegrationUpdate(BaseModel):
    provider: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class IntegrationTestResult(BaseModel):
    integration_id: str
    status: str  # healthy | error
    latency_ms: float | None = None
    error: str | None = None


# --- Audit Log ---
class AuditLogEntryOut(BaseModel):
    id: int
    user_id: str | None = None
    action: str
    entity: str | None = None
    entity_id: str | None = None
    payload_before: dict | None = None
    payload_after: dict | None = None
    ip: str | None = None
    user_agent: str | None = None
    correlation_id: str | None = None
    module: str | None = None
    category: str
    severity: str
    hmac_valid: bool = True
    created_at: datetime

    model_config = {"from_attributes": True}


class AuditLogSearchResponse(BaseModel):
    items: list[AuditLogEntryOut]
    total: int
    page: int
    size: int


# --- Modules ---
class ModuleOut(BaseModel):
    module_id: str
    is_active: bool
    config: dict | None = None
    registered_at: datetime

    model_config = {"from_attributes": True}


class ModuleUpdate(BaseModel):
    is_active: bool | None = None
    config: dict | None = None


class ModuleHookOut(BaseModel):
    id: str
    module_id: str
    event_type: str
    policy: dict | None = None
    is_active: bool

    model_config = {"from_attributes": True}


# --- Settings ---
class SystemSettingOut(BaseModel):
    key: str
    value: dict
    updated_at: datetime

    model_config = {"from_attributes": True}


class SystemSettingUpdate(BaseModel):
    settings: dict[str, dict]


# --- Backup ---
class BackupOut(BaseModel):
    name: str
    size: int | None = None
    created_at: str | None = None


class BackupTriggerResponse(BaseModel):
    task_id: str
    message: str


# --- Metrics ---
class SystemMetricsOut(BaseModel):
    db_pool_size: int = 0
    db_pool_checked_out: int = 0
    redis_connected_clients: int = 0
    redis_used_memory_mb: float = 0
    celery_active_tasks: int = 0
    celery_reserved_tasks: int = 0


# --- Global Search ---
class SearchResultItem(BaseModel):
    id: str
    type: str  # customer | vehicle | contract
    title: str
    subtitle: str | None = None
    url: str


class GlobalSearchResponse(BaseModel):
    results: list[SearchResultItem]
    total: int


# --- LGPD ---
class AnonymizeRequest(BaseModel):
    reason: str


class AnonymizeResponse(BaseModel):
    message: str
    customer_id: str
