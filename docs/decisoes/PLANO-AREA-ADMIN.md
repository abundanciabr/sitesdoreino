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
| 4.6 | **Vendas & marketing** | **CONGELADA** — nem métricas de checkout/pagamentos. Só nasce quando o mantenedor disser que o site vai vender | — |
| 4.7 | **Configuração** | o que é **dado** (chave-valor por site no `admin_db`; dados do `catalogo`), com formulário. O que é **código/infra** (`sites.json`, Traefik, envs) continua entrando por PR — a seção mostra somente-leitura e aponta o caminho | 4 |
| 4.8 | **Roadmap & planos** | página interna editável (markdown no banco). Não confundir com o roadmap PÚBLICO da Caixa (EVO-31): este é o de dentro | 4 |

## §5 — Onde os dados moram (as muralhas aplicadas)

- **`admin_db`** (banco + role próprios, `infra/provisionamento-postgres.sql`):
  auditoria, painéis enviados, config chave-valor, textos do roadmap. Nada de
  dado de outra célula copiado sem necessidade.
- **Métricas são federadas por contrato, nunca por banco.** Cada célula
  provedora ganha `GET /interno/metricas` — leitura, sem rota no Traefik
  (rede interna, token `TOKENS_ACEITOS_ADMIN` na célula provedora), devolvendo
  meia dúzia de contadores com `site_id`. Nas células de contrato congelado é
  Rito §3, **um PR por célula** (muralha). No painel, **fail-open por tile**:
  célula fora do ar = tile "sem dados", a página abre — é leitura de vitrine
  interna, não autorização.
- **Cliente HTTP único e reutilizado** (armadilha 082) e **lido em request,
  nunca no `__init__`** (armadilha 097: env no init vira 500 em toda página).

## §6 — A escada de entrega

Copiada do precedente que funcionou (`DECISAO-celula-de-identidade.md` §5),
com os degraus que as armadilhas 076/088/089 provaram serem obrigatórios.
Custo honesto, medido no próprio histórico: nascimento de célula = 7–9 merges
(Lotes 6 e 7). Cada PR respeita o orçamento de 15 arquivos — a divisão abaixo
já é a conta feita no papel.

| Passo | Quem | O quê | Notas de mandato |
|---|---|---|---|
| PR 1 | agente | **Gênese**: `services/admin` esqueleto (healthz, settings fail-hard, Dockerfile, Makefile, fumaça) + declaração `not-applicable` no `ci/manifesto-de-contratos.json` (motivo: não fornece API; contrato entra pelo Rito §3 se um dia fornecer) + **linha no `rollback.yml`** + promoção deste plano a `DECISAO-celula-admin.md` | `.github/` e `ci/` são CODEOWNERS — o despacho de gênese nasce com esse mandato e anuncia nominalmente (armadilha 076: célula nasce COM rollback) |
| **H21** | **mantenedor** | UM bloco único, fail-closed, janela rotulada: banco+role `admin` na VPS · `env/admin.env` (SCRIPT_NAME, DATABASE_URL, SECRET_KEY, endereço da `identidade`, token do par, `ADMIN_EMAILS` com o e-mail dele) · acrescentar `TOKENS_ACEITOS_ADMIN`/`TOKENS_COMPLETOS_ADMIN` ao `env/identidade.env` | roteiro `infra/provisionar-admin.sh` entregue no PR 2; registrado em `ARMADILHAS-OPERACAO.md` §1. **Antes do merge do PR 2**, senão crashloop (armadilha 088, lição H18) |
| PR 2 | agente | **Infra**: serviço no `infra/docker-compose.yml` + router/service no Traefik (Host-bound, §2) + `env/admin.env.exemplo` + `provisionar-admin.sh` + inventário `ci/tests/test_rotas_sem_forma_de_locale.py` | mandato `infra/` + `ci/`; merge SÓ com H21 executado |
| PR 3 | agente | **A porta** (§3): middleware fail-closed + página Visão geral + auditoria append-only com guardas + registro do par na lei da identidade | testes-guarda das três linhas da tabela do §3 no mesmo PR |
| PRs 4+ | agente | **Fase 2**: `GET /interno/metricas` numa célula provedora por PR (Rito §3 onde congelado) e a página Métricas no admin | ordem sugerida: `sugestoes` → `identidade` → `leads` → `alunos` → `catalogo` |
| depois | agente | **Fase 3** (galeria, ~1–2 PRs) → **Fase 4** (usuários, cursos, config, roadmap — 1 despacho por seção) | Fase 4.4 exige Rito §3 na `identidade` |

**Aviso de fenômeno esperado:** entre o merge do PR 1 e o fim do PR 2 + H21, o
`deploy-celula` fica **vermelho em todo merge da célula** com "não tem serviço
algum em /opt/plataforma/docker-compose.yml" — é ERROR de ambiente, não FAIL de
código (armadilha 088). O relatório de cada despacho da janela avisa isso ao
mantenedor de antemão, para o vermelho não assustar.

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
6. **Métricas entram por contrato HTTP interno**, jamais lendo banco alheio —
   e cada célula provedora é um PR próprio.
7. **`/admin` é preso a `Host(meshcraft.top)`** — domínio novo com área admin é
   decisão nova, não uma linha a menos no router.
8. UI só PT-BR, sem rota com forma de idioma, sem página pública.

## §9 — O que o mantenedor decide agora

1. **Aprovar (ou ajustar) este plano** — nome `admin`, endereço
   `meshcraft.top/admin/`, o mapa do §4 e a ordem das fases (recomendo: 1 → 2
   → 3 → 4, porque métricas vivas são o valor que nenhum painel local entrega
   hoje).
2. Se preferir **endereço camuflado** (ex.: `/operacao/`), é troca de uma
   palavra no plano — a proteção real é a porta 404 do §3, não o nome; por
   isso a recomendação é ficar com `/admin` mesmo.
3. Ciência de que haverá **um passo manual (H21)**, um bloco único de colar,
   entre os PRs 1 e 2 — o resto inteiro é dos agentes.

## Estado

**Proposta em 25/08/2026 — aguardando a palavra do mantenedor.**
