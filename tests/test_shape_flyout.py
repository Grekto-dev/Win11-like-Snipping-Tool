"""Executar com DISPLAY disponível e XDG_CONFIG_HOME temporário."""
import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from captura import flyouts


class ShapeFlyoutTests(unittest.TestCase):
    def test_compact_shape_picker_has_separate_fill_and_outline(self):
        self.assertTrue(hasattr(flyouts, 'ShapeFlyout'), 'Falta o seletor compacto de Formas')
        win = Gtk.Window()
        anchor = Gtk.Button(label='Formas')
        win.add(anchor)
        events = []
        pop = flyouts.ShapeFlyout(anchor, '#e61b1b', 3, 'rect', None,
                                  lambda *v: events.append(v))
        self.assertEqual(set(pop.shape_btns), {'rect', 'ellipse', 'line', 'arrow'})
        self.assertEqual(pop.fill_btn.get_label(), 'Preencher')
        self.assertEqual(pop.outline_btn.get_label(), 'Contorno')
        self.assertLess(pop.get_child().get_preferred_height().natural_height, 90)
        pop.shape_btns['arrow'].set_active(True)
        self.assertEqual(events[-1], ('#e61b1b', 3, 'arrow', None))
        self.assertFalse(pop.fill_btn.get_sensitive(), 'Linha e seta não têm preenchimento')
        pop.destroy()
        win.destroy()
