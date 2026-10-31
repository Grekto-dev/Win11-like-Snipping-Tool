"""Opções "Após a captura": migração das configurações, salvar/copiar de verdade, gravações e menu com dicas."""
import json
import os
import pathlib
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from gtkapp import shared_app
from captura import config, menus, services
from captura.app import CapturaApp
from captura.config import settings

HAVE_X = bool(os.environ.get("DISPLAY"))
NEED_X = unittest.skipUnless(HAVE_X, "precisa de DISPLAY")


def drain(seconds=.1):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False)
        time.sleep(.003)


class ConfigMigrationTests(unittest.TestCase):
    def load(self, saved):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "settings.json")
            pathlib.Path(path).write_text(json.dumps(saved))
            with patch.object(config, "CONFIG_FILE", path):
                return config.Settings()["shot_after"]

    def test_old_notify_and_copy_choice_becomes_the_new_notify_choice(self):
        self.assertEqual(self.load({"shot_after": "notify_copy"}), "notify")

    def test_valid_choices_are_kept(self):
        for mode in ("notify", "editor", "copy", "save"):
            self.assertEqual(self.load({"shot_after": mode}), mode)

    def test_unknown_or_damaged_values_fall_back_to_the_default(self):
        for value in ("outro", None, 3, ["save"]):
            self.assertEqual(self.load({"shot_after": value}), "notify", value)

    def test_a_new_install_starts_on_notify(self):
        self.assertEqual(self.load({}), "notify")


class AutosaveTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = shared_app()

    def setUp(self):
        self.dir = tempfile.mkdtemp(prefix="captura-after-")
        self.addCleanup(shutil.rmtree, self.dir, True)
        for key, value in (("shot_dir", self.dir), ("shot_autosave", False)):
            old = settings[key]
            settings[key] = value
            self.addCleanup(settings.__setitem__, key, old)
        import cairo
        self.surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, 20, 10)

    def test_respects_the_automatic_saving_switch_by_default(self):
        self.assertIsNone(services.autosave(self.surface))
        self.assertEqual(os.listdir(self.dir), [])

    def test_force_saves_even_when_the_switch_is_off(self):
        path = services.autosave(self.surface, force=True)
        self.assertEqual(os.path.dirname(path), self.dir)
        self.assertTrue(os.path.getsize(path) > 0)

    def test_an_unwritable_folder_is_reported_as_none(self):
        blocker = os.path.join(self.dir, "arquivo")
        pathlib.Path(blocker).write_text("x")
        settings["shot_dir"] = os.path.join(blocker, "pasta")
        self.assertIsNone(services.autosave(self.surface, force=True))


@NEED_X
class ClipboardFileTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = shared_app()

    def test_a_file_is_offered_in_the_formats_file_managers_and_chat_apps_read(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4", prefix="Gravação ", delete=False) as f:
            f.write(b"video")
        self.addCleanup(os.unlink, f.name)
        services.copy_file(f.name)
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        uri = GLib.filename_to_uri(f.name)
        gnome = cb.wait_for_contents(Gdk.Atom.intern("x-special/gnome-copied-files", False))
        self.assertEqual(bytes(gnome.get_data()).decode(), "copy\n" + uri)
        plain = cb.wait_for_contents(Gdk.Atom.intern("text/uri-list", False))
        self.assertEqual(bytes(plain.get_data()).decode().strip(), uri)


@NEED_X
class ClipboardTableTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = shared_app()

    def test_copy_as_table_really_reaches_the_clipboard_in_html_and_plain_text(self):
        services.copy_html_table("<table><tr><td>a</td><td>b</td></tr></table>", "a\tb")
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        html = cb.wait_for_contents(Gdk.Atom.intern("text/html", False))
        self.assertEqual(bytes(html.get_data()).decode(), "<table><tr><td>a</td><td>b</td></tr></table>")
        self.assertEqual(cb.wait_for_text(), "a\tb")

    def test_a_later_image_copy_replaces_the_offered_file(self):
        import cairo
        services.copy_file(__file__)
        services.copy_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 4, 4))
        cb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.assertIsNone(cb.wait_for_contents(Gdk.Atom.intern("x-special/gnome-copied-files", False)))
        self.assertIsNotNone(cb.wait_for_image())


class RecordingAfterTests(unittest.TestCase):
    """O que acontece quando a gravação termina e já está salva (Fake do gravador escreve o arquivo)."""

    def setUp(self):
        self.app = CapturaApp()
        self.app._release = lambda delay_ms=0: None
        self.app.msg = Mock()
        self.temp = tempfile.mkdtemp(prefix="captura-after-rec-")
        self.addCleanup(shutil.rmtree, self.temp, True)
        for key, value in (("rec_dir", self.temp), ("rec_autosave", True), ("rec_mic", False), ("rec_system_audio", False)):
            old = settings[key]
            settings[key] = value
            self.addCleanup(settings.__setitem__, key, old)
        old = settings["shot_after"]
        self.addCleanup(settings.__setitem__, "shot_after", old)
        self.notified, self.copied, self.opened = [], [], []
        created = {}

        def make(rect, mic, system, dest):
            created["dest"] = dest
            r = Mock()
            r.alive.return_value = True
            r.stop.side_effect = lambda: pathlib.Path(dest).write_bytes(b"video")
            return r
        self.created = created
        for p in (patch("captura.app.services.ffmpeg_path", return_value="/usr/bin/ffmpeg"),
                  patch("captura.app.services.Recorder", side_effect=make),
                  patch("captura.app.OutlineWindow"), patch("captura.app.RecordingBar"),
                  patch("captura.app.services.notify", side_effect=lambda *a, **k: self.notified.append(a)),
                  patch("captura.app.services.copy_file", side_effect=lambda path: self.copied.append(path)),
                  patch("captura.app.subprocess.Popen", side_effect=lambda cmd, *a, **k: self.opened.append(cmd))):
            p.start()
            self.addCleanup(p.stop)

    def record(self, mode):
        settings["shot_after"] = mode
        self.app.start_recording((0, 0, 100, 100))
        self.app.stop_recording()
        self.app.wait_stop()
        return self.created["dest"]

    def test_notify_copies_the_saved_file_and_shows_one_notification_that_opens_it(self):
        dest = self.record("notify")
        self.assertEqual((self.copied, self.opened), ([dest], []))
        self.assertEqual(len(self.notified), 1)
        (_id, _label, open_it), = self.notified[0][3]
        open_it()
        self.assertEqual(self.opened, [["xdg-open", dest]])

    def test_a_failed_clipboard_copy_does_not_hide_the_notification(self):
        with patch("captura.app.services.copy_file", side_effect=OSError("sem área de transferência")):
            self.record("notify")
        self.assertEqual(len(self.notified), 1)

    def test_editor_opens_the_saved_video_without_notification_or_clipboard(self):
        dest = self.record("editor")
        self.assertEqual((self.notified, self.copied, self.opened), ([], [], [["xdg-open", dest]]))

    def test_copy_only_copies_the_saved_file(self):
        dest = self.record("copy")
        self.assertEqual((self.notified, self.copied, self.opened), ([], [dest], []))

    def test_save_only_leaves_the_saved_file_silently(self):
        dest = self.record("save")
        self.assertTrue(os.path.exists(dest))
        self.assertEqual((self.notified, self.copied, self.opened), ([], [], []))

    def test_a_discarded_recording_does_nothing_in_any_mode(self):
        self.app.ask_save_recording = lambda tmp: None
        settings["rec_autosave"] = False
        self.record("notify")
        self.assertEqual((self.notified, self.copied, self.opened), ([], [], []))


@NEED_X
class AfterCaptureMenuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = shared_app()

    def setUp(self):
        from captura.settings_page import SettingsPage
        self.old = settings["shot_after"]
        self.addCleanup(settings.__setitem__, "shot_after", self.old)
        self.window = Gtk.Window()
        self.window.set_default_size(900, 700)
        self.page = SettingsPage(lambda: None, lambda: None)
        self.window.add(self.page)
        self.window.show_all()
        self.addCleanup(self.window.destroy)
        drain(.3)

    def open_menu(self):
        self.page.after_capture_button.clicked()
        drain(.2)
        menu = self.page.after_capture_button.menu
        self.addCleanup(menu.close_popup)
        rows = [b for b in self.walk(menu) if isinstance(b, Gtk.Button)]
        return menu, rows

    @classmethod
    def walk(cls, widget):
        yield widget
        if isinstance(widget, Gtk.Container):
            for child in widget.get_children():
                yield from cls.walk(child)

    @staticmethod
    def text(row):
        return [w.get_text() for w in AfterCaptureMenuTests.walk(row) if isinstance(w, Gtk.Label)]

    def test_entries_are_short_and_each_one_has_a_short_tip(self):
        _menu, rows = self.open_menu()
        labels = [self.text(r)[0] for r in rows]
        self.assertEqual(labels, ["Mostrar notificação", "Abrir editor", "Apenas copiar", "Apenas salvar"])
        for label in labels:
            self.assertLessEqual(len(label.split()), 3, label)
        tips = [r.get_tooltip_text() for r in rows]
        self.assertTrue(all(tips), tips)
        self.assertEqual(len(set(tips)), 4)
        for tip in tips:
            self.assertLessEqual(len(tip), 75, tip)
            self.assertNotIn(tip, labels)

    def test_picking_each_entry_saves_the_choice(self):
        for index, mode in enumerate(("notify", "editor", "copy", "save")):
            _menu, rows = self.open_menu()
            rows[index].clicked()
            drain(.15)
            self.assertEqual(settings["shot_after"], mode)

    def test_the_current_entry_is_marked(self):
        settings["shot_after"] = "copy"
        _menu, rows = self.open_menu()
        marks = [any(isinstance(w, Gtk.Image) for w in self.walk(r)) for r in rows]
        self.assertEqual(marks, [False, False, True, False])

    def test_a_real_hover_shows_the_tip_of_that_entry(self):
        from Xlib import X, display
        from Xlib.ext import xtest
        _menu, rows = self.open_menu()
        row = rows[2]
        d = display.Display()
        pointer = d.screen().root.query_pointer()
        self.addCleanup(lambda: (xtest.fake_input(d, X.MotionNotify, x=pointer.root_x, y=pointer.root_y), d.sync(), d.close()))
        ox, oy = menus.anchor_origin(row)
        alloc = row.get_allocation()
        for step in range(8):                 # movimento real, em passos, como um usuário
            xtest.fake_input(d, X.MotionNotify, x=int(ox + 30 + step * 3), y=int(oy + alloc.height / 2))
            d.sync()
            drain(.05)
        expected = row.get_tooltip_text()
        end = time.monotonic() + 3
        shown = []
        while time.monotonic() < end and not shown:
            drain(.1)
            shown = [w for w in Gtk.Window.list_toplevels() if w.get_name() in ("gtk-tooltip", "GtkTooltipWindow") and w.get_visible()
                     and expected in [l.get_text() for l in self.walk(w) if isinstance(l, Gtk.Label)]]
        self.assertTrue(shown, "a dica não apareceu ao passar o ponteiro")


if __name__ == "__main__":
    unittest.main()
