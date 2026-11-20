#!/usr/bin/env python3
"""Render a browser-free A4 cover PDF from minimax design tokens."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from reportlab.lib.colors import HexColor
from reportlab.lib.pagesizes import A4
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.pdfgen import canvas


def safe_color(value: str, fallback: str) -> HexColor:
    try:
        return HexColor(value)
    except Exception:
        return HexColor(fallback)


def wrap(text: str, font: str, size: float, width: float) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines, current = [], words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if stringWidth(candidate, font, size) <= width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tokens", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--subtitle", default="")
    args = parser.parse_args()
    tokens = json.loads(Path(args.tokens).read_text(encoding="utf-8"))
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)

    width, height = A4
    background = safe_color(tokens.get("cover_bg", "#172033"), "#172033")
    accent = safe_color(tokens.get("accent", "#2D5F8A"), "#2D5F8A")
    light = safe_color(tokens.get("text_light", "#F4F1EA"), "#F4F1EA")
    muted = safe_color(tokens.get("muted", "#AAB2C0"), "#AAB2C0")

    pdf = canvas.Canvas(str(output), pagesize=A4)
    pdf.setFillColor(background)
    pdf.rect(0, 0, width, height, stroke=0, fill=1)
    pdf.setFillColor(accent)
    pdf.rect(0, height - 7, width, 7, stroke=0, fill=1)
    pdf.rect(42, 120, 3, height - 240, stroke=0, fill=1)

    title = str(tokens.get("title", "Untitled Document"))
    subtitle = args.subtitle or str(tokens.get("subtitle", ""))
    label = f"{tokens.get('doc_type', 'DOCUMENT')}  ·  {tokens.get('date', '')}".upper()

    pdf.setFillColor(accent)
    pdf.setFont("Helvetica-Bold", 9)
    pdf.drawString(64, height - 170, label)

    pdf.setFillColor(light)
    pdf.setFont("Helvetica-Bold", 34)
    y = height - 230
    for line in wrap(title, "Helvetica-Bold", 34, width - 130):
        pdf.drawString(64, y, line)
        y -= 43

    pdf.setStrokeColor(accent)
    pdf.setLineWidth(2)
    pdf.line(64, y - 4, width * 0.58, y - 4)
    y -= 35
    if subtitle:
        pdf.setFillColor(muted)
        pdf.setFont("Helvetica", 12)
        for line in wrap(subtitle, "Helvetica", 12, width - 130):
            pdf.drawString(64, y, line)
            y -= 18

    pdf.setFillColor(muted)
    pdf.setFont("Helvetica", 9)
    pdf.drawString(64, 58, str(tokens.get("author", "")))
    pdf.drawRightString(width - 64, 58, str(tokens.get("date", "")))
    pdf.showPage()
    pdf.save()
    print(json.dumps({"status": "ok", "out": str(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
