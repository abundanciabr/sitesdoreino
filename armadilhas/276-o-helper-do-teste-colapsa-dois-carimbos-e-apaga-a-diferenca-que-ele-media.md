---
schema_version: 2
armadilha: 276
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir "este helper colapsa dois conceitos" de "este helper tem um padrão conveniente"; medir exigiria adivinhar quais parâmetros do código sob teste são conceitualmente distintos, e o falso vermelho cairia em todo helper legítimo com default. A defesa é o rito que já existe (RITOS §2 peça 3, mutação deliberada depois de verde) apontada para o carimbo, e este arquivo é o que diz onde apontá-la.
sinal:
  - asserção comparando dois `datetime` que o helper fez iguais
  - teste de reagendamento que passa com o reagendamento apagado
---

# O helper do teste colapsa dois carimbos num parâmetro só, e apaga exatamente a diferença que o teste existia para medir

**Sintoma.** Você escreveu o helper honesto, com a assinatura mais curta, e o
teste que prova a distinção entre dois carimbos de tempo falha por um motivo que
não é o defeito:

```
assert liberada.enviado_em == as_horas(9, dia=16)
E  AssertionError: assert datetime(2026, 9, 15, 11, 0, ...) == datetime(2026, 9, 16, 9, 0, ...)
```

O código estava certo. O teste é que não conseguia dizer o que queria dizer.

**Causa.** O helper tinha um parâmetro só onde o código sob teste tem dois:

```python
def entregar(veredito, inscricao, passo, momento, canal="sino"):
    return regua.registrar(
        ...,
        previsto_para=momento,   # <- quando o passo ERA para sair
        momento=momento,         # <- quando ele SAIU
    )
```

Os dois valores coincidem no caminho feliz, e é por isso que o colapso parece
inofensivo enquanto você escreve o helper. Ele deixa de ser inofensivo no
primeiro teste que existe **justamente porque os dois divergem**: o passo era
para as 11h de ontem e saiu às 9h de hoje, depois de a régua reagendar.

**E a versão perigosa deste erro não falha: ela fica verde.** Aqui o vermelho
apareceu porque a asserção esperava o valor certo. Se ela tivesse sido escrita
a partir do que o helper produz (`assert enviado_em == as_horas(11)`, "para
casar"), o teste passaria — e passaria também com o reagendamento inteiro
apagado, porque nunca houve dois valores para comparar. Um teste que só pode
observar um valor não consegue afirmar nada sobre dois.

**A regra que sai disto:** quando o código sob teste separa dois campos de
propósito, **o helper não pode juntá-los**. Um default é aceitável (`previsto_para=None`
significando "igual ao momento"); um parâmetro só, não.

```python
def entregar(veredito, inscricao, passo, momento, canal="sino", previsto_para=None):
    return regua.registrar(
        ...,
        previsto_para=previsto_para if previsto_para is not None else momento,
        momento=momento,
    )
```

**Como reconhecer antes de doer.** Se o documento de desenho se dá ao trabalho
de explicar por que são dois campos e não um, esse é o aviso. No caso que gerou
esta entrada, o plano tinha um parágrafo inteiro chamado *"os cinco carimbos de
tempo, e por que não basta um"* — e o helper juntou dois deles na primeira
linha de teste escrita depois de lê-lo.

**A conexão com `armadilhas/267`:** é a mesma família de falso-verde por cenário
que não exercita a regra, vista de outro ângulo. Lá o cenário só tinha o caso
que sobrevive ao filtro; aqui o cenário não consegue nem produzir os dois
valores. A defesa é a mesma e continua sendo a melhor que existe: mutação
deliberada depois do verde.

**Origem:** TAR-072, a régua anti-chateação das jornadas
(`services/mensageria/apps/jornadas/regua.py`).
