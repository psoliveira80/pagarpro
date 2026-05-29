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

# Valor monetário BR: "R$ 1.234,56" ou "R$ 1234,56" ou "1.234,56" sozinho.
# Auditoria 2026-05-29 B2: OCR em CPF mascarado ("***.987,65 4-+*") gerava
# match espúrio de valor. Por isso temos dois regexes: o "com R$" tem
# precedência absoluta na função `extrair_valor_principal`.
RE_VALOR_COM_REAL = re.compile(
    r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2})",
    re.IGNORECASE,
)
RE_VALOR_SEM_REAL = re.compile(
    r"(?<![.,\d])(\d{1,3}(?:\.\d{3})*,\d{2})(?![.,\d])",
)

# Data BR: "01/06/2026" ou "01-06-2026" — hora opcional após espaço, vírgula
# ou hífen. Auditoria 2026-05-29 B11: Caixa usa "27/05/2026, 18:09:07" (vírgula
# obrigatória entre data e hora) e antes o regex perdia a hora. Agora aceita
# vírgula, espaço e/ou hífen como separadores entre data e hora.
RE_DATA_BR = re.compile(
    r"\b(\d{2})[/-](\d{2})[/-](\d{4})"
    r"(?:[\s,]+(?:às|as|-)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
    re.IGNORECASE,
)

# Data BR com mês em texto: "23/mai/2026 - 08:34:21" (PicPay e variantes).
# Auditoria 2026-05-29 B11.
_MES_PT = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}
RE_DATA_BR_MES_TEXTO = re.compile(
    r"\b(\d{1,2})[/\s-](jan|fev|mar|abr|mai|jun|jul|ago|set|out|nov|dez)[a-zçãéúí]*"
    r"[/\s.,-]+(\d{4})"
    r"(?:[\s,]+(?:às|as|-)?\s*(\d{1,2}):(\d{2})(?::(\d{2}))?)?",
    re.IGNORECASE,
)

# CPF: "000.000.000-00"
RE_CPF = re.compile(r"\b(\d{3}\.\d{3}\.\d{3}-\d{2})\b")

# CNPJ com máscara: "00.000.000/0000-00"
RE_CNPJ_MASCARADO = re.compile(r"\b(\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2})\b")
# CNPJ sem máscara — 14 dígitos isolados (precedido por boundary ou palavra "CNPJ").
# Auditoria 2026-05-29 B5: comprovantes simulados traziam "CNPJ: 12345678000199".
RE_CNPJ_SEM_MASCARA = re.compile(
    r"(?:CNPJ[\s:]*)(\d{14})\b",
    re.IGNORECASE,
)

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


def extrair_valor_principal(texto: str) -> tuple[Decimal | None, list[str]]:
    """Retorna (valor_extraído, avisos).

    Estratégia em camadas (auditoria 2026-05-29 B2):
    1. Procura matches com prefixo `R$` obrigatório → pega o maior. É a
       fonte mais confiável: bancos sempre usam `R$` antes do valor.
    2. Se nenhum match com `R$`, cai num pass mais permissivo (decimais
       isolados) e devolve com um aviso explicando que veio sem prefixo
       — observabilidade pro gestor reavaliar.
    3. Linhas que claramente são CPF/CNPJ mascarado são descartadas no
       pass 2 (regex evita matches grudados em outros dígitos).

    Retorna `None` quando nenhum decimal é encontrado.
    """
    avisos: list[str] = []

    # Pass 1: valores com R$ explícito (alta confiança)
    candidatos_com_real = _coletar_decimais(RE_VALOR_COM_REAL, texto)
    if candidatos_com_real:
        return max(candidatos_com_real), avisos

    # Pass 2: fallback sem R$ — filtra linhas suspeitas de máscara CPF/CNPJ
    candidatos_sem_real: list[Decimal] = []
    for linha in texto.splitlines():
        if _linha_e_documento_mascarado(linha):
            continue
        candidatos_sem_real.extend(_coletar_decimais(RE_VALOR_SEM_REAL, linha))

    if candidatos_sem_real:
        avisos.append("valor_sem_prefixo_real")
        return max(candidatos_sem_real), avisos

    return None, avisos


def _coletar_decimais(regex: re.Pattern[str], texto: str) -> list[Decimal]:
    saida: list[Decimal] = []
    for m in regex.finditer(texto):
        valor_str = m.group(1).replace(".", "").replace(",", ".")
        try:
            saida.append(Decimal(valor_str))
        except InvalidOperation:
            continue
    return saida


def _linha_e_documento_mascarado(linha: str) -> bool:
    """Detecta heurísticamente linhas onde OCR pode ter quebrado uma máscara
    de CPF/CNPJ e gerado falso valor monetário (ex: `***.987,65 4-+*`)."""
    linha_lower = linha.lower()
    if "cpf" in linha_lower or "cnpj" in linha_lower:
        return True
    # 3+ asteriscos seguidos → máscara de privacidade
    if linha.count("*") >= 3:
        return True
    return False


def extrair_data(texto: str) -> datetime | None:
    """Retorna a primeira data válida encontrada.

    Heurística: comprovantes PIX têm a data da transação no topo
    (logo após o cabeçalho do banco). Primeira data encontrada é
    quase sempre a data da transação.

    Suporta dois formatos (auditoria 2026-05-29 B11):
    - Numérico: `21/05/2026 - 20:06:18` ou `27/05/2026, 18:09:07`
    - Com mês em texto: `23/mai/2026 - 08:34:21` (PicPay e variantes)
    """
    candidatas: list[datetime | None] = []

    m = RE_DATA_BR.search(texto)
    if m:
        candidatas.append(_montar_datetime(
            int(m.group(1)), int(m.group(2)), int(m.group(3)),
            m.group(4), m.group(5), m.group(6),
        ))

    m2 = RE_DATA_BR_MES_TEXTO.search(texto)
    if m2:
        mes_int = _MES_PT.get(m2.group(2)[:3].lower())
        if mes_int is not None:
            candidatas.append(_montar_datetime(
                int(m2.group(1)), mes_int, int(m2.group(3)),
                m2.group(4), m2.group(5), m2.group(6),
            ))

    validos = [d for d in candidatas if d is not None]
    return validos[0] if validos else None


def _montar_datetime(
    dia: int, mes: int, ano: int,
    hora_s: str | None, minuto_s: str | None, segundo_s: str | None,
) -> datetime | None:
    hora = int(hora_s) if hora_s else 0
    minuto = int(minuto_s) if minuto_s else 0
    segundo = int(segundo_s) if segundo_s else 0
    try:
        return datetime(ano, mes, dia, hora, minuto, segundo)
    except ValueError:
        return None


def extrair_documentos(texto: str) -> tuple[str | None, str | None, list[str]]:
    """Retorna (cpf_primeiro_valido, cnpj_primeiro_valido, avisos).

    Auditoria 2026-05-29 B5: aceita CNPJ com e sem máscara (`12.345.678/0001-99`
    ou `12345678000199` precedido de "CNPJ"). Quando um match regex casa mas
    a validação de DV falha, registra aviso pra debug — ajuda a saber que o
    OCR enxergou algo mas o dígito verificador não bate (provável erro de OCR).
    """
    avisos: list[str] = []
    cpf_encontrado: str | None = None
    cnpj_encontrado: str | None = None

    cpf_invalido_visto = False
    for m in RE_CPF.finditer(texto):
        if _validar_cpf(m.group(1)):
            cpf_encontrado = m.group(1)
            break
        cpf_invalido_visto = True
    if cpf_encontrado is None and cpf_invalido_visto:
        avisos.append("cpf_regex_casou_mas_dv_invalido")

    cnpj_invalido_visto = False
    candidatos_cnpj: list[str] = []
    for m in RE_CNPJ_MASCARADO.finditer(texto):
        candidatos_cnpj.append(m.group(1))
    for m in RE_CNPJ_SEM_MASCARA.finditer(texto):
        bruto = m.group(1)
        # Reformata pro padrão com máscara só pra normalizar a saída
        candidatos_cnpj.append(
            f"{bruto[:2]}.{bruto[2:5]}.{bruto[5:8]}/{bruto[8:12]}-{bruto[12:]}"
        )
    for candidato in candidatos_cnpj:
        if _validar_cnpj(candidato):
            cnpj_encontrado = candidato
            break
        cnpj_invalido_visto = True
    if cnpj_encontrado is None and cnpj_invalido_visto:
        avisos.append("cnpj_regex_casou_mas_dv_invalido")

    return cpf_encontrado, cnpj_encontrado, avisos


def extrair_e2e_id(texto: str) -> str | None:
    """E2E ID do BACEN — formato `E` + 31 chars. Sempre presente em PIX real."""
    m = RE_E2E_ID.search(texto)
    return m.group(1) if m else None


def extrair_chave_pix(texto: str) -> str | None:
    """Detecta chave PIX no texto. Prioridade: e-mail > celular > UUID.

    Auditoria 2026-05-29 B3: o campo "Autenticação" do banco usa UUID e
    estava sendo tratado como chave PIX. Agora UUID só é aceito se a
    linha do match não contiver palavras que indiquem outro campo
    (autenticação, hash, protocolo, código de transação, etc).
    """
    # E-mail é a chave mais comum em PIX comercial.
    m = RE_CHAVE_EMAIL.search(texto)
    if m:
        return m.group(0)

    # Celular
    m = RE_CHAVE_CELULAR.search(texto)
    if m:
        return m.group(0)

    # Chave aleatória — filtra falsos positivos por contexto da linha
    for m in RE_CHAVE_UUID.finditer(texto):
        linha = _linha_do_match(texto, m.start())
        if not _linha_indica_chave_pix(linha):
            continue
        return m.group(0)

    return None


_PALAVRAS_NAO_CHAVE_PIX = (
    "autenticação",
    "autenticacao",
    "auth",
    "hash",
    "protocolo",
    "código de transação",
    "codigo de transacao",
    "id da transação",
    "id da transacao",
    "id transação",
    "id transacao",
    "transaction id",
)
_PALAVRAS_INDICAM_CHAVE_PIX = ("chave", "pix")


def _linha_do_match(texto: str, pos: int) -> str:
    inicio = texto.rfind("\n", 0, pos) + 1
    fim = texto.find("\n", pos)
    if fim == -1:
        fim = len(texto)
    return texto[inicio:fim]


def _linha_indica_chave_pix(linha: str) -> bool:
    linha_lower = linha.lower()
    for proibida in _PALAVRAS_NAO_CHAVE_PIX:
        if proibida in linha_lower:
            return False
    # Se não tem indício claro de chave, ainda aceita — mas só quando a
    # linha está "neutra". Linhas que mencionam "chave"/"pix" têm
    # prioridade máxima (futuro: ordenação por relevância).
    return True


def extrair_nomes(texto: str) -> tuple[str | None, str | None]:
    """Heurística para extrair pagador e beneficiário.

    Procura linhas seguintes a palavras-chave em DUAS classes:
    - "Cabeçalho de seção" (Pagador, Dados do pagador, De): nome vem na
      linha N+1 ou N+2 (caso N+1 seja outro label como "Nome").
    - "Label inline" ("Nome:" / "Nome"): nome vem na mesma linha após o
      label, ou na linha seguinte.

    Auditoria 2026-05-29 B10: bancos reais usam combinações distintas
    (Santander: "De" sozinho + nome em N+1; Caixa: "Pagador" + "Nome
    Alexvaldo"; Bradesco: "Nome: ADSON..." dentro de seção; PicPay:
    "De" + nome em múltiplas linhas).

    Retorna (pagador, beneficiario).
    """
    linhas = [l.strip() for l in texto.splitlines() if l.strip()]
    pagador: str | None = None
    beneficiario: str | None = None

    cabecalhos_pagador = (
        "dados do pagador", "dados de quem fez", "pagador", "origem",
        "quem pagou", "remetente",
    )
    cabecalhos_beneficiario = (
        "dados do recebedor", "dados de quem recebeu", "destinatário",
        "beneficiário", "quem recebeu", "favorecido", "recebedor",
    )

    # Standalone "De" / "Para" como linhas inteiras (Santander, PicPay)
    standalones_pagador = ("de", "de:")
    standalones_beneficiario = ("para", "para:")

    for i, linha in enumerate(linhas):
        linha_lower = linha.lower()

        if pagador is None:
            for chave in cabecalhos_pagador:
                if chave in linha_lower:
                    pagador = _nome_inline_ou_proximo(linha, linhas, i)
                    break
            if pagador is None and linha_lower in standalones_pagador:
                pagador = _nome_apos_cabecalho(linhas, i)

        if beneficiario is None:
            for chave in cabecalhos_beneficiario:
                if chave in linha_lower:
                    beneficiario = _nome_inline_ou_proximo(linha, linhas, i)
                    break
            if beneficiario is None and linha_lower in standalones_beneficiario:
                beneficiario = _nome_apos_cabecalho(linhas, i)

    return pagador, beneficiario


# Linhas que NÃO podem virar "nome" — são sub-labels que costumam aparecer
# após cabeçalhos de seção (Pagador/Recebedor). Inclui "para"/"de" sozinhos
# porque Santander e PicPay quebram "Dados do recebedor\nPara\n<nome>"
# (auditoria 2026-05-29 B10).
_LINHAS_NAO_NOME = {
    "nome", "cpf", "cnpj", "cpf/cnpj", "instituição", "instituicao",
    "chave", "chave pix", "ag", "cc", "tipo", "valor", "data",
    "id", "id transação", "id da transação", "número de controle",
    "código de segurança", "chave de segurança", "situação",
    "para", "de", "para:", "de:",
}


def _nome_inline_ou_proximo(linha: str, linhas: list[str], i: int) -> str | None:
    """Tenta primeiro pegar nome inline ("Pagador: João da Silva") e cai pra
    cabeçalho de seção só se não houver nome após `:` na mesma linha.

    Casos cobertos:
    - "Pagador: João da Silva" → inline pega "João da Silva" ✓
    - "Dados do pagador" (sem dois pontos) → busca seção em N+1..N+3
    - "Pagador" (sozinho, com `:` no fim) → busca seção em N+1..N+3
    """
    idx = linha.find(":")
    if idx > 0:
        inline = linha[idx + 1:].strip()
        if inline:
            sanitizado = _sanitizar_nome(inline)
            if sanitizado is not None:
                return sanitizado
    return _nome_apos_cabecalho(linhas, i)


def _nome_apos_cabecalho(linhas: list[str], i: int) -> str | None:
    """Pega o nome real após um cabeçalho de seção (Pagador, De, Recebedor).

    Tenta linhas N+1, N+2, N+3 — pula sub-labels (Nome, CPF, etc.) e
    aceita a primeira que tenha cara de nome humano. Se a sub-label
    "Nome" aparece, devolve o conteúdo da linha seguinte (e se essa for
    continuação em 2 linhas, junta com a próxima — caso PicPay).
    """
    for offset in range(1, 4):
        if i + offset >= len(linhas):
            return None
        candidato = linhas[i + offset]
        candidato_lower = candidato.lower().strip(":")
        # Sub-label "Nome" — segue olhando a próxima linha
        if candidato_lower in ("nome", "nome:"):
            if i + offset + 1 < len(linhas):
                return _juntar_continuacao_nome(linhas, i + offset + 1)
            return None
        # "Nome Alexvaldo Lemos de Souza" — Caixa
        if candidato_lower.startswith("nome ") and len(candidato) > 5:
            return _sanitizar_nome(candidato[5:])
        # "Nome: ADSON..." — Bradesco
        if candidato_lower.startswith("nome:"):
            return _sanitizar_nome(candidato.split(":", 1)[1])
        # Linha "De" sozinha aninhada — ignora e segue
        if candidato_lower in _LINHAS_NAO_NOME:
            continue
        return _juntar_continuacao_nome(linhas, i + offset)
    return None


def _juntar_continuacao_nome(linhas: list[str], idx: int) -> str | None:
    """Pega `linhas[idx]` e tenta concatenar com `linhas[idx+1]` se essa
    parecer continuação do nome (linha curta, só letras maiúsculas, sem
    label conhecido). Caso PicPay: `ANA MARIA DE JESUS` + `COELHO`.
    """
    base = linhas[idx].strip()
    if idx + 1 < len(linhas):
        seguinte = linhas[idx + 1].strip()
        seguinte_lower = seguinte.lower().strip(":")
        # Pula se a próxima linha tem cara de label/documento/agência
        if seguinte and seguinte_lower not in _LINHAS_NAO_NOME:
            letras = sum(1 for c in seguinte if c.isalpha())
            so_letras_ou_espaco = all(
                c.isalpha() or c.isspace() or c in ".-'" for c in seguinte
            )
            if 0 < len(seguinte) <= 40 and letras >= 3 and so_letras_ou_espaco:
                base = f"{base} {seguinte}"
    return _sanitizar_nome(base)


def _sanitizar_nome(nome: str) -> str | None:
    """Limpa nome — corta em pontuação e remove documentos colados.

    Auditoria 2026-05-29 B10: descarta linhas que parecem agência/conta
    (`AG 0323 | CC 15379`) e ruído OCR (sequências de pontuação).
    """
    nome = re.sub(r"\d{3}\.\d{3}\.\d{3}-\d{2}", "", nome)  # remove CPF
    nome = re.sub(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", "", nome)  # remove CNPJ
    nome = nome.strip(" -|:•\t.")
    if len(nome) < 3 or len(nome) > 100:
        return None
    # Descarta dados bancários "AG 0323 | CC 15379"
    if re.match(r"^(AG|CC|AG\.|CC\.)\b", nome, re.IGNORECASE):
        return None
    # Descarta linhas que são só pontuação/dígitos
    letras = sum(1 for c in nome if c.isalpha())
    if letras < 3:
        return None
    # Remove prefixo "Nome "/"Nome." residual ("Nome FELIPE..." / "Nome. FELIPE...")
    nome_low = nome.lower()
    if nome_low.startswith("nome. "):
        nome = nome[6:].strip()
    elif nome_low.startswith("nome "):
        nome = nome[5:].strip()
    return nome if len(nome) >= 3 else None


def extrair_entidades_de_texto(texto: str) -> tuple[EntidadesExtraidas, list[str]]:
    """Compõe a `EntidadesExtraidas` aplicando todos os extratores ao texto bruto.

    Retorna `(entidades, avisos)`. Os avisos refletem heurísticas de baixa
    confiança que o caller deve repassar pro resultado final
    (`ResultadoAnaliseComprovante.avisos`). Auditoria 2026-05-29.
    """
    valor, avisos_valor = extrair_valor_principal(texto)
    cpf, cnpj, avisos_doc = extrair_documentos(texto)
    pagador, beneficiario = extrair_nomes(texto)

    entidades = EntidadesExtraidas(
        valor=valor,
        data=extrair_data(texto),
        pix_e2e_id=extrair_e2e_id(texto),
        chave_pix=extrair_chave_pix(texto),
        beneficiario_cnpj=cnpj,
        beneficiario_nome=beneficiario,
        pagador_documento=cpf,
        pagador_nome=pagador,
        textos_brutos=[texto],
    )
    return entidades, [*avisos_valor, *avisos_doc]
