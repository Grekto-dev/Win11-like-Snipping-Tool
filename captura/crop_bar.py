"""Barra do modo de corte: Aplicar | Cancelar (centro) e Zoom (direita), medidos na referência do Windows 11.

Caixas (coordenadas de janela): Aplicar [401,486)x[38,70), Cancelar [486,581), Zoom [920,976); hover #eaeaea, raio 4.
"""
import math
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .shape_bar import _setup_button, draw_text, text_rgb, icon_chevron

APPLY_BOX = (401, 38, 85, 32)
CANCEL_BOX = (486, 38, 95, 32)
ZOOM_BOX = (920, 38, 56, 32)
TEXT_BASELINE = 21           # relativa ao topo do botão


def icon_check(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.1)
    cr.move_to(.5, 4.3)
    cr.line_to(4.2, 7.6)
    cr.line_to(11.5, .6)
    cr.stroke()


def icon_cross(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.1)
    cr.move_to(.4, .4); cr.line_to(10.6, 10.6)
    cr.move_to(10.6, .4); cr.line_to(.4, 10.6)
    cr.stroke()


def icon_zoom_in(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.1)
    cr.arc(5.9, 5.9, 5.3, 0, math.tau)
    cr.stroke()
    cr.move_to(3.2, 5.9); cr.line_to(8.6, 5.9)
    cr.move_to(5.9, 3.2); cr.line_to(5.9, 8.6)
    cr.stroke()
    cr.move_to(9.8, 9.8); cr.line_to(13.5, 13.5)
    cr.stroke()


def _at(cr, x, y, fn, c):
    cr.save(); cr.translate(x, y); fn(cr, c); cr.restore()


def paint_apply(cr):
    c = text_rgb()
    _at(cr, 11, 13, icon_check, c)
    draw_text(cr, "Aplicar", 33, TEXT_BASELINE, c, max_w=50)


def paint_cancel(cr):
    c = text_rgb()
    _at(cr, 11, 11, icon_cross, c)
    draw_text(cr, "Cancelar", 34, TEXT_BASELINE, c, max_w=55)


def paint_zoom(cr):
    c = text_rgb()
    _at(cr, 15, 9, icon_zoom_in, c)
    _at(cr, 36, 14, icon_chevron, c)


class CropButton(Gtk.Button):
    def __init__(self, box, painter, tooltip):
        super().__init__()
        _setup_button(self, box[2], box[3], painter, tooltip, plain=False)
        self.get_style_context().add_class("crop-btn")
        self.set_halign(Gtk.Align.START)
        self.set_valign(Gtk.Align.START)


def make_apply():
    return CropButton(APPLY_BOX, paint_apply, "Aplicar (Enter)")


def make_cancel():
    return CropButton(CANCEL_BOX, paint_cancel, "Cancelar (Esc)")


def make_zoom():
    return CropButton(ZOOM_BOX, paint_zoom, "Zoom")
