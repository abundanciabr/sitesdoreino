"""Qual oferta cada resultado de cada quiz leva: leitura e ajuste para a central.

O botão do resultado mora na faixa (`ResultBand.botao_destino` e
`botao_rotulo`); nas campanhas direcionadas o endereço de cada oferta também
mora em `experience["ofertas"][id]["checkout_url"]`. Esta porta lê esses dois
lugares e grava neles mesmos, sem criar uma terceira cópia da ligação.

Sem destino, a faixa não tem oferta: a tela de resultado não mostra botão.
"""

import json

from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .destinos import conectar_checkouts
from .editor import _authorized, _error, _site, destino_do_botao_valido
from .models import Quiz, QuizDraft, QuizVersion, ResultBand


def _versoes_ativas(quiz):
    return list(quiz.versions.filter(active=True).order_by("id"))


def _faixas(quiz, versoes):
    """Uma linha por resultado (chave da faixa), somando as versões ativas."""
    por_chave = {}
    ofertas_da_faixa = {}
    if quiz.directed:
        for versao in versoes:
            ofertas_da_faixa.update(versao.experience.get("band_offers") or {})
    bandas = ResultBand.objects.filter(version__in=versoes).order_by(
        "min_score", "version_id"
    )
    for banda in bandas:
        item = por_chave.get(banda.key)
        if item is None:
            item = por_chave[banda.key] = {
                "key": banda.key,
                "titulo": banda.title,
                "pontos": f"{banda.min_score} a {banda.max_score}",
                "destino": banda.botao_destino,
                "rotulo": banda.botao_rotulo,
                "oferta_id": ofertas_da_faixa.get(banda.key),
                "divergente": False,
            }
        elif (banda.botao_destino, banda.botao_rotulo) != (
            item["destino"],
            item["rotulo"],
        ):
            item["divergente"] = True
    return list(por_chave.values())


def _ofertas(quiz, versoes):
    if not quiz.directed or not versoes:
        return []
    ofertas = versoes[0].experience.get("ofertas") or {}
    return [
        {
            "id": oferta_id,
            "nome": (oferta or {}).get("nome", ""),
            "checkout_url": (oferta or {}).get("checkout_url") or "",
        }
        for oferta_id, oferta in ofertas.items()
    ]


def _quiz_em_dados(quiz):
    versoes = _versoes_ativas(quiz)
    return {
        "slug": quiz.slug,
        "title": quiz.title,
        "published": quiz.active and bool(versoes),
        "directed": quiz.directed,
        "versoes": sorted(v.key for v in versoes),
        "faixas": _faixas(quiz, versoes),
        "ofertas": _ofertas(quiz, versoes),
    }


@csrf_exempt
def ofertas_do_site(request):
    """GET: todos os quizzes do site, cada resultado com o botão que leva à oferta."""
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method != "GET":
        return _error("Método não permitido.", 405)
    site = _site(request)
    if site is None:
        return _error("Site não encontrado.", 404)
    quizzes = Quiz.objects.filter(site=site).order_by("slug")
    return JsonResponse(
        {"site_id": site.pk, "items": [_quiz_em_dados(q) for q in quizzes]}
    )


def _ler_corpo(request):
    try:
        corpo = json.loads(request.body)
    except (ValueError, UnicodeDecodeError):
        raise ValueError("Corpo inválido.")
    if not isinstance(corpo, dict):
        raise ValueError("Corpo inválido.")
    return corpo


def _ajustar_faixas(quiz, pedidos):
    """Troca destino e rótulo do botão das faixas indicadas, em todas as versões ativas."""
    if not isinstance(pedidos, list) or not pedidos:
        raise ValueError("Informe as faixas a ajustar.")
    novos = {}
    for pedido in pedidos:
        if not isinstance(pedido, dict) or set(pedido) != {"key", "destino", "rotulo"}:
            raise ValueError("Cada faixa precisa de key, destino e rotulo.")
        chave, destino, rotulo = pedido["key"], pedido["destino"], pedido["rotulo"]
        if not all(isinstance(v, str) for v in (chave, destino, rotulo)) or chave in novos:
            raise ValueError("Faixa inválida ou repetida.")
        if len(destino) > 500 or len(rotulo) > 80:
            raise ValueError("Destino ou rótulo longo demais.")
        if bool(destino) != bool(rotulo):
            raise ValueError("Destino e rótulo do botão devem ser preenchidos juntos.")
        destino_do_botao_valido(destino)
        novos[chave] = (destino, rotulo)
    versoes = list(
        QuizVersion.objects.select_for_update().filter(quiz=quiz, active=True)
    )
    if not versoes:
        raise ValueError("Este quiz não está publicado.")
    bandas = list(
        ResultBand.objects.select_for_update().filter(version__in=versoes)
    )
    existentes = {b.key for b in bandas}
    desconhecidas = sorted(set(novos) - existentes)
    if desconhecidas:
        raise ValueError(f"Resultado desconhecido: {', '.join(desconhecidas)}.")
    for banda in bandas:
        if banda.key in novos:
            banda.botao_destino, banda.botao_rotulo = novos[banda.key]
            banda.save(update_fields=["botao_destino", "botao_rotulo"])
    # Rascunho aberto não desfaz o ajuste quando for publicado.
    rascunho = QuizDraft.objects.select_for_update().filter(quiz=quiz).first()
    if rascunho is not None and isinstance(rascunho.content.get("bands"), list):
        conteudo = json.loads(json.dumps(rascunho.content))
        for faixa in conteudo["bands"]:
            if isinstance(faixa, dict) and faixa.get("key") in novos:
                destino, rotulo = novos[faixa["key"]]
                faixa["botao_destino"], faixa["botao_rotulo"] = destino, rotulo
        rascunho.content = conteudo
        rascunho.save(update_fields=["content", "updated_at"])


def _ajustar_ofertas(quiz, destinos):
    """Campanha direcionada: troca o endereço de compra de cada uma das duas ofertas."""
    if not isinstance(destinos, dict):
        raise ValueError("Informe o endereço de compra de cada oferta.")
    conectar_checkouts(quiz, destinos)


@csrf_exempt
def ofertas_do_quiz(request, slug):
    """PUT: ajusta a ligação dos resultados deste quiz com as ofertas.

    Quiz comum: {"faixas": [{"key", "destino", "rotulo"}]}; destino e rótulo
    vazios tiram o botão. Campanha direcionada: {"ofertas": {"<id>": "<https>"}}
    com as duas ofertas.
    """
    if not _authorized(request):
        return _error("Não autorizado.", 401)
    if request.method not in ("GET", "PUT"):
        return _error("Método não permitido.", 405)
    site = _site(request)
    if site is None:
        return _error("Site não encontrado.", 404)
    quiz = Quiz.objects.filter(site=site, slug=slug).first()
    if quiz is None:
        return _error("Quiz não encontrado.", 404)
    if request.method == "GET":
        return JsonResponse(_quiz_em_dados(quiz))
    try:
        corpo = _ler_corpo(request)
        with transaction.atomic():
            quiz = Quiz.objects.select_for_update().get(pk=quiz.pk)
            if quiz.directed:
                if set(corpo) != {"ofertas"}:
                    raise ValueError("Use apenas ofertas nesta campanha.")
                _ajustar_ofertas(quiz, corpo["ofertas"])
            else:
                if set(corpo) != {"faixas"}:
                    raise ValueError("Use apenas faixas neste quiz.")
                _ajustar_faixas(quiz, corpo["faixas"])
    except ValueError as erro:
        return _error(str(erro), 422)
    return JsonResponse(_quiz_em_dados(quiz))
