import gc
import unittest
import gi
gi.require_version('Gtk', '3.0')
from gi.repository import Gtk
from captura import icons


class IconThemeTests(unittest.TestCase):
    def test_owned_image_recolors_after_python_wrapper_is_collected(self):
        icons.set_text_color('#1b1b1b')
        box = Gtk.Box()
        im = icons.image('back', 18, '#1b1b1b')
        box.add(im)
        before = bytes(im.get_pixbuf().get_pixels())
        del im
        gc.collect()
        icons.set_text_color('#ffffff')
        after = bytes(box.get_children()[0].get_pixbuf().get_pixels())
        self.assertNotEqual(before, after)
        box.destroy()
