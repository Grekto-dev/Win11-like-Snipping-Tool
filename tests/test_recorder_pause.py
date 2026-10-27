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
        r.close()
        self.assertTrue(os.path.exists(out))
        self.assertEqual(sorted(os.listdir(d)), ["clip.mp4"])
        dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", out],
                                   capture_output=True, text=True).stdout.strip())
        self.assertGreater(dur, 1.6)
        self.assertLess(dur, 3.6)               # a pausa de 0,5 s não entra no vídeo

    def test_stop_closes_the_command_pipe_and_pause_resume_does_not_leak_descriptors(self):
        import time
        d = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, d, True)
        out = os.path.join(d, "clip.mp4")
        before = len(os.listdir("/proc/self/fd"))
        r = services.Recorder((0, 0, 160, 120), False, False, out)
        r.start()
        time.sleep(.8)
        for _ in range(2):
            r.pause(); r.resume(); time.sleep(.5)
        proc = r.proc
        r.stop()
        self.assertTrue(proc.stdin.closed)
        r.close()
        self.assertLessEqual(len(os.listdir("/proc/self/fd")) - before, 1)      # no máximo o descritor do ffprobe/py temporário


if __name__ == "__main__":
    unittest.main()
