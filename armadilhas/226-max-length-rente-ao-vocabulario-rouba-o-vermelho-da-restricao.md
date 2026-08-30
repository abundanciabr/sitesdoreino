---
schema_version: 2
armadilha: 226
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir "o max_length é apertado por decisão de armazenamento" de "o max_length é apertado por acidente e está encobrindo a restrição"; medir exigiria comparar o tamanho da coluna com o maior valor de um vocabulário QUE NEM SEMPRE É uma TextChoices, e o falso vermelho cairia justamente em campos legítimos de tamanho fixo (hash, sigla, código de país)
sinal:
  - `value too long for type character varying`
  - `DataError` num teste que espera `IntegrityError`
---

# O `max_length` rente ao vocabulário rouba o vermelho da `CheckConstraint`, e a proibição some no dia em que alguém alargar a coluna

**Sintoma.** Você escreveu a decisão do projeto como restrição de banco, do jeito
certo, e o teste que prova que ela morde falha por um motivo que não tem nada a
ver com ela:

```
E   django.db.utils.DataError: value too long for type character varying(7)
FAILED tests/test_modelo_de_dados.py::test_o_banco_recusa_uma_liga_diamante
```

O teste esperava `IntegrityError` com o nome da restrição
(`tier_de_liga_e_um_dos_quatro`). O que veio foi `DataError`: a palavra
`diamante` tem 8 letras e a coluna tinha 7. **A linha proibida nem chegou a ser
avaliada pela restrição.**

**Causa.** `max_length` de um campo com vocabulário fechado costuma nascer
"justo" — o tamanho da maior escolha existente. É o reflexo natural: `bronze`,
`prata`, `ouro`, `platina` cabem em 7, então 7 parece o número certo. Só que a
partir daí quem recusa um valor inventado é o **tamanho da coluna**, e não a
lei; e o tamanho da coluna:

| | a restrição nomeada | o `max_length` justo |
|---|---|---|
| **mensagem** | `tier_de_liga_e_um_dos_quatro` | `value too long for varchar(7)` |
| **diz qual lei foi violada?** | sim | não |
| **sobrevive a uma escolha nova legítima?** | sim (migração explícita) | **não — some junto** |

A terceira linha é o estrago de verdade. No dia em que alguém acrescentar uma
liga chamada `esmeralda` (9 letras), a migração vai alargar a coluna para caber
— e nesse instante `diamante` passa a caber também, **sem que ninguém tenha
tocado numa restrição**. A proibição não é revogada: ela evapora como efeito
colateral de uma mudança que parecia inofensiva. É a `RETROSPECTIVA-FASE-D` §2
(garantia sem mecanismo) com um agravante: aqui a garantia PARECIA ter mecanismo.

E o mesmo laço acontece com um teste de SQL cru contra vocabulário fechado
(`origem`, `tipo`, `status`): o valor inventado que você escolhe para provar a
recusa tende a ser mais descritivo — e mais longo — que os legítimos.

**A conexão com `armadilhas/195`:** este é o caso irmão. Lá, o vermelho morria
na construção do teste; aqui, ele morre no tamanho da coluna. Nos dois, o
`FAILED` é honesto e a prova não vale — e no caso do `max_length` o engano é
pior, porque o teste PASSA depois que você troca `diamante` por uma palavra mais
curta, e você segue em frente achando que provou a lei.

**Solução: `max_length` FOLGADO em todo campo cuja lei é uma restrição nomeada.**

```python
class Tier(models.TextChoices):
    BRONZE = "bronze", "Bronze"
    PRATA = "prata", "Prata"
    OURO = "ouro", "Ouro"
    PLATINA = "platina", "Platina"

# O `max_length` é FOLGADO de propósito, e a folga é a decisão. Rente ao maior
# valor, quem recusaria um valor inventado seria o TAMANHO da coluna, com um
# `DataError` genérico — e a proteção evaporaria no dia em que alguém alargasse
# a coluna por outro motivo. Com folga, quem recusa é a restrição NOMEADA, e a
# mensagem do banco diz qual lei foi violada.
tier = models.CharField(max_length=16, choices=Tier.choices)

# ...
models.CheckConstraint(
    condition=models.Q(tier__in=["bronze", "prata", "ouro", "platina"]),
    name="tier_de_liga_e_um_dos_quatro",
)
```

A régua prática, em uma frase: **se existe uma `CheckConstraint` nomeada
guardando o vocabulário daquela coluna, o `max_length` não é uma trava — é só
armazenamento, e deve ser generoso o bastante para nunca disputar o papel de
quem recusa.** Onde não há restrição nomeada (um `slug`, um `hash`, uma sigla de
duas letras), o `max_length` justo continua certo: ali ele é a especificação, e
não um guarda acidental.

**E a asserção do teste tem de citar o nome da restrição**, nunca só "levantou
alguma exceção":

```python
assert "tier_de_liga_e_um_dos_quatro" in str(erro.value)
```

Com `pytest.raises(IntegrityError)` sozinho, o `DataError` teria falhado o teste
(ele não é `IntegrityError`) — mas com um `pytest.raises(Exception)` genérico,
ou com um `except` largo, o teste ficaria **VERDE pelo motivo errado**, e a
proibição seria uma ficção com prova.

**Origem.** 30/08/2026, TAR-035 (as tabelas da gamificação e os três
testes-invariante da economia, PR #636). Duas colunas caíram na mesma armadilha
no mesmo instante: `LigaDefinicao.tier` (`max_length=7`, contra `diamante`, que
a lei do projeto PROÍBE nominalmente) e `MovimentoDeCristais.origem`
(`max_length=18`, contra `compra_com_dinheiro`, que é a origem de Cristal que o
primeiro invariante da economia existe para tornar impossível). As duas leis são
das mais sérias daquela célula, e as duas estavam sendo "provadas" por um limite
de `varchar`.
