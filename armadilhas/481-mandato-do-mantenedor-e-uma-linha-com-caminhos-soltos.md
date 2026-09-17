---
schema_version: 2
armadilha: 481
estado: guardada
degrau: 4
confianca: estrutural
custo_por_queda: alto
gatilho:
  - .github/CODEOWNERS
  - ci/pr.py
  - ci/mergear.py
  - contracts/
  - infra/
sinal:
  - "falta mandato do dono para"
guarda:
  tipo: CI
  dono: ci/mergear.py
  detector: checar_mandato
licao: O portão lê `Mandato-do-mantenedor:` com uma regex de UMA linha e compara os caminhos com `.split()`. Mandato em parágrafo deixa os caminhos nas linhas de baixo, invisíveis; vírgula depois do caminho (`CAMINHO-DOURADO.md,`) vira token com vírgula, que nunca casa. Escreva o mandato numa linha só, com os caminhos como palavras soltas e sem vírgula entre eles. Receita em CAMINHO-DOURADO.md R14.
---

# O mandato do mantenedor é uma linha só, e os caminhos são palavras soltas

Quem escreve `Mandato-do-mantenedor:` escreve como se escreve para gente: um
parágrafo com o pedido, e a lista de caminhos separada por vírgulas, porque é
assim que se lista em português. As duas coisas derrubam o pouso, e nenhuma
delas aparece em check vermelho.

O leitor é `checar_mandato`, em `ci/mergear.py`:

```python
mandato = re.search(r"^Mandato-do-mantenedor: (.{20,})$", corpo, re.MULTILINE)
...
any(alvo in mandato.group(1).split() for alvo in (padrao, caminho))
```

A regex termina em `$` com `re.MULTILINE`: ela captura a primeira linha e para
ali. Caminho escrito na segunda linha do parágrafo não existe para o portão. E
a comparação é `.split()`, palavras separadas por espaço, com igualdade exata:
o token `CAMINHO-DOURADO.md,` tem uma vírgula colada e jamais é igual a
`CAMINHO-DOURADO.md`.

O custo medido: o PR #1684 ficou com os 8 checks verdes, `mergeStateStatus`
`CLEAN`, e a varredura do pouso o pulou por 19 minutos, sem uma linha de log
(esse silêncio é a armadilhas/482). O conserto foi reescrever o mandato numa
linha só, com os caminhos como palavras soltas.

O formato que passa, pronto para colar, e a lista do que é CODEOWNERS hoje
estão na receita R14 do `CAMINHO-DOURADO.md`. A fonte da verdade dos caminhos
é `.github/CODEOWNERS`, nunca uma cópia da lista.
