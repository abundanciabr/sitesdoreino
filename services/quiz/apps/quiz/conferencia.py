"""Conferência dos links de campanha antes de anunciar.

Só lê: para cada link, a versão, o formato e o segmento que a pessoa vai ver,
as somas de pontos possíveis, a faixa e a oferta de cada uma e o endereço final
da saída com os parâmetros da campanha, montado pela mesma função da saída
real, e a prova de cada saída real com um anúncio de origem completa (os 12
parâmetros). Nada é gravado e nenhum formulário é enviado. O endereço de teste de cada
experiência leva src=teste, que os relatórios deixam fora das taxas.
"""

from urllib.parse import parse_qsl, urlencode, urlsplit

from django.http import Http404, JsonResponse, QueryDict
from django.utils.html import escape

from .direcionadas import destino_com_parametros, parametros_de_entrada
from .editor import _authorized, _error
from .experiencias import calcular, resolver_experiencia
from .painel_campanhas import _host_https, _ia_ligada, _montar_links, _quiz_privado

LIMITE_SOMAS = 5000
CAMPANHA_DE_TESTE = "teste-conferencia"
# Um anúncio com a origem completa, de propósito com src e utm_source (e os
# outros pares) diferentes: os dois valores precisam chegar à oferta.
ORIGEM_DE_PROVA = {
    "fmt": "text",
    "seg": "frio",
    "src": "meta",
    "med": "cpc",
    "cpg": "prova_da_origem",
    "ctv": "anuncio_de_prova",
    "utm_source": "facebook",
    "utm_medium": "paid_social",
    "utm_campaign": "prova_utm_campaign",
    "utm_content": "prova_utm_content",
    "utm_term": "prova_utm_term",
}


def _curto(texto, limite=90):
    texto = " ".join(str(texto or "").split())
    return texto if len(texto) <= limite else texto[: limite - 1] + "…"


def _somas_possiveis(perguntas):
    """Cada soma de pontos possível e um caminho de respostas que chega nela."""
    caminhos = {0: ()}
    for pergunta in perguntas:
        opcoes = list(pergunta.options.all())
        if not opcoes:
            return None
        proximos = {}
        for soma, caminho in caminhos.items():
            for opcao in opcoes:
                proximos.setdefault(soma + opcao.points, caminho + ((pergunta, opcao),))
        caminhos = proximos
        if len(caminhos) > LIMITE_SOMAS:
            return None
    return caminhos


def _exemplo(soma, caminho):
    return {
        "pontuacao": soma,
        "respostas": [
            {
                "pergunta": pergunta.order,
                "opcao": _curto(opcao.text, 70),
                "pontos": opcao.points,
            }
            for pergunta, opcao in caminho
        ],
    }


def _prova_da_origem(versao_key, destino):
    """A saída de um anúncio com os 12 parâmetros, pela mesma função da saída
    real: o endereço final e o que se perdeu no caminho."""
    chegada = {"v": versao_key, **ORIGEM_DE_PROVA}
    contexto, utm = parametros_de_entrada(QueryDict(urlencode(chegada)))
    final = destino_com_parametros(destino, utm, contexto)
    destino_original = dict(parse_qsl(urlsplit(destino).query))
    recebidos = dict(parse_qsl(urlsplit(final).query))
    faltam = sorted(
        chave
        for chave, valor in chegada.items()
        if chave not in destino_original and recebidos.get(chave) != valor
    )
    return {"url_final": final, "faltam": faltam}


def _conferir_versao(versao):
    """Faixas, ofertas e somas possíveis de uma versão."""
    experiencia = versao.experience if isinstance(versao.experience, dict) else {}
    ofertas = experiencia.get("ofertas") if isinstance(experiencia.get("ofertas"), dict) else {}
    band_offers = (
        experiencia.get("band_offers")
        if isinstance(experiencia.get("band_offers"), dict)
        else {}
    )
    problemas, avisos = [], []
    perguntas = list(versao.questions.prefetch_related("options").order_by("order"))
    caminhos = _somas_possiveis(perguntas)
    if not perguntas:
        problemas.append("A versão não tem perguntas.")
        caminhos = {}
    elif caminhos is None:
        problemas.append(
            "Alguma pergunta está sem opções, ou há combinações demais para conferir."
        )
        caminhos = {}
    somas = sorted(caminhos)
    bandas = list(versao.bands.order_by("min_score", "key"))
    if not bandas:
        problemas.append("A versão não tem faixas de resultado.")

    faixas = []
    for banda in bandas:
        dentro = [s for s in somas if banda.min_score <= s <= banda.max_score]
        oferta_id = band_offers.get(banda.key)
        oferta = ofertas.get(oferta_id) if oferta_id else None
        checkout = (oferta or {}).get("checkout_url") or ""
        destino = banda.botao_destino or ""
        prova = None
        if oferta is None:
            problemas.append(f"A faixa {banda.key} não leva a nenhuma oferta.")
        elif checkout and destino != checkout:
            problemas.append(
                f"A faixa {banda.key} leva a {destino or '(nada)'}, mas a oferta "
                f"{oferta_id} está ligada a {checkout}."
            )
        elif checkout:
            try:
                prova = _prova_da_origem(versao.key, destino)
            except ValueError:
                problemas.append(f"O destino da faixa {banda.key} não é HTTPS válido.")
            else:
                if prova["faltam"] and dentro:
                    problemas.append(
                        f"A saída da faixa {banda.key} perde "
                        + ", ".join(prova["faltam"])
                        + " quando o anúncio traz a origem completa."
                    )
        if not dentro and somas:
            avisos.append(
                f"A faixa {banda.key} ({banda.min_score} a {banda.max_score} pontos) "
                "nunca acontece: nenhuma combinação de respostas soma isso."
            )
        faixas.append(
            {
                "key": banda.key,
                "titulo": _curto(banda.title),
                "min": banda.min_score,
                "max": banda.max_score,
                "alcancavel": bool(dentro),
                "oferta_id": oferta_id or "",
                "oferta": _curto((oferta or {}).get("nome", "")),
                "demonstracao": bool(oferta) and not checkout,
                "destino": destino,
                "prova_origem": prova,
                "rotulo": banda.botao_rotulo,
                "exemplos": [
                    _exemplo(s, caminhos[s]) for s in dict.fromkeys((dentro[0], dentro[-1]))
                ]
                if dentro
                else [],
            }
        )

    sem_faixa = [s for s in somas if not any(b.min_score <= s <= b.max_score for b in bandas)]
    if sem_faixa:
        problemas.append(
            "Quem somar " + ", ".join(map(str, sem_faixa)) + " pontos fica sem "
            "resultado: nenhuma faixa cobre essa pontuação."
        )
    duplas = [
        s for s in somas if sum(1 for b in bandas if b.min_score <= s <= b.max_score) > 1
    ]
    if duplas:
        problemas.append(
            "Quem somar " + ", ".join(map(str, duplas)) + " pontos cai em mais de "
            "uma faixa; o site usa a de menor pontuação."
        )
    indicadas = {f["oferta_id"] for f in faixas if f["alcancavel"] and f["oferta_id"]}
    for oferta_id, oferta in sorted(ofertas.items()):
        if oferta_id not in indicadas:
            avisos.append(
                f"A oferta {oferta_id} não é indicada por nenhuma faixa que acontece."
            )
        elif not (oferta or {}).get("checkout_url"):
            avisos.append(
                f"A oferta {oferta_id} ainda é demonstração: a saída mostra uma "
                "página sem cobrança."
            )
    return {
        "key": versao.key,
        "perguntas": len(perguntas),
        "pontuacao": {
            "min": somas[0] if somas else None,
            "max": somas[-1] if somas else None,
            "possiveis": somas,
        },
        "faixas": faixas,
        "ofertas": [
            {
                "id": oferta_id,
                "nome": _curto((oferta or {}).get("nome", "")),
                "checkout_url": (oferta or {}).get("checkout_url") or "",
                "indicada": oferta_id in indicadas,
            }
            for oferta_id, oferta in sorted(ofertas.items())
        ],
        "problemas": problemas,
        "avisos": avisos,
    }


def _marcas(quiz, versao, resolvida):
    """Trechos exatos que a página pública precisa trazer."""
    titulo = resolvida["headline"] or ""
    if resolvida["fmt"] == "ai":
        return [f"<h1>{escape(titulo or quiz.title)}</h1>", 'name="quiz_attempt"']
    marcas = [f'data-versao="{escape(versao.key)}"']
    if titulo:
        marcas.append(f"<h1>{escape(titulo)}</h1>")
    if resolvida.get("video_kind") == "pendente":
        marcas.append('class="video-pendente"')
    elif resolvida.get("video_kind") == "embed":
        marcas.append(f'<iframe src="{escape(resolvida["video_url"])}"')
    elif resolvida.get("video_kind") == "file":
        marcas.append(f'<source src="{escape(resolvida["video_url"])}">')
    if resolvida["fmt"] == "calc":
        marcas.append('id="experiencia-calculadora"')
    return marcas


def _conferir_experiencia(quiz, versao, fmt, seg, host, ia_ligada, faixas):
    resolvida = resolver_experiencia(versao, fmt, seg or None)
    problemas, avisos = [], []
    calculo = None
    if not resolvida["headline"]:
        avisos.append("Sem título próprio nesta combinação.")
    if resolvida.get("video_kind") == "pendente":
        avisos.append(
            "Vídeo em produção: a página abre com um aviso no lugar do vídeo."
        )
    if resolvida["fmt"] == "calc":
        try:
            calculo = calcular(resolvida["calculator"], {})
        except ValueError as erro:
            problemas.append(f"A calculadora não calcula com os valores iniciais: {erro}")
    if resolvida["fmt"] == "ai" and not ia_ligada:
        avisos.append(
            "Conversa com IA desligada: a página faz as mesmas perguntas em botões."
        )
    textos = resolvida.get("results") if isinstance(resolvida.get("results"), dict) else {}
    chaves = {f["key"]: f for f in faixas}
    for chave, texto in sorted(textos.items()):
        if chave not in chaves:
            avisos.append(f"O público {seg} tem texto para a faixa {chave}, que não existe.")
            continue
        if isinstance(texto, dict) and texto.get("botao_destino") not in (
            None,
            "",
            chaves[chave]["destino"],
        ):
            problemas.append(
                f"O texto do público {seg} troca o destino da faixa {chave}; "
                "a saída usa o destino da faixa."
            )
    parametros = {"v": versao.key, "fmt": resolvida["fmt"]}
    if seg:
        parametros["seg"] = seg
    parametros.update(src="teste", cpg=CAMPANHA_DE_TESTE)
    return {
        "chave": f"{versao.key}|{resolvida['fmt']}|{seg}",
        "version_key": versao.key,
        "fmt": resolvida["fmt"],
        "seg": seg,
        "headline": _curto(resolvida["headline"], 140),
        "subheadline": _curto(resolvida["subheadline"], 160),
        "video": resolvida.get("video_kind") or "",
        "calculo": calculo,
        "ia": ia_ligada if resolvida["fmt"] == "ai" else None,
        "teste_url": f"https://{host}/quiz/{quiz.slug}/?{urlencode(parametros)}",
        "marcas": _marcas(quiz, versao, resolvida),
        "problemas": problemas,
        "avisos": avisos,
    }


def _saidas(item, versao_conferida, versao):
    """O que acontece em cada faixa possível para quem chega por este link."""
    consulta = urlsplit(item["url"]).query
    contexto, utm = parametros_de_entrada(QueryDict(consulta))
    contexto.update(v=versao.key, fmt=item["fmt"], seg=item["seg"])
    chegada = dict(parse_qsl(consulta))
    saidas, problemas = [], []
    for faixa in versao_conferida["faixas"]:
        if not faixa["alcancavel"] or not faixa["oferta_id"]:
            continue
        saida = {
            "faixa": faixa["key"],
            "oferta": faixa["oferta"],
            "demonstracao": faixa["demonstracao"],
            "url_final": "",
            "faltam": [],
        }
        if not faixa["demonstracao"]:
            try:
                final = destino_com_parametros(faixa["destino"], utm, contexto)
            except ValueError:
                problemas.append(f"A saída da faixa {faixa['key']} não abre.")
            else:
                destino_original = dict(parse_qsl(urlsplit(faixa["destino"]).query))
                recebidos = dict(parse_qsl(urlsplit(final).query))
                saida["url_final"] = final
                saida["faltam"] = sorted(
                    chave
                    for chave, valor in chegada.items()
                    if chave not in destino_original and recebidos.get(chave) != valor
                )
                if saida["faltam"]:
                    problemas.append(
                        f"A saída da faixa {faixa['key']} perde "
                        + ", ".join(saida["faltam"])
                        + "."
                    )
        saidas.append(saida)
    return saidas, problemas


def conferencia(request, slug):
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    quiz = _quiz_privado(request, slug)
    if quiz is None:
        return _error("Quiz ou site não encontrado.", 404)
    try:
        host = _host_https(quiz.site.host)
        itens = _montar_links(request, quiz, host)
    except ValueError as erro:
        return _error(str(erro), 422)
    ia_ligada = _ia_ligada()
    versoes = {v.key: v for v in quiz.versions.filter(key__in={i["version_key"] for i in itens})}
    conferidas = {chave: _conferir_versao(versoes[chave]) for chave in sorted(versoes)}
    experiencias = {}
    links = []
    for item in itens:
        versao = versoes[item["version_key"]]
        chave = f"{versao.key}|{item['fmt']}|{item['seg']}"
        if chave not in experiencias:
            try:
                experiencias[chave] = _conferir_experiencia(
                    quiz,
                    versao,
                    item["fmt"],
                    item["seg"],
                    host,
                    ia_ligada,
                    conferidas[versao.key]["faixas"],
                )
            except Http404 as erro:
                experiencias[chave] = {
                    "chave": chave,
                    "version_key": versao.key,
                    "fmt": item["fmt"],
                    "seg": item["seg"],
                    "problemas": [f"A combinação não abre: {erro}"],
                    "avisos": [],
                    "marcas": [],
                    "teste_url": "",
                }
        saidas, problemas = _saidas(item, conferidas[versao.key], versao)
        links.append({**item, "experiencia": chave, "saidas": saidas, "problemas": problemas})
    problemas = (
        sum(len(v["problemas"]) for v in conferidas.values())
        + sum(len(e["problemas"]) for e in experiencias.values())
        + sum(len(link["problemas"]) for link in links)
    )
    avisos = sum(len(v["avisos"]) for v in conferidas.values()) + sum(
        len(e["avisos"]) for e in experiencias.values()
    )
    resposta = JsonResponse(
        {
            "site_id": quiz.site_id,
            "quiz_slug": quiz.slug,
            "quiz_titulo": quiz.title,
            "host": host,
            "ia_ligada": ia_ligada,
            "versoes": list(conferidas.values()),
            "experiencias": list(experiencias.values()),
            "links": links,
            "resumo": {
                "links": len(links),
                "experiencias": len(experiencias),
                "versoes": len(conferidas),
                "problemas": problemas,
                "avisos": avisos,
            },
        }
    )
    resposta["Cache-Control"] = "no-store"
    return resposta
