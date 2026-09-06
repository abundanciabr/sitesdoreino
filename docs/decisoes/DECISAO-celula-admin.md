# DECISÃO — a célula `admin` nasce (a área administrativa da plataforma)

> **Aprovada pelo mantenedor em 25/08/2026**, com ele presente na sessão, ao
> fim de um caminho de quatro etapas no mesmo dia: o plano
> (`PLANO-AREA-ADMIN.md`), a auditoria de quatro cadeiras independentes
> (`PARECER-BANCA-AREA-ADMIN.md`), as seis perguntas respondidas por ele uma a
> uma, e uma revisão final que achou cinco erros de fato — quatro deles
> introduzidos ao aplicar as próprias respostas (`armadilhas/109`).
>
> Este documento é a **lei** do assunto: o que não se re-decide sem uma sessão
> nova com o mantenedor. O **plano** continua sendo o mapa de execução (as
> seções por fase, a escada de PRs, as armadilhas do caminho) e é lá que um
> despacho vai buscar o "como". Quando os dois divergirem, **esta lei vence**.

---

## 1. O que nasce

Uma célula própria, `admin`, servindo `meshcraft.top/admin/`: painéis de
métricas vivas, galeria de painéis de status, usuários, cursos, configuração e
roadmap interno — a sala de comando da plataforma, atrás do login do site.

**Por que célula própria, e não uma seção dentro de outra:** Lei 2 (o raio de
explosão é uma célula — a área admin caindo não pode derrubar a vitrine, e um
deploy da vitrine não pode derrubar a ferramenta de operação); muralha de
código (a área admin cresce por anos, e dentro do `funil` cada crescimento
colidiria no portão "1 PR = 1 célula"); muralha de dados (`admin_db` com role
próprio — a connection string da área admin *não consegue* ler o banco de
ninguém). As três alternativas consideradas e por que foram descartadas estão
no §2 do plano.

## 2. A porta — e é aqui que esta célula é diferente de todas as outras

A área admin **não tem login próprio**: usa o do site (célula `identidade`),
como qualquer página. O que ela tem é uma **lista própria**, e um modo de
falha invertido.

| Situação | Site público (`funil`) | Área admin |
|---|---|---|
| `identidade` fora do ar | página abre, mostra "Entrar" (fail-OPEN) | **não abre** (fail-CLOSED) |
| Sessão válida, e-mail fora da lista | — | **404**, não 403 |
| Sem sessão | — | 302 para o login do site |

**A inversão é deliberada e é a aplicação literal do invariante *reconhecer não
é autorizar*** (`DECISAO-onde-mora-a-sessao.md` §4): reconhecimento falha
aberto, autorização falha fechada. Cada linha desta tabela nasce com
teste-guarda no mesmo PR (Lei 8).

Três regras que decorrem dela e não se negociam:

1. **`ADMIN_EMAILS` autoriza; a resposta da `identidade` nunca** — nem o campo
   `papel`, nem o e-mail por si. O papel é derivado a cada requisição e nunca
   gravado: trocar quem é admin é editar env e reiniciar.
2. **Esta célula nunca assina o cookie `meshcraft_sessao`.** Quem assina é a
   `identidade`, e só ela (`DECISAO-celula-de-identidade.md` §6.4). Duas
   células assinando o mesmo cookie com chaves diferentes é um cabo-de-guerra
   silencioso. Guarda: `services/admin/tests/test_inv_admin_nao_assina_sessao.py`.
3. **`/admin` é preso a `Host(meshcraft.top)`** no Traefik. Sem isso, qualquer
   domínio apontado para a VPS serviria a porta administrativa da plataforma —
   matéria-prima de golpe. Domínio novo com área admin é decisão nova.

## 3. O que o mantenedor decidiu em 25/08/2026 (as seis)

Colhidas por pergunta estruturada de múltipla escolha — formato que ele
confirmou como o certo para toda decisão dele daqui em diante (`CLAUDE.md`).

| # | Decisão |
|---|---|
| 1 | **Escopo completo**, não versão reduzida — `DECISAO-filosofia-de-escopo.md` |
| 2 | **A área não escreve no `catalogo`** — cursos e preço são somente-leitura; editar continua por PR |
| 3 | **Métricas em tempo real, por HTTP direto** — não por evento; aceitas as 5 sessões de Rito de Contrato que isso custa |
| 4 | **Mesma origem e sessão do site**, com CSP própria e verificação de frescor para escrita — sem login próprio, sem domínio separado |
| 5 | **Marketing sai do congelamento de vendas** e vira seção própria |
| 6 | **Sem botão de emergência à parte** — porta travada se conserta por PR, como tudo neste projeto (coerente com a Lei 5) |

## 4. O que fica proibido, por decisão e não por omissão

1. **Nada de vendas, checkout ou pagamentos** — nem um tile de métrica — até
   ordem explícita do mantenedor (diretiva de 22/08/2026). Quem começar por aí
   está fora de mandato.
2. **A célula não escreve fora do próprio banco.** Métricas são leitura, e o
   token do par entra em `TOKENS_SOMENTE_LEITURA_*` na provedora — porque
   `TOKENS_ACEITOS_*` sozinho é conjunto plano e concederia `POST /leads` e
   `POST /matriculas` de brinde. Sem essa segunda lista, "só leitura" seria
   texto, não mecanismo.
3. **Toda escrita gera linha de auditoria**, em tabela append-only protegida
   nas três metades que `armadilhas/023` e `/079` cobram — `save()`,
   `QuerySet.update()` e cascade, esta última por trigger no banco. Formulário
   novo sem linha de auditoria não mergeia.
4. **Nenhum login próprio, nenhum domínio separado, nenhum break-glass** — os
   três foram descartados por decisão explícita (§3), não por esquecimento.
5. **CSP com `frame-ancestors 'self'`, nunca `'none'`** — `'none'` proíbe
   enquadramento inclusive de mesma origem, e a galeria de painéis serve
   iframe de mesma origem. O erro já foi cometido no papel e pego na revisão
   (`armadilhas/109`).
6. **UI só em PT-BR, sem rota com forma de idioma, sem página pública.** A
   única rota de TELA que responde sem crachá é `/healthz`. Desde 06/09/2026
   existe também uma porta de MÁQUINA, `/interno/`, que não é tela e tem
   cadeado próprio: ver a emenda do §7.

## 5. O custo, declarado (para ninguém ser surpreendido)

- **Fase 1 (até a porta abrir):** 7–9 merges, incluindo **um passo do
  mantenedor** (H21) — uma linha de colar, script versionado, nunca bloco
  multi-linha.
- **O §4 inteiro do plano:** da ordem de **30 merges**, sendo a fase 2 sozinha
  12–13 PRs **e cinco sessões de arquitetura com o mantenedor presente** (o
  preço da decisão 3).
- **Fora da conta, porque dependem de decisão dele quando chegar a hora:** a
  contagem de visitas (não existe dado hoje) e a verificação de frescor de
  sessão (Rito §3 próprio na `identidade`).

## 6. Estado

**Aprovada e em execução desde 25/08/2026.** A escada de entrega, os mandatos
de cada PR e as armadilhas do caminho estão no `PLANO-AREA-ADMIN.md` §6 e §7 —
é de lá que cada despacho tira o próximo passo.

## 7. Emenda de 06/09/2026 — a célula passa a expor UMA porta de máquina

**O que mudou.** Até aqui esta lei descrevia uma célula que só consome API dos
outros, e a linha dela no manifesto de contratos dizia, com todas as letras,
que a `admin` "não expõe API de máquina". **Isso deixou de ser verdade.** A
célula passa a servir uma operação em `/interno/`, de LEITURA:
`POST /interno/administradores/consultar` responde `e_administrador: sim ou
não` para um e-mail.

**Quando, e por pedido de quem.** Sessão de arquitetura com o mantenedor em
06/09/2026. Ele pediu que todo administrador possa conferir o portfólio do
aluno, para agilizar, em vez de uma lista de conferentes colada à mão no
servidor. Recebeu na mesma sessão a objeção da fresta (administrador desta casa
enxerga a economia e os capítulos do livro não lançado dele), com as duas
saídas na mesa, e escolheu "simplesmente todo admin confere", sem lista
separada.

**Por que isso obriga uma porta.** A permissão de conferir passa a ser
calculada de quem é administrador, e quem sabe isso é esta célula. Sem a porta,
a `pages` continuaria lendo um `IDS_DA_EQUIPE` escrito à mão no env da VPS:
uma segunda casa do mesmo fato, que ninguém atualiza no dia em que o mantenedor
promove alguém pela tela de `/admin/escola/`, e cuja divergência é invisível.

**Os limites que nascem junto, e não se afrouxam sem sessão nova:**

1. **Só leitura.** Nenhuma operação promove, remove ou lista administrador.
   Quem faz isso é o mantenedor, na tela desta casa, com sessão. O motivo é
   mecânico: o conjunto de tokens desta célula é plano (`TOKENS_ACEITOS`),
   então todo par que ganhasse o token para ler ganharia de brinde o poder de
   escrever (`armadilhas/318`). Escrita aqui é Rito de Contrato novo E um
   segundo grau de token, como a `identidade` já faz.
2. **A resposta é sim ou não, e nada mais.** Nome, papel, id de plataforma,
   data de promoção e a lista inteira não saem. Cada campo a mais é um campo a
   mais vazando por um par de tokens.
3. **A resposta sai da MESMA função que a porta de gente usa**
   (`apps/core/porta.py`), que soma `ADMIN_EMAILS` com os ativos da tabela. Um
   segundo jeito de responder "esta pessoa é administradora?" seria uma segunda
   resposta livre para discordar da primeira.
4. **Quem fecha a porta é o Bearer do par, e só ele.** A célula roda sob
   `SCRIPT_NAME=/admin`, e o corte do prefixo é do Django, não do Traefik:
   `meshcraft.top/admin/interno/...` é alcançável pela internet
   (`armadilhas/186`). Conjunto de tokens vazio recusa todo mundo, e o guarda é
   o teste de 401 em todas as operações.
5. **Reconhecer continua não sendo autorizar.** Esta porta diz um grau; quem
   decide o que fazer com o sim é a célula dona do recurso, fail-closed
   (`DECISAO-onde-mora-a-sessao.md` §4).

Contrato congelado: `contracts/admin.openapi.yaml`, pelo Rito de Contrato
(RITOS.md §3), em PR próprio.
