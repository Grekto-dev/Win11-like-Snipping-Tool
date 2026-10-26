import os
import shutil
import subprocess
import tempfile
import unittest

from captura import services


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe") and os.environ.get("DISPLAY"), "ffmpeg/DISPLAY ausentes")
class RecorderPauseTests(unittest.TestCase):
    def test_pause_resume_produces_one_merged_file_without_leftovers(self):
        import time
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        out = os.path.join(d, "clip.mp4")
        r = services.Recorder((0, 0, 160, 120), False, False, out)
        r.start()
        time.sleep(1.2)
        self.assertTrue(r.pause())
        self.assertTrue(r.paused)
        time.sleep(.5)
        self.assertTrue(r.resume())
        time.sleep(1.2)
        r.stop()
        self.assertTrue(os.path.exists(out))
        self.assertEqual(sorted(os.listdir(d)), ["clip.mp4"])
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                                   capture_output=True, text=True).stdout.strip())
        self.assertGreater(dur, 1.6)
        self.assertLess(dur, 3.6)               # a pausa de 0,5 s não entra no vídeo


if __name__ == "__main__":
    unittest.main()
