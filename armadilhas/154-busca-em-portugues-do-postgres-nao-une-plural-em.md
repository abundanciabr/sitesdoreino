# Busca em português do PostgreSQL: o plural em `-ens` não é unido, e acento importa

**Sintoma:** a busca do site "não acha" um texto que existe. O aluno escreve
`modelagens` e não encontra a mensagem que diz `modelagem`; escreve `chapeu` e
não encontra `chapéu`. Nada falha, nada dá erro — a consulta devolve zero
resultado com toda a cara de que aquilo não existe.

**Causa (medida em 28/08/2026 contra PostgreSQL 17, não suposta):** a
configuração `portuguese` do PostgreSQL usa o radicalizador Snowball, e ele tem
dois limites concretos:

```sql
SELECT to_tsvector('portuguese', 'modelagem');   -- 'modelag'
SELECT to_tsquery ('portuguese', 'modelagens');  -- 'modelagens'  ← NÃO radicalizou
```

| par | casa? |
|---|---|
| `textura` ~ `texturas` | ✅ sim — plural regular em `-s` funciona |
| `malhas` ~ `malha` | ✅ sim |
| `renderizar` ~ `renderizando` | ✅ sim — formas verbais funcionam |
| **`modelagem` ~ `modelagens`** | ❌ **não** — plural em `-em`/`-ens` |
| **`chapéu` ~ `chapeu`** | ❌ **não** — acento é significativo |

O segundo é o mais caro na prática: **no Brasil quase ninguém acentua ao
buscar.** Uma busca acento-sensível erra a maioria das consultas reais sem que
ninguém perceba que está errando.

**Por que passa despercebido:** o teste óbvio ("busco uma palavra que está lá,
escrita igual") passa. O caso que quebra é o que o usuário faz de verdade —
plural diferente, sem acento — e ninguém reporta "a busca não achou": a pessoa
conclui que a resposta não existe e pergunta de novo. Num fórum, isso destrói
justamente o que ele existe para fazer.

**Solução:**

1. **Escreva o teste do buraco, não só o do caso feliz.** Em
   `services/forum/tests/test_modelo_de_dados.py` há
   `test_os_dois_buracos_conhecidos_da_busca_em_portugues`, que **exige** o
   comportamento limitado de hoje. Quando a cura chegar, ele fica vermelho — e
   é assim que se descobre que a cura chegou, em vez de o limite virar folclore.
2. **A cura do acento é a extensão `unaccent`**, e ela só se instala como
   superusuário do banco:
   ```sql
   CREATE EXTENSION IF NOT EXISTS unaccent;
   ```
   Logo, o lugar dela é o **script de provisionamento da célula**
   (`infra/provisionar-<celula>.sh`), que já roda com esse poder — nunca uma
   migração do Django, que roda com o papel restrito da célula e falharia.
3. **A cura do `-ens`** é uma lista de sinônimos ou um dicionário
   `ispell`/`hunspell` português, montado sobre a mesma configuração.
4. **Nunca calcule o vetor de busca na consulta.** Coluna materializada
   (`SearchVectorField`) com índice GIN, preenchida na escrita. Calcular no
   `WHERE` funciona com 500 linhas e trava com 50 mil — e só se descobre em
   produção, quando o conserto já é migração na maior tabela do sistema.

**Onde já mordeu:** na gênese do modelo de dados do fórum (PR do modelo,
28/08/2026). O teste original afirmava que `modelagens` acharia `modelagem` — e
falhou contra um PostgreSQL 17 de verdade, rodando localmente antes do PR. Se a
suíte tivesse usado SQLite ou um dublê, a afirmação errada teria entrado no
repositório como se fosse verdade.
