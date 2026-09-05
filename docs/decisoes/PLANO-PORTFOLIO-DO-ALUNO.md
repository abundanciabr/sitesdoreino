# PLANO — o aluno monta o portfólio, a escola confere, e sai um link para mandar ao cliente

**Nasceu de:** sugestão "Guias de portifolio com Check-list" na Caixa (15 votos,
categoria "Curso e aulas", autor Ricardo) · 01/09/2026
**Estado:** estudo com **duas decisões do mantenedor já tomadas** (01/09/2026, na
conversa em que o plano foi apresentado). Ver §6, que agora tem as respostas.
A construção NÃO foi autorizada: ele pediu para guardar o plano por enquanto.
**Molde:** `docs/caixa-de-sugestoes/MODELO-ESTUDO-DE-VIABILIDADE.md` (este é o
primeiro estudo escrito nele, e serve de exemplo preenchido).

## §1 O pedido, decomposto

> "Eu terminei as aulas e senti que tinha muita coisa para fazer até finalizar o
> portifolio então procrastinei bastante, queria ajuda para decidir o que entra
> no portifolio ou nao."
>
> "Alguns Check-list tipo como estruturar o portifolio, e gostaria de um filtro
> de qualidade, e um gerador final, eu não sei se é em PDF ou se só envia as
> fotos, mas seria bom um suporte a mais nessa reta 'final' do curso."

São cinco pedidos, e o quinto ele não fez com todas as letras:

1. **Roteiro** — check-lists de como estruturar o portfólio.
2. **Curadoria** — ajuda para decidir o que entra e o que não entra.
3. **Filtro de qualidade** — alguém ou algo diz se a peça está boa.
4. **Gerador final** — PDF, ou envio das fotos; ele mesmo não sabe qual.
5. **O empurrão da reta final** — "procrastinei bastante". O problema não é só
   falta de ferramenta: é a montanha sem trilha depois da última aula. Um plano
   que entregue 1 a 4 e ignore o 5 resolve o pedido e não resolve o aluno.

## §2 O que a casa já tem

Medido com `python ci/reconhecer.py portfolio portifolio estudio` em
`origin/main` (commit `62f70ba1`), e conferido a mão nos pontos que decidem o
plano:

- **A fila de conferência humana já existe e está no ar.** `/conquistas/marcos`
  recebe a prova do aluno, `/conquistas/interno` é a fila da equipe, com prazo,
  aceite e devolução com motivo escrito em português. É o pedido 3 quase pronto,
  faltando só a peça de imagem. Molde:
  `services/gamificacao/apps/core/templates/gamificacao/marcos.html`.
- **A trilha de marcos reais já prevê o portfólio como degrau:** "obra →
  portfólio → cliente → dólar" (`DECISAO-gamificacao.md` §2).
- **A vitrine pública já foi decidida:** `meshcraft.top/estudio/<apelido>`,
  opt-in, só apelido, obras aprovadas e marcos escolhidos, `noindex` (decisão 3
  da Sessão A, 30/08/2026 — fechada, não se reabre por preferência de agente).
- **A validação em três degraus já foi decidida:** o autor marca "resolveu", um
  monitor confere, o mantenedor entra só no que envolve dinheiro (decisão 5).
- **O texto de tela já pode morar no banco:** o editor de documentos do admin
  (31/08/2026) deixa o mantenedor escrever e versionar sem PR.
- **O sininho e o motor de sequências existem**, então o pedido 5 tem por onde
  chegar ao aluno.

## §3 O que não existe

- **Nenhuma tela desta plataforma recebe arquivo.** Sem `FileField`, sem
  `ImageField`, sem `MEDIA_ROOT`, sem `boto3`, e no `infra/docker-compose.yml`
  os únicos volumes são banco, Redis e certificados. **Custo:** um portfólio de
  modelagem 3D é feito de imagem, então a parte visual do plano depende de uma
  decisão do mantenedor sobre onde os arquivos moram (§6.2) e de um PR de
  infraestrutura próprio. É a maior consequência deste estudo, e a que mais
  muda o desenho.
- **Nada aqui monta PDF.** **Custo:** a saída barata é uma página com desenho de
  impressão (o navegador salva sozinho); o dossiê montado no servidor é
  dependência nova na imagem e vira degrau próprio.
- **O curso não mora no site.** Nenhuma célula serve aula. **Custo:** "quando o
  aluno terminar as aulas" não é medível pela plataforma — o gatilho do pedido 5
  precisa ser declarado (liberação, marco, ou um botão "terminei as aulas"),
  nunca inferido.

*Observação de método:* a primeira execução do `ci/reconhecer.py` respondeu SIM
para "guardar arquivo" e "servir vídeo", os dois falsos. As assinaturas foram
corrigidas e o teste-guarda encena os dois enganos
(`ci/tests/test_reconhecer.py`). Falso SIM apaga trabalho real da escada, e foi
por pouco que não apagou daqui.

## §4 Onde a coisa mora

**Opção A — célula nova. ESCOLHIDA pelo mantenedor em 01/09/2026, e em
02/09/2026 ela deixou de ser a casa do PORTFÓLIO para ser a casa das PÁGINAS
do aluno: `pages`.**

> **A emenda de 02/09/2026, e por que ela é melhor que o plano original.**
> O mantenedor perguntou se, em vez de uma célula por coisa pedida na Caixa,
> não havia um lugar único onde todas nascessem. Há, e o raciocínio dele fecha
> a questão do nome: *"quero `pages` porque podemos criar todo tipo de
> ferramentas, portfólio, estúdio, e etc"*. Um nome específico (`portfolio`,
> `ferramentas`) excluiria o que não é ferramenta nem portfólio; o guarda-chuva
> é o ponto.
>
> **O que isso muda de verdade: o custo por pedido do aluno.** O caro nesta
> plataforma nunca foi a tela, foi a FUNDAÇÃO — banco novo, provisionamento,
> rota, e o passo manual que só o mantenedor executa. Uma célula por sugestão
> cobraria esse pedágio a cada pedido. Com a casa guarda-chuva ele é pago UMA
> vez: da segunda página em diante, o custo é um PR de tela e zero passo dele.
>
> **Dois endereços, uma casa:**
> - `meshcraft.top/pages/...` — a área do aluno logado. O portfólio é a
>   primeira página; as próximas entram ao lado.
> - `meshcraft.top/estudio/<apelido>` — a vitrine pública, **decisão 3 da
>   Sessão A (30/08/2026), preservada**. Endereço curto de propósito: é o link
>   que o aluno manda ao cliente, e `/pages/estudio/joao` seria pior no chat de
>   um freelancer. Os dois prefixos apontam para a mesma célula no Traefik.
>
> **O que NÃO se conclui daqui:** que toda sugestão da Caixa vira uma página
> em `/pages`. Os pedidos se dividem em quatro tipos, e só um mora aqui — aula
> nova é conteúdo do curso; material para baixar é documento no editor;
> mudança em tela existente se faz onde ela já está. Ver `DA-IDEIA-A-OBRA.md`,
> estação 2.
>
> **A alternativa foi levantada pelo mantenedor e RECUSADA por ele em
> 02/09/2026, no mesmo dia: não reabra.** A pergunta dele foi boa e merece a
> resposta registrada, porque ela volta: *"e se as páginas fossem criadas na
> própria célula `sugestoes`, com endereços diferentes? já cansei de criar
> novas células"*. Tecnicamente funciona (endereço e célula são coisas
> separadas: `/docs` e `/mapa-ia` já apontam para a célula `admin`), e a
> decisão dele de guardar foto por LINK derrubou o argumento mais forte a favor
> da casa própria, que era o isolamento do armazenamento de imagem. Ainda
> assim ele escolheu a casa nova, informado de que ela custa cinco degraus e um
> passo manual dele, e de que dentro da Caixa custaria zero.
>
> **O que sustenta a escolha dele: `pages` é a ÚLTIMA casa nova.** O pedágio da
> fundação é pago uma vez e nunca mais; da segunda página em diante nenhuma
> sugestão da Caixa pede célula nem passo do mantenedor. E a Caixa continua
> intocada: publicar uma página nova não republica a casa da voz dos alunos,
> que é o risco que a alternativa trazia.
>
> **Nome da célula = nome da rota (`pages`), de propósito.** O par
> `/conquistas` ↔ `gamificacao` já custa uma tradução mental a cada leitura;
> não se cria um segundo.

A obra do aluno ganha casa própria e a página pública sai dela; a gamificação
só recebe o evento e acende o marco.

- *A favor:* a gamificação tem **critério de morte declarado** (`DECISAO-gamificacao`
  §10) — ela pode ser desligada um dia, de propósito. O portfólio é o que o
  aluno mostra a cliente pagante e não pode ser desligado junto. Guardar imagem
  traz preocupações novas (disco, backup, conteúdo impróprio, dado pessoal) que
  merecem canto próprio, e é a Muralha 1 e 2 da Lei 2. O exemplo do
  `FORMATO-CHANGESPEC.md` §6 já nomeia `CS-PORTFOLIO-0001` numa célula própria.
- *Preço:* 1 gênese (~22 arquivos, label `arquitetural`), 1 contrato, 1
  provisionamento, 1 PR de infra e **1 passo manual do mantenedor** na VPS.

**Opção B — dentro de `gamificacao`.** O portfólio entra como mais telas de
`/conquistas`, aproveitando a fila de validação que já existe.

- *A favor:* zero fundação, zero passo manual, começa quatro degraus antes.
- *Preço:* a maior célula do projeto fica maior; o portfólio passa a viver e
  morrer com o andaime; e a célula que conta pontos herda o disco de imagens.

**Nos dois casos, a mesma regra:** a peça tem UMA casa. O portfólio não guarda
cópia de medalha, a gamificação não guarda cópia de peça, e a tela que precisa
das duas pergunta por HTTP com falha ABERTA (o mesmo desenho já usado entre
fórum e gamificação).

## §5 A escada

| # | Entrega | O que muda para o aluno | Célula | Arqs |
|---|---|---|---|---|
| **S** | **Conversa de fronteira com o mantenedor** | nada | — | 0 |
| 00 | O mapa para IA cita a célula que nasce (canário do lote) | nada | painel | 2 |
| 01 | Gênese da célula (esqueleto, INV-P12, healthz, celulas.yml, manifesto, rollback, constituição) | nada | pages | ~22 |
| 02 | Modelos: portfólio, peça, item de conferência, estado do aluno (numa app própria dentro da casa) | nada | pages | ~14 |
| 03 | Contrato congelado + eventos `pages.portfolio.*` | nada | contracts | ~7 |
| 04 | `infra/provisionar-pages.sh` + env exemplo (SOZINHO) | nada | infra | ~5 |
| **H** | **Passo manual: banco, role e env na VPS** (bloco único, fail-closed) | nada | mantenedor | 1 linha |
| 05 | Compose + Traefik `/pages` e `/estudio` + inventário de rotas no MESMO PR | o endereço responde | infra | ~3 |
| 06 | Porta e sessão (repassa o cookie à `identidade`, nunca assina) + tela mínima | abre a Prancheta e é reconhecido | pages | ~12 |
| 07 | A Prancheta: cinco etapas, listas de conferência lidas do banco | vê o roteiro e marca o que fez | pages | ~12 |
| 08 | Peças por link, com legenda, ordem e destaque | monta o portfólio | pages | ~10 |
| ~~09~~ | ~~Envio de imagem no servidor~~ — **fora, por decisão de 01/09/2026** (§6.2). Volta a existir no dia em que o link colado doer | — | — | — |
| 10 | O semáforo por peça, calculado das respostas objetivas | vê o que falta em cada peça | pages | ~8 |
| 11 | Pedido de conferência + tela da equipe (molde dos marcos) | manda para a escola olhar | pages | ~12 |
| 12 | Selo "conferido pela escola" + evento + carta no sininho | recebe o selo e fica sabendo | pages | ~9 |
| 13 | `/estudio/<apelido>` (opt-in, `noindex`, despublicar imediato) + versão de impressão | o link para mandar no chat | pages | ~12 |
| 14 | O dossiê em PDF montado no servidor | baixa o arquivo para anexar | pages | ~7 |
| 15 | A gamificação escuta o evento e acende o marco "portfólio" | o marco acende na trilha | gamificacao | ~8 |
| **16** | **Os guias no editor de documentos** (rascunho pronto, texto dele) | lê o guia com a voz da escola | admin | ~4 |
| 17 | A sequência que convida quem terminou as aulas | recebe o convite em vez de travar | mensageria | ~9 |
| 18 | O caminho no menu e na home logada | encontra sem procurar | funil | ~6 |

Se a resposta do §6.1 for a opção B, saem 01, 03, 04, 05 e o passo H.

## §6 O que volta para o mantenedor

**1. A fronteira — RESPONDIDA em 01/09/2026 (célula própria) e EMENDADA em
02/09/2026: a casa chama-se `pages`, é o guarda-chuva das páginas do aluno e é
a última casa nova do site. O portfólio é a primeira página dela. A emenda está
por extenso no §4.**
Com ela vêm a gênese, o contrato, o provisionamento, o PR de infra e o passo
manual na VPS, e o portfólio deixa de depender da vida do sistema de pontos.

**2. Onde as fotos moram — RESPONDIDA em 01/09/2026: só o link colado.**
O aluno cola o endereço do render que já está no Drive, no ArtStation ou onde
ele guarda. A recomendação deste estudo era o disco da VPS; o mantenedor
escolheu o link, informado do preço, e o preço é este, escrito aqui para
ninguém redescobri-lo por acidente:

- **link de aluno quebra**, e quando quebra o portfólio dele fica com um buraco
  que a escola não consegue consertar. Mitigação barata, que cabe na entrega 08:
  a Prancheta confere o link quando ele é colado e avisa o aluno se ele parar de
  responder depois (medição periódica, aviso no sininho, nunca apagar sozinho);
- **a página pública passa a exibir imagem de domínio de terceiro.** Isso é
  decisão de segurança de tela, não detalhe: a política de conteúdo da página
  precisa permitir imagem externa de forma controlada, e nenhuma outra tela
  desta plataforma faz isso hoje. Trate no PR da entrega 13, com teste;
- **a escola não controla o que está do outro lado do link.** O selo "conferido
  pela escola" passa a valer para o que o monitor VIU no dia da conferência, e
  o texto do selo precisa dizer isso.

A porta para mudar de ideia fica aberta e barata: o campo do link e o campo de
uma imagem hospedada por nós cabem no mesmo modelo, e a entrega 09 volta à
escada sem reescrever nada do que vier antes. **Não a construa antes de ele
pedir.**
**3. Assinar a obra na Caixa** (estação 4 de `DA-IDEIA-A-OBRA.md`), conferindo
   antes que o e-mail dele está em `SUGESTOES_APROVADORES`.
**4. O texto dos guias** — ou a aprovação do rascunho que a entrega 16 deixa
   pronto no editor.

## §7 O que ninguém pode inventar

- Nota, estrela, ranking ou voto popular em portfólio de aluno (`DECISAO-gamificacao`
  §8 já proíbe voto popular e ranking público; aqui vale para peça também).
- Detecção de "isto foi feito por IA" (proibida por escrito, §8).
- Trancar aula ou conteúdo atrás de check-list, ponto ou nível (invariante 3 da
  economia: aula nunca fica atrás de jogo).
- E-mail, telefone ou nome completo na página pública; padrão é privado e o
  `noindex` não é negociável.
- Guardar a peça em duas células.
- Travessão em texto que o aluno lê (`ci/travessao.py`).
- Marco real pagando XP (decisão 7 da Sessão A: vale zero, de propósito).

## §8 Os critérios da escola, rascunho da professora (05/09/2026)

O mantenedor repassou o texto abaixo numa caixa de pergunta estruturada em
05/09/2026, respondendo à pergunta sobre quem escreveria os critérios do guia:
quem escreveu foi a professora da escola. O texto está aqui como ela mandou,
sem correção e sem reescrita, porque é a fala dela e o valor está justamente
em ser o que ela escreveu.

> No curso eu ensino o aluno a criar diversos tipos de modelos, sendo eles armas, carros, cabelos, acessórios, animais, e etc
>
> Mas deixo claro que é interessante que a pessoa TENTE criar todos esses modelos, mas sempre tem alguns que gostamos mais de modelar do que outros, e que também temos mais facilidade
>
> E então o aluno deve escolher PELO MENOS 3 desses "tipos de modelos" (animais armas etc) e criar mais 3 variantes, exemplo
> "Eu tenho mais facilidade em criar acessórios, animais e armas"
>
> Então você vai criar 3 animais, 3 acessórios e 3 armas, pelo menos, para começar um bom portfolio
>
> Os modelos devem ser low poly ou high poly? (mais simples ou detalhados)
>
> O ideal é que sejam high poly, para impressionar o cliente e mostrar o máximo do seu potencial, mas você também pode criar algumas variações mais simples, mas o ideal é que a maioria seja de fato, high poly
>
> Posso usar um dos modelos do portfólio, do mesmo que eu aprendi na aula?
>
> É bom que você crie 3 variações que não se pareçam com a aula, para evitar que repita muitos modelos em portfólio
>
> OBS: Mas isso é só um rascunho, ainda podemos mudar isso mais pra frente

**O que esse texto vira dentro da obra.** São quatro regras objetivas, e é o
que a lista de conferência do aluno passa a medir: escolher pelo menos 3 tipos
entre os que o curso ensina (armas, carros, cabelos, acessórios, animais e os
demais); entregar pelo menos 3 peças de cada tipo escolhido, o que dá 9 peças
no mínimo; ter a maioria das peças em high poly, com algumas variações mais
simples permitidas; e não repetir o modelo feito na aula, nem entregar peça que
se pareça com ele. É isso que o degrau 07 da escada do §5 lê do banco para
montar a lista de conferência, e é isso que o degrau 16 publica como guia com a
voz da escola.

**Duas ressalvas, para ninguém errar depois.** A própria professora marcou o
texto como rascunho, e ele pode mudar. E a casa definitiva dele é o editor de
documentos do admin (degrau 16 da escada): no dia em que o texto for para lá,
esta seção passa a apontar para lá em vez de guardar cópia, porque nenhum fato
do projeto mora em dois lugares.
