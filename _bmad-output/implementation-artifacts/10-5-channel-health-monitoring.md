---
epic: 10
story: 5
title: "Monitoramento de Saúde de Canais e Auto-descoberta"
type: "Core"
status: ready-for-dev
---

# Story 10.5: Monitoramento de Saúde de Canais e Auto-descoberta

## História de Usuário
Como Gestor,
quero ver quais canais de mensageria estão configurados e saudáveis,
para que eu saiba se minha cobrança automatizada vai funcionar.

## Critérios de Aceite

1. Task Celery `check_channel_health` roda a cada 5 minutos — chama `health_check()` em todos os canais registrados, armazena resultado em `integration_credentials.status` e `last_health_check`.
2. Widget no painel mostrando status do canal: ponto verde (saudável), amarelo (degradado), vermelho (fora do ar), cinza (não configurado).
3. Notificação SSE quando um canal passa de saudável para não saudável.
4. Página Configurações > Integrações mostra status de saúde em tempo real por canal com latência.
5. Registro de canais no startup lê da tabela `integration_credentials` e encapsula adapters via `WhatsAppChannelWrapper`.
6. Testes: mock do health check, verifica persistência do status.

## Contexto Técnico

### Referências de Arquitetura
- `docs/architecture-messaging-channels.md`
- `app/core/channels/registry.py` (ChannelRegistry)
- `app/domain/ports/message_channel.py` (IMessageChannel.health_check)

### Arquivos a Criar/Modificar
```
backend-api/
├── app/workers/tasks/check_channel_health.py
├── app/main.py                              # Registra canais a partir do banco no startup
frontend/
├── src/app/features/settings/integrations.component.html  # Adiciona badges de saúde
├── src/app/features/dashboard/dashboard.component.html    # Adiciona widget de canal
```

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
