"""Regressões das otimizações/correções da bateria de desempenho."""
import gi
gi.require_version("Gtk", "3.0")
import time
import unittest

import cairo
from gi.repository import GLib, Gtk

from gtkapp import shared_app
from captura import annot, theme
from captura.window import EditorWindow
from captura.textlayer import Word


def pump(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.003)


def surf(w, h, rgb=(.2, .5, .9)):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    c = cairo.Context(s); c.set_source_rgb(*rgb); c.paint()
    return s


class CanvasCacheTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def setUp(self):
        theme.apply()
        self.w = EditorWindow(self.app)
        self.w.show_all()
        self.addCleanup(self.w.destroy)
        pump(.3)

    def render(self):
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, 984, 640)
        self.w.canvas.on_draw(self.w.canvas, cairo.Context(out))
        return out

    def test_scaled_base_is_cached_per_image_and_zoom_and_invalidated_on_change(self):
        self.w.load_surface(surf(1920, 1080))
        pump(.2)
        c = self.w.canvas
        c.zoom = 0.5
        pump(.3)                                   # fora da janela de "zoom em andamento"
        self.render()
        first = c._scaled_base()
        self.assertIs(first, c._scaled_base())
        self.w.load_surface(surf(1920, 1080, (1, 0, 0)))
        c.zoom = 0.5
        pump(.3)
        self.assertIsNot(first, c._scaled_base())

    def test_reduced_image_matches_a_direct_render(self):
        self.w.load_surface(surf(1600, 900, (.9, .1, .1)))
        pump(.2)
        c = self.w.canvas
        c.zoom = 0.5
        pump(.3)
        out = self.render()
        a = c.get_allocation()
        ox, oy = c.origin()
        px = out.get_data()
        stride = out.get_stride()
        x, y = int(ox + 100), int(oy + 100)
        b, g, r = px[y * stride + x * 4], px[y * stride + x * 4 + 1], px[y * stride + x * 4 + 2]
        self.assertAlmostEqual(r / 255, .9, delta=.02)
        self.assertAlmostEqual(g / 255, .1, delta=.02)

    def test_zoom_in_progress_uses_a_fast_path_without_building_every_step(self):
        self.w.load_surface(surf(1920, 1080))
        pump(.2)
        c = self.w.canvas
        c.zoom = 0.5; pump(.3); self.render()
        built = c._scaled
        for z in (.45, .4, .35, .3):
            c.zoom = z
            self.render()
        self.assertIs(c._scaled, built)            # nenhuma reconstrução durante o gesto
        pump(.4)                                   # depois do gesto, reconstrói (timer)
        self.render()
        self.assertEqual(c._scaled[1], .3)

    def test_draw_all_culls_items_outside_the_view_but_keeps_visible_ones(self):
        inside = annot.Shape("rect", 10, 10, 60, 60, "#ff0000", 3)
        outside = annot.Shape("rect", 5000, 5000, 5060, 5060, "#ff0000", 3)
        calls = []
        orig = annot.draw_shape
        annot.draw_shape = lambda cr, it: calls.append(it)
        try:
            cr = cairo.Context(surf(100, 100))
            annot.draw_all(cr, [inside, outside], (0, 0, 200, 200))
            self.assertEqual(calls, [inside])
            calls.clear()
            annot.draw_all(cr, [inside, outside])
            self.assertEqual(calls, [inside, outside])
        finally:
            annot.draw_shape = orig


class DarkThemeTests(unittest.TestCase):
    def test_no_hard_coded_light_colors_remain_in_the_toolbar_css(self):
        css = theme.CSS.template
        for needle in ("#fbfbfb", "#e5e5e5", "#e0e0e0", "#cccccc", "#f9f9f9", "#ededed", "#c4c4c4"):
            self.assertNotIn(needle, css, needle)
        for k in ("new_bg", "pxsep", "px_hover", "canvas_bg"):
            self.assertIn(k, theme.LIGHT)
            self.assertIn(k, theme.DARK)
        self.assertNotEqual(theme.LIGHT["new_bg"], theme.DARK["new_bg"])


if __name__ == "__main__":
    unittest.main()
