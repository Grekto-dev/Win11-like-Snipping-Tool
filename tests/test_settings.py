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


def labels(widget):
    return [w.get_text() for w in walk(widget) if isinstance(w, Gtk.Label)]


class SettingsAppearanceTests(unittest.TestCase):
    def setUp(self):
        self.old = settings['theme']
        self.addCleanup(lambda: settings.__setitem__('theme', self.old))
        settings['theme'] = 'system'
        self.changed = []
        self.page = SettingsPage(lambda: None, lambda: self.changed.append(settings['theme']))
        self.addCleanup(self.page.destroy)

    def test_header_scrolls_with_the_content(self):
        sw = next(w for w in walk(self.page) if isinstance(w, Gtk.ScrolledWindow))
        self.assertIn('Configurações', labels(sw))
        self.assertEqual([c for c in self.page.get_children() if not isinstance(c, Gtk.ScrolledWindow)], [])

    def test_theme_is_a_collapsed_card_with_three_radio_rows_in_windows_order(self):
        self.assertTrue(hasattr(self.page, 'theme_radios'))
        self.assertEqual([k for k, _b in self.page.theme_radios], ['light', 'dark', 'system'])
        self.assertEqual([b.get_tooltip_text() for _k, b in self.page.theme_radios],
                         ['Claro', 'Escuro', 'Usar configuração do sistema'])
        self.assertFalse(self.page.theme_revealer.get_reveal_child())
        self.assertEqual([b.get_active() for _k, b in self.page.theme_radios], [False, False, True])

    def test_choosing_a_radio_applies_the_theme_once_and_stays_exclusive(self):
        dark = dict(self.page.theme_radios)['dark']
        dark.clicked()
        self.assertEqual(settings['theme'], 'dark')
        self.assertEqual(self.changed, ['dark'])
        self.assertEqual([b.get_active() for _k, b in self.page.theme_radios], [False, True, False])
        dark.clicked()          # clicar no já marcado não repete nem desmarca
        self.assertEqual(self.changed, ['dark'])
        self.assertTrue(dark.get_active())

    def test_chevron_expands_the_theme_panel(self):
        self.page.theme_chevron.clicked()
        self.assertTrue(self.page.theme_revealer.get_reveal_child())
        self.page.theme_chevron.clicked()
        self.assertFalse(self.page.theme_revealer.get_reveal_child())


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
