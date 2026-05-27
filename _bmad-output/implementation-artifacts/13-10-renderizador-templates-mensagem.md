---
epic: 13
story: 10
title: "Renderizador de Templates de Mensagem"
type: "Infraestrutura + Comunicação"
status: review
priority: medium
depends_on: "13.4"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.10: Renderizador de Templates de Mensagem

## História de Usuário

**Como** motor financeiro,
**eu quero** um renderizador de templates centralizado,
**para que** todos os workers enviem mensagens consistentes com variáveis preenchidas.

## Contexto

Hoje cada worker monta string manualmente. Esta story centraliza: tabela de templates personalizáveis por empresa + função `renderizador_template.renderizar(nome, contexto)`.

## Critérios de Aceite

1. `renderizador_template.py` em `infrastructure/mensageria/` com função `renderizar(nome_template, contexto: dict) -> str`.
2. Tabela `templates_mensagem(empresa_id, nome, canal, conteudo, ativo)` — personalizáveis por empresa, fallback para templates padrão do sistema.
3. Templates padrão PT-BR seedados: `lembrete_vencimento`, `cobranca_vencida`, `aviso_suspensao`, `pagamento_confirmado`, `opcao_compra_exercida`.
4. Variáveis disponíveis: `{{cliente.nome}}`, `{{titulo.valor}}`, `{{titulo.valor_atualizado}}`, `{{titulo.data_vencimento}}`, `{{titulo.dias_atraso}}`, `{{veiculo.placa}}`, `{{contrato.id}}`, `{{empresa.nome}}`.
5. Endpoint CRUD `GET/POST/PUT /api/v1/templates-mensagem` (role `admin`) com preview com dados de exemplo.

## Contexto Técnico

### Engine de template

Usar **Jinja2** (já é dependência do projeto). Sandbox restrito — sem acesso a filesystem.

### Resolução de template

```python
def renderizar(nome: str, contexto: dict, empresa_id: UUID) -> str:
    template = repo.por_empresa_ou_padrao(empresa_id, nome)
    return jinja_env.from_string(template.conteudo).render(**contexto)
```

### Fallback

Se empresa não tem template customizado, usa o padrão do sistema (`empresa_id IS NULL`).

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0026_templates_mensagem.py
├── app/infrastructure/mensageria/
│   └── renderizador_template.py                         # CRIAR
├── app/infrastructure/db/models/
│   └── template_mensagem.py                             # CRIAR
├── app/api/v1/
│   └── templates_mensagem_routes.py                     # CRIAR
├── app/cli/seed.py                                      # MODIFICAR — seed templates padrão
└── app/tests/test_renderizador_templates.py             # CRIAR
```

## Checklist do Dev

- [ ] 13.4 (`sistema-configuracoes-tipadas`) `done`.
- [ ] Migration aplicada com seed dos 5 templates padrão.
- [ ] Função `renderizar()` substitui variáveis corretamente.
- [ ] Empresa pode customizar template; fallback funciona.
- [ ] Endpoint admin permite CRUD + preview.
- [ ] Sandbox Jinja2 não permite acesso a filesystem/network.

## Notas

- Pré-requisito para 13.7, 13.8 — eles consomem esse renderizador.
- Atenção a injeção: contexto deve passar por escape automático do Jinja2.

---

## Dev Agent Record

### Implementação (2026-05-27 — Amelia)

**Decisões arquiteturais:**

1. **Migration 0022 cria `comunicacao.templates_mensagem`** com CHECK constraint `ck_canal_aceito` (whatsapp/email/sms/telegram), `empresa_id NULLABLE` (NULL = padrão global), unique `(empresa_id, nome, canal)`, RLS permissiva. Schema `comunicacao` é novo — criado com `CREATE SCHEMA IF NOT EXISTS`.

2. **SandboxedEnvironment do Jinja2** em vez do `Environment` padrão. Bloqueia: acesso a `__class__`, `__bases__`, `__mro__` (mitiga template-escape clássico do Python sandbox), builtins perigosos (`open`, `__import__`, `exec`), atributos privados de objetos. Validado por dois testes (`test_sandbox_bloqueia_acesso_a_atributos_privados` e `test_sandbox_bloqueia_acesso_a_builtins`).

3. **StrictUndefined** força o render a falhar com `UndefinedError` se uma variável referenciada não estiver no contexto. Alternativa (`ChainableUndefined`) renderiza vazia silenciosamente, mascarando bugs no caller. Testado em `test_levanta_quando_variavel_ausente_no_contexto`.

4. **`autoescape=False`** pois mensagens WhatsApp/SMS são texto plano, não HTML. Se um canal futuro precisar de escape HTML, adicionar `autoescape=select_autoescape(['html'])` por canal.

5. **`_env` global** (módulo-level) — `SandboxedEnvironment` é thread-safe e cara de instanciar; reutilizar é a prática recomendada.

6. **Endpoint `POST /preview`** aceita `contexto` opcional — se omitido, usa `CONTEXTO_EXEMPLO` exportado do módulo. Útil para a tela admin testar sintaxe antes de salvar (Story 13.15).

7. **Fallback de resolução**: tenant procura `(empresa_id próprio, nome, canal, ativo=true)` primeiro; se não acha, cai para `(NULL, nome, canal, ativo=true)`. Validado em `test_override_tenant_prevalece_sobre_global`.

**Validação:**
- Migration 0022 aplicada. Schema `comunicacao` criado.
- Seed populou 5 templates globais (`lembrete_vencimento`, `cobranca_vencida`, `aviso_suspensao`, `pagamento_confirmado`, `opcao_compra_exercida`).
- `docker exec frotauber-api pytest`: **205 passed, 6 skipped, 4 warnings em 85.18s** (de 194 → +11 novos testes, zero regressão).
- Cobertura: render básico, fallback global, override tenant, sandbox bloqueando escapes (2 testes), preview ad-hoc, CRUD (POST/GET/preview).

### File List

- `src/backend-api/alembic/versions/0022_templates_mensagem.py` (novo)
- `src/backend-api/app/infrastructure/db/models/template_mensagem.py` (novo)
- `src/backend-api/app/infrastructure/mensageria/__init__.py` (novo — pacote)
- `src/backend-api/app/infrastructure/mensageria/renderizador_template.py` (novo)
- `src/backend-api/app/api/v1/templates_mensagem_routes.py` (novo)
- `src/backend-api/app/main.py` (modificado — registra router)
- `src/backend-api/app/cli/seed.py` (modificado — seed dos 5 templates padrão)
- `src/backend-api/app/tests/test_renderizador_templates.py` (novo — 11 testes)

### Change Log

| Data | Versão | Mudança |
|---|---|---|
| 2026-05-27 | 1.0 | Story implementada por Amelia. Migration 0022 cria tabela `comunicacao.templates_mensagem`. Renderizador com Jinja2 SandboxedEnvironment + StrictUndefined. Endpoints GET/POST/PUT/preview role admin. Seed dos 5 templates padrão. 205 testes verdes (11 novos). Status → `review`. |

### Completion Notes

- ✅ AC 1 — `renderizar()` em `app/infrastructure/mensageria/renderizador_template.py`.
- ✅ AC 2 — Tabela criada via migration 0022, fallback funcional validado.
- ✅ AC 3 — 5 templates padrão seedados em PT-BR (whatsapp).
- ✅ AC 4 — Todas as variáveis suportadas via dict de contexto (cliente, titulo, veiculo, contrato, empresa).
- ✅ AC 5 — CRUD `GET/POST/PUT` + `POST /preview` em `/api/v1/templates-mensagem`, role admin.
- ✅ Sandbox Jinja2 bloqueia escape de atributos privados e builtins — 2 testes específicos.
