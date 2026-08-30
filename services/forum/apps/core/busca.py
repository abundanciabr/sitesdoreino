"""A BUSCA do fórum — achar a dúvida já respondida em vez de perguntar de novo.

Escolha do mantenedor em 30/08/2026, com a escola inaugurando na segunda. A
parte cara já existia desde o modelo de dados (lei §4.4): a coluna `busca` do
PostgreSQL, em português, indexada com GIN e preenchida na ESCRITA
(`Mensagem.indexar_para_busca`). Faltava a tela — e coluna que ninguém consulta
é trabalho parado.

**As duas coisas que decidem este arquivo, e que não se reabrem:**

1. **A BUSCA NUNCA MOSTRA O QUE A PESSOA NÃO PODERIA LER.** Quem responde
   "pode?" é `areas_visiveis`, a MESMA função das telas — nunca um filtro novo
   escrito aqui. Duas expressões da mesma regra divergem no primeiro dia em que
   alguém mexer numa delas, e aqui divergir significa vazar mensagem de aluno
   de área privada para um estranho que digitou a palavra certa. É o caminho
   mais curto para o pior acidente possível num fórum de escola: a busca é a
   única tela que atravessa TODAS as áreas de uma vez.

2. **O DESTAQUE ESCAPA ANTES DE MARCAR.** O `ts_headline` do PostgreSQL devolve
   o trecho já com os marcadores dentro, e **não escapa o texto de origem**.
   Marcar isso como seguro para o navegador seria publicar o que o aluno
   escreveu como HTML: bastaria alguém mandar `<script>` numa mensagem para o
   código dele rodar na tela de quem buscasse. A ordem correta, e a razão de
   `_trecho_seguro` existir, é: **escapar primeiro, trocar os marcadores
   depois.**

**Com que configuração ela indexa e procura:** com a que `config_de_busca()`
disser, nunca com uma cravada aqui. É a mesma função que a escrita usa para
indexar (`Mensagem.indexar_para_busca`), e o motivo de as duas pontas morarem
no mesmo arquivo é que indexar com uma e procurar com outra é a forma
silenciosa de a busca não achar o que existe.

Enquanto o banco não tiver a cura do acento instalada, a tela avisa disso em
português ao não achar nada — e o aviso some sozinho quando ela chegar, porque
quem decide é `acento_importa()`, medindo o que está ativo.
"""

from __future__ import annotations

from django.contrib.postgres.search import SearchHeadline, SearchQuery, SearchRank
from django.core.paginator import Paginator
from django.shortcuts import render
from django.utils.html import escape
from django.utils.safestring import mark_safe
from django.views.decorators.http import require_GET

from apps.forum.config_de_busca import acento_importa, config_de_busca
from apps.forum.models import Mensagem, Topico

from .permissoes import areas_visiveis, pode_moderar
from .sessao import quem_e

POR_PAGINA = 20
# Uma letra casa com quase tudo e devolve o fórum inteiro ordenado por acaso.
TERMO_MINIMO = 2
# Teto de sanidade: ninguém busca um parágrafo, e o limite evita transformar a
# barra de endereço numa forma de empurrar texto para dentro da consulta.
TERMO_MAXIMO = 120

# Os marcadores que o PostgreSQL põe em volta do que casou. NÃO são HTML de
# propósito: eles atravessam o escape como texto comum e só viram `<mark>`
# depois dele (ver `_trecho_seguro`). Se um aluno escrever `[[hl]]` numa
# mensagem, o pior que acontece é um destaque a mais no trecho — nunca HTML
# executável.
ABRE = "[[hl]]"
FECHA = "[[/hl]]"


def _trecho_seguro(bruto: str) -> str:
    """O trecho do PostgreSQL virando HTML seguro. A ORDEM é a segurança.

    `escape` primeiro: tudo que veio da mensagem (inclusive um `<script>` que
    alguém tenha escrito) deixa de ser HTML. Só então os marcadores, que são
    nossos e conhecidos, viram as únicas tags da string.

    Inverter as duas linhas publica o texto do aluno como HTML na tela de quem
    busca. É a razão de esta função existir em vez de um `|safe` no template.
    """
    return mark_safe(
        escape(bruto).replace(escape(ABRE), "<mark>").replace(escape(FECHA), "</mark>")
    )


@require_GET
def buscar(request):
    """A tela de busca. Sem termo, ela convida; com termo, ela responde."""
    ator = quem_e(request)
    termo = (request.GET.get("q") or "").strip()[:TERMO_MAXIMO]
    contexto = {
        "ator": ator,
        "termo": termo,
        # A tela só avisa do acento enquanto o acento importa de verdade. Quando
        # a cura estiver instalada no banco, o aviso some por MEDIÇÃO do que
        # está ativo, e não porque alguém lembrou de apagar a frase.
        "acento_importa": acento_importa(),
        "curto": bool(termo) and len(termo) < TERMO_MINIMO,
        "pagina": None,
        "quantas": 0,
    }
    if len(termo) < TERMO_MINIMO:
        return render(request, "forum/busca.html", contexto)

    # AS ÁREAS QUE ESTA PESSOA ENXERGA — a mesma função das telas, sempre.
    areas = areas_visiveis(ator)
    if not areas:
        return render(request, "forum/busca.html", contexto)

    # `websearch` é o tradutor de linguagem de gente do PostgreSQL: aspas viram
    # frase exata, `or` vira alternativa, `-palavra` exclui. E, ao contrário do
    # `to_tsquery` cru, ele **nunca levanta** com pontuação solta — o que
    # importa numa caixa onde qualquer pessoa digita qualquer coisa.
    consulta = SearchQuery(termo, config=config_de_busca(), search_type="websearch")

    achadas = (
        Mensagem.objects.filter(topico__area__in=areas, busca=consulta)
        .select_related("topico", "topico__area", "autor")
        .annotate(
            relevancia=SearchRank("busca", consulta),
            trecho=SearchHeadline(
                "texto",
                consulta,
                config=config_de_busca(),
                start_sel=ABRE,
                stop_sel=FECHA,
                max_words=40,
                min_words=18,
            ),
        )
    )
    if not pode_moderar(ator):
        # Fora do ar é fora do ar também aqui. Para quem modera, aparece
        # marcado — a MESMA regra das outras telas, e não uma segunda.
        achadas = achadas.filter(
            removida_em__isnull=True, topico__estado=Topico.Estado.PUBLICADO
        )

    achadas = achadas.order_by("-relevancia", "-criado_em")

    paginas = Paginator(achadas, POR_PAGINA)
    pagina = paginas.get_page(request.GET.get("p"))
    for mensagem in pagina:
        # O atributo só existe para a tela; não é campo do modelo.
        mensagem.trecho_seguro = _trecho_seguro(mensagem.trecho)

    contexto["pagina"] = pagina
    contexto["quantas"] = paginas.count
    return render(request, "forum/busca.html", contexto)
