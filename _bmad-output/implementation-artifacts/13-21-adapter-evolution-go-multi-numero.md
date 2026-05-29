---
epic: 13
story: 21
title: "Adapter Evolution Go + Multi-Número por Empresa com Atribuição Estável"
type: "Integração + Infraestrutura"
status: review
priority: critical
depends_on: "13.5, 13.10"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.21: Adapter Evolution Go e Multi-Número

## História de Usuário

**Como** sistema de cobrança automatizado,
**eu quero** me conectar ao Evolution Go (provedor único central, modelo SaaS A) e suportar múltiplos números de WhatsApp por empresa cliente com atribuição estável por cliente,
**para que** as cobranças aconteçam de forma resiliente a banimentos sem confundir o cliente com troca de número e sem virar gerenciador de API.

## Contexto

Decisões consolidadas:
- **Topologia A:** Provedor SaaS (Pablo) hospeda 1 Evolution Go central. Cada empresa cliente tem 1+ instâncias dentro dele. FrotaUber **não** gera QR Code, **não** gerencia conexão. Apenas consome a API.
- **Atribuição estável:** cliente recebe um número fixo no primeiro contato outbound. Não muda por balanceamento, só se número for banido.
- **Distribuição de carga proativa:** quando empresa tem N números ativos, novo cliente é atribuído ao número com menor contagem de clientes (balancea automaticamente).
- **Conversa unificada:** mensagens trocadas em diferentes números da mesma empresa com o mesmo cliente compartilham a mesma `conversa` (chaveada por `empresa_id + telefone_cliente`). Cada `mensagem` registra qual número (`numero_origem_id`).

## Critérios de Aceite

1. **Migration nova** adiciona:
   - Coluna `numero_origem_id` em `cobranca.mensagens` (FK opcional para `config.credenciais_integracao` — qual instância Evolution Go enviou/recebeu).
   - Coluna `numero_origem_id` em `cadastro.clientes` (FK opcional — qual número da empresa atende esse cliente).
   - Campos em `config.credenciais_integracao.config` JSONB para integrações da categoria `whatsapp_evolution_go`:
     - `instance_id` — identificador da instância no Evolution Go.
     - `instance_token` — autenticação da instância.
     - `numero_e164` — número de telefone associado.
     - `status_whatsapp` — `ativo` / `inativo` (gestor desligou) / `banido` (detectado pelo sistema) / `desconectado` (sessão caiu, recuperável).
     - `eh_principal` — boolean, marca número padrão para clientes novos quando sistema empata na contagem.
     - `clientes_atribuidos_cache` — contagem cacheada (atualizada por trigger ou worker leve).
     - `ultimo_health_check` — timestamp.
     - `motivo_banimento` — texto auditável quando status='banido'.

2. **Adapter `EvolutionGoAdapter`** implementando `IMessageChannel`:
   - `send_text(to, text)` — POST para Evolution Go.
   - `send_buttons(to, body, buttons)` — botões interativos (até 3, conforme limite WhatsApp).
   - `send_list(to, body, sections)` — menu list.
   - `download_media(media_id)` — baixa mídia recebida (comprovante).
   - `health_check()` — ping na API + verifica status da instância.
   - `parse_webhook(payload)` — converte payload Evolution Go em `ReceivedMessage` ou `MessageStatusUpdate`.

3. **Serviço `ServicoRoteamentoNumeros`** em `application/services/`:
   - `atribuir_numero(cliente_id) -> numero_origem_id` — escolhe o número com menor contagem entre os ativos da empresa do cliente. Persiste em `cliente.numero_origem_id`. Idempotente (se já atribuído, retorna o existente).
   - `numero_para_outbound(cliente_id) -> credencial_integracao` — retorna a credencial do número atribuído. Se número estiver `banido` ou `desconectado`, re-atribui via `migrar_cliente_para_outro_numero`.
   - `migrar_cliente_para_outro_numero(cliente_id, motivo)` — usado quando número original cai. Audit log obrigatório.
   - `marcar_numero_banido(credencial_id, motivo)` — atualiza status, dispara re-atribuição de todos os clientes afetados, notifica gestor.

4. **Worker `monitorar_saude_numeros`** (Celery Beat, a cada 15 min):
   - Para cada número de cada empresa, chama `health_check`.
   - Se health_check falha com indicador de ban (HTTP 401/403 com mensagem do provider) → marca como `banido` automaticamente.
   - Persiste resultado em `motor.execucoes_motor` para a tela de observabilidade (Story 13.5).

5. **Endpoints REST `/api/v1/numeros-cobranca`** (role `admin`):
   - `GET /` — lista números da empresa com status, contagem de clientes, último health check.
   - `PUT /{credencial_id}/marcar-banido` — gestor força marcação manual com motivo.
   - `PUT /{credencial_id}/marcar-ativo` — reativa número (depois de troca manual no Evolution Go).
   - `PUT /{credencial_id}/marcar-principal` — define número padrão para empate na atribuição.
   - **Não tem** endpoint de criar/conectar instância — isso é feito por fora (Pablo no painel Evolution Go).

6. **Roteamento de webhook inbound** — o webhook do Evolution Go envia em qual instância recebeu. O `process_inbound_whatsapp` lê isso e:
   - Identifica `credencial_integracao` pelo `instance_id` do payload.
   - Identifica `empresa_id` via `credencial.empresa_id`.
   - Persiste `mensagem.numero_origem_id` com a credencial.
   - Conversa continua chaveada por `(empresa_id, telefone_cliente)` — não há divisão.

7. **Configurações novas** em `configuracoes_sistema` módulo `comunicacao`:
   - `limite_clientes_por_numero` (inteiro, default 80) — acima disso, sistema notifica gestor (não bloqueia).
   - `limite_outbound_por_hora_por_numero` (inteiro, default 30) — usado pela Story 13.24.
   - `limite_outbound_por_dia_por_numero` (inteiro, default 300) — usado pela 13.24.

## Contexto Técnico

### Por que o cliente fica fixo num número

Cliente acostuma com o número que sempre fala com ele. Se sistema balancear a cada mensagem, cliente recebe de números diferentes da mesma empresa → desconfia → suporte ao WhatsApp pode marcar como spam.

### Por que atribuir balanceado

Múltiplos números reduzem outbound por número/dia → reduzem chance de banimento. Se a empresa tem 4 números ativos atendendo 100 clientes, cada número atende ~25 (menos tráfego, mais seguro).

### Por que conversa unificada

Cliente é a unidade do relacionamento, não o número. Se sistema migra cliente de N1 (banido) pra N2, gestor vê na inbox a **mesma conversa**, com timeline contínua. Cada mensagem mostra qual número usou (filtro opcional na UI).

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0028_evolution_go_multi_numero.py
├── app/infrastructure/adapters/whatsapp/
│   ├── evolution_go_adapter.py                     # CRIAR
│   └── whatsapp_factory.py                          # MODIFICAR — registra evolution_go
├── app/application/services/
│   └── servico_roteamento_numeros.py                # CRIAR
├── app/workers/tasks/
│   └── monitorar_saude_numeros.py                   # CRIAR
├── app/api/v1/
│   └── numeros_cobranca_routes.py                   # CRIAR
├── app/workers/tasks/process_inbound_whatsapp.py    # MODIFICAR — grava numero_origem_id
└── app/infrastructure/db/models/
    ├── cobranca.py                                  # MODIFICAR — Mensagem ganha numero_origem_id
    └── cadastro.py                                  # MODIFICAR — Cliente ganha numero_origem_id
```

## Checklist do Dev

- [ ] Migration aplicada com sucesso.
- [ ] Adapter envia texto, botões e list — todos testados contra mock.
- [ ] Atribuição balanceada testada com 3 números e 30 clientes (média de 10 por número, sem viés).
- [ ] Migração automática quando número marcado como banido testada.
- [ ] Inbound roteado para conversa correta quando dois números diferentes atendem mesmo cliente.
- [ ] Endpoints `/numeros-cobranca` funcionais com role-gate `admin`.
- [ ] Worker `monitorar_saude_numeros` registra execução em `motor.execucoes_motor`.

## Notas

- Fundação para 13.22 (state machine) e 13.27 (inbox).
- Mantém princípio "não somos gerenciador de API WhatsApp" — Evolution Go cuida da sessão; nós cuidamos do relacionamento.
