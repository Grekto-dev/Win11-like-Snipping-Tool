"""Construção pixel a pixel da barra de título, da faixa de ferramentas e do aviso (infobar)."""
import math
import cairo
import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, Gdk

from . import crop_bar, icons, metrics as M, APP_NAME
from .config import settings


def _px(widget, w, h):
    widget.set_size_request(w, h)
    return widget


def px_button(tile, canvas, icon=None, role="text", toggle=False, cls=(), size=20, tip=None, origin=(0, 0)):
    """Botão de tamanho exato `tile` (x,y,w,h absolutos) com o ícone cujo canvas 20x20 começa em `canvas`.

    `origin` é o canto (x,y) do contêiner Fixed, para converter coordenadas absolutas em locais.
    Devolve (botão, imagem, overlay).
    """
    b = Gtk.ToggleButton() if toggle else Gtk.Button()
    ctx = b.get_style_context()
    ctx.add_class("px")
    for c in cls:
        ctx.add_class(c)
    b.set_can_focus(False)
    b.set_size_request(tile[2], tile[3])
    b.set_halign(Gtk.Align.START)
    b.set_valign(Gtk.Align.START)
    if tip:
        b.set_tooltip_text(tip)
    ov = Gtk.Overlay()
    b.add(ov)
    img = None
    if icon:
        img = icons.role_image(icon, size, role)
        img.set_halign(Gtk.Align.START)
        img.set_valign(Gtk.Align.START)
        bw = 1 if any(k in cls for k in ("newbtn", "segl", "segr", "tool")) else 0   # borda CSS desloca o conteúdo
        img.set_margin_start(canvas[0] - tile[0] - bw)
        img.set_margin_top(canvas[1] - tile[1] - bw)
        ov.add(img)
    else:
        ov.add(Gtk.Box())
    return b, img, ov


def put(fixed, widget, abs_x, abs_y, origin=(0, 0)):
    fixed.put(widget, abs_x - origin[0], abs_y - origin[1])


def separator(fixed, abs_x, origin):
    s = Gtk.Box()
    s.get_style_context().add_class("pxsep")
    s.set_size_request(1, M.SEP_H)
    put(fixed, s, abs_x, M.SEP_Y, origin)
    return s


# --------------------------------------------------------------------------- cabeçalho
class CaptionButton(Gtk.Button):
    """Minimizar / maximizar / fechar desenhados em cairo, na geometria medida (46x32, glifo 10x10)."""

    def __init__(self, kind, on_click):
        super().__init__()
        self.kind = kind
        self.get_style_context().add_class("caption")
        if kind == "close":
            self.get_style_context().add_class("caption-close")
        self.set_can_focus(False)
        self.set_size_request(M.CAPTION_W, M.TITLE_H)
        self.da = Gtk.DrawingArea()
        self.da.connect("draw", self._draw)
        self.add(self.da)
        self.connect("clicked", lambda *_: on_click())

    def _draw(self, da, cr):
        from . import theme
        pal = theme.palette()
        hover = bool(self.get_state_flags() & Gtk.StateFlags.PRELIGHT)
        if self.kind == "close" and hover:
            r, g, b = 1, 1, 1
        else:
            r, g, b = _rgb(pal["text"])
        cr.set_source_rgb(r, g, b)
        cr.set_line_width(1)
        cr.set_antialias(cairo.ANTIALIAS_DEFAULT)
        if self.kind == "min":
            cr.move_to(19, 14.5)
            cr.line_to(29, 14.5)
        elif self.kind == "max":
            _round_rect(cr, 18.5, 9.5, 9, 9, 1.6)
        else:
            cr.move_to(18.5, 9.5)
            cr.line_to(27.5, 18.5)
            cr.move_to(27.5, 9.5)
            cr.line_to(18.5, 18.5)
        cr.stroke()
        return False


def _rgb(h):
    h = h.lstrip("#")
    return int(h[0:2], 16) / 255, int(h[2:4], 16) / 255, int(h[4:6], 16) / 255


def _round_rect(cr, x, y, w, h, r):
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -math.pi / 2, 0)
    cr.arc(x + w - r, y + h - r, r, 0, math.pi / 2)
    cr.arc(x + r, y + h - r, r, math.pi / 2, math.pi)
    cr.arc(x + r, y + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def build_header(win):
    hb = Gtk.HeaderBar()
    hb.get_style_context().add_class("cap-header")
    hb.set_show_close_button(False)
    hb.props.spacing = 0
    hb.set_custom_title(Gtk.Box())
    title = Gtk.Box(spacing=0)
    title.set_size_request(-1, M.TITLE_H)
    icon = Gtk.Image.new_from_icon_name("captura", Gtk.IconSize.MENU)
    icon.set_pixel_size(16)
    icon.set_margin_start(M.ICON_X)
    icon.set_margin_end(M.TITLE_X - M.ICON_X - 16)
    icon.set_margin_bottom(6)
    title.pack_start(icon, False, False, 0)
    win.title_label = Gtk.Label(label=APP_NAME)
    win.title_label.get_style_context().add_class("cap-title")
    win.title_label.set_margin_bottom(2)
    title.pack_start(win.title_label, False, False, 0)
    hb.pack_start(title)
    caps = Gtk.Box(spacing=0)
    caps.pack_start(CaptionButton("min", win.iconify), False, False, 0)

    def toggle_max():
        if win.is_maximized():
            win.unmaximize()
        else:
            win.maximize()
    caps.pack_start(CaptionButton("max", toggle_max), False, False, 0)
    caps.pack_start(CaptionButton("close", win.close), False, False, 0)
    hb.pack_end(caps)
    hb.show_all()
    return hb


# --------------------------------------------------------------------------- faixa de ferramentas
def build_toolbar(win, shapes, delays):
    """Cria a faixa e anexa os widgets a `win` (mesmos nomes de atributos usados no restante do app)."""
    bar = Gtk.Box()
    bar.get_style_context().add_class("cap-toolbar")
    bar.set_size_request(-1, M.TB_H)

    # ---- esquerda
    left = Gtk.Fixed()
    left.set_size_request(M.NEW["tile"][0] + 275 - 16, M.TB_H)
    o = (0, M.TB_Y)
    win.btn_new, win.new_img, _ = px_button(M.NEW["tile"], M.NEW["canvas"], "plus", "accent", cls=("newbtn",),
                                            tip="Nova captura (Ctrl+N)")
    put(left, win.btn_new, *M.NEW["tile"][:2], origin=o)
    ov_new = win.btn_new.get_child()
    win.new_label = Gtk.Label(label="Novo")
    win.new_label.set_halign(Gtk.Align.START)
    win.new_label.set_valign(Gtk.Align.CENTER)
    win.new_label.set_margin_start(M.EMPTY_NEW_LABEL_X - M.NEW["tile"][0] - 1)
    win.new_label.set_margin_bottom(1)
    win.new_label.set_no_show_all(True)
    ov_new.add_overlay(win.new_label)
    ov_new.set_overlay_pass_through(win.new_label, True)      # os filhos do botão não podem engolir o clique

    win.b_photo, _, ov_p = px_button(M.PHOTO["tile"], M.PHOTO["canvas"], "camera", toggle=True, cls=("segl",),
                                     tip="Captura de tela")
    win.b_video, _, ov_v = px_button(M.VIDEO["tile"], M.VIDEO["canvas"], "video", toggle=True, cls=("segr",),
                                     tip="Gravação de tela")
    for b, ov, t in ((win.b_photo, ov_p, M.PHOTO["tile"]), (win.b_video, ov_v, M.VIDEO["tile"])):
        bar_ind = Gtk.Box()
        bar_ind.get_style_context().add_class("ind-bar")
        bar_ind.set_size_request(16, 3)
        bar_ind.set_halign(Gtk.Align.START)
        bar_ind.set_valign(Gtk.Align.START)
        bar_ind.set_margin_start(10)
        bar_ind.set_margin_top(27)
        bar_ind.set_opacity(0.0)
        ov.add_overlay(bar_ind)
        ov.set_overlay_pass_through(bar_ind, True)      # os filhos do botão não podem engolir o clique
        b.connect("toggled", lambda x, ind=bar_ind: ind.set_opacity(1.0 if x.get_active() else 0.0))
    (win.b_video if settings["mode"] == "video" else win.b_photo).set_active(True)
    put(left, win.b_photo, *M.PHOTO["tile"][:2], origin=o)
    put(left, win.b_video, *M.VIDEO["tile"][:2], origin=o)

    win.shape_btn, win.shape_img, ov = px_button(M.SHAPE["tile"], M.SHAPE["canvas"], "rect", tip="Modo de captura")
    ch = icons.role_image("chev", 20, "chev")
    _place(ch, M.SHAPE["tile"], M.SHAPE["chev"])
    ov.add_overlay(ch)
    ov.set_overlay_pass_through(ch, True)      # os filhos do botão não podem engolir o clique
    put(left, win.shape_btn, *M.SHAPE["tile"][:2], origin=o)

    win.delay_btn, win.delay_img, ov = px_button(M.DELAY["tile"], M.DELAY["canvas"], "timer0", tip="Atraso de captura")
    ch = icons.role_image("chev", 20, "chev")
    _place(ch, M.DELAY["tile"], M.DELAY["chev"])
    ov.add_overlay(ch)
    ov.set_overlay_pass_through(ch, True)      # os filhos do botão não podem engolir o clique
    put(left, win.delay_btn, *M.DELAY["tile"][:2], origin=o)

    win.btn_ocr_empty, _, _ = px_button(M.OCR["tile"], M.OCR["canvas"], "textscan", tip="Extrator de Texto")
    win.ocr_sep = separator(left, M.OCR_SEP_X, o)
    put(left, win.btn_ocr_empty, *M.OCR["tile"][:2], origin=o)
    win._ocr_widgets = (win.ocr_sep, win.btn_ocr_empty)
    win._left = left
    win._left_origin = o
    # posições base (estado com captura) para poder deslocar no estado vazio
    win._left_items = [(w_, x_, y_) for w_, (x_, y_) in (
        (win.b_photo, M.PHOTO["tile"][:2]), (win.b_video, M.VIDEO["tile"][:2]),
        (win.shape_btn, M.SHAPE["tile"][:2]), (win.delay_btn, M.DELAY["tile"][:2]))]
    bar.pack_start(left, False, False, 0)

    # ---- centro
    win.center = Gtk.Stack()
    win.center.set_halign(Gtk.Align.CENTER)
    win.center.set_homogeneous(False)
    co = (M.CENTER_X, M.TB_Y)
    edit = Gtk.Fixed()
    edit.set_size_request(M.CENTER_W, M.TB_H)
    win.edit_group = edit
    win.tool_btns = {}
    specs = (("pen", M.PEN, "Caneta"), ("hl", M.HL, "Marca-texto"), ("eraser", M.ERASER, "Borracha"), ("shape", M.SHAPES, "Formas"))
    names = {"pen": "pen", "hl": "hl", "eraser": "eraser", "shape": "shapes"}
    win.tool_imgs = {}
    for key, g, tip in specs:
        b, img, ov = px_button(g["tile"], g["canvas"], names[key], toggle=True, cls=("tool",), tip=tip)
        ch = icons.role_image("chev", 20, "chev")
        _place(ch, g["tile"], (g["tile"][0] + M.TOOL_CHEV_DX, g["tile"][1] + M.TOOL_CHEV_DY))
        ch.set_opacity(0.0)
        ov.add_overlay(ch)
        ov.set_overlay_pass_through(ch, True)      # os filhos do botão não podem engolir o clique
        b.connect("toggled", lambda x, c=ch: c.set_opacity(1.0 if x.get_active() else 0.0))
        b.connect("button-press-event", win.on_tool_press, key)
        put(edit, b, *g["tile"][:2], origin=co)
        win.tool_btns[key] = b
        win.tool_imgs[key] = img
    win.btn_pen, win.btn_hl = win.tool_btns["pen"], win.tool_btns["hl"]
    win.btn_eraser, win.btn_shape = win.tool_btns["eraser"], win.tool_btns["shape"]
    win.pen_img, win.hl_img = win.tool_imgs["pen"], win.tool_imgs["hl"]
    separator(edit, M.SEP1_X, co)
    win.btn_crop, _, _ = px_button(M.CROP["tile"], M.CROP["canvas"], "crop", toggle=True, tip="Corte de imagem")
    win.btn_crop.connect("clicked", lambda b: win.toggle_crop(b.get_active()))
    put(edit, win.btn_crop, *M.CROP["tile"][:2], origin=co)
    win.btn_text, _, _ = px_button(M.TEXT["tile"], M.TEXT["canvas"], "textscan", toggle=True, cls=("tool",), tip="Ações de texto")
    win.btn_text.connect("toggled", win.toggle_text_mode)
    put(edit, win.btn_text, *M.TEXT["tile"][:2], origin=co)
    separator(edit, M.SEP2_X, co)
    win.btn_undo, win.undo_img, _ = px_button(M.UNDO["tile"], M.UNDO["canvas"], "undo", tip="Desfazer (Ctrl+Z)")
    win.btn_redo, win.redo_img, _ = px_button(M.REDO["tile"], M.REDO["canvas"], "redo", tip="Refazer (Ctrl+Y)")
    win.btn_undo.connect("clicked", lambda *_: win.canvas.undo())
    win.btn_redo.connect("clicked", lambda *_: win.canvas.redo())
    put(edit, win.btn_undo, *M.UNDO["tile"][:2], origin=co)
    put(edit, win.btn_redo, *M.REDO["tile"][:2], origin=co)
    win.center.add_named(edit, "edit")

    crop = Gtk.Fixed()
    crop.set_size_request(M.CENTER_W, M.TB_H)
    win.crop_apply, win.crop_cancel = crop_bar.make_apply(), crop_bar.make_cancel()
    win.crop_apply.connect("clicked", lambda *_: win.toggle_crop(False, apply=True))
    win.crop_cancel.connect("clicked", lambda *_: win.toggle_crop(False, apply=False))
    put(crop, win.crop_apply, *crop_bar.APPLY_BOX[:2], origin=co)
    put(crop, win.crop_cancel, *crop_bar.CANCEL_BOX[:2], origin=co)
    win.crop_group = crop
    win.center.add_named(crop, "crop")
    win.center.add_named(Gtk.Box(), "none")
    bar.pack_start(win.center, True, True, 0)

    # ---- direita
    ro = (M.RIGHT_X, M.TB_Y)
    right = Gtk.Fixed()
    right.set_size_request(M.RIGHT_W, M.TB_H)
    win.right = right
    win.file_group = Gtk.Fixed()
    win.btn_ext, win.ext_img, _ = px_button(M.EXT["tile"], M.EXT["canvas"], "paint", tip="Editar em outro aplicativo")
    win.btn_save, _, _ = px_button(M.SAVE["tile"], M.SAVE["canvas"], "save", tip="Salvar como (Ctrl+S)")
    win.btn_copy, _, _ = px_button(M.COPY["tile"], M.COPY["canvas"], "copy", tip="Copiar (Ctrl+C)")
    win.btn_share, _, _ = px_button(M.SHARE["tile"], M.SHARE["canvas"], "share", tip="Compartilhar")
    win.btn_more, _, _ = px_button(M.MORE["tile"], M.MORE["canvas"], "more", tip="Mais")
    win.btn_ext.connect("clicked", lambda *_: win.edit_external())
    win.btn_save.connect("clicked", lambda *_: win.save_as())
    win.btn_copy.connect("clicked", lambda *_: win.copy_image())
    win.btn_share.connect("clicked", win.popup_share)
    win.btn_more.connect("clicked", win.popup_more)
    win.file_widgets = []
    for b, g in ((win.btn_ext, M.EXT), (win.btn_save, M.SAVE), (win.btn_copy, M.COPY), (win.btn_share, M.SHARE)):
        put(right, b, *g["tile"][:2], origin=ro)
        win.file_widgets.append(b)
    win.file_widgets.append(separator(right, M.SEP3_X, ro))
    put(right, win.btn_more, *M.MORE["tile"][:2], origin=ro)
    win.crop_zoom = crop_bar.make_zoom()
    win.crop_zoom.connect("clicked", win.popup_crop_zoom)
    win.crop_zoom.set_no_show_all(True)
    win.crop_zoom.hide()
    put(right, win.crop_zoom, *crop_bar.ZOOM_BOX[:2], origin=ro)
    bar.pack_end(right, False, False, 0)
    win.toolbar = bar
    return bar


def _place(img, tile, canvas):
    img.set_halign(Gtk.Align.START)
    img.set_valign(Gtk.Align.START)
    img.set_margin_start(canvas[0] - tile[0])
    img.set_margin_top(canvas[1] - tile[1])


# --------------------------------------------------------------------------- infobar
def build_infobar(win):
    """Cartão sobreposto ao conteúdo (974x120), com ícone, dois textos, link e botão de fechar."""
    rev = Gtk.Revealer()
    rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
    rev.set_halign(Gtk.Align.FILL)
    rev.set_valign(Gtk.Align.START)
    rev.set_margin_start(M.INFO_CARD[0])
    rev.set_margin_end(M.W - M.INFO_CARD[0] - M.INFO_CARD[2])
    rev.set_margin_top(M.INFO_CARD[1] - (M.LINE_Y + 1))
    frame = Gtk.Box()          # GtkOverlay não desenha o próprio fundo CSS; o Box sim
    frame.get_style_context().add_class("cap-infobar")
    card = Gtk.Overlay()
    frame.pack_start(card, True, True, 0)
    base = Gtk.Box()
    base.set_size_request(-1, M.INFO_CARD[3] - 2)
    card.add(base)
    cx, cy = M.INFO_CARD[0], M.INFO_CARD[1]

    def put_at(widget, x_abs, y_abs, end=False):
        widget.set_halign(Gtk.Align.END if end else Gtk.Align.START)
        widget.set_valign(Gtk.Align.START)
        if end:
            widget.set_margin_end(x_abs - 1)
        else:
            widget.set_margin_start(x_abs - cx - 1)       # -1: borda CSS do cartão
        widget.set_margin_top(int(round(y_abs - cy)) - 1 - (1 if widget.get_style_context().has_class("lbl") else 0))
        card.add_overlay(widget)

    ic = icons.role_image("info15", 20, "accent")
    put_at(ic, M.INFO_ICON[0] - 3, M.INFO_ICON[1] - 3)

    def label(text, cls, cy_abs):
        l = Gtk.Label(label=text, xalign=0)
        l.get_style_context().add_class(cls)
        l.get_style_context().add_class("lbl")
        l.set_size_request(-1, 20)
        put_at(l, M.INFO_TITLE_CX - 1, cy_abs - 10)
        return l
    win.info_title = label("As capturas de tela são salvas automaticamente na pasta Capturas de Tela", "info-title", M.INFO_TITLE_CY)
    win.info_desc = label("Você pode desativá-lo nas configurações do aplicativo.", "info-desc", M.INFO_DESC_CY)
    link = Gtk.Button()
    link.set_can_focus(False)
    link.get_style_context().add_class("link")
    link.add(Gtk.Label(label="Abrir as Configurações da Ferramenta de Captura", xalign=0))
    link.get_style_context().add_class("lbl")
    link.set_size_request(-1, 20)
    link.connect("clicked", lambda *_: win.show_page("settings"))
    put_at(link, M.INFO_TITLE_CX - 1, M.INFO_LINK_CY - 10)
    close, _, _ = px_button((0, 0, 32, 32), (6, 6), "close")
    close.connect("clicked", lambda *_: (rev.set_reveal_child(False), settings.__setitem__("infobar_dismissed", True)))
    # distância da borda direita do cartão até a borda direita do botão (32px, centrado em INFO_CLOSE_CENTER)
    right_gap = (cx + M.INFO_CARD[2]) - (M.INFO_CLOSE_CENTER[0] + 16)
    put_at(close, right_gap, M.INFO_CLOSE_CENTER[1] - 16, end=True)
    rev.add(frame)
    return rev


def layout_left(win, empty):
    """Estado vazio: botão "Novo" largo + grupo deslocado; extrator de texto depois do atraso."""
    o = win._left_origin
    dx = M.EMPTY_DX if empty else 0
    win.btn_new.set_size_request(M.EMPTY_NEW_W if empty else M.NEW["tile"][2], M.NEW["tile"][3])
    win.new_label.set_visible(empty)
    for w_, x_, y_ in win._left_items:
        win._left.move(w_, x_ + dx - o[0], y_ - o[1])
    # o ícone "+" fica no mesmo lugar nos dois estados; no vazio é cinza-azulado como no original
    win._left.move(win.ocr_sep, M.EMPTY_OCR_SEP_X - o[0], M.SEP_Y - o[1])
    win._left.move(win.btn_ocr_empty, M.EMPTY_OCR["tile"][0] - o[0], M.EMPTY_OCR["tile"][1] - o[1])
    ocr_img = win.btn_ocr_empty.get_child().get_children()[0] if False else None
