# Wizard de Cadastro de Contrato — Detalhamento UX

> **Autor:** John (PM/BMad) com input direto do Pablo (PO).
> **Data:** 2026-05-26 (sessão pós smoke-test do frontend).
> **Status:** Especificação aprovada pelo PO — pronto para refinar em story.
> **Documentos relacionados:** [PRD § Contratos (CTR)](../_bmad-output/planning-artifacts/PRD.md), [ARCHITECTURE § Máquina de Estados do Contrato](../_bmad-output/planning-artifacts/ARCHITECTURE.md), [Glossário PT-BR](glossario-ptbr.md).
> **Implementação atual:** `src/frontend/src/app/features/contratos/contrato-wizard/`.

---

## 1. Visão Geral

Wizard de **4 telas (steps)** para criação de contrato de aluguel com opção de compra. O resultado dispara a geração de títulos a receber, que alimenta o **Motor de Cobrança Autônomo** (Epic 13).

> **Princípio orientador:** "essa parte é muito importante porque é quem vai orientar o worker de geração e cobrança dos títulos" — Pablo.
> Cada campo dessa tela tem que produzir dado **consumível por worker** sem ambiguidade — nada de string livre.

| Tela | Título | Conteúdo |
|---|---|---|
| 1 | Cliente e Ativo | Já está OK. Não muda. |
| 2 | Plano de Parcelas | **Reformular** — todos os campos novos abaixo. |
| 3 | Espelho de Parcelas | Lista visual de todas as parcelas geradas. |
| 4 | Revisão | Resumo executivo do contrato. |

---

## 2. Tela 1 — Cliente e Ativo (sem mudança)

Mantém o estado atual: dois `SearchableSelectComponent` (Cliente, Veículo). Validação: ambos preenchidos para avançar.

---

## 3. Tela 2 — Plano de Parcelas (NOVA estrutura)

### 3.1 Campos

| # | Campo | Tipo | Validação | Observação |
|---|---|---|---|---|
| 1 | Data de vencimento da primeira parcela | `<input type="date">` | obrigatório, futuro ou hoje | base do cronograma |
| 2 | Valor da parcela | `<app-input-moeda>` | obrigatório, > 0 | máscara R$ (padrão da casa) |
| 3 | Quantidade de parcelas | `<input type="number">` com setas | obrigatório, inteiro ≥ 1 | inteiro — setas são aceitáveis |
| 4 | Intervalo entre parcelas | `<app-select>` (CustomSelect) | obrigatório | dropdown com tipos — ver § 3.2 |
| 5 | Multa por atraso (%) | `<input>` decimal 2 casas | opcional, ≥ 0 | NÃO é monetário; padrão de máscara igual ao input-moeda, mas sem prefixo "R$" (ver § 3.4) |
| 6 | Juros por atraso (% a.m.) | `<input>` decimal 2 casas | opcional, ≥ 0 | mesma máscara da multa |
| 7 | Valor da parcela final (opção de compra) | `<app-input-moeda>` | opcional, ≥ 0 | parcela "balão" para retirada do veículo |
| 8 | Aplicar índice de correção? | `<toggle>` sim/não | obrigatório | quando "sim", abre sub-campo (§ 3.3) |

> **Convenção:** todos os campos obrigatórios têm asterisco vermelho `<span class="text-[var(--danger)]">*</span>` (padrão já documentado).

### 3.2 Campo 4 — Intervalo entre parcelas (regras condicionais)

O dropdown abre opções, e cada escolha **revela um sub-campo dinâmico**. Importante: essa estrutura precisa ser **extensível** para acomodar tipos futuros sem refatoração — Pablo: *"depois podem surgir novas formas de pagamento"*.

| Tipo selecionado | Slug (backend) | Sub-campo adicional | Exemplo final |
|---|---|---|---|
| Semanal — escolher dia da semana | `semanal` | Dia da semana (Seg, Ter, Qua, Qui, Sex, Sáb, Dom) | "Toda quarta-feira" |
| A cada N dias | `personalizado_dias` | Número de dias (inteiro ≥ 1) | "A cada 15 dias" |
| Mensal — escolher dia do mês | `mensal` | Dia do mês (1..31, com fallback para último dia útil em meses com menos dias) | "Todo dia 15" |

**Para extensibilidade futura** (já preparar arquitetura, não precisa UI agora):
- Quinzenal pode ser modelado como `personalizado_dias` + 15 ou como tipo próprio `quinzenal`.
- Cobrança diária (`diaria`) — pode entrar depois com 0 sub-campos.
- Cobrança em datas específicas (`datas_customizadas`) — já existe campo `datas_customizadas: list[date]` no backend para isso.

**Esquema técnico:**
```typescript
type TipoIntervalo = 'semanal' | 'personalizado_dias' | 'mensal' | /* extensível */ string;

interface PlanoParcelas {
  tipo_intervalo: TipoIntervalo;
  dia_semana?: 0..6;      // só para tipo=semanal (0=domingo, 6=sábado)
  intervalo_dias?: number;  // só para tipo=personalizado_dias
  dia_mes?: 1..31;          // só para tipo=mensal
}
```

### 3.3 Campo 8 — Toggle índice de correção

**Comportamento:**

- Estado padrão: **desligado**.
- Quando ligado: aparece **outro `<app-select>`** logo abaixo, listando **apenas índices integrados e testados** (vem da tabela `config.credenciais_integracao` com `categoria='correction_index'` e `ativo=true`).
- Lista atual (BCBCorrectionAdapter): IGPM, IPCA, INPC.
- Quando o usuário escolhe um índice, o **espelho de parcelas (Tela 3)** mostra cada parcela já corrigida; o **valor total na Tela 4** soma os valores corrigidos.
- Se nenhuma integração de índice estiver ativa, o toggle aparece **desabilitado** com mensagem `"Nenhum índice configurado — ative em Configurações > Integrações > Índice de Correção"`.

**Cálculo da correção:**
- Aplicação: a partir da **2ª parcela** (regra atual do `gerar_titulos_mensais.py`).
- Taxa: snapshot do índice no momento da geração de cada título (não fixar no contrato).
- Frequência: por geração (mensal/semanal, conforme `tipo_intervalo`).

### 3.4 Padrão de input decimal para multa/juros (% por atraso)

Pablo: *"campo não é monetário, mas é decimal, segue o mesmo padrão com 2 casas decimais"*.

**Especificação:**
- Componente: pode usar `<app-input-moeda>` com `prefix=""` e label próprio `"% a.m."`, ou criar `<app-input-decimal-pct>` se preferir desacoplar.
- Comportamento: digita "275" → mostra "2,75"; alinhado à direita; sem setas up/down.
- Backend: enviar como `Decimal` (string `"2.75"`).

**Recomendação técnica:** criar `<app-input-decimal>` genérico com `prefix` opcional e `suffix` opcional (ex: "%"). `<app-input-moeda>` vira caso particular (prefix="R$"). Reduz duplicação.

### 3.5 Campo 7 — Parcela final (opção de compra)

Pablo: *"Valor da parcela final para retirada do veículo"*.

Modelagem (alinha com PRD-Modelo de negócio: rent-to-own):
- Campo `valor_parcela_final` no contrato (decimal opcional).
- Quando preenchido, gera **N+1 títulos** no cronograma: N parcelas regulares + 1 título extra com `tipo='opcao_compra'` na data seguinte à última parcela.
- Quando vazio ou 0, gera apenas N parcelas regulares.

> **Nota:** O PRD já cita `tipo_titulo` enum (`parcela`, `opcao_compra`, `multa`, `taxa`, `ajuste`) em `1.3 Histórico de Mudanças`. Isso casa perfeitamente.

---

## 4. Tela 3 — Espelho de Parcelas

**Comportamento:** chamada ao backend `POST /api/v1/contracts/preview-schedule` com payload completo (incluindo `indice_correcao` se ligado). Mostra **lista completa** das parcelas geradas.

**Colunas:**
1. Nº (sequência, 1..N+1)
2. Data de vencimento (`dd/mm/yyyy`)
3. Valor previsto (R$) — já com correção aplicada se o toggle estiver ligado
4. Tipo (`Parcela` ou `Opção de Compra` para a última)
5. (futuro) Coluna "Juros aplicados" — se índice ativo, mostrar % aplicado naquela parcela

**Sumário no rodapé da tabela:**
- Total: soma de todos os valores
- Sem correção: total original (se houver toggle)
- Com correção: total corrigido (se aplicável)

**Sem ações nessa tela** — apenas preview. Voltar e Avançar.

---

## 5. Tela 4 — Revisão

Resumo executivo organizado em cards/blocos:

### 5.1 Cliente e Ativo
- **Cliente:** nome completo + CPF/CNPJ
- **Veículo:** placa, marca, modelo, ano

### 5.2 Vigência
- **Data de início:** data da 1ª parcela
- **Data de término:** data da última parcela (ou da opção de compra, se houver)
- **Período total:** "X meses" ou "Y dias"

### 5.3 Plano de Cobrança
- Linha principal: `80 × R$ 800,00 = R$ 64.000,00` (formato sugerido pelo Pablo)
- Se houver parcela final: linha extra `+ 1 × R$ 20.000,00 (opção de compra)`
- **Total geral:** R$ 84.000,00 (com correção aplicada se toggle ligado)
- Intervalo: "Mensal, dia 15" / "Semanal, quarta-feira" / "A cada 15 dias"
- Multa/juros: "Multa 2,00% · Juros 1,00% a.m." (se preenchidos)
- Índice de correção: "Aplicado: IGPM" (se ligado) ou "Sem correção"

### 5.4 Botão final
- **"Salvar como rascunho"** (default) — contrato fica `status='rascunho'`, não gera títulos.
- **"Salvar e ativar"** (opcional, toggle) — contrato vai pra `status='vigente'` e dispara geração dos títulos imediatamente.

---

## 6. Mudanças necessárias no PRD

### 6.1 FR-CORE-CTR-2 (Construtor visual de parcelamento) — **expandir**
Adicionar texto:
> O construtor de parcelamento opera com **valor por parcela + quantidade** (não valor total), e permite definir:
> - Tipo de intervalo: `semanal` (com dia da semana), `mensal` (com dia do mês), `personalizado_dias` (com N dias). Arquitetura extensível para tipos futuros.
> - Multa e juros por atraso (decimais, % a.m.).
> - Valor de parcela final ("opção de compra") opcional.
> - Toggle de aplicação de índice de correção, vinculado a `IIndiceCorrecao` ativo nas integrações.

### 6.2 FR-CORE-CTR-3 (Geração de títulos) — **adicionar**
> Quando contrato é finalizado com `valor_parcela_final > 0`, gera N+1 títulos: N do tipo `parcela`, 1 do tipo `opcao_compra` na data seguinte à última parcela.

### 6.3 FR-CORE-CR (novo) — Multa e juros por atraso
> Multa e juros são **fields do contrato**, não constantes globais. Cálculo de valor atualizado de título em atraso usa `contrato.multa_atraso_pct` e `contrato.juros_atraso_pct`.

### 6.4 FR-INT (novo) — Índices de correção plugáveis
> Listagem dinâmica de índices de correção segue o padrão de `IntegrationCredentials` (categoria=`correction_index`). Apenas providers `ativo=true` aparecem no wizard.

---

## 7. Gaps vs implementação atual

### 7.1 Frontend — `contrato-wizard.component.ts`

| Tela | Gap |
|---|---|
| **Tela 2** | Hoje pede `startDate`, `endDate`, `totalValue`, `notes`. Precisa **substituir** por: `firstInstallmentDate`, `installmentAmount`, `numInstallments` (já existe), `intervalType` + sub-campo, `lateFinePct`, `lateInterestPct`, `finalInstallmentAmount`, `correctionEnabled` + `correctionIndex`. |
| **Tela 3** | Hoje chama `previewSchedule` com `valor_total + quantidade_parcelas + data_inicio` apenas. Precisa passar todos os novos parâmetros. |
| **Tela 4** | Hoje mostra `totalValue`, `notes`, `activateAfterCreate`. Precisa rederizar resumo com formato `N × R$ X,XX = R$ Y,YY`. |
| Geral | Função `loadSchedulePreview` precisa enviar payload completo. Função `submit` precisa enviar payload completo. |

### 7.2 Backend — schemas e modelo

| Item | Estado | Ação |
|---|---|---|
| `ContratoCreate.valor_total` | existe | Mantém. Frontend calcula: `valor_total = valor_parcela * quantidade_parcelas` (e soma `valor_parcela_final` se houver). |
| `ContratoCreate.valor_parcela` | NÃO existe | **Adicionar** (Decimal, opcional). Útil para reconstituição/auditoria. |
| `ContratoCreate.valor_parcela_final` | NÃO existe | **Adicionar** (Decimal, opcional). |
| `ContratoCreate.tipo_intervalo` | tem `periodicidade: str` | **Renomear** OU criar `tipo_intervalo` separado. Recomenda renomear `periodicidade` → `tipo_intervalo` (mais expressivo) com migration de dados. |
| `ContratoCreate.dia_semana`, `dia_mes`, `intervalo_dias` | NÃO existem | **Adicionar** todos como `Optional`. Validação Pydantic: só preencher conforme `tipo_intervalo`. |
| `ContratoCreate.multa_atraso_pct`, `juros_atraso_pct` | NÃO existem (existe `taxa_juros` mas é juros do contrato, não de atraso) | **Adicionar** como campos separados. Manter `taxa_juros` para uso atual. |
| `Contrato.indice_correcao` (model) | existe como string nullable | OK. **Adicionar no Pydantic `ContratoCreate`** (hoje só está no modelo, não no schema). |
| `PreviewPlanilhaRequest` | aceita `periodicidade, taxa_juros, metodo, datas_customizadas` | **Adicionar** mesmos novos campos para preview funcionar com correção. |

### 7.3 Worker `gerar_titulos_mensais.py`
- Hoje suporta `mensal`, `semanal`, `quinzenal` (em `gerar_despesas_recorrentes.py`). 
- **Adicionar:** `personalizado_dias` com `intervalo_dias` em vez de assumir mês.
- **Validar:** `dia_mes` em meses com menos dias (ex: 31 em fevereiro → último dia útil).
- **Adicionar:** geração de título extra com `tipo='opcao_compra'` quando contrato tem `valor_parcela_final`.

### 7.4 Migration
- Adicionar colunas em `contrato.contratos`: `valor_parcela`, `valor_parcela_final`, `tipo_intervalo`, `dia_semana`, `dia_mes`, `intervalo_dias`, `multa_atraso_pct`, `juros_atraso_pct`.
- Renomear `periodicidade` → `tipo_intervalo` (com data migration: valores existentes ficam como estão, são compatíveis).

---

## 8. Recomendação de Story

**Criar nova story 13-X** (Epic 13 — Motor Financeiro Central):

| ID sugerido | Título | Justificativa |
|---|---|---|
| **13-16** | Wizard de Contrato — Plano de Parcelas Detalhado | Epic 13 é Motor Financeiro Central. Esta evolução do wizard está alinhada com Stories 13-2 (máquina de estados), 13-3 (tipo título opção compra) e 13-15 (tela de configurações motor) que já estão no backlog. |

**Por que NÃO refinar a Story 3-3 (Construtor de Parcelamento Frontend, já `done`):**
- Stories `done` não são reescritas (regra Pablo).
- Os requisitos novos vão além do escopo original (toggle de correção, parcela final).

**Pré-requisito da Story 13-16:** Stories 13-3 (tipo_titulo enum) e 13-4 (sistema_configuracoes) precisam estar concluídas ou rodando em paralelo — afetam o mesmo modelo.

**Subdivisão recomendada da 13-16:**
- **13-16-a:** Migration + schemas + repositórios (backend)
- **13-16-b:** Endpoint `preview-schedule` estendido (backend)
- **13-16-c:** Wizard frontend tela 2 (campos + condicionais)
- **13-16-d:** Wizard frontend telas 3 e 4 (preview + revisão)
- **13-16-e:** Worker de geração: suporte a `personalizado_dias` + `opcao_compra`

---

## 9. Próximos passos

1. **Pablo aprovar** este detalhamento (especialmente § 7.2 — mudanças no schema do contrato).
2. **Criar Story 13-16** em `_bmad-output/implementation-artifacts/13-16-wizard-contrato-plano-parcelas.md` com as subdivisões acima como tasks.
3. **Atualizar PRD** com os ajustes de § 6 (Pablo pode pedir o `bmad-edit-prd` se quiser ritual completo).
4. **Sequenciar:** 13-16 entra depois de 13-3 (tipo título) e 13-4 (configurações) — esses são pré-req.

---

**Validado contra glossário PT-BR.** Termos consagrados (toggle, wizard, preview, dropdown) mantidos em inglês conforme regra. Identificadores de schema/Pydantic em snake_case PT-BR.
