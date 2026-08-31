# LIÇÕES — célula `identidade`

> Decisões e armadilhas **só desta célula**. O que serve a qualquer célula vai
> em `armadilhas/` (arquivo novo por entrada); o que é lei do assunto está em
> `docs/decisoes/DECISAO-celula-de-identidade.md`.

## Por que esta célula existe (e o que ela NÃO é)

Nascida em 25/08/2026, por decisão do mantenedor com ele presente (o rito que a
`DECISAO-onde-mora-a-sessao` §7 exige): o login deixou de morar dentro da Caixa
de Sugestões e virou prédio próprio. Esta célula faz **três** coisas:

1. a dança com o Google (`/entrar/google` → `/entrar/google/retorno`);
2. emite e lê o cookie de sessão do site (`meshcraft_sessao`, `Path=/`);
3. responde "quem é o dono desta sessão?" pela API interna (`/interno/…`).

Ela **não** renderiza página (a tela de login é do `funil`, `/{idioma}/login` —
guarda mecânico `ci/tests/test_rotas_sem_forma_de_locale.py` proíbe célula
nova de servir caminho com forma de idioma), **não** confere matrícula (quem
decide SE PODE é a célula dona do recurso, na hora do recurso) e **não**
autoriza nada (reconhecer não é autorizar — invariante da
DECISAO-onde-mora-a-sessao §4, que continua valendo com esta célula
respondendo).

## O vocabulário de recusa é CONTRATO com o `funil`

Toda recusa da porta redireciona para `/{idioma}/login?erro=<chave>`. As
chaves, que a tela do `funil` traduz nos três idiomas:

| chave | quando |
|---|---|
| `interrompida` | a pessoa voltou do Google sem concluir (`?error=`) |
| `nao-confere` | `state` ausente/errado — retorno fora de ordem ou forjado |
| `nao-configurada` | falta credencial do Google no env desta célula |
| `google-indisponivel` | o Google não respondeu ou respondeu inutilizável |
| `email-nao-verificado` | o Google não confirma o e-mail como verificado |

Mudar uma chave aqui é mudar a tradução lá — e vice-versa. O idioma da
aterrissagem sai do `?next=` pedido (`/es/…` ⇒ `/es/login`), com `pt-br` de
padrão.

## O cookie tem o MESMO nome que a Caixa publicava — e isso é deliberado

`meshcraft_sessao`, `Path=/`: o endereço no navegador não mudou; mudou quem
assina. Cookie assinado pela chave antiga (da `sugestoes`) falha a assinatura
aqui e vira visitante — **todo mundo é deslogado uma vez na virada**, e reentra
com um clique. Dois nomes convivendo seria pior: a armadilha da
DECISAO-onde-mora-a-sessao §5.1 (dois cookies de mesmo nome em caminhos
diferentes) só não volta porque a Caixa **para de escrever** o cookie no mesmo
corte (há guarda lá).

## `/entrar/sair` é `csrf_exempt` — e a defesa é a de ORIGEM

Quem posta para cá são formulários renderizados por OUTRAS células (`funil`,
Caixa), que não têm como carregar o token de CSRF desta. A defesa equivalente:
`Origin` (ou `Referer`) tem de ser o próprio host, senão 403; sem cabeçalho
nenhum, 403 também (fail-closed). O pior caso de um bypass aqui seria um
logout indesejado — não há escrita além de apagar a própria sessão. Se um dia
esta célula ganhar um POST que CRIE estado, ele usa CSRF de verdade, não este
padrão.

## A resposta completa (`/sessao/completa`) tem um degrau a mais de propósito

`TOKENS_ACEITOS_*` prova quem chama; `TOKENS_COMPLETOS_*` decide quem pode ver
**e-mail**. O `funil` tem só o primeiro (ele quer um nome para o canto da
página); a Caixa tem os dois (ela confere matrícula e staff sobre o e-mail,
nas listas DELA). O degrau é conferido no handler contra
`settings.TOKENS_COMPLETOS` — um segundo security scheme no contrato dobraria
a superfície congelada por algo que um 403 nomeado explica melhor.

## O `redirect_uri` neutro já estava cadastrado desde 24/08/2026

`https://meshcraft.top/entrar/google/retorno` foi cadastrado no console do
Google um dia ANTES desta célula nascer (DECISAO-onde-mora-a-sessao §5.2,
"cadastrado justamente para o dia da célula dedicada"). Por isso a gênese não
tem passo de console do Google — as credenciais são as MESMAS do aplicativo
OAuth existente, copiadas de `env/sugestoes.env` para `env/identidade.env`
pelo bloco do mantenedor. `reverse()` monta o endereço, jamais string à mão; e
`SECURE_PROXY_SSL_HEADER` é o que faz ele sair `https` atrás do Traefik.

## Multissítio: a rota casa em qualquer host, o Google só conhece um

O Traefik roteia `/entrar` por CAMINHO, em qualquer domínio da plataforma —
mas o único `redirect_uri` cadastrado é o de `meshcraft.top`. Entrar a partir
de outro domínio falharia no Google com `redirect_uri_mismatch`. Hoje isso é
teórico (o login só é oferecido pelo site multilíngue, que é o meshcraft);
no dia em que outro domínio quiser login, o passo é cadastrar o retorno DELE
no console — uma linha no aplicativo OAuth, nenhum código aqui.

## `conn_max_age` > 0 sob ASGI VAZA uma conexão por requisição — o pool é a saída

Esta célula foi a única da plataforma com `conn_max_age=60` (25/08/2026, por
uma medição legítima: conexão nova + SELECT custa ~24ms, o mesmo SELECT
reaproveitando a conexão custa ~0,2ms, e a `identidade` responde "quem é você"
no caminho de toda página logada).

O que a medição não viu: **sob ASGI o Django abre um `ThreadSensitiveContext`
por REQUISIÇÃO** (`django/core/handlers/asgi.py`, `ASGIHandler.__call__`), e o
asgiref cria um executor de uma thread para cada um. A conexão de banco do
Django é **thread-local**. No fim da requisição, `request_finished` chama
`close_old_connections`, que só fecha a conexão se ela estiver **obsoleta** —
com `conn_max_age=60` ela não está. A thread morre, a conexão fica aberta, e
não sobra ninguém com uma referência para fechá-la.

Nas outras 12 células o valor é o default `0` do `dj_database_url`, então a
conexão fecha ao fim da requisição e o vazamento não existe — **esta era a
única**. Foi por aqui que os 86 pedidos quase simultâneos do painel, em
27/08/2026, estouraram o limite de 100 conexões do Postgres da plataforma
inteira: cada pedido do painel passa pelo login.

**A saída não é voltar para `conn_max_age=0`** — isso devolveria os 24ms. É o
pool nativo do Django 5.1 (`OPTIONS["pool"]`, extra `psycopg[pool]`): o pool
vive em `_connection_pools`, atributo de **classe** do `DatabaseWrapper`, logo
é do PROCESSO e não da thread. Thread descartada devolve a conexão em vez de
abandoná-la, e `max_size` põe um teto que não existia. O Django exige
`CONN_MAX_AGE == 0` junto com o pool, e levanta `ImproperlyConfigured` se você
esquecer — o guarda de `tests/test_pool_de_conexoes.py` encena essa recusa de
propósito, para não nascer verde por acidente (`armadilhas/132`).

## O segundo login (por senha) — a mesma lição do `/sair`, mas na direção oposta (31/08/2026)

`DECISAO-login-por-senha.md` deu à célula um SEGUNDO caminho de entrada,
para quem não tem conta do Google — `entrar_senha` (`apps/core/views.py`),
que termina exatamente no mesmo `ses.abrir_sessao` que o retorno do Google já
usa. A parte que valeu a pena registrar:

**A seção acima ("`/entrar/sair` é `csrf_exempt`") já avisava, por escrito,
antes de este login existir: aquele padrão é só para ações que DESTROEM
estado.** Login CRIA sessão — é exatamente o caso que a frase reservou. A
tentação óbvia (copiar `_mesma_origem` para `entrar_senha` também, "já que
funcionou pro logout") teria sido copiar o padrão errado: Origin/Referer
prova de onde a REQUISIÇÃO saiu, não protege contra "login CSRF" (um site
malicioso forçar a vítima a logar como o ATACANTE, com as credenciais dele,
para minerar o que a vítima digita ou faz achando que está na própria conta).

**A saída, sem inventar CSRF cruzando célula:** `apps/core/tokens_de_entrada.py`
assina um valor efêmero com `TimestampSigner` (o `funil` busca via
`issueLoginToken` ao montar `/login`, embute como campo oculto). Mesmo
princípio do `state` do OAuth — só que emitido por uma célula e consumido
pela mesma, atravessando a fronteira por um valor opaco carregado por outra
célula, exatamente como o cookie de sessão já atravessa. **Detalhe que
custou um teste vermelho:** `TimestampSigner().sign(valor)` não amarra o
token a UM propósito por si só — qualquer string assinada com o mesmo
`SECRET_KEY` "confere". É o `salt` (`TimestampSigner(salt=...)`) que separa
usos diferentes da mesma chave, e é conferir o VALOR desassinado (não só a
assinatura) que fecha a porta para "um token de outro assunto, mas assinado
por esta célula, também vale aqui".

## `make ci` fica vermelho até o contrato mergear — e a ordem certa é exportar, não escrever de cabeça

Vivido na prática: o contrato de `issueLoginToken`/`setPassword`/`resetPassword`
foi escrito à mão no PR de contrato (`DECISAO-login-por-senha.md`), e quando o
código desta célula saiu pronto, o freeze (`ci/freeze-de-contrato.sh
identidade`) achou DUAS divergências reais — descrição com palavras
ligeiramente diferentes (fácil: copiar o texto exato do congelado para o
docstring) e um bloco `security: [{bearerAuth: []}]` POR OPERAÇÃO que o
código nunca emitiria (esta célula usa `security` GLOBAL, `openapi_extra` em
`config/api.py`; nenhuma operação, nova ou velha, tem bloco próprio). A
segunda exigiu um PR de contrato à parte, só para apagar as duas linhas
erradas — `armadilhas/243` já documentava o sintoma ("vermelho até o
contrato mergear é o portão funcionando"), mas não cobria o caso de o
CONTRATO em si estar errado, só o caso comum de "código ainda não implementa
o que o contrato já promete". **Lição para a próxima operação nova:**
escreva o handler primeiro, rode `python manage.py export_openapi`, e monte
(ou audite) o texto do contrato A PARTIR do que sai dali — nunca as duas
proses de cabeça, mesmo com cinco minutos de distância uma da outra.
