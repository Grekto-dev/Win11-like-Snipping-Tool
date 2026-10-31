"""Ponteiros do overlay conforme medido no Windows: cruz em repouso, seta ao arrastar/varrer, I-beam ao arrastar texto, setas de redimensionar nas alças."""
import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
import hashlib
import os
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

    def make(self, tool, shape="rectangle"):
        settings["mode"], settings["shape"] = "photo", shape
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

    # ---- modos e barra de ferramentas: a cruz só existe fora da barra e nos modos retângulo e forma livre ----
    def bar_center(self, ov):
        bar = ov.bar
        x, y = bar.translate_coordinates(ov, bar.get_allocated_width() // 2, bar.get_allocated_height() // 2)
        return int(x), int(y)

    def test_cross_only_in_rectangle_and_freeform_modes_arrow_in_window_and_fullscreen(self):
        for shape, kind in (("rectangle", "cross"), ("freeform", "cross"), ("window", "arrow"), ("fullscreen", "arrow")):
            ov = self.make("snip", shape)
            self.assertEqual(ov._wanted_cursor(400, 400), kind, shape)
            self.assertEqual(ov._cursor_kind, kind, shape)

    def test_text_extractor_keeps_the_cross_at_rest_whatever_the_remembered_shape(self):
        for shape in ("rectangle", "window", "fullscreen"):
            self.assertEqual(self.make("ocr", shape)._wanted_cursor(400, 400), "cross", shape)

    def test_the_toolbar_always_gets_the_arrow_in_every_mode_and_tool(self):
        for tool in ("snip", "color"):
            for shape in ("rectangle", "freeform", "window", "fullscreen"):
                ov = self.make(tool, shape)
                bx, by = self.bar_center(ov)
                self.assertEqual(ov._wanted_cursor(bx, by), "arrow", (tool, shape))

    def test_the_cursor_follows_the_real_pointer_after_a_change_made_while_it_rests_on_the_toolbar(self):
        ov = self.make("snip", "window")
        bx, by = self.bar_center(ov)
        with patch.object(ov, "_pointer_now", return_value=(bx, by)):
            ov.set_shape("rectangle")                         # escolher o modo no menu deixa o ponteiro sobre a barra
            self.assertEqual(ov._cursor_kind, "arrow")
            ov.set_shape("freeform")
            self.assertEqual(ov._cursor_kind, "arrow")
        with patch.object(ov, "_pointer_now", return_value=(400, 400)):
            ov.update_cursor()                                # ao sair da barra volta o que o modo pede
            self.assertEqual(ov._cursor_kind, "cross")
            ov.set_shape("fullscreen")
            self.assertEqual(ov._cursor_kind, "arrow")

    def test_the_toolbar_arrow_survives_a_tool_switch_and_returns_to_the_mode_cursor_when_leaving(self):
        ov = self.make("snip", "rectangle")
        bx, by = self.bar_center(ov)
        with patch.object(ov, "_pointer_now", return_value=(bx, by)):
            ov.update_cursor()
            self.assertEqual(ov._cursor_kind, "arrow")
        with patch.object(ov, "_pointer_now", return_value=(300, 300)):
            ov.update_cursor()
            self.assertEqual(ov._cursor_kind, "cross")

    def test_press_without_moving_keeps_the_mode_cursor_then_arrow_once_dragging(self):
        ov = self.make("snip", "freeform")
        ov.on_press(ov.da, self.ev(100, 100))
        self.assertEqual(ov._cursor_kind, "cross")
        ov.on_motion(ov.da, self.ev(150, 140))
        self.assertEqual(ov._cursor_kind, "arrow")
        ov.on_release(ov.da, self.ev(150, 140))


HAVE_XFIXES = False
if os.environ.get("DISPLAY"):
    try:
        from Xlib import display as xdisplay, X
        from Xlib.ext import xtest, xfixes
        _d = xdisplay.Display()
        HAVE_XFIXES = bool(_d.query_extension("XFIXES").present)
        if HAVE_XFIXES:
            xfixes.query_version(_d)
    except Exception:
        HAVE_XFIXES = False


@unittest.skipUnless(HAVE_XFIXES, "precisa de DISPLAY com XFIXES e python-xlib")
class RealPointerTests(unittest.TestCase):
    """O cursor X de verdade (XFixes) com movimento XTEST, não só o estado interno do overlay."""

    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def sig(self):
        _d.sync()
        img = _d.xfixes_get_cursor_image(_d.screen().root)
        return img.width, hashlib.md5(str(list(img.cursor_image)).encode()).hexdigest()

    def move(self, x, y):
        xtest.fake_input(_d, X.MotionNotify, x=int(x), y=int(y))
        _d.sync()
        pump(.25)

    def make(self, shape):
        settings["mode"], settings["shape"] = "photo", shape
        screen = Gdk.Screen.get_default()          # a barra é centrada no monitor: o overlay precisa cobri-lo, como na captura real
        ov = Overlay(cairo.ImageSurface(cairo.FORMAT_ARGB32, screen.get_width(), screen.get_height()), lambda k, p: None, "snip")
        ov.show_all()
        pump(.4)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        ox, oy = ov.get_window().get_origin()[1:]
        bar = ov.bar
        bx, by = bar.translate_coordinates(ov, bar.get_allocated_width() // 2, bar.get_allocated_height() // 2)
        return ov, (ox, oy), (ox + bx, oy + by), bar.get_allocated_height()

    def references(self, ov, origin):
        """Imagem do ponteiro de cada cursor candidato, medida na mesma tela."""
        out = {}
        for name in ("arrow", "cross"):
            ov.get_window().set_cursor(ov._cursors[name])
            self.move(origin[0] + 450, origin[1] + 450)
            out[name] = self.sig()
        self.assertNotEqual(out["arrow"], out["cross"])
        return out

    def test_real_pointer_per_mode_over_the_canvas_and_over_the_toolbar(self):
        pointer = _d.screen().root.query_pointer()
        self.addCleanup(lambda: (xtest.fake_input(_d, X.MotionNotify, x=pointer.root_x, y=pointer.root_y), _d.sync()))
        for shape, expected in (("rectangle", "cross"), ("freeform", "cross"), ("window", "arrow"), ("fullscreen", "arrow")):
            ov, origin, bar, bar_h = self.make(shape)
            ref = self.references(ov, origin)
            ov.update_cursor()
            self.move(origin[0] + 450, origin[1] + 450)
            self.assertEqual(self.sig(), ref[expected], "no canvas, modo " + shape)
            self.move(*bar)
            self.assertEqual(self.sig(), ref["arrow"], "sobre a barra, modo " + shape)
            self.move(bar[0], bar[1] + bar_h // 2 + 14)
            self.assertEqual(self.sig(), ref[expected], "logo abaixo da barra, modo " + shape)

    def test_choosing_a_mode_while_resting_on_the_toolbar_keeps_the_arrow_there(self):
        pointer = _d.screen().root.query_pointer()
        self.addCleanup(lambda: (xtest.fake_input(_d, X.MotionNotify, x=pointer.root_x, y=pointer.root_y), _d.sync()))
        ov, origin, bar, bar_h = self.make("window")
        ref = self.references(ov, origin)
        self.move(*bar)
        ov.set_shape("rectangle")                              # como ao escolher "Retângulo" no menu da barra
        pump(.2)
        self.assertEqual(self.sig(), ref["arrow"])
        self.move(origin[0] + 450, origin[1] + 450)
        self.assertEqual(self.sig(), ref["cross"])


if __name__ == "__main__":
    unittest.main()
