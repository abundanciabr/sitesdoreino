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
> aprovaram com ressalvas; a de produto recomenda uma versão reduzida ("O
> Mirante", parecer §4). As correções de **fato** já entraram neste documento,
> marcadas com **[BANCA]**; o que depende de decisão do mantenedor está no §7 do
> parecer e **não** foi alterado aqui.

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
| 4.5 | **Cursos & conteúdo** | formulários sobre a API do `catalogo` (ofertas, cursos); é o embrião da gestão da Meshcraft Academy — cresce quando a escola nascer | 4 |
| 4.6 | **Vendas** | **CONGELADA** — nem métricas de checkout/pagamentos. Só nasce quando o mantenedor disser que o site vai vender | — |
| 4.6b | **Público & demanda** (marketing) | **[BANCA] separada da anterior: congelar marketing junto com vendas foi erro de categoria.** Visitas, cadastros no `/cadastro`, leads, quizzes completados — por idioma e por site. Existe hoje, é dado real e **não encosta no Mercado Pago**. E é a inversão que importa: métricas de venda seriam zeros; o que produz a ordem "o site vai vender" é ver pessoas deixarem e-mail sem que exista produto | **2** (candidata a primeira seção de métricas) |
| 4.7 | **Configuração** | o que é **dado** (chave-valor por site no `admin_db`; dados do `catalogo`), com formulário. O que é **código/infra** (`sites.json`, Traefik, envs) continua entrando por PR — a seção mostra somente-leitura e aponta o caminho | 4 |
| 4.8 | **Roadmap & planos** | página interna editável (markdown no banco). Não confundir com o roadmap PÚBLICO da Caixa (EVO-31): este é o de dentro | 4 |

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
    teste-guarda no mesmo PR.
- **[BANCA] A alternativa mais barata para metade disto é evento, não HTTP.**
  A Caixa já emite `sugestao.criada.v1`, `voto-adicionado`, `voto-removido` e
  `status-alterado`, todos com `site_id`. Um `admin-consumer` construindo read
  model no `admin_db` é a Virtude da Lei 3 e faz a primeira provedora da fila
  custar **zero** rito. Desenho certo: **híbrido** — evento onde já há evento,
  HTTP onde não há. Qual dos dois depende de uma decisão do mantenedor (parecer
  §7.3: a métrica pode ser de "há alguns segundos"?).
- **Cliente HTTP único e reutilizado** (armadilha 082) e **lido em request,
  nunca no `__init__`** (armadilha 097: env no init vira 500 em toda página).

## §6 — A escada de entrega

Copiada do precedente que funcionou (`DECISAO-celula-de-identidade.md` §5),
com os degraus que as armadilhas 076/088/089 provaram serem obrigatórios.

**[BANCA] O custo honesto, corrigido.** A versão original desta seção dizia
"7–9 merges" e "cada PR respeita o orçamento de 15 arquivos". As duas frases
estavam erradas:

- **7–9 merges abre a PORTA (fase 1). O §4 inteiro é da ordem de 30 merges** —
  a fase 2 sozinha são 11 PRs. E os "Lotes 6 e 7" citados não eram dois
  exemplos: eram as duas metades do **mesmo** nascimento (9 + 7 = 16 merges para
  pôr a `sugestoes` do zero ao ar).
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
| PR 3 | agente | **A porta** (§3): middleware fail-closed + página Visão geral + auditoria append-only (com trigger no banco, não só guarda em Python — `armadilhas/079`) + CSP + lista de caminhos isentos **enumerada e guardada por igualdade exata** **[BANCA]** | testes-guarda das três linhas da tabela do §3 no mesmo PR |
| PRs 4+ | agente | **Fase 2 — [BANCA] 11 PRs, não 5**: por provedora congelada são **2 PRs** (o Rito §3 proíbe `contracts/` junto com `services/`) **e uma sessão de arquitetura com o mantenedor presente**. Ordem sugerida: `sugestoes` → `identidade` → `leads` → `alunos` → `catalogo`, mais a página Métricas | **Aprovar a fase 2 é aprovar cinco sessões com o mantenedor.** O caminho por evento (§5) reduz isso — decisão dele |
| depois | agente | **Fase 3** (galeria, 2–3 PRs) → **Fase 4** (usuários, cursos, config, roadmap — 8–12 PRs, 1 despacho por seção, serializados entre si pela muralha "1 PR = 1 célula") | Fase 4.4 exige Rito §3 na `identidade` |

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
6. **Métricas jamais leem banco alheio** — entram por contrato HTTP **ou por
   evento** (§5), e **[BANCA]** provedora congelada custa **2 PRs + uma sessão
   de arquitetura**, não um PR. Token de métrica nunca concede escrita.
7. **`/admin` é preso a `Host(meshcraft.top)`** — domínio novo com área admin é
   decisão nova, não uma linha a menos no router.
8. UI só PT-BR, sem rota com forma de idioma, sem página pública.

## §9 — O que o mantenedor decide agora

**[BANCA] Esta seção foi reescrita.** A versão original pedia aprovação de uma
ordem que o próprio plano já tinha escolhido, e gastava um dos três itens numa
questão de nome. As perguntas que importam são as do `PARECER-BANCA-AREA-ADMIN.md`
§7; as seis, em resumo:

1. **Fazer agora, ou fazer "O Mirante" primeiro?** Três cadeiras aprovam o plano
   completo; a de produto recomenda a versão reduzida (1–2 PRs, sem célula nova)
   até existir um curso publicado — e lembra que há um congelamento arquitetural
   escrito (*"nenhuma célula nova até um piloto pago rodar"*) que isto quebraria
   pela terceira vez. **Esta é a decisão-mãe; todas as outras dependem dela.**
2. **A área admin vai ESCREVER no catálogo, ou só ler?** Decide o tamanho do
   §4.5 e se a área ganha autoridade sobre preço de oferta.
3. **A métrica pode ser de "há alguns segundos" (evento, barato) ou precisa ser
   "agora" (HTTP, 5 ritos de contrato)?**
4. **A área que escreve configuração de produção mora na mesma origem e sessão
   dos visitantes comuns?** (a) mesma origem com CSP + re-autenticação + sessão
   curta, (b) origem separada, ou (c) mesma origem e **somente leitura**.
5. **Marketing vira seção própria** (§4.6b), fora do congelamento de vendas?
6. **O que ele faz às 2h se a porta fechar contra ele?** Se não houver caminho,
   isso precisa estar escrito antes do PR 1.

Sobre o endereço: se preferir `/operacao/` é troca de uma palavra — a proteção
real é a porta, não o nome. E o passo manual H21 passa a ser **uma linha**, não
um bloco de colar (§6).

## Estado

**Proposta em 25/08/2026 — auditada no mesmo dia por uma banca de quatro
cadeiras (`PARECER-BANCA-AREA-ADMIN.md`), com as correções de fato já aplicadas.
Aguardando a palavra do mantenedor sobre as seis perguntas do §9.**
