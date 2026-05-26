# Manual Funcional do Desenvolvedor — FrotaUber

> **Para quem:** desenvolvedor novo no time que precisa entender o NEGÓCIO antes de mexer no código.
> **O que NÃO é:** manual técnico, guia de API, doc de arquitetura. Para isso, ver `architecture.md`, `PRD.md` e os épicos em `_bmad-output/planning-artifacts/`.
> **Autor:** John (PM) | **Versão:** 1.0 | **Data:** 24/05/2026

---

## Índice

1. [Visão geral do sistema](#1-visão-geral-do-sistema)
2. [O modelo de negócio (rent-to-own)](#2-o-modelo-de-negócio-rent-to-own)
3. [Atores e perfis de usuário](#3-atores-e-perfis-de-usuário)
4. [Fluxos principais — operação do gestor](#4-fluxos-principais--operação-do-gestor)
5. [Regras de negócio explícitas](#5-regras-de-negócio-explícitas)
6. [Multi-tenancy (Modelo A)](#6-multi-tenancy-modelo-a)
7. [Glossário do domínio (PT-BR)](#7-glossário-do-domínio-pt-br)
8. [Decisões de produto e seus porquês](#8-decisões-de-produto-e-seus-porquês)
9. [Roadmap atual (Épicos 10 a 13)](#9-roadmap-atual-épicos-10-a-13)

---

## 1. Visão geral do sistema

### 1.1 Para quem é

FrotaUber é uma plataforma SaaS multi-tenant voltada a **gestores de frota de veículos alugados a motoristas de aplicativo** (Uber, 99, InDrive, iFood Moto). O perfil do cliente-âncora é:

- Operador com 10 a 200 veículos próprios.
- Modelo comercial: aluga o carro ao motorista por uma diária/semanal/mensal, e em muitos contratos oferece **opção de compra** ao final.
- Hoje opera tudo no Excel, WhatsApp manual e grupos com motoristas. Sangra horas/semana com cobrança, perde dinheiro com fraude de comprovante, não enxerga ROI por veículo.

O produto resolve esse gestor — mas o **core do sistema é genérico** (plataforma de cobrança recorrente + gestão de ativos), e o "Vehicle Module" é o primeiro módulo vertical plugável. Outros verticais (imóveis, equipamentos, assinaturas) podem ser plugados depois sem alterar o core.

### 1.2 O que o sistema resolve, em uma frase

> "Transforma uma planilha caótica de cobrança manual no WhatsApp em um motor financeiro auditável, com bloqueio remoto do ativo quando o cliente atrasa, conciliação bancária verificável e dashboard de ROI por veículo."

### 1.3 O que diferencia (não é "mais um ERP")

- **Foco obsessivo em WhatsApp como canal de cobrança.** Não é "tem chat também". É o **único canal natural** do motorista, e o sistema é desenhado em torno disso (token economy, agente IA classificador, templates determinísticos, OCR de comprovante).
- **Bloqueio remoto do veículo via GPS é primeira classe.** Não é integração extra; é parte do motor de cobrança.
- **Pagamento Pix em confiança + OCR de comprovante.** O gestor brasileiro não quer pagar R$ 2,00 por Pix de gateway. O sistema valida comprovante com OCR + conciliação bancária diferida.
- **Configuração tipada pelo gestor.** Tudo que é parâmetro (multa, juros, dias para suspender, dias para encerrar, multa por cancelamento) é editável na UI, sem dev.
- **Auditoria forte.** Toda mutação sensível é registrada em audit log imutável com HMAC.

### 1.4 Tech stack em uma frase

Backend Python/FastAPI hexagonal, frontend Angular 21 standalone com Signals, Postgres + Redis + MinIO, Celery para motor de cobrança, tudo Docker.

---

## 2. O modelo de negócio (rent-to-own)

Este é o **único capítulo que o dev novo precisa decorar.** Se você não entender este modelo, vai mexer no código achando que sabe e vai quebrar coisa.

### 2.1 Como funciona um contrato típico

Um motorista chega no gestor e fecha o seguinte negócio:

- Veículo: HB20 2023.
- Valor de mercado: R$ 80.000 (FIPE).
- Acordo:
  - **100 parcelas mensais de R$ 800** (= R$ 80.000 pagos pelo uso ao longo de ~8 anos).
  - **1 parcela única final de R$ 20.000** (opção de compra).

O contrato é gerado no sistema com:

- 100 títulos `tipo = 'parcela'` (mensalidades pelo uso).
- 1 título `tipo = 'opcao_compra'` no final.

### 2.2 Os três desfechos possíveis

#### Desfecho A — Cliente paga tudo (parcelas + opção de compra)

- 100 parcelas pagas → tudo baixado.
- Última parcela (`opcao_compra`) paga → dispara evento `ContractPurchaseOptionExercised`.
- Veículo é transferido formalmente ao cliente.
- Contrato vai para estado `encerrado_compra`.
- Veículo sai da frota (`status = 'vendido'`).

#### Desfecho B — Cliente cancela sem atraso

- Cliente devolve o veículo, está em dia, não quer mais.
- Saldo devedor = R$ 0 (nada vencido).
- Veículo volta para a frota (`status = 'disponivel'`).
- Contrato vai para `encerrado_sem_pendencia`.
- **Crítico:** o gestor NÃO cobra o "valor residual do contrato". O que o cliente devia era pelo USO, e ele pagou pelo uso até hoje. As parcelas futuras simplesmente são canceladas (status `cancelado`).

#### Desfecho C — Cliente cancela COM parcelas atrasadas (ou some)

- Cliente devolve o veículo (ou é apreendido), mas existem 3 parcelas vencidas e não pagas.
- Essas 3 parcelas viram **`passivo_inoperante`** — ficam registradas como dívida histórica, podem ir para protesto/cobrança jurídica, mas o contrato é encerrado.
- Saldo devedor = soma das parcelas atrasadas (NÃO o residual do contrato).
- Veículo volta para a frota.
- Contrato vai para `encerrado_com_pendencia`.

### 2.3 A definição crítica de saldo devedor

**Saldo devedor de um cliente = SOMA dos títulos com status `vencido` (ou seja, parcelas que venceram e não foram pagas).**

NÃO é:

- O valor residual do contrato.
- A soma das parcelas futuras.
- O total que o cliente "ainda deve pagar pelo veículo".

Por quê? Porque o modelo é locação. As parcelas futuras representam uso futuro do veículo. Se o cliente devolve o veículo amanhã, ele não usa mais → não deve mais. O sistema deve refletir essa realidade jurídica.

Toda query, todo dashboard, todo dunning message que mostra "saldo devedor" deve usar essa definição. Se você ver código que soma parcelas futuras como dívida, é bug.

### 2.4 Multa por cancelamento antecipado

Configurável por contrato (`multa_cancelamento_percentual`, default 0%). Se > 0, ao rescindir o contrato antes do prazo o sistema gera 1 título adicional `tipo = 'multa'` no valor de `(parcelas_futuras_restantes * percentual)`. Por padrão é 0 porque o mercado brasileiro de aluguel informal não cobra multa.

---

## 3. Atores e perfis de usuário

### 3.1 Quem usa o sistema

| Ator | Quem é | O que faz no sistema |
|---|---|---|
| **Admin** | Dono da frota ou gestor sênior | Tudo: configurações, parametrização, convidar usuários, estornos, ver financeiro consolidado |
| **Operador** | Funcionário do escritório (atendimento) | Cadastra cliente, cria contrato, lança recebimento, processa comprovante. Não muda parâmetros nem estorna |
| **Validador** | Pessoa dedicada a aprovar comprovantes | Só a fila de validação de pagamentos e conciliação bancária |
| **Auditor** | Contador externo, sócio passivo | Read-only em tudo financeiro |
| **Cliente final (motorista)** | NÃO usa a UI do sistema | Interage 100% via WhatsApp (recebe cobranças, envia comprovante, pede 2ª via) |

**Importante:** o cliente final (motorista) **nunca loga no sistema**. Não tem app, não tem portal. O canal dele é WhatsApp. Isso é proposital — a personae é "motorista de app que mal sabe usar email". Toda funcionalidade pensada para o motorista tem que ser entregue via mensagem de WhatsApp (texto + menu botão + áudio às vezes).

---

## 4. Fluxos principais — operação do gestor

### 4.1 Onboarding (primeiro uso)

1. **Empresa nova se cadastra** via convite/contrato comercial (self-register desabilitado em V1 — ver decisão 8.2).
2. Time interno cria a empresa (tenant) no banco e o **primeiro Admin**.
3. Admin recebe email com link de definir senha.
4. Primeiro login → tour guiado mostra:
   - Configurações da empresa (logo, dados fiscais).
   - Configurações de cobrança (juros, multa, dias para suspender, dias para encerrar).
   - Conectar WhatsApp (escanear QR Code via Uazapi/Z-API/Evolution — gestor escolhe provider).
   - Convidar primeiro operador.
5. Admin convida usuários por email → cada um recebe link de cadastro de senha → entra no tenant da empresa.

**Regra dura:** um email pertence a UMA empresa só. Se o mesmo email tentar ser convidado por duas empresas, a segunda recebe erro. Isso é Modelo A (ver capítulo 6).

### 4.2 Cadastrar cliente → cadastrar veículo → criar contrato

#### 4.2.1 Cadastrar cliente

- Wizard multi-step (não é drawer lateral — padrão do sistema):
  - **Step 1:** dados pessoais (nome, CPF/CNPJ com validação, RG, telefone E.164, email, data nascimento).
  - **Step 2:** endereço (CEP via ViaCEP autopreenchido).
  - **Step 3:** CNH (módulo Vehicle: número, categoria, validade, foto).
  - **Step 4:** anexos (PDF/JPG até 10 MB cada).
- Ao salvar, cliente está disponível para contratos.
- Existe também importação Excel em lote para migração inicial.

#### 4.2.2 Cadastrar veículo

- Wizard multi-step:
  - **Step 1:** placa (validação Mercosul) + Renavam + chassi.
  - **Step 2:** marca → modelo → ano-combustível (busca FIPE encadeada, autopreenche valor).
  - **Step 3:** dados de aquisição (data, valor pago, modelo de pagamento — à vista / financiado / consórcio / custom).
  - **Step 4:** rastreador GPS (código do dispositivo, vincula com tracker provider).
  - **Step 5:** documentação (seguro, IPVA, licenciamento, datas de vencimento).
  - **Step 6:** fotos (galeria com lightbox).
- Job mensal (dia 5) atualiza `valor_fipe_atual` automaticamente.

#### 4.2.3 Criar contrato

- Wizard multi-step:
  - **Step 1:** selecionar cliente (SearchableSelect com busca server-side).
  - **Step 2:** selecionar veículo (SearchableSelect, só lista veículos com status `disponivel`).
  - **Step 3:** datas (início, término previsto) + periodicidade (diária/semanal/quinzenal/mensal) + dia de vencimento.
  - **Step 4:** construtor visual de parcelas — entrada opcional + N parcelas regulares + extras semestrais/anuais + carência + opção de compra (valor + cláusula).
  - **Step 5:** parâmetros financeiros (% juros ao dia, % multa, % multa de cancelamento, política de cobrança a usar).
  - **Step 6:** cláusulas livres em editor rich text.
  - **Step 7:** revisão + gerar PDF + assinar (anexo de PDF assinado ou D4Sign futuramente).
- Ao salvar com status `ativo`:
  - Sistema gera N títulos `tipo = 'parcela'` + 1 título `tipo = 'opcao_compra'` (se houver).
  - Veículo passa para `alugado`.
  - Evento `ContractCreated` é disparado (motor de cobrança começa a agendar lembretes).

### 4.3 Operação diária do gestor

**Manhã (10 minutos no máximo):**

1. Abre dashboard → vê KPIs (recebido hoje, a receber hoje, atrasados, fila de validação).
2. Vai na **fila de validação de comprovantes**: cada item tem foto do comprovante + dados extraídos pelo OCR + match sugerido com título. Clica "validar" ou "rejeitar" (e responde no WhatsApp se rejeitou).
3. Vai na **inbox WhatsApp**: vê conversas não respondidas pelo agente IA (ou que o agente escalou para humano).
4. Vai em **conciliação bancária** (1x/semana): importa OFX/PDF do extrato, faz drag-and-drop dos lançamentos não conciliados.

**Durante o dia (passivo):**

- Motor de cobrança roda sozinho (Celery beat). Envia lembrete D-3, D-1, D0, D+1, D+3, D+7. Cada envio passa pelo agente IA (que pode customizar tom baseado no score do cliente).
- Cliente paga → manda comprovante no WhatsApp → OCR extrai valor e data → sistema tenta auto-match com um título em aberto do cliente → se confidence alto, vai para `pago_aguardando_verificacao`; se baixo, vai para fila manual.

### 4.4 Como o motor de cobrança funciona

Esta é uma das peças mais críticas do sistema. Vale entender a lógica:

#### 4.4.1 Política de cobrança (configurável por tenant ou por contrato)

```
politica_cobranca:
  lembrete_dias_antes: [3, 1]      # avisa D-3 e D-1
  enviar_no_vencimento: true       # envia no dia D0
  escalacao_pos_vencimento: [1, 3, 7, 15]  # avisa D+1, D+3, D+7, D+15
  limite_dias_bloqueio: 7          # bloqueia GPS a partir de D+7
  limite_dias_suspensao: 15        # suspende contrato a partir de D+15
  limite_dias_encerramento: 60     # encerra com pendência a partir de D+60
  auto_block: true                 # bloqueio automático sem aprovação humana
  score_minimo_para_bloqueio: 0    # 0 = bloqueia todos; >0 = só bloqueia score abaixo
```

#### 4.4.2 O que o motor faz (Celery Beat + 32 tasks orquestradas)

- **Diariamente às 06:00:** scan de todos os títulos ativos. Para cada um, decide:
  - Está em janela de lembrete? → enfileira task `enviar_lembrete`.
  - Venceu hoje e não pagou? → marca como `vencido`, enfileira `enviar_aviso_vencimento`.
  - Está atrasado X dias onde X está na lista de escalação? → enfileira `enviar_escalacao`.
  - Atingiu `limite_dias_bloqueio`? → enfileira `bloquear_veiculo` (passa pelo `IAssetModule` do Vehicle).
  - Atingiu `limite_dias_suspensao`? → muda contrato para `suspenso`.
  - Atingiu `limite_dias_encerramento`? → muda contrato para `encerrado_com_pendencia`, marca parcelas atrasadas como `passivo_inoperante`, retorna veículo para frota.
- Tudo idempotente (3 camadas de idempotência: chave única por título+evento+data, lock Redis, status_check).
- Paralelismo: coordinator task faz fan-out em lotes de 50.

#### 4.4.3 O agente IA entra onde?

- Ele NÃO decide quando cobrar (isso é o motor determinístico).
- Ele decide **como redigir a mensagem**: usa template base + ajusta tom baseado no score do cliente (cliente score 90 = tom amigável; score 30 = tom firme).
- Quando o cliente responde, o agente IA classifica intent (vou pagar amanhã / não vou pagar / quero parcelar / xingou / mandou comprovante) e dispara a ação correspondente.
- Em modo `ia-zero` (Épico 11) o agente é substituído por regex + menu interativo WhatsApp. Sistema não para nunca.

### 4.5 Pagamento parcial: as duas situações

Cliente devia R$ 800, pagou R$ 700. E aí?

**Regra de fusão (configurável, default `limite_fusao_percentual = 20%`):**

- **Resto ≤ 20% do valor original (resto ≤ R$ 160):** o resto (R$ 100) é **fundido no próximo título**. O título antigo vira `pago_parcial` (imutável). O próximo título de R$ 800 passa para R$ 900. Não cria título solto.
- **Resto > 20% do valor original (ex.: pagou R$ 300, resto R$ 500):** cria um **novo título** com vencimento configurável (default = mesma data, ou D+3, configurável). O título antigo vira `pago_parcial` (imutável). Novo título R$ 500 entra na régua de cobrança normalmente.

**Por que essa regra existe?** Sem ela, todo pagamento que faltam R$ 5 vira um título solto que polui a base e consome dunning. Fundir até 20% é prática operacional consagrada — gestor faz isso na cabeça, sistema só formaliza.

### 4.6 Cliente em atraso: bloqueio → desbloqueio em confiança → re-bloqueio

#### 4.6.1 Bloqueio automático

- Motor de cobrança detecta atraso >= `limite_dias_bloqueio` (ex.: 7 dias).
- Verifica `auto_block = true` e `score_cliente < score_minimo_para_bloqueio` (ou ambos atendidos).
- Dispara `IAssetModule.on_installment_overdue` → módulo Vehicle chama `ITrackerGateway.bloquear(veiculo_id)`.
- Se gateway API falhar → fallback RPA (script automatizando painel web do tracker).
- Se RPA falhar → fallback notificação manual (cria task na fila do gestor com instrução).
- Cliente recebe mensagem WhatsApp: "Seu veículo foi bloqueado por inadimplência. Para desbloquear, pague R$ X via Pix abaixo, ou solicite desbloqueio em confiança."

#### 4.6.2 Desbloqueio em confiança (Épico 13)

- Cliente solicita desbloqueio para "trabalhar e conseguir pagar".
- Gestor (ou agente IA com regra) aprova: clica em "desbloquear em confiança" → escolhe **validade em dias** (default configurável, ex.: 3 dias).
- Sistema:
  - Manda `desbloquear` no tracker.
  - Grava `unblock_until = now + 3 dias`.
  - Manda mensagem ao cliente: "Desbloqueado em confiança até DD/MM. Se não pagar até lá, será bloqueado novamente automaticamente."
- Cron diário verifica `unblock_until < now AND ainda em atraso` → re-bloqueia automaticamente.
- Toda essa interação é auditada (quem aprovou, por quanto tempo, motivo).

#### 4.6.3 Suspensão e encerramento

- D+15 (configurável): contrato vai para `suspenso`. Visualmente fica vermelho na lista. Títulos continuam acumulando (não geram novos — os existentes mantém status `vencido`).
- D+60 (configurável): motor encerra contrato → `encerrado_com_pendencia`. Parcelas vencidas que continuam não pagas viram `passivo_inoperante`. Veículo retorna para frota.

### 4.7 Encerramento de contrato — 3 cenários

| Cenário | Trigger | Estado final | Veículo |
|---|---|---|---|
| Limpo | Cliente devolveu sem atraso, todas as parcelas pagas até a data ou canceladas | `encerrado_sem_pendencia` | Volta para `disponivel` |
| Com pendência | Motor automático após X dias de atraso OU gestor rescinde manualmente com saldo devedor | `encerrado_com_pendencia` | Volta para `disponivel`, parcelas vencidas viram `passivo_inoperante` |
| Opção de compra exercida | Cliente pagou todas as parcelas + título `opcao_compra` | `encerrado_compra` | Vai para `vendido`, transferência formal de propriedade é registrada |

**Rescisão manual:** Admin pode rescindir antes do prazo. Sistema pergunta motivo (campo livre), calcula saldo devedor (vencidos + opcionalmente multa de cancelamento), encerra.

### 4.8 Conciliação bancária

Fluxo semanal (ou diário em frotas grandes):

1. Gestor exporta extrato do banco em OFX ou PDF.
2. Faz upload na tela de Conciliação.
3. Sistema processa:
   - OFX: parser nativo extrai lançamentos.
   - PDF: OCR + heurística (formato bancário).
   - Open Finance: opcional, lê via API se gestor conectou.
4. UI mostra dois painéis:
   - Esquerda: lançamentos do extrato (entradas).
   - Direita: títulos com status `pago_aguardando_verificacao`.
5. Sistema sugere matches por valor + data (algoritmo de fingerprint).
6. Gestor confirma drag-and-drop ou aceita sugestão em lote.
7. Match confirmado → título vai para `pago` (imutável). Lançamento bancário marcado como conciliado.
8. Divergências (valor diferente, data diferente) → fica em "pendências" para tratamento manual.

### 4.9 Configurações tipadas — como o gestor ajusta sem dev

Tela de Configurações (Épico 13 entrega isso de forma sistemática):

- **Configurações da empresa:** nome fantasia, logo, CNPJ, endereço, dados fiscais.
- **Cobrança:** política padrão (lembretes, escalação, dias para bloqueio/suspensão/encerramento), juros, multa, multa de cancelamento, limite de fusão de pagamento parcial, validade de desbloqueio em confiança.
- **Comunicação:** templates de WhatsApp editáveis (com placeholders `{{cliente}}`, `{{valor}}`, `{{data}}`, `{{link_pix}}`), provider WhatsApp escolhido, modo de operação do agente (`ia-full` / `ia-eco` / `ia-zero` — Épico 11).
- **Integrações:** chaves de API por categoria (whatsapp_gateway, tracker, llm, ocr, storage). Cada categoria tem N providers; gestor escolhe qual está ativo.
- **Módulos:** ativa/desativa módulos verticais (Vehicles ativo por padrão).
- **Usuários e permissões:** convidar, atribuir perfil, revogar acesso.
- **Auditoria:** ver log de mutações sensíveis (filtrar por usuário, módulo, data).

Toda configuração tipada (não string solta): tem schema, tem validação, tem default, tem help text. Gestor não precisa de dev para mudar política de cobrança.

---

## 5. Regras de negócio explícitas

### 5.1 Estados do contrato (máquina de estados)

```
rascunho
   ↓ (gestor finaliza)
ativo
   ↓ (cliente atrasa >= limite_dias_suspensao)
suspenso ←──┐
   ↓        │ (cliente paga tudo atrasado)
   │   (pode voltar para ativo)
   ↓
encerrado_sem_pendencia    ← (cliente pagou tudo + devolveu OU cancelou em dia)
encerrado_com_pendencia    ← (motor automático D+60 OU gestor rescindiu com saldo)
encerrado_compra           ← (cliente pagou parcela 'opcao_compra')
rescindido                 ← (rescisão manual antecipada por motivo qualquer)
```

Transições proibidas (validar no backend):
- Não dá pra voltar de qualquer "encerrado_*" para `ativo`.
- Não dá pra ir de `rascunho` direto para `encerrado_*`.
- `suspenso` → `ativo` só se saldo devedor = 0.

### 5.2 Estados do título (instalment lifecycle — 7 estados)

```
em_aberto                       (gerado, aguardando pagamento)
   ↓ (data vencimento passou, cron diário)
vencido                         (atrasado, entra na régua de cobrança forte)
   ↓ (cliente paga, comprovante recebido)
pago_aguardando_verificacao     (aguarda OCR + match + conciliação)
   ↓ (validador aprova OU conciliação bate)
pago                            (IMUTÁVEL — não pode ser editado, só estornado)

# Variantes terminais:
pago_parcial    (parte foi paga, resto virou novo título OU fundiu — IMUTÁVEL)
renegociado     (substituído por renegociação — IMUTÁVEL)
cancelado       (terminal — contrato cancelado, parcela perdeu validade)
```

**Imutabilidade é dura.** Estados `pago`, `pago_parcial` e `renegociado` NÃO podem ser editados. Para corrigir, só via estorno explícito (que só Admin pode fazer e gera evento de auditoria).

### 5.3 Tipos de título (enum `tipo_titulo`)

| Tipo | Significado | Quando é criado |
|---|---|---|
| `parcela` | Mensalidade pelo uso do veículo | Gerado em massa na finalização do contrato |
| `opcao_compra` | Parcela única final; se paga, transfere propriedade | Gerado junto com parcelas, se contrato tem opção |
| `multa` | Multa por atraso ou cancelamento | Gerado pelo motor quando aplicável |
| `taxa` | Taxa extra (lavagem, dano leve, traslado) | Gerado manualmente pelo gestor |
| `ajuste` | Correção contábil (estorno, crédito, débito manual) | Gerado pelo gestor para ajustes |

### 5.4 Definição de saldo devedor (REPETIDO porque é crítico)

```sql
saldo_devedor_cliente = SUM(valor_titulo)
                        WHERE cliente_id = X
                          AND tipo = 'parcela'  -- ou outros tipos não-futuros
                          AND status = 'vencido'
```

NÃO inclui:
- Títulos `em_aberto` (futuros — uso futuro, não dívida).
- Títulos `pago`, `pago_parcial`, `cancelado`, `renegociado`.
- Títulos `opcao_compra` futuros.

### 5.5 Política de cobrança — parâmetros configuráveis

Tudo abaixo é tipado, editável pelo gestor sem dev:

| Parâmetro | Default | Significado |
|---|---|---|
| `lembrete_dias_antes` | `[3, 1]` | Em quantos dias ANTES do vencimento avisa |
| `enviar_no_vencimento` | `true` | Manda mensagem no D0 |
| `escalacao_pos_vencimento` | `[1, 3, 7, 15]` | Dias APÓS vencimento que envia escalação |
| `limite_dias_bloqueio` | `7` | A partir de quantos dias atrasado bloqueia o veículo |
| `limite_dias_suspensao` | `15` | A partir de quantos dias atrasado suspende contrato |
| `limite_dias_encerramento` | `60` | A partir de quantos dias atrasado encerra contrato |
| `auto_block` | `true` | Permite bloqueio sem aprovação humana se critérios atendidos |
| `score_minimo_para_bloqueio` | `0` | Só bloqueia se score < X (0 = bloqueia todos) |
| `juros_dia_percentual` | `0.1%` | Juros ao dia sobre títulos vencidos |
| `multa_percentual` | `2%` | Multa fixa sobre títulos vencidos |
| `multa_cancelamento_percentual` | `0%` | Multa por cancelamento antecipado |
| `limite_fusao_percentual` | `20%` | Se resto de pagamento parcial <= X, funde no próximo título |
| `validade_desbloqueio_confianca_dias` | `3` | Validade do desbloqueio em confiança |

### 5.6 Score do cliente

Cada cliente tem `score` (0-100) calculado por job diário. Fórmula simplificada:

- Base: 50.
- +N para cada pagamento em dia consecutivo.
- -N para cada atraso (peso proporcional a dias de atraso).
- -N para cada bloqueio sofrido.
- +N para tempo de relacionamento sem incidente.

Score é usado por:
- Agente IA (tom da mensagem).
- Política de cobrança (`score_minimo_para_bloqueio`).
- Risk dashboard.
- Decisão semi-automatizada de aprovar renegociação.

---

## 6. Multi-tenancy (Modelo A)

### 6.1 O que é Modelo A

**Um usuário pertence a UMA empresa só. Email único globalmente.**

Implicações:

- Quando admin convida pelo email, sistema valida que o email não existe em nenhuma outra empresa.
- Usuário não pode "trocar de empresa" sem ser convidado e ter usuário deletado da anterior.
- Cada request autenticado carrega `tenant_id` no JWT.
- Todas as queries usam `WHERE tenant_id = :current_tenant` (forçado via SQLAlchemy event listener — não confiar em dev lembrar).
- Migrações compartilhadas (schema único, particionado lógico por tenant_id).
- Backup é por tenant (export full por tenant_id quando necessário — LGPD).

### 6.2 Por que Modelo A e não Modelo B (multi-tenant + user pode estar em N empresas)

- Persona alvo (gestor de frota) raramente trabalha em duas frotas. Complexidade não se paga.
- Modelo B exige seletor de tenant em cada login, multiplicidade de permissões, complica audit.
- Se um dia algum cliente precisar Modelo B, é evolução possível (renomear `user.tenant_id` para tabela `user_tenant`).

### 6.3 Self-register desabilitado

Não tem "Crie sua conta grátis" na home. Por quê?

- Mercado-alvo é B2B com onboarding consultivo (gestor precisa ajuda pra configurar política, conectar WhatsApp, importar Excel).
- LGPD e KYC mais fáceis com onboarding controlado.
- V2 pode habilitar trial self-service quando tiver volume justificando.

### 6.4 Isolamento de dados

- Postgres: tabelas compartilhadas com `tenant_id` em todas (exceto `tenants`, `audit_log_global`, `system_settings`).
- Redis: keys prefixadas (`tenant:{id}:rate_limit:...`).
- MinIO: buckets prefixados (`tenant-{id}-attachments`, `tenant-{id}-receipts`).
- Workers: cada task carrega `tenant_id` no contexto, propaga em logs estruturados.

---

## 7. Glossário do domínio (PT-BR)

> Convenção: termos de domínio são SEMPRE PT-BR no código (sem inglês misturado). Frontend e backend compartilham vocabulário.

| Termo | Significado |
|---|---|
| **Ativo** | Bem que o gestor possui e aluga/financia. Para Vehicle Module, é um veículo. Genérico no core |
| **Cliente** | Pessoa física ou jurídica que aluga o ativo (motorista, no caso de frota) |
| **Contrato** | Acordo jurídico-comercial entre tenant e cliente, regendo uso de um ativo |
| **Título** | Cada cobrança individual gerada pelo contrato (parcela, opção de compra, multa, taxa, ajuste) |
| **Parcela** | Título tipo `parcela` — mensalidade pelo uso |
| **Opção de compra** | Título tipo `opcao_compra` — última parcela que, se paga, transfere propriedade |
| **Saldo devedor** | Soma dos títulos VENCIDOS e não pagos do cliente (NUNCA inclui futuros) |
| **Passivo inoperante** | Parcela vencida que ficou registrada após encerramento do contrato — dívida histórica |
| **Régua de cobrança** | Sequência de ações automatizadas que o motor executa por título (D-3, D-1, D0, D+1...) |
| **Motor de cobrança** | Conjunto de Celery tasks que orquestram régua de cobrança, bloqueios e mudanças de estado |
| **Política de cobrança** | Conjunto de parâmetros configuráveis que regem o motor (limites de dias, percentuais, escalação) |
| **Bloqueio em confiança** | Renomeação informal: o sistema chama de "desbloqueio em confiança" — cliente bloqueado é desbloqueado por X dias sob confiança que vai pagar |
| **Re-bloqueio automático** | Cron que verifica desbloqueios em confiança expirados e re-bloqueia se ainda em atraso |
| **Fusão de pagamento parcial** | Quando resto <= 20% do valor original, é somado ao próximo título em vez de criar título novo |
| **Score do cliente** | Indicador 0-100 de qualidade de pagador, calculado por job diário |
| **Conciliação bancária** | Processo de bater lançamentos do extrato bancário com títulos `pago_aguardando_verificacao` |
| **Estorno de baixa** | Desfazer um pagamento marcado como `pago`. Só Admin. Gera evento de auditoria |
| **Tenant** | Empresa cliente do SaaS (1 tenant = 1 frota = N usuários) |
| **Asset Module** | Módulo vertical plugável (Vehicles é o primeiro). Implementa `IAssetModule` |
| **Hook de módulo** | Função que o módulo registra para reagir a eventos do core (ex.: `on_installment_overdue`) |
| **Domain Event** | Evento publicado pelo core (ex.: `InstallmentPaid`, `ContractCreated`) que módulos podem escutar |
| **Configuração tipada** | Parâmetro com schema, validação e default — editável na UI sem precisar de dev |
| **Comprovante** | Foto/PDF que o cliente manda pelo WhatsApp atestando que pagou |
| **OCR** | Extração de texto do comprovante (Tesseract padrão, LLM Vision em modo `ia-full`) |
| **Régua reativa** | Mudanças no contrato (postergar parcelas, dar desconto) reemitem títulos em aberto |
| **Token economy** | Sistema do Épico 11 que controla gasto de tokens LLM (modos full/eco/zero, auto-throttle) |

---

## 8. Decisões de produto e seus porquês

### 8.1 Por que rent-to-own e não aluguel puro

- Mercado-alvo (motoboy/motorista de app) majoritariamente quer "ser dono no fim". É commodity comercial.
- Sem rent-to-own o gestor perde 60% do mercado.
- Tecnicamente exige só 1 título extra (`opcao_compra`) e 1 estado novo (`encerrado_compra`).

### 8.2 Por que self-register desabilitado em V1

- Onboarding consultivo (configurar política, conectar WhatsApp, importar Excel) não é self-service.
- Mercado pequeno e identificado — vendas é outbound, não inbound.
- Vai habilitar quando volume justificar trial automatizado.

### 8.3 Por que motor em Python (Celery) e não em outra coisa

- Mesmo stack que o resto do backend (FastAPI/SQLAlchemy/Postgres) — zero context switch.
- Celery + Redis é maduro, observável, deploy simples.
- Volume previsto (milhares de títulos/dia por tenant) está bem dentro do que Celery aguenta.
- Alternativas (Temporal, Hatchet, Inngest) seriam overkill para complexidade atual.

### 8.4 Por que WhatsApp como canal único do cliente final

- 100% dos motoristas usam WhatsApp diariamente.
- Email tem taxa de abertura <5% na persona; SMS é R$ 0,10 cada vs WhatsApp grátis (no plano pessoal) ou R$ 0,01 (gateway BR).
- Portal web/app para cliente final = produto inteiro, não se paga.

### 8.5 Por que pagamento Pix em confiança + OCR e não gateway

- Asaas/PagSeguro cobram R$ 1-2 por Pix. Tenant médio = 200 títulos/mês = R$ 400/mês só em taxa, esmaga margem do SaaS.
- Pix direto + OCR + conciliação bancária diferida = custo marginal zero.
- Trade-off: tem fraude residual (comprovante falso). Mitigado por:
  - OCR validation (extrai valor e data, compara com título).
  - Conciliação bancária semanal pega divergências.
  - Score do cliente caia rápido com fraude detectada.
- Gateway segue como plugin opcional (gestor pode habilitar se preferir conveniência > custo).

### 8.6 Por que Modelo A multi-tenancy

- Ver 6.2. Simplifica auth, audit, query, UI.
- Reversível (migração para Modelo B é factível) se demanda real aparecer.

### 8.7 Por que arquitetura hexagonal + ports (e não MVC tradicional)

- Integrações externas mudam (WhatsApp provider, tracker provider, LLM provider, OCR provider). Hex isola troca atrás de Port.
- Testes ficam triviais (mock do port).
- Asset Abstraction Layer é literalmente uma port (`IAssetModule`) — segue o mesmo paradigma.

### 8.8 Por que Asset Abstraction Layer (não hardcoded para veículo)

- Aposta: depois de validar Vehicle, queremos plugar Imóvel/Equipamento/Assinatura sem reescrever core.
- Custo de fazer agora (1 sprint extra) muito menor que custo de refatorar depois (1 quarter).
- Stripe/Notion/Linear seguem padrão similar (extensibilidade via interface plugável).
- Risco: over-engineering. Mitigado mantendo Vehicle como first-class durante MVP e só refatorando outros módulos quando comprar mercado.

### 8.9 Por que Signals + zero NgRx no frontend

- Stack moderno Angular 21 oferece Signals + `resource()` como reatividade de primeira classe.
- NgRx tem boilerplate enorme (actions, reducers, effects, selectors) para 80% de casos onde signal resolve.
- Quando precisar de side effects complexos, usar `effect()` ou serviço dedicado.
- 1 dev solo no frontend não pode arcar com tax do NgRx.

### 8.10 Por que tudo é Wizard multi-step (não modal/drawer)

- Wizard reduz cognitiva por step (5 campos vs 30).
- Mobile-first: drawer lateral só funciona em desktop; wizard funciona em qualquer tela.
- Padrão consistente: gestor aprende uma vez, aplica em todos os CRUDs.
- Validação por step evita "submitar e ver 17 erros".

---

## 9. Roadmap atual (Épicos 10 a 13)

### 9.1 Épico 10 — Motor de Recorrência e Cobrança Automatizada

**Status:** em progresso (10-1 next, 7 stories ready-for-dev).

**O que entrega:**
- Motor Celery completo com 32 tasks orquestradas.
- 3 camadas de idempotência (chave única + Redis lock + status_check).
- Coordinator + fan-out em lotes de 50.
- Régua configurável por política de cobrança.
- Hooks para módulo vertical (bloqueio GPS via Vehicle).
- Reemissão de títulos em alteração contratual.
- Pagamento parcial com fusão automática.

**Valor de negócio:** zera o trabalho manual de cobrança. Gestor não precisa lembrar de avisar D-3, D+7. Sistema faz sozinho, registra tudo, escala quando precisa, suspende contrato sozinho.

### 9.2 Épico 11 — WhatsApp Token Economy

**Status:** backlog (vem depois do Épico 10).

**O que entrega:**
- 3 modos de operação: `ia-full`, `ia-eco`, `ia-zero`.
- Auto-throttle por budget (75% → eco, 95% → zero).
- Stack regex/intent homegrown (flashtext + rapidfuzz + re).
- Menu interativo WhatsApp (botões + lista).
- Dedupe de comprovante (pHash + txn_id).
- Audio handling per mode (transcribe ou deflect).
- Manager learning (gestor salva resposta como regra).

**Valor de negócio:** controla custo de LLM (token é caro, escala mal). Em modo `ia-zero` o sistema operacional continua funcionando 100% determinístico, sem nenhum custo de IA. Gestor escolhe o trade-off.

### 9.3 Épico 12 — Schema PT-BR + Multi-Tenancy

**Status:** 12-1/2/3 done; 12-4 a 12-8 ready.

**O que entrega:**
- Renomeação completa de schema para PT-BR (clientes, contratos, titulos, etc.).
- Coluna `tenant_id` em todas as tabelas operacionais.
- Event listener SQLAlchemy que injeta filtro `tenant_id` automaticamente.
- Convite por email + onboarding de novos usuários.
- Isolamento de buckets MinIO e keys Redis por tenant.
- Audit log particionado por tenant.

**Valor de negócio:** habilita o produto a vender para mais de uma empresa. É pré-requisito para escalar.

### 9.4 Épico 13 — Motor Financeiro Central

**Status:** 15 stories backlog (planejado).

**O que entrega:**
- Novos motores: motor de juros e multas, motor de renegociação, motor de devolução de ativo, motor de transferência de propriedade.
- Configurações tipadas: schema completo de parametrização, UI de configurações com help text e validação.
- Herói financeiro: dashboard executivo top-of-app mostrando 4 KPIs críticos do tenant em tempo real.
- Desbloqueio em confiança com expiração: implementa fluxo completo (UI + cron + audit).
- Override FIPE: gestor pode sobrescrever valor de mercado manualmente (FIPE vira referência, não verdade absoluta).
- Tela de configurações reorganizada: sidebar overlay, agrupada por área (Cobrança / Comunicação / Integrações / Módulos).

**Valor de negócio:** consolida e profissionaliza tudo que ficou disperso. Gestor passa a ter controle fino e visão executiva. Sistema vira "configurável" em vez de "customizável só com dev".

### 9.5 O que vem depois (visão V2+)

- **Épico 14 (este documento):** Manual do desenvolvedor (documentação).
- **Landing page + self-register:** quando time comercial validar mercado outbound.
- **Módulos verticais novos:** Properties (imóveis), Services (assinaturas SaaS B2B), Equipamentos.
- **App mobile do gestor:** PWA ou Capacitor.
- **Open Banking nativo:** pagamento direto pelo sistema (gestor cobra a partir da UI sem depender de WhatsApp).
- **Plano de carreira financeiro do veículo:** modelo preditivo de ROI baseado em histórico real.

---

## Apêndice — Como navegar o código sabendo este manual

| Quer entender... | Vá para... |
|---|---|
| Estados do contrato | `api/domain/contracts/state_machine.py` |
| Estados do título | `api/domain/titulos/state_machine.py` |
| Cálculo de saldo devedor | `api/application/services/saldo_devedor_service.py` |
| Motor de cobrança | `api/workers/cobranca/` (coordinator + 32 tasks) |
| Política de cobrança | `api/domain/cobranca/politica.py` + `api/infrastructure/db/models/politica_cobranca.py` |
| Asset Abstraction | `api/domain/assets/ports/iassetmodule.py` + `api/modules/vehicles/` |
| Multi-tenant filter | `api/infrastructure/db/tenant_filter.py` (SQLAlchemy event listener) |
| Wizard de contrato | `web/src/app/features/contracts/wizard/` |
| Inbox WhatsApp | `web/src/app/features/inbox/` + `api/application/services/inbox_service.py` |
| Configurações tipadas | `api/domain/settings/typed_config.py` + `web/src/app/features/settings/` |

---

**Fim do manual.**

Se você leu até aqui e ainda tem dúvida sobre o NEGÓCIO (não sobre o código), pergunte para John (PM). Se a dúvida é técnica, pergunte para Winston (Architect) ou Amelia (Dev). Se é UX, pergunte para Sally.

Bom código.
