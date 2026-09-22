from __future__ import annotations

import json
from pathlib import Path


def generate_pdfs(source: Path, destination: Path) -> list[Path]:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
    except ImportError as exc:
        raise RuntimeError(
            "Install project dependencies before generating PDF fixtures"
        ) from exc
    records = json.loads(source.read_text(encoding="utf-8"))
    destination.mkdir(parents=True, exist_ok=True)
    generated: list[Path] = []
    for invoice in records:
        path = destination / f"{invoice['invoice_number']}.pdf"
        pdf = canvas.Canvas(str(path), pagesize=A4)
        pdf.setTitle(f"Synthetic invoice {invoice['invoice_number']}")
        pdf.setFont("Helvetica-Bold", 16)
        pdf.drawString(54, 790, "SYNTHETIC DEMO INVOICE")
        pdf.setFont("Helvetica", 10)
        pdf.drawString(54, 772, "Generated mock data — not a real commercial document")
        lines = [
            f"Vendor: {invoice['vendor']}",
            f"Invoice Number: {invoice['invoice_number']}",
            f"Issue Date: {invoice['issue_date']}",
            f"Due Date: {invoice['due_date']}",
            f"Currency: {invoice['currency']}",
            "Line Items:",
        ]
        y = 740
        for line in lines:
            pdf.drawString(54, y, line)
            y -= 18
        pdf.setFont("Helvetica-Bold", 9)
        pdf.drawString(54, y, "Description | Qty | Unit Price | Line Total")
        y -= 16
        pdf.setFont("Helvetica", 9)
        for item in invoice["items"]:
            pdf.drawString(
                54,
                y,
                f"{item['description']} | {item['quantity']} | {item['unit_price']:.2f} | {item['line_total']:.2f}",
            )
            y -= 16
        y -= 8
        pdf.drawString(54, y, f"Subtotal: {invoice['subtotal']:.2f}")
        pdf.drawString(54, y - 18, f"Tax: {invoice['tax']:.2f}")
        pdf.setFont("Helvetica-Bold", 10)
        pdf.drawString(54, y - 38, f"Total: {invoice['total']:.2f}")
        pdf.save()
        generated.append(path)
    return generated
