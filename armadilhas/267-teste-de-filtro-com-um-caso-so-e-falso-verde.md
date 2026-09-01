---
schema_version: 2
armadilha: 267
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhuma ferramenta acusa cenário incompleto — o teste existe, tem nome descritivo, cobre a linha e passa, e a cobertura é IDÊNTICA nas duas implementações porque as duas executam o mesmo trecho; um portão que exigisse "dois casos por teste de filtro" teria de adivinhar quais testes são de filtro e reprovaria prova honesta. A defesa é o rito que já existe (RITOS §2 peça 3: mutação deliberada depois de verde), e este arquivo é o que diz onde apontá-la.
sinal:
  - `1 passed` com a regra apagada
  - teste de filtro que não distingue incluir de excluir
---

# O teste do seu filtro passa com a regra apagada, porque o cenário tem só o caso que sobrevive ao filtro

**Sintoma.** Você escreveu um filtro cuja regra é sutil (excluir quem *só* tem a
situação X, e não excluir cada linha X), escreveu o teste que descreve
exatamente essa sutileza, e ele ficou verde. Depois, na prova por mutação, você
troca a regra pela versão errada e o teste **continua verde**:

```
MUTACAO 2 - alunos: filtrar LINHA a linha em vez de por PESSOA
  [esperado VERMELHO] 1 passed, 16 deselected in 0.30s
```

O teste tinha uma docstring impecável explicando por que a distinção importa. A
docstring estava certa; o cenário é que não a exercitava.

**Causa.** O cenário só tinha a pessoa que **sobrevive** ao filtro:

```python
_pedido("ana@exemplo.test", RECUSADA)
_pedido("ana@exemplo.test", ATIVA)

saida = _rodar(exceto="recusada")

assert "1 pessoa(s)." in saida
assert "ativa (1):" in saida
assert "ficaram de fora, porque só têm pedido recusada (0):" in saida
```

As duas implementações concordam sobre a Ana. Filtrando por linha, a matrícula
recusada some e sobra a ativa; filtrando por pessoa, ela entra porque tem uma
linha fora da exclusão. **Nos dois casos ela aparece, e o grupo "ficaram de
fora" dá zero.** O teste mede um ponto onde as duas curvas se cruzam.

Isto não é descuido de quem escreveu: é a forma normal de escrever um teste. Você
pensa no comportamento que quer garantir ("a Ana continua na lista"), monta a
Ana e mede a Ana. O que falta é a **contraprova no mesmo cenário** — e ela nunca
aparece sozinha, porque a asserção que você já tem passa.

**Solução: todo teste de filtro carrega os DOIS lados na mesma cena.** Quem
sobrevive ao filtro e quem é cortado por ele, juntos, com o grupo dos cortados
conferido por número **e** por nome:

```python
_pedido("ana@exemplo.test", RECUSADA)
_pedido("ana@exemplo.test", ATIVA)
_pedido("dario@exemplo.test", RECUSADA)   # ⟵ o que faltava

saida = _rodar(exceto="recusada")

assert "1 pessoa(s)." in saida
assert "ficaram de fora, porque só têm pedido recusada (1):" in saida
assert "dario@exemplo.test" in saida
```

Com o Dario em cena, a implementação errada esvazia o grupo dos cortados (ela
filtra a consulta inteira, então não sobra ninguém para contar como "ficou de
fora"), e o teste fica vermelho. A regra de bolso: **um filtro tem duas saídas,
e um cenário com uma saída só nunca prova qual delas você implementou.**

**Por que a mutação é a única que pega isto.** Nenhuma ferramenta acusa: o teste
existe, tem nome descritivo, tem docstring, cobre a linha e passa. A cobertura
de linhas fica idêntica nas duas implementações, porque as duas *executam* o
mesmo trecho. Só apagar a regra e olhar o resultado revela que o teste não
estava medindo nada. É o RITOS §2 peça 3 aplicado depois do verde, e é por isso
que ele diz "vermelho **sem** o fix" e não "verde com o fix".

**Onde mais isto mora.** A mesma armadilha espera em qualquer par
incluir/excluir cujo cenário tenha um lado só: uma lista de permissão testada
só com o item permitido, uma checagem de acesso testada só com quem tem acesso,
um `--exceto` testado só com quem escapa dele. Quando o teste afirma uma
distinção, o cenário precisa conter as duas coisas que ele distingue.

**Origem:** despacho da ponte do Fundador (`alunos` + `gamificacao`),
01/09/2026, PR #833. Achado na mutação 2 de oito, e consertado no mesmo PR.
