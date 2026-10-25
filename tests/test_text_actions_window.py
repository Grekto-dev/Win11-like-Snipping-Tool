import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from unittest.mock import patch
import cairo
from gi.repository import Gtk, GLib
import uuid
from gi.repository import Gio
from gtkapp import shared_app
from captura import theme
from captura.config import settings
from captura.window import EditorWindow
from captura.textlayer import Word


def drain(cond, timeout=3):
    end = time.monotonic() + timeout
    while time.monotonic() < end and not cond():
        GLib.MainContext.default().iteration(False); time.sleep(.005)
    return cond()


WORDS = [Word("Contato:", (10, 10, 70, 30), (1, 1, 1)),
         Word("ana@example.com", (80, 10, 220, 30), (1, 1, 1)),
         Word("Tel", (10, 50, 40, 70), (1, 1, 2)),
         Word("11999990000", (50, 50, 160, 70), (1, 1, 2))]


class TextActionsWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply


    def setUp(self):
        settings["theme"] = "light"
        theme.apply()
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 100)
        cr = cairo.Context(s); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.w.load_surface(s)
        self.copied = []
        p = patch("captura.window.services.copy_text", side_effect=self.copied.append); p.start(); self.addCleanup(p.stop)

    def enter(self, words=WORDS):
        with patch("captura.window.textlayer.ocr_surface", return_value=list(words)):
            self.w.btn_text.clicked()
            self.assertTrue(drain(lambda: self.w.canvas.tool == "text" or not self.w.btn_text.get_active()))

    def test_button_runs_ocr_and_enters_text_mode_with_actions(self):
        self.enter()
        self.assertEqual(self.w.canvas.tool, "text")
        self.assertTrue(self.w.btn_text.get_active())
        self.assertTrue(self.w.text_bar.get_visible())
        self.assertEqual(len(self.w.canvas.text_words), 4)

    def test_copy_all_text_keeps_line_breaks(self):
        self.enter()
        self.w.copy_all_text()
        self.assertEqual(self.copied, ["Contato: ana@example.com\nTel 11999990000"])

    def test_copy_selection_is_disabled_without_selection(self):
        self.enter()
        self.assertFalse(self.w.btn_copy_sel.get_sensitive())
        self.w.canvas.text_sel = [WORDS[1]]
        self.w.canvas.emit("changed")
        self.assertTrue(self.w.btn_copy_sel.get_sensitive())
        self.w.copy_selected_text()
        self.assertEqual(self.copied, ["ana@example.com"])

    def test_hide_sensitive_redacts_emails_and_phones_only(self):
        self.enter()
        n = self.w.hide_sensitive(("email", "phone"))
        self.assertEqual(n, 2)
        self.assertEqual(len(self.w.canvas.items), 2)
        self.assertEqual([w.text for w in self.w.canvas.text_words], ["Contato:", "Tel"])

    def test_no_text_found_leaves_text_mode_off(self):
        self.enter([])
        self.assertNotEqual(self.w.canvas.tool, "text")
        self.assertFalse(self.w.btn_text.get_active())
        self.assertFalse(self.w.text_bar.get_visible())

    def test_selecting_another_tool_or_second_click_leaves_text_mode(self):
        self.enter()
        self.w.btn_text.clicked()
        self.assertNotEqual(self.w.canvas.tool, "text")
        self.assertFalse(self.w.text_bar.get_visible())
        self.enter()
        self.w.select_tool("pen")
        self.assertEqual(self.w.canvas.tool, "pen")
        self.assertFalse(self.w.btn_text.get_active())
        self.assertFalse(self.w.text_bar.get_visible())


if __name__ == "__main__":
    unittest.main()
