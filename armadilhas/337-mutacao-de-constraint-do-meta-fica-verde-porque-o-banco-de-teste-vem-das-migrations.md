---
schema_version: 2
armadilha: 337
estado: guardada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: `nenhum portão sabe que uma prova por mutação foi feita contra o arquivo errado: o CI vê a suíte verde nos dois casos. A cura é de MÉTODO e cabe numa frase: a mutação tem de alcançar o que EXECUTA a regra, e uma restrição de banco executa no DDL, não na classe Python.`
---

# A mutação de uma `constraint` do `Meta` fica verde, porque o banco de teste vem das migrations e a chave continua lá

**Sintoma.** Você está fazendo a prova por mutação que o rito exige para uma
regra que mora no banco (uma `UniqueConstraint`, uma `CheckConstraint`): apaga
a linha do `Meta.constraints` em `models.py`, roda o teste que deveria
depender dela, e ele fica **verde**. Duas leituras erradas nascem daí, e as
duas custam caro: "o teste não mede a chave" (e você o reescreve para pior),
ou "a chave é decoração" (e alguém a apaga um dia).

**Causa.** `pytest-django` constrói o banco de teste **rodando as migrations**.
O `Meta.constraints` da classe é lido por `makemigrations`, e por mais ninguém
em tempo de teste: apagar a restrição do Python não a apaga da tabela, porque a
tabela nasce do `0001_initial.py`, que ainda a tem. A mutação não chegou ao
lugar onde a regra executa.

Medido em 05/09/2026, na `gamificacao`, com a chave
`Unique(origem_event_id, regra_slug, pessoa)` do ledger removida de
`models.py`:

```
$ pytest tests/test_escutar_a_sala_de_aula.py::test_o_mesmo_evento_reentregue...
1 passed                              # falso-verde: a chave continua no banco

$ pytest --no-migrations tests/test_escutar_a_sala_de_aula.py::test_o_mesmo_evento_reentregue...
AssertionError: o ledger deixou pagar duas vezes
assert 3 == 1                         # a prova de verdade
```

**Solução.** A mutação precisa alcançar o DDL. Dois caminhos, e qual usar
depende de onde a restrição mora:

1. **Restrição declarada no `Meta`** (o caso comum): rode o teste mutado com
   `--no-migrations`. O banco de teste passa a ser construído a partir das
   classes, e a mutação em `models.py` vira mutação na tabela. Restaure com
   `git checkout -- models.py` e rode de novo, verde, SEM o flag.
2. **Restrição que só existe numa migration** (`RunSQL`, como a chave
   estrangeira composta da `armadilhas/274`): o `--no-migrations` a PERDERIA,
   e o vermelho que aparecesse seria por outro motivo. Ali a mutação é na
   própria migration, e o teste roda do jeito normal.

**A regra de bolso que fica.** Antes de declarar uma prova por mutação, responda
"o que executa esta regra?". Se a resposta for "o Postgres", a mutação tem de
mudar o que o Postgres recebeu, e um `models.py` editado não é isso até alguém
gerar DDL a partir dele. É a irmã da `armadilhas/268` (vermelho que não prova)
vista do outro lado: o verde que não prova.
