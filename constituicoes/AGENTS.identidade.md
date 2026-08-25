# Constituição da Célula: identidade (o login do site)
> **Jurisdição:** governa apenas `services/identidade/`. Herda `CONSTITUICAO.md`.
> **STATUS:** ATIVA (nascida em 25/08/2026, sessão de arquitetura com o mantenedor) · **Merge:** auto-merge permitido com CI verde

## Missão
Provar QUEM É a pessoa, para o site inteiro. Três coisas, e mais nada: a dança
com o Google, o cookie de sessão do site (`meshcraft_sessao`, `Path=/`) e a
resposta "quem é o dono desta sessão?" pela API interna. Lei do assunto:
`docs/decisoes/DECISAO-celula-de-identidade.md`; o desenho herdado e o
invariante que a governa estão em `docs/decisoes/DECISAO-onde-mora-a-sessao.md`.
A frase está dentro do próprio contrato congelado: *"A resposta desta API
RECONHECE uma pessoa; ela nunca AUTORIZA nada — autorização é fail-closed na
célula dona do recurso."*

## Fronteiras
- **PERMITIDO ESCREVER:** `services/identidade/**`
- **SOMENTE LEITURA:** `contracts/identidade.openapi.yaml` — o PRÓPRIO contrato,
  congelado (`freeze: required` no manifesto). Hoje `funil`, `sugestoes` e
  `admin` consomem estas duas operações: mexer nelas é Rito §3, nunca decisão de
  sessão
- **PROIBIDO (nem ler):** as demais células, `infra/`, qualquer segredo de
  pagamento. Esta célula não consome API de célula nenhuma — o `make mocks` dela
  diz isso por escrito

## Comunicação
- **Expõe (gente):** `/entrar/google`, `/entrar/google/retorno` (GET) e
  `/entrar/sair` (POST), roteados pelo Traefik em
  `Host(meshcraft.top) && PathPrefix(/entrar)`, **sem remoção de prefixo e sem
  `SCRIPT_NAME`**: o urlconf declara os caminhos por extenso, porque
  `/entrar/google/retorno` é o endereço EXATO cadastrado no console do Google
- **Expõe (máquina):** `GET /interno/sessao` (`getSession`) e
  `GET /interno/sessao/completa` (`getSessionFull`), em
  `http://identidade:8000/interno` — **sem rota no Traefik, de propósito**: quem
  pergunta o faz pela rede interna do Docker. `/healthz` é da sonda do compose
- **Consome:** nenhuma célula. Só o Google (autorização, troca do código e
  `userinfo`), com timeout explícito de 5s e um `httpx.Client` por processo
- **Auth:** Bearer estático por par (`TOKENS_ACEITOS_<PAR>`; conjunto nasce
  vazio ⇒ 401 para todos). O e-mail exige um degrau A MAIS
  (`TOKENS_COMPLETOS_<PAR>`), conferido no handler ⇒ 403 sem ele
- **Emite:** nada. Sem outbox, sem worker, sem auxiliar no compose
- **Banco:** `identidade_db` (role `identidade_user` — não enxerga nenhum outro
  database). **Uma tabela:** `Identidade` (id opaco, e-mail único, provedor,
  nome exibido, criada em)

## O que esta célula NÃO é
- **Não autoriza.** O `papel` que ela devolve (`aluno`/`staff`) é de
  **EXIBIÇÃO** — decide o que o site MOSTRA, nunca o que a pessoa PODE. Quem é
  staff de outra célula é lista DELA (`SUGESTOES_STAFF_EMAILS`, `ADMIN_EMAILS`),
  conferida lá
- **Não guarda matrícula, nem consulta nenhuma.** A porta do site não confere
  nada além do e-mail verificado do Google; quem decide SE PODE é a célula dona
  do recurso, na hora do recurso
- **Não renderiza página** e não serve caminho com forma de idioma (guarda:
  `ci/tests/test_rotas_sem_forma_de_locale.py`). Toda recusa volta para
  `/{idioma}/login?erro=<chave>`, e o vocabulário de chaves é contrato com o
  `funil` (tabela em `services/identidade/LICOES.md`)
- **Não é dona do dado de ninguém.** Cada célula casa a pessoa por snapshot
  próprio (Virtude da Lei 3); ninguém lê este banco

## Invariantes desta célula
- **Reconhecer não é autorizar** (`DECISAO-onde-mora-a-sessao` §4), nas duas
  metades: reconhecimento falha **ABERTO** — identidade fora do ar ⇒ a vitrine
  abre mostrando "Entrar"; autorização falha **FECHADO** na célula dona do
  recurso (a área admin, no mesmo caso, não abre).
- **O e-mail vive numa linha só e não circula** (EVO-01 §3). `/sessao` **nunca**
  o devolve; `/sessao/completa` só a par que esteja também em
  `TOKENS_COMPLETOS_*`. Par novo com esse direito **se registra por escrito** na
  lei da célula (§4/§6.3), no mesmo PR. Guardas:
  `tests/test_inv_sessao_nao_vaza_email.py`,
  `tests/test_inv_sessao_completa_so_para_autorizados.py`.
- **O papel é derivado a cada requisição** de `IDENTIDADE_STAFF_EMAILS`, jamais
  gravado na linha nem no cookie — trocar quem é staff é editar env e reiniciar,
  sem migração e sem deploy. Guarda: `tests/test_inv_papel_derivado.py`.
- **A reconferência da linha no banco é a ÚNICA revogação que existe.** O cookie
  é assinado e sem estado: identidade apagada ⇒ a sessão cai no request
  seguinte. Trocar isso por cache, ou por confiar no conteúdo assinado, remove o
  freio de mão da plataforma. Guarda: `tests/test_inv_revogacao.py`.
- **Só esta célula assina `meshcraft_sessao`** — `Path=/`, HttpOnly,
  `SameSite=Lax` (obrigatório: com `Strict` o navegador não manda o cookie na
  volta do Google e TODO login legítimo falha como se fosse falsificação),
  Secure fora de DEBUG. Guarda: `tests/test_inv_cookie_de_sessao.py`.
- **Uma pessoa, uma linha:** `email` é `unique` e a entrada usa `get_or_create`;
  `nome_exibido` só é gravado na cunhagem. E-mail **não verificado** pelo Google
  é recusado, sem exceção (`is not True`, nunca `not`). Guarda:
  `tests/test_inv_identidade_idempotente.py`.
- **O `?next=` nunca vira redirect aberto** — só caminho local passa, todo o
  resto vira `/`. Guarda: `tests/test_inv_next_seguro.py`.
- **A porta fala com o Google e com mais ninguém**: salto de rede novo neste
  fluxo fica vermelho sozinho, sem o guarda precisar saber o nome do que foi
  consultado. Guarda: `tests/test_inv_porta_nao_consulta_ninguem.py`.
- **O `redirect_uri` é montado por `reverse()` sobre `SECURE_PROXY_SSL_HEADER`**,
  jamais à mão, e a célula **não crava domínio** (o host vem da requisição).
  Remover aquela linha derruba o login em produção com CI verde, deploy verde e
  `/healthz` respondendo 200 — foi medido por mutação. Guarda:
  `tests/test_inv_redirect_uri.py`.
- **`Host(meshcraft.top)` no Traefik é cláusula deliberada** (achado da cadeira
  de IAM, 25/08/2026): sem ela, qualquer domínio apontado para a VPS serviria
  esta porta. Domínio novo com login = o retorno DELE cadastrado no console do
  Google + uma linha lá — nunca uma linha a menos aqui.
- **Só `DJANGO_SECRET_KEY` e `DATABASE_URL` são lidas no import.** Toda variável
  futura é lida no ponto de uso e fecha apenas o caminho que precisa dela: o
  container não morre no boot por credencial que ainda não foi colada na VPS.

## Definição de Pronto
`make ci` verde (`lint`, `type`, `test`, `contrato-check`) · guarda novo provado
por mutação (vermelho sem o fix, verde com) · diff no escopo.

## Ritos
RITOS.md §1, §2. Operação, campo ou payload novo em
`contracts/identidade.openapi.yaml` é Rito §3 — dois PRs e sessão com o
mantenedor. Quatro coisas **não se decidem em sessão**: página HTML, rota com
forma de idioma e consulta de matrícula na porta já têm casa, e é outra (§6.1 da
lei); par novo em `TOKENS_COMPLETOS_*` exige o registro escrito do §6.3.

> **Escrita a partir do código, conferido em 25/08/2026** — não do plano:
> `config/settings.py`, `config/api.py`, `config/urls.py`, `apps/core/api.py`,
> `apps/core/auth.py`, `apps/core/sessao.py`, `apps/core/views.py`,
> `apps/core/clients.py`, `apps/identidade/models.py`, `Makefile` e `LICOES.md`
> da célula; os nove testes de `services/identidade/tests/`;
> `contracts/identidade.openapi.yaml`; `ci/manifesto-de-contratos.json`;
> `infra/docker-compose.yml`, `infra/traefik/dynamic/plataforma.yml`,
> `infra/env/identidade.env.exemplo` e `infra/provisionar-identidade.sh`; e as
> leis `DECISAO-celula-de-identidade.md`, `DECISAO-onde-mora-a-sessao.md` §4 e
> `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md` §3.
