"""Gera 3 tipos de comprovante simulado pra testar o pipeline de análise:

1. PDF com texto selecionável → pdfplumber (camada 2 do pipeline)
2. PDF escaneado (imagem dentro de PDF) → OCR (camada 3) — mas a Story
   13.19 ainda só faz OCR em imagem direta; PDF escaneado vai cair em
   "nenhuma camada funcionou" e vamos auditar isso.
3. PNG (foto de comprovante) — vamos gerar 2 variantes:
   3a. Com BR Code (QR Code PIX) → camada 1
   3b. Sem BR Code, só texto OCR → camada 3

Usado pelo auditor pra rodar `ServicoAnaliseComprovante.analisar()` em
cada arquivo e ver o que sai.
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path

import qrcode
from PIL import Image, ImageDraw, ImageFont
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.pdfgen import canvas as rl_canvas


PASTA = Path("/srv/comprovantes-simulados")


# ─────────────────── BR Code PIX (EMV-padronizado) ────────────────────

def montar_brcode_pix(
    chave: str,
    nome_recebedor: str,
    cidade: str,
    valor: float,
    txid: str,
) -> str:
    """Gera um BR Code PIX EMV (estático) válido sem CRC verdadeiro —
    o suficiente para o decodificador encontrar campos."""

    def tlv(tag: str, valor: str) -> str:
        return f"{tag}{len(valor):02d}{valor}"

    payload_account = tlv("00", "br.gov.bcb.pix") + tlv("01", chave)
    template_account = tlv("26", payload_account)
    additional = tlv("05", txid)
    template_add = tlv("62", additional)

    body = (
        tlv("00", "01")
        + tlv("01", "11")
        + template_account
        + tlv("52", "0000")
        + tlv("53", "986")
        + tlv("54", f"{valor:.2f}")
        + tlv("58", "BR")
        + tlv("59", nome_recebedor[:25])
        + tlv("60", cidade[:15])
        + template_add
    )
    # CRC-16 placeholder (decodificador pode tolerar)
    body = body + "6304"
    return body + "ABCD"


# ─────────────────── 1. PDF com texto (banco simulado) ────────────────

def gerar_pdf_texto(saida: Path) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    c = rl_canvas.Canvas(str(saida), pagesize=A4)
    largura, altura = A4

    y = altura - 2 * cm
    c.setFont("Helvetica-Bold", 16)
    c.drawString(2 * cm, y, "Banco Simulado S.A.")
    y -= 0.7 * cm
    c.setFont("Helvetica", 10)
    c.drawString(2 * cm, y, "Comprovante de Transferência PIX")
    y -= 1.2 * cm

    c.setFont("Helvetica-Bold", 12)
    c.drawString(2 * cm, y, "Detalhes da operação")
    y -= 0.7 * cm
    c.setFont("Helvetica", 11)

    linhas = [
        ("Valor:",              "R$ 800,00"),
        ("Data e hora:",        "28/05/2026 às 14:32:11"),
        ("Tipo:",               "Transferência PIX"),
        ("Pagador:",            "JOAO DA SILVA SANTOS"),
        ("CPF do pagador:",     "***.456.789-**"),
        ("Banco do pagador:",   "Banco Simulado S.A."),
        ("Recebedor:",          "FROTAUBER LOCACOES LTDA"),
        ("CNPJ do recebedor:",  "12.345.678/0001-99"),
        ("Chave PIX:",          "12345678000199"),
        ("Tipo de chave:",      "CNPJ"),
        ("Identificador (txid):", "FU2026052800001"),
        ("ID end-to-end:",      "E60746948202605281432000000123456"),
        ("Autenticação:",       "9F4A2B1C-7E5D-4F9A-B8C2-1234567890AB"),
    ]
    for chave, val in linhas:
        c.drawString(2 * cm, y, chave)
        c.drawString(7 * cm, y, val)
        y -= 0.55 * cm

    y -= 1 * cm
    c.setFont("Helvetica-Oblique", 9)
    c.drawString(
        2 * cm, y,
        "Este comprovante é meramente informativo e foi gerado para teste de auditoria."
    )
    c.showPage()
    c.save()


# ─────────────────── 2. PDF "escaneado" (imagem dentro) ───────────────

def gerar_pdf_escaneado(saida: Path) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)

    img = Image.new("RGB", (1240, 1754), color="white")
    draw = ImageDraw.Draw(img)
    try:
        fonte_grande = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40
        )
        fonte = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 28
        )
    except OSError:
        fonte_grande = ImageFont.load_default()
        fonte = ImageFont.load_default()

    draw.text((80, 60), "Banco Brasileiro Digital", font=fonte_grande, fill="black")
    draw.text((80, 120), "Comprovante PIX", font=fonte, fill="black")
    draw.line((80, 180, 1160, 180), fill="black", width=2)

    linhas = [
        ("Valor", "R$ 1.250,00"),
        ("Data", "27/05/2026 09:15"),
        ("Tipo", "PIX Transferencia"),
        ("Pagador", "MARIA FERREIRA COSTA"),
        ("CPF pagador", "***.123.456-**"),
        ("Recebedor", "FROTAUBER LOCACOES LTDA"),
        ("CNPJ recebedor", "12.345.678/0001-99"),
        ("Chave", "12345678000199"),
        ("ID transacao", "BBD20260527091500ABC"),
    ]
    y = 220
    for k, v in linhas:
        draw.text((80, y), f"{k}:", font=fonte, fill="black")
        draw.text((520, y), v, font=fonte, fill="black")
        y += 50

    # Ruído leve (faixa cinza, simula scanner)
    for i in range(0, img.height, 6):
        draw.line((0, i, img.width, i), fill=(245, 245, 245), width=1)

    img.save(saida, "PDF", resolution=200)


# ─────────────────── 3a. PNG com BR Code ──────────────────────────────

def gerar_png_com_brcode(saida: Path) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    brcode = montar_brcode_pix(
        chave="12345678000199",
        nome_recebedor="FROTAUBER LOCACOES LTDA",
        cidade="SAO PAULO",
        valor=950.00,
        txid="FU2026052900042",
    )

    qr = qrcode.QRCode(box_size=12, border=2)
    qr.add_data(brcode)
    qr.make(fit=True)
    qr_img = qr.make_image(fill_color="black", back_color="white").convert("RGB")

    # Canvas maior que só o QR pra ter "comprovante visual"
    canvas = Image.new("RGB", (900, 1400), "white")
    canvas.paste(qr_img.resize((520, 520)), (190, 200))

    draw = ImageDraw.Draw(canvas)
    try:
        fonte_t = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
        )
        fonte = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
        )
    except OSError:
        fonte_t = ImageFont.load_default()
        fonte = ImageFont.load_default()

    draw.text((250, 50), "Pagamento PIX", font=fonte_t, fill="black")
    draw.text((180, 110), "Aponte para o QR Code para concluir", font=fonte, fill="gray")

    y = 780
    linhas = [
        ("Valor", "R$ 950,00"),
        ("Recebedor", "FROTAUBER LOCACOES LTDA"),
        ("Chave PIX", "12345678000199"),
        ("Identificador", "FU2026052900042"),
        ("Data emissão", "29/05/2026"),
    ]
    for k, v in linhas:
        draw.text((100, y), f"{k}:", font=fonte, fill="black")
        draw.text((360, y), v, font=fonte, fill="black")
        y += 50

    canvas.save(saida, "PNG")


# ─────────────────── 3b. PNG comprovante texto (sem QR) ───────────────

def gerar_png_apenas_texto(saida: Path) -> None:
    saida.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGB", (900, 1400), "white")
    draw = ImageDraw.Draw(img)
    try:
        fonte_t = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 36
        )
        fonte = ImageFont.truetype(
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24
        )
    except OSError:
        fonte_t = ImageFont.load_default()
        fonte = ImageFont.load_default()

    draw.text((280, 60), "Banco XYZ Digital", font=fonte_t, fill="black")
    draw.text((300, 110), "Comprovante PIX", font=fonte, fill="black")
    draw.line((60, 180, 840, 180), fill="black", width=2)

    linhas = [
        ("Valor", "R$ 600,00"),
        ("Data", "26/05/2026 18:42"),
        ("Pagador", "CARLOS DE OLIVEIRA"),
        ("CPF", "***.987.654-**"),
        ("Recebedor", "FROTAUBER LOCACOES LTDA"),
        ("CNPJ", "12.345.678/0001-99"),
        ("Chave", "12345678000199"),
        ("Codigo", "XYZ2026052618420987"),
    ]
    y = 220
    for k, v in linhas:
        draw.text((80, y), f"{k}:", font=fonte, fill="black")
        draw.text((360, y), v, font=fonte, fill="black")
        y += 55

    img.save(saida, "PNG")


# ─────────────────── Entry-point ──────────────────────────────────────

def gerar_todos(pasta: Path = PASTA) -> dict[str, Path]:
    pasta.mkdir(parents=True, exist_ok=True)
    saidas = {
        "pdf_texto":       pasta / "comprovante_01_pdf_texto.pdf",
        "pdf_escaneado":   pasta / "comprovante_02_pdf_escaneado.pdf",
        "png_brcode":      pasta / "comprovante_03_png_brcode.png",
        "png_texto":       pasta / "comprovante_04_png_texto.png",
    }
    gerar_pdf_texto(saidas["pdf_texto"])
    gerar_pdf_escaneado(saidas["pdf_escaneado"])
    gerar_png_com_brcode(saidas["png_brcode"])
    gerar_png_apenas_texto(saidas["png_texto"])
    return saidas


if __name__ == "__main__":
    saidas = gerar_todos()
    for k, v in saidas.items():
        tam = v.stat().st_size if v.exists() else 0
        print(f"[OK] {k:<15} → {v}  ({tam} bytes)")
