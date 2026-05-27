---
epic: 13
story: 11
title: "Ledger de Passivo Inoperante"
type: "Domínio Financeiro"
status: ready-for-dev
priority: high
depends_on: "13.2, 13.8"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.11: Ledger de Passivo Inoperante

## História de Usuário

**Como** gestor financeiro,
**eu quero** que títulos em atraso de contratos encerrados sejam registrados como passivo inoperante,
**para que** a dívida real seja rastreável e possa ser cobrada ou baixada formalmente.

## Contexto

Quando contrato é encerrado **com pendência** (Story 13.2), os títulos em atraso não desaparecem — viram **passivo inoperante**. Esta story cria o ledger imutável onde esses passivos vivem até serem baixados ou recuperados.

## Critérios de Aceite

1. Tabela `passivos_inoperantes` criada:

```sql
CREATE TABLE passivos_inoperantes (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID NOT NULL REFERENCES comercial.empresas(id),
    cliente_id      UUID NOT NULL REFERENCES cadastro.clientes(id),
    contrato_id     UUID NOT NULL REFERENCES contrato.contratos(id),
    titulo_id       UUID NOT NULL REFERENCES financeiro.titulos_receber(id),
    valor_nominal   NUMERIC(12,2) NOT NULL,
    valor_encargos  NUMERIC(12,2) NOT NULL DEFAULT 0,
    situacao        VARCHAR(30) NOT NULL DEFAULT 'pendente',
    origem          VARCHAR(50) NOT NULL,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    baixado_em      TIMESTAMPTZ,
    motivo_baixa    TEXT,
    criado_por      UUID REFERENCES acesso.usuarios(id),
    CONSTRAINT ck_passivo_situacao CHECK (situacao IN ('pendente','baixado','recuperado'))
);
```

2. Hook `quando_contrato_encerrado` (quando `situacao='encerrado_com_pendencia'`): itera títulos com `status='em_atraso'` do contrato → cria registro em `passivos_inoperantes` para cada um.
3. Endpoints: `GET /api/v1/passivo-inoperante` (filtros por `empresa_id`, `cliente_id`, `situacao`), `PATCH /{id}/baixar`, `PATCH /{id}/recuperado`.
4. Frontend: aba `Passivos` no detalhe do cliente com badge numérico. Card exibe valor, data origem e botões de ação com `ConfirmService` antes de confirmar.
5. KPI no dashboard: "Passivo Inoperante Total — R$ X / N clientes".
6. Audit log para toda mutação com `categoria='financeiro'`.

## Contexto Técnico

### Imutabilidade

Tabela é append-only para o histórico, mas permite UPDATE de `situacao`, `baixado_em` e `motivo_baixa`. Trigger de auditoria registra cada mudança.

### Origem

Campo `origem` registra de onde veio o passivo. Valores iniciais: `contrato_encerrado` (default), `ajuste_manual`, `rescisao`.

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0027_passivos_inoperantes.py
├── app/infrastructure/db/models/
│   └── passivo_inoperante.py                            # CRIAR
├── app/application/hooks/
│   └── quando_contrato_encerrado.py                     # MODIFICAR — gerar passivos
├── app/api/v1/
│   └── passivo_routes.py                                # CRIAR
└── app/tests/test_passivo_inoperante.py                 # CRIAR

src/frontend/src/app/features/clientes/cliente-detalhe/
└── cliente-detalhe.component.html                       # MODIFICAR — aba Passivos
```

## Checklist do Dev

- [ ] 13.2, 13.8 concluídas.
- [ ] Migration aplicada.
- [ ] Encerramento `encerrado_com_pendencia` gera passivos para todos os títulos em atraso.
- [ ] Endpoints `baixar` e `recuperado` funcionais com audit log.
- [ ] Aba Passivos no frontend lista por cliente.
- [ ] KPI dashboard atualizada.

## Notas

- Passivo inoperante NÃO é igual a "dívida ativa". É registro contábil para acompanhamento.
- Recuperação (`recuperado`) é quando cliente paga depois — registra valor recuperado.
