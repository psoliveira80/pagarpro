"""Renderizador de templates de mensagem (Story 13.10).

Usa Jinja2 em modo **sandbox** — sem acesso a filesystem, network, atributos
privados de objetos ou builtins perigosos (`exec`, `open`, `__import__`).

Resolução do template segue o fallback:

1. Procura por `(empresa_id == empresa_id_do_tenant, nome, canal)`.
2. Se não achar, cai pro padrão `(empresa_id IS NULL, nome, canal)`.
3. Se nada existe, levanta `TemplateNaoEncontradoError`.

Variáveis disponíveis no contexto seguem o glossário:
`cliente`, `titulo`, `veiculo`, `contrato`, `empresa` — cada um é um dict
plano (chaves: nome, valor, data_vencimento, etc.). O caller monta o dict.
"""

from __future__ import annotations

from uuid import UUID

from jinja2 import StrictUndefined, TemplateError
from jinja2.sandbox import SandboxedEnvironment
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.db.models.template_mensagem import TemplateMensagem


class TemplateNaoEncontradoError(Exception):
    """Levantado quando nenhum template (tenant nem padrão) casa com (nome, canal)."""


class TemplateRenderError(Exception):
    """Wrap de erro do Jinja2 durante render (variável ausente, sintaxe inválida)."""


# Ambiente Jinja2 sandbox global — thread-safe e reutilizável.
# - SandboxedEnvironment bloqueia: acesso a atributos privados, `__class__`,
#   chamadas de métodos perigosos, etc.
# - StrictUndefined faz o render falhar se uma variável referenciada não
#   estiver no contexto (preferível a renderizar string vazia silenciosamente).
_env = SandboxedEnvironment(
    undefined=StrictUndefined,
    autoescape=False,  # mensagens são texto plano, não HTML
)


class RenderizadorTemplate:
    def __init__(self, session: AsyncSession, empresa_id: UUID | None) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def renderizar(
        self,
        nome: str,
        contexto: dict,
        canal: str = "whatsapp",
    ) -> str:
        """Resolve template (tenant → global → 404) e renderiza com `contexto`.

        Levanta `TemplateNaoEncontradoError` se não houver template.
        Levanta `TemplateRenderError` se Jinja2 falhar (variável ausente,
        sintaxe inválida no template salvo no banco).
        """
        template = await self._resolver(nome, canal)
        if template is None:
            raise TemplateNaoEncontradoError(
                f"Template '{nome}' (canal={canal}) não encontrado "
                f"para empresa {self.empresa_id} nem como global."
            )
        try:
            jinja_tmpl = _env.from_string(template.conteudo)
            return jinja_tmpl.render(**contexto)
        except TemplateError as e:
            raise TemplateRenderError(
                f"Erro ao renderizar '{nome}': {e}"
            ) from e

    async def preview(self, conteudo: str, contexto: dict) -> str:
        """Renderiza um template ad-hoc sem persistir (usado pelo endpoint de preview)."""
        try:
            return _env.from_string(conteudo).render(**contexto)
        except TemplateError as e:
            raise TemplateRenderError(f"Erro ao renderizar preview: {e}") from e

    async def _resolver(self, nome: str, canal: str) -> TemplateMensagem | None:
        # 1) Override do tenant
        if self.empresa_id is not None:
            result = await self.session.execute(
                select(TemplateMensagem).where(
                    TemplateMensagem.empresa_id == self.empresa_id,
                    TemplateMensagem.nome == nome,
                    TemplateMensagem.canal == canal,
                    TemplateMensagem.ativo.is_(True),
                )
            )
            row = result.scalar_one_or_none()
            if row is not None:
                return row

        # 2) Fallback: template global (empresa_id IS NULL)
        result = await self.session.execute(
            select(TemplateMensagem).where(
                TemplateMensagem.empresa_id.is_(None),
                TemplateMensagem.nome == nome,
                TemplateMensagem.canal == canal,
                TemplateMensagem.ativo.is_(True),
            )
        )
        return result.scalar_one_or_none()


# Contexto de exemplo usado por preview na UI (5 templates padrão)
CONTEXTO_EXEMPLO = {
    "cliente": {
        "nome": "João da Silva",
        "primeiro_nome": "João",
        "telefone": "11999990000",
    },
    "titulo": {
        "valor": "R$ 1.250,00",
        "valor_atualizado": "R$ 1.287,50",
        "data_vencimento": "15/06/2026",
        "dias_atraso": 5,
        "numero_parcela": 3,
    },
    "veiculo": {
        "placa": "ABC1D23",
        "modelo": "Toyota Corolla",
    },
    "contrato": {
        "id": "C-001234",
        "data_inicio": "01/03/2026",
    },
    "empresa": {
        "nome": "FrotaUber Demo",
        "telefone": "1140044004",
    },
}
