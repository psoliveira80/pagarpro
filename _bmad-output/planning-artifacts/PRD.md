# PRD — {{product_name}} (Plataforma Genérica de Cobrança Recorrente e Gestão de Ativos)

> **Método:** BMAD (Breakthrough Method for Agile AI-Driven Development)
> **Tipo de Projeto:** Greenfield Fullstack (Web Responsivo)
> **Versão do Documento:** 3.1
> **Data:** 27/05/2026
> **Autor (Agente PM):** John (BMAD)
> **Stakeholder Principal:** Gestor de Negócios (Cliente Final)
> **Nome do Produto:** `{{product_name}}` (configurável no deploy)

---

## 1. Objetivos e Contexto

### 1.1 Objetivos do Produto

- **G1.** Oferecer uma **plataforma genérica de cobrança recorrente e gestão de recebíveis** que substitua planilhas e processos manuais para qualquer negócio que alugue, loque, financie ou assine ativos ou serviços — eliminando retrabalho de digitação e divergências entre versões.
- **G2.** Reduzir em **>= 70%** o tempo gasto com cobranças manuais via WhatsApp através de um **Agent Orchestrator** conversacional inteligente e parametrizável — capaz de operar em qualquer canal (WhatsApp remoto, chat in-app web) e executar qualquer ação que o caller esteja autorizado a realizar (cobrança sendo o caso de uso primário).
- **G3.** Garantir **rastreabilidade financeira completa** (auditoria) de cada título a receber e a pagar, do nascimento à baixa, com conciliação bancária verificável.
- **G4.** Implementar uma **Asset Abstraction Layer** com interface `IAssetModule` que permite plugar módulos verticais (Vehicles, Properties, Services, etc.) sem alterar o core — comunicação exclusivamente via Domain Events + Module Hooks.
- **G5.** Entregar o **primeiro módulo vertical: Vehicles (Frota)** — incluindo integração FIPE, rastreador GPS com bloqueio/desbloqueio remoto por inadimplência, depreciação patrimonial, ROI por veículo e mapa da frota.
- **G6.** Permitir **flexibilidade contratual total** (entrada + N parcelas + extras semestrais/anuais + carências + juros customizáveis), mantendo títulos baixados imutáveis e títulos em aberto editáveis em lote.
- **G7.** Construir uma arquitetura **plug-and-play** onde fornecedores externos (WhatsApp, Open Finance, gateway de pagamento, LLM, OCR, storage, módulos verticais) sejam intercambiáveis sem refatoração de regras de negócio.
- **G8.** Entregar uma experiência de UI/UX **premium** com componentes sofisticados (drag-and-drop em conciliação, chat estilo WhatsApp, mapas interativos, dashboards reativos com Signals).

### 1.2 Contexto

A plataforma {{product_name}} nasce para atender um mercado amplo de negócios que operam com **cobrança recorrente e gestão de ativos**: frotas de veículos, locação de imóveis, assinaturas de serviços, equipamentos alugados, etc. O core genérico cobre: clientes, contratos com construtor flexível de parcelas, recebíveis (lifecycle de 7 estados), contas a pagar, agente de cobrança IA via WhatsApp, conciliação bancária, dashboards e auditoria. Módulos verticais plugáveis adicionam funcionalidades de domínio específico.

O **primeiro deployment target** é um operador de frota com dezenas de veículos alugados a motoristas de aplicativo (Uber, 99 etc.). O modelo de negócio é semelhante a um *rent-to-own* informal: o motorista paga parcelas (diárias, semanais ou mensais) e, em alguns contratos, pode adquirir o veículo ao final. Hoje, a operação é controlada via Excel, com os seguintes gargalos identificados:

1. **Cobrança manual repetitiva**: o gestor envia mensagens individuais aos clientes atrasados, sem histórico estruturado, sem políticas consistentes e sem escalonamento automático.
2. **Conciliação bancária frágil**: comprovantes de Pix chegam por WhatsApp e são "validados no olho", levando a fraudes e baixas erradas. Verificação automática via gateway (ex.: Asaas) é descartada pelo custo de R$ 2,00/Pix em volume > 100/mês.
3. **Falta de visão financeira consolidada**: não há cálculo de ROI por ativo, depreciação patrimonial, comparativo aquisição x retorno, nem indicadores operacionais.
4. **Contratos rígidos**: alterar parcelas em massa (ex.: dar carência em uma semana de greve) é trabalhoso; contratos personalizados são feitos em Word manualmente.
5. **Sem integração com sistemas de domínio**: a localização e o bloqueio de veículos dependem de logar em outro app, fora do fluxo de cobrança.

**Fluxo de pagamento padrão (sem gateway):** O agente envia card Pix via WhatsApp -> cliente paga diretamente na conta bancária -> envia screenshot do comprovante -> agente executa OCR e valida -> baixa primária com status `pago_aguardando_verificacao` (aguardando conciliação bancária). Plugins de pagamento (Asaas, Stripe, boleto, cartão) podem ser habilitados opcionalmente para conveniência.

**Pagamentos parciais:** Se o valor pago é menor que o título em aberto, ocorre baixa parcial e a DIFERENÇA gera um novo título em aberto com um novo ciclo de cobrança.

**Lifecycle de títulos:** Títulos são gerados na finalização do contrato. Alterações contratuais reemitem títulos em aberto (cancelam os antigos, geram novos). Títulos pagos ou baixados são IMUTÁVEIS.

O produto deve absorver as grandes áreas funcionais — **Cadastro & Ativos (genérico + verticais)**, **Financeiro (CR/CP)**, **Cobrança Inteligente** e **Conciliação Bancária** — sob um mesmo guarda-chuva, com dashboards executivos no topo, e ser entregue como SaaS *single-tenant first* (preparado para *multi-tenant* futuro).

---

**Modelo de negócio: Locação com Opção de Compra (Rent-to-Own)**

O primeiro deployment target opera no modelo de **locação com opção de compra**, cujo funcionamento é:

- **N parcelas mensais** (ex.: 100 × R$ 800 = R$ 80.000) — representam o pagamento pelo uso do veículo durante o período contratual.
- **1 parcela única final** = opção de compra (ex.: R$ 20.000) — se paga, o veículo é formalmente transferido ao cliente; se não paga ou não exercida, o veículo retorna à frota.
- **Cancelamento sem atraso** → zero saldo devedor; o veículo retorna à frota sem passivo.
- **Cancelamento com parcelas em atraso** → apenas as parcelas efetivamente atrasadas constituem passivo; não há "valor residual do contrato" a cobrar.
- **`saldo_devedor`** de um cliente é definido como `SUM(titulos WHERE tipo = 'parcela' AND status = 'em_atraso')` — nunca o valor residual do contrato inteiro.

---

### 1.3 Histórico de Mudanças

| Data       | Versão | Descrição                                                                 | Autor     |
|------------|--------|---------------------------------------------------------------------------|-----------|
| 07/05/2026 | 1.0    | Criação inicial do PRD a partir do brief                                  | John (PM) |
| 07/05/2026 | 2.0    | Reescrita como plataforma genérica com Asset Abstraction Layer + Vehicle Module | John (PM) |
| 22/05/2026 | 3.0    | Clarificação do modelo de negócio (locação com opção de compra); especificação do Motor de Cobrança Autônomo (32 tasks, 7 filas, paralelismo coordinator + fan-out em lotes de 50 + 3 camadas de idempotência); novos requisitos FR-CORE-COB-11 a 16 e FR-CORE-CR-12; introdução do enum `tipo_titulo` (`parcela`, `opcao_compra`, `multa`, `taxa`, `ajuste`); passivos inoperantes; máquina de estados do contrato expandida (7 estados: `rascunho`, `ativo`, `suspenso`, `encerrado_sem_pendencia`, `encerrado_com_pendencia`, `encerrado_compra`, `rescindido`); convenção PT-BR consolidada para termos técnicos. | John (PM) |
| 27/05/2026 | 3.1    | Refinamento do construtor de parcelamento pós-smoke-test (FR-CORE-CTR-2 expandido com tipo de intervalo + sub-campos condicionais, multa/juros, parcela final, toggle de correção — Story 13.16); regra explícita de geração N+1 títulos quando há opção de compra (FR-CORE-CTR-3); novo FR-CORE-CTR-11 (boleto proporcional ao suspender/cancelar) com fórmula, parâmetros e regras; novo FR-CORE-CR-13 (multa/juros por contrato); novo FR-CORE-INT-4 (índices de correção plugáveis via `IIndiceCorrecao`). | John (PM) + Amelia (dev) |

---

## 2. Requisitos

### 2.1 Requisitos Funcionais

> Convenção de IDs:
> - **Core (genérico):** `FR-CORE-{módulo}-{nº}`. Módulos core: `AUTH` (autenticação), `CAD` (cadastros genéricos), `CTR` (contratos), `CR` (contas a receber), `CP` (contas a pagar), `COB` (cobranças), `CON` (conciliação), `DSH` (dashboards/relatórios), `INT` (integrações), `PRM` (parametrização), `AUD` (auditoria), `AST` (asset abstraction).
> - **Vehicle Module:** `FR-VH-{nº}`. Requisitos específicos do módulo vertical de veículos.

---

#### Asset Abstraction Layer (AST) — Core

- **FR-CORE-AST-1.** O core deve definir a interface `IAssetModule` que cada módulo vertical implementa:
  ```python
  class IAssetModule(Protocol):
      module_id: str  # ex.: "vehicles", "properties", "services"
      display_name: str

      async def on_contract_created(self, event: ContractCreatedEvent) -> None: ...
      async def on_contract_terminated(self, event: ContractTerminatedEvent) -> None: ...
      async def on_installment_overdue(self, event: InstallmentOverdueEvent) -> None: ...
      async def on_installment_paid(self, event: InstallmentPaidEvent) -> None: ...
      async def on_reconciliation_completed(self, event: ReconciliationEvent) -> None: ...
      async def get_asset_details(self, asset_id: UUID) -> AssetDetails: ...
      async def get_asset_financials(self, asset_id: UUID) -> AssetFinancials: ...
      async def get_dashboard_widgets(self) -> list[DashboardWidget]: ...
      async def get_report_dimensions(self) -> list[ReportDimension]: ...
      async def get_agent_tools(self) -> list[AgentTool]: ...
  ```
- **FR-CORE-AST-2.** O core NUNCA importa código de módulo diretamente. A comunicação é via Domain Events publicados em um event bus interno (sync in-process para MVP, evoluível para async message broker). Módulos registram hooks no startup.
- **FR-CORE-AST-3.** O core deve manter uma tabela `assets` genérica com: `id`, `module_id`, `external_ref` (ID do registro no módulo), `display_name`, `status` (`disponivel`/`em_uso`/`manutencao`/`inativo`), `metadata` (JSONB). Contratos referenciam `asset_id` em vez de entidades específicas.
- **FR-CORE-AST-4.** O sistema deve permitir ativar/desativar módulos verticais em Configurações > Módulos, sem restart. Módulos desabilitados não recebem eventos e seus hooks ficam inativos.
- **FR-CORE-AST-5.** O core deve fornecer lifecycle hooks para eventos de domínio que módulos podem escutar: `InstallmentOverdue`, `InstallmentPaid`, `ContractCreated`, `ContractTerminated`, `ReconciliationCompleted`, `CustomerScoreChanged`, `PaymentPartiallyReceived`.

---

#### Autenticação & Controle de Acesso (AUTH) — Core

- **FR-CORE-AUTH-1.** O sistema deve oferecer login por e-mail/senha com hash Argon2id e MFA opcional (TOTP).
- **FR-CORE-AUTH-2.** O sistema deve suportar perfis: *Admin* (gestor/dono), *Operador* (funcionário com permissão limitada — pode lançar mas não excluir/alterar parametrização global), *Validador* (apenas validação de comprovantes e conciliação) e *Auditor Read-only*.
- **FR-CORE-AUTH-3.** Cada perfil tem matriz de permissão granular por módulo (CRUD + ações sensíveis como "estornar baixa", "aprovar cobrança em lote"). Módulos verticais podem registrar permissões adicionais (ex.: Vehicle Module registra "bloquear veículo via rastreador").
- **FR-CORE-AUTH-4.** Toda sessão deve emitir JWT de curta duração (15 min) com refresh token rotativo (7 dias) armazenado em cookie `HttpOnly Secure SameSite=Lax`.
- **FR-CORE-AUTH-5.** O sistema deve registrar log de login/logout, IP, user-agent e tentativas falhadas (5 tentativas -> bloqueio temporário de 15 min).

---

#### Cadastros Genéricos (CAD) — Core

- **FR-CORE-CAD-1.** O sistema deve permitir cadastro de **Cliente** com: nome completo, CPF/CNPJ (com validação), RG, telefone (formato E.164), e-mail, endereço completo (CEP via ViaCEP), data de nascimento, foto de perfil, observações livres, e até **N anexos** (PDF, JPG, PNG até 10 MB cada). Campos adicionais específicos de vertical (ex.: CNH para Vehicle Module) são registrados pelo módulo via schema extension.
- **FR-CORE-CAD-2.** O core deve manter um registro genérico de **Ativo** (tabela `assets`) conforme FR-CORE-AST-3. Cada módulo vertical gerencia seus próprios cadastros detalhados de ativo e sincroniza com a tabela `assets` do core.
- **FR-CORE-CAD-3.** O sistema deve permitir agrupar ativos em **categorias** genéricas para fins de relatório. Módulos verticais podem definir categorias de domínio adicionais.

---

#### Vehicle Module — Cadastros (VH)

- **FR-VH-1.** O módulo Vehicles deve permitir cadastro de **Veículo** com: placa (validação Mercosul), Renavam, chassi, marca, modelo, versão, ano modelo/fabricação, cor, combustível, KM atual, KM inicial (na compra), data de aquisição, valor de compra, valor FIPE atual (preenchido via integração), código FIPE, código do rastreador (vínculo com dispositivo), status (`disponivel` / `alugado` / `manutencao` / `vendido` / `inativo`), seguradora, apólice, vencimento do seguro, IPVA, vencimento do IPVA, licenciamento, vencimento do licenciamento, fotos (galeria com lightbox). O registro é sincronizado com a tabela `assets` do core.
- **FR-VH-2.** O módulo deve buscar automaticamente dados FIPE do veículo cadastrado mediante seleção encadeada `marca -> modelo -> ano-combustível` e atualizar o `valor_fipe_atual` periodicamente (job mensal automático no dia 5 de cada mês).
- **FR-VH-3.** O módulo deve permitir cadastro do **modelo de pagamento da aquisição do veículo** (forma como o gestor adquiriu o carro): à vista, financiado (com entrada, N parcelas, taxa de juros mensal, sistema de amortização — Price ou SAC), consórcio (com lance, parcelas restantes, taxa adm) ou outras formas (custom: lista de parcelas datadas livres). Esse modelo é vinculado ao veículo e usado em cálculos de ROI.
- **FR-VH-4.** O módulo deve calcular e exibir, para cada veículo, em tempo real: **valor patrimonial atual** (FIPE), **depreciação acumulada** (compra - FIPE), **total já pago à fonte de financiamento**, **saldo devedor da aquisição**, **total recebido em locação**, **ROI percentual** ((recebido - pago) / pago x 100) e **payback projetado** (em meses).
- **FR-VH-5.** O módulo deve oferecer um **mapa interativo** (Leaflet com tile server OSM, swappable para Google Maps) mostrando a posição atual de cada veículo da frota. Clique no marcador exibe popup com dados do cliente responsável, status do contrato e botões rápidos (ver detalhes, bloquear, ligar para cliente via `tel:`).
- **FR-VH-6.** O módulo deve cadastrar campos adicionais no Cliente via schema extension: CNH (número + categoria + validade + foto).
- **FR-VH-7.** O módulo deve implementar hook `on_installment_overdue`: verificar política de bloqueio parametrizada (dias atraso >= X AND score < Y) e, se aplicável, disparar bloqueio GPS via `ITrackerGateway`. Bloqueio pode ser automático quando a política configurada pelo Admin permite (auto_block=true AND critérios atendidos). Aprovação humana é configurável, não obrigatória.
- **FR-VH-8.** O módulo deve registrar tools adicionais para o Agent Orchestrator IA: `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao_veiculo`. Esses tools são injetados via `IAssetModule.get_agent_tools()`.

---

#### Contratos (CTR) — Core

- **FR-CORE-CTR-1.** O sistema deve permitir gerar um **Contrato** vinculando um Cliente a um Ativo (`asset_id`), contendo: data de início, data prevista de término, valor total, modelo de parcelamento, periodicidade da cobrança (`diaria`, `semanal`, `quinzenal`, `mensal`), dia de vencimento, juros por atraso (% ao dia, parametrizável por contrato), multa por atraso (% fixo), carência em dias, possibilidade de compra do ativo (sim/não, com `valor_opcao_compra` e cláusula de transferência), garantias (caução, fiador), cláusulas livres em texto rico. O campo `situacao` do contrato deve suportar os seguintes estados: `rascunho` (editável, ainda não vigente), `ativo` (em curso, títulos ativos), `suspenso` (inadimplência atingiu `limite_dias_suspensao` — serviço interrompido, títulos seguem acumulando), `encerrado_sem_pendencia` (todas as parcelas quitadas, sem saldo devedor), `encerrado_com_pendencia` (encerrado pelo motor após `limite_dias_encerramento`, com parcelas em atraso registradas como `passivo_inoperante`), `encerrado_compra` (opção de compra exercida — veículo/ativo transferido ao cliente), `rescindido` (rescisão antecipada manual). A transição `ativo → suspenso` é automática via Motor de Cobrança após `limite_dias_suspensao` dias de inadimplência configurados na `politica_cobranca`.
- **FR-CORE-CTR-2.** O sistema deve oferecer **construtor visual de parcelamento** com as seguintes possibilidades combináveis:
  - Entrada única (data + valor).
  - **N parcelas regulares** (qtd, valor, periodicidade, primeiro vencimento).
  - **Parcelas extras semestrais ou anuais** (ex.: 13a parcela em dezembro).
  - **Carência inicial** (X dias sem cobrança após assinatura).
  - **Custom Schedule**: tabela editável onde o usuário pode arrastar, adicionar, remover ou alterar qualquer linha individualmente antes de salvar.

  **Detalhamento operacional (Story 13.16 — pós-feedback de smoke-test):** O construtor opera primariamente com **valor por parcela + quantidade** (o valor total é derivado: `valor_total = valor_parcela × quantidade + valor_parcela_final`), e expõe os seguintes campos no wizard:
  - **Tipo de intervalo** (select obrigatório com sub-campos condicionais):
    - `semanal` → sub-campo "Dia da semana" (Seg..Dom).
    - `mensal` → sub-campo "Dia do mês" (1..31, com fallback para último dia útil em meses curtos).
    - `personalizado_dias` → sub-campo "Número de dias" (inteiro ≥ 1).
    - Arquitetura extensível para tipos futuros (`diaria`, `quinzenal`, `datas_customizadas`) sem refator.
  - **Multa e juros por atraso** (decimais, 2 casas, % a.m.) — armazenados **por contrato** (ver FR-CORE-CR-13).
  - **Valor da parcela final ("opção de compra")** — opcional; quando preenchido, gera 1 título extra do tipo `opcao_compra` na data seguinte à última parcela regular.
  - **Toggle de aplicação de índice de correção** — quando ligado, exibe seletor com índices de correção `ativo=true` em `config.credenciais_integracao` (ver FR-CORE-INT-4). Espelho de parcelas e total geral refletem valores corrigidos.

  Especificação UX completa em `docs/wizard-contrato-detalhamento-ux.md`.
- **FR-CORE-CTR-3.** Ao finalizar o contrato (status `ativo`), o sistema deve gerar automaticamente os **Títulos a Receber** com status inicial `em_aberto`, vinculados ao contrato. A tabela `titulos` deve distinguir o tipo de título via campo `tipo` (enum `tipo_titulo`): `parcela` (mensalidade regular de locação), `opcao_compra` (parcela única final que, se paga, transfere a propriedade do ativo ao cliente), `multa`, `taxa`, `ajuste`. **Regra de geração:** quando `contrato.valor_parcela_final > 0` (ou `valor_opcao_compra IS NOT NULL`), o sistema gera **N+1 títulos** — N do tipo `parcela` com `numero_parcela` sequencial + 1 do tipo `opcao_compra` na data seguinte à última parcela (respeitando o `tipo_intervalo` do contrato). Quando `valor_parcela_final` é nulo ou zero, gera apenas N parcelas regulares. O pagamento do título `opcao_compra` dispara o evento `ContractPurchaseOptionExercised`, que muda a `situacao` do contrato para `encerrado_compra` e notifica o módulo vertical para executar a transferência de propriedade do ativo. Alterações contratuais que afetam parcelas devem cancelar títulos em aberto antigos e gerar novos (reemissão).
- **FR-CORE-CTR-4.** O sistema deve gerar uma **versão renderizada do contrato em PDF** usando template Jinja2 + WeasyPrint, com placeholders preenchidos (dados do cliente, ativo, parcelas, cláusulas, assinaturas), e armazenar no S3-compatível com hash SHA-256.
- **FR-CORE-CTR-5.** O sistema deve permitir **assinatura digital** do contrato (anexo de PDF assinado eletronicamente OU integração futura com D4Sign/Clicksign — ponto de extensão).
- **FR-CORE-CTR-6.** O sistema deve permitir **edição em lote** de títulos em aberto (ex.: postergar todas as parcelas em aberto em 7 dias; aplicar desconto de 10%; mudar valor padrão a partir da próxima). Operações sempre dentro de uma **transação atômica** com gravação de evento de auditoria.
- **FR-CORE-CTR-7.** Títulos com status `pago` (baixados) são **imutáveis**. Qualquer correção exige **estorno de baixa** (que gera evento de auditoria) e regravação. Apenas Admin pode estornar.
- **FR-CORE-CTR-8.** O sistema deve permitir **rescisão de contrato** com cálculo de saldo (multa rescisória parametrizável, soma dos abertos x percentual), gerando título de cobrança final ou crédito a favor do cliente. Ao rescindir, emite evento `ContractTerminated` para que o módulo vertical execute ações de domínio (ex.: Vehicle Module libera veículo para `disponivel`).
- **FR-CORE-CTR-9.** O sistema deve manter **versionamento de contrato**: alterações relevantes (ex.: alteração do valor da parcela em lote) criam uma nova revisão visível em timeline.
- **FR-CORE-CTR-10.** O sistema deve permitir **simulação de contrato** sem persistir, com preview de todas as parcelas e do valor total — útil antes de fechar.
- **FR-CORE-CTR-11.** O sistema deve gerar **boleto proporcional** quando contrato com pagamento periódico (semanal, mensal, `personalizado_dias`) é **suspenso** ou **cancelado** dentro de um ciclo de cobrança (entre dois vencimentos consecutivos).

  **Fórmula:**
  ```
  valor_proporcional = valor_parcela × (dias_usados_no_ciclo / dias_totais_do_ciclo)
  ```

  **Exemplo (semanal, parcela R$200, quarta a quarta):**
  - Cliente paga parcela na quarta-feira.
  - Pede cancelamento na sexta-feira (2 dias usados).
  - Boleto proporcional = R$200 × (2/7) = R$57,14.

  **Parâmetros configuráveis em `config.configuracoes_sistema` (módulo `financeiro`):**
  - `cobrar_proporcional_ao_suspender` (booleano, default `true`)
  - `cobrar_proporcional_ao_cancelar` (booleano, default `true`)
  - `dia_base_calculo_proporcional` (string: `data_pagamento` | `data_vencimento_anterior`, default `data_vencimento_anterior`)

  **Regras:**
  - Se a última parcela do ciclo ainda **NÃO** foi paga: o título proporcional **substitui** a parcela em aberto (cancela a parcela cheia, gera a proporcional do tipo `taxa` com referência ao título original).
  - Se a última parcela **JÁ** foi paga (cliente pagou adiantado): gera um **crédito** de devolução do valor não usado (`tipo='ajuste'` com valor negativo).
  - **Hooks de domínio:** `quando_contrato_suspenso` e `quando_contrato_encerrado` chamam `ServicoBoletoProporcional.gerar(contrato_id, data_interrupcao)`.
  - Audit log obrigatório com `categoria='financeiro'` registrando data de interrupção, dias usados, valor calculado.

  **Stories que implementam:** 13.17 (`ServicoBoletoProporcional` — domínio + application service + 3 configs) é o coração da regra. Hooks `quando_contrato_suspenso` (Story 13.2) e `quando_contrato_encerrado` (Story 13.8 e rescisão manual) invocam o serviço.

---

#### Contas a Receber (CR) — Core

- **FR-CORE-CR-1.** O sistema deve listar todos os **Títulos a Receber** com filtros multi-seletivos: status (em_aberto, vencido, pago, pago_aguardando_verificacao, pago_parcial, renegociado, cancelado), cliente, ativo, contrato, faixa de vencimento, faixa de valor, faixa de competência.
- **FR-CORE-CR-2.** O sistema deve permitir **registrar baixa manual** de um título com: data efetiva, valor pago, forma (Pix, dinheiro, transferência, cartão, outros), observação, anexo de comprovante (obrigatório para Pix). Status passa a `pago_aguardando_verificacao` (aguarda conciliação).
- **FR-CORE-CR-3.** O sistema deve suportar **pagamentos parciais**: se o valor pago é menor que o título em aberto, ocorre baixa parcial do valor efetivamente pago (status `pago` para o valor parcial) e a DIFERENÇA gera automaticamente um novo título em aberto com novo ciclo de cobrança (vencimento = data atual + grace_days do contrato).
- **FR-CORE-CR-4.** O sistema deve permitir **baixa em lote**: marcar múltiplos títulos do mesmo cliente, somar valores, registrar um único pagamento que quita N títulos.
- **FR-CORE-CR-5.** O sistema deve calcular automaticamente **juros + multa** em títulos vencidos no momento da baixa, exibindo o valor atualizado, e permitir o gestor **conceder desconto** (com motivo registrado).
- **FR-CORE-CR-6.** O sistema deve oferecer **fila de validação de comprovantes** (somente para perfis Validador/Admin) com: imagem/PDF do comprovante, dados do título, valor esperado x valor identificado (OCR), botões `Aprovar`, `Rejeitar com motivo`, `Solicitar reenvio`.
- **FR-CORE-CR-7.** O sistema deve realizar **OCR automático** em comprovantes de Pix recebidos (via tesseract + heurísticas regex para extrair valor, data, e ID de transação) e pré-preencher os campos da validação.
- **FR-CORE-CR-8.** Após aprovação do validador, o título passa para `pago_aguardando_verificacao`. Após conciliação bancária, vai para `pago` (estado final imutável).
- **FR-CORE-CR-9.** O sistema deve gerar **PIX QR Code estático/dinâmico** (BR Code) por título usando a biblioteca `pix-utils` ou similar, sem custo de transação. O QR Code é exibido para envio via WhatsApp ou impressão.
- **FR-CORE-CR-10.** O sistema deve permitir **integração opcional** com gateway Pix (Asaas, Efi, PagBank, Stripe) via adapter — desabilitada por padrão para evitar custo, mas habilitável a qualquer momento. Plugins de pagamento adicionais (boleto, cartão de crédito) podem ser ativados como conveniência.
- **FR-CORE-CR-11.** O sistema deve permitir **acordos de renegociação**: agrupar títulos vencidos, recalcular com desconto/parcelamento, gerar novos títulos e marcar os antigos como `renegociado`.

- **FR-CORE-CR-13.** **Multa e juros por atraso são fields do contrato, não constantes globais.** O cálculo de valor atualizado de título em atraso usa `contrato.multa_atraso_pct` e `contrato.juros_atraso_pct` (decimais, % a.m., armazenados na tabela `contratos`), com fallback para configurações globais via `ServicoConfiguracao` (`percentual_multa` e `percentual_juros_dia` em `config.configuracoes_sistema` módulo `financeiro`) quando o contrato não define valor próprio. Esta granularidade por contrato permite acordos comerciais individuais sem alterar a política padrão.

- **FR-CORE-CR-12.** O sistema deve registrar automaticamente como **`passivo_inoperante`** todos os títulos `tipo = 'parcela'` em atraso pertencentes a contratos com situação `encerrado_com_pendencia`, vinculando o passivo ao CPF/CNPJ do cliente na tabela `passivos_inoperantes` (campos: `cliente_id`, `contrato_id`, `valor_original`, `valor_atualizado`, `data_encerramento`, `status` — enum: `ativo`, `baixado_perda`, `recuperado`). O gestor pode: (a) consultar todos os passivos ativos com filtros por cliente, faixa de valor e data; (b) **baixar como perda** (move status para `baixado_perda`, registra justificativa e gera evento de auditoria); (c) **marcar como recuperado** (após recebimento extrajudicial, move para `recuperado` e cria título de entrada avulso). O passivo inoperante de um cliente deve ser exibido em destaque — com valor total e data de origem — na tela de seleção de cliente durante a criação de novo contrato, permitindo ao gestor tomar decisão informada antes de fechar o negócio.

---

#### Contas a Pagar (CP) — Core

- **FR-CORE-CP-1.** O sistema deve permitir cadastrar **Categorias de Despesa** hierárquicas (ex.: Manutenção > Mecânica > Motor; Tributos > IPVA). Categorias padrão são definidas pelo core; módulos verticais podem registrar categorias adicionais.
- **FR-CORE-CP-2.** O sistema deve permitir cadastrar **Fornecedores** com dados básicos (razão social, CNPJ, contato, dados bancários).
- **FR-CORE-CP-3.** O sistema deve permitir lançar **Título a Pagar** (avulso) com: descrição, fornecedor, categoria, ativo vinculado (opcional — `asset_id`), valor, vencimento, status, anexo de NF/recibo.
- **FR-CORE-CP-4.** O sistema deve permitir cadastrar **Despesas Recorrentes** (ex.: aluguel, salário, internet) que geram automaticamente os títulos no dia configurado de cada mês (job agendado).
- **FR-CORE-CP-5.** O sistema deve permitir **lançamento simplificado** "Lançar e Pagar" (gera título e baixa simultaneamente — atalho para gastos imediatos).
- **FR-CORE-CP-6.** O sistema deve calcular **DRE simplificado** (Receitas - Despesas) por período, com filtros por ativo, categoria e centro de custo.

---

#### Agent Orchestrator & Messaging (COB) — Core

> **Nota:** Cobrança é o caso de uso **primário**, mas o Agent Orchestrator é um motor genérico que aceita qualquer comando que o caller esteja autorizado a executar. Ele recebe texto, áudio (transcrito) e imagens de qualquer canal — WhatsApp (remoto) ou chat in-app (web UI) — e despacha tools filtrados pelas permissões RBAC do caller.

- **FR-CORE-COB-1.** O sistema deve integrar com WhatsApp via adapter (default: **Evolution API self-hosted**; alternativas: Z-API, UazAPI, WPPConnect, WhatsApp Cloud API oficial — selecionável por configuração).
- **FR-CORE-COB-1B.** O mesmo Agent Orchestrator deve servir o **chat in-app** (web UI) via HTTP/WebSocket. O gestor pode digitar comandos no chat web e receber as mesmas respostas e ações disponíveis no canal WhatsApp. O orchestrator é agnóstico de canal — recebe `AgentInput(text, media, caller, permissions)` e não sabe nem se importa de onde veio a mensagem.
- **FR-CORE-COB-1C.** O sistema deve aceitar **mensagens de áudio** e transcrevê-las automaticamente antes de passar ao orchestrator, via port plugável `IAudioTranscriber` (default: **OpenAI Whisper API**; alternativas: `LocalWhisperAdapter` via whisper.cpp, `GoogleSpeechAdapter`, `AzureSpeechAdapter`). O resultado da transcrição é tratado como texto normal pelo orchestrator.
- **FR-CORE-COB-2.** O sistema deve oferecer um **Agent Orchestrator IA** com:
  - **LLM** plugável (default: OpenAI GPT-4o; alternativas: Anthropic Claude, Google Gemini, modelos locais via Ollama).
  - **RAG** sobre histórico do cliente (todos os títulos, conversas anteriores, comprovantes, score, observações, contrato vigente).
  - **Tools com permissão RBAC**: a lista de tools disponíveis em cada sessão é composta dinamicamente com base nas permissões do caller. Admin tem acesso a todos os tools. Operador tem acesso restrito conforme sua matriz de permissão. Motorista/Cliente tem acesso apenas a consultas dos próprios dados + envio de comprovantes.
  - **Tools core** (cobrança — caso de uso primário) acessíveis via function-calling: `consultar_titulos_em_aberto`, `enviar_qr_pix`, `registrar_baixa_primaria`, `solicitar_validacao_humana`, `agendar_cobranca`, `gerar_acordo`, `escalar_para_gestor`.
  - **Tools de módulo vertical**: injetados dinamicamente via `IAssetModule.get_agent_tools()` (ex.: Vehicle Module injeta `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao_veiculo`).
  - **Memória conversacional** persistente (histórico das últimas N mensagens trazido a cada turno).
- **FR-CORE-COB-3.** O sistema deve permitir **parametrizar regras do agente** (totalmente sem código):
  - Tom (formal, amigável, descontraído).
  - Saudação por horário do dia.
  - Antecedência da cobrança preventiva (ex.: 2 dias antes do vencimento).
  - Frequência de follow-up (ex.: a cada 24h após vencimento).
  - **Política de concessão por score**: thresholds (ex.: score >= 80 -> tolerância de 5 dias; score 50-79 -> 2 dias; < 50 -> cobrança imediata).
  - Limite máximo de dias de tolerância antes de escalar a humano.
  - Juros e multa aplicáveis.
  - Templates de mensagem por evento (preventiva, pós-vencimento D+1, D+3, D+7, confirmação de recebimento, agradecimento de pagamento).
  - **Políticas de módulo vertical**: cada módulo pode registrar políticas adicionais (ex.: Vehicle Module adiciona "dias antes de bloqueio" e "ameaça de bloqueio").
- **FR-CORE-COB-4.** O sistema deve calcular **score de cliente** (0-100) com base em: % de pagamentos em dia nos últimos 12 meses, dias médios de atraso, tempo de relacionamento, valor histórico pago. Módulos verticais podem contribuir com fatores adicionais (ex.: Vehicle Module adiciona "n. de bloqueios sofridos"). Fórmula configurável.
- **FR-CORE-COB-5.** O sistema deve enviar automaticamente o **QR Code Pix do título** (formato BR Code + texto "Copia e Cola") em formato compatível com card Pix do WhatsApp. Este é o fluxo padrão de pagamento: envio do Pix card -> pagamento direto na conta -> screenshot do comprovante -> OCR + validação -> baixa primária.
- **FR-CORE-COB-6.** Ao receber **mensagem com imagem/PDF** via webhook do WhatsApp, o agente deve: detectar se é comprovante (classificador), executar OCR, extrair valor e data, casar com título em aberto. Se valor extraído < valor do título, executar **baixa parcial** (gera novo título para a diferença). Se valor >= título, executar **baixa primária** (status `pago_aguardando_verificacao`). Responder confirmação com tom apropriado e adicionar à fila de validação humana.
- **FR-CORE-COB-7.** O sistema deve oferecer **interface de chat estilo WhatsApp** dentro do app (bolhas verde-claro/branco, timestamps, ticks de leitura, anexos, áudios, separadores por dia), com lista de conversas à esquerda, painel de chat ao centro, painel de contexto do cliente à direita (score, títulos em aberto, ações rápidas).
- **FR-CORE-COB-8.** O gestor deve poder **interceptar** uma conversa em andamento (modo "humano assume"), pausando o agente. O agente é retomado mediante clique em "Devolver para o agente".
- **FR-CORE-COB-9.** O sistema deve permitir **disparos em massa** de cobranças (com confirmação dupla, preview, e respeito a janela horária — ex.: não enviar antes das 8h ou depois das 20h).
- **FR-CORE-COB-10.** O sistema deve manter **histórico imutável** de mensagens (incoming + outgoing), com IDs externos para reconciliação com a Evolution API.

- **FR-CORE-COB-11.** O sistema deve possuir um **Motor de Cobrança Autônomo** com 32 tasks Celery organizadas em 7 filas independentes: `fila_cobranca` (cobranças agendadas e preventivas), `fila_notificacoes` (envio de mensagens WhatsApp), `fila_verificacao` (OCR e validação de comprovantes), `fila_contratos` (geração de títulos, encerramento e opção de compra), `fila_frota` (hooks do Vehicle Module), `fila_padrao` (tarefas gerais de manutenção) e `fila_whatsapp_entrada` (processamento de mensagens recebidas). O motor opera 24h com **paralelismo real**: padrão coordinator + fan-out em lotes de 50 clientes por task + 3 camadas de idempotência (chave Celery por tarefa, deduplicação por `external_id` no banco, lock Redis por entidade processada).

- **FR-CORE-COB-12.** O motor deve aplicar **encargos automáticos** (juros diários + multa por atraso) em todos os títulos vencidos, diariamente, registrando cada acréscimo na tabela `titulo_ajustes` com rastreabilidade completa (data, percentual aplicado, valor calculado, título de origem).

- **FR-CORE-COB-13.** O motor deve **verificar automaticamente comprovantes de pagamento** recebidos via WhatsApp utilizando OCR + validação cruzada de valor e data. Quando a confiança do OCR for >= 70% e o valor extraído casar com um título em aberto do cliente, o motor deve reconciliar o comprovante com o título correspondente e executar a baixa primária (`pago_aguardando_verificacao`) sem intervenção manual. Casos com confiança < 70% ou ambiguidade são encaminhados para a fila de validação humana.

- **FR-CORE-COB-14.** O motor deve **escalonar automaticamente a inadimplência** seguindo a sequência de estados configurada na `politica_cobranca` da empresa: lembrete preventivo (D-N dias antes do vencimento) → cobrança pós-vencimento (D+1) → aviso de suspensão iminente (D+`limite_aviso_suspensao`) → suspensão automática do contrato (D+`limite_dias_suspensao`, transição `ativo → suspenso`) → encerramento com passivo registrado (D+`limite_dias_encerramento`, transição `suspenso → encerrado_com_pendencia`). Cada transição é registrada em `contract_events` e notifica o cliente via WhatsApp com o template configurado.

- **FR-CORE-COB-15.** O motor deve monitorar contratos ativos com `valor_opcao_compra` configurado e, ao detectar que todas as parcelas regulares (`tipo = 'parcela'`) foram pagas, gerar automaticamente o título `tipo = 'opcao_compra'` caso ainda não exista. O cliente deve ser alertado via WhatsApp com 30, 15 e 7 dias de antecedência à data de vencimento da opção de compra.

- **FR-CORE-COB-16.** O sistema deve manter uma tabela `politica_cobranca` por empresa configurando todos os parâmetros do Motor de Cobrança: `antecedencia_lembrete_dias` (dias antes do vencimento para envio preventivo), `carencia_dias` (dias de tolerância após vencimento antes da primeira cobrança), `multa_pct` (percentual de multa por atraso), `juros_pct_dia` (percentual de juros compostos por dia de atraso), `limite_tentativas_cobranca` (máximo de mensagens de cobrança antes de escalar), `limite_aviso_suspensao_dias`, `limite_dias_suspensao` e `limite_dias_encerramento`. Alterações na política geram evento de auditoria e são versionadas.

---

#### Conciliação Bancária (CON) — Core

- **FR-CORE-CON-1.** O sistema deve permitir **importação de extrato OFX** com parsing nativo (`ofxparse`), gerando lista de transações com data, valor, descrição, ID FITID.
- **FR-CORE-CON-2.** O sistema deve permitir **importação de extrato em PDF** (de bancos brasileiros: BB, Itaú, Bradesco, Santander, Caixa, Nubank, Inter, C6 e outros) com parsing inteligente — primeira tentativa via `pdfplumber` + heurísticas; fallback via LLM com prompt estruturado quando heurística falha (configurável).
- **FR-CORE-CON-3.** O sistema deve permitir **integração via Open Finance** (adapter — default: **Pluggy**; alternativas: Belvo, TecnoSpeed, Klavi) para puxar extratos automaticamente sem upload manual.
- **FR-CORE-CON-4.** O sistema deve oferecer **tela de conciliação** com dois painéis lado a lado:
  - **Esquerda**: transações bancárias importadas (não conciliadas).
  - **Direita**: títulos do sistema em status `pago_aguardando_verificacao`.
  - **Centro**: zona de "match" com **drag-and-drop** (arrastar transação sobre título -> confirma conciliação). Auto-sugestões em destaque baseadas em valor + data +/- 3 dias.
- **FR-CORE-CON-5.** O sistema deve oferecer **algoritmo de auto-match** que pré-conecta combinações com confiança >= X% (configurável); o usuário só revisa e clica para confirmar.
- **FR-CORE-CON-6.** O sistema deve permitir **conciliação 1:N** (uma transação cobrindo múltiplos títulos) e **N:1** (múltiplas transações para um título — caso de pagamento parcelado), além de **transações sem título** (despesas/receitas avulsas que viram lançamento livre).
- **FR-CORE-CON-7.** O sistema deve mostrar **divergências**: transação no extrato sem título correspondente (alerta), título marcado como pago sem transação no extrato (suspeita), valores diferentes (vermelho).
- **FR-CORE-CON-8.** Após conciliação, o título passa de `pago_aguardando_verificacao` para `pago` (estado final imutável). A transação é marcada como `conciliada` e fica visível mas bloqueada.

---

#### Dashboards & Relatórios (DSH) — Core

- **FR-CORE-DSH-1.** O sistema deve oferecer um **Dashboard Principal** com KPIs genéricos em cards reativos (Signals): Receita do Mês, Despesas do Mês, Lucro Líquido, Inadimplência (%), Ativos em Uso, Ativos Parados, Patrimônio Total (R$), Próximos Vencimentos (7 dias), Comprovantes Pendentes, Score Médio da Carteira. Módulos verticais podem injetar widgets adicionais via `IAssetModule.get_dashboard_widgets()`.
- **FR-CORE-DSH-2.** O sistema deve oferecer **Dashboard Financeiro por Cliente** com: histórico completo de títulos, gráfico de pontualidade (linha temporal), score evolutivo, total contratado x pago, dívida atualizada, próximos vencimentos.
- **FR-CORE-DSH-3.** O sistema deve oferecer **relatórios prontos** exportáveis (Excel/PDF):
  - Top clientes por receita (12m).
  - Inadimplência por faixa etária (1-7d, 8-30d, 31-60d, 61-90d, > 90d).
  - DRE consolidada e por ativo.
  - Curva ABC de clientes.
  - Módulos verticais podem registrar relatórios adicionais via `IAssetModule.get_report_dimensions()`.
- **FR-CORE-DSH-4.** O sistema deve oferecer **construtor de relatório customizado** (drag-and-drop de dimensões e medidas) com salvamento de relatórios favoritos.

---

#### Vehicle Module — Dashboards & Relatórios (VH)

- **FR-VH-9.** O módulo deve injetar widget **Dashboard por Veículo** com: investimento, ROI %, lucro acumulado, depreciação, comparativo aquisição x retorno, KM rodado (se rastreador fornecer), produtividade R$/km, cliente atual, histórico de clientes.
- **FR-VH-10.** O módulo deve registrar relatórios adicionais:
  - Top Veículos por ROI (12m).
  - Histórico de Bloqueios Remotos.
  - Posição da Frota (data X) — valor patrimonial total (FIPE consolidado).
- **FR-VH-11.** O módulo deve injetar no Dashboard Principal: Frota Total (R$ FIPE consolidado), Veículos Ativos, Veículos Parados, Veículos em Manutenção (via `get_dashboard_widgets()`).

---

#### Integrações & Plug-and-Play (INT) — Core

- **FR-CORE-INT-1.** O sistema deve expor **interfaces (Protocols/Ports)** para todos os fornecedores externos, com adapters intercambiáveis: `IWhatsAppGateway`, `IBankReconciliationProvider`, `IPaymentGateway`, `ILLMProvider`, `IStorageProvider`, `IOcrProvider`, `IPdfRenderer`, `IAudioTranscriber`. Módulos verticais podem definir ports adicionais (ex.: Vehicle Module define `IFipeProvider`, `ITrackerGateway`).
- **FR-CORE-INT-2.** O sistema deve oferecer **tela administrativa de Integrações** onde o Admin pode: ativar/desativar adapters, inserir credenciais (encriptadas em repouso), testar conexão (botão "Testar"), ver status (saudável / degradado / offline).
- **FR-CORE-INT-3.** O sistema deve consumir **webhooks** de todos os provedores (Evolution API, Pluggy, gateway de pagamento se ativo, etc.) com validação de assinatura, idempotência (chave única por evento) e fila de processamento via Redis Streams ou Celery.
- **FR-CORE-INT-4.** O sistema deve suportar **índices de correção monetária plugáveis** via padrão `IIndiceCorrecao`. Listagem dinâmica segue o esquema de `config.credenciais_integracao` (categoria=`correction_index`). Apenas providers com `ativo=true` aparecem no wizard de contrato (FR-CORE-CTR-2) e são consumíveis pelo motor de geração de títulos. Adapter default: `BCBCorrectionAdapter` (IGPM, IPCA, INPC via API do Banco Central do Brasil). A taxa do índice é resolvida **no momento da geração de cada título** (snapshot por competência), não no momento da assinatura do contrato.

---

#### Vehicle Module — Integrações (VH)

- **FR-VH-12.** O módulo deve definir e implementar `IFipeProvider` com adapter default `ApiFipeBrAdapter` (apifipe.com.br), alternativa `FipeApiBrAdapter` (fipeapi.com.br) e adapter de fallback. Cache Redis com TTL de 30 dias.
- **FR-VH-13.** O módulo deve definir e implementar `ITrackerGateway` com adapters genéricos (REST, MQTT+REST) para obter posição GPS, velocidade, ignição, e enviar comandos de bloqueio/desbloqueio. Comandos de bloqueio sempre passam por aprovação dupla (perfil + senha do Admin) e geram evento de auditoria.

---

#### Parametrização (PRM) — Core

- **FR-CORE-PRM-1.** O sistema deve oferecer tela centralizada de **Configurações** com seções: Geral, Empresa, Cobrança, Agente IA, Integrações, Módulos Verticais, Usuários, Permissões, Templates, Auditoria.
- **FR-CORE-PRM-2.** Toda configuração relevante deve ser **versionada** com histórico de quem alterou, quando e o valor anterior.

---

#### Auditoria (AUD) — Core

- **FR-CORE-AUD-1.** O sistema deve registrar em log imutável (append-only) toda operação relevante: login, criação/edição/exclusão de cadastros, baixa, estorno, conciliação, alteração de configuração, envio de mensagem, geração de PDF, exportação. Módulos verticais registram ações adicionais (ex.: Vehicle Module registra "comando ao rastreador").
- **FR-CORE-AUD-2.** O log de auditoria deve ser consultável por filtros (usuário, ação, entidade, período) e exportável.
- **FR-CORE-AUD-3.** O log deve ser **assinado** (HMAC com chave rotativa) para detectar adulteração.

---

### 2.2 Requisitos Não-Funcionais

- **NFR-1 (Desempenho).** O P95 das requisições de leitura deve ser <= 300 ms; das mutações <= 500 ms; renderização de dashboard inicial <= 1.5 s em rede 4G.
- **NFR-2 (Escalabilidade).** Arquitetura deve suportar até **10 k ativos / 50 k títulos ativos / 100 k mensagens WhatsApp/mês** sem refatoração estrutural; horizontal scaling via stateless API + workers.
- **NFR-3 (Disponibilidade).** SLA alvo de **99.5%** para o app web (aprox. 3.6h de downtime/mês). Workers e jobs em fila tolerantes a falha (retry exponencial).
- **NFR-4 (Segurança).** OWASP ASVS Nível 2 como linha base. Senhas com Argon2id. JWT com chaves rotativas (RS256). Dados pessoais (CPF, CNH) encriptados em repouso (AES-256-GCM com chave em KMS/Vault). Tudo em HTTPS (TLS 1.3). Headers de segurança (CSP, HSTS, X-Frame-Options, Permissions-Policy). Rate limiting por IP + por usuário.
- **NFR-5 (LGPD).** Tela "Meus Dados" para o cliente (export CSV + apagamento mediante regras retentivas). Consentimento explícito para uso de imagem (foto), localização (rastreador) e contato via WhatsApp. Logs de acesso a dados sensíveis (quem leu CPF de quem e quando).
- **NFR-6 (Auditabilidade Financeira).** Toda mudança de estado em título financeiro deve gerar evento imutável (event sourcing parcial). Conciliação bancária deve ser **reproduzível**: dado o extrato e os títulos do dia, o sistema chega ao mesmo estado.
- **NFR-7 (Observabilidade).** Logs estruturados JSON, métricas Prometheus, tracing OpenTelemetry. Dashboards Grafana para SRE.
- **NFR-8 (Acessibilidade).** Frontend deve atender WCAG 2.1 AA: contraste mínimo, navegação por teclado, atributos ARIA, foco visível, *prefers-reduced-motion* respeitado.
- **NFR-9 (Internacionalização).** Strings externalizadas em pt-BR; arquitetura pronta para adicionar en-US e es-ES no futuro (Angular i18n nativo).
- **NFR-10 (Plug-and-Play).** Trocar um provedor (ex.: Evolution -> Z-API) deve exigir **apenas alteração de configuração e implementação de novo adapter** — zero alteração no domínio. Adicionar um novo módulo vertical deve exigir apenas implementar `IAssetModule` — zero alteração no core.
- **NFR-11 (Mobile-First Responsivo).** UX otimizada para tablet (uso comum em campo) e mobile; uso intensivo de Tailwind responsive utilities; PWA-ready (instalável, com offline-first para tela de baixa rápida).
- **NFR-12 (Tempo Real).** Atualizações de chat (WhatsApp), comprovantes recém-chegados, e mudanças de status de títulos devem refletir na UI em <= 2 s sem refresh manual.
- **NFR-13 (Backup & DR).** Backup full diário do PostgreSQL + WAL contínuo. RPO <= 1h, RTO <= 4h. Backups testados mensalmente.
- **NFR-14 (Custo).** Stack default 100% open-source; nenhum SaaS pago obrigatório. Custos opcionais (Pluggy, OpenAI, Z-API) são habilitáveis a critério do cliente.
- **NFR-15 (Modularidade Vertical).** O core deve funcionar completamente sem nenhum módulo vertical ativo (modo "billing-only"). Cada módulo vertical pode ser habilitado/desabilitado independentemente.

---

## 3. Objetivos de Design de Interface

### 3.1 Visão Geral de UX

A interface deve transmitir a sensação de uma **ferramenta operacional premium** — o mesmo nível de polimento de produtos como Linear, Notion, Stripe Dashboard ou Vercel. O gestor passa horas no sistema; cada microinteração precisa ser fluida. Princípios:

1. **Clarity over cleverness**: dados financeiros são lidos em fração de segundo; tipografia, espaçamento e hierarquia priorizam leitura > decoração.
2. **Reactive by default**: tudo que muda no servidor reflete na UI sem refresh, via Signals + WebSocket/SSE.
3. **Progressive disclosure**: telas iniciais são limpas; complexidade aparece sob demanda (drawers, modals, popovers).
4. **Zero learning curve para Excel users**: o gestor vem do Excel — listas, filtros, edição inline, atalhos de teclado (`Ctrl+K` para command palette, `J/K` para navegar, `Enter` para abrir, `Esc` para fechar) são obrigatórios.
5. **Sophisticated where it matters**: drag-and-drop na conciliação e no construtor de parcelamento; mapas com clusters; gráficos animados; chat estilo WhatsApp pixel-perfect.
6. **Module-aware UI**: a interface adapta-se aos módulos verticais ativos — menus, dashboards, formulários e relatórios exibem apenas o que é relevante para os módulos habilitados.

### 3.2 Principais Paradigmas de Interação

- **Command Palette (Ctrl+K)**: acesso rápido a qualquer tela, busca global por cliente/ativo/título, ações rápidas ("baixar título 1234").
- **Inline Editing**: tabelas com edição direta (clique para editar célula). Validação inline.
- **Drag-and-Drop** (Angular CDK):
  - Reordenar parcelas no construtor.
  - Mover transações para títulos na conciliação.
  - Reordenar etapas de cobrança.
  - Anexar arquivos.
- **Bulk Actions**: ao selecionar N itens, aparece barra flutuante na base com ações em lote.
- **Filters as URL state**: filtros vivem na query string para serem compartilháveis e bookmarkáveis.
- **Keyboard-First**: toda ação primária tem atalho.

### 3.3 Telas Principais

Lista mínima de telas/views (não exaustiva — apenas as estruturais):

- **Login / 2FA / Recuperação de Senha**.
- **Dashboard Principal** (KPIs genéricos + widgets de módulos + alertas + atalhos rápidos).
- **Lista de Clientes** + **Ficha do Cliente** (com abas: Contratos, Títulos, Score, Documentos, Conversas, Auditoria + abas injetadas por módulos verticais).
- **Lista de Ativos** (genérica) + **Ficha do Ativo** (renderizada pelo módulo vertical ativo).
- **[Vehicle Module] Mapa da Frota**.
- **Construtor de Contrato** (wizard de 4 passos).
- **Lista de Contratos** + **Ficha de Contrato** (parcelamento, eventos, PDF).
- **Contas a Receber** (lista com filtros + ações em lote + fila de validação).
- **Contas a Pagar** (lista + recorrências + lançamento rápido).
- **Conciliação Bancária** (tela cheia split-pane).
- **Inbox de WhatsApp** (3 painéis: conversas / chat / contexto).
- **Configurações** (seções: Geral, Empresa, Cobrança, Agente IA, Integrações, Módulos, Usuários, Permissões, Templates, Auditoria).
- **Relatórios & Construtor** + **Visualizador**.
- **Auditoria** (log searchable).
- **Perfil & Preferências** (tema, notificações, atalhos).

### 3.4 Acessibilidade

- WCAG 2.1 AA estrita (contraste 4.5:1, foco visível, ARIA correto).
- *Skip links*, navegação por teclado completa, leitor de tela testado em NVDA + VoiceOver.
- *Reduced motion* respeitado (prefere `transform: none` em quem ativa).

### 3.5 Branding e Estilo Visual

- **Stack visual**: Tailwind CSS v4 + design tokens estilo shadcn/ui + Heroicons.
- **Tema**: Light / Dark sincronizado com OS, persistido em `theme.service.ts`. Variáveis CSS globais em `styles.css`:
  - `--surface`, `--surface-elevated`, `--surface-overlay`
  - `--text-primary`, `--text-secondary`, `--text-muted`
  - `--border`, `--border-subtle`
  - `--accent`, `--accent-hover`, `--accent-foreground`
  - `--success`, `--warning`, `--danger`, `--info`
- **Estética**: superfícies elevadas com glassmorphism sutil (backdrop-blur leve em modais/menus), bordas `rounded-xl` / `rounded-2xl`, sombras suaves, gradientes muito sutis em botões primários.
- **Tipografia**: Inter (UI) + JetBrains Mono (números financeiros e códigos). Tabular-nums obrigatório em colunas de valor.
- **Cores**: paleta neutra-fria como base; accent vibrante (sugestão: índigo/violeta `#6366F1` ou verde-financeiro `#10B981`) — definido em fase de design.
- **Iconografia**: Heroicons exclusivamente, via `@ng-icons/core` + `@ng-icons/heroicons`. Nenhum SVG inline solto.
- **Branding**: o nome do produto (`{{product_name}}`) é configurável via variável de ambiente e exibido no header, login, favicon e manifest. Nenhum nome hardcoded no código.

### 3.6 Dispositivos e Plataformas Alvo

- **Web Responsive** (desktop > tablet > mobile, nessa ordem de prioridade).
- **PWA**: instalável, splash screen, ícones, offline shell (cobrança offline com fila de sync futura).
- **Não há app nativo** no MVP. A PWA cobre o caso mobile.

---

## 4. Premissas Técnicas

### 4.1 Estrutura do Repositório

**Monorepo** com Nx ou Turborepo opcional, mas como início simples: **dois diretórios paralelos** (`frontend/` Angular e `api/` FastAPI) gerenciados juntos sob um diretório guarda-chuva com `docker-compose.yml` para dev local. Nenhum nome de produto em nomes de pasta ou pacotes.

```
project-root/
  api/               # Backend FastAPI
  frontend/          # Frontend Angular
  docker-compose.yml
  .github/
  docs/
```

> Justificativa: a estrutura Angular do cliente já é muito específica (arquivos anexados); um monorepo Nx adiciona complexidade desnecessária no MVP. Pode-se migrar depois. O nome do produto é injetado via variável de ambiente `PRODUCT_NAME`, nunca hardcoded.

### 4.2 Arquitetura de Serviços

**API monolítica modular** (não microsserviços). FastAPI organizado em módulos por *bounded context*:
- **Core modules**: auth, customers, contracts, finance (receivables + payables), collections, reconciliation, integrations, reports, audit, assets.
- **Vertical modules**: vehicles (primeiro), com pasta isolada `backend-api/app/modules/vehicles/` que implementa `IAssetModule`.

Workers Celery rodam em processos separados para tarefas assíncronas (cobranças agendadas, parsing de PDF, OCR, jobs de módulo vertical, geração de relatórios pesados).

**Asset Abstraction Layer**: o core publica Domain Events em um event bus interno. Módulos verticais registram listeners no startup. O core nunca importa código de módulo — apenas consome a interface `IAssetModule` via dependency injection.

**Comunicação Frontend <-> Backend**:

- **REST** (CRUD geral) — JSON, OpenAPI 3.1 gerado automaticamente.
- **WebSocket** (`/ws/chat`) — chat WhatsApp bidirecional em tempo real.
- **Server-Sent Events (`/sse/notifications`)** — atualizações de status de títulos, comprovantes recebidos, conciliação concluída, alertas. Mais simples que WebSocket para o caso unidirecional.
- **Polling de fallback** apenas se SSE falhar (degraded mode).

> **Decisão**: SSE como primário para notificações (unidirecional, leve, reconexão automática nativa); WebSocket somente para chat (bidirecional, baixa latência); polling somente como fallback explícito.

### 4.3 Requisitos de Testes

- **Backend**: unit tests com pytest (cobertura >= 80% no domínio); integration tests com testcontainers (Postgres real); contract tests com schemathesis sobre o OpenAPI.
- **Frontend**: unit tests com Vitest + @ngneat/spectator; component tests com Storybook + Chromatic (visual regression); E2E com Playwright cobrindo os 5 fluxos críticos.
- **CI**: GitHub Actions executando lint + test + build em cada PR; bloqueio de merge sem testes verdes.

### 4.4 Premissas Técnicas Adicionais

- **Banco**: PostgreSQL 16+ (com `pgvector` para RAG do agente de cobrança).
- **Cache & Queue**: Redis 7.
- **Object Storage**: MinIO (self-hosted, S3-compatible) — comprovantes, contratos PDF, fotos.
- **Auth**: JWT com biblioteca `python-jose`; refresh em cookie HttpOnly.
- **ORM**: SQLAlchemy 2 + Alembic.
- **DTOs**: Pydantic v2.
- **Workers**: Celery + Redis (alternativa Dramatiq registrada no ARCHITECTURE).
- **AI/LLM**: SDK abstrato (`pydantic-ai` ou `LiteLLM` ou camada própria) sobre OpenAI/Anthropic/Gemini/Ollama.
- **Rendering PDF**: WeasyPrint (server-side) com templates Jinja2.
- **OCR**: `pytesseract` (default) com pré-processamento OpenCV; opção LLM Vision como fallback.
- **Mapas**: Leaflet (default OSM) com `@asymmetrik/ngx-leaflet`; alternativa Google Maps. (Usado pelo Vehicle Module; outros módulos podem usar se aplicável.)
- **PIX BR Code**: biblioteca `pix-utils` (Python).
- **Frontend**: Angular 21+ standalone, signals e resources (NÃO ngrx; estado é local-first com signal services em `/core` quando preciso).
- **Validators**: brazilian-values libs ou validators próprios para CPF/CNPJ/CEP/placa.
- **Linting**: Ruff + Black (Python); ESLint + Prettier + stylelint (Angular).
- **Pre-commit hooks**: lint + format + secret scan.
- **Containerização**: Docker para tudo; `docker-compose` para dev; Dockerfile multi-stage para produção.
- **Deploy**: Coolify ou Dokploy ou Kubernetes (a definir com ops); inicialmente VPS único com docker-compose para o cliente.
- **Product Name**: injetado via `PRODUCT_NAME` env var, usado em título da página, header, login, manifest, e-mails. Nunca hardcoded.

---

## 5. Lista de Épicos

> A divisão em épicos segue a regra BMAD: **cada épico entrega valor utilizável de ponta-a-ponta**, na menor granularidade possível. A primeira história do Épico 1 sempre estabelece a fundação técnica (login + endpoint de saúde + UI base navegável).

| #  | Épico                                                | Tipo          | Descrição em 1 linha                                                                                       |
|----|------------------------------------------------------|---------------|------------------------------------------------------------------------------------------------------------|
| 1  | **Foundation & Identity**                            | Core          | Setup do projeto, autenticação, layout base, design system, Asset Abstraction Layer e pipeline CI/CD.       |
| 2A | **Core Asset Management & Cadastros**                | Core          | Cadastro genérico de clientes e ativos, tabela `assets`, event bus, interface `IAssetModule`.                |
| 2B | **Vehicle Module: Cadastros & Integrações**          | Vehicle Module | Cadastro de veículos, integração FIPE, rastreador GPS, mapa da frota, hooks de domínio.                     |
| 3  | **Contratos & Parcelamento Flexível**                | Core          | Construtor visual, geração de PDF, geração automática de títulos, edição em lote, reemissão.                |
| 4  | **Contas a Receber, Pagamento Parcial & Validação**  | Core          | Títulos a receber, baixa manual/parcial, fila de comprovantes, OCR, QR Code Pix, fluxo padrão sem gateway. |
| 5  | **Contas a Pagar & Recorrências**                    | Core          | Despesas avulsas e recorrentes, "Lançar e Pagar", DRE.                                                      |
| 6  | **Agent Orchestrator, Messaging & Inbox**            | Core + Hooks  | Agent Orchestrator multi-canal (WhatsApp + chat in-app), transcrição de áudio, tools com RBAC, cobrança como caso de uso primário.        |
| 7  | **Conciliação Bancária Sofisticada**                 | Core          | Importação OFX/PDF, Open Finance opcional, drag-and-drop, auto-match.                                       |
| 8  | **Dashboards, Relatórios & Patrimônio**              | Core + Hooks  | KPIs genéricos, dashboards por cliente, widgets de módulo vertical, relatórios exportáveis.                  |
| 9  | **Hardening & Plug-and-Play Final**                  | Core          | Auditoria completa, painel de integrações, testes de carga, polimento, documentação de adapters e módulos.  |

---

## 6. Detalhamento dos Épicos

> **Convenção:** cada história tem `ID`, `Como [perfil] / quero [ação] / para que [valor]`, e **Acceptance Criteria** numerados. Histórias devem ser executáveis em <= 1 dia por um agente Dev BMAD em sessão única (ou seja, "AI agent-sized").

---

### Épico 1 — Fundação e Identidade (Core)

**Objetivo do épico:** ter o esqueleto técnico do produto rodando em dev e produção, com login funcional, layout base navegável, tema dark/light, Asset Abstraction Layer (interface `IAssetModule` + event bus) e CI/CD verde — sem nenhuma funcionalidade de domínio ainda. Ao final do épico, qualquer dev consegue clonar, subir o ambiente e ver a tela "Olá, X" autenticado.

**Premissas do épico:**

- Repositórios criados (`api/`, `frontend/`).
- Docker Compose com Postgres, Redis e MinIO para dev local.
- GitHub Actions com workflow de CI básico.

#### Story 1.1 — Bootstrap do Backend FastAPI

**Como** Desenvolvedor, **quero** o esqueleto FastAPI configurado com Postgres, Alembic, Pydantic v2 e estrutura modular, **para que** futuras features tenham base sólida e padronizada.

**Acceptance Criteria:**

1. Diretório `api/` com Python 3.12+, gerenciado por `uv` ou `poetry`.
2. Estrutura de diretórios alinhada à arquitetura definida: `app/{api,core,domain,infrastructure,modules,workers,tests}` + `alembic/`. A pasta `modules/` conterá módulos verticais (inicialmente vazia, com `__init__.py`).
3. Endpoint `GET /health` retornando `{"status":"ok","db":"ok","redis":"ok","storage":"ok"}` com checagem real de cada dependência.
4. Alembic configurado com primeira migração vazia.
5. Configurações via Pydantic Settings com `.env` (dev) e variáveis de ambiente (prod). Secrets nunca commitados. `PRODUCT_NAME` como variável de configuração.
6. Logs estruturados JSON (`structlog`) saindo no stdout.
7. CORS configurado para o frontend em dev (`http://localhost:4200`).
8. OpenAPI disponível em `/docs` (Swagger) e `/redoc`.
9. Dockerfile multi-stage (build -> runtime) gerando imagem <= 250 MB.
10. `docker-compose.yml` sobe API + Postgres + Redis + MinIO em <= 30s na máquina dev.

#### Story 1.2 — Bootstrap do Frontend Angular 21

**Como** Desenvolvedor, **quero** o esqueleto Angular 21 standalone configurado com Tailwind v4, Heroicons e estrutura de pastas conforme manifesto, **para que** features sejam construídas com padrão consistente.

**Acceptance Criteria:**

1. Projeto Angular 21+ standalone gerado em `frontend/`, sem NgModules.
2. Estrutura `src/app/` exatamente como definido em `angular-structure.md` (core, shared, features). Nenhuma pasta `assets/` em src — `public/` na raiz.
3. Tailwind CSS v4 instalado e configurado com `tailwind.config` mínimo, plugins de tipografia e forms.
4. `styles.css` com import Tailwind e bloco `@theme` com **todas** as variáveis CSS listadas em 3.5 (light + dark).
5. `theme.service.ts` em `core/services/` com signal `theme()` e métodos `setTheme('light'|'dark'|'system')`, persistindo em localStorage.
6. `@ng-icons/core` + `@ng-icons/heroicons` instalados; componente `<ui-icon name="HeroXMark" />` reutilizável em `shared/components/icon/`.
7. Layout shell `AppShellComponent` em `shared/components/app-shell/` com sidebar colapsável, header com toggle de tema e nome do produto (via `environment.productName`), área de conteúdo com `<router-outlet>`.
8. Rotas: `/login`, `/dashboard` (placeholder), `/404` (NotFound).
9. ESLint + Prettier + stylelint configurados; `npm run lint` passa.
10. `index.html` com meta-tags PWA básicas (manifest.webmanifest com placeholder — `name` preenchido via build config, não hardcoded).

#### Story 1.3 — Modelo de Usuário e Migração Inicial

**Como** Desenvolvedor, **quero** as tabelas `users`, `roles`, `permissions`, `user_roles` e `audit_log` criadas no banco, **para que** o sistema de identidade tenha persistência.

**Acceptance Criteria:**

1. Modelos SQLAlchemy criados em `app/domain/identity/models.py` com tipos corretos (UUID PK, timestamps, soft-delete via coluna `deleted_at`).
2. Migration Alembic gerada e aplicada com `alembic upgrade head`.
3. Tabela `users` tem: `id`, `email` (unique), `password_hash`, `full_name`, `is_active`, `is_mfa_enabled`, `mfa_secret` (encriptado), `created_at`, `updated_at`, `deleted_at`.
4. Tabela `audit_log` tem: `id`, `user_id`, `action`, `entity`, `entity_id`, `payload_before`, `payload_after`, `ip`, `user_agent`, `signature_hmac`, `created_at`.
5. Seeds: 1 usuário Admin (`admin@app.local`, senha `Admin@123` para dev) inserido via comando `python -m app.cli seed`.
6. Index criado em `users.email` (unique), `audit_log.user_id`, `audit_log.created_at`.

#### Story 1.4 — Endpoint de Login com JWT

**Como** Usuário Admin, **quero** logar com e-mail/senha e receber tokens JWT, **para que** eu possa acessar recursos protegidos.

**Acceptance Criteria:**

1. `POST /api/v1/auth/login` recebe `{email, password}`, valida credenciais, retorna `{access_token, refresh_token, user}`.
2. Senha verificada com Argon2id; falha em <= 200 ms para evitar enumeration; resposta genérica `401 Unauthorized` em erro.
3. Access token JWT (RS256) com claims: `sub`, `email`, `roles`, `exp` (15 min), `iat`, `iss`, `aud`.
4. Refresh token retornado em cookie `HttpOnly Secure SameSite=Lax`, válido 7 dias, com rotação a cada uso.
5. `POST /api/v1/auth/refresh` consome refresh token (do cookie), invalida o anterior, emite novo par.
6. `POST /api/v1/auth/logout` invalida o refresh token (lista de revogação em Redis).
7. 5 tentativas falhadas em 15 min para um email -> `429 Too Many Requests` por 15 min.
8. Eventos de login (sucesso e falha) gravados em `audit_log`.
9. Testes unitários cobrindo: sucesso, senha errada, usuário inativo, MFA ativo, rate limit.

#### Story 1.5 — Tela de Login no Frontend

**Como** Usuário, **quero** uma tela de login bonita e funcional, **para que** eu acesse o sistema com segurança.

**Acceptance Criteria:**

1. Componente `LoginComponent` em `features/auth/login/` com 3 arquivos (TS/HTML/CSS, este último praticamente vazio).
2. Form com Reactive Forms tipados: campos email (validador required + email) e senha (required, min 8).
3. Botão "Entrar" desabilitado enquanto inválido; spinner inline ao submeter.
4. Erros de servidor exibidos em alerta toast (componente shared `<ui-toast>`); 401 -> "Credenciais inválidas".
5. Sucesso -> armazena access token em memória (signal `authState()` no `AuthService` core), navega para `/dashboard`.
6. Estilização premium: card central com glassmorphism sutil, logo/nome do produto (via `environment.productName`) no topo, fundo gradient muito suave no theme atual, ilustração lateral em desktop.
7. Atalho `Enter` submete; foco inicial em email; foco visível em todos os campos.
8. Link "Esqueci minha senha" (rota placeholder `/auth/forgot-password`).
9. E2E Playwright: login com sucesso navega para `/dashboard`; falha mantém na página com toast.

#### Story 1.6 — AuthGuard, JWT Interceptor e Refresh Automático

**Como** Sistema, **quero** que rotas protegidas exijam autenticação e tokens sejam renovados sem ação do usuário, **para que** a UX seja contínua.

**Acceptance Criteria:**

1. `auth.guard.ts` em `core/guards/` bloqueia rotas autenticadas se `authState().isAuthenticated() === false`, redirecionando para `/login?redirect=...`.
2. `jwt.interceptor.ts` em `core/interceptors/` injeta header `Authorization: Bearer <token>` em todas as chamadas para `${API_URL}/`.
3. Em resposta `401`, interceptor tenta `POST /auth/refresh` uma única vez; se sucesso, repete a request original; se falhar, limpa estado e redireciona para login.
4. Concurrent 401s não disparam múltiplos refreshes (lock com `Promise` ou `BehaviorSubject` em `AuthService`).
5. Em logout (manual ou forçado), limpa estado, cookie e navega para login.

#### Story 1.7 — CI/CD Inicial

**Como** Time, **quero** pipeline de CI verificando lint, type-check, testes e build a cada PR, **para que** regressões sejam pegas cedo.

**Acceptance Criteria:**

1. Workflow `.github/workflows/api-ci.yml` executa em PRs tocando o backend: ruff, mypy strict, pytest com cobertura, build de imagem Docker.
2. Workflow `.github/workflows/web-ci.yml` executa em PRs tocando o frontend: eslint, ng build --configuration=production, vitest.
3. Branch `main` protegida: PR obrigatório, 1 review, todos os checks verdes.
4. Cobertura mínima: 70% no backend; medida via Codecov ou similar.
5. Tempo total do CI <= 10 min para o conjunto.

#### Story 1.8 — Asset Abstraction Layer: Interface e Event Bus

**Como** Desenvolvedor, **quero** a interface `IAssetModule` definida e o event bus interno implementado, **para que** módulos verticais possam ser plugados sem alterar o core.

**Acceptance Criteria:**

1. Interface `IAssetModule` (Protocol) definida em `app/core/assets/module_interface.py` conforme FR-CORE-AST-1.
2. Event bus síncrono in-process implementado em `app/core/events/event_bus.py` com métodos `publish(event)`, `subscribe(event_type, handler)`, `unsubscribe(event_type, handler)`.
3. Domain Events definidos em `app/core/events/domain_events.py`: `ContractCreatedEvent`, `ContractTerminatedEvent`, `InstallmentOverdueEvent`, `InstallmentPaidEvent`, `ReconciliationCompletedEvent`, `CustomerScoreChangedEvent`, `PaymentPartiallyReceivedEvent`.
4. Module registry em `app/core/assets/registry.py`: `register_module(module: IAssetModule)`, `get_module(module_id: str)`, `list_modules()`, `is_module_active(module_id: str)`.
5. Tabela `assets` migrada conforme FR-CORE-AST-3.
6. Tabela `active_modules` com `module_id`, `is_active`, `config` (JSONB), `registered_at`.
7. Testes unitários: registrar módulo mock, publicar evento, verificar que handler foi chamado.

---

### Épico 2A — Gestão Core de Ativos e Cadastros (Core)

**Objetivo:** o gestor consegue cadastrar clientes e ter a infraestrutura genérica de ativos pronta. O core gerencia clientes e delega detalhes de ativos aos módulos verticais via `IAssetModule`.

#### Story 2A.1 — Modelo & API de Clientes (CRUD)

**Como** Backend, **quero** entidade Cliente com endpoints REST completos, **para que** o frontend possa gerenciar a base.

**Acceptance Criteria:**

1. Modelo `Customer` com campos genéricos: nome completo, CPF/CNPJ (com validação), telefone (E.164), e-mail, endereço completo, data de nascimento, foto, observações, `score` (default 100), `status` (`ativo`/`inativo`/`bloqueado`), `tags` (JSONB), `metadata_extensions` (JSONB — campos adicionais injetados por módulos verticais), `created_by_user_id`.
2. CPF/CNPJ validado e único; e-mail único; telefone normalizado E.164.
3. Endpoints:
   - `POST /api/v1/customers` (cria — Admin/Operador)
   - `GET /api/v1/customers?search=&status=&page=&size=` (lista paginada com busca textual no nome/CPF/telefone)
   - `GET /api/v1/customers/{id}` (detalhe)
   - `PATCH /api/v1/customers/{id}` (atualiza parcial)
   - `DELETE /api/v1/customers/{id}` (soft delete — Admin)
   - `POST /api/v1/customers/{id}/attachments` (upload, Admin/Operador)
4. Anexos armazenados no MinIO sob `customers/{id}/{uuid}-{filename}`; gravado registro em `customer_attachments`.
5. Toda mutação gera evento em `audit_log`.
6. Testes integration cobrindo CRUD e upload.

#### Story 2A.2 — Tela Lista de Clientes

**Como** Gestor, **quero** ver todos os clientes em tabela com busca e filtros, **para que** eu encontre rapidamente quem procuro.

**Acceptance Criteria:**

1. Componente `CustomersListComponent` em `features/system/customers/`.
2. Tabela com colunas: avatar, nome, CPF/CNPJ (mascarado nos últimos 3), telefone (com botão WhatsApp), score (badge colorido), status (badge), última atualização, ações (ver, editar, excluir).
3. Busca textual com debounce 300ms (signal-based).
4. Filtros: status, tag, score (range slider).
5. URL state: filtros refletidos em query string.
6. Paginação server-side (signal `currentPage`, `pageSize`); preferencialmente com `resource()` API do Angular 21.
7. Botão "Novo Cliente" abre drawer com form (componente irmão `CustomerFormComponent`).
8. Skeleton loader enquanto carrega; estado vazio com ilustração e CTA.
9. Atalhos: `/` foca busca, `n` abre novo cliente, `up/down` navega linhas, `Enter` abre detalhe.

#### Story 2A.3 — Drawer / Modal de Cadastro de Cliente

**Como** Gestor, **quero** formulário ergonômico para cadastrar cliente, **para que** o processo seja rápido.

**Acceptance Criteria:**

1. Form em 3 seções colapsáveis: Dados Pessoais, Documentos, Contato & Endereço. Módulos verticais podem injetar seções adicionais (ex.: Vehicle Module injeta seção "CNH").
2. Validação inline (Reactive Forms tipados).
3. CEP busca via ViaCEP e auto-preenche endereço.
4. Foto do cliente: drop-zone com crop circular preview.
5. Anexos: drop-zone múltiplo (documentos gerais) com preview.
6. Salvar fecha drawer e atualiza lista; erro mostra toast e mantém form.
7. Acessível: tab order correto, foco move para primeiro campo, ESC fecha (com confirmação se houver alterações).

#### Story 2A.4 — Ficha do Cliente (Tabs)

**Como** Gestor, **quero** ver toda a vida do cliente em uma página, **para que** eu tenha contexto completo antes de decisões.

**Acceptance Criteria:**

1. Rota `/system/customers/:id` carrega `CustomerDetailComponent`.
2. Header com avatar, nome, CPF/CNPJ, score grande visualmente, status, ações primárias (Editar, Mensagem WhatsApp).
3. Abas core: **Visão Geral**, **Contratos**, **Títulos**, **Score**, **Documentos**, **Conversas**, **Auditoria**. Módulos verticais podem injetar abas adicionais. Cada aba é lazy-loaded.
4. Visão Geral: cards com métricas (total contratado, total recebido, em aberto, próximos vencimentos), timeline de eventos.
5. URL preserva aba ativa via query string (`?tab=titulos`).

#### Story 2A.5 — Lista Genérica de Ativos

**Como** Gestor, **quero** ver todos os ativos cadastrados na plataforma, **para que** eu tenha visão consolidada.

**Acceptance Criteria:**

1. Tela `/system/assets` lista registros da tabela `assets` com colunas: nome, módulo (badge), status, última atualização, ações.
2. Filtros: módulo vertical (multi-select), status, busca textual.
3. Clique em ativo redireciona para a ficha detalhada renderizada pelo módulo vertical correspondente.
4. Se nenhum módulo vertical está ativo, exibe estado vazio com mensagem "Ative um módulo vertical em Configurações > Módulos para começar a cadastrar ativos."

---

### Épico 2B — Módulo de Veículos: Cadastros e Integrações

**Objetivo:** o módulo Vehicle está implementado e registrado como `IAssetModule`. O gestor consegue cadastrar veículos, ver a frota em um mapa em tempo real, e o sistema atualiza automaticamente o valor patrimonial via FIPE. Ao final do épico, o Excel de cadastros de veículos é substituível.

#### Story 2B.1 — Estrutura do Vehicle Module e Registro como IAssetModule

**Como** Desenvolvedor, **quero** o Vehicle Module estruturado e registrado no core, **para que** ele receba domain events e injete funcionalidades.

**Acceptance Criteria:**

1. Pasta `backend-api/app/modules/vehicles/` com estrutura: `__init__.py`, `module.py` (implementação de `IAssetModule`), `models.py`, `routes.py`, `services.py`, `hooks.py`.
2. Classe `VehicleModule(IAssetModule)` implementa todos os métodos da interface: `on_contract_created`, `on_installment_overdue`, etc.
3. Module registrado no startup via `register_module(VehicleModule())`.
4. Entry na tabela `active_modules` com `module_id='vehicles'`, `is_active=True`.
5. Testes: publicar `InstallmentOverdueEvent` -> Vehicle Module hook é chamado.

#### Story 2B.2 — Adapter de FIPE (Interface + Implementação)

**Como** Sistema, **quero** abstração `IFipeProvider` com implementação default, **para que** trocar provedor seja trivial.

**Acceptance Criteria:**

1. Interface (Protocol) `IFipeProvider` em `app/modules/vehicles/ports/fipe.py`:
   ```python
   class IFipeProvider(Protocol):
       async def list_brands(self, vehicle_type: Literal['car','motorcycle','truck']) -> list[FipeBrand]: ...
       async def list_models(self, vehicle_type, brand_code: str) -> list[FipeModel]: ...
       async def list_years(self, vehicle_type, brand_code, model_code) -> list[FipeYearOption]: ...
       async def get_price(self, vehicle_type, brand_code, model_code, year_code) -> FipePriceResult: ...
   ```
2. Adapter `ApiFipeBrAdapter` em `app/modules/vehicles/adapters/fipe/apifipe_br.py` consumindo `apifipe.com.br`.
3. Adapter `FipeApiBrAdapter` (alternativo) consumindo `fipeapi.com.br`.
4. Adapter de fallback que tenta o primário e cai para o secundário em erro.
5. Cache Redis com TTL de 30 dias por chave `fipe:{type}:{brand}:{model}:{year}`.
6. Endpoint: `GET /api/v1/modules/vehicles/fipe/brands?type=car`, etc.
7. Configuração de qual adapter usar via env `FIPE_PROVIDER=apifipe_br|fipeapi_br|fallback`.

#### Story 2B.3 — Modelo & API de Veículos com FIPE

**Como** Backend, **quero** entidade Vehicle e endpoints CRUD com integração FIPE, **para que** o frontend possa cadastrar veículos.

**Acceptance Criteria:**

1. Modelo `Vehicle` com todos os campos de FR-VH-1, mais relacionamentos: `asset_id` (FK para `assets`), `current_contract_id` (nullable), `current_customer_id` (nullable, derivado).
2. CRUD endpoints sob `/api/v1/modules/vehicles/`.
3. Ao criar/atualizar veículo, sincroniza registro na tabela `assets` do core (cria ou atualiza `asset_id`).
4. Endpoint `POST /api/v1/modules/vehicles/{id}/refresh-fipe` força atualização do `valor_fipe_atual` via adapter.
5. Job Celery agendado (cron `0 3 5 * *` — dia 5 às 3am) atualiza FIPE de todos os veículos ativos.
6. Modelo `VehicleAcquisition` 1:1 com Vehicle, contendo a forma de aquisição (FR-VH-3): `type` (`a_vista`/`financiamento`/`consorcio`/`custom`), `down_payment`, `installments` (JSONB com lista), `interest_rate`, `amortization_system` (`price`/`sac`).
7. Cálculos derivados expostos em `GET /api/v1/modules/vehicles/{id}/financials`: valor patrimonial, depreciação, total pago aquisição, saldo aquisição, total recebido, ROI %, payback projetado.

#### Story 2B.4 — Tela de Cadastro de Veículo (Wizard)

**Como** Gestor, **quero** wizard guiado para cadastrar veículo, **para que** o processo seja claro mesmo com muitos campos.

**Acceptance Criteria:**

1. 4 passos: **Identificação** (placa, renavam, chassi, cor), **Dados FIPE** (selects encadeados marca -> modelo -> ano com valor preenchido), **Aquisição** (data, valor de compra, forma de pagamento — sub-form dinâmico conforme tipo), **Documentos & Foto** (seguro, IPVA, fotos).
2. Selects FIPE com search/typeahead; loading inline.
3. Formulário dinâmico: ao escolher "Financiamento", aparece sub-form com entrada, qtd parcelas, valor parcela ou taxa de juros + sistema de amortização (Price/SAC), com preview da tabela.
4. Botão "Voltar"/"Próximo" + indicador de progresso (stepper).
5. Salvar no último passo; preview final antes de confirmar.

#### Story 2B.5 — Lista e Cards de Veículos

**Como** Gestor, **quero** visão da frota em tabela ou em grade de cards, **para que** eu acompanhe o estado.

**Acceptance Criteria:**

1. Toggle Tabela <-> Cards.
2. Cards mostram foto, modelo, placa, status (badge), cliente atual, ROI %, próximo vencimento, mini-mapa com posição.
3. Filtros: status, marca, ano, cliente atual, tag.
4. KPI no topo: Frota Total (R$ FIPE somado), Veículos Ativos, Veículos Parados.

#### Story 2B.6 — Adapter de Rastreador GPS

**Como** Sistema, **quero** abstração `ITrackerGateway` com implementação genérica, **para que** rastreamento seja plug-and-play.

**Acceptance Criteria:**

1. Interface:
   ```python
   class ITrackerGateway(Protocol):
       async def get_position(self, device_id: str) -> Position: ...
       async def get_positions(self, device_ids: list[str]) -> dict[str, Position]: ...
       async def block_vehicle(self, device_id: str, reason: str) -> CommandResult: ...
       async def unblock_vehicle(self, device_id: str, reason: str) -> CommandResult: ...
       async def get_history(self, device_id, start, end) -> list[Position]: ...
   ```
2. Adapter `GenericRestTrackerAdapter` configurável (URL, auth header, mapping JSON-path) — funciona para a maioria dos rastreadores REST sem código novo.
3. Adapter `Mqtt+RestTrackerAdapter` para rastreadores que recebem comandos via MQTT mas devolvem posição via REST.
4. Comandos de bloqueio/desbloqueio sempre passam por aprovação dupla (perfil + senha do Admin) e geram evento de auditoria.

#### Story 2B.7 — Mapa Interativo da Frota (Vehicle Module)

**Como** Gestor, **quero** ver todos os veículos em um mapa, **para que** eu acompanhe a operação geograficamente.

**Acceptance Criteria:**

1. Componente `FleetMapComponent` em `features/modules/vehicles/fleet-map/`.
2. Leaflet com OSM, marcadores customizados (ícone do tipo do veículo + cor pelo status).
3. Cluster automático em zoom-out.
4. Popup ao clicar: foto miniatura, modelo, placa, cliente, status, botão "Ver detalhes" e "Bloquear" (com confirmação dupla).
5. Atualização das posições a cada 30s via SSE (`/sse/modules/vehicles/tracker`).
6. Filtros laterais: por status, por cliente, por tag.
7. Polígono opcional de "região da operação" para destacar veículos fora da zona.

#### Story 2B.8 — Hook de Inadimplência: Bloqueio GPS (Vehicle Module)

**Como** Vehicle Module, **quero** reagir a `InstallmentOverdueEvent` verificando política de bloqueio, **para que** veículos sejam bloqueados automaticamente quando configurado.

**Acceptance Criteria:**

1. Hook `on_installment_overdue` no `VehicleModule` consulta política parametrizada: `dias_atraso >= X` AND `score < Y`.
2. Se condições atendidas E política exige aprovação humana -> cria notificação para Admin com ação "Aprovar Bloqueio" / "Rejeitar".
3. Se condições atendidas E aprovação automática habilitada -> dispara `block_vehicle` via `ITrackerGateway`.
4. Evento `vehicle_blocked` gravado em `audit_log` com motivo, título associado, score do cliente.
5. Ao registrar pagamento (evento `InstallmentPaidEvent`), hook verifica se veículo está bloqueado e, se todos os títulos vencidos foram quitados, dispara `unblock_vehicle` automaticamente.

---

### Épico 3 — Contratos & Parcelamento Flexível (Core)

**Objetivo:** o gestor consegue gerar qualquer contrato imaginável (entrada + N parcelas + extras + carência + custom), vinculado a um ativo genérico (`asset_id`), com geração automática de PDF e títulos vinculados, suportando edição em lote dos abertos sem nunca tocar nos baixados. Alterações contratuais reemitem títulos em aberto.

#### Story 3.1 — Modelo de Domínio: Contract, Installment, ContractEvent

**Como** Backend, **quero** o domínio de contratos modelado, **para que** as regras financeiras tenham fundação correta.

**Acceptance Criteria:**

1. Tabela `contracts`: id, customer_id, asset_id (FK para `assets`), status (`rascunho`/`vigente`/`encerrado`/`rescindido`), start_date, end_date, total_amount, periodicity, due_day, late_interest_pct_per_day, late_fine_pct, grace_days, has_purchase_option (bool), residual_value, terms_md (markdown), pdf_url, version (int), created_by, signed_at.
2. Tabela `installments`: id, contract_id, sequence, due_date, amount, status (`em_aberto`/`vencido`/`pago_aguardando_verificacao`/`pago`/`renegociado`/`cancelado`), kind (`regular`/`down_payment`/`extra_semestral`/`extra_anual`/`custom`), paid_at, paid_amount, payment_method, receipt_url, observation, parent_installment_id (nullable — referência ao título original em caso de baixa parcial).
3. Tabela `contract_events` (event sourcing parcial): id, contract_id, event_type, payload (JSONB), created_by_user_id, created_at. Tipos: `created`, `signed`, `installments_generated`, `installments_reissued`, `bulk_edit`, `cancellation_requested`, `terminated`, `pdf_generated`.
4. Constraint: `installment.status='pago'` é imutável (trigger PG ou check em domain layer).
5. Index: `installments(contract_id)`, `installments(due_date, status)`.
6. Ao finalizar contrato (status -> `vigente`), publica `ContractCreatedEvent` no event bus.

#### Story 3.2 — Construtor Visual de Parcelamento (Backend)

**Como** Backend, **quero** endpoint que aceita uma "definição de parcelamento" e devolve lista preview de parcelas, **para que** frontend mostre antes de salvar.

**Acceptance Criteria:**

1. `POST /api/v1/contracts/preview-schedule` aceita:
   ```json
   {
     "start_date": "2026-06-01",
     "down_payment": {"amount": 1000, "date": "2026-06-01"},
     "regular": {"count": 36, "amount": 350, "periodicity": "weekly", "first_due_date": "2026-06-08", "due_day": 8},
     "extras": [
       {"kind": "anual", "amount": 1500, "first_date": "2026-12-15", "count": 3}
     ],
     "grace_days": 7,
     "custom_overrides": [
       {"sequence": 5, "due_date": "2026-08-01", "amount": 0, "note": "Carência adicional"}
     ]
   }
   ```
2. Retorna lista ordenada de parcelas calculadas com `sequence`, `due_date`, `amount`, `kind`.
3. Soma confere com total esperado (validação de coerência).
4. Suporta `custom_only` (lista totalmente livre).
5. Endpoint `POST /api/v1/contracts/` aceita o mesmo payload + dados do contrato e persiste tudo atomicamente. Ao salvar com status `vigente`, gera títulos e publica `ContractCreatedEvent`.

#### Story 3.3 — Construtor Visual de Parcelamento (Frontend)

**Como** Gestor, **quero** UI visual para montar o parcelamento, **para que** eu veja todas as parcelas antes de confirmar.

**Acceptance Criteria:**

1. Componente `ScheduleBuilderComponent` em `features/system/contracts/components/schedule-builder/`.
2. Painel esquerdo: configurador (entrada toggle, parcelas regulares — qtd/valor/periodicidade, extras adicionáveis, carência).
3. Painel direito: tabela de preview, atualizada reativamente (signal `previewSchedule = resource(...)` chamando o endpoint de preview com debounce).
4. Tabela suporta drag-and-drop (CDK Drag-Drop) para reordenar parcelas custom.
5. Edição inline: clicar em valor abre input; data abre datepicker; observação livre.
6. Botão "Adicionar parcela manual" insere linha; "Remover" deleta.
7. Resumo no rodapé: Total parcelado, Total geral, Qtd parcelas, Última data, Período total.
8. Modo "Custom Schedule" (toggle) limpa configurador e habilita só edição manual.

#### Story 3.4 — Wizard Completo de Criação de Contrato

**Como** Gestor, **quero** wizard guiado para criar contrato, **para que** dados venham organizados.

**Acceptance Criteria:**

1. 4 passos: **Cliente & Ativo** (selects com busca — ativo filtrado por módulo vertical ativo e status `disponivel`), **Termos** (datas, juros/multa, opção de compra), **Parcelamento** (Story 3.3), **Cláusulas & Revisão** (texto rico Tiptap, preview do PDF).
2. Validações cruzadas: cliente ativo, ativo disponível, datas coerentes.
3. Salvar como Rascunho a qualquer momento (`status='rascunho'`).
4. Confirmar gera contrato `vigente`, dispara geração de PDF, gera títulos e publica `ContractCreatedEvent` atomicamente.
5. Toast de sucesso com link "Ver Contrato".

#### Story 3.5 — Geração de PDF do Contrato

**Como** Sistema, **quero** gerar PDF do contrato com template profissional, **para que** o gestor possa imprimir/enviar.

**Acceptance Criteria:**

1. Worker Celery task `render_contract_pdf(contract_id)` carrega dados, renderiza Jinja2 -> HTML -> WeasyPrint -> PDF.
2. Template em `app/infrastructure/pdf_templates/contract.html.j2` com cláusulas padrão configuráveis em `Settings`, dados do cliente/ativo, tabela de parcelas, espaço para assinatura. Nome do produto via `{{product_name}}` no template.
3. PDF gravado em MinIO sob `contracts/{contract_id}/v{version}.pdf`; URL salva em `contract.pdf_url`.
4. Hash SHA-256 do PDF gravado em `contract_events`.
5. Re-geração ao editar cria nova versão (`v+1`); versões antigas preservadas.
6. Endpoint `GET /api/v1/contracts/{id}/pdf?version=` retorna PDF (URL pré-assinada do MinIO).

#### Story 3.6 — Edição em Lote de Parcelas em Aberto e Reemissão

**Como** Gestor, **quero** alterar múltiplas parcelas em aberto de uma só vez, **para que** ajustes sejam rápidos.

**Acceptance Criteria:**

1. Tabela de parcelas do contrato com seleção múltipla (checkbox + Shift+click range).
2. Barra flutuante "Ações em Lote": Postergar X dias, Aplicar desconto X% ou X R$, Alterar valor para X, Cancelar parcelas, Recriar parcelas.
3. Ações afetam apenas parcelas com `status IN ('em_aberto','vencido')`.
4. Modal de confirmação mostra preview do antes/depois.
5. Backend valida e aplica em transação atômica; gera evento `bulk_edit` com payload completo. Títulos antigos em aberto são cancelados e novos são gerados (reemissão conforme FR-CORE-CTR-3).
6. Parcelas com `status='pago'` ou `pago_aguardando_verificacao` não podem ser tocadas — feedback claro ao usuário.

#### Story 3.7 — Versionamento e Timeline de Eventos do Contrato

**Como** Gestor, **quero** ver histórico de alterações do contrato, **para que** eu rastreie qualquer mudança.

**Acceptance Criteria:**

1. Aba "Histórico" na ficha do contrato.
2. Timeline vertical com cada evento (ícone + descrição + autor + data).
3. Clique em evento expande payload (diff visual quando aplicável).
4. Ações: "Ver PDF desta versão" para eventos de geração.

#### Story 3.8 — Rescisão de Contrato

**Como** Gestor, **quero** rescindir contrato com cálculo automático, **para que** a saída do cliente seja documentada.

**Acceptance Criteria:**

1. Botão "Rescindir" na ficha; abre modal com motivo, data efetiva, política de multa (toggle: "Aplicar multa rescisória X%", default vindo das configurações).
2. Cálculo: soma das parcelas em aberto x pct_multa + ajuste manual.
3. Gera **título de cobrança final** (ou crédito) no módulo CR.
4. Marca parcelas em aberto como `cancelado` com justificativa.
5. Status do contrato -> `rescindido`; publica `ContractTerminatedEvent` para que módulos verticais executem ações de domínio (ex.: Vehicle Module muda veículo para `disponivel`).
6. Evento `terminated` com payload completo.

---

### Épico 4 — Contas a Receber, Pagamento Parcial & Validação (Core)

**Objetivo:** o gestor consegue gerenciar todos os títulos a receber gerados pelos contratos, com baixa manual + pagamento parcial + validação de comprovantes via fila, OCR automático e geração de QR Pix sem custo. O fluxo padrão é: envio de Pix card -> pagamento direto -> screenshot -> OCR -> baixa primária.

#### Story 4.1 — Lista Mestre de Títulos a Receber

**Como** Gestor, **quero** ver todos os títulos a receber em uma única tabela poderosa, **para que** eu opere o financeiro.

**Acceptance Criteria:**

1. Tela `/system/finance/receivables` carrega `ReceivablesListComponent`.
2. Filtros: status (multi-select), cliente, ativo, contrato, faixa de vencimento (date range), faixa de valor.
3. Colunas: vencimento, cliente (com avatar), ativo (com módulo badge), contrato (link), valor original, valor atualizado (com juros/multa), status (badge), forma esperada, ações.
4. Ações por linha: Baixar, Ver, Editar (se em aberto), Cancelar (se em aberto).
5. Soma totais ao filtrar (rodapé: "Selecionados: R$ X | Filtro total: R$ Y | Inadimplência: R$ Z").
6. Atalhos: `b` baixar selecionado, `Espaço` selecionar linha, `f` foca filtro.

#### Story 4.2 — Cálculo de Juros, Multa e Desconto

**Como** Sistema, **quero** calcular valor atualizado de título vencido, **para que** baixas usem o valor correto.

**Acceptance Criteria:**

1. Função pura `compute_updated_value(installment, on_date, contract_terms)` em `domain/finance/calculations.py`.
2. Fórmula: `base = amount`; `dias_atraso = max(0, on_date - due_date - grace_days)`; `multa = amount * fine_pct if dias_atraso > 0 else 0`; `juros = amount * interest_pct_per_day * dias_atraso`; `total = base + multa + juros`.
3. Endpoint `GET /api/v1/receivables/{id}/updated-value?on_date=` retorna breakdown completo.
4. Suporta override (desconto manual) com motivo obrigatório, persistido em `installment_adjustments`.
5. Testes cobrindo: em dia, atraso curto, atraso longo, dentro da carência, com desconto.

#### Story 4.3 — Modal de Baixa Manual e Baixa Parcial

**Como** Gestor, **quero** baixar título informando dados do pagamento, incluindo pagamentos parciais, **para que** o título saia do "em aberto".

**Acceptance Criteria:**

1. Modal de baixa: data efetiva (default hoje), valor pago (default updated_value), forma (Pix/dinheiro/transferência/cartão/outros), observação, anexo de comprovante (drop-zone — obrigatório se forma=Pix).
2. Para forma=Pix, OCR roda no upload e auto-preenche valor e data se confiança >= 70%.
3. **Pagamento parcial**: se valor pago < valor do título, o sistema executa baixa parcial (registra pagamento para o valor informado) e gera automaticamente um novo título em aberto para a DIFERENÇA (valor_título - valor_pago), com `parent_installment_id` referenciando o título original e vencimento = data atual + grace_days do contrato. Novo título entra em novo ciclo de cobrança.
4. **Pagamento integral**: confirmar muda status para `pago_aguardando_verificacao`.
5. Refresh da lista; toast de sucesso indicando se foi baixa integral ou parcial (com valor do novo título gerado, se parcial).

#### Story 4.4 — Adapter de OCR

**Como** Sistema, **quero** abstração `IOcrProvider` com implementação Tesseract, **para que** OCR funcione sem custo externo.

**Acceptance Criteria:**

1. Interface:
   ```python
   class IOcrProvider(Protocol):
       async def extract_text(self, file_bytes: bytes, mime: str) -> OcrResult: ...
       async def extract_pix_receipt(self, file_bytes, mime) -> PixReceiptExtracted: ...
   ```
2. Adapter `TesseractOcrAdapter` com pré-processamento OpenCV (deskew, denoise, threshold).
3. Adapter `LlmVisionOcrAdapter` (fallback opcional) usando GPT-4o Vision ou Claude para casos que Tesseract falha.
4. Heurísticas regex para Pix: valor (`R\$\s*[\d.,]+`), data (`\d{2}/\d{2}/\d{4}`), ID transação (`[A-Z0-9]{30,}`), beneficiário, banco emissor.
5. Cache em Redis por hash do arquivo (TTL 7 dias) para reprocessamento.

#### Story 4.5 — Fila de Validação de Comprovantes

**Como** Validador, **quero** fila com comprovantes pendentes, **para que** eu valide rapidamente em massa.

**Acceptance Criteria:**

1. Tela `/system/finance/validation-queue` lista títulos `pago_aguardando_verificacao` ordenados por data crescente.
2. Layout split: lista esquerda + visualizador centralizado (imagem ou PDF preview com zoom) + painel direito com dados do título e ações (`Aprovar`, `Rejeitar`, `Solicitar Reenvio`).
3. Atalhos: `A` aprovar, `R` rejeitar, `->` próximo, `<-` anterior.
4. Aprovar muda status para `pago_aguardando_verificacao`; gera evento auditoria com `validated_by_user_id`.
5. Rejeitar exige motivo (selectable: valor divergente, comprovante ilegível, suspeita de fraude, outros + texto).
6. Solicitar Reenvio dispara mensagem WhatsApp para o cliente (via cobrança) e mantém status.
7. KPI no topo: pendentes de validação, validados hoje, rejeitados hoje.

#### Story 4.6 — Geração de QR Code Pix Estático

**Como** Sistema, **quero** gerar BR Code Pix por título, **para que** cobranças sejam imediatamente pagáveis sem gateway externo.

**Acceptance Criteria:**

1. Configuração da chave Pix da empresa em Configurações > Empresa (chave + favorecido).
2. Endpoint `GET /api/v1/receivables/{id}/pix-qr` retorna SVG/PNG do QR + texto "Copia e Cola" (BR Code).
3. Implementação via biblioteca `pix-utils` (Python) ou própria seguindo MN-002 do BCB.
4. ID da transação inclui o ID do título (para reconciliação posterior).
5. Botão na ficha do título "Gerar QR Pix" mostra modal com QR + CTA "Enviar via WhatsApp" (passa para o módulo cobrança). Este é o fluxo de pagamento padrão, evitando custos de gateway.

#### Story 4.7 — Renegociação de Títulos

**Como** Gestor, **quero** renegociar títulos vencidos, **para que** clientes em dificuldade sejam reabilitados.

**Acceptance Criteria:**

1. Selecionar múltiplos títulos vencidos do mesmo cliente -> ação "Renegociar".
2. Modal calcula soma + juros/multa atualizados; gestor define novo parcelamento (entrada + N parcelas) usando o construtor do Épico 3.
3. Confirmar marca títulos antigos como `renegociado` (imutável a partir daí) e cria novos `installments` ligados ao mesmo contrato (ou a um "contrato de renegociação" — flag).
4. Evento `renegotiated` com payload `{old_ids, new_ids, total_old, total_new}` no `audit_log`.

#### Story 4.8 — Adapter Opcional de Gateway de Pagamento

**Como** Admin, **quero** opcionalmente conectar gateway de pagamento (Asaas, Efi, Stripe), **para que** cobranças possam ser automatizadas quando o ROI justificar.

**Acceptance Criteria:**

1. Interface `IPaymentGateway` com `create_charge(installment) -> Charge`, `webhook_handler(payload, signature) -> Event`.
2. Adapter `AsaasAdapter` implementado.
3. Adapter `EfiAdapter` (Gerencianet) implementado.
4. Em Configurações > Integrações, Admin pode ativar adapter, inserir credenciais e mapear para qual conjunto de títulos será aplicado (ex.: somente clientes VIP). Plugins adicionais (boleto, cartão de crédito) também são configuráveis.
5. Webhook `/api/v1/webhooks/payment-gateway/{provider}` valida assinatura, processa idempotente, baixa título automaticamente para `pago` (pula validação manual).
6. Default: **desabilitado** — o fluxo padrão é Pix card via WhatsApp sem gateway para evitar custos.

---

### Épico 5 — Contas a Pagar & Recorrências (Core)

**Objetivo:** o gestor controla todas as despesas da operação, com lançamentos avulsos, recorrências geradas automaticamente e atalho "Lançar e Pagar" para agilidade.

#### Story 5.1 — Modelo & API de Categorias e Fornecedores

**Como** Backend, **quero** entidades para categorizar despesas, **para que** relatórios sejam ricos.

**Acceptance Criteria:**

1. Tabela `expense_categories`: id, parent_id (auto-relação), name, color, icon, is_active, module_id (nullable — para categorias injetadas por módulos verticais).
2. Tabela `suppliers`: id, name, document (CPF/CNPJ), contact, bank_data (JSONB), is_active.
3. CRUD endpoints sob `/api/v1/expense-categories` e `/api/v1/suppliers`.
4. Seeds com categorias padrão core: Salários, Aluguel, Energia, Internet, Outros. Vehicle Module registra categorias adicionais: Manutenção, Combustível, Tributos (IPVA, Licenciamento), Seguro.

#### Story 5.2 — Modelo & API de Títulos a Pagar

**Como** Backend, **quero** entidade Payable e endpoints, **para que** o frontend gerencie despesas.

**Acceptance Criteria:**

1. Tabela `payables`: id, description, supplier_id (nullable), category_id, asset_id (nullable — para custo por ativo), amount, due_date, status (`em_aberto`/`pago`/`cancelado`), paid_at, paid_amount, payment_method, attachment_url, observation, created_by, recurring_template_id (nullable).
2. Endpoints CRUD sob `/api/v1/payables`.
3. Endpoint `POST /api/v1/payables/{id}/pay` registra baixa.
4. Endpoint `POST /api/v1/payables/quick-pay` cria + baixa em uma operação atômica.

#### Story 5.3 — Despesas Recorrentes

**Como** Sistema, **quero** gerar títulos recorrentes automaticamente, **para que** o gestor não esqueça obrigações fixas.

**Acceptance Criteria:**

1. Tabela `recurring_payables_templates`: id, description, supplier_id, category_id, asset_id, amount, periodicity (`mensal`/`bimestral`/`anual`), day_of_month, start_date, end_date (nullable), is_active.
2. CRUD endpoints sob `/api/v1/recurring-payables`.
3. Job Celery diário: para cada template ativo, se hoje é dia X e não há payable gerado para o mês corrente, gera.
4. Tela "Despesas Recorrentes" com toggle ativo/inativo, próximas datas previstas, opção "Gerar agora" (para emergência).

#### Story 5.4 — Tela "Lançar e Pagar"

**Como** Gestor, **quero** atalho rápido para lançar gasto que já foi pago, **para que** registros instantâneos sejam triviais.

**Acceptance Criteria:**

1. Botão flutuante "Lançar e Pagar" disponível em qualquer tela (FAB ou no command palette).
2. Modal compacto: descrição, fornecedor (autocomplete + criar inline), categoria, valor, data (default hoje), forma de pagamento, anexo de NF (drop-zone), ativo (opcional — select filtrado por módulos ativos).
3. Confirmar cria payable já com `status='pago'` em transação atômica.

#### Story 5.5 — DRE Simplificado

**Como** Gestor, **quero** ver Receitas - Despesas por período, **para que** eu acompanhe o resultado.

**Acceptance Criteria:**

1. Tela `/system/finance/dre` com filtros: período (mês/trimestre/ano custom), ativo, categoria.
2. Estrutura: Receitas (por origem), Despesas (por categoria), Margem Bruta, Margem %.
3. Gráfico de barras comparando meses (drilldown ao clicar).
4. Exportável para Excel/PDF.

---

### Épico 6 — Orquestrador de Agentes, Mensageria e Inbox (Core + Hooks)

**Objetivo:** o gestor para de cobrar manualmente. Um Agent Orchestrator conversacional, educado e parametrizável conduz cobranças (caso de uso primário) e qualquer outra ação autorizada, seguindo políticas pré-definidas, com humano podendo intervir a qualquer momento. O orchestrator é multi-canal (WhatsApp remoto + chat in-app web), aceita texto, áudio (transcrito via `IAudioTranscriber`) e imagens, e compõe a lista de tools dinamicamente com base nas permissões RBAC do caller. Tools core estão sempre disponíveis; tools de módulo vertical são injetados via `IAssetModule.get_agent_tools()`. O fluxo padrão de pagamento é: agente envia Pix card -> cliente paga e manda screenshot -> OCR valida -> baixa primária.

#### Story 6.1 — Adapter de WhatsApp Gateway

**Como** Sistema, **quero** abstração `IWhatsAppGateway` com Evolution API como default, **para que** mudar de provedor não afete o domínio.

**Acceptance Criteria:**

1. Interface:
   ```python
   class IWhatsAppGateway(Protocol):
       async def send_text(self, to: str, text: str, *, quoted_id: str | None = None) -> SentMessage: ...
       async def send_image(self, to: str, image_bytes: bytes, caption: str | None = None) -> SentMessage: ...
       async def send_document(self, to: str, doc_bytes: bytes, filename: str) -> SentMessage: ...
       async def send_pix_card(self, to: str, br_code: str, qr_image: bytes, description: str) -> SentMessage: ...
       async def mark_as_read(self, message_id: str) -> None: ...
       async def webhook_parse(self, payload: dict, signature: str | None) -> ReceivedMessage: ...
   ```
2. Adapter `EvolutionApiAdapter` implementado e testado contra instância local.
3. Adapter `ZapiAdapter` implementado.
4. Adapter `UazapiAdapter` implementado.
5. Adapter `WhatsAppCloudApiAdapter` (Meta oficial) implementado para clientes que precisam de selo verificado.
6. Configuração via env e tela de Integrações: provider, API key, instance ID, webhook secret.

#### Story 6.2 — Domínio de Mensagens e Conversas

**Como** Backend, **quero** modelar conversas e mensagens persistidas, **para que** histórico esteja sempre disponível.

**Acceptance Criteria:**

1. Tabela `whatsapp_conversations`: id, customer_id, phone_e164, last_message_at, unread_count, is_archived, agent_active (bool), agent_paused_until.
2. Tabela `whatsapp_messages`: id, conversation_id, external_id (do provider), direction (`in`/`out`), kind (`text`/`image`/`document`/`audio`/`pix_card`/`system`), content_text, media_url, media_mime, sent_at, delivered_at, read_at, sent_by (`agent`/`human:user_id`), status (`sent`/`delivered`/`read`/`failed`), context (JSONB — IDs de títulos referenciados, etc).
3. Endpoint `GET /api/v1/conversations?search=&unread=&page=` lista conversas paginadas.
4. Endpoint `GET /api/v1/conversations/{id}/messages?before=&limit=` paginação reversa cronológica.
5. WebSocket `/ws/conversations` empurra novas mensagens em tempo real.

#### Story 6.3 — Webhook Receiver e Pipeline de Mensagens

**Como** Sistema, **quero** receber e processar mensagens recebidas com idempotência, **para que** nenhuma mensagem se perca.

**Acceptance Criteria:**

1. Endpoint `POST /api/v1/webhooks/whatsapp/{provider}` valida assinatura.
2. Persiste evento bruto em tabela `webhook_events_raw` (auditoria).
3. Encaminha para fila Celery `whatsapp_inbound`.
4. Worker normaliza para `ReceivedMessage`, identifica/cria `Conversation` (lookup por `phone_e164`), grava `WhatsAppMessage`, e enfileira para o agente decidir resposta.
5. Idempotência por `external_id` (UNIQUE).
6. Suporta mídias (download para MinIO antes de processar OCR/classificação).

#### Story 6.4 — Engine do Agente IA com RAG

**Como** Backend, **quero** agente conversacional com contexto do cliente, **para que** respostas sejam personalizadas.

**Acceptance Criteria:**

1. Adapter `ILLMProvider` com implementações: OpenAI, Anthropic, Gemini, Ollama (local).
2. Configuração: provider, modelo, temperatura, max tokens — em Configurações > Agente IA.
3. Para cada turno:
   - Carrega contexto: dados do cliente, todos os títulos em aberto/vencidos com valores atualizados, score, últimas N mensagens da conversa, política de cobrança vigente, observações livres do gestor.
   - Vetoriza mensagens antigas em `pgvector` (job assíncrono); busca top-K semanticamente similares à mensagem atual para enriquecer prompt.
   - Compõe **system prompt** parametrizado (tom, persona, regras, listas de tools).
   - Chama LLM com function calling.
   - Executa tools chamadas (com guardrails — tools sensíveis exigem condições).
   - Persiste resposta como mensagem `out` e envia via gateway.
4. **Tools core** (sempre disponíveis):
   - `consultar_titulos_em_aberto(customer_id)` -> lista
   - `enviar_qr_pix(installment_id)` -> envia card via gateway (fluxo de pagamento padrão)
   - `registrar_baixa_primaria(installment_id, valor, data, comprovante_message_id)` -> cria `pago_aguardando_verificacao`. Se valor < título, executa baixa parcial e gera novo título para a diferença.
   - `solicitar_validacao_humana(installment_id, motivo)` -> marca para validador
   - `agendar_cobranca(customer_id, when, type)` -> cria job Celery
   - `gerar_acordo(customer_id, params)` -> propõe renegociação
   - `escalar_para_gestor(motivo)` -> pausa agente, notifica
5. **Tools de módulo vertical**: injetados dinamicamente via `IAssetModule.get_agent_tools()`. Ex.: Vehicle Module injeta:
   - `bloquear_veiculo(vehicle_id, reason)` — **gated**: requer score < threshold E dias atraso >= X E confirmação humana, conforme política
   - `desbloquear_veiculo(vehicle_id, reason)` — idem
   - `verificar_localizacao_veiculo(vehicle_id)` -> consulta tracker
6. Logging completo de cada chamada (prompt, response, tools, tokens, latência) para análise.
7. Feature flag `AGENT_DRY_RUN`: agente gera mas não envia, só sugere ao humano (modo de calibração inicial).

#### Story 6.5 — Parametrização do Agente (UI)

**Como** Admin, **quero** configurar tom, regras e templates do agente, **para que** ele represente meu negócio.

**Acceptance Criteria:**

1. Tela `/system/config/agent` com seções:
   - **Persona**: nome do agente, tom (formal/amigável/descontraído — slider visual com prévia de exemplo), saudação por horário (manhã/tarde/noite — campos editáveis).
   - **Janela de Atendimento**: horário permitido para envios (default 8h-20h), dias da semana.
   - **Cobrança Preventiva**: dias antes do vencimento (input), template (textarea com placeholders `{nome}`, `{valor}`, `{data_vencimento}`).
   - **Pós-vencimento**: cadeia de mensagens em D+1, D+3, D+7 (cada uma editável + toggle ativo/inativo).
   - **Política de Concessão por Score**: tabela editável com colunas `score_min`, `score_max`, `dias_tolerancia`, `requer_aprovacao_humana`.
   - **Políticas de Módulo Vertical**: seção dinâmica renderizada com base nos módulos ativos. Ex.: Vehicle Module adiciona "Bloqueio Remoto" com toggle ativo, condições (`dias_atraso >= X` AND `score < Y`), exige aprovação humana (sim/não).
   - **Juros e Multa**: % padrão (override por contrato).
   - **Templates**: editor rich (Tiptap) com lista de templates nomeados; suporte a placeholders e prévia.
2. Toda alteração registra evento de auditoria com diff.
3. Botão "Testar Mensagem" abre modal com persona aplicada respondendo a um cliente fictício.

#### Story 6.6 — Cálculo do Score de Cliente

**Como** Backend, **quero** score recalculado periodicamente, **para que** decisões do agente sejam baseadas em dados.

**Acceptance Criteria:**

1. Job Celery diário: para cada cliente ativo, recalcula score 0-100 baseado em:
   - Pontualidade nos últimos 12 meses (60% do peso): `% pago em dia ou antes`.
   - Dias médios de atraso (20% do peso, invertido).
   - Fatores de módulo vertical (10% — ex.: Vehicle Module contribui n. de bloqueios remotos sofridos como penalidade).
   - Tempo de relacionamento (10% — bônus por longevidade).
2. Fórmula configurável em Configurações > Score (mostra valores e permite ajustar pesos). Módulos verticais registram fatores adicionais via hook.
3. Histórico de score em tabela `customer_score_history`: snapshot diário.
4. Gráfico de evolução do score na ficha do cliente (aba Score).
5. Ao recalcular, publica `CustomerScoreChangedEvent` no event bus.

#### Story 6.7 — Inbox WhatsApp (UI estilo WhatsApp)

**Como** Gestor, **quero** ver e responder conversas em interface familiar, **para que** o atendimento humano seja fluido.

**Acceptance Criteria:**

1. Tela `/system/inbox` em layout 3-painéis:
   - **Esquerda (320px)**: lista de conversas com avatar, nome, última mensagem (truncada), timestamp, badge de não lidas, ícone de status (agente ativo/pausado).
   - **Centro (flex)**: thread de mensagens com bolhas (verde-claro `bg-[var(--whatsapp-out)]` para enviadas, branco para recebidas), separadores por dia, timestamps no canto, ticks de status (enviado, entregue, lido), suporte a imagens com lightbox, áudios com player, PDFs com preview.
   - **Direita (340px, colapsável)**: contexto do cliente (avatar, nome, score grande, status, lista de títulos em aberto com valores atualizados, ações rápidas: gerar Pix, marcar como pago, escalar). Widgets de módulo vertical também exibidos (ex.: Vehicle Module mostra localização do veículo e botão "Bloquear").
2. Input de mensagem com suporte a anexo, emoji, áudio (gravação inline).
3. Toggle "Agente ativo / Pausado" no header da conversa.
4. Mensagens novas chegam via WebSocket sem refresh.
5. Atalhos: `up/down` navega conversas, `Ctrl+Enter` envia, `/` foca busca.
6. Suporta busca textual dentro da conversa atual.
7. Indicador "agente está digitando..." visível quando o agente está processando.

#### Story 6.8 — Disparo em Massa Controlado

**Como** Gestor, **quero** disparar cobrança preventiva para todos os vencendo amanhã, **para que** eu economize tempo.

**Acceptance Criteria:**

1. Tela `/system/inbox/broadcast` com seletor de público (filtros: status do título, faixa de vencimento, score, etc) -> preview de destinatários.
2. Editor de mensagem com placeholders.
3. Botão "Disparar" exige confirmação dupla (modal + senha) e mostra preview com 3 mensagens reais renderizadas.
4. Respeita janela horária; agenda envios escalonados (1 mensagem a cada X segundos para evitar ban).
5. Relatório pós-disparo: enviadas, entregues, lidas, falhas, respondidas (atualiza ao longo do tempo via webhook).
6. Limite hard-coded: máximo 200 destinatários por disparo (anti-spam guard).

#### Story 6.9 — Detecção de Comprovante, Baixa Primária e Baixa Parcial pelo Agente

**Como** Cliente, **quero** que ao enviar comprovante via WhatsApp meu título seja processado automaticamente, **para que** eu tenha confirmação imediata.

**Acceptance Criteria:**

1. Mensagens recebidas com mídia passam por classificador (heurística: imagem ou PDF + OCR detecta padrões de Pix).
2. Se classificado como comprovante: agente extrai valor + data + ID transação, busca título mais provável (cliente + valor + janela de data).
3. **Pagamento integral** (valor extraído >= valor do título): executa `registrar_baixa_primaria` com status `pago_aguardando_verificacao`.
4. **Pagamento parcial** (valor extraído < valor do título): executa baixa parcial, gerando novo título para a diferença. Responde ao cliente informando que o pagamento parcial foi recebido e o saldo restante.
5. Responde ao cliente com mensagem de confirmação (template configurável): "Recebi seu comprovante! O pagamento de R$ X relativo à parcela Y está em validação. Em breve confirmo a baixa definitiva."
6. Adiciona à fila de validação humana (Story 4.5).
7. Caso ambiguidade (múltiplos títulos compatíveis ou nenhum), agente pergunta ao cliente em linguagem natural ou escala para humano.

---

### Épico 7 — Conciliação Bancária Sofisticada (Core)

**Objetivo:** ao final do mês (ou diariamente), o gestor confere o extrato bancário com os títulos do sistema em uma tela de duplo painel com drag-and-drop, auto-match e suporte a OFX, PDF e Open Finance.

#### Story 7.1 — Importador OFX

**Como** Gestor, **quero** subir arquivo OFX do banco, **para que** transações entrem no sistema.

**Acceptance Criteria:**

1. Tela `/system/finance/reconciliation` com botão "Importar OFX".
2. Drop-zone aceita .ofx; parser via `ofxparse`.
3. Detecção de duplicatas: se `FITID` (transaction id do OFX) já existe, pula.
4. Tabela `bank_transactions`: id, account_id, fitid, posted_at, amount (signed: positivo crédito, negativo débito), description_raw, description_clean, type, status (`pendente`/`conciliada`/`ignorada`), reconciled_to (FK para installment ou payable), imported_from (`ofx`/`pdf`/`open_finance`/`manual`).
5. Pré-classificação: regex/heurísticas tentam extrair nome do remetente (em descrições de Pix), categoria provável.

#### Story 7.2 — Importador PDF Inteligente

**Como** Gestor, **quero** subir extrato PDF, **para que** mesmo bancos sem OFX funcionem.

**Acceptance Criteria:**

1. Drop-zone aceita .pdf; backend tenta primeiro parsing estruturado via `pdfplumber` + heurísticas por banco (perfis: BB, Itaú, Bradesco, Santander, Caixa, Nubank, Inter, C6).
2. Se heurística retorna < 80% das linhas confiáveis, fallback opcional via LLM (configurável + alerta de custo).
3. LLM é chamado com prompt estruturado: "Você é um parser de extrato bancário. Extraia transações no JSON Schema X."
4. Resultado é exibido em tela de revisão antes de persistir (usuário marca/desmarca linhas duvidosas).
5. Mesma tabela `bank_transactions` recebe os dados.

#### Story 7.3 — Adapter Open Finance (Pluggy)

**Como** Admin, **quero** opcionalmente conectar Open Finance, **para que** extratos venham automaticamente.

**Acceptance Criteria:**

1. Interface `IBankReconciliationProvider` com `connect_account`, `list_accounts`, `fetch_transactions(account_id, since)`, `disconnect`.
2. Adapter `PluggyAdapter` (default) implementado.
3. Adapter `BelvoAdapter` (alternativa) implementado.
4. Adapter `TecnoSpeedAdapter` (alternativa) registrado.
5. Tela em Configurações > Integrações: conectar conta (fluxo OAuth-like via widget Pluggy), listar contas conectadas, status, último sync.
6. Job Celery a cada 6h faz sync incremental.
7. Default: **desabilitado** (custo).

#### Story 7.4 — Tela de Conciliação Drag-and-Drop

**Como** Gestor, **quero** conciliar transações com títulos arrastando, **para que** o trabalho seja rápido e visual.

**Acceptance Criteria:**

1. Tela `/system/finance/reconciliation` em layout split (50/50):
   - **Esquerda**: tabela `bank_transactions` filtráveis (status=pendente, faixa de data, valor +/-, tipo).
   - **Direita**: tabela de títulos do sistema candidatos (`installments` + `payables` em `pago_aguardando_verificacao`).
2. Linha pode ser arrastada (CDK Drag-Drop) sobre item do outro lado -> drop dispara confirmação modal com diff.
3. **Auto-match** roda em background: `score = exato_valor (60%) + janela_data (30%) + match_descricao (10%)`. Se score >= 0.85, pinta a linha em verde-claro com sugestão visível (badge "match sugerido").
4. Botão "Aceitar todas as sugestões" aplica em massa.
5. Suporte a **N:1** (múltiplas transações para um título): seleção múltipla esquerda + drop em um título à direita.
6. Suporte a **1:N** (uma transação cobre vários títulos): seleção múltipla direita + drop da transação.
7. **Transações sem match** podem virar `payable` ou `receita avulsa` por botão lateral.
8. Confirmação muda status final: título -> `pago`; transação -> `conciliada`. Publica `ReconciliationCompletedEvent`.
9. Indicadores visuais: total transações pendentes, total títulos pendentes, total conciliado hoje.

#### Story 7.5 — Detecção de Divergências

**Como** Sistema, **quero** alertar inconsistências, **para que** o gestor decida.

**Acceptance Criteria:**

1. Painel "Alertas" no topo da tela mostra:
   - Transações sem título compatível (possível receita avulsa ou erro do banco).
   - Títulos baixados como `pago` sem transação no extrato (possível problema).
   - Transações com valor diferente do título (sugestão de match parcial com aviso — pode indicar pagamento parcial que gerou novo título).
2. Cada alerta clicável leva à investigação contextual.

---

### Épico 8 — Dashboards, Relatórios & Patrimônio (Core + Hooks)

**Objetivo:** o gestor tem visão executiva consolidada e drilldown a qualquer nível, com relatórios prontos e construtor customizado. Dashboards genéricos do core são enriquecidos com widgets injetados pelos módulos verticais ativos.

#### Story 8.1 — Dashboard Principal

**Como** Gestor, **quero** ver KPIs do negócio em uma tela, **para que** eu sinta o pulso do operacional.

**Acceptance Criteria:**

1. Tela `/system/dashboard` com grid responsivo de cards:
   - **Cards core (sempre visíveis)**:
     - Receita do Mês (atual vs anterior, % delta).
     - Despesas do Mês.
     - Lucro Líquido do Mês.
     - Inadimplência (R$ + % do total a receber).
     - Ativos em Uso / Parados.
     - Próximos 7 dias: Vencimentos a Receber (R$ + qtd).
     - Comprovantes Pendentes (qtd com badge urgente se > 5).
     - Score Médio da Carteira.
   - **Cards de módulo vertical (injetados via `get_dashboard_widgets()`)**: ex.: Vehicle Module injeta Frota Total (R$ FIPE consolidado), Veículos Ativos / Parados / Em Manutenção, mini-gráfico de evolução patrimonial.
2. Cards são reativos via Signals com `resource()` API; refresh a cada 60s ou via SSE quando há mudanças.
3. Cada card é clicável e leva ao drilldown (lista filtrada da entidade).
4. Toggle "Hoje | Esta Semana | Este Mês | Este Trimestre | Este Ano" no topo.
5. Gráficos: linha de receita 12 meses, donut de despesas por categoria, barras de inadimplência por faixa etária.

#### Story 8.2 — Dashboard por Cliente

**Como** Gestor, **quero** dashboard financeiro do cliente, **para que** eu negocie com dados.

**Acceptance Criteria:**

1. Aba "Dashboard" na ficha do cliente.
2. Cards: Total Contratado, Total Pago, Total em Aberto, Total Vencido, Score Atual (gauge), Pontualidade % (12m).
3. Gráfico de pagamentos (linha temporal — pago em dia / pago atrasado / não pago).
4. Tabela de contratos com saldos e ROI por contrato.
5. Botão "Exportar histórico do cliente" (PDF).

#### Story 8.3 — Dashboard por Ativo (Vehicle Module)

**Como** Gestor, **quero** analisar viabilidade de cada veículo, **para que** eu tome decisões de venda/troca.

**Acceptance Criteria:**

1. Aba "Análise" na ficha do veículo (renderizada pelo Vehicle Module).
2. Cards: Investimento (compra + financiamento total), FIPE Atual, Depreciação, Recebido Total, ROI %, Lucro Acumulado, Payback (meses, projetado se ainda ativo, real se já pago).
3. Gráfico comparativo: linha de investimento acumulado vs receita acumulada.
4. KM rodado se rastreador fornecer (cumulativo desde aquisição).
5. Produtividade: R$/dia, R$/km (se aplicável).
6. Linha do tempo de clientes que usaram o veículo.

#### Story 8.4 — Relatórios Prontos

**Como** Gestor, **quero** relatórios pré-construídos, **para que** análises rotineiras sejam de um clique.

**Acceptance Criteria:**

1. Tela `/system/reports` com cards de relatórios disponíveis:
   - **Relatórios core**:
     - Top Clientes por Receita (12m).
     - Inadimplência por Faixa Etária.
     - DRE Consolidada e por Ativo.
     - Curva ABC de Clientes.
   - **Relatórios de módulo vertical** (registrados via `get_report_dimensions()`): ex.: Vehicle Module registra:
     - Top Veículos por ROI (12m).
     - Histórico de Bloqueios Remotos.
     - Posição da Frota (data X) — valor patrimonial total.
2. Cada relatório abre em viewer com filtros, gráficos e tabela.
3. Exportação para Excel (com formatação) e PDF (com cabeçalho/rodapé).
4. Geração de relatórios pesados em background (Celery) com notificação SSE quando pronto.

#### Story 8.5 — Construtor de Relatórios Customizado

**Como** Gestor avançado, **quero** montar meu próprio relatório, **para que** eu não dependa de TI.

**Acceptance Criteria:**

1. Tela `/system/reports/builder` com 3 zonas de drag-and-drop:
   - **Dimensões disponíveis** (lista): cliente, ativo, contrato, categoria, mês, status, etc. + dimensões de módulos verticais.
   - **Linhas** e **Colunas** (drop targets).
   - **Medidas** (drop targets): qtd, soma, média, máx, mín de campos numéricos.
2. Filtros laterais (data, status, cliente).
3. Preview da tabela atualiza em tempo real.
4. Botão "Salvar como" cria relatório favorito (em `saved_reports`).
5. Compartilhamento futuro via URL (read-only) — não no MVP.

---

### Épico 9 — Hardening, Plug-and-Play Final & Documentação (Core)

**Objetivo:** o sistema está completo. Falta o último 20% que separa software demo de software de produção: auditoria robusta, painel de integrações funcional, testes de carga, polimento de UX e documentação detalhada para futuros mantenedores e criadores de módulos verticais.

#### Story 9.1 — Painel Centralizado de Integrações

**Como** Admin, **quero** uma tela única para gerenciar todas as integrações, **para que** plug-and-play seja uma realidade operável.

**Acceptance Criteria:**

1. Tela `/system/config/integrations` com cards para cada categoria:
   - **Core**: WhatsApp Gateway, Open Finance / Bancos, Gateway de Pagamento, LLM Provider, OCR Provider, Storage (MinIO/S3/Azure Blob), PDF Renderer (WeasyPrint/Browserless/Gotenberg).
   - **Vehicle Module** (se ativo): FIPE, Rastreador.
   - Outros módulos verticais exibem suas integrações dinamicamente.
2. Cada card mostra: provider ativo, status (saudável / degradado / erro), botão "Testar conexão", "Trocar provider", "Configurar".
3. Selecionar trocar abre lista de adapters disponíveis com checkboxes para credenciais necessárias.
4. Credenciais são encriptadas em repouso (KMS ou Vault).
5. Toda alteração gera evento de auditoria com diff (com mascaramento de secrets).
6. Endpoint `GET /api/v1/integrations/health` retorna status de todas; usado por monitoring externo.

#### Story 9.2 — Gerenciamento de Módulos Verticais

**Como** Admin, **quero** ativar/desativar módulos verticais sem restart, **para que** o sistema se adapte ao meu negócio.

**Acceptance Criteria:**

1. Tela `/system/config/modules` lista módulos registrados com: nome, descrição, status (ativo/inativo), integrações associadas, permissões registradas.
2. Toggle ativo/inativo por módulo; requer confirmação (desativar módulo oculta funcionalidades mas preserva dados).
3. Ao ativar módulo, sidebar e dashboard ganham menus/widgets do módulo; ao desativar, esses elementos somem.
4. Dados do módulo nunca são deletados ao desativar — apenas ocultados da UI.

#### Story 9.3 — Logs de Auditoria Completos & Visualização

**Como** Auditor, **quero** consultar todo o histórico de ações, **para que** eu rastreie qualquer evento.

**Acceptance Criteria:**

1. Tela `/system/audit` com tabela searchable: usuário, ação, entidade, data, IP, payload.
2. Filtros: usuário, entidade, ação (multi-select), data range, módulo (core ou vertical).
3. Clicar em linha mostra payload diff antes/depois (em JSON pretty-print colapsável).
4. Verificação HMAC: indicador visual de "íntegro" se assinatura confere; "ALERTA: alterado" se não.
5. Exportação CSV com filtro aplicado.

#### Story 9.4 — Backup, Restore e DR

**Como** Operador, **quero** backups automáticos verificados, **para que** desastres sejam recuperáveis.

**Acceptance Criteria:**

1. Job Celery diário 03h faz `pg_dump` comprimido, envia para storage off-site (S3 / B2 / Wasabi configurável), retém 30 dias.
2. WAL contínuo via wal-g ou pgBackRest.
3. Job Celery semanal restaura backup em ambiente isolado e roda smoke tests; falha alerta admins.
4. Documento `RUNBOOK_DR.md` no repositório com passo-a-passo de restauração em < 4h.

#### Story 9.5 — Observabilidade Completa

**Como** Operador, **quero** dashboards Grafana e alertas, **para que** eu opere o sistema com confiança.

**Acceptance Criteria:**

1. Métricas Prometheus expostas em `/metrics`: contadores de requests por rota/método/status, latência P50/P95/P99, profundidade de filas, erros, conexões DB.
2. Tracing OpenTelemetry em todas as requests; visível em Jaeger ou Tempo.
3. Logs estruturados JSON com `correlation_id` propagado.
4. Dashboards Grafana versionados em `infra/observability/grafana/`.
5. Alertas configurados: API acima de 1% 5xx em 5min, Latência P95 > 1s, Fila Celery > 1000 itens, Disk > 85%.

#### Story 9.6 — Testes de Carga e Performance Tuning

**Como** Time, **quero** validar que o sistema aguenta a carga prevista, **para que** lançamento seja seguro.

**Acceptance Criteria:**

1. Suite k6 em `tests/load/` com cenários: dashboard, lista de títulos, baixa, conciliação.
2. Targets validados: 100 RPS sustentados, P95 <= 300 ms (read), 500 ms (write).
3. Otimizações documentadas: índices, query rewrites, caching, paginação cursor-based em listas grandes.

#### Story 9.7 — Documentação Final

**Como** Próximo Desenvolvedor, **quero** docs completas, **para que** eu mantenha o produto sem o autor original.

**Acceptance Criteria:**

1. `README.md` com setup local em < 10 min.
2. `ARCHITECTURE.md` revisado e versionado.
3. `ADAPTERS.md` — guia "como adicionar um novo adapter" para cada interface (WhatsApp, Bank, Payment, LLM, OCR).
4. `MODULES.md` — guia "como criar um novo módulo vertical" implementando `IAssetModule`, com exemplo passo-a-passo.
5. `API.md` ou OpenAPI publicado em `/docs`.
6. `DEPLOYMENT.md` com playbook de deploy.
7. `RUNBOOK.md` com troubleshooting comum.
8. ADRs (Architecture Decision Records) em `docs/adrs/` para decisões não-óbvias (ex.: SSE vs WebSocket; Asset Abstraction Layer; SQLAlchemy 2 typed; pgvector vs Qdrant).

#### Story 9.8 — Polimento de UX e Microinterações

**Como** Usuário, **quero** o app polido, **para que** a experiência seja prazerosa.

**Acceptance Criteria:**

1. Animações de transição de página (FLIP / View Transitions API).
2. Skeleton loaders em todas as listas e cards.
3. Toasts unificados com fila e descarte automático.
4. Empty states com ilustração + CTA em todas as listas.
5. Modais com `prefers-reduced-motion` respeitado.
6. Feedback visual em todas as ações (otimismo + rollback em erro).
7. Acessibilidade: auditoria com axe-core CI; zero violations críticas.
8. Mobile: revisão tela a tela em 375px e 768px.

---

## 7. Checklist Results Report

> A ser preenchido após execução do `pm-checklist` e revisão pelo PO.

**Áreas a validar:**

- [ ] Cobertura completa do brief original (cada bullet do prompt -> >= 1 FR).
- [ ] Cada épico entrega valor independente.
- [ ] Cada história é AI-agent-sized (<= 1 dia, escopo claro).
- [ ] Sequenciamento lógico (dependências respeitadas).
- [ ] NFRs cobrem segurança, performance, escalabilidade, LGPD.
- [ ] Plug-and-play está cravado em arquitetura, não em "vontade".
- [ ] Asset Abstraction Layer (`IAssetModule`) bem definida e testável.
- [ ] Core funciona sem nenhum módulo vertical ativo (modo "billing-only").
- [ ] Separação clara entre FRs Core e FRs de módulo vertical.
- [ ] Nenhum nome de produto hardcoded — apenas `{{product_name}}`.

---

## 8. Next Steps

### 8.1 Architect Prompt

> Architect (Winston, BMAD): receba este PRD + os arquivos `angular-structure.md` e `frontend_architecture_manifesto.md` do cliente. Produza o documento `ARCHITECTURE.md` completo, cobrindo: high level architecture, tech stack definitivo, data models (incluindo tabela `assets` genérica e módulo vehicles), API spec OpenAPI, component design, Asset Abstraction Layer (`IAssetModule` + Event Bus + Module Registry), external APIs com adapters, core workflows com sequence diagrams (incluindo fluxo de pagamento padrão Pix card -> screenshot -> OCR -> baixa primária e fluxo de pagamento parcial), database schema completo, source tree (frontend Angular standalone com signals/resources + backend FastAPI modular com pasta `modules/`), development workflow, deployment, error handling, security, performance, testing strategy, monitoring. Decida explicitamente: SSE vs WebSocket vs polling para cada caso; Celery vs Dramatiq; pgvector vs Qdrant; storage MinIO vs S3; LLM provider default. Use diagramas Mermaid sempre que enriquecer a leitura. Mantenha **plug-and-play como tema central** — toda integração externa atrás de uma Port (interface). Estrutura de pastas: `api/` e `frontend/` (sem nome de produto). Nome do produto via env var `PRODUCT_NAME`.

### 8.2 UX Expert Prompt

> UX Expert (Sally, BMAD): use as seções 3 e 6 deste PRD para produzir `FRONT_END_SPEC.md` cobrindo: information architecture (com menus dinâmicos por módulo vertical ativo), fluxos críticos (login, criar contrato com ativo genérico, baixar título com pagamento parcial, validar comprovante, conciliação, conversar via inbox), wireframes textuais, estados (loading, empty, error, success), componentes do design system (catálogo com variantes), tokens visuais finais (paleta, tipografia, spacing, motion), microinterações chave, padrões de teclado, acessibilidade. Stack: Tailwind v4 + shadcn-inspired + Heroicons. Foco em densidade de informação operacional sem perder respiração visual. Nome do produto via `{{product_name}}` placeholder.

### 8.3 PO Prompt

> Product Owner (Sarah, BMAD): valide alinhamento PRD <-> Brief. Sequencie histórias do Épico 1 para sprints de 5 dias. Identifique riscos de bloqueio (ex.: credenciais Evolution API, instância de teste do rastreador). Aprovar épicos para descida ao SM. Validar que o core funciona sem módulos verticais e que a separação Core vs Vehicle Module está correta.

---

> *"Build the right product, then build it right. The PRD is the contract between business and engineering — it must be precise, complete, and lived."* — BMAD Method
