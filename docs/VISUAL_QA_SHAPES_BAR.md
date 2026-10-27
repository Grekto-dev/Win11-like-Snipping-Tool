# QA visual — barra de Formas no conteúdo

Referência: Ferramenta de Captura 11.2608 (Windows 11, VM `windows11`), janela normalizada em (220,20) 1000×691,
origem do conteúdo visível (228,21), tema claro, escala 100 %. Capturas em `~/snip-tool-research/shots/ref/sb-*.png`
(geradas por `sbstates.py`); comparação por `uishot.py` + `regcmp.py` / `inkcmp.py` / `blobcmp.py`.

## Geometria medida (coordenadas de janela)

| Elemento | Medida |
|---|---|
| Barra | 486×48 (borda #ededed 1 px, fundo #f9f9f9, raio 8), centrada na largura, borda superior em y=85 (6 px abaixo do topo do conteúdo) |
| Botões | 36×36 (raio 4), passo 40: Emoji x=6; Quadrado/Oval/Linha/Seta x=55/95/135/175 (relativos à barra); y=6 |
| Separadores | x=48 e x=217, y=12–36, #eaeaea |
| Ativo | borda 1 px #0067c0 + anel interno branco 1 px + fundo #f0f0f0; hover #f0f0f0 |
| Preencher / Contorno | sem caixa de hover; ícone em x=+13, texto em +38/+39, chevron 8×4 |
| Flyout de cores | caixa externa 314×374 (Preencher) / 314×497 (Contorno), borda #eaeaea, raio 8; topo 44 px abaixo do topo da barra; centrado no botão (+1,5) |
| Grade de cores | 6×5, discos de 32 px, passo 48, 1.º centro (36,62) do interior; anel de seleção 2 px #0067c0 com intervalo de 1 px; 1.ª célula "sem cor" |
| Opacidade | 1–100 %, trilho 12 px xadrez + degradê, x=17–294, polegar 22 px com ponto de 8 px |
| Tamanho (só Contorno) | 1–24 (padrão 4, lido por UIA), prévia de traço medida da referência |
| Emoji | caixa 242×122, grade 6×3 de células 40×40 sem margem, topo 52 px abaixo do topo da barra, centrada no botão |

## Resultado (MAE por região, 0–255)

| Estado | Região | MAE |
|---|---|---|
| Barra | (240,78)-(745,140) | 1,86 (antes dos ajustes 7,26) |
| Preencher aberto | interior da caixa | 1,58 |
| Contorno aberto | interior da caixa | 2,24 |
| Emoji aberto | interior da caixa | 5,36 |

Caixas de tinta de todos os 11 ícones/textos da barra coincidem com a referência ao pixel (exceto largura do
texto: "Preencher" 59 px contra 61 px na referência, por diferença Selawik × fonte do Windows). Os 28 discos de cor
coincidem ao pixel.

## Limites conhecidos

- O Windows usa emojis Fluent coloridos; usamos Noto Color Emoji. Posições dentro de ±1–2 px, arte diferente.
- Sombra projetada dos flyouts não reproduzida.
- Tema escuro: cores da barra derivadas (sem referência medida).
- O aviso (infobar) cobre a barra, como na referência.

# QA visual — modo de corte

Referência: `shots/ref/cr-*.png` (`crstates.py`, `crdrag.py`). Com a mesma imagem de entrada
(`shots/win-crop-input.png`, recorte 700×450 da própria referência) o estado "modo de corte" fecha em **MAE 0,30** na janela inteira.

| Elemento | Medida |
|---|---|
| Aplicar | caixa 85×32 em (401,38), ícone de visto 12×8 em +11,+13, texto em +33; hover #eaeaea raio 4; dica "Aplicar (Enter)" |
| Cancelar | caixa 95×32 em (486,38), ícone × 11×11, texto em +34; dica "Cancelar (Esc)" |
| Zoom | caixa 56×32 em (920,38); lupa+ e chevron; abre menu de 184×138 centrado no botão, topo 44 px abaixo |
| Menu de zoom | "100%" Ctrl+0, "Aplicar zoom" Ctrl++, "Reduzir" Ctrl+- (desabilitado enquanto ajustado), "Ajustar à janela" Ctrl+1 |
| Escurecimento | fora do corte = 40 % do brilho original (preto 60 %), medido por razão de pixels |
| Borda | linha branca de 1 px dentro da aresta |
| Alças | cantos em L: faixa de 4 px, braços de 24 px, de [aresta−3, aresta+1) (topo/esquerda) e [aresta−1, aresta+3) (base/direita); barras 24×4 nas arestas, totalmente fora |
| Outros grupos | esquerda fica invisível e inerte (mantém o espaço); Salvar/Copiar/Compartilhar/Mais somem |

Menu Mais → Zoom: submenu de 184×138, encostado à direita do menu principal (−1 px) e 5 px mais baixo.

## Diferença conhecida (não reproduzida)

Depois de redimensionar o corte, o Windows reposiciona a vista (imagem deslocada ≈ +73,+48 px) e mostra barras de rolagem:
o conteúdo vira um `ScrollViewer` com margens. Aqui a vista continua fixa.

## Defeito real encontrado e corrigido no caminho

Fechar a janela com um menu/flyout aberto deixava o `grab` do popup ativo no processo (testes seguintes falhavam de
forma intermitente). `EditorWindow` agora fecha `_cur_menu`, `_emoji_picker` e `_tool_pop` ao destruir.

# QA visual — Configurações

Referência: `shots/ref/set-*.png` (`setstates*.py`). Medido e reproduzido: cabeçalho que rola junto com o conteúdo
(seta com tinta em x=16–31, título Semibold 19,5 px em x=56), cartões de 872 px em x=56 com 4 px de intervalo,
linhas de 62/63 px, interruptor 40×20 em x=750 + rótulo "Ativado/Desativado" em x=802, seta de expansão centrada em x≈903,
painel interno (path + "Alterar" + botão "Abrir pasta" 84×32 em x=767), seção "Sobre este app" em negrito,
cartão **Tema do aplicativo** recolhido com painel de três botões de opção (Claro, Escuro, Usar configuração do sistema; 20 px, passo 40).

| Estado | MAE (janela inteira) |
|---|---|
| Topo (`set-top`) | 4,98 (antes 9,87) |
| Tema aberto (`set-theme-open2`, cartão alinhado em y=244) | 4,99 |

## Diferenças deliberadas / pendentes
- Linha "Atalhos": o Windows mostra um link para as configurações do Windows; aqui continua um interruptor funcional para a tecla Imprimir.
- O Windows tem "Corretor de cores para capturas de tela HDR"; não se aplica ao Linux e foi omitido.
- Seção "Sobre": textos, links e licenças são os do projeto (GPL, Fluent, Selawik), sem botão "Enviar comentários" (não há remoto público).
- Painel de borda: sem seletor de cor/slider da referência medido (cor de swatch 38×38 e slider ainda do GTK).

# QA visual — Ações de texto (OCR)

Referência: Windows 11, imagem `ocr-input.png` aberta com Ctrl+O (`ocrwin5.py`, `ocrwin6.py`), estados em `shots/ref/ocr-*.png`.
Medido e reproduzido: barra de 550×48 (Copiar todo o texto | Copiar como tabela [desabilitado] | Redação rápida ▾), imagem esmaecida a #919191,
uma caixa branca de cantos arredondados por linha (padding 11/12/10/11 px), seleção por arrasto em ordem de leitura (#b2d6f2 com texto #0e324e),
duplo clique seleciona palavra, Ctrl+A / Ctrl+C / Ctrl+R, menu de contexto (Copiar texto, Selecionar tudo, Redigir texto), menu ▾ com
"Endereços de email" / "Números de telefone" (marcados) / "Remover todas as redações", balão "Certifique-se de que todas as informações confidenciais foram editadas."

| Estado | MAE (janela inteira) |
|---|---|
| barra | 1,30 |
| seleção parcial | 1,70 |
| redigido (parcial) | 1,75 |
| menu ▾ | 1,60 |
| Redação rápida + balão | 2,19 |
| menu de contexto | 2,39 |

Diferenças restantes: o Windows usa o OCR dele (caixas de linha ±1–2 px diferentes do Tesseract); "Copiar como tabela" fica desabilitado
(o Windows só o habilita quando detecta tabela; não implementado); ícones redesenhados (não são os da Microsoft).

# QA visual — Overlay de captura e gravação

Referência: Windows 11 (`ovwin*.py`, `shots/ref/ov-*.png`); nosso lado renderizado em Xephyr 1440×900 sobre a área de trabalho do Windows (`ovrun.sh`, `ovshot.py`, `recshot.py`, `ovcmp.py`).
Medido: escurecimento 60%; barra principal 330×48 (13 px do topo, centrada) com segmento foto/vídeo; estado "Iniciar" 284×44
([● Iniciar] 00:00:00 [mic] [áudio] | [fechar]); região de vídeo travada com borda tracejada 4/3 e 12 alças brancas de 6 px;
menu de formas; Esc fecha de imediato; barra de gravação 258×48 (pausar, parar, tempo, mic, áudio | descartar); moldura rosa pontilhada de 2 px (#bf6881).

| Estado | MAE |
|---|---|
| barra ociosa (região da barra) | 6,9 |
| região de vídeo travada | 0,43 |
| menu de formas | 8,6 |
| moldura de gravação | 0,07 |
| barra de gravação | 13,9 (região pequena; deslocamentos de 1–2 px nos ícones) |

Mudanças de comportamento: pausar/continuar gravação de verdade (trechos unidos com concat), parar a gravação fora da thread da interface,
janelas do app voltam ao fim da gravação, forma livre no modo vídeo trava o retângulo envolvente, tentativas de grab por overlay.
Pendente: contagem regressiva 3-2-1 não comparada (o Windows pediu permissão de microfone na VM durante a captura); mic/áudio não alternam durante a gravação.

# QA — Animação e comportamento do OCR (Ações de texto)

Gravação do Windows quadro a quadro (~30 fps, `rec.ps1` + `upsrv.py` + `animrec.py`; análise `framediff.py`, `animcmp.py`) contra o nosso app no Xephyr (`animshot.py`).
Medido e implementado (`captura/text_anim.py`):
- **Varredura:** borda em gradiente cônico de 6 px (azul `#4a50ec` → violeta → coral `#fb7382`) girando no sentido horário, 1 volta a cada 1500 ms;
  dura 1,155 s + 20,5 ms por linha reconhecida (1, 7 e 24 linhas medidas: 1155, 1265, 1621 ms).
- **Revelação:** a borda some em ~250 ms, a imagem esmaece até `#919191` em ~860 ms (curva medida) e a barra de ações desce de 54 px acima em ~250 ms.
- **Saída do modo:** instantânea, sem animação; a caneta fica selecionada.
- **Imagem sem texto:** a varredura termina, o modo sai, "Copiar como tabela" e o botão de texto ficam desabilitados e aparece o aviso "Nenhum texto ou código QR foi detectado."
- **Tabela:** células viram caixas separadas; "Copiar como tabela" copia `text/html` (mesmo HTML do Windows) + texto com tabulações.
- **Menus:** abertura revelada de cima para baixo em ~250 ms (curva medida no menu Mais); balão da Redação rápida cresce a partir da ponta em ~160 ms.
- **Parágrafos:** Tesseract em modo 4 gera as mesmas quebras de parágrafo do Windows ("Copiar todo o texto").

| Comparação (MAE, janela de conteúdo) | valor |
|---|---|
| varredura (5 instantes) | 0,75–0,92 |
| revelação (0–1000 ms) | 1,3–4,3 |

Diferenças restantes: o Tesseract não lê dígitos soltos em tabelas ("4", "1"); a tarja da redação aparece de uma vez (o Windows faz fade de ~250 ms);
animação de seleção/cópia (mudanças < 0,5 de MAE) não replicada; o OCR do Windows é mais rápido que o Tesseract em imagens grandes (a varredura espera o OCR).

# Referência — Extrator de texto dentro da captura (Windows, página "lorem ipsum")

Gravado com `snip-tool-research/lprec.py lp-flow` (427 quadros, ~30 fps, região 200,0 760×440) + capturas `shots/ref/lp-*.png`.
Fluxo: janela → **Novo** → overlay → **Extrator de texto** → arrastar um retângulo → arrastar dentro do texto detectado.
Tempos relativos à gravação (ms); a pasta `frames/lp-flow` guarda os quadros.

1. **Novo (clique ≈3,55 s):** a janela do app some em ~130 ms (fade); ~0,5 s depois o overlay aparece **de uma vez** (sem fade): tela escurecida
   (brilho 238→95, ≈ preto a 60%) e a barra superior de captura surge no mesmo quadro.
2. **Extrator de texto (clique ≈5,6 s):** a barra é trocada **instantaneamente** (sem animação) por outra: `←` | `Copiar todo o texto` (desabilitado, cinza) | `⋯` | `✕`, centrada no topo (≈ x 558–882, y 13–62).
   O botão de texto aparece pressionado (cinza) um quadro antes. A escuridão não muda. Cursor: cruz (+).
3. **Arrasto (≈7,7–8,2 s):** o retângulo vira uma janela **sem escurecimento** (mostra a tela normal) com borda branca tracejada de 1 px; o texto dentro fica nítido; a barra segue desabilitada.
4. **Soltar (≈8,2 s):** surge uma borda de **gradiente** (azul→violeta→rosa/coral, ~4 px, em rotação) em volta da seleção durante o reconhecimento: de 8,37 s a ≈8,85 s (≈0,5–0,6 s);
   "Copiar todo o texto" **habilita** em ≈8,6 s (texto preto). Fim: a borda vira **branca grossa em L nos cantos + alças brancas nos meios das arestas** (cantos 3×... alças tipo pílula), contorno tracejado fino por dentro,
   e as **linhas de texto ficam em caixas brancas** sobre o fundo escurecido (a imagem fora das linhas permanece escura *dentro da seleção também*: só as linhas ficam claras).
5. **Arrastar dentro do texto (≈11,6–12,3 s):** o cursor vira I-beam; a seleção é feita **palavra a palavra em ordem de leitura** (da âncora ao cursor): realce azul claro `#b2d6f2` por linha, parcial na primeira/última linha; cresce a cada movimento.
6. **Soltar a seleção de texto (≈12,2 s):** aparece de uma vez, sem animação, uma **mini barra flutuante** (fundo `#f9f9f9`, cantos ~8 px, sombra suave, ≈ 89×47) com dois ícones: copiar `⧉` e QR/código `⠿`, **posicionada logo à direita e abaixo do ponto final do arrasto** (canto superior-esquerdo ≈ (fim.x, fim.y+4)); fica visível mesmo com o mouse longe.
   A seleção azul permanece; o botão da barra principal continua "Copiar todo o texto".
7. **✕:** o overlay inteiro fecha (menos de 1,5 s) e volta a janela "Pressione ⊞ + Shift + S" (a mesma do início).

# Referência — Extrator de texto numa área SEM texto (Windows)

Gravação `lprec_empty.py lp-empty` (402 quadros, região 0,0 1000×500) + capturas `ue-*.png`. Seleção arrastada em (40,140)→(200,340), margem branca da página.

**Seleção parcial (desenhada pelo usuário, `ue-0-current.png`):** só as linhas de texto que **cruzam** a seleção ficam em caixas brancas; as caixas são **recortadas pela borda da seleção** (não saem dela) e o texto fora da seleção
continua escuro. Linhas totalmente fora não aparecem. Alças/cantos: cantos em L brancos de ~5 px e alças-pílula no meio de cada aresta, contorno tracejado de 1 px por dentro.

**Sem texto, linha do tempo (ms):**
- ≈7,66–8,26 s: arrasto — o retângulo é uma janela sem escurecimento (branca na margem), tracejado fino.
- 8,42 s (soltar): a janela clara some **no mesmo quadro**; só fica um anel de gradiente (traço de 6 px, cantos arredondados ≈4 px, fora do retângulo: x 32–206, y 133–346 para a seleção 40–200 × 140–340),
  interior **escurecido** como o resto (#666666 = preto a 60%). Gradiente cônico `#4c50eb` (esq.) → `#a55af8` (topo) → `#fa7283` (dir.) → `#ad5bf9` (base), girando; dura **≈0,40 s** (8,42→8,82 s) e some **de uma vez**.
- 8,46 s: aparece o aviso **"Nenhum texto foi detectado"** — cartão branco `#ffffff`, 237×51 px, cantos 8 px, ícone de informação azul `#0078d4` (círculo 15 px, "i" branco) e texto 14 px `#1b1b1b`;
  centrado sob a barra (x 602–838 ≈ meio da barra 558–881; topo em y 73, a 11 px da barra que termina em 62).
  Entra **subindo ~23 px com fade em ~200 ms** (y 96→73 em 8,47→8,62 s), fica **≈2,9 s** e sai **descendo ~22 px com fade em ~150 ms** (11,53→11,62 s; some em 11,62 s). Total ≈3,15 s.
- A barra permanece `←  Copiar todo o texto (cinza/desabilitado)  ⋯  ✕`. **Nada** da seleção sobra: sem tracejado, sem alças. A tela fica só escurecida e o usuário pode arrastar de novo.

# Implementação — Extrator de texto na sobreposição (`captura/overlay_text.py`)

Medido contra `shots/ref/ov-ocr-*.png` (Xephyr 1440×900, `snip-tool-research/ovtext.py` + `ovcmp.py`):

| Estado | MAE |
|---|---|
| pronto (barra + caixas + alças), janela inteira | 0,70 |
| seleção de texto + mini barra | 1,16 |
| anel de varredura (área sem texto, ≈250 ms) | 1,74 |
| área sem texto, aviso + barra (tela toda) | 0,64 |

Fluxo implementado: barra `← | Copiar todo o texto | ⋯ | ✕` (324×50), arrasto sem escurecimento, anel de gradiente ao soltar, caixas recortadas 5 px dentro da seleção,
alças, seleção palavra a palavra, mini barra [copiar | QR] no ponto final, aviso "Nenhum texto foi detectado" (sobe/desce com fade), clique fora recomeça,
Ctrl+C/Ctrl+A, menu ⋯ (copiar automaticamente / remover quebras de linha), copiar fecha a sobreposição e mostra o toast "Texto copiado".
E2E real (`snip-tool-research/e2e.sh`): app aberto com `--ocr`, cliques/arrastos XTEST, clipboard conferido.
Não verificado/diferenças: ícone QR é só visual (a leitura de QR não está implementada); o toast só é translúcido com compositor.

## Ponteiros do Windows no fluxo de captura (medidos em `shots/ref/cur-*.png`)
| Situação | Ponteiro |
|---|---|
| Overlay em repouso; botão pressionado sem mover | cruz fina |
| Arrastando a seleção (assim que se move), durante a varredura, sobre as barras, sobre texto/seleção pronta | seta |
| Arrastando sobre o texto detectado (após mover) | I-beam |
| Sobre as alças da seleção do extrator (cantos / lados) | setas de redimensionar (⇔ ⇕ ↘ ↙) |
Alça arrastada: a seleção volta a ser janela clara, "Copiar todo o texto" desabilita e ao soltar refaz a varredura.
Implementado em `Overlay._wanted_cursor` (o grab do seat não usa cursor próprio, senão ele sobrepõe o da janela); verificado com XFixes (`curx.sh`).

`captura --capture` (`-c`): abre direto o overlay no modo captura (como Novo). Ao copiar texto, sem janela principal aberta, o programa fecha após o aviso (~3,8 s).

# Auditoria final: varredura visual + bateria de desempenho/depuração

**Varredura visual** (`snip-tool-research/sweep.py`: renderiza 28 estados e mede o MAE contra a referência do Windows)
- Editor, menus, flyouts, Formas, Corte e Ações de texto: MAE 0,5–2,4 (janela inteira de 984×683).
- Divergências conhecidas e intencionais: *menu Compartilhar* (o Windows abre a folha de compartilhamento do sistema; o nosso é um menu com 3 itens),
  *Configurações* (MAE 5–11: caminho/versão/"Sobre" são do Linux e falta a linha "Corretor de cores HDR", recurso exclusivo do Windows).
- Achados corrigidos: referência `ocr-select-all` estava capturada em estado errado (régua aberta), recapturada (41,4 → 1,7); `uishot.py` usava imagem de fundo diferente da referência (MAE inflado);
  **tema escuro**: o botão "Novo", separadores, hover e bordas tinham cores claras fixas no CSS — agora vêm da paleta (a numeração do tema claro não mudou).

**Bateria** (`scripts/perf.sh`, `scripts/perf_battery.py`, Xephyr isolado; relatório em `scripts/perf_report.json`): 55 medições com orçamento, 0 fora.
| Área | Antes | Depois |
|---|---|---|
| quadro do canvas 1080p (zoom ajustado) | 16,3 ms | 0,9 ms (imagem reduzida em cache) |
| zoom contínuo | 67 ms/quadro | 2,9 ms/quadro (caminho rápido + reconstrução depois do gesto) |
| quadro 3840×2160 | 35 ms | 0,9 ms |
| OCR página 1080p / 700×450 | 3,4 s / 0,78 s | 2,1 s / 0,48 s (modos 4 e 11 do Tesseract em paralelo) |
| varredura animada (CPU) | 31 % | 16–18 % (invalida só o anel) |
Sem vazamento em 40 ciclos de overlay/janela (RSS, descritores, threads, widgets). Fuzz: 7 200 eventos no overlay (12 combinações) e todos os botões do editor ×3 + 900 eventos no canvas: 0 exceções, 0 avisos Gtk.
`python -X dev` na suíte achou 2 vazamentos reais no gravador (pipe de comandos do FFmpeg e arquivo de log por segmento de pausa) — corrigidos e cobertos por teste.

# Idioma, "Após a captura", links e gravação de vídeo
- **Idioma** (`captura/i18n.py`, catálogos em `captura/data/i18n/*.json`, 235 mensagens): pt-BR, English (padrão), 中文, 日本語, Español, Français, Italiano.
  Troca ao vivo: widgets Gtk são "ganchados" (rótulos, botões, dicas, títulos, diálogos), o que é desenhado à mão passa por `draw_text` (que traduz e encolhe a fonte de 14 para 11 px / reticências se não couber; o português medido não muda).
  Novos textos de interface precisam entrar nos 6 catálogos e em `_msgids.json` (o teste `test_code_has_no_new_ui_string_outside_the_catalog` e `scripts/extract_i18n.py` avisam).
- **Após a captura** (`shot_after`): notificação (padrão) | abrir no editor | só copiar. A imagem é sempre copiada para a área de transferência.
- **Cursor de mão** nos links (`captura/cursors.py`).
- **Gravação de vídeo** (testes `test_video_recorder.py`, `test_video_app.py`): 11 bugs corrigidos (regiões inválidas, pausa curta que apagava a gravação, falha de união silenciosa, ffmpeg morto anunciado como "salvo", janelas do editor que não voltavam após falha, zumbis/órfãos, áudio ausente sem aviso).
  Em aberto: latência de ~0,5–0,8 s no 1º quadro do ffmpeg; queda do app com kill -9 deixa MP4 sem trailer em ~50% dos casos (solução possível: MP4 fragmentado); pausa bloqueia a UI até 13 s se o ffmpeg demorar; botões de microfone/áudio da barra de gravação não alteram a gravação em curso.
