"""Animação do modo Ações de texto, medida quadro a quadro no Windows 11 (gravação ~30 fps da VM).

Linha do tempo (t em ms):
  varredura   borda em gradiente cônico de 6 px ao redor da imagem, girando no sentido horário (1 volta a cada 1500 ms);
              dura até o OCR terminar e no mínimo MIN_SCAN (medido: 1155 ms em imagem pequena, 1265 ms com 7 linhas, 1621 ms com 24)
  revelação   (t=0 no fim da varredura) a borda encolhe e some em ~140 ms; a imagem esmaece até #919191 em ~860 ms
              (curva medida); a barra de ações desce de cima em ~250 ms
  saída       instantânea (um quadro): sem animação
"""
import math

MIN_SCAN = 1.155           # s (1 linha)
SCAN_BASE, SCAN_PER_LINE = 1.135, 0.0205      # s: duração medida da varredura = base + 20,5 ms por linha reconhecida (1, 7 e 24 linhas)


def scan_duration(n_lines):
    return max(MIN_SCAN, SCAN_BASE + SCAN_PER_LINE * n_lines)
ROTATION_MS = 1500.0
PHASE0 = 187.0             # graus: onde o azul está quando a borda aparece
BORDER = 6.0

# cores medidas a cada 10° (0° = azul; 180° = coral), sentido horário
PALETTE = ["4a50ec", "5551ed", "6152ef", "6c54f0", "7655f2", "8256f3", "8d57f5", "9a5af7", "a45af8", "af5cfa",
           "b95dfb", "c65ffd", "d160fe", "da62f1", "e266d5", "e96abb", "f16ea1", "f97286", "fb7382", "f26e9f",
           "ea6abc", "e166d9", "d861f6", "ce60fe", "c35efc", "b95dfb", "af5cfa", "a35af8", "9859f6", "8e58f5",
           "8256f3", "7755f2", "6d53f0", "6252ef", "5852ee", "4d4fec"]
_RGB = [tuple(int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)) for h in PALETTE]

# (ms, valor)
APPEAR = [(0, 4.5), (50, 5.7), (90, 6.7), (130, 6.2), (200, 6.0)]            # espessura da borda ao aparecer
COLLAPSE = [(0, 6.0), (48, 2.0), (96, 1.1), (130, 0.8), (190, 0.1), (250, 0.0)]                  # espessura ao sumir
DIM = [(-40, 0.0), (0, .08), (48, .25), (96, .33), (127, .43), (188, .53), (250, .63), (313, .72), (360, .78),
       (423, .84), (470, .87), (516, .91), (563, .94), (612, .955), (642, .96), (705, .98), (766, .99), (861, 1.0)]
BAR_OFFSET = [(-20, 54.0), (0, 37.0), (48, 12.0), (96, 6.0), (127, 3.0), (188, 1.0), (250, 0.0)]   # px acima da posição final
REVEAL_LAG = 30.0          # a captura de tela mede o início da revelação ~30 ms depois do instante real
REVEAL_MS = 861 + 30


def interp(keys, t):
    if t <= keys[0][0]:
        return keys[0][1]
    for (t0, v0), (t1, v1) in zip(keys, keys[1:]):
        if t <= t1:
            f = (t - t0) / (t1 - t0)
            return v0 + (v1 - v0) * f
    return keys[-1][1]


def palette_color(angle):
    """Cor (r, g, b) em 0-1 para um ângulo relativo ao azul, com interpolação linear."""
    a = (angle % 360.0) / 10.0
    i = int(a) % 36
    f = a - int(a)
    p, q = _RGB[i], _RGB[(i + 1) % 36]
    return tuple(p[k] + (q[k] - p[k]) * f for k in range(3))


def phase_at(t_ms):
    """Ângulo (graus, sentido horário) em que está o azul do gradiente."""
    return (PHASE0 + t_ms * 360.0 / ROTATION_MS) % 360.0


def scan_thickness(t_ms):
    return interp(APPEAR, t_ms)


def reveal_state(t_ms):
    """(espessura da borda, progresso do esmaecimento 0-1, deslocamento da barra em px) em t ms após o fim da varredura."""
    t_ms -= REVEAL_LAG
    return interp(COLLAPSE, t_ms), interp(DIM, t_ms), interp(BAR_OFFSET, t_ms)


def draw_border(cr, x0, y0, x1, y1, thickness, phase, steps=120):
    """Anel de `thickness` px fora do retângulo (x0,y0)-(x1,y1), preenchido com o gradiente cônico girando."""
    if thickness <= 0.05:
        return
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    cr.save()
    cr.rectangle(x0 - thickness, y0 - thickness, (x1 - x0) + 2 * thickness, (y1 - y0) + 2 * thickness)
    cr.rectangle(x0, y0, x1 - x0, y1 - y0)
    cr.set_fill_rule(1)                                   # EVEN_ODD
    cr.clip()
    far = math.hypot(x1 - x0, y1 - y0) + 40
    step = 360.0 / steps
    for k in range(steps):
        a0 = k * step
        a1 = a0 + step + 0.6                              # sobreposição para não deixar fresta
        r, g, b = palette_color(a0 + step / 2 - phase)
        cr.set_source_rgb(r, g, b)
        cr.move_to(cx, cy)
        cr.line_to(cx + far * math.cos(math.radians(a0)), cy + far * math.sin(math.radians(a0)))
        cr.line_to(cx + far * math.cos(math.radians(a1)), cy + far * math.sin(math.radians(a1)))
        cr.close_path()
        cr.fill()
    cr.restore()
