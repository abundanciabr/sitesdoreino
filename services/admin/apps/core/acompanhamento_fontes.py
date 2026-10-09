"""Consultas de acompanhamento às fontes autorizadas da escola."""
import os
from urllib.parse import quote
import httpx
from .clients import http, IdentidadeClient, GamificacaoClient


def _pedir(base, token, caminho, *, metodo="GET", corpo=None):
    if not base or not token:
        return "sem_configuracao", None
    try:
        resposta = http().request(metodo, base.rstrip("/") + caminho,
            headers={"Authorization": "Bearer " + token}, json=corpo, timeout=6)
        if resposta.status_code == 404:
            return "sem_registro", None
        if resposta.status_code != 200:
            return "indisponivel", None
        dados = resposta.json()
        if not isinstance(dados, (dict, list)):
            return "indisponivel", None
        return "ok", dados
    except (httpx.HTTPError, ValueError):
        return "indisponivel", None


def _fonte(url, token, caminho):
    return _pedir(os.environ.get(url, "").strip(), os.environ.get(token, "").strip(), caminho)


def consultar_fontes(site_id, email):
    fontes = {nome: {"estado": "sem_identidade", "dados": None} for nome in
              ("portfolio", "conquistas", "fila", "pecas", "comunidade", "pratica")}
    config = IdentidadeClient()._configuracao()
    estado, identidade = (_pedir(*config, "/pessoas/por-email", metodo="POST", corpo={"email": email})
                           if config else ("sem_configuracao", None))
    pessoa = str(identidade.get("id") or "") if estado == "ok" and isinstance(identidade, dict) else ""
    fontes["identidade"] = {"estado": estado, "pessoa_id": pessoa}
    # Esta fonte também funciona para alunos externos que ainda não têm conta local.
    try:
        from .nps_client import NPSClient
        estado_nps, dados_nps = NPSClient().historico(site_id, email=email)
    except ImportError:
        estado_nps, dados_nps = "sem_configuracao", None
    if estado_nps == "ok" and (not isinstance(dados_nps, dict)
            or not isinstance(dados_nps.get("avaliacoes"), list)):
        estado_nps, dados_nps = "indisponivel", None
    if estado_nps == "ok":
        dados_nps = dict(dados_nps)
        dados_nps["avaliacoes"] = [dict(i, nota=(i.get("respostas") or {}).get("nota", (i.get("resultado") or {}).get("nps")),
            comentario=(i.get("respostas") or {}).get("comentario", (i.get("respostas") or {}).get("R13")), respondida_em=i.get("concluida_em"))
            for i in dados_nps["avaliacoes"] if isinstance(i, dict)]
    fontes["nps"] = {"estado": estado_nps, "dados": dados_nps}
    if not pessoa:
        return fontes
    site, pid = quote(site_id, safe=""), quote(pessoa, safe="")
    consultas = {
        "portfolio": ("PAGES_API_URL", "PAGES_API_TOKEN", f"/portfolios/{site}/{pid}"),
        "fila": ("ENCOMENDAS_API_URL", "ENCOMENDAS_API_TOKEN", f"/perfis/{pid}/fila"),
        "pecas": ("ENCOMENDAS_API_URL", "ENCOMENDAS_API_TOKEN", f"/perfis/{pid}/pecas-aprovadas"),
        "comunidade": ("FORUM_API_URL", "TOKEN_FORUM", f"/acompanhamento/{site}/{pid}"),
        "pratica": ("ENCOMENDAS_API_URL", "ENCOMENDAS_API_TOKEN", f"/acompanhamento/{site}/{pid}"),
    }
    for nome, argumentos in consultas.items():
        estado, dados = _fonte(*argumentos)
        if estado == "ok" and not isinstance(dados, dict):
            estado, dados = "indisponivel", None
        if estado == "ok" and nome in ("comunidade", "pratica"):
            if dados.get("site_id") != site_id or str(dados.get("pessoa_id")) != pessoa:
                estado, dados = "indisponivel", None
            elif nome == "comunidade":
                dados = dict(dados, limitacao=dados.get("motivo_parcial"))
                dados["atividades"] = [dict(i, data=i.get("criado_em")) for i in dados.get("atividades", [])]
            else:
                dados = dict(dados)
                for lista in ("projetos", "encomendas"):
                    dados[lista] = [dict(i, status=i.get("estado"), prazo=i.get("prazo_ate"))
                                     for i in dados.get(lista, [])]
        fontes[nome] = {"estado": estado, "dados": dados}
    quadro = GamificacaoClient().quadro()
    if quadro is None:
        fontes["conquistas"] = {"estado": "indisponivel", "dados": None}
    else:
        dados = next((i for i in quadro if str(i.get("pessoa_id")) == pessoa), None)
        nomes = {i.get("slug"): i.get("nome") or i.get("slug")
                 for i in (GamificacaoClient().conquistas() or [])}
        if dados:
            dados = dict(dados)
            dados["conquistas"] = [dict(i, nome=nomes.get(i.get("slug"), i.get("slug")))
                                     for i in dados.get("conquistas", [])]
        fontes["conquistas"] = {"estado": "ok" if dados else "sem_registro", "dados": dados}
    # A faixa é um enfeite da ficha: qualquer falha a omite, sem derrubar o resto.
    try:
        faixa = GamificacaoClient().faixa_do_aluno(pessoa)
        atual = faixa.get("atual") if isinstance(faixa, dict) else None
        if isinstance(atual, dict) and atual.get("nome"):
            cores = [c for c in (atual.get("cores") or []) if isinstance(c, str)
                     and len(c) == 7 and c.startswith("#")]
            if cores:
                fundo = cores[0] if len(cores) == 1 else (
                    f"linear-gradient(90deg,{cores[0]} 50%,{cores[1]} 50%)")
                fontes["faixa"] = {"nome": atual["nome"], "conquista": atual.get("conquista"),
                                   "alcancada_em": atual.get("alcancada_em"), "fundo": fundo,
                                   "ordem": atual.get("ordem")}
    except Exception:
        pass
    return fontes
