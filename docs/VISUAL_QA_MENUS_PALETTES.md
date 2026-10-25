# Rodada visual: menus e paletas — 2026-10-25

Estado: **parcial; não há equivalência completa nem aprovação visual do usuário**.

## Referências e método

VM Windows `windows11`, Ferramenta de Captura 11.2608.41.0, tema claro,
janela visível 984×683. Capturas de referência em
`~/snip-tool-research/shots/ref/`, origem (228,21). Implementação renderizada
por `uishot.py`; comparação por `regcmp.py`. MAE é a diferença média absoluta
RGB, 0–255, somente na região indicada: não representa a aplicação inteira.

| Estado | Região x0,y0,x1,y1 | MAE inicial nesta rodada | MAE final |
|---|---|---:|---:|
| Mais (⋯) | 640,60,984,320 | 8,31 | 6,72 |
| Formato | 140,20,340,200 | 12,25 | 7,01 |
| Atraso | 150,20,450,200 | 11,12 | 8,33 |
| Caneta | 200,78,540,540 | não medido antes da reconstrução | 2,45 |
| Marca-texto | 240,78,580,372 | não medido antes da reconstrução | 2,03 |

Persistem diferenças de fonte/rasterização, ícones de pasta, atalhos,
indicadores e posição do thumb do slider. Não chamar essas telas de idênticas.
Uma captura de marca-texto perdeu o popup e deu MAE 49,72; foi inspecionada,
descartada como estado incorreto e repetida. A próxima melhoria do harness é
rejeitar explicitamente estados com popup fechado, em vez de medir a tela errada.

## Mudanças verificadas

- Menus flutuantes sem seta GTK, com superfícies claro/escuro, item selecionado
  e barra azul medidos. Posicionamento acompanha a janela redimensionada e o
  botão de formato no estado vazio; popup limitado à área útil do monitor.
- Corrigidos: callback que podia repetir no idle do GLib; orçamento global
  mutável de retries; corte do rótulo da borracha; clique fora que não fechava o
  popup quando o alvo era outra janela do mesmo processo.
- Seis SVGs próprios para zoom, pastas, janela, tela inteira e forma livre,
  desenhados com primitivas vetoriais a partir da observação. Nenhum bitmap ou
  recurso proprietário do Windows copiado para o código.
- Paletas de caneta/marca-texto reconstruídas: largura 322 px; alturas 456 e
  288 px; círculos 36 px em alvos 40 px; passo de 52 px; anel de seleção;
  preview antes do slider. Atributos de acessibilidade em pt-BR.
- UIA da VM confirmou intervalos: caneta 1–24 (valor observado 4), marca-texto
  12–64 (valor observado 12). Cores confirmadas por amostragem dos centros.
- Testes usam configuração temporária. Testes XTEST exercitam seleção real de
  cor, Escape e clique externo. Suíte nesta rodada: 19 testes passando, sem
  avisos GTK/GLib na última execução. Compileall e diff --check passaram.
- Harness de teste de janela usa uma Gtk.Application compartilhada e encerra
  por run()/quit() para não deixar exportações D-Bus órfãs entre testes.

## Erro de referência descoberto

As capturas antigas `shapes-bar.png` e `text-actions.png` não demonstram os
estados pretendidos: o aviso de salvamento cobria Formas, e a imagem sem texto
não ativava OCR. Não utilizá-las como evidência de equivalência.

Novas observações:
- `ref/shapes-bar-noinfo.png`: aviso fechado, barra de Formas efetivamente
  visível em y≈85; contém Emoji, Quadrado, Oval, Linha reta, Seta, Preencher,
  Contorno. A implementação ainda usa popover; não está equivalente.
- `ref/text-actions-noinfo.png`: toast "Nenhum texto ou código QR foi
  detectado." Uma imagem de texto controlada é necessária para investigar
  seleção/destaque/ocultação de dados; isso ainda está pendente.
- `ref/menu-eraser-noinfo.png`: caixa 228 px, rótulo completo
  "Apagar todas as marcações".

## Próximo escopo (não concluído)

1. Barra de Formas e submenus, incluindo estado sem aviso e comportamento Emoji.
2. Modo de corte: barra inteira (Aplicar, Cancelar, Zoom), não apenas centro.
3. Configurações, overlay de captura/gravação e temas nos mesmos estados.
4. Ações de texto com imagem de teste, destaque/seleção, copiar/ocultar dados.
5. Auditoria funcional completa e duas rodadas de regressão, incluindo animações,
   exportação, clipboard de imagem, áudio e múltiplas janelas.
