"""Seed script: creates default roles, admin user, and default system configs.

Usage: python -m app.cli.seed
"""

import asyncio
import os
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.session import get_sessionmaker
from app.infrastructure.db.models.config import ConfiguracaoSistema
from app.infrastructure.db.models.template_mensagem import TemplateMensagem
from app.infrastructure.db.models.user import User, Role, UserRole
from app.infrastructure.security.password_hasher import hash_password


ROLES = ["Admin", "Operador", "Validador", "Auditor"]

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")
ADMIN_PASSWORD = os.environ.get("ADMIN_INITIAL_PASSWORD", "Admin@123")
ADMIN_FULL_NAME = "Administrador"


# Configurações padrão do sistema (Story 13.4). empresa_id = NULL → global.
# (slug, modulo, tipo_valor, valor, descricao)
CONFIGURACOES_PADRAO: list[tuple[str, str, str, str, str]] = [
    # ── financeiro ──
    ("dias_antecedencia_lembrete", "financeiro", "inteiro", "3",
     "Dias antes do vencimento para enviar lembrete"),
    ("dias_carencia", "financeiro", "inteiro", "0",
     "Dias de tolerância após vencimento antes de considerar atrasado"),
    ("percentual_multa", "financeiro", "decimal", "2.00",
     "Percentual de multa aplicado em títulos vencidos (% sobre o valor)"),
    ("percentual_juros_dia", "financeiro", "decimal", "0.0333",
     "Percentual de juros ao dia (default ≈ 1% ao mês)"),
    ("limite_tentativas_cobranca", "financeiro", "inteiro", "3",
     "Máximo de mensagens automáticas de cobrança por título"),
    ("intervalo_tentativas_horas", "financeiro", "inteiro", "24",
     "Horas entre tentativas consecutivas de cobrança"),
    ("limite_dias_suspensao", "financeiro", "inteiro", "15",
     "Dias de atraso para suspender contrato automaticamente"),
    ("limite_dias_encerramento", "financeiro", "inteiro", "60",
     "Dias de atraso para encerrar contrato com pendência"),
    ("permite_pagamento_parcial", "financeiro", "booleano", "false",
     "Aceita pagamentos parciais que abatem parcialmente o título"),
    ("limite_fusao_parcial_pct", "financeiro", "decimal", "20.00",
     "Pagamento abaixo deste percentual do valor da parcela funde com a próxima"),
    # ── frota (desbloqueio em confiança) ──
    ("desbloqueio_confianca_dias", "frota", "inteiro", "3",
     "Validade em dias do desbloqueio em confiança"),
    ("desbloqueio_confianca_min_meses_historico", "frota", "inteiro", "3",
     "Mínimo de meses de relacionamento para elegibilidade"),
    ("desbloqueio_confianca_max_atrasos_historico", "frota", "inteiro", "1",
     "Máximo de ocorrências de atraso no histórico para elegibilidade"),
    # ── comunicacao ──
    ("canal_cobranca_principal", "comunicacao", "string", "whatsapp",
     "Canal padrão de cobrança (whatsapp, email, sms)"),
    ("canal_cobranca_fallback", "comunicacao", "string", "",
     "Canal de fallback se o principal falhar (vazio = sem fallback)"),
    # ── comprovantes (Story 13.19) ──
    ("modo_analise", "comprovantes", "string", "nativo",
     "Modo de análise de comprovantes: nativo | ia_como_reforco | ia_primario"),
    ("provedor_ia", "comprovantes", "string", "",
     "Provedor de IA Vision quando modo!=nativo: openai-vision | claude-vision | gemini"),
    ("threshold_acionar_ia", "comprovantes", "decimal", "0.70",
     "Quando modo=ia_como_reforco, IA é chamada se score nativo < este valor"),
    ("threshold_notificacao_baixa_confianca", "comprovantes", "decimal", "0.70",
     "Comprovantes com score abaixo deste valor geram notificação operacional"),
    ("threshold_alerta_critico", "comprovantes", "decimal", "0.40",
     "Comprovantes com score abaixo deste valor viram alerta crítico (revisão urgente)"),
    # ── menu adaptativo do WhatsApp (Story 13.22) ──
    ("score_minimo_adiar_vencimento", "cobranca", "decimal", "80",
     "Score (0-100) mínimo para cliente ver botão 'Adiar próximo vencimento'"),
    ("score_minimo_desbloqueio_confianca", "cobranca", "decimal", "65",
     "Score mínimo para ver 'Desbloqueio em confiança'"),
    ("score_minimo_pagamento_parcial", "cobranca", "decimal", "50",
     "Score mínimo para ver 'Pagar parcial'"),
    ("dias_maximos_adiamento", "cobranca", "inteiro", "5",
     "Quantos dias o cliente pode adiar o vencimento via menu"),
    ("valor_minimo_pagamento_parcial_pct", "cobranca", "decimal", "40.0",
     "% mínimo do valor da parcela que cliente pode pagar como parcial"),
    ("limite_usos_periodo_adiar", "cobranca", "inteiro", "1",
     "Quantas vezes por período o cliente pode adiar"),
    ("limite_usos_periodo_desbloqueio_confianca", "cobranca", "inteiro", "1",
     "Quantas vezes por período o cliente pode pedir desbloqueio em confiança"),
    ("periodo_limite_acoes_cliente", "cobranca", "string", "mensal",
     "Período do contador (semanal/quinzenal/mensal/5d/Nd)"),
    # ── comprovante via WhatsApp (Story 13.23) ──
    ("timeout_aguardar_comprovante_min", "comunicacao", "inteiro", "5",
     "Minutos que o sistema aguarda comprovante após cliente clicar 'Enviar comprovante'"),
    ("desbloqueio_automatico_apos_validacao", "comprovantes", "booleano", "true",
     "Quando true, valida comprovante e desbloqueia veículo automaticamente"),
    ("score_minimo_auto_homologar", "comprovantes", "decimal", "0.80",
     "Score (0-1) mínimo para auto-homologar comprovante (sem revisão humana). "
     "Cliente em blacklist sempre vai pra fila manual independente do score."),
    # ── confirmação de recebimento (Story 13.25) ──
    ("dias_adiar_apos_confirmacao", "comunicacao", "inteiro", "2",
     "Quando cliente clica 'Confirmo recebimento' no lembrete, sistema pula "
     "os próximos envios desse título por N dias"),
    # ── IA atendente (Story 13.26 — adiada V2; flag já registrada) ──
    ("ia_atendente_ativa", "comunicacao", "booleano", "false",
     "Toggle global de IA atendente (false = menu rígido apenas)"),
    # ── WhatsApp multi-número (Story 13.21 + ajuste 2026-05-29) ──
    ("max_clientes_por_numero_whatsapp", "whatsapp", "inteiro", "150",
     "Capacidade máxima de clientes atribuídos por número WhatsApp. "
     "Quando todos os números ativos atingem o teto, novos clientes ficam sem "
     "atribuição e o gestor é notificado pra ativar mais um número. "
     "Cliente já atribuído NUNCA migra por capacidade — só por banimento."),
]


# Templates padrão de mensagem (Story 13.10). empresa_id = NULL → global.
# (nome, canal, conteudo, descricao)
TEMPLATES_PADRAO: list[tuple[str, str, str, str]] = [
    (
        "lembrete_vencimento", "whatsapp",
        "Olá {{cliente.primeiro_nome}}! Sua parcela de {{titulo.valor}} "
        "vence em {{titulo.data_vencimento}}. Veículo: {{veiculo.placa}}.",
        "Lembrete enviado N dias antes do vencimento",
    ),
    (
        "cobranca_vencida", "whatsapp",
        "Olá {{cliente.primeiro_nome}}, sua parcela do contrato {{contrato.id}} "
        "está vencida há {{titulo.dias_atraso}} dia(s). Valor original: {{titulo.valor}} "
        "— valor atualizado com multa e juros: {{titulo.valor_atualizado}}.",
        "Mensagem de cobrança após vencimento",
    ),
    (
        "aviso_suspensao", "whatsapp",
        "{{cliente.primeiro_nome}}, seu contrato {{contrato.id}} foi suspenso "
        "por inadimplência. Veículo {{veiculo.placa}} indisponível até regularização. "
        "Entre em contato: {{empresa.telefone}}.",
        "Notificação de suspensão de contrato",
    ),
    (
        "pagamento_confirmado", "whatsapp",
        "{{cliente.primeiro_nome}}, recebemos seu pagamento de {{titulo.valor}}. "
        "Obrigado! — {{empresa.nome}}",
        "Confirmação de pagamento recebido",
    ),
    (
        "opcao_compra_exercida", "whatsapp",
        "Parabéns {{cliente.primeiro_nome}}! Sua opção de compra do veículo "
        "{{veiculo.placa}} ({{veiculo.modelo}}) foi confirmada. Em breve nossa "
        "equipe entrará em contato para a transferência.",
        "Confirmação do exercício da opção de compra (parcela final)",
    ),
    # ── Stories 13.22 / 13.23 / 13.25 — fluxo de comprovante via WhatsApp ──
    (
        "iniciar_captura_comprovante", "whatsapp",
        "📎 Pode mandar a foto/PDF do comprovante agora.\n"
        "Vou processar automaticamente quando chegar! 🙂\n\n"
        "(Aguardo até {{timeout_min}} minutos.)",
        "Resposta quando cliente clica 'Enviar comprovante' no menu rígido",
    ),
    (
        "comprovante_recebido_inicial", "whatsapp",
        "📎 Recebi seu comprovante! Vou analisar e te aviso em instantes. 🙂",
        "Ack imediato quando mídia chega no estado AGUARDANDO_COMPROVANTE",
    ),
    (
        "comprovante_ja_enviado", "whatsapp",
        "📎 Esse comprovante já tinha sido enviado antes — verificamos o histórico.",
        "Cliente reenviou o mesmo arquivo (hash SHA-256 idêntico)",
    ),
    (
        "comprovante_validado_automatico", "whatsapp",
        "✓ Pagamento confirmado! "
        "{% if contrato_reativado %}Veículo liberado. Boa rodagem 🚗💨"
        "{% else %}Valeu 🙏{% endif %}",
        "Auto-homologação OK (integral/excedente). Reativa contrato se estava suspenso.",
    ),
    (
        "comprovante_validado_parcial", "whatsapp",
        "✓ Pagamento parcial recebido! O restante foi adicionado à próxima "
        "parcela. Veículo continua na situação anterior.",
        "Pagamento parcial detectado (fundido/separado pelo ServicoTituloPago)",
    ),
    (
        "comprovante_aguardando_validacao_manual", "whatsapp",
        "📎 Recebi seu comprovante! Está em análise.\n"
        "Vou te avisar assim que confirmar. 🙂\n\n(motivo: {{motivo}})",
        "Comprovante caiu em homologação manual (score baixo, sem match, etc.)",
    ),
    (
        "comprovante_rejeitado_blacklist", "whatsapp",
        "📎 Recebi seu comprovante! Está em análise pela nossa equipe. "
        "Em breve daremos retorno. 🙂",
        "Cliente em blacklist — fluxo idêntico ao manual sem revelar a flag",
    ),
    (
        "comprovante_erro_homologacao", "whatsapp",
        "📎 Recebi seu comprovante. Houve um problema no processamento "
        "automático — um humano vai revisar e te confirmar em breve.",
        "registrar_pagamento levantou exceção após análise OK",
    ),
    (
        "agradecimento_confirmacao_recebimento", "whatsapp",
        "Obrigado! Avisaremos novamente próximo do vencimento. 🙂",
        "Cliente clicou 'Confirmo recebimento' no lembrete (Story 13.25)",
    ),
]


async def _get_empresa_id(session: AsyncSession) -> UUID:
    """Fetch the first empresa_id from comercial.empresas."""
    row = (await session.execute(text("SELECT id FROM comercial.empresas LIMIT 1"))).first()
    if row is None:
        raise RuntimeError("No empresa found in comercial.empresas — run migrations first.")
    return row[0]


async def seed() -> None:
    session_factory = get_sessionmaker()
    async with session_factory() as session:
        async with session.begin():
            # Migrations rodam com row_security = off; ao seedar fora de migration,
            # forçamos o mesmo aqui para inserir configs globais (empresa_id NULL).
            await session.execute(text("SET LOCAL row_security = off"))
            empresa_id = await _get_empresa_id(session)
            await _seed_roles(session, empresa_id)
            await _seed_admin(session, empresa_id)
            await _seed_configuracoes(session)
            await _seed_templates_mensagem(session)
    print("Seed completed successfully.")


async def _seed_roles(session: AsyncSession, empresa_id: UUID) -> None:
    for role_name in ROLES:
        existing = await session.execute(
            select(Role).where(Role.nome == role_name)
        )
        if existing.scalar_one_or_none() is None:
            session.add(Role(nome=role_name, descricao=f"Role: {role_name}"))
            print(f"  Created role: {role_name}")
        else:
            print(f"  Role exists: {role_name}")


async def _seed_configuracoes(session: AsyncSession) -> None:
    """Seed das 15 configurações default (escopo global, empresa_id NULL).

    Idempotente — só insere o que ainda não existe. Ignora overrides por
    tenant que possam ter sido criados manualmente.
    """
    for slug, modulo, tipo_valor, valor, descricao in CONFIGURACOES_PADRAO:
        existing = await session.execute(
            select(ConfiguracaoSistema).where(
                ConfiguracaoSistema.empresa_id.is_(None),
                ConfiguracaoSistema.slug == slug,
            )
        )
        if existing.scalar_one_or_none() is not None:
            print(f"  Config exists: {slug}")
            continue
        session.add(
            ConfiguracaoSistema(
                empresa_id=None,
                modulo=modulo,
                slug=slug,
                tipo_valor=tipo_valor,
                valor=valor,
                descricao=descricao,
            )
        )
        print(f"  Created config: {slug} = {valor} ({tipo_valor}, {modulo})")


async def _seed_templates_mensagem(session: AsyncSession) -> None:
    """Seed dos 5 templates padrão globais (Story 13.10). Idempotente."""
    for nome, canal, conteudo, descricao in TEMPLATES_PADRAO:
        existing = await session.execute(
            select(TemplateMensagem).where(
                TemplateMensagem.empresa_id.is_(None),
                TemplateMensagem.nome == nome,
                TemplateMensagem.canal == canal,
            )
        )
        if existing.scalar_one_or_none() is not None:
            print(f"  Template exists: {nome} ({canal})")
            continue
        session.add(
            TemplateMensagem(
                empresa_id=None,
                nome=nome,
                canal=canal,
                conteudo=conteudo,
                descricao=descricao,
                ativo=True,
            )
        )
        print(f"  Created template: {nome} ({canal})")


async def _seed_admin(session: AsyncSession, empresa_id: UUID) -> None:
    existing = await session.execute(
        select(User).where(User.email == ADMIN_EMAIL)
    )
    if existing.scalar_one_or_none() is not None:
        print(f"  Admin user exists: {ADMIN_EMAIL}")
        return

    user = User(
        empresa_id=empresa_id,
        email=ADMIN_EMAIL,
        senha_hash=hash_password(ADMIN_PASSWORD),
        nome_completo=ADMIN_FULL_NAME,
        ativo=True,
    )
    session.add(user)
    await session.flush()

    admin_role = await session.execute(
        select(Role).where(Role.nome == "Admin")
    )
    role = admin_role.scalar_one()
    session.add(UserRole(usuario_id=user.id, perfil_id=role.id, empresa_id=empresa_id))
    print(f"  Created admin user: {ADMIN_EMAIL} (linked to Admin role)")


def main() -> None:
    asyncio.run(seed())


if __name__ == "__main__":
    main()
