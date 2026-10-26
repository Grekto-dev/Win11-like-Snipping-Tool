"""Aplicação: instância única (D-Bus), fluxos de captura, gravação, OCR, cor, notificações."""
import os
import shutil
import subprocess
import sys
import threading
import time

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, Gio, GLib

from . import APP_ID, APP_NAME, grab, icons, keybindings, services, theme
from .config import settings
from .overlay import Overlay
from .window import EditorWindow


class CountdownWindow(Gtk.Window):
    """Contagem regressiva exibida no topo da tela antes de uma captura com atraso."""

    def __init__(self, seconds, on_done):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.left = seconds
        self.on_done = on_done
        self.set_app_paintable(True)
        self.set_visual(self.get_screen().get_rgba_visual())
        self.set_keep_above(True)
        self.set_default_size(220, 84)
        self.da = Gtk.DrawingArea()
        self.da.connect("draw", self.draw)
        self.add(self.da)
        x, y, w, h = grab.monitor_at(*grab.pointer_position())
        self.move(x + (w - 220) // 2, y + 24)
        self.show_all()
        GLib.timeout_add(1000, self.tick)

    def draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        pal = theme.palette()
        r = 12
        cr.new_sub_path()
        W, H = 220, 84
        cr.arc(W - r, r, r, -1.5708, 0); cr.arc(W - r, H - r, r, 0, 1.5708)
        cr.arc(r, H - r, r, 1.5708, 3.1416); cr.arc(r, r, r, 3.1416, 4.7124); cr.close_path()
        cr.set_source_rgba(*annot_rgb(pal["card"]), 0.97)
        cr.fill_preserve()
        cr.set_source_rgba(*annot_rgb(pal["border2"]), 1)
        cr.set_line_width(1)
        cr.stroke()
        cr.set_source_rgb(*annot_rgb(pal["text"]))
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_BOLD)
        cr.set_font_size(30)
        t = str(self.left)
        e = cr.text_extents(t)
        cr.move_to(W / 2 - e.width / 2 - e.x_bearing, 40)
        cr.show_text(t)
        cr.set_font_size(11)
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        t = "Capturando em instantes…"
        e = cr.text_extents(t)
        cr.move_to(W / 2 - e.width / 2 - e.x_bearing, 66)
        cr.show_text(t)

    def tick(self):
        self.left -= 1
        if self.left <= 0:
            self.destroy()
            GLib.timeout_add(120, lambda: (self.on_done(), False)[1])
            return False
        self.da.queue_draw()
        return True


def annot_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


class RecordingBar(Gtk.Window):
    """Barra de gravação (medida no Windows 11): [pausar] [parar] 00:00:00 [mic] [áudio] | [descartar]; 258x48."""
    W, H = 258, 48
    BOXES = dict(pause=(4, 8, 32, 32), stop=(44, 8, 32, 32), mic=(148, 8, 32, 32), audio=(180, 8, 32, 32), trash=(221, 8, 32, 32))

    def __init__(self, on_stop, on_discard, rect, on_pause=None):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.elapsed = 0.0
        self.t_run = time.time()
        self.paused = False
        self.on_pause = on_pause
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis is not None:
            self.set_visual(vis)
        self.set_accept_focus(False)
        self.set_keep_above(True)
        self.get_style_context().add_class("cap-window")
        frame = Gtk.EventBox()
        frame.set_visible_window(True)
        frame.get_style_context().add_class("ov-bar")
        frame.set_size_request(self.W, self.H)
        fx = Gtk.Fixed()
        frame.add(fx)
        self.add(frame)
        col = theme.icon_color()
        self.col = col

        def mk(name, icon, tip, cb, css=()):
            x, y, w, h = self.BOXES[name]
            btn = Gtk.Button()
            ctx = btn.get_style_context()
            ctx.add_class("ov-btn")
            for c in css:
                ctx.add_class(c)
            btn.set_size_request(w, h)
            btn.set_can_focus(False)
            btn.add(icons.image(icon, 20, "#b4b4b4" if icon.endswith("_off") and name == "mic" else col))
            btn.set_tooltip_text(tip)
            btn.get_accessible().set_name(tip)
            btn.connect("clicked", lambda *_: cb())
            fx.put(btn, x, y)
            return btn
        self.btn_pause = mk("pause", "pause", "Pausar", self.toggle_pause)
        self.btn_stop = mk("stop", "rec_stop", "Parar gravação", on_stop)
        self.lbl = Gtk.Label(label="00:00:00")
        self.lbl.get_style_context().add_class("ov-time")
        self.lbl.get_style_context().add_class("rec")
        fx.put(self.lbl, 85, 14)
        mic_on, sys_on = settings["rec_mic"], settings["rec_system_audio"]
        self.btn_mic = mk("mic", "mic_on" if mic_on else "mic_off", "Microfone", lambda: None)
        self.btn_audio = mk("audio", "screen_audio" if sys_on else "screen_audio_off", "Áudio do computador", lambda: None)
        sep = Gtk.Box()
        sep.get_style_context().add_class("ov-sep")
        sep.set_size_request(1, 24)
        fx.put(sep, 217, 12)
        self.btn_trash = mk("trash", "trash", "Descartar", on_discard)
        self.show_all()
        x, y, w, h = rect
        mx, my, mw, mh = grab.monitor_at(x + w // 2, y + h // 2)
        self.move(mx + (mw - self.W) // 2, my + 13)
        self.timer = GLib.timeout_add(250, self.tick)

    def seconds(self):
        return int(self.elapsed + (0 if self.paused else time.time() - self.t_run))

    def toggle_pause(self):
        if self.on_pause is not None and not self.on_pause(not self.paused):
            return
        if self.paused:
            self.paused = False
            self.t_run = time.time()
        else:
            self.elapsed += time.time() - self.t_run
            self.paused = True
        icon = "play" if self.paused else "pause"
        self.btn_pause.get_child().set_from_pixbuf(icons.pixbuf(icon, 20, self.col))
        self.btn_pause.set_tooltip_text("Continuar" if self.paused else "Pausar")
        self.tick()

    def tick(self):
        s = self.seconds()
        self.lbl.set_text(f"{s // 3600:02d}:{s % 3600 // 60:02d}:{s % 60:02d}")
        return True

    def close_bar(self):
        GLib.source_remove(self.timer)
        self.destroy()


class OutlineWindow(Gtk.Window):
    """Moldura pontilhada rosa de 2 px ao redor da região gravada, fora da área capturada (medido no Windows 11)."""
    PAD = 2

    def __init__(self, rect):
        super().__init__(type=Gtk.WindowType.POPUP)
        x, y, w, h = rect
        p = self.PAD
        self.set_app_paintable(True)
        self.set_visual(self.get_screen().get_rgba_visual())
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_default_size(w + 2 * p, h + 2 * p)
        self.W, self.H = w + 2 * p, h + 2 * p
        self.connect("draw", self.draw)
        self.move(x - p, y - p)
        self.show_all()
        reg = cairo.Region()
        self.input_shape_combine_region(reg)
        # formato real da janela: sem compositor o interior transparente viraria um retângulo preto sobre a gravação
        shape = cairo.Region()
        for x, y, w_, h_ in self.rects():
            shape.union(cairo.RectangleInt(x, y, w_, h_))
        self.shape_combine_region(shape)

    def rects(self):
        """Pixels ligados da moldura: 2 px ligado / 2 px desligado nas quatro bordas."""
        p, W, H = self.PAD, self.W, self.H
        out = []
        for k in range(W):
            if (k + 3) % 4 < 2 or k < p or k >= W - p:
                out.append((k, 0, 1, p))
                out.append((k, H - p, 1, p))
        for k in range(p, H - p):
            if (k + 1) % 4 < 2:
                out.append((0, k, p, 1))
                out.append((W - p, k, p, 1))
        return out

    def draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        cr.set_source_rgb(0.749, 0.408, 0.506)             # #bf6881
        cr.set_antialias(cairo.ANTIALIAS_NONE)
        for x, y, w_, h_ in self.rects():
            cr.rectangle(x, y, w_, h_)
        cr.fill()


class CapturaApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.windows = []
        self.overlay = None
        self.recorder = None
        self.rec_bar = None
        self.rec_outline = None
        self.rec_dest = None
        self._rec_begin_id = 0
        self._rec_check_id = 0
        self.capturing = False
        self.add_main_option("snip", ord("s"), 0, 0, "Abre a sobreposição de captura", None)
        self.add_main_option("ocr", 0, 0, 0, "Extrator de texto", None)
        self.add_main_option("color", 0, 0, 0, "Seletor de cores", None)
        self.add_main_option("record", 0, 0, 0, "Gravação de tela", None)
        self.add_main_option("settings", 0, 0, 0, "Abre as Configurações", None)
        self.add_main_option("background", 0, 0, 0, "Fica residente, sem janela", None)
        self.add_main_option("fullscreen", 0, 0, 0, "Captura a tela inteira imediatamente", None)

    # ------------------------------------------------------------ ciclo
    def do_startup(self):
        Gtk.Application.do_startup(self)
        theme.apply()
        Gtk.Settings.get_default().connect("notify::gtk-theme-name", lambda *a: self.apply_theme())
        try:
            self.exe = os.path.abspath(sys.argv[0])
            cmd = os.path.expanduser("~/.local/bin/captura") + " --snip" if os.path.exists(os.path.expanduser("~/.local/bin/captura")) else self.exe + " --snip"
            keybindings.ensure_snip_binding(cmd)
        except Exception as e:
            print("atalho global não configurado:", e)

    def do_command_line(self, cl):
        opts = cl.get_options_dict().end().unpack()
        files = [f for f in cl.get_arguments()[1:] if not f.startswith("-")]
        if "background" in opts:
            self.hold()
            return 0
        if "settings" in opts:
            w = self.get_window()
            w.show_page("settings")
            w.present()
        elif "snip" in opts:
            self.start_capture("snip", 0)
        elif "ocr" in opts:
            self.start_capture("ocr", 0)
        elif "color" in opts:
            self.start_capture("color", 0)
        elif "record" in opts:
            settings["mode"] = "video"
            self.start_capture("snip", 0)
        elif "fullscreen" in opts:
            settings["shape"] = "fullscreen"
            self.start_capture("snip", 0)
        elif files:
            w = self.get_window(new=settings["shot_multi_window"])
            w.open_file(files[0])
        else:
            self.get_window().present()
        return 0

    def get_window(self, new=False):
        self.windows = [w for w in self.windows if w.get_realized() or w.get_visible()]
        if new or not self.windows:
            w = EditorWindow(self)
            w.connect("destroy", lambda ww: self._window_gone(ww))
            self.windows.append(w)
            mx, my, mw, mh = grab.monitor_at(*grab.pointer_position())
            w.move(mx + max(0, (mw - 1000) // 2), my + max(0, (mh - 700) // 3))
            w.show()
            return w
        return self.windows[-1]

    def _window_gone(self, w):
        if w in self.windows:
            self.windows.remove(w)

    def apply_theme(self):
        theme.apply()
        for w in self.windows:
            w.retheme()
            w.queue_draw()

    # ------------------------------------------------------------ captura
    def start_capture(self, tool="snip", delay=0, from_app=False):
        if self.capturing or self.recorder is not None:
            return
        self.capturing = True
        self.hold()
        self._held = getattr(self, "_held", 0) + 1
        self._from_app = from_app
        self._hidden = [w for w in self.windows if w.get_visible()]
        for w in self._hidden:
            w.hide()
        if delay and tool == "snip":
            GLib.timeout_add(150, lambda: (CountdownWindow(delay, lambda: self._grab_and_show(tool)), False)[1])
        else:
            # dá tempo para a animação de fechar a janela terminar antes de congelar a tela
            GLib.timeout_add(480 if self._hidden else 80, lambda: (self._grab_and_show(tool), False)[1])

    def _grab_and_show(self, tool):
        try:
            surf = grab.grab_screen()
        except Exception as e:
            self.capturing = False
            services.notify("Ferramenta de Captura", f"Não foi possível capturar a tela: {e}")
            self._restore_windows()
            self._release()
            return
        self.overlay = Overlay(surf, lambda kind, payload: self._on_overlay(kind, payload, surf), tool)
        self.overlay.present_grabbed()

    def _restore_rec_windows(self):
        for w in getattr(self, "_rec_hidden", []):
            w.show()
        self._rec_hidden = []

    def _restore_windows(self):
        for w in self._hidden:
            w.show()
        self._hidden = []

    def _release(self, delay_ms=0):
        """Libera o hold da captura; o processo só encerra se não restar janela, gravação ou notificação."""
        if getattr(self, "_held", 0) > 0:
            self._held -= 1
            if delay_ms:
                GLib.timeout_add(delay_ms, lambda: (self.release(), False)[1])
            else:
                self.release()

    def _on_overlay(self, kind, payload, surf):
        try:
            self._on_overlay_inner(kind, payload, surf)
        finally:
            if kind == "video":
                pass                       # o hold da gravação é liberado em stop_recording/falha
            elif kind == "cancel":
                self._release()
            else:
                self._release(60000)       # mantém o processo vivo p/ ações das notificações

    def _on_overlay_inner(self, kind, payload, surf):
        self.capturing = False
        self.overlay = None
        if kind == "cancel":
            self._restore_windows()
            return
        if kind == "color":
            services.copy_text(payload)
            self._restore_windows_if_app()
            services.notify("Seletor de cores", f"A cor {payload} foi copiada para a área de transferência.", "applications-graphics")
            return
        if kind == "ocr":
            self._restore_windows_if_app()
            self.run_ocr(payload)
            return
        if kind == "video":
            self._rec_hidden, self._hidden = list(self._hidden), []      # reaparecem quando a gravação terminar
            self.start_recording(payload)
            return
        self.handle_image(payload)

    def _restore_windows_if_app(self, show=True):
        if show and self._hidden:
            self._restore_windows()
        self._hidden = []

    def handle_image(self, pb):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
        cr = cairo.Context(surf)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        border = (settings["shot_border_color"], settings["shot_border_width"]) if settings["shot_border"] else None
        out = surf
        if border:
            from . import annot
            out = annot.render(surf, [], border)
        services.copy_surface(out)
        path = services.autosave(out)
        open_editor = self._from_app or settings["quick_markup"] or bool(self._hidden)
        self._hidden = []
        if open_editor:
            w = self.get_window(new=settings["shot_multi_window"] and bool(self.windows) and self.windows[-1].canvas.base is not None)
            w.load_surface(surf if not border else surf, new_capture=True, path=path)
            return
        body = "Salvo automaticamente na pasta de capturas de tela." if path else "Copiado para a área de transferência."
        def open_it():
            w = self.get_window(new=settings["shot_multi_window"] and bool(self.windows) and self.windows[-1].canvas.base is not None)
            w.load_surface(surf, new_capture=True, path=path)
        services.notify("Captura de tela salva", body + "\nSelecione para marcar e compartilhar.", path or "camera-photo",
                        [("default", "Marcar e compartilhar", open_it)])

    # ------------------------------------------------------------ OCR
    def run_ocr(self, pb, parent=None):
        if not services.ocr_available():
            self.msg(parent, "Extrator de Texto indisponível",
                     "O Extrator de Texto usa o Tesseract OCR, que não está instalado.\n\nInstale com:\n  sudo apt install tesseract-ocr tesseract-ocr-por tesseract-ocr-eng")
            return

        def work():
            try:
                text = services.ocr_pixbuf(pb)
            except Exception as e:
                text = ""
                GLib.idle_add(self.msg, parent, "Falha ao extrair o texto", str(e))
                return
            GLib.idle_add(self._ocr_done, text, parent)
        threading.Thread(target=work, daemon=True).start()

    def _ocr_done(self, text, parent):
        if not text:
            services.notify("Extrator de Texto", "Nenhum texto foi encontrado na região selecionada.")
            return False
        services.copy_text(text)
        services.notify("Extrator de Texto", "O texto foi copiado para a área de transferência.\n" + (text[:90] + "…" if len(text) > 90 else text), "edit-copy")
        return False

    def ocr_current(self, win):
        s = win.current_surface()
        if s is not None:
            self.run_ocr(services.surface_to_pixbuf(s), win)

    def msg(self, parent, title, text):
        d = Gtk.MessageDialog(parent=parent, flags=0, message_type=Gtk.MessageType.INFO, buttons=Gtk.ButtonsType.CLOSE, text=title)
        d.format_secondary_text(text)
        d.run()
        d.destroy()
        return False

    # ------------------------------------------------------------ gravação
    def start_recording(self, rect):
        if not services.ffmpeg_path():
            self._release()
            self.msg(None, "FFmpeg não encontrado", "A gravação de tela precisa do FFmpeg.\n\nInstale com:\n  sudo apt install ffmpeg")
            return
        d = settings.rec_directory if settings["rec_autosave"] else self._rec_scratch_dir()
        name = services.timestamp_name("Gravação de tela", "mp4")
        self.rec_dest = services.unique_path(d, name)
        self.recorder = services.Recorder(rect, settings["rec_mic"], settings["rec_system_audio"], self.rec_dest)
        self.rec_rect = rect
        self.rec_outline = OutlineWindow(rect)
        self.rec_bar = RecordingBar(self.stop_recording, lambda: self.stop_recording(discard=True), rect, on_pause=self._pause_rec)
        self._rec_begin_id = GLib.timeout_add(350, self._begin_rec)

    def _begin_rec(self):
        self._rec_begin_id = 0
        if self.recorder is None:
            return False
        try:
            self.recorder.start()
        except Exception as error:
            try:
                self.recorder.stop()
            finally:
                self._teardown_rec(release_delay=0)
            self.msg(None, "A gravação falhou", str(error))
            return False
        self._rec_check_id = GLib.timeout_add(1200, self._check_rec)
        return False

    def _pause_rec(self, pause):
        """Barra de gravação: pausa/continua. Devolve False se não foi possível."""
        r = self.recorder
        if r is None:
            return False
        if pause:
            return r.pause()
        ok = r.resume()
        if ok and self._rec_check_id == 0:
            self._rec_check_id = GLib.timeout_add(1200, self._check_rec)
        return ok

    def _check_rec(self):
        self._rec_check_id = 0
        if self.recorder is not None and not self.recorder.paused and not self.recorder.alive():
            err = self.recorder.error_text()
            self._teardown_rec()
            self.msg(None, "A gravação falhou", err[-600:] or "O FFmpeg encerrou inesperadamente.")
        return False

    def _teardown_rec(self, release_delay=60000):
        for attr in ("_rec_begin_id", "_rec_check_id"):
            source_id = getattr(self, attr, 0)
            if source_id:
                GLib.source_remove(source_id)
                setattr(self, attr, 0)
        self._release(release_delay)
        if self.rec_bar:
            self.rec_bar.close_bar()
        if self.rec_outline:
            self.rec_outline.destroy()
        self.rec_bar = self.rec_outline = None
        self.recorder = None

    @staticmethod
    def _remove_quietly(path):
        try:
            os.remove(path)
        except OSError:
            pass

    @staticmethod
    def _rec_scratch_dir():
        d = os.path.join(GLib.get_user_cache_dir(), "captura", "recordings")
        os.makedirs(d, exist_ok=True)
        return d

    def ask_save_recording(self, tmp_path):
        """Com o salvamento automático desligado: pergunta onde salvar. None descarta a gravação."""
        while True:
            d = Gtk.MessageDialog(message_type=Gtk.MessageType.QUESTION, text="Salvar a gravação de tela?")
            d.format_secondary_text("O salvamento automático está desativado. Se você descartar, a gravação será perdida.")
            d.add_buttons("Descartar", Gtk.ResponseType.REJECT, "Salvar", Gtk.ResponseType.YES)
            r = d.run()
            d.destroy()
            if r != Gtk.ResponseType.YES:
                return None
            fc = Gtk.FileChooserDialog(title="Salvar gravação de tela", action=Gtk.FileChooserAction.SAVE)
            fc.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.OK)
            fc.set_do_overwrite_confirmation(True)
            if os.path.isdir(settings.rec_directory):
                fc.set_current_folder(settings.rec_directory)
            fc.set_current_name(os.path.basename(tmp_path))
            ok = fc.run() == Gtk.ResponseType.OK
            path = fc.get_filename() if ok else None
            fc.destroy()
            if path:
                return path if os.path.splitext(path)[1] else path + ".mp4"

    def stop_recording(self, discard=False):
        r = self.recorder
        if r is None:
            return
        dest = self.rec_dest
        self._teardown_rec()
        self._restore_rec_windows()
        self._stop_job = job = threading.Thread(target=r.stop, daemon=True)     # o ffmpeg leva um instante para fechar o arquivo
        job.start()
        self._finish_stop_pending = True

        def poll():
            if job.is_alive():
                return GLib.SOURCE_CONTINUE
            self._finish_stop_pending = False
            self._finish_recording(dest, discard)
            return GLib.SOURCE_REMOVE
        GLib.timeout_add(40, poll)

    def wait_stop(self):
        """Usado nos testes: espera a thread de parada e a finalização."""
        job = getattr(self, "_stop_job", None)
        if job is not None:
            job.join()
        end = time.monotonic() + 3
        while getattr(self, "_finish_stop_pending", False) and time.monotonic() < end:
            GLib.MainContext.default().iteration(False)
            time.sleep(.005)

    def _finish_recording(self, dest, discard):
        if discard or not os.path.exists(dest):
            self._remove_quietly(dest)
            return
        if not settings["rec_autosave"]:
            final = self.ask_save_recording(dest)
            if not final:
                self._remove_quietly(dest)
                return
            try:
                os.makedirs(os.path.dirname(final), exist_ok=True)
                shutil.move(dest, final)
            except OSError as e:
                self.msg(None, "Não foi possível salvar a gravação", f"{e}\n\nO arquivo foi mantido em:\n{dest}")
                return
            dest = final
        services.notify("Gravação de tela salva", os.path.basename(dest) + "\nSelecione para abrir.", "video-x-generic",
                        [("default", "Abrir", lambda: subprocess.Popen(["xdg-open", dest]))])

    def toast_in_window(self, text):
        for w in self.windows:
            if w.is_active():
                w.show_toast(text)
                return
        if self.windows:
            self.windows[-1].show_toast(text)


def main(argv=None):
    app = CapturaApp()
    return app.run(argv if argv is not None else sys.argv)
