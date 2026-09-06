---
schema_version: 2
armadilha: 358
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe QUAIS restrições de QUAIS células são adiadas, nem se o teste que deveria provar a recusa força a conferência. O CI vê a suíte verde no caso certo e no caso errado, porque a diferença mora dentro de uma transação que nunca commita. O guarda barato que se imagina (achar `Deferrable.DEFERRED` no `models.py` da célula e exigir um `check_constraints()` em algum teste dela) é um falso-verde novo: uma chamada solta em qualquer teste o satisfaz, sem que o teste da recusa a use. O que pega esta classe é o rito da prova por mutação (`RUNBOOK-LOTES.md` §9, lição 3 do Lote A, com a família de entradas 155, 268, 319 e 337 atrás dela), somado à leitura de método da `armadilhas/337`
sinal:
  - DID NOT RAISE .*IntegrityError
  - ERROR at teardown of test_
  - Deferrable\.DEFERRED
---

# 358 — Restrição adiada passa por engano dentro do teste, e o vermelho estoura no desmonte da suíte

**Data:** 05/09/2026 · **Onde:** qualquer célula com `models.UniqueConstraint(...,
deferrable=models.Deferrable.DEFERRED)` e testes de `pytest-django` · **Custo
evitado:** uma rodada inteira de suíte perseguindo um erro de integridade que
apontava para o teste errado, mais um teste-guarda que jurava provar uma recusa
do banco e não provava nada

## Sintoma

Dois sintomas, e o segundo é o caro.

**1. O falso-verde.** O teste que deveria provar que o banco RECUSA o dado
inválido fica verde. Ele fica verde inclusive quando você sabota a restrição de
propósito: apague a chave, regenere a migração, rode de novo, e continua
`1 passed`. Escrito do jeito óbvio, ele é assim:

```python
def test_uma_peca_por_posicao(criar_portfolio, criar_peca):
    portfolio = criar_portfolio("aluno-1")
    criar_peca(portfolio, ordem=1)
    with pytest.raises(IntegrityError):
        criar_peca(portfolio, ordem=1)   # o segundo INSERT não levanta nada
```

**2. O vermelho deslocado.** No dia em que a conferência acontece, o erro de
integridade estoura **no desmonte da suíte**, e o rótulo que o pytest imprime é
o de um teste que não tem nada a ver com a causa:

```
ERROR at teardown of test_qualquer_outra_coisa
django.db.utils.IntegrityError: duplicate key value violates unique constraint
```

Você abre o teste acusado, ele está impecável, e a rodada seguinte se vai
procurando o defeito onde ele não está.

## Causa

**A restrição adiada só é conferida no `COMMIT`, e o teste nunca commita.**

`DEFERRABLE INITIALLY DEFERRED` é uma instrução ao Postgres: *"não confira esta
chave na linha do `INSERT`, confira quando a transação inteira fechar"*. É
exatamente o que se quer para reordenar peças, porque trocar a peça 1 com a
peça 2 passa por um instante em que as duas ocupam a mesma posição, e uma
restrição imediata recusaria esse passo do meio, obrigando a tela a inventar
posições temporárias.

O `pytest-django` roda cada teste **dentro de uma transação que ele desfaz no
fim**, com `ROLLBACK`, para o banco voltar limpo para o teste seguinte. O
`COMMIT` que dispararia a conferência simplesmente nunca acontece.

E o ponto que engana quem já conhece transação aninhada: **um `atomic()` de
dentro não resolve.** Transação aninhada no Django não é transação de verdade,
é um marcador de posição chamado `SAVEPOINT`, e fechá-lo é um
`RELEASE SAVEPOINT`, que **não confere restrição adiada nenhuma**. Só o
`COMMIT` da transação de fora confere, e esse é o que o `ROLLBACK` do
`pytest-django` come.

O erro reaparece no desmonte porque, ao fechar o caso de teste, o Django chama
`connection.check_constraints()` por conta própria antes de desfazer tudo. A
conferência finalmente acontece, mas já fora do corpo do teste que criou o dado
ruim, e por isso o rótulo do vermelho aponta para o vizinho.

Esta é prima da `armadilhas/337` e vale saber a diferença, porque a cura é
outra. Lá o falso-verde vem da mutação não alcançar o banco (a chave continua
na tabela, que nasceu das migrations). Aqui a chave **está** na tabela, do jeito
certo: o que não acontece é a conferência dela.

## Solução

**Force a conferência dentro do teste, no ponto exato em que você espera a
recusa.** São duas linhas, e elas movem o vermelho para o lugar certo:

```python
from django.db import IntegrityError, connection, transaction

def test_uma_peca_por_posicao(criar_portfolio, criar_peca):
    portfolio = criar_portfolio("aluno-1")
    criar_peca(portfolio, ordem=1)
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            criar_peca(portfolio, ordem=1)
            connection.check_constraints()
```

O `transaction.atomic()` de dentro é obrigatório, e não é enfeite: sem ele, o
erro de integridade aborta a transação do teste inteira e a consulta seguinte
morre com `TransactionManagementError`, que é a `armadilhas/027`. Com ele, só o
savepoint é desfeito, e o teste segue vivo.

**A régua geral, e é ela que fica: guarda que continua verde depois de sabotado
não testa nada.** O rito da prova por mutação (`RUNBOOK-LOTES.md` §9) é o que
pega esta classe inteira, e aqui ele pegou. A sabotagem foi a mais grosseira
possível, todas as restrições fora do `Meta` e a migração regerada sem elas:

- **antes do conserto:** suíte verde, o falso-verde intacto;
- **depois do conserto:** **23 testes reprovando** com
  `Failed: DID NOT RAISE <class 'django.db.utils.IntegrityError'>`.

Vinte e três vermelhos onde antes havia zero é a medida do que o teste passou a
provar. Desfaça a sabotagem antes de commitar.

**Duas armadilhas menores no caminho, ditas para ninguém tropeçar:**

- **Não troque a restrição por imediata para o teste ficar fácil.** O `DEFERRED`
  existe por causa da reordenação, e trocá-lo quebra a funcionalidade para
  arrumar o teste, que é a troca errada.
- **`check_constraints()` confere TUDO que está pendente na conexão, não só a
  sua chave.** Se o cenário do teste deixou outra pendência para trás, o
  `pytest.raises` captura a errada e você volta a provar nada. Mantenha o
  cenário mínimo.

**Evidência:** PR
[#1142](https://github.com/abundanciabr/sitesdoreino/pull/1142), célula `pages`,
tabelas do portfólio do aluno.
