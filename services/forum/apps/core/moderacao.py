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

2. **404 para quem não é administrador, nunca 403.** Um 403 confirmaria que a
   porta existe. Quem não modera não deve nem descobrir que estas rotas foram
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

from django.db import IntegrityError, transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.http import require_POST

from apps.forum.models import Area, Mensagem, Topico

from .permissoes import pode_moderar
from .sessao import quem_e
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


def _so_o_administrador(request):
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
    ator = _so_o_administrador(request)
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
    ator = _so_o_administrador(request)
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


@require_POST
def moderar_topico(request, topico_id: int):
    """As seis ações sobre uma conversa inteira."""
    ator = _so_o_administrador(request)
    topico = get_object_or_404(
        Topico.objects.select_related("area", "autor"), pk=topico_id
    )
    acao = (request.POST.get("acao") or "").strip()

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
    topico.resposta_aceita = mensagem
    return _salvar_com_a_rede_do_banco(topico)


# ===========================================================================
# MENSAGEM — editar o texto, tirar do ar, devolver ao ar
# ===========================================================================


@require_POST
def moderar_mensagem(request, mensagem_id: int):
    """As três ações sobre uma fala."""
    ator = _so_o_administrador(request)
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
        with transaction.atomic():
            mensagem.removida_em = timezone.now() if acao == "tirar_do_ar" else None
            erro = _salvar_com_a_rede_do_banco(mensagem)
            if not erro and mensagem.removida_em is not None:
                # Uma mensagem fora do ar não pode continuar sendo a resposta
                # premiada da conversa: o selo apontaria para o vazio.
                Topico.objects.filter(pk=topico.pk, resposta_aceita=mensagem).update(
                    resposta_aceita=None
                )
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
