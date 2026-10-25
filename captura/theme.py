"""Tema Fluent (claro/escuro) aplicado por CSS do GTK3, independente do tema do Mint."""
import string
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

from .config import settings

LIGHT = dict(
    dark=False, bg0="#f3f3f3", surface="#fbfbfb", canvas="#fcfcfc", text="#1b1b1b", subtle="#5f5f5f", disabled="#a0a0a0",
    border="#e0e0e0", border2="#d1d1d1", hover="rgba(0,0,0,0.055)", press="rgba(0,0,0,0.085)", card="#fdfdfd",
    accent="#0067c0", accent_hover="#1975c5", accent_text="#ffffff", infobar="#ffffff", flyout="#fcfcfc",
    shadow="rgba(0,0,0,0.28)", crop_bg="#666666", toast_bg="#ffffff", link="#003e92", segbg="#ececec",
)
DARK = dict(
    dark=True, bg0="#202020", surface="#2b2b2b", canvas="#1c1c1c", text="#ffffff", subtle="#c8c8c8", disabled="#6f6f6f",
    border="#333333", border2="#454545", hover="rgba(255,255,255,0.07)", press="rgba(255,255,255,0.05)", card="#2b2b2b",
    accent="#60cdff", accent_hover="#7ad6ff", accent_text="#000000", infobar="#2b2b2b", flyout="#2c2c2c",
    shadow="rgba(0,0,0,0.6)", crop_bg="#1a1a1a", toast_bg="#2b2b2b", link="#99ebff", segbg="#2d2d2d",
)

CSS = string.Template(r"""
.cap-window, .cap-window decoration { background: $bg0; color: $text; }
.cap-window headerbar, headerbar.cap-header {
    background: $bg0; color: $text; border: none; box-shadow: none; min-height: 46px; padding: 0 6px;
    border-bottom: 1px solid $border;
}
headerbar.cap-header .title { color: $subtle; font-size: 9pt; }
headerbar.cap-header button.titlebutton { color: $text; background: transparent; border: none; box-shadow: none; min-width: 34px; min-height: 30px; border-radius: 4px; }
headerbar.cap-header button.titlebutton:hover { background: $hover; }
headerbar.cap-header button.titlebutton.close:hover { background: #c42b1c; color: #fff; }
.cap-window label { color: $text; }
.cap-window label.subtle { color: $subtle; font-size: 9pt; }
.cap-window label.section { font-weight: 600; font-size: 11pt; margin-top: 8px; }
.cap-window label.pagetitle { font-size: 20pt; font-weight: 600; }
.cap-canvas-bg { background: $canvas; }
.cap-canvas-bg.cropping { background: $crop_bg; }

button.tbtn, button.tbtn:backdrop {
    background: transparent; color: $text; border: 1px solid transparent; box-shadow: none; text-shadow: none;
    border-radius: 4px; padding: 0 8px; min-height: 32px; min-width: 32px; -gtk-icon-shadow: none; outline: none;
}
button.tbtn:hover { background: $hover; }
button.tbtn:active, button.tbtn:checked { background: $press; }
button.tbtn:checked { border-color: $accent; }
button.tbtn:disabled { opacity: .4; }
button.tbtn.newbtn { background: $surface; border: 1px solid $border2; padding: 0 12px; }
button.tbtn.newbtn:hover { background: $hover; }
button.tbtn.accentbtn { background: $accent; color: $accent_text; border: none; padding: 0 16px; }
button.tbtn.accentbtn:hover { background: $accent_hover; }
button.tbtn.accentbtn label { color: $accent_text; }
button.tbtn.menuitem { min-width: 0; padding: 0 12px; border-radius: 4px; }
button.tbtn.menuitem label { color: $text; }

.seg { background: $segbg; border: 1px solid $border; border-radius: 6px; padding: 1px; }
.seg button.tbtn { min-width: 36px; min-height: 28px; border-radius: 5px; padding: 0 4px; }
.seg button.tbtn:checked { background: $card; border: 1px solid $border2; }
.seg button.tbtn:checked.indicator { }
.sep { background: $border2; min-width: 1px; margin: 9px 6px; }

.cap-infobar { background: $infobar; border: 1px solid $border; border-radius: 4px; margin: 6px 6px 0 6px; padding: 6px 10px; }
.cap-infobar label.bold { font-weight: 700; }
.cap-infobar button.link { background: none; border: none; box-shadow: none; padding: 0 8px; color: $link; min-height: 24px; }
.cap-infobar button.link label { color: $link; }

popover.cap-pop, popover.cap-pop.background {
    background: $flyout; background-color: $flyout; color: $text; border-radius: 8px; border: 1px solid $border2;
    box-shadow: 0 6px 20px $shadow; padding: 6px;
}
popover.cap-pop label { color: $text; }
popover.cap-pop label.subtle { color: $subtle; }
popover.cap-pop modelbutton, popover.cap-pop button.menuitem { border-radius: 4px; min-height: 34px; padding: 0 10px; }
popover.cap-pop modelbutton:hover { background: $hover; }
.cap-pop-body { padding: 8px; }
.swatch { min-width: 30px; min-height: 30px; border-radius: 4px; border: 1px solid $border2; padding: 0; box-shadow: none; background-image: none; }
.swatch:hover { border-color: $text; }
.swatch:checked { border: 2px solid $accent; }
scale trough { background: $border2; min-height: 4px; border-radius: 2px; }
scale highlight { background: $accent; border-radius: 2px; min-height: 4px; }
scale slider { background: $accent; border: 3px solid $flyout; border-radius: 99px; min-width: 14px; min-height: 14px; margin: -7px; box-shadow: 0 0 0 1px $border2; }

/* Overlay de captura */
.snip-toolbar { background: $card; border: 1px solid $border2; border-radius: 8px; padding: 4px 6px; box-shadow: 0 4px 16px $shadow; }
.snip-toolbar button.tbtn { min-height: 32px; }
.snip-toolbar .sep { margin: 8px 6px; }

/* Configurações */
.cap-card { background: $card; border: 1px solid $border; border-radius: 4px; }
.cap-card.inner { border-radius: 0; border-width: 1px 0 0 0; background: $surface; }
.cap-row { padding: 14px 16px; min-height: 36px; }
switch { background: transparent; border: 1px solid $subtle; border-radius: 99px; min-width: 40px; min-height: 20px; }
switch slider { background: $subtle; border-radius: 99px; min-width: 12px; min-height: 12px; margin: 3px; border: none; }
switch:checked { background: $accent; border-color: $accent; }
switch:checked slider { background: $accent_text; }
.cap-window scrolledwindow, .cap-window viewport { background: transparent; }
.cap-window button.plain { background: $surface; border: 1px solid $border2; border-radius: 4px; padding: 4px 12px; box-shadow: none; background-image: none; color: $text; min-height: 24px; }
.cap-window button.plain:hover { background: $hover; }
.cap-window button.linkbtn { background: none; border: none; box-shadow: none; padding: 0; color: $link; min-height: 0; }
.cap-window button.linkbtn label { color: $link; }
.cap-window combobox button, .cap-window combobox * { color: $text; }
.cap-toolbar-crop label { color: $text; }
.sizelabel { color: $subtle; font-size: 9pt; }
.rec-bar { background: $card; border: 1px solid $border2; border-radius: 8px; padding: 4px 10px; box-shadow: 0 4px 16px $shadow; }
.rec-time { font-weight: 600; font-size: 11pt; min-width: 54px; }
.rec-dot { color: #e81123; }
.toast { background: $card; border: 1px solid $border2; border-radius: 8px; padding: 10px 18px; box-shadow: 0 4px 16px $shadow; }
""")

_provider = None
_current = None


def is_dark():
    pref = settings["theme"]
    if pref == "dark":
        return True
    if pref == "light":
        return False
    s = Gtk.Settings.get_default()
    name = (s.get_property("gtk-theme-name") or "").lower()
    return "dark" in name or bool(s.get_property("gtk-application-prefer-dark-theme"))


def palette():
    return DARK if is_dark() else LIGHT


def apply():
    global _provider, _current
    pal = palette()
    screen = Gdk.Screen.get_default()
    if _provider is not None:
        Gtk.StyleContext.remove_provider_for_screen(screen, _provider)
    _provider = Gtk.CssProvider()
    _provider.load_from_data(CSS.substitute(pal).encode())
    Gtk.StyleContext.add_provider_for_screen(screen, _provider, Gtk.STYLE_PROVIDER_PRIORITY_USER)
    _current = pal
    return pal


def icon_color():
    return palette()["text"]
