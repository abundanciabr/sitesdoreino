"""`/admin/paginas/experimentos/`: criar e conduzir um experimento da página.

Um experimento troca UM espaço da página de oferta para uma parte das visitas:
o braço `a` é o texto que está no ar, o braço `b` é o texto novo. Esta tela é
onde o mantenedor cria o experimento, põe no ar e encerra. O resultado mora em
outra tela, e a decisão de promover ou reverter em outra ainda.

## Onde o dado mora, e por que não aqui

No `catalogo`, dono da página (frente F5 do sistema de experimentos). É lá que
o sorteio do `funil` lê o experimento ativo, e uma cópia aqui seria o mesmo
fato em dois lugares. Esta célula só fala pelo cliente do catálogo.

## Três estados, e nenhum deles é pausa

`rascunho` não muda o site. `ativo` põe o braço `b` no ar para a parte das
visitas escolhida. `encerrado` é definitivo. Não existe pausar nem retomar
(decisão da sessão de 26/09/2026, após a segunda opinião sobre o sistema de
experimentos): quem visitou durante a pausa veria o texto `a` com o braço `b`
registrado, e a conta do resultado misturaria os dois.
Parar é encerrar; testar de novo é criar outro, com sorteio novo. A tela diz
isso onde o gesto aparece, para a ausência do botão não parecer defeito.

## O braço `a` sai da página no ar, nunca do formulário

No momento de salvar, a tela relê a versão publicada e manda o texto dela.
Aceitar o `a` do formulário deixaria um campo escondido decidir o controle do
experimento, e o controle só vale se for o que as visitas de fato viam.

## O plano é fixado antes de começar

Métrica principal, taxa base, efeito mínimo detectável e dias planejados são
escritos no rascunho, e a amostra por braço sai deles pela conta da tela de
resultado (`n_por_braco_planejado`). Escolher o tamanho do teste depois de ver
o placar é o erro que o horizonte fixo existe para impedir.

## Repetir um gesto é seguro

Duplo clique no Iniciar manda duas vezes. O catálogo responde 409 à segunda,
porque o experimento já saiu do rascunho; a tela relê o experimento e, se ele
já está no estado pedido, responde o mesmo sucesso da primeira, sem segunda
linha de auditoria. Só quando o experimento continua em rascunho o 409 é o
conflito de verdade: outro experimento ativo ocupa a página.

## Sem script

Pelos mesmos motivos de `apps/core/paginas.py`: cada gesto é um POST que
recarrega a página, e a política de segurança da área proíbe script embutido.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient
from .paginas import SECOES, SLUG_DA_PAGINA, _site
from .resultado_do_experimento import n_por_braco_planejado
from .views import _auditar

#: O espaço do primeiro experimento, que é o que a tela abre escolhido.
ESPACO_PADRAO = "cubo.headline"

#: O vocabulário do catálogo, na ordem da página, como `seção.espaço`.
ESPACOS = tuple(f"{secao.nome}.{nome}" for secao in SECOES for nome in secao.espacos())

#: A métrica que decide o experimento. Uma só hoje, porque é a única que a
#: leitura do funil conta por braço (`convertidos`); a próxima entra aqui.
METRICAS = {"cta_checkout": "Entrada no checkout"}

ROTULO_DO_ESTADO = {"rascunho": "Rascunho", "ativo": "Ativo", "encerrado": "Encerrado"}

#: Os pesos viajam em pontos-base e somam isto (50/50 é 5000 e 5000).
PESO_TOTAL = 10000

CAMPOS = (
    "espaco",
    "hipotese",
    "texto_b",
    "parte_b",
    "metrica_principal",
    "taxa_base",
    "mde",
    "dias_planejados",
)


# ---------------------------------------------------------------------------
# Números como ele escreve
# ---------------------------------------------------------------------------
def _decimal(texto: str) -> "float | None":
    """`10`, `10,5` ou `10.5`. `None` quando não é número."""
    try:
        return float(texto.replace(",", "."))
    except ValueError:
        return None


def _inteiro(texto: str) -> "int | None":
    return int(texto) if texto.isascii() and texto.isdigit() else None


def _porcento(fracao) -> str:
    """0.105 vira `10,5`: a fração do catálogo escrita como ele lê."""
    if not isinstance(fracao, (int, float)):
        return ""
    return f"{fracao * 100:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _milhar(numero) -> str:
    return f"{numero:,}".replace(",", ".") if isinstance(numero, int) else ""


# ---------------------------------------------------------------------------
# O formulário
# ---------------------------------------------------------------------------
def _escrito_do_formulario(post) -> dict[str, str]:
    return {campo: (post.get(campo) or "").strip() for campo in CAMPOS}


def _plano(escrito) -> "tuple[dict[str, str], float | None, float | None]":
    """Taxa base e efeito mínimo como frações, com a frase de cada recusa."""
    erros = {}
    taxa = _decimal(escrito["taxa_base"])
    if taxa is None or not 0 < taxa < 100:
        erros["taxa_base"] = (
            "A taxa base é a porcentagem de hoje, maior que 0 e menor que 100 "
            "(por exemplo 10)."
        )
    mde = _decimal(escrito["mde"])
    if mde is None or not 0 < mde < 100:
        erros["mde"] = (
            "O efeito mínimo detectável é quantos pontos a taxa precisa subir, "
            "maior que 0 (por exemplo 2)."
        )
    if not erros and taxa + mde >= 100:
        erros["mde"] = (
            "A taxa base somada ao efeito mínimo passa de 100%. Diminua o efeito "
            "mínimo."
        )
    if erros:
        return erros, None, None
    return {}, taxa / 100, mde / 100


def _recusas(escrito) -> dict[str, str]:
    """Tudo o que não faz sentido, antes de perguntar ao catálogo."""
    erros, _, _ = _plano(escrito)
    if escrito["espaco"] not in ESPACOS:
        erros["espaco"] = (
            f"{escrito['espaco'] or 'O espaço escolhido'} não é um espaço da "
            "página. Escolha um da lista."
        )
    if not escrito["hipotese"]:
        erros["hipotese"] = "Escreva a hipótese: o que você espera que mude, e por quê."
    if not escrito["texto_b"]:
        erros["texto_b"] = (
            "Escreva o texto do braço b. Para um teste A/A, use o botão que copia "
            "o texto atual."
        )
    parte = _inteiro(escrito["parte_b"])
    if parte is None or not 1 <= parte <= 99:
        erros["parte_b"] = (
            "A parte das visitas que vê o braço b precisa ser um número inteiro "
            "entre 1 e 99."
        )
    if escrito["metrica_principal"] not in METRICAS:
        erros["metrica_principal"] = "Escolha a métrica principal da lista."
    dias = _inteiro(escrito["dias_planejados"])
    if dias is None or dias < 1:
        erros["dias_planejados"] = (
            "Os dias planejados precisam ser um número inteiro, de 1 para cima."
        )
    return erros


def _corpo_do_experimento(escrito, texto_a: str) -> dict:
    """O experimento na forma que o catálogo recebe. Só chamado sem recusa."""
    _, taxa, mde = _plano(escrito)
    secao, slot = escrito["espaco"].split(".", 1)
    peso_b = int(escrito["parte_b"]) * PESO_TOTAL // 100
    return {
        "secao": secao,
        "slot": slot,
        "hipotese": escrito["hipotese"],
        "metrica_principal": escrito["metrica_principal"],
        "taxa_base": taxa,
        "mde": mde,
        "n_por_braco_planejado": n_por_braco_planejado(taxa, mde),
        "dias_planejados": int(escrito["dias_planejados"]),
        "variantes": [
            {"variante_id": "a", "peso": PESO_TOTAL - peso_b, "valor": texto_a},
            {"variante_id": "b", "peso": peso_b, "valor": escrito["texto_b"]},
        ],
    }


def _texto_no_ar(site, espaco: str) -> "tuple[str, str]":
    """`(situação, texto)` do espaço na versão publicada.

    Espaço ausente da versão no ar volta `OK` com texto vazio: é resposta, e a
    tela diz que não há o que testar ali.
    """
    situacao, pagina = CatalogoClient().pagina_publicada(site["id"], SLUG_DA_PAGINA)
    if situacao != CatalogoClient.OK:
        return situacao, pagina
    secao, slot = espaco.split(".", 1)
    for bloco in pagina.get("secoes") or []:
        if isinstance(bloco, dict) and bloco.get("nome") == secao:
            slots = bloco.get("slots")
            texto = slots.get(slot) if isinstance(slots, dict) else None
            return situacao, texto if isinstance(texto, str) else ""
    return situacao, ""


def _no_ar(situacao: str, texto_a: str) -> str:
    """O que a tela diz sobre o braço `a`, numa palavra que o template lê."""
    if situacao == CatalogoClient.SEM_PAGINA:
        return "nunca_publicada"
    if situacao != CatalogoClient.OK:
        return "nao_leu"
    return "ok" if texto_a.strip() else "vazio"


def _formulario(request, site, escrito, *, erros=None, motivo="", erro="", status=200):
    """A tela do experimento novo, sempre com o que ele já digitou."""
    erros = erros or {}
    texto_a, situacao = "", ""
    if escrito["espaco"] in ESPACOS:
        situacao, texto_a = _texto_no_ar(site, escrito["espaco"])
    no_ar = _no_ar(situacao, texto_a) if situacao else "sem_espaco"
    _, taxa, mde = _plano(escrito)
    return render(
        request,
        "admin/experimento_novo.html",
        {
            "admin": request.admin,
            "escrito": escrito,
            "texto_a": texto_a if no_ar == "ok" else "",
            "no_ar": no_ar,
            "grupos": [
                (secao.e, [f"{secao.nome}.{nome}" for nome in secao.espacos()])
                for secao in SECOES
            ],
            "metricas": METRICAS.items(),
            "amostra": (
                _milhar(n_por_braco_planejado(taxa, mde)) if taxa is not None else ""
            ),
            "erros": list(erros.values()),
            "motivo": motivo,
            "erro": erro,
        },
        status=status,
    )


def _sem_catalogo(request, template: str, status: int = 200):
    """Fail-OPEN como a tela da página: aviso honesto, nunca 500, sem gesto."""
    return render(
        request, template, {"admin": request.admin, "sem_catalogo": True}, status=status
    )


@require_http_methods(["GET", "POST"])
def experimento_novo(request):
    """GET abre o formulário; POST calcula a amostra ou salva em rascunho."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(
            request,
            "admin/experimento_novo.html",
            status=503 if request.method == "POST" else 200,
        )

    if request.method == "GET":
        espaco = request.GET.get("espaco") or ESPACO_PADRAO
        escrito = dict.fromkeys(CAMPOS, "")
        escrito.update(
            espaco=espaco if espaco in ESPACOS else ESPACO_PADRAO,
            parte_b="50",
            metrica_principal=next(iter(METRICAS)),
        )
        if request.GET.get("copiar"):
            situacao, texto_a = _texto_no_ar(site, escrito["espaco"])
            if situacao == CatalogoClient.OK:
                escrito["texto_b"] = texto_a
        return _formulario(request, site, escrito)

    escrito = _escrito_do_formulario(request.POST)
    if request.POST.get("gesto") != "salvar":
        erros, _, _ = _plano(escrito)
        return _formulario(request, site, escrito, erros=erros)

    erros = _recusas(escrito)
    if erros:
        return _formulario(request, site, escrito, erros=erros, status=422)

    situacao, texto_a = _texto_no_ar(site, escrito["espaco"])
    if situacao != CatalogoClient.OK or not texto_a.strip():
        return _formulario(request, site, escrito, status=422)

    situacao, resposta = CatalogoClient().criar_experimento(
        site["id"], SLUG_DA_PAGINA, _corpo_do_experimento(escrito, texto_a)
    )
    detalhe = (
        f"{SLUG_DA_PAGINA}: {escrito['espaco']}, braço b com "
        f"{escrito['parte_b']}% das visitas"
    )
    if situacao == CatalogoClient.OK:
        _auditar(
            request,
            Registro.CRIAR_EXPERIMENTO,
            str(resposta.get("id") or SLUG_DA_PAGINA),
            Registro.OK,
            detalhe,
        )
        return HttpResponseRedirect(f"{reverse('experimentos')}?recado=criado")

    recusado = situacao in (CatalogoClient.RECUSADO, CatalogoClient.SEM_PAGINA)
    _auditar(
        request,
        Registro.CRIAR_EXPERIMENTO,
        SLUG_DA_PAGINA,
        Registro.RECUSADO_PELA_CELULA if recusado else Registro.NAO_RESPONDEU,
        f"{detalhe}: {resposta}",
    )
    return _formulario(
        request,
        site,
        escrito,
        motivo="recusado" if recusado else "nao_salvou",
        erro=resposta,
        status=422 if recusado else 503,
    )


# ---------------------------------------------------------------------------
# A lista e os dois gestos do ciclo
# ---------------------------------------------------------------------------
def _para_a_tela(experimento: dict) -> dict:
    estado = experimento.get("estado") or ""
    return {
        "id": str(experimento.get("id") or ""),
        "espaco": f"{experimento.get('secao')}.{experimento.get('slot')}",
        "hipotese": experimento.get("hipotese") or "",
        "estado": estado,
        "rotulo": ROTULO_DO_ESTADO.get(estado, estado),
        "metrica": METRICAS.get(
            experimento.get("metrica_principal"), experimento.get("metrica_principal")
        ),
        "taxa_base": _porcento(experimento.get("taxa_base")),
        "mde": _porcento(experimento.get("mde")),
        "amostra": _milhar(experimento.get("n_por_braco_planejado")),
        "dias": experimento.get("dias_planejados"),
        "iniciado_em": parse_datetime(experimento.get("iniciado_em") or ""),
        "fim_planejado": parse_datetime(experimento.get("fim_planejado") or ""),
        "variantes": [
            {
                "variante_id": v.get("variante_id"),
                "parte": _porcento((v.get("peso") or 0) / PESO_TOTAL),
                "valor": v.get("valor") or "",
            }
            for v in experimento.get("variantes") or []
            if isinstance(v, dict)
        ],
    }


def _lista(request, site, *, recado="", motivo="", gesto="", erro="", status=200):
    situacao, lista = CatalogoClient().experimentos_da_pagina(
        site["id"], SLUG_DA_PAGINA
    )
    contexto = {
        "admin": request.admin,
        "recado": recado,
        "motivo": motivo,
        "gesto": gesto,
        "erro": erro,
    }
    if situacao != CatalogoClient.OK:
        contexto.update(sem_leitura=True, erro_da_leitura=lista)
    else:
        experimentos = [_para_a_tela(e) for e in lista]
        contexto.update(
            experimentos=experimentos,
            ha_ativo=any(e["estado"] == "ativo" for e in experimentos),
        )
    return render(request, "admin/experimentos.html", contexto, status=status)


@require_GET
def experimentos(request):
    """Os experimentos da página de oferta, cada um com o gesto do estado dele."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, "admin/experimentos.html")
    return _lista(request, site, recado=request.GET.get("recado", ""))


def _conduzir(request, experimento_id, *, gesto, mudar, estado_pedido, acao, recado):
    """Iniciar e encerrar: o mesmo caminho, com o 409 relido antes de virar erro."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, "admin/experimentos.html", status=503)

    catalogo = CatalogoClient()
    alvo = str(experimento_id)
    situacao, resposta = mudar(catalogo, alvo)
    sucesso = HttpResponseRedirect(f"{reverse('experimentos')}?recado={recado}")
    if situacao == CatalogoClient.OK:
        _auditar(request, acao, alvo, Registro.OK, SLUG_DA_PAGINA)
        return sucesso

    motivo = "nao_respondeu"
    if situacao == CatalogoClient.CONFLITO:
        lido, experimento = catalogo.experimento(alvo)
        estado = experimento.get("estado") if lido == CatalogoClient.OK else None
        if estado == estado_pedido:
            return sucesso
        motivo = "ja_existe_ativo" if estado == "rascunho" else "recusado"
    elif situacao in (CatalogoClient.RECUSADO, CatalogoClient.SEM_EXPERIMENTO):
        motivo = "recusado"

    recusado = motivo != "nao_respondeu"
    _auditar(
        request,
        acao,
        alvo,
        Registro.RECUSADO_PELA_CELULA if recusado else Registro.NAO_RESPONDEU,
        f"{SLUG_DA_PAGINA}: {resposta}",
    )
    return _lista(
        request,
        site,
        motivo=motivo,
        gesto=gesto,
        erro=resposta,
        status={"ja_existe_ativo": 409, "recusado": 422}.get(motivo, 503),
    )


@require_POST
def experimento_iniciar(request, experimento_id):
    """Põe o rascunho no ar. Só um experimento fica ativo por página."""
    return _conduzir(
        request,
        experimento_id,
        gesto="Iniciar",
        mudar=CatalogoClient.iniciar_experimento,
        estado_pedido="ativo",
        acao=Registro.INICIAR_EXPERIMENTO,
        recado="iniciado",
    )


@require_POST
def experimento_encerrar(request, experimento_id):
    """Encerra de vez. A página volta ao texto que está no ar."""
    return _conduzir(
        request,
        experimento_id,
        gesto="Encerrar",
        mudar=CatalogoClient.encerrar_experimento,
        estado_pedido="encerrado",
        acao=Registro.ENCERRAR_EXPERIMENTO,
        recado="encerrado",
    )
