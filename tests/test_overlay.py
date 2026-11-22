import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
from gi.repository import Gdk, GLib

from gtkapp import shared_app
from captura import theme, overlay_bar
from captura.config import settings
from captura.overlay import Overlay


def pump(sec=.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.004)


class OverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def make(self, mode="photo", shape="rectangle", scale=1):
        settings["mode"], settings["shape"] = mode, shape
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)
        surf.set_device_scale(scale, scale)
        self.results = []
        ov = Overlay(surf, lambda k, p: self.results.append((k, p)))
        ov.show_all()
        pump(.3)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        return ov

    def ev(self, x, y, key=None):
        return SimpleNamespace(x=x, y=y, button=1, state=0, keyval=key, type=Gdk.EventType.BUTTON_PRESS)

    def drag(self, ov, a, b):
        ov.on_press(ov.da, self.ev(*a))
        ov.on_motion(ov.da, self.ev(*b))
        ov.on_release(ov.da, self.ev(*b))

    def test_bar_is_measured_geometry_centered_13px_from_top(self):
        ov = self.make()
        self.assertEqual((ov.bar.get_size_request()), (overlay_bar.MAIN_W, overlay_bar.MAIN_H))
        self.assertEqual(ov.bar.get_margin_top(), overlay_bar.TOP)
        self.assertEqual(ov.bar.get_margin_start(), (800 - overlay_bar.MAIN_W) // 2) if ov._mon[2] == 800 else None

    def test_fullscreen_highlights_only_the_monitor_under_the_pointer(self):
        monitors = [(0, 0, 300, 500), (300, 100, 500, 400)]
        with patch("captura.grab.monitors", return_value=monitors), \
             patch("captura.grab.pointer_position", return_value=(90, 200)):
            ov = self.make(shape="fullscreen")
            self.assertEqual(ov.hole(), ("rect", (0, 0, 300, 500)))
            ov.on_motion(ov.da, self.ev(300, 220))
            self.assertEqual(ov.hole(), ("rect", (300, 100, 800, 500)))
            ov.on_motion(ov.da, self.ev(500, 50))  # espaço vazio acima do segundo monitor
            self.assertIsNone(ov.hole())

    def test_fullscreen_captures_the_clicked_monitor_not_the_last_hover(self):
        with patch("captura.grab.monitors", return_value=[(0, 0, 300, 500), (300, 100, 500, 400)]):
            ov = self.make(shape="fullscreen")
            cr = cairo.Context(ov.surface)
            cr.set_source_rgb(1, 0, 0); cr.paint()
            cr.set_source_rgb(0, 1, 0); cr.rectangle(300, 100, 500, 400); cr.fill()
            ov.on_motion(ov.da, self.ev(100, 220))
            ov.on_press(ov.da, self.ev(500, 50))  # o espaço vazio não é elegível
            self.assertFalse(ov._done)
            ov.on_press(ov.da, self.ev(500, 250))
            pump(.2)
        [(kind, image)] = self.results
        self.assertEqual(kind, "image")
        self.assertEqual((image.get_width(), image.get_height()), (500, 400))
        self.assertEqual(tuple(image.get_pixels()[:3]), (0, 255, 0))

    def test_fullscreen_and_all_screens_match_on_a_single_monitor(self):
        with patch("captura.grab.monitors", return_value=[(0, 0, 800, 500)]):
            for shape in ("fullscreen", "all_screens"):
                with self.subTest(shape=shape):
                    ov = self.make(shape=shape)
                    ov.on_motion(ov.da, self.ev(450, 250))
                    self.assertEqual(ov.hole(), ("rect", (0, 0, 800, 500)))
                    ov.on_press(ov.da, self.ev(450, 250))
                    pump(.2)
                    [(kind, image)] = self.results
                    self.assertEqual(kind, "image")
                    self.assertEqual((image.get_width(), image.get_height()), (800, 500))

    def test_root_snapshot_ignores_cached_size_when_xsettings_switches_to_2x(self):
        from captura import grab, services
        from gi.repository import GdkPixbuf
        root = SimpleNamespace(get_width=lambda: 800, get_height=lambda: 500,
                               get_geometry=lambda: (0, 0, 400, 250), get_scale_factor=lambda: 2)
        def read_pixels(_root, x, y, w, h):
            self.assertEqual((x, y, w, h), (0, 0, 400, 250))
            return GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, 2*w, 2*h)
        with patch.object(Gdk, "get_default_root_window", return_value=root), \
             patch.object(Gdk, "pixbuf_get_from_window", side_effect=read_pixels):
            shot = grab.grab_screen()
            self.assertEqual(services.screen_size(), (800, 500))
        self.assertEqual((shot.get_width(), shot.get_height()), (800, 500))
        self.assertEqual(shot.get_device_scale(), (2, 2))

    def test_fullscreen_keeps_native_pixels_when_the_overlay_is_scaled(self):
        with patch("captura.grab.monitors", return_value=[(0, 0, 200, 250), (200, 0, 200, 250)]):
            ov = self.make(shape="fullscreen", scale=2)
            cr = cairo.Context(ov.surface)
            cr.set_source_rgb(1, 0, 0); cr.paint()
            cr.set_source_rgb(0, 1, 0); cr.rectangle(200, 0, 200, 250); cr.fill()
            self.assertEqual((ov.W, ov.H), (400, 250))
            ov.on_press(ov.da, self.ev(240, 150))
            pump(.2)
        [(kind, image)] = self.results
        self.assertEqual(kind, "image")
        self.assertEqual((image.get_width(), image.get_height()), (400, 500))
        self.assertEqual(tuple(image.get_pixels()[:3]), (0, 255, 0))

    def test_all_screens_preserves_the_entire_desktop(self):
        with patch("captura.grab.monitors", return_value=[(0, 0, 300, 500), (300, 100, 500, 400)]):
            ov = self.make(shape="all_screens")
            self.assertEqual(ov.hole(), ("rect", (0, 0, 800, 500)))
            ov.on_motion(ov.da, self.ev(450, 250))
            self.assertEqual(ov.hole(), ("rect", (0, 0, 800, 500)))
            ov.on_press(ov.da, self.ev(450, 250))
            pump(.2)
        [(kind, image)] = self.results
        self.assertEqual(kind, "image")
        self.assertEqual((image.get_width(), image.get_height()), (800, 500))

    def test_screen_modes_offer_the_same_regions_for_recording(self):
        with patch("captura.grab.monitors", return_value=[(0, 0, 300, 500), (300, 100, 500, 400)]):
            for shape, region in (("fullscreen", (300, 100, 500, 400)), ("all_screens", (0, 0, 800, 500))):
                with self.subTest(shape=shape):
                    ov = self.make(mode="video", shape=shape)
                    ov.on_press(ov.da, self.ev(500, 250))
                    self.assertTrue(ov.sel_locked)
                    ov.bar.start_btn.clicked()
                    pump(.2)
                    self.assertEqual(self.results, [("video", region)])

    def test_all_screens_is_between_fullscreen_and_freeform_in_both_menus(self):
        from captura.overlay import SHAPES as overlay_shapes
        from captura.window import SHAPES as editor_shapes
        for options in (overlay_shapes, editor_shapes):
            self.assertEqual([key for key, _, _ in options],
                             ["rectangle", "window", "fullscreen", "all_screens", "freeform"])

    def test_escape_closes_even_with_a_locked_video_selection(self):
        ov = self.make("video")
        self.drag(ov, (100, 100), (300, 250))
        self.assertTrue(ov.sel_locked)
        self.assertEqual(ov.bar.mode_name, "record")
        ov.on_key(ov, self.ev(0, 0, Gdk.KEY_Escape))
        pump(.3)
        self.assertEqual([k for k, _ in self.results], ["cancel"])

    def test_video_selection_switches_bar_to_start_state_and_start_records_region(self):
        ov = self.make("video")
        self.drag(ov, (100, 100), (300, 250))
        self.assertEqual((ov.bar.get_size_request()), (overlay_bar.REC_W, overlay_bar.REC_H))
        ov.bar.start_btn.clicked()
        pump(.3)
        self.assertEqual(self.results, [("video", (100, 100, 200, 150))])

    def test_freeform_in_video_mode_locks_the_bounding_box_instead_of_taking_a_picture(self):
        ov = self.make("video", "freeform")
        ov.on_press(ov.da, self.ev(100, 100))
        for p in ((200, 120), (260, 220), (120, 240)):
            ov.on_motion(ov.da, self.ev(*p))
        ov.on_release(ov.da, self.ev(110, 230))
        self.assertTrue(ov.sel_locked)
        self.assertEqual(self.results, [])

    def test_grab_retry_counter_is_per_overlay(self):
        a = self.make()
        a._grab_tries = 20
        b = self.make()
        self.assertEqual(b._grab_tries, 0)

    def test_mic_toggle_in_the_start_bar_persists_the_setting(self):
        old = settings["rec_mic"]
        self.addCleanup(lambda: settings.__setitem__("rec_mic", old))
        ov = self.make("video")
        self.drag(ov, (100, 100), (300, 250))
        ov.bar.btn_mic.clicked()
        self.assertEqual(settings["rec_mic"], not old)


if __name__ == "__main__":
    unittest.main()
