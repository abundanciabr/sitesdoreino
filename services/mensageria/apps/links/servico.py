"""Reescrita de URLs em links individuais e registro dos acessos."""
from __future__ import annotations

import re
import secrets
import string
from datetime import timezone as fuso
from urllib.parse import urlsplit

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from . import classificacao as classificador
from .models import Acesso, Destino, LinkIndividual, VersaoDoDestino

# Mesma regra de apps/conversas/interacoes.py: quem acha a URL lá acha aqui.
PADRAO_DE_URL = re.compile(r"https://[^\s<>]+")
# Pontuação e marcas de formatação do WhatsApp (*negrito*, _itálico_, ~riscado~) não fazem parte da URL.
PONTUACAO_FINAL = ".,;!?:*_~`'\""
LIMITE_DA_URL = 2000  # cabe na coluna da versão; acima disso a URL fica como está, sem rastreio
ALFABETO = string.ascii_lowercase + string.digits
TAMANHO_DO_TOKEN = 10
ESTADOS_ACEITOS = frozenset({"aceito", "enviado", "entregue", "lido"})
# O link de compra sai cru: o checkout já atribui o pedido pelo ?link=<id>, e o ciclo comercial
# (services/aplicacao/tests/e2e/test_ciclo_comercial.py, caso 09) confere a URL byte a byte na mensagem.
CAMINHO_DO_CHECKOUT = "/checkout/"


def _limpar(achado: str) -> str:
    """Tira pontuação/formatação do fim; ')' só sai se não fecha um '(' da própria URL."""
    url = achado
    while url:
        if url[-1] in PONTUACAO_FINAL or (url[-1] == ")" and url.count(")") > url.count("(")):
            url = url[:-1]
        else:
            break
    if not re.search(r"[A-Za-z0-9]", url[len("https://"):]):
        return ""
    return url


def e_link_de_compra(url: str) -> bool:
    return urlsplit(url).path.startswith(CAMINHO_DO_CHECKOUT)


def url_base() -> str:
    return getattr(settings, "LINKS_URL_BASE", "https://meshcraft.top/r/")


def _novo_token() -> str:
    return "".join(secrets.choice(ALFABETO) for _ in range(TAMANHO_DO_TOKEN))


def _destino_para(site_id: str, url: str) -> tuple[Destino, VersaoDoDestino]:
    """Reaproveita o destino do site cuja versão atual é esta URL; senão cria um automático."""
    candidatos = (Destino.objects.filter(site_id=site_id, arquivado_em__isnull=True, versoes__url=url)
                  .distinct().order_by("criado_em"))
    for destino in candidatos:
        versao = destino.versao_atual
        if versao is not None and versao.url == url:
            return destino, versao
    # O nome não leva query string nem fragmento: podem trazer e-mail, telefone ou token pessoal.
    nome = url.split("#", 1)[0].split("?", 1)[0]
    destino = Destino.objects.create(site_id=site_id, nome=nome[:200], origem="automatico")
    versao = VersaoDoDestino.objects.create(destino=destino, numero=1, url=url, criada_por="automatico")
    return destino, versao


def _link_da_url(url: str, *, site_id, origem, referencia, conversa_id, mensagem_id,
                 jornada_slug, inscricao_id, passo_id) -> LinkIndividual:
    chave = dict(site_id=site_id, origem=origem, referencia=referencia, url_original=url)
    for _ in range(5):
        existente = LinkIndividual.objects.filter(**chave).first()
        if existente is not None:
            return existente
        try:
            with transaction.atomic():
                destino, versao = _destino_para(site_id, url)
                return LinkIndividual.objects.create(
                    token=_novo_token(), destino=destino, versao=versao,
                    conversa_id=conversa_id, mensagem_id=mensagem_id, jornada_slug=jornada_slug,
                    inscricao_id=inscricao_id, passo_id=passo_id, **chave)
        except IntegrityError:
            continue  # token repetido ou outro processo criou o mesmo link: olha de novo
    raise RuntimeError("nao foi possivel criar o link individual")


def reescrever(texto: str, *, site_id: str, origem: str, referencia: str, conversa_id=None,
               mensagem_id=None, jornada_slug: str = "", inscricao_id=None,
               passo_id=None) -> tuple[str, list[LinkIndividual]]:
    """Troca cada URL https do texto por LINKS_URL_BASE+token. Repetir devolve os mesmos tokens."""
    base = url_base()
    por_url: dict[str, LinkIndividual] = {}
    for achado in PADRAO_DE_URL.findall(texto or ""):
        url = _limpar(achado)
        if not url or url.startswith(base) or url in por_url or len(url) > LIMITE_DA_URL:
            continue
        if e_link_de_compra(url):
            continue
        por_url[url] = _link_da_url(
            url, site_id=site_id, origem=origem, referencia=referencia[:200],
            conversa_id=conversa_id, mensagem_id=mensagem_id, jornada_slug=jornada_slug,
            inscricao_id=inscricao_id, passo_id=passo_id)
    if not por_url:
        return texto, []

    def trocar(m: re.Match) -> str:
        achado = m.group(0)
        url = _limpar(achado)
        link = por_url.get(url)
        if link is None:
            return achado
        return base + link.token + achado[len(url):]

    return PADRAO_DE_URL.sub(trocar, texto), list(por_url.values())


def links_do_texto(texto: str, *, site_id: str) -> list[LinkIndividual]:
    """Os links já reescritos que aparecem num texto (para marcar envio na retomada)."""
    padrao = re.escape(url_base()) + r"([a-z0-9]{%d})" % TAMANHO_DO_TOKEN
    tokens = re.findall(padrao, texto or "")
    return list(LinkIndividual.objects.filter(site_id=site_id, token__in=tokens))


def marcar_enviados_no_texto(texto: str, *, site_id: str) -> None:
    """Marca como enviados só os links que de fato estão no texto que saiu (também na retomada)."""
    links = links_do_texto(texto, site_id=site_id)
    if links:
        marcar_enviados(links)


def vincular_mensagem(links, mensagem_id) -> None:
    ids = [link.pk for link in links]
    if ids:
        LinkIndividual.objects.filter(pk__in=ids, mensagem_id__isnull=True).update(mensagem_id=mensagem_id)


def vincular_conversa(links, conversa_id, mensagem_id) -> None:
    """Liga à conversa os links de jornada, depois que a mensagem entrou nela."""
    ids = [link.pk for link in links]
    if ids:
        LinkIndividual.objects.filter(pk__in=ids, conversa_id__isnull=True).update(conversa_id=conversa_id)
        LinkIndividual.objects.filter(pk__in=ids, mensagem_id__isnull=True).update(mensagem_id=mensagem_id)


def _texto_id(valor) -> str | None:
    return str(valor) if valor else None


def _iso(momento) -> str:
    return momento.astimezone(fuso.utc).isoformat()


def marcar_enviados(links) -> None:
    """Emite link.enviado uma só vez por link (enviado_em é a trava)."""
    from apps.jornadas import eventos, tasks

    for link in links:
        with transaction.atomic():
            atual = (LinkIndividual.objects.select_for_update().select_related("destino", "versao")
                     .get(pk=link.pk))
            if atual.enviado_em is not None:
                continue
            atual.enviado_em = timezone.now()
            atual.save(update_fields=["enviado_em"])
            eventos.emitir("link.enviado", {
                "site_id": atual.site_id, "link_id": str(atual.pk), "token": atual.token,
                "destino_id": str(atual.destino_id), "destino_nome": atual.destino.nome,
                "versao": atual.versao.numero, "origem": atual.origem, "referencia": atual.referencia,
                "campanha": atual.jornada_slug, "conversa_id": _texto_id(atual.conversa_id),
                "mensagem_id": _texto_id(atual.mensagem_id), "passo_id": _texto_id(atual.passo_id),
                "enviado_em": _iso(atual.enviado_em),
            })
            transaction.on_commit(tasks.relay_apos_commit)


def registrar_acesso(token: str, *, metodo: str, user_agent: str, accept: str) -> dict | None:
    from apps.jornadas import eventos

    link = LinkIndividual.objects.select_related("destino", "versao").filter(token=token).first()
    if link is None:
        return None
    classe, motivo = classificador.classificar(metodo, user_agent, accept)
    with transaction.atomic():
        acesso = Acesso.objects.create(link=link, metodo=(metodo or "")[:8], user_agent=(user_agent or "")[:300],
                                       classificacao=classe, motivo=motivo[:120])
        eventos.emitir("link.acessado", {
            "site_id": link.site_id, "link_id": str(link.pk), "token": link.token,
            "destino_id": str(link.destino_id), "versao": link.versao.numero, "origem": link.origem,
            "campanha": link.jornada_slug, "mensagem_id": _texto_id(link.mensagem_id),
            "passo_id": _texto_id(link.passo_id), "classificacao": classe, "motivo": motivo,
            "metodo": acesso.metodo, "ocorrido_em": _iso(acesso.ocorrido_em),
        })
        # Sem relay aqui: o clique não pode depender do Redis; o relay periódico publica.
    atual = link.destino.versao_atual
    return {"destino": atual.url if atual else link.url_original, "classificacao": classe, "motivo": motivo}
