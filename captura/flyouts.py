"""Flyouts (Popover) das ferramentas de marcação: cores + tamanho + pré-visualização."""
import math
import gi
gi.require_version("Gtk", "3.0")
import cairo
from gi.repository import Gtk, Gdk

from . import annot, icons, theme


class Preview(Gtk.DrawingArea):
    """Compatibility preview used by the settings page."""
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
        annot.draw_stroke(cr, annot.Stroke("hl" if self.hl else "pen", pts, col, size))
        return False


from .tool_palette import ToolFlyout
