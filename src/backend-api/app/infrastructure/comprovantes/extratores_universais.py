"""Extratores universais por regex (Story 13.19).

Funciona em qualquer texto bruto (vindo de PDF nativo ou OCR), em qualquer
banco — porque o PIX é padronizado pelo BACEN: todo comprovante PIX tem
E2E ID (`E[A-Z0-9]{31}`), valor em formato BR (`R$ X.XXX,XX`), datas
brasileiras (`dd/mm/aaaa`), CPF/CNPJ com máscara padrão.

Não substitui parsing específico por banco (`detector_banco.py`) — é a
camada base que sempre funciona, mesmo em bancos desconhecidos.
"""

from __future__ import annotations

import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from app.domain.finance.comprovante import EntidadesExtraidas


# ─── Regex (compiladas uma vez por módulo) ─────────────────────────────

# Valor monetário BR: "R$ 1.234,56" ou "R$ 1234,56" ou "1.234,56" sozinho
# Aceitamos formatos com e sem "R$" prefixo. Decimal sempre com vírgula.
RE_VALOR_BR = re.compile(
    r"(?:R\$\s*)?(\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)

# Data BR: "01/06/2026" ou "01-06-2026" (com ou sem hora opcional após)
RE_DATA_BR = re.compile(
    r"\b(\d{2})[/-](\d{2})[/-](\d{4})(?:\s+(?:às|as|-)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?\b",
    re.IGNORECASE,
)

# CPF: "000.000.000-00"
RE_CPF = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")

# CNPJ: "00.000.000/0000-00"
RE_CNPJ = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")

# E2E ID padronizado pelo BACEN: "E" + 31 caracteres alfanuméricos (ISPB+timestamp+sequencial)
RE_E2E_ID = re.compile(r"\b(E[0-9A-Za-z]{31})\b")

# Chave PIX celular (com +55 BR opcional)
RE_CHAVE_CELULAR = re.compile(r"\+?55\s?\(?\d{2}\)?\s?9?\d{4}-?\d{4}")

# Chave PIX e-mail (simplificado — RFC completa seria overkill)
RE_CHAVE_EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

# Chave PIX aleatória (UUID-like)
RE_CHAVE_UUID = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)

# TxID PIX (35 chars alfanuméricos opcional)
RE_TXID = re.compile(r"\b[A-Za-z0-9]{15,35}\b")


def _validar_cpf(cpf: str) -> bool:
    """Valida dígitos verificadores do CPF."""
    digitos = re.sub(r"\D", "", cpf)
    if len(digitos) != 11 or len(set(digitos)) == 1:
        return False

    for i in [9, 10]:
        soma = sum(int(digitos[j]) * (i + 1 - j) for j in range(i))
        dv = (soma * 10) % 11
        if dv == 10:
            dv = 0
        if dv != int(digitos[i]):
            return False
    return True


def _validar_cnpj(cnpj: str) -> bool:
    """Valida dígitos verificadores do CNPJ."""
    digitos = re.sub(r"\D", "", cnpj)
    if len(digitos) != 14 or len(set(digitos)) == 1:
        return False

    pesos1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    pesos2 = [6] + pesos1

    for pesos, i in [(pesos1, 12), (pesos2, 13)]:
        soma = sum(int(digitos[j]) * pesos[j] for j in range(i))
        dv = soma % 11
        dv = 0 if dv < 2 else 11 - dv
        if dv != int(digitos[i]):
            return False
    return True


def extrair_valor_principal(texto: str) -> Decimal | None:
    """Retorna o maior valor monetário do texto.

    Heurística: em comprovantes, o valor da transação é geralmente o maior
    valor exibido (vs. saldo após, taxas pequenas, etc.). Para PIX simples
    isso é correto em > 95% dos casos.
    """
    candidatos: list[Decimal] = []
    for m in RE_VALOR_BR.finditer(texto):
        valor_str = m.group(1).replace(".", "").replace(",", ".")
        try:
            candidatos.append(Decimal(valor_str))
        except InvalidOperation:
            continue
    if not candidatos:
        return None
    return max(candidatos)


def extrair_data(texto: str) -> datetime | None:
    """Retorna a primeira data válida encontrada.

    Heurística: comprovantes PIX têm a data da transação no topo
    (logo após o cabeçalho do banco). Primeira data encontrada é
    quase sempre a data da transação.
    """
    m = RE_DATA_BR.search(texto)
    if not m:
        return None
    dia, mes, ano = int(m.group(1)), int(m.group(2)), int(m.group(3))
    hora = int(m.group(4)) if m.group(4) else 0
    minuto = int(m.group(5)) if m.group(5) else 0
    segundo = int(m.group(6)) if m.group(6) else 0
    try:
        return datetime(ano, mes, dia, hora, minuto, segundo)
    except ValueError:
        return None


def extrair_documentos(texto: str) -> tuple[str | None, str | None]:
    """Retorna (cpf_primeiro_valido, cnpj_primeiro_valido)."""
    cpf_encontrado: str | None = None
    cnpj_encontrado: str | None = None

    for m in RE_CPF.finditer(texto):
        if _validar_cpf(m.group(1)):
            cpf_encontrado = m.group(1)
            break

    for m in RE_CNPJ.finditer(texto):
        if _validar_cnpj(m.group(1)):
            cnpj_encontrado = m.group(1)
            break

    return cpf_encontrado, cnpj_encontrado


def extrair_e2e_id(texto: str) -> str | None:
    """E2E ID do BACEN — formato `E` + 31 chars. Sempre presente em PIX real."""
    m = RE_E2E_ID.search(texto)
    return m.group(1) if m else None


def extrair_chave_pix(texto: str) -> str | None:
    """Detecta chave PIX no texto. Prioridade: e-mail > celular > UUID."""
    # E-mail é a chave mais comum em PIX comercial.
    m = RE_CHAVE_EMAIL.search(texto)
    if m:
        return m.group(0)

    # Celular
    m = RE_CHAVE_CELULAR.search(texto)
    if m:
        return m.group(0)

    # Chave aleatória
    m = RE_CHAVE_UUID.search(texto)
    if m:
        return m.group(0)

    return None


def extrair_nomes(texto: str) -> tuple[str | None, str | None]:
    """Heurística para extrair pagador e beneficiário.

    Procura linhas seguintes a palavras-chave:
    - Beneficiário: "Para", "Destinatário", "Beneficiário", "Quem recebeu"
    - Pagador: "De", "Pagador", "Origem", "Quem pagou"

    Retorna (pagador, beneficiario).
    """
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    pagador: str | None = None
    beneficiario: str | None = None

    palavras_chave_pagador = (
        "de:", "pagador", "origem", "quem pagou", "remetente"
    )
    palavras_chave_beneficiario = (
        "para:", "destinatário", "beneficiário", "quem recebeu", "favorecido", "recebedor"
    )

    for i, linha in enumerate(linhas):
        linha_lower = linha.lower()

        for chave in palavras_chave_pagador:
            if chave in linha_lower and pagador is None:
                pagador = _nome_proximo(linha, linhas, i, chave)
                break

        for chave in palavras_chave_beneficiario:
            if chave in linha_lower and beneficiario is None:
                beneficiario = _nome_proximo(linha, linhas, i, chave)
                break

    return pagador, beneficiario


def _nome_proximo(linha: str, linhas: list[str], i: int, chave: str) -> str | None:
    """Pega o nome após a palavra-chave (mesma linha ou próxima)."""
    # Tenta extrair da mesma linha após o `:`
    idx_dois_pontos = linha.find(":")
    if idx_dois_pontos > 0 and idx_dois_pontos < len(linha) - 1:
        nome = linha[idx_dois_pontos + 1 :].strip()
        if nome and not nome.lower().startswith(("destinatário", "beneficiário", "pagador")):
            return _sanitizar_nome(nome)
    # Senão, pega a linha seguinte
    if i + 1 < len(linhas):
        return _sanitizar_nome(linhas[i + 1])
    return None


def _sanitizar_nome(nome: str) -> str | None:
    """Limpa nome — corta em pontuação e remove documentos colados."""
    nome = re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "", nome)  # remove CPF
    nome = re.sub(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", "", nome)  # remove CNPJ
    nome = nome.strip(" -|:•\t")
    if len(nome) < 3 or len(nome) > 100:
        return None
    return nome


def extrair_entidades_de_texto(texto: str) -> EntidadesExtraidas:
    """Compõe a `EntidadesExtraidas` aplicando todos os extratores ao texto bruto."""
    cpf, cnpj = extrair_documentos(texto)
    pagador, beneficiario = extrair_nomes(texto)

    return EntidadesExtraidas(
        valor=extrair_valor_principal(texto),
        data=extrair_data(texto),
        pix_e2e_id=extrair_e2e_id(texto),
        chave_pix=extrair_chave_pix(texto),
        beneficiario_cnpj=cnpj,
        beneficiario_nome=beneficiario,
        pagador_documento=cpf,
        pagador_nome=pagador,
        textos_brutos=[texto],
    )
