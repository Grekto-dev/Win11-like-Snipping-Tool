import time
import unittest
import uuid

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk, Gio, GLib

from gtkapp import shared_app
from captura import menus, theme
from captura.window import EditorWindow
from captura.config import settings


def drain(seconds=0.12):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(.001)


class MenuWindowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply


    def setUp(self):
        settings['theme'] = 'light'
        theme.apply()
        self.assertTrue(self.app.get_is_registered())
        self.w = EditorWindow(self.app)
        self.addCleanup(self.w.destroy)
        self.addCleanup(lambda: getattr(self.w, '_cur_menu', None) and self.w._cur_menu.close_popup())
        self.w.show()
        drain()

    def test_real_save_dialog_cancel_keeps_window_open(self):
        import tempfile
        import cairo
        with tempfile.TemporaryDirectory(prefix='captura-dialog-test-') as directory:
            before = {k: settings[k] for k in ('shot_dir', 'shot_ask_save_edited')}
            self.addCleanup(lambda: [settings.__setitem__(k, v) for k,v in before.items()])
            settings['shot_dir'] = directory
            settings['shot_ask_save_edited'] = True
            self.w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 10))
            self.w.canvas.dirty = True
            seen = []
            def respond():
                for dialog in Gtk.Window.list_toplevels():
                    if not dialog.get_visible():
                        continue
                    if isinstance(dialog, Gtk.FileChooserDialog) and 'save' not in seen:
                        seen.append('save')
                        dialog.response(Gtk.ResponseType.CANCEL)
                        return False
                    if isinstance(dialog, Gtk.MessageDialog) and 'question' not in seen:
                        seen.append('question')
                        dialog.response(Gtk.ResponseType.YES)
                return True
            source = GLib.timeout_add(40, respond)
            # A watchdog prevents any broken modal from blocking the test runner.
            def watchdog():
                for dialog in Gtk.Window.list_toplevels():
                    if isinstance(dialog, Gtk.Dialog) and dialog.get_visible():
                        dialog.response(Gtk.ResponseType.CANCEL)
                return False
            timeout = GLib.timeout_add(1800, watchdog)
            self.w.close()
            drain(.6)
            if GLib.MainContext.default().find_source_by_id(source):
                GLib.source_remove(source)
            if GLib.MainContext.default().find_source_by_id(timeout):
                GLib.source_remove(timeout)
            self.assertEqual(seen, ['question', 'save'])
            self.assertTrue(self.w.get_visible())
            self.assertTrue(self.w.canvas.dirty)

    def test_new_editor_restores_persisted_tool_styles(self):
        values = dict(pen_color='#004de6', pen_size=20, hl_color='#26e600', hl_size=48,
                      shape_color='#600080', shape_size=9, shape_kind='arrow', shape_fill='#ffce00')
        before = {key: settings[key] for key in values}
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k,v in before.items()])
        for key, value in values.items():
            settings[key] = value
        window = EditorWindow(self.app)
        self.addCleanup(window.destroy)
        self.assertEqual(window.canvas.opts['pen'], ('#004de6', 20))
        self.assertEqual(window.canvas.opts['hl'], ('#26e600', 48))
        self.assertEqual(window.canvas.opts['shape'], ('#600080', 9))
        self.assertEqual(window.canvas.opts['shape_kind'], 'arrow')
        self.assertEqual(window.canvas.opts['shape_fill'], '#ffce00')

    def test_capture_menu_tracks_its_button_in_empty_state(self):
        self.w.popup_shape_menu(self.w.shape_btn)
        drain()
        pop = self.w._cur_menu
        _, px, _ = pop.get_window().get_origin()
        bx, _ = menus.anchor_origin(self.w.shape_btn)
        self.assertEqual(px + menus.SHADOW, bx - 5)

    def test_more_menu_tracks_the_right_edge_after_resize(self):
        self.w.resize(1184, 651)
        drain()
        self.w.popup_more(self.w.btn_more)
        drain()
        pop = self.w._cur_menu
        _, px, _ = pop.get_window().get_origin()
        ox, _ = menus.anchor_origin(self.w.toolbar)
        frame_right = px + menus.SHADOW + pop.frame.get_allocated_width()
        self.assertEqual(frame_right, ox + self.w.toolbar.get_allocated_width())


if __name__ == '__main__':
    unittest.main()
