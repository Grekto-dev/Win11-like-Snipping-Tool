"""Camada de texto do OCR: palavras com caixas, seleção por retângulo e dados sensíveis."""
import csv
import io
import os
import re
import subprocess
import tempfile
import threading
import time
from dataclasses import dataclass

from . import ocr_engine, services

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
    """Texto na ordem de leitura; uma linha em branco entre parágrafos do OCR (o Tesseract em modo 4 separa os
    parágrafos da mesma forma que o Windows: medido com a mesma imagem nos dois)."""
    out, last_line = [], None
    cur = []
    for w in words:
        if last_line is not None and w.line != last_line:
            out.append((last_line, " ".join(cur)))
            cur = []
        cur.append(w.text)
        last_line = w.line
    if cur:
        out.append((last_line, " ".join(cur)))
    text, prev = [], None
    for line, s in out:
        if prev is not None and line[:2] != prev[:2]:
            text.append("")
        text.append(s)
        prev = line
    return "\n".join(text)


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


def _words_from_rows(rows):
    return [Word(t, tuple(round(v, 2) if v % 1 else int(v) for v in box), line, conf)
            for t, box, conf, line in rows if t and conf >= 0]


def ocr_surface(surface, job=None):
    """Reconhece o texto de uma superfície cairo e devolve as palavras em coordenadas da imagem.

    Mantém os modos, a escala e a seleção de tabela da versão publicada. A otimização
    fica no transporte, no carregamento persistente e no controle das threads."""
    return ocr_pixbuf_words(services.surface_to_pixbuf(surface), job)


def _prefer_sparse(rows):
    # Same decision as the published pipeline, on a fully recognized original
    # image. No layout heuristic, confidence shortcut or approximate table test.
    return bool(rows) and detect_table(_words_from_rows(rows)) is not None


def ocr_pixbuf_words(pb, job=None):
    langs = services.ocr_language_spec()
    job = ocr_engine.new_job() if job is None else job
    try:
        if ocr_engine.available():
            try:
                sparse_rows, plain_rows, _scale = ocr_engine.recognize_pair(pb, langs, job, accept_sparse=_prefer_sparse)
            except ocr_engine.WorkerError:
                job.check()                  # cancelado durante a falha do worker: não inicia a CLI
            else:
                sparse = _words_from_rows(sparse_rows)
                if sparse and detect_table(sparse) is not None:
                    return sparse
                return _words_from_rows(plain_rows)
        return _ocr_cli(pb, langs, job)      # plano B: mesmo token, cancelável até o fim
    finally:
        ocr_engine.end_job(job)


def warm_up():
    """Prepara o OCR e consulta os idiomas fora da thread da interface."""
    def prepare():
        if services.ocr_available():
            ocr_engine.warm_up(services.ocr_language_spec())
    threading.Thread(target=prepare, daemon=True).start()


def new_ocr_job(owner=None):
    """Token de uma leitura. Criado ANTES da thread: um cancelamento que chega antes da leitura já vale."""
    return ocr_engine.new_job(owner)


def cancel_ocr(job=None):
    """Interrompe a leitura de `job` (ou todas, sem token): libera os núcleos na hora."""
    ocr_engine.cancel(job)


def ocr_text(pb):
    return words_text(ocr_pixbuf_words(pb))


CLI_TIMEOUT = 300          # segundos, prazo absoluto de cada chamada à CLI


def _tesseract(path, psm, langs, job):
    """Uma execução da CLI presa ao token: cancelável em ~0,1 s, com prazo; sempre morta, recolhida e fechada."""
    env = dict(os.environ, OMP_THREAD_LIMIT="1", LC_ALL="C")          # sem isto o OpenMP do Tesseract fica ~5x mais lento por núcleo
    cmd = ["tesseract", path, "stdout", "--psm", str(psm)] + (["-l", langs] if langs else []) + ["tsv"]
    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
    except OSError as exc:
        raise ocr_engine.WorkerError("tesseract-indisponivel: %s" % exc) from exc
    try:
        job.attach(proc)
        deadline = time.monotonic() + CLI_TIMEOUT
        while True:
            try:
                out, err = proc.communicate(timeout=.1)
                break
            except subprocess.TimeoutExpired:
                job.check()
                if time.monotonic() >= deadline:
                    raise ocr_engine.WorkerError("ocr-cli-timeout")
        job.check()                          # um cancelamento mata o processo: sua saída não conta como resultado
        if proc.returncode != 0:
            raise ocr_engine.WorkerError("ocr-cli-exit %d: %s"
                                         % (proc.returncode, (err or "").strip()[:200] or "no-stderr"))
        if not (out or "").startswith("level\t"):
            raise ocr_engine.WorkerError("ocr-cli-invalid-tsv")
        return out
    finally:
        if proc.poll() is None:
            proc.kill()
        try:
            proc.wait(timeout=2)             # recolhe o processo (sem zumbi)
        except subprocess.TimeoutExpired:
            pass
        for stream in (proc.stdout, proc.stderr):
            if stream:
                stream.close()
        job.detach(proc)


def _ocr_cli(pb, langs, job):
    """Plano B: os mesmos modos, escala e seleção de tabela da versão publicada."""
    from gi.repository import GdkPixbuf
    job.check()
    w, h = pb.get_width(), pb.get_height()
    with tempfile.TemporaryDirectory() as d:
        orig = os.path.join(d, "orig.png")
        pb.savev(orig, "png", [], [])
        scale, src = 1, orig
        if max(w, h) < 1200:
            scale = 2
            src = os.path.join(d, "x2.png")
            pb.scale_simple(w * 2, h * 2, GdkPixbuf.InterpType.BILINEAR).savev(src, "png", [], [])
        sparse = parse_tsv(_tesseract(orig, 11, langs, job), 1)
        if sparse and detect_table(sparse) is not None:
            return sparse
        plain = parse_tsv(_tesseract(src, 4, langs, job), scale)
    return plain


# ------------------------------------------------------------------ geometria (medida no Windows)
LINE_PAD = (11, 12, 10, 11)          # esquerda, topo, direita, base (a partir da base das letras sem descendente)


@dataclass
class Line:
    words: list
    box: tuple          # caixa branca da linha no modo Ações de texto (x0, y0, x1, y1)


CELL_GAP = 2.4          # um vazio horizontal maior que 2,4 alturas de letra separa células (tabelas)


def _segments(ws):
    """Divide as palavras de uma linha do OCR em trechos separados por vazios largos."""
    ws = sorted(ws, key=lambda w: w.box[0])
    segs = [[ws[0]]]
    for w in ws[1:]:
        prev = segs[-1][-1]
        h = max(prev.box[3] - prev.box[1], w.box[3] - w.box[1])
        if w.box[0] - prev.box[2] > CELL_GAP * h:
            segs.append([w])
        else:
            segs[-1].append(w)
    return segs


def group_lines(words):
    """Agrupa as palavras por linha do OCR (na ordem de leitura) e calcula a caixa de cada linha/célula."""
    order, groups = [], {}
    for w in words:
        if w.line not in groups:
            groups[w.line] = []
            order.append(w.line)
        groups[w.line].append(w)
    lines = []
    for k in order:
        for ws in _segments(groups[k]):
            x0 = min(w.box[0] for w in ws); x1 = max(w.box[2] for w in ws)
            top = min(w.box[1] for w in ws); base = min(w.box[3] for w in ws)
            l, t, r, b = LINE_PAD
            lines.append(Line(ws, (x0 - l, top - t, x1 + r, base + b)))
    return lines


def sel_rect(w):
    """Retângulo de seleção/redação de uma palavra (medido: 1 px à esquerda, 4 à direita, 3 acima, 1 abaixo)."""
    x0, y0, x1, y1 = w.box
    return (x0 - 1, y0 - 3, x1 + 4, y1 + 1)


def sel_rects(words):
    """Um retângulo por linha, unindo palavras consecutivas (os espaços entre elas ficam cobertos)."""
    out = {}
    for w in words:
        r = sel_rect(w)
        if w.line in out:
            o = out[w.line]
            out[w.line] = (min(o[0], r[0]), min(o[1], r[1]), max(o[2], r[2]), max(o[3], r[3]))
        else:
            out[w.line] = r
    return list(out.values())


def _caret(words, lines, px, py):
    """Índice (na ordem de leitura) da palavra sob/ao lado do ponto."""
    best = min(range(len(lines)), key=lambda i: 0 if lines[i].box[1] <= py <= lines[i].box[3]
               else min(abs(py - lines[i].box[1]), abs(py - lines[i].box[3])))
    ws = lines[best].words
    pick = ws[-1]
    for w in ws:
        if px <= w.box[2] + 4:
            pick = w
            break
    return words.index(pick)


def select_between(words, p0, p1):
    """Seleção por arrasto em ordem de leitura, como num texto comum."""
    if not words:
        return []
    lines = group_lines(words)
    a = _caret(words, lines, *p0)
    b = _caret(words, lines, *p1)
    lo, hi = min(a, b), max(a, b)
    return words[lo:hi + 1]


# ------------------------------------------------------------------ tabelas
def _table_rows(words):
    """Palavras agrupadas em linhas visuais (centros a menos de ~6 px): [[Word, ...], ...] de cima para baixo."""
    rows = {}
    for w in words:
        rows.setdefault(round((w.box[1] + w.box[3]) / 2 / 6), []).append(w)
    merged = []
    for key in sorted(rows):
        if merged and key - merged[-1][0] <= 1:
            merged[-1][1].extend(rows[key])
        else:
            merged.append([key, list(rows[key])])
    return [ws for _k, ws in merged]


def detect_table(words):
    """Linhas de células alinhadas em colunas -> [[texto, ...], ...] (>= 2 linhas e 2 colunas) ou None."""
    if not words:
        return None
    table = []
    for ws in _table_rows(words):
        segs = _segments(ws)
        table.append([(" ".join(w.text for w in s), min(w.box[0] for w in s)) for s in segs])
    table = [r for r in table if r]
    multi = [r for r in table if len(r) >= 2]
    if len(multi) < 2 or len(multi) < len(table) * 0.6:
        return None
    ncol = max(len(r) for r in multi)
    anchors = [r for r in multi if len(r) == ncol]
    if len(anchors) < 2:
        return None
    cols = [sum(r[c][1] for r in anchors) / len(anchors) for c in range(ncol)]
    if not all(abs(r[c][1] - cols[c]) < 28 for r in anchors for c in range(ncol)):
        return None
    out = []
    for r in table:
        row = [""] * ncol
        for text, x in r:
            c = min(range(ncol), key=lambda i: abs(cols[i] - x))
            row[c] = (row[c] + " " + text).strip()
        out.append(row)
    return out


def table_html(rows):
    """HTML no formato que o Windows coloca na área de transferência (tabela com bordas)."""
    import html
    cells = "".join("<tr>" + "".join("<td>%s</td>" % html.escape(c) for c in r) + "</tr>" for r in rows)
    return ("<html><head><style>th, td { padding: 4px; font-family: Arial, Helvetica, sans-serif; }"
            "table { border-collapse: collapse; } table, th, td { border: 1px solid black; }</style></head>"
            "<body><table>%s</table></body></html>" % cells)


def table_text(rows):
    return "\n".join("\t".join(r) for r in rows)
