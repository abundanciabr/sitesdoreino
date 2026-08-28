# O registro do livro não pode viajar no PR de outra célula — `painel/` conta como a célula `admin`

**Sintoma:** você fez o gesto de sempre — código da célula + registro em
`painel/registros/` + `node painel/gerar_manifesto.js` — e o portão reprova com
uma mensagem que não fala de painel nenhum:

```
ERROR — o diff toca 2 células e este job testa uma só.
O escopo completo não seria verificado. 1 PR = 1 célula (RITOS.md §1).
...
CELULA: admin   N: 2
```

O `ci-celula` fica **verde** (ele testou a sua célula), e quem reprova é o
`ci-celula-gate`. Fácil de ler como defeito do portão, porque a sua mudança
tocou uma célula só — e tocou mesmo.

**Causa:** `ci/ci.py::celulas_tocadas` mapeia **`painel/` ⇒ célula `admin`**, e
o mapeamento é correto: a `admin` SERVE o painel do dono atrás do login, e a
pasta entra na imagem dela no build (é por isso que `deploy-celula.yml` tem
`painel/**` nos `paths`). Então um PR com `services/<outra>/**` + `painel/**`
toca **duas** células, e o portão de "1 PR = 1 célula" reprova — corretamente.

**A consequência que não é óbvia, e é a regra que fica:**

| Célula do PR | O registro do livro pode ir junto? |
|---|---|
| `admin` | **sim** — `painel/` É a `admin`, continua sendo 1 célula |
| qualquer outra (`alunos`, `funil`, `sugestoes`, `identidade`, …) | **não** — vira PR separado |
| nenhuma (lei, `contracts/`, `docs/`) | **sim** — não há célula no diff |

Ou seja: o gesto "registrar é parte de terminar a tarefa" continua obrigatório,
mas em PR de célula que não seja a `admin` ele é um **segundo PR**, logo depois
do merge do primeiro. Não é burocracia inventada: é o mesmo desenho que os PRs
#291/#292 (contrato da fila + livro) já tinham usado.

**Não tente contornar** tirando `painel/` do mapeamento ou pedindo label: o
mapeamento é o que faz o painel online acompanhar o livro. Quem tem de mudar é
a forma de entregar, não o portão.

**Mecânica, quando você já commitou tudo junto** — o commit do livro é sempre o
último, então:

```bash
git reset --hard <commit-do-codigo>     # solta o commit do livro
git push --force-with-lease             # o PR volta a ser de 1 célula
# depois do merge: ramo novo a partir de origin/main, só com o registro
```

Guarde o arquivo do registro antes do `reset --hard` — ele some junto. E ao
recriá-lo, **confira o número**: entre um PR e outro é comum outra sessão ter
gravado o `NNN` que você tinha escolhido (`armadilhas/085` e `/150`).

**Origem:** lote das categorias de usuário, 28/08/2026 — PR #345, célula
`alunos`. O `ci-celula` verde ao lado do `ci-celula-gate` vermelho foi o que
mais atrasou o diagnóstico.
