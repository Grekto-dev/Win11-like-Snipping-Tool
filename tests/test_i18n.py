"""Idiomas (i18n), "após a captura", cursor de mão nos links e cópia para a área de transferência."""
import gi
gi.require_version("Gtk", "3.0")
import json
import os
import re
import sys
import time
import unittest
from unittest.mock import patch

import cairo
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, GLib, Gtk

from gtkapp import shared_app
from captura import app as capp, cursors, i18n, services, theme
from captura.config import settings
from captura.window import EditorWindow

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
DATA = os.path.join(ROOT, "captura", "data", "i18n")
sys.path.insert(0, os.path.join(ROOT, "scripts"))


def pump(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        GLib.MainContext.default().iteration(False); time.sleep(.003)


def msgids():
    return json.load(open(os.path.join(DATA, "_msgids.json"), encoding="utf-8"))


def fields(s):
    return sorted(re.findall(r"\{[a-z_]+\}", s)), s.count("\n"), sorted(re.findall(r"</?b>", s))


class CatalogTests(unittest.TestCase):
    def test_every_language_translates_every_message_with_the_same_placeholders(self):
        for code, _name in i18n.LANGS:
            if code == i18n.SOURCE:
                continue
            cat = json.load(open(os.path.join(DATA, code + ".json"), encoding="utf-8"))
            self.assertEqual(sorted(cat), sorted(msgids()), code)
            for k, v in cat.items():
                self.assertTrue(v.strip(), (code, k))
                self.assertEqual(fields(v), fields(k), (code, k, v))

    def test_no_untranslated_portuguese_in_other_languages(self):
        """Inglês/espanhol/francês/italiano não podem conter acentos portugueses típicos (ã, õ, ç) — sinal de texto não traduzido."""
        for code in ("en", "es", "fr", "it"):
            cat = json.load(open(os.path.join(DATA, code + ".json"), encoding="utf-8"))
            bad = [(k, v) for k, v in cat.items() if re.search(r"[ãõ]|ção\b|ções\b", v)]
            self.assertEqual(bad, [], code)

    def test_cjk_catalogs_actually_use_cjk_characters(self):
        for code, rx in (("zh", r"[\u4e00-\u9fff]"), ("ja", r"[\u3040-\u30ff\u4e00-\u9fff]")):
            cat = json.load(open(os.path.join(DATA, code + ".json"), encoding="utf-8"))
            plain = [k for k, v in cat.items() if not re.search(rx, v)]
            self.assertLess(len(plain), 12, (code, plain[:12]))       # só nomes/atalhos podem ficar sem caracteres CJK

    def test_code_has_no_new_ui_string_outside_the_catalog(self):
        import extract_i18n
        missing = sorted(set(extract_i18n.candidates()) - set(extract_i18n.FRAGMENTS) - set(msgids()))
        self.assertEqual(missing, [], "textos de interface sem tradução: adicione aos catálogos e a _msgids.json")

    def test_default_language_is_english_and_options_cover_the_seven_languages(self):
        from captura import config
        self.assertEqual(config.DEFAULTS["language"], "en")
        self.assertEqual(config.DEFAULTS["shot_after"], "notify_copy")
        self.assertEqual([c for c, _ in i18n.LANGS], ["pt-BR", "en", "zh", "ja", "es", "fr", "it"])

    def test_tr_falls_back_to_english_then_source(self):
        self.assertEqual(i18n.tr("Cancelar", "pt-BR"), "Cancelar")
        self.assertEqual(i18n.tr("Cancelar", "en"), "Cancel")
        self.assertEqual(i18n.tr("texto que não existe", "ja"), "texto que não existe")
        self.assertEqual(i18n.trf("Salvo em {caminho}", caminho="/x") if i18n.current() == "pt-BR" else "", "Salvo em /x" if i18n.current() == "pt-BR" else "")


class LiveSwitchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def setUp(self):
        theme.apply()
        self.saved = settings["language"]
        saved_env = os.environ.pop("CAPTURA_LANG", None)             # a variável fixa o idioma (testes): aqui o idioma é o da configuração
        self.addCleanup(lambda: os.environ.__setitem__("CAPTURA_LANG", saved_env) if saved_env else None)
        i18n.set_language("pt-BR")
        self.w = EditorWindow(self.app)
        self.w.show_all()
        self.w.load_surface(cairo.ImageSurface(cairo.FORMAT_ARGB32, 300, 200))
        pump(.3)
        self.addCleanup(self.w.destroy)
        self.addCleanup(lambda: i18n.set_language(self.saved))

    def texts(self):
        out = []

        def walk(w):
            if isinstance(w, Gtk.Label):
                out.append(w.get_text())
            tip = w.get_tooltip_text()
            if tip:
                out.append(tip)
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    walk(c)
        walk(self.w)
        return out

    def test_switching_language_retranslates_the_open_window_at_once(self):
        pt = self.texts()
        self.assertIn("Nova captura (Ctrl+N)", pt)
        i18n.set_language("en")
        en = self.texts()
        self.assertIn(i18n.tr("Nova captura (Ctrl+N)", "en"), en)
        self.assertNotIn("Nova captura (Ctrl+N)", en)
        self.assertEqual(settings["language"], "en")
        i18n.set_language("ja")
        self.assertNotEqual(self.texts(), en)
        i18n.set_language("pt-BR")
        self.assertEqual(sorted(self.texts()), sorted(pt))            # voltar ao português restaura tudo

    def test_every_message_shown_in_each_language_has_no_portuguese_leftover(self):
        for code in ("en", "es", "fr", "it", "zh", "ja"):
            i18n.set_language(code)
            pump(.05)
            left = [t for t in self.texts() if t in set(msgids()) and i18n.tr(t, "pt-BR") == t and i18n.tr(t, code) != t]
            self.assertEqual(left, [], code)

    def test_language_dropdown_switches_the_ui_and_persists(self):
        self.w.show_page("settings")
        pump(.4)
        page = self.w.settings_page
        btns = []

        def walk(w):
            if isinstance(w, Gtk.Button) and w.get_style_context().has_class("fluent-btn"):
                btns.append(w)
            if isinstance(w, Gtk.Container):
                for c in w.get_children():
                    walk(c)
        walk(page)
        lang_btn = [b for b in btns if "Português" in " ".join(l.get_text() for l in _labels(b))][0]
        lang_btn.clicked(); pump(.4)
        popups = [t for t in Gtk.Window.list_toplevels() if type(t).__name__ == "Menu"]      # o menu é um Popup próprio
        self.assertTrue(popups, "menu de idiomas não abriu")
        names = [l.get_text() for l in _labels(popups[0])]
        for n in ("Português (Brasil)", "English", "中文（简体）", "日本語", "Español", "Français", "Italiano"):
            self.assertIn(n, names)
        for b in _buttons(popups[0]):
            if any(l.get_text() == "Español" for l in _labels(b)):
                b.clicked()
        pump(.5)
        self.assertEqual(settings["language"], "es")
        self.assertNotIn("Nova captura (Ctrl+N)", self.texts())
        self.assertIn(i18n.tr("Nova captura (Ctrl+N)", "es"), self.texts())


def _labels(w):
    out = []
    if isinstance(w, Gtk.Label):
        out.append(w)
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            out += _labels(c)
    return out


def _buttons(w):
    out = []
    if isinstance(w, Gtk.Button):
        out.append(w)
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            out += _buttons(c)
    return out


class AfterCaptureTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.shared = shared_app()

    def setUp(self):
        self.saved = {k: settings[k] for k in ("shot_after", "quick_markup", "shot_autosave", "shot_border")}
        settings["quick_markup"], settings["shot_autosave"], settings["shot_border"] = False, False, False
        self.addCleanup(lambda: [settings.__setitem__(k, v) for k, v in self.saved.items()])
        self.app = capp.CapturaApp.__new__(capp.CapturaApp)
        self.app.windows, self.app._hidden, self.app._from_app = [], [], False
        self.opened, self.notified, self.copied = [], [], []
        self.app.get_window = lambda new=False: type("W", (), {"load_surface": lambda s, *a, **k: self_opened.append(a)})()
        self_opened = self.opened
        p1 = patch.object(capp.services, "copy_surface", side_effect=lambda s: self.copied.append(s))
        p2 = patch.object(capp.services, "notify", side_effect=lambda *a, **k: self.notified.append(a))
        p3 = patch.object(capp.services, "autosave", return_value=None)
        for p in (p1, p2, p3):
            p.start(); self.addCleanup(p.stop)
        from gi.repository import GdkPixbuf
        self.pb = GdkPixbuf.Pixbuf.new(GdkPixbuf.Colorspace.RGB, True, 8, 40, 30)
        self.pb.fill(0x336699ff)

    def test_clipboard_is_used_by_every_mode_except_notification_only(self):
        for mode, expected in (("notify_copy", 1), ("editor", 1), ("copy", 1), ("notify", 0)):
            settings["shot_after"] = mode
            self.copied.clear()
            self.app.handle_image(self.pb)
            self.assertEqual(len(self.copied), expected, mode)

    def test_notify_and_copy_mode_shows_a_notification_copies_and_does_not_open_the_editor(self):
        settings["shot_after"] = "notify_copy"
        self.app.handle_image(self.pb)
        self.assertEqual(len(self.notified), 1)
        self.assertEqual(len(self.copied), 1)
        self.assertEqual(self.opened, [])
        self.assertIn("Copiado para a área de transferência", self.notified[0][1])

    def test_notify_only_mode_shows_a_notification_without_touching_the_clipboard(self):
        settings["shot_after"] = "notify"
        self.app.handle_image(self.pb)
        self.assertEqual(len(self.notified), 1)
        self.assertEqual((self.copied, self.opened), ([], []))
        self.assertNotIn("Copiado", self.notified[0][1])

    def test_dropdown_lists_the_four_options_with_notify_and_copy_first(self):
        import inspect
        from captura import settings_page
        src = inspect.getsource(settings_page.SettingsPage.__init__)
        order = [src.index('"%s"' % k) for k in ("notify_copy", "notify", "copy", "editor")]
        self.assertEqual(order, sorted(order))

    def test_about_shows_version_1_0_0(self):
        import captura
        self.assertEqual(captura.__version__, "1.0.0")

    def test_editor_mode_opens_the_editor_without_a_notification(self):
        settings["shot_after"] = "editor"
        self.app.handle_image(self.pb)
        self.assertEqual(len(self.opened), 1)
        self.assertEqual(self.notified, [])

    def test_copy_mode_only_copies_no_editor_no_notification(self):
        settings["shot_after"] = "copy"
        self.app.handle_image(self.pb)
        self.assertEqual((self.opened, self.notified), ([], []))
        self.assertEqual(len(self.copied), 1)

    def test_new_button_from_the_window_still_returns_to_the_editor(self):
        settings["shot_after"] = "copy"
        self.app._from_app = True
        self.app.handle_image(self.pb)
        self.assertEqual(len(self.opened), 1)


class RealClipboardTests(unittest.TestCase):
    def test_a_real_copy_is_readable_back_from_the_clipboard(self):
        s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 50, 40)
        cr = cairo.Context(s); cr.set_source_rgb(1, 0, 0); cr.paint()
        services.copy_surface(s)
        pump(.3)
        pb = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_image()
        self.assertIsNotNone(pb)
        self.assertEqual((pb.get_width(), pb.get_height()), (50, 40))


class LinkCursorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = shared_app()
        cls.app.apply_theme = theme.apply

    def test_every_link_button_gets_the_hand_cursor(self):
        theme.apply()
        w = EditorWindow(self.app)
        w.show_all()
        w.show_page("settings")
        pump(.5)
        self.addCleanup(w.destroy)
        links = []

        def walk(x):
            if cursors.is_link(x):
                links.append(x)
            if isinstance(x, Gtk.Container):
                for c in x.get_children():
                    walk(c)
        walk(w)
        links = [b for b in links if b.get_realized()]
        self.assertGreaterEqual(len(links), 5)          # "Alterar" + 4 links de "Sobre" (o aviso inicial está na outra página)
        for b in links:
            self.assertTrue(b.__dict__.get("_hand"), b.get_label() or b)
            self.assertIsNotNone(b.get_window().get_cursor(), b.get_label() or b)

    def test_non_link_buttons_keep_the_default_cursor(self):
        b = Gtk.Button(label="normal")
        self.assertFalse(cursors.is_link(b))


if __name__ == "__main__":
    unittest.main()
