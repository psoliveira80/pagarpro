---
epic: 13
story: 13
title: "Desbloqueio em Confiança com Expiração Automática"
type: "Worker + Domínio Frota"
status: ready-for-dev
priority: high
depends_on: "13.4, 13.5, 13.2"
authored_by: "Amelia (dev) via bmad-create-story"
created_at: "2026-05-27"
---

# Story 13.13: Desbloqueio em Confiança com Expiração

## História de Usuário

**Como** operador financeiro,
**eu quero** configurar regras de desbloqueio em confiança com prazo de validade,
**para que** clientes elegíveis sejam reativados ao pagar sem aprovação manual — e re-bloqueados automaticamente se não cumprirem o prazo prometido.

## Contexto

Cliente com bom histórico que promete pagar "amanhã" — gestor pode dar **desbloqueio temporário** sem precisar esperar pagamento real. Esta story automatiza: regras de elegibilidade + janela de validade + re-bloqueio automático se prazo passar.

## Critérios de Aceite

1. Parâmetros via `ServicoConfiguracao` (módulo `frota`):
   - `desbloqueio_confianca_dias` (inteiro, default 3) — validade do desbloqueio em dias
   - `desbloqueio_confianca_min_meses_historico` (inteiro, default 3) — mínimo de meses de relacionamento
   - `desbloqueio_confianca_max_atrasos_historico` (inteiro, default 1) — máx. ocorrências de atraso no histórico

2. Tabela `veiculos` recebe colunas:
   - `desbloqueio_confianca_ativo_ate TIMESTAMPTZ NULL` — data/hora em que o desbloqueio expira
   - `desbloqueio_confianca_concedido_em TIMESTAMPTZ NULL`
   - `desbloqueio_confianca_concedido_por UUID NULL REFERENCES acesso.usuarios(id)`

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

## Contexto Técnico

### Avaliação de elegibilidade

```python
def verificar_elegibilidade(contrato_id: UUID) -> bool:
    contrato = repo.obter(contrato_id)
    min_meses = config.obter_inteiro('desbloqueio_confianca_min_meses_historico', 'frota', 3)
    max_atrasos = config.obter_inteiro('desbloqueio_confianca_max_atrasos_historico', 'frota', 1)
    if relacao_meses(contrato.cliente_id) < min_meses:
        return False
    if contar_atrasos_historico(contrato.cliente_id) > max_atrasos:
        return False
    return True
```

### Hook ao pagar dentro do prazo

Quando `quando_titulo_pago` (13.9) executa em contrato com desbloqueio ativo, o estado vai pra `ativo` normal e os campos de desbloqueio são limpos (já não são mais necessários).

## Arquivos a Criar/Modificar

```
src/backend-api/
├── alembic/versions/0028_desbloqueio_confianca.py
├── app/application/services/
│   └── servico_desbloqueio_confianca.py                 # CRIAR
├── app/workers/tasks/
│   └── verificar_desbloqueios_expirados.py              # CRIAR
├── app/api/v1/
│   └── contratos_routes.py                              # MODIFICAR — endpoint desbloqueio
├── app/infrastructure/db/models/veiculos.py             # MODIFICAR — 3 colunas
└── app/tests/test_desbloqueio_confianca.py              # CRIAR

src/frontend/src/app/features/veiculos/veiculo-detalhe/
└── veiculo-detalhe.component.html                       # MODIFICAR — badge countdown (criar componente se não existe)
```

## Checklist do Dev

- [ ] 13.4, 13.5, 13.2 concluídas.
- [ ] Migration aplicada.
- [ ] Elegibilidade avaliada corretamente contra histórico.
- [ ] Concessão desbloqueia GPS + persiste prazo.
- [ ] Task de expiração roda a cada 30 min e re-bloqueia veículos com prazo vencido.
- [ ] Pagamento dentro do prazo converte em reativação normal.
- [ ] Badge no frontend com countdown ao vivo.

## Notas

- Esta story habilita Story 13.9 (conciliação pode reativar contrato suspenso usando essa lógica).
- Audit log obrigatório — cada desbloqueio é decisão de risco.
