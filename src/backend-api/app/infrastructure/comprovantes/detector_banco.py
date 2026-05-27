"""Detector de banco emissor (Story 13.19).

A camada universal extrai entidades sem saber o banco. Quando conseguimos
identificar o banco emissor, aplicamos **boost de confiança** (+10 a +15%)
no resultado, porque o cross-check com layout conhecido reduz risco de
extração errada.

Templates ficam em `templates_banco/*.yaml`. Cada template tem:
- `marcadores`: lista de substrings que, se aparecerem no texto, confirmam
  o banco (case-insensitive). Match de qualquer marcador identifica.
- `confianca_boost`: incremento de score quando banco é identificado e
  os campos extraídos batem com o esperado.

Os 8 templates iniciais (Itaú, Bradesco, BB, Caixa, Santander, Nubank,
Inter, C6) carregam só marcadores básicos. Templates ficam vazios de
regras específicas — completam-se conforme aparecem casos reais que
exijam refinamento.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path

import yaml


log = logging.getLogger(__name__)

DIR_TEMPLATES = Path(__file__).parent / "templates_banco"


@dataclass(frozen=True)
class TemplateBanco:
    slug: str  # 'itau', 'bradesco', 'bb', etc.
    nome_oficial: str  # 'Banco Itaú S.A.', etc.
    marcadores: list[str]
    confianca_boost: float


_CACHE: dict[str, TemplateBanco] | None = None


def _carregar_templates() -> dict[str, TemplateBanco]:
    """Carrega todos os templates YAML uma vez por processo."""
    global _CACHE
    if _CACHE is not None:
        return _CACHE

    templates: dict[str, TemplateBanco] = {}
    if not DIR_TEMPLATES.exists():
        log.warning(f"detector_banco.templates_dir_ausente: {DIR_TEMPLATES}")
        _CACHE = {}
        return _CACHE

    for arquivo in DIR_TEMPLATES.glob("*.yaml"):
        try:
            with open(arquivo, "r", encoding="utf-8") as f:
                conteudo = yaml.safe_load(f)
            tpl = TemplateBanco(
                slug=conteudo.get("slug") or arquivo.stem,
                nome_oficial=conteudo.get("nome_oficial", arquivo.stem.title()),
                marcadores=[str(m).lower() for m in conteudo.get("marcadores", [])],
                confianca_boost=float(conteudo.get("confianca_boost", 0.10)),
            )
            templates[tpl.slug] = tpl
        except Exception as exc:
            log.warning(f"detector_banco.erro_carregar_template arquivo={arquivo}: {exc}")

    _CACHE = templates
    return _CACHE


def detectar_banco(texto: str) -> TemplateBanco | None:
    """Detecta o banco emissor pelo texto.

    Args:
        texto: conteúdo textual do comprovante (vem do PDF ou OCR).

    Returns:
        O `TemplateBanco` com a primeira correspondência por marcador.
        `None` se nenhum banco reconhecido.
    """
    if not texto:
        return None

    texto_lower = texto.lower()
    templates = _carregar_templates()

    # Itera em ordem alfabética dos slugs para determinismo
    for slug in sorted(templates.keys()):
        tpl = templates[slug]
        for marcador in tpl.marcadores:
            if marcador in texto_lower:
                return tpl

    return None


def reset_cache_para_testes() -> None:
    """Limpa cache (usado pelos testes para recarregar templates dinamicamente)."""
    global _CACHE
    _CACHE = None
