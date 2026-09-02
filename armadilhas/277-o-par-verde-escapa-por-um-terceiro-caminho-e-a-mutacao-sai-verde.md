---
schema_version: 2
armadilha: 277
estado: documentada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhuma ferramenta sabe qual saída de uma função o seu cenário exercitou — a cobertura de linhas fica IDÊNTICA nas duas versões, porque a linha do `return None` é executada nos dois casos, só que por motivos diferentes. Um portão que exigisse "um par verde por guard clause" teria de adivinhar quais `return` são saídas de regra e quais são fluxo normal, e reprovaria prova honesta. A defesa é o rito da mutação (RITOS §2 peça 3) somado à leitura deste arquivo quando ela sai VERDE.
sinal:
  - mutação deliberada que sai VERDE num par verde que você acabou de escrever
  - regra escrita, teste escrito, e a mutação não acusa nenhum dos dois
  - guard clause cuja condição nunca foi verdadeira em teste nenhum
---

# A mutação saiu verde, e o culpado não é o guarda: é o seu PAR VERDE, que escapa por um terceiro caminho

**Sintoma.** Você escreveu um detector com várias saídas — o padrão comum de
`guard clauses` — e escreveu os dois testes que o rito pede: o caso que ele
precisa acusar e o **par verde**, o vizinho legítimo que ele precisa deixar
passar. Os dois ficam verdes. Aí você faz a prova por mutação e desfaz uma das
saídas:

```
[FURO] M6 D1: sem a saída pela presença forte
       VERDE com a regra desfeita — test_d1_nao_acusa_quando_o_teste_prova_que_a_coisa_acontece
[FURO] M7 D1: `any` no lugar de `all`
       VERDE com a regra desfeita — test_d1_nao_acusa_quando_o_teste_prova_que_a_coisa_acontece
```

Duas regras diferentes, arrancadas separadamente, e o mesmo par verde não
acusou nenhuma das duas.

**Causa.** A função tinha TRÊS saídas, e o seu corpus escapava pela terceira:

```python
def d1(bloco):
    asserts = _asserts(bloco)
    if not asserts:
        return None                                   # saída A
    if any(_tem_presenca_forte(l.texto) for l in asserts):
        return None                                   # saída B  ← mutada
    if not all(_e_ausencia(l.texto) for l in asserts):
        return None                                   # saída C  ← o corpus saía por aqui
    return Achado(...)
```

O par verde tinha uma asserção comum (`assert nivel == 7`), então ele **nunca
chegava** à saída B: a C já o mandava embora. Desfazer a B não mudava nada, e
desfazer a C também não, porque o corpus saía pela C com folga — trocar `all`
por `any` continuava dando o mesmo destino para aquele cenário específico.

**E a mutação revelou uma segunda coisa, pior:** a saída B era **inalcançável**.
Ela procurava `.assert_called_once()` entre os `assert` — e
`rota.assert_called_once()` não começa com a palavra `assert`, então nunca
entrava na lista. A regra existia, estava escrita, tinha comentário explicando o
porquê, e **nunca rodou uma vez**. Regra que nunca roda é enfeite com cara de
proteção (RETROSPECTIVA-FASE-D §2: garantia declarada sem mecanismo apodrece).
Sem a mutação, ela teria vivido para sempre — nada fica vermelho por causa de um
`if` cuja condição é sempre falsa.

**Por que ninguém percebe sozinho.** É a `armadilhas/267` um andar acima. Lá, o
cenário do teste tinha um lado só do filtro; aqui, o corpus do par verde tem um
caminho só de uma função com vários. Nos dois casos o teste existe, tem nome
descritivo, cobre a linha e passa — e a **cobertura de linhas é idêntica** nas
duas implementações, porque a linha `return None` é executada nas duas, só que
por motivos diferentes. Nenhuma ferramenta distingue "voltou por B" de "voltou
por C".

E há a leitura errada que quase sempre vem primeiro: a mutação verde parece
dizer *"meu detector é fraco"*. Não é isso. O detector pode estar perfeito; o
que falhou foi o **cenário escolhido para prová-lo**.

**Solução: um par verde por SAÍDA, não um par verde por detector.** Antes de
escrever o corpus, conte os `return` da função e pergunte, para cada um, qual
cenário sai por ali. Depois nomeie cada corpus pela saída que ele exercita —
o nome é o que impede a fusão preguiçosa dos dois seis meses depois:

```python
@pytest.mark.parametrize(
    "patch",
    [
        pytest.param(LIMPO_POR_PRESENCA, id="tambem-afirma-presenca"),        # saída C
        pytest.param(LIMPO_POR_PRESENCA_FORTE, id="prova-que-a-chamada-acontece"),  # saída B
    ],
)
def test_nao_acusa_quando_o_teste_prova_que_a_coisa_acontece(patch):
    assert _codigos(patch) == []
```

Com os dois, as duas mutações reprovam, e cada vermelho nomeia o parâmetro que
caiu — que é o que a `armadilhas/268` exige para uma mutação valer alguma coisa.

**A régua que generaliza:** *uma função com N saídas precisa de N cenários, e um
cenário só prova a saída por onde ele efetivamente passou.* Vale para todo
`guard clause`, todo `early return`, toda cadeia de `elif` — e vale em dobro
quando você escreveu as saídas em ordem, porque a primeira que casar esconde
todas as seguintes.

**O truque barato para descobrir isso em dez segundos**, e que teria evitado as
duas: ponha um `raise AssertionError("cheguei aqui")` na saída que você acha que
o corpus exercita e rode o teste. Se ele continuar verde, o corpus nunca passou
por ali — e o seu par verde está provando outra coisa.

**Origem.** 02/09/2026, TAR-006 (o revisor de pouso, PR #849, recomendação B11
do `PLANO-MESTRE-ROBOS-SEM-COLISAO`). Treze mutações deliberadas; onze
reprovaram de primeira, e as duas que saíram verdes eram as duas saídas do mesmo
detector. A ironia útil: o detector que elas quase deixaram passar quebrado é
justamente o que existe para achar asserção com mais de uma causa suficiente
(`armadilhas/266`) — a doença mordeu o remédio.
