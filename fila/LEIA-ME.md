# fila/ — a fila de trabalho dos robôs

> Nascida em 29/08/2026, fase 2 do plano aprovado pelo mantenedor (veredito da
> consultoria em `docs/consultorias/central-de-orquestracao/VEREDITO.md`).
> A lei é a mesma do livro (`painel/LEIA-ME.md`): **acontecimento se
> acrescenta; estado se calcula; fato nenhum mora em dois lugares.**

## O que isto é

A resposta à pergunta que nenhuma superfície do projeto respondia: *"a tarefa
X existe? quem pegou? em que pé está?"*. Sem esta fonte, qualquer quadro de
tarefas seria lista digitada à mão — proibida pela lei anti-duplicação.

| O que | Onde | Regra |
|---|---|---|
| Uma tarefa | `tarefas/NNN-slug.json` | Um arquivo por tarefa. **Nunca se edita depois de criado** — número vem do almoxarife (`python ci/reservar.py numero tarefa`), id é `TAR-NNN`. |
| Um acontecimento | `eventos/AAAAMMDD-HHMMSS-TAR-NNN-<evento>.json` | Um arquivo por evento: `reivindicada` · `devolvida` · `bloqueada` · `concluida` · `cancelada`. Corrigir é acrescentar, nunca editar. |
| O estado | **em lugar nenhum** | Calculado, sempre: pela cadeia de eventos + reservas do almoxarife + PRs abertos. Não existe campo `status`. |

## O balcão — como um robô usa (`ci/fila.py`)

```
python ci/fila.py listar --ao-vivo     # o quadro: estados calculados + reservas + PRs
python ci/fila.py pegar TAR-007 --quem "sessao-<area>-<data>"
python ci/fila.py soltar TAR-007 --quem "..." --motivo "..."
python ci/fila.py concluir TAR-007 --quem "..." --evidencia "https://github.com/.../pull/NNN"
python ci/fila.py criar --titulo "..." --toca <celulas> --evidencia-exigida "..." --despacho "..."
python ci/fila.py validar              # o que a muralha roda em todo PR
```

**`pegar` é a trava.** Ele chama o almoxarife (`ci/reservar.py`), que cria uma
referência atômica no servidor do GitHub — quem chega segundo recebe recusa DO
SERVIDOR, na hora, e a reserva expira sozinha em 3 horas se a sessão morrer.
O evento gravado em `eventos/` é o registro durável; a referência é a trava em
tempo real. Os dois viajam por caminhos diferentes de propósito: a referência
vale AGORA, o evento vale para sempre (entra no PR do trabalho).

**`concluir` exige evidência.** Sem prova (URL de PR, saída crua de teste), o
balcão recusa — a mesma lei do verde do livro. `validar` reprova evento
`concluida` sem `evidencia` + `verificado_em`.

## Os estados que o quadro calcula

- **na fila** — existe, ninguém pegou, dependências satisfeitas.
- **bloqueada** — evento `bloqueada` (com motivo), OU `depende_de` aberta
  (calculado — ninguém escreve isso).
- **reivindicada** — evento `reivindicada` sem devolução posterior, OU reserva
  viva no servidor.
- **em execução** — há PR ABERTO citando `TAR-NNN` no título ou no ramo
  (só na vista `--ao-vivo`).
- **concluída / cancelada** — evento terminal. Depois do fim, silêncio:
  evento após o fim reprova na muralha.

## O `toca` é conferido contra o diff — em SOMBRA (desde 30/08/2026, TAR-015)

O campo `toca` é o único que autoriza duas tarefas a rodarem em paralelo, e até
aqui ninguém o comparava com a realidade: **declaração otimista libera um
paralelo que colide de verdade**, e a colisão só aparece depois, como conflito
de merge ou suíte alheia quebrada.

Agora, em todo PR que cita `TAR-NNN` no título ou no ramo,
`ci/conferencia_do_toca.py` compara o `toca` declarado com os caminhos que o
diff realmente alterou (as áreas saem de `celulas.yml`, a mesma fonte que
decide a matriz do deploy — nunca de uma lista nova). Divergiu, ele **comenta
no PR** dizendo onde.

**Ela avisa e não reprova**, e isso é desenho: regra nova nasce em sombra (a
lei da autoridade proporcional à certeza, no cabeçalho de
`ci/muralha_das_armadilhas.py`), porque um PR pode legitimamente crescer para
além de um `toca` escrito antes de alguém abrir o código. O comentário diz, com
todas as letras, o que a regra teria feito.

E o conserto **nunca** é editar a tarefa — o arquivo de `tarefas/` não muda
depois de criado. Ou o PR encolhe, ou o desvio é contado no `--detalhe` do
evento de conclusão, para a próxima declaração nascer melhor. Três lojas
append-only ficam de fora da conta por não poderem gerar colisão:
`painel/registros/`, `fila/eventos/` e `armadilhas/`.

## O que NÃO mora aqui

- **O que já aconteceu no projeto** — isso é do livro (`painel/registros/`).
  Concluir uma tarefa relevante continua exigindo registro no livro; o evento
  da fila fecha a TAREFA, o registro conta ao DONO.
- **Waves, scheduler, heartbeat, compilador de prompts** — registrados como
  evolução no veredito, sem promessa. A fila nasce com o vocabulário que
  permite calculá-los depois (`toca`, `depende_de`).

## Quem faz valer

- `ci/muralha-da-fila.sh` (roda em todo PR via `ci/ci.py --apenas muralhas`)
  → `python ci/fila.py validar`, fail-closed.
- A trava de reivindicação: o servidor do GitHub, via `ci/reservar.py`
  (refs atômicas com `--force-with-lease` e nonce — ver o cabeçalho de lá).
- Testes-guarda: `ci/tests/test_fila.py` (inclui a corrida: segunda sessão
  recusada) e `ci/tests/test_reservar.py`.
- A conferência do `toca`: `ci/conferencia_do_toca.py`, disparada por
  `.github/workflows/conferencia-do-toca.yml` em todo PR que cita `TAR-NNN`.
  Em SOMBRA — ela comenta, não reprova. Guarda:
  `ci/tests/test_conferencia_do_toca.py`.
