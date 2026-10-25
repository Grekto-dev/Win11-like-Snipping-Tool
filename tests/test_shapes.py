"""Regressões do preenchimento: renderização e seleção da geometria."""
import unittest
import cairo
from captura import annot


def pixel(s, x, y):
    s.flush()
    o = y * s.get_stride() + x * 4
    return tuple(s.get_data()[o:o + 4])


class FillTests(unittest.TestCase):
    def test_fill_is_rendered_without_replacing_outline(self):
        base = cairo.ImageSurface(cairo.FORMAT_ARGB32, 100, 100)
        cr = cairo.Context(base)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        shape = annot.Shape('rect', 10, 10, 90, 90, '#ff0000', 4)
        shape.fill = '#0000ff'
        result = annot.render(base, [shape])
        self.assertEqual(pixel(result, 50, 50), (255, 0, 0, 255))
        self.assertEqual(pixel(result, 10, 50), (0, 0, 255, 255))
        self.assertTrue(shape.hit(50, 50, 1))


if __name__ == '__main__':
    unittest.main()
