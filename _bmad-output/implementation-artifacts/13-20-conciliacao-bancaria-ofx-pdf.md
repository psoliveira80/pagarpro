---
epic: 13
story: 20
title: "Conciliação Bancária com UX Visual (OFX + PDF + CSV)"
type: "UX + Domínio Financeiro + Backend"
status: ready-for-dev
priority: high
depends_on: "13.9, 13.19"
authored_by: "Amelia (dev) + Sally (UX)"
created_at: "2026-05-27"
---

# Story 13.20: Conciliação Bancária Visual

## História de Usuário

**Como** gestor da empresa,
**eu quero** importar extrato bancário (OFX, PDF ou CSV) e conciliar visualmente com os títulos em aberto,
**para que** eu confirme em minutos os pagamentos recebidos no mês — mesmo quando o cliente não enviou comprovante.

## Contexto

Complementa o fluxo de Story 13.19 (comprovante em tempo real). Conciliação é **trabalho retroativo** do gestor, tipicamente mensal ou bi-mensal:

1. Gestor faz download do extrato no app do banco.
2. Importa no sistema (OFX = padrão ideal, PDF/CSV como fallback).
3. Sistema confronta cada transação de crédito do extrato contra títulos em aberto.
4. UX mostra matches com 3 cores (verde ≥ 95%, amarelo 70–95%, vermelho < 70%).
5. Gestor revisa, aprova em lote ou ajusta individualmente.

## Critérios de Aceite

1. **Importação de OFX** (caminho ideal):
   - Lib `ofxparse`. Faz parsing direto do XML.
   - Endpoint `POST /api/v1/conciliacao/importar-ofx` (admin/financeiro).
   - Extrai todas as transações de crédito (deposit, transfer, pix).
   - Cria sessão de conciliação (`sessoes_conciliacao` — já existe).

2. **Importação de PDF textual** (PDF gerado pelo banco):
   - Lib `pdfplumber` para extração direta de texto.
   - Detecta layout do banco e usa template específico (mesmos 8 bancos da Story 13.19).
   - Endpoint `POST /api/v1/conciliacao/importar-pdf`.

3. **Importação de PDF escaneado**:
   - Reusa pipeline OCR da Story 13.19 (PaddleOCR + OpenCV).
   - Detecta automaticamente se PDF é nativo ou escaneado (tenta extração textual; se < 50 caracteres por página, é escaneado).

4. **Importação de CSV/XLSX** (bonus):
   - Lib `pandas`. UX mostra preview das primeiras 10 linhas e pede mapeamento de colunas (Data, Valor, Descrição).
   - Persiste o mapeamento por banco para reutilização em próximas importações.

5. **Matching automático** com títulos em aberto:
   - **Score 100% (verde forte):** valor exato + data ±2 dias + (descrição contém CPF/CNPJ do cliente OU nome do cliente).
   - **Score 95% (verde):** valor exato + data ±2 dias.
   - **Score 80% (amarelo):** valor exato sem outros campos batendo.
   - **Score 70% (amarelo claro):** valor ±R$ 1 + data ±5 dias.
   - **Score < 70% (sem match):** vai pra "não conciliadas — revisar".

6. **UX da tela** (`/sistema/financeiro/conciliacao/nova`):

   - Layout 2 colunas (responsivo: empilha no mobile).
   - **Esquerda — extrato:** lista de transações importadas com filtros (data, valor, status).
   - **Direita — títulos em aberto:** lista de títulos da empresa não-pagos.
   - Linhas conectadas por linha visual (SVG) entre match sugerido. Cor da linha indica score.
   - Cada match sugerido tem botão `[✓ Conciliar]` que dispara `ServicoTituloPago.registrar_pagamento(...)`.
   - Botão massivo: `[Aplicar todos os matches verdes (≥ 95%)]` com confirmação. Aplica em lote.
   - Cada match aplicado fica registrado e pode ser **desfeito** em até 30 dias (libera o título, marca a transação como "não conciliada novamente").
   - Transações sem match → grupo "Não identificadas" com ações: `[Marcar como receita avulsa]` / `[Marcar como despesa]` / `[Ignorar]`.
   - Histórico de sessões em `/sistema/financeiro/conciliacao/historico`.

7. **Estado da sessão de conciliação:**
   - Sessão pode ser **rascunho** (pausada, gestor volta depois) ou **finalizada** (não permite mais alterações sem auditoria).
   - Auto-save: cada match aplicado salva o estado da sessão imediatamente.

8. **Cross-check com comprovantes da Story 13.19:**
   - Se um pagamento já foi homologado via comprovante (Story 13.19) e agora aparece no extrato, o sistema **avisa**: "Este pagamento já foi conciliado via comprovante em DD/MM" e oferece marcar a transação do extrato como `ja_conciliada_via_comprovante` (não duplica).

9. **Persistência:**
   - Reusa tabelas `conta_bancaria.sessoes_conciliacao` e adjacentes (já existem da Story 5.x — Pablo confirme se é o caso, senão criar).
   - Nova tabela `conta_bancaria.matches_conciliacao` (transacao_id, titulo_id, score, aplicado_por_id, aplicado_em, desfeito_em, motivo_desfazer).

10. **Testes:**
    - OFX sintético com 5 transações → import + match com 3 títulos.
    - PDF nativo do Itaú (1 exemplo real) → extrai + match correto.
    - CSV genérico com mapeamento de colunas → import.
    - Match aplicado dispara `ServicoTituloPago` corretamente.
    - Desfazer match em até 30 dias libera título.
    - Conflito com comprovante já homologado → aviso e não-duplicação.

## Contexto Técnico

### Dependências novas

- `ofxparse` (~30KB, parsing XML OFX).
- `pdfplumber` (já vem da Story 13.19).
- `pandas` (já está no projeto se não estiver; ~30MB) — para CSV/XLSX.
- Pipeline OCR reusa o que foi feito em 13.19.

### Componentes Angular (frontend)

```
src/frontend/src/app/features/financeiro/conciliacao-visual/
├── conciliacao-visual.component.ts        # tela principal
├── conciliacao-visual.component.html
├── conciliacao-visual.component.css
├── importar-extrato-modal/                # wizard de importação
├── match-card/                            # card individual de transação
├── titulo-card/                           # card de título em aberto
└── linha-conexao-svg/                     # SVG da linha de match visual
```

### Sally UX (design notes)

- Cores via CSS variables (sem hardcoded).
- Match verde (`var(--success)`), amarelo (`var(--warning)`), vermelho (`var(--danger)`).
- Animação suave (200ms) quando match é aplicado — card sai da esquerda e título "afunda" na direita.
- Mobile: empilha (extrato em cima, títulos embaixo), com lista de matches no meio.
- Tooltip nos cards: mostra raw da transação ou título (debug do gestor).
- Atalhos de teclado: `Enter` aplica match focado, `Esc` cancela, `Tab` navega.
- Acessibilidade: roles ARIA, navegação por teclado, contraste WCAG AA.

## Checklist do Dev

- [ ] Story 13.19 concluída (pipeline OCR + 13.9 funcionando).
- [ ] Lib `ofxparse` adicionada.
- [ ] Endpoints de importação (OFX/PDF/CSV) funcionais.
- [ ] Matching automático com 4 tiers de score.
- [ ] UI de 2 colunas responsiva mobile-first.
- [ ] Linha SVG conectando matches.
- [ ] Aplicar lote (verdes) com 1 clique.
- [ ] Desfazer em 30 dias.
- [ ] Cross-check com comprovantes da Story 13.19.
- [ ] Histórico de sessões.

## Notas

- Sally UX é **co-autora** desta story — UX visual é diferencial competitivo.
- Reusa quase tudo do backend de 13.9 e 13.19. O esforço aqui é majoritariamente frontend + os importadores.
- Considerar **export** da sessão de conciliação em PDF (relatório auditável) — pode ser sub-story se virar grande.
