---
schema_version: 2
armadilha: 200
estado: guardada
degrau: 3
confianca: estrutural
custo_por_queda: alto
guarda:
  tipo: CI
  dono: ci/muralha-do-indice.sh
sinal: null
---

# A pista devolveu seu PR por conflito em `armadilhas/INDICE.md` — o gerado viajava no Git, e toda armadilha nova reescrevia o arquivo inteiro

**Sintoma:** a pista de pouso devolve o PR e o motivo é sempre o mesmo arquivo,
que você nem editou à mão:

```
CONFLICT (content): Merge conflict in armadilhas/INDICE.md
Automatic merge failed; fix conflicts and then commit the result.
```

Às vezes ele vem acompanhado de `armadilhas/GUARDAS.json`. Você resolve
regenerando, empurra, e o PR volta a ser devolvido na passagem seguinte — porque
outro robô do mesmo lote acabou de acrescentar a armadilha DELE.

**Medido em 30/08/2026**, num lote de 4 robôs em paralelo: **dois dos quatro PRs
foram devolvidos pela pista por este conflito** — o #571 uma vez e o #573 **duas**
(registro `20260830-024`).

**Causa — três coisas verdadeiras ao mesmo tempo, nenhuma delas com defeito:**

1. `armadilhas/INDICE.md`, `armadilhas/GUARDAS.json` e `armadilhas/SINAIS.json`
   são **gerados** por `ci/indice_de_armadilhas.py` a partir de
   `armadilhas/NNN-slug.md`.
2. A lei desta casa **MANDA** todo robô acrescentar uma armadilha ao fim de cada
   tarefa (`CLAUDE.md`). Não é eventual: é o caminho normal de todo despacho.
3. Cada entrada nova reescreve os três arquivos **inteiros** — a tabela ganha uma
   linha, o rodapé muda a contagem (`**190 entradas** — …`, a linha que TODO PR
   toca), e os dois JSON ganham um bloco no fim do array. Números consecutivos
   do almoxarife (196, 197) põem as linhas novas uma ao lado da outra, dentro do
   mesmo hunk.

O resultado: **dois robôs colidem sem ter escrito uma linha em comum**. O conflito
não é de conteúdo, é do formato — e não adianta ser mais rápido, porque cada robô
do lote acrescenta a sua.

**Isto é a `armadilhas/156` de novo, com outro arquivo.** Lá era `painel.html` e
`livro-AAAAMM.js`; um PR de 4 arquivos levou oito tentativas. A Onda 3 do
`PLANO-MESTRE-ROBOS-SEM-COLISAO.md` curou aquele caso e nomeou o desenho — e
ninguém foi procurar o **outro** arquivo do repositório com exatamente a mesma
anatomia. É a categoria "sessões paralelas" da `RETROSPECTIVA-FASE-D`: o catálogo
cura o caso, só o padrão cura a classe.

**Solução (30/08/2026, TAR-022) — o mesmo desenho da Onda 3, copiado, não
reinventado:**

| peça | quem faz |
|---|---|
| fonte multiescritor | `armadilhas/NNN-slug.md` — um arquivo por entrada, só se acrescenta |
| materialização de escritor único | `ci/muralha-do-indice.sh` em todo PR · o `SessionStart` de `.claude/settings.json` · `python ci/indice_de_armadilhas.py` na mão |
| validação independente | a mesma muralha, no passo que pergunta ao `git ls-files` — fora do gerador |
| degrau local | `.githooks/pre-commit` barra `git add -f` (escape: `PERMITIR_GERADO_DAS_ARMADILHAS=sim`) |

**A diferença que quase matou o remédio, e como ela foi resolvida.** O painel é
uma tela; o índice é lido por HUMANO e por AGENTE no começo de **toda** tarefa. Um
gerado fora do Git simplesmente **não existe** num checkout novo. Duas correções
tornaram isso seguro:

- `ci/indice_de_armadilhas.py --tambem-aqui` materializa em DUAS árvores: a do
  próprio arquivo (o clone principal — é de lá que `ci/sino_das_armadilhas.py` lê,
  porque o hook o chama por `${CLAUDE_PROJECT_DIR}`) e a de onde o comando foi
  chamado (o worktree do agente, que é onde ele vai abrir o índice). É o que o
  `SessionStart` roda.
- O modo de falha que sobra é **barulhento**: arquivo ausente dá erro na hora e a
  correção é uma linha. O conflito diário era **silencioso** até a pista devolver
  o PR — e devolvia o de outra pessoa junto.

**O que NÃO tentar:** `git show origin/main:armadilhas/INDICE.md` responde
`fatal: path 'armadilhas/INDICE.md' does not exist in 'origin/main'`. O índice não
está mais no Git. Rode `python ci/indice_de_armadilhas.py` (ou `make indice`) e
abra o arquivo.

**Por que esta entrada não tem `sinal`, declarado em vez de fingido:** a
assinatura natural seria a mensagem do `git show` acima — mas
`ci/sino_das_armadilhas.py` ignora de propósito todo comando cujo texto casa
`armadilhas/`, `INDICE.md`, `SINAIS.json` ou `GUARDAS.json`, para não tocar o sino
quando alguém está lendo o próprio catálogo. Um `sinal` aqui seria uma promessa
que o sino nunca cumpriria. Quem guarda esta lição é a muralha, não o sino.

**Prova (30/08/2026, dois robôs simulados no mesmo commit-base):**

```
ANTES  (gerados no Git)     robô A commita 2 arquivos, robô B commita 2
                            git merge → CONFLICT (content) in armadilhas/INDICE.md   exit 1
DEPOIS (gerados fora)       robô A commita 1 arquivo,  robô B commita 1
                            git merge → Merge made by the 'ort' strategy            exit 0
```

**Origem:** TAR-022, aberta a partir do lote de 4 robôs de 30/08/2026 (PRs #571 e
#573). **Categoria** (`RETROSPECTIVA-FASE-D`): sessões paralelas · garantia sem
mecanismo.
