"""Tela de edição: imagem centralizada, zoom, caneta, marca-texto, borracha, formas e corte."""
import math
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GObject

from . import annot, theme
from .ruler import Ruler
from . import textlayer

HANDLE_R = 5.5


class Canvas(Gtk.DrawingArea):
    __gsignals__ = {
        "changed": (GObject.SignalFlags.RUN_FIRST, None, ()),       # histórico/estado mudou
        "zoom-changed": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "tool-changed": (GObject.SignalFlags.RUN_FIRST, None, ()),
    }

    def __init__(self):
        super().__init__()
        self.set_can_focus(True)
        self.add_events(Gdk.EventMask.BUTTON_PRESS_MASK | Gdk.EventMask.BUTTON_RELEASE_MASK |
                        Gdk.EventMask.POINTER_MOTION_MASK | Gdk.EventMask.SCROLL_MASK |
                        Gdk.EventMask.SMOOTH_SCROLL_MASK | Gdk.EventMask.KEY_PRESS_MASK |
                        Gdk.EventMask.LEAVE_NOTIFY_MASK)
        self.base = None
        self.items = []
        self.undo_stack = []
        self.redo_stack = []
        self.tool = None                 # None | pen | hl | eraser | shape | crop
        self.zoom = 1.0
        self.fit = True
        self.sel = None                  # Shape selecionada
        self.cur_stroke = None
        self.drag = None
        self.cursor_pos = None
        self.show_ruler = False
        self.ruler = None
        self.ruler_drag = None
        self.text_words = []
        self.text_sel = []
        self.text_drag = None
        self.opts = {"pen": ("#e61b1b", 4), "hl": ("#ffe600", 12), "shape": ("#e61b1b", 3), "shape_kind": "rect"}
        self.crop_rect = None            # (x0, y0, x1, y1) em px da imagem
        self.crop_drag = None
        self.dirty = False
        self.connect("draw", self.on_draw)
        self.connect("button-press-event", self.on_press)
        self.connect("button-release-event", self.on_release)
        self.connect("motion-notify-event", self.on_motion)
        self.connect("scroll-event", self.on_scroll)
        self.connect("key-press-event", self.on_key)
        self.connect("size-allocate", self.on_size)
        self.connect("leave-notify-event", lambda *a: (setattr(self, "cursor_pos", None), self.queue_draw()))

    # ------------------------------------------------------------ dados
    def set_image(self, surface, items=None):
        self.base = surface
        self.items = items or []
        self.undo_stack, self.redo_stack = [], []
        self.sel = None
        self.crop_rect = None
        self.dirty = False
        self.fit = True
        self.update_scale()
        self.queue_draw()
        self.emit("changed")

    def clear(self):
        self.base = None
        self.items = []
        self.undo_stack, self.redo_stack = [], []
        self.queue_draw()
        self.emit("changed")

    def _snapshot(self):
        return (self.base, annot.clone(self.items), list(self.text_words))

    def _restore(self, snap):
        self.base, self.items, self.text_words = snap
        self.text_sel = []

    def push_undo(self):
        self.undo_stack.append(self._snapshot())
        if len(self.undo_stack) > 100:
            self.undo_stack.pop(0)
        self.redo_stack.clear()
        self.dirty = True

    def undo(self):
        if not self.undo_stack:
            return
        self.redo_stack.append(self._snapshot())
        self._restore(self.undo_stack.pop())
        self.sel = None
        self.update_scale()
        self.queue_draw()
        self.emit("changed")

    def redo(self):
        if not self.redo_stack:
            return
        self.undo_stack.append(self._snapshot())
        self._restore(self.redo_stack.pop())
        self.sel = None
        self.update_scale()
        self.queue_draw()
        self.emit("changed")

    def clear_markup(self):
        if self.items:
            self.push_undo()
            self.items = []
            self.sel = None
            self.queue_draw()
            self.emit("changed")

    def rendered(self, border=None):
        return annot.render(self.base, self.items, border)

    # ------------------------------------------------------------ geometria
    def update_scale(self):
        if self.base is None:
            return
        a = self.get_allocation()
        if self.fit and a.width > 1:
            pad = 48 if self.tool != "crop" else 70
            sx = (a.width - pad) / self.base.get_width()
            sy = (a.height - pad) / self.base.get_height()
            self.zoom = max(0.05, min(1.0, sx, sy))
            self.emit("zoom-changed", self.zoom)

    def on_size(self, *a):
        self.update_scale()

    def origin(self):
        a = self.get_allocation()
        w = self.base.get_width() * self.zoom
        h = self.base.get_height() * self.zoom
        return (a.width - w) / 2, (a.height - h) / 2

    def to_img(self, x, y):
        ox, oy = self.origin()
        return (x - ox) / self.zoom, (y - oy) / self.zoom

    def set_zoom(self, z, fit=False):
        self.fit = fit
        self.zoom = max(0.05, min(8.0, z))
        self.emit("zoom-changed", self.zoom)
        self.queue_draw()

    def zoom_by(self, f):
        self.set_zoom(self.zoom * f)

    def add_emoji(self, char, size=48):
        """Insere o emoji no centro da imagem, já selecionado (com alças de redimensionar/girar)."""
        if self.base is None:
            return None
        self.push_undo()
        e = annot.Emoji(char, self.base.get_width() / 2, self.base.get_height() / 2, size)
        self.items.append(e)
        self.sel = e
        self.queue_draw()
        self.emit("changed")
        return e

    def set_text_words(self, words):
        self.text_words = list(words)
        self.text_sel = []
        self.text_drag = None
        self.queue_draw()

    def selected_text(self):
        if self.tool != "text":
            return ""
        return textlayer.words_text(self.text_sel)

    def redact(self, words, pad=2):
        """Cobre palavras com retângulos pretos opacos (anotações desfazíveis)."""
        words = [w for w in words if w in self.text_words]
        if not words or self.base is None:
            return 0
        self.push_undo()
        for w in words:
            x0, y0, x1, y1 = w.box
            s = annot.Shape("rect", x0 - pad, y0 - pad, x1 + pad, y1 + pad, "#000000", 1)
            s.fill = "#000000"
            self.items.append(s)
        self.text_words = [w for w in self.text_words if w not in words]
        self.text_sel = [w for w in self.text_sel if w not in words]
        self.queue_draw()
        self.emit("changed")
        return len(words)

    def set_tool(self, tool):
        changed = tool != self.tool
        self.tool = tool
        self.sel = None
        self.text_sel = []
        self.text_drag = None
        if tool == "crop" and self.base is not None:
            self.crop_rect = (0, 0, self.base.get_width(), self.base.get_height())
            self.fit = True
            self.update_scale()
        else:
            self.crop_rect = None
        self.update_cursor()
        self.queue_draw()
        if changed:
            self.emit("tool-changed")

    def update_cursor(self):
        w = self.get_window()
        if not w:
            return
        d = self.get_display()
        name = {"pen": "crosshair", "hl": "crosshair", "shape": "crosshair", "eraser": "default"}.get(self.tool, "default")
        w.set_cursor(Gdk.Cursor.new_from_name(d, name))

    # ------------------------------------------------------------ desenho
    def on_draw(self, w, cr):
        a = self.get_allocation()
        pal = theme.palette()
        bg = pal["crop_bg"] if self.tool == "crop" else pal["canvas"]
        cr.set_source_rgb(*annot.hex_rgb(bg))
        cr.paint()
        if self.base is None:
            return False
        ox, oy = self.origin()
        cr.save()
        cr.translate(ox, oy)
        cr.scale(self.zoom, self.zoom)
        iw, ih = self.base.get_width(), self.base.get_height()
        cr.set_source_surface(self.base, 0, 0)
        f = cr.get_source()
        if self.zoom < 1:
            f.set_filter(cairo.FILTER_GOOD)
        elif self.zoom >= 2:
            f.set_filter(cairo.FILTER_NEAREST)
        cr.paint()
        cr.save()
        cr.rectangle(0, 0, iw, ih)
        cr.clip()
        annot.draw_all(cr, self.items)
        if self.cur_stroke:
            annot.draw_stroke(cr, self.cur_stroke)
        cr.restore()
        if self.sel is not None:
            self.draw_handles(cr, self.sel)
        if self.tool == "crop" and self.crop_rect:
            self.draw_crop(cr)
        if self.tool == "text":
            self.draw_text_layer(cr, iw, ih)
        cr.restore()
        if self.show_ruler:
            if self.ruler is None:
                self.ruler = Ruler(a.width/2, a.height/2 + 60)
            self.ruler.draw(cr, a.width, a.height)
        if self.tool == "eraser" and self.cursor_pos and self.base is not None:
            x, y = self.cursor_pos
            cr.set_line_width(1.5)
            cr.set_source_rgba(0, 0, 0, .7)
            cr.arc(x, y, 8, 0, 2 * math.pi)
            cr.stroke()
            cr.set_source_rgba(1, 1, 1, .9)
            cr.arc(x, y, 9, 0, 2 * math.pi)
            cr.stroke()
        return False

    def draw_text_layer(self, cr, iw, ih):
        """Esmaece a imagem e mantém as palavras reconhecidas em destaque."""
        cr.save()
        cr.rectangle(0, 0, iw, ih)
        for w in self.text_words:
            x0, y0, x1, y1 = w.box
            cr.rectangle(x0 - 2, y0 - 1, x1 - x0 + 4, y1 - y0 + 2)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.set_source_rgba(0, 0, 0, .5)
        cr.fill()
        cr.restore()
        pal = theme.palette()
        r, g, b = annot.hex_rgb(pal.get("accent", "#0067c0"))
        cr.set_line_width(1.2 / self.zoom)
        for w in self.text_words:
            x0, y0, x1, y1 = w.box
            cr.rectangle(x0 - 2, y0 - 1, x1 - x0 + 4, y1 - y0 + 2)
            if w in self.text_sel:
                cr.set_source_rgba(r, g, b, .35)
                cr.fill_preserve()
            cr.set_source_rgba(r, g, b, .9)
            cr.stroke()
        if self.text_drag:
            x0, y0, x1, y1 = self.text_drag
            cr.rectangle(min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0))
            cr.set_source_rgba(r, g, b, .15)
            cr.fill_preserve()
            cr.set_source_rgba(r, g, b, .9)
            cr.stroke()

    def draw_handles(self, cr, s):
        z = self.zoom
        r = HANDLE_R / z
        if s.kind == "emoji":
            hs = s.handles()
            cr.set_source_rgba(0, 0, 0, .45)
            cr.set_line_width(1 / z)
            cr.move_to(*hs["nw"]); cr.line_to(*hs["ne"]); cr.line_to(*hs["se"]); cr.line_to(*hs["sw"]); cr.close_path()
            cr.stroke()
            tx, ty = (hs["nw"][0] + hs["ne"][0]) / 2, (hs["nw"][1] + hs["ne"][1]) / 2
            cr.move_to(tx, ty); cr.line_to(*hs["rot"]); cr.stroke()
        for name, (hx, hy) in s.handles().items():
            cr.arc(hx, hy, r, 0, 2 * math.pi)
            cr.set_source_rgb(1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgba(0, 0, 0, .55)
            cr.set_line_width(1 / z)
            cr.stroke()

    def draw_crop(self, cr):
        x0, y0, x1, y1 = self.crop_rect
        iw, ih = self.base.get_width(), self.base.get_height()
        z = self.zoom
        cr.set_source_rgba(0.4, 0.4, 0.4, 0.62)
        cr.rectangle(0, 0, iw, ih)
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        cr.set_fill_rule(cairo.FILL_RULE_EVEN_ODD)
        cr.fill()
        cr.set_source_rgb(1, 1, 1)
        cr.set_line_width(1.5 / z)
        cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        cr.stroke()
        # alças em "L" nos cantos e barras nas arestas, como no Windows
        L = 16 / z
        t = 4 / z
        cr.set_line_width(t)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        for (cx, cy, dx, dy) in ((x0, y0, 1, 1), (x1, y0, -1, 1), (x1, y1, -1, -1), (x0, y1, 1, -1)):
            cr.move_to(cx + dx * L, cy)
            cr.line_to(cx, cy)
            cr.line_to(cx, cy + dy * L)
            cr.stroke()
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        S = 11 / z
        for (cx, cy, hz) in ((mx, y0, True), (mx, y1, True), (x0, my, False), (x1, my, False)):
            if hz:
                cr.move_to(cx - S, cy); cr.line_to(cx + S, cy)
            else:
                cr.move_to(cx, cy - S); cr.line_to(cx, cy + S)
            cr.stroke()

    # ------------------------------------------------------------ crop helpers
    def crop_hit(self, ix, iy):
        x0, y0, x1, y1 = self.crop_rect
        tol = 14 / self.zoom
        left, right = abs(ix - x0) <= tol, abs(ix - x1) <= tol
        top, bottom = abs(iy - y0) <= tol, abs(iy - y1) <= tol
        inx = x0 - tol <= ix <= x1 + tol
        iny = y0 - tol <= iy <= y1 + tol
        if left and top: return "nw"
        if right and top: return "ne"
        if right and bottom: return "se"
        if left and bottom: return "sw"
        if top and inx: return "n"
        if bottom and inx: return "s"
        if left and iny: return "w"
        if right and iny: return "e"
        if x0 < ix < x1 and y0 < iy < y1: return "move"
        return None

    def apply_crop(self):
        if not self.crop_rect or self.base is None:
            return False
        x0, y0, x1, y1 = [int(round(v)) for v in self.crop_rect]
        iw, ih = self.base.get_width(), self.base.get_height()
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(iw, x1), min(ih, y1)
        if x1 - x0 < 2 or y1 - y0 < 2:
            return False
        if (x0, y0, x1, y1) == (0, 0, iw, ih):
            return True
        self.push_undo()
        new = cairo.ImageSurface(cairo.FORMAT_ARGB32, x1 - x0, y1 - y0)
        c = cairo.Context(new)
        c.set_source_surface(self.base, -x0, -y0)
        c.paint()
        for it in self.items:
            it.translate(-x0, -y0)
        self.base = new
        self.text_words = []
        self.text_sel = []
        self.crop_rect = None
        self.fit = True
        self.update_scale()
        self.queue_draw()
        self.emit("changed")
        return True

    # ------------------------------------------------------------ eventos
    def find_item(self, ix, iy, kinds=None):
        tol = 6 / self.zoom
        for it in reversed(self.items):
            if kinds and it.kind not in kinds:
                continue
            if it.hit(ix, iy, tol):
                return it
        return None

    def handle_at(self, s, ix, iy):
        r = (HANDLE_R + 4) / self.zoom
        for name, (hx, hy) in s.handles().items():
            if math.hypot(ix - hx, iy - hy) <= r:
                return name
        return None

    def on_press(self, w, ev):
        self.grab_focus()
        if self.base is None or ev.button != 1:
            return False
        if self.show_ruler and self.ruler and self.ruler.contains(ev.x, ev.y, inset=3):
            self.ruler_drag = (ev.x, ev.y, self.ruler.x, self.ruler.y)
            return True
        ix, iy = self.to_img(ev.x, ev.y)
        t = self.tool
        if t == "text":
            self.text_drag = (ix, iy, ix, iy)
            self.queue_draw()
            return True
        if t in ("pen", "hl"):
            col, size = self.opts[t]
            self.cur_stroke = annot.Stroke(t, [(ix, iy)], col, size)
        elif t == "eraser":
            self.erase_at(ix, iy, first=True)
            self.drag = ("erase",)
        elif t == "shape":
            if self.sel is not None:
                h = self.handle_at(self.sel, ix, iy)
                if h:
                    self.push_undo()
                    self.drag = ("handle", h)
                    return True
            hit = self.find_item(ix, iy, ("shape", "emoji"))
            if hit is not None:
                self.sel = hit
                self.push_undo()
                self.drag = ("move", ix, iy)
            else:
                col, size = self.opts["shape"]
                s = annot.Shape(self.opts["shape_kind"], ix, iy, ix, iy, col, size)
                self.push_undo()
                s.fill = self.opts.get("shape_fill")
                s.alpha = self.opts.get("shape_alpha", 1.0)
                s.fill_alpha = self.opts.get("shape_fill_alpha", 1.0)
                self.items.append(s)
                self.sel = s
                self.drag = ("new",)
        elif t == "crop":
            h = self.crop_hit(ix, iy)
            if h:
                self.crop_drag = (h, ix, iy, self.crop_rect)
        else:
            hit = self.find_item(ix, iy, ("shape", "emoji"))
            self.sel = hit
            if hit is not None:
                h = self.handle_at(hit, ix, iy)
                self.push_undo()
                self.drag = ("handle", h) if h else ("move", ix, iy)
        self.queue_draw()
        return True

    def on_motion(self, w, ev):
        if self.ruler_drag and self.ruler:
            sx, sy, rx, ry = self.ruler_drag
            self.ruler.x, self.ruler.y = rx + ev.x - sx, ry + ev.y - sy
            self.queue_draw()
            return True
        self.cursor_pos = (ev.x, ev.y)
        if self.base is None:
            return False
        ix, iy = self.to_img(ev.x, ev.y)
        if self.text_drag:
            self.text_drag = (self.text_drag[0], self.text_drag[1], ix, iy)
            self.queue_draw()
            return True
        if self.cur_stroke:
            last = self.cur_stroke.pts[-1]
            if math.hypot(ix - last[0], iy - last[1]) * self.zoom >= 1.2:
                self.cur_stroke.pts.append((ix, iy))
        elif self.drag:
            d = self.drag
            if d[0] == "erase":
                self.erase_at(ix, iy)
            elif d[0] == "new" and self.sel is not None:
                self.sel.x1, self.sel.y1 = ix, iy
                if ev.state & Gdk.ModifierType.SHIFT_MASK and self.sel.shape in ("rect", "ellipse"):
                    s = max(abs(ix - self.sel.x0), abs(iy - self.sel.y0))
                    self.sel.x1 = self.sel.x0 + math.copysign(s, ix - self.sel.x0)
                    self.sel.y1 = self.sel.y0 + math.copysign(s, iy - self.sel.y0)
            elif d[0] == "handle" and self.sel is not None:
                self.sel.drag_handle(d[1], ix, iy)
            elif d[0] == "move" and self.sel is not None:
                self.sel.translate(ix - d[1], iy - d[2])
                self.drag = ("move", ix, iy)
        elif self.crop_drag:
            h, sx, sy, r0 = self.crop_drag
            x0, y0, x1, y1 = r0
            iw, ih = self.base.get_width(), self.base.get_height()
            dx, dy = ix - sx, iy - sy
            if h == "move":
                w_, h_ = x1 - x0, y1 - y0
                nx = min(max(0, x0 + dx), iw - w_)
                ny = min(max(0, y0 + dy), ih - h_)
                self.crop_rect = (nx, ny, nx + w_, ny + h_)
            else:
                if "w" in h: x0 = min(max(0, x0 + dx), x1 - 8)
                if "e" in h: x1 = max(min(iw, x1 + dx), x0 + 8)
                if "n" in h: y0 = min(max(0, y0 + dy), y1 - 8)
                if "s" in h: y1 = max(min(ih, y1 + dy), y0 + 8)
                self.crop_rect = (x0, y0, x1, y1)
        elif self.tool == "crop" and self.crop_rect:
            h = self.crop_hit(ix, iy)
            names = {"nw": "nw-resize", "ne": "ne-resize", "se": "se-resize", "sw": "sw-resize", "n": "n-resize",
                     "s": "s-resize", "e": "e-resize", "w": "w-resize", "move": "move", None: "default"}
            self.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), names[h]))
        elif self.tool in (None, "shape") and self.sel is not None:
            h = self.handle_at(self.sel, ix, iy)
            hit = self.find_item(ix, iy, ("shape", "emoji"))
            nm = "pointer" if h else ("move" if hit is not None else ("crosshair" if self.tool == "shape" else "default"))
            self.get_window().set_cursor(Gdk.Cursor.new_from_name(self.get_display(), nm))
        self.queue_draw()
        return True

    def on_release(self, w, ev):
        if ev.button != 1:
            return False
        if self.ruler_drag:
            self.ruler_drag = None
            return True
        if self.text_drag:
            x0, y0, x1, y1 = self.text_drag
            self.text_drag = None
            if abs(x1 - x0) * self.zoom < 3 and abs(y1 - y0) * self.zoom < 3:
                hit = [w for w in self.text_words if w.box[0] <= x0 <= w.box[2] and w.box[1] <= y0 <= w.box[3]]
                self.text_sel = hit[:1]
            else:
                self.text_sel = textlayer.words_in_rect(self.text_words, (x0, y0, x1, y1))
            self.queue_draw()
            self.emit("changed")
            return True
        if self.cur_stroke:
            self.push_undo()
            self.items.append(self.cur_stroke)
            self.cur_stroke = None
            self.emit("changed")
        if self.drag:
            d = self.drag
            if d[0] == "new" and self.sel is not None:
                dx = abs(self.sel.x1 - self.sel.x0)
                dy = abs(self.sel.y1 - self.sel.y0)
                if dx < 3 and dy < 3:
                    self.items.remove(self.sel)
                    self.undo_stack.pop()
                    self.sel = None
            self.drag = None
            self.emit("changed")
        self.crop_drag = None
        self.queue_draw()
        return True

    def erase_at(self, ix, iy, first=False):
        tol = 8 / self.zoom
        for it in reversed(self.items):
            if it.hit(ix, iy, tol):
                self.push_undo()
                self.items.remove(it)
                self.emit("changed")
                return

    def on_scroll(self, w, ev):
        if (self.show_ruler and self.ruler and self.ruler.contains(ev.x, ev.y)
                and not ev.state & Gdk.ModifierType.CONTROL_MASK):
            if ev.direction == Gdk.ScrollDirection.UP:
                delta = 1
            elif ev.direction == Gdk.ScrollDirection.DOWN:
                delta = -1
            elif ev.direction == Gdk.ScrollDirection.SMOOTH:
                delta = -ev.delta_y
            else:
                return False
            self.ruler.angle = (self.ruler.angle + delta) % 360
            self.queue_draw()
            return True
        if ev.state & Gdk.ModifierType.CONTROL_MASK:
            if ev.direction == Gdk.ScrollDirection.UP:
                self.zoom_by(1.1)
            elif ev.direction == Gdk.ScrollDirection.DOWN:
                self.zoom_by(1 / 1.1)
            elif ev.direction == Gdk.ScrollDirection.SMOOTH:
                self.zoom_by(1.1 if ev.delta_y < 0 else 1 / 1.1)
            return True
        return False

    def on_key(self, w, ev):
        if ev.keyval in (Gdk.KEY_Delete, Gdk.KEY_BackSpace) and self.sel is not None and self.sel in self.items:
            self.push_undo()
            self.items.remove(self.sel)
            self.sel = None
            self.queue_draw()
            self.emit("changed")
            return True
        return False
