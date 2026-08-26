# Um `Sum` ao lado de `Count(distinct=True)` no mesmo `annotate` sai multiplicado — e é o `distinct` do vizinho que faz você não desconfiar

**Sintoma:** uma consulta que já agrega DUAS relações resolve tudo certo há
meses. Você acrescenta um terceiro número, dessa vez uma soma, na mesma linha:

```python
Sugestao.objects.annotate(
    total_votos=Count("votos", distinct=True),        # já estava, e está certo
    total_comentarios=Count("comentarios", distinct=True),  # já estava, e está certo
    calor=Sum(Case(When(votos__criado_em__gte=corte, then=3), default=0)),  # novo
)
```

O `calor` sai **multiplicado pelo número de comentários** da sugestão. Uma ideia
com 1 voto recente e 3 comentários pontua 9 em vez de 3; a mesma ideia sem
comentário nenhum pontua 3. **Nada reprova**: o número continua plausível, o
ranking continua ordenando, e a página continua bonita. O sintoma real é de
produto — o ranking passa a premiar quem tem thread comprido.

**Causa:** os dois `JOIN` produzem o **produto cartesiano** das duas pernas. Uma
sugestão com 2 votos e 3 comentários vira **6 linhas** antes do `GROUP BY`, e
cada voto aparece 3 vezes. A documentação do Django avisa disso em
[*Combining multiple aggregations*](https://docs.djangoproject.com/en/5.1/topics/db/aggregation/#combining-multiple-aggregations),
e o remédio que ela dá — `distinct=True` — **só existe para `Count`**.

E é aí que está a parte cara. O `distinct=True` dos vizinhos **funciona**, então
o código à sua frente parece a prova viva de que "aqui a junção está resolvida".
Quem escreve a linha nova copia o padrão que está do lado e conclui que basta
somar o `distinct`. Mas:

* `Count(x, distinct=True)` conta **valores distintos de x** — e como cada linha
  de voto tem `id` próprio, isso é exatamente o que se queria;
* `Sum(x, distinct=True)` também soma **valores distintos**, que é uma pergunta
  **diferente**: três votos que valem 3 cada somariam 3, não 9. Trocar um erro
  por outro.

Ou seja: não existe versão do `Sum` que sobreviva à junção dupla. A correção não
é um argumento — é mudar de lugar.

**Solução — tire a soma da junção, com uma subconsulta correlacionada:**

```python
Coalesce(
    Subquery(
        Voto.objects.filter(sugestao=OuterRef("pk"))
        .order_by()                    # armadilhas/115: Meta.ordering entra no GROUP BY
        .values("sugestao")
        .annotate(calor=Sum(degraus))
        .values("calor")[:1],
        output_field=IntegerField(),
    ),
    Value(0),                          # sem votos ⇒ 0, e não NULL (ver abaixo)
    output_field=IntegerField(),
)
```

Continua **uma** consulta ao banco: `assertNumQueries` não muda, e o número não
depende mais de nada que a consulta de fora venha a juntar depois. As duas linhas
que parecem detalhe e não são:

* **`.order_by()` vazio** — sem ele, um `Meta.ordering` no model entra no
  `GROUP BY` e a subconsulta devolve uma linha por voto (`armadilhas/115`).
  Escreva-o mesmo quando o model de hoje não tiver ordering: o custo é zero e o
  dia em que alguém acrescentar um, ninguém vai lembrar de voltar aqui.
* **`Coalesce(..., 0)`** — a subconsulta não produz linha para quem não tem voto
  nenhum, e no Postgres `ORDER BY … DESC` põe `NULL` **na frente** de qualquer
  número. Sem o `Coalesce`, uma aba "em alta" abriria mostrando exatamente as
  ideias em que ninguém votou.

**Como pegar isto num teste, já que o resultado costuma sair plausível:** o
guarda tem de existir com a **segunda relação povoada**. Duas linhas com o mesmo
número de votos, uma delas com comentários, e a asserção sobre a ORDEM. Medido
neste projeto: com o `Sum` de volta na junção, **1 teste** ficou vermelho de 8 no
arquivo — todos os outros continuaram verdes porque as suas fixtures não tinham
comentário nenhum. Um arquivo de testes de ranking escrito sem pensar nisso
aprova a versão errada inteira.

**Regra que generaliza:** `distinct=True` num `Count` vizinho **não é evidência
de que a junção está resolvida para a linha que você está escrevendo**. Toda vez
que um `annotate` tocar mais de uma relação, pergunte de qual perna cada número
vem — e se algum deles não for um `Count`, tire-o da junção.

**Origem:** V1.2 da Caixa de Sugestões (a aba "Em alta", com peso de recência),
25/08/2026 — o `Sum(Case(...))` do calor foi escrito ao lado de dois
`Count(distinct=True)` que já estavam certos há três despachos. Ver também
`armadilhas/115`, do mesmo modelo de dados e da mesma família.
