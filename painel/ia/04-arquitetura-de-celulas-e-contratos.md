# painel/ia — 04. Arquitetura de Células e Contratos

> Parte do [Mapa para IA](INDICE.md) do sitesdoreino. Resumo curado — a fonte
> de verdade é `celula-template/`, `constituicoes/`, `contracts/` e cada
> `services/<celula>/`. **Os números abaixo (quantas células têm contrato,
> quantos eventos existem) mudam conforme o projeto cresce — antes de
> confiar numa contagem para uma decisão importante, confira ao vivo com
> `git ls-files` em vez de aceitar este snapshot (27/08/2026).**

## O padrão (`celula-template/`)

Toda célula é um projeto **Django 5 + django-ninja** completo e autônomo,
gerado a partir de `celula-template/`. Árvore canônica: `manage.py`,
`requirements.txt`, `Makefile`, `Dockerfile`, `docker-compose.dev.yml` (sobe
só aquela célula + Postgres + Redis + mocks Prism das dependências — nunca a
plataforma inteira), `.env.dev` (gitignored), `config/{settings,urls,asgi}.py`
(o projeto Django sempre se chama `config`), `apps/` (domínio), `templates/`
e `static/` próprios (não existe `base.html` compartilhado entre células —
Lei 7 da Constituição), `tests/`, `pytest.ini`.

Convenções mecânicas que atravessam as 12 células:
- **Fail-hard de settings** — `SECRET_KEY`/`DATABASE_URL` ausentes ⇒
  `ImproperlyConfigured`, nunca fallback silencioso.
- **`SCRIPT_NAME`/`FORCE_SCRIPT_NAME`** lido do env — o urlconf nunca conhece
  o prefixo público; mover a célula de endereço é editar Traefik + env,
  nunca o código.
- **Dinheiro é sempre `amount_cents` inteiro** — float é proibido em toda a
  plataforma, models, APIs e eventos.
- **Migrations Expand-and-Contract** — nunca remover coluna/tabela em uso
  (Receita R7 do Caminho Dourado).
- **Outbox transacional** nas células emissoras (evento gravado na mesma
  transação do estado; relay Huey publica em Redis Streams) e **consumer
  idempotente** (grupo = nome da célula, dedup por `event_id`) nas ouvintes.
- **`make ci` = lint + type + test + contrato-check**, e `contrato-check`
  delega a decisão "esta célula tem contrato?" a `ci/manifesto-de-contratos.json`
  — nunca à presença do arquivo em disco.
- Módulo extra opcional (`celula-template/pagamentos-extra/`) para células
  que precisam do isolamento reforçado que hoje só `pagamentos` usa.

## As 12 células

| Célula | Domínio (por `apps/`) | LICOES.md | Constituição | Contrato OpenAPI |
|---|---|---|---|---|
| `admin` | `core` apenas — sem app de domínio próprio | ✓ | ✓ | — (só consome) |
| `alunos` | `bridge`, `core`, `eventos`, `matriculas` | ✓ | ✓ | ✓ |
| `catalogo` | `core`, `ofertas`, `produtos`, `sites` | ✓ | ✓ | ✓ |
| `checkout` | `core`, `pedidos` | ✓ | ✓ | ✓ |
| `funil` | `core`, `i18n` | ✓ | ✓ | — (páginas HTML, sem API JSON) |
| `identidade` | `core`, `identidade` | ✓ | ✓ | ✓ |
| `leads` | `core` apenas | ✓ | ✓ | ✓ |
| `mensageria` | `core`, `eventos` | ✓ | ✓ | — (esqueleto: só `/healthz`) |
| `notificacoes` | `core`, `eventos`, `notificacoes` | ✓ | ✓ | — (nasce sem contrato, por lei de gênese) |
| `pagamentos` | sem `apps/`: `core`, `methods/{pix,card}`, `providers/mercadopago`, `api` | ✓ | ✓ | ✓ |
| `quiz` | `core`, `quiz` | ✓ | ✓ | — (só páginas HTML) |
| `sugestoes` | `core`, `sugestoes` | ✓ | ✓ | ✓ (1 operação) |

**Todas as 12 células têm `LICOES.md` e constituição própria** — não é um
subconjunto (um levantamento anterior a este mapa presumia só 8; foi
corrigido nesta pesquisa). 7 células têm contrato OpenAPI `required`
(alunos, catalogo, checkout, leads, pagamentos, identidade, sugestoes); as
outras 5 são `not-applicable` por motivo escrito em
`ci/manifesto-de-contratos.json`.

**Nota de método para medir tamanho de célula:** use `git ls-files
services/<celula> | wc -l`, nunca `find`. O caso `services/pagamentos`
chegou a mostrar 2073 arquivos num `find` cru — investigado a fundo, **96%
era `.mypy_cache/`** de uma sessão anterior (gitignored, não existe em clone
limpo). Contado certo (`git ls-files`), `pagamentos` tem 48 arquivos — menor
que `funil` (50) e pouco maior que `checkout` (44), apesar de ser o domínio
mais crítico. Por código real versionado, quem lidera é `sugestoes` (97
arquivos), de longe a célula mais recente e mais extensa.

## O mecanismo de contratos: OpenAPI + eventos, e o freeze que os protege

`contracts/README.md` chama a pasta de "**Muralha nº 4**" — a implementação
da Lei 2.4 (Contrato) da `CONSTITUICAO.md`. Regras centrais: nenhuma sessão
normal edita `contracts/` (mudança = Rito de Contrato, `RITOS.md` §3: PR só
com `contracts/`, label `contrato`, aprovação do mantenedor, provedor
implementa primeiro com retrocompatibilidade, consumidores em PRs
seguintes); consumidor desenvolve contra mock Prism, nunca contra o código
do provedor; eventos são versionados no nome do arquivo (`*.v1.json` →
`*.v2.json` numa mudança breaking, com o `v1` continuando a ser emitido até
o último consumidor migrar — hoje `sugestao.status-alterado.v1.json` e
`.v2.json` **coexistem de verdade**, o v2 acrescentando `ator_id` ao
envelope); envelope canônico `{event, version, event_id, occurred_at, data}`,
consumo idempotente por `event_id`; autenticação por Bearer estático **por
par nomeado** (checkout→pagamentos ≠ funil→leads, tokens nunca
compartilhados entre pares).

O congelamento é vigiado por `ci/contract_freeze.py` — reescrito em Python
depois de um **incidente real**: a versão antiga em Bash chamava `python3`
(ausente numa máquina), os dois lados do diff viravam string vazia,
`diff(vazio, vazio)` dava "igual" e o script imprimia "OK" sem ter comparado
nada. A versão atual tem duas defesas específicas:
1. Normalização com guarda-contra-vazio — documento `None`/inválido vira
   ERROR (exit 2), nunca uma string comparável.
2. Segunda checagem, **independente**, da autenticação efetiva: o diff
   textual do OpenAPI é cego para auth porque o django-ninja **omite** a
   chave `security` em rotas públicas em vez de emitir `security: []` — e
   por spec OpenAPI, ausência de `security` *herda* a segurança do
   documento pai. Já causou um caso real medido (endpoint de `catalogo`
   virou público sem o freeze acusar nada). A correção não lê o documento:
   uma sonda importa o app Django de verdade e lê a lista real de
   autenticadores que o ninja vai executar.

## Fluxo de eventos entre células

**Comércio** (síncrono + assíncrono misturados): `checkout` chama
`pagamentos` diretamente via HTTP para criar a cobrança; em paralelo emite
`pedido.criado.v1` (consumido por `leads`). `pagamentos` recebe o webhook do
Mercado Pago, confere a assinatura (INV-P10), **reconsulta o status na API
do MP** em vez de confiar no corpo do webhook, e emite
`pagamento.aprovado.v1` / `pagamento.recusado.v1` / `pix.expirado.v1` —
consumidos por `checkout` (INV-P7), `alunos` (matrícula sob lock, INV-P5, só
no aprovado), `mensageria` e `leads`. `quiz` emite `quiz.completado.v1`,
consumido por `leads` (mas o consumo em `mensageria` ainda **não está
implementado**, apesar de listado na constituição).

**Voice-of-customer**: `sugestoes` emite `sugestao.criada` /
`voto-adicionado` / `voto-removido` / `status-alterado.v1|v2`. Ninguém fora
da célula consome `status-alterado` para avisar o aluno diretamente — a
própria `sugestoes`, na mesma transação, gera `notificacao.devida.v1`
("uma carta, uma pessoa", fan-out feito **na origem**) para `notificacoes`,
que só ouve esse único stream e fica deliberadamente "burra" (grava uma
linha, incrementa contador — não sabe montar leque de destinatários). Ver
[06 — produto e decisões](06-produto-decisoes-e-roadmap.md) para o porquê.

## Isolamento entre células (`ci/cerca-de-celula.sh`)

Implementa a Lei 2.3 (uma sessão = uma célula = um worktree) e a Lei 3
(proibido importar código/ler banco de outra célula). Roda em todo PR:
calcula o diff, extrai células tocadas em `services/*`, **reprova se o diff
tocar mais de uma** — a mensagem manda abrir um PR por célula. Reprova
também se `contracts/` mudar junto com qualquer `services/`, e se
`contracts/` mudar sem a label `contrato`.

O isolamento de dados é reforçado a nível de infraestrutura, não só de CI:
cada célula tem seu próprio database + role Postgres — a conexão de uma
célula **não consegue** ler outra (`permission denied` do próprio banco, não
convenção). A única forma legítima de uma célula levar dado de outra é
**copiar** (snapshot), nunca importar código nem ler banco alheio — por isso
`checkout` congela o preço no pedido em vez de re-perguntar ao catálogo
depois.

## Achados concretos surgidos desta pesquisa (candidatos a PR pequeno)

1. **`ci/manifesto-de-contratos.json` tem motivo desatualizado** para `funil`
   e `quiz` — o texto diz "célula ainda em esqueleto, só expõe `/healthz`",
   mas `funil` já tem ~10 rotas HTML com i18n de 3 idiomas e `quiz` serve um
   formulário completo. A conclusão (sem API JSON, sem contrato) continua
   válida — só o texto do motivo mente sobre a maturidade real da célula.
2. **`sugestao.mesclada.v1` é prometido na constituição de `sugestoes`** mas
   o arquivo não existe em `contracts/eventos/` — ou ainda não foi
   implementado, ou a constituição está adiantada em relação ao contrato.
3. **`checkout` expõe um Bearer token estático no HTML da página**
   (visível em "ver código-fonte") — a própria `LICOES.md` da célula já
   registra isso como pendência de arquitetura em aberto, não decisão
   fechada, sugerindo um token de curto prazo por sessão como alternativa.
4. **`quiz` resolve "Site" localmente** (tabela própria, seedada à mão) em
   vez de chamar a API do `catalogo`, como a receita genérica do Caminho
   Dourado prescreve — desvio deliberado e documentado, mas a própria
   `LICOES.md` pede revisão humana da leitura, porque o `site_id` local
   precisa ficar sincronizado manualmente com o do catálogo, sem checagem
   automática.

Estes 4 pontos também aparecem em
[07 — oportunidades e fronteiras](07-oportunidades-e-fronteiras.md).
