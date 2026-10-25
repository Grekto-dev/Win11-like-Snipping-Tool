import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
import cairo
from gi.repository import Gtk, GLib
from gtkapp import shared_app
from captura import theme, metrics as M, menus
from captura.config import settings
from captura.window import EditorWindow


def drain(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.002)


class CropBarTests(unittest.TestCase):
    def setUp(self):
        settings["theme"] = "light"; theme.apply()
        old = settings["shot_autocopy_edits"]; settings["shot_autocopy_edits"] = False
        self.addCleanup(lambda: settings.__setitem__("shot_autocopy_edits", old))
        self.app = shared_app(); self.app.apply_theme = theme.apply
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        self.w.show(); drain()
        self.w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)); drain()
        self.w.btn_crop.set_active(True); drain(.3)

    def pos(self, widget):
        x, y = widget.translate_coordinates(self.w.toolbar, 0, 0)
        return x, y + M.TB_Y

    def test_crop_toolbar_matches_reference_geometry(self):
        self.assertEqual(self.pos(self.w.crop_apply), (401, 38))
        self.assertEqual((self.w.crop_apply.get_allocated_width(), self.w.crop_apply.get_allocated_height()), (85, 32))
        self.assertEqual(self.pos(self.w.crop_cancel), (486, 38))
        self.assertEqual((self.w.crop_cancel.get_allocated_width(), self.w.crop_cancel.get_allocated_height()), (95, 32))
        self.assertEqual(self.pos(self.w.crop_zoom), (920, 38))
        self.assertEqual((self.w.crop_zoom.get_allocated_width(), self.w.crop_zoom.get_allocated_height()), (56, 32))

    def test_other_groups_are_hidden_and_not_clickable_in_crop_mode(self):
        self.assertFalse(self.w.btn_more.get_visible())
        self.assertFalse(any(b.get_visible() for b in self.w.file_widgets))
        self.assertEqual(self.w._left.get_opacity(), 0)
        self.assertFalse(self.w._left.get_sensitive())
        self.assertTrue(self.w.crop_zoom.get_visible())
        self.w.btn_crop.set_active(False); drain(.3)
        self.assertTrue(self.w.btn_more.get_visible())
        self.assertEqual(self.w._left.get_opacity(), 1)
        self.assertTrue(self.w._left.get_sensitive())
        self.assertFalse(self.w.crop_zoom.get_visible())

    def test_apply_crops_and_cancel_keeps_image(self):
        self.w.canvas.crop_rect = (10, 20, 110, 120)
        self.w.crop_cancel.clicked(); drain(.2)
        self.assertEqual(self.w.canvas.base.get_width(), 400)
        self.assertNotEqual(self.w.canvas.tool, "crop")
        self.w.btn_crop.set_active(True); drain(.2)
        self.w.canvas.crop_rect = (10, 20, 110, 120)
        self.w.crop_apply.clicked(); drain(.2)
        self.assertEqual((self.w.canvas.base.get_width(), self.w.canvas.base.get_height()), (100, 100))

    def test_outside_the_crop_is_dimmed_to_40_percent_and_handles_are_outside_the_image(self):
        c = self.w.canvas
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, 400, 300)
        cr = cairo.Context(surf); cr.set_source_rgb(200 / 255, 100 / 255, 50 / 255); cr.paint()
        c.set_image(surf); c.set_tool("crop"); c.crop_rect = (100, 80, 300, 220)
        c.set_zoom(1.0); drain(.2)
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, c.get_allocated_width(), c.get_allocated_height())
        c.on_draw(c, cairo.Context(out)); out.flush()
        d, st = out.get_data(), out.get_stride()
        ox, oy = c.origin()
        px = lambda x, y: tuple(d[int(y) * st + int(x) * 4: int(y) * st + int(x) * 4 + 3])      # BGR
        inside = px(ox + 200, oy + 150)
        dim = px(ox + 20, oy + 20)
        self.assertEqual(inside, (50, 100, 200))
        self.assertEqual(dim, (20, 40, 80))
        # alça superior esquerda: faixa branca de 4 px começando 3 px antes da aresta, fora da imagem recortada
        self.assertEqual(px(ox + 100 - 3, oy + 80 - 3), (255, 255, 255))
        self.assertEqual(px(ox + 100 - 3 + 23, oy + 80 - 3), (255, 255, 255))
        self.assertNotEqual(px(ox + 100 - 3 + 25, oy + 80 - 3), (255, 255, 255))
        # barra do meio: 24x4, totalmente fora da aresta superior
        mid = ox + 200
        self.assertEqual(px(mid, oy + 80 - 4), (255, 255, 255))
        self.assertNotEqual(px(mid + 14, oy + 80 - 3), (255, 255, 255))

    def test_destroying_the_window_releases_an_open_popup_grab(self):
        self.w.crop_zoom.clicked(); drain(.4)
        self.assertIsNotNone(Gtk.grab_get_current())
        self.w.destroy(); drain(.2)
        self.assertIsNone(Gtk.grab_get_current(), "popup com grab sobreviveu à janela")

    def test_tooltips_name_the_shortcuts(self):
        self.assertEqual(self.w.crop_apply.get_tooltip_text(), "Aplicar (Enter)")
        self.assertEqual(self.w.crop_cancel.get_tooltip_text(), "Cancelar (Esc)")

    def test_zoom_menu_items_and_geometry(self):
        self.w.crop_zoom.clicked(); drain(.4)
        m = self.w._cur_menu
        rows = [b for b in m.frame.get_children()[0].get_children() if isinstance(b, Gtk.Button)]
        labels = [[c for c in b.get_child().get_children() if isinstance(c, Gtk.Label)] for b in rows]
        texts = [[l.get_text() for l in ls] for ls in labels]
        self.assertEqual(texts, [["100%", "Ctrl+0"], ["Aplicar zoom", "Ctrl++"], ["Reduzir", "Ctrl+-"], ["Ajustar à janela", "Ctrl+1"]])
        self.assertEqual([b.get_sensitive() for b in rows], [True, True, False, True])
        fr = m.frame.get_allocation()
        self.assertEqual((fr.width, fr.height), (184, 138))
        bx, by = menus.anchor_origin(self.w.crop_zoom)
        _, px, py = m.get_window().get_origin()
        self.assertEqual(py + menus.SHADOW, by + 44)
        self.assertLessEqual(abs(px + menus.SHADOW + 92 - (bx + 28)), 1)

    def test_zoom_actions_change_canvas_and_enable_zoom_out(self):
        c = self.w.canvas
        self.w.zoom_in(); drain(.1)
        self.assertGreater(c.zoom, 0)
        z_in = c.zoom
        self.assertFalse(c.fit)
        self.assertTrue(self.w.can_zoom_out())
        self.w.zoom_out(); drain(.1)
        self.assertLess(c.zoom, z_in)
        self.w.zoom_fit(); drain(.1)
        self.assertTrue(c.fit)
        self.assertFalse(self.w.can_zoom_out())
        self.w.zoom_actual(); drain(.1)
        self.assertEqual(c.zoom, 1.0)

    def test_more_menu_zoom_submenu_sits_right_of_main_menu_5px_lower(self):
        self.w.btn_crop.set_active(False); drain(.3)
        self.w.popup_more(self.w.btn_more); drain(.4)
        main = self.w._cur_menu
        _, mx, my = main.get_window().get_origin()
        mfr = main.frame.get_allocation()
        rows = [b for b in main.frame.get_children()[0].get_children() if isinstance(b, Gtk.Button)]
        rows[0].clicked(); drain(.6)
        sub = self.w._cur_menu
        self.assertIsNot(sub, main)
        _, sx, sy = sub.get_window().get_origin()
        self.assertEqual(sx + menus.SHADOW, mx + menus.SHADOW + mfr.width - 1)
        self.assertEqual(sy + menus.SHADOW, my + menus.SHADOW + 5)
        sfr = sub.frame.get_allocation()
        self.assertEqual((sfr.width, sfr.height), (184, 138))


if __name__ == "__main__":
    unittest.main()
