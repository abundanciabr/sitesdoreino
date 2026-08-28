# Prompt para consultoria externa — ROBÔS TRABALHANDO EM PARALELO SEM COLIDIR

> **Como usar:** copie tudo o que estiver **abaixo da linha** e cole numa outra
> IA (GPT, Gemini, outro Claude, Fable...). Uma IA por conversa nova, sempre o
> texto inteiro. Salve a resposta nesta mesma pasta como `resposta-<IA>.txt`.
> Instruções completas da rodada: `LEIA-ME.md`, ao lado deste arquivo.

---

Preciso de uma segunda opinião honesta e técnica sobre **como fazer vários
agentes de IA trabalharem ao mesmo tempo, em qualquer parte de um sistema, sem
que um atrapalhe ou destrua o trabalho do outro** — hoje e daqui a um ano.

Quero que você **questione minhas premissas**, não que me elogie. Se achar que o
caminho que eu descrevo abaixo está errado, diga com todas as letras e proponha
outro. Uma crítica bem fundamentada vale mais para mim do que uma confirmação.

## Quem sou eu e como este projeto funciona

Sou o dono e **não sou programador**. Não escrevo código e não leio código. Todo
o trabalho é feito por **agentes de IA** (Claude Code) que eu despacho com
instruções escritas: eles criam ramos, escrevem o código, rodam os testes, abrem
o PR, **mergeiam sozinhos** e publicam. Eu leio painéis e respondo perguntas.

Quatro coisas tornam este caso diferente do "time de desenvolvimento assistido
por IA" que você provavelmente já viu:

1. **Não há revisor humano no caminho.** Nenhum humano lê o diff antes do merge.
   O merge é do próprio agente desde 22/08/2026, por decisão minha e
   documentada: ele espera os checks terminarem, confere e mergeia.
2. **Os agentes não se falam.** Cada sessão nasce sem saber que as outras
   existem, faz o seu trabalho e morre. Não há memória compartilhada entre elas,
   não há troca de mensagens, não há coordenador rodando continuamente. Quando
   eu disparo 5 frentes em paralelo, são 5 desconhecidos trabalhando no mesmo
   repositório.
3. **O ritmo é de dias, não de sprints.** Num único dia recente saíram 5 frentes
   em paralelo, 7 merges e 4 publicações, sem reversão. Em 48 horas o projeto
   andou cerca de 90 PRs. Não me avalie com cronograma de equipe humana.
4. **O que sobrevive de uma sessão para a outra são arquivos versionados** —
   leis, ritos, um catálogo de armadilhas com 151 entradas, um livro de
   ocorrências com 118 registros. O conhecimento é lido no início da sessão e
   **congela ali**: o que outro robô escrever nos 40 minutos seguintes, essa
   sessão nunca vai saber.

Contexto técnico para você calibrar: plataforma de cursos online, **12 serviços
isolados** (chamamos cada um de "célula"), cada célula com processo, banco de
dados e contrato de API próprios; **um repositório Git único** (monorepo) no
GitHub, privado, em **plano gratuito**; CI no GitHub Actions; deploy automático
para **uma** VPS; a máquina onde os agentes rodam é **um PC com Windows**.

## O que eu quero resolver, em uma frase

**Quero que os robôs possam trabalhar livremente em todo o sistema, ao mesmo
tempo, sem que um prejudique, apague ou atrapalhe o trabalho do outro — e quero
isso resolvido de forma definitiva, por mecanismo, não por disciplina.**

A palavra que pesa é **livremente**. Hoje eu compro a não-colisão com
**restrição**: cada robô fica trancado numa fatia pequena do sistema, e o que
não cabe na fatia vira fila. Funciona, mas o preço é alto e cresce junto com o
projeto. O que eu quero saber é se essa troca é inevitável — ou se existe um
desenho em que os robôs andam soltos e a segurança vem de outro lugar.

## Como eu compro segurança HOJE — e o preço de cada trava

Tudo isto já existe e funciona. **Não me proponha de novo o que já está aqui** —
critique, substitua ou complemente:

| Trava que existe hoje | O que ela impede | O preço em liberdade |
|---|---|---|
| **Um worktree por agente** (cada sessão trabalha numa cópia própria da pasta, criada do zero a cada tarefa) | Duas sessões pisando nos arquivos uma da outra no disco | Nenhum preço grave — é a trava mais barata que eu tenho |
| **Muralha da pasta compartilhada** (o programa recusa mecanicamente edição e comandos de git na pasta principal, que virou espelho) | A colisão que já aconteceu de verdade: uma sessão trocar o ramo debaixo dos pés da outra | Nenhum preço — mas ela é cerca, não jaula (classe 1 abaixo) |
| **1 PR = 1 célula** (o CI reprova qualquer entrega que toque mais de um serviço) | Um robô quebrar três serviços de uma vez; e o teste de um serviço "aprovar" mudança em outro que ele nunca testou | **Alto.** Nenhum robô pode consertar sozinho algo que atravessa duas células. Vira 2 PRs, 2 sessões — e a ordem entre eles passa a importar |
| **Orçamento de 15 arquivos por PR** | Entrega gigante que ninguém consegue conferir, e o "refatorar de passagem" | Médio — trabalho legítimo e grande precisa ser fatiado à mão |
| **Dono obrigatório em 10 caminhos sensíveis** (contratos, pagamentos, checkout, infraestrutura, CI, arquivos-lei) | Robô mudando as regras do jogo por conta própria | Médio — trabalho nesses caminhos só com autorização explícita minha, no pedido |
| **Merges em janela serial** (um por vez, na ordem, conferindo a publicação entre um e outro) | Dois merges verdes que, juntos, quebram a publicação | **Alto** — é o gargalo: os robôs trabalham em paralelo, mas terminam em fila |
| **Um arquivo por entrada** (cada anotação nova é um arquivo novo, nunca uma linha acrescentada a um arquivo comum) | O conflito de texto clássico: dois robôs editando o mesmo parágrafo | Baixo — mas foi ela que criou a corrida de numeração da classe 3 |

O resumo honesto do desenho atual: **a segurança vem de manter os robôs
separados**. Cada trava nova estreita a fatia de mundo em que um robô pode
mexer. Eu quero o contrário — e não sei se é possível.

## O histórico REAL de colisões deste projeto

Isto não é hipótese: é o que já aconteceu, com data. Se a sua recomendação não
cobrir estas oito classes, ela não resolve o meu problema. Considere que **a
classe 1 já está curada** — as outras sete, não, ou só pela metade.

**Classe 1 — Duas sessões no mesmo diretório.** Em 26/08/2026, duas sessões
usaram a pasta principal ao mesmo tempo: a troca de ramo de uma apagou as
edições da outra, em silêncio, sem erro nenhum. No mesmo dia, uma segunda sessão
perdeu edições em seis arquivos do mesmo jeito. *Curada por mecanismo* (a
muralha da pasta compartilhada), **com uma fronteira honesta**: ela cobre as
ferramentas de edição e o git, mas não cobre um comando de terminal que escreva
o arquivo direto. É cerca, não jaula.

**Classe 2 — Recurso global do Git que não é por pasta.** Em 22/08/2026, no
primeiro lote paralelo, duas sessões usaram `git stash` ao mesmo tempo: a pilha
de stash é **uma só por repositório**, e cada uma desempilhou o trabalho da
outra. Arquivos de um serviço apareceram, não-commitados, na pasta de outro.
*Curada só por convenção escrita* ("em paralelo, não use stash, use patch") — ou
seja, **garantia sem mecanismo**: nada impede que aconteça de novo amanhã.

**Classe 3 — Corrida por um nome ou número livre.** A regra "crie um arquivo
novo com o próximo número livre" resolve o conflito de texto, mas cria outro:
duas sessões que listam a pasta ao mesmo tempo veem o **mesmo** número livre, e
as duas o usam. Como os nomes completos diferem, **o Git junta os dois sem ter
nada para detectar**. Aconteceu duas vezes no mesmo dia no catálogo de
armadilhas (24/08/2026) e **quatro vezes num dia só, entre três sessões**, no
livro de ocorrências (26/08/2026) — ali "o registro 037" deixou de ser uma
referência e virou uma pergunta. *Curada duas vezes, por dois validadores
diferentes, escritos separadamente* — um para cada superfície. **Toda superfície
nova reinventa a própria trava**, e é isso que me incomoda: não há cura de
classe, só cura de caso.

**Classe 4 — Mesma linha de um arquivo compartilhado.** Duas sessões marcando
linhas *diferentes* da mesma tabela colidiram assim mesmo (blocos vizinhos), e a
resolução certa era "as duas linhas sobrevivem" — o que um robô apressado
resolve facilmente descartando o trabalho alheio. *Tratada por desenho* (um
catálogo de 1.490 linhas virou um arquivo por entrada), mas ainda existem
arquivos comuns por natureza: a configuração da publicação, os arquivos-lei, os
índices gerados.

**Classe 5 — Trabalho duplicado invisível.** Em 26/08/2026, **duas sessões
desenharam a MESMA trava em paralelo**, sem nenhuma saber da outra; a duplicação
só foi descoberta por acaso, e uma acabou creditando a outra num comentário do
código. Nenhum arquivo colidiu, nenhum teste reprovou, o Git não tinha o que
detectar — e mesmo assim metade do esforço foi jogada fora. O único sinal que
existe hoje é o painel mostrar **para mim** os PRs abertos por área — o que
chega tarde (o PR só nasce depois do trabalho pronto) e chega no lugar errado
(a mim, não ao robô). **Nada impede dois robôs de começar a mesma coisa no
mesmo minuto.**

**Classe 6 — Colisão semântica entre entregas individualmente corretas.** Dois
PRs verdes, cada um perfeito isoladamente, que **juntos** quebram o sistema. O
caso pior já medido: uma entrega trouxe um serviço novo e a configuração da
publicação **no mesmo commit** — a publicação do serviço procurou no servidor
uma configuração que ainda não estava lá e abortou; a publicação da configuração
viu a outra vermelha no mesmo commit e se recusou a subir. **As duas travas
estavam certas.** O veneno e o antídoto no mesmo commit: nenhuma repetição
resolvia, só um terceiro PR. Nenhum sistema de "reservar arquivo" teria evitado
isso — os arquivos eram diferentes.

**Classe 7 — Recursos únicos fora do Git.** Existe **uma** VPS, **uma** fila de
publicação, **uma** ramificação principal, **um** Docker nesta máquina e **uma**
franquia mensal do meu plano de IA. Já aconteceu de dois processos rodarem a
migração do mesmo banco ao mesmo tempo e um morrer na corrida. Uma publicação
vermelha pausa a janela de merge de **todos**. Aqui o paralelismo não é só
inútil — é ativamente perigoso.

**Classe 8 — Conhecimento congelado (a mais grave, e a mais recente).** Medida
em 28/08/2026: uma sessão fez todo o seu reconhecimento ("o que já existe neste
sistema?") lendo a pasta principal, que estava **75 merges atrasada** em relação
ao repositório real — sem um único aviso, porque ler nunca dá erro. Ela entregou
ao mantenedor a afirmação sincera de que uma funcionalidade **não existia**;
existia havia um dia, com lei escrita e código publicado. Nada falhou: os testes
passaram, os portões ficaram verdes. O erro só apareceu quando eu li o texto e
respondi "mas isso já foi feito ontem". A versão geral do problema: **um robô
que começou às 14h decide com o mundo das 14h, enquanto outros quatro mudam esse
mundo até as 15h.**

## RESTRIÇÕES DURAS — leia antes de recomendar qualquer coisa

Se a sua recomendação violar alguma delas, ela é inútil para mim. Pode
argumentar contra uma restrição, mas argumente — não a ignore.

1. **Não existe orquestrador rodando o tempo todo.** Não há servidor meu, não há
   processo em segundo plano, não há vigia. O que existe entre as sessões é: o
   repositório Git, a API do GitHub (Actions, PRs, issues, labels) e o disco
   deste PC. Qualquer coordenação tem que caber num desses três.
2. **Plano gratuito, repositório privado pessoal.** A proteção nativa de
   ramificação do GitHub (revisão obrigatória, fila de merge nativa) **está fora
   de alcance** — já testamos: exige plano pago, e não há forma de pagamento
   aceita. Se a sua proposta depende de "fila de merge do GitHub", diga como
   fazer o equivalente com o que eu tenho.
3. **Não recomende ferramentas de coordenação com conta e mensalidade** (Jira,
   Linear, Temporal, um serviço de fila gerenciado). O mecanismo mora junto do
   projeto, versionado. Se você acha essa decisão errada, argumente.
4. **Nada pode depender de disciplina diária minha.** Eu não arrasto cartão, não
   preencho formulário, não sou o árbitro de quem trabalha em quê. Qualquer
   desenho em que eu sou a trava vai falhar — eu durmo, e os robôs não.
5. **Nada pode depender de disciplina do robô.** Esta é a mais importante. Toda
   regra que ficou só "escrita no documento" neste projeto acabou violada por
   uma sessão sob pressão. O nome disso aqui é **garantia sem mecanismo**, e é a
   categoria de falha que mais nos custou. Recomendação boa é a que **recusa**,
   não a que **pede**.
6. **A sessão de IA é volátil e pode morrer no meio.** A janela fecha, a franquia
   acaba, a internet cai. Qualquer trava que um robô "pegue" precisa ter resposta
   pronta para o robô que morreu segurando a chave.
7. **Eu leio somente português e não entendo jargão cru.** Sigla sem tradução,
   para mim, é ruído. Escreva para mim — o robô que vai executar entende o resto.
8. **Não recomende "comece pequeno" ou "faça uma versão mínima para economizar
   tempo".** É regra firme e informada deste projeto: entre a opção completa e a
   reduzida, escolho a completa, mesmo custando mais tempo. Fatiar a construção
   em etapas seguras é bem-vindo; **cortar escopo por pressa, não.** Se algo for
   genuinamente inviável ou perigoso, diga que é inviável — isso é fato, não é o
   conselho que estou recusando.
9. **Assunto fora desta consulta:** cobrança e pagamento estão deliberadamente
   pausados por decisão minha. E há uma consulta paralela em andamento sobre a
   *tela* de acompanhamento das tarefas (um quadro tipo kanban com a fila dos
   robôs). **Esta consulta aqui é sobre o andar de baixo:** o mecanismo que
   impede a colisão de verdade. Não redesenhe a tela.

## As perguntas que quero que você responda

Responda na ordem, com franqueza e priorizando. Prefiro uma recomendação forte e
justificada a cinco fracas.

1. **A premissa está certa?** É possível ter robôs trabalhando com liberdade
   ampla — vários ao mesmo tempo, em qualquer parte do sistema — sem colisão? Ou
   "não colidir" é sempre comprado com restrição, e o que eu devo procurar é a
   **fronteira ótima** dessa troca? Defenda a sua posição. Se for troca
   inevitável, diga onde você poria a linha e por quê.

2. **O que substitui a cerca "1 PR = 1 célula"?** É a trava que mais me custa
   liberdade. Se eu quisesse permitir que um robô mudasse três serviços de uma
   vez com segurança, o que teria que existir no lugar dela? E o que desse
   desenho roda **sem servidor e sem plano pago**?

3. **Quem deve ser o árbitro de "esta parte do sistema é minha agora"?** Vejo
   três candidatos: (a) o próprio Git — um arquivo de reserva com nome fixo por
   tarefa, em que a segunda tentativa colide de propósito; (b) a API do GitHub —
   issues, labels ou o próprio PR aberto funcionando como reserva; (c) o disco
   local — um arquivo de trava na máquina. Compare os três: qual é mais
   confiável, como cada um falha, e o que acontece com cada um quando o robô
   morre segurando a reserva (restrição 6). Existe um quarto candidato?

4. **A classe 6 (colisão semântica) é a que nenhuma reserva resolve** — dois PRs
   verdes, arquivos diferentes, que juntos quebram o sistema. Que mecanismo
   ataca essa classe? Testar o resultado da junção antes de mergear? Declarar
   dependência entre entregas? Publicação em etapas? Diga o que você usaria e o
   que ele custa quando aplicado errado.

5. **As classes 5 e 8 são sobre informação, não sobre arquivos** — trabalho
   duplicado invisível, e robô decidindo com um mapa velho. Como um robô fica
   sabendo (a) o que os outros quatro estão fazendo **neste momento** e (b) o que
   o mundo aprendeu nos últimos 40 minutos, **sem depender de eu contar** e sem
   gastar metade da memória dele lendo o projeto inteiro? Considere que ler o
   repositório é a primeira coisa que uma sessão faz, e que **ler nunca dá
   erro** — é por isso que o mapa velho passa despercebido.

6. **Qual é o modo de falha do sistema que você propuser?** Descreva
   concretamente como ele apodrece daqui a três meses, e que mecanismo — não que
   boa intenção — impede o apodrecimento. Já sei que promessa de disciplina não
   funciona aqui: foi exatamente assim que regras anteriores deste projeto
   morreram.

7. **O que fazer com o robô que morre no meio?** Sessão fechada, franquia
   acabada, PC desligado — segurando uma reserva, com um ramo pela metade e um
   PR aberto. A limpeza tem que ser automática ou tem que esperar? Quem decide
   que um trabalho foi abandonado, sem nenhum processo rodando para vigiar?

8. **Existe teto de paralelismo?** Hoje eu disparo até 5 frentes ao mesmo tempo.
   Existe um número a partir do qual o custo de coordenação supera o ganho — e o
   que determina esse número: a quantidade de serviços, a taxa de conflito
   medida, a fila da publicação, outra coisa? Como eu mediria isso, em vez de
   chutar?

9. **O que você vê que eu não perguntei?** Pontos cegos, riscos, e coisas que
   costumam derrubar sistemas multiagente como este.

## Como quero a resposta

- **Em português**, direta e priorizada. Comece dizendo se concorda ou discorda
  da premissa da pergunta 1 — não me faça caçar a sua posição.
- **Discorde explicitamente** onde discordar.
- Toda recomendação precisa ser **executável por um agente de IA escrevendo
  arquivos no repositório e usando Git e a API do GitHub**. Se depender de
  servidor, ferramenta paga, ou de alguém vigiando, **diga isso na hora**, para
  eu já descartar.
- **Prefira mecanismos que recusam a regras que pedem.** Para cada coisa que
  você recomendar, responda numa linha: *o que exatamente acontece quando um robô
  tenta fazer errado?* Se a resposta for "ele leu a regra e não deveria fazer",
  eu já sei que não funciona aqui.
- Se citar um método (fila de merge, reserva otimista, bloqueio pessimista,
  divisão por dono, o que for), diga **quem o usa na prática, em que escala**, e
  o que ele custa quando aplicado errado.
- **Nada de plano por fases com prazos em semanas.** Diga o que fazer e em que
  ordem; aqui o tempo se mede em dias.
