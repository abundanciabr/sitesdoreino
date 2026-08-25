# `{% static %}` sob `SCRIPT_NAME` manda o navegador para a célula ERRADA — e a rota `/static` de `armadilhas/083` não salva

**Sintoma:** a célula serve sob prefixo (`meshcraft.top/forms/sugestoes/`), você já
pagou a `armadilhas/083` — a rota `re_path(r"^static/…")` está no urlconf, servindo
de `STATICFILES_DIRS[0]` — e a página **continua** chegando sem estilo em produção.
No navegador do visitante, o `<link>` aponta para um endereço que existe e responde
**200**: só que quem responde é **outra célula**.

```
<link rel="stylesheet" href="/static/sugestoes/caixa.css">   <-- o que {% static %} gera
https://meshcraft.top/forms/sugestoes/     -> a Caixa      (PathPrefix /forms/sugestoes)
https://meshcraft.top/static/…             -> o funil      (catch-all PathPrefix /)
```

Em `make ci` tudo verde, e em dev também: sem `SCRIPT_NAME` no ambiente local, o
`{% static %}` e o `{% url %}` devolvem exatamente a mesma string. **A diferença
entre os dois só existe no regime da VPS.**

**Causa — `{% static %}` e `{% url %}` leem prefixos DIFERENTES:**

| tag | de onde tira o prefixo | sob `SCRIPT_NAME` |
|---|---|---|
| `{% url %}` / `reverse()` | prefixo de **thread**, que o `ASGIHandler` preenche a cada requisição (`set_script_prefix`) | leva o prefixo |
| `{% static %}` | `settings.STATIC_URL` | **não** leva |

O Django até tenta ajudar: `django/conf/__init__.py::_add_script_prefix` acrescenta
`get_script_prefix()` a `STATIC_URL`/`MEDIA_URL` — **mas só quando o valor é
relativo**. O `STATIC_URL = "/static/"` de fábrica começa com `/`, então cai no
primeiro `return` e sai intacto:

```python
    @staticmethod
    def _add_script_prefix(value):
        # Don't apply prefix to absolute paths and URLs.
        if value.startswith(("http://", "https://", "/")):
            return value
```

**Não "conserte" tirando a barra** (`STATIC_URL = "static/"`). Duas linhas acima
desse método, o `LazySettings.__getattr__` faz `self.__dict__[name] = val`: o valor
é **cacheado no primeiro acesso**. Qualquer coisa que leia `settings.STATIC_URL`
durante o boot — um check do `staticfiles`, um storage sendo construído — congela
`get_script_prefix()` no valor daquele instante, que antes da primeira requisição é
`"/"`. O bug volta, agora dependendo de ordem de import.

**Solução: a folha de estilo sai de `{% url %}`, como todo o resto da célula.** Dê
`name=` à rota de estático que a `083` já obriga a existir e chame-a pelo nome:

```python
# config/urls.py — o nome é `estatico`, não `static`: `{% url 'static' %}` ao lado
# do `{% static %}` do Django seriam duas coisas diferentes com o mesmo nome.
re_path(r"^static/(?P<caminho>.*)$", servir_estatico, name="estatico"),
```

```django
<link rel="stylesheet" href="{% url 'estatico' caminho='sugestoes/caixa.css' %}">
```

**O guarda, e ele precisa do prefixo LIGADO para morder.** Sem
`set_script_prefix()` — que o servidor faz e os handlers de teste do Django não
(`armadilhas/081`) — as duas tags devolvem a mesma coisa e o teste fica verde para
sempre. Com o prefixo ligado, a varredura de links que a célula já tinha reprova
sozinha:

```
AssertionError: links sem o prefixo público no quadro: ['/static/sugestoes/caixa.css'].
Todo endereço interno sai de {% url %}, nunca escrito à mão.
```

Medido em 25/08/2026: trocar a tag deixa **7 testes vermelhos** na `sugestoes`
(todas as varreduras de `href|action` sob prefixo, mais o guarda dedicado
`test_a_folha_de_estilo_sai_com_o_prefixo_publico`).

**Quem mais está exposto:** toda célula servida sob prefixo — hoje `sugestoes`
(`/forms/sugestoes`), e as demais no dia em que saírem da raiz. A `funil` e a
`checkout` usam `{% static %}`/caminho na raiz e estão certas **por acidente de
endereço**, não por desenho: mover qualquer uma delas para baixo de um prefixo
reproduz este 404-que-não-é-404 inteiro.

**Origem:** despacho `sugestoes/evo-30-o-rosto` (25/08/2026), o PR que deu tela à
Caixa de Sugestões. A `083` foi paga primeiro, a página continuou sem estilo sob
prefixo, e o que fechou foi trocar a TAG — não a rota.
