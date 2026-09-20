publico-para-ia: true

# Plano mestre: deploy sem perdas

Versão: 1.0
Data: 20/09/2026
Autoridade: pedido direto do mantenedor nesta conversa
Estado deste documento: plano fechado; implementação não iniciada
Responsabilidade de execução: célula `ci`, com fatias de `infra`

## 1. A decisão em uma frase

O projeto manterá um único escritor da produção, trocará a vaga única do grupo
`deploy` por `queue: max`, impedirá regressão com versões imutáveis por célula e
fechará qualquer dívida restante com um reconciliador que compara o estado
desejado na `main` com o estado realmente aplicado na VPS.

Adicionar apenas `queue: max` não resolve o problema inteiro. A fila nativa tem
limite de 100 esperas e o GitHub ordena pelo instante em que cada run começou a
esperar, não pelo instante do push. A própria documentação avisa que a ordem não
é garantida. Sem monotonicidade, um run antigo que acorde depois de um novo pode
reescrever a tag mutável `:main` e voltar a célula silenciosamente.

O menor desenho que resolve o problema inteiro tem quatro peças:

1. fila nativa ampla para não perder eventos normais;
2. imagem imutável e estado aplicado por célula para um run antigo não voltar;
3. reconciliador para recuperar perda, limite, falha parcial e desvio manual;
4. auditoria do estado real, com rollback prioritário e fail-closed.

## 2. O que este plano é e o que não é

Este documento é a fonte de arquitetura, sequência, riscos, testes, portões de
aceite e provas para eliminar as armadilhas 173, 183 e 188 sem abrir concorrência
na VPS. Ele também incorpora as lições das armadilhas 215, 245, 359 e 383.

Este documento não altera workflow, script, produção ou configuração do GitHub.
Não cria as tarefas dos lotes e não autoriza os futuros caminhos CODEOWNERS. Cada
fatia de implementação nasce em PR próprio, com mandato nominal, prova local e
prova do GitHub. O pedido desta sessão autoriza somente este plano.

## 3. Resultado visto por quem usa o sistema

Quem publica uma mudança deixa de precisar entender a fila:

1. o PR entra na `main`;
2. o deploy correspondente espera sem expulsar outro;
3. só um escritor modifica a produção por vez;
4. cada célula sobe a imagem exata do SHA aprovado;
5. a esteira prova saúde, imagem, SHA e estado aplicado;
6. se um evento sumir ou uma parte falhar, o reconciliador cria a correção;
7. o painel mostra a dívida até ela chegar a zero.

O estado terminal deixa de ser apenas "um workflow ficou verde". A entrega só é
publicada quando cada recurso tocado tem prova de que o conteúdo esperado está
rodando. Falha de consulta é erro de instrumentação, nunca ausência de dívida.

## 4. Fatos medidos antes do desenho

### 4.1 A escrita é realmente compartilhada

`deploy-celula.yml`, `deploy-infra.yml` e `rollback.yml` usam o mesmo grupo
`deploy`. Isso é correto: todos podem agir sobre o mesmo projeto Compose na VPS.
Separar os grupos sem uma trava comum permitiria intercalar `pull`, troca de
compose, `up -d`, migração e reversão.

### 4.2 A fila atual perde o pendente

Os três workflows usam `cancel-in-progress: false`, mas não declaram `queue`.
Nesse modo o GitHub conserva um run em execução e um pendente. A chegada de um
novo run cancela o pendente anterior. É a causa mecânica das armadilhas 173, 183
e 188.

Fonte oficial consultada em 20/09/2026:
<https://docs.github.com/en/actions/how-tos/write-workflows/choose-when-workflows-run/control-workflow-concurrency>

Na documentação atual, `queue: max` aceita até 100 runs pendentes e não pode ser
combinado com `cancel-in-progress: true`.

### 4.3 Um run posterior não quita a célula anterior

`deploy-celula.yml` calcula a matriz a partir de `github.event.before`. Um run
posterior olha somente o próprio intervalo. Ele pode conter o SHA anterior e
continuar sem executar `deploy (<célula>)` para a célula que ficou para trás.
Ancestralidade de commit não é cobertura de célula, como registra a armadilha
359.

### 4.4 A ativação ainda depende de uma tag mutável

O build cria `:<sha>` e `:main`, mas a execução normal na VPS usa os defaults
`${CELULA_TAG:-main}` do Compose. A tag imutável já existe no registro, porém a
ativação normal ainda escolhe `:main`. Um run antigo pode sobrescrever essa tag
antes de um `pull` posterior.

### 4.5 A vacina é valiosa, mas reativa

`vacina-do-deploy.yml` e `ci/rerun_de_deploy.py` já reconhecem cancelamento,
ancestralidade e cobertura por célula. Essa rede reduziu o dano, mas o rerun
volta à mesma fila disputada. A armadilha 245 mede que uma segunda tentativa
pode ser cancelada de novo em dias movimentados.

### 4.6 Capacidade observada

Retrato obtido às 08:55 BRT de 20/09/2026 com `gh run list`:

| Medida | Resultado |
|---|---:|
| `deploy-celula`, últimos 100 | 88 success, 8 failure, 4 cancelled |
| `deploy-infra`, histórico disponível de 49 | 40 success, 5 failure, 4 cancelled |
| Duração success, p50 | 3,7 min |
| Duração success, p95 | 10,2 min |
| Maior chegada em 10 min | 3 runs |
| Maior chegada em 60 min | 14 runs |
| Runs não terminados no retrato | 0 |

A capacidade de 100 pendentes é 7,1 vezes o maior volume horário observado. Ela
é suficiente para a carga medida, mas não é ilimitada. O plano inclui alarme de
profundidade, idade e cancelamento antes de depender dessa margem.

## 5. Invariantes que nenhuma fatia pode quebrar

| ID | Invariante | Guarda exigida |
|---|---|---|
| DEP-01 | Há no máximo um escritor da produção | mesmo grupo e trava na VPS |
| DEP-02 | Nenhum push elegível desaparece em silêncio | fila ampla e reconciliador |
| DEP-03 | Run antigo nunca substitui estado mais novo | comparação monotônica antes de publicar e ativar |
| DEP-04 | Produção usa imagem imutável | tag SHA ou digest, nunca `:main` como alvo efetivo |
| DEP-05 | Verde exige sentinela e saúde reais | sentinela, `--wait`, smoke e leitura do estado |
| DEP-06 | Cobertura é por recurso | célula, dados admin e infra, não só SHA do run |
| DEP-07 | Estado ilegível para a entrega | JSON inválido, SHA desconhecido ou consulta falha encerram em erro |
| DEP-08 | Rollback vence deploy normal | congelamento antes da espera e fila normal drenada sem tocar o run ativo |
| DEP-09 | Rollback permanece aplicado | pin imutável persiste até descongelamento explícito |
| DEP-10 | Segredos não entram no estado | manifesto contém somente identidade, digest, tempo e prova |
| DEP-11 | Quem entra na VPS não escreve no Git | permissões separadas por job |
| DEP-12 | Toda correção é idempotente | repetir converge para o mesmo SHA e o mesmo digest |

## 6. Arquitetura escolhida

### 6.1 Visão do fluxo

```text
merge na main
    |
    v
detecção de recursos tocados + portão existente
    |
    v
fila global deploy, queue: max, um escritor
    |
    v
comparar desejado x aplicado x congelamento
    |                  |
    | antigo/igual     | avanço válido
    v                  v
ignorar com prova      construir e enviar :<sha>
                       |
                       v
                 ativar SHA exato na VPS
                       |
                       v
                 saúde + smoke + digest
                       |
                       v
                 gravar estado atômico
                       |
                       v
reconciliador compara main, manifesto e containers
    |
    +-- dívida: agenda uma convergência
    +-- sem dívida: publica estado saudável
```

### 6.2 Fila global

Todos os escritores continuam no grupo `deploy`. Os três pontos que usam esse
grupo recebem a mesma política:

```yaml
concurrency:
  group: deploy
  queue: max
  cancel-in-progress: false
```

A igualdade entre os workflows terá teste estrutural. Uma configuração isolada
é reprovada, pois um único produtor no modo `single` pode reintroduzir a troca do
pendente para o grupo inteiro.

### 6.3 Estado aplicado

A VPS mantém um manifesto por recurso em
`/opt/plataforma/deploy-state/<recurso>.json`. Recursos válidos são as células
do `celulas.yml`, `infra`, `painel-dados` e `fila-dados`.

Campos mínimos:

```json
{
  "schema_version": 1,
  "recurso": "pagamentos",
  "sha": "40-hex",
  "fingerprint": "sha256-hex",
  "image_digest": "sha256:hex",
  "run_id": 123,
  "run_attempt": 1,
  "aplicado_em": "UTC ISO-8601"
}
```

O `fingerprint` representa os arquivos que o mapa atribui ao recurso naquele
SHA. Ele permite comparar conteúdo de célula sem confundir uma mudança alheia na
`main` com dívida desta célula.

Regras de escrita:

- validar esquema, recurso, SHA, digest, números e instante antes de usar;
- segurar `flock` por toda mutação do recurso;
- escrever arquivo temporário no mesmo filesystem;
- executar saúde e smoke antes de promover;
- promover com `mv` atômico;
- preservar o manifesto anterior quando qualquer passo falhar;
- modo, dono e grupo iguais aos arquivos operacionais vizinhos;
- nunca guardar token, URL com credencial, ambiente ou saída livre de comando.

### 6.4 Imagem imutável e pin persistente

O build continua produzindo `:<sha>`, mas `:main` deixa de decidir o que roda.
O workflow entrega `CELULA`, `TAG=<sha>` e o digest esperado. A VPS grava o pin
da célula num arquivo não secreto `deploy-tags.env`, troca o pin de forma
atômica e chama o Compose com esse arquivo e o `.env` existente.

Todos os serviços auxiliares cujo nome começa por `<celula>-` recebem a mesma
tag, pois já compartilham a variável da célula no Compose.

O pin anterior só é substituído depois de:

1. a imagem imutável existir no GHCR;
2. o digest local coincidir com o digest esperado;
3. o backup anterior à migração terminar;
4. `docker compose up -d --wait` concluir;
5. os smokes existentes passarem;
6. a sentinela incluir célula, SHA e digest.

Se a ativação falhar após a troca do pin, o script restaura o pin e a imagem
anteriores usando a reversão automática já existente. O manifesto aplicado não
muda. `:main` pode continuar sendo enviado durante a migração por
compatibilidade, mas nenhum caminho de produção pode escolhê-lo ao fim da fase.

### 6.5 Regra monotônica

Antes do build e antes de qualquer alteração em `:main`, o workflow lê o estado
aplicado e classifica o candidato:

| Relação | Decisão |
|---|---|
| mesmo fingerprint e mesmo digest | sucesso idempotente, sem mutação |
| aplicado é ancestral e fingerprint mudou | avançar |
| candidato é ancestral do aplicado | ignorar como antigo, sem build nem push mutável |
| históricos divergiram | parar por segurança |
| estado ausente ou inválido após a gênese | parar por segurança |
| célula congelada | não aplicar; registrar dívida suspensa |
| rollback validado | aplicar alvo antigo e persistir o pin congelado |

O veredito é emitido por código puro e coberto por tabela de testes. Nenhum
`if` de shell reimplementa ancestralidade.

### 6.6 Reconciliação do desejado com o real

O reconciliador é controle, não um segundo escritor. Ele lê:

- topo atual da `main`;
- `celulas.yml` e fingerprints desejados;
- manifestos aplicados;
- digest dos containers em execução;
- jobs e sentinelas dos runs;
- referências `refs/congelamentos/<celula>`.

Ele produz uma decisão fechada por recurso:

| Estado | Ação |
|---|---|
| desejado = aplicado = container | quitar |
| aplicado antigo | solicitar convergência no topo atual da `main` |
| manifesto e container divergem | alarme crítico e convergência |
| recurso congelado | mostrar dívida, não aplicar |
| consulta incompleta | erro de instrumentação |
| run parcial | solicitar apenas os recursos sem prova |
| fila cheia ou run cancelado | manter dívida e solicitar nova convergência |

A solicitação sempre aponta para o topo validado da `main` e para uma lista
explícita de recursos. Ela passa pelo portão normal e entra na mesma fila
global. O reconciliador nunca chama `docker compose` e não recebe chave SSH.

Gatilhos:

- término de `deploy-celula`, `deploy-infra` ou `rollback`;
- agenda de 15 minutos como rede contra evento perdido;
- comando manual de diagnóstico, sem mutação por padrão.

O grupo próprio do reconciliador pode usar cancelamento do run anterior, pois
duas leituras se substituem e nenhuma delas escreve na VPS. A convergência que
ele solicitar entra no grupo `deploy` e não é cancelável.

### 6.7 Rollback prioritário

Uma fila maior não pode transformar emergência em espera atrás de dezenas de
deploys. O fluxo de rollback fica em três partes:

1. validar alvo e congelar a célula antes de entrar na fila de escrita;
2. cancelar somente runs normais ainda `queued` ou `pending`, nunca o escritor
   ativo;
3. aplicar o rollback no mesmo grupo `deploy`, com o pin imutável persistente.

Os runs normais cancelados continuam visíveis como dívida e são refeitos pelo
reconciliador depois do descongelamento. O rollback não usa
`cancel-in-progress: true` e não interrompe migração ou troca de arquivos já em
curso.

O congelamento passa a existir antes da espera. Se a aplicação do rollback não
terminar, a célula continua congelada. A volta a `main` remove o pin antigo
somente depois de saúde e estado aplicado comprovados.

## 7. Alternativas recusadas

### 7.1 Somente `queue: max`

Recusada como solução completa. Resolve a perda normal até 100 pendentes, mas
não garante ordem, não impede regressão por `:main`, não detecta desvio real e
não dá prioridade ao rollback.

### 7.2 Separar `deploy-celula` e `deploy-infra`

Recusada. Ambos escrevem no mesmo Compose e na mesma plataforma. Ganhar
paralelismo aqui compra interleaving de migração, imagem e topologia.

### 7.3 Manter apenas a vacina e os reruns

Recusada. É recuperação reativa dentro da mesma fila que causou a perda. A
armadilha 245 já mede o rerun sendo cancelado repetidamente.

### 7.4 Criar Redis, banco ou serviço externo para a fila

Recusada nesta escala. A fila nativa suporta 100 pendentes contra pico medido de
14 chegadas por hora. Um coordenador externo adicionaria disponibilidade,
segredo, persistência e operação sem remover a necessidade de monotonicidade e
reconciliação.

### 7.5 Cancelar runs antigos e publicar sempre o topo

Recusada como regra principal. Um run do topo pode não ter passado pelo portão
que o run antigo passou, e a seleção por caminhos continuaria sem provar a
cobertura de cada célula.

## 8. Plano de implementação em fatias seguras

Nenhum lote mistura mudança de fila, mudança de formato de estado e remoção de
rede de segurança. Cada linha abaixo é um PR independente e reversível.

### Fase 0. Congelar a régua

**Objetivo:** transformar os invariantes e o retrato atual em testes antes de
mudar produção.

Entregas:

- teste que enumera todos os workflows no grupo `deploy`;
- teste que exige política idêntica entre eles;
- teste que preserva a separação SSH versus `contents: write`;
- consulta que resume fila, idade, cancelamentos e cobertura por recurso;
- atualização das armadilhas somente quando a nova guarda existir.

Aceite:

- a caracterização da política atual fica verde e prova que os três escritores
  ainda usam o modo `single` implícito;
- a guarda da política alvo é exercitada contra fixtures válidas e inválidas,
  sem deixar teste vermelho na branch;
- a consulta reproduz os oito cancelamentos do retrato;
- nenhuma chave SSH ou segredo é necessário para a medição.

Reversão: remover somente os testes e a consulta deste lote. Produção não foi
tocada.

### Fase 1. Contrato de estado e gênese

**Objetivo:** criar o estado aplicado sem mudar como a VPS ativa imagens.

Entregas:

- módulo puro para esquema, fingerprint e decisão monotônica;
- leitor e escritor atômico de manifestos;
- inventário de containers, imagens e digests atuais;
- associação de cada digest em execução a uma tag SHA existente no GHCR;
- comando de gênese que apenas propõe o manifesto e exige correspondência
  única antes de gravar;
- estado inicial de `infra`, `painel-dados` e `fila-dados` a partir das provas
  existentes.

Casos que barram a gênese:

- container sem digest;
- digest com zero ou mais de uma origem incompatível;
- SHA fora da `main`;
- serviço auxiliar em digest diferente do servidor da mesma célula;
- célula declarada sem container ou container sem célula declarada;
- manifesto existente que diverge do inventário.

Aceite:

- duas leituras consecutivas produzem o mesmo inventário;
- cada célula tem SHA, fingerprint e digest provados;
- o comando de escrita usa temporário, `flock` e promoção atômica;
- corrupção intencional do JSON termina em erro e preserva o arquivo anterior.

Reversão: apagar apenas os manifestos recém-criados depois de conferir o alvo
exato. O deploy existente continua escolhendo `:main`.

### Fase 2. Ativação imutável por célula

**Objetivo:** retirar `:main` do caminho que decide a imagem em produção.

Ordem interna:

1. ensinar build e envio a publicar digest e rótulo de revisão;
2. criar `deploy-tags.env` a partir da gênese;
3. fazer deploy e reversão usarem tag SHA persistente;
4. conferir servidor e auxiliares pelo digest real;
5. gravar manifesto somente após sentinela e smoke;
6. fazer infra preservar os pins ao executar `up -d` global;
7. adicionar caminho de preparação de imagem para célula nova antes do compose.

Aceite:

- um deploy válido avança pin, container e manifesto para o mesmo SHA/digest;
- repetir o mesmo run não recria estado nem altera o manifesto;
- executar um candidato antigo imprime `DEPLOY-ANTIGO-IGNORADO` e não faz push
  de `:main`, `pull`, migração ou `up`;
- falha de saúde restaura pin e imagem anteriores e mantém manifesto anterior;
- `deploy-infra` não altera digest de nenhuma célula sem declarar isso;
- rollback persiste no SHA antigo até a volta explícita à linha principal;
- célula nova não usa `:main` como atalho para quebrar a ordem de criação.

Reversão: restaurar os pins do inventário inicial e os scripts anteriores no
mesmo PR de reversão. Os manifestos continuam úteis como prova e não comandam a
produção durante a volta.

### Fase 3. Fila nativa de até 100 pendentes

**Objetivo:** eliminar a cadeira musical depois de a ordem deixar de ser risco.

Entregas:

- `queue: max` em `deploy-celula`, `deploy-infra` e no job escritor do rollback;
- teste estrutural cobrindo todos os membros do grupo;
- alarme de fila e idade;
- comentários e armadilhas corrigidos para não ensinar a limitação antiga como
  comportamento atual.

Aceite no PR:

- o GitHub registra os workflows com a nova sintaxe sem erro de validação;
- `cancel-in-progress: true` inexiste no grupo;
- o grupo continua único;
- a política do rollback está coberta pelo teste.

Aceite em produção:

- primeira rajada natural de três ou mais chegadas conserva todos os pendentes;
- cada run termina com estado por recurso;
- nenhum run antigo regride SHA ou digest;
- qualquer cancelamento conserva dívida visível para o reconciliador.

Reversão: remover `queue: max` dos três consumidores juntos. Nunca reverter um
workflow isolado.

### Fase 4. Rollback prioritário

**Objetivo:** impedir que uma fila longa atrase a resposta à emergência.

Entregas:

- congelamento validado antes da espera;
- cancelamento restrito a deploys normais que ainda não começaram;
- prova de que o run ativo nunca é cancelado;
- pin antigo persistente;
- dívida automática para cada normal cancelado;
- teste de permissões mantendo Git e VPS em jobs diferentes.

Aceite:

- cenário com um run ativo e três pendentes deixa o ativo terminar, remove os
  três pendentes, aplica o rollback em seguida e registra três dívidas;
- chegada posterior da célula congelada não a republica;
- voltar a `main` quita as dívidas e descongela somente depois do smoke;
- falha no cancelamento de um pendente não vira autorização para aplicar em
  paralelo.

Reversão: devolver o rollback à fila comum, mantendo pins imutáveis e
congelamento. A segurança permanece; apenas a prioridade é perdida.

### Fase 5. Reconciliador

**Objetivo:** transformar evento em aviso e estado real em verdade.

Entregas:

- decisão pura desejado versus aplicado versus container;
- gatilho após workflows e a cada 15 minutos;
- convergência explícita das células devedoras no topo aprovado da `main`;
- cobertura de dados admin e infra;
- integração com congelamentos;
- limite contra laço: uma dívida não agenda outra enquanto já houver
  convergência viva para os mesmos recursos;
- falha alta quando histórico, manifesto ou GitHub não puder ser lido.

Aceite:

- run cancelado sem jobs é reconstruído pelo diff, como exige a armadilha 383;
- run parcial solicita somente as células sem sucesso;
- deploy verde de outra célula não quita a dívida, como exige a 359;
- container trocado fora da esteira aparece como desvio;
- três despertares simultâneos criam no máximo uma convergência equivalente;
- recurso congelado permanece devedor sem ser tocado;
- após convergência, uma nova leitura devolve dívida zero.

Reversão: pausar o gatilho do reconciliador. Fila, pins e vacina continuam
operando sem ele.

### Fase 6. Painel, alarmes e simplificação

**Objetivo:** tornar a saúde da entrega visível e retirar somente o que ficou
comprovadamente redundante.

O painel calculado mostra:

- escritor atual;
- profundidade da fila;
- idade do pendente mais antigo;
- recurso, SHA e digest desejados e aplicados;
- dívidas abertas, suspensas e em convergência;
- cancelamentos por motivo;
- último rollback e congelamentos vivos;
- p50 e p95 de espera e execução.

Alarmes iniciais, derivados do retrato:

| Nível | Condição |
|---|---|
| aviso | profundidade maior que 14 ou espera maior que 20,4 min |
| crítico | profundidade igual ou maior que 80, qualquer cancelamento por fila cheia, ou dívida além do SLO |
| erro de instrumento | não foi possível ler fila, estado ou containers |

O limite de idade usa duas vezes o p95 medido. Enquanto ainda não existe uma
série histórica de profundidade, o aviso usa de forma conservadora as 14
chegadas da hora mais carregada como aproximação. O crítico de 80 reserva 20%
da capacidade máxima para reação. Depois de 14 dias, a auditoria substitui a
aproximação pela profundidade observada, recalcula os percentis e registra
qualquer mudança de régua.

A vacina atual permanece durante toda a implantação. Depois de 30 dias com
zero perda e com os testes de falha injetada verdes, ela passa a chamar o
reconciliador e alertar. Código específico de rerun só sai quando nenhum cenário
de aceite depender dele.

## 9. Estratégia de testes

### 9.1 Testes puros, maioria da cobertura

- todas as relações entre SHA aplicado e candidato;
- fingerprint estável e sensível aos caminhos do `celulas.yml`;
- manifesto válido, ausente, corrompido e de versão desconhecida;
- decisão de dívida por célula, infra e dados admin;
- coalescência de despertares;
- congelamento e descongelamento;
- cancelamento seletivo de pendentes;
- mensagens de erro com causa e próxima ação.

Meta: 100% dos ramos de decisão de segurança e todos os estados da tabela de
transição. Cobertura numérica global não substitui esses casos nominados.

### 9.2 Testes de integração sem VPS

Executar os scripts contra diretório temporário, Compose de mentira e comandos
`docker` controlados:

- sucesso escreve pin e manifesto;
- falha antes da ativação não muda nada;
- falha após ativação restaura o anterior;
- dois escritores disputam o mesmo `flock` sem intercalar;
- servidor e auxiliares recebem o mesmo digest;
- infra preserva pins;
- nenhuma saída contém valor de `env/`.

### 9.3 Testes estruturais de workflow

- YAML válido;
- todos os escritores conhecidos no mesmo grupo;
- todos com `queue: max` e sem cancelamento do ativo;
- portão antes de packages e SSH;
- nenhum job reúne chave SSH e `contents: write`;
- dados vindos de evento entram por `env`, não por interpolação em shell;
- toda ação SSH tem checkout, branch principal e sentinela exigida.

### 9.4 Falhas injetadas

O ambiente de teste reproduz:

1. três chegadas com um escritor ocupado;
2. run antigo acordando depois do novo;
3. run cancelado com zero jobs;
4. matriz com uma célula verde e outra falha;
5. imagem ausente no registro;
6. digest diferente do esperado;
7. JSON aplicado truncado;
8. queda entre pin, `up` e manifesto;
9. consulta GitHub indisponível;
10. rollback solicitado com fila cheia;
11. recurso congelado;
12. alteração manual do container.

Cada falha termina em um destes resultados, sem terceiro estado implícito:
convergiu, preservou o anterior, ou parou com dívida e ação explícitas.

### 9.5 Provas reais

Cada fase que muda produção exige:

- comandos locais e saídas no PR;
- checks obrigatórios verdes;
- IDs dos runs de canário;
- SHA e digest antes e depois;
- sentinela da VPS;
- resposta HTTP ou saúde específica da célula;
- leitura independente do manifesto e do container;
- plano de reversão exercitado no ambiente controlado.

## 10. Auditoria rigorosa por portão

| Portão | Pergunta | Evidência mínima | Quem reprova |
|---|---|---|---|
| A0 Escopo | a fatia toca só uma garantia? | diff e limite de arquivos | muralhas |
| A1 Lei | preserva as três costuras e o rollback? | testes canônicos | CI |
| A2 Fila | algum produtor continua em `single`? | enumeração estrutural | teste de workflow |
| A3 Ordem | candidato antigo consegue mutar? | cenário novo antes do antigo | teste monotônico |
| A4 Artefato | o SHA ativado é o aprovado? | tag, digest e rótulo | script de deploy |
| A5 Estado | o manifesto corresponde ao container? | leitura pós-ativação | reconciliador |
| A6 Saúde | processo e jornada respondem? | `--wait` e smoke | workflow |
| A7 Segurança | um job ganhou Git e VPS juntos? | matriz de permissões | teste de segurança |
| A8 Recuperação | falha preserva estado anterior? | teste de injeção e backup | CI |
| A9 Produção | dívida ficou zero após o canário? | painel e comando independente | estado da entrega |
| A10 Reversão | rollback entra e permanece? | run, pin, congelamento e smoke | auditoria pós-deploy |

Um portão sem evidência retorna ERROR. Nenhum portão aceita comentário, plano ou
saída parcial como substituto de mecanismo executado.

## 11. Matriz de riscos

| Risco | Probabilidade | Impacto | Controle | Sinal |
|---|---|---|---|---|
| fila chega a 100 | baixa no retrato | alto | alertar a 80 e reconciliar | cancelamento novo |
| ordem do GitHub muda | média | alto | ativação monotônica | antigo ignorado |
| `:main` volta ao caminho | média | crítico | teste que recusa alvo mutável | pin igual a `main` |
| manifesto mente | baixa | crítico | conferir digest do container | divergência real |
| infra troca imagem de carona | média | alto | pins persistentes e auditoria antes/depois | digest não declarado |
| rollback espera a fila | média | crítico | congelar cedo e drenar pendentes | tempo até aplicar |
| reconciliador cria laço | média | alto | chave de dívida e run vivo único | repetição do mesmo alvo |
| consulta externa falha | média | médio | fail-closed | erro de instrumento |
| script imprime segredo | baixa | crítico | teste de saída e leitura nominal | padrão sensível no log |
| migração irreversível | baixa | crítico | backup antes do `up` e rollback testado | falha de saúde |

## 12. Observabilidade e objetivos operacionais

Objetivos iniciais:

- zero cancelamento causado por substituição de pendente;
- zero regressão de SHA ou digest;
- 100% dos recursos tocados com estado terminal por recurso;
- dívida normal quitada em até duas vezes o p95 de execução medido, 20,4 min;
- rollback inicia sua escrita em até 5 min após o escritor ativo terminar;
- divergência entre manifesto e container detectada em até 15 min;
- toda falha informa o que ocorreu, o que permaneceu no ar e a próxima ação.

Os objetivos são calculados por janela de 14 dias e publicados no painel. Uma
janela vazia é "sem amostra", não 100% de sucesso.

## 13. Ordem dos PRs e dependências

| Ordem | Entrega | Depende de | Toca principalmente |
|---:|---|---|---|
| 1 | guardas e medição da fila | este plano | `ci/tests`, `ci` |
| 2 | contrato e decisão de estado | 1 | `ci`, testes |
| 3 | inventário e gênese | 2 | `ci`, `infra`, workflow controlado |
| 4 | build com identidade imutável | 2 | deploy de célula, envio de imagem |
| 5 | pin persistente e ativação | 3 e 4 | scripts da VPS, Compose, testes |
| 6 | infra preserva pins | 5 | deploy de infra e reversão |
| 7 | fila `queue: max` | 5 e 6 | três workflows e teste estrutural |
| 8 | rollback prioritário | 7 | rollback, congelamento, auditoria |
| 9 | reconciliador | 7 | `ci`, workflow e estado da entrega |
| 10 | painel e alarmes | 9 | admin e dados calculados |
| 11 | simplificação após 30 dias | 10 | vacina, armadilhas e documentação |

Cada PR fica abaixo do limite de 15 arquivos. Se uma linha ultrapassar esse
limite, ela é dividida por responsabilidade, nunca por metade de uma garantia.

## 14. Critério de conclusão do programa

O programa inteiro só termina quando todas as afirmações abaixo têm prova:

- os três escritores usam fila ampla e política idêntica;
- produção não ativa `:main`;
- todo serviço executa tag SHA ou digest declarado;
- run antigo é ignorado antes de qualquer mutação;
- manifestos e containers concordam;
- o reconciliador cura cancelamento, falha parcial e desvio;
- rollback ganha prioridade sem interromper o escritor ativo;
- pins sobrevivem ao `deploy-infra` e ao reinício do Compose;
- painel mostra fila, dívida, divergência e congelamento;
- 30 dias consecutivos não registram perda, regressão ou dívida vencida;
- um exercício controlado prova cancelamento, reconciliação e rollback;
- armadilhas 173, 183 e 188 mudam para estado guardado com dono mecânico;
- instruções antigas de commit vazio ou rerun repetido deixam de ser a cura
  principal.

Antes dessas provas, o programa está em implantação, mesmo que uma fase isolada
esteja verde.

## 15. Comandos de auditoria previstos

Os nomes finais podem acompanhar as convenções do código, mas as provas não
podem desaparecer:

```powershell
python -m pytest ci/tests/test_fila_de_deploy.py -q
python -m pytest ci/tests/test_estado_do_deploy.py -q
python -m pytest ci/tests/test_reconciliar_deploy.py -q
python -m pytest ci/tests/test_rollback.py ci/tests/test_reversao.py -q
python ci/ci.py --apenas muralhas
python ci/estado_da_entrega.py --pr <numero>
gh run list --workflow deploy-celula.yml --limit 100 --json status,conclusion,createdAt,updatedAt
gh run list --workflow deploy-infra.yml --limit 100 --json status,conclusion,createdAt,updatedAt
```

Na VPS, a evidência vem pelos próprios scripts da esteira. O plano não cria um
passo manual de SSH para o mantenedor nem transforma acesso ao servidor em
pré-requisito de operação normal.

## 16. Corte explícito

Não entra neste programa:

- paralelizar escritores da mesma VPS;
- adotar Kubernetes, Redis ou banco apenas para esta fila;
- redesenhar todos os workflows de CI;
- mudar regras de merge ou contratos de produto;
- reconstruir todas as células em todo merge;
- remover a vacina antes da janela de evidência;
- confiar em ordem de chegada, cor do run ou tag `:main` como prova.

Esses cortes preservam o foco: nenhum deploy elegível some, nenhum run antigo
volta a produção e toda divergência termina visível e recuperável.
