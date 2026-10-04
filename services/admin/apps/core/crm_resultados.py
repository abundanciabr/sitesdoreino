"""Resultados comerciais do CRM: conversão, receita líquida, custos e versões.

Definições da seção "Como medir resultado e custo" do plano do CRM com agentes:

* conversão por quiz: pessoas que compraram o produto do quiz divididas pelas
  pessoas que fizeram aquele quiz no período (a coorte);
* resposta por canal: pessoas que responderam divididas pelas alcançadas,
  separando o que foi enviado do que foi entregue;
* recuperação observada: compras aprovadas depois de uma tentativa que falhou;
* conversão assistida: compras com interação registrada de um agente (mensagem
  enviada ou link de compra preparado) antes da aprovação;
* receita líquida de reversões: aprovado menos estornos e contestações;
* custo por venda: consumo dos modelos mais as mensagens, dividido pelas vendas;
* margem de contribuição: receita líquida menos os custos variáveis que temos
  medidos. O desconto já está no valor pago e não é descontado de novo. Não é
  lucro: despesas fixas e o que ainda não é medido ficam fora, e a tela diz
  quais componentes faltam.

Os fatos vêm de quem é dono deles: compras e coorte da `leads`
(`/resultados/comerciais`), trabalho e custo dos agentes desta célula
(`apps.comercial`), entrega e resposta da `mensageria`. Quem não responde
aparece como "ainda indisponível", nunca como zero nem como erro 500.
"""

from __future__ import annotations

import logging
import os
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal, InvalidOperation

import httpx
from django.apps import apps
from django.db.models import Q
from django.shortcuts import render
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime
from django.views.decorators.http import require_GET

from . import crm_resultados_atendimento as atendimento
from apps.comercial import comparacao

from .clients import LeadsClient, http

logger = logging.getLogger("admin.crm_resultados")

AMOSTRA_MINIMA_PESSOAS = 30
AMOSTRA_MINIMA_VENDAS = 5
# Ferramentas que contam como contato do agente com a pessoa.
INTERACOES = ("enviar_mensagem", "preparar_link_compra")
CANAIS = ("whatsapp", "email")
NOMES_DOS_PAPEIS = {"analista": "Analista do lead", "abordagem": "Abordagem",
                    "atendimento": "Atendimento e negociação", "resultados": "Análise de resultados"}
INDISPONIVEL = "indisponivel"


# ---------------------------------------------------------------------------
# Fontes
# ---------------------------------------------------------------------------
class ResultadosClient(LeadsClient):
    """`GET /resultados/comerciais` da `leads`, com o par do painel."""

    TIMEOUT = 10.0

    def comerciais(self, **filtros) -> "tuple[str, dict | None]":
        config = self._configuracao()
        if config is None:
            return self.SEM_CONFIGURACAO, None
        base, token = config
        try:
            r = http().get(
                base + "/resultados/comerciais",
                params={k: v for k, v in filtros.items() if v},
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("resultados: a leads não respondeu: %s", erro)
            return self.NAO_RESPONDEU, None
        if r.status_code != 200:
            logger.error("resultados: a leads respondeu HTTP %s", r.status_code)
            return self.NAO_RESPONDEU, None
        try:
            dados = r.json()
        except ValueError:
            return self.NAO_RESPONDEU, None
        if not (
            isinstance(dados, dict)
            and isinstance(dados.get("totais"), dict)
            and all(isinstance(dados.get(k), list) for k in ("por_quiz", "por_campanha", "por_oferta", "compras", "oportunidades"))
        ):
            return self.NAO_RESPONDEU, None
        return self.OK, dados


class ConversasClient:
    """Leitura das conversas na `mensageria` para medir resposta e entrega.

    Primeiro pergunta o resumo pronto (`GET /conversas/resultados`); se a
    mensageria ainda não o tiver, lê a lista de conversas ligadas a leads e usa
    `ultima_entrada_em` para saber quem respondeu depois do primeiro envio.
    """

    TIMEOUT = 5.0
    PAGINAS = 5

    def _configuracao(self):
        base = (os.environ.get("MENSAGERIA_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("MENSAGERIA_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def _get(self, caminho, params):
        config = self._configuracao()
        if config is None:
            return None, None
        base, token = config
        try:
            r = http().get(base + caminho, params=params, headers={"Authorization": "Bearer " + token}, timeout=self.TIMEOUT)
        except httpx.HTTPError:
            return None, None
        try:
            corpo = r.json() if r.status_code == 200 else None
        except ValueError:
            corpo = None
        return r.status_code, corpo if isinstance(corpo, dict) else None

    def resumo(self, site_id, desde, ate):
        status, corpo = self._get("/conversas/resultados", {"site_id": site_id, "desde": desde, "ate": ate})
        if status == 200 and isinstance((corpo or {}).get("por_canal"), list):
            return corpo
        return None

    def conversas(self, site_id):
        """Conversas ligadas a leads deste site, ou `None` se não deu para ler."""
        itens = []
        for pagina in range(1, self.PAGINAS + 1):
            status, corpo = self._get("/conversas", {"site_id": site_id, "pagina": pagina, "por_pagina": 100})
            if status != 200 or not isinstance((corpo or {}).get("itens"), list):
                return None if pagina == 1 else itens
            itens.extend(i for i in corpo["itens"] if isinstance(i, dict))
            if not corpo.get("tem_mais"):
                break
        return itens


# ---------------------------------------------------------------------------
# Conversões e números
# ---------------------------------------------------------------------------
def _instante(texto):
    if not isinstance(texto, str) or not texto:
        return None
    try:
        momento = parse_datetime(texto)
    except ValueError:
        return None
    if momento is not None and timezone.is_naive(momento):
        momento = timezone.make_aware(momento)
    return momento


VALOR_MAXIMO = Decimal("1000000")  # cotação e tarifas: acima disso é erro de digitação


def _decimal(texto) -> "Decimal | None":
    """Número não negativo, finito e razoável; qualquer outra coisa ("inf",
    "nan", "1e99999999", texto) vale como não informado."""
    try:
        valor = Decimal(str(texto).replace(",", ".").strip())
    except (InvalidOperation, ValueError):
        return None
    if not valor.is_finite() or valor < 0 or valor > VALOR_MAXIMO:
        return None
    return valor


def _inteiro(texto) -> "int | None":
    """Inteiro escrito só com dígitos ASCII, até 9: "²", "١" e texto enorme não valem."""
    texto = texto if isinstance(texto, str) else ""
    return int(texto) if texto.isascii() and texto.isdigit() and len(texto) <= 9 else None


def _data(texto, padrao):
    """Data AAAA-MM-DD da tela; vazia, mal escrita ou impossível (2026-02-31) cai no padrão."""
    try:
        return parse_date(texto or "") or padrao
    except ValueError:
        return padrao


def _taxa(numerador, denominador):
    return (numerador / denominador) if denominador else None


def reais(centavos) -> str:
    if centavos is None:
        return "ainda indisponível"
    centavos = int(centavos)
    inteiro, resto = divmod(abs(centavos), 100)
    return ("-" if centavos < 0 else "") + f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def porcento(taxa) -> str:
    if taxa is None:
        return "—"
    return f"{taxa * 100:.1f}%".replace(".", ",")


def dolares(valor) -> str:
    return f"US$ {Decimal(valor or 0):.2f}".replace(".", ",")


def _formatar_grupo(linha: dict) -> dict:
    return dict(linha, conversao_texto=porcento(linha.get("conversao")),
                liquido_texto=reais(linha.get("liquido_centavos")),
                aprovado_texto=reais(linha.get("aprovado_centavos")),
                estornos_texto=reais(linha.get("estornos_centavos")))


def _suficiente(pessoas, vendas) -> bool:
    return pessoas >= AMOSTRA_MINIMA_PESSOAS and vendas >= AMOSTRA_MINIMA_VENDAS


def _somar_compras(compras) -> dict:
    aprovado = sum(int(c.get("aprovado_centavos") or 0) for c in compras)
    estornos = sum(int(c.get("estornos_centavos") or 0) for c in compras)
    return {
        "compras_aprovadas": len(compras),
        "compras_revertidas": sum(1 for c in compras if c.get("revertida")),
        "compras_recuperadas": sum(1 for c in compras if c.get("recuperada")),
        "aprovado_centavos": aprovado,
        "estornos_centavos": estornos,
        "liquido_centavos": aprovado - estornos,
    }


def _grupo(oportunidades, compras) -> dict:
    elegiveis = len(oportunidades)
    compradores = len({c.get("lead_id") for c in compras})
    return {"elegiveis": elegiveis, "compradores": compradores,
            "conversao": round(compradores / elegiveis, 4) if elegiveis else None,
            **_somar_compras(compras)}


def _agrupar(oportunidades, compras, chave):
    grupos = defaultdict(lambda: ([], []))
    for o in oportunidades:
        grupos[o.get(chave) or "—"][0].append(o)
    for c in compras:
        grupos[c.get(chave) or "—"][1].append(c)
    return [{chave: k, **_grupo(o, c)} for k, (o, c) in sorted(grupos.items())]


# ---------------------------------------------------------------------------
# Trabalho dos agentes (dados desta célula)
# ---------------------------------------------------------------------------
def _modelos_comerciais():
    try:
        return apps.get_model("comercial", "TrabalhoComercial"), apps.get_model("comercial", "DecisaoComercial")
    except LookupError:
        return None


def fatos_dos_agentes(oportunidades: list, compras: list) -> "dict | None":
    """Interações, envios, custos e versões dos agentes para a coorte.

    `None` quando o registro dos agentes comerciais ainda não existe nesta
    célula. Trabalhos marcados como teste ficam fora.
    """
    modelos = _modelos_comerciais()
    if modelos is None:
        return None
    Trabalho, Decisao = modelos
    por_oportunidade = {o["id"]: o for o in oportunidades if o.get("id")}
    do_lead = defaultdict(list)
    for o in oportunidades:
        do_lead[o.get("lead_id")].append(o["id"])
    trabalhos = Trabalho.objects.filter(teste=False).filter(
        Q(oportunidade_id__in=list(por_oportunidade)) | Q(oportunidade_id="", contato_id__in=list(do_lead))
    )
    info = {t["id"]: t for t in trabalhos.values("id", "oportunidade_id", "contato_id", "site_id", "conversa_id", "custo_usd")}

    def alvos(trabalho):
        if trabalho["oportunidade_id"]:
            return [trabalho["oportunidade_id"]] if trabalho["oportunidade_id"] in por_oportunidade else []
        return do_lead.get(trabalho["contato_id"], [])

    custo_das_decisoes = defaultdict(Decimal)
    toques = defaultdict(list)  # oportunidade -> [(quando, papel, versao)]
    versoes = defaultdict(lambda: {"custo_usd": Decimal(0), "oportunidades": set(), "envios": defaultdict(int)})
    envios = {canal: {"enviadas": 0, "pessoas": set(), "primeiro_envio": {}} for canal in CANAIS}
    envios_sem_canal = 0
    for d in Decisao.objects.filter(trabalho_id__in=list(info)).values(
        "trabalho_id", "papel", "versao_estrategia", "ferramenta", "resultado", "custo_usd", "criada_em", "saida"
    ).order_by("criada_em", "id"):
        trabalho = info[d["trabalho_id"]]
        custo = Decimal(d["custo_usd"] or 0)
        custo_das_decisoes[d["trabalho_id"]] += custo
        chave = (d["papel"] or "—", d["versao_estrategia"])
        versoes[chave]["custo_usd"] += custo
        if d["ferramenta"] not in INTERACOES or d["resultado"] != "feito":
            continue
        for alvo in alvos(trabalho):
            toques[alvo].append((d["criada_em"], chave))
            versoes[chave]["oportunidades"].add(alvo)
        if d["ferramenta"] == "enviar_mensagem":
            saida = d["saida"] if isinstance(d["saida"], dict) else {}
            canal = saida.get("canal")
            if canal not in envios:
                envios_sem_canal += 1
                continue
            envios[canal]["enviadas"] += 1
            versoes[chave]["envios"][canal] += 1
            pessoa = trabalho["contato_id"] or trabalho["oportunidade_id"]
            envios[canal]["pessoas"].add(pessoa)
            conversa = str(saida.get("conversa_id") or trabalho["conversa_id"] or "")
            if conversa:
                envios[canal]["primeiro_envio"].setdefault(conversa, (d["criada_em"], trabalho["site_id"]))

    # O custo da rodada do modelo fica na decisão que ela gerou; o trabalho pode
    # guardar o total. Vale o maior dos dois, para não contar duas vezes.
    custo_modelos = sum(
        (max(Decimal(t["custo_usd"] or 0), custo_das_decisoes[t["id"]]) for t in info.values()), Decimal(0)
    )

    assistidas = []
    for compra in compras:
        aprovada = _instante(compra.get("aprovado_em"))
        anteriores = [t for t in toques.get(compra.get("oportunidade_id"), []) if aprovada and t[0] < aprovada]
        if anteriores:
            assistidas.append(dict(compra, versao=max(anteriores, key=lambda t: t[0])[1]))
    return {
        "trabalhos": len(info),
        "custo_modelos_usd": custo_modelos,
        "assistidas": assistidas,
        "atendidas": len(toques),
        "versoes": versoes,
        "envios": envios,
        "envios_sem_canal": envios_sem_canal,
    }


# ---------------------------------------------------------------------------
# Com agente x sem agente (grupo de comparação)
# ---------------------------------------------------------------------------
NOMES_DOS_GRUPOS = {comparacao.GRUPO_AGENTE: "Com agente", comparacao.GRUPO_COMPARACAO: "Sem agente (comparação)"}


def _respostas_por_grupo(oportunidades_por_grupo: dict, sites: set) -> "dict | None":
    """Quantas pessoas de cada grupo escreveram para a equipe depois de entrar no CRM, lendo as
    conversas ligadas a leads na mensageria. `None` quando ela não responde: aparece como
    "ainda indisponível", nunca como zero."""
    if not sites:
        return None
    cliente = ConversasClient()
    entradas = {}
    for site in sorted(sites):
        conversas = cliente.conversas(site)
        if conversas is None:
            return None
        for c in conversas:
            if c.get("lead_id"):
                entradas.setdefault((site, str(c["lead_id"])), []).append(_instante(c.get("ultima_entrada_em")))
    resposta = {}
    for grupo, oportunidades in oportunidades_por_grupo.items():
        pessoas = set()
        for o in oportunidades:
            criada = _instante(o.get("criada_em"))
            for quando in entradas.get((o.get("site_id") or "", str(o.get("lead_id"))), []):
                if quando and (criada is None or quando > criada):
                    pessoas.add(o.get("lead_id"))
        resposta[grupo] = len(pessoas)
    return resposta


def _lado(oportunidades: list, compras: list, responderam) -> dict:
    pessoas = len(oportunidades)
    compradores = len({c.get("lead_id") for c in compras})
    soma = _somar_compras(compras)
    return {
        "pessoas": pessoas, "responderam": responderam, "compras": soma["compras_aprovadas"],
        "compradores": compradores, "liquido_centavos": soma["liquido_centavos"],
        "conversao": _taxa(compradores, pessoas),
        "liquido_por_pessoa": round(soma["liquido_centavos"] / pessoas) if pessoas else None,
        "suficiente": _suficiente(pessoas, soma["compras_aprovadas"]),
    }


def _comparar(oportunidades_por_grupo: dict, compras_por_grupo: dict, responderam: "dict | None") -> dict:
    """Os dois lados e a diferença (com agente menos sem agente)."""
    lados = {g: _lado(oportunidades_por_grupo.get(g, []), compras_por_grupo.get(g, []),
                      None if responderam is None else responderam.get(g, 0))
             for g in (comparacao.GRUPO_AGENTE, comparacao.GRUPO_COMPARACAO)}
    com, sem = lados[comparacao.GRUPO_AGENTE], lados[comparacao.GRUPO_COMPARACAO]
    ha_os_dois = bool(com["pessoas"] and sem["pessoas"])
    conclusivo = ha_os_dois and com["suficiente"] and sem["suficiente"]
    diferenca = None
    if ha_os_dois:
        diferenca = {
            "conversao_pontos": round((com["conversao"] - sem["conversao"]) * 100, 1),
            "liquido_por_pessoa_centavos": com["liquido_por_pessoa"] - sem["liquido_por_pessoa"],
        }
    return {"com": com, "sem": sem, "diferenca": diferenca, "ha_os_dois": ha_os_dois, "conclusivo": conclusivo}


def comparacao_com_e_sem_agente(dados: dict, filtros: dict) -> dict:
    """A seção "Com agente x sem agente": no mesmo site, quiz, campanha, oferta e período, o que
    aconteceu com quem ficou fora do trabalho dos agentes (grupo de comparação) e com quem não.

    Só entram leads marcados (`comparacao.decidir`); lead sem marca é de antes do recurso e o
    tratamento dele não é conhecido. Testes e sandbox já saem dos totais na `leads`.
    """
    base = {"percentual": comparacao.percentual(), "grupos": NOMES_DOS_GRUPOS, "blocos": [], "marcados": 0,
            "varios_sites": False}
    oportunidades = [o for o in dados["oportunidades"] if isinstance(o, dict) and o.get("id")]
    grupos = comparacao.grupos_por_chave(
        [c for o in oportunidades for c in (o.get("chaves_de_contato") or [])], filtros.get("site_id") or "")
    marcadas = []
    for o in oportunidades:
        achados = {grupos[c] for c in (o.get("chaves_de_contato") or []) if c in grupos}
        # Uma pessoa com duas chaves de grupos diferentes é ambígua: fica fora da conta.
        if len(achados) == 1:
            marcadas.append((o, achados.pop()))
    base["marcados"] = len(marcadas)
    if not marcadas:
        return base
    grupo_da_oportunidade = {o["id"]: g for o, g in marcadas}
    site_da_oportunidade = {o["id"]: o.get("site_id") or "" for o, _ in marcadas}
    compras = [c for c in dados["compras"] if isinstance(c, dict) and c.get("oportunidade_id") in grupo_da_oportunidade]

    sites = sorted(set(site_da_oportunidade.values()))
    for site in sites:
        do_site = [(o, g) for o, g in marcadas if (o.get("site_id") or "") == site]
        compras_do_site = [c for c in compras if site_da_oportunidade[c["oportunidade_id"]] == site]
        por_grupo = {g: [o for o, gg in do_site if gg == g] for g in NOMES_DOS_GRUPOS}
        responderam = _respostas_por_grupo(por_grupo, {site}) if site else None

        def compras_de(grupo, fonte=compras_do_site):
            return [c for c in fonte if grupo_da_oportunidade[c["oportunidade_id"]] == grupo]

        geral = _comparar(por_grupo, {g: compras_de(g) for g in NOMES_DOS_GRUPOS}, responderam)
        # Mesmo quiz e mesma campanha: só se compara o que é parecido.
        celulas = sorted({(o.get("quiz") or "—", o.get("campanha") or "—") for o, _ in do_site})
        linhas = []
        for quiz, campanha in celulas:
            ops = {g: [o for o in por_grupo[g] if (o.get("quiz") or "—", o.get("campanha") or "—") == (quiz, campanha)]
                   for g in NOMES_DOS_GRUPOS}
            cps = {g: [c for c in compras_de(g) if (c.get("quiz") or "—", c.get("campanha") or "—") == (quiz, campanha)]
                   for g in NOMES_DOS_GRUPOS}
            linhas.append({"quiz": quiz, "campanha": campanha, **_comparar(ops, cps, None)})
        # Oferta é atributo da compra: o denominador é o grupo inteiro.
        ofertas = []
        for oferta in sorted({c.get("oferta") or "—" for c in compras_do_site}):
            cps = {g: [c for c in compras_de(g) if (c.get("oferta") or "—") == oferta] for g in NOMES_DOS_GRUPOS}
            ofertas.append({"oferta": oferta, **_comparar(por_grupo, cps, None)})
        base["blocos"].append({"site_id": site, "geral": geral, "linhas": linhas, "ofertas": ofertas})
    base["varios_sites"] = len(sites) > 1
    return base


# ---------------------------------------------------------------------------
# Montagem da tela
# ---------------------------------------------------------------------------
def _periodo(request):
    hoje = timezone.localdate()
    desde = _data(request.GET.get("desde", ""), hoje - timedelta(days=30))
    ate = _data(request.GET.get("ate", ""), hoje)
    if ate < desde:
        desde, ate = ate, desde
    return desde, ate


def _parametro_de_custo(request, nome, ambiente):
    texto = (request.GET.get(nome) or "").strip() or (os.environ.get(ambiente) or "").strip()
    return texto, (_decimal(texto) if texto else None)


def _resposta_por_canal(agentes, desde, ate, site_id):
    """Envio (agentes), entrega e resposta (mensageria) por canal."""
    if agentes is None:
        return {"disponivel": False, "canais": []}
    cliente = ConversasClient()
    sites = {site_id} if site_id else {s for e in agentes["envios"].values() for _, s in e["primeiro_envio"].values() if s}
    resumos = [r for r in (cliente.resumo(s, desde.isoformat(), ate.isoformat()) for s in sorted(sites)) if r]
    canais = []
    if resumos:
        juntos = defaultdict(lambda: defaultdict(int))
        for resumo in resumos:
            for linha in resumo["por_canal"]:
                if isinstance(linha, dict) and linha.get("canal") in CANAIS:
                    for campo in ("alcancadas", "enviadas", "entregues", "responderam", "descadastros"):
                        juntos[linha["canal"]][campo] += int(linha.get(campo) or 0)
        for canal in CANAIS:
            linha = juntos.get(canal)
            enviados = agentes["envios"][canal]["enviadas"]
            if not linha and not enviados:
                continue
            linha = linha or {}
            alcancadas = linha.get("alcancadas") or len(agentes["envios"][canal]["pessoas"])
            canais.append({"canal": canal, "enviadas": linha.get("enviadas", enviados), "alcancadas": alcancadas,
                           "entregues": linha.get("entregues"), "responderam": linha.get("responderam"),
                           "taxa": _taxa(linha.get("responderam") or 0, alcancadas), "fonte": "mensageria"})
        return {"disponivel": True, "canais": canais}

    lidas = {}
    for site in sorted(sites):
        conversas = cliente.conversas(site)
        if conversas is not None:
            lidas.update({str(c.get("id")): c for c in conversas})
    for canal in CANAIS:
        envio = agentes["envios"][canal]
        if not envio["enviadas"]:
            continue
        responderam = None
        if lidas:
            responderam = 0
            for conversa_id, (primeiro, _site) in envio["primeiro_envio"].items():
                entrada = _instante((lidas.get(conversa_id) or {}).get("ultima_entrada_em"))
                if entrada and primeiro and entrada > primeiro:
                    responderam += 1
        alcancadas = len(envio["pessoas"])
        canais.append({"canal": canal, "enviadas": envio["enviadas"], "alcancadas": alcancadas, "entregues": None,
                       "responderam": responderam, "taxa": _taxa(responderam, alcancadas) if responderam is not None else None,
                       "fonte": "conversas" if lidas else "agentes"})
    return {"disponivel": True, "canais": canais}


def _versoes(agentes, compras_por_versao):
    linhas = []
    for (papel, versao), dados in sorted(agentes["versoes"].items(), key=lambda i: (i[0][0], i[0][1] or 0)):
        pessoas = len(dados["oportunidades"])
        vendas = compras_por_versao.get((papel, versao), [])
        if not pessoas and not vendas:
            continue
        soma = _somar_compras(vendas)
        linhas.append({
            "papel": papel, "versao": versao, "pessoas": pessoas, "vendas": len(vendas),
            "conversao": _taxa(len(vendas), pessoas), "liquido_centavos": soma["liquido_centavos"],
            "custo_usd": dados["custo_usd"], "suficiente": _suficiente(pessoas, len(vendas)),
        })
    papeis = defaultdict(list)
    for linha in linhas:
        papeis[linha["papel"]].append(linha)
    comparacoes = []
    for papel, itens in papeis.items():
        if len(itens) < 2:
            continue
        conclusivo = all(i["suficiente"] for i in itens)
        comparacoes.append({"papel": papel, "conclusivo": conclusivo,
                            "melhor": max(itens, key=lambda i: i["conversao"] or 0)["versao"] if conclusivo else None})
    return linhas, comparacoes


def montar(request) -> "tuple[dict, int]":
    desde, ate = _periodo(request)
    filtros = {k: (request.GET.get(k) or "").strip()[:120] for k in ("quiz", "oferta", "campanha", "site_id", "estrategia")}
    contexto = {"admin": request.admin, "desde": desde, "ate": ate, "filtros": filtros,
                "amostra_pessoas": AMOSTRA_MINIMA_PESSOAS, "amostra_vendas": AMOSTRA_MINIMA_VENDAS}
    estado, dados = ResultadosClient().comerciais(
        desde=desde.isoformat(), ate=ate.isoformat(), quiz=filtros["quiz"], oferta=filtros["oferta"],
        campanha=filtros["campanha"], site_id=filtros["site_id"],
    )
    if estado != ResultadosClient.OK:
        contexto["erro"] = (
            "Os resultados ainda estão indisponíveis: o painel aguarda a conexão com os contatos."
            if estado == ResultadosClient.SEM_CONFIGURACAO
            else "Os resultados ainda estão indisponíveis: a base de contatos não respondeu. Tente de novo em instantes."
        )
        return contexto, 503

    oportunidades, compras = dados["oportunidades"], dados["compras"]
    agentes = fatos_dos_agentes(oportunidades, compras)
    contexto["agentes_disponivel"] = agentes is not None

    estrategia = filtros["estrategia"]
    if agentes is not None and ":" in estrategia:
        papel, _, numero = estrategia.partition(":")
        chave = (papel, _inteiro(numero))
        tocadas = agentes["versoes"].get(chave, {}).get("oportunidades", set())
        oportunidades = [o for o in oportunidades if o["id"] in tocadas]
        compras = [c for c in agentes["assistidas"] if c["versao"] == chave]
        totais = _grupo(oportunidades, compras)
        versao_escolhida = agentes["versoes"].get(chave) or {"custo_usd": Decimal(0), "oportunidades": set(), "envios": {}}
        contexto.update(por_quiz=_agrupar(oportunidades, compras, "quiz"),
                        por_campanha=_agrupar(oportunidades, compras, "campanha"),
                        por_oferta=[dict(i, elegiveis=len(oportunidades)) for i in _agrupar([], compras, "oferta")])
    else:
        versao_escolhida = None
        totais = dados["totais"]
        contexto.update(por_quiz=dados["por_quiz"], por_campanha=dados["por_campanha"], por_oferta=dados["por_oferta"])
    contexto["totais"] = totais
    contexto["testes_fora"] = dados.get("testes_fora") or {}
    contexto["truncado"] = bool(dados.get("oportunidades_truncadas"))
    contexto["opcoes"] = {
        "quiz": sorted({o.get("quiz") for o in dados["oportunidades"] if o.get("quiz")}),
        "campanha": sorted({o.get("campanha") for o in dados["oportunidades"] if o.get("campanha")}),
        "oferta": sorted({c.get("oferta") for c in dados["compras"] if c.get("oferta")}),
        "estrategia": sorted(f"{p}:{v}" for p, v in (agentes or {}).get("versoes", {}) if v is not None),
    }

    # Custos: cotação do dólar e tarifa das mensagens vêm do mantenedor.
    dolar_texto, dolar = _parametro_de_custo(request, "dolar", "CRM_REAIS_POR_DOLAR")
    tarifas = {canal: _parametro_de_custo(request, "tarifa_" + canal, f"CRM_CUSTO_{canal.upper()}_CENTAVOS") for canal in CANAIS}
    contexto["parametros_custo"] = {"dolar": dolar_texto, **{"tarifa_" + c: t[0] for c, t in tarifas.items()}}
    vendas = int(totais.get("compras_aprovadas") or 0)
    liquido = int(totais.get("liquido_centavos") or 0)
    faltam = ["taxas do provedor de pagamento", "processamento de áudio", "infraestrutura e serviços externos"]
    componentes = []
    custo_centavos = Decimal(0)
    if agentes is None:
        faltam = ["consumo dos modelos", "mensagens"] + faltam
        assistidas = []
        contexto["resposta"] = {"disponivel": False, "canais": []}
        contexto["versoes"], contexto["comparacoes"] = [], []
    else:
        assistidas = agentes["assistidas"] if ":" not in estrategia else compras
        usd = versao_escolhida["custo_usd"] if versao_escolhida else agentes["custo_modelos_usd"]
        contexto["custo_modelos_usd"] = usd
        if dolar is None:
            faltam.insert(0, "consumo dos modelos em reais (informe quanto vale um dólar)")
        else:
            valor = usd * dolar * 100
            custo_centavos += valor
            componentes.append(("Consumo dos modelos", valor))
        for canal in CANAIS:
            enviadas = (versao_escolhida["envios"].get(canal, 0) if versao_escolhida
                        else agentes["envios"][canal]["enviadas"])
            if not enviadas:
                continue
            tarifa = tarifas[canal][1]
            if tarifa is None:
                faltam.insert(0, f"mensagens de {'WhatsApp' if canal == 'whatsapp' else 'e-mail'} (informe a tarifa)")
            else:
                valor = tarifa * enviadas
                custo_centavos += valor
                componentes.append((f"Mensagens de {'WhatsApp' if canal == 'whatsapp' else 'e-mail'}", valor))
        contexto["resposta"] = _resposta_por_canal(agentes, desde, ate, filtros["site_id"])
        contexto["envios_sem_canal"] = agentes["envios_sem_canal"]
        por_versao = defaultdict(list)
        for compra in agentes["assistidas"]:
            por_versao[compra["versao"]].append(compra)
        contexto["versoes"], contexto["comparacoes"] = _versoes(agentes, por_versao)
    contexto["assistidas"] = len(assistidas)
    contexto["assistidas_taxa"] = _taxa(len(assistidas), vendas)
    contexto["assistidas_liquido"] = sum(int(c.get("liquido_centavos") or 0) for c in assistidas)
    contexto["componentes"] = [(nome, int(valor.to_integral_value())) for nome, valor in componentes]
    contexto["faltam"] = faltam
    contexto["custo_centavos"] = int(custo_centavos.to_integral_value()) if componentes else None
    contexto["custo_por_venda"] = int((custo_centavos / vendas).to_integral_value()) if componentes and vendas else None
    contexto["margem_centavos"] = liquido - contexto["custo_centavos"] if componentes else None
    contexto["amostra_geral_suficiente"] = _suficiente(int(totais.get("elegiveis") or 0), vendas)
    contexto["funil"] = atendimento.funil(request, desde, ate, filtros["site_id"])
    contexto["qualidade"] = atendimento.qualidade(desde, ate, filtros["site_id"])
    contexto["desempenho"] = atendimento.desempenho(desde, ate, filtros["site_id"])
    contexto["comparacao_agente"] = comparacao_com_e_sem_agente(dados, filtros)
    _formatar(contexto)
    return contexto, 200


def _formatar(contexto: dict) -> None:
    contexto["totais"] = _formatar_grupo(contexto["totais"])
    for chave in ("por_quiz", "por_campanha", "por_oferta"):
        contexto[chave] = [_formatar_grupo(linha) for linha in contexto[chave]]
    contexto["componentes"] = [(nome, reais(valor)) for nome, valor in contexto["componentes"]]
    for chave in ("custo_centavos", "custo_por_venda", "margem_centavos", "assistidas_liquido"):
        contexto[chave + "_texto"] = reais(contexto.get(chave))
    contexto["assistidas_taxa_texto"] = porcento(contexto.get("assistidas_taxa"))
    if "custo_modelos_usd" in contexto:
        contexto["custo_modelos_usd_texto"] = dolares(contexto["custo_modelos_usd"])
    for linha in contexto["resposta"]["canais"]:
        linha["nome"] = "WhatsApp" if linha["canal"] == "whatsapp" else "E-mail"
        linha["taxa_texto"] = porcento(linha.get("taxa"))
    for linha in contexto["versoes"]:
        linha["conversao_texto"] = porcento(linha.get("conversao"))
        linha["liquido_texto"] = reais(linha.get("liquido_centavos"))
        linha["custo_texto"] = dolares(linha.get("custo_usd"))
        linha["papel_nome"] = NOMES_DOS_PAPEIS.get(linha["papel"], linha["papel"])
    for linha in contexto["comparacoes"]:
        linha["papel_nome"] = NOMES_DOS_PAPEIS.get(linha["papel"], linha["papel"])
    for bloco in contexto["comparacao_agente"]["blocos"]:
        for comp in (bloco["geral"], *bloco["linhas"], *bloco["ofertas"]):
            _formatar_comparacao(comp)


def _formatar_comparacao(comp: dict) -> None:
    for lado in (comp["com"], comp["sem"]):
        lado["conversao_texto"] = porcento(lado["conversao"])
        lado["liquido_texto"] = reais(lado["liquido_centavos"])
        lado["liquido_por_pessoa_texto"] = reais(lado["liquido_por_pessoa"]) if lado["pessoas"] else "—"
    dif = comp["diferenca"]
    if dif:
        pontos = f"{dif['conversao_pontos']:+.1f}".replace(".", ",")
        dif["conversao_texto"] = f"{pontos} p.p."
        dif["liquido_por_pessoa_texto"] = reais(dif["liquido_por_pessoa_centavos"])


@require_GET
def crm_resultados(request):
    contexto, status = montar(request)
    return render(request, "admin/crm_resultados.html", contexto, status=status)
