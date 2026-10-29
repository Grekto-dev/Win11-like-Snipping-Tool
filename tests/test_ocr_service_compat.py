"""The auxiliary copy-text route must retain its published PSM6 plain-text format."""
import os
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from captura import services
from test_ocr_compat import fixture


@unittest.skipUnless(shutil.which("tesseract"), "Tesseract unavailable")
class AuxiliaryTextCompatibilityTests(unittest.TestCase):
    def test_operational_failure_is_an_error_not_an_empty_recognition(self):
        # Deliberate operational change: an exit failure used to look like 'no text'.
        with tempfile.TemporaryDirectory() as directory:
            executable = os.path.join(directory, "tesseract")
            with open(executable, "w") as stream:
                stream.write("#!/bin/sh\nprintf 'recognizer failed\\n' >&2\nexit 3\n")
            os.chmod(executable, 0o755)
            with patch.dict(os.environ, {"PATH": directory}), \
                 patch.object(services, "ocr_language_spec", return_value="eng"):
                with self.assertRaises(subprocess.CalledProcessError) as error:
                    services.ocr_pixbuf(fixture())
            self.assertEqual(error.exception.returncode, 3)

    def test_copy_text_keeps_psm6_plain_output_including_line_breaks(self):
        for cols in (1, 2):
            with self.subTest(columns=cols):
                pb = fixture(size=14, cols=cols)
                from gi.repository import GdkPixbuf
                if max(pb.get_width(), pb.get_height()) < 1200:
                    pb = pb.scale_simple(pb.get_width() * 2, pb.get_height() * 2, GdkPixbuf.InterpType.BILINEAR)
                with tempfile.TemporaryDirectory() as directory:
                    path = os.path.join(directory, "page.png")
                    pb.savev(path, "png", [], [])
                    expected = subprocess.run(["tesseract", path, "stdout", "--psm", "6", "-l", "eng"],
                                              capture_output=True, text=True, check=True,
                                              env=dict(os.environ, OMP_THREAD_LIMIT="1")).stdout.strip()
                with patch.object(services, "ocr_language_spec", return_value="eng"):
                    actual = services.ocr_pixbuf(fixture(size=14, cols=cols))
                self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
