# DECISÃO — o sistema de notificações da plataforma (as três respostas do mantenedor)

> **Tomada pelo mantenedor em 25/08/2026**, respondendo às três perguntas da §7 do
> `docs/notificacoes/PLANO-MESTRE.md` — a Fase 0 daquele plano. Palavras dele:
> *"as respostas são: sim, sim e nascer só com a Caixa. Vou seguir as recomendações
> integralmente."*
>
> **O que originou:** o pedido dele, no mesmo dia, de um **sininho ao lado do nome em
> todo o site** — *"algo como as notificações do Facebook, e isso já é o começo do que
> vamos enviar de notificações para o aluno e **serão muitas**"*. O pedido virou plano
> (`docs/notificacoes/PLANO-MESTRE.md`), o plano terminou em três perguntas que só ele
> podia responder, e este documento é a resposta virando lei.
>
> **Status:** *isto é lei. O `docs/notificacoes/PLANO-MESTRE.md` é o **mapa de
> execução** — as sete fases, o terreno medido, os riscos. Se os dois divergirem, a
> lei vence, e o plano é corrigido para caber nela.* Este documento não copia trechos
> longos do plano de propósito: duas cópias derivam em silêncio (lição do Lote 4 da
> Caixa). Onde precisar do detalhe, siga o ponteiro.

---

## 1. Decisão 1 — a célula `notificacoes` nasce

**SIM.** A caixa de notificações mora numa **célula própria**, e não espalhada por
célula nem dentro da `identidade`. As três opções e o preço de cada uma estão na §4 do
plano mestre; o argumento decisivo é o *"serão muitas"* dele: um sino que o site
desenha em **toda** página tem de custar **uma** pergunta barata, e tem de continuar
custando uma quando existirem dez células publicando.

### Isto abre o congelamento arquitetural, de propósito

Célula nova não é rotina nesta plataforma. Esta é a terceira vez que o congelamento é
aberto deliberadamente, e sempre pela palavra do mantenedor: foi assim que nasceram a
`sugestoes` e a `identidade` (`docs/decisoes/DECISAO-celula-de-identidade.md`). O
registro fica aqui para que nenhuma sessão futura trate a criação como detalhe de
implementação — nem, no sentido contrário, a trate como impossível.

### Como ela nasce (as condições da gênese, que são lei)

1. **`freeze: not-applicable` no `ci/manifesto-de-contratos.json`.** A célula nasce
   sem contrato público e só congela contrato quando alguém for consumi-la — é a
   correção nº 1 da auditoria da Caixa, e o caminho que a `identidade` seguiu (gênese,
   depois contrato, em dois tempos).
2. **Rollback no mesmo PR da gênese.** A gênese exige mandato para
   `.github/workflows/rollback.yml`: célula que não aparece na lista fixa daquele
   workflow **fica sem rollback**, e o portão `testar-o-testador` reprova — é a
   `armadilhas/076-celula-nova-reprova-em-testar-o-testador-rollback.md`, e é o item
   (2) do H17. Célula nasce **com** rollback, na mesma entrega.
3. **Banco isolado, role própria** (Lei 2, muralha de dados). A `notificacoes` não lê
   o banco de ninguém; ela ouve o fio.
4. **Passo de provisionamento do mantenedor na VPS** (banco + `env/notificacoes.env`),
   porque env nunca viaja por pipeline (INV-P8, Lei 5). Ele é entregue como **script
   versionado com invocação de UMA LINHA** — `infra/provisionar-notificacoes.sh` —,
   **nunca** como bloco de texto para colar passo a passo. É a lição H18/H19/H20: em
   24/08/2026 um passo entregue como texto falhou três vezes seguidas, nenhuma por
   culpa dele, e a cura foi parar de entregar texto.

---

## 2. Decisão 2 — a garantia muda, e o que ela NÃO é

**SIM à saída A da §3 do plano mestre**, com a promessa reescrita. Esta é a seção mais
importante deste documento, porque é a única coisa aqui que uma sessão futura pode
"consertar" de boa-fé e desfazer a decisão sem perceber.

### A promessa NOVA

> **A mudança de status e o fato notificável nascem na MESMA transação (na outbox); a
> entrega do aviso é em segundos, e é rastreável.**

### A promessa que ela SUBSTITUI

> *"O aviso existe no mesmo instante da mudança."*

Essa era a garantia protegida nominalmente pela §2 da
`docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` — o `Aviso`
local da Caixa nascendo dentro da transação do `HistoricoStatus`. **Ela está, a partir
de hoje, substituída pela promessa nova.** A §2 daquela decisão continua valendo em
tudo o mais (quem é avisado: todos os que interagiram, não só o autor; o aviso é a
cópia do aluno; cada pessoa vê só os avisos dela).

### O que isto NÃO é

**Não é afrouxamento de durabilidade.** O fato continua não podendo se perder: ele é
gravado na outbox na mesma transação da mudança de estado, e o relay publica depois —
padrão outbox, **INV-P6**, que é como a plataforma inteira já roda. Estado sem evento
e evento sem estado continuam impossíveis.

O que muda é **a latência** e **a janela em que a pessoa ainda não sabe**. Nada mais.

### A frase que impede o conserto errado

O guarda que hoje prova a atomicidade medindo a tabela de `Aviso` —
`services/sugestoes/tests/test_inv_aviso_nasce_com_o_status.py` — **muda junto com esta
decisão**, para medir a **outbox** (a forma que
`services/sugestoes/tests/test_inv_outbox_transacional.py` já usa).

**Isso é a implementação da decisão, não um teste enfraquecido.** Nenhuma sessão
futura deve "restaurar" o guarda antigo, nem tratar a mudança dele como regressão a
corrigir: o invariante não foi removido, foi **reapontado** para onde o fato passou a
nascer. Um guarda que continuasse exigindo o `Aviso` local dentro da transação estaria
exigindo exatamente a arquitetura que o mantenedor decidiu não ter.

### As saídas recusadas, nominalmente

- **Saída C — chamar a célula `notificacoes` por HTTP dentro da transação da
  `sugestoes`: RECUSADA.** Contraria a **Lei 3** da `CONSTITUICAO.md`: acopla duas
  células no caminho crítico, e a célula de notificações fora do ar passaria a
  **impedir mudar status**. Está proibida — não é uma alternativa a reconsiderar sob
  pressão de prazo.
- **Saída B — espelho local + central: RECUSADA.** Ela *parece* a mais segura e é a
  mais cara: cria **duas verdades sobre "lido"**, e essa dívida só aparece quando o
  aluno reclama que já tinha lido. Uma notificação tem **um dono só**.

---

## 3. Decisão 3 — a V1 nasce só com a Caixa

**A primeira versão notifica apenas fatos da Caixa de Sugestões** — hoje, a única
célula que produz fatos notificáveis. Quiz, matrícula e pagamento produzem eventos que
**poderiam** virar notificação, e o *"serão muitas"* dele diz que virão.

### A consequência prática, e ela é uma exigência de desenho

**Assunto novo vira UM PR PEQUENO, nunca uma refatoração.** Isso não é uma esperança
sobre o futuro: é requisito do primeiro PR da célula. Se acrescentar "matrícula
confirmada" exigir mexer na forma da tabela, no consumidor ou no contador, o desenho
está errado e deve ser corrigido **antes**, não depois.

Nascer só com a Caixa é recorte de **conteúdo**, não de arquitetura — o desenho nasce
pronto para os outros assuntos desde o primeiro dia.

---

## 4. O que esta lei NÃO autoriza

Ela autoriza a **gênese** e fixa o **desenho**. Ela não substitui nenhum rito.

1. **As Fases 2 e 4 continuam sendo Rito de Contrato** (`RITOS.md` §3), com o
   mantenedor presente e PR só de `contracts/` com a label `contrato`:
   - **Fase 2** — o envelope de evento ganha `ator_id` (versão nova do schema; os
     consumidores migram em PRs seguintes, nunca no mesmo);
   - **Fase 4** — a superfície de máquina que o site (`funil`) consome: contagem de
     não-lidos e lista paginada.

   Contrato **nunca** muda dentro de um lote (`RUNBOOK-LOTES.md` §7). Esta lei não
   dispensa uma vírgula disso.

2. **Nenhum canal fora do in-app.** E-mail, push do navegador e SMS **não estão
   autorizados**. A Fase 7 depende de **decisão nova**, e o motivo é concreto: o
   e-mail vive numa linha só, por decisão do mantenedor
   (`docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md` §3), e a `mensageria`
   precisaria de um destinatário. Vale saber que o envio da `mensageria` ainda é
   **stub** — "ligar o e-mail" é construir o envio, não plugar um fio.

3. **A Fase 1 (o id que atravessa) não é opcional.** Sem um id de pessoa que qualquer
   célula entenda, uma caixa central recebe o fato e não consegue endereçar ninguém
   (§2 do plano mestre). Qualquer atalho vira o e-mail circulando — a decisão que não
   se reabre.

---

## 5. As duas irreversibilidades que o desenho tem de respeitar desde o PRIMEIRO PR

Estão medidas na §5 do plano mestre. Ficam aqui porque errar qualquer uma delas **não
tem conserto barato depois**.

### 5.1 Notificação é DADO, nunca frase pronta

A linha guarda **`tipo` + `parametros` (json)** — mais destinatário, ator e `lido_em`.
A frase nasce **na leitura**, no idioma de quem está lendo.

O site serve **três idiomas**. Gravar *"Sua ideia mudou para Em desenvolvimento"* no
banco congela o idioma de quem gravou, e quem lê em espanhol recebe português para
sempre. **Texto já gravado não se traduz depois** — por isso é irreversível, e por
isso é lei e não recomendação.

### 5.2 O contador é O(1), com arquivamento, e isso se prova

O sino aparece em **toda página**. Um `COUNT(*)` numa tabela que cresce para sempre
fica lento exatamente quando o produto der certo.

Exigências, com prova no mesmo PR:
- contador **O(1)** (contador por pessoa, não varredura);
- **arquivamento desde o começo** — notificação lida e velha sai do caminho quente;
- fan-out em **lote**;
- e o **teste de volume** que prova que o custo não cresce com a plateia:
  `assertNumQueries` com **2** e com **200** destinatários, como o EVO-42 fez em
  `services/sugestoes/tests/test_volume_dos_avisos.py`.

---

## 6. Estado

**Decidido em 25/08/2026. A Fase 0 do `docs/notificacoes/PLANO-MESTRE.md` está
FECHADA.** As Fases 1 a 7 são trabalho de agente e de rito, na ordem do plano — cada
uma destrava a seguinte.

---

*Relacionados: `docs/notificacoes/PLANO-MESTRE.md` (o mapa de execução),
`docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` §2 (a
garantia que esta lei substitui), `docs/caixa-de-sugestoes/DECISAO-EVO-01-identidade.md`
§3 (o e-mail numa linha só), `docs/decisoes/DECISAO-celula-de-identidade.md` (o
precedente de célula nova), `docs/decisoes/DECISAO-onde-mora-a-sessao.md` §4 (falha
aberta), `CONSTITUICAO.md` Leis 2 e 3, `INVARIANTES.md` INV-P6 e INV-P8, `RITOS.md` §3,
`RUNBOOK-LOTES.md` §7, `armadilhas/076`.*
