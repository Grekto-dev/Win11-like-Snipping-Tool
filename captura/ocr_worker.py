#!/usr/bin/python3
"""Processo de trabalho do OCR: mantém o Tesseract (libtesseract via ctypes) carregado e atende pedidos do aplicativo.

Protocolo (stdin/stdout, binário): cada pedido é uma linha JSON, seguida de `n` bytes quando o pedido traz dados (campo \"n\").
Cada resposta é uma linha JSON. Comandos: init, image, ocr, quit.

Roda como processo separado de propósito: (1) OMP_THREAD_LIMIT só vale se for definido antes de a libgomp carregar, e o
Tesseract fica ~5x mais lento por núcleo com as threads do OpenMP competindo; (2) o modelo fica na memória entre pedidos
(sem recarregar a cada captura); (3) um travamento ou um pedido cancelado não afeta a interface — o processo é só encerrado.
Este arquivo não importa nada do aplicativo nem o GTK (parte rápida e leve).
"""
import ctypes
import ctypes.util
import json
import os
import sys

RIL_BLOCK, RIL_PARA, RIL_LINE, RIL_WORD = 0, 1, 2, 3

_L = None


def lib():
    global _L
    if _L is None:
        L = ctypes.CDLL(ctypes.util.find_library("tesseract") or "libtesseract.so.5")
        vp, ci, cp = ctypes.c_void_p, ctypes.c_int, ctypes.c_char_p
        pci = ctypes.POINTER(ci)
        L.TessBaseAPICreate.restype = vp
        L.TessBaseAPIInit3.argtypes = [vp, cp, cp]
        L.TessBaseAPIInit3.restype = ci
        L.TessBaseAPIEnd.argtypes = [vp]
        L.TessBaseAPIDelete.argtypes = [vp]
        L.TessBaseAPISetVariable.argtypes = [vp, cp, cp]
        L.TessBaseAPISetVariable.restype = ctypes.c_bool
        L.TessBaseAPISetPageSegMode.argtypes = [vp, ci]
        L.TessBaseAPISetImage.argtypes = [vp, vp, ci, ci, ci, ci]
        L.TessBaseAPISetImage2.argtypes = [vp, vp]
        L.TessBaseAPIRecognize.argtypes = [vp, vp]
        L.TessBaseAPIRecognize.restype = ci
        L.TessBaseAPIGetIterator.argtypes = [vp]
        L.TessBaseAPIGetIterator.restype = vp
        L.TessBaseAPIClear.argtypes = [vp]
        L.TessResultIteratorGetPageIterator.argtypes = [vp]
        L.TessResultIteratorGetPageIterator.restype = vp
        L.TessResultIteratorGetUTF8Text.argtypes = [vp, ci]
        L.TessResultIteratorGetUTF8Text.restype = vp
        L.TessResultIteratorConfidence.argtypes = [vp, ci]
        L.TessResultIteratorConfidence.restype = ctypes.c_float
        L.TessResultIteratorDelete.argtypes = [vp]
        L.TessPageIteratorBoundingBox.argtypes = [vp, ci, pci, pci, pci, pci]
        L.TessPageIteratorBoundingBox.restype = ctypes.c_bool
        L.TessPageIteratorIsAtBeginningOf.argtypes = [vp, ci]
        L.TessPageIteratorIsAtBeginningOf.restype = ctypes.c_bool
        L.TessPageIteratorNext.argtypes = [vp, ci]
        L.TessPageIteratorNext.restype = ctypes.c_bool
        L.TessDeleteText.argtypes = [vp]
        _L = L
    return _L


_LEPT = None


def lept():
    global _LEPT
    if _LEPT is None:
        lp = ctypes.CDLL(ctypes.util.find_library("lept") or "liblept.so.5")
        lp.pixReadMemPng.argtypes = [ctypes.c_void_p, ctypes.c_size_t]
        lp.pixReadMemPng.restype = ctypes.c_void_p
        lp.pixDestroy.argtypes = [ctypes.POINTER(ctypes.c_void_p)]
        _LEPT = lp
    return _LEPT


class Worker:
    def __init__(self):
        self.h = None
        self.img = None            # (buffer, w, h, bpp, stride)
        self.png = False

    def free(self):
        if self.h is not None:
            L = lib()
            L.TessBaseAPIEnd(self.h)
            L.TessBaseAPIDelete(self.h)
            self.h = None

    def init(self, langs, datapath=None):
        L = lib()
        self.free()                                  # um init repetido não vaza o handle anterior
        h = L.TessBaseAPICreate()
        if L.TessBaseAPIInit3(h, datapath.encode() if datapath else None, langs.encode()) != 0:
            L.TessBaseAPIEnd(h)                      # falha: libera o handle criado, não guarda nada
            L.TessBaseAPIDelete(h)
            raise RuntimeError("falha ao carregar o Tesseract (%s)" % langs)
        L.TessBaseAPISetVariable(h, b"debug_file", b"/dev/null")       # silencia \"Estimating resolution as N\" no stderr
        self.h = h

    def set_image(self, data, w, h, bpp, stride, png=False):
        """Imagem crua: o último row pode ser abreviado (GdkPixbuf), então o mínimo é (h-1)*stride + w*bpp."""
        if w <= 0 or h <= 0 or bpp not in (1, 3, 4) or stride < w * bpp:
            raise ValueError("geometria de imagem inválida: %sx%s bpp=%s stride=%s" % (w, h, bpp, stride))
        if png:
            if not data:
                raise ValueError("empty-png")
        elif len(data) < (h - 1) * stride + w * bpp:
            raise ValueError("payload RAW curto: %d bytes, mínimo %d" % (len(data), (h - 1) * stride + w * bpp))
        buf = ctypes.create_string_buffer(data, len(data))
        self.img = (buf, w, h, bpp, stride)
        self.png = png

    def _prepare(self, psm):
        L = lib()
        buf, w, h, bpp, stride = self.img
        L.TessBaseAPISetPageSegMode(self.h, psm)
        if self.png:
            lp = lept()
            pix = ctypes.c_void_p(lp.pixReadMemPng(buf, len(buf)))
            if not pix:
                raise RuntimeError("invalid-png")
            try:
                L.TessBaseAPISetImage2(self.h, pix)
            finally:
                lp.pixDestroy(ctypes.byref(pix))
        else:
            L.TessBaseAPISetImage(self.h, ctypes.cast(buf, ctypes.c_void_p), w, h, bpp, stride)

    def ocr(self, psm=3):
        """Palavras como no TSV da CLI: [[texto, l, t, r, b, conf, bloco, parágrafo, linha], ...] (conf >= 0)."""
        L = lib()
        self._prepare(psm)
        out = []
        try:
            if L.TessBaseAPIRecognize(self.h, None) != 0:
                raise RuntimeError("tesseract-recognize-failed")      # erro explícito, nunca \"sem palavras\"
            it = L.TessBaseAPIGetIterator(self.h)
            if it:
                pi = L.TessResultIteratorGetPageIterator(it)
                blk = par = line = 0
                l, t, r, b = (ctypes.c_int() for _ in range(4))
                while True:
                    if L.TessPageIteratorIsAtBeginningOf(pi, RIL_BLOCK):
                        blk += 1
                        par = line = 0
                    if L.TessPageIteratorIsAtBeginningOf(pi, RIL_PARA):
                        par += 1
                        line = 0
                    if L.TessPageIteratorIsAtBeginningOf(pi, RIL_LINE):
                        line += 1
                    p = L.TessResultIteratorGetUTF8Text(it, RIL_WORD)
                    if p:
                        text = ctypes.string_at(p).decode("utf-8", "replace").strip()
                        L.TessDeleteText(p)
                        conf = L.TessResultIteratorConfidence(it, RIL_WORD)
                        if text and conf >= 0:
                            L.TessPageIteratorBoundingBox(pi, RIL_WORD, l, t, r, b)
                            out.append([text, l.value, t.value, r.value, b.value, round(conf, 2), blk, par, line])
                    if not L.TessPageIteratorNext(pi, RIL_WORD):
                        break
                L.TessResultIteratorDelete(it)
        finally:
            L.TessBaseAPIClear(self.h)
        return out


def main():
    try:
        os.nice(max(0, int(os.environ.get("CAPTURA_OCR_NICE", "4"))))
    except (OSError, ValueError):
        pass
    rin, rout = sys.stdin.buffer, sys.stdout.buffer
    w = Worker()

    def reply(obj):
        rout.write(json.dumps(obj, ensure_ascii=False).encode("utf-8") + b"\n")
        rout.flush()

    while True:
        line = rin.readline()
        if not line:
            return
        try:
            req = json.loads(line)
            n = req.get("n", 0)
            data = rin.read(n) if n else b""
            if n and len(data) != n:
                return
            cmd = req["cmd"]
            if cmd == "quit":
                return
            if cmd == "init":
                w.init(req["langs"], req.get("datapath"))
                reply({"ok": True})
            elif cmd == "image":
                w.set_image(data, req["w"], req["h"], req["bpp"], req["stride"], req.get("png", False))
                reply({"ok": True})
            elif cmd == "ocr":
                reply({"ok": True, "words": w.ocr(req.get("psm", 3))})
            else:
                reply({"ok": False, "error": "comando desconhecido: %s" % cmd})
        except Exception as e:                             # o pedido falha, o processo continua
            reply({"ok": False, "error": "%s: %s" % (type(e).__name__, e) if str(e) else type(e).__name__})


if __name__ == "__main__":
    main()
