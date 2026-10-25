"""Barra de Formas dentro do conteúdo (como no Windows 11) e flyouts de Preencher/Contorno.

Todas as coordenadas vêm de medidas da referência (ver docs/VISUAL_QA_SHAPES_BAR.md): barra 486x48 centralizada,
botões 36x36 com passo de 40, ícones desenhados em pixels inteiros com traço de 1 px.
"""
import math
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
import cairo
from gi.repository import Gdk, Gtk, Pango, PangoCairo

from . import annot, theme
from .menus import Popup, SHADOW, anchor_origin

SQUIGGLE = [(33, 422.0), (51, 416.5), (69, 412.5), (87, 410.5), (105, 410.5), (123, 412.0), (141, 415.0),
            (159, 418.5), (177, 422.5), (195, 426.0), (213, 428.5), (231, 429.0), (249, 426.0), (267, 417.5), (275, 412.0)]

# ---- geometria da barra (relativa ao canto superior esquerdo da caixa externa, borda incluída)
BAR_W, BAR_H = 486, 48
BTN = 36
EMOJI_X = 6
KIND_X = {"rect": 55, "ellipse": 95, "line": 135, "arrow": 175}
SEP1_X, SEP2_X, SEP_Y, SEP_H = 48, 217, 12, 24
FILL_BOX = (224, 6, 128, 36)
OUTLINE_BOX = (354, 6, 126, 36)
BTN_Y = 6

# ---- flyouts de cor (interior; a borda de 1 px fica por fora)
FLY_W = 312
FILL_H, OUTLINE_H = 372, 495
SWATCH_R = 16
SWATCH_PITCH = 48
SWATCH0 = (36, 62)          # centros em coordenadas de aresta de pixel
TITLE_BASE, OPACITY_BASE, SIZE_BASE = 30, 307, 378
LABEL_X = 16
OPACITY_Y = 324          # topo da área do controle de opacidade (centro em 335)
PREVIEW_Y = 400
SLIDER_X, SLIDER_W = 17, 277      # trilho de 17 a 294 (medido), nos dois controles
SIZE_SCALE_Y = 446
SIZE_RANGE = (1, 24)
ALPHA_MIN = 0.01

SWATCHES = [None, "#000000", "#ffffff", "#d1d3d4", "#a7a9ac", "#808285"] + annot.PEN_COLORS[6:]
SWATCH_NAMES = (["Sem cor", "Preto", "Branco", "Prateado", "Cinza", "Cinza escuro"] +
                ["Magenta", "Vermelho", "Vermelho-alaranjado", "Laranja", "Dourado", "Amarelo",
                 "Verde-grama", "Verde", "Verde escuro", "Azul-petróleo", "Azul", "Índigo",
                 "Violeta", "Roxo", "Bege", "Marrom claro", "Marrom", "Marrom escuro",
                 "Rosa pastel", "Laranja pastel", "Amarelo pastel", "Verde pastel", "Azul pastel", "Roxo pastel"])


def rgb(h):
    return annot.hex_rgb(h)


def text_rgb():
    return rgb(theme.palette()["text"])


# ------------------------------------------------------------------ ícones (pixel exato)
def icon_smile(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.2)
    cr.arc(8, 8, 7.4, 0, math.tau)
    cr.stroke()
    for x in (5.4, 10.6):
        cr.arc(x, 6.6, 1.05, 0, math.tau)
        cr.fill()
    cr.set_line_width(1.2)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    cr.arc(8, 8, 4.4, math.radians(38), math.radians(142))
    cr.stroke()


def icon_rect(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1)
    r = 2.4
    x0, y0, x1, y1 = .5, .5, 13.5, 13.5
    cr.new_sub_path()
    cr.arc(x1 - r, y0 + r, r, -math.pi / 2, 0)
    cr.arc(x1 - r, y1 - r, r, 0, math.pi / 2)
    cr.arc(x0 + r, y1 - r, r, math.pi / 2, math.pi)
    cr.arc(x0 + r, y0 + r, r, math.pi, 1.5 * math.pi)
    cr.close_path()
    cr.stroke()


def icon_ellipse(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1)
    cr.arc(8, 8, 7.5, 0, math.tau)
    cr.stroke()


def icon_line(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.1)
    cr.move_to(.3, .3)
    cr.line_to(15.7, 15.7)
    cr.stroke()


def icon_arrow(cr, c):
    cr.set_source_rgb(*c)
    cr.set_line_width(1.1)
    cr.move_to(13.5, 13.5)
    cr.line_to(.6, .6)
    cr.stroke()
    cr.set_line_width(1.1)
    cr.move_to(.6, 7.6)
    cr.line_to(.6, .6)
    cr.line_to(7.6, .6)
    cr.stroke()


def icon_none(cr, c, size=15):
    cr.set_source_rgb(*c)
    cr.set_line_width(1)
    h = size / 2
    cr.arc(h, h, h - .5, 0, math.tau)
    cr.stroke()
    cr.set_line_width(1.1)
    d = h * .7
    cr.move_to(h - d, h + d)
    cr.line_to(h + d, h - d)
    cr.stroke()


def icon_ring(cr, color):
    """Anel na cor do contorno atual (16 px), com fio escuro nas bordas."""
    r, g, b = rgb(color)
    cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
    cr.arc(8, 8, 7.6, 0, math.tau)
    cr.new_sub_path()
    cr.arc(8, 8, 3.3, 0, math.tau)
    cr.set_source_rgb(r, g, b)
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, .42)
    cr.set_line_width(1)
    cr.stroke()


def icon_disc(cr, color):
    cr.arc(8, 8, 7.6, 0, math.tau)
    cr.set_source_rgb(*rgb(color))
    cr.fill_preserve()
    cr.set_source_rgba(0, 0, 0, .42)
    cr.set_line_width(1)
    cr.stroke()


def icon_chevron(cr, c):
    cr.set_source_rgba(*c, .88)
    cr.set_line_width(1.3)
    cr.move_to(.5, .4)
    cr.line_to(4, 3.9)
    cr.line_to(7.5, .4)
    cr.stroke()


KIND_ICONS = {"rect": (icon_rect, 14), "ellipse": (icon_ellipse, 16), "line": (icon_line, 16), "arrow": (icon_arrow, 14)}


_TEXT_OPTIONS = cairo.FontOptions()
_TEXT_OPTIONS.set_antialias(cairo.ANTIALIAS_GRAY)      # a referência usa cinza, sem franjas coloridas
_TEXT_OPTIONS.set_hint_style(cairo.HINT_STYLE_NONE)
_TEXT_OPTIONS.set_hint_metrics(cairo.HINT_METRICS_ON)


def draw_text(cr, text, x, baseline, c, weight=400):
    cr.set_font_options(_TEXT_OPTIONS)
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription(f"Selawik {'Semibold' if weight >= 600 else ''} 14px".replace("  ", " ")))
    layout.set_text(text, -1)
    ink, _ = layout.get_pixel_extents()
    cr.set_source_rgb(*c)
    cr.move_to(x - ink.x, baseline - layout.get_baseline() / Pango.SCALE)
    PangoCairo.show_layout(cr, layout)


# ------------------------------------------------------------------ botões
def _setup_button(btn, w, h, painter, label, plain):
    ctx = btn.get_style_context()
    ctx.add_class("sb-btn")
    if plain:
        ctx.add_class("sb-plain")
    btn.painter = painter
    btn.set_size_request(w, h)
    btn.set_can_focus(False)
    btn.set_tooltip_text(label)
    btn.get_accessible().set_name(label)
    area = Gtk.DrawingArea()
    area.set_size_request(w - 2, h - 2)

    def draw(_area, cr):
        cr.translate(-1, -1)          # a borda CSS de 1 px desloca a área de desenho
        painter(cr)
        return False
    area.connect("draw", draw)
    btn.add(area)
    area.show()               # o botão pode ficar com no_show_all; o desenho precisa estar visível
    btn.area = area


class SbToggle(Gtk.ToggleButton):
    """Geometria selecionável: borda de destaque quando ativa."""
    def __init__(self, w, h, painter, label):
        super().__init__()
        _setup_button(self, w, h, painter, label, plain=False)


class SbButton(Gtk.Button):
    """Botão de ação (Emoji, Preencher, Contorno): sem estado marcado."""
    def __init__(self, w, h, painter, label, plain=False):
        super().__init__()
        _setup_button(self, w, h, painter, label, plain)


class ShapeBar(Gtk.EventBox):
    """Caixa 486x48 com Emoji | geometrias | Preencher | Contorno."""

    def __init__(self, on_emoji, on_kind, on_fill, on_outline):
        super().__init__()
        self.set_visible_window(True)
        self.get_style_context().add_class("shapebar")
        self.set_size_request(BAR_W, BAR_H)
        self.set_halign(Gtk.Align.CENTER)
        self.set_valign(Gtk.Align.START)
        self.kind = "rect"
        self.fill = None
        self.outline = "#e61b1b"
        self._busy = False
        self._cb = (on_emoji, on_kind, on_fill, on_outline)
        fx = Gtk.Fixed()
        self.add(fx)

        def put(widget, x, y):
            fx.put(widget, x, y)               # EventBox não desloca o filho pela borda CSS

        self.emoji_btn = SbButton(BTN, BTN, lambda cr: self._icon(cr, icon_smile, 10, 10), "Emoji")
        self.emoji_btn.connect("clicked", lambda b: on_emoji(b))
        put(self.emoji_btn, EMOJI_X, BTN_Y)
        self.kind_btns = {}
        for key, label in (("rect", "Quadrado"), ("ellipse", "Oval"), ("line", "Linha reta"), ("arrow", "Seta")):
            fn, size = KIND_ICONS[key]
            off = (BTN - size) // 2
            b = SbToggle(BTN, BTN, lambda cr, fn=fn, off=off: self._icon(cr, fn, off, off), label)
            b.connect("toggled", self._kind_toggled, key)
            self.kind_btns[key] = b
            put(b, KIND_X[key], BTN_Y)
        self._busy = True
        self.kind_btns["rect"].set_active(True)      # estado inicial: sem notificar a janela
        self._busy = False
        for x in (SEP1_X, SEP2_X):
            sep = Gtk.Box()
            sep.get_style_context().add_class("sb-sep")
            sep.set_size_request(1, SEP_H)
            put(sep, x, SEP_Y)
        self.fill_btn = SbButton(FILL_BOX[2], FILL_BOX[3], self._paint_fill, "Preencher", plain=True)
        self.fill_btn.connect("clicked", lambda b: on_fill(b))
        put(self.fill_btn, FILL_BOX[0], FILL_BOX[1])
        self.outline_btn = SbButton(OUTLINE_BOX[2], OUTLINE_BOX[3], self._paint_outline, "Contorno", plain=True)
        self.outline_btn.connect("clicked", lambda b: on_outline(b))
        put(self.outline_btn, OUTLINE_BOX[0], OUTLINE_BOX[1])
        fx.show_all()

    # -- desenho
    @staticmethod
    def _icon(cr, fn, x, y):
        cr.save()
        cr.translate(x, y)
        fn(cr, text_rgb())
        cr.restore()

    def _paint_fill(self, cr):
        c = text_rgb()
        cr.save(); cr.translate(13, 11)
        if self.fill is None:
            icon_none(cr, c)
        else:
            icon_disc(cr, self.fill)
        cr.restore()
        draw_text(cr, "Preencher", 38, 23, c)
        cr.save(); cr.translate(107, 16); icon_chevron(cr, c); cr.restore()

    def _paint_outline(self, cr):
        c = text_rgb()
        cr.save(); cr.translate(13, 10)
        if self.outline is None:
            cr.translate(0, 1)
            icon_none(cr, c)
        else:
            icon_ring(cr, self.outline)
        cr.restore()
        draw_text(cr, "Contorno", 38, 23, c)
        cr.save(); cr.translate(105, 16); icon_chevron(cr, c); cr.restore()

    # -- estado
    def _kind_toggled(self, button, key):
        if self._busy:
            return
        self._busy = True
        try:
            if not button.get_active():
                button.set_active(True)          # um dos quatro sempre ativo
            else:
                self.set_kind(key, notify=True)
        finally:
            self._busy = False

    def set_kind(self, key, notify=False):
        self.kind = key
        was, self._busy = self._busy, True
        try:
            for k, b in self.kind_btns.items():
                b.set_active(k == key)
        finally:
            self._busy = was
        if notify:
            self._cb[1](key)

    def set_style(self, fill, outline):
        self.fill, self.outline = fill, outline
        self.fill_btn.area.queue_draw()
        self.outline_btn.area.queue_draw()

    def refresh(self):
        for w in [self.emoji_btn, self.fill_btn, self.outline_btn] + list(self.kind_btns.values()):
            w.area.queue_draw()


# ------------------------------------------------------------------ flyout de cores
class Swatch(Gtk.ToggleButton):
    def __init__(self, color, label):
        super().__init__()
        self.color = color
        self.get_style_context().add_class("palette-swatch")
        self.set_size_request(2 * SWATCH_R + 12, 2 * SWATCH_R + 12)
        self.set_can_focus(False)
        self.set_tooltip_text(label)
        self.get_accessible().set_name(label)
        area = Gtk.DrawingArea()
        area.set_size_request(2 * SWATCH_R + 12, 2 * SWATCH_R + 12)
        area.connect("draw", self._draw)
        self.add(area)
        self.connect("toggled", lambda *_: area.queue_draw())

    def _draw(self, area, cr):
        a = area.get_allocation()
        x, y = a.width / 2, a.height / 2
        pal = theme.palette()
        if self.color is None:
            cr.set_source_rgb(*text_rgb())
            cr.set_line_width(1.6)
            cr.arc(x, y, 14.2, 0, math.tau)
            cr.stroke()
            cr.move_to(x - 10, y + 10)
            cr.line_to(x + 10, y - 10)
            cr.stroke()
        else:
            cr.arc(x, y, SWATCH_R, 0, math.tau)
            cr.set_source_rgb(*rgb(self.color))
            cr.fill_preserve()
            if self.color.lower() in ("#ffffff",):
                cr.set_source_rgba(0, 0, 0, .12)       # branco precisa de contorno para não sumir
                cr.set_line_width(1)
                cr.stroke()
            else:
                cr.new_path()
        if self.get_active():
            cr.set_source_rgb(*rgb(pal["accent"]))
            cr.set_line_width(2)
            cr.arc(x, y, 18, 0, math.tau)
            cr.stroke()
        return False


class OpacitySlider(Gtk.DrawingArea):
    """Trilho xadrez com degradê da cor; polegar branco com ponto central. Valor 0..1."""
    H = 22
    TRACK_H = 12

    def __init__(self, width, on_change):
        super().__init__()
        self.set_size_request(width, self.H)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.set_can_focus(True)
        self.value = 1.0
        self.color = "#e61b1b"
        self.enabled = True
        self.on_change = on_change
        self._drag = False
        self.get_accessible().set_name("Opacidade")
        self.connect("draw", self._draw)
        self.connect("button-press-event", self._press)
        self.connect("motion-notify-event", self._motion)
        self.connect("button-release-event", lambda *_: setattr(self, "_drag", False) or True)
        self.connect("key-press-event", self._key)

    def _x_to_value(self, x):
        w = self.get_allocated_width()
        return min(1.0, max(0.0, (x - self.H / 2) / (w - self.H)))

    def _set(self, v):
        v = round(min(1.0, max(ALPHA_MIN, v)), 2)
        if v != self.value:
            self.value = v
            self.queue_draw()
            self.on_change(v)

    def _press(self, w, ev):
        if not self.enabled or ev.button != 1:
            return True
        self.grab_focus()
        self._drag = True
        self._set(self._x_to_value(ev.x))
        return True

    def _motion(self, w, ev):
        if self._drag:
            self._set(self._x_to_value(ev.x))
        return True

    def _key(self, w, ev):
        step = {Gdk.KEY_Left: -.05, Gdk.KEY_Down: -.05, Gdk.KEY_Right: .05, Gdk.KEY_Up: .05}.get(ev.keyval)
        if step is None or not self.enabled:
            return False
        self._set(self.value + step)
        return True

    def _draw(self, w, cr):
        a = self.get_allocation()
        pal = theme.palette()
        th = self.TRACK_H
        x0, x1 = self.H / 2, a.width - self.H / 2
        y0 = (a.height - th) / 2
        cr.save()
        r = th / 2
        cr.new_sub_path()
        cr.arc(x1, y0 + r, r, -math.pi / 2, math.pi / 2)
        cr.arc(x0, y0 + r, r, math.pi / 2, 1.5 * math.pi)
        cr.close_path()
        cr.clip()
        sq = 6
        for i in range(int((x1 - x0) // sq) + 2):
            for j in range(2):
                dark = (i + j) % 2 == 0
                cr.rectangle(x0 - r + i * sq, y0 + j * sq, sq, sq)
                cr.set_source_rgb(*(rgb("#cfcfcf") if dark else rgb(pal["menu_bg"])))
                cr.fill()
        if self.enabled:
            g = cairo.LinearGradient(x0, 0, x1, 0)
            cr.rectangle(x0 - r, y0, x1 - x0 + 2 * r, th)
            cr.set_source_rgba(*rgb(self.color), 0)
            g.add_color_stop_rgba(0, *rgb(self.color), 0)
            g.add_color_stop_rgba(1, *rgb(self.color), .95)
            cr.set_source(g)
            cr.fill()
        else:
            cr.rectangle(x0 - r, y0, x1 - x0 + 2 * r, th)
            cr.set_source_rgba(*rgb(pal["menu_bg"]), .55)
            cr.fill()
        cr.restore()
        cx = x0 + (x1 - x0) * self.value
        cy = a.height / 2
        cr.arc(cx, cy, self.H / 2 - .5, 0, math.tau)
        cr.set_source_rgb(*rgb("#ffffff" if not pal["dark"] else "#454545"))
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, .18)
        cr.set_line_width(1)
        cr.stroke()
        cr.arc(cx, cy, 4, 0, math.tau)
        cr.set_source_rgb(*rgb(pal["accent"] if self.enabled else "#c8c8c8"))
        cr.fill()
        return False


class ShapePreview(Gtk.DrawingArea):
    """Traço de exemplo na cor, opacidade e espessura atuais (curva medida da referência)."""
    def __init__(self, getter):
        super().__init__()
        self.getter = getter
        self.set_size_request(FLY_W, 50)
        self.connect("draw", self._draw)

    def _draw(self, w, cr):
        color, alpha, size = self.getter()
        if color is None:
            return False
        cr.translate(0, -PREVIEW_Y)
        pts = SQUIGGLE
        cr.move_to(*pts[0])
        for i in range(len(pts) - 1):
            p0, p1, p2, p3 = pts[max(0, i - 1)], pts[i], pts[i + 1], pts[min(len(pts) - 1, i + 2)]
            cr.curve_to(p1[0] + (p2[0] - p0[0]) / 6, p1[1] + (p2[1] - p0[1]) / 6,
                        p2[0] - (p3[0] - p1[0]) / 6, p2[1] - (p3[1] - p1[1]) / 6, *p2)
        cr.set_source_rgba(*rgb(color), alpha)
        cr.set_line_width(size)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()
        return False


class ShapeColorFlyout(Popup):
    """Preencher / Contorno: grade 6x5 de cores (a primeira é "sem cor"), opacidade e, no contorno, tamanho."""

    def __init__(self, anchor, mode, color, alpha, size, on_change):
        if mode not in ("fill", "outline"):
            raise ValueError(mode)
        self.anchor, self.mode = anchor, mode
        self.color, self.alpha, self.size = color, alpha, size
        self.on_change = on_change
        self._busy = False
        h = OUTLINE_H if mode == "outline" else FILL_H
        box = Gtk.Fixed()
        box.set_size_request(FLY_W, h)
        self.title = self._label(box, "Cores", TITLE_BASE, semibold=True)
        self.swatches = []
        for i, (c, name) in enumerate(zip(SWATCHES, SWATCH_NAMES)):
            s = Swatch(c, name)
            s.set_active(self._same(c, color))
            s.connect("toggled", self._swatch_toggled, c)
            cx = SWATCH0[0] + SWATCH_PITCH * (i % 6)
            cy = SWATCH0[1] + SWATCH_PITCH * (i // 6)
            box.put(s, int(cx - SWATCH_R - 6), int(cy - SWATCH_R - 6))
            self.swatches.append(s)
        self.opacity_label = self._label(box, "Opacidade", OPACITY_BASE, semibold=True,
                                         dim=lambda: not self.opacity.enabled)
        self.opacity = OpacitySlider(SLIDER_W, self._opacity_changed)
        self.opacity.value = alpha if color is not None else 0.0
        self.opacity.color = color or "#000000"
        self.opacity.enabled = color is not None
        box.put(self.opacity, SLIDER_X, OPACITY_Y)
        self.preview = None
        self.scale = None
        if mode == "outline":
            self._label(box, "Tamanho", SIZE_BASE, semibold=True)
            self.preview = ShapePreview(lambda: (self.color, self.alpha, self.size))
            box.put(self.preview, 0, PREVIEW_Y)
            self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, *SIZE_RANGE, 1)
            self.scale.get_style_context().add_class("palette-size")
            self.scale.set_size_request(SLIDER_W, 32)
            self.scale.set_draw_value(False)
            self.scale.set_value(size)
            self.scale.get_accessible().set_name("Tamanho do contorno")
            self.scale.connect("value-changed", self._size_changed)
            box.put(self.scale, SLIDER_X, SIZE_SCALE_Y)
        super().__init__(box, "wflyout2")

    @staticmethod
    def _same(a, b):
        return (a is None and b is None) or (a is not None and b is not None and a.lower() == b.lower())

    def _label(self, box, text, baseline, semibold=False, dim=None):
        lab = Gtk.DrawingArea()
        lab.set_size_request(FLY_W - 2 * LABEL_X, 20)

        def draw(w, cr):
            c = rgb(theme.palette()["disabled"]) if dim and dim() else text_rgb()
            draw_text(cr, text, 1, 15, c, 600)
            return False
        lab.connect("draw", draw)
        box.put(lab, LABEL_X, baseline - 15)
        return lab

    def popup(self):
        x, y = anchor_origin(self.anchor)
        # `y` da âncora é a do botão; a caixa externa da barra começa BTN_Y acima.
        bar_top = y - BTN_Y
        cx = x + self.anchor.get_allocated_width() / 2 + 1.5
        self.open_at(cx - (FLY_W + 2) / 2, bar_top + 44)

    def popdown(self):
        self.close_popup()

    def _emit(self):
        self.on_change(self.color, self.alpha, self.size)

    def _swatch_toggled(self, button, color):
        if self._busy:
            return
        self._busy = True
        if button.get_active():
            was_none = self.color is None
            self.color = color
            for s in self.swatches:
                s.set_active(s.color == color)
            self.opacity.enabled = color is not None
            if color is None:
                self.opacity.value = 0.0
            else:
                self.opacity.color = color
                if was_none:
                    self.alpha = 1.0
                self.opacity.value = self.alpha
            self.opacity.queue_draw()
            self.opacity_label.queue_draw()
            if self.preview:
                self.preview.queue_draw()
            self._emit()
        else:
            button.set_active(self._same(self.color, color))
        self._busy = False

    def _opacity_changed(self, value):
        self.alpha = value
        self._emit()

    def _size_changed(self, scale):
        self.size = int(scale.get_value())
        if self.preview:
            self.preview.queue_draw()
        self._emit()
