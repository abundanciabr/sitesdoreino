# LICOES.md — leads

Específico desta célula. Transversal vai em `ARMADILHAS.md` (raiz).

## `EventoProcessado.objects.create()` sem `atomic()` quebra a transação do teste

**Sintoma:** `TransactionManagementError: An error occurred in the current
transaction` na SEGUNDA query após um `IntegrityError` esperado (o dedup por
`event_id` do R4), mesmo o `except IntegrityError` tendo capturado a exceção
certa.
**Causa:** o `except` só evita que a exceção suba — não desfaz o estado
"transação abortada" que o Postgres deixa depois de um erro dentro de uma
transação aberta. `pytest-django` embrulha cada teste em uma transação
(`@pytest.mark.django_db`); a query seguinte (mesmo que só um `.count()` de
asserção) esbarra na trava. Isso é invisível fora de teste porque o comando
`consume_eventos` roda em autocommit, sem transação explícita ao redor do
loop — a mesma linha de código só quebra dentro do isolamento do teste.
**Solução:** todo INSERT usado como guarda de idempotência (`try: ...create()
except IntegrityError`) precisa do próprio savepoint:

```python
try:
    with transaction.atomic():
        EventoProcessado.objects.create(event_id=envelope["event_id"])
except IntegrityError:
    return False
```

**Isto generaliza:** a receita R4 em `CAMINHO-DOURADO.md` não mostra esse
`atomic()` — funciona em produção só porque o consumer nunca roda dentro de
uma transação externa. Qualquer célula que testar o handler de R4 diretamente
(em vez de só via loop do Redis) precisa do savepoint para o teste não quebrar
na segunda asserção. Ver também `ARMADILHAS.md` §4 (mesma lição, versão
transversal).
**Origem:** despacho leads/timeline, ao escrever `test_inv_leads_evento_idempotente.py`.

## Fase 0 → real: `test_superficie_da_api_ainda_nao_implementada` precisa ser desmembrado

O esqueleto tinha um teste parametrizado que esperava 501 em `/leads` E
`/leads/{id}/tags`. Ao implementar upsert real em `/leads` (mission desta
sessão), o handler de tags continuou 501 (fora de escopo) — o teste
parametrizado teve que virar dois testes: um smoke isolado para tags (ainda
501) e um arquivo novo (`test_leads_upsert.py`) para o comportamento real.
**Origem:** despacho leads/timeline.
