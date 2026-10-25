# Ferramenta de Captura (Linux Mint / Cinnamon, X11)

Recriação livre da Ferramenta de Captura do Windows 11, observada em uma VM Windows.
Não contém código nem recursos da Microsoft; ícones e interface são originais.

- Captura: retângulo, janela, tela inteira e forma livre; atraso 3/5/10 s; Super+Shift+S.
- Editor: caneta, marca-texto (multiplicar), borracha, formas, corte, desfazer/refazer, zoom.
- Seletor de cores, Extrator de Texto (OCR), gravação de tela (ffmpeg), configurações, tema claro/escuro.

## Uso
    ./bin/captura            # janela
    ./bin/captura --snip     # sobreposição de captura
    ./bin/captura --color | --ocr | --record

Dependências: python3-gi, gir1.2-gtk-3.0, gir1.2-wnck-3.0, gir1.2-notify-0.7, python3-cairo.
Opcionais: `tesseract-ocr tesseract-ocr-por tesseract-ocr-eng` (OCR), `ffmpeg` (gravação).

Licença: GPL-3.0-or-later.
