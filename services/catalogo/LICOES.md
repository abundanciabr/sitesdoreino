# LICOES — célula catalogo

Específico desta célula. Transversal vai em `armadilhas/` (uma entrada por arquivo).

## Idioma do site: por que JSONField e não uma tabela `Language`

**Contexto:** fase 4 do `PLANO-I18N` (D3) — "quais idiomas este site tem" saiu do
registro interim do funil (`services/funil/sites_i18n.yaml`) e virou dado do
catálogo: `Site.default_language` (CharField) + `Site.languages` (JSONField com
`[{code, indexable}]`).

**O critério do despacho era um só:** acrescentar o décimo idioma não pode exigir
migration nova. **As duas formas passam nesse critério** — numa tabela `Language`
o décimo idioma é uma linha; no JSONField é um elemento na lista. Então o critério
não decide, e o desempate foi:

- **A lista é sempre lida inteira, junto com o site.** Ninguém consulta "quais
  sites falam espanhol" — a única pergunta é `by-host` → devolva o site com os
  idiomas dele. Uma tabela relacional serve para filtrar e juntar; aqui não há
  filtro nem junção, só um documento pequeno lido em bloco.
- **`theme` já estabeleceu o padrão** para exatamente este caso (atributo do site,
  opaco, lido em bloco) — divergir dele exigiria motivo, e não há.
- **Custo real da alternativa:** model + migration + serialização + um
  `prefetch_related` no handler, para zero benefício de consulta.

**O que a escolha cobra em troca, e como foi pago:** JSONField não valida nada
sozinho. Toda a coerência vive em `normalizar_idiomas()`
(`apps/sites/models.py`) — ver a seção seguinte.

**Se um dia virar tabela:** o gatilho é uma consulta que precise filtrar sites
POR idioma (relatório, roteamento reverso). Aí a migração é mecânica, e os testes
de `tests/test_idioma_do_site.py` continuam valendo sem reescrita, porque testam
comportamento, não armazenamento.

## `normalizar_idiomas()` NÃO pode ser fonte única do sincronizador — e o porquê custou um deploy

> **Corrigido em 24/08/2026, depois do incidente.** A versão anterior desta
> entrada dizia que `infra/sincronizar_sites.py` importava `normalizar_idiomas`
> do modelo, e chamava isso de fonte única. **Estava errado, e travou o canal de
> deploy inteiro** — ver `armadilhas/078`.

Dentro da célula, a função continua sendo fonte única de verdade: `Site.save()`
e `SiteQuerySet.update()` a chamam, e é isso que faz a regra valer nos dois
caminhos de escrita do ORM.

**Mas o `infra/sincronizar_sites.py` não pode importá-la.** Ele é *injetado*
pelo `deploy-infra` dentro do container do catálogo **que já está rodando na
VPS** — e essa imagem pode ser mais VELHA que o próprio script, porque
`deploy-infra` e `deploy-celula` disparam em paralelo no mesmo merge, sem ordem
entre si. Foi exatamente o que aconteceu: o script novo importou um símbolo que
só existia na imagem nova, o `deploy-infra` morreu em `ImportError`, e o
`deploy-celula` — que traria a imagem nova — foi barrado pelo portão fail-closed
por causa do irmão vermelho. Impasse fechado: cada um esperando o outro.

Por isso o script hoje traz uma **cópia consciente** da regra, com guarda
mecânica contra deriva (`ci/tests/test_sincronizar_sites_tolerante.py`, que lê
o AST e reprova qualquer `from apps.* import` fora de `{Site, Product, Offer}`).
A regra geral, que vale para qualquer arquivo injetado num container: **só
dependa de símbolo que já existia na versão anterior.** Duplicação vigiada custa
menos que acoplamento de versão entre dois workflows paralelos.

**Ela normaliza além de validar** (código para minúsculas, `indexable` sempre
explícito), pelo mesmo motivo que `save()` já fazia `host.lower()`: o código
aparece na URL e é comparado como string pelo funil (D5) — a forma guardada tem
de ser canônica, não "o que o declarante digitou". Efeito colateral útil: a
comparação de convergência do sincronizador (`if getattr(site, campo) != valor`)
compara duas formas canônicas, então não acusa "mudou" a cada deploy.

**`monolíngue == ("", [])`** e passa intocado pela função. É assim que todo site
que não declara idioma segue com o comportamento de sempre — por ausência, não
por caso especial espalhado pelo código.

## O guarda do `update()` recusa em vez de adivinhar

`SiteQuerySet.update()` existe por causa de `armadilhas/023` (§4.4): `update()`
não passa por `save()`. Mas há um detalhe que só aparece ao escrever o guarda:
num `update()` de queryset, se só um dos dois campos vier, a coerência dependeria
do valor **atual de cada linha** — e um guarda que precisa ler linha a linha para
decidir não é um guarda, é uma corrida. Por isso `update(languages=...)` sozinho
**é recusado**: quem toca idioma por `update()` declara o par.

`bulk_create()` continua furando os dois guardas (é assim para qualquer validação
em `save()`). Não há uso de `bulk_create` para `Site` no repositório; o handler da
API lê `indexable` com `.get("indexable", True)` para que mesmo uma linha gravada
por esse caminho ainda saia na forma do contrato.

## Campo opcional na API congelada: `default_factory`, nunca `default=`

Está em `armadilhas/075` porque vale para qualquer célula com contrato congelado.
Resumo local: os campos opcionais do `Schema` desta célula (`theme`,
`default_offer_slug` e agora `default_language`/`languages`) usam
`default_factory` porque `default=` emitiria uma chave `"default"` no OpenAPI
exportado que o contrato não tem — e o `contrato-check` reprovaria. O
`getSiteByHost` usa `exclude_unset=True` para que o site monolíngue responda sem
as chaves novas, byte-idêntico ao de antes da fase 4.
