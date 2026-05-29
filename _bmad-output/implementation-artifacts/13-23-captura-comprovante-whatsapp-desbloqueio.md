---
epic: 13
story: 23
title: "Captura de Comprovante via WhatsApp + Validação Automática + Blacklist + Desbloqueio do Veículo"
type: "Integração + Domínio Financeiro + Frota"
status: ready-for-dev
priority: critical
depends_on: "13.19, 13.21, 13.22, 13.2, 13.13"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.23: Captura de Comprovante via WhatsApp e Desbloqueio Automático

## História de Usuário

**Como** sistema autônomo de cobrança,
**eu quero** receber comprovantes pelo WhatsApp, validá-los automaticamente (com bypass para clientes em blacklist) e desbloquear o veículo quando o pagamento for confirmado,
**para que** o cliente recupere uso do veículo sem intervenção humana e o gestor só atue em casos suspeitos.

## Contexto

Fluxo completo que esta story implementa:

```
cliente clica "📎 Enviar comprovante" no menu (Story 13.22)
  → state machine seta aguardando_comprovante_ate = now + timeout_aguardar_comprovante_min (default 5min)
  → cliente envia foto/PDF dentro do timeout
  → worker baixa mídia do Evolution Go
  → pipeline 13.19 analisa, retorna ResultadoAnaliseComprovante
  → ServicoValidacaoAutomatica decide:
       se cliente.na_blacklist_comprovantes:
           → status = "aguardando_homologacao_manual"
           → notifica gestor no painel
       senão se score >= score_minimo_validacao_automatica:
           → marca título como pago (ServicoTituloPago da 13.9)
           → se contrato está suspenso:
                → dispara desbloqueio via IGatewayRastreador (hook quando_contrato_reativado)
                → transita contrato suspenso → vigente
           → envia mensagem ao cliente: "Pagamento confirmado! Veículo desbloqueado ✓"
       senão (score < threshold):
           → status = "aguardando_homologacao_manual"
           → envia mensagem: "Recebi seu comprovante. Vamos verificar e te avisamos em breve."
```

Se cliente envia mídia fora do timeout: bot responde "Use o botão Enviar comprovante antes de mandar a foto 👇" + reenvia menu (Story 13.22 cuida).

## Critérios de Aceite

1. **Worker handler** modificado em `process_inbound_whatsapp`:
   - Quando mensagem inbound é mídia (`tipo='image'` ou `tipo='document'`):
     - Carrega `Conversa` correspondente.
     - Se `aguardando_comprovante_ate IS NOT NULL AND aguardando_comprovante_ate > now()`:
       - Baixa a mídia via `EvolutionGoAdapter.download_media`.
       - Faz upload para MinIO/S3.
       - Dispara task Celery `analisar_e_validar_comprovante_whatsapp` (queue `fila_verificacao`).
       - Limpa o flag: `aguardando_comprovante_ate = null`.
     - Senão (fora de timeout ou não esperando):
       - Salva mídia na conversa normal.
       - Envia mensagem padrão: "Use o botão *Enviar comprovante* antes de mandar a foto 👇" + reenvia menu.

2. **Task `analisar_e_validar_comprovante_whatsapp`**:
   - Roda pipeline da Story 13.19 (`ServicoAnaliseComprovante`).
   - Marca origem `whatsapp` + `telefone_remetente`.
   - Chama `ServicoValidacaoAutomatica.avaliar(comprovante_id)`.

3. **`ServicoValidacaoAutomatica`** em `application/services/`:
   - Aplica regra de decisão (blacklist + score + threshold).
   - Configuração lida:
     - `comprovantes.validacao_automatica_default` (boolean, default `true`).
     - `comprovantes.score_minimo_validacao_automatica` (decimal, default 0.70).
     - `comprovantes.desbloqueio_automatico_apos_validacao` (boolean, default `true`).
     - Já existe da 13.19 — esta story só **usa**.
   - Se decisão é homologar: chama `ServicoTituloPago.registrar_pagamento` + marca comprovante `homologado` + envia confirmação ao cliente via Evolution Go.
   - Se decisão é manual: marca comprovante `aguardando_homologacao_manual` + notifica gestor.

4. **Desbloqueio automático do veículo**:
   - Quando `ServicoTituloPago` marca título como `pago` e o contrato está em `suspenso`:
     - Chama `ServicoSituacaoContrato.transicionar(contrato, vigente, motivo='Pagamento confirmado via comprovante WhatsApp')`.
     - O hook `quando_contrato_reativado` (já existe — Story 13.2) chama `IGatewayRastreador.desbloquear`.
   - Configurável: `desbloqueio_automatico_apos_validacao = false` desabilita esse passo (gestor desbloqueia manualmente).

5. **Mensagens automáticas ao cliente** (via templates da Story 13.10):
   - Template `comprovante_validado_automatico`: "Pagamento confirmado! Veículo desbloqueado ✓. Próxima parcela vence dia X."
   - Template `comprovante_aguardando_validacao_manual`: "Recebi seu comprovante. Vamos verificar e te avisamos em breve."
   - Template `comprovante_rejeitado_blacklist`: igual ao anterior em conteúdo, mas internamente flag para que gestor saiba motivo.
   - Templates seedados via `cli/seed.py`.

6. **Notificação para o gestor** quando validação manual é necessária:
   - Cria registro em `logs.log_eventos` com categoria `comprovante_aguardando_homologacao`.
   - Painel admin mostra contador "X comprovantes aguardando" no dashboard.
   - Notificação push opcional (out of scope desta story — depende de WebSocket/SSE existente).

7. **Endpoint REST para a tela de comprovantes** (Story 13.19 já tem `/homologar`):
   - Não precisa de novo endpoint — `/comprovantes/{id}/homologar` já cobre. O que muda é que homologação manual de blacklist tem badge "BLACKLIST" no detalhe do comprovante.

8. **Testes obrigatórios**:
   - Cliente clica botão + envia foto + score 0.95 + não-blacklist → título marcado pago + desbloqueio chamado + mensagem enviada.
   - Cliente clica botão + envia foto + score 0.95 + **blacklist ativa** → fica `aguardando_homologacao_manual`, NENHUM bloqueio é liberado.
   - Cliente envia foto sem clicar botão → mensagem padrão pedindo usar botão.
   - Cliente clica botão + 6 min depois envia foto (timeout 5min) → mensagem padrão.
   - Cliente envia 2 fotos em sequência depois de clicar botão (dentro do timeout) → ambas analisadas, ambas viram registros de comprovante. (Bot não pergunta de novo).
   - Desbloqueio automático desabilitado: validação ocorre mas veículo segue bloqueado.

## Contexto Técnico

### Por que blacklist é absoluta

Pablo definiu: cliente em blacklist perde **todos** os direitos automáticos, mesmo com score 100. Justificativa: se cliente já foi pego forjando comprovante, sistema não pode mais confiar nele jamais — gestor é a única autoridade pra validar.

### Timeout configurável

Está em `comunicacao.timeout_aguardar_comprovante_min` (default 5). Gestor ajusta na tela de configurações.

### Desbloqueio do veículo

Reusa toda a infra existente:
- `ServicoSituacaoContrato.transicionar` (Story 13.2)
- Hook `quando_contrato_reativado` (Story 13.2)
- `IGatewayRastreador` (rename Story 13.18)

Nada novo — só compõe.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── app/application/services/
│   └── servico_validacao_automatica.py             # CRIAR
├── app/workers/tasks/
│   ├── analisar_e_validar_comprovante_whatsapp.py  # CRIAR
│   └── process_inbound_whatsapp.py                 # MODIFICAR — roteia mídia
├── app/cli/seed.py                                  # MODIFICAR — seed templates
└── app/tests/test_validacao_automatica_whatsapp.py # CRIAR
```

## Checklist do Dev

- [ ] Stories 13.19, 13.21, 13.22 concluídas.
- [ ] Worker integra com pipeline 13.19 corretamente.
- [ ] Decisão de blacklist bypassa score (testado).
- [ ] Desbloqueio automático funcional (com mock do IGatewayRastreador).
- [ ] Toggle `desbloqueio_automatico_apos_validacao = false` desativa o desbloqueio sem afetar a homologação.
- [ ] Confirmação ao cliente via WhatsApp funciona via template.
- [ ] Notificação ao gestor registrada quando validação manual é necessária.
- [ ] Testes específicos passam.

## Notas

- Esta story **fecha o loop crítico** do produto: cliente atrasou → veículo bloqueou → cliente pagou → enviou comprovante → veículo desbloqueou. **Tudo sem gestor.**
- Bypass por blacklist é o que protege o gestor contra fraude.
