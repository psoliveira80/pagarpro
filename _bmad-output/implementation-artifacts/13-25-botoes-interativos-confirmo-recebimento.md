---
epic: 13
story: 25
title: "Botões Interativos no Lembrete + Lógica de Adiar Cobrança quando Cliente Confirma Recebimento"
type: "Integração + Domínio"
status: ready-for-dev
priority: medium
depends_on: "13.7, 13.10, 13.21, 13.22"
authored_by: "Amelia (dev) + Pablo (PO)"
created_at: "2026-05-28"
---

# Story 13.25: Botões Interativos no Lembrete

## História de Usuário

**Como** sistema de cobrança autônomo,
**eu quero** enviar lembretes de vencimento com botão "Confirmo o recebimento", e quando o cliente clicar, adiar a próxima tentativa de cobrança,
**para que** clientes engajados (que já viram o lembrete) não recebam cobranças repetidas desnecessariamente, melhorando a reputação do número e a experiência do cliente.

## Contexto

Lembrete proativo (Story 13.7) hoje envia texto puro. Esta story:

1. Adiciona **botão interativo** `✓ Confirmo recebimento` no lembrete.
2. Quando cliente clica, sistema:
   - Grava `confirmacao_recebimento_em` na conversa.
   - **Adia próxima tentativa de cobrança** por N dias configuráveis.
   - Envia resposta curta: "Obrigado! Avisaremos novamente próximo do vencimento. 🙂"
3. Próxima execução do `alertar_vencimentos_proximos` (13.7) verifica essa flag e **pula** o cliente se confirmou recentemente.

Ganhos:
- **Reputação do número** (cliente respondeu → WhatsApp vê interação humana).
- **Menos cobrança redundante** (cliente que já viu não precisa receber 3 lembretes seguidos).
- **Sinaliza intenção** ("vi a cobrança, vou pagar").

## Critérios de Aceite

1. **Migration** (algumas colunas já criadas pela 13.22):
   - Confirma que `cobranca.conversas.confirmacao_recebimento_em` existe.
   - Adiciona `confirmacao_recebimento_titulo_id` (FK opcional para `financeiro.titulos_receber`) — qual título o cliente confirmou ter visto.

2. **Template `lembrete_vencimento` modificado**:
   - Renderizador suporta atributo `botoes` no template:
     ```yaml
     conteudo: "Olá {{cliente.primeiro_nome}}, sua parcela de {{titulo.valor}} vence em {{titulo.data_vencimento}}."
     botoes:
       - { id: "confirma_recebimento_{{titulo.id}}", title: "✓ Confirmo recebimento" }
       - { id: "ver_qr_{{titulo.id}}", title: "💰 Gerar QR Code agora" }
     ```
   - Renderizador retorna estrutura `{texto, botoes}` quando template tem botões; outbound passa para adapter Evolution Go.

3. **Handler de clique** em `process_inbound_whatsapp`:
   - Quando inbound é interactive button response:
     - Parse `button_id`:
       - `confirma_recebimento_<titulo_id>` → grava confirmação + envia resposta + adia cobrança.
       - `ver_qr_<titulo_id>` → state machine processa (Story 13.22).
       - Demais ids do menu rígido → state machine processa.

4. **`ServicoConfirmacaoRecebimento`** em `application/services/`:
   - `registrar_confirmacao(conversa_id, titulo_id, ator='cliente')`:
     - Atualiza `conversa.confirmacao_recebimento_em = now`.
     - Atualiza `conversa.confirmacao_recebimento_titulo_id = titulo_id`.
     - Envia template `agradecimento_confirmacao_recebimento` ao cliente.
     - Audit log com categoria `comunicacao`.

5. **Worker `alertar_vencimentos_proximos` (Story 13.7) modificado**:
   - Antes de enviar lembrete para título X, verifica:
     - Cliente tem `conversa.confirmacao_recebimento_em` para esse mesmo título nas últimas `dias_adiar_apos_confirmacao` dias?
     - Se sim, **pula** este envio. Audit: "lembrete pulado porque cliente confirmou recebimento em DD/MM".
   - Configuração: `dias_adiar_apos_confirmacao` (inteiro, default 2).

6. **Worker `processar_titulos_vencidos` (Story 13.8) NÃO usa essa flag**:
   - Cobrança de inadimplente é mais grave — confirmação de recebimento de lembrete não pula cobrança de vencido. Apenas a 13.7 (lembrete pré-vencimento) respeita.

7. **Configurações novas** em `comunicacao`:
   - `dias_adiar_apos_confirmacao` (inteiro, default 2).

8. **Templates novos** seedados:
   - `agradecimento_confirmacao_recebimento`: "Obrigado, {{cliente.primeiro_nome}}! Avisaremos novamente próximo do vencimento. 🙂"

9. **Testes obrigatórios**:
   - Cliente recebe lembrete com 2 botões.
   - Cliente clica "Confirmo recebimento" → confirmação registrada + resposta enviada.
   - Worker 13.7 roda no dia seguinte → cliente NÃO recebe lembrete (porque está dentro da janela de adiamento).
   - Worker 13.7 roda após `dias_adiar_apos_confirmacao + 1` → cliente VOLTA a receber.
   - Cliente em atraso (worker 13.8) recebe cobrança normalmente, mesmo confirmando lembrete anterior.

## Contexto Técnico

### Por que adiar só 2 dias

Default conservador. Se cliente confirmou e vencimento ainda é em 10 dias, não faz sentido lembrar de novo amanhã. Mas próximo do vencimento (D-1), vale lembrar de novo. Default 2 dias dá margem sem deixar cliente esquecer.

### Por que cobrança de vencido ignora a flag

Cliente que confirmou recebimento e mesmo assim não pagou no prazo → cobrança vencida prossegue. Filosofia: confirmação de visualização ≠ pagamento.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0031_confirmacao_recebimento.py
├── app/application/services/
│   └── servico_confirmacao_recebimento.py          # CRIAR
├── app/infrastructure/mensageria/
│   └── renderizador_template.py                    # MODIFICAR — suporta botões
├── app/workers/tasks/
│   ├── process_inbound_whatsapp.py                 # MODIFICAR — handler de botão
│   └── alertar_vencimentos_proximos.py             # MODIFICAR — skip se confirmou
├── app/cli/seed.py                                  # MODIFICAR — template e configs
└── app/tests/test_confirmacao_recebimento.py       # CRIAR
```

## Checklist do Dev

- [ ] Migration aplicada.
- [ ] Renderizador suporta botões no template.
- [ ] Cliente recebe lembrete com 2 botões.
- [ ] Clique em "Confirmo recebimento" registra e envia agradecimento.
- [ ] Próxima execução do 13.7 pula o cliente confirmado.
- [ ] Worker 13.8 (vencidos) ignora a flag.

## Notas

- Story de **engajamento**. Não é crítica do ponto de vista funcional — mas aumenta reputação do número e UX do cliente.
