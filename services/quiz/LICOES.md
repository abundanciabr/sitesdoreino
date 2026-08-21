# LICOES — services/quiz

> Decisões e armadilhas específicas desta célula. Regra geral em `ARMADILHAS.md`.

## Site resolvido LOCALMENTE, não via API do catálogo (desvio deliberado da receita CONV-SITE)

**Contexto:** `CAMINHO-DOURADO.md` §3 define CONV-SITE como uma chamada HTTP a
`CATALOGO_API_URL` para resolver Host→Site, e lista explicitamente quiz entre as
células que usam essa convenção. Um agente lendo só a receita implementaria
exatamente isso — um `CatalogoClient` como o do checkout.

**Por que não foi isso que foi implementado:** `constituicoes/AGENTS.quiz.md` (o
documento mais específico, e por isso mais autoritativo para esta célula) diz
duas coisas que contradizem a chamada de rede:

1. `## Comunicação` → `Consome: nada`.
2. `## Fronteiras` → `SOMENTE LEITURA: contracts/eventos/quiz.completado.v1.json`
   — não lista `contracts/catalogo.openapi.yaml` (checkout e funil listam o seu
   explicitamente, exatamente porque chamam a API do catálogo).

Comparar os três `AGENTS.<celula>.md`: sempre que uma célula chama a API de
outra, isso aparece em **duas** frentes (Fronteiras E Comunicação) — quiz não
tem nenhuma das duas. Isso não parece esquecimento; parece intenção de que o
Crivo seja mesmo "burro" (a missão diz "o quiz não sabe o que é um cartão de
crédito" — a mesma filosofia de isolamento vale para não depender do catálogo
estar de pé).

**O que foi implementado:** `apps.quiz.models.Site` — cadastro **local**
(host, site_id, name), seedado via `seed_quiz` (R9), nunca sincronizado por
rede. `apps/core/middleware.py` consulta esse modelo local em vez de fazer
`httpx.get(.../sites/by-host/...)`. Sem cache de TTL (a receita cacheia para
evitar round-trip de rede repetido; aqui é uma query indexada local, o cache
não paga o preço que paga lá).

**A costura que isso exige do operador:** o `id` do `Site` local **precisa**
ser o mesmo `site_id` que o catálogo usa para aquele host — é assim que
`quiz.completado.v1` correlaciona com o que leads/checkout enxergam do mesmo
lead. Isso é responsabilidade de quem roda `seed_quiz --site-id <id-do-catalogo>`,
não é garantido por código. Não existe hoje verificação automática de que os
dois IDs continuam batendo se o catálogo mudar o ID de um site.

**Se a intenção real era consumir o catálogo:** os dois documentos (receita
genérica vs. constituição da célula) estão em tensão, e resolver isso é
decisão de arquitetura do mantenedor, não deveria ter sido decidida em uma
sessão de feature (Lei 2 do `CAMINHO-DOURADO.md`: "desviar de uma receita não
é improviso local — é issue `arquitetura:` ANTES"). Como o despacho pedia
para seguir em frente, a leitura acima foi registrada aqui e no relatório
final da sessão em vez de travar a entrega — mas **um humano deveria revisar
essa leitura** e, se discordar, abrir a issue e trocar para o `CatalogoClient`
padrão.

## Sem `apps/quiz/__init__.py`

Confirma o que `ARMADILHAS.md` §4.3 já registrava para `management/commands/`:
pacote de namespace (Python 3, sem `__init__.py`) funciona em `INSTALLED_APPS`
também para o pacote raiz do app, não só para `management/commands/`. Usado
aqui para caber no orçamento de arquivos do despacho — não é necessidade
técnica, é economia deliberada.

## Sem relay do outbox (Huey → Redis Streams)

Igual ao estado atual do checkout (`ARMADILHAS.md` §9): o evento
`quiz.completado.v1` é gravado transacionalmente na outbox
(`apps.quiz.models.OutboxEvent`), mas ninguém publica no Redis Streams ainda.
Fica pendente para um despacho futuro, mesma dívida já registrada para
checkout.

## Sem contrato REST — só páginas HTML

Diferente de checkout (django-ninja + `contracts/checkout.openapi.yaml`), o
Crivo não expõe API JSON nenhuma: é formulário HTML simples com POST-redirect-GET
(sem Alpine, sem `api.js` — não há necessidade de polling de status como no
Pix). `make contrato-check` já cai no fallback "não expõe contrato congelado"
sem precisar de nenhum ajuste.
