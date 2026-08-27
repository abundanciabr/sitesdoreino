# Teste de ROTA que prova a rota pelo CONTEÚDO da página quebra quando a página muda — e a rota não mudou

**Sintoma:** você mexe numa página (troca o que ela mostra) e ficam vermelhos
testes que não têm nada a ver com ela — a matriz de idioma, o roteamento, a
varredura de estáticos:

```
FAILED tests/test_i18n_http.py::test_raiz_com_query_nao_perde_a_query_nem_redireciona
FAILED tests/test_i18n_http.py::test_cada_idioma_serve_a_pagina_no_seu_caminho[en]
FAILED tests/test_static_em_producao.py::test_todo_estatico_que_a_pagina_PEDE_e_realmente_servido[/pt-br/-meshcraft.top]
E       AssertionError: /pt-br/ não pediu nenhum estático — o scanner cegou
```

Nenhuma rota foi tocada. O resolver continua servindo `/pt-br/` em português,
a query continua chegando inteira, e todo estático que a página pede continua
sendo servido — só que a página parou de imprimir a UTM, parou de mostrar o
nome do produto e parou de carregar o `api.js`.

**Causa:** o teste media a propriedade CERTA por um sinal EMPRESTADO da página.
"A query chega inteira" era provado por `b'"utm_source": "ig"' in resp.content`
— o eco de `{{ utm|json_script }}`. "Cada idioma serve a página no seu caminho"
era provado pelo nome do produto no HTML — que, ironicamente, é DADO e é igual
nos três idiomas: o teste passaria com o resolver servindo sempre o inglês, e
reprovava quando a vitrine virou porta.

É a forma barata de escrever um teste de roteamento: a página está ali, tem
texto, e comparar string é fácil. O preço só aparece um mês depois, e aparece
como **falso vermelho** — o pior tipo, porque ensina o próximo agente que
"mudar página quebra o roteamento" e o convida a afrouxar o guarda para
destravar o PR.

**Solução:** meça a propriedade uma camada antes do HTML — no ponto em que ela
existe de verdade.

- **Query/caminho chegaram à view?** Um espião no lugar da view, atravessando o
  middleware real, não o eco no template:

  ```python
  chegou = {}

  def espiao(request):
      chegou["query"] = request.META.get("QUERY_STRING")
      chegou["path_info"] = request.path_info
      return HttpResponse("ok")

  SiteResolutionMiddleware(espiao)(RequestFactory().get("/", {"utm_source": "ig"}))
  assert chegou == {"query": "utm_source=ig", "path_info": "/"}
  ```

- **Veio no idioma certo?** Compare com o CATÁLOGO de tradução resolvido
  naquele idioma (`t("landing.entrar", idioma)`), nunca com um dado que é igual
  nos três — o teste antigo passaria com o resolver quebrado.

- **Instrumentação anti-cegueira (`assert achados, "o scanner cegou"`):** ancore
  no ESCOPO em que a afirmação é verdadeira. "Toda página pede algum estático"
  não é invariante — uma página legitimamente deixa de carregar script. "O site
  inteiro não pode parar de pedir estático de uma vez" é. Varra a lista, some,
  e afirme sobre a soma:

  ```python
  achados = 0
  for caminho, host in PAGINAS_VARRIDAS:
      pedidos = RE_ESTATICO_PEDIDO.findall(cliente.get(caminho, ...))
      achados += len(pedidos)
      for url in pedidos: ...      # a prova por página continua de pé
  assert achados, "nenhuma página pediu estático — o scanner cegou"
  ```

**A pergunta de bolso, antes de escrever a asserção:** *se amanhã alguém
reescrever esta página inteira sem tocar em rota nenhuma, este teste deve ficar
vermelho?* Se a resposta é não e ele ficaria, o sinal está emprestado.

**O caso legítimo, que não é este:** teste cujo OBJETO é a página (a home mostra
o convite para entrar; a landing monolíngua é byte-idêntica) — ali o conteúdo
**é** a propriedade, e amarrar nele é o certo.

**Origem:** despacho funil/home-nova (27/08/2026) — a raiz do meshcraft.top
deixou de ser vitrine de oferta e virou porta. Quatro guardas de roteamento e
estáticos ficaram vermelhos sem nenhuma rota ter mudado.
