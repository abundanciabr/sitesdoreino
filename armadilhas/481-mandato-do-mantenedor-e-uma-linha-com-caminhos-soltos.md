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
licao: O portão lê `Mandato-do-mantenedor:` com uma regex de UMA linha e compara os caminhos com `.split()`. Mandato em parágrafo esconde os caminhos das linhas de baixo; vírgula colada (`ci/,`) nunca casa; e prefixo pela metade (`ci/tests`) também não, porque só valem o padrão do CODEOWNERS com barra (`ci/`) ou o caminho exato do arquivo. Uma linha, palavras soltas. Receita em CAMINHO-DOURADO.md R14.
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

A terceira forma de errar não tem nada a ver com pontuação: é escrever um
prefixo pela metade. O portão compara cada arquivo do PR com duas formas, e só
com elas: o padrão do CODEOWNERS com a barra final (`ci/`) ou o caminho exato
do arquivo (`ci/tests/test_chaves_do_gateway_no_deploy.py`). `ci/tests` é uma
linha só, palavra solta, sem vírgula, e mesmo assim não é nenhuma das duas, então
reprova igual. Foi o que quase pulou o PR #1686 poucas horas depois de esta
armadilha nascer. O prefixo intermediário é o mais caro dos três porque parece
obviamente certo.

O formato que passa, pronto para colar, e a lista do que é CODEOWNERS hoje
estão na receita R14 do `CAMINHO-DOURADO.md`. A fonte da verdade dos caminhos
é `.github/CODEOWNERS`, nunca uma cópia da lista.
