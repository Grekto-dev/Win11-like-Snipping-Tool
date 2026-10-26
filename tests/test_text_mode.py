import gi
gi.require_version("Gtk", "3.0")
import unittest
from types import SimpleNamespace
import cairo
from gi.repository import Gtk, Gdk
from captura.canvas import Canvas
from captura.textlayer import Word


def words():
    return [Word("Nome:", (20, 20, 80, 40), (1, 1, 1)),
            Word("ana@example.com", (90, 20, 230, 40), (1, 1, 1)),
            Word("Fone", (20, 60, 70, 80), (1, 1, 2)),
            Word("11999990000", (80, 60, 190, 80), (1, 1, 2))]


class TextModeTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        self.canvas.set_size_request(640, 480)
        self.window = Gtk.OffscreenWindow()
        self.window.add(self.canvas)
        self.window.show_all()
        self.addCleanup(self.window.destroy)
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 120)
        cr = cairo.Context(surface); cr.set_source_rgb(1, 1, 1); cr.paint()
        self.canvas.set_image(surface)
        self.canvas.set_tool("text")
        self.canvas.set_text_words(words())

    def pointer(self, a, b, double=False):
        ox, oy = self.canvas.origin(); z = self.canvas.zoom
        kind = Gdk.EventType._2BUTTON_PRESS if double else Gdk.EventType.BUTTON_PRESS
        ev = lambda p: SimpleNamespace(x=ox + p[0] * z, y=oy + p[1] * z, button=1, state=0, type=kind)
        self.canvas.on_press(self.canvas, ev(a))
        self.canvas.on_motion(self.canvas, ev(b))
        self.canvas.on_release(self.canvas, ev(b))

    def test_drag_selects_overlapped_words_in_reading_order(self):
        self.pointer((10, 10), (240, 45))
        self.assertEqual(self.canvas.selected_text(), "Nome: ana@example.com")

    def test_double_click_selects_one_word_and_single_click_clears(self):
        self.pointer((100, 30), (100, 30), double=True)
        self.assertEqual(self.canvas.selected_text(), "ana@example.com")
        self.pointer((5, 100), (5, 100))
        self.assertEqual(self.canvas.selected_text(), "")

    def test_drag_follows_reading_order_across_lines(self):
        self.pointer((100, 30), (30, 70))             # do meio da 1ª linha ao começo da 2ª
        self.assertEqual(self.canvas.selected_text(), "ana@example.com\nFone")

    def test_select_all_text(self):
        self.canvas.select_all_text()
        self.assertEqual(len(self.canvas.text_sel), 4)

    def test_remove_redactions_only_removes_black_boxes(self):
        self.canvas.redact([words()[1]])
        self.assertTrue(self.canvas.has_redactions())
        self.assertEqual(self.canvas.remove_redactions(), 1)
        self.assertFalse(self.canvas.has_redactions())
        self.assertEqual(self.canvas.items, [])

    def test_redaction_adds_undoable_opaque_boxes_that_are_exported(self):
        before = bytes(self.canvas.rendered().get_data())
        count = self.canvas.redact([words()[1]])
        self.assertEqual(count, 1)
        self.assertTrue(self.canvas.dirty)
        out = self.canvas.rendered()
        out.flush()
        data = out.get_data(); stride = out.get_stride()
        px = lambda x, y: tuple(data[y * stride + x * 4:y * stride + x * 4 + 3])
        self.assertEqual(px(150, 30), (0, 0, 0))
        self.assertEqual(px(10, 100), (255, 255, 255))
        self.assertNotEqual(bytes(out.get_data()), before)
        self.assertEqual(len(self.canvas.items), 1)
        self.canvas.undo()
        self.assertEqual(self.canvas.items, [])

    def test_leaving_text_mode_clears_selection_but_keeps_words_cache(self):
        self.pointer((10, 10), (240, 45))
        self.canvas.set_tool(None)
        self.assertEqual(self.canvas.selected_text(), "")
        self.assertEqual(len(self.canvas.text_words), 4)

    def test_text_mode_draws_dim_overlay_with_highlighted_words(self):
        res = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 480)
        self.canvas.on_draw(self.canvas, cairo.Context(res)); res.flush()
        data = res.get_data(); stride = res.get_stride()
        ox, oy = self.canvas.origin(); z = self.canvas.zoom
        def px(ix, iy):
            x, y = int(ox + ix * z), int(oy + iy * z)
            return tuple(data[y * stride + x * 4:y * stride + x * 4 + 3])
        inside, outside = px(150, 30), px(10, 100)       # dentro da caixa da linha: branco; fora: imagem esmaecida (#919191)
        self.assertEqual(inside, (255, 255, 255))
        self.assertEqual(outside, (145, 145, 145))


if __name__ == "__main__":
    unittest.main()
