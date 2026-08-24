<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.14  ·  referencias antigas "ARMADILHAS §4.14" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.14 Mudar um template Django preservando saída BYTE-IDÊNTICA: as tags coladas, não em linha própria

**Sintoma:** um teste de regressão que compara a página renderizada byte a byte
quebra com uma linha em branco a mais (ou um comentário inesperado), mesmo com
toda a lógica nova dentro de `{% if %}` cujo ramo falso "não muda nada".
**Causa dupla:** (1) comentário HTML (`<!-- -->`) é TEXTO — vai inteiro para a
saída renderizada; anotação de template que não pode aparecer usa
`{% comment %}…{% endcomment %}`. (2) Tag de bloco em linha própria deixa a
quebra de linha ÓRFÃ na saída: em `…>\n{% if x %}\n<link>\n{% endif %}\n<title>`,
o `\n` antes do `{% if %}` e o de depois do `{% endif %}` ficam FORA do bloco —
com a condição falsa a saída ganha uma linha em branco que não existia.
**Solução:** cole a tag de abertura no fim da linha anterior e a de fechamento
imediatamente antes da quebra que já existia
(`…initial-scale=1">{% if x %}\n  <link …>{% endif %}\n  <title>`): ramo falso
reproduz o original byte a byte, ramo verdadeiro emite linhas completas. Vale
para `{% comment %}` também. De quebra: o Django lê template em modo texto
(universal newlines), então a saída renderizada é SEMPRE LF — mesmo com o
working tree do Windows em CRLF — e a comparação byte a byte é estável entre a
máquina local e o CI Linux.
**Onde está aplicado:** `services/funil/templates/base_mobile.html` (emissão
SEO i18n condicionada a site registrado, com regressão byte-idêntica em
`tests/test_i18n_http.py`).
**Origem:** despacho funil/i18n-fundacao (23/08/2026) — a primeira versão usou
comentário HTML e derrubou a regressão na hora.
