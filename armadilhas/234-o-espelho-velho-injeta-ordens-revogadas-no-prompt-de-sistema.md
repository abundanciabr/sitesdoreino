---
schema_version: 2
armadilha: 234
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_muralha_pasta_compartilhada.py
sinal: null
---

# O clone principal injetou um `CLAUDE.md` REVOGADO no seu prompt de sistema — você obedeceu à regra certa do documento errado

**Sintoma:** você seguiu à risca uma instrução que estava no seu prompt de
sistema, e um portão do CI reprovou você **por causa dela**. O caso medido:

```
  entrada-nova  FAIL   número escolhido à mão: 219
```

O robô tinha feito exatamente o que leu: *"crie um arquivo novo
`armadilhas/NNN-slug.md` (NNN = próximo número livre)"*. Essa frase estava no
`CLAUDE.md` que ele recebeu. Ela tinha sido **revogada** — desde 29/08/2026 o
número se **pede** (`python ci/reservar.py numero armadilha`), e o `CLAUDE.md`
de `origin/main` já dizia isso.

Nada falhou no caminho. O agente não leu documentação velha por descuido: o
texto velho chegou até ele **antes de ele poder ler qualquer coisa**.

**Causa — e é estrutural, não descuido.** O harness injeta no prompt de sistema
de toda sessão e de todo subagente o `CLAUDE.md` **da pasta onde a sessão
nasce**. Sessões nascem no clone principal — que a `armadilhas/135` transformou
em **espelho** justamente para ninguém trabalhar nele. Espelho não se atualiza
sozinho: `git fetch` move as refs remotas, **não** o `HEAD` do checkout. Então:

| | de onde vem | quão fresco |
|---|---|---|
| as ORDENS (prompt de sistema) | `CLAUDE.md` do clone principal | **o que ele tiver** |
| a bancada (`git worktree add ... origin/main`) | `origin/main` | sempre fresquíssimo |

Medido em 30/08/2026: o clone principal estava **358 commits atrás**. A
divergência é **silenciosa por construção** — o agente não tem como saber que o
texto que ele recebeu foi revogado, porque para ele aquele texto *é* a lei.

**Por que é uma classe, e não este caso.** Não é sobre número de armadilha.
Enquanto o espelho ficar atrás, **toda lei nova do `CLAUDE.md` demora a valer
para os robôs**, e ninguém descobre até um portão reprovar. É a irmã de cima da
`armadilhas/148` (o custo de LER do espelho): lá o agente lê arquivo velho por
iniciativa própria; aqui ele **recebe ordens velhas** antes de ler coisa
alguma. E é a mesma família da `armadilhas/227` — instrução revogada que
continua ensinando —, com o agravante de que a fonte da instrução é o canal de
maior obediência que existe numa sessão.

**Solução (desde 30/08/2026, TAR-045): o aviso de abertura passou a MEDIR.**
`ci/muralha_pasta_compartilhada.py --aviso` já rodava em todo `SessionStart` e
já falava quando a sessão nascia no principal. Agora ele mede, **sem rede**, com
o que o git tem em cache:

```
git rev-list --count HEAD..origin/main        # a distância
git diff --name-only origin/main -- CLAUDE.md # o atraso alcançou as ORDENS?
```

e diz uma de três coisas — nunca uma quarta:

| medição | o que o aviso faz |
|---|---|
| 0 commits atrás | **cala** sobre a idade |
| N > 0, `CLAUDE.md` divergindo | fala o número **e** que as ordens podem estar REVOGADAS, com `git show origin/main:CLAUDE.md` |
| N > 0, `CLAUDE.md` idêntico | fala o número e diz que as **ordens valem** — o que está velho é o código lido dali |
| não conseguiu medir | fala **dizendo que não mediu** (INV-CI01) e nunca inventa número |

**As duas coisas que o conserto NÃO faz, de propósito:**

1. **Não atualiza o espelho.** A pasta é compartilhada e pode ter trabalho não
   commitado de outra sessão (`armadilhas/135`) — atualizar é decisão de quem
   está na frente do computador. O aviso é a cura; o `git pull` não é dele.
2. **Não mede em worktree.** Um worktree de ramo vivo fica atrás de
   `origin/main` o tempo todo: isso é o normal, não um defeito. Medir lá seria
   alarme falso, e o `CLAUDE.md` do worktree nasceu de `origin/main` de
   qualquer forma.

**A armadilha DENTRO da solução, e ela é o centro da tarefa.** Este aviso roda
em **toda** sessão. Guarda que grita à toa é guarda que se aprende a ignorar
(`armadilhas/174`; o sino da TAR-038 adoeceu exatamente assim, tocando em cima
de mensagem de sucesso). Por isso o silêncio com 0 commits é **contrato
testado**, não acaso: `test_espelho_em_dia_nao_fala_do_atraso` reprova se o
aviso falar — provado por mutação (`if idade.commits == 0` virou `== -1` ⇒ o
aviso passou a anunciar `IDADE DO ESPELHO: 0 commits atrás` e o teste ficou
vermelho). E pelo mesmo motivo o aviso é **preciso em vez de probabilístico**:
sem comparar o `CLAUDE.md`, todo atraso viraria "suas ordens podem estar
revogadas", inclusive os atrasos que não encostaram nas ordens — meia dúzia
desses e ninguém lê mais o parágrafo.

**O par que faz esta entrada difícil de acertar:** o silêncio e a fala têm de
ser testados **juntos**. Um teste só do lado "fala" aceita um aviso que grita
sempre; um teste só do lado "cala" aceita um aviso que nunca fala. E o terceiro
lado — "não mediu" — é o que impede o conserto de virar falso-verde: sem ele, o
caminho do erro cairia no **mesmo** silêncio do espelho em dia, e "não medi"
viraria "está em dia" (INV-CI01, RETROSPECTIVA-FASE-D §1).

**Sem sinal de sino, e é de propósito:** o sino reage a saída de comando, e
esta cura é **proativa** — ela fala no `SessionStart`, antes de qualquer
comando. Declarar `IDADE DO ESPELHO` como assinatura só faria o sino tocar em
cima de um aviso que já disse tudo, que é a doença da `armadilhas/229`.

**Guarda:** `ci/tests/test_muralha_pasta_compartilhada.py` — sete testes que
montam espelhos à mão e sem rede (`origin/main` escrito com `git update-ref`,
commits da frente deixados para trás com `reset --hard`): em dia cala · atrás
fala com o número certo · ordens divergentes dizem "revogada" e o comando de
conferência · atraso que não tocou as ordens **não** grita revogado · git mudo
diz `NÃO MEDIDA` e cita a INV-CI01 · o aviso nunca manda `git pull` · worktree
não é medido.

**Origem:** TAR-045, 30/08/2026 — aberta na sessão principal depois de o
`CLAUDE.md` de 358 commits atrás mandar um robô do lote escolher número de
armadilha à mão, contra a regra que a `armadilhas/227` tinha acabado de curar
no código. O conserto chegou à `main` e não chegou a quem recebe as ordens.
