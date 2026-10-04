"""A ficha completa do contato (`/admin/contatos/<id>/`, 03/10/2026).

A ficha de `contatos.py` mostra quem a pessoa é e a linha do tempo. Este módulo
junta o resto do que a equipe precisa para atender sem abrir cinco telas:

- **Quiz e respostas**, legíveis, como a `leads` guarda (`quizzes` da ficha).
- **Perfil** que o analista escreveu: cada afirmação com a resposta ou a
  mensagem que a sustenta; o que não tem prova aparece como hipótese.
- **Produto ou oferta de interesse**: a oferta indicada no perfil e as ofertas
  das oportunidades abertas.
- **Próximo passo e prazo**, **quem atende** e **pagamentos**, das
  oportunidades do CRM da `leads` (`GET /crm?lead_id=`), com a receita que o
  provedor confirmou.
- **Conversa**: as últimas mensagens, pela API de conversas da `mensageria`,
  com os botões de assumir e devolver o atendimento.
- **Links de compra enviados**, pela API interna do `checkout`
  (`GET /interno/pedidos?oportunidade_ref=`).

## Cada parte cai sozinha

Cada fonte é uma célula, e cada uma pode estar fora do ar ou ainda não ter a
capacidade publicada. A ficha nunca vira erro por isso: a parte que faltou diz
"ainda indisponível" e o resto aparece. Lista vazia só quando a fonte
respondeu e não há nada.

## Nada de um contato na ficha de outro

As conversas são pedidas por `site_id` e `lead_id` da própria ficha; os links,
por oportunidade deste contato; e o que volta ainda é filtrado pelo mesmo
contato antes de ir para a tela. Assumir ou devolver só vale para conversa que
a `mensageria` diz ser deste contato.
"""

from __future__ import annotations

import logging
import os
from urllib.parse import quote

import httpx
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from .clients import http
from .crm_client import CRMClient

logger = logging.getLogger(__name__)

#: Desfechos comuns às fontes da ficha.
OK = "ok"
SEM_CONFIGURACAO = "sem-configuracao"
NAO_RESPONDEU = "nao-respondeu"
#: A rota ainda não existe do outro lado (capacidade não publicada).
INDISPONIVEL = "indisponivel"
NAO_EXISTE = "nao-existe"
SEM_GRAU = "sem-grau"
RECUSADO = "recusado"

#: Quantas mensagens da conversa aparecem na ficha.
MENSAGENS_NA_FICHA = 10
#: Quantas oportunidades têm os links de compra consultados.
OPORTUNIDADES_COM_LINKS = 5
#: O `autor_id` do histórico do CRM cabe em 100 caracteres do outro lado.
AUTOR_MAXIMO = 100

ETAPAS = {
    "nova": "Nova", "qualificada": "Qualificada", "proposta": "Proposta",
    "negociacao": "Em negociação", "ganha": "Ganha", "perdida": "Perdida",
    "desqualificada": "Encerrada",
}
SITUACOES_DO_QUIZ = {"completo": "Concluído", "parcial": "Não concluído"}
CANAIS = {"whatsapp": "WhatsApp", "email": "E-mail"}
ESTADOS_DA_CONVERSA = {
    "agente": "Assistente da equipe",
    "pessoa": "Pessoa da equipe",
    "encerrada": "Conversa encerrada",
}
CAMPOS_DO_PERFIL = (
    ("objetivo_declarado", "Objetivo"),
    ("experiencia", "Experiência"),
    ("disponibilidade", "Disponibilidade"),
    ("duvidas", "Dúvida"),
    ("objecoes", "Objeção"),
    ("hipoteses", "Hipótese"),
)
TIPOS_DE_EVIDENCIA = {
    "resposta": "Resposta do quiz",
    "resposta_quiz": "Resposta do quiz",
    "quiz": "Resposta do quiz",
    "mensagem": "Mensagem",
    "respostas": "Resposta do quiz",
    "evento": "Atividade",
    "timeline": "Atividade",
    "linha_do_tempo": "Atividade",
    "oportunidade": "Acompanhamento",
    "historico": "Acompanhamento",
    "nota": "Acompanhamento",
    "pedido": "Pedido",
}
PRIORIDADES = {"alta": "Alta", "media": "Média", "baixa": "Baixa"}
SITUACOES_DA_COMPRA = {
    "aprovada": "Pago (confirmado pelo provedor)",
    "revertida": "Devolvido ou contestado",
    "recuperacao": "Pagamento falhou",
    "pendente": "Aguardando pagamento",
}
SITUACOES_DO_PEDIDO = {
    "aguardando_dados": "Link enviado, ainda não aberto",
    "pendente": "Pedido feito, aguardando pagamento",
    "aguardando_pagamento": "Pedido feito, aguardando pagamento",
    "pago": "Pago (confirmado pelo provedor)",
    "reembolsado": "Reembolsado",
    "expirado": "Venceu sem pagar",
    "cancelado": "Cancelado",
    "recusado": "Pagamento recusado",
}


# ---------------------------------------------------------------------------
# Leitura tolerante
# ---------------------------------------------------------------------------


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _data(texto):
    if not isinstance(texto, str) or not texto:
        return None
    try:
        data = parse_datetime(texto)
    except ValueError:
        return None
    if data is None:
        return None
    if timezone.is_naive(data):
        data = timezone.make_aware(data, timezone.get_default_timezone())
    return timezone.localtime(data)


def _inteiro(valor):
    if isinstance(valor, bool) or not isinstance(valor, int):
        return None
    return valor


def dinheiro(centavos) -> str:
    centavos = _inteiro(centavos)
    if centavos is None:
        return ""
    sinal = "-" if centavos < 0 else ""
    inteiro, resto = divmod(abs(centavos), 100)
    return f"{sinal}R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _oferta_da_referencia(referencia) -> str:
    referencia = _texto(referencia)
    return referencia[len("oferta:"):] if referencia.startswith("oferta:") else ""


# ---------------------------------------------------------------------------
# Quiz e perfil (vêm na própria ficha da `leads`)
# ---------------------------------------------------------------------------


def montar_quizzes(bruto):
    """`None` quando a `leads` ainda não entrega quizzes; senão a lista."""
    if not isinstance(bruto, list):
        return None
    quizzes = []
    for quiz in bruto:
        if not isinstance(quiz, dict):
            continue
        respostas = []
        for item in quiz.get("respostas") or []:
            if not isinstance(item, dict):
                continue
            escolhidas = [
                _texto(opcao.get("texto")) if isinstance(opcao, dict) else _texto(opcao)
                for opcao in item.get("respostas") or []
            ]
            escolhidas = [texto for texto in escolhidas if texto]
            livre = _texto(item.get("valor_livre"))
            if livre:
                escolhidas.append(livre)
            respostas.append({
                "pergunta": _texto(item.get("pergunta")) or "Pergunta sem texto",
                "resposta": "; ".join(escolhidas) or "Sem resposta",
            })
        situacao = _texto(quiz.get("situacao"))
        quizzes.append({
            "quiz": _texto(quiz.get("quiz_slug")) or "quiz",
            "situacao": SITUACOES_DO_QUIZ.get(situacao, "Em andamento"),
            "completo": situacao == "completo",
            "resultado": _texto(quiz.get("resultado")),
            "quando": _data(quiz.get("completado_em")) or _data(quiz.get("atualizado_em"))
            or _data(quiz.get("criado_em")),
            "campanha": _texto(quiz.get("campanha")),
            "respostas": respostas,
        })
    return quizzes


def _evidencias(bruto) -> list:
    saida = []
    for item in bruto or []:
        if not isinstance(item, dict):
            continue
        tipo = _texto(item.get("tipo"))
        saida.append({
            # Tipo que a ficha ainda não conhece aparece como a `leads` o chama.
            "tipo": TIPOS_DE_EVIDENCIA.get(tipo.casefold()) or tipo or "Registro",
            "trecho": _texto(item.get("trecho")) or "(sem trecho)",
        })
    return saida


def _afirmacao(rotulo, bruto):
    if isinstance(bruto, str):
        bruto = {"texto": bruto}
    if not isinstance(bruto, dict) or not _texto(bruto.get("texto")):
        return None
    evidencias = _evidencias(bruto.get("evidencias"))
    return {
        "rotulo": rotulo,
        "texto": _texto(bruto.get("texto")),
        "evidencias": evidencias,
        # Sem prova é hipótese, diga a `leads` o que disser.
        "hipotese": bool(bruto.get("hipotese")) or not evidencias,
    }


def montar_perfil(ficha: dict):
    """`{"estado": ...}`: indisponivel, sem_analise ou ok (com o perfil)."""
    if "perfil" not in ficha:
        return {"estado": "indisponivel"}
    bruto = ficha.get("perfil")
    if not isinstance(bruto, dict):
        return {"estado": "sem_analise"}
    afirmacoes = []
    for campo, rotulo in CAMPOS_DO_PERFIL:
        valor = bruto.get(campo)
        itens = valor if isinstance(valor, list) else [valor]
        for item in itens:
            afirmacao = _afirmacao(rotulo, item)
            if afirmacao:
                afirmacoes.append(afirmacao)
    prioridade = bruto.get("prioridade") if isinstance(bruto.get("prioridade"), dict) else {}
    oferta = bruto.get("oferta_indicada") if isinstance(bruto.get("oferta_indicada"), dict) else None
    novos = _inteiro(bruto.get("fatos_novos_desde_a_analise")) or 0
    return {
        "estado": "ok",
        "resumo": _texto(bruto.get("resumo")),
        "afirmacoes": afirmacoes,
        "prioridade": PRIORIDADES.get(_texto(prioridade.get("nivel")), ""),
        "prioridade_explicacao": _texto(prioridade.get("explicacao")),
        "oferta_indicada": {
            "nome": _texto(oferta.get("nome")) or _texto(oferta.get("oferta_ref")),
            "motivo": _texto(oferta.get("motivo")),
            "evidencias": _evidencias(oferta.get("evidencias")),
        } if oferta else None,
        "informacoes_ausentes": [t for t in map(_texto, bruto.get("informacoes_ausentes") or []) if t],
        "perguntas_uteis": [t for t in map(_texto, bruto.get("perguntas_uteis") or []) if t],
        "analisado_em": _data(bruto.get("analisado_em")),
        "versao": _inteiro(bruto.get("versao")),
        "fatos_novos": novos,
    }


# ---------------------------------------------------------------------------
# Oportunidades: próximo passo, prazo, quem atende e pagamentos
# ---------------------------------------------------------------------------


def _compra(bruto) -> dict:
    situacao = _texto(bruto.get("situacao"))
    produtos = [p for p in (bruto.get("produtos") or []) if isinstance(p, str) and p]
    return {
        "pedido_id": _texto(bruto.get("pedido_id")),
        "situacao": SITUACOES_DA_COMPRA.get(situacao, "Situação desconhecida"),
        "confirmada": situacao == "aprovada",
        "oferta": _texto(bruto.get("oferta_ref")) or ", ".join(produtos[:3]),
        "valor": dinheiro(bruto.get("valor_pedido_centavos")),
        "aprovado": dinheiro(bruto.get("aprovado_centavos")),
        "estornos": dinheiro(bruto.get("estornos_centavos"))
        if _inteiro(bruto.get("estornos_centavos")) else "",
        "aprovado_em": _data(bruto.get("aprovado_em")),
        "revertida_em": _data(bruto.get("revertida_em")),
    }


def montar_oportunidade(bruto: dict) -> dict:
    passo = bruto.get("proximo_passo") if isinstance(bruto.get("proximo_passo"), dict) else {}
    prazo = _data(bruto.get("prazo")) or _data(passo.get("executar_ate"))
    aberta = bruto.get("situacao") == "aberta"
    atendido = bruto.get("atendido_por") if isinstance(bruto.get("atendido_por"), dict) else None
    receita = bruto.get("receita") if isinstance(bruto.get("receita"), dict) else None
    fonte = bruto.get("fonte") if isinstance(bruto.get("fonte"), dict) else {}
    return {
        "id": _texto(bruto.get("id")),
        "etapa": ETAPAS.get(_texto(bruto.get("etapa")), "Etapa desconhecida"),
        "aberta": aberta,
        "oferta": _oferta_da_referencia(fonte.get("referencia_id")),
        "proximo_passo": _texto(passo.get("descricao")),
        "prazo": prazo,
        "atrasada": bool(aberta and prazo and prazo < timezone.now()),
        "atendido_por": {
            "tipo": "Pessoa da equipe" if atendido.get("tipo") == "pessoa" else "Assistente da equipe",
            "nome": _texto(atendido.get("nome")),
        } if atendido and atendido.get("tipo") else None,
        "aguardando_resposta": bruto.get("aguardando_resposta") is True,
        "objecao": _texto(bruto.get("objecao_principal")),
        "ultimo_contato_em": _data(bruto.get("ultimo_contato_em")),
        "tem_receita": receita is not None,
        "liquido": dinheiro(receita.get("liquido_centavos")) if receita else "",
        "compras": [_compra(c) for c in (receita or {}).get("compras") or [] if isinstance(c, dict)],
    }


def oportunidades_do_contato(lead_id: str):
    """`(estado, [oportunidades montadas])`, só as deste contato."""
    estado, dados = CRMClient().quadro(lead_id=str(lead_id), testes="mostrar", por_pagina=100)
    if estado != CRMClient.OK:
        return (SEM_CONFIGURACAO if estado == CRMClient.SEM_CONFIGURACAO else NAO_RESPONDEU), []
    itens = [
        montar_oportunidade(item)
        for item in dados["itens"]
        if isinstance(item, dict) and str(item.get("lead_id", lead_id)) == str(lead_id)
    ]
    # Abertas primeiro; entre elas, o prazo mais perto.
    itens.sort(key=lambda o: (not o["aberta"], o["prazo"] is None, o["prazo"] or timezone.now()))
    return OK, itens


def pagamentos_das_oportunidades(oportunidades: list):
    """Compras confirmadas pelo provedor, cada pedido uma vez.

    `None` quando a `leads` ainda não entrega a receita das oportunidades.
    """
    if oportunidades and not any(o["tem_receita"] for o in oportunidades):
        return None
    vistas, compras = set(), []
    for oportunidade in oportunidades:
        for compra in oportunidade["compras"]:
            chave = compra["pedido_id"] or id(compra)
            if chave in vistas:
                continue
            vistas.add(chave)
            compras.append(compra)
    return compras


# ---------------------------------------------------------------------------
# Conversas (mensageria)
# ---------------------------------------------------------------------------


class ConversasClient:
    """Conversas de um contato na `mensageria` (`/conversas`).

    Leitura fail-OPEN, escrita fail-CLOSED, como o `MensageriaClient`. Usa o
    mesmo par `MENSAGERIA_API_URL`/`MENSAGERIA_API_TOKEN`; para assumir e
    devolver, o par precisa do grau de escrita, e o 403 vira `SEM_GRAU`.
    """

    TIMEOUT = 4.0

    def _configuracao(self):
        base = (os.environ.get("MENSAGERIA_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("MENSAGERIA_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def _pedir(self, metodo, caminho, *, params=None, corpo=None):
        config = self._configuracao()
        if config is None:
            return SEM_CONFIGURACAO, None
        base, token = config
        try:
            resposta = http().request(
                metodo, base + caminho, params=params, json=corpo,
                headers={"Authorization": "Bearer " + token}, timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("ficha: a mensageria não respondeu: %s", erro)
            return NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return NAO_EXISTE, None
        if resposta.status_code in (401, 403):
            return SEM_GRAU, None
        if resposta.status_code in (409, 422):
            return RECUSADO, None
        if resposta.status_code != 200:
            logger.error("ficha: a mensageria respondeu HTTP %s", resposta.status_code)
            return NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return NAO_RESPONDEU, None
        return (OK, dados) if isinstance(dados, dict) else (NAO_RESPONDEU, None)

    def conversas(self, site_id: str, lead_id: str):
        estado, dados = self._pedir(
            "GET", "/conversas", params={"site_id": site_id, "lead_id": str(lead_id)}
        )
        if estado == NAO_EXISTE:
            return INDISPONIVEL, []
        if estado == SEM_GRAU:
            return NAO_RESPONDEU, []
        if estado != OK:
            return estado, []
        if not isinstance(dados.get("itens"), list):
            return NAO_RESPONDEU, []
        return OK, [
            c for c in dados["itens"]
            if isinstance(c, dict) and str(c.get("lead_id")) == str(lead_id)
            and c.get("site_id", site_id) == site_id and c.get("id")
        ]

    def mensagens(self, conversa_id: str, site_id: str, limite: int = MENSAGENS_NA_FICHA):
        estado, dados = self._pedir(
            "GET", "/conversas/" + quote(str(conversa_id), safe="") + "/mensagens",
            params={"site_id": site_id, "limite": limite},
        )
        if estado != OK or not isinstance(dados.get("mensagens"), list):
            return (estado if estado != OK else NAO_RESPONDEU), []
        return OK, [m for m in dados["mensagens"] if isinstance(m, dict)]

    def assumir(self, conversa_id: str, site_id: str, pessoa_id: str):
        return self._pedir(
            "POST", "/conversas/" + quote(str(conversa_id), safe="") + "/assumir",
            corpo={"site_id": site_id, "pessoa_id": pessoa_id[:AUTOR_MAXIMO]},
        )

    def devolver(self, conversa_id: str, site_id: str):
        return self._pedir(
            "POST", "/conversas/" + quote(str(conversa_id), safe="") + "/devolver",
            corpo={"site_id": site_id},
        )


def _mensagem(bruto: dict) -> dict:
    autor = _texto(bruto.get("autor"))
    entrada = bruto.get("direcao") == "entrada"
    if entrada:
        quem = "Contato"
    elif autor == "pessoa":
        quem = "Equipe" + (f" ({_texto(bruto.get('autor_id'))})" if _texto(bruto.get("autor_id")) else "")
    else:
        quem = "Assistente da equipe"
    texto = _texto(bruto.get("texto")) or _texto(bruto.get("transcricao"))
    if not texto and isinstance(bruto.get("midia"), dict):
        texto = "(mídia sem transcrição)"
    return {
        "entrada": entrada,
        "quem": quem,
        "texto": texto,
        "quando": _data(bruto.get("ocorrida_em")),
        "falhou": _texto(bruto.get("estado_envio")) in ("falhou", "erro"),
    }


def _conversa(bruto: dict) -> dict:
    estado = _texto(bruto.get("estado"))
    return {
        "id": _texto(bruto.get("id")),
        "canal": CANAIS.get(_texto(bruto.get("canal")), "Outro canal"),
        "estado": estado,
        "quem_atende": ESTADOS_DA_CONVERSA.get(estado, "Situação desconhecida"),
        "assumida_por": _texto(bruto.get("assumida_por")),
        "janela_aberta": bruto.get("janela_aberta") is True,
        "descadastrado": bruto.get("descadastrado") is True,
        "ambigua": bruto.get("ambigua") is True,
        "ultima_mensagem_em": _data(bruto.get("ultima_mensagem_em")),
    }


def escolher_conversa_atual(conversas: list):
    """A conversa que a ficha mostra e que os botões usam, escolhida uma vez.

    A primeira que não foi encerrada; se todas foram, a mais recente.
    `conversas` já vem da mais recente para a mais antiga.
    """
    return next((c for c in conversas if c["estado"] != "encerrada"), conversas[0] if conversas else None)


def conversa_do_contato(site_id: str, lead_id: str) -> dict:
    """As conversas do contato e as últimas mensagens da conversa atual."""
    cliente = ConversasClient()
    estado, conversas = cliente.conversas(site_id, lead_id)
    if estado != OK:
        return {"estado": estado, "conversas": [], "atual": None, "mensagens": []}
    conversas = sorted(
        conversas, key=lambda c: _texto(c.get("ultima_mensagem_em")) or "", reverse=True
    )
    montadas = [_conversa(c) for c in conversas]
    atual = escolher_conversa_atual(montadas)
    mensagens, estado_mensagens = [], OK
    if atual:
        estado_mensagens, brutas = cliente.mensagens(atual["id"], site_id)
        mensagens = [_mensagem(m) for m in brutas][-MENSAGENS_NA_FICHA:]
    return {
        "estado": OK,
        "conversas": montadas,
        "atual": atual,
        "mensagens": mensagens,
        "mensagens_indisponiveis": estado_mensagens != OK,
    }


def url_da_caixa_de_conversas() -> str:
    """Endereço da caixa de conversas do painel, ou `""` se esta versão não a tem."""
    try:
        return reverse("crm_conversas")
    except NoReverseMatch:
        return ""


# ---------------------------------------------------------------------------
# Links de compra (checkout)
# ---------------------------------------------------------------------------


class LinksDeCompraClient:
    """Pedidos e links de uma oportunidade no `checkout` (`/interno/pedidos`).

    O checkout descobre o site pelo `Host`; a ficha manda o host do painel,
    como a tela de campanhas faz. Só leitura e fail-OPEN.
    """

    TIMEOUT = 2.0

    def _configuracao(self):
        base = (os.environ.get("CHECKOUT_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("CHECKOUT_API_TOKEN") or "").strip()
        return (base, token) if base and token else None

    def pedidos(self, oportunidade_ref: str, host: str):
        config = self._configuracao()
        if config is None:
            return SEM_CONFIGURACAO, None
        base, token = config
        try:
            resposta = http().get(
                base + "/interno/pedidos", params={"oportunidade_ref": oportunidade_ref},
                headers={"Authorization": "Bearer " + token, "Host": host},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError as erro:
            logger.error("ficha: o checkout não respondeu: %s", erro)
            return NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return INDISPONIVEL, None
        if resposta.status_code != 200:
            return NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return NAO_RESPONDEU, None
        if not isinstance(dados, dict) or not isinstance(dados.get("pedidos"), list):
            return NAO_RESPONDEU, None
        return OK, dados


def _link(bruto: dict, oportunidade: dict) -> dict:
    status = _texto(bruto.get("status"))
    url = _texto(bruto.get("url"))
    return {
        "pedido_id": _texto(bruto.get("pedido_id")),
        "oferta": _texto(bruto.get("oferta_ref")) or oportunidade.get("oferta", ""),
        "situacao": SITUACOES_DO_PEDIDO.get(status, "Situação desconhecida"),
        "confirmado": bruto.get("confirmado") is True,
        "valor": dinheiro(bruto.get("valor_cents")),
        "criado_em": _data(bruto.get("criado_em")),
        "pago_em": _data(bruto.get("pago_em")),
        # Só endereço https vira link clicável.
        "url": url if url.startswith("https://") else "",
    }


def links_das_oportunidades(oportunidades: list, host: str) -> dict:
    if not oportunidades:
        return {"estado": OK, "links": []}
    cliente = LinksDeCompraClient()
    links, estados = [], set()
    for oportunidade in oportunidades[:OPORTUNIDADES_COM_LINKS]:
        if not oportunidade["id"]:
            continue
        estado, dados = cliente.pedidos(oportunidade["id"], host)
        estados.add(estado)
        if estado == NAO_RESPONDEU:
            # O checkout não está respondendo: perguntar de novo para cada
            # oportunidade só faria a ficha esperar o prazo várias vezes. As que
            # sobraram contam como "não responderam".
            break
        if estado != OK:
            continue
        if _texto(dados.get("oportunidade_ref")) not in ("", oportunidade["id"]):
            continue
        for pedido in dados["pedidos"]:
            if isinstance(pedido, dict) and _texto(pedido.get("oportunidade_ref")) in ("", oportunidade["id"]):
                links.append(_link(pedido, oportunidade))
    if OK not in estados:
        estado = (SEM_CONFIGURACAO if SEM_CONFIGURACAO in estados
                  else INDISPONIVEL if INDISPONIVEL in estados else NAO_RESPONDEU)
        return {"estado": estado, "links": []}
    links.sort(key=lambda l: l["criado_em"] or timezone.now(), reverse=True)
    return {"estado": OK, "links": links, "parcial": len(estados) > 1}


# ---------------------------------------------------------------------------
# Juntando tudo
# ---------------------------------------------------------------------------


def quem_atende(conversa: dict, oportunidades: list) -> dict:
    """Pessoa ou agente. A conversa manda; sem conversa, vale o CRM."""
    atual = conversa.get("atual")
    if atual and atual["estado"] != "encerrada":
        if atual["estado"] == "pessoa":
            nome = atual["assumida_por"]
            return {"tipo": "pessoa", "texto": "Pessoa da equipe" + (f": {nome}" if nome else "")}
        return {"tipo": "agente", "texto": "Assistente da equipe (agente)"}
    for oportunidade in oportunidades:
        if oportunidade["aberta"] and oportunidade["atendido_por"]:
            atendido = oportunidade["atendido_por"]
            tipo = "pessoa" if atendido["tipo"] == "Pessoa da equipe" else "agente"
            texto = atendido["tipo"] + (f": {atendido['nome']}" if atendido["nome"] else "")
            return {"tipo": tipo, "texto": texto}
    return {"tipo": "", "texto": "Ninguém atendendo ainda"}


def interesse(perfil: dict, oportunidades: list, quizzes) -> list:
    """Produtos ou ofertas de interesse, sem repetir."""
    vistos, saida = set(), []

    def juntar(nome, origem):
        if nome and nome.lower() not in vistos:
            vistos.add(nome.lower())
            saida.append({"nome": nome, "origem": origem})

    if perfil.get("estado") == "ok" and perfil.get("oferta_indicada"):
        juntar(perfil["oferta_indicada"]["nome"], "Indicada no perfil")
    for oportunidade in oportunidades:
        if oportunidade["aberta"]:
            juntar(oportunidade["oferta"], "Oportunidade aberta")
    for quiz in quizzes or []:
        juntar(quiz["resultado"], f"Resultado do quiz {quiz['quiz']}")
    return saida


def completar_ficha(tela: dict, resposta: dict, *, host: str) -> dict:
    """Acrescenta à ficha básica as partes das outras células."""
    lead_id = str(tela.get("id") or "")
    quizzes = montar_quizzes(resposta.get("quizzes"))
    perfil = montar_perfil(resposta)
    estado_crm, oportunidades = oportunidades_do_contato(lead_id) if lead_id else (NAO_RESPONDEU, [])
    conversa = (
        conversa_do_contato(tela["site_id"], lead_id)
        if lead_id and tela.get("site_id")
        else {"estado": INDISPONIVEL, "conversas": [], "atual": None, "mensagens": []}
    )
    tela.update({
        "quizzes": quizzes,
        "perfil": perfil,
        "crm_estado": estado_crm,
        "oportunidades": oportunidades,
        "proxima": next((o for o in oportunidades if o["aberta"]), None),
        "pagamentos": pagamentos_das_oportunidades(oportunidades) if estado_crm == OK else None,
        "conversa": conversa,
        "caixa_de_conversas": url_da_caixa_de_conversas(),
        "links": links_das_oportunidades(oportunidades, host) if estado_crm == OK
        else {"estado": INDISPONIVEL, "links": []},
        "atendimento": quem_atende(conversa, oportunidades),
        "interesse": interesse(perfil, oportunidades, quizzes),
    })
    return tela


def marcar_atendimento_no_crm(oportunidades: list, *, tipo: str, nome: str, autor: str) -> bool:
    """Melhor esforço: o quadro do CRM passa a mostrar quem atende.

    Quem manda é a conversa na `mensageria`; se a `leads` não aceitar, a
    conversa já mudou e a ficha continua certa. Devolve `False` quando alguma
    oportunidade não foi marcada, para a ficha avisar a equipe.
    """
    cliente = CRMClient()
    tudo_certo = True
    for oportunidade in oportunidades:
        if not oportunidade["aberta"] or not oportunidade["id"]:
            continue
        estado, _ = cliente.alterar(
            oportunidade["id"], "PATCH", "/acompanhamento",
            {"autor_id": autor[:AUTOR_MAXIMO], "atendido_por": {"tipo": tipo, "nome": nome}},
        )
        if estado != CRMClient.OK:
            tudo_certo = False
            logger.warning("ficha: o CRM não registrou quem atende (%s)", estado)
    return tudo_certo
