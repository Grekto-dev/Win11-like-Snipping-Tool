"""Persistent, cancellable Tesseract workers without changing the published OCR parameters.

PSM 11 reads the original; PSM 4 reads the original or the same 2x bilinear image
as before. Independent passes may run concurrently, but never split or mask a page.
"""
import hashlib
import json
import os
import select
import subprocess
import sys
import threading
import time

WORKER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ocr_worker.py")
JOB_TIMEOUT = 240
IDLE_SECONDS = 90
CACHE_SIZE = 4


class Cancelled(Exception):
    pass


class WorkerError(Exception):
    pass


def cpu_count():
    try:
        return max(1, len(os.sched_getaffinity(0)))
    except AttributeError:
        return max(1, os.cpu_count() or 1)


def pool_size():
    # Only the two existing, independent passes can run in parallel, not page crops.
    return min(cpu_count(), 2)


class Job:
    """Token de um pedido. Só mata processos enquanto estiver anexado a eles (até `release`)."""

    def __init__(self, owner=None):
        self.owner = owner
        self.cancelled = False
        self.procs = []
        self.lock = threading.Lock()

    def attach(self, proc):
        with self.lock:
            if self.cancelled:
                proc.kill()
                raise Cancelled()
            self.procs.append(proc)

    def detach(self, proc):
        with self.lock:
            if proc in self.procs:
                self.procs.remove(proc)

    def release(self):
        with self.lock:
            self.procs = []                  # workers voltam ao pool: cancelar este token não os toca mais

    def cancel(self):
        with self.lock:                      # kill under the lock: a released worker is never signalled
            self.cancelled = True
            for proc in self.procs:
                proc.kill()                  # signal only; never wait on the GTK thread

    def check(self):
        if self.cancelled:
            raise Cancelled()


class Proc:
    def __init__(self, langs):
        env = dict(os.environ, OMP_THREAD_LIMIT="1", OMP_NUM_THREADS="1", LC_ALL="C")
        self.p = subprocess.Popen([sys.executable, WORKER], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.DEVNULL, env=env, bufsize=0, close_fds=True)
        self.fd = self.p.stdout.fileno()
        os.set_blocking(self.p.stdin.fileno(), False)
        os.set_blocking(self.fd, False)
        self.langs = langs
        self.dead = False
        self.ready = False
        self.lock = threading.Lock()
        self.buf = b""

    def _write(self, data, deadline):
        view = memoryview(data)
        fd = self.p.stdin.fileno()
        while view:
            left = deadline - time.monotonic()
            if left <= 0:
                raise WorkerError("ocr-write-timeout")
            if self.dead:
                raise WorkerError("ocr-worker-unavailable")
            _, writable, _ = select.select([], [fd], [], min(left, .1))
            if writable:
                try:
                    n = os.write(fd, view[:65536])
                except BlockingIOError:
                    continue
                if n <= 0:
                    raise WorkerError("ocr-write-failed")
                view = view[n:]

    def _readline(self, deadline):
        while b"\n" not in self.buf:
            left = deadline - time.monotonic()
            if left <= 0:
                raise WorkerError("ocr-read-timeout")
            if self.dead:
                raise WorkerError("ocr-worker-unavailable")
            readable, _, _ = select.select([self.fd], [], [], min(left, .1))
            if readable:
                try:
                    chunk = os.read(self.fd, 1 << 20)
                except BlockingIOError:
                    continue
                if not chunk:
                    raise WorkerError("ocr-worker-exited")
                self.buf += chunk
        line, _, self.buf = self.buf.partition(b"\n")
        return line

    def call(self, req, payload=b"", timeout=JOB_TIMEOUT):
        with self.lock:
            if self.dead:
                raise WorkerError("ocr-worker-unavailable")
            try:
                deadline = time.monotonic() + timeout
                header = dict(req, n=len(payload)) if payload else req
                self._write(json.dumps(header).encode() + b"\n", deadline)
                if payload:
                    self._write(payload, deadline)
                resp = json.loads(self._readline(deadline))
            except (OSError, ValueError, WorkerError) as exc:
                self.kill()
                raise WorkerError(str(exc) or "ocr-worker-failed") from exc
            if not isinstance(resp, dict):
                self.kill()
                raise WorkerError("ocr-worker-response-error")
            if not resp.get("ok"):
                self.kill()
                raise WorkerError(str(resp.get("error") or "ocr-worker-response-error"))
        return resp

    def start(self):
        self.call({"cmd": "init", "langs": self.langs}, timeout=60)
        self.ready = True

    def set_image(self, pb):
        # SetImage(raw RGBA) ignores alpha, unlike the PNG CLI. Preserve Leptonica's
        # exact PNG alpha treatment, without disk I/O, for transparent captures.
        png = pb.get_has_alpha()
        payload = pb.save_to_bufferv("png", [], [])[1] if png else pb.get_pixels()
        self.call({"cmd": "image", "w": pb.get_width(), "h": pb.get_height(), "bpp": pb.get_n_channels(),
                   "stride": pb.get_rowstride(), "png": png}, payload)

    def kill(self):
        self.dead = True
        try:
            self.p.kill()
        except OSError:
            pass

    def close(self):
        self.kill()
        try:
            self.p.wait(timeout=2)
        except subprocess.TimeoutExpired:
            pass
        for stream in (self.p.stdin, self.p.stdout):
            stream.close()


class Pool:
    def __init__(self):
        self.lock = threading.RLock()
        self.run_lock = threading.Lock()
        self.procs = []
        self.langs = None
        self.requests = {}                   # owner -> newest Job of that owner
        self.timer = None
        self.cache = []

    def new_job(self, owner=None):
        with self.lock:
            previous = self.requests.get(owner)
            if previous is not None:
                previous.cancel()            # só o pedido anterior do MESMO dono
            job = Job(owner)
            self.requests[owner] = job
            return job

    def cancel_current(self, job=None):
        with self.lock:
            jobs = list(self.requests.values()) if job is None else [job]
        for pending in jobs:
            pending.cancel()

    def ensure(self, langs, n, job):
        """Called only while holding run_lock, including during warm-up."""
        job.check()
        if self.langs != langs:
            self._close_workers()
            self.langs = langs
        alive = []
        for proc in self.procs:
            if proc.dead or proc.p.poll() is not None:
                proc.close()
            else:
                alive.append(proc)
        self.procs = alive
        while len(self.procs) < n:
            try:
                proc = Proc(langs)
            except OSError as exc:
                raise WorkerError("ocr-worker-spawn-failed") from exc
            self.procs.append(proc)
            job.attach(proc)                  # cancellation also covers model initialization
            proc.start()
        for proc in self.procs[:n]:
            job.attach(proc)
        job.check()
        return self.procs[:n]

    def _close_workers(self):
        for proc in self.procs:
            proc.close()
        self.procs = []
        self.langs = None

    def shutdown(self):
        # An idle timer must not kill a long-running recognition or a new warm-up.
        if not self.run_lock.acquire(blocking=False):
            self._touch()
            return
        try:
            with self.lock:
                if self.timer:
                    self.timer.cancel()
                    self.timer = None
                self._close_workers()
        finally:
            self.run_lock.release()

    def _touch(self):
        with self.lock:
            if self.timer:
                self.timer.cancel()
            self.timer = threading.Timer(IDLE_SECONDS, self.shutdown)
            self.timer.daemon = True
            self.timer.start()

    def cached(self, key):
        if CACHE_SIZE <= 0:
            return None
        with self.lock:
            for k, value in self.cache:
                if k == key:
                    return value
        return None

    def remember(self, key, value):
        if CACHE_SIZE <= 0:
            return
        with self.lock:
            rest = [(k, v) for k, v in self.cache if k != key]
            self.cache = (rest + [(key, value)])[-CACHE_SIZE:]


POOL = Pool()


def available():
    return os.path.exists(WORKER)


def new_job(owner=None):
    return POOL.new_job(owner)


def end_job(job):
    with POOL.lock:
        if POOL.requests.get(job.owner) is job:      # só o token vigente deste dono; nunca o de outro
            del POOL.requests[job.owner]


def cancel(job=None):
    POOL.cancel_current(job)


def warm_up(langs):
    def work():
        with POOL.run_lock:
            with POOL.lock:
                if POOL.requests:
                    return
            job = Job()
            try:
                POOL.ensure(langs, pool_size(), job)
            except (WorkerError, OSError):
                POOL._close_workers()
            finally:
                job.release()
                POOL._touch()
    threading.Thread(target=work, daemon=True).start()


def image_key(pb, langs, mode):
    h = hashlib.blake2b(digest_size=16)
    h.update(("%d,%d,%d,%d,%s,%s" % (pb.get_width(), pb.get_height(), pb.get_n_channels(),
                                  pb.get_rowstride(), langs, mode)).encode())
    h.update(pb.get_pixels())
    return h.digest()


def _is_number(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def _is_int(v):
    return isinstance(v, int) and not isinstance(v, bool)


def _words_from_reply(resp, scale):
    """Linhas [texto, l, t, r, b, conf, bloco, parágrafo, linha] da resposta do worker, validadas e na escala."""
    rows = resp.get("words") if isinstance(resp, dict) else None
    if not isinstance(rows, list):
        raise WorkerError("ocr-worker-response-error")
    out = []
    for r in rows:
        if not (isinstance(r, list) and len(r) == 9 and isinstance(r[0], str)
                and all(_is_number(v) for v in r[1:6]) and all(_is_int(v) for v in r[6:9])):
            raise WorkerError("ocr-worker-response-error")
        out.append((r[0], tuple(v / scale for v in r[1:5]), r[5], tuple(r[6:9])))
    return out


def _dense_image(pb):
    from gi.repository import GdkPixbuf
    if max(pb.get_width(), pb.get_height()) < 1200:
        return pb.scale_simple(pb.get_width() * 2, pb.get_height() * 2, GdkPixbuf.InterpType.BILINEAR), 2
    return pb, 1


def _token(job):
    if not isinstance(job, Job):
        raise TypeError("the OCR job must come from ocr_engine.new_job()")
    return job


def _execute(pb, langs, mode, job=None, accept_sparse=None):
    owned = job is None
    job = POOL.new_job() if owned else _token(job)
    try:
        job.check()
        # A selected result can omit dense rows; never confuse it with a full
        # pair or with another selector's policy. Keep the callable alive in key.
        key = (image_key(pb, langs, mode), accept_sparse)
        hit = POOL.cached(key)
        if hit is not None:
            job.check()
            return hit
        with POOL.run_lock:
            try:
                job.check()
                count = pool_size() if mode in ("pair", "select") else 1
                procs = POOL.ensure(langs, count, job)
                dense_pb, scale = _dense_image(pb) if mode != "sparse" else (pb, 1)
                result, errors = {}, []

                def read(label, proc, image, psm, factor):
                    try:
                        job.check()
                        proc.set_image(image)
                        result[label] = _words_from_reply(proc.call({"cmd": "ocr", "psm": psm}), factor)
                        job.check()
                    except Exception as exc:     # carried to this thread and re-raised below, never dropped
                        errors.append(exc)

                if mode in ("pair", "select") and len(procs) == 2:
                    sparse = threading.Thread(target=read, args=("sparse", procs[1], pb, 11, 1), daemon=True)
                    sparse.start()
                    read("plain", procs[0], dense_pb, 4, scale)
                    sparse.join()
                else:
                    if mode in ("pair", "select", "sparse"):
                        read("sparse", procs[0], pb, 11, 1)
                    if mode == "select" and not errors and accept_sparse(result["sparse"]):
                        job.check()
                        # Exactly the original winner: no dense output is used.
                        value = (result["sparse"], [], 1)
                        POOL.remember(key, value)
                        return value
                    if mode in ("pair", "select", "page") and not errors:
                        read("plain", procs[0], dense_pb, 4, scale)
                job.check()
                if errors:
                    exc = errors[0]
                    if isinstance(exc, (WorkerError, OSError)):
                        raise WorkerError(str(exc) or "ocr-worker-failed") from exc
                    raise exc                    # programming error: surfaces as itself
                value = (result["sparse"], result["plain"], scale) if mode in ("pair", "select") else (
                    (result["plain"], scale) if mode == "page" else result["sparse"])
                POOL.remember(key, value)
                return value
            except WorkerError:
                job.check()                      # cancelado durante a falha: quem chamou recebe Cancelled
                raise
            finally:
                job.release()                    # workers go back to the pool without this token
                for proc in list(POOL.procs):
                    if proc.dead:
                        proc.close()
                POOL._touch()
    finally:
        if owned:
            end_job(job)


def recognize_pair(pb, langs, job=None, *, accept_sparse=None):
    """Original two passes; on one CPU an exact sparse winner can skip the unused dense pass.

    On a cache miss without a selector, both passes run. With a selector and
    one worker, an accepted sparse result returns (sparse_rows, [], 1): the empty
    dense rows mean "not computed", and 1 is the original sparse coordinate scale.
    The selector must be a stable, pure policy for a given input. With two workers
    the original parallel pair remains unchanged on a cache miss.
    """
    mode = "select" if accept_sparse is not None else "pair"
    return _execute(pb, langs, mode, job, accept_sparse)


def recognize_page(pb, langs, job=None):
    return _execute(pb, langs, "page", job)


def recognize_sparse(pb, langs, scale=1.0, job=None):
    # Kept for callers measuring a single pass. Sparse always reads the original.
    return _execute(pb, langs, "sparse", job)
