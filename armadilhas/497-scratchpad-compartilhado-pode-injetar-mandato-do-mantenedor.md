---
schema_version: 2
armadilha: 497
estado: documentada
degrau: 9
confianca: alta
custo_por_queda: alto
guarda:
  tipo: nenhum
  motivo: o portao de pouso confere a PRESENCA e o FORMATO da linha Mandato-do-mantenedor no corpo do PR; ele nao tem como saber que o autor pretendia autorizar aquele caminho especifico, so que o texto apareceu la. Distinguir mandato escrito pelo dono de mandato que apareceu por colisao de arquivo exige a mesma disciplina de nome unico no scratchpad que ja guarda armadilhas/196 e 488, nao um novo portao.
sinal:
  - "^Mandato-do-mantenedor:"
gatilho:
  - ci/pr.py
  - ci/mergear.py
licao: "Corpo de PR compartilhado no scratchpad pode injetar Mandato-do-mantenedor: no PR de outra tarefa; checar_mandato le essa linha e libera CODEOWNERS no pouso automatico sem saber que o dono nao a escreveu. Nome unico por tarefa, e gh pr view --json body | grep Mandato-do-mantenedor depois de publicar."
---

# 497: Scratchpad compartilhado pode injetar `Mandato-do-mantenedor:` no corpo de outro PR

## Sintoma

`gh pr view 1773 --json body`, conferido em 19/09/2026: o corpo publicado do
PR #1773 (célula `catalogo`) começava com uma linha `Mandato-do-mantenedor:`
em coluna zero, autorizando `contracts/catalogo.openapi.yaml`. Esse trecho
não foi escrito pelo agente da célula `catalogo`; o `corpo.md` do scratchpad
compartilhado foi sobrescrito às 16:50 por outro despacho, três minutos
depois de o agente do `catalogo` ter escrito o dele, e `ci/pr.py` leu o
arquivo do vizinho no momento de publicar.

## Causa

A mesma raiz de `armadilhas/196` e `armadilhas/488` (scratchpad compartilhado
entre sessões irmãs, nome genérico sobrescrito entre escrita e leitura), mas
com uma consequência mais grave do que "corpo com o assunto errado":
`ci/mergear.py::checar_mandato` (linha 902) lê `Mandato-do-mantenedor:` do
corpo do PR no momento do pouso automático e, se o autor bate e o caminho
citado casa um arquivo tocado, libera a integração de um caminho protegido
por `CODEOWNERS` sem revisão humana. O portão confere presença e formato da
linha; ele não tem como saber que o dono nunca a escreveu. Uma colisão de
scratchpad vira, sem querer, uma autorização do dono no corpo de um PR que
integra sozinho.

## O que estava a um passo de acontecer

O PR #1773 não toca `contracts/`, então nada foi liberado indevidamente
desta vez, e o corpo já foi reescrito e conferido antes do pouso. Se o PR
sobrescrito tivesse tocado um caminho protegido, o pouso automático teria
integrado sem revisão, lendo uma autorização que ninguém deu.

## Solução

Duas partes, as duas obrigatórias:

- **Diretório próprio por tarefa** no scratchpad (`scratchpad/TAR-NNN/corpo.md`,
  nunca a raiz nem um nome genérico) para os quatro arquivos de entrada do
  `ci/pr.py`.
- **Conferir depois de publicar**, sempre, antes de deixar o pouso automático
  rodar:

```bash
gh pr view <N> --json body --jq .body | grep -n '^Mandato-do-mantenedor:'
```

Uma saída não vazia nesse grep, quando você não escreveu essa linha, é sinal
de colisão: corrija o corpo com `gh pr edit <N> --body-file <arquivo com nome
único>` antes de qualquer coisa.

## Evidência

PR #1773 (`catalogo`), corpo conferido por `gh pr view 1773 --json body` em
19/09/2026. Ver também `armadilhas/196` e `armadilhas/488` para o mecanismo
raiz do scratchpad compartilhado.
