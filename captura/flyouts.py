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


class ShapeFlyout(Gtk.Popover):
    """Seletor horizontal observado no Windows: geometria | Preencher | Contorno.

    Os menus de cor são separados para a barra continuar compacta.
    Não há botão de emoji: essa ferramenta ainda não é implementada.
    """
    def __init__(self, relative_to, color, size, shape_kind, fill, on_change, on_emoji=None, emoji_selected=False):
        super().__init__(relative_to=relative_to)
        self.on_emoji = on_emoji
        self.get_style_context().add_class('cap-pop')
        self.color, self.size, self.shape_kind, self.fill = color, size, shape_kind, fill
        self.on_change = on_change
        self._busy = False
        self._child_pop = None
        self.set_position(Gtk.PositionType.BOTTOM)
        row = Gtk.Box(spacing=2)
        self.add(row)
        self.shape_btns = {}
        self.emoji_btn = Gtk.Button()
        self.emoji_btn.get_style_context().add_class('tbtn')
        self.emoji_btn.set_tooltip_text('Emoji')
        self.emoji_btn.add(icons.image('emoji', 20, theme.icon_color()))
        self.emoji_btn.connect('clicked', lambda b: self.on_emoji and self.on_emoji(b))
        row.pack_start(self.emoji_btn, False, False, 0)
        sep0 = Gtk.Box()
        sep0.get_style_context().add_class('sep')
        row.pack_start(sep0, False, False, 0)
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
        self.emoji_selected = emoji_selected
        self.outline_btn.set_sensitive(not emoji_selected)
        self.fill_btn.set_sensitive(shape_kind in ('rect', 'ellipse') and not emoji_selected)
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
            self.fill_btn.set_sensitive(key in ('rect', 'ellipse') and not self.emoji_selected)
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
