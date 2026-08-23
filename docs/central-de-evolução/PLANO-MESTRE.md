# PLANO MESTRE — Central de Evolução

> Criado em 22/08/2026, a partir de `feedback_cell_spec.md` (a célula),
> `changespec_format.md` (o corredor sugestão→código) e dos protótipos visuais
> `central_evolucao_design.html` / `central_evolucao_design_v2.html`.
>
> **Como executar:** em LOTES, regidos pelo `RUNBOOK-LOTES.md` (raiz). Cada lote
> abaixo já vem recortado pela cerca 1 PR = 1 célula e com o orçamento de 15
> arquivos contado no papel. O acompanhamento leigo fica em
> [`ANDAMENTO.md`](ANDAMENTO.md) (mesma pasta) e no painel.
>
> **O modelo de despacho** desta iniciativa é [`MODELO-DESPACHO.md`](MODELO-DESPACHO.md)
> — todo brief de agente nasce dele.

---

## 1. O que é (em linguagem de resultado)

Os alunos de qualquer produto da plataforma ganham um lugar para **sugerir
melhorias, votar nas sugestões dos outros e acompanhar cada ideia até a
entrega** — "em análise → planejado → em desenvolvimento → implementado", como
no protótipo v2. Do lado de dentro, cada sugestão aprovada vira um
**ChangeSpec**: um documento de engenharia que um agente executa sem inventar
escopo. É o ciclo completo: a voz do aluno entra por cima, código revisado sai
por baixo.

## 2. O que já existe e o que falta

| Pronto | Faltando |
|---|---|
| Especificação técnica da célula (`feedback_cell_spec.md`): modelos, eventos, invariantes, fases | A célula `feedback` em si (seria a 9ª de `services/`) |
| Formato do ChangeSpec (`changespec_format.md`) com regras de validade | O contrato `contracts/feedback.openapi.yaml` (exige Rito de Contrato) |
| Protótipo visual navegável (v2: quadro, tabs, inspector, roadmap) | **A decisão de identidade** — ver risco nº 1 abaixo |
| Infra de eventos provada (outbox + Redis Streams + consumers no ar desde 22/08) | Auditoria AS-IS exigida pela própria spec (§3 e DoD §11) |
| Esteira completa: PR → portão → merge pelo agente → deploy → VPS | Banco `feedback_db` + env real na VPS (passo do mantenedor) |

## 3. Riscos e divergências spec ↔ realidade (encarar ANTES de codar)

1. **Identidade — o maior.** A spec pressupõe um `AuthenticatedActor` emitido
   por uma "célula de auth". **Essa célula não existe**: as 8 células são
   alunos, catalogo, checkout, funil, leads, mensageria, pagamentos e quiz.
   Quem sabe quem é o aluno hoje é a célula `alunos` (matrículas). O Lote 0
   mede o AS-IS e a sessão de arquitetura (EVO-01) decide o contrato mínimo de
   identidade do MVP — sem essa decisão, nenhuma linha de código da célula.
2. **`tenant_id` vs CONV-SITE.** A spec fala em `tenant_id` UUID; a plataforma
   resolve site pelo Host (middleware CONV-SITE + catálogo). A auditoria diz se
   tenant = site e como o quadro se ancora nisso.
3. **Gamificação e analytics não existem.** Os eventos da seção 7 da spec são
   emitidos mesmo assim (fatos não expiram); os consumidores nascem depois.
   No MVP só a `mensageria` consome (notificação in-app).
4. **A receita R4 tem bug conhecido nas duas metades** (ARMADILHAS §4.8 e
   §4.12) — 3 das 4 células consumidoras nasceram com ele. O brief do consumer
   novo (EVO-21) já leva a forma correta injetada.
5. **Contrato é CODEOWNERS + Rito** (RITOS §3): nasce numa sessão de
   arquitetura com o mantenedor presente, nunca dentro de um lote.

## 4. Fora do escopo — de todo o plano

- **Pagamentos, checkout, Mercado Pago: NADA.** Diretiva vigente do mantenedor
  (22/08/2026) — a Central não toca e não depende de nenhuma célula de dinheiro.
- Cálculo de XP/gamificação, e-mail/push/WhatsApp (só o evento; consumidores futuros).
- Merge administrativo de sugestões, "seguir sugestão" (V1.1), "em alta" com
  recência e "meu impacto" (V1.2), busca semântica/clustering (depois do volume).
- Refatoração oportunista de qualquer célula existente (anti-meta do PLANO-10X).

---

## 5. Os lotes

Visão geral — cada linha é um lote completo (disparo → vigília → janela de
merge → deploy conferido → painel + ANDAMENTO):

| Lote | Nome | Conteúdo | Paralelismo |
|---|---|---|---|
| 0 | Alicerce | Auditoria AS-IS + sessão de arquitetura (identidade + contrato) | 1 agente + 1 sessão com você |
| 1 | A célula nasce | Scaffold, modelos, API do aluno, API staff | Fila interna (mesma célula, 4 PRs seriais) |
| 2 | Eventos e produção | Outbox/eventos · consumer na mensageria · infra/deploy | **3 despachos em paralelo real** |
| 3 | O rosto | UI do aluno seguindo o protótipo v2 | Fila interna (2 PRs) |
| 4 | O corredor | Trava ChangeSpec no pipeline de status + fechamento do DoD | 1–2 despachos |

Regra de ordem entre lotes: **um lote só abre quando o anterior fechou** (merge
+ deploy verde + ANDAMENTO atualizado). Dentro do lote, vale o RUNBOOK §5:
canário → comuns → CODEOWNERS por último.

### LOTE 0 — Alicerce (não escreve código de produção)

**EVO-00 — Auditoria AS-IS** · agente, somente-leitura · célula: nenhuma
Responde, com evidência (comando + saída), as perguntas que a spec §3 exige:

1. As 8 células realmente operam com banco próprio isolado?
2. Como um aluno se autentica hoje? O que existe de mais próximo de
   `AuthenticatedActor`? (célula `alunos`, sessões do checkout, o que for real)
3. `tenant_id` da spec ≙ site do CONV-SITE? Como um quadro se ancora num produto?
4. O que uma célula nova precisa tocar para existir de ponta a ponta: manifesto
   de contratos, `ci-celula.yml`, `deploy-celula.yml`, compose, traefik,
   `constituicoes/`, CODEOWNERS — lista exata de arquivos e quais são protegidos.
5. Convenções reais dos eventos (nomes de stream, envelope, versão) medidas no
   código produtor de `pagamentos` e nos 4 consumers.

Entrega: `docs/central-de-evolução/AUDITORIA-AS-IS.md` + a lista de
divergências spec↔realidade. **Este documento é pré-requisito do DoD do MVP**
(spec §11, último item).

**EVO-01 — Sessão de arquitetura (VOCÊ presente — Rito de Contrato, RITOS §3)**
Com a auditoria na mesa, decidir e congelar:
- o contrato mínimo de identidade do MVP (de onde vem `actor_id`, o que é staff);
- `contracts/feedback.openapi.yaml` v1 (superfície mínima: sugestões, votos,
  comentários, status, avaliação staff);
- a URL pública (proposta: `SCRIPT_NAME=/evolucao`, roteada pelo Traefik como
  as demais);
- tenant/produto: como o quadro referencia o site e o produto (IDs opacos, sem FK).

Sai daqui: PR só de `contracts/` com a label `contrato`, mergeado com mandato.
É o único passo do plano inteiro que exige reunião — todo o resto é lote.

### LOTE 1 — A célula nasce (`services/feedback/`, fila interna: 4 PRs seriais)

> Mesma célula ⇒ nunca em paralelo (RUNBOOK §1). A maestro rege a fila e
> mergeia um a um. Canário do lote = EVO-10 (o mais inofensivo).

**EVO-10 — Scaffold** (~14 arquivos, contado):
`manage.py`, `requirements.txt` (pinado), `Makefile` (o do `celula-template`,
que decide pelo manifesto — corrige H12 por nascença), `Dockerfile`,
`docker-compose.dev.yml`, `config/{settings,urls,asgi}.py` (fail-hard),
`apps/core/api.py` (healthz + esqueleto Ninja), `export_openapi` batendo byte a
byte com o contrato congelado em EVO-01, 2–3 testes de fumaça. Middleware
CONV-SITE **já com `request.path_info`** (armadilha §4.10 morta por nascença).
Se a auditoria (EVO-00 pergunta 4) mostrar que `.github/` precisa de 1 linha
para a célula entrar no CI, isso é um PR-irmão minúsculo com mandato, anunciado
nominalmente.

**EVO-11 — Modelos e invariantes** (~9 arquivos):
os 6 modelos da spec §6 + `migrations/0001` + `migrations/__init__.py`
(armadilha §4.3 — conta no orçamento), guarda de append-only do
`HistoricoStatus` **nos dois caminhos** (`save()` e `QuerySet.update()` —
armadilha §4.4), testes-guarda de TODOS os invariantes da spec §8 que já são
testáveis sem API.

**EVO-12 — API do aluno** (~8 arquivos):
criar sugestão (com busca simples de duplicata antes de publicar), votar/
desvotar (corrida protegida por `unique_together` + `IntegrityError` com
savepoint — §4.8), comentar, listar com ranking por votos, rate limit 3
sugestões/7 dias, validação de entitlement pelo contrato de identidade (nunca
consulta a outro banco). Aliases nos schemas Ninja (§4.1 — `Sugestao` model vs
schema é exatamente o cenário do sombreamento).

**EVO-13 — API staff + pipeline de status** (~7 arquivos):
mudança de status com `HistoricoStatus`, "não planejado" exige justificativa,
`AvaliacaoProduto` (403 para qualquer ator sem role staff — teste obrigatório,
DoD spec §11), endpoint staff nunca exposto ao aluno.

### LOTE 2 — Eventos e produção (paralelismo real: 3 células/áreas distintas)

**EVO-20 — Produtor de eventos** · célula `feedback`:
tabela outbox gravada NA MESMA transação do estado, relay Huey → Redis Streams,
os 5 eventos da spec §7. Padrão copiado do produtor de `pagamentos` (o lado que
está íntegro — §4.12, nota final). Evento de status publicado antes do commit
externo confirmar (DoD spec §11).

**EVO-21 — Notificação in-app** · célula `mensageria` (paralelo):
consumer de `feedback.suggestion.status_changed` → notificação simples para os
autores que votaram. Brief leva injetadas as duas metades da armadilha R4
(§4.8 + §4.12: dois `atomic` aninhados, handler fora do `try`) e a variante do
`xack` que é justamente da mensageria.

**EVO-22 — Infra** · `infra/**` (paralelo, CODEOWNERS — mandato + anúncio nominal):
serviço `feedback` no compose (healthcheck, bloco `x-celula`), rota Traefik,
`infra/env/feedback.exemplo`, lista de provisionamento atualizada. O merge
dispara o `deploy-infra` — canal provado (H11 ✅); veredito do run conferido por
`gh run view --json` antes de fechar a janela.

**Precisa de você (único passo manual do plano, além do EVO-01):** criar
`feedback_db` + role isolada na VPS e escrever o `feedback.env` real — chega
como UM bloco de colar fail-closed, com a janela rotulada (`root@srv...` = já
dentro da VPS).

Janela de merge do lote: EVO-20 (canário) → EVO-21 → EVO-22 (infra por último,
com o deploy conferido antes de qualquer celebração).

### LOTE 3 — O rosto (célula `feedback`, fila interna: 2 PRs)

**EVO-30 — Quadro e sugestão:** templates + static próprios da célula (não
existe base.html compartilhado), seguindo `central_evolucao_design_v2.html`:
quadro com tabs (Mais votadas / Novas — "Em alta" fica p/ V1.2), card com voto,
inspector/detalhe com comentários e histórico, formulário "Nova ideia" com a
busca de duplicata na frente.

**EVO-31 — Roadmap e notificação:** a faixa de roadmap por status (as 4 zonas
do protótipo) e a exibição da notificação in-app vinda da mensageria.

### LOTE 4 — O corredor ChangeSpec

**EVO-40 — A trava** · célula `feedback`:
`Sugestao.status` só sai de `PLANEJADO` para `EM_DESENVOLVIMENTO` se existir
registro de ChangeSpec aprovado referenciando o `suggestion_id`
(`changespec_format.md` §5) — validação no `save()`, com teste-guarda. Registro
mínimo na própria célula (id do CS, `aprovado_por`, data, link), preenchido por
endpoint staff — a célula não lê o repositório em runtime.

**EVO-41 — Fechamento do MVP:**
`docs/changespecs/` criado com `changespec_format.md` como lei local + um
`CS-TEMPLATE.md` pronto para copiar; conferência item a item do Definition of
Done da spec §11, com evidência colada; ANDAMENTO e painel fechados; lições
para `ARMADILHAS.md` / `services/feedback/LICOES.md`.

Regra de autoria que atravessa tudo (changespec_format §1): **quem escreve o
ChangeSpec nunca é o agente que o implementa**, e `APROVADO_POR` é sempre você.

---

## 5.1 Ajustes pós-auditoria (23/08/2026 — EVO-00 executado, ver [`AUDITORIA-AS-IS.md`](AUDITORIA-AS-IS.md))

A auditoria confirmou o desenho geral e impôs 4 correções ao texto acima:

1. **O contrato NÃO nasce no EVO-01.** O manifesto de contratos reprova
   contrato sem célula (e célula declarada sem disco). A célula nasce
   `freeze: not-applicable` no EVO-10 (padrão provado por funil/mensageria/
   quiz) e o contrato congela pelo Rito §3 na fronteira EVO-11→EVO-12. O
   EVO-01 vira sessão só de DECISÃO: identidade (não existe login de usuário
   final na plataforma — o maior achado), IDs (strings opacas, não UUID),
   nomes de evento em PT (`feedback.sugestao.criada` etc.) e URL pública.
2. **EVO-10 toca `ci/manifesto-de-contratos.json`** (obrigatório no MESMO PR
   do scaffold) — `ci/` é CODEOWNERS: mandato + anúncio nominal.
3. **Vermelho esperado no Lote 1:** cada merge em `services/feedback/` dispara
   `deploy-celula`, que falha no passo da VPS até o compose ganhar o serviço
   (Lote 2). Vermelho de causa conhecida e registrada — não pausa a janela;
   o Lote 2 o cura (as imagens já publicadas no ghcr são puxadas então).
4. **Modelos ajustados:** `tenant_id`/`produto_id`/`autor_id` como strings
   opacas (`CharField`), seguindo os contratos vivos de catálogo e alunos.

## 6. Backlog pós-MVP (não entra em lote nenhum agora)

V1.1: merge administrativo transacional · seguir sugestão · gamificação por
eventos (exige célula nova — decisão de arquitetura própria).
V1.2: "em alta" com peso de recência · "meu impacto" no perfil.
Depois, só com volume real: similaridade trigram, busca semântica, clustering.

## 7. Como pedir cada lote (cole numa janela raiz nova — `PS C:\>` = seu PC)

```
Leia RUNBOOK-LOTES.md e docs/central-de-evolução/PLANO-MESTRE.md e toque o LOTE <N> da Central de Evolução, atualizando ANDAMENTO.md e o painel no fechamento.
```

A sessão monta os briefs a partir do [`MODELO-DESPACHO.md`](MODELO-DESPACHO.md),
dispara, vigia, **mergeia** e reporta o placar. Só volta para você o que está
marcado como "precisa de você" (EVO-01 e o banco da VPS no Lote 2).
