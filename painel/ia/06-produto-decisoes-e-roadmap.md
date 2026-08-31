# painel/ia — 06. Produto, Decisões e Roadmap

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Resumo curado — a fonte
> de verdade é `docs/decisoes/`, `docs/caixa-de-sugestoes/`, `docs/i18n/`,
> `docs/notificacoes/`, `docs/futuro/`. **Nota metodológica importante: cada
> "status" abaixo é o que o documento afirmava na data em que foi escrito —
> nenhum desses documentos é atualizado depois. São leis e fotografias
> datadas, não painéis vivos. O estado real e atual de qualquer feature deve
> ser conferido em `painel/registros/`, nunca inferido daqui.**

## Mapa de features

### Identidade / login (célula `identidade`)

**O que é:** dona do login do site via Google, do cookie de sessão, e da
resposta "quem é o dono desta sessão?".

**Decisão-chave:** o invariante central é **"reconhecer não é autorizar"** —
reconhecimento falha ABERTO (identidade fora do ar → site mostra "Entrar" e
continua abrindo normal, o raio de explosão de 1 célula não pode virar o
site inteiro), autorização falha FECHADA e nunca deriva da resposta de
sessão (cada célula dona de um recurso decide sozinha o que a pessoa pode).
Papel é sempre derivado por requisição, nunca gravado. Esta separação existe
para impedir que um fail-open de reconhecimento vire fail-open de
autorização — descrita nos próprios docs como "a família do bug mais caro da
Fase D" (ver [02](02-armadilhas-e-padroes-recorrentes.md), padrão 4).

**Trajetória (relevante para não reabrir a discussão):** passou por 3
decisões sucessivas — sessão vivendo só dentro da Caixa de Sugestões (23/08)
→ "costura primeiro, célula depois" para não pagar o preço de uma célula
nova antes de saber se valia a pena (24/08) → célula `identidade` de fato
(25/08), com desenho que evitou migração de dado (a Caixa manteve sua tabela
local como snapshot casada por e-mail). Cada par de células que ganha acesso
ao e-mail completo precisa ser registrado por escrito com o motivo — hoje só
`sugestoes` e `admin`.

### Área administrativa (célula `admin`)

**O que é:** `meshcraft.top/admin/` — métricas vivas por célula, galeria de
painéis históricos, usuários, cursos (leitura), configuração, roadmap
interno.

**Decisão-chave:** reaproveita o login do site sem login próprio, com o modo
de falha **invertido** do público (fail-CLOSED, porque aqui é autorização) —
autoriza por lista de e-mails no env, nunca pela resposta de sessão sozinha.
Métricas são por **HTTP direto em tempo real**, não por evento (mais caro —
5 sessões extras de Rito de Contrato — mas o mantenedor quer números sempre
exatos, não com segundos de atraso).

**Este é o melhor exemplo documentado da filosofia "sempre completo":** o
plano passou por uma banca de 4 cadeiras independentes (arquitetura,
segurança, SRE, produto); a cadeira de produto propôs uma alternativa
reduzida ("O Mirante": 1-2 PRs, zero célula nova) — **supersedida no mesmo
dia** pela decisão de escopo completo (~30 merges), mesmo sabendo do custo,
quebrando de novo o congelamento arquitetural de propósito. Proibições
permanentes: nada de vendas/checkout/pagamentos sem ordem explícita,
somente-leitura no catálogo, sem login próprio/domínio separado/botão de
emergência.

### Sininho / Notificações (célula `notificacoes`)

**O que é:** um sino ao lado do nome, em toda página do site.

**Decisões em cadeia, e os porquês:**
1. Célula própria — terceira vez que o congelamento arquitetural foi aberto
   deliberadamente (depois de `sugestoes` e `identidade`). Um sino em toda
   página precisa custar uma pergunta barata mesmo com dez células
   publicando.
2. **A garantia de entrega muda de latência, não de durabilidade**: o fato
   nasce na mesma transação (outbox), a entrega passa a ser em segundos e
   rastreável em vez de instantânea. Duas alternativas descartadas por
   escrito: espelho local+central (duas verdades sobre "lido") e chamada
   HTTP síncrona na transação (violaria a Lei 3 de não acoplar células no
   caminho crítico).
3. **O fan-out muda de endereço**: a célula de origem publica "uma carta por
   pessoa" (evento endereçado, em lote); a central fica deliberadamente
   "burra" — só escreve uma linha por carta recebida. Mantém custo O(1)
   mesmo com centenas de destinatários.
4. Quem mexeu na ideia é sempre **guardado**, nunca **mostrado** ao aluno (a
   tela sempre diz "a equipe") — mostrar depois é reversível, não guardar
   não é.

### Internacionalização (i18n)

**O que é:** inglês, pt-br e es hoje; outras variantes de português depois.

**Decisão mais sensível a reabertura por engano:** o idioma **padrão** mora
na raiz nua sem prefixo (`meshcraft.top` = inglês); todo outro idioma leva
prefixo (`/pt-br/`, `/es/`); `/en/...` é 404 proposital, não redirecionamento.
Isto **revogou** uma recomendação anterior unânime de 4 IAs consultadas (que
mandava até o inglês levar prefixo, pelo argumento de que trocar o idioma
padrão no futuro viraria "uma linha de dado"). O mantenedor decidiu
pessoalmente pelo endereço mais limpo, aceitando que se o idioma padrão
mudar um dia, deixa de ser barato. **Se o código parecer "errado" contra uma
recomendação antiga de consultoria, o código está certo** — foi decisão
consciente, não deriva.

Catálogo de tradução em YAML "key-major" (um arquivo por página, todos os
idiomas dentro). Vale como método replicável: o próprio plano conclui que
"convergência entre LLMs mede convencionalidade, não correção" — o valor
real veio de **verificar** cada afirmação contra o repositório real (rodar o
parser, checar a versão do Traefik), não de contar votos entre modelos —
isso inclusive achou erros técnicos concretos nos pareceres externos (ex.:
sintaxe de rota do Traefik v2 que não existe mais na v3.4 usada aqui).

### Caixa de Sugestões (internamente "Central de Evolução"/"EVO")

**O que é:** ferramenta de voice-of-customer em `/forms/sugestoes/` — alunos
sugerem, votam, comentam, acompanham status. **O nome interno "EVO" é
deliberadamente camuflado** para o usuário final; o nome público fechado em
23/08/2026 é "Caixa de Sugestões" — nenhuma sessão deve tentar corrigir ou
unificar esse vocabulário.

**Decisões-chave:**
- **Identidade:** "o Google prova QUEM É; a célula `alunos` decide SE PODE"
  — duas perguntas, dois lugares. Quem entra é só a matrícula `ativa`:
  `suspensa` saiu em 28/08/2026 e `reembolsada` saiu em 31/08/2026, esta
  última por decisão do mantenedor revertendo a dele próprio de 24/08
  (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`). Staff é lista de
  e-mails, não precisa de matrícula.
- **Aprovação de ChangeSpec:** só o mantenedor, mecanicamente, via lista de
  aprovadores — lista vazia é fail-closed.
- **Quem é avisado:** todos que interagiram (autor + votantes +
  comentaristas), não só o autor — decisão que depois motivou o próprio
  plano de notificações.

## O mecanismo de ChangeSpec

O corredor formal entre uma ideia aprovada e código: *sugestão → decisão de
produto (1 linha) → ChangeSpec (`docs/changespecs/CS-<CELULA>-<NNNN>.md`) →
implementação*.

**Regra de segurança central, não negociável:** quem escreve/aprova o
ChangeSpec **nunca** é o mesmo agente que o implementa — se fosse, o
documento viraria formalidade que o agente preenche para si mesmo, e a
propriedade de segurança desapareceria. Campos obrigatórios incluem
`FORA DO ESCOPO` (nunca vazio) e `CÉLULAS PROIBIDAS` (lista exaustiva, nunca
"nenhuma outra"). Depois de aprovado, é imutável — mudança de escopo vira
arquivo novo (`-v2`), nunca edição.

O gatilho é mecânico e redundante em três degraus (serviço, `save()` do
model, trigger no Postgres): status só sai de `PLANEJADO` para
`EM_DESENVOLVIMENTO` se existir ChangeSpec aprovado referenciando aquela
sugestão. A célula não lê o repositório em runtime — guarda só um registro
mínimo (quem aprovou, quando, link); quem confere o documento em si é gente.

## Checkout / Pagamentos

**Diretiva crítica, permanente, desde 22/08/2026: nunca propor ou retomar
pagamento/checkout/Mercado Pago por iniciativa própria** — só quando o
mantenedor disser explicitamente que o site vai vender. Isto não é sobre
reduzir escopo (a filosofia geral é sempre fazer completo) — é sobre
**ordem**: o site/conteúdo vem antes da venda. Se você é uma IA sugerindo
melhorias e este mapa te levou a esta célula, **não proponha trabalho aqui**
a menos que o pedido do usuário seja explicitamente sobre pagamentos.

Contexto técnico histórico (não é convite para retomar): havia um bug grave
de fail-open onde respostas de erro do Mercado Pago eram tratadas como
sucesso, produzindo "intents fantasma" com QR vazio — corrigido e citado
como o bug mais caro da Fase D, o exemplo canônico de "2xx não é sucesso"
nas bordas externas (ver [02](02-armadilhas-e-padroes-recorrentes.md),
padrão 4).

## PLANO-10X e suas alavancas

Síntese de três auditorias internas, quatro consultorias externas e duas
varreduras de código — não vinte melhorias de 10%, poucas alavancas onde a
linha de base medida está uma ordem de grandeza longe do possível. Premissa
inegociável: nenhuma alavanca cria célula, rito ou abstração nova.

1. **Throughput da fábrica** — o gargalo real era a janela de atenção
   humana (mediana 22min/média 264min por merge), não a CI (15-70s); lotes
   de 4-6 células em paralelo passaram a ser possíveis.
2. **Custo de contexto por despacho** — de ~32k tokens de governança antes
   da primeira linha de código para meta de ~8k. **Esta é a alavanca cujo
   primeiro movimento foi particionar `ARMADILHAS.md`** em `armadilhas/` +
   índice gerado — a mesma lição que motivou a estrutura deste próprio mapa
   em `painel/ia/`.
3. **Confiança mecânica** — a tese do projeto ("leigo opera com segurança
   via agentes") depende de portões que mordem de verdade; a auditoria
   original mediu vários portões-teatro, hoje corrigidos.
4. **Detecção de falha** — de "o cliente reclama" para "o sistema avisa".
5. **O gargalo não é de engenharia** — quatro consultorias unânimes: o
   maior risco é "a fortaleza perfeita que ninguém visita", não bug
   técnico. Recomendações: validar demanda antes de plataforma, lançar só
   com Pix, modo concierge.

## PROJETO-PORTAO-DEPLOY

"O required check que o GitHub não vende": sem branch protection nativa
disponível por muito tempo (limite de plano), todo PR podia ficar vermelho e
ainda ser mergeado pelo botão. Resposta: já que não dava para impedir um
merge ruim, dava para impedir um **deploy** ruim — é o deploy que alcança o
cliente. Provado ao vivo em 22/08/2026: um PR vermelho de propósito,
mergeado pelo botão, gerou deploy `skipped`; revertido, gerou deploy
`success`. Ver detalhe mecânico em
[05 — infraestrutura e deploy](05-infraestrutura-ci-e-deploy.md).

## Decisões que uma IA nova pode ficar tentada a reabrir, mas não deve

1. **Nome camuflado "Caixa de Sugestões"** (interno: EVO) — deliberado, não
   é rebranding pendente.
2. **Filosofia de escopo sempre completo** — já derrubou explicitamente uma
   recomendação de MVP de uma auditoria própria da área admin.
3. **Merge é trabalho do agente**, não do mantenedor — a lei antiga
   (aprovação humana prévia) era literalmente inexecutável neste GitHub.
4. **Idioma padrão sem prefixo na raiz** — revogou deliberadamente uma
   recomendação unânime de 4 IAs.
5. **"Reconhecer não é autorizar"** — nenhuma célula deve tratar a resposta
   de sessão como crachá de permissão.
6. **"Pagamento por último"** — não propor nem retomar checkout/pagamentos
   por iniciativa própria.
7. **Sem célula de auth genérica nem Django admin nativo** — já avaliado e
   descartado.
8. **Área admin sem login próprio, domínio separado ou botão de
   emergência** — três alternativas descartadas por decisão explícita.
9. **Painéis antigos (`arquivos/painel-*.html`) são lápides** — não
   atualizar, não criar novos.
10. **O e-mail do aluno nunca circula entre células** — vive numa linha só
    na `identidade`; qualquer atalho que o faça viajar em eventos é
    retrocesso.
11. **Fan-out de notificação acontece na origem, a caixa central é burra**
    — não mover essa responsabilidade de volta ao centro.
12. **Aprovação de ChangeSpec é humana, nominal e exclusiva do mantenedor**
    — a separação escritor/implementador/aprovador é propriedade de
    segurança, não burocracia a simplificar.
13. **GitHub Pro é impossibilidade, não custo adiado** — não sugerir "só
    assine o Pro"; o portão de deploy já é a resposta arquitetural ao
    mesmo problema de fundo.
14. **O congelamento arquitetural só o mantenedor reabre**, sessão a
    sessão — já foi aberto deliberadamente três vezes (`sugestoes`,
    `identidade`, `notificacoes`/`admin`); isso não o torna "regra que não
    vale mais" para uma quarta vez sem pedido.
