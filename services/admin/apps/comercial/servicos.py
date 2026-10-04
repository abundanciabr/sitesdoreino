"""As APIs das outras células que a equipe comercial consulta e aciona.

Cada célula é dona dos seus dados: a admin pergunta pelo par já usado nas
outras telas (`LEADS_API_*`, `QUIZ_API_*`, `MENSAGERIA_API_*`,
`CHECKOUT_API_*`), lido no ponto de uso. As rotas ficam TODAS em `ROTAS`,
para casar num lugar só com o que cada célula publicar.

Os desfechos têm nome, porque levam a caminhos diferentes:

* ``ok`` — respondeu dentro do esperado;
* ``indisponivel`` — sem par configurado, sem conexão, 404 ou 405: a
  capacidade ainda não existe ali. A ferramenta devolve
  ``capacidade_indisponivel`` e o trabalho segue;
* ``fora`` — a célula respondeu que o provedor está fora (5xx, 429). Numa
  escrita, o trabalho volta para a fila e tenta de novo com a MESMA chave;
* ``incerto`` — uma escrita saiu e a resposta não voltou (tempo esgotado). Não
  se reenvia às cegas: a reconciliação repete o pedido com a mesma
  ``chave_idempotencia``, que a célula reconhece;
* ``recusado`` — a célula recusou (403, 409, 422...), com o motivo dela.

Nenhum segredo entra no resultado nem no log: o token só vai no cabeçalho.
"""

from __future__ import annotations

import logging
import os
import time
from dataclasses import dataclass, field
from urllib.parse import quote

import httpx

from apps.core.clients import http

log = logging.getLogger(__name__)

PARES = {
    "leads": ("LEADS_API_URL", "LEADS_API_TOKEN"),
    "quiz": ("QUIZ_API_URL", "QUIZ_API_TOKEN"),
    "mensageria": ("MENSAGERIA_API_URL", "MENSAGERIA_API_TOKEN"),
    "checkout": ("CHECKOUT_API_URL", "CHECKOUT_API_TOKEN"),
}

# Caminhos relativos à base de cada par. `{}` são preenchidos com quote().
ROTAS = {
    # leads (LEADS_API_URL = http://leads:8000/api/leads; /crm e /perfil pedem o token do admin)
    "buscar_contato": ("leads", "GET", "/leads"),
    "contato": ("leads", "GET", "/leads/{}"),
    "perfil": ("leads", "GET", "/leads/{}/perfil"),
    "salvar_perfil": ("leads", "PUT", "/leads/{}/perfil"),
    "respostas_do_lead": ("leads", "GET", "/leads/{}/respostas"),
    "oportunidades": ("leads", "GET", "/crm"),
    "oportunidade": ("leads", "GET", "/crm/{}"),
    "acompanhamento": ("leads", "PATCH", "/crm/{}/acompanhamento"),
    "nota": ("leads", "POST", "/crm/{}/history"),
    "receita": ("leads", "GET", "/crm/{}/receita"),
    # quiz (QUIZ_API_URL); `site_id` vai na consulta
    "submissoes_do_contato": ("quiz", "GET", "/interno/crm/submissoes"),
    "respostas_da_submissao": ("quiz", "GET", "/interno/crm/submissoes/{}"),
    "captura": ("quiz", "GET", "/interno/crm/capturas/{}"),
    # mensageria (MENSAGERIA_API_URL); `site_id` vai na consulta ou no corpo
    "conversas": ("mensageria", "GET", "/conversas"),
    "conversa": ("mensageria", "GET", "/conversas/{}"),
    "mensagens": ("mensageria", "GET", "/conversas/{}/mensagens"),
    "envios_do_pedido": ("mensageria", "GET", "/envios-de-pedido"),
    "abrir_conversa": ("mensageria", "POST", "/conversas"),
    "enviar_na_conversa": ("mensageria", "POST", "/conversas/{}/mensagens"),
    # O modelo aprovado do WhatsApp para o primeiro contato (fora da janela de 24 horas); só escolhe e preenche.
    "modelo_primeiro_contato": ("mensageria", "POST", "/whatsapp-modelos/{}/primeiro-contato"),
    # Endereços da orientação fixa a quem escreve sem ser do quiz (endereço do quiz e atendimento geral do site).
    "orientacao_do_site": ("mensageria", "GET", "/orientacoes/{}"),
    "definir_orientacao_do_site": ("mensageria", "PUT", "/orientacoes/{}"),
    "assumir": ("mensageria", "POST", "/conversas/{}/assumir"),
    "devolver": ("mensageria", "POST", "/conversas/{}/devolver"),
    # checkout (CHECKOUT_API_URL); o site vem do cabeçalho Host
    "condicoes": ("checkout", "GET", "/interno/ofertas/{}/condicoes-agente"),
    "link_de_compra": ("checkout", "POST", "/interno/links-de-compra"),
    "pagamento_do_pedido": ("checkout", "GET", "/interno/pedidos/{}/pagamento"),
    "pedidos_da_oportunidade": ("checkout", "GET", "/interno/pedidos"),
}

# O checkout e o quiz acham o site pelo Host, como nas outras telas do
# painel. O domínio é o do SITE do trabalho (`host_do_site`); sem ele, a
# chamada não sai e responde `indisponivel`: nunca vale o de outro site.

TIMEOUT = 8.0
# Estas duas rotas fazem o checkout cotar as parcelas no provedor (até 15 s,
# mais até 5 s pela oferta no catálogo): quem pergunta espera mais que ele.
# As outras rotas seguem no TIMEOUT geral.
TIMEOUT_POR_ROTA = {"condicoes": 25.0, "link_de_compra": 25.0}

_CACHE_DO_HOST: dict[str, tuple[str, float]] = {}
VALIDADE_DO_HOST = 3600.0  # o domínio de um site quase nunca muda
VALIDADE_DO_HOST_NAO_ACHADO = 60.0  # não achou: não pergunta ao catálogo a cada chamada


def _host_do_indice(site_id: str) -> str:
    """O domínio que o índice comercial já guardou para este site (banco desta célula)."""
    from apps.agentes.models import MaterialComercial, TrechoComercial

    for modelo in (TrechoComercial, MaterialComercial):
        achado = (
            modelo.objects.filter(site_id=site_id).exclude(site_host="")
            .order_by().values_list("site_host", flat=True).first()
        )
        if achado:
            return str(achado).strip().lower()
    return ""


def _host_pelo_catalogo(site_id: str) -> str:
    """Procura, entre os domínios que a plataforma conhece, o que o catálogo
    diz ser deste site. O domínio só vale se o id do site conferir."""
    from apps.agentes.conhecimento_comercial import hosts_conhecidos
    from apps.core.clients import CatalogoClient

    catalogo = CatalogoClient()
    if catalogo._configuracao() is None:
        return ""
    for candidato in hosts_conhecidos():
        site = catalogo.site_por_host(candidato)
        if site and str(site.get("id") or "") == site_id:
            return str(site.get("host") or candidato).strip().lower()
    return ""


def host_do_site(site_id: str, *, perguntar_ao_catalogo: bool = True) -> str:
    """O domínio do site, achado pelo id do site: primeiro o que o índice
    comercial guardou, depois o catálogo. Vazio quando não se sabe. Nunca
    levanta erro e nunca devolve um domínio "padrão"."""
    site_id = str(site_id or "").strip()
    if not site_id:
        return ""
    agora = time.monotonic()
    guardado = _CACHE_DO_HOST.get(site_id)
    if guardado is not None and agora < guardado[1]:
        return guardado[0]
    host = ""
    try:
        host = _host_do_indice(site_id)
        if not host and perguntar_ao_catalogo:
            host = _host_pelo_catalogo(site_id)
    except Exception:  # noqa: BLE001 - sem o domínio a chamada diz `indisponivel`
        log.warning("comercial: não deu para achar o domínio do site %s", site_id, exc_info=True)
    if host or perguntar_ao_catalogo:
        _CACHE_DO_HOST[site_id] = (
            host, agora + (VALIDADE_DO_HOST if host else VALIDADE_DO_HOST_NAO_ACHADO))
    return host


def host_do_trabalho(trabalho) -> str:
    """O domínio guardado na entrada do trabalho; sem ele, o do site dele."""
    guardado = str((trabalho.entrada or {}).get("host") or "").strip().lower()[:255]
    return guardado or host_do_site(trabalho.site_id)


@dataclass
class Resposta:
    estado: str
    dados: dict = field(default_factory=dict)
    detalhe: str = ""
    status: int | None = None

    @property
    def ok(self) -> bool:
        return self.estado == "ok"


def configurado(servico: str) -> bool:
    return _configuracao(servico) is not None


def _configuracao(servico: str):
    url, token = PARES[servico]
    base = (os.environ.get(url) or "").strip().rstrip("/")
    segredo = (os.environ.get(token) or "").strip()
    return (base, segredo) if base and segredo else None


def _detalhe(resposta: httpx.Response) -> str:
    try:
        corpo = resposta.json()
    except ValueError:
        return ""
    if isinstance(corpo, dict):
        detalhe = corpo.get("detail") or corpo.get("erro") or corpo.get("motivo") or ""
        return str(detalhe)[:300]
    return ""


def pedir(rota: str, *partes, params: dict | None = None, corpo: dict | None = None,
          site_id: str = "", host: str = "") -> Resposta:
    servico, metodo, molde = ROTAS[rota]
    config = _configuracao(servico)
    if config is None:
        return Resposta("indisponivel", detalhe=f"{servico} ainda não está ligada nesta célula")
    base, token = config
    caminho = molde.format(*(quote(str(p), safe="") for p in partes))
    escrita = metodo != "GET"
    cabecalhos = {"Authorization": f"Bearer {token}"}
    if site_id:
        cabecalhos["X-Site-Id"] = str(site_id)
    if servico in ("checkout", "quiz"):
        dominio = (host or "").strip().lower()[:255]
        if not dominio:
            return Resposta("indisponivel", detalhe=f"sem o domínio do site, {servico} não sabe de qual site é")
        cabecalhos["Host"] = dominio
    try:
        resposta = http().request(
            metodo,
            base + caminho,
            params={k: v for k, v in (params or {}).items() if v not in (None, "")},
            json=corpo if escrita else None,
            headers=cabecalhos,
            timeout=TIMEOUT_POR_ROTA.get(rota, TIMEOUT),
        )
    except httpx.ConnectError:
        # Não conectou: o pedido não saiu.
        return Resposta("indisponivel", detalhe=f"{servico} não respondeu")
    except httpx.HTTPError as erro:
        log.warning("comercial: %s %s sem resposta (%s)", metodo, rota, type(erro).__name__)
        if escrita:
            return Resposta("incerto", detalhe=f"{servico} não confirmou a tempo")
        return Resposta("indisponivel", detalhe=f"{servico} não respondeu a tempo")
    status = resposta.status_code
    if status in (404, 405, 501):
        return Resposta("indisponivel", detalhe=_detalhe(resposta) or f"{servico} sem esta capacidade",
                        status=status)
    if status == 429 or status >= 500:
        return Resposta("fora", detalhe=_detalhe(resposta) or f"{servico} fora agora", status=status)
    if status >= 400:
        return Resposta("recusado", detalhe=_detalhe(resposta) or f"{servico} recusou", status=status)
    try:
        dados = resposta.json() if resposta.content else {}
    except ValueError:
        return Resposta("indisponivel", detalhe=f"{servico} respondeu fora do contrato", status=status)
    if isinstance(dados, list):
        dados = {"itens": dados}
    if not isinstance(dados, dict):
        return Resposta("indisponivel", detalhe=f"{servico} respondeu fora do contrato", status=status)
    return Resposta("ok", dados=dados, status=status)


def garantir_endereco_do_quiz_na_orientacao(site_id: str) -> bool:
    """Diz à mensageria o endereço do site, para a orientação a quem não é do quiz citá-lo.

    Só preenche o que está vazio (o que a equipe definiu fica) e nunca levanta erro:
    sem o domínio ou sem a mensageria, a orientação vai sem o link. Devolve se gravou.
    """
    try:
        host = host_do_site(site_id)
        if not host:
            return False
        atual = pedir("orientacao_do_site", site_id)
        if not atual.ok or str(atual.dados.get("endereco_quiz") or "").strip():
            return False
        gravada = pedir("definir_orientacao_do_site", site_id, corpo={
            "endereco_quiz": f"https://{host}/",
            "atendimento_geral": str(atual.dados.get("atendimento_geral") or ""),
        })
        return gravada.ok
    except Exception:  # noqa: BLE001 - cortesia: a mensagem do contato não depende disto
        log.warning("comercial: não deu para informar o endereço do site %s à mensageria", site_id, exc_info=True)
        return False
