"""Ferramenta de Captura — recriação, para o Linux Mint (Cinnamon/X11), da Ferramenta de Captura do Windows 11."""
APP_ID = "org.captura.App"
APP_NAME = "Ferramenta de Captura"      # ID da mensagem (texto-fonte em pt-BR); o nome exibido sai de app_name()
__version__ = "1.0.2"


def app_name():
    """Nome do programa no idioma ativo: Snipping Tool (padrão, inglês), Ferramenta de Captura (pt-BR), etc."""
    from . import i18n
    return i18n.tr(APP_NAME)


try:
    from . import i18n as _i18n
    _i18n.install()
except Exception:      # sem Gtk 3 (ferramentas de linha de comando): sem tradução automática
    pass

try:
    from . import fonts as _fonts
    _fonts.register()
except Exception:      # fontes opcionais
    pass
