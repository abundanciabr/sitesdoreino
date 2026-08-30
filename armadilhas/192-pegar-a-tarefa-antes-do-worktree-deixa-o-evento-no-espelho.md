---
schema_version: 2
armadilha: 192
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: ci/tests/test_fila.py
sinal:
  - `RECUSADO NO ESPELHO`
  - `COMPROVANTE ÓRFÃO`
---

# Você pegou a tarefa no balcão antes de criar o worktree — o evento nasceu no espelho e o seu PR vai sem ele, em silêncio

**Sintoma.** Você seguiu a ordem de partida do despacho à risca: primeiro
`python ci/fila.py pegar TAR-NNN --quem "..."`, depois
`git worktree add ../wt-<area>-<tarefa> ...`. No fim do trabalho,
`git diff --name-only origin/main...HEAD` mostra o registro e o evento de
conclusão — mas **não** o de reivindicação. O arquivo existe: ele está no
`git status` do **clone principal**, como `?? fila/eventos/AAAAMMDD-HHMMSS-TAR-NNN-reivindicada.json`,
numa pasta onde a muralha do RITOS §1 impede você de commitar qualquer coisa.

E **nada acusa**. `python ci/fila.py validar` responde `✅ Fila válida` com o
evento fora — medido em 30/08/2026: com o arquivo movido para fora,
`✅ Fila válida — 17 tarefa(s), 15 evento(s)`, exit 0. A muralha da fila do CI
chama esse mesmo validador. É falso-verde clássico (RETROSPECTIVA-FASE-D §1):
ausência de evidência não é evidência de sucesso.

**Causa — duas coisas verdadeiras que se somam:**

1. **`ci/fila.py` escreve o evento relativo ao repositório em que foi
   executado.** Rodou no clone principal, o arquivo nasce no clone principal.
   Não há nada de errado nisso; o script não tem como adivinhar em que worktree
   você vai trabalhar daqui a dez segundos.
2. **A ordem de partida canônica dos despachos garante que isso aconteça.** Ela
   manda pegar a tarefa no balcão *antes de tudo* — e "antes de tudo" inclui
   antes do worktree existir. O motivo da ordem é bom (se o balcão recusar, você
   para sem ter criado ramo nenhum), mas o efeito colateral é este.

**Por que a muralha da pasta compartilhada não pega.** Ela recusa
`Edit`/`Write` do harness e git de estado no clone principal
(`armadilhas/135`), e a própria 135 declara a fronteira honesta: **shell que
escreve por dentro de um script não passa por ela**. `ci/fila.py` é exatamente
isso. A recusa 🧱 que você espera nunca vem.

**O que se perde se ninguém notar.** A tarefa chega à `main` com `concluida` e
sem `reivindicada`. O estado calculado continua certo (concluída é concluída),
então nada quebra — mas o histórico de *quem pegou o trabalho e quando* some
para sempre, que é justamente o que o RITOS §5 peça 4 promete guardar: *"a
referência no servidor vale AGORA; o evento em `fila/eventos/` vale para
sempre"*. Promessa sem mecanismo (RETROSPECTIVA-FASE-D §2).

**Solução — duas linhas, e a primeira é a boa:**

```bash
# O CERTO: worktree primeiro, balcão de dentro dele.
git fetch origin
git worktree add ../wt-<area>-<tarefa> -b agent/<area>/<tarefa> origin/main
cd ../wt-<area>-<tarefa>
python ci/fila.py pegar TAR-NNN --quem "sessao-<area>-<data>"
```

A reserva é uma referência atômica no servidor do GitHub (`ci/reservar.py`) —
ela **não depende da pasta** de onde você pede. Inverter a ordem não enfraquece
a trava contra dois robôs na mesma tarefa: se o balcão recusar, você só terá um
worktree a mais para remover.

```bash
# O CONSERTO, se você já pegou no principal:
mv fila/eventos/<o-arquivo-que-o-balcao-imprimiu>.json ../wt-<area>-<tarefa>/fila/eventos/
```

O balcão **imprime o caminho** do arquivo que acabou de criar e diz
`(commite-o no seu PR)` — leia essa linha, não a pule. E antes de pedir pouso,
confira com os olhos:

```bash
git diff --name-only origin/main...HEAD    # tem TODOS os eventos da tarefa?
```

**A guarda, desde 30/08/2026 (TAR-018).** O buraco deixou de ser assumido:

- `criar`, `pegar` e `concluir` **RECUSAM no clone principal** (exit 1), e a
  recusa ensina as quatro linhas acima — ela diz, com todas as letras, que a
  TAREFA não foi recusada. Aviso em sombra não serviria aqui: o arquivo já
  teria nascido, e o robô nem consegue apagá-lo (medido no mesmo dia — o
  classificador de permissão recusou a limpeza ao robô da TAR-014).
- `validar` **diz em voz alta, em SOMBRA**, todo arquivo de `fila/eventos/` que
  o Git não conhece, nomeando cada um e o conserto. Não muda o veredito: é ali
  que mora o portão de CI, e regra nova nasce em sombra.
- `listar`, `validar` e `soltar` **continuam livres** no espelho — devolver à
  fila uma tarefa presa é gesto de emergência.
- `RITOS.md` §5 peça 1 passou a mandar **worktree primeiro, balcão depois**.

**Origem.** 30/08/2026, na TAR-016 (a medição dos três números da aba "Os
robôs", PR #571). O evento de reivindicação nasceu no clone principal e foi
movido à mão antes do primeiro commit; a falha silenciosa do validador foi
confirmada por teste — arquivo fora, `✅ Fila válida`, exit 0. A muralha que
curaria a classe ficou registrada como **TAR-018** na própria fila, em vez de
virar item de memória de sessão (RITOS §5 peça 2).
