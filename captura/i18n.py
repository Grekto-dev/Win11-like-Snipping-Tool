"""Internacionalização: o texto-fonte do código está em português (pt-BR) e vira o ID da mensagem; cada idioma tem um catálogo
JSON em `data/i18n/<código>.json` (ID em português -> tradução). Inglês é o idioma padrão.

Troca ao vivo: `set_language()` grava a preferência, re-traduz todos os widgets das janelas abertas e manda redesenhar o que é
pintado à mão. Para isso os widgets Gtk de texto são "ganchados" (`install()`): ao criar/atualizar um Label/Button/tooltip/título
com um texto que existe no catálogo, o ID original fica guardado no widget (`_i18n`) e o texto exibido já sai traduzido.
"""
import json
import os

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

SOURCE = "pt-BR"
DEFAULT = "en"
# (código, nome nativo) na ordem do seletor
LANGS = [("pt-BR", "Português (Brasil)"), ("en", "English"), ("zh", "中文（简体）"), ("ja", "日本語"),
         ("es", "Español"), ("fr", "Français"), ("it", "Italiano")]
CODES = [c for c, _ in LANGS]
_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "i18n")
_cache = {}
_lang = None
_listeners = []


def current():
    """Idioma ativo: CAPTURA_LANG (testes/depuração) > configuração salva > inglês."""
    global _lang
    env = os.environ.get("CAPTURA_LANG")
    if env in CODES:
        return env
    if _lang is None:
        from .config import settings
        v = settings["language"]
        _lang = v if v in CODES else DEFAULT
    return _lang


def catalog(lang):
    if lang not in _cache:
        try:
            with open(os.path.join(_DIR, lang + ".json"), encoding="utf-8") as f:
                _cache[lang] = json.load(f)
        except (OSError, ValueError):
            _cache[lang] = {}
    return _cache[lang]


def trf(msg, **kw):
    """Traduz e formata um ID com campos {nome}."""
    return tr(msg).format(**kw)


def tr(msg, lang=None):
    """Traduz `msg` (ID em português). Sem tradução no idioma: tenta inglês e, por fim, devolve o próprio texto."""
    lang = lang or current()
    if lang == SOURCE or not msg:
        return msg
    out = catalog(lang).get(msg)
    if out is None and lang != DEFAULT:
        out = catalog(DEFAULT).get(msg)
    return msg if out is None else out


def known(msg):
    """`msg` é um ID de mensagem (existe no catálogo de inglês, o completo)?"""
    return msg in catalog(DEFAULT)


_reverse = {}


def source_of(text, lang=None):
    """ID em português de um texto já traduzido em `lang` (para widgets que não guardaram a origem)."""
    lang = lang or current()
    if lang == SOURCE:
        return text if known(text) else None
    r = _reverse.get(lang)
    if r is None:
        r = _reverse[lang] = {}
        for k in catalog(DEFAULT):
            r.setdefault(tr(k, lang), k)
    return r.get(text)


# ------------------------------------------------------------------------------------------------ ganchos nos widgets
def _tag(widget, slot, msg):
    d = widget.__dict__.setdefault("_i18n", {})
    if msg is None:
        d.pop(slot, None)
    else:
        d[slot] = msg


def _out(widget, slot, text):
    """Texto a exibir para `text` e registro da origem no widget."""
    if text is None or not isinstance(text, str):
        return text
    src = text if known(text) else None
    _tag(widget, slot, src)
    return tr(text) if src else text


_installed = False


def set_fmt(widget, slot, msg, **kw):
    """Texto dinâmico que precisa acompanhar o idioma (ex.: "Editar no {app}"): guarda ID e valores para re-traduzir."""
    widget.__dict__.setdefault("_i18n_fmt", {})[slot] = (msg, kw)
    return trf(msg, **kw)


def install():
    """Instala os ganchos uma única vez (idempotente)."""
    global _installed
    if _installed:
        return
    _installed = True

    def wrap_setter(cls, name, slot):
        orig = getattr(cls, name)

        def f(self, text, *a, **k):
            return orig(self, _out(self, slot, text), *a, **k)
        f.__name__ = name
        setattr(cls, name, f)

    def wrap_init(cls, kwname, slot):
        orig = cls.__init__

        def init(self, *a, **k):
            src = k.get(kwname)
            if isinstance(src, str):
                k[kwname] = tr(src) if known(src) else src
            orig(self, *a, **k)
            if isinstance(src, str) and known(src):
                _tag(self, slot, src)
        cls.__init__ = init

    # diálogos: botões "texto, resposta, texto, resposta…" e título do seletor de arquivos
    orig_ab = Gtk.Dialog.add_buttons

    def add_buttons(self, *args):
        return orig_ab(self, *[tr(a) if isinstance(a, str) and known(a) else a for a in args])
    Gtk.Dialog.add_buttons = add_buttons
    wrap_init(Gtk.FileChooserDialog, "title", "title")
    wrap_setter(Gtk.FileFilter, "set_name", "name")
    wrap_init(Gtk.Label, "label", "text")
    wrap_setter(Gtk.Label, "set_text", "text")
    wrap_setter(Gtk.Label, "set_label", "text")
    wrap_setter(Gtk.Label, "set_markup", "markup")
    wrap_init(Gtk.Button, "label", "label")
    wrap_setter(Gtk.Button, "set_label", "label")
    wrap_setter(Gtk.Widget, "set_tooltip_text", "tooltip")
    wrap_setter(Gtk.Window, "set_title", "title")
    wrap_setter(Gtk.MessageDialog, "format_secondary_text", "secondary") if hasattr(Gtk.MessageDialog, "format_secondary_text") else None
    wrap_init(Gtk.MessageDialog, "text", "text")


# ------------------------------------------------------------------------------------------------ troca ao vivo
def on_change(fn):
    _listeners.append(fn)


def _walk(w):
    yield w
    if isinstance(w, Gtk.Container):
        for c in w.get_children():
            yield from _walk(c)
    if isinstance(w, Gtk.Bin) and not isinstance(w, Gtk.Container):
        c = w.get_child()
        if c is not None:
            yield from _walk(c)


def retranslate(root, prev=None):
    """Re-traduz `root` e seus descendentes. Os setters ganchados apagam a origem quando recebem um texto já traduzido,
    por isso cada escrita é seguida de um novo registro da origem."""
    n = 0
    for w in _walk(root):
        d = w.__dict__.get("_i18n")
        if isinstance(w, Gtk.Label) and "text" not in (w.__dict__.get("_i18n_fmt") or {}):
            src = d.get("text") if d else None
            if src is None:
                src = source_of_label(w, prev)
            if src is not None and not w.get_use_markup():
                Gtk.Label.set_text(w, tr(src))
                _tag(w, "text", src)
                n += 1
        if isinstance(w, Gtk.Label) and d and d.get("markup"):
            src = d["markup"]
            Gtk.Label.set_markup(w, tr(src))
            _tag(w, "markup", src)
            n += 1
        if isinstance(w, Gtk.Button) and d and d.get("label"):
            src = d["label"]
            Gtk.Button.set_label(w, tr(src))
            _tag(w, "label", src)
            n += 1
        tip = d.get("tooltip") if d else None
        if tip:
            Gtk.Widget.set_tooltip_text(w, tr(tip))
            _tag(w, "tooltip", tip)
            n += 1
        title = d.get("title") if d else None
        if title and isinstance(w, Gtk.Window):
            Gtk.Window.set_title(w, tr(title))
            _tag(w, "title", title)
        fm = w.__dict__.get("_i18n_fmt")
        if fm:
            if "text" in fm and isinstance(w, Gtk.Label):
                Gtk.Label.set_text(w, trf(fm["text"][0], **fm["text"][1]))
            if "tooltip" in fm:
                Gtk.Widget.set_tooltip_text(w, trf(fm["tooltip"][0], **fm["tooltip"][1]))
        if hasattr(w, "i18n_refresh"):
            w.i18n_refresh()
        if isinstance(w, Gtk.DrawingArea):
            w.queue_draw()
    return n


def source_of_label(label, prev=None):
    try:
        text = label.get_text()
    except Exception:
        return None
    return source_of(text, prev) if text else None


def set_language(code):
    """Grava e aplica o idioma na hora em todas as janelas abertas."""
    global _lang
    if code not in CODES:
        return
    from .config import settings
    prev = current()
    settings["language"] = code
    _lang = code
    for fn in list(_listeners):
        fn()
    for win in Gtk.Window.list_toplevels():
        retranslate(win, prev)
