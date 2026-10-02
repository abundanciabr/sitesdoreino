"""A jornada autoral: explorar, escolher, criar e pedir ajuda."""

from django.db import transaction
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST, require_http_methods

from apps.portfolio import conferencia, projetos
from apps.portfolio.models import Peca, Portfolio, ProjetoAutoral
from apps.portfolio.quiz_client import QuizIndisponivel, QuizRecusado, quiz
from .views import de_fora, site_atual, sem_escola

ETAPAS = {
    "interesses": "O que desperta sua vontade de criar?",
    "contexto": "Onde você imagina seu trabalho?",
    "ponto_partida": "De onde você está começando?",
    "projeto": "Escolha uma ideia para desenvolver",
    "apresentacao": "O que você quer mostrar a um cliente?",
    "escolha_final": "Seu projeto, do seu jeito",
}
CAMINHOS = {
    "descobrir": list(ETAPAS),
    "ideia": [
        "interesses",
        "projeto",
        "contexto",
        "ponto_partida",
        "apresentacao",
        "escolha_final",
    ],
    "prontos": [
        "ponto_partida",
        "contexto",
        "projeto",
        "apresentacao",
        "escolha_final",
    ],
}
CONTEXTOS = [
    ("corrida", "Corridas"),
    ("social", "Encontros e convivência"),
    ("aventura", "Aventura e exploração"),
    ("simulador", "Simuladores"),
    ("proprio", "Meu próprio jogo ou outro uso"),
    ("explorar", "Quero experimentar"),
]
ESTILOS = [
    ("cartunesco", "Cartunesco e estilizado"),
    ("low_poly", "Formas simples / low poly"),
    ("detalhado", "Detalhado"),
    ("explorar", "Quero explorar estilos"),
]
EXPERIENCIAS = [
    ("comecando", "Estou começando no Blender"),
    ("pratiquei", "Já criei alguns modelos"),
    ("roblox", "Já usei meus modelos no Roblox"),
]
TAMANHOS = [
    ("um", "Um objeto para começar"),
    ("conjunto", "Um pequeno conjunto"),
    ("cena", "Uma cena ou modelo mais complexo"),
    ("existente", "Aproveitar algo que já fiz"),
]
CAMINHO_COMERCIAL = [
    "ponto_partida",
    "contexto",
    "interesses",
    "projeto",
    "apresentacao",
    "escolha_final",
]
TITULOS_COMERCIAIS = {
    "ponto_partida": "Comece pelo que você já sabe e já criou",
    "contexto": "Como você pretende ganhar dinheiro com 3D?",
    "interesses": "Que trabalhos vão mostrar o que você oferece?",
    "projeto": "Com o que seu portfólio vai começar?",
    "apresentacao": "Prepare sua apresentação para clientes ou compradores",
    "escolha_final": "Seu portfólio para buscar oportunidades",
}
EXPERIENCIAS_COMERCIAIS = [
    ("iniciante", "Iniciante: estou começando ou fiz poucos modelos"),
    (
        "intermediario",
        "Intermediário: já criei vários modelos e consigo concluir trabalhos; talvez já tenha feito encomendas",
    ),
    (
        "avancado",
        "Avançado: tenho bastante experiência e trabalhos concluídos, inclusive para clientes ou projetos profissionais",
    ),
    ("nao_sei", "Não sei dizer: quero escolher meu caminho pelo que já tenho criado"),
]
ANDAMENTOS = [
    ("nao_comecou", "Ainda não comecei"),
    ("comeco", "Estou no começo"),
    ("meio", "Estou no meio"),
    ("final", "Estou perto do final"),
    ("concluido", "Já concluí"),
]
EXPERIENCIA_COMERCIAL = [
    ("nunca", "Ainda não fiz encomendas"),
    ("encomendas", "Já fiz algumas encomendas"),
    ("profissional", "Já trabalhei para clientes ou projetos profissionais"),
]
TRABALHOS = [
    ("nenhum", "Ainda não tenho modelos"),
    ("rascunhos", "Tenho rascunhos ou modelos em desenvolvimento"),
    ("prontos", "Tenho trabalhos concluídos que posso apresentar"),
]
CAMINHOS_RENDA = [
    (
        "experiencias",
        "Modelagem por encomenda para criadores de experiências Roblox, como objetos, armas, animais ou cenários",
    ),
    (
        "ugc_clientes",
        "Produção de acessórios ou itens UGC para clientes, como cabelos, roupas 3D e chapéus",
    ),
    (
        "marketplace",
        "Preparação de itens próprios para vender no Marketplace do Roblox",
    ),
    ("explorar", "Ainda não sei: quero conhecer essas possibilidades"),
]
PUBLICOS = [
    ("criadores", "Criadores de experiências Roblox"),
    ("marcas", "Clientes e equipes que encomendam itens para avatares"),
    ("jogadores", "Jogadores que compram itens para seus avatares"),
    ("descobrir", "Quero descobrir quem pode se interessar"),
]
PECAS = [
    ("cabelo", "Um cabelo"),
    ("roupa", "Uma roupa 3D — Layered Clothing"),
    ("chapeu", "Um chapéu ou acessório de cabeça"),
    ("outra", "Outra criação: espada, arma, objeto, animal ou minha ideia"),
]
APRESENTACAO_ITENS = [
    ("imagens", "Preparar imagens claras da forma e dos detalhes"),
    ("descricao", "Escrever uma descrição: o que fiz e o que consigo entregar"),
    ("roblox", "Mostrar o uso no Roblox, no avatar ou na experiência prevista"),
]
DIVULGACOES = [
    ("pagina", "Quero começar pelo link da minha página pública"),
    (
        "comunidades",
        "Quero apresentar meu serviço em comunidades de criadores e espaços de encomendas",
    ),
    ("marketplace", "Quero preparar a apresentação dos meus itens para o Marketplace"),
    ("descobrir", "Quero uma sugestão de próximo passo"),
]
LISTAS_COMERCIAIS = (
    "interesses",
    "contextos",
    "estilos",
    "trabalhos_selecionados",
    "proximas_pecas",
    "apresentacao_itens",
)
CAMPOS_COMERCIAIS = {
    "ponto_partida": (
        "experiencia",
        "andamento_curso",
        "experiencia_comercial",
        "tem_trabalhos",
    ),
    "contexto": ("caminho_comercial", "publico", "servico_proprio"),
    "interesses": (
        "interesses",
        "ideia_propria",
        "modelos_prontos",
        "trabalhos_selecionados",
        "pronta_entrega",
    ),
    "projeto": (
        "primeira_peca",
        "acrescentar",
        "proximas_pecas",
        "projeto_chave",
        "ideia_propria",
    ),
    "apresentacao": (
        "apresentacao_itens",
        "divulgacao",
        "objetivo_apresentacao",
        "primeira_acao",
    ),
    "escolha_final": (),
}


def comercial(tentativa):
    return tentativa.get("fluxo_versao") == "comercial"


def caminho_de(tentativa):
    return CAMINHO_COMERCIAL if comercial(tentativa) else CAMINHOS[tentativa["entrada"]]


CAMPOS_PROPOSTA = {
    "titulo": "Nome do projeto",
    "descricao": "O que quero criar ou aproveitar",
    "direcao": "Minha direção criativa",
    "intencao": "Por que quero criar isso",
    "aplicacao": "Onde imagino usar esse trabalho",
    "servico": "O serviço que gostaria de oferecer",
    "primeira_entrega": "Minha primeira entrega",
    "aprendizagem": "O que quero aprender ou melhorar",
    "apresentacao": "Como pretendo mostrar o resultado",
    "primeira_acao": "Por onde vou começar",
}
CAMPOS_ETAPA = {
    "interesses": ("interesses", "ideia_propria"),
    "contexto": ("contextos", "estilos"),
    "ponto_partida": ("experiencia", "modelos_prontos", "dificuldade"),
    "projeto": ("tamanho", "habilidade", "projeto_chave", "ideia_propria"),
    "apresentacao": ("objetivo_apresentacao", "servico_proprio", "primeira_acao"),
    "escolha_final": (),
}


def dono(request):
    escola = site_atual()
    if not escola:
        raise QuizIndisponivel(
            "Não foi possível identificar a escola. Tente novamente mais tarde."
        )
    return {"site_id": escola, "aluno_id": request.aluno["id"]}


def desenhar(request, template, contexto=None, status=200):
    resposta = render(
        request,
        "pages/" + template,
        {"aluno": getattr(request, "aluno", None), **de_fora(), **(contexto or {})},
        status=status,
    )
    resposta["Cache-Control"] = "no-store"
    return resposta


def problema(request, erro, status=503):
    return desenhar(request, "jornada_erro.html", {"erro": str(erro)}, status=status)


@require_GET
def inicio(request):
    escola = site_atual()
    if not escola:
        return sem_escola(request)
    portfolio = (
        Portfolio.objects.do_aluno(site_id=escola, aluno_id=request.aluno["id"]).first()
        if escola
        else None
    )
    exploracao, aviso = None, ""
    if escola:
        try:
            exploracao = quiz.chamar("exploracoes/atual", **dono(request))
        except (QuizIndisponivel, QuizRecusado) as erro:
            aviso = str(erro)
    return desenhar(
        request,
        "jornada.html",
        {
            "portfolio": portfolio,
            "projetos": portfolio.projetos_autorais.all() if portfolio else [],
            "exploracao": exploracao,
            "aviso": aviso,
        },
    )


@require_POST
def iniciar_quiz(request):
    entrada = request.POST.get("entrada", "descobrir")
    if entrada not in CAMINHOS:
        raise Http404
    try:
        tentativa = quiz.chamar(
            "exploracoes",
            **dono(request),
            dados={"entrada": entrada, "nova": request.POST.get("nova") == "1"},
        )
        if not tentativa:
            raise QuizIndisponivel(
                "Não foi possível iniciar a exploração. Tente novamente."
            )
        etapa = tentativa.get("etapa") or caminho_de(tentativa)[0]
        return redirect("quiz_etapa", exploracao_id=tentativa["id"], etapa=etapa)
    except (QuizIndisponivel, QuizRecusado) as erro:
        return problema(request, erro)


def exploracao_de(request, exploracao_id):
    tentativa = quiz.chamar("exploracoes/" + str(exploracao_id), **dono(request))
    if tentativa is None:
        raise Http404
    return tentativa


def proposta_de(tentativa):
    respostas = tentativa["respostas"]
    chave = respostas.get("projeto_chave", "")
    propostas = tentativa.get("propostas", [])
    escolhida = next(
        (p for p in propostas if p["chave"] == chave), propostas[0] if propostas else {}
    )
    if chave == "proprio":
        escolhida = {
            **(escolhida if comercial(tentativa) else {}),
            "titulo": respostas.get("ideia_propria", "")[:100] or "Meu portfólio",
            "descricao": respostas.get("ideia_propria")
            or respostas.get("modelos_prontos", ""),
            "servico": respostas.get("servico_proprio")
            or tentativa.get("plano", {}).get("servico", ""),
            "aprendizagem": respostas.get("habilidade", ""),
            "primeira_acao": respostas.get("primeira_acao", ""),
            "apresentacao": respostas.get("objetivo_apresentacao", ""),
        }
    if comercial(tentativa):
        escolhida = {
            **escolhida,
            "plano": escolhida.get("plano") or tentativa.get("plano", {}),
        }
        plano = escolhida["plano"]
        if plano.get("trabalhos_existentes"):
            escolhida["titulo"] = (
                "Portfólio: " + plano.get("servico", "Meus trabalhos")[:180]
            )
            escolhida["descricao"] = (
                "Minha composição inicial: "
                + "; ".join(plano.get("composicao_inicial", []))[:2800]
            )
        escolhida["aplicacao"] = "Apresentar meus trabalhos a " + plano.get(
            "publico", "clientes ou compradores"
        )
    return {**escolhida, **respostas.get("proposta_editada", {})}


def edicoes_da_proposta(request, tentativa):
    """Guarda as escolhas escritas, sem congelar sugestões apenas exibidas."""
    sem_edicoes = {
        **tentativa,
        "respostas": {
            chave: valor
            for chave, valor in tentativa["respostas"].items()
            if chave != "proposta_editada"
        },
    }
    base = proposta_de(sem_edicoes)
    atuais = proposta_de(tentativa)
    return {
        chave: request.POST.get(chave, atuais.get(chave, ""))
        for chave in CAMPOS_PROPOSTA
        if request.POST.get(chave, atuais.get(chave, "")) != base.get(chave, "")
    }


@require_http_methods(["GET", "POST"])
def quiz_etapa(request, exploracao_id, etapa):
    if etapa not in ETAPAS:
        raise Http404
    try:
        tentativa = exploracao_de(request, exploracao_id)
        caminho = caminho_de(tentativa)
        if etapa not in caminho:
            return redirect("quiz_etapa", exploracao_id=exploracao_id, etapa=caminho[0])
        posicao = caminho.index(etapa)
        seguinte = caminho[min(posicao + 1, len(caminho) - 1)]
        recusa = ""
        if request.method == "POST":
            respostas = {}
            campos_etapa = CAMPOS_COMERCIAIS if comercial(tentativa) else CAMPOS_ETAPA
            for chave in campos_etapa[etapa]:
                if chave in LISTAS_COMERCIAIS:
                    respostas[chave] = request.POST.getlist(chave)
                elif chave in request.POST:
                    respostas[chave] = request.POST[chave]
            if etapa == "escolha_final":
                respostas["proposta_editada"] = edicoes_da_proposta(request, tentativa)
            try:
                quiz.chamar(
                    f"exploracoes/{exploracao_id}/respostas",
                    **dono(request),
                    dados={"etapa": seguinte, "respostas": respostas},
                )
                if request.POST.get("acao") == "salvar_sair":
                    return redirect("prancheta")
                return redirect(
                    "quiz_etapa", exploracao_id=exploracao_id, etapa=seguinte
                )
            except QuizRecusado as erro:
                recusa = str(erro)
                tentativa["respostas"].update(respostas)
        catalogo = quiz.chamar("catalogo", site_id=site_atual()) or {}
        trabalhos = list(Peca.objects.do_aluno(**dono(request)).order_by("ordem", "pk"))
        for trabalho in trabalhos:
            trabalho.nome_quiz = trabalho.legenda or f"Trabalho #{trabalho.pk}"
        proposta = proposta_de(tentativa)
        return desenhar(
            request,
            "quiz_autoral.html" if comercial(tentativa) else "quiz_autoral_legado.html",
            {
                "tentativa": tentativa,
                "respostas": tentativa["respostas"],
                "etapa": etapa,
                "titulo_etapa": (
                    TITULOS_COMERCIAIS[etapa] if comercial(tentativa) else ETAPAS[etapa]
                ),
                "passo": posicao + 1,
                "total_passos": len(caminho),
                "andamentos": ANDAMENTOS,
                "experiencias_comerciais": EXPERIENCIAS_COMERCIAIS,
                "experiencia_comercial": EXPERIENCIA_COMERCIAL,
                "situacoes_trabalhos": TRABALHOS,
                "caminhos_renda": CAMINHOS_RENDA,
                "publicos": PUBLICOS,
                "pecas_sugeridas": PECAS,
                "apresentacao_itens": APRESENTACAO_ITENS,
                "divulgacoes": DIVULGACOES,
                "trabalhos_existentes": trabalhos,
                "plano": proposta.get("plano", tentativa.get("plano", {})),
                "anterior": caminho[posicao - 1] if posicao else None,
                "familias": sorted(
                    catalogo.get("familias", []),
                    key=lambda item: (
                        [
                            "cabelos",
                            "roupas",
                            "chapeus",
                            "armas",
                            "objetos",
                            "animais",
                        ].index(item["chave"])
                        if item["chave"]
                        in {
                            "cabelos",
                            "roupas",
                            "chapeus",
                            "armas",
                            "objetos",
                            "animais",
                        }
                        else 6
                    ),
                ),
                "contextos": CONTEXTOS,
                "estilos": ESTILOS,
                "experiencias": EXPERIENCIAS,
                "tamanhos": TAMANHOS,
                "recusa": recusa,
                "campos_proposta": [
                    (chave, rotulo, proposta.get(chave, ""))
                    for chave, rotulo in CAMPOS_PROPOSTA.items()
                ],
                "proposta": proposta,
            },
            status=422 if recusa else 200,
        )
    except (QuizIndisponivel, QuizRecusado) as erro:
        return problema(request, erro)


@require_POST
def comecar_projeto(request, exploracao_id):
    try:
        tentativa = exploracao_de(request, exploracao_id)
        proposta = proposta_de(tentativa)
        proposta.update(
            {
                chave: request.POST.get(chave, proposta.get(chave, ""))
                for chave in CAMPOS_PROPOSTA
            }
        )
        proposta["titulo"] = proposta.get("titulo", "").strip() or "Meu projeto"
        quiz.chamar(
            f"exploracoes/{exploracao_id}/respostas",
            **dono(request),
            dados={
                "etapa": "escolha_final",
                "respostas": {
                    "proposta_editada": edicoes_da_proposta(request, tentativa)
                },
            },
        )
        projeto = projetos.criar_do_aluno(
            **dono(request),
            exploracao_id=exploracao_id,
            proposta_chave=tentativa["respostas"].get(
                "projeto_chave", proposta.get("chave", "proprio")
            ),
            proposta_dict=proposta,
        )
        return redirect("projeto", projeto_id=projeto.pk)
    except (QuizIndisponivel, QuizRecusado, ValueError) as erro:
        return problema(request, erro, 422 if isinstance(erro, ValueError) else 503)


@require_http_methods(["GET", "POST"])
def novo_projeto(request):
    recusa = ""
    if request.method == "POST":
        try:
            proposta = {chave: request.POST.get(chave, "") for chave in CAMPOS_PROPOSTA}
            proposta["titulo"] = proposta["titulo"].strip() or "Meu projeto"
            projeto = projetos.criar_do_aluno(**dono(request), proposta_dict=proposta)
            return redirect("projeto", projeto_id=projeto.pk)
        except (ValueError, QuizIndisponivel) as erro:
            recusa = str(erro)
    return desenhar(
        request,
        "projeto_novo.html",
        {
            "recusa": recusa,
            "campos_proposta": [
                (chave, rotulo, request.POST.get(chave, ""))
                for chave, rotulo in CAMPOS_PROPOSTA.items()
            ],
        },
        status=422 if recusa else 200,
    )


@require_http_methods(["GET", "POST"])
def projeto(request, projeto_id):
    item = get_object_or_404(
        ProjetoAutoral,
        pk=projeto_id,
        portfolio__site_id=site_atual(),
        portfolio__aluno_id=request.aluno["id"],
    )
    recusa = ""
    if request.method == "POST":
        try:
            if request.POST.get("acao") == "feedback":
                conferencia.pedir(
                    item.portfolio,
                    projeto=item,
                    duvida_aluno=request.POST.get("duvida_aluno", ""),
                )
            else:
                projetos.editar_do_aluno(
                    **dono(request),
                    projeto_id=projeto_id,
                    **{chave: request.POST.get(chave, "") for chave in CAMPOS_PROPOSTA},
                )
            return redirect("projeto", projeto_id=projeto_id)
        except (ValueError, conferencia.ConferenciaRecusada, QuizIndisponivel) as erro:
            recusa = str(erro)
    pedidos = list(
        item.portfolio.pedidos_de_conferencia.filter(projeto=item).order_by(
            "-criado_em"
        )
    )
    for pedido in pedidos:
        pedido.versao_atual = projetos.contexto_atual(pedido)
    return desenhar(
        request,
        "projeto.html",
        {
            "projeto": item,
            "trabalhos": item.pecas.all(),
            "pedidos": pedidos,
            "recusa": recusa,
            "campos_proposta": [
                (
                    chave,
                    rotulo,
                    (
                        request.POST.get(chave, getattr(item, chave, ""))
                        if recusa and request.POST.get("acao") != "feedback"
                        else getattr(item, chave, "")
                    ),
                )
                for chave, rotulo in CAMPOS_PROPOSTA.items()
            ],
        },
        status=422 if recusa else 200,
    )


@require_POST
def contexto_trabalho(request, peca_id):
    item = get_object_or_404(Peca.objects.do_aluno(**dono(request)), pk=peca_id)
    identificador = request.POST.get("projeto_id", "")
    try:
        projeto_escolhido = (
            get_object_or_404(
                ProjetoAutoral, pk=identificador, portfolio=item.portfolio
            )
            if identificador
            else None
        )
    except (ValidationError, ValueError):
        raise Http404 from None
    campos = ("legenda", "uso_pretendido", "contribuicao", "duvida")
    for chave in campos:
        valor = request.POST.get(chave, "").strip()
        if len(valor) > (200 if chave == "legenda" else 3000):
            return problema(
                request,
                "O texto está muito longo. Use até 200 caracteres no título e 3000 nos demais campos.",
                422,
            )
        setattr(item, chave, valor)
    item.projeto = projeto_escolhido
    item.mostrar_na_pagina_publica = (
        request.POST.get("mostrar_na_pagina_publica") == "1"
    )
    item.save(
        update_fields=[*campos, "projeto", "mostrar_na_pagina_publica", "atualizada_em"]
    )
    return redirect("pecas")


@require_http_methods(["GET", "POST"])
def apresentacao_publica(request):
    escola = site_atual()
    if not escola:
        return sem_escola(request)
    portfolio = Portfolio.objects.do_aluno(**dono(request)).first()
    if request.method == "POST":
        textos = {
            chave: request.POST.get(chave, "").strip()
            for chave in ("apresentacao_publica", "servico_publico")
        }
        if any(len(valor) > 3000 for valor in textos.values()):
            return problema(
                request, "Use até 3000 caracteres em cada texto da apresentação.", 422
            )
        with transaction.atomic():
            portfolio, _ = Portfolio.objects.get_or_create(**dono(request))
            for chave, valor in textos.items():
                setattr(portfolio, chave, valor)
            portfolio.save(update_fields=list(textos))
        return redirect("apresentacao_publica")
    return desenhar(
        request,
        "apresentacao.html",
        {
            "portfolio": portfolio,
            "selecionados": (
                portfolio.pecas.filter(mostrar_na_pagina_publica=True)
                if portfolio
                else []
            ),
        },
    )


@require_http_methods(["GET", "POST"])
def catalogo_equipe(request, chave=None):
    try:
        catalogo = quiz.chamar("catalogo", site_id=site_atual())
        if not catalogo:
            raise QuizIndisponivel("A biblioteca do quiz não está disponível agora.")
        item = next(
            (item for item in catalogo.get("projetos", []) if item["chave"] == chave),
            None,
        )
        if chave and not item:
            raise Http404
        if request.method == "POST" and item:
            for campo in CAMPOS_PROPOSTA:
                if campo in request.POST:
                    item[campo] = request.POST[campo]
            quiz.chamar("catalogo", site_id=site_atual(), dados={"catalogo": catalogo})
            return redirect("catalogo_equipe")
        return desenhar(
            request,
            "catalogo_equipe.html",
            {
                "catalogo": catalogo,
                "item": item,
                "campos_proposta": (
                    [
                        (chave, rotulo, item.get(chave, ""))
                        for chave, rotulo in CAMPOS_PROPOSTA.items()
                    ]
                    if item
                    else []
                ),
            },
        )
    except (QuizIndisponivel, QuizRecusado) as erro:
        return problema(request, erro)
