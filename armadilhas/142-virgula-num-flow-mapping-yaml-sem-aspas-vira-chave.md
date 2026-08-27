# Vírgula dentro de `{ chave: valor }` YAML sem aspas cria uma CHAVE fantasma — e o freeze de contrato cobra dela

**Sintoma:** o `make contrato-check` da célula reprova com um diff que ninguém
escreveu — o congelado tem uma chave a mais, e ela é um pedaço de frase:

```
   "422": {
-    "description": "Payload invalido",
-    "ou recusa sem motivo": null
+    "description": "Payload invalido, ou recusa sem motivo"
   }
```

A linha do contrato parece perfeitamente normal:

```yaml
'422': { description: Payload invalido, ou recusa sem motivo }
```

**Causa:** dentro de um *flow mapping* (`{ ... }`), a vírgula é o **separador de
entradas** do YAML, não texto. `description: Payload invalido, ou recusa sem
motivo` é lido como DUAS entradas: `description: "Payload invalido"` e a chave
`"ou recusa sem motivo"` com valor `null`. O arquivo é YAML válido — nada avisa.

É a mesma família do `armadilhas/048` (`run: algo: coisa`), com o outro
metacaractere: lá o culpado é `: ` abrindo um mapeamento, aqui é `,` fechando
uma entrada. Em ambos, o texto escrito por um humano em português cai dentro da
sintaxe do YAML sem pedir licença — e vírgula em português é muito mais comum
que dois-pontos.

**Por que dói mais num contrato do que num workflow:** um Response Object de
OpenAPI não aceita chave arbitrária (só `x-` de extensão), então o documento
publicado fica inválido — mas o freeze não reclama disso: ele compara o vivo com
o congelado, e o **congelado é a referência**. Quem implementa o provedor cai
numa escolha ruim: reproduzir a chave fantasma no código para o portão ficar
verde (e publicar a bobagem para todo consumidor), ou ficar vermelho até o
contrato ser reaberto — que tem rito próprio (`RITOS.md` §3) e passa por
CODEOWNERS. Nenhuma das duas é decisão de sessão.

**Solução:** aspas em todo escalar de flow mapping que contenha texto humano.

```yaml
'422': { description: "Payload invalido, ou recusa sem motivo" }
```

**Como pegar ANTES de congelar** — vale como passo do Rito de Contrato, porque
custa dois segundos e o conserto depois custa um PR e uma decisão do mantenedor:

```bash
python -c "import yaml,json;print(json.dumps(yaml.safe_load(open('contracts/<celula>.openapi.yaml',encoding='utf-8')),indent=2,ensure_ascii=False))"
```

Leia as chaves do que saiu. Chave que é um pedaço de frase, ou valor `null` que
você não escreveu, é este bug. Um `grep -n ", " contracts/*.openapi.yaml | grep
"{"` acha os candidatos em qualquer contrato do repositório.

**Origem:** Fase 1 da fila de liberação (`alunos`, 27/08/2026) — o contrato
mergeado no PR #291 trouxe a linha, e o defeito só apareceu quando o provedor
foi implementado e o freeze comparou os dois lados.
