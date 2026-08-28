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

## O painel da escola (28/08/2026) — duas lições que custaram tempo aqui

**1. `armadilhas/081` mordeu de verdade nesta célula, e do jeito silencioso.**
O mapa acima já a citava como "família conhecida"; conhecer o caso não impediu
de cair nele. O teste que prova que os links levam o prefixo público começou
escrito como `settings.FORCE_SCRIPT_NAME = "/admin"` — e ficou **vermelho por
não medir nada**: `reverse()` não lê essa variável, lê um prefixo de THREAD que
o servidor preenche (`ASGIHandler.__call__` chama `set_script_prefix()`), e os
handlers de teste do Django não chamam. A cura é a da armadilha:
`set_script_prefix("/admin/")` com restauração no `finally` — o prefixo vaza
entre testes. Sorte: o teste falhou. Escrito na ordem inversa (asserção fraca
primeiro), teria ficado verde para sempre guardando o nada.

**2. "Não sei quantos" e "não há nenhum" são telas diferentes — e o template
tem de saber disso.** A página de alunos mostra `—`, nunca `0`, enquanto não
houver de onde ler o número: um `0` diria ao mantenedor *"ninguém está
esperando aprovação"*, quando a verdade é *"ninguém está contando"*. Isso é
falso-verde de produto (`RETROSPECTIVA-FASE-D.md` §1). A mecânica: `{% if
tipo.quantidade is None %}`, **nunca** `{% if tipo.quantidade %}` — zero é
falso em template, e o dia em que a contagem existir um zero legítimo cairia
no ramo do "não sei", mentindo para o outro lado. O guarda
(`tests/test_painel_da_escola.py`) renderiza a mesma página com `0` e exige
que a tela mude — sem isso ele estaria só confirmando que o traço aparece.

**3. E uma lição cara do mesmo dia: esta célula publicou, na tela do
mantenedor, que a fila de espera de alunos "não existe em lugar nenhum".**
Existia desde a véspera — lei (`docs/decisoes/DECISAO-fila-de-liberacao.md`),
três portas no contrato congelado da `alunos` e o formulário no ar. A causa
está em `armadilhas/148`, e é estrutural: o reconhecimento da sessão aconteceu
no clone principal, que estava **75 merges** atrás do `origin/main`, enquanto o
worktree onde ela trabalhou nasceu fresco. Bancada nova, mapa velho.

**A regra que fica para quem escrever a próxima tela desta célula:** a área
administrativa é, por natureza, a que mais fala sobre as OUTRAS células — e é a
única do projeto onde uma frase errada sobre outra célula chega direto aos
olhos do dono, sem passar por nenhum teste. Antes de afirmar que algo não
existe, leia `contracts/<celula>.openapi.yaml` do `origin/main`
(`git show origin/main:contracts/alunos.openapi.yaml`), nunca o arquivo do
disco de um clone de longa duração. O guarda que mecaniza a parte que dá para
mecanizar está em `tests/test_painel_da_escola.py`: porta declarada tem de
existir no contrato, e porta que o contrato tem não pode ficar sem dono nesta
tela.

## A auditoria append-only e o `TRUNCATE` que ninguém lembra (28/08/2026)

A primeira escrita desta área — liberar e recusar quem está na fila — trouxe a
auditoria junto, como a regra acima manda. Três coisas que quem mexer nela
precisa saber:

**1. O trigger tem TRÊS metades, e a terceira é a esquecida.** `UPDATE` e
`DELETE` são as óbvias; `TRUNCATE` não dispara trigger de linha nenhum e
apagaria a tabela inteira sem acusar nada. No Postgres ele exige um trigger
`FOR EACH STATEMENT` próprio, e ele está lá.

**2. Os dois dialetos são escritos de propósito.** Produção é Postgres, a suíte
local é SQLite. Um trigger só de Postgres deixaria o guarda inexistente
justamente onde o agente o exercita todo dia — e guarda que ninguém consegue
ver morder é indistinguível de nenhum guarda. Provado por mutação: comentar o
`RunPython` da migration deixa `test_a_auditoria_e_append_only_no_BANCO`
vermelho.

**3. A armadilha que ainda não doeu, escrita antes de doer:** no Postgres, um
teste `django_db(transaction=True)` limpa as tabelas com `TRUNCATE` — e o
trigger o recusa. Esta célula não tem nenhum teste assim hoje. Quem escrever o
primeiro vai bater nisto, e a saída certa é **o teste não tocar nesta tabela**,
nunca afrouxar o trigger.

**E a decisão de desenho que evita duplicação:** esta tabela NÃO é uma segunda
fonte de "quem é aluno" — esse fato mora na `alunos`, que já carimba
`decidido_em`/`decidido_por` na matrícula. O que ela guarda é o que foi feito
ATRAVÉS desta área, **inclusive o que falhou** — e é justamente o caso que não
deixa rastro em lugar nenhum: uma decisão que a `alunos` não recebeu não tem
linha para carimbar lá.

**Um detalhe que o CI pegou e a máquina local não podia pegar:** a primeira
versão do teste exigia `IntegrityError`. No SQLite o `RAISE(ABORT)` produz
exatamente isso; no Postgres, um `RAISE EXCEPTION` sem `ERRCODE` sai com o
código genérico `P0001`, que o Django traduz em **`ProgrammingError`**. O
guarda passava aqui e reprovava lá — **pela classe da exceção, não pelo
comportamento**. A correção foi nos dois lados, e a ordem importa: o trigger
passou a declarar `ERRCODE = '23000'` (para os dois bancos falharem IGUAL, que
é o que quem escrever um `except` daqui a meses precisa), e só então a asserção
passou a aceitar a classe-pai `DatabaseError` conferindo a mensagem. Afrouxar a
asserção sem corrigir o trigger teria escondido uma diferença real entre dev e
produção.

## Auditoria append-only e "apagar de vez" brigam — e a briga tem lado certo (28/08/2026)

Na mesma tarde, esta célula ganhou (a) uma auditoria append-only por trigger no
banco e (b) um botão que apaga uma pessoa de vez. **As duas coisas são
incompatíveis se a auditoria guardar dado que a PESSOA forneceu**: apagar
alguém exigiria editar linhas que o próprio banco recusa editar.

O conflito nasceu de código escrito horas antes: o formulário de gestão gravava
`nome_completo=Fulano`, `whatsapp=...` no detalhe da auditoria.

**A regra, e ela vale para toda escrita desta área:** a auditoria guarda o que
o OPERADOR fez e escreveu — os NOMES dos campos tocados, a decisão, o motivo
que ele digitou. Nunca os valores que a pessoa preencheu. O guarda está em
`tests/test_gestao_na_tela.py::test_a_auditoria_diz_QUAIS_campos_mudaram_e_nunca_os_valores`,
e ele procura os valores no texto — não confia na leitura do código.

**A lição geral, e é ela que vale além deste caso:** append-only e direito ao
esquecimento não se resolvem no dia do conflito. Ou a tabela nasce sem dado
pessoal, ou um dos dois vai ter de ser furado depois — e o que se fura, na
pressa, é sempre o guarda.

## A porta passou a tocar o banco a cada requisição (28/08/2026)

Com a lista de administradores meio no env e meio no banco
(`DECISAO-administradores-e-apagar` §3.1), `_emails_autorizados()` consulta o
banco em TODA requisição autorizada. Consequência imediata na suíte: 60 testes
que nunca precisaram de banco passaram a reprovar com `Database access not
allowed` — e a leitura errada seria "a mudança quebrou a porta".

Não quebrou: mudou de quanto a porta precisa para responder. `tests/conftest.py`
libera `db` para toda a suíte, que é o que produção faz.

**O que NÃO mudou, e é o que sustenta o resto:** `/healthz` continua sem tocar
no banco (é caminho isento, e a porta devolve antes da lista), e falha de banco
vale só o env — **erro nunca AMPLIA quem entra**. As duas coisas têm teste.
