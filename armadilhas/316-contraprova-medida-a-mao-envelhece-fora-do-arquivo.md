---
schema_version: 2
armadilha: 316
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: CI
  dono: ci/tests/test_indice_com_a_origem.py
---

# A contraprova de um `is None` medida à mão envelhece fora do arquivo: em quatro horas o número já estava errado

**Sintoma.** Nada quebra e nada avisa. Um guarda de ausência passa verde para
sempre, e o número que provava que ele guardava alguma coisa está errado:

```python
def test_clone_sem_a_ref_da_origem_tambem_e_nao_medi(casa):
    outra = casa["outra"]
    _git(outra, "remote", "rename", "origin", "espelho")
    assert indice.coletar_da_origem(outra) is None   # ← e o outro lado, cadê?
    assert indice.caminhos_da_origem(outra) is None
```

O teste inteiro é ausência. Ponha `return None` na primeira linha das duas
funções e ele continua verde, sem uma palavra. Medido em 04/09/2026: as duas
sabotagens passaram, uma de cada vez.

**Causa.** A contraprova FOI medida, e bem: quem escreveu o teste rodou a
função no mesmo clone antes do `remote rename`, viu que ela devolvia entradas,
e escreveu isso no relatório final. Só que o relatório não roda. A medição
virou prosa, e prosa não reprova nada.

Pior: **ela já estava errada quando alguém foi conferir, no mesmo dia.** A nota
dizia "devolve 1 entrada"; a medição de dentro do arquivo, quatro horas depois,
disse duas (a 001 que veio do clone e a 002 que aquele clone acabou de
empurrar). Ninguém mentiu — a fixture tem duas entradas do lado da origem, e a
lembrança guardou uma. É esse o ponto: número guardado fora do arquivo não é
compromisso, é lembrança, e lembrança apodrece sem fazer barulho.

Isto é `RETROSPECTIVA-FASE-D` §2 aplicado à própria prova: garantia sem
mecanismo. A `armadilhas/266` já mandava quebrar o código de propósito para
descobrir se o guarda guarda; o que faltava dizer é **onde o resultado dessa
quebra tem de morar**.

**Solução.** A contraprova vai para dentro do mesmo teste, ANTES do fato que
causa a ausência, com o único fato que muda entre as duas medições anotado em
voz alta:

```python
    # A CONTRAPROVA: com a ref no lugar, as duas funções MEDEM de verdade.
    antes = indice.coletar_da_origem(outra)
    assert antes is not None, "contraprova: com `origin/main` no lugar, mede-se"
    assert [e.nome for e in antes] == ["001-primeira.md", "002-segunda.md"]

    # O ÚNICO fato que muda daqui para baixo: a ref some deste clone.
    _git(outra, "remote", "rename", "origin", "espelho")

    assert indice.coletar_da_origem(outra) is None
```

Com isso a sabotagem reprova na linha da contraprova, com a mensagem certa.

**A régua, em uma frase:** se o seu `assert ... is None` (ou `== []`, ou `== 0`)
não tem, no MESMO arquivo, a linha que mostra o valor diferente de `None` no
mesmo cenário, ele ainda não é um guarda. E a régua tem um teste barato: leia o
arquivo fingindo que a função devolve `None` sempre. Se nada fica vermelho, a
contraprova está faltando.

**Onde isso NÃO se aplica:** um `is None` cercado de medição positiva no mesmo
teste (o valor que sobrou, a mensagem que saiu no `stderr`) já tem o outro lado
por perto. O caso desta entrada é o teste que só afirma ausências.

**Origem.** 04/09/2026, TAR-139 (PR desta entrada). A ponta foi DECLARADA em voz
alta pela sessão da TAR-050 (PR #973) no relatório final dela, virou tarefa na
fila em vez de morrer no relatório, e a tarefa achou o número errado. Declarar o
que ficou por fazer é o comportamento certo; o que não pode é a declaração ser o
único lugar onde a prova existe.
