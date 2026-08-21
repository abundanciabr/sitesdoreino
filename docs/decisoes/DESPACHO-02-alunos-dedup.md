# DESPACHO 02 — alunos: dedup dentro da transação da matrícula

> ## ✅ EXECUTADO — PR #43, mergeado em 21/08/2026. NÃO redespache.
> A correção saiu com a estrutura de duas transações aninhadas + guarda
> `test_inv_p5_dedup_atomico.py`. Sessões paralelas estenderam o mesmo fix para
> **leads (PR #46)** e **mensageria (PR #47)** — os três dedups estão fechados.
> Lição registrada em `ARMADILHAS.md` §4.12 (PR #48).
>
> ~~Copie tudo abaixo da linha e cole para o agente.~~
> Criado em 21/08/2026 · merge: auto (CI verde)

---

# DESPACHO — alunos: o dedup de evento não pode commitar antes da matrícula

CÉLULA: alunos · WORKTREE: wt-alunos-dedup · RECEITAS: R4, R5

ANTES: leia `AGENTS.alunos.md`, `INVARIANTES.md` (INV-P5), `ARMADILHAS.md` — com atenção
especial a **§4.8** (`IntegrityError` capturado sem savepoint quebra a transação inteira),
que é exatamente o terreno deste despacho — e `services/alunos/LICOES.md`. Declaração de
abertura (RITOS.md §1) antes de tocar qualquer arquivo.

## CONTEXTO — o bug, com o código

`services/alunos/apps/eventos/management/commands/consume_eventos.py:25-30`:

```python
try:
    with transaction.atomic():
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return
handlers[envelope["event"]](envelope["data"])   # ← FORA da transação acima
```

O `EventoProcessado` **commita** no fim do `with`. Só depois a matrícula é tentada. Se
`matricular()` falhar por qualquer motivo transitório (deadlock, conexão caída, timeout),
o evento já está marcado como processado — e **qualquer reentrega futura cai no
`except IntegrityError: return` e é descartada em silêncio**.

Cenário real: o Postgres dá um hiccup de 2s num pico. O consumer registra o evento, falha
ao inserir a `Matricula`, o processo morre. Sobe de novo, o evento está marcado como
visto, **a matrícula nunca acontece**. O cliente pagou. Nada no sistema descobre — não há
reconciliação.

## MISSÃO

Fazer o registro de "evento processado" e o efeito do evento viverem ou morrerem juntos:
se o handler falhar, o evento **não** pode ficar marcado como processado.

## ALVOS (PERMITIDO ESCREVER)

- `services/alunos/apps/eventos/management/commands/consume_eventos.py`
- `services/alunos/tests/**`
- `services/alunos/LICOES.md`

## SOMENTE-LEITURA

`contracts/eventos/pagamento.aprovado.v1.json`, `CAMINHO-DOURADO.md` (R4),
`INVARIANTES.md`

## FORA DE ESCOPO

- Qualquer outra célula. **`leads` tem o mesmo bug** (`apps/core/handlers.py`,
  `processar_envelope`) — **não conserte aqui**: é outra célula e a cerca de CI reprova
  (1 PR = 1 célula). Vai em despacho próprio.
- Recuperação de mensagens presas na PEL do Redis (`xautoclaim`) — outro despacho.
- **NÃO toque em `arquivos/painel-fundacao.html`** — isso é sempre da janela raiz.

## ⚠️ A ARMADILHA DESTE DESPACHO — leia antes de escrever a correção

A correção óbvia (mover o handler para dentro do `try`) **introduz um bug novo**: se o
handler levantar `IntegrityError` por um motivo **não relacionado** ao `event_id`
duplicado, o `except` vai lê-lo como "já processado" e descartar o evento em silêncio —
trocando um bug por outro mais difícil de enxergar.

A estrutura precisa distinguir as duas coisas: uma transação externa que envolve **os
dois** (para que a falha do handler desfaça o registro), e um savepoint interno **só** em
volta do `create`, que é o único ponto onde `IntegrityError` significa "já processado".
`ARMADILHAS.md` §4.8 explica por que o savepoint aninhado é obrigatório aqui.

Escreva o comentário no código explicando a estrutura — o próximo agente vai olhar isso e
achar que é redundante.

## INVARIANTES TOCADOS

INV-P5 (matrícula idempotente sob lock). O guarda existente
(`tests/test_inv_p5_matricula_lock.py`) **não pode ser enfraquecido** — RITOS §2.3.

## DoD

- Teste-guarda novo, com evidência **vermelho→verde**: um handler que falha
  deliberadamente ⇒ (a) nenhuma `Matricula` criada, (b) **nenhum `EventoProcessado`
  gravado**, (c) a reentrega do MESMO evento depois disso **matricula normalmente**.
  Esse (c) é o ponto todo — sem ele o teste não prova nada.
- O comportamento de dedup legítimo continua: mesmo `event_id` entregue 2× ⇒ **uma**
  matrícula (é o teste que já existe; ele tem que continuar verde).
- `make ci` VERDE — cole a saída completa, sem resumir.
- `make contrato-check` VERDE (nada deve mudar no contrato).

## ORÇAMENTO

≤ 5 arquivos. Este é um despacho cirúrgico: a correção é de poucas linhas.

## EVIDÊNCIA

Saída crua do guarda novo **vermelho sem o fix e verde com o fix** (Lei 6, protocolo em
`ARMADILHAS.md` §6.1 — `git stash` do handler, não branch descartável) + `make ci`
completo. Handoff completo ao final (RITOS.md §1): branch, arquivos, resultado, pendências,
pronto para PR ou não.
