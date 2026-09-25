# CLAUDE.md | sitesdoreino

Lei canônica: leia `CONSTITUICAO.md`, `RITOS.md` e instruções por caminho.
Motivos: `docs/decisoes/DECISAO-historia-das-leis-do-claude-md.md`.

## O Padrão de Trabalho (Modelo Steve Jobs / Apple) — a régua de TODA tarefa

Restrições operacionais para toda tarefa: a regra vence a pressa.

#### 1. Resolva o problema real antes de escrever

Resolva o problema real. Antes de código, salvo tarefa trivial, diga em até
5 linhas: quem usa, o que vê, faz e sente; a versão mais simples que resolve
o problema inteiro; o que pode sair sem perda. Comece pela experiência. Incerteza real de UX ou
arquitetura exige o menor protótipo visível, apresentado antes da construção.

#### 2. Discorde antes, execute depois

Se a abordagem é inferior, diga antes: uma objeção de até 5 linhas, uma
alternativa concreta e seu trade-off. Execute o que ele decidir. Nunca
obedeça em silêncio ao que sabe ser ruim nem troque a ideia dele sem avisar.

#### 3. Justifique cada adição e preserve o pedido inteiro

Cada adição exige justificativa em uma frase; na dúvida, não adicione.
Sem pedido explícito, proíba opções/flags por flexibilidade, abstrações
hipotéticas, dependência que a linguagem ou o projeto dispensa, arquivos
`utils`, `helpers`, `misc`, `common`, wrappers e camadas sem motivo,
comentário óbvio, código comentado, TODO e melhoria fora do escopo.
Prefira menos arquivos, linhas, conceitos e passos. Entregue o núcleo completo
em partes coesas e liste o que falta do pedido; nunca reduza a ambição para
economizar esforço. Uma coisa completa vale mais que cinco pela metade.

#### 4. Decida o que é seu

Escolha a solução e justifique em uma linha; não sirva cardápio nem pergunte
o que o código responde. Decisões irreversíveis, destrutivas ou caras
(dados, migrations, API pública, dinheiro), segredos e decisões exclusivas
dele exigem confirmação antes da ação. A sessão responsável pergunta; o subagente
registra o bloqueio e devolve impacto e reversão.

#### 5. Responda pelo produto inteiro

Do primeiro comando à tela, responda por setup, execução, erros e documentos.
Dependência quebrada exige conserto autorizado ou aviso explícito.
A entrega funciona da cadeira do usuário.

#### 6. Só declare pronto com prova

Rodou de verdade, com comando e saída real, ou escreva "NÃO RODEI".
Trate vazio, erro, carregando, primeiro uso e entrada inválida. Todo erro
explica o que aconteceu e o que fazer. Zero caminhos quebrados, placeholders
ou "implementar depois". Nomes dizem o que são, renomeie quando necessário.
Siga convenções existentes. Sem debug, código morto ou import sem uso.
Todos os itens aplicáveis são obrigatórios; um item falhando impede PRONTO.
Prometer o conserto não é consertar: PRONTO sobre medição vermelha é recusado.

#### 7. Faça o passe de remoção

Examine cada linha, arquivo, dependência e passo: se remover não quebra
nada do pedido, remova. Pronto é quando não há mais nada a tirar.

#### 8. Revise com rigor

Leia como o crítico mais implacável: liste o que reprovaria e corrija antes
de entregar. Código que causaria vergonha numa apresentação não está pronto.

#### 9. Demonstre e preste contas

Mostre comando e saída real, tela ou artefato do jeito que o usuário vê.
Checklist final e cinco blocos: **O que mudou**, **O que foi verificado**,
**Pendências**, **Veredito** PRONTO ou NÃO PRONTO com motivo, e **Instruções**
com o que acontece agora. NÃO PRONTO exige lista em português de leigo: o que
houve, de quem é a bola, o que destrava e o prazo, mesmo que nada dependa dele.
Cortes só se houver; auditoria item a item só quando relevante.
Sem elogio próprio, enchimento, repetir o que ele sabe ou "espero que ajude".

#### 10. Não substitua prova por promessa

Frases proibidas: "deve funcionar", "provavelmente", "em teoria",
"bom o suficiente", "por enquanto", "depois a gente melhora",
"solução temporária", "gambiarra", "quick fix". Se surgirem, falta concluir.

#### 11. Conversa é mudança real; fim de loops inúteis

Toda troca de mensagem deve levar a mudança, resultados, benefícios ou soluções
CONCRETAS em direção ao resultado da tarefa proposta. É expressamente proibido
repetir status sem agir, delegar repetidamente sem avanço ou entrar em loop de
mensagens inúteis.

**Nenhuma IA deve perguntar ou informar à outra IA sobre estado do Git, PR,
checks, branches ou pouso.** O Git já emite avisos de status automaticamente.
Cada agente consulta diretamente a fonte estruturada (comandos, portões,
scripts) e age sobre o resultado. Mensagem de status só existe quando traz uma
mudança concreta, decisão necessária ou bloqueio novo. Todo loop ou perda de
tempo deve ser imediatamente reconhecido, interrompido e redirecionado para
ação.

### As três costuras

A regra 3 proíbe adição não pedida. Tudo o que foi pedido entra no menor caminho funcional, na forma mais enxuta que já funciona e já tem lugar para crescer.
A regra 4 distingue decisões do agente das decisões exclusivas do mantenedor.
O formato da regra 9 inclui as obrigações da casa: CODEOWNERS nominal em
mudanças; provas de integração/publicação só quando conferidas; bloqueio,
decisão ou passo manual em Pendências. Nunca invente resultado para fechar.

**Quem faz valer:** `ci/padrao_de_trabalho.py`; julgamento não automatizado.

## Antes de começar qualquer tarefa: leia as armadilhas

Use o contexto direcionado da abertura `ci/sessao.py`: confira origens,
ausências e truncamento; abra entradas citadas/recuperadas,
`services/<celula>/LICOES.md` e uma vez por sessão os 8 padrões de
`docs/decisoes/RETROSPECTIVA-FASE-D.md`. Leis globais e por caminho permanecem.
Consulte `python ci/consultar_armadilhas.py "<erro>"` ou `--caminho <arquivo>`.
Índices ausentes: `python ci/indice_de_armadilhas.py`; não suponha ausência
de restrições. Para aprofundamento, use `--caminho`/`--sintoma` da sessão ou abra
`armadilhas/INDICE.md` sob demanda.

Lição nova: número por `python ci/reservar.py numero armadilha`, arquivo
novo `armadilhas/NNN-slug.md`, índice regenerado. Não acrescente a
`ARMADILHAS.md` nem edite entrada alheia. Declare `gatilho` e `licao`
quando ligados a caminho. Lição exclusiva da célula vai ao `LICOES.md`.
O escrivão julga lições da equipe. Correção fora do alcance exige registro
`pendencia`, `precisa_do_dono: true`, e relatório.

**Quem faz valer:** `ci/consultar_armadilhas.py`, muralhas do índice e reservas.

## O clone principal é espelho, não bancada

Nunca edite nem mude o git no principal. Abra
`python ci/sessao.py --celula <area> --tarefa <slug> --sem-container`
para área sem serviço; com serviço, omita `--sem-container`.
Entre no caminho absoluto informado. Retome pela mesma entrada, preservando
alterações. Recusa exige conferir dono e ação segura, nunca forçar.
Baseline da abertura é conferido antes de editar; sem contêiner, rode testes
dos alvos. Falha herdada exige saída e revisão medida, ausência não aprova.
No principal são livres leituras, fetch, worktree e gh; somente com árvore
limpa são permitidos switch main e pull.

**Quem faz valer:** `ci/sessao.py`, `ci/muralha_pasta_compartilhada.py`
(aviso SessionStart; a proibição de editar continua lei).

## Execute o pedido dentro do mandato

A sessão que recebe o pedido responde pela execução, validação e entrega.
As fichas em `.claude/agents/` e `.codex/agents/` definem competências por
tarefa, sem reservar trabalho a uma marca de IA. Subagente não pergunta ao
mantenedor nem cria outro. No Claude Code, declare model sonnet ou opus;
Workflow é recusado. Dependências seguem em série, com `Depende-de: #N`
somente quando reais. Preserve o orçamento de 15 arquivos fora `painel/`
e `fila/`, as suítes de cada célula e o mandato dos caminhos protegidos.
`make pr` embarca reserva, recibo e eventos; não duplique esses efeitos.
Trabalho descoberto fora do brief vira tarefa na fila, sem ampliar o mandato.
O fluxo está em `RUNBOOK-LOTES.md`.

**Quem faz valer:** `ci/pr.py`, `ci/fila.py`, `ci/muralha_dos_sub_agentes.py` e testes das fichas.

## O que uma chamada custa

Modelo e esforço: `python ci/economia_da_fabrica.py brief`; rotina usa
econômico, arquitetura/dúvida usa superior. Sub-agente nasce só em `sonnet`
ou `opus` declarado.
Meça o estado nas fontes estruturadas de Git, GitHub e fila.

**Quem faz valer:** `ci/economia_da_fabrica.py`.

## Entregue o menor caminho que funciona de ponta a ponta

O pedido vira o menor caminho que uma pessoa usa do começo ao fim e que já se testa inteiro. Fora dessa entrega fica o que esse caminho não precisa para funcionar.

Nome, dado e fronteira desse caminho já são os definitivos. O próximo pedaço entra por acréscimo. Proibido o protótipo que será reescrito. Proibido o sistema inteiro antes de existir uma porta que abre.

O que foi pedido com nome entra no caminho, na forma mais enxuta que já funciona. Jogar fora o plano pedido continua proibido.

Sem flag, sem abstração para um futuro hipotético e sem peça que ninguém usa. O lugar de crescer é a fronteira real deste caminho.

PRs pequenos, Ritos e prova de vermelho para verde continuam. Serviço pago, credencial, limite legal e segurança continuam bloqueio real.

Escopo: o site é `meshcraft.top`. `basileiatoutheou.org` está
congelado e não recebe trabalho, exceto a rota do webhook do Mercado Pago presa
a esse host. `docs/decisoes/DECISAO-foco-em-meshcraft.md`.

**Quem faz valer:** julgamento.

## Nenhum texto publicado sai com travessão

Proíba `—`, `–`, `―` e entidades HTML em texto publicado.
Reescreva em português correto. Não separe verbo de complemento nem
continuação direta com dois-pontos; use conectivo ou ponto.
Hífen livre; título de aba usa barra: `Cadastro | Meshcraft`.
Vale em templates, traducoes, documentos, management/commands, rótulos
TextChoices fora de migrations e arquivos `ci:texto-publicado`.
Exclua bastidor (`ci/texto-publico-bastidor.txt`), `painel/ia/`, não publicado
e a obra dele (aulas/livro), sem contagem de riscas nem pedido de reescrita.
O portão mede arquivos; texto semeado exige migração de dados.
Confira `python ci/travessao.py --listar`.

**Quem faz valer:** `ci/travessao.py` no pre-commit (staged), CI e testes do editor.

## O livro de ocorrências é obrigatório, não opcional

Conclusão, falha, bloqueio, incidente e decisão pedida/respondida exigem
registro novo <1 KB em `painel/registros/`; molde `painel/LEIA-ME.md` e número
por `python ci/reservar.py numero registro`. Nunca edite registro; correção
é outro, com `responde_a` ao fechar pedido. Verde exige `evidencia` e
`verificado_em`. `make pr` abre PR e embarca recibo no ramo: não repita esses efeitos.
Só registro é commitado; painel.html e livro-AAAAMM.js são gerados.
Merge confirmado de fora: `gh pr view <N> --json state,mergedBy,mergeCommit`
e registro na mesma resposta. Telas calculam o livro, sem lista paralela.
Superfície muda em `painel/logica.js` por PR com guarda.
Sem tipo específico, use nota.

**Quem faz valer:** `ci/divida_do_livro.py`, pre-commit e portão de pouso.

## Integração automática

PR pronto integra por `pouso.yml` e `ci/mergear.py --automatico`, sem revisor,
atestado, etiqueta ou gesto de coordenação. `muralhas` e `ci-celula-gate` precisam
passar no SHA atual. Contrato congelado e CODEOWNERS
exigem a palavra do mantenedor, e ela vale onde ele a deu: dita na sessão vale
tanto quanto digitada no site. Quem a recebeu transcreve `Mandato-do-mantenedor:`
na descrição com o pedido, os caminhos autorizados e a origem (sessão e data).
Nunca invente mandato nem pare a tarefa para mandá-lo escrever no site o que
já autorizou; sem autorização nenhuma, peça a ele na própria sessão.
Base atrasada é atualizada e medida novamente; rascunhos, forks e conflitos
não integram. Informe somente estados comprovados de validação, integração e
publicação. Veja `docs/decisoes/DECISAO-merge-sem-rito-de-pouso.md`.

**Quem faz valer:** `ci/mergear.py`, `.github/workflows/pouso.yml` e a proteção nativa da main.

## O que você entrega para ele mora no site

Entrega durável vai ao site: fatos em tela calculada, conteúdo em página.
Documento recebido é ordem de serviço: inventarie, compare, abra fila e
execute. Antes dessas entregas, leia `docs/guia-mantenedor.md`.

### Regra de destino do conteúdo

Pedido de manual, documento, página, guia, roteiro, texto, conteúdo, anúncio,
explicação ou material para leitura do público tem como destino padrão o site.
Publique por qualquer caminho autorizado, inclusive editor ou migração de
documento novo. Confira a URL pública; arquivo Markdown isolado não conta
como publicação.

O GitHub fica reservado ao que é necessário para o funcionamento do site,
sistema ou projeto: código, templates, testes, contratos, configurações,
infraestrutura, workflows, leis mecânicas e registros exigidos pelos ritos.
Documento técnico interno só vai para o repositório quando o mantenedor pedir
esse destino ou quando a lei do projeto exigir o arquivo como fonte de
execução. Se o caminho de publicação não puder ser executado, registre o
bloqueio em vez de mudar silenciosamente a entrega para o GitHub.

**Quem faz valer:** julgamento.

## Como trabalhar com o mantenedor

Sempre PT-BR. Tudo aqui é feito por robôs: execute até a entrega. Ferramenta
ausente exige outro caminho autorizado; ele entra só no insubstituível. Sem SSH da
VPS, use pipeline: `operacoes-vps.yml` diagnostica com saída sanitizada;
rollback e provisionamento usam seus workflows. Operação ausente exige PR
com operação delimitada e teste, não script para ele colar na VPS.
Antes de passo manual/decisão, leia `docs/guia-mantenedor.md`.
Toda proibição de perguntar, inclusive a do subagente, obriga a dizer no fecho
o que vem depois.

### Proibição de adiamento silencioso

Nenhum robô pode marcar, tratar ou comunicar uma tarefa como adiada,
postergada ou deliberadamente deixada para depois sem anuência expressa do
mantenedor. A fila não possui estado de adiamento. Se houver impedimento real,
o robô deve registrar imediatamente `bloqueada`, com motivo e `espera` igual a
`mantenedor` ou `fila`, e comunicar isso no mesmo retorno. Cancelar, reduzir o
escopo ou trocar o destino também exige decisão expressa do mantenedor. Silêncio
não é anuência: sem decisão registrada, a tarefa continua aberta e em execução.

**Quem faz valer:** `ci/fila.py` recusa eventos de adiamento; `ci/fila.py validar`
reprova qualquer arquivo que tente criá-los; a prestação de contas exige que uma
tarefa incompleta diga o que falta, quem destrava e a próxima ação.

**Quem faz valer:** julgamento.

## Plano na abertura, contas no fecho

Abra com `## Plano` e `- [ ]` por passo. **Etapa** é concluir ou bloquear passo
planejado, nunca ferramenta, leitura, aviso automático ou retentativa.
Reimprima o checklist só quando uma caixa mudou ou surgiu bloqueio, nunca
após o gancho exibi-lo. No fecho, uma prestação de contas (regra 9): PRONTO
com caixa aberta é contradição, NÃO PRONTO honesto é aceito, e leitura,
pergunta ou acordar não geram dívida. **Instruções** fecha toda prestação de
contas e o gancho recusa sem ele.
PRONTO sobre a última medição vermelha: conserte e meça de novo, ou diga
NÃO PRONTO e explique nas Instruções.
Entrega em voo não fecha sessão: PR aberto, rascunho, check ou deploy sem
veredito é objetivo incompleto; meça com teto (`ci/esperar.py`),
nunca em laço; remedeie o técnico, e só decisão dele vira pendência dele
(Lei 11).

**Quem faz valer:** `ci/prestacao_de_contas.py` (UserPromptSubmit, Stop, voo)
e testes; checklist intermediário é julgamento.

## Mapa do projeto para IA

`painel/ia/INDICE.md` é o mapa técnico para auditoria ampla/segunda opinião
de arquitetura, não leitura de todo despacho. Fonte original vence divergência;
quem detectar corrige mapa no mesmo PR.

**Quem faz valer:** `ci/tests/test_painel_ia_atualizado.py`.
