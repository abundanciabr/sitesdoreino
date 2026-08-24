# RETROSPECTIVA DA FASE D — os padrões que se repetem

> **Para quem:** todo agente que for trabalhar neste repositório, em qualquer
> célula, em qualquer fase. **Leia depois** do `PLAYBOOK.md` e do
> `armadilhas/INDICE.md`, **antes** de escrever código.
>
> **O que este documento NÃO é:** não é lista de bugs (isso é `armadilhas/`,
> uma entrada por sintoma), não é lei (`CONSTITUICAO.md`), não é receita
> (`CAMINHO-DOURADO.md`) nem invariante (`INVARIANTES.md`).
>
> **O que ele É:** os **padrões que atravessam** 67 armadilhas registradas —
> o andar de cima daquele catálogo. Ele existe porque a Fase D provou que
> conhecer os casos individuais **não impede** repetir a categoria: em
> 23/08/2026 uma sessão repetiu, no mesmo dia, dois erros que já estavam
> documentados em outra forma. Catálogo de sintomas cura o caso; só o padrão
> cura a classe.

Escrito em 23/08/2026, ao fim de um dia de trabalho na Fase D (2 de 4 critérios
de `ESQUELETO-QUE-ANDA.md` — ✅ 1 local · ☐ 2 VPS/MP, adiado por decisão do
mantenedor · ✅ 3 drill de rollback · ☐ 4 fecha junto com o 2), a pedido do
mantenedor.

---

## 1. Falso-verde é o modo de falha nº 1 deste projeto

Não é opinião — é o padrão mais frequente do catálogo:

| O que aconteceu | Por que ficou verde |
|---|---|
| `make contrato-check` dizia **OK** com o contrato divergente | `python3` era o stub da Microsoft Store; as duas pontas do `diff` viraram vazio, e `diff(vazio, vazio)` é igualdade |
| **Nenhum** green histórico do `deploy-celula` provou deploy real (até 21/08/2026) | o script terminava em `docker compose ps`, que sai 0 mesmo com a lista vazia |
| Veredito de run lido de um comando com `\| tail` | o exit de um pipeline é o do **último** comando |
| `make ci` da célula verde com o contrato **apagado** | o alvo decidia pelo disco (`if [ -f ... ]`), não pelo manifesto |

**A regra, em uma frase: _ausência de evidência nunca é evidência de sucesso_**
([INV-CI01]).

Consequências práticas, obrigatórias:

- Todo portão devolve **quatro** estados — `PASS` / `FAIL` / `ERROR` / `SKIP` —
  e **`ERROR` nunca vira `PASS`**. "Não consegui medir" é resultado, não silêncio.
  `SKIP` só existe **declarado**, jamais inferido.
- **Veredito vem da fonte estruturada**: `gh run view <id> --json status,conclusion`.
  Nunca do exit de um pipe, nunca de `\| tail`, nunca de "não deu erro".
- **Todo verificador novo tem de ser testado com o instrumento quebrado de
  propósito.** Os três estados: aceita o certo · recusa o errado **e diz o quê** ·
  erro de instrumento vira `ERROR`. Um portão que nunca foi visto reprovando é
  um portão que ninguém sabe se reprova.

## 2. Garantia declarada sem mecanismo apodrece

Toda vez que um documento afirmou uma propriedade que nada impunha, a
propriedade estava falsa quando alguém finalmente olhou:

- `ESQUELETO-QUE-ANDA.md` afirmava que o esqueleto roda "no CI a cada PR de
  célula que participe do caminho". **Nunca rodou** — não existe em workflow
  nenhum.
- A Lei 4 exigia revisão de terceiro num repositório de **um** colaborador, e o
  GitHub proíbe aprovar o próprio PR. Era **inexecutável**, não rigorosa — e
  ninguém tinha percebido porque ninguém tentou impor.
- O workflow de rollback (23/08/2026) prometia em três documentos que o alvo é
  "ancestral da `main`"; o código media contra o **ref do disparo**. Só a
  auditoria pegou.
- Os golpes 5 e 14 do red-team foram **executados com evidência real** e a
  tabela do rito continuou `☐` nos dois casos — **2 dias** de distância entre
  eles (21/08 e 23/08/2026), mesma falha. A proximidade é o ponto: não foi uma
  lição esquecida com o tempo, foi a mesma sessão repetindo em 48h algo que já
  estava documentado.

**A regra:** toda promessa escrita precisa de **(a)** um mecanismo que a imponha
e **(b)** um teste-guarda que reprove se alguém a desfizer. Se hoje não dá para
mecanizar, **escreva que não está imposta** — buraco assumido é gerenciável,
meia-verdade não. E, ao terminar um teste do rito, **marcar a tabela faz parte
de terminar**: resultado que não está na tabela não aconteceu, para quem lê depois.

## 3. A prova vem de fora, não de dentro

O drill de rollback (23/08/2026) escolheu **de propósito** uma versão anterior
cuja diferença era **visível pela internet pública** — as páginas de checkout
respondiam 404 nela. Isso transformou "o container reiniciou" (que não prova
nada) em `200 → 404 → 200` medido como qualquer visitante veria.

O contraste é o H13: `docker compose ps` vazio + exit 0 + "✅ Successfully
executed" — verde perfeito, deploy inexistente.

**A regra:** prova de que algo funciona em produção se mede **do lado do
usuário**, pela borda pública. E, ao desenhar um teste, **escolha o alvo que
torna a diferença observável** — se sucesso e fracasso parecem iguais de fora, o
teste não é teste.

## 4. Nas bordas externas, fail-closed — e o 2xx não é sucesso

O bug mais caro da Fase D: o cliente do Mercado Pago traduzia um corpo de **erro**
em `201 Created` com QR **vazio** — o cliente via uma tela de pagamento que não
pagava. A causa não foi o erro do provedor; foi a tradução otimista
(`str(resposta.get("id", ""))` → string vazia → seguiu adiante como sucesso).

Da mesma família: dedup que marcava o evento como processado **antes** de aplicar
o efeito (reentrega descartada em silêncio, em 3 células); webhook que confiava no
`status` do corpo **não assinado**.

**A regra:** em toda borda externa, **status 2xx não é sucesso** — o corpo
precisa descrever a coisa que você pediu, e o que não descrever levanta erro
nomeado. Nada que decide dinheiro pode vir de dado não assinado: a assinatura
cobre o `data.id`, então o **status vem da consulta à API**, nunca do corpo.

## 5. O gargalo era humano — e mecanizá-lo foi a maior alavanca do projeto

Medido no `PLANO-10X`: **mediana de 22 min e média de 264 min por merge**,
esperando o mantenedor. Não era falta de rigor; era um humano no caminho crítico.

Três coisas que eram "cole este bloco no terminal" viraram pipeline em 48 horas:
o **merge** (Lei 4 reescrita), o **cadastro de domínio** (`infra/sites.json`), e o
**rollback** (`rollback.yml`). O rollback é o caso exemplar: o rito mandava
responder a emergências "em segundos", mas o comando exigia uma chave SSH que
agente não tem — ou seja, **o caminho mais rápido dependia de acordar uma
pessoa**. A regra contradizia a si mesma e ninguém tinha notado.

**A regra:** todo passo que depende do mantenedor merece a pergunta *"isso pode
virar pipeline?"*. Quando **não** puder — segredo, painel de terceiro, console do
provedor (Lei 5) — registre em `ARMADILHAS-OPERACAO.md` §1 **e diga ao humano em
texto claro no relatório final**. Contornar em silêncio faz o mesmo atrito voltar
no próximo despacho, e no seguinte.

## 6. Contexto é orçamento, e ele decide arquitetura antes do código

O `ARMADILHAS.md` monolítico chegou a ser **48% da carga de contexto de todo
despacho** — por isso virou índice + uma entrada por arquivo. E o teto de **15
arquivos por PR** é portão mecânico: ele decide a divisão do trabalho **antes** da
primeira linha.

**A regra:** leia o `INDICE.md` e abra **só** a entrada que casa com a sua tarefa
— ler a pasta inteira desfaz o motivo de ela existir. Conte os arquivos no papel
antes de codar; se estourar 15, divida o despacho **e diga isso na primeira
resposta**, não no fim.

## 7. Sessões paralelas: arquivo novo, nunca o fim de um arquivo compartilhado

Em 23/08/2026 uma sessão acrescentou quatro entradas ao fim do `ARMADILHAS.md`
**enquanto outra sessão particionava exatamente aquele arquivo**. Funcionou por
sorte (a segunda absorveu as entradas da primeira); a colisão no mesmo hunk era o
resultado esperado. No mesmo dia, a mesma sessão concluiu **erradamente** que seu
trabalho no painel havia sumido — o conteúdo tinha migrado para
`arquivos/painel-dados.js` por uma terceira sessão, e ela olhou o arquivo antigo.

**A regra:**

- **Entrada nova = arquivo novo** (`armadilhas/NNN-slug.md`), nunca append ao fim
  de um arquivo que outra sessão pode estar reescrevendo.
- Antes de editar qualquer artefato compartilhado: `git fetch` e **confirme que
  ele ainda é o que você pensa que é**.
- **Se o `CLAUDE.md` (ou qualquer lei) descrever um estado que o repositório não
  tem, isso é sinal de trabalho paralelo em voo — pergunte, não improvise pelo
  caminho antigo.**

## 8. Não afirme viabilidade sem ler a configuração

Ainda em 23/08/2026, uma sessão afirmou ao mantenedor que o critério 2 da Fase D
era "quase todo meu" e propôs um plano de execução — **antes** de ler o
roteamento do Traefik. A peça central (`POST /intents/{id}/card`) **não é
acessível pela internet**, e o proxy no checkout não existe. O plano era
impossível, e a afirmação influenciou uma decisão do mantenedor.

**A regra:** afirmação de viabilidade exige **leitura da configuração real**
(roteamento, permissões, secrets, workflow), não inferência a partir do código de
aplicação. Na dúvida entre investigar mais 10 minutos e prometer, investigue.

---

## Como usar isto num despacho

1. Antes de codar, releia os **títulos** das 8 seções (30 segundos). Eles são
   perguntas: *meu portão pode ficar verde sem medir? estou prometendo algo que
   nada impõe? minha prova é de fora? esta borda falha fechada?*
2. Ao terminar, se a sua sessão produziu um **caso novo** de um destes padrões,
   a entrada vai para `armadilhas/NNN-slug.md` (sintoma concreto primeiro) e
   `python ci/indice_de_armadilhas.py` regenera o índice.
3. Se você descobrir um **padrão novo** — que atravessa vários casos e não cabe
   em nenhuma das 8 seções — acrescente uma seção aqui. Este documento é a
   memória de segunda ordem do projeto; ele cresce devagar, de propósito.
