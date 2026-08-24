# LICOES — services/sugestoes

> Decisões e armadilhas específicas desta célula. Regra geral em `ARMADILHAS.md`
> (leia `armadilhas/INDICE.md` e abra só a entrada que casa com a sua tarefa).

## O que existe aqui hoje (EVO-10 + EVO-11) — e o que NÃO existe

Do EVO-10, o esqueleto: `config/` (settings fail-hard, urls, asgi),
`GET /healthz`, `apps/core`. Do EVO-11, **só a camada de dados**:
`apps/sugestoes/models.py`, a migration `0001_initial`, o seed e os três
testes-guarda de invariante.

**Continua não existindo**, e cada um tem despacho próprio: API/endpoints
(EVO-12), moderação e staff (EVO-13), o FLUXO de entrar com Google (o model
`Identidade` existe; o login não), middleware CONV-SITE, `config/api.py` e
outbox/eventos (Lote 2, EVO-20 — a célula ainda não emite nada). Se você chegou
aqui esperando encontrar rota, sessão ou evento, o despacho é outro.

## O modelo de dados diverge da spec em três pontos, e os três são deliberados

A `ESPECIFICACAO-CELULA.md` §6 foi escrita antes da `AUDITORIA-AS-IS.md`. Onde
as duas discordam, **vence a realidade medida** — e é isto que a §6 diz de
errado:

| A spec §6 diz | O que está no código | Por quê |
|---|---|---|
| `tenant_id = models.UUIDField()` | `site_id = models.CharField()` | "Tenant" não existe no vocabulário da casa; site existe (Lei 9). E em toda a plataforma o ID que atravessa fronteira é `type: string` **sem** `format: uuid` (auditoria Q3) |
| `autor_id = models.UUIDField()` | `autor = FK(Identidade)` | Ver abaixo |
| `HistoricoStatus.sugestao` com `CASCADE` | `PROTECT` | A §8 da mesma spec diz "nenhuma linha é apagada". As duas não cabiam juntas (`armadilhas/078`) |

Há um teste-guarda mecânico para o primeiro item
(`tests/test_inv_sem_fk_para_fora.py::test_os_ids_inter_celula_sao_texto_opaco_e_nao_uuid`):
qualquer `UUIDField` que apareça em model desta célula reprova o CI. Não é
gosto — é a fronteira que os consumidores já falam.

## `Identidade` é FK de verdade, e isso NÃO fura a Lei 3

A leitura apressada da Lei 3 ("nenhuma FK saindo da célula") vira, na cabeça de
quem está com pressa, "nenhuma FK". São coisas diferentes: o que o Postgres não
sustenta é constraint **entre bancos**, e `Identidade` mora no mesmo
`sugestoes_db` de `Sugestao`, `Voto` e `Comentario`. Dentro do banco, a
integridade referencial é de graça — recusá-la seria pagar o preço da restrição
sem receber nada em troca.

E não custa o nome: FK chamada `autor` faz o Django criar a coluna `autor_id`,
que é exatamente o campo que a spec pede — e continua sendo **texto opaco**,
porque `Identidade.id` é `CharField`. Ganha-se o `ON DELETE` explícito de
brinde: `PROTECT` em toda referência a `Identidade`, para que apagar uma pessoa
nunca vire histórico órfão em silêncio.

**O que continua proibido, e o guarda que impõe:** FK para model de outra
célula. `tests/test_inv_sem_fk_para_fora.py` varre `apps.get_models()` e deriva
sozinho quais apps são desta célula (os que moram em `apps/`), então app novo
entra no guarda sem ninguém lembrar de cadastrá-lo.

## O append-only tem TRÊS degraus, e o terceiro é o banco

`HistoricoStatus` (spec §8) é imposto em `save()`, no `AppendOnlyQuerySet`
(`update`/`delete`/`bulk_update` — `armadilhas/023`) **e** num trigger plpgsql
criado pela `0001_initial`. O terceiro não é zelo excessivo: sem ele, o
`Collector` do Django apagaria o histórico inteiro por um `CASCADE`, sem passar
por nenhum dos dois primeiros e sem erro nenhum (`armadilhas/078`).

Consequência prática para quem for escrever a API (EVO-12/EVO-13): **não existe
"corrigir o histórico"**. Correção é `HistoricoStatus.objects.create(...)` com o
estado novo; qualquer tentativa de editar levanta `RegistroImutavel` antes de
chegar ao banco, e o banco recusa de novo se alguém desviar do ORM.

## O e-mail vive numa linha só, e há guarda para isso

`Identidade.email` é o único campo de e-mail da célula (EVO-01 §3), e
`test_o_email_vive_numa_linha_so` reprova qualquer `EmailField` — ou campo com
"email" no nome — que apareça em outro model. Dado pessoal espalhado por cada
voto de cada pessoa não é problema de estilo: é o que faz uma troca de endereço
virar migração de dados em vez de um `UPDATE` de uma linha.

## O prefixo mora no env, e o `/healthz` foi travado ANTES de o middleware chegar

A Caixa serve em `meshcraft.top/forms/sugestoes/`
(`DECISAO-EVO-01-identidade.md` §2) — ou seja, **sob `SCRIPT_NAME`**, o mesmo
regime que matou a sonda do `checkout` (PR #65) e do `quiz` (PR #71). A
armadilha (`armadilhas/029`) tem duas metades, e as duas estão travadas por
`tests/test_healthz_script_name.py`:

1. `config/urls.py` **não conhece o prefixo**. Quem o aplica é
   `FORCE_SCRIPT_NAME`, lido do env. Rota escrita como
   `path("forms/sugestoes/healthz", …)` faz da mudança de URL uma cirurgia em
   código; o teste `test_urlconf_nao_conhece_o_prefixo` reprova isso.
2. Quando o middleware CONV-SITE entrar (EVO-11/EVO-12), a isenção de
   `/healthz` compara **`request.path_info`**, nunca `request.path`. Pela borda
   pública o Traefik NÃO remove o prefixo: a request line que chega ao uvicorn
   é `GET /forms/sugestoes/healthz`, e aí `request.path` contém o prefixo em
   qualquer versão do Django.

**O guarda usa `AsyncClient`, e isso não é preciosismo.** Em produção a célula
roda sob uvicorn, logo o objeto de requisição é `ASGIRequest` — que faz
`path = scope["path"]` e `path_info = path.removeprefix(script_name)`. O
`client` síncrono do Django constrói um `WSGIRequest`, cuja aritmética é a
inversa (`path_info` vem do environ como está, `path = script_name + path_info`).
Testar a borda pública pelo client síncrono mediria outra coisa. Detalhe que
custa tempo se descoberto na hora errada: no `AsyncClient` a requisição sai por
`resp.asgi_request`, **não** `resp.wsgi_request` (que só existe no síncrono, e
é o que os testes das outras células usam).

## O compose de dev foge do molde em duas linhas, de propósito

`docker-compose.dev.yml` das outras 8 células usa `name: dev-celula` e mapeia o
Postgres em `5432`. Aqui é `name: dev-sugestoes`, `container_name:
sugestoes-pg-dev` e `55440:5432`.

O nome do projeto do compose é o **namespace dos containers**: com
`dev-celula` em todas, duas sessões de agente rodando em paralelo (o modo de
trabalho normal desta casa — `RUNBOOK-LOTES.md`) disputam o mesmo
`dev-celula-db-1`, e a segunda derruba o banco da primeira sem avisar. A porta
55440 é a pré-atribuída a esta célula, para não colidir com o `55432` da
partida rápida do `ARMADILHAS.md` §2.

**Isso é dívida das outras 8, não invenção desta.** Se alguém uniformizar, o
caminho é uniformizar para o nome por célula, não de volta para `dev-celula`.

## Fail-hard: só as duas variáveis que o CI já fornece

`config/settings.py` levanta `ImproperlyConfigured` no import para
`DJANGO_SECRET_KEY` e `DATABASE_URL` — e mais nada. O motivo é mecânico
(`armadilhas/037`): variável nova e fail-hard no `settings.py` precisa ser
espelhada no bloco `env:` de `.github/workflows/ci-celula.yml`, que é o único
lugar que alimenta o `make ci` do CI real — e `.github/` está fora do escopo
desta célula. As variáveis que ainda vão nascer aqui
(`SUGESTOES_STAFF_EMAILS`, `ALUNOS_API_URL`, `TOKEN_ALUNOS`, credenciais do
Google) são lidas **no ponto de uso**, com default inofensivo, como manda a
convenção do lote de Huey. `SCRIPT_NAME` já segue essa forma
(`os.environ.get(...) or None`).

## `contrato-check` veio do template, não do vizinho

O `Makefile` desta célula usa `bash ../../ci/freeze-de-contrato.sh $(CELULA)`
— a forma do `celula-template/`. O `Makefile` de `quiz` e `funil` ainda usa a
forma antiga (`if [ -f ../../contracts/… ]` + escrita em `/tmp`), que tem dois
problemas: infere "não tem contrato" de "não achei o arquivo" (exatamente a
ambiguidade que o `ci/manifesto-de-contratos.json` foi criado para matar,
INV-CI01) e escreve em `/tmp`, que não existe na máquina Windows do
mantenedor. Quem decide é o manifesto, e nele esta célula é
`freeze: not-applicable`.

## Por que `not-applicable` aqui não envelhece como o de `funil`/`quiz`

O `reason` de `funil`, `mensageria` e `quiz` diz "célula ainda em esqueleto: só
`/healthz`" — um motivo que caduca no dia em que a célula ganhar API. O desta
não caduca, porque não é sobre maturidade: `contracts/` é a fronteira **ENTRE**
células (`contracts/README.md`), e a superfície HTTP da Caixa é consumida pelo
front-end **dela mesma**. Mesmo depois de EVO-12, com sugerir/votar/comentar no
ar, continua não havendo contrato a congelar. Só muda se outra célula precisar
consumir a Caixa — e aí é RITOS.md §3, não edição de manifesto.
