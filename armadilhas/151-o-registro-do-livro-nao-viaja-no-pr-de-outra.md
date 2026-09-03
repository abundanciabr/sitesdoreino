# O registro do livro não pode viajar no PR de outra célula — `painel/` conta como a célula `admin`

> **Atualizada em 03/09/2026 — a causa raiz não existe mais, esta armadilha é histórico.**
> A cerca "1 PR = 1 célula" (`RITOS.md §1`) que gerava o erro abaixo **caiu em
> 29/08/2026, na Onda 5 do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`**
> (confira `ci/cerca-de-celula.sh`: hoje ele só reprova por causa da label
> `contrato`, não por número de células no diff). Desde então, `CLAUDE.md`
> (seção "O livro de ocorrências é obrigatório") descreve a regra atual sem
> ressalva por célula: **"o registro EMBARCA no próprio PR, antes do pedido de
> pouso"**, qualquer que seja a célula tocada.
>
> Medido de novo em 03/09/2026, PR #909 (`services/notificacoes` +
> `painel/registros/` no mesmo PR): `ci/mergear.py --conferir` não reclamou de
> cerca nenhuma, só cobrou o registro faltando — e aceitou normalmente depois
> dele entrar no mesmo PR.
>
> A única exceção que continua de pé é PR tocando `contracts/`, que segue o
> Rito de Contrato próprio (`RITOS.md §3`) e não é o caso descrito aqui.
>
> **Não siga a tabela nem o passo "mecânica" abaixo** — hoje eles descrevem um
> trabalho (separar em dois PRs, ou um `git reset --hard` para soltar o commit
> do livro) que é desnecessário e pode jogar fora commit bom por engano. O
> resto deste arquivo fica como registro histórico: por que o erro existia, e
> por que `painel/` mapeia para a célula `admin` (esse mapeamento em si
> continua verdadeiro, e ainda importa para o `deploy-celula`).

**Sintoma (histórico — não ocorre mais desde a Onda 5):** você fez o gesto de
sempre — código da célula + registro em `painel/registros/` +
`node painel/gerar_manifesto.js` — e o portão reprovava com uma mensagem que
não falava de painel nenhum:

```
ERROR — o diff toca 2 células e este job testa uma só.
O escopo completo não seria verificado. 1 PR = 1 célula (RITOS.md §1).
...
CELULA: admin   N: 2
```

O `ci-celula` ficava **verde** (ele testou a sua célula), e quem reprovava era
o `ci-celula-gate`. Fácil de ler como defeito do portão, porque a sua mudança
tocava uma célula só, e tocava mesmo.

**Causa (ainda verdadeira hoje, só a consequência mudou):**
`ci/ci.py::celulas_tocadas` mapeia **`painel/` ⇒ célula `admin`**, e o
mapeamento é correto: a `admin` SERVE o painel do dono atrás do login, e a
pasta entra na imagem dela no build (é por isso que `deploy-celula.yml` tem
`painel/**` nos `paths`). Um PR com `services/<outra>/**` + `painel/**` toca
**duas** células — isso continua verdade. O que mudou é que, depois da Onda 5,
tocar duas células num PR deixou de ser motivo de reprovação por si só; o
`ci-celula-gate` de hoje testa o escopo completo do diff em vez de recusar por
contagem de células.

**A tabela abaixo é a regra ANTIGA, mantida só para quem está lendo o
histórico — não aplique:**

| Célula do PR | O registro do livro podia ir junto? (regra até 29/08/2026) |
|---|---|
| `admin` | sim, `painel/` É a `admin`, continuava sendo 1 célula |
| qualquer outra (`alunos`, `funil`, `sugestoes`, `identidade`, …) | não, exigia um PR separado |
| nenhuma (lei, `contracts/`, `docs/`) | sim, não havia célula no diff |

**A regra de hoje é uma linha só:** o registro do livro embarca no mesmo PR
que o código, em qualquer célula, exceto PRs de `contracts/` (que seguem
`RITOS.md §3`). Ver `CLAUDE.md` e `painel/LEIA-ME.md`.

**Mecânica antiga (não use mais)** — quando a cerca existia e alguém já tinha
commitado tudo junto, o contorno era soltar o commit do livro com
`git reset --hard` e reenviar em dois PRs. Isso descartaria trabalho bom hoje,
porque não há cerca para contornar: se o portão reprovar um PR que toca
`painel/` + outra célula, o motivo é outro (ex.: registro realmente faltando,
ou algo em `contracts/`) e o registro pede investigar essa mensagem, não
separar o PR por reflexo.

**Origem:** lote das categorias de usuário, 28/08/2026, PR #345, célula
`alunos`. O `ci-celula` verde ao lado do `ci-celula-gate` vermelho foi o que
mais atrasou o diagnóstico na época. **Correção:** 03/09/2026, depois de medir
diretamente no PR #909 que a ressalva por célula não existe mais.
