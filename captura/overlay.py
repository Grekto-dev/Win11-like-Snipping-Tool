"""Sobreposição de captura (equivalente ao Win+Shift+S): tela congelada e escurecida + barra flutuante."""
import math
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GLib

from . import grab, icons, theme
from .config import settings

DIM = 0.6          # medido no Windows 11: preto a 60% sobre a tela
SHAPES = [("rectangle", "rect", "Retângulo"), ("window", "window", "Janela"),
          ("fullscreen", "fullscreen", "Tela inteira"), ("freeform", "freeform", "Forma livre")]


def make_crosshair_cursor(display, size=29):
    """Cruz fina branca com contorno escuro (como o cursor do Windows durante a captura)."""
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(surf)
    c = size // 2 + 0.5
    for width, rgba in ((3, (0, 0, 0, 0.55)), (1, (1, 1, 1, 1))):
        cr.set_source_rgba(*rgba)
        cr.set_line_width(width)
        cr.move_to(c, 1)
        cr.line_to(c, size - 1)
        cr.move_to(1, c)
        cr.line_to(size - 1, c)
        cr.stroke()
    return Gdk.Cursor.new_from_surface(display, surf, c, c)


def blank_cursor(display):
    return Gdk.Cursor.new_for_display(display, Gdk.CursorType.BLANK_CURSOR)


class Overlay(Gtk.Window):
    """Emite `on_result(kind, payload)`; kind ∈ image | video | ocr | color | cancel."""

    def __init__(self, surface, on_result, tool="snip"):
        super().__init__(type=Gtk.WindowType.POPUP)
        self.surface = surface
        self.W, self.H = surface.get_width(), surface.get_height()
        self.on_result = on_result
        self.tool = tool                       # snip | ocr | color
        self.shape = settings["shape"]
        self.mode = settings["mode"]
        self._done = False
        self.sel = None                        # (x0, y0, x1, y1) normalizado
        self.anchor = None
        self.free_pts = []
        self.windows = grab.list_windows()
        self.hover_rect = None
        self.pointer = grab.pointer_position()
        self.loupe_rect = None
        self.sel_locked = False                # seleção feita no modo vídeo, aguardando "Iniciar"
        self.display = Gdk.Display.get_default()
        self.cur_cross = make_crosshair_cursor(self.display)
        self.cur_blank = blank_cursor(self.display)
        self.cur_arrow = Gdk.Cursor.new_from_name(self.display, "default")

        self.set_decorated(False)
        self.set_app_paintable(True)
        self.set_keep_above(True)
        self.set_default_size(self.W, self.H)
        self.move(0, 0)
        self.get_style_context().add_class("snip-window")

        overlay = Gtk.Overlay()
        self.add(overlay)
        self.da = Gtk.DrawingArea()
        self.da.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                           Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.KEY_PRESS_MASK)
        self.da.connect("draw", self.on_draw)
        self.da.connect("button-press-event", self.on_press)
        self.da.connect("button-release-event", self.on_release)
        self.da.connect("motion-notify-event", self.on_motion)
        overlay.add(self.da)
        self.connect("key-press-event", self.on_key)

        self.build_toolbar(overlay)
        self.start_btn = None
        self.update_cursor()

    # ------------------------------------------------------------------ barra
    def build_toolbar(self, overlay):
        col = theme.icon_color()
        self.toolbar_ev = Gtk.EventBox()
        self.toolbar_ev.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.toolbar_ev.connect("enter-notify-event", lambda *a: self.get_window().set_cursor(self.cur_arrow))
        self.toolbar_ev.connect("leave-notify-event", lambda *a: self.update_cursor())
        box = Gtk.Box(spacing=2)
        box.get_style_context().add_class("snip-toolbar")
        self.toolbar_ev.add(box)

        # foto | vídeo (com barra azul sob o modo ativo, como no Windows)
        seg = Gtk.Box(spacing=2)
        seg.get_style_context().add_class("seg")
        self.btn_photo = self._seg_toggle("camera", "Captura de tela", col)
        self.btn_video = self._seg_toggle("video", "Gravação de tela", col)
        for b in (self.btn_photo, self.btn_video):
            seg.pack_start(b, False, False, 0)
        (self.btn_video if self.mode == "video" else self.btn_photo).set_active(True)
        self.btn_photo.connect("clicked", lambda b: self.set_mode("photo") if b.get_active() else self._keep(b))
        self.btn_video.connect("clicked", lambda b: self.set_mode("video") if b.get_active() else self._keep(b))
        box.pack_start(seg, False, False, 2)

        # forma
        self.shape_btn = Gtk.Button()
        self.shape_btn.get_style_context().add_class("tbtn")
        self.shape_btn.set_tooltip_text("Modo de captura")
        self.shape_img = Gtk.Image()
        row = Gtk.Box(spacing=6)
        row.pack_start(self.shape_img, False, False, 0)
        row.pack_start(icons.image("chevron_down", 12, col), False, False, 0)
        self.shape_btn.add(row)
        self.shape_btn.connect("clicked", self.show_shape_menu)
        box.pack_start(self.shape_btn, False, False, 2)
        self._refresh_shape_icon()

        # marcação rápida, seletor de cores, extrator de texto
        self.btn_markup = self._toggle("markup_img", "Marcação rápida (Ctrl+E)", col)
        self.btn_markup.set_active(settings["quick_markup"])
        self.btn_markup.connect("toggled", lambda b: settings.__setitem__("quick_markup", b.get_active()))
        box.pack_start(self.btn_markup, False, False, 2)
        box.pack_start(self._sep(), False, False, 2)
        self.btn_color = self._toggle("eyedropper", "Seletor de cores", col)
        self.btn_color.set_active(self.tool == "color")
        self.btn_color.connect("toggled", lambda b: self._tool_toggled(b, "color"))
        self.btn_ocr = self._toggle("textscan", "Extrator de Texto", col)
        self.btn_ocr.set_active(self.tool == "ocr")
        self.btn_ocr.connect("toggled", lambda b: self._tool_toggled(b, "ocr"))
        box.pack_start(self.btn_color, False, False, 2)
        box.pack_start(self.btn_ocr, False, False, 2)
        box.pack_start(self._sep(), False, False, 2)
        close = Gtk.Button()
        close.get_style_context().add_class("tbtn")
        close.add(icons.image("close", 18, col))
        close.set_tooltip_text("Fechar")
        close.connect("clicked", lambda *_: self.finish("cancel", None))
        box.pack_start(close, False, False, 2)

        self.toolbar_ev.set_halign(Gtk.Align.START)
        self.toolbar_ev.set_valign(Gtk.Align.START)
        px, py = self.pointer
        self._mon = grab.monitor_at(px, py)
        self.toolbar_ev.set_margin_top(self._mon[1] + 13)

        def place(w, alloc):
            mx, my, mw, mh = self._mon
            want = max(0, mx + (mw - alloc.width) // 2)
            if abs(w.get_margin_start() - want) > 0:
                w.set_margin_start(want)
        self.toolbar_ev.connect("size-allocate", place)
        overlay.add_overlay(self.toolbar_ev)
        self.toolbar_box = box

    def _seg_toggle(self, icon, tip, col):
        b = Gtk.ToggleButton()
        b.get_style_context().add_class("tbtn")
        ov = Gtk.Overlay()
        ov.add(icons.image(icon, 20, col))
        ind = Gtk.Box()
        ind.get_style_context().add_class("ind-bar")
        ind.set_halign(Gtk.Align.CENTER)
        ind.set_valign(Gtk.Align.END)
        ind.set_margin_bottom(-6)
        ind.set_opacity(0.0)
        ov.add_overlay(ind)
        b.add(ov)
        b.connect("toggled", lambda x: ind.set_opacity(1.0 if x.get_active() else 0.0))
        b.set_tooltip_text(tip)
        b.set_can_focus(False)
        return b

    def _toggle(self, icon, tip, col):
        b = Gtk.ToggleButton()
        b.get_style_context().add_class("tbtn")
        b.add(icons.image(icon, 20, col))
        b.set_tooltip_text(tip)
        b.set_can_focus(False)
        return b

    def _keep(self, b):
        b.set_active(True)

    def _sep(self):
        s = Gtk.Box()
        s.get_style_context().add_class("sep")
        s.set_valign(Gtk.Align.CENTER)
        return s

    def _refresh_shape_icon(self):
        name = [i for k, i, _ in SHAPES if k == self.shape][0]
        self.shape_img.set_from_pixbuf(icons.pixbuf(name, 20, theme.icon_color()))

    def show_shape_menu(self, btn):
        pop = Gtk.Popover.new(btn)
        pop.get_style_context().add_class("cap-pop")
        pop.set_position(Gtk.PositionType.BOTTOM)
        vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        vb.set_margin_top(4)
        vb.set_margin_bottom(4)
        vb.set_margin_start(4)
        vb.set_margin_end(4)
        col = theme.icon_color()
        for key, icon, label in SHAPES:
            row = Gtk.Button()
            row.get_style_context().add_class("tbtn")
            row.get_style_context().add_class("menuitem")
            hb = Gtk.Box(spacing=10)
            bar = Gtk.Box()
            bar.set_size_request(3, 16)
            bar.set_valign(Gtk.Align.CENTER)
            if key == self.shape:
                bar.get_style_context().add_class("selbar")
                bar.override_background_color(Gtk.StateFlags.NORMAL, Gdk.RGBA(*self._accent_rgba()))
            hb.pack_start(bar, False, False, 0)
            hb.pack_start(icons.image(icon, 18, col), False, False, 0)
            lb = Gtk.Label(label=label, xalign=0)
            hb.pack_start(lb, True, True, 0)
            hb.set_size_request(160, -1)
            row.add(hb)
            row.connect("clicked", lambda _b, k=key: (pop.popdown(), self.set_shape(k)))
            vb.pack_start(row, False, False, 0)
        pop.add(vb)
        pop.show_all()
        pop.popup()

    def _accent_rgba(self):
        c = Gdk.RGBA()
        c.parse(theme.palette()["accent"])
        return (c.red, c.green, c.blue, 1.0)

    # ------------------------------------------------------------- estados
    def set_mode(self, mode):
        self.mode = mode
        settings["mode"] = mode
        for b, m in ((self.btn_photo, "photo"), (self.btn_video, "video")):
            if b.get_active() != (m == mode):
                b.set_active(m == mode)
        self.clear_selection()

    def set_shape(self, shape):
        self.shape = shape
        settings["shape"] = shape
        self._refresh_shape_icon()
        self.clear_selection()
        self.update_hover(*self.pointer)
        self.da.queue_draw()
        self.update_cursor()

    _busy = False

    def _tool_toggled(self, b, t):
        if self._busy:
            return
        self.set_tool(t if b.get_active() else "snip")

    def set_tool(self, tool):
        self.tool = tool
        self._busy = True
        for b, t in ((self.btn_color, "color"), (self.btn_ocr, "ocr")):
            if b.get_active() != (tool == t):
                b.set_active(tool == t)
        self._busy = False
        self.clear_selection()
        self.update_cursor()
        self.da.queue_draw()

    def clear_selection(self):
        self.sel = None
        self.anchor = None
        self.free_pts = []
        self.sel_locked = False
        if self.start_btn is not None:
            self.start_btn.destroy()
            self.start_btn = None
        self.da.queue_draw()

    def update_cursor(self):
        if self.get_window() is None:
            return
        self.get_window().set_cursor(self.cur_blank if self.tool == "color" else self.cur_cross)

    # -------------------------------------------------------------- desenho
    def hole(self):
        """Região mantida clara: (tipo, dados)."""
        if self.sel_locked or self.anchor is not None:
            if self.shape == "freeform" and self.free_pts and self.tool != "color":
                return ("poly", self.free_pts)
            if self.sel:
                return ("rect", self.sel)
        if self.anchor is None and not self.sel_locked and self.tool != "color":
            if self.shape == "window" and self.hover_rect:
                x, y, w, h = self.hover_rect
                return ("rect", (x, y, x + w, y + h))
            if self.shape == "fullscreen":
                return ("rect", (0, 0, self.W, self.H))
        return None

    def on_draw(self, da, cr):
        cr.set_source_surface(self.surface, 0, 0)
        cr.paint()
        h = self.hole()
        if self.tool != "color":
            cr.set_source_rgba(0, 0, 0, DIM)
            cr.rectangle(0, 0, self.W, self.H)
            if h:
                if h[0] == "rect":
                    x0, y0, x1, y1 = h[1]
                    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
                else:
                    pts = h[1]
                    cr.move_to(*pts[0])
                    for p in pts[1:]:
                        cr.line_to(*p)
                    cr.close_path()
                cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
            cr.fill()
            if h:
                cr.set_source_rgba(1, 1, 1, 0.95)
                cr.set_line_width(1.0)
                if h[0] == "rect":
                    x0, y0, x1, y1 = h[1]
                    cr.rectangle(x0 + 0.5, y0 + 0.5, x1 - x0 - 1, y1 - y0 - 1)
                else:
                    pts = h[1]
                    cr.move_to(*pts[0])
                    for p in pts[1:]:
                        cr.line_to(*p)
                    cr.close_path()
                cr.stroke()
        else:
            self.draw_loupe(cr)
        return False

    def draw_loupe(self, cr):
        px, py = self.pointer
        n = 11
        cell = 11
        size = n * cell
        r = size / 2 + 3
        cx, cy = px + r + 18, py + r + 18
        if cx + r + 6 > self.W:
            cx = px - r - 18
        if cy + r + 56 > self.H:
            cy = py - r - 60
        cr.save()
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(0, 0, 0, 0.9)
        cr.fill_preserve()
        cr.clip()
        cr.translate(cx - size / 2, cy - size / 2)
        for j in range(n):
            for i in range(n):
                rgb = grab.pixel_at(self.surface, px + i - n // 2, py + j - n // 2)
                cr.set_source_rgb(rgb[0] / 255, rgb[1] / 255, rgb[2] / 255)
                cr.rectangle(i * cell, j * cell, cell, cell)
                cr.fill()
        cr.set_source_rgba(0, 0, 0, 0.35)
        cr.set_line_width(1)
        for k in range(n + 1):
            cr.move_to(k * cell, 0); cr.line_to(k * cell, size)
            cr.move_to(0, k * cell); cr.line_to(size, k * cell)
        cr.stroke()
        cr.restore()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(2)
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.stroke()
        cr.set_line_width(1.5)
        cr.set_source_rgb(0, 0, 0)
        cr.rectangle(cx - cell / 2, cy - cell / 2, cell, cell)
        cr.stroke()
        cr.set_source_rgb(1, 1, 1)
        cr.rectangle(cx - cell / 2 - 1.5, cy - cell / 2 - 1.5, cell + 3, cell + 3)
        cr.set_line_width(1)
        cr.stroke()
        rgb = grab.pixel_at(self.surface, px, py)
        hexs = "#%02X%02X%02X" % rgb
        text = f"{hexs}   RGB({rgb[0]}, {rgb[1]}, {rgb[2]})"
        cr.select_font_face("Sans", cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(12)
        ext = cr.text_extents(text)
        bw, bh = ext.width + 20, 26
        bx, by = cx - bw / 2, cy + r + 8
        cr.set_source_rgba(0.12, 0.12, 0.12, 0.95)
        self._round_rect(cr, bx, by, bw, bh, 6)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.move_to(bx + 10, by + 17)
        cr.show_text(text)
        self.loupe_rect = (int(cx - r - 4), int(cy - r - 4), int(max(2 * r, bw) + 8), int(2 * r + bh + 24))

    @staticmethod
    def _round_rect(cr, x, y, w, h, r):
        cr.new_sub_path()
        cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
        cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
        cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
        cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()

    def _hole_bbox(self):
        h = self.hole()
        if not h:
            return None
        if h[0] == "rect":
            x0, y0, x1, y1 = h[1]
        else:
            xs = [p[0] for p in h[1]]
            ys = [p[1] for p in h[1]]
            x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
        return int(x0) - 3, int(y0) - 3, int(x1 - x0) + 7, int(y1 - y0) + 7

    def _inval(self, *rects):
        for r in rects:
            if r:
                self.da.queue_draw_area(max(0, r[0]), max(0, r[1]), r[2], r[3])

    # ------------------------------------------------------------- eventos
    def update_hover(self, x, y):
        self.hover_rect = None
        if self.shape == "window":
            for wx, wy, ww, wh, _ in self.windows:
                if wx <= x < wx + ww and wy <= y < wy + wh:
                    x0, y0, w, h = grab.clamp_rect(wx, wy, ww, wh, self.W, self.H)
                    self.hover_rect = (x0, y0, w, h)
                    break

    def on_motion(self, da, ev):
        x, y = int(ev.x), int(ev.y)
        old = self._hole_bbox()
        old_loupe = self.loupe_rect
        self.pointer = (x, y)
        if self.tool == "color":
            self._inval(old_loupe, (x - 10, y - 10, 300, 280), (x - 300, y - 300, 300, 600))
            self.da.queue_draw()
            return True
        if self.sel_locked:
            return True
        if self.anchor is not None:
            ax, ay = self.anchor
            if self.shape == "freeform":
                self.free_pts.append((x, y))
            else:
                self.sel = (min(ax, x), min(ay, y), max(ax, x), max(ay, y))
        else:
            if self.shape in ("window", "fullscreen"):
                self.update_hover(x, y)
        self._inval(old, self._hole_bbox())
        return True

    def on_press(self, da, ev):
        if ev.button != 1:
            return False
        x, y = int(ev.x), int(ev.y)
        if self.tool == "color":
            rgb = grab.pixel_at(self.surface, x, y)
            self.finish("color", "#%02X%02X%02X" % rgb)
            return True
        if self.sel_locked:
            return True
        if self.shape == "rectangle" or (self.shape == "freeform" and self.tool != "color"):
            self.anchor = (x, y)
            self.sel = (x, y, x, y)
            self.free_pts = [(x, y)] if self.shape == "freeform" else []
        elif self.shape == "window":
            if self.hover_rect:
                hx, hy, hw, hh = self.hover_rect
                self.sel = (hx, hy, hx + hw, hy + hh)
                self.commit_rect()
        elif self.shape == "fullscreen":
            self.sel = (0, 0, self.W, self.H)
            self.commit_rect()
        return True

    def on_release(self, da, ev):
        if ev.button != 1 or self.anchor is None:
            return True
        x, y = int(ev.x), int(ev.y)
        ax, ay = self.anchor
        self.anchor = None
        if self.shape == "freeform":
            self.free_pts.append((x, y))
            if len(self.free_pts) < 3:
                self.clear_selection()
                return True
            xs = [p[0] for p in self.free_pts]
            ys = [p[1] for p in self.free_pts]
            self.sel = (min(xs), min(ys), max(xs), max(ys))
            self.commit_freeform()
            return True
        self.sel = (min(ax, x), min(ay, y), max(ax, x), max(ay, y))
        if self.sel[2] - self.sel[0] < 3 or self.sel[3] - self.sel[1] < 3:
            self.clear_selection()
            return True
        self.commit_rect()
        return True

    def commit_rect(self):
        x0, y0, x1, y1 = self.sel
        if self.tool == "snip" and self.mode == "video":
            self.sel_locked = True
            self.show_start_button()
            self.da.queue_draw()
            return
        pb = grab.crop_pixbuf(self.surface, x0, y0, x1 - x0, y1 - y0)
        if pb is None:
            self.clear_selection()
            return
        self.finish("ocr" if self.tool == "ocr" else "image", pb)

    def commit_freeform(self):
        pb = grab.crop_freeform(self.surface, self.free_pts)
        if pb is None:
            self.clear_selection()
            return
        self.finish("ocr" if self.tool == "ocr" else "image", pb)

    def show_start_button(self):
        x0, y0, x1, y1 = self.sel
        b = Gtk.Button()
        b.get_style_context().add_class("tbtn")
        b.get_style_context().add_class("accentbtn")
        hb = Gtk.Box(spacing=8)
        hb.pack_start(icons.image("record", 14, theme.palette()["accent_text"]), False, False, 0)
        hb.pack_start(Gtk.Label(label="Iniciar"), False, False, 0)
        b.add(hb)
        b.set_halign(Gtk.Align.START)
        b.set_valign(Gtk.Align.START)
        b.set_margin_start(int((x0 + x1) / 2 - 45))
        b.set_margin_top(int((y0 + y1) / 2 - 16))
        b.connect("clicked", lambda *_: self.finish("video", (x0, y0, x1 - x0, y1 - y0)))
        self.get_child().add_overlay(b)
        b.show_all()
        self.start_btn = b

    def on_key(self, win, ev):
        key = ev.keyval
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        if key == Gdk.KEY_Escape:
            if self.sel_locked or self.anchor is not None:
                self.clear_selection()
            else:
                self.finish("cancel", None)
            return True
        if ctrl and key in (Gdk.KEY_e, Gdk.KEY_E):
            self.btn_markup.set_active(not self.btn_markup.get_active())
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.sel_locked:
            x0, y0, x1, y1 = self.sel
            self.finish("video", (x0, y0, x1 - x0, y1 - y0))
            return True
        return False

    # ----------------------------------------------------------- ciclo de vida
    def present_grabbed(self):
        self.show_all()
        self.update_cursor()
        GLib.idle_add(self._grab)

    def _grab(self, tries=[0]):
        win = self.get_window()
        if win is None:
            return False
        seat = self.display.get_default_seat()
        st = seat.grab(win, Gdk.SeatCapabilities.ALL, True, self.cur_cross, None, None)
        if st != Gdk.GrabStatus.SUCCESS and tries[0] < 20:
            tries[0] += 1
            GLib.timeout_add(30, self._grab)
        return False

    def finish(self, kind, payload):
        if self._done:
            return
        self._done = True
        try:
            self.display.get_default_seat().ungrab()
        except Exception:
            pass
        self.hide()
        self.destroy()
        GLib.timeout_add(60, lambda: (self.on_result(kind, payload), False)[1])
