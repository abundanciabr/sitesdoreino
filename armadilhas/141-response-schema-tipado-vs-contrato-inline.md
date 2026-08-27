# `response=Schema` no django-ninja sempre emite `$ref` nomeado — errado quando o contrato da rota é inline

**Sintoma:** um handler novo declara `@router.get("/resumo", response=RespostaResumo, ...)`
com `RespostaResumo(ninja.Schema)`, e `make contrato-check` reprova com um diff que
ninguém escreveu à mão:

```
       schema:
-        type: object
-        additionalProperties: false
-        required: [nao_lidas]
-        properties:
-          nao_lidas: { type: integer, minimum: 0 }
+        $ref: '#/components/schemas/RespostaResumo'
 components:
+  schemas:
+    RespostaResumo:
+      title: RespostaResumo
+      type: object
+      properties:
+        nao_lidas: { type: integer }
   securitySchemes:
     bearerAuth: { type: http, scheme: bearer }
```

O contrato congelado (`contracts/<celula>.openapi.yaml`) não tem NENHUM
`components.schemas` para aquele path — a resposta é um objeto INLINE, escrito
por extenso dentro do próprio `path`. O schema vivo saiu com um componente
nomeado que o congelado nunca teve, e o freeze (`ci/contract_freeze.py`)
reprova a divergência de forma, não de conteúdo.

**Causa:** o django-ninja, quando o handler declara `response=AlgumaSchema`
(uma classe `ninja.Schema`/pydantic), **sempre** registra um componente em
`components.schemas` com o nome da classe e troca o corpo por `$ref` no lugar
do objeto — não existe parâmetro para pedir "gera esse Schema, mas inlinado".
Isso é o padrão CORRETO quando o contrato daquele path de fato nomeia um
componente — `catalogo` (`Site`/`Product`/`Offer`) e `identidade`
(`Session`/`SessionFull`) fazem exatamente isso, com `response=Site` etc.
casando o `$ref` byte a byte — e o padrão ERRADO quando o path é inline (hoje:
`alunos`, `leads`, `notificacoes`).

**A armadilha não é "por célula", é por ROTA.** `sugestoes` tem um único
endpoint (`/sessao`, legado) e ELE usa `response=Session`, porque o contrato
dessa célula também nomeia um componente `Session` — olhar de longe e concluir
"sugestoes é inline como alunos" seria errado. A pergunta certa nunca é "que
célula é essa", é "o `schema:` desse path específico, no YAML congelado, é
`$ref: '#/components/schemas/X'` ou é a forma escrita por extenso (`type:
object`, `type: array`) direto no path?" — a resposta dita a técnica, sempre,
mesmo dentro da mesma célula.

**Por que isso já foi descoberto três vezes, em silêncio:** `alunos` e `leads`
carregam, cada uma, um comentário quase idêntico no topo do próprio
`apps/core/api.py` — a mesmíssima frase, "isso criaria refs nomeadas que o
contrato não tem", escrita duas vezes sem uma célula saber da outra — e a
`notificacoes` da Fase 4 do sininho (PR #280) escreveu a versão mais longa,
em docstring de módulo. Três células reinventando a mesma explicação, quase
palavra por palavra, é o sinal de que ela precisava morar num lugar central em
vez de dentro de cada `api.py`.

**Solução:** antes de escrever o handler, abra `contracts/<celula>.openapi.yaml`
no path que você vai implementar e olhe o nó `schema:` da resposta (e do
`requestBody`, se houver):

- **`$ref: '#/components/schemas/Nome'`** → declare `class Nome(Schema): ...`
  com o nome EXATO do componente (cuidado com sombreamento de import —
  `armadilhas/020`) e use `response=Nome`. O ninja reproduz o mesmo `$ref`.
- **objeto inline** → NÃO use `response=`. O handler recebe `request` puro —
  nem `Query`/`Path` tipado do ninja entram aqui tampouco, pelo mesmo motivo:
  não é só o `$ref` do corpo que foge do congelado, é o pydantic decidindo
  sozinho `required`/`default`/`format` de qualquer campo que ele gere (a
  mesma classe de divergência que a `armadilhas/075` documentou para campo
  opcional novo). Declare `parameters`, `requestBody` e `responses` por
  inteiro em `openapi_extra={...}`, byte a byte igual ao YAML congelado, e
  devolva `django.http.JsonResponse(...)` direto do handler — nunca
  `response=`.

```python
_RESUMO_OPENAPI = {
    "responses": {
        200: {
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["nao_lidas"],
                        "properties": {"nao_lidas": {"type": "integer", "minimum": 0}},
                    }
                }
            },
        },
    },
}


@router.get("/resumo", openapi_extra=_RESUMO_OPENAPI)
def obter_resumo(request):
    return JsonResponse({"nao_lidas": resumo_de_nao_lidos(...)}, status=200)
```

**Como conferir em 10 segundos, sem rodar o portão inteiro:** `grep -n
"schema:" -A2 contracts/<celula>.openapi.yaml` no trecho do path em questão —
`$ref:` ou forma escrita por extenso na linha seguinte já responde a pergunta
antes de escrever qualquer Python.

**Origem:** PR #280 (célula `notificacoes`, Fase 4 do sininho — `/resumo`,
`/avisos`, `/marcar-lidas`), 27/08/2026.
