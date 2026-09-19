# Diagnóstico TAR-458: a exposição do bearer do checkout

Encaminhamento do risco Alto levantado na Parte VIII do
[RELATORIO.md](RELATORIO.md): "bearer estático chega a templates/views de
checkout". Data da medição: 18/09/2026.

## O limite desta tarefa

Isto é diagnóstico, não conserto. Nenhuma credencial real foi lida ou
reproduzida; todo valor citado aqui é sintético e existiu apenas dentro do
processo de teste local. Não houve consulta a produção, transação, ativação de
venda nem alteração de comportamento da aplicação: nenhum arquivo de
`services/checkout/` foi modificado por este trabalho.

`services/checkout/` é caminho CODEOWNERS. A implementação nasce na tarefa
separada citada no fim deste documento, com mandato próprio do mantenedor.

## O mecanismo, lido na fonte

| Onde | O que faz |
| --- | --- |
| [`apps/pedidos/views.py`](../../../services/checkout/apps/pedidos/views.py) | Lê `TOKENS_ACEITOS_PAGINAS` do ambiente no import do módulo e entrega o valor no contexto das três páginas como `api_token`. |
| [`templates/checkout/dados.html`](../../../services/checkout/templates/checkout/dados.html), [`pix.html`](../../../services/checkout/templates/checkout/pix.html), [`cartao.html`](../../../services/checkout/templates/checkout/cartao.html) | Publicam o valor no corpo da resposta com `{{ api_token|json_script:"api-token" }}`. |
| [`static/checkout/api.js`](../../../services/checkout/static/checkout/api.js) | Lê o valor do próprio DOM e o envia em `Authorization: Bearer`. |
| [`apps/core/auth.py`](../../../services/checkout/apps/core/auth.py) | Aceita o token com `token in settings.TOKENS_ACEITOS`. |
| [`config/settings.py`](../../../services/checkout/config/settings.py) | Monta `TOKENS_ACEITOS` como um conjunto único a partir de qualquer variável com prefixo `TOKENS_ACEITOS_`. |
| [`config/api.py`](../../../services/checkout/config/api.py) | Aplica `bearerAuth()` na API inteira, com `security` declarado no contrato congelado. |
| [`infra/traefik/dynamic/plataforma.yml`](../../../infra/traefik/dynamic/plataforma.yml) | Publica na internet tanto `PathPrefix(/checkout)` quanto `PathPrefix(/api/checkout)`, ambos no ponto de entrada `websecure`. |

A exposição já estava registrada como pendência de arquitetura em
[`services/checkout/LICOES.md`](../../../services/checkout/LICOES.md), e o
[`infra/env/checkout.env.exemplo`](../../../infra/env/checkout.env.exemplo)
pede em comentário que o valor seja diferente dos tokens servidor a servidor.
Comentário é o degrau "documento" da Lei 1: nada mede se o pedido foi atendido.

## A fronteira, medida localmente

Seis sondas, todas com credencial sintética, saída verbatim:

```
tests/test_tar458_sonda_bearer.py::test_a_pagina_pix_entrega_o_bearer_a_visitante_anonimo
[pix]    200 sem autenticacao; token no HTML = 'SINTETICO-tar458-token-de-pagina'
PASSED
tests/test_tar458_sonda_bearer.py::test_a_pagina_de_cartao_entrega_o_bearer_a_visitante_anonimo
[cartao] 200 sem autenticacao; token no HTML = 'SINTETICO-tar458-token-de-pagina'
PASSED
tests/test_tar458_sonda_bearer.py::test_o_token_lido_do_html_abre_toda_a_api_interna
[alcance] createSession=201 placeOrder=201 getOrder=200 com o token colhido do HTML
PASSED
tests/test_tar458_sonda_bearer.py::test_a_autenticacao_nao_distingue_o_token_publico_do_servidor_a_servidor
[fronteira] mesma resposta para os dois pares consumidores: {'pagina': 201, 'servidor': 201}
PASSED
tests/test_tar458_sonda_bearer.py::test_a_pagina_de_dados_entrega_o_bearer_a_visitante_anonimo
[dados]  200 sem autenticacao; token no HTML = 'SINTETICO-tar458-token-de-pagina'
PASSED
tests/test_tar458_sonda_bearer.py::test_credencial_ausente_ou_errada_continua_sendo_recusada
[contraprova] sem token=401 token errado=401
PASSED

============================== 6 passed in 0.46s ==============================
```

A sonda foi falsificada antes de valer como prova (Lei 6). Com o token da
página trocado em memória por vazio, que é o efeito do conserto proposto
adiante, a mesma asserção reprova:

```
>       assert colhido == TOKEN_DA_PAGINA
E       AssertionError: assert '' == 'SINTETICO-ta...ken-de-pagina'
1 failed in 0.63s
```

Ou seja: a sonda lê o valor realmente renderizado, não uma constante do teste.

## O alcance da credencial

1. **As três operações da API do checkout.** O valor colhido do HTML autentica
   `createSession`, `placeOrder` e `getOrder`. São exatamente as operações que a
   página já executa em nome do visitante, então o alcance de hoje não excede o
   que um comprador anônimo faz pelo navegador.
2. **Qualquer operação futura, no instante em que nascer.** `TOKENS_ACEITOS` é
   um conjunto plano: `bearerAuth` não sabe qual par consumidor apresentou o
   token. A sonda mostra respostas idênticas para o token publicado no HTML e
   para um token servidor a servidor. Uma rota nova na API do checkout nasce
   alcançável por qualquer visitante, sem que ninguém precise errar.
3. **Rotação exige reinício do processo.** `_API_TOKEN` é lido no import de
   `views.py`. Trocar a variável de ambiente sem recriar o contêiner não troca o
   valor servido.
4. **Fora do checkout, apenas se o valor for reusado.** Nada mecaniza a
   unicidade pedida pelo comentário do env de exemplo. Se o mesmo valor estiver
   em `TOKENS_ACEITOS_<PAR>` de outra célula, o alcance passa a ser o daquela
   célula também. Este ponto não foi medido: exigiria ler segredo real, o que
   esta tarefa proíbe.

## O que a exposição não alcança

Os freios existentes continuam de pé, e é por isso que o achado é Alto e não
Crítico:

- **[INV-P2]** o preço vem do catálogo no fechamento; total enviado pelo cliente
  é ignorado, com token ou sem.
- **[INV-P11]** sessão e pedido são escopados pelo site resolvido do Host; host
  não cadastrado é 404.
- **[INV-P1]** o snapshot é create-only, no `save()` e no `QuerySet.update()`.
- **[INV-P4]** a intent é idempotente pela sessão: repetir não cobra duas vezes.
- **[INV-P8]** o checkout não guarda credencial secreta do provedor de
  pagamento, então o token da página não é ponte para `pagamentos`.
- A contraprova mostra 401 para ausência de token e para valor desconhecido: o
  que falha é a confidencialidade do valor, não o mecanismo de autenticação.

## Modelo de ameaça

**Quem.** Qualquer visitante anônimo da página de checkout, e qualquer
rastreador, extensão de navegador ou captura de tela que leia o código-fonte.
Não é preciso habilidade: "ver código-fonte" basta.

**O que consegue hoje.** Abrir sessões e pedidos em massa pela API, sem passar
pelo formulário, e consultar o status de um pedido cujo identificador conheça.
O identificador é UUID versão 4 e não é enumerável, então a consulta depende de
já possuir o número. O efeito prático é poluição de banco e emissão de eventos
`pedido.criado` sem comprador real, além de intents criadas no provedor de
pagamento.

**O que muda quando a venda for ativada.** A poluição deixa de ser ruído e passa
a contaminar o funil de leads, a mensageria e as métricas, que consomem
`pedido.criado`. Nenhum invariante de dinheiro é violado, mas o custo de separar
pedido real de pedido falso passa a existir.

**O que muda quando a API do checkout crescer.** É aqui que o risco vira
Crítico sem aviso. Uma rota de cancelamento, reembolso, cupom ou relatório
acrescentada à API nasce autenticada pelo token que está no HTML. O autor da
rota nova não tem como perceber: o `auth=bearerAuth()` já está no `NinjaAPI`, e
nada no código diz que aquele conjunto contém um segredo público.

## A alternativa imediata

**Recomendação: degradar o token da página a um par consumidor com alçada
declarada, e negar por padrão.** Existe precedente na casa: a `identidade`
separa "quem chama" de "o que este par pode fazer" com um segundo grau conferido
no handler, contra `settings.TOKENS_COMPLETOS`, sem criar um segundo esquema de
segurança no contrato
([`services/identidade/apps/core/auth.py`](../../../services/identidade/apps/core/auth.py)).
O checkout copia o padrão, não o arquivo: um conjunto `TOKENS_PUBLICOS` montado
das variáveis conhecidamente publicadas no HTML, e uma lista escrita das
operações que um token público alcança, hoje `createSession`, `placeOrder` e
`getOrder`. Operação fora da lista responde 403 ao token público e continua
aberta ao token servidor a servidor.

**Por que esta e não outra.** Ela é a única que fecha o modo de falha que
importa, a rota futura que nasce pública, sem depender de disciplina de quem
escrever essa rota, e sem pedir ao mantenedor nenhuma decisão de produto.

**Impacto.** Nenhum para o comprador: as três operações da página continuam
respondendo o mesmo, o que a sonda já mede. Nenhuma mudança no contrato
congelado `contracts/checkout.openapi.yaml`, porque não nasce esquema de
segurança novo e as três operações existentes não passam a devolver 403.

**Reversão.** Apagar a variável de ambiente `TOKENS_PUBLICOS_PAGINAS` devolve o
comportamento atual sem tocar código, porque um conjunto vazio de tokens
públicos não restringe ninguém. A reversão de código é remover uma função e a
lista de operações.

**O que esta alternativa não resolve, e é dívida declarada.** O valor continua
visível no código-fonte da página. Um token de curto prazo emitido por sessão,
já cogitado no `LICOES.md` da célula, é a resposta completa, e é decisão do
mantenedor porque muda o desenho da página, não só a alçada. A alternativa
recomendada aqui não fecha essa porta: reduz o que passa por ela.

**Fora de escopo, verificado como pergunta, não como conserto.** A página de Pix
e a de cartão são alcançáveis por quem tiver o identificador do pedido, sem
autenticação de pessoa. Isso não decorre do bearer e não foi medido como risco
próprio aqui; fica anotado para quem revisar a jornada de compra.

## Como reproduzir

A sonda não foi versionada, porque `services/checkout/` é CODEOWNERS e esta
tarefa não tem mandato para escrever lá. Ela vira teste-guarda na tarefa de
implementação. Para repetir a medição, grave o arquivo abaixo em
`services/checkout/tests/test_tar458_sonda_bearer.py`, rode, e apague.

```bash
cd services/checkout
DJANGO_SECRET_KEY=teste-sintetico DATABASE_URL="sqlite:///:memory:" \
CATALOGO_API_URL="http://catalogo.teste/api/catalogo" TOKEN_CATALOGO=x \
PAGAMENTOS_API_URL="http://pagamentos.teste/api/pagamentos" TOKEN_PAGAMENTOS=x \
python -m pytest tests/test_tar458_sonda_bearer.py -q -s
```

```python
"""TAR-458 - sonda local de diagnostico. Somente leitura da aplicacao.

Nenhum valor real e lido ou reproduzido: a credencial abaixo e sintetica e
existe so dentro deste processo de teste.
"""

import json
import uuid

import pytest

from apps.pedidos import views as paginas
from apps.pedidos.models import Order, Session
from tests.conftest import HOST_A, OFERTA_A, SITE_A, SLUG

TOKEN_DA_PAGINA = "SINTETICO-tar458-token-de-pagina"
TOKEN_SERVIDOR_A_SERVIDOR = "SINTETICO-tar458-token-servidor"


@pytest.fixture
def credenciais_sinteticas(monkeypatch, settings):
    monkeypatch.setattr(paginas, "_API_TOKEN", TOKEN_DA_PAGINA)
    settings.TOKENS_ACEITOS = {TOKEN_DA_PAGINA, TOKEN_SERVIDOR_A_SERVIDOR}


@pytest.fixture
def pedido_pix(db):
    sessao = Session.objects.create(
        site_id=SITE_A["id"], offer_slug=SLUG, offer=OFERTA_A
    )
    return Order.objects.create(
        id=uuid.uuid4(),
        session=sessao,
        site_id=SITE_A["id"],
        items=[
            {
                "product_id": "prod-x",
                "name": "Curso",
                "price_cents": 990,
                "kind": "principal",
            }
        ],
        total_cents=990,
        customer={"email": "comprador@exemplo.test", "name": "Comprador"},
        method="pix",
        intent_id="intent-sintetico",
        pix={"qr_code": "copia-e-cola-sintetico", "qr_code_base64": "iVBORw0KGgo="},
    )


def _token_no_html(html: str) -> str:
    marca = '<script id="api-token" type="application/json">'
    inicio = html.index(marca) + len(marca)
    fim = html.index("</script>", inicio)
    return json.loads(html[inicio:fim])


def test_a_pagina_de_dados_entrega_o_bearer_a_visitante_anonimo(
    client, rede, credenciais_sinteticas
):
    resposta = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert _token_no_html(html) == TOKEN_DA_PAGINA
    print(f"\n[dados]  200 sem autenticacao; token no HTML = {_token_no_html(html)!r}")


def test_a_pagina_pix_entrega_o_bearer_a_visitante_anonimo(
    client, rede, credenciais_sinteticas, pedido_pix
):
    resposta = client.get(f"/pedido/{pedido_pix.id}/pix/", HTTP_HOST=HOST_A)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert _token_no_html(html) == TOKEN_DA_PAGINA
    print(f"[pix]    200 sem autenticacao; token no HTML = {_token_no_html(html)!r}")


def test_a_pagina_de_cartao_entrega_o_bearer_a_visitante_anonimo(
    client, rede, credenciais_sinteticas, pedido_pix
):
    pedido_pix.method = "card"
    pedido_pix.save()
    resposta = client.get(f"/pedido/{pedido_pix.id}/cartao/", HTTP_HOST=HOST_A)
    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert _token_no_html(html) == TOKEN_DA_PAGINA
    print(f"[cartao] 200 sem autenticacao; token no HTML = {_token_no_html(html)!r}")


def test_o_token_lido_do_html_abre_toda_a_api_interna(
    client, rede, credenciais_sinteticas, pedido_pix
):
    html = client.get(f"/{SLUG}/", HTTP_HOST=HOST_A).content.decode()
    colhido = _token_no_html(html)
    cabecalho = {"HTTP_AUTHORIZATION": f"Bearer {colhido}", "HTTP_HOST": HOST_A}

    sessao = client.post(
        "/api/checkout/sessoes",
        data=json.dumps({"offer_slug": SLUG}),
        content_type="application/json",
        **cabecalho,
    )
    assert sessao.status_code == 201

    pedido = client.post(
        f"/api/checkout/sessoes/{sessao.json()['id']}/pedido",
        data=json.dumps({"customer": {"email": "a@b.test", "name": "A"}, "method": "pix"}),
        content_type="application/json",
        **cabecalho,
    )
    assert pedido.status_code == 201

    consulta = client.get(f"/api/checkout/pedidos/{pedido_pix.id}", **cabecalho)
    assert consulta.status_code == 200
    print(
        "[alcance] createSession=201 placeOrder=201 getOrder=200 "
        "com o token colhido do HTML"
    )


def test_a_autenticacao_nao_distingue_o_token_publico_do_servidor_a_servidor(
    db, client, rede, credenciais_sinteticas
):
    corpo = json.dumps({"offer_slug": SLUG})
    respostas = {}
    for nome, token in (
        ("pagina", TOKEN_DA_PAGINA),
        ("servidor", TOKEN_SERVIDOR_A_SERVIDOR),
    ):
        resposta = client.post(
            "/api/checkout/sessoes",
            data=corpo,
            content_type="application/json",
            HTTP_AUTHORIZATION=f"Bearer {token}",
            HTTP_HOST=HOST_A,
        )
        respostas[nome] = resposta.status_code
    assert respostas["pagina"] == respostas["servidor"] == 201
    print(f"[fronteira] mesma resposta para os dois pares consumidores: {respostas}")


def test_credencial_ausente_ou_errada_continua_sendo_recusada(
    client, rede, credenciais_sinteticas
):
    corpo = json.dumps({"offer_slug": SLUG})
    sem = client.post(
        "/api/checkout/sessoes",
        data=corpo,
        content_type="application/json",
        HTTP_HOST=HOST_A,
    )
    errado = client.post(
        "/api/checkout/sessoes",
        data=corpo,
        content_type="application/json",
        HTTP_AUTHORIZATION="Bearer SINTETICO-tar458-token-que-nao-existe",
        HTTP_HOST=HOST_A,
    )
    assert sem.status_code == 401
    assert errado.status_code == 401
    print(f"[contraprova] sem token={sem.status_code} token errado={errado.status_code}")
```

## Estado da suíte da célula nesta medição

`python -m pytest -q` em `services/checkout`: 60 passaram, 2 ERROR.
Os dois ERROR são de instrumento e vêm declarados pelo próprio teste:
`test_reentrega_pel.py` exige um Redis real e a variável `REDIS_STREAMS_URL`
não existe nesta bancada, aberta com `--sem-container`. Não é reprovação de
teste e não foi introduzido por este trabalho.

## O que fica pendente

A implementação está na tarefa TAR-478, aberta por este mesmo PR, que só começa
com mandato específico do mantenedor porque toca caminho CODEOWNERS. Este
documento não altera comportamento, não fecha o achado da Parte VIII e não
autoriza ativação de venda.
