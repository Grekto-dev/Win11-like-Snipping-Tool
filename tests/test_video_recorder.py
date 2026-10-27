"""Gravação de tela com FFmpeg real (x11grab) — captura, pausa, parada, falhas e limpeza.

Precisa de DISPLAY (use um Xephyr isolado, ex.: Xephyr :19 -screen 1440x900) e de ffmpeg/ffprobe.
Cada teste grava num diretório temporário próprio; nada vai para ~/Vídeos.
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from captura import services

HERE = os.path.dirname(os.path.abspath(__file__))
ANIM = os.path.join(HERE, "animated_window.py")
HAVE_X = bool(os.environ.get("DISPLAY"))
HAVE_FF = bool(shutil.which("ffmpeg") and shutil.which("ffprobe"))
NEED_X = unittest.skipUnless(HAVE_X and HAVE_FF, "precisa de DISPLAY e ffmpeg/ffprobe")


def ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration:stream=codec_type,codec_name,pix_fmt,width,height",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise AssertionError(f"ffprobe falhou em {path}: {r.stderr.strip()}")
    return json.loads(r.stdout)


def duration(path):
    return float(ffprobe(path)["format"]["duration"])


def video_streams(path):
    return [s for s in ffprobe(path)["streams"] if s["codec_type"] == "video"]


def decode_errors(path):
    """Decodifica tudo; devolve o stderr (vazio = arquivo íntegro)."""
    return subprocess.run(["ffmpeg", "-v", "error", "-i", path, "-f", "null", "-"],
                          capture_output=True, text=True).stderr.strip()


def playable(path):
    try:
        return not decode_errors(path) and duration(path) > 0
    except (AssertionError, KeyError, ValueError):
        return False


def fd_count():
    return len(os.listdir("/proc/self/fd"))


class _Base(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="captura-vrec-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.out = os.path.join(self.dir, "clip.mp4")
        self.procs = []
        self.addCleanup(self._reap_all)

    def _reap_all(self):
        for p in self.procs:
            if p.poll() is None:
                p.kill()
            try:
                p.wait(timeout=5)
            except Exception:
                pass

    def rec(self, rect, out=None, mic=False, sysa=False):
        r = services.Recorder(rect, mic, sysa, out or self.out)
        self.addCleanup(self._kill_rec, r)
        return r

    @staticmethod
    def _kill_rec(r):
        if r.proc is not None and r.proc.poll() is None:
            r.proc.kill()
            r.proc.wait(timeout=5)
        r.close()

    def animated(self, x, y, w, h, secs=25):
        p = subprocess.Popen([sys.executable, ANIM, str(x), str(y), str(w), str(h), str(secs)])
        self.procs.append(p)
        time.sleep(1.5)                 # a janela precisa estar mapeada antes de gravar
        return p


@NEED_X
class RealCaptureTests(_Base):
    def test_three_second_capture_of_moving_window_is_valid_h264_yuv420p(self):
        self.animated(100, 100, 301, 201)
        r = self.rec((100, 100, 301, 201))
        self.assertEqual(r.region, (100, 100, 300, 200))       # lados ímpares viram pares
        r.start()
        time.sleep(3.0)
        self.assertTrue(r.stop())
        v = video_streams(self.out)
        self.assertEqual(len(v), 1)
        self.assertEqual((v[0]["codec_name"], v[0]["pix_fmt"], v[0]["width"], v[0]["height"]),
                         ("h264", "yuv420p", 300, 200))
        self.assertTrue(2.4 <= duration(self.out) <= 3.8, duration(self.out))
        self.assertEqual(decode_errors(self.out), "")
        frames = []
        for t in ("0.5", "2.5"):
            raw = subprocess.run(["ffmpeg", "-v", "error", "-ss", t, "-i", self.out, "-frames:v", "1",
                                  "-f", "rawvideo", "-pix_fmt", "rgb24", "-"], capture_output=True).stdout
            frames.append(raw)
        self.assertNotEqual(frames[0], frames[1], "a região gravada deveria mudar (janela animada)")
        self.assertEqual(os.listdir(self.dir), ["clip.mp4"])

    def test_tiny_region_is_rejected_before_spawning_ffmpeg(self):
        r = self.rec((0, 0, 1, 1))
        self.assertIsNone(r.region)
        with self.assertRaises(ValueError):
            r.start()
        self.assertIsNone(r.proc)

    def test_odd_and_minimum_size_regions_record_valid_even_files(self):
        for i, (rect, want) in enumerate([((5, 7, 201, 101), (5, 7, 200, 100)), ((0, 0, 3, 3), (0, 0, 2, 2))]):
            out = os.path.join(self.dir, f"odd{i}.mp4")
            r = self.rec(rect, out=out)
            self.assertEqual(r.region, want)
            r.start()
            time.sleep(1.0)
            self.assertTrue(r.stop())
            self.assertTrue(playable(out))
            v = video_streams(out)[0]
            self.assertEqual((v["width"], v["height"]), want[2:])

    def test_region_touching_bottom_right_corner_records(self):
        size = services.screen_size()
        if size is None:
            self.skipTest("sem tamanho de tela")
        sw, sh = size
        r = self.rec((sw - 3, sh - 3, 3, 3))           # canto: 3x3 colado na borda → 2x2
        self.assertEqual(r.region, (sw - 3, sh - 3, 2, 2))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.stop(), r.failure)
        self.assertTrue(playable(self.out))

    def test_negative_origin_is_clipped_to_desktop_and_records(self):
        r = self.rec((-20, -10, 100, 100))
        self.assertEqual(r.region, (0, 0, 80, 90))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.stop())
        self.assertTrue(playable(self.out), decode_errors(self.out))

    def test_region_larger_than_desktop_is_clipped(self):
        size = services.screen_size()
        if size is None:
            self.skipTest("sem tamanho de tela")
        sw, sh = size
        r = self.rec((1000, 700, 3000, 2000))
        w, h = sw - 1000, sh - 700
        self.assertEqual(r.region, (1000, 700, w - w % 2, h - h % 2))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.stop())
        self.assertTrue(playable(self.out))

    def test_region_fully_outside_desktop_is_rejected(self):
        r = self.rec((5000, 5000, 100, 100))
        self.assertIsNone(r.region)
        with self.assertRaises(ValueError):
            r.start()

    def test_several_pauses_merge_into_one_file_and_leave_no_parts(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.5)
        self.assertTrue(r.resume())
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.4)
        self.assertTrue(r.resume())
        time.sleep(1.0)
        self.assertTrue(r.stop())
        self.assertEqual(os.listdir(self.dir), ["clip.mp4"])
        self.assertTrue(2.3 <= duration(self.out) <= 3.7, duration(self.out))

    def test_very_short_pause_keeps_recording(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.05)
        self.assertTrue(r.resume())
        time.sleep(1.0)
        self.assertTrue(r.stop())
        self.assertTrue(playable(self.out))
        self.assertTrue(1.5 <= duration(self.out) <= 2.6, duration(self.out))

    def test_pause_right_after_start_does_not_lose_the_recording(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(.4)
        self.assertTrue(r.pause())
        time.sleep(.3)
        self.assertTrue(r.resume())
        time.sleep(1.2)
        self.assertTrue(r.stop(), r.failure)
        self.assertTrue(playable(self.out))
        self.assertGreaterEqual(duration(self.out), 1.0)

    def test_stop_while_paused_saves_what_was_recorded(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.2)
        self.assertTrue(r.pause())
        self.assertTrue(r.stop(), r.failure)
        self.assertEqual(os.listdir(self.dir), ["clip.mp4"])
        self.assertTrue(0.8 <= duration(self.out) <= 2.0, duration(self.out))

    def test_pause_and_resume_are_noops_when_not_recording(self):
        r = self.rec((0, 0, 160, 120))
        self.assertFalse(r.pause())
        self.assertFalse(r.resume())
        self.assertFalse(r.stop())            # nada gravado: falha informada, sem exceção
        self.assertFalse(os.path.exists(self.out))

    def test_double_stop_is_safe(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.stop())
        self.assertTrue(r.stop())
        self.assertTrue(playable(self.out))

    def test_killed_ffmpeg_is_reported_and_leaves_no_corrupt_file(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        r.proc.kill()
        r.proc.wait()
        self.assertFalse(r.alive())
        self.assertFalse(r.stop(), "um ffmpeg morto não pode virar 'gravação salva'")
        self.assertTrue(r.failure)
        self.assertEqual(os.listdir(self.dir), [])

    def test_killed_after_pause_keeps_valid_part_and_drops_broken_tail(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.2)
        self.assertTrue(r.resume())
        time.sleep(.8)
        r.proc.kill()
        r.proc.wait()
        self.assertFalse(r.stop())
        self.assertEqual(os.listdir(self.dir), ["clip.parte0.mp4"])
        self.assertTrue(playable(os.path.join(self.dir, "clip.parte0.mp4")))

    def test_discard_while_recording_leaves_no_files(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        r.discard()
        self.assertEqual(os.listdir(self.dir), [])
        self.assertFalse(r.alive())

    def test_discard_after_pause_leaves_no_parts_or_output(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.2)
        self.assertTrue(r.resume())
        time.sleep(.8)
        r.discard()
        self.assertEqual(os.listdir(self.dir), [])

    def test_slow_stop_over_eight_seconds_still_finalizes_and_reaps_process(self):
        sample = os.path.join(self.dir, "sample.mp4")
        subprocess.run(["ffmpeg", "-v", "error", "-f", "lavfi", "-i", "testsrc=duration=1:size=160x120:rate=10",
                        "-c:v", "libx264", "-pix_fmt", "yuv420p", sample], check=True)
        fake = os.path.join(self.dir, "slow-ffmpeg")
        with open(fake, "w") as f:
            # ignora 'q' no stdin; só finaliza ao receber SIGINT, depois de ~9 s (mais que o limite de 8 s)
            f.write('#!/bin/sh\nfor a; do out="$a"; done\n'
                    f'trap \'sleep 1; cp "{sample}" "$out"; exit 0\' INT\n'
                    'sleep 9 & wait\n')
        os.chmod(fake, 0o755)
        out = os.path.join(self.dir, "slow.mp4")
        r = self.rec((0, 0, 160, 120), out=out)
        with patch("captura.services.ffmpeg_path", return_value=fake):
            r.start()
            time.sleep(.3)
            t0 = time.monotonic()
            ok = r.stop()
            elapsed = time.monotonic() - t0
        self.assertTrue(ok, r.failure)
        self.assertGreaterEqual(elapsed, 7.5)
        self.assertIsNotNone(r.proc.poll(), "o processo precisa ser recolhido (sem zumbi)")
        self.assertTrue(playable(out))

    def test_stop_before_first_frame_reports_a_clear_reason(self):
        r = self.rec((0, 0, 160, 120))
        r.start()
        time.sleep(.2)
        self.assertFalse(r.stop())
        self.assertIn("curta demais", r.failure)
        self.assertEqual(os.listdir(self.dir), [])

    def test_names_in_same_second_never_collide(self):
        name = "Gravação de tela 2026-10-27 120000.mp4"
        first = services.unique_path(self.dir, name)
        open(first, "w").close()
        second = services.unique_path(self.dir, name)
        open(second, "w").close()
        third = services.unique_path(self.dir, name)
        self.assertEqual(len({first, second, third}), 3)
        self.assertTrue(second.endswith("(2).mp4"), second)
        self.assertTrue(third.endswith("(3).mp4"), third)

    def test_accented_quoted_path_survives_pause_and_merge(self):
        out = os.path.join(self.dir, "Gravação 'João' & ç \"x\".mp4")
        r = self.rec((0, 0, 160, 120), out=out)
        r.start()
        time.sleep(1.0)
        self.assertTrue(r.pause())
        time.sleep(.2)
        self.assertTrue(r.resume())
        time.sleep(1.0)
        self.assertTrue(r.stop(), r.failure)
        self.assertEqual(os.listdir(self.dir), [os.path.basename(out)])
        self.assertTrue(playable(out))

    def test_ten_start_stop_cycles_leak_no_descriptors_or_processes(self):
        before = fd_count()
        recorders = []
        for i in range(10):
            out = os.path.join(self.dir, f"cycle{i}.mp4")
            r = services.Recorder((0, 0, 160, 120), False, False, out)
            r.start()
            time.sleep(1.0)                 # o ffmpeg leva ~0,5–0,8 s para produzir o primeiro quadro
            if i % 3 == 0:
                r.pause()
                r.resume()
                time.sleep(1.0)
            self.assertTrue(r.stop(), r.failure)
            r.close()
            recorders.append(r)
        self.assertLessEqual(fd_count() - before, 2)
        self.assertTrue(all(r.proc.poll() is not None for r in recorders))
        self.assertTrue(all(r.proc.stdin is None or r.proc.stdin.closed for r in recorders))
        self.assertEqual(sorted(os.listdir(self.dir)), sorted(f"cycle{i}.mp4" for i in range(10)))


@unittest.skipUnless(HAVE_FF, "precisa de ffmpeg/ffprobe")
class FailureModeTests(_Base):
    def _bin_with(self, *names, extra=None):
        """PATH isolado: só os binários pedidos (+ scripts `extra`), sem pactl."""
        bindir = os.path.join(self.dir, "bin")
        os.makedirs(bindir)
        for n in names:
            os.symlink(shutil.which(n), os.path.join(bindir, n))
        for n, body in (extra or {}).items():
            p = os.path.join(bindir, n)
            with open(p, "w") as f:
                f.write("#!/bin/sh\n" + body + "\n")
            os.chmod(p, 0o755)
        return bindir

    def test_audio_tools_missing_records_video_only_and_says_so(self):
        bindir = self._bin_with("ffmpeg", "ffprobe")
        with patch.dict(os.environ, {"PATH": bindir}):
            self.assertEqual(services.missing_audio(True, True), ["microfone", "áudio do sistema"])
            r = self.rec((0, 0, 160, 120), mic=True, sysa=True)
            r.start()
            time.sleep(1.0)
            self.assertTrue(r.stop(), r.failure)
        self.assertEqual([s["codec_type"] for s in ffprobe(self.out)["streams"]], ["video"])

    def test_hanging_pactl_does_not_block_recording_forever(self):
        bindir = self._bin_with("ffmpeg", "ffprobe", extra={"pactl": "sleep 30"})
        with patch.dict(os.environ, {"PATH": bindir}):
            r = self.rec((0, 0, 160, 120), mic=True, sysa=True)
            t0 = time.monotonic()
            r.start()
            self.assertLess(time.monotonic() - t0, 6)
            time.sleep(1.0)
            self.assertTrue(r.stop(), r.failure)
        self.assertTrue(playable(self.out))

    def test_broken_audio_source_is_reported_not_silent(self):
        bindir = self._bin_with("ffmpeg", "ffprobe", extra={
            "pactl": 'case "$1" in get-default-source) echo bogus-mic;; get-default-sink) echo bogus-sink;; esac'})
        with patch.dict(os.environ, {"PATH": bindir}):
            r = self.rec((0, 0, 160, 120), mic=True, sysa=True)
            r.start()
            time.sleep(1.5)
            ok = r.stop()
        # Com o PulseAudio/PipeWire ativo, um nome de fonte inválido costuma cair no padrão do sistema;
        # o contrato é: ou grava (com ou sem áudio) ou informa a falha — nunca um arquivo vazio calado.
        if ok:
            self.assertTrue(playable(self.out))
        else:
            self.assertTrue(r.failure, "falha sem motivo informado")
            self.assertFalse(os.path.exists(self.out))

    def test_disk_full_is_reported_as_failure(self):
        if not os.path.exists("/dev/full"):
            self.skipTest("sem /dev/full")
        link = os.path.join(self.dir, "full.mp4")
        os.symlink("/dev/full", link)            # gravar em /dev/full simula disco cheio (ENOSPC)
        r = self.rec((0, 0, 160, 120), out=link)
        r.start()
        time.sleep(1.0)
        self.assertFalse(r.stop())
        self.assertTrue(r.failure)

    @unittest.skipIf(hasattr(os, "geteuid") and os.geteuid() == 0, "root ignora permissões")
    def test_read_only_output_directory_is_reported_as_failure(self):
        ro = os.path.join(self.dir, "ro")
        os.makedirs(ro)
        os.chmod(ro, 0o555)
        self.addCleanup(os.chmod, ro, 0o755)
        out = os.path.join(ro, "clip.mp4")
        r = self.rec((0, 0, 160, 120), out=out)
        r.start()
        time.sleep(1.0)
        self.assertFalse(r.stop())
        self.assertFalse(os.path.exists(out))

    def test_directory_that_cannot_be_created_raises_on_start_and_stop_is_safe(self):
        blocker = os.path.join(self.dir, "arquivo")
        open(blocker, "w").close()
        out = os.path.join(blocker, "sub", "clip.mp4")
        r = self.rec((0, 0, 160, 120), out=out)
        with self.assertRaises(OSError):
            r.start()
        self.assertIsNone(r.proc)
        self.assertFalse(r.stop())


def _children_of(pid):
    """PIDs de filhos diretos (lidos de /proc; o ffmpeg do gravador é filho do processo de teste)."""
    out = []
    for name in os.listdir("/proc"):
        if not name.isdigit():
            continue
        try:
            with open(f"/proc/{name}/stat", encoding="utf-8") as f:
                stat = f.read()
        except OSError:
            continue
        fields = stat[stat.rindex(")") + 2:].split()
        if int(fields[1]) == pid:                       # campo 4 do stat = ppid
            out.append(int(name))
    return out


def _alive(pid):
    try:
        with open(f"/proc/{pid}/stat", encoding="utf-8") as f:
            state = f.read().rsplit(")", 1)[1].split()[0]
    except OSError:
        return False
    return state != "Z"


@NEED_X
class ProcessLifetimeTests(_Base):
    def test_app_killed_during_recording_leaves_no_orphan_ffmpeg(self):
        """Se o app cair no meio da gravação, o ffmpeg não pode continuar gravando sozinho para sempre."""
        child_py = os.path.join(HERE, "recorder_child.py")
        child = subprocess.Popen([sys.executable, child_py, "0", "0", "160", "120", self.out],
                                 stdout=subprocess.PIPE, text=True)
        self.procs.append(child)
        self.assertEqual(child.stdout.readline().strip(), "started")
        time.sleep(1.5)
        ff = _children_of(child.pid)
        self.assertTrue(ff, "o ffmpeg deveria ser filho do processo do app")
        child.kill()                                    # kill -9 no app
        child.wait()
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline and any(_alive(pid) for pid in ff):
            time.sleep(.1)
        # Garantido: o ffmpeg não sobrevive ao app. (Finalizar o arquivo nesse caso ainda é irregular:
        # o MP4 sem moov pode ficar truncado; ver a nota de MP4 fragmentado no relatório.)
        self.assertFalse(any(_alive(pid) for pid in ff), "ffmpeg órfão continua gravando")
