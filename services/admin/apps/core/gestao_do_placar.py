"""Edição persistente das metas, medições e compromissos do placar."""

import uuid

from django.shortcuts import redirect, render
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from .models import CartaoDoPlacar, RegistroDoPlacar, VersaoDoCartaoDoPlacar
from .placar import validar


@require_http_methods(["GET", "POST"])
def gestao_do_placar(request):
    responsavel = (request.admin or {}).get("id") or (request.admin or {}).get("email")
    erro = ""
    edicao_do_cartao = None
    edicao_do_registro = None
    salvo = request.GET.get("salvo") == "1"
    selecionado = request.GET.get("cartao", "compras-no-ciclo")
    if request.method == "POST":
        acao = request.POST.get("acao")
        if acao == "cartao":
            selecionado = request.POST.get("nome", "")
            linha = CartaoDoPlacar.objects.filter(nome=selecionado).first()
            if linha is None:
                erro = "Este cartão não existe."
            else:
                dados = dict(linha.dados)
                for chave in ("alvo", "partida", "alvo_do_mes", "meta_semanal"):
                    if chave in request.POST:
                        texto = request.POST[chave].strip()
                        try:
                            dados[chave] = int(texto) if texto else None
                        except ValueError:
                            dados[chave] = texto
                            erro = f"{chave} precisa ser um número inteiro."
                for chave in ("ate", "partida_em", "pergunta", "_por_que"):
                    if chave in request.POST:
                        dados[chave] = request.POST[chave].strip()
                if "orientacao" in request.POST:
                    dados["acao"] = request.POST["orientacao"].strip()
                if "semanas" in dados:
                    semanas = [dict(semana) for semana in dados["semanas"]]
                    for i, semana in enumerate(semanas):
                        for chave in ("de", "ate"):
                            campo = f"semana_{i}_{chave}"
                            if campo in request.POST:
                                semana[chave] = request.POST[campo].strip()
                        campo = f"semana_{i}_alvo"
                        if campo in request.POST:
                            try:
                                semana["alvo"] = int(request.POST[campo])
                            except ValueError:
                                semana["alvo"] = request.POST[campo]
                                erro = "A meta de cada semana precisa ser um número inteiro."
                    dados["semanas"] = semanas
                if not erro:
                    problemas = validar(dados)
                    if problemas:
                        erro = "; ".join(problemas)
                    else:
                        dados["atualizado_por"] = responsavel
                        dados["versao"] = int(linha.dados.get("versao") or 0) + 1
                        dados["desde"] = timezone.localdate().isoformat()
                        with transaction.atomic():
                            linha.dados = dados
                            linha.save(update_fields=["dados", "atualizado_em"])
                            revisao = (linha.versoes.aggregate(n=Max("revisao"))["n"] or 0) + 1
                            VersaoDoCartaoDoPlacar.objects.create(
                                cartao=linha, revisao=revisao, dados=dados,
                                responsavel=responsavel or "",
                            )
                        return redirect("/admin/placar/editar/?cartao=" + selecionado + "&salvo=1")
                edicao_do_cartao = dados
        elif acao == "registro":
            tipo = request.POST.get("tipo", "")
            if tipo not in ("medicao", "compromisso", "decisao"):
                erro = "Escolha medição, compromisso ou decisão."
            elif not request.POST.get("titulo", "").strip():
                erro = "Escreva o título do registro."
            else:
                arquivo = request.POST.get("arquivo", "").strip() or uuid.uuid4().hex
                linha = RegistroDoPlacar.objects.filter(arquivo=arquivo).first()
                dados = dict(linha.dados) if linha else {"arquivo": arquivo}
                dados.update({
                    "tipo": tipo,
                    "quando": request.POST.get("quando", "").strip(),
                    "titulo": request.POST["titulo"].strip(),
                    "detalhe": request.POST.get("detalhe", "").strip(),
                    "responde_a": request.POST.get("responde_a", "").strip() or None,
                    "foto": request.POST.get("foto", "").strip() or None,
                    "problema": request.POST.get("problema", "").strip() or None,
                    "hipotese": request.POST.get("hipotese", "").strip() or None,
                    "metrica": request.POST.get("metrica", "").strip() or None,
                    "guarda": request.POST.get("guarda", "").strip() or None,
                    "veredito": request.POST.get("veredito", "").strip() or None,
                    "portao": request.POST.get("portao", "").strip() or None,
                    "evidencia": request.POST.get("evidencia", "").strip() or None,
                    "verificado_em": request.POST.get("verificado_em", "").strip() or None,
                    "responsavel": dados.get("responsavel") or responsavel,
                    "atualizado_por": responsavel,
                })
                prazo = request.POST.get("vence_em_dias", "").strip()
                try:
                    dados["vence_em_dias"] = int(prazo) if prazo else None
                except ValueError:
                    erro = "O prazo precisa ser um número de dias."
                if not erro:
                    RegistroDoPlacar.objects.update_or_create(
                        arquivo=arquivo, defaults={"dados": dados}
                    )
                    return redirect("/admin/placar/editar/?salvo=1")
            if erro:
                arquivo = request.POST.get("arquivo", "").strip()
                anterior = RegistroDoPlacar.objects.filter(arquivo=arquivo).first() if arquivo else None
                preenchido = dict(anterior.dados) if anterior else {}
                for campo in (
                    "tipo", "quando", "titulo", "detalhe", "foto", "vence_em_dias",
                    "responde_a", "problema", "hipotese", "metrica", "guarda",
                    "veredito", "portao", "evidencia", "verificado_em",
                ):
                    preenchido[campo] = request.POST.get(campo, "")
                edicao_do_registro = RegistroDoPlacar(arquivo=arquivo, dados=preenchido)
    cartoes = list(CartaoDoPlacar.objects.order_by("nome"))
    atual = next((c for c in cartoes if c.nome == selecionado), None)
    if atual is not None and edicao_do_cartao is not None:
        atual.dados = edicao_do_cartao
    registro = edicao_do_registro or RegistroDoPlacar.objects.filter(arquivo=request.GET.get("registro", "")).first()
    return render(request, "admin/gestao_do_placar.html", {
        "admin": request.admin, "erro": erro, "salvo": salvo,
        "cartoes": cartoes, "cartao": atual,
        "por_que_do_cartao": atual.dados.get("_por_que", "") if atual else "",
        "versoes_do_cartao": atual.versoes.order_by("-revisao") if atual else [],
        "registros": RegistroDoPlacar.objects.order_by("-arquivo"),
        "registro": registro,
    })
