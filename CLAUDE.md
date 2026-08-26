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
novo** `armadilhas/NNN-slug.md` (NNN = próximo número livre) e rode
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

## O livro de ocorrências é obrigatório, não opcional (desde 26/08/2026)

O painel do dono é **`painel/painel.html`** — a porta única, que **não guarda
nenhum dado próprio**: toda vista é calculada de **`painel/registros/`** (o
livro de ocorrências, versionado) e de medições ao vivo. Decisão do mantenedor
em 26/08/2026, após 8 rodadas de consultoria externa; análise em
`docs/paineis/VEREDITO-DAS-CONSULTORIAS.html`, contrato em `painel/LEIA-ME.md`.

**Regra permanente:** depois de CADA tarefa relevante — concluída, falhou,
ficou bloqueada, mudou de estado, incidente, decisão pedida ou respondida —
**acrescente UM REGISTRO NOVO** em `painel/registros/` (molde no
`painel/LEIA-ME.md`) e rode `node painel/gerar_manifesto.js`, **sem perguntar
se deve**. Registrar é parte de terminar a tarefa; a muralha-do-painel do CI
recusa PR com o livro inconsistente. As regras que importam:

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

## Mergear é trabalho do agente (desde 22/08/2026)

Decisão do mantenedor — motivos e mecânica em
`docs/decisoes/DECISAO-merge-pelo-agente.md`; lei: `CONSTITUICAO.md` Lei 4;
rito: `RITOS.md` §2 peça 4. O fluxo, sem perguntar "posso mergear?":

1. PR aberto dentro do escopo de um despacho → espere os checks concluírem.
2. `python ci/mergear.py <N> --conferir` — tudo verde?
3. `python ci/mergear.py <N> --confirmo <N>` — mergeia e já confere no GitHub
   que o PR virou `MERGED`.
4. O registro no livro (`painel/registros/` + `node painel/gerar_manifesto.js`);
   e, se o merge toca `services/` ou `infra/`, o veredito do run de deploy
   (seção "Depois de todo merge que dispara deploy").

Vermelho, pendente, ausente ou ERROR **nunca** se mergeia — conserte ou
reporte. O botão de merge do site não é caminho para ninguém. Merge em caminho
CODEOWNERS (`contracts/`, `pagamentos`, `checkout`, `infra/`, `ci/`,
`.github/`, arquivos-lei da raiz) só com mandato do despacho, e **anunciado
nominalmente no relatório final**.

**Vários despachos em paralelo (lote):** a sessão raiz rege pelo
`RUNBOOK-LOTES.md` — composição, as sete regras de inteligência, janela de
merge serial e fechamento. Se o mantenedor pedir "toque um lote", é esse
documento que define o como.

Se o livro não tiver um `tipo` adequado para o que aconteceu, registre com o
tipo mais próximo (`nota` serve para quase tudo) e anote no detalhe — mudar o
vocabulário de tipos é mudança em `painel/logica.js`, por PR, com teste-guarda.
A capa do painel tem teto de blocos e se RECUSA a crescer: realidade nova entra
como registro, não como seção nova.

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
- **Decisão que só ele pode tomar → pergunta estruturada de múltipla escolha,
  nunca prosa técnica esperando que ele extraia a resposta sozinho.** Use
  `AskUserQuestion` (ou equivalente) com cada opção traduzida para português
  simples — o porquê e a consequência prática de cada lado, sem jargão cru
  ("evento ou HTTP" vira "os números podem demorar alguns segundos, ou
  precisam ser sempre exatos?") — e marque a opção recomendada quando houver
  uma. **Confirmado por ele em 25/08/2026** como o formato certo, ao responder
  as 5 perguntas pendentes da área administrativa desse jeito: use sempre que
  uma bifurcação real do projeto depender da palavra dele.

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
  arquivos, uma célula por PR, Ritos de Contrato, evidência vermelho→verde —
  nada disso muda. Fatiar em fases seguras não é reduzir escopo, é a forma
  responsável de construir algo grande. "Completo" é o destino; a escada de
  PRs é o caminho.
- **Bloqueio real continua sendo bloqueio real** — custo de serviço pago,
  credencial que só ele tem, limite legal, vulnerabilidade de segurança. Isso
  é fato sobre o que é possível, não "conselho de ir devagar", e continua
  reportado como sempre (`ARMADILHAS-OPERACAO.md` §1).

## Depois de todo merge que dispara deploy

Merge tocando `services/**` dispara o `deploy-celula`; tocando
`infra/docker-compose.yml`, `infra/traefik/**` ou o próprio workflow, dispara o
`deploy-infra`. **Merge confirmado ⇒ conferir o run disparado**, na mesma
resposta — o veredito REAL vem de `gh run view <id> --json status,conclusion`,
nunca do exit de um comando com `| tail`/`| head` pendurado (ARMADILHAS §5.10:
já houve falso-verde assim, e os greens históricos do deploy-celula mentiram
até 21/08/2026 — H13). Run vermelho: `gh run view <id> --log-failed` mostra
onde parou; repete-se sem novo merge com `gh run rerun <id> --failed`. Reporte
o veredito ao mantenedor em texto claro — desde 26/08/2026 a `main` tem sim
required checks (`muralhas` e `ci-celula-gate`, H3), mas **nenhum deles olha o
deploy**: ele roda DEPOIS do merge, e ninguém mais vai olhar por você.
