"""Janela principal: barra de ferramentas, editor, configurações."""
import os
import subprocess
import threading
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from . import APP_NAME, annot, chrome, icons, menus, metrics as M, services, textlayer, theme
from .text_bar import BAR_H, BAR_W, InfoTip, TextBar
from .canvas import Canvas
from .config import settings
from .emoji_picker import EmojiPicker
from .flyouts import ToolFlyout
from .shape_bar import ShapeBar, ShapeColorFlyout, BTN_Y
from .settings_page import SettingsPage

SHAPES = [("rectangle", "rect", "Retângulo"), ("window", "window", "Janela"),
          ("fullscreen", "fullscreen", "Tela inteira"), ("freeform", "freeform", "Forma livre")]
DELAYS = [(0, "timer0", "Sem atraso"), (3, "timer3", "3 segundos de atraso"),
          (5, "timer5", "5 segundos de atraso"), (10, "timer10", "10 segundos de atraso")]


def btn(icon=None, label=None, tip=None, cls=(), size=18, toggle=False):
    b = Gtk.ToggleButton() if toggle else Gtk.Button()
    sc = b.get_style_context()
    sc.add_class("tbtn")
    for c in cls:
        sc.add_class(c)
    b.set_can_focus(False)
    if tip:
        b.set_tooltip_text(tip)
    if icon or label:
        box = Gtk.Box(spacing=8)
        if icon:
            box.pack_start(icons.image(icon, size, theme.icon_color()), False, False, 0)
        if label:
            box.pack_start(Gtk.Label(label=label), False, False, 0)
        b.add(box)
    return b


def make_menu(parent, items, width=250):
    """items: (icon, rótulo, atalho, callback, enabled) | None (separador). Devolve Popover."""
    pop = Gtk.Popover.new(parent)
    pop.get_style_context().add_class("cap-pop")
    pop.set_position(Gtk.PositionType.BOTTOM)
    vb = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
    for m in (vb.set_margin_top, vb.set_margin_bottom, vb.set_margin_start, vb.set_margin_end):
        m(4)
    for it in items:
        if it is None:
            s = Gtk.Box()
            s.get_style_context().add_class("msep")
            vb.pack_start(s, False, False, 0)
            continue
        icon, label, accel, cb = it[:4]
        enabled = it[4] if len(it) > 4 else True
        b = Gtk.Button()
        b.get_style_context().add_class("tbtn")
        b.get_style_context().add_class("menuitem")
        row = Gtk.Box(spacing=12)
        if icon:
            row.pack_start(icons.image(icon, 18, theme.icon_color()), False, False, 0)
        lb = Gtk.Label(label=label, xalign=0)
        row.pack_start(lb, True, True, 0)
        if accel:
            al = Gtk.Label(label=accel, xalign=1)
            al.get_style_context().add_class("subtle")
            row.pack_end(al, False, False, 0)
        row.set_size_request(width, -1)
        b.add(row)
        b.set_sensitive(enabled)
        b.connect("clicked", lambda _b, cb=cb: (pop.popdown(), GLib.idle_add(cb)))
        vb.pack_start(b, False, False, 0)
    pop.add(vb)
    vb.show_all()
    return pop


class EditorWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.app = app
        self.set_default_size(M.W, M.H - M.TITLE_H)
        self.set_icon_name("captura")
        self.get_style_context().add_class("cap-window")
        self.saved_path = None
        self.source_name = None
        self._copy_timer = 0
        self.tool = None
        self.is_new_capture = False

        self.set_titlebar(chrome.build_header(self))

        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(root)
        self.stack = Gtk.Stack()
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(180)
        root.pack_start(self.stack, True, True, 0)

        main = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.stack.add_named(main, "main")
        self.settings_page = SettingsPage(lambda: self.show_page("main"), self.app.apply_theme)
        self.stack.add_named(self.settings_page, "settings")

        main.pack_start(self.build_toolbar(), False, False, 0)
        line = Gtk.Box()
        line.get_style_context().add_class("tbline")
        line.set_size_request(-1, 1)
        main.pack_start(line, False, False, 0)
        self.infobar = self.build_infobar()
        self.canvas_stack = Gtk.Stack()
        self.toast_overlay = Gtk.Overlay()
        self.toast_overlay.add(self.canvas_stack)
        # a barra de Formas fica sob o aviso (como na referência, onde o aviso a oculta)
        self.shape_bar = ShapeBar(self.popup_emoji_picker, self.on_shape_kind, self.popup_fill_flyout, self.popup_outline_flyout)
        self.shape_bar.set_margin_top(M.SHAPEBAR_TOP)
        self.shape_bar.set_no_show_all(True)
        self.toast_overlay.add_overlay(self.shape_bar)
        self.toast_overlay.add_overlay(self.infobar)
        self.toast_rev = Gtk.Revealer()
        self.toast_rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_UP)
        self.toast_rev.set_halign(Gtk.Align.CENTER)
        self.toast_rev.set_valign(Gtk.Align.END)
        self.toast_rev.set_margin_bottom(24)
        tbox = Gtk.Box()
        tbox.get_style_context().add_class("toast")
        self.toast_lbl = Gtk.Label()
        tbox.pack_start(self.toast_lbl, False, False, 0)
        self.toast_rev.add(tbox)
        self.toast_overlay.add_overlay(self.toast_rev)
        self.toast_overlay.set_overlay_pass_through(self.toast_rev, True)
        self.toast_overlay.add_overlay(self.build_text_bar())
        self.toast_overlay.add_overlay(self.infotip)
        self.toast_overlay.set_overlay_pass_through(self.infotip, True)
        self._toast_id = 0
        main.pack_start(self.toast_overlay, True, True, 0)
        self.canvas = Canvas()
        self.canvas.on_text_context = self.popup_text_context
        for name in ("pen", "hl", "shape"):
            self.canvas.opts[name] = (settings[f"{name}_color"], settings[f"{name}_size"])
        self.canvas.opts["shape_kind"] = settings["shape_kind"]
        self.canvas.opts["shape_fill"] = settings["shape_fill"]
        self.canvas.opts["shape_alpha"] = settings["shape_alpha"]
        self.canvas.opts["shape_fill_alpha"] = settings["shape_fill_alpha"]
        self.canvas.connect("tool-changed", self.sync_shape_bar)
        self.canvas.connect("changed", self.on_canvas_changed)
        self.canvas_stack.add_named(self.canvas, "canvas")
        self.empty = self.build_empty()
        self.canvas_stack.add_named(self.empty, "empty")
        self.canvas_stack.set_visible_child_name("empty")

        self.connect("delete-event", self.on_delete)
        self.connect("destroy", self._close_popups)
        self.connect("key-press-event", self.on_key)
        self.refresh_state()
        root.show_all()
        self.infobar.set_reveal_child(False)
        self.canvas_stack.set_visible_child_name("empty")
        self.update_edit_group()
        self.set_title(APP_NAME)
        self.resize(M.W, M.H - M.TITLE_H)

    # --------------------------------------------------------------- UI
    def build_toolbar(self):
        bar = chrome.build_toolbar(self, SHAPES, DELAYS)
        self.refresh_capture_icons()
        self.refresh_tool_icons()
        self.btn_hl.connect("toggled", lambda *_: self.refresh_tool_icons())
        return bar

    def build_infobar(self):
        return chrome.build_infobar(self)

    def build_empty(self):
        l = Gtk.Label()
        l.set_markup("Pressione <b>⊞</b> + <b>Shift</b> + <b>S</b> para iniciar uma captura")
        l.get_style_context().add_class("empty-text")
        l.set_valign(Gtk.Align.CENTER)
        l.set_halign(Gtk.Align.CENTER)
        l.set_margin_bottom(61)      # o original centraliza o texto acima de uma faixa inferior de 29 px
        bg = Gtk.EventBox()
        bg.get_style_context().add_class("cap-canvas-bg")
        bg.add(l)
        return bg

    # --------------------------------------------------------------- estado
    def app_tool_for_new(self):
        return "snip"

    def set_mode(self, mode):
        settings["mode"] = mode
        for b, m in ((self.b_photo, "photo"), (self.b_video, "video")):
            if b.get_active() != (m == mode):
                b.set_active(m == mode)

    def refresh_capture_icons(self):
        name = [i for k, i, _ in SHAPES if k == settings["shape"]][0]
        icons.set_role(self.shape_img, name=name)
        d = [i for k, i, _ in DELAYS if k == settings["delay"]][0]
        icons.set_role(self.delay_img, name=d)

    def refresh_tool_icons(self):
        pal = theme.palette()
        pc, _ = self.canvas_opts("pen")
        hc, _ = self.canvas_opts("hl")
        self.pen_img.set_from_pixbuf(icons.tool_pixbuf("pen", pc, pal["text"], 20, pal["bg0"]))
        self.hl_img.set_from_pixbuf(icons.tool_pixbuf("highlighter", hc, pal["text"], 20, pal["tile_on"] if self.btn_hl.get_active() else pal["bg0"]))

    def canvas_opts(self, k):
        c = getattr(self, "canvas", None)
        if c is not None:
            return c.opts[k]
        return {"pen": (settings["pen_color"], settings["pen_size"]), "hl": (settings["hl_color"], settings["hl_size"]),
                "shape": (settings["shape_color"], settings["shape_size"])}[k]

    def retheme(self):
        """Reconstrói ícones depois de trocar o tema."""
        self.refresh_capture_icons()
        self.refresh_tool_icons()
        self.canvas.queue_draw()

    def update_edit_group(self):
        has = self.canvas.base is not None
        cropping = self.canvas.tool == "crop"
        self.center.set_visible_child_name("crop" if has and cropping else "edit" if has else "none")
        for w_ in self._ocr_widgets:
            w_.set_visible(not has)
        chrome.layout_left(self, not has)
        for w_ in self.file_widgets:
            w_.set_visible(has and not cropping)
        self.btn_more.set_visible(not cropping)
        self.crop_zoom.set_visible(cropping)
        # no corte, o grupo da esquerda some (mas mantém o espaço, para o centro não se mover)
        self._left.set_opacity(0 if cropping else 1)
        self._left.set_sensitive(not cropping)
        self.btn_undo.set_sensitive(bool(self.canvas.undo_stack))
        self.btn_redo.set_sensitive(bool(self.canvas.redo_stack))
        icons.set_role(self.undo_img, role="text" if self.canvas.undo_stack else "disabled")
        icons.set_role(self.redo_img, role="text" if self.canvas.redo_stack else "disabled")
        ed, lab = services.external_editor()
        self.btn_ext.set_tooltip_text(f"Editar no {lab}" if lab else "Abrir com…")

    def refresh_state(self):
        pass

    def on_canvas_changed(self, *a):
        self.update_edit_group()
        self.sync_shape_bar()
        if self.canvas.base is not None and settings["shot_autocopy_edits"] and self.canvas.dirty:
            if self._copy_timer:
                GLib.source_remove(self._copy_timer)
            self._copy_timer = GLib.timeout_add(500, self._autocopy)

    def _autocopy(self):
        self._copy_timer = 0
        if self.canvas.base is not None:
            services.copy_surface(self.canvas.rendered())
        return False

    def show_toast(self, text, ms=2200):
        self.toast_lbl.set_text(text)
        self.toast_rev.show_all()
        self.toast_rev.set_reveal_child(True)
        if self._toast_id:
            GLib.source_remove(self._toast_id)
        self._toast_id = GLib.timeout_add(ms, self._hide_toast)

    def _hide_toast(self):
        self._toast_id = 0
        self.toast_rev.set_reveal_child(False)
        return False

    def show_page(self, name):
        self.stack.set_visible_child_name(name)

    # --------------------------------------------------------------- imagem
    def load_surface(self, surface, name=None, new_capture=False, path=None):
        self.canvas.set_image(surface)
        self.canvas_stack.set_visible_child_name("canvas")
        self.saved_path = path
        self.source_name = name
        self.is_new_capture = new_capture
        self.show_page("main")
        show = new_capture and settings["shot_autosave"] and not settings["infobar_dismissed"]
        self.infobar.set_reveal_child(bool(show))
        self.title_label.set_text(APP_NAME)
        self.canvas.set_tool(None)
        self.uncheck_tools()
        self.update_edit_group()
        self.present()

    def load_pixbuf(self, pb, **kw):
        surf = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
        cr = cairo.Context(surf)
        Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
        cr.paint()
        self.load_surface(surf, **kw)

    def open_file(self, path):
        try:
            pb = GdkPixbuf.Pixbuf.new_from_file(path)
            pb = pb.apply_embedded_orientation() or pb
        except Exception as e:
            self.error_dialog("Não foi possível abrir o arquivo", str(e))
            return
        self.load_pixbuf(pb, name=os.path.basename(path), path=path)

    # --------------------------------------------------------------- ferramentas
    def uncheck_tools(self):
        for b in self.tool_btns.values():
            if b.get_active():
                b.set_active(False)
        self.btn_crop.set_active(False) if self.btn_crop.get_active() else None

    def on_tool_press(self, b, ev, name):
        if ev.button != 1:
            return False
        if self.canvas.base is None:
            return True
        if self.canvas.tool == name:
            if name == "eraser":
                self.popup_eraser_menu(b)
            elif name != "shape":          # Formas: a barra já está no conteúdo
                self.popup_flyout(b, name)
            return True
        self.select_tool(name)
        return True

    def select_tool(self, name):
        if self.btn_text.get_active():
            self.btn_text.set_active(False)
        for k, tb in self.tool_btns.items():
            tb.set_active(k == name)
        if self.btn_crop.get_active():
            self.btn_crop.set_active(False)
        self.canvas.set_tool(name)

    def popup_flyout(self, b, name):
        if name == "pen":
            col, sz = self.canvas.opts["pen"]
            fl = ToolFlyout(b, "pen", col, sz, lambda c, s: self.set_tool_opts("pen", c, s))
        elif name == "hl":
            col, sz = self.canvas.opts["hl"]
            fl = ToolFlyout(b, "hl", col, sz, lambda c, s: self.set_tool_opts("hl", c, s))
        else:
            return
        old = getattr(self, "_tool_pop", None)
        if old:
            old.destroy()
        self._tool_pop = fl
        fl.popup()

    def _close_popups(self, *_):
        """Fecha menus/flyouts abertos: um popup com grab não pode sobreviver à janela dona."""
        for name in ("_cur_menu", "_emoji_picker", "_tool_pop"):
            pop = getattr(self, name, None)
            if pop is None:
                continue
            try:
                pop.close_popup() if hasattr(pop, "close_popup") else pop.destroy()
            except Exception:
                pass

    # ------------------------------------------------- barra de Formas (no conteúdo)
    def _bar_top(self):
        """y de tela da borda superior da barra de Formas."""
        return menus.anchor_origin(self.shape_bar.emoji_btn)[1] - BTN_Y

    def popup_emoji_picker(self, anchor):
        old = getattr(self, "_emoji_picker", None)
        if old is not None:
            old.close_popup()
        picker = EmojiPicker(self.insert_emoji)
        self._emoji_picker = picker
        x, _ = menus.anchor_origin(anchor)
        picker.popup(self._bar_top(), x + anchor.get_allocated_width() / 2)

    def insert_emoji(self, char):
        self.canvas.add_emoji(char)
        self.canvas.grab_focus()

    def popup_fill_flyout(self, anchor):
        self._color_flyout(anchor, "fill")

    def popup_outline_flyout(self, anchor):
        self._color_flyout(anchor, "outline")

    def _color_flyout(self, anchor, mode):
        old = getattr(self, "_tool_pop", None)
        if old:
            old.destroy()
        st = self.shape_style()
        if mode == "fill":
            fl = ShapeColorFlyout(anchor, "fill", st["fill"], st["fill_alpha"], st["size"],
                                  lambda c, a, sz: self.apply_shape_style(fill=c, fill_alpha=a))
        else:
            fl = ShapeColorFlyout(anchor, "outline", st["color"], st["alpha"], st["size"],
                                  lambda c, a, sz: self.apply_shape_style(color=c, alpha=a, size=sz))
        self._style_session = object()
        self._tool_pop = fl
        fl.popup()

    def on_shape_kind(self, kind):
        self.apply_shape_style(kind=kind)

    def shape_style(self):
        """Estilo atual: da forma selecionada, se houver; senão das opções da ferramenta."""
        o = self.canvas.opts
        sel = self.canvas.sel
        if sel is not None and sel.kind == "shape":
            return dict(kind=sel.shape, color=sel.color, alpha=sel.alpha, size=sel.size, fill=sel.fill, fill_alpha=sel.fill_alpha)
        return dict(kind=o["shape_kind"], color=o["shape"][0], alpha=o.get("shape_alpha", 1.0), size=o["shape"][1],
                    fill=o.get("shape_fill"), fill_alpha=o.get("shape_fill_alpha", 1.0))

    def apply_shape_style(self, **changes):
        """Atualiza opções da ferramenta (e a forma selecionada, de forma desfazível e agrupada por flyout)."""
        st = self.shape_style()
        st.update(changes)
        o = self.canvas.opts
        o["shape"] = (st["color"], st["size"])
        o["shape_kind"], o["shape_alpha"] = st["kind"], st["alpha"]
        o["shape_fill"], o["shape_fill_alpha"] = st["fill"], st["fill_alpha"]
        for key, val in (("shape_color", st["color"]), ("shape_size", st["size"]), ("shape_kind", st["kind"]),
                         ("shape_alpha", st["alpha"]), ("shape_fill", st["fill"]), ("shape_fill_alpha", st["fill_alpha"])):
            settings[key] = val
        sel = self.canvas.sel
        if sel is not None and sel.kind == "shape":
            token = (getattr(self, "_style_session", None), id(sel))
            if getattr(self, "_style_undo_token", None) != token or changes.keys() == {"kind"}:
                self.canvas.push_undo()
                self._style_undo_token = token
            sel.shape, sel.color, sel.alpha, sel.size = st["kind"], st["color"], st["alpha"], st["size"]
            sel.fill, sel.fill_alpha = st["fill"], st["fill_alpha"]
            self.canvas.emit("changed")
        self.shape_bar.set_kind(st["kind"])
        self.shape_bar.set_style(st["fill"], st["color"])
        self.canvas.queue_draw()
        self.refresh_tool_icons()

    def sync_shape_bar(self, *a):
        show = self.canvas.base is not None and self.canvas.tool == "shape"
        self.shape_bar.set_visible(show)
        if show:
            st = self.shape_style()
            self.shape_bar.set_kind(st["kind"])
            self.shape_bar.set_style(st["fill"], st["color"])

    def set_tool_opts(self, name, color, size, shape_kind=None):
        self.canvas.opts[name] = (color, size)
        settings[f"{name}_color"] = color
        settings[f"{name}_size"] = size
        if shape_kind:
            self.canvas.opts["shape_kind"] = shape_kind
            settings["shape_kind"] = shape_kind
        if self.canvas.sel is not None and name == "shape":
            self.canvas.sel.color, self.canvas.sel.size = color, size
            if shape_kind:
                self.canvas.sel.shape = shape_kind
            self.canvas.queue_draw()
        self.refresh_tool_icons()

    def toggle_crop(self, on, apply=False):
        if on:
            if self.btn_text.get_active():
                self.btn_text.set_active(False)
            for tb in self.tool_btns.values():
                tb.set_active(False)
            self.canvas.set_tool("crop")
        else:
            if apply:
                self.canvas.apply_crop()
            self.canvas.set_tool(None)
            if self.btn_crop.get_active():
                self.btn_crop.set_active(False)
        self.canvas.update_scale()
        self.update_edit_group()
        self.canvas.queue_draw()

    # --------------------------------------------------------------- menus
    def _menu(self, items, style, left=None, right=None, top=None):
        """Abre o menu com o canto superior esquerdo da caixa em (left, top) relativos à janela (conteúdo)."""
        old = getattr(self, "_cur_menu", None)
        if old is not None:
            old.close_popup()
        m = menus.Menu(items, style)
        self._cur_menu = m
        if right is not None:
            # `right` uses reference-window coordinates; follow the real right edge.
            right += self.toolbar.get_allocated_width() - M.W
            left = right - (style["width"] + 2)
        ox, oy = menus.anchor_origin(self.toolbar)
        # a faixa começa em y=32 da janela; `top` é dado em coordenadas da janela
        m.open_at(ox + left, oy + (top - M.TB_Y))
        return m

    def _menu_at(self, items, style, x, y):
        """Abre o menu com o canto superior esquerdo da caixa em coordenadas de tela."""
        old = getattr(self, "_cur_menu", None)
        if old is not None:
            old.close_popup()
        m = menus.Menu(items, style)
        self._cur_menu = m
        m.open_at(x, y)
        return m

    def popup_shape_menu(self, b):
        cur = settings["shape"]
        items = [(i, l, None, (lambda k=k: self.set_shape(k)), True, False, k == cur) for k, i, l in SHAPES]
        idx = [k for k, _, _ in SHAPES].index(cur)
        left, _ = b.translate_coordinates(self.toolbar, 0, 0)
        self._menu(items, menus.SHAPE, left=left - 5, top=32 - idx * menus.SHAPE["row_h"])

    def set_shape(self, k):
        settings["shape"] = k
        self.refresh_capture_icons()

    def popup_delay_menu(self, b):
        cur = settings["delay"]
        items = [(i, l, None, (lambda d=d: self.set_delay(d)), True, False, d == cur) for d, i, l in DELAYS]
        idx = [d for d, _, _ in DELAYS].index(cur)
        left, _ = b.translate_coordinates(self.toolbar, 0, 0)
        self._menu(items, menus.CHOICE, left=left - 4, top=32 - idx * menus.CHOICE["row_h"])

    def set_delay(self, d):
        settings["delay"] = d
        self.refresh_capture_icons()

    def popup_share(self, b):
        self._menu([("share_mail", "Enviar por e-mail", None, self.share_mail),
                    ("copytext", "Copiar caminho do arquivo", None, self.copy_path),
                    ("openwith", "Abrir com…", None, self.open_with)], menus.MORE, right=M.W, top=78)

    # ------------------------------------------------------- ações de texto
    def build_text_bar(self):
        bar = TextBar(self.copy_all_text, lambda: None, self.quick_redact, self.popup_redact_menu)
        bar.set_margin_top(M.SHAPEBAR_TOP)
        bar.set_no_show_all(True)
        bar.hide()
        self.text_bar = bar
        self.btn_copy_all, self.btn_table = bar.btn_copy_all, bar.btn_table
        self.btn_redact, self.btn_chev = bar.btn_redact, bar.btn_chev
        tip = InfoTip("Certifique-se de que todas as informações confidenciais foram editadas.")
        tip.set_halign(Gtk.Align.START)
        tip.set_valign(Gtk.Align.START)
        tip.set_no_show_all(True)
        tip.hide()
        self.infotip = tip
        self._tip_id = 0
        return bar

    def show_redact_tip(self):
        total = self.toast_overlay.get_allocated_width()
        if total <= 1:
            return
        self.infotip.set_margin_start((total - BAR_W) // 2 + 276)       # a barra é centrada; o balão aponta para a Redação rápida
        self.infotip.set_margin_top(M.SHAPEBAR_TOP + BAR_H + 1)
        self.infotip.show()
        if self._tip_id:
            GLib.source_remove(self._tip_id)
        self._tip_id = GLib.timeout_add(6000, self._hide_tip)

    def _hide_tip(self):
        self._tip_id = 0
        self.infotip.hide()
        return False

    def toggle_text_mode(self, btn):
        if not btn.get_active():
            if self.canvas.tool == "text":
                self.canvas.set_tool(None)
            self.text_bar.hide()
            self._hide_tip()
            return
        s = self.current_surface()
        if s is None:
            btn.set_active(False)
            return
        if self.btn_crop.get_active():
            self.btn_crop.set_active(False)
        for tb in self.tool_btns.values():
            tb.set_active(False)
        self._text_job = job = object()

        def work():
            try:
                words = textlayer.ocr_surface(s)
                err = None
            except Exception as e:
                words, err = [], str(e)
            GLib.idle_add(done, words, err)

        def done(words, err):
            if self._text_job is not job or not self.btn_text.get_active():
                return False
            if err or not words:
                self.btn_text.set_active(False)
                self.show_toast("Falha ao reconhecer o texto" if err else "Nenhum texto foi encontrado na imagem")
                return False
            self.canvas.set_tool("text")
            self.canvas.set_text_words(words)
            self.text_bar.show()
            self.text_bar.show_all()
            return False
        if not services.ocr_available():
            btn.set_active(False)
            self.app.run_ocr(services.surface_to_pixbuf(s), self)      # mostra a orientação de instalação
            return
        threading.Thread(target=work, daemon=True).start()

    def copy_all_text(self):
        text = textlayer.words_text(self.canvas.text_words)
        if text:
            services.copy_text(text)

    def copy_selected_text(self):
        text = self.canvas.selected_text()
        if text:
            services.copy_text(text)
            return True
        return False

    def redact_kinds(self):
        return tuple(k for k, key in (("email", "redact_emails"), ("phone", "redact_phones")) if settings[key])

    def hide_sensitive(self, kinds=None):
        kinds = self.redact_kinds() if kinds is None else kinds
        found = textlayer.sensitive(self.canvas.text_words)
        words = [w for k in kinds for w in found.get(k, [])]
        n = self.canvas.redact(words)
        return n

    def quick_redact(self):
        self.hide_sensitive()
        self.show_redact_tip()

    def redact_selected_text(self):
        n = self.canvas.redact_selection()
        if n:
            self.canvas.text_sel = []
            self.canvas.queue_draw()
        return n

    def remove_redactions(self):
        self.canvas.remove_redactions()

    def toggle_redact_kind(self, key):
        settings[key] = not settings[key]

    def popup_redact_menu(self, b):
        items = [("checksm" if settings["redact_emails"] else None, "Endereços de email", None,
                  lambda: self.toggle_redact_kind("redact_emails")),
                 ("checksm" if settings["redact_phones"] else None, "Números de telefone", None,
                  lambda: self.toggle_redact_kind("redact_phones")),
                 None,
                 (None, "Remover todas as redações", None, self.remove_redactions, self.canvas.has_redactions())]
        bx, by = menus.anchor_origin(self.text_bar)
        self._menu_at(items, menus.TEXTCHK, bx + BAR_W - menus.TEXTCHK["width"] - 2 - 4, by + BAR_H + 1)

    def popup_text_context(self, x_root, y_root):
        has = bool(self.canvas.text_sel)
        items = [("copy", "Copiar texto", "Ctrl+C", self.copy_selected_text, has),
                 ("selall", "Selecionar tudo", "Ctrl+A", self.canvas.select_all_text),
                 None,
                 ("redact", "Redigir texto", "Ctrl+R", self.redact_selected_text, has)]
        self._menu_at(items, menus.TEXTCTX, x_root, y_root)

    def popup_eraser_menu(self, b):
        self._menu([("trash", "Apagar todas as marcações", None, self.canvas.clear_markup)],
                   menus.SINGLE, left=337, top=80)

    def popup_more(self, b):
        has = self.canvas.base is not None
        items = [
            ("zoom", "Zoom", None, self.popup_zoom, has, True),
            ("ruler", "Mostrar régua", "Ctrl+R", self.toggle_ruler, has),
            ("visualsearch", "Pesquisa visual com o Bing", None, self.visual_search, has),
            ("folder_open", "Abrir arquivo", "Ctrl+O", self.open_dialog),
            ("folder_shots", "Abrir a pasta de capturas de tela", None, self.open_folder),
            ("print", "Imprimir", "Ctrl+P", self.print_image, has),
            ("gear", "Configurações", None, lambda: self.show_page("settings")),
        ]
        m = self._menu(items, menus.MORE, right=M.W, top=78)
        gw = m.get_window()
        if gw is not None:
            _, wx, wy = gw.get_origin()
            self._more_geom = (wx + menus.SHADOW, wy + menus.SHADOW, m.frame.get_preferred_width()[1])

    # -------------------------------------------------------------- zoom
    def zoom_items(self):
        return [(None, "100%", "Ctrl+0", self.zoom_actual),
                (None, "Aplicar zoom", "Ctrl++", self.zoom_in),
                (None, "Reduzir", "Ctrl+-", self.zoom_out, self.can_zoom_out()),
                (None, "Ajustar à janela", "Ctrl+1", self.zoom_fit)]

    def can_zoom_out(self):
        return not self.canvas.fit

    def zoom_in(self):
        self.canvas.zoom_by(1.25)

    def zoom_out(self):
        if self.can_zoom_out():
            self.canvas.zoom_by(0.8)

    def zoom_fit(self):
        self.canvas.set_zoom(1.0, fit=True)
        self.canvas.update_scale()

    def zoom_actual(self):
        self.canvas.set_zoom(1.0)

    def popup_zoom(self):
        """Submenu de Zoom do menu Mais: à direita do menu principal, 5 px mais baixo (medido)."""
        x, y, w = getattr(self, "_more_geom", (None, None, None))
        if x is None:
            return
        GLib.idle_add(lambda: (self._menu_at(self.zoom_items(), menus.ZOOM, x + w - 1, y + 5), False)[1])

    def popup_crop_zoom(self, anchor):
        """Zoom do modo de corte: centrado no botão, topo 44 px abaixo do topo dele."""
        ax, ay = menus.anchor_origin(anchor)
        self._menu_at(self.zoom_items(), menus.ZOOM, ax + anchor.get_allocated_width() / 2 - (menus.ZOOM["width"] + 2) / 2, ay + 44)

    def toggle_ruler(self):
        self.canvas.show_ruler = not getattr(self.canvas, "show_ruler", False)
        self.canvas.queue_draw()

    def visual_search(self):
        self.app.msg(self, "Pesquisa visual", "A pesquisa visual envia a imagem a um serviço da web. Salve a captura e use o serviço de sua escolha.")

    # --------------------------------------------------------------- ações
    def current_surface(self):
        border = (settings["shot_border_color"], settings["shot_border_width"]) if settings["shot_border"] and self.is_new_capture else None
        return self.canvas.rendered(border) if self.canvas.base is not None else None

    def copy_image(self):
        s = self.current_surface()
        if s:
            services.copy_surface(s)
            self.app.toast_in_window("Copiado para a área de transferência")

    def save_as(self):
        """Return True only after a successful write; cancellation must not discard edits."""
        s = self.current_surface()
        if s is None:
            return False
        dlg = Gtk.FileChooserDialog(title="Salvar como", transient_for=self, action=Gtk.FileChooserAction.SAVE)
        saved = False
        try:
            dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.OK)
            dlg.set_do_overwrite_confirmation(True)
            d = settings.shot_directory
            os.makedirs(d, exist_ok=True)
            dlg.set_current_folder(d)
            dlg.set_current_name(services.timestamp_name())
            for label, pats in (("PNG (*.png)", ["*.png"]), ("JPEG (*.jpg, *.jpeg)", ["*.jpg", "*.jpeg"]), ("BMP (*.bmp)", ["*.bmp"])):
                f = Gtk.FileFilter()
                f.set_name(label)
                for pattern in pats:
                    f.add_pattern(pattern)
                dlg.add_filter(f)
            if dlg.run() != Gtk.ResponseType.OK:
                return False
            path = dlg.get_filename()
            if not path:
                return False
            if not os.path.splitext(path)[1]:
                path += ".png"
            services.save_surface(s, path)
            self.saved_path = path
            self.canvas.dirty = False
            saved = True
            self.app.toast_in_window("Salvo em " + path)
        except Exception as e:
            self.error_dialog("Não foi possível salvar", str(e))
        finally:
            dlg.destroy()
        return saved

    def ensure_file(self):
        """Arquivo temporário/salvo com a versão atual (para e-mail, abrir com…)."""
        s = self.current_surface()
        if s is None:
            return None
        import tempfile
        d = tempfile.mkdtemp(prefix="captura-")
        p = os.path.join(d, services.timestamp_name())
        services.save_surface(s, p)
        return p

    def edit_external(self):
        p = self.ensure_file()
        if not p:
            return
        cmd, _ = services.external_editor()
        if cmd:
            subprocess.Popen([cmd, p])
        else:
            self.open_with(p)

    def open_with(self, path=None):
        p = path if isinstance(path, str) else self.ensure_file()
        if not p:
            return
        dlg = Gtk.AppChooserDialog.new_for_content_type(self, 0, "image/png")
        if dlg.run() == Gtk.ResponseType.OK:
            info = dlg.get_app_info()
            if info:
                from gi.repository import Gio
                info.launch([Gio.File.new_for_path(p)], None)
        dlg.destroy()

    def share_mail(self):
        p = self.ensure_file()
        if p:
            subprocess.Popen(["xdg-email", "--attach", p, "--subject", "Captura de tela"])

    def copy_path(self):
        p = self.saved_path or self.ensure_file()
        if p:
            services.copy_text(p)
            self.app.toast_in_window("Caminho copiado")

    def open_folder(self):
        d = settings.shot_directory
        os.makedirs(d, exist_ok=True)
        subprocess.Popen(["xdg-open", d])

    def open_dialog(self):
        dlg = Gtk.FileChooserDialog(title="Abrir arquivo", parent=self, action=Gtk.FileChooserAction.OPEN)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Abrir", Gtk.ResponseType.OK)
        f = Gtk.FileFilter()
        f.set_name("Imagens")
        f.add_pixbuf_formats()
        dlg.add_filter(f)
        dlg.set_current_folder(settings.shot_directory) if os.path.isdir(settings.shot_directory) else None
        if dlg.run() == Gtk.ResponseType.OK:
            self.open_file(dlg.get_filename())
        dlg.destroy()

    def print_image(self):
        s = self.current_surface()
        if s is None:
            return
        op = Gtk.PrintOperation()
        op.set_n_pages(1)
        op.set_job_name("Captura de tela")

        def draw(op, ctx, n):
            cr = ctx.get_cairo_context()
            pw, ph = ctx.get_width(), ctx.get_height()
            sc = min(pw / s.get_width(), ph / s.get_height(), 1.0)
            cr.scale(sc, sc)
            cr.set_source_surface(s, 0, 0)
            cr.paint()
        op.connect("draw-page", draw)
        op.run(Gtk.PrintOperationAction.PRINT_DIALOG, self)

    def error_dialog(self, title, text):
        d = Gtk.MessageDialog(parent=self, flags=0, message_type=Gtk.MessageType.ERROR, buttons=Gtk.ButtonsType.CLOSE, text=title)
        d.format_secondary_text(text)
        d.run()
        d.destroy()

    # --------------------------------------------------------------- teclado / fechar
    def on_key(self, w, ev):
        ctrl = ev.state & Gdk.ModifierType.CONTROL_MASK
        shift = ev.state & Gdk.ModifierType.SHIFT_MASK
        k = ev.keyval
        if ctrl and k in (Gdk.KEY_s, Gdk.KEY_S):
            self.save_as(); return True
        if self.canvas.tool == "text" and ctrl and k in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_selected_text(); return True
        if self.canvas.tool == "text" and ctrl and k in (Gdk.KEY_a, Gdk.KEY_A):
            self.canvas.select_all_text(); return True
        if ctrl and k in (Gdk.KEY_r, Gdk.KEY_R):
            if self.canvas.tool == "text":
                self.redact_selected_text()
            elif self.canvas.base is not None:
                self.toggle_ruler()
            return True
        if ctrl and k in (Gdk.KEY_c, Gdk.KEY_C) and self.canvas.base is not None and not self.is_text_focus():
            self.copy_image(); return True
        if ctrl and k in (Gdk.KEY_z, Gdk.KEY_Z) and not shift:
            self.canvas.undo(); return True
        if ctrl and (k in (Gdk.KEY_y, Gdk.KEY_Y) or (shift and k in (Gdk.KEY_z, Gdk.KEY_Z))):
            self.canvas.redo(); return True
        if ctrl and k in (Gdk.KEY_o, Gdk.KEY_O):
            self.open_dialog(); return True
        if ctrl and k in (Gdk.KEY_p, Gdk.KEY_P):
            self.print_image(); return True
        if ctrl and k in (Gdk.KEY_plus, Gdk.KEY_equal, Gdk.KEY_KP_Add):
            self.zoom_in(); return True
        if ctrl and k in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.zoom_out(); return True
        if ctrl and k in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.zoom_actual(); return True
        if ctrl and k in (Gdk.KEY_1, Gdk.KEY_KP_1):
            self.zoom_fit(); return True
        if ctrl and k in (Gdk.KEY_n, Gdk.KEY_N):
            self.btn_new.clicked(); return True
        if k == Gdk.KEY_Escape:
            if self.canvas.tool == "text":
                self.btn_text.set_active(False); return True
            if self.canvas.tool == "crop":
                self.toggle_crop(False, apply=False); return True
            if self.stack.get_visible_child_name() == "settings":
                self.show_page("main"); return True
        if k in (Gdk.KEY_Return, Gdk.KEY_KP_Enter) and self.canvas.tool == "crop":
            self.toggle_crop(False, apply=True); return True
        return False

    def is_text_focus(self):
        f = self.get_focus()
        return isinstance(f, (Gtk.Entry, Gtk.TextView))

    def on_delete(self, w, ev):
        if self.canvas.base is not None and self.canvas.dirty and settings["shot_ask_save_edited"]:
            d = Gtk.MessageDialog(transient_for=self, flags=0, message_type=Gtk.MessageType.QUESTION, text="Salvar alterações na captura de tela?")
            d.format_secondary_text("Suas edições serão perdidas se você não salvar.")
            d.add_buttons("Não salvar", Gtk.ResponseType.NO, "Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.YES)
            r = d.run()
            d.destroy()
            if r == Gtk.ResponseType.CANCEL or r == Gtk.ResponseType.DELETE_EVENT:
                return True
            if r == Gtk.ResponseType.YES:
                return not self.save_as()
        return False
