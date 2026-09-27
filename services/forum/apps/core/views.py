"""As telas do fórum.

Nenhuma view confere permissão por conta própria: quem responde "pode?" é
`apps/core/permissoes.py`, sempre. Uma regra em dois lugares diverge no primeiro
dia em que alguém mexer num deles.
"""

import mimetypes
import os
from pathlib import Path
from urllib.parse import quote, urlencode

from django.conf import settings
from django.db import transaction
from django.db.models import Exists, F, OuterRef, Window
from django.db.models.functions import RowNumber
from django.http import FileResponse, Http404, HttpResponseForbidden, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST
from django.views.decorators.csrf import csrf_protect

from apps.forum.models import (
    Area,
    MembroDoGrupo,
    Mensagem,
    Pessoa,
    RegistroDeModeracao,
    Topico,
)

from . import agente
from .etiquetas import decorar as decorar_com_etiquetas
from .galeria import caixa_da_galeria
from .leitura import (
    marcar_area_como_lida,
    novidades_por_area,
    registrar_leitura,
    topicos_com_novidade,
)
from .permissoes import (
    areas_visiveis,
    pode_escrever,
    pode_ler,
    pode_moderar,
    por_que_nao_escreve,
)
from apps.forum import eventos
from apps.forum.tasks import relay_apos_commit

from .menu import site_id_do_host
from .sessao import email_da_equipe, quem_e

# ---------------------------------------------------------------------------
# OS LIMITES DO QUE SE ESCREVE — números, num lugar só
# ---------------------------------------------------------------------------
# Não são regra de negócio inventada: são a diferença entre uma tela que recusa
# com uma frase em português e um `DataError` do PostgreSQL virando HTTP 500. O
# teto do título é o `max_length` do modelo, repetido aqui para a recusa
# acontecer ANTES do banco.
TITULO_MINIMO = 5
TITULO_MAXIMO = 180
TEXTO_MINIMO = 2
# Vinte mil caracteres são umas oito páginas. O limite não existe contra o aluno
# prolixo — existe para uma requisição não conseguir empurrar um megabyte para
# dentro da coluna de busca que todo mundo consulta.
TEXTO_MAXIMO = 20000

ERRO_TITULO_CURTO = (
    f"O título precisa ter pelo menos {TITULO_MINIMO} letras — "
    "escreva a dúvida em uma linha, como você contaria para um colega."
)
ERRO_TITULO_LONGO = (
    f"O título passou de {TITULO_MAXIMO} letras. O resto cabe na mensagem."
)
ERRO_TEXTO_VAZIO = "Faltou escrever a mensagem."
ERRO_TEXTO_LONGO = "A mensagem é longa demais para uma só. Divida em duas."
ERRO_TOPICO_TRANCADO = "Esta conversa foi trancada pela moderação."
ERRO_SEM_LEITURA = (
    "Entre para o fórum guardar o que você já leu. Sem entrar, ele não tem de "
    "quem guardar essa marca."
)
ERRO_SEM_PERMISSAO = (
    "Você não pode escrever nesta área. "
    "Volte para a página dela — ela diz o motivo, em português."
)


@require_GET
def healthz(request):
    """A sonda do container. Rota de MÁQUINA.

    Ela responde nas DUAS formas de entrada, porque as duas existem em
    produção: `/forum/healthz` pela internet (o Traefik **não** remove o
    prefixo) e `/healthz` pelo healthcheck do compose (`armadilhas/029`).

    Quando esta célula ganhar uma porta de autorização, a isenção desta rota
    tem de ser comparada por `request.path_info` — **nunca** `request.path`,
    que pela borda pública contém o prefixo. Guarda:
    `tests/test_healthz_script_name.py`.
    """
    return JsonResponse({"status": "ok"})


@require_GET
def servir_estatico(request, caminho: str):
    """O CSS do fórum. Rota de MÁQUINA, como o `/healthz`.

    Sem ela o estilo é 404 em produção e **só lá** (`armadilhas/083` e `/102`):
    com `DEBUG=0` o Django não serve estático, e não há nginx nem CDN atrás do
    Traefik. Em dev funciona, e é justamente por isso que passa despercebido.

    O nome da rota é `estatico`, e não `static`, de propósito: os templates a
    chamam por `{% url 'estatico' … %}`, e **é `{% url %}` e não `{% static %}`
    porque só o primeiro carrega o prefixo público** — `/static/forum.css` em
    `meshcraft.top` é endereço do `funil`, não do fórum.
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


@require_GET
def home(request):
    """A porta do fórum: as áreas que esta pessoa enxerga.

    Visitante vê as áreas públicas — é a aposta de crescimento da escola, e é
    o que o robô do Google encontra.
    """
    ator = quem_e(request)
    return render(request, "forum/home.html", contexto_da_home(ator))


@require_GET
def ver_area(request, slug: str):
    """Os tópicos de uma área. 404 para quem não pode ler — nunca 403.

    **404 e não 403 é decisão de segurança:** um 403 confirma que a área
    existe, e numa escola isso vaza a estrutura de turmas para quem não deveria
    conhecê-la.

    A consulta NÃO filtra `ativa=True`: quem decide se uma área arquivada
    aparece é `pode_ler` (e ela aparece só para quem modera). Dois lugares
    decidindo a mesma coisa é como um deles passa a discordar do outro.
    """
    ator = quem_e(request)
    area = get_object_or_404(Area, slug=slug)
    if not pode_ler(area, ator):
        raise Http404("área não encontrada")

    return render(request, "forum/area.html", contexto_da_area(request, ator, area))


@require_GET
def ver_topico(request, topico_id: int):
    """Uma conversa inteira. A permissão é a da ÁREA — o tópico não afrouxa."""
    ator = quem_e(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"), pk=topico_id
    )
    if not pode_ler(topico.area, ator):
        raise Http404("tópico não encontrado")
    if topico.estado != Topico.Estado.PUBLICADO and not pode_moderar(ator):
        # Tópico fora do ar é 404 para o mundo inteiro, e continua abrindo para
        # quem pode devolvê-lo ao ar — senão "tirar do ar" seria porta de mão
        # única, e quem modera teria de decidir sem reler o que tirou.
        raise Http404("tópico não encontrado")

    # Abrir a conversa é o gesto que a marca como lida (`leitura.py` explica por
    # que uma escrita durante um GET é aceitável AQUI, e só aqui).
    registrar_leitura(ator, topico)

    return render(
        request, "forum/topico.html", contexto_do_topico(request, ator, topico)
    )


# ===========================================================================
# O CONTEXTO DAS TRÊS TELAS — montado uma vez, usado por quem lê e por quem erra
# ===========================================================================
# Existe uma função só porque a tela de erro de escrita é a MESMA tela de
# leitura, com o que a pessoa digitou ainda dentro do formulário. Montar o
# contexto duas vezes é como uma delas passa a esquecer um campo — e o campo
# esquecido aqui seria justamente `motivo`, o que explica a recusa.
#
# **Sem underline no nome, e isso é intencional:** desde as ferramentas do
# da escola (30/08/2026) quem devolve a tela com um erro de moderação é
# `apps/core/moderacao.py`, um módulo vizinho. Um contexto montado lá dentro
# seria a segunda expressão da mesma tela, e a primeira coisa que ela esqueceria
# é `pode_moderar` — os botões sumiriam justamente na tela que veio explicar
# por que a ação foi recusada.


def _porta_de_entrada(request) -> str:
    """O destino do "entrar para escrever": a porta central, voltando PARA CÁ.

    Duas metades, e cada uma tem seu motivo:

    * O endereço da porta vem do env (`URL_DE_ENTRADA`), lido no ponto de uso e
      com o endereço real como default (`armadilhas/097`: variável ausente não
      pode derrubar a página; aqui, no pior caso, ela leva ao lugar certo). É o
      mesmo desenho de `services/sugestoes/apps/core/views.py`, a célula de
      referência para consumir a `identidade`.
    * O `next` sai de `request.get_full_path()`, que já carrega o prefixo
      público — em produção ele é `/forum/a/duvidas`, em dev `/a/duvidas`, sem
      uma string cravada em lugar nenhum (`armadilhas/029` e `/081`).
    """
    porta = (os.environ.get("URL_DE_ENTRADA") or "").strip() or "/entrar/google"
    return f"{porta}?{urlencode({'next': request.get_full_path()})}"


def responsaveis_possiveis() -> list[Pessoa]:
    """Quem pode responder por um grupo de prática: a equipe que já entrou aqui.

    A pergunta "é da equipe?" é `email_da_equipe`, a MESMA que decide o poder de
    quem está do outro lado da tela, e é por isso que o filtro corre em Python
    e não num `email__in` montado aqui: montar a lista de novo seria a segunda
    leitura das duas variáveis do env. Só a escola chega a pedir isto, e o
    número de pessoas de um fórum de escola é de centenas.

    Quem nunca entrou no fórum não tem espelho em `Pessoa` e não aparece: peça
    à professora que entre uma vez.
    """
    return [
        pessoa
        for pessoa in Pessoa.objects.order_by("nome_exibido", "pk")
        if email_da_equipe(pessoa.email)
    ]


def contexto_da_home(ator, *, erro_admin="", digitado=None):
    """A capa do fórum. `digitado` (os campos do formulário de criar área, lidos
    por `moderacao._ler_o_formulario_da_area`) volta preenchido quando a criação
    foi recusada: perder o que a pessoa digitou é a pior forma de recusar, e
    devolver um grupo de prática com "quem enxerga" zerado criaria, no segundo
    clique, uma área aberta a todo aluno."""
    digitado = digitado or {}
    areas = areas_visiveis(ator)
    # A contagem de novidades vem de UMA consulta para todas as áreas, e é
    # pendurada em cada uma. Perguntar dentro do laço do template faria uma ida
    # ao banco por área — o tipo de lentidão que só aparece quando o fórum
    # cresce, que é quando ela é mais cara de consertar.
    quantas = novidades_por_area(ator, areas)
    for uma in areas:
        uma.novidades = quantas.get(uma.pk, 0)
    return {
        "ator": ator,
        "areas": areas,
        # O "salão vazio" é problema conhecido e declarado
        # (`DECISAO-forum-da-escola.md` §6.1): o fórum nasce sem ninguém. A tela
        # diz isso em voz alta em vez de fingir movimento.
        "vazio": not areas,
        "pode_moderar": pode_moderar(ator),
        "erro_admin": erro_admin,
        "nome_digitado": digitado.get("nome", ""),
        "descricao_digitada": digitado.get("descricao", ""),
        "visibilidade_digitada": digitado.get("visibilidade", ""),
        "grupo_digitado": digitado.get("grupo", {}),
        "responsaveis": responsaveis_possiveis() if pode_moderar(ator) else [],
    }


def contexto_da_area(
    request, ator, area, *, erro="", titulo="", texto="", erro_admin=""
):
    topicos = Topico.objects.filter(area=area).select_related("autor")
    if not pode_moderar(ator):
        # Fora do ar é fora do ar para o mundo. Para quem modera, o tópico
        # removido continua na lista, marcado — senão restaurá-lo exigiria
        # lembrar o endereço de cor.
        topicos = topicos.filter(estado=Topico.Estado.PUBLICADO)

    # A lista é materializada aqui porque cada tópico leva consigo se é
    # novidade para esta pessoa. A conta é uma consulta só (`leitura.py`), e o
    # conjunto de ids evita perguntar de novo por linha.
    novos = topicos_com_novidade(ator, area)
    lista = list(topicos)
    for topico in lista:
        topico.tem_novidade = topico.pk in novos

    return {
        "ator": ator,
        "area": area,
        "porta_de_entrada": _porta_de_entrada(request),
        "topicos": lista,
        "tem_novidade_na_area": bool(novos),
        "pode_escrever": pode_escrever(area, ator),
        # POR QUE não pode, quando não pode. A tela diz a verdade em vez de
        # simplesmente esconder o formulário: "entre" e "matricule-se" são
        # recusas diferentes, e quem lê merece saber qual das duas levou.
        "motivo": por_que_nao_escreve(area, ator),
        "erro": erro,
        "titulo_digitado": titulo,
        "texto_digitado": texto,
        "pode_moderar": pode_moderar(ator),
        "erro_admin": erro_admin,
        # Os campos do grupo só aparecem na caixa de editar de um GRUPO: é o
        # que impede salvar um grupo pela tela e vê-lo virar área de alunos.
        "responsaveis": (
            responsaveis_possiveis()
            if pode_moderar(ator) and area.visibilidade == Area.Visibilidade.TURMA
            else []
        ),
    }


def contexto_do_topico(
    request,
    ator,
    topico,
    *,
    erro="",
    texto="",
    erro_admin="",
    aviso_ia="",
    erro_ia="",
    orientacao="",
    erro_galeria="",
):
    mensagens = Mensagem.objects.filter(topico=topico).select_related("autor")
    if not pode_moderar(ator):
        mensagens = mensagens.filter(removida_em__isnull=True)

    # A ETIQUETA DE NÍVEL de cada autor, em UMA ida à rede para a página
    # inteira. A lista é materializada aqui de propósito: cada mensagem leva
    # consigo a etiqueta do autor, pelo mesmo desenho de `topico.tem_novidade`
    # na tela de área. Perguntar dentro do laço do template faria um salto de
    # rede por mensagem exibida — e a página do fórum passaria a depender da
    # latência da `gamificacao` tantas vezes quantas fossem as falas.
    #
    # Falha sempre para "sem etiqueta" (`apps/core/etiquetas.py`): gamificação
    # fora do ar ou par de tokens não provisionado deixa a página exatamente
    # como ela era antes desta linha existir.
    lista = decorar_com_etiquetas(list(mensagens.order_by("criado_em")))

    modera = pode_moderar(ator)
    return {
        "ator": ator,
        "topico": topico,
        "porta_de_entrada": _porta_de_entrada(request),
        "area": topico.area,
        "mensagens": lista,
        "pode_escrever": pode_escrever(topico.area, ator),
        "motivo": por_que_nao_escreve(topico.area, ator),
        "erro": erro,
        "texto_digitado": texto,
        "pode_moderar": modera,
        "erro_admin": erro_admin,
        # O destino possível de uma mudança de área. Só é montado para quem
        # modera: para o resto é consulta ao banco que ninguém vai olhar.
        "areas_para_mover": Area.objects.all() if modera else [],
        # O RASCUNHO DA IA (02/09/2026, `apps/core/agente.py`). Os três
        # entram juntos porque a caixa da IA é uma peça só na tela:
        # se ela aparece, o que ela avisa, e o que a pessoa digitou na
        # orientação (perder isso ao recusar seria a pior forma de
        # recusar, como no resto desta função).
        #
        # `ia_ligada` é a MESMA leitura de env que `agente.rascunhar`
        # faz no ponto de uso (`armadilhas/097`): a tela nunca oferece um
        # botão que a view vai recusar, e nunca esconde um que ela
        # aceitaria. Só é perguntada para quem modera; para o resto seria
        # leitura de env que ninguém vai olhar.
        "ia_ligada": modera and agente.ligado(),
        "aviso_ia": aviso_ia,
        "erro_ia": erro_ia,
        "orientacao_digitada": orientacao,
        # MOSTRAR NA GALERIA (`apps/core/galeria.py`). `None` para quase todo
        # mundo: a caixa só existe para o DONO do trabalho, e só na área da
        # vitrine. Quem não a vê também recebe 404 na rota do POST — esconder
        # o botão nunca foi a proteção.
        "galeria": caixa_da_galeria(ator, topico, erro_galeria),
    }


# ===========================================================================
# ESCREVER — atrás do login, e só para quem está matriculado
# ===========================================================================
# Mandato do mantenedor em 30/08/2026 (registro `20260830-021`). As três regras
# que estas duas views fazem valer, e que não se reabrem aqui:
#
#   1. aluno só escreve atrás do login;
#   2. só aluno matriculado escreve — cadastro sem matrícula LÊ e não escreve;
#   3. a proteção é o CADEADO, não fila de aprovação. Não há moderação prévia
#      nesta porta, e é por isso que o tópico nasce PUBLICADO: o estado
#      `esperando` continua existindo no modelo, para o dia em que a moderação
#      em volume for construída (lei §4.6), mas nada aqui o usa.
#
# Nenhuma das duas confere permissão por conta própria: quem responde "pode?" é
# `apps/core/permissoes.py`, sempre — e é a MESMA função que decide se o
# formulário aparece na tela. Duas expressões da mesma regra divergem no
# primeiro dia em que alguém mexer numa delas.
#
# **404 para quem não pode LER, 403 para quem não pode ESCREVER.** A diferença é
# de segurança: o 404 esconde a existência da área (num fórum de escola isso
# vaza a estrutura de turmas para quem não deveria conhecê-la); o 403 só alcança
# quem já enxerga a área, e aí esconder não protegeria ninguém — só confundiria.
#
# **`require_POST`, e não uma view que aceita GET e POST.** Escrita por GET é
# escrita que um `<img src>` de outro site consegue disparar, e que o robô do
# Google executa ao passear pela página.


def _area_para_ler(request, slug: str):
    """A área desta requisição, ou 404. Devolve `(ator, area)`."""
    ator = quem_e(request)
    area = get_object_or_404(Area, slug=slug)
    if not pode_ler(area, ator):
        raise Http404("área não encontrada")
    return ator, area


def _validar_nova_conversa(titulo: str, texto: str) -> str:
    if len(titulo) < TITULO_MINIMO:
        return ERRO_TITULO_CURTO
    if len(titulo) > TITULO_MAXIMO:
        return ERRO_TITULO_LONGO
    if len(texto) < TEXTO_MINIMO:
        return ERRO_TEXTO_VAZIO
    if len(texto) > TEXTO_MAXIMO:
        return ERRO_TEXTO_LONGO
    return ""


def _criar_nova_conversa(request, ator, area, titulo: str, texto: str):
    site_id = site_id_do_host(request.get_host())

    with transaction.atomic():
        topico = Topico.objects.create(area=area, autor=ator.pessoa, titulo=titulo)
        mensagem = Mensagem.objects.create(
            topico=topico, autor=ator.pessoa, texto=texto
        )
        mensagem.indexar_para_busca()
        eventos.topico_criado(
            site_id=site_id, topico=topico, ator_id=ator.pessoa.id_da_plataforma
        )
        eventos.mensagem_criada(
            site_id=site_id, mensagem=mensagem, ator_id=ator.pessoa.id_da_plataforma
        )
        transaction.on_commit(relay_apos_commit)

    return redirect(f"{reverse('topico', args=[topico.pk])}#m{mensagem.pk}")


@require_POST
def li_tudo(request, slug: str):
    """ "Já vi tudo": avança a marca-d'água desta área para agora.

    POST, e não GET, porque aqui a escrita é o PEDIDO da pessoa — diferente de
    abrir uma conversa, onde marcar como lida é consequência de ler. Um `<img
    src>` de outro site não pode apagar as novidades de ninguém.
    """
    ator, area = _area_para_ler(request, slug)
    if not ator.autenticado:
        # Visitante não tem marca de leitura: não há de quem guardar.
        return HttpResponseForbidden(ERRO_SEM_LEITURA)
    marcar_area_como_lida(ator, area)
    return redirect(reverse("area", args=[area.slug]))


@require_POST
def novo_topico(request, slug: str):
    """Abre uma conversa nova: o tópico e a primeira mensagem, juntos."""
    ator, area = _area_para_ler(request, slug)
    if not pode_escrever(area, ator):
        return HttpResponseForbidden(ERRO_SEM_PERMISSAO)

    titulo = (request.POST.get("titulo") or "").strip()
    texto = (request.POST.get("texto") or "").strip()

    erro = _validar_nova_conversa(titulo, texto)

    if erro:
        # Devolve a MESMA tela com o que a pessoa digitou ainda lá dentro. Esta
        # célula não assina sessão (lei §3), então não existe
        # `django.contrib.messages` para levar o recado num redirect — e perder
        # o texto de quem escreveu seria a pior forma de recusar.
        return render(
            request,
            "forum/area.html",
            contexto_da_area(
                request, ator, area, erro=erro, titulo=titulo, texto=texto
            ),
            status=400,
        )

    return _criar_nova_conversa(request, ator, area, titulo, texto)


@csrf_protect
@require_http_methods(["GET", "POST"])
def abrir_conversa(request):
    ator = quem_e(request)
    if request.method == "GET":
        if not ator.autenticado:
            return redirect(_porta_de_entrada(request))
        visiveis = areas_visiveis(ator)
        areas = [area for area in visiveis if pode_escrever(area, ator)]
        motivo = next(
            (
                por_que_nao_escreve(area, ator)
                for area in visiveis
                if por_que_nao_escreve(area, ator) == "matricula"
            ),
            "matricula",
        )
        return render(
            request,
            "forum/abrir_conversa.html",
            {
                "ator": ator,
                "areas": areas,
                "area_digitada": "",
                "titulo_digitado": "",
                "texto_digitado": "",
                "erro": "",
                "motivo": motivo,
            },
        )

    slug = (request.POST.get("area") or "").strip()
    if not ator.autenticado:
        return redirect(_porta_de_entrada(request))
    ator, area = _area_para_ler(request, slug)
    if not pode_escrever(area, ator):
        return HttpResponseForbidden(ERRO_SEM_PERMISSAO)
    titulo = (request.POST.get("titulo") or "").strip()
    texto = (request.POST.get("texto") or "").strip()
    erro = _validar_nova_conversa(titulo, texto)
    if erro:
        return render(
            request,
            "forum/abrir_conversa.html",
            {
                "ator": ator,
                "areas": [a for a in areas_visiveis(ator) if pode_escrever(a, ator)],
                "area_digitada": area.slug,
                "titulo_digitado": titulo,
                "texto_digitado": texto,
                "erro": erro,
                "motivo": "",
            },
            status=400,
        )

    return _criar_nova_conversa(request, ator, area, titulo, texto)


@require_POST
def responder(request, topico_id: int):
    """Acrescenta uma fala a uma conversa que já existe."""
    ator = quem_e(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"),
        pk=topico_id,
        estado=Topico.Estado.PUBLICADO,
    )
    if not pode_ler(topico.area, ator):
        raise Http404("tópico não encontrado")
    if not pode_escrever(topico.area, ator):
        return HttpResponseForbidden(ERRO_SEM_PERMISSAO)
    if topico.trancado:
        return HttpResponseForbidden(ERRO_TOPICO_TRANCADO)

    texto = (request.POST.get("texto") or "").strip()
    erro = ""
    if len(texto) < TEXTO_MINIMO:
        erro = ERRO_TEXTO_VAZIO
    elif len(texto) > TEXTO_MAXIMO:
        erro = ERRO_TEXTO_LONGO

    if erro:
        return render(
            request,
            "forum/topico.html",
            contexto_do_topico(request, ator, topico, erro=erro, texto=texto),
            status=400,
        )

    site_id = site_id_do_host(request.get_host())

    with transaction.atomic():
        mensagem = Mensagem.objects.create(
            topico=topico, autor=ator.pessoa, texto=texto
        )
        mensagem.indexar_para_busca()
        eventos.mensagem_criada(
            site_id=site_id, mensagem=mensagem, ator_id=ator.pessoa.id_da_plataforma
        )
        transaction.on_commit(relay_apos_commit)
        # A marca de leitura compara com ISTO (`MarcaDeLeitura`), nunca com a
        # data de cada mensagem. Sem este avanço, uma conversa que acabou de
        # receber resposta continuaria parecendo lida para a turma inteira.
        Topico.objects.filter(pk=topico.pk).update(ultima_atividade_em=timezone.now())

    return redirect(f"{reverse('topico', args=[topico.pk])}#m{mensagem.pk}")


# ===========================================================================
# A COMUNIDADE: o que o membro de um grupo de prática pode fazer agora
# ===========================================================================
# TAR-824, 27/09/2026. A página responde uma pergunta só, "o que posso fazer
# agora?", e tem quatro estados, todos com texto: sem login, sem matrícula
# (inclusive a `alunos` fora do ar, que chega aqui como "não é aluno"), sem
# grupo e com grupo. Nenhum deles depende da `gamificacao`: ela fora do ar não
# tira nada desta página.
#
# QUEM É "MEU GRUPO" sai de `areas_visiveis`, a mesma regra de todas as telas.
# Para o aluno, ler o grupo já É ter vínculo ativo. Para a equipe, que lê todo
# grupo, "meu" é aquele pelo qual ela responde.

# O endereço do desafio mora na célula `cursos`, fora do prefixo `/forum`, e
# por isso é caminho do SITE e não `reverse()` deste urlconf.
DESAFIO_DO_CURSO = "/cursos/{}/"
# O bastante para uma tarde de ajuda. A lista existe para ser atendida, e a
# mais antiga vem primeiro, então o corte nunca esconde quem espera há mais
# tempo.
QUEM_DEPENDE_DE_VOCE_MAXIMO = 20


def endereco_do_desafio(grupo: Area) -> str:
    """O link do desafio atual de um grupo: o curso dele, na célula `cursos`."""
    return DESAFIO_DO_CURSO.format(quote(grupo.curso_id, safe=""))


def ha_quanto_tempo(momento, agora) -> str:
    """A espera em português de gente, sem depender do idioma do Django.

    O filtro `timesince` responderia no idioma configurado, e esta célula não
    configura nenhum: a tela diria "3 days" para um aluno brasileiro.
    """
    horas = max(0, int((agora - momento).total_seconds())) // 3600
    if horas < 1:
        return "há menos de uma hora"
    if horas < 24:
        return f"há {horas} hora{'s' if horas > 1 else ''}"
    dias = horas // 24
    return f"há {dias} dia{'s' if dias > 1 else ''}"


def grupos_de(ator) -> list[Area]:
    """Os grupos de prática desta pessoa, na ordem da tela."""
    return [
        area
        for area in areas_visiveis(ator)
        if area.visibilidade == Area.Visibilidade.TURMA
        and area.ativa
        and (not ator.eh_equipe or area.responsavel_id == ator.pessoa.pk)
    ]


def duvidas_abertas(grupos):
    """As dúvidas destes grupos que esperam resposta, a mais antiga primeiro.

    Esperar é estar publicada, destrancada e sem resposta aceita: uma conversa
    trancada não recebe resposta, então ninguém espera por ela. A mesma
    pergunta serve ao membro ("quem depende de você") e à equipe ("o que
    espera em cada grupo"); duas cópias dela divergiriam na primeira mudança.
    """
    return (
        Topico.objects.filter(
            area__in=grupos,
            estado=Topico.Estado.PUBLICADO,
            trancado=False,
            resposta_aceita__isnull=True,
        )
        .select_related("area", "autor")
        .order_by("criado_em", "pk")
    )


def contexto_da_comunidade(request, ator) -> dict:
    contexto = {
        "ator": ator,
        "porta_de_entrada": _porta_de_entrada(request),
        "estado": "",
        "grupos": [],
        "dependem": [],
    }
    if not ator.autenticado:
        contexto["estado"] = "entrar"
        return contexto
    if not (ator.eh_aluno or ator.eh_equipe):
        contexto["estado"] = "matricula"
        return contexto

    grupos = grupos_de(ator)
    if not grupos:
        contexto["estado"] = "sem_grupo"
        return contexto

    for grupo in grupos:
        grupo.desafio = endereco_do_desafio(grupo)

    # QUEM DEPENDE DE VOCÊ: as dúvidas abertas do grupo que são de outra
    # pessoa, porque a sua própria você não responde.
    agora = timezone.now()
    dependem = list(
        duvidas_abertas(grupos).exclude(autor=ator.pessoa)[:QUEM_DEPENDE_DE_VOCE_MAXIMO]
    )
    for topico in dependem:
        topico.espera = ha_quanto_tempo(topico.criado_em, agora)

    contexto.update(estado="com_grupo", grupos=grupos, dependem=dependem)
    return contexto


@require_GET
def comunidade(request):
    """A página Comunidade do membro. Nunca 404: cada estado tem seu texto."""
    ator = quem_e(request)
    return render(
        request, "forum/comunidade.html", contexto_da_comunidade(request, ator)
    )


# ===========================================================================
# A COMUNIDADE VISTA PELA EQUIPE: o que espera em cada grupo, e quem responde
# ===========================================================================
# TAR-827, 27/09/2026. A especificação da Comunidade pede que a equipe
# identifique filas, atrasos e limites de capacidade. Esta página mostra, por
# grupo de prática ativo: o responsável, as vagas ocupadas, as dúvidas abertas
# e quem entrou e ainda não escreveu. Toda espera aponta para o responsável do
# grupo, e o grupo sem responsável diz isso em voz alta.
#
# As filas das outras células (laudos em `cursos`, validação em
# `conquistas`) entram só como link: cada célula responde pelos próprios
# números, e copiá-los aqui criaria uma segunda verdade atrasada.
PLANTAO_DE_LAUDOS = "/cursos/plantao"
FILA_DE_VALIDACAO = "/conquistas/interno"
SEM_NOME_DE_EXIBICAO = "pessoa da escola sem nome de exibição"
ULTIMAS_ACOES = 10


def contexto_da_comunidade_da_equipe(ator) -> dict:
    """Os grupos ativos com as esperas penduradas, em cinco consultas no total.

    Uma consulta para os grupos, uma para as dúvidas abertas de todos eles, uma
    para os vínculos ativos já sabendo se a pessoa escreveu no grupo e duas
    para o rastro da moderação. Perguntar por grupo dentro do laço faria uma
    ida ao banco por grupo.
    """
    grupos = list(
        Area.objects.filter(
            visibilidade=Area.Visibilidade.TURMA, ativa=True
        ).select_related("responsavel")
    )
    por_pk = {grupo.pk: grupo for grupo in grupos}
    for grupo in grupos:
        grupo.quem_responde = (
            (grupo.responsavel.nome_exibido or SEM_NOME_DE_EXIBICAO)
            if grupo.responsavel
            else ""
        )
        grupo.membros_ativos = 0
        grupo.duvidas = []
        grupo.acolhimento = []

    agora = timezone.now()
    for topico in duvidas_abertas(grupos):
        topico.espera = ha_quanto_tempo(topico.criado_em, agora)
        por_pk[topico.area_id].duvidas.append(topico)

    # ACOLHIMENTO PENDENTE: quem tem vínculo ativo e nunca escreveu uma
    # mensagem em conversa nenhuma do grupo, quem entrou antes primeiro.
    ja_escreveu = Mensagem.objects.filter(
        topico__area=OuterRef("grupo"), autor=OuterRef("pessoa")
    )
    vinculos = (
        MembroDoGrupo.objects.filter(grupo__in=grupos, ate__isnull=True)
        .annotate(ja_escreveu=Exists(ja_escreveu))
        .select_related("pessoa")
        .order_by("desde", "pk")
    )
    for vinculo in vinculos:
        grupo = por_pk[vinculo.grupo_id]
        grupo.membros_ativos += 1
        if not vinculo.ja_escreveu:
            vinculo.espera = ha_quanto_tempo(vinculo.desde, agora)
            grupo.acolhimento.append(vinculo)

    for grupo in grupos:
        # Vaga zero é o lado fechado (`Area.vagas`): o grupo não recebe ninguém.
        grupo.sem_vaga = grupo.membros_ativos >= grupo.vagas
        grupo.rastro = []

    # O RASTRO DA MODERAÇÃO (TAR-847): as últimas ações de cada grupo, quem fez
    # e por quê. Duas consultas, e não uma por grupo: uma pelas linhas em que o
    # grupo é a origem e outra pelas em que é o destino (mover, trocar de
    # grupo), cada uma já cortada em dez por grupo dentro do banco.
    for campo in ("area", "area_destino"):
        linhas = (
            RegistroDeModeracao.objects.filter(**{f"{campo}__in": grupos})
            .annotate(
                posicao=Window(
                    RowNumber(),
                    partition_by=[F(campo)],
                    order_by=[F("quando").desc(), F("pk").desc()],
                )
            )
            .filter(posicao__lte=ULTIMAS_ACOES)
            .select_related("ator")
        )
        for linha in linhas:
            por_pk[getattr(linha, f"{campo}_id")].rastro.append(linha)
    for grupo in grupos:
        grupo.rastro.sort(key=lambda linha: (linha.quando, linha.pk), reverse=True)
        del grupo.rastro[ULTIMAS_ACOES:]

    return {
        "ator": ator,
        "grupos": grupos,
        "plantao_de_laudos": PLANTAO_DE_LAUDOS,
        "fila_de_validacao": FILA_DE_VALIDACAO,
    }


@require_GET
def comunidade_da_equipe(request):
    """A Comunidade vista pela escola. 404 para quem não modera, nunca 403:
    o 403 confirmaria que a página existe."""
    ator = quem_e(request)
    if not pode_moderar(ator):
        raise Http404("página não encontrada")
    return render(
        request,
        "forum/comunidade_da_equipe.html",
        contexto_da_comunidade_da_equipe(ator),
    )
