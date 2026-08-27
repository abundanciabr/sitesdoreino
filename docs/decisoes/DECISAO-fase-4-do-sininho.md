# DECISÃO — as quatro escolhas do Rito de Contrato do sininho (Fase 4)

> **Tomada pelo mantenedor em 27/08/2026**, na sessão de arquitetura conduzida em
> conversa — perguntas estruturadas, com recomendação marcada em cada uma (o
> formato que ele confirmou em 25/08). É o **Rito de Contrato** do `RITOS.md` §3
> cumprido: PR só de `contracts/` com a label `contrato`
> ([#274](https://github.com/abundanciabr/sitesdoreino/pull/274)), e a decisão
> registrada — este documento.
>
> **Status:** *isto é lei.* Fecha a **Fase 4** do `docs/notificacoes/PLANO-MESTRE.md`
> e responde, na mesma sessão, à primeira pergunta em aberto da **Fase 7**
> (preferências e o e-mail). Onde este documento e o `PLANO-MESTRE.md`
> divergirem, vence este, por ser posterior.
>
> **O que este documento NÃO é:** autorização para construir a célula. A
> implementação em `notificacoes` é lote separado (`RUNBOOK-LOTES.md`), como
> sempre — provedor primeiro, consumidores em PRs seguintes.

---

## 1. Escolha 1 — o sino mostra o número exato, estilo Facebook

**A pergunta:** *"O número de avisos não lidos aparece exato, ou só um sinal
dizendo 'tem coisa nova'?"*

**A resposta: número exato**, até um teto de EXIBIÇÃO (a tela mostra "99+"
quando passar de 99 — o dado guardado continua exato, só a exibição
arredonda). Foi a própria referência do pedido original, nas palavras dele:
*"algo como as notificações do Facebook"*.

**Consequência de desenho:** a API (`GET /resumo`) devolve a contagem real,
sem teto — o teto de exibição é decisão da TELA (`funil`), nunca do dado.
Contador O(1), como a `DECISAO-notificacoes` §5.2 já exigia.

---

## 2. Escolha 2 — se a caixa cair, a tela de avisos avisa; o sino, não

**A pergunta:** *"Se a caixa central de avisos ficar fora do ar, a TELA de
avisos da Caixa deve avisar que algo deu errado, ou aparecer vazia?"*

**A resposta: avisa.** Uma frase em português, sem jargão — algo como "não
consegui buscar seus avisos agora, tente de novo em instantes".

**Isto NÃO contradiz a Fase 5.** A regra de lá continua valendo, sem exceção,
para o SINO em toda página: *"falha ABERTA — notificações fora do ar ⇒ o site
mostra o nome sem sino e a página abre normal."* São duas telas com papéis
diferentes. O sino é decoração em toda página — se a caixa cair, nenhuma
página do site pode ficar esperando por ele. A tela de avisos É a função
daquela página — esconder a falha em silêncio faria a pessoa achar que não
tem avisos quando, na verdade, a caixa é que está fora do ar.

**Consequência de desenho:** a página de avisos da `sugestoes` chama
`GET /avisos` com timeout curto; erro de rede ou 5xx renderiza a mensagem de
falha, nunca uma lista vazia. Zero avisos de verdade e falha em consultar são
estados DIFERENTES na tela — nunca o mesmo visual, para não se confundirem.

---

## 3. Escolha 3 — "marcar tudo como lido" entra agora; "silenciar assunto" espera

**A pergunta:** *"Quais preferências de aviso entram já, junto com o resto do
plano?"*

**A resposta:** **"marcar tudo como lido" entra** — é barato e imediatamente
útil assim que a lista de avisos existir. **"Silenciar um assunto" fica para
quando houver mais de um assunto** de aviso: hoje só a Caixa produz avisos
(`DECISAO-notificacoes` §3 — a V1 nasce só com ela), e um botão para silenciar
o único assunto que existe não muda nada na prática. Fica registrado no mapa
do projeto, não descartado — é sequência, não corte.

**Consequência de desenho:** `POST /marcar-lidas` entra no contrato desta
Fase 4. Preferência por assunto não ganha contrato ainda — nasce quando um
segundo assunto (matrícula, quiz…) tornar a escolha real.

---

## 4. Escolha 4 — o e-mail continua fora, por agora

**A pergunta:** *"Avançar com o envio de avisos por e-mail agora, ou manter só
dentro do site?"*

**A resposta: manter só dentro do site.** O e-mail é o item mais caro da
Fase 7: reabre a regra de que o e-mail do aluno mora numa linha só e não
circula (`DECISAO-EVO-01` §3), e exige construir o envio de verdade — a
`mensageria` hoje só registra um rascunho no log
(`services/mensageria/apps/eventos/tasks.py`: *"Stub: loga o envio"*), não
manda nada de verdade.

**Isto não é corte de escopo — é sequência.** O sino e a tela de avisos da
Caixa funcionam completos, hoje, sem e-mail nenhum. A porta continua fechada
até um pedido novo e explícito dele; nenhuma sessão futura deve reabri-la por
conta própria.

---

## 5. O que o rito produziu, e o que ficou para depois

**Entrou** (PR [#274](https://github.com/abundanciabr/sitesdoreino/pull/274),
só `contracts/`, label `contrato`):

| Arquivo | O que é |
|---|---|
| `contracts/notificacoes.openapi.yaml` | a porta de consulta: `GET /resumo` (contagem), `GET /avisos` (lista paginada), `POST /marcar-lidas` |

**Ficou de fora, de propósito:**

- **Preferência por assunto** (silenciar) — sem contrato até existir um
  segundo assunto de aviso.
- **E-mail e qualquer canal fora do in-app** — `DECISAO-notificacoes` §4.2
  continua inteira; a Escolha 4 acima reafirma.
- **Quem mais pode consultar os avisos de uma pessoa** (ex.: um painel de
  suporte da equipe olhando por outra pessoa) — não foi pedido nem desenhado;
  fora do escopo desta V1.

---

*Relacionados: **`docs/notificacoes/PLANO-MESTRE.md`** (§6 — Fase 4 fechada por
este documento, Fase 7 parcialmente respondida) · **`docs/decisoes/DECISAO-notificacoes.md`**
(a lei da Fase 0) · **`docs/decisoes/DECISAO-fase-2-do-sininho.md`** (a Fase 2 —
o `ator_id` e a carta endereçada) · `RITOS.md` §3 (o rito cumprido) ·
`contracts/README.md` (a Muralha nº 4).*
