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
from urllib.parse import quote

from django.conf import settings
from django.http import FileResponse, Http404, HttpResponseRedirect, JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.gamificacao import forja as forjas
from apps.gamificacao.models import Concessao, ConquistaDefinicao, PedidoDeValidacao
from apps.gamificacao.validacao import (
    ValidacaoRecusada,
    aceitar,
    devolver,
    fila_da_equipe,
    marcos_da_pessoa,
    pedir_validacao,
    reenviar,
)

from .equipe import e_da_equipe
from .perfil import escada_de, perfil_de
from .sessao import quem_e, site_atual

# Os recados que uma tela manda para si mesma depois de um POST. São CÓDIGOS e
# não frases: o texto vive no template, no idioma de quem lê, e uma frase pronta
# viajando na barra de endereço é uma frase que alguém pode trocar por outra
# (`?recado=voce-foi-expulso`) e mandar por link a um aluno.
RECADOS = {
    "enviado": "Sua prova foi enviada. A escola vai olhar.",
    "reenviado": "Enviado de novo. O prazo recomeçou.",
    "aceito": "Aceito. A pessoa já foi avisada.",
    "devolvido": "Devolvido, com o motivo que você escolheu.",
    "forja-aberta": "A forja começou. A primeira tentativa já está contada.",
    "forja-somada": "Mais uma tentativa contada. É assim que se faz.",
    "forja-selada": "Peça selada. O número de tentativas ficou gravado nela.",
}


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
def marcos(request):
    """A trilha de marcos reais: o que a pessoa já provou, e o que falta provar.

    **Visitante não leva erro**, pela mesma razão da Base: um 403 aqui seria a
    escola dizendo "isto não é para você" a quem ainda vai se matricular.

    **É esta tela que conta a devolução.** Devolver um pedido não gera aviso no
    sininho — só boa notícia vira carta, e o contrato congelado não tem assunto
    para "seu pedido voltou". Sem esta página a devolução seria silenciosa, e o
    aluno ficaria esperando por uma resposta que já chegou. É por isso que ela
    mostra o motivo em português e põe o botão de mandar de novo ao lado.
    """
    de_fora = {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }
    pessoa_id, site = _pessoa_e_site(request)
    if not pessoa_id:
        return render(request, "gamificacao/marcos.html", {"entrou": False, **de_fora})

    perfil = perfil_de(pessoa_id, site)
    return render(
        request,
        "gamificacao/marcos.html",
        {
            "entrou": True,
            "linhas": marcos_da_pessoa(perfil.pessoa, site),
            "recado": RECADOS.get(request.GET.get("recado", "")),
            "erro": request.GET.get("erro", ""),
            **de_fora,
        },
    )


@require_POST
def enviar_prova(request):
    """O aluno diz "consegui", e mostra onde está a prova.

    Padrão POST-redirect-GET: sem ele, um F5 depois de enviar repetiria o gesto.
    Aqui repetir já seria recusado pela própria regra (o pedido está na fila),
    mas o padrão fica porque o dia em que um gesto NÃO for idempotente é tarde
    demais para lembrar dele.

    **A recusa vira FRASE, nunca 500.** `ValidacaoRecusada` carrega um texto
    escrito para ser lido por gente, e é ele que volta para a tela.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not pessoa_id:
        return HttpResponseRedirect(settings.URL_DE_ENTRADA)

    perfil = perfil_de(pessoa_id, site)
    slug = (request.POST.get("slug") or "").strip()
    evidencia = (request.POST.get("evidencia") or "").strip()
    de_novo = request.POST.get("de_novo") == "1"

    marco = ConquistaDefinicao.objects.filter(
        site_id=site, slug=slug, classe=ConquistaDefinicao.Classe.MARCO
    ).first()
    if marco is None:
        return _voltar("marcos", erro="Não encontrei esse marco nesta escola.")

    try:
        if de_novo:
            pedido = (
                PedidoDeValidacao.objects.filter(
                    pessoa=perfil.pessoa,
                    site_id=site,
                    conquista=marco,
                    estado=PedidoDeValidacao.Estado.DEVOLVIDO,
                )
                .order_by("-id")
                .first()
            )
            if pedido is None:
                return _voltar(
                    "marcos", erro="Não há pedido devolvido para reenviar aqui."
                )
            reenviar(pedido=pedido, evidencia=evidencia)
            return _voltar("marcos", recado="reenviado")

        pedir_validacao(
            pessoa=perfil.pessoa, site_id=site, conquista=marco, evidencia=evidencia
        )
    except ValidacaoRecusada as recusa:
        return _voltar("marcos", erro=str(recusa))

    return _voltar("marcos", recado="enviado")


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
        "gamificacao/interno.html",
        {"pode": False, "url_da_capa": settings.URL_DA_CAPA},
        status=403,
    )


@require_GET
def interno(request):
    """A fila única da equipe: o mais urgente em cima.

    Ordenada por PRAZO, e não por data de criação: os prazos são de 2 e de 5 dias
    úteis, então o pedido mais novo pode vencer antes do mais velho.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not e_da_equipe(pessoa_id) or not site:
        return _recusar_quem_nao_e_da_equipe(request)

    return render(
        request,
        "gamificacao/interno.html",
        {
            "pode": True,
            "fila": fila_da_equipe(site),
            "motivos": PedidoDeValidacao.MotivoDaDevolucao.choices,
            "recado": RECADOS.get(request.GET.get("recado", "")),
            "erro": request.GET.get("erro", ""),
            "agora": timezone.now(),
            "url_da_capa": settings.URL_DA_CAPA,
        },
    )


@require_POST
def decidir(request):
    """Aceitar ou devolver, em um clique.

    **O papel de quem decide sai do SERVIDOR, nunca do formulário.** Um campo
    escondido dizendo `validador_papel=professor` seria uma etiqueta escrita pelo
    próprio navegador — e a auditoria de um marco contestado passaria a valer o
    que vale um campo que qualquer um edita. Quem está na lista da equipe decide
    como equipe, e é isso que fica gravado.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not e_da_equipe(pessoa_id) or not site:
        return _recusar_quem_nao_e_da_equipe(request)

    pedido = PedidoDeValidacao.objects.filter(
        pk=request.POST.get("pedido") or 0, site_id=site
    ).first()
    if pedido is None:
        return _voltar("interno", erro="Esse pedido não existe mais nesta escola.")

    try:
        if request.POST.get("gesto") == "aceitar":
            aceitar(
                pedido=pedido,
                validador_id=pessoa_id,
                validador_papel=Concessao.PapelDoValidador.PROFESSOR,
            )
            return _voltar("interno", recado="aceito")

        devolver(
            pedido=pedido,
            validador_id=pessoa_id,
            validador_papel=Concessao.PapelDoValidador.PROFESSOR,
            motivo=(request.POST.get("motivo") or "").strip(),
        )
    except ValidacaoRecusada as recusa:
        return _voltar("interno", erro=str(recusa))

    return _voltar("interno", recado="devolvido")


# ---------------------------------------------------------------------------
# A FORJA — o medidor de tentativas por peça, e o selo que sai dele
# ---------------------------------------------------------------------------
def _linha_da_forja(forja) -> dict:
    """Uma peça pronta para o template, com o nome já em português.

    A conta mora aqui e não dentro de `{{ }}`: template que calcula é template
    que erra em silêncio, e ninguém escreve teste para uma expressão dentro de
    uma chave dupla (o mesmo motivo de `Escada` trazer `falta` e `fracao`
    prontos).
    """
    return {
        "chave": forja.desafio_ref,
        "nome": forjas.nome_da_peca(forja.desafio_ref),
        "tentativas": forja.medidor,
        "teto": forja.teto,
        "no_teto": forja.medidor >= forja.teto,
        "selo": forja.selo,
        "selada_em": forja.selada_em,
    }


@require_GET
def forja(request):
    """A Forja: o único medidor desta escola que celebra a INSISTÊNCIA.

    **Visitante não leva erro**, e **sem `SITE_ID` também não quebra** — a mesma
    postura da Base e dos Marcos, pela mesma razão: página sem selo é uma
    página, página quebrada não é.

    A REGRA DE TELA aqui tem uma leitura própria. *"XP nunca maior que a imagem
    da obra"* não vira "esconda o número": vira **o número de tentativas é o
    assunto, e é dito com orgulho, não como placar**. Ele é a única coisa que
    esta página conta, e a razão de ela existir é justamente tirar da pessoa a
    vontade de escondê-lo.
    """
    de_fora = {
        "url_de_entrada": settings.URL_DE_ENTRADA,
        "url_da_capa": settings.URL_DA_CAPA,
    }
    pessoa_id, site = _pessoa_e_site(request)
    if not pessoa_id:
        return render(request, "gamificacao/forja.html", {"entrou": False, **de_fora})

    perfil = perfil_de(pessoa_id, site)
    return render(
        request,
        "gamificacao/forja.html",
        {
            "entrou": True,
            "abertas": [
                _linha_da_forja(f) for f in forjas.abertas_de(perfil.pessoa, site)
            ],
            "seladas": [
                _linha_da_forja(f) for f in forjas.seladas_de(perfil.pessoa, site)
            ],
            "recado": RECADOS.get(request.GET.get("recado", "")),
            "erro": request.GET.get("erro", ""),
            **de_fora,
        },
    )


@require_POST
def forjar(request):
    """Os três gestos da Forja, numa porta só: começar, somar, selar.

    **Nenhum deles recebe o id de uma linha.** O formulário manda o NOME da
    peça, e o dono é sempre quem a sessão diz que é — a forja de outra pessoa
    não é protegida por uma conferência que alguém precisa lembrar de escrever,
    ela simplesmente não existe para esta consulta (`forja._minha`).

    Padrão POST-redirect-GET, como em `enviar_prova`: sem ele um F5 depois de
    somar uma tentativa somaria outra, e o medidor que só cresce cresceria por
    engano — que é a única forma de esse número mentir.
    """
    pessoa_id, site = _pessoa_e_site(request)
    if not pessoa_id:
        return HttpResponseRedirect(settings.URL_DE_ENTRADA)

    perfil = perfil_de(pessoa_id, site)
    gesto = request.POST.get("gesto", "")

    try:
        if gesto == "abrir":
            forjas.abrir(
                pessoa=perfil.pessoa,
                site_id=site,
                nome=(request.POST.get("nome") or "").strip(),
            )
            return _voltar("forja", recado="forja-aberta")

        chave = (request.POST.get("peca") or "").strip()
        if gesto == "selar":
            forjas.selar(pessoa=perfil.pessoa, site_id=site, desafio_ref=chave)
            return _voltar("forja", recado="forja-selada")

        if gesto == "tentativa":
            forjas.mais_uma_tentativa(
                pessoa=perfil.pessoa, site_id=site, desafio_ref=chave
            )
            return _voltar("forja", recado="forja-somada")
    except forjas.ForjaRecusada as recusa:
        return _voltar("forja", erro=str(recusa))

    # Gesto que não existe não é erro do aluno: é formulário adulterado ou
    # navegador antigo. Volta para a página sem mexer em nada.
    return _voltar("forja")
