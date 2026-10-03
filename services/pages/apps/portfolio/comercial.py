"""Dados de oferta, textos editáveis e projeção pública do portfólio."""
from __future__ import annotations

import copy
import ipaddress
import json
from urllib.parse import urlsplit

OFERTA = ("encomenda", "comprador", "uso", "entregaveis", "formatos", "prazo", "revisoes", "suporte",
          "preco", "moeda", "condicoes", "continuidade", "contato")
PROSPECCAO = ("nome", "projeto", "detalhe", "necessidade", "demonstracao", "pedido", "idioma")
PAGINA = ("titulo", "subtitulo", "apresentacao", "oferta", "continuidade", "diferenciais",
          "condicoes", "duvidas", "cta", "trabalho_destaque")
KIT = ("apresentacao_principal", "bio_curta", "abordagem", "proposta")
POSICIONAMENTO = ("comprador", "necessidade", "oferta", "prova")
TIPOS_PROVA = {"render", "detalhe", "wireframe", "studio", "video"}


def texto(valor, limite=6000):
    return valor.strip()[:limite] if isinstance(valor, str) else ""


def url_publica(valor):
    valor = texto(valor, 1000)
    try:
        partes = urlsplit(valor)
        host = partes.hostname or ""
        if (partes.scheme not in {"https", "http"} or not host or "." not in host or partes.username or partes.password
                or host.lower() == "localhost" or host.lower().endswith((".local", ".localhost"))
                or any(ord(c) < 33 for c in valor) or "\\" in valor):
            return ""
        try:
            if not ipaddress.ip_address(host).is_global:
                return ""
        except ValueError:
            pass
        return valor
    except ValueError:
        return ""


def oferta_de(portfolio, respostas=None, dados=None):
    respostas = respostas or {}
    guardada = getattr(portfolio, "oferta_comercial", {}) or {}
    resultado = {k: texto(guardada.get(k) or respostas.get("oferta_" + k)) for k in OFERTA}
    resultado["encomenda"] = resultado["encomenda"] or texto(respostas.get("servico_proprio"))
    publico = {"criadores": "Criadores de experiências Roblox", "marcas": "Criadores de itens para avatares",
               "jogadores": "Jogadores que procuram itens de avatar", "equipes_marcas": "Marcas e estúdios de experiências Roblox"}
    resultado["comprador"] = resultado["comprador"] or publico.get(respostas.get("publico"), "")
    resultado["exibir_preco"] = bool(guardada.get("exibir_preco")) if guardada else respostas.get("oferta_exibir_preco") == "sim"
    if dados is not None:
        for k in OFERTA:
            if "oferta_" + k in dados:
                resultado[k] = texto(dados.get("oferta_" + k))
        if "oferta_formulario" in dados or "oferta_exibir_preco" in dados:
            resultado["exibir_preco"] = dados.get("oferta_exibir_preco") in {"1", "sim", "on", "true"}
    return resultado


def prospeccao_de(portfolio, dados=None):
    guardada = getattr(portfolio, "prospeccao_comercial", {}) or {}
    resultado = {k: texto(guardada.get(k), 10000 if k == "pedido" else 3000) for k in PROSPECCAO}
    if dados is not None:
        for k in PROSPECCAO:
            if "prospeccao_" + k in dados:
                resultado[k] = texto(dados.get("prospeccao_" + k), 10000 if k == "pedido" else 3000)
    resultado["idioma"] = "en" if resultado["idioma"] in {"en", "ingles"} else "pt-BR"
    return resultado


def normalizar_conteudo(valor, ids=None):
    if not isinstance(valor, dict):
        raise ValueError("Não foi possível ler a apresentação. Seus textos foram mantidos.")
    if len(json.dumps(valor, ensure_ascii=False)) > 100000:
        raise ValueError("A apresentação está muito longa. Reduza os textos e tente salvar novamente.")
    resultado = {"versao": 1, "posicionamento": {}, "pagina": {}, "kit": {}}
    for secao, campos in (("posicionamento", POSICIONAMENTO), ("pagina", PAGINA), ("kit", KIT)):
        recebido = valor.get(secao) or {}
        if not isinstance(recebido, dict):
            raise ValueError("Não foi possível ler os textos da apresentação.")
        resultado[secao] = {k: texto(recebido.get(k), 280 if k == "bio_curta" else 6000) for k in campos}
    permitidos = None if ids is None else {str(k) for k in ids}
    pagina = resultado["pagina"]
    if permitidos is not None and pagina["trabalho_destaque"] not in permitidos:
        pagina["trabalho_destaque"] = ""
    pagina["legendas"] = []
    vistas = set()
    legendas = (valor.get("pagina") or {}).get("legendas") or []
    if not isinstance(legendas, list):
        raise ValueError("Não foi possível ler as legendas dos trabalhos.")
    for item in legendas[:60]:
        if not isinstance(item, dict):
            continue
        peca_id = str(item.get("peca_id", ""))
        if peca_id in vistas or (permitidos is not None and peca_id not in permitidos):
            continue
        vistas.add(peca_id)
        pagina["legendas"].append({"peca_id": peca_id, "titulo": texto(item.get("titulo"), 200), "texto": texto(item.get("texto"), 3000)})
    return resultado


def conteudo_de(portfolio, dados=None, ids=None):
    guardado = getattr(portfolio, "apresentacao_comercial", {}) or {}
    valor = copy.deepcopy(guardado)
    valor.setdefault("pagina", {})
    valor.setdefault("kit", getattr(portfolio, "kit_vendas", {}) or {})
    valor["pagina"].setdefault("apresentacao", getattr(portfolio, "apresentacao_publica", "") or "")
    valor["pagina"].setdefault("oferta", getattr(portfolio, "servico_publico", "") or "")
    if dados is not None:
        bruto = dados.get("conteudo_json")
        if bruto:
            try:
                valor = json.loads(bruto)
            except (ValueError, TypeError):
                raise ValueError("Não foi possível ler a apresentação. Seus textos foram mantidos.") from None
        valor = normalizar_conteudo(valor, ids)
        for secao, campos in (("pagina", PAGINA), ("kit", KIT)):
            for k in campos:
                if secao + "_" + k in dados:
                    valor[secao][k] = dados[secao + "_" + k]
        for antigo, novo in (("apresentacao_publica", "apresentacao"), ("servico_publico", "oferta")):
            if antigo in dados and "pagina_" + novo not in dados:
                valor["pagina"][novo] = dados[antigo]
        for item in valor["pagina"]["legendas"]:
            for campo in ("titulo", "texto"):
                nome = "legenda_" + campo + "_" + item["peca_id"]
                if nome in dados:
                    item[campo] = dados[nome]
        # Uma legenda pode ser escrita antes da primeira geração.
        existentes = {i["peca_id"] for i in valor["pagina"]["legendas"]}
        for peca_id in ids or []:
            peca_id = str(peca_id)
            if peca_id not in existentes and "legenda_texto_" + peca_id in dados:
                valor["pagina"]["legendas"].append({"peca_id": peca_id,
                    "titulo": dados.get("legenda_titulo_" + peca_id, ""), "texto": dados.get("legenda_texto_" + peca_id, "")})
    return normalizar_conteudo(valor, ids)


def provas_de(valor):
    if isinstance(valor, str):
        valor = [{"tipo": partes[0].strip(), "link": partes[1].strip(), "descricao": partes[2].strip() if len(partes) > 2 else ""}
                 for linha in valor.splitlines() if len(partes := linha.split("|", 2)) >= 2]
    if not isinstance(valor, list):
        return []
    return [{"tipo": item.get("tipo") if item.get("tipo") in TIPOS_PROVA else "detalhe",
             "link": url_publica(item.get("link")), "descricao": texto(item.get("descricao"), 1000)}
            for item in valor[:8] if isinstance(item, dict) and url_publica(item.get("link"))]


def preparar_trabalhos(trabalhos, conteudo):
    legendas = {i["peca_id"]: i for i in conteudo["pagina"]["legendas"]}
    for obra in trabalhos:
        legenda = legendas.get(str(obra.pk), {})
        obra.titulo_comercial = legenda.get("titulo") or obra.legenda
        obra.texto_comercial = legenda.get("texto") or obra.uso_pretendido
        obra.provas_visiveis = provas_de(obra.provas_comerciais)
        obra.provas_texto = "\n".join(f"{i['tipo']} | {i['link']} | {i['descricao']}" for i in obra.provas_visiveis)
    return trabalhos


def contexto_publico(portfolio, obras):
    conteudo = conteudo_de(portfolio, ids=[o.pk for o in obras])
    obras = preparar_trabalhos(obras, conteudo)
    pagina = conteudo["pagina"] if portfolio.apresentacao_comercial else {}
    oferta = oferta_de(portfolio)
    # Esta projeção não contém destinatário, pedido nem kit pessoal.
    if not oferta["exibir_preco"]:
        oferta["preco"] = ""
    hero = next((o for o in obras if str(o.pk) == conteudo["pagina"]["trabalho_destaque"]), None)
    hero = hero or next((o for o in obras if o.destaque), None) or next(iter(obras), None)
    return {"comercial": pagina, "oferta": oferta, "contato_url": url_publica(oferta["contato"]), "hero": hero, "obras": obras}
