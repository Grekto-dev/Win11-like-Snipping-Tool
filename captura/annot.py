"""Modelo de anotações e renderização (tela e exportação) com cairo."""
import copy
import math
import cairo

# Paletas medidas no Windows 11 (Ferramenta de Captura 11.2608)
PEN_COLORS = [
    "#000000", "#ffffff", "#d1d3d4", "#a7a9ac", "#808285", "#58595b",
    "#b31564", "#e61b1b", "#ff5500", "#ffaa00", "#ffce00", "#ffe600",
    "#a2e61b", "#26e600", "#008055", "#00aacc", "#004de6", "#3d00b8",
    "#6600cc", "#600080", "#f7d7c4", "#bb9167", "#8e562e", "#613d30",
    "#ff80ff", "#ffc680", "#ffff80", "#80ff9e", "#80d6ff", "#bcb3ff",
]
HL_COLORS = ["#ffe600", "#26e600", "#44c8f5", "#ec008c", "#ff5500", "#6600cc"]

SHAPE_KINDS = [("rect", "Retângulo", "square"), ("ellipse", "Elipse", "ellipse"),
               ("line", "Linha", "line"), ("arrow", "Seta", "arrow")]


def hex_rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


class Stroke:
    kind = "stroke"

    def __init__(self, tool, pts, color, size):
        self.tool = tool          # pen | hl
        self.pts = list(pts)
        self.color = color
        self.size = size

    def bbox(self):
        xs = [p[0] for p in self.pts]
        ys = [p[1] for p in self.pts]
        m = self.size / 2 + 2
        return min(xs) - m, min(ys) - m, max(xs) + m, max(ys) + m

    def hit(self, x, y, tol):
        r = self.size / 2 + tol
        pts = self.pts
        if len(pts) == 1:
            return math.hypot(x - pts[0][0], y - pts[0][1]) <= r
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if dist_seg(x, y, x0, y0, x1, y1) <= r:
                return True
        return False

    def translate(self, dx, dy):
        self.pts = [(x + dx, y + dy) for x, y in self.pts]


class Shape:
    kind = "shape"

    def __init__(self, shape, x0, y0, x1, y1, color, size):
        self.shape = shape        # rect | ellipse | line | arrow
        self.x0, self.y0, self.x1, self.y1 = x0, y0, x1, y1
        self.color = color
        self.size = size

    def bbox(self):
        m = self.size + 10
        return (min(self.x0, self.x1) - m, min(self.y0, self.y1) - m,
                max(self.x0, self.x1) + m, max(self.y0, self.y1) + m)

    def handles(self):
        if self.shape in ("line", "arrow"):
            return {"p0": (self.x0, self.y0), "p1": (self.x1, self.y1)}
        l, r = min(self.x0, self.x1), max(self.x0, self.x1)
        t, b = min(self.y0, self.y1), max(self.y0, self.y1)
        return {"nw": (l, t), "ne": (r, t), "se": (r, b), "sw": (l, b)}

    def hit(self, x, y, tol):
        r = self.size / 2 + tol
        l, rr = min(self.x0, self.x1), max(self.x0, self.x1)
        t, b = min(self.y0, self.y1), max(self.y0, self.y1)
        if self.shape in ("line", "arrow"):
            return dist_seg(x, y, self.x0, self.y0, self.x1, self.y1) <= r
        if self.shape == "rect":
            inside = l - r <= x <= rr + r and t - r <= y <= b + r
            core = l + r < x < rr - r and t + r < y < b - r
            return inside and not core
        cx, cy = (l + rr) / 2, (t + b) / 2
        a, bb = max(1, (rr - l) / 2), max(1, (b - t) / 2)
        v = math.hypot((x - cx) / a, (y - cy) / bb)
        return abs(v - 1) * min(a, bb) <= r

    def translate(self, dx, dy):
        self.x0 += dx; self.x1 += dx; self.y0 += dy; self.y1 += dy

    def drag_handle(self, name, x, y):
        if name == "p0":
            self.x0, self.y0 = x, y
        elif name == "p1":
            self.x1, self.y1 = x, y
        else:
            l, r = min(self.x0, self.x1), max(self.x0, self.x1)
            t, b = min(self.y0, self.y1), max(self.y0, self.y1)
            if "n" in name: t = y
            if "s" in name: b = y
            if "w" in name: l = x
            if "e" in name: r = x
            self.x0, self.y0, self.x1, self.y1 = l, t, r, b


def dist_seg(px, py, x0, y0, x1, y1):
    dx, dy = x1 - x0, y1 - y0
    if dx == 0 and dy == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0, min(1, ((px - x0) * dx + (py - y0) * dy) / (dx * dx + dy * dy)))
    return math.hypot(px - (x0 + t * dx), py - (y0 + t * dy))


def _smooth_path(cr, pts):
    cr.move_to(*pts[0])
    if len(pts) == 1:
        cr.line_to(pts[0][0] + 0.01, pts[0][1])
        return
    if len(pts) == 2:
        cr.line_to(*pts[1])
        return
    for i in range(1, len(pts) - 1):
        mx, my = (pts[i][0] + pts[i + 1][0]) / 2, (pts[i][1] + pts[i + 1][1]) / 2
        cr.curve_to(*_quad_to_cubic(cr.get_current_point(), pts[i], (mx, my)))
    cr.line_to(*pts[-1])


def _quad_to_cubic(p0, c, p1):
    return (p0[0] + 2 / 3 * (c[0] - p0[0]), p0[1] + 2 / 3 * (c[1] - p0[1]),
            p1[0] + 2 / 3 * (c[0] - p1[0]), p1[1] + 2 / 3 * (c[1] - p1[1]), p1[0], p1[1])


def draw_stroke(cr, s):
    r, g, b = hex_rgb(s.color)
    cr.save()
    if s.tool == "hl":
        cr.push_group()
        cr.set_source_rgb(r, g, b)
        cr.set_line_cap(cairo.LINE_CAP_BUTT)
        cr.set_line_join(cairo.LINE_JOIN_BEVEL)
        cr.set_line_width(s.size)
        if len(s.pts) == 1:
            x, y = s.pts[0]
            cr.rectangle(x - s.size / 2, y - s.size / 2, s.size, s.size)
            cr.fill()
        else:
            _smooth_path(cr, s.pts)
            cr.stroke()
        cr.pop_group_to_source()
        cr.set_operator(cairo.OPERATOR_MULTIPLY)
        cr.paint()
    else:
        cr.set_source_rgb(r, g, b)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_width(s.size)
        _smooth_path(cr, s.pts)
        cr.stroke()
    cr.restore()


def draw_shape(cr, s):
    r, g, b = hex_rgb(s.color)
    cr.save()
    cr.set_source_rgb(r, g, b)
    cr.set_line_width(s.size)
    cr.set_line_join(cairo.LINE_JOIN_MITER)
    cr.set_line_cap(cairo.LINE_CAP_ROUND)
    l, rr = min(s.x0, s.x1), max(s.x0, s.x1)
    t, bt = min(s.y0, s.y1), max(s.y0, s.y1)
    if s.shape == "rect":
        cr.rectangle(l, t, rr - l, bt - t)
        cr.stroke()
    elif s.shape == "ellipse":
        w, h = max(0.1, rr - l), max(0.1, bt - t)
        cr.save()
        cr.translate((l + rr) / 2, (t + bt) / 2)
        cr.scale(w / 2, h / 2)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        cr.stroke()
    elif s.shape == "line":
        cr.move_to(s.x0, s.y0)
        cr.line_to(s.x1, s.y1)
        cr.stroke()
    elif s.shape == "arrow":
        ang = math.atan2(s.y1 - s.y0, s.x1 - s.x0)
        head = max(12, s.size * 4)
        bx, by = s.x1 - math.cos(ang) * head * 0.6, s.y1 - math.sin(ang) * head * 0.6
        cr.move_to(s.x0, s.y0)
        cr.line_to(bx, by)
        cr.stroke()
        cr.move_to(s.x1, s.y1)
        for da in (math.pi * 0.84, -math.pi * 0.84):
            cr.line_to(s.x1 + math.cos(ang + da) * head, s.y1 + math.sin(ang + da) * head)
            cr.move_to(s.x1, s.y1)
        cr.set_line_width(s.size)
        cr.stroke()
    cr.restore()


def draw_all(cr, items):
    for it in items:
        if it.kind == "stroke":
            draw_stroke(cr, it)
        else:
            draw_shape(cr, it)


def render(base, items, border=None):
    """Renderiza base + anotações em uma nova ImageSurface (resolução original)."""
    w, h = base.get_width(), base.get_height()
    bw = 0
    if border:
        bw = int(border[1])
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, w + 2 * bw, h + 2 * bw)
    cr = cairo.Context(out)
    if bw:
        cr.set_source_rgb(*hex_rgb(border[0]))
        cr.paint()
        cr.translate(bw, bw)
    cr.set_source_surface(base, 0, 0)
    cr.paint()
    cr.rectangle(0, 0, w, h)
    cr.clip()
    draw_all(cr, items)
    return out


def clone(items):
    return [copy.deepcopy(i) for i in items]
