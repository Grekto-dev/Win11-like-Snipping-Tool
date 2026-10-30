"""Ciclo de vida do OCR: donos independentes, cancelamento, fallback da CLI, respostas malformadas, worker.

Headless: não usa GTK nem janela. O Tesseract real só é exigido onde o teste precisa de um processo real;
os demais usam processos falsos ou um `tesseract` de script no PATH.
"""
import os
import shutil
import signal
import tempfile
import threading
import time
import unittest
from unittest.mock import MagicMock, patch

import gi
gi.require_version("Gdk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import GdkPixbuf

from captura import ocr_engine as E, ocr_worker as W, services, textlayer

TSV = ("level\tpage_num\tblock_num\tpar_num\tline_num\tword_num\tleft\ttop\twidth\theight\tconf\ttext\n"
       "5\t1\t1\t1\t1\t1\t10\t10\t40\t12\t96\thello\n")


def pixbuf(w=50, h=40):
    pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, False, 8, w, h)
    pb.fill(0xffffffff)
    return pb


class PoolCase(unittest.TestCase):
    def setUp(self):
        E.POOL.shutdown()
        E.POOL.requests.clear()
        E.POOL.cache.clear()
        patcher = patch.object(services, "ocr_language_spec", return_value="eng")
        patcher.start()
        self.addCleanup(patcher.stop)
        self.addCleanup(self._reset)

    def _reset(self):
        E.POOL.requests.clear()
        E.POOL.shutdown()


class OwnerTests(PoolCase):
    def test_owners_are_independent(self):
        a = textlayer.new_ocr_job("A")
        b = textlayer.new_ocr_job("B")
        self.assertFalse(a.cancelled or b.cancelled)
        a2 = textlayer.new_ocr_job("A")                  # novo pedido do MESMO dono cancela o anterior
        self.assertTrue(a.cancelled)
        self.assertFalse(b.cancelled)
        self.assertFalse(a2.cancelled)

    def test_end_job_clears_only_its_owner(self):
        a = textlayer.new_ocr_job("A")
        b = textlayer.new_ocr_job("B")
        a2 = textlayer.new_ocr_job("A")                  # substitui a
        E.end_job(a)                                     # token antigo de A: não toca no pedido vigente
        self.assertIs(E.POOL.requests["A"], a2)
        self.assertIs(E.POOL.requests["B"], b)
        E.end_job(b)
        self.assertNotIn("B", E.POOL.requests)
        self.assertIs(E.POOL.requests["A"], a2)
        E.end_job(a2)
        self.assertNotIn("A", E.POOL.requests)

    def test_cancel_with_token_touches_only_that_job(self):
        a = textlayer.new_ocr_job("A")
        b = textlayer.new_ocr_job("B")
        textlayer.cancel_ocr(a)
        self.assertTrue(a.cancelled)
        self.assertFalse(b.cancelled)

    def test_cancel_without_token_cancels_every_pending_request(self):
        a = textlayer.new_ocr_job("A")
        b = textlayer.new_ocr_job("B")
        textlayer.cancel_ocr()
        self.assertTrue(a.cancelled and b.cancelled)

    def test_none_owner_keeps_the_old_single_request_behaviour(self):
        first = textlayer.new_ocr_job()
        second = textlayer.new_ocr_job()
        self.assertTrue(first.cancelled)
        self.assertFalse(second.cancelled)


class CancelBeforeRunTests(PoolCase):
    def test_cancel_before_execution_never_runs_ocr(self):
        job = textlayer.new_ocr_job("A")
        textlayer.cancel_ocr(job)
        with patch.object(E.POOL, "ensure", side_effect=AssertionError("worker started")), \
             patch.object(E.Proc, "call", side_effect=AssertionError("ocr sent")), \
             patch.object(textlayer, "_ocr_cli", side_effect=AssertionError("cli started")):
            with self.assertRaises(E.Cancelled):
                textlayer.ocr_pixbuf_words(pixbuf(), job)

    def test_cancel_during_worker_failure_does_not_start_the_cli(self):
        job = textlayer.new_ocr_job("A")

        def fail(pb, langs, job, **_options):
            textlayer.cancel_ocr(job)
            raise E.WorkerError("worker-down")

        with patch.object(E, "recognize_pair", side_effect=fail), \
             patch.object(textlayer, "_ocr_cli", side_effect=AssertionError("cli started")):
            with self.assertRaises(E.Cancelled):
                textlayer.ocr_pixbuf_words(pixbuf(), job)
        self.assertNotIn("A", E.POOL.requests)           # o token é encerrado no fim


class FakeTesseract(PoolCase):
    """Um `tesseract` de script no PATH: a CLI real é substituída por um processo controlado."""

    def setUp(self):
        super().setUp()
        self.dir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.pidfile = os.path.join(self.dir, "pid")
        self.tsvfile = os.path.join(self.dir, "out.tsv")
        with open(self.tsvfile, "w") as f:
            f.write(TSV)
        env = patch.dict(os.environ, {"PATH": self.dir + os.pathsep + os.environ.get("PATH", ""),
                                       "PIDFILE": self.pidfile, "TSVFILE": self.tsvfile})
        env.start()
        self.addCleanup(env.stop)

    def script(self, body):
        path = os.path.join(self.dir, "tesseract")
        with open(path, "w") as f:
            f.write("#!/bin/sh\n" + body + "\n")
        os.chmod(path, 0o755)

    def wait_pid(self, limit=5):
        deadline = time.monotonic() + limit
        while time.monotonic() < deadline:
            if os.path.exists(self.pidfile) and os.path.getsize(self.pidfile):
                with open(self.pidfile) as f:
                    return int(f.read())
            time.sleep(.02)
        self.fail("fake tesseract never started")

    def no_worker(self):
        return patch.object(E, "recognize_pair", side_effect=E.WorkerError("worker-down"))


class FallbackTests(FakeTesseract):
    def test_cli_success_returns_words(self):
        self.script('cat "$TSVFILE"; exit 0')
        with self.no_worker():
            words = textlayer.ocr_pixbuf_words(pixbuf())
        self.assertEqual([w.text for w in words], ["hello"])

    def test_cancel_during_cli_kills_and_reaps_the_same_token(self):
        self.script('echo $$ > "$PIDFILE"; exec sleep 30')
        job = textlayer.new_ocr_job("A")
        errors = []

        def read():
            try:
                with self.no_worker():
                    textlayer.ocr_pixbuf_words(pixbuf(), job)
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=read)
        thread.start()
        pid = self.wait_pid()
        before = time.monotonic()
        textlayer.cancel_ocr(job)
        thread.join(3)
        self.assertFalse(thread.is_alive())
        self.assertLess(time.monotonic() - before, 1.5)
        self.assertTrue(errors and isinstance(errors[0], E.Cancelled), errors)
        with self.assertRaises(ProcessLookupError):      # morto E recolhido (reap), não zumbi
            os.kill(pid, 0)
        self.assertEqual(job.procs, [])

    def test_cli_deadline_kills_and_reaps(self):
        self.script('echo $$ > "$PIDFILE"; exec sleep 30')
        with patch.object(textlayer, "CLI_TIMEOUT", .5), self.no_worker():
            started = time.monotonic()
            with self.assertRaises(E.WorkerError) as cm:
                textlayer.ocr_pixbuf_words(pixbuf())
        self.assertLess(time.monotonic() - started, 5)
        self.assertEqual(str(cm.exception), "ocr-cli-timeout")
        with self.assertRaises(ProcessLookupError):
            os.kill(self.wait_pid(), 0)

    def test_cli_nonzero_exit_is_an_error_not_an_empty_result(self):
        self.script('echo "tesseract: broken" >&2; exit 3')
        with self.no_worker(), self.assertRaises(E.WorkerError) as cm:
            textlayer.ocr_pixbuf_words(pixbuf())
        self.assertTrue(str(cm.exception).strip())
        self.assertIn("3", str(cm.exception))

    def test_cli_empty_stdout_with_zero_exit_is_an_error(self):
        self.script('exit 0')
        with self.no_worker(), self.assertRaises(E.WorkerError):
            textlayer.ocr_pixbuf_words(pixbuf())

    def test_malformed_worker_reply_falls_back_to_cli(self):
        self.script('cat "$TSVFILE"; exit 0')
        with patch.object(E, "pool_size", return_value=1), \
             patch.object(E.POOL, "ensure", return_value=[FakeProc({"ok": True})]):
            words = textlayer.ocr_pixbuf_words(pixbuf())
        self.assertEqual([w.text for w in words], ["hello"])

    def test_programming_errors_in_the_fast_path_are_not_swallowed(self):
        self.script('cat "$TSVFILE"; exit 0')
        with patch.object(E, "recognize_pair", side_effect=TypeError("bug")), \
             patch.object(textlayer, "_ocr_cli", side_effect=AssertionError("cli started")):
            with self.assertRaises(TypeError):
                textlayer.ocr_pixbuf_words(pixbuf())


class FakeProc:
    def __init__(self, reply=None, delay=0.0):
        self.reply, self.delay = reply, delay
        self.dead = self.closed = False
        self.calls = []

    def set_image(self, pb):
        self.calls.append("image")

    def call(self, req, payload=b"", timeout=None):
        self.calls.append(req["cmd"])
        if self.delay:
            time.sleep(self.delay)
        if isinstance(self.reply, BaseException):
            raise self.reply
        return self.reply

    def kill(self):
        self.dead = True

    def close(self):
        self.dead = self.closed = True


class MalformedTests(PoolCase):
    def run_with(self, reply):
        fake = FakeProc(reply)
        with patch.object(E, "pool_size", return_value=1), \
             patch.object(E.POOL, "ensure", return_value=[fake]):
            return E.recognize_pair(pixbuf(), "eng")

    def test_malformed_replies_become_worker_errors(self):
        bad = [{"ok": True}, {"ok": True, "words": "x"}, {"ok": True, "words": [["a", 1]]},
               {"ok": True, "words": [["a", 1, 2, 3, 4, "x", 1, 1, 1]]}, {"ok": True, "words": [None]},
               [], "not-a-dict", None]
        for reply in bad:
            with self.subTest(reply=reply), self.assertRaises(E.WorkerError):
                self.run_with(reply)

    def test_well_formed_reply_is_accepted(self):
        sparse, plain, scale = self.run_with({"ok": True, "words": [["hello", 10, 10, 50, 22, 96.0, 1, 1, 1]]})
        self.assertEqual(sparse, [("hello", (10.0, 10.0, 50.0, 22.0), 96.0, (1, 1, 1))])
        self.assertEqual(plain, [("hello", (5.0, 5.0, 25.0, 11.0), 96.0, (1, 1, 1))])   # passe 2x: divide por 2
        self.assertEqual(scale, 2)

    def test_programming_error_from_proc_is_not_wrapped(self):
        with self.assertRaises(TypeError):
            self.run_with(TypeError("bug"))


class IdleTests(PoolCase):
    def test_idle_shutdown_does_not_interrupt_a_running_read(self):
        fake = FakeProc({"ok": True, "words": []}, delay=.4)
        E.POOL.procs = [fake]
        result, errors = [], []

        def read():
            try:
                with patch.object(E, "pool_size", return_value=1), \
                     patch.object(E.POOL, "ensure", return_value=[fake]):
                    result.append(E.recognize_pair(pixbuf(), "eng"))
            except Exception as exc:
                errors.append(exc)

        thread = threading.Thread(target=read)
        thread.start()
        time.sleep(.1)
        E.POOL.shutdown()                                # o timer ocioso dispara durante a leitura
        self.assertFalse(fake.closed)
        self.assertEqual(E.POOL.procs, [fake])
        thread.join(5)
        self.assertEqual(errors, [])
        self.assertTrue(result)
        E.POOL.shutdown()                                # depois de ociosa de verdade, libera
        self.assertTrue(fake.closed)


class WorkerProcessTests(PoolCase):
    def test_init_failure_leaves_the_worker_dead(self):
        proc = E.Proc("xx_no_such_language")
        try:
            with self.assertRaises(E.WorkerError):
                proc.start()
            self.assertTrue(proc.dead)
        finally:
            proc.close()
        self.assertIsNotNone(proc.p.returncode)

    def test_stopped_worker_write_timeout_kills_and_reaps(self):
        proc = E.Proc("eng")
        try:
            os.kill(proc.p.pid, signal.SIGSTOP)          # o worker para de ler o pipe
            with self.assertRaises(E.WorkerError) as cm:
                proc.call({"cmd": "image"}, b"\0" * (8 << 20), timeout=.3)
            self.assertEqual(str(cm.exception), "ocr-write-timeout")
            self.assertTrue(proc.dead)
        finally:
            proc.close()
        self.assertIsNotNone(proc.p.returncode)

    def test_raw_payload_minimum_uses_the_abbreviated_last_row(self):
        w, h, bpp, stride = 10, 7, 4, 44                 # stride com padding
        needed = (h - 1) * stride + w * bpp                 # 304, não stride*h = 308
        W.Worker().set_image(bytes(needed), w, h, bpp, stride)
        with self.assertRaises(ValueError):
            W.Worker().set_image(bytes(needed - 1), w, h, bpp, stride)

    def test_raw_image_dimensions_are_validated(self):
        for w, h, bpp, stride in [(0, 5, 4, 0), (5, 0, 4, 20), (5, 5, 2, 10), (5, 5, 4, 19), (-1, 5, 1, 1)]:
            with self.subTest(args=(w, h, bpp, stride)), self.assertRaises(ValueError):
                W.Worker().set_image(bytes(1 << 12), w, h, bpp, stride)

    def test_recognize_failure_is_a_non_empty_error_and_clears_the_page(self):
        L = MagicMock()
        L.TessBaseAPIRecognize.return_value = 1
        worker = W.Worker()
        worker.h = 1234
        worker.set_image(bytes(4 * 5 * 5), 5, 5, 4, 20)
        with patch.object(W, "lib", return_value=L):
            with self.assertRaises(RuntimeError) as cm:
                worker.ocr(psm=4)
        self.assertTrue(str(cm.exception).strip())
        L.TessBaseAPIClear.assert_called_with(1234)

    def test_init_failure_frees_the_handle(self):
        L = MagicMock()
        L.TessBaseAPICreate.return_value = 4321
        L.TessBaseAPIInit3.return_value = -1
        worker = W.Worker()
        with patch.object(W, "lib", return_value=L), self.assertRaises(RuntimeError):
            worker.init("eng")
        L.TessBaseAPIEnd.assert_called_with(4321)
        L.TessBaseAPIDelete.assert_called_with(4321)
        self.assertIsNone(worker.h)


if __name__ == "__main__":
    unittest.main()
