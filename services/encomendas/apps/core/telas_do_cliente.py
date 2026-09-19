"""As telas do cliente: escolher o cartão, descrever, negociar e acompanhar.

Produto: `PLANO-MESTRE-FILA-DO-PRIMEIRO-DOLAR.md` §5.1 a §5.5. Lei:
`docs/decisoes/DECISAO-fila-do-primeiro-dolar.md` §3.4 (a escola é a primeira
cliente, e o dinheiro fica por último).

NÃO EXISTE ROTA DE PAGAR, E A AUSÊNCIA É O DESENHO
---------------------------------------------------
A pausa financeira de 22/08/2026 continua de pé. Uma tela de pagar que
respondesse "ainda não" seria uma promessa com data; uma rota que não existe é
404, e 404 não promete nada. `tests/test_cliente_nao_paga_nem_ve_contato.py`
mede exatamente isso, percorrendo os endereços que alguém escreveria por
instinto. O que o cliente lê no lugar é "aguardando a confirmação da escola",
e quem confirma é o plantão, com autor e data.

QUEM É O CLIENTE HOJE, E POR QUE ELE É O PLANTÃO
-------------------------------------------------
`Encomenda.Origem.ESCOLA` já dizia a resposta antes desta tela existir: *"aberta
pelo plantão, a escola é a cliente"*. Enquanto a origem for `escola`, o banco só
aceita a confirmação de pagamento do plantão
(`confirmacao_pelo_plantao_so_para_a_escola`), e um pedido aberto por qualquer
outra pessoa nasceria impossível de levar à produção.

Então a porta é a MESMA lista de sempre, `IDS_DO_PLANTAO`: nenhum login novo,
nenhuma segunda régua de autorização, e nada inventado sobre a aprovação de
cliente externo, que é tarefa própria. O dia em que ela chegar, o que muda é
esta função de quatro linhas, e não a jornada inteira.

NADA DO ALUNO ATRAVESSA ESTA FRONTEIRA ALÉM DO TÍTULO
-------------------------------------------------------
[INV-ENC-S3]. A tela do pedido nomeia "o modelador" e o título de Banca dele, e
mais nada: nem nome exibido, nem e-mail, nem o id opaco. O guarda é
`tests/test_cliente_nao_paga_nem_ve_contato.py`, que planta um nome de exibição
no perfil e confere que ele não sai na página.
"""

from __future__ import annotations

from functools import wraps

from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from apps.core import plantao as porta_do_plantao
from apps.core import sessao
from apps.encomendas import acompanhamento, cardapio, negociacao
from apps.encomendas.models import Encomenda, Proposta

# Os recados da tela, por código. Mesmo desenho da tela do plantão: o POST
# redireciona para o GET com o código na barra de endereço, e a frase mora aqui.
# Recarregar a página não repete o gesto, e nenhum texto vindo de fora entra na
# URL.
RECADOS = {
    "pedido_aberto": (
        "Pronto. O seu pedido entrou na Fila e ja esta procurando um modelador."
    ),
    "proposta_aceita": (
        "Acordo fechado. Valor, prazo e entregaveis estao congelados, e a escola "
        "vai confirmar o pagamento."
    ),
    "contraproposta_enviada": "A sua contraproposta foi enviada ao modelador.",
    "entrega_aprovada": "Entrega aprovada. Obrigado.",
    "ajuste_pedido": "O modelador recebeu o seu pedido de ajuste.",
    "pedido_cancelado": "O pedido foi cancelado.",
    "desistencia": (
        "Voce saiu desta negociacao. O plantao da escola vai olhar o seu pedido."
    ),
    cardapio.CARTAO_DESCONHECIDO: "Escolha um dos tres cartoes do cardapio.",
    cardapio.SEM_NOME_DA_PECA: "De um nome a peca que voce quer.",
    cardapio.NOME_DA_PECA_LONGO_DEMAIS: (
        "O nome da peca ficou longo demais. Escreva um nome curto, e conte o "
        "resto nas observacoes."
    ),
    cardapio.ONDE_FORA_DA_LISTA: "Escolha onde a peca vai ser usada.",
    cardapio.ESTILO_FORA_DA_LISTA: "Escolha um dos estilos da lista.",
    cardapio.SEM_ENTREGAVEL: "Marque pelo menos um entregavel.",
    cardapio.ENTREGAVEL_FORA_DO_CARTAO: (
        "Um dos entregaveis marcados nao pertence a este cartao. Marque de novo, "
        "usando so o que a lista mostra."
    ),
    cardapio.OBSERVACOES_LONGAS_DEMAIS: (
        "As observacoes ficaram longas demais. Resuma o essencial: o modelador "
        "le isto junto com o briefing."
    ),
    cardapio.CONTATO_NO_BRIEFING: (
        "Tire o e-mail, o telefone, o link ou o arroba do texto. A conversa com "
        "o modelador acontece dentro do site, e a escola acompanha: e assim que "
        "voce fica protegido."
    ),
    acompanhamento.SEM_O_QUE_AJUSTAR: "Escreva o que precisa ser ajustado.",
    acompanhamento.AJUSTE_LONGO_DEMAIS: (
        "O pedido de ajuste ficou longo demais. Diga o essencial, item a item."
    ),
    acompanhamento.CONTATO_NO_AJUSTE: (
        "Tire o e-mail, o telefone, o link ou o arroba do texto do ajuste. A "
        "conversa acontece dentro do site."
    ),
    acompanhamento.ACABARAM_AS_CORRECOES: (
        "Este acordo ja usou todas as correcoes combinadas. O seu pedido foi "
        "para o plantao da escola, que vai falar com voce."
    ),
    acompanhamento.CANCELAMENTO_DEPOIS_DO_PAGAMENTO: (
        "A escola ja confirmou o pagamento deste pedido, entao ele nao se "
        "cancela por aqui. Fale com o plantao da escola."
    ),
    acompanhamento.NAO_E_ESTA_HORA: (
        "Este gesto nao cabe no momento em que o pedido esta. A pagina abaixo "
        "mostra o estado de agora."
    ),
    negociacao.NAO_ESTA_EM_NEGOCIACAO: (
        "Este pedido nao esta em negociacao agora. A pagina abaixo mostra o "
        "estado de agora."
    ),
    negociacao.NAO_E_A_SUA_VEZ: (
        "A vez e do modelador: ele esta respondendo a sua ultima proposta."
    ),
    negociacao.O_ALUNO_PROPOE_PRIMEIRO: (
        "Quem poe o primeiro numero e o modelador, porque quem faz o trabalho e "
        "quem sabe quanto ele custa. Espere a proposta dele."
    ),
    negociacao.RODADAS_ESGOTADAS: (
        "As rodadas de negociacao deste pedido acabaram. Ele foi para o plantao "
        "da escola, que vai falar com voce."
    ),
    negociacao.ENTREGAVEL_FORA_DO_BRIEFING: (
        "A contraproposta marca um entregavel que o seu briefing nao pediu. "
        "Marque de novo, usando so o que a lista mostra."
    ),
    negociacao.JUSTIFICATIVA_LONGA_DEMAIS: (
        "A justificativa ficou longa demais. Resuma o motivo em poucas linhas."
    ),
    negociacao.SEM_PROPOSTA_DE_PE: (
        "Nao ha proposta esperando a sua resposta neste pedido."
    ),
    "numero_invalido": (
        "O valor e o prazo sao numeros inteiros, sem sinal. Escreva o valor em "
        "reais e o prazo em dias."
    ),
}

# O código que a tela pinta como boa notícia. Os outros são recusas, e pintá-los
# igual esconderia a diferença.
RECADOS_BONS = frozenset(
    {
        "pedido_aberto",
        "proposta_aceita",
        "contraproposta_enviada",
        "entrega_aprovada",
        "ajuste_pedido",
    }
)


def _quem_e_o_cliente(request) -> str | None:
    """O id opaco de quem pode usar estas telas, ou `None`. Fail-closed duas vezes.

    Quem não entrou não é ninguém, e quem entrou sem a escola ter liberado
    também não. Ver a nota do topo sobre por que a lista é a do plantão.
    """
    pessoa_id = sessao.quem_e(request)
    return pessoa_id if porta_do_plantao.e_do_plantao(pessoa_id) else None


def _porta_fechada(request):
    return render(
        request,
        "cliente_fechado.html",
        {
            "titulo": "Esta area e de quem a escola liberou",
            "texto": (
                "Ela e de quem encomenda peca pela Fila do Primeiro Dolar. Se "
                "voce faz parte da escola e chegou ate aqui, fale com a "
                "coordenacao: o acesso e liberado um a um, de proposito."
            ),
        },
        status=403,
    )


def _pedido_nao_achado(request):
    """404 para o pedido que não existe E para o pedido que é de outra pessoa.

    A mesma resposta para os dois casos, de propósito: um 403 contaria a um
    curioso que aquele identificador existe e é de alguém.
    """
    return render(
        request,
        "cliente_fechado.html",
        {
            "titulo": "Nao achei este pedido",
            "texto": (
                "Ele nao esta na sua lista. Confira o endereco, ou volte ao "
                "cardapio para ver os seus pedidos."
            ),
        },
        status=404,
    )


def _de_volta(destino: str, codigo: str, *args):
    return HttpResponseRedirect(f"{reverse(destino, args=args)}?recado={codigo}")


def _recado(request):
    codigo = request.GET.get("recado", "")
    return RECADOS.get(codigo), codigo in RECADOS_BONS


def _meu_pedido(encomenda_id, cliente_id: str, site_id: str) -> Encomenda | None:
    """O pedido, se ele for DESTE cliente. `None` em qualquer outro caso.

    Pedido de outra pessoa e pedido inexistente devolvem a mesma coisa, e a
    tela responde 404 para as duas: distinguir contaria a um curioso que aquele
    identificador existe e é de alguém.
    """
    return Encomenda.objects.filter(
        pk=encomenda_id, cliente_id=cliente_id, site_id=site_id
    ).first()


def _inteiro(texto: str) -> int | None:
    texto = (texto or "").strip()
    return int(texto) if texto.isdigit() else None


def _em_reais(centavos: int | None) -> str:
    """Centavos viram reais na TELA, e continuam centavos no banco.

    O contrato desta casa guarda dinheiro em inteiro de centavos, e a conversão
    mora aqui, na última camada, porque é a única em que um arredondamento não
    contamina nada depois.
    """
    if centavos is None:
        return ""
    return f"{centavos // 100},{centavos % 100:02d}"


def _nomes(entregaveis) -> list[str]:
    """Os entregáveis pelo nome que o cliente lê, e não pela chave do banco."""
    return [cardapio.ENTREGAVEIS.get(item, item) for item in entregaveis or ()]


def _em_data(quando) -> str:
    """A data no fuso e na escrita do Brasil.

    Nenhuma célula desta casa define `LANGUAGE_CODE`, então o Django escreveria
    `Sept. 20, 2026, 5:40 p.m.` na tela de um cliente brasileiro. Foi a prévia
    desta tarefa que pegou isso. Mudar a língua do projeto inteiro por causa de
    uma data seria martelo para o que cabe em uma linha, e `localtime` já aplica
    o `TIME_ZONE` de São Paulo que a célula declara.
    """
    if quando is None:
        return ""
    local = timezone.localtime(quando)
    return f"{local:%d/%m/%Y} as {local:%Hh%M}"


def gesto_do_cliente(sucesso: str):
    """As quatro conferências que todo gesto faz antes de mexer em alguma coisa.

    Quem está agindo, qual é o site, o pedido é dele, e só então o gesto. Os
    cinco botões desta tela fazem as mesmas quatro, e cinco cópias
    divergiriam na primeira que mudasse: bastaria uma delas esquecer o dono do
    pedido para um cliente agir no pedido de outro.

    O gesto decorado devolve o `Desfecho` do motor, e este envelope traduz em
    redirecionamento: `sucesso` quando deu certo, a razão nomeada quando não.
    """

    def decorar(funcao):
        @wraps(funcao)
        @require_POST
        def porta(request, encomenda_id):
            quem = _quem_e_o_cliente(request)
            if quem is None:
                return _porta_fechada(request)
            try:
                site = sessao.site_desta_instalacao()
            except sessao.ConfiguracaoAusente:
                return _porta_fechada(request)
            if _meu_pedido(encomenda_id, quem, site) is None:
                return _pedido_nao_achado(request)
            desfecho = funcao(request, encomenda_id, quem=quem, site=site)
            if desfecho is None:
                return _de_volta("pedido", "numero_invalido", encomenda_id)
            codigo = sucesso if desfecho.feito else desfecho.razao
            return _de_volta("pedido", codigo, encomenda_id)

        return porta

    return decorar


@require_GET
def cardapio_do_cliente(request):
    """Os três cartões, e acima deles os pedidos que já estão andando.

    As duas coisas na mesma página de propósito: quem volta ao site volta para
    olhar um pedido, e não para abrir outro. Uma página só de cardápio obrigaria
    a maioria das visitas a procurar a lista.
    """
    quem = _quem_e_o_cliente(request)
    if quem is None:
        return _porta_fechada(request)
    try:
        site = sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        return _porta_fechada(request)
    agora = timezone.now()
    recado, deu_certo = _recado(request)
    meus = Encomenda.objects.filter(cliente_id=quem, site_id=site).order_by(
        "-criada_em"
    )
    return render(
        request,
        "cardapio.html",
        {
            "cartoes": cardapio.listar(agora, site_id=site),
            "pedidos": [
                {
                    "id": projeto.pk,
                    "nome_da_peca": projeto.briefing.get("nome_da_peca", ""),
                    "cartao": cardapio.CARTOES[projeto.cartao].titulo,
                    "aconteceu": acompanhamento.RECADO[projeto.status][0],
                }
                for projeto in meus
            ],
            "recado": recado,
            "deu_certo": deu_certo,
        },
    )


@require_GET
def briefing(request, cartao: str):
    """O formulário blindado daquele cartão."""
    quem = _quem_e_o_cliente(request)
    if quem is None:
        return _porta_fechada(request)
    if cartao not in cardapio.CARTOES:
        return _de_volta("cardapio_do_cliente", cardapio.CARTAO_DESCONHECIDO)
    try:
        site = sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        return _porta_fechada(request)
    escolhido = cardapio.CARTOES[cartao]
    recado, _ = _recado(request)
    return render(
        request,
        "briefing.html",
        {
            "cartao": escolhido,
            "prazo_dias": cardapio.prazo_de_producao_em_dias(
                cartao, timezone.now(), site_id=site
            ),
            "entregaveis": [
                (valor, cardapio.ENTREGAVEIS[valor]) for valor in escolhido.entregaveis
            ],
            "onde_vai_ser_usada": sorted(cardapio.ONDE_VAI_SER_USADA.items()),
            "estilos": sorted(cardapio.ESTILOS.items()),
            "limite_das_observacoes": cardapio.teto_do_texto(
                timezone.now(), site_id=site
            ),
            "recado": recado,
        },
    )


@require_POST
def abrir_pedido(request, cartao: str):
    """O passo 1 da §5.3: descrever. O pedido nasce na pista do nível dele."""
    quem = _quem_e_o_cliente(request)
    if quem is None:
        return _porta_fechada(request)
    try:
        site = sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        return _porta_fechada(request)
    recusa, briefing_pronto = cardapio.preparar(
        cartao,
        {
            "nome_da_peca": request.POST.get("nome_da_peca"),
            "onde_vai_ser_usada": request.POST.get("onde_vai_ser_usada"),
            "estilo": request.POST.get("estilo"),
            "entregaveis": request.POST.getlist("entregaveis"),
            "observacoes": request.POST.get("observacoes"),
        },
        timezone.now(),
        site_id=site,
    )
    if recusa:
        if recusa == cardapio.CARTAO_DESCONHECIDO:
            return _de_volta("cardapio_do_cliente", recusa)
        return _de_volta("briefing", recusa, cartao)
    projeto = cardapio.abrir(
        site_id=site,
        cliente_id=quem,
        cartao=cartao,
        briefing=briefing_pronto,
        autoriza_portfolio=request.POST.get("autoriza_portfolio") == "sim",
    )
    return _de_volta("pedido", "pedido_aberto", projeto.pk)


@require_GET
def pedido(request, encomenda_id):
    """O passo 4 da §5.3: acompanhar, e agir quando for a vez dele."""
    quem = _quem_e_o_cliente(request)
    if quem is None:
        return _porta_fechada(request)
    try:
        site = sessao.site_desta_instalacao()
    except sessao.ConfiguracaoAusente:
        return _porta_fechada(request)
    projeto = _meu_pedido(encomenda_id, quem, site)
    if projeto is None:
        return _pedido_nao_achado(request)

    aconteceu, fazer = acompanhamento.RECADO[projeto.status]
    de_pe = negociacao.proposta_de_pe(projeto)
    recado, deu_certo = _recado(request)
    return render(
        request,
        "pedido.html",
        {
            "pedido": projeto,
            "nome_da_peca": projeto.briefing.get("nome_da_peca", ""),
            "cartao": cardapio.CARTOES[projeto.cartao],
            "aconteceu": aconteceu,
            "fazer": fazer,
            "gestos": acompanhamento.o_que_o_cliente_pode_fazer(projeto),
            "correcoes_restantes": acompanhamento.correcoes_restantes(projeto),
            "acordo_em_reais": _em_reais(projeto.acordo_valor_cents),
            "acordo_entregaveis": _nomes(projeto.acordo_entregaveis),
            # A proposta só aparece quando é a vez do cliente responder. A que o
            # próprio cliente escreveu fica fora: mostrar a sua proposta com os
            # botões de aceitar ao lado convidaria a assinar sozinho um contrato
            # de dois, que `negociacao.aceitar_a_proposta` recusa depois.
            "proposta": (
                de_pe if de_pe and de_pe.de_quem == Proposta.DeQuem.ALUNO else None
            ),
            "proposta_em_reais": _em_reais(de_pe.valor_cents if de_pe else None),
            "proposta_vale_ate": _em_data(de_pe.valida_ate if de_pe else None),
            "entregaveis_do_briefing": [
                (valor, cardapio.ENTREGAVEIS.get(valor, valor))
                for valor in negociacao.entregaveis_do_briefing(projeto)
            ],
            # O título de Banca do modelador, e nada mais dele ([INV-ENC-S3]).
            "titulo_do_modelador": (
                projeto.aluno.get_titulo_banca_display()
                if projeto.aluno and projeto.aluno.titulo_banca
                else ""
            ),
            "recado": recado,
            "deu_certo": deu_certo,
        },
    )


@gesto_do_cliente("proposta_aceita")
def aceitar_proposta(request, encomenda_id, *, quem, site):
    """O cliente aceita a proposta do modelador, e o combinado vira pedra."""
    return negociacao.aceitar_a_proposta(
        encomenda_id,
        timezone.now(),
        site_id=site,
        de_quem=Proposta.DeQuem.CLIENTE,
        quem=quem,
    )


@gesto_do_cliente("contraproposta_enviada")
def contrapor(request, encomenda_id, *, quem, site):
    """A contraproposta: o mesmo formulário de seis campos, do outro lado."""
    reais = _inteiro(request.POST.get("valor_reais"))
    prazo = _inteiro(request.POST.get("prazo_dias"))
    correcoes = _inteiro(request.POST.get("correcoes_inclusas"))
    if reais is None or prazo is None or correcoes is None:
        return None
    return negociacao.propor(
        encomenda_id,
        timezone.now(),
        site_id=site,
        de_quem=Proposta.DeQuem.CLIENTE,
        # A tela pede reais porque é o que o cliente sabe escrever; o banco
        # guarda centavos, que é o que o contrato desta casa exige.
        valor_cents=reais * 100,
        prazo_dias=prazo,
        entregaveis=request.POST.getlist("entregaveis"),
        correcoes_inclusas=correcoes,
        justificativa=(request.POST.get("justificativa") or "").strip(),
    )


@gesto_do_cliente("desistencia")
def desistir_da_negociacao(request, encomenda_id, *, quem, site):
    """Sair da negociação antes do acordo. O pedido vai ao plantão, e nunca ao
    próximo aluno ([INV-ENC-N7])."""
    return negociacao.desistir(
        encomenda_id, timezone.now(), site_id=site, de_quem=Proposta.DeQuem.CLIENTE
    )


@gesto_do_cliente("entrega_aprovada")
def aprovar_entrega(request, encomenda_id, *, quem, site):
    """O cliente aprova a entrega revisada, e o trabalho do aluno conta."""
    return acompanhamento.aprovar(encomenda_id, timezone.now(), site_id=site, quem=quem)


@gesto_do_cliente("ajuste_pedido")
def pedir_ajuste(request, encomenda_id, *, quem, site):
    """O ajuste do §5.5, com texto estruturado e dentro do que o acordo incluiu."""
    return acompanhamento.pedir_correcao(
        encomenda_id,
        timezone.now(),
        site_id=site,
        quem=quem,
        o_que_ajustar=request.POST.get("o_que_ajustar") or "",
    )


@gesto_do_cliente("pedido_cancelado")
def cancelar_pedido(request, encomenda_id, *, quem, site):
    """Desistir do pedido antes de alguém pagar ou produzir."""
    return acompanhamento.cancelar(
        encomenda_id, timezone.now(), site_id=site, quem=quem
    )
