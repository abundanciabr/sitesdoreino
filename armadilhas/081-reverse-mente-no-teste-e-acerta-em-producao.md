# `reverse()` mente no teste e acerta em produção (célula sob `SCRIPT_NAME`)

**Sintoma:** numa célula servida sob prefixo de caminho (`/forms/sugestoes/`,
`/checkout/`, `/quiz/`), a MESMA requisição de teste tem `request.path_info` **certo**
e `reverse()` devolvendo caminho **sem o prefixo**. O teste que confere a URL passa
quando devia falhar — ou falha quando a produção está correta. Em produção o mesmo
código acerta, então o erro só aparece pelo lado de fora, muito depois.

No OAuth isso é grave: o `redirect_uri` é comparado **caractere a caractere** pelo
provedor. Um prefixo faltando ⇒ `redirect_uri_mismatch` em **todo** login legítimo, e
o teste não avisou.

**Causa:** `reverse()` **não lê** `settings.FORCE_SCRIPT_NAME`. Ele lê um prefixo
guardado em **variável de thread**, que o SERVIDOR preenche — `ASGIHandler.__call__`
chama `set_script_prefix()`. Os handlers de teste do Django (`Client`, `AsyncClient`)
**não chamam**. Ou seja: o objeto de requisição do teste é fiel, mas o estado global
do qual `reverse()` depende não existe ali.

**Solução:** o teste tem de **emular o servidor**, não confiar no handler:

```python
from django.urls import set_script_prefix, clear_script_prefix

def test_url_de_retorno_leva_o_prefixo(settings):
    set_script_prefix("/forms/sugestoes/")
    try:
        ...  # exercite o código que monta a URL
    finally:
        clear_script_prefix()   # o prefixo é de THREAD e vaza entre testes
```

O `finally` não é zelo: sem ele o prefixo vaza para os testes seguintes, e o próximo
vermelho aparece num arquivo que não tem nada a ver.

**Confira as três partes do endereço separadamente** — elas quebram por motivos
diferentes e um `assertEqual` na URL inteira esconde qual foi:

| Parte | De onde vem | Quebra quando |
|---|---|---|
| esquema (`https`) | `SECURE_PROXY_SSL_HEADER` | o proxy não manda o header, ou o settings não o declara |
| domínio | header `Host` da requisição | `ALLOWED_HOSTS`/proxy mexem no `Host` |
| caminho | `reverse()` | é esta armadilha |

**Vale para `checkout`, `quiz` e qualquer célula futura sob prefixo** — as três
servem sob `SCRIPT_NAME`. Parente próxima: a entrada sobre `/healthz` sumindo sob
`SCRIPT_NAME` (a cura de lá é `request.path_info`; esta aqui é o lado do `reverse()`,
que `path_info` não resolve).

**Origem:** despacho EVO-12a (`sugestoes`, "Entrar com Google"), 24/08/2026 — foi a
pegadinha que custou a maior parte do tempo daquele despacho.
