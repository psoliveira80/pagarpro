# Deferred Work

## Deferred from: code review of 10-1-monthly-installment-generation-with-correction (2026-05-20)

- **W1**: Notificação SSE ao gestor quando BCB completamente indisponível (`bcb_correction_adapter.py`) — dev notes explicitamente adiam para Epic 10.3 ou story de alertas dedicada; receptor da notificação ainda não está definido no contexto da task.
- **W2**: `_advance_one_month` re-ancora silenciosamente em `generation_day` após `next_generation_date` irregular (`generate_monthly_installments.py`) — edge case de override administrativo manual; não ocorre em fluxo normal de criação de contrato.
- **W3**: Fallback de cache para mês anterior quando cache do mês atual está vazio (`bcb_correction_adapter.py`) — extensão razoável do spec ("usar último valor em cache"); é uma decisão de negócio se mês anterior é aceitável como substituto.
