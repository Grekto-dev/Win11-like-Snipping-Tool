"""Barra flutuante do overlay de captura (Win+Shift+S), medida no Windows 11 (1440x900).

Dois estados:
  main    330x48: [foto|vídeo] [forma ▾] [marcação rápida] | [conta-gotas] [extrator de texto] | [fechar]
  record  284x44: [● Iniciar] 00:00:00 [microfone] [áudio do sistema] | [fechar]   (modo vídeo, após selecionar a área)
Origem: x centrado no monitor, y = 13 px abaixo do topo.
"""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from . import icons, theme
from .config import settings

TOP = 13
MAIN_W, MAIN_H = 330, 48
REC_W, REC_H = 284, 44
BTN_Y, BTN_H = 8, 32

# (x, largura) relativos à barra principal
PHOTO = (8, 37)
VIDEO = (45, 39)
SHAPE = (96, 46)
MARKUP = (150, 36)
SEP1_X = 192
COLOR = (199, 36)
OCR = (239, 36)
SEP2_X = 281
CLOSE = (287, 36)
SEP_Y, SEP_H = 12, 24

# barra de gravação
START = (5, 6, 94, 32)
TIME_X = 109
MIC = (175, 6, 32, 32)
AUDIO = (207, 6, 32, 32)
REC_SEP_X = 243
REC_CLOSE = (250, 6, 32, 32)


def _btn(css, w, h):
    b = Gtk.Button()
    ctx = b.get_style_context()
    ctx.add_class("ov-btn")
    for c in css:
        ctx.add_class(c)
    b.set_size_request(w, h)
    b.set_can_focus(False)
    return b


class SnipBar(Gtk.EventBox):
    def __init__(self, handlers):
        super().__init__()
        self.h = handlers
        self.set_visible_window(True)
        self.get_style_context().add_class("ov-bar")
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)
        self.col = theme.icon_color()
        self.fx = Gtk.Fixed()
        self.add(self.fx)
        self.main = Gtk.Fixed()
        self.rec = Gtk.Fixed()
        self.fx.put(self.main, 0, 0)
        self.fx.put(self.rec, 0, 0)
        self._build_main()
        self._build_rec()
        self.show_main()

    # -------------------------------------------------------------- principal
    def _icon_btn(self, icon, tip, box, css=(), size=20):
        b = _btn(css, box[1], BTN_H)
        b.add(icons.image(icon, size, self.col))
        b.set_tooltip_text(tip)
        b.get_accessible().set_name(tip)
        self.main.put(b, box[0], BTN_Y)
        return b

    def _seg(self, icon, tip, box, active, on):
        b = Gtk.ToggleButton()
        ctx = b.get_style_context()
        ctx.add_class("ov-btn")
        ctx.add_class("ov-seg")
        b.set_size_request(box[1], BTN_H)
        b.set_can_focus(False)
        ov = Gtk.Overlay()
        ov.add(icons.image(icon, 20, self.col))
        ind = Gtk.Box()
        ind.get_style_context().add_class("ind-bar")
        ind.set_halign(Gtk.Align.CENTER)
        ind.set_valign(Gtk.Align.END)
        ind.set_opacity(1.0 if active else 0.0)
        ov.add_overlay(ind)
        b.add(ov)
        b.ind = ind
        b.set_active(active)
        b.set_tooltip_text(tip)
        b.get_accessible().set_name(tip)
        b.connect("toggled", lambda x: ind.set_opacity(1.0 if x.get_active() else 0.0))
        b.connect("clicked", lambda x: on() if x.get_active() else x.set_active(True))
        self.main.put(b, box[0], BTN_Y)
        return b

    def _build_main(self):
        h = self.h
        video = settings["mode"] == "video"
        self.btn_photo = self._seg("camera", "Captura de tela", PHOTO, not video, lambda: h["mode"]("photo"))
        self.btn_video = self._seg("video", "Gravação de tela", VIDEO, video, lambda: h["mode"]("video"))
        self.shape_btn = _btn([], SHAPE[1], BTN_H)
        self.shape_btn.set_tooltip_text("Modo de captura")
        self.shape_btn.get_accessible().set_name("Modo de captura")
        row = Gtk.Box(spacing=2)
        self.shape_img = Gtk.Image()
        row.pack_start(self.shape_img, False, False, 0)
        row.pack_start(icons.image("chevron_down", 12, self.col), False, False, 0)
        row.set_halign(Gtk.Align.CENTER)
        self.shape_btn.add(row)
        self.shape_btn.connect("clicked", lambda b: h["shape_menu"](b))
        self.main.put(self.shape_btn, SHAPE[0], BTN_Y)
        self.btn_markup = self._icon_btn("markup_img", "Marcação rápida (Ctrl+E)", MARKUP, ["ov-toggle"])
        self.btn_markup.connect("clicked", lambda b: h["markup"]())
        self._sep(self.main, SEP1_X)
        self.btn_color = self._icon_btn("eyedropper", "Seletor de cores", COLOR, ["ov-toggle"])
        self.btn_color.connect("clicked", lambda b: h["tool"]("color"))
        self.btn_ocr = self._icon_btn("textscan", "Extrator de Texto", OCR, ["ov-toggle"])
        self.btn_ocr.connect("clicked", lambda b: h["tool"]("ocr"))
        self._sep(self.main, SEP2_X)
        self.btn_close = self._icon_btn("close", "Fechar", CLOSE)
        self.btn_close.connect("clicked", lambda b: h["close"]())

    @staticmethod
    def _sep(fx, x):
        s = Gtk.Box()
        s.get_style_context().add_class("ov-sep")
        s.set_size_request(1, SEP_H)
        fx.put(s, x, SEP_Y)

    # -------------------------------------------------------------- gravação
    def _build_rec(self):
        h = self.h
        x, y, w, hh = START
        self.start_btn = _btn(["ov-start"], w, hh)
        row = Gtk.Box(spacing=8)
        row.set_halign(Gtk.Align.CENTER)
        row.pack_start(icons.image("ov_record", 20, theme.palette()["accent_text"]), False, False, 0)
        lb = Gtk.Label(label="Iniciar")
        row.pack_start(lb, False, False, 0)
        self.start_btn.add(row)
        self.start_btn.connect("clicked", lambda b: h["start"]())
        self.rec.put(self.start_btn, x, y)
        self.time_lbl = Gtk.Label(label="00:00:00")
        self.time_lbl.get_style_context().add_class("ov-time")
        self.rec.put(self.time_lbl, TIME_X, 12)
        self.btn_mic = self._toggle_icon(MIC, "mic_off", "mic_on", "Microfone", "rec_mic")
        self.btn_audio = self._toggle_icon(AUDIO, "screen_audio_off", "screen_audio", "Áudio do computador", "rec_system_audio")
        self._sep(self.rec, REC_SEP_X)
        c = _btn([], REC_CLOSE[2], REC_CLOSE[3])
        c.add(icons.image("close", 20, self.col))
        c.set_tooltip_text("Fechar")
        c.connect("clicked", lambda b: h["close"]())
        self.rec.put(c, REC_CLOSE[0], REC_CLOSE[1])
        self.rec_close = c

    def _toggle_icon(self, box, off, on, tip, key):
        x, y, w, hh = box
        b = _btn([], w, hh)
        b.set_tooltip_text(tip)
        b.get_accessible().set_name(tip)
        img = icons.image(on if settings[key] else off, 20, self.col)
        b.add(img)

        def clicked(_b):
            settings[key] = not settings[key]
            img.set_from_pixbuf(icons.pixbuf(on if settings[key] else off, 20, self.col))
        b.connect("clicked", clicked)
        self.rec.put(b, x, y)
        return b

    # -------------------------------------------------------------- estado
    def show_main(self):
        self.set_size_request(MAIN_W, MAIN_H)
        self.fx.set_size_request(MAIN_W, MAIN_H)
        self.main.show_all()
        self.main.set_no_show_all(False)
        self.rec.hide()
        self.rec.set_no_show_all(True)
        self.mode_name = "main"

    def show_record(self):
        self.set_size_request(REC_W, REC_H)
        self.fx.set_size_request(REC_W, REC_H)
        self.main.hide()
        self.main.set_no_show_all(True)
        self.rec.set_no_show_all(False)
        self.rec.show_all()
        self.mode_name = "record"

    def width(self):
        return REC_W if self.mode_name == "record" else MAIN_W

    def set_mode(self, mode):
        for b, m in ((self.btn_photo, "photo"), (self.btn_video, "video")):
            if b.get_active() != (m == mode):
                b.set_active(m == mode)
        self.btn_markup.set_sensitive(mode != "video")

    def set_tool(self, tool):
        for b, t in ((self.btn_color, "color"), (self.btn_ocr, "ocr")):
            b.get_style_context().remove_class("on")
            if tool == t:
                b.get_style_context().add_class("on")
