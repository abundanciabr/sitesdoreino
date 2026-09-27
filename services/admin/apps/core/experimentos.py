"""`/admin/paginas/experimentos/`: criar e pôr no ar um experimento da página.

Um experimento troca UM espaço da página de oferta para uma parte das visitas:
o braço `a` é o texto que está no ar, o braço `b` é o texto novo. Esta tela é
onde o mantenedor vê os experimentos da página, cria um em rascunho e o põe no
ar. Parar é uma das três decisões (promover, reverter, encerrar) da tela
`decisao_do_experimento`, e a lista leva até ela em vez de repetir o gesto.

## Onde o dado mora, e por que não aqui

No `catalogo`, dono da página, pelas operações `listExperiments`,
`createExperiment` e `changeExperimentState` do contrato congelado. É lá que o
sorteio do `funil` lê o experimento ativo, e uma cópia aqui seria o mesmo fato
em dois lugares.

## Três estados, e nenhum deles é pausa

`rascunho` não muda o site. `ativo` põe o braço `b` no ar para a parte das
visitas escolhida. `encerrado` é definitivo. Não existe pausar nem retomar
(decisão da sessão de 26/09/2026, após a segunda opinião sobre o sistema de
experimentos): quem visitou durante a pausa veria o texto `a` com o braço `b`
registrado, e a conta do resultado misturaria os dois.
Parar é encerrar; testar de novo é criar outro, com sorteio novo. A tela diz
isso onde o gesto aparece, para a ausência do botão não parecer defeito.

## O braço `a` é o texto no ar, e quem o grava é o catálogo

A tela mostra o texto publicado do espaço, e o controle `a` viaja sem texto: o
catálogo o preenche com a versão publicada no momento da criação. Aceitar o `a`
do formulário deixaria um campo decidir o controle do experimento, e o controle
só vale se for o que as visitas de fato viam.

## O plano é fixado antes de começar

Métrica principal, taxa base, efeito mínimo detectável e dias planejados são
escritos no rascunho. A tela mostra a amostra por braço que sai deles pela
conta da tela de resultado (`n_por_braco_planejado`), a mesma que o catálogo
grava. Escolher o tamanho do teste depois de ver o placar é o erro que o
horizonte fixo existe para impedir.

## Repetir o Iniciar é seguro

Pedir ao catálogo o estado em que o experimento já está responde 200 sem mudar
nada, então o duplo clique chega ao mesmo recado de sucesso. O 409 é outra
coisa: nada mudou, e a tela diz por quê olhando a página. Havendo outro
experimento ativo, a frase é que já existe um experimento ativo nesta página.

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


def recusas_do_plano(escrito) -> dict[str, str]:
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


def _corpo_do_experimento(escrito) -> dict:
    """`NovoExperimento`, na forma do contrato. Só chamado sem recusa."""
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
        "dias_planejados": int(escrito["dias_planejados"]),
        "variantes": [
            {"variante_id": "a", "peso": PESO_TOTAL - peso_b},
            {"variante_id": "b", "peso": peso_b, "valor": escrito["texto_b"]},
        ],
    }


def texto_no_ar(site, espaco: str) -> "tuple[str, str]":
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
        situacao, texto_a = texto_no_ar(site, escrito["espaco"])
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


# ---------------------------------------------------------------------------
# As duas escritas, chamadas pela tela e pelo `manage.py semear_experimento`
# ---------------------------------------------------------------------------
def criar_rascunho(quem_assina, site, escrito) -> "tuple[str, dict | str]":
    """Grava o rascunho no catálogo e a linha de auditoria, deu certo ou não.

    `escrito` já passou por `recusas_do_plano`. De `quem_assina` só se lê
    `.admin`, que assina a auditoria: a tela passa a requisição, o semeador
    passa o ator dele.
    """
    situacao, resposta = CatalogoClient().criar_experimento(
        site["id"], SLUG_DA_PAGINA, _corpo_do_experimento(escrito)
    )
    detalhe = (
        f"{SLUG_DA_PAGINA}: {escrito['espaco']}, braço b com "
        f"{escrito['parte_b']}% das visitas"
    )
    if situacao == CatalogoClient.OK:
        _auditar(
            quem_assina,
            Registro.CRIAR_EXPERIMENTO,
            str(resposta.get("id") or SLUG_DA_PAGINA),
            Registro.OK,
            detalhe,
        )
        return situacao, resposta

    recusado = situacao in (CatalogoClient.RECUSADO, CatalogoClient.SEM_PAGINA)
    _auditar(
        quem_assina,
        Registro.CRIAR_EXPERIMENTO,
        SLUG_DA_PAGINA,
        Registro.RECUSADO_PELA_CELULA if recusado else Registro.NAO_RESPONDEU,
        f"{detalhe}: {resposta}",
    )
    return situacao, resposta


def iniciar_experimento(quem_assina, site, alvo: str) -> "tuple[str, dict | str]":
    """Pede ao catálogo o estado `ativo` e grava a linha de auditoria.

    `quem_assina` como em `criar_rascunho`.
    """
    situacao, resposta = CatalogoClient().mudar_estado_do_experimento(
        site["id"], SLUG_DA_PAGINA, alvo, {"estado": "ativo"}
    )
    if situacao == CatalogoClient.OK:
        _auditar(
            quem_assina, Registro.INICIAR_EXPERIMENTO, alvo, Registro.OK, SLUG_DA_PAGINA
        )
        return situacao, resposta

    recusado = situacao != CatalogoClient.NAO_RESPONDEU
    _auditar(
        quem_assina,
        Registro.INICIAR_EXPERIMENTO,
        alvo,
        Registro.RECUSADO_PELA_CELULA if recusado else Registro.NAO_RESPONDEU,
        f"{SLUG_DA_PAGINA}: {resposta}",
    )
    return situacao, resposta


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
            situacao, texto_a = texto_no_ar(site, escrito["espaco"])
            if situacao == CatalogoClient.OK:
                escrito["texto_b"] = texto_a
        return _formulario(request, site, escrito)

    escrito = _escrito_do_formulario(request.POST)
    if request.POST.get("gesto") != "salvar":
        erros, _, _ = _plano(escrito)
        return _formulario(request, site, escrito, erros=erros)

    erros = recusas_do_plano(escrito)
    if erros:
        return _formulario(request, site, escrito, erros=erros, status=422)

    situacao, resposta = criar_rascunho(request, site, escrito)
    if situacao == CatalogoClient.OK:
        return HttpResponseRedirect(f"{reverse('experimentos')}?recado=criado")

    recusado = situacao in (CatalogoClient.RECUSADO, CatalogoClient.SEM_PAGINA)
    return _formulario(
        request,
        site,
        escrito,
        motivo="recusado" if recusado else "nao_salvou",
        erro=resposta,
        status=422 if recusado else 503,
    )


# ---------------------------------------------------------------------------
# A lista e o gesto de pôr no ar
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


def _lista(request, site, *, recado="", recusado_id="", erro="", status=200):
    """A lista da página. `recusado_id` é o experimento cujo Iniciar voltou com
    409: a frase sai do estado da página, que é onde está o porquê."""
    situacao, lista = CatalogoClient().experimentos_da_pagina(
        site["id"], SLUG_DA_PAGINA
    )
    contexto = {"admin": request.admin, "recado": recado, "erro": erro}
    if situacao != CatalogoClient.OK:
        contexto.update(sem_leitura=True, erro_da_leitura=lista)
    else:
        experimentos = [_para_a_tela(e) for e in lista]
        ativos = [e["id"] for e in experimentos if e["estado"] == "ativo"]
        contexto.update(
            experimentos=experimentos,
            ha_ativo=bool(ativos),
            outro_ativo=bool(recusado_id) and any(i != recusado_id for i in ativos),
        )
    return render(request, "admin/experimentos.html", contexto, status=status)


@require_GET
def experimentos(request):
    """Os experimentos da página de oferta, cada um com o gesto do estado dele."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, "admin/experimentos.html")
    return _lista(request, site, recado=request.GET.get("recado", ""))


@require_POST
def experimento_iniciar(request, experimento_id):
    """Põe o rascunho no ar. Só um experimento fica ativo por página."""
    site = _site(request)
    if site is None:
        return _sem_catalogo(request, "admin/experimentos.html", status=503)

    alvo = str(experimento_id)
    situacao, resposta = iniciar_experimento(request, site, alvo)
    if situacao == CatalogoClient.OK:
        return HttpResponseRedirect(f"{reverse('experimentos')}?recado=iniciado")

    recusado = situacao != CatalogoClient.NAO_RESPONDEU
    if situacao == CatalogoClient.CONFLITO:
        return _lista(
            request,
            site,
            recado="recusado",
            recusado_id=alvo,
            erro=resposta,
            status=409,
        )
    return _lista(
        request,
        site,
        recado="recusado" if recusado else "nao_iniciou",
        erro=resposta,
        status=422 if recusado else 503,
    )
