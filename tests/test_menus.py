"""Regression tests for the measured floating menus (real GTK widgets)."""
import time
import unittest

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, GLib

from captura import menus, theme
from captura.config import settings


def drain(seconds=0.06):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        GLib.MainContext.default().iteration(False)
        time.sleep(0.001)


class MenuTests(unittest.TestCase):
    def setUp(self):
        settings['theme'] = 'light'
        theme.apply()

    def popup(self, callback):
        pop = menus.Menu([(None, 'Executar', None, callback)], menus.MORE)
        self.addCleanup(pop.close_popup)
        return pop

    def test_action_returning_true_is_not_repeated_by_glib(self):
        calls = []
        def action():
            calls.append('called')
            return True  # GTK callbacks may return values; this must NOT repeat.
        pop = self.popup(action)
        # Activate the real Gtk.Button, then run the actual GLib scheduler.
        row = pop.frame.get_children()[0].get_children()[0]
        row.clicked()
        drain()
        self.assertEqual(calls, ['called'])
        self.assertTrue(pop._closed)

    def test_click_on_owner_window_dismisses_popup(self):
        from Xlib import X, display
        from Xlib.ext import xtest
        owner = Gtk.Window()
        owner.set_default_size(240, 160)
        owner.move(50, 50)
        owner.add(Gtk.Label(label='Janela de origem'))
        owner.show_all()
        self.addCleanup(owner.destroy)
        drain(.15)
        pop = self.popup(lambda: None)
        pop.open_at(500, 200)
        drain()
        d = display.Display()
        pointer = d.screen().root.query_pointer()
        self.addCleanup(lambda: (xtest.fake_input(d, X.MotionNotify, x=pointer.root_x, y=pointer.root_y), d.sync(), d.close()))
        _, x, y = owner.get_window().get_origin()
        xtest.fake_input(d, X.MotionNotify, x=x+60, y=y+60)
        xtest.fake_input(d, X.ButtonPress, 1)
        xtest.fake_input(d, X.ButtonRelease, 1)
        d.sync()
        drain(.15)
        self.assertTrue(pop._closed)

    def test_popup_is_clamped_to_its_monitor_workarea(self):
        pop = self.popup(lambda: None)
        pop.open_at(-1000, -1000)
        drain()
        area = menus.Gdk.Display.get_default().get_monitor(0).get_workarea()
        _, x, y = pop.get_window().get_origin()
        self.assertGreaterEqual(x + menus.SHADOW, area.x)
        self.assertGreaterEqual(y + menus.SHADOW, area.y)

    def test_eraser_label_is_fully_inside_frame(self):
        pop = menus.Menu([('trash', 'Apagar todas as marcações', None, lambda: None)], menus.SINGLE)
        self.addCleanup(pop.close_popup)
        pop.open_at(100, 100)
        drain()
        row = pop.frame.get_children()[0].get_children()[0]
        label = next(w for w in row.get_child().get_children() if isinstance(w, Gtk.Label))
        x, _ = label.translate_coordinates(pop.frame, 0, 0)
        self.assertLessEqual(x + label.get_allocated_width(), pop.frame.get_allocated_width() - 10)

    def test_more_text_center_matches_measured_reference(self):
        pop = self.popup(lambda: None)
        pop.open_at(100, 100)
        drain()
        row = pop.frame.get_children()[0].get_children()[0]
        overlay = row.get_child()
        label = next(w for w in overlay.get_children() if isinstance(w, Gtk.Label))
        _, y = label.translate_coordinates(row, 0, 0)
        self.assertAlmostEqual(y + label.get_allocated_height() / 2, row.get_allocated_height() / 2 - 2, delta=0.5)

    def test_popup_surface_follows_dark_theme(self):
        settings['theme'] = 'dark'
        theme.apply()
        pop = self.popup(lambda: None)
        pop.open_at(100, 100)
        drain()
        # The rendered frame is a real style context, not a template-string check.
        import warnings
        with warnings.catch_warnings():
            warnings.simplefilter('ignore', DeprecationWarning)
            rgba = pop.frame.get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
        self.assertLess(rgba.red, 0.25)
        self.assertLess(rgba.green, 0.25)
        self.assertLess(rgba.blue, 0.25)

    def test_grab_retry_budget_is_per_popup(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        # A failed seat grab must allow the next popup its own full retry budget.
        counts = []
        for _ in range(2):
            pop = self.popup(lambda: None)
            pop.realize()
            calls = []
            seat = SimpleNamespace(grab=lambda *a: (calls.append(1), menus.Gdk.GrabStatus.FAILED)[1])
            display = SimpleNamespace(get_default_seat=lambda: seat)
            with patch.object(menus.Gdk.Display, 'get_default', return_value=display), \
                 patch.object(menus.GLib, 'timeout_add', side_effect=lambda _ms, cb: cb()):
                pop._grab()
            counts.append(len(calls))
        self.assertEqual(counts, [16, 16])


if __name__ == '__main__':
    unittest.main()
