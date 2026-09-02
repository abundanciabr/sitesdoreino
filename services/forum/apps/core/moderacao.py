"""AS FERRAMENTAS DO ADMINISTRADOR — editar, tirar do ar, deixar privado.

Mandato do mantenedor em 30/08/2026, com as palavras dele: *"Crie as opções
(que devem aparecer apenas para o Admin) de editar, deletar, deixar privado, e
etc; tudo no fórum."* É a condição 6 da lei do fórum
(`DECISAO-forum-da-escola.md` §4.6), a que fala em moderação de verdade.

As cinco regras que este arquivo inteiro obedece, e que não se reabrem aqui:

1. **NADA É APAGADO DE VERDADE.** "Deletar" nesta casa é tirar do ar: o tópico
   vira `estado=removido`, a mensagem ganha `removida_em`, a área perde o
   `ativa`. A linha continua no banco. O público desta escola é
   majoritariamente menor de idade, e apagar destrói exatamente o contexto que
   uma denúncia precisa — justamente quando ele importa. Não existe `DELETE`
   neste módulo, e a ausência é a decisão.

2. **404 para quem não modera, nunca 403.** Um 403 confirmaria que a porta
   existe. Aluno e visitante não devem nem descobrir que estas rotas foram
   construídas. É o mesmo desenho do resto do fórum, um degrau acima.

3. **Quem responde "pode?" é `apps/core/permissoes.py`**, sempre, e é a MESMA
   função que decide se o botão aparece na tela. Esconder o botão nunca é a
   proteção; a proteção é o 404 daqui.

4. **Tudo por POST, com CSRF.** Ação de moderação por GET é ação que um
   `<img src>` de outro site dispara e que o robô do Google executa ao passear
   pela página. Um `<a href>` "tirar do ar" apagaria o fórum sozinho na
   primeira visita de um leitor de links.

5. **Toda recusa devolve a MESMA tela, com a frase do que houve.** Esta célula
   não assina sessão (lei §3), então não existe `django.contrib.messages` para
   levar recado num redirect. A tela recusada é a tela de novo, com `erro_admin`
   preenchido e o que foi digitado ainda dentro do formulário.
"""

from __future__ import annotations

import json

from django.db import IntegrityError, transaction
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.forum import eventos
from apps.forum.models import Area, Mensagem, Topico
from apps.forum.tasks import relay_apos_commit

from . import agente
from .menu import site_id_do_host
from .permissoes import pode_moderar
from .sessao import email_da_equipe, quem_e
from .views import (
    TITULO_MAXIMO,
    TITULO_MINIMO,
    contexto_da_area,
    contexto_da_home,
    contexto_do_topico,
)

# ---------------------------------------------------------------------------
# O QUE A TELA DIZ QUANDO RECUSA — em português de gente, num lugar só
# ---------------------------------------------------------------------------
# Sem travessão: texto publicado deste projeto sai sem ele (decisão do
# mantenedor em 30/08/2026, portão `ci/travessao.py`).
NOME_MAXIMO = 100

ERRO_NOME_VAZIO = "Toda área precisa de um nome."
ERRO_NOME_LONGO = f"O nome da área passou de {NOME_MAXIMO} letras."
ERRO_NOME_SEM_LETRA = (
    "Não consegui montar um endereço com esse nome. Use pelo menos uma letra "
    "ou um número."
)
ERRO_AREA_REPETIDA = "Já existe uma área com esse nome (ou com um endereço igual)."
ERRO_VISIBILIDADE = "Escolha quem enxerga a área."
ERRO_QUEM_ESCREVE = "Escolha quem escreve na área."
ERRO_PUBLICA_SO_A_ESCOLA = (
    "Área aberta ao mundo é só a escola falando. Ou deixe a área privada, ou "
    "escolha 'só a escola' em quem escreve. É a regra que protege os alunos "
    "menores de idade: o que estranho lê sem entrar não leva mensagem de aluno."
)
ERRO_TITULO_CURTO_ADMIN = f"O título precisa ter pelo menos {TITULO_MINIMO} letras."
ERRO_TITULO_LONGO_ADMIN = f"O título passou de {TITULO_MAXIMO} letras."
ERRO_AREA_INEXISTENTE = "Essa área não existe mais. Recarregue a página."
ERRO_MENSAGEM_VAZIA = (
    "A mensagem não pode ficar vazia. Para sumir com ela, use 'tirar do ar'."
)
ERRO_MENSAGEM_DE_OUTRO_TOPICO = "Essa mensagem não é desta conversa."
ERRO_MENSAGEM_FORA_DO_AR = (
    "Não dá para apontar como resposta certa uma mensagem que está fora do ar."
)
ERRO_ACAO_DESCONHECIDA = (
    "Não entendi o que você pediu. Recarregue a página e tente de novo."
)
ERRO_BANCO_RECUSOU = (
    "O banco recusou essa combinação. Ela quebra uma regra que protege os "
    "alunos, então nada foi mudado."
)

# O RASCUNHO DA IA (02/09/2026). As duas recusas existem porque o rascunho nasce
# dentro da caixa de responder, e nas duas situações abaixo essa caixa não está
# na tela: gerar texto para uma caixa que não existe seria trabalho pago à
# Anthropic e jogado fora, sem nada aparecer para quem clicou.
ERRO_IA_TRANCADO = (
    "Esta conversa está trancada, então não há caixa de resposta para receber o "
    "rascunho. Destranque ali em cima e peça de novo."
)
ERRO_IA_FORA_DO_AR = (
    "Esta conversa está fora do ar, então ninguém pode responder nela. Devolva "
    "ao ar ali em cima e peça de novo."
)

# Os avisos que acompanham um rascunho PRONTO. Não são erro: são o que a pessoa
# precisa saber antes de apertar Responder.
AVISO_IA_PRONTO = (
    "Rascunho da IA na caixa de resposta aqui embaixo. Leia inteiro antes de "
    "publicar: ela não sabe preço, prazo, turma nem reembolso, e o texto sai "
    "com o seu nome em cima."
)
AVISO_IA_CORTADO = (
    "A resposta veio no limite de tamanho e terminou no meio. Complete o final "
    "antes de publicar."
)
AVISO_IA_TRAVESSAO = (
    "A IA usou risca longa no texto, e este site publica sem ela. Reescreva "
    "essas frases com vírgula, parênteses, dois-pontos ou aspas, do jeito que "
    "soar certo em cada uma."
)

# As duas visibilidades que o fórum sabe conferir hoje. `turma` existe no
# modelo e continua fora daqui de propósito: enquanto o fórum não souber
# perguntar à `alunos` se alguém está NUM curso, `pode_ler` fecha para todo
# mundo (`permissoes.py`), e oferecer o botão seria oferecer a criação de uma
# área que ninguém abre.
VISIBILIDADES_OFERECIDAS = {Area.Visibilidade.PUBLICA, Area.Visibilidade.ALUNOS}
QUEM_ESCREVE_OFERECIDO = {
    Area.QuemEscreve.EQUIPE,
    Area.QuemEscreve.ALUNO,
    Area.QuemEscreve.CADASTRADO,
}


def _so_quem_modera(request):
    """O Ator desta requisição, se ele modera. Se não, a porta não existe.

    Regra 2 do cabeçalho: 404, nunca 403. E vale para aluno, para professor e
    para visitante do mesmo jeito, porque `pode_moderar` é uma pergunta só.
    """
    ator = quem_e(request)
    if not pode_moderar(ator):
        raise Http404("página não encontrada")
    return ator


def _salvar_com_a_rede_do_banco(objeto) -> str:
    """Grava, e transforma a recusa do PostgreSQL em frase de gente.

    As restrições do modelo (`pagina_publica_so_a_escola_fala`,
    `area_de_turma_exige_curso`, as duas de autoria) são a última linha de
    defesa, e ela existe justamente para o caso de a conferência daqui deixar
    passar uma combinação nova. Sem este `try`, esse caso viraria HTTP 500 numa
    tela do mantenedor; com ele, vira um recado.

    **O `atomic` não é enfeite:** `IntegrityError` capturado sem savepoint
    envenena a transação inteira e o próximo comando estoura longe da causa
    (`armadilhas/027`).
    """
    try:
        with transaction.atomic():
            objeto.save()
    except IntegrityError:
        return ERRO_BANCO_RECUSOU
    return ""


# ===========================================================================
# ÁREA — criar, editar, deixar privada ou aberta, arquivar
# ===========================================================================


def _ler_o_formulario_da_area(request) -> tuple[dict, str]:
    """Os quatro campos da área, conferidos juntos. Devolve (campos, erro)."""
    campos = {
        "nome": (request.POST.get("nome") or "").strip(),
        "descricao": (request.POST.get("descricao") or "").strip(),
        "visibilidade": (request.POST.get("visibilidade") or "").strip(),
        "quem_escreve": (request.POST.get("quem_escreve") or "").strip(),
    }

    if not campos["nome"]:
        return campos, ERRO_NOME_VAZIO
    if len(campos["nome"]) > NOME_MAXIMO:
        return campos, ERRO_NOME_LONGO
    if campos["visibilidade"] not in VISIBILIDADES_OFERECIDAS:
        return campos, ERRO_VISIBILIDADE
    if campos["quem_escreve"] not in QUEM_ESCREVE_OFERECIDO:
        return campos, ERRO_QUEM_ESCREVE
    # EM PÁGINA PÚBLICA, SÓ A ESCOLA FALA. A conferência é aqui para o
    # mantenedor receber uma frase em vez de um erro de banco; a garantia de
    # verdade continua sendo a restrição do PostgreSQL, que nem um `update()`
    # fura (`armadilhas/023`).
    if (
        campos["visibilidade"] == Area.Visibilidade.PUBLICA
        and campos["quem_escreve"] != Area.QuemEscreve.EQUIPE
    ):
        return campos, ERRO_PUBLICA_SO_A_ESCOLA
    return campos, ""


@require_POST
def criar_area(request):
    """Uma área nova, a partir da capa do fórum.

    **O endereço nasce do nome e nunca mais muda** (`slugify`). Endereço que
    acompanha o nome parece gentileza e é armadilha: cada renomeação quebraria
    todos os links já compartilhados, e um fórum existe para ser linkado.
    """
    ator = _so_quem_modera(request)
    campos, erro = _ler_o_formulario_da_area(request)

    slug = slugify(campos["nome"])[:60] if not erro else ""
    if not erro and not slug:
        erro = ERRO_NOME_SEM_LETRA
    # Repetido é repetido pelos DOIS lados: o endereço (que o banco já recusaria,
    # com um erro que ninguém entende) e o nome visível. Duas áreas chamadas
    # "Dúvidas gerais" em endereços diferentes não quebram nada e são pior que
    # um erro: ninguém descobre em qual das duas o aluno escreveu.
    if not erro and (
        Area.objects.filter(slug=slug).exists()
        or Area.objects.filter(nome__iexact=campos["nome"]).exists()
    ):
        erro = ERRO_AREA_REPETIDA

    if erro:
        return render(
            request,
            "forum/home.html",
            contexto_da_home(
                ator,
                erro_admin=erro,
                nome=campos["nome"],
                descricao=campos["descricao"],
            ),
            status=400,
        )

    # A área nova entra no fim da lista. `ordem` é dado de exibição, e o passo
    # de 10 deixa espaço para intercalar sem renumerar tudo.
    ultima = Area.objects.order_by("-ordem").values_list("ordem", flat=True).first()
    area = Area(
        slug=slug,
        nome=campos["nome"],
        descricao=campos["descricao"],
        visibilidade=campos["visibilidade"],
        quem_escreve=campos["quem_escreve"],
        ordem=(ultima or 0) + 10,
    )
    erro = _salvar_com_a_rede_do_banco(area)
    if erro:
        return render(
            request,
            "forum/home.html",
            contexto_da_home(
                ator,
                erro_admin=erro,
                nome=campos["nome"],
                descricao=campos["descricao"],
            ),
            status=400,
        )
    return redirect(reverse("area", args=[area.slug]))


@require_POST
def moderar_area(request, slug: str):
    """Editar, deixar privada ou aberta, arquivar e reabrir uma área."""
    ator = _so_quem_modera(request)
    area = get_object_or_404(Area, slug=slug)
    acao = (request.POST.get("acao") or "").strip()

    erro = ""
    if acao == "salvar":
        campos, erro = _ler_o_formulario_da_area(request)
        if not erro:
            area.nome = campos["nome"]
            area.descricao = campos["descricao"]
            area.visibilidade = campos["visibilidade"]
            area.quem_escreve = campos["quem_escreve"]
            erro = _salvar_com_a_rede_do_banco(area)
    elif acao in ("arquivar", "reabrir"):
        # O "deletar" honesto: a área some da lista de todo mundo e continua
        # aparecendo para quem pode reabri-la, marcada (ver `pode_ler`).
        area.ativa = acao == "reabrir"
        erro = _salvar_com_a_rede_do_banco(area)
    else:
        erro = ERRO_ACAO_DESCONHECIDA

    if erro:
        area.refresh_from_db()
        return render(
            request,
            "forum/area.html",
            contexto_da_area(request, ator, area, erro_admin=erro),
            status=400,
        )
    return redirect(reverse("area", args=[area.slug]))


# ===========================================================================
# TÓPICO — editar, mover, fixar, trancar, tirar do ar, apontar a resposta certa
# ===========================================================================


def _de_volta_para(request, topico) -> str:
    """Onde a pessoa estava quando apertou o botão.

    O destino sai de uma LISTA FECHADA de dois valores, e nunca de um endereço
    que veio no formulário: destino vindo de fora é redirecionamento aberto, e
    um site de fora poderia usar o fórum como trampolim para uma página falsa
    de login.
    """
    if (request.POST.get("de_onde") or "") == "area":
        return reverse("area", args=[topico.area.slug])
    return reverse("topico", args=[topico.pk])


# AS DUAS AÇÕES QUE O DONO DA PERGUNTA TAMBÉM FAZ, e a lista é fechada.
#
# Decisão D da Sessão B (30/08/2026, com o mantenedor presente): *a marca
# "resolveu" é do AUTOR da pergunta e vale a recompensa cheia na hora, sem
# confirmação de adulto*. Até 01/09/2026 essa decisão existia só no contrato do
# evento — no fórum, apontar a resposta certa era ação de moderador, e o dono da
# dúvida não conseguia fazer o gesto que a lei diz ser dele.
#
# É uma LISTA e não um `if` solto porque o poder que se abre aqui é exatamente
# este e mais nada: o autor NÃO fixa, NÃO tranca, NÃO move de área e NÃO tira do
# ar. Um `elif` embutido no meio das seis ações abriria a porta por descuido no
# dia em que uma sétima chegasse.
ACOES_DO_AUTOR_DA_PERGUNTA = frozenset({"aceitar", "desmarcar"})


@require_POST
def moderar_topico(request, topico_id: int):
    """As seis ações sobre uma conversa inteira, e duas que o autor também faz."""
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"), pk=topico_id
    )
    acao = (request.POST.get("acao") or "").strip()
    ator = quem_e(request)
    dono_da_pergunta = (
        ator.pessoa is not None and ator.pessoa.id_da_plataforma == topico.autor_id
    )
    if not (dono_da_pergunta and acao in ACOES_DO_AUTOR_DA_PERGUNTA):
        # A porta de sempre, para todo o resto: 404 e não 403 (regra 2 do
        # cabeçalho deste arquivo).
        ator = _so_quem_modera(request)

    erro = ""
    if acao == "salvar":
        titulo = (request.POST.get("titulo") or "").strip()
        area_id = (request.POST.get("area_id") or "").strip()
        destino = Area.objects.filter(pk=area_id).first() if area_id else topico.area
        if len(titulo) < TITULO_MINIMO:
            erro = ERRO_TITULO_CURTO_ADMIN
        elif len(titulo) > TITULO_MAXIMO:
            erro = ERRO_TITULO_LONGO_ADMIN
        elif destino is None:
            erro = ERRO_AREA_INEXISTENTE
        else:
            topico.titulo = titulo
            # MOVER (lei §4.6). A conversa inteira vai junto: as mensagens
            # pendem do tópico, não da área.
            topico.area = destino
            erro = _salvar_com_a_rede_do_banco(topico)
    elif acao in ("fixar", "desafixar"):
        topico.fixado = acao == "fixar"
        erro = _salvar_com_a_rede_do_banco(topico)
    elif acao in ("trancar", "destrancar"):
        # Trancado esconde a caixa de responder E faz a view de resposta
        # recusar. As duas coisas, sempre: esconder o formulário nunca foi a
        # proteção.
        topico.trancado = acao == "trancar"
        erro = _salvar_com_a_rede_do_banco(topico)
    elif acao in ("tirar_do_ar", "restaurar"):
        topico.estado = (
            Topico.Estado.REMOVIDO if acao == "tirar_do_ar" else Topico.Estado.PUBLICADO
        )
        erro = _salvar_com_a_rede_do_banco(topico)
    elif acao == "aceitar":
        erro = _apontar_a_resposta_certa(request, topico)
    elif acao == "desmarcar":
        topico.resposta_aceita = None
        erro = _salvar_com_a_rede_do_banco(topico)
    else:
        erro = ERRO_ACAO_DESCONHECIDA

    if erro:
        topico.refresh_from_db()
        return render(
            request,
            "forum/topico.html",
            contexto_do_topico(request, ator, topico, erro_admin=erro),
            status=400,
        )
    return redirect(_de_volta_para(request, topico))


def _apontar_a_resposta_certa(request, topico) -> str:
    """O selo de "resolvido" (lei §5): esta mensagem respondeu a dúvida.

    É o que transforma o fórum em patrimônio da escola em vez de arquivo morto:
    quem chega depois lê a pergunta e vê, marcada, a resposta que resolveu.
    """
    mensagem = Mensagem.objects.filter(pk=request.POST.get("mensagem_id") or 0).first()
    if mensagem is None or mensagem.topico_id != topico.pk:
        return ERRO_MENSAGEM_DE_OUTRO_TOPICO
    if mensagem.removida_em is not None:
        return ERRO_MENSAGEM_FORA_DO_AR

    site_id = site_id_do_host(request.get_host())
    ator = quem_e(request)

    with transaction.atomic():
        topico.resposta_aceita = mensagem
        erro = _salvar_com_a_rede_do_banco(topico)
        if erro:
            return erro
        # O FATO MAIS VALIOSO DO SISTEMA (decisão 4 da Sessão A: validação humana
        # vale ~10x consumo). Os dois ids são diferentes de propósito — quem
        # marcou vai no envelope, quem escreveu vai no `data` e é quem recebe.
        eventos.resposta_aceita(
            site_id=site_id,
            topico=topico,
            mensagem=mensagem,
            ator_id=ator.pessoa.id_da_plataforma if ator.pessoa else "",
            marcada_por=_papel_de_quem_marcou(ator, topico),
        )
        transaction.on_commit(relay_apos_commit)
    return ""


def _papel_de_quem_marcou(ator, topico) -> str:
    """COM QUE AUTORIDADE a marca foi feita — a escadinha da decisão 5 da Sessão A.

    É o PAPEL, nunca o id (o id de quem marcou já vai no `ator_id` do envelope), e
    o vocabulário é fechado pelo contrato: `autor`, `monitor`, `professor`.

    Ele existe porque a decisão D da Sessão B tirou o adulto do caminho do maior
    prêmio do sistema: sem este campo, o motor não distingue a marca de um colega
    da marca de alguém da equipe, e a detecção de anéis de reciprocidade fica
    cega. Quem é da equipe entra como `professor`; o dono da pergunta, como
    `autor`; qualquer outro caminho é `monitor`.
    """
    if ator.pessoa and ator.pessoa.id_da_plataforma == topico.autor_id:
        return "autor"
    if ator.eh_equipe:
        return "professor"
    return "monitor"


# ===========================================================================
# MENSAGEM — editar o texto, tirar do ar, devolver ao ar
# ===========================================================================


@require_POST
def moderar_mensagem(request, mensagem_id: int):
    """As três ações sobre uma fala."""
    ator = _so_quem_modera(request)
    mensagem = get_object_or_404(
        Mensagem.objects.select_related("topico", "topico__area", "autor"),
        pk=mensagem_id,
    )
    topico = mensagem.topico
    acao = (request.POST.get("acao") or "").strip()

    erro = ""
    if acao == "salvar":
        texto = (request.POST.get("texto") or "").strip()
        if not texto:
            erro = ERRO_MENSAGEM_VAZIA
        else:
            mensagem.texto = texto
            # A tela mostra "editada" a partir DESTE campo. Editar em silêncio
            # a fala de outra pessoa é o que um fórum não pode fazer: quem
            # respondeu confiando no que estava escrito merece ver que mudou.
            mensagem.editado_em = timezone.now()
            erro = _salvar_com_a_rede_do_banco(mensagem)
            if not erro:
                # A busca é calculada na ESCRITA, nunca na consulta (lei §4.4).
                # Sem esta linha o texto novo ficaria invisível para a busca e
                # o antigo continuaria aparecendo nela, sem erro em lugar nenhum.
                mensagem.indexar_para_busca()
    elif acao in ("tirar_do_ar", "restaurar"):
        site_id = site_id_do_host(request.get_host())
        with transaction.atomic():
            mensagem.removida_em = timezone.now() if acao == "tirar_do_ar" else None
            erro = _salvar_com_a_rede_do_banco(mensagem)
            if not erro and mensagem.removida_em is not None:
                # Uma mensagem fora do ar não pode continuar sendo a resposta
                # premiada da conversa: o selo apontaria para o vazio.
                Topico.objects.filter(pk=topico.pk, resposta_aceita=mensagem).update(
                    resposta_aceita=None
                )
                # O EVENTO DO ESTORNO. Sem ele, o ponto pago por uma mensagem que
                # a escola depois removeu ficaria no placar de quem a escreveu, e
                # a quarentena do motor de XP — que existe para exatamente esta
                # janela — não teria o que desfazer.
                eventos.mensagem_removida(
                    site_id=site_id,
                    mensagem=mensagem,
                    ator_id=(
                        ator.pessoa.id_da_plataforma if ator and ator.pessoa else ""
                    ),
                )
                transaction.on_commit(relay_apos_commit)
    else:
        erro = ERRO_ACAO_DESCONHECIDA

    if erro:
        mensagem.refresh_from_db()
        topico.refresh_from_db()
        return render(
            request,
            "forum/topico.html",
            contexto_do_topico(request, ator, topico, erro_admin=erro),
            status=400,
        )
    return redirect(f"{reverse('topico', args=[topico.pk])}#m{mensagem.pk}")


# ===========================================================================
# O RASCUNHO DA IA — a máquina escreve, a pessoa publica
# ===========================================================================
# Mandato do mantenedor em 02/09/2026: *"o Admin clica na dúvida que quer
# responder em um botão 'gerar resposta', e com um form opcional de campo único
# para enviar mais detalhes de como o agente deverá responder"*.
#
# A view mora AQUI, junto das outras ferramentas da escola, por uma razão que
# não é arrumação: é neste arquivo que vive `_so_quem_modera`, e é dele que sai
# o 404 (nunca 403) para quem não é da escola. Uma porta de IA com regra própria
# de permissão seria a segunda expressão da mesma regra, e a primeira a divergir.
# Quem fala com a Anthropic é `apps/core/agente.py`; aqui fica só o que a tela
# faz com o que voltou.
#
# **Esta view não escreve nada no banco**, e a ausência é a decisão. Ela devolve
# a mesma conversa com o texto dentro da caixa de responder. Publicar continua
# sendo um segundo clique, de uma pessoa, na rota de sempre.


def _falas_para_a_ia(topico: Topico) -> list[tuple[str, str]]:
    """A conversa em pares (quem, texto), SEM nome de ninguém.

    Duas escolhas:

    * **Mensagem fora do ar não viaja.** O que a escola tirou do ar está tirado
      do ar, inclusive para a máquina. Um rascunho construído em cima de uma
      fala removida devolveria pela porta da frente o que a moderação tinha
      acabado de tirar.
    * **O rótulo é `Escola` para fala da instituição E para fala de quem é da
      equipe.** `publicado_pela_escola` sozinho pegaria só as mensagens
      semeadas: a resposta que o próprio administrador escreveu ontem tem autor
      de pessoa, e chegaria à IA como se fosse dúvida de aluno.
    """
    falas: list[tuple[str, str]] = []
    for mensagem in (
        Mensagem.objects.filter(topico=topico, removida_em__isnull=True)
        .select_related("autor")
        .order_by("criado_em")
    ):
        da_escola = mensagem.publicado_pela_escola or (
            mensagem.autor is not None and email_da_equipe(mensagem.autor.email)
        )
        falas.append(("Escola" if da_escola else "Aluno", mensagem.texto))
    return falas


def _o_que_avisar(rascunho: agente.Rascunho) -> str:
    """A linha que aparece com o rascunho pronto. Nunca vazia.

    O aviso de sempre vem primeiro; os dois condicionais só aparecem quando têm
    o que dizer. Juntar tudo numa frase só faria a advertência que importa (a IA
    não sabe preço nem prazo) sumir nos dias em que não houvesse travessão
    nenhum, e é justamente nesses dias que o texto parece confiável.
    """
    partes = [AVISO_IA_PRONTO]
    if rascunho.cortado:
        partes.append(AVISO_IA_CORTADO)
    if agente.travessoes_em(rascunho.texto):
        partes.append(AVISO_IA_TRAVESSAO)
    return " ".join(partes)


@require_POST
def gerar_resposta(request, topico_id: int):
    """Pede à IA o rascunho de uma resposta para esta conversa.

    `require_POST` pelo mesmo motivo das outras quatro rotas daqui, um degrau
    mais caro: gerar por GET seria uma chamada PAGA que o robô do Google
    dispararia sozinho ao passear pela página.
    """
    ator = _so_quem_modera(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"), pk=topico_id
    )
    # Cortada no tamanho em vez de recusada: quem escreveu demais na caixinha
    # quis dizer alguma coisa, e devolver a tela com um erro por causa disso
    # seria atrito puro. O teto existe para a chamada não carregar um livro.
    orientacao = (request.POST.get("orientacao") or "").strip()[
        : agente.TETO_DA_ORIENTACAO
    ]

    recusa = ""
    if topico.estado != Topico.Estado.PUBLICADO:
        recusa = ERRO_IA_FORA_DO_AR
    elif topico.trancado:
        recusa = ERRO_IA_TRANCADO
    if recusa:
        return render(
            request,
            "forum/topico.html",
            contexto_do_topico(
                request, ator, topico, erro_ia=recusa, orientacao=orientacao
            ),
            status=400,
        )

    try:
        rascunho = agente.rascunhar(
            area_nome=topico.area.nome,
            titulo=topico.titulo,
            falas=_falas_para_a_ia(topico),
            orientacao=orientacao,
        )
    except agente.AgenteIndisponivel as erro:
        # A conversa volta inteira, com a frase do que houve e a orientação
        # ainda na caixinha. 503 e não 400: quem falhou foi um serviço de fora,
        # não o pedido de quem clicou.
        return render(
            request,
            "forum/topico.html",
            contexto_do_topico(
                request, ator, topico, erro_ia=str(erro), orientacao=orientacao
            ),
            status=503,
        )

    return render(
        request,
        "forum/topico.html",
        contexto_do_topico(
            request,
            ator,
            topico,
            texto=rascunho.texto,
            aviso_ia=_o_que_avisar(rascunho),
            orientacao=orientacao,
        ),
    )


# ===========================================================================
# O MESMO RASCUNHO, AO VIVO — palavra por palavra, enquanto ela escreve
# ===========================================================================
# Pedido do mantenedor em 02/09/2026: *"quero o streaming da resposta sendo
# gerada na tela ao vivo para facilitar o feedback visual"*. O motivo é o susto
# que ele levou horas antes: alguns segundos sem sinal nenhum são
# indistinguíveis de um botão quebrado.
#
# **Esta porta NÃO substitui a de cima, e é por isso que ela não a apaga.** A
# view `gerar_resposta` continua sendo o caminho do formulário comum, e é para
# ela que `static/forum.js` volta quando o ao vivo falha. Duas portas para o
# mesmo pedido é duplicação aceita e declarada: o que elas compartilham (a
# permissão, as falas, o aviso do fim) mora em função, e o que difere é só a
# forma de entregar.
#
# O CONTRATO DA RESPOSTA é uma linha JSON por pedaço, terminada em `\n`:
#
#     {"t": "Escale "}      texto que chegou agora
#     {"erro": "..."}       deu errado; a frase já vem em português
#     {"fim": "..."}        acabou; o aviso para quem vai publicar
#
# Linha é o quadro mais simples que sobrevive a um pedaço partido no meio pela
# rede, e quem remonta a metade é o navegador. Não é SSE de propósito: SSE
# traria um formato de eventos que ninguém aqui precisa, e o `EventSource` do
# navegador nem sequer faz POST.


def _linha(pedaco: dict) -> str:
    """Um quadro do fluxo. `ensure_ascii=False` para o acento não virar escape."""
    return json.dumps(pedaco, ensure_ascii=False) + "\n"


def _fluxo_de_um_erro(frase: str) -> StreamingHttpResponse:
    """Uma recusa no MESMO formato do fluxo.

    Devolver aqui um HTML de erro obrigaria o navegador a ter dois jeitos de ler
    a resposta, e o segundo jeito só seria exercitado no dia da falha — que é o
    dia em que ninguém quer descobrir um caminho novo.
    """
    return StreamingHttpResponse(
        iter([_linha({"erro": frase})]),
        content_type="application/x-ndjson",
        status=400,
    )


@require_POST
def gerar_resposta_ao_vivo(request, topico_id: int):
    """O rascunho saindo em pedaços, para o navegador mostrar enquanto chega."""
    ator = _so_quem_modera(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"), pk=topico_id
    )
    orientacao = (request.POST.get("orientacao") or "").strip()[
        : agente.TETO_DA_ORIENTACAO
    ]

    if topico.estado != Topico.Estado.PUBLICADO:
        return _fluxo_de_um_erro(ERRO_IA_FORA_DO_AR)
    if topico.trancado:
        return _fluxo_de_um_erro(ERRO_IA_TRANCADO)

    # AS FALAS SAEM DO BANCO AGORA, antes de a resposta começar. Consulta dentro
    # do gerador rodaria com o fluxo já aberto, e uma falha ali chegaria no meio
    # do texto, quando não há mais como devolver um erro limpo.
    falas = _falas_para_a_ia(topico)
    area_nome = topico.area.nome
    titulo = topico.titulo

    def pedacos():
        recibo: dict = {}
        inteiro: list[str] = []
        try:
            for pedaco in agente.rascunhar_ao_vivo(
                area_nome=area_nome,
                titulo=titulo,
                falas=falas,
                orientacao=orientacao,
                recibo=recibo,
            ):
                inteiro.append(pedaco)
                yield _linha({"t": pedaco})
        except agente.AgenteIndisponivel as erro:
            # No meio do fluxo o status já foi 200 e não dá para voltar atrás:
            # a recusa viaja DENTRO do corpo, e o navegador a mostra na caixa.
            yield _linha({"erro": str(erro)})
            return

        texto = "".join(inteiro).strip()
        if not texto:
            yield _linha({"erro": agente.VEIO_VAZIA})
            return

        yield _linha(
            {
                "fim": _o_que_avisar(
                    agente.Rascunho(
                        texto=texto,
                        cortado=bool(recibo.get("cortado")),
                        tokens_de_entrada=int(recibo.get("tokens_de_entrada") or 0),
                        tokens_de_saida=int(recibo.get("tokens_de_saida") or 0),
                    )
                )
            }
        )

    resposta = StreamingHttpResponse(pedacos(), content_type="application/x-ndjson")
    # Sem isto, um intermediário que resolva guardar a resposta entregaria o
    # texto inteiro no fim, e o ao vivo viraria uma espera com passos extras.
    resposta["Cache-Control"] = "no-store"
    resposta["X-Accel-Buffering"] = "no"
    return resposta
