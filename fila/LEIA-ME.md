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
