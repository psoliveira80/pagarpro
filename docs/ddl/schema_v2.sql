-- =============================================================================
-- SCHEMA V2 — Reestruturação completa com multi-tenancy
-- =============================================================================
-- Gerado em: 2026-05-21
-- Convenções:
--   - Todos os PKs: UUID gerado por gen_random_uuid()
--   - Timestamps: TIMESTAMPTZ (com fuso)
--   - Soft delete: coluna excluido_em TIMESTAMPTZ
--   - Multi-tenancy: empresa_id NOT NULL em todas as tabelas de dados
--   - Booleans: sem prefixo "is_" (ativo, não is_active)
--   - FKs circulares (veiculos ↔ contratos): resolvidas via ALTER TABLE no final
-- =============================================================================

-- Extensões (executar uma vez no banco)
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE EXTENSION IF NOT EXISTS unaccent;
CREATE EXTENSION IF NOT EXISTS vector;

-- =============================================================================
-- SCHEMAS
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS comercial;
CREATE SCHEMA IF NOT EXISTS acesso;
CREATE SCHEMA IF NOT EXISTS cadastro;
CREATE SCHEMA IF NOT EXISTS veiculos;
CREATE SCHEMA IF NOT EXISTS contrato;
CREATE SCHEMA IF NOT EXISTS financeiro;
CREATE SCHEMA IF NOT EXISTS conta_bancaria;
CREATE SCHEMA IF NOT EXISTS cobranca;
CREATE SCHEMA IF NOT EXISTS config;
CREATE SCHEMA IF NOT EXISTS relatorios;
CREATE SCHEMA IF NOT EXISTS notificacoes;
CREATE SCHEMA IF NOT EXISTS logs;


-- =============================================================================
-- COMERCIAL — Empresas que contratam o sistema (raiz multi-tenant)
-- =============================================================================

CREATE TABLE comercial.empresas (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    razao_social        TEXT        NOT NULL,
    nome_fantasia       TEXT,
    cnpj                VARCHAR(14) UNIQUE NOT NULL,
    email               TEXT        NOT NULL,
    telefone            VARCHAR(20),
    -- endereço
    cep                 VARCHAR(8),
    logradouro          TEXT,
    numero              TEXT,
    complemento         TEXT,
    bairro              TEXT,
    cidade              TEXT,
    estado              VARCHAR(2),
    -- status
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    -- timestamps
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em         TIMESTAMPTZ
);


-- =============================================================================
-- ACESSO — Identidade, perfis e permissões
-- =============================================================================

-- Perfis são globais (Admin, Operador, Validador, Auditor)
CREATE TABLE acesso.perfis (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    nome        VARCHAR(100) UNIQUE NOT NULL,
    descricao   TEXT,
    is_admin    BOOLEAN     NOT NULL DEFAULT FALSE,
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Permissões são globais — catálogo do que o sistema permite
CREATE TABLE acesso.permissoes (
    id          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    codigo      VARCHAR(100) UNIQUE NOT NULL,   -- ex: 'titulos_receber.baixar'
    descricao   TEXT,
    modulo      VARCHAR(50),                    -- ex: 'financeiro', 'veiculos'
    criado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Mapeamento perfil → permissões (global)
CREATE TABLE acesso.perfil_permissoes (
    perfil_id       UUID NOT NULL REFERENCES acesso.perfis(id)     ON DELETE CASCADE,
    permissao_id    UUID NOT NULL REFERENCES acesso.permissoes(id)  ON DELETE CASCADE,
    PRIMARY KEY (perfil_id, permissao_id)
);

-- Usuários pertencem a uma empresa
CREATE TABLE acesso.usuarios (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    email               CITEXT      UNIQUE NOT NULL,
    senha_hash          TEXT        NOT NULL,
    nome_completo       TEXT        NOT NULL,
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    mfa_ativo           BOOLEAN     NOT NULL DEFAULT FALSE,
    mfa_secret_enc      BYTEA,
    ultimo_login_em     TIMESTAMPTZ,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em         TIMESTAMPTZ
);

-- Vínculo usuário → perfil, dentro do contexto da empresa
CREATE TABLE acesso.usuario_perfis (
    id              UUID    DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID    NOT NULL REFERENCES comercial.empresas(id),
    usuario_id      UUID    NOT NULL REFERENCES acesso.usuarios(id)  ON DELETE CASCADE,
    perfil_id       UUID    NOT NULL REFERENCES acesso.perfis(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, usuario_id, perfil_id)
);

CREATE TABLE acesso.refresh_tokens (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    usuario_id      UUID        NOT NULL REFERENCES acesso.usuarios(id) ON DELETE CASCADE,
    token_hash      TEXT        UNIQUE NOT NULL,
    expira_em       TIMESTAMPTZ NOT NULL,
    revogado_em     TIMESTAMPTZ,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- CADASTRO — Clientes, fornecedores e categorias
-- =============================================================================

-- empresa_id nullable = categoria global/padrão do sistema
CREATE TABLE cadastro.categorias_despesa (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        REFERENCES comercial.empresas(id),
    categoria_pai_id    UUID        REFERENCES cadastro.categorias_despesa(id),
    nome                TEXT        NOT NULL,
    cor                 VARCHAR(7),
    icone               TEXT,
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    ordem               SMALLINT    NOT NULL DEFAULT 0,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cadastro.clientes (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome_completo       TEXT        NOT NULL,
    cpf_cnpj            VARCHAR(14) NOT NULL,
    email               TEXT,
    telefone            VARCHAR(20),
    data_nascimento     DATE,
    -- endereço
    cep                 VARCHAR(8),
    logradouro          TEXT,
    numero              TEXT,
    complemento         TEXT,
    bairro              TEXT,
    cidade              TEXT,
    estado              VARCHAR(2),
    -- perfil
    foto_url            TEXT,
    observacoes         TEXT,
    score               SMALLINT    NOT NULL DEFAULT 100,
    status              TEXT        NOT NULL DEFAULT 'ativo'
                            CHECK (status IN ('ativo', 'inativo', 'bloqueado')),
    tags                JSONB       NOT NULL DEFAULT '[]',
    metadata_extensoes  JSONB       NOT NULL DEFAULT '{}',
    -- auditoria
    criado_por_id       UUID        REFERENCES acesso.usuarios(id),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em         TIMESTAMPTZ,
    UNIQUE (empresa_id, cpf_cnpj)
);

CREATE TABLE cadastro.anexos_cliente (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    cliente_id      UUID        NOT NULL REFERENCES cadastro.clientes(id) ON DELETE CASCADE,
    nome_arquivo    TEXT        NOT NULL,
    tipo            TEXT,           -- 'cnh', 'rg', 'comprovante_residencia', etc.
    url             TEXT        NOT NULL,
    tamanho_bytes   BIGINT,
    mime_type       TEXT,
    criado_por_id   UUID        REFERENCES acesso.usuarios(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cadastro.fornecedores (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome            TEXT        NOT NULL,
    documento       VARCHAR(14),
    contato         TEXT,
    dados_bancarios JSONB       NOT NULL DEFAULT '{}',
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em     TIMESTAMPTZ
);


-- =============================================================================
-- VEICULOS — Módulo vertical de frota
-- Nota: contrato_ativo_id adicionado via ALTER TABLE após criação de contrato.contratos
-- =============================================================================

CREATE TABLE veiculos.veiculos (
    id                      UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id              UUID        NOT NULL REFERENCES comercial.empresas(id),
    -- identificação
    placa                   VARCHAR(8)  NOT NULL,
    renavam                 VARCHAR(11),
    chassi                  VARCHAR(17),
    cor                     TEXT,
    ano_fabricacao          SMALLINT,
    ano_modelo              SMALLINT,
    -- FIPE
    fipe_codigo             TEXT,
    fipe_marca              TEXT,
    fipe_modelo             TEXT,
    fipe_valor_atual        NUMERIC(15,2),
    fipe_atualizado_em      DATE,
    -- rastreamento
    rastreador_codigo       TEXT,
    rastreador_imei         TEXT,
    chip_operadora          TEXT,
    chip_numero             TEXT,
    -- documentação
    seguro_vencimento       DATE,
    ipva_vencimento         DATE,
    licenciamento_vencimento DATE,
    -- status
    status                  TEXT        NOT NULL DEFAULT 'disponivel'
                                CHECK (status IN ('disponivel', 'em_uso', 'manutencao', 'inativo')),
    foto_url                TEXT,
    observacoes             TEXT,
    -- denormalizado para consulta rápida (FK adicionada depois)
    contrato_ativo_id       UUID,
    cliente_atual_id        UUID        REFERENCES cadastro.clientes(id),
    -- auditoria
    criado_por_id           UUID        REFERENCES acesso.usuarios(id),
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em             TIMESTAMPTZ,
    UNIQUE (empresa_id, placa)
);

-- Aquisição de veículo: registro histórico imutável do custo de aquisição.
-- Fonte para cálculo de lucro do veículo (receita do contrato - custo de aquisição).
-- Quando forma='parcelado', N títulos a pagar são gerados em financeiro.titulos_pagar
-- no momento da criação (não pelo motor scheduler). Quitação antecipada cancela
-- as parcelas restantes em titulos_pagar; a linha de aquisição permanece imutável.
CREATE TABLE veiculos.aquisicoes_veiculo (
    id                       UUID          DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id               UUID          NOT NULL REFERENCES comercial.empresas(id),
    veiculo_id               UUID          NOT NULL REFERENCES veiculos.veiculos(id) ON DELETE CASCADE,
    fornecedor_id            UUID          REFERENCES cadastro.fornecedores(id),
    forma                    TEXT          NOT NULL DEFAULT 'avista'
                                 CHECK (forma IN ('avista', 'parcelado')),

    -- composição do valor
    data_aquisicao           DATE          NOT NULL,
    valor_total              NUMERIC(15,2) NOT NULL,
    valor_entrada            NUMERIC(15,2) NOT NULL DEFAULT 0,
    valor_troca              NUMERIC(15,2) NOT NULL DEFAULT 0,
    veiculo_usado_id         UUID          REFERENCES veiculos.veiculos(id),
    valor_financiado         NUMERIC(15,2) GENERATED ALWAYS AS
                                 (valor_total - valor_entrada - valor_troca) STORED,

    -- dados do financiamento (todos NULL quando forma='avista')
    banco                    TEXT,
    contrato_financiamento   TEXT,
    qtd_parcelas             INTEGER       CHECK (qtd_parcelas IS NULL OR qtd_parcelas > 0),
    taxa_juros_mes_pct       NUMERIC(8,4)  DEFAULT 0
                                 CHECK (taxa_juros_mes_pct IS NULL OR taxa_juros_mes_pct >= 0),
    sistema_amortizacao      TEXT
                                 CHECK (sistema_amortizacao IS NULL
                                        OR sistema_amortizacao IN ('price','sac','sem_juros')),
    data_primeira_parcela    DATE,

    observacoes              TEXT,
    criado_por_id            UUID          REFERENCES acesso.usuarios(id),
    criado_em                TIMESTAMPTZ   NOT NULL DEFAULT NOW(),
    atualizado_em            TIMESTAMPTZ   NOT NULL DEFAULT NOW(),

    CONSTRAINT ck_aquisicao_parcelado_requer_campos CHECK (
        forma <> 'parcelado' OR (
            qtd_parcelas IS NOT NULL
            AND sistema_amortizacao IS NOT NULL
            AND data_primeira_parcela IS NOT NULL
        )
    ),
    CONSTRAINT ck_aquisicao_valor_total_positivo CHECK (valor_total > 0),
    CONSTRAINT ck_aquisicao_entrada_nao_excede CHECK (
        valor_entrada >= 0 AND valor_troca >= 0
        AND (valor_entrada + valor_troca) <= valor_total
    ),
    CONSTRAINT ck_aquisicao_veiculo_usado_difere CHECK (
        veiculo_usado_id IS NULL OR veiculo_usado_id <> veiculo_id
    )
);

CREATE TABLE veiculos.dispositivos_rastreamento (
    id                      UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id              UUID        NOT NULL REFERENCES comercial.empresas(id),
    veiculo_id              UUID        REFERENCES veiculos.veiculos(id),
    serial                  TEXT        NOT NULL,
    modelo                  TEXT,
    fabricante              TEXT,
    imei                    TEXT,
    status                  TEXT        NOT NULL DEFAULT 'ativo'
                                CHECK (status IN ('ativo', 'inativo', 'manutencao')),
    ultima_posicao_lat      NUMERIC(10,7),
    ultima_posicao_lng      NUMERIC(10,7),
    ultima_comunicacao_em   TIMESTAMPTZ,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, serial)
);


-- =============================================================================
-- CONTRATO — Contratos e ciclo de vida
-- =============================================================================

CREATE TABLE contrato.contratos (
    id                      UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id              UUID        NOT NULL REFERENCES comercial.empresas(id),
    numero                  TEXT        NOT NULL,
    cliente_id              UUID        NOT NULL REFERENCES cadastro.clientes(id),
    veiculo_id              UUID        NOT NULL REFERENCES veiculos.veiculos(id),
    status                  TEXT        NOT NULL DEFAULT 'rascunho'
                                CHECK (status IN ('rascunho', 'vigente', 'encerrado', 'rescindido')),
    -- vigência
    data_inicio             DATE        NOT NULL,
    data_fim                DATE,
    -- valores
    valor_total             NUMERIC(15,2) NOT NULL,
    periodicidade           TEXT        NOT NULL
                                CHECK (periodicidade IN ('mensal','bimestral','trimestral','semestral','anual','personalizado')),
    dia_vencimento          SMALLINT    NOT NULL CHECK (dia_vencimento BETWEEN 1 AND 28),
    -- encargos
    juros_mora_dia_pct      NUMERIC(8,4) NOT NULL DEFAULT 0,
    multa_mora_pct          NUMERIC(8,4) NOT NULL DEFAULT 0,
    dias_carencia           SMALLINT    NOT NULL DEFAULT 0,
    -- geração de títulos
    modo_geracao            TEXT        NOT NULL DEFAULT 'antecipado'
                                CHECK (modo_geracao IN ('antecipado', 'mensal')),
    indice_correcao         TEXT        CHECK (indice_correcao IN ('igpm', 'ipca', 'inpc')),
    dia_geracao             SMALLINT    CHECK (dia_geracao BETWEEN 1 AND 28),
    proxima_geracao_em      DATE,
    valor_base_mensal       NUMERIC(15,2),
    -- opção de compra
    tem_opcao_compra        BOOLEAN     NOT NULL DEFAULT FALSE,
    valor_residual          NUMERIC(15,2),
    -- documento
    clausulas_md            TEXT,
    pdf_url                 TEXT,
    versao                  SMALLINT    NOT NULL DEFAULT 1,
    -- assinatura e encerramento
    assinado_em             TIMESTAMPTZ,
    encerrado_em            DATE,
    motivo_encerramento     TEXT,
    -- auditoria
    criado_por_id           UUID        REFERENCES acesso.usuarios(id),
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em             TIMESTAMPTZ,
    UNIQUE (empresa_id, numero)
);

-- Fecha FK circular: veículo aponta para contrato ativo
ALTER TABLE veiculos.veiculos
    ADD CONSTRAINT fk_contrato_ativo
    FOREIGN KEY (contrato_ativo_id) REFERENCES contrato.contratos(id);

CREATE TABLE contrato.eventos_contrato (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    contrato_id     UUID        NOT NULL REFERENCES contrato.contratos(id),
    tipo            TEXT        NOT NULL
                        CHECK (tipo IN (
                            'criado','assinado','titulos_gerados','titulos_reemitidos',
                            'edicao_em_lote','cancelamento_solicitado','encerrado','pdf_gerado'
                        )),
    payload         JSONB       NOT NULL DEFAULT '{}',
    pdf_hash        TEXT,
    criado_por_id   UUID        REFERENCES acesso.usuarios(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE contrato.lotes_geracao (
    id                      UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id              UUID        NOT NULL REFERENCES comercial.empresas(id),
    contrato_id             UUID        NOT NULL REFERENCES contrato.contratos(id),
    rotulo                  TEXT        NOT NULL,
    qtd_titulos             INTEGER     NOT NULL DEFAULT 0,
    valor_total             NUMERIC(15,2) NOT NULL DEFAULT 0,
    tem_movimento_financeiro BOOLEAN    NOT NULL DEFAULT FALSE,
    criado_por_id           UUID        REFERENCES acesso.usuarios(id),
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    revertido_em            TIMESTAMPTZ,
    revertido_por_id        UUID        REFERENCES acesso.usuarios(id)
);


-- =============================================================================
-- FINANCEIRO — Títulos a receber, a pagar e despesas recorrentes
-- =============================================================================

CREATE TABLE financeiro.titulos_receber (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    contrato_id         UUID        NOT NULL REFERENCES contrato.contratos(id),
    lote_id             UUID        REFERENCES contrato.lotes_geracao(id),
    sequencia           SMALLINT    NOT NULL,
    data_vencimento     DATE        NOT NULL,
    valor               NUMERIC(15,2) NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'em_aberto'
                            CHECK (status IN (
                                'em_aberto','vencido','pago_aguardando_verificacao',
                                'pago','pago_parcial','renegociado','cancelado'
                            )),
    tipo                TEXT        NOT NULL DEFAULT 'regular'
                            CHECK (tipo IN ('regular','entrada','extra_semestral','extra_anual','personalizado')),
    -- pagamento
    pago_em             DATE,
    valor_pago          NUMERIC(15,2),
    forma_pagamento     TEXT,
    comprovante_url     TEXT,
    -- origem em pagamento parcial
    titulo_origem_id    UUID        REFERENCES financeiro.titulos_receber(id),
    -- observações
    observacoes         TEXT,
    -- auditoria
    criado_por_id       UUID        REFERENCES acesso.usuarios(id),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, contrato_id, sequencia)
);

-- Trilha imutável de movimentos financeiros sobre um título a receber
CREATE TABLE financeiro.movimentos_titulo_receber (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    titulo_id       UUID        NOT NULL REFERENCES financeiro.titulos_receber(id),
    tipo            TEXT        NOT NULL
                        CHECK (tipo IN (
                            'baixa_parcial','desconto','juros','multa',
                            'renegociacao','edicao_em_lote','estorno'
                        )),
    delta_valor     NUMERIC(15,2) NOT NULL,
    snapshot_antes  JSONB,
    snapshot_depois JSONB,
    motivo          TEXT,
    aplicado_por_id UUID        REFERENCES acesso.usuarios(id),
    aplicado_em     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Templates de despesas fixas recorrentes
CREATE TABLE financeiro.despesas_recorrentes (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    fornecedor_id   UUID        REFERENCES cadastro.fornecedores(id),
    categoria_id    UUID        REFERENCES cadastro.categorias_despesa(id),
    veiculo_id      UUID        REFERENCES veiculos.veiculos(id),
    descricao       TEXT        NOT NULL,
    valor           NUMERIC(15,2) NOT NULL,
    periodicidade   TEXT        NOT NULL
                        CHECK (periodicidade IN ('mensal','bimestral','anual')),
    dia_do_mes      SMALLINT    NOT NULL CHECK (dia_do_mes BETWEEN 1 AND 28),
    data_inicio     DATE        NOT NULL,
    data_fim        DATE,
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    proxima_geracao_em DATE,
    criado_por_id   UUID        REFERENCES acesso.usuarios(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE financeiro.titulos_pagar (
    id                          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id                  UUID        NOT NULL REFERENCES comercial.empresas(id),
    fornecedor_id               UUID        REFERENCES cadastro.fornecedores(id),
    categoria_id                UUID        REFERENCES cadastro.categorias_despesa(id),
    veiculo_id                  UUID        REFERENCES veiculos.veiculos(id),
    descricao                   TEXT        NOT NULL,
    valor                       NUMERIC(15,2) NOT NULL,
    data_vencimento             DATE        NOT NULL,
    status                      TEXT        NOT NULL DEFAULT 'rascunho'
                                    CHECK (status IN ('rascunho','pendente','pago','cancelado')),
    -- pagamento
    data_pagamento              DATE,
    valor_pago                  NUMERIC(15,2),
    forma_pagamento             TEXT,
    comprovante_url             TEXT,
    -- origem direta 1-pra-1 (estorno de título a receber). Origens 1-pra-N
    -- (aquisição parcelada, despesa recorrente) ficam em tabelas de junção:
    -- veja financeiro.parcelas_aquisicao_veiculo e financeiro.geracoes_despesa_recorrente.
    titulo_receber_origem_id    UUID        REFERENCES financeiro.titulos_receber(id),
    -- observações
    observacoes                 TEXT,
    -- auditoria
    criado_por_id               UUID        REFERENCES acesso.usuarios(id),
    criado_em                   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    excluido_em                 TIMESTAMPTZ
);

-- Vincula parcelas de uma aquisição de veículo aos seus títulos a pagar.
-- N títulos são gerados de uma vez no momento da contratação (não pelo scheduler).
-- Quitação antecipada cancela os títulos restantes; a aquisição permanece imutável.
CREATE TABLE financeiro.parcelas_aquisicao_veiculo (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    aquisicao_id        UUID        NOT NULL REFERENCES veiculos.aquisicoes_veiculo(id)
                                      ON DELETE CASCADE,
    titulo_pagar_id     UUID        NOT NULL REFERENCES financeiro.titulos_pagar(id)
                                      ON DELETE CASCADE,
    numero              INTEGER     NOT NULL CHECK (numero > 0),  -- 1..qtd_parcelas
    UNIQUE (aquisicao_id, numero),
    UNIQUE (titulo_pagar_id)
);

-- Vincula gerações mensais de uma despesa recorrente aos seus títulos a pagar.
-- Motor scheduler insere 1 linha por mês quando gera o título correspondente.
CREATE TABLE financeiro.geracoes_despesa_recorrente (
    id                       UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    despesa_recorrente_id    UUID        NOT NULL REFERENCES financeiro.despesas_recorrentes(id)
                                           ON DELETE CASCADE,
    titulo_pagar_id          UUID        NOT NULL REFERENCES financeiro.titulos_pagar(id)
                                           ON DELETE CASCADE,
    mes_referencia           DATE        NOT NULL,  -- sempre dia 1 do mês de referência
    UNIQUE (despesa_recorrente_id, mes_referencia),
    UNIQUE (titulo_pagar_id)
);


-- =============================================================================
-- CONTA_BANCARIA — Contas, transações e reconciliação
-- =============================================================================

CREATE TABLE conta_bancaria.contas_bancarias (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome            TEXT        NOT NULL,
    codigo_banco    VARCHAR(5),
    agencia         VARCHAR(10),
    numero_conta    VARCHAR(20),
    tipo            TEXT        CHECK (tipo IN ('corrente','poupanca','pagamento')),
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE conta_bancaria.transacoes_bancarias (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    conta_id            UUID        NOT NULL REFERENCES conta_bancaria.contas_bancarias(id),
    fitid               TEXT        NOT NULL,
    lancado_em          DATE        NOT NULL,
    valor               NUMERIC(15,2) NOT NULL,   -- positivo = entrada, negativo = saída
    descricao_bruta     TEXT,
    descricao_limpa     TEXT,
    tipo                TEXT        CHECK (tipo IN ('credito','debito')),
    status              TEXT        NOT NULL DEFAULT 'pendente'
                            CHECK (status IN ('pendente','conciliada','ignorada')),
    conciliado_com_tipo TEXT        CHECK (conciliado_com_tipo IN ('titulo_receber','titulo_pagar','receita_avulsa')),
    conciliado_com_id   UUID,
    importado_de        TEXT        CHECK (importado_de IN ('ofx','pdf','open_finance','manual')),
    importado_em        TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, conta_id, fitid)
);

CREATE TABLE conta_bancaria.sessoes_conciliacao (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    conta_id            UUID        NOT NULL REFERENCES conta_bancaria.contas_bancarias(id),
    periodo_inicio      DATE        NOT NULL,
    periodo_fim         DATE        NOT NULL,
    status              TEXT        NOT NULL DEFAULT 'em_andamento'
                            CHECK (status IN ('em_andamento','concluida','cancelada')),
    total_transacoes    INTEGER     NOT NULL DEFAULT 0,
    total_conciliadas   INTEGER     NOT NULL DEFAULT 0,
    criado_por_id       UUID        REFERENCES acesso.usuarios(id),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    concluida_em        TIMESTAMPTZ
);


-- =============================================================================
-- COBRANCA — WhatsApp, agente IA e campanhas
-- =============================================================================

CREATE TABLE cobranca.conversas (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    cliente_id          UUID        REFERENCES cadastro.clientes(id),
    telefone            VARCHAR(20) NOT NULL,
    ultima_mensagem_em  TIMESTAMPTZ,
    nao_lidas           INTEGER     NOT NULL DEFAULT 0,
    arquivada           BOOLEAN     NOT NULL DEFAULT FALSE,
    agente_ativo        BOOLEAN     NOT NULL DEFAULT TRUE,
    agente_pausado_ate  TIMESTAMPTZ,
    canal               TEXT        NOT NULL DEFAULT 'whatsapp'
                            CHECK (canal IN ('whatsapp','in_app')),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cobranca.mensagens (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    conversa_id     UUID        NOT NULL REFERENCES cobranca.conversas(id),
    external_id     TEXT        UNIQUE,
    direcao         TEXT        NOT NULL CHECK (direcao IN ('entrada','saida')),
    tipo            TEXT        NOT NULL
                        CHECK (tipo IN ('texto','imagem','documento','audio','interativo')),
    conteudo_texto  TEXT,
    midia_url       TEXT,
    midia_mime      TEXT,
    enviado_em      TIMESTAMPTZ NOT NULL,
    entregue_em     TIMESTAMPTZ,
    lido_em         TIMESTAMPTZ,
    enviado_por     TEXT,       -- 'agente' ou 'humano:{usuario_id}'
    status          TEXT        CHECK (status IN ('pendente','enviado','entregue','lido','falhou')),
    contexto        JSONB       NOT NULL DEFAULT '{}',
    transcricao     TEXT,
    embedding       vector(1536),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cobranca.configuracoes_agente (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome                TEXT        NOT NULL,
    tipo                TEXT        NOT NULL
                            CHECK (tipo IN ('cobranca','assistente_interno')),
    provedor_llm        TEXT,
    modelo_llm          TEXT,
    temperatura         NUMERIC(4,2) NOT NULL DEFAULT 0.70,
    max_tokens          INTEGER     NOT NULL DEFAULT 1000,
    persona_nome        TEXT,
    tom                 TEXT,
    instrucoes_sistema  TEXT,
    ativo               BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cobranca.execucoes_agente (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    conversa_id         UUID        REFERENCES cobranca.conversas(id),
    mensagem_id         UUID        REFERENCES cobranca.mensagens(id),
    provedor            TEXT,
    modelo              TEXT,
    tokens_entrada      INTEGER,
    tokens_saida        INTEGER,
    latencia_ms         INTEGER,
    ferramentas_chamadas JSONB      NOT NULL DEFAULT '[]',
    acao_final          TEXT,
    erro                TEXT,
    custo_usd           NUMERIC(10,6),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cobranca.scores_clientes (
    id                          UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id                  UUID        NOT NULL REFERENCES comercial.empresas(id),
    cliente_id                  UUID        NOT NULL REFERENCES cadastro.clientes(id),
    score                       SMALLINT    NOT NULL,
    pontualidade_pct            NUMERIC(5,2),
    dias_atraso_medio           NUMERIC(5,2),
    tempo_relacionamento_meses  INTEGER,
    valor_total_pago            NUMERIC(15,2),
    detalhamento                JSONB       NOT NULL DEFAULT '{}',
    calculado_em                TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE cobranca.campanhas_disparo (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome                TEXT        NOT NULL,
    mensagem            TEXT        NOT NULL,
    filtros             JSONB       NOT NULL DEFAULT '{}',
    total_destinatarios INTEGER     NOT NULL DEFAULT 0,
    enviadas            INTEGER     NOT NULL DEFAULT 0,
    entregues           INTEGER     NOT NULL DEFAULT 0,
    lidas               INTEGER     NOT NULL DEFAULT 0,
    falhas              INTEGER     NOT NULL DEFAULT 0,
    status              TEXT        NOT NULL DEFAULT 'rascunho'
                            CHECK (status IN ('rascunho','agendada','em_andamento','concluida','cancelada')),
    agendado_para       TIMESTAMPTZ,
    iniciado_em         TIMESTAMPTZ,
    concluido_em        TIMESTAMPTZ,
    criado_por_id       UUID        REFERENCES acesso.usuarios(id),
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- CONFIG — Configurações, políticas e credenciais por empresa
-- =============================================================================

CREATE TABLE config.configuracoes_sistema (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    chave           TEXT        NOT NULL,
    valor           JSONB       NOT NULL,
    descricao       TEXT,
    atualizado_por_id UUID      REFERENCES acesso.usuarios(id),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, chave)
);

-- Políticas de reação automática a eventos de domínio por módulo
CREATE TABLE config.politicas_eventos_modulo (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    modulo_id       TEXT        NOT NULL,   -- 'veiculos', etc.
    tipo_evento     TEXT        NOT NULL,   -- 'titulo_vencido', 'titulo_pago', etc.
    politica        JSONB       NOT NULL DEFAULT '{}',
    ativo           BOOLEAN     NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, modulo_id, tipo_evento)
);

CREATE TABLE config.credenciais_integracao (
    id                  UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id          UUID        NOT NULL REFERENCES comercial.empresas(id),
    categoria           TEXT        NOT NULL,   -- 'whatsapp', 'gateway_pagamento', 'rastreamento'
    provedor            TEXT        NOT NULL,   -- 'evolution', 'asaas', 'anytrack'
    config              JSONB       NOT NULL DEFAULT '{}',  -- criptografado na camada app
    status              TEXT        NOT NULL DEFAULT 'inativo'
                            CHECK (status IN ('ativo','inativo','erro')),
    ultimo_health_check TIMESTAMPTZ,
    criado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, categoria, provedor)
);


-- =============================================================================
-- RELATORIOS — Relatórios salvos pelo usuário
-- =============================================================================

CREATE TABLE relatorios.relatorios_salvos (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        NOT NULL REFERENCES comercial.empresas(id),
    nome            TEXT        NOT NULL,
    tipo            TEXT        NOT NULL,
    filtros         JSONB       NOT NULL DEFAULT '{}',
    colunas         JSONB       NOT NULL DEFAULT '[]',
    criado_por_id   UUID        REFERENCES acesso.usuarios(id),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- NOTIFICACOES — Webhooks recebidos de providers externos
-- empresa_id nullable: webhook pode chegar antes da associação com a empresa
-- =============================================================================

CREATE TABLE notificacoes.webhooks_brutos (
    id              UUID        DEFAULT gen_random_uuid() PRIMARY KEY,
    empresa_id      UUID        REFERENCES comercial.empresas(id),
    provedor        TEXT        NOT NULL,    -- 'asaas', 'evolution', 'pluggy', etc.
    external_id     TEXT        NOT NULL,
    payload         JSONB       NOT NULL,
    processado      BOOLEAN     NOT NULL DEFAULT FALSE,
    processado_em   TIMESTAMPTZ,
    erro            TEXT,
    recebido_em     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (provedor, external_id)
);


-- =============================================================================
-- LOGS — Auditoria e eventos de domínio
-- empresa_id nullable: ações de sistema não têm empresa
-- =============================================================================

-- Append-only. Trigger bloqueia UPDATE e DELETE (criado na migration Alembic).
CREATE TABLE logs.log_auditoria (
    id              BIGSERIAL   PRIMARY KEY,
    empresa_id      UUID        REFERENCES comercial.empresas(id),
    usuario_id      UUID        REFERENCES acesso.usuarios(id),
    acao            TEXT        NOT NULL,
    entidade        TEXT        NOT NULL,
    entidade_id     TEXT,
    payload_antes   JSONB,
    payload_depois  JSONB,
    ip              INET,
    user_agent      TEXT,
    correlation_id  UUID,
    hmac_assinatura TEXT,
    modulo          TEXT,
    categoria       TEXT        NOT NULL DEFAULT 'info'
                        CHECK (categoria IN ('financeiro','navegacao','erro','info','seguranca')),
    severidade      TEXT        NOT NULL DEFAULT 'info'
                        CHECK (severidade IN ('debug','info','aviso','erro','critico')),
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Eventos de domínio publicados no barramento interno
CREATE TABLE logs.log_eventos (
    id                      BIGSERIAL   PRIMARY KEY,
    empresa_id              UUID        REFERENCES comercial.empresas(id),
    event_id                UUID        UNIQUE NOT NULL,
    tipo_evento             TEXT        NOT NULL,
    tipo_ativo              TEXT,
    payload                 JSONB       NOT NULL DEFAULT '{}',
    despachado_em           TIMESTAMPTZ,
    processado_em           TIMESTAMPTZ,
    status_processamento    TEXT        NOT NULL DEFAULT 'pendente'
                                CHECK (status_processamento IN ('pendente','processando','concluido','falhou')),
    erro                    TEXT,
    criado_em               TIMESTAMPTZ NOT NULL DEFAULT NOW()
);


-- =============================================================================
-- MATERIALIZED VIEWS (estrutura — dados populados pelo worker)
-- =============================================================================

CREATE MATERIALIZED VIEW financeiro.mv_resumo_receber AS
SELECT
    tr.empresa_id,
    tr.contrato_id,
    COUNT(*)                                            AS total_titulos,
    SUM(tr.valor)                                       AS valor_total,
    SUM(CASE WHEN tr.status = 'em_aberto'   THEN tr.valor ELSE 0 END) AS em_aberto,
    SUM(CASE WHEN tr.status = 'vencido'     THEN tr.valor ELSE 0 END) AS vencido,
    SUM(CASE WHEN tr.status = 'pago'        THEN tr.valor_pago ELSE 0 END) AS recebido
FROM financeiro.titulos_receber tr
GROUP BY tr.empresa_id, tr.contrato_id
WITH NO DATA;

CREATE MATERIALIZED VIEW cadastro.mv_metricas_clientes AS
SELECT
    c.empresa_id,
    c.id                                                AS cliente_id,
    COUNT(DISTINCT co.id)                               AS total_contratos,
    COALESCE(SUM(tr.valor_pago), 0)                     AS total_recebido,
    COALESCE(SUM(CASE WHEN tr.status IN ('em_aberto','vencido') THEN tr.valor END), 0) AS saldo_aberto,
    MAX(sc.score)                                       AS score_atual
FROM cadastro.clientes c
LEFT JOIN contrato.contratos co    ON co.cliente_id  = c.id AND co.excluido_em IS NULL
LEFT JOIN financeiro.titulos_receber tr ON tr.contrato_id = co.id
LEFT JOIN cobranca.scores_clientes sc   ON sc.cliente_id  = c.id
GROUP BY c.empresa_id, c.id
WITH NO DATA;

CREATE MATERIALIZED VIEW veiculos.mv_metricas_veiculos AS
SELECT
    v.empresa_id,
    v.id                                                AS veiculo_id,
    v.fipe_valor_atual,
    COALESCE(aq.valor_total, 0)                     AS valor_aquisicao,
    COALESCE(SUM(tr.valor_pago), 0)                     AS total_recebido,
    COALESCE(SUM(tr.valor_pago), 0) - COALESCE(aq.valor_total, 0) AS lucro_acumulado
FROM veiculos.veiculos v
LEFT JOIN veiculos.aquisicoes_veiculo aq    ON aq.veiculo_id  = v.id
LEFT JOIN contrato.contratos co             ON co.veiculo_id  = v.id AND co.excluido_em IS NULL
LEFT JOIN financeiro.titulos_receber tr     ON tr.contrato_id = co.id AND tr.status = 'pago'
GROUP BY v.empresa_id, v.id, v.fipe_valor_atual, aq.valor_total
WITH NO DATA;


-- =============================================================================
-- ÍNDICES — Performance e multi-tenancy
-- =============================================================================

-- acesso
CREATE INDEX idx_usuarios_empresa          ON acesso.usuarios(empresa_id);
CREATE INDEX idx_usuarios_email            ON acesso.usuarios(email);
CREATE INDEX idx_usuario_perfis_empresa    ON acesso.usuario_perfis(empresa_id);
CREATE INDEX idx_refresh_tokens_usuario    ON acesso.refresh_tokens(usuario_id);
CREATE INDEX idx_refresh_tokens_empresa    ON acesso.refresh_tokens(empresa_id);

-- cadastro
CREATE INDEX idx_clientes_empresa          ON cadastro.clientes(empresa_id);
CREATE INDEX idx_clientes_cpf_cnpj         ON cadastro.clientes(empresa_id, cpf_cnpj);
CREATE INDEX idx_clientes_nome_trgm        ON cadastro.clientes USING gin(nome_completo gin_trgm_ops);
CREATE INDEX idx_clientes_status           ON cadastro.clientes(empresa_id, status);
CREATE INDEX idx_anexos_cliente            ON cadastro.anexos_cliente(empresa_id, cliente_id);
CREATE INDEX idx_fornecedores_empresa      ON cadastro.fornecedores(empresa_id);
CREATE INDEX idx_categorias_despesa_emp    ON cadastro.categorias_despesa(empresa_id);

-- veiculos
CREATE INDEX idx_veiculos_empresa          ON veiculos.veiculos(empresa_id);
CREATE INDEX idx_veiculos_placa            ON veiculos.veiculos(empresa_id, placa);
CREATE INDEX idx_veiculos_status           ON veiculos.veiculos(empresa_id, status);
CREATE INDEX idx_veiculos_cliente          ON veiculos.veiculos(cliente_atual_id);
CREATE INDEX idx_aquisicoes_empresa        ON veiculos.aquisicoes_veiculo(empresa_id);
CREATE INDEX idx_aquisicoes_veiculo        ON veiculos.aquisicoes_veiculo(veiculo_id);
CREATE INDEX idx_aquisicoes_forma          ON veiculos.aquisicoes_veiculo(empresa_id, forma);
CREATE INDEX idx_dispositivos_empresa      ON veiculos.dispositivos_rastreamento(empresa_id);
CREATE INDEX idx_dispositivos_veiculo      ON veiculos.dispositivos_rastreamento(veiculo_id);

-- contrato
CREATE INDEX idx_contratos_empresa         ON contrato.contratos(empresa_id);
CREATE INDEX idx_contratos_cliente         ON contrato.contratos(empresa_id, cliente_id);
CREATE INDEX idx_contratos_veiculo         ON contrato.contratos(empresa_id, veiculo_id);
CREATE INDEX idx_contratos_status          ON contrato.contratos(empresa_id, status);
CREATE INDEX idx_contratos_prox_geracao    ON contrato.contratos(empresa_id, proxima_geracao_em)
    WHERE modo_geracao = 'mensal' AND status = 'vigente';
CREATE INDEX idx_eventos_contrato          ON contrato.eventos_contrato(empresa_id, contrato_id);
CREATE INDEX idx_lotes_geracao_contrato    ON contrato.lotes_geracao(empresa_id, contrato_id);

-- financeiro
CREATE INDEX idx_titulos_receber_empresa   ON financeiro.titulos_receber(empresa_id);
CREATE INDEX idx_titulos_receber_contrato  ON financeiro.titulos_receber(empresa_id, contrato_id);
CREATE INDEX idx_titulos_receber_status    ON financeiro.titulos_receber(empresa_id, status);
CREATE INDEX idx_titulos_receber_venc      ON financeiro.titulos_receber(empresa_id, data_vencimento);
CREATE INDEX idx_titulos_receber_lote      ON financeiro.titulos_receber(lote_id);
CREATE INDEX idx_movimentos_titulo         ON financeiro.movimentos_titulo_receber(empresa_id, titulo_id);
CREATE INDEX idx_titulos_pagar_empresa     ON financeiro.titulos_pagar(empresa_id);
CREATE INDEX idx_titulos_pagar_status      ON financeiro.titulos_pagar(empresa_id, status);
CREATE INDEX idx_titulos_pagar_venc        ON financeiro.titulos_pagar(empresa_id, data_vencimento);
CREATE INDEX idx_titulos_pagar_fornecedor  ON financeiro.titulos_pagar(empresa_id, fornecedor_id);
CREATE INDEX idx_parc_aquisicao_aq         ON financeiro.parcelas_aquisicao_veiculo(aquisicao_id);
CREATE INDEX idx_parc_aquisicao_titulo     ON financeiro.parcelas_aquisicao_veiculo(titulo_pagar_id);
CREATE INDEX idx_ger_desp_rec_template     ON financeiro.geracoes_despesa_recorrente(despesa_recorrente_id);
CREATE INDEX idx_ger_desp_rec_titulo       ON financeiro.geracoes_despesa_recorrente(titulo_pagar_id);
CREATE INDEX idx_despesas_rec_empresa      ON financeiro.despesas_recorrentes(empresa_id);
CREATE INDEX idx_despesas_rec_prox_geracao ON financeiro.despesas_recorrentes(empresa_id, proxima_geracao_em)
    WHERE ativo = TRUE;

-- conta_bancaria
CREATE INDEX idx_contas_bancarias_empresa  ON conta_bancaria.contas_bancarias(empresa_id);
CREATE INDEX idx_transacoes_empresa        ON conta_bancaria.transacoes_bancarias(empresa_id);
CREATE INDEX idx_transacoes_conta          ON conta_bancaria.transacoes_bancarias(empresa_id, conta_id);
CREATE INDEX idx_transacoes_status         ON conta_bancaria.transacoes_bancarias(empresa_id, status);
CREATE INDEX idx_transacoes_lancado_em     ON conta_bancaria.transacoes_bancarias(empresa_id, lancado_em);
CREATE INDEX idx_sessoes_conciliacao       ON conta_bancaria.sessoes_conciliacao(empresa_id, conta_id);

-- cobranca
CREATE INDEX idx_conversas_empresa         ON cobranca.conversas(empresa_id);
CREATE INDEX idx_conversas_cliente         ON cobranca.conversas(empresa_id, cliente_id);
CREATE INDEX idx_conversas_telefone        ON cobranca.conversas(empresa_id, telefone);
CREATE INDEX idx_mensagens_empresa         ON cobranca.mensagens(empresa_id);
CREATE INDEX idx_mensagens_conversa        ON cobranca.mensagens(empresa_id, conversa_id);
CREATE INDEX idx_execucoes_agente_empresa  ON cobranca.execucoes_agente(empresa_id);
CREATE INDEX idx_scores_clientes_empresa   ON cobranca.scores_clientes(empresa_id, cliente_id);
CREATE INDEX idx_campanhas_empresa         ON cobranca.campanhas_disparo(empresa_id);

-- config
CREATE INDEX idx_config_sistema_empresa    ON config.configuracoes_sistema(empresa_id);
CREATE INDEX idx_politicas_empresa         ON config.politicas_eventos_modulo(empresa_id);
CREATE INDEX idx_credenciais_empresa       ON config.credenciais_integracao(empresa_id);

-- logs
CREATE INDEX idx_log_auditoria_empresa     ON logs.log_auditoria(empresa_id);
CREATE INDEX idx_log_auditoria_usuario     ON logs.log_auditoria(usuario_id);
CREATE INDEX idx_log_auditoria_entidade    ON logs.log_auditoria(entidade, entidade_id);
CREATE INDEX idx_log_auditoria_criado_em   ON logs.log_auditoria(criado_em DESC);
CREATE INDEX idx_log_eventos_empresa       ON logs.log_eventos(empresa_id);
CREATE INDEX idx_log_eventos_tipo          ON logs.log_eventos(tipo_evento);
CREATE INDEX idx_log_eventos_status        ON logs.log_eventos(status_processamento)
    WHERE status_processamento IN ('pendente','processando');

-- notificacoes
CREATE INDEX idx_webhooks_empresa          ON notificacoes.webhooks_brutos(empresa_id);
CREATE INDEX idx_webhooks_provedor         ON notificacoes.webhooks_brutos(provedor);
CREATE INDEX idx_webhooks_nao_processados  ON notificacoes.webhooks_brutos(recebido_em)
    WHERE processado = FALSE;

-- materialized views
CREATE INDEX idx_mv_resumo_receber         ON financeiro.mv_resumo_receber(empresa_id, contrato_id);
CREATE INDEX idx_mv_metricas_clientes      ON cadastro.mv_metricas_clientes(empresa_id, cliente_id);
CREATE INDEX idx_mv_metricas_veiculos      ON veiculos.mv_metricas_veiculos(empresa_id, veiculo_id);


-- =============================================================================
-- DADOS INICIAIS (seeds globais)
-- =============================================================================

INSERT INTO acesso.perfis (nome, descricao, is_admin) VALUES
    ('Admin',     'Acesso total ao sistema', true),
    ('Operador',  'Operações do dia a dia: contratos, títulos, cobrança', false);

INSERT INTO cadastro.categorias_despesa (empresa_id, nome, ordem) VALUES
    (NULL, 'Manutenção',     1),
    (NULL, 'Combustível',    2),
    (NULL, 'Impostos',       3),
    (NULL, 'Seguro',         4),
    (NULL, 'Salários',       5),
    (NULL, 'Aluguel',        6),
    (NULL, 'Utilidades',     7),
    (NULL, 'Outros',         8);


-- =============================================================================
-- NOTAS PARA A MIGRATION ALEMBIC (0015_schema_restructure.py)
-- =============================================================================
-- 1. Trigger append-only em logs.log_auditoria (bloqueia UPDATE/DELETE)
-- 2. Trigger enforce_paid_immutability em financeiro.titulos_receber
--    (bloqueia alteração de valor/data em títulos com status='pago')
-- 3. Row Level Security (RLS) habilitado em todas as tabelas com empresa_id
--    via policy: USING (empresa_id = current_setting('app.empresa_id')::uuid)
-- 4. Função set_atualizado_em() + triggers de updated_at em todas as tabelas
-- =============================================================================
