"""Differential checks against the pre-optimization OCR contract, not token-count F1."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import cairo
import gi
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from captura import ocr_engine as E, services, textlayer


def fixture(size=14, cols=1, dark=False):
    width, height = (940 if cols == 1 else 1600), 380
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, height)
    cr = cairo.Context(surface)
    cr.set_source_rgb(*((.12, .12, .14) if dark else (1, 1, 1)))
    cr.paint()
    cr.set_source_rgb(*((.88, .88, .9) if dark else (0, 0, 0)))
    cr.select_font_face("DejaVu Sans")
    cr.set_font_size(size)
    lines = ["Permission is hereby granted without restriction.",
             "The quick brown fox jumps over the lazy dog.",
             "Software, documentation and copyright notices.",
             "Contact: jane.doe@example.com or +55 11 98765-4321.",
             "Numbers: 123, 456.78 and 2026-10-29."]
    for c in range(cols):
        for r, text in enumerate(lines):
            cr.move_to(20 + c * 780, 35 + r * (size * 2))
            cr.show_text(text)
    return services.surface_to_pixbuf(surface)


def legacy(pb, langs):
    """Same scale, modes and table selection as 959b64a; OMP1 only changes scheduling."""
    with tempfile.TemporaryDirectory() as directory:
        orig = os.path.join(directory, "orig.png")
        pb.savev(orig, "png", [], [])
        scale, src = 1, orig
        if max(pb.get_width(), pb.get_height()) < 1200:
            scale, src = 2, os.path.join(directory, "x2.png")
            pb.scale_simple(pb.get_width() * 2, pb.get_height() * 2,
                            GdkPixbuf.InterpType.BILINEAR).savev(src, "png", [], [])
        def read(path, mode, factor):
            result = subprocess.run(["tesseract", path, "stdout", "--psm", str(mode), "-l", langs, "tsv"],
                                    capture_output=True, text=True, check=True, timeout=120,
                                    env=dict(os.environ, OMP_THREAD_LIMIT="1"))
            return textlayer.parse_tsv(result.stdout, factor)
        sparse = read(orig, 11, 1)
        plain = read(src, 4, scale)
    return sparse if sparse and textlayer.detect_table(sparse) is not None else plain


def signature(words):
    return [(w.text, w.box, w.line) for w in words]


@unittest.skipUnless(shutil.which("tesseract"), "Tesseract unavailable")
class CompatibilityTests(unittest.TestCase):
    def tearDown(self):
        E.POOL.shutdown()

    def test_alpha_png_semantics_match_the_previous_pipeline(self):
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 900, 220)
        cr = cairo.Context(surface)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_source_rgba(0, 0, 0, .75)
        cr.select_font_face("DejaVu Sans")
        cr.set_font_size(26)
        for row in range(4):
            cr.move_to(20, 40 + row * 42)
            cr.show_text("Transparent image: black text on transparent pixels")
        pb = services.surface_to_pixbuf(surface)
        expected = legacy(pb, "eng")
        with patch.object(services, "ocr_language_spec", return_value="eng"):
            actual = textlayer.ocr_pixbuf_words(pb)
        self.assertTrue(expected)
        self.assertEqual(signature(actual), signature(expected))

    def test_default_keeps_words_order_boxes_and_paragraphs_of_previous_pipeline(self):
        for size, cols, dark in [(12, 1, False), (22, 1, False), (14, 2, False), (13, 2, True)]:
            with self.subTest(size=size, cols=cols, dark=dark):
                pb = fixture(size, cols, dark)
                expected = legacy(pb, "eng")
                with patch.object(services, "ocr_language_spec", return_value="eng"):
                    actual = textlayer.ocr_pixbuf_words(pb)
                self.assertEqual(signature(actual), signature(expected))
                self.assertEqual(textlayer.words_text(actual), textlayer.words_text(expected))
                self.assertEqual(textlayer.detect_table(actual), textlayer.detect_table(expected))


if __name__ == "__main__":
    unittest.main()
