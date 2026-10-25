"""Janela principal: barra de ferramentas, editor, configurações."""
import os
import subprocess
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
from gi.repository import Gtk, Gdk, GLib, GdkPixbuf

from . import APP_NAME, annot, icons, services, theme
from .canvas import Canvas
from .config import settings
from .flyouts import ToolFlyout
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
            s.set_size_request(-1, 1)
            s.get_style_context().add_class("sep")
            s.set_margin_top(3); s.set_margin_bottom(3)
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
        self.set_default_size(1000, 640)
        self.set_icon_name("captura")
        self.get_style_context().add_class("cap-window")
        self.saved_path = None
        self.source_name = None
        self._copy_timer = 0
        self.tool = None
        self.is_new_capture = False

        hb = Gtk.HeaderBar()
        hb.get_style_context().add_class("cap-header")
        hb.set_show_close_button(True)
        title = Gtk.Box(spacing=8)
        title.pack_start(icons.image("camera", 16, theme.icon_color()), False, False, 0)
        self.title_label = Gtk.Label(label=APP_NAME)
        self.title_label.get_style_context().add_class("title")
        title.pack_start(self.title_label, False, False, 0)
        hb.set_custom_title(title)
        self.set_titlebar(hb)
        hb.show_all()

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
        self.infobar = self.build_infobar()
        main.pack_start(self.infobar, False, False, 0)
        self.canvas_stack = Gtk.Stack()
        self.toast_overlay = Gtk.Overlay()
        self.toast_overlay.add(self.canvas_stack)
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
        self._toast_id = 0
        main.pack_start(self.toast_overlay, True, True, 0)
        self.canvas = Canvas()
        self.canvas.connect("changed", self.on_canvas_changed)
        self.canvas_stack.add_named(self.canvas, "canvas")
        self.empty = self.build_empty()
        self.canvas_stack.add_named(self.empty, "empty")
        self.canvas_stack.set_visible_child_name("empty")

        self.connect("delete-event", self.on_delete)
        self.connect("key-press-event", self.on_key)
        self.refresh_state()
        root.show_all()
        self.infobar.set_reveal_child(False)
        self.canvas_stack.set_visible_child_name("empty")
        self.update_edit_group()
        self.set_title(APP_NAME)
        self.resize(1000, 640)

    # --------------------------------------------------------------- UI
    def build_toolbar(self):
        col = theme.icon_color()
        bar = Gtk.Box(spacing=2)
        bar.set_margin_start(10)
        bar.set_margin_end(10)
        bar.set_margin_top(4)
        bar.set_margin_bottom(4)
        bar.get_style_context().add_class("cap-toolbar")

        self.btn_new = btn("plus", "Novo", cls=("newbtn",), size=16)
        self.btn_new.connect("clicked", lambda *_: self.app.start_capture(self.app_tool_for_new(), settings["delay"], from_app=True))
        bar.pack_start(self.btn_new, False, False, 0)

        seg = Gtk.Box()
        seg.get_style_context().add_class("seg")
        seg.set_margin_start(6)
        self.b_photo = btn("camera", tip="Captura de tela", toggle=True)
        self.b_video = btn("video", tip="Gravação de tela", toggle=True)
        seg.pack_start(self.b_photo, False, False, 0)
        seg.pack_start(self.b_video, False, False, 0)
        (self.b_video if settings["mode"] == "video" else self.b_photo).set_active(True)
        self.b_photo.connect("clicked", lambda b: self.set_mode("photo"))
        self.b_video.connect("clicked", lambda b: self.set_mode("video"))
        bar.pack_start(seg, False, False, 0)

        self.shape_btn = btn(None, None, tip="Modo de captura")
        self.shape_img = Gtk.Image()
        r = Gtk.Box(spacing=4)
        r.pack_start(self.shape_img, False, False, 0)
        r.pack_start(icons.image("chevron_down", 12, col), False, False, 0)
        self.shape_btn.add(r)
        self.shape_btn.connect("clicked", self.popup_shape_menu)
        bar.pack_start(self.shape_btn, False, False, 0)

        self.delay_btn = btn(None, None, tip="Atraso de captura")
        self.delay_img = Gtk.Image()
        r = Gtk.Box(spacing=4)
        r.pack_start(self.delay_img, False, False, 0)
        r.pack_start(icons.image("chevron_down", 12, col), False, False, 0)
        self.delay_btn.add(r)
        self.delay_btn.connect("clicked", self.popup_delay_menu)
        bar.pack_start(self.delay_btn, False, False, 0)
        self.refresh_capture_icons()

        # grupo de edição (centro)
        self.edit_group = Gtk.Box(spacing=2)
        self.btn_pen = btn(None, tip="Caneta", toggle=True)
        self.btn_hl = btn(None, tip="Marca-texto", toggle=True)
        self.btn_eraser = btn("eraser", tip="Borracha", toggle=True)
        self.btn_shape = btn("shapes", tip="Formas", toggle=True)
        self.tool_btns = {"pen": self.btn_pen, "hl": self.btn_hl, "eraser": self.btn_eraser, "shape": self.btn_shape}
        for name, b in self.tool_btns.items():
            b.connect("button-press-event", self.on_tool_press, name)
            self.edit_group.pack_start(b, False, False, 0)
        self.refresh_tool_icons()
        self.edit_group.pack_start(self._sep(), False, False, 0)
        self.btn_crop = btn("crop", tip="Corte de imagem", toggle=True)
        self.btn_crop.connect("clicked", lambda b: self.toggle_crop(b.get_active()))
        self.btn_text = btn("textscan", tip="Ações de texto")
        self.btn_text.connect("clicked", lambda *_: self.app.ocr_current(self))
        self.edit_group.pack_start(self.btn_crop, False, False, 0)
        self.edit_group.pack_start(self.btn_text, False, False, 0)
        self.edit_group.pack_start(self._sep(), False, False, 0)
        self.btn_undo = btn("undo", tip="Desfazer (Ctrl+Z)")
        self.btn_redo = btn("redo", tip="Refazer (Ctrl+Y)")
        self.btn_undo.connect("clicked", lambda *_: self.canvas.undo())
        self.btn_redo.connect("clicked", lambda *_: self.canvas.redo())
        self.edit_group.pack_start(self.btn_undo, False, False, 0)
        self.edit_group.pack_start(self.btn_redo, False, False, 0)
        self.edit_group.set_halign(Gtk.Align.CENTER)
        bar.pack_start(self.edit_group, True, False, 0)

        # extrator de texto quando não há imagem
        self.btn_ocr_empty = btn("textscan", "Extrator de Texto", tip="Extrair texto da tela")
        self.btn_ocr_empty.connect("clicked", lambda *_: self.app.start_capture("ocr", settings["delay"], from_app=True))
        self.btn_ocr_empty.set_margin_start(6)
        bar.pack_start(self.btn_ocr_empty, False, False, 0)
        spacer = Gtk.Box()
        bar.pack_start(spacer, True, True, 0)
        self.empty_spacer = spacer

        # crop actions (substituem o grupo de edição durante o corte)
        self.crop_group = Gtk.Box(spacing=6)
        ok = btn("check", "Concluir", cls=("accentbtn",), size=16)
        ok.get_style_context().add_class("accentbtn")
        ok.connect("clicked", lambda *_: self.toggle_crop(False, apply=True))
        cancel = btn("close", "Cancelar", size=16)
        cancel.connect("clicked", lambda *_: self.toggle_crop(False, apply=False))
        self.crop_group.pack_start(cancel, False, False, 0)
        self.crop_group.pack_start(ok, False, False, 0)
        self.crop_group.set_halign(Gtk.Align.CENTER)
        bar.pack_start(self.crop_group, True, False, 0)

        # direita
        self.right = Gtk.Box(spacing=2)
        self.btn_ext = btn(None, "Editar", tip="Editar em outro aplicativo")
        self.btn_ext.connect("clicked", lambda *_: self.edit_external())
        self.btn_save = btn("save", tip="Salvar como (Ctrl+S)")
        self.btn_save.connect("clicked", lambda *_: self.save_as())
        self.btn_copy = btn("copy", tip="Copiar (Ctrl+C)")
        self.btn_copy.connect("clicked", lambda *_: self.copy_image())
        self.btn_share = btn("share", tip="Compartilhar")
        self.btn_share.connect("clicked", self.popup_share)
        self.btn_more = btn("more", tip="Mais")
        self.btn_more.connect("clicked", self.popup_more)
        for w in (self.btn_ext, self.btn_save, self.btn_copy, self.btn_share):
            self.right.pack_start(w, False, False, 0)
        self.right.pack_start(self._sep(), False, False, 0)
        self.right.pack_start(self.btn_more, False, False, 0)
        bar.pack_end(self.right, False, False, 0)
        self.toolbar = bar
        return bar

    def _sep(self):
        s = Gtk.Box()
        s.get_style_context().add_class("sep")
        s.set_size_request(1, 20)
        s.set_valign(Gtk.Align.CENTER)
        s.set_margin_start(6)
        s.set_margin_end(6)
        s.set_margin_top(0)
        s.set_margin_bottom(0)
        return s

    def build_infobar(self):
        rev = Gtk.Revealer()
        rev.set_transition_type(Gtk.RevealerTransitionType.SLIDE_DOWN)
        box = Gtk.Box(spacing=10)
        box.get_style_context().add_class("cap-infobar")
        box.pack_start(icons.image("info", 18, theme.palette()["accent"]), False, False, 0)
        t = Gtk.Label(label="As capturas de tela são salvas automaticamente na pasta Capturas de Tela", xalign=0)
        t.get_style_context().add_class("bold")
        t.set_ellipsize(3)
        t.set_width_chars(8)
        box.pack_start(t, False, False, 0)
        t2 = Gtk.Label(label="Você pode desativá-lo nas configurações do aplicativo.", xalign=0)
        t2.get_style_context().add_class("subtle")
        t2.set_ellipsize(3)
        t2.set_width_chars(8)
        box.pack_start(t2, True, True, 0)
        link = Gtk.Button(label="Abrir as Configurações da Ferramenta de Captura")
        link.get_child().set_ellipsize(3)
        link.get_style_context().add_class("link")
        link.connect("clicked", lambda *_: self.show_page("settings"))
        box.pack_end(self._close_btn(rev), False, False, 0)
        box.pack_end(link, False, False, 0)
        rev.add(box)
        return rev

    def _close_btn(self, rev):
        b = btn("close", size=14)
        b.connect("clicked", lambda *_: (rev.set_reveal_child(False), settings.__setitem__("infobar_dismissed", True)))
        return b

    def build_empty(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        box.set_valign(Gtk.Align.CENTER)
        box.set_halign(Gtk.Align.CENTER)
        box.pack_start(icons.image("camera", 56, theme.palette()["disabled"]), False, False, 0)
        l = Gtk.Label(label="Pressione Super + Shift + S para iniciar uma captura")
        l.get_style_context().add_class("subtle")
        box.pack_start(l, False, False, 0)
        l2 = Gtk.Label(label="ou clique em Novo")
        l2.get_style_context().add_class("subtle")
        box.pack_start(l2, False, False, 0)
        bg = Gtk.EventBox()
        bg.get_style_context().add_class("cap-canvas-bg")
        bg.add(box)
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
        self.shape_img.set_from_pixbuf(icons.pixbuf(name, 18, theme.icon_color()))
        d = [i for k, i, _ in DELAYS if k == settings["delay"]][0]
        self.delay_img.set_from_pixbuf(icons.pixbuf(d, 18, theme.icon_color()))

    def refresh_tool_icons(self):
        self.btn_pen.get_child() and self.btn_pen.remove(self.btn_pen.get_child())
        self.btn_hl.get_child() and self.btn_hl.remove(self.btn_hl.get_child())
        pc, _ = self.canvas_opts("pen")
        hc, _ = self.canvas_opts("hl")
        self.btn_pen.add(Gtk.Image.new_from_pixbuf(icons.tool_pixbuf("pen", pc, theme.icon_color())))
        self.btn_hl.add(Gtk.Image.new_from_pixbuf(icons.tool_pixbuf("highlighter", hc, theme.icon_color())))
        self.btn_pen.show_all()
        self.btn_hl.show_all()

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
        self.edit_group.set_visible(has and not cropping)
        self.crop_group.set_visible(has and cropping)
        self.btn_ocr_empty.set_visible(not has)
        self.empty_spacer.set_visible(not has)
        for w in (self.btn_ext, self.btn_save, self.btn_copy, self.btn_share):
            w.set_sensitive(has)
        self.btn_undo.set_sensitive(bool(self.canvas.undo_stack))
        self.btn_redo.set_sensitive(bool(self.canvas.redo_stack))
        ed, lab = services.external_editor()
        child = self.btn_ext.get_child()
        for c in child.get_children():
            child.remove(c)
        child.pack_start(icons.image("openwith", 18, theme.icon_color()), False, False, 0)
        child.pack_start(Gtk.Label(label=f"Editar no {lab}" if lab else "Abrir com…"), False, False, 0)
        child.show_all()

    def refresh_state(self):
        pass

    def on_canvas_changed(self, *a):
        self.update_edit_group()
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
        self.title_label.set_text(APP_NAME if not name else f"{APP_NAME} — {name}")
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
            else:
                self.popup_flyout(b, name)
            return True
        self.select_tool(name)
        return True

    def select_tool(self, name):
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
            col, sz = self.canvas.opts["shape"]
            fl = ToolFlyout(b, "shape", col, sz, lambda c, s, k: self.set_tool_opts("shape", c, s, k), self.canvas.opts["shape_kind"])
        fl.popup()

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

    def popup_eraser_menu(self, b):
        make_menu(b, [("trash", "Apagar todas as marcações", None, self.canvas.clear_markup, bool(self.canvas.items))]).popup()

    def toggle_crop(self, on, apply=False):
        if on:
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
    def popup_shape_menu(self, b):
        items = [(i, l, None, (lambda k=k: self.set_shape(k))) for k, i, l in SHAPES]
        make_menu(b, items, 180).popup()

    def set_shape(self, k):
        settings["shape"] = k
        self.refresh_capture_icons()

    def popup_delay_menu(self, b):
        items = [(i, l, None, (lambda d=d: self.set_delay(d))) for d, i, l in DELAYS]
        make_menu(b, items, 200).popup()

    def set_delay(self, d):
        settings["delay"] = d
        self.refresh_capture_icons()

    def popup_share(self, b):
        make_menu(b, [("share_mail", "Enviar por e-mail", None, self.share_mail),
                      ("copytext", "Copiar caminho do arquivo", None, self.copy_path),
                      ("openwith", "Abrir com…", None, self.open_with)], 240).popup()

    def popup_more(self, b):
        pop = Gtk.Popover.new(b)
        pop.get_style_context().add_class("cap-pop")
        pop.set_position(Gtk.PositionType.BOTTOM)
        stack = Gtk.Stack()
        stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)

        def row(icon, label, accel, cb, chevron=False, enabled=True):
            r = Gtk.Button()
            r.get_style_context().add_class("tbtn")
            r.get_style_context().add_class("menuitem")
            hb = Gtk.Box(spacing=12)
            hb.pack_start(icons.image(icon, 18, theme.icon_color()) if icon else Gtk.Box(), False, False, 0)
            hb.pack_start(Gtk.Label(label=label, xalign=0), True, True, 0)
            if accel:
                a = Gtk.Label(label=accel)
                a.get_style_context().add_class("subtle")
                hb.pack_end(a, False, False, 0)
            if chevron:
                hb.pack_end(icons.image("chevron_right", 12, theme.icon_color()), False, False, 0)
            hb.set_size_request(280, -1)
            r.add(hb)
            r.set_sensitive(enabled)
            r.connect("clicked", cb)
            return r
        has = self.canvas.base is not None
        p1 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        p1.pack_start(row("zoom", "Zoom", None, lambda *_: stack.set_visible_child_name("zoom"), True, has), False, False, 0)
        p1.pack_start(row("openwith", "Abrir arquivo", "Ctrl+O", lambda *_: (pop.popdown(), GLib.idle_add(self.open_dialog))), False, False, 0)
        p1.pack_start(row("folder", "Abrir a pasta de capturas de tela", None, lambda *_: (pop.popdown(), self.open_folder())), False, False, 0)
        p1.pack_start(row("print", "Imprimir", "Ctrl+P", lambda *_: (pop.popdown(), GLib.idle_add(self.print_image)), False, has), False, False, 0)
        p1.pack_start(row("gear", "Configurações", None, lambda *_: (pop.popdown(), self.show_page("settings"))), False, False, 0)
        p2 = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1)
        p2.pack_start(row("back", "Zoom", None, lambda *_: stack.set_visible_child_name("main")), False, False, 0)
        p2.pack_start(row("zoom", "Aumentar zoom", "Ctrl++", lambda *_: self.canvas.zoom_by(1.25)), False, False, 0)
        p2.pack_start(row(None, "Diminuir zoom", "Ctrl+-", lambda *_: self.canvas.zoom_by(0.8)), False, False, 0)
        p2.pack_start(row(None, "Ajustar à janela", "Ctrl+0", lambda *_: self.canvas.set_zoom(1.0, fit=True) or self.canvas.update_scale()), False, False, 0)
        p2.pack_start(row(None, "Tamanho real (100%)", None, lambda *_: self.canvas.set_zoom(1.0)), False, False, 0)
        stack.add_named(p1, "main")
        stack.add_named(p2, "zoom")
        wrap = Gtk.Box()
        for m in (wrap.set_margin_top, wrap.set_margin_bottom, wrap.set_margin_start, wrap.set_margin_end):
            m(4)
        wrap.add(stack)
        pop.add(wrap)
        wrap.show_all()
        stack.set_visible_child_name("main")
        pop.popup()

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
        s = self.current_surface()
        if s is None:
            return
        dlg = Gtk.FileChooserDialog(title="Salvar como", parent=self, action=Gtk.FileChooserAction.SAVE)
        dlg.add_buttons("Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.OK)
        dlg.set_do_overwrite_confirmation(True)
        d = settings.shot_directory
        os.makedirs(d, exist_ok=True)
        dlg.set_current_folder(d)
        dlg.set_current_name(services.timestamp_name())
        for label, pats in (("PNG (*.png)", ["*.png"]), ("JPEG (*.jpg, *.jpeg)", ["*.jpg", "*.jpeg"]), ("BMP (*.bmp)", ["*.bmp"])):
            f = Gtk.FileFilter()
            f.set_name(label)
            for p in pats:
                f.add_pattern(p)
            dlg.add_filter(f)
        if dlg.run() == Gtk.ResponseType.OK:
            path = dlg.get_filename()
            if not os.path.splitext(path)[1]:
                path += ".png"
            try:
                services.save_surface(s, path)
                self.saved_path = path
                self.canvas.dirty = False
                self.app.toast_in_window("Salvo em " + path)
            except Exception as e:
                self.error_dialog("Não foi possível salvar", str(e))
        dlg.destroy()

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
            self.canvas.zoom_by(1.25); return True
        if ctrl and k in (Gdk.KEY_minus, Gdk.KEY_KP_Subtract):
            self.canvas.zoom_by(0.8); return True
        if ctrl and k in (Gdk.KEY_0, Gdk.KEY_KP_0):
            self.canvas.set_zoom(1.0, fit=True); self.canvas.update_scale(); return True
        if ctrl and k in (Gdk.KEY_n, Gdk.KEY_N):
            self.btn_new.clicked(); return True
        if k == Gdk.KEY_Escape:
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
            d = Gtk.MessageDialog(parent=self, flags=0, message_type=Gtk.MessageType.QUESTION, text="Salvar alterações na captura de tela?")
            d.format_secondary_text("Suas edições serão perdidas se você não salvar.")
            d.add_buttons("Não salvar", Gtk.ResponseType.NO, "Cancelar", Gtk.ResponseType.CANCEL, "Salvar", Gtk.ResponseType.YES)
            r = d.run()
            d.destroy()
            if r == Gtk.ResponseType.CANCEL or r == Gtk.ResponseType.DELETE_EVENT:
                return True
            if r == Gtk.ResponseType.YES:
                self.save_as()
        return False
