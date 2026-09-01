---
schema_version: 2
armadilha: 265
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: services/forum/tests/test_etiqueta_de_nivel.py
sinal:
  - `CheckConstraint` que já garante a mesma coisa que o `if`
  - teste de regra de produto que continua verde com a regra apagada
---

# A regra de produto passa no teste por herança de uma `CheckConstraint`, e apagá-la não deixa nada vermelho

**Sintoma.** Você escreve uma regra de produto em código, com todas as letras
("fala publicada em nome da escola nunca recebe etiqueta de nível"), escreve o
teste que a prova pela tela, roda, verde. Depois **apaga a regra do código** por
curiosidade, roda a suíte inteira de novo, e ela continua **verde**.

Medido em 01/09/2026, no PR #828 (`forum`). O código era:

```python
ids = [
    m.autor_id for m in mensagens
    if m.autor_id and not m.publicado_pela_escola      # <- a regra
]
```

Apagando `and not m.publicado_pela_escola`, a suíte de 15 testes ficou
`15 passed`. Inclusive o teste chamado
`test_fala_publicada_pela_escola_nao_recebe_etiqueta`, escrito de propósito para
aquilo.

**Causa.** A condição da esquerda (`m.autor_id`) já esconde a etiqueta sozinha,
**porque o banco garante que as duas andam juntas**:

```python
models.CheckConstraint(
    condition=(
        models.Q(autor__isnull=False, publicado_pela_escola=False)
        | models.Q(autor__isnull=True, publicado_pela_escola=True)
    ),
    name="mensagem_de_pessoa_ou_da_escola",
)
```

Fala da escola tem autor **nulo**, por restrição. Então todo teste que cria a
linha pelo ORM prova a *restrição*, nunca a *regra*. O teste está medindo o
banco e dando o crédito ao código.

A restrição é ótima e não é o problema. O problema é que ela **não foi escrita
para proteger esta regra** — ela existe para impedir duas mentiras sobre quem
falou. No dia em que alguém a afrouxar por outro motivo (uma tela de
administração, um caso novo de publicação institucional), a regra de produto
desaparece junto, em silêncio, e nenhum guarda pisca.

É a família do **falso-verde por cenário fraco** (`RETROSPECTIVA-FASE-D` §1): o
teste mede o mundo em que a mudança é trivial, e o mundo que importa é o outro.
A parenta mais próxima no catálogo é a `armadilhas/261` (teste de ordem com
dados que já vêm na ordem certa): ali o dado, aqui o esquema.

**Solução — medir a regra numa combinação que o banco recusa, SEM ir ao banco.**
O objeto em memória basta, porque a função só lê os atributos:

```python
def test_a_bandeira_da_escola_sozinha_ja_tira_a_etiqueta(porta, ana):
    # NÃO é salvo: a restrição recusaria esta combinação, e é justamente ela
    # que precisa ser provada sem depender da restrição continuar existindo.
    da_escola = Mensagem(autor=ana, publicado_pela_escola=True, texto="oficial")
    de_pessoa = Mensagem(autor=ana, publicado_pela_escola=False, texto="normal")

    motor.decorar([da_escola, de_pessoa])

    assert da_escola.etiqueta is None
    assert de_pessoa.etiqueta is not None
```

Com este teste, apagar a regra deixa **exatamente um** teste vermelho. Provado
na mesma sessão, nos dois sentidos.

**A régua de bolso, para não precisar reler isto.** Sempre que uma condição de
produto tiver a forma `if A and B`, pergunte: *existe alguma restrição de banco,
`unique`, `null=False` ou default que já force `A` e `B` a andarem juntas?* Se
existe, o seu teste de tela prova uma delas e presenteia a outra. A outra precisa
de um teste de unidade com a combinação impossível — e o comentário dizendo por
que ele não vai ao banco, senão o próximo agente "conserta" o teste salvando a
linha.

**E o método que achou isto, que vale mais que o caso.** Nada acusou: `black`,
`make ci`, `freeze-de-contrato` e as 13 muralhas estavam todos verdes com o
guarda furado. O que achou foi **mutação deliberada**, um guarda de cada vez,
depois de a suíte ficar verde: alterar o código de propósito e exigir ver o
vermelho. Foram 8 mutações naquele PR; **duas** passaram verdes na primeira
tentativa e viraram testes melhores (esta e a da validação de `nivel`, que o
caso de teste escolhido não isolava). Suíte que nunca foi vista vermelha não é
suíte: é decoração que passa.

**Origem:** PR #828, `forum`, 01/09/2026, Lote A da gamificação (degrau 18).
