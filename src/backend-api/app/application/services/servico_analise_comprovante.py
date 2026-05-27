"""ServicoAnaliseComprovante — orquestrador do pipeline (Story 13.19).

Encadeia as 3 camadas de análise + matcher + persistência num único fluxo:

    bytes do arquivo
        ↓
    1) BR Code decoder (pyzbar)
        ↓ (se falha)
    2) PDF texto (pdfplumber) — só se é PDF
        ↓ (se falha ou PDF escaneado)
    3) OCR (Tesseract+OpenCV) → extrai texto bruto
        ↓
    Extratores universais (regex sobre o texto)
        +
    Detector de banco + boost se identificado
        ↓
    Matcher com títulos em aberto da empresa
        ↓
    Persiste em `comprovantes_pagamento` (idempotente por hash)

Quando configurado, dispara IA Vision como reforço ou primário (port
`IProvedorIAVision` — adapter implementado em story futura).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.services.servico_configuracao import ServicoConfiguracao
from app.domain.finance.comprovante import (
    EntidadesExtraidas,
    MetodoAnalise,
    ResultadoAnaliseComprovante,
)
from app.infrastructure.comprovantes.br_code_decoder import decodificar_br_code
from app.infrastructure.comprovantes.detector_banco import detectar_banco
from app.infrastructure.comprovantes.extratores_universais import (
    extrair_entidades_de_texto,
)
from app.infrastructure.comprovantes.matcher_titulos import encontrar_titulo_match
from app.infrastructure.comprovantes.ocr import extrair_texto_via_ocr
from app.infrastructure.comprovantes.pdf_text_extractor import extrair_texto_pdf
from app.infrastructure.db.models.comprovante_pagamento import ComprovantePagamento


log = logging.getLogger(__name__)


class ComprovanteJaAnalisadoError(Exception):
    """Levantada quando hash do arquivo já existe (idempotência)."""

    def __init__(self, comprovante_existente: ComprovantePagamento):
        self.comprovante_existente = comprovante_existente
        super().__init__(f"Comprovante já analisado: {comprovante_existente.id}")


class ServicoAnaliseComprovante:
    def __init__(self, session: AsyncSession, empresa_id: UUID) -> None:
        self.session = session
        self.empresa_id = empresa_id

    async def analisar(
        self,
        bytes_arquivo: bytes,
        tipo_mime: str,
        arquivo_url: str,
        cliente_id: UUID | None = None,
        titulo_id_sugerido: UUID | None = None,
        origem: str = "upload",
        telefone_remetente: str | None = None,
    ) -> ComprovantePagamento:
        """Pipeline completo. Retorna o registro persistido em `comprovantes_pagamento`.

        Levanta `ComprovanteJaAnalisadoError` se hash do arquivo já existe pra
        este tenant (idempotência — retorna o registro anterior em vez de
        criar duplicata).
        """
        hash_arquivo = hashlib.sha256(bytes_arquivo).hexdigest()

        # Idempotência: já analisado?
        existente = await self.session.execute(
            select(ComprovantePagamento).where(
                ComprovantePagamento.empresa_id == self.empresa_id,
                ComprovantePagamento.arquivo_hash == hash_arquivo,
            )
        )
        ja_existe = existente.scalar_one_or_none()
        if ja_existe is not None:
            log.info(f"comprovante.ja_analisado hash={hash_arquivo[:16]}")
            raise ComprovanteJaAnalisadoError(ja_existe)

        # Carrega configuração do tenant
        servico_config = ServicoConfiguracao(self.session, self.empresa_id, redis=None)
        modo_analise = await servico_config.obter_string(
            "modo_analise", "comprovantes", padrao="nativo"
        )
        threshold_acionar_ia = await servico_config.obter_decimal(
            "threshold_acionar_ia", "comprovantes", padrao=Decimal("0.70")
        )

        # Executa pipeline (com possível IA dependendo do modo)
        resultado = await self._executar_pipeline(
            bytes_arquivo, tipo_mime, modo_analise, threshold_acionar_ia
        )

        # Tenta match com títulos em aberto
        cnpj_empresa = await self._obter_cnpj_empresa()
        if resultado.entidades.valor is not None:
            match = await encontrar_titulo_match(
                self.session, self.empresa_id, resultado.entidades, cnpj_empresa
            )
            if match is not None:
                resultado.titulo_match_id = str(match.titulo_id)
                resultado.titulo_match_score = match.score_match
                resultado.score_confianca += match.score_boost
                resultado.adicionar_aviso(f"match: {match.motivo}")
            else:
                resultado.adicionar_aviso("nenhum título compatível encontrado")
        else:
            resultado.adicionar_aviso("valor não detectado — sem possibilidade de match")

        resultado.clamp_score()

        # Persiste
        comprovante = ComprovantePagamento(
            empresa_id=self.empresa_id,
            cliente_id=cliente_id,
            titulo_id=UUID(resultado.titulo_match_id) if resultado.titulo_match_id else titulo_id_sugerido,
            arquivo_url=arquivo_url,
            arquivo_hash=hash_arquivo,
            tipo_arquivo=tipo_mime,
            tamanho_bytes=len(bytes_arquivo),
            metodo_analise=resultado.metodo.value,
            score_confianca=Decimal(str(round(resultado.score_confianca, 2))),
            valor_detectado=resultado.entidades.valor,
            data_detectada=resultado.entidades.data,
            pix_txid=resultado.entidades.pix_txid,
            pix_e2e_id=resultado.entidades.pix_e2e_id,
            banco_emissor=resultado.entidades.banco_emissor,
            beneficiario_cnpj=resultado.entidades.beneficiario_cnpj,
            beneficiario_nome=resultado.entidades.beneficiario_nome,
            pagador_nome=resultado.entidades.pagador_nome,
            pagador_documento=resultado.entidades.pagador_documento,
            chave_pix_usada=resultado.entidades.chave_pix,
            texto_bruto_ocr=(
                "\n".join(resultado.entidades.textos_brutos)
                if resultado.metodo == MetodoAnalise.OCR
                else None
            ),
            avisos=resultado.avisos,
            status="analisado",
            origem=origem,
            telefone_remetente=telefone_remetente,
        )
        self.session.add(comprovante)
        await self.session.flush()
        return comprovante

    async def _executar_pipeline(
        self,
        bytes_arquivo: bytes,
        tipo_mime: str,
        modo_analise: str,
        threshold_acionar_ia: Decimal,
    ) -> ResultadoAnaliseComprovante:
        """Aplica camadas 1 → 2 → 3 e, se configurado, IA Vision."""

        # Modo IA primário: pula pipeline nativo
        if modo_analise == "ia_primario":
            return await self._chamar_ia_vision(
                bytes_arquivo,
                tipo_mime,
                aviso="modo_analise=ia_primario",
                metodo_se_falha=MetodoAnalise.OCR,
            )

        # ── Camada 1: BR Code (só faz sentido em imagens) ──
        if tipo_mime.startswith("image/"):
            br_code = decodificar_br_code(bytes_arquivo)
            if br_code is not None:
                entidades, confianca = br_code
                entidades = self._completar_com_banco(entidades, "")
                resultado = ResultadoAnaliseComprovante(
                    metodo=MetodoAnalise.BR_CODE,
                    score_confianca=confianca,
                    entidades=entidades,
                )
                return await self._talvez_acionar_ia(
                    resultado, bytes_arquivo, tipo_mime, modo_analise, threshold_acionar_ia
                )

        # ── Camada 2: PDF textual ──
        if tipo_mime == "application/pdf":
            pdf_result = extrair_texto_pdf(bytes_arquivo)
            if pdf_result is not None:
                texto, confianca = pdf_result
                entidades = extrair_entidades_de_texto(texto)
                entidades = self._completar_com_banco(entidades, texto)
                resultado = ResultadoAnaliseComprovante(
                    metodo=MetodoAnalise.PDF_TEXTO,
                    score_confianca=confianca,
                    entidades=entidades,
                )
                # Boost por banco identificado
                tpl = detectar_banco(texto)
                if tpl is not None:
                    resultado.score_confianca += tpl.confianca_boost
                    resultado.adicionar_aviso(f"banco_detectado: {tpl.nome_oficial}")
                return await self._talvez_acionar_ia(
                    resultado, bytes_arquivo, tipo_mime, modo_analise, threshold_acionar_ia
                )

        # ── Camada 3: OCR ──
        # Para PDF que chegou aqui, é escaneado → precisamos rasterizar
        # antes do OCR. Em V1, só suportamos OCR direto em imagens.
        # PDF escaneado: TODO em story futura (incluir pdf2image).
        if tipo_mime.startswith("image/"):
            ocr_result = extrair_texto_via_ocr(bytes_arquivo)
            if ocr_result is not None:
                texto, confianca = ocr_result
                entidades = extrair_entidades_de_texto(texto)
                entidades = self._completar_com_banco(entidades, texto)
                resultado = ResultadoAnaliseComprovante(
                    metodo=MetodoAnalise.OCR,
                    score_confianca=confianca,
                    entidades=entidades,
                )
                tpl = detectar_banco(texto)
                if tpl is not None:
                    resultado.score_confianca += tpl.confianca_boost
                    resultado.adicionar_aviso(f"banco_detectado: {tpl.nome_oficial}")
                return await self._talvez_acionar_ia(
                    resultado, bytes_arquivo, tipo_mime, modo_analise, threshold_acionar_ia
                )

        # Nada funcionou — retorna resultado mínimo com aviso
        return ResultadoAnaliseComprovante(
            metodo=MetodoAnalise.OCR,  # placeholder
            score_confianca=0.0,
            entidades=EntidadesExtraidas(),
            avisos=["nenhuma camada do pipeline conseguiu extrair dados"],
        )

    def _completar_com_banco(
        self, entidades: EntidadesExtraidas, texto: str
    ) -> EntidadesExtraidas:
        """Anexa `banco_emissor` na EntidadesExtraidas se detectado."""
        if not texto:
            return entidades
        tpl = detectar_banco(texto)
        if tpl is None:
            return entidades
        # EntidadesExtraidas é frozen — recria com banco_emissor preenchido
        return EntidadesExtraidas(
            valor=entidades.valor,
            data=entidades.data,
            pix_txid=entidades.pix_txid,
            pix_e2e_id=entidades.pix_e2e_id,
            chave_pix=entidades.chave_pix,
            beneficiario_cnpj=entidades.beneficiario_cnpj,
            beneficiario_nome=entidades.beneficiario_nome,
            pagador_documento=entidades.pagador_documento,
            pagador_nome=entidades.pagador_nome,
            banco_emissor=tpl.nome_oficial,
            textos_brutos=list(entidades.textos_brutos),
        )

    async def _talvez_acionar_ia(
        self,
        resultado: ResultadoAnaliseComprovante,
        bytes_arquivo: bytes,
        tipo_mime: str,
        modo_analise: str,
        threshold_acionar_ia: Decimal,
    ) -> ResultadoAnaliseComprovante:
        """Quando modo=ia_como_reforco e confiança < threshold, chama IA."""
        if modo_analise != "ia_como_reforco":
            return resultado
        if resultado.score_confianca >= float(threshold_acionar_ia):
            return resultado
        resultado.adicionar_aviso(
            f"acionando_ia: confiança nativa {resultado.score_confianca:.2f} < threshold {threshold_acionar_ia}"
        )
        return await self._chamar_ia_vision(
            bytes_arquivo,
            tipo_mime,
            aviso=f"reforço acionado por confiança {resultado.score_confianca:.2f}",
            metodo_se_falha=resultado.metodo,
            base=resultado,
        )

    async def _chamar_ia_vision(
        self,
        bytes_arquivo: bytes,
        tipo_mime: str,
        aviso: str,
        metodo_se_falha: MetodoAnalise,
        base: ResultadoAnaliseComprovante | None = None,
    ) -> ResultadoAnaliseComprovante:
        """Stub — adapter real será implementado em story de integração futura.

        Por enquanto registra a intenção como aviso e devolve o resultado
        base (ou um placeholder vazio).
        """
        log.warning(
            "ia_vision.adapter_nao_implementado",
            extra={"aviso": aviso},
        )
        if base is not None:
            base.adicionar_aviso("ia_vision_pendente: adapter não implementado")
            return base
        return ResultadoAnaliseComprovante(
            metodo=metodo_se_falha,
            score_confianca=0.0,
            entidades=EntidadesExtraidas(),
            avisos=[
                "ia_primario configurado, mas adapter não implementado — pipeline nativo pulado",
                aviso,
            ],
        )

    async def _obter_cnpj_empresa(self) -> str | None:
        """Lê CNPJ da empresa tenant para reforçar match por beneficiário."""
        from app.infrastructure.db.models.comercial import Empresa
        try:
            empresa = await self.session.execute(
                select(Empresa).where(Empresa.id == self.empresa_id)
            )
            row = empresa.scalar_one_or_none()
            return row.cnpj if row else None
        except Exception:
            return None
