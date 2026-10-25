# Avisos de componentes de terceiros

Este projeto é uma recriação independente para Linux. Não é o aplicativo
proprietário da Microsoft, nem um produto afiliado, certificado ou endossado
pela Microsoft. Os nomes de produtos citados identificam as referências
observadas e os componentes utilizados.

A licença do código próprio do aplicativo está em `LICENSE`. Ela não substitui
as licenças dos recursos de terceiros listados abaixo. Os textos completos dos
avisos/licenças acompanham esta árvore em `third_party/` e devem acompanhar os
respectivos recursos nas distribuições.

## Fluent UI System Icons

- Origem: repositório público `microsoft/fluentui-system-icons` no GitHub.
- Titular: **Copyright (c) 2020 Microsoft Corporation**.
- Licença: **MIT**, texto integral em
  `third_party/LICENSE-fluentui-system-icons.txt`.
- Arquivos de referência redistribuídos: `third_party/fluent-icons/*.svg`.
- Recursos utilizados pelo aplicativo: `captura/data/icons/fluent/*.svg`.

O renderizador pode redimensionar os SVGs e substituir as cores em memória
para acompanhar os temas e os estados dos controles. Isso não altera o texto
da licença nem remove o aviso de titularidade.

### Adaptação local identificada

`ic_fluent_timer_5_20_regular.svg`, presente nas duas pastas acima, foi adaptado
localmente de `ic_fluent_timer_3_20_regular.svg`: preserva o corpo do timer e
substitui o algarismo 3 por um traçado vetorial próprio do algarismo 5. Esta
adaptação conserva a atribuição e a licença MIT da biblioteca de origem.

Os SVGs em `captura/data/icons/custom/` são desenhos próprios da recriação,
não extrações de glifos ou imagens do executável proprietário. O diretório é
separado dos arquivos Fluent para distinguir sua procedência.

## Selawik

- Origem: repositório público `microsoft/Selawik` no GitHub.
- Aviso do titular:

  > Copyright 2015, Microsoft Corporation (www.microsoft.com), with Reserved Font Name Selawik. All Rights Reserved. Selawik is a trademark of Microsoft Corporation in the United States and/or other countries.

- Licença: **SIL Open Font License, Version 1.1**, texto integral em
  `third_party/LICENSE-selawik-OFL.txt`, incluindo o aviso original e o nome
  reservado.
- Arquivos incluídos em `captura/data/fonts/`:
  `selawk.ttf`, `selawkb.ttf`, `selawkl.ttf`, `selawksb.ttf`, `selawksl.ttf`.

O aplicativo registra as fontes no fontconfig do próprio processo por
`captura/fonts.py`; não precisa instalar a fonte no sistema. Os arquivos de
fonte mantêm a licença OFL e não são apresentados como recursos GPL do projeto.
Nenhuma fonte Segoe UI extraída do Windows é distribuída nesta árvore.

## Escopo da comparação com o Windows

As capturas de tela da VM utilizadas na pesquisa ficam fora da árvore do
aplicativo, em `~/snip-tool-research/`. A observação visual orienta o código e
os desenhos próprios; não converte recursos proprietários do aplicativo de
referência em componentes redistribuíveis deste projeto.
