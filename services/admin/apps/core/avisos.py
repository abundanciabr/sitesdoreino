"""`/admin/avisos/` — o botão que prova se os avisos na tela do celular estão
funcionando.

Nasceu de um caso real: em 02/09/2026 o botão de ligar os avisos falhava no
navegador do mantenedor, e o servidor estava verde. Não havia como distinguir
"o aviso não foi enviado" de "o aviso foi enviado e não chegou" sem entrar na
VPS, e o agente não entra (Lei 5). Um clique que dispara um aviso de teste, e
diz **para quantos aparelhos ele saiu**, encerra essa classe de dúvida sem
SSH nenhum.

## Onde o dado mora, e por que não aqui

Na célula `notificacoes`, dona da porta `POST /aviso-de-teste`
(`contracts/notificacoes.openapi.yaml`, Rito de Contrato de 03/09/2026). Esta
tela não guarda nada: pede o teste e mostra o que voltou. Guardar um contador
aqui seria o mesmo fato em dois lugares — a lei anti-duplicação do
`CLAUDE.md`.

## Quem recebe é sempre quem pediu

`destinatario_id` é `request.admin["id"]` — o id da PLATAFORMA de quem está
logado nesta área agora. Não existe campo para escolher outra pessoa: um
formulário que aceitasse um id à mão seria um jeito de fazer tocar o celular
de outra pessoa, e nenhum teste vale isso. A garantia real mora do outro lado
(a célula grava `ator_id` igual ao `destinatario_id`); aqui ela é reforçada
por simplesmente não expor o campo.

## O site_id vem do HOST desta própria requisição

Mesmo padrão de `apps/core/menu.py::_carregar` — `CatalogoClient().site_por_host`
sobre `request.get_host()`. Não há seletor de site: quem abre `/admin/avisos/`
num domínio testa os avisos DAQUELE domínio, sem escolher nada numa lista.

## Fail-OPEN na leitura da tela, fail-CLOSED no clique

A tela abre sempre — não há nada para ela "não conseguir ler", é só um botão.
O clique, se a `notificacoes` não responder, diz isso claramente (nunca
finge que enviou); é a mesma disciplina de `CaixaClient`/`AlunosClient` na
escrita: `None` seria mentira perigosa quando a pessoa clicou esperando saber
alguma coisa.
"""

from __future__ import annotations

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from .clients import CatalogoClient, NotificacoesClient
from .views import _auditar


def _site_desta_requisicao(request) -> "dict | None":
    return CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())


@require_GET
def avisos(request):
    """A tela: um botão, e o resultado do último clique (se houve um)."""
    return render(
        request,
        "admin/avisos.html",
        {
            "admin": request.admin,
            "resultado": request.GET.get("resultado", ""),
            "aparelhos": request.GET.get("aparelhos", ""),
        },
    )


@require_POST
def avisos_testar(request):
    """O gesto: manda o aviso de teste para o aparelho de quem clicou.

    Padrão POST-redirect-GET, como toda escrita desta área: sem ele, um F5
    depois de testar repetiria o gesto — aqui repetir é inofensivo (a porta é
    idempotente na leitura do estado), mas o padrão fica pela mesma razão de
    sempre: o dia em que um gesto não for idempotente é tarde demais para
    lembrar dele.
    """
    site = _site_desta_requisicao(request)
    if site is None:
        _auditar(
            request,
            Registro.TESTAR_AVISO,
            request.admin.get("id") or "",
            Registro.NAO_RESPONDEU,
            "não consegui saber qual site é este (catálogo fora do ar)",
        )
        return HttpResponseRedirect(f"{reverse('avisos')}?resultado=sem_site")

    desfecho, aparelhos = NotificacoesClient().enviar_aviso_de_teste(
        site_id=site["id"], destinatario_id=request.admin.get("id") or ""
    )
    if desfecho == NotificacoesClient.OK:
        _auditar(
            request,
            Registro.TESTAR_AVISO,
            request.admin.get("id") or "",
            Registro.OK,
            f"{aparelhos} aparelho(s)",
        )
        return HttpResponseRedirect(
            f"{reverse('avisos')}?resultado=enviado&aparelhos={aparelhos}"
        )

    _auditar(
        request,
        Registro.TESTAR_AVISO,
        request.admin.get("id") or "",
        Registro.NAO_RESPONDEU,
        "a notificacoes não respondeu",
    )
    return HttpResponseRedirect(f"{reverse('avisos')}?resultado=nao_respondeu")
