---
schema_version: 2
armadilha: 361
estado: documentada
degrau: 2
confianca: alta
custo_por_queda: medio
guarda:
  tipo: nenhum
  motivo: nenhum portão sabe distinguir "um teste marcado `transaction=True`" de "um teste que precisava disso de verdade". Um guarda que proibisse a marca no `grep` reprovaria o dia em que ela for genuinamente necessária (SQLite real, ou uma migração que só funciona fora de transação); o defeito é de JULGAMENTO — "isto precisa mesmo de `transaction=True`?" — não de sintaxe.
sinal:
  - "ERROR at teardown of test_"
  - "auditoria e append-only"
  - "Database .* couldn't be flushed"
---

# `transaction=True` numa célula com auditoria append-only quebra o `flush` do teardown, e o erro aponta para o teste errado

**Sintoma.** Um teste que usa `MigrationExecutor` para reconstruir o banco de
antes de uma migração (mesmo molde de `tests/test_reembolso_no_banco.py`,
adaptado para uma migração que muda o ESQUEMA) passa o corpo inteiro — todos os
`assert` batem — e ainda assim a suíte acusa erro **nele mesmo**, mas na fase de
desmonte:

```
ERROR at teardown of test_a_migracao_associa_um_capitulo_preexistente_a_um_livro_padrao
psycopg.errors.IntegrityConstraintViolation: auditoria e append-only: nao se
edita nem se apaga linha de auditoria (TRUNCATE)
CONTEXT:  PL/pgSQL function auditoria_append_only() line 10 at RAISE
```

**Causa.** `@pytest.mark.django_db(transaction=True)` não embrulha o teste numa
transação com `ROLLBACK` no fim — ele roda uma `TransactionTestCase` de
verdade, e o desmonte dela é `call_command("flush", ...)`, que faz
`TRUNCATE` em TODAS as tabelas do banco de teste para devolvê-lo limpo. Numa
célula com a trava append-only da auditoria (`armadilhas/079`,
`armadilhas/246`), essa tabela **recusa `TRUNCATE`** por mecanismo — o mesmo
gatilho que protege a auditoria em produção protege (ou, aqui, atrapalha) o
banco de teste. O `flush` levanta, o pytest atribui o erro ao teste que estava
rodando quando o desmonte aconteceu, e quem lê o relatório vai procurar o
defeito dentro de um teste que está perfeito.

**Por que `transaction=True` parecia necessário.** A crença (documentada no
próprio docstring do teste, antes deste conserto) era: "o SQLite recusa
desligar a checagem de chave estrangeira dentro de uma transação, e a migração
para trás precisa disso". Verdade em SQLite — mas **este projeto testa
Postgres em CI** (`ci-celula.yml` sobe `postgres:16`, nunca SQLite), e o
Postgres roda DDL (`ALTER TABLE`, `CREATE TABLE`) dentro de transação sem
nenhum problema. O `db` comum do `pytest-django` (que embrulha o teste numa
transação e faz `ROLLBACK`, nunca `flush`) já bastava — o `MigrationExecutor`
anda para trás e para frente dentro dela, e o `ROLLBACK` desfaz tudo, DDL
incluído, sem tocar a trava append-only nenhuma vez.

**Solução.** Não marque `transaction=True` só porque o teste usa
`MigrationExecutor`. Use o `db` padrão primeiro, e só suba para
`transaction=True` se o teste realmente estourar por causa de transação
aninhada — nesse caso, a migração daquela célula terá o mesmo problema que
esta armadilha descreve, e a saída não é a marca e sim testar a migração sem
depender do `flush`: chamar a função `RunPython` diretamente com um `apps`
falso (o molde de `tests/test_reembolso_no_banco.py`) quando o teste não
precisar mudar o ESQUEMA, ou aceitar que `transaction=True` é a ferramenta
certa e o `flush` vai esbarrar na trava — nesse caso o achado é sobre a trava,
não sobre o teste, e cabe a quem construiu a auditoria (`armadilhas/079`)
decidir se o `flush` de teste deve enxergar essa tabela como especial.

**O que NÃO fazer.** Não enfraqueça o gatilho append-only para o ambiente de
teste "passar por baixo" dele — ele existe para blindar um dado que não pode
ser editado nem apagado nem em teste, e testar contra um banco onde a trava
não existe é exatamente o defeito que a `armadilhas/246` já descreveu (o
guarda mede um banco fake, e a regressão real passa despercebida).

**Contexto:** achado em 06/09/2026, célula `admin`, ao dar prosseguimento a um
despacho que ficou pela metade (`Biblioteca do Livro`, migração `0012_o_livro_por_tras_dos_capitulos`)
— o teste da migração de dado (`TAR` da tela de leitura estilo Kindle) foi a
primeira vez que esta célula usou `transaction=True` num teste.
