"""Leitura administrativa de uma tomografia guardada em entregas privadas."""

from __future__ import annotations

import json

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.text import slugify
from django.views.decorators.http import require_http_methods

from apps.agentes.models import Entrega
from apps.agentes.trabalhos import robo_de
from apps.core.equipe import _membro_da_sessao

TIPO = "tomografia_turmas"
TITULO = "Tomografia das turmas · relatório 20261013"
LIMITE_BYTES = 2_000_000
SINAIS = {
    "impacto": "Impacto relatado ou atrito recorrente",
    "atrito": "Atrito localizado",
    "avanco": "Avanço ou ajuda entre alunos",
    "hipotese": "Hipótese ou oportunidade",
    "sem_dados": "Sem dados",
}


def _lista(valor):
    return valor if isinstance(valor, list) else []


def _textos(valor):
    if isinstance(valor, str):
        return [valor] if valor else []
    return [item for item in _lista(valor) if isinstance(item, str) and item]


def _dados():
    entrega = Entrega.objects.filter(tipo=TIPO, titulo=TITULO).order_by("-id").first()
    if entrega is None:
        return {}, False, None
    try:
        dados = json.loads(entrega.conteudo)
        if not isinstance(dados, dict):
            raise ValueError("raiz não é objeto")
    except (ValueError, UnicodeError):
        return {}, False, entrega
    return dados, True, entrega


def _preparar_achados(originais, turmas, prefixo):
    achados = []
    for numero, original in enumerate(_lista(originais), start=1):
        if not isinstance(original, dict):
            continue
        achado = dict(original)
        achado["ancora"] = f"{prefixo}-{numero}-{slugify(str(original.get('id') or original.get('titulo') or numero))}"
        sinal = str(original.get("sinal") or "sem_dados")
        achado["sinal"] = sinal if sinal in SINAIS else "sem_dados"
        achado["sinal_nome"] = SINAIS[achado["sinal"]]
        for chave in ("turmas", "evidencias", "limites", "oportunidades", "acoes"):
            achado[chave] = _lista(original.get(chave))
        for chave in ("interpretacao", "causas_observadas", "hipoteses", "estado_desfecho"):
            achado[chave] = _textos(original.get(chave))
        leituras = {str(item.get("id")): item.get("leitura") for item in achado["turmas"] if isinstance(item, dict)}
        achado["celulas"] = [
            {"id": turma.get("id"), "sem_dados": turma.get("estado") == "sem dados",
             "texto": turma.get("leitura") if turma.get("estado") == "sem dados"
             else leituras.get(str(turma.get("id"))) or "Sem evidência classificada."}
            for turma in turmas if isinstance(turma, dict)
        ]
        achados.append(achado)
    return achados


def _preparar(dados):
    """Normaliza a navegação; o texto do relatório permanece autoescapado."""
    turmas = _lista(dados.get("turmas"))
    achados = _preparar_achados(dados.get("achados"), turmas, "achado")
    atlas = []
    for numero, original in enumerate(_lista(dados.get("atlas")), start=1):
        if not isinstance(original, dict):
            continue
        recorte = dict(original)
        recorte["ancora"] = f"atlas-{numero}"
        recorte["achados"] = _preparar_achados(original.get("achados"), turmas, recorte["ancora"])
        recorte["casos"] = _lista(original.get("casos"))
        recorte["surpresas"] = _textos(original.get("surpresas"))
        atlas.append(recorte)
    linha_do_tempo = []
    for ponto in _lista(dados.get("linha_do_tempo")):
        if not isinstance(ponto, dict):
            continue
        item = dict(ponto)
        try:
            item["mensagens"] = max(0, int(item.get("mensagens", 0)))
        except (TypeError, ValueError):
            item["mensagens"] = 0
        linha_do_tempo.append(item)
    return {
        "achados": achados,
        "atlas": atlas,
        "comparacoes": _lista(dados.get("comparacoes")),
        "linha_do_tempo": linha_do_tempo,
        "max_mensagens_tempo": max((p["mensagens"] for p in linha_do_tempo), default=1) or 1,
        "oportunidades": _lista(dados.get("oportunidades")),
        "sumario": _lista(dados.get("sumario")),
        "metodologia": _lista(dados.get("metodologia")),
        "limites": _lista(dados.get("limites")),
        "fontes": _lista(dados.get("fontes")),
        "quadros": _lista(dados.get("quadros")),
        "decisoes": _lista(dados.get("decisoes")),
    }


def _importar(request):
    arquivo = request.FILES.get("arquivo")
    if arquivo is None:
        return "Escolha um arquivo JSON para importar."
    if arquivo.size > LIMITE_BYTES:
        return "O arquivo excede 2 MB. Nenhuma versão foi criada."
    try:
        texto = arquivo.read(LIMITE_BYTES + 1).decode("utf-8-sig")
        if len(texto.encode("utf-8")) > LIMITE_BYTES:
            return "O arquivo excede 2 MB. Nenhuma versão foi criada."
        dados = json.loads(texto)
    except (UnicodeError, ValueError):
        return "O arquivo não é um JSON UTF-8 válido. Nenhuma versão foi criada."
    if not isinstance(dados, dict) or not isinstance(dados.get("turmas"), list) or not isinstance(dados.get("achados"), list):
        return "O JSON precisa conter listas 'turmas' e 'achados'. Nenhuma versão foi criada."
    membro = _membro_da_sessao(request)
    if membro is None:
        return "Esta conta administrativa não está associada a um robô pessoal. Nenhuma versão foi criada."
    anterior = Entrega.objects.filter(tipo=TIPO, titulo=TITULO).order_by("-id").first()
    Entrega.objects.create(
        robo=robo_de(membro), tipo=TIPO, titulo=TITULO, conteudo=texto,
        versao=(anterior.versao + 1) if anterior else 1,
    )
    return None


@require_http_methods(["GET", "POST"])
def tomografia_turmas(request):
    erro_importacao = None
    if request.method == "POST":
        erro_importacao = _importar(request)
        if erro_importacao is None:
            return HttpResponseRedirect(reverse("tomografia_turmas_20261013") + "?importado=1")
    dados, disponivel, entrega = _dados()
    secoes = _preparar(dados)
    resposta = render(request, "admin/tomografia_turmas.html", {
        "admin": request.admin,
        "titulo_relatorio": dados.get("titulo") or "Tomografia das turmas",
        "subtitulo_relatorio": dados.get("subtitulo") or "Leitura de conversas de alunos",
        "periodo_relatorio": dados.get("periodo") or "",
        "turmas": _lista(dados.get("turmas")),
        "total_mensagens": dados.get("total_mensagens"),
        "aviso_cobertura": dados.get("aviso_cobertura"),
        "sinais": SINAIS,
        "dados_disponiveis": disponivel,
        "versao": entrega.versao if entrega else None,
        "importado": request.GET.get("importado") == "1",
        "erro_importacao": erro_importacao,
        **secoes,
    }, status=400 if erro_importacao else 200)
    return resposta
