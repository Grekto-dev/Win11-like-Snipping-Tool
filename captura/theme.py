"""Tema Fluent (claro/escuro) aplicado por CSS do GTK3, independente do tema do Mint."""
import string
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gtk, Gdk

from .config import settings

LIGHT = dict(
    dark=False, bg0="#f3f3f3", surface="#fbfbfb", canvas="#fcfcfc", text="#1a1a1a", subtle="#5f5f5f", disabled="#a0a0a0",
    chev="#5b5b5b", disabled_icon="#9b9b9b", tile_on="#eaeaea", seg_off="#ededed", seg_on="#fafafa", seg_edge="#c4c4c4", seg_out="#dfdfdf",
    border="#e0e0e0", border2="#d1d1d1", hover="rgba(0,0,0,0.055)", press="rgba(0,0,0,0.085)", card="#fdfdfd",
    accent="#0067c0", accent_hover="#1975c5", accent_text="#ffffff", infobar="#ffffff", flyout="#fcfcfc",
    shadow="rgba(0,0,0,0.28)", bar="#e9e9e9", crop_bg="#656565", toast_bg="#ffffff", link="#003e92", segbg="#ececec",
    menu_bg="#f9f9f9", menu_border="#dbdbdb", menu_top="#c0c0c0", menu_sel="#eaeaea", menu_sep="#e5e5e5",
    crop_hover="#eaeaea", radio_fill="#eeeeee", radio_ring="#878787", set_card="#fbfbfb", set_border="#e5e5e5", set_inner="#f4f4f4", set_btn="#fcfcfc", set_btn_top="#e6e6e6", set_btn_bot="#cdcdcd", sbar_border="#ededed", sbar_sep="#eaeaea", sbar_sel="#f0f0f0", sbar_inner="#ffffff", fly2_border="#eaeaea",
)
DARK = dict(
    dark=True, bg0="#202020", surface="#2b2b2b", canvas="#1c1c1c", text="#ffffff", subtle="#c8c8c8", disabled="#6f6f6f",
    chev="#c8c8c8", disabled_icon="#6f6f6f", tile_on="#2f2f2f", seg_off="#2b2b2b", seg_on="#3a3a3a", seg_edge="#5a5a5a", seg_out="#3d3d3d",
    border="#333333", border2="#454545", hover="rgba(255,255,255,0.07)", press="rgba(255,255,255,0.05)", card="#2b2b2b",
    accent="#60cdff", accent_hover="#7ad6ff", accent_text="#000000", infobar="#2b2b2b", flyout="#2c2c2c",
    shadow="rgba(0,0,0,0.6)", bar="#2c2c2c", crop_bg="#1a1a1a", toast_bg="#2b2b2b", link="#99ebff", segbg="#2d2d2d",
    menu_bg="#2c2c2c", menu_border="#383838", menu_top="#454545", menu_sel="#383838", menu_sep="#414141",
    crop_hover="#333333", radio_fill="#2f2f2f", radio_ring="#9a9a9a", set_card="#2b2b2b", set_border="#383838", set_inner="#262626", set_btn="#323232", set_btn_top="#3d3d3d", set_btn_bot="#2a2a2a", sbar_border="#3a3a3a", sbar_sep="#404040", sbar_sel="#383838", sbar_inner="#2c2c2c", fly2_border="#3a3a3a",
)

CSS = string.Template(r"""
* { font-family: "Selawik", "Segoe UI", "Noto Sans", sans-serif; font-size: 14px; }
.cap-window { background: $bg0; color: $text; }
window.cap-window decoration { background: $bg0; box-shadow: 0 0 0 1px rgba(0,0,0,0.18), 0 6px 22px rgba(0,0,0,0.28); margin: 24px; border-radius: 8px; }
window.cap-window.maximized decoration { margin: 0; box-shadow: none; border-radius: 0; }
headerbar.cap-header { background: $bg0; color: $text; border: none; box-shadow: none; min-height: 32px; padding: 0; margin: 0; border-radius: 8px 8px 0 0; }
headerbar.cap-header .title { color: $text; }
headerbar.cap-header .title { color: $subtle; font-size: 9pt; }
.cap-window label { color: $text; }
.cap-window label.subtle { color: $subtle; font-size: 12px; }
.cap-window label.section { font-weight: 400; font-size: 14px; }
.cap-window label.pagetitle { font-size: 19.5px; font-weight: 600; }
.cap-canvas-bg { background: #f9f9f9; }
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
.cap-title { color: $text; font-size: 12px; }
.empty-text { font-size: 14px; }

.cap-infobar { background: $infobar; border: 1px solid #ededed; border-radius: 5px; margin: 0; padding: 0; }
.info-title { font-weight: 600; color: $text; }
.info-desc { color: $text; letter-spacing: 0.1px; }
.cap-infobar button.link { background: none; border: none; box-shadow: none; padding: 0; margin: 0; color: $link; min-height: 0; min-width: 0; }
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
.cap-pop scale value { color: $text; font-size: 12px; }
scale slider { background: $accent; border: 3px solid $flyout; border-radius: 99px; min-width: 14px; min-height: 14px; margin: -7px; box-shadow: 0 0 0 1px $border2; }

tooltip.background, tooltip { background: $flyout; background-color: $flyout; color: $text; border: 1px solid $border2; border-radius: 6px; box-shadow: 0 2px 8px rgba(0,0,0,0.2); }
tooltip label { color: $text; font-size: 12px; padding: 2px 4px; }
menu, .menu { background: $flyout; color: $text; border: 1px solid $border2; border-radius: 6px; }
menu menuitem label, .menu menuitem label { color: $text; }
/* ---- botões de precisão (barra de ferramentas) ---- */
button.px { background: transparent; background-image: none; border: 0 solid transparent; border-radius: 4px; padding: 0; margin: 0;
    min-width: 0; min-height: 0; box-shadow: none; text-shadow: none; outline: none; -gtk-icon-shadow: none; }
button.px:hover { background: rgba(0,0,0,0.0373); }
button.px:active { background: rgba(0,0,0,0.0241); }
button.px:disabled { opacity: 1; }
button.px:disabled image { -gtk-icon-effect: none; opacity: 1; }
button.px.tool { border: 1px solid transparent; border-radius: 5px; }
button.px.tool:checked { background: $tile_on; border-color: $accent; box-shadow: inset 0 0 0 2px $card; }
button.px.newbtn { background: #fbfbfb; border: 1px solid #e5e5e5; border-bottom-color: #cccccc; border-radius: 4px; }
button.px.segl, button.px.segr { background: $seg_off; border: 1px solid $seg_out; border-radius: 0; }
button.px.segl { border-radius: 4px 0 0 4px; border-right-color: transparent; }
button.px.segr { border-radius: 0 4px 4px 0; border-left-color: transparent; }
button.px.segl:checked, button.px.segr:checked { background: $seg_on; border-color: $seg_edge; }
button.px.segl:checked { border-right-color: #cccccc; }
button.px.segr:checked { border-left-color: #cccccc; }
box.pxsep { background: #e0e0e0; min-width: 1px; }
box.tbline { background: #e0e0e0; min-height: 1px; }
button.caption { background: transparent; background-image: none; border: 0; border-radius: 0; padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none; outline: none; }
button.caption:hover { background: rgba(0,0,0,0.0373); }
button.caption-close:hover { background: #c42b1c; }
.ind-bar { background: $accent; border-radius: 2px; min-width: 16px; min-height: 3px; }
.cap-toolbar { background: $bg0; }
/* ---- menus ---- */
window.popup-root, .popup-root { background: transparent; }
.wmenu, .wflyout { background: $menu_bg; border: 1px solid $menu_border; border-top-color: $menu_top; border-radius: 8px; box-shadow: none; }
button.wmi { background: transparent; background-image: none; border: 0; border-radius: 4px; padding: 0; margin: 0; box-shadow: none; min-width: 0; min-height: 0; text-shadow: none; outline: none; }
button.wmi:hover { background: $hover; }
.wmenu-selection { background: $menu_sel; border-radius: 4px; }
.wmenu label, .wflyout label { color: $text; }
button.wmi:disabled label { color: $disabled_icon; }
.wmenu-bar { background: $accent; border-radius: 2px; }
.wmenu label.wmenu-accel { color: $subtle; font-size: 12px; }
.wmenu-sep { background: $menu_sep; min-height: 1px; margin: 3px 0; }
.wmenu-sep.tight { margin: 1px 0; }
/* measured tool palettes */
.wflyout { border-color: #c4c4c4; border-radius: 4px; }
button.palette-swatch { background: transparent; background-image: none; border: 0; border-radius: 20px; padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none; outline: none; }
button.palette-swatch:hover { background: $hover; }
scale.palette-size { padding: 0; margin: 0; }
scale.palette-size trough { background: #8a8a8a; min-height: 4px; border: 0; border-radius: 2px; }
scale.palette-size highlight { background: $accent; min-height: 4px; border-radius: 2px; }
scale.palette-size slider { background: $accent; background-image: none; border: 5px solid #ffffff; border-radius: 99px; min-width: 10px; min-height: 10px; margin: -8px; box-shadow: 0 0 0 1px rgba(0,0,0,0.04); }
/* barra de Formas no conteúdo e flyouts de cor */
.shapebar { background: $menu_bg; border: 1px solid $sbar_border; border-radius: 8px; }
box.sb-sep { background: $sbar_sep; min-width: 1px; }
button.sb-btn { background: transparent; background-image: none; border: 1px solid transparent; border-radius: 4px; padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none; outline: none; }
button.sb-btn:hover { background: $sbar_sel; }
button.sb-btn:checked { background: $sbar_sel; border-color: $accent; box-shadow: inset 0 0 0 1px $sbar_inner; }
button.sb-btn.sb-plain:hover { background: transparent; }
button.sb-btn.crop-btn:hover { background: $crop_hover; }
.wflyout2 { background: $menu_bg; border: 1px solid $fly2_border; border-radius: 8px; box-shadow: none; }
.wflyout2 button.emoji-cell { background: transparent; background-image: none; border: 0; border-radius: 4px; padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none; outline: none; }
.wflyout2 button.emoji-cell:hover { background: $sbar_sel; }
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
.cap-card { background: $set_card; border: 1px solid $set_border; border-radius: 4px; }
.cap-card.inner { border-radius: 0; border-width: 1px 0 0 0; background: $bg0; }
button.radio-row { background: transparent; background-image: none; border: 0; padding: 0; margin: 0; min-width: 0; min-height: 0; box-shadow: none; outline: none; }
.cap-inner { background: $set_inner; border-top: 1px solid $set_border; }
.cap-row { padding: 0 0 0 16px; }
.cap-window label.section { font-weight: 400; font-size: 14px; }
.cap-window label.section-about { font-weight: 600; font-size: 14px; }
.cap-window label.about-line { margin: 0 0 8px 0; }
.cap-window button.about-link { margin: 10px 0 0 12px; }
.cap-window button.fluent-btn { background: $set_btn; background-image: none; border: 1px solid $set_btn_top; border-bottom-color: $set_btn_bot; border-radius: 4px; padding: 0; box-shadow: none; min-height: 0; min-width: 0; color: $text; }
.cap-window button.fluent-btn:hover { background: $hover; }
switch { background: transparent; border: 1px solid $subtle; border-radius: 99px; min-width: 38px; min-height: 18px; padding: 0; margin: 0; }
switch slider { background: $subtle; border-radius: 99px; min-width: 12px; min-height: 12px; margin: 2px; border: none; }
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
.sizelabel { color: $subtle; font-size: 12px; }
.rec-bar { background: $card; border: 1px solid $border2; border-radius: 8px; padding: 4px 10px; box-shadow: 0 4px 16px $shadow; }
.rec-time { font-weight: 600; font-size: 14px; min-width: 54px; }
.rec-dot { color: #e81123; }
.textbar { background: $card; border: 1px solid $border2; border-radius: 8px; padding: 6px; box-shadow: 0 4px 16px $shadow; }
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
    icons.apply_palette(pal)
    return pal


def icon_color():
    return palette()["text"]
