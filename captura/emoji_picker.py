"""Seletor de emojis (grade 6x3 de células 40x40, observada na Ferramenta de Captura do Windows 11)."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import GLib, Gtk, Pango, PangoCairo

from .menus import Popup

EMOJIS = ["❤", "⭐", "❓", "✔", "❌", "🔥",
          "👍", "👎", "👏", "🙌", "👀", "💯",
          "🙂", "😞", "😮", "😍", "😂", "😱"]
COLUMNS = 6
CELL = 40
GLYPH_PX = 13.6          # o glifo colorido ocupa ~16 px (medido na referência)


def draw_glyph(cr, char, cx, cy, px=GLYPH_PX):
    layout = PangoCairo.create_layout(cr)
    layout.set_font_description(Pango.FontDescription(f"Noto Color Emoji {px}px"))
    layout.set_text(char, -1)
    ink, logical = layout.get_pixel_extents()
    cr.move_to(cx - (ink.x + ink.width / 2), cy - (ink.y + ink.height / 2))
    PangoCairo.show_layout(cr, layout)


class EmojiPicker(Popup):
    def __init__(self, on_pick):
        grid = Gtk.Grid(column_spacing=0, row_spacing=0)
        self.buttons = []
        for i, char in enumerate(EMOJIS):
            b = Gtk.Button()
            b.get_style_context().add_class("emoji-cell")
            b.set_size_request(CELL, CELL)
            b.set_can_focus(False)
            b.set_tooltip_text(char)
            b.get_accessible().set_name(char)
            area = Gtk.DrawingArea()
            area.set_size_request(CELL, CELL)
            area.connect("draw", lambda w, cr, c=char: (draw_glyph(cr, c, CELL / 2, CELL / 2), False)[1])
            b.add(area)
            b.connect("clicked", self._picked, char)
            grid.attach(b, i % COLUMNS, i // COLUMNS, 1, 1)
            self.buttons.append(b)
        self._on_pick = on_pick
        super().__init__(grid, "wflyout2")

    def popup(self, bar_top, center_x):
        """Caixa externa 242x122: topo 52 px abaixo do topo da barra, centrada no botão Emoji."""
        w = COLUMNS * CELL + 2
        self.open_at(center_x - w / 2, bar_top + 52)

    def _picked(self, _button, char):
        self.close_popup()
        GLib.idle_add(lambda: (self._on_pick(char), GLib.SOURCE_REMOVE)[1])
