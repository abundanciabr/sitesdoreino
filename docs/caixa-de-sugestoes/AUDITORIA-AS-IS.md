# AUDITORIA AS-IS — EVO-00 (Lote 0 da Caixa de Sugestões)

> Executada em 23/08/2026, somente leitura, pela sessão-maestro (o apagão do CI
> — H14 — não impede auditoria; impede merge). É o documento que a spec exige
> antes de qualquer implementação (`ESPECIFICACAO-CELULA.md` §3 e DoD §11).
> Método: evidência medida no repositório, com caminho de arquivo citado.

## Q1 — As células operam com banco próprio isolado? ✅ SIM

- `infra/provisionamento-postgres.sql`: **um database + um role por célula**,
  com `REVOKE ALL ... FROM PUBLIC` — 7 bancos (funil é stateless por desenho:
  "formulários postam em leads", comentário no próprio SQL).
- `infra/env/*.exemplo`: cada `DATABASE_URL` usa exclusivamente o par
  `<celula>_user`/`<celula>_db`.
- A isolação é **negada pelo Postgres, não por convenção** — provada pelo
  red-team (golpe nº 7: `permission denied for database`) e pelo teste do
  Prompt Zero ("banco cruzado" no painel).

**Consequência:** o pressuposto da spec §3 vale. A restrição "nenhuma FK para
fora da célula" é estrutural mesmo. `sugestoes_db` + `sugestoes_user` entram no
provisionamento no Lote 2 (passo do mantenedor, via console — Lei 5).

## Q2 — Como um aluno se autentica hoje? ❌ NÃO SE AUTENTICA — o maior achado

- **Não existe login de usuário final em nenhuma célula**: zero ocorrências de
  `LoginView`/`login_required`/`AuthenticationForm` em `services/*/`.
- A única autenticação da plataforma é **interna, célula→célula**: Bearer
  estático por par (`contracts/README.md` item 6; implementação em
  `services/alunos/apps/core/auth.py` — token contra `TOKENS_ACEITOS`).
- O "aluno" hoje é **um e-mail dentro da matrícula**: `contracts/alunos.openapi.yaml`
  identifica por `customer.email` (createEnrollment) e consulta por
  `/alunos/{email}/matriculas` (listEnrollments).

**Consequência:** o `AuthenticatedActor {actor_id UUID, tenant_id, roles,
entitlements}` da spec §4 **não tem provedor** — não é campo a confirmar, é
mecanismo a criar. A decisão é do EVO-01 (mantenedor presente). Caminho de
menor invenção compatível com o AS-IS: identidade por e-mail + link mágico
validado contra a matrícula na célula `alunos` (contrato já existente), com
`actor_id` = e-mail normalizado ou um UUID cunhado pela própria célula
sugestoes na primeira aparição. "Staff" também não existe como role em lugar
nenhum — precisa nascer junto (ex.: lista de e-mails staff no env da célula,
fail-hard).

## Q3 — `tenant_id` da spec ≙ o quê na realidade? Site, com ID **string**

- A plataforma resolve o site pelo **Host**: middleware CONV-SITE →
  `getSiteByHost` do catálogo (`contracts/catalogo.openapi.yaml`).
- Os IDs do catálogo (`Site.id`, `Product.id`, `site_id`, `product_id`) são
  `type: string` **sem** `format: uuid` — em toda a plataforma os IDs
  inter-célula são strings opacas (o contrato de alunos idem).

**Consequência:** os campos `tenant_id = models.UUIDField()` e
`produto_id = models.UUIDField(null=True)` da spec §5/§6 divergem da casa.
Na implementação: `site_id`/`produto_id` como `CharField` opacos (mesma
semântica dos consumidores existentes). Sem custo: nada foi persistido.

## Q4 — O que uma célula nova precisa tocar para existir de ponta a ponta

Medido em `.github/workflows/*` + `ci/`:

| Peça | Como funciona | Precisa editar? |
|---|---|---|
| CI de PR (`ci-celula.yml`) | **Detecção automática** (`python ci/ci.py --detectar-celulas`) — sem matriz fixa | ❌ nada no `.github/` |
| Deploy (`deploy-celula.yml`) | Mesma detecção; builda `ghcr.io/.../plataforma-<celula>` e exige o serviço no compose **da VPS** | ❌ nada no `.github/` |
| **Rollback (`rollback.yml`)** ⚠️ | **NÃO detecta nada.** A célula é um `type: choice` do `workflow_dispatch`, e choice do Actions não aceita lista dinâmica — as células estão escritas à mão em `options:`. `ci/tests/test_rollback.py::test_opcoes_de_celula_do_workflow_batem_com_o_manifesto` exige **paridade EXATA** com o manifesto, e reprova nos DOIS sentidos | ✅ **SIM, no MESMO PR do scaffold** — `.github/` é CODEOWNERS: o despacho de gênese precisa nascer com esse mandato |
| **Manifesto** `ci/manifesto-de-contratos.json` | "célula em services/ fora deste manifesto → ERROR"; o próprio arquivo manda: **"Ao criar uma célula nova, declare-a aqui no MESMO PR"** | ✅ no PR do scaffold — e `ci/` é CODEOWNERS (mandato + anúncio nominal) |
| Compose + Traefik (`infra/**`) | Bloco `x-celula` reutilizável; entrega mecanizada pelo `deploy-infra` (H11 ✅) | ✅ Lote 2 (CODEOWNERS) |
| Env (`infra/env/sugestoes.exemplo` + `.env` real na VPS) | Real é segredo escrito à mão (INV-P8) | ✅ exemplo no repo; real = 🙋 mantenedor |
| Banco na VPS (`provisionamento-postgres.sql`) | `CREATE ROLE/DATABASE` como superuser | 🙋 mantenedor, console |
| Constituição `constituicoes/AGENTS.sugestoes.md` | As 8 células têm a sua | ✅ Lote 1 |

> ⚠️ **CORREÇÃO DE 24/08/2026 — esta Q4 estava incompleta e custou uma rodada.**
> A linha do `rollback.yml` acima **não existia**: a auditoria mediu o `ci-celula.yml`
> e o `deploy-celula.yml`, viu que os dois detectam a célula sozinhos, e generalizou
> para "❌ nada no `.github/`". O `rollback.yml` não foi medido.
>
> O resultado, no PR de gênese da `sugestoes` (#108): o `muralhas` reprovou com
> `AssertionError: Right contains one more item: 'sugestoes'`, o agente de célula
> **não podia** corrigir (`.github/` fora do escopo, CODEOWNERS sem mandato, e o
> harness bloqueia a edição), e o merge parou até a sessão-maestro entrar com o
> mandato dela. Uma linha. O guarda estava certo: sem ela a célula nasceria **sem
> rollback** — a válvula do `RITOS.md` §4.
>
> **Regra que fica:** todo despacho de gênese de célula nasce com mandato explícito
> para `.github/workflows/rollback.yml`, do mesmo jeito que já nascia para `ci/`.
> Registro completo: `ARMADILHAS-OPERACAO.md` §1 H17 e `armadilhas/076`.

**Descoberta de sequenciamento nº 1 — o contrato NÃO pode nascer antes da célula.**
O manifesto reprova nos dois sentidos: contrato em `contracts/` sem célula
declarada → ERROR; célula declarada sem existir no disco → ERROR (declaração
órfã). Logo, o desenho original do plano ("EVO-01 congela o contrato antes do
Lote 1") é **mecanicamente impossível**. O caminho provado pela própria casa é
o de funil/mensageria/quiz: **a célula nasce `freeze: not-applicable`**
("esqueleto, só /healthz") e o contrato entra pelo Rito §3 **quando a API vai
nascer** (entre EVO-11 e EVO-12), flipando para `required` no mesmo movimento.
O EVO-01 continua existindo — mas como sessão de DECISÃO (identidade, IDs,
nomes de evento, URL); o congelamento do contrato desloca-se para a fronteira
EVO-11→EVO-12.

**Descoberta de sequenciamento nº 2 — vermelho esperado no deploy durante o Lote 1.**
Todo merge em `services/sugestoes/` dispara o `deploy-celula`, que **exige** o
serviço no compose da VPS ("ERRO: '<celula>' não tem serviço algum...") — e o
compose só ganha `sugestoes` no Lote 2 (depois do banco existir, senão o
container cai em crashloop com `DATABASE_URL` fail-hard e o `deploy-infra`
reprova a verificação de serviços rodando). Portanto: **durante o Lote 1, o
job de deploy da célula sugestoes fica vermelho por causa conhecida e
registrada** — a maestro trata esse vermelho específico como esperado (não
pausa a janela por ele), e o Lote 2 o cura. As imagens `plataforma-sugestoes`
já vão sendo publicadas no ghcr nesses merges — o Lote 2 só as puxa.

## Q5 — Convenções reais dos eventos (medidas no código vivo)

- **Envelope canônico** (`contracts/README.md` item 5, confirmado nos consumers):
  `{event, version, event_id (uuid), occurred_at, data}` — dedup por `event_id` é lei.
- **Stream**: `eventos.<nome-do-evento>` — o relay de pagamentos publica
  `f"eventos.{evento.event}"`. **A versão vai no envelope, não no nome do
  stream** (streams reais: `eventos.pagamento.aprovado`, `eventos.quiz.completado`,
  `eventos.pedido.criado`, `eventos.pix.expirado`).
- **Nomes em PT, `substantivo.verbo-no-particípio`** — a spec nascera com nomes
  em inglês (`suggestion.created`…), divergindo da casa. **Resolvido em
  23/08/2026**, junto da decisão de nome: os eventos passaram a ser
  `sugestao.criada`, `sugestao.voto-adicionado`, `sugestao.voto-removido`,
  `sugestao.status-alterado` e `sugestao.mesclada` (v1 no envelope), e a
  ESPECIFICACAO-CELULA.md §7 já está reescrita assim.
- **Consumer group = nome da célula**; e os consumers atuais (alunos, checkout,
  leads) já têm **reentrega via XAUTOCLAIM** — a peça que faltava do §9 do
  ARMADILHAS existe no código novo. O consumer do EVO-21 (mensageria) copia
  esse padrão, com as duas metades do §4.8/§4.12 corretas.

## Tabela de divergências spec ↔ realidade (insumo do EVO-01)

| # | Spec diz | Realidade medida | Decisão proposta |
|---|---|---|---|
| 1 | `AuthenticatedActor` emitido por célula de auth | Não existe auth de usuário final; aluno = e-mail na matrícula | Link mágico validado em `alunos` (contrato existente); staff por lista no env |
| 2 | `actor_id`/`tenant_id`/`produto_id` UUID | IDs inter-célula são strings opacas | Strings opacas, como toda a plataforma |
| 3 | Contrato congelado antes da célula | Manifesto proíbe contrato sem célula | Nascer `not-applicable`; Rito §3 na fronteira EVO-11→EVO-12 |
| 4 | Eventos em inglês (`suggestion.created`…) | Streams `eventos.<nome-pt>`, versão no envelope | Nomes PT (lista acima) |
| 5 | — (spec não trata deploy) | deploy-celula exige serviço no compose da VPS | Vermelho esperado no Lote 1; cura no Lote 2 |

## Veredito

Nenhum impedimento estrutural: a arquitetura da casa comporta a célula
`sugestoes` exatamente como especificada — com as 5 adaptações da tabela, todas
baratas porque **nada foi persistido ainda** (a própria spec previu isso).
O item do DoD "auditoria AS-IS documentada e anexada antes da implementação"
(spec §11) está cumprido por este documento.
