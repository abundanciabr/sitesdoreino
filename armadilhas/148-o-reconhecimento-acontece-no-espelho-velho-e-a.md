# O reconhecimento acontece no espelho velho, e a bancada nasce nova — você projeta para um sistema que não existe mais

**Sintoma:** você entrega uma tela, uma decisão ou uma pergunta ao mantenedor
declarando que alguma coisa **não existe** ("não há fila de espera", "nenhuma
célula guarda isso", "essa operação não está no contrato") — e ela existe, com
lei escrita, contrato congelado e código no ar. Nada falhou: os testes passam,
o portão fica verde, o deploy sobe. O erro só aparece quando um humano lê o
texto e responde *"mas isso já foi feito ontem"*.

**Causa — e ela é ESTRUTURAL, não descuido.** O `armadilhas/135` fez do clone
principal um **espelho**: lá a muralha recusa edição e git de estado. Mas ela
não recusa **leitura**, e leitura é justamente o que uma sessão faz primeiro.
O resultado é uma assimetria que ninguém escolheu:

| Fase da sessão | Onde acontece | Quão fresco |
|---|---|---|
| reconhecimento (`grep`, `cat`, `find` — "o que existe hoje?") | clone principal | **o que ele tiver**: pode ser semanas |
| trabalho (`git worktree add ... origin/main`) | worktree novo | sempre fresquíssimo |

Ou seja: **a bancada nasce atualizada, e o mapa que você desenhou antes dela,
não.** O `git fetch` do rito de abertura atualiza as *refs remotas* e o
worktree, mas **não move o `HEAD` do espelho** — `cat services/x/models.py` no
clone principal continua devolvendo o arquivo do commit em que ele parou.

O caso medido: 28/08/2026, célula `admin`. O espelho estava no PR **#261** e o
`origin/main`, no **#336** — **75 merges** de distância, sem um único aviso. A
sessão leu `services/alunos/apps/matriculas/models.py` de lá, viu três status
(`ativa`/`suspensa`/`reembolsada`), e concluiu com sinceridade que a fila de
liberação não existia. Ela existia desde a véspera: `DECISAO-fila-de-liberacao.md`
(lei, Rito de Contrato com o mantenedor presente), três portas no contrato
congelado da `alunos` e o formulário no ar. O contrato chamava
`GET /pre-matriculas` de *"a porta do painel administrativo"* — e a sessão
publicou, na área administrativa, uma tela dizendo que aquilo não existia, mais
uma pergunta pedindo ao mantenedor que decidisse de novo o que ele já tinha
decidido.

**Por que escapou de tudo:** nenhum guarda do repositório mede isto. Os testes
de uma célula medem o que a célula FAZ; os do painel medem o que o painel MOSTRA.
Ausência afirmada sobre outra célula não é código executado — é uma frase. E o
`ci/mergear.py` confere o GitHub, que estava certo o tempo todo.

**Parente próxima, e a diferença importa:** `armadilhas/101` é o mesmo clone
velho, com o gatilho *"vou AUDITAR uma mudança"* e o prejuízo *"reportei um bug
que já foi corrigido"*. Aqui o gatilho é **anterior e muito mais comum** —
*"vou entender o que existe para propor o que falta"* — e o prejuízo é pior:
não é um relatório errado, é **produto desenhado e mergeado** sobre um mapa
falso, mais o tempo do mantenedor gasto redecidindo. Cure as duas juntas; a
101 sozinha não cobre esta, porque quem está levantando fatos não sente que
está "auditando" nada.

**Solução — nesta ordem, e a primeira é a barata:**

1. **Não leia código do espelho para saber o que existe. Leia do `origin/main`.**
   Depois de `git fetch origin`, é uma linha, e vale antes de criar worktree:

   ```bash
   git show origin/main:services/alunos/apps/matriculas/models.py
   ```

   `git grep <padrão> origin/main -- <caminho>` faz o mesmo para varredura.
   Nenhum dos dois depende do estado do espelho.

2. **Se o reconhecimento for longo, crie o worktree ANTES dele** e leia de lá.
   O rito já manda criar worktree para trabalhar; o que esta armadilha
   acrescenta é que **explorar também é trabalho**. Custa um comando, e a partir
   dele todo `cat`/`grep` está no estado real.

3. **Antes de afirmar ausência sobre OUTRA célula, confira o contrato, não o
   código** — `contracts/<celula>.openapi.yaml` no `origin/main`. Ele é a
   fronteira congelada: se a operação está lá, ela existe, e a pergunta certa
   passa a ser "por que esta célula ainda não a usa?" em vez de "por que
   ninguém construiu isso?".

4. **Uma medição de sanidade, quando o assunto for grande** (`git rev-list
   --count HEAD..origin/main` no espelho): se der um número grande, todo fato
   que você levantou ali é suspeito. Setenta e cinco não parece diferente de
   zero em nenhuma tela — é preciso perguntar.

**O guarda que dá para plantar, e o que ele NÃO cobre:** onde uma tela ou um
documento declara que uma operação de outra célula não existe, o teste pode ler
`contracts/<celula>.openapi.yaml` e exigir que a declaração case com o contrato
— foi o que a `admin` passou a fazer em
`services/admin/tests/test_painel_da_escola.py`
(`test_a_fila_que_o_contrato_tem_nao_pode_ficar_sem_dono_nesta_tela`, provado
por mutação). Isso fecha a ausência afirmada sobre *contrato*. **Não fecha**
ausência afirmada sobre lei, sobre plano ou sobre código interno de outra
célula — para essas, a cura continua sendo o passo 1.

**Origem:** entrega do painel da escola na célula `admin` (PR #339),
28/08/2026 — o mantenedor leu a tela recém-publicada e respondeu descrevendo o
formulário da fila que já estava no ar havia um dia.
