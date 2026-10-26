import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
from unittest.mock import patch

import cairo
from gi.repository import GLib

from gtkapp import shared_app
from captura import theme, text_anim
from captura.config import settings
from captura.textlayer import Word
from captura.window import EditorWindow


def pump(sec):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.004)


class CurveTests(unittest.TestCase):
    def test_scan_duration_follows_the_windows_measurements(self):
        self.assertAlmostEqual(text_anim.scan_duration(1), 1.155, places=3)
        self.assertAlmostEqual(text_anim.scan_duration(7), 1.27, delta=.03)
        self.assertAlmostEqual(text_anim.scan_duration(24), 1.62, delta=.03)

    def test_gradient_rotates_one_turn_per_1500ms_clockwise(self):
        a, b = text_anim.phase_at(0), text_anim.phase_at(1500)
        self.assertAlmostEqual((b - a) % 360, 0, places=3)
        self.assertAlmostEqual((text_anim.phase_at(375) - a) % 360, 90, places=3)

    def test_palette_matches_measured_colors(self):
        r, g, b = text_anim.palette_color(0)
        self.assertEqual((round(r * 255), round(g * 255), round(b * 255)), (0x4a, 0x50, 0xec))
        r, g, b = text_anim.palette_color(180)
        self.assertEqual((round(r * 255), round(g * 255), round(b * 255)), (0xfb, 0x73, 0x82))

    def test_reveal_fades_the_image_to_full_dim_and_drops_the_bar_into_place(self):
        border0, dim0, off0 = text_anim.reveal_state(0)
        border1, dim1, off1 = text_anim.reveal_state(text_anim.REVEAL_MS)
        self.assertGreater(border0, 4)
        self.assertEqual((border1, dim1, off1), (0.0, 1.0, 0.0))
        self.assertGreater(off0, 20)
        _, d_mid, _ = text_anim.reveal_state(300)
        self.assertTrue(.5 < d_mid < .85)


class WindowAnimationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def setUp(self):
        theme.apply()
        old = settings["shot_autocopy_edits"]; settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", old))
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 100)
        cr = cairo.Context(s); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.w.load_surface(s)
        self.w.show()
        pump(.3)

    def words(self):
        return [Word("Olá", (10, 10, 60, 30), (1, 1, 1)), Word("mundo", (70, 10, 140, 30), (1, 1, 1))]

    def test_scan_runs_for_the_measured_minimum_then_reveals(self):
        with patch("captura.window.textlayer.ocr_surface", return_value=self.words()):
            t0 = time.monotonic()
            self.w.btn_text.clicked()
            pump(.3)
            self.assertTrue(self.w.canvas.text_scanning())
            self.assertFalse(self.w.text_bar.get_visible())
            self.assertEqual(self.w.canvas.text_dim, 0.0)
            while self.w.canvas.text_scanning() and time.monotonic() - t0 < 3:
                pump(.02)
            took = time.monotonic() - t0
        self.assertGreaterEqual(took, 1.12)
        self.assertLess(took, 1.6)
        self.assertTrue(self.w.text_bar.get_visible())
        pump(1.1)
        self.assertEqual(self.w.canvas.text_dim, 1.0)
        self.assertEqual(self.w.canvas.text_border, 0.0)

    def test_leaving_text_mode_is_instant(self):
        with patch("captura.window.textlayer.ocr_surface", return_value=self.words()):
            self.w.btn_text.clicked()
            pump(1.4)
        self.w.btn_text.clicked()
        self.assertFalse(self.w.text_bar.get_visible())
        self.assertFalse(self.w.canvas.text_scanning())
        self.assertNotEqual(self.w.canvas.tool, "text")

    def test_cancelling_during_the_scan_stops_everything(self):
        with patch("captura.window.textlayer.ocr_surface", return_value=self.words()):
            self.w.btn_text.clicked()
            pump(.3)
            self.w.btn_text.clicked()
            pump(1.4)
        self.assertFalse(self.w.text_bar.get_visible())
        self.assertFalse(self.w.canvas.text_scanning())


class MenuRevealTests(unittest.TestCase):
    def test_reveal_curve_is_monotonic_and_ends_in_250ms(self):
        from captura import menus
        vals = [menus._curve(t) for t in range(0, 300, 10)]
        self.assertEqual(vals, sorted(vals))
        self.assertEqual(menus._curve(250), 1.0)
        self.assertAlmostEqual(menus._curve(62), .75, places=2)


if __name__ == "__main__":
    unittest.main()


class TextBehaviorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def setUp(self):
        theme.apply()
        old = settings["shot_autocopy_edits"]; settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", old))
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 100)
        cr = cairo.Context(s); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.w.load_surface(s)
        self.w.show()
        pump(.3)

    def run_scan(self, words, secs=2.6):
        with patch("captura.window.textlayer.ocr_surface", return_value=words):
            self.w.btn_text.clicked()
            pump(secs)

    def test_blank_image_exits_selects_pen_disables_the_button_and_shows_the_notice(self):
        self.run_scan([])
        self.assertFalse(self.w.btn_text.get_active())
        self.assertFalse(self.w.btn_text.get_sensitive())
        self.assertTrue(self.w.btn_pen.get_active())
        self.assertTrue(self.w.notice.get_visible())
        self.assertEqual(self.w.notice.text, "Nenhum texto ou código QR foi detectado.")
        self.assertFalse(self.w.text_bar.get_visible())

    def test_loading_another_image_reenables_the_button_and_clears_the_notice(self):
        self.run_scan([])
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 50)
        self.w.load_surface(s)
        self.assertTrue(self.w.btn_text.get_sensitive())
        self.assertFalse(self.w.notice.get_visible())

    def test_leaving_text_mode_selects_the_pen_but_choosing_another_tool_wins(self):
        words = [Word("Olá", (10, 10, 60, 30), (1, 1, 1))]
        self.run_scan(words)
        self.w.btn_text.clicked()
        self.assertTrue(self.w.btn_pen.get_active())
        self.run_scan(words)
        self.w.select_tool("eraser")
        self.assertTrue(self.w.btn_eraser.get_active())
        self.assertFalse(self.w.btn_pen.get_active())

    def test_copy_as_table_is_enabled_only_for_aligned_columns_and_copies_html(self):
        grid = [Word(t, (x, y, x + 60, y + 20), (1, 1, n))
                for n, y in enumerate((10, 50, 90), 1)
                for t, x in (("Produto", 20), ("Qtd", 300), ("Preço", 420))]
        self.run_scan(grid)
        self.assertTrue(self.w.btn_table.get_sensitive())
        with patch("captura.window.services.copy_html_table") as ch:
            self.w.btn_table.clicked()
        html, text = ch.call_args[0]
        self.assertIn("<table>", html)
        self.assertEqual(text.splitlines()[0], "Produto\tQtd\tPreço")
        self.w.btn_text.clicked()
        self.run_scan([Word("Olá", (10, 10, 60, 30), (1, 1, 1)), Word("mundo", (70, 10, 140, 30), (1, 1, 1))])
        self.assertFalse(self.w.btn_table.get_sensitive())


class TextLayerShapeTests(unittest.TestCase):
    def test_wide_gaps_split_a_line_into_cells(self):
        from captura import textlayer
        ws = [Word("A", (10, 10, 30, 30), (1, 1, 1)), Word("B", (40, 10, 60, 30), (1, 1, 1)),
              Word("C", (300, 10, 320, 30), (1, 1, 1))]
        self.assertEqual([[w.text for w in l.words] for l in textlayer.group_lines(ws)], [["A", "B"], ["C"]])

    def test_paragraph_change_adds_a_blank_line(self):
        from captura import textlayer
        ws = [Word("um", (0, 0, 30, 20), (1, 1, 1)), Word("dois", (0, 40, 30, 60), (1, 1, 2)),
              Word("tres", (0, 80, 30, 100), (1, 2, 1)), Word("quatro", (0, 180, 30, 200), (1, 3, 1))]
        self.assertEqual(textlayer.words_text(ws), "um\ndois\n\ntres\n\nquatro")
