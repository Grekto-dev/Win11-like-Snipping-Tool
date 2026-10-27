"""Itens que eram casca (placeholders): leitura de QR, indicadores da barra de gravação, pesquisa visual."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import os
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import cairo
from gi.repository import Gdk, GdkPixbuf, GLib, Gtk

from gtkapp import shared_app
from captura import qr, services, theme
from captura.config import settings
from captura.overlay import Overlay
from captura.textlayer import Word


def pump(sec=.3):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.004)


def qr_surface(text, box=6, pad=30):
    import qrcode
    q = qrcode.QRCode(box_size=box, border=4)
    q.add_data(text)
    q.make(fit=True)
    m = q.get_matrix()                                   # inclui a borda branca (quiet zone)
    n = len(m)
    side = n * box
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, side + 2 * pad, side + 2 * pad)
    cr = cairo.Context(s); cr.set_source_rgb(1, 1, 1); cr.paint()
    cr.set_source_rgb(0, 0, 0)
    for y, row in enumerate(m):
        for x, v in enumerate(row):
            if v:
                cr.rectangle(pad + x * box, pad + y * box, box, box)
    cr.fill()
    return s


@unittest.skipUnless(qr.available(), "libzbar ausente")
class QrDecodeTests(unittest.TestCase):
    def test_decodes_text_urls_and_accents(self):
        for t in ("https://example.com/a?x=1&y=2", "olá, ação — 日本語"):
            self.assertEqual(qr.decode(qr_surface(t)), [t])

    def test_small_codes_are_found_by_the_upscaled_pass_and_blank_images_return_nothing(self):
        self.assertEqual(qr.decode(qr_surface("pequeno", box=2, pad=10)), ["pequeno"])
        blank = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200)
        c = cairo.Context(blank); c.set_source_rgb(1, 1, 1); c.paint()
        self.assertEqual(qr.decode(blank), [])


@unittest.skipUnless(qr.available(), "libzbar ausente")
class QrOverlayTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def make(self, surf):
        settings["mode"], settings["shape"] = "photo", "rectangle"
        self.results = []
        ov = Overlay(surf, lambda k, p: self.results.append((k, p)), "ocr")
        ov.show_all(); pump(.3)
        self.addCleanup(lambda: ov.destroy() if ov.get_window() else None)
        return ov

    def drag(self, ov, a, b):
        e = lambda x, y: SimpleNamespace(x=x, y=y, button=1, state=0, type=Gdk.EventType.BUTTON_PRESS)
        ov.on_press(ov.da, e(*a)); ov.on_motion(ov.da, e(*b)); ov.on_release(ov.da, e(*b))

    def test_selection_with_only_a_qr_code_becomes_ready_and_the_qr_button_copies_it(self):
        ov = self.make(qr_surface("https://exemplo.org/qr", box=5, pad=60))
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=[]), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.drag(ov, (5, 5), (ov.W - 5, ov.H - 5))
            pump(1.5)
        self.assertEqual(ov.ts.phase, "ready")
        self.assertEqual(ov.ts.qr, ["https://exemplo.org/qr"])
        self.assertTrue(ov.mini.qr_enabled and ov.mini.get_visible())
        self.assertTrue(ov.bar_ocr.copy_enabled)
        ov.mini._release(ov.mini, SimpleNamespace(x=ov.mini and 60, y=20, button=1))
        pump(.4)
        self.assertEqual(self.results[0], ("textcopy", "https://exemplo.org/qr"))

    def test_qr_button_is_disabled_when_there_is_no_qr(self):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        c = cairo.Context(s); c.set_source_rgb(1, 1, 1); c.paint()
        ov = self.make(s)
        words = [Word("Olá", (20, 20, 70, 40), (1, 1, 1))]
        with patch("captura.overlay_text.textlayer.ocr_surface", return_value=words), \
             patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
            self.drag(ov, (5, 5), (390, 290))
            pump(1.5)
        self.assertEqual(ov.ts.phase, "ready")
        self.assertFalse(ov.mini.qr_enabled)
        self.assertIsNone(ov.mini._which(60, 20))


class RecordingBarIndicatorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def test_mic_and_audio_are_status_icons_not_dead_buttons(self):
        from captura.app import RecordingBar
        bar = RecordingBar(lambda: None, lambda: None, (100, 100, 200, 150), on_pause=lambda: None)
        self.addCleanup(bar.destroy)
        self.assertNotIsInstance(bar.btn_mic, Gtk.Button)
        self.assertNotIsInstance(bar.btn_audio, Gtk.Button)
        self.assertTrue(bar.btn_mic.get_tooltip_text())
        self.assertIsInstance(bar.btn_pause, Gtk.Button)
        self.assertIsInstance(bar.btn_stop, Gtk.Button)
        self.assertIsInstance(bar.btn_trash, Gtk.Button)


class VisualSearchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        theme.apply()

    def test_page_posts_the_image_to_bing_and_is_private_and_cleaned_up(self):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 40)
        cr = cairo.Context(s); cr.set_source_rgb(0, 0, 1); cr.paint()
        path = services.visual_search_page(s)
        self.addCleanup(lambda: os.path.exists(path) and os.remove(path))
        html = open(path, encoding="utf-8").read()
        self.assertIn(services.BING_UPLOAD, html)
        self.assertIn('name="imageBin"', html)
        self.assertIn("iVBOR", html)                              # PNG em base64
        self.assertEqual(oct(os.stat(path).st_mode & 0o777), "0o600")

    def test_window_asks_for_confirmation_before_sending_anything(self):
        from captura.window import EditorWindow
        self.app.apply_theme = theme.apply
        w = EditorWindow(self.app)
        w.show_all()
        w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 60, 40))
        self.addCleanup(w.destroy)
        with patch.object(Gtk.MessageDialog, "run", return_value=Gtk.ResponseType.CANCEL), \
             patch.object(services, "visual_search_page") as page, patch("subprocess.Popen") as popen:
            w.visual_search()
        page.assert_not_called(); popen.assert_not_called()
        with patch.object(Gtk.MessageDialog, "run", return_value=Gtk.ResponseType.OK), \
             patch.object(services, "visual_search_page", return_value="/tmp/x.html") as page, patch("subprocess.Popen") as popen:
            w.visual_search()
        page.assert_called_once()
        popen.assert_called_once_with(["xdg-open", "/tmp/x.html"])


if __name__ == "__main__":
    unittest.main()
