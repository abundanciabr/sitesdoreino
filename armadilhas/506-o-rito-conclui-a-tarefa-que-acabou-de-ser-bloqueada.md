---
schema_version: 2
armadilha: 506
estado: documentada
degrau: 8
confianca: alta
custo_por_queda: alto
gatilho:
  - ci/pr.py
  - fila/eventos/*
sinal:
  - "TAR-[0-9]{3,}-bloqueada[.]json[\s\S]*TAR-[0-9]{3,}-concluida[.]json"
guarda:
  tipo: nenhum
  motivo: distinguir "o ramo entregou esta tarefa" de "o ramo so registrou o bloqueio dela" exige ler o proposito do PR; um teste de CI nao prova isso sem reimplementar a leitura humana do diff. O que fecha e a conferencia do git status antes do pouso
licao: "Ramo que registra o BLOQUEIO de uma tarefa e abre PR sem --tarefa tem essa tarefa dada por concluida: ci/pr.py::_identificar_tarefa adota toda tarefa cujo 'quem' aponte para o ramo e cujo estado nao seja concluida, cancelada ou na fila, e bloqueada NAO esta nessa lista. O bloqueio some do quadro sem erro nenhum. Confira git status antes de terminar e apague os eventos indevidos."
---

# 506: o rito conclui a tarefa que o próprio PR acabou de bloquear

**Data:** 21/09/2026 · **Onde:** `ci/pr.py`, fila · **Custo evitado:** um bloqueio
apagado do quadro do mantenedor sem nenhum aviso.

## Sintoma

O despacho mediu que a tarefa não podia ser feita do jeito pedido, escreveu o
evento de bloqueio, e abriu o PR **de propósito sem `--tarefa`**, justamente para
não fechar uma tarefa bloqueada. O rito rodou limpo, sem erro nenhum, e embarcou
no ramo:

```
fila/eventos/20260921-XXXXXX-TAR-583-bloqueada.json
fila/eventos/20260921-XXXXXX-TAR-583-submetida.json
fila/eventos/20260921-XXXXXX-TAR-583-concluida.json
```

O estado calculado da fila passou de `bloqueada` para `concluida`. Nenhum comando
falhou, nenhuma mensagem apareceu, e o motivo do bloqueio deixou de existir para
quem lê o quadro.

## Causa

`ci/pr.py::_identificar_tarefa` monta o conjunto de candidatas e, além do
`--tarefa` explícito e da tarefa da abertura, acrescenta toda tarefa cujo estado
calculado aponte o `quem` para este ramo:

```python
candidatos.update(tid for tid, estado in estados.items()
                  if estado.get("quem") == ramo and estado["estado"] not in (CONCLUIDA, CANCELADA, NA_FILA))
```

`BLOQUEADA` não está na lista de exclusão. Como o próprio ramo reivindicou a
tarefa antes de bloqueá-la, o `quem` aponta para ele, e a tarefa bloqueada entra
como candidata única. Omitir `--tarefa` não protege nada: a inferência acontece
de qualquer jeito, e é mais forte que a intenção de quem chamou.

Isto é parente de `armadilhas/495`, mas não é o mesmo caso. Lá a tarefa errada
entrava por menção solta no CORPO do PR, e só quando não havia nenhuma outra
candidata. Aqui a tarefa entra pelo ESTADO da fila, é a tarefa certa, e o erro é
o veredito: bloqueada virou concluída.

## Solução

O conserto manual, que foi o aplicado e funcionou: apagar os eventos
`submetida` e `concluida` num commit seguinte, no mesmo ramo. O estado calculado
volta sozinho para `bloqueada`, porque o estado é derivado dos eventos.

```bash
git rm fila/eventos/*-TAR-NNN-submetida.json fila/eventos/*-TAR-NNN-concluida.json
py -3.12 ci/fila.py validar
```

A regra que evita: **todo PR cujo trabalho foi bloquear uma tarefa exige
`git status --short` conferido antes de terminar**, procurando por evento
`concluida` que você não escreveu. Se ele estiver lá, apague antes do pouso. Um
PR que apenas registra bloqueio nunca deve sair com evento de conclusão dentro.

**Origem.** Medido em 21/09/2026 no despacho da TAR-583, bloqueada por conflito
entre a ordem do despacho e o portão de contrato.
