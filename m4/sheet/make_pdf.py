"""Make the printable PDF: page 1 = answer sheet (bubbles), next pages = the questions."""
from __future__ import annotations

import argparse
import math
import os
import re
from pathlib import Path

from m4.sheet import layout as L

LETTERS = "ABCD"
CHARS_PER_LINE = 80  # safe estimate for 10pt text across the page
LINE_H = 13.5


def sheets_dir() -> Path:
    return Path(os.getenv("M4_SHEETS_DIR", "data/sheets_out"))


def sheet_path(quiz_id: str) -> Path:
    if not re.fullmatch(r"[A-Za-z0-9-]{1,64}", quiz_id):
        raise ValueError("bad quiz id")
    return sheets_dir() / f"{quiz_id}.pdf"


def _fitz():
    try:
        import pymupdf as fitz
    except ImportError:  # older PyMuPDF
        import fitz
    return fitz


def _block_height(text: str) -> float:
    lines = sum(max(1, math.ceil(len(line) / CHARS_PER_LINE)) for line in text.split("\n"))
    return lines * LINE_H + 4


def build_sheet_pdf(quiz_id: str, items, out_path: Path | str, n: int | None = None) -> Path:
    """`items` = list of QuizItem (questions get printed). With items=None only the sheet is made, for `n` questions."""
    fitz = _fitz()
    count = len(items) if items is not None else n
    if not count or not 1 <= count <= L.MAX_ITEMS:
        raise ValueError(f"need 1..{L.MAX_ITEMS} questions")

    doc = fitz.open()
    page = doc.new_page(width=L.PAGE_W, height=L.PAGE_H)

    half = L.MARKER_SIZE / 2
    for cx, cy in L.MARKER_CENTERS.values():
        page.draw_rect(fitz.Rect(cx - half, cy - half, cx + half, cy + half), color=(0, 0, 0), fill=(0, 0, 0))

    page.insert_text((150, 85), "EduPilot - answer sheet", fontsize=18, fontname="helv")
    page.insert_text((150, 105), f"Quiz: {quiz_id}", fontsize=10, fontname="helv")
    page.insert_text((150, 122), "Name: ______________________", fontsize=10, fontname="helv")
    page.insert_text((150, 140), "Fill ONE circle per question completely with a dark pen or pencil.",
                     fontsize=8, fontname="helv")

    for col in range(2):
        for j in range(4):
            page.insert_text((L.COL_X[col] + j * L.CHOICE_PITCH - 3.5, L.FIRST_ROW_Y - 22),
                             LETTERS[j], fontsize=11, fontname="helv")
    for i in range(count):
        x0, y0 = L.bubble_center(i, 0)
        page.insert_text((x0 - 40, y0 + 4), str(i + 1), fontsize=11, fontname="helv")
        for j in range(4):
            cx, cy = L.bubble_center(i, j)
            page.draw_circle(fitz.Point(cx, cy), L.BUBBLE_R, color=(0, 0, 0), width=1.0)

    if items is not None:
        qpage = doc.new_page(width=L.PAGE_W, height=L.PAGE_H)
        y = 60.0
        for i, item in enumerate(items):
            text = f"{i + 1}. {item.stem}\n" + "\n".join(
                f"     {LETTERS[j]}) {opt}" for j, opt in enumerate(item.options))
            h = _block_height(text)
            if y + h > L.PAGE_H - 50:
                qpage = doc.new_page(width=L.PAGE_W, height=L.PAGE_H)
                y = 60.0
            qpage.insert_textbox(fitz.Rect(50, y, L.PAGE_W - 50, y + h), text, fontsize=10, fontname="helv")
            y += h + 10

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(out))
    doc.close()
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Make a blank answer sheet PDF (no questions) for testing")
    ap.add_argument("--n", type=int, default=20)
    ap.add_argument("--quiz-id", default="demo")
    ap.add_argument("--out", default="data/sheet_demo.pdf")
    a = ap.parse_args()
    print("wrote", build_sheet_pdf(a.quiz_id, None, a.out, n=a.n))