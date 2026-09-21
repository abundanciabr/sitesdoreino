publico-para-ia: true

# Plano mestre da fila de deploy: a ordem de execução do programa deploy sem perdas

Versão: 1.3
Data: 20/09/2026
Autoridade: pedido direto do mantenedor nesta conversa
Tarefa deste documento: TAR-527
Responsabilidade de acompanhamento: operacao-tecnica
Programa a que pertence: `docs/decisoes/PLANO-MESTRE-DEPLOY-SEM-PERDAS.md` (TAR-528)

## 0. Relação com o programa deploy sem perdas

No mesmo dia, duas tarefas do mantenedor produziram dois documentos sobre o
mesmo problema. `PLANO-MESTRE-DEPLOY-SEM-PERDAS.md` (TAR-528, PR 1798, na
main desde 12:28 UTC de 20/09/2026) é o programa: arquitetura alvo, doze
invariantes DEP-01 a DEP-12, sete fases e onze PRs. Este documento não repete
nada disso. Um fato do projeto mora em um lugar só, e a arquitetura mora lá.

O que este documento acrescenta, e só isto:

1. a ordem de execução dos primeiros degraus, com a decisão do mantenedor de
   20/09/2026 de pôr a fila nativa na frente das fases de imagem imutável, e
   a medição que torna essa ordem segura;
2. a decisão por célula dentro do próprio `deploy-celula`, que entrega a parte
   do reconciliador (Fase 5 do programa) que não precisa de workflow novo, de
   SSH nem de disparo manual;
3. a prova, a auditoria e a reversão de cada um desses degraus, no grão que o
   despacho executa;
4. duas lacunas do programa que precisam de decisão antes da Fase 5 dele, e
   que este documento registra em vez de resolver por conta própria.

Mapa entre os dois:

| Este documento | Programa deploy sem perdas |
|---|---|
| degrau A, item 7 | Fase 3, fila nativa, antecipada por decisão do mantenedor |
| degrau B, item 8 | a metade da Fase 5 que cabe no `detectar`; invariantes DEP-02, DEP-03 e DEP-06 |
| degrau C, item 9 | o fecho de medição destes degraus |
| item 13 | Fases 0, 1, 2, 4 e 6 seguem no programa, cada uma com mandato próprio, depois de C |

As duas lacunas do programa, com a linha do arquivo na main:

- a Fase 5 lista "digest dos containers em execução" como entrada do
  reconciliador (linha 275) e, na mesma seção, diz que ele "não recebe chave
  SSH" (linha 293). Sem SSH, ninguém lê o digest de um container da VPS. A
  Fase 5 precisa decidir de onde vem esse dado, ou tirar a linha;
- a convergência que o reconciliador solicita "passa pelo portão normal e
  entra na mesma fila global" (linha 292). O `deploy-celula` só dispara por
  `push`, e `PROJETO-PORTAO-DEPLOY.md`, decisão 6, proíbe `workflow_dispatch`
  nele de propósito. Solicitar um deploy sem push exige ou revogar essa
  decisão, ou um commit novo na main, e o programa não diz qual.

Nenhuma das duas lacunas afeta os degraus A, B e C.

## 1. O que este plano é

Este documento é a fonte de sequência, prova e auditoria para os primeiros
degraus contra as armadilhas 173, 183 e 188: o grupo de concorrência `deploy`
guarda uma única vaga de espera, e o deploy que perde a vaga termina
`cancelled` sem log, sem alarme e com o merge fora do ar.

Ele descreve três degraus, cada um em um PR próprio, com a prova que fecha o
degrau e a medição no ar que autoriza o seguinte. Quem constrói é o despacho;
quem revisa antes do pouso é o revisor; quem verifica depois do merge é a
sentinela; quem autoriza os caminhos CODEOWNERS é o mantenedor, por mandato
nominal em cada PR.

## 2. O que este plano não é

- não altera workflow, `ci/`, `infra/` nem o comportamento de produção: só
  descreve. Pousar este arquivo reconstrói e republica a imagem da célula
  `admin`, como todo documento de `docs/decisoes/`, porque a pasta entra na
  imagem e está nos `paths:` do `deploy-celula`;
- não repete a arquitetura, os invariantes nem as alternativas recusadas do
  programa; onde precisa deles, cita a seção;
- não abre tarefa de implementação além da que o mantenedor já autorizou: o
  degrau A foi autorizado em 20/09/2026 e a tarefa dele, TAR-529, viaja neste
  mesmo PR com `depende_de` TAR-527; os degraus B e C nascem quando ele
  autorizar cada um, uma tarefa por PR, com este documento citado;
- não guarda estado de execução: quem responde "isto foi feito?" é o livro em
  `painel/registros/` e a fila em `fila/`, nunca uma lista aqui dentro;
- não edita as armadilhas existentes: lição nova é arquivo novo, e as entradas
  antigas continuam verdadeiras como história.

## 3. O problema, medido em 20/09/2026

| Esteira | Runs lidos na main | success | failure | cancelled |
|---|---|---|---|---|
| deploy-celula | 400 | 380 | 15 | 5 |
| deploy-infra | 49 | 40 | 5 | 4 |
| rollback | 8 | 6 | 2 | 0 |

Ritmo: 73 deploys em 08/09 e 52 em 19/09. Um deploy verde leva 3 minutos na
mediana e 14 no pior caso. O programa mediu o mesmo retrato às 08:55 BRT com
outra janela (item 4.6 dele: 100 runs, p50 de 3,7 minutos, p95 de 10,2,
pico de 14 chegadas numa hora); os dois retratos concordam. Comandos que
produziram a tabela e o ritmo daqui:

```bash
gh run list --workflow deploy-celula.yml --branch main --limit 400 --json conclusion --jq 'group_by(.conclusion) | map({c: .[0].conclusion, n: length})'
gh run list --workflow deploy-infra.yml --branch main --limit 100 --json conclusion --jq 'group_by(.conclusion) | map({c: .[0].conclusion, n: length})'
gh run list --workflow rollback.yml --branch main --limit 30 --json conclusion --jq 'group_by(.conclusion) | map({c: .[0].conclusion, n: length})'
gh run list --workflow deploy-celula.yml --branch main --limit 400 --json createdAt --jq 'map(.createdAt[0:10]) | group_by(.) | map({dia: .[0], n: length})'
gh run list --workflow deploy-celula.yml --branch main --status success --limit 40 --json createdAt,updatedAt --jq 'map(((.updatedAt|fromdateiso8601) - (.createdAt|fromdateiso8601))/60 | floor) | {min: min, max: max, mediana: (sort | .[length/2|floor])}'
```

O `deploy-celula` só dispara por `push`, então os 5 cancelados são todos de
push: não há disparo manual nessa esteira para confundir a conta.

A mecânica, em três fatos que se somam:

1. `concurrency: {group: deploy, cancel-in-progress: false}` em
   `deploy-celula.yml`, `deploy-infra.yml` e `rollback.yml`. Sem a chave
   `queue`, o GitHub guarda um único run pendente por grupo e cancela o
   pendente anterior quando chega outro (armadilha 173).
2. Cada run do `deploy-celula` decide quais células publicar pelo diff do
   próprio push (`BASE='${{ github.event.before }}'` no job `detectar`).
   O run seguinte começa onde o cancelado terminaria, então nunca publica a
   célula do cancelado (armadilha 183).
3. `cancelled` não é `failure`: nada fica vermelho, o `alarme-main` não
   dispara, e o histórico mostra uma linha cinza entre verdes (armadilha 188).

O que já existe e o que ainda não fecha:

- `vacina-do-deploy.yml` acorda no `cancelled` e no `failure` das duas
  esteiras e chama `ci/rerun_de_deploy.py`. Quem decide repetir é
  `_a_republicacao_avanca`: repete quando o publicado é ancestral do SHA
  doente, ou quando o publicado é mais novo mas alguma célula daquele push
  nunca foi construída por ninguém (TAR-017, TAR-029, TAR-210).
  `_porque_republicar` só escreve a frase do log.
- O rerun entra na mesma fila de vaga única e morre igual em dia movimentado
  (armadilha 245). A vacina cura o sintoma quando o repositório está calmo.
- Um run que falha numa célula cancela as irmãs pelo `fail-fast` da matriz, e
  o run seguinte não as cobre (armadilha 215). Isso não é cancelamento pela
  fila e a fila sozinha não o resolve.
- Um run verde não prova célula publicada: um push que só toca `painel/` ou
  `fila/` termina `success` sem nenhum job `deploy (<celula>)`, porque
  `celulas_imagem` fica vazio (armadilha 359 e `ci/rerun_de_deploy.py`,
  função `celulas_sem_publicacao`). Todo PR desta casa carrega um registro em
  `painel/`, então esse run verde e vazio é o caso comum, não a exceção.
- A armadilha 183 já nomeava a cura de verdade: "um portão que compare o que
  está na main com o que está no ar, por célula, fecharia a classe inteira".

## 4. O fato novo que muda o desenho

Desde 07/05/2026 o `concurrency` do GitHub Actions aceita a chave `queue`.
Conferido em 20/09/2026 na documentação oficial e no changelog:

- `queue: single` é o padrão e mantém a vaga única;
- `queue: max` guarda até 100 runs pendentes no grupo, atendidos em ordem de
  chegada; a documentação avisa que "a ordem não é garantida" porque o instante
  real de partida varia;
- com a fila cheia, o run que chega além do centésimo é cancelado;
- `queue: max` junto com `cancel-in-progress: true` é erro de validação do
  workflow.

O cabeçalho de `deploy-infra.yml` (TAR-029, 30/08/2026) mediu que separar os
grupos é errado porque os dois scripts escrevem no mesmo `docker-compose.yml`
da VPS, e concluiu que "o caminho é fundir as duas esteiras". A medição sobre
os scripts continua certa. A conclusão sobre o caminho deixou de valer: a
fila nativa dá o enfileiramento sem fundir nada e sem separar nada.

## 5. Resultado visto da cadeira do mantenedor

Antes: merge pousa, checks verdes, e o comportamento novo não aparece no site.
Ninguém avisa. A descoberta vem pelo sintoma errado, dias depois.

Depois do degrau A: todo deploy de push espera a vez e publica a célula dele.
O histórico do `deploy-celula` deixa de ter linhas cinza por disputa de vaga.
Um rerun ou um rollback manual entram na fila e rodam, em vez de serem
expulsos em 31 segundos como o rerun medido na armadilha 359.

Depois do degrau B: cada célula é publicada quando a main tem algo novo para
ela desde a última vez em que ela subiu, não quando o push da vez a tocou.
Um run que falha numa célula deixa de esconder a irmã, um run verde e vazio
deixa de enterrar o que veio antes, e nenhuma célula volta a uma versão mais
velha por cima de uma mais nova. O alcance é de duas semanas de histórico:
dívida mais velha que isso fica com a vacina, e o item 8.1 diz por quê.

Depois do degrau C: o livro tem a medição de sete dias que prova os dois
degraus, e a fila e as armadilhas dizem o que mudou e o que continua valendo.

## 6. Princípios que governam os três degraus

1. Uma mudança de comportamento por PR. O revisor recusa PR que misture
   degraus.
2. Prova vermelho para verde: todo guarda nasce reprovando o estado atual e
   passa só com a mudança. A saída crua das duas execuções vai no corpo do PR.
3. Prova por mutação: cada guarda novo declara `# guarda:` e passa por
   `python ci/provar_guardas.py <teste>`; o JSON da prova é evidência do PR.
4. Fail-closed onde publicar errado custa caro, degradação declarada onde
   deixar de publicar custa mais: "não medi" nunca vira "pode publicar por
   cima de um rollback", e nunca vira "não há nada a publicar" em silêncio.
   Onde a medição falhar, a tabela de estados diz o que acontece e o resumo do
   run diz que aconteceu.
5. Reversão em um gesto: cada degrau lista o revert exato, sem estado
   persistente para limpar.
6. Medição no ar antes do degrau seguinte, com comando, recorte de data e
   número esperado.
7. Lista derivada, nunca colada: guardas que percorrem workflows leem a pasta
   `.github/workflows/`; guardas que falam de células leem `celulas.yml`.
8. Sem travessão no texto que `python ci/travessao.py --listar` mede. O
   texto novo deste plano em comentários de YAML e em mensagens de issue segue
   o estilo do arquivo em que entra, e não reescreve o que já está lá.

## 7. Degrau A: a fila nativa no grupo `deploy`

É a Fase 3 do programa, antecipada. O programa a coloca depois das fases de
imagem imutável para que a ordem da fila nunca seja risco (invariante
DEP-03). O mantenedor decidiu em 20/09/2026 abrir este degrau primeiro, com a
janela do item 7.9 declarada e medida, porque a expulsão da vaga acontece
hoje, todo dia, e a reordenação só dói em duas chegadas quase simultâneas na
mesma célula. O degrau B fecha essa janela por desenho, dias depois, não
semanas.

### 7.1 Mudança

Acrescentar `queue: max` ao bloco `concurrency` de três workflows, mantendo
`cancel-in-progress: false`:

```yaml
concurrency:
  group: deploy
  cancel-in-progress: false
  queue: max
```

Alvos: `.github/workflows/deploy-celula.yml` (linhas 55 a 57 hoje),
`.github/workflows/deploy-infra.yml` (106 a 108), `.github/workflows/rollback.yml`
(71 a 73).

### 7.2 Texto que a mudança desatualiza e que sai no mesmo PR

- cabeçalho do `concurrency` de `deploy-celula.yml` e de `deploy-infra.yml`:
  o preço da vaga única deixa de existir e a frase "o caminho é fundir as
  duas esteiras" sai; a medição sobre os scripts da VPS fica;
- cabeçalho e texto da issue de `vacina-do-deploy.yml`: o `cancelled` de push
  passa a ter duas causas possíveis, fila cheia com mais de 100 pendentes ou
  cancelamento manual, e a issue deve dizer isso em vez de apontar a disputa
  de vaga. Os testes `test_a_issue_DIZ_qual_das_duas_doencas_foi` e vizinhos
  em `ci/tests/test_vacina_do_deploy_automatica.py` continuam valendo e
  precisam continuar verdes;
- `ci/rerun_de_deploy.py`, ramo `_decidir_o_cancelado`: as mensagens dizem
  hoje que a cura do cancelamento é "dar grupo de concorrência próprio" e que
  "a vaga de pendente está sendo tomada a cada volta". Depois da fila, a causa
  de um `cancelled` é fila cheia ou cancelamento manual, e o texto tem de
  dizer isso. Os testes de `ci/tests/test_rerun_de_deploy.py` que afirmam a
  frase acompanham a mudança; a decisão (repetir, parar, nada) não muda;
- todo workflow cujo `concurrency.group` não é `deploy` fica como está: os
  grupos próprios seguem em `queue: single` e os comentários deles continuam
  corretos.

### 7.3 Guarda

Arquivo novo `ci/tests/test_fila_do_deploy.py`, com a lista derivada da pasta
`.github/workflows/`:

- todo workflow cujo `concurrency.group` é `deploy` declara `queue: max` e
  `cancel-in-progress: false`; o conjunto encontrado tem no mínimo três
  membros, para o teste não passar vazio;
- nenhum workflow da pasta combina `queue: max` com
  `cancel-in-progress: true`.

Vermelho para verde: o teste reprova no YAML atual e passa depois da linha.
Mutação: remover `queue: max` de um só dos três arquivos reprova. É o teste
estrutural que a Fase 3 do programa também exige.

### 7.4 Lição nova

Uma armadilha nova, número por `python ci/reservar.py numero armadilha`, com
o frontmatter completo que `ci/indice_de_armadilhas.py` exige:
`schema_version: 2`, `estado: guardada`, `degrau: 2`, `confianca: alta`,
`custo_por_queda: alto`, `guarda: {tipo: teste, dono:
ci/tests/test_fila_do_deploy.py}`, `sinal` com a frase `terminou 'cancelled'
sem job nenhum`, `gatilho` com os três caminhos literais
(`.github/workflows/deploy-celula.yml`, `.github/workflows/deploy-infra.yml`,
`.github/workflows/rollback.yml`; um gatilho largo avisaria nos 21 workflows
e é o que a régua do índice proíbe) e `licao` de até 400 caracteres: grupo
de concorrência compartilhado por deploys usa `queue: max`; sem a chave, a
vaga de espera é única e o pendente anterior é cancelado.

A entrada organiza a história em três grupos: 173, 188 e 245 descrevem a
expulsão da vaga única, que este degrau encerra; 383 continua valendo, porque
um run cancelado por fila cheia ou à mão segue morrendo sem job nenhum; 183,
215 e 359 descrevem a decisão pelo diff do push, que só o degrau B encerra.
Registra a categoria da retrospectiva: afirmar inviabilidade sem reler a
configuração. O índice é regenerado por `python ci/indice_de_armadilhas.py`;
os quatro artefatos gerados (`INDICE.md`, `GATILHOS.json`, `GUARDAS.json`,
`SINAIS.json`) são ignorados pelo git e não entram no PR.

### 7.5 Orçamento e mandato

Arquivos fora de `painel/` e `fila/`: três workflows, `vacina-do-deploy.yml`,
`ci/rerun_de_deploy.py`, `ci/tests/test_rerun_de_deploy.py`, o teste novo e
a armadilha nova. Oito.
Caminhos CODEOWNERS: `.github/` e `ci/`. `armadilhas/` não é CODEOWNERS.
Célula da CI: `ci`. Modelo e esforço:

```bash
python ci/economia_da_fabrica.py brief --tipo teste --objetivo "queue max no grupo deploy, teste de forma dos tres workflows e armadilha nova" --alvo .github/workflows/deploy-celula.yml
```

Resposta em 20/09/2026: `sonnet`, `medium`.

### 7.6 Prova no PR

1. Saída de `python -m pytest ci/tests/test_fila_do_deploy.py` antes e depois
   da linha, colada crua.
2. JSON de `python ci/provar_guardas.py ci/tests/test_fila_do_deploy.py`.
3. `python -m pytest ci/tests/test_vacina_do_deploy_automatica.py
   ci/tests/test_rerun_de_deploy.py ci/tests/test_rollback.py
   ci/tests/test_portao_de_deploy.py ci/tests/test_workflows_com_ssh_tem_portao.py`
   verde.
4. `python ci/travessao.py --listar` sem ocorrência nos arquivos tocados.

### 7.7 Prova no ar, 48 horas depois do merge

`DESDE` é o instante do merge do degrau A em ISO 8601 UTC, lido de
`gh pr view <N> --json mergedAt`. Os comandos que comparam instantes usam
`--status completed`, porque um run ainda na fila tem `startedAt` vazio e
apareceria como "começou antes de todos".

Cancelados desde o merge, esperado `0` (a linha de base é 5 em 400 runs):

```bash
gh run list --workflow deploy-celula.yml --branch main --created ">=$DESDE" --limit 300 --json conclusion --jq '[.[] | select(.conclusion=="cancelled")] | length'
```

Pares em que o segundo run foi criado antes de o primeiro terminar e ambos
terminaram `success`, esperado maior que zero num período com lote; é a prova
de que a fila segurou em vez de cancelar:

```bash
gh run list --workflow deploy-celula.yml --branch main --status completed --created ">=$DESDE" --limit 300 --json createdAt,updatedAt,conclusion --jq 'sort_by(.createdAt) | [range(1; length) as $i | select(.[$i].createdAt < .[$i-1].updatedAt and .[$i].conclusion=="success" and .[$i-1].conclusion=="success")] | length'
```

Pares consecutivos que começaram fora da ordem de criação, esperado `0`;
cada um é uma reordenação da fila:

```bash
gh run list --workflow deploy-celula.yml --branch main --status completed --created ">=$DESDE" --limit 300 --json createdAt,startedAt,headSha,databaseId --jq 'sort_by(.createdAt) | [range(1; length) as $i | select(.[$i].startedAt < .[$i-1].startedAt) | {antes: .[$i-1].databaseId, depois: .[$i].databaseId, sha_antes: .[$i-1].headSha, sha_depois: .[$i].headSha}]'
```

Se a lista de reordenações não vier vazia: para cada par, comparar as células
dos dois pushes com `ci/rerun_de_deploy.py::celulas_do_push`; se alguma célula
aparece nos dois, republicar o run de SHA mais novo com `gh run rerun <id>`
e conferir o veredito com `python ci/esperar.py --run <id>`. A vacina não
serve aqui: `ci/rerun_de_deploy.py` devolve `nada` para run verde, e os dois
runs do par são verdes. Registrar o caso no livro como incidente. Sem célula
em comum, não há o que consertar.

Registro `medicao` no livro com os três números e `verificado_em`.

### 7.8 Reversão

`git revert` do commit de merge do degrau A: tira a linha dos três workflows,
o teste e a armadilha juntos. Tirar só a linha deixaria o teste vermelho, e
`muralhas` roda `ci/tests/` como check obrigatório: o PR de reversão não
pousaria. Não há estado a limpar.

### 7.9 Riscos deste degrau

- Latência: numa rajada de dez merges em dez minutos o último espera perto de
  trinta minutos. Run pendente não consome minuto de runner.
- Janela nova, medida e com fecho marcado: hoje o run mais velho é cancelado;
  com a fila ele roda. Se dois pushes entram no grupo quase juntos e o GitHub
  os inverte, um SHA mais velho pode publicar `:main` de uma célula depois de
  um mais novo, com tudo verde e sem acordar a vacina, que só acorda em
  `cancelled` e `failure`. Só dói quando os dois pushes tocam a mesma célula.
  Entre A e B, o invariante DEP-03 do programa fica coberto por medição e
  remédio (item 7.7), não por mecanismo. Foi essa a troca que o mantenedor
  aceitou em 20/09/2026; se preferir a ordem do programa, a TAR-529 é
  cancelada antes de ser pega, sem custo. O degrau B fecha a janela por
  desenho, recusando publicar célula cuja última publicação não é ancestral
  do run.
- Rollback manual espera a vez atrás dos deploys enfileirados. Antes ele
  esperava e ainda podia ser expulso; agora só espera. O pouso já recusa
  merges da célula congelada (`ci/mergear.py::checar_congelamento`). A
  prioridade de rollback é a Fase 4 do programa e vem depois.
- Fila cheia com mais de 100 pendentes cancela o que chega depois. A vacina
  continua acordando no `cancelled` e a issue dela passa a dizer isso.

## 8. Degrau B: cada célula publica o que a main deve a ela

É a metade da Fase 5 do programa que cabe dentro do `deploy-celula`: a
comparação entre o que a main deve e o que já subiu, feita por célula, a cada
push, sem workflow novo, sem SSH e sem disparo manual. O que a Fase 5 pede
além disto (leitura dos containers, agenda de 15 minutos, convergência
solicitada) depende das duas lacunas do item 0 e fica no programa.

### 8.1 Mudança

O job `detectar` do `deploy-celula.yml` deixa de derivar tudo de
`github.event.before` e passa a decidir célula por célula, com a lógica em
um arquivo novo `ci/base_do_deploy.py`. O YAML só faz a fiação, na doutrina de
`PROJETO-PORTAO-DEPLOY.md`.

**A busca das publicações, e por que ela é barata.** Os runs do
`deploy-celula` na main são lidos do mais novo ao mais velho por
`gh api --paginate` em `/actions/workflows/deploy-celula.yml/runs?branch=main&per_page=100`,
com teto de 10 páginas: 1000 runs, perto de duas semanas no ritmo medido. Para
cada run, `celulas_do_push(headSha)` diz, só com o git local (o checkout tem
`fetch-depth: 0`), quais células o push dele tocou. Só para runs que tocaram
uma célula ainda sem resposta é que se pedem os jobs (`jobs_do_run`), e a
busca daquela célula para no primeiro `deploy (<celula>)` com
`conclusion: success`. Um run que não tocou a célula não pode tê-la
publicado, então não custa chamada. Célula que nenhum run da janela tocou
está em dia dentro do que a janela enxerga, sem nenhuma chamada. É a lição da
armadilha 459: busca histórica sem teto e sem filtro percorre todas as
páginas e vira timeout; aqui o teto são 10 páginas e o filtro é o diff.
Dívida mais velha que a janela é invisível a este degrau e continua com a
vacina; o limite fica declarado no resumo do run.

Para cada célula com imagem em `celulas.yml`:

1. se algum run da janela tocou a célula e nenhum run desde então a publicou,
   a célula é devida e entra na matriz;
2. se a última publicação existe e é ancestral do SHA do run (`e_ancestral`
   devolve `True`), a célula entra quando
   `git diff --name-only <publicacao>...HEAD` toca um caminho dela, decidido
   por `ci/mapa_de_celulas.py::celulas_do_diff` sobre `celulas.yml`; se não
   toca, está em dia;
3. se a última publicação não é ancestral (`False`), uma versão mais nova da
   célula já está no ar: a célula não entra, e o resumo do run nomeia o SHA
   que está no ar. É isto que fecha a janela do item 7.9;
4. se `e_ancestral` devolve `None`, a célula segue a regra de hoje, o diff
   contra `github.event.before`, com a linha `base(<celula>)=event.before` no
   resumo; se `event.before` também estiver inutilizável (vazio ou zeros), o
   job termina em ERROR, como hoje. Não medi não é permissão para publicar
   por cima, mas também não é motivo para deixar de publicar o que o push da
   vez tocou;
5. célula com congelamento vivo não entra na matriz, e o resumo a nomeia.
   Congelamentos são lidos como o pouso lê, `ci/mergear.py::
   congelamentos_no_servidor`, e decididos por
   `ci/rollback.py::congelamentos_vivos`. Quando o congelamento expira, a
   célula volta sozinha na próxima passagem: a última publicação dela ficou
   velha e o diff desde então a toca. Republicar `:main` por cima de um
   rollback ativo é a armadilha 051 por outra porta;
6. se a leitura dos congelamentos falhar, o job termina em ERROR e nada é
   publicado: não saber não é "não há". É a mesma decisão de
   `checar_congelamento` no pouso;
7. se o Actions não responder à busca das publicações, todas as células seguem
   a regra de hoje com `base=event.before (o Actions não respondeu)` no
   resumo. Cair para o comportamento de hoje nunca é pior do que hoje.

As outras saídas do `detectar` seguem a mesma decisão:

- `celulas_imagem` e `n_imagem`: as células decididas acima. A regra de hoje
  para a `admin`, que não reconstrói imagem quando o diff dela toca só
  `painel/` ou `fila/`, continua valendo, aplicada ao diff da própria `admin`
  desde a última publicação dela. As strings `SOMENTE_DADOS_ADMIN=true` e
  `JSON_IMAGEM='[]'` que `ci/tests/test_painel_vivo_no_deploy.py` procura no
  YAML mudam de lugar com a lógica, e esse teste é atualizado no mesmo PR para
  afirmar a regra onde ela passa a morar;
- `painel_dados` e `fila_dados`: o diff é medido contra o `headSha` do run
  mais recente com o job `publicar-dados-admin` em `success`, procurado com o
  mesmo filtro (só runs cujo push tocou `painel/` ou `fila/`) e o mesmo teto;
  publicação de dados mais nova que o run significa dados em dia; sem
  publicação na janela e com toque na janela, dados devidos; `None` segue
  `event.before`; `admin` congelada não publica dados, porque o quadro novo
  seria lido por uma imagem voltada no tempo;
- `celulas` e `n`: a união do que acima pede imagem ou dados, na ordem de
  `ci/ordem_de_publicacao.py`, como hoje.

O job `detectar` ganha `permissions: {contents: read, actions: read}` e um
bloco `env` com `GH_TOKEN: ${{ github.token }}`, como o job `portao` já tem,
porque hoje ele não tem token nenhum e `gh api` falharia em todo run. O
portão de deploy não muda: continua provando os checks do SHA do run, e a
imagem continua sendo construída do checkout desse SHA.

**A vacina passa a fazer a mesma pergunta.** Para o `deploy-celula`,
`_a_republicacao_avanca` deixa de comparar o SHA doente com
`sha_do_ultimo_deploy_verde` (que fica para o `deploy-infra`, onde a pergunta
é de run mesmo) e pergunta por célula do push doente, com a mesma função de
`ci/base_do_deploy.py`: célula devida, ou cuja última publicação é ancestral
do SHA doente, pede repetição; célula cuja última publicação já contém o SHA
doente está coberta. Alguma devida: `repetir`, e o rerun decide por célula,
sem republicar as cobertas. Nenhuma devida: `nada`. Leitura das publicações
falhou: ERROR, porque não medi não vira permissão para repetir. O campo
`Fatos.sha_publicado`, que alimenta as mensagens, recebe a publicação da
célula que motivou a decisão. O desfecho `parar` por divergência deixa de
existir para o `deploy-celula`: a main é linear e o rerun não publica célula
ultrapassada. Sem esta parte, um run que terminou verde sem publicar nada
(ultrapassado, congelado ou em dia) passaria a ser "o publicado" para a
vacina.

O `deploy-infra` não entra neste degrau: a sincronização dele é do compose
inteiro, sem matriz por célula, e um run vermelho dele é curado pela vacina,
que com o degrau A deixa de ser expulsa.

### 8.2 Tabela de estados que o teste cobre

Decisão do `detectar`, por célula com imagem:

| Publicação na janela | Ancestral do run? | Diff desde ela toca a célula? | Congelada? | Resultado |
|---|---|---|---|---|
| encontrada | sim | sim | não | publica |
| encontrada | sim | não | não | em dia |
| encontrada | não | qualquer | não | ultrapassada: não publica; resumo nomeia o SHA no ar |
| encontrada | não medi (`None`) | usa `event.before` | não | publica pelo diff do push; resumo avisa |
| encontrada | não medi (`None`) e `event.before` inutilizável | não se aplica | não | ERROR, como hoje |
| ausente, e algum run da janela tocou a célula | não se aplica | não se aplica | não | devida: publica; resumo diz desde qual run |
| ausente, e nenhum run da janela tocou a célula | não se aplica | não se aplica | não | em dia dentro da janela; resumo declara o limite |
| qualquer | qualquer | qualquer | sim | não publica; resumo nomeia a célula e o prazo do congelamento |
| `admin`, encontrada | sim | só `painel/` ou `fila/` | não | dados sim, imagem não |
| Actions sem resposta | não se aplica | usa `event.before` para todas | lida | publica pelo diff do push; resumo avisa |
| qualquer | qualquer | qualquer | leitura falhou | ERROR: nada publicado |
| `event.before` inutilizável e Actions sem resposta | não se aplica | não se aplica | qualquer | ERROR, como hoje |
| todas em dia, ultrapassadas ou congeladas | | | | run verde sem job `deploy (<celula>)`; resumo lista o motivo de cada uma |

Decisão do `detectar` para `painel_dados` e `fila_dados`:

| Última `publicar-dados-admin` verde | Situação | Resultado |
|---|---|---|
| encontrada e ancestral | diff desde ela toca `painel/` ou `fila/` | publica dados |
| encontrada e ancestral | diff não toca | dados em dia |
| encontrada, não ancestral | qualquer | dados em dia: publicação mais nova já está no ar |
| encontrada, `None` | usa `event.before` | publica pelo diff do push; resumo avisa |
| ausente, e algum run da janela tocou `painel/` ou `fila/` | qualquer | dados devidos: publica |
| qualquer | `admin` congelada | não publica dados; resumo explica |

Decisão da vacina para um run doente do `deploy-celula`:

| Células do push doente | Resultado |
|---|---|
| alguma devida ou com última publicação ancestral do SHA doente | `repetir`; o rerun decide por célula |
| todas com última publicação que contém o SHA doente | `nada` |
| leitura das publicações falhou | ERROR: não medi não vira repetição |

O teste fabrica o histórico do Actions substituindo `_rodar` e
`jobs_do_run`, como `ci/tests/test_rerun_de_deploy.py` já faz, e fabrica o
congelamento derivando a referência de `rollback.NS_CONGELAMENTO`, como
`ci/tests/test_rollback_congela_a_celula.py` faz. Cada linha das três tabelas
tem uma função de teste com o nome do estado.

### 8.3 Orçamento e mandato

Arquivos fora de `painel/` e `fila/`: `deploy-celula.yml`,
`ci/base_do_deploy.py`, `ci/tests/test_base_do_deploy.py`,
`ci/rerun_de_deploy.py`, `ci/tests/test_rerun_de_deploy.py`,
`ci/tests/test_painel_vivo_no_deploy.py`, `ci/tests/test_portao_de_deploy.py`
se a forma do YAML afirmada lá mudar, e uma armadilha nova se o despacho medir
lição própria. Até oito.
Caminhos CODEOWNERS: `.github/` e `ci/`. Célula da CI: `ci`. Modelo e
esforço:

```bash
python ci/economia_da_fabrica.py brief --tipo arquitetura --objetivo "deploy-celula decide por celula desde a ultima publicacao dela, recusa SHA ultrapassado e respeita congelamentos" --alvo .github/workflows/deploy-celula.yml
```

Resposta em 20/09/2026: `opus`, `high`.

### 8.4 Prova no PR

1. `python -m pytest ci/tests/test_base_do_deploy.py` reprovando antes do
   arquivo novo e verde depois, com as três tabelas do item 8.2 inteiras
   cobertas, uma função de teste por linha.
2. JSON de `python ci/provar_guardas.py ci/tests/test_base_do_deploy.py`.
3. `python -m pytest ci/tests/test_rerun_de_deploy.py
   ci/tests/test_portao_de_deploy.py ci/tests/test_painel_vivo_no_deploy.py
   ci/tests/test_ordem_de_publicacao.py ci/tests/test_fila_do_deploy.py`
   verde.
4. O teste do YAML afirma que o `detectar` chama `ci/base_do_deploy.py`, tem
   `GH_TOKEN` e `actions: read`, e que o job `deploy` mantém as quatro
   condições que `test_workflow_de_deploy_exige_o_portao` já cobra.
5. O log do job `detectar` imprime uma linha por célula:
   `base(<celula>)=<sha ou event.before> estado=<publica|em dia|ultrapassada|devida|congelada>`,
   e uma linha com o alcance da busca: páginas lidas e SHA mais velho visto.

### 8.5 Prova no ar, sete dias depois do merge

`DESDE` é o `mergedAt` do PR do degrau B.

1. Em todo run desde o merge, o log do `detectar` mostra as linhas por célula;
   o número de células decididas por `event.before` é reportado e precisa ser
   zero ou explicado célula a célula.
2. Para o primeiro run `failure` que ocorrer, o run verde seguinte tem na
   matriz todas as células que o run falhado ia publicar, e
   `celulas_sem_publicacao(<sha falhado>, celulas_do_push(<sha falhado>))`
   devolve vazio depois dele.
3. Nenhum run desde o merge tem job `deploy (<celula>)` verde para célula que
   o log do próprio `detectar` marcou como `estado=congelada`. A referência
   `refs/congelamentos/<celula>` é apagada no descongelamento, então a
   conferência é pelo log gravado no run, não pelo servidor.
4. Custo: a duração do job `detectar` antes e depois do merge, esperada
   abaixo de dois minutos no pior caso, e o número de páginas lidas por run.

Registro `medicao` no livro com os quatro resultados.

### 8.6 Reversão

`git revert` do commit de merge do degrau B: volta `BASE='${{ github.event.before }}'`
no `detectar`, tira `ci/base_do_deploy.py`, o teste e a mudança da vacina
juntos. Sem estado a limpar.

### 8.7 Riscos deste degrau

- Republicação restaura o contêiner: cada célula publicada passa pelo
  caminho normal, `docker compose pull`, dump da base e
  `docker compose up -d --wait` com migração no boot. Com a decisão por
  célula, uma célula só entra quando a main tem algo novo para ela desde a
  última vez em que ela subiu, então não há republicação redundante por
  desenho; a única a mais é a célula que o run vermelho anterior não
  conseguiu subir, que é exatamente a que faltava.
- Dependência do Actions para achar as publicações: até 10 páginas de runs e
  uma consulta de jobs por run que tocou célula ainda sem resposta; coberta
  pela queda para `event.before` com aviso.
- Alcance de duas semanas: dívida mais velha que a janela não é vista por este
  degrau. Fica declarada no resumo de todo run e continua sendo caso da vacina
  no `failure` que a originou.
- O `deploy-infra` segue com `docker compose up -d` sem argumento, que devolve
  células congeladas ao `:main` (armadilha 051). É a Fase 2 do programa,
  item 6 dela, e vem depois deste degrau.

## 9. Degrau C: o fecho

Um PR pequeno, depois da medição de sete dias do degrau B:

- registro `medicao` consolidando os números dos itens 7.7 e 8.5;
- nota em `PLANO-MESTRE-ROBOS-SEM-COLISAO.md`, item P5 e divergência 1, dizendo
  que a afirmação "concurrency não é fila" valia até a chave `queue`; a
  conclusão de não usar `concurrency` como fila de merge continua certa por
  outro motivo, a ordem não garantida;
- linha em `painel/ia/05-infraestrutura-ci-e-deploy.md` descrevendo a fila e a
  decisão por célula;
- decisão sobre `TAR-228`: a TAR-210 entregou a cobertura por célula na
  vacina; confirmar com `python ci/fila.py listar --ao-vivo` e cancelar com
  motivo, ou executar o que faltar.

Caminhos CODEOWNERS: `docs/decisoes/`. Célula: `admin`. Modelo `sonnet`,
esforço `medium`, pelo mesmo comando de brief com `--tipo escrita`.

## 10. Auditoria: quem confere o quê, e quando

### 10.1 Antes do pouso, em cada PR

O revisor (ficha `.claude/agents/revisor.md`, chamado com `model: opus`
declarado na chamada) lê o diff com esta lista e reprova ao primeiro item
falho:

1. o PR toca um degrau só;
2. cada guarda novo tem saída vermelha e verde coladas cruas no corpo;
3. o JSON de `provar_guardas` está no corpo e tem `FAIL` na chamada do teste
   sabotado;
4. nenhum `always()` novo, nenhum `|| true`, nenhum `continue-on-error` novo,
   nenhum `cancel-in-progress: true` em grupo com `queue: max`;
5. nenhuma lista colada de workflows ou células onde a pasta ou o
   `celulas.yml` respondem;
6. texto no escopo de `travessao.py` sem travessão;
7. a linha `Mandato-do-mantenedor:` está em coluna zero no corpo, cita os
   caminhos exatos e a origem, e o autor do PR é o mantenedor;
8. o registro do livro embarcado cita o PR e não jura integração nem
   publicação;
9. nenhuma armadilha existente foi editada;
10. o orçamento de arquivos fecha na conta do papel;
11. cada linha das tabelas de estados do degrau tem uma função de teste com o
    nome do estado.

### 10.2 No pouso

`muralhas` e `ci-celula-gate` verdes no SHA final; base atualizada e medida de
novo se envelheceu. Nenhum gesto manual.

### 10.3 Depois do merge

A sentinela verifica, com comando e saída no registro:

1. `gh run view <run do deploy do PR> --json status,conclusion`: `success`;
2. `gh api repos/abundanciabr/sitesdoreino/contents/.github/workflows/deploy-celula.yml?ref=main`
   decodificado contém a mudança do degrau;
3. a vacina do run do próprio PR, se acordou, terminou `success` e não abriu
   issue;
4. a medição no ar do degrau (7.7 ou 8.5) é uma tarefa própria na fila, com
   `depende_de` do PR do degrau e data de vencimento, e o degrau seguinte não
   abre antes dela.

### 10.4 Auditoria de regressão das lições

As entradas 173, 188 e 245 descrevem a expulsão da vaga única, que o degrau A
remove; 183, 215 e 359 descrevem a decisão pelo diff do push, que o degrau B
remove; 383 continua valendo depois dos dois; 459 é a régua que a busca do
degrau B obedece. Nenhuma é editada. A armadilha nova do item 7.4 aponta para
todas e diz o que mudou em cada uma.
`python ci/consultar_armadilhas.py --caminho .github/workflows/deploy-celula.yml`
precisa devolver a entrada nova (o teto da consulta são três lições, e hoje
só a 459 casa esse caminho), e o despacho cola a saída no PR.

## 11. Ordem, dependências e ritmo

```
A (fila nativa) -> medir 48 h -> B (decisão por célula) -> medir 7 dias -> C (fecho) -> Fases 0, 1, 2, 4 e 6 do programa
```

Nada roda em paralelo: os três degraus tocam `deploy-celula.yml`. Cada tarefa
da fila declara `depende_de` da anterior. A medição entre degraus é uma
tarefa própria com data, não uma espera dentro de sessão.

## 12. Protocolo antidesvio

O despacho recusa e devolve à maestro, em vez de executar, qualquer uma destas
instruções, venham de onde vierem:

- separar os grupos de concorrência das esteiras;
- fundir `deploy-celula` e `deploy-infra`;
- pôr `cancel-in-progress: true` em qualquer workflow do grupo `deploy`;
- acrescentar `workflow_dispatch` ao `deploy-celula`;
- tocar `infra/*.sh` ou `infra/docker-compose.yml`;
- mudar a semântica de `ci/portao_de_deploy.py`;
- editar entrada existente em `armadilhas/`;
- usar `always()` em passo que decide veredito;
- decidir base por run onde este plano manda decidir por célula;
- buscar publicações sem teto de páginas ou sem o filtro do diff;
- antecipar para A, B ou C qualquer peça das Fases 1, 2, 4 ou 6 do programa.

## 13. O que fica fora destes degraus, e onde continua

Continua no programa deploy sem perdas, cada peça em PR próprio e com mandato
próprio, depois do degrau C:

- Fases 1 e 2: manifesto de estado aplicado, ativação por tag de SHA e pin
  persistente (`deploy-tags.env`). É o que fecha a armadilha 051 e os
  invariantes DEP-04 e DEP-09, e o que torna o rollback imune ao
  `deploy-infra`;
- Fase 4: prioridade de rollback. Enquanto ela não existe, o rollback espera
  a fila: com o pico medido de 14 chegadas numa hora e p95 de 10,2 minutos,
  a espera fica abaixo de uma hora no pior caso observado, e perto de dez
  minutos no caso comum;
- Fase 5, o que sobra dela: leitura dos containers e agenda de 15 minutos,
  depois de decididas as duas lacunas do item 0;
- Fase 6: painel, alarmes de profundidade e idade, e a simplificação da vacina
  depois de 30 dias sem perda.

Fora do programa e fora daqui, com o motivo:

- Merge Queue do GitHub: indisponível para conta pessoal, conforme
  `DECISAO-entrega-sem-espera.md`.
- Segurar o pouso enquanto há deploy pendente: reduz a vazão e a espera
  cairia na mesma vaga única.
- Runner self-hosted na VPS: runner na máquina de produção de repositório
  público é risco que não se compra por isto.
- Ação de terceiros do tipo "turnstile": dependência de supply chain no
  caminho do deploy para fazer o que `queue: max` faz nativo.
- Perguntar ao registro de imagens qual SHA a tag `:main` aponta: a tag é
  empurrada antes da ativação na VPS, então ela mente quando o SSH falha
  depois do push, que é o caso da armadilha 127.

As alternativas que o programa já recusou (item 7 dele: só a fila, separar
esteiras, só a vacina, coordenador externo, cancelar antigos) não são
repetidas aqui.

## 14. Decisões do mantenedor

1. Este documento: mandato para `docs/decisoes/PLANO-MESTRE-FILA-DE-DEPLOY.md`
   dado na sessão de 20/09/2026.
2. Degrau A: mandato dado na sessão de 20/09/2026 para
   `.github/workflows/deploy-celula.yml`, `.github/workflows/deploy-infra.yml`,
   `.github/workflows/rollback.yml`, `.github/workflows/vacina-do-deploy.yml`,
   `ci/rerun_de_deploy.py`, `ci/tests/test_rerun_de_deploy.py` e
   `ci/tests/test_fila_do_deploy.py`. A tarefa é a TAR-529, que viaja neste
   PR com o brief inteiro no campo `despacho` e entra na fila quando ele
   pousar.
3. Ordem em relação ao programa: a fila (Fase 3) entra antes das Fases 0, 1 e
   2, com a janela do item 7.9 declarada. Decidido em 20/09/2026 ao autorizar
   a TAR-529. Para voltar à ordem do programa, cancelar a TAR-529 antes de ela
   ser pega; nada mais precisa ser desfeito.
4. Degrau B: mandato a pedir quando a medição de 48 horas do degrau A estiver
   no livro, para `.github/workflows/deploy-celula.yml`, `ci/base_do_deploy.py`,
   `ci/tests/test_base_do_deploy.py`, `ci/rerun_de_deploy.py`,
   `ci/tests/test_rerun_de_deploy.py`, `ci/tests/test_painel_vivo_no_deploy.py`
   e `ci/tests/test_portao_de_deploy.py`.
5. Degrau C: mandato a pedir para `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.
6. As duas lacunas do item 0 são decisões do dono do programa antes da Fase 5
   dele: de onde vem o digest dos containers sem SSH, e como uma convergência
   entra na fila sem `workflow_dispatch` no `deploy-celula`.

Os mandatos são transcritos no corpo de cada PR com a origem: sessão e data.

## 15. Fontes

- `docs/decisoes/PLANO-MESTRE-DEPLOY-SEM-PERDAS.md`, o programa (TAR-528).
- GitHub Docs, "Control the concurrency of workflows and jobs":
  https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency
- GitHub Docs, "Workflow syntax", seção `concurrency`:
  https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax
- GitHub Changelog, 07/05/2026, "GitHub Actions concurrency groups now allow larger queues":
  https://github.blog/changelog/2026-05-07-github-actions-concurrency-groups-now-allow-larger-queues/
- Neste repositório: `armadilhas/051`, `127`, `173`, `183`, `188`, `215`,
  `245`, `359`, `383`, `459`; `.github/workflows/deploy-celula.yml`,
  `deploy-infra.yml`, `rollback.yml`, `vacina-do-deploy.yml`;
  `ci/rerun_de_deploy.py`; `ci/mergear.py`; `ci/rollback.py`;
  `ci/mapa_de_celulas.py`; `ci/indice_de_armadilhas.py`; `celulas.yml`;
  `docs/decisoes/PROJETO-PORTAO-DEPLOY.md`;
  `docs/decisoes/DECISAO-entrega-sem-espera.md`.
