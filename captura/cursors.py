"""Cursor de "mãozinha" para links (botões estilizados como link)."""
import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
from gi.repository import Gdk, Gtk

LINK_CLASSES = ("linkbtn", "link", "about-link")


def hand(widget):
    """Faz o cursor virar mão sobre o widget (e voltar ao normal ao sair)."""
    if widget.__dict__.get("_hand"):
        return widget
    widget.__dict__["_hand"] = True
    widget.add_events(Gdk.EventMask.ENTER_NOTIFY_MASK | Gdk.EventMask.LEAVE_NOTIFY_MASK)

    # Um Gtk.Button não tem GdkWindow próprio: get_window() devolve o da janela-mãe. Por isso o cursor só pode valer enquanto o
    # ponteiro está sobre o link (entrar -> mão; sair, esconder ou destruir -> volta ao normal), nunca ficar gravado na mãe.
    def set_cursor(w, kind):
        win = w.get_window()
        if win is not None:
            win.set_cursor(Gdk.Cursor.new_from_name(w.get_display(), kind) if kind else None)

    def on_leave(w, e):
        if e.detail != Gdk.NotifyType.INFERIOR:
            set_cursor(w, None)
        return False
    widget.connect("enter-notify-event", lambda w, e: set_cursor(w, "pointer") or False)
    widget.connect("leave-notify-event", on_leave)
    widget.connect("unmap", lambda w: set_cursor(w, None))
    widget.connect("destroy", lambda w: set_cursor(w, None))
    return widget


def is_link(widget):
    ctx = widget.get_style_context()
    return isinstance(widget, Gtk.Button) and any(ctx.has_class(c) for c in LINK_CLASSES)


def apply_links(root):
    """Aplica a mãozinha a todos os botões-link sob `root` (chamar depois de montar a interface)."""
    n = 0
    stack = [root]
    while stack:
        w = stack.pop()
        if is_link(w):
            hand(w)
            n += 1
        if isinstance(w, Gtk.Container):
            stack.extend(w.get_children())
    return n
