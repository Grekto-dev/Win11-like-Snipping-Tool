"""Ferramenta de Captura — recriação, para o Linux Mint (Cinnamon/X11), da Ferramenta de Captura do Windows 11."""
APP_ID = "org.captura.App"
APP_NAME = "Ferramenta de Captura"
__version__ = "0.1.0"


try:
    from . import fonts as _fonts
    _fonts.register()
except Exception:      # fontes opcionais
    pass
