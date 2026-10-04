"""Caixa de conversas do CRM: o que o lead escreveu e o que a casa respondeu.

As conversas são dado da célula `mensageria` (WhatsApp e e-mail nos dois
sentidos). O painel só pergunta pela API dela, sempre com o site do domínio
pelo qual a tela foi aberta: conversa de outro site nunca aparece aqui.

Gestos da pessoa da equipe: assumir (o agente para de responder), devolver ao
agente e responder como pessoa. Responder assume a conversa antes de enviar,
para o agente não falar por cima de quem está atendendo; se o envio não sair
no mesmo pedido, a conversa volta sozinha para o agente.
"""
import uuid
from urllib.parse import quote, urlencode

import httpx
from django.db import DatabaseError
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_http_methods

from apps.auditoria.models import Registro
from .clients import CatalogoClient, LeadsClient, MensageriaClient, http
from .crm_client import CRMClient
from .models import AparelhoDaEquipe, MembroDaEquipe

OK = "ok"
SEM_CONFIGURACAO = "sem_configuracao"
INDISPONIVEL = "indisponivel"  # a mensageria ainda não tem a caixa de conversas
NAO_EXISTE = "nao_existe"
RECUSADO = "recusado"
NAO_RESPONDEU = "nao_respondeu"
TEMPO_ESGOTADO = "tempo_esgotado"  # escrita que não voltou a tempo: pode ter saído
INCERTO = "incerto"  # a mensageria aceitou, mas não confirmou a entrega

FILTROS = (
    ("", "Todas"),
    ("agente", "Com o agente"),
    ("pessoa", "Com uma pessoa"),
    ("aguardando", "Aguardando resposta"),
    ("ambigua", "Contato ambíguo"),
    ("encerrada", "Encerradas"),
)
CANAIS = {"whatsapp": "WhatsApp", "email": "E-mail"}
ESTADOS = {"agente": "Com o agente", "pessoa": "Com uma pessoa", "encerrada": "Encerrada"}
ENVIOS = {
    "recebida": "Recebida", "pendente": "Enviando", "aceito": "Aceita pelo provedor",
    "enviado": "Enviada", "entregue": "Entregue", "lido": "Lida", "falhou": "Falhou",
    "reservado": "Reservada para envio", "desconhecido": "Resultado incerto — confira antes de repetir",
}
# Só estes estados dizem que a mensagem de fato saiu.
ENTREGA_CONFIRMADA = ("enviado", "entregue", "lido")
# No máximo esta quantidade de buscas por página para completar o último recado.
RECADOS_POR_PAGINA = 10
MENSAGENS_POR_PAGINA = 100
AUTORES = {"lead": "Contato", "agente": "Agente", "pessoa": "Equipe", "sistema": "Sistema"}
MIDIAS = {"audio": "Áudio", "imagem": "Imagem", "video": "Vídeo", "documento": "Documento"}
RESULTADOS = {
    "enviada": "Mensagem enviada.",
    "repetida": "Esta resposta já tinha sido enviada. Não enviamos de novo.",
}
NAO_CONFIRMADA = "Enviada, mas a entrega não foi confirmada; veja o histórico antes de reenviar."
PODE_TER_SAIDO = "O envio pode ter saído: o serviço de mensagens demorou para responder. Confira o histórico antes de reenviar."
CONTINUA_COM_O_AGENTE = " Nada foi enviado; a conversa continua com o agente."
# Respostas em que a mensageria diz que NADA foi enviado.
RECUSAS = {
    "fora_da_janela": "Não enviada: já passaram 24 horas desde a última mensagem do contato no WhatsApp. Agora só um modelo aprovado pode ser enviado.",
    "descadastrado": "Não enviada: o contato pediu para não receber mais mensagens neste canal. Só dá para responder quando ele escrever de novo.",
    "conversa_com_pessoa": "Não enviada: outra pessoa da equipe está atendendo esta conversa.",
    "sem_consentimento": "Esta pessoa ainda não autorizou receber mensagens por WhatsApp.",
    "fora_do_horario": "Não enviada: agora está fora do horário permitido para enviar mensagens. Tente de novo dentro do horário.",
    "limite_diario": "Não enviada: o limite de mensagens do dia já foi atingido. Tente de novo amanhã.",
    "limite_do_dia": "Não enviada: o limite de mensagens do dia já foi atingido. Tente de novo amanhã.",
}


class ConversasClient:
    """`/conversas` da mensageria. Leitura falha aberta, escrita falha fechada."""

    TIMEOUT = 5.0
    TIMEOUT_ESCRITA = 15.0

    def pedir(self, metodo, caminho, *, params=None, corpo=None):
        config = MensageriaClient()._configuracao()
        if config is None:
            return SEM_CONFIGURACAO, None
        base, token = config
        escrita = metodo != "GET"
        try:
            resposta = http().request(
                metodo, base + "/conversas" + caminho, params=params, json=corpo,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT_ESCRITA if escrita else self.TIMEOUT,
            )
        except (httpx.ReadTimeout, httpx.WriteTimeout):
            # O pedido saiu e a resposta não voltou: numa escrita, pode ter valido.
            return (TEMPO_ESGOTADO if escrita else NAO_RESPONDEU), None
        except httpx.HTTPError:
            return NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return NAO_EXISTE, None
        if resposta.status_code in (403, 409, 422):
            try:
                detalhe = resposta.json().get("detail")
            except (ValueError, AttributeError):
                detalhe = None
            return RECUSADO, detalhe if isinstance(detalhe, str) else ""
        if resposta.status_code != 200:
            return NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return NAO_RESPONDEU, None
        return (OK, dados) if isinstance(dados, dict) else (NAO_RESPONDEU, None)

    def listar(self, site_id, **filtros):
        estado, dados = self.pedir("GET", "", params={"site_id": site_id, **{k: v for k, v in filtros.items() if v not in ("", None)}})
        if estado == NAO_EXISTE:
            # A rota inteira não existe: a mensageria publicada ainda não tem a caixa.
            return INDISPONIVEL, None
        if estado == OK and not isinstance(dados.get("itens"), list):
            return NAO_RESPONDEU, None
        return estado, dados

    def mensagens(self, site_id, conversa_id, limite=MENSAGENS_POR_PAGINA, antes_de=""):
        params = {"site_id": site_id, "limite": limite}
        if antes_de:
            params["antes_de"] = antes_de
        estado, dados = self.pedir("GET", "/" + quote(str(conversa_id), safe="") + "/mensagens", params=params)
        if estado == OK and (not isinstance(dados.get("conversa"), dict) or not isinstance(dados.get("mensagens"), list)):
            return NAO_RESPONDEU, None
        return estado, dados

    def gesto(self, conversa_id, acao, corpo):
        return self.pedir("POST", "/" + quote(str(conversa_id), safe="") + "/" + acao, corpo=corpo)


def instante(texto):
    try:
        data = parse_datetime(texto) if isinstance(texto, str) else None
    except (ValueError, TypeError):
        return None
    return timezone.localtime(data) if data and timezone.is_aware(data) else data


def ficha_do_lead(lead_id):
    try:
        return reverse("contato", args=[uuid.UUID(str(lead_id))]) if lead_id else ""
    except (ValueError, NoReverseMatch):
        return ""


def aguardando(conversa):
    """O contato falou por último e ninguém respondeu ainda.

    Quem pediu para parar não espera resposta: não há o que responder."""
    entrada, ultima = conversa.get("ultima_entrada"), conversa.get("ultima")
    if conversa.get("estado") == "encerrada" or conversa.get("descadastrado"):
        return False
    return bool(entrada and ultima and entrada >= ultima)


def preparar_conversa(item):
    item = dict(item)
    item["canal_nome"] = CANAIS.get(item.get("canal"), item.get("canal") or "")
    item["estado_nome"] = ESTADOS.get(item.get("estado"), item.get("estado") or "")
    item["ultima"] = instante(item.get("ultima_mensagem_em"))
    item["ultima_entrada"] = instante(item.get("ultima_entrada_em"))
    item["janela_ate"] = instante(item.get("janela_aberta_ate"))
    item["aguardando"] = aguardando(item)
    item["ficha"] = "" if item.get("ambigua") else ficha_do_lead(item.get("lead_id"))
    recado = item.get("ultima_mensagem") if isinstance(item.get("ultima_mensagem"), dict) else None
    item["recado"] = preparar_mensagem(recado) if recado else None
    return item


def preparar_mensagem(item):
    item = dict(item)
    item["momento"] = instante(item.get("ocorrida_em"))
    item["autor_nome"] = AUTORES.get(item.get("autor"), item.get("autor") or "")
    item["envio_nome"] = ENVIOS.get(item.get("estado_envio"), item.get("estado_envio") or "")
    midia = item.get("midia") if isinstance(item.get("midia"), dict) else None
    item["midia_nome"] = MIDIAS.get((midia or {}).get("tipo"), (midia or {}).get("tipo") or "") if midia else ""
    item["resumo"] = (item.get("texto") or item.get("transcricao") or (item["midia_nome"] and f"[{item['midia_nome']}]") or "").strip()
    return item


def site_do_pedido(request):
    site = CatalogoClient().site_por_host(request.get_host().split(":")[0].lower())
    return site.get("id") if isinstance(site, dict) and site.get("id") else None


def erro_da_fonte(estado):
    if estado == SEM_CONFIGURACAO:
        return "A caixa de conversas está aguardando a conexão com a mensageria."
    if estado == INDISPONIVEL:
        return "A caixa de conversas ainda não está disponível neste site. Assim que a mensageria passar a guardar as conversas, elas aparecem aqui."
    return "Não foi possível consultar as conversas agora. Tente novamente em alguns instantes."


def ultimo_recado(cliente, site_id, conversas):
    """Quando a lista não traz o texto do último recado, busca um por conversa.

    A lista da mensageria não traz o recado (`ultima_mensagem`) hoje; por isso
    a busca é limitada: no máximo `RECADOS_POR_PAGINA` por página, e para no
    primeiro tropeço. A lista abre mesmo sem os recados."""
    buscas = 0
    for conversa in conversas:
        if conversa["recado"] is not None or not conversa.get("ultima"):
            continue
        if buscas >= RECADOS_POR_PAGINA:
            return
        buscas += 1
        estado, dados = cliente.mensagens(site_id, conversa["id"], limite=1)
        if estado != OK:
            return
        if dados["mensagens"]:
            conversa["recado"] = preparar_mensagem(dados["mensagens"][-1])


@require_GET
def crm_conversas(request):
    filtro = request.GET.get("estado", "")
    if filtro not in dict(FILTROS):
        filtro = ""
    canal = request.GET.get("canal", "")
    if canal not in CANAIS:
        canal = ""
    try:
        pagina = min(10000, max(1, int(request.GET.get("pagina", 1))))
    except ValueError:
        pagina = 1
    contexto = {"admin": request.admin, "filtros": FILTROS, "filtro": filtro, "canal": canal, "canais": CANAIS, "conversas": [], "erro": "", "aviso": ""}
    site_id = site_do_pedido(request)
    if not site_id:
        contexto["erro"] = "Não consegui identificar este site. Tente novamente em alguns instantes."
        return render(request, "admin/crm_conversas.html", contexto, status=503)
    params = {"canal": canal, "pagina": pagina, "por_pagina": 100 if filtro == "aguardando" else 50}
    if filtro in ("agente", "pessoa", "encerrada"):
        params["estado"] = filtro
    elif filtro == "ambigua":
        params["ligacao"] = "ambigua"
    cliente = ConversasClient()
    estado, dados = cliente.listar(site_id, **params)
    if estado == INDISPONIVEL:
        contexto["aviso"] = erro_da_fonte(estado)
        return render(request, "admin/crm_conversas.html", contexto)
    if estado != OK:
        contexto["erro"] = erro_da_fonte(estado)
        return render(request, "admin/crm_conversas.html", contexto, status=503)
    conversas = [preparar_conversa(c) for c in dados["itens"] if isinstance(c, dict) and c.get("id")]
    if filtro == "aguardando":
        conversas = [c for c in conversas if c["aguardando"]]
    if filtro != "aguardando":
        # Neste filtro a página traz até 100 conversas: nenhuma busca extra.
        ultimo_recado(cliente, site_id, conversas)
    contexto["conversas"] = conversas
    contexto["total"] = dados.get("total")
    parametros = {k: v for k, v in (("estado", filtro), ("canal", canal)) if v}
    # Página filtrada que veio vazia não leva a "mais conversas": seria andar por páginas sem nada.
    sem_nada_a_mostrar = filtro == "aguardando" and not conversas
    contexto["proxima"] = "?" + urlencode(dict(parametros, pagina=pagina + 1)) if dados.get("tem_mais") and not sem_nada_a_mostrar else ""
    contexto["anterior"] = "?" + urlencode(dict(parametros, pagina=pagina - 1)) if pagina > 1 else ""
    return render(request, "admin/crm_conversas.html", contexto)


def oportunidade_do_lead(lead_id):
    """Link para a oportunidade aberta do lead no CRM, se der para saber."""
    if not lead_id:
        return ""
    estado, dados = CRMClient().quadro(lead_id=str(lead_id), situacao="aberta", por_pagina=5)
    if estado != CRMClient.OK:
        return ""
    for item in dados["itens"]:
        if not isinstance(item, dict) or item.get("situacao", "aberta") != "aberta":
            continue
        if item.get("id") and str(item.get("lead_id", lead_id)) == str(lead_id):
            try:
                return reverse("crm_oportunidade", args=[uuid.UUID(str(item["id"]))])
            except (ValueError, NoReverseMatch):
                return ""
    return ""


def nome_do_lead(lead_id):
    try:
        uuid.UUID(str(lead_id))
    except (ValueError, TypeError):
        return ""
    estado, ficha = LeadsClient().ficha(lead_id)
    if estado != LeadsClient.OK:
        return ""
    return (ficha.get("nome") or "").strip()


def quem_atende(request, assumida_por):
    """Como a tela chama quem assumiu a conversa: "você", o nome da pessoa da
    equipe, ou "outra pessoa da equipe". Nunca o identificador cru."""
    if not assumida_por:
        return ""
    admin = request.admin or {}
    meus = {str(admin.get("id") or ""), str(admin.get("email") or "")} - {""}
    if str(assumida_por) in meus or str(assumida_por).lower() in {m.lower() for m in meus}:
        return "você"
    chave = str(assumida_por)
    try:
        if chave.startswith("aparelho-") and chave[9:].isdigit():
            aparelho = AparelhoDaEquipe.objects.select_related("membro").filter(pk=int(chave[9:])).first()
            if aparelho:
                return aparelho.membro.nome
        elif "@" in chave:
            membro = MembroDaEquipe.objects.filter(email=chave.strip().lower()).first()
            if membro:
                return membro.nome
    except (DatabaseError, ValueError):
        pass
    return "outra pessoa da equipe"


def contexto_da_conversa(request, site_id, conversa_id, antes_de=""):
    estado, dados = ConversasClient().mensagens(site_id, conversa_id, antes_de=antes_de)
    if estado == NAO_EXISTE:
        raise Http404("Conversa não encontrada")
    if estado != OK:
        return {"admin": request.admin, "erro": erro_da_fonte(estado)}, 503
    conversa = preparar_conversa(dados["conversa"])
    if str(conversa.get("id")) != str(conversa_id):
        return {"admin": request.admin, "erro": erro_da_fonte(NAO_RESPONDEU)}, 503
    lead_id = None if conversa.get("ambigua") else conversa.get("lead_id")
    mensagens = [preparar_mensagem(m) for m in dados["mensagens"] if isinstance(m, dict)]
    anteriores = ""
    if len(mensagens) >= MENSAGENS_POR_PAGINA:
        # A página veio cheia: pode haver mais antigas. O ponto de corte é a mais velha daqui.
        datadas = [m for m in mensagens if m["momento"] and isinstance(m.get("ocorrida_em"), str)]
        if datadas:
            anteriores = "?" + urlencode({"antes_de": min(datadas, key=lambda m: m["momento"])["ocorrida_em"]})
    return {
        "admin": request.admin, "erro": "", "recado": "",
        "conversa": conversa,
        "quem_atende": quem_atende(request, conversa.get("assumida_por")) if conversa.get("estado") == "pessoa" else "",
        "mensagens": mensagens,
        "anteriores": anteriores,
        "antes_de": antes_de,
        "nome": nome_do_lead(lead_id) if lead_id else "",
        "oportunidade": oportunidade_do_lead(lead_id),
        "whatsapp": conversa.get("canal") == "whatsapp",
        "referencia": str(uuid.uuid4()),
    }, 200


def registrar(request, conversa_id, gesto, estado):
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")
    Registro.objects.create(
        quem_email=request.admin.get("email", ""), quem_id=autor[:64], acao=Registro.EDITAR,
        alvo=str(conversa_id), detalhe="Conversa: " + gesto,
        desfecho=Registro.OK if estado == OK else Registro.RECUSADO_PELA_CELULA if estado in (RECUSADO, NAO_EXISTE) else Registro.NAO_RESPONDEU,
    )


def devolver_se_assumi(request, cliente, site_id, conversa_id, assumi_agora):
    """Se foi ESTE pedido que assumiu a conversa e nada saiu, ela volta ao agente
    sozinha: a pessoa não fica dona de uma conversa em que não falou nada."""
    if not assumi_agora:
        return ""
    estado, _ = cliente.gesto(conversa_id, "devolver", {"site_id": site_id})
    registrar(request, conversa_id, "devolver (nada foi enviado)", estado)
    if estado == OK:
        return CONTINUA_COM_O_AGENTE
    return " Nada foi enviado, mas não conseguimos devolver a conversa ao agente: use o botão \"Devolver ao agente\"."


def responder(request, cliente, site_id, conversa_id, autor):
    """Devolve (estado, texto). `OK` é enviada ou repetida; `INCERTO` é enviada
    sem confirmação de entrega (ou sem resposta a tempo): o texto fica no
    formulário e a conversa fica com a pessoa."""
    texto = request.POST.get("texto", "").strip()
    modelo = request.POST.get("modelo", "").strip()
    referencia = request.POST.get("referencia", "").strip()
    try:
        referencia = str(uuid.UUID(referencia))
    except ValueError:
        return None, "Reabra a conversa antes de responder."
    if not texto and not modelo:
        return None, "Escreva a resposta antes de enviar."
    estado, atual = cliente.mensagens(site_id, conversa_id, limite=1)
    if estado != OK:
        return estado, "Não conseguimos consultar a conversa. Nada foi enviado."
    assumi_agora = False
    if atual["conversa"].get("estado") != "pessoa":
        estado, _ = cliente.gesto(conversa_id, "assumir", {"site_id": site_id, "pessoa_id": autor})
        registrar(request, conversa_id, "assumir", estado)
        if estado != OK:
            return estado, "Não conseguimos assumir a conversa, então nada foi enviado. Tente novamente."
        assumi_agora = True
    corpo = {"site_id": site_id, "texto": texto, "chave_idempotencia": "painel:" + referencia, "autor": "pessoa", "autor_id": autor}
    if modelo:
        corpo["modelo"] = {"nome": modelo[:200], "idioma": "pt_BR", "componentes": []}
    estado, resultado = cliente.gesto(conversa_id, "mensagens", corpo)
    desfecho = resultado.get("resultado") if estado == OK else None
    registrar(request, conversa_id, "responder" + (f" ({desfecho})" if desfecho else ""), RECUSADO if desfecho and desfecho not in RESULTADOS else estado)
    if estado == TEMPO_ESGOTADO:
        return INCERTO, PODE_TER_SAIDO
    if estado == RECUSADO:
        return estado, "A mensageria recusou o envio" + (f": {resultado}" if resultado else ".") + devolver_se_assumi(request, cliente, site_id, conversa_id, assumi_agora)
    if estado != OK:
        return estado, "Não conseguimos confirmar o envio. Reabra a conversa e confira antes de repetir."
    if desfecho == "enviada":
        saida = resultado.get("mensagem") if isinstance(resultado.get("mensagem"), dict) else {}
        if saida.get("estado_envio") in ENTREGA_CONFIRMADA:
            return OK, RESULTADOS["enviada"]
        return INCERTO, NAO_CONFIRMADA
    if desfecho in RESULTADOS:
        return OK, RESULTADOS[desfecho]
    if desfecho in RECUSAS:
        return RECUSADO, RECUSAS[desfecho] + devolver_se_assumi(request, cliente, site_id, conversa_id, assumi_agora)
    detalhe = resultado.get("detalhe") or (resultado.get("mensagem") or {}).get("erro") or ""
    frase = "O envio falhou" + (f": {detalhe}" if detalhe else ".")
    if desfecho == "falhou":
        volta = devolver_se_assumi(request, cliente, site_id, conversa_id, assumi_agora)
        if volta:
            return RECUSADO, frase + volta
    return RECUSADO, frase + " Confira a conversa antes de tentar de novo."


def mostrar_conversa(request, site_id, conversa_id, **marcas):
    """Mostra a conversa de novo depois de um gesto, com o que a pessoa escreveu."""
    contexto, status = contexto_da_conversa(request, site_id, conversa_id)
    contexto.update(marcas)
    contexto["formulario"] = request.POST
    try:
        contexto["referencia"] = str(uuid.UUID(request.POST.get("referencia", "")))
    except ValueError:
        pass
    return contexto, status


@require_http_methods(["GET", "POST"])
def crm_conversa(request, conversa_id):
    site_id = site_do_pedido(request)
    if not site_id:
        return render(request, "admin/crm_conversa.html", {"admin": request.admin, "erro": "Não consegui identificar este site. Tente novamente em alguns instantes."}, status=503)
    if request.method == "GET":
        antes_de = request.GET.get("antes_de", "").strip()[:64]
        if antes_de and instante(antes_de) is None:
            antes_de = ""
        contexto, status = contexto_da_conversa(request, site_id, conversa_id, antes_de=antes_de)
        contexto["recado"] = {"1": "Conversa assumida. O agente não responde enquanto você atende.", "2": "Conversa devolvida ao agente.", "3": "Mensagem enviada."}.get(request.GET.get("feito", ""), "")
        return render(request, "admin/crm_conversa.html", contexto, status=status)
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")[:100]
    cliente = ConversasClient()
    gesto = request.POST.get("gesto", "")
    if gesto in ("assumir", "devolver"):
        corpo = {"site_id": site_id, "pessoa_id": autor} if gesto == "assumir" else {"site_id": site_id}
        estado, detalhe = cliente.gesto(conversa_id, gesto, corpo)
        registrar(request, conversa_id, gesto, estado)
        if estado == OK:
            return HttpResponseRedirect(reverse("crm_conversa", args=[conversa_id]) + ("?feito=1" if gesto == "assumir" else "?feito=2"))
        if estado == NAO_EXISTE:
            raise Http404("Conversa não encontrada")
        erro = (detalhe or "A mensageria recusou o pedido.") if estado == RECUSADO else "Não conseguimos confirmar a mudança. Reabra a conversa antes de tentar de novo."
    elif gesto == "responder":
        estado, erro = responder(request, cliente, site_id, conversa_id, autor)
        if estado == NAO_EXISTE:
            raise Http404("Conversa não encontrada")
        if estado == OK:
            if erro == RESULTADOS["enviada"]:
                return HttpResponseRedirect(reverse("crm_conversa", args=[conversa_id]) + "?feito=3")
            contexto, status = contexto_da_conversa(request, site_id, conversa_id)
            contexto["recado"] = erro
            return render(request, "admin/crm_conversa.html", contexto, status=status)
        if estado == INCERTO:
            # Saiu, ou pode ter saído: aviso sem alarme, e o texto continua no formulário.
            contexto, status = mostrar_conversa(request, site_id, conversa_id, recado=erro)
            return render(request, "admin/crm_conversa.html", contexto, status=status)
    else:
        estado, erro = RECUSADO, "Este pedido não foi reconhecido."
    contexto, status = mostrar_conversa(request, site_id, conversa_id)
    contexto["erro"] = contexto.get("erro") or erro
    if status == 200:
        status = 422 if estado in (RECUSADO, None) else 503
    return render(request, "admin/crm_conversa.html", contexto, status=status)
