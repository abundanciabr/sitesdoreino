"""Jornada privada de criação do portfólio, separada do Crivo comercial."""

import copy
import json
import re
import secrets
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.http import FileResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from .models import PortfolioCatalog, PortfolioExploration, Site


ENTRADAS = {"descobrir", "ideia", "prontos"}
ETAPAS = {
    "interesses",
    "contexto",
    "ponto_partida",
    "projeto",
    "apresentacao",
    "escolha_final",
}
LISTAS = {
    "interesses",
    "contextos",
    "estilos",
    "trabalhos_selecionados",
    "proximas_pecas",
    "apresentacao_itens",
}
OPCOES = {
    "experiencia": {"iniciante", "intermediario", "avancado", "nao_sei"},
    "andamento_curso": {"nao_comecou", "comeco", "meio", "final", "concluido"},
    "experiencia_comercial": {"nunca", "encomendas", "profissional"},
    "tem_trabalhos": {"nenhum", "rascunhos", "prontos"},
    "caminho_comercial": {"experiencias", "ugc_clientes", "marketplace", "explorar"},
    "publico": {"criadores", "marcas", "equipes_marcas", "jogadores", "descobrir"},
    "oferta_exibir_preco": {"sim", "nao"},
    "pronta_entrega": {"desenvolvimento", "comercial"},
    "primeira_peca": {"cabelo", "roupa", "chapeu", "outra", "nenhuma"},
    "acrescentar": {"sim", "nao"},
    "divulgacao": {"pagina", "comunidades", "marketplace", "descobrir"},
}
PECAS = {"cabelo", "roupa", "chapeu", "outra"}
APRESENTACAO = {"imagens", "descricao", "roblox"}
TEXTOS = {
    "ideia_propria": 3000,
    "modelos_prontos": 3000,
    "experiencia": 100,
    "dificuldade": 3000,
    "tamanho": 100,
    "habilidade": 3000,
    "projeto_chave": 100,
    "objetivo_apresentacao": 3000,
    "servico_proprio": 3000,
    "primeira_acao": 3000,
    **{f"oferta_{campo}": 3000 for campo in (
        "encomenda", "comprador", "uso", "entregaveis", "formatos",
        "prazo", "revisoes", "suporte", "preco", "moeda",
        "condicoes", "continuidade", "contato",
    )},
    **{campo: 100 for campo in OPCOES},
}
PROPOSTA_CAMPOS = {
    "chave": 100,
    "titulo": 200,
    "descricao": 3000,
    "direcao": 3000,
    "intencao": 3000,
    "aplicacao": 3000,
    "servico": 3000,
    "primeira_entrega": 3000,
    "aprendizagem": 3000,
    "apresentacao": 3000,
    "primeira_acao": 3000,
    "por_que": 3000,
    "referencia": 250,
}
CATALOGO_ARQUIVO = Path(__file__).with_name("portfolio_catalogo.json")
REFERENCIAS = Path(settings.BASE_DIR) / "static" / "quiz" / "portfolio"
REFERENCIA_PREFIXO = "/quiz/portfolio/referencias/"
FAMILIAS_COMERCIAIS = {"cabelos", "roupas", "chapeus", "armas", "animais"}


def _erro(mensagem, status=400):
    return JsonResponse({"detail": mensagem}, status=status)


def _autorizado(request):
    esquema, _, token = request.headers.get("Authorization", "").partition(" ")
    aceitos = [
        item.strip()
        for item in settings.TOKENS_ACEITOS_PAGES.split(",")
        if item.strip()
    ]
    return (
        esquema.lower() == "bearer"
        and bool(token)
        and any(secrets.compare_digest(token, aceito) for aceito in aceitos)
    )


def _json(request):
    if len(request.body) > 160_000:
        raise ValueError("Conteúdo excede o tamanho permitido.")
    try:
        dados = json.loads(request.body)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("JSON inválido.") from None
    if not isinstance(dados, dict):
        raise ValueError("Envie um objeto JSON.")
    return dados


def _identidade(dados):
    site_id = dados.get("site_id")
    aluno_id = dados.get("aluno_id")
    if not isinstance(site_id, str) or not 1 <= len(site_id) <= 64:
        raise ValueError("site_id inválido.")
    if not isinstance(aluno_id, str) or not 1 <= len(aluno_id) <= 64:
        raise ValueError("aluno_id inválido.")
    site = Site.objects.filter(pk=site_id, active=True).first()
    if site is None:
        raise LookupError("Site desconhecido ou inativo.")
    return site, aluno_id


def _site(dados):
    site_id = dados.get("site_id")
    if not isinstance(site_id, str) or not 1 <= len(site_id) <= 64:
        raise ValueError("site_id inválido.")
    site = Site.objects.filter(pk=site_id, active=True).first()
    if site is None:
        raise LookupError("Site desconhecido ou inativo.")
    return site


def _texto(valor, limite, nome):
    if not isinstance(valor, str) or len(valor) > limite:
        raise ValueError(f"{nome} inválido (máximo {limite} caracteres).")
    return valor.strip()


def _referencia(valor):
    if valor and (
        not valor.startswith(REFERENCIA_PREFIXO)
        or not re.fullmatch(r"/quiz/portfolio/referencias/[a-z0-9_-]+\.svg", valor)
    ):
        raise ValueError("Referência deve apontar para uma imagem própria do quiz.")
    return valor


def _validar_catalogo(catalogo):
    if not isinstance(catalogo, dict):
        raise ValueError("Catálogo inválido.")
    familias = catalogo.get("familias")
    projetos = catalogo.get("projetos")
    if not isinstance(familias, list) or not 1 <= len(familias) <= 30:
        raise ValueError("Informe de 1 a 30 famílias.")
    if not isinstance(projetos, list) or not 1 <= len(projetos) <= 100:
        raise ValueError("Informe de 1 a 100 projetos.")
    familias_chaves = set()
    for familia in familias:
        if not isinstance(familia, dict):
            raise ValueError("Família inválida.")
        chave = _texto(familia.get("chave"), 100, "chave da família")
        if not re.fullmatch(r"[a-z0-9_-]+", chave) or chave in familias_chaves:
            raise ValueError("Chave de família inválida ou repetida.")
        familias_chaves.add(chave)
        _texto(familia.get("nome"), 200, "nome da família")
        _texto(familia.get("descricao", ""), 1000, "descrição da família")
    projetos_chaves = set()
    for projeto in projetos:
        if not isinstance(projeto, dict):
            raise ValueError("Projeto inválido.")
        chave = _texto(projeto.get("chave"), 100, "chave do projeto")
        if not re.fullmatch(r"[a-z0-9_-]+", chave) or chave in projetos_chaves:
            raise ValueError("Chave de projeto inválida ou repetida.")
        projetos_chaves.add(chave)
        if projeto.get("familia") not in familias_chaves:
            raise ValueError("Projeto aponta para família desconhecida.")
        _texto(projeto.get("titulo"), 200, "titulo")
        for campo in (
            "descricao",
            "direcao",
            "aplicacao",
            "servico",
            "primeira_entrega",
            "aprendizagem",
            "apresentacao",
            "primeira_acao",
        ):
            _texto(projeto.get(campo), 3000, campo)
        _referencia(_texto(projeto.get("referencia", ""), 250, "referencia"))
        for campo in ("contextos", "estilos", "escopos"):
            valores = projeto.get(campo, [])
            if not isinstance(valores, list) or len(valores) > 30:
                raise ValueError(f"{campo} inválido.")
            for valor in valores:
                _texto(valor, 100, campo)
        for campo in ("versao_pequena", "expansao", "feedback"):
            valor = projeto.get(campo, "")
            if isinstance(valor, str):
                _texto(valor, 3000, campo)
            elif isinstance(valor, list) and len(valor) <= 20:
                for item in valor:
                    _texto(item, 500, campo)
            else:
                raise ValueError(f"{campo} inválido.")
    return catalogo


def _catalogo(site):
    publicado = PortfolioCatalog.objects.filter(site=site).order_by("-version").first()
    with CATALOGO_ARQUIVO.open(encoding="utf-8") as arquivo:
        base = _validar_catalogo(json.load(arquivo))
    if not publicado:
        return base, str(base.get("versao", "2"))
    # Preserve school edits; add only commercial choices absent from older catalogs.
    catalogo = copy.deepcopy(publicado.content)
    familias = {item["chave"] for item in catalogo["familias"]}
    projetos = {item["chave"] for item in catalogo["projetos"]}
    catalogo["familias"].extend(
        copy.deepcopy(item)
        for item in base["familias"]
        if item["chave"] in FAMILIAS_COMERCIAIS and item["chave"] not in familias
    )
    catalogo["projetos"].extend(
        copy.deepcopy(item)
        for item in base["projetos"]
        if item["familia"] in FAMILIAS_COMERCIAIS and item["chave"] not in projetos
    )
    catalogo["fluxo_versao"] = "comercial"
    return catalogo, str(publicado.version)


def _validar_respostas(respostas, *, comercial=True):
    if not isinstance(respostas, dict) or len(respostas) > 50:
        raise ValueError("Respostas inválidas.")
    desconhecidos = set(respostas) - LISTAS - set(TEXTOS) - {"proposta_editada"}
    if desconhecidos:
        raise ValueError("Campo de resposta desconhecido.")
    validadas = {}
    for campo, valor in respostas.items():
        if campo in LISTAS:
            limite = 30 if campo == "trabalhos_selecionados" else 20
            if not isinstance(valor, list) or len(valor) > limite:
                raise ValueError(f"{campo} inválido.")
            tamanho = 200 if campo == "trabalhos_selecionados" else 100
            validadas[campo] = [_texto(item, tamanho, campo) for item in valor]
            if campo == "proximas_pecas" and set(valor) - PECAS:
                raise ValueError(f"{campo} inválido.")
            if campo == "apresentacao_itens" and set(valor) - APRESENTACAO:
                raise ValueError(f"{campo} inválido.")
        elif campo in TEXTOS:
            validadas[campo] = _texto(valor, TEXTOS[campo], campo)
            if comercial and campo in OPCOES and valor and valor not in OPCOES[campo]:
                raise ValueError(f"{campo} inválido.")
        else:
            if not isinstance(valor, dict) or set(valor) - set(PROPOSTA_CAMPOS):
                raise ValueError("proposta_editada inválida.")
            validadas[campo] = {
                chave: (
                    _referencia(_texto(item, limite, chave))
                    if chave == "referencia"
                    else _texto(item, limite, chave)
                )
                for chave, item in valor.items()
                for limite in [PROPOSTA_CAMPOS[chave]]
            }
    return validadas


def _proposta(projeto, motivo, respostas):
    campos = (
        "chave",
        "titulo",
        "descricao",
        "direcao",
        "aplicacao",
        "servico",
        "primeira_entrega",
        "aprendizagem",
        "apresentacao",
        "primeira_acao",
        "referencia",
    )
    proposta = {campo: projeto.get(campo, "") for campo in campos}
    proposta["intencao"] = respostas.get("ideia_propria") or projeto.get("intencao", "")
    proposta["por_que"] = motivo
    proposta["expansao"] = projeto.get("expansao", "")
    proposta["feedback"] = projeto.get("feedback", "")
    if respostas.get("tamanho") == "um" and projeto.get("versao_pequena"):
        proposta["primeira_entrega"] = projeto["versao_pequena"]
    if respostas.get("habilidade"):
        proposta["aprendizagem"] = respostas["habilidade"]
    if respostas.get("servico_proprio"):
        proposta["servico"] = respostas["servico_proprio"]
    if respostas.get("objetivo_apresentacao"):
        proposta["apresentacao"] = respostas["objetivo_apresentacao"]
    if respostas.get("primeira_acao"):
        proposta["primeira_acao"] = respostas["primeira_acao"]
    return proposta


def _plano(respostas, proposta=None):
    """Concrete portfolio composition from the student's own commercial choices."""
    proposta = proposta or {}
    caminho = respostas.get("caminho_comercial", "explorar")
    servicos = {
        "experiencias": "Modelagem por encomenda para experiências Roblox",
        "ugc_clientes": "Criação de acessórios ou itens UGC para clientes",
        "marketplace": "Criação de itens próprios para vender no Marketplace",
        "explorar": "Explorar encomendas para experiências, UGC para clientes e itens próprios",
    }
    publicos = {
        "criadores": "criadores de experiências Roblox",
        "marcas": "marcas e clientes",
        "equipes_marcas": "equipes de marcas que encomendam experiências ou itens Roblox",
        "jogadores": "jogadores e compradores",
        "descobrir": "público a definir ao apresentar os primeiros trabalhos",
    }
    nomes = {
        "cabelo": "um cabelo",
        "roupa": "uma roupa 3D (Layered Clothing)",
        "chapeu": "um chapéu ou acessório de cabeça",
        "outra": "outra criação 3D",
    }
    existentes = list(respostas.get("trabalhos_selecionados", []))
    for nome in re.split(r"[;\r\n]+", respostas.get("modelos_prontos", "")):
        nome = nome.strip()
        if nome and nome.casefold() not in {item.casefold() for item in existentes}:
            existentes.append(nome)
    tem = respostas.get("tem_trabalhos", "prontos" if existentes else "nenhum")
    experiencia = respostas.get("experiencia", "nao_sei")
    momento_aluno = {
        "iniciante": "Você está começando: organize sua primeira versão com trabalhos que já fez ou uma única peça.",
        "intermediario": "Você já conclui trabalhos: selecione os que demonstram seu serviço e acrescente peças para buscar novas encomendas.",
        "avancado": "Você já tem experiência: organize serviço, público e clientes, aproveitando trabalhos profissionais que tem autorização para apresentar.",
        "nao_sei": (
            "Use os trabalhos que já possui para decidir o caminho do seu portfólio."
            if existentes or tem != "nenhum"
            else "Comece com uma peça e descubra o caminho a partir dela."
        ),
    }
    primeira_codigo = respostas.get("primeira_peca", "nenhuma")
    primeira = nomes.get(primeira_codigo, "")
    if primeira_codigo == "outra" and proposta.get("titulo"):
        primeira = proposta["titulo"]
    if primeira_codigo == "nenhuma":
        primeira = ""
    if not existentes and not primeira:
        primeira = proposta.get("titulo") or "uma peça 3D à sua escolha"
    if (
        primeira
        and respostas.get("ideia_propria")
        and primeira_codigo in {"cabelo", "roupa", "chapeu"}
    ):
        primeira += ": " + respostas["ideia_propria"][:200]
    acrescentar = respostas.get("acrescentar")
    composicao = list(existentes)
    if not existentes or acrescentar == "sim":
        if primeira and primeira.casefold() not in {
            item.casefold() for item in composicao
        }:
            composicao.append(primeira)
    elif acrescentar == "nao":
        primeira = "Organizar os trabalhos existentes; nenhuma peça nova agora."
    proximos = [nomes[item] for item in respostas.get("proximas_pecas", [])]
    if not proximos:
        proximos = (
            [
                "Outro cabelo no seu estilo",
                "Uma roupa 3D (Layered Clothing)",
                "Um chapéu ou acessório de cabeça",
            ]
            if caminho in {"ugc_clientes", "marketplace", "explorar"}
            else [
                "Um objeto para uma experiência Roblox",
                "Uma espada ou arma para o jogo",
                "Um animal para uma experiência Roblox",
            ]
        )
    formatos = {
        "imagens": "imagens claras de vários ângulos",
        "descricao": "descrição do trabalho e do que pode ser entregue",
        "roblox": "exemplo de uso no Roblox",
    }
    itens = respostas.get("apresentacao_itens") or []
    apresentacao = [formatos[item] for item in list(dict.fromkeys([*itens, *formatos]))]
    curso = respostas.get("andamento_curso", "")
    continuidade = {
        "nao_comecou": "Ao começar o curso, acrescente novas peças no seu ritmo.",
        "comeco": "No começo do curso, apresente o que já tem e acrescente peças aos poucos.",
        "meio": "Na metade do curso, revise os trabalhos concluídos e amplie a seleção conforme seu objetivo.",
        "final": "Perto do final do curso, revise a apresentação e escolha o que ainda deseja acrescentar.",
        "concluido": "Com o curso concluído, mantenha o portfólio atualizado com trabalhos que demonstram seu serviço.",
    }.get(curso, "Acrescente trabalhos conforme desenvolver novas peças.")
    meta = (
        "Meta desejável da escola até o final do curso para um portfólio UGC, se fizer sentido para seus objetivos: "
        "3 cabelos, 3 roupas 3D (Layered Clothing) e 3 chapéus ou acessórios de cabeça. "
        "Comece com o que já tem ou com uma peça; essa meta não é requisito inicial, para publicar ou buscar clientes."
        if caminho in {"ugc_clientes", "marketplace", "explorar"}
        else ""
    )
    divulgacoes = {
        "pagina": "Apresente os trabalhos na sua página pública de portfólio.",
        "comunidades": "Mostre o portfólio a criadores e comunidades relacionados ao serviço escolhido.",
        "marketplace": "Prepare a apresentação dos itens próprios para compradores no Marketplace.",
        "descobrir": "Comece pela página pública e escolha onde mostrar os trabalhos conforme seu público.",
    }
    canal = respostas.get("divulgacao") or (
        "marketplace" if caminho == "marketplace" else "pagina"
    )
    if canal == "marketplace" and caminho != "marketplace":
        canal = (
            "comunidades"
            if caminho in {"experiencias", "ugc_clientes"}
            else "descobrir"
        )
    if caminho == "explorar":
        divulgacao = "Compare três possibilidades: encomendas para experiências Roblox, UGC para clientes e itens próprios no Marketplace. Mostre primeiro seus trabalhos na página pública."
    else:
        divulgacao = divulgacoes[canal]
    if caminho == "explorar":
        acao = "Escolher qual dos três caminhos comerciais combina com os trabalhos que deseja apresentar."
    elif not existentes and primeira:
        acao = f"Criar {primeira} e preparar {apresentacao[0] if apresentacao else 'sua apresentação'} para o portfólio."
    elif existentes:
        acao = f"Organizar {existentes[0]} com {apresentacao[0] if apresentacao else 'uma apresentação clara'} na página pública."
    else:
        acao = "Selecionar um trabalho existente ou escolher uma primeira peça para apresentar."
    if (
        caminho != "explorar"
        and respostas.get("pronta_entrega") == "desenvolvimento"
        and existentes
    ):
        acao = f"Concluir e revisar {existentes[0]} antes de apresentá-lo como entrega comercial."
    elif (
        caminho != "explorar"
        and respostas.get("pronta_entrega") == "comercial"
        and existentes
    ):
        acao = f"Preparar {existentes[0]} para mostrar a {publicos.get(respostas.get('publico', 'descobrir'))}."
    razoes = [
        (
            "Você já tem trabalhos para apresentar; escolha os que mostram seu serviço."
            if existentes
            else "Uma peça concreta permite iniciar o portfólio no seu ritmo."
        )
    ]
    if respostas.get("experiencia_comercial") in {"encomendas", "profissional"}:
        razoes.append(
            "Aproveite trabalhos de encomenda ou profissionais que possa apresentar."
        )
    elif respostas.get("experiencia_comercial") == "nunca":
        razoes.append(
            "Sua primeira apresentação pode mostrar capacidade de entrega mesmo antes da primeira encomenda."
        )
    if respostas.get("pronta_entrega") == "desenvolvimento":
        razoes.append(
            "Identifique peças em desenvolvimento antes de oferecê-las como entrega comercial."
        )
    razoes.append(continuidade)
    oferta_campos = (
        "encomenda", "comprador", "uso", "entregaveis", "formatos",
        "prazo", "revisoes", "suporte", "preco", "moeda",
        "condicoes", "continuidade", "contato", "exibir_preco",
    )
    oferta_comercial = {
        campo: respostas.get(f"oferta_{campo}", "") for campo in oferta_campos
    }
    oferta_comercial["encomenda"] = (
        oferta_comercial["encomenda"]
        or respostas.get("servico_proprio")
        or servicos[caminho]
    )
    oferta_comercial["comprador"] = (
        oferta_comercial["comprador"]
        or publicos.get(respostas.get("publico", "descobrir"), "")
    )
    return {
        "servico": respostas.get("servico_proprio") or servicos[caminho],
        "publico": publicos.get(respostas.get("publico", "descobrir")),
        "trabalhos_existentes": existentes,
        "primeira_peca": primeira
        or "Organizar os trabalhos existentes; nenhuma peça nova agora.",
        "apresentacao": apresentacao,
        "composicao_inicial": composicao,
        "proximos_trabalhos": proximos,
        "meta_escola": meta,
        "divulgacao": divulgacao,
        "proxima_acao": respostas.get("primeira_acao") or acao,
        "momento": momento_aluno[experiencia],
        "continuidade": continuidade,
        "objetivo_apresentacao": respostas.get("objetivo_apresentacao", ""),
        "por_que": " ".join(razoes),
        "oferta_comercial": oferta_comercial,
    }


def _propostas(exploracao):
    respostas = exploracao.respostas
    comercial = exploracao.catalogo_snapshot.get("fluxo_versao") == "comercial"
    projetos = exploracao.catalogo_snapshot.get("projetos", [])
    interesses = set(respostas.get("interesses", []))
    contextos = set(respostas.get("contextos", []))
    estilos = set(respostas.get("estilos", []))
    escolha = respostas.get("projeto_chave", "")
    caminho = respostas.get("caminho_comercial", "explorar")
    primeira = respostas.get("primeira_peca", "")
    por_peca = {
        "cabelo": "cabelos",
        "roupa": "roupas",
        "chapeu": "chapeus",
        "outra": "objetos",
    }
    prioridades = (
        ["cabelos", "roupas", "chapeus", "objetos", "armas", "animais"]
        if caminho in {"ugc_clientes", "marketplace", "explorar"}
        else [
            "objetos",
            "armas",
            "animais",
            "veiculos",
            "construcoes",
            "mobiliario",
            "natureza",
            "personagens",
        ]
    )
    if primeira in por_peca:
        familia = por_peca[primeira]
        prioridades = [familia, *[item for item in prioridades if item != familia]]

    def ordem(projeto):
        return (
            0 if projeto.get("chave") == escolha else 1,
            0 if projeto.get("familia") in interesses else 1,
            (
                prioridades.index(projeto.get("familia"))
                if comercial and projeto.get("familia") in prioridades
                else len(prioridades)
            ),
            0 if contextos.intersection(projeto.get("contextos", [])) else 1,
            0 if estilos.intersection(projeto.get("estilos", [])) else 1,
            projeto.get("chave", ""),
        )

    sugestoes = []
    ideia = respostas.get("ideia_propria") or (
        respostas.get("modelos_prontos") if exploracao.entrada == "prontos" else ""
    )
    if ideia and escolha in {"", "ideia-do-aluno", "proprio"}:
        sugestoes.append(
            {
                "chave": "ideia-do-aluno",
                "titulo": ideia[:100],
                "descricao": ideia,
                "direcao": "Sua ideia",
                "aplicacao": respostas.get("objetivo_apresentacao", ""),
                "intencao": ideia,
                "servico": respostas.get("servico_proprio", ""),
                "primeira_entrega": "Selecione uma parte para começar ou apresente os modelos que já criou.",
                "aprendizagem": respostas.get("habilidade", ""),
                "apresentacao": respostas.get("objetivo_apresentacao", ""),
                "primeira_acao": respostas.get(
                    "primeira_acao", "Definir a primeira entrega."
                ),
                "por_que": "Você descreveu esta ideia como seu ponto de partida.",
                "referencia": "",
                "expansao": "",
                "feedback": "",
            }
        )
    if interesses and any(projeto.get("familia") in interesses for projeto in projetos):
        projetos = [
            projeto
            for projeto in projetos
            if projeto.get("familia") in interesses or projeto.get("chave") == escolha
        ]
    for projeto in sorted(projetos, key=ordem):
        if len(sugestoes) == 3:
            break
        if projeto.get("chave") == escolha:
            motivo = "Você escolheu este projeto diretamente."
        elif projeto.get("familia") in interesses:
            motivo = "Você escolheu esta família de criações."
        elif contextos.intersection(projeto.get("contextos", [])):
            motivo = "Este projeto combina com o contexto que você escolheu."
        elif estilos.intersection(projeto.get("estilos", [])):
            motivo = "Este projeto combina com o estilo que você escolheu."
        else:
            motivo = "Uma possibilidade para explorar e adaptar do seu jeito."
        sugestoes.append(_proposta(projeto, motivo, respostas))
    if comercial:
        for proposta in sugestoes:
            plano = _plano(respostas, proposta)
            proposta["plano"] = plano
            proposta["servico"] = plano["servico"]
            proposta["descricao"] = (
                f"{proposta['descricao']} No portfólio, esta peça mostra {plano['servico'].lower()} para {plano['publico']}.".strip()
            )
            proposta["direcao"] = plano["servico"]
            proposta["primeira_entrega"] = plano["primeira_peca"] or (
                plano["composicao_inicial"][0]
                if plano["composicao_inicial"]
                else "Escolher uma primeira peça."
            )
            proposta["aprendizagem"] = ""
            proposta["apresentacao"] = "; ".join(plano["apresentacao"])
            if plano["objetivo_apresentacao"]:
                proposta[
                    "apresentacao"
                ] += f". Objetivo: {plano['objetivo_apresentacao']}"
            proposta["primeira_acao"] = plano["proxima_acao"]
            proposta["expansao"] = "; ".join(plano["proximos_trabalhos"])
            proposta["feedback"] = ""
            proposta["por_que"] = f"{proposta['por_que']} {plano['por_que']}"
    return sugestoes


def _serializar(exploracao):
    comercial = exploracao.catalogo_snapshot.get("fluxo_versao") == "comercial"
    propostas = _propostas(exploracao)
    resultado = {
        "id": str(exploracao.id),
        "entrada": exploracao.entrada,
        "etapa": exploracao.etapa,
        "respostas": exploracao.respostas,
        "versao": exploracao.versao,
        "propostas": propostas,
        "fluxo_versao": "comercial" if comercial else "legado",
    }
    if comercial:
        escolhida = next(
            (
                p
                for p in propostas
                if p.get("chave") == exploracao.respostas.get("projeto_chave")
            ),
            None,
        )
        resultado["plano"] = _plano(
            exploracao.respostas, escolhida or (propostas[0] if propostas else None)
        )
    return resultado


@csrf_exempt
def catalogo(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method not in {"GET", "POST"}:
        return _erro("Método não permitido.", 405)
    try:
        dados = request.GET if request.method == "GET" else _json(request)
        site = _site(dados)
        if request.method == "GET":
            conteudo, versao = _catalogo(site)
            return JsonResponse({**conteudo, "versao": versao})
        if set(dados) != {"site_id", "catalogo"}:
            raise ValueError("Envie site_id e catalogo.")
        conteudo = _validar_catalogo(dados["catalogo"])
        if len(json.dumps(conteudo, ensure_ascii=False)) > 120_000:
            raise ValueError("Catálogo excede o tamanho permitido.")
        with transaction.atomic():
            Site.objects.select_for_update().get(pk=site.pk)
            atual = (
                PortfolioCatalog.objects.filter(site=site).order_by("-version").first()
            )
            nova_versao = (atual.version + 1) if atual else 2
            salvo = copy.deepcopy(conteudo)
            salvo["versao"] = str(nova_versao)
            PortfolioCatalog.objects.create(
                site=site, version=nova_versao, content=salvo
            )
        return JsonResponse(salvo, status=201)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    except (OSError, json.JSONDecodeError):
        return _erro("Catálogo indisponível.", 503)


@csrf_exempt
def exploracoes(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "POST":
        return _erro("Método não permitido.", 405)
    try:
        dados = _json(request)
        if set(dados) - {"site_id", "aluno_id", "entrada", "nova"}:
            raise ValueError("Campo desconhecido.")
        site, aluno_id = _identidade(dados)
        entrada = dados.get("entrada")
        if entrada not in ENTRADAS or not isinstance(dados.get("nova", False), bool):
            raise ValueError("Entrada ou nova inválida.")
        with transaction.atomic():
            # Serializa dois POSTs da mesma conta sem apagar tentativas anteriores.
            Site.objects.select_for_update().get(pk=site.pk)
            atual = (
                PortfolioExploration.objects.filter(site=site, aluno_id=aluno_id)
                .order_by("-created_at", "-id")
                .first()
            )
            if atual and not dados.get("nova", False):
                return JsonResponse(_serializar(atual))
            conteudo, versao = _catalogo(site)
            exploracao = PortfolioExploration.objects.create(
                site=site,
                aluno_id=aluno_id,
                entrada=entrada,
                etapa="ponto_partida",
                versao=versao,
                catalogo_snapshot=conteudo,
            )
        return JsonResponse(_serializar(exploracao), status=201)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    except (OSError, json.JSONDecodeError):
        return _erro("Catálogo indisponível.", 503)


def exploracao_atual(request):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "GET":
        return _erro("Método não permitido.", 405)
    try:
        site, aluno_id = _identidade(request.GET)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    tentativas = list(
        PortfolioExploration.objects.filter(site=site, aluno_id=aluno_id).order_by(
            "-created_at", "-id"
        )[:51]
    )
    if not tentativas:
        return _erro("Exploração não encontrada.", 404)
    resultado = _serializar(tentativas[0])
    resultado["historico"] = [
        {
            "id": str(item.id),
            "etapa": item.etapa,
            "entrada": item.entrada,
            "fluxo_versao": (
                "comercial"
                if item.catalogo_snapshot.get("fluxo_versao") == "comercial"
                else "legado"
            ),
        }
        for item in tentativas[1:]
    ]
    return JsonResponse(resultado)


@csrf_exempt
def exploracao(request, exploracao_id):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "GET":
        return _erro("Método não permitido.", 405)
    try:
        site, aluno_id = _identidade(request.GET)
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)
    registro = PortfolioExploration.objects.filter(
        pk=exploracao_id, site=site, aluno_id=aluno_id
    ).first()
    return (
        JsonResponse(_serializar(registro))
        if registro
        else _erro("Exploração não encontrada.", 404)
    )


@csrf_exempt
def respostas(request, exploracao_id):
    if not _autorizado(request):
        return _erro("Não autorizado.", 401)
    if request.method != "POST":
        return _erro("Método não permitido.", 405)
    try:
        dados = _json(request)
        if set(dados) != {"site_id", "aluno_id", "etapa", "respostas"}:
            raise ValueError("Envie site_id, aluno_id, etapa e respostas.")
        site, aluno_id = _identidade(dados)
        etapa = dados["etapa"]
        if etapa not in ETAPAS:
            raise ValueError("Etapa inválida.")
        with transaction.atomic():
            registro = (
                PortfolioExploration.objects.select_for_update()
                .filter(pk=exploracao_id, site=site, aluno_id=aluno_id)
                .first()
            )
            if registro is None:
                return _erro("Exploração não encontrada.", 404)
            novas = _validar_respostas(
                dados["respostas"],
                comercial=registro.catalogo_snapshot.get("fluxo_versao") == "comercial",
            )
            atualizadas = {**registro.respostas, **novas}
            if "proposta_editada" in novas:
                atualizadas["proposta_editada"] = {
                    **registro.respostas.get("proposta_editada", {}),
                    **novas["proposta_editada"],
                }
            registro.respostas = atualizadas
            registro.etapa = etapa
            registro.save(update_fields=["respostas", "etapa", "updated_at"])
        return JsonResponse(_serializar(registro))
    except ValueError as exc:
        return _erro(str(exc))
    except LookupError as exc:
        return _erro(str(exc), 404)


def referencia(request, chave):
    # Referências são obras próprias e públicas, sem dados de aluno.
    arquivo = REFERENCIAS / f"{chave}.svg"
    if not arquivo.is_file():
        return _erro("Imagem não encontrada.", 404)
    return FileResponse(arquivo.open("rb"), content_type="image/svg+xml")
