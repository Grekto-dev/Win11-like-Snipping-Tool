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
    def __init__(self, on_stop, on_discard, rect):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.t0 = time.time()
        self.set_keep_above(True)
        self.get_style_context().add_class("cap-window")
        frame = Gtk.Box(spacing=8)
        frame.get_style_context().add_class("rec-bar")
        self.add(frame)
        dot = icons.image("record", 14, "#e81123")
        frame.pack_start(dot, False, False, 0)
        self.lbl = Gtk.Label(label="00:00")
        self.lbl.get_style_context().add_class("rec-time")
        frame.pack_start(self.lbl, False, False, 0)
        stop = Gtk.Button()
        stop.get_style_context().add_class("tbtn")
        stop.add(icons.image("stop", 16, "#e81123"))
        stop.set_tooltip_text("Parar gravação")
        stop.connect("clicked", lambda *_: on_stop())
        frame.pack_start(stop, False, False, 0)
        trash = Gtk.Button()
        trash.get_style_context().add_class("tbtn")
        trash.add(icons.image("trash", 16, theme.icon_color()))
        trash.set_tooltip_text("Descartar")
        trash.connect("clicked", lambda *_: on_discard())
        frame.pack_start(trash, False, False, 0)
        self.show_all()
        x, y, w, h = rect
        mx, my, mw, mh = grab.monitor_at(x + w // 2, y + h // 2)
        _, nat = self.get_preferred_width()
        self.move(mx + (mw - nat) // 2, my + 14)
        self.timer = GLib.timeout_add(500, self.tick)

    def tick(self):
        s = int(time.time() - self.t0)
        self.lbl.set_text(f"{s // 60:02d}:{s % 60:02d}")
        return True

    def close_bar(self):
        GLib.source_remove(self.timer)
        self.destroy()


class OutlineWindow(Gtk.Window):
    """Moldura vermelha ao redor da região gravada (fora da área capturada)."""

    def __init__(self, rect):
        super().__init__(type=Gtk.WindowType.POPUP)
        x, y, w, h = rect
        self.set_app_paintable(True)
        self.set_visual(self.get_screen().get_rgba_visual())
        self.set_keep_above(True)
        self.set_accept_focus(False)
        self.set_default_size(w + 6, h + 6)
        self.W, self.H = w + 6, h + 6
        self.connect("draw", self.draw)
        self.move(x - 3, y - 3)
        self.show_all()
        reg = cairo.Region()
        self.input_shape_combine_region(reg)

    def draw(self, w, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_source_rgba(0.91, 0.07, 0.14, 1)
        cr.set_line_width(2)
        cr.rectangle(1, 1, self.W - 2, self.H - 2)
        cr.stroke()


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
            self._restore_windows_if_app(False)
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
        self.rec_bar = RecordingBar(self.stop_recording, lambda: self.stop_recording(discard=True), rect)
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

    def _check_rec(self):
        self._rec_check_id = 0
        if self.recorder is not None and not self.recorder.alive():
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
        r.stop()
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
