---
titulo: As alavancas de 10x da fábrica (setembro de 2026)
publico: false
ordem: 22
---

# As alavancas de 10x da fábrica (setembro de 2026)

Onde o tempo de um pedido se esconde hoje, medido, e o que muda a velocidade por uma ordem de grandeza.

> Escrito em 5 de setembro de 2026, a pedido do mantenedor: "analise o processo de criação de algo no site e me mostre o que pode ser feito nesse projeto que aumentaria em 10x ou mais a velocidade de execução das tarefas". Tudo o que está aqui foi medido nesse dia: 120 PRs pousados em 4 e 5 de setembro, 200 execuções da esteira, e as transcrições das 60 sessões de robô mais recentes. A seção **Como conferir cada número** diz o comando de cada medição. Os números são a fotografia daquele dia; a régua viva é `python ci/metricas_da_fabrica.py`.

## A resposta em uma frase

O robô que escreve código não é o gargalo. Um pedido leva horas porque os pedaços dele são feitos um atrás do outro pela mesma cabeça, porque cada pedaço espera de 15 a 30 minutos numa esteira cujo passo mais lento é uma conferência que ninguém exige, e porque entre uma sessão do mantenedor e a próxima nenhum robô trabalha.

O 10x não vem de um lugar só. Vem de três multiplicações que se somam: os pedaços em paralelo (×4 num pedido de cinco pedaços), a esteira sem a espera inútil (×2,5 por pedaço) e os robôs acordados quando ele não está (o "ou mais", em tempo de calendário).

## O caminho de um pedido hoje, medido

Um pedido do mantenedor atravessa cinco trechos. Os tempos são medianas.

- **Da mensagem dele à primeira edição de arquivo: 13 minutos e meio.** É o tempo em que o robô lê antes de escrever. Medido em 43 sessões que abriram PR.
- **Do começo da tarefa ao PR aberto: 23 minutos.** O robô cria a bancada, roda a suíte, escreve, testa, escreve o registro e abre o PR. A escrituração (registro, evento da fila, armadilha) custa 42 segundos entre o PR aberto e a espera armada: não é ela que pesa.
- **Do PR aberto ao PR pousado: 14,6 minutos** nos 120 PRs de 4 e 5 de setembro, e **29 minutos** na semana inteira segundo o termômetro da fábrica. Nesse trecho o robô só espera.
- **Do pouso ao site no ar: 3,7 minutos.** Desses, 1 minuto e 22 segundos é o portão de deploy esperando o alarme da main terminar; o build da imagem leva 23 segundos e a ativação na VPS, 32.
- **Uma sessão típica dura 199 minutos e pousa 5 PRs, um atrás do outro.** No pico, o contexto dela chega a 490 mil tokens, e a partir daí cada turno fica mais lento e menos preciso.

Somando por pedaço: perto de 40 minutos de relógio, dos quais uns 20 são espera pura. Um pedido de cinco pedaços em série é uma tarde.

## Onde os minutos se escondem: os cinco achados

### 1. A conferência do Windows manda no relógio de todo PR

A esteira `muralhas` leva 5,8 minutos por PR. O job chamado `muralhas`, que é o que a proteção da `main` exige, termina em 80 segundos. Quem segura os outros 4 minutos é o job `windows-a-maquina-dos-robos`, que roda a suíte dos portões num executor Windows em 4 minutos e 50 segundos (a mesma suíte leva 41 segundos no Linux, no mesmo PR).

A proteção da `main` exige só dois checks: `muralhas` e `ci-celula-gate`. Mas a espera do robô (`ci/esperar.py --checks`), o portão de pouso (`ci/mergear.py`) e o despertador da pista (o evento de conclusão do workflow inteiro) esperam **todos** os checks. Então um job que o GitHub não exige é o que define quanto tempo todo PR desta casa fica parado. O relógio de um PR é o job mais lento, não a soma, e o mais lento é uma rede de segurança para um erro de página de código que já tem teste próprio no Linux.

### 2. A base envelhece e o PR roda tudo de novo

Desde 4 de setembro a `main` recebeu 71 PRs e **155 commits de "a base envelheceu"** (o `Merge branch 'main' into ...` que a pista faz ao atualizar um PR atrasado): 2,2 voltas por PR, e média de 5,4 commits por PR. Cada volta reinicia os checks e custa mais 6 minutos de espera.

A conta é simples: a `main` anda 60 vezes por dia; quanto mais tempo um PR demora para ficar verde, maior a chance de a `main` andar no meio e ele envelhecer de novo. Com checks de 5,8 minutos a corrida é perdida com frequência; com checks de 1,7 minutos (o que sobra sem o Windows) ela é perdida três vezes menos. A tarefa TAR-165 da fila ("a fome da pista voltou: o teto de espera não acompanhou o check mais lento") é o sintoma deste achado, e o achado 1 é a causa.

### 3. A suíte dos portões roda quatro vezes por PR

A suíte que testa os próprios portões (`ci/tests/`, 82 arquivos, 29 mil linhas, e cresce a cada guarda novo) roda no job `muralhas`, de novo no job `espelho-da-main`, de novo no Windows, e uma quarta vez depois do merge, no `alarme-main`. O portão de deploy espera essa quarta rodada terminar antes de construir a imagem: são os 82 segundos do trecho "do pouso ao site". As três primeiras rodam sobre o mesmo commit e respondem a mesma pergunta.

### 4. Os pedaços de um pedido são feitos em série pela mesma cabeça

A lei de 5 de setembro diz que todo pedido do mantenedor é um lote: a sessão divide em pedaços e dispara um robô por pedaço, em paralelo. Medido nas transcrições: das 60 sessões mais recentes, **4** dispararam o robô construtor (`despacho`), 16 vezes ao todo. As outras fizeram os 5 PRs da mediana uma atrás da outra, na mesma janela, com o mesmo contexto crescendo até quase meio milhão de tokens.

Cinco pedaços em série são cinco vezes 40 minutos. Cinco pedaços em paralelo são 40 minutos mais a consolidação. É a maior multiplicação disponível, já é lei, e ainda não é o comum. Lei que depende de lembrança é a doença-mãe desta casa; o que falta aqui é um mecanismo que diga, no fim do turno, "este turno abriu N PRs em série sem despachar ninguém".

### 5. Entre uma sessão dele e a próxima, nada anda

A fila tem 11 tarefas com despacho pronto e dependências satisfeitas, esperando por um robô, e 10 atrás delas. O único gatilho que existe é o mantenedor abrir uma janela e digitar. O despachante que acorda sozinho (degrau 2 do plano de orquestração autônoma) está desenhado e espera duas decisões dele: o teto de tarefas por dia e quais tarefas da fábrica ele pode pegar.

Este é o "ou mais" do pedido: uma tarefa que hoje espera 18 horas por uma janela dele passaria a esperar 2. Nenhuma alavanca dentro da sessão compete com isso em tempo de calendário.

## O que NÃO é o gargalo, para ninguém mexer no lugar errado

- A escrituração: 42 segundos por PR entre abrir o PR e armar a espera.
- Os ganchos da sessão: quatro programas por comando, 130 milissegundos cada, perto de 2 minutos numa sessão inteira.
- A pista de pouso: 30 segundos por passagem.
- O deploy em si: 23 segundos de build e 32 de VPS.
- A velocidade com que o robô escreve código.

## As alavancas, na ordem, com o ganho medido

### Alavanca 1: tirar a conferência do Windows do caminho do PR

O job Windows sai do workflow `muralhas` e vira uma rede na `main`, rodando a cada merge, como o `alarme-main` já faz, abrindo issue se reprovar. A cobertura continua a mesma (todo commit da `main` passa por ele); o que muda é que nenhum PR fica parado esperando por ele.

Ganho por PR: checks de 5,8 para 1,7 minutos, e as voltas de base envelhecida caem junto (achado 2). Do PR aberto ao pouso, de perto de 15 para perto de 6 minutos. Toca `.github/` e `ci/` (o teste que amarra os jobs do workflow), caminho CODEOWNERS: precisa de mandato do mantenedor.

### Alavanca 2: a suíte dos portões roda uma vez, e o deploy não espera o alarme

O job `espelho-da-main` fica com o que só ele faz (a guarda de segredos do repositório inteiro) e deixa de repetir a suíte dos portões. O portão de deploy deixa de esperar o `alarme-main`: o commit que chega à `main` já foi medido por esses mesmos checks, no mesmo conteúdo, antes do pouso. O alarme continua rodando e continua abrindo issue se a `main` quebrar; ele só deixa de ser um degrau na frente do deploy.

Ganho: 82 segundos por deploy (de 3,7 para 2,3 minutos) e um executor a menos por PR. Toca `.github/` e `ci/portao_de_deploy.py`: mandato.

### Alavanca 3: o lote deixa de depender de lembrança

O gancho de fim de turno (`ci/prestacao_de_contas.py`) já lê a transcrição para cobrar a prestação de contas. Ele passa a contar, em sombra, quantos PRs o turno abriu e quantos robôs despachou, e diz na cara quando abriu dois ou mais em série sem despachar nenhum. Regra nova nasce em sombra, dizendo o que teria feito, pela lei do Sistema Imunológico; quando a medição mostrar que o aviso muda o comportamento, ele gradua.

Ganho: é o ×4 do achado 4, num pedido de cinco pedaços. Toca `ci/`: mandato.

### Alavanca 4: o despachante que não dorme

É o degrau 2 do plano de orquestração autônoma, já aprovado na escada e parado nas duas decisões do mantenedor. Ganho em tempo de calendário: as 11 tarefas prontas da fila deixam de esperar uma janela dele.

### Alavanca 5, para depois das quatro: a fila de merge nativa do GitHub

O GitHub oferece uma fila de merge própria, gratuita em repositório público, que agrupa PRs, testa o conjunto uma vez e mergeia em lote: as voltas de base envelhecida deixam de existir por construção. A pista desta casa nasceu quando se acreditava que a proteção da `main` não estava disponível, e carrega seis decisões que não podem se perder na troca (a chave que dispara o deploy, o recibo a bordo, o revisor de pouso). Por isso ela é a quinta e não a primeira: as alavancas 1 e 2 devem ser medidas antes, e se as voltas caírem para menos de uma por PR, a troca não paga o risco.

## O que multiplica com o quê

- Um pedaço só: de perto de 40 minutos para perto de 22 (alavancas 1 e 2). Os 13 minutos de leitura no começo não mudam com nada disto, e são o próximo alvo depois destas.
- Um pedido de cinco pedaços: de perto de 200 minutos para perto de 45 (alavanca 3), e para perto de 30 com as alavancas 1 e 2 juntas. É o ×7 dentro de uma sessão.
- Uma tarefa deixada na fila à noite: de "amanhã, quando ele abrir a janela" para "feita quando ele acordar" (alavanca 4). É aqui que mora o "ou mais".

## Como conferir cada número

Todos os comandos rodam na raiz do repositório, no PC, com o `gh` autenticado.

- Tempo do PR aberto ao pouso e voltas de base velha: `python ci/metricas_da_fabrica.py --dias 7`
- Duração de cada job de um PR: `gh run view <id do run de muralhas> --json jobs`
- Voltas de base envelhecida desde uma data: `git log origin/main --since=2026-09-04 --grep="Merge branch 'main' into" --oneline | wc -l`
- Merges de PR na mesma janela: `git log origin/main --since=2026-09-04 --merges --grep="Merge pull request" --oneline | wc -l`
- Os checks que a `main` exige de verdade: `gh api repos/abundanciabr/sitesdoreino/rulesets`
- Onde o deploy gasta o tempo: `gh run view <id do run de deploy-celula> --json jobs`
- A fila e quem está com o quê: `python ci/fila.py listar --ao-vivo`
- Os tempos dentro das sessões de robô vêm das transcrições em `~/.claude/projects/`, lidas em 5 de setembro de 2026; o método está no registro do livro que acompanha este documento.

## O que fica com o mantenedor

As alavancas 1, 2 e 3 tocam `.github/` e `ci/`, que são caminhos com dono: nenhum robô as constrói sem mandato dele. A alavanca 4 espera as duas decisões já registradas na caixa "Precisa de você". Nada aqui muda o que o aluno vê no site: tudo é a fábrica ficando mais rápida por trás.
