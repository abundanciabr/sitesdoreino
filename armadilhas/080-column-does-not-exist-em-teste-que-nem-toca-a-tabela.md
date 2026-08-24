# `ProgrammingError: column <tabela>.<campo> does not exist` num teste que nem toca aquela tabela

**Sintoma:** você acrescenta um campo a um model, ainda sem rodar
`makemigrations`, e roda **um único** teste que só lê metadados:

```python
def test_o_model_nao_tem_campo_de_desvoto_logico(sugestao, aluno):
    nomes = {campo.name for campo in Voto._meta.get_fields()}   # nem consulta o banco
    assert not (nomes & {"ativo", "removido_em"})
```

O teste estoura — e não na sua asserção, mas lá no fundo do driver:

```
E   django.db.utils.ProgrammingError: column sugestoes_voto.ativo does not exist
E   LINE 1: ...voto"."sugestao_id", "sugestoes_voto"."autor_id", "sugestoes...
C:\...\site-packages\psycopg\server_cursor.py:294: ProgrammingError
```

**Causa:** o teardown do `TestCase` do Django (que é o que o marker `django_db` usa)
chama `connection.check_constraints()` no fim de cada teste. No Postgres, esse método
**varre todos os models instalados** com um cursor server-side, conferindo cada FK.
Um único model dessincronizado das migrations derruba, no teardown, **qualquer** teste
com acesso ao banco — inclusive os que nunca leram aquela tabela. A mensagem aponta a
coluna certa e o teste errado, o que faz perder tempo procurando no lugar errado.

**Solução:**

- **No caminho normal:** o descasamento é o bug. `python manage.py makemigrations
  --check --dry-run` responde em um segundo se model e migration estão em dia — vale
  como portão de DoD, porque model sem migration é bomba-relógio que só explode em
  outro teste.
- **Quando o descasamento é DE PROPÓSITO** — a prova vermelho→verde (Lei 6) de um
  guarda que só inspeciona `_meta`, em que você introduz o campo errado sem gerar
  migration para ele: rode aquele teste com
  `python -m pytest <teste> --no-migrations --create-db`. O `--no-migrations` do
  pytest-django cria as tabelas direto dos models, então o schema volta a bater e o
  guarda falha pela asserção dele, que é o vermelho que você queria mostrar.

**Origem:** EVO-11 (`sugestoes`), montando o vermelho do guarda "desvotar apaga a
linha, nunca marca inativa".
