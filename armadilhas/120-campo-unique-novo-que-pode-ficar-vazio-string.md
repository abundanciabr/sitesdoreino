# Campo `unique` novo que pode ficar vazio: `default=""` colide, `NULL` não — e a colisão precisa de savepoint

**Sintoma:** você acrescenta a um model uma coluna `unique=True` cujo valor vem
de fora (o id da pessoa em outra célula, um `external_id`, o número do pedido no
provedor) e que **nem sempre chega**. Duas formas do mesmo erro:

```
django.db.utils.IntegrityError: duplicate key value violates unique constraint
  "sugestoes_identidade_id_da_plataforma_key"
DETAIL:  Key (id_da_plataforma)=() already exists.
```

- no `migrate`, se o campo nasceu com `default=""`: o `AddField` morre na
  **segunda** linha que já existia na tabela;
- em produção, num `create()`/`save()` comum: a segunda pessoa cujo valor não
  veio derruba a requisição — e, no meio de um `transaction.atomic()`, o erro
  seguinte é ainda mais confuso, porque não fala de unicidade nenhuma:
  `TransactionManagementError: An error occurred in the current transaction. You
  can't execute queries until the end of the 'atomic' block.`

**Causa:** são duas, e resolver só a primeira deixa a segunda de pé.

1. **No Postgres, `NULL` não é igual a `NULL`** — um índice único aceita mil
   linhas nulas. String vazia é um valor de verdade: `''` colide com `''` na
   segunda ocorrência. Ou seja: `null=True` e `default=""` **não** são duas
   grafias do mesmo "vazio"; a escolha decide se a migration sobe sobre uma
   tabela que já tem gente dentro.
2. **Um `IntegrityError` engolido dentro de um bloco atômico envenena a
   transação inteira.** O Django não desfaz nada sozinho por causa de um `except`
   seu: qualquer consulta seguinte na mesma transação levanta
   `TransactionManagementError`. O `try/except` que parecia "tratar o caso raro"
   vira 500 numa linha de código que não tem nada a ver com o campo novo.

**Solução — as duas metades, juntas.**

```python
# 1. NULL é o "ainda não sei" (e é o que deixa o AddField subir sobre a tabela
#    cheia); o CheckConstraint fecha o SEGUNDO jeito de não saber, para que a
#    coluna tenha uma forma só de vazio.
id_externo = models.CharField(max_length=64, null=True, unique=True)

class Meta:
    constraints = [
        models.CheckConstraint(
            condition=~models.Q(id_externo=""),
            name="tabela_id_externo_nunca_vazio",
        ),
    ]

# 2. Normalize na BORDA: "", "   " e None viram um None só.
valor = (resposta.get("id") or "").strip() or None

# 3. E engula a colisão dentro de um SAVEPOINT — nunca solta no atomic de fora.
try:
    with transaction.atomic():          # <- o savepoint é isto
        linha.save(update_fields=["id_externo"])
except IntegrityError:
    linha.refresh_from_db(fields=["id_externo"])
    logger.warning("id externo %s ja pertence a outra linha; segue sem ele", valor)
```

**A colisão não é hipótese exótica:** o valor vem de outra célula, e a pessoa que
troca de e-mail lá vira uma linha nova aqui com o **mesmo** id externo. Se a sua
coluna é dado a mais (não a chave de recuperação), a resposta certa é registrar e
seguir — derrubar a porta por causa de um dado que você acabou de passar a
coletar pune quem não tem como resolver o problema.

**E há DOIS caminhos de escrita, não um.** `get_or_create(..., defaults={...})`
estoura no `INSERT`; a gravação da reentrada estoura no `UPDATE`. Um `try` só, no
lugar errado, deixa metade das pessoas vendo 500 — aqui isso foi achado por um
teste parametrizado (`["cunhagem", "reentrada"]`), e a metade que faltava era a
do `INSERT`.

**Como medir antes de confiar:** troque `null=True` por `blank=True, default=""`
no model **e na migration** (estado coerente — model sem migration dá ERROR, não
FAIL: `armadilhas/080`) e rode a suíte com `--create-db`. Na célula `sugestoes`
isso derrubou **20 testes**, quase todos de fixtures que criam duas pessoas.

**Origem:** Fase 1 do plano de notificações (`sugestoes`, `Identidade.id_da_plataforma`),
25/08/2026 — as duas metades medidas por mutação antes de o PR abrir.
