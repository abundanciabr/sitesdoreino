---
schema_version: 2
armadilha: 512
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/pr.py
sinal:
  - "recibo (excede|estoura) 1 ?kb"
  - ">= ?1024"
guarda:
  tipo: nenhum
  motivo: ci/pr.py aceita qualquer titulo e detalhe que passem o minimo de 80 caracteres; nao ha limite superior verificado antes do commit, e o estouro so aparece na gravacao do registro, tarde para reescrever com calma
licao: "O recibo de ci/pr.py soma titulo e detalhe no mesmo arquivo de registro, e o teto e 1 KB do arquivo inteiro, nao so do campo detalhe. Titulo longo (citando PR, tarefa e cinco adjetivos) ou detalhe no maximo dos 400 caracteres sugeridos, somados ao restante do molde, estouram o teto. Escreva titulo curto (ate 70 caracteres) e detalhe entre 80 e 400; meca com wc -c antes de rodar ci/pr.py."
---

# 512: o recibo de `ci/pr.py` estoura 1 KB quando título e detalhe são longos

**Data:** 26 e 27/09/2026 · **Onde:** `ci/pr.py`, obra Appmax (PRs #2158 e
#2159) · **Custo evitado:** recibo reescrito depois do PR já aberto, e uma
segunda rodada de validação só para trocar texto.

## Sintoma

Os PRs #2158 e #2159 tiveram o recibo do livro reprovado por tamanho: o
arquivo de registro gerado por `ci/pr.py` passou de 1 KB porque o título
citava a tarefa e o PR por extenso e o detalhe usava o teto de 400
caracteres sugerido pelo molde. Nenhum comando de validação falhou antes
disso: o estouro só aparece quando o gerador do painel mede o arquivo
final.

## Causa

`ci/pr.py` mede `MINIMO_DO_DETALHE = 80` (linha 322) mas não impõe um
teto superior a `--titulo` nem a `--detalhe`; o limite de 1 KB é do
arquivo de registro inteiro (título + detalhe + os demais campos do
molde), verificado tarde, na gravação. Título "para leigo" tentando
explicar tudo de uma vez, mais detalhe no máximo do intervalo sugerido
(80 a 400 caracteres), somam mais que o espaço que resta depois dos
campos fixos do molde.

## Solução

Antes de chamar `ci/pr.py`, meça os dois textos:

```bash
wc -c titulo.txt detalhe.txt
```

Título até 70 caracteres, sem repetir o número do PR ou da tarefa (o
recibo já os cita nos campos próprios). Detalhe no meio do intervalo
sugerido (80 a 250 caracteres é seguro), guardando julgamento extenso
para um registro à parte em `painel/registros/` quando o fato exigir
mais texto que o recibo comporta.

## Origem

PRs #2158 e #2159, obra Appmax, sessões de coordenação de 26 e 27/09/2026.
