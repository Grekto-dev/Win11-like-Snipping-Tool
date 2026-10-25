"""Atalhos globais no Cinnamon: Super+Shift+S (e opcionalmente Imprimir tela) via custom-keybindings do dconf."""
import gi
from gi.repository import Gio, GLib

SCHEMA = "org.cinnamon.desktop.keybindings"
CUSTOM_SCHEMA = "org.cinnamon.desktop.keybindings.custom-keybinding"
CUSTOM_PATH = "/org/cinnamon/desktop/keybindings/custom-keybindings/%s/"
MEDIA_SCHEMA = "org.cinnamon.desktop.keybindings.media-keys"
BACKUP_KEY = "/org/captura/backup-print-keys"

SNIP_ID = "captura-snip"
PRINT_ID = "captura-print"


def _schema_exists(name):
    src = Gio.SettingsSchemaSource.get_default()
    return src is not None and src.lookup(name, True) is not None


def available():
    return _schema_exists(SCHEMA) and _schema_exists(CUSTOM_SCHEMA)


def _set_custom(kid, name, command, bindings):
    s = Gio.Settings.new(SCHEMA)
    lst = list(s.get_strv("custom-list"))
    if kid not in lst:
        lst.append(kid)
        s.set_strv("custom-list", lst)
    c = Gio.Settings.new_with_path(CUSTOM_SCHEMA, CUSTOM_PATH % kid)
    c.set_string("name", name)
    c.set_string("command", command)
    c.set_strv("binding", bindings)
    Gio.Settings.sync()


def _remove_custom(kid):
    s = Gio.Settings.new(SCHEMA)
    lst = [k for k in s.get_strv("custom-list") if k != kid]
    s.set_strv("custom-list", lst)
    Gio.Settings.sync()


def has_snip_binding():
    if not available():
        return False
    return SNIP_ID in Gio.Settings.new(SCHEMA).get_strv("custom-list")


def ensure_snip_binding(command):
    """Cria Super+Shift+S -> `captura --snip` se ainda não existir (não sobrescreve escolha do usuário)."""
    if not available() or has_snip_binding():
        return False
    _set_custom(SNIP_ID, "Ferramenta de Captura", command, ["<Super><Shift>s"])
    return True


def set_print_key(enabled, command=None):
    """Liga/desliga a tecla Imprimir tela para a Ferramenta de Captura (libera/restaura o atalho do sistema)."""
    if not available():
        return
    media = Gio.Settings.new(MEDIA_SCHEMA) if _schema_exists(MEDIA_SCHEMA) else None
    keys = ("screenshot",)
    store = Gio.Settings.new("org.cinnamon.desktop.keybindings")
    if enabled:
        if media:
            for k in keys:
                cur = list(media.get_strv(k))
                if "Print" in cur:
                    media.set_strv(k, [b for b in cur if b != "Print"])
        _set_custom(PRINT_ID, "Ferramenta de Captura (Imprimir tela)", command or "captura --snip", ["Print"])
    else:
        _remove_custom(PRINT_ID)
        if media:
            for k in keys:
                cur = list(media.get_strv(k))
                if "Print" not in cur:
                    media.set_strv(k, cur + ["Print"])
    Gio.Settings.sync()
