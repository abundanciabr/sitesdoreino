# apps/sites/menu.py  # [RECEITA:R7 v1]
"""O menu do topo de um site: a REGRA de coerência, num lugar só.

Por que o menu mora no catálogo, e não na célula que o desenha: o menu é DADO
DO SITE, como os idiomas e a oferta padrão. As células públicas (funil, forum)
já perguntam "quem é este host?" ao catálogo uma vez por requisição, com cache
de 60s. Pendurar o menu nessa resposta faz o dado novo chegar às telas sem
nenhum salto de rede a mais, sem célula nova, e sem ninguém ler o banco de
ninguém (Lei 3).

A forma segue o precedente de `languages` (PLANO-I18N D3): JSON validado por
uma função ÚNICA, chamada pelo `save()` do model e pelo `update()` do
queryset. Regra escrita duas vezes é regra que diverge, e aqui os dois
caminhos de escrita existem de verdade (a tela do Admin grava pelo model; uma
correção em massa gravaria pelo queryset).

VOCABULÁRIO, em português de quem configura:

  versão   um menu inteiro, com nome ("Menu completo", "Menu enxuto"). Um site
           pode ter várias; é isso que faz "em outras páginas tem menu mas ele
           é diferente".
  item     uma opção da versão: para onde vai, como se chama em cada idioma, e
           para quem aparece.
  página   a regra "esta página usa esta versão". Versão vazia ("") é a página
           SEM MENU NENHUM, a outra metade do pedido do mantenedor.
  padrão   a versão que vale para toda página sem regra própria. Vazio quer
           dizer que o site inteiro nasce sem menu, e cada página que quiser um
           o declara.
"""

import re

from django.core.exceptions import ValidationError

# O apelido de uma versão aparece na configuração, nunca numa URL, mas é a
# chave que liga página a versão: precisa ser estável e legível para quem abrir
# o JSON no dia em que algo estiver estranho.
SLUG_DE_VERSAO = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")

# A mesma forma que `normalizar_idiomas` aceita, de propósito: o rótulo é por
# idioma, e "por idioma" nesta plataforma quer dizer BCP 47 minúsculo.
CODIGO_DE_IDIOMA = re.compile(r"^[a-z]{2}(-[a-z]{2})?$")

# A chave de uma página é `<celula>/<rota>`, exatamente como o par
# (celula, rota) de `painel/mapa-do-site.json`, que é a lista única de
# endereços do projeto e é dela que a tela do Admin oferece as opções. A rota
# da página inicial é vazia, então `funil/` é uma chave legítima.
CHAVE_DE_PAGINA = re.compile(r"^[a-z][a-z0-9_-]*/\S*$")

# Para quem o item aparece. A tela do Admin oferece exatamente estes em
# português, e um valor a mais sem tela que o escreva seria dado que só nasce
# torto — por isso os dois lados mudam no MESMO PR.
#
# `staff` entrou em 03/09/2026, com o Rito de Contrato do PR #890: o mantenedor
# pediu um atalho para a área de administração visível só para quem é da equipe.
# Ele sai do campo `papel` da sessão (contrato da `identidade`, schema
# `Session`), que é de EXIBIÇÃO — esconder um item nunca é autorizar nada, e
# quem barra a entrada continua sendo a porta fail-closed da célula dona do
# recurso.
#
# **Quem CONSOME esta lista tem uma obrigação, e ela está escrita no contrato:**
# plateia que o consumidor não reconhecer deve ser ESCONDIDA, nunca mostrada a
# todos. Sem isso, acrescentar um valor aqui vazaria o item durante a janela em
# que um consumidor ainda não subiu. As quatro células aprenderam isso no #887,
# que entrou antes do contrato de propósito.
PLATEIAS = ("everyone", "logged_out", "logged_in", "staff")

MAXIMO_DE_VERSOES = 20
MAXIMO_DE_ITENS = 20
MAXIMO_DE_PAGINAS = 200
TAMANHO_DO_NOME = 60
TAMANHO_DO_ROTULO = 40
TAMANHO_DO_ENDERECO = 300

# Endereço externo só nas duas formas que um navegador abre com segurança. A
# recusa é a cerca que impede `javascript:` de virar um item de menu gravado, e
# ela mora AQUI, na escrita, não na tela: a tela é uma porta, o dado é o que
# sobrevive a ela (fail-closed na borda, Retrospectiva §4).
ESQUEMAS_EXTERNOS = ("https://", "http://")


def _texto(valor, onde: str, tamanho: int) -> str:
    if not isinstance(valor, str):
        raise ValidationError(f"{onde} precisa ser texto, veio {valor!r}.")
    limpo = valor.strip()
    if len(limpo) > tamanho:
        raise ValidationError(f"{onde} passa de {tamanho} caracteres.")
    return limpo


def _endereco(valor):
    """Devolve `(endereço, é_interno)`, ou recusa.

    Interno é o que começa com uma barra só (`/forum`); `//outro.site` é
    endereço externo disfarçado de caminho, e é justamente por isso que ele é
    recusado aqui em vez de tratado como interno.
    """
    bruto = _texto(valor, "o endereço do item", TAMANHO_DO_ENDERECO)
    if not bruto:
        raise ValidationError("item de menu sem endereço.")
    if bruto.startswith("//"):
        raise ValidationError(
            f"endereço {bruto!r} começa com duas barras, isso é um site de fora "
            f"escrito como se fosse página daqui. Escreva o endereço completo, "
            f"com https://, ou uma barra só."
        )
    if bruto.startswith("/"):
        return bruto, True
    if bruto.startswith(ESQUEMAS_EXTERNOS):
        return bruto, False
    raise ValidationError(
        f"endereço {bruto!r} não é aceito: comece com uma barra (uma página "
        f"deste site) ou com https:// (um site de fora)."
    )


def _rotulos(valor, onde: str) -> dict:
    if not isinstance(valor, dict) or not valor:
        raise ValidationError(f"{onde} precisa de pelo menos um nome escrito.")
    saida = {}
    for codigo, texto in valor.items():
        if not isinstance(codigo, str) or not CODIGO_DE_IDIOMA.match(codigo.lower()):
            raise ValidationError(
                f"{onde}: {codigo!r} não é um código de idioma como 'pt-br', "
                f"'en' ou 'es'."
            )
        nome = _texto(texto, f"{onde} em {codigo}", TAMANHO_DO_ROTULO)
        if not nome:
            raise ValidationError(f"{onde} em {codigo} ficou vazio.")
        saida[codigo.lower()] = nome
    return dict(sorted(saida.items()))


def _item(bruto, onde: str) -> dict:
    if not isinstance(bruto, dict):
        raise ValidationError(f"{onde} precisa ser um objeto, veio {bruto!r}.")
    endereco, interno = _endereco(bruto.get("url"))

    # `localized` diz "este endereço tem uma versão no idioma de quem está
    # lendo". Quem serve a página é que sabe prefixar (`/es/cadastro`), e só
    # sabe fazê-lo para as próprias rotas: um link para OUTRA célula segue cru
    # e monolíngue enquanto o D6 não estiver no gateway (R12). Endereço externo
    # nunca é traduzido, e a coerção mora aqui para o dado não guardar uma
    # combinação impossível.
    localized = bruto.get("localized", interno)
    if not isinstance(localized, bool):
        raise ValidationError(f"{onde}: 'localized' precisa ser true/false.")
    if not interno:
        localized = False

    audience = bruto.get("audience", "everyone")
    if audience not in PLATEIAS:
        raise ValidationError(
            f"{onde}: 'audience' precisa ser um de {list(PLATEIAS)}, veio "
            f"{audience!r}."
        )

    new_tab = bruto.get("new_tab", False)
    if not isinstance(new_tab, bool):
        raise ValidationError(f"{onde}: 'new_tab' precisa ser true/false.")

    return {
        "url": endereco,
        "labels": _rotulos(bruto.get("labels"), f"{onde}: o nome do item"),
        "localized": localized,
        "audience": audience,
        "new_tab": new_tab,
    }


def _versao(bruto, indice: int) -> dict:
    onde = f"a versão nº {indice + 1} do menu"
    if not isinstance(bruto, dict):
        raise ValidationError(f"{onde} precisa ser um objeto, veio {bruto!r}.")

    slug = _texto(bruto.get("slug"), f"o apelido de {onde}", 40).lower()
    if not SLUG_DE_VERSAO.match(slug):
        raise ValidationError(
            f"o apelido {slug!r} não serve: use letras minúsculas, números e "
            f"hífen (ex.: 'completo', 'so-o-essencial')."
        )

    nome = _texto(bruto.get("name"), f"o nome de {onde}", TAMANHO_DO_NOME)
    if not nome:
        raise ValidationError(f"{onde} precisa de um nome, é o que você lê na tela.")

    itens = bruto.get("items")
    if not isinstance(itens, list):
        raise ValidationError(f"{onde}: 'items' precisa ser uma lista.")
    if len(itens) > MAXIMO_DE_ITENS:
        raise ValidationError(
            f"{onde} tem {len(itens)} itens, e o teto é {MAXIMO_DE_ITENS}. Um menu "
            f"maior que isso não cabe num celular, que é onde o site é lido."
        )

    return {
        "slug": slug,
        "name": nome,
        "items": [
            _item(item, f"o item nº {i + 1} de {onde}") for i, item in enumerate(itens)
        ],
    }


def normalizar_menu(bruto) -> dict:
    """Valida e devolve o menu na forma canônica, ou levanta `ValidationError`.

    Canônica quer dizer: toda chave explícita, sem depender de ninguém lembrar
    o padrão do contrato. É o que faz a comparação de "mudou?" ser um `!=`
    honesto, e é a mesma escolha de `normalizar_idiomas`.

    Menu ausente é `{}`, e continua passando intocado por aqui: é isso que
    mantém a resposta de um site sem menu byte a byte igual à de antes.
    """
    if not bruto:
        return {}
    if not isinstance(bruto, dict):
        raise ValidationError(f"o menu precisa ser um objeto, veio {bruto!r}.")

    versoes_brutas = bruto.get("versions") or []
    if not isinstance(versoes_brutas, list):
        raise ValidationError("'versions' precisa ser uma lista de versões.")
    if len(versoes_brutas) > MAXIMO_DE_VERSOES:
        raise ValidationError(
            f"{len(versoes_brutas)} versões de menu, e o teto é {MAXIMO_DE_VERSOES}."
        )

    versoes = []
    apelidos = set()
    for indice, item in enumerate(versoes_brutas):
        versao = _versao(item, indice)
        if versao["slug"] in apelidos:
            raise ValidationError(
                f"duas versões com o mesmo apelido {versao['slug']!r}. O apelido "
                f"é o que liga a página à versão, então ele precisa ser único."
            )
        apelidos.add(versao["slug"])
        versoes.append(versao)

    padrao = _texto(bruto.get("default_version", ""), "a versão padrão", 40).lower()
    if padrao and padrao not in apelidos:
        raise ValidationError(
            f"a versão padrão {padrao!r} não existe. Versões disponíveis: "
            f"{sorted(apelidos) or 'nenhuma'}."
        )

    paginas_brutas = bruto.get("pages") or []
    if not isinstance(paginas_brutas, list):
        raise ValidationError("'pages' precisa ser uma lista de regras por página.")
    if len(paginas_brutas) > MAXIMO_DE_PAGINAS:
        raise ValidationError(
            f"{len(paginas_brutas)} regras de página, e o teto é {MAXIMO_DE_PAGINAS}."
        )

    paginas = []
    vistas = set()
    for regra in paginas_brutas:
        if not isinstance(regra, dict):
            raise ValidationError(
                f"cada regra de página é um objeto {{page, version}}, veio {regra!r}."
            )
        chave = _texto(regra.get("page"), "a chave da página", 120)
        if not CHAVE_DE_PAGINA.match(chave):
            raise ValidationError(
                f"a página {chave!r} não está na forma 'celula/rota', como "
                f"'funil/' (a página inicial) ou 'funil/login'."
            )
        if chave in vistas:
            raise ValidationError(
                f"a página {chave!r} aparece duas vezes, com regras que podem "
                f"discordar. Deixe uma só."
            )
        vistas.add(chave)
        versao = _texto(regra.get("version", ""), f"a versão de {chave}", 40).lower()
        if versao and versao not in apelidos:
            raise ValidationError(
                f"a página {chave!r} aponta para a versão {versao!r}, que não "
                f"existe. Versões disponíveis: {sorted(apelidos) or 'nenhuma'}."
            )
        paginas.append({"page": chave, "version": versao})

    if not versoes and not paginas and not padrao:
        return {}

    paginas.sort(key=lambda regra: regra["page"])
    return {"default_version": padrao, "versions": versoes, "pages": paginas}
