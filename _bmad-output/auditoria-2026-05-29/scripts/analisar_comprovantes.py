"""Auditoria focada — só executa o pipeline de análise sobre os 4
comprovantes simulados. Reporta o que cada camada conseguiu extrair.

Rodar:
    PYTHONPATH=/app:/srv/audit-scripts python /srv/audit-scripts/analisar_comprovantes.py
"""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text


PASTA = Path("/srv/comprovantes-simulados")
SAIDA = Path("/srv/logs-auditoria/analise-comprovantes.json")


async def preparar_empresa_cliente() -> tuple:
    """Cria empresa+cliente descartáveis pra rodar análise. Sem contrato
    porque queremos ver o que o pipeline extrai mesmo sem match de título."""
    from app.infrastructure.db.session import get_engine

    engine = get_engine()
    emp_id = uuid4()
    cli_id = uuid4()
    async with engine.begin() as conn:
        await conn.execute(text("SET LOCAL row_security = off"))
        await conn.execute(
            text(
                "INSERT INTO comercial.empresas (id, razao_social, cnpj, email) "
                "VALUES (:i, :r, :c, :e)"
            ),
            {
                "i": str(emp_id),
                "r": f"Audit-Comprov-{emp_id.hex[:6]}",
                "c": str(emp_id.int)[:14].ljust(14, "0"),
                "e": f"audit-comp-{emp_id.hex[:6]}@local",
            },
        )
        await conn.execute(
            text(
                "INSERT INTO cadastro.clientes "
                "(id, empresa_id, nome_completo, cpf_cnpj, telefone, score, status) "
                "VALUES (:i, :e, :n, :cpf, :tel, 100, 'ativo')"
            ),
            {
                "i": str(cli_id),
                "e": str(emp_id),
                "n": "Auditor Comprovantes",
                "cpf": str(emp_id.int)[:11].ljust(11, "0"),
                "tel": "5511900000000",
            },
        )
    return emp_id, cli_id


async def analisar_um(emp_id, cli_id, arquivo: Path) -> dict:
    from app.application.services.servico_analise_comprovante import (
        ComprovanteJaAnalisadoError,
        ServicoAnaliseComprovante,
    )
    from app.infrastructure.db.session import get_sessionmaker

    sm = get_sessionmaker()
    bytes_arquivo = arquivo.read_bytes()
    mime = (
        "application/pdf" if arquivo.suffix.lower() == ".pdf"
        else "image/png" if arquivo.suffix.lower() == ".png"
        else "application/octet-stream"
    )
    async with sm() as s:
        await s.execute(text("SET LOCAL row_security = off"))
        try:
            svc = ServicoAnaliseComprovante(s, emp_id)
            c = await svc.analisar(
                bytes_arquivo=bytes_arquivo,
                tipo_mime=mime,
                arquivo_url=f"file://{arquivo}",
                cliente_id=cli_id,
                origem="upload",
                telefone_remetente=None,
            )
            await s.commit()
            return {
                "arquivo": arquivo.name,
                "mime": mime,
                "tamanho_bytes": len(bytes_arquivo),
                "ok": True,
                "metodo_analise": c.metodo_analise,
                "score_confianca": float(c.score_confianca) if c.score_confianca else None,
                "valor_detectado": str(c.valor_detectado) if c.valor_detectado else None,
                "data_detectada": c.data_detectada.isoformat() if c.data_detectada else None,
                "pix_txid": c.pix_txid,
                "pix_e2e_id": c.pix_e2e_id,
                "pagador_nome": c.pagador_nome,
                "pagador_documento": c.pagador_documento,
                "beneficiario_cnpj": c.beneficiario_cnpj,
                "beneficiario_nome": c.beneficiario_nome,
                "chave_pix_usada": c.chave_pix_usada,
                "banco_emissor": c.banco_emissor,
                "titulo_match_id": str(c.titulo_id) if c.titulo_id else None,
                "avisos": c.avisos if c.avisos else [],
                "texto_bruto_ocr": (c.texto_bruto_ocr or "")[:500],
            }
        except ComprovanteJaAnalisadoError as ja:
            return {
                "arquivo": arquivo.name, "ok": False, "duplicado": True,
                "comprovante_id": str(ja.comprovante_existente.id),
            }
        except Exception as exc:
            await s.rollback()
            import traceback
            return {
                "arquivo": arquivo.name, "ok": False,
                "erro": str(exc), "tipo_erro": type(exc).__name__,
                "traceback": traceback.format_exc()[-2000:],
            }


async def main() -> None:
    emp_id, cli_id = await preparar_empresa_cliente()
    arquivos = sorted(PASTA.glob("*.*"))
    resultados = []
    for arq in arquivos:
        print(f"==> analisando {arq.name}...")
        r = await analisar_um(emp_id, cli_id, arq)
        resultados.append(r)
        if r.get("ok"):
            print(f"    metodo: {r.get('metodo_analise')}, "
                  f"score: {r.get('score_confianca')}, "
                  f"valor: {r.get('valor_detectado')}")
        else:
            print(f"    FALHA: {r.get('erro') or 'duplicado'}")

    SAIDA.parent.mkdir(parents=True, exist_ok=True)
    SAIDA.write_text(
        json.dumps(resultados, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nResultados em {SAIDA}")


if __name__ == "__main__":
    asyncio.run(main())
