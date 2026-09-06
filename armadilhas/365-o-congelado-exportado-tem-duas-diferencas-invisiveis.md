---
schema_version: 2
armadilha: 365
estado: documentada
degrau: 3
confianca: alta
custo_por_queda: baixo
guarda:
  tipo: nenhum
  motivo: o portao ja diz a verdade (ele mostra o diff exato); o que falta e saber de antemao que as duas diferencas existem, e isso e conhecimento, nao regra
sinal:
  - '"parameters": \[\]'
  - "o schema vivo derivou do contrato congelado"
---

# O congelado montado a partir do exportado ainda difere em dois lugares invisíveis

**Sintoma.** Você faz tudo certo no Rito de Contrato: escreve o código, exporta o
OpenAPI vivo (`python manage.py export_openapi`), monta o congelado a partir
dele (é a `armadilhas/243` passo 2, e a `armadilhas/324` para a prosa) e roda o
freeze com os dois na mesma árvore. Mesmo assim:

```
--- FAIL contrato/catalogo -------------------------------------------
--- congelado/catalogo
+++ vivo/catalogo
@@ -373,8 +373,9 @@
     "/produtos": {
       "get": {
-        "description": "...continua vendo o nome dele por `getProduct`.\n",
+        "description": "...continua vendo o nome dele por `getProduct`.",
         "operationId": "listProducts",
+        "parameters": [],
```

Duas diferenças, e nenhuma delas está no que você escreveu. Elas nascem entre o
YAML e o JSON.

**Causa 1: o bloco `|` do YAML acrescenta uma quebra de linha no fim.** Você
copia a `description` do JSON exportado para dentro de um `description: |` e o
YAML devolve o texto com um `\n` a mais que a docstring do Python não tem.

**Causa 2: o django-ninja emite `"parameters": []` mesmo em operação sem
parâmetro nenhum.** Uma lista vazia é fácil de não escrever no YAML, e o
normalizador do freeze não a apaga de nenhum dos dois lados.

**Solução, as duas em uma linha cada:**

```yaml
      description: |-        # `|-` corta a quebra final; `|` a mantém
        ...
      parameters: []         # sempre, mesmo quando não há parâmetro
```

A escolha entre `|` e `|-` **não é de gosto**: ela depende de a string exportada
terminar em `\n` ou não. Confira no JSON, não no olho. Docstring de função
django-ninja normalmente NÃO termina em quebra; `description=` escrito à mão numa
constante, frequentemente sim.

**Como não descobrir isso pelo CI.** O passo 2 da `armadilhas/243` manda rodar o
freeze uma vez com o congelado e o código na mesma árvore, ANTES de separar os
dois PRs. As duas diferenças aparecem ali, em dez segundos, em vez de num PR
devolvido. Se você pular esse passo, o PR do contrato passa (contrato sozinho não
roda freeze) e o do CÓDIGO é que reprova, um degrau depois, longe da causa.

**Origem.** Rito de Contrato de 06/09/2026 (PR #1186), que acrescentou
`listProducts` ao `catalogo` e `product_id` ao `alunos`. Uma rodada de freeze
gasta nas duas diferenças acima; depois do conserto,
`contrato/catalogo PASS idêntico ao congelado (587 linhas comparadas)`.
