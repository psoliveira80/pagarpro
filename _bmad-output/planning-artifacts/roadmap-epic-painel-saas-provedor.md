---
status: roadmap (não-priorizado)
tipo: epic-futuro
proposto_por: Pablo
registrado_em: 2026-05-27
registrado_por: Amelia
---

# Epic Futuro — Painel SaaS do Provedor (Multi-Tenant Admin)

> **Status:** ideia registrada para roadmap. **Não é para agora.** Quando priorizado, virar épico numerado (provavelmente Epic 14 ou posterior) e gerar stories formais via `bmad-create-story`.

## Visão

Hoje o FrotaUber é um SaaS multi-tenant onde cada empresa cliente (linha em `comercial.empresas`) vive isolada via RLS. **Falta o "outro lado":** o painel de quem **VENDE** o SaaS — o painel do provedor.

O provedor precisa:

1. **Cadastrar e gerenciar clientes** (as empresas tenant), com plano, cobrança e ciclo de vida (trial → ativo → suspenso por inadimplência → cancelado).
2. **Monitorar saúde de cada módulo** do sistema em tempo real — saber em segundos se um motor parou, um canal WhatsApp foi bloqueado, uma integração caiu, ou a VPS está sufocando.
3. **Logs estruturados visíveis em tempo real** — não só audit, mas observabilidade operacional do dia-a-dia.
4. **Atender chamados de suporte** dos clientes (sistema de tickets).

## Por que isso virou prioridade no roadmap

Ditado do Pablo (literal):
> "afinal, um título não pode deixar de ser gerado, uma cobrança não pode deixar de ser feita, uma mensagem de whatsapp não pode estar com número bloqueado etc"

Risco operacional sem isso:
- Motor cai de madrugada e ninguém percebe até cliente reclamar.
- Canal WhatsApp banido e cobrança para silenciosamente — multas + churn.
- VPS estourando memória e o dev descobre só quando o site cai.
- Cliente abre ticket no email e demora dias pra alguém ver.

---

## Componentes propostos

### 1. Painel Admin do Provedor (frontend)

**Decisão arquitetural pendente:**

- [ ] **Opção A — Frontend separado** (`src/frontend-admin/`): blast radius zero, build independente, pode rodar em domínio diferente (ex.: `admin.frotauber.com.br`). Custo: duplica setup Angular.
- [ ] **Opção B — Área protegida no frontend atual** (`/admin-saas/*` com role `super_admin`): reusa tudo (auth, layout, componentes). Custo: mistura código de produto com código de provedor, requer atenção redobrada a RBAC.
- **Recomendação Amelia:** **Opção B** para V1 (chega antes, reusa muito), com migração futura para A se a separação operacional ficar essencial.

**Telas (mínimo viável):**
- Lista de empresas clientes (com filtros: plano, status, MRR, inadimplência).
- Detalhe de empresa: dados cadastrais, plano atual, histórico de pagamentos do plano, uso (qtd usuários, contratos, mensagens enviadas).
- Wizard de cadastro de empresa cliente (CNPJ, razão, plano inicial, admin owner).
- Tela de planos (CRUD de planos + features incluídas).
- Painel de saúde dos módulos (próximo componente).
- Caixa de tickets (próximo componente).

### 2. Cobrança do SaaS (plano dos clientes)

Modelo: cada empresa cliente paga uma mensalidade ao provedor (plano básico/pro/enterprise + add-ons). Esse fluxo é **separado** da cobrança que a empresa cliente faz dos *seus* clientes.

**Decisão arquitetural pendente:**

- [ ] **Reuso vs duplicação dos motores:** os motores que construímos no Epic 13 (`gerar_titulos_mensais`, `processar_titulos_vencidos`, `conciliar_pagamentos_recebidos`) cobrem 90% dessa lógica de cobrança SaaS. Decisão:
  - **(A)** Tratar o provedor como um "tenant especial" (empresa raiz) que cobra de todas as outras → reusa motores existentes. Conceitualmente é um cliente cobrando outros clientes.
  - **(B)** Criar motores dedicados em schema `saas` separado → isolamento total.
  - **Recomendação:** (A) — é elegante e usa o que já está bem testado. Único cuidado: schema separado pra essas tabelas (`saas.assinaturas`, `saas.faturas`) ou tabelas dedicadas em `comercial`.

**Entidades novas:**
- `Plano` (id, nome, mensalidade, limites: max_usuarios, max_contratos, max_mensagens_mes, features_jsonb).
- `Assinatura` (empresa_id, plano_id, inicio, fim, status: trial/ativa/suspensa/cancelada, dia_cobranca, valor_mensal_atual).
- `FaturaSaaS` (assinatura_id, periodo_inicio, periodo_fim, valor, status, pago_em).

### 3. Painel de Saúde dos Módulos (MAIS CRÍTICO)

Worker `monitorar_saude_modulos` (a cada N minutos, default 5) verifica:

| Sinal | Como medir | Status saudável |
|---|---|---|
| Última execução de cada motor (Epic 13) | `motor.execucoes_motor` — delta entre `iniciado_em` mais recente e schedule esperado | dentro de 2× intervalo do cron |
| Taxa de erro de cada motor | `total_erros / total_registros` últimas 10 execuções | < 5% |
| Status dos canais de mensageria | `verificar_saude_canais` (já existe) + flag banido | todos ativos |
| Integrações externas (FIPE, BCB, Pluggy, Z-API) | ping HTTP + tempo de resposta | < 2s, 200 OK |
| Saúde da VPS | API externa tipo `node_exporter` Prometheus exposto na VPS | CPU < 80%, RAM < 85%, disk < 90% |
| Profundidade da fila Celery | `celery_inspect()` | < 100 jobs pendentes |
| Conexões Postgres em uso | `pg_stat_activity` | < 80% do `max_connections` |
| Lag de réplica (se houver) | `pg_replication` | < 30s |

**Persiste em `monitoramento.snapshots_saude`** (1 linha por execução, com JSONB consolidado).

**Tela:** dashboard estilo Grafana-lite, com cards verde/amarelo/vermelho por módulo, sparkline das últimas 24h, e histórico.

**Alerta:** quando módulo vai pra vermelho, dispara notificação (canal a definir — Slack? WhatsApp? Email? Push?).

### 4. Logs Estruturados em Tempo Real

Hoje: `structlog` joga logs no stdout do container.
Futuro: dev quer ver logs em tempo real **no painel admin**.

**Decisão arquitetural pendente:**

- [ ] **Opção A — Stack dedicada** (Loki + Grafana, ou Vector + ClickHouse): mais robusto, custo de infra.
- [ ] **Opção B — Redis Streams + SSE**: zero infra adicional, reusa o que já temos. Logs estruturados publicados em `stream:logs:{nivel}` e o frontend admin consome via Server-Sent Events.
- **Recomendação:** **Opção B** para V1. Se volume de logs estourar, migrar pra Loki.

**Tela:** terminal-like com filtros (módulo, nível, empresa_id, correlation_id), pausa/resume, busca regex.

### 5. Módulo de Suporte (Tickets)

**Entidades:**
- `Ticket` (id, empresa_id, abertura_em, assunto, severidade, status: aberto/em_atendimento/aguardando_cliente/resolvido, atribuido_a).
- `MensagemTicket` (ticket_id, autor, conteudo, anexos, criado_em, interna: bool).

**Telas:**
- Lista de tickets (admin do provedor) com filtros (severidade, status, cliente).
- Detalhe do ticket com thread de mensagens e ações (atribuir, fechar, escalar).
- **Bônus:** integração com inbox WhatsApp existente — cliente abre ticket mandando mensagem pra número de suporte. Worker classifica via LLM e cria ticket automaticamente.

---

## Estimativa grossa (post-priorização)

Quando virar épico:
- 5–8 stories no total.
- Esforço estimado: **2–3 sprints** (sem o módulo de suporte, que pode ser sprint à parte).
- Maior incógnita: integração de health-check com VPS (depende de qual VPS você usa — DigitalOcean, AWS, OCI, BareMetal).

## O que NÃO está no escopo deste epic

- Onboarding self-service (cliente novo se cadastra sozinho via landing page): isso é Epic V2 documentado em `[[project_landing_page]]`.
- Comparativo de planos para venda (pricing page): também V2.
- Marketing automation (email drip, CRM): fora do escopo.

## Dependências e pré-requisitos

- Epic 13 (Motor Financeiro Central) — `review`/`done`. **Já está pronto.** O painel SaaS consome `motor.execucoes_motor` para o dashboard de saúde.
- Sistema de roles tem que ter `super_admin` (verificar se já existe em `acesso.perfis` — provavelmente sim, criado no seed inicial).
- VPS precisa expor algum endpoint de health (node_exporter, custom HTTP, etc.) — definição operacional.

## Próximos passos quando priorizar

1. Pablo decide as 3 decisões arquiteturais marcadas com `[ ]` acima.
2. John (PM) gera o épico formal com `bmad-create-epics` ou estende `epics.md`.
3. Amelia gera stories com `bmad-create-story` por componente:
   - Story 1: schema do plano + assinatura
   - Story 2: cadastro de empresas + wizard
   - Story 3: cobrança SaaS (reusando motores Epic 13)
   - Story 4: worker `monitorar_saude_modulos`
   - Story 5: dashboard de saúde (frontend)
   - Story 6: logs em tempo real (Redis Streams + SSE)
   - Story 7: tickets (backend + UI)
   - Story 8: integração tickets ↔ WhatsApp (opcional)
4. Sprint planning prioriza componentes (sugiro **dashboard de saúde primeiro** — é o que impede dor operacional).

---

**Última atualização:** 2026-05-27 — Amelia (dev) registrou a pedido do Pablo após sessão autônoma do Epic 13.
