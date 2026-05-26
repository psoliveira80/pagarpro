---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - "_bmad-output/planning-artifacts/PRD.md"
  - "_bmad-output/planning-artifacts/ARCHITECTURE.md"
project_name: "{{product_name}}"
---

# {{product_name}} — Detalhamento de Épicos e Histórias

## Visão Geral

Este documento fornece o detalhamento completo de épicos e histórias para **{{product_name}}**, uma plataforma genérica de cobrança recorrente e gestão de inadimplência com módulos verticais de ativos plugáveis. O **Core** da plataforma cuida de: clientes, contratos com construtor flexível de parcelas, títulos a receber (ciclo de 7 estados), títulos a pagar, agente de cobrança via WhatsApp com IA, conciliação bancária, dashboards e auditoria. **Módulos verticais** se conectam via Camada de Abstração de Ativos (`IAssetModule` + Eventos de Domínio + Module Hooks) para adicionar funcionalidades específicas de domínio sem tocar no Core.

O **primeiro módulo vertical é o de Veículos** (gestão de frota), cobrindo valoração FIPE, integração com rastreador GPS com bloqueio/desbloqueio remoto, depreciação, ROI por veículo e mapa interativo da frota.

O sistema é uma aplicação web fullstack greenfield (Angular 21+ / FastAPI) construída sobre arquitetura Hexagonal (Ports & Adapters), de modo que provedores externos (WhatsApp, Open Finance, gateways de pagamento, LLM, OCR, storage, APIs específicas de módulo) sejam intercambiáveis por configuração. Referências de pasta: `backend-api/` (backend), `frontend/` (frontend).

**Decisões financeiras-chave de design:**

- **Ciclo de vida do título:** Títulos (parcelas) são gerados na finalização do contrato (`status='vigente'`). Mudanças no contrato que afetam parcelas cancelam títulos em aberto e reemitem novos. Títulos pagos são imutáveis.
- **Pagamentos parciais:** Se valor pago < valor do título, o título original recebe baixa parcial e um NOVO título é criado para a diferença, com novo ciclo de cobrança.
- **Pagamento padrão:** Pix via WhatsApp (custo zero). O sistema gera o QR Code Pix e envia via WhatsApp; o cliente paga diretamente na conta bancária e envia o comprovante; OCR + validação + conciliação confirmam o pagamento. Plugins de gateway (Asaas, Stripe, etc.) são opcionais.

## Inventário de Requisitos

### Requisitos Funcionais

#### Camada de Abstração de Ativos (AST) — Core

- **FR-CORE-AST-1.** Interface `IAssetModule` que cada módulo vertical implementa (Protocol com hooks para eventos de domínio, detalhes do ativo, dados financeiros, widgets de dashboard, dimensões de relatório, ferramentas de cobrança).
- **FR-CORE-AST-2.** O Core NUNCA importa código de módulo diretamente. Comunicação via Eventos de Domínio num event bus interno (síncrono in-process no MVP, evoluível para assíncrono). Módulos registram hooks no startup.
- **FR-CORE-AST-3.** Tabela genérica `assets`: `id`, `module_id`, `external_ref`, `display_name`, `status`, `metadata` (JSONB). Contratos referenciam `asset_id`.
- **FR-CORE-AST-4.** Ativar/desativar módulos verticais em Configurações > Módulos sem restart.
- **FR-CORE-AST-5.** Hooks de ciclo de vida do Core para eventos de domínio: `InstallmentOverdue`, `InstallmentPaid`, `ContractCreated`, `ContractTerminated`, `ReconciliationCompleted`, `CustomerScoreChanged`, `PaymentPartiallyReceived`.

#### Autenticação e Controle de Acesso (AUTH) — Core

- **FR-CORE-AUTH-1.** Login por email/senha com hash Argon2id e MFA opcional (TOTP).
- **FR-CORE-AUTH-2.** Papéis: Administrador, Operador, Validador, Auditor (somente leitura), cada um com capacidades de escopo definido.
- **FR-CORE-AUTH-3.** RBAC granular por módulo (CRUD + ações sensíveis). Módulos verticais podem registrar permissões adicionais (ex.: Módulo de Veículos registra "bloquear veículo via rastreador").
- **FR-CORE-AUTH-4.** JWT de curta duração (15 min) com refresh token rotativo (7 dias) em cookie `HttpOnly Secure SameSite=Lax`.
- **FR-CORE-AUTH-5.** Auditoria de login/logout, IP, user-agent, tentativas falhas; bloqueio após 5 falhas em 15 min.

#### Cadastros Genéricos (CAD) — Core

- **FR-CORE-CAD-1.** Cadastro de cliente com dados pessoais completos, CPF/CNPJ validado, endereço ViaCEP, foto de perfil, N anexos. Campos adicionais de módulos verticais via extensão de schema.
- **FR-CORE-CAD-2.** Tabela genérica `assets` (conforme FR-CORE-AST-3). Cada módulo vertical gerencia seus próprios registros detalhados de ativo e sincroniza com `assets` do core.
- **FR-CORE-CAD-3.** Agrupar ativos em categorias genéricas para relatórios. Módulos verticais podem adicionar categorias específicas do domínio.

#### Módulo de Veículos — Cadastros (VH)

- **FR-VH-1.** Cadastro de veículo com validação de placa Mercosul, Renavam, chassi, vínculo FIPE, código do rastreador, status, dados de seguro/IPVA/licenciamento, galeria de fotos. Sincronizado com `assets` do core.
- **FR-VH-2.** Busca automática FIPE via seletores em cascata marca/modelo/ano; job mensal de atualização (dia 5).
- **FR-VH-3.** Modelo de pagamento de aquisição do veículo (à vista, financiado Price/SAC, consórcio, customizado).
- **FR-VH-4.** Dados financeiros por veículo: valor FIPE, depreciação, total pago em aquisição, saldo, total recebido, ROI %, payback.
- **FR-VH-5.** Mapa interativo da frota (Leaflet+OSM, intercambiável com Google Maps) com posições ao vivo, popups, ações de bloqueio/desbloqueio.
- **FR-VH-6.** Extensão de schema para Cliente: CNH (número, categoria, validade, foto).
- **FR-VH-7.** Hook `on_installment_overdue`: verifica política parametrizada de bloqueio (dias em atraso >= X E score < Y), dispara bloqueio GPS via `ITrackerGateway` com aprovação humana obrigatória.
- **FR-VH-8.** Ferramentas adicionais do agente de cobrança: `bloquear_veiculo`, `desbloquear_veiculo`, `verificar_localizacao_veiculo` injetadas via `IAssetModule.get_collection_tools()`.

#### Contratos (CTR) — Core

- **FR-CORE-CTR-1.** Contrato vinculando Cliente a Ativo (`asset_id`) com termos completos (datas, modelo de parcelamento, periodicidade, dia de vencimento, juros, multa, carência, opção de compra, garantias, cláusulas).
- **FR-CORE-CTR-2.** Construtor visual de parcelas: entrada, N parcelas regulares, extras semestrais/anuais, carência, cronograma customizado.
- **FR-CORE-CTR-3.** Na finalização (`vigente`): geração automática de títulos (`em_aberto`). Mudanças no contrato que afetam parcelas cancelam títulos em aberto e reemitem novos.
- **FR-CORE-CTR-4.** Renderização de PDF (Jinja2 + WeasyPrint), armazenado em storage compatível com S3 com hash SHA-256.
- **FR-CORE-CTR-5.** Assinatura digital (upload de PDF assinado; ponto de extensão futuro para D4Sign/Clicksign).
- **FR-CORE-CTR-6.** Edição em lote de parcelas em aberto (adiar, descontar, cancelar) em transação atômica com evento de auditoria. Títulos pagos imutáveis.
- **FR-CORE-CTR-7.** Parcelas pagas (`pago`) são imutáveis. Correções exigem estorno explícito (somente Admin, auditado).
- **FR-CORE-CTR-8.** Encerramento de contrato com cálculo de rescisão, título a receber final ou crédito, evento `ContractTerminated` para ações de módulo vertical.
- **FR-CORE-CTR-9.** Versionamento de contrato com timeline de revisões.
- **FR-CORE-CTR-10.** Simulação de contrato sem persistência.

#### Títulos a Receber (CR) — Core

- **FR-CORE-CR-1.** Lista mestre de títulos a receber com filtros multi-select (status, cliente, ativo, contrato, faixa de data, faixa de valor, competência).
- **FR-CORE-CR-2.** Baixa manual com data, valor, forma de pagamento, observação, anexo de comprovante (obrigatório para Pix). Status -> `pago_aguardando_verificacao`.
- **FR-CORE-CR-3.** Pagamentos parciais: se pago < valor do título, baixa parcial + NOVO título para a diferença, com novo ciclo de cobrança.
- **FR-CORE-CR-4.** Baixa em lote sobre múltiplas parcelas do mesmo cliente.
- **FR-CORE-CR-5.** Cálculo automático de juros + multa em parcelas vencidas; desconto opcional com motivo obrigatório.
- **FR-CORE-CR-6.** Fila de validação (Validador/Admin): visualizador de comprovante, valor esperado vs. detectado por OCR, Aprovar/Rejeitar/Solicitar reenvio.
- **FR-CORE-CR-7.** OCR em comprovantes Pix (Tesseract + heurísticas regex) extraindo valor, data, ID da transação.
- **FR-CORE-CR-8.** Máquina de estados: aprovação do validador -> `pago_aguardando_verificacao` -> conciliação bancária -> `pago` (imutável).
- **FR-CORE-CR-9.** Geração de QR Code Pix (BR Code) por título, custo zero, via `pix-utils`.
- **FR-CORE-CR-10.** Integração opcional com gateway de pagamento (Asaas, Efi, PagBank, Stripe) via adapter, desabilitada por padrão.
- **FR-CORE-CR-11.** Renegociação: agrupa títulos vencidos, recalcula, gera novos títulos, marca os originais como `renegociado`.

#### Títulos a Pagar (CP) — Core

- **FR-CORE-CP-1.** Categorias de despesa hierárquicas. Padrões do core; módulos adicionam extras.
- **FR-CORE-CP-2.** Cadastro de fornecedores.
- **FR-CORE-CP-3.** Título a pagar avulso com vínculo opcional a ativo (`asset_id`).
- **FR-CORE-CP-4.** Despesas recorrentes gerando títulos a pagar automaticamente.
- **FR-CORE-CP-5.** Atalho "Pagamento Rápido" (cria + paga atomicamente).
- **FR-CORE-CP-6.** DRE simplificado por período, filtrável por ativo, categoria, centro de custo.

#### Cobrança Inteligente e Agente WhatsApp (COB) — Core

- **FR-CORE-COB-1.** Integração WhatsApp via adapter (padrão: Evolution API; alternativas: Z-API, UazAPI, WPPConnect, Cloud API).
- **FR-CORE-COB-2.** Agente de Cobrança com IA plugável (LLM), RAG com pgvector, ferramentas core de function-calling, ferramentas injetadas por módulo via `IAssetModule.get_collection_tools()`, memória persistente.
- **FR-CORE-COB-3.** Parametrização no-code do agente: tom, saudações, cadência, concessão baseada em score, escalonamento, modelos de mensagem. Módulos registram políticas adicionais.
- **FR-CORE-COB-4.** Score do cliente (0-100) baseado em pontualidade, dias em atraso, tempo de relacionamento, valor pago. Módulos contribuem com fatores adicionais. Fórmula configurável.
- **FR-CORE-COB-5.** Envio automático de QR Pix via WhatsApp (fluxo padrão de pagamento: card Pix -> pagamento direto -> comprovante -> OCR -> validação -> baixa).
- **FR-CORE-COB-6.** Em mídia recebida: classificar, OCR, casar com título, baixa parcial ou total (`pago_aguardando_verificacao`), responder, enfileirar para validação humana.
- **FR-CORE-COB-7.** Caixa de entrada in-app estilo WhatsApp (3 painéis: conversas / chat / contexto do cliente).
- **FR-CORE-COB-8.** Gestor pode interceptar ("humano assume conversa"), pausar/retomar agente.
- **FR-CORE-COB-9.** Disparo em massa com dupla confirmação, preview, janela de tempo, rate limiting.
- **FR-CORE-COB-10.** Histórico de mensagens imutável com IDs do provedor externo.

#### Conciliação Bancária (CON) — Core

- **FR-CORE-CON-1.** Importação OFX com deduplicação por FITID.
- **FR-CORE-CON-2.** Importação de extrato em PDF (principais bancos brasileiros) via pdfplumber + fallback opcional com LLM.
- **FR-CORE-CON-3.** Adapter de Open Finance (padrão Pluggy; alternativas Belvo, TecnoSpeed, Klavi), desabilitado por padrão.
- **FR-CORE-CON-4.** Tela de conciliação com painéis lado a lado + zona de match drag-and-drop + auto-sugestões.
- **FR-CORE-CON-5.** Algoritmo de auto-match com threshold de confiança configurável.
- **FR-CORE-CON-6.** Suporte a 1:N, N:1, e transações não casadas como título a pagar/receita.
- **FR-CORE-CON-7.** Painel de divergências: transações órfãs, títulos pagos sem lançamento bancário, mismatches de valor.
- **FR-CORE-CON-8.** Conciliação final -> título `pago` (imutável), transação `conciliada` (travada).

#### Dashboards e Relatórios (DSH) — Core

- **FR-CORE-DSH-1.** Dashboard principal com cards de KPI genéricos reativos (Signals). Módulos injetam widgets via `IAssetModule.get_dashboard_widgets()`.
- **FR-CORE-DSH-2.** Dashboard Financeiro do Cliente.
- **FR-CORE-DSH-3.** Relatórios prontos exportáveis (Excel/PDF). Módulos registram relatórios adicionais via `IAssetModule.get_report_dimensions()`.
- **FR-CORE-DSH-4.** Construtor de relatório customizado com dimensões/medidas drag-and-drop, favoritos salvos.

#### Módulo de Veículos — Dashboards e Relatórios (VH)

- **FR-VH-9.** Widget de Dashboard de Veículo: investimento, ROI %, lucro, depreciação, aquisição vs. retorno, KM, produtividade, histórico de motoristas.
- **FR-VH-10.** Relatórios adicionais: Top Veículos por ROI, Histórico de Bloqueios, snapshot de Posição da Frota.
- **FR-VH-11.** Widgets injetados no Dashboard principal: Total da Frota (R$ FIPE), Veículos Ativos, Parados, Em Manutenção.

#### Integrações e Plug-and-Play (INT) — Core

- **FR-CORE-INT-1.** Ports (Protocols) para todos os provedores externos: `IWhatsAppGateway`, `IBankReconciliationProvider`, `IPaymentGateway`, `ILLMProvider`, `IStorageProvider`, `IOcrProvider`, `IPdfRenderer`. Módulos definem ports adicionais.
- **FR-CORE-INT-2.** Tela de Integrações do Admin: ativar/desativar adapters, credenciais criptografadas, testar conexão, indicador de status.
- **FR-CORE-INT-3.** Ingestão de webhook para todos os provedores com validação de assinatura, idempotência, fila de processamento.

#### Módulo de Veículos — Integrações (VH)

- **FR-VH-12.** `IFipeProvider` com `ApiFipeBrAdapter` padrão, `FipeApiBrAdapter` alternativo, fallback. Cache Redis de 30 dias.
- **FR-VH-13.** `ITrackerGateway` com adapters genéricos REST/MQTT para posição GPS, bloqueio/desbloqueio. Aprovação dupla + auditoria para comandos de bloqueio.

#### Parametrização (PRM) — Core

- **FR-CORE-PRM-1.** Tela de Configurações centralizada com seções: Geral, Empresa, Cobrança, Agente de IA, Integrações, Módulos, Usuários, Permissões, Modelos de Mensagem, Auditoria.
- **FR-CORE-PRM-2.** Configuração versionada com histórico de mudanças.

#### Auditoria (AUD) — Core

- **FR-CORE-AUD-1.** Log de auditoria append-only para todas as operações relevantes. Módulos registram ações adicionais.
- **FR-CORE-AUD-2.** Log de auditoria pesquisável com filtros e exportação.
- **FR-CORE-AUD-3.** Entradas assinadas por HMAC para detecção de adulteração.

### Requisitos Não-Funcionais

- **NFR-1 (Performance).** P95 leitura <= 300 ms, escrita <= 500 ms, render de dashboard <= 1.5 s em 4G.
- **NFR-2 (Escalabilidade).** 10k ativos / 50k títulos ativos / 100k mensagens WhatsApp/mês sem reestruturação.
- **NFR-3 (Disponibilidade).** SLA 99,5%.
- **NFR-4 (Segurança).** OWASP ASVS Nível 2; Argon2id; JWT RS256; AES-256-GCM em repouso; TLS 1.3; security headers; rate limiting.
- **NFR-5 (LGPD).** Exportação + exclusão de dados; consentimento; logs de acesso a PII.
- **NFR-6 (Auditabilidade Financeira).** Toda mudança de estado em título financeiro gera evento imutável; conciliação é reproduzível.
- **NFR-7 (Observabilidade).** Logs JSON estruturados, Prometheus, OpenTelemetry, Grafana.
- **NFR-8 (Acessibilidade).** WCAG 2.1 AA.
- **NFR-9 (i18n).** pt-BR padrão; pronto para en-US/es-ES.
- **NFR-10 (Plug-and-Play).** Trocar um provedor = config + novo adapter, zero mudança de domínio. Adicionar um módulo = implementar `IAssetModule`, zero mudança no core.
- **NFR-11 (Mobile-First).** Responsivo; PWA-ready.
- **NFR-12 (Tempo Real).** Chat, comprovantes, status de título na UI <= 2 s sem refresh.
- **NFR-13 (Backup e DR).** Full diário + WAL contínuo; RPO <= 1h, RTO <= 4h.
- **NFR-14 (Custo).** Stack padrão 100% open-source; nenhum SaaS pago obrigatório.
- **NFR-15 (Verticais Modulares).** Core funciona plenamente sem nenhum módulo vertical ativo (modo billing-only). Cada módulo é ativado/desativado independentemente.

### Requisitos Adicionais

- **Estrutura greenfield, dois diretórios:** `backend-api/` (FastAPI) e `frontend/` (Angular) sob raiz do projeto com `docker-compose.yml`. Sem nome de produto em pastas ou nomes de pacote. Nome do produto injetado via variável de ambiente `PRODUCT_NAME`.
- **Arquitetura Hexagonal inegociável:** todo provedor externo atrás de um Protocol em `app/domain/ports/`; domínio nunca importa `infrastructure/`.
- **Stack tecnológica travada** pelo documento de Arquitetura; nova tecnologia exige ADR aprovado.
- **Extensões PostgreSQL:** `pgcrypto`, `pg_trgm`, `unaccent`, `pgvector` habilitadas na primeira migration.
- **Triggers de banco:** trigger append-only de `audit_log`, trigger `enforce_paid_immutability` em `installments` nas primeiras migrations.
- **Materialized view `mv_asset_roi`:** necessária para dashboards de ROI por ativo; atualizada por job agendado. O Módulo de Veículos estende com colunas específicas de veículo.
- **Criptografia em repouso:** AES-256-GCM para CPF, CNH, segredos MFA, credenciais de integração.
- **Idempotência de webhook:** `webhook_events_raw` com `UNIQUE(provider, external_id)` obrigatório antes de qualquer integração de provedor.
- **Tempo real:** SSE padrão; WebSocket apenas para chat; polling como fallback degradado.
- **Schedule do Celery Beat:** atualização mensal FIPE (Módulo de Veículos), recálculo diário de score, cobrança preventiva diária, geração diária de títulos a pagar recorrentes, backup diário, conciliação por auto-match horária.
- **Importação Excel one-shot:** CLI `python -m app.cli import-excel` com reexecução idempotente e `--dry-run`.
- **Endpoints LGPD:** exportação e anonimização de dados do cliente.
- **Security headers + controles de Edge:** TLS 1.3, HSTS, rate limiting, CSP, etc.
- **Stack de observabilidade:** Prometheus, OpenTelemetry, structlog, dashboards Grafana.
- **Pirâmide de testes:** unit 55% / integração 25% / componente+contrato 15% / E2E 5%.
- **Branching:** features em `feat/{epic}-{story}-{slug}`; Conventional Commits; `main` protegida.
- **Guardrails de custo:** métrica de gasto LLM com alerta de budget diário e fallback automático.

### Requisitos de Design UX

_Não existe Especificação de Design UX standalone. A orientação de UI/UX está embutida na Seção 3 do PRD e Seção 10 da Arquitetura. Quando uma spec dedicada de UX for entregue, esta seção deve ser preenchida._

### Mapa de Cobertura dos FRs

| Requisito | Épico | Notas |
|---|---|---|
| FR-CORE-AST-1 (interface IAssetModule) | Épico 1 | Story 1.8 |
| FR-CORE-AST-2 (event bus, sem imports diretos) | Épico 1 | Story 1.8 |
| FR-CORE-AST-3 (tabela genérica assets) | Épico 1 | Story 1.8 |
| FR-CORE-AST-4 (ativar/desativar módulos sem restart) | Épico 1 | Story 1.8 |
| FR-CORE-AST-5 (hooks de ciclo de vida para eventos de domínio) | Épico 1 | Story 1.8 |
| FR-CORE-AUTH-1 (login email/senha + Argon2id + MFA) | Épico 1 | — |
| FR-CORE-AUTH-2 (papéis Admin/Operador/Validador/Auditor) | Épico 1 | — |
| FR-CORE-AUTH-3 (RBAC granular por módulo) | Épico 1 | Permissões populadas progressivamente por épico |
| FR-CORE-AUTH-4 (JWT 15min + refresh HttpOnly 7d) | Épico 1 | — |
| FR-CORE-AUTH-5 (auditoria de login + bloqueio após 5 falhas) | Épico 1 | — |
| FR-CORE-CAD-1 (Cliente com CPF/anexos + extensões de módulo) | Épico 2A | — |
| FR-CORE-CAD-2 (sync da tabela genérica assets) | Épico 2A | — |
| FR-CORE-CAD-3 (categorias de ativo) | Épico 2A | — |
| FR-VH-1 (cadastro de Veículo sincronizado com assets do core) | Épico 2B | — |
| FR-VH-2 (busca automática FIPE + job mensal) | Épico 2B | Depende de FR-VH-12 |
| FR-VH-3 (modelo de pagamento de aquisição de veículo) | Épico 2B | — |
| FR-VH-4 (dados financeiros por veículo: ROI, depreciação) | Épico 2B | Materialized view finalizada no Épico 8 |
| FR-VH-5 (mapa interativo da frota) | Épico 2B | Depende de FR-VH-13 |
| FR-VH-6 (extensão de schema CNH para Cliente) | Épico 2B | — |
| FR-VH-7 (hook on_installment_overdue: bloqueio GPS) | Épico 2B | — |
| FR-VH-8 (ferramentas do agente: bloquear/desbloquear/localizar) | Épico 2B | Injetadas no startup do agente no Épico 6 |
| FR-CORE-CTR-1 (Contrato vinculando Cliente a Ativo) | Épico 3 | — |
| FR-CORE-CTR-2 (construtor visual de parcelas) | Épico 3 | — |
| FR-CORE-CTR-3 (geração automática de títulos na finalização; reemissão na mudança) | Épico 3 | — |
| FR-CORE-CTR-4 (PDF Jinja2 + WeasyPrint + SHA-256) | Épico 3 | — |
| FR-CORE-CTR-5 (ponto de extensão para assinatura digital) | Épico 3 | — |
| FR-CORE-CTR-6 (edição em lote de parcelas em aberto; pagas imutáveis) | Épico 3 | — |
| FR-CORE-CTR-7 (imutabilidade de pagas + estorno) | Épico 3 | Trigger PG entregue junto com o model |
| FR-CORE-CTR-8 (encerramento de contrato com rescisão) | Épico 3 | — |
| FR-CORE-CTR-9 (timeline de versionamento de contrato) | Épico 3 | — |
| FR-CORE-CTR-10 (simulação de contrato) | Épico 3 | — |
| FR-CORE-CR-1 (lista mestre de títulos a receber) | Épico 4 | — |
| FR-CORE-CR-2 (baixa manual com comprovante) | Épico 4 | — |
| FR-CORE-CR-3 (pagamentos parciais: baixa + novo título para a diferença) | Épico 4 | — |
| FR-CORE-CR-4 (baixa em lote) | Épico 4 | — |
| FR-CORE-CR-5 (juros/multa + desconto manual) | Épico 4 | — |
| FR-CORE-CR-6 (fila de validação) | Épico 4 | — |
| FR-CORE-CR-7 (OCR em comprovantes Pix) | Épico 4 | Depende de FR-CORE-INT-1 (IOcrProvider) |
| FR-CORE-CR-8 (máquina de estados: pago_aguardando_verificacao -> pago) | Épico 4 | Estado final `pago` alcançado no Épico 7 |
| FR-CORE-CR-9 (QR Code Pix BR Code) | Épico 4 | — |
| FR-CORE-CR-10 (adapter opcional de gateway de pagamento) | Épico 4 | Desabilitado por padrão |
| FR-CORE-CR-11 (renegociação de títulos vencidos) | Épico 4 | — |
| FR-CORE-CP-1 (categorias hierárquicas de despesa) | Épico 5 | — |
| FR-CORE-CP-2 (cadastro de fornecedores) | Épico 5 | — |
| FR-CORE-CP-3 (Título a Pagar avulso) | Épico 5 | — |
| FR-CORE-CP-4 (despesas recorrentes) | Épico 5 | — |
| FR-CORE-CP-5 (atalho "Pagamento Rápido") | Épico 5 | — |
| FR-CORE-CP-6 (DRE simplificado) | Épico 5 | — |
| FR-CORE-COB-1 (adapter WhatsApp: Evolution/Z-API/etc.) | Épico 6 | — |
| FR-CORE-COB-2 (Agente IA com LLM + RAG + ferramentas core + ferramentas de módulo) | Épico 6 | Ferramentas de módulo injetadas via IAssetModule |
| FR-CORE-COB-3 (parametrização no-code do agente + políticas de módulo) | Épico 6 | — |
| FR-CORE-COB-4 (score do cliente 0-100 com fatores de módulo) | Épico 6 | Job diário |
| FR-CORE-COB-5 (envio automático de QR Pix via WhatsApp) | Épico 6 | Reusa FR-CORE-CR-9 |
| FR-CORE-COB-6 (comprovante recebido: classificar, OCR, baixa parcial/total) | Épico 6 | — |
| FR-CORE-COB-7 (caixa de entrada WhatsApp em 3 painéis) | Épico 6 | WebSocket `/ws/conversations` |
| FR-CORE-COB-8 (intervenção humana / pausar-retomar agente) | Épico 6 | — |
| FR-CORE-COB-9 (disparo em massa com controles) | Épico 6 | — |
| FR-CORE-COB-10 (histórico de mensagens imutável) | Épico 6 | — |
| FR-CORE-CON-1 (importador OFX) | Épico 7 | — |
| FR-CORE-CON-2 (importador de extrato PDF) | Épico 7 | Fallback LLM configurável |
| FR-CORE-CON-3 (Open Finance via Pluggy/Belvo/etc.) | Épico 7 | Desabilitado por padrão |
| FR-CORE-CON-4 (conciliação drag-and-drop em painéis lado a lado) | Épico 7 | — |
| FR-CORE-CON-5 (algoritmo de auto-match) | Épico 7 | — |
| FR-CORE-CON-6 (1:N, N:1, não casados como pagar/receita) | Épico 7 | — |
| FR-CORE-CON-7 (painel de divergências) | Épico 7 | — |
| FR-CORE-CON-8 (conciliação final -> pago imutável) | Épico 7 | — |
| FR-CORE-DSH-1 (Dashboard principal com KPIs genéricos + widgets de módulo) | Épico 8 | Atualização via SSE |
| FR-CORE-DSH-2 (Dashboard do Cliente) | Épico 8 | — |
| FR-CORE-DSH-3 (relatórios prontos + relatórios de módulo) | Épico 8 | — |
| FR-CORE-DSH-4 (construtor de relatórios customizados) | Épico 8 | — |
| FR-VH-9 (Dashboard de Veículo: ROI/payback/depreciação) | Épico 8 | Atualiza mv_asset_roi |
| FR-VH-10 (relatórios específicos de Veículo) | Épico 8 | — |
| FR-VH-11 (widgets injetados no Dashboard principal: KPIs de frota) | Épico 8 | Via get_dashboard_widgets() |
| FR-CORE-INT-1 (Ports/Protocols para todos os provedores) | Transversal | Cada Port criada no épico que primeiro precisa dela; auditoria de completude no Épico 9 |
| FR-CORE-INT-2 (tela de Integrações do Admin) | Épico 9 | Painel centralizado |
| FR-CORE-INT-3 (framework de ingestão de webhook) | Transversal | `webhook_events_raw` no Épico 1; cada provedor adiciona webhook em seu épico |
| FR-VH-12 (provedor FIPE com cache + fallback) | Épico 2B | — |
| FR-VH-13 (gateway de Rastreador REST/MQTT + comandos de bloqueio) | Épico 2B | — |
| FR-CORE-PRM-1 (Configurações centralizadas) | Transversal | Cada épico cria sua aba; consolidação no Épico 9 |
| FR-CORE-PRM-2 (configuração versionada) | Épico 9 | — |
| FR-CORE-AUD-1 (log de auditoria append-only + eventos de módulo) | Épico 1 (infra) -> todos os épicos (eventos) | Tabela + trigger no Épico 1 |
| FR-CORE-AUD-2 (log de auditoria pesquisável + exportação) | Épico 9 | UI completa |
| FR-CORE-AUD-3 (entradas assinadas por HMAC) | Épico 1 (HMAC) -> Épico 9 (UI verificadora) | — |

## Lista de Épicos

| # | Épico | Tipo | Resultado em 1 linha |
|---|---|---|---|
| 1 | **Fundação e Identidade** | Core | Time tem fundação rodando (auth, layout, Camada de Abstração de Ativos, CI/CD verde) — admin faz login e navega. |
| 2A | **Gestão Core de Ativos e Cadastros** | Core | Infraestrutura genérica de gestão de clientes e ativos pronta; módulos verticais podem plugar. |
| 2B | **Módulo de Veículos: Cadastros e Integrações** | Módulo de Veículos | Módulo de Veículos registrado como IAssetModule; frota num mapa em tempo real; valoração FIPE atualizada automaticamente. |
| 3 | **Contratos e Parcelas Flexíveis** | Core | Gestor gera qualquer formato de contrato com PDF e títulos vinculados; edita em lote títulos em aberto; títulos pagos imutáveis; mudanças reemitem títulos em aberto. |
| 4 | **Títulos a Receber, Pagamentos Parciais e Validação** | Core | Gestor opera títulos a receber com suporte a pagamentos parciais, fila de validação de comprovantes, OCR, Pix QR grátis — fluxo de pagamento padrão custo zero. |
| 5 | **Títulos a Pagar e Despesas Recorrentes** | Core | Gestor controla despesas com recorrências, Pagamento Rápido e DRE visível. |
| 6 | **Caixa de Entrada WhatsApp e Agente IA de Cobrança** | Core + Module Hooks | Agente conduz cobranças com política parametrizada e ferramentas injetadas por módulo; humanos intervêm quando quiserem. |
| 7 | **Conciliação Bancária Sofisticada** | Core | Conciliação OFX/PDF/Open Finance em minutos com drag-and-drop; baixas equivocadas -> zero. |
| 8 | **Dashboards, Relatórios e Analytics de Ativos** | Core + Module Hooks | Gestor lê o pulso operacional em segundos; ROI por ativo dirige decisões. Widgets de módulo injetados. |
| 9 | **Hardening e Plug-and-Play Final** | Core | Sistema entra em produção com confiança operacional; trocar um provedor é trivial; módulos documentados. |

---

## Épico 1: Fundação e Identidade (Core)

**Objetivo:** Subir o esqueleto técnico em dev e prod com login funcionando, layout base navegável, tema dark/light, Camada de Abstração de Ativos (`IAssetModule` + event bus + registro de Module Hooks) e pipeline CI/CD verde — sem nenhuma feature de domínio ainda. Ao final, qualquer desenvolvedor pode clonar, subir o ambiente e chegar à tela autenticada "Olá, X". O core está pronto para receber módulos verticais.

**Premissas:** Diretórios `backend-api/` e `frontend/` criados. Docker Compose com Postgres + Redis + MinIO para dev local. GitHub Actions habilitado.

### Story 1.1: Bootstrap do Backend FastAPI (Core)

Como Desenvolvedor,
quero um esqueleto FastAPI conectado a Postgres, Alembic, Pydantic v2 e com layout modular,
para que features futuras tenham uma base sólida e padronizada.

**Critérios de Aceite:**

1. Diretório `backend-api/` com Python 3.12+, gerenciado por `uv` (fallback `poetry`).
2. Layout de diretórios: `app/{api,core,domain,infrastructure,modules,workers,tests}` mais `alembic/`. O diretório `modules/` conterá módulos verticais (inicialmente vazio com `__init__.py`).
3. **Dado** que a API está rodando, **Quando** `GET /health` é chamado, **Então** a resposta retorna `{"status":"ok","db":"ok","redis":"ok","storage":"ok"}` com checagem real em cada dependência.
4. Alembic configurado com primeira migration vazia aplicada via `alembic upgrade head`.
5. Configuração via Pydantic Settings a partir de `.env` (dev) e variáveis de ambiente (prod). Segredos nunca commitados. `PRODUCT_NAME` como variável de configuração.
6. Logs JSON estruturados (`structlog`) emitidos para stdout.
7. CORS configurado para `http://localhost:4200`.
8. OpenAPI em `/docs` (Swagger) e `/redoc`.
9. Dockerfile multi-stage (build -> runtime) produzindo imagem <= 250 MB.
10. `docker-compose.yml` sobe API + Postgres + Redis + MinIO em <= 30 s.
11. `docker-compose.yml` inclui serviço `worker` (Celery worker) e serviço `beat` (Celery Beat scheduler), ambos usando a mesma imagem backend-api com comandos diferentes. Worker escuta filas: `default,high,low,events,agent,ocr`.
12. Dependências de sistema do WeasyPrint (libpangocairo, libcairo2, libgdk-pixbuf, tesseract-ocr, tesseract-ocr-por) são incluídas no estágio runtime do Dockerfile para suportar futuras histórias de geração de PDF e OCR.

### Story 1.2: Bootstrap do Frontend Angular 21 (Core)

Como Desenvolvedor,
quero um esqueleto Angular 21 standalone conectado a Tailwind v4, Heroicons e com a estrutura de pastas guiada pelo manifesto,
para que as features sejam construídas consistentemente desde o dia 1.

**Critérios de Aceite:**

1. Projeto Angular 21+ standalone em `frontend/`; sem NgModules.
2. `src/app/` segue o manifesto: `core`, `shared`, `features`. Sem `assets/` em `src/` — `public/` na raiz.
3. Tailwind CSS v4 com `tailwind.config`, plugins typography + forms.
4. `styles.css` com import do Tailwind e bloco `@theme` com **todas** as variáveis CSS listadas na Seção 3.5 do PRD (light + dark).
5. `theme.service.ts` em `core/services/` com signal `theme()` e `setTheme('light'|'dark'|'system')`, persistindo no localStorage.
6. `@ng-icons/core` + `@ng-icons/heroicons` instalados; `<ui-icon name="HeroXMark" />` em `shared/components/icon/`.
7. `AppShellComponent` em `shared/components/app-shell/` com sidebar colapsável, header com toggle de tema e nome do produto (via `environment.productName`), `<router-outlet>`.
8. Rotas: `/login`, `/dashboard` (placeholder), `/404`.
9. ESLint + Prettier + stylelint; `npm run lint` passa.
10. `index.html` com meta tags PWA e placeholder `manifest.webmanifest` (`name` vindo da config de build, nunca hardcoded).

### Story 1.3: Tabelas de Identidade de Usuário e Migration Inicial (Core)

Como Desenvolvedor,
quero as tabelas `users`, `roles`, `permissions`, `user_roles`, `refresh_tokens` e `audit_log` criadas,
para que o sistema de identidade tenha persistência e a auditoria comece desde o dia 1.

**Critérios de Aceite:**

1. Models SQLAlchemy em `app/infrastructure/db/models/` com PKs UUID via `gen_random_uuid()`, timestamps `TIMESTAMPTZ`, soft-delete via `deleted_at`.
2. Migration habilita as extensões `pgcrypto`, `pg_trgm`, `unaccent`, `pgvector`.
3. Tabela `users`: `id`, `email` (CITEXT unique), `password_hash`, `full_name`, `is_active`, `is_mfa_enabled`, `mfa_secret_enc` (BYTEA nullable), `last_login_at`, `created_at`, `updated_at`, `deleted_at`.
4. Tabela `audit_log`: `id`, `user_id`, `action`, `entity`, `entity_id`, `payload_before`, `payload_after`, `ip`, `user_agent`, `correlation_id`, `signature_hmac`, `created_at`. Trigger PG append-only bloqueando UPDATE/DELETE.
5. Índices: `users.email` unique, `audit_log(user_id, created_at DESC)`, `audit_log(entity, entity_id)`.
6. **Dado** um banco zerado, **Quando** `python -m app.cli seed` roda, **Então** os quatro papéis `Admin`, `Operador`, `Validador`, `Auditor` são inseridos, um usuário Admin `admin@app.local` (senha `Admin@123`) é criado e vinculado ao papel Admin. Permissões são populadas incrementalmente por épico.
7. Tabela `audit_log` inclui colunas `module` (TEXT), `category` (TEXT, default 'info' — valores: financial/navigation/error/info/security), `severity` (TEXT, default 'info' — valores: debug/info/warning/error/critical). Categorias financial e security são sempre persistidas; navigation é configurável OFF por padrão.

### Story 1.4: Endpoint de Login com JWT (Core)

Como usuário Admin,
quero fazer login com email e senha e receber tokens JWT,
para acessar recursos protegidos.

**Critérios de Aceite:**

1. **Dado** credenciais válidas, **Quando** `POST /api/v1/auth/login` é chamado, **Então** a resposta retorna `{access_token, refresh_token, user}` com 200.
2. Senhas verificadas com Argon2id; falhas em <= 200 ms (constant-time); `401 Unauthorized` genérico.
3. JWT RS256 com claims `sub`, `email`, `roles`, `iat`, `exp` (15 min), `iss`, `aud`.
4. Refresh token em cookie `HttpOnly Secure SameSite=Lax`, 7 dias, rotação a cada uso.
5. `POST /api/v1/auth/refresh` consome cookie, invalida token antigo, emite novo par.
6. `POST /api/v1/auth/logout` invalida refresh token (lista de revogação no Redis).
7. **Dado** 5 tentativas falhas em 15 min, **Quando** a 6ª chega, **Então** `429 Too Many Requests` por 15 min.
8. Eventos de login registrados em `audit_log` com assinatura HMAC.
9. Testes unitários: sucesso, senha errada, usuário inativo, fluxo MFA, rate limit.

### Story 1.5: Tela de Login no Frontend (Core)

Como Usuário,
quero uma tela de login polida,
para entrar com segurança e ter uma boa primeira impressão.

**Critérios de Aceite:**

1. `LoginComponent` em `features/auth/login/` com três arquivos (TS/HTML/CSS).
2. Reactive Forms (tipados) com email (required + email) e senha (required, min 8).
3. **Dado** que o formulário está inválido, **Quando** "Entrar" é clicado, **Então** o botão permanece desabilitado.
4. Spinner enquanto a request está em voo.
5. **Dado** 401, **Então** toast "Credenciais inválidas" e foco retorna ao email.
6. **Dado** 200, **Então** access token armazenado no signal `authState()`, navega para `/dashboard`.
7. Visual: card centralizado com glassmorphism, nome do produto (via `environment.productName`) no topo, background gradiente, ilustração no desktop.
8. `Enter` submete; foco inicial no email; indicadores visíveis de foco.
9. Link "Esqueci minha senha" para `/auth/forgot-password` (placeholder).
10. Playwright E2E: sucesso navega para `/dashboard`; falha permanece com toast.

### Story 1.6: AuthGuard, Interceptor JWT e Silent Refresh (Core)

Como o Sistema,
quero que rotas protegidas exijam autenticação e que tokens sejam renovados transparentemente,
para que a experiência do usuário não seja interrompida.

**Critérios de Aceite:**

1. `auth.guard.ts` em `core/guards/` bloqueia rotas quando `authState().isAuthenticated()` é falso, redirecionando para `/login?redirect=...`.
2. `jwt.interceptor.ts` em `core/interceptors/` injeta `Authorization: Bearer <token>`.
3. **Dado** 401, **Então** tenta `POST /auth/refresh` uma vez, replay em caso de sucesso, limpa estado e redireciona em caso de falha.
4. **Dado** múltiplos 401 concorrentes, **Então** apenas um refresh dispara (lock).
5. Em logout: limpa estado e cookie, navega para `/login`.

### Story 1.7: Pipeline CI/CD Inicial (Core)

Como o Time,
quero checks de CI rodando lint, type-check, testes e build em todo PR,
para que regressões sejam pegas cedo.

**Critérios de Aceite:**

1. `.github/workflows/api-ci.yml`: ruff, mypy strict, pytest com cobertura, Docker build.
2. `.github/workflows/web-ci.yml`: eslint, `ng build --configuration=production`, vitest.
3. Branch `main` protegida: PR + 1 review + todos os checks verdes.
4. Cobertura mínima de backend 70%.
5. Duração total do CI <= 10 min.

### Story 1.8: Bootstrap da Camada de Abstração de Ativos (Core)

Como Desenvolvedor,
quero a interface `IAssetModule` definida, o event bus implementado e o registro de Module Hooks funcionando,
para que módulos verticais possam plugar sem alterar o core.

**Critérios de Aceite:**

1. Protocol `IAssetModule` definido em `app/core/assets/module_interface.py` conforme FR-CORE-AST-1, com type hints completos incluindo `handles_event(event_type) -> bool` para declaração de capacidade, todos os métodos de hook retornando `list[Action]`, e métodos utilitários (`get_asset_schema`, `get_dashboard_widgets`, `get_report_dimensions`, `get_agent_tools`, `get_score_factors`, `get_custom_routes`).
2. **Event bus assíncrono via Celery** implementado em `app/core/events/event_bus.py`. `publish(event)` enfileira uma task Celery `handle_domain_event` na fila `events`. O worker Celery deserializa o evento, verifica `active_modules.is_active` + `module_hooks_config.is_active` + `handles_event()` do módulo, e dispatcha para o hook.
3. Eventos de Domínio definidos em `app/core/events/domain_events.py` como frozen dataclasses herdando de `DomainEvent(event_id, occurred_at, asset_type)`: `ContractCreatedEvent`, `ContractTerminatedEvent`, `InstallmentOverdueEvent`, `InstallmentPaidEvent`, `ReconciliationCompletedEvent`, `CustomerScoreChangedEvent`, `PaymentPartiallyReceivedEvent`.
4. Registro de Module Hooks em `app/core/assets/registry.py`: `register_module()`, `get_module()`, `list_modules()`, `is_module_active()`, `get_tools_for_context(caller_permissions, module_id)`. Módulos registram **apenas no boot time**; toggle em runtime via `active_modules.is_active` no banco.
5. Tabela `assets`: `id` UUID PK, `module_id`, `external_ref`, `display_name`, `status` (`disponivel`/`em_uso`/`manutencao`/`inativo`), `metadata` (JSONB), timestamps, soft delete.
6. Tabela `active_modules`: `module_id` PK, `is_active`, `config` (JSONB), `registered_at`.
7. Tabela `module_hooks_config`: `id` UUID PK, `module_id` FK, `event_type`, `policy` (JSONB), `is_active`.
8. Tabela `event_log`: `id` BIGSERIAL PK, `event_id` UUID UNIQUE, `event_type`, `asset_type`, `payload` (JSONB), `dispatched_at`, `processed_at`, `processing_status` (`pending`/`processing`/`completed`/`failed`), `error`. Suporta replay e debug.
9. **Todo hook handler DEVE ser idempotente** — verifica estado antes de agir; `event_log.event_id` UNIQUE previne processamento duplicado.
10. **O Core nunca faz JOIN com tabelas de módulo.** Dados do módulo são acessados via `get_asset_details(asset_id)`.
11. Testes unitários com `task_always_eager=True`: registrar MockModule, publicar evento, verificar que o handler foi chamado; verificar que módulo inativo é ignorado; verificar que `event_id` duplicado é ignorado.

### Story 1.9: Infraestrutura SSE (Core)

Como Desenvolvedor,
quero endpoints SSE com dispatch via Redis Pub/Sub e auth via token,
para que notificações em tempo real funcionem em todas as features.

**Critérios de Aceite:**

1. Endpoint SSE `GET /sse/notifications` implementado usando `sse-starlette` com backend Redis Pub/Sub.
2. Auth via query param `?token=<jwt>` (EventSource não suporta headers).
3. `SseService` em `backend-api/app/api/sse.py` se inscreve no canal Redis `sse:user:{user_id}`.
4. Reconexão tratada nativamente pelo EventSource; servidor envia diretiva `retry: 3000`.
5. `SseService` no frontend em `frontend/src/app/core/services/sse.service.ts` envolve EventSource com signal `connected` e signal `lastEvent`.
6. Teste unitário: publicar no canal Redis, verificar que o cliente SSE recebe o evento.

### Story 1.10: Fluxo de Recuperação de Senha (Core)

Como Usuário,
quero redefinir minha senha por email,
para recuperar o acesso se esquecer das credenciais.

**Critérios de Aceite:**

1. `POST /api/v1/auth/password/forgot` aceita `{email}` e envia link de reset por email (SMTP ou adapter configurável).
2. `POST /api/v1/auth/password/reset` aceita `{token, new_password}` e redefine a senha.
3. Tokens de reset expiram em 1 hora, são single-use e armazenados hasheados no Redis.
4. Port `IEmailSender` definida em `app/domain/ports/email_sender.py` com `SmtpAdapter` padrão e `ConsoleAdapter` para dev (imprime no stdout).
5. `ForgotPasswordComponent` e `ResetPasswordComponent` no frontend em `features/auth/`.
6. Log de auditoria registra eventos de reset de senha.

---

## Épico 2A: Gestão Core de Ativos e Cadastros (Core)

**Objetivo:** O gestor consegue cadastrar clientes e a infraestrutura genérica de ativos está pronta. O core gerencia clientes e delega detalhes de ativo aos módulos verticais via `IAssetModule`. UI ciente de módulos exibe apenas conteúdo relevante baseado nos módulos ativos.

### Story 2A.1: Modelo de Domínio de Cliente e API CRUD (Core)

Como desenvolvedor Backend,
quero uma entidade Cliente com endpoints REST completos,
para que o frontend possa gerenciar a base de clientes.

**Critérios de Aceite:**

1. Model `Customer` com campos genéricos: nome completo, CPF/CNPJ (validado), telefone (E.164), email, endereço completo, data de nascimento, foto, observações, `score` (default 100), `status` (`ativo`/`inativo`/`bloqueado`), `tags` (JSONB), `metadata_extensions` (JSONB para campos injetados por módulos), `created_by_user_id`.
2. CPF/CNPJ validado e unique; email unique; telefone normalizado para E.164.
3. Endpoints: `POST /api/v1/customers`, `GET /api/v1/customers?search=&status=&page=&size=`, `GET /api/v1/customers/{id}`, `PATCH /api/v1/customers/{id}`, `DELETE /api/v1/customers/{id}` (soft delete), `POST /api/v1/customers/{id}/attachments`.
4. Anexos armazenados no MinIO em `customers/{id}/{uuid}-{filename}` com registro em `customer_attachments`.
5. Toda mutação grava em `audit_log` com assinatura HMAC.
6. Testes de integração cobrindo CRUD + upload de anexo.

### Story 2A.2: Tela de Lista de Clientes (Core)

Como Gestor,
quero navegar por todos os clientes numa tabela pesquisável e filtrável,
para encontrar qualquer um em segundos.

**Critérios de Aceite:**

1. `CustomersListComponent` em `features/system/customers/`.
2. Colunas: avatar, nome, CPF/CNPJ mascarado (últimos 3 visíveis), telefone (atalho WhatsApp), score (badge colorido), status (badge), última atualização, ações da linha (ver, editar, excluir).
3. Busca textual com debounce 300 ms, dirigida por signal.
4. Filtros: status (multi-select), tag (multi-select), score (range slider).
5. Estado da URL: filtros na query string.
6. Paginação server-side via signals, preferencialmente usando a API `resource()`.
7. "Novo Cliente" abre drawer com `CustomerFormComponent`.
8. Skeleton loader durante fetch; empty state com ilustração e CTA.
9. Atalhos de teclado: `/` foca busca, `n` abre novo, setas percorrem linhas, `Enter` abre detalhe.

### Story 2A.3: Drawer de Criar/Editar Cliente (Core)

Como Gestor,
quero um formulário ergonômico para criar ou editar um cliente,
para que o cadastro seja rápido.

**Critérios de Aceite:**

1. Formulário em 3 seções colapsáveis: Dados Pessoais, Documentos, Contato e Endereço. Módulos verticais podem injetar seções adicionais (ex.: Módulo de Veículos injeta seção "CNH").
2. Validação inline (Reactive Forms tipados).
3. CEP preenche automaticamente via ViaCEP.
4. Foto: drop-zone com preview de crop circular.
5. Anexos: drop-zone multi-arquivo com previews.
6. Salvar fecha o drawer e atualiza a lista; erro exibe toast e preserva o formulário.
7. Acessível: ordem de tab correta, foco na primeira inválida ao submeter, `Esc` fecha (confirma se dirty).

### Story 2A.4: Página de Detalhe do Cliente com Abas (Core)

Como Gestor,
quero ver a vida completa de um cliente em uma única página,
para ter contexto completo antes de qualquer decisão.

**Critérios de Aceite:**

1. Rota `/system/customers/:id` renderiza `CustomerDetailComponent`.
2. Header: avatar, nome, CPF/CNPJ, score em destaque visual, status, ações primárias (Editar, Enviar Mensagem WhatsApp).
3. Abas core: **Visão Geral**, **Contratos**, **Títulos a Receber**, **Score**, **Documentos**, **Conversas**, **Auditoria**. Módulos verticais podem injetar abas adicionais. Cada aba é lazy-loaded.
4. Visão Geral: cards de métrica (total contratado, recebido, saldo em aberto, próximos), timeline de eventos.
5. URL preserva aba ativa via `?tab=...`.

### Story 2A.5: Lista Genérica de Ativos (Core)

Como Gestor,
quero ver todos os ativos cadastrados na plataforma,
para ter visão consolidada independente do módulo.

**Critérios de Aceite:**

1. Rota `/system/assets` lista registros da tabela `assets` com colunas: nome, módulo (badge), status, última atualização, ações.
2. Filtros: tipo de módulo (multi-select), status, busca textual.
3. Clique redireciona para a página de detalhe renderizada pelo módulo vertical correspondente.
4. Se nenhum módulo vertical está ativo, empty state: "Ative um módulo vertical em Configurações > Módulos para começar a cadastrar ativos."

### Story 2A.6: Importador Excel One-Shot — Clientes (Core)

Como Gestor entrando em produção,
quero importar clientes existentes de uma planilha,
para não redigitar dezenas de registros.

**Critérios de Aceite:**

1. CLI `python -m app.cli import-excel --entity=customers --file=clientes.xlsx --sheet=Clientes` mapeia colunas para a tabela `customers`.
2. **Dada** a flag `--dry-run`, **Então** valida e imprime relatório de diff sem persistir.
3. **Dada** reexecução com a mesma entrada, **Quando** registros existentes são encontrados por CPF, **Então** são atualizados (não duplicados).
4. Relatório ao final: criados, atualizados, ignorados (com motivos).
5. Importação escreve uma entrada de resumo em `audit_log`.

---

## Épico 2B: Módulo de Veículos — Cadastros e Integrações (Módulo de Veículos)

**Objetivo:** O Módulo de Veículos está implementado e registrado como `IAssetModule`. O gestor consegue cadastrar veículos, ver a frota num mapa em tempo real, e valorações FIPE são atualizadas automaticamente. O módulo reage a eventos de domínio via hooks. Ao final, a planilha de cadastro de veículos é substituível.

### Story 2B.1: Estrutura do Módulo de Veículos e Registro IAssetModule (Módulo de Veículos)

Como Desenvolvedor,
quero o Módulo de Veículos estruturado e registrado no core,
para que receba eventos de domínio e injete funcionalidade específica do domínio.

**Critérios de Aceite:**

1. Diretório `backend-api/app/modules/vehicles/` com: `__init__.py`, `module.py` (implementação de IAssetModule), `models.py`, `routes.py`, `services.py`, `hooks.py`, `ports/`, `adapters/`.
2. Classe `VehicleModule(IAssetModule)` implementa todos os métodos da interface: `on_contract_created`, `on_contract_terminated`, `on_installment_overdue`, `on_installment_paid`, `on_reconciliation_completed`, `get_asset_details`, `get_asset_financials`, `get_dashboard_widgets`, `get_report_dimensions`, `get_collection_tools`.
3. Módulo registrado no startup via `register_module(VehicleModule())`.
4. Entrada em `active_modules`: `module_id='vehicles'`, `is_active=True`.
5. Testes: publicar `InstallmentOverdueEvent` -> hook do Módulo de Veículos é chamado.

### Story 2B.2: Adapter do Provedor FIPE (Módulo de Veículos)

Como o Sistema,
quero uma Port `IFipeProvider` com adapters concretos,
para que o fornecedor FIPE seja intercambiável.

**Critérios de Aceite:**

1. Protocol `IFipeProvider` em `app/modules/vehicles/ports/fipe.py` com `list_brands`, `list_models`, `list_years`, `get_price`.
2. `ApiFipeBrAdapter` (padrão) em `app/modules/vehicles/adapters/fipe/apifipe_br.py`.
3. `FipeApiBrAdapter` (alternativo) em `app/modules/vehicles/adapters/fipe/fipeapi_br.py`.
4. Adapter de fallback: primário -> secundário em caso de erro.
5. Cache Redis com TTL de 30 dias por chave `fipe:{type}:{brand}:{model}:{year}`.
6. Endpoints: `GET /api/v1/modules/vehicles/fipe/{brands|models|years|price}`.
7. Adapter ativo selecionado via variável de ambiente `FIPE_PROVIDER`.

### Story 2B.3: Modelo de Domínio de Veículo, Integração FIPE e Aquisição (Módulo de Veículos)

Como desenvolvedor Backend,
quero uma entidade Veículo com CRUD, refresh FIPE e modelagem de aquisição,
para que o frontend possa gerenciar a frota financeiramente.

**Critérios de Aceite:**

1. Model `Vehicle` com todos os campos de FR-VH-1, mais `asset_id` (FK para `assets`), `current_contract_id` (nullable), `current_customer_id` (nullable, derivado).
2. Endpoints CRUD sob `/api/v1/modules/vehicles/` com checks de permissão.
3. Em create/update, sincroniza registro na tabela `assets` do core (cria ou atualiza `asset_id`).
4. `POST /api/v1/modules/vehicles/{id}/refresh-fipe` atualiza `valor_fipe_atual` via adapter ativo.
5. Job do Celery beat (`0 3 5 * *`) atualiza FIPE para todos os veículos ativos mensalmente.
6. Entidade `VehicleAcquisition` (1:1 com Vehicle) com formulário de aquisição (FR-VH-3): tipo, entrada, parcelas (JSONB), taxa de juros, sistema de amortização.
7. `GET /api/v1/modules/vehicles/{id}/financials` retorna: valor FIPE, depreciação, total pago na aquisição, saldo, total recebido, ROI %, payback.

### Story 2B.4: Wizard de Cadastro de Veículo (Módulo de Veículos)

Como Gestor,
quero um wizard guiado para cadastrar um veículo,
para que os muitos campos não me sobrecarreguem.

**Critérios de Aceite:**

1. 4 passos: **Identificação** (placa, renavam, chassi, cor), **Dados FIPE** (seletores em cascata marca/modelo/ano com valor auto-preenchido), **Aquisição** (data, valor de compra, forma de pagamento com sub-formulário dinâmico), **Documentos e Fotos** (seguro, IPVA, fotos).
2. Seletores FIPE com typeahead e loading inline.
3. **Dado** "Financiamento" selecionado, **Então** sub-formulário: entrada, quantidade de parcelas, taxa, amortização (Price/SAC), tabela de preview.
4. Stepper + Voltar/Próximo; estado do formulário preservado entre passos.
5. Passo final: preview antes do commit; ao confirmar, cria veículo + aquisição atomicamente.

### Story 2B.5: Lista de Veículos e Grid de Cards (Módulo de Veículos)

Como Gestor,
quero ver a frota como tabela ou cards,
para examinar seu estado rapidamente.

**Critérios de Aceite:**

1. Toggle Tabela <-> Cards; preferência persistida no localStorage.
2. Cards: foto, modelo, placa, badge de status, motorista atual, ROI %, próxima data de vencimento, mini-mapa com posição.
3. Filtros: status, marca, ano, motorista atual, tag.
4. Barra de KPI: Total da Frota (soma R$ FIPE), Veículos Ativos, Veículos Parados.

### Story 2B.6: Adapter de Rastreador GPS (Módulo de Veículos)

Como o Sistema,
quero uma Port `ITrackerGateway` com uma implementação genérica,
para que o rastreamento GPS seja plug-and-play.

**Critérios de Aceite:**

1. Protocol `ITrackerGateway` com `get_position`, `get_positions`, `block_vehicle`, `unblock_vehicle`, `get_history`.
2. `GenericRestTrackerAdapter` parametrizável por URL base, auth, mapeamento JSONPath — funciona para a maioria dos rastreadores REST sem mudança de código.
3. `MqttRestTrackerAdapter` para rastreadores com comandos MQTT / posição REST.
4. Bloqueio/desbloqueio exige perfil Admin + reconfirmação de senha (dupla aprovação) e grava evento assinado em `audit_log` com motivo.

### Story 2B.7: Mapa Interativo da Frota (Módulo de Veículos)

Como Gestor,
quero ver todos os veículos num mapa interativo,
para monitorar a operação geograficamente.

**Critérios de Aceite:**

1. `FleetMapComponent` em `features/modules/vehicles/fleet-map/`.
2. Leaflet com tiles OSM, marcadores customizados (ícone do tipo de veículo + cor do status).
3. Auto-cluster no zoom-out.
4. **Dado** clique no marcador, **Então** popup: foto, modelo, placa, motorista, status, "Ver Detalhes" + "Bloquear" (com dupla confirmação).
5. Posições atualizam a cada 30 s via SSE (`/sse/module/vehicles`).
6. Filtros laterais: status, motorista, tag.
7. Polígono opcional de "região de operação" destacando veículos fora da zona.

### Story 2B.8: Hook de Vencimento — Política de Bloqueio GPS (Módulo de Veículos)

Como o Módulo de Veículos,
quero reagir ao `InstallmentOverdueEvent` verificando a política de bloqueio,
para que veículos sejam bloqueados automaticamente quando configurado.

**Critérios de Aceite:**

1. Hook `on_installment_overdue` em `VehicleModule` verifica política parametrizada: `dias_atraso >= X` E `score < Y`.
2. Se condições atendidas E política exige aprovação humana -> cria notificação para o Admin com "Aprovar Bloqueio" / "Rejeitar".
3. Se condições atendidas E aprovação automática habilitada -> dispatcha `block_vehicle` via `ITrackerGateway`.
4. Evento `vehicle_blocked` gravado em `audit_log` com motivo, título associado, score do cliente.
5. Em `InstallmentPaidEvent`, hook verifica se veículo está bloqueado e todos os títulos vencidos foram quitados -> dispatcha automaticamente `unblock_vehicle`.

### Story 2B.9: Extensão de Schema CNH para Cliente (Módulo de Veículos)

Como o Módulo de Veículos,
quero cadastrar campos de CNH na entidade Cliente,
para que a documentação do motorista faça parte do perfil do cliente.

**Critérios de Aceite:**

1. Módulo de Veículos registra extensão de schema para Cliente via `metadata_extensions`: número de CNH, categoria, data de validade, URL da foto.
2. Formulário de Cliente (Story 2A.3) renderiza a seção "CNH" quando o Módulo de Veículos está ativo.
3. Validação de CNH: formato do número, categoria (A/B/AB/C/D/E), validade não no passado.
4. Foto da CNH enviada para o MinIO como anexo do cliente com tipo `cnh`.

### Story 2B.10: Importador Excel One-Shot — Veículos (Módulo de Veículos)

Como Gestor entrando em produção,
quero importar veículos existentes de uma planilha,
para não redigitar dados da frota.

**Critérios de Aceite:**

1. CLI `python -m app.cli import-excel --entity=vehicles --file=veiculos.xlsx` mapeia colunas para a tabela de veículos e sincroniza com `assets` do core.
2. `--dry-run` valida e imprime relatório sem persistir.
3. Reexecução com mesma entrada: registros existentes casados pela placa são atualizados (idempotente).
4. Relatório ao final: criados, atualizados, ignorados (com motivos).
5. Importação escreve uma entrada de resumo em `audit_log`.

---

## Épico 3: Contratos e Parcelas Flexíveis (Core)

**Objetivo:** O gestor consegue produzir qualquer formato de contrato imaginável (entrada + N parcelas + extras + carência + customizado), vinculado a um ativo genérico (`asset_id`), com PDF e títulos vinculados gerados automaticamente. Suporta edições em lote em parcelas em aberto sem tocar nas pagas. Mudanças no contrato reemitem títulos em aberto. Ciclo de vida do título: títulos gerados na finalização; mudanças no contrato cancelam títulos em aberto e geram novos; títulos pagos imutáveis.

### Story 3.1: Modelo de Domínio Contract, Installment, ContractEvent (Core)

Como desenvolvedor Backend,
quero o domínio de contratos modelado no banco,
para que regras financeiras tenham uma base correta.

**Critérios de Aceite:**

1. Tabela `contracts`: id, customer_id, asset_id (FK para `assets`), status (`rascunho`/`vigente`/`encerrado`/`rescindido`), start_date, end_date, total_amount, periodicity, due_day, late_interest_pct_per_day, late_fine_pct, grace_days, has_purchase_option, residual_value, terms_md, pdf_url, version, created_by, signed_at, terminated_at, termination_reason, soft delete.
2. Tabela `installments`: id, contract_id, sequence, due_date, amount, status (`em_aberto`/`vencido`/`pago_aguardando_verificacao`/`pago`/`pago_parcial`/`renegociado`/`cancelado`), kind (`regular`/`down_payment`/`extra_semestral`/`extra_anual`/`custom`), paid_at, paid_amount, payment_method, receipt_url, notes, parent_installment_id (nullable — referência ao título original em pagamento parcial), `UNIQUE(contract_id, sequence)`.
3. Tabela `contract_events` (append-only): id, contract_id, event_type, payload (JSONB), pdf_hash, created_by, created_at. Tipos: `created`, `signed`, `installments_generated`, `installments_reissued`, `bulk_edit`, `cancellation_requested`, `terminated`, `pdf_generated`.
4. Tabela `installment_adjustments` (append-only): id, installment_id, kind (`discount`/`fine`/`interest`/`renegotiation`/`bulk_edit`/`partial_payment`/`reverse_write_off`), amount_delta, snapshot_before, snapshot_after, reason, applied_by, applied_at.
5. Trigger PG `enforce_paid_immutability`: **Dado** que o status da parcela é `pago`, **Quando** um UPDATE tenta mudar `amount`, `due_date`, `paid_at`, `paid_amount`, ou reverter o status, **Então** exceção é lançada. Exceção: status -> `cancelado` somente quando a session var `app.reverse_write_off=true`.
6. Índices: `installments(contract_id)`, `installments(due_date, status)`, `installments(status)`.
7. Na finalização do contrato (status -> `vigente`), publica `ContractCreatedEvent` no event bus.
8. Tabela `installment_generations` criada com: id, contract_id, batch_label, installment_count, total_amount, has_financial_activity (bool, default false), created_by_user_id, created_at, rolled_back_at, rolled_back_by. Cada parcela carrega FK `generation_id` ligando-a à geração que a criou.

### Story 3.2: Backend do Construtor de Parcelas — Preview + Persist (Core)

Como desenvolvedor Backend,
quero um endpoint que calcule um cronograma a partir de uma definição de parcelamento,
para que o frontend possa fazer preview antes de persistir.

**Critérios de Aceite:**

1. **Dado** payload com `start_date`, `down_payment` opcional, `regular` opcional, `extras[]` opcional, `grace_days` opcional, `custom_overrides[]` opcional, **Quando** `POST /api/v1/contracts/preview-schedule` é chamado, **Então** a resposta retorna lista ordenada com `sequence`, `due_date`, `amount`, `kind`.
2. Total das parcelas calculadas confere com o total esperado (check de coerência).
3. Suporta modo `custom_only` para cronogramas totalmente editados à mão.
4. `POST /api/v1/contracts/` persiste contrato + todas as parcelas + `contract_events.created` atomicamente.
5. Cálculo do cronograma em `app/domain/contracts/schedule_calculator.py` com 100% de cobertura de teste unitário (sem I/O).
6. Suporta periodicidade `custom_days` onde `next_due = prev_due + timedelta(days=N)` com N configurável por contrato via campo `custom_days_interval`.

### Story 3.3: Frontend do Construtor Visual de Parcelas (Core)

Como Gestor,
quero uma UI visual para compor parcelas,
para ver o cronograma antes de confirmar.

**Critérios de Aceite:**

1. `ScheduleBuilderComponent` em `features/system/contracts/components/schedule-builder/`.
2. Painel esquerdo: configurador (toggle de entrada, parcelas regulares, extras, dias de carência).
3. Painel direito: tabela de preview atualizada reativamente via `resource()` chamando o endpoint de preview com debounce.
4. **Dado** toggle "Cronograma Customizado", **Então** configurador escondido, edição manual apenas.
5. Tabela de preview suporta reordenação drag-and-drop (CDK), edição inline de valor e data.
6. Botões "Adicionar parcela" e "Remover".
7. Rodapé: total parcelado, total geral, contagem, última data, período total.

### Story 3.4: Wizard de Criação de Contrato (Core)

Como Gestor,
quero um wizard guiado para criar um contrato,
para que os dados entrem de forma limpa e consistente.

**Critérios de Aceite:**

1. 4 passos: **Cliente e Ativo** (seletores com typeahead para cliente e ativo da tabela `assets`), **Termos** (datas, juros/multa, opção de compra), **Cronograma** (componente da Story 3.3), **Cláusulas e Revisão** (Tiptap rich text + preview do PDF).
2. Validações cruzadas: cliente é `ativo`, ativo é `disponivel`, end_date >= start_date.
3. **Dado** qualquer passo, **Quando** "Salvar Rascunho", **Então** persiste como `rascunho`, retomável.
4. **Dado** confirmar, **Então** contrato -> `vigente`, renderização de PDF enfileirada, parcelas geradas atomicamente. `ContractCreatedEvent` publicado.
5. Toast de sucesso com deep link "Ver Contrato".

### Story 3.5: Geração de PDF do Contrato (Core)

Como o Sistema,
quero renderizar um PDF profissional de cada contrato,
para que o gestor possa imprimi-lo ou enviá-lo.

**Critérios de Aceite:**

1. Task Celery `render_contract_pdf(contract_id)` carrega contrato + cliente + detalhes do ativo (via `IAssetModule.get_asset_details()`) + parcelas, renderiza Jinja2 -> HTML -> WeasyPrint -> PDF.
2. Template em `app/infrastructure/pdf/templates/contract.html.j2` com cláusulas configuráveis, dados, tabela de parcelas, espaço para assinatura.
3. PDFs armazenados no MinIO em `contracts/{contract_id}/v{version}.pdf`; URL salva em `contract.pdf_url`.
4. Hash SHA-256 registrado em `contract_events.pdf_generated`.
5. Em edição de contrato, version incrementa; versões anteriores continuam acessíveis.
6. `GET /api/v1/contracts/{id}/pdf?version=` retorna URL pré-assinada do MinIO (TTL 5 min).

### Story 3.6: Edição em Lote de Parcelas em Aberto (Core)

Como Gestor,
quero atualizar muitas parcelas em aberto de uma vez,
para que ajustes ad-hoc sejam rápidos.

**Critérios de Aceite:**

1. Tabela de parcelas do contrato suporta seleção multi-linha (checkbox + Shift-click range).
2. Barra flutuante "Ações em Lote": Adiar X dias, Aplicar desconto X% ou X R$, Definir valor, Cancelar, Recriar.
3. **Dada** ação em lote, **Então** aplicada **somente** a parcelas com status em (`em_aberto`, `vencido`). Títulos pagos são imutáveis — pulados com notificação.
4. Preview de diff antes/depois em modal de confirmação.
5. Backend aplica em transação única com evento `contract_events.bulk_edit`.
6. Após edição em lote, se parcelas foram alteradas, títulos abertos antigos são cancelados e novos gerados (reemissão). Evento `contract_events.installments_reissued` registrado.

### Story 3.7: Versionamento de Contrato e Timeline de Eventos (Core)

Como Gestor,
quero ver o histórico de mudanças de um contrato,
para rastrear qualquer modificação.

**Critérios de Aceite:**

1. Aba "Histórico" na página de detalhe do contrato.
2. Timeline vertical com ícone + descrição + autor + data por evento.
3. **Dado** clique no evento, **Então** payload mostrado (diff visual quando aplicável).
4. Cada evento `pdf_generated` tem botão "Ver PDF desta versão".

### Story 3.8: Encerramento de Contrato (Core)

Como Gestor,
quero encerrar um contrato com cálculo de quitação,
para que a devolução do ativo seja documentada.

**Critérios de Aceite:**

1. Modal "Encerrar": motivo, data efetiva, política de multa de rescisão (toggle "Aplicar X% de multa", default das Configurações).
2. Backend calcula: `soma(parcelas_em_aberto) * pct_multa + ajuste_manual`.
3. **Dado** confirmar, **Então** título a receber final (ou crédito) criado, parcelas em aberto -> `cancelado`, contrato -> `rescindido`, evento `ContractTerminated` publicado (módulo vertical reage — ex.: Módulo de Veículos seta veículo como `disponivel`).
4. Entrada `contract_events.terminated` gravada.

### Story 3.9: Simulação de Contrato (Core)

Como Gestor,
quero simular um contrato sem persistir,
para explorar cenários antes de confirmar.

**Critérios de Aceite:**

1. `POST /api/v1/contracts/simulate` aceita definição completa de contrato + cronograma, retorna parcelas e totais calculados.
2. Sem escritas no banco; usa a mesma função pura `schedule_calculator.py`.
3. Modal de preview no frontend mostra todas as parcelas com totais.

### Story 3.10: Gestão de Gerações de Parcelas e Rollback (Core)

Como Gestor,
quero ver todas as gerações de parcelas de um contrato e fazer rollback de gerações errôneas instantaneamente,
para não poluir o sistema com centenas de títulos cancelados de um erro de digitação.

**Critérios de Aceite:**

1. Página de detalhe do contrato ganha aba "Gerações" listando todas as `installment_generations` com batch_label, contagem de parcelas, valor total, status (active/rolled_back), badge `has_financial_activity`.
2. **Dada** uma geração com `has_financial_activity = FALSE`, **Quando** o usuário clica em "Rollback", **Então** todas as parcelas dessa geração são **hard deletadas** (não canceladas), a geração é marcada com `rolled_back_at = now()`, e uma entrada de audit_log registra todos os IDs de parcelas deletadas.
3. **Dada** uma geração com `has_financial_activity = TRUE`, **Quando** o usuário a visualiza, **Então** o botão "Rollback" fica escondido e um botão "Cancelar em massa" aparece no lugar. Clicar nele seta todas as parcelas em aberto dessa geração para `cancelado`.
4. `has_financial_activity` vira TRUE quando QUALQUER parcela na geração: recebe baixa (total/parcial), é enviada para cobrança (card Pix enviado via WhatsApp), recebe cobrança por gateway de pagamento, ou tem qualquer `installment_adjustment`.
5. A ação de rollback exige confirmação de papel Admin.
6. Após rollback, a lista de parcelas do contrato atualiza imediatamente.

---

## Épico 4: Títulos a Receber, Pagamentos Parciais e Validação (Core)

**Objetivo:** O gestor conduz a operação completa de títulos a receber com suporte a pagamento parcial, baixa manual, fila de validação de comprovantes, OCR automático e geração gratuita de QR Code Pix. Fluxo padrão de pagamento: Pix via WhatsApp (custo zero).

### Story 4.1: Lista Mestre de Títulos a Receber (Core)

Como Gestor,
quero ver cada título a receber em uma tabela poderosa,
para operar finanças em escala.

**Critérios de Aceite:**

1. Rota `/system/finance/receivables` renderiza `ReceivablesListComponent`.
2. Filtros: status (multi-select), cliente, ativo, contrato, faixa de vencimento, faixa de valor.
3. Colunas: data de vencimento, cliente (avatar), ativo, contrato (link), valor original, valor atualizado (juros/multa), status (badge), forma, ações da linha.
4. Ações da linha: Baixar, Baixa Parcial, Ver, Editar (se em aberto), Cancelar (se em aberto).
5. Totais no rodapé: "Selecionados: R$ X | Total do filtro: R$ Y | Inadimplência: R$ Z".
6. Atalhos de teclado: `b` baixa selecionados, `Espaço` seleciona, `f` foca filtros.

### Story 4.2: Cálculo de Valor Atualizado — Juros, Multa, Desconto (Core)

Como o Sistema,
quero uma função pura que calcule o valor atualizado de uma parcela vencida,
para que baixas usem o valor correto.

**Critérios de Aceite:**

1. `compute_updated_value(installment, on_date, contract_terms)` é função pura em `domain/finance/calculations.py`.
2. Fórmula: `dias_atraso = max(0, on_date - due_date - grace_days)`; `multa = amount * fine_pct if dias_atraso > 0 else 0`; `juros = amount * interest_pct_per_day * dias_atraso`; `total = amount + multa + juros`.
3. `GET /api/v1/receivables/{id}/updated-value?on_date=` retorna breakdown completo (base, juros, multa, desconto, total).
4. Desconto manual exige `reason` obrigatório, persistido em `installment_adjustments`.
5. Testes unitários: em dia, atraso curto, atraso longo, dentro da carência, com desconto.

### Story 4.3: Modal de Baixa Manual (Core)

Como Gestor,
quero baixar uma parcela informando os dados do pagamento,
para que o título saia do status "em aberto".

**Critérios de Aceite:**

1. Modal: data efetiva (default hoje), valor pago (default `updated_value`), forma (Pix/dinheiro/transferência/cartão/outro), observações, drop-zone de anexo (obrigatório para Pix).
2. **Dado** Pix e comprovante enviado, **Então** OCR roda em background, auto-popula valor e data se confiança >= 70%.
3. **Dado** baixa Pix confirmada, **Então** status -> `pago_aguardando_verificacao`.
4. **Dado** dinheiro ou cartão presencial, **Então** status -> `pago_aguardando_verificacao`.
5. Lista atualiza; toast de sucesso exibido.

### Story 4.4: Suporte a Pagamento Parcial (Core)

Como o Sistema,
quero tratar pagamentos parciais corretamente,
para que a diferença seja rastreada como um novo título a receber.

**Critérios de Aceite:**

1. Função pura `compute_partial_payment(title_amount, paid_amount, original_due_date, grace_days)` em `domain/finance/calculations.py` retorna: `original_new_status='pago_parcial'`, `remainder_amount`, `remainder_due_date`, `adjustment_delta`.
2. **Dado** paid_amount < valor do título, **Quando** `POST /api/v1/receivables/{id}/partial-write-off` é chamado com dados de pagamento, **Então**:
   - Título original recebe `paid_amount` e status `pago_parcial`.
   - `InstallmentAdjustment` com `kind='partial_payment'` criado, registrando `amount_delta` e referência ao novo título em `reason` (JSON).
   - Um NOVO título é gerado para a diferença (`title.amount - paid_amount`) com `kind='regular'`, `due_date` = próximo vencimento ou mesmo dia + `grace_days`, vinculado ao mesmo contrato, com `parent_installment_id` apontando para o original.
   - Sequence do contrato incrementada.
3. `PaymentPartiallyReceivedEvent` publicado no event bus (módulos podem reagir).
4. Testes unitários: vários valores parciais, casos de borda (pago = 0, pago = total).
5. Pagamentos parciais concorrentes na mesma parcela são prevenidos via pessimistic locking (`SELECT ... FOR UPDATE`). Segunda request concorrente recebe 409 Conflict.

### Story 4.5: Adapter de Provedor OCR (Core)

Como o Sistema,
quero uma Port `IOcrProvider` com implementação Tesseract padrão,
para que o OCR funcione com custo externo zero.

**Critérios de Aceite:**

1. Protocol `IOcrProvider`: `extract_text(file_bytes, mime)`, `extract_pix_receipt(file_bytes, mime)`.
2. `TesseractOcrAdapter` com pré-processamento OpenCV (deskew, denoise, threshold), idioma `por+eng`.
3. `LlmVisionOcrAdapter` (fallback opcional) chamando GPT-4o Vision ou Claude quando a confiança for baixa.
4. Regex de comprovante Pix: valor (`R\$\s*[\d.,]+`), data (`\d{2}/\d{2}/\d{4}`), ID de transação, beneficiário, banco.
5. Resultados cacheados no Redis por SHA-256 dos bytes do arquivo (TTL 7 dias).

### Story 4.6: Fila de Validação de Comprovantes (Core)

Como Validador,
quero uma fila de comprovantes pendentes,
para validar rapidamente em lote.

**Critérios de Aceite:**

1. Rota `/system/finance/validation-queue` lista parcelas em `pago_aguardando_verificacao` ordenadas por data ascendente.
2. Layout dividido: lista à esquerda, visualizador de arquivo ao centro (imagem/PDF com zoom), painel direito com dados do título e Aprovar/Rejeitar/Solicitar Reenvio.
3. Teclado: `A` aprova, `R` rejeita, seta próximo/anterior.
4. **Dado** aprovar, **Então** status -> `pago_aguardando_verificacao`, evento `audit_log` com `validated_by_user_id`.
5. **Dado** rejeitar, **Então** motivo obrigatório (pré-definido + texto livre).
6. **Dado** "Solicitar Reenvio", **Então** mensagem WhatsApp dispatchada (usa Épico 6), status inalterado.
7. KPIs no topo: pendentes, validados hoje, rejeitados hoje.

### Story 4.7: Geração de QR Code Pix Estático (Core)

Como o Sistema,
quero gerar um BR Code Pix por parcela,
para que cobranças sejam imediatamente pagáveis com custo zero.

**Critérios de Aceite:**

1. Chave Pix da empresa configurada em Configurações > Empresa (chave + nome do beneficiário).
2. `GET /api/v1/receivables/{id}/pix-qr` retorna QR SVG/PNG + texto BR Code "Copia e Cola".
3. Usa `pix-utils` seguindo spec BCB MN-002.
4. TXID embute ID da parcela para conciliação.
5. Detalhe do título a receber: botão "Gerar QR Pix" abre modal com QR + CTA "Enviar via WhatsApp".

### Story 4.8: Renegociação de Parcelas Vencidas (Core)

Como Gestor,
quero renegociar títulos a receber vencidos,
para que clientes em dificuldade possam voltar aos eixos.

**Critérios de Aceite:**

1. **Dadas** múltiplas parcelas vencidas do mesmo cliente selecionadas, **Quando** "Renegociar" é acionado, **Então** modal mostra soma com juros/multa atualizados.
2. Modal usa o construtor de cronograma do Épico 3 para o novo cronograma.
3. **Dado** confirmado, **Então** parcelas originais -> `renegociado` (imutáveis), novas parcelas criadas.
4. Evento `renegotiated` com `{old_ids, new_ids, total_old, total_new}` em `audit_log`.

### Story 4.9: Adapter Opcional de Gateway de Pagamento Pix (Core)

Como Admin,
quero conectar opcionalmente Asaas/Efi,
para que cobranças Pix auto-confirmadas fiquem disponíveis quando o ROI justificar o custo por transação.

**Critérios de Aceite:**

1. Port `IPaymentGateway`: `create_charge(installment) -> Charge`, `webhook_handler(payload, signature) -> Event`.
2. `AsaasAdapter`, `EfiAdapter` implementados; `NoOpPaymentGateway` é padrão (desligado).
3. Configurações > Integrações: Admin pode ativar, armazenar credenciais criptografadas, definir escopo.
4. **Dado** webhook em `POST /api/v1/webhooks/payment-gateway/{provider}`, **Quando** assinatura valida, **Então** processamento idempotente move parcela direto para `pago` (pula validação manual).
5. Padrão: **desabilitado**, conforme preferência por Pix custo-zero.

### Story 4.10: Estorno de Parcela — Total e Parcial (Core)

Como Admin,
quero estornar uma parcela paga total ou parcialmente,
para que pagamentos a maior sejam corrigidos com trilha de auditoria completa e o fluxo de caixa reflita a realidade.

**Critérios de Aceite:**

1. **Dada** uma parcela `pago` ou `pago_parcial`, **Quando** Admin clica em "Estornar", **Então** um modal pergunta: estorno total ou parcial, valor (se parcial), motivo, e reautenticação de senha do Admin.
2. Estorno total cria `InstallmentAdjustment` com `kind='full_reversal'` e gera um `Payable` (título a pagar) com `linked_installment_id` apontando para o título original. O valor do título a pagar é igual ao `paid_amount` original.
3. Estorno parcial cria `InstallmentAdjustment` com `kind='partial_reversal'` e gera um `Payable` para o valor delta com `linked_installment_id`.
4. O status da parcela original NÃO muda — permanece `pago` ou `pago_parcial` (imutável). O estorno vive inteiramente no adjustment + título a pagar.
5. Tabela `payables` inclui `linked_installment_id UUID REFERENCES installments(id)` para rastrear estornos.
6. DRE e dashboards calculam receita líquida = bruto recebido - soma dos títulos a pagar de estorno.
7. Log de auditoria registra o estorno com module='core', category='financial', payload antes/depois, e ID do usuário Admin.
8. O Payable gerado é conciliável contra a transação bancária de saída na tela de conciliação.

### Story 4.11: Baixa em Lote (Core)

Como Gestor,
quero baixar múltiplas parcelas do mesmo cliente com um único pagamento,
para que pagamentos em batch sejam rápidos.

**Critérios de Aceite:**

1. Usuário seleciona múltiplas parcelas em aberto/vencidas do mesmo cliente na lista de títulos a receber.
2. Ação "Baixa em Lote" abre um modal mostrando títulos selecionados, soma total (com juros/multas) e um formulário único de pagamento.
3. Pagamento é distribuído entre os títulos por ordem de vencimento (mais antigo primeiro).
4. Cada título recebe seu próprio `InstallmentAdjustment` e mudança de status.
5. Se valor pago < total selecionado, o último título recebe baixa parcial com título remanescente gerado.
6. Log de auditoria registra a operação em lote com todos os IDs de parcela afetados.

---

## Épico 5: Títulos a Pagar e Despesas Recorrentes (Core)

**Objetivo:** O gestor controla cada despesa operacional com lançamentos avulsos, recorrências auto-geradas, atalho "Pagamento Rápido" e DRE simplificado — resultado mensal visível de relance.

### Story 5.1: Domínio e API CRUD de Categorias e Fornecedores (Core)

Como desenvolvedor Backend,
quero entidades para categorizar despesas e fornecedores,
para que relatórios subsequentes sejam ricos.

**Critérios de Aceite:**

1. Tabela `expense_categories`: id, parent_id (hierarquia auto-referencial), name, color, icon, is_active, sort_order. Padrões do core populados; módulos podem registrar categorias adicionais.
2. Tabela `suppliers`: id, name, document (CPF/CNPJ), contact, bank_data (JSONB), is_active.
3. Endpoints CRUD `/api/v1/expense-categories` e `/api/v1/suppliers` com permissões.
4. Categorias default populadas: Manutenção, Combustível, Impostos, Seguro, Salários, Aluguel, Utilidades, Outros.

### Story 5.2: Domínio e API de Títulos a Pagar (Core)

Como desenvolvedor Backend,
quero uma entidade Payable com endpoints REST,
para que o frontend possa gerenciar despesas.

**Critérios de Aceite:**

1. Tabela `payables`: id, description, supplier_id (nullable), category_id, asset_id (nullable, FK para `assets` para custeio por ativo), amount, due_date, status (`em_aberto`/`pago`/`cancelado`), paid_at, paid_amount, payment_method, attachment_url, notes, created_by, recurring_template_id (nullable).
2. Endpoints CRUD sob `/api/v1/payables`.
3. **Dado** título a pagar `em_aberto`, **Quando** `POST /api/v1/payables/{id}/pay`, **Então** status -> `pago`, entrada de auditoria.
4. **Dada** intenção "Pagamento Rápido", **Quando** `POST /api/v1/payables/quick-pay`, **Então** cria + paga atomicamente.

### Story 5.3: Despesas Recorrentes (Core)

Como o Sistema,
quero títulos a pagar recorrentes gerados automaticamente,
para que o gestor não esqueça obrigações fixas.

**Critérios de Aceite:**

1. Tabela `recurring_payable_templates`: id, description, supplier_id, category_id, asset_id, amount, periodicity (`mensal`/`bimestral`/`anual`), day_of_month, start_date, end_date (nullable), is_active.
2. Endpoints CRUD sob `/api/v1/recurring-payables`.
3. **Dado** job diário do Celery beat (`0 4 * * *`), **Quando** template ativo e hoje confere com day_of_month e nenhum título a pagar existe para o período atual, **Então** novo título a pagar criado.
4. Tela "Despesas Recorrentes": templates com toggle de ativo, próximas datas, botão "Gerar agora".

### Story 5.4: Modal "Pagamento Rápido" (Core)

Como Gestor,
quero um atalho rápido para registrar uma despesa já paga,
para que o lançamento instantâneo seja trivial.

**Critérios de Aceite:**

1. Botão flutuante "Lançar e Pagar" (FAB) disponível em todas as telas + command palette.
2. Modal compacto: descrição, fornecedor (autocomplete + criar-inline), categoria, valor, data (default hoje), forma, anexo, ativo (opcional).
3. **Dado** confirmar, **Então** título a pagar criado com `status='pago'` em transação atômica única.

### Story 5.5: DRE Simplificado (Core)

Como Gestor,
quero ver Receitas - Despesas por período,
para ler o resultado da operação.

**Critérios de Aceite:**

1. Rota `/system/finance/dre` com filtros: período (mês/trimestre/customizado), ativo, categoria.
2. Estrutura: Receitas (por fonte), Despesas (por categoria), Margem Bruta, Margem %.
3. Gráfico de barras comparando meses com drilldown no clique.
4. Exportação para Excel e PDF com formatação preservada.

---

## Épico 6: Caixa de Entrada WhatsApp e Agente IA de Cobrança (Core + Module Hooks)

**Objetivo:** O gestor para de cobrar manualmente. Um agente conversacional educado e parametrizável conduz cobranças seguindo políticas pré-definidas; humanos podem intervir a qualquer momento. Ferramentas injetadas por módulo (ex.: `bloquear_veiculo` do Módulo de Veículos) ficam disponíveis para o agente. Histórico completo de conversa em UI familiar estilo WhatsApp. Fluxo padrão de pagamento: Pix via WhatsApp (custo zero).

### Story 6.1: Adapter de Gateway WhatsApp (Core)

Como o Sistema,
quero uma Port `IWhatsAppGateway` com Evolution API como padrão,
para que trocar de provedor não afete o domínio.

**Critérios de Aceite:**

> **Escopo MVP:** Apenas EvolutionApiAdapter é exigido para o MVP. ZapiAdapter, UazapiAdapter, WppConnectAdapter e WhatsAppCloudApiAdapter são V2.

1. Protocol `IWhatsAppGateway`: `send_text`, `send_image`, `send_document`, `send_pix_card`, `mark_as_read`, `webhook_parse`.
2. Adapters: `EvolutionApiAdapter` (padrão), `ZapiAdapter`, `UazapiAdapter`, `WppConnectAdapter`, `WhatsAppCloudApiAdapter`.
3. Configuração via env + Configurações > Integrações: provider, API key, instance ID, webhook secret.

### Story 6.2: Domínio de Conversas e Mensagens (Core)

Como desenvolvedor Backend,
quero conversas e mensagens persistidas,
para que o histórico seja sempre recuperável.

**Critérios de Aceite:**

1. Tabela `whatsapp_conversations`: id, customer_id, phone_e164, last_message_at, unread_count, is_archived, agent_active, agent_paused_until.
2. Tabela `whatsapp_messages`: id, conversation_id, external_id (UNIQUE), direction, kind, content_text, media_url, media_mime, sent_at, delivered_at, read_at, sent_by (`agent` ou `human:{user_id}`), status, context (JSONB), embedding (vector(1536) nullable).
3. `GET /api/v1/conversations?search=&unread=&page=` retorna lista paginada.
4. `GET /api/v1/conversations/{id}/messages?before=&limit=` retorna paginação por cursor cronológica reversa.
5. WebSocket `/ws/conversations` empurra novas mensagens para subscribers em tempo real.

### Story 6.3: Receiver de Webhook e Pipeline de Inbound (Core)

Como o Sistema,
quero receber e processar mensagens WhatsApp recebidas com idempotência,
para que nenhuma mensagem se perca.

**Critérios de Aceite:**

1. `POST /api/v1/webhooks/whatsapp/{provider}` valida assinatura; payload bruto persistido em `webhook_events_raw` (idempotente em `(provider, external_id)`).
2. Handler enfileira task Celery na fila `whatsapp_inbound`.
3. Worker normaliza para `ReceivedMessage`, encontra/cria conversa por telefone, persiste `WhatsAppMessage`, enfileira task de turno do agente.
4. Mídia baixada para o MinIO antes de OCR/classificação.
5. `external_id` duplicado -> `{"status":"duplicate"}`, sem efeitos colaterais.

### Story 6.4: Engine do Agente IA com RAG (Core + Module Hooks)

Como desenvolvedor Backend,
quero um agente conversacional com contexto rico do cliente e ferramentas injetadas por módulo,
para que respostas sejam personalizadas, conscientes da política e capazes no domínio.

**Critérios de Aceite:**

1. Port `ILLMProvider`: semântica `chat`/`tool_call`. Adapters: `OpenAiAdapter` (padrão), `AnthropicAdapter`, `GeminiAdapter`, `OllamaAdapter`, `LiteLlmAdapter`.
2. Configuração em Configurações > Agente: provider, model, temperature, max tokens.
3. **Dada** mensagem recebida, **Quando** turno do agente roda, **Então** prompt composto a partir de: registro do cliente, parcelas em aberto/vencidas com valores atualizados, score, últimas N mensagens, política de cobrança ativa, notas do gestor.
4. Mensagens antigas são vetorizadas assincronamente no pgvector; top-K chunks similares são recuperados para enriquecer o prompt.
5. System prompt parametrizado por tom, persona, regras, lista de ferramentas.
6. **Ferramentas core de function-calling**: `consultar_titulos_em_aberto`, `enviar_qr_pix`, `registrar_baixa_primaria`, `solicitar_validacao_humana`, `agendar_cobranca`, `gerar_acordo`, `escalar_para_gestor`.
7. **Ferramentas injetadas por módulo**: carregadas dinamicamente via `IAssetModule.get_collection_tools()` no startup do agente. Ex.: Módulo de Veículos injeta `bloquear_veiculo` (gated: score < threshold E dias_atraso >= X E aprovação humana conforme política), `desbloquear_veiculo`, `verificar_localizacao_veiculo`.
8. Cada turno escreve em `agent_runs` (provider, model, tokens, latency, tools_called, final_action, error, cost_usd).
9. Feature flag `AGENT_DRY_RUN`: gera mas não envia — enfileirado para revisão humana (modo calibração).

### Story 6.5: UI de Parametrização do Agente (Core + Module Hooks)

Como Admin,
quero configurar tom, regras e modelos de mensagem do agente,
para que ele represente a voz do meu negócio.

**Critérios de Aceite:**

1. Rota `/system/config/agent` com seções: **Persona** (nome, slider de tom com exemplo ao vivo, saudações por horário do dia), **Janela de Atendimento** (horários, dias), **Cobrança Preventiva** (dias de antecedência + template), **Pós-Vencimento** (templates D+1/D+3/D+7 com toggles), **Política de Concessão por Score** (tabela editável: score_min, score_max, days_tolerance, requires_human_approval), defaults de **Juros e Multa**, **Templates** (editor Tiptap com placeholders + preview).
2. **Políticas específicas de módulo**: cada módulo ativo pode registrar seções de política adicionais. Ex.: Módulo de Veículos adiciona "Bloqueio Remoto" (toggle ativo + condições: `dias_atraso >= X` E `score < Y` + exige-aprovação-humana).
3. Toda mudança grava registro versionado com diff no log de auditoria.
4. Botão "Mensagem de Teste" gera uma resposta-exemplo contra um cliente fictício.

### Story 6.6: Cálculo do Score do Cliente (Core + Module Hooks)

Como desenvolvedor Backend,
quero um score por cliente recalculado periodicamente,
para que decisões do agente sejam orientadas por dados.

**Critérios de Aceite:**

1. Job diário do Celery beat (`0 2 * * *`) recalcula score 0-100 usando: pontualidade 12m (60%), média de dias em atraso (20% invertido), tempo de relacionamento (10% bônus), valor histórico pago (10%).
2. **Contribuição de módulo**: módulos ativos podem adicionar fatores de score via `IAssetModule`. Ex.: Módulo de Veículos adiciona "quantidade de bloqueios prévios" como fator de penalidade.
3. Fórmula configurável em Configurações > Score (pesos editáveis).
4. `customer_score_history` registra snapshot diário com breakdown de fatores.
5. Aba "Score" do cliente plota gráfico de evolução.

### Story 6.7: Caixa de Entrada In-App Estilo WhatsApp (Core)

Como Gestor,
quero ver e responder conversas em uma interface familiar,
para que a passagem para o humano seja fluida.

**Critérios de Aceite:**

1. Rota `/system/inbox` com layout em 3 painéis:
   - **Esquerdo (320 px)**: conversas com avatar, nome, última mensagem, timestamp, badge de não lidas, ícone de status do agente.
   - **Central (flex)**: thread de mensagens com balões (verde-saída / branco-entrada), separadores de dia, timestamps, ticks, lightbox de imagem, player de áudio, preview de PDF.
   - **Direito (340 px, colapsável)**: contexto do cliente (avatar, nome, score, status, títulos em aberto com valores atualizados, ações rápidas: Gerar Pix, Marcar como Pago, Escalar).
2. Input de chat: anexos, emojis, gravação de áudio.
3. Toggle no header: pausar/retomar agente na conversa ativa.
4. Entrega de mensagens em tempo real via WebSocket.
5. Teclado: setas navegam conversas, `Ctrl+Enter` envia, `/` foca busca.
6. Busca dentro da conversa (textual).
7. Indicador "Agente está digitando..." enquanto processa.

### Story 6.8: Disparo em Massa Controlado (Core)

Como Gestor,
quero disparar cobranças preventivas a todos os clientes que vencem amanhã,
para economizar tempo em escala.

**Critérios de Aceite:**

1. Rota `/system/inbox/broadcast` com filtros de audiência e preview ao vivo de destinatários.
2. Editor de mensagem com placeholders.
3. Modal de dupla confirmação (com senha) + 3 renderizações de amostra.
4. Janela de tempo + envios escalonados (1 a cada X segundos) para evitar banimentos.
5. Relatório pós-disparo: enviadas/entregues/lidas/falhas/respondidas (atualizado via webhooks).
6. Limite duro de 200 destinatários por disparo (anti-spam).

### Story 6.9: Detecção de Comprovante e Baixa Primária via Agente (Core)

Como Cliente,
quero meu título considerado pago assim que enviar um comprovante pelo WhatsApp,
para receber confirmação instantânea.

**Critérios de Aceite:**

1. Mídia recebida classificada via heurística (imagem/PDF + OCR detecta padrões Pix).
2. **Dado** comprovante detectado, **Então** agente extrai valor + data + ID da transação, encontra título mais provável (cliente + valor + janela de data), chama `registrar_baixa_primaria`.
3. **Dado** valor pago < valor do título, **Então** agente executa baixa parcial (lógica da Story 4.4): pagamento parcial registrado, novo título para a diferença gerado. Agente informa cliente do pagamento parcial e saldo restante.
4. **Dada** baixa total bem-sucedida, **Então** agente responde com template de confirmação. Parcela adicionada à fila de validação (Story 4.6).
5. **Dado** match ambíguo, **Então** agente pergunta ao cliente em linguagem natural ou escala para o gestor.

### Story 6.10: Canal de Chat In-App para Orquestrador de Agentes (Core)

Como Gestor,
quero conversar com o Orquestrador de Agentes diretamente na UI web,
para emitir comandos sem abrir o WhatsApp.

**Critérios de Aceite:**

1. Botão "Chat com Agente" no header do app abre um drawer/painel de chat.
2. O chat usa o mesmo pipeline do Orquestrador de Agentes — mesmas ferramentas, mesmo RBAC, mesma LLM.
3. O canal é identificado como `in_app` (vs `whatsapp`) em `AgentInput`.
4. Mensagens são persistidas em uma conversa separada com `channel='in_app'`.
5. O JWT do gestor fornece o contexto RBAC (sem necessidade de lookup de número de telefone).
6. Suporta entrada de texto; upload de imagem/arquivo para envio de comprovante.

### Story 6.11: Transcrição de Áudio para o Orquestrador de Agentes (Core)

Como Usuário,
quero enviar mensagens de áudio que o agente entenda,
para interagir hands-free.

**Critérios de Aceite:**

1. Port `IAudioTranscriber` definida em `app/domain/ports/audio_transcriber.py`.
2. `WhisperApiAdapter` (padrão) chama OpenAI Whisper API com language='pt-BR'.
3. `ConsoleTranscriberAdapter` para dev (retorna texto placeholder).
4. Pipeline de inbound: quando uma mensagem WhatsApp tem áudio, transcrever ANTES de passar ao Orquestrador de Agentes.
5. Chat in-app: gravação de áudio via API MediaRecorder do browser, enviado como blob, transcrito no servidor.
6. Resultado da transcrição é armazenado junto à mensagem em `whatsapp_messages.transcription` (campo TEXT nullable).

---

## Épico 7: Conciliação Bancária Sofisticada (Core)

**Objetivo:** No fim do mês (ou diariamente), o gestor concilia o extrato bancário com os títulos do sistema em uma tela com painéis lado a lado e drag-and-drop com auto-match, suportando OFX, PDF e Open Finance.

### Story 7.0: Cadastro de Conta Bancária (Core)

Como Gestor,
quero cadastrar minhas contas bancárias no sistema,
para que transações importadas sejam vinculadas à conta correta.

**Critérios de Aceite:**

1. Tabela `bank_accounts`: id UUID PK, name TEXT, bank_code VARCHAR(5), agency VARCHAR(10), account_number VARCHAR(20), type TEXT, is_active BOOLEAN DEFAULT TRUE, created_at TIMESTAMPTZ.
2. API CRUD sob `/api/v1/bank-accounts` com permissão de Admin.
3. UI em Configurações > Empresa > "Contas Bancárias" com lista + formulário criar/editar.
4. Pelo menos uma conta bancária deve existir antes de a importação OFX/PDF ser permitida.

### Story 7.1: Importador OFX (Core)

Como Gestor,
quero subir um arquivo OFX do meu banco,
para que transações entrem no sistema automaticamente.

**Critérios de Aceite:**

1. Rota `/system/finance/reconciliation` expõe botão "Importar OFX".
2. Drop-zone aceita `.ofx`; parsing via `ofxparse`.
3. **Dados** FITIDs sobrepostos, **Então** transações existentes são puladas (deduplicação).
4. Tabela `bank_transactions`: id, account_id, fitid, posted_at, amount (signed), description_raw, description_clean, type, status (`pendente`/`conciliada`/`ignorada`), reconciled_to_kind, reconciled_to_id, imported_from (`ofx`/`pdf`/`open_finance`/`manual`), imported_at; `UNIQUE(account_id, fitid)`.
5. Pré-classificação: regex/heurísticas extraem nome do remetente de descrições Pix.

### Story 7.2: Importador Inteligente de PDF (Core)

Como Gestor,
quero subir um extrato em PDF,
para que mesmo bancos sem suporte a OFX funcionem.

**Critérios de Aceite:**

1. Drop-zone aceita `.pdf`. Backend: `pdfplumber` + heurísticas por banco (BB, Itaú, Bradesco, Santander, Caixa, Nubank, Inter, C6).
2. **Dada** confiança das heurísticas < 80%, **Quando** fallback LLM habilitado, **Então** LLM é chamada com prompt JSON estruturado; caso contrário tela de revisão manual.
3. Chamada LLM controlada por feature flag com métrica de tracking de custo.
4. Tela de revisão: marcar/desmarcar linhas suspeitas antes de persistir.
5. Linhas persistidas em `bank_transactions` com `imported_from='pdf'`.

### Story 7.3: Adapter Open Finance — Pluggy Padrão (Core)

> **Escopo MVP:** Apenas PluggyAdapter é exigido se habilitado. BelvoAdapter e TecnoSpeedAdapter são V2.

Como Admin,
quero conectar opcionalmente o Open Finance,
para que extratos cheguem automaticamente.

**Critérios de Aceite:**

1. Port `IBankReconciliationProvider`: `connect_account`, `list_accounts`, `fetch_transactions`, `disconnect`.
2. `PluggyAdapter` (padrão); `BelvoAdapter`, `TecnoSpeedAdapter` alternativos.
3. Configurações > Integrações: fluxo "Conectar conta" com widget Pluggy Connect.
4. Celery beat: sync incremental a cada 6 horas.
5. Padrão: **desabilitado** (preocupação com custo).

### Story 7.4: Tela de Conciliação Drag-and-Drop (Core)

Como Gestor,
quero conciliar transações com títulos arrastando-os,
para que o trabalho seja rápido e visual.

**Critérios de Aceite:**

1. Rota `/system/finance/reconciliation` com split 50/50:
   - **Esquerda**: transações bancárias (status=pendente, filtrável por data/valor/tipo).
   - **Direita**: títulos do sistema (parcelas + títulos a pagar em `pago_aguardando_verificacao`).
2. Arrastar linha de um lado para o outro -> modal de confirmação com diff.
3. Auto-match: `score = valor_exato(60%) + janela_data(30%) + match_descricao(10%)`; score >= 0,85 destacado com badge "match sugerido".
4. Botão "Aceitar todas as sugestões" para match em lote.
5. Conciliação N:1 e 1:N suportadas (multi-select + drop).
6. Transação não casada -> converter em título a pagar ou receita livre.
7. Na confirmação: título -> `pago` (imutável), transação -> `conciliada` (travada).
8. Indicadores no topo: transações pendentes, títulos pendentes, conciliados hoje.

### Story 7.5: Detecção de Divergências (Core)

Como o Sistema,
quero sinalizar inconsistências,
para que o gestor possa investigar.

**Critérios de Aceite:**

1. Painel de "Alertas" no topo da tela com três categorias:
   - Transações sem título compatível (receita órfã ou erro do banco).
   - Títulos marcados como `pago` sem transação correspondente (suspeitos).
   - Mismatches de valor entre transação e título candidato.
2. Clique no alerta -> painel de investigação contextual.

---

## Épico 8: Dashboards, Relatórios e Analytics de Ativos (Core + Module Hooks)

**Objetivo:** O gestor tem visão executiva consolidada e drilldown em qualquer nível, com relatórios prontos e um construtor customizado. Módulos verticais injetam widgets e relatórios específicos de domínio via `IAssetModule.get_dashboard_widgets()` e `IAssetModule.get_report_dimensions()`.

### Story 8.0: Materialized Views e Camada de Dados do Dashboard (Core)

Como Desenvolvedor,
quero materialized views para queries pesadas de dashboard,
para que dashboards carreguem em menos de 1,5s.

**Critérios de Aceite:**

1. Migration Alembic cria materialized view `mv_asset_roi` (como definido na Seção 9.9 da Arquitetura).
2. Job do Celery Beat atualiza `mv_asset_roi` diariamente às 05:00 via `REFRESH MATERIALIZED VIEW CONCURRENTLY`.
3. Endpoint `POST /api/v1/admin/refresh-views` permite ao Admin forçar atualização manualmente.
4. Índice na materialized view para lookups rápidos.

### Story 8.1: Dashboard Principal (Core + Module Hooks)

Como Gestor,
quero ver KPIs do negócio em uma única tela,
para ler o pulso operacional instantaneamente.

**Critérios de Aceite:**

1. Rota `/system/dashboard` com grid de cards responsivo:
   - **KPIs Core**: Receita Mensal (atual vs anterior, % delta), Despesas Mensais, Lucro Líquido, Inadimplência (R$ + %), Ativos em Uso, Ativos Ociosos, Total de Ativos (R$), Títulos a Receber dos Próximos 7 Dias, Comprovantes Pendentes, Score Médio da Carteira.
   - **Widgets injetados por módulo**: renderizados via `IAssetModule.get_dashboard_widgets()`. Ex.: Módulo de Veículos injeta: Total da Frota (R$ FIPE consolidado), Veículos Ativos, Parados, Em Manutenção.
2. Cards reativos via Signals + `resource()`; atualizam a cada 60 s ou push via SSE.
3. Clique no card faz deep-link para lista de entidades filtrada.
4. Toggle de período: Hoje | Esta Semana | Este Mês | Este Trimestre | Este Ano.
5. Gráficos: linha de receita de 12 meses, donut de despesas por categoria, barras de inadimplência por aging.

### Story 8.2: Dashboard do Cliente (Core)

Como Gestor,
quero um dashboard financeiro por cliente,
para negociar com dados.

**Critérios de Aceite:**

1. Aba "Dashboard" na página de detalhe do cliente.
2. Cards: Total Contratado, Total Pago, Total em Aberto, Total Vencido, Score Atual (gauge), Pontualidade % (12m).
3. Gráfico de timeline: cada pagamento colorido por status.
4. Tabela: contratos vigentes com saldos e ROI por contrato.
5. "Exportar histórico do cliente" -> PDF.

### Story 8.3: Dashboard de Veículo (Módulo de Veículos)

Como Gestor,
quero analisar a viabilidade de cada veículo,
para decidir sobre venda/substituição.

**Critérios de Aceite:**

1. Aba "Análise" na página de detalhe do veículo (injetada pelo Módulo de Veículos).
2. Cards: Investimento, FIPE Atual, Depreciação, Total Recebido, ROI %, Lucro Acumulado, Payback em meses.
3. Lê da materialized view `mv_asset_roi`; job do Celery atualiza no schedule.
4. Gráfico de linha: investimento acumulado vs receita acumulada.
5. **Dado** que o rastreador fornece KM, **Então** produtividade R$/dia e R$/km exibida.
6. Timeline de motoristas que usaram o veículo.

### Story 8.4: Relatórios Pré-Prontos (Core + Module Hooks)

Como Gestor,
quero relatórios prontos,
para que análises de rotina sejam a um clique de distância.

**Critérios de Aceite:**

1. Rota `/system/reports` com cards para:
   - **Relatórios core**: Top Clientes por Receita (12m), Aging de Inadimplência, DRE Consolidado e por Ativo, Curva ABC de Clientes.
   - **Relatórios de módulo** (via `IAssetModule.get_report_dimensions()`): Ex.: Módulo de Veículos adiciona: Top Veículos por ROI (12m), Histórico de Bloqueios Remotos, snapshot de Posição da Frota (data X).
2. Cada relatório abre em visualizador com filtros, gráficos, tabela.
3. Exportação para Excel (formatado) e PDF (header/footer).
4. Relatórios pesados: geração por Celery worker + notificação SSE quando pronto.

### Story 8.5: Construtor de Relatórios Customizados (Core)

> **V2 — Adiada para pós-lançamento.** Relatórios prontos (Story 8.4) cobrem as necessidades do MVP.

Como Gestor avançado,
quero compor meus próprios relatórios,
para não depender de engenharia para novas análises.

**Critérios de Aceite:**

1. Rota `/system/reports/builder` com três zonas drag-and-drop:
   - **Dimensões Disponíveis**: cliente, ativo, contrato, categoria, mês, status, etc. + dimensões registradas por módulos.
   - Targets de **Linhas** e **Colunas**.
   - **Medidas** (count, sum, avg, min, max de campos numéricos).
2. Filtros: faixa de data, status, cliente.
3. Tabela de preview atualiza ao vivo.
4. "Salvar como" persiste em `saved_reports`.

---

## Épico 9: Hardening, Plug-and-Play e Documentação Final (Core)

**Objetivo:** Os últimos 20% que separam demo de produção: auditoria completa com verificação de integridade, painel de integrações funcional, observabilidade, testes de carga, polimento de UX, documentação de módulos e guia de adapter.

### Story 9.1: Painel Centralizado de Integrações (Core)

Como Admin,
quero uma única tela para gerenciar todas as integrações,
para que o plug-and-play seja operacionalmente real.

**Critérios de Aceite:**

1. Rota `/system/config/integrations` com cards por categoria: WhatsApp Gateway, Open Finance / Bancos, Payment Gateway, Provedor LLM, Provedor OCR, Storage, Renderizador PDF. Integrações específicas de módulo: ex.: Módulo de Veículos adiciona FIPE, Rastreador.
2. Cada card: provider ativo, status (saudável/degradado/erro), ações: "Testar conexão", "Trocar provider", "Configurar".
3. "Trocar provider": dialog lista adapters disponíveis com credenciais exigidas.
4. Credenciais criptografadas em repouso (AES-256-GCM com master key).
5. Toda mudança grava diff no log de auditoria com segredos mascarados.
6. `GET /api/v1/integrations/health` retorna status de cada provider.

### Story 9.2: Busca e Visualizador de Log de Auditoria (Core)

Como Auditor,
quero consultar todo o histórico de ações,
para rastrear qualquer evento.

**Critérios de Aceite:**

1. Rota `/system/audit` com tabela pesquisável: usuário, ação, entidade, data, IP, payload.
2. Filtros: usuário, entidade, ação (multi-select), faixa de data.
3. Expandir linha: diff de payload antes/depois em JSON pretty-print colapsável.
4. Indicador de integridade: "OK" se HMAC verifica, "ALERTA: adulterado" se não.
5. Exportação CSV respeita filtro ativo.

### Story 9.3: UI de Gerenciamento de Módulos (Core)

Como Admin,
quero ativar/desativar módulos verticais e configurar seus hooks,
para que a plataforma se adapte às necessidades do meu negócio.

**Critérios de Aceite:**

1. Rota `/system/config/modules` lista módulos registrados com: nome, status (ativo/inativo), toggle, botão "Configurar".
2. **Dado** toggle desligado, **Então** módulo para de receber eventos, seus hooks são desativados, suas seções/abas/widgets de UI desaparecem, menus escondem itens específicos do módulo.
3. **Dado** toggle ligado, **Então** módulo registra, recebe eventos, seções de UI aparecem.
4. "Configurar" abre configurações específicas do módulo (ex.: Módulo de Veículos: thresholds da política de bloqueio, schedule de refresh FIPE).
5. Configuração de hooks: lista de eventos aos quais o módulo se inscreve, com editor de política por evento.

### Story 9.4: Backup, Restore e DR (Core)

Como Operador,
quero backups automáticos verificados,
para que desastres sejam recuperáveis dentro do SLA.

**Critérios de Aceite:**

1. Celery beat diário às 03:00: `pg_dump`, comprime, envia para off-site (S3/B2/Wasabi, configurável), retenção de 30 dias.
2. Arquivamento contínuo de WAL via wal-g ou pgBackRest.
3. Teste de restore semanal em ambiente isolado com smoke tests; falhas alertam admins.
4. `RUNBOOK_DR.md` commitado com playbook de restore passo a passo (RTO < 4h).

### Story 9.5: Observabilidade Completa (Core)

Como Operador,
quero dashboards Grafana e alertas,
para operar o sistema com confiança.

**Critérios de Aceite:**

1. Métricas Prometheus em `/metrics`: contagem de requests por rota, histogramas de latência, profundidade de fila, erros, conexões DB.
2. Tracing OpenTelemetry; traces em Jaeger ou Tempo.
3. Logs JSON estruturados com propagação de `correlation_id`.
4. Dashboards Grafana (API Overview, DB, Workers, Business, Agente IA) em `infra/observability/grafana/`.
5. Regras do Alertmanager: API 5xx > 1% (5m), P95 > 1s (10m), fila Celery > 1000 (5m), pool de conn DB > 90% (5m), disco > 85%, falhas de webhook > 5% (10m), gasto diário do LLM do agente acima do threshold.

### Story 9.6: Testes de Carga e Tuning de Performance (Core)

Como o Time,
quero validar que o sistema aguenta a carga prevista,
para que o lançamento seja seguro.

**Critérios de Aceite:**

1. Suite k6 em `tests/load/` cobrindo: dashboard, lista de títulos a receber, baixa, conciliação.
2. Targets validados: 100 RPS sustentados, P95 <= 300 ms (leitura), 500 ms (escrita).
3. Mudanças de otimização documentadas: índices, reescritas de query, caching, paginação por cursor.

### Story 9.7: Documentação Final (Core)

Como o Próximo Desenvolvedor,
quero documentação completa,
para manter o produto sem o autor original.

**Critérios de Aceite:**

1. `README.md` permite setup local em < 10 minutos.
2. `ARCHITECTURE.md` revisado e versionado.
3. `ADAPTERS.md`: guia "como adicionar um novo adapter" para cada Port.
4. `MODULES.md`: guia "como criar um novo módulo vertical", cobrindo implementação de `IAssetModule`, registro de hook, extensões de schema, pontos de injeção de UI.
5. OpenAPI em `/docs` com snapshot em `API.md`.
6. `DEPLOYMENT.md` playbook de deploy.
7. `RUNBOOK.md` guia de troubleshooting.
8. ADRs `0001`-`0010` sob `docs/adrs/` (Hexagonal, split SSE+WS, pgvector, Celery, Evolution, Tesseract OCR, Pix sem gateway por padrão, trigger PG de imutabilidade de parcela paga, Single-tenant first, Camada de Abstração de Ativos).

> **Escopo MVP:** Apenas ADRs 0008 (imutabilidade de parcela paga) e 0010 (dois repos paralelos) são exigidos pré-lançamento. Outras podem ser escritas retroativamente.

### Story 9.8: Polimento UX e Microinterações (Core)

> **Escopo MVP:** axe-core no CI, skeleton loaders e empty states são MVP. Animações FLIP, View Transitions e rollback de UI otimista são V2.

Como Usuário,
quero o app polido,
para que a experiência seja agradável no uso diário.

**Critérios de Aceite:**

1. Animações de transição de página (FLIP / View Transitions API onde suportado).
2. Skeleton loaders em toda lista e card.
3. Toasts: fila unificada com auto-dismiss.
4. Empty states (ilustração + CTA) em toda lista.
5. Modais respeitam `prefers-reduced-motion`.
6. Atualizações otimistas com rollback no erro.
7. axe-core no CI com zero violações críticas.
8. Revisão mobile em 375 px e 768 px tela a tela.

### Story 9.9: Configuração Versionada e Consolidação de Configurações (Core)

Como Admin,
quero todas as configurações versionadas com histórico de mudanças,
para auditar quem mudou o quê e quando.

**Critérios de Aceite:**

1. Toda seção de configuração (Empresa, Cobrança, Agente, Integrações, Módulos, Permissões, Templates) mantém histórico versionado com quem, quando e valor anterior.
2. Rota `/system/config/history` mostra log de mudanças de configuração com visualizador de diff.
3. Tela de Configurações consolidada em `/system/config` com todas as seções.

### Story 9.10: Self-Service LGPD "Meus Dados" (Core)

Como Cliente (externo),
quero exportar ou solicitar exclusão dos meus dados pessoais,
para que o sistema esteja em conformidade com a LGPD.

**Critérios de Aceite:**

1. Endpoint `GET /api/v1/customers/{id}/data-export` gera um ZIP com todos os dados pessoais (perfil, contratos, títulos, mensagens, anexos).
2. Endpoint `POST /api/v1/customers/{id}/anonymize` substitui campos pessoais por "[redigido]", mascara CPF, remove fotos — preservando histórico financeiro para auditoria.
3. Anonimização exige papel Admin + motivo + entrada no log de auditoria com category='security'.
4. Uma página simples "Meus Dados" acessível via um link único enviado ao cliente (sem login completo no app — acesso baseado em token).
5. A página mostra: resumo de dados pessoais, botão "Exportar Dados", botão "Solicitar Exclusão" (envia request ao Admin para revisão).

### Story 9.11: Command Palette (Ctrl+K) (Core)

Como Gestor,
quero um command palette global para navegação e ações instantâneas,
para nunca precisar caçar uma tela ou ação.

**Critérios de Aceite:**

1. `Ctrl+K` (ou `Cmd+K` no Mac) abre overlay `<ui-command-palette>` em qualquer lugar do app.
2. Modos de busca: padrão (busca fuzzy em clientes, veículos, contratos, títulos por nome/CPF/placa/número), prefixo `>` para ações ("baixar título 1234"), `#` para títulos por número, `@` para clientes.
3. Resultados atualizam ao vivo com debounce 200ms; navegação por teclado (↑/↓/Enter/Esc).
4. Buscas recentes persistidas no localStorage (últimas 10).
5. Componente vive em `frontend/src/app/shared/components/command-palette/`.
6. Endpoint backend `GET /api/v1/search?q=&type=` retorna resultados de busca unificada entre entidades.

---

## Épico 10: Motor de Recorrência, Cobrança Automatizada e Saúde de Canais (Core)

Este épico implementa a espinha dorsal operacional automatizada: geração de títulos recorrentes (com correção monetária), ciclo de vida de rascunho de título a pagar, motor completo de cobrança (lembretes pré-vencimento → escalonamento de vencidos → bloqueio GPS), gestão de modelos de mensagem, monitoramento de saúde de canais, consolidação do scheduler de workers, auto-cadastro de usuário e componente de modal reutilizável.

### Story 10.1: Geração Mensal de Parcelas com Índice de Correção (Core)

Como Sistema,
quero gerar parcelas mensalmente aplicando o índice de correção atual,
para que contratos com correção monetária tenham valores precisos a cada mês.

**Critérios de Aceite:**

1. Model de contrato estendido com `generation_mode` (upfront | monthly), `correction_index` (igpm | ipca | inpc | null), `generation_day` (1-28), `next_generation_date`.
2. Port `ICorrectionIndexProvider` com `get_current_rate(index, reference_date) -> Decimal`.
3. `BcbCorrectionAdapter` busca taxas da API do BCB (Banco Central do Brasil) — pública, sem auth. Séries: IGPM=189, IPCA=433, INPC=188. Cache no Redis TTL 30 dias.
4. Task do Celery Beat `generate_monthly_installments` roda diariamente às 06:00.
5. Task é idempotente — verifica se parcela para aquele período já existe.
6. Fallback: se BCB indisponível, usa última taxa cacheada + loga warning.

### Story 10.2: Ciclo de Vida de Rascunho de Título a Pagar (Core)

Como Gestor,
quero títulos a pagar recorrentes gerados como rascunhos que eu posso preencher e salvar,
para que o sistema me lembre de despesas fixas sem exigir valores exatos antecipadamente.

**Critérios de Aceite:**

1. Ciclo de vida de status do título a pagar imposto: `rascunho` → `pendente` → `pago` | `cancelado`.
2. `rascunho`: pode editar todos os campos, pode DELETE (hard delete permitido).
3. `pendente`: pode editar, pagar ou cancelar (soft — nunca hard delete, preserva trilha de auditoria).
4. `pago` e `cancelado`: imutáveis.
5. Template recorrente gera títulos a pagar com `status=rascunho`.
6. Notificação SSE para o gestor quando um rascunho é gerado.

### Story 10.3: Motor de Cobrança Automatizada (Core)

Como Sistema,
quero enviar lembretes de pagamento automaticamente antes do vencimento e escalonar parcelas vencidas,
para que a cobrança aconteça sem intervenção manual.

**Critérios de Aceite:**

1. `collection_policy` em system_settings: `reminder_days_before`, `overdue_escalation` (array de {days, action, template_id}), `agent_can_negotiate`, `agent_max_grace_days`, taxas de juros/multa.
2. Task Celery `check_upcoming_due_dates` (diária 08:00): envia lembrete via WhatsApp N dias antes do vencimento.
3. Task Celery `check_overdue_installments` (diária 09:00): atualiza status para `vencido`, executa escalonamento conforme política (lembrete → avisar_bloqueio → bloquear → notificar_gestor).
4. Task Celery `check_paid_installments` (a cada 30 min): detecta pagamentos, envia confirmação, dispara desbloqueio.
5. Todas as mensagens enviadas via `IMessageChannel` (channel registry), não adapter direto.
6. Orquestrador de agentes trata respostas do cliente com autonomia de negociação (max grace days configurável).
7. Frontend: página de config de política de cobrança em `/system/settings/collection`.

### Story 10.4: Gestão de Modelos de Mensagem (Core)

Como Gestor,
quero criar e gerenciar modelos de mensagem para cada estágio de cobrança,
para customizar o tom e conteúdo de mensagens automatizadas.

**Critérios de Aceite:**

1. Tabela `message_templates`: name, channel, trigger (upcoming_due | overdue_d1 | warn_block | payment_confirmed | custom), body, variables.
2. Endpoints CRUD para templates.
3. Templates padrão populados em português.
4. Preview de template com dados-exemplo.
5. Variáveis: {nome}, {valor}, {valor_atualizado}, {data_vencimento}, {dias_atraso}, {placa}, {contrato}, {link_pagamento}.

### Story 10.5: Monitoramento de Saúde de Canais (Core)

Como Gestor,
quero ver quais canais de mensagem estão configurados e saudáveis,
para saber se minha cobrança automatizada vai funcionar.

**Critérios de Aceite:**

1. Task Celery `check_channel_health` roda a cada 5 minutos — chama `health_check()` em todos os canais registrados via `ChannelRegistry`.
2. Widget de dashboard mostrando status dos canais com badges verde/amarelo/vermelho.
3. Notificação SSE quando um canal fica não-saudável.
4. Configurações > Integrações mostra saúde em tempo real por canal com latência.

### Story 10.6: Consolidação do Scheduler de Workers (Core)

Como Administrador de Sistema,
quero todas as tasks agendadas consolidadas com timing crontab apropriado e um dashboard de monitoramento,
para verificar que todas as automações estão rodando corretamente.

**Critérios de Aceite:**

1. Todas as tasks do Celery Beat usam `crontab()` com horários exatos (03:00 backup, 04:00 títulos a pagar recorrentes, 05:00 scores, 06:00 parcelas mensais, 08:00 vencimentos próximos, 09:00 vencidos, */30 check de pagos, */5 saúde de canais, */60 refresh de views).
2. Endpoint Admin lista todas as tasks agendadas com última execução, próxima execução, status.
3. Frontend: página "Tarefas Agendadas" mostrando schedule e status de execução de cada task.

### Story 10.7: Cadastro de Usuário e Verificação por Email (Core)

Como novo Usuário,
quero cadastrar uma conta e verificar meu email,
para acessar o sistema com segurança.

**Critérios de Aceite:**

1. `POST /auth/register` — cria usuário com `is_active=false`, envia email de verificação.
2. `POST /auth/verify-email` — ativa conta de usuário (token de uso único, TTL 1h).
3. `POST /auth/resend-verification` — rate limited (3/hora), sempre retorna 200.
4. Login com email não verificado retorna 403.
5. Frontend: wizard de cadastro em 3 passos (glassmorphism), página verify-email, página resend-verification.

### Story 10.8: Componente de Modal Reutilizável (Core)

Como Desenvolvedor,
quero um único componente de modal reutilizável que trate ESC, clique no backdrop, z-index e animação,
para nunca repetir boilerplate de modal em cada componente.

**Critérios de Aceite:**

1. `ModalComponent` em `shared/components/modal/` com inputs: `[open]`, `[size]`, `[title]`.
2. Output: `(closed)` em ESC, clique no backdrop ou botão X.
3. Built-in: z-index, backdrop, animação fade+scale, auto-foco para captura de ESC.
4. Projeção de conteúdo via `<ng-content>` + `<ng-content select="[modal-footer]">`.
5. TODOS os 13 modais inline existentes substituídos por `<app-modal>`.

---

## Épico 11: Economia de Tokens do WhatsApp e Modos Operacionais (Core)

Este épico implementa a camada de economia de tokens sobre o Épico 6: três modos de operação (`ia-full` / `ia-eco` / `ia-zero`) com downgrade automático na exaustão do budget, roteamento determinístico de intenção sem LLM, menus interativos de WhatsApp, deduplicação de comprovantes com fila de validação manual, tratamento de áudio por modo, aprendizado de regras dirigido pelo gestor e tiers de plano. **Princípio operacional crítico: o sistema nunca para, mesmo quando a IA está totalmente esgotada (ia-zero).**

### Story 11.1: Budget de Tokens, Tracking e Motor de Throttle (Core)

Como Gestor do Tenant,
quero um budget mensal de tokens LLM com tracking ao vivo, alertas e downgrade automático de modo,
para nunca receber uma conta surpresa e para que a operação WhatsApp nunca pare quando a IA acabar.

**Critérios de Aceite:**

1. `system_settings.token_budget` JSONB com `monthly_limit_tokens`, `auto_throttle_enabled`, `thresholds`, `reset_day_of_month`.
2. Tabela `token_usage_monthly` faz upsert a partir de `agent_runs` (Story 6.4).
3. Task Celery `evaluate_token_throttle` (a cada 5 min) faz downgrade do modo quando o threshold é cruzado.
4. Reset mensal restaura `configured_mode` no dia 1 às 00:05.
5. Alertas SSE em 50%/75%/95% do budget.
6. Endpoints: `GET/PUT /api/v1/system/token-usage`, `/token-budget`.
7. Widget de dashboard + página de Configurações + banner persistente quando em throttle.
8. Anti-flap: override manual bloqueia auto-throttle pelo período atual.

### Story 11.2: Modos de Operação (ia-full / ia-eco / ia-zero) (Core)

Como Gestor do Tenant,
quero escolher quão agressivamente a IA participa das operações no WhatsApp,
para balancear experiência do cliente contra custo de tokens.

**Critérios de Aceite:**

1. Enum Postgres `operation_mode`: `ia_full`, `ia_eco`, `ia_zero`.
2. Matriz de capabilities controla cada chamada LLM/transcrição/visão.
3. `OperationModeService.is_allowed(capability)` consultado pelo orquestrador de agentes (Story 6.4).
4. Em `ia-zero`, inbound bypassa LLM e vai 100% para regras de intenção (Story 11.4).
5. UI mostra modo atual vs configurado com auto-restore no reset mensal.
6. Mudança de modo emite SSE + entrada em audit_log (category=security).
7. Badge no header com cor do modo (verde/amarelo/cinza).

### Story 11.3: Menu Interativo WhatsApp (List Messages e Reply Buttons) (Core)

Como Cliente,
quero escolher ações em um menu de botões/opções em vez de digitar,
para receber respostas mais rápidas e a empresa gastar menos em IA.

**Critérios de Aceite:**

1. Tabela `interactive_menus` com itens (action_type: send_template | show_submenu | call_function | handover_human).
2. `MenuRenderer` gera payload por adapter (Z-API / Uazapi / Evolution).
3. Limites do WhatsApp aplicados (Lista ≤10 itens, Botões ≤3, auto-fallback).
4. Menus padrão PT-BR populados (principal, pagamento, vencidos).
5. `interactive_response` recebido mapeado para ação via dispatcher.
6. Editor drag-drop + preview side-by-side + "Testar" envia para o número do gestor.
7. Em `ia-zero`, mensagens não casadas auto-respondem com main_menu.
8. Detecção da janela de 24h do WhatsApp (templates fora da janela).

### Story 11.4: Motor de Regras de Intenção (flashtext + rapidfuzz + regex) (Core)

Como Sistema,
quero classificar mensagens do cliente deterministicamente sem LLM,
para que possamos rotear para templates/menus/funções nos modos ia-eco e ia-zero com custo zero de tokens.

**Critérios de Aceite:**

1. Tabela `intent_rules` com match_type (keyword/regex/fuzzy), priority, action_type.
2. Serviço `IntentMatcher`: flashtext para keywords, `re` para regex, rapidfuzz para fuzzy.
3. Regras padrão PT-BR populadas (saudacao, pedido_boletos, comprovante_enviado, etc.).
4. Em `ia-zero`: apenas matcher, sem LLM. Em `ia-eco`: matcher primeiro, classificador LLM em desconhecidos (~50 tokens).
5. `intent_match_log` para estatísticas e aprendizado da Story 11.7.
6. UI para CRUD + drag-drop de prioridade + "Testar" + importação em lote.
7. Target de performance: p99 < 10ms para 500 regras por tenant.
8. Prevenção de ReDoS na validação de regex.

### Story 11.5: Deduplicação de Comprovante + Fila de Validação Manual (Core)

Como Sistema,
quero detectar comprovantes duplicados e enfileirar resultados de OCR de baixa confiança para validação humana com elegância,
para nunca creditar um pagamento em duplicidade e para que a operação continue mesmo quando o fallback LLM Vision está desabilitado.

**Critérios de Aceite:**

1. Tabela `receipt_fingerprints` com pHash + txn_id + confidence + status.
2. Detecção de duplicata: txn_id exato OU distância de Hamming pHash ≤5.
3. Baixa automática apenas quando confidence ≥70 E match único de candidato.
4. Em `ia-eco`/`ia-zero`: fallback LLM Vision desabilitado; baixa confiança → fila manual com template de notificação ao cliente.
5. Página `/system/receipts/pending` com modal de detalhe + ranking de candidatos.
6. Notificação SSE em novo item pendente.
7. Endpoints Aprovar / Rejeitar / Reatribuir com trilha de auditoria.

### Story 11.6: Tratamento de Áudio por Modo de Operação (Core)

Como Cliente,
quero que minhas mensagens de voz sejam transcritas (quando IA está ligada) ou desviadas com um menu amigável (quando IA está desligada),
para sempre receber resposta e a empresa ter custo previsível.

**Critérios de Aceite:**

1. Gate por modo: `ia-full`/`ia-eco` transcrevem; `ia-zero` desvia.
2. Template de desvio + follow-up imediato com `main_menu`.
3. 3 áudios desviados consecutivos → conversa marcada como `needs-attention`.
4. Inbox mostra áudios desviados com opção "Ouvir mesmo assim" para transcrição manual.
5. Toggle `transcribe_in_eco_mode` (default ON).
6. Config de duração máxima de áudio (default 5min) — auto-desvio mesmo em ia-full.

### Story 11.7: Detecção de Fora de Escopo e Aprendizado pelo Gestor (Core)

Como Gestor,
quero ver mensagens de cliente que o sistema não conseguiu classificar e facilmente transformar minha resposta manual em uma regra permanente,
para que o autopilot fique cada vez mais inteligente ao longo do tempo.

**Critérios de Aceite:**

1. Detecção de fora-de-escopo em todos os modos (hit no catch-all, LLM unknown, handover explícito).
2. Materialized view + página de top-50 mensagens agrupadas (Configurações → Aprendizado).
3. Botão inline "Salvar como regra" em mensagens do inbox flagueadas como out_of_scope.
4. Sugestão de keyword via IDF (sem LLM) + filtro de stop words PT-BR.
5. Quick-form (não wizard) para criar regra a partir de uma mensagem em 2 cliques.
6. Widget de dashboard: "X fora-de-escopo esta semana — Treinar agora".

### Story 11.8: UI de Tiers de Plano e Quotas (Core)

Como Gestor do Tenant,
quero ver em qual plano estou, o que cada plano inclui e o que destravaria fazendo upgrade,
para decidir se aumento meu budget quando atingir os limites.

**Critérios de Aceite:**

1. Tabela `plan_tiers` system-wide (Starter / Pro / Business / Enterprise) com matriz de features + limites de tokens/msg.
2. FK `tenants.plan_tier_id`.
3. `PlanService.is_feature_included()` controla ativação de feature (ex.: Starter não pode setar `ia-full`).
4. `effective_token_limit` = min(limite do plano, setting do gestor).
5. Configurações → Plano: comparador horizontal + modal de upgrade (V1 mailto, V2 billing real).
6. Feature gates na edição do budget de tokens, mudança de modo, seleção de provider LLM.
7. Entradas no log de auditoria em mudança de plano (category=billing).

---

## 🔴 PRIORIDADE ALTA: Tradução PT-BR de Artefatos de Planejamento (decisão 2026-05-24)

> **Decisão de Pablo (2026-05-24):** "Eu não estou entendendo o que está escrito nas stories porque está tudo em inglês e eu não domino o inglês. Coloque no roadmap para, assim que possível, fazermos essa tradução, e a partir de agora deixe configurado para documentar tudo em português."
>
> Config `_bmad/bmm/config.yaml` já foi mudado para `document_output_language: Portuguese`. Documentos NOVOS já saem em PT-BR. Falta traduzir o backlog existente.

### História 12.9: Tradução PT-BR de Artefatos de Planejamento e Stories

**Status:** ready-for-dev (alta prioridade — sem isso, Pablo não consegue revisar nenhuma story)

**Como** product owner que precisa revisar e aprovar cada história antes da implementação,
**quero** que todo o backlog (PRD, épicos, stories) esteja em português,
**para** poder ler, entender e validar o conteúdo sem depender de tradução manual.

**Critérios de aceite:**

1. `_bmad-output/planning-artifacts/PRD.md` traduzido integralmente para PT-BR (terminologia técnica consagrada permanece em inglês: HTTP, JWT, Celery, FastAPI, REST, etc.).
2. `_bmad-output/planning-artifacts/ARCHITECTURE.md` traduzido integralmente para PT-BR.
3. `_bmad-output/planning-artifacts/epics.md`: títulos e descrições de épicos 1 a 11 (que ainda estão em inglês) traduzidos para PT-BR. Épicos 12, 13 e 14 já estão em PT-BR — manter.
4. `_bmad-output/implementation-artifacts/*.md`: todas as stories `ready-for-dev` ou `backlog` traduzidas. Stories `done` podem ficar como estão (não vamos reescrever histórico) — exceção: títulos no sprint-status.yaml ficam como estão (identificadores).
5. `docs/manual-desenvolvedor-tecnico.md` e `docs/manual-desenvolvedor-funcional.md`: já estão em PT-BR — apenas revisar se tem trechos remanescentes em inglês.
6. Glossário em `docs/glossario-ptbr.md` ampliado com termos de produto recém-traduzidos (ex.: "asset" → "ativo", "tracker" → "rastreador", "installment" → "título a receber", "payable" → "título a pagar", "draft" → "rascunho").
7. CHECK: rodar busca por palavras frequentes em inglês (`receivable`, `payable`, `installment`, `customer`, `vehicle`, `tracker`, `attachment`, `recurring`, `template`, `aggregate`) nos artefatos `.md` — não devem aparecer em frases corridas (só em nomes de classe/arquivo/identificador).

**Dev notes:**

- A tradução é mecânica + revisão humana. Pode ser feita em lotes (1 PR por épico).
- Termos técnicos a manter em inglês: HTTP, REST, JWT, OAuth, RSA, Argon2, Celery, FastAPI, Pydantic, SQLAlchemy, Alembic, Redis, PostgreSQL, MinIO, JSONB, UUID, ENUM, TIMESTAMPTZ, ASGI, ORM, DTO, repository, adapter, port, hexagonal, ADR, CRUD, CI/CD, PR, idempotência (já em PT-BR).
- Termos de produto/domínio: traduzir SEMPRE. Ver [[feedback-naming-convention-pt]].
- Após tradução, atualizar `_bmad-output/implementation-artifacts/sprint-status.yaml` apenas se algum slug de identificador mudar (provavelmente não muda — slugs ficam como estão).

**Estimativa:** 1-2 sessões dedicadas. Pode ser feita em paralelo com Epic 12 restante (não bloqueia).

**Onde encaixar na sequência:** **AGORA** — entre fechar Epic 12 (stories 12.4 a 12.8) e iniciar Epic 13. Pablo precisa conseguir revisar as próximas stories antes de aprovar implementação.

---

## ⏸️ PAUSA OBRIGATÓRIA antes de Épico 13: Revisão Automation/Manual + Arquitetura de Workers

> **Decisão de Pablo (2026-05-24):** Antes de implementar qualquer motor do Epic 13, fazer uma sessão dedicada para:
>
> 1. **Definir o que é automático vs manual** para cada operação financeira (geração, juros/multa, bloqueio, cobrança, conciliação, renegociação, encerramento, quitação antecipada). Cada story do Epic 13 deve declarar explicitamente seu trigger.
> 2. **Confirmar arquitetura single-infra multi-tenant**: backend é deployment único, banco único, workers Celery paralelos que varrem TODAS empresas filtrando por estado (não por empresa). NUNCA infra "por cliente". Workers herdam empresa_id do registro processado, não do request. Ver memória `project_single_infra_architecture`.
> 3. **Especificar a "Sala de Health Multi-Tenant"** (story nova, possivelmente Epic 15): UI cross-tenant para devs/operação ver status de workers, filas Celery, motores (último/próximo run, taxa de sucesso), logs estruturados em tempo real, alertas de erro. Funciona FORA do frontend do cliente (subdomain `admin.*` ou rota `/admin/observability/*` com guard role=superadmin). Verificar reuso da infra Grafana/Loki/Prometheus de 9.5 antes de duplicar.
>
> **Sem essa revisão, não iniciar Epic 13.**

---

## Épico 13: Motor Financeiro Central (Core)

> ⚠️ **Nota sobre numeração:** O Epic 12 já está alocado para "Schema Restructure & Multi-Tenancy" (DDL migration, rename PT-BR de tabelas/models, multi-tenancy com empresa_id). As histórias 12.1 a 12.8 do Epic 12 são pré-requisito deste Epic 13 — especialmente 12.6 (workers & tasks rename) que prepara o terreno para os motors deste épico.

**Objetivo:** Tornar o sistema operacional 24h/7 com workers Celery autônomos para geração de títulos, cobrança automatizada, verificação de pagamentos, máquina de estados do contrato e regras de negócio ausentes — incluindo o modelo correto de locação com opção de compra.

**Premissas do modelo de negócio confirmadas:**
- O contrato é **locação com opção de compra** (rent-to-own): N parcelas mensais + 1 parcela única final (opção de compra).
- Saldo devedor = apenas parcelas vencidas e não pagas (`status = 'em_atraso'`). Parcelas futuras **não** são dívida.
- Cancelamento sem atraso → zero saldo devedor. Veículo retorna à frota.
- Opção de compra paga → veículo transferido ao cliente.

**Dependências:** Épicos 1–11 concluídos ou em progresso.

**Convenção de nomenclatura:** TODOS os termos técnicos em PT-BR. Inglês vedado em código de domínio.

---

### História 13.1: Verificação de Consistência PT-BR + Glossário do Domínio

> **Nota:** O rename principal do sistema (tabelas, models SQLAlchemy, schemas Pydantic, routes, workers existentes, frontend) é feito pelas histórias 12.2 a 12.8 do **Epic 12 (Schema Restructure & Multi-Tenancy)**. Esta história 13.1 cobre a **verificação final**, o **glossário** e a **convenção para todo código NOVO** do motor (histórias 13.4 em diante).

**Critérios de Aceite Originais (mantidos):**

Como desenvolvedor do sistema,
quero que todo o código de domínio financeiro use nomenclatura em português,
para que haja consistência entre código, documentação e regras de negócio.

**Critérios de Aceite:**

1. Todos os nomes de funções, classes, variáveis e eventos de domínio financeiro renomeados conforme tabela abaixo — sem quebra de funcionalidade existente.

2. Tabela de mapeamento obrigatória aplicada:

| Nome antigo (EN) | Nome novo (PT-BR) |
|---|---|
| `generate_monthly_installments` | `gerar_titulos_mensais` |
| `check_overdue_installments` | `processar_titulos_vencidos` |
| `check_upcoming_due_dates` | `alertar_vencimentos_proximos` |
| `check_paid_installments` | `conciliar_pagamentos_recebidos` |
| `calculate_customer_scores` | `atualizar_scores_clientes` |
| `generate_recurring_payables` | `gerar_contas_pagar_recorrentes` |
| `check_channel_health` | `monitorar_saude_canais` |
| `refresh_materialized_views` | `atualizar_visoes_materializadas` |
| `on_installment_paid` | `quando_titulo_pago` |
| `on_installment_overdue` | `quando_titulo_vencido` |
| `on_contract_created` | `quando_contrato_ativado` |
| `on_contract_terminated` | `quando_contrato_encerrado` |
| `InstallmentOverdueEvent` | `EventoTituloVencido` |
| `InstallmentPaidEvent` | `EventoTituloPago` |
| `ContractCreatedEvent` | `EventoContratoAtivado` |
| `ContractTerminatedEvent` | `EventoContratoEncerrado` |
| `PaymentPartiallyReceivedEvent` | `EventoPagamentoParcialRecebido` |
| `CustomerScoreChangedEvent` | `EventoScoreClienteAlterado` |
| `collection_policy` | `politica_cobranca` |
| `template_renderer` | `renderizador_template` |
| `IAssetModule` | `IModuloVertical` |
| `IMessageChannel` | `ICanalMensagem` |
| `IPaymentGateway` | `IGatewayPagamento` |
| `ITrackerGateway` | `IGatewayRastreador` |

3. Rotas de API existentes mantêm compatibilidade via aliases com `deprecated=True` até próximo épico — sem breaking change para o frontend.

4. Migrações Alembic geradas para colunas renomeadas em tabelas de auditoria.

5. Suite de testes existente passa sem alteração de lógica — apenas adaptação de imports e nomes renomeados.

6. Arquivo `docs/glossario_dominio.md` criado com a tabela de mapeamento completa.

7. Nenhum termo em inglês de domínio financeiro permanece em: `domain/`, `application/`, `workers/`, `api/routers/`. Infraestrutura técnica (SQLAlchemy, FastAPI, Celery internals) mantém nomenclatura original das bibliotecas.

---

### História 13.2: Máquina de Estados do Contrato com Status `suspenso`

Como operador do sistema,
quero que o contrato possua a máquina de estados completa com o status `suspenso`,
para que contratos inadimplentes sejam pausados automaticamente sem encerramento definitivo.

**Critérios de Aceite:**

1. Enum `SituacaoContrato` com todos os estados e transições válidas (parâmetros de limite lidos de `config.configuracoes_sistema` via `ServicoConfiguracao` — ver História 13.4):

| De | Para | Ator | Gatilho |
|---|---|---|---|
| `rascunho` | `ativo` | Humano | Ativação manual |
| `ativo` | `suspenso` | Automático | Motor ao atingir config `limite_dias_suspensao` (financeiro) |
| `suspenso` | `ativo` | Humano | Pagamento confirmado ou desbloqueio em confiança |
| `ativo` | `encerrado_sem_pendencia` | Automático + Humano | Cancelamento sem atraso |
| `ativo` | `encerrado_com_pendencia` | Automático + Humano | Cancelamento com atraso — passivo gerado |
| `ativo` | `encerrado_compra` | Automático | Opção de compra paga — `OpcaoCompraPaga` |
| `ativo` | `rescindido` | Humano | Rescisão formal |
| `suspenso` | `encerrado_com_pendencia` | Automático + Humano | Inadimplência crônica (> config `limite_dias_encerramento`) |

2. Tabela `contratos` recebe coluna `situacao` com constraint CHECK validando estados acima. Migration Alembic gerada.

3. Colunas adicionais: `suspenso_em` (timestamptz nullable), `motivo_suspensao` (varchar 255 nullable).

4. Serviço `ServicoSituacaoContrato` em `application/services/` com método `transicionar(contrato_id, nova_situacao, motivo)` que valida o grafo, persiste, publica evento de domínio e registra `audit_log` com `categoria='financeiro'`.

5. Contratos `suspenso` são ignorados pelo motor `gerar_titulos_mensais` — nenhuma nova parcela gerada enquanto suspenso.

6. Ao suspender: hook `quando_contrato_suspenso` chama bloqueio do veículo via `IGatewayRastreador`.

7. Ao reativar: hook `quando_contrato_reativado` chama desbloqueio do veículo.

8. Frontend: badge de situação no card do contrato — `ativo` (verde), `suspenso` (âmbar), `encerrado_*` (cinza), `rescindido` (cinza escuro). Badge exibido na listagem de contratos e no detalhe.

9. Testes unitários: todas as transições válidas passam; todas as inválidas lançam `TransicaoInvalidaError`.

---

### História 13.3: Tipo de Título e Opção de Compra

Como sistema financeiro,
quero que a tabela de títulos distingua parcelas regulares de locação da opção de compra,
para que o pagamento da opção de compra dispare automaticamente a transferência de propriedade do veículo.

**Critérios de Aceite:**

1. Enum `TipoTitulo` adicionado:

```sql
CREATE TYPE tipo_titulo AS ENUM (
    'parcela',        -- mensalidade regular de locação
    'opcao_compra',   -- parcela única final — se paga, transfere propriedade
    'multa',          -- multa contratual
    'taxa',           -- taxa avulsa
    'ajuste'          -- ajuste manual
);

ALTER TABLE titulos ADD COLUMN tipo tipo_titulo NOT NULL DEFAULT 'parcela';
ALTER TABLE titulos ADD COLUMN numero_parcela SMALLINT;
ALTER TABLE titulos ADD COLUMN total_parcelas SMALLINT;
```

2. Constraint: apenas 1 título `opcao_compra` por contrato:

```sql
CREATE UNIQUE INDEX uniq_opcao_compra_por_contrato
    ON titulos (contrato_id) WHERE tipo = 'opcao_compra'::tipo_titulo;
```

3. Geração de títulos ao criar contrato: N parcelas `tipo='parcela'` com `numero_parcela` sequencial + 1 parcela `tipo='opcao_compra'` com vencimento após a última parcela regular (apenas se `contrato.valor_opcao_compra IS NOT NULL`).

4. Campo `valor_opcao_compra` adicionado à tabela `contratos` (nullable — contratos de locação pura sem opção de compra têm `NULL`).

5. Hook `quando_titulo_pago` verifica `titulo.tipo`:
   - `parcela` → fluxo normal
   - `opcao_compra` → publica evento `OpcaoCompraPaga(contrato_id, titulo_id, cliente_id, veiculo_id, valor_pago, data_pagamento)`

6. Handler `OpcaoCompraPagaHandler` no módulo de Veículos:
   - `veiculo.status = 'alienado'`
   - `veiculo.proprietario_id = cliente_id`
   - `contrato.situacao = 'encerrado_compra'`
   - Audit log com `categoria='transferencia_propriedade'`

7. Saldo devedor calculado apenas sobre parcelas `tipo='parcela'` com `status='em_atraso'` — opção de compra não entra no cálculo de inadimplência padrão.

8. Frontend: no detalhe do contrato, a opção de compra é exibida em seção separada com destaque visual (`★`), valor, data de vencimento e status (`pendente` / `pago` / `⏸ suspenso — quitar atraso primeiro`).

9. Testes: pagamento da parcela regular → sem transferência; pagamento da `opcao_compra` → veículo alienado, contrato `encerrado_compra`.

---

### História 13.4: Sistema de Configurações Tipadas (`config.configuracoes_sistema`)

Como gestor de empresa,
quero um sistema centralizado e tipado de configurações que sirva a todos os módulos do sistema,
para que qualquer parâmetro (financeiro, frota, comunicação) seja editável sem migration de banco e validado pelo PostgreSQL.

**Critérios de Aceite:**

1. Tabela `config.configuracoes_sistema` criada com validação por tipo via `CHECK constraint`:

```sql
CREATE TABLE config.configuracoes_sistema (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID REFERENCES comercial.empresas(id) ON DELETE CASCADE,
    modulo          VARCHAR(50) NOT NULL,
    slug            VARCHAR(100) NOT NULL,
    tipo_valor      VARCHAR(20) NOT NULL,
    valor           TEXT NOT NULL,
    descricao       TEXT,
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_por  UUID REFERENCES usuarios(id),

    CONSTRAINT uniq_config_empresa_slug UNIQUE (empresa_id, slug),

    CONSTRAINT ck_tipo_valor_aceito CHECK (
        tipo_valor IN ('string','inteiro','decimal','booleano','json')
    ),

    CONSTRAINT ck_valor_combina_com_tipo CHECK (
        (tipo_valor = 'inteiro'  AND valor ~ '^-?\d+$')                    OR
        (tipo_valor = 'decimal'  AND valor ~ '^-?\d+(\.\d+)?$')            OR
        (tipo_valor = 'booleano' AND valor IN ('true','false'))            OR
        (tipo_valor = 'string')                                            OR
        (tipo_valor = 'json'     AND valor::jsonb IS NOT NULL)
    )
);

CREATE INDEX idx_config_modulo ON config.configuracoes_sistema(modulo);
CREATE INDEX idx_config_empresa_modulo ON config.configuracoes_sistema(empresa_id, modulo);
```

2. **Serviço `ServicoConfiguracao`** em `application/services/` com fallback automático:

```python
class ServicoConfiguracao:
    def obter_inteiro(self, slug: str, modulo: str, padrao: int) -> int: ...
    def obter_decimal(self, slug: str, modulo: str, padrao: Decimal) -> Decimal: ...
    def obter_booleano(self, slug: str, modulo: str, padrao: bool) -> bool: ...
    def obter_string(self, slug: str, modulo: str, padrao: str) -> str: ...
    def obter_json(self, slug: str, modulo: str, padrao: dict) -> dict: ...

    def definir(self, slug: str, modulo: str, valor: Any, tipo_valor: str) -> None: ...
```

3. Seed inicial via `python -m app.cli seed` cria configurações padrão por módulo:

| slug | módulo | tipo_valor | valor padrão | descrição |
|---|---|---|---|---|
| `dias_antecedencia_lembrete` | financeiro | inteiro | 3 | Dias antes do vencimento para enviar lembrete |
| `dias_carencia` | financeiro | inteiro | 0 | Dias de tolerância após vencimento |
| `percentual_multa` | financeiro | decimal | 2.00 | % de multa por atraso |
| `percentual_juros_dia` | financeiro | decimal | 0.0333 | % de juros ao dia |
| `limite_tentativas_cobranca` | financeiro | inteiro | 3 | Máx. mensagens de cobrança por título |
| `intervalo_tentativas_horas` | financeiro | inteiro | 24 | Horas entre tentativas de cobrança |
| `limite_dias_suspensao` | financeiro | inteiro | 15 | Dias de atraso para suspender contrato |
| `limite_dias_encerramento` | financeiro | inteiro | 60 | Dias de atraso para encerrar com pendência |
| `permite_pagamento_parcial` | financeiro | booleano | false | Aceita pagamentos parciais |
| `limite_fusao_parcial_pct` | financeiro | decimal | 20.00 | % do valor da parcela abaixo do qual o resto funde na próxima |
| `desbloqueio_confianca_dias` | frota | inteiro | 3 | Validade em dias do desbloqueio em confiança |
| `desbloqueio_confianca_min_meses_historico` | frota | inteiro | 3 | Mínimo de meses de relacionamento para elegibilidade |
| `desbloqueio_confianca_max_atrasos_historico` | frota | inteiro | 1 | Máx. ocorrências de atraso no histórico |
| `canal_cobranca_principal` | comunicacao | string | whatsapp | Canal padrão de cobrança |
| `canal_cobranca_fallback` | comunicacao | string | (vazio) | Canal de fallback se principal falhar |

4. Endpoint REST `GET /api/v1/configuracoes?modulo={modulo}` (role `admin`) — lista paginada filtrável.
5. Endpoint `PUT /api/v1/configuracoes/{slug}` (role `admin`) — atualiza valor com validação do tipo no backend antes do `INSERT`.
6. Audit log para toda mutação com `categoria='configuracao'` e diff antes/depois.
7. Testes: tentar gravar `tipo_valor='inteiro'` com `valor='abc'` → 422; gravar valor válido → 200.
8. `ServicoConfiguracao` cacheia consultas por `(empresa_id, slug)` por 60s em Redis — invalida no `definir()`.

---

### História 13.5: Infraestrutura Base dos Workers

Como engenheiro de plataforma,
quero a infraestrutura base do worker Celery com filas separadas, observabilidade e idempotência,
para que todos os motors do épico tenham fundação confiável e diagnosticável.

**Critérios de Aceite:**

1. `workers/celeryconfig.py` consolidado com **7 filas** isoladas:

| Fila | Concurrency | Propósito |
|---|---|---|
| `fila_cobranca` | 4 workers × 4 threads | Geração, encargos, cobrança |
| `fila_notificacoes` | 2 workers × 4 threads | WhatsApp/email/SSE com rate-limit |
| `fila_verificacao` | 2 workers × 4 threads | OCR, reconciliação, comprovantes |
| `fila_contratos` | 2 workers × 2 threads | Ciclo de vida de contratos |
| `fila_frota` | 2 workers × 2 threads | GPS, FIPE, documentos |
| `fila_padrao` | 2 workers × 2 threads | Coordinators, manutenção |
| `fila_whatsapp_entrada` | 2 workers × 4 threads | Inbound prioridade máxima |
| `fila_agente` | 2 workers × 1 thread/processo | LLM I/O-bound |

2. `docker-compose.yml` com serviço `beat` (replicas=1 — fixo) + serviços de worker por fila escaláveis.

3. **Padrão fan-out**: coordinator no Beat consulta IDs elegíveis, distribui em lotes de 50 via `group()`/`chord()` do Celery — falha em uma empresa não bloqueia as demais.

4. **3 camadas de idempotência** obrigatórias em toda task de cobrança:
   - `SELECT FOR UPDATE SKIP LOCKED` no PostgreSQL
   - Redis lock `titulo:{id}:{operacao}` com TTL 60s
   - Colunas `proxima_acao_em TIMESTAMPTZ` e `acoes_de_cobranca INTEGER` na tabela `titulos`

5. Tabela `execucoes_motor` para observabilidade:

```sql
CREATE TABLE execucoes_motor (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    nome_tarefa     VARCHAR(100) NOT NULL,
    empresa_id      UUID REFERENCES empresas(id),
    iniciado_em     TIMESTAMPTZ NOT NULL,
    finalizado_em   TIMESTAMPTZ,
    total_registros INTEGER DEFAULT 0,
    total_erros     INTEGER DEFAULT 0,
    situacao        VARCHAR(20) NOT NULL DEFAULT 'executando',
    detalhes        JSONB,
    CONSTRAINT ck_situacao CHECK (situacao IN ('executando','concluido','erro'))
);
```

6. Tabela `lembretes_enviados` para idempotência de envios:

```sql
CREATE TABLE lembretes_enviados (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    titulo_id   UUID NOT NULL REFERENCES titulos(id),
    tipo        VARCHAR(30) NOT NULL,
    canal       VARCHAR(30) NOT NULL,
    enviado_em  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    sucesso     BOOLEAN NOT NULL,
    erro        TEXT,
    UNIQUE(titulo_id, tipo, DATE(enviado_em))
);
```

7. Endpoint `GET /api/v1/motor/execucoes` lista histórico paginado com filtros `nome_tarefa`, `empresa_id`, `situacao`, `data_inicio` (role `admin`).

8. Configuração de retry e dead-letter queue: `acks_late=True`, `reject_on_worker_lost=True`, `max_retries=3` com backoff exponencial.

9. Testes: 2 workers competindo pelo mesmo título → apenas um processa (SKIP LOCKED); worker crasha após processar → não duplica execução (acks_late).

---

### História 13.6: Motor `gerar_titulos_mensais`

Como sistema financeiro,
quero gerar títulos mensais automaticamente com aplicação de índice de correção,
para que o ciclo de cobrança seja autônomo.

**Critérios de Aceite:**

1. Task Celery `gerar_titulos_mensais` com schedule `crontab(hour=3, minute=0, day_of_month=1)`.

2. Lógica: busca contratos com `situacao='ativo'` e `modo_geracao='mensal'` e `proxima_data_geracao <= hoje`. Para cada contrato: verifica idempotência por `(contrato_id, competencia)` → cria título com correção monetária aplicada → avança `proxima_data_geracao`.

3. Tabela `tabela_indices_economicos(indice, competencia, percentual, UNIQUE(indice, competencia))` para armazenamento de IGPM/IPCA/INPC.

4. Contratos com índice configurado mas valor ausente: título gerado com valor base + alerta em `alertas_sistema`.

5. Idempotente: execuções repetidas no mesmo mês não geram duplicatas.

6. Endpoint `POST /api/v1/motor/gerar-titulos` para disparo manual (role `admin`).

---

### História 13.7: Motor `alertar_vencimentos_proximos`

Como cliente,
quero receber lembretes antes do vencimento,
para que eu pague em dia e evite encargos.

**Critérios de Aceite:**

1. Task Celery `alertar_vencimentos_proximos` com schedule `crontab(hour=8, minute=0)`.

2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento` entre `hoje + 1` e `hoje + ServicoConfiguracao.obter_inteiro('dias_antecedencia_lembrete', 'financeiro', padrao=3)`. Ignora se já enviado hoje (`lembretes_enviados`).

3. Renderiza mensagem via `renderizador_template` com template `lembrete_vencimento`. Envia pelo `ServicoConfiguracao.obter_string('canal_cobranca_principal', 'comunicacao', padrao='whatsapp')`. Fallback para `canal_cobranca_fallback` se falhar.

4. Registra resultado em `lembretes_enviados` e métricas em `execucoes_motor`.

---

### História 13.8: Motor `processar_titulos_vencidos`

Como sistema financeiro,
quero processar automaticamente títulos vencidos com aplicação de encargos e escalonamento até suspensão do contrato,
para que a inadimplência seja tratada sem intervenção manual.

**Critérios de Aceite:**

1. Task Celery `processar_titulos_vencidos` com schedule `crontab(hour=9, minute=0)`.

2. Busca títulos `tipo='parcela'`, `situacao='pendente'`, `data_vencimento < hoje - ServicoConfiguracao.obter_inteiro('dias_carencia', 'financeiro', padrao=0)`.

3. Para cada título: calcula `valor_atualizado = valor_nominal + multa + juros`:
   - `multa = valor × ServicoConfiguracao.obter_decimal('percentual_multa', 'financeiro', padrao=Decimal('2.00')) / 100` no D+1
   - `juros = valor × ServicoConfiguracao.obter_decimal('percentual_juros_dia', 'financeiro', padrao=Decimal('0.0333')) / 100 × dias_atraso`
   
   Atualiza `situacao = 'em_atraso'`, persiste encargos.

4. Envia mensagem de cobrança via `renderizador_template` respeitando `limite_tentativas_cobranca` e `intervalo_tentativas_horas` (lidos via `ServicoConfiguracao`). Registra em `lembretes_enviados`.

5. Ao atingir `limite_dias_suspensao` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'suspenso', motivo=...)`.

6. Ao atingir `limite_dias_encerramento` (config `financeiro`): chama `ServicoSituacaoContrato.transicionar(contrato_id, 'encerrado_com_pendencia', motivo=...)` → hook gera passivo inoperante para cada título `em_atraso`.

7. Publica `EventoTituloVencido` para cada título processado.

8. Idempotente: encargos calculados com base na data atual (sobrescreve, não acumula). Contratos `suspenso` ou terminais ignorados.

9. Testes: D+1 → multa aplicada, mensagem enviada; D+`limite_dias_suspensao+1` → contrato suspenso, veículo bloqueado; D+`limite_dias_encerramento+1` → contrato encerrado, passivo gerado.

---

### História 13.9: Motor `conciliar_pagamentos_recebidos` (com Fusão de Pagamento Parcial)

Como sistema financeiro,
quero verificar automaticamente pagamentos recebidos, reconciliá-los e tratar pagamentos parciais com regra de fusão,
para que o ciclo financeiro seja autônomo e diferenças pequenas sejam fundidas na próxima parcela em vez de gerar título novo desnecessariamente.

**Critérios de Aceite:**

1. Task Celery `conciliar_pagamentos_recebidos` com schedule `crontab(minute='*/15')`.

2. Busca pagamentos com `situacao='pendente_verificacao'`. Para cada um: localiza título por `titulo_id` ou por `(empresa_id, valor, competencia)` como fallback.

3. Hook `quando_titulo_pago(titulo_id, pagamento_id)`: atualiza título (`situacao='pago'`), verifica `titulo.tipo`:
   - `parcela` → fluxo normal: verifica se contrato `suspenso` pode ser reativado
   - `opcao_compra` → publica `OpcaoCompraPaga`

4. Ao reativar contrato suspenso: chama `ServicoDesbloqueioConfianca.verificar()` (História 13.13). Se elegível, `ServicoSituacaoContrato.transicionar(contrato_id, 'ativo', motivo='Pagamento confirmado')`.

5. **Pagamento parcial com fusão automática**: se `valor_pago < valor_titulo`:
   - Calcula `restante = valor_titulo - valor_pago`
   - Lê `limite_fusao_parcial_pct` via `ServicoConfiguracao` (default 20.00%)
   - Se `restante <= valor_titulo × limite_fusao_parcial_pct / 100`:
     - **Funde**: marca título original como `pago_parcial`, adiciona `restante` ao próximo título em aberto do contrato (com nota de auditoria), sem criar título novo
   - Caso contrário:
     - **Separa**: cria título novo `tipo='parcela'`, `valor=restante`, `parent_titulo_id=titulo.id`, vencimento = hoje + `dias_carencia`
   - Publica `EventoPagamentoParcialRecebido` em ambos os casos

6. Pagamentos sem identificação → tabela `pagamentos_nao_identificados` + alerta operacional.

7. Webhook externo `POST /api/v1/webhooks/pagamento` cria pagamento e dispara task com `countdown=5s`.

8. Idempotente: pagamento já `conciliado` ignorado sem erro.

9. Testes:
   - Pagamento integral → título `pago`
   - Pagamento parcial dentro do threshold (ex: paga 95% de R$800, restam R$40 = 5% < 20%) → funde no próximo título
   - Pagamento parcial fora do threshold (ex: paga 50%, restam R$400 = 50% > 20%) → cria título novo com `parent_titulo_id`
   - Opção de compra paga → `OpcaoCompraPaga` publicado, veículo alienado

---

### História 13.10: Renderizador de Templates de Mensagem

Como motor financeiro,
quero um renderizador de templates centralizado,
para que todos os workers enviem mensagens consistentes com variáveis preenchidas.

**Critérios de Aceite:**

1. `renderizador_template.py` em `infrastructure/mensageria/` com função `renderizar(nome_template, contexto: dict) -> str`.

2. Tabela `templates_mensagem(empresa_id, nome, canal, conteudo, ativo)` — personalizáveis por empresa, fallback para templates padrão do sistema.

3. Templates padrão PT-BR seedados: `lembrete_vencimento`, `cobranca_vencida`, `aviso_suspensao`, `pagamento_confirmado`, `opcao_compra_exercida`.

4. Variáveis disponíveis: `{{cliente.nome}}`, `{{titulo.valor}}`, `{{titulo.valor_atualizado}}`, `{{titulo.data_vencimento}}`, `{{titulo.dias_atraso}}`, `{{veiculo.placa}}`, `{{contrato.id}}`, `{{empresa.nome}}`.

5. Endpoint CRUD `GET/POST/PUT /api/v1/templates-mensagem` (role `admin`) com preview com dados de exemplo.

---

### História 13.11: Ledger de Passivo Inoperante

Como gestor financeiro,
quero que títulos em atraso de contratos encerrados sejam registrados como passivo inoperante,
para que a dívida real seja rastreável e possa ser cobrada ou baixada formalmente.

**Critérios de Aceite:**

1. Tabela `passivos_inoperantes` criada:

```sql
CREATE TABLE passivos_inoperantes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id),
    cliente_id      UUID NOT NULL REFERENCES clientes(id),
    contrato_id     UUID NOT NULL REFERENCES contratos(id),
    titulo_id       UUID NOT NULL REFERENCES titulos(id),
    valor_nominal   NUMERIC(12,2) NOT NULL,
    valor_encargos  NUMERIC(12,2) NOT NULL DEFAULT 0,
    situacao        VARCHAR(30) NOT NULL DEFAULT 'pendente',
    origem          VARCHAR(50) NOT NULL,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    baixado_em      TIMESTAMPTZ,
    motivo_baixa    TEXT,
    criado_por      UUID REFERENCES usuarios(id),
    CONSTRAINT ck_passivo_situacao CHECK (situacao IN ('pendente','baixado','recuperado'))
);
```

2. Hook `quando_contrato_encerrado` (quando `situacao='encerrado_com_pendencia'`): itera títulos com `status='em_atraso'` do contrato → cria registro em `passivos_inoperantes` para cada um.

3. Endpoints: `GET /api/v1/passivo-inoperante` (filtros por `empresa_id`, `cliente_id`, `situacao`), `PATCH /{id}/baixar`, `PATCH /{id}/recuperado`.

4. Frontend: aba `Passivos` no detalhe do cliente com badge numérico. Card exibe valor, data origem e botões de ação com `ConfirmService` antes de confirmar.

5. KPI no dashboard: "Passivo Inoperante Total — R$ X / N clientes".

6. Audit log para toda mutação com `categoria='financeiro'`.

---

### História 13.12: Herói Financeiro no Detalhe do Contrato

Como gestor,
quero ver o estado financeiro do contrato de forma clara e imediata ao abrir o detalhe,
para que possa agir sem precisar escanear tabelas.

**Critérios de Aceite:**

1. Componente `ContractHeroComponent` no detalhe do contrato exibe, em estados distintos:

   **Estado EM DIA:**
   - Badge `✓ EM DIA` (verde)
   - Barra de progresso: parcelas pagas / total, com marcador `★` para a opção de compra
   - Totais: "R$X pagos · R$Y restam · Opção de compra: R$Z"
   - Última parcela paga e próximo vencimento (data + countdown em dias)

   **Estado EM ATRASO:**
   - Badge `⚠ EM ATRASO — N parcelas` (âmbar/vermelho)
   - Bloco de atraso acima da barra: lista de parcelas em atraso com valor + encargos + total
   - CTA principal: "Registrar pagamento das parcelas em atraso"
   - Barra de progresso com segmento `em atraso` em cor âmbar
   - Opção de compra com estado `⏸ Suspenso — quitar atraso primeiro`

2. Seção separada para a opção de compra com: valor, data de vencimento, status e texto explicativo ("Se paga, o veículo passa para o nome do cliente").

3. No wizard de novo contrato (Passo 1 — seleção de cliente): se cliente possui passivos inoperantes, exibe banner âmbar obrigatório antes de prosseguir: "Este cliente possui passivo de contratos anteriores — R$X. Deseja criar contrato normalmente ou registrar acordo de passivo?"

4. Botão "Cancelar contrato" no detalhe: abre modal `ConfirmService` com texto diferente conforme situação:
   - Sem atraso: "Carlos não possui parcelas em atraso. O encerramento é limpo — sem saldo devedor."
   - Com atraso: "Carlos possui N parcelas em atraso (R$X). Elas permanecerão como passivo inoperante."

5. Testes E2E: contrato em dia → badge verde, sem bloco de atraso; contrato com atraso → badge âmbar, bloco de atraso visível, CTA correto.

---

### História 13.13: Desbloqueio em Confiança com Expiração

Como operador financeiro,
quero configurar regras de desbloqueio em confiança com prazo de validade,
para que clientes elegíveis sejam reativados ao pagar sem aprovação manual — e re-bloqueados automaticamente se não cumprirem o prazo prometido.

**Critérios de Aceite:**

1. Parâmetros via `ServicoConfiguracao` (módulo `frota`):
   - `desbloqueio_confianca_dias` (inteiro, default 3) — validade do desbloqueio em dias
   - `desbloqueio_confianca_min_meses_historico` (inteiro, default 3) — mínimo de meses de relacionamento
   - `desbloqueio_confianca_max_atrasos_historico` (inteiro, default 1) — máx. ocorrências de atraso no histórico

2. Tabela `veiculos` recebe colunas:
   - `desbloqueio_confianca_ativo_ate TIMESTAMPTZ NULL` — data/hora em que o desbloqueio expira
   - `desbloqueio_confianca_concedido_em TIMESTAMPTZ NULL`
   - `desbloqueio_confianca_concedido_por UUID NULL REFERENCES usuarios(id)`

3. Serviço `ServicoDesbloqueioConfianca`:
   - `verificar_elegibilidade(contrato_id) -> bool` — avalia histórico contra os 3 parâmetros de config
   - `conceder(veiculo_id, usuario_id) -> None` — desbloqueia veículo via `IGatewayRastreador`, preenche `desbloqueio_confianca_ativo_ate = NOW() + dias`
   - `revogar(veiculo_id, motivo) -> None` — re-bloqueia, limpa campos

4. Endpoint `POST /api/v1/contratos/{id}/desbloqueio-confianca` (role `admin` ou agente IA com escopo) com justificativa — registra no `audit_log` categoria `frota`.

5. **Nova task `verificar_desbloqueios_expirados`** com schedule `crontab(minute='*/30')`:
   - Busca veículos com `desbloqueio_confianca_ativo_ate < NOW()` e contrato `suspenso`
   - Para cada: chama `ServicoDesbloqueioConfianca.revogar(veiculo_id, motivo='Prazo de desbloqueio em confiança expirado sem pagamento')`
   - Envia template `aviso_re_bloqueio` ao cliente
   - Registra em `execucoes_motor`

6. Frontend: no detalhe do veículo, se desbloqueio em confiança ativo → badge âmbar `🤝 Desbloqueio em confiança até DD/MM HH:mm` com countdown ao vivo.

7. Testes: cliente elegível pede desbloqueio → veículo desbloqueado por N dias; cliente paga dentro do prazo → desbloqueio convertido em reativação normal; cliente NÃO paga → re-bloqueio automático após `desbloqueio_confianca_dias`.

---

### História 13.14: Override Manual do Valor de Mercado do Veículo

Como gestor de frota,
quero poder sobrescrever manualmente o valor de mercado de um veículo quando o valor FIPE não reflete a realidade,
para que dashboards e cálculos de ROI usem o valor real (carro batido vale menos, carro raro vale mais).

**Critérios de Aceite:**

1. Tabela `veiculos` recebe colunas:
   - `valor_mercado_manual NUMERIC(12,2) NULL`
   - `valor_mercado_manual_atualizado_em TIMESTAMPTZ NULL`
   - `valor_mercado_manual_motivo TEXT NULL`
   - `valor_mercado_manual_atualizado_por UUID NULL REFERENCES usuarios(id)`

2. Função `obter_valor_mercado(veiculo_id) -> Decimal` retorna `valor_mercado_manual` se preenchido, senão `valor_fipe_atual`.

3. Dashboards e cálculos de ROI usam `obter_valor_mercado()` — NUNCA acessam `valor_fipe_atual` diretamente.

4. Endpoint `PUT /api/v1/veiculos/{id}/valor-mercado-manual` com payload `{"valor": decimal, "motivo": string}` (role `admin` ou `gestor_frota`). `motivo` é obrigatório.

5. Endpoint `DELETE /api/v1/veiculos/{id}/valor-mercado-manual` remove o override (volta a usar FIPE).

6. Frontend: no detalhe do veículo, campo "Valor de mercado" com:
   - Valor exibido (manual se sobrescrito, FIPE caso contrário)
   - Badge `📝 Manual` ou `📊 FIPE` ao lado
   - Botão "Sobrescrever" abre modal com input de valor + textarea de motivo
   - Se manual: botão "Remover override" volta a usar FIPE

7. Audit log para toda mutação com `categoria='frota'`.

8. Testes: sem override → ROI usa FIPE; com override → ROI usa manual; remover override → ROI volta a FIPE.

---

### História 13.15: Tela de Configurações do Motor (UI para o gestor)

Como gestor,
quero uma tela visual e organizada para configurar todos os parâmetros do motor financeiro e demais módulos,
para que eu possa ajustar regras de negócio sem precisar de desenvolvedor.

**Atenção UX (Sally):** esta é a tela mais crítica do épico. Se mal feita, o sistema vira planilha cara. Gestor precisa configurar **sem treinamento**, idealmente em menos de 5 minutos por seção.

**Critérios de Aceite:**

1. Rota `/sistema/config/parametros` com layout responsivo mobile-first.

2. Navegação por **tabs verticais** (desktop) ou **accordion** (mobile), uma por módulo:
   - Financeiro (parâmetros de cobrança, multa, juros, suspensão)
   - Frota (desbloqueio em confiança, alertas de documentos)
   - Comunicação (canais, templates default)
   - Motor (status das tasks agendadas, com horários e última execução)

3. Cada parâmetro renderizado conforme `tipo_valor`:
   - `inteiro` → input number com min/max + stepper (`+`/`-`)
   - `decimal` → input number com 2 casas + sufixo `%` ou `R$` quando aplicável (detectado do slug)
   - `booleano` → toggle switch (não checkbox)
   - `string` → select se houver `opcoes_aceitas` no metadata, senão input text
   - `json` → editor JSON com syntax highlighting + validador inline

4. Cada campo mostra:
   - Label legível em PT-BR (não o slug técnico)
   - Tooltip `ℹ️` com descrição e exemplo do efeito da mudança
   - Valor atual + valor padrão (badge "padrão" se = padrão)
   - Botão "Restaurar padrão" ao lado

5. Mudanças são salvas com **debounce de 1s** + indicador visual de salvamento (`✓ Salvo às HH:mm:ss`). Sem botão "Salvar" — autosave.

6. Erro de validação (ex: tentar gravar "abc" em campo inteiro) exibe inline em vermelho sem perder o foco.

7. Cada seção tem **botão de pré-visualização**: "Simular como esses valores impactariam X contratos ativos" (ex: alterar `percentual_multa` mostra "Multa total mensal estimada: R$2.450").

8. Toda mudança gera audit log + opção "Reverter última alteração" disponível por 10 minutos.

9. Permissão: apenas role `admin`. Demais perfis veem em modo somente-leitura com badge `🔒 Apenas admin pode alterar`.

10. Testes E2E: alterar `percentual_multa` de 2.00 para 3.00 → autosave → recarregar página → valor persistido; tentar gravar string em campo inteiro → mensagem inline em vermelho.

---

**Resumo do Épico 13**

| História | Título | Complexidade |
|---|---|---|
| 13.1 | Padronização de Nomenclatura PT-BR | Média |
| 13.2 | Máquina de Estados do Contrato | Média |
| 13.3 | Tipo de Título e Opção de Compra | Alta |
| 13.4 | Sistema de Configurações Tipadas | Média |
| 13.5 | Infraestrutura Base dos Workers | Alta |
| 13.6 | Motor `gerar_titulos_mensais` | Média |
| 13.7 | Motor `alertar_vencimentos_proximos` | Baixa |
| 13.8 | Motor `processar_titulos_vencidos` | Alta |
| 13.9 | Motor `conciliar_pagamentos_recebidos` (com fusão parcial) | Alta |
| 13.10 | Renderizador de Templates | Baixa |
| 13.11 | Ledger de Passivo Inoperante | Média |
| 13.12 | Herói Financeiro no Detalhe do Contrato | Média |
| 13.13 | Desbloqueio em Confiança com Expiração | Média |
| 13.14 | Override Manual do Valor de Mercado do Veículo | Baixa |
| 13.15 | Tela de Configurações do Motor (UI) | Alta |

**Sequência recomendada de implementação:**

`13.1 → 13.4 → 13.2 → 13.3 → 13.5 → 13.10 → 13.6 → 13.7 → 13.8 → 13.9 → 13.11 → 13.13 → 13.12 → 13.14 → 13.15`

**Pré-requisito obrigatório:** Epic 12 (histórias 12.2 a 12.8) deve estar completo antes de iniciar Epic 13. O rename de tabelas/models/schemas/workers existentes do Epic 12 é fundação para os motors deste épico.

**Justificativa da ordem:**
- 13.1 primeiro (verificação PT-BR + glossário): zero risco, valida que Epic 12 deixou tudo consistente
- 13.4 antes de qualquer motor: todos os motors dependem do `ServicoConfiguracao`
- 13.5 (infra) antes dos motors específicos: filas, idempotência, observabilidade
- Motors do mais simples ao mais complexo (13.6 → 13.9)
- 13.13 (desbloqueio) antes de 13.12 (herói): herói usa o estado de desbloqueio na UI
- 13.15 (tela) por último: UI consome tudo que foi construído antes

**Cobertura de teste exigida por história:** mínimo 70%. **Code review obrigatório** via `bmad-code-review` após cada `bmad-dev-story`.

---

## Épico 14: Manual do Desenvolvedor & Documentação Final (Core)

**Objetivo:** Consolidar toda a documentação técnica e funcional do sistema num conjunto de manuais que permita um novo desenvolvedor ser produtivo em < 1 semana e que o sistema seja mantido sem dependência do autor original.

**Pré-requisito:** Todos os épicos anteriores (10, 11, 12, 13) devem estar concluídos. É o último épico do roadmap antes de versão 1.0 estável.

**Por que último:** Documentar sistema em transição é desperdício — toda a documentação fica desatualizada antes de ir a produção. Faz mais sentido escrever depois que o motor de cobrança, multi-tenancy e Epic 13 estiverem fechados e validados.

**Status:** backlog

---

### História 14.1: Manual do Desenvolvedor — Camada Técnica

Como desenvolvedor novo no projeto,
quero um manual técnico que me leve do zero ao primeiro PR mergado em menos de 1 semana,
para que eu seja produtivo sem depender de tribal knowledge.

**Critérios de Aceite:**

1. Documento `docs/manual-desenvolvedor-tecnico.md` com 800-1500 linhas, em PT-BR.
2. Cobre: arquitetura hexagonal, estrutura de pastas, 12 schemas PostgreSQL, padrões obrigatórios (UUIDPrimaryKeyMixin, TimestampMixin, SoftDeleteMixin, schema= em table_args, ForeignKey qualificado, empresa_id em tudo tenant-scoped), convenções de naming PT-BR + synonyms, workers Celery (7 filas, fan-out, 3 idempotências), Ports & Adapters com exemplos, multi-tenancy Modelo A, testes pytest async, migrations Alembic, env vars, frontend Angular básico, observabilidade.
3. Todo exemplo de código cita path absoluto real do projeto.
4. Decisões arquiteturais consolidadas em uma seção única (ADRs resumidos).
5. Glossário PT-BR↔EN com synonyms vigentes na transição.
6. Mapa "pergunta → arquivo onde encontrar" para navegação rápida.
7. Lista de antipadrões rejeitados em code review.

> ⚠️ **Já entregue em 2026-05-24 como rascunho** — 1123 linhas. Revisar e atualizar após épicos 10/11/12/13 completos.

---

### História 14.2: Manual do Desenvolvedor — Camada Funcional

Como desenvolvedor que precisa entender o NEGÓCIO antes de codar,
quero um manual funcional que explique o sistema do ponto de vista do gestor de frota,
para que minhas decisões técnicas sejam coerentes com o modelo de negócio.

**Critérios de Aceite:**

1. Documento `docs/manual-desenvolvedor-funcional.md` com 600-1200 linhas, em PT-BR.
2. Cobre: visão geral, modelo rent-to-own, atores e perfis, fluxos principais (onboarding, cadastros, contrato, operação diária, motor de cobrança, pagamento parcial, bloqueio/desbloqueio, encerramento, conciliação, configurações tipadas).
3. Regras de negócio explícitas (máquina de estados do contrato, lifecycle do título, definição precisa de saldo devedor, política de cobrança com parâmetros configuráveis, score do cliente).
4. Multi-tenant Modelo A explicado com implicações de negócio.
5. Glossário PT-BR de termos do domínio com significado de negócio (não técnico).
6. Decisões de produto com justificativa (por que rent-to-own, por que Modelo A, por que self-register desabilitado, por que motor Python, por que Pix sem gateway, etc.).
7. Roadmap de épicos com status, entregáveis e valor de negócio de cada um.
8. Apêndice "quer entender X → vá em arquivo Y" para conectar conceito ao código.

> ⚠️ **Já entregue em 2026-05-24 como rascunho** — 662 linhas. Revisar e atualizar após épicos 10/11/12/13 completos.

---

### História 14.3: Documentação de APIs (OpenAPI consolidado)

Como dev frontend ou integrador externo,
quero documentação de API consolidada e navegável,
para consumir os endpoints sem ler código backend.

**Critérios de Aceite:**

1. OpenAPI gerado automaticamente via FastAPI em `/docs` (Swagger) e `/redoc`.
2. Cada endpoint tem `summary`, `description`, `response_model` tipado e exemplos no docstring.
3. Schemas Pydantic com `Field(description=)` em todos os campos.
4. Tags organizadas por módulo (auth, clientes, veículos, contratos, recebíveis, etc.).
5. Documento `docs/api-reference.md` exportado do OpenAPI com curl examples para os 20 endpoints mais usados.
6. Webhooks documentados separadamente (provider, payload, signature validation).

---

### História 14.4: Runbook Operacional

Como operador (DevOps/SRE) do sistema em produção,
quero um runbook com procedimentos de operação e troubleshooting,
para resolver incidentes sem precisar do autor original.

**Critérios de Aceite:**

1. Documento `docs/runbook-operacional.md` em PT-BR.
2. Cobre: deploy (Docker Compose dev + Kubernetes/Coolify prod), backup/restore, rotação de chaves JWT, escala de workers Celery, monitoramento Grafana, alertas Prometheus, troubleshooting comum (queue stuck, DB lento, agente IA falhando).
3. Playbook de incidentes: o que fazer quando o motor de cobrança para, quando WhatsApp gateway cai, quando OCR fica lento, quando o banco trava.
4. Procedimentos LGPD (export/anonimização de dados).
5. Checklist de release (deploy seguro com migration).

---

### História 14.5: Documentação de Adaptadores (ADAPTERS.md)

Como dev integrando um novo provider externo,
quero um guia que explique como criar um novo adapter para qualquer Port,
para integrar provedores sem quebrar a arquitetura hexagonal.

**Critérios de Aceite:**

1. Documento `docs/adapters-guide.md` em PT-BR.
2. Para cada Port (IGatewayPagamento, ICanalMensagem, IGatewayRastreador, IProvedorFipe, IProvedorOcr, IProvedorLLM, IProvedorIndiceCorrecao, IProvedorArmazenamento, IEnviadorEmail): contrato detalhado, exemplo de adapter existente, passo-a-passo para criar um novo.
3. Cobertura de testes obrigatória para novos adapters (≥80%).
4. Convenção de configuração via `config.configuracoes_sistema` (credenciais cifradas).

---

### História 14.6: Documentação de Módulos Verticais (MODULES.md)

Como dev criando uma vertical nova (ex: imóveis, equipamentos),
quero um guia que explique como implementar `IModuloVertical`,
para adicionar verticais sem tocar no Core.

**Critérios de Aceite:**

1. Documento `docs/modules-guide.md` em PT-BR.
2. Explica: interface `IModuloVertical`, hooks (`quando_*`), schema extension, registro de tools no agente IA, dashboard widgets, report dimensions.
3. Usa `ModuloVeiculos` como template ao longo da explicação.
4. Inclui exemplo passo-a-passo de criação de um módulo "Properties" (locação de imóveis) — não precisa ser implementado, só documentado como exercício didático.
5. Checklist do que verificar antes de habilitar um módulo em produção.

---

### História 14.7: Vídeos Curtos de Onboarding (Opcional V2)

> **V2 — Diferido pós-launch.** Manuais escritos cobrem MVP.

Vídeos screencast (5-10 min cada) para acelerar onboarding visual:
- Visão geral em 5min
- Setup local com docker-compose
- Criar primeiro contrato no sistema
- Como debugar uma task Celery
- Como adicionar um adapter novo

---

**Resumo do Épico 14**

| História | Título | Status | Tamanho |
|---|---|---|---|
| 14.1 | Manual do Desenvolvedor — Técnico | rascunho entregue | 1123 linhas |
| 14.2 | Manual do Desenvolvedor — Funcional | rascunho entregue | 662 linhas |
| 14.3 | Documentação de APIs (OpenAPI) | backlog | — |
| 14.4 | Runbook Operacional | backlog | — |
| 14.5 | ADAPTERS.md | backlog | — |
| 14.6 | MODULES.md | backlog | — |
| 14.7 | Vídeos de Onboarding | V2 (diferido) | — |

**Sequência recomendada:** `14.1 → 14.2 → 14.3 → 14.5 → 14.6 → 14.4 → (V2: 14.7)`

**Quando começar:** Apenas após épicos 10, 11, 12 e 13 estarem `done`. Documentar sistema em transição é desperdício.
