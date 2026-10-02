"""Melhoria contínua do quiz: leitura de gargalos e propostas de nova versão.

Nada aqui altera uma versão existente. A leitura só mede; a proposta só
registra a ideia e a decisão, e aceitar apenas indica a key nova que o estúdio
deve criar.
"""

import json
import re
from collections import defaultdict

from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt

from .campanhas import (
    AMOSTRA_MINIMA,
    FUSO,
    SEM_COMPRA,
    coletar_sessoes,
    etapas_das_versoes,
    funis_por_versao,
    taxa,
)
from .editor import _authorized, _error
from .models import PropostaDeVersao
from .painel_campanhas import _quiz_privado


AVISO_COMPARACAO = (
    "Campanhas são direcionadas, não aleatórias: comparar versões ou campanhas "
    "mostra o que aconteceu em cada link, mas não prova que uma delas causa o resultado."
)
AVISO_AMOSTRA = (
    f"Com menos de {AMOSTRA_MINIMA} sessões a leitura é inconclusiva: "
    "serve para observar, não para decidir."
)
SEM_CAMPANHA = "(sem campanha)"
ORDEM_PRIORIDADE = {"alta": 0, "media": 1, "baixa": 2, "inconclusiva": 3}


def _prioridade(medida):
    if medida["inconclusiva"]:
        return "inconclusiva"
    valor = medida["valor"] or 0
    if valor >= 0.5:
        return "alta"
    if valor >= 0.25:
        return "media"
    return "baixa"


def _pct(medida):
    return f"{round((medida['valor'] or 0) * 100)}%"


def _gargalo(identidade, escopo, versao, tipo, medida, texto):
    prioridade = _prioridade(medida)
    return {
        "id": identidade,
        "tipo": tipo,
        "escopo": escopo,
        "version_key": versao,
        "prioridade": prioridade,
        "evidencia": {
            "numerador": medida["numerador"],
            "denominador": medida["denominador"],
            "valor": medida["valor"],
            "texto": f"{texto} ({medida['numerador']} de {medida['denominador']}, {_pct(medida)})",
        },
        "inconclusivo": prioridade == "inconclusiva",
        "observacao": AVISO_AMOSTRA if prioridade == "inconclusiva" else "",
    }


def gargalos_do_funil(funil, escopo):
    """Etapa com maior perda relativa e conclusões sem clique de saída."""
    if not funil["visitas_elegiveis"]:
        return []
    versao = funil["version_key"]
    chave = escopo["chave"]
    achados = []
    candidatas = [e for e in funil["etapas"] if e["perda"] and e["viram"]]
    if candidatas:
        pior = max(candidatas, key=lambda e: (e["perda"] / e["viram"], e["viram"]))
        medida = taxa(pior["perda"], pior["viram"])
        achados.append(
            _gargalo(
                f"etapa:{chave}:{versao}:{pior['etapa']}",
                escopo,
                versao,
                "etapa_com_maior_perda",
                medida,
                f"{pior['rotulo']}: sessões que viram a etapa e não seguiram adiante",
            )
        )
    if funil["conclusoes"] and funil["conclusoes_sem_saida"] > 0:
        medida = taxa(funil["conclusoes_sem_saida"], funil["conclusoes"])
        achados.append(
            _gargalo(
                f"saida:{chave}:{versao}",
                escopo,
                versao,
                "conclusoes_sem_saida",
                medida,
                "Conclusões sem clique de saída",
            )
        )
    return achados


def _ordenar(gargalos):
    return sorted(
        gargalos,
        key=lambda g: (
            ORDEM_PRIORIDADE[g["prioridade"]],
            -(g["evidencia"]["valor"] or 0),
            -g["evidencia"]["denominador"],
            g["id"],
        ),
    )


def _resumo(funil):
    return {
        "version_key": funil["version_key"],
        "visitas_elegiveis": funil["visitas_elegiveis"],
        "conclusoes": funil["conclusoes"],
        "saidas_reais": funil["saidas_reais"],
        "saidas_demonstracao": funil["saidas_demonstracao"],
        "taxa_conclusao": funil["taxa_conclusao"],
        "taxa_saida_total": funil["taxa_saida_total"],
        "comercial": funil["comercial"],
    }


def _campanha_da_sessao(sessao):
    return sessao["contexto"].get("cpg") or sessao["utm"].get("campaign") or ""


SEM_VALOR = "(sem valor)"

# Cortes da arquitetura de URL: cada um vira um funil por versão, como a
# leitura por campanha. O parâmetro interno vale primeiro; a UTM correspondente
# cobre quem chegou só com ela.
DIMENSOES = (
    ("formato", "Formato (fmt)", lambda s: s["contexto"].get("fmt")),
    ("segmento", "Segmento (seg)", lambda s: s["contexto"].get("seg")),
    ("origem", "Origem (src / utm_source)",
     lambda s: s["contexto"].get("src") or s["utm"].get("source")),
    ("meio", "Meio (med / utm_medium)",
     lambda s: s["contexto"].get("med") or s["utm"].get("medium")),
    ("criativo", "Criativo (ctv / utm_content)",
     lambda s: s["contexto"].get("ctv") or s["utm"].get("content")),
    ("termo", "Termo (utm_term)", lambda s: s["utm"].get("term")),
)


def _sem_origem(sessao):
    return not _campanha_da_sessao(sessao) and not any(
        sessao["utm"].get(campo) for campo in ("source", "medium", "campaign")
    ) and not sessao["contexto"].get("src")


def _escopos(quiz, sessoes, conhecidas, tipo, agrupar):
    grupos = defaultdict(list)
    for sessao in sessoes:
        grupos[agrupar(sessao)].append(sessao)
    resultado = []
    for nome, itens in sorted(grupos.items()):
        escopo = {"tipo": tipo, "chave": f"{tipo}={nome}", "nome": nome}
        funis = [
            f
            for f in funis_por_versao(quiz, itens, conhecidas)
            if f["visitas_elegiveis"]
        ]
        gargalos = _ordenar(
            [g for f in funis for g in gargalos_do_funil(f, escopo)]
        )
        resultado.append(
            {
                **escopo,
                "sessoes": sum(1 for s in itens if not s["teste"]),
                "versoes": [_resumo(f) for f in funis],
                "gargalos": gargalos,
            }
        )
    return resultado


def _comparacao(escopos, rotulo):
    linhas = []
    for escopo in escopos:
        for versao in escopo["versoes"]:
            linhas.append(
                {
                    rotulo: escopo["nome"],
                    "version_key": versao["version_key"],
                    "taxa_conclusao": versao["taxa_conclusao"],
                    "inconclusiva": versao["taxa_conclusao"]["inconclusiva"],
                }
            )
    return linhas if len({(l[rotulo], l["version_key"]) for l in linhas}) >= 2 else []


def leitura_diaria(quiz, inicio=None, fim=None):
    coleta = coletar_sessoes(quiz, inicio, fim)
    sessoes = coleta["sessoes"]
    reais = [s for s in sessoes if not s["teste"]]
    conhecidas = etapas_das_versoes(quiz)
    geral = {"tipo": "geral", "chave": "geral", "nome": "Todas as visitas"}
    funis = funis_por_versao(quiz, sessoes, conhecidas)
    gargalos = [g for f in funis if f["visitas_elegiveis"] for g in gargalos_do_funil(f, geral)]

    por_dia = _escopos(quiz, reais, conhecidas, "dia", lambda s: s["dia"].isoformat())
    por_campanha = _escopos(
        quiz, reais, conhecidas, "campanha", lambda s: _campanha_da_sessao(s) or SEM_CAMPANHA
    )

    por_dimensao = [
        {
            "tipo": tipo,
            "rotulo": rotulo,
            "escopos": _escopos(quiz, reais, conhecidas, tipo, lambda s, f=valor: f(s) or SEM_VALOR),
        }
        for tipo, rotulo, valor in DIMENSOES
    ]

    faltantes = []
    for funil in funis:
        if funil["ativa"] and not funil["visitas_elegiveis"]:
            faltantes.append(
                {
                    "tipo": "versao_sem_visitas",
                    "version_key": funil["version_key"],
                    "texto": f"A versão {funil['version_key']} está ativa e não teve visitas no período.",
                }
            )
        if not funil["cadastrada"] and funil["visitas_elegiveis"]:
            faltantes.append(
                {
                    "tipo": "versao_nao_cadastrada",
                    "version_key": funil["version_key"],
                    "texto": f"Há visitas na versão {funil['version_key']}, que não está cadastrada no quiz.",
                }
            )
        if funil["conclusoes"] and not funil["saidas_reais"]:
            faltantes.append(
                {
                    "tipo": "sem_saida_real",
                    "version_key": funil["version_key"],
                    "texto": (
                        f"A versão {funil['version_key']} tem conclusões e nenhuma saída real para o checkout"
                        + (
                            f" ({funil['saidas_demonstracao']} saída(s) de demonstração)."
                            if funil["saidas_demonstracao"]
                            else "."
                        )
                    ),
                }
            )
    sem_origem = sum(1 for s in reais if _sem_origem(s))
    if sem_origem:
        faltantes.append(
            {
                "tipo": "campanha_sem_utm",
                "quantidade": sem_origem,
                "texto": f"{sem_origem} sessão(ões) chegaram sem utm nem campanha marcada.",
            }
        )
    if coleta["conclusoes_sem_visita"]:
        faltantes.append(
            {
                "tipo": "conclusoes_sem_visita",
                "quantidade": coleta["conclusoes_sem_visita"],
                "texto": (
                    f"{coleta['conclusoes_sem_visita']} conclusão(ões) sem abertura registrada "
                    "ficaram fora do funil."
                ),
            }
        )
    faltantes.append(
        {
            "tipo": "sem_dados_de_compra",
            "texto": "Compras, receita e LTV: sem dados de compra. Nenhuma taxa comercial é calculada.",
        }
    )

    comparacoes = {
        "aviso": AVISO_COMPARACAO,
        "versoes": _comparacao(
            [
                {"nome": "geral", "versoes": [_resumo(f) for f in funis if f["visitas_elegiveis"]]}
            ],
            "escopo",
        ),
        "campanhas": _comparacao(por_campanha, "campanha"),
    }
    return {
        "site_id": quiz.site_id,
        "quiz_slug": quiz.slug,
        "periodo": {
            "inicio": coleta["inicio"].isoformat() if coleta["inicio"] else None,
            "fim": coleta["fim"].isoformat() if coleta["fim"] else None,
            "fuso": FUSO.key,
        },
        "denominador": "sessões distintas com abertura do quiz registrada, sem tráfego de teste",
        "amostra_minima": AMOSTRA_MINIMA,
        "visitas_elegiveis": len(reais),
        "teste": {
            "visitas": len(sessoes) - len(reais),
            "conclusoes": sum(1 for s in sessoes if s["teste"] and s["concluiu"]),
        },
        "comercial": {"estado": SEM_COMPRA},
        "gargalos": _ordenar(gargalos),
        "dados_faltantes": faltantes,
        "por_dia": por_dia,
        "por_campanha": por_campanha,
        "por_dimensao": por_dimensao,
        "comparacoes": comparacoes,
        "funil": funis,
        "avisos": [AVISO_COMPARACAO, AVISO_AMOSTRA],
    }


# ---------------------------------------------------------------------------
# Propostas de nova versão
# ---------------------------------------------------------------------------

KEY = re.compile(r"^[A-Za-z0-9_-]{1,100}$")
TRANSICOES = {
    "proposta": {"aceita", "descartada"},
    "aceita": {"publicada", "descartada"},
    "publicada": {"medida"},
    "descartada": set(),
    "medida": set(),
}
CAMPOS_TEXTO = ("gargalo", "hipotese", "mudanca", "resultado_texto", "decisao_seguinte")


def serializar(proposta):
    def quando(valor):
        return valor.isoformat() if valor else None

    dados = {
        "id": proposta.id,
        "quiz_slug": proposta.quiz.slug,
        "versao_base": proposta.versao_base,
        "gargalo": proposta.gargalo,
        "hipotese": proposta.hipotese,
        "prioridade": proposta.prioridade,
        "mudanca": proposta.mudanca,
        "key_sugerida": proposta.key_sugerida,
        "estado": proposta.estado,
        "criada_em": quando(proposta.criada_em),
        "aceita_em": quando(proposta.aceita_em),
        "descartada_em": quando(proposta.descartada_em),
        "publicada_em": quando(proposta.publicada_em),
        "medida_em": quando(proposta.medida_em),
        "resultado_texto": proposta.resultado_texto,
        "resultado_json": proposta.resultado_json,
        "decisao_seguinte": proposta.decisao_seguinte,
    }
    if proposta.estado == "aceita":
        dados["criar_no_estudio"] = {
            "key": proposta.key_sugerida,
            "a_partir_de": proposta.versao_base,
            "mensagem": (
                f"Crie a versão {proposta.key_sugerida} no estúdio, a partir da "
                f"{proposta.versao_base}. A versão {proposta.versao_base} não foi alterada."
            ),
        }
    return dados


def _texto(dados, campo, obrigatorio=False, maximo=4000):
    valor = dados.get(campo)
    if valor is None:
        if obrigatorio:
            raise ValueError(f"Preencha {campo}.")
        return None
    if not isinstance(valor, str):
        raise ValueError(f"{campo} deve ser texto.")
    valor = valor.strip()
    if obrigatorio and not valor:
        raise ValueError(f"Preencha {campo}.")
    if len(valor) > maximo:
        raise ValueError(f"{campo} é longo demais.")
    return valor


def _key_livre(quiz, key, ignorar_id=None):
    if not isinstance(key, str) or not KEY.fullmatch(key):
        raise ValueError("A key sugerida usa letras, números, hífen e sublinhado.")
    if quiz.versions.filter(key=key).exists():
        raise ValueError(
            f"Já existe a versão {key}. Proponha uma key nova; versões existentes não mudam."
        )
    outras = PropostaDeVersao.objects.filter(
        quiz=quiz, key_sugerida=key, estado__in=("proposta", "aceita", "publicada")
    )
    if ignorar_id:
        outras = outras.exclude(pk=ignorar_id)
    if outras.exists():
        raise ValueError(f"Outra proposta em andamento já usa a key {key}.")


def criar_proposta(quiz, dados):
    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON.")
    base = _texto(dados, "versao_base", True, 100)
    if not quiz.versions.filter(key=base).exists():
        raise ValueError(f"A versão base {base} não existe neste quiz.")
    prioridade = _texto(dados, "prioridade", False, 8) or "media"
    if prioridade not in ORDEM_PRIORIDADE or prioridade == "inconclusiva":
        raise ValueError("A prioridade deve ser alta, media ou baixa.")
    key = _texto(dados, "key_sugerida", True, 100)
    _key_livre(quiz, key)
    return PropostaDeVersao.objects.create(
        quiz=quiz,
        versao_base=base,
        gargalo=_texto(dados, "gargalo", False, 200) or "",
        hipotese=_texto(dados, "hipotese", True),
        prioridade=prioridade,
        mudanca=_texto(dados, "mudanca", True),
        key_sugerida=key,
    )


def atualizar_proposta(proposta, dados):
    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON.")
    quiz = proposta.quiz
    agora = timezone.now()
    textos = {c: _texto(dados, c) for c in CAMPOS_TEXTO if c in dados}
    for campo in ("hipotese", "mudanca"):
        if campo in textos and not textos[campo]:
            raise ValueError(f"Preencha {campo}.")
    if "prioridade" in dados:
        if dados["prioridade"] not in ("alta", "media", "baixa"):
            raise ValueError("A prioridade deve ser alta, media ou baixa.")
        proposta.prioridade = dados["prioridade"]
    if "key_sugerida" in dados and dados["key_sugerida"] != proposta.key_sugerida:
        if proposta.estado not in ("proposta", "aceita"):
            raise ValueError("A key só muda enquanto a proposta não foi publicada.")
        _key_livre(quiz, dados["key_sugerida"], proposta.pk)
        proposta.key_sugerida = dados["key_sugerida"]
    if "resultado_json" in dados:
        if not isinstance(dados["resultado_json"], dict):
            raise ValueError("resultado_json deve ser um objeto.")
        proposta.resultado_json = dados["resultado_json"]
    for campo, valor in textos.items():
        setattr(proposta, campo, valor)

    novo = dados.get("estado")
    if novo is not None and novo != proposta.estado:
        if novo not in TRANSICOES.get(proposta.estado, ()):
            raise ValueError(
                f"Não dá para passar de {proposta.estado} para {novo}."
            )
        if novo == "aceita":
            _key_livre(quiz, proposta.key_sugerida, proposta.pk)
            proposta.aceita_em = agora
        elif novo == "descartada":
            proposta.descartada_em = agora
        elif novo == "publicada":
            if not quiz.versions.filter(key=proposta.key_sugerida).exists():
                raise ValueError(
                    f"A versão {proposta.key_sugerida} ainda não existe no quiz; crie e publique no estúdio antes."
                )
            proposta.publicada_em = agora
        elif novo == "medida":
            if not proposta.resultado_texto and not proposta.resultado_json:
                raise ValueError("Registre o resultado observado antes de marcar como medida.")
            proposta.medida_em = agora
        proposta.estado = novo
    proposta.save()
    return proposta


def _corpo(request):
    try:
        return json.loads(request.body or b"{}")
    except (UnicodeDecodeError, ValueError):
        raise ValueError("Corpo JSON inválido.")


def _entrada(request, slug, metodos):
    if not _authorized(request):
        return None, _error("Não autorizado.", 401)
    if request.method not in metodos:
        return None, _error("Método não permitido.", 405)
    quiz = _quiz_privado(request, slug)
    if quiz is None:
        return None, _error("Quiz ou site não encontrado.", 404)
    return quiz, None


@csrf_exempt
def propostas(request, slug):
    quiz, erro = _entrada(request, slug, ("GET", "POST"))
    if erro:
        return erro
    if request.method == "GET":
        itens = quiz.propostas.select_related("quiz")
        estado = request.GET.get("estado")
        if estado:
            itens = itens.filter(estado=estado)
        return JsonResponse(
            {
                "quiz_slug": quiz.slug,
                "propostas": [serializar(p) for p in itens],
                "aviso": "Propostas não alteram versões existentes.",
            }
        )
    try:
        proposta = criar_proposta(quiz, _corpo(request))
    except ValueError as falha:
        return _error(str(falha), 422)
    return JsonResponse(serializar(proposta), status=201)


@csrf_exempt
def proposta(request, slug, proposta_id):
    quiz, erro = _entrada(request, slug, ("GET", "PATCH", "PUT"))
    if erro:
        return erro
    item = quiz.propostas.select_related("quiz").filter(pk=proposta_id).first()
    if item is None:
        return _error("Proposta não encontrada.", 404)
    if request.method == "GET":
        return JsonResponse(serializar(item))
    try:
        item = atualizar_proposta(item, _corpo(request))
    except ValueError as falha:
        return _error(str(falha), 422)
    return JsonResponse(serializar(item))


def leitura(request, slug):
    quiz, erro = _entrada(request, slug, ("GET",))
    if erro:
        return erro
    try:
        dados = leitura_diaria(
            quiz,
            inicio=request.GET.get("inicio") or None,
            fim=request.GET.get("fim") or None,
        )
    except ValueError as falha:
        return _error(str(falha), 422)
    return JsonResponse(dados)
