# DECISÃO — o fórum da escola nasce como célula própria, construído na casa

> **Autorizado pelo mantenedor em 28/08/2026**, reabrindo nominalmente o
> congelamento arquitetural — a quinta vez (depois de `sugestoes`, `identidade`,
> `notificacoes` e `admin`).
>
> **A análise que levou aqui não se repete neste documento.** Ela mora em
> `docs/consultorias/forum-da-escola/VEREDITO.md`, com os dois pareceres
> externos arquivados ao lado. Aqui ficam só as **normas** — o que vale, o que
> é proibido, e o que ainda está em aberto.

## 1. A decisão

Nasce a célula **`services/forum`**, Django + django-ninja como todas as outras,
com **banco próprio** (`forum_db`), **processo próprio** e **contrato próprio**.

**Nenhum motor de fórum de prateleira entra** — nem Discourse, nem Misago, nem
`django-machina`, nem NodeBB, nem Flarum. O fórum é construído na casa,
reaproveitando o que já existe (o reconhecimento de sessão, as categorias de
pessoa, o sininho, o molde de discussão da Caixa de Sugestões).

## 2. O endereço é lei, e o motivo é o login

**O fórum serve em `meshcraft.top/forum` — caminho, NUNCA subdomínio.**

Isto não é preferência estética. O cookie `meshcraft_sessao` é de **host**
(`SESSION_COOKIE_PATH = "/"`, e deliberadamente **não** `SESSION_COOKIE_DOMAIN` —
ver `services/identidade/config/settings.py`). Em `forum.meshcraft.top` o crachá
não viaja, e o mantenedor teria exatamente o que pediu para não ter: **um segundo
login**.

O requisito, nas palavras dele em 28/08/2026:

> *"Eu quero que o usuário já esteja logado uma única vez e possa acessar o site
> todo em qualquer parte sem necessidade de qualquer tipo de login."*

Uma célula da casa herda isso de graça. **Foi este requisito — e não a análise
técnica — que eliminou os motores de fora.**

## 3. Esta célula NÃO assina sessão

Herdado de `DECISAO-celula-de-identidade.md` §6.4 e do **[INV-P12]**: não há
`SessionMiddleware`, não há `django.contrib.sessions` em `INSTALLED_APPS`, não há
`SESSION_ENGINE`. O fórum **repassa** o cookie recebido para a `identidade` e
pergunta quem é — nunca o lê, nunca o escreve.

Guarda: `services/forum/tests/test_inv_forum_nao_assina_sessao.py`, plantado na
gênese.

E a regra que vem junto: **reconhecer não é autorizar.** O `papel` que a
`identidade` devolve é de exibição. Quem decide o que alguém pode fazer no fórum
é **o fórum**, fail-closed, conferindo as listas dele — do mesmo jeito que a
Caixa faz.

## 4. As sete condições que a construção carrega

Vieram do veredito e são parte do escopo, não enfeite:

1. **Endereço por caminho** (§2 acima).
2. **Modelo de dados no formato normal de fórum** — área → tópico → mensagem.
   É o seguro que mantém aberta a porta de migrar para o Discourse se a escola
   crescer muito: migração é caminho batido, com ferramenta de importação
   pronta. **Só vira porta de mão única se inventarmos um formato esquisito.**
3. **A marca de leitura por marca-d'água** — uma marca por pessoa por área ("li
   até aqui") mais uma pequena tabela de exceções, que é como o Discourse faz.
   **Nunca uma linha por pessoa por mensagem lida**: com 200 alunos e 20 mil
   mensagens isso fabrica milhões de linhas para responder uma pergunta boba.
4. **Busca do PostgreSQL em português desde o primeiro dia**, em **coluna
   indexada** — nunca calculada na hora da consulta. É o único item caro de
   instalar depois: vira migração na maior tabela do sistema.
5. **Anexos com lista branca** de tipos e limite de tamanho, servidos sem deixar
   ninguém subir coisa executável. O "mostre seu trabalho" é a parte mais
   exposta da escola.
6. **Moderação em volume**: fila de aprovação, mover, juntar duplicatas, dividir
   conversa, trancar, fixar, apagar sem perder histórico.
7. **Critérios de morte** — se a construção começar a recriar do zero um **motor
   de busca**, um **editor sofisticado**, **resposta por e-mail** ou um
   **framework de reputação**, **pare e reabra a decisão**. A partir dali
   estaríamos reinventando o Discourse, e mal.

## 5. O produto, como o mantenedor decidiu

- **Áreas mistas**: seções públicas (visitante lê, Google indexa) e seções
  trancadas por curso/turma.
- **O papel de professor nasce com o fórum**, com autoridade real: resposta com
  selo, poder de marcar dúvida como resolvida, moderar sem ser dono do sistema.
  **Ele não existia antes desta decisão** — `DECISAO-categorias-de-usuario.md`
  tem cinco categorias e professor não é uma delas. Como o papel se materializa
  (lista própria do fórum? célula `alunos`?) é decisão do PR que o criar, e
  **não pode** ser resolvida pondo papel dentro do cookie ou da resposta da
  `identidade` (§3).
- **O fórum nasce em salão vazio** — não existe comunidade hoje, nem Discord,
  nem grupo de mensagens. Isso é problema de desenho, não detalhe.

## 6. O que está EM ABERTO, e não se resolve por conta própria

Registrado com honestidade porque a rodada de consultoria **não** respondeu:

1. **O salão vazio** — como o fórum não nasce deserto nos primeiros 90 dias.
   Os dois consultores ignoraram a pergunta.
2. **Menores de idade, moderação e lei brasileira.** Idem.
3. **Quem escreve nas áreas públicas** — só aluno, ou também quem tem cadastro
   sem ter comprado? Muda o desenho de anti-spam.

**Os itens 1 e 2 pedem rodada própria de consultoria, e precisam estar
respondidos ANTES de o fórum abrir ao público** — não antes de começar a
construir. O item 3 é pergunta ao mantenedor no PR que criar as permissões.

## 7. A escada de PRs

Como nas quatro gêneses anteriores:

| PR | O quê | Por que nesta posição |
|---|---|---|
| **1** | **Gênese** — esqueleto, `/healthz` nas duas formas, settings fail-hard, os dois guardas, a linha em `rollback.yml`, o manifesto de contratos, a constituição da célula e esta lei | Célula nasce **com** botão de desfazer (`armadilhas/076`). O `deploy-celula` fica vermelho até o PR 3 — **isso é esperado** (`armadilhas/088`) |
| **2** | **Modelo de dados** — área, tópico, mensagem, marca de leitura, estados de moderação | O veredito manda: fundação antes de tela. É a peça que decide a reversibilidade |
| **3** | **Contrato** (`contracts/forum.openapi.yaml`), PR só de `contracts/`, label `contrato` | RITOS §3 |
| — | **Passo do mantenedor na VPS**: `infra/provisionar-forum.sh` (banco, papel, `env/forum.env`) | ANTES do PR 4, senão o deploy reprova em crashloop (lição H18) |
| **4** | **`infra/`** — compose + traefik + env exemplo. **PR PRÓPRIO, SOZINHO** | `armadilhas/134`: compose junto com código trava os dois deploys |
| **5+** | Telas, e o `funil` linkando o fórum | Depois de a fundação estar de pé |

**Ao acrescentar `/forum` ao roteamento (PR 4), o inventário de primeiros
segmentos de `ci/tests/test_rotas_sem_forma_de_locale.py` precisa ser atualizado
no MESMO PR** (`armadilhas/089`) — hoje ele conhece `{quiz, checkout, alunos,
api, forms, entrar, admin}`.

## 8. Uma dívida que esta decisão herda e não cria

O consultor 1 apontou, e é justo: *"um passo seu no servidor" já apareceu quatro
vezes*. Criar o banco de uma célula nova deveria ser coisa que a esteira faz
sozinha. **Isto não bloqueia o fórum** — o passo manual continua valendo aqui —
mas fica registrado como dívida do projeto, não como exceção pontual.
