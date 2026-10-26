"""Barra do modo Ações de texto (medida no Windows 11): Copiar todo o texto | Copiar como tabela | Redação rápida ▾.

Painel de 550x48 centrado, 6 px abaixo do topo do conteúdo. Ícones desenhados em pixels, como na barra de Formas.
"""
import math

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from . import theme
from .shape_bar import SbButton, draw_text, icon_chevron, rgb, text_rgb

BAR_W, BAR_H = 550, 48
BTN_Y, BTN_H = 6, 36
COPY_BOX = (8, BTN_Y, 164, BTN_H)
TABLE_BOX = (182, BTN_Y, 162, BTN_H)
SEP_X, SEP_Y, SEP_H = 354, 12, 24
REDACT_BOX = (363, BTN_Y, 142, BTN_H)
CHEV_BOX = (508, BTN_Y, 36, BTN_H)
ICON_Y = 11             # topo dos ícones dentro do botão
TEXT_BASE = 23          # linha de base dos rótulos dentro do botão


def _muted(c):
    """Cor de item desabilitado: 40 % da cor do texto sobre o fundo do painel."""
    bg = rgb(theme.palette()["menu_bg"])
    return tuple(c[i] * .4 + bg[i] * .6 for i in range(3))


def icon_copy(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.25)
    cr.move_to(5.2, 3.4)                               # peça de trás: só o "L" visível
    cr.curve_to(3.0, 3.4, 1.0, 3.4, 1.0, 5.4)
    cr.line_to(1.0, 11.6)
    cr.curve_to(1.0, 13.4, 1.6, 13.9, 3.4, 13.9)
    cr.line_to(8.2, 13.9)
    cr.stroke()
    cr.rectangle(5.6, .65, 8.2, 10.9)                  # peça da frente
    cr.stroke()


def icon_table(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.2)
    cr.rectangle(.6, .6, 12, 12)
    cr.stroke()
    for v in (4.6, 8.6):
        cr.move_to(v, .6); cr.line_to(v, 12.6)
        cr.move_to(.6, v); cr.line_to(12.6, v)
    cr.stroke()
    cr.move_to(13.6, 3.6); cr.line_to(13.6, 13.6); cr.line_to(3.6, 13.6)      # sombra deslocada (folha de trás)
    cr.stroke()


def icon_redact(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.25)
    cr.move_to(11.6, 5.2); cr.line_to(11.6, 13.2)
    cr.curve_to(11.6, 14.2, 11.0, 14.6, 10.2, 14.6)
    cr.line_to(2.6, 14.6)
    cr.curve_to(1.6, 14.6, 1.0, 14.0, 1.0, 13.0)
    cr.line_to(1.0, 2.6)
    cr.curve_to(1.0, 1.6, 1.6, 1.0, 2.6, 1.0)
    cr.line_to(8.0, 1.0)
    cr.stroke()
    cr.set_line_width(1.1)
    for (x0, x1, y) in ((3.2, 6.0, 4.6), (3.2, 6.4, 7.6), (3.2, 9.4, 10.8)):
        cr.move_to(x0, y); cr.line_to(x1, y)
    cr.stroke()
    cr.move_to(13.8, 0.7); cr.line_to(15.0, 1.9); cr.line_to(9.2, 7.8); cr.line_to(7.4, 8.4)   # lápis
    cr.line_to(8.0, 6.6); cr.close_path()
    cr.fill()


class TextBar(Gtk.EventBox):
    def __init__(self, on_copy_all, on_table, on_quick_redact, on_chevron):
        super().__init__()
        self.set_visible_window(True)
        self.get_style_context().add_class("shapebar")
        self.set_size_request(BAR_W, BAR_H)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        fx = Gtk.Fixed()
        self.add(fx)
        self.btn_copy_all = self._button(fx, COPY_BOX, "Copiar todo o texto", icon_copy, 9, 5, on_copy_all)
        self.btn_table = self._button(fx, TABLE_BOX, "Copiar como tabela", icon_table, 8, 5, on_table)
        self.btn_table.set_sensitive(False)
        sep = Gtk.Box()
        sep.get_style_context().add_class("sb-sep")
        sep.set_size_request(1, SEP_H)
        fx.put(sep, SEP_X, SEP_Y)
        self.btn_redact = self._button(fx, REDACT_BOX, "Redação rápida", icon_redact, 8, 5, on_quick_redact, dy=-1)
        self.btn_chev = SbButton(CHEV_BOX[2], CHEV_BOX[3], self._paint_chev, "Opções de redação", plain=False)
        self.btn_chev.connect("clicked", lambda b: on_chevron(b))
        fx.put(self.btn_chev, CHEV_BOX[0], CHEV_BOX[1])
        fx.show_all()

    def _button(self, fx, box, label, icon, ix, ix_off, cb, dy=0):
        x, y, w, h = box
        btn = SbButton(w, h, lambda cr, b=None: None, label, plain=False)

        def paint(cr, label=label, icon=icon):
            sensitive = btn.get_sensitive()
            c = text_rgb() if sensitive else _muted(text_rgb())
            cr.save(); cr.translate(ix, ICON_Y + dy); icon(cr, c); cr.restore()
            draw_text(cr, label, ix + 26, TEXT_BASE, c)
        btn.painter = paint
        btn.connect("clicked", lambda b: cb())
        btn.connect("state-flags-changed", lambda *_: btn.area.queue_draw())
        fx.put(btn, x, y)
        return btn

    @staticmethod
    def _paint_chev(cr):
        cr.set_source_rgb(*text_rgb())
        cr.set_line_width(1.1)
        cr.move_to(12.6, 15.6); cr.line_to(17.9, 20.9); cr.line_to(23.2, 15.6)
        cr.stroke()


class InfoTip(Gtk.DrawingArea):
    """Balão "Certifique-se…" que aparece sob a Redação rápida (314x62 + ponta de 8 px; medido)."""
    W, H, ARROW = 314, 62, 8

    def __init__(self, text):
        super().__init__()
        self.text = text
        self.set_size_request(self.W, self.H + self.ARROW)
        self.scale = 1.0
        self.connect("draw", self._draw)

    SCALE_CURVE = [(0, .30), (40, .36), (90, .85), (130, .98), (160, 1.0)]       # medido: abre crescendo a partir da ponta

    def pop(self):
        import time
        from gi.repository import GLib
        from . import menus
        if not menus.ANIMATE:
            self.scale = 1.0
            return
        t0 = time.monotonic()
        self.scale = self.SCALE_CURVE[0][1]

        def tick():
            t = (time.monotonic() - t0) * 1000
            keys = self.SCALE_CURVE
            if t >= keys[-1][0]:
                self.scale = 1.0
                self.queue_draw()
                return False
            for (t0_, v0), (t1_, v1) in zip(keys, keys[1:]):
                if t <= t1_:
                    self.scale = v0 + (v1 - v0) * (t - t0_) / (t1_ - t0_)
                    break
            self.queue_draw()
            return True
        GLib.timeout_add(16, tick)

    def _draw(self, _w, cr):
        import textwrap
        pal = theme.palette()
        a, W, H, R = self.ARROW, self.W - 1, self.H, 8
        if self.scale < 1.0:
            cr.translate(155.5, 0)
            cr.scale(self.scale, self.scale)
            cr.translate(-155.5, 0)
        x0, y0, x1, y1 = .5, a + .5, W - .5, a + H - .5
        cr.new_path()
        cr.move_to(x0 + R, y0)
        ax = 155.5
        cr.line_to(ax - 7, y0); cr.line_to(ax, y0 - 7.5); cr.line_to(ax + 7, y0)
        cr.line_to(x1 - R, y0)
        cr.arc(x1 - R, y0 + R, R, -math.pi / 2, 0)
        cr.arc(x1 - R, y1 - R, R, 0, math.pi / 2)
        cr.arc(x0 + R, y1 - R, R, math.pi / 2, math.pi)
        cr.arc(x0 + R, y0 + R, R, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(*rgb(pal["menu_bg"]))
        cr.fill_preserve()
        cr.set_source_rgb(*rgb(pal["sbar_border"]))
        cr.set_line_width(1)
        cr.stroke()
        c = text_rgb()
        cr.set_source_rgb(*c)                                  # ícone (i) em círculo
        cr.set_line_width(1.2)
        cr.arc(19.5, a + 31.5, 7, 0, math.tau); cr.stroke()
        cr.move_to(19.5, a + 28.5); cr.line_to(19.5, a + 28.7); cr.stroke()
        cr.move_to(19.5, a + 31.2); cr.line_to(19.5, a + 36); cr.stroke()
        for n, line in enumerate(("Certifique-se de que todas as informações", "confidenciais foram editadas.")):
            draw_text(cr, line, 40, a + 29 + n * 18, c)
        return False


class Notice(Gtk.DrawingArea):
    """Aviso informativo sob a barra de ferramentas (medido: 332x53, 83 px abaixo do topo, centrado)."""
    W, H, TOP = 332, 53, 4

    def __init__(self):
        super().__init__()
        self.text = ""
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.set_margin_top(self.TOP)
        self.set_size_request(self.W, self.H)
        self.connect("draw", self._draw)

    def set_text(self, text):
        self.text = text
        self.queue_draw()

    def _draw(self, _w, cr):
        pal = theme.palette()
        R = 8
        x0, y0, x1, y1 = .5, .5, self.W - .5, self.H - .5
        cr.new_path()
        cr.arc(x1 - R, y0 + R, R, -math.pi / 2, 0)
        cr.arc(x1 - R, y1 - R, R, 0, math.pi / 2)
        cr.arc(x0 + R, y1 - R, R, math.pi / 2, math.pi)
        cr.arc(x0 + R, y0 + R, R, math.pi, 3 * math.pi / 2)
        cr.close_path()
        cr.set_source_rgb(*rgb(pal["menu_bg"]))
        cr.fill_preserve()
        cr.set_source_rgb(*rgb(pal["sbar_border"]))
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(0, .47, .831)                     # #0078d4
        cr.arc(24.5, self.H / 2, 7.4, 0, math.tau)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(23.9, self.H / 2 - 4.2, 1.3, 1.5); cr.fill()
        cr.rectangle(23.9, self.H / 2 - 1.8, 1.3, 5.2); cr.fill()
        draw_text(cr, self.text, 48, self.H / 2 + 5, text_rgb())
        return False
