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
   única rota que responde sem crachá é `/healthz`.

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
