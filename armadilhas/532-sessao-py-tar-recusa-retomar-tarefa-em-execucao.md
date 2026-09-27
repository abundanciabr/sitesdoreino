---
schema_version: 2
armadilha: 532
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: baixo
gatilho:
  - ci/sessao.py
  - ci/fila.py
sinal:
  - "RECUSADO.*está 'em execução'"
guarda:
  tipo: nenhum
  motivo: "cmd_pegar (ci/fila.py) recusa de proposito qualquer estado que nao seja na_fila ou reivindicada-propria; ensinar --tar a pular o balcao quando ja em execucao e mudanca de comportamento do rito de abertura, fora do alcance de uma entrada de licao"
licao: "python ci/sessao.py --celula <c> --tarefa <slug> --tar TAR-NNN chama fila.py pegar por baixo, e cmd_pegar recusa com RECUSADO: TAR-NNN esta 'em execucao' quando a tarefa ja tem PR aberto (estado em_execucao, nao na_fila nem reivindicada por voce). Para retomar bancada de tarefa ja em execucao, chame ci/sessao.py sem --tar; a reivindicacao no balcao ja existe e nao precisa ser repetida."
---

# 532: `ci/sessao.py --tar` recusa retomar tarefa `em execução`

**Data:** 27/09/2026 · **Onde:** `ci/sessao.py`, `ci/fila.py::cmd_pegar`,
obra Appmax · **Custo evitado:** achar que a abertura da bancada está
quebrada ao retomar uma tarefa que já tem PR aberto.

## Sintoma

```
python ci/sessao.py --celula <celula> --tarefa <slug> --tar TAR-NNN
...
RECUSADO: TAR-NNN está 'em execução'.
```

A tarefa já tem PR aberto (estado calculado `em_execução`, constante
`EM_EXECUCAO = "em execução"` em `ci/fila.py`), e retomar a bancada citando
`--tar` de novo passa pelo mesmo balcão (`cmd_pegar`) que recusa qualquer
estado diferente de `na_fila` (tarefa livre) ou `reivindicada` pela própria
sessão.

## Causa

`ci/sessao.py`, ao receber `--tar`, chama `fila.py pegar TAR-NNN` como
PRIMEIRO passo da abertura (`pegar_a_tarefa`, `armadilhas/357`).
`cmd_pegar` só aceita dois casos: a tarefa está `na_fila` (reivindicação
nova) ou está `reivindicada` pela mesma sessão (reserva própria conferida).
Qualquer outro estado — inclusive `em_execução`, que é exatamente o estado
de uma tarefa que já tem PR aberto e está sendo retomada — cai no
`RECUSADO` genérico, sem distinguir "tarefa de outra sessão" de "minha
tarefa que eu mesmo já levei adiante".

## Solução

Para retomar a bancada de uma tarefa já `em_execução` (PR já aberto por
você), chame `ci/sessao.py` **sem** `--tar`:

```bash
python ci/sessao.py --celula <celula> --tarefa <slug>
```

A reivindicação no balcão já existe desde a primeira abertura; repeti-la
não é necessário e é exatamente o que o balcão recusa. Confirme o estado
antes com `python ci/fila.py listar --ao-vivo` quando houver dúvida sobre
qual a bancada certa a reabrir.

## Origem

Obra Appmax, sessão de coordenação de 27/09/2026, `ci/sessao.py` e
`ci/fila.py::cmd_pegar`.
