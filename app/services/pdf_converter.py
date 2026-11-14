import io
from pathlib import Path

from fastapi import HTTPException, status


IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "gif", "bmp", "tiff", "tif", "webp", "heic"}
EXCEL_EXTENSIONS = {"xls", "xlsx"}


def convert_image_to_pdf(file_bytes: bytes, original_name: str) -> bytes:
    from PIL import Image

    img = Image.open(io.BytesIO(file_bytes))
    if img.mode in ("RGBA", "P", "LA"):
        img = img.convert("RGB")

    pdf_bytes = io.BytesIO()
    img.save(pdf_bytes, format="PDF")
    return pdf_bytes.getvalue()


def convert_excel_to_pdf(file_bytes: bytes, original_name: str) -> bytes:
    import openpyxl
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.units import mm
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)

    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=landscape(A4),
        leftMargin=10 * mm,
        rightMargin=10 * mm,
        topMargin=10 * mm,
        bottomMargin=10 * mm,
    )

    styles = getSampleStyleSheet()
    elements = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]

        if len(wb.sheetnames) > 1:
            elements.append(Paragraph(f"Лист: {sheet_name}", styles["Heading2"]))
            elements.append(Spacer(1, 4 * mm))

        rows = []
        for row in ws.iter_rows(values_only=True):
            cells = []
            for cell in row:
                if cell is None:
                    cells.append("")
                elif isinstance(cell, (int, float)):
                    cells.append(str(cell))
                else:
                    text = str(cell)
                    if len(text) > 60:
                        text = text[:57] + "..."
                    cells.append(text)
            rows.append(cells)

        if not rows:
            continue

        max_cols = max(len(r) for r in rows)
        for row in rows:
            while len(row) < max_cols:
                row.append("")

        available_width = landscape(A4)[0] - 20 * mm
        col_width = available_width / max_cols
        col_widths = [col_width] * max_cols

        table = Table(rows, colWidths=col_widths, repeatRows=1)
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#4472C4")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("ALIGN", (0, 0), (-1, -1), "LEFT"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#D6E4F0")]),
            ("TOPPADDING", (0, 0), (-1, -1), 2),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ("LEFTPADDING", (0, 0), (-1, -1), 3),
            ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ]))
        elements.append(table)
        elements.append(Spacer(1, 6 * mm))

    if not elements:
        elements.append(Paragraph("Пустой документ", styles["Normal"]))

    doc.build(elements)
    return pdf_buffer.getvalue()


def get_pdf_bytes(file_bytes: bytes, original_name: str) -> bytes:
    ext = Path(original_name).suffix.lower().lstrip(".")

    if ext in IMAGE_EXTENSIONS:
        return convert_image_to_pdf(file_bytes, original_name)

    if ext in EXCEL_EXTENSIONS:
        return convert_excel_to_pdf(file_bytes, original_name)

    if ext == "pdf":
        return file_bytes

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Формат .{ext} не поддерживается для конвертации в PDF. Поддерживаются: изображения (png, jpg, jpeg, gif, bmp, tiff, webp) и Excel (xls, xlsx).",
    )
