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
