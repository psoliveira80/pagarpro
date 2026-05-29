from celery import Celery
from celery.schedules import crontab

from app.infrastructure.settings import get_settings

settings = get_settings()

celery_app = Celery(
    "app",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.task_acks_late = True
celery_app.conf.task_reject_on_worker_lost = True
celery_app.conf.worker_prefetch_multiplier = 1
celery_app.conf.include = [
    # Orquestrador multi-tenant (story 12-6)
    "app.workers.dispatcher",
    # Tasks tenant-scoped (recebem empresa_id como primeiro argumento)
    "app.workers.tasks.gerar_titulos_mensais",
    "app.workers.tasks.gerar_despesas_recorrentes",
    "app.workers.tasks.recalcular_scores_clientes",
    "app.workers.tasks.verificar_saude_canais",
    "app.workers.tasks.alertar_vencimentos_proximos",
    "app.workers.tasks.processar_titulos_vencidos",
    "app.workers.tasks.monitorar_saude_numeros",
    # Tasks system-wide (sem tenant)
    "app.workers.tasks.atualizar_views",
    "app.workers.tasks.backup",
    # Tasks acionadas por evento (derivam empresa_id do registro processado)
    "app.workers.tasks.handle_domain_event",
    "app.workers.tasks.render_contract_pdf",
    "app.workers.tasks.process_inbound_whatsapp",
    "app.workers.tasks.run_agent_turn",
    "app.workers.tasks.send_broadcast",
    "app.workers.tasks.analisar_e_validar_comprovante_whatsapp",
]

# Beat schedule — tasks por-empresa rodam via dispatch_por_empresa.
# Horários em UTC (ajuste em produção conforme timezone do operador).
_DISPATCHER = "app.workers.dispatcher.dispatch_por_empresa"

celery_app.conf.beat_schedule = {
    # Diariamente às 06:00 UTC — geração de parcelas mensais por empresa.
    "gerar-titulos-mensais": {
        "task": _DISPATCHER,
        "schedule": crontab(hour=6, minute=0),
        "args": ("app.workers.tasks.gerar_titulos_mensais.executar",),
    },
    # Diariamente às 04:00 UTC — geração de TítulosPagar a partir de
    # DespesasRecorrentes (rascunho), por empresa.
    "gerar-despesas-recorrentes": {
        "task": _DISPATCHER,
        "schedule": crontab(hour=4, minute=0),
        "args": ("app.workers.tasks.gerar_despesas_recorrentes.executar",),
    },
    # Diariamente às 02:00 UTC — recalcular scores dos clientes por empresa.
    "recalcular-scores-clientes": {
        "task": _DISPATCHER,
        "schedule": crontab(hour=2, minute=0),
        "args": ("app.workers.tasks.recalcular_scores_clientes.executar",),
    },
    # A cada 5 minutos — health check de canais de mensageria por empresa.
    "verificar-saude-canais": {
        "task": _DISPATCHER,
        "schedule": crontab(minute="*/5"),
        "args": ("app.workers.tasks.verificar_saude_canais.executar",),
    },
    # Diariamente às 08:00 UTC (Epic 13, Story 13.7) — lembretes proativos
    # de vencimento por empresa.
    "alertar-vencimentos-proximos": {
        "task": _DISPATCHER,
        "schedule": crontab(hour=8, minute=0),
        "args": ("app.workers.tasks.alertar_vencimentos_proximos.executar",),
    },
    # Diariamente às 09:00 UTC (Epic 13, Story 13.8) — processa títulos
    # vencidos: aplica encargos, envia cobrança, suspende/encerra contratos
    # ao atingir limites configurados.
    "processar-titulos-vencidos": {
        "task": _DISPATCHER,
        "schedule": crontab(hour=9, minute=0),
        "args": ("app.workers.tasks.processar_titulos_vencidos.executar",),
    },
    # A cada hora — refresh das materialized views (system-wide).
    "atualizar-views": {
        "task": "app.workers.tasks.atualizar_views.executar",
        "schedule": crontab(minute=0),
    },
    # A cada 15 minutos (Epic 13, Story 13.21) — saúde de todos os números
    # WhatsApp (Evolution Go) cadastrados de todos os clientes. System-wide
    # pois é responsabilidade do provedor SaaS (não rotaciona por empresa).
    "monitorar-saude-numeros": {
        "task": "app.workers.tasks.monitorar_saude_numeros.executar",
        "schedule": crontab(minute="*/15"),
    },
    # Diariamente às 03:00 UTC — backup completo (system-wide).
    "daily-backup-03utc": {
        "task": "backup.run_backup",
        "schedule": crontab(hour=3, minute=0),
    },
}
