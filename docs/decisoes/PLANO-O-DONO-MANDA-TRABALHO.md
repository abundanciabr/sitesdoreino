# PLANO | o dono manda trabalho, e destrava, pela própria tela

publico-para-ia: true

**Escrito em 03/09/2026**, a partir de duas escolhas do mantenedor em pergunta
estruturada, no mesmo dia, logo depois de a aba `/admin/caixa/robos/` deixar de
ser ilegível (PR #932). A pergunta foi *"o que você quer conseguir FAZER nessa
página?"*, e ele marcou **as duas** opções de ação:

- **mandar trabalho por aqui** — escrever um pedido em português e jogá-lo na
  fila dos robôs;
- **destravar as paradas por aqui** — responder uma tarefa parada e devolvê-la
  à fila.

Ele não marcou "só olhar, e assim está bom". A palavra dele na abertura da
conversa tinha sido *"não estou conseguindo **usar**"*, e as duas escolhas
explicam o que "usar" queria dizer: a página é uma vitrine, e ele quer um
volante.

Molde: `docs/decisoes/PLANO-CELULA-GAMIFICACAO.md` (a escada de degraus) e
`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` (o plano que declara o que ainda não
existe). Este documento **não é um painel**: ele não guarda estado e não se
atualiza sozinho. Quem responde "isto foi feito?" é o livro
(`painel/registros/`) e a fila (`fila/`).

---

## Parte 1 | O problema de verdade, em uma frase

**O gesto do dono acontece numa VPS, e a fila mora no Git.**

A fila de trabalho (`fila/LEIA-ME.md`) é um monte de arquivos versionados:
`tarefas/NNN-slug.json` para o que existe, `eventos/…json` para o que
aconteceu, e o estado **não mora em lugar nenhum** — é calculado dos dois. Essa
é a lei que impede a fila de virar uma lista digitada à mão, e ela não está em
discussão.

A célula `admin` roda num contêiner na VPS. Ela **não tem, e não vai ter, poder
de commitar no repositório** (Lei 5: agente não tem SSH; e um contêiner de
produção com chave de escrita no Git seria pior que o problema). Logo, o
formulário da tela não pode escrever o arquivo. Alguma ponte tem que existir, e
escolher qual é a decisão central deste plano.

Uma coisa que **não** vai acontecer: o Admin guardar as tarefas no próprio
banco e desenhar a fila a partir de lá. Isso seria uma segunda definição de "em
que pé está o trabalho", e as duas divergiriam no primeiro dia — é a lei
anti-duplicação do `CLAUDE.md`, e é o defeito que a própria fila nasceu para
curar.

---

## Parte 2 | Os dois caminhos, e por que um deles ganha

### Caminho A — a tela pede ao GitHub que rode uma esteira (RECOMENDADO)

O formulário manda o texto para a célula `admin`. Ela chama uma API do GitHub
(`workflow_dispatch`) com uma chave guardada na VPS. Do outro lado, uma esteira
roda `python ci/fila.py criar …`, abre um PR com o arquivo da tarefa e pede
pouso à pista. A pista mergeia, como faz com qualquer PR.

- **A fila continua sendo a única definição.** Nada de estado novo no banco do
  Admin: o pedido vira arquivo no repositório em menos de um minuto, e some da
  memória da VPS.
- **O retorno vem de graça.** O bloco "Agora, neste minuto" da própria página já
  lista os PRs abertos, perguntando ao GitHub do navegador dele. O PR que a
  esteira abrir aparece ali sozinho, sem uma linha de código a mais.
- **Ninguém fica no caminho crítico.** Ele aperta, e a coisa anda até o fim sem
  robô nenhum acordado. É o padrão que a `RETROSPECTIVA-FASE-D` §5 cobra.
- **Custa a ele um passo manual, uma vez:** criar uma chave no GitHub e colá-la.

### Caminho B — o Admin guarda o pedido, e um robô vem buscar

O pedido fica numa tabela do Admin. Um comando novo (`ci/fila.py recados`)
busca os pendentes quando algum robô lembrar de perguntar, e os converte em
tarefas.

- Não precisa de chave nenhuma, nem de passo manual dele.
- **Mas põe um robô no caminho crítico.** O pedido dele fica parado até alguém
  abrir uma sessão e lembrar de buscar. É exatamente o atrito que a fila e a
  pista foram construídas para tirar, e é o padrão "humano no caminho crítico"
  da `RETROSPECTIVA-FASE-D` §5, aplicado a um robô.
- E cria uma caixa de entrada que o painel do dono não enxerga, contra a lei
  anti-duplicação.

### Caminho C — uma esteira de relógio busca os pedidos na VPS

O pedido fica guardado no Admin, como no B, mas quem vem buscar é uma esteira
com `schedule` (de N em N minutos), sozinha. **A direção da confiança se
inverte:** a chave passa a morar no GitHub, e a VPS não ganha poder nenhum
novo.

Este caminho existe neste documento porque ele **conserta o defeito que fez o B
perder** — ninguém fica no caminho crítico —, e omiti-lo seria escolher o A por
uma comparação incompleta.

O que sobra contra ele:

- **A tabela do B continua existindo.** O pedido precisa de um lugar para
  esperar o relógio, e esse lugar é uma segunda caixa de entrada que o painel
  não enxerga. No A não existe espera: o pedido vira arquivo no repositório e
  some da VPS.
- **O relógio custa minutos**, e o retorno na tela deixa de ser imediato: ele
  aperta e não vê nada acontecer até a próxima batida.
- **A chave não some, ela muda de lado.** Continua sendo um passo manual dele —
  agora para a esteira poder ler o endereço protegido da VPS.

O que ele ganha é real, e é só um: **a VPS não passa a poder mandar o GitHub
rodar esteira.**

### A recomendação

**Caminho A**, por dois motivos, nesta ordem:

1. **Nada fica guardado esperando.** O pedido vira arquivo do repositório em
   menos de um minuto, e a fila continua sendo a definição única. B e C, os
   dois, precisam de uma tabela nova que o painel não vê.
2. **O retorno é imediato e sai de graça.** Ele aperta, e o PR aparece no bloco
   ao vivo da mesma página, que já pergunta ao GitHub pelos PRs abertos.

O preço é um passo manual único, e a casa já pagou esse preço uma vez pelo mesmo
motivo: a `PISTA_TOKEN`, que ele criou em 28/08/2026 para a pista poder mergear.

**Quando o C seria a escolha certa:** se o poder extra na VPS incomodar ele. A
troca é honesta — alguns minutos de espera e uma tabela a mais, em troca de a
VPS não ganhar nada. É decisão dele, não minha, e por isso os três estão
escritos aqui em vez de dois.

### O que a chave pode, e o que ela não pode

A chave é um *fine-grained token* limitado a **este repositório** e a **uma
permissão só: `actions: write`** (disparar esteira). Com ela, quem a tivesse
poderia mandar rodar as esteiras que já existem — nada além. Ela **não** lê
código privado (o repositório é público de propósito), **não** commita, **não**
mergeia, **não** toca em segredo nenhum. O pouso continua sendo da pista, com a
chave dela, que mora no GitHub e não na VPS.

Isto está escrito aqui porque é um risco real e pequeno, e risco pequeno se diz
na cara: a VPS passa a ter poder de fazer o GitHub rodar esteiras.

---

## Parte 3 | A escada

Cada degrau é um PR, e cada um deixa a casa funcionando. A ordem é escolhida
para que **o degrau 0 seja provado antes de existir tela nenhuma** — se a ponte
não funcionar, ninguém desenhou um formulário à toa.

### Degrau 0 | A esteira que recebe o pedido, apertada por mim

`.github/workflows/pedido-do-dono.yml`, com `workflow_dispatch` e três campos:
o que ele quer, onde isso mexe, e se é pedido novo ou destravamento. A esteira
roda `ci/fila.py criar` (ou `soltar`, no caso do destravamento), abre o PR e
pede pouso.

**Este degrau não termina no merge.** `armadilhas/260` é a lição desta casa
sobre botões entregues e nunca apertados: em 31/08/2026 um workflow de semear
entrou verde, com o livro prometendo *"você não precisa colar nada: eu disparo"*,
e a conferência do dia seguinte deu `total_count: 0`. A tela do mantenedor
passou a madrugada vazia. Aqui: **eu aperto o botão na mesma sessão, e o id do
run vai na evidência do registro.** Sem o id, o livro registrou uma intenção.

Toca `.github/` e `ci/`, que são caminhos CODEOWNERS: precisa de mandato dele, e
sai anunciado nominalmente no relatório.

### Degrau 1 | A chave, e o único passo manual dele

Um bloco único de colar, fail-closed, com a janela dita na primeira linha, no
formato que funcionou nos outros passos manuais desta casa. Enquanto ele não
colar, o degrau 2 já pode estar no ar: a tela nasce **fail-closed**, dizendo em
português por que o botão não está lá.

Nasce um registro de `pendencia` com `precisa_do_dono: true`, para a caixa
"Precisa de você" cobrar sozinha — ela é calculada, e não esquece. Uma frase no
meio de um relatório esquece.

### Degrau 2 | A tela de mandar trabalho

Em `/admin/caixa/robos/`, acima do quadro: **"O que você quer que os robôs
façam?"** Um campo de texto grande, em português, e um botão. Nada de campo
técnico: `evidencia_exigida` e `despacho` a esteira preenche.

O ponto delicado, e ele fica escrito na tela: **o pedido dele em português não
é um despacho técnico, e fingir que é seria mentira.** A tarefa nasce com o
texto dele palavra por palavra, mais uma instrução ao robô que a pegar: leia o
pedido do dono, traduza para um plano, e se a tradução tiver mais de um caminho,
pergunte antes de escolher. É honesto, e é como a Caixa de Sugestões já trata o
texto de um aluno.

### Degrau 3 | Destravar uma parada

Em cada cartão parado, um campo curto — *"o que eu respondo"* — e um botão. Ele
escreve, e a esteira grava o evento `devolvida` em `fila/eventos/`, com a
resposta dele no motivo. A tarefa volta para "esperando um robô pegar", e o
próximo robô lê a resposta no cartão.

Aviso medido em 03/09/2026, e que vale ser dito antes de construir: **das 11
paradas de hoje, nenhuma espera por ele.** Todas esperam outra tarefa terminar
(plano desatualizado, ou corrente de dependência). Este degrau é para o dia em
que uma parada precisar dele de verdade, e esse dia chega — mas ele não é hoje,
e por isso ele vem depois do degrau 2, que serve hoje.

### Degrau 4 | O pedido sabe em que PR virou

O bloco ao vivo já mostra o PR aberto pela esteira, mas mostra como um PR
qualquer. Aqui ele passa a dizer, com todas as letras, *"este é o seu pedido de
14h32"*. É o degrau mais barato e o mais fácil de cortar — e ele não vai ser
cortado, porque sem ele o dono aperta um botão e olha para uma lista que não o
menciona.

---

## Parte 4 | O que este plano NÃO muda

- **O estado continua calculado.** Nenhum campo `status` nasce em lugar nenhum,
  nem no banco do Admin.
- **O pouso continua sendo da pista.** A esteira do pedido pede pouso como
  qualquer agente; ela não mergeia nada.
- **O livro continua obrigatório.** Cada degrau acrescenta o próprio registro,
  embarcado no próprio PR.
- **A régua dos travessões não alcança estas telas** (`admin` é bastidor, por
  `ci/texto-publico-bastidor.txt`), mas o texto continua sendo escrito para um
  leigo: sem sigla, sem jargão, e sem prometer o que a fila não sabe.

---

## Parte 5 | O que ainda depende dele

1. **Qual ponte** — A (a tela chama o GitHub, instantâneo, a VPS ganha o poder
   de disparar esteira) ou C (uma esteira de relógio busca, a VPS não ganha
   nada, alguns minutos de espera). A recomendação é A; a Parte 2 diz por quê,
   e diz também o que o C compra em troca.
2. **O mandato** para tocar `.github/` e `ci/` (CODEOWNERS) no degrau 0. Vale
   para os dois caminhos: os dois moram numa esteira.
3. **A chave**, no degrau 1 — o único passo manual, e ele vem num bloco só. Os
   dois caminhos pedem uma; muda de que lado ela fica.

Nada mais. Os quatro degraus restantes são trabalho de robô, e a escada foi
ordenada para que ele possa dizer "pode ir" uma vez e não ser incomodado de
novo até a chave.
