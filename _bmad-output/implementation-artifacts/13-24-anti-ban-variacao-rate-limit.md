---
epic: 13
story: 24
title: "Anti-Banimento: Variação de Template + Rate-Limit + Janela Horária + Detecção Automática de Ban"
type: "Infraestrutura + Comunicação"
status: ready-for-dev
priority: high
depends_on: "13.10, 13.21"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.24: Resiliência Anti-Banimento

## História de Usuário

**Como** sistema de cobrança autônomo,
**eu quero** evitar banimento dos números de WhatsApp via técnicas automáticas (variação de texto, controle de ritmo, horário civilizado),
**para que** a operação continue funcionando sem gestor manualmente disparando mensagens (filosofia: gestor acompanha, não opera).

## Contexto

WhatsApp banimento detecta padrões:
- Mesmo texto exato enviado para muitos números seguidos.
- Volume alto em curto período.
- Mensagens em horários incomuns (madrugada).
- Padrão "rajada" (vários disparos em segundos).

Esta story implementa **6 mecanismos automáticos** que mitigam esses sinais. Tudo configurável por tenant, com defaults conservadores.

## Critérios de Aceite

1. **Variação de templates** (`templates_mensagem` modificada):
   - Migration: campo `variacoes` (JSONB array de strings) em `comunicacao.templates_mensagem`.
   - Cada template ganha N variações do mesmo conteúdo, com mesmas variáveis Jinja2.
   - `RenderizadorTemplate.renderizar` escolhe uma variação aleatória a cada chamada.
   - Seed inicial: 3 variações por template padrão (`lembrete_vencimento`, `cobranca_vencida`, etc.).
   - UI da tela de templates (futura sub-story) permite gestor adicionar/editar variações.

2. **Rate-limit por número (hora e dia)**:
   - `ServicoLimiteEnvioWhatsapp` em `application/services/`:
     - `pode_enviar(credencial_id) -> bool` consulta:
       - Quantas mensagens outbound já saíram desse número na última hora vs `limite_outbound_por_hora_por_numero`.
       - Quantas no dia vs `limite_outbound_por_dia_por_numero`.
     - Se passa de qualquer limite → adia envio (não erra). Worker reagenda para próxima janela disponível.
   - Implementação: usa Redis sorted set por `numero_id` com timestamps; query O(log n).

3. **Janela horária civilizada**:
   - Configuração `janela_envio_inicio` (string HH:MM, default `07:00`) e `janela_envio_fim` (HH:MM, default `21:00`).
   - Timezone configurável (`fuso_horario`, default `America/Sao_Paulo`).
   - Worker que tenta envio fora da janela: reagenda para o início da próxima janela.
   - Mensagens de **emergência** (ex.: aviso de bloqueio iminente) podem bypassar com flag `respeita_janela=False` (configurável por template — flag `bypass_janela_horaria` no template).

4. **Espalhamento temporal de lote**:
   - Quando worker (ex.: 13.7 ou 13.8) gera lote de 100 cobranças, **não dispara tudo de uma vez**.
   - Distribui envio com `countdown` aleatório entre 0 e `tempo_espalhamento_lote_segundos` (default 7200 = 2h).
   - Cada job dentro do lote ainda passa pelo rate-limit (item 2).

5. **Detecção automática de ban**:
   - Hook no adapter Evolution Go: quando API retorna erro indicador de ban (HTTP 401/403 com `code='instance_banned'` ou similar, ou `code='session_expired'` após N tentativas):
     - Marca `status_whatsapp='banido'` na credencial.
     - Cria notificação para gestor.
     - Dispara `ServicoRoteamentoNumeros.marcar_numero_banido` (Story 13.21).
   - Worker `monitorar_saude_numeros` (Story 13.21) também faz health check proativo.

6. **Configurações novas** em `configuracoes_sistema` módulo `comunicacao`:
   - `janela_envio_inicio` (string, default `07:00`).
   - `janela_envio_fim` (string, default `21:00`).
   - `fuso_horario` (string, default `America/Sao_Paulo`).
   - `tempo_espalhamento_lote_segundos` (inteiro, default 7200).
   - **`limite_outbound_por_hora_por_numero` e `limite_outbound_por_dia_por_numero` já criadas na 13.21.**

7. **Testes obrigatórios**:
   - 100 chamadas a `RenderizadorTemplate` retornam pelo menos 2 variações diferentes do mesmo template (verifica aleatoriedade).
   - Rate-limit bloqueia o 31º envio dentro da mesma hora (com limite default 30).
   - Worker chamado às 03:00 reagenda para 07:00 do dia seguinte (janela).
   - Lote de 50 mensagens gera 50 jobs com countdowns distribuídos.
   - Adapter detecta ban e marca número como banido (com mock do erro Evolution Go).

## Contexto Técnico

### Rate-limit em Redis

Sorted set por `wa_outbound:{numero_id}:hourly` com timestamps. A cada envio, adiciona timestamp atual; remove os anteriores a `now - 3600`. Conta os restantes — se ≥ limite, bloqueia.

Mesmo para `wa_outbound:{numero_id}:daily` com janela de 86400.

### Janela horária com timezone

Worker recebe horário UTC; converte para timezone configurado da empresa antes de comparar com janela. Se fora, calcula próximo `inicio_janela` em UTC e usa como `eta` do Celery.

### Quem chama o ServicoLimiteEnvioWhatsapp

Todos os workers que mandam mensagem: `alertar_vencimentos_proximos` (13.7), `processar_titulos_vencidos` (13.8), `conciliar_pagamentos_recebidos` (13.9 quando notifica pagamento), futura task de notificação WhatsApp para qualquer evento. Cada um, antes de chamar `IMessageChannel.send_text`, checa permissão.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0030_variacoes_template_anti_ban.py
├── app/application/services/
│   └── servico_limite_envio_whatsapp.py            # CRIAR
├── app/infrastructure/mensageria/
│   └── renderizador_template.py                    # MODIFICAR — escolhe variação random
├── app/infrastructure/adapters/whatsapp/
│   └── evolution_go_adapter.py                     # MODIFICAR — detecta erro de ban
├── app/workers/tasks/
│   ├── alertar_vencimentos_proximos.py             # MODIFICAR — chama limite + countdown
│   ├── processar_titulos_vencidos.py               # MODIFICAR — idem
│   └── conciliar_pagamentos_recebidos.py           # MODIFICAR — idem
├── app/cli/seed.py                                  # MODIFICAR — variações + configs novas
└── app/tests/test_anti_ban.py                      # CRIAR
```

## Checklist do Dev

- [ ] Migration aplicada.
- [ ] Templates seedados têm pelo menos 3 variações cada.
- [ ] Rate-limit hora e dia testados.
- [ ] Janela horária respeitada com timezone correto.
- [ ] Espalhamento de lote: 50 jobs em 2h.
- [ ] Detecção de ban marca número e dispara migração de clientes.

## Notas

- **Filosofia central:** gestor não dispara mensagem manualmente. Sistema atua sozinho com proteções.
- Variações de template podem ser editadas pelo gestor via tela futura (não nessa story).
