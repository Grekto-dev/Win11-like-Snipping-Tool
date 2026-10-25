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
    shadow="rgba(0,0,0,0.28)", bar="#e9e9e9", crop_bg="#666666", toast_bg="#ffffff", link="#003e92", segbg="#ececec",
)
DARK = dict(
    dark=True, bg0="#202020", surface="#2b2b2b", canvas="#1c1c1c", text="#ffffff", subtle="#c8c8c8", disabled="#6f6f6f",
    border="#333333", border2="#454545", hover="rgba(255,255,255,0.07)", press="rgba(255,255,255,0.05)", card="#2b2b2b",
    accent="#60cdff", accent_hover="#7ad6ff", accent_text="#000000", infobar="#2b2b2b", flyout="#2c2c2c",
    shadow="rgba(0,0,0,0.6)", bar="#2c2c2c", crop_bg="#1a1a1a", toast_bg="#2b2b2b", link="#99ebff", segbg="#2d2d2d",
)

CSS = string.Template(r"""
* { font-size: 9.5pt; }
.cap-window, .cap-window decoration { background: $bg0; color: $text; }
.cap-window headerbar, headerbar.cap-header {
    background: $bg0; color: $text; border: none; box-shadow: none; min-height: 32px; padding: 0 4px;
}
headerbar.cap-header .title { color: $subtle; font-size: 9pt; }
headerbar.cap-header button.titlebutton { color: $text; background: transparent; border: none; box-shadow: none; min-width: 34px; min-height: 30px; border-radius: 4px; }
headerbar.cap-header button.titlebutton:hover { background: $hover; }
headerbar.cap-header button.titlebutton.close:hover { background: #c42b1c; color: #fff; }
.cap-window label { color: $text; }
.cap-window label.subtle { color: $subtle; font-size: 9pt; }
.cap-window label.section { font-weight: 400; font-size: 10.5pt; }
.cap-window label.pagetitle { font-size: 15pt; font-weight: 600; }
.cap-canvas-bg { background: $canvas; }
.cap-canvas-bg.cropping { background: $crop_bg; }

button.tbtn, button.tbtn:backdrop {
    background: transparent; color: $text; border: 1px solid transparent; box-shadow: none; text-shadow: none;
    border-radius: 4px; padding: 0 3px; min-height: 34px; min-width: 34px; -gtk-icon-shadow: none; outline: none;
}
button.tbtn:hover { background: $hover; }
button.tbtn:active, button.tbtn:checked { background: $press; }
button.tbtn:checked { border-color: $accent; }
button.tbtn:disabled { opacity: .4; }
button.tbtn.newbtn { background: $surface; border: 1px solid $border2; padding: 0 12px; }
button.tbtn.newbtn:hover { background: $hover; }
button.tbtn.newbtn.icononly { padding: 0; min-width: 40px; }
button.tbtn.accentbtn { background: $accent; color: $accent_text; border: none; padding: 0 16px; }
button.tbtn.accentbtn:hover { background: $accent_hover; }
button.tbtn.accentbtn label { color: $accent_text; }
button.tbtn.menuitem { min-width: 0; padding: 0 12px; border-radius: 4px; }
button.tbtn.menuitem label { color: $text; }

.seg { background: $segbg; border: 1px solid $border; border-radius: 6px; padding: 1px; }
.seg button.tbtn { min-width: 36px; min-height: 30px; border-radius: 5px; padding: 0 4px; }
.seg button.tbtn:checked { background: $card; border: 1px solid $border2; }
.seg button.tbtn:checked.indicator { }
.sep { background: $border2; min-width: 1px; min-height: 20px; margin: 0 6px; }
.msep { background: $border; min-height: 1px; margin: 4px 2px; }
.cap-toolbar { border-bottom: 0; }
.ind-bar { background: $accent; border-radius: 2px; min-width: 14px; min-height: 3px; }
.cap-infobar { padding: 14px 18px 12px 18px; }
.cap-infobar label, .cap-infobar label.bold { font-size: 9pt; }
.tbtn label { font-size: 9.5pt; }
.cap-infobar label.bold { font-weight: 600; }
.cap-title { color: $subtle; font-size: 9pt; }
.empty-text { font-size: 9.5pt; }

.cap-infobar { background: $infobar; border: 0 solid $border; border-width: 1px 0 1px 0; border-radius: 0; margin: 0; }
.cap-infobar label.bold { font-weight: 700; }
.cap-infobar button.link { background: none; border: none; box-shadow: none; padding: 0; color: $link; min-height: 24px; min-width: 0; }
.cap-infobar button.link label { color: $link; }

popover.cap-pop, popover.cap-pop.background {
    background: $flyout; background-color: $flyout; color: $text; border-radius: 8px; border: 1px solid $border2;
    box-shadow: 0 3px 10px rgba(0,0,0,0.22); padding: 6px; margin: 4px;
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
.cap-pop scale value { color: $text; font-size: 9pt; }
scale slider { background: $accent; border: 3px solid $flyout; border-radius: 99px; min-width: 14px; min-height: 14px; margin: -7px; box-shadow: 0 0 0 1px $border2; }

tooltip.background, tooltip { background: $flyout; background-color: $flyout; color: $text; border: 1px solid $border2; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
tooltip label { color: $text; font-size: 9.5pt; padding: 2px 4px; }
menu, .menu { background: $flyout; color: $text; border: 1px solid $border2; border-radius: 6px; }
menu menuitem label, .menu menuitem label { color: $text; }
/* Overlay de captura */
.snip-toolbar { background: $bar; border: 1px solid $border; border-radius: 12px; padding: 3px 8px; box-shadow: 0 6px 24px $shadow; }
.snip-toolbar .seg { background: transparent; border: none; }
.snip-toolbar .seg button.tbtn { background: $hover; border-radius: 6px; margin: 0 1px; }
.snip-toolbar .seg button.tbtn { min-width: 34px; min-height: 36px; padding: 0; border-radius: 6px; border: 1px solid transparent; }
.snip-toolbar .seg button.tbtn:checked { background: $card; border: 1px solid $border2; }
.snip-toolbar button.tbtn { min-height: 34px; min-width: 28px; padding: 0 2px; }
.snip-toolbar button.tbtn { min-height: 32px; }
.snip-toolbar .sep { margin: 8px 6px; }

/* Configurações */
.cap-card { background: $card; border: 1px solid $border; border-radius: 5px; }
.cap-card.inner { border-radius: 0; border-width: 1px 0 0 0; background: $bg0; }
.cap-row { padding: 10px 16px; min-height: 40px; }
switch { background: transparent; border: 1px solid $subtle; border-radius: 99px; min-width: 40px; min-height: 20px; }
switch slider { background: $subtle; border-radius: 99px; min-width: 12px; min-height: 12px; margin: 3px; border: none; }
switch:checked { background: $accent; border-color: $accent; }
switch:checked slider { background: $accent_text; }
.cap-window scrolledwindow, .cap-window viewport { background: transparent; }
.cap-window button.plain { background: $surface; border: 1px solid $border2; border-radius: 4px; padding: 4px 12px; box-shadow: none; background-image: none; color: $text; min-height: 24px; }
.cap-window button.plain:hover { background: $hover; }
.cap-window button.linkbtn { background: none; border: none; box-shadow: none; padding: 0; color: $link; min-height: 0; }
.cap-window button.linkbtn label { color: $link; }
.cap-window combobox button.combo { background: $surface; background-image: none; color: $text; border: 1px solid $border2; border-radius: 4px; box-shadow: none; padding: 4px 10px; min-height: 28px; min-width: 190px; }
.cap-window combobox button.combo:hover { background: $hover; }
.cap-window combobox button.combo cellview, .cap-window combobox button.combo label, .cap-window combobox arrow { color: $text; }
.cap-window combobox window.popup, .cap-window combobox menu, menu.cap-combo-menu { background: $flyout; color: $text; border: 1px solid $border2; border-radius: 6px; padding: 4px; }
.cap-window combobox menu menuitem, menu menuitem { color: $text; padding: 6px 10px; border-radius: 4px; }
.cap-window combobox menu menuitem:hover, menu menuitem:hover { background: $hover; }
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
    from . import icons
    icons.set_text_color(pal["text"])
    return pal


def icon_color():
    return palette()["text"]
