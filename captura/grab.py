"""Captura de tela (X11): tela inteira congelada, monitores, janelas (Wnck) e recortes."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
gi.require_version("Wnck", "3.0")
import cairo
from gi.repository import Gdk, Wnck


def root_scale():
    return Gdk.get_default_root_window().get_scale_factor()


def grab_screen():
    """Congela a área de trabalho inteira (todos os monitores). Devolve uma ImageSurface ARGB32."""
    root = Gdk.get_default_root_window()
    _x, _y, w, h = root.get_geometry()  # consulta o X11; o tamanho em cache pode estar na escala anterior
    pb = Gdk.pixbuf_get_from_window(root, 0, 0, w, h)
    surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
    cr = cairo.Context(surf)
    Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
    cr.paint()
    # A imagem do GDK tem pixels nativos, mas o desenho e os eventos usam coordenadas lógicas.
    scale = root.get_scale_factor()
    surf.set_device_scale(scale, scale)
    return surf


def logical_size(surface):
    sx, sy = surface.get_device_scale()
    return int(surface.get_width() / sx), int(surface.get_height() / sy)


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
    scale = root_scale()
    for win in reversed(scr.get_windows_stacked()):
        try:
            if win.is_minimized() or win.get_window_type() in _SKIP:
                continue
            if ws is not None and not win.is_on_workspace(ws) and not win.is_pinned():
                continue
            x, y, w, h = win.get_geometry()
            x0, y0 = x // scale, y // scale
            x1, y1 = (x + w + scale - 1) // scale, (y + h + scale - 1) // scale
            if x1 - x0 > 1 and y1 - y0 > 1:
                res.append((x0, y0, x1 - x0, y1 - y0, win.get_name() or ""))
        except Exception:
            continue
    return res


def clamp_rect(x, y, w, h, sw, sh):
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(sw, x + w), min(sh, y + h)
    return x0, y0, max(0, x1 - x0), max(0, y1 - y0)


def crop_pixbuf(surface, x, y, w, h):
    sx, sy = surface.get_device_scale()
    x, y, w, h = clamp_rect(int(x * sx), int(y * sy), int(w * sx), int(h * sy),
                           surface.get_width(), surface.get_height())
    if w < 1 or h < 1:
        return None
    return Gdk.pixbuf_get_from_surface(surface, x, y, w, h)


def crop_freeform(surface, points):
    """Recorta a região delimitada por `points` (lista de (x, y)); fora do laço fica transparente."""
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    sw, sh = logical_size(surface)
    x1, y1 = min(sw, int(max(xs)) + 1), min(sh, int(max(ys)) + 1)
    w, h = x1 - x0, y1 - y0
    if w < 2 or h < 2:
        return None
    sx, sy = surface.get_device_scale()
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, int(w * sx), int(h * sy))
    cr = cairo.Context(out)
    cr.scale(sx, sy)
    cr.move_to(points[0][0] - x0, points[0][1] - y0)
    for px, py in points[1:]:
        cr.line_to(px - x0, py - y0)
    cr.close_path()
    cr.clip()
    cr.set_source_surface(surface, -x0, -y0)
    cr.paint()
    return Gdk.pixbuf_get_from_surface(out, 0, 0, out.get_width(), out.get_height())


def pixel_at(surface, x, y):
    sx, sy = surface.get_device_scale()
    x, y = int(x * sx), int(y * sy)
    if not (0 <= x < surface.get_width() and 0 <= y < surface.get_height()):
        return (0, 0, 0)
    surface.flush()
    data = surface.get_data()
    stride = surface.get_stride()
    o = y * stride + x * 4
    return (data[o + 2], data[o + 1], data[o])  # BGRA little-endian
