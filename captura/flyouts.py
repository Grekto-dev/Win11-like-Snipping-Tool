"""Flyouts (Popover) das ferramentas de marcação: cores + tamanho + pré-visualização."""
import math
import gi
gi.require_version("Gtk", "3.0")
import cairo
from gi.repository import Gtk, Gdk

from . import annot, icons, theme


class Preview(Gtk.DrawingArea):
    def __init__(self, getter, highlighter=False):
        super().__init__()
        self.getter = getter
        self.hl = highlighter
        self.set_size_request(-1, 54)
        self.connect("draw", self.on_draw)

    def on_draw(self, w, cr):
        col, size = self.getter()
        a = self.get_allocation()
        r, g, b = annot.hex_rgb(col)
        pal = theme.palette()
        cr.set_source_rgb(*annot.hex_rgb(pal["card"]))
        cr.paint()
        if self.hl:
            cr.set_source_rgb(0.62, 0.78, 0.95) if not pal["dark"] else cr.set_source_rgb(0.25, 0.4, 0.6)
            cr.rectangle(0, a.height / 2 - 11, a.width, 22)
            cr.fill()
        pts = []
        for i in range(0, 41):
            x = 14 + (a.width - 28) * i / 40
            y = a.height / 2 + math.sin(i / 40 * 2 * math.pi * 1.5) * (a.height * 0.2)
            pts.append((x, y))
        s = annot.Stroke("hl" if self.hl else "pen", pts, col, size)
        annot.draw_stroke(cr, s)
        return False


class ToolFlyout(Gtk.Popover):
    """kind: pen | hl | shape — chama on_change(cor, tamanho[, forma])."""

    def __init__(self, relative_to, kind, color, size, on_change, shape_kind=None):
        super().__init__(relative_to=relative_to)
        self.get_style_context().add_class("cap-pop")
        self.kind = kind
        self.color, self.size = color, size
        self.shape_kind = shape_kind
        self.on_change = on_change
        self.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        box.set_margin_top(14)
        box.set_margin_bottom(14)
        box.set_margin_start(16)
        box.set_margin_end(16)
        box.set_size_request(300, -1)
        self.add(box)
        pal = theme.palette()

        if kind == "shape":
            lab = Gtk.Label(label="Forma", xalign=0)
            lab.get_style_context().add_class("subtle")
            box.pack_start(lab, False, False, 0)
            row = Gtk.Box(spacing=4)
            self.shape_btns = {}
            for key, label, icon in annot.SHAPE_KINDS:
                b = Gtk.ToggleButton()
                b.get_style_context().add_class("tbtn")
                b.add(icons.image(icon, 20, pal["text"]))
                b.set_tooltip_text(label)
                b.set_active(key == shape_kind)
                b.connect("toggled", self._shape_toggled, key)
                row.pack_start(b, False, False, 0)
                self.shape_btns[key] = b
            box.pack_start(row, False, False, 0)

        lab = Gtk.Label(label="Cores", xalign=0)
        lab.get_style_context().add_class("subtle")
        box.pack_start(lab, False, False, 0)
        palette = annot.HL_COLORS if kind == "hl" else annot.PEN_COLORS
        grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        self.swatches = {}
        for i, c in enumerate(palette):
            b = Gtk.ToggleButton()
            b.get_style_context().add_class("swatch")
            b.set_size_request(30, 30)
            b.set_tooltip_text(c.upper())
            p = Gtk.CssProvider()
            p.load_from_data(f"button {{ background-color: {c}; background-image: none; }}".encode())
            b.get_style_context().add_provider(p, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            b.set_active(c.lower() == color.lower())
            b.connect("toggled", self._swatch_toggled, c)
            grid.attach(b, i % 6, i // 6, 1, 1)
            self.swatches[c] = b
        box.pack_start(grid, False, False, 0)

        lab = Gtk.Label(label="Tamanho", xalign=0)
        lab.get_style_context().add_class("subtle")
        box.pack_start(lab, False, False, 0)
        hi = {"pen": 20, "hl": 40, "shape": 20}[kind]
        lo = 1 if kind != "hl" else 4
        self.scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, lo, hi, 1)
        self.scale.set_draw_value(False)
        self.scale.set_value(size)
        self.scale.connect("value-changed", self._scale_changed)
        box.pack_start(self.scale, False, False, 0)
        if kind != "shape":
            self.preview = Preview(lambda: (self.color, self.size), kind == "hl")
            box.pack_start(self.preview, False, False, 0)
        else:
            self.preview = None
        box.show_all()

    def _swatch_toggled(self, b, c):
        if not b.get_active():
            if c.lower() == self.color.lower():
                b.handler_block_by_func(self._swatch_toggled)
                b.set_active(True)
                b.handler_unblock_by_func(self._swatch_toggled)
            return
        self.color = c
        for k, other in self.swatches.items():
            if other is not b and other.get_active():
                other.handler_block_by_func(self._swatch_toggled)
                other.set_active(False)
                other.handler_unblock_by_func(self._swatch_toggled)
        self._emit()

    def _shape_toggled(self, b, key):
        if not b.get_active():
            if key == self.shape_kind:
                b.handler_block_by_func(self._shape_toggled)
                b.set_active(True)
                b.handler_unblock_by_func(self._shape_toggled)
            return
        self.shape_kind = key
        for k, other in self.shape_btns.items():
            if other is not b and other.get_active():
                other.handler_block_by_func(self._shape_toggled)
                other.set_active(False)
                other.handler_unblock_by_func(self._shape_toggled)
        self._emit()

    def _scale_changed(self, s):
        self.size = int(s.get_value())
        self._emit()

    def _emit(self):
        if self.preview:
            self.preview.queue_draw()
        if self.kind == "shape":
            self.on_change(self.color, self.size, self.shape_kind)
        else:
            self.on_change(self.color, self.size)


class ShapeFlyout(Gtk.Popover):
    """Seletor horizontal observado no Windows: geometria | Preencher | Contorno.

    Os menus de cor são separados para a barra continuar compacta.
    Não há botão de emoji: essa ferramenta ainda não é implementada.
    """
    def __init__(self, relative_to, color, size, shape_kind, fill, on_change):
        super().__init__(relative_to=relative_to)
        self.get_style_context().add_class('cap-pop')
        self.color, self.size, self.shape_kind, self.fill = color, size, shape_kind, fill
        self.on_change = on_change
        self._busy = False
        self._child_pop = None
        self.set_position(Gtk.PositionType.BOTTOM)
        row = Gtk.Box(spacing=2)
        self.add(row)
        self.shape_btns = {}
        for key, label, icon in annot.SHAPE_KINDS:
            b = Gtk.ToggleButton()
            b.get_style_context().add_class('tbtn')
            b.set_tooltip_text(label)
            b.add(icons.image(icon, 20, theme.icon_color()))
            b.set_active(key == shape_kind)
            b.connect('toggled', self._shape_changed, key)
            self.shape_btns[key] = b
            row.pack_start(b, False, False, 0)
        sep = Gtk.Box()
        sep.get_style_context().add_class('sep')
        sep.set_valign(Gtk.Align.CENTER)
        row.pack_start(sep, False, False, 0)
        self.fill_btn = Gtk.Button(label='Preencher')
        self.outline_btn = Gtk.Button(label='Contorno')
        for b in (self.fill_btn, self.outline_btn):
            b.get_style_context().add_class('tbtn')
            row.pack_start(b, False, False, 0)
        self.fill_btn.set_sensitive(shape_kind in ('rect', 'ellipse'))
        self.fill_btn.connect('clicked', lambda b: self._colors(b, filling=True))
        self.outline_btn.connect('clicked', lambda b: self._colors(b, filling=False))
        row.show_all()

    def _shape_changed(self, b, key):
        if self._busy:
            return
        self._busy = True
        if not b.get_active():
            b.set_active(True)
        else:
            self.shape_kind = key
            for k, other in self.shape_btns.items():
                other.set_active(k == key)
            self.fill_btn.set_sensitive(key in ('rect', 'ellipse'))
            self._emit()
        self._busy = False

    def _emit(self):
        self.on_change(self.color, self.size, self.shape_kind, self.fill)

    def _colors(self, anchor, filling):
        if self._child_pop:
            self._child_pop.destroy()
        pop = Gtk.Popover.new(anchor)
        self._child_pop = pop
        pop.get_style_context().add_class('cap-pop')
        pop.set_position(Gtk.PositionType.BOTTOM)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        for margin in (box.set_margin_start, box.set_margin_end,
                       box.set_margin_top, box.set_margin_bottom):
            margin(10)
        pop.add(box)
        title = Gtk.Label(label='Preenchimento' if filling else 'Cor do contorno', xalign=0)
        box.pack_start(title, False, False, 0)
        if filling:
            none = Gtk.Button(label='Sem preenchimento')
            none.get_style_context().add_class('tbtn')
            none.connect('clicked', lambda *_: (self.choose_fill(None), pop.popdown()))
            box.pack_start(none, False, False, 0)
        grid = Gtk.Grid(column_spacing=6, row_spacing=6)
        box.pack_start(grid, False, False, 0)
        for i, color in enumerate(annot.PEN_COLORS):
            b = Gtk.ToggleButton()
            b.get_style_context().add_class('swatch')
            b.set_tooltip_text(color.upper())
            css = Gtk.CssProvider()
            css.load_from_data(f'button {{ background-color: {color}; background-image: none; }}'.encode())
            b.get_style_context().add_provider(css, Gtk.STYLE_PROVIDER_PRIORITY_USER + 5)
            b.set_active(color == (self.fill if filling else self.color))
            b.connect('clicked', lambda _b, c=color: self._choose_color(c, filling, pop))
            grid.attach(b, i % 6, i // 6, 1, 1)
        if not filling:
            box.pack_start(Gtk.Label(label='Espessura', xalign=0), False, False, 0)
            scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 20, 1)
            scale.set_value(self.size)
            scale.set_draw_value(True)
            scale.set_digits(0)
            scale.connect('value-changed', self._size_changed)
            box.pack_start(scale, False, False, 0)
        box.show_all()
        pop.popup()

    def _choose_color(self, color, filling, pop):
        if filling:
            self.choose_fill(color)
        else:
            self.color = color
            self._emit()
        pop.popdown()

    def choose_fill(self, color):
        self.fill = color
        self._emit()

    def _size_changed(self, scale):
        self.size = int(scale.get_value())
        self._emit()
