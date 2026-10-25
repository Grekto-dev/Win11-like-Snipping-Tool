"""Geometria medida (px) na Ferramenta de Captura do Windows 11 (janela 984x683, tema claro, escala 100%).

Todas as coordenadas são relativas ao canto superior esquerdo da janela. `canvas` é a origem do
quadro 20x20 onde o ícone foi ajustado contra a referência (ver ~/snip-tool-research/iconlab.py).
"""
W, H = 984, 683
TITLE_H = 32
TB_Y = 32            # topo da faixa de ferramentas
TB_H = 46            # altura da faixa (até a linha separadora em y=78)
LINE_Y = 78

# (tile x, y, w, h)  /  origem do canvas 20x20 do ícone
NEW = dict(tile=(16, 38, 40, 32), canvas=(25, 43))
PHOTO = dict(tile=(72, 38, 38, 32), canvas=(81, 43))
VIDEO = dict(tile=(110, 38, 38, 32), canvas=(119, 45))
SHAPE = dict(tile=(164, 38, 46, 32), canvas=(170, 45), chev=(188, 46))
DELAY = dict(tile=(220, 38, 46, 32), canvas=(226, 44), chev=(244, 46))
OCR_SEP_X = 283
OCR = dict(tile=(292, 38, 40, 32), canvas=(302, 44))

CENTER_X = 351       # esquerda do grupo central (centrado entre os grupos esquerdo e direito)
CENTER_W = 336
PEN = dict(tile=(351, 36, 36, 36), canvas=(360, 44))
HL = dict(tile=(391, 36, 36, 36), canvas=(400, 44))
ERASER = dict(tile=(431, 36, 36, 36), canvas=(439, 44))
SHAPES = dict(tile=(471, 36, 36, 36), canvas=(479, 44))
SEP1_X = 515
CROP = dict(tile=(524, 36, 36, 36), canvas=(532, 44))
TEXT = dict(tile=(565, 36, 36, 36), canvas=(573, 45))
SEP2_X = 608
UNDO = dict(tile=(615, 36, 36, 36), canvas=(623, 44))
REDO = dict(tile=(650, 36, 36, 36), canvas=(658, 44))
TOOL_CHEV_DX, TOOL_CHEV_DY = 8, 22      # canvas do chevron sob a ferramenta ativa, relativo ao tile
SEP_Y, SEP_H = 42, 24

RIGHT_X = 763
RIGHT_W = 221
EXT = dict(tile=(764, 36, 36, 36), canvas=(772, 44))
SAVE = dict(tile=(805, 36, 36, 36), canvas=(813, 44))
COPY = dict(tile=(845, 36, 36, 36), canvas=(853, 44))
SHARE = dict(tile=(886, 36, 36, 36), canvas=(894, 45))
SEP3_X = 929
MORE = dict(tile=(940, 36, 36, 36), canvas=(948, 51))

# barra de título
CAPTION_W = 46
ICON_X, TITLE_X = 8, 29

# cartão de informação (relativo à janela)
INFO_CARD = (5, 84, 974, 120)
INFO_ICON = (22, 102)           # 15x15
INFO_TITLE_CX, INFO_TITLE_CY = 53, 109.5
INFO_DESC_CY = 132.7
INFO_LINK_CY = 169.5
INFO_CLOSE_CENTER = (953, 108)
FONT_PX = 14

# ---- estado vazio (sem captura): "Novo" com rótulo desloca o grupo esquerdo em +42 px
EMPTY_DX = 42
EMPTY_NEW_W = 82
EMPTY_NEW_LABEL_X = 52          # x da haste do "N" do rótulo "Novo" (53)
EMPTY_OCR = dict(tile=(326, 38, 36, 32), canvas=(334, 44))
EMPTY_OCR_SEP_X = 318
EMPTY_TEXT_BBOX = (344, 640, 360, 373)     # x0,x1,y0,y1 do texto central
