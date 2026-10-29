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
        old = settings["shot_autocopy_edits"]; settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", old))
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
            self.assertTrue(drain(lambda: (self.w.canvas.tool == "text" and not self.w.canvas.text_scanning() and bool(self.w.canvas.text_words)) or not self.w.btn_text.get_active(), 4))

    def test_leaving_before_worker_start_cancels_the_precreated_request(self):
        with patch("captura.window.threading.Thread") as thread:
            self.w.btn_text.set_active(True)
            token = self.w._text_job
            target = thread.call_args.kwargs["target"]
            self.w.btn_text.set_active(False)
            self.assertTrue(getattr(token, "cancelled", False))
            with patch("captura.ocr_engine.Proc.call", side_effect=AssertionError("cancelled job reached a worker")):
                target()

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

    def test_copy_selected_text_only_copies_the_selection(self):
        self.enter()
        self.assertFalse(self.w.copy_selected_text())
        self.w.canvas.text_sel = [WORDS[1]]
        self.assertTrue(self.w.copy_selected_text())
        self.assertEqual(self.copied, ["ana@example.com"])

    def test_bar_has_the_windows_buttons_and_table_is_disabled(self):
        self.enter()
        labels = [b.get_tooltip_text() for b in (self.w.btn_copy_all, self.w.btn_table, self.w.btn_redact)]
        self.assertEqual(labels, ["Copiar todo o texto", "Copiar como tabela", "Redação rápida"])
        self.assertFalse(self.w.btn_table.get_sensitive())

    def test_quick_redact_uses_the_checked_kinds_and_shows_the_tip(self):
        self.enter()
        settings["redact_phones"] = False
        self.addCleanup(lambda: settings.__setitem__("redact_phones", True))
        self.w.btn_redact.clicked()
        self.assertEqual(len(self.w.canvas.items), 1)                 # só o e-mail
        self.assertTrue(self.w.canvas.has_redactions())

    def test_ctrl_r_redacts_the_selection_in_text_mode(self):
        self.enter()
        self.w.canvas.text_sel = [WORDS[1]]
        self.w.redact_selected_text()
        self.assertEqual(len(self.w.canvas.items), 1)
        self.assertEqual(self.w.canvas.text_sel, [])

    def test_hide_sensitive_redacts_emails_and_phones_only(self):
        self.enter()
        n = self.w.hide_sensitive(("email", "phone"))
        self.assertEqual(n, 2)
        self.assertEqual(len(self.w.canvas.items), 2)               # uma tarja por linha
        self.assertEqual(len(self.w.canvas.text_words), 4)

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
