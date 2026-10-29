"""Even the first --list-langs query must not block GTK."""
import threading
import time
import unittest
from unittest.mock import patch
from captura import textlayer


class WarmupTests(unittest.TestCase):
    def test_language_discovery_is_off_the_calling_thread(self):
        release, entered, warmed = threading.Event(), threading.Event(), threading.Event()
        caller = threading.get_ident()
        lookup_threads = []
        def languages():
            lookup_threads.append(threading.get_ident())
            entered.set()
            release.wait(1)
            return "eng"
        with patch.object(textlayer.services, "ocr_available", return_value=True), \
             patch.object(textlayer.services, "ocr_language_spec", side_effect=languages), \
             patch.object(textlayer.ocr_engine, "warm_up", side_effect=lambda *_args: warmed.set()):
            try:
                before = time.monotonic()
                textlayer.warm_up()
                elapsed = time.monotonic() - before
                self.assertTrue(entered.wait(2))
                self.assertLess(elapsed, .1)
                self.assertNotIn(caller, lookup_threads)
            finally:
                release.set()
                self.assertTrue(warmed.wait(2))


if __name__ == "__main__":
    unittest.main()
