"""As telas da célula `gamificacao`.

A primeira delas é a BASE, em `/conquistas`. As outras que o
`PLANO-CELULA-GAMIFICACAO.md` §5 prevê (o Passaporte dos Marcos, a coleção de
medalhas, a loja de Cristais, o Meu Estúdio) são degraus próprios da escada.

A REGRA DE TELA QUE A LEI ESCREVE, e ela manda no visual daqui para a frente
---------------------------------------------------------------------------
*"XP nunca maior que a imagem da obra"* (`PLANO` §5). Esta célula existe para
sustentar quem cria, não para virar o placar de si mesma: o número informa, o
trabalho é a estrela. Um contador gigante piscando na abertura seria a
gamificação se promovendo a assunto principal, que é o critério de morte nº 3 da
lei acontecendo devagar.

ESTA CÉLULA NÃO ASSINA SESSÃO, E NENHUMA VIEW DAQUI PODE ESQUECER ISSO
-----------------------------------------------------------------------
Quem diz quem é a pessoa é a `identidade`, por `apps/core/sessao.py::quem_e`.
Não há `SessionMiddleware`, não há `request.session`, e a tentação de guardar
"já viu a comemoração?" ali dentro é a que desloga a plataforma inteira sem erro
em lugar nenhum ([INV-P12]; `armadilhas/143`). O estado dessas coisas mora em
`PerfilJogador.celebracoes_pendentes`, no banco.
"""

import mimetypes
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .perfil import escada_de, perfil_de
from .sessao import quem_e, site_atual


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/conquistas/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def base(request):
    """A Base: onde o aluno vê em que degrau está.

    **Visitante não leva erro.** Ele vê a mesma página, com um convite para
    entrar no lugar dos números. Um 403 aqui seria a escola dizendo "isto não é
    para você" a quem ainda vai se matricular; um 500 seria pior, porque a
    página existiria e pareceria quebrada.

    **Sem `SITE_ID` no env, também não quebra.** `site_atual()` devolve `None`,
    grita no log, e esta tela trata como visitante. É a mesma falha ABERTA que o
    contrato exige da porta de máquina, pela mesma razão: página sem selo, nunca
    página quebrada. E é por ser uma falha silenciosa que
    `infra/provisionar-gamificacao.sh` se recusa a terminar sem esse campo.
    """
    pessoa_id = quem_e(request)
    site = site_atual()
    # Os dois endereços de fora saem do `settings`, nunca do template: eles são
    # de outras células e `{% url %}` não os conhece.
    de_fora = {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }

    if not pessoa_id or not site:
        return render(request, "gamificacao/base.html", {"entrou": False, **de_fora})

    perfil = perfil_de(pessoa_id, site)
    return render(
        request,
        "gamificacao/base.html",
        {"entrou": True, "escada": escada_de(perfil), **de_fora},
    )


@require_GET
def servir_estatico(request, caminho: str):
    """O CSS das conquistas. Rota de MÁQUINA, como o `/healthz`.

    Sem ela o estilo é 404 em produção e **só lá** (`armadilhas/083` e `/102`):
    com `DEBUG=0` o Django não serve estático, e não há nginx nem CDN atrás do
    Traefik. Em dev funciona, e é justamente por isso que passa despercebido.

    O nome da rota é `estatico`, e não `static`, de propósito: os templates a
    chamam por `{% url 'estatico' … %}`, e **é `{% url %}` e não `{% static %}`
    porque só o primeiro carrega o prefixo público** — `/static/gamificacao.css`
    em `meshcraft.top` é endereço do `funil`, não desta célula.

    Copiado de `services/forum/apps/core/views.py`, não importado: Lei 3, célula
    não importa código de célula.
    """
    raiz = (Path(settings.BASE_DIR) / "static").resolve()
    alvo = (raiz / caminho).resolve()
    # Trava de travessia: o caminho pedido tem de ficar DENTRO de `static/`.
    if not str(alvo).startswith(str(raiz)) or not alvo.is_file():
        raise Http404("arquivo não encontrado")
    tipo, _ = mimetypes.guess_type(str(alvo))
    return FileResponse(
        alvo.open("rb"), content_type=tipo or "application/octet-stream"
    )
