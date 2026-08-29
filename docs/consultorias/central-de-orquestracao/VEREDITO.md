# VEREDITO — Central de Orquestração de Trabalho

**Fechado em 29/08/2026**, com três pareceres externos (GPT, Opus e Gemini,
nesta pasta) e uma verificação que decidiu mais que os três juntos: **conferir o
que o projeto construiu ENTRE a pergunta e a resposta.** A rodada foi aberta em
28/08 de manhã; entre a abertura e este veredito, o projeto ganhou o almoxarife,
a pista de pouso, a espera-que-fala e o escritor único — e os três consultores
escreveram sem saber de nenhuma dessas peças.

---

## A decisão, em uma frase

**A fila de trabalho nasce como pasta de arquivos no repositório (`fila/`), no
mesmo molde do livro de ocorrências; a trava contra dois robôs na mesma tarefa
é o almoxarife que JÁ existe (`ci/reservar.py`); e a aba "Os robôs" do
`/admin/caixa/` é toda calculada dessa fonte — nenhum banco novo, nenhum
servidor novo, nenhuma lista digitada à mão.**

---

## Em que os três concordam — e que vira lei da fila

Convergência de três analistas independentes vale mais que a preferência de
qualquer um deles. Os cinco pontos:

1. **Estado calculado, nunca campo editado.** GPT: "a coluna em que um card
   aparece é sempre calculada a partir da última ocorrência, nunca um campo
   status sobrescrito". Opus: máquina de estados com transições válidas, onde
   "DONE pode ser calculado, não declarado arbitrariamente". Gemini: o
   check-out atômico muda o estado, não a boa vontade do robô. É a mesma lei
   que o livro já impõe (`painel/LEIA-ME.md`): acontecimento se acrescenta;
   estado se calcula.

2. **A trava de reivindicação é atômica e tem prazo de validade.** GPT propôs
   conflito de Git em arquivo de nome fixo + ocorrência de expiração; Gemini
   propôs bloqueio otimista com `timeout_segundos`; Opus propôs lease com
   heartbeat. Os três desenharam, com vocabulários diferentes, a mesma peça —
   e ela **já foi construída** (ver "O que mudou entre a pergunta e a
   resposta", abaixo).

3. **A tarefa declara o que toca e do que depende.** O campo `toca` do GPT, o
   `conflict_scopes` do Opus, as `dependencias` do Gemini: sem isso não existe
   resposta para "pode rodar em paralelo?". Entra no molde da tarefa desde o
   primeiro dia — mesmo que o cálculo de "onda ótima" fique para depois.

4. **Exceção é resultado esperado, não falha do robô.** GPT nomeou o risco
   exato: sob pressão para "concluir", o robô prefere forçar um resolvido a
   abrir exceção — e a coluna fica vazia "não porque nada trava, mas porque
   nada é declarado". O despacho de cada tarefa dirá, com todas as letras, que
   parar e reportar é o comportamento certo quando travar.

5. **Cada tarefa carrega o prompt pronto.** Os três chamaram de nomes
   diferentes (protocolo embutido, Execution Pack, Prompt Gerado); a essência
   é a mesma: o despacho se copia da tarefa, não se redige de memória a cada
   vez.

---

## O que mudou entre a pergunta e a resposta

Os pareceres partem da premissa "nenhuma trava existe". Ela era verdadeira em
28/08 de manhã e **deixou de ser no mesmo dia**:

- **O almoxarife** (`ci/reservar.py`, Onda 2 do
  `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`): reserva atômica
  arbitrada pelo servidor do GitHub — quem chega primeiro cria a referência,
  quem chega segundo recebe recusa DO SERVIDOR, na hora; a reserva expira
  sozinha em 3 horas se a sessão morrer. É o lease do Opus e o bloqueio
  otimista do Gemini, sem servidor próprio — e sem a fraqueza fatal do desenho
  do GPT (abaixo).
- **A pista de pouso** (`mergear.py --pousar`): a fila de integração serial
  que o Opus desenhou como "Integration Queue" já existe e já opera.
- **A espera-que-fala + a telemetria**: toda espera tem voz e teto
  (RITOS §2 peça 6), e o diário de esperas nasceu em 29/08 — é uma das fontes
  da aba.
- **O escritor único** (Onda 3): fonte multiescritor em arquivo-por-fato,
  materialização gerada por um escritor só, prova por fora. É o molde que a
  fila copia.

---

## Onde cada consultor errou — e o veredito de cada proposta

### GPT — a trava por conflito de Git: SUPERADA

O truque (arquivo de reivindicação com nome fixo por tarefa; dois robôs criam
o mesmo caminho, o Git recusa o segundo) é engenhoso e o parecer é honesto
sobre a fraqueza fatal: *"se a reivindicação precisar da aprovação de PR antes
de valer, a trava para de ser em tempo real — vira tão rápida quanto sua fila
de revisão"*. É exatamente o caso deste projeto: a `main` só aceita PR com
checks verdes. O almoxarife não tem essa fraqueza — a recusa vem do servidor
no instante do pedido, sem esperar merge nenhum. **Fica do GPT:** o ciclo de
vida como cadeia de ocorrências, a conferência do `toca` declarado contra o
diff real do PR (mesmo princípio do `--conferir`), e o aviso sobre a coluna de
exceção vazia por medo.

### Gemini — o despachante-servidor: NÃO CABE NOS CANAIS DA CASA

O desenho ("os robôs mandam um pedido ativo para o painel; o painel tranca a
porta no milissegundo da entrega") pressupõe um serviço vivo que arbitra. Este
projeto não tem — e não deve ter — um servidor de tarefas: os robôs falam com
o mundo por git/gh e pipeline (Lei 5: nem SSH têm), e um serviço 24/7 novo
seria custo, superfície de ataque num repositório público, e uma segunda casa
para fatos — o que a lei anti-duplicação proíbe. O que a transação dele compra
(atomicidade), as referências do GitHub já dão de graça. **Fica do Gemini:** a
separação instrução × dados no despacho (evita injeção acidental de prompt), a
taxonomia dos dois tipos de exceção (erro técnico × validação humana), e o
desenho visual — borda colorida significa AÇÃO EXIGIDA, nunca prioridade
(`desenho-kanban-cores-Gemini.html`).

### Opus — o control-plane com Postgres: A DIREÇÃO CERTA, A FUNDAÇÃO ERRADA

O parecer mais profundo dos três — e o mais caro. A célula `orquestrador` com
banco próprio, APIs de `claim/heartbeat/submit`, WebSocket para o cartão se
mover sozinho: tudo isso pressupõe robôs que chamam APIs de um backend
próprio. Os robôs desta casa não chamam — eles leem e escrevem arquivos,
criam referências e abrem PRs. Construir o backend seria reconstruir, do lado
de fora dos canais existentes, o que o molde do livro + almoxarife + GitHub já
garantem por dentro. **Fica do Opus, e é muito:** a separação
tarefa × execução × quem executa ("uma tarefa não falhou; uma execução dela
falhou"), a máquina de estados com transições proibidas (`RUNNING → DONE`
nunca), evidência estruturada para fechar, a exceção que chega como DECISÃO
com opções e recomendação (não como problema cru), e o princípio "o robô não
edita a própria tarefa para facilitar o trabalho" — na fila, o arquivo da
tarefa nunca se edita; tudo é evento novo.

---

## O desenho decidido (o que as fases 2 e 3 do plano executam)

**A fonte — `fila/` na raiz, no molde do livro:**

- `fila/LEIA-ME.md` — o contrato.
- `fila/tarefas/` — **um arquivo por tarefa**, nunca editado depois de criado.
  Campos: id (alocado pelo almoxarife, nunca adivinhado), título para leigo,
  `toca` (o que mexe), `depende_de`, evidência exigida para fechar, o despacho
  pronto para colar, origem, `criada_em`.
- `fila/eventos/` — **um arquivo por acontecimento** (reivindicada, devolvida,
  bloqueada, concluída-com-evidência). Corrigir é acrescentar, nunca editar.
- **Estados sempre calculados:** na fila → reivindicada (reserva ativa no
  almoxarife OU evento) → em execução (PR aberto no ramo da tarefa) →
  concluída (evento com evidência conferida); bloqueada enquanto `depende_de`
  estiver aberta.
- `ci/fila.py` — o balcão: `criar`, `listar`, `pegar` (via almoxarife),
  `soltar`, `concluir` (fail-closed: sem evidência, recusa), `validar` (na
  muralha). Teste de corrida obrigatório: duas sessões pegam a mesma tarefa,
  uma TEM de ser recusada — a trava só é declarada pronta com essa prova.

**A aba — "Os robôs" em `/admin/caixa/`, toda calculada, três blocos:**

1. **A fila** — o quadro, da materialização de `fila/` embutida no build do
   admin (escritor único, como o `painel.html`).
2. **Quem está com o quê agora** — ao vivo, do navegador: PRs abertos e
   reservas do almoxarife, lidos da API pública do GitHub (o repositório é
   público de propósito) — zero backend novo.
3. **As esperas** — a régua viva (`ci/tempos_esperados.json`) + um resumo
   curado dos estouros, exportado do diário local com a mesma redação de
   segredos da telemetria. O diário cru continua dentro do `.git`, fora do
   GitHub, por desenho.

---

## O que fica registrado como evolução — sem construir agora e sem prometer

| Ideia | De quem | Por que ainda não |
|---|---|---|
| Waves (cálculo da combinação ótima de tarefas paralelas) | Opus | Exige histórico do campo `toca` funcionando na prática; a fila nasce com o vocabulário que permite calcular isso depois. |
| Scheduler / "melhor próxima tarefa" / caminho crítico | Opus | Mesma dependência; hoje quem despacha é o mantenedor com a maestro. |
| Heartbeat de progresso | Opus | O prazo de validade do almoxarife já cobre o caso "sessão morreu"; batimento fino é refinamento. |
| Compilador de prompts (despacho recompilado do estado real) | Opus | O despacho pronto no arquivo da tarefa resolve o hoje; recompilação automática é o passo 2. |
| Conferência automática do `toca` declarado × diff real do PR | GPT | Boa e barata — candidata natural à primeira evolução da fila. |
| Colina (posição dentro do "em execução") | GPT | Complemento visual; depende da fila existir. |
| Segunda opinião automática em exceção | Opus | O rito manual (banca) já existe; automatizar é depois. |

Nada de pagamento/checkout em nenhuma dessas — a diretiva de 22/08 continua.

---

## Rastreabilidade — de onde veio cada peça do desenho

| Peça da fila/aba | Origem |
|---|---|
| Estado calculado de cadeia de eventos | GPT + lei do livro |
| Trava atômica com prazo | os três → já construída (almoxarife) |
| `toca` / `depende_de` no molde | GPT (`toca`) + Opus (`conflict_scopes`, `depends_on`) |
| Evidência obrigatória para fechar | Opus + lei do verde do livro |
| Despacho pronto por tarefa | os três |
| Exceção como decisão traduzida, não problema cru | Opus + GPT |
| Borda colorida = ação exigida | Gemini |
| Tarefa × execução separadas | Opus |
| Materialização com escritor único | Onda 3 (casa) — nenhum consultor conhecia |
