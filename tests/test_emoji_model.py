import gi
gi.require_version("Gtk", "3.0")
import math
import unittest
import cairo
from captura import annot


def pixels(items, size=(120, 120)):
    base = cairo.ImageSurface(cairo.FORMAT_ARGB32, *size)
    cr = cairo.Context(base); cr.set_source_rgb(1, 1, 1); cr.paint()
    out = annot.render(base, items)
    out.flush()
    return out, out.get_data(), out.get_stride()


class EmojiModelTests(unittest.TestCase):
    def test_renders_color_glyph_inside_its_square(self):
        e = annot.Emoji("❤", 60, 60, 60)
        out, data, stride = pixels([e])
        colored = [(x, y) for y in range(120) for x in range(120)
                   if max(data[y*stride+x*4:y*stride+x*4+3]) - min(data[y*stride+x*4:y*stride+x*4+3]) > 60]
        self.assertGreater(len(colored), 400, "glyph colorido ausente")
        xs, ys = [p[0] for p in colored], [p[1] for p in colored]
        self.assertTrue(25 <= min(xs) and max(xs) <= 95 and 25 <= min(ys) and max(ys) <= 95, (min(xs), max(xs), min(ys), max(ys)))

    def test_rotation_moves_pixels_around_center(self):
        flat = pixels([annot.Emoji("👍", 60, 60, 60)])[1]
        e = annot.Emoji("👍", 60, 60, 60); e.angle = math.pi / 2
        rot = pixels([e])[1]
        self.assertNotEqual(bytes(flat), bytes(rot))

    def test_handles_follow_rotation_and_rotate_handle_sits_above(self):
        e = annot.Emoji("⭐", 100, 100, 40)
        h = e.handles()
        self.assertEqual((h["nw"], h["se"]), ((80, 80), (120, 120)))
        self.assertEqual(h["rot"][0], 100)
        self.assertLess(h["rot"][1], 80)
        e.angle = math.pi / 2
        h = e.handles()
        self.assertAlmostEqual(h["nw"][0], 120); self.assertAlmostEqual(h["nw"][1], 80)

    def test_corner_drag_resizes_around_center_and_rot_drag_sets_angle(self):
        e = annot.Emoji("⭐", 100, 100, 40)
        e.drag_handle("se", 130, 130)
        self.assertAlmostEqual(e.size, 60)
        self.assertEqual((e.cx, e.cy), (100, 100))
        e.drag_handle("rot", 150, 100)       # à direita do centro → +90°
        self.assertAlmostEqual(e.angle, math.pi / 2)

    def test_hit_translate_and_clone(self):
        e = annot.Emoji("🔥", 50, 50, 40)
        self.assertTrue(e.hit(55, 45, 0))
        self.assertFalse(e.hit(90, 90, 0))
        e.translate(10, -5)
        self.assertEqual((e.cx, e.cy), (60, 45))
        c = annot.clone([e])[0]
        c.translate(1, 1)
        self.assertEqual((e.cx, e.cy), (60, 45))

    def test_size_has_a_minimum(self):
        e = annot.Emoji("⭐", 100, 100, 40)
        e.drag_handle("se", 101, 101)
        self.assertGreaterEqual(e.size, 12)


if __name__ == "__main__":
    unittest.main()
