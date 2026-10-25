"""Measured pen/highlighter palettes, drawn independently from observed geometry."""
import math
import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
import cairo
from gi.repository import Gtk

from . import annot, theme
from .menus import Popup, anchor_origin

PEN_NAMES = ['Preto', 'Branco', 'Prateado', 'Cinza', 'Cinza escuro', 'Carvão',
             'Magenta', 'Vermelho', 'Vermelho-alaranjado', 'Laranja', 'Dourado', 'Amarelo',
             'Verde-grama', 'Verde', 'Verde escuro', 'Azul-petróleo', 'Azul', 'Índigo',
             'Violeta', 'Roxo', 'Bege', 'Marrom claro', 'Marrom', 'Marrom escuro',
             'Rosa pastel', 'Laranja pastel', 'Amarelo pastel', 'Verde pastel', 'Azul pastel', 'Roxo pastel']
HL_NAMES = ['Amarelo', 'Verde', 'Azul claro', 'Rosa', 'Vermelho-alaranjado', 'Violeta']


class ColorSwatch(Gtk.ToggleButton):
    """36 px circle in a 40 px hit target; selected ring is independent of the color."""
    def __init__(self, color, label):
        super().__init__()
        self.color = color
        self.get_style_context().add_class('palette-swatch')
        self.set_size_request(40, 40)
        self.set_tooltip_text(label)
        self.get_accessible().set_name(label)
        area = Gtk.DrawingArea()
        area.set_size_request(40, 40)
        area.connect('draw', self._draw_color)
        self.add(area)
        self.connect('toggled', lambda *_: area.queue_draw())

    def _draw_color(self, area, cr):
        a = area.get_allocation()
        x, y = a.width / 2, a.height / 2
        cr.set_source_rgb(*annot.hex_rgb(self.color))
        cr.arc(x, y, 18, 0, math.tau)
        cr.fill()
        if self.get_active():
            # The light gap leaves white / black swatches readable in either theme.
            cr.set_source_rgb(*annot.hex_rgb(theme.palette()['menu_bg']))
            cr.set_line_width(2)
            cr.arc(x, y, 18, 0, math.tau)
            cr.stroke()
            cr.set_source_rgb(*annot.hex_rgb(theme.palette()['text']))
            cr.set_line_width(1.5)
            cr.arc(x, y, 19, 0, math.tau)
            cr.stroke()
        return False


class StrokePreview(Gtk.DrawingArea):
    """Same single-wave sample for both brushes; no extra blue backing stripe."""
    CENTERS = [(23,35), (33,28), (53,19), (73,14), (93,12.5), (113,14.5),
               (133,20), (153,27.5), (173,33.5), (193,36.5), (213,36),
               (233,32.5), (253,26), (273,14)]

    def __init__(self, getter, highlighter=False):
        super().__init__()
        self.getter = getter
        self.highlighter = highlighter
        self.set_size_request(296, 80)
        self.connect('draw', self.on_draw)

    @staticmethod
    def _curve(cr, points, start=True):
        if start:
            cr.move_to(*points[0])
        for i in range(len(points)-1):
            p0 = points[max(0, i-1)]
            p1, p2 = points[i], points[i+1]
            p3 = points[min(len(points)-1, i+2)]
            cr.curve_to(p1[0]+(p2[0]-p0[0])/6, p1[1]+(p2[1]-p0[1])/6,
                        p2[0]-(p3[0]-p1[0])/6, p2[1]-(p3[1]-p1[1])/6, *p2)

    def on_draw(self, widget, cr):
        color, size = self.getter()
        cr.set_source_rgb(*annot.hex_rgb(color))
        points = [(x, y+10) for x,y in self.CENTERS] if self.highlighter else self.CENTERS
        if self.highlighter:
            top = [(x,y-size/2) for x,y in points]
            bottom = [(x,y+size/2) for x,y in reversed(points)]
            self._curve(cr, top)
            cr.line_to(*bottom[0])
            self._curve(cr, bottom, start=False)
            cr.close_path()
            cr.fill()
        else:
            self._curve(cr, points)
            cr.set_line_width(size)
            cr.set_line_cap(cairo.LINE_CAP_ROUND)
            cr.stroke()
        return False


class ToolFlyout(Popup):
    def __init__(self, relative_to, kind, color, size, on_change, shape_kind=None):
        if kind not in ('pen', 'hl'):
            raise ValueError('ToolFlyout supports pen and hl; shapes use shape_bar.ShapeColorFlyout')
        self.anchor = relative_to
        self.kind = kind
        self.color = color
        self.size = size
        self.on_change = on_change
        self._busy = False
        box = Gtk.Fixed()
        box.set_size_request(320, 454 if kind == 'pen' else 286)
        title = Gtk.Label(label='Cores', xalign=0)
        title.set_size_request(296, 20)
        box.put(title, 12, 8)
        colors = annot.PEN_COLORS if kind == 'pen' else annot.HL_COLORS
        labels = PEN_NAMES if kind == 'pen' else HL_NAMES
        self.swatches = {}
        for i, (c, label) in enumerate(zip(colors, labels)):
            swatch = ColorSwatch(c, label)
            swatch.set_active(c.lower() == color.lower())
            swatch.connect('toggled', self._color_toggled, c)
            box.put(swatch, 10 + 52*(i % 6), 44 + 52*(i // 6))
            self.swatches[c] = swatch
        size_y = 314 if kind == 'pen' else 106
        lab = Gtk.Label(label='Tamanho', xalign=0)
        lab.set_size_request(296, 20)
        box.put(lab, 12, size_y)
        self.preview = StrokePreview(lambda: (self.color, self.size), kind == 'hl')
        box.put(self.preview, 12, 337 if kind == 'pen' else 139)
        lo, hi = (1, 24) if kind == 'pen' else (12, 64)
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        self.scale.get_style_context().add_class('palette-size')
        self.scale.set_size_request(296, 32)
        self.scale.set_draw_value(False)
        self.scale.set_value(size)
        self.size = int(self.scale.get_value())
        self.scale.get_accessible().set_name('Tamanho da Caneta')
        self.scale.connect('value-changed', self._size_changed)
        box.put(self.scale, 12, 398 if kind == 'pen' else 230)
        super().__init__(box, 'wflyout')

    def popup(self):
        x, y = anchor_origin(self.anchor)
        self.open_at(x + self.anchor.get_allocated_width()/2 - 159, y + self.anchor.get_allocated_height() + 8)

    def popdown(self):
        self.close_popup()

    def _color_toggled(self, button, color):
        if self._busy:
            return
        self._busy = True
        if button.get_active():
            self.color = color
            for c, other in self.swatches.items():
                other.set_active(c == color)
            self._emit()
        else:
            button.set_active(self.color.lower() == color.lower())
        self._busy = False

    def _size_changed(self, scale):
        self.size = int(scale.get_value())
        self._emit()

    def _emit(self):
        self.preview.queue_draw()
        self.on_change(self.color, self.size)
