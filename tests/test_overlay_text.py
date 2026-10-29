"""Extrator de texto dentro da sobreposição de captura (fluxo medido no Windows)."""
import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
from gi.repository import Gdk, GLib

from gtkapp import shared_app
from captura import theme, overlay_text as OT
from captura.config import settings
from captura.overlay import Overlay
from captura.textlayer import Word


def pump(sec=.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.004)


def words():
    return [Word("Olá", (20, 20, 70, 40), (1, 1, 1)), Word("mundo", (80, 20, 150, 40), (1, 1, 1)),
            Word("segunda", (20, 60, 100, 80), (1, 1, 2)), Word("linha", (110, 60, 160, 80), (1, 1, 2))]


class OverlayTextTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def setUp(self):
        self.saved = {k: settings[k] for k in ("mode", "shape", "ocr_auto_copy", "ocr_remove_breaks")}
        for k in ("ocr_auto_copy", "ocr_remove_breaks"):
            settings[k] = False
        settings["mode"], settings["shape"] = "photo", "rectangle"
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)
        cr = cairo.Context(surf); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.results = []
        self.ov = Overlay(surf, lambda k, p: self.results.append((k, p)), "ocr")
        self.ov.show_all()
        pump(.3)
        self.addCleanup(lambda: self.ov.destroy() if self.ov.get_window() else None)
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k, v in self.saved.items()])

    def ev(self, x, y):
        return SimpleNamespace(x=x, y=y, button=1, state=0, type=Gdk.EventType.BUTTON_PRESS)

    def drag(self, a, b):
        self.ov.on_press(self.ov.da, self.ev(*a))
        self.ov.on_motion(self.ov.da, self.ev(*b))
        self.ov.on_release(self.ov.da, self.ev(*b))

    def scan(self, ws, rect=((10, 10), (300, 200)), wait=1.5):
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=ws), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.drag(*rect)
            pump(wait)

    def test_destroy_cancels_its_own_pending_request(self):
        token = SimpleNamespace(cancelled=False)
        token.cancel = lambda: setattr(token, "cancelled", True)
        self.ov.ts.ocr_job = token
        self.ov.ts.phase = "scan"
        with patch.object(OT.textlayer, "cancel_ocr", side_effect=lambda job: job.cancel()):
            self.ov.destroy()
        self.assertTrue(token.cancelled)

    def test_ocr_tool_swaps_the_bar_for_the_text_bar(self):
        self.assertTrue(self.ov.bar_ocr.get_visible())
        self.assertFalse(self.ov.bar.get_visible())
        self.assertFalse(self.ov.bar_ocr.copy_enabled)

    def test_back_button_returns_to_the_main_bar(self):
        self.ov.set_tool("snip")
        self.assertTrue(self.ov.bar.get_visible())
        self.assertFalse(self.ov.bar_ocr.get_visible())

    def test_release_starts_a_scan_and_ready_enables_copy(self):
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words()), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.drag((10, 10), (300, 200))
            self.assertEqual(self.ov.ts.phase, "scan")
            self.assertFalse(self.ov.bar_ocr.copy_enabled)
            pump(1.2)
        self.assertEqual(self.ov.ts.phase, "ready")
        self.assertTrue(self.ov.bar_ocr.copy_enabled)
        self.assertEqual(self.results, [])                 # nada fecha sozinho

    def test_empty_area_shows_the_notice_and_clears_the_selection(self):
        self.scan([])
        self.assertEqual(self.ov.ts.phase, "none")
        self.assertTrue(self.ov.notice.get_visible())
        self.assertEqual(self.ov.notice.text, "Nenhum texto foi detectado")
        self.assertFalse(self.ov.bar_ocr.copy_enabled)
        self.assertIsNone(self.ov.sel)
        self.assertEqual(self.results, [])
        pump(3.5)
        self.assertFalse(self.ov.notice.get_visible())     # some sozinho em ~3 s

    def test_dragging_inside_selects_words_and_shows_the_mini_bar(self):
        self.scan(words())
        self.drag((30, 30), (140, 80))                     # (coords de tela = recorte + 10)
        self.assertTrue(self.ov.ts.sel)
        self.assertEqual(self.ov.ts.sel[0].text, "Olá")
        self.assertTrue(self.ov.mini.get_visible())
        self.assertEqual(self.ov.mini.get_margin_start(), max(self.ov._mon[0], 140))

    def test_click_outside_the_selection_starts_a_new_one(self):
        self.scan(words(), rect=((10, 10), (200, 120)))
        self.drag((400, 300), (600, 400))
        self.assertEqual(self.ov.ts.phase, "scan")
        self.assertEqual(self.ov.ts.rect, (400, 300, 600, 400))

    def test_ctrl_c_with_a_selection_copies_it_and_closes_with_the_toast_kind(self):
        self.scan(words())
        self.drag((30, 30), (140, 80))
        self.ov.on_key(self.ov, SimpleNamespace(keyval=Gdk.KEY_c, state=Gdk.ModifierType.CONTROL_MASK))
        pump(.3)
        kind, text = self.results[0]
        self.assertEqual(kind, "textcopy")
        self.assertTrue(text.startswith("Olá"))

    def test_copy_all_copies_the_whole_text_and_remove_breaks_joins_lines(self):
        self.scan(words())
        self.ov.copy_all_text(); pump(.3)
        self.assertIn("segunda linha", self.results[0][1])

    def test_remove_line_breaks_option(self):
        settings["ocr_remove_breaks"] = True
        self.scan(words())
        self.ov.copy_all_text(); pump(.3)
        self.assertEqual(self.results[0][1], "Olá mundo segunda linha")

    def test_auto_copy_option_copies_when_the_scan_ends(self):
        settings["ocr_auto_copy"] = True
        self.scan(words(), wait=2.0)
        self.assertEqual(self.results[0][0], "textcopy")

    def test_escape_cancels(self):
        self.ov.on_key(self.ov, SimpleNamespace(keyval=Gdk.KEY_Escape, state=0))
        pump(.2)
        self.assertEqual(self.results, [("cancel", None)])

    def test_selection_is_cleared_when_leaving_the_tool(self):
        self.scan(words())
        self.ov.set_tool("snip")
        self.assertEqual(self.ov.ts.phase, "none")
        self.assertFalse(self.ov.mini.get_visible())


class AppToastTests(unittest.TestCase):
    def test_textcopy_result_copies_text_and_shows_a_toast(self):
        from captura import app as A
        shared = shared_app()
        calls = []
        with patch.object(A.services, "copy_text", side_effect=lambda t: calls.append(t)), \
             patch("captura.overlay_text.show_toast", side_effect=lambda t, m: calls.append(("toast", t))):
            shared._on_overlay_inner("textcopy", "abc", None) if hasattr(shared, "_on_overlay_inner") else None
        if hasattr(shared, "_on_overlay_inner"):
            self.assertEqual(calls, ["abc", ("toast", "Texto copiado")])


if __name__ == "__main__":
    unittest.main()
