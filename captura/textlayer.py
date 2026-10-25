"""Camada de texto do OCR: palavras com caixas, seleção por retângulo e dados sensíveis."""
import csv
import io
import os
import re
import subprocess
import tempfile
from dataclasses import dataclass

from . import services

EMAIL_RE = re.compile(r"^[\w.+-]+@[\w-]+(\.[\w-]+)+[.,;:]?$")
PHONE_CHARS = re.compile(r"^[+()\-.\d]+$")
URL_RE = re.compile(r"^(https?://|www\.)\S+$", re.I)


@dataclass
class Word:
    text: str
    box: tuple          # x0, y0, x1, y1 em pixels da imagem original
    line: tuple         # (bloco, parágrafo, linha)
    conf: float = 100.0


def parse_tsv(tsv, scale=1):
    words = []
    for row in csv.DictReader(io.StringIO(tsv), delimiter="\t", quoting=csv.QUOTE_NONE):
        text = (row.get("text") or "").strip()
        if row.get("level") != "5" or not text:
            continue
        try:
            left, top = int(row["left"]), int(row["top"])
            width, height = int(row["width"]), int(row["height"])
            conf = float(row.get("conf") or -1)
            line = (int(row["block_num"]), int(row["par_num"]), int(row["line_num"]))
        except (KeyError, ValueError):
            continue
        if conf < 0:
            continue
        box = (left / scale, top / scale, (left + width) / scale, (top + height) / scale)
        words.append(Word(text, tuple(round(v, 2) if v % 1 else int(v) for v in box), line, conf))
    return words


def words_text(words):
    lines, order = {}, []
    for w in words:
        if w.line not in lines:
            lines[w.line] = []
            order.append(w.line)
        lines[w.line].append(w.text)
    return "\n".join(" ".join(lines[k]) for k in order)


def _digits(text):
    return sum(c.isdigit() for c in text)


def sensitive(words):
    """Agrupa palavras que parecem e-mail, telefone ou URL (telefones podem vir em vários tokens)."""
    out = {"email": [], "phone": [], "url": []}
    run = []

    def flush():
        if sum(_digits(w.text) for w in run) >= 8:
            out["phone"].extend(run)
        run.clear()

    for w in words:
        t = w.text
        if run and run[-1].line != w.line:
            flush()
        if EMAIL_RE.match(t):
            flush(); out["email"].append(w)
        elif URL_RE.match(t):
            flush(); out["url"].append(w)
        elif PHONE_CHARS.match(t) and _digits(t) >= 1:
            run.append(w)
        else:
            flush()
    flush()
    return out


def words_in_rect(words, rect):
    rx0, ry0, rx1, ry1 = rect
    if rx0 > rx1: rx0, rx1 = rx1, rx0
    if ry0 > ry1: ry0, ry1 = ry1, ry0
    picked = []
    for w in words:
        x0, y0, x1, y1 = w.box
        ix, iy = min(x1, rx1) - max(x0, rx0), min(y1, ry1) - max(y0, ry0)
        if ix > 0 and iy > 0 and (ix * iy) / max(1, (x1 - x0) * (y1 - y0)) >= .25:
            picked.append(w)
    return picked


def ocr_surface(surface):
    """Executa o Tesseract (TSV) e devolve as palavras em coordenadas da imagem."""
    pb = services.surface_to_pixbuf(surface)
    from gi.repository import GdkPixbuf
    scale = 1
    w, h = pb.get_width(), pb.get_height()
    if max(w, h) < 1200:
        scale = 2
        pb = pb.scale_simple(w * 2, h * 2, GdkPixbuf.InterpType.BILINEAR)
    langs = services.ocr_languages()
    want = [l for l in ("por", "eng") if l in langs] or langs[:1]
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.png")
        pb.savev(src, "png", [], [])
        cmd = ["tesseract", src, "stdout", "--psm", "6"] + (["-l", "+".join(want)] if want else []) + ["tsv"]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
    return parse_tsv(r.stdout, scale)
