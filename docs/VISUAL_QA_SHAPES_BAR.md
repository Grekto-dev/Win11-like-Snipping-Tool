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
