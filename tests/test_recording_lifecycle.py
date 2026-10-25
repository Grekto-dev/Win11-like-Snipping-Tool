"""Recording-state regressions, with external recorder/UI boundaries replaced."""
import pathlib
import tempfile
import time
import unittest
from unittest.mock import Mock, patch
from gi.repository import GLib
from captura.app import CapturaApp
from captura.config import settings


def drain(seconds):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(.001)


class RecordingLifecycleTests(unittest.TestCase):
    def setUp(self):
        self.app = CapturaApp()  # no startup: never changes desktop keybindings
        self.releases = []
        self.app._release = lambda delay_ms=0: self.releases.append(delay_ms)
        self.app.msg = Mock()
        self.scratch = tempfile.TemporaryDirectory(prefix='captura-rec-scratch-')
        self.addCleanup(self.scratch.cleanup)
        self.app._rec_scratch_dir = lambda: self.scratch.name
        self.temp = tempfile.TemporaryDirectory(prefix='captura-recording-tests-')
        self.addCleanup(self.temp.cleanup)
        old = settings['rec_dir']
        settings['rec_dir'] = self.temp.name
        self.addCleanup(lambda: settings.__setitem__('rec_dir', old))

    def _record(self, autosave, fake_file=b"video"):
        """Runs start→stop with a fake recorder that really writes its output file."""
        old = settings['rec_autosave']
        settings['rec_autosave'] = autosave
        self.addCleanup(lambda: settings.__setitem__('rec_autosave', old))
        created = {}

        def make(rect, mic, system, dest):
            created['dest'] = dest
            r = Mock()
            r.alive.return_value = True
            r.stop.side_effect = lambda: pathlib.Path(dest).write_bytes(fake_file)
            return r
        self.notified = []
        patches = [patch('captura.app.services.ffmpeg_path', return_value='/usr/bin/ffmpeg'),
                   patch('captura.app.services.Recorder', side_effect=make),
                   patch('captura.app.OutlineWindow'), patch('captura.app.RecordingBar'),
                   patch('captura.app.services.notify', side_effect=lambda *a, **k: self.notified.append(a))]
        for p in patches:
            p.start(); self.addCleanup(p.stop)
        self.app.start_recording((0, 0, 100, 100))
        self.app.stop_recording()
        return created['dest']

    def test_autosave_on_keeps_recording_in_configured_folder(self):
        import os
        dest = self._record(True)
        self.assertEqual(os.path.dirname(dest), self.temp.name)
        self.assertTrue(os.path.exists(dest))
        self.assertEqual(len(self.notified), 1)

    def test_autosave_off_records_outside_folder_and_saves_only_on_confirmation(self):
        import os
        chosen = os.path.join(self.temp.name, 'meu-video.mp4')
        self.app.ask_save_recording = lambda tmp: chosen
        dest = self._record(False)
        self.assertNotEqual(os.path.dirname(dest), self.temp.name)
        self.assertFalse(os.path.exists(dest), 'o temporário deve ser movido')
        self.assertEqual(pathlib.Path(chosen).read_bytes(), b'video')

    def test_autosave_off_discarded_recording_leaves_no_file(self):
        import os
        self.app.ask_save_recording = lambda tmp: None
        dest = self._record(False)
        self.assertFalse(os.path.exists(dest))
        self.assertEqual(os.listdir(self.temp.name), [])
        self.assertEqual(self.notified, [])

    def test_start_exception_closes_ui_and_releases_hold(self):
        recorder = Mock()
        recorder.start.side_effect = PermissionError('cannot create output')
        self.app.recorder = recorder
        bar, outline = Mock(), Mock()
        self.app.rec_bar, self.app.rec_outline = bar, outline
        self.assertIs(self.app._begin_rec(), False)
        recorder.stop.assert_called_once()
        bar.close_bar.assert_called_once()
        outline.destroy.assert_called_once()
        self.assertIsNone(self.app.recorder)
        self.assertEqual(self.releases, [0])
        self.app.msg.assert_called_once()

    def test_missing_ffmpeg_releases_capture_hold(self):
        with patch('captura.app.services.ffmpeg_path', return_value=None):
            self.app.start_recording((0, 0, 100, 100))
        self.assertEqual(self.releases, [0])
        self.app.msg.assert_called_once()
        self.assertIsNone(self.app.recorder)

    def test_restart_during_countdown_does_not_start_new_recorder_twice(self):
        first, second = Mock(), Mock()
        first.alive.return_value = second.alive.return_value = True
        with patch('captura.app.services.ffmpeg_path', return_value='/usr/bin/ffmpeg'), \
             patch('captura.app.services.Recorder', side_effect=[first, second]), \
             patch('captura.app.OutlineWindow'), patch('captura.app.RecordingBar'):
            self.app.start_recording((0, 0, 100, 100))
            self.app.stop_recording(discard=True)
            self.app.start_recording((0, 0, 100, 100))
            try:
                drain(.5)
                self.assertEqual(first.start.call_count, 0)
                self.assertEqual(second.start.call_count, 1)
            finally:
                self.app.stop_recording(discard=True)

    def test_begin_after_teardown_is_a_noop(self):
        self.app.recorder = None
        self.assertIs(self.app._begin_rec(), False)


if __name__ == '__main__': unittest.main()
