import gi
gi.require_version("Gtk", "3.0")
import time
import unittest
import cairo
from gi.repository import Gtk, GLib
from gtkapp import shared_app
from captura import theme, metrics as M
from captura.config import settings
from captura.window import EditorWindow


def drain(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.002)


def swatch_index(color):
    from captura.shape_bar import SWATCHES
    return SWATCHES.index(color)


class ShapeBarWindowTests(unittest.TestCase):
    def setUp(self):
        settings["theme"] = "light"; theme.apply()
        saved = {k: settings[k] for k in ("shot_autocopy_edits", "shape_kind", "shape_color", "shape_size", "shape_fill",
                                          "shape_alpha", "shape_fill_alpha", "infobar_dismissed")}
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k, v in saved.items()])
        settings["shot_autocopy_edits"] = False
        settings["shape_kind"], settings["shape_color"], settings["shape_size"] = "rect", "#e61b1b", 3
        settings["shape_fill"], settings["shape_alpha"], settings["shape_fill_alpha"] = None, 1.0, 1.0
        self.app = shared_app(); self.app.apply_theme = theme.apply
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        self.w.show(); drain()
        self.w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200))
        self.w.select_tool("shape"); drain()

    def rel(self, widget):
        """Posição do widget relativa à caixa externa da barra de Formas."""
        return widget.translate_coordinates(self.w.shape_bar, 0, 0)

    def test_bar_is_inside_content_centered_and_only_for_the_shapes_tool(self):
        bar = self.w.shape_bar
        self.assertTrue(bar.get_visible())
        a = bar.get_allocation()
        self.assertEqual((a.width, a.height), (486, 48))
        total = self.w.toast_overlay.get_allocated_width()
        x, y = bar.translate_coordinates(self.w.toast_overlay, 0, 0)
        self.assertLessEqual(abs(x - (total - 486) // 2), 1)
        self.assertEqual(y, M.SHAPEBAR_TOP)
        self.w.select_tool("pen"); drain()
        self.assertFalse(bar.get_visible())
        self.w.select_tool("shape"); drain()
        self.assertTrue(bar.get_visible())

    def test_positions_match_measured_reference(self):
        bar = self.w.shape_bar
        self.assertEqual(self.rel(bar.emoji_btn), (6, 6))
        self.assertEqual([self.rel(bar.kind_btns[k])[0] for k in ("rect", "ellipse", "line", "arrow")], [55, 95, 135, 175])
        self.assertEqual(self.rel(bar.fill_btn), (224, 6))
        self.assertEqual(self.rel(bar.outline_btn), (354, 6))
        for b in [bar.emoji_btn] + list(bar.kind_btns.values()):
            self.assertEqual((b.get_allocated_width(), b.get_allocated_height()), (36, 36))

    def test_exactly_one_geometry_is_active_and_it_becomes_the_tool_option(self):
        bar = self.w.shape_bar
        bar.kind_btns["ellipse"].set_active(True); drain()
        self.assertEqual([k for k, b in bar.kind_btns.items() if b.get_active()], ["ellipse"])
        self.assertEqual(self.w.canvas.opts["shape_kind"], "ellipse")
        self.assertEqual(settings["shape_kind"], "ellipse")
        bar.kind_btns["ellipse"].set_active(False); drain()
        self.assertTrue(bar.kind_btns["ellipse"].get_active(), "um dos quatro deve permanecer ativo")

    def test_fill_flyout_changes_new_shapes_and_selected_shape_with_one_undo_step(self):
        from types import SimpleNamespace
        self.w.shape_bar.fill_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        self.assertEqual(fl.mode, "fill")
        fl.swatches[swatch_index("#004de6")].set_active(True); drain()
        self.assertEqual(self.w.canvas.opts["shape_fill"], "#004de6")
        c = self.w.canvas; ox, oy = c.origin(); z = c.zoom
        ev = lambda x, y: SimpleNamespace(x=ox + x * z, y=oy + y * z, button=1, state=0)
        c.on_press(c, ev(10, 10)); c.on_motion(c, ev(150, 80)); c.on_release(c, ev(150, 80))
        shape = c.items[-1]
        self.assertEqual(shape.fill, "#004de6")
        fl.close_popup()
        self.w.shape_bar.fill_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        before = len(c.undo_stack)
        fl.swatches[swatch_index("#26e600")].set_active(True); drain()
        fl.opacity._set(.5); drain()
        self.assertEqual((shape.fill, shape.fill_alpha), ("#26e600", .5))
        self.assertEqual(len(c.undo_stack), before + 1, "mexer cor e opacidade no mesmo flyout é um único passo")
        c.undo()
        self.assertEqual((c.items[-1].fill, c.items[-1].fill_alpha), ("#004de6", 1.0))

    def test_outline_flyout_sets_none_alpha_and_size(self):
        self.w.shape_bar.outline_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        self.assertEqual(fl.mode, "outline")
        self.assertIsNotNone(fl.scale)
        fl.scale.set_value(9); drain()
        self.assertEqual(self.w.canvas.opts["shape"], ("#e61b1b", 9))
        fl.opacity._set(.4); drain()
        self.assertEqual(self.w.canvas.opts["shape_alpha"], .4)
        fl.swatches[0].set_active(True); drain()
        self.assertIsNone(self.w.canvas.opts["shape"][0])
        self.assertFalse(fl.opacity.enabled)
        self.assertIsNone(settings["shape_color"])

    def test_controls_follow_windows_ranges_size_1_to_24_opacity_1_to_100_percent(self):
        self.w.shape_bar.outline_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        adj = fl.scale.get_adjustment()
        self.assertEqual((adj.get_lower(), adj.get_upper()), (1, 24))
        fl.opacity._set(0.0); drain()
        self.assertEqual(fl.opacity.value, 0.01, "opacidade mínima é 1 %")
        self.assertEqual(self.w.canvas.opts["shape_alpha"], 0.01)
        sl = fl.opacity.get_allocation()
        self.assertEqual(sl.width, 277)
        from captura.config import DEFAULTS
        self.assertEqual(DEFAULTS["shape_size"], 4, "tamanho padrão do Windows")

    def test_flyout_geometry_matches_reference(self):
        self.w.shape_bar.fill_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        self.assertEqual(len(fl.swatches), 30)
        self.assertIsNone(fl.swatches[0].color)
        self.assertEqual(fl.swatches[1].color, "#000000")
        self.assertEqual(fl.swatches[5].color, "#808285")
        fr = fl.frame.get_allocation()
        self.assertEqual((fr.width, fr.height), (314, 374))      # interior 312x372 + borda
        center = lambda s: (s.get_allocation().x + s.get_allocation().width / 2, s.get_allocation().y + s.get_allocation().height / 2)
        c0, c1, c6 = center(fl.swatches[0]), center(fl.swatches[1]), center(fl.swatches[6])
        self.assertEqual((c1[0] - c0[0], c6[1] - c0[1]), (48, 48))
        fl.close_popup()
        self.w.shape_bar.outline_btn.clicked(); drain(.4)
        fr = self.w._tool_pop.frame.get_allocation()
        self.assertEqual((fr.width, fr.height), (314, 497))

    def test_flyout_is_centered_under_its_button_and_top_is_44px_below_bar_top(self):
        import captura.menus as menus
        self.w.shape_bar.outline_btn.clicked(); drain(.4)
        fl = self.w._tool_pop
        _, px, py = fl.get_window().get_origin()
        bx, by = menus.anchor_origin(self.w.shape_bar.outline_btn)
        self.assertEqual(py + menus.SHADOW, by - 6 + 44)
        self.assertLessEqual(abs(px + menus.SHADOW + 157 - (bx + 63 + 1.5)), 1)

    def test_emoji_picker_geometry_and_insertion(self):
        import captura.menus as menus
        self.w.shape_bar.emoji_btn.clicked(); drain(.4)
        p = self.w._emoji_picker
        fr = p.frame.get_allocation()
        self.assertEqual((fr.width, fr.height), (242, 122))
        ex, ey = menus.anchor_origin(self.w.shape_bar.emoji_btn)
        _, px, py = p.get_window().get_origin()
        self.assertEqual(py + menus.SHADOW, ey - 6 + 52)
        self.assertLessEqual(abs(px + menus.SHADOW + 121 - (ex + 18)), 1)
        xs = sorted({b.get_allocation().x for b in p.buttons}); ys = sorted({b.get_allocation().y for b in p.buttons})
        self.assertEqual((len(xs), len(ys), xs[1] - xs[0], ys[1] - ys[0]), (6, 3, 40, 40))
        p.buttons[1].clicked(); drain(.4)
        self.assertEqual([i.char for i in self.w.canvas.items], ["⭐"])

    def test_emoji_does_not_take_shape_style_changes(self):
        e = self.w.canvas.add_emoji("🔥")
        self.w.apply_shape_style(color="#000000")
        self.assertIs(self.w.canvas.sel, e)
        self.assertFalse(hasattr(e, "color"))

    def test_selecting_a_drawn_shape_reflects_its_style_in_the_bar(self):
        from captura import annot
        s = annot.Shape("arrow", 10, 10, 90, 90, "#004de6", 5)
        self.w.canvas.items.append(s); self.w.canvas.sel = s
        self.w.canvas.emit("changed"); drain()
        self.assertTrue(self.w.shape_bar.kind_btns["arrow"].get_active())
        self.assertEqual(self.w.shape_bar.outline, "#004de6")


if __name__ == "__main__":
    unittest.main()
