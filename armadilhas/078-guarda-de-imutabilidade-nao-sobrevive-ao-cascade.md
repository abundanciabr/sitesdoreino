# Guarda de imutabilidade passa em todos os testes e mesmo assim o CASCADE apaga as linhas

**Sintoma:** você protegeu uma tabela append-only nas duas metades que a
`armadilhas/023` manda proteger — `Model.save()` **e** `QuerySet.update()`/`delete()`
num QuerySet customizado — os testes ficam verdes, e aí:

```python
sugestao.delete()          # a linha PAI
HistoricoStatus.objects.filter(sugestao=sugestao).count()   # -> 0
```

O histórico "imutável" evaporou, sem exceção nenhuma, sem log nenhum.

**Causa:** o `Collector` do Django (`django/db/models/deletion.py`) **não usa o seu
QuerySet**. Ele coleta os objetos relacionados e emite
`sql.DeleteQuery(model).delete_batch(pks)` — SQL montado direto, que não passa nem por
`Model.delete()` nem por `QuerySet.delete()`. Todo `on_delete=CASCADE` apontando para a
sua tabela é, portanto, uma porta dos fundos que os dois guardas da 023 não cobrem.

**Solução — as duas que funcionam, e valem juntas:**

1. **`on_delete=models.PROTECT`** na FK que aponta para a tabela append-only. Apagar o
   pai passa a levantar `ProtectedError` durante a coleta, antes de qualquer SQL. É a
   correção barata e legível.
2. **Trigger no próprio banco**, criado por `RunSQL` na migration — o degrau que
   sobrevive a `cursor.execute` cru, a `psql`, ao collector e a qualquer código futuro
   que não conheça a sua classe:

```python
migrations.RunSQL(
    sql=[CRIAR_FUNCAO, CRIAR_TRIGGER],   # LISTA, nunca string única: string passa
    reverse_sql=[APAGAR_TRIGGER, APAGAR_FUNCAO],   # por prepare_sql_script, que
)                                        # fatia o SQL em `;` com o sqlparse
```

```sql
CREATE OR REPLACE FUNCTION x_append_only() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'INV-xxx: tabela e append-only; UPDATE e DELETE sao recusados';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER x_append_only BEFORE UPDATE OR DELETE ON <tabela>
FOR EACH ROW EXECUTE FUNCTION x_append_only();
```

No teste, o trigger aparece como `django.db.utils.DatabaseError` com a sua mensagem;
envolva em `transaction.atomic()` aninhado (savepoint) para a transação do teste
sobreviver e ainda poder consultar depois. `TRUNCATE` **não** dispara trigger de linha,
então o teardown de `django_db(transaction=True)` continua funcionando.

**O teste que falta na 023:** apague o objeto PAI e afirme que as linhas continuam lá.
Sem ele, um guarda de imutabilidade fica verde protegendo só metade das portas.

**Origem:** EVO-11 (`sugestoes`, `HistoricoStatus` append-only da
`docs/caixa-de-sugestoes/ESPECIFICACAO-CELULA.md` §8) — a spec §6 pedia `CASCADE` e a
§8 pedia "nenhuma linha é apagada"; as duas não cabiam juntas.
