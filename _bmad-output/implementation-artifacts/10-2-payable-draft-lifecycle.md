---
epic: 10
story: 2
title: "Ciclo de Vida do Título a Pagar (Rascunho → Pendente → Pago/Cancelado)"
type: "Core"
status: ready-for-dev
---

# Story 10.2: Ciclo de Vida do Título a Pagar

## História de Usuário
Como Gestor,
quero que títulos a pagar recorrentes sejam gerados como rascunhos que eu possa preencher e salvar,
para que o sistema me lembre das despesas fixas sem exigir valores exatos antecipadamente.

## Critérios de Aceite

1. Ciclo de vida de status de título a pagar é obrigatório: `rascunho` → `pendente` → `pago` | `cancelado`.
2. `rascunho`: pode editar todos os campos, pode DELETAR (hard delete).
3. `pendente`: pode editar, pode pagar, pode cancelar (soft — seta `status=cancelado`, nunca hard delete).
4. `pago` e `cancelado`: imutáveis.
5. Template de recorrência gera títulos a pagar com `status=rascunho` (atualizar task existente).
6. Notificação SSE ao gestor: "Título de {description} gerado como rascunho — preencha o valor".
7. Frontend: distinção visual para rascunho (borda tracejada, ícone de lápis), botão "Preencher".
8. Testes: verifica transições do ciclo de vida, verifica que hard delete é permitido apenas para rascunho.

## Contexto Técnico

### Referências de Arquitetura
- `docs/architecture-recurrence-and-collection.md` Seção 2

### Arquivos a Criar/Modificar
```
backend-api/
├── app/api/v1/payable_routes.py            # Aplica regras do ciclo de vida
├── app/workers/tasks/generate_recurring_payables.py  # Status=rascunho + notificação SSE
frontend/
├── src/app/features/finance/payables-list.component.html  # Distinção visual
```

### Contexto da Sessão
- Tabela de títulos a pagar já tem coluna `status`
- Infraestrutura SSE existe (app/api/sse.py)

## Checklist do Dev
- [ ] Todos os critérios de aceite atendidos
- [ ] Testes escritos e passando
- [ ] Sem regressões
