import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from captura.config import settings
from captura.settings_page import SettingsPage


def walk(widget):
    yield widget
    if isinstance(widget, Gtk.Container):
        for child in widget.get_children():
            yield from walk(child)


class SettingsTests(unittest.TestCase):
    def test_autosave_switch_keeps_expander_arrow_in_sync(self):
        old = settings['shot_autosave']
        settings['shot_autosave'] = True
        page = SettingsPage(lambda: None, lambda: None)
        try:
            card = next(c for c in page.col.get_children() if any(
                isinstance(w, Gtk.Label) and w.get_text() == 'Salvar automaticamente as capturas de tela originais'
                for w in walk(c)))
            sw = next(w for w in walk(card) if isinstance(w, Gtk.Switch))
            image = next(w for w in walk(card.get_children()[0]) if isinstance(w, Gtk.Image))
            rev = next(w for w in walk(card) if isinstance(w, Gtk.Revealer))
            before = bytes(image.get_pixbuf().get_pixels())
            sw.set_active(False)
            self.assertFalse(rev.get_reveal_child())
            self.assertNotEqual(before, bytes(image.get_pixbuf().get_pixels()))
        finally:
            page.destroy()
            settings['shot_autosave'] = old
