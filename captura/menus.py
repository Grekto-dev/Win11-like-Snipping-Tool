"""Menus e flyouts como janelas POPUP próprias: posição exata em pixels, sem seta, sombra por CSS (Windows 11)."""
import os
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import time
import cairo
from gi.repository import Gtk, Gdk, GLib

from . import icons

# parâmetros medidos (relativos à caixa do menu): largura interna, altura da linha, x do ícone e do texto
MORE = dict(width=323, row_h=32, icon_x=12, text_x=38, right_pad=16, text_dy=-2)
CHOICE = dict(width=197, row_h=37, icon_x=18, text_x=42, right_pad=12, text_dy=-1)      # atraso
SHAPE = dict(width=128, row_h=37, icon_x=18, text_x=43, right_pad=12, text_dy=-1)       # modo de captura
SINGLE = dict(width=226, row_h=42, icon_x=12, text_x=42, right_pad=12, text_dy=-2)      # borracha
TEXTCHK = dict(width=226, row_h=32, pad=1, sep_m=1, icon_x=12, text_x=43, right_pad=16, text_dy=-1)      # chevron da Redação rápida
TEXTCTX = dict(width=212, row_h=33, pad=1, sep_m=1, icon_x=12, text_x=43, right_pad=16, text_dy=-1)      # clique direito no texto
OVSHAPE = dict(width=134, row_h=37, pad=5, sel_m=(1, 2), sel_lite=True, icon_x=18, text_x=43, right_pad=12, text_dy=-1)   # forma do overlay de captura
ZOOM = dict(width=182, row_h=32, icon_x=12, text_x=16, right_pad=16, text_dy=-1)    # submenu/menu de zoom (184 px externos)
PAD = 4
SHADOW = 2          # margem transparente ao redor da caixa para a sombra


def anchor_origin(widget):
    """Canto superior esquerdo de `widget` em coordenadas de tela."""
    win = widget.get_window()
    _, ox, oy = win.get_origin()
    a = widget.get_allocation()
    if widget.get_has_window():
        return ox, oy
    return ox + a.x, oy + a.y


# Abertura dos menus do Windows 11 (medida quadro a quadro): a caixa é revelada de cima para baixo e o conteúdo
# desliza junto (começa deslocado para cima). (ms, fração visível)
OPEN_CURVE = [(0, 0.0), (32, .49), (62, .75), (94, .85), (141, .94), (188, .987), (250, 1.0)]
ANIMATE = os.environ.get("CAPTURA_NO_ANIM") != "1"


def _curve(t):
    keys = OPEN_CURVE
    if t >= keys[-1][0]:
        return 1.0
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            return v0 + (v1 - v0) * (t - t0) / (t1 - t0)
    return 1.0


class RevealClip(Gtk.EventBox):
    """Mostra só a parte de cima do filho (fração `progress`) e desliza o conteúdo para o lugar."""

    def __init__(self):
        super().__init__()
        self.set_visible_window(False)
        self.progress = 1.0

    def do_draw(self, cr):
        child = self.get_child()
        if child is None:
            return False
        if self.progress >= 1.0:
            self.propagate_draw(child, cr)
            return False
        a = self.get_allocation()
        h = a.height
        cr.save()
        cr.rectangle(a.x, a.y, a.width, h * self.progress)
        cr.clip()
        cr.translate(0, -h * (1.0 - self.progress))
        self.propagate_draw(child, cr)
        cr.restore()
        return False

    def play(self, on_done=None):
        self.progress = 0.0
        t0 = time.monotonic()

        def tick():
            if not self.get_realized():
                return GLib.SOURCE_REMOVE
            self.progress = _curve((time.monotonic() - t0) * 1000)
            self.queue_draw()
            if self.progress >= 1.0:
                return GLib.SOURCE_REMOVE
            return GLib.SOURCE_CONTINUE
        GLib.timeout_add(16, tick)


class Popup(Gtk.Window):
    """Caixa flutuante sem decoração. `frame_class` define a aparência (wmenu | wflyout)."""

    def __init__(self, content, frame_class="wmenu", on_close=None):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.set_app_paintable(True)
        vis = self.get_screen().get_rgba_visual()
        if vis is not None:
            self.set_visual(vis)
        self.set_decorated(False)
        self.set_skip_taskbar_hint(True)
        self.set_resizable(False)
        self.on_close = on_close
        self._closed = False
        self._grab_attempts = 0
        outer = Gtk.Box()
        for m in (outer.set_margin_start, outer.set_margin_end, outer.set_margin_top, outer.set_margin_bottom):
            m(SHADOW)
        self.frame = Gtk.Box()
        self.frame.get_style_context().add_class(frame_class)
        self.frame.add(content)
        self.clip = RevealClip()
        self.clip.add(self.frame)
        self._animate = ANIMATE and frame_class == "wmenu"
        outer.add(self.clip)
        self.add(outer)
        self.get_style_context().add_class("popup-root")
        self.connect("draw", self._clear)
        self.connect("button-press-event", self._press)
        self.connect("key-press-event", self._key)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        outer.show_all()

    @staticmethod
    def _clear(widget, cr):
        cr.set_operator(cairo.OPERATOR_SOURCE)
        cr.set_source_rgba(0, 0, 0, 0)
        cr.paint()
        cr.set_operator(cairo.OPERATOR_OVER)
        return False

    def open_at(self, x, y):
        """x,y = canto superior esquerdo da CAIXA (sem a margem da sombra), em coordenadas de tela."""
        display = Gdk.Display.get_default()
        monitor = display.get_monitor_at_point(int(x), int(y))
        area = monitor.get_workarea()
        _, natural_width = self.frame.get_preferred_width()
        _, natural_height = self.frame.get_preferred_height()
        x = max(area.x, min(int(x), area.x + area.width - natural_width))
        y = max(area.y, min(int(y), area.y + area.height - natural_height))
        self.move(x - SHADOW, y - SHADOW)
        if self._animate:
            self.clip.progress = 0.0
        self.show()
        if self._animate:
            self.clip.play()
        self.grab_add()
        GLib.idle_add(self._grab)

    def _grab(self):
        win = self.get_window()
        if win is None or self._closed:
            return False
        seat = Gdk.Display.get_default().get_default_seat()
        st = seat.grab(win, Gdk.SeatCapabilities.ALL, True, None, None, None)
        if st != Gdk.GrabStatus.SUCCESS and self._grab_attempts < 15:
            self._grab_attempts += 1
            GLib.timeout_add(20, self._grab)
        return False

    def _press(self, w, ev):
        a = self.frame.get_allocation()
        _, wx, wy = self.get_window().get_origin()
        gx, gy = ev.x_root - wx, ev.y_root - wy
        inside = a.x <= gx <= a.x + a.width and a.y <= gy <= a.y + a.height
        if not inside:
            self.close_popup()
            return True
        return False

    def _key(self, w, ev):
        if ev.keyval == Gdk.KEY_Escape:
            self.close_popup()
            return True
        return False

    def close_popup(self):
        if self._closed:
            return
        self._closed = True
        if Gtk.grab_get_current() is self:
            self.grab_remove()
        try:
            Gdk.Display.get_default().get_default_seat().ungrab()
        except Exception:
            pass
        self.hide()
        self.destroy()
        if self.on_close:
            self.on_close()


class Menu(Popup):
    """items: (ícone|None, rótulo, atalho|None, callback, ativo=True, seta=False, selecionado=False) | None."""

    def __init__(self, items, style):
        self.style = style
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        pad = style.get("pad", PAD)
        self.pad = pad
        box.set_size_request(style["width"] - 2 * pad, -1)
        box.set_margin_start(pad)
        box.set_margin_end(pad)
        box.set_margin_top(pad)
        box.set_margin_bottom(pad)
        for it in items:
            if it is None:
                s = Gtk.Box()
                s.get_style_context().add_class("wmenu-sep")
                if style.get("sep_m", 3) < 3:
                    s.get_style_context().add_class("tight")
                box.pack_start(s, False, False, 0)
                continue
            box.pack_start(self._row(*it), False, False, 0)
        super().__init__(box, "wmenu")

    def _row(self, icon, label, accel, cb, enabled=True, arrow=False, selected=False):
        s = self.style
        b = Gtk.Button()
        b.set_can_focus(False)
        ctx = b.get_style_context()
        ctx.add_class("wmi")
        if selected:
            ctx.add_class("sel")
        b.set_size_request(-1, s["row_h"])
        ov = Gtk.Overlay()
        b.add(ov)
        surface = Gtk.Box()
        if selected:
            surface.get_style_context().add_class("wmenu-selection")
            sm = s.get("sel_m", (2, 2))
            surface.set_margin_top(sm[0])
            surface.set_margin_bottom(sm[1])
            if s.get("sel_lite"):
                surface.get_style_context().add_class("lite")
        ov.add(surface)
        if icon:
            glyph = {"zoom": "menu_zoom", "folder_open": "menu_open", "folder_shots": "menu_folder",
                     "window": "menu_window", "fullscreen": "menu_fullscreen", "freeform": "menu_freeform"}.get(icon, icon)
            im = icons.role_image(glyph, 20, "chev" if glyph == "checksm" else ("text" if enabled else "disabled"))
            im.set_halign(Gtk.Align.START)
            im.set_valign(Gtk.Align.CENTER)
            im.set_margin_bottom(2)
            im.set_margin_start(s["icon_x"] - self.pad - 2)
            ov.add_overlay(im)
        lb = Gtk.Label(label=label, xalign=0)
        lb.set_halign(Gtk.Align.START)
        lb.set_valign(Gtk.Align.CENTER)
        lb.set_margin_start(s["text_x"] - self.pad - 1)
        lb.set_margin_bottom(max(0, -2 * s.get("text_dy", 0)))
        ov.add_overlay(lb)
        if accel:
            al = Gtk.Label(label=accel)
            al.get_style_context().add_class("wmenu-accel")
            al.set_halign(Gtk.Align.END)
            al.set_valign(Gtk.Align.CENTER)
            al.set_margin_end(s["right_pad"] - 2)
            al.set_margin_bottom(max(0, -2 * s.get("text_dy", 0)))
            ov.add_overlay(al)
        if arrow:
            ch = icons.role_image("chevron_right", 20, "chev")
            ch.set_halign(Gtk.Align.END)
            ch.set_valign(Gtk.Align.CENTER)
            ch.set_margin_end(s["right_pad"] - 6)
            ov.add_overlay(ch)
        if selected:
            bar = Gtk.Box()
            bar.get_style_context().add_class("wmenu-bar")
            bar.set_size_request(3, 16)
            bar.set_halign(Gtk.Align.START)
            bar.set_margin_start(1)
            bar.set_valign(Gtk.Align.CENTER)
            ov.add_overlay(bar)
        b.set_sensitive(enabled)
        def activate(_button):
            self.close_popup()

            def invoke_once():
                cb()
                return GLib.SOURCE_REMOVE

            GLib.idle_add(invoke_once)

        b.connect("clicked", activate)
        return b
