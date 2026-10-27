#!/usr/bin/python3
"""Bateria de desempenho e depuração da Ferramenta de Captura (roda num X isolado: Xephyr :9).

uso: scripts/perf_battery.py [grupo ...]     grupos: import window draw overlay text ocr anim leak idle fuzz
Imprime uma tabela e grava perf_report.json (orçamento de quadro: 16,7 ms a 60 Hz)."""
import gc
import json
import os
import random
import subprocess
import sys
import threading
import time
import tracemalloc

os.environ.setdefault("XDG_CONFIG_HOME", os.path.expanduser("~/.hermes/cache/scratch/perf-config"))
os.environ.setdefault("NO_AT_BRIDGE", "1")
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
sys.path.insert(0, os.path.join(os.path.dirname(HERE), "tests"))

import gi
gi.require_version("Gtk", "3.0")
gi.require_version("Gdk", "3.0")
import cairo
import psutil
from gi.repository import Gdk, GLib, GdkPixbuf, Gtk

from gtkapp import shared_app
from captura import annot, theme, textlayer
from captura.config import settings

HOOK = []                                # exceções que o PyGObject engole dentro de handlers de sinal (vão ao sys.excepthook)


def _hook(tp, val, tb):
    import traceback
    HOOK.append("".join(traceback.format_exception_only(tp, val)).strip() + " @ " + traceback.extract_tb(tb)[-1].name)


sys.excepthook = _hook
REPORT = {}
ROWS = []
PROC = psutil.Process()
SHOTS = os.path.expanduser("~/snip-tool-research/shots/")


def row(group, name, value, unit, budget=None, note=""):
    ok = budget is None or value <= budget
    ROWS.append((group, name, value, unit, budget, ok, note))
    REPORT["%s/%s" % (group, name)] = {"value": round(value, 3), "unit": unit, "budget": budget, "ok": ok}
    print("%-8s %-44s %9.2f %-5s %s%s" % (group, name, value, unit, "" if budget is None else ("OK  (<=%g)" % budget if ok else "ESTOUROU (>%g)" % budget), (" " + note) if note else ""), flush=True)


def pump(sec=.2):
    end = time.monotonic() + sec
    while time.monotonic() < end:
        while Gtk.events_pending():
            Gtk.main_iteration_do(False)
        time.sleep(.002)


def run_loop(sec):
    """Espera `sec` s num GLib.MainLoop de verdade (sem laço de polling, que distorceria a medição de CPU ocioso)."""
    loop = GLib.MainLoop()
    GLib.timeout_add(int(sec * 1000), lambda: (loop.quit(), False)[1])
    loop.run()


def timed(fn, n=1):
    t = time.perf_counter()
    for _ in range(n):
        fn()
    return (time.perf_counter() - t) * 1000 / n


def rss():
    return PROC.memory_info().rss / 1048576


def gtk_objects():
    gc.collect()
    n = 0
    for o in gc.get_objects():
        if isinstance(o, Gtk.Widget):
            n += 1
    return n


def solid(w, h, rgb=(.95, .95, .95)):
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
    cr = cairo.Context(s)
    cr.set_source_rgb(*rgb)
    cr.paint()
    cr.set_source_rgb(.1, .3, .8)
    for i in range(0, w, 40):
        cr.rectangle(i, 0, 20, h)
        cr.fill()
    return s


def from_png(path):
    pb = GdkPixbuf.Pixbuf.new_from_file(path)
    s = cairo.ImageSurface(cairo.FORMAT_ARGB32, pb.get_width(), pb.get_height())
    cr = cairo.Context(s)
    Gdk.cairo_set_source_pixbuf(cr, pb, 0, 0)
    cr.paint()
    return s


def words_grid(lines, per=8):
    out = []
    for r in range(lines):
        for c in range(per):
            x = 20 + c * 70
            out.append(textlayer.Word("palavra%d" % c, (x, 20 + r * 24, x + 60, 38 + r * 24), (1, 1 + r // 6, 1 + r % 6)))
    return out


# --------------------------------------------------------------------------------------------------- grupos
def g_import():
    out = subprocess.run([sys.executable, "-X", "importtime", "-c", "import captura.app"], capture_output=True, text=True,
                         cwd=os.path.dirname(HERE), env=dict(os.environ, DISPLAY=os.environ["DISPLAY"])).stderr
    rows = []
    for line in out.splitlines():
        if "|" in line and "captura" in line:
            parts = line.split("|")
            try:
                rows.append((int(parts[1]), parts[2].strip()))
            except ValueError:
                pass
    total = max((c for c, n in rows if n == "captura.app"), default=0) / 1000
    row("import", "import captura.app (a frio, dentro do processo)", total, "ms", 900)
    for cum, name in sorted(rows, reverse=True)[1:4]:
        row("import", "  mais lento: " + name, cum / 1000, "ms")
    t = time.perf_counter()
    subprocess.run([sys.executable, "-c", "import gi;gi.require_version('Gtk','3.0');from gi.repository import Gtk"], env=os.environ)
    row("import", "baseline: só importar o Gtk", (time.perf_counter() - t) * 1000, "ms")


def g_window():
    from captura.window import EditorWindow
    app = shared_app()
    ms = []
    for _ in range(3):
        t = time.perf_counter()
        w = EditorWindow(app)
        w.show_all()
        pump(.05)
        ms.append((time.perf_counter() - t) * 1000)
        w.destroy()
        pump(.05)
    row("window", "criar + mostrar EditorWindow (melhor de 3)", min(ms), "ms", 400)
    w = EditorWindow(app)
    w.show_all()
    pump(.3)
    for name, surf in (("700x450", solid(700, 450)), ("1920x1080", solid(1920, 1080)), ("3840x2160", solid(3840, 2160))):
        t = time.perf_counter()
        w.load_surface(surf)
        c = w.canvas
        c.on_draw(c, cairo.Context(cairo.ImageSurface(cairo.FORMAT_ARGB32, 984, 640)))
        row("window", "load_surface + 1º desenho " + name, (time.perf_counter() - t) * 1000, "ms", 60 if "3840" not in name else 120)
        pump(.05)
    t = time.perf_counter()
    w.show_page("settings")
    pump(.1)
    row("window", "abrir página Configurações", (time.perf_counter() - t) * 1000, "ms", 400)
    t = time.perf_counter()
    w.show_page("main")
    pump(.1)
    row("window", "voltar ao editor", (time.perf_counter() - t) * 1000, "ms", 300)
    from captura import menus
    for label, fn in (("menu Mais", lambda: w.popup_more(w.btn_more)), ("menu de formas", lambda: w.popup_shape_menu(w.shape_btn))):
        def op():
            fn()
            pump(.02)
            m = getattr(w, "_cur_menu", None)
            if m:
                m.close_popup()
                pump(.02)
        row("window", "abrir+fechar " + label, timed(op, 5), "ms", 120)
    w.destroy()


def g_draw():
    from captura.window import EditorWindow
    app = shared_app()
    w = EditorWindow(app)
    w.show_all()
    pump(.3)
    c = w.canvas
    w.load_surface(solid(1920, 1080))
    pump(.2)
    out = cairo.ImageSurface(cairo.FORMAT_ARGB32, 984, 640)

    def frame():
        c.on_draw(c, cairo.Context(out))
    row("draw", "quadro do canvas vazio 1920x1080 (zoom ajustado)", timed(frame, 20), "ms", 8)
    rnd = random.Random(1)
    items = []
    for _ in range(150):
        x, y = rnd.randint(50, 1800), rnd.randint(50, 1000)
        items.append(annot.Stroke("pen", [(x + i * 3, y + 8 * ((i % 4) - 2)) for i in range(60)], "#e61b1b", 4))
    for _ in range(60):
        x, y = rnd.randint(50, 1700), rnd.randint(50, 900)
        sh = annot.Shape(rnd.choice(["rect", "ellipse", "line", "arrow"]), x, y, x + 120, y + 80, "#0067c0", 4)
        sh.fill = "#ffcc00" if rnd.random() < .5 else None
        items.append(sh)
    c.items = items
    row("draw", "quadro com 150 traços + 60 formas (estresse)", timed(frame, 10), "ms", 33, "estresse: 210 itens")
    c.items = items[:30]
    row("draw", "quadro com 30 itens (uso típico)", timed(frame, 10), "ms", 16.7, "orçamento 60 Hz")
    c.items = items
    c.items = items[:1]
    w.load_surface(solid(3840, 2160))
    pump(.2)
    row("draw", "quadro do canvas 3840x2160", timed(frame, 10), "ms", 16.7)
    c.items = []
    c.items = items[:20]
    zs = [0.3 + i * 0.007 for i in range(60)]
    t = time.perf_counter()
    for z in zs:                                   # zoom contínuo: cada passo refaz a imagem reduzida
        c.zoom = z
        c.on_draw(c, cairo.Context(out))
    row("draw", "60 passos de zoom contínuo (média por quadro)", (time.perf_counter() - t) * 1000 / 60, "ms", 33)
    c.zoom = 0.5
    row("draw", "quadro com zoom fixo 0.5 e 20 itens (cache)", timed(frame, 20), "ms", 8)
    w.destroy()


def g_overlay():
    from captura.overlay import Overlay
    for label, (W, H) in (("1440x900", (1440, 900)), ("3840x1080 (seu desktop)", (3840, 1080))):
        surf = solid(W, H)
        t = time.perf_counter()
        ov = Overlay(surf, lambda k, p: None, "snip")
        ov.show_all()
        pump(.05)
        row("overlay", "criar + mostrar " + label, (time.perf_counter() - t) * 1000, "ms", 350)
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, W, H)
        row("overlay", "quadro ocioso " + label, timed(lambda: ov.on_draw(ov.da, cairo.Context(out)), 10), "ms", 16.7)
        ov.sel = (300, 200, 1100, 700)
        ov.anchor = (300, 200)
        row("overlay", "quadro durante o arrasto " + label, timed(lambda: ov.on_draw(ov.da, cairo.Context(out)), 10), "ms", 16.7)
        ov.anchor = None
        ov.destroy()
        pump(.05)
    # movimento de ponteiro: custo por evento de arrasto
    ov = Overlay(solid(1440, 900), lambda k, p: None, "snip")
    ov.show_all()
    pump(.2)

    class E:
        button, state = 1, 0
    e = E()
    e.x, e.y = 100, 100
    ov.on_press(ov.da, e)
    t = time.perf_counter()
    for i in range(2000):
        e = E()
        e.x, e.y = 100 + i % 900, 100 + (i * 3) % 600
        ov.on_motion(ov.da, e)
    row("overlay", "2000 eventos de movimento no arrasto (µs/ev)", (time.perf_counter() - t) * 1e6 / 2000, "µs", 500)
    ov.destroy()


def g_text():
    from captura.overlay import Overlay
    for n in (24, 200):
        ws = words_grid(n)
        row("text", "group_lines %d linhas" % n, timed(lambda: textlayer.group_lines(ws), 5), "ms", 30)
    ws = words_grid(250)
    row("text", "detect_table (2000 palavras)", timed(lambda: textlayer.detect_table(ws), 5), "ms", 80)
    row("text", "select_between (2000 palavras)", timed(lambda: textlayer.select_between(ws, (30, 30), (500, 5000)), 5), "ms", 30)
    row("text", "words_text (2000 palavras)", timed(lambda: textlayer.words_text(ws), 5), "ms", 20)
    row("text", "sensitive (2000 palavras)", timed(lambda: textlayer.sensitive(ws), 5), "ms", 60)
    # desenho das caixas + seleção no overlay
    surf = solid(1440, 900)
    ov = Overlay(surf, lambda k, p: None, "ocr")
    ov.show_all()
    pump(.1)
    for n in (24, 120):
        ws = words_grid(n)
        ov.ts.phase, ov.ts.rect, ov.ts.crop = "ready", (50, 50, 1300, 850), solid(1250, 800)
        ov.ts.words, ov.ts.lines = ws, textlayer.group_lines(ws)
        ov.ts.sel = ws[: len(ws) // 2]
        out = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1440, 900)
        row("text", "quadro do overlay pronto, %d linhas, metade selecionada" % n, timed(lambda: ov.on_draw(ov.da, cairo.Context(out)), 8), "ms", 16.7)
    ov.ts.phase = "scan"
    ov.ts.t0 = time.monotonic()
    row("text", "quadro do anel de varredura", timed(lambda: ov.on_draw(ov.da, cairo.Context(out)), 10), "ms", 16.7)
    ov.destroy()


def g_ocr():
    if not textlayer.services.ocr_available():
        print("tesseract ausente: pulando")
        return
    for name, path, budget in (("700x450 (texto)", "ocr-input.png", 1500), ("tabela 4x3", "ocr-table.png", 1500), ("em branco 500x300", "ocr-blank.png", 1200),
                               ("página 1920x1080 (lorem)", "ref/lp-clean.png", 6000)):
        p = SHOTS + path
        if not os.path.exists(p):
            continue
        s = from_png(p)
        t = time.perf_counter()
        words = textlayer.ocr_surface(s)
        row("ocr", "ocr_surface " + name, (time.perf_counter() - t) * 1000, "ms", budget, "%d palavras" % len(words))


def g_anim():
    """Cadência real da animação no X (sem GPU): intervalo entre quadros do timer de 16 ms durante a varredura."""
    from captura.overlay import Overlay
    ov = Overlay(solid(1440, 900), lambda k, p: None, "ocr")
    ov.show_all()
    pump(.2)
    frames = []
    mark = [0.0]

    def before(da, cr):
        mark[0] = time.perf_counter()
        return False

    def after(da, cr):
        frames.append((time.monotonic(), (time.perf_counter() - mark[0]) * 1000))
        return False
    # os handlers do GTK rodam na ordem de conexão; "before" precisa vir antes do on_draw do overlay (já conectado), então
    # medimos pelo intervalo entre quadros e pelo custo chamando on_draw à parte
    ov.da.connect_after("draw", after)
    out_s = cairo.ImageSurface(cairo.FORMAT_ARGB32, 1440, 900)
    ov.ts.result = None
    ov.ts.start((200, 200, 900, 600))
    ov.ts.scan_end = time.monotonic() + 30           # mantém a varredura rodando durante a medição
    ov.start_anim()
    c0 = PROC.cpu_times()
    run_loop(1.5)
    c1 = PROC.cpu_times()
    ts = [f[0] for f in frames]
    gaps = sorted((b - a) * 1000 for a, b in zip(ts, ts[1:]))
    durs = sorted(timed(lambda: ov.on_draw(ov.da, cairo.Context(out_s))) for _ in range(30))
    if gaps:
        row("anim", "quadros desenhados por segundo na varredura", len(frames) / 1.5, "fps", None, "alvo ~60; sem GPU/compositor")
        row("anim", "intervalo mediano entre quadros", gaps[len(gaps) // 2], "ms", 20)
        row("anim", "p95 do intervalo entre quadros", gaps[int(len(gaps) * .95)], "ms", 40)
        row("anim", "p95 do custo de desenho de um quadro", durs[int(len(durs) * .95)], "ms", 16.7)
    row("anim", "CPU durante a varredura animada", ((c1.user + c1.system) - (c0.user + c0.system)) / 1.5 * 100, "%", 60)
    ov.destroy()
    from captura import menus
    from captura.window import EditorWindow
    menus.ANIMATE = True
    w = EditorWindow(shared_app())
    w.show_all()
    w.load_surface(solid(700, 450))
    pump(.4)
    cpu0 = PROC.cpu_times()
    t = time.perf_counter()
    for _ in range(5):
        w.popup_more(w.btn_more)
        pump(.35)
        m = getattr(w, "_cur_menu", None)
        if m:
            m.close_popup()
        pump(.1)
    cpu1 = PROC.cpu_times()
    row("anim", "CPU gasta pela animação de abrir menu (5x)", ((cpu1.user + cpu1.system) - (cpu0.user + cpu0.system)) * 1000 / 5, "ms/menu", 120)
    w.destroy()
    menus.ANIMATE = os.environ.get("CAPTURA_NO_ANIM") != "1"


def g_leak():
    from captura.overlay import Overlay
    from captura.window import EditorWindow
    app = shared_app()

    def cycle_overlay(i):
        ov = Overlay(solid(1440, 900), lambda k, p: None, "ocr" if i % 2 else "snip")
        ov.show_all()
        pump(.03)
        if i % 2:
            ov.ts.reset()
        ov.destroy()
        pump(.02)

    def cycle_window(i):
        w = EditorWindow(app)
        w.show_all()
        w.load_surface(solid(1280, 720))
        w.canvas.items = [annot.Stroke("pen", [(10 * j, 5 * j) for j in range(40)], "#e61b1b", 4)]
        pump(.03)
        w.destroy()
        pump(.02)

    for label, fn, n in (("overlay (criar/destruir)", cycle_overlay, 40), ("EditorWindow (criar/carregar/destruir)", cycle_window, 40)):
        for i in range(25):
            fn(i)                                   # aquecimento: o alocador sobe ao pico (a RSS estabiliza depois)
        gc.collect()
        tracemalloc.start(8)
        base_snap = tracemalloc.take_snapshot()
        r0, f0, t0, w0 = rss(), PROC.num_fds(), PROC.num_threads(), gtk_objects()
        samples = []
        for i in range(n):
            fn(i)
            if i % 10 == 9:
                gc.collect()
                samples.append(rss())
        print("         série RSS (MB) a cada 10 ciclos:", " ".join("%.0f" % x for x in samples))
        gc.collect()
        r1, f1, t1, w1 = rss(), PROC.num_fds(), PROC.num_threads(), gtk_objects()
        snap = tracemalloc.take_snapshot()
        tracemalloc.stop()
        slope = (samples[-1] - samples[0]) / max(1, len(samples) - 1) / 10 if len(samples) > 1 else 0
        row("leak", label + " RSS após %d ciclos" % n, r1 - r0, "MB", 25, "inicial %.0f MB; %.2f MB/ciclo na 2ª metade" % (r0, slope))
        row("leak", label + " descritores de arquivo", f1 - f0, "fds", 5)
        row("leak", label + " threads", t1 - t0, "thr", 2)
        row("leak", label + " widgets Gtk vivos", w1 - w0, "obj", 60, "(coletados com gc)")
        top = snap.compare_to(base_snap, "lineno")[:3]
        for s in top:
            if s.size_diff > 200 * 1024:
                print("         tracemalloc:", str(s)[:150])


def g_idle():
    from captura.window import EditorWindow
    w = EditorWindow(shared_app())
    w.show_all()
    w.load_surface(solid(1280, 720))
    pump(.5)
    PROC.cpu_percent(None)
    t0 = time.perf_counter()
    c0 = PROC.cpu_times()
    run_loop(5.0)
    c1 = PROC.cpu_times()
    el = time.perf_counter() - t0
    row("idle", "CPU do editor aberto e parado (5 s)", ((c1.user + c1.system) - (c0.user + c0.system)) / el * 100, "%", 2)
    w.btn_text.set_active(True) if False else None
    from captura.overlay import Overlay
    ov = Overlay(solid(1440, 900), lambda k, p: None, "snip")
    ov.show_all()
    pump(.5)
    c0 = PROC.cpu_times()
    t0 = time.perf_counter()
    run_loop(4.0)
    c1 = PROC.cpu_times()
    row("idle", "CPU do overlay parado (4 s)", ((c1.user + c1.system) - (c0.user + c0.system)) / (time.perf_counter() - t0) * 100, "%", 3)
    ov.destroy()
    w.destroy()


def g_fuzz():
    """Eventos aleatórios (2500 no overlay em cada ferramenta + cliques em todos os botões do editor); nenhuma exceção Python, nenhum CRITICAL."""
    from captura.overlay import Overlay
    from captura.window import EditorWindow
    from unittest.mock import patch
    from gi.repository import Gdk

    class E:
        pass

    def ev(x, y, b=1):
        e = E()
        e.x, e.y, e.button, e.state, e.keyval = x, y, b, 0, 0
        return e

    exc = []
    HOOK.clear()
    # autoteste dos coletores: um handler que falha e um aviso GLib têm de ser vistos
    b = Gtk.Button()
    b.connect("clicked", lambda *_: 1 / 0)
    b.clicked()
    box, lab = Gtk.Box(), Gtk.Label()
    box.add(lab)
    box.add(lab)                                          # aviso GTK conhecido (vai ao stderr; perf.sh conta e espera ver este)
    pump(.05)
    row("fuzz", "autoteste: exceção dentro de handler GTK é capturada", len(HOOK), "de 1", None)
    if len(HOOK) != 1:
        row("fuzz", "COLETOR DE EXCEÇÕES NÃO FUNCIONA", 1, "!", 0)
    HOOK.clear()
    app = shared_app()
    for name in ("start_capture", "toast_in_window", "get_window", "handle_image", "ocr_current"):
        if not hasattr(app, name):
            setattr(app, name, lambda *a, **k: None)           # o app de teste não tem as ações do CapturaApp
    rnd = random.Random(7)
    ws = words_grid(10)
    for tool in ("snip", "ocr", "color"):
        for shape in ("rectangle", "freeform", "window", "fullscreen"):
            settings["shape"], settings["mode"] = shape, rnd.choice(["photo", "video"])
            ov = Overlay(solid(1440, 900), lambda k, p: None, tool)
            ov.show_all()
            pump(.05)
            with patch("captura.overlay_text.textlayer.ocr_surface", return_value=ws), \
                 patch("captura.overlay_text.textlayer.services.ocr_available", return_value=True):
                for i in range(600):
                    a = rnd.random()
                    x, y = rnd.randint(-20, 1460), rnd.randint(-20, 920)
                    try:
                        if a < .15:
                            ov.on_press(ov.da, ev(x, y))
                        elif a < .3:
                            ov.on_release(ov.da, ev(x, y))
                        elif a < .9:
                            ov.on_motion(ov.da, ev(x, y))
                        elif a < .95:
                            e = ev(x, y); e.keyval = rnd.choice([Gdk.KEY_a, Gdk.KEY_c, Gdk.KEY_e, Gdk.KEY_Return, Gdk.KEY_Down]); e.state = rnd.choice([0, Gdk.ModifierType.CONTROL_MASK])
                            ov.on_key(ov, e)
                        else:
                            ov.set_tool(rnd.choice(["snip", "ocr", "color"]))
                        if i % 25 == 0:
                            pump(.01)
                    except Exception as ex:                       # noqa
                        exc.append("overlay %s/%s: %r" % (tool, shape, ex))
                        break
                    if ov._done:
                        break
            if not ov._done:
                ov.destroy()
            pump(.02)
    pump(.3)
    exc += ["handler GTK: " + h for h in HOOK]
    row("fuzz", "overlay: exceções em 12 combinações x 600 eventos", len(exc), "exc", 0)
    HOOK.clear()
    for e in exc[:5]:
        print("         ", e)
    # editor: aciona todos os botões
    settings["shot_autocopy_edits"] = False
    w = EditorWindow(shared_app())
    w.show_all()
    w.load_surface(solid(900, 600))
    pump(.4)
    exc2 = []
    from captura import services
    with patch.object(services, "copy_surface"), patch.object(services, "notify"), patch.object(w, "save_as", return_value=True), \
         patch.object(w, "open_dialog"), patch("subprocess.Popen"):
        btns = [o for _n, o in vars(w).items() if isinstance(o, Gtk.Button)]
        for rd in range(3):
            rnd.shuffle(btns)
            for b in btns:
                try:
                    if b.get_sensitive() and b.get_mapped():
                        b.clicked()
                        pump(.02)
                    m = getattr(w, "_cur_menu", None)
                    if m is not None and m.get_window() is not None:
                        m.close_popup()
                        pump(.02)
                    for fl in getattr(w, "_flyout", None) and [w._flyout] or []:
                        fl.close_popup()
                except Exception as ex:                          # noqa
                    exc2.append("%s: %r" % (b.get_accessible().get_name() if b.get_accessible() else b, ex))
            # eventos aleatórios no canvas
            c = w.canvas
            for _ in range(300):
                try:
                    x, y = rnd.randint(0, 900), rnd.randint(0, 600)
                    kind = rnd.random()
                    if kind < .3:
                        c.on_press(c, ev(x, y))
                    elif kind < .6:
                        c.on_motion(c, ev(x, y))
                    else:
                        c.on_release(c, ev(x, y))
                except Exception as ex:                          # noqa
                    exc2.append("canvas: %r" % (ex,))
                    break
            pump(.1)
    pump(.3)
    exc2 += ["handler GTK: " + h for h in HOOK]
    row("fuzz", "editor: exceções em %d botões x3 rodadas + 900 eventos de canvas" % len(btns), len(exc2), "exc", 0)
    for e in exc2[:6]:
        print("         ", e)
    w.destroy()
    pump(.1)


GROUPS = dict(import_=g_import, window=g_window, draw=g_draw, overlay=g_overlay, text=g_text, ocr=g_ocr, anim=g_anim, leak=g_leak, idle=g_idle, fuzz=g_fuzz)
ORDER = ["import_", "window", "draw", "overlay", "text", "ocr", "anim", "idle", "leak", "fuzz"]

if __name__ == "__main__":
    want = [a.rstrip("_") for a in sys.argv[1:]] or [g.rstrip("_") for g in ORDER]
    app = shared_app()
    app.apply_theme = theme.apply
    theme.apply()
    settings["theme"] = "light"
    for g in ORDER:
        if g.rstrip("_") in want:
            print("\n== %s ==" % g.rstrip("_"), flush=True)
            try:
                GROUPS[g]()
            except Exception as e:
                import traceback
                traceback.print_exc()
                row(g.rstrip("_"), "EXCEÇÃO NA BATERIA", 1, "exc", 0, repr(e)[:100])
    bad = [r for r in ROWS if not r[5]]
    json.dump(REPORT, open(os.path.join(HERE, "perf_report.json"), "w"), indent=1)
    print("\n%d medições, %d fora do orçamento" % (len(ROWS), len(bad)))
    for r in bad:
        print("  ✗ %s/%s = %.2f %s (orçamento %s)" % (r[0], r[1], r[2], r[3], r[4]))
    os._exit(1 if bad else 0)
