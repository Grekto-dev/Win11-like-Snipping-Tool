"""Registra as fontes incluídas (Selawik, SIL OFL 1.1) no fontconfig do processo, sem instalar nada no sistema."""
import ctypes
import glob
import os

_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "fonts")


def register():
    try:
        fc = ctypes.CDLL("libfontconfig.so.1")
        fc.FcConfigAppFontAddFile.argtypes = [ctypes.c_void_p, ctypes.c_char_p]
        for f in sorted(glob.glob(os.path.join(_DIR, "*.ttf"))):
            fc.FcConfigAppFontAddFile(None, f.encode())
        return True
    except OSError:
        return False
