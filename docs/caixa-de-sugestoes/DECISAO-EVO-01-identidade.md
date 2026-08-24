# DECISÃO EVO-01 — como o aluno entra na Caixa de Sugestões

> **Sessão de arquitetura com o mantenedor presente**, 23/08/2026 (noite), janela raiz.
> É a única reunião que o `PLANO-MESTRE.md` exige, e ela destrava os Lotes 1 a 4.
> Insumo: `AUDITORIA-AS-IS.md` (EVO-00) — em especial a Q2, que mediu o maior achado
> do projeto: **não existe login de usuário final em nenhuma célula da plataforma**
> (zero ocorrências de `LoginView`/`login_required` em `services/*/`).
>
> Este documento é a **lei** do assunto. Agente nenhum re-decide identidade sem uma
> sessão nova como esta.

---

## 1. As três decisões do mantenedor

| # | Pergunta | Decisão |
|---|---|---|
| 1 | Quem usa a Caixa? | **Adultos.** O e-mail da matrícula é do próprio aluno |
| 2 | Quem pode entrar e votar? | **Só quem tem matrícula.** Curioso que apenas se cadastrou no site fica de fora |
| 3 | Como o aluno prova quem é? | **Entrar com Google** |

**A decisão 1 apagou um risco antes de ele existir:** se os alunos fossem crianças, o
e-mail da matrícula seria o do responsável, e qualquer login por e-mail obrigaria a
criança a pedir a caixa de entrada do pai toda vez que quisesse votar. Com adultos, o
e-mail do Google e o e-mail da compra tendem a ser a mesma pessoa.

---

## 2. O desenho que decorre disso

**A regra que organiza tudo: o Google prova QUEM É; a célula `alunos` decide SE PODE.**
São duas perguntas diferentes, e elas moram em lugares diferentes. O Google nunca
autoriza nada — ele só devolve um e-mail verificado. Quem diz "esta pessoa é aluna" é a
matrícula, que é a fonte de verdade da casa.

O passo a passo, do clique até estar dentro:

1. A pessoa abre `meshcraft.top/forms/sugestoes/` e clica em **Entrar com Google**.
2. O Google autentica e devolve um e-mail **verificado** (`email_verified`) — a célula
   `sugestoes` **recusa** e-mail não verificado, sem exceção.
3. `sugestoes` pergunta à célula `alunos`, **pelo contrato que já existe e já está
   implementado de verdade**: `GET /alunos/{email}/matriculas` (`listEnrollments`,
   `services/alunos/apps/core/api.py:137` — não é stub).
4. **Tem matrícula** ⇒ a `sugestoes` cunha (ou recupera) a identidade interna dessa
   pessoa e abre a sessão. **Não tem** ⇒ tela explicativa (§5), sem criar nada.

**Lei 3 respeitada:** `sugestoes` NUNCA lê o banco de `alunos`. Pergunta por HTTP, pelo
contrato, como `leads` e `checkout` já fazem (padrão R2, cliente com timeout explícito).

---

## 3. O que a célula guarda (e o que ela deliberadamente NÃO guarda)

```
Identidade
  id            texto opaco, cunhado pela sugestoes na primeira entrada  <- é o "autor"
  email         o e-mail verificado do Google (uma linha, um lugar)
  provedor      "google"
  nome_exibido  default = primeiro nome vindo do Google
  criada_em
```

Sugestões, votos e comentários apontam para `Identidade.id` — **nunca para o e-mail**.

Por quê: o e-mail é dado pessoal e passa a viver em UMA linha, em vez de espalhado por
cada voto de cada pessoa. Se alguém trocar de e-mail um dia, muda-se uma linha e o
histórico inteiro continua de pé. É também o que permite, mais tarde, aceitar outra
forma de entrar (um código, por exemplo) sem redesenhar nada: entra um `provedor` novo,
e pronto.

**IDs são texto opaco, não UUID** — é o que a plataforma inteira já faz (`Site.id`,
`product_id`, `site_id` são todos `type: string` sem `format: uuid`). Isto corrige a
assunção provisória da `ESPECIFICACAO-CELULA.md` §4.

---

## 4. Quem é "equipe" (staff)

Staff também não existia como papel em lugar nenhum da plataforma. Decisão, escolhendo
o mecanismo mais barato que já é usado na casa:

- **Lista de e-mails no `.env` da célula** (`SUGESTOES_STAFF_EMAILS`), separada por
  vírgula, lida **no ponto de uso** — nunca fail-hard no import (o container web não
  pode morrer no boot por causa de uma variável; é a convenção do lote de Huey).
- Entra pelo mesmo botão do Google. E-mail na lista ⇒ papel `staff`.
- **Staff não precisa de matrícula** — a checagem de staff acontece ANTES da de
  matrícula. Você precisa conseguir moderar a Caixa sem comprar o próprio curso.

Trocar quem é staff = editar uma variável no servidor e reiniciar a célula. Sem
migração, sem deploy de código.

---

## 5. A fricção conhecida desta escolha (e o que fazer com ela)

**Cenário real:** a pessoa comprou o curso com `joao@empresa.com` e a conta Google dela
é `joao.silva@gmail.com`. O Google prova a identidade, mas a matrícula não aparece — e
ela fica de fora sem entender por quê.

Isto **não é motivo para reverter a decisão**: é o preço de qualquer login amarrado a
identidade externa, e o mantenedor foi avisado disso antes de escolher. O que se faz:

- **A tela de recusa diz exatamente o que aconteceu**, com o e-mail que o Google mandou
  visível: *"Entramos com `joao.silva@gmail.com`, mas não encontramos matrícula para
  esse endereço. Se você comprou com outro e-mail, entre com ele — ou fale com a
  gente."* Nunca um "acesso negado" seco.
- **Saída manual pela staff** quando acontecer: não é MVP, mas o modelo de dados acima
  já comporta (uma segunda linha de `Identidade` apontando para a mesma pessoa, ou o
  ajuste do e-mail da matrícula na célula `alunos`, que é a fonte de verdade).

**Não vamos construir a saída manual agora.** Enquanto não houver alunos de verdade
esbarrando nisso, ela é solução para um problema que talvez não apareça.

---

## 6. O que isto exige do mantenedor — UM passo, e não é agora

No **Lote 2** (quando a Caixa for para a VPS), e só nele:

1. Criar um aplicativo OAuth no console do Google (gera um **ID de cliente** e um
   **segredo**), com o endereço de retorno
   `https://meshcraft.top/forms/sugestoes/entrar/google/retorno`.
2. Colar os dois em `/opt/plataforma/env/sugestoes.env`, junto da lista de staff.

Vai chegar como **um bloco único de colar, fail-closed, com a janela rotulada**
(`CLAUDE.md`). Segredo nunca passa pelo agente (INV-P8, Lei 5).

Até lá, em desenvolvimento e no CI, a entrada pelo Google é **simulada** — o teste não
chama o Google de verdade. Nenhum despacho fica bloqueado esperando este passo.

---

## 7. O que foi decidido NÃO fazer, e por quê

| Descartado | Motivo |
|---|---|
| **Link mágico por e-mail** (a proposta original do plano) | A plataforma **não manda e-mail**: `services/mensageria/apps/eventos/tasks.py:12` é um stub que só escreve no log (*"Provedor SMTP real fica para depois"*), e as variáveis SMTP estão vazias. Exigiria o mantenedor contratar um serviço de envio — um passo a mais e uma conta a mais, para um resultado pior que o Google num público adulto |
| **Senha própria** | Traz junto: guardar hash, fluxo de "esqueci minha senha" (que precisa de e-mail **de novo**), bloqueio por tentativa, e a responsabilidade de um vazamento. Muito código e risco para zero ganho |
| **Sem login** | Mata o produto: o voto vira bagunça, e ninguém pode ser avisado quando a própria ideia muda de status — que é metade do motivo de a Caixa existir |
| **Célula de auth nova** | Anti-meta do congelamento arquitetural: nenhuma célula nova além da `sugestoes`. A `sugestoes` cuida da própria sessão |

---

## 8. Consequências para os documentos e para a implementação

- **`ESPECIFICACAO-CELULA.md` §4** foi reescrita neste mesmo PR: o `AuthenticatedActor`
  "emitido pela célula de auth" deixa de existir; quem emite é a própria `sugestoes`, e
  `actor_id` é texto opaco.
- **Contrato REST:** nada a fazer agora. A auditoria (Q4) provou que o manifesto
  reprova contrato sem célula, então o congelamento continua na fronteira
  **EVO-11 → EVO-12**, pelo Rito §3. Esta decisão não antecipa isso.
- **Roteamento:** hoje `PathPrefix("/")` manda tudo para o `funil`
  (`infra/traefik/dynamic/plataforma.yml`). A regra de `/forms/sugestoes` entra no
  **Lote 2**, junto do compose e do banco.
- **Armadilha para quem implementar:** a célula vai servir sob prefixo de caminho, e
  isso já mordeu o `checkout` e o `quiz` — `/healthz` some sob `SCRIPT_NAME` se a rota
  não usar `request.path_info`. Está no `armadilhas/INDICE.md`; leia a entrada antes de
  escrever a primeira rota.

---

## 9. Estado

**EVO-01 fechado em 23/08/2026.** O Lote 1 (EVO-10 a EVO-13) pode ser despachado a
qualquer momento, sem nenhuma pendência do mantenedor.
