---
schema_version: 2
armadilha: 246
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: services/admin/tests/test_liberar_e_recusar.py::test_a_auditoria_e_append_only_no_BANCO
  motivo: ele tenta um UPDATE de verdade e exige que o BANCO recuse; foi o único sinal
sinal:
  - `DID NOT RAISE <class 'django.db.utils.DatabaseError'>`
  - `test_a_auditoria_e_append_only_no_BANCO`
---

# Alterar uma coluna no SQLite reconstrói a tabela e leva os gatilhos junto

**Sintoma:** você mexeu só nas `choices` e no `max_length` de um campo, o
`makemigrations` gerou um `AlterField` inocente, e um teste que não tem nada a
ver com a sua mudança fica vermelho:

```
Failed: DID NOT RAISE <class 'django.db.utils.DatabaseError'>
tests/test_liberar_e_recusar.py:245: test_a_auditoria_e_append_only_no_BANCO
```

**Causa.** O SQLite não sabe alterar uma coluna no lugar. O Django então faz o
que o próprio manual do SQLite manda: cria uma tabela nova com o esquema novo,
copia as linhas, apaga a velha e renomeia. **Os gatilhos ficam presos à tabela
velha e morrem na troca.** No Postgres nada disso acontece: um `ALTER TABLE ...
TYPE varchar(32)` preserva os gatilhos.

Aqui, o gatilho que morreu é a trava **append-only** da auditoria da célula
`admin` (`apps/auditoria/migrations/0001_initial.py`) — a que impede `UPDATE`,
`DELETE` e `TRUNCATE` na tabela que guarda o que foi feito pela área
administrativa. A lei da casa (`armadilhas/079`) é que ela é append-only por
MECANISMO, e não por disciplina; a migração a desarmava **sem erro nenhum, sem
mudar uma linha do modelo, e sem que ninguém tivesse pedido isso**.

**Por que isto é pior do que parece.** Em produção (Postgres) a trava continua
de pé, então o defeito é só do ambiente de teste — e essa é justamente a
armadilha. O guarda que prova a trava passa a medir um banco onde ela não
existe, e a partir daí ele carimba: qualquer regressão FUTURA na trava, inclusive
uma que valha em Postgres, encontra um teste que já estava verde por outro
motivo.

**Solução.** Toda migração que altera uma coluna de uma tabela com gatilho
refaz o gatilho no fim, e pelo mesmo caminho nos dois bancos:

```python
def refazer_o_gatilho(apps, schema_editor):
    # desinstala ANTES de instalar: no SQLite ele já morreu (o DROP IF EXISTS
    # não acha nada), no Postgres ele sobreviveu e precisa sair antes de entrar.
    _INICIAL.desinstalar(apps, schema_editor)
    _INICIAL.instalar(apps, schema_editor)

operations = [
    migrations.AlterField(...),
    migrations.RunPython(refazer_o_gatilho, refazer_o_gatilho, elidable=False),
]
```

Três detalhes que não são estilo:

- **Reuse as funções da migração que criou o gatilho**, via
  `importlib.import_module("apps.auditoria.migrations.0001_initial")` (um nome
  que começa com dígito não é identificador Python, então `from .0001_initial
  import` é erro de sintaxe). Copiar o SQL cria duas versões da trava, e um dia
  elas divergem.
- **`elidable=False`**: um `squashmigrations` que descartasse este passo
  devolveria a auditoria adulterável, em silêncio.
- **Um caminho só para os dois bancos.** Um `if vendor == "sqlite"` faria o
  retoque ser exercitado só onde ele não importa.

**Contexto:** caiu em 31/08/2026, no editor de documentos do painel do admin.
O verbo `desarquivar_documento` tem 21 caracteres, a coluna `acao` tinha 20, e
alargá-la para 32 foi o gesto mais banal possível. Ver
`services/admin/apps/auditoria/migrations/0010_verbos_dos_gestos_do_documento.py`,
que carrega a explicação colada no código.
