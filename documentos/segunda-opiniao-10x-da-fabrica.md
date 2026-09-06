---
titulo: A segunda opinião de 10x, por cinco especialistas (setembro de 2026)
publico: false
ordem: 24
---

# A segunda opinião de 10x, por cinco especialistas (setembro de 2026)

Onde a cota de uma semana se esconde, medido por cinco ângulos que ninguém tinha olhado, e o que faz a fábrica render dez vezes mais pelo mesmo preço.

> Escrito em 6 de setembro de 2026, a pedido do mantenedor: "quero uma segunda opinião de uma equipe de especialistas para mais melhorias e otimizações de 10x". Foi no mesmo dia em que ele viu 47% da cota semanal consumida em 36 horas. Cinco especialistas foram convocados, cada um num ângulo que as duas análises anteriores não tinham medido: as alavancas de 5 de setembro mediram TEMPO, e a lei "O que uma chamada custa", de 6 de setembro, mediu COTA. Todos só leram e mediram; nenhum editou nada. Os números vêm das transcrições dos robôs de 5 e 6 de setembro, e a seção **Como conferir cada número** diz o comando de cada medição.

## A resposta em uma frase

A fábrica não desperdiça trabalho, desperdiça idas e voltas. Cada comando que um robô roda reenvia a conversa inteira, e a conversa fica cara por três motivos: a fábrica nunca agrupa (92% das chamadas usam uma ferramenta só), acorda o robô para ler um placar (a espera dos checks custa um quinto da semana), e manda o robô buscar o que a máquina já sabe (o endereço da armadilha, o número do registro, a causa do check vermelho). Os cinco chegaram ao mesmo lugar por caminhos diferentes: o 10x vem de cortar chamadas, nunca de cortar trabalho.

## Os cinco ângulos e quem os mediu

- **O contador de tokens** mediu o custo fixo que entra em toda chamada sem ninguém pedir.
- **O engenheiro de idas e voltas** decompôs o rito de um PR, fase por fase, em chamadas.
- **O especialista no Claude Code** listou o que a ferramenta já oferece e a casa não usa.
- **O auditor de retrabalho** mediu o que se faz duas vezes, e quanto cada volta custa.
- **O crítico da papelada** mediu a escrituração obrigatória em tokens, não em segundos.

## Onde os cinco convergem

### 1. A espera é a alavanca número um, e três chegaram nela sozinhos

Um robô que espera os checks de um PR é acordado toda vez que o placar muda ("3 de 7 verdes") e a cada 60 segundos calado. Cada despertar reenvia a conversa inteira, e a espera acontece no momento mais gordo da sessão: contexto mediano de 372 mil a 401 mil tokens. Os três que mediram chegaram a 18%, 21,5% e 21,8% da semana. É a maior peça isolada da cota, e o robô não faz nada nela além de ler o placar.

### 2. O robô busca o que a máquina já sabe

- Quando um check reprova, a espera diz o NOME do check e manda "ver o link do run". O robô gasta em mediana **41 chamadas** para descobrir a causa que o CI já tinha impresso. Foram 32 episódios na semana, 12% da cota.
- Quando o sino das armadilhas casa uma assinatura, ele imprime o endereço da armadilha e o robô gasta uma chamada inteira (206 mil tokens de contexto) para ler 996 bytes. Foram 891 chamadas, 4,3% da semana.
- O número do registro do livro é escolhido olhando a pasta, e outra sessão escolhe o mesmo. Houve 4 colisões só em 6 de setembro, todas DEPOIS de a lição do caminho ter pousado. Ensinar não bastou. Cada colisão custa uma rodada de checks e o diagnóstico dela.
- O sub-agente que recebe uma tarefa gasta em mediana **57 chamadas** lendo o código antes da primeira edição, porque o despacho diz a célula e não os arquivos. São 28% do orçamento de todos os sub-agentes.

### 3. Três suspeitos foram absolvidos com número

Os ganchos que rodam a cada comando custam **0,7%** da semana; o sino só fala quando tem fato. A papelada obrigatória, medida como texto escrito, custa **0,3%**. As armadilhas novas da semana são 0,45 por PR, e 11 das 15 lidas são lição de verdade, com sintoma, sinal e guarda. O erro que as duas análises anteriores quase cometeram, e que esta desfaz, seria mexer nos ganchos e na papelada: é o lugar errado.

## As alavancas, na ordem do ganho

Cada ganho é a conta do especialista que o mediu, em tokens por semana. As réguas dos cinco diferem um pouco (cada um recortou a semana de um jeito), então as porcentagens são ordens de grandeza, e o comando que as reproduz está no fim. Nenhuma alavanca tira um passo do rito, uma lei do lugar ou uma linha de escopo: o que muda é o número de idas, nunca o número de gestos.

### Família A: o robô deixa de acordar à toa

**A1. A espera fala a partida, uma vez na metade do teto, e o desfecho.** O placar continua gravado no arquivo da espera, para auditoria, e o teto continua matando a espera travada. O que sai é o despertar do robô a cada mudança de placar. Ganho: de 5,5 despertares por espera para 1,5; **386 a 529 milhões por semana (10% a 13%)**. Toca `ci/esperar.py` e a lei da espera (RITOS §2 peça 6). Risco: o mantenedor deixa de ver o batimento na janela; o chip da espera continua visível enquanto ela roda. Se isso basta para ele é decisão dele.

**A2. A espera reprovada diz a causa, não o nome do check.** A espera já sabe quais checks caíram; passa a buscar o log do job reprovado, extrair o bloco de falha (cinco linhas, teto duro) e casá-lo com as armadilhas pelo mesmo sinal que o sino usa. O robô sai do aviso sabendo "renomeie o registro para o próximo número livre" em vez de "vá ver o link". Ganho: **até 440 milhões por semana, 11 PRs de cota**. Toca `ci/esperar.py`. Risco: log lento; com teto de tempo, cai para o texto de hoje.

### Família B: a máquina entrega o que já sabe

**B1. O sino entrega a lição, não o endereço.** Quando casa uma assinatura, injeta as seções "sintoma" e "o que fazer" da armadilha no próprio retorno do gancho, com teto de 1,5 KB, e o caminho para o resto. Ganho: 891 chamadas viram zero; **145 milhões, 4,2%**. Toca `ci/sino_das_armadilhas.py`. Risco: sessão que casa muitos sinais engorda 1,5 KB por casamento, contra 206 mil hoje.

**B2. O número do registro é dado na hora de gravar, nunca escolhido.** A reserva atômica já existe (`ci/reservar.py numero registro`) e não é exigida. O gancho da lição do caminho passa a recusar a gravação de registro cujo número não tenha reserva desta sessão, e a recusa já traz o número alocado. Ganho: **100 a 250 milhões por semana**, e a classe some por construção. Toca `ci/licao_do_caminho.py`. Nasce em sombra, pela lei do Sistema Imunológico.

**B3. O reconhecimento vem no despacho, e a leitura é em bloco.** O despacho da fila ganha um bloco obrigatório com os arquivos da tarefa (caminho e âncora pelo nome, nunca número de linha), que a maestro já tem porque foi ela quem mediu a tarefa. E o robô lê vários arquivos na mesma chamada, pela ferramenta de leitura, em vez de um `sed` por vez. Ganho: **292 milhões** (leitura em bloco) mais **90 a 180 milhões** (mapa no despacho), e o robô começa a escrever 25 chamadas antes. Toca `ci/fila.py`, a ficha do despacho e o molde de brief.

**B4. Os papéis obrigatórios nascem preenchidos pela máquina, e o robô escreve só o julgamento.** O registro do livro tem 14 campos e 11 são deriváveis do PR (título, data, endereço, frente); só o `detalhe` é julgamento, e ele é 35% do arquivo. O evento "concluída" da fila tem 6 campos e todos existem na hora do pouso. O relatório de seis blocos tem quatro cujos fatos estão no diff, nos checks e no plano. Um gerador preenche os fatos, deixa o julgamento em branco e RECUSA gravar vazio: a única frase que o mantenedor lê continua sendo escrita por quem fez o trabalho. Ganho: **cerca de 5% da semana**, e a armadilha 185 (registro sem número) morre por construção. Toca `ci/`, `painel/LEIA-ME.md` e a lei da prestação de contas: cada peça é lei do mantenedor.

**B5. O orçamento e o balcão falam antes do push e antes da pasta.** Dois ganchos: um roda o orçamento de mudança localmente ao ver `git push`; outro consulta o balcão ao ver `git worktree add` (leitura, não reivindicação). Ganho: **201 milhões**. Toca `ci/` e `.claude/settings.json`.

### Família C: dezessete idas viram uma

**C1. Do commit ao pouso armado, num comando.** Os passos de escrituração, PR e conferência são 17 chamadas totalmente determinísticas: adicionar, commitar, enviar, abrir o PR, ler o número, pedir o número ao almoxarife, escrever o registro pelo molde, conferir o livro, concluir na fila, segundo commit, enviar. Numa sessão medida foram 20 idas e voltas entre o primeiro `git add` e a espera, com o almoxarife chamado duas vezes e três `git status`. Um `make pr` faz os mesmos gestos numa ida, imprimindo PASS ou FAIL por linha, idempotente, com `--continuar` para retomar de onde parou. Ganho: 14 chamadas por PR, **344 milhões por semana**. Toca `Makefile`, `ci/` e a ficha do despacho.

**C2. A bancada e a suíte de partida no comando que já existe.** `ci/sessao.py` se descreve como "os 6 primeiros minutos do RITOS §1 em UM comando" e foi usado **uma vez em 10.534 comandos**, porque a ficha do despacho ensina os cinco comandos à mão. Estender e mandar a ficha chamá-lo. Ganho: 11 chamadas viram 1, **246 milhões**. Toca `ci/sessao.py` e a ficha.

**C3. Nenhum arquivo entra duas vezes na mesma conversa.** Um terço das leituras é o mesmo arquivo relido na mesma sessão (`models.py` 49 vezes, `views.py` 48, e o próprio `CLAUDE.md` 27 vezes dentro de sessões que já o carregam). Um gancho que avisa, pela data de modificação, quando o arquivo não mudou desde a última leitura. Ganho: **120 milhões**. Nasce em sombra.

**C4. Saída de arquivo pelo shell com teto, e escrita inteira vira edição.** A ferramenta de leitura trunca em 2.000 linhas; `cat` e `git show` não truncam nada, e 10% dos resultados carregam 58% dos bytes. E reescrever um arquivo inteiro custa 3,7 vezes uma edição, com o conteúdo reenviado em anexo. Ganho: **125 milhões** mais **96 milhões**. Sugestão, não bloqueio.

**C5. Desligar os catálogos de ferramentas que ninguém chama.** Cinco servidores de ferramentas entram no preâmbulo de toda chamada e foram chamados zero vezes na semana. Ganho: **156 milhões, 3,2%**, sem perder capacidade (liga-se de volta numa linha). Toca `.claude/settings.json`.

### Para depois, com o gatilho já batido

**A fila de merge nativa do GitHub.** O documento das alavancas mandou medir depois das alavancas 1 e 2 e só trocar se as voltas de base envelhecida ficassem acima de uma por PR. Ficaram em **1,375** (88 voltas para 64 PRs), contra 2,10 antes: caiu 35% e continua acima da linha. Ganho: 264 milhões e a classe some por construção. É a de maior risco, porque a pista carrega seis decisões que não podem se perder, e por isso fica por último.

## O que multiplica com o quê

O engenheiro de idas e voltas mediu o teto: **46 chamadas por PR em vez de 117**, sem tirar um passo. Isso sozinho é 2,5 vezes menos idas, mas vale mais, porque o contexto da chamada N cai junto com N: uma conversa 2,5 vezes mais curta termina 2,5 vezes mais leve, e o custo cresce com o quadrado do número de turnos. Um PR sairia de 32,7 milhões para cerca de 6,4 milhões de tokens: **5 vezes**.

O 10x fecha somando isto ao que as duas rodadas anteriores já decidiram e que multiplica com esta em vez de repetir: o modelo escolhido em vez de herdado (corta o preço de cada token) e o lote em paralelo (impede o contexto de crescer; 80 dos 124 PRs da semana foram feitos dentro da maestro, cujo batimento roda a 372 mil em vez de 157 mil).

## A dúvida que muda a ordem de tudo

O especialista no Claude Code levantou a única pergunta que nenhum dos cinco conseguiu responder de dentro: **se a cota semanal conta a releitura de cache com peso cheio ou com um décimo**. Na API, releitura custa um décimo. Se a cota fizer o mesmo desconto, os 4,92 bilhões da semana valem perto de 500 milhões equivalentes, e a ordem das alavancas muda: as que cortam contexto novo e saída sobem, as que cortam releitura descem. Como conferir: uma segunda fotografia do painel de uso, comparada com a das 12h de domingo, contra os tokens brutos gastos entre as duas. Até lá, a ordem acima é a da hipótese de peso cheio, que é a mais conservadora.

## O que os especialistas descartaram, com o número

- **Os ganchos, todos:** 0,7% da semana. O sino dispara em 5,9% dos comandos e custa 227 bytes. Mexer neles é mexer no lugar errado, e cada um segura uma lei.
- **A papelada como texto escrito:** 0,3%. Ela custa como ida e volta (família B4), não como escrita.
- **Reduzir o número de registros:** os 111 da semana são 33 mil tokens, 0,001%. Menos registros não economiza nada e cega o painel.
- **Encurtar o relatório final por regra de tamanho:** rende 0,4% e degrada o único canal que o mantenedor lê.
- **Mexer nas armadilhas:** 0,45 por PR, 11 de 15 são lição de verdade. O que é caro é LER, e isso é a B1.
- **Os comandos de saída gorda (pytest, gh, git log):** 1,1%. O gordo é ler arquivo, não rodar comando.
- **Cache frio por espera longa:** 1,6%. Não é alavanca.
- **O CLAUDE.md por diretório:** 2,3% de ganho e risco alto, porque lei que só carrega quando o robô já está dentro da pasta chega tarde para quem decide se entra. Não recomendado.
- **Trocar a muralha da pasta compartilhada por permissão negada:** zero de ganho e perde a medição da idade do espelho.
- **Escrever a papelada num modelo mais barato:** já é lei de 6 de setembro; ataca 20% do preço de uma chamada, enquanto a B4 remove a chamada inteira.
- **Tirar ou afrouxar qualquer portão:** o que reprovou o PR #1197 estava certo. O retrabalho é a colisão, não a recusa.

## Dois achados fora de ângulo, para registro

- **A ficha do escrivão nunca foi disparada** em 25 sessões: a ficha do despacho manda ele mesmo escrever o registro. A lei de 6 de setembro pôs um guarda no modelo dela, e o guarda protege uma ficha morta. Ela continua no preâmbulo de toda sessão à toa.
- **O checklist por etapa apareceu 3 vezes em 121 PRs.** É a peça que o mantenedor pediu com as palavras dele e a única que ele quase não recebeu; a armadilha 350 já diz que ela não tem discriminador mecânico. Um gancho que conta chamadas desde a última caixinha e cobra passando de N, em sombra, custaria 0,3% da semana e sai inteiro do que as famílias A e B economizam.

## O que fica com o mantenedor

Todas as alavancas tocam `ci/`, `.claude/` ou leis da raiz, que são caminhos com dono: nenhum robô as constrói sem mandato. E quatro delas mexem em regras que ele decidiu com motivo escrito:

1. **A voz da espera** (A1): o batimento na janela dele era o motivo da lei; se o chip da espera basta, o batimento pode calar.
2. **O `detalhe` do registro** pode nascer de um molde de máquina com o campo em branco (B4).
3. **O evento "concluída"** pode ser emitido pela porta do merge, sem robô no meio (B4).
4. **Os fatos do relatório final** podem chegar prontos ao robô, com o julgamento separado e recusado se vazio (B4).

Nada aqui muda o que o aluno vê no site. Tudo é a fábrica custando menos por trás.

## Como conferir cada número

Todos os comandos rodam na raiz do repositório, no PC.

- Tokens por chamada, por sessão e por modelo, e a fração da espera: o script em `armadilhas/367`, ampliado para agrupar por `isSidechain` e por origem do turno (`task-notification`).
- Chamadas por fase do rito: agrupar os `tool_use` de uma sessão de `despacho` por nome e posição; o `ci/sessao.py` usado uma vez: `grep -c "sessao.py" ~/.claude/projects/**/*.jsonl`.
- Diagnóstico depois de REPROVADO: contar chamadas entre a linha "terminou REPROVADO" e a primeira edição seguinte, nos mesmos transcripts.
- Voltas de base envelhecida depois das alavancas: `git log origin/main --since="2026-09-05 20:00" --grep="Merge branch 'main' into" --oneline | wc -l` contra os merges de PR na mesma janela.
- Colisões de número: `gh run list --workflow muralhas.yml --limit 500` e, nos reprovados, `gh run view <id> --log-failed | grep -m1 "número repetido no mesmo dia"`.
- Custo fixo do preâmbulo: o `cache_creation_input_tokens` da primeira chamada de cada sessão.
- Leituras repetidas: os `tool_result` de `Read`, `cat`, `sed` e `git show` agrupados por caminho dentro de uma sessão.
- O que cada peça de papelada custa: as chamadas cuja ferramenta escreve em `painel/registros/`, `fila/eventos/` ou `armadilhas/`, com o contexto de cada uma.
