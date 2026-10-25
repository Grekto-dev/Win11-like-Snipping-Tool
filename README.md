# Ferramenta de Captura (Linux Mint / Cinnamon, X11)

Recriação independente, em desenvolvimento, da experiência da Ferramenta de
Captura do Windows 11, observada em uma VM Windows. **O projeto não é oficial e
não possui afiliação nem endosso da Microsoft.**

A implementação do aplicativo é própria. Os recursos redistribuídos de terceiros
são os ícones **Fluent UI System Icons** (Microsoft, MIT) e a fonte **Selawik**
(Microsoft, SIL OFL 1.1). Os avisos e as licenças estão descritos em
`THIRD_PARTY_NOTICES.md`; não são recursos extraídos do aplicativo proprietário
do Windows. Há também SVGs próprios desenhados para esta implementação.

## Estado do projeto

Há caminhos implementados para:

- Captura retangular, de janela, de tela inteira e de forma livre; atraso de 3/5/10 s.
- Editor com caneta, marca-texto, borracha, formas, corte, desfazer/refazer e zoom.
- OCR com Tesseract, gravação de tela com ffmpeg, configurações e temas claro/escuro.

Isso **não significa equivalência completa** com o Windows. A comparação visual
e a auditoria de funcionalidades continuam em andamento. Entre as pendências
estão a barra de Formas e suas opções, ações de texto com seleção/destaque das
palavras reconhecidas, animações e uma bateria funcional completa. A interface
não deve ser apresentada como idêntica nem o aplicativo como concluído.

As evidências e limitações da rodada de menus/paletas estão em
`docs/VISUAL_QA_MENUS_PALETTES.md`.

## Uso

```sh
./bin/captura             # janela principal
./bin/captura --snip      # sobreposição de captura
./bin/captura --color     # seletor de cores
./bin/captura --ocr       # captura para OCR
./bin/captura --record    # gravação
```

Dependências GTK: `python3-gi`, `gir1.2-gtk-3.0`, `gir1.2-wnck-3.0`,
`gir1.2-notify-0.7` e `python3-cairo`.

Opcionais por funcionalidade: `tesseract-ocr`, `tesseract-ocr-por` e
`tesseract-ocr-eng` para OCR; `ffmpeg` para gravação.

Os testes de interação X11 também utilizam `python3-xlib`. Execute os testes
com `/usr/bin/python3`, uma sessão X11 acessível e configuração temporária para
não alterar as preferências do usuário.

## Licença e atribuição

O código próprio do aplicativo é disponibilizado sob **GPL-3.0-or-later**;
consulte `LICENSE`. Os componentes de terceiros conservam suas próprias
licenças e avisos:

| Componente | Titular / origem | Licença incluída |
|---|---|---|
| Fluent UI System Icons | Microsoft Corporation | `third_party/LICENSE-fluentui-system-icons.txt` — MIT |
| Selawik | Microsoft Corporation | `third_party/LICENSE-selawik-OFL.txt` — SIL OFL 1.1 |

O ícone `ic_fluent_timer_5_20_regular.svg` é uma adaptação local do timer de
3 segundos da biblioteca Fluent, com o algarismo redesenhado. Consulte
`THIRD_PARTY_NOTICES.md` para os caminhos, as modificações e as origens.
