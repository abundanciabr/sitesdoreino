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
python ci/fila.py bloquear TAR-007 --quem "..." --motivo "..." --espera <mantenedor|fila>
python ci/fila.py cancelar TAR-007 --quem "..." --motivo "..."   # não vai mais ser feita
python ci/fila.py concluir TAR-007 --quem "..." --evidencia "https://github.com/.../pull/NNN"
python ci/fila.py criar --titulo "..." --toca <celulas> --move <cartao|manutencao> --evidencia-exigida "..." --despacho "..."
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

**O comprovante nasce na bancada, nunca no espelho** (desde 30/08/2026,
TAR-018). O balcão escreve o evento na pasta em que foi chamado — e a ordem de
partida antiga (pegar a tarefa *antes* de criar o worktree) fazia esse arquivo
nascer no CLONE PRINCIPAL, onde ninguém commita. O PR viajava sem ele, a tarefa
chegava à `main` com `concluida` e sem `reivindicada`, e nada acusava: com o
arquivo fora, `validar` respondia `✅ Fila válida`, exit 0 (`armadilhas/192`).

A cura tem duas peças, com autoridade deliberadamente diferente:

- **`criar`, `pegar`, `bloquear`, `cancelar` e `concluir` RECUSAM no clone
  principal** (exit 1) e a
  recusa ensina a ordem certa: worktree primeiro, balcão de dentro dele. Não é
  portão de CI — nenhum PR reprova por isto; é um comando interativo se
  recusando a produzir lixo, e o conserto custa um `git worktree add`. Aviso em
  sombra aqui não curaria nada: o arquivo já teria nascido, e o robô nem
  consegue apagá-lo (medido em 30/08/2026 — o classificador de permissão
  recusou a limpeza). `listar`, `validar` e `soltar` **continuam livres** no
  espelho: devolver à fila uma tarefa presa é gesto de emergência, e emergência
  não pode depender de ter worktree.
- **`validar` DIZ EM VOZ ALTA, em SOMBRA**, todo arquivo de `eventos/` que o
  Git não conhece — nomeando cada um, com o conserto (`mv` para a bancada, no
  espelho; `git add` na bancada) — e **não muda o veredito**. Aqui é onde mora
  o portão de CI, e é aqui que vale a lei do Sistema Imunológico: regra nova
  nasce em sombra, dizendo o que teria feito. Quando não consegue medir (git
  mudo), ela **diz que não mediu** — "não medi" se declara, não se esconde.

## Os estados que o quadro calcula

- **na fila** — existe, ninguém pegou, dependências satisfeitas.
- **bloqueada** — evento `bloqueada` (com motivo e `espera`), OU `depende_de`
  aberta (calculado — ninguém escreve isso, e o `espera` sai `fila`).
- **reivindicada** — evento `reivindicada` sem devolução posterior, OU reserva
  viva no servidor.
- **em execução** — há PR ABERTO citando `TAR-NNN` no título ou no ramo
  (só na vista `--ao-vivo`).
- **concluída / cancelada** — evento terminal. Depois do fim, silêncio:
  evento após o fim reprova na muralha.

## Quem destrava uma parada: o campo `espera` (desde 06/09/2026)

"Bloqueada" sempre significou duas coisas incompatíveis no mesmo balde, e quem
pagava a conta era o painel do dono. Medido em 06/09/2026, quando ele perguntou
como se atualizava a lista de `/admin/caixa/robos/`: **27 tarefas paradas, todas
no mesmo bloco âmbar de urgência, e seis delas esperavam uma decisão dele.** Para
achar essas seis era preciso abrir e ler os 27 cartões, um por um.

Metade da resposta já era calculada e se perdia no caminho: `calcular_estados`
distingue o bloqueio por DEPENDÊNCIA ABERTA (13 das 27 naquele dia, e ninguém
precisa fazer nada) do bloqueio por EVENTO ESCRITO. O que não existia era a
segunda metade: dentro dos escritos, quem destrava.

```bash
python ci/fila.py bloquear TAR-007 --quem "..." --motivo "..." --espera mantenedor
python ci/fila.py bloquear TAR-007 --quem "..." --motivo "..." --espera fila
```

| No evento | Quer dizer | Onde aparece |
|---|---|---|
| `espera: mantenedor` | autorização, decisão ou prova que só o dono pode dar | bloco "Esperando uma decisão sua", aberto, no topo |
| `espera: fila` | um robô resolve quando a vez dela chegar | bloco "Esperando outra tarefa terminar", fechado |
| dependência aberta | calculado, ninguém escreve | vira `fila` sozinho |

**`--espera` é obrigatório**, pela mesma lição que o `--move` já deu aqui: campo
que nasce opcional no balcão nasce vazio. Quem bloqueia sabe, naquele instante,
se um robô destrava aquilo sozinho — ninguém depois vai saber melhor, e ninguém
depois volta para preencher.

**Ler isso do texto do `motivo` foi considerado e recusado.** Seria adivinhar por
palavra ("espera mandato", "só o mantenedor pode") uma resposta que quem bloqueou
tinha na mão — e `robos.py` já proibia o palpite com todas as letras, porque ele
nasceria como segunda definição de "o que espera por você". Quem sabe, declara.

**`validar` cobra em todo bloqueio VIVO**, e a régua é o estado de hoje, não uma
data de corte no código: os 22 eventos `bloqueada` de tarefas que já seguiram
adiante são história encerrada, e cobrar deles exigiria reescrever evento — que
esta fila não faz. Na tela, uma parada com `espera` que ela não reconhece cai no
bloco do mantenedor: falha para o lado de MOSTRAR, porque cartão a mais custa uma
leitura e cartão que some custa uma tarefa esquecida.

## Cancelar também é um verbo (desde 06/09/2026)

`cancelada` era terminal desde que a fila nasceu, `validar` já exigia `detalhe`
nele, e o painel já tinha o grupo "Não vão mais ser feitas" — sem nenhuma porta
para chegar lá. Quem precisasse cancelar escrevia o JSON à mão, que é a porta de
entrada da `armadilhas/192`. Estado sem verbo não é estado: é um lugar que
ninguém alcança.

Medido no mesmo dia: oito tarefas (TAR-057 a TAR-065) moravam em `bloqueada` com
o motivo dizendo "TRANCADA ... substituta já criada". Nunca mais seriam feitas, e
por falta deste verbo ocupavam o bloco de urgência do painel do dono.

`cancelar` não pede `--espera`, e é isso que importa: cancelada não espera
ninguém. Ele avisa, antes de escrever, quem depende da tarefa e vai ficar preso
para sempre — dependência só se destrava CONCLUÍDA, e foi assim que a TAR-060
caiu junto com a TAR-057 em 31/08/2026.

## A tarefa que CRIA o que declara: o campo `cria` (desde 30/08/2026)

Um guarda da muralha exige que todo `toca` aponte para pasta que existe, e ele
tem razão em dois casos: vocabulário errado, e pasta renomeada sem avisar a
fila. Existe um terceiro, legítimo, que ele não sabia distinguir: **a tarefa de
GÊNESE, que é justamente quem cria a pasta.**

Medido em 30/08/2026, na hora de enfileirar a gênese da célula da gamificação:
a tarefa reprovou a muralha por declarar `toca: [gamificacao]`, a célula que ela
mesma inaugura. Sem uma saída, **nenhuma célula nova poderia nascer pela fila**.

A saída é escrita, nunca implícita:

```
python ci/fila.py criar --titulo "..." --toca gamificacao --cria gamificacao ...
```

`cria` usa o MESMO vocabulário do `toca`, e se lê "eu mexo nesta célula, e sou
eu quem a inaugura". Exigir a declaração é o que impede a porta de absolver os
dois primeiros casos: `toca` com erro de digitação continua reprovando, porque
ninguém escreveu no arquivo da tarefa que ia criar aquilo.

A dispensa vale só na janela entre a tarefa nascer e a célula existir. Depois
disso a pasta está lá, e a conferência do diff nem precisa dela: o PR da gênese
declara a célula em `celulas.yml`, então o `toca` e o diff se encontram
sozinhos. Quem lê o campo: `ci/conferencia_do_toca.py::areas_criadas`, uma
definição só.

## O que a tarefa veio MOVER: o campo `move` (desde 04/09/2026)

O quinto documento do Scale OS faz uma pergunta que esta fila não sabia
responder: **que resultado estratégico esta tarefa move?** O `toca` diz em que
pasta se mexe, e isso nunca foi a mesma coisa. Sem a resposta, atividade se
confunde com progresso: em 04/09/2026, das 123 tarefas da fila, dava para dizer
que 46 tocavam só a fábrica e 77 tocavam o negócio, e nada além disso, porque
pasta não é propósito.

`--move` é **obrigatório** ao criar, e tem três estados que são diferentes de
propósito:

| No arquivo | Quer dizer |
|---|---|
| campo ausente | **ninguém declarou.** É o estado das 123 tarefas anteriores a esta data, e não quer dizer "não move nada" |
| `["manutencao"]` | declarado: **mantém a fábrica de pé** e não move número nenhum. Sozinho, nunca misturado |
| `["compras-no-mes", ...]` | move estes cartões de `painel/cartoes/` |

```bash
python ci/fila.py criar --titulo "..." --toca admin --move compras-no-mes ...
python ci/fila.py criar --titulo "..." --toca ci --move manutencao ...
```

**O nome do cartão é conferido contra `painel/cartoes/`, e nome errado
reprova** (no balcão, ANTES de gastar número do almoxarife; e na muralha, para
quem escreveu o JSON à mão). Sem essa conferência o campo seria texto livre, e
texto livre vira erro de digitação silencioso: foi a lição que o `toca` já deu
nesta casa. Quando a pasta dos cartões não existe no checkout, a validação
também reprova, em vez de deixar passar: sem a lista, o nome não é conferível,
e ausência de evidência não é evidência de acerto (INV-CI01).

Por que ele nasceu obrigatório: campo que nasce opcional no balcão nasce vazio,
e a garantia escrita em prosa apodrece. Quem não tem número para declarar
escreve `manutencao`, que é uma resposta honesta, não uma fuga.

Onde isto foi decidido: degrau 19 de `docs/decisoes/PLANO-PAINEL-DE-GESTAO.md`,
derivado de `docs/consultorias/painel-de-gestao/CONFRONTO-growth-execution-engine.md`
§4.1. O caminho de volta (de um número para as tarefas que o movem) é a segunda
metade do degrau.

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
- A recusa no espelho e o aviso em sombra sobre comprovante fora do Git:
  `ci/fila.py` (`_parar_se_for_o_espelho` e `dizer_os_comprovantes_soltos`),
  que reusam a leitura de espelho-vs-bancada de
  `ci/muralha_pasta_compartilhada.py` — uma definição só. Guardas em
  `ci/tests/test_fila.py`, encenados com repositório descartável real
  (principal + worktree ligado).
- A trava de reivindicação: o servidor do GitHub, via `ci/reservar.py`
  (refs atômicas com `--force-with-lease` e nonce — ver o cabeçalho de lá).
- Testes-guarda: `ci/tests/test_fila.py` (inclui a corrida: segunda sessão
  recusada) e `ci/tests/test_reservar.py`.
- A conferência do `toca`: `ci/conferencia_do_toca.py`, disparada por
  `.github/workflows/conferencia-do-toca.yml` em todo PR que cita `TAR-NNN`.
  Em SOMBRA — ela comenta, não reprova. Guarda:
  `ci/tests/test_conferencia_do_toca.py`.
