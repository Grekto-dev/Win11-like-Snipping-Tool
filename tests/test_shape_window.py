import unittest
from types import SimpleNamespace
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio
import cairo
from captura import annot, theme
from captura.window import EditorWindow


class ShapeWindowTests(unittest.TestCase):
    def test_fill_from_picker_reaches_new_shapes_and_can_be_undone(self):
        app = Gtk.Application(application_id='org.captura.VisualTests', flags=Gio.ApplicationFlags.NON_UNIQUE)
        app.register(None)
        app.apply_theme = theme.apply
        theme.apply()
        w = EditorWindow(app)
        self.addCleanup(w.destroy)
        w.realize()
        w.canvas.set_image(cairo.ImageSurface(cairo.FORMAT_ARGB32, 200, 100))
        w.select_tool('shape')
        w.popup_flyout(w.btn_shape, 'shape')
        self.assertTrue(hasattr(w, '_tool_pop'), 'O seletor deve ficar ligado à janela')
        pop = w._tool_pop
        pop.choose_fill('#004de6')
        self.assertEqual(w.canvas.opts.get('shape_fill'), '#004de6')
        pop.popdown()
        # Simula o arrasto real pelo mesmo caminho de eventos do DrawingArea.
        ox, oy = w.canvas.origin()
        z = w.canvas.zoom
        ev = lambda x, y: SimpleNamespace(x=ox+x*z, y=oy+y*z, button=1, state=0)
        w.canvas.on_press(w.canvas, ev(10, 10))
        w.canvas.on_motion(w.canvas, ev(150, 80))
        w.canvas.on_release(w.canvas, ev(150, 80))
        self.assertEqual(w.canvas.items[-1].fill, '#004de6')
        # Alterar estilo de uma forma selecionada deve ser desfazível.
        w.popup_flyout(w.btn_shape, 'shape')
        w._tool_pop.choose_fill('#26e600')
        self.assertEqual(w.canvas.items[-1].fill, '#26e600')
        w.canvas.undo()
        self.assertEqual(w.canvas.items[-1].fill, '#004de6')
