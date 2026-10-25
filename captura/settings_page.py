"""Página de Configurações (cartões com interruptores, como no Windows 11)."""
import os
import subprocess
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from . import __version__, icons, keybindings, theme
from .config import settings


def _label(text, cls=None, xalign=0.0, wrap=False):
    l = Gtk.Label(label=text, xalign=xalign)
    l.set_line_wrap(wrap)
    if cls:
        l.get_style_context().add_class(cls)
    return l


def _card(inner=False):
    f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    f.get_style_context().add_class("cap-card")
    return f


class SettingsPage(Gtk.Box):
    def __init__(self, on_back, on_theme_changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_theme_changed = on_theme_changed
        head = Gtk.Box(spacing=12)
        head.set_margin_start(14)
        head.set_margin_top(14)
        head.set_margin_bottom(6)
        back = Gtk.Button()
        back.get_style_context().add_class("tbtn")
        back.add(icons.image("back", 18, theme.icon_color()))
        back.connect("clicked", lambda *_: on_back())
        head.pack_start(back, False, False, 0)
        head.pack_start(_label("Configurações", "pagetitle"), False, False, 0)
        self.pack_start(head, False, False, 0)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.AUTOMATIC, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(sw, True, True, 0)
        outer = Gtk.Box(spacing=32)
        outer.set_margin_start(32)
        outer.set_margin_end(32)
        outer.set_margin_bottom(32)
        sw.add(outer)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        col.set_size_request(560, -1)
        outer.pack_start(col, False, False, 0)
        self.col = col

        self.section("Captura")
        self.switch_row("Copiar as alterações automaticamente", "As edições na sua captura de tela são copiadas automaticamente para a área de transferência", "shot_autocopy_edits")
        self.switch_row("Salvar automaticamente as capturas de tela originais", None, "shot_autosave",
                        expander=lambda: self.dir_row("As capturas de tela são salvas em", "shot_dir", settings.shot_directory))
        self.switch_row("Pedir para salvar as capturas de tela editadas", None, "shot_ask_save_edited")
        self.switch_row("Várias janelas", "Abrir novas capturas de tela em diferentes janelas", "shot_multi_window")
        self.switch_row("Adicionar borda a cada captura de tela", None, "shot_border", expander=self.border_panel)

        self.section("Gravação de tela")
        self.switch_row("Copiar as alterações automaticamente", "As edições na gravação da tela são copiadas automaticamente para a área de transferência", "rec_autocopy_edits")
        self.switch_row("Salvar automaticamente gravações de tela originais", None, "rec_autosave",
                        expander=lambda: self.dir_row("As gravações de tela são salvas em", "rec_dir", settings.rec_directory))
        self.switch_row("Solicitar para salvar gravações de tela editadas", None, "rec_ask_save_edited")
        self.switch_row("Incluir a entrada do microfone por padrão quando uma gravação de tela for iniciada", None, "rec_mic", icon="mic")
        self.switch_row("Incluir áudio do sistema por padrão quando uma gravação de tela for iniciada", None, "rec_system_audio", icon="speaker")

        self.section("Atalhos")
        self.switch_row("Use a tecla Imprimir tela para abrir a Ferramenta de Captura", "Super + Shift + S sempre abre a captura", "use_print_key", on_change=self._print_key)

        self.section("Aparência")
        card = _card()
        row = Gtk.Box(spacing=12)
        row.get_style_context().add_class("cap-row")
        row.pack_start(_label("Tema do aplicativo"), True, True, 0)
        combo = Gtk.ComboBoxText()
        for key, label in (("system", "Usar configuração do sistema"), ("light", "Claro"), ("dark", "Escuro")):
            combo.append(key, label)
        combo.set_active_id(settings["theme"])
        combo.connect("changed", self._theme_changed)
        row.pack_end(combo, False, False, 0)
        card.pack_start(row, False, False, 0)
        col.pack_start(card, False, False, 0)

        about = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        about.set_margin_top(24)
        about.set_size_request(240, -1)
        about.pack_start(_label("Sobre este app", "section"), False, False, 0)
        about.pack_start(_label(f"Ferramenta de Captura {__version__}"), False, False, 0)
        about.pack_start(_label("Recriação para o Linux Mint (Cinnamon/X11).\nSoftware livre — GPL-3.0-or-later.", "subtle", wrap=True), False, False, 0)
        about.pack_start(_label("Inspirada na Ferramenta de Captura do Windows 11;\nnão contém código nem recursos da Microsoft.", "subtle", wrap=True), False, False, 0)
        outer.pack_start(about, False, False, 0)

    def section(self, title):
        l = _label(title, "section")
        l.set_margin_top(18)
        l.set_margin_bottom(6)
        self.col.pack_start(l, False, False, 0)

    def switch_row(self, title, desc, key, expander=None, on_change=None, icon=None):
        card = _card()
        row = Gtk.Box(spacing=12)
        row.get_style_context().add_class("cap-row")
        if icon:
            row.pack_start(icons.image(icon, 18, theme.icon_color()), False, False, 0)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        tb.pack_start(_label(title, wrap=True), False, False, 0)
        if desc:
            tb.pack_start(_label(desc, "subtle", wrap=True), False, False, 0)
        row.pack_start(tb, True, True, 0)
        state = _label("Ativado" if settings[key] else "Desativado")
        sw = Gtk.Switch()
        sw.set_active(bool(settings[key]))
        sw.set_valign(Gtk.Align.CENTER)
        row.pack_end(state, False, False, 0)
        row.reorder_child(state, 0)
        # ordem: [texto][Ativado][switch] — pack_end inverte; monta manualmente
        row.remove(state)
        right = Gtk.Box(spacing=12)
        right.pack_start(state, False, False, 0)
        right.pack_start(sw, False, False, 0)
        row.pack_end(right, False, False, 0)
        revealer = None
        if expander:
            chev = Gtk.Button()
            chev.get_style_context().add_class("tbtn")
            chev.set_valign(Gtk.Align.CENTER)
            img = icons.image("chevron_up" if settings[key] else "chevron_down", 14, theme.icon_color())
            chev.add(img)
            right.pack_start(chev, False, False, 0)
            revealer = Gtk.Revealer()
            inner = expander()
            revealer.add(inner)
            revealer.set_reveal_child(bool(settings[key]))

            def toggle(*_):
                r = not revealer.get_reveal_child()
                revealer.set_reveal_child(r)
                img.set_from_pixbuf(icons.pixbuf("chevron_up" if r else "chevron_down", 14, theme.icon_color()))
            chev.connect("clicked", toggle)

        def changed(s, _p):
            settings[key] = s.get_active()
            state.set_text("Ativado" if s.get_active() else "Desativado")
            if revealer is not None:
                revealer.set_reveal_child(s.get_active())
            if on_change:
                on_change(s.get_active())
        sw.connect("notify::active", changed)
        card.pack_start(row, False, False, 0)
        if revealer is not None:
            card.pack_start(revealer, False, False, 0)
        self.col.pack_start(card, False, False, 0)

    def dir_row(self, title, key, current):
        box = Gtk.Box(spacing=12)
        box.get_style_context().add_class("cap-card")
        box.get_style_context().add_class("inner")
        box.get_style_context().add_class("cap-row")
        box.set_margin_start(0)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        tb.set_margin_start(16)
        tb.pack_start(_label(title), False, False, 0)
        path_l = Gtk.Box(spacing=6)
        path = _label(current, "subtle")
        path.set_ellipsize(3)
        path_l.pack_start(path, False, False, 0)
        change = Gtk.Button(label="Alterar")
        change.get_style_context().add_class("linkbtn")
        path_l.pack_start(change, False, False, 0)
        tb.pack_start(path_l, False, False, 0)
        box.pack_start(tb, True, True, 0)
        openb = Gtk.Button(label="Abrir pasta")
        openb.get_style_context().add_class("plain")
        openb.set_valign(Gtk.Align.CENTER)
        box.pack_end(openb, False, False, 0)

        def cur():
            return settings.shot_directory if key == "shot_dir" else settings.rec_directory

        def do_open(*_):
            d = cur()
            os.makedirs(d, exist_ok=True)
            subprocess.Popen(["xdg-open", d])

        def do_change(*_):
            dlg = Gtk.FileChooserDialog(title=title, parent=self.get_toplevel(), action=Gtk.FileChooserAction.SELECT_FOLDER)
            dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Selecionar pasta", Gtk.ResponseType.OK)
            dlg.set_current_folder(cur()) if os.path.isdir(cur()) else None
            if dlg.run() == Gtk.ResponseType.OK:
                settings[key] = dlg.get_filename()
                path.set_text(cur())
            dlg.destroy()
        openb.connect("clicked", do_open)
        change.connect("clicked", do_change)
        return box

    def border_panel(self):
        from .flyouts import Preview  # noqa: F401
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        box.get_style_context().add_class("cap-card")
        box.get_style_context().add_class("inner")
        prev = Gtk.DrawingArea()
        prev.set_size_request(-1, 150)

        def draw(w, cr):
            import cairo
            from . import annot
            a = w.get_allocation()
            pw, ph = 240, 140
            x, y = (a.width - pw) / 2, (a.height - ph) / 2
            g = cairo.LinearGradient(x, y, x, y + ph)
            g.add_color_stop_rgb(0, 0.72, 0.65, 0.78)
            g.add_color_stop_rgb(1, 0.75, 0.38, 0.28)
            cr.set_source(g)
            cr.rectangle(x, y, pw, ph)
            cr.fill()
            bw = settings["shot_border_width"]
            cr.set_source_rgb(*annot.hex_rgb(settings["shot_border_color"]))
            cr.set_line_width(bw)
            cr.rectangle(x - bw / 2 + 0, y - bw / 2, pw + bw, ph + bw)
            cr.stroke()
        prev.connect("draw", draw)
        box.pack_start(prev, False, False, 0)
        row = Gtk.Box(spacing=12)
        row.get_style_context().add_class("cap-row")
        row.pack_start(_label("Cor"), True, True, 0)
        cb = Gtk.ColorButton()
        from gi.repository import Gdk
        rgba = Gdk.RGBA()
        rgba.parse(settings["shot_border_color"])
        cb.set_rgba(rgba)
        cb.set_use_alpha(False)

        def color_set(b):
            c = b.get_rgba()
            settings["shot_border_color"] = "#%02x%02x%02x" % (round(c.red * 255), round(c.green * 255), round(c.blue * 255))
            prev.queue_draw()
        cb.connect("color-set", color_set)
        row.pack_end(cb, False, False, 0)
        box.pack_start(row, False, False, 0)
        row2 = Gtk.Box(spacing=12)
        row2.get_style_context().add_class("cap-row")
        row2.pack_start(_label("Espessura"), True, True, 0)
        sc = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 12, 1)
        sc.set_draw_value(False)
        sc.set_value(settings["shot_border_width"])
        sc.set_size_request(140, -1)

        def sc_changed(s):
            settings["shot_border_width"] = int(s.get_value())
            prev.queue_draw()
        sc.connect("value-changed", sc_changed)
        row2.pack_end(sc, False, False, 0)
        box.pack_start(row2, False, False, 0)
        return box

    def _theme_changed(self, combo):
        settings["theme"] = combo.get_active_id()
        self.on_theme_changed()

    def _print_key(self, on):
        try:
            keybindings.set_print_key(on)
        except Exception as e:
            print("falha ao configurar a tecla Imprimir tela:", e)
