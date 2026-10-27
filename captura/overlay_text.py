"""Extrator de texto dentro da sobreposição de captura (Win+Shift+S), medido no Windows 11 (1440x900, quadro a quadro).

Fluxo: o extrator troca a barra principal por [← | Copiar todo o texto | ⋯ | ✕] (324x50, y=13); o usuário arrasta um retângulo
(janela clara sem escurecimento); ao soltar, a seleção vira um anel de gradiente girando (6 px, ~0,4 s + 20,5 ms por linha); depois:
  - sem texto: aviso "Nenhum texto foi detectado" (sobe 23 px com fade em 200 ms, fica ~3 s, desce 22 px em 150 ms), seleção some;
  - com texto: só as linhas viram caixas brancas (recortadas pela seleção), alças brancas; arrastar dentro seleciona palavras
    em ordem de leitura (#b2d6f2) e, ao soltar, aparece a mini barra [copiar | QR] com o canto superior esquerdo no ponto final.
Copiar (barra, mini barra ou Ctrl+C) fecha a sobreposição e mostra o aviso "Texto copiado" no topo da tela.
"""
import math
import threading
import time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gdk, GLib, Gtk

from . import i18n, icons, qr, text_anim, textlayer, theme
from .config import settings
from .shape_bar import draw_text, rgb, text_rgb
from .text_bar import icon_copy

# --------------------------------------------------------------------------- medidas (relativas à barra / ao cartão)
BAR_W, BAR_H, BAR_TOP = 324, 50, 13
BTN_Y, BTN_H = 9, 32
BACK = (9, BTN_Y, 32, BTN_H)
COPYALL = (57, BTN_Y, 168, BTN_H)
MORE = (234, BTN_Y, 32, BTN_H)
CLOSE = (282, BTN_Y, 32, BTN_H)
SEPS = (49, 274)
SEP_Y, SEP_H = 13, 24

MINI_W, MINI_H = 89, 48
MINI_COPY = (8, 8, 32, 32)
MINI_QR = (48, 8, 32, 32)

CARD_H = 51
NOTICE_W, NOTICE_TOP = 237, 73
TOAST_W, TOAST_H, TOAST_TOP = 151, 52, 9

MENU_DX, MENU_DY = 127, 52                  # menu ⋯: canto superior esquerdo relativo à barra
INSET = 5
MIN_SCAN = 0.40                             # s (área sem texto)
SCAN_PER_LINE = 0.0205

APPEAR_MS, HOLD_S, LEAVE_MS = 200, 2.9, 150
RISE, FALL = 23, 22


def hit(box, x, y):
    return box[0] <= x < box[0] + box[2] and box[1] <= y < box[1] + box[3]


def round_path(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def muted(c):
    bg = rgb(theme.palette()["ov_bar"])
    return tuple(c[i] * .4 + bg[i] * .6 for i in range(3))


# --------------------------------------------------------------------------- barra do extrator
class OcrBar(Gtk.DrawingArea):
    """← | Copiar todo o texto | ⋯ | ✕, desenhada em pixels (mesmo estilo da barra do overlay)."""

    def __init__(self, on_back, on_copy_all, on_more, on_close):
        super().__init__()
        self.cb = dict(back=on_back, copy=on_copy_all, more=on_more, close=on_close)
        self.copy_enabled = False
        self.hover = None
        self.pressed = None
        self.set_size_request(BAR_W, BAR_H)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_has_tooltip(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self._draw)
        self.connect("motion-notify-event", self._motion)
        self.connect("leave-notify-event", lambda *a: self._set_hover(None))
        self.connect("button-press-event", self._press)
        self.connect("button-release-event", self._release)
        self.connect("query-tooltip", self._tip)

    BOXES = (("back", BACK), ("copy", COPYALL), ("more", MORE), ("close", CLOSE))

    def hold(self, name):
        self.held = name
        self.queue_draw()

    held = None

    def set_copy_enabled(self, on):
        self.copy_enabled = on
        self.queue_draw()

    def _which(self, x, y):
        for name, box in self.BOXES:
            if hit(box, x, y) and (name != "copy" or self.copy_enabled):
                return name
        return None

    def _set_hover(self, name):
        if name != self.hover:
            self.hover = name
            self.queue_draw()

    def _motion(self, _w, ev):
        self._set_hover(self._which(ev.x, ev.y))
        return False

    def _press(self, _w, ev):
        if ev.button == 1:
            self.pressed = self._which(ev.x, ev.y)
            self.queue_draw()
        return True

    def _release(self, _w, ev):
        name, self.pressed = self.pressed, None
        self.queue_draw()
        if ev.button == 1 and name and name == self._which(ev.x, ev.y):
            GLib.idle_add(lambda: (self.cb[name](), False)[1])
        return True

    def _tip(self, _w, x, y, _kb, tip):
        text = {"more": "Mais opções", "close": "Fechar", "back": "Voltar"}.get(self._which(x, y))
        if text:
            tip.set_text(text)
            return True
        return False

    def _draw(self, _w, cr):
        pal = theme.palette()
        round_path(cr, 0, 0, BAR_W, BAR_H, 8)
        cr.set_source_rgb(*rgb(pal["ov_bar"]))
        cr.fill()
        col = text_rgb()
        for name, box in self.BOXES:
            if name == "copy" and not self.copy_enabled:
                continue
            if self.hover == name or self.pressed == name or self.held == name:
                round_path(cr, *box, 4)
                cr.set_source_rgb(*rgb(pal["ov_hover"]))
                cr.fill()
        cr.set_source_rgb(*rgb(pal["ov_sep"]))
        for x in SEPS:
            cr.rectangle(x, SEP_Y, 1, SEP_H)
            cr.fill()
        for name, box in (("back", BACK), ("close", CLOSE)):
            pb = icons.pixbuf(name, 20, theme.icon_color())
            Gdk.cairo_set_source_pixbuf(cr, pb, box[0] + (box[2] - 20) // 2, box[1] + (box[3] - 20) // 2)
            cr.paint()
        cr.set_source_rgb(*col)
        for dx in (244, 249, 254):                                   # ⋯ medido: três pontos de 2x2
            cr.rectangle(dx, 24, 2, 2)
            cr.fill()
        c = col if self.copy_enabled else muted(col)
        cr.save(); cr.translate(COPYALL[0] + 13, 17); icon_copy(cr, c); cr.restore()
        draw_text(cr, "Copiar todo o texto", COPYALL[0] + 36, 29, c, max_w=COPYALL[2] - 36 - 8)
        return False


# --------------------------------------------------------------------------- mini barra
def icon_qr(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.0)
    cr.set_dash([2, 1.5])
    cr.rectangle(.5, .5, 14, 14)
    cr.stroke()
    cr.set_dash([])
    for ox, oy in ((3, 3), (8.5, 3), (3, 8.5), (8.5, 8.5)):
        cr.rectangle(ox, oy, 3.5, 3.5)
        cr.stroke()


class MiniBar(Gtk.DrawingArea):
    def __init__(self, on_copy, on_qr):
        super().__init__()
        self.cb = dict(copy=on_copy, qr=on_qr)
        self.hover = None
        self.qr_enabled = False
        self.set_size_request(MINI_W, MINI_H)
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_has_tooltip(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.connect("draw", self._draw)
        self.connect("motion-notify-event", lambda _w, e: self._set(self._which(e.x, e.y)) or False)
        self.connect("leave-notify-event", lambda *a: self._set(None))
        self.connect("button-press-event", lambda *a: True)
        self.connect("button-release-event", self._release)
        self.connect("query-tooltip", self._tip)

    def _which(self, x, y):
        return "copy" if hit(MINI_COPY, x, y) else "qr" if hit(MINI_QR, x, y) and self.qr_enabled else None

    def _set(self, v):
        if v != self.hover:
            self.hover = v
            self.queue_draw()

    def _release(self, _w, ev):
        name = self._which(ev.x, ev.y)
        if ev.button == 1 and name:
            GLib.idle_add(lambda: (self.cb[name](), False)[1])
        return True

    def _tip(self, _w, x, y, _kb, tip):
        which = self._which(x, y)
        if which == "copy":
            tip.set_text(i18n.tr("Copiar texto (Ctrl + C)"))
            return True
        if which == "qr":
            tip.set_text(i18n.tr("Copiar o conteúdo do código QR"))
            return True
        return False

    def _draw(self, _w, cr):
        pal = theme.palette()
        round_path(cr, .5, .5, MINI_W - 1, MINI_H - 1, 8)
        cr.set_source_rgb(*rgb(pal["menu_bg"]))
        cr.fill_preserve()
        cr.set_source_rgb(*rgb(pal["sbar_border"]))
        cr.set_line_width(1)
        cr.stroke()
        for name, box in (("copy", MINI_COPY), ("qr", MINI_QR)):
            if self.hover == name:
                round_path(cr, *box, 4)
                cr.set_source_rgb(*rgb(pal["ov_hover"]))
                cr.fill()
        c = text_rgb()
        cr.save(); cr.translate(MINI_COPY[0] + 8, MINI_COPY[1] + 8); icon_copy(cr, c); cr.restore()
        cr.save(); cr.translate(MINI_QR[0] + 8, MINI_QR[1] + 8); icon_qr(cr, c if self.qr_enabled else muted(c)); cr.restore()
        return False


# --------------------------------------------------------------------------- cartões (aviso e toast)
def draw_card(cr, w, h, text, kind, dy=0.0, alpha=1.0):
    cr.save()
    cr.push_group()
    cr.translate(0, dy)
    round_path(cr, .5, .5, w - 1, h - 1, 8)
    cr.set_source_rgb(1, 1, 1) if not theme.is_dark() else cr.set_source_rgb(*rgb(theme.palette()["menu_bg"]))
    cr.fill_preserve()
    cr.set_source_rgb(*rgb(theme.palette()["sbar_border"] if kind == "check" else theme.palette()["menu_bg"] if theme.is_dark() else "#ffffff"))
    cr.set_line_width(1)
    cr.stroke()
    cx, cy = (25.5 if kind == "check" else 24.5), h / 2
    if kind == "check":
        cr.set_source_rgb(.059, .482, .059)                         # #0f7b0f
        cr.arc(cx - 6.5 + 7.5, cy, 7.5, 0, math.tau)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(1.3)
        cr.move_to(cx - 2.8, cy + .2); cr.line_to(cx - .8, cy + 2.2); cr.line_to(cx + 2.9, cy - 2.0)
        cr.stroke()
    else:
        cr.set_source_rgb(0, .47, .831)                             # #0078d4
        cr.arc(cx, cy, 7.5, 0, math.tau)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(cx - .65, cy - 4.4, 1.3, 1.5); cr.fill()
        cr.rectangle(cx - .65, cy - 2.0, 1.3, 5.6); cr.fill()
    draw_text(cr, text, 48 if kind == "info" else 47, cy + 5, (.106, .106, .106))
    cr.pop_group_to_source()
    cr.paint_with_alpha(alpha)
    cr.restore()


class Notice(Gtk.DrawingArea):
    """"Nenhum texto foi detectado": sobe com fade, fica ~3 s e desce com fade."""

    def __init__(self):
        super().__init__()
        self.text = ""
        self.t0 = None
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.set_size_request(NOTICE_W, CARD_H + RISE + 2)
        self.connect("draw", self._draw)
        self._id = 0

    def show_text(self, text, width=NOTICE_W):
        self.text = text
        self.set_size_request(width, CARD_H + RISE + 2)
        self.w = width
        self.t0 = time.monotonic()
        self.show()
        if not self._id:
            self._id = GLib.timeout_add(16, self._tick)
        self.queue_draw()

    def stop(self):
        self.t0 = None
        if self._id:
            GLib.source_remove(self._id)
            self._id = 0
        self.hide()

    def _state(self):
        if self.t0 is None:
            return None
        t = (time.monotonic() - self.t0) * 1000
        hold = HOLD_S * 1000 + APPEAR_MS
        if t < APPEAR_MS:
            f = t / APPEAR_MS
            return RISE * (1 - f), f
        if t < hold:
            return 0.0, 1.0
        if t < hold + LEAVE_MS:
            f = (t - hold) / LEAVE_MS
            return FALL * f, 1 - f
        return None

    def _tick(self):
        if self._state() is None:
            self._id = 0
            self.hide()
            return False
        self.queue_draw()
        return True

    def _draw(self, _w, cr):
        st = self._state()
        if st is not None:
            draw_card(cr, getattr(self, "w", NOTICE_W), CARD_H, self.text, "info", st[0] + 0.0, st[1])
        return False


class Toast(Gtk.Window):
    """"Texto copiado" no topo da tela, depois que a sobreposição fecha (janela própria, sem entrada)."""

    def __init__(self, text, monitor):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.text = text
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis is not None:
            self.set_visual(vis)
        self.set_decorated(False)
        self.set_accept_focus(False)
        self.set_keep_above(True)
        self.set_default_size(TOAST_W, TOAST_H + RISE + 2)
        self.set_size_request(TOAST_W, TOAST_H + RISE + 2)
        mx, my, mw, _mh = monitor
        self.move(mx + (mw - TOAST_W) // 2, my + TOAST_TOP)
        da = Gtk.DrawingArea()
        da.connect("draw", self._draw)
        self.add(da)
        self.t0 = time.monotonic()
        self.connect("realize", lambda w: w.get_window().input_shape_combine_region(cairo.Region(), 0, 0))
        self.show_all()
        GLib.timeout_add(16, self._tick)

    def _draw(self, _w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        t = (time.monotonic() - self.t0) * 1000
        hold = HOLD_S * 1000 + APPEAR_MS
        if t < APPEAR_MS:
            f = t / APPEAR_MS
            dy, a = RISE * (1 - f), f
        elif t < hold:
            dy, a = 0.0, 1.0
        else:
            f = min(1.0, (t - hold) / LEAVE_MS)
            dy, a = FALL * f, 1 - f
        draw_card(cr, TOAST_W, TOAST_H, self.text, "check", dy, a)
        return False

    def _tick(self):
        t = (time.monotonic() - self.t0) * 1000
        if t > HOLD_S * 1000 + APPEAR_MS + LEAVE_MS:
            self.destroy()
            return False
        self.queue_draw()
        return True


def show_toast(text, monitor):
    return Toast(text, monitor)


# --------------------------------------------------------------------------- sessão de texto
class TextSession:
    """Estado do extrator na sobreposição: retângulo escolhido, OCR, caixas e seleção de palavras (coordenadas de tela)."""

    def __init__(self, overlay):
        self.ov = overlay
        self.reset()

    def reset(self):
        self.phase = "none"            # none | scan | ready
        self.rect = None               # x0, y0, x1, y1 (tela)
        self.crop = None
        self.words = []
        self.lines = []
        self.sel = []
        self.anchor = None             # ponto (coords do recorte) onde o arrasto de texto começou
        self.dragging = False
        self.t0 = 0.0
        self.scan_end = 0.0
        self.job = 0
        self.result = None
        self.qr = []                   # textos dos códigos QR dentro da seleção

    # ---- início
    def start(self, rect):
        ov = self.ov
        x0, y0, x1, y1 = rect
        self.reset()
        self.rect = rect
        self.phase = "scan"
        self.t0 = time.monotonic()
        self.scan_end = self.t0 + MIN_SCAN
        crop = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0)
        c = cairo.Context(crop)
        c.set_source_surface(ov.surface, -x0, -y0)
        c.paint()
        self.crop = crop
        self.job += 1
        job = self.job
        ov.bar_ocr.set_copy_enabled(False)

        def work():
            try:
                codes = qr.decode(crop)
            except Exception:
                codes = []
            try:
                words = textlayer.ocr_surface(crop) if textlayer.services.ocr_available() else None
            except Exception:
                words = None
            GLib.idle_add(self._done, job, words, codes)
        threading.Thread(target=work, daemon=True).start()
        ov.start_anim()

    def _done(self, job, words, codes=()):
        if job != self.job or self.phase != "scan":
            return False
        self.qr = list(codes)
        if not words and self.qr:
            self.result = ("qr", [])                   # só código QR: não há caixas de texto, mas a seleção fica pronta
            self.scan_end = max(self.scan_end, self.t0 + MIN_SCAN)
        elif words is None:
            self.result = ("error", [])
        else:
            lines = textlayer.group_lines(words)
            self.result = ("ok" if words else "empty", words)
            self.scan_end = max(self.scan_end, self.t0 + MIN_SCAN + SCAN_PER_LINE * len(lines))
            self.words = words
        return False

    def tick(self):
        """Chamado a cada quadro; encerra a varredura quando o OCR terminou e o tempo mínimo passou."""
        if self.phase == "scan" and self.result is not None and time.monotonic() >= self.scan_end:
            kind, words = self.result
            if kind in ("ok", "qr"):
                self.phase = "ready"
                self.lines = textlayer.group_lines(words)
                self.ov.bar_ocr.set_copy_enabled(True)
                self.ov.text_ready()
            else:
                self.phase = "none"
                self.rect = None
                self.ov.text_empty("Nenhum texto foi detectado" if kind == "empty"
                                   else "Extrator de texto indisponível (instale o tesseract-ocr)")
        return self.phase == "scan"

    # ---- seleção de palavras (coordenadas do recorte)
    def local(self, x, y):
        return x - self.rect[0], y - self.rect[1]

    def inside(self, x, y):
        return self.phase == "ready" and self.rect[0] <= x < self.rect[2] and self.rect[1] <= y < self.rect[3]

    def begin_select(self, x, y):
        self.anchor = self.local(x, y)
        self.sel = []
        self.dragging = True

    def drag_select(self, x, y):
        if self.dragging:
            self.sel = textlayer.select_between(self.words, self.anchor, self.local(x, y))

    def end_select(self, x, y):
        self.dragging = False
        p = self.local(x, y)
        if abs(p[0] - self.anchor[0]) < 3 and abs(p[1] - self.anchor[1]) < 3:
            self.sel = []
        return bool(self.sel)

    def select_all(self):
        self.sel = list(self.words)

    def qr_text(self):
        return "\n".join(self.qr)

    def text(self, picked=None):
        words = self.sel if picked is None and self.sel else (self.words if picked is None else picked)
        t = textlayer.words_text(words)
        if settings["ocr_remove_breaks"]:
            t = " ".join(p.strip() for p in t.split("\n") if p.strip())
        return t

    # ---- desenho
    def draw(self, cr):
        """Desenha ANEL (varredura) ou CAIXAS + seleção (pronto) sobre a imagem já escurecida."""
        if self.phase == "scan":
            t = (time.monotonic() - self.t0) * 1000
            self.draw_ring(cr, self.rect, t)
        elif self.phase == "ready":
            self._draw_ready(cr)

    @staticmethod
    def draw_ring(cr, rect, t_ms):
        """Anel de 6 px (medido: 8 px para fora à esquerda, 7 em cima, 6 à direita e embaixo; cantos arredondados) com o gradiente
        cônico girando; o interior fica escurecido como o resto da tela."""
        x0, y0, x1, y1 = rect
        ox0, oy0, ox1, oy1 = x0 - 8, y0 - 7, x1 + 6, y1 + 6
        th = 6.0
        cr.save()
        round_path(cr, ox0, oy0, ox1 - ox0, oy1 - oy0, 7)
        round_path(cr, ox0 + th, oy0 + th, ox1 - ox0 - 2 * th, oy1 - oy0 - 2 * th, 2)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.clip()
        cx, cy = (ox0 + ox1) / 2, (oy0 + oy1) / 2
        far = math.hypot(ox1 - ox0, oy1 - oy0)
        phase = (130.0 + t_ms * 360.0 / text_anim.ROTATION_MS) % 360.0      # medido: azul na esquerda 155 ms depois de aparecer
        steps = 120
        for k in range(steps):
            a0, a1 = k * 360 / steps, (k + 1) * 360 / steps + .6
            cr.set_source_rgb(*text_anim.palette_color(a0 + 1.5 - phase))
            cr.move_to(cx, cy)
            cr.line_to(cx + far * math.cos(math.radians(a0)), cy + far * math.sin(math.radians(a0)))
            cr.line_to(cx + far * math.cos(math.radians(a1)), cy + far * math.sin(math.radians(a1)))
            cr.close_path()
            cr.fill()
        cr.restore()

    def _draw_ready(self, cr):
        x0, y0, x1, y1 = self.rect
        cr.save()
        cr.rectangle(x0 + INSET, y0 + INSET, x1 - x0 - INSET, y1 - y0 - INSET)     # medido: caixas recortadas 5 px dentro (esq./topo)
        cr.clip()
        cr.translate(x0, y0)
        for line in self.lines:
            bx0, by0, bx1, by1 = line.box
            cr.save()
            round_path(cr, bx0, by0, bx1 - bx0, by1 - by0, 4.0)
            cr.clip()
            cr.set_source_rgb(1, 1, 1)
            cr.paint()
            cr.set_source_surface(self.crop, 0, 0)
            cr.paint()
            cr.restore()
        for r in textlayer.sel_rects(self.sel):
            self._selection(cr, *r)
        cr.restore()
        self.ov.draw_locked_selection(cr, self.rect)

    def _selection(self, cr, x0, y0, x1, y1):
        cr.save()
        round_path(cr, x0, y0, x1 - x0, y1 - y0, 1.5)
        cr.clip()
        cr.push_group()
        cr.set_source_rgb(.698, .839, .949)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_source_surface(self.crop, 0, 0)
        cr.paint()
        light = cr.pop_group()
        cr.push_group()
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_DIFFERENCE)
        cr.set_source_surface(self.crop, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.set_source_rgb(.055, .196, .306)
        cr.paint()
        dark = cr.pop_group()
        cr.set_source(dark)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_ADD)
        cr.set_source(light)
        cr.paint()
        cr.restore()
