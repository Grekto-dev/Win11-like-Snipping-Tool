"""Salvar, copiar, notificar, OCR, gravação — operações de apoio da aplicação."""
import ctypes
import datetime
import functools
import os
import shutil
import signal
import subprocess
import tempfile

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk, GdkPixbuf, GLib

from . import i18n
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


BING_UPLOAD = "https://www.bing.com/images/search?view=detailv2&iss=sbiupload&FORM=SBIHMP&sbisrc=ImgDropper&idpbck=1"


def visual_search_page(surface):
    """Cria um HTML temporário com um formulário que envia a imagem (PNG em base64) ao Bing assim que abre no navegador."""
    import base64
    pb = surface_to_pixbuf(surface)
    ok, data = pb.save_to_bufferv("png", [], [])
    if not ok:
        raise RuntimeError(i18n.tr("Falha ao codificar a imagem."))
    d = tempfile.mkdtemp(prefix="captura-bing-")
    path = os.path.join(d, "pesquisa-visual.html")
    html = ('<!doctype html><meta charset="utf-8"><title>Bing</title><body onload="document.forms[0].submit()">'
            '<form method="post" action="%s" enctype="multipart/form-data"><input type="hidden" name="imageBin" value="%s"></form>'
            '<noscript><button form="x">JavaScript necessário</button></noscript></body>' % (BING_UPLOAD, base64.b64encode(bytes(data)).decode()))
    with open(path, "w", encoding="utf-8") as f:
        f.write(html)
    os.chmod(path, 0o600)

    def cleanup():                                                   # a página já foi lida pelo navegador
        shutil.rmtree(d, ignore_errors=True)
        return False
    GLib.timeout_add_seconds(120, cleanup)
    return path


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
            Notify.init(i18n.tr("Ferramenta de Captura"))
            _notify = Notify
        Notify.set_app_name(i18n.tr("Ferramenta de Captura"))          # segue o idioma escolhido, mesmo depois de trocar
        n = Notify.Notification.new(i18n.tr(title), i18n.tr(body), icon or "camera-photo")
        for aid, label, cb in actions or []:
            n.add_action(aid, i18n.tr(label), lambda _n, _a, cb=cb: cb())
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
MIN_REC_SIDE = 2                    # lado mínimo (px) de uma região gravável; o x11grab/libx264 exigem pares ≥ 2


def ffmpeg_path():
    return shutil.which("ffmpeg")


def pulse_sources():
    """(microfone padrão, monitor do sistema) via pactl; (None, None) se o PulseAudio/PipeWire não responder."""
    mic = mon = None
    try:
        mic = subprocess.run(["pactl", "get-default-source"], capture_output=True, text=True, timeout=3).stdout.strip() or None
        sink = subprocess.run(["pactl", "get-default-sink"], capture_output=True, text=True, timeout=3).stdout.strip()
        if sink:
            mon = sink + ".monitor"
    except Exception:
        pass
    return mic, mon


def missing_audio(mic, system_audio):
    """Áudios pedidos sem fonte disponível (rótulos para o aviso). Lista vazia = nada faltando."""
    mic_src, mon_src = pulse_sources() if (mic or system_audio) else (None, None)
    out = []
    if mic and not mic_src:
        out.append("microfone")
    if system_audio and not mon_src:
        out.append("áudio do sistema")
    return out


def screen_size():
    """Tamanho do desktop inteiro (todas as telas) em pixels; None sem display."""
    try:
        root = Gdk.get_default_root_window()
        w, h = root.get_width(), root.get_height()
    except Exception:
        return None
    return (w, h) if w > 0 and h > 0 else None


def clip_region(rect, screen=None):
    """Área gravável (x, y, w, h): recortada ao desktop e com lados pares ≥ MIN_REC_SIDE. None se não sobra nada."""
    x, y, w, h = [int(v) for v in rect]
    if w < 0:
        x, w = x + w, -w
    if h < 0:
        y, h = y + h, -h
    if screen is not None:
        sw, sh = screen
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(sw, x + w), min(sh, y + h)
        x, y, w, h = x0, y0, x1 - x0, y1 - y0
    w -= w % 2
    h -= h % 2
    if w < MIN_REC_SIDE or h < MIN_REC_SIDE:
        return None
    return x, y, w, h


def playable(path):
    """True se o arquivo existe, não está vazio e o ffprobe lê uma duração > 0 (trecho interrompido → False)."""
    try:
        if os.path.getsize(path) <= 0:
            return False
    except OSError:
        return False
    probe = shutil.which("ffprobe")
    if probe is None:
        return True
    try:
        r = subprocess.run([probe, "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", path],
                           capture_output=True, text=True, timeout=30)
        return r.returncode == 0 and float(r.stdout.strip()) > 0
    except (OSError, ValueError, subprocess.SubprocessError):
        return False


def _rm(path):
    try:
        os.remove(path)
    except OSError:
        pass


_PR_SET_PDEATHSIG = 1
try:
    _prctl = ctypes.CDLL(None, use_errno=True).prctl
except (OSError, AttributeError):
    _prctl = None


def _ffmpeg_preexec(parent_pid):
    """Roda no filho antes do exec do ffmpeg: se o app morrer (inclusive kill -9), o kernel manda SIGINT ao
    ffmpeg, que fecha o arquivo. Sem isso o ffmpeg ficava órfão gravando para sempre. Só chama prctl (sem alocações)."""
    if _prctl is not None:
        _prctl(_PR_SET_PDEATHSIG, signal.SIGINT, 0, 0, 0)
    if os.getppid() != parent_pid:                     # o app já tinha morrido antes do prctl
        os._exit(0)


class Recorder:
    """Grava uma região da tela com ffmpeg (x11grab) + áudio PulseAudio/PipeWire.

    Pausar fecha o trecho atual (se ficou tocável) e continuar abre outro. Ao parar, os trechos são unidos
    (concat, sem recodificar). Nada falha em silêncio: `stop()` devolve False e `failure` traz o motivo;
    `abort()` trata a queda do ffmpeg e devolve os trechos íntegros que sobraram."""

    def __init__(self, rect, mic, system_audio, out_path):
        self.region = clip_region(rect, screen_size())   # None: fora da tela ou menor que 2×2 px
        self.mic = mic
        self.system_audio = system_audio
        self.path = out_path
        self.proc = None
        self.log = None
        self.current = None         # arquivo do trecho em gravação
        self.parts = []             # trechos já fechados e tocáveis
        self.paused = False
        self.failure = ""           # motivo da última falha
        self._sources = (None, None)

    def _segment_path(self, n):
        root, ext = os.path.splitext(self.path)
        return f"{root}.parte{n}{ext}"

    def start(self):
        if self.region is None:
            raise ValueError("A área selecionada é pequena demais para gravar (mínimo de 2 × 2 px dentro da tela).")
        if self.mic or self.system_audio:
            self._sources = pulse_sources()
        self._spawn(self.path)

    def _spawn(self, out_path):
        ffmpeg = ffmpeg_path()
        if ffmpeg is None:
            raise RuntimeError("FFmpeg não encontrado")
        x, y, w, h = self.region
        display = os.environ.get("DISPLAY", ":0")
        cmd = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "x11grab", "-framerate", "30",
               "-draw_mouse", "1", "-video_size", f"{w}x{h}", "-i", f"{display}+{x},{y}"]
        mic_src, mon_src = self._sources
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
        if self.log is not None:                           # pausa/retomada: o log do segmento anterior não é mais necessário
            self.log.close()
        self.log = tempfile.TemporaryFile()
        self.current = out_path
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=self.log, stderr=self.log,
                                     preexec_fn=functools.partial(_ffmpeg_preexec, os.getpid()))

    def alive(self):
        return self.proc is not None and self.proc.poll() is None

    def _halt(self):
        """Pede ao ffmpeg que feche o arquivo ('q'); sem resposta, SIGINT; por fim, kill. Devolve o código de saída."""
        p = self.proc
        if p is None:
            return None
        try:
            if p.poll() is None:
                p.stdin.write(b"q")
                p.stdin.flush()
                p.wait(timeout=8)
        except Exception:                                   # pipe quebrado ou ffmpeg lento demais
            try:
                if p.poll() is None:
                    p.send_signal(signal.SIGINT)
                    p.wait(timeout=5)
            except Exception:
                try:
                    p.kill()
                    p.wait(timeout=5)                       # sem wait o kill deixava um zumbi
                except Exception:
                    pass
        finally:
            try:
                if p.stdin is not None:                     # o pipe de comandos (stdin) vazava um descritor por segmento
                    p.stdin.close()
            except Exception:
                pass
        return p.returncode

    def pause(self):
        if self.paused or not self.alive():
            return False
        self._halt()
        self._close_segment()
        self.paused = True
        return True

    def resume(self):
        if not self.paused:
            return False
        self._spawn(self.path)                             # se falhar, o gravador continua pausado e a exceção sobe
        self.paused = False
        return True

    def _close_segment(self):
        """Fecha o trecho atual: se estiver tocável vira parte; senão (vazio/interrompido) é descartado."""
        src = self.current
        if not src or not os.path.exists(src):
            return False
        if playable(src):
            dst = self._segment_path(len(self.parts))
            os.replace(src, dst)
            self.parts.append(dst)
            return True
        _rm(src)
        return False

    def _crash_text(self):
        return self.error_text()[-600:] or "O FFmpeg encerrou inesperadamente."

    def _fail(self, text):
        self.failure = text
        if self.current and os.path.exists(self.current) and self.current not in self.parts:
            _rm(self.current)                              # trecho quebrado nunca fica na pasta do usuário
        return False

    def stop(self):
        """Para e fecha o arquivo. True se o resultado final é tocável; False = falha (motivo em `failure`)."""
        if self.paused:
            return self._merge()
        if self.current is None:                           # nunca foi iniciado
            self.failure = "A gravação não começou."
            return False
        died = self.proc is not None and self.proc.poll() not in (None, 0)   # morreu sozinho (kill, erro de áudio/tela)
        self._halt()
        if died:
            return self._fail(self._crash_text())
        if self.parts:
            self._close_segment()                          # trecho final vazio é descartado; os anteriores estão íntegros
            return self._merge()
        if playable(self.path):
            return True
        err = self.error_text()
        if "received no packets" in err:               # ffmpeg ainda não tinha quadros: parada muito cedo
            return self._fail("A gravação foi curta demais: o FFmpeg ainda não tinha quadros para gravar.")
        return self._fail(err[-600:] or "O FFmpeg não gravou nenhum quadro.")

    def _merge(self):
        """Une os trechos em `path`. Em falha o arquivo final é removido e os trechos ficam em disco (`parts`)."""
        parts = [p for p in self.parts if os.path.exists(p)]
        self.parts = parts
        if not parts:
            self.failure = self.failure or "Nenhum trecho foi gravado."
            return False
        if len(parts) == 1:
            os.replace(parts[0], self.path)
        else:
            err = self._concat(parts)
            if err or not playable(self.path):
                _rm(self.path)
                self.failure = err or "Não foi possível unir os trechos da gravação."
                return False
        for p in parts:
            _rm(p)
        self.parts = []
        return True

    def _concat(self, parts):
        """Une os trechos sem recodificar. Devolve '' se deu certo; senão, o erro do ffmpeg."""
        fd, listing = tempfile.mkstemp(suffix=".txt")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                for p in parts:
                    f.write("file '" + p.replace("'", "'\\''") + "'\n")
            r = subprocess.run([ffmpeg_path(), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
                                "-i", listing, "-c", "copy", self.path], capture_output=True, text=True, timeout=120)
        except (OSError, subprocess.SubprocessError) as e:
            return str(e)
        finally:
            _rm(listing)
        if r.returncode == 0:
            return ""
        return r.stderr.strip()[-600:] or i18n.trf("ffmpeg saiu com código {codigo}", codigo=r.returncode)

    def discard(self):
        """Para e apaga tudo o que esta gravação produziu (trechos e arquivo final)."""
        self._halt()
        for p in [self.current, self.path, *self.parts]:
            if p:
                _rm(p)
        self.parts = []

    def abort(self):
        """ffmpeg caiu durante a gravação: fecha/descarta o trecho quebrado e devolve os trechos íntegros."""
        self._halt()
        self._close_segment()
        return list(self.parts)

    def close(self):
        """Libera o log temporário do FFmpeg (chamar depois de ler `error_text`)."""
        if self.log is not None:
            try:
                self.log.close()
            except Exception:
                pass

    def error_text(self):
        if self.log is None:
            return ""
        try:
            self.log.seek(0)
            return self.log.read().decode("utf-8", "replace").strip()
        except Exception:
            return ""
