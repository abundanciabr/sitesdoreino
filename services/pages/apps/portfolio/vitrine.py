"""Página pública em /portfolio/<apelido>, disponível apenas após publicação.

ci:texto-publicado

O prefixo compartilhado com a área privada é aplicado uma vez ao link público.
A autorização distingue as rotas resolvidas, não o prefixo comum.
"""

from __future__ import annotations

import re
import unicodedata
from types import SimpleNamespace
from urllib.parse import urlsplit

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.portfolio.models import EstadoDoLink, Peca, Portfolio
from apps.core.enderecos import PREFIXO, RESERVADOS

#: O prefixo do endereço público é compartilhado com a área privada.
PREFIXO_PUBLICO = PREFIXO

#: O tamanho do apelido é o da coluna (`Portfolio.apelido`), e não um número
#: novo: dois limites para o mesmo fato divergem no dia em que um deles mudar.
LIMITE_DO_APELIDO = Portfolio._meta.get_field("apelido").max_length


class VitrineRecusada(Exception):
    """O gesto não pode acontecer, e o motivo é regra, não erro de programa.

    Uma exceção, e não um `return None`, pelo mesmo motivo do
    `conferencia.ConferenciaRecusada`: quem chama é uma tela, e uma tela que
    recebe `None` mostra "nada aconteceu", que é o que uma pessoa recusada NÃO
    pode ver. A mensagem é escrita para ser lida por gente.
    """


SEM_LETRA_NEM_NUMERO = (
    "Escolha um endereço com letras e números, por exemplo ana-3d. Ele é o "
    "final do link que você manda ao cliente."
)

JA_E_DE_OUTRO = (
    "Este endereço já é de outro aluno da escola. Escolha outro, por exemplo "
    "com o seu sobrenome ou com o nome do seu estúdio."
)


def endereco(apelido: str) -> str:
    """O endereço público completo desta vitrine, do jeito que o aluno o copia."""
    return f"{PREFIXO_PUBLICO}/{apelido}"


def apelido_de(texto: str) -> str:
    """O que a pessoa digitou vira o endereço que a máquina liga.

    O aluno escreve "Ana 3D" e o endereço precisa de `ana-3d`. Pedir os dois
    seria pedir a ele que entendesse a diferença, e recusar o que ele digitou
    seria fazê-lo adivinhar o formato. O resultado aparece inteiro na tela, para
    ele conferir antes de mandar o link a alguém.

    O formato é o mesmo que o banco exige em `apelido_e_endereco_web`, e o vazio
    é a resposta para o que não tem nenhuma letra nem número aproveitável.
    """
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c)).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo).strip("-")
    return limpo[:LIMITE_DO_APELIDO].strip("-")


def publicar(*, site_id: str, aluno_id: str, texto: str) -> Portfolio:
    """O aluno liga a vitrine, com o endereço que ele escolheu.

    **Cria o portfólio se ele ainda não existir**, do mesmo jeito que guardar a
    primeira peça cria: publicar antes de colar obra é caminho normal, e a
    página diz ao visitante que ainda não há obras. Trancar aqui seria inventar
    uma regra que ninguém pediu, e a lista desta casa orienta, nunca tranca
    (plano §7).

    **A colisão é decidida pelo BANCO**, e não por uma consulta antes da
    escrita: entre o `exists()` e o `save()` cabe o pedido de outro aluno, e a
    restrição `um_apelido_por_site` é a única régua que não tem essa fresta.
    """
    apelido = apelido_de(texto)
    if not apelido:
        raise VitrineRecusada(SEM_LETRA_NEM_NUMERO)
    if apelido in RESERVADOS:
        raise VitrineRecusada(
            "Esse endereço é usado por uma página do site. Escolha outro, como ana-3d."
        )

    try:
        with transaction.atomic():
            portfolio, _ = Portfolio.objects.get_or_create(
                site_id=site_id, aluno_id=aluno_id
            )
            portfolio = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
            portfolio.publicacao_comercial = snapshot_rascunho(portfolio)
            portfolio.apelido = apelido
            portfolio.vitrine_publicada = True
            portfolio.publicada_em = timezone.now()
            portfolio.save(
                update_fields=["apelido", "vitrine_publicada", "publicada_em", "publicacao_comercial"]
            )
    except IntegrityError as erro:
        raise VitrineRecusada(JA_E_DE_OUTRO) from erro
    return portfolio


def despublicar(portfolio: Portfolio) -> None:
    """Tira a página do ar. Imediatamente, e no pedido seguinte já não existe.

    **O apelido FICA.** Desligar não é perder o endereço: quem religa amanhã
    precisa do mesmo link que já mandou ao cliente, e apagar o apelido aqui
    entregaria esse endereço ao próximo aluno que o pedisse.
    """
    portfolio.vitrine_publicada = False
    portfolio.publicada_em = None
    portfolio.save(update_fields=["vitrine_publicada", "publicada_em"])


def publicada(*, site_id: str, apelido: str) -> Portfolio | None:
    """O portfólio que este endereço mostra, ou `None` quando não há página.

    `None` responde por TODOS os casos de uma vez, e essa é a economia que faz o
    404 não vazar nada: apelido que nunca existiu, aluno que nunca ligou, aluno
    que desligou hoje de manhã e escola diferente saem por aqui com a mesma
    resposta, e quem chama não tem como tratá-los diferente sem querer.

    **A fronteira de site entra na consulta** (multissítio: site é dado): o apelido é único por
    escola, e sem o `site_id` duas alunas chamadas `ana` em escolas diferentes
    disputariam a mesma página.
    """
    return Portfolio.objects.filter(
        site_id=site_id, apelido=apelido, vitrine_publicada=True
    ).first()


def obras(portfolio: Portfolio) -> list[Peca]:
    """As peças que a vitrine mostra, na ordem que o aluno escolheu.

    **A peça com o link QUEBRADO fica de fora**, e isso não é filtro de
    qualidade nem opinião sobre a obra (o plano §7 proíbe as duas coisas): é o
    fato medido de que o endereço parou de responder. Mostrá-la renderia um
    quadrado vazio na página que o aluno manda a um cliente pagante, e quem
    pareceria ruim seria a obra dele.

    **Sair da vitrine não é ser apagada** (critério AC-09). A peça continua na
    estante, marcada, com a data da quebra e a frase que diz o que fazer, e ela
    volta sozinha para cá no minuto em que o endereço responder de novo.

    O `nao_conferido` ENTRA, pela assimetria que o degrau 08 já escreveu em
    `conferencia_do_link.py`: daqui não dá para separar "o site dele caiu" de "a
    nossa rede caiu", e esconder a obra do aluno por causa de uma tosse da nossa
    rede seria a mesma injustiça que aquele módulo recusou.
    """
    snapshot = dados_publicados(portfolio)
    if snapshot is not None:
        return [_obra_do_snapshot(item) for item in snapshot.get("obras", [])]
    return list(
        portfolio.pecas.filter(mostrar_na_pagina_publica=True)
        .exclude(estado_do_link=EstadoDoLink.QUEBRADO)
        .order_by("ordem")
    )


def contexto_comercial(portfolio):
    from .comercial import contexto_publico
    snapshot = dados_publicados(portfolio)
    if snapshot is None:
        contexto = contexto_publico(portfolio, obras(portfolio))
        contexto["publico"] = snapshot_rascunho(portfolio)
        return contexto
    obras_publicas = obras(portfolio)
    pagina = snapshot.get("conteudo", {}).get("pagina", {})
    oferta = dict(snapshot.get("oferta", {}))
    from .comercial import url_publica
    if not oferta.get("exibir_preco"):
        oferta["preco"] = ""
    hero = next((obra for obra in obras_publicas if str(obra.pk) == pagina.get("trabalho_destaque")), None)
    hero = hero or next((obra for obra in obras_publicas if obra.destaque), None) or next(iter(obras_publicas), None)
    return {"publico": snapshot, "comercial": pagina, "oferta": oferta,
            "contato_url": url_publica(oferta.get("contato")), "hero": hero, "obras": obras_publicas}


def materiais_de(peca: Peca) -> list[dict]:
    """Imagens disponíveis ao editor, inclusive imagem antiga e link externo."""
    resultado = []
    ativos = list(peca.materiais.filter(substituido_por__isnull=True).order_by("ordem", "criado_em"))
    principal_novo = any(material.principal for material in ativos)
    antiga = getattr(peca, "imagem_enviada", None)
    if antiga is not None:
        resultado.append({"id": str(antiga.pk), "link": peca.link, "url": peca.link,
                          "categoria": "render", "legenda": peca.legenda,
                          "principal": not principal_novo, "ordem": 0})
    elif peca.link:
        resultado.append({"id": "externo:" + str(peca.pk), "link": peca.link, "url": peca.link,
                          "categoria": "render", "legenda": peca.legenda,
                          "principal": not principal_novo, "ordem": 0})
    for material in ativos:
        resultado.append({"id": str(material.pk), "link": material.url, "url": material.url,
                          "categoria": material.categoria, "legenda": material.legenda,
                          "principal": material.principal, "ordem": material.ordem})
    rotulos = {"render": "Render principal", "vistas": "Vistas da peça", "wireframe": "Wireframe", "uv": "Mapa UV"}
    for material in resultado:
        material["rotulo"] = rotulos.get(material["categoria"], "Imagem")
    return resultado


def snapshot_rascunho(portfolio: Portfolio) -> dict:
    """Copia textos, ordem, seleção e IDs de imagem para publicação atômica."""
    from .comercial import conteudo_de, oferta_de, provas_de
    pecas = list(portfolio.pecas.filter(mostrar_na_pagina_publica=True).exclude(
        estado_do_link=EstadoDoLink.QUEBRADO).order_by("ordem", "pk"))
    conteudo = conteudo_de(portfolio, ids=[peca.pk for peca in pecas])
    pagina = conteudo["pagina"]
    pagina.pop("apelido_rascunho", None)
    selecao_explicita = "materiais_ids" in (portfolio.apresentacao_comercial or {}).get("pagina", {})
    ordem = {str(valor): pos for pos, valor in enumerate(pagina.get("ordem_trabalhos", []))}
    pecas.sort(key=lambda p: (ordem.get(str(p.pk), len(ordem) + p.ordem), p.ordem))
    selecionados = set(pagina.get("materiais_ids", []))
    legendas = {i["peca_id"]: i for i in pagina.get("legendas", [])}
    obras = []
    imagens_ids = []
    for peca in pecas:
        materiais = materiais_de(peca)
        if not selecao_explicita:
            escolhidos = materiais[:1]
        else:
            escolhidos = [item for item in materiais if item["id"] in selecionados]
        imagens_ids.extend(item["id"] for item in escolhidos if not item["id"].startswith("externo:"))
        provas = provas_de(peca.provas_comerciais)
        if not selecao_explicita:
            for prova in provas:
                imagem_legada = portfolio.pecas.filter(link=prova["link"], imagem_enviada__isnull=False).first()
                if imagem_legada is not None:
                    imagens_ids.append(str(imagem_legada.imagem_enviada.pk))
        principal = next((item for item in escolhidos if item["principal"]), None)
        principal = principal or next(iter(escolhidos), None)
        complementos = [item for item in escolhidos if item != principal and item["categoria"] in {"render", "vistas"}]
        tecnicos = [item for item in escolhidos if item != principal and item["categoria"] in {"wireframe", "uv"}]
        legenda = legendas.get(str(peca.pk), {})
        obras.append({
            "id": peca.pk, "link": principal["link"] if principal else "",
            "imagem_principal": principal["link"] if principal else "",
            "legenda": peca.legenda, "ordem": peca.ordem,
            "destaque": str(peca.pk) == pagina["trabalho_destaque"] if pagina.get("trabalho_destaque") else peca.destaque,
            "titulo": peca.titulo, "descricao": peca.descricao,
            "titulo_comercial": legenda.get("titulo") or peca.titulo or peca.legenda,
            "texto_comercial": legenda.get("texto") or peca.descricao or peca.uso_pretendido,
            "uso_pretendido": peca.uso_pretendido, "contribuicao": peca.contribuicao,
            "triangulos": peca.triangulos, "textura": peca.textura,
            "provas_comerciais": provas,
            "complementos": complementos, "tecnicos": tecnicos,
        })
    oferta = oferta_de(portfolio)
    if not oferta.get("exibir_preco"):
        oferta["preco"] = ""
    publicados = set(imagens_ids)
    for obra in obras:
        obra["provas_comerciais"] = [
            prova for prova in obra["provas_comerciais"]
            if not urlsplit(prova["link"]).path.startswith("/portfolio/imagens/")
            or urlsplit(prova["link"]).path.rsplit("/", 1)[-1] in publicados
        ]
    return {"versao": 2, "conteudo": {"pagina": pagina}, "oferta": oferta,
            "obras": obras, "imagens_ids": list(dict.fromkeys(imagens_ids))}


def dados_publicados(portfolio: Portfolio) -> dict | None:
    valor = portfolio.publicacao_comercial or {}
    return valor if valor.get("versao") == 2 else None


def garantir_publicacao_legada(portfolio: Portfolio) -> None:
    """Congela página antiga antes da primeira edição de seu rascunho."""
    if not portfolio.vitrine_publicada or dados_publicados(portfolio) is not None:
        return
    with transaction.atomic():
        atual = Portfolio.objects.select_for_update().get(pk=portfolio.pk)
        if atual.vitrine_publicada and dados_publicados(atual) is None:
            atual.publicacao_comercial = snapshot_rascunho(atual)
            atual.save(update_fields=["publicacao_comercial"])
            portfolio.publicacao_comercial = atual.publicacao_comercial


def _obra_do_snapshot(dados):
    obra = SimpleNamespace(**dados)
    obra.pk = dados["id"]
    obra.provas_visiveis = dados.get("provas_comerciais", [])
    obra.provas_texto = "\n".join(f"{i['tipo']} | {i['link']} | {i['descricao']}" for i in obra.provas_visiveis)
    return obra
