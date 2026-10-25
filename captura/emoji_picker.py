"""Seletor de emojis (grade 6×3 observada na Ferramenta de Captura do Windows 11)."""
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk

from .menus import Popup

EMOJIS = ["❤", "⭐", "❓", "✔", "❌", "🔥",
          "👍", "👎", "👏", "🙌", "👀", "💯",
          "🙂", "😞", "😮", "😍", "😂", "😱"]
COLUMNS = 6


class EmojiPicker(Popup):
    def __init__(self, on_pick):
        grid = Gtk.Grid(column_spacing=0, row_spacing=0)
        grid.set_margin_start(2); grid.set_margin_end(2); grid.set_margin_top(4); grid.set_margin_bottom(4)
        self.buttons = []
        for i, char in enumerate(EMOJIS):
            b = Gtk.Button()
            b.get_style_context().add_class("tbtn")
            b.get_style_context().add_class("emoji-cell")
            lab = Gtk.Label()
            lab.set_markup(f'<span font_family="Noto Color Emoji" size="15360">{char}</span>')
            b.add(lab)
            b.set_size_request(40, 40)
            b.set_can_focus(False)
            b.set_tooltip_text(char)
            b.connect("clicked", self._picked, char)
            grid.attach(b, i % COLUMNS, i // COLUMNS, 1, 1)
            self.buttons.append(b)
        self._on_pick = on_pick
        super().__init__(grid, "wflyout")

    def _picked(self, _button, char):
        self.close_popup()
        GLib.idle_add(lambda: (self._on_pick(char), GLib.SOURCE_REMOVE)[1])
