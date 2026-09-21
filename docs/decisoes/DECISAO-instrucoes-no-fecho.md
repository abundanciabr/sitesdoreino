# DECISÃO: o fecho diz o que vem depois, e quem cobra é o gancho

**Data:** 20/09/2026
**Quem decidiu:** o mantenedor, na sessão, com as palavras dele
**Estado:** vigente

## O pedido

"Crie uma regra para que todo robô coloque após o VEREDITO, caso a tarefa ainda
esteja como NÃO PRONTO, uma parte de INSTRUÇÕES com as próximas ações para o
mantenedor. Quero que isso seja obrigatório, e reescreva a regra de nunca falar
com o mantenedor, que faz com que o robô não queira incomodar o mantenedor e
por isso deixa de lhe instruir a respeito da continuação, próximos passos,
desdobramentos, etapas."

E, no meio da construção, a régua do conteúdo:

"Todas as vezes que o Veredito for NÃO PRONTO é necessário informar com clareza
para o mantenedor LEIGO o que ele precisa fazer, ou o que está acontecendo
porque ainda está NÃO PRONTO, mesmo que NÃO dependa dele, mesmo que algo esteja
sendo esperado. Ele precisa entender o que está acontecendo para saber o que
houve com a tarefa que pediu. Isso é básico. É prestar contas."

Ele acrescentou que, sem isso, cancelaria o projeto pela terceira vez, porque
não estava conseguindo avançar com o trabalho das IAs.

## Por que já tinha sido pedido e nunca funcionou

Não foi falta de redação. A mesma ideia já tinha virado texto três vezes, e as
três estavam abertas e apodrecendo quando esta sessão começou:

| PR | Título | Aberto em | Estado em 20/09 |
|---|---|---|---|
| #1502 | ci: explicitar ação humana nas pausas | 09/09/2026 | conflitado |
| #1504 | ci: exigir ação em veredito de falha externa | 09/09/2026 | 3 checks vermelhos |
| #1713 | ci: fecho sem promessa pendente | 18/09/2026 | conflitado |

E havia um PR empurrando na direção contrária, o #1655 ("lei: IA age, não manda
o mantenedor agir"), que é provavelmente uma das fontes do reflexo de calar.

A lição, e é ela que governa esta decisão: **regra que só existe em texto não é
regra, é intenção.** Por isso o centro desta mudança não é a prosa da lei, é o
portão do `Stop`.

## O que foi decidido

### 1. O relatório tem cinco blocos, não quatro

`**O que mudou**`, `**O que foi verificado**`, `**Pendências**`, `**Veredito**`
e `**Instruções**`. O quinto fecha toda prestação de contas.

### 2. A régua do quinto bloco

- **Em PRONTO:** presença e substância. "Nada a fazer, a tarefa acabou" é
  resposta completa. Exigir uma lista aqui ensinaria o robô a inventar trabalho
  para satisfazer o portão, que é a outra forma de mentir.
- **Em NÃO PRONTO:** pelo menos uma ação em lista e um piso de 50 caracteres.
  A lista responde o que houve, de quem é a bola, o que destrava e o prazo. Vale
  igual quando nada depende dele: nesse caso diz o que está sendo esperado e
  quanto leva.

O piso derruba o não-resposta de uma palavra ("- aguardando", 10 caracteres) e
nada além disso: nenhum portão julga clareza. O número foi medido contra
respostas curtas e completas, que ficam entre 54 e 63; nasceu em 120 e foi
baixado na revisão, porque em 120 ele reprovaria "Nada depende de você: o
GitHub testa o PR e leva uns 8 minutos; eu confirmo aqui" e ensinaria a encher
linguiça, que é a outra forma de mentir.

A caixinha do checklist (`- [ ]`) não conta como ação: ela diz o que falta na
tarefa, não o que acontece agora. Se contasse, todo NÃO PRONTO passaria pelo
portão sem uma instrução sequer.

### 3. Também em PRONTO, que ele não pediu

O print que ele mandou junto com o pedido é um **PRONTO**, e mesmo assim ele
teve de digitar sozinho qual era o próximo passo. Exigir o bloco só no NÃO
PRONTO reproduziria exatamente a tela que ele fotografou. O custo é uma linha
"nada a fazer" quando a tarefa acabou de verdade.

### 4. "Nunca pergunte" continua; "nunca informe" nunca existiu

A proibição de sub-agente perguntar ao mantenedor está certa e fica: ele não
tem canal, e transferir decisão sem poder decidir é pior que bloquear. O que
estava errado era a leitura larga dela, que virou "não incomode" e por isso
"não explique".

A lei passa a dizer, em `CLAUDE.md`, `AGENTS.md`, `docs/guia-mantenedor.md` e
nas fichas: **poupar pergunta nunca foi poupar informação.** Não perguntar é
não transferir decisão; nunca dispensa instruir. Toda proibição de perguntar,
inclusive a do sub-agente, obriga a dizer no fecho o que vem depois. O bloqueio
que o sub-agente devolve à maestro é a matéria-prima do bloco `Instruções`.

## O que foi rejeitado, e por quê

**O formato de menu do GPT** ("Próximas opções", 2 a 4 opções numeradas com
subtópicos, ao fim de toda resposta). É o cardápio que a regra 4 proíbe: pede
que ele escolha em vez de o robô decidir, e em turno trivial vira ruído que se
aprende a pular. O bloco único entrega a informação sem devolver a decisão.

**Deixar a regra só no texto.** Foi o que falhou três vezes.

## O teto do CLAUDE.md subiu de 12 500 para 13 500 bytes

O arquivo estava a 11 bytes do teto. A alternativa a subir era apagar lei que
ninguém mandou apagar, e a costura 1 do Padrão proíbe subtração do pedido. O
teto continua existindo e continua protegendo o contexto de toda sessão; o que
ele não pode virar é uma catraca que só aceita obrigação nova em troca de outra
saindo em silêncio.

No mesmo passo, a medição do teto passou a normalizar CRLF. Com
`core.autocrlf=true` o Windows guarda CRLF e o Git guarda LF: o portão
reprovava em toda máquina do mantenedor e passava na CI pelos mesmos bytes
(~242 no `CLAUDE.md`). Portão que mente localmente é portão que se aprende a
ignorar.

## Quem faz valer

`ci/prestacao_de_contas.py` no `Stop` do Claude Code e do Codex, com os testes
de `ci/tests/test_prestacao_de_contas.py`; `ci/padrao_de_trabalho.py` guarda a
frase na lei para que ela não seja apagada em silêncio.
