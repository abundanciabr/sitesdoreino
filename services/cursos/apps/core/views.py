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
from django.http import (
    FileResponse,
    Http404,
    HttpResponsePermanentRedirect,
    HttpResponseRedirect,
    JsonResponse,
)
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_date
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.cursos import agente as assistente
from apps.cursos import enderecos
from apps.cursos import envio as checkpoint
from apps.cursos import laudo as parecer
from apps.cursos import progresso as portas
from apps.cursos.models import (
    Aula,
    Curso,
    Envio,
    Laudo,
    Pausa,
    Peca,
    Progresso,
    RascunhoDaIA,
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

# As três Partes do livro, com o título de cada uma (`PLANO-CELULA-CURSOS.md`,
# Parte 0: as três Partes são Fundação, Itens que vendem e Profissional). O
# aluno está com o LIVRO ABERTO ao lado da tela, e o mapa precisa dizer as
# Partes com as palavras que ele tem na mão. O número vem primeiro e em
# algarismo porque é ele que aparece no endereço da aula (`parte-1`): é assim
# que a barra do navegador e o sumário do livro se reconhecem.
NOMES_DAS_PARTES = {
    1: "Parte 1 · Fundação",
    2: "Parte 2 · Itens que vendem",
    3: "Parte 3 · Profissional",
}


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
def _de_fora(curso: Curso | None = None) -> dict:
    """Os dois endereços de outras células, que `{% url %}` não conhece, mais
    o endereço do mapa DESTE curso, que só a view sabe montar."""
    return {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
        "url_do_mapa": _url_do_mapa(curso),
    }


def _url_do_mapa(curso: Curso | None) -> str:
    """O mapa das portas: o do curso quando ele é conhecido, o endereço antigo
    quando não é (uma recusa não tem curso para apontar)."""
    return reverse("curso", args=[curso.slug]) if curso else reverse("mapa")


def _recusar(request, motivo: str, *, status: int, **extra):
    return render(
        request,
        "cursos/entrar.html",
        {"motivo": motivo, **_de_fora(), **extra},
        status=status,
    )


def _recusa_de_curso(ator, curso: Curso) -> str:
    """`""` quando esta pessoa entra NESTE curso; o motivo da recusa quando não.

    A segunda porta da sala (`DECISAO-cursos-matriculas-e-alunos.md` §1): a
    primeira pergunta se a pessoa é aluna, esta pergunta **de qual curso**.
    Enquanto havia um curso só, a primeira bastava por coincidência; no dia do
    segundo, todo aluno do primeiro abriria o segundo digitando o endereço.

    Os dois motivos são separados porque mandam a pessoa a lugares diferentes:
    `outro-curso` é "abra o seu, que é aquele ali"; `curso-sem-produto` é
    "ninguém entra aqui ainda, avise a escola".

    **Curso sem produto apontado FECHA, e é como todo curso nasce.** Não é
    descuido: um curso que não diz de qual produto é não pode ter a matrícula
    conferida, e nesta célula não conseguir conferir nunca é "pode entrar" (a
    mesma lei que `apps/core/sessao.py` aplica à `alunos` fora do ar). Curso
    fechado é problema visível, que aparece na primeira visita e se resolve com
    `manage.py apontar_o_produto_do_curso`; curso aberto por falta de
    apontamento é o defeito invisível que esta mudança existe para matar.
    """
    if not curso.produto_id:
        return "curso-sem-produto"
    if curso.produto_id not in ator.produtos_matriculados:
        return "outro-curso"
    return ""


def _meus_cursos(ator, site_id: str) -> list[Curso]:
    """Os cursos deste site em que ESTA pessoa está matriculada.

    A sala não OFERECE curso alheio: uma tela que convida para uma porta que
    ela mesma vai fechar é pior do que não mostrar nada, porque parece um
    direito e termina em recusa.
    """
    return [
        curso
        for curso in enderecos.cursos_do_site(site_id)
        if not _recusa_de_curso(ator, curso)
    ]


def _cursos_para_escolher(ator, site_id: str) -> list[dict]:
    """Os cursos DESTA pessoa com o endereço de cada um, para a tela que pede
    que ela escolha. Sem eles a recusa mandaria a pessoa adivinhar."""
    return [
        {
            "slug": curso.slug,
            "nome": curso.nome,
            "url": reverse("curso", args=[curso.slug]),
        }
        for curso in _meus_cursos(ator, site_id)
    ]


def _sala(request, slug: str | None = None):
    """`(pessoa, curso, None)` para quem pode entrar; `(None, None, resposta)`
    para quem não pode, com a resposta já pronta.

    Fail-CLOSED na matrícula, em DUAS portas: `eh_aluno` diz se a pessoa tem
    alguma matrícula ativa, e `_recusa_de_curso` diz se ela tem a DESTE curso.
    Não conseguir perguntar fecha as duas e diz isso.

    O CURSO VEM DO SLUG DO ENDEREÇO, e nunca de "o primeiro do site" (TAR-212).
    Sem slug (os endereços antigos, que continuam respondendo), a sala serve o
    curso quando ele é o ÚNICO DA PESSOA e pede para escolher quando não é: com
    dois cursos, "o primeiro" servia sempre o mesmo e o segundo era invisível
    para todo mundo, sem erro em lugar nenhum.
    """
    ator = quem_e(request)
    if not ator.autenticado:
        return None, None, _recusar(request, "entrar", status=200)
    if not ator.eh_aluno:
        motivo = "sem-matricula" if ator.matricula_conferida else "sem-resposta"
        return None, None, _recusar(request, motivo, status=403)
    site = site_atual()
    if not site:
        return None, None, _recusar(request, "sem-curso", status=200)
    if slug is not None:
        curso = enderecos.curso_do_site(site, slug)
        if curso is None:
            return (
                None,
                None,
                _recusar(
                    request,
                    "curso-desconhecido",
                    status=404,
                    slug_pedido=slug,
                    cursos=_cursos_para_escolher(ator, site),
                ),
            )
        recusa = _recusa_de_curso(ator, curso)
        if recusa:
            return (
                None,
                None,
                _recusar(
                    request,
                    recusa,
                    status=403,
                    cursos=_cursos_para_escolher(ator, site),
                ),
            )
        return ator.pessoa, curso, None
    if not enderecos.cursos_do_site(site):
        return None, None, _recusar(request, "sem-curso", status=200)
    meus = _meus_cursos(ator, site)
    if len(meus) == 1:
        return ator.pessoa, meus[0], None
    if not meus:
        # Ela é aluna de alguma coisa, e de nenhum curso DESTA escola. A tela
        # sai sem lista, e a lista vazia é a informação: não há para onde
        # mandá-la, e por isso a frase manda falar com a escola.
        return None, None, _recusar(request, "outro-curso", status=403, cursos=[])
    return (
        None,
        None,
        _recusar(
            request,
            "escolha-o-curso",
            status=200,
            cursos=_cursos_para_escolher(ator, site),
        ),
    )


def _voltar_ao_mapa(curso: Curso, *, recado: str = ""):
    endereco = _url_do_mapa(curso)
    return HttpResponseRedirect(f"{endereco}?recado={recado}" if recado else endereco)


def _url_da_aula(curso: Curso, aula: Aula) -> str:
    """O endereço do livro: o curso e a parte, os dois no caminho."""
    return reverse("aula-do-curso", args=[curso.slug, aula.bloco.parte, aula.numero])


def _voltar_a_aula(
    curso: Curso, aula: Aula, *, recado: str = "", erro: str = "", ancora: str = ""
):
    """POST-redirect-GET, com o recado por CÓDIGO e o erro por texto.

    O erro é texto porque vem da recusa, escrita para gente; o template o
    escapa, como escapa qualquer entrada.

    A volta é sempre para o endereço do livro, mesmo quando o gesto chegou pelo
    endereço antigo: é o endereço que o aluno vai copiar da barra do navegador
    e mandar para um colega.
    """
    endereco = _url_da_aula(curso, aula)
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
        # A parte vai junto porque ela é METADE do endereço da aula: sem ela o
        # template teria de adivinhá-la, e o mapa é justamente quem sabe.
        "parte": aula.bloco.parte,
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


def _curso_unico() -> Curso | None:
    """O curso deste site quando ele é o ÚNICO; `None` com zero ou com dois.

    É a condição que decide todo 301 desta célula. O endereço antigo não diz
    QUAL curso o aluno quer: com um só, a leitura é óbvia e o endereço muda de
    casa; com dois, mandá-lo para um deles seria um chute com cara de certeza,
    e o navegador guarda o 301 e nunca mais pergunta. Aí a tela que PERGUNTA
    (`_sala`) continua sendo a resposta certa.
    """
    site = site_atual()
    if not site:
        return None
    cursos = enderecos.cursos_do_site(site)
    return cursos[0] if len(cursos) == 1 else None


def _a_raiz_mudou_de_casa():
    """A raiz da célula (`/cursos`) mudada de casa (301) para o mapa do curso.

    Enquanto os dois endereços servissem a mesma sala com 200, um link antigo
    já compartilhado levaria o aluno a uma página que não diz em que parte do
    curso ele está: o oposto do que o endereço do livro veio fazer. O 301
    ensina o navegador e o buscador de uma vez (TAR-216).
    """
    curso = _curso_unico()
    if curso is None:
        return None
    return HttpResponsePermanentRedirect(reverse("curso", args=[curso.slug]))


@require_GET
def mapa(request, curso: str | None = None):
    """A home de UM curso: as 34 portas, o estado de cada uma, a próxima em
    destaque. `curso` é o slug do endereço; sem ele, é o endereço antigo.

    É aqui que a E00 NASCE `disponivel` para quem tem matrícula ativa
    (`progresso.nascer`, inerte a partir da segunda visita).

    O 301 vem ANTES da porta, e de propósito: um 301 é guardado pelo navegador
    pela URL, sem olhar o cookie, e um redirecionamento que dependesse de quem
    está olhando mentiria no cache do primeiro visitante em diante.
    """
    if curso is None:
        mudou_de_casa = _a_raiz_mudou_de_casa()
        if mudou_de_casa is not None:
            return mudou_de_casa
    pessoa, curso, recusa = _sala(request, curso)
    if recusa is not None:
        return recusa
    portas.nascer(pessoa, curso)
    partes, atual = _partes(curso, pessoa)
    return render(
        request,
        "cursos/mapa.html",
        {
            "curso": curso,
            "partes": partes,
            "atual": atual,
            "recado": RECADOS.get(request.GET.get("recado", "")),
            **_de_fora(curso),
        },
    )


# ---------------------------------------------------------------------------
# A AULA
# ---------------------------------------------------------------------------
def _aula_publicada(curso: Curso, numero: str) -> Aula:
    """A aula publicada deste curso, ou 404: rascunho não existe para o aluno."""
    return get_object_or_404(
        Aula.objects.select_related("bloco"),
        curso=curso,
        numero=numero,
        estado=Aula.Estado.PUBLICADA,
    )


def _pecas(aula: Aula) -> list[dict]:
    """As 16 peças na ORDEM_CANONICA, renderizadas de Markdown, só as escritas.

    As duas internas (o roteiro e o guia do mentor) NUNCA saem daqui, e a
    vídeo-aula em texto TAMBÉM não: a lista percorrida é a canônica, e nenhuma
    das três está nela. A vídeo-aula tem caminho próprio, em `_videoaula`.
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


def _videoaula(aula: Aula) -> dict:
    """A vídeo-aula em texto desta aula, renderizada, ou `html` vazio.

    O vazio é o que APAGA o botão na tela, e é o caso comum por muito tempo: as
    34 encomendas vão viver um bom tempo sem este texto, e botão que abre um
    modal vazio é defeito, não paciência.

    O renderizador é o mesmo das outras peças (`para_html`), de propósito: dois
    renderizadores dariam duas aparências para o mesmo Markdown. E o título do
    modal sai do rótulo do `TextChoices`, nunca escrito de novo aqui.
    """
    peca = aula.pecas.filter(tipo=Peca.Tipo.VIDEOAULA_EM_TEXTO).first()
    texto = (peca.texto if peca else "").strip()
    return {
        "rotulo": TipoDePeca(Peca.Tipo.VIDEOAULA_EM_TEXTO).label,
        "html": para_html(texto) if texto else "",
    }


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


def _porta_aberta(request, numero: str, *, slug: str | None = None, parte=None):
    """A pessoa, o curso, a aula publicada e o progresso NÃO trancado, ou a
    resposta que recusa (o convite, o 403, o 404, a parte errada ou a volta ao
    mapa). Devolve `(pessoa, curso, aula, progresso, recusa)`."""
    pessoa, curso, recusa = _sala(request, slug)
    if recusa is not None:
        return None, None, None, None, recusa
    portas.nascer(pessoa, curso)
    aula = _aula_publicada(curso, numero)
    # A PARTE É GUARDA, E NÃO ENFEITE: um endereço que aponta certo para a aula
    # ERRADA é pior do que um endereço quebrado, porque o aluno está com o
    # livro aberto e confia no número. A regra é a MESMA da porta de máquina
    # (`apps/cursos/enderecos.py`), e a tela diz onde a aula realmente está.
    errada = enderecos.parte_errada(curso, aula, parte)
    if errada is not None:
        return (
            None,
            None,
            None,
            None,
            _recusar(
                request,
                "parte-errada",
                status=404,
                parte_pedida=parte,
                aula_pedida=aula,
                url_certa=_url_da_aula(curso, aula),
                # A faixa desta recusa volta para o mapa DESTE curso: quem
                # errou a parte já disse qual curso quer.
                url_do_mapa=_url_do_mapa(curso),
            ),
        )
    progresso = portas.progresso_de(pessoa, aula)
    if progresso is None or progresso.estado == Progresso.Estado.TRANCADA:
        # Aula trancada mostra o mapa, não o conteúdo.
        return None, None, None, None, _voltar_ao_mapa(curso, recado="trancada")
    return pessoa, curso, aula, progresso, None


def _o_endereco_de_um_segmento_mudou_de_casa(numero: str):
    """O endereço antigo, de UM segmento só, mudado de casa (301).

    Um segmento pode ser duas coisas, e as duas mudam de casa. Slug de curso é
    palavra (`profissional`), número de aula é código (`E00`), e por isso a
    leitura é sem ambiguidade.

    **O slug de um curso** é o mapa digitado SEM a barra final. A barra é o que
    separa as duas famílias de endereço no urlconf (`config/urls.py`), e quem
    digita o endereço à mão come a barra: sem esta regra,
    `meshcraft.top/cursos/profissional` cairia em `<str:numero>` e responderia
    "essa aula não existe" a quem pediu o mapa do curso. O aluno vai digitar
    este endereço a partir do LIVRO, e uma barra esquecida não pode custar a
    aula. Este caso não depende de haver um curso só: o slug JÁ diz qual é.

    **O número de uma aula** é o endereço antigo da sala, e ele vira o endereço
    do livro, com a parte dentro (TAR-216). Aqui a mudança exige um curso único
    (`_curso_unico`) e uma aula publicada nele: um 301 para um 404 ensinaria ao
    navegador, de uma vez, um endereço que não serve.
    """
    site = site_atual()
    if not site:
        return None
    if enderecos.curso_do_site(site, numero) is not None:
        return HttpResponsePermanentRedirect(reverse("curso", args=[numero]))
    curso = _curso_unico()
    if curso is None:
        return None
    try:
        # O que conta como aula publicada tem UMA definição, e é a que a sala
        # usa. Repetir o filtro aqui deixaria as duas divergirem no dia em que
        # uma ganhasse condição nova, e o 301 apontaria para um 404.
        aula = _aula_publicada(curso, numero)
    except Http404:
        return None
    return HttpResponsePermanentRedirect(_url_da_aula(curso, aula))


@require_GET
def aula(request, numero: str, curso: str | None = None, parte: int | None = None):
    """A aula: as 16 peças, o botão da vídeo-aula em texto, o vídeo com as
    pausas, o quiz e o lugar do checkpoint.

    `curso` e `parte` vêm do endereço do livro; sem eles, é o endereço antigo,
    que muda de casa (301) antes da porta pelo motivo escrito em `mapa`.
    `disponivel` vira `em_producao` na primeira abertura (`progresso.abrir`).
    Aula em rascunho é 404; porta trancada volta ao mapa.
    """
    if curso is None:
        mudou_de_casa = _o_endereco_de_um_segmento_mudou_de_casa(numero)
        if mudou_de_casa is not None:
            return mudou_de_casa
    pessoa, curso, aula, progresso, recusa = _porta_aberta(
        request, numero, slug=curso, parte=parte
    )
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
            "videoaula": _videoaula(aula),
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
            **_de_fora(curso),
        },
    )


@require_POST
def registrar_pausa(request, numero: str, ordem: int):
    """O vídeo parou no segundo marcado, a pessoa escreveu: nasce o registro.

    Padrão POST-redirect-GET: sem ele um F5 repetiria o gesto. Aqui repetir já
    é inerte (uma pausa, um registro, `get_or_create`), mas o padrão fica.
    """
    pessoa, curso, aula, progresso, recusa = _porta_aberta(request, numero)
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
                curso,
                aula,
                erro="Preencha todos os campos da pausa antes de registrar.",
                ancora=ancora,
            )
        respostas[nome] = valor
    RegistroDePausa.objects.get_or_create(
        pessoa=pessoa, pausa=pausa, defaults={"respostas": respostas}
    )
    return _voltar_a_aula(curso, aula, recado="pausa-registrada", ancora=ancora)


@require_POST
def gravar_autoavaliacao(request, numero: str):
    """A pessoa responde ao quiz com as próprias palavras; só então a
    resposta-modelo abre. Gravada uma vez: a autoavaliação é o registro do que
    ela sabia ANTES de ver o modelo, e regravar apagaria isso."""
    pessoa, curso, aula, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    portas.abrir(progresso)
    if (progresso.autoavaliacao or {}).get("respostas"):
        return _voltar_a_aula(
            curso,
            aula,
            erro="A autoavaliação desta aula já foi gravada.",
            ancora="quiz",
        )
    itens = aula.quiz if isinstance(aula.quiz, list) else []
    respostas = [
        (request.POST.get(f"resposta_{indice}") or "").strip()
        for indice in range(len(itens))
    ]
    if not respostas or not all(respostas):
        return _voltar_a_aula(
            curso,
            aula,
            erro="Responda todas as perguntas antes de gravar a autoavaliação.",
            ancora="quiz",
        )
    progresso.autoavaliacao = {
        "respostas": respostas,
        "gravada_em": timezone.now().isoformat(),
    }
    progresso.save(update_fields=["autoavaliacao"])
    return _voltar_a_aula(curso, aula, recado="autoavaliacao-gravada", ancora="quiz")


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
    pessoa, curso, aula, progresso, recusa = _porta_aberta(request, numero)
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
        return _voltar_a_aula(curso, aula, erro=str(motivo), ancora="checkpoint")
    return _voltar_a_aula(curso, aula, recado="entregue", ancora="checkpoint")


# ---------------------------------------------------------------------------
# O LAUDO RECEBIDO (degrau 2.2): a tela do aluno
# ---------------------------------------------------------------------------
@require_GET
def laudo_recebido(request, numero: str):
    """O laudo do envio mais recente desta aula, para a PESSOA DA SESSÃO
    ([INV-CUR-P1]). Sem envio ainda, ou envio ainda sem laudo: a tela diz isso,
    nunca um erro. A data aparece ANTES do texto quando devolvido (lei §6).

    **Nunca identifica quem assinou.** A célula já não guarda e-mail nem nome
    de terceiros aqui ([INV-CUR-S1]), e o `avaliador` não sai desta tela por
    NOME nem por PAPEL: um laudo de Banca (Fase 5) é o veredito da mesa, não a
    opinião de um membro, e mostrar "Banca" não identifica ninguém — mas
    mostrar QUAL membro identificaria, e é isso que [INV-CUR-S2] proíbe. Por
    isso o template lê só `laudo.decisao`, `laudo.notas`, `laudo.forcas`,
    `laudo.mudanca` e `laudo.data_de_retorno`: nunca `laudo.avaliador`.
    """
    pessoa, curso, aula_da_porta, progresso, recusa = _porta_aberta(request, numero)
    if recusa is not None:
        return recusa
    envio = checkpoint.ultimo_envio(progresso)
    laudo_do_envio = getattr(envio, "laudo", None) if envio is not None else None
    return render(
        request,
        "cursos/laudo.html",
        {
            "aula": aula_da_porta,
            "envio": envio,
            "laudo": laudo_do_envio,
            **_de_fora(curso),
        },
    )


# ---------------------------------------------------------------------------
# O PLANTÃO (degrau 2.2): a tela da professora
# ---------------------------------------------------------------------------
# As três forças são sempre três campos fixos no formulário (nunca uma lista
# dinâmica): é o que garante que a VIEW manda exatamente três strings ao
# serviço em todo POST normal; o guarda de [INV-CUR-L6] que prova "2 ou 4 é
# recusado" chama `apps/cursos/laudo.py::emitir` direto, sem passar por aqui.
NUMERO_DE_FORCAS = 3

# O valor do botão que pede a sugestão da IA. O outro botão do mesmo formulário
# emite o laudo, e é ele o padrão: `gesto` ausente EMITE, nunca rascunha, para
# que nenhum POST antigo ou repetido vire uma chamada paga sem alguém ter
# clicado no botão que a pede.
GESTO_DE_RASCUNHAR = "rascunhar"

RECADOS_DO_PLANTAO = {
    "laudo-emitido": "Laudo emitido. O envio saiu da fila de revisão.",
    "ja-tem-laudo": "Este envio já recebeu um laudo: não há mais nada a fazer aqui.",
}


def _negar_plantao(request, *, status: int = 403):
    return render(request, "cursos/plantao_negado.html", {**_de_fora()}, status=status)


def _professor(request):
    """`(Ator, None)` para quem entra no plantão; `(None, resposta)` para quem
    não entra, com a resposta pronta.

    Fail-CLOSED pela união de `CURSOS_PROFESSORES` com `ADMIN_EMAILS` (as duas
    listas vazias, e-mail fora das duas, e identidade fora do ar, que devolve
    `VISITANTE` com `eh_professor=False`) dão a MESMA resposta, 403 — nunca
    500, e nunca o convite fail-OPEN da sala do aluno: aqui não há "sem saber
    quem é, então convida a entrar".
    """
    ator = quem_e(request)
    if not ator.eh_professor:
        return None, _negar_plantao(request)
    return ator, None


def _envio_do_plantao(site_id: str | None, envio_id: int) -> Envio:
    return get_object_or_404(
        Envio.objects.select_related("aula__curso", "aula__instrumento", "pessoa"),
        pk=envio_id,
        aula__curso__site_id=site_id,
    )


def _laudo_anterior_de(envio: Envio) -> Laudo | None:
    """O laudo do envio (numero - 1) desta mesma pessoa e aula, para o reenvio
    aparecer ao lado (lei §6). `None` no primeiro envio."""
    if envio.numero <= 1:
        return None
    anterior = (
        Envio.objects.filter(
            pessoa_id=envio.pessoa_id, aula_id=envio.aula_id, numero=envio.numero - 1
        )
        .select_related("laudo")
        .first()
    )
    return getattr(anterior, "laudo", None) if anterior is not None else None


def _item_da_fila(envio: Envio) -> dict:
    return {
        "envio": envio,
        "vencido": envio.vencido,
        "reenvio": envio.numero > 1,
        "laudo_anterior": _laudo_anterior_de(envio),
    }


@require_GET
def plantao_fila(request):
    """A fila de revisão: vencidos primeiro (`envio.fila_de_revisao` já ordena
    por `prazo_em`), reenvio com o laudo anterior ao lado, o estouro à vista."""
    ator, recusa = _professor(request)
    if recusa is not None:
        return recusa
    site = site_atual()
    itens = (
        [_item_da_fila(envio) for envio in checkpoint.fila_de_revisao(site)]
        if site
        else []
    )
    return render(
        request,
        "cursos/plantao_fila.html",
        {
            "itens": itens,
            "recado": RECADOS_DO_PLANTAO.get(request.GET.get("recado", "")),
            **_de_fora(),
        },
    )


def _criterios_do_formulario(envio: Envio, enviado: dict | None = None) -> list[dict]:
    """A escala do instrumento, mais o que a professora já tinha digitado (se
    esta é a segunda passada, depois de uma recusa 422): nada do que foi
    escrito se perde por causa de uma nota inválida em outro critério."""
    enviado = enviado or {}
    return [
        {
            "indice": indice,
            "nome": criterio.nome,
            "notas": list(range(criterio.minimo, criterio.maximo + 1)),
            "valor_nota": enviado.get(f"nota_{indice}", ""),
            "valor_frase": enviado.get(f"frase_{indice}", ""),
        }
        for indice, criterio in enumerate(
            checkpoint.criterios_de(envio.aula.instrumento)
        )
    ]


def _aulas_do_curso(envio: Envio) -> list[dict]:
    return [
        {
            "id": uma_aula.id,
            "numero": uma_aula.numero,
            "titulo": uma_aula.titulo_exibido,
        }
        for uma_aula in envio.aula.curso.aulas.order_by("ordem")
    ]


def _formulario_do_laudo(
    request,
    envio: Envio,
    *,
    erro: str = "",
    enviado: dict | None = None,
    status: int = 200,
    sugestao: assistente.Sugestao | None = None,
    rascunho_id: str = "",
):
    enviado = enviado or {}
    return render(
        request,
        "cursos/plantao_ficha.html",
        {
            "envio": envio,
            "laudo_anterior": _laudo_anterior_de(envio),
            "criterios": _criterios_do_formulario(envio, enviado),
            "aulas": _aulas_do_curso(envio),
            "erro": erro,
            "enviado": enviado,
            # A IA aparece na tela em três lugares, e nenhum deles preenche
            # decisão, data nem a pergunta de amanhã de manhã ([INV-CUR-L4]).
            "ia_ligada": assistente.ligado(),
            "sugestao": sugestao,
            "avisos_da_ia": assistente.avisos_de(sugestao) if sugestao else [],
            "rascunho_id": rascunho_id,
            **_de_fora(),
        },
        status=status,
    )


def _preenchido_pela_ia(sugestao: assistente.Sugestao, envio: Envio, digitado) -> dict:
    """Os campos do formulário com a sugestão dentro, e o que a professora já
    tinha digitado por cima.

    **Quem digitou, ganha.** A sugestão preenche só o que está vazio: pedir um
    rascunho no meio de um laudo meio escrito nunca apaga uma frase que a
    professora pensou. É a regra inteira, numa frase, e por isso ela é
    previsível na tela.

    **O que esta função NÃO escreve é [INV-CUR-L4] na prática:** não há
    `decisao`, não há `data_de_retorno` e não há `sabe_o_que_fazer_amanha` nas
    chaves montadas aqui. Mesmo que a IA devolva os três no JSON dela (e um
    modelo prestativo devolve), eles não têm por onde chegar ao formulário: o
    guarda que prova isso pela tela é `tests/test_inv_l4_a_ia_nao_decide.py`.
    """
    campos = {chave: valor for chave, valor in digitado.items()}

    def preencher(chave: str, valor) -> None:
        if valor and not str(campos.get(chave) or "").strip():
            campos[chave] = str(valor)

    for indice, criterio in enumerate(checkpoint.criterios_de(envio.aula.instrumento)):
        item = sugestao.notas.get(criterio.nome)
        if item:
            preencher(f"nota_{indice}", item["nota"])
            preencher(f"frase_{indice}", item["frase"])
    for indice, forca in enumerate(sugestao.forcas):
        preencher(f"forca_{indice}", forca)
    preencher("mudanca_texto", sugestao.mudanca.get("texto", ""))
    preencher("mudanca_aula", sugestao.mudanca.get("aula_id", ""))
    return campos


def _rascunhar_o_laudo(request, envio: Envio):
    """Pede ao Assistente de laudo a sugestão e RE-DESENHA o formulário com ela.

    Nunca grava laudo, nunca redireciona: o resultado deste botão é a mesma
    tela, com os campos pré-preenchidos e marcados "SUGERIDO", e a professora
    ainda tem tudo a decidir. A falha da IA devolve a mesma tela com a frase do
    que houve (503, porque quem falhou foi um serviço de fora) e sem perder uma
    letra do que ela já tinha escrito.
    """
    digitado = request.POST
    try:
        sugestao = assistente.rascunhar(envio, laudo_anterior=_laudo_anterior_de(envio))
    except assistente.AgenteIndisponivel as erro:
        return _formulario_do_laudo(
            request, envio, erro=str(erro), enviado=digitado, status=503
        )

    rascunho = RascunhoDaIA.objects.create(
        envio=envio,
        conteudo={
            "notas": sugestao.notas,
            "forcas": sugestao.forcas,
            "mudanca": sugestao.mudanca,
            "reenvio": sugestao.reenvio,
            "bloco": sugestao.bloco,
        },
        modelo=assistente.MODELO,
        tokens_entrada=sugestao.tokens_de_entrada,
        tokens_saida=sugestao.tokens_de_saida,
    )
    return _formulario_do_laudo(
        request,
        envio,
        enviado=_preenchido_pela_ia(sugestao, envio, digitado),
        sugestao=sugestao,
        rascunho_id=str(rascunho.pk),
    )


def _rascunho_deste_envio(request, envio: Envio) -> RascunhoDaIA | None:
    """O rascunho que a tela mandou de volta no campo escondido, se for DESTE
    envio.

    O filtro por `envio` não é zelo: o campo vem do navegador, e sem ele um id
    trocado à mão penduraria a Ficha de Série de um aluno no laudo de outro.
    Id ausente ou que não é número devolve `None`, e o laudo sai sem rascunho:
    emitir à mão é o caminho normal desta tela, nunca um erro.
    """
    id_do_rascunho = (request.POST.get("rascunho_id") or "").strip()
    if not id_do_rascunho.isdigit():
        return None
    return RascunhoDaIA.objects.filter(pk=id_do_rascunho, envio=envio).first()


def _gravar_laudo(request, envio: Envio, avaliador):
    """Lê o formulário, chama `laudo.emitir` e traduz a recusa em tela (422)
    ou o sucesso em POST-redirect-GET (302) de volta para a fila."""
    criterios = checkpoint.criterios_de(envio.aula.instrumento)
    notas = {
        criterio.nome: {
            "nota": _nota(request.POST.get(f"nota_{indice}")),
            "frase": request.POST.get(f"frase_{indice}", ""),
        }
        for indice, criterio in enumerate(criterios)
    }
    forcas = [
        request.POST.get(f"forca_{indice}", "") for indice in range(NUMERO_DE_FORCAS)
    ]
    mudanca = [
        {
            "texto": request.POST.get("mudanca_texto", ""),
            "aula_id": request.POST.get("mudanca_aula", ""),
        }
    ]
    decisao = request.POST.get("decisao", "")
    data_de_retorno = parse_date(request.POST.get("data_de_retorno") or "")
    ajuste_feito = request.POST.get("ajuste_feito", "")
    # A pergunta só existe como `true`: a caixa não marcada é OMITIDA do POST
    # (ela não tem `value` de "não"), e ausência é lida como não respondida,
    # nunca como `false` (lei §6, [INV-CUR-L7]).
    sabe_o_que_fazer_amanha = (
        True if request.POST.get("sabe_o_que_fazer_amanha") == "sim" else None
    )

    try:
        parecer.emitir(
            envio,
            avaliador=avaliador,
            papel=Laudo.Papel.PROFESSOR,
            notas=notas,
            forcas=forcas,
            mudanca=mudanca,
            decisao=decisao,
            data_de_retorno=data_de_retorno,
            ajuste_feito=ajuste_feito,
            sabe_o_que_fazer_amanha=sabe_o_que_fazer_amanha,
            rascunho=_rascunho_deste_envio(request, envio),
        )
    except parecer.LaudoRecusado as motivo:
        return _formulario_do_laudo(
            request,
            envio,
            erro=str(motivo),
            enviado=request.POST,
            status=422,
            rascunho_id=(request.POST.get("rascunho_id") or "").strip(),
        )
    endereco = reverse("plantao")
    return HttpResponseRedirect(f"{endereco}?recado=laudo-emitido")


@require_http_methods(["GET", "POST"])
def plantao_ficha(request, envio_id: int):
    """O formulário do laudo: a rubrica completa, as três forças, a mudança, a
    decisão, a data de retorno (só quando devolvido) e a pergunta de amanhã de
    manhã. `GET` desenha; `POST` valida pelas nove regras de `laudo.emitir` e,
    na recusa, RE-DESENHA com o texto digitado preservado e status 422 — ao
    contrário do checkpoint do aluno, este formulário é grande demais para se
    dar ao luxo de um redirect que perde tudo o que a professora escreveu.

    **O mesmo formulário tem dois botões**, e é `gesto` que os separa:
    "Rascunhar laudo" pede a sugestão ao Assistente de laudo e volta com os
    campos pré-preenchidos; qualquer outro valor emite. O emitir é o PADRÃO (e
    não o rascunhar) de propósito: um POST sem `gesto` é o caminho antigo desta
    tela, e o que ele nunca pode virar por acidente é uma chamada paga.
    """
    ator, recusa = _professor(request)
    if recusa is not None:
        return recusa
    envio = _envio_do_plantao(site_atual(), envio_id)
    if envio.estado not in checkpoint.ESTADOS_NA_FILA:
        endereco = reverse("plantao")
        return HttpResponseRedirect(f"{endereco}?recado=ja-tem-laudo")
    if request.method == "POST":
        if request.POST.get("gesto") == GESTO_DE_RASCUNHAR:
            return _rascunhar_o_laudo(request, envio)
        return _gravar_laudo(request, envio, ator.pessoa)
    return _formulario_do_laudo(request, envio)
