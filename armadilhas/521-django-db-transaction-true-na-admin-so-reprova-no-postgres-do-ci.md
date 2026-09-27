---
schema_version: 2
armadilha: 521
estado: documentada
degrau: 4
confianca: media
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: o SQLite local nao tem o gatilho de auditoria que o Postgres do CI recria; nao ha portao local capaz de reproduzir a diferenca de banco sem rodar contra Postgres.
sinal:
  - "django.db.utils.NotSupportedError"
gatilho:
  - services/admin/tests
licao: "@pytest.mark.django_db(transaction=True) na admin passa no SQLite local e reprova no Postgres do CI: o flush entre testes bate no gatilho (trigger) de auditoria, que o SQLite nao recria. Rode a suite da admin contra Postgres antes de confiar num django_db(transaction=True) verde local."
---

# 521: `django_db(transaction=True)` na admin só reprova no Postgres do CI

## Sintoma

Um teste marcado `@pytest.mark.django_db(transaction=True)` em
`services/admin/tests` passava localmente (SQLite) e reprovava no CI
(Postgres) com um erro do tipo

```
django.db.utils.NotSupportedError
```

disparado durante o `TRUNCATE`/flush que o `transaction=True` do pytest-django
faz entre testes.

## Causa

`transaction=True` pede ao pytest-django para envolver cada teste na própria
transação e desfazer com `TRUNCATE` (ou equivalente) ao final, em vez do
rollback padrão. O Postgres recria, no schema de teste, os gatilhos (triggers)
de auditoria da admin; o `TRUNCATE` dispara esse gatilho. O SQLite local não
tem suporte a esses triggers, então o mesmo teste nunca exercita esse caminho
ali: ele só aparece contra um banco Postgres de verdade.

## Solução

Suíte da admin com `django_db(transaction=True)`: rode contra Postgres antes
de declarar verde, não confie no SQLite local sozinho. Se o ambiente local
não tem Postgres disponível, trate o teste como "não confirmado localmente"
e deixe o CI ser a prova final antes do PR.

## Evidência

Suíte de `services/admin/tests`, sistema de experimentos, 26/09/2026: verde
no SQLite local, vermelho no Postgres do CI.
