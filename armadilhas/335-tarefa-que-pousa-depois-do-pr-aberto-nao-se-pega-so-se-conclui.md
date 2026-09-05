---
schema_version: 2
armadilha: 335
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: a recusa É o balcão funcionando (o PR aberto que cita a tarefa é a prova de que ela está em execução); o que faltava era saber de antemão que, num lote, a tarefa pode chegar à main depois do PR do robô, e que `concluir` sozinho fecha a conta
sinal:
  - "RECUSADO: TAR-\\d+ está 'em execução' \\(PR #\\d+\\)"
  - "RECUSADO: TAR-\\d+ não existe na fila"
---

# A tarefa pousou na `main` DEPOIS de o seu PR já estar aberto: o balcão recusa `pegar` com "está 'em execução'", e isso não é defeito, `concluir` sozinho fecha a conta

**Sintoma.** Você é um robô de lote. Na partida, `python ci/fila.py pegar TAR-NNN`
responde `RECUSADO: TAR-NNN não existe na fila`, porque a tarefa ainda viaja no PR
só-de-fila que a maestro está pousando naquele instante. O despacho previu isso e
mandou seguir o trabalho. Você abre o seu PR, o PR da fila mergeia, você faz
`git rebase origin/main`, a tarefa agora existe na sua árvore, e o `pegar`
responde outra coisa:

```
RECUSADO: TAR-149 está 'em execução' (PR #1049).
Só tarefa NA FILA se pega. Veja o quadro: python ci/fila.py listar --ao-vivo
```

O PR #1049 é o SEU. Nenhum evento de reivindicação vai existir, e o DoD do
despacho dizia "a TAR reivindicada e concluída pelo balcão".

**Causa.** O estado "em execução" do quadro ao vivo não sai dos eventos: sai de
`prs_citando_tarefas` em `ci/fila.py`, que lista os PRs ABERTOS e casa `TAR-NNN`
no título ou no nome do ramo. O seu PR já cita a tarefa, logo, para o balcão,
ela está em execução, e "só tarefa NA FILA se pega". A ordem canônica (pegar,
trabalhar, abrir o PR) supõe que a tarefa exista antes do PR; num lote em que a
fila e o trabalho pousam em paralelo, a ordem se inverte e a reivindicação fica
impossível por construção. A recusa está certa: o PR aberto é uma prova melhor
de "em execução" do que um evento escrito à mão.

**Solução.** Não repita o `pegar`, não abra outro ramo, não escreva o evento à
mão. Depois do rebase, vá direto ao fecho:

```bash
python ci/fila.py concluir TAR-NNN --quem <sessao> --evidencia <URL do PR> --verificado-em <AAAA-MM-DD>
python ci/fila.py validar          # ✅ Fila válida, e o aviso em SOMBRA do comprovante fora do Git
git add fila/eventos && git commit  # o evento viaja no seu PR (armadilhas/192)
```

`concluir` não exige reivindicação prévia, e o quadro passa a mostrar
`TAR-NNN [concluída · <sessao>] — <URL do PR>`. Medido em 05/09/2026 (TAR-149):
`✅ Fila válida — 141 tarefa(s), 233 evento(s)`, exit 0, e a muralha da fila
verde no PR.

**A espera pela tarefa tem teto, e o jeito autorizado é a sonda.** Entre "o PR
da fila ainda está aberto" e "posso concluir" não se fica em laço de `git
fetch`. Uma linha, pela ferramenta `Monitor`, com `timeout_ms` maior que o
teto:

```bash
python ci/esperar.py --sonda "git fetch origin -q && git cat-file -e origin/main:fila/tarefas/<arquivo-da-tarefa>.json" --teto 15 --dizendo "a TAR-NNN chegar na main pelo PR #<fila>"
```

A sonda roda com `shell=True` (no Windows, `cmd.exe`): por isso `git cat-file -e`
em vez de `ls | grep`, que não existe lá. O nome do arquivo da tarefa você lê no
ramo da maestro antes de ele mergear:
`git ls-tree --name-only origin/<ramo-da-fila> fila/tarefas/ | grep NNN-`.

**Origem.** TAR-149 (os cinco eventos v1 da célula `cursos`), 05/09/2026, lote
regido pela maestro com a fila no PR #1048 e o trabalho no PR #1049. Parente de
`armadilhas/192` (o evento da fila que nasce fora do PR): lá o comprovante
existe no lugar errado; aqui ele não existe, e está certo não existir.
