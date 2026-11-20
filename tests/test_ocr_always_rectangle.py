"""O Extrator de Texto sempre seleciona um retângulo, sem ler nem alterar o modo de captura (janela, tela inteira, etc.)."""
import gi
gi.require_version("Gtk", "3.0")
import json
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib

from gtkapp import shared_app
from captura import icons, theme
from captura.config import settings
from captura.overlay import SHAPES, Overlay
from captura import overlay_text as OT
from captura.textlayer import Word

try:
    from Xlib import X, display as xdisplay
    from Xlib.ext import xtest
    HAVE_XTEST = bool(os.environ.get("DISPLAY"))
except ImportError:
    HAVE_XTEST = False

SHAPE_KEYS = [k for k, _i, _l in SHAPES]


def pump(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.003)


def words():
    return [Word("Olá", (20, 20, 70, 40), (1, 1, 1)), Word("mundo", (80, 20, 150, 40), (1, 1, 1))]


class OcrAlwaysRectangleTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def setUp(self):
        self.saved = {k: settings[k] for k in ("mode", "shape", "ocr_auto_copy", "ocr_remove_breaks")}
        settings["ocr_auto_copy"] = settings["ocr_remove_breaks"] = False
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k, v in self.saved.items()])
        self.results = []

    def make(self, tool="ocr", shape="rectangle", mode="photo"):
        settings["mode"], settings["shape"] = mode, shape
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)
        cr = cairo.Context(surf); cr.set_source_rgb(1, 1, 1); cr.paint()
        ov = Overlay(surf, lambda k, p: self.results.append((k, p)), tool)
        ov.show_all()
        pump(.3)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        return ov

    def drag(self, ov, a, b):
        ev = lambda x, y: SimpleNamespace(x=x, y=y, button=1, state=0, type=Gdk.EventType.BUTTON_PRESS)
        ov.on_press(ov.da, ev(*a)); ov.on_motion(ov.da, ev(*b)); ov.on_release(ov.da, ev(*b))

    def scan(self, ov, a=(10, 10), b=(300, 200)):
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words()), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.drag(ov, a, b)
            pump(1.2)

    def test_the_text_extractor_always_works_in_rectangle_mode_and_leaves_the_saved_mode_alone(self):
        for saved in SHAPE_KEYS:
            ov = self.make("ocr", saved)
            self.assertEqual(ov.shape, "rectangle", saved)
            self.assertEqual(settings["shape"], saved, saved)

    def test_a_drag_selects_a_rectangle_whatever_the_saved_mode(self):
        for saved in ("window", "fullscreen", "freeform"):
            self.results.clear()
            ov = self.make("ocr", saved)
            self.scan(ov)
            self.assertEqual(ov.ts.rect, (10, 10, 300, 200), saved)
            self.assertEqual(ov.ts.phase, "ready", saved)
            self.assertEqual((ov.free_pts, self.results), ([], []), saved)
            self.assertEqual(settings["shape"], saved, saved)

    def test_a_plain_click_never_captures_the_window_or_screen_under_the_pointer(self):
        for saved in ("window", "fullscreen"):
            ov = self.make("ocr", saved)
            ov.on_press(ov.da, SimpleNamespace(x=100, y=100, button=1, state=0, type=Gdk.EventType.BUTTON_PRESS))
            ov.on_release(ov.da, SimpleNamespace(x=100, y=100, button=1, state=0, type=Gdk.EventType.BUTTON_RELEASE))
            pump(.3)
            self.assertEqual((ov.ts.phase, self.results), ("none", []), saved)

    def test_the_saved_mode_survives_the_whole_text_flow(self):
        for saved in SHAPE_KEYS:
            ov = self.make("ocr", saved)
            self.scan(ov)
            self.drag(ov, (30, 30), (140, 80))
            ov.on_key(ov, SimpleNamespace(keyval=Gdk.KEY_c, state=Gdk.ModifierType.CONTROL_MASK))
            pump(.3)
            self.assertEqual(settings["shape"], saved, saved)
            self.assertEqual(self.results[-1][0], "textcopy", saved)
            self.results.clear()

    def test_leaving_the_text_extractor_gives_back_the_saved_mode_and_its_icon(self):
        for saved in ("window", "fullscreen", "freeform"):
            ov = self.make("snip", saved)
            self.assertEqual(ov.shape, saved)
            ov.set_tool("ocr")
            self.assertEqual((ov.shape, settings["shape"]), ("rectangle", saved), saved)
            ov.set_tool("snip")
            self.assertEqual((ov.shape, settings["shape"]), (saved, saved), saved)
            icon = [i for k, i, _l in SHAPES if k == saved][0]
            expected = icons.pixbuf(icon, 20, theme.icon_color()).get_pixels()
            self.assertEqual(ov.shape_img.get_pixbuf().get_pixels(), expected, saved)

    def test_the_text_extractor_ignores_the_photo_video_mode_too(self):
        ov = self.make("ocr", "window", mode="video")
        self.scan(ov)
        self.assertEqual((ov.ts.phase, ov.ts.rect), ("ready", (10, 10, 300, 200)))
        self.assertEqual((settings["mode"], settings["shape"]), ("video", "window"))

    def test_other_tools_still_follow_the_saved_mode(self):
        for tool in ("snip", "color"):
            for saved in SHAPE_KEYS:
                self.assertEqual(self.make(tool, saved).shape, saved, (tool, saved))

    def test_choosing_a_mode_in_the_capture_bar_after_the_text_extractor_is_saved_normally(self):
        ov = self.make("snip", "window")
        ov.set_tool("ocr")
        ov.set_tool("snip")
        ov.set_shape("freeform")
        self.assertEqual((ov.shape, settings["shape"]), ("freeform", "freeform"))
        ov.set_tool("ocr")
        self.assertEqual((ov.shape, settings["shape"]), ("rectangle", "freeform"))


@unittest.skipUnless(HAVE_XTEST, "precisa de DISPLAY e python-xlib")
class OcrAlwaysRectangleRealInputTests(unittest.TestCase):
    """Cliques e arrastos reais (XTEST), com o modo salvo em janela, tela inteira e forma livre."""

    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def setUp(self):
        from captura import config
        self.config = config
        self.saved = {k: settings[k] for k in ("mode", "shape", "ocr_auto_copy", "ocr_remove_breaks")}
        settings["ocr_auto_copy"] = settings["ocr_remove_breaks"] = False
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k, v in self.saved.items()])
        self.conn = xdisplay.Display()
        self.addCleanup(self.conn.close)
        if not self.conn.has_extension("XTEST"):
            self.skipTest("XTEST indisponível")
        root = self.conn.screen().root
        pointer = root.query_pointer()
        self.addCleanup(lambda: (root.warp_pointer(pointer.root_x, pointer.root_y), self.conn.sync()))
        self.results = []

    def overlay(self, tool, shape):
        settings["mode"], settings["shape"] = "photo", shape
        screen = Gdk.Screen.get_default()
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, screen.get_width(), screen.get_height())
        cr = cairo.Context(surf); cr.set_source_rgb(1, 1, 1); cr.paint()
        ov = Overlay(surf, lambda k, p: self.results.append((k, p)), tool)
        ov.show_all()
        pump(.5)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        return ov

    def move(self, x, y, wait=.06):
        xtest.fake_input(self.conn, X.MotionNotify, x=int(x), y=int(y)); self.conn.sync(); pump(wait)

    def button(self, kind):
        xtest.fake_input(self.conn, kind, 1); self.conn.sync(); pump(.08)

    def click_widget(self, ov, widget):
        a = widget.get_allocation()
        x, y = widget.translate_coordinates(ov, 0, 0)
        ox, oy = ov.get_window().get_origin()[1:]
        self.move(ox + x + a.width / 2, oy + y + a.height / 2, .15)
        self.button(X.ButtonPress); self.button(X.ButtonRelease)

    def real_drag(self, ov, a, b):
        ox, oy = ov.get_window().get_origin()[1:]
        self.move(ox + a[0], oy + a[1], .12)
        self.button(X.ButtonPress)
        for i in range(1, 11):
            self.move(ox + a[0] + (b[0] - a[0]) * i / 10, oy + a[1] + (b[1] - a[1]) * i / 10, .03)
        self.button(X.ButtonRelease)

    def on_disk(self):
        with open(self.config.CONFIG_FILE, encoding="utf-8") as f:
            return json.load(f)["shape"]

    def test_a_real_drag_in_the_text_extractor_selects_a_rectangle_with_any_saved_mode(self):
        for saved in ("window", "fullscreen", "freeform"):
            ov = self.overlay("ocr", saved)
            with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words()), \
                 patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
                self.real_drag(ov, (150, 200), (500, 420))
                pump(1.3)
            self.assertEqual(ov.ts.phase, "ready", saved)
            x0, y0, x1, y1 = ov.ts.rect
            self.assertEqual((x1 - x0, y1 - y0), (350, 220), saved)
            self.assertEqual(self.results, [], saved)
            self.assertEqual((settings["shape"], self.on_disk()), (saved, saved), saved)
            ov.destroy()

    def test_clicking_the_text_button_in_the_bar_switches_to_a_rectangle_and_back_without_touching_the_saved_mode(self):
        ov = self.overlay("snip", "window")
        self.click_widget(ov, ov.btn_ocr)
        self.assertEqual((ov.tool, ov.shape, settings["shape"]), ("ocr", "rectangle", "window"))
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words()), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.real_drag(ov, (150, 200), (500, 420))
            pump(1.3)
        self.assertEqual(ov.ts.phase, "ready")
        bx, by, bw, bh = OT.BACK                                  # a seta da barra do extrator volta à barra principal
        a = ov.bar_ocr.get_allocation()
        ox, oy = ov.get_window().get_origin()[1:]
        x, y = ov.bar_ocr.translate_coordinates(ov, 0, 0)
        self.move(ox + x + bx + bw / 2, oy + y + by + bh / 2, .15)
        self.button(X.ButtonPress); self.button(X.ButtonRelease)
        pump(.3)
        self.assertEqual((ov.tool, ov.shape, settings["shape"], self.on_disk()), ("snip", "window", "window", "window"))


if __name__ == "__main__":
    unittest.main()
