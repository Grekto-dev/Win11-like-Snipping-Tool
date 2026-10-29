"""Real OCR through editor buttons and a real clipboard, without mocking recognition."""
import os
import shutil
import time
import unittest
import cairo
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk, GLib
from gtkapp import shared_app
from captura import theme, ocr_engine
from captura.config import settings
from captura.window import EditorWindow

try:
    from Xlib import X, display
    from Xlib.ext import xtest
    HAVE = bool(os.environ.get("DISPLAY")) and shutil.which("tesseract")
except ImportError:
    HAVE = False


def pump_until(condition, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        while GLib.MainContext.default().pending():
            GLib.MainContext.default().iteration(False)
        if condition():
            return True
        time.sleep(.01)
    return bool(condition())


@unittest.skipUnless(HAVE, "XTEST/Tesseract unavailable")
class RealOcrClickTests(unittest.TestCase):
    def test_real_recognition_and_copy_through_actual_button_clicks(self):
        app = shared_app()
        app.apply_theme = theme.apply
        theme.apply()
        previous = settings["shot_autocopy_edits"]
        settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", previous))
        window = EditorWindow(app)
        self.addCleanup(window.destroy)
        self.addCleanup(ocr_engine.POOL.shutdown)
        surface = cairo.ImageSurface(cairo.FORMAT_RGB24, 940, 240)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.set_source_rgb(0, 0, 0)
        cr.set_font_size(25)
        for row in range(3):
            cr.move_to(20, 40 + row * 50)
            cr.show_text("The quick brown fox jumps over the lazy dog")
        window.load_surface(surface)
        window.show()
        window.present()
        self.assertTrue(pump_until(lambda: window.get_window() is not None))
        pump_until(lambda: False, .5)
        connection = display.Display()
        self.addCleanup(connection.close)
        if not connection.has_extension("XTEST"):
            self.skipTest("XTEST unavailable")
        root = connection.screen().root
        saved = root.query_pointer()
        def restore_pointer():
            root.warp_pointer(saved.root_x, saved.root_y)
            connection.sync()
        self.addCleanup(restore_pointer)
        def click(button):
            self.assertTrue(button.get_visible() and button.get_sensitive())
            allocation = button.get_allocation()
            x, y = button.translate_coordinates(window, 0, 0)
            ox, oy = window.get_window().get_origin()[1:]
            root.warp_pointer(int(ox + x + allocation.width / 2), int(oy + y + allocation.height / 2))
            connection.sync()
            pump_until(lambda: False, .08)
            xtest.fake_input(connection, X.ButtonPress, 1)
            connection.sync()
            pump_until(lambda: False, .06)
            clicked = []
            handler = button.connect("clicked", lambda *_args: clicked.append(True))
            try:
                xtest.fake_input(connection, X.ButtonRelease, 1)
                connection.sync()
                self.assertTrue(pump_until(lambda: bool(clicked), 2), "button did not receive a click")
            finally:
                button.disconnect(handler)
        click(window.btn_text)
        self.assertTrue(pump_until(lambda: bool(window.canvas.text_words) and not window.canvas.text_scanning(), 20))
        self.assertTrue(window.text_bar.get_visible())
        # Recognition finishes before the toolbar's slide-in animation. Click its
        # settled allocation rather than its position during the transition.
        pump_until(lambda: False, .5)
        click(window.btn_copy_all)
        copied = []
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.request_text(lambda _clipboard, text, _data: copied.append(text), None)
        self.assertTrue(pump_until(lambda: bool(copied)))
        self.assertEqual(" ".join(copied[0].split()), " ".join(["The quick brown fox jumps over the lazy dog"] * 3))


if __name__ == "__main__":
    unittest.main()
