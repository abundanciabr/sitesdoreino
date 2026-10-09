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
em lugar nenhum. O estado dessas coisas mora em
`PerfilJogador.celebracoes_pendentes`, no banco.
"""

import logging
import mimetypes
from pathlib import Path
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.gamificacao.recursos import disponiveis
from apps.gamificacao.criterios import medalhas_da_pessoa
from .participacao import minha as minha_participacao
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
)
from apps.gamificacao.validacao import (
    ValidacaoRecusada,
    corrigir,
    reconhecimentos_da_escola,
    restaurar,
    revogar,
)

from .equipe import e_da_equipe
from .perfil import escada_de, perfil_de
from .sessao import quem_e, site_atual

logger = logging.getLogger(__name__)

# As 13 faixas ainda são só do admin (ficha do aluno no painel); a página do
# aluno não as mostra enquanto isto for False.
FAIXAS_PARA_O_ALUNO = False


# Os recados que uma tela manda para si mesma depois de um POST. São CÓDIGOS e
# não frases: o texto vive no template, no idioma de quem lê, e uma frase pronta
# viajando na barra de endereço é uma frase que alguém pode trocar por outra
# (`?recado=voce-foi-expulso`) e mandar por link a um aluno.
RECADOS = {
    "revogada": "Retirada. A história ficou guardada.",
    "restaurada": "Devolvida à pessoa. A história ficou guardada.",
    "corrigida": "Referência corrigida. A antiga ficou na história.",
}


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/conquistas/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose.

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
        {
            "entrou": True,
            "escada": escada_de(perfil),
            "faixas": _faixas_para_tela(pessoa_id, site) if FAIXAS_PARA_O_ALUNO else None,
            **de_fora,
        },
    )


def _reais(cents: int) -> str:
    """Centavos em 'R$ 1.234,56' (sem dependência de locale)."""
    inteiro, centavos = divmod(int(cents), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{centavos:02d}"


def _fundo(cores: list[str]) -> str:
    """Uma cor = cheia; duas = metade e metade."""
    if len(cores) == 1:
        return cores[0]
    return f"linear-gradient(135deg, {cores[0]} 50%, {cores[1]} 50%)"


def _faixas_para_tela(pessoa_id: str, site: str) -> dict:
    """A situação das 13 faixas pronta para o template (sem dado de cliente)."""
    from django.utils import timezone

    from apps.gamificacao.faixas import situacao_das_faixas

    s = situacao_das_faixas(pessoa_id, site)

    def data(d):
        return timezone.localtime(d).strftime("%d/%m/%Y") if d else None

    atual = {**s["atual"], "fundo": _fundo(s["atual"]["cores"]),
             "data": data(s["atual"]["alcancada_em"])}
    proxima = None
    if s["proxima"]:
        p = s["proxima"]
        proxima = {**p, "fundo": _fundo(p["cores"]), "barra": None}
        d = p["dinheiro"]
        if d:
            proxima["barra"] = {
                "pct": d["fracao_pct"],
                "total": _reais(d["total_cents"]),
                "meta": _reais(d["meta_cents"]),
                "falta": _reais(d["falta_cents"]),
                "unica": d["meta_cents"] <= 1,
            }
    lista = [
        {**f, "fundo": _fundo(f["cores"]), "data": data(f["alcancada_em"]),
         "atual": f["ordem"] == s["atual"]["ordem"]}
        for f in s["faixas"]
    ]
    return {"atual": atual, "proxima": proxima, "lista": lista,
            "total": _reais(s["total_real_cents"])}


@require_GET
def servir_estatico(request, caminho: str):
    """O CSS das conquistas. Rota de MÁQUINA, como o `/healthz`.

    Sem ela o estilo é 404 em produção e **só lá**:
    com `DEBUG=0` o Django não serve estático, e não há nginx nem CDN atrás do
    Traefik. Em dev funciona, e é justamente por isso que passa despercebido.

    O nome da rota é `estatico`, e não `static`, de propósito: os templates a
    chamam por `{% url 'estatico' … %}`, e **é `{% url %}` e não `{% static %}`
    porque só o primeiro carrega o prefixo público** — `/static/gamificacao.css`
    em `meshcraft.top` é endereço do `funil`, não desta célula.

    Copiado de `services/forum/apps/core/views.py`, não importado: célula
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


# ---------------------------------------------------------------------------
# OS MARCOS REAIS — a tela do aluno
# ---------------------------------------------------------------------------
def _pessoa_e_site(request):
    """Quem está olhando, e em que escola. `(None, None)` para visitante.

    A dupla sempre junta porque as duas telas abaixo precisam das duas coisas, e
    esquecer o `site_atual()` daria a alguém uma fila de OUTRA escola para julgar.
    """
    pessoa_id = quem_e(request)
    site = site_atual()
    if not pessoa_id or not site:
        return None, None
    return pessoa_id, site


def _voltar(nome: str, *, recado: str = "", erro: str = ""):
    """POST-redirect-GET, com o recado por CÓDIGO e o erro por texto.

    O recado é código porque a frase vive no template, no idioma de quem lê —
    uma frase pronta viajando na barra de endereço é uma frase que alguém troca
    por outra e manda por link a um aluno. O erro é texto porque ele vem da
    recusa, que é escrita para ser lida por gente; o template o escapa, como
    escapa qualquer entrada.
    """
    endereco = reverse(nome)
    if recado:
        return HttpResponseRedirect(f"{endereco}?recado={recado}")
    if erro:
        return HttpResponseRedirect(f"{endereco}?erro={quote(erro)}")
    return HttpResponseRedirect(endereco)




@require_GET
def medalhas(request):
    """As medalhas ligadas da escola: como cada uma se ganha, e onde a pessoa está.

    **O critério aparece ANTES de conquistar.** Uma medalha que cai sem que a
    pessoa soubesse que existia não ensina nada; dita antes, ela mostra o
    próximo passo. O texto sai do próprio critério
    (`criterios.criterio_em_portugues`), nunca de uma frase solta.

    **Só a pessoa que olha.** Nenhum número de outras pessoas, nenhuma ordem
    entre alunos: ranking público é proibido pela lei §8, e "quantos já têm"
    é o primeiro passo dele.

    **Visitante não leva erro**, e sem `SITE_ID` também não quebra: a mesma
    postura da Base, dos Marcos e da Forja.
    """
    de_fora = {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }
    pessoa_id, site = _pessoa_e_site(request)
    if not pessoa_id:
        return render(
            request, "gamificacao/medalhas.html", {"entrou": False, **de_fora}
        )

    perfil = perfil_de(pessoa_id, site)
    return render(
        request,
        "gamificacao/medalhas.html",
        {"entrou": True, "linhas": medalhas_da_pessoa(perfil), "participacao_nps": minha_participacao(pessoa_id), **de_fora},
    )




# ---------------------------------------------------------------------------
# A FILA DA EQUIPE — e a porta dela
# ---------------------------------------------------------------------------
def _recusar_quem_nao_e_da_equipe(request):
    """403 com frase, e não tela vazia.

    Uma tela vazia diria "não há nada aqui" a quem deveria ver a fila, e um
    professor com o env mal configurado passaria a tarde achando que a escola não
    tem pedidos. O 403 diz o que é: a área existe, e esta pessoa não está na
    lista.

    Fail-CLOSED: lista vazia recusa todo mundo, inclusive o mantenedor.
    """
    return render(
        request,
        "gamificacao/sem_acesso.html",
        {"pode": False, "url_da_capa": settings.URL_DA_CAPA},
        status=403,
    )






# ---------------------------------------------------------------------------
# A FORJA — o medidor de tentativas por peça, e o selo que sai dele
# ---------------------------------------------------------------------------






# ---------------------------------------------------------------------------
# O QUADRO DE CONTRIBUIÇÕES: a escola pede, o aluno assume e entrega
# ---------------------------------------------------------------------------




def _numero(valor) -> int:
    """Um id vindo do formulário, ou 0, que nenhuma linha tem."""
    try:
        return int(valor)
    except (TypeError, ValueError):
        return 0








# ---------------------------------------------------------------------------
# O RASTRO DOS RECONHECIMENTOS — o bastidor da equipe
# ---------------------------------------------------------------------------
@require_GET
def interno_reconhecimentos(request):
    """Cada conquista concedida, com a regra do dia, a origem e a história inteira.

    É aqui que a equipe retira, devolve ou corrige uma conquista; o motivo é
    opcional e, se vier, fica na história. A porta é a mesma da fila dos marcos, fail-CLOSED por
    `IDS_DA_EQUIPE`, e quem não está na lista leva o mesmo 403 com a razão.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not e_da_equipe(pessoa_id) or not site:
        return _recusar_quem_nao_e_da_equipe(request)

    procurada = (request.GET.get("pessoa") or "").strip()
    return render(
        request,
        "gamificacao/interno_reconhecimentos.html",
        {
            "concessoes": reconhecimentos_da_escola(site, procurada),
            "procurada": procurada,
            "revogada": Concessao.Estado.REVOGADA,
            "eu": pessoa_id,
            "recado": RECADOS.get(request.GET.get("recado", "")),
            "erro": request.GET.get("erro", ""),
            "url_da_capa": settings.URL_DA_CAPA,
        },
    )


@require_POST
def decidir_reconhecimento(request):
    """Retirar, devolver ou corrigir uma conquista; o motivo escrito é opcional.

    Quem decide é quem a sessão diz que é, conferido na lista da equipe; a
    concessão é procurada DENTRO da escola desta instalação, e a de outra escola
    simplesmente não existe para o gesto.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not e_da_equipe(pessoa_id) or not site:
        return _recusar_quem_nao_e_da_equipe(request)

    concessao = disponiveis(Concessao.objects.filter(
        pk=_numero(request.POST.get("concessao")), site_id=site
    ), "conquista__").first()
    if concessao is None:
        return _voltar(
            "interno-reconhecimentos",
            erro="Essa conquista não existe nesta escola.",
        )

    gesto = request.POST.get("gesto", "")
    motivo = request.POST.get("motivo", "")
    try:
        if gesto == "revogar":
            revogar(concessao=concessao, quem_id=pessoa_id, motivo=motivo)
            return _voltar("interno-reconhecimentos", recado="revogada")
        if gesto == "restaurar":
            restaurar(concessao=concessao, quem_id=pessoa_id, motivo=motivo)
            return _voltar("interno-reconhecimentos", recado="restaurada")
        if gesto == "corrigir":
            corrigir(
                concessao=concessao,
                quem_id=pessoa_id,
                origem_nova=request.POST.get("origem", ""),
                motivo=motivo,
            )
            return _voltar("interno-reconhecimentos", recado="corrigida")
    except ValidacaoRecusada as recusa:
        return _voltar("interno-reconhecimentos", erro=str(recusa))

    # Gesto que não existe é formulário adulterado: volta sem mexer em nada.
    return _voltar("interno-reconhecimentos")
