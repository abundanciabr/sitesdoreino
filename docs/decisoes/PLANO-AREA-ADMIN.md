# PLANO — Área Administrativa (`meshcraft.top/admin/`)

> **Proposta de arquitetura escrita a pedido do mantenedor**, 25/08/2026, com ele
> presente na sessão. Vira lei executável quando ele disser "aprovado" — a partir
> daí, o despacho de gênese promove os §2–§4 a `DECISAO-celula-admin.md` e a
> escada do §6 começa a andar. Até lá, **nenhuma linha de código deste plano
> existe**, e nada aqui autoriza começar sem a palavra dele.
>
> Pedido original, nas palavras dele: *"uma área administrativa no sistema, tipo
> meshcraft.top/admin/, onde teremos vários painéis (…) métricas, roadmaps,
> planos, usuários, gestão de cursos, vendas, marketing (…) além de formulários
> de configuração do site, sistema, e outras coisas. (…) acho que será mais uma
> célula."*
>
> ⚠️ **AUDITADO EM 25/08/2026 POR UMA BANCA DE QUATRO CADEIRAS — leia o
> `PARECER-BANCA-AREA-ADMIN.md` ANTES de agir por este plano.** Três cadeiras
> aprovaram com ressalvas; a de produto recomendou uma versão reduzida ("O
> Mirante", parecer §4) — **superseded no mesmo dia** por
> `DECISAO-filosofia-de-escopo.md`. As correções de **fato** já entraram neste
> documento, marcadas com **[BANCA]**.
>
> ✅ **AS SEIS PERGUNTAS DO §9 ESTÃO TODAS RESPONDIDAS (25/08/2026)**, colhidas
> por pergunta estruturada de múltipla escolha — formato que o mantenedor
> confirmou como o certo para toda decisão dele daqui em diante (`CLAUDE.md`,
> "Como trabalhar com o mantenedor"). As respostas já foram aplicadas nas
> seções técnicas abaixo, marcadas **[DECIDIDO 25/08]**. **Falta só ele dizer
> "aprovado" para o PR 1 começar.**

---

## §1 — O que é (e o que NÃO é)

**É:** uma casa única, atrás do login do site, onde o mantenedor — e só ele, e
quem ele autorizar — enxerga e opera a plataforma: painéis de métricas vivas,
galeria de painéis de status (como o `painel-retomada.html`), lista de usuários,
gestão de cursos/ofertas, formulários de configuração, roadmap interno.

**Não é:**

- **Não substitui o `painel-fundacao.html` local.** O painel vivo é atualizado
  pelos agentes várias vezes por sessão, sem deploy — mudá-lo para a web
  custaria um merge+deploy por atualização. Ele continua local e obrigatório
  (lei do `CLAUDE.md`); a área admin ganha uma **galeria** que recebe cópias
  datadas (§4.3).
- **Não é o Django admin** (`django.contrib.admin`). O admin nativo exige o
  sistema de usuários do Django; a nossa sessão mora na célula `identidade`.
  As páginas seguem a receita R6 da casa (ilha Alpine, mobile-first).
- **Não toca pagamento.** Vendas, checkout e Mercado Pago estão congelados por
  diretiva do mantenedor (22/08/2026) até ele dizer que o site vai vender. A
  seção de vendas existe no mapa (§4.6) como espaço reservado, e **nenhum
  despacho a inicia** antes dessa ordem.

## §2 — A decisão de arquitetura: célula própria `admin`

O palpite do mantenedor está certo, e pelos motivos que a Constituição já
escreveu:

- **Lei 2 (raio de explosão = 1 célula):** a área admin caindo não pode derrubar
  a vitrine, e um deploy do site não pode derrubar a ferramenta de operação.
- **Muralha de código:** admin vai crescer por anos (painel novo, formulário
  novo). Dentro do `funil` ou da Caixa, cada crescimento colidiria com a célula
  hospedeira no portão de "1 PR = 1 célula".
- **Muralha de dados:** auditoria, painéis enviados e configurações merecem
  banco próprio (`admin_db`) — e a Lei 2 garante que a connection string do
  admin *não consegue* ler o banco de ninguém: métricas entram por contrato
  HTTP, nunca por baixo (§5).

Alternativas olhadas e descartadas:

| Alternativa | Por que não |
|---|---|
| Páginas estáticas atrás de BasicAuth no Traefik | barato, mas sem formulário, sem dado vivo, senha compartilhada, zero auditoria — não cabe no pedido ("formulários de configuração") |
| Seção dentro do `funil` | o `funil` é a vitrine pública e catch-all de N domínios; misturar operação com vitrine quebra o raio de explosão e entope a muralha de código |
| Reaproveitar a Caixa (`sugestoes`) | a Caixa é produto para aluno, com moderação própria; a EVO-30 acabou de lhe dar um rosto público — operação interna é outro morador |

**Nome da célula: `admin`. Rota: `Host(meshcraft.top) && PathPrefix(/admin)`,
prioridade 10, `SCRIPT_NAME=/admin`.** O `Host(...)` explícito é deliberado e
copia o achado da cadeira de IAM na rota da `identidade`
(`infra/traefik/dynamic/plataforma.yml`): sem ele, qualquer domínio apontado
para a VPS serviria a porta administrativa da plataforma. O segmento `admin`
não tem forma de idioma — passa nas regras A e B do guarda de rotas; só o
inventário precisa crescer (armadilha 089).

## §3 — A porta: quem entra, e o que acontece quando algo falha

A área admin **não tem login próprio** — usa o login do site, como qualquer
página (era exatamente o mandato da célula de identidade):

1. Visitante abre `/admin/…` sem sessão → **302** para a tela de login do
   `funil` com `?next=` do caminho pedido (o `funil` já sanitiza `next` para
   caminho local — `services/funil/apps/core/views.py:177`). Entra pelo Google,
   volta para onde estava.
2. Com o cookie `meshcraft_sessao`, a célula `admin` pergunta à `identidade`
   **pela rede interna do Docker**: `GET /interno/sessao/completa` (a resposta
   com e-mail). Isso exige um par novo de tokens — `TOKENS_ACEITOS_ADMIN` e
   `TOKENS_COMPLETOS_ADMIN` — que é **só variável de ambiente** na `identidade`
   (`config/settings.py:108–123` monta as listas por prefixo do env; zero
   código). A lei da identidade exige registrar por escrito cada par novo com
   acesso a e-mail (`DECISAO-celula-de-identidade.md` §6.3): o registro entra
   no PR 3 da escada, com este motivo — *a porta administrativa autoriza por
   lista de e-mails, e e-mail é o único identificador estável que o mantenedor
   consegue gerir sozinho num env*.
3. O e-mail é conferido contra **`ADMIN_EMAILS`**, lista própria no env da
   célula `admin`. **A resposta da `identidade` nunca é autorização** — nem o
   campo `papel`, nem o e-mail por si: quem decide quem entra é a lista DESTA
   célula, na hora, derivada e nunca gravada (mesma promessa da EVO-01 §4:
   trocar quem é admin = editar env + reiniciar).

**Modos de falha — deliberadamente o INVERSO do site público:**

| Situação | Site público (`funil`) | Área admin |
|---|---|---|
| `identidade` fora do ar | página abre, mostra "Entrar" (fail-OPEN: é reconhecimento) | **302 para o login, nunca abre** (fail-CLOSED: é autorização) |
| Sessão válida, e-mail fora da lista | — | **404**, não 403: para quem não é da casa, `/admin` não existe |
| Sem sessão | — | 302 para o login do site |

Isto é a aplicação literal do invariante *reconhecer não é autorizar*
(`DECISAO-onde-mora-a-sessao.md` §4) — e cada linha da tabela nasce com
teste-guarda no mesmo PR (Lei 8).

**Toda escrita feita pela área admin gera linha de auditoria** em tabela
append-only (quem, quando, o quê, valor anterior) — protegida nas TRÊS metades
que as armadilhas 023 e 079 cobram: `save()`, `QuerySet.update()` e cascade.

**[DECIDIDO 25/08] Mesma origem e mesma sessão do site — com reforços,
não com login próprio.** A parecer §7.4 pôs três caminhos na mesa: mesma
origem, origem separada, ou mesma origem só-leitura. O mantenedor escolheu
mesma origem com proteções extras — não vale a pena duplicar todo o sistema
de login por uma segunda "casa" só para administração. Isso exige três
reforços, respondendo aos achados A1/A4 da cadeira de segurança — **[REVISÃO
25/08] e eles NÃO cabem todos no PR 3**, como a versão anterior deste plano
afirmava: o primeiro é do PR 3, o segundo é um Rito §3 à parte (detalhado
abaixo) e o terceiro é uma decisão já tomada, sem trabalho:

- **CSP própria da célula admin.** Base: `default-src 'self'; script-src
  'self'; object-src 'none'`. **[REVISÃO 25/08] `frame-ancestors` NÃO pode ser
  `'none'` em toda a célula** — a versão anterior deste plano escreveu
  `'none'` e teria recriado, por dentro da célula, exatamente o bug que a
  banca pegou no `frameDeny` do Traefik: `'none'` proíbe enquadramento
  **inclusive de mesma origem**, e a galeria do §4.3 serve painel em iframe
  a partir da própria área admin. Correto: `frame-ancestors 'self'` (ou CSP
  por rota, mais estrita nas páginas que não são enquadradas). O guarda do
  PR 3 tem de medir a galeria renderizando de verdade, não só a presença do
  cabeçalho.
- **Verificação de frescor para escrita**, não sessão curta para o site
  inteiro (mudar `SESSION_COOKIE_AGE` afetaria todo visitante comum). A
  `identidade` passaria a devolver `autenticada_em` em `/sessao/completa`.
  **[REVISÃO 25/08] Isto custa MAIS do que a versão anterior deste plano
  dizia, e o texto errado precisa ser desfeito com todas as letras:** ele
  afirmava que pegaria carona no "mesmo Rito §3 do PR 3, sem PR extra". Não
  existe essa carona — **o PR 3 não toca contrato nenhum**, porque os tokens
  do §3 item 2 são env puro (`TOKENS_ACEITOS_ADMIN`/`TOKENS_COMPLETOS_ADMIN`,
  zero código, conferido no `settings.py` da identidade). Acrescentar
  `autenticada_em` ao `SessionFull` é mudança no **contrato congelado** da
  `identidade` e custa, de verdade:
  - **uma sessão de arquitetura com o mantenedor presente** (Rito §3);
  - **um PR só de `contracts/`**, com a label `contrato`;
  - **um PR de implementação na `identidade`** — que é outra célula, e
    portanto **nunca** poderia caber no PR 3 (muralha "1 PR = 1 célula");
  - e cai na `armadilhas/075`: campo opcional novo com `default=` reprova o
    freeze, e sem cuidado o campo vaza como `""` para o `funil`, que é o
    outro consumidor de `/sessao` hoje.

  **Consequência de ordem, que o plano precisa respeitar:** o PR 3 pode
  nascer com a porta e a auditoria; a verificação de frescor só existe
  depois desse rito. Ou a escrita da área admin espera o frescor, ou o PR 3
  entrega escrita sem esse degrau — **decisão a tomar quando a fase 4
  chegar** (é lá que nasce o primeiro formulário; até a fase 3 a área é toda
  de leitura, e o frescor não protege nada ainda).
- **Nenhum login próprio, nenhum domínio separado** — descartado por
  decisão explícita, não por omissão. Registrar aqui para ninguém reabrir:
  a defesa contra XSS em outra página do site é a CSP acima, não uma
  segunda porta de entrada.

## §4 — O mapa das seções (o produto, por fase)

A UI é **só PT-BR** (o público é o mantenedor) e **nenhuma rota tem forma de
idioma**. Por ser plataforma multissítio (Lei 9), todo painel com dado de site
tem filtro por site — a plataforma é uma, as lojas são N.

| # | Seção | O que mostra/faz | Fase |
|---|---|---|---|
| 4.1 | **Visão geral** | a home: saúde das células (os `/healthz`, de dentro), últimas linhas da auditoria, atalhos | 1 |
| 4.2 | **Métricas** | tiles vivos por célula: sugestões/votos/comentários (Caixa), contas criadas (`identidade`), leads, alunos, cursos no catálogo — federados por contrato (§5) | 2 |
| 4.3 | **Galeria de painéis** | upload de painéis HTML datados (ex.: `painel-retomada.html`), servidos em iframe sandbox; a história do projeto navegável de qualquer lugar | 3 |
| 4.4 | **Usuários** | lista paginada das contas do site (via operação interna nova na `identidade` — Rito §3) | 4 |
| 4.5 | **Cursos & conteúdo** | **[DECIDIDO 25/08] SOMENTE LEITURA.** Mostra ofertas/cursos do `catalogo`, sem formulário de edição — mudar preço ou criar curso continua sendo por PR, como hoje. Reavaliar quando a Meshcraft Academy nascer e houver o que editar de verdade | 4 |
| 4.6 | **Vendas** | **CONGELADA** — nem métricas de checkout/pagamentos. Só nasce quando o mantenedor disser que o site vai vender | — |
| 4.6b | **Público & demanda** (marketing) | **[DECIDIDO 25/08] Liberada, seção própria, fora do congelamento de vendas.** **[REVISÃO 25/08] mas só metade do dado existe hoje** — ver a nota logo abaixo desta tabela. **Existe:** cadastros/leads (model `Lead`), quizzes completados (célula `quiz`), por site. **NÃO existe:** contagem de visitas — não há nenhum modelo de pageview em lugar nenhum do repositório, e construí-la é trabalho novo (middleware de contagem + tabela + decisão de privacidade), não uma leitura de algo pronto | 2 |
| 4.7 | **Configuração** | o que é **dado** (chave-valor por site no `admin_db`; dados do `catalogo`), com formulário. O que é **código/infra** (`sites.json`, Traefik, envs) continua entrando por PR — a seção mostra somente-leitura e aponta o caminho | 4 |
| 4.8 | **Roadmap & planos** | página interna editável (markdown no banco). Não confundir com o roadmap PÚBLICO da Caixa (EVO-31, já no ar): este é o de dentro | 4 |

**[REVISÃO 25/08] A pendência aberta do §4.6b — contagem de visitas.** O
mantenedor liberou a seção de marketing com a informação, dada por mim, de que
o dado "existe hoje". Conferido depois: **existe para cadastros, leads e
quizzes; não existe para visitas.** Nenhuma célula conta acesso a página —
`grep` por pageview/visita nos apps do `funil` e do `leads` não encontra
modelo nenhum. As opções, quando a fase 2 chegar (**decisão do mantenedor, não
do agente**):

- **Construir a contagem** — middleware no `funil` + tabela + agregação por
  site/idioma. É a opção coerente com "sempre completo", e é um despacho
  próprio (não cabe de carona na página de métricas). Tem uma pergunta de
  privacidade embutida: contar visita sem identificar pessoa (contador
  agregado) é simples; contar "visitantes únicos" mexe com dado pessoal e
  merece decisão separada.
- **Nascer sem visitas**, mostrando só o que existe (cadastros, leads,
  quizzes) — e a seção cresce depois.

Enquanto isso não for decidido, **a seção 4.6b não promete visitas**: nenhum
agente deve construir um tile de visitas assumindo que o dado está em algum
lugar, porque não está.

## §5 — Onde os dados moram (as muralhas aplicadas)

- **`admin_db`** (banco + role próprios, `infra/provisionamento-postgres.sql`):
  auditoria, painéis enviados, config chave-valor, textos do roadmap. Nada de
  dado de outra célula copiado sem necessidade.
- **Métricas são federadas por contrato, nunca por banco.** Cada célula
  provedora ganha uma operação de leitura devolvendo meia dúzia de contadores
  com `site_id`, autenticada por token do par. No painel, **fail-open por
  tile**: célula fora do ar = tile "sem dados", a página abre — é leitura de
  vitrine interna, não autorização. **Com orçamento de tempo explícito por tile
  (2,0s, como o `funil` já faz)**, porque "célula fora do ar" e "célula que
  pendura" são falhas diferentes. **[BANCA]** três correções de fato:
  - **O caminho NÃO é uniforme.** `/interno` só existe em `sugestoes` e
    `identidade`; `leads`, `alunos` e `catalogo` montam em `/api/<celula>/`, e o
    mount está gravado no `servers:` do contrato congelado. A regra é *"entra na
    API que a célula JÁ tem"* — **segunda instância `NinjaAPI` é proibida**: o
    exportador só enxerga `config.api.api`, e o endpoint ficaria fora do contrato
    com o freeze verde (`armadilhas/041`).
  - **Não é "sem rota no Traefik".** O Traefik não remove o prefixo, então nas
    células sob `SCRIPT_NAME` a API de máquina **é alcançável pela internet**.
    Medido de fora em 25/08/2026: `/forms/sugestoes/interno/sessao` → **401**,
    `/alunos/api/alunos/matriculas` → **405**, `/interno/sessao` (identidade) →
    **404**. O token protege, mas o endpoint de métricas nasce exposto — exige o
    guarda de 401-sem-Bearer no mesmo PR.
  - **`TOKENS_ACEITOS_ADMIN` sozinho concede ESCRITA.** O conjunto é plano e sem
    escopo: o mesmo token valeria para `POST /leads` e `POST /matriculas`. O par
    do admin entra também em `TOKENS_SOMENTE_LEITURA_<PAR>`, conferido no handler
    — o padrão que a `identidade` já usa para `TOKENS_COMPLETOS` — com
    teste-guarda no mesmo PR. **Isto deixou de ser só prudência**: com o §4.5
    decidido somente-leitura, é a mecanização exata dessa promessa — sem esta
    lista, "só ver" seria só texto.
- **[DECIDIDO 25/08] HTTP direto, tempo real — não evento.** A alternativa
  mais barata foi posta na mesa (um `admin-consumer` fazendo read-model
  sobre os eventos que a Caixa já emite, custando zero Rito de Contrato para
  essa provedora) e o mantenedor escolheu pagar o caminho mais caro — **HTTP
  direto em cada provedora, aceitando as 5 sessões de Rito de Contrato do
  §6** — porque quer os números sempre exatos, não com alguns segundos de
  atraso. Registrado para não ser reaberto: a opção barata foi vista e
  recusada, não esquecida.
- **Cliente HTTP único e reutilizado** (armadilha 082) e **lido em request,
  nunca no `__init__`** (armadilha 097: env no init vira 500 em toda página).

## §6 — A escada de entrega

Copiada do precedente que funcionou (`DECISAO-celula-de-identidade.md` §5),
com os degraus que as armadilhas 076/088/089 provaram serem obrigatórios.

**[BANCA] O custo honesto, corrigido.** A versão original desta seção dizia
"7–9 merges" e "cada PR respeita o orçamento de 15 arquivos". As duas frases
estavam erradas:

- **7–9 merges abre a PORTA (fase 1). O §4 inteiro é da ordem de 30 merges** —
  a fase 2 sozinha são 12–13 PRs (**[REVISÃO 25/08]**: a conta da banca dizia
  11 e esquecera o `quiz`, que o §4.6b precisa). E os "Lotes 6 e 7" citados não
  eram dois exemplos: eram as duas metades do **mesmo** nascimento (9 + 7 = 16
  merges para pôr a `sugestoes` do zero ao ar). Fora da conta, porque dependem
  de decisão dele: a contagem de visitas (§4.6b) e o frescor de sessão (§3,
  +1 sessão e +2 PRs se for construído).
- **O PR 1 tem ~21 arquivos e NÃO cabe em 15.** O esqueleto Django é
  indivisível (meia-célula não passa no `make ci`), e os dois precedentes foram
  **24** (`sugestoes`, #108) e **44** (`identidade`, #142). A saída é a válvula
  que o próprio portão prevê: **label `arquitetural`** — e atenção à
  `armadilhas/077`: abrir o PR já com `--label` **não funciona**, é preciso
  `gh pr close && gh pr reopen` logo depois de criar.

| Passo | Quem | O quê | Notas de mandato |
|---|---|---|---|
| PR 1 | agente | **Gênese**: `services/admin` esqueleto (healthz nas DUAS formas — crua e sob prefixo, settings fail-hard com `TIME_ZONE`, `CSRF_COOKIE_NAME` próprio, `SECURE_PROXY_SSL_HEADER`, Dockerfile, Makefile) + declaração `not-applicable` no `ci/manifesto-de-contratos.json` + **linha no `rollback.yml`** + `constituicoes/AGENTS.admin.md` **[BANCA]** + promoção deste plano a `DECISAO-celula-admin.md` | `.github/` e `ci/` são CODEOWNERS — mandato de gênese, anunciado nominalmente. **Label `arquitetural`** (~21 arquivos) |
| **PR 2a** | agente | **[BANCA] O provisionamento, SOZINHO e ANTES do passo humano**: `infra/provisionar-admin.sh` + bloco no `infra/provisionamento-postgres.sql` + `infra/env/admin.env.exemplo` + `infra/env/identidade.env.exemplo` (as duas chaves novas) + linha **H21** no `ARMADILHAS-OPERACAO.md` §1 | **Corrige o impasse circular do plano original**: o comando do mantenedor busca o script **da `main`** (`curl .../main/infra/...`). Precedentes: #131 (`sugestoes`) e `a55a179` (`identidade`), ambos com o script separado do compose |
| **H21** | **mantenedor** | **UMA LINHA**, não um bloco de colar: `curl` do script + `bash`. Idempotente, sem argumentos, sem perguntas, terminando em `PRONTO:` ou `PAROU POR SEGURANÇA:` com o estado DEPOIS conferido. Cria banco+role `admin`, escreve `env/admin.env`, acrescenta as duas chaves ao `env/identidade.env` | Molde: `infra/provisionar-identidade.sh` (H20, deu certo de primeira). **Bloco de colar multi-linha é proibido** — falhou 3× (H18/H19, `RUNBOOK-LOTES.md` §36). **As duas chaves de token precisam ter o MESMO valor**, senão 403 silencioso |
| **PR 2b** | agente | **Infra**: serviço no `infra/docker-compose.yml` + router/service no Traefik (Host-bound, §2) + cadeia de middleware **própria** do admin **[BANCA]** (o `frameDeny` compartilhado quebraria a galeria do §4.3, e afrouxá-lo enfraqueceria `checkout` e `pagamentos`) + inventário em **três lugares** de `ci/tests/test_rotas_sem_forma_de_locale.py` (`armadilhas/089`) | mandato `infra/` + `ci/`; merge SÓ com H21 conferido — senão o `deploy-infra` reprova **depois** de instalar o compose e devolve o mantenedor ao terminal da VPS |
| PR 3 | agente | **A porta** (§3): middleware fail-closed + página Visão geral + auditoria append-only (com trigger no banco, não só guarda em Python — `armadilhas/079`) + CSP (`frame-ancestors 'self'`, **não** `'none'` — **[REVISÃO 25/08]**) + lista de caminhos isentos **enumerada e guardada por igualdade exata** **[BANCA]** | testes-guarda das três linhas da tabela do §3 no mesmo PR. **Não toca contrato nenhum** — os tokens são env puro; o frescor de sessão é rito à parte (§3) |
| PRs 4+ | agente | **Fase 2 — [REVISÃO 25/08] 12–13 PRs, não 11.** Por provedora **congelada** são **2 PRs** (o Rito §3 proíbe `contracts/` junto com `services/`) **e uma sessão de arquitetura com o mantenedor presente**: `sugestoes`, `identidade`, `leads`, `alunos`, `catalogo` = 10 PRs + 5 sessões. **Some o `quiz`** — que a conta anterior esquecera, e que o §4.6b precisa: ele é `not-applicable` no manifesto, então custa **1 PR e nenhuma sessão**. Mais a página Métricas e a página Público & demanda | **[DECIDIDO 25/08]** cinco sessões com o mantenedor, aceitas — ele escolheu tempo real (§5) sabendo do custo. **Não inclui** a contagem de visitas (§4.6b), que é despacho próprio se ele mandar construir |
| depois | agente | **Fase 3** (galeria, 2–3 PRs) → **Fase 4** (usuários, config, roadmap — 6–9 PRs, 1 despacho por seção, serializados entre si pela muralha "1 PR = 1 célula"; cursos/§4.5 fica mais barato que o estimado por ser somente-leitura) | Fase 4.4 exige Rito §3 na `identidade` |

**Aviso de fenômeno esperado — [BANCA] são TRÊS, não um:**

1. Entre o merge do PR 1 e o fim do PR 2b, o `deploy-celula` fica **vermelho em
   todo merge da célula** com "não tem serviço algum em
   /opt/plataforma/docker-compose.yml" — ERROR de ambiente, não FAIL de código
   (`armadilhas/088`).
2. **O `deploy-infra` reprova a plataforma INTEIRA** se o H21 não tiver criado o
   banco: ele troca os arquivos e só então verifica que todos os serviços estão
   `running`; o container do admin em crashloop derruba a verificação de todo
   mundo, **depois** de o compose novo já estar instalado — e a mensagem manda o
   mantenedor restaurar à mão na VPS. É por isso que o H21 precisa terminar
   conferindo o estado DEPOIS.
3. Nessa mesma janela, `admin` **já aparece no menu de rollback** (a linha entrou
   no PR 1) e **não funciona** — o rollback usa o mesmo `grep` no compose da VPS.
   Não tente usá-lo antes do PR 2b.

O relatório de cada despacho da janela avisa os três ao mantenedor de antemão,
para o vermelho não assustar.

## §7 — Armadilhas já mapeadas deste caminho

| Armadilha | Onde morde aqui | O que o despacho faz |
|---|---|---|
| 035 (15 arquivos) | gênese + porta + páginas não cabem num PR | a escada do §6 já divide |
| 076 (rollback.yml lista fixa) | célula nova sem linha = sem rollback às 2h | linha no PR 1, com mandato |
| 088 (compose da VPS) | deploy-celula vermelho até PR 2 + H21 | ordem do §6; avisar o vermelho esperado |
| 089 (inventário de rotas) | segmento `admin` novo | atualizar inventário no PR 2 |
| 081 / 083 / 102 / 029 | célula sob `SCRIPT_NAME`: `reverse()` no teste, `/static` 404, `{% static %}` indo à célula errada, healthz 404 | copiar as soluções da `sugestoes` (mesma anatomia; `LICOES.md` dela) |
| 024 / 086 | middleware da porta interceptando `/healthz` (e a gêmea reescrita) | isenção testada nas duas formas |
| 097 | cliente da `identidade` lendo env no `__init__` | env em request; teste com env ausente |
| 082 | um `SSLContext` por chamada | cliente httpx único da célula |
| 075 | campo novo em `/interno/metricas` de contrato congelado | Rito §3, sem `default=` esperto |
| 023 / 079 | auditoria "imutável" furada por `update()` ou cascade | as três metades guardadas no PR 3 |
| 099 | hora de Chicago em painel de métricas | `TIME_ZONE` explícito na gênese |

## §8 — O que fica decidido para o próximo agente (quando aprovado)

1. **Lista própria autoriza; resposta de sessão nunca.** `ADMIN_EMAILS` no env
   da célula `admin` é a única fonte de "pode entrar". Papel derivado, nunca
   gravado.
2. **A porta é fail-closed** — o contraste com o fail-open do `funil` é
   deliberado e tem teste-guarda: na dúvida, a área admin NÃO abre.
3. **Nada de vendas/checkout/pagamentos** — nem tile de métrica — até ordem
   explícita do mantenedor. Quem quiser começar por aí está fora de mandato.
4. **Toda escrita da área admin passa pela auditoria.** Formulário novo sem
   linha de auditoria não mergeia.
5. **O `painel-fundacao.html` local continua vivo e obrigatório** — a galeria
   (§4.3) recebe cópias datadas, não o substitui.
6. **Métricas jamais leem banco alheio** — entram por contrato HTTP em tempo
   real (decidido; §5), e provedora congelada custa **2 PRs + uma sessão de
   arquitetura**, não um PR. Token de métrica nunca concede escrita.
7. **`/admin` é preso a `Host(meshcraft.top)`** — domínio novo com área admin é
   decisão nova, não uma linha a menos no router.
8. UI só PT-BR, sem rota com forma de idioma, sem página pública.
9. **A área admin não escreve fora do próprio banco** — nem no `catalogo`
   (§4.5 é somente-leitura), nem em nenhuma outra célula. Se isso mudar um
   dia, é decisão nova, registrada aqui, não um formulário acrescentado de
   passagem.
10. **Sem login próprio, sem domínio separado, sem botão de emergência
    à parte** — as três foram descartadas por decisão explícita do
    mantenedor (§3, §9), não por omissão. Quem travar a própria porta é
    consertado por PR normal, como qualquer outra coisa neste projeto.

## §9 — As seis perguntas, e as seis respostas (25/08/2026)

Todas colhidas por pergunta estruturada de múltipla escolha, em português
simples — formato que o mantenedor confirmou como o certo para toda decisão
dele daqui em diante (ver `CLAUDE.md`). Nenhuma é decisão de agente; todas
já aplicadas nas seções técnicas acima.

1. ~~Fazer agora, ou fazer "O Mirante" primeiro?~~ **Plano completo.**
   `DECISAO-filosofia-de-escopo.md`: este projeto é para ser feito completo,
   não minimalista, mesmo custando mais tempo — inclusive quebrando de novo,
   deliberadamente, o congelamento arquitetural que dizia "nenhuma célula
   nova até um piloto pago". Não dispensa a disciplina de entrega (PRs
   pequenos, uma célula por PR, Ritos de Contrato) — só decide que a
   construção não espera.
2. ~~A área admin vai ESCREVER no catálogo, ou só ler?~~ **Só ler.** §4.5 é
   somente-leitura; editar continua por PR. Reavaliar quando a escola nascer.
3. ~~A métrica pode ter alguns segundos de atraso (evento, barato) ou precisa
   ser exata (HTTP, mais caro)?~~ **Sempre exata.** HTTP direto em cada
   provedora, aceitando as 5 sessões de Rito de Contrato (§5, §6) — a opção
   barata foi vista e recusada, não esquecida.
4. ~~Mesma origem do site, ou separada?~~ **Mesma origem, com reforços**
   (CSP própria + verificação de frescor de sessão para escrita, §3) — sem
   login próprio, sem domínio separado. **[REVISÃO 25/08]** a CSP é do PR 3;
   o frescor exige um Rito §3 próprio e só faz falta na fase 4, quando nascer
   o primeiro formulário (§3).
5. ~~Marketing sai do congelamento de vendas?~~ **Sim, seção própria**
   (§4.6b), liberada desde já.
6. ~~O que ele faz às 2h se a porta travar contra ele?~~ **O conserto normal
   já basta** — PR pequeno pelo caminho de sempre, poucos minutos, sem
   precisar do servidor. Sem botão de emergência à parte: seria mais uma
   porta para proteger, sem ganho real de velocidade. Combina com a Lei 5 do
   projeto (emergência é sempre pipeline, nunca acesso direto ao servidor).

Sobre o endereço: se preferir `/operacao/` é troca de uma palavra — a proteção
real é a porta, não o nome. E o passo manual H21 passa a ser **uma linha**, não
um bloco de colar (§6).

## Estado

**Proposta em 25/08/2026, auditada no mesmo dia por uma banca de quatro
cadeiras (`PARECER-BANCA-AREA-ADMIN.md`), com as seis perguntas do §9 todas
respondidas pelo mantenedor, e revisada uma última vez depois das respostas
(marcações `[REVISÃO 25/08]`) — essa revisão achou quatro erros de fato, três
deles introduzidos ao aplicar as próprias respostas: a CSP que recriava o bug
do iframe, o custo do frescor de sessão dado como "de carona" quando é um
Rito §3 inteiro, o `quiz` ausente da conta da fase 2, e a promessa de contagem
de visitas sobre um dado que não existe.**

**Falta só ele dizer "aprovado" — a partir daí o PR 1 (gênese da célula) pode
começar.** Duas coisas ficam explicitamente **em aberto** e não travam o PR 1,
porque só aparecem lá na frente: se a contagem de visitas será construída
(§4.6b, fase 2) e se o frescor de sessão será construído antes do primeiro
formulário (§3, fase 4).
