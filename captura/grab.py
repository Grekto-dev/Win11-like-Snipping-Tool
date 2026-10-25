"""Captura de tela (X11): tela inteira congelada, monitores, janelas (Wnck) e recortes."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Wnck", "3.0")
import cairo
from gi.repository import Gdk, Wnck


def grab_screen():
    """Congela a área de trabalho inteira (todos os monitores). Devolve uma ImageSurface ARGB32."""
    root = Gdk.get_default_root_window()
    w, h = root.get_width(), root.get_height()
    pb = Gdk.pixbuf_get_from_window(root, 0, 0, w, h)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(surf)
    Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
    cr.paint()
    return surf


def monitors():
    d = Gdk.Display.get_default()
    out = []
    for i in range(d.get_n_monitors()):
        g = d.get_monitor(i).get_geometry()
        out.append((g.x, g.y, g.width, g.height))
    return out


def pointer_position():
    seat = Gdk.Display.get_default().get_default_seat()
    _, x, y = seat.get_pointer().get_position()
    return x, y


def monitor_at(x, y):
    ms = monitors()
    for m in ms:
        if m[0] <= x < m[0] + m[2] and m[1] <= y < m[1] + m[3]:
            return m
    return ms[0]


def screen_size():
    root = Gdk.get_default_root_window()
    return root.get_width(), root.get_height()


_SKIP = (Wnck.WindowType.DESKTOP, Wnck.WindowType.DOCK, Wnck.WindowType.SPLASHSCREEN, Wnck.WindowType.MENU)


def list_windows():
    """Janelas visíveis, da mais alta para a mais baixa na pilha: [(x, y, w, h, nome)]."""
    scr = Wnck.Screen.get_default()
    scr.force_update()
    ws = scr.get_active_workspace()
    res = []
    for win in reversed(scr.get_windows_stacked()):
        try:
            if win.is_minimized() or win.get_window_type() in _SKIP:
                continue
            if ws is not None and not win.is_on_workspace(ws) and not win.is_pinned():
                continue
            x, y, w, h = win.get_geometry()
            if w > 1 and h > 1:
                res.append((x, y, w, h, win.get_name() or ""))
        except Exception:
            continue
    return res


def clamp_rect(x, y, w, h, sw, sh):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(sw, x + w), min(sh, y + h)
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def crop_pixbuf(surface, x, y, w, h):
    x, y, w, h = clamp_rect(int(x), int(y), int(w), int(h), surface.get_width(), surface.get_height())
    if w < 1 or h < 1:
        return None
    return Gdk.pixbuf_get_from_surface(surface, x, y, w, h)


def crop_freeform(surface, points):
    """Recorta a região delimitada por `points` (lista de (x, y)); fora do laço fica transparente."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(surface.get_width(), int(max(xs)) + 1), min(surface.get_height(), int(max(ys)) + 1)
    w, h = x1 - x0, y1 - y0
    if w < 2 or h < 2:
        return None
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(out)
    cr.move_to(points[0][0] - x0, points[0][1] - y0)
    for px, py in points[1:]:
        cr.line_to(px - x0, py - y0)
    cr.close_path()
    cr.clip()
    cr.set_source_surface(surface, -x0, -y0)
    cr.paint()
    return Gdk.pixbuf_get_from_surface(out, 0, 0, w, h)


def pixel_at(surface, x, y):
    x, y = int(x), int(y)
    if not (0 <= x < surface.get_width() and 0 <= y < surface.get_height()):
        return (0, 0, 0)
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()
    o = y * stride + x * 4
    return (data[o + 2], data[o + 1], data[o])  # BGRA little-endian
