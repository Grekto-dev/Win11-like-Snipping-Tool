"""Ponteiros do overlay conforme medido no Windows: cruz em repouso, seta ao arrastar/varrer, I-beam ao arrastar texto, setas de redimensionar nas alças."""
import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
from gi.repository import Gdk, GLib

from gtkapp import shared_app
from captura import theme
from captura.config import settings
from captura.overlay import Overlay
from captura.textlayer import Word


def pump(sec=.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.004)


class CursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def make(self, tool):
        settings["mode"], settings["shape"] = "photo", "rectangle"
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)
        self.results = []
        ov = Overlay(surf, lambda k, p: self.results.append((k, p)), tool)
        ov.show_all()
        pump(.3)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        return ov

    def ev(self, x, y):
        return SimpleNamespace(x=x, y=y, button=1, state=0, type=Gdk.EventType.BUTTON_PRESS)

    def test_cross_at_rest_and_when_pressed_without_moving_then_arrow_once_dragging(self):
        ov = self.make("snip")
        self.assertEqual(ov._cursor_kind, "cross")
        ov.on_press(ov.da, self.ev(100, 100))
        self.assertEqual(ov._cursor_kind, "cross")
        ov.on_motion(ov.da, self.ev(150, 140))
        self.assertEqual(ov._cursor_kind, "arrow")
        ov.on_release(ov.da, self.ev(150, 140))

    def test_scan_ready_and_text_drag_cursors(self):
        ov = self.make("ocr")
        words = [Word("Olá", (20, 20, 70, 40), (1, 1, 1)), Word("mundo", (80, 20, 150, 40), (1, 1, 1))]
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            ov.on_press(ov.da, self.ev(10, 10)); ov.on_motion(ov.da, self.ev(300, 200)); ov.on_release(ov.da, self.ev(300, 200))
            self.assertEqual(ov._cursor_kind, "arrow")                     # varredura
            pump(1.4)
        self.assertEqual(ov.ts.phase, "ready")
        ov.on_motion(ov.da, self.ev(100, 100))
        self.assertEqual(ov._cursor_kind, "arrow")                         # sobre a seleção/texto: seta
        ov.on_press(ov.da, self.ev(30, 30))
        self.assertEqual(ov._cursor_kind, "arrow")
        ov.on_motion(ov.da, self.ev(120, 35))
        self.assertEqual(ov._cursor_kind, "text")                          # arrastando sobre o texto: I-beam
        ov.on_release(ov.da, self.ev(120, 35))
        self.assertEqual(ov._cursor_kind, "arrow")

    def test_handles_give_resize_cursors(self):
        ov = self.make("ocr")
        ov.ts.phase, ov.ts.rect = "ready", (100, 100, 400, 300)
        want = {(100, 200): "w", (400, 200): "e", (250, 100): "n", (250, 300): "s",
                (100, 100): "nw", (400, 300): "se", (400, 100): "ne", (100, 300): "sw"}
        for (x, y), h in want.items():
            self.assertEqual(ov.handle_at(x, y), h, (x, y))
        for (x, y), kind in {(100, 200): "w", (400, 100): "ne", (250, 300): "s"}.items():
            ov.on_motion(ov.da, self.ev(x, y))
            self.assertEqual(ov._cursor_kind, {"w": "w", "ne": "ne", "s": "s"}[kind])
        ov.on_motion(ov.da, self.ev(250, 200))
        self.assertEqual(ov._cursor_kind, "arrow")
        self.assertIsNone(ov.handle_at(250, 200))
        self.assertIsNone(ov.handle_at(20, 20))

    def test_dragging_a_side_handle_resizes_and_rescans(self):
        ov = self.make("ocr")
        words = [Word("Olá", (20, 20, 70, 40), (1, 1, 1))]
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            ov.on_press(ov.da, self.ev(10, 10)); ov.on_motion(ov.da, self.ev(300, 200)); ov.on_release(ov.da, self.ev(300, 200))
            pump(1.4)
            ov.on_press(ov.da, self.ev(300, 100))                          # alça da direita
            self.assertEqual(ov.ts.phase, "none")
            self.assertFalse(ov.bar_ocr.copy_enabled)
            ov.on_motion(ov.da, self.ev(450, 140))                         # y fica travado
            self.assertEqual(ov.sel, (10, 10, 450, 200))
            ov.on_release(ov.da, self.ev(450, 140))
            self.assertEqual(ov.ts.phase, "scan")
            self.assertEqual(ov.ts.rect, (10, 10, 450, 200))
            pump(1.4)
        self.assertTrue(ov.bar_ocr.copy_enabled)


if __name__ == "__main__":
    unittest.main()
