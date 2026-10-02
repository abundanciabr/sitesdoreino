# Retomada do sistema de experimentos | roadmap, frentes e checklist vivo

Cole este arquivo inteiro numa sessão nova do Claude Code aberta no repositório
abundanciabr/sitesdoreino. Ele é a rota de continuação e o arquivo de retomada
ao mesmo tempo. Sempre PT-BR. Estado medido em 26/09/2026 por volta das 22h UTC
pela sessão de rota, em checkout de origin/main `3626b247`. O estado vivo sai
dos comandos da seção "Medir agora", nunca das caixinhas.

A ordem do mantenedor: NÃO é auditoria. É concluir a IMPLEMENTAÇÃO do sistema
de experimentos de ponta a ponta, o mais rápido possível, com frentes em
subagente (sonnet ou opus conforme o brief). Toda leitura abaixo existe só para
o executor não reinvestigar; o que não estiver aqui, meça e siga.

Como publicar hoje: teste no PC (`make testes`, `make celula CELULA=<modulo>`),
empurre na `main` e em cerca de 1 minuto a VPS publica (`plataforma receber`).
Não há pull request obrigatório, mandato, fila nem workflow; as partes abaixo
que falam deles são do desenho antigo e valem só como histórico.

## Resultado e destino

Resultado, da cadeira do mantenedor: ele abre a administração, cria um
experimento num slot da página de oferta (`cubo.headline`), com dois braços
50/50, e inicia. Cada visitante recebe sempre o mesmo braço. A visita, a seção
vista, o clique no CTA e o lead capturado viram fatos no livro da `metricas`.
A tela do funil mostra a escada por visitantes distintos. A tela do experimento
mostra atribuídos, expostos, conversões por braço, efeito, intervalo, p, SRM e
maturidade, e diz "coletando", "inconclusivo" ou "candidato à promoção". Ele
decide: promover (publica a versão vencedora pela publicação que já existe),
reverter ou encerrar; o aprendizado vira registro no livro e aparece no
laboratório. Se ele autorizar o checkout, a compra volta ao visitante.

Destino: PRs integrados e publicados nas células `funil`, `metricas`,
`catalogo`, `admin` e, com mandato, `contracts` e `checkout`; este arquivo em
`docs/experimentos/RETOMADA-EXPERIMENTOS.md`; o manual de experimentação
resolvido em `/docs/`.

Prova que encerra a tarefa (todas):

1. Uma visita real a https://meshcraft.top/oferta gera `funil.pagina-vista`,
   `funil.secao-vista` e `funil.cta-clicado` que aparecem em
   `/admin/placar/funil/` com o mesmo `visitor_id`, medido de fora e depois na
   tela (print ou vídeo do mantenedor, ou o harness `e2e/`).
2. Um experimento A/A técnico (duas cópias idênticas) roda em produção: dois
   visitantes com cookies diferentes caem em braços determinísticos, a
   exposição conta, a tela mostra SRM sem alarme e veredito "inconclusivo".
3. Um A/B com a headline B que ele fornecer roda com os mesmos passos.
4. Todo PR MERGED, todo deploy verde, toda tela sondada; nenhum dado pessoal no
   livro (`customer`, e-mail, nome, telefone nunca entram na `metricas`).
5. `/docs/plataforma-experimentacao-e-aprendizado-de-conversao` responde 200,
   ou o mantenedor disse que o manual fica privado.

## O que já está pronto (não refazer)

A lei é `docs/decisoes/DECISAO-a-pagina-real-antes-do-experimento.md`
(19/09/2026): página real e telemetria antes de qualquer infraestrutura de
experimento; escada de sete PRs em quatro células. Estado da escada:

| Degrau | Entrega | Estado | Prova |
|---|---|---|---|
| 1 contratos | aditivo de páginas no catálogo e quatro eventos `funil.*` | FEITO | TAR-510, PR #1772; `contracts/eventos/funil.{pagina-vista,secao-vista,cta-clicado,lead-capturado}.v1.json` |
| 2 catalogo | `Page`, `PageVersion` imutável, `PageDraft`, vocabulário de slots | FEITO | TAR-509 #1773, TAR-526 #1796, #2043 páginas tipadas; `services/catalogo/apps/paginas/` |
| 3 funil | `visitor_id` de primeira parte (cookie `meshcraft_visitante`) | FEITO | TAR-508 #1774, TAR-513 #1779; `services/funil/apps/core/visitante.py` |
| 4 funil | `/oferta` renderizada da estrutura | FEITO | TAR-520 #1784; 200 em produção |
| 5 admin | editor da copy e publicação (`/admin/paginas/`) | FEITO | TAR-522 #1785; `services/admin/apps/core/paginas.py` |
| 6 funil | telemetria: seção vista, CTA clicado, lead capturado | PARCIAL: só `pagina-vista` é emitido (`views.py` 435 a 462) | os três restantes existem só como contrato |
| 7 admin | funil na tela, calculado do livro | NÃO FEITO | nenhuma leitura de `funil.*` em `services/admin` |

Também pronto: livro de fatos imutável e recepção na `metricas`
(`apps/fatos/models.py`, `recepcao.py`); `REDIS_STREAMS_URL` no serviço `funil`
do compose (TAR-523 #1788); par admin→metricas provisionado em 04/09
(registro 20260904-085 responde ao 073); laboratório organizacional
`/admin/placar/laboratorio/` (experimento = registro `medicao` do livro com
`problema`, `hipotese`, `metrica`, `guarda`, `vence_em_dias`; resultado =
registro com `responde_a` e `veredito`); harness de navegador em `e2e/`; manual
publicado como documento semeado (PR #2014, migração 0028) e a ordem de serviço
da copy em `docs/despachos/DESPACHO-COPY-DA-PAGINA-DE-OFERTA.md`.

## Situação confirmada em 26/09/2026, 22h UTC

| Item | Fato medido | Fonte |
|---|---|---|
| Página de oferta | 200, título "Curso de Teste \| Meshcraft", conteúdo "TESTE FICTÍCIO: página completa de demonstração" semeado por TAR-624 (#1934); a copy real depende das respostas dele à ordem de serviço | `curl https://meshcraft.top/oferta` |
| Consumidor da metricas | `STREAMS` em `consume_eventos.py` (linhas 63 a 82) assina identidade, quiz, forum, matricula e sugestao. NENHUM `eventos.funil.*`, `eventos.pedido.*` ou `eventos.pagamento.*`. As visitas publicadas pelo funil vão ao Redis e ninguém as guarda | `grep -c "eventos.funil" consume_eventos.py` = 0 |
| API da metricas | `countFacts` (por tipo e dia, sem visitante distinto), `listCoverage`, `listDeadLetters`, `getDeadLetter`, `countMilestones`, `listMilestones` | `contracts/metricas.openapi.yaml` |
| `Evento` | guarda `dados` (JSON) com o payload inteiro; `event_id` único; append-only | `services/metricas/apps/fatos/models.py` |
| Cookie do visitante | `httponly`, `samesite=Lax`, `secure` atrás do proxy, path padrão `/`: o checkout, servido no mesmo host em `/checkout/`, recebe o cookie | `visitante.py` 113 a 128 |
| Checkout | `CheckoutSession` tem `lead_id` e `utm`, não tem `visitor_id`; `pedido.criado.v1` leva `customer` (dado pessoal) e não pode entrar no livro; o checkout já consome `pagamento.aprovado.v2` (TAR-546) | `services/checkout/apps/pedidos/models.py`, `core/api.py` 380 a 420 |
| Eventos de compra | `pagamento.aprovado.v2` leva `customer`; `matricula.situacao-alterada.v1` não leva `order_id`. Logo, compra atribuída exige evento sanitizado novo emitido pelo checkout | `contracts/eventos/` |
| Esquemas dos três eventos faltantes | `secao-vista`: site_id, visitor_id, pagina_slug, pagina_version, secao. `cta-clicado`: mais `slot` e `destino`. `lead-capturado`: mais `lead_id`. Todos `additionalProperties: false`: campo de experimento exige aditivo de contrato | `contracts/eventos/funil.*.v1.json` |
| Template da oferta | seções com `data-secao`, CTA `.cta` para `url_checkout` (`/checkout/<slug>/` com UTM); sem script no template | `services/funil/templates/funil/oferta.html` |
| Vocabulário | seções `cubo`, `viloes`, `metodo`, `instrumentos`, `percurso`, `tempo`, `para_quem_nao_serve`, `se_eu_parar`, `oferta`, `carta`, `perguntas`; `cubo` tem `headline`, `subheadline`, `cta_texto`, `cta_destino`, `imagem` | `services/catalogo/apps/paginas/vocabulario.py` |
| Classificação | `services/checkout/` e `services/pagamentos/` mexem em pagamento e cobrança: dinheiro real só com a palavra dele. `contracts/` guarda os contratos entre os módulos. `funil`, `metricas`, `catalogo`, `admin`, `docs/experimentos/` andam livres | `celulas.yml`, `contracts/` |
| Rascunhos #1917 e #2017 | ramos só com o commit "anunciar intenção"; PR #1917 (medir-funil-real) não tem trabalho. A bancada local `C:\Users\davia\abundanciabr\wt-admin-manual-experimentacao-mvp` tem 340 linhas NÃO commitadas reescrevendo o manual, com o capítulo 21 "Plano de execução do MVP" (lotes L0 a L10) | `git -C <bancada> diff --stat` |
| Manual | `/docs/plataforma-experimentacao-e-aprendizado-de-conversao` 404; `/docs/` lista quatro documentos públicos e o manual não está entre eles; a admin foi implantada depois do #2014 (runs verdes de 24/09 03:57 em diante), então a migração 0028 rodou. Causa possível: linha ausente, privada ou arquivada no banco; não dá para saber de fora | sondas e `plataforma estado` na VPS |
| Ambiente | gh logado (`abundanciabr`, escopo repo), Python 3.12.14, Docker 29.7.2, Node 24.19.0 | medido na máquina |

NÃO MEDIDO: se o processo consumidor da `metricas` está de pé em produção
(na VPS, `plataforma operar operacoes-vps --operacao estado-servico --servico metricas`
mede); o estado do banco de documentos da admin (só pela tela autenticada).

## Escopo e autoridade

- A lei da ordem é a decisão de 19/09/2026. Ela mantém: nenhuma célula
  `experimentos` nova (§8); CUPED, bandits, personalização, knowledge graph e
  IA geradora de hipóteses fora (§7); SRM entra agora, porque o primeiro
  experimento divide tráfego (§6); camadas de exclusão mútua e holdout ficam
  fora até o gatilho.
- O manual `documentos/plataforma-experimentacao-e-aprendizado-de-conversao.md`
  é a especificação publicada; o capítulo 21 do rascunho local é plano, não lei.
- Checkout e contratos: `services/checkout/` mexe em pagamento, então só anda
  com a palavra dele NESTA sessão. `contracts/` só cresce por aditivo (campo
  opcional novo). Todo o resto anda livre.
- Decisões exclusivas dele: autorizar contratos e checkout, a métrica principal
  do primeiro experimento, o conteúdo do braço B, o manual público ou privado.
  Reúna tudo numa pergunta estruturada só. "Não agora" para a parte dependente e
  não repete.
- Copy real da página é dele (ordem de serviço). O sistema se prova com A/A
  sobre a página atual; não espere a copy para construir.
- Subagente recebe um brief escrito (célula, alvos, o que é só leitura,
  evidência esperada), com modelo `sonnet` ou `opus` declarado na chamada.
  Subagente não pergunta ao mantenedor nem cria outro. Frente grande demais
  divide por provedor e consumidor; dependência real é dita no brief.
- Sem travessão em texto publicado e documentos. Fecho no formato da regra 9.

## Primeira ação

1. No espelho `C:\Users\davia\abundanciabr\sitesdoreino-limpo-20260923`:
   `git fetch origin` e
   `git worktree add ../wt-experimentos-retomada -b agent/experimentos/retomada origin/main`.
   Entre nessa pasta: é a bancada da sessão responsável. As frentes abrem as
   próprias bancadas por `ci/sessao.py`.
2. Rode "Medir agora". Se algum PR das células já mudou o estado descrito,
   recalcule.
3. Dispare em paralelo, na mesma resposta, F1, F2 e F3 (Lista B, sem decisão
   pendente).
4. Faça a pergunta única. Quando ele responder, dispare F4; com F4 integrada,
   F5, F6 e F10 em paralelo; depois F7 e F8; depois F9; por fim L10.

## Medir agora (o estado vive aqui)

```bash
gh pr list --state open --limit 100 --json number,title,isDraft,headRefName --jq '.[] | select(.headRefName | test("^agent/(funil|catalogo|contratos|contracts|admin|metricas|checkout|experimentos)/")) | "\(.number) draft=\(.isDraft) \(.headRefName) :: \(.title)"'
curl -s -o /dev/null -w "oferta %{http_code}\n" https://meshcraft.top/oferta
curl -s -o /dev/null -w "manual %{http_code}\n" https://meshcraft.top/docs/plataforma-experimentacao-e-aprendizado-de-conversao
curl -s -o /dev/null -w "funil-admin %{http_code}\n" https://meshcraft.top/admin/placar/funil/
git grep -c "eventos.funil" origin/main -- services/metricas/apps/fatos/management/commands/consume_eventos.py
git grep -nE "secao-vista|cta-clicado|lead-capturado" origin/main -- services/funil/apps/core/views.py
ssh sitesdoreino-vps /opt/plataforma/bin/plataforma operar operacoes-vps --operacao estado-servico --servico metricas
```

## A pergunta única ao mantenedor

Uma chamada de AskUserQuestion com quatro perguntas. Português de leigo,
consequência e recomendação em cada opção.

1. Autorizações (multiSelect):
   - "Contratos aditivos (Lista B com etiqueta contrato)": os eventos `funil.*`
     ganham campos opcionais `experimento_id` e `variante_id`; nascem
     `checkout.pedido-atribuido.v1` e `checkout.pedido-pago.v1` sem dado
     pessoal; `catalogo.openapi` ganha o experimento na página e as operações
     de criar, ler, listar e mudar estado; `metricas.openapi` ganha
     `countFunnel`. Sem isso o sistema para na telemetria.
   - "Checkout (Lista A, pagamento e cobrança)": `CheckoutSession.visitor_id`
     lido do cookie e os dois eventos sanitizados. Sem isso a compra não volta
     ao visitante e o funil termina na entrada do checkout.
2. Métrica principal do primeiro experimento: "Entrada no checkout por
   visitante (CTA clicado com destino /checkout)" ou "Compra confirmada".
   Recomendação: entrada no checkout, porque se mede com centenas de visitantes
   por braço; compra pede milhares e depende da autorização do checkout.
3. Conteúdo do primeiro experimento: "A/A técnico agora com a página atual e
   A/B quando eu mandar a headline B do cubo" (recomendado), "Já mando a
   headline B agora" (ele digita), ou "Esperar a copy real". Explique: A/A
   prova o sistema sem inventar promessa pública; a copy é dele.
4. Manual de experimentação: "Quero público em /docs; autorizo abrir
   /admin/documentos/ no meu Chrome para diagnosticar" ou "Deixei privado de
   propósito; nada a fazer".

Informe no mesmo texto: os rascunhos #1917 e #2017 não têm trabalho no ramo;
o rascunho local do manual (capítulo 21) será aproveitado pela F1; nenhuma
célula nova nasce (decisão de 19/09).

## Roadmap: trilho principal e frentes

Trilho principal (sessão responsável): T1 pergunta única; T2 F4 pousa; T3
ondas de frentes conforme dependências; T4 ensaio L10 em produção (A/A e, se
houver headline, A/B); T5 fechamento (provador, procurador, escrivão, limpeza).

Frentes (dez; cada uma vira um PR pela ficha `despacho`; revisor em cada PR
enquanto os checks rodam):

| Frente | Lote do manual | Brief e modelo | Célula e alvos | Depende de | Prova de conclusão |
|---|---|---|---|---|---|
| F1 Este arquivo e o manual | L0 | `--tipo escrita` (sonnet) | `docs/experimentos/RETOMADA-EXPERIMENTOS.md`; capítulo 21 do rascunho local de `wt-admin-manual-experimentacao-mvp` conferido contra esta rota e commitado em `documentos/`; diagnóstico do 404 conforme a resposta 4 | nada | PR integrado; `git show origin/main:docs/experimentos/RETOMADA-EXPERIMENTOS.md`; `/docs/...` 200 ou decisão dele registrada |
| F2 O livro recebe o funil | L3 | `--tipo teste` (sonnet) | `services/metricas`: `STREAMS` ganha `eventos.funil.pagina-vista`, `secao-vista`, `cta-clicado`, `lead-capturado`; teste de recepção com fixture de cada um; sem dado pessoal | pousa DEPOIS da F3 (provedor antes do consumidor); prepare em paralelo | deploy da metricas verde; `countFacts` com `tipo=funil.pagina-vista` devolve a visita de teste |
| F3 O funil emite o que sabe | L2 | `--tipo produto` (opus) | `services/funil`: endpoint fail-open de telemetria do navegador (seção vista uma vez por seção e carga; CTA clicado com `slot` e `destino`), contexto validado no servidor, `event_id` estável por fato; `lead-capturado` após resposta válida da `leads` com `lead_id`; testes | nada (campos base do contrato atual) | testes vermelho→verde; sonda: visita real gera os três fatos no Redis; nada quebra sem Redis |
| F4 Contratos do experimento | L1 | `--tipo contrato` (opus); etiqueta `contrato`; linha de mandato com `contracts/` | `contracts/eventos/` (aditivos opcionais em `funil.*`; novos `checkout.pedido-atribuido.v1` e `checkout.pedido-pago.v1`), `contracts/catalogo.openapi.yaml` (experimento na página; operações de ciclo), `contracts/metricas.openapi.yaml` (`countFunnel`: por passo e por variante, visitantes distintos, janela) | resposta 1 | `python ci/contrato_aditivo.py` PASS; PR integrado |
| F5 O experimento mora na página | L6 | `--tipo produto` (opus) | `services/catalogo`: `Experimento` (página, idioma, seção, slot, alocação, estado rascunho→ativo→pausado→encerrado, um ativo por página e idioma) e `Variante` com snapshot imutável do texto; `getPage` devolve o experimento ativo; API do ciclo | F4 | testes: imutabilidade, um ativo por página, pausa; PR integrado |
| F6 A leitura do funil | L3 | `--tipo teste` (sonnet) | `services/metricas`: `countFunnel` sobre `dados->>'visitor_id'`, por dia, por passo e por `variante_id`; teste com dois sites e duplicata | F4 | testes verdes; PR integrado |
| F7 O funil na tela | L4 | `--tipo produto` (opus) | `services/admin`: `/admin/placar/funil/` lendo `countFunnel` pelo cliente da metricas; zero verdadeiro distinto de sem coleta; erro de rede não vira zero | F2, F3, F6 | tela mostra a visita de teste com os mesmos IDs do livro |
| F8 Sorteio e exposição | L7 | `--tipo produto` (opus) | `services/funil`: avaliador determinístico (hash de `visitor_id` e `experimento_id`), braço sticky, render do slot da variante, `pagina-vista` com `experimento_id` e `variante_id`, exposição = `secao-vista` da seção do slot com os mesmos campos; A/A técnico | F3, F4, F5 | teste de distribuição e de sticky; A/A em bancada percorre sorteio, exposição e livro |
| F9 Decidir com rigor | L8, L9 | `--tipo produto` (opus); dois PRs se estourar 15 arquivos | `services/admin`: telas de criar (slot, hipótese, texto B, alocação), iniciar, pausar, encerrar; resultado com N por braço, conversões, taxa, efeito, intervalo, p de duas proporções, SRM (qui-quadrado), maturidade e estados; promover publica B pela publicação existente; reverter; aprendizado vira registro `medicao` com resposta no livro | F5, F6, F8 | fixtures aprovadas dão resultado reproduzível; duplo clique não duplica; PR integrado |
| F10 A compra volta ao visitante | L5 | `--tipo teste` (sonnet); Lista A | `services/checkout`: `CheckoutSession.visitor_id` do cookie `meshcraft_visitante`; outbox emite `pedido-atribuido` ao criar pedido e `pedido-pago` ao consumir `pagamento.aprovado.v2`; metricas assina os dois (F2 ou PR irmão) | F4 e resposta 1 | pedido de teste em sandbox aparece no funil ligado ao visitante |

**F4 foi dividida em 26/09/2026, pelo Rito de Contrato (RITOS.md §3, "provedor
primeiro"):** F4a entrega só os aditivos de `contracts/eventos/` (os quatro
`funil.*` ganhando `experimento_id`/`variante_id` opcionais e os dois eventos
novos de compra), porque não depende de nenhuma célula terminar. Os aditivos
de `contracts/catalogo.openapi.yaml` (experimento na página) e de
`contracts/metricas.openapi.yaml` (`countFunnel`) deixam de nascer de uma
sessão de arquitetura solta e passam a nascer do EXPORT do ramo de quem
implementa: F5 (catálogo) e F6 (métricas) escrevem a operação primeiro na sua
própria célula, cada uma exporta e serializa o congelado byte a byte, e cada
aditivo pousa no PR de contrato dela (só `contracts/`, etiqueta `contrato`),
com `Depende-de: #<PR da célula>`. F5 e F6 na tabela abaixo passam a depender
de F4a (não mais de "F4" inteira), e cada uma abre seu próprio PR de contrato
antes do PR de código.

Rito de fechamento, sem frente própria: `provador` (sonnet) prova por mutação
os guardas de F5, F8 e F9 (sticky, distribuição, exposição separada, SRM,
imutabilidade); `procurador` (sonnet) antes de fechar a fila; `escrivão`
(sonnet) registra as lições, inclusive "a decisão supôs que o livro recebia
qualquer evento, e o consumidor tem lista fechada".

Como convocar uma frente:

Escreva o brief no prompt do Agent com célula, alvos, o que é só leitura e a
evidência esperada. Exemplo da F3: célula `funil`; objetivo "Emitir
funil.secao-vista, funil.cta-clicado e funil.lead-capturado com endpoint
fail-open e testes"; alvos `services/funil/apps/core/views.py`,
`services/funil/apps/core/telemetria.py` e
`services/funil/templates/funil/oferta.html`.

## Caminho de cada frente até o ar

Brief; teste vermelho→verde no PC; `make testes` e `make celula CELULA=<modulo>`;
push na `main`; a VPS publica em cerca de 1 minuto (`plataforma receber`);
conferir `publicacoes/logs/lote-<sha12>.log` e `plataforma estado` na VPS
(`ssh sitesdoreino-vps`); sonda pública no endereço. Se a prova do endereço
falhar, o código volta sozinho para a última versão aprovada: conserte e
empurre de novo. O banco não volta sozinho.

### T4: ensaio L10 em produção

1. Com F1 a F9 integradas e implantadas: crie o experimento A/A pela tela da
   F9 (mesmo texto nos dois braços), inicie.
2. Dois navegadores sem cookie visitam `/oferta`: confira o braço de cada um
   no HTML (atributo de dados do slot), repita a visita e confira que o braço
   não muda.
3. Role até o slot e clique no CTA nos dois; confira em `/admin/placar/funil/`
   e na tela do experimento os dois visitantes, a exposição e o clique.
4. Encerre: a tela precisa dizer "inconclusivo" com SRM sem alarme, e o
   registro `medicao` mais a resposta com `veredito` precisam aparecer em
   `/admin/placar/laboratorio/`.
5. Se ele deu a headline B: repita como A/B e deixe rodando; a duração vem do
   tráfego medido, nunca inventada.
6. Prova: URLs, SHAs dos deploys, IDs dos eventos no livro e as telas (print,
   vídeo ou `e2e/`). Sem terminal do mantenedor em nenhum passo.

## Checklist vivo

Marque só com a prova ao lado. A fonte é a fila (`depende_de` entre as TARs) e
os comandos de "Medir agora"; a cópia deste arquivo no repositório é atualizada
uma vez, no fechamento, por um PR só.

- [x] Degraus 1 a 5 da decisão de 19/09 integrados (PRs #1772, #1773, #1774, #1779, #1784, #1785, #1796)
- [x] `funil.pagina-vista` emitido em produção; `REDIS_STREAMS_URL` no funil (#1788)
- [x] Par admin→metricas provisionado (registro 20260904-085)
- [x] Rota e arquivo de retomada escritos (26/09/2026, sessão de rota)
- [x] Pergunta única respondida em 26/09/2026 22:25 UTC: contratos e checkout autorizados; métrica entrada no checkout; A/A agora e A/B quando ele mandar a headline B; manual público
- [ ] F1 integrada: arquivo em `docs/experimentos/`, manual resolvido
- [ ] F3 integrada e implantada: visita real gera secao-vista e cta-clicado
- [ ] F2 integrada e implantada: os quatro `funil.*` no livro
- [ ] F4 integrada (contratos aditivos, etiqueta `contrato`)
- [ ] F5 integrada: experimento e variante no catálogo
- [ ] F6 integrada: `countFunnel`
- [ ] F7 integrada e implantada: `/admin/placar/funil/` mostra a visita de teste
- [ ] F8 integrada e implantada: A/A em bancada e em produção
- [ ] F9 integrada e implantada: criar, iniciar, resultado, SRM, promover, reverter, aprendizado no livro
- [ ] F10 integrada (só com mandato do checkout): compra atribuída ao visitante
- [ ] Ensaio L10 em produção com prova (telas, IDs, SHAs)
- [ ] Provador, procurador e escrivão devolvidos
- [ ] Limpeza: bancadas removidas com `git status` limpo e PR integrado
- [ ] Prestação de contas final com Instruções

## Referências e por que ler

- `docs/decisoes/DECISAO-a-pagina-real-antes-do-experimento.md`: a ordem, o
  que fica adiado (§6) e o que fica fora (§7 e §8).
- `documentos/plataforma-experimentacao-e-aprendizado-de-conversao.md`
  (capítulos 6 a 12, 21 e 22): inventário, entidades, assignment e exposure,
  métricas, SRM, fases e guardas exigidos.
- Rascunho local `C:\Users\davia\abundanciabr\wt-admin-manual-experimentacao-mvp\documentos\...` (capítulo 21, L0 a L10): plano detalhado por lote; aproveite, não obedeça.
- `services/metricas/apps/fatos/management/commands/consume_eventos.py`
  (docstring e `STREAMS`) e `recepcao.py`: como assinar sem criar grupo vazio.
- `services/funil/apps/core/telemetria.py`, `visitante.py`, `views.py` 425 a
  470: como o funil publica hoje.
- `services/catalogo/apps/paginas/models.py`, `vocabulario.py`, `api.py`: onde
  o experimento vai morar.
- `services/admin/apps/core/paginas.py`, `laboratorio.py`, `placar.py`,
  `clients.py` 1767 a 1830: editor, laboratório, placar e cliente da metricas.
- `services/checkout/apps/pedidos/models.py` e `core/api.py` 296 a 420: sessão
  e pedido (F10).
- `contracts/README.md`: como o contrato cresce por aditivo.
- `docs/guia-mantenedor.md` ("Decisões", "Operações da VPS pelo agente").
- `e2e/`: harness de navegador para a prova L10.
- `armadilhas/505`: bancada com ambiente recusada; se `ci/sessao.py` recusar,
  reabra com `--sem-container` e rode a suíte da célula à mão.

## Bloqueios e recuperação

- "Não agora" dele em contratos: F1, F2, F3 e F7 (com `countFacts` por tipo e
  dia, sem visitante distinto) ainda entregam a telemetria e um funil de
  contagens; registre `bloqueada` com `--espera mantenedor` para F4 a F10.
- "Não agora" no checkout: tudo anda; o funil termina na entrada do checkout e
  a compra atribuída fica registrada como pendente dele.
- Consumidor da metricas sem grupo para um stream novo: `XGROUP CREATE` com
  `MKSTREAM` é o molde das outras células; provedor antes do consumidor.
- Evento recusado na recepção (fica em `listDeadLetters`): corrija o emissor,
  nunca afrouxe a recepção.
- Publicação falhou: leia `publicacoes/logs/lote-<sha12>.log` e `plataforma
  estado` na VPS; o código já voltou sozinho, conserte e empurre de novo.
- Duas tentativas sem mover um critério: abordagem diferente.

## Recalcular a rota quando

- Um PR aberto nas células listadas tocar telemetria, páginas, experimento ou
  consumidor da metricas (alguém pode ter começado).
- `consume_eventos.py` já contiver `eventos.funil.` em origin/main.
- A resposta dele mudar a métrica principal, o slot ou recusar contratos.
- `git show origin/main:CLAUDE.md` ou a decisão de 19/09 mudarem.
- A página de oferta deixar de responder 200.

Ponto de retomada: este arquivo e os comandos de "Medir agora". Nada aqui autoriza executar além do que ele
respondeu.
