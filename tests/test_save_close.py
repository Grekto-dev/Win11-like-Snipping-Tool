"""Save/close regression tests; only the modal chooser boundary is replaced."""
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import cairo
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from captura.window import EditorWindow
from captura.config import settings


class Chooser:
    def __init__(self, response, path):
        self.response, self.path = response, str(path)
        self.destroyed = False
    def add_buttons(self, *args): pass
    def set_do_overwrite_confirmation(self, *args): pass
    def set_current_folder(self, *args): pass
    def set_current_name(self, *args): pass
    def add_filter(self, *args): pass
    def run(self): return self.response
    def get_filename(self): return self.path
    def destroy(self): self.destroyed = True


class SaveCloseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='captura-save-tests-')
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name)/'image.png'
        previous = settings['shot_dir']
        settings['shot_dir'] = self.tmp.name
        self.addCleanup(lambda: settings.__setitem__('shot_dir', previous))
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 8, 6)
        self.errors = []
        self.w = SimpleNamespace(current_surface=lambda: self.surface,
            canvas=SimpleNamespace(base=self.surface, dirty=True), saved_path=None,
            app=SimpleNamespace(toast_in_window=lambda *a: None),
            error_dialog=lambda *a: self.errors.append(a))

    def test_cancelled_save_reports_failure_and_keeps_dirty_image(self):
        chooser = Chooser(Gtk.ResponseType.CANCEL, self.path)
        with patch('captura.window.Gtk.FileChooserDialog', return_value=chooser):
            saved = EditorWindow.save_as(self.w)
        self.assertIs(saved, False)
        self.assertTrue(self.w.canvas.dirty)
        self.assertFalse(self.path.exists())
        self.assertTrue(chooser.destroyed)

    def test_successful_save_writes_real_image_and_reports_success(self):
        from PIL import Image
        chooser = Chooser(Gtk.ResponseType.OK, self.path)
        with patch('captura.window.Gtk.FileChooserDialog', return_value=chooser):
            saved = EditorWindow.save_as(self.w)
        self.assertIs(saved, True)
        self.assertFalse(self.w.canvas.dirty)
        self.assertEqual(self.w.saved_path, str(self.path))
        with Image.open(self.path) as image:
            self.assertEqual(image.size, (8, 6))
            self.assertEqual(image.format, 'PNG')
        self.assertTrue(chooser.destroyed)

    def test_write_error_keeps_dirty_image_and_prevents_closing(self):
        chooser = Chooser(Gtk.ResponseType.OK, self.path)
        with patch('captura.window.Gtk.FileChooserDialog', return_value=chooser), \
             patch('captura.window.services.save_surface', side_effect=OSError('read-only filesystem')):
            saved = EditorWindow.save_as(self.w)
        self.assertIs(saved, False)
        self.assertTrue(self.w.canvas.dirty)
        self.assertEqual(len(self.errors), 1)
        self.assertTrue(chooser.destroyed)

    def test_directory_error_is_reported_and_dialog_is_destroyed(self):
        chooser = Chooser(Gtk.ResponseType.OK, self.path)
        with patch('captura.window.Gtk.FileChooserDialog', return_value=chooser), \
             patch('captura.window.os.makedirs', side_effect=PermissionError('directory denied')):
            saved = EditorWindow.save_as(self.w)
        self.assertIs(saved, False)
        self.assertTrue(self.w.canvas.dirty)
        self.assertTrue(chooser.destroyed)
        self.assertEqual(len(self.errors), 1)

    def test_close_is_cancelled_when_save_as_is_cancelled(self):
        previous = settings['shot_ask_save_edited']
        settings['shot_ask_save_edited'] = True
        self.addCleanup(lambda: settings.__setitem__('shot_ask_save_edited', previous))
        self.w.save_as = lambda: False
        with patch('captura.window.Gtk.MessageDialog') as dialog:
            dialog.return_value.run.return_value = Gtk.ResponseType.YES
            prevent_close = EditorWindow.on_delete(self.w, None, None)
        self.assertIs(prevent_close, True)
        self.assertTrue(self.w.canvas.dirty)


if __name__ == '__main__': unittest.main()
