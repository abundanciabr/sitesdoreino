<!-- Entrada extraida de ARMADILHAS.md (o monolito) em 23/08/2026.
     Categoria de origem: §4 — Django e django-ninja
     ID historico: §4.8  ·  referencias antigas "ARMADILHAS §4.8" apontam para este arquivo.
     O INDICE.md e GERADO: nao o edite a mao (python ci/indice_de_armadilhas.py). -->

# 4.8 `IntegrityError` capturado sem savepoint quebra a transação do teste inteira

**Sintoma:** um `except IntegrityError:` que deveria simplesmente ignorar uma
duplicata (dedup por `unique=True`, padrão da Receita R4) funciona isolado, mas a
**query seguinte** — no mesmo teste, ou até um teste depois que reusa a conexão —
estoura `django.db.transaction.TransactionManagementError: An error occurred in the
current transaction. You can't execute queries until the end of the 'atomic' block.`
**Causa:** `Model.objects.create(...)` dentro de um `try/except IntegrityError` sem
`transaction.atomic()` próprio roda na transação corrente inteira (a que o
`pytest.mark.django_db` já abriu para o teste). Quando o INSERT viola a constraint
`UNIQUE`, o Postgres marca **essa transação inteira** como abortada — o Django só
descobre isso na tentativa de query seguinte, não na hora do `except`.
**Solução:** todo `create()` que pode legitimamente colidir com uma constraint única
(dedup de evento, corrida de criação idempotente) precisa do próprio savepoint:

```python
try:
    with transaction.atomic():          # savepoint — só ISTO é desfeito no IntegrityError
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return
```

**Atenção — a Receita R4 em `CAMINHO-DOURADO.md` (bloco `apps/eventos/management/
commands/consume_eventos.py`) mostra o `create()` sem esse `with transaction.atomic()`
aninhado.** Reproduz o bug assim que dois eventos (ou o mesmo evento 2×) passarem pelo
mesmo teste. Quem copiar a receita ao pé da letra herda o bug — considere `issue
arquitetura:` para corrigir a receita na fonte. **Atualização (21/08/2026):** isso
deixou de ser suspeita — ver §4.12, onde a mesma receita produziu um segundo bug, pior,
em três das quatro células consumidoras.
**Origem:** alunos (matrícula por evento, R4/INV-P5) — descoberto ao escrever o
teste-guarda de reentrega de `event_id`. **Redescoberto de forma independente** em
leads (timeline por evento) na sessão seguinte, mesmo sintoma, mesma causa — reforça
que é falha da receita, não acidente de uma célula: qualquer célula que testar o
handler de R4 direto (sem passar pelo loop do Redis) bate nisso.
