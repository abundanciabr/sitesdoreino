# CLAUDE.md — sitesdoreino

Instruções para qualquer sessão do Claude Code neste repositório.

## Antes de começar qualquer tarefa: leia as armadilhas


A memória de campo do projeto — o que já custou tempo aqui, em formato sintoma →
causa → solução — mora em **`armadilhas/`**, uma entrada por arquivo. Desde
23/08/2026 ela **não é mais um monólito**: o antigo `ARMADILHAS.md` de 1.490 linhas
era 48% da carga de contexto de todo despacho (PLANO-10X, Alavanca 2).

**A regra de leitura, em uma frase: leia `armadilhas/INDICE.md` e abra SÓ a entrada
que casa com a sua tarefa.** O índice tem uma linha por armadilha, com a mensagem de
erro crua como chave — dê Ctrl+F pelo erro que você está vendo, ou pela tecnologia
que vai tocar. Ler a pasta inteira desfaz o motivo de ela existir. Leia também o
`ARMADILHAS.md` (que ficou curto: a regra de uso + a partida rápida do §2) e, se for
trabalhar dentro de uma célula, o `services/<celula>/LICOES.md` quando existir.

**O índice é GERADO e não viaja mais no Git (desde 30/08/2026, TAR-022).** Ele, o
`armadilhas/GUARDAS.json` e o `armadilhas/SINAIS.json` saem de
`ci/indice_de_armadilhas.py` — e por isso **não existem num checkout novo até serem
materializados**. Quem materializa por você: o `SessionStart` de
`.claude/settings.json`, ao abrir a sessão (no clone principal, de onde o sino lê, e
no seu worktree). Se mesmo assim faltar, é uma linha:

```bash
python ci/indice_de_armadilhas.py    # ou: make indice
```

Não procure o índice com `git show origin/main:armadilhas/INDICE.md` — ele não está
mais lá, e o comando falha. **Por que saiu:** a lei manda todo robô acrescentar uma
armadilha ao fim de cada tarefa, e cada entrada nova reescrevia os três arquivos
inteiros; dois robôs do mesmo lote colidiam sem ter escrito uma linha em comum. Em
30/08/2026, num lote de 4, DOIS PRs foram devolvidos pela pista por esse conflito
(o #573, duas vezes). É a doença do painel (`armadilhas/156`), curada com o mesmo
desenho da Onda 3 — fonte multiescritor, materialização de escritor único, validação
independente. Arquivo ausente dá erro na hora e você regenera; o conflito diário era
silencioso até a pista devolver o PR.

Não é formalidade: as mesmas armadilhas já pegaram mais de um agente — sombreamento
de nome entre model Django e `ninja.Schema`, o middleware que derruba o `/healthz`, o
orçamento de 15 arquivos que decide a arquitetura antes de você escrever código. Cada
redescoberta custa tokens e uma rodada de teste.

**E leia também, uma vez por sessão, os 8 padrões de
`docs/decisoes/RETROSPECTIVA-FASE-D.md`** — é curto e é o *andar de cima* do catálogo:
as categorias que atravessam as armadilhas individuais (falso-verde · garantia sem
mecanismo · prova de fora · fail-closed na borda · humano no caminho crítico · contexto
é orçamento · sessões paralelas · viabilidade sem ler a config). O catálogo cura o caso;
só o padrão cura a classe — e a Fase D provou isso do jeito caro: em 48h, uma sessão
repetiu **duas** falhas que já estavam documentadas em outra forma, por conhecer os casos
e não a categoria.

**Ao terminar, acrescente o que aprendeu** — isso faz parte de terminar a tarefa, como
o painel. Regra de onde escrever: se serve para qualquer célula, **crie um arquivo
novo** `armadilhas/NNN-slug.md` — e o **`NNN` se PEDE, não se escolhe**
(`python ci/reservar.py numero armadilha`, que reserva no servidor; `ci/muralha-das-reservas.sh`
reprova o PR que escolheu à mão) — e rode
`python ci/indice_de_armadilhas.py` para regenerar o índice; se só faz sentido dentro
de uma célula, vai no `LICOES.md` dela. **Nunca acrescente ao fim do `ARMADILHAS.md`
nem edite a entrada de outro agente para encaixar a sua** — arquivo novo por entrada
é exatamente o que faz duas sessões paralelas pararem de colidir no mesmo hunk.

**Se a correção definitiva não estiver nas suas mãos** — depende de instalar algo na
máquina, de plano pago, de permissão — **abra um registro** em `painel/registros/`
(tipo `pendencia`, com `precisa_do_dono: true`) **e diga isso ao usuário no relatório
final, em texto claro**. Ele não lê documento a cada sessão; se você contornar em
silêncio, o mesmo atrito volta no próximo despacho, e no seguinte.

**O que espera por ele mora num lugar só — e esse lugar é o livro.** A caixa
"Precisa de você" do painel é CALCULADA (pedido sem resposta), então ela não
consegue esquecer nem inventar. A `§1` do `ARMADILHAS-OPERACAO.md` **deixou de ser
lista de pendências em 26/08/2026**: ela guarda o histórico de cada atrito e as
instruções técnicas dos passos manuais, e **nada de estado**. Não acrescente linha
nova lá, e não devolva marcador 🔴/🟡 às que existem —
`ci/tests/test_uma_casa_para_o_precisa_de_voce.py` reprova as duas coisas.

Por que a regra é dura: até 26/08 as duas listas coexistiam e **já discordavam** —
7 itens "abertos" na tabela contra 6 no painel, com um deles invisível para o
mantenedor. Foi a doença do H18 voltando por dentro da própria lei que a curou
(a auditoria que achou isso está no registro `20260826-019`).

**Quem faz valer:** `ci/muralha-do-indice.sh` (constrói o índice em todo PR, prova que reconstrói igual, e reprova se um gerado voltar ao índice do Git) · `.githooks/pre-commit` (o mesmo, aqui na máquina) · `ci/muralha-das-reservas.sh` (número pedido ao almoxarife). **A LEITURA em si não tem mecanismo** e está declarada em `ci/leis-sem-mecanismo.txt`.

## Mapa do projeto para IA (desde 27/08/2026)


Existe um mapa técnico do projeto inteiro — leis, células, contratos,
infraestrutura, CI/CD, decisões de produto — escrito especificamente para
uma IA sem contexto prévio auditar o sistema de ponta a ponta e sugerir
melhorias: **`painel/ia/INDICE.md`**. Não é leitura obrigatória de todo
despacho (é mais longo que a dieta normal de contexto, e a maioria das
tarefas cabe na leitura de armadilhas + a constituição da célula) — abra
quando a tarefa for uma auditoria ampla, uma segunda opinião externa sobre
arquitetura, ou quando faltar a visão geral do sistema inteiro. Como os
outros mapas deste projeto, ele é um resumo curado: se divergir do
documento original, o original vence, e quem perceber a divergência corrige
o mapa no mesmo PR.

**Quem faz valer:** `ci/tests/test_painel_ia_atualizado.py`.

## O livro de ocorrências é obrigatório, não opcional (desde 26/08/2026)


O painel do dono é **`painel/painel.html`** — a porta única, que **não guarda
nenhum dado próprio**: toda vista é calculada de **`painel/registros/`** (o
livro de ocorrências, versionado) e de medições ao vivo. Decisão do mantenedor
em 26/08/2026, após 8 rodadas de consultoria externa; análise em
`docs/paineis/VEREDITO-DAS-CONSULTORIAS.html`, contrato em `painel/LEIA-ME.md`.

**Regra permanente:** depois de CADA tarefa relevante — concluída, falhou,
ficou bloqueada, mudou de estado, incidente, decisão pedida ou respondida —
**acrescente UM REGISTRO NOVO** em `painel/registros/` (molde no
`painel/LEIA-ME.md`), **sem perguntar se deve**. Registrar é parte de terminar a
tarefa; a muralha-do-painel do CI recusa PR com o livro inconsistente.

**O que você commita é o registro, e SÓ o registro** (desde 28/08/2026, Onda 3
do `docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`). `painel/painel.html` e
`painel/livro-AAAAMM.js` são **gerados**, estão no `.gitignore` e quem os
constrói é a integração — a muralha em todo PR e o deploy antes de montar a
imagem. Rodar `node painel/gerar_manifesto.js` na sua máquina continua sendo
bom (ele valida o registro e você vê o painel), mas o resultado **não entra no
commit**: `.githooks/pre-commit` barra aqui e `ci/verificar_painel.py` reprova
no CI. Motivo medido: enquanto os dois viajavam no Git, todo registro reescrevia
os arquivos inteiros e dois robôs no mesmo dia colidiam sem ter escrito uma
linha em comum — um PR de 4 arquivos levou oito tentativas para entrar
(`armadilhas/156`). Para VER o painel na sua máquina: dois cliques em
`painel/abrir-o-painel.cmd`. O painel de verdade é
<https://meshcraft.top/admin/painel/>.

As regras que importam:

- **Nunca edite um registro existente.** Atualização, correção ou resposta é
  um registro NOVO — se ele fecha um pedido, aponte `responde_a`. A caixa
  "precisa de você" é CALCULADA (pedido sem resposta): ela não esquece, e
  ninguém a mantém à mão.
- **Verde exige prova conferida** (`evidencia` + `verificado_em`). Sem prova,
  registre como está — o painel mostra "não comprovado", e isso é honesto.
- **Merge é gatilho de registro, não pergunta.** Mergeou (ou confirmou um
  merge de fora — "feito", "ok", um link, um "✓"): confira de verdade
  (`gh pr view <N> --json state,mergedBy,mergeCommit`) e registre na MESMA
  resposta.
- **A LEI ANTI-DUPLICAÇÃO: nenhum fato do projeto mora em dois lugares.**
  Superfície nova de acompanhamento se calcula do livro; superfície que
  mantém lista própria é proibida — inclusive dentro do próprio painel, e
  inclusive "só um HTML rapidinho em `arquivos/`". Se o painel não mostra algo
  que deveria, a mudança é na regra de cálculo (`painel/logica.js`, por PR,
  com teste-guarda) — nunca uma lista paralela.
- Os painéis antigos de `arquivos/painel-*.html` são **lápides e fotografias**
  (história congelada). Não os atualize; não crie novos.

**Quem faz valer:** `ci/divida_do_livro.py` (merge sem registro reprova no portão) · `ci/muralha-do-painel.sh` e `ci/verificar_painel.py` (o livro válido e materializado) · `ci/tests/test_uma_casa_para_o_precisa_de_voce.py`.

## O clone principal é espelho, não bancada (desde 26/08/2026)


Duas sessões dividindo a pasta principal já apagaram o trabalho uma da outra
(26/08/2026 — uma trocou o ramo, as edições da outra sumiram). Desde então a
regra do RITOS §1 (worktree por agente) tem muralha mecânica: os hooks de
`.claude/settings.json` chamam `ci/muralha_pasta_compartilhada.py`, que RECUSA
no clone principal qualquer edição e qualquer git que mude estado
(switch/checkout/reset/commit/stash/...). Se a recusa 🧱 aparecer, não é
defeito e não se contorna: crie seu worktree —
`git fetch origin && git worktree add ../wt-<area>-<tarefa> -b
agent/<area>/<tarefa> origin/main` — e trabalhe lá. No principal ficam livres
leituras, `git fetch`, `git worktree` e `gh`; com a árvore limpa, também
`git switch main` e `git pull` (para manter o espelho fresco). Detalhes e
fronteiras: `armadilhas/135`.

**Quem faz valer:** `ci/muralha_pasta_compartilhada.py`, ligado como hook em `.claude/settings.json`.

## O agente pede pouso; quem mergeia é a pista (desde 29/08/2026)


Decisão do mantenedor em 22/08/2026 tirou o merge das mãos dele (motivos em
`docs/decisoes/DECISAO-merge-pelo-agente.md`); decisão dele em 29/08/2026
(registro `20260829-006`) tirou o merge das mãos do AGENTE e o entregou à pista.
Lei: `CONSTITUICAO.md` Lei 4 (com a emenda); rito: `RITOS.md` §2 peças 4 e 5.
**O que não mudou: ninguém espera por ele.** Quem mergeia continua sendo
máquina — mudou qual, e a nova tem paciência.

O fluxo, sem perguntar nada:

1. PR aberto dentro do escopo de um despacho → espere os checks concluírem.
2. `python ci/mergear.py <N> --conferir` — tudo verde?
3. `python ci/mergear.py <N> --pousar` — pede pouso e **vá embora**. A pista
   atualiza com a `main` de agora, confere pelo MESMO portão e mergeia; ela
   comenta no PR o que aconteceu (pousou, devolveu, ou está esperando).
4. O registro no livro (`painel/registros/` — só o registro); e, se o merge
   toca `services/` ou `infra/`, o veredito do run de deploy (seção "Depois de
   todo merge que dispara deploy").

`--confirmo` **recusa** para quem não é a pista, e a recusa ensina o caminho.
Vermelho, pendente, ausente ou ERROR **nunca** vira pedido de pouso — conserte
ou reporte. O botão de merge do site não é caminho para ninguém. Merge em
caminho CODEOWNERS (`contracts/`, `pagamentos`, `checkout`, `infra/`, `ci/`,
`.github/`, arquivos-lei da raiz) só com mandato do despacho, e **anunciado
nominalmente no relatório final**.

**A pista é a única porta, e é opt-out só para emergência** (desde 29/08/2026):
antes dela o agente insistia — atualizar, esperar 90s de checks, a `main` andar,
repetir. Medido: oito voltas num PR de 4 arquivos (`armadilhas/156`). Hoje esse
laço não existe mais, porque o agente não fica na corrida: ele pede pouso e sai.
Os três desfechos possíveis e a mecânica da pista: `RITOS.md` §2 peça 5.

**Vários despachos em paralelo (lote):** a sessão raiz rege pelo
`RUNBOOK-LOTES.md` — composição, as sete regras de inteligência, janela de
merge serial e fechamento. Se o mantenedor pedir "toque um lote", é esse
documento que define o como.

Se o livro não tiver um `tipo` adequado para o que aconteceu, registre com o
tipo mais próximo (`nota` serve para quase tudo) e anote no detalhe — mudar o
vocabulário de tipos é mudança em `painel/logica.js`, por PR, com teste-guarda.
A capa do painel tem teto de blocos e se RECUSA a crescer: realidade nova entra
como registro, não como seção nova.

**Quem faz valer:** `ci/mergear.py` (recusa `--confirmo` para quem não é a pista) · `.github/workflows/pouso.yml` · `ci/tests/test_mergear.py`.

## Como trabalhar com o mantenedor (vale para TODA sessão)


O dono do projeto é leigo em código e em terminal, e lê SOMENTE português —
**toda resposta em PT-BR, sempre**. O resto foi aprendido a custo alto em
21-22/08/2026, no dia em que a plataforma subiu (ele quase desistiu do projeto
no meio dos passos manuais):

- **Faça você o máximo.** Tudo que der por `gh`, pipeline e arquivos, o agente
  faz — o mantenedor só entra onde é insubstituível (segredos, console do
  provedor; desde 22/08/2026 nem o merge: ele é do agente, seção acima).
  Agente não tem SSH para a VPS (Lei 5) e o harness bloqueia a tentativa —
  não insista; o canal do agente é o pipeline.
- **Quando sobrar passo manual, entregue UM bloco único de colar**, fail-closed
  (que se recusa a agir se algo estiver estranho, com uma mensagem tipo "PAROU
  POR SEGURANÇA"), nunca uma sequência de comandos avulsos para digitar um a um.
- **Diga SEMPRE em qual janela colar.** A confusão mais repetida da história do
  projeto: rodar comando do PC dentro da VPS e vice-versa. Regra de bolso que
  funcionou: linha começando com `PS C:\>` = PC; começando com `deploy@srv...`
  ou `root@srv...` = já está DENTRO da VPS (não use `ssh` aí).
- **Avise as surpresas de terminal antes delas acontecerem**: senha invisível ao
  digitar, silêncio = sucesso, a diferença entre `>>` (acrescenta) e `>` (apaga).
- **Reporte em linguagem de resultado** ("a plataforma está no ar"), não de
  processo — e marcos merecem ser celebrados. O ânimo do mantenedor é parte da
  infraestrutura do projeto.
- **Qualquer coisa pendente nele ao fechar uma tarefa ou uma conversa vira
  pergunta estruturada ali mesmo — nunca uma frase solta esperando que ele
  digite uma resposta livre.** Use `AskUserQuestion` (ou equivalente) com cada
  opção traduzida para português simples — o porquê e a consequência prática
  de cada lado, sem jargão cru ("evento ou HTTP" vira "os números podem
  demorar alguns segundos, ou precisam ser sempre exatos?") — e marque a
  opção recomendada quando houver uma. Vale para decisão técnica real E para
  algo tão simples quanto agendar uma conversa futura ("quer que eu explique
  agora, prefere um resumo primeiro, ou fica para depois") — a régua não é
  "isto é grande o bastante para virar pergunta", é "isto ia deixar ele
  compondo uma resposta livre". Se ele fechar a pergunta sem responder, é
  "não agora": pare e espere, não repita a mesma pergunta.
  **Confirmado com força por ele em 25/08 e reforçado em 27/08/2026** — na
  segunda vez, depois de eu fechar um relatório com "isso vai precisar de uma
  conversa sua quando puder" em vez de abrir a caixa ali mesmo; ele reagiu
  pedindo por essa "caixa que aparece pedindo a resposta" em vez do texto
  cair na caixa de digitar dele. A regra virou instrução permanente dele
  também em `~/.claude/CLAUDE.md` (todo projeto, toda conversa) — este
  parágrafo é a camada específica do sitesdoreino, que soma à de lá.
  **Em lote (RUNBOOK-LOTES.md):** quem fala com ele é a sessão-maestro, nunca
  os despachos individuais — um despacho que topa com algo do mantenedor
  registra e devolve à maestro (RUNBOOK-LOTES.md §7, Lote 3 lição 11), e é a
  maestro quem consolida numa única pergunta estruturada. Sem essa regra, um
  lote de 5 despachos em paralelo viraria 5 caixas de pergunta simultâneas.

## Este projeto é para ser feito completo — nunca proponha a versão minimalista


Decisão do mantenedor em 25/08/2026 (lei completa, com as palavras dele:
`docs/decisoes/DECISAO-filosofia-de-escopo.md`): **entre uma opção completa/robusta
e uma reduzida/rápida, a completa é a escolha padrão — mesmo custando mais tempo,
mais PRs, mais sessões dele.** Não é ingenuidade sobre custo: é decisão informada,
depois de outros projetos dele terem falhado por seguir justamente o conselho de
"comece pequeno e rápido".

Na prática:

- **Nenhum agente — nem uma "banca" convocada para dar segunda opinião —
  recomenda escopo reduzido como forma de economizar tempo ou esforço.** Pode
  registrar a análise; a recomendação final não escolhe uma opção só por ser
  mais barata.
- **Não use "isso vai levar dias/semanas" para desencorajar ambição.** O
  mantenedor já viu, na prática, robôs deste projeto fazendo em minutos o que
  esse vocabulário sugere levar semanas — não avalie por cronograma de equipe
  humana.
- **Isto não é desculpa para descuido.** PRs pequenos, orçamento de 15
  arquivos, Ritos de Contrato, evidência vermelho→verde —
  nada disso muda. Fatiar em fases seguras não é reduzir escopo, é a forma
  responsável de construir algo grande. "Completo" é o destino; a escada de
  PRs é o caminho.
- **Bloqueio real continua sendo bloqueio real** — custo de serviço pago,
  credencial que só ele tem, limite legal, vulnerabilidade de segurança. Isso
  é fato sobre o que é possível, não "conselho de ir devagar", e continua
  reportado como sempre (`ARMADILHAS-OPERACAO.md` §1).

## Nenhum texto publicado sai com travessão (desde 30/08/2026)


Decisão do mantenedor em 30/08/2026: **todo texto escrito para ser publicado
online sai sem travessão.** No lugar dele entram vírgula, parênteses,
dois-pontos ou aspas. A escolha depende do papel que o travessão fazia na
frase, e é de quem escreve:

- **Vírgula (troca neutra)** — explicação comum no meio da frase, que mantém a
  leitura fluida e natural. `O motorista — que estava muito cansado — parou no
  posto.` vira `O motorista, que estava muito cansado, parou no posto.`
- **Parênteses (menor destaque)** — dado puramente acessório, que pode ser
  ignorado sem perda. `A inflação — principal vilã do orçamento — voltou a
  subir.` vira `A inflação (principal vilã do orçamento) voltou a subir.`
- **Dois-pontos (fechamento)** — quando o trecho isolado fica no FIM da frase e
  serve de esclarecimento ou conclusão. `Ele só queria uma coisa — paz.` vira
  `Ele só queria uma coisa: paz.`
- **Aspas (diálogo)** — quando o travessão marcava fala de personagem.
  `— Não quero ir hoje — disse Pedro.` vira `"Não quero ir hoje", disse Pedro.`

**A troca é uma REESCRITA, não um caractere trocado.** Esta é a metade da lei
que faltava, e ela custou uma dúzia de frases ruins publicadas no site antes de
o mantenedor apontar o erro em 30/08/2026. A régua não é "sumiu o travessão": é
**a frase ficou em português correto do Brasil**. Se a troca mais próxima
deixar a frase torta, a resposta é reescrever, não aceitar a torta.

**O erro que já aconteceu, para ninguém repetir:** dois-pontos **não** separa o
verbo do seu complemento, nem abre uma oração que continua direto o pensamento
anterior. Quando o trecho depois do travessão é continuação direta (começa por
`é`, `são`, `não`, um imperativo), dois-pontos quebra a frase:

```
travessão:  Modelo pela metade também conta — é vendo o meio do caminho…
ERRADO:     Modelo pela metade também conta: é vendo o meio do caminho…
certo:      Modelo pela metade também conta, pois é vendo o meio do caminho…
certo:      Modelo pela metade também conta: afinal, é vendo o meio do caminho…
```

A saída é **vírgula com conectivo** (`pois`, `porque`, `e`, `mas`), ou um
**ponto final** quando o que vem depois é uma frase nova (`Nada foi criado.
Tente de novo.`), ou dois-pontos **com** palavra de transição (`: afinal,`).

**Onde dois-pontos está certo, e continua:** lista de definição
(`**Aluno**: você entra normalmente`), enumeração seguida de síntese
(`…o que está pronto: isso é calculado`), anúncio do único item
(`tem uma forma só: a situação Ex-aluno`) e rótulo antes do conteúdo.

**A régua final, em uma pergunta:** leia a frase em voz alta. Se você tropeçar,
a troca está errada, ainda que o travessão tenha sumido.

Contam como travessão as três riscas longas (`—`, `–`, `―`) e as formas
escritas em HTML que viram risca na tela (`&mdash;`, `&#8212;` e parentes). O
**hífen continua livre**: ele é letra de palavra composta ("guarda-chuva"), não
pontuação de frase — um portão que o caçasse recusaria português correto.

**Título de aba usa barra vertical, não uma das quatro.** Em `<title>` e em
`{% block titulo %}` o travessão não era pontuação de frase: era separador entre
a página e o nome do lugar (`Cadastro — Meshcraft`). Nenhuma das quatro trocas
encaixa ali, e o mantenedor escolheu a barra em 30/08/2026, depois de ver a
proposta de parênteses: **`Cadastro | Meshcraft`**. A barra vale SÓ para
separador de título; dentro de uma frase, as quatro continuam sendo a régua.
Não "conserte" isto de volta para parênteses.

**Onde a regra vale:** em tudo que alguém que não é o mantenedor lê. A vitrine
do site, cadastro, login, checkout, quiz, fórum, área do aluno, Caixa de
Sugestões, os documentos publicados e as traduções. A superfície é DERIVADA, não
listada à mão: toda pasta `templates/` de toda célula, toda `traducoes/` e
`documentos/`. Célula nova, ou tela nova numa célula que já existe, entra
sozinha — mapa mantido à mão envelhece em silêncio, e é a Classe 8 do
`docs/decisoes/PLANO-MESTRE-ROBOS-SEM-COLISAO.md`.

**Onde ela NÃO vale:** o bastidor do mantenedor (o painel e as telas de
administração), que sai por lista curta em `ci/texto-publico-bastidor.txt`, uma
linha por tela e com o motivo escrito; e o que nunca é publicado — este
arquivo, as armadilhas, os documentos internos e os comentários dentro do
código. O portão DESPE os comentários antes de contar (`{% comment %}`, `{# #}`,
`<!-- -->`, `#` de YAML): sem essa poda a dívida medida seria quatro vezes maior
e quase toda falsa, e medir a coisa errada com precisão é como um portão morre.

**Cuidado com a célula `admin`:** ela não é bastidor inteira. As páginas de erro
e a área pública de documentos (`/docs/…`, isenta na porta) moram nela e
continuam sob a regra.

**Onde a regra alcança o código:** a pasta `management/commands/` inteira, de
toda célula. É de lá que sai conteúdo que o visitante lê — o nome e a descrição
de uma área do fórum, as categorias da Caixa. Só as constantes de string contam;
docstring e comentário, não.

A fronteira já foi estreita demais uma vez, e quem achou o buraco foi o
mantenedor olhando o site: ela era `semear_*.py`, e `seed_sugestoes.py` escapava
pelo NOME do arquivo. Régua que depende de alguém escolher o prefixo certo não é
régua.

**O limite que fica, e é o mais importante desta lei:** o portão vigia
ARQUIVOS. **Texto que já está gravado no banco ele não vê, e nunca verá.**
Corrigir um semeador NÃO corrige a linha que ele criou — `semear_areas` é
`get_or_create` e de propósito não altera o que existe. Foi assim que um
travessão sobreviveu no fórum a uma varredura que se declarou completa: o
mantenedor o viu no site depois de eu reportar tudo limpo (registro
`20260830-051`). Quando mexer no texto de um semeador, pergunte **se aquilo já
foi semeado em produção** — e, se foi, o conserto é uma migração de dados que
casa o texto antigo inteiro (molde em `forum/migrations/0003`). O teste não
avisa: ele roda em banco vazio, onde o `UPDATE` não encontra linha nenhuma.

Fica de fora também `painel/ia/`, que sai em `/mapa-ia/` sem porta: é mapa
técnico para uma IA de fora auditar o sistema, e a régua do mantenedor é a
leitura de PESSOAS.

**O que já estava publicado** quando a regra nasceu está em
`ci/travessoes-herdados.txt`, arquivo por arquivo, com a contagem exata. A
catraca é a mesma das outras dívidas da casa: o número declarado é compromisso,
não teto frouxo — crescer reprova, e encolher também reprova até o número novo
aparecer no diff. Texto NOVO nunca nasce devendo.

Na dúvida sobre uma frase, rode `python ci/travessao.py --listar`: ele mostra
frase por frase, com o número da linha. A recusa do portão já traz as quatro
trocas com exemplo, na mesma tela — não é preciso voltar aqui.

**Quem faz valer:** `ci/muralha-do-travessao.sh` → `ci/travessao.py` (roda em
todo PR via `ci/ci.py --apenas muralhas`; fail-closed) · `ci/tests/test_travessao.py`.


## Depois de todo merge que dispara deploy


Merge tocando `services/**` **ou `painel/**`** dispara o `deploy-celula` (a
célula `admin` embute `painel/` no build — registro novo no livro também
conta); tocando `infra/docker-compose.yml`, `infra/traefik/**` ou o próprio
workflow, dispara o `deploy-infra`. **Merge confirmado ⇒ conferir o run
disparado**, na mesma
resposta — o veredito REAL vem de `gh run view <id> --json status,conclusion`,
nunca do exit de um comando com `| tail`/`| head` pendurado (ARMADILHAS §5.10:
já houve falso-verde assim, e os greens históricos do deploy-celula mentiram
até 21/08/2026 — H13). Run vermelho: `gh run view <id> --log-failed` mostra
onde parou; repete-se sem novo merge com `gh run rerun <id> --failed`. Reporte
o veredito ao mantenedor em texto claro — desde 26/08/2026 a `main` tem sim
required checks (`muralhas` e `ci-celula-gate`, H3), mas **nenhum deles olha o
deploy**: ele roda DEPOIS do merge, e ninguém mais vai olhar por você.

**E essa conferência NUNCA se espera em silêncio** (desde 29/08/2026): rode
`python ci/esperar.py --run <id> --teto 20 --dizendo "o deploy da <célula>"`
pela ferramenta `Monitor` — a espera fala sozinha na janela do mantenedor e
morre no teto. Toda espera tem voz e tem teto: RITOS.md §2 peça 6
(`armadilhas/161`).

**Quem faz valer:** `ci/portao_de_deploy.py` (nenhuma imagem sobe sem evidência verde) · `.github/workflows/alarme-main.yml` (abre issue se a `main` fica vermelha) · `ci/muralha_da_espera.py` (espera muda e sem teto é comando recusado).

