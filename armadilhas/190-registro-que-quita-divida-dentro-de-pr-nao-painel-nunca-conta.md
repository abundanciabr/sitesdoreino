---
schema_version: 2
armadilha: 190
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `o portao ja diz a verdade sobre o que mede; o que faltava era a instrucao de ONDE por o registro. Uma muralha que adivinhasse a intencao de um registro (quitar divida x contar entrega) recusaria registro honesto, e recusa errada e mais cara que a volta perdida. A cura mora no texto e na mensagem da propria recusa.`
sinal: null
---

# `dívida do livro FAIL` que não sai por mais que você escreva o registro — a pista julga da `main`, não do seu PR

**Sintoma:** `ci/mergear.py <N> --conferir` na sua máquina diz **`dívida do livro
PASS — livro em dia`**, você pede pouso, e a pista devolve o PR com
**`dívida do livro FAIL — 1 merge(s) sem registro`** apontando um PR que o seu
registro cita, pelo número, na evidência. Você confere o arquivo, ele está lá,
está no ramo remoto, o `git ls-tree origin/<seu-ramo>` mostra. Pede pouso de
novo: **exatamente a mesma recusa, no mesmo PR**.

A tentação é chamar de corrida de tempo e tentar mais uma vez. Não é, e tentar
de novo custa outra volta inteira da pista.

**Causa — o juiz olha para outro lugar, e olha de propósito.**
`.github/workflows/pouso.yml` faz `actions/checkout` com **`ref: main`**, não com
o ramo do PR. Está comentado lá em cima: *"o job nunca faz checkout do código do
PR"* — é o que impede um PR de alterar o juiz que vai julgá-lo. Sem isso, um PR
poderia editar `ci/divida_do_livro.py` para se aprovar.

E `ci/divida_do_livro.py::numeros_citados()` lê **`painel/registros/` do
checkout em que está rodando**. Na sua máquina, isso é o seu ramo — com o
registro novo. Na pista, isso é a `main` — **sem** ele.

Em uma frase: **um registro que quita dívida não conta enquanto viaja dentro de
um PR. Ele precisa já estar na `main`.**

Isso não vale só para dívida: qualquer coisa que o portão de merge leia da
árvore é lida **da `main`**, não do seu PR. Já o `orçamento` e os `checks` são
lidos da API do GitHub sobre o PR — por isso alguns itens do mesmo relatório
enxergam o seu trabalho e outros não. A régua é: **o que vem de arquivo vem da
`main`; o que vem do GitHub vem do PR.**

**Solução — o registro que quita dívida vai SOZINHO, num PR só de `painel/`:**

```bash
git switch -c agent/painel/quitar-a-divida-do-<N> origin/main
# escreva SÓ painel/registros/AAAAMMDD-NNN-slug.js citando o #<N> na evidencia
python ci/mergear.py <esse-PR> --pousar     # pousa sozinho: so_toca_o_livro() o isenta
# depois que ele estiver na main:
git switch <seu-ramo> && git merge origin/main
python ci/mergear.py <seu-PR> --pousar
```

`ci/divida_do_livro.py::so_toca_o_livro()` isenta da conta o PR cujos arquivos
são todos de `painel/` — **ele é o registro**. É por isso que esse caminho
existe e é o único que fecha: o PR-registro não precisa de si mesmo na `main`
para passar.

Não confunda com a `armadilhas/185` (o registro existe mas **não cita o
número**) nem com a `140` (checkout atrasado faz a dívida parecer real quando
não é). A pergunta de triagem que separa as três:

```bash
grep -rl "pull/<N>\|#<N>" painel/registros/     # achou? entao nao e a 185
git ls-tree origin/main painel/registros/ | grep <seu-registro>   # vazio? e ESTA
```

Vazio na segunda linha significa: o registro existe no seu ramo e **não** na
`main`. É esta entrada, e a solução é o PR separado acima.

**Origem:** 29-30/08/2026, PR #566 (a tranca do número de armadilha). A dívida
era do #547, criada por outra sessão — e ela travava a porta de merge para
**todo mundo**, não só para quem a criou. Duas voltas completas da pista foram
gastas antes de a causa aparecer, e as duas devolveram exatamente a mesma
mensagem. O registro que a quitou foi ao ar sozinho no PR #567.
