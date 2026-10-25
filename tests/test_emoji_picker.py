import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
import cairo
from gi.repository import Gtk, GLib
from gtkapp import shared_app
from captura import theme, annot
from captura.config import settings
from captura.emoji_picker import EMOJIS, EmojiPicker
from captura.window import EditorWindow


def drain(sec=.15):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.002)


class EmojiPickerTests(unittest.TestCase):
    def setUp(self):
        settings["theme"] = "light"; theme.apply()
        old = settings["shot_autocopy_edits"]; settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", old))
        self.app = shared_app(); self.app.apply_theme = theme.apply
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        self.w.show(); drain()
        self.w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200))
        self.w.select_tool("shape")

    def test_catalog_matches_observed_windows_grid(self):
        self.assertEqual(len(EMOJIS), 18)
        self.assertEqual("".join(EMOJIS[:6]), "❤⭐❓✔❌🔥")

    def test_picker_has_six_columns_and_three_rows_of_real_buttons(self):
        got = []
        p = EmojiPicker(got.append)
        buttons = p.buttons
        self.assertEqual(len(buttons), 18)
        p.show(); drain()
        xs = sorted({b.get_allocation().x for b in buttons})
        ys = sorted({b.get_allocation().y for b in buttons})
        self.assertEqual((len(xs), len(ys)), (6, 3))
        buttons[5].clicked(); drain()
        self.assertEqual(got, ["🔥"])
        p.destroy()

    def test_shape_flyout_emoji_button_inserts_selected_emoji_and_disables_fill(self):
        self.w.popup_flyout(self.w.btn_shape, "shape")
        fl = self.w._tool_pop
        self.assertTrue(hasattr(fl, "emoji_btn"))
        fl.emoji_btn.clicked(); drain()
        picker = self.w._emoji_picker
        picker.buttons[1].clicked(); drain(.4)
        self.assertEqual([i.kind for i in self.w.canvas.items], ["emoji"])
        self.assertEqual(self.w.canvas.items[0].char, "⭐")
        self.assertIs(self.w.canvas.sel, self.w.canvas.items[0])
        self.w.popup_flyout(self.w.btn_shape, "shape")
        self.assertFalse(self.w._tool_pop.fill_btn.get_sensitive())


if __name__ == "__main__":
    unittest.main()
