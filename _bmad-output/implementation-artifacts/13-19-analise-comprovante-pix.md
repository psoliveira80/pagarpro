---
epic: 13
story: 19
title: "Análise de Comprovante PIX (pipeline multi-camada nativo, sem IA por padrão)"
type: "Infraestrutura + Domínio Financeiro + ML"
status: ready-for-dev
priority: critical
depends_on: "13.4, 13.9"
authored_by: "Amelia (dev)"
created_at: "2026-05-27"
---

# Story 13.19: Análise de Comprovante PIX

## História de Usuário

**Como** sistema financeiro,
**eu quero** analisar automaticamente comprovantes de PIX enviados pelos clientes (imagem ou PDF) e atribuir score de confiança,
**para que** o gestor homologue pagamentos com 1 clique sem desconfiar — e seja alertado quando algo parece suspeito.

## Contexto

Cliente recebe código PIX, paga no banco dele, envia comprovante (geralmente print do app via WhatsApp). Esta story constrói o **pipeline nativo** que:

1. Identifica o pagamento (valor, data, beneficiário, ID).
2. Faz match com títulos em aberto do contrato.
3. Atribui `score_confianca` (0.0 a 1.0).
4. Persiste o comprovante associado ao título e marca como `pago_aguardando_verificacao`.
5. Gera notificação para o gestor quando confiança baixa.

**Decisão de produto:** o gestor SEMPRE homologa manualmente (1 clique). Score alto = clique rápido sem revisão; score baixo = revisão detalhada.

**IA como opção plugável** (não padrão) — configuração por tenant em `configuracoes_sistema`:
- `modo_analise = 'nativo'` (default) — pipeline livre.
- `modo_analise = 'ia_como_reforco'` — chama IA Vision quando confiança nativa < threshold.
- `modo_analise = 'ia_primario'` — pula direto pra IA (máxima precisão, custo).

## Critérios de Aceite

1. Endpoint `POST /api/v1/comprovantes/analisar` (autenticado): recebe `multipart/form-data` com arquivo (imagem ou PDF) + `titulo_id` (opcional, se cliente já vincula via WhatsApp). Retorna `ResultadoAnaliseComprovante` em < 5s para imagens típicas.

2. **Pipeline em camadas** (ordem decrescente de eficiência, para no primeiro match alto):

   - **Camada 1 — BR Code (QR Code PIX):** usa `pyzbar`. Decodifica payload EMV BR Code do BACEN. **Confiança base 0.95** quando decodifica com sucesso.
   - **Camada 2 — PDF textual:** se entrada é PDF não-escaneado, usa `pdfplumber` (extração direta de texto). Confiança base 0.85.
   - **Camada 3 — OCR (PaddleOCR):** pré-processamento via OpenCV (deskew, denoise, threshold adaptativo, upscale 2x). Confiança base 0.65.

3. **Extração universal de entidades** (regex robusta sobre o texto, funciona em qualquer banco porque PIX é padronizado pelo BACEN):
   - **Valor monetário**: `R\$\s*[\d\.\,]+` — pega o maior valor (geralmente é a transação).
   - **Data + hora**: `\d{2}/\d{2}/\d{4}.{0,10}\d{2}:\d{2}` — mais recente.
   - **CPF**: `\d{3}\.\d{3}\.\d{3}-\d{2}` (com validação dos dígitos).
   - **CNPJ**: `\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}` (com validação dos dígitos).
   - **E2E ID (end-to-end PIX padrão BACEN)**: `E[0-9A-Z]{31}`.
   - **Chave PIX**: detecta tipo (CPF / CNPJ / e-mail / celular `+55…` / aleatória UUID-like).
   - **Banco emissor**: detecta logo/nome no header (Itaú, Bradesco, BB, Caixa, Santander, Nubank, Inter, C6 — 8 templates iniciais como YAML).

4. **Templates por banco como boost (não pré-requisito):**
   - Templates em `app/infrastructure/comprovantes/templates_banco/*.yaml`.
   - Banco identificado → tenta extração específica do template; campos extras encontrados elevam `score_confianca` em +0.10 a +0.15.
   - Sem template ou banco desconhecido → continua com a camada universal, score sem boost.

5. **Match com títulos em aberto** (em ordem decrescente de peso):
   - Valor exato + CNPJ destinatário == empresa do tenant + data ±2 dias → score = `min(score_camada + 0.20, 1.0)`.
   - Valor exato + data ±2 dias → score `+0.10`.
   - Valor ±R$ 0,01 + CNPJ → score `+0.05`.
   - Valor exato (sem outros campos) → score base.

6. **Modos de análise (configuração por tenant):**
   - Configuração nova em `configuracoes_sistema` (módulo `comprovantes`):
     - `modo_analise` (string, default `nativo`)
     - `provedor_ia` (string, opcional)
     - `ia_credencial_id` (uuid, opcional — FK pra `integration_credentials`)
     - `threshold_acionar_ia` (decimal, default 0.70)
     - `threshold_notificacao_baixa_confianca` (decimal, default 0.70)
     - `threshold_alerta_critico` (decimal, default 0.40)
   - Se `modo_analise = 'ia_como_reforco'` e confiança nativa < `threshold_acionar_ia`: chama `IProvedorIAVision` (port) com adapters disponíveis (OpenAI Vision, Claude Vision, Gemini — implementação futura, port só esta story).
   - Se `modo_analise = 'ia_primario'`: pipeline nativo é pulado, vai direto pra IA.

7. **Persistência:**
   - Tabela `financeiro.comprovantes_pagamento` (NOVA):
     - `id`, `empresa_id`, `titulo_id` (nullable — pode existir sem match), `arquivo_url` (MinIO/S3), `arquivo_hash` (SHA-256 — idempotência por hash do arquivo), `tipo_arquivo`, `metodo_analise` (br_code/pdf_texto/ocr/ia), `score_confianca`, `valor_detectado`, `data_detectada`, `pix_txid`, `pix_e2e_id`, `banco_emissor`, `beneficiario_cnpj`, `pagador_nome`, `texto_bruto_ocr` (auditoria), `avisos` (jsonb array), `status` (analisado/homologado/rejeitado), `homologado_por_id`, `homologado_em`, `criado_em`.
   - Índice único `(empresa_id, arquivo_hash)` — idempotência: enviar o mesmo arquivo 2x não duplica.
   - Migration nova.

8. **Notificação operacional:**
   - Score < `threshold_notificacao_baixa_confianca` → cria registro em `notificacoes_sistema` (nova ou reusa `log_eventos`) + flag visual no painel.
   - Score < `threshold_alerta_critico` → mesma notificação com `severidade='critico'` (destaque vermelho na UI).

9. **Endpoint de homologação:**
   - `POST /api/v1/comprovantes/{id}/homologar`: valida que role é admin ou financeiro; chama `ServicoTituloPago.registrar_pagamento(...)` com os dados detectados; marca comprovante como `homologado`; transiciona título via fluxo da Story 13.9.
   - `POST /api/v1/comprovantes/{id}/rejeitar`: marca como `rejeitado`, libera para nova análise.

10. **Integração com webhook WhatsApp:** quando handler atual de inbound WhatsApp recebe imagem/PDF, dispara `analisar_comprovante` como task Celery (fila `fila_verificacao`) com `cliente_id` extraído pelo telefone. Não bloqueia o webhook.

11. **Testes obrigatórios:**
   - **Sintéticos** (sem dependência de comprovantes reais):
     - BR Code válido → decodifica e extrai valor/chave/txid → score ≥ 0.95.
     - PDF textual gerado por reportlab → extrai valor/data → score ≥ 0.85.
     - Imagem sintética com texto fixo → OCR → extrai entidades → score ≥ 0.60.
     - CPF/CNPJ inválido (dígitos errados) → descarta.
     - Match valor + CNPJ → score correto.
     - Comprovante duplicado (mesmo hash) → segunda chamada retorna o registro existente, não cria novo.
   - **Reais** (quando você fornecer): minimal viable smoke-test com 1 comprovante real por banco coberto.

## Contexto Técnico

### Dependências novas (todas open-source, custo zero)

- `paddleocr` (~600MB modelo baixado 1x na primeira execução; cache local)
- `pyzbar` (wrapper Python do ZBar — leve, ~5MB)
- `pdfplumber` (extração de texto de PDFs nativos)
- `opencv-python-headless` (pré-processamento — versão sem GUI para container)
- `Pillow` (manipulação de imagem)

Todas adicionadas a `pyproject.toml` (extras opcional `[ocr]` para manter o core leve).

### Estrutura de código

```
src/backend-api/app/
├── domain/finance/
│   └── comprovante.py                     # dataclass ResultadoAnaliseComprovante
├── application/services/
│   └── servico_analise_comprovante.py     # orquestrador do pipeline
├── infrastructure/comprovantes/
│   ├── __init__.py
│   ├── br_code_decoder.py                 # camada 1
│   ├── pdf_text_extractor.py              # camada 2
│   ├── ocr_paddle.py                      # camada 3 (PaddleOCR + OpenCV)
│   ├── extratores_universais.py           # regex pra valor, data, CPF, CNPJ, E2E, chave PIX
│   ├── detector_banco.py                  # detecta banco pelo header
│   ├── templates_banco/
│   │   ├── itau.yaml
│   │   ├── bradesco.yaml
│   │   ├── bb.yaml
│   │   ├── caixa.yaml
│   │   ├── santander.yaml
│   │   ├── nubank.yaml
│   │   ├── inter.yaml
│   │   └── c6.yaml
│   └── matcher_titulos.py                 # cross-check com títulos em aberto
├── domain/ports/
│   └── provedor_ia_vision.py              # port (sem adapter ainda)
├── api/v1/
│   └── comprovantes_routes.py             # endpoints analisar/homologar/rejeitar
├── workers/tasks/
│   └── analisar_comprovante.py            # task Celery acionada via WhatsApp inbound
└── tests/
    └── test_comprovantes.py
```

### Migration

`alembic/versions/0026_comprovantes_pagamento.py`:

- Cria `financeiro.comprovantes_pagamento` com colunas listadas em AC 7.
- Índice único `(empresa_id, arquivo_hash)`.
- RLS estrita por `empresa_id`.

## Checklist do Dev

- [ ] Stories 13.4 (`ServicoConfiguracao`), 13.9 (`ServicoTituloPago`) concluídas.
- [ ] Migration aplicada.
- [ ] PaddleOCR instalado e modelo baixado no Dockerfile do container.
- [ ] Pipeline executa em < 5s para imagens típicas de comprovante PIX.
- [ ] BR Code decodifica corretamente em 3 amostras de bancos diferentes.
- [ ] Templates dos 8 bancos com pelo menos detecção de logo.
- [ ] Endpoint `/analisar` retorna `ResultadoAnaliseComprovante` no formato spec.
- [ ] Notificação criada quando score < threshold configurável.
- [ ] Idempotência por hash testada.
- [ ] Webhook WhatsApp aciona task Celery.

## Notas

- **Sem IA por padrão.** Configurar IA é opt-in explícito do gestor que aceita o custo.
- Templates por banco são **boost**, não pré-requisito. A camada universal já cobre ~95% dos casos sozinha.
- Sobre o tempo de processamento: PaddleOCR leva 2–4s por imagem em CPU. Se virar gargalo (muitos uploads simultâneos), considerar fila dedicada (`fila_verificacao` da Story 13.5) com worker em container separado.
- Story 13.20 (conciliação OFX/PDF) reusa o pipeline OCR construído aqui.
