"""`/admin/menu/` — onde o mantenedor decide o menu do topo do site.

Pedido dele em 31/08/2026: *"quero que em algumas páginas não tenha o menu e em
outras tenha mas seja diferente, dai preciso poder configurar ele no painel de
controle"*.

## Onde o dado mora, e por que não aqui

O menu é DADO DO SITE, e dado de site mora na célula `catalogo`, que é o
registro canônico do multissítio. Esta tela não guarda nada: ela lê o menu do
catálogo, aplica UM gesto, e grava o documento inteiro de volta. Guardar uma
cópia aqui seria o mesmo fato em dois lugares, que é a lei anti-duplicação do
`CLAUDE.md`, e no dia em que as duas discordassem o site mostraria uma coisa e
esta tela outra.

Qual site? O do domínio pelo qual a requisição chegou (`request.get_host()`).
Nada de lista para escolher: [INV-P11] já manda o site sair do host, e assim
quem abrir `/admin` de outro domínio configura o menu daquele site sem escolher
nada.

## Por que a tela é de formulários simples, sem script

Cada gesto é um POST que recarrega a página. Não há ilha, não há framework, não
há estado no navegador. Três razões, nesta ordem:

1. **O que se vê é o que está gravado.** Um editor no cliente teria um botão de
   salvar e uma janela entre o que a tela mostra e o que o site serve.
2. **A política de segurança desta área é apertada de propósito.** Cada script
   embutido exige um hash na CSP (`armadilhas/199`), e uma tela que é
   formulário não precisa de nenhum.
3. **O mantenedor é leigo.** Um botão por gesto, com o nome do gesto escrito
   nele, não tem como ser mal entendido.

O preço é uma volta ao servidor por gesto, e ele é barato: configurar um menu é
coisa de uma vez por mês, não de uma vez por segundo.

## De onde vem a lista de páginas

De `painel/mapa-do-site.json`, o mesmo arquivo de `/admin/mapa/`, nunca de uma
lista escrita à mão aqui. Página nova aparece nesta tela sozinha, sem ninguém
lembrar de atualizar uma segunda lista. É a lei anti-duplicação outra vez, e é
o caso em que ela já cobrou caro nesta casa (a Classe 8, mapa velho).
"""

from __future__ import annotations

import json
import re
import unicodedata

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient
from .mapa_do_site import _e_molde, arquivo_do_mapa
from .views import _auditar

# As células que DESENHAM o menu. Uma página da área administrativa ou uma rota
# de máquina não tem topo de site para configurar, e oferecê-la aqui seria
# convidar a uma regra que nunca teria efeito.
#
# ESTA LISTA CRESCE JUNTO COM AS CÉLULAS QUE MOSTRAM O MENU, e esquecê-la é o
# defeito que ela mesma documenta: em 31/08/2026 a `sugestoes` passou a desenhar
# o menu e ficou de fora daqui por uma linha — o menu aparecia na Caixa e o
# mantenedor não tinha onde configurá-lo. Célula que ganha o menu entra aqui no
# MESMO PR, e `tests/test_celulas_com_menu.py` mede a lista contra as células
# que de fato o desenham (o caminho citado aqui até 02/09/2026,
# `ci/tests/test_menu_no_admin.py`, nunca existiu).
#
# A `admin` entrou em 02/09/2026, e ela é o caso estranho: até aqui esta célula
# só CONFIGURAVA o menu. Agora ela também o DESENHA, nas duas páginas públicas
# dela (`/docs/`), por `apps/core/barra_do_site.py` — arquivo com nome próprio
# justamente porque `apps/core/menu.py` é esta tela, e os dois nomes juntos
# confundiriam para sempre quem chegasse depois.
#
# A `cursos` entrou em 05/09/2026, com a sala do aluno (degrau 1.8): o mapa das
# portas e a aula desenham o menu por `apps/core/menu.py` de lá, no molde da
# `gamificacao`.
#
# A `pages` entrou em 06/09/2026, com a Prancheta do aluno (degrau 06 do
# portfólio), pelo mesmo molde. Ela oferece UMA página, `/pages/`, e esse único
# botão manda nas duas caras do endereço: a tela de quem foi reconhecido e as
# três telas de recusa da porta. É de propósito, e está medido no guarda
# `services/pages/tests/test_menu_do_topo.py`: as telas da porta são desenhadas
# antes de a rota ser resolvida, e dar a elas uma chave própria criaria um botão
# que ESTA tela nunca mostraria, porque as opções daqui saem do mapa do site.
CELULAS_COM_MENU = (
    "funil",
    "forum",
    "sugestoes",
    "gamificacao",
    "admin",
    "cursos",
    "pages",
)

# Para quem o item aparece, com o nome que o mantenedor lê. A ordem é a da
# tela; os códigos são os do contrato.
PLATEIAS = (
    ("everyone", "Todo mundo"),
    ("logged_out", "Só quem ainda não entrou"),
    ("logged_in", "Só quem já entrou"),
    # 03/09/2026. O rótulo diz EQUIPE, e não "administradores", porque é a
    # verdade: quem decide é a lista `IDENTIDADE_STAFF_EMAILS` do servidor, a
    # mesma que faz o site reconhecer alguém como equipe. Normalmente ela tem o
    # mesmo conteúdo da lista de quem entra em `/admin`, mas são decisões
    # separadas de propósito (ver `infra/env/identidade.env.exemplo`) — e um
    # rótulo que prometesse "administradores" mentiria no dia em que elas
    # divergissem, com um professor vendo um atalho que lhe devolve 404.
    ("staff", "Só quem é da equipe"),
)

# Os três estados de uma regra de página, no vocabulário do formulário. O do
# meio é a ausência de regra, e ele precisa de um valor próprio: sem ele, "usar
# o padrão" e "sem menu" seriam a mesma caixa vazia.
USAR_O_PADRAO = "__padrao__"
SEM_MENU = "__nenhum__"


def _mapa_de_paginas() -> list:
    """As páginas públicas que podem ter menu, lidas do mapa do site.

    Devolve lista vazia quando o mapa não veio na imagem. A tela então diz
    isso, em vez de oferecer um formulário sem opções, que se leria como "este
    site não tem páginas" — o falso-verde do padrão 1 da RETROSPECTIVA-FASE-D.
    """
    caminho = arquivo_do_mapa()
    if caminho is None:
        return []
    try:
        dados = json.loads(caminho.read_text(encoding="utf-8"))
        entradas = dados["enderecos"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError):
        return []

    paginas = []
    for entrada in entradas:
        if entrada.get("celula") not in CELULAS_COM_MENU:
            continue
        if entrada.get("alcance") != "publico":
            continue
        if entrada.get("gesto"):
            continue  # não é página: é o que acontece ao apertar um botão
        if entrada.get("para_quem") not in ("visitante", "aluno"):
            continue
        paginas.append(
            {
                "chave": f"{entrada['celula']}/{entrada['rota']}",
                "endereco": entrada.get("endereco", ""),
                "titulo": entrada.get("titulo", ""),
                "descricao": entrada.get("descricao", ""),
                "celula": entrada["celula"],
                # Só a célula que serve a própria página sabe pôr o prefixo do
                # idioma no caminho (R12). Guardar isso no item, na hora de
                # criá-lo, poupa o mantenedor de entender a regra.
                "traduzida": entrada["celula"] == "funil",
                # `/forum/t/<int:topico_id>` NÃO é um lugar: é a forma de todos
                # os assuntos do fórum. Ela pode ter regra de menu (todas as
                # conversas mostram o mesmo topo), mas não pode virar DESTINO de
                # um item — seria um link para 404. A regra é a mesma de
                # `/admin/mapa/`, e por isso ela é IMPORTADA de lá em vez de
                # reescrita: duas cópias divergiriam no primeiro molde novo.
                "molde": _e_molde(entrada.get("endereco", "")),
            }
        )
    paginas.sort(key=lambda p: (p["celula"], p["endereco"]))
    return paginas


def _idiomas_do_site(site: dict) -> list:
    """Os idiomas em que o menu precisa de nome. Site monolíngue devolve um só.

    Sai do próprio site, e não de uma lista aqui: acrescentar um idioma é mudar
    um dado no catálogo, e esta tela tem de crescer junto, sozinha.
    """
    codigos = [i.get("code") for i in site.get("languages") or [] if i.get("code")]
    padrao = site.get("default_language") or ""
    if not codigos:
        return [padrao or "pt-br"]
    if not padrao:
        padrao = codigos[0]
    # O padrão primeiro: é o campo que o mantenedor preenche sempre, e o único
    # que importa de verdade (os outros recuam para ele quando faltam).
    return [padrao] + [c for c in codigos if c != padrao]


def _apelido(texto: str) -> str:
    """Um nome que gente escreveu vira um apelido que a máquina liga.

    O mantenedor digita "Menu completo"; a regra de página precisa de
    "menu-completo". Pedir os dois seria pedir a ele que entendesse a diferença.
    """
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c)).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo).strip("-")
    return limpo[:40] or "menu"


def _versao(menu: dict, apelido: str) -> "dict | None":
    for v in menu.get("versions") or []:
        if v.get("slug") == apelido:
            return v
    return None


def _contexto(request, site, menu, erro="", recado=""):
    paginas = _mapa_de_paginas()
    regras = {r["page"]: r["version"] for r in menu.get("pages") or []}
    versoes = menu.get("versions") or []
    padrao = menu.get("default_version") or ""
    idiomas = _idiomas_do_site(site)

    for pagina in paginas:
        # Três estados possíveis, e a tela os mostra por extenso: segue o
        # padrão do site, usa uma versão nomeada, ou não tem menu nenhum.
        if pagina["chave"] not in regras:
            pagina["escolha"] = USAR_O_PADRAO
        elif regras[pagina["chave"]] == "":
            pagina["escolha"] = SEM_MENU
        else:
            pagina["escolha"] = regras[pagina["chave"]]

    for versao in versoes:
        for indice, item in enumerate(versao.get("items") or []):
            item["indice"] = indice
            item["nome"] = (item.get("labels") or {}).get(idiomas[0]) or next(
                iter((item.get("labels") or {}).values()), ""
            )
            item["plateia"] = dict(PLATEIAS).get(
                item.get("audience", "everyone"), "Todo mundo"
            )

    return {
        "admin": request.admin,
        "site": site,
        "versoes": versoes,
        "padrao": padrao,
        "paginas": paginas,
        "idiomas": idiomas,
        "plateias": PLATEIAS,
        "usar_o_padrao": USAR_O_PADRAO,
        "sem_menu": SEM_MENU,
        "erro": erro,
        "recado": recado,
    }


def _carregar(request):
    """O site e o menu de hoje, ou `(None, None)` quando não deu para perguntar."""
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    if site is None:
        return None, None
    return site, site.get("menu") or {}


@require_GET
def menu_do_topo(request):
    """A tela. Fail-OPEN: catálogo mudo vira aviso honesto, nunca 500."""
    site, menu = _carregar(request)
    if site is None:
        return render(
            request,
            "admin/menu.html",
            {"admin": request.admin, "sem_catalogo": True},
        )
    return render(
        request,
        "admin/menu.html",
        _contexto(request, site, menu, recado=request.GET.get("recado", "")),
    )


def _gravar(request, site, menu, detalhe: str):
    """Grava o documento inteiro e volta para a tela com o que aconteceu.

    Padrão POST-redirect-GET: sem ele, um F5 depois de salvar repetiria o
    gesto, e "adicionar item" repetido é um menu com o item em dobro.
    """
    situacao, frase = CatalogoClient().gravar_menu(site["id"], menu)
    if situacao == CatalogoClient.OK:
        _auditar(request, Registro.EDITAR_MENU, str(site["id"]), Registro.OK, detalhe)
        return HttpResponseRedirect(f"{reverse('menu_do_topo')}?recado=salvo")

    desfecho = (
        Registro.RECUSADO_PELA_CELULA
        if situacao == CatalogoClient.RECUSADO
        else Registro.NAO_RESPONDEU
    )
    _auditar(request, Registro.EDITAR_MENU, str(site["id"]), desfecho, detalhe)
    # A tela volta com o menu COMO ESTÁ GRAVADO, não com o que foi recusado:
    # mostrar o rascunho recusado faria a página discordar do site.
    return render(
        request,
        "admin/menu.html",
        _contexto(request, site, site.get("menu") or {}, erro=frase),
        status=422 if situacao == CatalogoClient.RECUSADO else 503,
    )


def _sem_catalogo(request):
    return render(
        request,
        "admin/menu.html",
        {"admin": request.admin, "sem_catalogo": True},
        status=503,
    )


@require_POST
def menu_criar_versao(request):
    """Uma versão nova, vazia. Ela só aparece no site quando alguma página a usa."""
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    nome = (request.POST.get("nome") or "").strip()
    if not nome:
        return _erro(request, site, menu, "Escreva um nome para a versão do menu.")

    apelido = _apelido(nome)
    if _versao(menu, apelido) is not None:
        return _erro(request, site, menu, f"Já existe uma versão chamada {nome!r}.")

    menu = _menu_editavel(menu)
    menu["versions"].append({"slug": apelido, "name": nome, "items": []})
    if not menu["default_version"]:
        # A primeira versão vira a padrão sozinha: uma versão criada e nenhuma
        # página usando-a seria uma tela que "não fez nada" aos olhos de quem
        # acabou de criá-la.
        menu["default_version"] = apelido
    return _gravar(request, site, menu, f"criou a versão {apelido}")


@require_POST
def menu_apagar_versao(request):
    """Apaga uma versão E as regras que apontavam para ela, na mesma escrita.

    As duas coisas juntas, e não em dois gestos, porque o catálogo recusa (com
    razão) uma página apontando para versão que não existe: separá-las deixaria
    a tela num estado que nenhuma gravação aceita.
    """
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    apelido = (request.POST.get("versao") or "").strip()
    menu = _menu_editavel(menu)
    menu["versions"] = [v for v in menu["versions"] if v.get("slug") != apelido]
    menu["pages"] = [r for r in menu["pages"] if r.get("version") != apelido]
    if menu["default_version"] == apelido:
        menu["default_version"] = ""
    return _gravar(request, site, menu, f"apagou a versão {apelido}")


@require_POST
def menu_versao_padrao(request):
    """Qual versão vale para toda página que não tem regra própria."""
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    escolha = (request.POST.get("versao") or "").strip()
    menu = _menu_editavel(menu)
    menu["default_version"] = "" if escolha == SEM_MENU else escolha
    return _gravar(request, site, menu, f"versão padrão = {menu['default_version']!r}")


@require_POST
def menu_adicionar_item(request):
    """Uma opção nova numa versão, no fim da fila."""
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    apelido = (request.POST.get("versao") or "").strip()
    menu = _menu_editavel(menu)
    versao = _versao(menu, apelido)
    if versao is None:
        return _erro(request, site, menu, "Essa versão do menu não existe mais.")

    # O endereço vem de UMA das duas caixas: a lista de páginas do site, ou o
    # campo de endereço de fora. A lista traz junto a resposta sobre idioma, e
    # é por isso que ela é a primeira opção da tela.
    destino = (request.POST.get("pagina") or "").strip()
    traduzido = True
    if destino == "__externo__":
        destino = (request.POST.get("endereco") or "").strip()
        traduzido = False
    else:
        paginas = {p["endereco"]: p for p in _mapa_de_paginas()}
        escolhida = paginas.get(destino)
        traduzido = bool(escolhida and escolhida["traduzida"])

    if not destino:
        return _erro(request, site, menu, "Diga para onde este item leva.")
    if _e_molde(destino):
        # Cinto e suspensório: a tela já não oferece molde na lista, mas um POST
        # montado à mão não passa por ela. Um item apontando para um molde é um
        # link para 404 no topo de toda página.
        return _erro(
            request,
            site,
            menu,
            "Esse endereço vale para várias páginas ao mesmo tempo, então ele "
            "não serve como opção de menu: um visitante que clicasse nele veria "
            "uma página inexistente.",
        )

    rotulos = {}
    for idioma in _idiomas_do_site(site):
        texto = (request.POST.get(f"rotulo_{idioma}") or "").strip()
        if texto:
            rotulos[idioma] = texto
    if not rotulos:
        return _erro(
            request,
            site,
            menu,
            "Escreva pelo menos o nome do item no idioma principal.",
        )

    versao["items"].append(
        {
            "url": destino,
            "labels": rotulos,
            "localized": traduzido,
            "audience": (request.POST.get("plateia") or "everyone").strip(),
            "new_tab": request.POST.get("aba_nova") == "sim",
        }
    )
    return _gravar(request, site, menu, f"acrescentou item em {apelido}")


@require_POST
def menu_remover_item(request):
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    apelido = (request.POST.get("versao") or "").strip()
    menu = _menu_editavel(menu)
    versao = _versao(menu, apelido)
    if versao is None:
        return _erro(request, site, menu, "Essa versão do menu não existe mais.")

    indice = _indice(request.POST.get("indice"), versao["items"])
    if indice is None:
        return _erro(request, site, menu, "Esse item já não está mais aí.")
    versao["items"].pop(indice)
    return _gravar(request, site, menu, f"removeu item de {apelido}")


@require_POST
def menu_mover_item(request):
    """Sobe ou desce um item. A ordem da lista é a ordem na tela do site."""
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    apelido = (request.POST.get("versao") or "").strip()
    menu = _menu_editavel(menu)
    versao = _versao(menu, apelido)
    if versao is None:
        return _erro(request, site, menu, "Essa versão do menu não existe mais.")

    itens = versao["items"]
    indice = _indice(request.POST.get("indice"), itens)
    if indice is None:
        return _erro(request, site, menu, "Esse item já não está mais aí.")

    destino = indice - 1 if request.POST.get("para") == "cima" else indice + 1
    if not 0 <= destino < len(itens):
        # Primeiro item subindo, ou último descendo: não é erro, é o fim da
        # fila. Volta para a tela sem escrever nada.
        return HttpResponseRedirect(reverse("menu_do_topo"))
    itens[indice], itens[destino] = itens[destino], itens[indice]
    return _gravar(request, site, menu, f"moveu item em {apelido}")


@require_POST
def menu_regras_das_paginas(request):
    """As regras de TODAS as páginas de uma vez, num formulário só.

    Um botão por página seria um botão por linha numa tela com dezenas delas.
    Aqui o mantenedor escolhe o que quiser e salva uma vez, que é como um
    formulário se comporta em qualquer outro lugar da vida dele.
    """
    site, menu = _carregar(request)
    if site is None:
        return _sem_catalogo(request)

    menu = _menu_editavel(menu)
    regras = []
    for pagina in _mapa_de_paginas():
        escolha = (request.POST.get(f"pagina_{pagina['chave']}") or "").strip()
        if not escolha or escolha == USAR_O_PADRAO:
            continue  # sem regra própria: a página segue a versão padrão
        regras.append(
            {
                "page": pagina["chave"],
                "version": "" if escolha == SEM_MENU else escolha,
            }
        )
    menu["pages"] = regras
    return _gravar(request, site, menu, f"{len(regras)} regra(s) de página")


# ---------------------------------------------------------------------------
# Peças pequenas, compartilhadas pelos gestos
# ---------------------------------------------------------------------------


def _menu_editavel(menu: dict) -> dict:
    """Uma cópia rasa com as três chaves sempre presentes.

    Sem isto, cada gesto começaria com três `or []` — e o primeiro que
    esquecesse um deles quebraria numa configuração vazia, que é justamente o
    estado do primeiro uso da tela.
    """
    return {
        "default_version": menu.get("default_version") or "",
        "versions": [
            dict(v, items=list(v.get("items") or []))
            for v in menu.get("versions") or []
        ],
        "pages": list(menu.get("pages") or []),
    }


def _indice(bruto, itens) -> "int | None":
    try:
        indice = int(bruto)
    except (TypeError, ValueError):
        return None
    return indice if 0 <= indice < len(itens) else None


def _erro(request, site, menu, frase: str):
    """Recusa desta tela, sem ida à rede. O catálogo continua sendo quem manda;
    isto só evita mandar a ele algo que já se sabe que ele vai recusar."""
    return render(
        request,
        "admin/menu.html",
        _contexto(request, site, menu, erro=frase),
        status=422,
    )
