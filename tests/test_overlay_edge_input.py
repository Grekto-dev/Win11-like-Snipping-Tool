"""X11 corner drags when the seat grab delivers events to the overlay window."""
import os
import time
import unittest

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import GLib

from captura import grab, theme
from captura.config import settings
from captura.overlay import Overlay
from gtkapp import shared_app

try:
    from Xlib import X, display
    from Xlib.ext import xtest
except ImportError:
    display = None


def pump_until(condition, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if condition():
            return True
        time.sleep(.005)
    return condition()


@unittest.skipUnless(display is not None and os.environ.get("DISPLAY"), "requires X11 and python-xlib")
class CornerInputTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shared_app()
        theme.apply()

    def setUp(self):
        self.driver = display.Display()
        self.addCleanup(self.driver.close)
        if not self.driver.has_extension("XTEST"):
            self.skipTest("XTEST unavailable")
        root = self.driver.screen().root
        pointer = root.query_pointer()
        self.addCleanup(self._input, X.MotionNotify, (pointer.root_x, pointer.root_y))
        # A distinct X client like a desktop edge window, not a child of the overlay.
        self.blocker = display.Display()
        self.addCleanup(self.blocker.close)
        self.root = self.blocker.screen().root
        for key, value in (("shape", "rectangle"), ("mode", "photo")):
            self.addCleanup(settings.__setitem__, key, settings[key])
            settings[key] = value

    def _input(self, event, point=None):
        if point is None:
            xtest.fake_input(self.driver, event, 1)
        else:
            xtest.fake_input(self.driver, event, x=point[0], y=point[1])
        self.driver.sync()
        pump_until(lambda: False, .045)

    def _assert_corner_drag(self, drag_from_corner):
        surface = grab.grab_screen()
        w, h = surface.get_width(), surface.get_height()
        sx, sy = map(int, surface.get_device_scale())
        for corner in ((0, 0), (w - sx, 0), (0, h - sy), (w - sx, h - sy)):
            with self.subTest(corner=corner):
                results = []
                overlay = Overlay(surface, lambda kind, payload: results.append((kind, payload)))
                overlay.present_grabbed()
                pump_until(lambda: False, .15)
                x, y = corner
                edge = self.root.create_window(min(x, w - 12), min(y, h - 12), 12, 12, 0, 0,
                                               X.InputOnly, X.CopyFromParent, override_redirect=True)
                try:
                    edge.map()
                    edge.configure(stack_mode=X.Above)
                    self.blocker.sync()
                    interior = (w // (4*sx)*sx, h // (3*sy)*sy)
                    start, end = (corner, interior) if drag_from_corner else (interior, corner)
                    self._input(X.MotionNotify, start)
                    self._input(X.ButtonPress)
                    try:
                        self._input(X.MotionNotify, tuple((a + b) // 2 for a, b in zip(start, end)))
                        self._input(X.MotionNotify, end)
                    finally:
                        self._input(X.ButtonRelease)
                    self.assertTrue(pump_until(lambda: results, .6), "release did not finish the capture")
                    [(kind, image)] = results
                    self.assertEqual(kind, "image")
                    self.assertEqual((image.get_width(), image.get_height()),
                                     tuple(abs(a - b) for a, b in zip(start, end)))
                finally:
                    edge.destroy()
                    self.blocker.sync()
                    if overlay.get_window() is not None:
                        overlay.finish("cancel", None)
                        pump_until(lambda: results, .2)

    def test_drag_can_start_on_a_desktop_corner(self):
        self._assert_corner_drag(drag_from_corner=True)

    def test_drag_can_finish_on_a_desktop_corner(self):
        self._assert_corner_drag(drag_from_corner=False)
