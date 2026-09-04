---
schema_version: 2
armadilha: 319
estado: guardada
degrau: 3
confianca: alta
custo_por_queda: alto
guarda:
  tipo: teste
  detector: services/encomendas/tests/test_modelo_de_dados.py
  motivo: "test_uma_oferta_pendente_por_encomenda e test_uma_oferta_pendente_por_aluno ficam VERMELHOS quando o indice parcial e derrubado por uma migracao 0002 (medido: '1 failed'), e ficam VERDES quando ele e derrubado por um RunSQL dentro da propria 0001 (medido: '1 passed') - que e o falso-negativo desta entrada."
sinal:
  - "AINDA VERDE"
  - "DROP INDEX IF EXISTS"
  - "deferred_sql"
  - "UniqueConstraint com condition"
---

# A mutação que não muta: um `RunSQL` na MESMA migração não derruba índice parcial, e a prova por mutação sai falso-negativa

**Sintoma.** Você provou vinte e sete guardas por mutação e dois teimam em ficar
verdes. A saída do arredor de mutação diz, para os dois:

```
duas ofertas pendentes na mesma encomenda            AINDA VERDE (guarda cego)  1 passed
duas ofertas pendentes para o mesmo aluno            AINDA VERDE (guarda cego)  1 passed
```

A leitura natural é a pior possível: *"estes dois testes passam mesmo sem a
restrição, logo são decoração"*. E a leitura está errada. Os guardas estão de pé;
quem falhou foi a MUTAÇÃO, que não mutou nada.

**Causa.** A mutação era um `migrations.RunSQL(["DROP INDEX IF EXISTS
uma_oferta_pendente_por_encomenda;"])` acrescentado ao fim das `operations` da
MESMA migração que cria a tabela. Só que uma `UniqueConstraint` **com
`condition=`** não vira restrição de tabela: vira `CREATE UNIQUE INDEX ... WHERE
...`, e o `SchemaEditor` do Django empurra todo índice para o `deferred_sql`, que
ele executa **ao final da migração inteira**, depois de todas as operações.

A ordem real, lida no `manage.py sqlmigrate`, é esta:

```
linha 170:  ALTER TABLE ... ADD CONSTRAINT oferta_e_encomenda_do_mesmo_site ...   <- meu RunSQL
linha 195:  DROP INDEX IF EXISTS uma_oferta_pendente_por_encomenda;               <- a mutação
linha 211:  CREATE UNIQUE INDEX "uma_oferta_pendente_por_encomenda" ...           <- o índice, DEPOIS
```

O `DROP` roda antes de o índice existir, o `IF EXISTS` engole o erro sem uma
palavra, e o índice nasce logo em seguida. A mutação foi aplicada, o teste rodou,
e nada tinha mudado.

**Por que isso é caro.** Uma prova por mutação existe para responder "este teste
morde?". Quando a própria mutação é um no-op silencioso, ela responde "não", e a
resposta é mentira. O caminho seguinte é sempre destrutivo: ou você apaga um
guarda bom achando que é decoração, ou você reescreve o teste até ele reprovar
por outro motivo. É a família `armadilhas/264` a `272` (asserção com mais de uma
causa suficiente) pelo avesso: aqui a asserção está certa e o EXPERIMENTO é que
tem duas leituras.

**Solução: derrube o índice numa migração SEGUINTE, não na mesma.**

```python
# apps/<celula>/migrations/0002_mutacao_temporaria.py  (temporário, some depois)
class Migration(migrations.Migration):
    dependencies = [("<celula>", "0001_initial")]
    operations = [
        migrations.RunSQL(
            sql=["DROP INDEX IF EXISTS uma_oferta_pendente_por_encomenda;"],
            reverse_sql=migrations.RunSQL.noop,
        ),
    ]
```

O `deferred_sql` da `0001` já terminou quando a `0002` começa, e aí o `DROP`
encontra o índice. Medido na mesma máquina, no mesmo minuto: `1 passed` com a
mutação na `0001`, `1 failed` com a mutação na `0002`.

**A regra de bolso que fica, e ela vale para toda mutação de esquema:** antes de
declarar um guarda cego, **prove que a mutação aconteceu**. Um `SELECT indexname
FROM pg_indexes WHERE tablename = '<tabela>'` (ou `SELECT conname FROM
pg_constraint`) dentro do banco de teste custa uma linha e responde a pergunta
que o veredito verde não responde. `IF EXISTS` é o que transforma o engano em
silêncio: use-o para o `DROP` funcionar nos dois sentidos, mas nunca confie nele
como prova de que algo foi derrubado.

**E como saber, de antemão, se a sua restrição cai neste caso:** rode
`python manage.py sqlmigrate <celula> 0001` e procure o nome dela. Se aparecer
dentro do `CREATE TABLE` ou num `ALTER TABLE ... ADD CONSTRAINT`, é restrição de
tabela e o `RunSQL` na mesma migração a alcança. Se aparecer num `CREATE [UNIQUE]
INDEX` no FIM da saída, é índice, é `deferred_sql`, e a mutação precisa da
migração seguinte. `UniqueConstraint` com `condition=`, `Index(...)` e
`UniqueConstraint` com `include=` caem todos no segundo grupo.

**Origem:** TAR-120, degrau 2.2 da Fila do Primeiro Dólar (célula `encomendas`),
04/09/2026. Vinte e nove guardas novos, provados um a um por mutação; dois deles
se declararam cegos e não eram. O tempo perdido foi inteiro em investigar dois
guardas corretos, com a hipótese errada de que a restrição não existia no banco.
