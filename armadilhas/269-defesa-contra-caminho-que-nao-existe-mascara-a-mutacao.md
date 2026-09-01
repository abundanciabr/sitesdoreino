---
schema_version: 2
armadilha: 269
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir "esta defesa protege de um caminho real" de "esta defesa protege de um caminho imaginário" — a diferença mora fora do arquivo, na resposta a `grep` por quem mais escreve aquele modelo. O que existe é o rito da mutação deliberada (RITOS §2 peça 3), que ACHA o caso; este arquivo é o que diz o que fazer quando ele acha.
sinal:
  - mutação deliberada que continua verde num código sem `if` nenhum errado
  - dois trechos da mesma função produzindo o mesmo valor
  - "defensivo, para o caso de"
---

# A sua mutação continua verde porque o código de produção conserta a mutação: a defesa contra um caminho que não existe é a segunda causa suficiente

**Sintoma.** Você fez tudo certo. Escreveu o guarda, ficou verde, e foi provar
por mutação. Apaga a regra, roda o teste, e ele **passa**:

```
FALSO-VERDE      5. abrir: nasce com o medidor zerado
                 o teste PASSOU com a regra apagada:
                 tests/test_forja.py::test_abrir_ja_conta_a_primeira_tentativa
```

Você reabre o teste procurando o cenário pobre da `armadilhas/267` e não acha:
o cenário está completo, a asserção é direta, o valor conferido é o valor certo.
O teste não tem defeito nenhum. **O defeito está no código de produção**, e ele
não é um bug: é uma linha a mais, escrita com boa intenção.

**Causa.** A função tinha DUAS coisas produzindo o mesmo resultado:

```python
forja, _ = Forja.objects.get_or_create(
    pessoa=pessoa, site_id=site_id, desafio_ref=chave,
    defaults={"medidor": 1},                 # (1) o valor de nascimento
)
if forja.medidor == 0 and forja.teto > 0 and forja.selada_em is None:
    # "Linha nascida por outro caminho (um reparo, uma importação) chega
    #  aqui com o medidor zerado."
    forja.medidor = 1                        # (2) o conserto do zero
    forja.save(update_fields=["medidor", "atualizada_em"])
```

Trocar `(1)` por `defaults={"medidor": 0}` não muda nada observável, porque
`(2)` conserta a mutação no mesmo instante. O guarda existia, tinha nome
descritivo, cobria a linha, e não conseguia reprovar a única coisa que ele
existia para reprovar.

E o pior: **o caminho de que `(2)` defendia não existe.** Uma linha de `grep`
resolve a dúvida, e ela devolveu vazio:

```
$ grep -rn "Forja.objects.create\|Forja(" --include=*.py apps/
apps/gamificacao/models.py:948:class Forja(models.Model):
```

Nada mais na célula escreve aquele modelo. A defesa protegia de um "outro
caminho" que só existia na imaginação de quem a escreveu, e o preço dela não foi
a linha extra: foi ter cegado o guarda.

**Por que isto não é a `armadilhas/267`.** Lá o cenário do teste era pobre — o
teste executava a regra sem exercitar a distinção. Aqui o teste é impecável e o
CÓDIGO é que tem duas expressões da mesma regra. A pista para separar os dois é
o lugar em que você procura o erro: se o teste parece certo, pare de reescrever
o teste e vá contar quantos trechos da função produzem aquele valor.

**Solução — apague a segunda causa, não some uma terceira.**

A tentação é escrever um teste mais esperto (espionar qual dos dois caminhos
gravou). Ela está errada: um teste que distingue dois caminhos que produzem o
mesmo resultado está travando a IMPLEMENTAÇÃO, não a regra. O conserto é tirar a
redundância do código:

```python
forja, _ = Forja.objects.get_or_create(
    pessoa=pessoa, site_id=site_id, desafio_ref=chave,
    defaults={"medidor": 1},
)
return forja
```

E escrever na docstring **por que** não há defesa ali, com o custo medido — sem
isso, a próxima sessão põe a defesa de volta por zelo, e o guarda cega outra vez.

**A régua, em uma pergunta:** antes de escrever `if` defensivo contra um estado
"que pode vir de outro caminho", rode o `grep` que responde **quem mais escreve
isto**. Vazio ⇒ a defesa não protege de nada e pode cegar um guarda. É a
`RETROSPECTIVA-FASE-D` §1 (falso-verde) encontrando a §2 (garantia sem
mecanismo) pelo lado de dentro: a garantia existia, o mecanismo estava
anestesiado por código bem-intencionado.

**Onde isto foi medido:** 01/09/2026, na entrega da Forja (PR #836, TAR-099).
Das 18 mutações do despacho, 17 ficaram vermelhas de primeira e essa foi a
única verde. Ela levou quatro minutos para ser diagnosticada e uma linha para
ser curada — mas só porque a mutação foi rodada. Sem esse passo, o guarda teria
entrado na `main` verde, com nome bonito, guardando nada.
