"""As views da célula `pages` (a casa das Páginas do aluno).

Duas: a sonda e a tela mínima da Prancheta, a primeira coisa que o aluno
reconhecido vê (degrau 06). O que falta continua vindo pela escada do
`PLANO-PORTFOLIO-DO-ALUNO.md` §5: as cinco etapas com as listas de conferência
(07), as peças coladas por link (08), o semáforo (10), o pedido de conferência
e a fila da equipe (11 e 12) e a vitrine em `/estudio/<apelido>` (13).

**Nenhuma view daqui decide quem entra.** Quem decide é a porta
(`apps/core/porta.py`), fail-CLOSED, e ela vem por último no `MIDDLEWARE`:
quando uma view desta célula roda, a pessoa já foi reconhecida e a matrícula
ativa já foi conferida. Espalhar essa decisão por tela faria o critério AC-05
depender de uma lembrança por arquivo, que é a forma como esse tipo de porta
morre.
"""

from django.conf import settings
from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET


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
    """A tela mínima: a casa diz ao aluno que sabe quem ele é.

    Ela não lê o banco, e isso é escopo, não esquecimento: o portfólio nasce
    quando houver o que guardar nele, que é o degrau 07. O que esta tela prova
    é o reconhecimento, e `request.aluno` só existe porque a porta deixou a
    pessoa passar.
    """
    return render(
        request, "pages/prancheta.html", {"aluno": request.aluno, **de_fora()}
    )
