# Verificação visual e regressões

## Referência

Windows 11, Microsoft.ScreenSketch 11.2608.41.0, VM `windows11`.
As capturas de pesquisa ficam em `~/snip-tool-research/shots/`; nenhum recurso do Windows é usado pelo aplicativo.

A árvore de acessibilidade do original confirmou a barra de Formas com Quadrado,
Oval, Linha reta, Seta, Preencher e Contorno. O original também possui Emoji,
ainda não implementado nesta recriação. O painel Linux é um popover compacto;
não é uma cópia exata do mecanismo flutuante do Windows.

## Ajustes

- Configurações em coluna única; Sobre no final, sem a antiga lateral.
- Espaço reservado para expansores em todas as linhas: interruptores e estados alinhados.
- Chevron sincronizado com a expansão, inclusive quando o interruptor é usado.
- Seletor de tema e seu menu com contraste nos temas claro e escuro.
- Ícones atualizados na troca de tema ao vivo (referência retida até o destroy do Gtk.Image).
- Formas: seletor horizontal; preenchimento opcional; cor e espessura do contorno em menu próprio.
- Mudanças de estilo de uma forma selecionada entram no histórico Desfazer/Refazer.

## Exercitado na interface

- Troca Claro → Escuro → Claro, conferindo ícones Voltar, microfone e áudio.
- Abertura dos painéis Preencher e Contorno.
- Desenho de um retângulo com preenchimento azul e contorno vermelho.
- Salvar como em PNG pelo diálogo real; arquivo decodificado com Pillow,
  1440×900 e 39.295 pixels da cor de preenchimento escolhida.

## Testes automatizados

Use o Python do sistema; a suíte precisa de um DISPLAY X11 e configurações temporárias
para não alterar suas preferências:

```bash
cfg=$(mktemp -d "${TMPDIR:-$HOME/.cache}/captura-tests.XXXXXX")
DISPLAY=:0 XDG_CONFIG_HOME="$cfg" /usr/bin/python3 -m unittest discover -s tests -v
```

Testes: renderização de preenchimento preservando contorno; seletor compacto e troca de geometria;
preenchimento chegando à tela/exportação e histórico; recoloração de ícones após coleta do wrapper Python;
sincronização de chevrons das Configurações.

## Ressalva independente

Neste teste, a leitura do alvo `image/png` via xclip retornou um buffer vazio, embora
os formatos fossem anunciados e o aplicativo mostrasse o aviso de cópia. Não foi
tratado como sucesso nem como teste da exportação: o PNG exportado foi verificado
pelo fluxo Salvar como. A interoperabilidade com o gerenciador de clipboard ainda
precisa ser investigada separadamente.
