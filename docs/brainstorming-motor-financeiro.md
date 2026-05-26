# Brainstorming Técnico — Motor Financeiro e Gaps de Regras de Negócio

> **Status:** Em andamento  
> **Data de início:** 2026-05-22  
> **Contexto:** Revisão pós-análise de estado do sistema. Gaps identificados no roundtable com os agentes BMAD. Este documento guia a discussão gap a gap até cobertura completa.

---

## Convenção de Nomenclatura (VIGENTE A PARTIR DE AGORA)

**Regra:** TODOS os termos técnicos — tasks Celery, eventos de domínio, hooks, ports, adapters — em **Português (PT-BR)**.

### Mapeamento Inglês → Português

| Inglês (antigo) | Português (novo) | Tipo |
|---|---|---|
| `generate_monthly_installments` | `gerar_titulos_mensais` | Task Celery |
| `check_upcoming_due_dates` | `verificar_vencimentos_proximos` | Task Celery |
| `check_overdue_installments` | `processar_titulos_vencidos` | Task Celery |
| `check_paid_installments` | `verificar_pagamentos_recebidos` | Task Celery |
| `calculate_customer_scores` | `recalcular_scores_clientes` | Task Celery |
| `generate_recurring_payables` | `gerar_contas_pagar_recorrentes` | Task Celery |
| `check_channel_health` | `verificar_saude_canais` | Task Celery |
| `refresh_materialized_views` | `atualizar_visoes_materializadas` | Task Celery |
| `on_installment_overdue` | `quando_titulo_vencido` | Hook |
| `on_installment_paid` | `quando_titulo_pago` | Hook |
| `on_contract_created` | `quando_contrato_ativado` | Hook |
| `on_contract_terminated` | `quando_contrato_encerrado` | Hook |
| `on_reconciliation_completed` | `quando_reconciliacao_concluida` | Hook |
| `InstallmentOverdueEvent` | `EventoTituloVencido` | Evento de Domínio |
| `InstallmentPaidEvent` | `EventoTituloPago` | Evento de Domínio |
| `ContractCreatedEvent` | `EventoContratoAtivado` | Evento de Domínio |
| `ContractTerminatedEvent` | `EventoContratoEncerrado` | Evento de Domínio |
| `PaymentPartiallyReceivedEvent` | `EventoPagamentoParcialRecebido` | Evento de Domínio |
| `CustomerScoreChangedEvent` | `EventoScoreClienteAlterado` | Evento de Domínio |
| `ReconciliationCompletedEvent` | `EventoConciliacaoConcluida` | Evento de Domínio |
| `IAssetModule` | `IModuloAtivo` | Port |
| `IMessageChannel` | `ICanalMensagem` | Port |
| `IPaymentGateway` | `IGatewayPagamento` | Port |
| `ITrackerGateway` | `IGatewayRastreador` | Port |
| `IFipeProvider` | `IProvedorFipe` | Port |
| `ICorrectionIndexProvider` | `IProvedorIndiceCorrecao` | Port |
| `IOcrProvider` | `IProvedorOcr` | Port |
| `ILLMProvider` | `IProvedorLLM` | Port |
| `IStorageProvider` | `IProvedorArmazenamento` | Port |
| `IEmailSender` | `IEnviadorEmail` | Port |
| `IWhatsAppGateway` | `IGatewayWhatsApp` | Port |
| `VehicleModule` | `ModuloVeiculos` | Módulo |
| `ChannelRegistry` | `RegistroCanais` | Serviço |

---

## Gaps para Discussão

### GAP 1 — Status CONGELADO no Contrato
**Problema:** O contrato só tem `rascunho`, `vigente`, `encerrado`, `rescindido`. Falta `suspenso` (congelamento temporário de cobranças).

**Pergunta para Pablo:**
- O congelamento tem prazo? Ou é indefinido?
- Enquanto congelado, juros continuam acumulando ou param?
- O gestor define data de retomada ou só pode recongelar manualmente?

**Exemplo do mundo real:**
> Motorista Carlos bate o carro em janeiro. Vai ao seguro. O reparo demora 3 semanas. O gestor congela o contrato por 21 dias para não gerar cobrança durante o período em que o carro não pode ser usado. No dia 22 o carro volta da oficina e o contrato é retomado automaticamente.

**Status:** ⬜ Aguardando resposta de Pablo

---

### GAP 2 — Passivo Inoperante (Ledger de Dívidas Inativas)
**Problema:** Quando um contrato é cancelado por inadimplência, o saldo devedor não tem tabela própria. Fica como metadado no contrato cancelado, sem rastreabilidade financeira.

**Cenário 3.1 (de Pablo):**
> Contrato de 50.000. Parcelas semanais de 800. Cliente pagou 30 parcelas (24.000). Devolveu o carro. Saldo devedor: 26.000. 
> Questão: onde fica esse saldo? Como o gestor cobra futuramente?

**Pergunta para Pablo:**
- O passivo de 26k pode ser cobrado posteriormente? Ou é considerado perdido?
- Se pode ser cobrado, o cliente pode fazer um acordo (renegociação de passivo)?
- Esse valor aparece no DRE como "devedores duvidosos" ou só quando efetivamente cobrado?

**Exemplo do mundo real:**
> Gestor João tem 3 contratos cancelados por inadimplência no mês. Total de passivo: 78k. Ele quer ver isso em um relatório mensal de "Carteira de Inadimplentes" para avaliar se vale busca ativa via cartório ou acordo.

**Status:** ⬜ Aguardando resposta de Pablo

---

### GAP 3 — Transferência de Saldo entre Contratos (Cenário 3.2)
**Problema:** Quando cliente retorna veículo e quer iniciar novo contrato, o saldo devedor do contrato antigo pode ou não ser transferido para o novo.

**Cenário 3.2 (de Pablo):**
> Contrato de 80.000. Cliente pagou 50 parcelas (40.000). Quer devolver e pegar outro carro com contrato de 100.000.
> Questão: o saldo devedor de 40k vai para o novo contrato? Ou cada contrato fica independente?

**Pergunta para Pablo:**
- Isso é uma decisão do negócio (cada operador decide) ou regra fixa?
- Se o saldo transfere, entra como parcela extra no novo contrato? Como "entrada negativa"?
- Se não transfere, o gestor sabe que o cliente tem 40k de passivo e decide conscientemente aceitar o novo contrato?

**Opções técnicas:**
1. **Independência total:** Cada contrato é uma entidade separada. Saldo antigo vira passivo inoperante. Novo contrato começa do zero. O sistema avisa o gestor: "Este cliente tem 40k de passivo de contratos anteriores."
2. **Transferência explícita:** O gestor pode "importar" o saldo do contrato antigo para o novo, gerando uma parcela extra no início com valor = saldo_devedor_anterior e label "Transferência de Saldo".
3. **Incorporação ao valor:** O novo contrato já nasce com valor de 140k (100k do veículo + 40k do saldo), e o plano de parcelas é recalculado.

**Status:** ⬜ Aguardando resposta de Pablo

---

### GAP 4 — Parametrização de Pagamento Parcial por Período
**Problema:** O pagamento parcial existe como operação, mas não há regra de quantas vezes por período é permitido.

**Pergunta para Pablo:**
- Qual o número máximo de parciais por mês que você quer permitir por padrão?
- O limite é por contrato ou por cliente?
- O que acontece quando o cliente esgota o limite? O sistema rejeita automaticamente ou avisa o gestor?

**Exemplo do mundo real:**
> Política configurada: máximo 2 pagamentos parciais por mês por cliente. No dia 15, Carlos paga 60% da parcela. No dia 22, paga mais 20%. No dia 28, tenta pagar mais 15% — o sistema bloqueia e avisa: "Limite de pagamentos parciais atingido. Contate o gestor."

**Status:** ⬜ Aguardando resposta de Pablo

---

### GAP 5 — Desbloqueio em Confiança
**Problema:** O módulo de veículos desbloqueia automaticamente ao receber pagamento, mas não há regra de "desbloqueio em confiança" (antes do pagamento, por promessa).

**Pergunta para Pablo:**
- O cliente pode pedir desbloqueio sem pagar ainda? Em quais condições?
- Quem decide: o gestor sempre aprova? O agente de IA pode decidir? A policy define automaticamente?
- Quantas vezes por período um cliente pode receber desbloqueio em confiança?

**Exemplo do mundo real:**
> Carlos tem carro bloqueado desde ontem. Liga para o gestor: "Vou pagar hoje à noite, pode desbloquear agora?" Policy configurada: 1 desbloqueio em confiança por trimestre. É o primeiro de Carlos. Sistema permite. Gestor toca um botão. Carro desbloqueado. Se Carlos não pagar no prazo acordado (ex: 24h), sistema re-bloqueia automaticamente.

**Status:** ⬜ Aguardando resposta de Pablo

---

### GAP 6 — Motor de Cobrança (Não Existe no Código) ✅ RESOLVIDO no Épico 13
**Problema original:** As tasks `alertar_vencimentos_proximos`, `processar_titulos_vencidos`, `conciliar_pagamentos_recebidos` não existem no código. O sistema gera títulos mas não cobra ninguém automaticamente.

**Solução final:**
- Histórias 12.6, 12.7, 12.8, 12.9 implementam as tasks faltantes
- Parâmetros (`dias_antes_lembrete`, `percentual_multa`, etc.) vão para `config.configuracoes_sistema` (módulo `financeiro`) — não há mais tabela `politica_cobranca`
- `ServicoConfiguracao` lê parâmetros com fallback automático
- História 12.5 entrega infraestrutura (filas, idempotência, observabilidade)

**Status:** ✅ Especificado no Épico 13, pronto para implementação

---

### GAP 7 — Integração do QR Code Pix no Motor de Cobrança
**Problema:** O endpoint `/recebíveis/{id}/pix-qr` existe, mas não é chamado automaticamente pelo motor de cobrança ao enviar mensagem de cobrança.

**O que precisamos:**
- Quando o motor envia mensagem de cobrança, deve incluir o QR Code Pix automaticamente
- O `renderizador_de_template` deve ter a variável `{qr_code_pix}` ou `{link_pagamento}`
- O arquivo `domínio/financeiro/renderizador_template.py` não existe

**Status:** ⬜ Depende do GAP 6

---

### GAP 8 — Arquitetura Multi-Empresa do Motor
**Problema:** As tasks Celery processam todos os contratos/títulos de todas as empresas num SELECT único. Não há isolamento por empresa.

**Solução (Winston propôs):**
```python
# Padrão coordinator → fan-out
def gerar_titulos_mensais():  # coordinator — roda às 06h
    for empresa in Empresa.todas_ativas():
        processar_geracao_empresa.delay(empresa_id=empresa.id)

@celery_app.task
def processar_geracao_empresa(empresa_id: UUID):
    # processa uma empresa por vez, com isolamento de erro
    ...
```

**Status:** ⬜ Baixo risco hoje (poucos tenants), implementar antes de multi-tenant real

---

### GAP 9 — `IGatewayPagamento` Port
**Problema:** O port `IPaymentGateway` pode existir na story 4-9, mas não está formalizado como o ponto de extensão para QR Code Pix, webhooks de confirmação e troca de gateway.

**Status:** ⬜ Verificar se a story 4-9 implementou o port corretamente

---

## Modelo de Negócio: Locação com Opção de Compra (DECISÃO FINAL)

**Confirmado por Pablo em 2026-05-22:**

> "O usuário tem direito de ficar com o carro se pagar todas as parcelas + parcela final."
> "Se ele cancela o contrato (sem dever nenhuma parcela), não existe mais qualquer saldo devedor a pagar."

### Estrutura do Contrato
- **N parcelas mensais** de valor fixo (ex: 100 × R$800 = R$80.000) = pagamento pelo USO do veículo
- **1 parcela única final** (opção de compra, ex: R$20.000) = exercício do direito de propriedade
- **Total**: R$100.000

### Regra de Saldo Devedor
```
saldo_devedor = SUM(titulos WHERE status = 'em_atraso' AND kind = 'parcela')
```

**NÃO é** `valor_total_contrato - total_pago` (esse seria modelo de financiamento/empréstimo).

Parcelas futuras não são "dívida" — são obrigações condicionais à continuidade do contrato.

### Dois Desfechos Possíveis
1. **Saída limpa** (sem atraso): contrato → `encerrado_sem_pendencia`, veículo → `disponivel`, zero cobrança
2. **Saída com atraso**: parcelas atrasadas viram passivo inoperante, contrato → `encerrado_com_pendencia`
3. **Exercício de opção de compra**: paga todas as parcelas + parcela final → veículo transferido para o cliente

### Tipos de Título (`titulo.kind`)
- `parcela` — mensalidade regular de locação
- `opcao_compra` — parcela única final; se paga → dispara `OpcaoCompraPaga` → propriedade do veículo transferida
- `multa` — multa contratual (saída antecipada, se parametrizada)
- `taxa` — taxa avulsa
- `ajuste` — ajuste manual

### Estados do Contrato (atualizados)
- `rascunho` → `ativo`
- `ativo` → `suspenso` (inadimplência ≥ N dias, automático)
- `suspenso` → `ativo` (pagamento confirmado)
- `ativo` → `encerrado_sem_pendencia` (saída limpa, sem atraso)
- `ativo` → `encerrado_com_pendencia` (saída com atraso — passivo gerado)
- `ativo` → `encerrado_compra` (opção de compra exercida — veículo alienado)
- `ativo` → `rescindido` (acordo formal entre as partes)

### Multa por Cancelamento Antecipado (DECISÃO FINAL — 2026-05-22)

Campo `percentual_multa_cancelamento NUMERIC(5,2) NOT NULL DEFAULT 0.00` na tabela `contratos`.

- Default `0.00` = cancelamento antecipado sem custo (comportamento padrão)
- Se configurado (ex: `5.00` = 5%), ao cancelar o contrato sem atraso, o sistema gera um título `kind='multa'` com valor calculado
- Cálculo: `valor_multa = parcelas_restantes × valor_parcela × (percentual_multa_cancelamento / 100)`
- O gestor define esse percentual no wizard de criação do contrato (campo opcional, default vazio = 0%)

**Impacto no código:**
- `contratos`: novo campo `percentual_multa_cancelamento`
- `ServicoSituacaoContrato.transicionar(→ 'encerrado_sem_pendencia')`: se `percentual > 0`, gera título `kind='multa'` antes de fechar
- Frontend: campo "Multa por cancelamento antecipado (%)" no Passo 2 do wizard de contrato, com hint "0% = sem multa"

---

## Próximos Passos

1. ✅ Pablo respondeu perguntas dos gaps principais
2. ✅ Agentes documentaram decisões
3. ✅ Épico 13 criado e revisado (15 histórias)
4. ✅ Nomenclatura PT-BR aplicada (`quando_` para hooks, `Evento` para eventos, `processar_/gerar_/alertar_` para tasks)
5. ✅ Decisão de configuração tipada via `config.configuracoes_sistema` (substitui `politica_cobranca`)
6. ✅ 3 nuances do modelo de negócio incorporadas: fusão de pagamento parcial, desbloqueio com expiração, override de FIPE
7. ⬜ **Próximo:** implementar História 12.1 (renomeação PT-BR) — risco baixo, fundação para o resto

**Sequência de implementação confirmada:**
`12.1 → 12.4 → 12.2 → 12.3 → 12.5 → 12.10 → 12.6 → 12.7 → 12.8 → 12.9 → 12.11 → 12.13 → 12.12 → 12.14 → 12.15`

**Regra invariável:** rodar `bmad-code-review` após cada `bmad-dev-story`.

---

## Épico 13 — Rascunho Inicial

> Ver rascunho completo em `_bmad-output/planning-artifacts/epics.md` seção "Épico 13"
