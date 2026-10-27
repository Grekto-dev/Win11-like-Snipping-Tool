"""Sobreposição de captura (equivalente ao Win+Shift+S): tela congelada e escurecida + barra flutuante."""
import math
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GLib

from . import grab, icons, menus, theme
from .overlay_bar import BTN_Y, MAIN_W, REC_W, SHAPE as _SHAPE, SnipBar, TOP
from .config import settings
from . import overlay_text as OT

SHAPE_X = _SHAPE[0]
DIM = 0.6          # medido no Windows 11: preto a 60% sobre a tela
# Ponteiros medidos no Windows: cruz fina em repouso e ao pressionar sem mover; seta assim que o arrasto começa, durante a varredura
# e sobre as barras; I-beam só ao arrastar sobre o texto; setas de redimensionar sobre as alças da seleção do extrator.
HANDLE_CURSORS = {"n": "ns-resize", "s": "ns-resize", "e": "ew-resize", "w": "ew-resize",
                  "nw": "nwse-resize", "se": "nwse-resize", "ne": "nesw-resize", "sw": "nesw-resize"}
HANDLE_OUT, HANDLE_IN = 8, 4                 # faixa (px) fora/dentro da borda que responde como alça
HANDLE_CORNER = 12

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
        self._grab_tries = 0
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
        self.cur_text = Gdk.Cursor.new_from_name(self.display, "text")
        self._cursors = {"cross": self.cur_cross, "arrow": self.cur_arrow, "blank": self.cur_blank, "text": self.cur_text}
        for kind, name in HANDLE_CURSORS.items():
            self._cursors[kind] = Gdk.Cursor.new_from_name(self.display, name)
        self._cursor_kind = None
        self._moved = False                    # o botão está pressionado e o ponteiro já se moveu
        self._edge = None
        self.ts = OT.TextSession(self)
        self._anim_id = 0

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
        self.connect("realize", lambda *_: self.update_cursor())
        self.update_cursor()

    # ------------------------------------------------------------------ barra
    def build_toolbar(self, overlay):
        handlers = dict(mode=self.set_mode, shape_menu=self.show_shape_menu, markup=self._toggle_markup,
                        tool=self._tool_clicked, close=lambda: self.finish("cancel", None), start=self._start_clicked)
        self.bar = bar = SnipBar(handlers)
        bar.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)
        bar.connect("enter-notify-event", lambda *a: self.get_window().set_cursor(self.cur_arrow))
        bar.connect("leave-notify-event", lambda *a: self.update_cursor())
        self.toolbar_ev = bar
        self.btn_photo, self.btn_video, self.shape_btn = bar.btn_photo, bar.btn_video, bar.shape_btn
        self.btn_markup, self.btn_color, self.btn_ocr, self.shape_img = bar.btn_markup, bar.btn_color, bar.btn_ocr, bar.shape_img
        px, py = self.pointer
        self._mon = grab.monitor_at(px, py)
        bar.set_margin_top(self._mon[1] + TOP)
        bar.set_margin_start(self._bar_x(MAIN_W))
        bar.set_mode(self.mode)
        bar.set_tool(self.tool)
        bar.btn_markup.get_style_context().add_class("on") if settings["quick_markup"] else None
        self._refresh_shape_icon()
        overlay.add_overlay(bar)
        self.bar_ocr = OT.OcrBar(lambda: self.set_tool("snip"), self.copy_all_text, self.show_text_menu,
                                 lambda: self.finish("cancel", None))
        self.bar_ocr.set_margin_top(self._mon[1] + OT.BAR_TOP)
        self.bar_ocr.set_margin_start(self._bar_x(OT.BAR_W))
        self.bar_ocr.set_no_show_all(True)
        overlay.add_overlay(self.bar_ocr)
        self.mini = OT.MiniBar(self.copy_selected_text, lambda: None)
        self.mini.set_no_show_all(True)
        overlay.add_overlay(self.mini)
        self.notice = OT.Notice()
        self.notice.set_no_show_all(True)
        self.notice.set_margin_top(self._mon[1] + OT.NOTICE_TOP)
        self.notice.set_margin_start(self._bar_x(OT.NOTICE_W) + 1)
        overlay.add_overlay(self.notice)
        overlay.set_overlay_pass_through(self.notice, True)
        self._show_bar_for_tool()

    def _show_bar_for_tool(self):
        ocr = self.tool == "ocr"
        self.bar.set_visible(not ocr)
        self.bar.set_no_show_all(ocr)
        self.bar_ocr.set_no_show_all(not ocr)
        self.bar_ocr.set_visible(ocr)
        if not ocr:
            self.mini.hide()
            self.notice.stop()

    def _menu_closed(self):
        self._grab_tries = 0
        GLib.idle_add(self._grab)

    def _bar_x(self, width):
        mx, _my, mw, _mh = self._mon
        return max(0, mx + (mw - width) // 2)

    def _toggle_markup(self):
        settings["quick_markup"] = not settings["quick_markup"]
        ctx = self.btn_markup.get_style_context()
        (ctx.add_class if settings["quick_markup"] else ctx.remove_class)("on")

    def _tool_clicked(self, tool):
        self.set_tool("snip" if self.tool == tool else tool)

    def _refresh_shape_icon(self):
        name = [i for k, i, _ in SHAPES if k == self.shape][0]
        self.shape_img.set_from_pixbuf(icons.pixbuf(name, 20, theme.icon_color()))

    def show_shape_menu(self, btn):
        items = [(i, l, None, (lambda k=k: self.set_shape(k)), True, False, k == self.shape) for k, i, l in SHAPES]
        idx = [k for k, _, _ in SHAPES].index(self.shape)
        bx = int(self.bar.get_margin_start()) + SHAPE_X
        by = int(self.bar.get_margin_top()) + BTN_Y
        m = menus.Menu(items, menus.OVSHAPE)
        m.on_close = self._menu_closed
        self._cur_menu = m
        m.open_at(self.get_window().get_origin()[1] + bx - 4, self.get_window().get_origin()[2] + by - 6 - idx * menus.OVSHAPE["row_h"])

    # ------------------------------------------------------------- estados
    def set_mode(self, mode):
        self.mode = mode
        settings["mode"] = mode
        self.bar.set_mode(mode)
        self.clear_selection()

    def set_shape(self, shape):
        self.shape = shape
        settings["shape"] = shape
        self._refresh_shape_icon()
        self.clear_selection()
        self.update_hover(*self.pointer)
        self.da.queue_draw()
        self.update_cursor()

    def set_tool(self, tool):
        self.tool = tool
        self.bar.set_tool(tool)
        self.ts.reset()
        self._show_bar_for_tool()
        self.clear_selection()
        self.update_cursor()
        self.da.queue_draw()

    def clear_selection(self):
        if hasattr(self, "mini"):
            self.mini.hide()
        self.sel = None
        self.anchor = None
        self.free_pts = []
        self.sel_locked = False
        if self.bar.mode_name == "record":
            self.bar.show_main()
            self.bar.set_margin_start(self._bar_x(MAIN_W))
        self.da.queue_draw()

    def update_cursor(self):
        if self.get_window() is None:
            return
        self._cursor_kind = None
        self._refresh_cursor()

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
        if self.tool == "ocr" and self.ts.phase != "none":
            cr.set_source_rgba(0, 0, 0, DIM)
            cr.paint()
            self.ts.draw(cr)
            return False
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
            if h and self.sel_locked and h[0] == "rect":
                self.draw_locked_selection(cr, h[1])
            elif h:
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

    def draw_locked_selection(self, cr, rect):
        """Região de gravação já escolhida (medido no Windows): borda tracejada 4/3 de 1 px logo fora da área e
        alças brancas de 6 px (cantos em L de 32 px e barras de 32 px no meio dos lados), encostadas por fora."""
        x0, y0, x1, y1 = rect
        cr.save()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(1)
        cr.set_dash([4, 3], 5)
        L, T, R, B = x0 - 1, y0 - 1, x1, y1
        for (ax, ay, bx, by) in ((L, T, R + 1, T), (L, T, L, B + 1), (R, T, R, B + 1), (L, B, R + 1, B)):
            cr.move_to(ax + (.5 if ax == bx else 0), ay + (.5 if ay == by else 0))
            cr.line_to(bx + (.5 if ax == bx else 0), by + (.5 if ay == by else 0))
            cr.stroke()
        cr.set_dash([])
        t, n = 6, 32
        mx, my = (x0 + x1) // 2, (y0 + y1) // 2
        bars = [(x0 - t, y0 - t, n, t), (x0 - t, y0 - t, t, n),                    # canto superior esquerdo
                (x1 - n + t, y0 - t, n, t), (x1, y0 - t, t, n),                    # superior direito
                (x0 - t, y1, n, t), (x0 - t, y1 - n + t, t, n),                    # inferior esquerdo
                (x1 - n + t, y1, n, t), (x1, y1 - n + t, t, n),                    # inferior direito
                (mx - n // 2, y0 - t, n, t), (mx - n // 2, y1, n, t),              # meio de cima / de baixo
                (x0 - t, my - n // 2, t, n), (x1, my - n // 2, t, n)]              # meio da esquerda / da direita
        for bx, by, w, hh in bars:
            self._round_rect(cr, bx, by, w, hh, 2.5)
            cr.fill()
        cr.restore()

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
        if self.tool == "ocr" and self.ts.phase != "none":
            if self.ts.dragging:
                self._moved = True
                self.ts.drag_select(x, y)
                self.da.queue_draw()
            self._refresh_cursor(x, y)
            return True
        if self.sel_locked:
            return True
        if self.anchor is not None:
            x, y = self._resize_point(x, y)
            self._moved = True
            self._set_cursor_kind("arrow")
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
        if self.tool == "ocr" and self.ts.phase == "scan":
            return True
        if self.tool == "ocr" and self.ts.phase == "ready":
            handle = self.handle_at(x, y)
            if handle:
                self.begin_resize(handle)
                return True
            if self.ts.inside(x, y):
                self.mini.hide()
                self._moved = False
                self.ts.begin_select(x, y)
                self.da.queue_draw()
                return True
            self.ts.reset()                         # clicar fora da seleção começa outra
            self.bar_ocr.set_copy_enabled(False)
            self.mini.hide()
            self.clear_selection()
        if self.sel_locked:
            return True
        self._edge = None
        self._moved = False
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
        if ev.button == 1 and self.tool == "ocr" and self.ts.dragging:
            x, y = int(ev.x), int(ev.y)
            self.ts.drag_select(x, y)
            if self.ts.end_select(x, y):
                self.place_mini(x, y)
            self._moved = False
            self._refresh_cursor(x, y)
            self.da.queue_draw()
            return True
        if ev.button != 1 or self.anchor is None:
            return True
        x, y = self._resize_point(int(ev.x), int(ev.y))
        ax, ay = self.anchor
        self.anchor = None
        self._edge = None
        self._moved = False
        self._refresh_cursor(int(ev.x), int(ev.y))
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
        if self.tool == "ocr":
            self.start_text_scan(self.sel)
            return
        pb = grab.crop_pixbuf(self.surface, x0, y0, x1 - x0, y1 - y0)
        if pb is None:
            self.clear_selection()
            return
        self.finish("image", pb)

    def commit_freeform(self):
        if self.tool == "snip" and self.mode == "video":
            self.sel_locked = True                  # gravação usa o retângulo envolvente da forma
            self.show_start_button()
            self.da.queue_draw()
            return
        if self.tool == "ocr":
            self.start_text_scan(self.sel)
            return
        pb = grab.crop_freeform(self.surface, self.free_pts)
        if pb is None:
            self.clear_selection()
            return
        self.finish("image", pb)

    # ------------------------------------------------------- extrator de texto
    def start_text_scan(self, rect):
        x0, y0, x1, y1 = [int(v) for v in rect]
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(self.W, x1), min(self.H, y1)
        self.sel = None
        self.anchor = None
        self.free_pts = []
        if x1 - x0 < 3 or y1 - y0 < 3:
            self.clear_selection()
            return
        self.ts.start((x0, y0, x1, y1))
        self._refresh_cursor()
        self.da.queue_draw()

    def start_anim(self):
        if not self._anim_id:
            self._anim_id = GLib.timeout_add(16, self._anim_tick)

    def _anim_tick(self):
        if self._done:
            self._anim_id = 0
            return False
        running = self.ts.tick()
        if running and self.ts.rect:                      # só o anel muda durante a varredura: invalida só a sua região
            x0, y0, x1, y1 = self.ts.rect
            o, i = 18, 4                                  # o anel ocupa de 8 px fora a 2 px dentro da borda da seleção
            w, h = x1 - x0, y1 - y0
            for rx, ry, rw, rh in ((x0 - o, y0 - o, w + 2 * o, o + i), (x0 - o, y1 - i, w + 2 * o, o + i),
                                   (x0 - o, y0 - o, o + i, h + 2 * o), (x1 - i, y0 - o, o + i, h + 2 * o)):
                self.da.queue_draw_area(max(0, rx), max(0, ry), rw, rh)
        else:
            self.da.queue_draw()
        if not running:
            self._anim_id = 0
        return running

    def text_ready(self):
        self.sel_locked = False
        self._refresh_cursor()
        if settings["ocr_auto_copy"]:
            GLib.idle_add(lambda: (self.copy_all_text(), False)[1])

    def text_empty(self, message):
        self.clear_selection()
        self.bar_ocr.set_copy_enabled(False)
        self.notice.show_text(message)

    def place_mini(self, x, y):
        mx, my, mw, mh = self._mon
        px = max(mx, min(x, mx + mw - OT.MINI_W))
        py = y if y + OT.MINI_H <= my + mh else y - OT.MINI_H
        self.mini.set_margin_start(px)
        self.mini.set_margin_top(max(my, py))
        self.mini.show()

    def copy_all_text(self):
        if self.ts.phase == "ready" and self.ts.words:
            self.finish("textcopy", self.ts.text(self.ts.words))

    def copy_selected_text(self):
        if self.ts.phase == "ready" and self.ts.sel:
            self.finish("textcopy", self.ts.text(self.ts.sel))

    def show_text_menu(self):
        items = [("checksm" if settings["ocr_auto_copy"] else None, "Copiar texto automaticamente", None,
                  lambda: settings.__setitem__("ocr_auto_copy", not settings["ocr_auto_copy"])),
                 ("checksm" if settings["ocr_remove_breaks"] else None, "Remover quebras de linha", None,
                  lambda: settings.__setitem__("ocr_remove_breaks", not settings["ocr_remove_breaks"]))]
        ox, oy = self.get_window().get_origin()[1:]
        m = menus.Menu(items, menus.OVTEXT)
        self.bar_ocr.hold("more")                       # o botão ⋯ fica realçado enquanto o menu está aberto
        m.on_close = lambda: (self.bar_ocr.hold(None), self._menu_closed())
        self._cur_menu = m
        m.open_at(ox + int(self.bar_ocr.get_margin_start()) + OT.MENU_DX, oy + int(self.bar_ocr.get_margin_top()) + OT.MENU_DY)

    def _set_cursor_kind(self, kind):
        if self._cursor_kind == kind or self.get_window() is None:
            return
        self._cursor_kind = kind
        self.get_window().set_cursor(self._cursors[kind])

    def _wanted_cursor(self, x, y):
        if self.tool == "color":
            return "blank"
        ts = self.ts
        if self.tool == "ocr" and ts.phase == "scan":
            return "arrow"
        if self.anchor is not None:                       # arrastando uma seleção (ou redimensionando)
            return "arrow" if self._moved else "cross"
        if self.tool == "ocr" and ts.phase == "ready":
            if ts.dragging:
                return "text" if self._moved else "arrow"
            return self.handle_at(x, y) or "arrow"
        return "cross"

    def _refresh_cursor(self, x=None, y=None):
        px, py = self.pointer if x is None else (x, y)
        self._set_cursor_kind(self._wanted_cursor(px, py))

    def handle_at(self, x, y):
        """Alça da seleção do extrator sob o ponto: n, s, e, w, ne, nw, se, sw ou None."""
        if self.ts.phase != "ready":
            return None
        x0, y0, x1, y1 = self.ts.rect
        if not (x0 - HANDLE_OUT <= x <= x1 + HANDLE_OUT and y0 - HANDLE_OUT <= y <= y1 + HANDLE_OUT):
            return None
        on_l, on_r = x0 - HANDLE_OUT <= x <= x0 + HANDLE_IN, x1 - HANDLE_IN <= x <= x1 + HANDLE_OUT
        on_t, on_b = y0 - HANDLE_OUT <= y <= y0 + HANDLE_IN, y1 - HANDLE_IN <= y <= y1 + HANDLE_OUT
        if not (on_l or on_r or on_t or on_b):
            return None
        near_x = min(abs(x - x0), abs(x - x1)) <= HANDLE_CORNER
        near_y = min(abs(y - y0), abs(y - y1)) <= HANDLE_CORNER
        v = "n" if on_t else "s" if on_b else ""
        h = "w" if on_l else "e" if on_r else ""
        if v and not h and near_x:
            h = "w" if abs(x - x0) <= abs(x - x1) else "e"
        if h and not v and near_y:
            v = "n" if abs(y - y0) <= abs(y - y1) else "s"
        return (v + h) or None

    def begin_resize(self, handle):
        """Redimensionar a seleção do extrator: vira um arrasto de retângulo normal (tela clara, sem caixas) e refaz a varredura ao soltar."""
        x0, y0, x1, y1 = self.ts.rect
        fx = x1 if "w" in handle else x0 if "e" in handle else None      # ponto fixo
        fy = y1 if "n" in handle else y0 if "s" in handle else None
        self.ts.reset()
        self.bar_ocr.set_copy_enabled(False)
        self.mini.hide()
        self.anchor = (x0 if fx is None else fx, y0 if fy is None else fy)
        self._edge = (handle, (x0, y0, x1, y1))
        self.sel = (x0, y0, x1, y1)
        self._moved = False
        self.da.queue_draw()

    def _resize_point(self, x, y):
        """Aplica a trava de eixo das alças de lado ao ponto do ponteiro."""
        edge = getattr(self, "_edge", None)
        if edge is None:
            return x, y
        handle, (x0, y0, x1, y1) = edge
        if handle in ("n", "s"):
            x = x1 if self.anchor[0] == x0 else x0
        if handle in ("e", "w"):
            y = y1 if self.anchor[1] == y0 else y0
        return x, y

    def show_start_button(self):
        """Modo vídeo, região escolhida: a barra vira [● Iniciar] 00:00:00 [mic] [áudio] | [fechar]."""
        self.bar.show_record()
        self.bar.set_margin_start(self._bar_x(REC_W))

    def _start_clicked(self):
        if self.sel:
            x0, y0, x1, y1 = self.sel
            self.finish("video", (x0, y0, x1 - x0, y1 - y0))

    def on_key(self, win, ev):
        key = ev.keyval
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        if key == Gdk.KEY_Escape:
            self.finish("cancel", None)              # medido no Windows: um Esc fecha a sobreposição
            return True
        if self.tool == "ocr" and ctrl and key in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_selected_text()
            return True
        if self.tool == "ocr" and ctrl and key in (Gdk.KEY_a, Gdk.KEY_A) and self.ts.phase == "ready":
            self.ts.select_all()
            self.place_mini(self.ts.rect[2] - OT.MINI_W, self.ts.rect[3])
            self.da.queue_draw()
            return True
        if ctrl and key in (Gdk.KEY_e, Gdk.KEY_E):
            self._toggle_markup()
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

    def _grab(self):
        win = self.get_window()
        if win is None or self._done:
            return False
        seat = self.display.get_default_seat()
        st = seat.grab(win, Gdk.SeatCapabilities.ALL, True, None, None, None)      # sem cursor de grab: o cursor da janela (mutável) vale
        if st != Gdk.GrabStatus.SUCCESS and self._grab_tries < 20:
            self._grab_tries += 1
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
        self.notice.stop()
        self.hide()
        self.destroy()
        GLib.timeout_add(60, lambda: (self.on_result(kind, payload), False)[1])
