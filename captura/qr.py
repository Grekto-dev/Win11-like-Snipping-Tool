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
        lib.zbar_image_convert.argtypes = [ctypes.c_void_p, ctypes.c_ulong]
        lib.zbar_image_convert.restype = ctypes.c_void_p
        lib.zbar_image_destroy.argtypes = [ctypes.c_void_p]
        _lib = lib
        return lib
    return None


def available():
    return _load() is not None


def _rgb(pb):
    """Bytes RGB sem preenchimento de linha (o zbar converte para cinza em C: nada de laços em Python por pixel)."""
    w, h, stride = pb.get_width(), pb.get_height(), pb.get_rowstride()
    data = pb.get_pixels()
    if stride == w * 3:
        return bytes(data)
    return b"".join(data[y * stride:y * stride + w * 3] for y in range(h))


def _scan(lib, w, h, rgb):
    sc = lib.zbar_image_scanner_create()
    lib.zbar_image_scanner_set_config(sc, 0, 0, 0)                   # tudo desligado
    lib.zbar_image_scanner_set_config(sc, Z_QRCODE, Z_CFG_ENABLE, 1)
    lib.zbar_image_scanner_set_config(sc, 0, Z_CFG_BINARY, 1)         # bytes brutos: o zbar não adivinha o encoding
    img = lib.zbar_image_create()
    lib.zbar_image_set_format(img, 0x33424752)                       # 'RGB3'
    lib.zbar_image_set_size(img, w, h)
    buf = ctypes.create_string_buffer(rgb, len(rgb))
    lib.zbar_image_set_data(img, buf, len(rgb), None)
    found = []
    gray = lib.zbar_image_convert(img, 0x30303859)                   # RGB3 -> 'Y800' (em C; o scanner só aceita cinza)
    if gray and lib.zbar_scan_image(sc, gray) > 0:
        sym = lib.zbar_image_first_symbol(gray)
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
    if gray:
        lib.zbar_image_destroy(gray)
    lib.zbar_image_destroy(img)
    lib.zbar_image_scanner_destroy(sc)
    return found


def decode(surface):
    """Textos dos QR codes encontrados em `surface` (cairo.ImageSurface). Tenta o tamanho original e uma ampliação 2x."""
    lib = _load()
    if lib is None or surface is None:
        return []
    import cairo
    from gi.repository import Gdk, GdkPixbuf
    flat = cairo.ImageSurface(cairo.FORMAT_RGB24, surface.get_width(), surface.get_height())      # sem canal alfa: pixbuf de 3 canais
    cr = cairo.Context(flat)
    cr.set_source_rgb(1, 1, 1)
    cr.paint()
    cr.set_source_surface(surface, 0, 0)
    cr.paint()
    pb = Gdk.pixbuf_get_from_surface(flat, 0, 0, flat.get_width(), flat.get_height())
    if pb is None:
        return []
    found = _scan(lib, pb.get_width(), pb.get_height(), _rgb(pb))
    if not found and max(pb.get_width(), pb.get_height()) <= 1400:
        big = pb.scale_simple(pb.get_width() * 2, pb.get_height() * 2, GdkPixbuf.InterpType.BILINEAR)
        found = _scan(lib, big.get_width(), big.get_height(), _rgb(big))
    return found
