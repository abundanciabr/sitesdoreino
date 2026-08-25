# `.distinct()` num model com `Meta.ordering` não é distinto pelo que você pediu — e sai certo por acidente

**Sintoma:** você quer as pessoas distintas que comentaram numa sugestão e escreve
o óbvio:

```python
Comentario.objects.filter(sugestao=s).values_list("autor_id", flat=True).distinct()
```

A consulta devolve **uma linha por comentário**, não uma por pessoa. Quem comentou
três vezes aparece três vezes. E o pior: **nada reprova**, porque na maioria dos
usos o resultado ainda sai certo — se você joga o retorno num `set`, num `dict`
ou numa chave de dicionário, a duplicata some antes de alguém notar. O que fica
errado é só o *número de linhas trafegadas* e qualquer `count()` em cima disso.

**Causa:** o Django acrescenta as colunas do `ORDER BY` ao `SELECT DISTINCT`. Com
`Meta.ordering` declarado, isso acontece **sem você escrever `order_by` nenhum**.
Medido em Django 5.1.4, imprimindo o `.query`:

```sql
-- Comentario.Meta.ordering = ["criado_em"]
SELECT DISTINCT "sugestoes_comentario"."autor_id",
                "sugestoes_comentario"."criado_em"   -- ← entrou sozinha
  FROM "sugestoes_comentario"
 ORDER BY "sugestoes_comentario"."criado_em" ASC
```

O distinto passou a ser **pelo par** `(autor, criado_em)`, e `criado_em` é único
por linha — logo o `DISTINCT` não elimina nada. A documentação do Django avisa
disso em `distinct()`, e é uma das armadilhas mais fáceis de ler e não registrar.

**O que torna isto pior do que um bug comum: ele é inconsistente entre models do
mesmo código.** Na mesma célula, medido no mesmo dia:

| Model | `Meta.ordering` | `.distinct()` funciona? |
|---|---|---|
| `Comentario` | `["criado_em"]` | ❌ distinto por par |
| `Voto` | `[]` | ✅ distinto por autor |

Ou seja: a **mesma linha de código**, copiada de um model para o outro, muda de
comportamento — e o autor da cópia não tem por que desconfiar.

**Solução:** limpe a ordenação **antes** do `distinct()`, sempre que o distinto
for por um subconjunto das colunas:

```python
Comentario.objects.filter(sugestao=s).order_by().values_list("autor_id", flat=True).distinct()
```

`.order_by()` sem argumento **zera** o `Meta.ordering` daquela consulta. O SQL vira
o pretendido:

```sql
SELECT DISTINCT "sugestoes_comentario"."autor_id" FROM "sugestoes_comentario"
```

**Como pegar isto num teste, já que o resultado costuma sair certo:** não teste o
valor — **teste o SQL ou o número de linhas**. Um `assertNumQueries` não pega
(a contagem de *consultas* é a mesma); o que pega é imprimir `qs.query`, ou contar
as linhas retornadas contra o número de pessoas esperado. Neste projeto quem
denunciou foi o SQL cru que um teste de volume imprimia — não uma asserção
escrita para isso.

**Regra que generaliza:** `DISTINCT` e `ORDER BY` interagem no SQL, e o
`Meta.ordering` é um `ORDER BY` que você não vê no ponto de uso. Toda vez que
`distinct()` aparecer depois de um `values`/`values_list` parcial, pergunte
**qual é a ordenação implícita daquele model**.

**Origem:** EVO-42 da Caixa de Sugestões (avisar todos os que interagiram com uma
ideia), 25/08/2026, ao montar a lista de destinatários distintos.
