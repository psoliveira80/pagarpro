# Recurrence Engine & Automated Collection — Architecture

## 1. Geração Recorrente de Recebíveis

### Modalidade A: Geração Antecipada (já implementada)
Todos os títulos são gerados na criação do contrato via `schedule_calculator`. Usado quando o valor é fixo e não há correção monetária.

### Modalidade B: Geração Mensal com Correção
Títulos gerados mês a mês, aplicando índice de correção vigente.

**Campos necessários no contrato:**
```python
# Contract model — campos adicionais
correction_index: str | None     # "igpm", "ipca", "inpc", None
generation_mode: str             # "upfront" | "monthly"
generation_day: int              # dia do mês para gerar (1-28)
next_generation_date: date | None
```

**Celery Beat Task:** `generate_monthly_installments`
```
Executa: diariamente às 06:00
Para cada contrato com generation_mode="monthly" e next_generation_date <= hoje:
  1. Buscar índice de correção vigente (via API do BCB ou tabela local)
  2. Calcular valor corrigido: base_value * (1 + index_rate)
  3. Criar Installment com status="aberto", due_date=next_generation_date
  4. Avançar next_generation_date para o próximo mês
  5. Criar ContractEvent registrando a geração
```

**API Externa — BCB (Banco Central do Brasil):**
```
GET https://api.bcb.gov.br/dados/serie/bcdata.sgs.{serie}/dados/ultimos/1?formato=json

Séries: IGPM=189, IPCA=433, INPC=188
Resposta: [{"data":"01/05/2026","valor":"0.53"}]
Auth: nenhuma (API pública)
Cache: Redis TTL 30 dias por série+mês
Fallback: último valor cacheado se API indisponível
```

**Port para índices:**
```python
class ICorrectionIndexProvider(Protocol):
    async def get_current_rate(self, index: str, reference_date: date) -> Decimal:
        """Retorna a taxa do índice para o mês/ano de referência."""
        ...
```

---

## 2. Contas a Pagar Recorrentes

### Fluxo de Vida do Título

```
Template Recorrente → [Celery gera] → Rascunho → [Gestor edita] → Pendente → [Paga] → Pago
                                          ↓                           ↓
                                       Excluído                   Cancelado
                                    (permitido)              (nunca deletar)
```

**Regras de negócio:**
- `status = "rascunho"` → pode editar e excluir (DELETE real)
- `status = "pendente"` → pode editar, pagar ou cancelar (soft delete, nunca DELETE)
- `status = "pago"` → imutável
- `status = "cancelado"` → imutável (rastro sempre preservado)

**Celery Beat Task:** `generate_recurring_payables` (já existe)
```
Executa: diariamente às 04:00
Para cada template ativo com next_generation_date <= hoje:
  1. Criar Payable com status="rascunho", amount=template.amount
  2. Avançar next_generation_date
  3. Notificar gestor via SSE: "Título de {description} gerado como rascunho"
```

---

## 3. Motor de Cobrança Automatizada

### Timeline de Cobrança

```
                    Vencimento
    ←── Antes ────────┼────────── Depois ──→
    
D-7: Lembrete       D+0         D+1: Aviso atraso
     preventivo                  D+3: 2º lembrete
                                 D+7: Aviso bloqueio
                                 D+15: Bloqueio (policy)
                                 D+30: Notifica gestor
```

### Parâmetros (ConfiguráveIs por tenant)

```python
# Tabela: collection_policy (ou em system_settings)
{
    "reminder_days_before": 7,           # dias antes do vencimento para 1º lembrete
    "reminder_template_id": "uuid",      # template da mensagem preventiva
    
    "overdue_grace_days": 0,             # dias de tolerância após vencimento
    "overdue_escalation": [
        {"days": 1, "action": "reminder", "template_id": "uuid"},
        {"days": 3, "action": "reminder", "template_id": "uuid"},
        {"days": 7, "action": "warn_block", "template_id": "uuid"},
        {"days": 15, "action": "block", "requires_approval": false},
        {"days": 30, "action": "notify_manager"},
    ],
    
    "agent_can_negotiate": true,         # agente pode dar prazo
    "agent_max_grace_days": 7,           # máximo de dias que o agente pode conceder
    "agent_can_renegotiate": false,      # agente pode criar renegociação (requer aprovação)
    
    "interest_rate_monthly": 0.02,       # 2% ao mês
    "fine_rate": 0.02,                   # 2% multa
    "updated_value_in_message": true,    # incluir valor atualizado na mensagem
}
```

### Celery Beat Tasks

**`check_upcoming_due_dates`** — Diário às 08:00
```
Para cada installment com status="aberto" e due_date = hoje + reminder_days_before:
  1. Buscar conversa ativa do cliente no WhatsApp
  2. Se não existe, criar conversa
  3. Renderizar template de lembrete com variáveis
  4. Enviar via canal WhatsApp
  5. Registrar em conversation_messages
```

**`check_overdue_installments`** — Diário às 09:00
```
Para cada installment com status="aberto" e due_date < hoje:
  1. Atualizar status para "vencido"
  2. Calcular dias de atraso
  3. Buscar policy de escalação para os dias de atraso
  4. Executar action correspondente:
     - "reminder": enviar template via WhatsApp
     - "warn_block": enviar aviso de bloqueio iminente
     - "block": publicar InstallmentOverdueEvent (hook do vehicle module bloqueia)
     - "notify_manager": criar notificação SSE para o gestor
  5. Se agent_can_negotiate e cliente responde:
     → AgentOrchestrator processa a resposta
     → Agente pode conceder prazo (max agent_max_grace_days)
     → Agente informa valor atualizado (juros + multa)
```

**`check_paid_installments`** — A cada 30 min
```
Para cada installment com status="vencido" que recebeu pagamento:
  1. Atualizar status
  2. Se veículo bloqueado → publicar InstallmentPaidEvent (hook desbloqueia)
  3. Enviar confirmação ao cliente via WhatsApp
  4. Fechar conversa de cobrança
```

---

## 4. Consolidação do Worker (Celery Beat Schedule)

```python
celery_app.conf.beat_schedule = {
    # === Geração ===
    "generate-monthly-installments": {
        "task": "...generate_monthly_installments",
        "schedule": crontab(hour=6, minute=0),
    },
    "generate-recurring-payables": {
        "task": "...generate_recurring_payables",
        "schedule": crontab(hour=4, minute=0),
    },
    
    # === Cobrança ===
    "check-upcoming-due-dates": {
        "task": "...check_upcoming_due_dates",
        "schedule": crontab(hour=8, minute=0),
    },
    "check-overdue-installments": {
        "task": "...check_overdue_installments",
        "schedule": crontab(hour=9, minute=0),
    },
    "check-paid-installments": {
        "task": "...check_paid_installments",
        "schedule": crontab(minute="*/30"),
    },
    
    # === Manutenção ===
    "calculate-customer-scores": {
        "task": "...calculate_customer_scores",
        "schedule": crontab(hour=5, minute=0),
    },
    "refresh-materialized-views": {
        "task": "...refresh_materialized_views",
        "schedule": crontab(minute=0),  # a cada hora
    },
    "daily-backup": {
        "task": "...backup",
        "schedule": crontab(hour=3, minute=0),
    },
}
```

---

## 5. Diagrama de Fluxo

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  Celery Beat │────→│ Check Tasks  │────→│ WhatsApp Agent  │
│  (Scheduler) │     │              │     │ (Orchestrator)  │
└─────────────┘     │ - upcoming   │     │                 │
                    │ - overdue    │     │ - envia msg     │
                    │ - paid       │     │ - negocia       │
                    │ - generate   │     │ - dá prazo      │
                    └──────┬───────┘     │ - informa valor │
                           │             └────────┬────────┘
                           │                      │
                    ┌──────▼───────┐      ┌───────▼────────┐
                    │   Domain     │      │  IMessageChannel│
                    │   Events     │      │  (WhatsApp)     │
                    │              │      └───────┬────────┘
                    │ Overdue      │              │
                    │ Paid         │      ┌───────▼────────┐
                    │ Created      │      │   Cliente      │
                    └──────┬───────┘      │   (WhatsApp)   │
                           │              └────────────────┘
                    ┌──────▼───────┐
                    │ Vehicle Hook │
                    │ (block/      │
                    │  unblock)    │
                    └──────────────┘
```

---

## 6. Templates de Mensagem

Armazenados em `system_settings` ou tabela dedicada `message_templates`:

```json
{
    "reminder_before_due": {
        "channel": "whatsapp",
        "body": "Olá {nome}! Sua parcela de {valor} vence em {data_vencimento}. Deseja receber o link de pagamento?",
        "trigger": "upcoming_due"
    },
    "overdue_first": {
        "channel": "whatsapp", 
        "body": "Olá {nome}, identificamos que sua parcela de {valor} venceu em {data_vencimento}. O valor atualizado é {valor_atualizado}. Posso gerar um link de pagamento?",
        "trigger": "overdue_d1"
    },
    "overdue_warn_block": {
        "channel": "whatsapp",
        "body": "{nome}, sua parcela está com {dias_atraso} dias de atraso. Conforme contrato, o veículo poderá ser bloqueado. Regularize para evitar o bloqueio.",
        "trigger": "overdue_d7"
    }
}
```

Variáveis disponíveis: `{nome}`, `{valor}`, `{valor_atualizado}`, `{data_vencimento}`, `{dias_atraso}`, `{placa}`, `{contrato}`.
