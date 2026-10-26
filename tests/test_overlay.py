import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from types import SimpleNamespace

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

    def make(self, mode="photo", shape="rectangle"):
        settings["mode"], settings["shape"] = mode, shape
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 800, 500)
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
