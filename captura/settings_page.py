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


RIGHT_W = 177          # do x do interruptor até a borda direita do cartão


def _card(inner=False):
    f = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    f.get_style_context().add_class("cap-card")
    return f


class RadioRow(Gtk.Button):
    """Botão de opção do Windows 11: 20 px; marcado = disco azul com ponto branco; desmarcado = anel cinza."""
    def __init__(self, label):
        super().__init__()
        self.get_style_context().add_class("radio-row")
        self.set_can_focus(False)
        self.set_tooltip_text(label)
        self.get_accessible().set_name(label)
        self._active = False
        self.label = label
        area = Gtk.DrawingArea()
        area.set_size_request(RADIO_W, 20)
        area.connect("draw", self._draw)
        self.add(area)
        self.area = area
        area.show()

    def get_active(self):
        return self._active

    def set_active(self, on):
        self._active = bool(on)
        self.area.queue_draw()

    def _draw(self, area, cr):
        from . import annot
        from .shape_bar import draw_text, text_rgb
        pal = theme.palette()
        if self._active:
            cr.arc(10, 10, 10, 0, 6.2832); cr.set_source_rgb(*annot.hex_rgb(pal["accent"])); cr.fill()
            cr.arc(10, 10, 4.5, 0, 6.2832); cr.set_source_rgb(*annot.hex_rgb(pal["accent_text"])); cr.fill()
        else:
            cr.arc(10, 10, 9.5, 0, 6.2832)
            cr.set_source_rgb(*annot.hex_rgb(pal["radio_fill"])); cr.fill_preserve()
            cr.set_source_rgb(*annot.hex_rgb(pal["radio_ring"])); cr.set_line_width(1); cr.stroke()
        draw_text(cr, self.label, 29, 15, text_rgb())
        return False


RADIO_W = 400


class SettingsPage(Gtk.Box):
    def __init__(self, on_back, on_theme_changed):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.on_theme_changed = on_theme_changed
        head = Gtk.Fixed()
        head.set_size_request(-1, 76)           # título com tinta em y=62..81 (relativo à janela, topo da página y=32)
        back = Gtk.Button()
        back.get_style_context().add_class("tbtn")
        back.set_size_request(32, 32)
        back.set_can_focus(False)
        back.add(icons.image("back", 16, theme.icon_color()))
        back.connect("clicked", lambda *_: on_back())
        head.put(back, 3, 27)                    # seta com tinta em x=16..31
        title = _label("Configurações", "pagetitle")
        head.put(title, 56, 25)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        self.pack_start(sw, True, True, 0)
        outer = Gtk.Box()
        outer.set_halign(Gtk.Align.FILL)
        outer.set_margin_start(56)               # cartões: x=56..927 (872 px)
        outer.set_margin_end(56)
        outer.set_margin_bottom(28)
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        page.pack_start(head, False, False, 0)
        page.pack_start(outer, True, True, 0)
        sw.add(page)
        col = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)     # 4 px entre cartões
        col.set_hexpand(True)
        outer.pack_start(col, True, True, 0)
        self.col = col

        self.section("Captura", first=True)
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
        self.switch_row("Use a tecla Imprimir tela para abrir a Ferramenta de Captura", None, "use_print_key", on_change=self._print_key, height=53)

        self.section("Aparência")
        self.build_theme_card()

        self.section("Sobre este app", about=True)
        about = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        about.set_margin_start(32)
        for text, cls in ((f"Ferramenta de Captura {__version__}", "about-line"),
                          ("Recriação livre para Linux Mint (Cinnamon/X11). Software livre sob GPL-3.0-or-later.", "about-line"),
                          ("Não contém código nem recursos da Microsoft.", "about-line")):
            about.pack_start(_label(text, cls), False, False, 0)
        for text, url in (("Termos de licença deste software", "https://www.gnu.org/licenses/gpl-3.0.html"),
                          ("Ícones Fluent UI System Icons (MIT)", "https://github.com/microsoft/fluentui-system-icons"),
                          ("Fonte Selawik (SIL OFL 1.1)", "https://github.com/microsoft/Selawik"),
                          ("Avisos de software de terceiros", "https://github.com/Grekto-dev")):
            b = Gtk.Button(label=text)
            b.get_style_context().add_class("linkbtn")
            b.get_style_context().add_class("about-link")
            b.set_halign(Gtk.Align.START)
            b.set_can_focus(False)
            b.connect("clicked", lambda _b, u=url: subprocess.Popen(["xdg-open", u]))
            about.pack_start(b, False, False, 0)
        col.pack_start(about, False, False, 0)

    def build_theme_card(self):
        card = _card()
        row = Gtk.Box(spacing=0)
        row.get_style_context().add_class("cap-row")
        row.set_size_request(-1, 64)
        row.pack_start(_label("Tema do aplicativo"), True, True, 0)
        slot = Gtk.Fixed()
        slot.set_size_request(RIGHT_W, -1)
        self.theme_chevron = Gtk.Button()
        self.theme_chevron.get_style_context().add_class("tbtn")
        self.theme_chevron.set_can_focus(False)
        self.theme_chevron.set_size_request(32, 32)
        img = icons.image("chevron_down", 12, theme.icon_color())
        self.theme_chevron.add(img)
        slot.put(self.theme_chevron, 132, 15)
        row.pack_end(slot, False, False, 0)
        card.pack_start(row, False, False, 0)

        inner_box = Gtk.Box()
        inner_box.get_style_context().add_class("cap-inner")
        inner = Gtk.Fixed()
        inner.set_size_request(-1, 148)
        inner_box.pack_start(inner, True, True, 0)
        self.theme_radios = []
        for n, (key, label) in enumerate((("light", "Claro"), ("dark", "Escuro"), ("system", "Usar configuração do sistema"))):
            r = RadioRow(label)
            r.set_active(settings["theme"] == key)
            r.connect("clicked", self._radio_clicked, key)
            inner.put(r, 19, 18 + 40 * n)
            self.theme_radios.append((key, r))
        self.theme_revealer = Gtk.Revealer()
        self.theme_revealer.add(inner_box)
        card.pack_start(self.theme_revealer, False, False, 0)

        def sync(*_):
            on = self.theme_revealer.get_reveal_child()
            img.set_from_pixbuf(icons.pixbuf("chevron_up" if on else "chevron_down", 12, theme.icon_color()))
        self.theme_revealer.connect("notify::reveal-child", sync)
        self.theme_chevron.connect("clicked", lambda *_: self.theme_revealer.set_reveal_child(
            not self.theme_revealer.get_reveal_child()))
        self.col.pack_start(card, False, False, 0)

    def _radio_clicked(self, button, key):
        if settings["theme"] == key and button.get_active():
            return
        for k, r in self.theme_radios:
            r.set_active(k == key)
        settings["theme"] = key
        self.on_theme_changed()

    def section(self, title, first=False, about=False):
        l = _label(title, "section-about" if about else "section")
        l.set_margin_top(0 if first else (22 if not about else 22))
        l.set_margin_bottom(6)
        l.set_margin_start(1 if not about else 32)
        self.col.pack_start(l, False, False, 0)

    def switch_row(self, title, desc, key, expander=None, on_change=None, icon=None, height=None):
        card = _card()
        row = Gtk.Box(spacing=0)
        row.get_style_context().add_class("cap-row")
        h = height or (63 if expander else 62)
        row.set_size_request(-1, h)     # linhas com seta são 2 px mais altas (medido)
        if icon:
            im = icons.image(icon, 18, theme.icon_color())
            im.set_valign(Gtk.Align.CENTER)
            im.set_margin_start(0)
            im.set_margin_end(14)
            row.pack_start(im, False, False, 0)
        tb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=3)
        tb.set_valign(Gtk.Align.CENTER)
        if not desc:
            tb.set_margin_bottom(1)
        tb.pack_start(_label(title, wrap=True), False, False, 0)
        if desc:
            tb.pack_start(_label(desc, "subtle", wrap=True), False, False, 0)
        row.pack_start(tb, True, True, 0)

        # grupo direito de largura fixa: interruptor em x=750 (40x20), rótulo em +52, seta com centro em +153 (medido)
        right = Gtk.Fixed()
        right.set_size_request(RIGHT_W, -1)
        sw = Gtk.Switch()
        sw.set_active(bool(settings[key]))
        sw.set_size_request(40, 20)
        right.put(sw, 0, (h - 20) // 2 + (1 if expander else 0))
        state = _label("Ativado" if settings[key] else "Desativado")
        right.put(state, 52, (h - 20) // 2 + 2 + (1 if expander else 0))
        row.pack_end(right, False, False, 0)

        revealer = None
        if expander:
            chev = Gtk.Button()
            chev.get_style_context().add_class("tbtn")
            chev.set_can_focus(False)
            chev.set_size_request(32, 32)
            img = icons.image("chevron_up" if settings[key] else "chevron_down", 12, theme.icon_color())
            chev.add(img)
            right.put(chev, 132, 14)
            revealer = Gtk.Revealer()
            revealer.add(expander())
            revealer.set_reveal_child(bool(settings[key]))
            revealer.connect('notify::reveal-child', lambda r, _p: img.set_from_pixbuf(
                icons.pixbuf('chevron_up' if r.get_reveal_child() else 'chevron_down',
                             12, theme.icon_color())))

            def toggle(*_):
                r = not revealer.get_reveal_child()
                revealer.set_reveal_child(r)
                img.set_from_pixbuf(icons.pixbuf("chevron_up" if r else "chevron_down", 12, theme.icon_color()))
            chev.connect("clicked", toggle)

        def changed(s_, _p):
            settings[key] = s_.get_active()
            state.set_text("Ativado" if s_.get_active() else "Desativado")
            if revealer is not None:
                revealer.set_reveal_child(s_.get_active())
            if on_change:
                on_change(s_.get_active())
        sw.connect("notify::active", changed)
        card.pack_start(row, False, False, 0)
        if revealer is not None:
            card.pack_start(revealer, False, False, 0)
        self.col.pack_start(card, False, False, 0)
        return card

    def dir_row(self, title, key, current):
        wrap = Gtk.Box()
        wrap.get_style_context().add_class("cap-inner")
        box = Gtk.Fixed()
        box.set_size_request(-1, 63)
        wrap.pack_start(box, True, True, 0)
        t = _label(title)
        box.put(t, 32, 15)                                # texto em x=89 (cartão em 56, +1 borda, +32)
        path_l = Gtk.Box(spacing=5)
        path = _label(current, "subtle")
        path.set_ellipsize(3)
        path.set_width_chars(min(len(current), 70))
        path.set_max_width_chars(70)
        path_l.pack_start(path, False, False, 0)
        change = Gtk.Button(label="Alterar")
        change.get_style_context().add_class("linkbtn")
        change.set_can_focus(False)
        path_l.pack_start(change, False, False, 0)
        box.put(path_l, 32, 35)
        openb = Gtk.Button(label="Abrir pasta")
        openb.get_style_context().add_class("fluent-btn")
        openb.set_can_focus(False)
        openb.set_size_request(84, 32)
        box.put(openb, 710, 17)                           # x=767..850, y=285..316 na referência

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
        return wrap

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
        cb.props.use_alpha = False

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
