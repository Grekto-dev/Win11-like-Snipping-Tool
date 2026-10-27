"""One registered Gtk.Application per test process (several registrations in one process abort)."""
import atexit
import os
os.environ.setdefault("CAPTURA_NO_ANIM", "1")
os.environ.setdefault("CAPTURA_LANG", "pt-BR")      # os testes comparam textos em português; o padrão do app é inglês
import uuid
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gio, GLib, Gtk

_app = None


def shared_app():
    global _app
    if _app is None:
        _app = Gtk.Application(application_id="org.captura.Tests.t" + uuid.uuid4().hex,
                               flags=Gio.ApplicationFlags.NON_UNIQUE)
        _app.register(None)
        _app.connect("activate", lambda _a: None)
        atexit.register(_close)
    return _app


def _close():
    # register() must be paired with run()/quit() to unexport D-Bus cleanly.
    GLib.idle_add(lambda: (_app.quit(), False)[1])
    _app.run([])
