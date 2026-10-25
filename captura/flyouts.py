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
