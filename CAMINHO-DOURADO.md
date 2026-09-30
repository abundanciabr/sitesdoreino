# CAMINHO DOURADO — Receita operacional vigente

Constituição: autoridade e limites. INVARIANTES.md: propriedades. Esta é a
fonte do Padrão de Trabalho e da execução comum. AGENTS.md e CLAUDE.md são
entradas diretas; não mantêm versões concorrentes. Leia a régua e as regras
pertinentes ao brief; as receitas técnicas continuam sob demanda.

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
(dados, migrations, API pública, dinheiro) e decisões exclusivas dele exigem
confirmação antes da ação. A sessão responsável pergunta; o subagente
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

### Provas da entrega e adoção incremental

`ci/pr.py` confere o recibo mínimo antes de escrever o commit, mas ainda
valida antes e depois do embarque do recibo e dos eventos. Não elimine uma
validação sem equivalência das entradas. `ci/telemetria.py` identifica cada
rodada para distinguir repetição de duração acumulada.

Submeter o PR registra a submissão; não conclui a tarefa. Integração,
publicação técnica e aceite funcional são estados distintos. O encerramento
exige a jornada afetada na revisão e ambiente comprovados, incluindo o efeito
final de operações assíncronas. Recibo, merge ou saúde isolados não bastam.
A ausência de um produtor dessa prova permanece pendência no GPS, não sucesso.

No caminho de candidatos, `validar` confere estrutura e equivalência e deixa
`aceito: false`. Aceitar e consumir exigem prova assinada do publicador oficial,
identidade da fonte e evidências realmente executadas. Código integrado não
comprova sozinho o piloto de publicação. Consulte os comandos e guardas de
`ci/candidato.py`; use a situação e as provas da tarefa no GPS para decidir
onde a adoção está ativa. Proposta, piloto e adoção não ampliam automaticamente
a receita para as demais classes.

Cada resultado adotado atualiza sua fonte e consumidores no mesmo incremento.
Registre no GPS existente item PME, escopo, situação, regra substituída,
fontes, prova e revisão; decisões históricas preservam a origem e apontam o
sucessor. O plano e seus modelos, limites de frentes e pilotos não viram leis
permanentes. Uma pendência obrigatória não desaparece ao escrever a receita.


## O que uma chamada custa

Modelo e esforço: `python ci/economia_da_fabrica.py brief`.
No programa TAR-958, a configuração atual autoriza `gpt-6-luna` ou
`gpt-6-sol`, explícitos com `fork_turns=none`; não é uma lei permanente
do produto. O mandato, o brief e os parâmetros executados precisam concordar.
Luna low lê mecanicamente; Luna medium implementa mudanças pequenas. Sol medium
executa múltiplas etapas; Sol high trata arquitetura, dados, autorização,
concorrência e recuperação. xhigh exige razão concreta; max é excepcional.
Valide arquivo e parâmetros do disparo por `python ci/economia_da_fabrica.py validar-brief`.
Brief ausente, modelo alheio, divergência ou fallback impedem execução.
Só a sessão responsável cria frentes e recebe indisponibilidade.
Preserve o modelo principal; confira metadados. Consistência não prova runtime.
No Claude Code, subagente usa `sonnet` ou `opus` declarado.

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

## Pontuação livre

Por decisão do mantenedor em 28/09/2026, não há revisão obrigatória,
bloqueio, aviso ou contagem por pontuação em textos públicos,
rascunhos, documentos, aulas, livros ou respostas da IA.
A pontuação pertence a quem escreve. Esta decisão substitui as regras
anteriores de travessão, inclusive nas fichas e decisões históricas.

**Quem faz valer:** `ci/tests/test_codex_nativo.py`, `services/admin/tests/test_editor_de_documentos.py` e `services/admin/tests/test_livro.py`.

## Histórico sem cobrança de dívida

O livro de ocorrências e seus registros existentes são preservados.
Ausência de registro ou de citação de PR não cria dívida e não impede
commit, integração ou publicação. O recibo automático de `make pr`
permanece como histórico, sem exigir escrituração manual adicional.
Não repita os efeitos que `make pr` já registrou.
Registros escritos continuam sujeitos ao formato e às evidências declaradas.

**Quem faz valer:** `ci/tests/test_codex_nativo.py` e `ci/pr.py`.

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

Conteúdo vai ao site. Documentos ficam só para administradores.
Acesso público exige pedido explícito do mantenedor, registrado na evidência.
`como-funciona-a-entrada` é exceção autorizada. Grave pelo editor ou migração
e confira a leitura em `/admin/documentos/`; com pedido público, também a URL
sem sessão. Markdown não encerra a entrega.

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
VPS, use `operacoes-vps.yml` (Lei 5). Antes de passo manual/decisão, leia `docs/guia-mantenedor.md`.
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

## Abrir e retomar uma sessão — sucessor de RITOS §1

Use `make sessao CELULA=<area> TAREFA=<slug> TAR=TAR-NNN` ou
`python ci/sessao.py --celula <area> --tarefa <slug> --tar <numero>`.
Sem serviço, acrescente `SEM_CONTAINER=1` ou `--sem-container`; nesse caso o
baseline não é medido e os testes dos alvos devem rodar antes da edição.
Entre na bancada absoluta informada e repita a mesma entrada para retomar,
sem apagar alterações. A abertura reivindica a tarefa depois de criar a bancada.
Confira o log e declare apenas o baseline observado. Se ele falhou antes da
edição, pare sem tocar arquivos e reporte a falha e a revisão medida; não
atribua a falha à mudança.

A primeira resposta declara a leitura do Padrão nesta fonte, da Constituição
global e da constituição da célula pertinente, o caminho da bancada, a tarefa
e o resultado real do baseline. O brief delimita alvos, leitura e restrições;
carregue só receitas técnicas citadas. Um PR pode tocar mais de uma célula
quando todas as suítes correspondentes rodam. PRs encadeados declaram
`Depende-de: #N`. No fecho, registre handoff com revisão, provas, pendências
e riscos; arquive a bancada somente depois de a entrega não precisar dela.

**Quem faz valer:** `ci/sessao.py`, `ci/muralha_pasta_compartilhada.py`,
`ci/padrao_de_trabalho.py` e `ci/tests/test_sessao.py`.

## Integrar, publicar e aceitar — sucessor de RITOS §2

A proteção da `main` exige PR, `muralhas` e `ci-celula-gate` verdes na revisão
atual. `pouso.yml` roda da `main`, atualiza base atrasada e retoma pelo próximo
evento. Rascunho, fork, conflito ou check ausente impedem integração. O SHA
conferido é exigido no merge. CODEOWNERS e contrato congelado continuam
exigindo mandato do mantenedor; a descrição registra pedido, caminhos e origem,
mas texto ou conta isolados não autenticam a autorização.

Depois de `make pr`, meça uma vez com
`python ci/esperar.py --checks <N> --so-desfecho` ou
`python ci/esperar.py --entrega <N> --so-desfecho`. Se o deploy foi cancelado
ou recusado pela VPS, consulte `python ci/rerun_de_deploy.py --ultimo`.
Integração, publicação e aceite funcional são provas distintas. Para
reconciliar TAR, confira a jornada afetada na revisão integrada e no ambiente
publicado, com comando, resultado, origem e efeito final assíncrono quando
existir; só então preencha `evidencia` e `verificado_em` no registro e use
`python ci/fila.py reconciliar TAR-NNN --quem <voce> --aceite-registro painel/registros/<arquivo>`.
Sem essa prova, mantenha a tarefa submetida e registre a pendência; a
continuação TAR-969 ainda trata o produtor mecânico. Falha técnica preserva
commits e arquivos. Teto ou decisão exclusiva são relatados como NÃO PRONTO.

**Quem faz valer:** `ci/mergear.py`, `.github/workflows/pouso.yml`,
`ci/prestacao_de_contas.py` e `ci/tests/test_merge_automatico.py`.

## Mudar contrato — sucessor de RITOS §3

Contrato congelado só muda com o mantenedor presente e mandato nominal.
Use PR com etiqueta `contrato`. Uma extensão pode acompanhar seu provedor
somente quando adiciona operações ou definições sem alterar as anteriores,
com freeze vivo e sonda de autenticação. Remoção, mudança de tipo, drift,
outro provedor e prova ausente são recusados; `contrato-remocao` não libera
essa exceção. Provedor vem primeiro e preserva compatibilidade: campo novo
opcional, evento incompatível em `*.v2.json` enquanto o v1 ainda tem
consumidores. Depois migre consumidores em PRs próprios contra mock novo.
Registre o quê, por quê, consumidores e plano de migração no PR.

**Quem faz valer:** `ci/cerca-de-celula.sh`, `ci/contract_freeze.py`,
`ci/contrato_aditivo.py` e `ci/tests/test_contrato_aditivo.py`.

## Reverter uma emergência — sucessor de RITOS §4

Em emergência, dispare o rollback delimitado pelo pipeline:

```bash
gh workflow run rollback.yml -f celula=<celula> -f alvo=<sha-main-anterior> -f motivo="<incidente>"
```

O alvo é o SHA completo de um commit ancestral da `main` cuja imagem exista
no registry. `ci/rollback.py` confere manifesto, ancestralidade e imagem antes
de qualquer SSH. O rollback de uma célula não toca as outras. O workflow
congela a célula, inclusive quando a aplicação termina incerta; a integração
de PRs dessa célula e de `infra/` fica recusada. A referência de congelamento
vale 6 horas e o mesmo disparo a renova. O pin não persiste sozinho: o próximo
deploy da célula volta a `:main`, por isso a trava impede a reexposição.
`alvo=main` descongela só depois de aplicação confirmada. Consulte
`python ci/rollback.py congelados`; `descongelar <celula>` é intervenção
explícita. O job com chave da VPS não escreve no repositório; o job que
escreve a referência não recebe essa chave. Se GitHub Actions estiver fora,
o acesso manual mínimo pelo mantenedor é último recurso:
`ssh deploy@<IP>`, `cd /opt/plataforma`,
`PAGAMENTOS_TAG=<sha> docker compose up -d pagamentos`,
`docker compose ps pagamentos`. Revertê-lo pelo deploy normal.
Depois do incidente, a correção viaja por PR e o post-mortem produz
um portão, com a armadilha e a prova registradas.

**Quem faz valer:** `ci/rollback.py`, `.github/workflows/rollback.yml`,
`ci/mergear.py` e `ci/tests/test_rollback_congela_ao_aplicar.py`.

## Pegar e registrar trabalho na fila — sucessor de RITOS §5

Abra a bancada antes de reivindicar TAR. `ci/reservar.py` mantém reserva
atômica por 3 horas, com expiração; a segunda sessão recebe recusa. `criar`, `pegar` e
`concluir` recusam o clone principal para que o evento viaje com o PR;
`listar`, `validar` e `soltar` continuam disponíveis para leitura e
recuperação. Descoberta fora do brief vira tarefa na fila, nunca lista
paralela. O estado é calculado dos eventos, sem campo de status.

Conclusão exige prova vinculada à jornada e revisão. Impedimento vira evento
`bloqueada` com `espera: mantenedor` ou `espera: fila`, comunicado na hora;
não existe adiamento silencioso. Embarque todos os eventos da tarefa no PR e
rode `python ci/fila.py validar`. Reserva remota vale agora, evento versionado
permanece como histórico.

**Quem faz valer:** `ci/fila.py`, `ci/reservar.py`, `ci/muralha-da-fila.sh`
e `ci/tests/test_fila.py`.

## §0 — Como usar (dieta por citação)

**Este documento NÃO é lido inteiro.** O despacho cita receitas por número
(`RECEITAS: R3, R5`); o agente carrega no contexto: este §0 + a tabela de decisão
(§1) + SOMENTE as receitas citadas. As receitas assumem a árvore do
`celula-template/` (projeto `config/`, apps em `apps/`).

**A memória de campo segue a mesma dieta, desde 23/08/2026.** `ARMADILHAS.md` deixou
de ser um monólito: cada armadilha é um arquivo em `armadilhas/`. O contexto direcionado
na abertura recupera por caminho e sintoma; abra as origens e confira limitações.
Para aprofundamento, refine a busca ou consulte `armadilhas/INDICE.md`. O que é do humano — §1 precisa-de-você, como se mergeia,
painéis, §9 dívidas abertas — está fora dessa dieta, em `ARMADILHAS-OPERACAO.md`;
o que já foi resolvido, em `docs/historico/RESOLVIDAS.md`. **Armadilha nova ao
terminar o despacho é arquivo NOVO** (`armadilhas/NNN-slug.md`) + `make indice`,
nunca um append no fim de um arquivo que outra sessão também está escrevendo.

**Três leis das receitas:**
1. Todo trecho colado leva o marcador da origem na primeira linha:
   `# [RECEITA:R3 v1]`. É assim que detectamos drift depois.
2. Desviar de uma receita não é improviso local — é issue `arquitetura:` ANTES.
3. Receita que precisar mudar duas vezes (chegar a v3) é candidata a virar pacote
   versionado (`plataforma-<nome>`) — a "casa única" definitiva da Lei 3. Mudança
   neste arquivo passa por CODEOWNERS, como toda lei.

## §1 — Tabela de decisão

| Preciso de... | Receita | Nunca faça |
|---|---|---|
| Expor um endpoint novo na minha API | **R1** | Mudar `contracts/` sem seguir “Mudar contrato” |
| Chamar a API de outra célula | **R2** | Importar código dela ou ler o banco dela |
| Avisar a plataforma que algo aconteceu | **R3** | Publicar direto no Redis sem outbox |
| Reagir a algo que aconteceu fora da célula | **R4** | Consultar o banco de quem emitiu |
| Proteger uma regra que não pode quebrar | **R5** | Guarda sem evidência vermelho→verde |
| Criar uma tela/página nova | **R6** | Estado compartilhado entre páginas; status decidido no cliente |
| Mudar o schema do banco | **R7** | Remover/renomear coluna na mesma release que parou de usá-la |
| Trabalho assíncrono interno da célula | **R8** | Task não-idempotente |
| Dado inicial, demo ou fixture de ambiente | **R9** | INSERT manual no banco |
| Marcar testes de caminho feliz por método | **R10** | Smoke sem marker registrado |
| Colocar um site/domínio novo no ar | **R11** | Editar o Traefik ou criar stack nova |
| Criar uma página em vários idiomas | **R12** | Texto fixo no template; a tag `url` crua; página nascendo com um idioma só |
| Acrescentar um idioma a um site | **R12** | Recalcular o `_fonte` sem traduzir; idioma novo nascendo indexável |
| Mexer na régua de uma meta (curva, datas, alvo) | **R13** | Corrigir o dado e deixar a prosa que o repete para trás |
| Abrir PR que toca caminho CODEOWNERS | **R14** | Mandato em parágrafo, caminhos separados por vírgula, ou prefixo pela metade |

## §2 — O Despacho (template de brief — copie e preencha)

A sessão que recebe o pedido define o brief e responde pela entrega. O despacho
executa uma tarefa dentro dos ALVOS e do ORÇAMENTO, com um PR por tarefa.
As fichas definem competências por tarefa, sem papéis fixos por fornecedor.

```markdown
# DESPACHO — <celula>: <tarefa em ≤5 palavras>
CÉLULA: <celula> · WORKTREE: wt-<celula>-<tarefa> · RECEITAS: R_, R_
PADRÃO: o Padrão de Trabalho (1ª seção do CAMINHO-DOURADO.md) vale nesta tarefa como em
  todas — inclusive a regra 2 (discorde ANTES, em ≤5 linhas, com UMA alternativa
  e o trade-off) e a regra 9 (relatório nos cinco blocos da regra 9, sem enchimento).
ANTES: abertura por “Abrir e retomar uma sessão” + contexto direcionado pelos ALVOS e sintoma;
  abra as entradas citadas e recuperadas + services/<celula>/LICOES.md, se existir. Ao terminar,
  acrescente o que aprendeu como ARQUIVO NOVO em armadilhas/NNN-slug.md + `make
  indice`; o que só o mantenedor resolve vai na tabela §1 do
  ARMADILHAS-OPERACAO.md E no seu relatório final.
CONTEXTO (≤5 linhas): ...
MISSÃO (1 frase): ...
ALVOS (PERMITIDO ESCREVER): services/<celula>/apps/<x>/..., services/<celula>/tests/...
SOMENTE-LEITURA: contracts/<...>.openapi.yaml, contracts/eventos/<...>.v1.json
FORA DE ESCOPO: <o que NÃO tocar, mesmo que pareça relacionado>
INVARIANTES TOCADOS: INV-P_ (evidência vermelho→verde obrigatória no PR)
DoD: make ci verde + <critérios específicos da tarefa>
ORÇAMENTO: ≤ N arquivos (fix: 1–5 · feature: 5–15)
```

## §3 — Convenções transversais (valem em toda receita)

```python
# config/settings.py — padrão fail-hard  # [RECEITA:CONV v1]
import os
from django.core.exceptions import ImproperlyConfigured

def env(nome: str) -> str:
    valor = os.environ.get(nome, "")
    if not valor:
        raise ImproperlyConfigured(f"variável obrigatória ausente: {nome}")
    return valor

SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = os.environ.get("DEBUG", "0") == "1"
FORCE_SCRIPT_NAME = os.environ.get("SCRIPT_NAME") or None  # célula dona do próprio prefixo

# Tokens estáticos aceitos, um por par consumidor (TOKENS_ACEITOS_CHECKOUT etc.):
TOKENS_ACEITOS = {v for k, v in os.environ.items() if k.startswith("TOKENS_ACEITOS_") and v}
```

```python
# apps/core/middleware.py — células PÚBLICAS (funil, quiz, checkout, alunos)  # [RECEITA:CONV-SITE v1]
import os
import time

import httpx
from django.http import Http404

_CACHE: dict = {}
TTL_SEGUNDOS = 60

class SiteResolutionMiddleware:
    """[INV-P11] Resolve Host→Site UMA vez por requisição, via catálogo (com cache).
    Host não cadastrado ⇒ 404 — nunca um site padrão."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        host = request.get_host().split(":")[0].lower()
        site = self._resolver(host)
        if site is None:
            raise Http404("site desconhecido")
        request.site = site          # todo o resto da célula lê daqui
        return self.get_response(request)

    def _resolver(self, host: str):
        hit = _CACHE.get(host)
        if hit and hit[0] > time.time():
            return hit[1]
        r = httpx.get(
            f"{os.environ['CATALOGO_API_URL']}/sites/by-host/{host}",
            headers={"Authorization": f"Bearer {os.environ['TOKEN_CATALOGO']}"},
            timeout=5.0,
        )
        site = r.json() if r.status_code == 200 else None
        _CACHE[host] = (time.time() + TTL_SEGUNDOS, site)   # cacheia inclusive o 404
        return site
```

Registre em `MIDDLEWARE` logo após os middlewares de segurança do Django. Views e
queries da célula filtram SEMPRE por `request.site["id"]`.

Dinheiro: `amount_cents`/`price_cents`/`total_cents` **inteiros**, sempre.
Identificadores em EN, comentários e prosa em PT. `Decimal` só na borda do provider.

**Rodar o portão da raiz localmente exige o mesmo ambiente que o CI declara.**
As células têm fail-hard em `config/settings.py` (INV-P10), então sem as
variáveis o exportador de contrato morre antes de exportar e cada célula vira
um ERROR. **Esse resultado não é um diagnóstico do repositório:** as
verificações de `seguranca/*` nem chegam a aparecer na tabela, e a lista curta
se parece com uma lista inteira (armadilhas/483).

```bash
# [RECEITA:CONV-CI v1] — os valores são os de .github/workflows/ci-celula.yml
PYTHONUTF8=1 \
DJANGO_SECRET_KEY=ci-apenas-nunca-em-producao \
DATABASE_URL=postgres://ci:ci@localhost:5432/ci_db \
REDIS_STREAMS_URL=redis://localhost:6379/0 \
HUEY_REDIS_URL=redis://localhost:6379/1 \
python ci/ci.py --apenas freeze
```

A célula `pagamentos` pede ainda `MP_ACCESS_TOKEN` e `MP_WEBHOOK_SECRET`; os
falsos que o CI usa estão no mesmo workflow.

---

## R1 — Endpoint novo (Django-Ninja) + export do schema

```python
# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI
from apps.core.auth import BearerPorPar
from apps.ofertas.api import router as ofertas_router

api = NinjaAPI(title="Catalogo API", version="1.0.0", auth=BearerPorPar())
api.add_router("/ofertas", ofertas_router)
# Webhooks públicos (só na fortaleza): api.add_router("/webhooks", webhooks_router, auth=None)
```

```python
# apps/core/auth.py  # [RECEITA:R1 v1]
from django.conf import settings
from ninja.security import HttpBearer

class BearerPorPar(HttpBearer):
    """Aceita os tokens estáticos de TOKENS_ACEITOS_* — um por par consumidor."""
    def authenticate(self, request, token: str):
        return token if token in settings.TOKENS_ACEITOS else None
```

```python
# apps/ofertas/api.py  # [RECEITA:R1 v1]
from ninja import Router, Schema

router = Router()

class OfferOut(Schema):
    slug: str
    price_cents: int  # dinheiro é centavos inteiros — lei da plataforma

@router.get("/{slug}", response=OfferOut)
def get_offer(request, slug: str):
    ...
```

```python
# apps/core/management/commands/export_openapi.py  # [RECEITA:R1 v1]
import json
from django.core.management.base import BaseCommand
from config.api import api

class Command(BaseCommand):
    help = "Imprime o schema OpenAPI vivo (o freeze de contrato compara com contracts/)"
    def handle(self, *args, **kwargs):
        self.stdout.write(json.dumps(api.get_openapi_schema(), ensure_ascii=False))
```

JSON é YAML válido — o `ci/freeze-de-contrato.sh` aceita a saída como está.
**Se o endpoint novo não está no contrato congelado: PARE.** É Rito de Contrato
(“Mudar contrato”), não decisão de sessão.

**Addendo — contrato sem `$ref` nomeado (schemas 100% inline nos paths):** alguns
contratos (ex.: `leads`, `alunos`) não declaram `components.schemas` — todo
`requestBody`/`response` é inline no próprio path. Se o handler usar um
`ninja.Schema` tipado normalmente (como `OfferOut` acima), o django-ninja extrai o
model para um `components.schemas.<Nome>` nomeado e referencia via `$ref` — o
freeze reprova, porque o congelado não tem esse `$ref`. Nesse caso, não tipe o
corpo com `Schema`: aceite `request` sem parâmetro de corpo tipado e declare o
`requestBody`/`responses` inteiros via `openapi_extra` no decorator (dict Python
literal, na mesma forma exata do YAML congelado — chaves de status como `int`,
não string). `deep_dict_update` do django-ninja faz merge recursivo: se a chave
já existir (ex.: `responses[200]["description"]`) o valor é sobrescrito; se não
existir (ex.: `requestBody`, ou um novo status `422`), é inserida inteira. Depois,
em `export_openapi.py`, remova também o que o django-ninja sempre emite mas o
contrato à mão omite quando vazio: `"parameters": []` por operação sem parâmetro
de path/query, e `components.schemas: {}` quando nenhum model nomeado foi
registrado. Exemplo completo: `services/leads/apps/core/api.py` +
`services/leads/apps/core/management/commands/export_openapi.py`.

Nota: esta técnica existe porque os contratos originais desta plataforma
misturam schemas nomeados e inline sem critério declarado. Contratos NOVOS
deveriam preferir components.schemas nomeados desde o início — evita este
workaround por completo. Use openapi_extra só quando o contrato congelado já
existir inline e mudar a estrutura não for opção (Rito de Contrato).

## R2 — Cliente da API de outra célula

```python
# apps/core/clients/pagamentos.py  # [RECEITA:R2 v1]
import os
import httpx

class PagamentosClient:
    """Fala SÓ o que está em contracts/pagamentos.openapi.yaml.
    Em dev, aponte PAGAMENTOS_API_URL para o mock prism (make mocks, porta 4010)."""

    def __init__(self) -> None:
        self.base = os.environ["PAGAMENTOS_API_URL"].rstrip("/")
        self.token = os.environ["TOKEN_PAGAMENTOS"]

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.token}"}

    def criar_intent(self, *, idempotency_key: str, payload: dict) -> dict:
        r = httpx.post(
            f"{self.base}/intents",
            json=payload,
            headers={**self._headers(), "X-Idempotency-Key": idempotency_key},  # [INV-P4]
            timeout=10.0,  # timeout SEMPRE explícito
        )
        r.raise_for_status()
        return r.json()

    def obter_intent(self, intent_id: str) -> dict:
        r = httpx.get(f"{self.base}/intents/{intent_id}", headers=self._headers(), timeout=10.0)
        r.raise_for_status()
        return r.json()
```

Retry: livre em GET; em POST **somente** repetindo a MESMA `X-Idempotency-Key`.
Em testes unitários, mocke com `respx` — nunca suba a outra célula.

## R3 — Emitir evento (outbox transacional + relay)

```python
# apps/eventos/models.py  # [RECEITA:R3 v1]
import uuid
from django.db import models

class OutboxEvent(models.Model):
    event_id = models.UUIDField(default=uuid.uuid4, unique=True)
    event = models.CharField(max_length=100)            # ex.: "pagamento.aprovado"
    version = models.PositiveSmallIntegerField(default=1)
    payload = models.JSONField()                        # SÓ o campo `data` do envelope
    occurred_at = models.DateTimeField(auto_now_add=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=["published_at"])]
```

```python
# apps/eventos/emitir.py  # [RECEITA:R3 v1]
from .models import OutboxEvent

def emitir(event: str, data: dict, *, version: int = 1) -> OutboxEvent:
    """[INV-P6] Chame SEMPRE dentro da MESMA transaction.atomic() da mudança de estado."""
    return OutboxEvent.objects.create(event=event, version=version, payload=data)
```

```python
# apps/eventos/tasks.py  # [RECEITA:R3 v1]
import json
import os

import redis
from django.utils import timezone
from huey import crontab

from config.huey import huey
from .models import OutboxEvent

_r = redis.from_url(os.environ["REDIS_STREAMS_URL"])

@huey.periodic_task(crontab(minute="*"))   # rede de segurança
def relay_outbox():
    pendentes = OutboxEvent.objects.filter(published_at__isnull=True).order_by("id")[:200]
    for ev in pendentes:
        envelope = {
            "event": ev.event,
            "version": ev.version,
            "event_id": str(ev.event_id),
            "occurred_at": ev.occurred_at.isoformat(),
            "data": ev.payload,
        }
        _r.xadd(f"eventos.{ev.event}", {"json": json.dumps(envelope, ensure_ascii=False)})
        ev.published_at = timezone.now()
        ev.save(update_fields=["published_at"])
```

Uso no ponto de mudança de estado (latência sub-segundo + segurança):

```python
from django.db import transaction
from apps.eventos.emitir import emitir
from apps.eventos.tasks import relay_outbox

with transaction.atomic():
    payment.aprovar()                      # mudança de estado
    emitir("pagamento.aprovado", data)     # [INV-P6] mesma transação
    transaction.on_commit(lambda: relay_outbox())   # publica já; o periódico cobre falhas
```

## R4 — Consumir evento (consumer group + dedup)

```python
# apps/eventos/models.py (acrescentar)  # [RECEITA:R4 v1]
class EventoProcessado(models.Model):
    event_id = models.UUIDField(unique=True)   # a unicidade É o guarda de idempotência
    processed_at = models.DateTimeField(auto_now_add=True)
```

```python
# apps/eventos/management/commands/consume_eventos.py  # [RECEITA:R4 v1]
import json
import os

import redis
from django.core.management.base import BaseCommand
from django.db import IntegrityError

from apps.eventos.models import EventoProcessado
from apps.matriculas.handlers import ao_pagamento_aprovado

GRUPO = "alunos"                                # nome DESTA célula
STREAMS = {"eventos.pagamento.aprovado": ao_pagamento_aprovado}

class Command(BaseCommand):
    help = "Consumer de eventos da célula (roda como processo supervisionado)"

    def handle(self, *args, **opts):
        r = redis.from_url(os.environ["REDIS_STREAMS_URL"])
        for stream in STREAMS:
            try:
                r.xgroup_create(stream, GRUPO, id="0", mkstream=True)
            except redis.ResponseError:
                pass  # grupo já existe
        while True:
            resp = r.xreadgroup(GRUPO, "worker-1", {s: ">" for s in STREAMS}, count=10, block=5000)
            for stream, msgs in resp or []:
                handler = STREAMS[stream.decode()]
                for msg_id, campos in msgs:
                    envelope = json.loads(campos[b"json"])
                    try:
                        EventoProcessado.objects.create(event_id=envelope["event_id"])
                    except IntegrityError:                      # já processado — idempotência
                        r.xack(stream, GRUPO, msg_id)
                        continue
                    handler(envelope["data"])
                    r.xack(stream, GRUPO, msg_id)
```

Handler com a unicidade como guarda (exemplo INV-P5):

```python
# apps/matriculas/handlers.py  # [RECEITA:R4 v1]
from django.db import transaction
from .models import Matricula   # order_id = models.CharField(unique=True)

def ao_pagamento_aprovado(data: dict) -> None:
    with transaction.atomic():
        Matricula.objects.get_or_create(          # [INV-P5] unique=True é o guarda real
            order_id=data["order_id"],
            defaults={"email": data["customer"]["email"]},
        )
```

## R5 — Teste-guarda de invariante

```python
# tests/test_inv_p3_webhook_idempotente.py  # [RECEITA:R5 v1]
# Nome do arquivo = código do invariante. Um arquivo por invariante.
import pytest

pytestmark = pytest.mark.django_db

def test_webhook_reentregue_gera_uma_transicao(client, webhook_pix_assinado):
    for _ in range(3):
        resp = client.post("/api/pagamentos/webhooks/mp/pix", **webhook_pix_assinado)
        assert resp.status_code == 200
    assert Payment.objects.filter(status="approved").count() == 1
    assert OutboxEvent.objects.filter(event="pagamento.aprovado").count() == 1
```

Protocolo de evidência (Lei 6): rode o guarda ANTES do fix e cole a saída vermelha
crua no PR; rode DEPOIS e cole a verde. Sem edição, sem resumo.

## R6 — Página nova (ilha Alpine, mobile-first, status do servidor)

```html
<!-- templates/<celula>/pix.html  # [RECEITA:R6 v1] -->
{% extends "base_mobile.html" %}
{% block conteudo %}
<div x-data="pixIsland()" x-init="init()" class="p-4 max-w-md mx-auto">
  <img :src="qrBase64" alt="QR Code Pix" class="w-full">
  <p class="text-center mt-4" x-text="statusLabel()"></p>
</div>
<script>
function pixIsland() {
  return {
    status: "aguardando_pagamento",
    qrBase64: window.PIX_QR,
    async poll() {                                   // [INV-P7] status vem do servidor
      const pedido = await api.get(`/pedidos/${window.ORDER_ID}`);
      this.status = pedido.status;
      if (this.status === "aguardando_pagamento") setTimeout(() => this.poll(), 3000);
      if (this.status === "pago") window.location = window.URL_OBRIGADO;
    },
    statusLabel() {
      return { aguardando_pagamento: "Aguardando pagamento…", pago: "Pagamento confirmado!",
               expirado: "QR Code expirado" }[this.status] ?? this.status;
    },
    init() { this.poll(); },
  };
}
</script>
{% endblock %}
```

```javascript
// static/<celula>/api.js  # [RECEITA:R6 v1] — cliente fino; NENHUMA regra de negócio
const api = {
  async get(path) {
    const r = await fetch(`${window.API_BASE}${path}`);
    if (!r.ok) throw new Error(`GET ${path}: ${r.status}`);
    return r.json();
  },
  async post(path, body) {
    const r = await fetch(`${window.API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!r.ok) throw new Error(`POST ${path}: ${r.status}`);
    return r.json();
  },
};
```

Cada página é uma ilha: estado próprio, zero variáveis compartilhadas entre páginas.
Comunicação entre páginas = servidor (snapshot/status), nunca `localStorage` ou globais.

Página de site multilíngue (site que o catálogo serve com `languages` — R12,
fluxo B): **R12** manda — texto por `{% t %}`, link por `{% url_i18n %}`,
strings da ilha pela subárvore `js.*`.

## R7 — Migration Expand-and-Contract (a dança de três releases)

| Release | O que entra | Regra |
|---|---|---|
| N (**expand**) | `AddField` nullable/nova tabela + código escreve nos DOIS lugares + `RunPython` de backfill | Nada é removido |
| N+1 (**switch**) | Código passa a LER só do novo; escrita dupla pode cair | Coluna velha ainda existe |
| N+2 (**contract**) | `RemoveField`/drop da coluna velha | Só depois do switch em produção |

```python
# migrations/000X_backfill_novo_campo.py  # [RECEITA:R7 v1]
from django.db import migrations

def backfill(apps, schema_editor):
    Order = apps.get_model("pedidos", "Order")
    for o in Order.objects.filter(novo_campo__isnull=True).iterator():
        o.novo_campo = derivar(o)
        o.save(update_fields=["novo_campo"])

class Migration(migrations.Migration):
    dependencies = [("pedidos", "000X_add_novo_campo")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
```

Nunca deletar/renomear migration aplicada. Migration reversível sempre que possível.

## R8 — Task assíncrona interna (Huey)

```python
# config/huey.py  # [RECEITA:R8 v1]
import os
from huey import RedisHuey

huey = RedisHuey(url=os.environ["HUEY_REDIS_URL"])   # db exclusivo da célula
```

```python
from config.huey import huey

@huey.task(retries=5, retry_delay=30)
def notificar_ponte(matricula_id: int) -> None:
    """Toda task é idempotente — retry é comportamento normal, não exceção."""
    ...
```

Fila intra-célula = Huey. Comunicação ENTRE células = eventos (R3/R4), nunca uma
célula enfileirando task na outra.

## R9 — Seed idempotente

```python
# apps/core/management/commands/seed_esqueleto.py  # [RECEITA:R9 v1]
from django.core.management.base import BaseCommand
from apps.produtos.models import Product, Offer

class Command(BaseCommand):
    help = "Dados do esqueleto — idempotente: rodar 2× não duplica nada"

    def handle(self, *args, **opts):
        produto, _ = Product.objects.get_or_create(
            slug="curso-esqueleto",
            defaults={"name": "Curso Esqueleto", "price_cents": 990, "active": True},
        )
        Offer.objects.get_or_create(slug="curso-esqueleto", defaults={"product": produto, "price_cents": 990})
        self.stdout.write(self.style.SUCCESS("✅ seed do esqueleto"))
```

## R10 — Markers de smoke registrados

```ini
# pytest.ini  # [RECEITA:R10 v1]
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
markers =
    smoke_pix: caminho feliz do Pix (cross-smoke roda quando cartão é tocado)
    smoke_card: caminho feliz do cartão (cross-smoke roda quando Pix é tocado)
```

```python
@pytest.mark.smoke_pix
def test_caminho_feliz_pix(...): ...
```

---

## R11 — Novo site (domínio) no ar

Um site novo é DADO, não infraestrutura. Três passos, minutos:

**1. DNS (mantenedor, fora do repo):** no Cloudflare (plano gratuito), adicionar o
domínio, registro `A` → IP da VPS (proxy laranja LIGADO), SSL mode **Full**.
Modo B (sem Cloudflare): adicionar o domínio à lista `tls.domains` do router
`funil` em `infra/traefik/dynamic/plataforma.yml` (uma linha, PR de infra).
Ao mexer em qualquer arquivo de `infra/traefik/dynamic/`, nunca escreva as
chaves duplas de template, nem dentro de comentário: o Traefik renderiza o
texto cru antes do YAML, e uma chamada inválida recusa o arquivo inteiro e
derruba a borda pública com 404 em todos os hosts (armadilha 478).

**2. Cadastro (agente, célula catalogo):**

```python
# apps/sites/management/commands/criar_site.py  # [RECEITA:R11 v1]
from django.core.management.base import BaseCommand
from apps.sites.models import Site

class Command(BaseCommand):
    help = "Cadastra um site novo (idempotente por host)"

    def add_arguments(self, parser):
        parser.add_argument("host")
        parser.add_argument("name")

    def handle(self, host: str, name: str, **opts):
        site, criado = Site.objects.get_or_create(
            host=host.lower(), defaults={"name": name, "active": True}
        )
        self.stdout.write(self.style.SUCCESS(
            f"{'✅ criado' if criado else 'ℹ já existia'}: {site.host} → {site.id}"
        ))
```

Depois, as ofertas do site: criar `Offer` com o `site_id` novo (slug livre —
slugs são únicos POR site).

**3. Smoke (30 segundos):**

```bash
curl -sS https://<dominio-novo>/healthz                      # gateway ok
curl -sS https://<dominio-novo>/ | head -20                  # landing do site certo
# na VPS — host não cadastrado DEVE dar 404 (INV-P11):
curl -k -s -o /dev/null -w "%{http_code}\n" -H "Host: nao-cadastrado.teste" https://localhost/
```

---

## R12 — Página multilíngue (prefixo de idioma + catálogo key-major + `{% t %}`)

Lei: `docs/i18n/PLANO-I18N.md`, decisões D1–D9. Implementação de referência,
verificada e no ar desde 23/08/2026: `services/funil/` — **copie o padrão, não o
arquivo** (Lei 7).

> ⚠️ **A URL do idioma PADRÃO não tem prefixo** (D1 revisto em 25/08/2026 —
> `docs/decisoes/DECISAO-raiz-sem-prefixo-do-idioma-padrao.md`). No meshcraft o
> inglês é `/cadastro`, não `/en/cadastro`; `/en/…` é **404**. Consequência para
> quem escreve página: **nunca monte URL de idioma à mão.** Toda URL pública sai
> de `apps/i18n/idiomas.py::caminho_publico(cfg, codigo, caminho)` — no template,
> pela tag `{% url_i18n %}`; no HTML de SEO, pelo `dados_seo()`. O portão é `apps/i18n/validador.py`, com DUAS entradas: o teste
`test_validador_da_celula_real_passa` (protege o merge) e `AppConfig.ready()`
(protege a produção — **catálogo inválido ⇒ a célula não sobe**, D4 fail-closed).
Não existe `ci/i18n_check.py` na raiz: o portão i18n roda dentro do `make ci` da
célula.

**Antes de escrever a primeira linha, escolha o fluxo (D9):**

| O que você vai fazer | Fluxo | Regra dura |
|---|---|---|
| Página NOVA em site já multilíngue | **A** | Nasce com TODOS os idiomas do site **no mesmo PR** — a paridade exata força, e o formato key-major faz custar **1 arquivo** de catálogo, tenha o site 3 ou 15 idiomas |
| Idioma NOVO em site que já tem páginas | **B** | Idioma-**base** novo toca TODO `traducoes/*.yaml` da célula de uma vez. Lote pela lane `traducoes`, ou sequência com `_fonte: pendente` + `indexable: false` até completar |

> ✅ **Fluxo B — a lane funciona ponta a ponta desde 23/08/2026.** O portão
> (`ci/orcamento-de-mudanca.sh`) e a catraca (`ci/mergear.py`, `checar_labels()`)
> conhecem os dois a lane `traducoes` (docs/historico/RESOLVIDAS.md §5.11, PR #94). Um lote com
> >15 arquivos passa **se e somente se** todo caminho casar
> `services/<celula>/traducoes/...` — e a label `traducoes` existe no GitHub.
> Divisão de trabalho entre os dois, de propósito: a catraca confere o
> **caminho**; o **modo** (executável, symlink, submódulo) fica com as muralhas,
> porque a API de PR do GitHub não devolve modo. Dois testes-guarda leem o
> próprio `.sh` e reprovam se as duas cópias da regra divergirem.

### A — Página nova (todos os idiomas de uma vez)

**1. Template** em `templates/<celula>/<pagina>.html` — `{% extends %}` na
LINHA 1, sempre (LICOES do funil: até um `{% load %}` antes derruba o parse):

```html
{% extends "base_mobile.html" %}
{% load t %}
{% load url_i18n %}
<!-- templates/<celula>/<pagina>.html  [RECEITA:R12 v1]
     Todo texto visível sai do catálogo. Em COMENTÁRIO de template, cite a tag
     url crua do Django pelo NOME — nunca escreva a sintaxe dela aqui: o lint do
     validador varre o arquivo inteiro por regex e reprova o comentário. -->
{% block titulo %}{% t "<pagina>.titulo" %}{% endblock %}
{% block head_extra %}
  <meta name="description" content="{% t "<pagina>.meta_descricao" %}">
  <meta property="og:title" content="{% t "<pagina>.titulo" %}">
  <meta property="og:description" content="{% t "<pagina>.meta_descricao" %}">
{% endblock %}
{% block conteudo %}
{{ i18n_js|json_script:"i18n-data" }}
<div class="card" x-data="ilha()" x-init="init()">
  <h1>{% t "<pagina>.titulo_pagina" %}</h1>
  <form method="post" action="{% url_i18n '<pagina>' %}">
    <button class="cta" type="submit"><span x-text="i18n.enviando">{% t "<pagina>.js.enviar" %}</span></button>
  </form>
</div>
{% endblock %}
```

Regras que o portão IMPÕE neste arquivo (não são estilo):

- **`{% t %}` com chave LITERAL entre aspas.** Chave dinâmica (`{% t variavel %}`)
  cega a análise estática e reprova.
- **`{% url_i18n %}` em TODO link/action interno.** A tag `url` crua do Django
  em template que usa `{% t %}` é **FAIL** — ela não gera o prefixo. Desde o D1
  revisto (25/08/2026) esse erro ficou **mais traiçoeiro, não menos**: o link cru
  *funciona* na versão do idioma padrão — que é justamente a que você abre para
  conferir — e joga quem está em `/pt-br/` de volta para o inglês, sem erro
  nenhum na tela. Antes ele quebrava igual em todos os idiomas e aparecia na
  primeira olhada. Link para OUTRA célula continua cru e monolíngue até o D6
  entrar no Traefik.
- **`title`, meta description e og:\* saem do catálogo** como qualquer texto —
  `lang`, `dir`, canonical, hreflang, `x-default`, `og:locale`, `robots
  noindex` e o seletor de idiomas o `base_mobile.html` já emite sozinho, dos
  idiomas do site (`apps/i18n/idiomas.py` → `dados_seo()`, que o middleware põe
  em `request.i18n_seo`). Não escreva nenhum deles à mão.
- **Ilha Alpine**: as strings que o JS troca em runtime moram na subárvore
  `<pagina>.js.*`, emitidas com `|json_script` e lidas no `init()`. **Proibido
  catálogo de tradução em JS.**

**2. Catálogo** `traducoes/<pagina>.yaml` — 1 arquivo, todos os idiomas lado a
lado. O nome do arquivo (`[a-z0-9_]+`) é o PRIMEIRO segmento de toda chave:

```yaml
# traducoes/<pagina>.yaml  # [RECEITA:R12 v1]
titulo:
  # Comentário YAML é o contexto que o tradutor-IA lê — use.
  _fonte: "9741dd"                       # sha256(valor en)[:6]
  en: "Sign up — Meshcraft"
  pt-br: "Cadastro — Meshcraft"
  es: "Registro — Meshcraft"

itens:
  _fonte: "a1b2c3"                       # plural: categorias CLDR DO IDIOMA
  en:    { one: "{quantidade} item", other: "{quantidade} items" }
  pt-br: { one: "{quantidade} item", many: "{quantidade} de itens", other: "{quantidade} itens" }

aviso.html:                              # única forma que admite markup
  _fonte: "d4e5f6"
  en: "See <strong>{nome}</strong>"

js:                                      # subárvore da ilha Alpine
  enviar:
    _fonte: "0f1e2d"
    en: "Send"
```

Formato, ponto a ponto (tudo verificado em `apps/i18n/catalogo.py`):

- **Chave semântica, imutável**: nomeia o papel (`cadastro.cta_primaria`), nunca
  o texto. Mudança de copy NÃO renomeia chave. Duplicar é melhor que acoplar.
- **Toda folha é string entre aspas** — o loader estrito recusa folha não-string
  (`12:30` viraria 750, `no` viraria `False`), chave duplicada, âncora, alias e
  tag explícita.
- **Placeholders `{nome_simples}`** em `[a-z_][a-z0-9_]*` — sem ponto, sem
  índice, sem `!r`, sem `:>10`. O conjunto de placeholders tem de ser IDÊNTICO
  em todos os idiomas da chave.
- **Meta permitida hoje: `_fonte`, `_juridico` e `_revisado_humano`** (os dois
  últimos andam juntos — D8.2, ver abaixo). Qualquer outra chave com `_`
  reprova como meta desconhecida. `_juridico` vai **entre aspas**
  (`_juridico: "true"`): toda folha do catálogo é `str`, então o booleano nu
  morre antes, na regra do loader.
- **Sufixo `.html` só na folha**, com whitelist (`a abbr b br code em i small
  span strong`); handler `on*=` e `javascript:` reprovam. Todo o resto é
  escapado por padrão.

**3. View e rota.** O urlconf da célula **não conhece prefixo de idioma** — o
resolver decapa o prefixo dos idiomas **não-padrão** (`/pt-br`, `/es`) de
`request.path_info` antes da resolução; o idioma padrão chega já sem prefixo:

```python
# config/urls.py  # [RECEITA:R12 v1]
path("<pagina>", <pagina>, name="<pagina>"),   # sem prefixo: o resolver já decapou
```

⚠️ **O nome da rota não pode colidir com um código de idioma.** Com o padrão na
raiz nua, o primeiro segmento é ambíguo (`/es` = espanhol ou página chamada
`es`?) e **o idioma vence sempre** — uma rota chamada `es` ou `pt-br` fica
inalcançável **em silêncio**. `tests/test_d6_roteamento.py` varre o urlconf e
reprova a colisão antes do merge; se ele ficar vermelho, renomeie a rota, não o
teste.

```python
# apps/core/views.py  # [RECEITA:R12 v1]
def <pagina>(request):
    if getattr(request, "idioma", None) is None:
        raise Http404("página só existe em site multilíngue")          # decida EXPLICITAMENTE
    contexto = {"i18n_js": js_da_pagina("<pagina>", request.idioma)}
    return render(request, "<celula>/<pagina>.html", contexto)
```

Site monolíngue (sem `languages` no catálogo) nunca tem `request.idioma`:
decida — **404** (como `cadastro`) ou **template próprio separado** (como
`landing`/`landing_i18n`).
Nunca um `if` de idioma dentro de um template só: é o que quebra o golden
byte-idêntico da landing.

**4. Sitemap**: acrescente o caminho a `PAGINAS_PUBLICAS` em `apps/core/views.py`
(hoje `("/", "/cadastro")`). Sem isso a página nasce fora do sitemap.

**5. Testes mínimos** (molde real: `tests/test_cadastro.py`) — parametrizados
pelos idiomas:

```python
# O caminho de cada idioma vem do MESMO lugar que o código usa — escrever
# f"/{idioma}/<pagina>" no teste faria o caso do idioma PADRÃO bater em 404.
@pytest.mark.parametrize("idioma", ("en", "pt-br", "es"))
def test_pagina_nos_3_idiomas(client, rede, idioma):
    caminho = caminho_publico(CFG_MESH, idioma, "/<pagina>")        # nu no padrão
    resp = client.get(caminho, HTTP_HOST=HOST_MESH)                 # Host SEMPRE (§4.6)
    conteudo = resp.content.decode()
    assert f'<html lang="{TAGS[idioma]}" dir="ltr">' in conteudo
    assert f"<title>{escape(t('<pagina>.titulo', idioma))}</title>" in conteudo
    assert f'action="{caminho}"' in conteudo

def test_pseudo_locale_sem_texto_hardcoded(catalogo_pseudo):        # D8.4
    html = get_template("<celula>/<pagina>.html").render({...}, request=_request_pseudo("/qps/<pagina>"))
    assert texto_hardcoded(html) == []
```

O teste de pseudo-locale é o **único detector mecânico de string fora do
catálogo** — página nova sem ele nasce sem rede. Valor esperado vem SEMPRE do
próprio `t()`/`gettext`, nunca de copy colado no teste (erro de formulário
localizado se afirma com `override()` + `gettext`).

### B — Idioma novo em site que já existe

**1. Primeiro a CÉLULA, depois o DADO — nesta ordem.** Desde a fase 4 (PRs
#104/#106/#107) **não existe registro local de idiomas**: o interim
`sites_i18n.yaml` foi apagado, e quem declara idioma de site é o catálogo.
São dois lugares, e trocar a ordem publica URL quebrada.

**1a — a célula tem de saber renderizar o idioma**, em
`services/<celula>/apps/i18n/catalogo.py`:

```python
IDIOMAS_BASE = ("en", "pt-br", "es")   # idioma-BASE: paridade EXATA no catálogo
VARIANTES: "dict[str, str]" = {}       # variante → base, ex.: {"pt-pt": "pt-br"}
```

Idioma que o catálogo declare para o site e não esteja em nenhum dos dois é
**ignorado** por `idiomas.idiomas_do_site()` (com `logger.error` nomeando o
host): a URL prefixada simplesmente não existe. Fazer o inverso — dado antes de
tradução — seria publicar uma URL prefixada servindo inglês, exatamente o padrão
que o D5 existe para evitar.

**1b — o idioma do site é DADO**, declarado em `infra/sites.json` e convergido
para a produção pelo `deploy-infra`. A lei é `contracts/catalogo.openapi.yaml`,
schema `Site`:

```json
{ "host": "meshcraft.top",
  "default_language": "en",
  "languages": [ { "code": "en" },
                 { "code": "pt-br" },
                 { "code": "es", "indexable": false } ] }
```

Site **sem os dois campos** é monolíngue — é assim que todo site que não declara
idioma segue com o comportamento de sempre.

Só o que varia por site virou campo. O resto do registro antigo não sumiu: virou
derivação ou constante da célula, porque é propriedade do IDIOMA, não do site
(escrever `dir` por site seria N lugares para escrever a mesma verdade, e N para
escrevê-la errado):

| campo do interim morto | onde a verdade mora agora |
|---|---|
| `tag` (`pt-br` → `pt-BR`) | derivado: `idiomas.tag_bcp47(codigo)` |
| `dir` (`ltr`/`rtl`) | derivado: `idiomas.direcao(codigo)`, tabela `IDIOMAS_RTL` |
| `base` da variante | `catalogo.VARIANTES` — política de tradução da célula |
| `indexavel` | contrato: `languages[].indexable`, default `true` |

Fail-closed nos dois lados, com regras DIFERENTES — e quem manda é a mais
apertada, que é a de quem grava:

- **No `deploy-infra`, antes de gravar** — `infra/sincronizar_sites.py` →
  `normalizar_idiomas`, cópia consciente do mesmo nome em
  `services/catalogo/apps/sites/models.py` (armadilhas/078: o script injetado
  não pode importar da imagem; a deriva entre as cópias tem teste-guarda em
  `ci/tests/test_sincronizar_sites_tolerante.py`). Ali o código tem de casar
  `^[a-z]{2}(-[a-z]{2})?$` — **só isso**.
  `en`, `pt-br`, `es` passam; `es-419` e `zh-hant` **não** (o run fica vermelho,
  o dado não entra). Também reprovam: código duplicado, `indexable`
  não-booleano, `languages` sem `default_language`, `default_language` sem
  `languages`, e `default_language` fora dos idiomas declarados.
- **Na célula, ao servir** (`apps/i18n/idiomas.py` → `RE_CODIGO`): a forma
  aceita é mais larga (`[a-z]{2,3}` com região de 2–8 alfanuméricos), porque é
  ela que decide o 404 da URL — `/pt-BR/` e `/pt_br/` são **404 por decisão**,
  nunca redirect e nunca fallback.

E dado que a célula não sabe servir **degrada para monolíngue com ERROR, nunca
para um idioma escolhido por conta**: `default_language` fora dos idiomas
servíveis, ou que seja variante, derruba o site inteiro para monolíngue;
`indexable` não-booleano vira `noindex` (indexar por engano é o erro caro; o
contrário reverte).

**2. Entenda o que você acabou de disparar.** Idioma em **`IDIOMAS_BASE`** é
idioma-BASE: a paridade exata passa a exigi-lo em **toda chave de todo
`traducoes/*.yaml` da célula** — não só nas páginas novas. Idioma em
**`VARIANTES`** é variante: overlay esparso, ausência herda (válido), presença
tem de DIFERIR da base (overlay idêntico reprova: "remova, a herança já cobre").
Máximo 1 nível — a base de uma variante tem de ser idioma-base, e o
`default_language` do site nunca pode ser variante.

**3. Complete o eixo** em cada `traducoes/*.yaml`, com o `_fonte` correto por
chave. As duas saídas legítimas quando não dá para traduzir tudo no mesmo PR:

- **`_fonte: pendente` na chave** — isenta aquela chave da paridade e declara a
  degradação; em runtime cai pela cadeia (variante → base → en) com **ERROR +
  contador**. Degradação declarável, nunca inferível.
- **`indexable: false`** no `languages[]` do site — mantém o idioma fora do
  hreflang, do `x-default` e do sitemap enquanto está incompleto, e emite
  `robots noindex`.

**4. Nasça `indexable: false`** (D5 — "3 idiomas bons antes do 4º"): idioma novo
em domínio novo com tradução de agente é o padrão que classificador de spam
procura. Indexar depois custa flipar um dado no `infra/sites.json` — não um
deploy de código. Foi assim que o `es` nasceu.

**5. Lote**: label `traducoes` no PR (`gh pr edit <N> --add-label traducoes`) —
o `ci/orcamento-de-mudanca.sh` deixa passar >15 arquivos **somente se** 100% do
diff casar `services/<celula>/traducoes/...` e **todo arquivo entrar como dado**
(modo `100644` ou remoção `000000`; executável, symlink e submódulo reprovam).
Um único arquivo fora dessa árvore derruba a lane inteira de volta ao teto de 15.
**E releia o aviso da catraca lá em cima antes de montar o lote.**

### O contrato do `_fonte` (D4) — e a regra anti-burla

`_fonte` são os **6 primeiros hex do sha256 do valor `en`** no momento em que a
tradução foi feita. É o detector de obsolescência: `_fonte != hash(en)` ⇒ o
inglês mudou e as traduções daquela chave estão velhas ⇒ **FAIL**.

```bash
# hash de um valor simples (a fonte da verdade, plural incluso, é
# apps/i18n/catalogo.py::hash_da_fonte — plural entra em forma canônica)
python -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest()[:6])" "Sign up — Meshcraft"
```

**Regra anti-burla (o portão de verdade):** se o `_fonte` de uma chave **mudou
no diff** contra `origin/main`, os valores não-base daquela chave têm de ter
mudado também, **OU** estar `pendente`, **OU** a linha carregar o marcador
literal `# revisado-sem-alteracao` (o caso legítimo: typo no inglês que não
altera as traduções — auditável, greppável, contável).

> **Recalcular o hash sem traduzir é violação, não atalho.** É a primeira ideia
> de um agente instruído a "deixar o CI verde", e é exatamente o que esta regra
> existe para matar. Se você não vai traduzir agora, escreva `pendente`.

O diff é medido com `git` contra `${BASE_REF:-origin/main}`; **diff
incalculável ⇒ ERROR**, nunca skip. No boot a regra não roda (container não tem
git nem `origin/main`) — ela é do CI, por construção do checkout `fetch-depth: 0`.

### Checklist do validador — rode ANTES do push

```bash
cd services/<celula> && python -m pytest -q     # inclui o validador (entrada a)
make -C services/<celula> ci                    # lint + type + testes + freeze
bash ci/orcamento-de-mudanca.sh                 # orçamento / lane traducoes
```

O que ele reprova, item a item (se um destes ficar vermelho, é isto que ele está
medindo):

1. **Paridade exata** entre idiomas-base: falta E sobra reprovam (chave de
   idioma fora de `IDIOMAS_BASE`/`VARIANTES` dentro de um MessageSpec = FAIL).
2. **Template ↔ catálogo nas DUAS direções**: chave usada e não definida, e
   chave definida e não usada em nenhum template. Só `*.js.*` é isenta da
   segunda (a ilha consome por `json_script`).
3. **Placeholders idênticos** entre idiomas e **restritos** (sem `{a.b}`,
   `{a[0]}`, `{a!r}`, `{a:>10}`).
4. **Plural CLDR do idioma**, consultado no `babel` pinado — exatamente as
   categorias daquele idioma, nunca lista à mão.
5. **Glossário de não-traduzir**: se o termo protegido aparece no `en`, tem de
   aparecer **literal** em toda tradução daquela chave. Os termos vêm de
   `catalogo.GLOSSARIO` — **constante da CÉLULA**, não dado de site: quem
   precisa da regra é quem escreve a tradução, e ela não muda de site para site.
6. **Overlay de variante**: presente sem a base reprova; idêntico à base
   reprova; ausência herda.
7. **Escape e `.html`**: whitelist de tags, nada de `on*=` nem `javascript:`;
   todo o resto escapado por padrão.
8. **YAML estrito**: chave duplicada, âncora, alias, tag explícita, folha
   não-string, chave não-string, mapeamento vazio, segmento fora de
   `[a-z0-9_]+`.
9. **`{% t %}` literal-only** e **tag `url` crua proibida** em template i18n.
10. **`_fonte`** presente, válido (6 hex ou `pendente`), igual a `hash(en)`, e a
    regra anti-burla acima.

Estados ([INV-CI01]): **PASS** mediu e está certo · **FAIL** mediu e achou
violação (conserte o catálogo) · **ERROR** não conseguiu medir (conserte o
ambiente — jamais leia como "quase passou").

### O que a máquina NÃO protege (D8) — sua responsabilidade, agente

Os portões acima verificam **integridade**. Nenhum verifica se a tradução está
**boa**. Numa página de cadastro de curso pago, copy é o produto:

- **Namespace jurídico** (termos de uso, privacidade, consentimento) **exige
  revisão humana antes de publicar** — e desde 23/08/2026 o marcador do D8.2
  **existe e tem dente**. Marque a chave com `_juridico: "true"` e declare a
  revisão em `_revisado_humano`, um mapa **idioma → "Quem revisou AAAA-MM-DD"**
  com uma entrada **por idioma** (revisar o inglês não valida o espanhol); o
  `_fonte` não pode estar `pendente`. Sem isso é FAIL no CI **e o boot recusa
  subir**. A declaração **expira**: se o texto daquele idioma mudar no diff,
  ela tem de mudar junto. Você não inventa o nome que vai ali: **registre a
  pendência com `precisa_do_dono: true` e pare nesta sessão. A pergunta vai ao
  mantenedor, e a resposta fica registrada**.
  ⛔ A outra guarda do D8.3, a **retrotradução**, continua NÃO implementada:
  depende de modelo externo (chave de API, custo) e é decisão do mantenedor —
  não escreva stub que finja fazê-la.
- **Nunca concatene frases** para montar um período — ordem de palavras e
  gênero mudam por idioma. Uma frase = uma chave.
- **Nunca traduza termo do glossário** (Meshcraft, Roblox, Roblox Studio, nomes
  de produto). O portão pega o caso fácil; o julgamento é seu.
- **`pt-br` é a janela de auditoria do mantenedor** — ele não lê inglês.
  Tradução **fiel ao sentido, nunca adaptação criativa**: se o pt-br "melhorar"
  o inglês, a única auditoria interna que existe deixa de funcionar. Risco
  estrutural ABERTO (D8.5) — só humano nativo ou conversão medida resolve.
- **Texto dentro de imagem é dívida**: um asset por idioma. Texto fica em HTML.

### CSS de página multilíngue

Propriedades **lógicas** em todo CSS novo: `margin-inline-start`,
`padding-inline-end`, `inset-inline`, `text-align: start/end`. **Nunca
`left`/`right`** — a direção vem do `dir` que `idiomas.direcao()` deriva do
código do idioma, e o dia do primeiro RTL vira uma linha nova em `IDIOMAS_BASE`
em vez de varredura de folha de estilo (a tabela `IDIOMAS_RTL` já responde
`rtl` para `ar`/`he`/`fa`/…, sem dado novo de site).

### Armadilhas já pagas (não redescubra)

`ARMADILHAS.md` **§4.10** (`path_info` vs `path` — o resolver reescreve
`path_info`; `request.path` segue completo e é dele que sai o canonical) ·
**§4.5** (isenção do `/healthz`; rota de máquina nunca se localiza — `/healthz`,
`/static/`, `/sitemap.xml`, `/api/**`, `/webhooks/**`) · **§4.6** e **§4.7**
(Host válido em todo teste, mock por endpoint, cache de sites limpo entre
testes) · **§4.14** (tags coladas quando a saída tem de ficar byte-idêntica) ·
**§5.1** (orçamento) · **§5.11** (a lane e a catraca) · **§6.1.1** (evidência
vermelho→verde por **patch**, nunca `git stash` — em lote o pop devolve o stash
de outro agente).

`services/funil/LICOES.md`: `{% extends %}` é a primeira tag, sempre · o
autoescape transforma `&` em `&amp;` (a asserção espera o escapado) · **o lint
lê os COMENTÁRIOS do template** — comentário que escreve a sintaxe proibida
derruba o `django.setup()` inteiro · `hreflang="es"` continua na **âncora** do
seletor mesmo com `noindex`; a asserção negativa mira
`<link rel="alternate" hreflang="es"`, nunca o atributo solto.

---

## R13 — Mexer na régua de uma meta (curva, datas, alvo)

A régua de uma meta mora no **cartão** (`painel/cartoes/<meta>.json`), nunca na
tela e nunca no código: quem lê a curva é uma função só (`placar.esperado_em`),
e por isso o placar, a meta do mês e o calendário nunca discordam
(`docs/decisoes/DECISAO-o-calendario-do-ciclo.md` §5). Mudar a régua é editar um
arquivo de dados, e o resto segue junto. Menos uma coisa, e é nela que esta
receita existe para doer: **a prosa em português que repete a curva.**

```json
// painel/cartoes/compras-no-ciclo.json  // [RECEITA:R13 v1]
"semanas": [ { "n": 0, "de": "2026-09-14", "ate": "2026-09-18", "alvo": 0, "rotulo": "Preparação" } ],
"versao": 5,
"desde": "2026-09-17",
"_por_que": "... a história anterior INTACTA, e o registro novo acrescentado no fim."
```

**O checklist, na ordem:**

1. **O dado primeiro.** Só o cartão muda. Se a mudança pedir uma linha de Python,
   a régua vazou do cartão para o código: pare e reporte, porque isso é outra
   tarefa e outra decisão.
2. **A soma continua fechando.** A soma dos alvos tem de dar exatamente `alvo`
   menos `partida`. O validador (`placar._validar_as_semanas`) reprova o cartão
   quando não dá, e a mensagem dele diz o conserto.
3. **A última faixa não passa de `ate`.** Faixa depois do prazo é ficção, e o
   validador NÃO vê isso. Quando o prazo é do mantenedor, quem encolhe é a faixa.
4. **`versao` sobe e `desde` recebe o dia da mudança.** É o que deixa a tela
   dizer de quando é a régua que ela está mostrando.
5. **`_por_que` cresce no fim, nunca por cima.** A história de como a meta virou
   o que é vale mais que a última versão dela.
6. **Cace a prosa que repete a curva.** O passo que ninguém lembra e o único que
   envelhece em silêncio: `grep -rn "primeiras semanas|semana de|em zero"` na
   tela, na lei e no próprio `_por_que`. Todo número da curva escrito por extenso
   em português é uma cópia, e cópia não muda por edição de dado nenhuma.
7. **Deixe um guarda no lugar da sua memória.** A frase da tela que repete um
   número do cartão ganha um teste que lê o cartão, conta, e exige a frase certa
   (exemplo vivo: `test_a_prosa_da_tela_conta_as_mesmas_semanas_em_zero_que_o_cartao`).
   Frase procurada por teste fica INTEIRA numa linha do template (armadilhas/394).
8. **Prove na tela renderizada, não no cartão.** Entre o dado e a página existe
   um template, e o teste que abre a tela e lê as datas dela é o único que mede
   o que o mantenedor enxerga.

**Por que esta receita existe:** a curva de `compras-no-ciclo` mudou duas vezes
em duas semanas (04/09/2026 e 17/09/2026) e nas duas o texto que a repetia em
português ficou para trás. Na primeira, a tela passou treze dias dizendo "as
três primeiras semanas pedem zero venda" com o cartão dizendo cinco, sem nenhum
portão ficar vermelho: prosa não é dado, e nada a media. O passo 7 é a resposta,
e `armadilhas/480` é o relato.

---

## R14 — Abrir PR que toca caminho CODEOWNERS

Alguns caminhos não são do agente: mudança neles só integra com a palavra
escrita do mantenedor na descrição do PR. A lista vive em `.github/CODEOWNERS`,
e hoje ela cobre `contracts/`, `services/pagamentos/`, `services/checkout/`,
`infra/`, `ci/`, `.github/`, `.githooks/`, os arquivos de lei da raiz
(`CONSTITUICAO.md`, `CAMINHO-DOURADO.md`, `INVARIANTES.md`, `RITOS.md`, este arquivo) e
`docs/decisoes/`. **Confira no arquivo, não nesta frase:** lista copiada
envelhece, e é por isso que o portão lê o original (a lição é a do R13 e da
armadilhas/480).

**1. O mandato é UMA LINHA, com os caminhos como palavras soltas.**

```markdown
<!-- na descrição do PR  [RECEITA:R14 v1] -->
Mandato-do-mantenedor: <o pedido dele, nas palavras dele> CAMINHO-DOURADO.md ci/mergear.py
```

Três regras, e as três vêm do leitor, não do gosto de ninguém. Quem julga é
`checar_mandato`, em `ci/mergear.py`:

```python
mandato = re.search(r"^Mandato-do-mantenedor: (.{20,})$", corpo, re.MULTILINE)
...
any(alvo in mandato.group(1).split() for alvo in (padrao, caminho))
```

- A regex termina em `$` com `re.MULTILINE`, então ela lê **a primeira linha e
  para**. Mandato escrito em parágrafo deixa os caminhos nas linhas de baixo, e
  para o portão eles não existem.
- A comparação é `.split()` com igualdade exata. **Vírgula depois do caminho
  derruba o pouso:** `CAMINHO-DOURADO.md,` é um token com vírgula colada, e ele
  nunca é igual a `CAMINHO-DOURADO.md`. Separe por espaço, e só por espaço.
- O que conta como caminho são **duas formas, e só elas**: o padrão escrito em
  `.github/CODEOWNERS`, com a barra final (`ci/`, `services/pagamentos/`), ou o
  caminho exato do arquivo que você tocou
  (`ci/tests/test_chaves_do_gateway_no_deploy.py`). **Prefixo pela metade
  reprova:** `ci/tests` é uma linha só, palavra solta e sem vírgula, e mesmo
  assim não é nenhuma das duas. Quase pulou o PR #1686.

E o autor do PR precisa constar como dono do caminho em `.github/CODEOWNERS`,
senão o mandato não é aceito venha de onde vier.

**2. Antes de dizer pronto, confira o julgamento.**

```bash
python ci/mergear.py <N> --conferir
```

Somente leitura, não integra nada, e imprime a tabela inteira com o motivo de
cada linha. É o único gesto que separa "o PR está esperando a vez" de "o PR foi
pulado". A varredura do `pouso.yml` descarta o PR reprovado no mandato com um
`continue` mudo: ele some do log, os outros continuam sendo julgados na tela, e
a espera fica idêntica ao progresso (armadilhas/482). O PR #1684 ficou 19
minutos assim, verde nos 8 checks e invisível, por causa de uma vírgula.

**3. Se reprovou, o conserto é reescrever a linha.** O FAIL diz
`falta mandato do dono para <caminho>`. Reescreva a descrição com a linha do
passo 1 e rode o `--conferir` de novo. Nada de novo commit: o portão lê a
descrição do PR, não o diff.

**Por que esta receita existe:** o mandato é a única lei desta casa que se
escreve em prosa e é lida por máquina. Escrever para gente (parágrafo, lista
com vírgulas) é o gesto natural, e é exatamente o gesto que o leitor recusa em
silêncio. `armadilhas/481` é o relato.

## §4 — Anti-padrões com resposta pronta

| A tentação | A resposta (sem pensar duas vezes) |
|---|---|
| "Vou importar esse util da outra célula" | R2 (API) — ou issue `arquitetura:` propondo pacote versionado |
| "Leio o banco dela só pra conferir" | API dela (R2) ou evento (R4). O Postgres vai negar mesmo. |
| "O teste está errado, ajusto o assert" | Identifique a propriedade e o guarda sucessor. Mostre o caso adversarial que ele rejeita; a revisão protegida confirma a pertinência. Enfraquecer a asserção para obter verde reduz a proteção. |
| "Crio um base.html compartilhado" | Cada célula tem o seu (Lei 7). Copie o padrão, não o arquivo. |
| "Só dessa vez o contrato muda junto" | A cerca exige “Mudar contrato”, com o mantenedor. |
| "Float facilita o cálculo do desconto" | `amount_cents` inteiro. Sempre. |
| "Coloco um retry nesse POST" | Só com a MESMA `X-Idempotency-Key` (R2). |
| "Resolvo a corrida com um sleep" | Poll de status do servidor (R6) ou lock/unicidade (R4). |
| "Um segundo commit gigante no fim" | Valide o incremento coeso e embarque sua prova pelo rito da entrega. |
| "Host desconhecido? Sirvo o site principal" | 404 (INV-P11). Site padrão silencioso contamina os testes de todos os sites. |

## §5: Validar, entregar e consultar no PowerShell

Roteiro dos agentes dentro da bancada aberta por “Abrir e retomar uma sessão”. O mantenedor recebe
resultado e prova; os comandos abaixo são trabalho da sessão responsável.

**1. Conferir o trabalho.** Rode os testes dos alvos do brief e guarde comando,
saída e revisão. `--sem-container` deixa o baseline não medido e não dispensa testes.
Confira `git status --short` e o diff, inclusive alterações sem commit, contra
ALVOS e ORÇAMENTO. Remova debug, código morto e pendências de implementação.
Invariante tocado exige vermelho→verde e prova dos guardas conforme a ficha.
Prepare o handoff com ramo, SHA, provas, pendências e título convencional.
Caminho com dono exige o mandato no formato da [R14](#r14--abrir-pr-que-toca-caminho-codeowners).

**2. Abrir o PR com validação e recibo no mesmo ramo.** Quem executa define `$alvos`
como lista dos caminhos autorizados no brief e `$preparo` como caminho absoluto
da pasta local de preparação, fora dos arquivos entregues. `$tarefaFila` contém
a TAR real vinculada a este trabalho por “Pegar e registrar trabalho na fila”; sessões novas exigem esse
vínculo antes de publicar. Prepare na pasta
`mensagem.txt` (primeira linha: título do PR; última linha:
`Co-Authored-By: Codex <noreply@openai.com>`), `corpo.md`, `detalhe.txt` e
`validacao.json` conforme [painel/LEIA-ME.md](painel/LEIA-ME.md#como-registrar-um-acontecimento-o-gesto-de-toda-sessão).

```powershell
# [RECEITA:ENTREGA v1]
if (-not $preparo -or -not $alvos -or $tarefaFila -notmatch '^TAR-\d{3,}$') { throw 'PAROU POR SEGURANÇA: defina a pasta, os alvos do brief e a TAR real desta entrega.' }
$alterados = @()
foreach ($consultaGit in @(@('diff', '--name-only', 'origin/main...HEAD'), @('diff', '--name-only', 'HEAD'), @('ls-files', '--others', '--exclude-standard'))) {
    $alterados += git @consultaGit
    if ($LASTEXITCODE -ne 0) { throw 'PAROU POR SEGURANÇA: não foi possível medir os arquivos; confira a bancada e origin/main.' }
}
$alterados = @($alterados | Sort-Object -Unique)
$foraDoBrief = @($alterados | Where-Object { $_ -notin $alvos })
if ($foraDoBrief.Count) { throw "PAROU POR SEGURANÇA: arquivos fora do brief: $($foraDoBrief -join ', '). Preserve-os e pare nesta sessão." }
$codigoEntregue = @($alterados | Where-Object { $_ -notmatch '^(painel|fila)/' })
if ($codigoEntregue.Count -gt 15) { throw 'PAROU POR SEGURANÇA: orçamento de 15 arquivos excedido; pare nesta sessão e divida a entrega.' }
$titulo = Get-Content -LiteralPath (Join-Path $preparo 'mensagem.txt') -Encoding UTF8 -TotalCount 1 -ErrorAction Stop
python ci/pr.py --titulo $titulo --mensagem-arquivo (Join-Path $preparo 'mensagem.txt') --corpo-arquivo (Join-Path $preparo 'corpo.md') --arquivos $alvos --detalhe-arquivo (Join-Path $preparo 'detalhe.txt') --validacao-arquivo (Join-Path $preparo 'validacao.json') --tarefa $tarefaFila
if ($LASTEXITCODE -ne 0) { throw 'PAROU POR SEGURANÇA: leia o diagnóstico, preserve a bancada e retome com --continuar após corrigir a causa.' }
```

O rito embarca os eventos da tarefa. Na retomada, use os mesmos argumentos e
`--continuar`;
não refaça reserva ou recibo. Inclua em `$alvos` os caminhos exatos do recibo e
dos eventos gerados nesta tarefa ao retomar; outras alterações continuam fora
do mandato. Confira `git diff --name-only origin/main...HEAD`,
inclusive recibo e eventos. O rito valida a revisão isolada e o SHA final.
PR aberto e validação local não comprovam integração nem publicação.

**3. Consultar uma vez, a partir do ramo da bancada.** A sessão responsável
consulta sem laço. A integração é automática pelos checks no SHA atual
(“Integrar, publicar e aceitar”). A consulta composta não promete resposta em cinco segundos.

```powershell
# [RECEITA:ENTREGA v1]
$jsonPr = gh pr view --json number,state,headRefOid,mergeCommit,url
if ($LASTEXITCODE -ne 0) { throw 'PAROU POR SEGURANÇA: confira ramo, autenticação e acesso ao GitHub.' }
try { $pr = $jsonPr | ConvertFrom-Json -ErrorAction Stop }
catch { throw 'PAROU POR SEGURANÇA: o GitHub não devolveu JSON válido; confira a consulta.' }
if ("$($pr.number)" -notmatch '^\d+$') { throw 'PAROU POR SEGURANÇA: o GitHub não identificou um PR; confira o ramo.' }
$pr | Select-Object number,state,headRefOid,mergeCommit,url
switch ($pr.state) {
    'MERGED' {
        python ci/esperar.py --entrega $pr.number
        $codigoConsulta = $LASTEXITCODE
        if ($codigoConsulta -eq 2) { throw 'PAROU POR SEGURANÇA: a consulta falhou; leia acao, sem declarar publicação.' }
        if ($codigoConsulta -notin @(0, 1)) { throw 'PAROU POR SEGURANÇA: saída inesperada; confira o instrumento.' }
    }
    'OPEN' { Write-Output 'PR aberto: integração não comprovada. Use a conferência da R14 para diagnóstico.' }
    'CLOSED' { Write-Output 'PR encerrado sem integrar: esta entrega não foi publicada.' }
    default { throw 'PAROU POR SEGURANÇA: estado desconhecido; confira a resposta do GitHub.' }
}
```

Use `--entrega` só após `MERGED`: em PR aberto, o leitor ainda cobra atestado e
etiqueta removidos pelo rito de integração vigente. Para diagnosticar PR aberto, a R14 usa
`python ci/mergear.py $pr.number --conferir`, somente leitura.

| JSON de `--entrega` | Prova e próxima ação |
|---|---|
| `PUBLICADO`, exit 0 | Jobs exigidos comprovados; guarde SHAs e links, confira o aceite funcional na borda |
| `SEM_PUBLICACAO`, exit 0 | Integrado; este diff não dispara publicação |
| `AGUARDANDO_PUBLICACAO`, exit 1 | Publicação não comprovada; leia `acao` e os runs |
| `FALHA_PUBLICACAO`, exit 1 | Falha medida na publicação; leia `acao` e evidência antes de corrigir |
| `ERROR`, exit 2 | Instrumento indisponível; corrija a consulta, sem atribuir sucesso ou falha ao site |

**4. Comprovar a entrega pública.** Quando o pedido exige deploy, a entrega só
termina com o texto ou aceite funcional conferido na URL pública e com o SHA
publicado ligado à execução do deploy. Registre os instantes UTC de abertura,
edição, PR, merge, deploy e verificação pública, além das falhas e do tempo
gasto em cada etapa. PR aberto não encerra esse pedido: a sessão responsável
acompanha a entrega até a conferência pública.
