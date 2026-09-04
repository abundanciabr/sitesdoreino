---
schema_version: 2
armadilha: 310
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  motivo: era `nenhum`, e a própria entrada dizia o que faltava — mudar `ci/esperar.py` para reconsultar o estado antes de desistir, com mandato. Foi feito no MESMO dia (PR #964, `armadilhas/308`), e o guarda é o par de testes que fixa os dois sentidos: o ERROR se remede, o FAIL nunca se remede
sinal:
  - `o GitHub ainda não sabe se dá para mergear`
  - `o portão RECUSOU o pouso do PR`
---

# `--e-pousar` chama o portão no PIOR instante e sai ERROR: o pouso volta a depender de um passo seu depois

**Sintoma.** Você usa o caminho normal de 03/09/2026, aquele que existe para o
pouso NUNCA ficar para depois:

```bash
python ci/esperar.py --checks <N> --teto 20 --dizendo "..." --e-pousar
```

Os checks ficam **todos verdes**, a espera anuncia `🛬 checks verdes: passo pelo
portão e peço pouso`, e o portão devolve:

```
check/espelho-da-main   PASS   verde
check/ci-celula-gate    PASS   verde
orçamento               PASS   14 arquivo(s)
registro a bordo        PASS   o registro viaja neste PR e cita #946
dívida do livro         PASS   livro em dia
--- ERROR conflitos ---
O GitHub calcula isso de forma assíncrona; se você acabou de dar push,
espere alguns segundos e rode de novo.
RESULTADO  ERROR
🔴 o portão RECUSOU o pouso do PR 946 (exit 2)
```

Tudo verde, e **nenhum pouso foi pedido**. Se a sessão terminar aqui, o PR fica
aberto, pronto, esperando um humano que não sabe que está sendo esperado — que
é exatamente a falha que custou horas ao mantenedor em 03/09/2026 e que o
`--e-pousar` nasceu para abolir.

**Medido em 03-04/09/2026** (Fase 0 da Fila do Primeiro Dólar): **5 usos do
`--e-pousar`, 3 terminaram em `ERROR conflitos`** (PRs #946 duas vezes, #955,
#962). Os 2 que passaram (#949, #951) tinham o último push mais velho.

**Causa — e não é defeito do portão.** O GitHub recalcula a mergeabilidade de
todo PR aberto de forma **assíncrona**, e o gatilho do recálculo é a `main` se
mover ou o ramo receber commit. O `--e-pousar` chama `ci/mergear.py --pousar`
no **instante exato** em que o último check vira verde — e esse instante é,
por construção, logo depois de um push (o que disparou os checks) e no meio de
uma `main` movimentada (~100 entregas/dia). É a janela de maior probabilidade
de `mergeable=UNKNOWN`. O portão então faz a coisa certa: `UNKNOWN` não é
`MERGEABLE`, e "não consegui medir" nunca vira PASS ([INV-CI01]).

A `armadilhas/130` já descrevia o `UNKNOWN` na janela de merge serial, com
`--confirmo`. Esta entrada existe porque o caminho novo **inverte o risco**: lá
o robô estava ali, olhando, e rodava de novo; aqui o comando é justamente o
que permite ir embora, e ele falha calado do ponto de vista de quem já saiu.

> **CURADO EM 04/09/2026, no mesmo dia em que esta entrada nasceu.** Esta entrada
> escreveu o que faltava: *"mecanizar seria mudar `ci/esperar.py` para reconsultar
> o estado de conflito antes de desistir, e essa é decisão de quem for consertar o
> `--e-pousar`, com mandato"*. Foi exatamente isso que o **PR #964** fez, com o
> mandato do despacho de lote, horas antes de esta entrada pousar — as duas
> sessões não podiam se ver.
>
> `pousar_pelo_portao` agora **remede o portão** quando, e só quando, a recusa é
> `ERROR` com a marca do recálculo do GitHub: seis voltas de vinte segundos,
> falando a cada uma. `FAIL` segue sem remedição nenhuma, e o código de saída
> passou a distinguir reprovado (`1`) de não consegui medir (`2`). O guarda é o
> par de testes mais duas mutações deliberadas: `armadilhas/308`.
>
> **O que isso muda para você:** o passo à mão descrito abaixo virou **plano B**,
> para quando as seis voltas se esgotarem (o GitHub que nunca decide) ou para
> quem estiver numa árvore anterior ao #964. **A regra que NÃO mudou, e é o
> melhor desta entrada:** `--e-pousar` não dispensa conferir se o pouso foi
> pedido. A prova é a etiqueta `pousar` no PR, nunca a tela verde que veio antes.

**Solução à mão, o plano B, e ela custa uma linha.** Ao ver `ERROR conflitos` depois do
`--e-pousar`, **não repita a espera inteira** (os checks já estão verdes; medir
de novo é gastar minutos contra um relógio que você não controla). Chame o
portão à mão, uma vez:

```bash
python ci/mergear.py <N> --pousar
```

Nas 3 quedas medidas, essa chamada devolveu `MOTIVO-DA-RECUSA: BASE-VELHA` e
**pediu o pouso do mesmo jeito** — porque base velha é o único caso que o
`--pousar` aceita, e é literalmente o serviço da pista (RITOS.md §2 peça 5). Ou
seja: o que parecia recusa era a fila funcionando.

**A regra que fica:** `--e-pousar` **não dispensa conferir se o pouso foi
pedido**. Antes de encerrar, leia o desfecho da espera; se ele terminou em
`🔴 o portão RECUSOU o pouso`, o gesto que fecha o rito é o `--pousar` à mão,
na mesma resposta. Um `gh pr view <N> --json labels` que mostre a etiqueta
`pousar` é a prova barata de que a fila assumiu.

**O que NÃO fazer:** repetir `--checks ... --e-pousar` (mede o que já foi
medido); forçar com `gh pr merge` (o botão não é caminho, Lei 4); ou concluir
que o PR está quebrado — os checks estão verdes e o conteúdo está bom.

**Origem.** Fase 0 da Fila do Primeiro Dólar, 03-04/09/2026, PRs #946, #949,
#951, #953, #955 e #962. Parente direta da `armadilhas/130` (o `UNKNOWN` em si)
e do padrão 2 da `RETROSPECTIVA-FASE-D.md`: o mecanismo que promete "o pouso
nunca fica para depois" precisa de alguém conferindo que ele cumpriu.
