"""Leitura de códigos QR com a libzbar (ctypes; sem dependência de Python extra). `decode(surface)` -> lista de textos."""
import ctypes
import ctypes.util

_lib = None
_tried = False
Z_CFG_ENABLE, Z_CFG_BINARY, Z_QRCODE = 0, 4, 64


def _load():
    global _lib, _tried
    if _tried:
        return _lib
    _tried = True
    for name in (ctypes.util.find_library("zbar"), "libzbar.so.0"):
        if not name:
            continue
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        lib.zbar_image_scanner_create.restype = ctypes.c_void_p
        lib.zbar_image_create.restype = ctypes.c_void_p
        lib.zbar_image_first_symbol.restype = ctypes.c_void_p
        lib.zbar_image_first_symbol.argtypes = [ctypes.c_void_p]
        lib.zbar_symbol_next.restype = ctypes.c_void_p
        lib.zbar_symbol_next.argtypes = [ctypes.c_void_p]
        lib.zbar_symbol_get_data.restype = ctypes.c_char_p
        lib.zbar_symbol_get_data.argtypes = [ctypes.c_void_p]
        lib.zbar_symbol_get_data.restype = ctypes.c_void_p
        lib.zbar_symbol_get_data_length.argtypes = [ctypes.c_void_p]
        lib.zbar_symbol_get_data_length.restype = ctypes.c_uint
        lib.zbar_symbol_get_type.argtypes = [ctypes.c_void_p]
        lib.zbar_symbol_get_type.restype = ctypes.c_int
        lib.zbar_image_scanner_set_config.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int, ctypes.c_int]
        lib.zbar_image_scanner_destroy.argtypes = [ctypes.c_void_p]
        lib.zbar_image_set_format.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        lib.zbar_image_set_size.argtypes = [ctypes.c_void_p, ctypes.c_uint, ctypes.c_uint]
        lib.zbar_image_set_data.argtypes = [ctypes.c_void_p, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p]
        lib.zbar_scan_image.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
        lib.zbar_image_destroy.argtypes = [ctypes.c_void_p]
        _lib = lib
        return lib
    return None


def available():
    return _load() is not None


def _gray(surface):
    """Cairo ARGB32 -> bytes de 8 bits (luminância), no tamanho original."""
    w, h, stride = surface.get_width(), surface.get_height(), surface.get_stride()
    data = bytes(surface.get_data())
    out = bytearray(w * h)
    for y in range(h):
        row = data[y * stride:y * stride + w * 4]
        b, g, r = row[0::4], row[1::4], row[2::4]
        out[y * w:(y + 1) * w] = bytes((29 * bb + 150 * gg + 77 * rr) >> 8 for bb, gg, rr in zip(b, g, r))
    return w, h, bytes(out)


def decode(surface):
    """Textos dos QR codes encontrados em `surface` (cairo.ImageSurface). Tenta o tamanho original e uma ampliação 2x."""
    lib = _load()
    if lib is None or surface is None:
        return []
    found = []
    for scale in (1, 2):
        w, h, gray = _gray(surface)
        if scale == 2:
            if max(w, h) > 1400:
                break
            up = bytearray(w * 2 * h * 2)
            for y in range(h):
                line = bytes(c for c in gray[y * w:(y + 1) * w] for _ in (0, 1))
                up[(2 * y) * (2 * w):(2 * y + 1) * (2 * w)] = line
                up[(2 * y + 1) * (2 * w):(2 * y + 2) * (2 * w)] = line
            w, h, gray = w * 2, h * 2, bytes(up)
        sc = lib.zbar_image_scanner_create()
        lib.zbar_image_scanner_set_config(sc, 0, 0, 0)                   # tudo desligado
        lib.zbar_image_scanner_set_config(sc, Z_QRCODE, Z_CFG_ENABLE, 1)
        lib.zbar_image_scanner_set_config(sc, 0, Z_CFG_BINARY, 1)         # bytes brutos: o zbar não adivinha o encoding
        img = lib.zbar_image_create()
        lib.zbar_image_set_format(img, 0x30303859)                       # 'Y800'
        lib.zbar_image_set_size(img, w, h)
        buf = ctypes.create_string_buffer(gray, len(gray))
        lib.zbar_image_set_data(img, buf, len(gray), None)
        if lib.zbar_scan_image(sc, img) > 0:
            sym = lib.zbar_image_first_symbol(img)
            while sym:
                if lib.zbar_symbol_get_type(sym) == Z_QRCODE:
                    n = lib.zbar_symbol_get_data_length(sym)
                    data = ctypes.string_at(lib.zbar_symbol_get_data(sym), n)
                    if data:
                        try:
                            t = data.decode("utf-8")
                        except UnicodeDecodeError:
                            t = data.decode("latin-1")
                        if t not in found:
                            found.append(t)
                sym = lib.zbar_symbol_next(sym)
        lib.zbar_image_destroy(img)
        lib.zbar_image_scanner_destroy(sc)
        if found:
            break
    return found
