"""Janela GTK animada usada como conteúdo "vivo" pelos testes de gravação (não é um teste).

Uso: python animated_window.py X Y W H [segundos]   — mostra a janela em (X, Y) e anima até o fim.
"""
import sys

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import GLib, Gtk


def main(argv):
    x, y, w, h = (int(v) for v in argv[1:5])
    seconds = float(argv[5]) if len(argv) > 5 else 60.0
    win = Gtk.Window(title="captura-animada")
    win.set_default_size(w, h)
    win.move(x, y)
    state = {"t": 0}
    da = Gtk.DrawingArea()

    def draw(_widget, cr):
        t = state["t"]
        cr.set_source_rgb((t % 60) / 60.0, 0.2, 1.0 - (t % 60) / 60.0)
        cr.paint()
        cr.set_source_rgb(1, 1, 1)
        bar_x = (t * 7) % max(1, w - 20)
        cr.rectangle(bar_x, h // 2 - 5, 20, 10)
        cr.fill()
        return True

    def tick():
        state["t"] += 1
        da.queue_draw()
        return True

    da.connect("draw", draw)
    win.add(da)
    win.connect("destroy", Gtk.main_quit)
    win.show_all()
    GLib.timeout_add(50, tick)
    GLib.timeout_add(int(seconds * 1000), Gtk.main_quit)
    Gtk.main()


if __name__ == "__main__":
    main(sys.argv)
