# DECISÃO — as três escolhas do Rito de Contrato do sininho (Fase 2)

> **Tomada pelo mantenedor em 26/08/2026**, na sessão de arquitetura que ele
> convocou (*"vamos marcar a conversa do sininho agora"*). É o **Rito de Contrato**
> do `RITOS.md` §3 cumprido: sessão com ele presente, PR só de `contracts/` com a
> label `contrato` ([#243](https://github.com/abundanciabr/sitesdoreino/pull/243)),
> e a decisão registrada — este documento.
>
> **Status:** *isto é lei.* Fecha a **Fase 2** do `docs/notificacoes/PLANO-MESTRE.md`
> e **emenda** a `DECISAO-notificacoes.md` num ponto, nomeado na §1 abaixo. Onde
> divergirem, vence o que está aqui, por ser posterior e por ter sido decidido por
> ele.
>
> **O que este documento NÃO é:** autorização para construir a célula. A Fase 3
> continua sendo Fase 3, e a Fase 4 continua sendo outro Rito de Contrato.

---

## 1. Escolha 1 — uma carta por pessoa, e o leque acontece na origem

**A pergunta, nas palavras dela:** *"Uma ideia popular pode ter centenas de pessoas
para avisar. Como o aviso deve chegar a cada uma?"*

**A resposta: uma carta por pessoa.** Nasce o evento `notificacao.devida.v1` — uma
pessoa a avisar, um evento, endereçado. As opções recusadas, nominalmente:

- **Uma lista com todos os nomes num evento só: RECUSADA.** Faria a lista de quem
  votou numa ideia circular pela plataforma inteira, e o tamanho de um evento
  cresceria sem teto com a plateia.
- **A caixa central pergunta à Caixa quem avisar: RECUSADA.** Acopla duas células no
  caminho do aviso — a Caixa reiniciando viraria aviso perdido ou atrasado, e é o
  mesmo vício da Saída C já recusada na `DECISAO-notificacoes` §2.

### A emenda, e ela precisa estar escrita para não ser "consertada" depois

A §5.2 da `DECISAO-notificacoes` exige **fan-out em lote**. Essa exigência **continua
valendo e muda de endereço**: sai da célula que **recebe** e vai para a que
**publica**.

A `sugestoes` já faz exatamente isso hoje — `avisar_os_interessados()` resolve o leque
em três consultas e escreve em `bulk_create` (EVO-42), com
`tests/test_volume_dos_avisos.py` medindo com 2 e com 20 interessados e exigindo o
mesmo número de consultas. **Publicar N cartas na outbox é o mesmo gesto, no mesmo
`transaction.atomic()`.** O que muda é o que se escreve em lote, não o fato de ser em
lote.

Quem for implementar: **um `create()` por pessoa dentro de um laço reprova**, aqui pela
mesma razão de sempre. E a caixa central, do outro lado, fica **burra**: uma carta que
chega é uma linha que se escreve. Ela não faz leque nenhum — é isso que a mantém barata
quando dez células estiverem publicando.

---

## 2. Escolha 2 — quem mexeu: guardar sim, mostrar não

**A pergunta:** *"O aviso deve dizer QUEM da equipe mexeu na ideia?"*

**A resposta: guardar sim, mostrar não.** O `ator_id` — o id de plataforma de quem
causou o fato — viaja nos dois eventos e é gravado. **A tela do aluno diz "a equipe".**

O motivo é de sentido único, e é por isso que a decisão é esta e não a oposta:

> **Mostrar o nome depois é reversível. Não ter guardado, não.**

Se um aluno questionar uma recusa daqui a três meses, ou o dado está lá ou a história
não se reconstrói. E expor nominalmente quem da equipe recusou a ideia de alguém é
criar atrito exatamente no ponto onde ele já é maior.

**Consequência de desenho:** `ator_id` é **nulável na carta** e **obrigatório no fato**.
Um fato de negócio sabe quem o causou; a carta é genérica e vai servir também a fatos
de máquina — um pagamento aprovado pelo provedor não tem gente por trás.

---

## 3. Escolha 3 — os avisos que já existem mudam de casa junto

**A pergunta:** *"Os avisos que já existem hoje dentro da Caixa — o que acontece com
eles quando a caixa central nascer?"*

**A resposta: mudam de casa junto.** A migração dos `Aviso` da `sugestoes` para a
célula `notificacoes` acontece **no mesmo PR da gênese** (Fase 3), e a tela de avisos
da Caixa passa a ler da caixa nova.

Recusada, nominalmente: **a caixa nova começando vazia**. Ela criaria, por um tempo,
**duas verdades sobre "o que você tem para ler"** — o sininho mostrando um número que
não bate com a tela da Caixa. É a lei anti-duplicação do `CLAUDE.md`, e é a doença que
o projeto passou o mês curando.

**Isto altera o escopo da Fase 3**, e a alteração é deliberada: a gênese da célula
`notificacoes` deixa de ser só "nascer" e passa a incluir a migração do dado existente
e o reapontamento da tela da Caixa. O `PLANO-MESTRE` §6 é corrigido para caber nisto.

---

## 4. O que o rito produziu, e o que ficou para depois

**Entrou** (PR #243, só `contracts/`, label `contrato`):

| Arquivo | O que é |
|---|---|
| `contracts/eventos/sugestao.status-alterado.v2.json` | o **fato**, um por mudança — ganha `ator_id` **obrigatório**, no envelope |
| `contracts/eventos/notificacao.devida.v1.json` | a **carta endereçada**, uma por pessoa — genérica, serve a qualquer assunto futuro |

**Migração, medida e não estimada:** `grep -rln "status-alterado" services/ --include=*.py`
fora da `sugestoes` devolve **vazio**. Zero consumidores externos do `v1`. Ele continua
no disco e continua válido; a `sugestoes` migra em PR próprio, na célula dela (RITOS
§3.4), e o `v1` só sai quando nada mais o emitir.

**Ficou de fora, de propósito:**

- **A Fase 4 continua sendo Rito de Contrato.** A superfície que o `funil` vai consumir
  — contagem de não-lidos e lista paginada — é outra sessão com ele. Este rito não a
  autorizou nem a desenhou.
- **Nenhum canal fora do in-app.** A `DECISAO-notificacoes` §4.2 continua inteira.
- **O e-mail continua preso na Caixa.** `parametros` não é objeto livre: cada assunto
  declara a forma dos seus, com `additionalProperties: false`. Objeto livre seria a
  porta por onde um e-mail entraria de carona, e a muralha que hoje recusa campo a mais
  no `data` ficaria cega exatamente ali. Provado no PR: `email` nos parâmetros é
  **RECUSADO**.
- **O título da ideia não viaja na carta.** Uma ideia renomeada deixaria avisos antigos
  mostrando o nome velho para sempre. A tela busca o título na hora de ler.

---

*Relacionados: **`docs/decisoes/DECISAO-notificacoes.md`** (a lei da Fase 0, emendada
na §5.2 por este documento) · **`docs/notificacoes/PLANO-MESTRE.md`** (o mapa das sete
fases; §6 Fase 3 alterada pela §3 daqui) · **`RITOS.md`** §3 (o rito cumprido) ·
**`docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md`** §2 (quem é
avisado: todos os que interagiram — inalterada).*
