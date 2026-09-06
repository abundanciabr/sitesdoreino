"""As views da célula `pages` (a casa das Páginas do aluno).

Três: a sonda, a Prancheta (o roteiro das cinco etapas, degrau 07) e a marcação
de um item da lista de conferência. O que falta continua vindo pela escada do
`PLANO-PORTFOLIO-DO-ALUNO.md` §5: as peças coladas por link (08), o semáforo
(10), o pedido de conferência e a fila da equipe (11 e 12) e a vitrine em
`/estudio/<apelido>` (13).

**Nenhuma view daqui decide quem entra.** Quem decide é a porta
(`apps/core/porta.py`), fail-CLOSED, e ela vem por último no `MIDDLEWARE`:
quando uma view desta célula roda, a pessoa já foi reconhecida e a matrícula
ativa já foi conferida. Espalhar essa decisão por tela faria o critério AC-05
depender de uma lembrança por arquivo, que é a forma como esse tipo de porta
morre.

**Nenhuma view daqui escreve um `filter()` por aluno.** O isolamento do critério
AC-07 tem UMA porta, o `do_aluno` dos gerenciadores de
`apps/portfolio/models.py`, provado por mutação em
`tests/test_isolamento_por_aluno.py`. Um segundo `filter` aqui seria a mesma
regra em duas expressões, e no dia em que discordassem o vazamento sairia pela
que ninguém está medindo.
"""

from __future__ import annotations

import logging
import os

from django.conf import settings
from django.db import transaction
from django.http import Http404, JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.portfolio.models import (
    EtapaDoRoteiro,
    ItemDeConferencia,
    ItemDoRoteiro,
    Portfolio,
)
from apps.portfolio.roteiro_da_escola import AVISO_DE_RASCUNHO

logger = logging.getLogger("pages.views")


def de_fora() -> dict:
    """Os dois endereços que NÃO são desta célula, e que `{% url %}` ignora.

    A entrada mora na `identidade` e a capa mora no `funil`. Com padrão, de
    propósito: `infra/provisionar-pages.sh` não escreve estas chaves, e a trava
    de deriva dele reprova env com variável que ele não sabe gerar. Molde:
    `services/cursos/apps/core/views.py`.
    """
    return {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }


def site_atual() -> str | None:
    """De que escola é esta instalação, ou `None` quando o env não diz.

    **Lida no ponto de uso, nunca no import** (`armadilhas/097`): variável lida
    no topo de um módulo transforma env ausente em HTTP 500 em toda página, com
    o deploy verde.

    **`None` é o estado real da VPS hoje**, e não uma hipótese:
    `infra/provisionar-pages.sh` não escreve `SITE_ID`, e não escrever
    configuração que a célula ainda não lia foi decisão consciente da gênese
    (`armadilhas/224`, dito por extenso em `infra/env/pages.env.exemplo`). O
    degrau 07 é a primeira tela desta casa que precisa da variável, e a linha
    que a escreve mora em `infra/`, caminho CODEOWNERS que este PR não tem
    mandato para tocar. A dívida está no balcão.

    Enquanto ela faltar, a Prancheta MOSTRA o roteiro (a lista orienta, nunca
    tranca, plano §7) e RECUSA a marcação, dizendo o que aconteceu. Gravar com
    o site em branco seria pior do que recusar: no dia em que a segunda escola
    chegasse, os alunos das duas estariam do mesmo lado da fronteira e nenhuma
    tela quebraria para avisar.
    """
    valor = (os.environ.get("SITE_ID") or "").strip()
    if not valor:
        logger.error(
            "SITE_ID ausente no env: a Prancheta mostra o roteiro mas não grava "
            "marcação, porque não sabe de que escola esta instalação é"
        )
        return None
    return valor


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/pages/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    A porta do degrau 06 isenta esta rota comparando `request.path_info`, e
    **nunca** `request.path`, que pela borda pública contém o prefixo
    (`apps/core/porta.py::CAMINHOS_ISENTOS`). Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def prancheta(request):
    """O roteiro: as cinco etapas, as listas de conferência e o que já foi marcado.

    **Ler não escreve.** O portfólio do aluno nasce na primeira marcação, e não
    aqui: um `GET` que criasse a linha encheria a tabela com quem só passou pela
    porta, e faria a página depender de uma escrita para responder.

    **As duas consultas são independentes de propósito.** O roteiro é da ESCOLA
    e é o mesmo para todo mundo; as marcações são DO ALUNO e saem pela porta do
    isolamento. Juntá-las numa consulta só amarraria o texto da escola ao dono
    da linha, que é a segunda verdade que o degrau 02 recusou.
    """
    site_id = site_atual()

    marcadas: set[str] = set()
    if site_id:
        marcadas = set(
            ItemDeConferencia.objects.do_aluno(
                site_id=site_id, aluno_id=request.aluno["id"]
            )
            .filter(marcado=True)
            .values_list("chave", flat=True)
        )

    etapas = [
        {
            "numero": etapa.numero,
            "titulo": etapa.titulo,
            "resumo": etapa.resumo,
            "itens": [
                {
                    "chave": item.chave,
                    "texto": item.texto,
                    "marcado": item.chave in marcadas,
                }
                for item in etapa.itens.all()
            ],
        }
        for etapa in EtapaDoRoteiro.objects.prefetch_related("itens")
    ]

    return render(
        request,
        "pages/prancheta.html",
        {
            "aluno": request.aluno,
            "etapas": etapas,
            "pode_marcar": site_id is not None,
            "aviso_de_rascunho": AVISO_DE_RASCUNHO,
            **de_fora(),
        },
    )


@require_POST
def marcar(request):
    """O aluno marca (ou desmarca) um item da lista. A marca vai para o BANCO.

    **Formulário normal, sem script:** a regra desta casa é que nenhum caminho
    exista só com JavaScript, e a resposta é o redirecionamento de volta para a
    Prancheta. O POST-redirect-GET também impede que recarregar a página repita
    a escrita.

    **O estado desejado vem no formulário, e não se calcula aqui.** Um botão que
    invertesse o valor atual gravaria o contrário do que o aluno viu sempre que
    ele tivesse duas abas abertas, ou que a rede repetisse o pedido.

    **Chave de fora do catálogo é 404.** Sem essa recusa, qualquer POST
    escreveria marcação com a chave que quisesse, e a tela do aluno passaria a
    mostrar itens que a escola nunca escreveu.
    """
    site_id = site_atual()
    if site_id is None:
        # Fail-closed, no mesmo vocabulário que a porta desta casa já usa: 503
        # é *a parte que responde por isto está incompleta*, e é temporário.
        resposta = render(
            request,
            "pages/porta.html",
            {"motivo": "sem-escola", **de_fora()},
            status=503,
        )
        resposta["Retry-After"] = "30"
        resposta["Cache-Control"] = "no-store"
        return resposta

    chave = (request.POST.get("chave") or "").strip()
    item = ItemDoRoteiro.objects.filter(chave=chave).select_related("etapa").first()
    if item is None:
        raise Http404(f"o roteiro da escola não tem o item {chave!r}")

    quer_marcar = request.POST.get("marcar") == "1"

    with transaction.atomic():
        portfolio, _ = Portfolio.objects.get_or_create(
            site_id=site_id, aluno_id=request.aluno["id"]
        )
        # A marcação é procurada pela MESMA porta do critério AC-07: é o
        # `do_aluno` que impede o desmarcar de um aluno de alcançar a linha de
        # outro que tenha a mesma chave.
        marcacao = (
            ItemDeConferencia.objects.do_aluno(
                site_id=site_id, aluno_id=request.aluno["id"]
            )
            .filter(chave=chave)
            .first()
        )
        if marcacao is None:
            marcacao = ItemDeConferencia(portfolio=portfolio, chave=chave)

        # A etapa acompanha o catálogo a cada escrita: se a escola mudar um item
        # de etapa, a marcação antiga se corrige na primeira vez que o aluno
        # tocar nela, em vez de apontar para a etapa de ontem para sempre.
        marcacao.etapa = item.etapa.numero
        marcacao.marcado = quer_marcar
        # A data anda junto com a marca, e o banco recusa uma sem a outra.
        marcacao.marcado_em = timezone.now() if quer_marcar else None
        marcacao.save()

    # `redirect` pelo NOME da rota: é `reverse()` que carrega o prefixo público
    # para dentro do endereço, e caminho cravado em string quebra em produção e
    # só lá (`armadilhas/029` e `/081`).
    return redirect("prancheta")
