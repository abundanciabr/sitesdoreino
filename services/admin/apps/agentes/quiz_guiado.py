"""Perguntas clicáveis da conversa e criação pelo mesmo editor do site."""

from __future__ import annotations

import copy
import json

from django.utils.text import slugify

from apps.core.conteudos import proxima_chave

from .models import Execucao, Mensagem


def montar_pergunta(args: dict) -> dict:
    pergunta = str(args.get("pergunta") or "").strip()[:300]
    tipo = args.get("tipo")
    opcoes = list(dict.fromkeys(
        o.strip()[:200] for o in args.get("opcoes", []) if isinstance(o, str) and o.strip()
    ))[:8]
    if not pergunta or tipo not in ("radio", "checkbox", "select", "texto"):
        raise ValueError("Envie uma pergunta e o tipo radio, checkbox, select ou texto.")
    if tipo != "texto" and not opcoes:
        raise ValueError("Esta pergunta precisa de opções para escolher.")
    return {
        "pergunta": pergunta,
        "tipo": tipo,
        "opcoes": [{"valor": str(i), "rotulo": o} for i, o in enumerate(opcoes)],
        "ajuda": str(args.get("ajuda") or "").strip()[:500],
        "aceita_outro": bool(args.get("aceita_outro")),
        "outro_rotulo": str(args.get("outro_rotulo") or "Prefiro escrever outra resposta").strip()[:120],
    }


def texto_da_pergunta(pergunta: dict) -> str:
    return pergunta["pergunta"] + ("\n\n" + pergunta["ajuda"] if pergunta.get("ajuda") else "")


def pergunta_da_mensagem(mensagem) -> dict | None:
    if mensagem.papel != Mensagem.Papel.ROBO or not mensagem.execucao_id:
        return None
    return (mensagem.execucao.estado or {}).get("pergunta_guiada")


def responder_pergunta(robo, slug: str, post) -> tuple[str, dict]:
    try:
        mensagem = Mensagem.objects.select_related("execucao").get(
            pk=int(post.get("pergunta_id") or "0"),
            papel=Mensagem.Papel.ROBO,
            execucao__robo=robo,
            execucao__estado__contexto__quiz=slug,
        )
    except (ValueError, Mensagem.DoesNotExist):
        raise ValueError("Essa pergunta não está disponível nesta conversa.") from None
    pergunta = pergunta_da_mensagem(mensagem)
    if not pergunta:
        raise ValueError("Essa mensagem não tem opções para responder.")
    contexto = dict(mensagem.execucao.estado.get("contexto") or {})
    # Uma pergunta antiga não pode avançar uma conversa que já continuou.
    if Mensagem.objects.filter(
        conversa=mensagem.conversa, id__gt=mensagem.id,
        execucao__estado__contexto__quiz=slug,
    ).exists():
        raise ValueError("A conversa já avançou. Responda à pergunta mais recente.")
    valores = list(dict.fromkeys(post.getlist("resposta")))
    livre = (post.get("resposta_livre") or "").strip()[:2000]
    opcoes = {o["valor"]: o["rotulo"] for o in pergunta["opcoes"]}
    if pergunta["tipo"] == "texto":
        respostas = [livre] if livre else []
    else:
        if any(v not in opcoes and v != "outro" for v in valores):
            raise ValueError("Escolha uma das opções desta pergunta.")
        if pergunta["tipo"] != "checkbox" and len(valores) > 1:
            raise ValueError("Escolha só uma opção.")
        respostas = [opcoes[v] for v in valores if v in opcoes]
        if "outro" in valores:
            if not pergunta["aceita_outro"] or not livre:
                raise ValueError("Escreva sua outra resposta para continuar.")
            respostas.append(livre)
    if not respostas:
        raise ValueError("Escolha ou escreva uma resposta para continuar.")
    contexto.pop("novo_fluxo", None)
    return pergunta["pergunta"] + "\n\n" + "; ".join(respostas), contexto


def consultar_rascunho(host: str, slug: str) -> dict:
    from .quiz import pedir_ao_quiz

    dados = pedir_ao_quiz(host, "GET", slug, "rascunho")
    documento = copy.deepcopy(dados.get("content") or {})
    for oferta in documento.get("ofertas") or []:
        oferta["checkout_configurado"] = bool(oferta.pop("checkout_url", None))
    return {"documento": documento, "publicadas": dados.get("publicadas") or []}


def criar_rascunho(ctx, host: str, slug: str, args: dict) -> dict:
    from .quiz import QuizRecusou, caminho, lista_de_quizzes, pedir_ao_quiz

    try:
        documento = json.loads(args.get("documento_json") or "")
    except (TypeError, ValueError):
        raise QuizRecusou("O conteúdo do quiz não veio completo. Monte o documento de novo.") from None
    if not isinstance(documento, dict) or documento.get("formato") != "quiz-low-ticket/2":
        raise QuizRecusou("Use o formato do estúdio: quiz-low-ticket/2.")
    versoes = documento.get("versoes")
    if not isinstance(versoes, list) or len(versoes) != 1 or not isinstance(versoes[0], dict):
        raise QuizRecusou("Monte uma versão nova por vez.")
    origem = f"robo-{ctx.robo.pk}-execucao-{ctx.execucao.pk}"
    modo = args.get("modo")
    if modo not in ("novo", "nova_versao"):
        raise QuizRecusou("Escolha criar um quiz novo ou uma nova versão.")
    if modo == "nova_versao":
        base = pedir_ao_quiz(host, "GET", slug, "rascunho")["content"]
        if base.get("formato") != "quiz-low-ticket/2":
            raise QuizRecusou("Este quiz usa outro editor. Crie um quiz novo.")
        nova = versoes[0]
        anteriores = base.get("versoes") or []
        existente = next((v for v in anteriores if v.get("robo_origem") == origem), None)
        if existente:
            nova = existente
        else:
            nova["key"] = proxima_chave(nova.get("key") or (anteriores[-1]["key"] if anteriores else "A"), [v["key"] for v in anteriores])
            nova["robo_origem"] = origem
            base["versoes"] = anteriores + [nova]
        documento = base
    else:
        titulo = (documento.get("quiz") or {}).get("title") or "Meu quiz"
        slug_base = slugify(args.get("slug") or titulo)[:85] or "meu-quiz"
        if not slug_base[0].isalpha():
            slug_base = "quiz-" + slug_base
        existentes = {q["slug"] for q in lista_de_quizzes(host)["quizzes"]}
        slug = slug_base
        numero = 2
        while slug in existentes:
            atual = pedir_ao_quiz(host, "GET", slug, "rascunho").get("content") or {}
            if atual.get("robo_origem") == origem:
                break
            slug = f"{slug_base}-{numero}"
            numero += 1
        documento["quiz"] = {"slug": slug, "title": titulo}
        documento["robo_origem"] = origem
        if args.get("usar_ofertas_do_quiz_atual"):
            base = pedir_ao_quiz(host, "GET", ctx.execucao.estado["contexto"]["quiz"], "rascunho")["content"]
            documento["ofertas"] = base.get("ofertas") or []
    # O editor existente confere perguntas, pontos, faixas, formatos e ofertas.
    salvo = pedir_ao_quiz(host, "PUT", slug, "rascunho", corpo=documento)
    if not salvo.get("has_draft"):
        raise QuizRecusou("O editor não confirmou que o quiz foi salvo.")
    resultado = {
        "salvo": True, "rascunho": True, "slug": slug,
        "titulo": documento["quiz"]["title"],
        "perguntas": len(documento["versoes"][-1].get("perguntas") or []),
        "estudio_url": f"https://{host}{caminho('conteudo_editar', 'quiz', slug)}",
        "aviso": "Quiz salvo no site. O botão Ver meu quiz abre a prévia e a publicação no estúdio.",
    }
    ctx.execucao.estado["rascunho_guiado"] = resultado
    Execucao.objects.filter(pk=ctx.execucao.pk).update(estado=ctx.execucao.estado)
    return resultado
