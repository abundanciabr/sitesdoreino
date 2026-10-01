"""Jornada privada de criação do portfólio, separada do Crivo comercial."""

import copy
import json
import re
import secrets
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import PortfolioCatalog, PortfolioExploration, Site


ENTRADAS = {"descobrir", "ideia", "prontos"}
ETAPAS = {
    "interesses",
    "contexto",
    "ponto_partida",
    "projeto",
    "apresentacao",
    "escolha_final",
}
LISTAS = {"interesses", "contextos", "estilos"}
TEXTOS = {
    "ideia_propria": 3000,
    "modelos_prontos": 3000,
    "experiencia": 100,
    "dificuldade": 3000,
    "tamanho": 100,
    "habilidade": 3000,
    "projeto_chave": 100,
    "objetivo_apresentacao": 3000,
    "servico_proprio": 3000,
    "primeira_acao": 3000,
}
PROPOSTA_CAMPOS = {
    "chave": 100,
    "titulo": 200,
    "descricao": 3000,
    "direcao": 3000,
    "intencao": 3000,
    "aplicacao": 3000,
    "servico": 3000,
    "primeira_entrega": 3000,
    "aprendizagem": 3000,
    "apresentacao": 3000,
    "primeira_acao": 3000,
    "por_que": 3000,
    "referencia": 250,
}
CATALOGO_ARQUIVO = Path(__file__).with_name("portfolio_catalogo.json")
REFERENCIAS = Path(settings.BASE_DIR) / "static" / "quiz" / "portfolio"
REFERENCIA_PREFIXO = "/quiz/portfolio/referencias/"


def _erro(mensagem, status=400):
    return JsonResponse({"detail": mensagem}, status=status)


def _autorizado(request):
    esquema, _, token = request.headers.get("Authorization", "").partition(" ")
    aceitos = [
        item.strip()
        for item in settings.TOKENS_ACEITOS_PAGES.split(",")
        if item.strip()
    ]
    return (
        esquema.lower() == "bearer"
        and bool(token)
        and any(secrets.compare_digest(token, aceito) for aceito in aceitos)
    )


def _json(request):
    if len(request.body) > 160_000:
        raise ValueError("Conteúdo excede o tamanho permitido.")
    try:
        dados = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("JSON inválido.") from None
    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON.")
    return dados


def _identidade(dados):
    site_id = dados.get("site_id")
    aluno_id = dados.get("aluno_id")
    if not isinstance(site_id, str) or not 1 <= len(site_id) <= 64:
        raise ValueError("site_id inválido.")
    if not isinstance(aluno_id, str) or not 1 <= len(aluno_id) <= 64:
        raise ValueError("aluno_id inválido.")
    site = Site.objects.filter(pk=site_id, active=True).first()
    if site is None:
        raise LookupError("Site desconhecido ou inativo.")
    return site, aluno_id


def _site(dados):
    site_id = dados.get("site_id")
    if not isinstance(site_id, str) or not 1 <= len(site_id) <= 64:
        raise ValueError("site_id inválido.")
    site = Site.objects.filter(pk=site_id, active=True).first()
    if site is None:
        raise LookupError("Site desconhecido ou inativo.")
    return site


def _texto(valor, limite, nome):
    if not isinstance(valor, str) or len(valor) > limite:
        raise ValueError(f"{nome} inválido (máximo {limite} caracteres).")
    return valor.strip()


def _referencia(valor):
    if valor and (
        not valor.startswith(REFERENCIA_PREFIXO)
        or not re.fullmatch(r"/quiz/portfolio/referencias/[a-z0-9_-]+\.svg", valor)
    ):
        raise ValueError("Referência deve apontar para uma imagem própria do quiz.")
    return valor


def _validar_catalogo(catalogo):
    if not isinstance(catalogo, dict):
        raise ValueError("Catálogo inválido.")
    familias = catalogo.get("familias")
    projetos = catalogo.get("projetos")
    if not isinstance(familias, list) or not 1 <= len(familias) <= 30:
        raise ValueError("Informe de 1 a 30 famílias.")
    if not isinstance(projetos, list) or not 1 <= len(projetos) <= 100:
        raise ValueError("Informe de 1 a 100 projetos.")
    familias_chaves = set()
    for familia in familias:
        if not isinstance(familia, dict):
            raise ValueError("Família inválida.")
        chave = _texto(familia.get("chave"), 100, "chave da família")
        if not re.fullmatch(r"[a-z0-9_-]+", chave) or chave in familias_chaves:
            raise ValueError("Chave de família inválida ou repetida.")
        familias_chaves.add(chave)
        _texto(familia.get("nome"), 200, "nome da família")
        _texto(familia.get("descricao", ""), 1000, "descrição da família")
    projetos_chaves = set()
    for projeto in projetos:
        if not isinstance(projeto, dict):
            raise ValueError("Projeto inválido.")
        chave = _texto(projeto.get("chave"), 100, "chave do projeto")
        if not re.fullmatch(r"[a-z0-9_-]+", chave) or chave in projetos_chaves:
            raise ValueError("Chave de projeto inválida ou repetida.")
        projetos_chaves.add(chave)
        if projeto.get("familia") not in familias_chaves:
            raise ValueError("Projeto aponta para família desconhecida.")
        _texto(projeto.get("titulo"), 200, "titulo")
        for campo in (
            "descricao",
            "direcao",
            "aplicacao",
            "servico",
            "primeira_entrega",
            "aprendizagem",
            "apresentacao",
            "primeira_acao",
        ):
            _texto(projeto.get(campo), 3000, campo)
        _referencia(_texto(projeto.get("referencia", ""), 250, "referencia"))
        for campo in ("contextos", "estilos", "escopos"):
            valores = projeto.get(campo, [])
            if not isinstance(valores, list) or len(valores) > 30:
                raise ValueError(f"{campo} inválido.")
            for valor in valores:
                _texto(valor, 100, campo)
        for campo in ("versao_pequena", "expansao", "feedback"):
            valor = projeto.get(campo, "")
            if isinstance(valor, str):
                _texto(valor, 3000, campo)
            elif isinstance(valor, list) and len(valor) <= 20:
                for item in valor:
                    _texto(item, 500, campo)
            else:
                raise ValueError(f"{campo} inválido.")
    return catalogo


def _catalogo(site):
    publicado = PortfolioCatalog.objects.filter(site=site).order_by("-version").first()
    if publicado:
        return copy.deepcopy(publicado.content), str(publicado.version)
    with CATALOGO_ARQUIVO.open(encoding="utf-8") as arquivo:
        catalogo = _validar_catalogo(json.load(arquivo))
    return catalogo, str(catalogo.get("versao", "1"))


def _validar_respostas(respostas):
    if not isinstance(respostas, dict) or len(respostas) > 20:
        raise ValueError("Respostas inválidas.")
    desconhecidos = set(respostas) - LISTAS - set(TEXTOS) - {"proposta_editada"}
    if desconhecidos:
        raise ValueError("Campo de resposta desconhecido.")
    validadas = {}
    for campo, valor in respostas.items():
        if campo in LISTAS:
            if not isinstance(valor, list) or len(valor) > 20:
                raise ValueError(f"{campo} inválido.")
            validadas[campo] = [_texto(item, 100, campo) for item in valor]
        elif campo in TEXTOS:
            validadas[campo] = _texto(valor, TEXTOS[campo], campo)
        else:
            if not isinstance(valor, dict) or set(valor) - set(PROPOSTA_CAMPOS):
                raise ValueError("proposta_editada inválida.")
            validadas[campo] = {
                chave: (
                    _referencia(_texto(item, limite, chave))
                    if chave == "referencia"
                    else _texto(item, limite, chave)
                )
                for chave, item in valor.items()
                for limite in [PROPOSTA_CAMPOS[chave]]
            }
    return validadas


def _proposta(projeto, motivo, respostas):
    campos = (
        "chave",
        "titulo",
        "descricao",
        "direcao",
        "aplicacao",
        "servico",
        "primeira_entrega",
        "aprendizagem",
        "apresentacao",
        "primeira_acao",
        "referencia",
    )
    proposta = {campo: projeto.get(campo, "") for campo in campos}
    proposta["intencao"] = respostas.get("ideia_propria") or projeto.get("intencao", "")
    proposta["por_que"] = motivo
    proposta["expansao"] = projeto.get("expansao", "")
    proposta["feedback"] = projeto.get("feedback", "")
    if respostas.get("tamanho") == "um" and projeto.get("versao_pequena"):
        proposta["primeira_entrega"] = projeto["versao_pequena"]
    if respostas.get("habilidade"):
        proposta["aprendizagem"] = respostas["habilidade"]
    if respostas.get("servico_proprio"):
        proposta["servico"] = respostas["servico_proprio"]
    if respostas.get("objetivo_apresentacao"):
        proposta["apresentacao"] = respostas["objetivo_apresentacao"]
    if respostas.get("primeira_acao"):
        proposta["primeira_acao"] = respostas["primeira_acao"]
    return proposta


def _propostas(exploracao):
    respostas = exploracao.respostas
    projetos = exploracao.catalogo_snapshot.get("projetos", [])
    interesses = set(respostas.get("interesses", []))
    contextos = set(respostas.get("contextos", []))
    estilos = set(respostas.get("estilos", []))
    escolha = respostas.get("projeto_chave", "")

    def ordem(projeto):
        return (
            0 if projeto.get("chave") == escolha else 1,
            0 if projeto.get("familia") in interesses else 1,
            0 if contextos.intersection(projeto.get("contextos", [])) else 1,
            0 if estilos.intersection(projeto.get("estilos", [])) else 1,
            projeto.get("chave", ""),
        )

    sugestoes = []
    ideia = respostas.get("ideia_propria") or (
        respostas.get("modelos_prontos") if exploracao.entrada == "prontos" else ""
    )
    if ideia and escolha in {"", "ideia-do-aluno", "proprio"}:
        sugestoes.append(
            {
                "chave": "ideia-do-aluno",
                "titulo": ideia[:100],
                "descricao": ideia,
                "direcao": "Sua ideia",
                "aplicacao": respostas.get("objetivo_apresentacao", ""),
                "intencao": ideia,
                "servico": respostas.get("servico_proprio", ""),
                "primeira_entrega": "Selecione uma parte para começar ou apresente os modelos que já criou.",
                "aprendizagem": respostas.get("habilidade", ""),
                "apresentacao": respostas.get("objetivo_apresentacao", ""),
                "primeira_acao": respostas.get(
                    "primeira_acao", "Definir a primeira entrega."
                ),
                "por_que": "Você descreveu esta ideia como seu ponto de partida.",
                "referencia": "",
                "expansao": "",
                "feedback": "",
            }
        )
    if interesses and any(projeto.get("familia") in interesses for projeto in projetos):
        projetos = [
            projeto
            for projeto in projetos
            if projeto.get("familia") in interesses or projeto.get("chave") == escolha
        ]
    for projeto in sorted(projetos, key=ordem):
        if len(sugestoes) == 3:
            break
        if projeto.get("chave") == escolha:
            motivo = "Você escolheu este projeto diretamente."
        elif projeto.get("familia") in interesses:
            motivo = "Você escolheu esta família de criações."
        elif contextos.intersection(projeto.get("contextos", [])):
            motivo = "Este projeto combina com o contexto que você escolheu."
        elif estilos.intersection(projeto.get("estilos", [])):
            motivo = "Este projeto combina com o estilo que você escolheu."
        else:
            motivo = "Uma possibilidade para explorar e adaptar do seu jeito."
        sugestoes.append(_proposta(projeto, motivo, respostas))
    return sugestoes


def _serializar(exploracao):
    return {
        "id": str(exploracao.id),
        "entrada": exploracao.entrada,
        "etapa": exploracao.etapa,
        "respostas": exploracao.respostas,
        "versao": exploracao.versao,
        "propostas": _propostas(exploracao),
    }


@csrf_exempt
def catalogo(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method not in {"GET", "POST"}:
        return _erro("Método não permitido.", 405)
    try:
        dados = request.GET if request.method == "GET" else _json(request)
        site = _site(dados)
        if request.method == "GET":
            conteudo, versao = _catalogo(site)
            return JsonResponse({**conteudo, "versao": versao})
        if set(dados) != {"site_id", "catalogo"}:
            raise ValueError("Envie site_id e catalogo.")
        conteudo = _validar_catalogo(dados["catalogo"])
        if len(json.dumps(conteudo, ensure_ascii=False)) > 120_000:
            raise ValueError("Catálogo excede o tamanho permitido.")
        with transaction.atomic():
            Site.objects.select_for_update().get(pk=site.pk)
            atual = (
                PortfolioCatalog.objects.filter(site=site).order_by("-version").first()
            )
            nova_versao = (atual.version + 1) if atual else 2
            salvo = copy.deepcopy(conteudo)
            salvo["versao"] = str(nova_versao)
            PortfolioCatalog.objects.create(
                site=site, version=nova_versao, content=salvo
            )
        return JsonResponse(salvo, status=201)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    except (OSError, json.JSONDecodeError):
        return _erro("Catálogo indisponível.", 503)


@csrf_exempt
def exploracoes(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "POST":
        return _erro("Método não permitido.", 405)
    try:
        dados = _json(request)
        if set(dados) - {"site_id", "aluno_id", "entrada", "nova"}:
            raise ValueError("Campo desconhecido.")
        site, aluno_id = _identidade(dados)
        entrada = dados.get("entrada")
        if entrada not in ENTRADAS or not isinstance(dados.get("nova", False), bool):
            raise ValueError("Entrada ou nova inválida.")
        with transaction.atomic():
            # Serializa dois POSTs da mesma conta sem apagar tentativas anteriores.
            Site.objects.select_for_update().get(pk=site.pk)
            atual = (
                PortfolioExploration.objects.filter(site=site, aluno_id=aluno_id)
                .order_by("-created_at", "-id")
                .first()
            )
            if atual and not dados.get("nova", False):
                return JsonResponse(_serializar(atual))
            conteudo, versao = _catalogo(site)
            exploracao = PortfolioExploration.objects.create(
                site=site,
                aluno_id=aluno_id,
                entrada=entrada,
                versao=versao,
                catalogo_snapshot=conteudo,
            )
        return JsonResponse(_serializar(exploracao), status=201)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    except (OSError, json.JSONDecodeError):
        return _erro("Catálogo indisponível.", 503)


def exploracao_atual(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "GET":
        return _erro("Método não permitido.", 405)
    try:
        site, aluno_id = _identidade(request.GET)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    atual = (
        PortfolioExploration.objects.filter(site=site, aluno_id=aluno_id)
        .order_by("-created_at", "-id")
        .first()
    )
    return (
        JsonResponse(_serializar(atual))
        if atual
        else _erro("Exploração não encontrada.", 404)
    )


@csrf_exempt
def exploracao(request, exploracao_id):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "GET":
        return _erro("Método não permitido.", 405)
    try:
        site, aluno_id = _identidade(request.GET)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    registro = PortfolioExploration.objects.filter(
        pk=exploracao_id, site=site, aluno_id=aluno_id
    ).first()
    return (
        JsonResponse(_serializar(registro))
        if registro
        else _erro("Exploração não encontrada.", 404)
    )


@csrf_exempt
def respostas(request, exploracao_id):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "POST":
        return _erro("Método não permitido.", 405)
    try:
        dados = _json(request)
        if set(dados) != {"site_id", "aluno_id", "etapa", "respostas"}:
            raise ValueError("Envie site_id, aluno_id, etapa e respostas.")
        site, aluno_id = _identidade(dados)
        etapa = dados["etapa"]
        if etapa not in ETAPAS:
            raise ValueError("Etapa inválida.")
        novas = _validar_respostas(dados["respostas"])
        with transaction.atomic():
            registro = (
                PortfolioExploration.objects.select_for_update()
                .filter(pk=exploracao_id, site=site, aluno_id=aluno_id)
                .first()
            )
            if registro is None:
                return _erro("Exploração não encontrada.", 404)
            atualizadas = {**registro.respostas, **novas}
            if "proposta_editada" in novas:
                atualizadas["proposta_editada"] = {
                    **registro.respostas.get("proposta_editada", {}),
                    **novas["proposta_editada"],
                }
            registro.respostas = atualizadas
            registro.etapa = etapa
            registro.save(update_fields=["respostas", "etapa", "updated_at"])
        return JsonResponse(_serializar(registro))
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)


def referencia(request, chave):
    # Referências são obras próprias e públicas, sem dados de aluno.
    arquivo = REFERENCIAS / f"{chave}.svg"
    if not arquivo.is_file():
        return _erro("Imagem não encontrada.", 404)
    return FileResponse(arquivo.open("rb"), content_type="image/svg+xml")
