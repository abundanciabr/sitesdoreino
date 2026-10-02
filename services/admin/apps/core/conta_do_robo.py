"""A CONTA DO ROBÔ: o agente que trabalha na máquina do mantenedor entra nesta
área sem o login dele, e sem ninguém ter de renovar nada (01/10/2026).

## Como ele entra

Cabeçalho `Authorization: Robo <credencial>` em cada pedido. Nada de cookie:
uma credencial que o navegador não manda sozinho não precisa de CSRF, e por
isso a porta desliga a conferência de CSRF SÓ para o pedido do robô já
reconhecido.

## Onde mora a credencial

Em lugar nenhum. O servidor guarda só o `sha256` dela, numa linha da auditoria
(`emitir_credencial_do_robo`), que é append-only por gatilho no banco. A
credencial que vale é a da ÚLTIMA linha de emissão, desde que nenhuma
`revogar_credencial_do_robo` tenha vindo depois. Por isso:

- emitir de novo invalida a anterior na hora, sem reiniciar nada;
- revogar é acrescentar uma linha, e a revogação fica registrada;
- ninguém troca a credencial em silêncio: toda troca é uma linha nova.

Emitir e revogar: `python manage.py conta_do_robo emitir|revogar|conferir`
(ver o comando). O valor sai UMA vez, no stdout do `emitir`, e o caminho dele é
o cano do `ssh` direto para o `ci/cofre.py guardar` na máquina do mantenedor.

## O que ele pode, e o que ele não pode

Pode tudo que tem volta: ler qualquer tela, criar e editar rascunho, arquivar.
Tirar item do menu e preparar quem entra ou sai da administração também são
rascunho, então ele pode. Não pode (403) o gesto sem volta: apagar dado, gastar
dinheiro real (o analista do fechamento chama a API paga), expor segredo (a
senha nova sai na tela) e mudar de fato quem administra ou quem entra (o
`escola_admin_publicar` recusa o robô por conta própria).

A conferência é pelo NOME da rota, por palavra: rota futura que nascer com
"apagar", "senha", "link"... no nome já nasce fechada para o robô.

Credencial errada ou revogada recebe o mesmo 404 de um estranho.
"""

from __future__ import annotations

import hashlib
import hmac
import logging

from django.db import DatabaseError
from django.http import HttpResponseForbidden
from django.urls import Resolver404, resolve

from apps.auditoria.models import Registro

logger = logging.getLogger("admin.porta")

ESQUEMA = "Robo "

#: O que a linha de emissão guarda no `detalhe`: a impressão, nunca o valor.
PREFIXO_DA_IMPRESSAO = "sha256="

#: O `alvo` das linhas de emissão e de revogação.
ALVO = "conta-do-robo"

#: Quem o robô é para as telas e para a auditoria. `.invalid` é domínio
#: reservado: nenhuma caixa de e-mail real.
ROBO = {
    "id": "conta-do-robo",
    "nome": "Robô (agente da máquina do mantenedor)",
    "email": "robo@conta-do-robo.invalid",
    "equipe_apenas": False,
    "robo": True,
}

#: Palavras que, no nome da rota, fazem dela um gesto sem volta para o robô.
PALAVRAS_SEM_VOLTA = (
    "apagar",  # apagar dado
    "estorn",  # devolver dinheiro
    "reembols",
    "senha",  # a senha nova sai em texto na tela
    "associar",  # mudar quem entra no painel da equipe
    "link",  # convite que dá entrada a alguém
    "segredo",
    "chave",
    "token",
)

def impressao(credencial: str) -> str:
    return hashlib.sha256(credencial.encode("utf-8")).hexdigest()


def apresentou(request) -> bool:
    """O pedido diz ser do robô? (Não diz se é.)"""
    return request.META.get("HTTP_AUTHORIZATION", "").startswith(ESQUEMA)


def impressao_vigente() -> str | None:
    """A impressão da credencial que vale agora, ou `None`. Banco fora ⇒ `None`."""
    try:
        ultima = (
            Registro.objects.filter(
                alvo=ALVO,
                acao__in=(
                    Registro.EMITIR_CREDENCIAL_DO_ROBO,
                    Registro.REVOGAR_CREDENCIAL_DO_ROBO,
                ),
            )
            .order_by("-id")
            .values_list("acao", "detalhe")
            .first()
        )
    except DatabaseError:
        logger.error("porta: não deu para ler a credencial do robô — ele não entra")
        return None
    if not ultima or ultima[0] != Registro.EMITIR_CREDENCIAL_DO_ROBO:
        return None
    detalhe = ultima[1] or ""
    if not detalhe.startswith(PREFIXO_DA_IMPRESSAO):
        return None
    return detalhe[len(PREFIXO_DA_IMPRESSAO) :]


def reconhecer(request) -> dict | None:
    """O crachá do robô, se a credencial do cabeçalho é a vigente."""
    credencial = request.META.get("HTTP_AUTHORIZATION", "")[len(ESQUEMA) :].strip()
    vigente = impressao_vigente()
    if not credencial or not vigente:
        return None
    if not hmac.compare_digest(impressao(credencial), vigente):
        return None
    return dict(ROBO)


def gesto_sem_volta(request) -> bool:
    try:
        nome = resolve(request.path_info).url_name or ""
    except Resolver404:
        return False
    if any(palavra in nome for palavra in PALAVRAS_SEM_VOLTA):
        return True
    # Salvar o fechamento não tem custo; somente o botão do analista chama IA paga.
    return (
        nome == "fechamento"
        and request.method not in ("GET", "HEAD")
        and request.POST.get("acao") == "analista"
    )


def recusa():
    return HttpResponseForbidden(
        "A conta do robô não faz gesto sem volta (apagar, gastar dinheiro, "
        "expor segredo, mudar quem administra). Peça ao mantenedor.",
        content_type="text/plain; charset=utf-8",
    )
