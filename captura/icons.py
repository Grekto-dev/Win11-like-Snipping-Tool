"""Ícones SVG inline (24x24, traço 1.5, estilo Fluent) — desenhados para este projeto.

`pixbuf(nome, tamanho, cor)` renderiza com GdkPixbuf; `image(...)` devolve Gtk.Image.
Os ícones usam `currentColor` (substituído pela cor pedida), então servem ao tema claro e escuro.
"""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("GdkPixbuf", "2.0")
from gi.repository import Gtk, GdkPixbuf

_S = 'fill="none" stroke="currentColor" stroke-width="1.65" stroke-linecap="round" stroke-linejoin="round"'

_ICONS = {
    "camera": '<path d="M8.5 5.5h7l1.5 2h2.5A1.5 1.5 0 0 1 21 9v8.5a1.5 1.5 0 0 1-1.5 1.5h-15A1.5 1.5 0 0 1 3 17.5V9a1.5 1.5 0 0 1 1.5-1.5H7z"/><circle cx="12" cy="13" r="3.5"/>',
    "video": '<rect x="3" y="6.5" width="12.5" height="11" rx="2.2"/><path d="M15.5 10.5l5-3v9l-5-3"/>',
    "rect": '<rect x="4" y="4" width="14" height="14" rx="3"/><path d="M17 14v6M14 17h6"/>',
    "window": '<rect x="3.5" y="5" width="17" height="14" rx="2.5"/><path d="M3.5 9.5h17"/>',
    "fullscreen": '<rect x="3" y="4.5" width="18" height="12" rx="2"/><path d="M8.5 20h7M12 16.5V20"/>',
    "freeform": '<path d="M5 10.5C5 7.4 8.1 5 12 5s7 2.4 7 5.5-3.1 5.5-7 5.5c-.8 0-1.6-.1-2.3-.3"/><path d="M9.6 15.7c-.4 1.7-1.5 3-3.6 3.8 1.5-.2 2.6-1 3-2.3"/>',
    "timer0": '<circle cx="12" cy="13.5" r="6.5"/><path d="M12 10.3v3.4l2 1.4M10 3.5h4M4 4l16 16"/>',
    "timer3": '<circle cx="11" cy="13.5" r="6.5"/><path d="M11 10.3v3.4l2 1.4M9 3.5h4"/><text x="16.5" y="21.5" font-size="8" font-family="sans-serif" fill="currentColor" stroke="none">3</text>',
    "timer5": '<circle cx="11" cy="13.5" r="6.5"/><path d="M11 10.3v3.4l2 1.4M9 3.5h4"/><text x="16.5" y="21.5" font-size="8" font-family="sans-serif" fill="currentColor" stroke="none">5</text>',
    "timer10": '<circle cx="10" cy="13.5" r="6.5"/><path d="M10 10.3v3.4l2 1.4M8 3.5h4"/><text x="14.5" y="21.5" font-size="8" font-family="sans-serif" fill="currentColor" stroke="none">10</text>',
    "eraser": '<path d="M8.6 19.5 4 14.9a2 2 0 0 1 0-2.8l8.2-8.2a2 2 0 0 1 2.8 0l5 5a2 2 0 0 1 0 2.8L12.2 19.5"/><path d="M8 19.5h12.5M7.5 9.5l7.5 7.5"/>',
    "shapes": '<circle cx="9.5" cy="9.5" r="5.5"/><rect x="11" y="11" width="9" height="9" rx="1.8"/>',
    "crop": '<path d="M7 3v12.5a1.5 1.5 0 0 0 1.5 1.5H21M3 7h12.5A1.5 1.5 0 0 1 17 8.5V21"/>',
    "textscan": '<path d="M4 8V6.5A2.5 2.5 0 0 1 6.5 4H8m8 0h1.5A2.5 2.5 0 0 1 20 6.5V8m0 8v1.5a2.5 2.5 0 0 1-2.5 2.5H16M8 20H6.5A2.5 2.5 0 0 1 4 17.5V16M8 9.5h8M8 12.5h8M8 15.5h5"/>',
    "undo": '<path d="M8.5 5.5 4 10l4.5 4.5"/><path d="M4 10h10.5a5 5 0 0 1 0 10H11"/>',
    "redo": '<path d="M15.5 5.5 20 10l-4.5 4.5"/><path d="M20 10H9.5a5 5 0 0 0 0 10H13"/>',
    "save": '<path d="M5.5 4h10.2L20 8.3v10.2a1.5 1.5 0 0 1-1.5 1.5h-13A1.5 1.5 0 0 1 4 18.5v-13A1.5 1.5 0 0 1 5.5 4z"/><path d="M8 4v5h7V4M8 20v-6h8v6"/>',
    "copy": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6A2 2 0 0 0 13.5 4H6A2 2 0 0 0 4 6v7.5A2 2 0 0 0 6 15.5h2.5"/>',
    "share": '<path d="M12 14.5V3.5M7.5 8 12 3.5 16.5 8"/><path d="M8 10.5H6.5a2 2 0 0 0-2 2v5.5a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2v-5.5a2 2 0 0 0-2-2H16"/>',
    "more": '<circle cx="5.5" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="12" cy="12" r="1.4" fill="currentColor" stroke="none"/><circle cx="18.5" cy="12" r="1.4" fill="currentColor" stroke="none"/>',
    "close": '<path d="M6 6l12 12M18 6 6 18"/>',
    "plus": '<path d="M12 5v14M5 12h14"/>',
    "check": '<path d="M5 12.5l4.5 4.5L19 7.5"/>',
    "eyedropper": '<path d="M13.5 6.5l4 4M16.8 3.7a2.4 2.4 0 0 1 3.5 3.5l-2 1.8-3.5-3.5z"/><path d="M14 7.5 6.2 15.3a2 2 0 0 0-.5 1l-.4 2.5 2.5-.4a2 2 0 0 0 1-.5l7.8-7.8"/>',
    "markup": '<path d="M4.5 19.5l.8-3.8L16.6 4.4a2.1 2.1 0 0 1 3 3L8.3 18.7z"/><path d="M14.8 6.2l3 3"/>',
    "gear": '<circle cx="12" cy="12" r="3.2"/><path d="M10.4 3.5h3.2l.5 2.3 1.5.8 2.2-.8 1.6 2.8-1.8 1.6v1.6l1.8 1.6-1.6 2.8-2.2-.8-1.5.8-.5 2.3h-3.2l-.5-2.3-1.5-.8-2.2.8-1.6-2.8 1.8-1.6v-1.6L4.6 8.3l1.6-2.8 2.2.8 1.5-.8z"/>',
    "folder": '<path d="M3.5 18V7A1.5 1.5 0 0 1 5 5.5h4l2 2.5h8A1.5 1.5 0 0 1 20.5 9.5V10"/><path d="M3.8 18.5l2.2-7.2a1.5 1.5 0 0 1 1.4-1h13.2a1 1 0 0 1 1 1.3l-2 6.4a1.5 1.5 0 0 1-1.4 1H4.8a1 1 0 0 1-1-1.5z"/>',
    "print": '<path d="M7 8.5V4.5h10v4M7 17H5.5A1.5 1.5 0 0 1 4 15.5v-5A1.5 1.5 0 0 1 5.5 9h13a1.5 1.5 0 0 1 1.5 1.5v5a1.5 1.5 0 0 1-1.5 1.5H17"/><rect x="7" y="13.5" width="10" height="6" rx="1"/>',
    "zoom": '<circle cx="10.5" cy="10.5" r="6.5"/><path d="M15.5 15.5 21 21M10.5 7.5v6M7.5 10.5h6"/>',
    "chevron_down": '<path d="M6 9.5l6 6 6-6"/>',
    "chevron_right": '<path d="M9.5 6l6 6-6 6"/>',
    "chevron_up": '<path d="M6 14.5l6-6 6 6"/>',
    "back": '<path d="M20 12H4.5M10.5 6 4.5 12l6 6"/>',
    "rotate": '<path d="M19 12a7 7 0 1 1-2.3-5.2"/><path d="M19 4.5v4h-4"/>',
    "edit": '<path d="M4.5 19.5l.8-3.8L16.6 4.4a2.1 2.1 0 0 1 3 3L8.3 18.7z"/>',
    "info": '<circle cx="12" cy="12" r="8.5"/><path d="M12 11v5.5" /><circle cx="12" cy="7.8" r=".6" fill="currentColor"/>',
    "markup_img": '<path d="M12.5 4.5H7A2.5 2.5 0 0 0 4.5 7v10A2.5 2.5 0 0 0 7 19.5h10a2.5 2.5 0 0 0 2.5-2.5v-4.5"/><path d="M4.8 16.5l4.2-4.2a1.6 1.6 0 0 1 2.2 0l1.3 1.3"/><circle cx="8.6" cy="8.6" r="1.2"/><path d="M19.8 4.2a1.7 1.7 0 0 1 0 2.4L14 12.4l-2.7.7.7-2.7 5.8-5.8a1.7 1.7 0 0 1 2.4 0z"/>',
    "info_filled": '<circle cx="12" cy="12" r="9.5" fill="currentColor" stroke="none"/><path d="M12 11v5.6" stroke="#ffffff" stroke-width="2"/><circle cx="12" cy="7.6" r="1.25" fill="#ffffff" stroke="none"/>',
    "trash": '<path d="M4.5 7h15M9.5 7V4.5h5V7M6.5 7l.8 12.5h9.4L17.5 7M10 11v5.5M14 11v5.5"/>',
    "copytext": '<rect x="8.5" y="8.5" width="11.5" height="11.5" rx="2"/><path d="M15.5 8.5V6A2 2 0 0 0 13.5 4H6A2 2 0 0 0 4 6v7.5A2 2 0 0 0 6 15.5h2.5M11.5 12.5h5M11.5 15.5h5"/>',
    "mic": '<rect x="9" y="3.5" width="6" height="11" rx="3"/><path d="M5.5 11.5a6.5 6.5 0 0 0 13 0M12 18v2.5"/>',
    "speaker": '<path d="M4 9.5v5h3.5l5 4v-13l-5 4z"/><path d="M16 9a4 4 0 0 1 0 6M18.5 6.5a7.5 7.5 0 0 1 0 11"/>',
    "stop": '<rect x="6.5" y="6.5" width="11" height="11" rx="2" fill="currentColor"/>',
    "record": '<circle cx="12" cy="12" r="6" fill="currentColor" stroke="none"/>',
    "line": '<path d="M5 19 19 5"/>',
    "arrow": '<path d="M5 19 19 5M10 5h9v9"/>',
    "ellipse": '<ellipse cx="12" cy="12" rx="8.5" ry="6.5"/>',
    "square": '<rect x="4.5" y="5.5" width="15" height="13" rx="1.5"/>',
    "share_mail": '<rect x="3.5" y="5.5" width="17" height="13" rx="2"/><path d="M4 7.5l8 6 8-6"/>',
    "openwith": '<path d="M10 4.5H6.5a2 2 0 0 0-2 2v11a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V14M13.5 4.5h6v6M19.5 4.5 11 13"/>',
}


def svg(name, size=20, color="#000000", extra=""):
    body = _ICONS[name]
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" {_S} '
            f'color="{color}" {extra}>{body}</svg>').replace("currentColor", color).encode()


_cache = {}


def pixbuf(name, size=20, color="#1b1b1b", scale=1):
    key = (name, size, color, scale)
    if key not in _cache:
        loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
        loader.set_size(size * scale, size * scale)
        loader.write(svg(name, size * scale, color))
        loader.close()
        _cache[key] = loader.get_pixbuf()
    return _cache[key]


import weakref
TEXT_COLOR = ["#1b1b1b"]
_themed = []


def image(name, size=20, color="#1b1b1b"):
    img = Gtk.Image.new_from_pixbuf(pixbuf(name, size, color))
    if color == TEXT_COLOR[0]:
        _themed.append((weakref.ref(img), name, size))
    return img


def set_text_color(color):
    """Recolore todos os ícones criados com a cor de texto do tema anterior."""
    TEXT_COLOR[0] = color
    alive = []
    for ref, name, size in _themed:
        img = ref()
        if img is not None:
            img.set_from_pixbuf(pixbuf(name, size, color))
            alive.append((ref, name, size))
    _themed[:] = alive


def marker_svg(color, tip="#e61b1b", highlighter=False, size=22):
    """Ícone de caneta/marca-texto com a ponta na cor atual (como no Windows)."""
    if highlighter:
        body = ('<path d="M7.5 3.5h9l1.5 8-4 1.5v4.2L12 19.5l-2-2.3V13L6 11.5z" fill="%s" fill-opacity=".9"/>'
                '<path d="M7.5 3.5h9l1.5 8-4 1.5v4.2L12 19.5l-2-2.3V13L6 11.5zM9 21h6" fill="none"/>') % tip
    else:
        body = ('<path d="M6 3.5h12l-3.8 8v5.4L12 20l-2.2-3.1v-5.4z" fill="none"/>'
                '<path d="M10 12.2h4l-.6 4.5L12 19l-1.4-2.3z" fill="%s" stroke="none"/>') % tip
    return body


def tool_pixbuf(kind, tip, color, size=22):
    """kind: 'pen' | 'highlighter'."""
    body = marker_svg(color, tip, kind == "highlighter")
    doc = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{size}" height="{size}" viewBox="0 0 24 24" {_S} '
           f'color="{color}">{body}</svg>').replace("currentColor", color).encode()
    loader = GdkPixbuf.PixbufLoader.new_with_type("svg")
    loader.set_size(size, size)
    loader.write(doc)
    loader.close()
    return loader.get_pixbuf()
