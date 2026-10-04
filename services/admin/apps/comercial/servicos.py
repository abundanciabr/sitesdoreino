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
    "abrir_conversa": ("mensageria", "POST", "/conversas"),
    "enviar_na_conversa": ("mensageria", "POST", "/conversas/{}/mensagens"),
    "assumir": ("mensageria", "POST", "/conversas/{}/assumir"),
    "devolver": ("mensageria", "POST", "/conversas/{}/devolver"),
    # checkout (CHECKOUT_API_URL); o site vem do cabeçalho Host
    "condicoes": ("checkout", "GET", "/interno/ofertas/{}/condicoes"),
    "link_de_compra": ("checkout", "POST", "/interno/links-de-compra"),
    "pagamento_do_pedido": ("checkout", "GET", "/interno/pedidos/{}/pagamento"),
    "pedidos_da_oportunidade": ("checkout", "GET", "/interno/pedidos"),
}

# O checkout e o quiz acham o site pelo Host, como nas outras telas do
# painel. Sem o host no evento, vale o do site principal.
HOST_PADRAO = "meshcraft.top"

TIMEOUT = 8.0


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
        cabecalhos["Host"] = (host or HOST_PADRAO).strip().lower()[:255]
    try:
        resposta = http().request(
            metodo,
            base + caminho,
            params={k: v for k, v in (params or {}).items() if v not in (None, "")},
            json=corpo if escrita else None,
            headers=cabecalhos,
            timeout=TIMEOUT,
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
