"""As telas da sala de aula: o mapa das portas, a aula, e os três gestos (a
pausa, a autoavaliação e, desde o degrau 2.1, a entrega do checkpoint).

QUEM ENTRA, E QUEM DECIDE
-------------------------
Quem diz quem é a pessoa é a `identidade`, por `apps/core/sessao.py::quem_e`;
quem decide se ela vê a aula é ESTA célula, pela matrícula ativa perguntada à
`alunos`, fail-CLOSED. Visitante vê o convite para entrar (nunca um erro);
quem entrou sem matrícula, ou cuja matrícula não deu para conferir, recebe 403
com a frase que diz qual dos dois casos é.

ESTA CÉLULA NÃO ASSINA SESSÃO, E NENHUMA VIEW DAQUI PODE ESQUECER ISSO
-----------------------------------------------------------------------
Não há `SessionMiddleware`, não há `request.session`, e a tentação de guardar
"já viu a cerimônia?" ali dentro é a que desloga a plataforma inteira sem erro
em lugar nenhum ([INV-P12]; `armadilhas/143`). O estado mora no `Progresso`.

NENHUMA TELA COMPARA ALUNOS ([INV-CUR-P1])
-------------------------------------------
Toda consulta daqui é filtrada pela pessoa da sessão. Não existe rota de
lista, ranking nem "quem está na sua turma": a sala é da pessoa que a abriu.

O VÍDEO É POR LINK, E O TOCADOR NÃO É CONTROLADO
------------------------------------------------
Onde os vídeos moram é decisão que o mantenedor adiou (lei §8). Até lá, o
vídeo do YouTube ou do Vimeo entra embutido e qualquer outro entra como link;
quem pausa no segundo marcado e retoma depois de registrar é o aluno, e a
lista de pausas diz em que segundo. Um tocador que parasse sozinho é o degrau
que a decisão dele abre.

Formulário normal com melhoria progressiva: nenhum caminho existe só com
script. Molde: `services/gamificacao/apps/core/views.py`.
"""

from __future__ import annotations

import mimetypes
import re
from pathlib import Path
from urllib.parse import quote, urlsplit

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.cursos import envio as checkpoint
from apps.cursos import progresso as portas
from apps.cursos.models import (
    Aula,
    Curso,
    Envio,
    Pausa,
    Peca,
    Progresso,
    RegistroDePausa,
    TipoDePeca,
)

from .markdown import para_html
from .sessao import quem_e, site_atual

# Os recados que uma tela manda para si mesma depois de um POST. São CÓDIGOS e
# não frases: o texto vive aqui, e uma frase pronta viajando na barra de
# endereço é uma frase que alguém troca por outra e manda por link a um aluno.
RECADOS = {
    "pausa-registrada": "Registro guardado. Pode retomar o vídeo.",
    "autoavaliacao-gravada": (
        "Sua autoavaliação foi gravada. As respostas-modelo estão abertas abaixo."
    ),
    "trancada": (
        "Essa porta ainda está trancada. A porta aberta para você é a que está "
        "em destaque."
    ),
    "entregue": (
        "Recebido. Seu envio entrou na fila de revisão: o laudo chega em até "
        "24 horas."
    ),
}

# As prévias que o formulário do checkpoint sugere, na ordem da lei §3.12
# (sólido, wireframe, silhueta), mais uma linha em branco para o que a
# encomenda pedir. Toda prévia é opcional, e o rótulo sugerido pode ser trocado.
PREVIAS_SUGERIDAS = ("Sólido", "Wireframe", "Silhueta", "")

# Os estados de porta em que a pessoa TEM o que fazer nela: é destes que sai a
# "próxima porta" em destaque no mapa. `trancada` e `concluida` ficam de fora.
ESTADOS_COM_A_PESSOA = (
    Progresso.Estado.DISPONIVEL,
    Progresso.Estado.EM_PRODUCAO,
    Progresso.Estado.DEVOLVIDA,
    Progresso.Estado.ENVIADA,
)

NOMES_DAS_PARTES = {1: "Parte 1", 2: "Parte 2", 3: "Parte 3"}


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/cursos/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).
    Qualquer isenção de middleware compara `request.path_info`, **nunca**
    `request.path`. Guarda: `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def servir_estatico(request, caminho: str):
    """O CSS da sala. Rota de MÁQUINA, como o `/healthz`.

    Sem ela o estilo é 404 em produção e **só lá** (`armadilhas/083` e `/102`).
    Copiado de `services/gamificacao/apps/core/views.py`, não importado.
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
# A PORTA DA SALA: quem entra, e em que curso
# ---------------------------------------------------------------------------
def _de_fora() -> dict:
    """Os dois endereços de outras células, que `{% url %}` não conhece."""
    return {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }


def _recusar(request, motivo: str, *, status: int):
    return render(
        request, "cursos/entrar.html", {"motivo": motivo, **_de_fora()}, status=status
    )


def _sala(request):
    """`(pessoa, curso, None)` para quem pode entrar; `(None, None, resposta)`
    para quem não pode, com a resposta já pronta.

    Fail-CLOSED na matrícula: `eh_aluno` só é verdadeiro quando a `alunos`
    respondeu `aluno`. Não conseguir perguntar fecha a porta e diz isso.
    """
    ator = quem_e(request)
    if not ator.autenticado:
        return None, None, _recusar(request, "entrar", status=200)
    if not ator.eh_aluno:
        motivo = "sem-matricula" if ator.matricula_conferida else "sem-resposta"
        return None, None, _recusar(request, motivo, status=403)
    site = site_atual()
    curso = Curso.objects.filter(site_id=site).order_by("id").first() if site else None
    if curso is None:
        return None, None, _recusar(request, "sem-curso", status=200)
    return ator.pessoa, curso, None


def _voltar_ao_mapa(*, recado: str = ""):
    endereco = reverse("mapa")
    return HttpResponseRedirect(f"{endereco}?recado={recado}" if recado else endereco)


def _voltar_a_aula(numero: str, *, recado: str = "", erro: str = "", ancora: str = ""):
    """POST-redirect-GET, com o recado por CÓDIGO e o erro por texto.

    O erro é texto porque vem da recusa, escrita para gente; o template o
    escapa, como escapa qualquer entrada.
    """
    endereco = reverse("aula", args=[numero])
    if recado:
        endereco = f"{endereco}?recado={recado}"
    elif erro:
        endereco = f"{endereco}?erro={quote(erro)}"
    if ancora:
        endereco = f"{endereco}#{ancora}"
    return HttpResponseRedirect(endereco)


# ---------------------------------------------------------------------------
# O MAPA DAS PORTAS
# ---------------------------------------------------------------------------
def _porta(aula: Aula, progresso: Progresso | None) -> dict:
    """Uma porta pronta para o template, com a conta feita aqui e não em `{{ }}`."""
    estado = progresso.estado if progresso else Progresso.Estado.TRANCADA
    publicada = aula.estado == Aula.Estado.PUBLICADA
    trancada = estado == Progresso.Estado.TRANCADA
    if trancada:
        rotulo = Progresso.Estado.TRANCADA.label
    elif not publicada:
        rotulo = "Em preparo"
    else:
        rotulo = Progresso.Estado(estado).label
    return {
        "numero": aula.numero,
        "titulo": aula.titulo_exibido,
        "estado": estado,
        "rotulo": rotulo,
        "boss": aula.e_boss,
        # Só se entra numa porta que não está trancada E cuja aula já foi
        # publicada: a aula em rascunho responde 404, e um link para ela seria
        # uma promessa quebrada no mapa.
        "abre": (not trancada) and publicada,
    }


def _partes(curso: Curso, pessoa) -> tuple[list[dict], dict | None]:
    """As três Partes com os doze Blocos e as 34 portas, e a porta em destaque.

    Uma consulta de progresso, filtrada pela PESSOA DA SESSÃO ([INV-CUR-P1]):
    linha ausente é porta trancada.
    """
    por_aula = {
        p.aula_id: p for p in Progresso.objects.filter(pessoa=pessoa, aula__curso=curso)
    }
    partes: dict[int, dict] = {}
    atual = None
    for aula in curso.aulas.select_related("bloco").order_by("ordem"):
        porta = _porta(aula, por_aula.get(aula.id))
        if atual is None and porta["estado"] in ESTADOS_COM_A_PESSOA:
            atual = porta
        parte = partes.setdefault(
            aula.bloco.parte,
            {"nome": NOMES_DAS_PARTES.get(aula.bloco.parte, ""), "blocos": {}},
        )
        bloco = parte["blocos"].setdefault(
            aula.bloco.ordem,
            {
                "letra": aula.bloco.letra,
                "nome": aula.bloco.nome or f"Bloco {aula.bloco.letra}",
                "portas": [],
            },
        )
        bloco["portas"].append(porta)
    if atual is not None:
        atual["atual"] = True
    lista = [
        {
            "nome": parte["nome"],
            "blocos": [parte["blocos"][k] for k in sorted(parte["blocos"])],
        }
        for _, parte in sorted(partes.items())
    ]
    return lista, atual


@require_GET
def mapa(request):
    """A home do curso: as 34 portas, o estado de cada uma, a próxima em destaque.

    É aqui que a E00 NASCE `disponivel` para quem tem matrícula ativa
    (`progresso.nascer`, inerte a partir da segunda visita).
    """
    pessoa, curso, recusa = _sala(request)
    if recusa is not None:
        return recusa
    portas.nascer(pessoa, curso)
    partes, atual = _partes(curso, pessoa)
    return render(
        request,
        "cursos/mapa.html",
        {
            "partes": partes,
            "atual": atual,
            "recado": RECADOS.get(request.GET.get("recado", "")),
            **_de_fora(),
        },
    )


# ---------------------------------------------------------------------------
# A AULA
# ---------------------------------------------------------------------------
def _aula_publicada(curso: Curso, numero: str) -> Aula:
    """A aula publicada deste curso, ou 404: rascunho não existe para o aluno."""
    return get_object_or_404(
        Aula, curso=curso, numero=numero, estado=Aula.Estado.PUBLICADA
    )


def _pecas(aula: Aula) -> list[dict]:
    """As 16 peças na ORDEM_CANONICA, renderizadas de Markdown, só as escritas.

    As duas internas (o roteiro e o guia do mentor) NUNCA saem daqui: a lista
    percorrida é a canônica, e elas não estão nela.
    """
    por_tipo = {peca.tipo: peca.texto for peca in aula.pecas.all()}
    return [
        {
            "tipo": tipo,
            "rotulo": TipoDePeca(tipo).label,
            "html": para_html(por_tipo[tipo]),
        }
        for tipo in Peca.ORDEM_CANONICA
        if por_tipo.get(tipo, "").strip()
    ]


_ID_DO_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_ID_DO_VIMEO = re.compile(r"^\d+$")


def _embutir(url: str) -> str | None:
    """O endereço de embutir, SÓ para YouTube e Vimeo; `None` para o resto.

    O `src` do iframe é montado a partir do ID extraído, nunca da URL crua:
    é o que impede um endereço qualquer de virar um quadro dentro da aula.
    """
    partes = urlsplit(url)
    if partes.scheme != "https":
        return None
    host = partes.netloc.lower().removeprefix("www.").removeprefix("m.")
    segmentos = [s for s in partes.path.split("/") if s]
    if host == "youtu.be" and segmentos:
        candidato = segmentos[0]
    elif host == "youtube.com" and segmentos:
        if segmentos[0] == "watch":
            candidato = dict(
                par.split("=", 1) for par in partes.query.split("&") if "=" in par
            ).get("v", "")
        elif segmentos[0] in ("embed", "shorts") and len(segmentos) > 1:
            candidato = segmentos[1]
        else:
            return None
    elif host == "vimeo.com" and segmentos:
        candidato = segmentos[-1]
        return (
            f"https://player.vimeo.com/video/{candidato}"
            if _ID_DO_VIMEO.match(candidato)
            else None
        )
    elif host == "player.vimeo.com" and len(segmentos) >= 2 and segmentos[0] == "video":
        candidato = segmentos[1]
        return (
            f"https://player.vimeo.com/video/{candidato}"
            if _ID_DO_VIMEO.match(candidato)
            else None
        )
    else:
        return None
    if _ID_DO_YOUTUBE.match(candidato):
        return f"https://www.youtube-nocookie.com/embed/{candidato}"
    return None


def _video(aula: Aula) -> dict:
    url = (aula.video_url or "").strip()
    return {"link": url, "embutido": _embutir(url) if url else None}


def _tempo(segundos: int) -> str:
    """`90` vira `1:30`; `3725` vira `1:02:05`."""
    horas, resto = divmod(segundos, 3600)
    minutos, seg = divmod(resto, 60)
    if horas:
        return f"{horas}:{minutos:02d}:{seg:02d}"
    return f"{minutos}:{seg:02d}"


def _campos(pausa: Pausa) -> list[str]:
    """Os mínimos do registro, como o editor os gravou (uma lista de frases)."""
    campos = pausa.campos if isinstance(pausa.campos, list) else []
    return [str(campo) for campo in campos]


def _pausas(aula: Aula, pessoa) -> list[dict]:
    """As pausas da aula, cada uma com o registro DESTA pessoa, se houver."""
    registros = {
        r.pausa_id: r
        for r in RegistroDePausa.objects.filter(pessoa=pessoa, pausa__aula=aula)
    }
    linhas = []
    for pausa in aula.pausas.all():
        registro = registros.get(pausa.id)
        campos = _campos(pausa)
        linhas.append(
            {
                "ordem": pausa.ordem,
                "segundo": pausa.segundo,
                "tempo": _tempo(pausa.segundo),
                "tipo": Pausa.Tipo(pausa.tipo).label,
                "pede": pausa.pede,
                "campos": [
                    {"indice": indice, "nome": nome}
                    for indice, nome in enumerate(campos)
                ],
                "registro": (
                    [
                        {"nome": nome, "texto": registro.respostas.get(nome, "")}
                        for nome in campos
                    ]
                    if registro is not None
                    else None
                ),
                "registrado_em": registro.registrado_em if registro else None,
            }
        )
    return linhas


def _quiz(aula: Aula, progresso: Progresso) -> dict:
    """As perguntas, e a resposta-modelo SÓ depois de a pessoa gravar a sua."""
    itens = aula.quiz if isinstance(aula.quiz, list) else []
    minhas = (progresso.autoavaliacao or {}).get("respostas") or []
    gravada = bool(minhas)
    perguntas = []
    for indice, item in enumerate(itens):
        if not isinstance(item, dict):
            continue
        perguntas.append(
            {
                "indice": indice,
                "pergunta": item.get("pergunta", ""),
                "resposta_modelo": item.get("resposta_modelo", "") if gravada else "",
                "minha": minhas[indice] if indice < len(minhas) else "",
            }
        )
    return {"perguntas": perguntas, "gravada": gravada}


def _checkpoint(progresso: Progresso, *, pausas_ok: bool) -> dict:
    """O bloco do checkpoint, com a conta feita aqui e não em `{{ }}`: o
    formulário aberto ou o porquê de fechado, o número do próximo envio, os
    critérios da escala, e o último envio (quando há), para a tela dizer
    "recebido em, revisão até".

    Toda regra é de `envio.py`: quem pode entregar, e quando. Aqui só se traduz
    o estado em frases e campos.
    """
    estado = Progresso.Estado(progresso.estado)
    if estado not in checkpoint.ESTADOS_QUE_ENTREGAM:
        fechado_por = checkpoint.POR_QUE_NAO_ENTREGA[estado]
    elif not pausas_ok:
        fechado_por = checkpoint.A_FRASE_DAS_PAUSAS
    else:
        fechado_por = ""
    ultimo = checkpoint.ultimo_envio(progresso)
    return {
        "aberto": not fechado_por,
        "fechado_por": fechado_por,
        "reenvio": estado == Progresso.Estado.DEVOLVIDA,
        "proximo_numero": ultimo.numero + 1 if ultimo else 1,
        "criterios": [
            {
                "indice": indice,
                "nome": criterio.nome,
                "notas": list(range(criterio.minimo, criterio.maximo + 1)),
            }
            for indice, criterio in enumerate(
                checkpoint.criterios_de(progresso.aula.instrumento)
            )
        ],
        "previas": [
            {"indice": indice, "rotulo": rotulo}
            for indice, rotulo in enumerate(PREVIAS_SUGERIDAS)
        ],
        "envio": (
            {
                "numero": ultimo.numero,
                "estado": Envio.Estado(ultimo.estado).label,
                "enviado_em": ultimo.enviado_em,
                "prazo_em": ultimo.prazo_em,
                "estourado_em": ultimo.estourado_em,
                "links": ultimo.links,
            }
            if ultimo
            else None
        ),
    }


def _porta_aberta(request, numero: str):
    """A pessoa, o curso, a aula publicada e o progresso NÃO trancado, ou a
    resposta que recusa (o convite, o 403, o 404 ou a volta ao mapa)."""
    pessoa, curso, recusa = _sala(request)
    if recusa is not None:
        return None, None, None, recusa
    portas.nascer(pessoa, curso)
    aula = _aula_publicada(curso, numero)
    progresso = portas.progresso_de(pessoa, aula)
    if progresso is None or progresso.estado == Progresso.Estado.TRANCADA:
        # Aula trancada mostra o mapa, não o conteúdo.
        return None, None, None, _voltar_ao_mapa(recado="trancada")
    return pessoa, aula, progresso, None


@require_GET
def aula(request, numero: str):
    """A aula: as 16 peças, o vídeo com as pausas, o quiz e o lugar do checkpoint.

    `disponivel` vira `em_producao` na primeira abertura (`progresso.abrir`).
    Aula em rascunho é 404; porta trancada volta ao mapa.
    """
    pessoa, aula, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    portas.abrir(progresso)
    return render(
        request,
        "cursos/aula.html",
        {
            "aula": aula,
            "estado": Progresso.Estado(progresso.estado).label,
            "pecas": _pecas(aula),
            "video": _video(aula),
            "pausas": _pausas(aula, pessoa),
            "quiz": _quiz(aula, progresso),
            "checkpoint": _checkpoint(
                progresso, pausas_ok=portas.pausas_registradas(progresso)
            ),
            "aceito_quando": (
                aula.aceito_quando if isinstance(aula.aceito_quando, list) else []
            ),
            "recado": RECADOS.get(request.GET.get("recado", "")),
            "erro": request.GET.get("erro", ""),
            **_de_fora(),
        },
    )


@require_POST
def registrar_pausa(request, numero: str, ordem: int):
    """O vídeo parou no segundo marcado, a pessoa escreveu: nasce o registro.

    Padrão POST-redirect-GET: sem ele um F5 repetiria o gesto. Aqui repetir já
    é inerte (uma pausa, um registro, `get_or_create`), mas o padrão fica.
    """
    pessoa, aula, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    portas.abrir(progresso)
    pausa = get_object_or_404(Pausa, aula=aula, ordem=ordem)
    ancora = f"pausa-{pausa.ordem}"
    respostas = {}
    for indice, nome in enumerate(_campos(pausa)):
        valor = (request.POST.get(f"campo_{indice}") or "").strip()
        if not valor:
            return _voltar_a_aula(
                numero,
                erro="Preencha todos os campos da pausa antes de registrar.",
                ancora=ancora,
            )
        respostas[nome] = valor
    RegistroDePausa.objects.get_or_create(
        pessoa=pessoa, pausa=pausa, defaults={"respostas": respostas}
    )
    return _voltar_a_aula(numero, recado="pausa-registrada", ancora=ancora)


@require_POST
def gravar_autoavaliacao(request, numero: str):
    """A pessoa responde ao quiz com as próprias palavras; só então a
    resposta-modelo abre. Gravada uma vez: a autoavaliação é o registro do que
    ela sabia ANTES de ver o modelo, e regravar apagaria isso."""
    pessoa, aula, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    portas.abrir(progresso)
    if (progresso.autoavaliacao or {}).get("respostas"):
        return _voltar_a_aula(
            numero, erro="A autoavaliação desta aula já foi gravada.", ancora="quiz"
        )
    itens = aula.quiz if isinstance(aula.quiz, list) else []
    respostas = [
        (request.POST.get(f"resposta_{indice}") or "").strip()
        for indice in range(len(itens))
    ]
    if not respostas or not all(respostas):
        return _voltar_a_aula(
            numero,
            erro="Responda todas as perguntas antes de gravar a autoavaliação.",
            ancora="quiz",
        )
    progresso.autoavaliacao = {
        "respostas": respostas,
        "gravada_em": timezone.now().isoformat(),
    }
    progresso.save(update_fields=["autoavaliacao"])
    return _voltar_a_aula(numero, recado="autoavaliacao-gravada", ancora="quiz")


def _nota(valor: str | None) -> int | None:
    """O `<select>` manda texto; a escala quer inteiro. Vazio ou lixo é `None`,
    e é `envio.py` quem diz "dê uma nota de 1 a 5"."""
    try:
        return int(valor or "")
    except ValueError:
        return None


@require_POST
def entregar_checkpoint(request, numero: str):
    """O aluno entrega o checkpoint por link: nasce o `Envio` na fila de 24
    horas (degrau 2.1). Toda regra mora em `envio.entregar`; aqui só se lê o
    formulário e se traduz a recusa em frase. POST-redirect-GET: um F5 depois
    de entregar não entrega de novo, e se entregasse a porta já estaria
    `enviada` e a segunda seria recusada com a frase certa."""
    pessoa, aula, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    portas.abrir(progresso)
    links = [
        {
            "rotulo": checkpoint.ROTULO_DO_ARQUIVO,
            "url": request.POST.get("arquivo", ""),
        }
    ]
    for indice in range(len(PREVIAS_SUGERIDAS)):
        links.append(
            {
                "rotulo": request.POST.get(f"previa_rotulo_{indice}", ""),
                "url": request.POST.get(f"previa_url_{indice}", ""),
            }
        )
    criterios = checkpoint.criterios_de(aula.instrumento)
    if criterios:
        laudo = {
            "notas": {
                criterio.nome: {
                    "nota": _nota(request.POST.get(f"nota_{indice}")),
                    "frase": request.POST.get(f"frase_{indice}", ""),
                }
                for indice, criterio in enumerate(criterios)
            }
        }
    else:
        laudo = {"texto": request.POST.get("autoavaliacao", "")}
    try:
        checkpoint.entregar(
            progresso,
            links=links,
            readme=request.POST.get("readme", ""),
            laudo_do_aluno=laudo,
        )
    except checkpoint.EnvioRecusado as motivo:
        return _voltar_a_aula(numero, erro=str(motivo), ancora="checkpoint")
    return _voltar_a_aula(numero, recado="entregue", ancora="checkpoint")
