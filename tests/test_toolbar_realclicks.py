"""Cliques reais (XTEST) em vários pontos de cada botão: filhos em overlay não podem engolir o clique."""
import os
import time
import unittest

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from gtkapp import shared_app
from captura import theme
from captura.window import EditorWindow

try:
    from Xlib import X, display
    from Xlib.ext import xtest
    D = display.Display()
    HAVE = bool(os.environ.get("DISPLAY")) and D.has_extension("XTEST")
except Exception:                                         # pragma: no cover
    HAVE = False

NAMES = ("btn_new", "b_photo", "b_video", "shape_btn", "delay_btn", "btn_ocr_empty", "btn_more")


def pump(sec):
    end = time.time() + sec
    while time.time() < end:
        while Gtk.events_pending():
            Gtk.main_iteration()
        time.sleep(.01)


@unittest.skipUnless(HAVE, "sem X/XTEST")
class RealClickTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def test_clicking_anywhere_inside_each_button_reaches_the_button(self):
        theme.apply()
        from unittest.mock import patch
        p = patch.object(self.app, "start_capture", create=True)
        p.start()
        self.addCleanup(p.stop)
        w = EditorWindow(self.app)
        self.addCleanup(w.destroy)
        w.show_all()
        w.present()
        pump(1.2)
        hits = {}
        for n in NAMES:
            getattr(w, n).connect("button-press-event", lambda _b, _e, n=n: hits.__setitem__(n, hits.get(n, 0) + 1) or False)
        saved = D.screen().root.query_pointer()
        misses = []
        for n in NAMES:
            b = getattr(w, n)
            al = b.get_allocation()
            wx, wy = b.translate_coordinates(w, 0, 0)
            gx, gy = w.get_window().get_origin()[1:]
            ox, oy = gx + wx, gy + wy
            for fx, fy in ((.15, .5), (.5, .5), (.85, .5), (.5, .2), (.5, .8)):
                before = hits.get(n, 0)
                x, y = int(ox + al.width * fx), int(oy + al.height * fy)
                D.screen().root.warp_pointer(x, y); D.sync(); pump(.08)
                xtest.fake_input(D, X.ButtonPress, 1); D.sync(); pump(.06)
                xtest.fake_input(D, X.ButtonRelease, 1); D.sync(); pump(.12)
                if hits.get(n, 0) == before:
                    misses.append((n, fx, fy))
                m = getattr(w, "_cur_menu", None)
                if m is not None:
                    m.close_popup(); pump(.1)
        D.screen().root.warp_pointer(saved.root_x, saved.root_y); D.sync()
        self.maxDiff = None
        self.assertEqual(misses, [], "pontos do botão que não recebem o clique")


if __name__ == "__main__":
    unittest.main()
