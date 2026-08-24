# Campo opcional novo numa API congelada: `default=` reprova o freeze, e `""` vaza para o consumidor

**Sintoma:** você acrescenta um campo **opcional** a um `ninja.Schema` cuja
célula tem contrato congelado, e o `make contrato-check` reprova com uma linha
que você não escreveu:

```
+          "default_language": {
+            "default": "",
             "description": "...",
             "type": "string"
```

Corrigido isso, aparece o segundo sintoma — mais silencioso e pior: todo
consumidor que hoje recebe o objeto **sem** o campo passa a receber
`"default_language": ""` e `"languages": []`. Nada quebra no CI; a mudança de
forma só é descoberta do outro lado da rede.

**Causa:** são duas, e é fácil consertar a primeira e não ver a segunda.

1. `Field(default="")` faz o pydantic emitir uma chave `"default"` no JSON
   Schema exportado. O contrato escrito à mão em `contracts/*.openapi.yaml`
   não tem essa chave — então o freeze acusa divergência por um detalhe que
   nada tem a ver com a semântica do campo.
2. O django-ninja serializa **todos** os campos do Schema, tenham eles sido
   preenchidos pelo handler ou não. Um campo com default vira chave presente
   na resposta, sempre. "Opcional no contrato" não vira "ausente na resposta"
   sozinho.

**Solução:** as duas metades, juntas.

```python
# 1. default_factory NÃO emite "default" no schema — o freeze volta a bater.
#    (É por isso que os campos opcionais que já existiam usavam default_factory
#     em vez de default= ; o motivo não estava escrito em lugar nenhum.)
default_language: str = Field(default_factory=str, description="...")
languages: list = Field(default_factory=list, json_schema_extra=_inline_items)

# 2. exclude_unset na OPERAÇÃO + handler que só põe a chave quando ela existe:
@router.get("/sites/by-host/{host}", response=Site, exclude_unset=True, ...)
def get_site_by_host(request, host: str):
    payload = {...}                       # o que sempre existiu
    if site.languages:                    # só então as chaves novas
        payload["default_language"] = site.default_language
        payload["languages"] = [...]
    return payload
```

`exclude_unset=True` serializa apenas as chaves que o handler realmente pôs no
dict — o pydantic marca como "set" o que veio na entrada. Resultado: quem não
tem o campo responde **byte-idêntico** ao de antes da mudança, e isso vira um
teste de regressão de uma linha (`assert set(corpo) == {…as chaves de antes…}`),
que é a prova mais forte possível de que nenhum consumidor atual quebrou.

**Não tente `str | None = None`:** o schema exportado vira
`anyOf: [{type: string}, {type: null}]` e o freeze reprova de novo — além de
`null` normalmente não ser permitido pelo contrato (`type: string` sem
`nullable`). Ausência e `null` não são a mesma coisa para quem consome.

**Como conferir antes de rodar o portão inteiro:** `Schema.model_json_schema()`
num shell com `django.setup()` mostra em 5 segundos se saiu chave `default`
sobrando.

**Origem:** fase 4 do i18n (catalogo, `Site.default_language`/`languages`) —
provedor do Rito de Contrato, 24/08/2026.
