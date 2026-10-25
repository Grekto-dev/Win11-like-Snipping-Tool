import gi
gi.require_version("Gtk", "3.0")
import math
import unittest
from types import SimpleNamespace
import cairo
from gi.repository import Gtk
from captura.canvas import Canvas
from captura import annot


class EmojiCanvasTests(unittest.TestCase):
    def setUp(self):
        self.c = Canvas()
        self.c.set_size_request(640, 480)
        self.win = Gtk.OffscreenWindow(); self.win.add(self.c); self.win.show_all()
        self.addCleanup(self.win.destroy)
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        cr = cairo.Context(s); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.c.set_image(s)
        self.c.set_tool("shape")

    def ev(self, ix, iy):
        ox, oy = self.c.origin(); z = self.c.zoom
        return SimpleNamespace(x=ox + ix * z, y=oy + iy * z, button=1, state=0)

    def drag(self, a, b):
        self.c.on_press(self.c, self.ev(*a)); self.c.on_motion(self.c, self.ev(*b)); self.c.on_release(self.c, self.ev(*b))

    def test_add_emoji_places_selected_item_at_center_and_marks_dirty(self):
        e = self.c.add_emoji("❤")
        self.assertIs(self.c.items[-1], e)
        self.assertIs(self.c.sel, e)
        self.assertEqual((e.cx, e.cy), (200, 150))
        self.assertTrue(self.c.dirty)
        self.c.undo()
        self.assertEqual(self.c.items, [])

    def test_dragging_body_moves_emoji_instead_of_drawing_a_shape(self):
        e = self.c.add_emoji("⭐")
        self.drag((200, 150), (250, 170))
        self.assertEqual(len(self.c.items), 1)
        self.assertEqual((round(e.cx), round(e.cy)), (250, 170))

    def test_corner_handle_resizes_and_rotate_handle_rotates(self):
        e = self.c.add_emoji("🔥")
        x, y = e.handles()["se"]
        self.drag((x, y), (x + 20, y + 20))
        self.assertGreater(e.size, 60)
        rx, ry = e.handles()["rot"]
        self.drag((rx, ry), (e.cx + 100, e.cy))
        self.assertAlmostEqual(e.angle, math.pi / 2, places=2)

    def test_delete_key_removes_selected_emoji_and_eraser_hits_it(self):
        e = self.c.add_emoji("👍")
        self.c.on_key(self.c, SimpleNamespace(keyval=__import__("gi").repository.Gdk.KEY_Delete))
        self.assertEqual(self.c.items, [])
        e = self.c.add_emoji("👍")
        self.c.set_tool("eraser")
        self.c.erase_at(e.cx, e.cy)
        self.assertEqual(self.c.items, [])

    def test_emoji_is_part_of_exported_pixels_and_selection_ui_is_not(self):
        self.c.add_emoji("❤")
        out = self.c.rendered(); out.flush()
        d, st = out.get_data(), out.get_stride()
        px = d[150 * st + 200 * 4:150 * st + 200 * 4 + 3]
        self.assertGreater(max(px) - min(px), 60)
        corner = d[(150 - 40) * st + (200 - 40) * 4:(150 - 40) * st + (200 - 40) * 4 + 3]
        self.assertEqual(tuple(corner), (255, 255, 255))

    def test_view_draw_with_selected_emoji_does_not_raise(self):
        self.c.add_emoji("😍")
        res = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 480)
        self.c.on_draw(self.c, cairo.Context(res))


if __name__ == "__main__":
    unittest.main()
