"""Fluxo de gravação no CapturaApp com barra/moldura GTK reais e FFmpeg real (precisa de DISPLAY isolado)."""
import os
import shutil
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gi.repository import GLib

from gtkapp import shared_app
from captura import theme
from captura.app import CapturaApp, RecordingBar
from captura.config import settings
from test_video_recorder import decode_errors, duration, ffprobe, HAVE_FF, HAVE_X

NEED = unittest.skipUnless(HAVE_X and HAVE_FF, "precisa de DISPLAY e ffmpeg/ffprobe")


def drain(seconds):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(.005)


def wait_until(pred, timeout=5.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        GLib.MainContext.default().iteration(False)
        time.sleep(.01)
    return pred()


class _AppCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if HAVE_X:
            shared_app()                  # inicializa o GTK (display) como nos outros testes de UI
            theme.apply()

    def setUp(self):
        self.app = CapturaApp()           # sem startup: não mexe em atalhos do desktop
        self.releases = []
        self.app._release = lambda delay_ms=0: self.releases.append(delay_ms)
        self.app.msg = Mock()
        self.notified = []
        p = patch("captura.app.services.notify", side_effect=lambda *a, **k: self.notified.append(a))
        p.start()
        self.addCleanup(p.stop)
        self.scratch = tempfile.mkdtemp(prefix="captura-app-scratch-")
        self.addCleanup(shutil.rmtree, self.scratch, True)
        self.app._rec_scratch_dir = lambda: self.scratch
        self.recdir = tempfile.mkdtemp(prefix="captura-app-rec-")
        self.addCleanup(shutil.rmtree, self.recdir, True)
        for key, value in (("rec_dir", self.recdir), ("rec_autosave", True)):
            old = settings[key]
            settings[key] = value
            self.addCleanup(settings.__setitem__, key, old)
        self.hidden = []

    def window(self):
        w = Mock(name="janela-do-app")
        self.hidden.append(w)
        return w

    def tearDown(self):
        # nada de gravação viva ou barra aberta ao sair
        r = self.app.recorder
        if r is not None:
            self.app.stop_recording(discard=True)
            self.app.wait_stop()
        if self.app.rec_bar is not None or self.app.rec_outline is not None:
            self.app._teardown_rec(0)


class RecordingWindowsTests(_AppCase):
    """Janelas escondidas para a captura precisam voltar em qualquer caminho de falha."""

    def test_missing_ffmpeg_restores_hidden_windows(self):
        w = self.window()
        self.app._rec_hidden = [w]
        with patch("captura.app.services.ffmpeg_path", return_value=None):
            self.app.start_recording((0, 0, 100, 100))
        w.show.assert_called_once()
        self.assertEqual(self.app._rec_hidden, [])
        self.app.msg.assert_called_once()

    def test_region_too_small_is_refused_and_restores_hidden_windows(self):
        w = self.window()
        self.app._rec_hidden = [w]
        with patch("captura.app.services.ffmpeg_path", return_value="/usr/bin/ffmpeg"):
            self.app.start_recording((0, 0, 1, 1))
        self.assertIsNone(self.app.recorder)
        self.assertIsNone(self.app.rec_bar)
        w.show.assert_called_once()
        self.assertEqual(self.releases, [0])
        self.app.msg.assert_called_once()

    def test_failed_begin_restores_hidden_windows(self):
        w = self.window()
        self.app._rec_hidden = [w]
        with patch("captura.app.services.ffmpeg_path", return_value="/usr/bin/ffmpeg"), \
             patch("captura.app.services.Recorder") as cls, \
             patch("captura.app.OutlineWindow"), patch("captura.app.RecordingBar"):
            cls.return_value.start.side_effect = PermissionError("sem permissão")
            self.app.start_recording((0, 0, 100, 100))
            drain(.6)
        w.show.assert_called_once()
        self.assertIsNone(self.app.recorder)
        self.app.msg.assert_called_once()

    @NEED
    def test_windows_stay_hidden_while_recording_and_return_after_stop(self):
        w = self.window()
        self.app._hidden = [w]
        self.app._on_overlay("video", (0, 0, 160, 120), None)
        self.assertIsNotNone(self.app.recorder)
        w.show.assert_not_called()
        self.app.stop_recording()
        self.app.wait_stop()
        w.show.assert_called_once()
        self.assertEqual(self.app._rec_hidden, [])


@NEED
class RealRecordingFlowTests(_AppCase):
    def test_bar_pause_resume_and_stop_saves_one_playable_file(self):
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.rec_bar is not None))
        bar = self.app.rec_bar
        drain(2.5)
        bar.btn_pause.clicked()                           # pausar
        self.assertTrue(self.app.recorder.paused)
        s1 = bar.seconds()
        drain(1.5)
        self.assertEqual(bar.seconds(), s1, "o cronômetro não pode contar durante a pausa")
        bar.btn_pause.clicked()                           # continuar
        self.assertFalse(self.app.recorder.paused)
        drain(2.0)
        self.assertGreater(bar.seconds(), s1)
        bar.btn_stop.clicked()                            # parar
        self.app.wait_stop()
        self.assertIsNone(self.app.rec_bar)
        self.assertEqual(len(self.notified), 1, self.notified)
        files = os.listdir(self.recdir)
        self.assertEqual(len(files), 1, files)
        path = os.path.join(self.recdir, files[0])
        self.assertEqual(decode_errors(path), "")
        # ~2,5 s + ~2,0 s gravados menos a latência de início de cada trecho; os 1,5 s de pausa ficam de fora
        self.assertTrue(2.0 <= duration(path) <= 4.0, duration(path))
        self.assertEqual(ffprobe(path)["streams"][0]["codec_type"], "video")
        self.app.msg.assert_not_called()
        self.assertIn(60000, self.releases)               # hold da captura liberado (com atraso)

    def test_ffmpeg_death_is_reported_and_all_ui_is_cleaned(self):
        w = self.window()
        self.app._rec_hidden = [w]
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.recorder is not None and self.app.recorder.alive()))
        drain(.6)
        bar, outline = self.app.rec_bar, self.app.rec_outline
        rec = self.app.recorder
        rec.proc.kill()
        self.assertTrue(wait_until(lambda: self.app.msg.called, 4.0), "queda do ffmpeg não foi avisada")
        self.assertEqual(self.app.msg.call_args[0][1], "A gravação falhou")
        self.assertIsNone(self.app.recorder)
        self.assertIsNone(self.app.rec_bar)
        self.assertIsNone(self.app.rec_outline)
        self.assertFalse(bar.get_visible(), "a barra de gravação não pode ficar na tela")
        self.assertFalse(outline.get_visible(), "a moldura não pode ficar na tela")
        w.show.assert_called_once()
        self.assertEqual(os.listdir(self.recdir), [], "arquivo corrompido não pode ficar na pasta do usuário")
        self.assertIsNotNone(rec.proc.poll(), "ffmpeg órfão")

    def test_stop_right_after_silent_death_does_not_announce_a_saved_recording(self):
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.recorder is not None and self.app.recorder.alive()))
        drain(.5)
        self.app.recorder.proc.kill()
        drain(.1)
        self.app.stop_recording()                          # antes do _check_rec perceber a queda
        self.app.wait_stop()
        self.assertEqual(self.notified, [], "não pode dizer 'gravação salva' para um arquivo quebrado")
        self.app.msg.assert_called_once()
        self.assertEqual(os.listdir(self.recdir), [])

    def test_stop_within_begin_delay_leaves_nothing_behind(self):
        self.app.start_recording((0, 0, 160, 120))
        self.app.stop_recording()
        self.app.wait_stop()
        drain(.6)
        self.assertEqual(os.listdir(self.recdir), [])
        self.assertEqual(self.notified, [])
        self.assertIsNone(self.app.recorder)

    def test_discard_from_bar_removes_everything(self):
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.rec_bar is not None))
        drain(1.0)
        self.app.rec_bar.btn_trash.clicked()
        self.app.wait_stop()
        self.assertEqual(os.listdir(self.recdir), [])
        self.assertEqual(self.notified, [])

    def test_resume_failure_is_reported_and_recording_stays_paused(self):
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.rec_bar is not None))
        drain(1.0)
        self.assertTrue(self.app._pause_rec(True))
        with patch("captura.services.Recorder._spawn", side_effect=OSError("sem recursos")):
            self.assertFalse(self.app._pause_rec(False))
        self.assertTrue(self.app.recorder.paused)
        self.app.msg.assert_called_once()
        self.app.stop_recording(discard=True)
        self.app.wait_stop()

    def test_stop_twice_from_the_bar_saves_once(self):
        self.app.start_recording((0, 0, 160, 120))
        self.assertTrue(wait_until(lambda: self.app.rec_bar is not None))
        drain(1.5)
        self.app.stop_recording()
        self.app.stop_recording()                         # segundo clique: nada a fazer
        self.app.wait_stop()
        self.assertEqual(len(self.notified), 1, self.notified)
        self.assertEqual(len(os.listdir(self.recdir)), 1)

    def test_pause_is_refused_when_not_recording(self):
        self.assertFalse(self.app._pause_rec(True))
        self.assertFalse(self.app._pause_rec(False))


@NEED
class ChronometerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        shared_app()
        theme.apply()

    def test_stopwatch_ignores_paused_time_and_refused_toggles(self):
        clock = SimpleNamespace(now=1000.0)
        accepted = [True]
        with patch("captura.app.time", SimpleNamespace(time=lambda: clock.now)):
            bar = RecordingBar(lambda: None, lambda: None, (0, 0, 100, 100), on_pause=lambda p: accepted[0])
            self.addCleanup(bar.close_bar)
            clock.now += 5
            self.assertEqual(bar.seconds(), 5)
            bar.toggle_pause()                           # pausa
            clock.now += 7                               # 7 s de pausa
            self.assertEqual(bar.seconds(), 5)
            accepted[0] = False
            bar.toggle_pause()                           # recusada pelo gravador: nada muda
            self.assertTrue(bar.paused)
            accepted[0] = True
            bar.toggle_pause()                           # continua
            clock.now += 2
            self.assertEqual(bar.seconds(), 7)
            bar.tick()
            self.assertEqual(bar.lbl.get_text(), "00:00:07")


class CheckRecTests(_AppCase):
    def test_check_rec_ignores_paused_recorder(self):
        rec = Mock()
        rec.paused = True
        rec.alive.return_value = False
        self.app.recorder = rec
        self.app._check_rec()
        self.app.msg.assert_not_called()
        self.assertIs(self.app.recorder, rec)


if __name__ == "__main__":
    unittest.main()
