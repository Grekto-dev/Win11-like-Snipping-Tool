import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from captura import annot, theme
from captura.config import settings
from captura.flyouts import ToolFlyout


class ToolFlyoutTests(unittest.TestCase):
    def setUp(self):
        settings['theme'] = 'light'
        theme.apply()
        self.anchor_window = Gtk.Window()
        self.anchor = Gtk.Button()
        self.anchor_window.add(self.anchor)
        self.anchor_window.show_all()
        self.addCleanup(self.anchor_window.destroy)

    def make(self, kind='hl', color='#ffe600', size=12, callback=lambda *_: None):
        pop = ToolFlyout(self.anchor, kind, color, size, callback)
        self.addCleanup(pop.destroy)
        return pop

    def test_palette_geometry_matches_reference(self):
        from captura.menus import SHADOW
        for kind, color, size, height in [('pen', '#e61b1b', 4, 456), ('hl', '#ffe600', 12, 288)]:
            with self.subTest(kind=kind):
                pop = self.make(kind, color, size)
                pop.show_all()
                self.assertEqual(pop.get_preferred_width()[1], 322 + 2 * SHADOW)
                self.assertEqual(pop.get_preferred_height()[1], height + 2 * SHADOW)

    def test_real_pointer_selects_color_and_escape_closes(self):
        from Xlib import X, XK, display
        from Xlib.ext import xtest
        import time
        from gi.repository import GLib, Gdk
        calls = []
        pop = self.make(callback=lambda *args: calls.append(args))
        pop.open_at(500, 200)
        def drain():
            end = time.monotonic() + .12
            while time.monotonic() < end:
                GLib.MainContext.default().iteration(False)
                time.sleep(.001)
        drain()
        d = display.Display()
        pointer = d.screen().root.query_pointer()
        self.addCleanup(lambda: (xtest.fake_input(d, X.MotionNotify, x=pointer.root_x, y=pointer.root_y), d.sync(), d.close()))
        button = pop.swatches['#26e600']
        bx, by = button.translate_coordinates(pop, 0, 0)
        _, px, py = pop.get_window().get_origin()
        xtest.fake_input(d, X.MotionNotify, x=px+bx+20, y=py+by+20)
        xtest.fake_input(d, X.ButtonPress, 1)
        xtest.fake_input(d, X.ButtonRelease, 1)
        d.sync()
        drain()
        self.assertEqual(calls, [('#26e600', 12)])
        self.assertFalse(pop._closed)
        key = d.keysym_to_keycode(XK.string_to_keysym('Escape'))
        xtest.fake_input(d, X.KeyPress, key)
        xtest.fake_input(d, X.KeyRelease, key)
        d.sync()
        drain()
        self.assertTrue(pop._closed)

    def test_swatches_are_exclusive_and_notify_once(self):
        calls = []
        pop = self.make(callback=lambda *args: calls.append(args))
        pop.swatches['#26e600'].clicked()
        self.assertEqual(calls, [('#26e600', 12)])
        self.assertEqual([c for c,b in pop.swatches.items() if b.get_active()], ['#26e600'])
        pop.swatches['#26e600'].clicked()
        self.assertTrue(pop.swatches['#26e600'].get_active())
        self.assertEqual(len(calls), 1)

    def test_scale_updates_preview_and_callback(self):
        calls = []
        pop = self.make(callback=lambda *args: calls.append(args))
        pop.scale.set_value(64)
        self.assertEqual(pop.preview.getter(), ('#ffe600', 64))
        self.assertEqual(calls, [('#ffe600', 64)])

    def test_highlighter_range_matches_observed_uia_range(self):
        pop = self.make()
        self.assertEqual(pop.scale.get_adjustment().get_lower(), 12)
        self.assertEqual(pop.scale.get_adjustment().get_upper(), 64)
