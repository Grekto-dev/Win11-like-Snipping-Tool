"""Persistent OCR infrastructure; recognition compatibility lives in test_ocr_compat."""
import os
import shutil
import subprocess
import threading
import time
import unittest
from unittest.mock import patch

import cairo
import gi
gi.require_version("Gdk", "3.0")
from captura import ocr_engine as E, services, textlayer

HAVE = bool(shutil.which("tesseract")) and E.available()
LANGS = "eng"


def page(rows=8, cols=1, size=22, w=None, dark=False):
    width = w or 40 + cols * 650
    surface = cairo.ImageSurface(cairo.FORMAT_RGB24, width, 50 + rows * (size * 2))
    cr = cairo.Context(surface)
    cr.set_source_rgb(*((.12, .12, .14) if dark else (1, 1, 1)))
    cr.paint()
    cr.set_source_rgb(*((.85, .85, .88) if dark else (0, 0, 0)))
    cr.select_font_face("DejaVu Sans")
    cr.set_font_size(size)
    for col in range(cols):
        for row in range(rows):
            cr.move_to(20 + col * 650, 30 + size + row * size * 2)
            cr.show_text("The quick brown fox jumps over the lazy dog")
    return surface


def words_of(surface):
    return " ".join(word.text for word in textlayer.ocr_surface(surface))


class PolicyTests(unittest.TestCase):
    def test_scale_matches_the_published_pipeline(self):
        for width, expected in [(800, 2), (1199, 2), (1200, 1), (1920, 1)]:
            pb = services.surface_to_pixbuf(page(rows=2, w=width))
            dense, scale = E._dense_image(pb)
            self.assertEqual(scale, expected)
            self.assertEqual(dense.get_width(), width * expected)

    def test_pool_uses_at_most_two_independent_passes(self):
        for cores in (1, 2, 4, 64):
            with patch.object(E, "cpu_count", return_value=cores):
                self.assertEqual(E.pool_size(), min(cores, 2))

    def test_cache_size_one_does_not_grow_without_bound(self):
        pool = E.Pool()
        with patch.object(E, "CACHE_SIZE", 1):
            for key in range(10):
                pool.remember(key, key)
        self.assertEqual(pool.cache, [(9, 9)])


@unittest.skipUnless(HAVE, "Tesseract unavailable")
class EngineTests(unittest.TestCase):
    def setUp(self):
        E.POOL.cache.clear()

    def tearDown(self):
        E.cancel()
        E.POOL.shutdown()

    def test_worker_matches_cli_words_boxes_lines(self):
        import tempfile
        pb = services.surface_to_pixbuf(page(rows=4, w=1300))
        with tempfile.TemporaryDirectory() as directory:
            path = os.path.join(directory, "page.png")
            pb.savev(path, "png", [], [])
            tsv = subprocess.run(["tesseract", path, "stdout", "--psm", "4", "-l", LANGS, "tsv"],
                                 capture_output=True, text=True, check=True,
                                 env=dict(os.environ, OMP_THREAD_LIMIT="1")).stdout
        cli = textlayer.parse_tsv(tsv)
        rows, scale = E.recognize_page(pb, LANGS)
        self.assertEqual(scale, 1)
        actual = textlayer._words_from_rows(rows)
        self.assertEqual([(w.text, w.box, w.line) for w in actual], [(w.text, w.box, w.line) for w in cli])

    def test_both_published_modes_run_without_masking_or_layout(self):
        modes = []
        real = E.Proc.call
        def spy(proc, req, *args, **kwargs):
            if req["cmd"] in ("ocr", "layout"):
                modes.append((req["cmd"], req.get("psm")))
            return real(proc, req, *args, **kwargs)
        with patch.object(E.Proc, "call", spy):
            words = textlayer.ocr_surface(page(rows=4))
        self.assertTrue(words)
        self.assertCountEqual(modes, [("ocr", 4), ("ocr", 11)])

    def test_workers_limit_openmp_threads(self):
        E.recognize_pair(services.surface_to_pixbuf(page(rows=4)), LANGS)
        for proc in E.POOL.procs:
            with open("/proc/%d/status" % proc.p.pid) as stream:
                status = stream.read()
            threads = int(next(line for line in status.splitlines() if line.startswith("Threads:")).split()[1])
            self.assertLessEqual(threads, 2, status)
            with open("/proc/%d/environ" % proc.p.pid, "rb") as stream:
                env = stream.read().split(b"\0")
            self.assertIn(b"OMP_THREAD_LIMIT=1", env)

    def test_result_is_cached_without_another_worker_call(self):
        pb = services.surface_to_pixbuf(page(rows=4))
        first = E.recognize_pair(pb, LANGS)
        with patch.object(E.Proc, "call", side_effect=AssertionError("cache miss")):
            second = E.recognize_pair(services.surface_to_pixbuf(page(rows=4)), LANGS)
        self.assertIs(first, second)

    def test_one_or_two_workers_return_identical_structured_output(self):
        for dark in (False, True):
            pb = services.surface_to_pixbuf(page(cols=2, rows=8, dark=dark))
            with patch.object(E, "CACHE_SIZE", 0):
                with patch.object(E, "pool_size", return_value=1):
                    one = E.recognize_pair(pb, LANGS)
                E.POOL.shutdown()
                with patch.object(E, "pool_size", return_value=2):
                    two = E.recognize_pair(pb, LANGS)
            self.assertEqual(one, two)

    def test_cancel_is_quick_and_next_request_works(self):
        errors, started = [], threading.Event()
        real = E.Proc.call
        def spy(proc, req, *args, **kwargs):
            if req["cmd"] == "ocr":
                started.set()
            return real(proc, req, *args, **kwargs)
        def read():
            try:
                textlayer.ocr_surface(page(cols=3, rows=40, size=14))
            except Exception as exc:
                errors.append(exc)
        with patch.object(E.Proc, "call", spy), patch.object(textlayer, "_ocr_cli", side_effect=AssertionError("cancelled fallback")):
            thread = threading.Thread(target=read)
            thread.start()
            self.assertTrue(started.wait(10))
            before = time.monotonic()
            textlayer.cancel_ocr()
            self.assertLess(time.monotonic() - before, .2)
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertTrue(errors and isinstance(errors[0], E.Cancelled), errors)
        self.assertIn("quick", words_of(page(rows=2)))

    def test_new_request_cancels_previous_read(self):
        first, started = [], threading.Event()
        real = E.Proc.call
        def spy(proc, req, *args, **kwargs):
            if req["cmd"] == "ocr":
                started.set()
            return real(proc, req, *args, **kwargs)
        def read():
            try:
                textlayer.ocr_surface(page(cols=3, rows=40, size=14))
            except Exception as exc:
                first.append(exc)
        with patch.object(E.Proc, "call", spy):
            thread = threading.Thread(target=read)
            thread.start()
            self.assertTrue(started.wait(10))
            self.assertIn("quick", words_of(page(rows=2)))
            thread.join(10)
        self.assertFalse(thread.is_alive())
        self.assertTrue(first and isinstance(first[0], E.Cancelled), first)

    def test_idle_workers_are_released(self):
        with patch.object(E, "IDLE_SECONDS", .2):
            E.recognize_pair(services.surface_to_pixbuf(page(rows=2)), LANGS)
            self.assertTrue(E.POOL.procs)
            deadline = time.monotonic() + 3
            while E.POOL.procs and time.monotonic() < deadline:
                time.sleep(.05)
        self.assertEqual(E.POOL.procs, [])

    def test_worker_failure_falls_back_to_cli(self):
        with patch.object(E, "recognize_pair", side_effect=E.WorkerError("failed")):
            self.assertIn("quick", words_of(page(rows=2)))

    def test_without_worker_cli_returns_same_structured_words(self):
        surface = page(rows=4)
        fast = textlayer.ocr_surface(surface)
        with patch.object(E, "available", return_value=False):
            slow = textlayer.ocr_surface(surface)
        self.assertEqual([(w.text, w.box, w.line) for w in fast], [(w.text, w.box, w.line) for w in slow])


if __name__ == "__main__":
    unittest.main()
