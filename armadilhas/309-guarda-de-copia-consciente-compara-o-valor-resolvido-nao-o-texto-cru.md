---
schema_version: 2
armadilha: 309
estado: guardada
degrau: 6
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: CI
  dono: ci/tests/test_sql_da_busca_sem_acento_e_um_so.py
---

# O guarda de uma "cópia consciente" raspou o texto cru da fonte e comparou `{CONFIG_SEM_ACENTO}` com `portugues_sem_acento`: um f-string não é o valor que ele produz

**Sintoma.** Você escreve o teste que a lei anti-duplicação manda para um fato
declarado em dois lugares (aqui, o SQL da busca sem acento: `SQL_DA_CURA` em
`services/forum/apps/forum/config_de_busca.py` e o heredoc `SQL_DA_BUSCA` de
`infra/provisionar-forum.sh`). O jeito óbvio é ler os dois arquivos como texto e
comparar. O teste nasce VERMELHO num repositório que está certo:

```
E   - DROP TEXT SEARCH CONFIGURATION IF EXISTS {CONFIG_SEM_ACENTO};
E   + DROP TEXT SEARCH CONFIGURATION IF EXISTS portugues_sem_acento;
```

A fonte é um `f"""…"""` que interpola uma constante; o texto cru do arquivo
carrega o marcador, não o valor. E a saída fácil (e errada) é afrouxar a
comparação até ela passar: trocar `{CONFIG_SEM_ACENTO}` à mão no teste, ou
comparar só "as linhas que não têm chave". Um guarda afrouxado assim deixaria
passar justamente a divergência que ele existe para pegar (o NOME da
configuração, que é o contrato entre os dois lados).

**Causa.** Cópia consciente entre um arquivo de CÓDIGO e um de TEXTO (shell
colado na VPS, YAML, SQL) tem os dois lados em linguagens diferentes. O lado de
código pode ter interpolação, concatenação, constante importada; raspar o texto
dele compara a receita, não o prato.

**Solução.** Compare o valor RESOLVIDO do lado de código: importe o módulo pelo
caminho (`importlib.util.spec_from_file_location`, sem `sys.path` nem Django) e
leia a constante já montada. Do lado de texto, extraia o trecho exato (o
heredoc, pelo delimitador) e normalize só espaço em branco. Aí a comparação é
entre dois produtos finais, e a prova por sabotagem funciona nas duas direções:
mudar `WITH unaccent, portuguese_stem` só no script reprova na ASSERÇÃO; mudar
só a constante na fonte também (`armadilhas/195`: o vermelho tem de morrer na
asserção, não na construção). O pré-requisito é o módulo-fonte ser importável a
frio, o que vale para qualquer arquivo lido no boot de uma célula (só `os`).

Quando o módulo NÃO puder ser importado a frio (puxa Django no import), a
alternativa honesta é resolver a interpolação com as mesmas constantes que o
arquivo declara, lidas por regex, e DIZER no teste que é isso que ele faz;
nunca "comparar só o que não tem chave".

**Origem.** TAR-052, 03/09/2026 (lote `ci` do dia), guarda
`ci/tests/test_sql_da_busca_sem_acento_e_um_so.py`. A duplicação foi declarada
na TAR-047 (`armadilhas/154`).
