"""`/admin/placar/experimentos/<id>/decisao/`: o fim de um experimento da página.

Três gestos, e só três, porque são as três decisões que o catálogo guarda no
encerramento (desenho comum do sistema de experimentos, 26/09/2026):

- **Promover** põe no ar o texto da variante vencedora, no espaço da página
  onde o experimento rodou, e encerra com a decisão `promover`;
- **Reverter** encerra com `reverter` e não publica nada: a página no ar já é
  o controle, e o sorteio para;
- **Encerrar** encerra com `encerrar`, para o experimento que não deu para
  julgar (ou que ainda estava em rascunho).

## Promover publica pela publicação que já existe

A variante vira texto da página pelo mesmo caminho da tela `/admin/paginas/`:
rascunho gravado (`putPageDraft`) e rascunho publicado (`publishPage`), que
cria a versão seguinte da página no catálogo. Um atalho de publicação só para
experimento seria o segundo lugar onde a página muda, e o histórico de versões
que o funil mede deixaria de contar a verdade inteira.

O rascunho novo nasce da versão PUBLICADA, com um espaço trocado. Se houver
texto salvo e ainda não publicado, promover publicaria esse texto junto, sem
ele ter pedido. Nesse caso a tela recusa e diz o que fazer: publicar ou desfazer
o rascunho na tela da página, e voltar.

## Promover só com veredito, ou com a palavra dele

O botão aparece habilitado quando o resultado (frente F9a) diz `candidato à
promoção`. Com qualquer outro veredito, ou sem veredito, promover exige marcar
a frase que diz que o resultado não é conclusivo. A conferência é repetida
aqui no servidor: o formulário não é prova de nada.

## Duplo clique não duplica nada

Um experimento decide uma vez. O gesto roda sob uma trava por experimento
(`pg_advisory_xact_lock`, no Postgres da célula): o segundo clique espera o
primeiro terminar e então encontra o experimento encerrado com a mesma decisão,
e responde que nada foi repetido. Sem a trava, os dois cliques leriam a mesma
página antiga e publicariam duas versões iguais.

## A ordem das duas portas

Promover atravessa duas escritas no catálogo: publicar e encerrar. Publicar
vem primeiro, pela pergunta da `LICOES.md` desta célula (qual metade, sobrando
sozinha, faz menos estrago?). Página publicada com experimento ainda aberto
continua sorteando e se completa no clique seguinte, que encontra o texto já no
ar e só encerra. Experimento encerrado como `promover` com a página antiga no ar
seria um registro dizendo o contrário do que o visitante vê.
"""

from __future__ import annotations

import hashlib
from contextlib import contextmanager
from dataclasses import dataclass

from django.db import connection, transaction
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient
from .views import _auditar

#: As três decisões, com o nome que aparece na tela.
DECISOES = {
    "promover": "Promover",
    "reverter": "Reverter",
    "encerrar": "Encerrar",
}

#: A variante que é o texto que já estava no ar quando o experimento nasceu.
CONTROLE = "a"

#: O veredito da F9a que habilita Promover sem confirmação.
CANDIDATO = "candidato à promoção"

#: Os estados em que o experimento ainda está medindo.
MEDINDO = ("ativo", "pausado")


@dataclass(frozen=True)
class Desfecho:
    """O que o gesto fez, na forma que a tela precisa para responder."""

    estado: str  # feito | repetido | recusado | nao_respondeu | metade
    frase: str = ""


def _veredito(site_id: str, experimento: dict) -> str | None:
    """O veredito do resultado (frente F9a), ou `None` se não deu para calcular.

    Sem a tela de resultado no ar, não há veredito: a tela diz "ainda sem
    cálculo" e Promover passa a exigir a confirmação, que é o lado seguro.
    """
    try:
        from .resultado_do_experimento import veredito_do_experimento
    except ImportError:
        return None
    return veredito_do_experimento(site_id, experimento)


@contextmanager
def _um_de_cada_vez(experimento_id: str):
    """A trava por experimento, solta no fim da transação.

    Só existe no Postgres, que é o banco da célula em produção e no CI; o
    SQLite local não tem trava consultiva.
    """
    resumo = hashlib.sha256(f"decisao-do-experimento:{experimento_id}".encode())
    chave = int.from_bytes(resumo.digest()[:8], "big", signed=True)
    with transaction.atomic():
        if connection.vendor == "postgresql":
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(%s)", [chave])
        yield


def _secoes(lista) -> tuple:
    """As seções numa forma comparável: ordem, nome e os textos de cada uma."""
    return tuple(
        sorted(
            (
                s.get("ordem"),
                s.get("nome"),
                tuple(sorted((c, v) for c, v in (s.get("slots") or {}).items())),
            )
            for s in lista or []
        )
    )


def _com_o_texto(secoes: list, secao: str, slot: str, valor: str) -> list | None:
    """As seções publicadas com um espaço trocado, ou `None` se a seção sumiu."""
    novas = [
        {
            "nome": s.get("nome"),
            "ordem": s.get("ordem"),
            "slots": dict(s.get("slots") or {}),
        }
        for s in secoes
    ]
    for s in novas:
        if s["nome"] == secao:
            s["slots"][slot] = valor
            return novas
    return None


def _no_ar(secoes: list, secao: str, slot: str) -> str | None:
    for s in secoes:
        if s.get("nome") == secao:
            return (s.get("slots") or {}).get(slot)
    return None


def _falha(situacao: str, frase: str) -> Desfecho:
    """Recusa do catálogo e silêncio do catálogo pedem gestos diferentes dele."""
    if situacao == CatalogoClient.NAO_RESPONDEU:
        return Desfecho("nao_respondeu", frase)
    return Desfecho("recusado", frase)


def _publicar_a_variante(request, site_id: str, experimento: dict, variante: dict):
    """Põe o texto da variante no ar. Devolve a versão no ar, ou um `Desfecho`."""
    catalogo = CatalogoClient()
    slug, secao, slot = experimento["pagina"], experimento["secao"], experimento["slot"]
    valor = variante["valor"]

    situacao, publicada = catalogo.pagina_publicada(site_id, slug)
    if situacao != CatalogoClient.OK:
        return _falha(
            situacao,
            f"Não consegui ler a página que está no ar ({publicada}). Nada foi "
            "publicado nem encerrado. Tente de novo em alguns minutos.",
        )
    no_ar = publicada.get("secoes") or []
    if _no_ar(no_ar, secao, slot) == valor:
        return publicada.get("version")

    novas = _com_o_texto(no_ar, secao, slot, valor)
    if novas is None:
        return Desfecho(
            "recusado",
            f"A seção {secao} não existe mais na página publicada, então não há "
            "onde pôr o texto da variante. Nada foi publicado. Use Encerrar.",
        )

    situacao, rascunho = catalogo.rascunho_da_pagina(site_id, slug)
    if situacao == CatalogoClient.OK:
        # O rascunho igual ao publicado, ou igual ao que este gesto já gravou
        # num clique que parou no meio, é seguro. Qualquer outro é texto dele.
        if _secoes(rascunho.get("secoes")) not in (_secoes(no_ar), _secoes(novas)):
            return Desfecho(
                "recusado",
                "Há texto salvo na página de venda que ainda não foi ao ar, e "
                "promover publicaria esse texto junto. Abra a página de venda, "
                "publique esse texto ou volte os campos ao que está no ar, e "
                "aperte Promover de novo. Nada foi publicado nem encerrado.",
            )
    elif situacao != CatalogoClient.SEM_RASCUNHO:
        return _falha(
            situacao,
            f"Não consegui ler o rascunho da página ({rascunho}). Nada foi "
            "publicado nem encerrado. Tente de novo em alguns minutos.",
        )

    situacao, resposta = catalogo.gravar_rascunho_da_pagina(
        site_id, slug, novas, tipo=publicada.get("tipo") or "oferta"
    )
    if situacao == CatalogoClient.OK:
        situacao, resposta = catalogo.publicar_pagina(site_id, slug)
    if situacao != CatalogoClient.OK:
        _auditar(
            request,
            Registro.PUBLICAR_PAGINA,
            slug,
            (
                Registro.NAO_RESPONDEU
                if situacao == CatalogoClient.NAO_RESPONDEU
                else Registro.RECUSADO_PELA_CELULA
            ),
            f"{slug}: promover a variante {variante['variante_id']} do "
            f"experimento {experimento['id']}: {resposta}",
        )
        return _falha(
            situacao,
            f"O catálogo não publicou a variante ({resposta}). O experimento "
            "continua aberto. Apertar Promover de novo é seguro.",
        )
    versao = resposta.get("version")
    _auditar(
        request,
        Registro.PUBLICAR_PAGINA,
        slug,
        Registro.OK,
        f"{slug}: publicou a versão {versao} promovendo a variante "
        f"{variante['variante_id']} do experimento {experimento['id']}",
    )
    return versao


def _ja_encerrado(experimento: dict, decisao: str, variante_id: str | None) -> Desfecho:
    gravada = experimento.get("decisao")
    if gravada == decisao and (
        decisao != "promover" or experimento.get("variante_vencedora") == variante_id
    ):
        return Desfecho(
            "repetido",
            "Este experimento já estava encerrado com esta decisão. Nada foi repetido.",
        )
    nome = DECISOES.get(gravada, gravada or "sem decisão")
    return Desfecho(
        "recusado",
        f"Este experimento já foi encerrado com a decisão {nome}. A decisão de "
        "um experimento não muda depois de gravada.",
    )


def decidir(
    request,
    site_id: str,
    experimento_id: str,
    decisao: str,
    variante_id: str | None,
    confirmou_inconclusivo: bool,
) -> Desfecho:
    """O gesto inteiro, sob a trava do experimento."""
    catalogo = CatalogoClient()
    with _um_de_cada_vez(experimento_id):
        situacao, experimento = catalogo.experimento(site_id, experimento_id)
        if situacao != CatalogoClient.OK:
            return _falha(
                situacao,
                f"Não consegui ler o experimento ({experimento}). Nada foi feito.",
            )
        if experimento.get("estado") == "encerrado":
            return _ja_encerrado(experimento, decisao, variante_id)

        versao = None
        if decisao == "promover":
            if experimento.get("estado") not in MEDINDO:
                return Desfecho(
                    "recusado",
                    "Um experimento que nunca começou não tem vencedor. Use Encerrar.",
                )
            variante = next(
                (
                    v
                    for v in experimento.get("variantes") or []
                    if v.get("variante_id") == variante_id
                ),
                None,
            )
            if not all(experimento.get(k) for k in ("pagina", "secao", "slot")):
                return Desfecho(
                    "recusado",
                    "O catálogo devolveu o experimento sem dizer em que espaço da "
                    "página ele roda, então não há onde pôr o texto. Nada foi "
                    "publicado. Use Encerrar.",
                )
            if (
                variante is None
                or variante_id == CONTROLE
                or not isinstance(variante.get("valor"), str)
            ):
                return Desfecho(
                    "recusado",
                    "Escolha a variante que vai ao ar. A variante a é o texto que "
                    "já está no ar: para mantê-lo, use Reverter.",
                )
            veredito = _veredito(site_id, experimento)
            if veredito != CANDIDATO and not confirmou_inconclusivo:
                return Desfecho(
                    "recusado",
                    "O resultado ainda não é conclusivo. Para promover assim "
                    "mesmo, marque a frase de confirmação e aperte Promover.",
                )
            publicado = _publicar_a_variante(request, site_id, experimento, variante)
            if isinstance(publicado, Desfecho):
                return publicado
            versao = publicado

        situacao, resposta = catalogo.encerrar_experimento(
            site_id,
            experimento_id,
            decisao,
            variante_id if decisao == "promover" else None,
        )
        if situacao == CatalogoClient.JA_ENCERRADO:
            situacao, experimento = catalogo.experimento(site_id, experimento_id)
            if situacao == CatalogoClient.OK:
                return _ja_encerrado(experimento, decisao, variante_id)
        _auditar(
            request,
            Registro.DECIDIR_EXPERIMENTO,
            experimento_id,
            (
                Registro.OK
                if situacao == CatalogoClient.OK
                else (
                    Registro.NAO_RESPONDEU
                    if situacao == CatalogoClient.NAO_RESPONDEU
                    else Registro.RECUSADO_PELA_CELULA
                )
            ),
            f"{decisao}"
            + (f" {variante_id}" if decisao == "promover" else "")
            + (" com resultado não conclusivo" if confirmou_inconclusivo else "")
            + ("" if situacao == CatalogoClient.OK else f": {resposta}"),
        )
        if situacao == CatalogoClient.OK:
            return Desfecho("feito")
        if decisao == "promover":
            return Desfecho(
                "metade",
                f"A variante {variante_id} já está no ar (versão {versao} da "
                f"página), mas o experimento não foi encerrado ({resposta}). "
                "Apertar Promover de novo é seguro: a página não será "
                "publicada outra vez, só o encerramento será repetido.",
            )
        return _falha(
            situacao,
            f"O catálogo não encerrou o experimento ({resposta}). Nada mudou. "
            "Tente de novo em alguns minutos.",
        )


# ---------------------------------------------------------------------------
# A tela
# ---------------------------------------------------------------------------
def _site(request) -> dict | None:
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


def _tela(
    request, experimento_id: str, *, desfecho: Desfecho | None = None, status=200
):
    site = _site(request)
    contexto = {
        "admin": request.admin,
        "experimento_id": experimento_id,
        "recado": request.GET.get("recado", ""),
        "desfecho": desfecho,
    }
    if site is None:
        return render(
            request,
            "admin/decisao_do_experimento.html",
            {**contexto, "sem_catalogo": True},
            status=status,
        )
    situacao, experimento = CatalogoClient().experimento(site["id"], experimento_id)
    if situacao != CatalogoClient.OK:
        desconhecido = situacao == CatalogoClient.SEM_EXPERIMENTO
        return render(
            request,
            "admin/decisao_do_experimento.html",
            {**contexto, "desconhecido": desconhecido, "sem_leitura": not desconhecido},
            status=404 if desconhecido and status == 200 else status,
        )
    encerrado = experimento.get("estado") == "encerrado"
    medindo = experimento.get("estado") in MEDINDO
    return render(
        request,
        "admin/decisao_do_experimento.html",
        {
            **contexto,
            "experimento": experimento,
            "encerrado": encerrado,
            "medindo": medindo,
            "decisao_gravada": DECISOES.get(experimento.get("decisao"), ""),
            "veredito": _veredito(site["id"], experimento) if medindo else None,
            "candidato": CANDIDATO,
            "promoviveis": [
                v
                for v in experimento.get("variantes") or []
                if v.get("variante_id") != CONTROLE
            ],
        },
        status=status,
    )


@require_GET
def decisao_do_experimento(request, experimento_id: str):
    """A tela: o experimento, o veredito e os três gestos."""
    return _tela(request, experimento_id)


@require_POST
def decidir_experimento(request, experimento_id: str):
    """Um dos três gestos. Sucesso volta para a tela (POST, redirect, GET)."""
    decisao = request.POST.get("decisao", "")
    if decisao not in DECISOES:
        return _tela(
            request,
            experimento_id,
            desfecho=Desfecho(
                "recusado", "A tela mandou uma decisão que não existe. Recarregue."
            ),
            status=422,
        )
    site = _site(request)
    if site is None:
        return _tela(request, experimento_id, status=503)
    desfecho = decidir(
        request,
        site["id"],
        experimento_id,
        decisao,
        request.POST.get("variante") or None,
        request.POST.get("confirmo_inconclusivo") == "sim",
    )
    if desfecho.estado in ("feito", "repetido"):
        recado = decisao if desfecho.estado == "feito" else "repetido"
        return HttpResponseRedirect(
            reverse("decisao_do_experimento", args=[experimento_id])
            + f"?recado={recado}"
        )
    return _tela(
        request,
        experimento_id,
        desfecho=desfecho,
        status=422 if desfecho.estado == "recusado" else 503,
    )
