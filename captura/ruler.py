"""Viewport-only ruler. Never part of the exported annotation model."""
import math
import cairo


class Ruler:
    def __init__(self, x, y):
        self.x, self.y = x, y
        self.angle = 0.0
        self.thickness = 120.0

    def local(self, x, y):
        a = math.radians(self.angle)
        dx, dy = x - self.x, y - self.y
        return dx*math.cos(a) + dy*math.sin(a), -dx*math.sin(a) + dy*math.cos(a)

    def contains(self, x, y, inset=0):
        return abs(self.local(x,y)[1]) < self.thickness/2 - inset

    def draw(self, cr, width, height):
        length = math.hypot(width, height) * 2
        half = self.thickness / 2
        cr.save()
        cr.translate(self.x, self.y)
        cr.rotate(math.radians(self.angle))
        cr.rectangle(-length, -half, 2 * length, self.thickness)
        cr.set_source_rgba(230/255, 230/255, 230/255, .7)
        cr.fill()
        cr.set_line_width(1)
        cr.set_source_rgba(0, 0, 0, .72)
        for y in (-half + .5, half - .5):
            cr.move_to(-length, y)
            cr.line_to(length, y)
        for x in range(-int(length)//5*5, int(length)+1, 5):
            tick = 20 if x % 50 == 0 else 16 if x % 25 == 0 else 12
            for sign in (-1, 1):
                cr.move_to(x+.5, sign*(half-.5))
                cr.line_to(x+.5, sign*(half-tick))
        cr.stroke()
        # Angle dial, observed at the middle of the Windows ruler.
        for deg in range(0, 360, 15):
            a = math.radians(deg)
            inner = 21 if deg % 45 == 0 else 24
            cr.move_to(math.cos(a)*inner, math.sin(a)*inner)
            cr.line_to(math.cos(a)*29, math.sin(a)*29)
        cr.stroke()
        cr.rotate(-math.radians(self.angle))
        cr.select_font_face('Selawik', cairo.FONT_SLANT_NORMAL, cairo.FONT_WEIGHT_NORMAL)
        cr.set_font_size(14)
        label = f'{round(self.angle) % 360}°'
        ext = cr.text_extents(label)
        cr.move_to(-ext.width/2-ext.x_bearing, -ext.height/2-ext.y_bearing)
        cr.show_text(label)
        cr.restore()
