"""Schema restructure: 12 PostgreSQL schemas, Portuguese table/column names, multi-tenancy.

Revision ID: 0015
Revises: 0014
Create Date: 2026-05-21

Epic 12 Story 1 — DDL Migration.

Moves all tables out of public schema into 12 domain schemas, renames every
table and column to Portuguese, adds empresa_id to all tenant-scoped tables,
creates comercial.empresas as the root tenant table, drops the asset-abstraction
layer (assets, active_modules), and recreates all indexes, triggers and
materialized views.

Reference: docs/ddl/schema_v2.sql
"""

from alembic import op

revision = "0015"
down_revision = "0014"
branch_labels = None
depends_on = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _exec(sql: str) -> None:
    """Execute raw SQL."""
    op.execute(sql)


def _add_empresa_id_not_null(schema_table: str) -> None:
    """Add empresa_id (FK → comercial.empresas) as NOT NULL, populating
    existing rows with the single seed empresa."""
    # Guard: assert seed empresa exists before any UPDATE
    _exec("""
        DO $$ BEGIN
            IF NOT EXISTS (SELECT 1 FROM comercial.empresas LIMIT 1) THEN
                RAISE EXCEPTION
                    'comercial.empresas is empty — cannot populate empresa_id. '
                    'Ensure the seed empresa was created in Phase 2.';
            END IF;
        END $$
    """)
    _exec(f"""
        ALTER TABLE {schema_table}
        ADD COLUMN IF NOT EXISTS empresa_id UUID
        REFERENCES comercial.empresas(id)
    """)
    _exec(f"""
        UPDATE {schema_table}
        SET empresa_id = (SELECT id FROM comercial.empresas LIMIT 1)
        WHERE empresa_id IS NULL
    """)
    _exec(f"ALTER TABLE {schema_table} ALTER COLUMN empresa_id SET NOT NULL")


def _add_empresa_id_nullable(schema_table: str) -> None:
    """Add empresa_id (FK → comercial.empresas) as NULLABLE (system rows)."""
    _exec(f"""
        ALTER TABLE {schema_table}
        ADD COLUMN IF NOT EXISTS empresa_id UUID
        REFERENCES comercial.empresas(id)
    """)


# ---------------------------------------------------------------------------
# upgrade
# ---------------------------------------------------------------------------

def upgrade() -> None:

    # =========================================================================
    # 1. Create schemas
    # =========================================================================
    for s in [
        "comercial", "acesso", "cadastro", "veiculos", "contrato",
        "financeiro", "conta_bancaria", "cobranca", "config",
        "relatorios", "notificacoes", "logs",
    ]:
        _exec(f"CREATE SCHEMA IF NOT EXISTS {s}")

    # =========================================================================
    # 2. Create comercial.empresas + seed default empresa
    # =========================================================================
    _exec("""
        CREATE TABLE IF NOT EXISTS comercial.empresas (
            id            UUID         DEFAULT gen_random_uuid() PRIMARY KEY,
            razao_social  TEXT         NOT NULL,
            nome_fantasia TEXT,
            cnpj          VARCHAR(14)  UNIQUE NOT NULL,
            email         TEXT         NOT NULL,
            telefone      VARCHAR(20),
            cep           VARCHAR(8),
            logradouro    TEXT,
            numero        TEXT,
            complemento   TEXT,
            bairro        TEXT,
            cidade        TEXT,
            estado        VARCHAR(2),
            ativo         BOOLEAN      NOT NULL DEFAULT TRUE,
            criado_em     TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            atualizado_em TIMESTAMPTZ  NOT NULL DEFAULT NOW(),
            excluido_em   TIMESTAMPTZ
        )
    """)
    _exec("""
        INSERT INTO comercial.empresas (razao_social, cnpj, email, nome_fantasia)
        VALUES ('Empresa Padrão', '00000000000100', 'admin@sistema.local', 'Sistema')
        ON CONFLICT (cnpj) DO NOTHING
    """)

    # =========================================================================
    # 3. Drop materialized views, triggers, old indexes
    # =========================================================================
    _exec("DROP MATERIALIZED VIEW IF EXISTS mv_vehicle_metrics CASCADE")
    _exec("DROP MATERIALIZED VIEW IF EXISTS mv_customer_metrics CASCADE")
    _exec("DROP MATERIALIZED VIEW IF EXISTS mv_receivables_summary CASCADE")

    _exec("DROP TRIGGER IF EXISTS trg_audit_log_immutable ON audit_log")
    _exec("DROP FUNCTION IF EXISTS prevent_audit_log_mutation() CASCADE")

    for idx in [
        "idx_users_active", "idx_refresh_user",
        "idx_audit_user_created", "idx_audit_entity",
        "idx_audit_log_action", "idx_audit_log_entity",
        "idx_audit_log_user_id", "idx_audit_log_created_at",
        "idx_assets_module_id", "idx_assets_external_ref",
        "idx_hooks_module_event", "idx_event_log_status",
        "idx_customers_cpf_cnpj", "idx_customers_status",
        "idx_customers_full_name_trgm", "idx_customers_fullname_trgm",
        "idx_customers_cpf_trgm", "idx_attachments_customer",
        "idx_vehicles_plate", "idx_vehicles_customer_id",
        "idx_vehicles_status", "idx_tracker_devices_vehicle_id",
        "idx_contracts_customer_id", "idx_contracts_status",
        "idx_contracts_contract_number", "idx_contracts_number_trgm",
        "idx_contracts_next_generation",
        "idx_installments_contract_id", "idx_installments_status",
        "idx_installments_due_date", "idx_installments_generation_id",
        "idx_contract_events_contract_id",
        "idx_installment_adjustments_installment_id",
        "idx_installment_generations_contract_id",
        "idx_expense_categories_parent_id", "idx_suppliers_cpf_cnpj",
        "idx_payables_supplier_id", "idx_payables_category_id",
        "idx_payables_status", "idx_payables_due_date",
        "idx_payables_linked_installment_id",
        "idx_integration_credentials_provider",
        "idx_integration_credentials_category",
        "idx_webhook_events_raw_provider",
        "idx_webhook_events_raw_processed",
        "idx_conversations_customer_id",
        "idx_conversations_channel_status",
        "idx_conversations_phone", "idx_conversations_last_msg",
        "idx_conv_messages_conv_sent", "idx_agent_runs_conv",
        "idx_customer_scores_cust_calc",
        "idx_btx_status", "idx_btx_posted",
    ]:
        _exec(f"DROP INDEX IF EXISTS {idx}")

    # =========================================================================
    # 4. Drop FK columns that reference tables being dropped (assets/active_modules)
    # =========================================================================
    _exec("ALTER TABLE vehicles       DROP COLUMN IF EXISTS asset_id")
    _exec("ALTER TABLE contracts      DROP COLUMN IF EXISTS asset_id")

    # Drop FK from module_hooks_config → active_modules using DO block
    _exec("""
        DO $$ BEGIN
            IF EXISTS (
                SELECT 1 FROM information_schema.table_constraints
                WHERE constraint_name = 'module_hooks_config_module_id_fkey'
                  AND table_name = 'module_hooks_config'
            ) THEN
                ALTER TABLE module_hooks_config
                    DROP CONSTRAINT module_hooks_config_module_id_fkey;
            END IF;
        END $$
    """)

    # =========================================================================
    # 5. Move tables: SET SCHEMA then RENAME
    # =========================================================================
    moves = [
        # (current public name,  new_schema,       new_name)
        ("users",                       "acesso",        "usuarios"),
        ("roles",                       "acesso",        "perfis"),
        ("permissions",                 "acesso",        "permissoes"),
        ("user_roles",                  "acesso",        "usuario_perfis"),
        ("role_permissions",            "acesso",        "perfil_permissoes"),
        ("refresh_tokens",              "acesso",        "refresh_tokens"),
        ("audit_log",                   "logs",          "log_auditoria"),
        ("event_log",                   "logs",          "log_eventos"),
        ("webhook_events_raw",          "notificacoes",  "webhooks_brutos"),
        ("module_hooks_config",         "config",        "politicas_eventos_modulo"),
        ("integration_credentials",     "config",        "credenciais_integracao"),
        ("customers",                   "cadastro",      "clientes"),
        ("customer_attachments",        "cadastro",      "anexos_cliente"),
        ("suppliers",                   "cadastro",      "fornecedores"),
        ("expense_categories",          "cadastro",      "categorias_despesa"),
        ("vehicles",                    "veiculos",      "veiculos"),
        ("vehicle_acquisitions",        "veiculos",      "aquisicoes_veiculo"),
        ("tracker_devices",             "veiculos",      "dispositivos_rastreamento"),
        ("contracts",                   "contrato",      "contratos"),
        ("contract_events",             "contrato",      "eventos_contrato"),
        ("installment_generations",     "contrato",      "lotes_geracao"),
        ("installments",                "financeiro",    "titulos_receber"),
        ("installment_adjustments",     "financeiro",    "movimentos_titulo_receber"),
        ("payables",                    "financeiro",    "titulos_pagar"),
        ("recurring_payable_templates", "financeiro",    "despesas_recorrentes"),
        ("bank_accounts",               "conta_bancaria","contas_bancarias"),
        ("bank_transactions",           "conta_bancaria","transacoes_bancarias"),
        ("reconciliation_sessions",     "conta_bancaria","sessoes_conciliacao"),
        ("conversations",               "cobranca",      "conversas"),
        ("conversation_messages",       "cobranca",      "mensagens"),
        ("agent_configs",               "cobranca",      "configuracoes_agente"),
        ("agent_runs",                  "cobranca",      "execucoes_agente"),
        ("customer_scores",             "cobranca",      "scores_clientes"),
        ("broadcast_campaigns",         "cobranca",      "campanhas_disparo"),
        ("saved_reports",               "relatorios",    "relatorios_salvos"),
    ]

    for current, new_schema, new_name in moves:
        _exec(f"ALTER TABLE public.{current} SET SCHEMA {new_schema}")
        if current != new_name:
            _exec(f"ALTER TABLE {new_schema}.{current} RENAME TO {new_name}")

    # system_settings: structural change too large — drop and recreate
    _exec("DROP TABLE IF EXISTS public.system_settings CASCADE")
    _exec("""
        CREATE TABLE config.configuracoes_sistema (
            id                UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
            empresa_id        UUID        NOT NULL REFERENCES comercial.empresas(id),
            chave             TEXT        NOT NULL,
            valor             JSONB       NOT NULL,
            descricao         TEXT,
            atualizado_por_id UUID        REFERENCES acesso.usuarios(id),
            atualizado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (empresa_id, chave)
        )
    """)

    # Drop asset abstraction layer tables
    _exec("DROP TABLE IF EXISTS public.active_modules CASCADE")
    _exec("DROP TABLE IF EXISTS public.assets CASCADE")

    # =========================================================================
    # 6. Rename columns
    # =========================================================================

    # --- acesso.usuarios ---
    for old, new in [
        ("password_hash",    "senha_hash"),
        ("full_name",        "nome_completo"),
        ("is_active",        "ativo"),
        ("is_mfa_enabled",   "mfa_ativo"),
        ("last_login_at",    "ultimo_login_em"),
        ("created_at",       "criado_em"),
        ("updated_at",       "atualizado_em"),
        ("deleted_at",       "excluido_em"),
    ]:
        _exec(f"ALTER TABLE acesso.usuarios RENAME COLUMN {old} TO {new}")

    # --- acesso.perfis ---
    for old, new in [
        ("name",        "nome"),
        ("description", "descricao"),
        ("created_at",  "criado_em"),
        ("updated_at",  "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE acesso.perfis RENAME COLUMN {old} TO {new}")

    # --- acesso.permissoes ---
    for old, new in [
        ("code",        "codigo"),
        ("description", "descricao"),
        ("created_at",  "criado_em"),
        ("updated_at",  "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE acesso.permissoes RENAME COLUMN {old} TO {new}")

    # --- acesso.usuario_perfis (was user_roles) ---
    for old, new in [
        ("user_id", "usuario_id"),
        ("role_id", "perfil_id"),
    ]:
        _exec(f"ALTER TABLE acesso.usuario_perfis RENAME COLUMN {old} TO {new}")

    # --- acesso.perfil_permissoes (was role_permissions) ---
    for old, new in [
        ("role_id",       "perfil_id"),
        ("permission_id", "permissao_id"),
    ]:
        _exec(f"ALTER TABLE acesso.perfil_permissoes RENAME COLUMN {old} TO {new}")

    # --- acesso.refresh_tokens ---
    for old, new in [
        ("user_id",    "usuario_id"),
        ("expires_at", "expira_em"),
        ("revoked_at", "revogado_em"),
        ("created_at", "criado_em"),
    ]:
        _exec(f"ALTER TABLE acesso.refresh_tokens RENAME COLUMN {old} TO {new}")

    # --- logs.log_auditoria ---
    for old, new in [
        ("entity",         "entidade"),
        ("entity_id",      "entidade_id"),
        ("signature_hmac", "hmac_assinatura"),
        ("created_at",     "criado_em"),
    ]:
        _exec(f"ALTER TABLE logs.log_auditoria RENAME COLUMN {old} TO {new}")

    # --- logs.log_eventos ---
    for old, new in [
        ("event_type",         "tipo_evento"),
        ("asset_type",         "tipo_ativo"),
        ("dispatched_at",      "despachado_em"),
        ("processed_at",       "processado_em"),
        ("processing_status",  "status_processamento"),
        ("error",              "erro"),
    ]:
        _exec(f"ALTER TABLE logs.log_eventos RENAME COLUMN {old} TO {new}")

    # --- notificacoes.webhooks_brutos ---
    for old, new in [
        ("provider",      "provedor"),
        ("processed",     "processado"),
        ("error_message", "erro"),
        ("received_at",   "recebido_em"),
    ]:
        _exec(f"ALTER TABLE notificacoes.webhooks_brutos RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE notificacoes.webhooks_brutos DROP COLUMN IF EXISTS event_type")

    # --- config.politicas_eventos_modulo ---
    for old, new in [
        ("event_type", "tipo_evento"),
        ("is_active",  "ativo"),
    ]:
        _exec(f"ALTER TABLE config.politicas_eventos_modulo RENAME COLUMN {old} TO {new}")

    # --- config.credenciais_integracao ---
    for old, new in [
        ("provider",          "provedor"),
        ("category",          "categoria"),
        ("is_active",         "ativo"),
        ("last_health_check", "ultimo_health_check"),
        ("created_at",        "criado_em"),
        ("updated_at",        "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE config.credenciais_integracao RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE config.credenciais_integracao DROP COLUMN IF EXISTS credential_type")
    _exec("ALTER TABLE config.credenciais_integracao DROP COLUMN IF EXISTS credentials_encrypted")

    # --- cadastro.clientes ---
    for old, new in [
        ("full_name",            "nome_completo"),
        ("phone",                "telefone"),
        ("birth_date",           "data_nascimento"),
        ("photo_url",            "foto_url"),
        ("notes",                "observacoes"),
        ("address_street",       "logradouro"),
        ("address_number",       "numero"),
        ("address_complement",   "complemento"),
        ("address_neighborhood", "bairro"),
        ("address_city",         "cidade"),
        ("address_state",        "estado"),
        ("address_zip",          "cep"),
        ("metadata_extensions",  "metadata_extensoes"),
        ("created_by_user_id",   "criado_por_id"),
        ("created_at",           "criado_em"),
        ("updated_at",           "atualizado_em"),
        ("deleted_at",           "excluido_em"),
    ]:
        _exec(f"ALTER TABLE cadastro.clientes RENAME COLUMN {old} TO {new}")

    # --- cadastro.anexos_cliente ---
    for old, new in [
        ("customer_id", "cliente_id"),
        ("kind",        "tipo"),
        ("mime",        "mime_type"),
        ("size",        "tamanho_bytes"),
        ("uploaded_at", "criado_em"),
    ]:
        _exec(f"ALTER TABLE cadastro.anexos_cliente RENAME COLUMN {old} TO {new}")

    # --- cadastro.fornecedores ---
    for old, new in [
        ("name",       "nome"),
        ("cpf_cnpj",   "documento"),
        ("is_active",  "ativo"),
        ("created_at", "criado_em"),
        ("updated_at", "atualizado_em"),
        ("deleted_at", "excluido_em"),
    ]:
        _exec(f"ALTER TABLE cadastro.fornecedores RENAME COLUMN {old} TO {new}")
    for col in ("phone", "email", "notes"):
        _exec(f"ALTER TABLE cadastro.fornecedores DROP COLUMN IF EXISTS {col}")

    # --- cadastro.categorias_despesa ---
    for old, new in [
        ("name",      "nome"),
        ("parent_id", "categoria_pai_id"),
        ("is_active", "ativo"),
        ("created_at","criado_em"),
        ("updated_at","atualizado_em"),
    ]:
        _exec(f"ALTER TABLE cadastro.categorias_despesa RENAME COLUMN {old} TO {new}")

    # --- veiculos.veiculos ---
    for old, new in [
        ("plate",        "placa"),
        ("brand",        "fipe_marca"),
        ("model_name",   "fipe_modelo"),
        ("model_year",   "ano_modelo"),
        ("fab_year",     "ano_fabricacao"),
        ("color",        "cor"),
        ("fipe_code",    "fipe_codigo"),
        ("fipe_value",   "fipe_valor_atual"),
        ("customer_id",  "cliente_atual_id"),
        ("tracker_id",   "rastreador_codigo"),
        ("created_at",   "criado_em"),
        ("updated_at",   "atualizado_em"),
        ("deleted_at",   "excluido_em"),
    ]:
        _exec(f"ALTER TABLE veiculos.veiculos RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE veiculos.veiculos DROP COLUMN IF EXISTS metadata")

    # --- veiculos.aquisicoes_veiculo ---
    for old, new in [
        ("vehicle_id",      "veiculo_id"),
        ("acquisition_type","tipo"),
        ("purchase_price",  "valor_aquisicao"),
        ("purchase_date",   "data_aquisicao"),
        ("created_at",      "criado_em"),
        ("updated_at",      "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE veiculos.aquisicoes_veiculo RENAME COLUMN {old} TO {new}")
    for col in ("financing_bank","financing_contract","financing_installments",
                "financing_monthly_value","notes"):
        _exec(f"ALTER TABLE veiculos.aquisicoes_veiculo DROP COLUMN IF EXISTS {col}")

    # --- veiculos.dispositivos_rastreamento ---
    for old, new in [
        ("vehicle_id", "veiculo_id"),
        ("device_id",  "serial"),
        ("created_at", "criado_em"),
        ("updated_at", "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE veiculos.dispositivos_rastreamento RENAME COLUMN {old} TO {new}")
    for col in ("config","last_position","is_active","provider"):
        _exec(f"ALTER TABLE veiculos.dispositivos_rastreamento DROP COLUMN IF EXISTS {col}")

    # --- contrato.contratos ---
    # Drop check constraints (reference old column names)
    for ck in ("ck_contracts_generation_mode","ck_contracts_correction_index",
               "ck_contracts_generation_day_range","ck_contracts_monthly_requires_fields"):
        _exec(f"ALTER TABLE contrato.contratos DROP CONSTRAINT IF EXISTS {ck}")

    for old, new in [
        ("customer_id",       "cliente_id"),
        ("contract_number",   "numero"),
        ("total_value",       "valor_total"),
        ("clauses",           "clausulas_md"),
        ("pdf_version",       "versao"),
        ("start_date",        "data_inicio"),
        ("end_date",          "data_fim"),
        ("created_by_user_id","criado_por_id"),
        ("created_at",        "criado_em"),
        ("updated_at",        "atualizado_em"),
        ("deleted_at",        "excluido_em"),
        ("generation_mode",   "modo_geracao"),
        ("correction_index",  "indice_correcao"),
        ("generation_day",    "dia_geracao"),
        ("next_generation_date","proxima_geracao_em"),
        ("monthly_base_value","valor_base_mensal"),
    ]:
        _exec(f"ALTER TABLE contrato.contratos RENAME COLUMN {old} TO {new}")
    for col in ("notes","terms"):
        _exec(f"ALTER TABLE contrato.contratos DROP COLUMN IF EXISTS {col}")

    # --- contrato.eventos_contrato ---
    for old, new in [
        ("contract_id",       "contrato_id"),
        ("event_type",        "tipo"),
        ("created_by_user_id","criado_por_id"),
        ("created_at",        "criado_em"),
    ]:
        _exec(f"ALTER TABLE contrato.eventos_contrato RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE contrato.eventos_contrato DROP COLUMN IF EXISTS description")

    # --- contrato.lotes_geracao ---
    for old, new in [
        ("contract_id",         "contrato_id"),
        ("generated_by_user_id","criado_por_id"),
        ("generated_at",        "criado_em"),
    ]:
        _exec(f"ALTER TABLE contrato.lotes_geracao RENAME COLUMN {old} TO {new}")
    for col in ("generation_number","config","status"):
        _exec(f"ALTER TABLE contrato.lotes_geracao DROP COLUMN IF EXISTS {col}")

    # --- financeiro.titulos_receber ---
    for old, new in [
        ("contract_id",          "contrato_id"),
        ("generation_id",        "lote_id"),
        ("parent_installment_id","titulo_origem_id"),
        ("number",               "sequencia"),
        ("due_date",             "data_vencimento"),
        ("original_value",       "valor"),
        ("paid_value",           "valor_pago"),
        ("payment_date",         "pago_em"),
        ("payment_method",       "forma_pagamento"),
        ("receipt_url",          "comprovante_url"),
        ("notes",                "observacoes"),
        ("created_at",           "criado_em"),
        ("updated_at",           "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE financeiro.titulos_receber RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE financeiro.titulos_receber DROP COLUMN IF EXISTS current_value")

    # --- financeiro.movimentos_titulo_receber ---
    for old, new in [
        ("installment_id",    "titulo_id"),
        ("kind",              "tipo"),
        ("reason",            "motivo"),
        ("created_by_user_id","aplicado_por_id"),
        ("created_at",        "aplicado_em"),
    ]:
        _exec(f"ALTER TABLE financeiro.movimentos_titulo_receber RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE financeiro.movimentos_titulo_receber DROP COLUMN IF EXISTS old_value")
    _exec("ALTER TABLE financeiro.movimentos_titulo_receber DROP COLUMN IF EXISTS new_value")

    # --- financeiro.titulos_pagar ---
    for old, new in [
        ("supplier_id",          "fornecedor_id"),
        ("category_id",          "categoria_id"),
        ("description",          "descricao"),
        ("amount",               "valor"),
        ("due_date",             "data_vencimento"),
        ("payment_date",         "data_pagamento"),
        ("payment_method",       "forma_pagamento"),
        ("linked_installment_id","titulo_receber_origem_id"),
        ("notes",                "observacoes"),
        ("receipt_url",          "comprovante_url"),
        ("recurring_template_id","template_id"),
        ("created_by_user_id",   "criado_por_id"),
        ("created_at",           "criado_em"),
        ("updated_at",           "atualizado_em"),
        ("deleted_at",           "excluido_em"),
    ]:
        _exec(f"ALTER TABLE financeiro.titulos_pagar RENAME COLUMN {old} TO {new}")

    # --- financeiro.despesas_recorrentes ---
    for old, new in [
        ("supplier_id",       "fornecedor_id"),
        ("category_id",       "categoria_id"),
        ("description",       "descricao"),
        ("amount",            "valor"),
        ("frequency",         "periodicidade"),
        ("day_of_month",      "dia_do_mes"),
        ("is_active",         "ativo"),
        ("next_generation_date","proxima_geracao_em"),
        ("created_by_user_id","criado_por_id"),
        ("created_at",        "criado_em"),
        ("updated_at",        "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE financeiro.despesas_recorrentes RENAME COLUMN {old} TO {new}")

    # --- conta_bancaria.contas_bancarias ---
    for old, new in [
        ("name",          "nome"),
        ("bank_code",     "codigo_banco"),
        ("agency",        "agencia"),
        ("account_number","numero_conta"),
        ("account_type",  "tipo"),
        ("is_active",     "ativo"),
        ("created_at",    "criado_em"),
        ("updated_at",    "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE conta_bancaria.contas_bancarias RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE conta_bancaria.contas_bancarias DROP COLUMN IF EXISTS bank_name")

    # --- conta_bancaria.transacoes_bancarias ---
    for old, new in [
        ("account_id",         "conta_id"),
        ("posted_at",          "lancado_em"),
        ("amount",             "valor"),
        ("description_raw",    "descricao_bruta"),
        ("description_clean",  "descricao_limpa"),
        ("type",               "tipo"),
        ("reconciled_to_kind", "conciliado_com_tipo"),
        ("reconciled_to_id",   "conciliado_com_id"),
        ("imported_from",      "importado_de"),
        ("imported_at",        "importado_em"),
    ]:
        _exec(f"ALTER TABLE conta_bancaria.transacoes_bancarias RENAME COLUMN {old} TO {new}")
    _exec("ALTER TABLE conta_bancaria.transacoes_bancarias DROP COLUMN IF EXISTS raw_data")

    # --- conta_bancaria.sessoes_conciliacao ---
    for old, new in [
        ("bank_account_id","conta_id"),
        ("period_start",   "periodo_inicio"),
        ("period_end",     "periodo_fim"),
        ("created_by",     "criado_por_id"),
        ("created_at",     "criado_em"),
    ]:
        _exec(f"ALTER TABLE conta_bancaria.sessoes_conciliacao RENAME COLUMN {old} TO {new}")

    # --- cobranca.conversas ---
    for old, new in [
        ("customer_id",      "cliente_id"),
        ("phone_e164",       "telefone"),
        ("channel",          "canal"),
        ("last_message_at",  "ultima_mensagem_em"),
        ("unread_count",     "nao_lidas"),
        ("is_archived",      "arquivada"),
        ("agent_active",     "agente_ativo"),
        ("agent_paused_until","agente_pausado_ate"),
        ("created_at",       "criado_em"),
        ("updated_at",       "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE cobranca.conversas RENAME COLUMN {old} TO {new}")
    for col in ("user_id","status"):
        _exec(f"ALTER TABLE cobranca.conversas DROP COLUMN IF EXISTS {col}")

    # --- cobranca.mensagens ---
    for old, new in [
        ("conversation_id","conversa_id"),
        ("role",           "direcao"),
        ("content_text",   "conteudo_texto"),
        ("media_url",      "midia_url"),
        ("media_mime",     "midia_mime"),
        ("transcription",  "transcricao"),
        ("sent_by",        "enviado_por"),
        ("metadata_extra", "contexto"),
        ("sent_at",        "enviado_em"),
        ("delivered_at",   "entregue_em"),
        ("read_at",        "lido_em"),
        ("created_at",     "criado_em"),
    ]:
        _exec(f"ALTER TABLE cobranca.mensagens RENAME COLUMN {old} TO {new}")
    for col in ("tool_call_id","tool_name"):
        _exec(f"ALTER TABLE cobranca.mensagens DROP COLUMN IF EXISTS {col}")

    # --- cobranca.configuracoes_agente ---
    for old, new in [
        ("name",          "nome"),
        ("system_prompt", "instrucoes_sistema"),
        ("llm_provider",  "provedor_llm"),
        ("llm_model",     "modelo_llm"),
        ("is_active",     "ativo"),
        ("created_at",    "criado_em"),
        ("updated_at",    "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE cobranca.configuracoes_agente RENAME COLUMN {old} TO {new}")
    for col in ("channel","whatsapp_provider","tools_enabled",
                "rate_limit_per_hour","budget_limit_monthly",
                "persona_config","policy_config"):
        _exec(f"ALTER TABLE cobranca.configuracoes_agente DROP COLUMN IF EXISTS {col}")

    # --- cobranca.execucoes_agente ---
    for old, new in [
        ("conversation_id",  "conversa_id"),
        ("prompt_tokens",    "tokens_entrada"),
        ("completion_tokens","tokens_saida"),
        ("tools_called",     "ferramentas_chamadas"),
        ("error",            "erro"),
        ("cost_usd",         "custo_usd"),
        ("started_at",       "criado_em"),
    ]:
        _exec(f"ALTER TABLE cobranca.execucoes_agente RENAME COLUMN {old} TO {new}")
    for col in ("agent_config_id","completed_at","iterations","total_tokens","status"):
        _exec(f"ALTER TABLE cobranca.execucoes_agente DROP COLUMN IF EXISTS {col}")

    # --- cobranca.scores_clientes ---
    for old, new in [
        ("customer_id",  "cliente_id"),
        ("factors",      "detalhamento"),
        ("calculated_at","calculado_em"),
    ]:
        _exec(f"ALTER TABLE cobranca.scores_clientes RENAME COLUMN {old} TO {new}")

    # --- cobranca.campanhas_disparo ---
    for old, new in [
        ("name",             "nome"),
        ("template",         "mensagem"),
        ("audience_filter",  "filtros"),
        ("total_recipients", "total_destinatarios"),
        ("sent_count",       "enviadas"),
        ("created_by",       "criado_por_id"),
        ("created_at",       "criado_em"),
        ("scheduled_at",     "agendado_para"),
    ]:
        _exec(f"ALTER TABLE cobranca.campanhas_disparo RENAME COLUMN {old} TO {new}")

    # --- relatorios.relatorios_salvos ---
    for old, new in [
        ("name",          "nome"),
        ("owner_user_id", "criado_por_id"),
        ("definition",    "filtros"),
        ("created_at",    "criado_em"),
        ("updated_at",    "atualizado_em"),
    ]:
        _exec(f"ALTER TABLE relatorios.relatorios_salvos RENAME COLUMN {old} TO {new}")
    for col in ("description","is_shared"):
        _exec(f"ALTER TABLE relatorios.relatorios_salvos DROP COLUMN IF EXISTS {col}")

    # =========================================================================
    # 7. Add empresa_id to tenant-scoped tables
    # =========================================================================
    for tbl in [
        "acesso.usuarios", "acesso.usuario_perfis", "acesso.refresh_tokens",
        "cadastro.clientes", "cadastro.anexos_cliente", "cadastro.fornecedores",
        "financeiro.titulos_receber", "financeiro.movimentos_titulo_receber",
        "financeiro.titulos_pagar", "financeiro.despesas_recorrentes",
        "veiculos.veiculos", "veiculos.aquisicoes_veiculo",
        "veiculos.dispositivos_rastreamento",
        "contrato.contratos", "contrato.eventos_contrato", "contrato.lotes_geracao",
        "conta_bancaria.contas_bancarias", "conta_bancaria.transacoes_bancarias",
        "conta_bancaria.sessoes_conciliacao",
        "cobranca.conversas", "cobranca.mensagens",
        "cobranca.configuracoes_agente", "cobranca.execucoes_agente",
        "cobranca.scores_clientes", "cobranca.campanhas_disparo",
        "config.politicas_eventos_modulo", "config.credenciais_integracao",
        "relatorios.relatorios_salvos",
    ]:
        _add_empresa_id_not_null(tbl)

    # Nullable empresa_id (system rows have no empresa)
    for tbl in [
        "logs.log_auditoria", "logs.log_eventos",
        "notificacoes.webhooks_brutos", "cadastro.categorias_despesa",
    ]:
        _add_empresa_id_nullable(tbl)

    # =========================================================================
    # 8. Add new columns (schema_v2 fields not in original tables)
    # =========================================================================

    # contrato.contratos
    for col_def in [
        "veiculo_id UUID REFERENCES veiculos.veiculos(id)",
        "periodicidade TEXT",
        "dia_vencimento SMALLINT",
        "juros_mora_dia_pct NUMERIC(8,4) DEFAULT 0",
        "multa_mora_pct NUMERIC(8,4) DEFAULT 0",
        "dias_carencia SMALLINT DEFAULT 0",
        "tem_opcao_compra BOOLEAN DEFAULT FALSE",
        "valor_residual NUMERIC(15,2)",
        "assinado_em TIMESTAMPTZ",
        "encerrado_em DATE",
        "motivo_encerramento TEXT",
    ]:
        _exec(f"ALTER TABLE contrato.contratos ADD COLUMN IF NOT EXISTS {col_def}")

    # veiculos.veiculos
    for col_def in [
        "rastreador_imei TEXT",
        "chip_operadora TEXT",
        "chip_numero TEXT",
        "seguro_vencimento DATE",
        "ipva_vencimento DATE",
        "licenciamento_vencimento DATE",
        "foto_url TEXT",
        "observacoes TEXT",
        "fipe_atualizado_em DATE",
        "criado_por_id UUID REFERENCES acesso.usuarios(id)",
    ]:
        _exec(f"ALTER TABLE veiculos.veiculos ADD COLUMN IF NOT EXISTS {col_def}")

    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS status TEXT NOT NULL DEFAULT 'ativo'")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS modelo TEXT")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS fabricante TEXT")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS imei TEXT")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS ultima_posicao_lat NUMERIC(10,7)")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS ultima_posicao_lng NUMERIC(10,7)")
    _exec("ALTER TABLE veiculos.dispositivos_rastreamento "
          "ADD COLUMN IF NOT EXISTS ultima_comunicacao_em TIMESTAMPTZ")

    # veiculos.aquisicoes_veiculo
    for col_def in [
        "entrada NUMERIC(15,2) DEFAULT 0",
        "parcelas JSONB DEFAULT '[]'",
        "taxa_juros NUMERIC(8,4)",
        "sistema_amortizacao TEXT",
    ]:
        _exec(f"ALTER TABLE veiculos.aquisicoes_veiculo ADD COLUMN IF NOT EXISTS {col_def}")

    # contrato.lotes_geracao
    for col_def in [
        "rotulo TEXT",
        "qtd_titulos INTEGER DEFAULT 0",
        "valor_total NUMERIC(15,2) DEFAULT 0",
        "tem_movimento_financeiro BOOLEAN DEFAULT FALSE",
        "revertido_em TIMESTAMPTZ",
        "revertido_por_id UUID REFERENCES acesso.usuarios(id)",
    ]:
        _exec(f"ALTER TABLE contrato.lotes_geracao ADD COLUMN IF NOT EXISTS {col_def}")

    # financeiro.titulos_receber
    _exec("ALTER TABLE financeiro.titulos_receber ADD COLUMN IF NOT EXISTS "
          "tipo TEXT DEFAULT 'regular'")
    _exec("ALTER TABLE financeiro.titulos_receber ADD COLUMN IF NOT EXISTS "
          "criado_por_id UUID REFERENCES acesso.usuarios(id)")

    # financeiro.movimentos_titulo_receber
    for col_def in [
        "delta_valor NUMERIC(15,2)",
        "snapshot_antes JSONB",
        "snapshot_depois JSONB",
    ]:
        _exec(f"ALTER TABLE financeiro.movimentos_titulo_receber "
              f"ADD COLUMN IF NOT EXISTS {col_def}")

    # financeiro.despesas_recorrentes
    _exec("ALTER TABLE financeiro.despesas_recorrentes ADD COLUMN IF NOT EXISTS data_inicio DATE")
    _exec("ALTER TABLE financeiro.despesas_recorrentes ADD COLUMN IF NOT EXISTS data_fim DATE")

    # conta_bancaria.sessoes_conciliacao
    for col_def in [
        "total_transacoes INTEGER DEFAULT 0",
        "total_conciliadas INTEGER DEFAULT 0",
        "concluida_em TIMESTAMPTZ",
    ]:
        _exec(f"ALTER TABLE conta_bancaria.sessoes_conciliacao ADD COLUMN IF NOT EXISTS {col_def}")

    # cobranca.mensagens
    _exec("ALTER TABLE cobranca.mensagens ADD COLUMN IF NOT EXISTS tipo TEXT DEFAULT 'texto'")

    # cobranca.configuracoes_agente
    for col_def in [
        "tipo TEXT DEFAULT 'cobranca'",
        "temperatura NUMERIC(4,2) DEFAULT 0.70",
        "max_tokens INTEGER DEFAULT 1000",
        "persona_nome TEXT",
        "tom TEXT",
    ]:
        _exec(f"ALTER TABLE cobranca.configuracoes_agente ADD COLUMN IF NOT EXISTS {col_def}")

    # cobranca.execucoes_agente
    for col_def in [
        "mensagem_id UUID REFERENCES cobranca.mensagens(id)",
        "provedor TEXT",
        "modelo TEXT",
        "latencia_ms INTEGER",
        "acao_final TEXT",
    ]:
        _exec(f"ALTER TABLE cobranca.execucoes_agente ADD COLUMN IF NOT EXISTS {col_def}")

    # cobranca.scores_clientes
    for col_def in [
        "pontualidade_pct NUMERIC(5,2)",
        "dias_atraso_medio NUMERIC(5,2)",
        "tempo_relacionamento_meses INTEGER",
        "valor_total_pago NUMERIC(15,2)",
    ]:
        _exec(f"ALTER TABLE cobranca.scores_clientes ADD COLUMN IF NOT EXISTS {col_def}")

    # cobranca.campanhas_disparo
    for col_def in [
        "entregues INTEGER DEFAULT 0",
        "lidas INTEGER DEFAULT 0",
        "falhas INTEGER DEFAULT 0",
        "iniciado_em TIMESTAMPTZ",
        "concluido_em TIMESTAMPTZ",
        "atualizado_em TIMESTAMPTZ DEFAULT NOW()",
    ]:
        _exec(f"ALTER TABLE cobranca.campanhas_disparo ADD COLUMN IF NOT EXISTS {col_def}")

    # notificacoes.webhooks_brutos
    _exec("ALTER TABLE notificacoes.webhooks_brutos ADD COLUMN IF NOT EXISTS external_id TEXT")
    _exec("ALTER TABLE notificacoes.webhooks_brutos ADD COLUMN IF NOT EXISTS processado_em TIMESTAMPTZ")

    # cadastro.anexos_cliente
    _exec("ALTER TABLE cadastro.anexos_cliente ADD COLUMN IF NOT EXISTS nome_arquivo TEXT")
    _exec("ALTER TABLE cadastro.anexos_cliente ADD COLUMN IF NOT EXISTS "
          "criado_por_id UUID REFERENCES acesso.usuarios(id)")

    # cadastro.fornecedores
    _exec("ALTER TABLE cadastro.fornecedores ADD COLUMN IF NOT EXISTS contato TEXT")
    _exec("ALTER TABLE cadastro.fornecedores ADD COLUMN IF NOT EXISTS dados_bancarios JSONB DEFAULT '{}'")

    # cadastro.categorias_despesa
    for col_def in ["cor VARCHAR(7)", "icone TEXT", "ordem SMALLINT DEFAULT 0"]:
        _exec(f"ALTER TABLE cadastro.categorias_despesa ADD COLUMN IF NOT EXISTS {col_def}")

    # relatorios.relatorios_salvos
    _exec("ALTER TABLE relatorios.relatorios_salvos ADD COLUMN IF NOT EXISTS tipo TEXT")
    _exec("ALTER TABLE relatorios.relatorios_salvos ADD COLUMN IF NOT EXISTS colunas JSONB DEFAULT '[]'")

    # logs.log_eventos
    _exec("ALTER TABLE logs.log_eventos ADD COLUMN IF NOT EXISTS "
          "criado_em TIMESTAMPTZ DEFAULT NOW()")

    # =========================================================================
    # 9. Resolve circular FK (veiculos ↔ contratos)
    # =========================================================================
    _exec("""
        ALTER TABLE veiculos.veiculos
        ADD COLUMN IF NOT EXISTS contrato_ativo_id UUID
        REFERENCES contrato.contratos(id)
    """)

    # =========================================================================
    # 10. Unique constraints
    # =========================================================================
    _exec("""
        DO $$ BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'uq_webhooks_provedor_external'
            ) THEN
                ALTER TABLE notificacoes.webhooks_brutos
                ADD CONSTRAINT uq_webhooks_provedor_external
                UNIQUE (provedor, external_id);
            END IF;
        END $$
    """)

    # =========================================================================
    # 11. Recreate indexes
    # =========================================================================
    simple_indexes = [
        # acesso
        ("idx_usuarios_empresa",       "acesso.usuarios",                    "(empresa_id)"),
        ("idx_usuarios_email",         "acesso.usuarios",                    "(email)"),
        ("idx_usuario_perfis_empresa", "acesso.usuario_perfis",              "(empresa_id)"),
        ("idx_refresh_tokens_empresa", "acesso.refresh_tokens",              "(empresa_id)"),
        # cadastro
        ("idx_clientes_empresa",       "cadastro.clientes",                  "(empresa_id)"),
        ("idx_clientes_status",        "cadastro.clientes",                  "(empresa_id, status)"),
        ("idx_clientes_cpf_cnpj",      "cadastro.clientes",                  "(empresa_id, cpf_cnpj)"),
        ("idx_fornecedores_empresa",   "cadastro.fornecedores",              "(empresa_id)"),
        ("idx_categorias_empresa",     "cadastro.categorias_despesa",        "(empresa_id)"),
        ("idx_anexos_cliente",         "cadastro.anexos_cliente",            "(empresa_id, cliente_id)"),
        # veiculos
        ("idx_veiculos_empresa",       "veiculos.veiculos",                  "(empresa_id)"),
        ("idx_veiculos_placa",         "veiculos.veiculos",                  "(empresa_id, placa)"),
        ("idx_veiculos_status",        "veiculos.veiculos",                  "(empresa_id, status)"),
        ("idx_veiculos_cliente",       "veiculos.veiculos",                  "(cliente_atual_id)"),
        ("idx_dispositivos_empresa",   "veiculos.dispositivos_rastreamento", "(empresa_id)"),
        ("idx_dispositivos_veiculo",   "veiculos.dispositivos_rastreamento", "(veiculo_id)"),
        # contrato
        ("idx_contratos_empresa",      "contrato.contratos",                 "(empresa_id)"),
        ("idx_contratos_cliente",      "contrato.contratos",                 "(empresa_id, cliente_id)"),
        ("idx_contratos_veiculo",      "contrato.contratos",                 "(empresa_id, veiculo_id)"),
        ("idx_contratos_status",       "contrato.contratos",                 "(empresa_id, status)"),
        ("idx_eventos_contrato",       "contrato.eventos_contrato",          "(empresa_id, contrato_id)"),
        ("idx_lotes_geracao",          "contrato.lotes_geracao",             "(empresa_id, contrato_id)"),
        # financeiro
        ("idx_tit_rec_empresa",        "financeiro.titulos_receber",         "(empresa_id)"),
        ("idx_tit_rec_contrato",       "financeiro.titulos_receber",         "(empresa_id, contrato_id)"),
        ("idx_tit_rec_status",         "financeiro.titulos_receber",         "(empresa_id, status)"),
        ("idx_tit_rec_venc",           "financeiro.titulos_receber",         "(empresa_id, data_vencimento)"),
        ("idx_tit_rec_lote",           "financeiro.titulos_receber",         "(lote_id)"),
        ("idx_movimentos_titulo",      "financeiro.movimentos_titulo_receber","(empresa_id, titulo_id)"),
        ("idx_tit_pag_empresa",        "financeiro.titulos_pagar",           "(empresa_id)"),
        ("idx_tit_pag_status",         "financeiro.titulos_pagar",           "(empresa_id, status)"),
        ("idx_tit_pag_venc",           "financeiro.titulos_pagar",           "(empresa_id, data_vencimento)"),
        ("idx_despesas_rec_empresa",   "financeiro.despesas_recorrentes",    "(empresa_id)"),
        # conta_bancaria
        ("idx_contas_banco_empresa",   "conta_bancaria.contas_bancarias",    "(empresa_id)"),
        ("idx_transacoes_empresa",     "conta_bancaria.transacoes_bancarias","(empresa_id)"),
        ("idx_transacoes_conta",       "conta_bancaria.transacoes_bancarias","(empresa_id, conta_id)"),
        ("idx_transacoes_status",      "conta_bancaria.transacoes_bancarias","(empresa_id, status)"),
        ("idx_sessoes_conciliacao",    "conta_bancaria.sessoes_conciliacao", "(empresa_id, conta_id)"),
        # cobranca
        ("idx_conversas_empresa",      "cobranca.conversas",                 "(empresa_id)"),
        ("idx_conversas_cliente",      "cobranca.conversas",                 "(empresa_id, cliente_id)"),
        ("idx_conversas_telefone",     "cobranca.conversas",                 "(empresa_id, telefone)"),
        ("idx_mensagens_empresa",      "cobranca.mensagens",                 "(empresa_id)"),
        ("idx_mensagens_conversa",     "cobranca.mensagens",                 "(empresa_id, conversa_id)"),
        ("idx_execucoes_empresa",      "cobranca.execucoes_agente",          "(empresa_id)"),
        ("idx_scores_empresa",         "cobranca.scores_clientes",           "(empresa_id, cliente_id)"),
        ("idx_campanhas_empresa",      "cobranca.campanhas_disparo",         "(empresa_id)"),
        # config
        ("idx_config_sistema",         "config.configuracoes_sistema",       "(empresa_id)"),
        ("idx_politicas_empresa",      "config.politicas_eventos_modulo",    "(empresa_id)"),
        ("idx_credenciais_empresa",    "config.credenciais_integracao",      "(empresa_id)"),
        # logs
        ("idx_log_audit_empresa",      "logs.log_auditoria",                 "(empresa_id)"),
        ("idx_log_audit_entidade",     "logs.log_auditoria",                 "(entidade, entidade_id)"),
        ("idx_log_audit_criado",       "logs.log_auditoria",                 "(criado_em DESC)"),
        ("idx_log_eventos_empresa",    "logs.log_eventos",                   "(empresa_id)"),
        # notificacoes
        ("idx_webhooks_empresa",       "notificacoes.webhooks_brutos",       "(empresa_id)"),
        ("idx_webhooks_provedor",      "notificacoes.webhooks_brutos",       "(provedor)"),
    ]
    for name, table, cols in simple_indexes:
        _exec(f"CREATE INDEX IF NOT EXISTS {name} ON {table} {cols}")

    # Partial indexes
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_contratos_prox_geracao
        ON contrato.contratos (empresa_id, proxima_geracao_em)
        WHERE modo_geracao = 'mensal' AND excluido_em IS NULL
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_despesas_prox_geracao
        ON financeiro.despesas_recorrentes (empresa_id, proxima_geracao_em)
        WHERE ativo = TRUE
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_webhooks_nao_processados
        ON notificacoes.webhooks_brutos (recebido_em)
        WHERE processado = FALSE
    """)
    _exec("""
        CREATE INDEX IF NOT EXISTS idx_log_eventos_status
        ON logs.log_eventos (status_processamento)
        WHERE status_processamento IN ('pendente', 'processando')
    """)

    # =========================================================================
    # 11b. Recreate check constraints on contrato.contratos (dropped in Phase 6)
    # =========================================================================
    _exec("""
        ALTER TABLE contrato.contratos
        ADD CONSTRAINT ck_contratos_modo_geracao
        CHECK (modo_geracao IN ('antecipado', 'mensal'))
    """)
    _exec("""
        ALTER TABLE contrato.contratos
        ADD CONSTRAINT ck_contratos_indice_correcao
        CHECK (indice_correcao IS NULL OR indice_correcao IN ('igpm', 'ipca', 'inpc'))
    """)
    _exec("""
        ALTER TABLE contrato.contratos
        ADD CONSTRAINT ck_contratos_dia_geracao
        CHECK (dia_geracao IS NULL OR (dia_geracao BETWEEN 1 AND 28))
    """)
    _exec("""
        ALTER TABLE contrato.contratos
        ADD CONSTRAINT ck_contratos_mensal_requer_campos
        CHECK (
            modo_geracao <> 'mensal' OR (
                dia_geracao IS NOT NULL
                AND proxima_geracao_em IS NOT NULL
                AND valor_base_mensal IS NOT NULL
            )
        )
    """)

    # =========================================================================
    # 12. Recreate triggers (DROP IF EXISTS first for idempotency)
    # =========================================================================
    _exec("DROP TRIGGER IF EXISTS trg_log_auditoria_immutable ON logs.log_auditoria")
    _exec("""
        CREATE OR REPLACE FUNCTION logs.prevent_log_auditoria_mutation()
        RETURNS trigger AS $$
        BEGIN RAISE EXCEPTION 'log_auditoria is append-only'; END;
        $$ LANGUAGE plpgsql
    """)
    _exec("""
        CREATE TRIGGER trg_log_auditoria_immutable
        BEFORE UPDATE OR DELETE ON logs.log_auditoria
        FOR EACH ROW EXECUTE FUNCTION logs.prevent_log_auditoria_mutation()
    """)

    _exec("DROP TRIGGER IF EXISTS trg_titulo_receber_pago_immutable ON financeiro.titulos_receber")
    _exec("""
        CREATE OR REPLACE FUNCTION financeiro.enforce_titulo_pago_immutability()
        RETURNS trigger AS $$
        BEGIN
            IF OLD.status = 'pago' THEN
                RAISE EXCEPTION 'titulo_receber with status=pago is immutable';
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
    """)
    _exec("""
        CREATE TRIGGER trg_titulo_receber_pago_immutable
        BEFORE UPDATE ON financeiro.titulos_receber
        FOR EACH ROW EXECUTE FUNCTION financeiro.enforce_titulo_pago_immutability()
    """)

    # =========================================================================
    # 13. Recreate materialized views (DROP IF EXISTS first for idempotency)
    # =========================================================================
    _exec("DROP MATERIALIZED VIEW IF EXISTS financeiro.mv_resumo_receber CASCADE")
    _exec("DROP MATERIALIZED VIEW IF EXISTS cadastro.mv_metricas_clientes CASCADE")
    _exec("DROP MATERIALIZED VIEW IF EXISTS veiculos.mv_metricas_veiculos CASCADE")

    _exec("""
        CREATE MATERIALIZED VIEW financeiro.mv_resumo_receber AS
        SELECT
            tr.empresa_id,
            tr.contrato_id,
            COUNT(*)                                                        AS total_titulos,
            SUM(tr.valor)                                                   AS valor_total,
            SUM(CASE WHEN tr.status = 'em_aberto' THEN tr.valor ELSE 0 END) AS em_aberto,
            SUM(CASE WHEN tr.status = 'vencido'   THEN tr.valor ELSE 0 END) AS vencido,
            COALESCE(SUM(CASE WHEN tr.status = 'pago' THEN tr.valor_pago ELSE 0 END), 0) AS recebido
        FROM financeiro.titulos_receber tr
        GROUP BY tr.empresa_id, tr.contrato_id
        WITH NO DATA
    """)
    _exec("""
        CREATE UNIQUE INDEX idx_mv_resumo_receber
        ON financeiro.mv_resumo_receber (empresa_id, contrato_id)
    """)

    _exec("""
        CREATE MATERIALIZED VIEW cadastro.mv_metricas_clientes AS
        SELECT
            c.empresa_id,
            c.id                                                          AS cliente_id,
            COUNT(DISTINCT co.id)                                         AS total_contratos,
            COALESCE(SUM(tr.valor_pago), 0)                               AS total_recebido,
            COALESCE(SUM(CASE WHEN tr.status IN ('em_aberto','vencido')
                              THEN tr.valor END), 0)                      AS saldo_aberto,
            MAX(sc.score)                                                 AS score_atual
        FROM cadastro.clientes c
        LEFT JOIN contrato.contratos co
               ON co.cliente_id = c.id AND co.excluido_em IS NULL
        LEFT JOIN financeiro.titulos_receber tr ON tr.contrato_id = co.id
        LEFT JOIN cobranca.scores_clientes sc   ON sc.cliente_id  = c.id
        GROUP BY c.empresa_id, c.id
        WITH NO DATA
    """)
    _exec("""
        CREATE UNIQUE INDEX idx_mv_metricas_clientes
        ON cadastro.mv_metricas_clientes (empresa_id, cliente_id)
    """)

    _exec("""
        CREATE MATERIALIZED VIEW veiculos.mv_metricas_veiculos AS
        SELECT
            v.empresa_id,
            v.id                                        AS veiculo_id,
            v.fipe_valor_atual,
            COALESCE(aq.valor_aquisicao, 0)             AS valor_aquisicao,
            COALESCE(SUM(tr.valor_pago), 0)             AS total_recebido,
            COALESCE(SUM(tr.valor_pago), 0)
                - COALESCE(aq.valor_aquisicao, 0)       AS lucro_acumulado
        FROM veiculos.veiculos v
        LEFT JOIN veiculos.aquisicoes_veiculo aq
               ON aq.veiculo_id = v.id
        LEFT JOIN contrato.contratos co
               ON co.veiculo_id = v.id AND co.excluido_em IS NULL
        LEFT JOIN financeiro.titulos_receber tr
               ON tr.contrato_id = co.id AND tr.status = 'pago'
        GROUP BY v.empresa_id, v.id, v.fipe_valor_atual, aq.valor_aquisicao
        WITH NO DATA
    """)
    _exec("""
        CREATE UNIQUE INDEX idx_mv_metricas_veiculos
        ON veiculos.mv_metricas_veiculos (empresa_id, veiculo_id)
    """)


# ---------------------------------------------------------------------------
# downgrade  — drops all new schemas CASCADE (data loss accepted in dev)
# ---------------------------------------------------------------------------

def downgrade() -> None:
    for s in [
        "financeiro", "contrato", "veiculos", "cadastro",
        "cobranca", "conta_bancaria", "config",
        "relatorios", "notificacoes", "logs",
        "acesso", "comercial",
    ]:
        _exec(f"DROP SCHEMA IF EXISTS {s} CASCADE")
