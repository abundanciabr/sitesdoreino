# DECISÃO — quem aprova o ChangeSpec, e quem fica sabendo que a ideia andou

> **Tomada pelo mantenedor em 25/08/2026**, em sessão, com as opções e os custos
> na mesa. Este documento é **lei** para os despachos do Lote 4 em diante.
> Complementa `FORMATO-CHANGESPEC.md` §1 e §5 e a `ESPECIFICACAO-CELULA.md` §10.
>
> Ele existe por um motivo medido: decisão de produto que fica só na conversa
> evapora, e decisão sem guarda é "consertada" pelo próximo agente de boa-fé
> (RUNBOOK-LOTES §9, lição 32 — que nasceu exatamente nesta célula).

---

## 1. Quem pode autorizar uma ideia a entrar em desenvolvimento

**Só o mantenedor. Sempre.** Foi a opção mais travada das três apresentadas, e
ele a escolheu **sabendo do custo** — mudar a lista depois exige um passo dele
no servidor.

### A mecânica

A célula `sugestoes` lê a variável de ambiente **`SUGESTOES_APROVADORES`** —
e-mails separados por vírgula —, **no ponto de uso**, com default vazio.
Comparação normalizada (minúsculas, sem espaços nas pontas), como o resto da
célula já faz com o crachá de equipe.

### Fail-closed, e isto é o ponto, não um efeito colateral

**Lista vazia ou ausente ⇒ NINGUÉM aprova ⇒ nenhuma sugestão sai de
`PLANEJADO` para `EM_DESENVOLVIMENTO`.**

Este é o comportamento **certo**, e precisa estar escrito aqui para que nenhuma
sessão futura o trate como defeito e o "conserte": *"não sei quem pode aprovar"*
jamais pode virar *"então pode qualquer um"*. Enquanto o mantenedor não registrar
o e-mail dele na VPS, a trava barra tudo — e a plataforma segue 100% saudável,
porque nada mais depende dessa transição.

### Ser da equipe não basta

`SUGESTOES_STAFF_EMAILS` e `SUGESTOES_APROVADORES` são **papéis diferentes** e
não se confundem:

| Papel | Quem tem | O que faz |
|---|---|---|
| **Equipe** (`SUGESTOES_STAFF_EMAILS`) | quem o mantenedor puser | modera, muda status, escreve avaliação interna |
| **Aprovador** (`SUGESTOES_APROVADORES`) | hoje, só o mantenedor | autoriza uma ideia a **entrar em desenvolvimento** |

Um membro da equipe que não esteja em `SUGESTOES_APROVADORES` **recebe recusa**
ao tentar registrar um ChangeSpec. Há teste-guarda para isso; afrouxá-lo é
desfazer esta decisão.

### Por que a Caixa não confere o documento

A célula **não lê o repositório em runtime** (decisão do plano mestre). Ela
guarda um **registro mínimo** — id do ChangeSpec, quem aprovou, quando, e o link
para o documento em `docs/changespecs/`. A garantia não é "o documento existe e
está aprovado"; é **"uma pessoa autorizada afirmou isso, e ficou registrado quem
foi e quando"**. A diferença está escrita aqui de propósito, para ninguém supor
uma verificação que não existe.

---

## 2. Quem é avisado quando a ideia muda de status

**Todos os que interagiram com a ideia** — no mínimo quem a criou, quem votou e
quem comentou —, em **qualquer** mudança de status. Não só o autor.

Isto **substitui** o recorte do EVO-21, que avisava apenas o autor. O código
daquele despacho já previa a extensão, e a previsão estava certa: *"avisar quem
VOTOU fica para depois; cabe sem mudar forma nenhuma, são mais linhas com outro
`destinatario`"* (`services/sugestoes/apps/core/avisos.py`).

### O que não muda, e é a parte cara de acertar

O invariante do EVO-21 continua valendo e **não pode ser afrouxado** para caber
o leque novo:

* o aviso nasce **dentro da mesma transação** da mudança de status — nunca de
  uma volta pelo Redis. Rollback leva status, histórico e avisos juntos;
* o `Aviso` continua sendo a **cópia do aluno**, sem a coluna de quem moderou —
  esse dado é auditoria da equipe e mora no `HistoricoStatus`;
* cada pessoa continua vendo **só os avisos dela**.

A igualdade que o EVO-21 protegia era *"uma linha de `HistoricoStatus` ⇒ um
`Aviso`"*. Ela passa a ser *"uma linha de `HistoricoStatus` ⇒ um `Aviso` por
interessado distinto"* — e o guarda de atomicidade tem de continuar mordendo na
forma nova, não ser relaxado para acomodá-la.

### O que o mantenedor sinalizou junto, e ainda não é lei

Ele disse, com estas palavras, que isto *"já é o começo do que vamos enviar de
notificações para o aluno e serão muitas"*, e descreveu um sininho **ao lado do
nome**, no estilo das notificações de redes sociais.

**A parte que fica dentro da Caixa está decidida e é o que o EVO-42 entrega.**
A parte que fica **fora** dela — o sininho visível em qualquer página do site,
não só nas telas da Caixa — **não é decisão pendente, é rito pendente**: exige
que o `funil` pergunte à `sugestoes` quantos avisos a pessoa tem, o que é uma
operação nova num contrato **congelado**. Contrato só muda pelo Rito de Contrato
(`RITOS.md` §3), com o mantenedor presente, e **nunca dentro de um lote**
(`RUNBOOK-LOTES.md` §7).

Registrado aqui para não se perder, e para que ninguém o improvise no meio de um
despacho: **um sistema de notificações que vai crescer merece um plano próprio,
não uma extensão improvisada da tela de avisos.**

---

## 3. O que isto exige do mantenedor

**Um passo, uma vez:** registrar o e-mail dele em `SUGESTOES_APROVADORES` no
`env/sugestoes.env` da VPS. Env **nunca** viaja por pipeline (INV-P8, Lei 5 — o
`deploy-infra.yml` declara que jamais toca `infra/env/` nem
`/opt/plataforma/env/`), então essa linha só existe se ele a puser lá.

Entregue como **script versionado com invocação de uma linha**
(`infra/provisionar-aprovadores.sh`), nunca como bloco de colar — é a lição do
H18/H19/H20: em 24/08/2026 um passo entregue como texto falhou **três vezes
seguidas** com ele, nenhuma por culpa dele, e a cura foi parar de entregar texto.

Até ele rodar, a trava barra tudo — o que é o lado seguro, e é exatamente o que
"só você, sempre" significa.

---

*Relacionados: `FORMATO-CHANGESPEC.md` (§1 autoria, §5 gatilho), `PLANO-MESTRE.md`
(Lote 4), `ESPECIFICACAO-CELULA.md` (§8 invariantes, §10, §11),
`DECISAO-EVO-01-identidade.md`, `ARMADILHAS-OPERACAO.md` §1 (H18–H20).*
