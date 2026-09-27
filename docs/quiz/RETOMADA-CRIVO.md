# Retomada do quiz Crivo | roadmap, frentes e checklist vivo

Cole este arquivo inteiro numa sessão nova do Claude Code aberta no repositório
abundanciabr/sitesdoreino. Ele é a rota de continuação e o arquivo de retomada
ao mesmo tempo. Sempre PT-BR. Estado medido em 26/09/2026 por volta das 21h UTC
pela sessão de rota. O estado vivo sai dos comandos da seção "Medir agora",
nunca das caixinhas. Preparar esta rota não executou nada: tudo abaixo ainda
está por fazer, salvo o que a seção "O que já está pronto" lista.

## Resultado e destino

Resultado: os dois PRs que sobraram do quiz Crivo integrados; a configuração
do quiz medida em produção e registrada no livro; as três decisões de produto
respondidas pelo mantenedor e executadas onde ele mandar; este arquivo vivendo
no repositório em `docs/quiz/RETOMADA-CRIVO.md`.

Prova que encerra a tarefa: `gh pr view 2116 --json state,mergedAt` e o mesmo
para 2117 com `MERGED` (ou 2117 fechado por decisão dele); URL de um run verde
de `operacoes-vps.yml` com `operacao=quiz-configuracao`; registro integrado em
`painel/registros/` com a medição; `MERGED` no PR que traz este arquivo; e a
prestação de contas final no formato da regra 9 do CLAUDE.md.

## O que já está pronto (não refazer)

- Jornada do quiz (TAR-751): PR #2115 integrado (`ea7db477`), deploy run
  36266933652 com `deploy (quiz): success`. Sonda pública
  https://meshcraft.top/quiz/crivo/ respondeu 200 em 26/09 às 21h UTC; o 422
  para telefone longo foi visto pela sessão anterior, não por esta. O que o
  quiz ganhou: quem volta vê o próprio resultado; o envio mostra "Calculando
  seu resultado…" em região `role="status"`; a página enviada que volta pelo
  histórico recarrega; o foco acompanha a pergunta; contato longo devolve 422;
  resultado sem faixa não mostra `sem_faixa`.
- Registro 053 da publicação: PR #2119 integrado (`120e5af1`, 20:02 UTC).
- TAR-587 (bancada com ambiente para alunos e identidade, armadilha 505) foi
  cancelada pelo mantenedor em 22/09/2026. Não recrie; só cite se esbarrar.

## Situação confirmada em 26/09/2026, 21h UTC

| Item | Fato medido | Fonte |
|---|---|---|
| PR #2116 (TAR-753) | OPEN, não rascunho, 8 checks verdes, `mergeStateStatus=BEHIND`, corpo SEM linha `Mandato-do-mantenedor:` | `gh pr view 2116`, `gh pr checks 2116` |
| PR #2117 (TAR-754) | OPEN, rascunho, 8 checks verdes, corpo com linha "Lista B" QUEBRADA em duas linhas (o regex só lê a primeira) | `gh pr view 2117 --json body` |
| Classificação do #2117 | `.github/workflows/operacoes-vps.yml` lê `secrets.` (VPS_HOST, DEPLOY_SSH_KEY): Lista A, senhas e chaves | `ci/mandato_por_faixa.py`, `docs/decisoes/MANDATO-POR-FAIXA.md` |
| CODEOWNERS | `/ci/`, `/.github/`, `/infra/`, `/docs/decisoes/` têm dono `@abundanciabr`; `painel/`, `fila/` e `docs/quiz/` não têm | `.github/CODEOWNERS` |
| Fila | TAR-753 e TAR-754 só existem nos ramos dos PRs, ambas com evento `concluida` apontando o próprio PR; a `evidencia_exigida` da 754 pede também a URL do run | `fila/eventos/` nos ramos |
| Bancadas | `wt-ci-teste-pix-sem-relogio`, `wt-ci-medir-crivo-em-producao` e `wt-painel-publicacao-quiz-jornada` existem em `C:\Users\davia\abundanciabr\` e estão limpas | `git status --short` em cada uma |
| Menu do site | A home de meshcraft.top não tem link para o quiz (links: cadastro, fórum, login, idiomas) | `curl https://meshcraft.top/` |
| Botão do resultado | Destino é `/checkout/<default_offer_slug do site>/`, montado por `infra/semear-quiz.sh` a partir do catálogo; hoje `curso-teste` (R$ 9,90, "Curso de Teste") em `infra/sites.json` | `infra/semear-quiz.sh` linhas 185 a 194 |
| Refazer o quiz | `formulario()` em `services/quiz/apps/quiz/views.py` (linha 227) devolve o resultado existente para a mesma `session_id`, sem botão nem aviso para refazer | fonte viva |
| Pouso | `pouso.yml` acorda em `edited`, `ready_for_review`, `synchronize` e a cada 15 min; base BEHIND não integra (política estrita) | `.github/workflows/pouso.yml`, `ci/mergear.py` linha 219 |
| Ambiente | gh logado (`abundanciabr`, escopos repo e workflow), Python 3.12.14, Docker 29.7.2, Node 24.19.0 | medido na máquina |
| origin/main | `ca3dd19d` (#2120 integrado) na hora da medição | `git rev-parse origin/main` |
| Linhas de mandato | As duas linhas propostas em T2 e T3, com a data 26/09/2026, passaram no classificador vivo com saída 0; o corpo atual do #2117 sai 1 ("o mandato não alcança .github/workflows/operacoes-vps.yml") | `python ci/mandato_por_faixa.py --corpo-arquivo` em checkout de `ca3dd19d` |

NÃO MEDIDO: o texto "Cartão indisponível" no checkout de `curso-teste` (a sonda
por curl não o vê; a sessão anterior o viu). Estado da fila por
`python ci/fila.py listar --ao-vivo` (só roda em bancada).

A lei viva difere da cópia do espelho em dois pontos: a regra 4 do CLAUDE.md
não cita mais "segredos"; operação na VPS sem SSH passa por `operacoes-vps.yml`
(Lei 5). Leia sempre `git show origin/main:CLAUDE.md`.

## Escopo e autoridade

- O clone principal `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923`
  é espelho: só leitura, `git fetch`, `git worktree` e `gh`. Toda edição nasce
  em bancada própria.
- Lista B (docs, painel, fila, testes, arquivos normais da faixa) já está
  autorizada por `docs/decisoes/MANDATO-POR-FAIXA.md`; a linha do PR cita a
  faixa, o documento e a cerca de CODEOWNERS.
- Lista A (pagamento e cobrança, servidor e infraestrutura, senhas e chaves)
  exige a palavra do mantenedor NESTA sessão, transcrita na linha
  `Mandato-do-mantenedor:`. Nunca invente mandato. O #2117 e qualquer mudança
  em `infra/sites.json` são Lista A.
- Decisões exclusivas dele: oferta do botão, quiz no menu, regra de refazer.
  Reúna tudo numa pergunta estruturada só (AskUserQuestion). Se ele fechar sem
  responder, é "não agora": pare a parte dependente e não repita.
- Subagente só com brief compilado por `python ci/economia_da_fabrica.py brief`
  (traz `modelo_recomendado` e `esforco_recomendado`; sem isso a ficha
  `despacho` recusa). Modelo declarado `sonnet` ou `opus` na chamada. Workflow
  é recusado. Subagente não pergunta ao mantenedor nem cria outro.
- Orçamento de 15 arquivos por PR fora `painel/` e `fila/`; um PR por frente.
  Frente sem tarefa na fila: crie com `python ci/fila.py criar` na bancada, ou
  omita `--tar` se o brief não citar tarefa.
- Sem travessão em texto publicado e em documentos. Fecho no formato da regra
  9 do CLAUDE.md, com Instruções.

## Primeira ação

1. No espelho: `git fetch origin` e
   `git worktree add ../wt-quiz-crivo-retomada -b agent/quiz/crivo-retomada origin/main`.
   Entre nessa pasta. É a bancada da sessão responsável (coordenação, `gh`,
   `ci/esperar.py`, `ci/fila.py listar`). As frentes abrem as próprias bancadas.
2. Rode a seção "Medir agora". Se #2116 ou #2117 mudaram de estado, recalcule
   (seção "Recalcular a rota").
3. Dispare em paralelo, na mesma resposta, as frentes F1, F2, F3 e F4.
4. Faça a pergunta única ao mantenedor. Enquanto ele responde, o trilho
   principal espera; as frentes F1 a F4 andam.

## Medir agora (o estado vive aqui)

```bash
gh pr view 2116 --json state,isDraft,mergedAt,mergeStateStatus,mergeCommit
gh pr view 2117 --json state,isDraft,mergedAt,mergeStateStatus,mergeCommit
gh pr checks 2116
gh pr checks 2117
gh pr view 2117 --json body --jq .body | grep -n "Mandato-do-mantenedor"
python ci/fila.py listar --ao-vivo | grep -E "TAR-75[134]"
gh run list --workflow=pouso.yml --limit 5 --json databaseId,status,conclusion,createdAt
gh run list --workflow=operacoes-vps.yml --limit 3 --json databaseId,status,conclusion,createdAt
curl -s -o /dev/null -w "%{http_code}\n" https://meshcraft.top/quiz/crivo/
```

TAR-753 e TAR-754 só aparecem no quadro depois que os PRs integram; até lá o
quadro mostra só a TAR-751 (concluída). `esperar.py --entrega` devolve JSON:
hoje `"estado": "AGUARDANDO_INTEGRACAO"`, e `"terminal": true` quando integrar.

## A pergunta única ao mantenedor

Uma chamada de AskUserQuestion com quatro perguntas, a primeira com
multiSelect. Português de leigo, consequência e recomendação em cada opção.

1. Autorizações (multiSelect):
   - "#2116, testes da CI (Lista B)": a lei já autoriza; o sim dele serve para
     o classificador de permissões da ferramenta deixar o `gh pr edit` passar.
   - "#2117, medição do quiz na VPS (Lista A)": autoriza tocar
     `.github/workflows/operacoes-vps.yml` e `ci/` para acrescentar a operação
     somente leitura `quiz-configuracao`. Sem isso o #2117 fica em rascunho.
2. Oferta do botão do resultado: "Manter curso-teste (R$ 9,90)" ou "Outra
   oferta" (ele digita slug, nome e preço; vira Lista A em `infra/sites.json`
   e exige mandato nominal na mesma resposta). Recomendação: manter até existir
   oferta real, porque preço de oferta publicada nunca é editado e oferta nova
   é decisão de dinheiro.
3. Quiz no menu do site: "Sim, eu coloco em /admin/menu/" ou "Não agora". O
   robô não tem credencial do admin; ele faz o gesto e o robô confere na home.
4. Regra para refazer o quiz. Hoje a mesma sessão sempre vê o mesmo resultado,
   sem aviso, inclusive com duas abas abertas. Opções: "Manter como está",
   "Botão Refazer que inicia sessão nova", "Só avisar na tela que o resultado é
   o da sessão". Recomendação: botão Refazer, porque resolve o caso das duas
   abas sem esconder o resultado de quem volta.

Informe no mesmo texto: TAR-587 cancelada em 22/09, não será recriada.

## Roadmap: trilho principal e frentes

Trilho principal (sessão responsável, em série): T1 pergunta única; T2 #2116
pousa; T3 #2117 pousa; T4 dispara F5; T5 frentes das decisões (F6, F7 e o
menu); T6 fechamento (F8, F9 e limpeza).

Frentes em subagente (nove; dispare só as que a decisão dele liberar):

| Frente | Ficha e modelo | Quando | Alvos | Prova de conclusão |
|---|---|---|---|---|
| F1 Este arquivo no repositório | despacho, brief `--tipo escrita` (sonnet), célula docs, `--sem-container` | T0, paralelo | `docs/quiz/RETOMADA-CRIVO.md` (Lista B, sem CODEOWNERS) | PR integrado; `git show origin/main:docs/quiz/RETOMADA-CRIVO.md` devolve o arquivo |
| F2 Revisão do #2116 | revisor (sonnet, fixo na ficha) | T0, paralelo | diff do PR 2116, só leitura | lista de reprovações com arquivo e linha, ou vazia |
| F3 Revisão do #2117 | revisor (sonnet) | T0, paralelo | diff do PR 2117; foco: a opção nova não amplia o que o workflow lê, o script só agrega, saída sem dado pessoal | idem; reprovação grave segura o `gh pr ready` até o conserto |
| F4 Saúde da esteira | maquinista (sonnet) | T0, paralelo | runs de `pouso.yml`, alarmes, último deploy | relatório do que trava o pouso agora, ou nada |
| F5 Medição em produção e livro | despacho, `--tipo escrita` (sonnet), célula painel, `--sem-container` | após #2117 MERGED | dispara o run `quiz-configuracao`; registro em `painel/registros/`; fecha TAR-754 conforme `listar --ao-vivo` | URL e SHA do run verde, JSON medido (faixas, `botao_destino`, cobertura), PR do registro integrado |
| F6 Oferta do botão | despacho, `--tipo produto` (opus) | só se ele escolher outra oferta e der mandato nominal para `infra/sites.json` | `infra/sites.json`; depois `gh workflow run semear-quiz.yml --ref main -f host=meshcraft.top` | deploy-infra verde, run do semeador verde, botão do resultado apontando para `/checkout/<oferta>/` na sonda |
| F7 Regra de refazer | despacho, `--tipo produto` (opus), célula quiz | só se ele escolher mudar | `services/quiz/apps/quiz/views.py`, template do resultado, testes; Lista B | teste vermelho→verde, PR integrado, deploy do quiz verde, sonda pública |
| F8 Contas do comprador e do aluno | procurador (sonnet) | antes de fechar a fila do pedido | só leitura | medição do que o trabalho entregou e do que ficou parado |
| F9 Lição da casa | escrivão (sonnet) | fim | armadilha nova: linha de mandato quebrada em duas linhas passa no olho e reprova no regex; despacho alegou Lista B em workflow com `secrets.` | número por `python ci/reservar.py numero armadilha`, arquivo `armadilhas/NNN-slug.md`, índice regenerado, PR |

Gesto dele, sem agente: menu em `/admin/menu/`. O robô confere com
`curl -s https://meshcraft.top/ | grep -o 'href="[^"]*quiz[^"]*"'`.

Como convocar uma frente de despacho:

```bash
python ci/economia_da_fabrica.py brief --tipo escrita --celula docs --objetivo "Publicar docs/quiz/RETOMADA-CRIVO.md com o conteúdo entregue pela sessão responsável" --alvo docs/quiz/RETOMADA-CRIVO.md --saida brief-f1.md
```

Cole o brief no prompt do Agent (subagent_type `despacho`, `model` igual ao
`modelo_recomendado`) com: célula, alvos, o que é só leitura, evidência
exigida, armadilhas, e o mandato nominal transcrito quando for Lista A. Revisor
em cada PR novo enquanto os checks rodam.

## Pipeline de cada PR

brief; despacho abre bancada (`ci/sessao.py`); classifica
(`python ci/mandato_por_faixa.py --arquivos <alvos> --faixa <célula>`); teste
vermelho→verde; `make pr` (embarca reserva, recibo, eventos e registro);
revisor durante os checks; linha de mandato conferida com `--corpo-arquivo`;
pouso automático; `python ci/esperar.py --entrega <N>`; registro de publicação
quando houver deploy.

### T2: pousar o #2116

```bash
gh pr view 2116 --json body --jq .body > corpo-2116.md
printf '\nMandato-do-mantenedor: mandato prévio por faixa ci ; docs/decisoes/MANDATO-POR-FAIXA.md ; cerca ci/ ; confirmado pelo mantenedor na sessão de DD/MM/AAAA\n' >> corpo-2116.md
python ci/mandato_por_faixa.py --arquivos $(gh pr view 2116 --json files --jq '.files[].path' | tr '\n' ' ') --faixa ci --corpo-arquivo corpo-2116.md
```

Só com saída 0: `gh pr edit 2116 --body-file corpo-2116.md`. A linha é UMA
linha, tokens separados por espaço, documento sem vírgula colada. Base BEHIND:
na bancada `wt-ci-teste-pix-sem-relogio`, `git fetch origin && git merge
origin/main`, depois `node painel/gerar_manifesto.js`, commit do que mudou e
push (o portão avisa que `gh pr update-branch` mistura a main sem regerar o
painel e o check `painel-no-navegador` reprova). Depois do push, espere os
checks com `python ci/esperar.py --checks 2116 --so-desfecho`; o pouso integra
sozinho quando os portões passam. Prova: `python ci/esperar.py --entrega 2116`
com `"terminal": true`, ou `gh pr view 2116 --json state,mergedAt,mergeCommit`
com `MERGED`. A linha acima, datada de 26/09/2026, saiu 0 no classificador vivo
quando esta rota foi escrita; rode a conferência mesmo assim.

### T3: pousar o #2117

Substitua as duas linhas que começam em `Mandato-do-mantenedor: Lista B` por
UMA linha com a palavra dele (adapte o pedido ao que ele disse):

```
Mandato-do-mantenedor: autoriza a operação somente leitura quiz-configuracao no canal da VPS .github/workflows/operacoes-vps.yml ci/ ; origem: sessão de DD/MM/AAAA
```

Confira com
`python ci/mandato_por_faixa.py --arquivos $(gh pr view 2117 --json files --jq '.files[].path' | tr '\n' ' ') --faixa ci --corpo-arquivo corpo-2117.md`:
precisa sair 0 com "mandato nominal presente e alcançando os caminhos" (a
linha acima, datada de 26/09/2026, saiu 0 quando esta rota foi escrita). Então
`gh pr edit 2117 --body-file corpo-2117.md`, base atualizada como no T2 (na
bancada `wt-ci-medir-crivo-em-producao`), `gh pr ready 2117` e a mesma
espera. Se ele recusar: `gh pr close 2117 --comment "<motivo dele>"` ou
retire a mudança do workflow, conforme ele disser, e registre `bloqueada` com
`--espera mantenedor` se sobrar parte dependente.

### T4: medir a produção (dentro da F5)

```bash
gh workflow run operacoes-vps.yml --ref main -f operacao=quiz-configuracao -f servico=quiz
gh run list --workflow=operacoes-vps.yml --limit 1 --json databaseId,status,url,headSha
python ci/esperar.py --run <id> --teto 15 --so-desfecho
gh run view <id> --json status,conclusion,url,headSha
gh run view <id> --log | grep -E "quiz|faixas|botao_destino|cobertura"
```

PASS prova a coleta, não a saúde. Entregue URL, SHA e a medição: faixas com
intervalo, `botao_destino` e `botao_rotulo`, cobertura, versões, contagens.
Registro <1 KB pelo molde de `painel/LEIA-ME.md`, número por
`python ci/reservar.py numero registro`, com `evidencia` e `verificado_em`.
TAR-754: se `listar --ao-vivo` a mostrar terminal, só o registro; se não,
`python ci/fila.py reconciliar TAR-754 --quem <sessão> --aceite-registro painel/registros/<registro já integrado>`
em PR seguinte.

## Checklist vivo

Marque só com a prova ao lado. O comando que prova está em "Medir agora". A
cópia deste arquivo no repositório é atualizada uma vez, no T6, por um PR só.
Este checklist é resumo humano: a fonte é a fila (`depende_de` entre as TARs)
mais os comandos de "Medir agora", como manda
`docs/decisoes/PLANO-MESTRE-APPMAX-NO-CARTAO.md` §13 a §15 (checklist vivo é
calculado, nunca digitado). As TARs novas das frentes declaram `depende_de`
real: F5 depende da TAR-754 integrada; F6 e F7 dependem das decisões dele.

- [x] TAR-751: #2115 MERGED `ea7db477`, deploy verde, sonda 200
- [x] Registro 053: #2119 MERGED `120e5af1`
- [x] #2117 devolvido a rascunho para não integrar com mandato inventado
- [x] Rota e arquivo de retomada escritos (26/09/2026, sessão de rota)
- [x] F1: `docs/quiz/RETOMADA-CRIVO.md` integrado: #2121 MERGED `6f7dcc8e`
- [x] Pergunta única respondida na sessão de 26/09/2026: autoriza #2116 e #2117; mantém curso-teste; menu "não agora"; botão Refazer (registro 058)
- [x] #2116 MERGED `e4e5babe`
- [x] #2117 MERGED `3626b247`
- [x] Run `quiz-configuracao` verde: https://github.com/abundanciabr/sitesdoreino/actions/runs/36273310706 (SHA `3626b247`); registro 059 no #2124 MERGED `570b2957`
- [x] TAR-754 `concluída` em `listar --ao-vivo`
- [x] Oferta do botão mantida em curso-teste por decisão dele (F6 não disparada)
- [x] Menu: "não agora" registrado no registro 058 (#2123 MERGED `74ae3dbf`)
- [x] Regra de refazer: F7 #2122 MERGED `869d3361`, deploy https://github.com/abundanciabr/sitesdoreino/actions/runs/36274527935 verde, rota com 405 (GET) e 403 (POST sem token); registro 065
- [x] F8 procurador devolvido; F9 armadilha 510 no #2123 MERGED `74ae3dbf`
- [ ] Limpeza: as três bancadas removidas; `%TEMP%\sitesdoreino-sessoes\quiz-jornada-completa-crivo\` ficou com o mantenedor (a ferramenta recusou apagar)
- [x] Prestação de contas final com Instruções na sessão de retomada de 26/09/2026

## Referências e por que ler

- `git show origin/main:CLAUDE.md`: a lei viva; a cópia do espelho está velha.
- `docs/decisoes/MANDATO-POR-FAIXA.md` e `ci/mandato_por_faixa.py`: o que é
  Lista A e B e o formato exato da linha.
- `ci/mergear.py` (linhas 219 a 246 e 850 a 910): base BEHIND e a conferência
  de CODEOWNERS na hora do pouso.
- `docs/guia-mantenedor.md`, seções "Decisões" e "Operações da VPS pelo
  agente": como perguntar e como disparar e ler o run.
- `.claude/agents/LEIA-ME.md` e `.claude/agents/despacho.md`: o que o brief
  carrega e o rito fixo.
- `infra/semear-quiz.sh` e `.github/workflows/semear-quiz.yml`: de onde vem o
  destino do botão (F6).
- `services/quiz/LICOES.md` e `views.py` linhas 212 a 235: o reenvio na mesma
  sessão (F7).
- `painel/LEIA-ME.md`: molde do registro.
- `armadilhas/505`: bancada com ambiente recusada. Se `ci/sessao.py --celula
  quiz` recusar com esse sinal, reabra com `--sem-container` e rode a suíte da
  célula à mão antes da primeira edição.

## Bloqueios e recuperação

- Classificador de permissões recusa `gh pr edit` com a linha de mandato: a
  resposta dele nesta sessão é o que destrava; sem ela, não escreva a linha.
- Pouso vermelho: leia a mensagem do portão (`python ci/mergear.py <N>
  --conferir`), conserte o técnico na bancada do PR, nunca no espelho.
- Run da VPS cancelado, vazio ou com erro: não é prova; não repita sem
  hipótese nova (`python ci/fila.py tentativa-sem-progresso`).
- "Não agora" dele: pare a parte dependente, registre `bloqueada` com
  `--espera mantenedor` e diga nas Instruções o que destrava.
- Duas tentativas sem mover um critério: checkpoint
  (`python ci/fila.py checkpoint TAR-NNN --quem ... --plano ... --ultimo-avanco ... --proxima-acao ... --verificacao ...`)
  e abordagem diferente.

## Recalcular a rota quando

- #2116 ou #2117 estiver MERGED, CLOSED ou com check vermelho ao medir.
- `ci/mandato_por_faixa.py` classificar diferente do descrito aqui.
- `git show origin/main:CLAUDE.md` mudar as regras de mandato ou de subagente.
- A sonda do quiz não responder 200.
- A resposta dele não couber nas opções: transcreva literalmente e reparta.

Ponto de retomada: este arquivo, mais `python ci/fila.py listar --ao-vivo` e
os comandos de "Medir agora". Nada aqui autoriza executar além do que ele
respondeu.
