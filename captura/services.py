"""Salvar, copiar, notificar, OCR, gravação — operações de apoio da aplicação."""
import datetime
import os
import shutil
import signal
import subprocess
import tempfile

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from .config import settings


def timestamp_name(prefix="Captura de tela", ext="png"):
    return f"{prefix} {datetime.datetime.now():%Y-%m-%d %H%M%S}.{ext}"


def surface_to_pixbuf(surface):
    return Gdk.pixbuf_get_from_surface(surface, 0, 0, surface.get_width(), surface.get_height())


def save_surface(surface, path):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    ext = os.path.splitext(path)[1].lower().lstrip(".")
    pb = surface_to_pixbuf(surface)
    if ext in ("jpg", "jpeg"):
        pb = pb.composite_color_simple(pb.get_width(), pb.get_height(), GdkPixbuf.InterpType.NEAREST, 255, 1, 0xffffffff, 0xffffffff)
        pb.savev(path, "jpeg", ["quality"], ["92"])
    elif ext == "bmp":
        pb.savev(path, "bmp", [], [])
    elif ext == "gif":
        pb.savev(path, "png", [], [])
    else:
        pb.savev(path, "png", [], [])


def unique_path(directory, name):
    p = os.path.join(directory, name)
    if not os.path.exists(p):
        return p
    stem, ext = os.path.splitext(name)
    i = 2
    while os.path.exists(os.path.join(directory, f"{stem} ({i}){ext}")):
        i += 1
    return os.path.join(directory, f"{stem} ({i}){ext}")


def autosave(surface):
    """Salva a captura original na pasta configurada. Devolve o caminho ou None."""
    if not settings["shot_autosave"]:
        return None
    try:
        p = unique_path(settings.shot_directory, timestamp_name())
        save_surface(surface, p)
        return p
    except Exception as e:
        print("falha ao salvar automaticamente:", e)
        return None


_clipboard_keep = []


def copy_surface(surface):
    pb = surface_to_pixbuf(surface)
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_image(pb)
    cb.store()
    _clipboard_keep[:] = [pb]


def copy_html_table(html, text):
    """Coloca a tabela como text/html + texto simples (colar em planilhas/editores)."""
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    targets = [Gtk.TargetEntry.new("text/html", 0, 0), Gtk.TargetEntry.new("UTF8_STRING", 0, 1),
               Gtk.TargetEntry.new("text/plain;charset=utf-8", 0, 1), Gtk.TargetEntry.new("TEXT", 0, 1)]

    def get(_cb, sel, info, _data):
        if info == 0:
            sel.set(Gdk.Atom.intern("text/html", False), 8, html.encode("utf-8"))
        else:
            sel.set_text(text, -1)
    cb.set_with_data(targets, get, lambda *_: None, None)
    cb.store()


def copy_text(text):
    cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
    cb.set_text(text, -1)
    cb.store()


# ------------------------------------------------------------------ notificações
_notify = None
_toasts = []


def notify(title, body, icon=None, actions=None):
    """Notificação do sistema (libnotify). actions = [(id, rótulo, callback)]."""
    try:
        gi.require_version("Notify", "0.7")
        from gi.repository import Notify
        global _notify
        if _notify is None:
            Notify.init("Ferramenta de Captura")
            _notify = Notify
        n = Notify.Notification.new(title, body, icon or "camera-photo")
        for aid, label, cb in actions or []:
            n.add_action(aid, label, lambda _n, _a, cb=cb: cb())
        n.set_hint("desktop-entry", GLib.Variant("s", "captura"))
        n.show()
        _toasts.append(n)
        del _toasts[:-4]
    except Exception as e:
        print("notificação indisponível:", e)


# ------------------------------------------------------------------ OCR
def ocr_available():
    return shutil.which("tesseract") is not None


def ocr_languages():
    try:
        out = subprocess.run(["tesseract", "--list-langs"], capture_output=True, text=True, timeout=5).stdout.split()[1:]
        return [l for l in out if l != "osd"]
    except Exception:
        return []


def ocr_pixbuf(pb):
    """Extrai texto com o tesseract (pt+en quando instalados)."""
    langs = ocr_languages()
    want = [l for l in ("por", "eng") if l in langs] or (langs[:1] if langs else [])
    with tempfile.TemporaryDirectory() as d:
        src = os.path.join(d, "in.png")
        w, h = pb.get_width(), pb.get_height()
        if max(w, h) < 1200:
            pb = pb.scale_simple(w * 2, h * 2, GdkPixbuf.InterpType.BILINEAR)
        pb.savev(src, "png", [], [])
        cmd = ["tesseract", src, "stdout", "--psm", "6"]
        if want:
            cmd += ["-l", "+".join(want)]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return r.stdout.strip()


# ------------------------------------------------------------------ editores externos
EXTERNAL_EDITORS = [("gimp", "GIMP"), ("pinta", "Pinta"), ("krita", "Krita"), ("kolourpaint", "KolourPaint"),
                    ("mypaint", "MyPaint"), ("drawing", "Drawing")]


def external_editor():
    for cmd, label in EXTERNAL_EDITORS:
        if shutil.which(cmd):
            return cmd, label
    return None, None


# ------------------------------------------------------------------ gravação
def ffmpeg_path():
    return shutil.which("ffmpeg")


def pulse_sources():
    """(microfone padrão, monitor do sistema) via pactl."""
    mic = mon = None
    try:
        mic = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True, timeout=3).stdout.strip() or None
        sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=3).stdout.strip()
        if sink:
            mon = sink + ".monitor"
    except Exception:
        pass
    return mic, mon


class Recorder:
    """Grava uma região da tela com ffmpeg (x11grab) + áudio PulseAudio/PipeWire.

    Pausar fecha o trecho atual; continuar abre outro. Ao parar, os trechos são unidos (concat, sem recodificar)."""

    def __init__(self, rect, mic, system_audio, out_path):
        self.rect = rect
        self.mic = mic
        self.system_audio = system_audio
        self.path = out_path
        self.proc = None
        self.log = None
        self.parts = []             # trechos já fechados
        self.paused = False

    def _segment_path(self, n):
        root, ext = os.path.splitext(self.path)
        return f"{root}.parte{n}{ext}"

    def start(self):
        self._spawn(self.path)

    def _spawn(self, out_path):
        x, y, w, h = [int(v) for v in self.rect]
        w -= w % 2
        h -= h % 2
        display = os.environ.get("DISPLAY", ":0")
        cmd = [ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "x11grab", "-framerate", "30",
               "-draw_mouse", "1", "-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}"]
        mic_src, mon_src = pulse_sources()
        n_audio = 0
        if self.mic and mic_src:
            cmd += ["-f", "pulse", "-i", mic_src]
            n_audio += 1
        if self.system_audio and mon_src:
            cmd += ["-f", "pulse", "-i", mon_src]
            n_audio += 1
        if n_audio == 2:
            cmd += ["-filter_complex", "[1:a][2:a]amix=inputs=2:duration=longest[a]", "-map", "0:v", "-map", "[a]"]
        cmd += ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "20", "-pix_fmt", "yuv420p"]
        if n_audio:
            cmd += ["-c:a", "aac", "-b:a", "160k"]
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        cmd.append(out_path)
        self.current = out_path
        self.log = tempfile.TemporaryFile()
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=self.log, stderr=self.log)

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def _halt(self):
        if self.proc is None:
            return
        try:
            if self.alive():
                self.proc.stdin.write(b"q")
                self.proc.stdin.flush()
                self.proc.wait(timeout=8)
        except Exception:
            try:
                self.proc.send_signal(signal.SIGINT)
                self.proc.wait(timeout=5)
            except Exception:
                self.proc.kill()

    def pause(self):
        if self.paused or not self.alive():
            return False
        self._halt()
        first = self._segment_path(len(self.parts))
        if os.path.exists(self.current):
            os.replace(self.current, first)
            self.parts.append(first)
        self.paused = True
        return True

    def resume(self):
        if not self.paused:
            return False
        self.paused = False
        self._spawn(self.path)
        return True

    def stop(self):
        if self.paused:                                    # parado em pausa: só falta unir
            self._merge()
            return
        self._halt()
        if self.parts:
            seg = self._segment_path(len(self.parts))
            if os.path.exists(self.current):
                os.replace(self.current, seg)
                self.parts.append(seg)
            self._merge()

    def _merge(self):
        parts = [p for p in self.parts if os.path.exists(p)]
        try:
            if not parts:
                return
            if len(parts) == 1:
                os.replace(parts[0], self.path)
                return
            listing = self.path + ".txt"
            with open(listing, "w", encoding="utf-8") as f:
                for p in parts:
                    f.write("file '" + p.replace("'", "'\\''") + "'\n")
            subprocess.run([ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                            "-i", listing, "-c", "copy", self.path], capture_output=True, timeout=120)
            try:
                os.remove(listing)
            except OSError:
                pass
        finally:
            for p in self.parts:
                try:
                    os.remove(p)
                except OSError:
                    pass
            self.parts = []

    def error_text(self):
        try:
            self.log.seek(0)
            return self.log.read().decode("utf-8", "replace").strip()
        except Exception:
            return ""
