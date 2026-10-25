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


def white_base(size=100):
    base = cairo.ImageSurface(cairo.FORMAT_ARGB32, size, size)
    cr = cairo.Context(base)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    return base


class OpacityAndNoneTests(unittest.TestCase):
    def test_fill_alpha_blends_with_the_image(self):
        shape = annot.Shape('rect', 10, 10, 90, 90, '#ff0000', 4)
        shape.fill, shape.fill_alpha = '#0000ff', 0.5
        px = pixel(annot.render(white_base(), [shape]), 50, 50)
        self.assertTrue(px[0] == 255 and abs(px[1] - 128) <= 2 and abs(px[2] - 128) <= 2, px)   # BGRA

    def test_outline_alpha_blends_with_the_image(self):
        shape = annot.Shape('rect', 10, 10, 90, 90, '#000000', 6)
        shape.alpha = 0.5
        px = pixel(annot.render(white_base(), [shape]), 10, 50)
        self.assertTrue(abs(px[0] - 128) <= 2 and px[0] == px[1] == px[2], px)

    def test_none_outline_draws_only_the_fill(self):
        shape = annot.Shape('rect', 10, 10, 90, 90, None, 4)
        shape.fill = '#0000ff'
        out = annot.render(white_base(), [shape])
        self.assertEqual(pixel(out, 50, 50), (255, 0, 0, 255))      # BGRA: azul
        self.assertEqual(pixel(out, 10, 50), (255, 0, 0, 255))   # sem contorno por cima
        self.assertEqual(pixel(out, 5, 50), (255, 255, 255, 255))
        self.assertTrue(shape.hit(50, 50, 1))

    def test_none_outline_and_none_fill_is_invisible_but_not_selectable_inside(self):
        shape = annot.Shape('rect', 10, 10, 90, 90, None, 4)
        self.assertEqual(pixel(annot.render(white_base(), [shape]), 10, 50), (255, 255, 255, 255))
        self.assertFalse(shape.hit(50, 50, 1))

    def test_defaults_are_fully_opaque_and_survive_clone(self):
        shape = annot.Shape('ellipse', 0, 0, 10, 10, '#ff0000', 2)
        self.assertEqual((shape.alpha, shape.fill_alpha), (1.0, 1.0))
        shape.alpha = 0.3
        self.assertEqual(annot.clone([shape])[0].alpha, 0.3)


if __name__ == '__main__':
    unittest.main()
