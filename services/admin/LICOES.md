# LIÇÕES — célula `admin` (área administrativa)

> Decisões e armadilhas **só** desta célula. O que serve para qualquer célula
> mora em `armadilhas/`; o que só o humano resolve, em `ARMADILHAS-OPERACAO.md`.
> Lei desta célula: `docs/decisoes/DECISAO-celula-admin.md`.

## A célula nasceu vazia de propósito (25/08/2026)

O PR de gênese entrega **a casa, não o produto**: `/healthz` nas duas formas,
settings fail-hard, e os dois guardas que travam decisões de arquitetura antes
de existir código que possa desrespeitá-las. A porta (quem entra) vem no PR 3,
depois que a infraestrutura existir — a ordem inteira está na escada do §6 da
lei, e ela não é estética: é a correção de um impasse circular que a auditoria
pegou (o script do passo humano precisa estar na `main` antes de o mantenedor
poder executá-lo).

## Os dois guardas plantados antes do código que eles protegem

Os dois foram provados por mutação no PR de gênese — quebrados de propósito,
vistos vermelhos, restaurados (Lei 6):

| Guarda | O que trava | Provado quebrando |
|---|---|---|
| `test_healthz_script_name.py` | o prefixo `/admin` mora no env, nunca no `urls.py`; e a isenção de middleware futura compara `path_info` | `path("admin/healthz", …)` ⇒ 3 vermelhos |
| `test_inv_admin_nao_assina_sessao.py` | esta célula nunca assina o cookie do site | `SessionMiddleware` instalado ⇒ 1 vermelho |

**Por que plantar guarda antes da funcionalidade:** os dois protegem contra o
caminho *mais curto* que alguém tomaria depois. Quem escrever a porta no PR 3
vai querer `request.session[...]` para guardar "já conferi esta pessoa" — e
isso funciona em dev, passa em teste de unidade, e só quebra em produção, onde
há um segundo assinante do mesmo cookie. O guarda transforma esse erro num
vermelho de `make ci`, que é onde ele custa minutos em vez de um incidente.

## Esta célula não tem sessão, e a ausência é a decisão

Sem `SessionMiddleware`, sem `django.contrib.sessions`, sem `SESSION_ENGINE`.
Quem assina `meshcraft_sessao` é a `identidade`, e só ela
(`DECISAO-celula-de-identidade.md` §6.4). A área admin **repassa** o cookie e
pergunta quem é; nunca o lê, nunca o escreve.

Duas células assinando o mesmo cookie com chaves diferentes produzem um
cabo-de-guerra silencioso — entrar num lugar desloga do outro, sem erro em
lugar nenhum. A `DECISAO-celula-de-identidade` §5 descreve o episódio real em
que isso quase entrou em produção.

## O que já está decidido e NÃO se re-decide aqui

Tudo abaixo é lei (`DECISAO-celula-admin.md`), decidido com o mantenedor
presente em 25/08/2026 — reabrir exige sessão nova com ele, não conveniência
de despacho:

- **A porta é fail-CLOSED** — o inverso do site público. `identidade` fora do
  ar ⇒ a área admin não abre. E `404` (não `403`) para sessão válida fora da
  lista: para quem não é da casa, `/admin` não existe.
- **`ADMIN_EMAILS` autoriza; a resposta da `identidade` nunca.** Papel
  derivado a cada requisição, nunca gravado.
- **A célula não escreve fora do próprio banco** — nem no `catalogo`. Métricas
  são leitura, e o token do par entra em `TOKENS_SOMENTE_LEITURA_*` na
  provedora para que "só leitura" seja mecanismo, não texto.
- **Nada de vendas/checkout/pagamentos**, nem tile de métrica, até ordem
  explícita do mantenedor.
- **CSP com `frame-ancestors 'self'`, nunca `'none'`** — a galeria do §4.3
  serve painel em iframe de mesma origem, e `'none'` proíbe enquadramento
  inclusive de mesma origem. Este erro já foi cometido uma vez, no papel, e
  pego na revisão (`armadilhas/109`).

## A porta (PR 3, 25/08/2026) — o que ela decidiu e o que ficou de fora

**Um ponto de autorização, e só um.** Nenhuma view confere crachá: se ela
está sendo executada, o middleware já deixou passar. A lista de isentos é
`frozenset` conferido por **igualdade exata** — rota nova não escapa em
silêncio. É assim que a omissão vira impossível em vez de improvável, e é o
contrário de espalhar `if` por view, que é como `armadilhas/024` e `/086`
nascem.

**Três respostas diferentes para três situações que se parecem de dentro:**

| Situação | Resposta | Por quê |
|---|---|---|
| não consegui perguntar | **503** | mandar ao login seria mandar à porta que também caiu — e é aqui que o dono vem olhar quando algo está errado |
| perguntei, e o e-mail não está na lista | **404** | para quem não é da casa, `/admin` não existe |
| não há sessão | 302 | a pessoa pode entrar e voltar ao lugar certo |

**O CSS mora no template, embutido.** Não é preguiça: célula sob
`SCRIPT_NAME` precisa de rota própria de estático para não dar 404 só em
produção (`armadilhas/083`), e a tag `static` monta endereço do prefixo errado
nessa situação (`armadilhas/102`). Enquanto a folha couber no `base.html`, ela
fica lá — zero rota, zero armadilha. Quando crescer, entra como rota **nomeada**
servida por `url`, nunca por `static`. E a lista de isentos **não** ganha
prefixo por causa disso sem que a rota exista de verdade.

**O que ficou DE FORA deste PR, de propósito: a auditoria.** A lei (§4) exige
que toda escrita gere linha de auditoria append-only, e isso continua valendo
por inteiro. Só que **esta célula ainda não escreve nada** — não há formulário
nenhum, e a área é toda de leitura até a fase 4. Construir agora a tabela, o
trigger e os guardas seria entregar mecanismo sem o que ele protege.

**A regra que fica para quem escrever o primeiro formulário:** a auditoria
entra no MESMO PR que a primeira escrita, ou num PR imediatamente anterior a
ela — nunca depois. Com trigger no banco, e não só guarda em Python
(`armadilhas/079`: override de `save()` é contornado por `psql`, por
`cursor.execute` e por qualquer código que não importe a classe). O mesmo vale
para a verificação de frescor de sessão (`autenticada_em`), que exige Rito §3
próprio na `identidade` e só faz falta quando houver escrita.

## Armadilhas conhecidas deste caminho (o mapa, antes de doer)

A lei tem a tabela completa no §7. As que mordem primeiro, na ordem em que
aparecem:

- **`armadilhas/088`** — entre o merge deste PR e o fim do PR 2b, o
  `deploy-celula` fica **vermelho em todo merge desta célula**: o compose da
  VPS ainda não conhece o serviço. É ERROR de ambiente, não FAIL de código;
  não saia consertando a célula.
- **`armadilhas/076`** — célula nova sem linha no `rollback.yml` nasce sem
  rollback. Feito neste PR.
- **`armadilhas/089`** — o segmento `/admin` novo no Traefik reprova o
  inventário de rotas em **três** lugares do mesmo arquivo. É do PR 2b.
- **`armadilhas/029` / `081` / `083` / `102`** — a família "célula sob
  `SCRIPT_NAME` é servida num lugar diferente do que o código supõe". A
  `sugestoes` já pagou as quatro; copie as soluções dela, nunca os arquivos.
- **`armadilhas/097`** — cliente que lê env no `__init__` transforma env
  ausente em 500 em toda página, com o deploy verde. Por isso toda variável
  desta célula é lida no ponto de uso.
