import gi
gi.require_version("Gtk", "3.0")
import unittest
from unittest.mock import patch
from gi.repository import Gtk, GObject

from gtkapp import shared_app
from captura import theme
from captura.config import settings
from captura.window import EditorWindow


def has_handler(widget):
    for name in ("clicked", "toggled", "button-press-event"):
        sid = GObject.signal_lookup(name, type(widget))
        if sid and GObject.signal_has_handler_pending(widget, sid, 0, False):
            return True
    return False


class ToolbarWiringTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def setUp(self):
        theme.apply()
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)

    def test_every_button_of_the_editor_window_has_a_handler(self):
        dead = [n for n, o in vars(self.w).items() if isinstance(o, Gtk.Button) and not has_handler(o)]
        self.assertEqual(dead, [])

    def test_new_button_starts_a_capture_from_the_app(self):
        with patch.object(self.app, "start_capture", create=True) as sc:
            self.w.btn_new.clicked()
        sc.assert_called_once_with("snip", settings["delay"], from_app=True)

    def test_empty_state_ocr_button_starts_text_capture(self):
        with patch.object(self.app, "start_capture", create=True) as sc:
            self.w.btn_ocr_empty.clicked()
        sc.assert_called_once_with("ocr", settings["delay"], from_app=True)

    def test_photo_video_toggle_switches_the_mode_setting(self):
        old = settings["mode"]
        self.addCleanup(lambda: settings.__setitem__("mode", old))
        self.w.b_video.clicked()
        self.assertEqual(settings["mode"], "video")
        self.assertTrue(self.w.b_video.get_active())
        self.assertFalse(self.w.b_photo.get_active())
        self.w.b_photo.clicked()
        self.assertEqual(settings["mode"], "photo")
        self.assertTrue(self.w.b_photo.get_active())

    def test_shape_and_delay_buttons_open_their_menus(self):
        import time
        from gi.repository import GLib
        self.w.show()
        end = time.monotonic() + .6
        while time.monotonic() < end:
            GLib.MainContext.default().iteration(False); time.sleep(.004)
        for btn in (self.w.shape_btn, self.w.delay_btn):
            self.w._cur_menu = None
            btn.clicked()
            self.assertIsNotNone(self.w._cur_menu, btn.get_tooltip_text())
            self.w._cur_menu.close_popup()


if __name__ == "__main__":
    unittest.main()
