import unittest
from types import SimpleNamespace
import cairo
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gdk
from captura.canvas import Canvas
from captura.window import EditorWindow


class RulerTests(unittest.TestCase):
    def setUp(self):
        self.canvas = Canvas()
        self.canvas.set_size_request(640, 480)
        self.window = Gtk.OffscreenWindow()
        self.window.add(self.canvas)
        self.window.show_all()
        self.addCleanup(self.window.destroy)
        while Gtk.events_pending(): Gtk.main_iteration_do(False)
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        cr = cairo.Context(surface);cr.set_source_rgb(.2,.4,.8);cr.paint()
        self.canvas.set_image(surface)

    def draw(self):
        result = cairo.ImageSurface(cairo.FORMAT_ARGB32, 640, 480)
        self.canvas.on_draw(self.canvas, cairo.Context(result))
        result.flush()
        return bytes(result.get_data())

    def test_wheel_rotates_ruler_without_zooming_image(self):
        EditorWindow.toggle_ruler(SimpleNamespace(canvas=self.canvas))
        self.draw()
        r = self.canvas.ruler
        zoom = self.canvas.zoom
        event = SimpleNamespace(x=r.x, y=r.y, state=0, direction=Gdk.ScrollDirection.UP)
        self.assertTrue(self.canvas.on_scroll(self.canvas, event))
        self.assertNotEqual(r.angle, 0)
        self.assertEqual(self.canvas.zoom, zoom)

    def test_drag_moves_ruler_without_creating_annotations(self):
        EditorWindow.toggle_ruler(SimpleNamespace(canvas=self.canvas))
        self.draw()
        r = self.canvas.ruler
        x, y = r.x, r.y
        event = lambda px, py: SimpleNamespace(x=px, y=py, button=1, state=0)
        self.canvas.on_press(self.canvas, event(x,y))
        self.canvas.on_motion(self.canvas, event(x+35,y-20))
        self.canvas.on_release(self.canvas, event(x+35,y-20))
        self.assertEqual((r.x,r.y), (x+35,y-20))
        self.assertEqual(self.canvas.items, [])
        self.assertFalse(self.canvas.dirty)

    def test_ruler_changes_view_but_never_exported_pixels(self):
        before = self.draw()
        exported = bytes(self.canvas.rendered().get_data())
        EditorWindow.toggle_ruler(SimpleNamespace(canvas=self.canvas))
        self.assertTrue(self.draw() != before, 'A régua deve alterar pixels da visualização')
        self.assertEqual(bytes(self.canvas.rendered().get_data()), exported)


if __name__ == '__main__': unittest.main()
