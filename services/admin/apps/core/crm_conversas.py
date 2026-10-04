"""Caixa de conversas do CRM: o que o lead escreveu e o que a casa respondeu.

As conversas são dado da célula `mensageria` (WhatsApp e e-mail nos dois
sentidos). O painel só pergunta pela API dela, sempre com o site do domínio
pelo qual a tela foi aberta: conversa de outro site nunca aparece aqui.

Gestos da pessoa da equipe: assumir (o agente para de responder), devolver ao
agente e responder como pessoa. Responder assume a conversa antes de enviar,
para o agente não falar por cima de quem está atendendo; se o envio não sai no
mesmo pedido, a conversa volta sozinha para o agente.
"""
import logging
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

logger = logging.getLogger(__name__)

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
    ("sem_origem", "Sem origem no quiz"),
    ("encerrada", "Encerradas"),
)
CANAIS = {"whatsapp": "WhatsApp", "email": "E-mail"}
ESTADOS = {"agente": "Com o agente", "pessoa": "Com uma pessoa", "encerrada": "Encerrada"}
ENVIOS = {
    "recebida": "Recebida", "pendente": "Enviando", "aceito": "Aceita pelo provedor",
    "enviado": "Enviada", "entregue": "Entregue", "lido": "Lida", "falhou": "Falhou",
    "reservado": "Reservada para envio", "desconhecido": "Resultado incerto — confira antes de repetir",
}
# Só estes estados dizem que a mensagem de fato saiu. "aceito" é o provedor ter
# recebido a mensagem para entregar: é o estado normal logo depois de um envio
# por WhatsApp (a confirmação da entrega chega depois, pelo retorno do provedor).
SAIU = ("aceito", "enviado", "entregue", "lido")
# Por que a conversa não tem oportunidade ligada (a mensageria diz; aqui só vira português).
ETIQUETAS = {
    "sem_origem_quiz": "Sem origem no quiz",
    "telefone_ambiguo": "Telefone de mais de um contato",
    "equipe_confirma": "A equipe confirma",
}
AUTORES = {"lead": "Contato", "agente": "Agente", "pessoa": "Equipe", "sistema": "Sistema"}
MIDIAS = {"audio": "Áudio", "imagem": "Imagem", "video": "Vídeo", "documento": "Documento"}
POR_PAGINA = 50
VARREDURA_MAXIMA = 10  # páginas de 100 conversas lidas por vez no filtro "aguardando"
RECADOS_POR_PAGINA = 10  # buscas do último recado por tela, quando a lista não traz o texto
CONFERENCIAS_MAXIMAS = RECADOS_POR_PAGINA  # as mesmas buscas, no filtro "aguardando"
MENSAGENS_POR_PAGINA = 100
MENSAGENS_DA_RECUSA = {
    "fora_da_janela": "Não enviada: já passaram 24 horas desde a última mensagem do contato no WhatsApp. Agora só um modelo aprovado pode ser enviado.",
    "descadastrado": "Não enviada: o contato pediu para não receber mais mensagens neste canal. Só dá para responder quando ele escrever de novo.",
    "conversa_com_pessoa": "Não enviada: outra pessoa da equipe está atendendo esta conversa.",
    "sem_consentimento": "Esta pessoa ainda não autorizou receber mensagens por WhatsApp.",
    "fora_do_horario": "Não enviada: agora está fora do horário permitido para enviar mensagens. Tente de novo dentro do horário.",
    "limite_diario": "Não enviada: o limite de mensagens do dia já foi atingido. Tente de novo amanhã.",
    "limite_do_dia": "Não enviada: o limite de mensagens do dia já foi atingido. Tente de novo amanhã.",
}
RESULTADOS = {
    "enviada": "Mensagem enviada.",
    "repetida": "Esta resposta já tinha sido enviada. Não enviamos de novo.",
}
NAO_CONFIRMADA = "Enviada, mas a entrega não foi confirmada; veja o histórico antes de reenviar."
PODE_TER_SAIDO = "O envio pode ter saído: o serviço de mensagens demorou para responder. Confira o histórico antes de reenviar."
CONTINUA_COM_O_AGENTE = " Nada foi enviado; a conversa continua com o agente."
CONTINUA_ENCERRADA = " Nada foi enviado; a conversa continua encerrada."
NOME_DO_AGENTE = "Assistente da equipe"


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
    """O contato falou por último e ninguém conseguiu responder ainda.

    Com o último recado em mãos vale ele: resposta que falhou no envio não
    responde ninguém, mas já atualizou a hora da última mensagem da conversa.
    Quem pediu para parar não espera resposta, a não ser que tenha escrito
    de novo depois do PARAR: a mensageria libera uma resposta a cada fala nova
    e só uma pessoa pode decidir o que dizer."""
    entrada = conversa.get("ultima_entrada")
    recado = conversa.get("recado")
    if conversa.get("estado") == "encerrada" or not entrada:
        return False
    if conversa.get("descadastrado"):
        return bool(recado and recado.get("direcao") == "entrada" and not recado.get("descadastro"))
    if (recado and recado.get("direcao") == "saida" and recado.get("autor") == "sistema"
            and str(recado.get("autor_id") or "").startswith("orientacao:")
            and conversa.get("etiqueta") in ("sem_origem_quiz", "equipe_confirma")):
        # A orientação e a confirmação automáticas não são resposta da equipe:
        # quem está sem origem ou espera confirmação ainda precisa de uma pessoa.
        return True
    if recado and recado.get("direcao") in ("entrada", "saida"):
        return recado["direcao"] == "entrada" or recado.get("estado_envio") == "falhou"
    ultima = conversa.get("ultima")
    return bool(ultima and entrada >= ultima)


def preparar_conversa(item):
    item = dict(item)
    item["recado_na_lista"] = "ultima_mensagem" in item  # a mensageria atual sempre manda (ou manda None: sem mensagem)
    item["canal_nome"] = CANAIS.get(item.get("canal"), item.get("canal") or "")
    item["estado_nome"] = ESTADOS.get(item.get("estado"), item.get("estado") or "")
    item["ultima"] = instante(item.get("ultima_mensagem_em"))
    item["ultima_entrada"] = instante(item.get("ultima_entrada_em"))
    item["janela_ate"] = instante(item.get("janela_aberta_ate"))
    item["ficha"] = "" if item.get("ambigua") else ficha_do_lead(item.get("lead_id"))
    item["etiqueta_nome"] = ETIQUETAS.get(item.get("etiqueta") or "", "")
    orientacao = item.get("orientacao") if isinstance(item.get("orientacao"), dict) else None
    item["orientacao_em"] = instante(orientacao.get("enviada_em")) if orientacao else None
    recado = item.get("ultima_mensagem") if isinstance(item.get("ultima_mensagem"), dict) else None
    item["recado"] = preparar_mensagem(recado) if recado else None
    item["aguardando"] = aguardando(item)
    return item


def preparar_mensagem(item):
    item = dict(item)
    item["momento"] = instante(item.get("ocorrida_em"))
    item["autor_nome"] = AUTORES.get(item.get("autor"), item.get("autor") or "")
    item["orientacao"] = str(item.get("autor_id") or "").startswith("orientacao:")
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
    """Só para a mensageria antiga: a lista dela não traz o último recado.

    A mensageria atual manda `ultima_mensagem` de todas as conversas da página
    na própria lista e aqui nada é buscado. Contra a antiga, a busca é limitada:
    no máximo `RECADOS_POR_PAGINA` por chamada, e para no primeiro tropeço. A
    lista abre mesmo sem os recados."""
    buscas = 0
    for conversa in conversas:
        if conversa["recado"] is not None or not conversa.get("ultima") or conversa["recado_na_lista"]:
            continue
        if buscas >= RECADOS_POR_PAGINA:
            return
        buscas += 1
        estado, dados = cliente.mensagens(site_id, conversa["id"], limite=1)
        if estado != OK:
            return
        if dados["mensagens"] and isinstance(dados["mensagens"][-1], dict):
            conversa["recado"] = preparar_mensagem(dados["mensagens"][-1])
            conversa["aguardando"] = aguardando(conversa)


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
    params = {"canal": canal}
    if filtro in ("agente", "pessoa", "encerrada"):
        params["estado"] = filtro
    # Sem `ligacao` a mensageria só devolve conversas ligadas a um lead e quem
    # escreve de um número ambíguo ou desconhecido nunca apareceria na lista.
    params["ligacao"] = {"ambigua": "ambigua", "sem_origem": "desconhecida"}.get(filtro, "todas")
    cliente = ConversasClient()
    if filtro == "aguardando":
        estado, conversas, mais, completo = varrer_aguardando(cliente, site_id, pagina, params)
        total = len(conversas) if estado == OK else None
        if estado == OK:
            inicio = (pagina - 1) * POR_PAGINA
            mais = len(conversas) > inicio + POR_PAGINA
            conversas = conversas[inicio:inicio + POR_PAGINA]
            contexto["parcial"] = not completo
    else:
        estado, dados = cliente.listar(site_id, pagina=pagina, por_pagina=POR_PAGINA, **params)
        if estado == OK:
            conversas = [preparar_conversa(c) for c in dados["itens"] if isinstance(c, dict) and c.get("id")]
            total, mais = dados.get("total"), bool(dados.get("tem_mais"))
    if estado == INDISPONIVEL:
        contexto["aviso"] = erro_da_fonte(estado)
        return render(request, "admin/crm_conversas.html", contexto)
    if estado != OK:
        contexto["erro"] = erro_da_fonte(estado)
        return render(request, "admin/crm_conversas.html", contexto, status=503)
    if filtro != "aguardando":
        # No filtro "aguardando" a varredura já conferiu o que podia (e dentro do limite).
        ultimo_recado(cliente, site_id, conversas)
    contexto["conversas"] = conversas
    contexto["total"] = total
    parametros = {k: v for k, v in (("estado", filtro), ("canal", canal)) if v}
    contexto["proxima"] = "?" + urlencode(dict(parametros, pagina=pagina + 1)) if mais else ""
    contexto["anterior"] = "?" + urlencode(dict(parametros, pagina=pagina - 1)) if pagina > 1 else ""
    return render(request, "admin/crm_conversas.html", contexto)


def varrer_aguardando(cliente, site_id, pagina, params):
    """Junta quem espera resposta lendo as páginas da mensageria até achar o bastante.

    A mensageria não filtra por quem falou por último; filtrar só a página que
    ela devolve deixaria as páginas do painel quase vazias. Por isso o painel
    lê as páginas em ordem (da mais recente) e guarda só as que esperam.
    Devolve (estado, conversas, tem_mais_na_mensageria, varredura_completa)."""
    achadas, conferidas, mais = [], 0, False
    necessarias = pagina * POR_PAGINA + 1  # uma a mais, para saber se há próxima página
    for numero in range(1, VARREDURA_MAXIMA + 1):
        estado, dados = cliente.listar(site_id, pagina=numero, por_pagina=100, **params)
        if estado != OK:
            if numero == 1:
                return estado, [], False, False
            return OK, achadas, True, False
        mais = bool(dados.get("tem_mais"))
        for bruta in dados["itens"]:
            if not isinstance(bruta, dict) or not bruta.get("id"):
                continue
            conversa = preparar_conversa(bruta)
            if conversa["estado"] == "encerrada" or not conversa["ultima_entrada"]:
                continue
            if (not conversa["aguardando"] and conversa["recado"] is None and not conversa["recado_na_lista"]
                    and conferidas < CONFERENCIAS_MAXIMAS):
                # Pela hora parece respondida, mas a resposta pode ter falhado: confere o último recado.
                conferidas += 1
                ultimo_recado(cliente, site_id, [conversa])
                if conversa["recado"] is None:
                    conferidas = CONFERENCIAS_MAXIMAS  # a leitura tropeçou: não insiste
            if conversa["aguardando"]:
                achadas.append(conversa)
        if not mais:
            return OK, achadas, False, True
        if len(achadas) >= necessarias:
            return OK, achadas, True, True
    return OK, achadas, True, False


def oportunidades_abertas_do_lead(lead_id):
    """Ids das oportunidades abertas do lead no CRM. `None` quando não deu para saber."""
    if not lead_id:
        return []
    estado, dados = CRMClient().quadro(lead_id=str(lead_id), situacao="aberta", por_pagina=5)
    if estado != CRMClient.OK:
        return None
    achadas = []
    for item in dados["itens"]:
        if not isinstance(item, dict) or item.get("situacao", "aberta") != "aberta":
            continue
        if item.get("id") and str(item.get("lead_id", lead_id)) == str(lead_id):
            try:
                achadas.append(str(uuid.UUID(str(item["id"]))))
            except ValueError:
                continue
    return achadas


def oportunidade_do_lead(lead_id):
    """Link para a oportunidade aberta do lead no CRM, se der para saber."""
    achadas = oportunidades_abertas_do_lead(lead_id)
    if not achadas:
        return ""
    try:
        return reverse("crm_oportunidade", args=[uuid.UUID(achadas[0])])
    except (ValueError, NoReverseMatch):
        return ""


def nome_de_quem_atende(request):
    """O nome que o cartão do CRM mostra para quem atendeu: o da equipe, ou o que a sessão traz."""
    admin = request.admin or {}
    email = str(admin.get("email") or "").strip().lower()
    if email:
        try:
            membro = MembroDaEquipe.objects.filter(email=email).first()
        except DatabaseError:
            membro = None
        if membro and membro.nome.strip():
            return membro.nome.strip()
    return str(admin.get("nome") or admin.get("email") or "Equipe").strip()[:200]


def acompanhar_no_crm(request, cliente, site_id, conversa_id, gesto, referencia, campos, lead_id=None):
    """Depois de um gesto da pessoa na conversa, o cartão da oportunidade acompanha:
    quem atende, o último contato e se ainda espera resposta.

    Melhor esforço: o gesto já aconteceu na mensageria, e se o CRM não responder
    a conversa não volta atrás. Só fica o aviso no registro do servidor. A chave
    é a do gesto, então repetir o mesmo pedido não grava de novo."""
    falhou = False
    try:
        if lead_id is None:
            estado, dados = cliente.mensagens(site_id, conversa_id, limite=1)
            if estado != OK:
                raise RuntimeError("não deu para ler a conversa")
            lead_id = None if dados["conversa"].get("ambigua") else dados["conversa"].get("lead_id")
        oportunidades = oportunidades_abertas_do_lead(lead_id) if lead_id else []
        if oportunidades is None:
            falhou = True
        autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")[:100]
        for oportunidade in oportunidades or []:
            estado, _ = CRMClient().alterar(oportunidade, "PATCH", "/acompanhamento", {
                **campos, "autor_id": autor, "chave_idempotencia": f"painel:{gesto}:{referencia}",
            })
            if estado != CRMClient.OK:
                falhou = True
    except Exception:  # o gesto já valeu: nada aqui pode derrubar a resposta da tela
        logger.exception("caixa de conversas: erro ao atualizar o acompanhamento da conversa %s", conversa_id)
        return
    if falhou:
        logger.warning("caixa de conversas: o gesto %s da conversa %s foi feito, mas o CRM não registrou o acompanhamento",
                       gesto, conversa_id)


def pessoa_atende(request):
    return {"tipo": "pessoa", "nome": nome_de_quem_atende(request)}


def referencia_do_pedido(request):
    try:
        return str(uuid.UUID(request.POST.get("referencia", "").strip()))
    except ValueError:
        return str(uuid.uuid4())


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
    meus = {str(admin.get("id") or "").lower(), str(admin.get("email") or "").lower()} - {""}
    chave = str(assumida_por)
    if chave.lower() in meus:
        return "você"
    try:
        if chave.startswith("aparelho-") and chave[9:].isascii() and chave[9:].isdigit():
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


def cursor_valido(texto):
    """O `antes_de` da página anterior: id de mensagem (preciso) ou uma data."""
    if not isinstance(texto, str) or not texto.strip() or len(texto) > 64:
        return False
    try:
        uuid.UUID(texto.strip())
        return True
    except ValueError:
        return instante(texto.strip()) is not None


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
        # Com o id da mais antiga, mensagens do mesmo instante não se perdem na virada da página.
        cursor = dados.get("proxima_antes_de")
        if not cursor_valido(cursor):
            datadas = [m for m in mensagens if m["momento"] and isinstance(m.get("ocorrida_em"), str)]
            cursor = min(datadas, key=lambda m: m["momento"])["ocorrida_em"] if datadas else ""
        if cursor:
            anteriores = "?" + urlencode({"antes_de": cursor})
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


def devolver_se_assumi(request, cliente, site_id, conversa_id, assumiu, era_encerrada=False):
    """Se foi ESTE pedido que assumiu a conversa e nada saiu, ela volta ao que era
    sozinha: ao agente, ou encerrada se estava encerrada. A pessoa não fica dona de
    uma conversa em que não falou nada, e uma conversa encerrada não é reaberta
    (nem devolvida ao robô) por um envio que não saiu.
    Devolve a frase que diz isso na tela."""
    if not assumiu:
        return ""
    if era_encerrada:
        encerrada, _ = cliente.gesto(conversa_id, "encerrar", {"site_id": site_id})
        registrar(request, conversa_id, "encerrar (envio recusado)", encerrada)
        if encerrada == OK:
            return CONTINUA_ENCERRADA
        return " Nada foi enviado, mas não conseguimos deixar a conversa encerrada: ela ficou com você. Use o botão \"Devolver ao agente\" se não quiser atendê-la."
    devolvido, _ = cliente.gesto(conversa_id, "devolver", {"site_id": site_id})
    registrar(request, conversa_id, "devolver (envio recusado)", devolvido)
    if devolvido == OK:
        return CONTINUA_COM_O_AGENTE
    return " Nada foi enviado, mas não conseguimos devolver a conversa ao agente: use o botão \"Devolver ao agente\"."


def responder(request, cliente, site_id, conversa_id, autor, lido=None):
    """Devolve (estado, texto). `OK` é enviada ou repetida; `INCERTO` é enviada
    sem confirmação de entrega (ou sem resposta a tempo): o texto fica no
    formulário e a conversa fica com a pessoa. Em `lido` (se vier) fica o
    lead da conversa, para o CRM acompanhar."""
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
    conversa = atual["conversa"]
    if lido is not None:
        lido["lead_id"] = None if conversa.get("ambigua") else conversa.get("lead_id")
    if conversa.get("canal") == "whatsapp" and conversa.get("janela_aberta") is False and not modelo:
        # A mensageria vai recusar: não assume a conversa para nada e o agente continua atendendo.
        return RECUSADO, MENSAGENS_DA_RECUSA["fora_da_janela"] + (CONTINUA_COM_O_AGENTE if conversa.get("estado") == "agente" else "")
    assumiu = False
    if conversa.get("estado") != "pessoa":
        estado, _ = cliente.gesto(conversa_id, "assumir", {"site_id": site_id, "pessoa_id": autor})
        registrar(request, conversa_id, "assumir", estado)
        if estado != OK:
            return estado, "Não conseguimos assumir a conversa, então nada foi enviado. Tente novamente."
        assumiu = True
    corpo = {"site_id": site_id, "texto": texto, "chave_idempotencia": "painel:" + referencia, "autor": "pessoa", "autor_id": autor}
    if modelo:
        corpo["modelo"] = {"nome": modelo[:200], "idioma": "pt_BR", "componentes": []}
    estado, resultado = cliente.gesto(conversa_id, "mensagens", corpo)
    desfecho = resultado.get("resultado") if estado == OK else None
    registrar(request, conversa_id, "responder" + (f" ({desfecho})" if desfecho else ""), RECUSADO if desfecho and desfecho not in RESULTADOS else estado)
    if estado == TEMPO_ESGOTADO:
        # Saiu e não voltou: pode ter ido. A conversa fica com a pessoa e o texto, no formulário.
        return INCERTO, PODE_TER_SAIDO
    # Só devolve ao agente quando a mensageria diz que NADA saiu.
    nao_saiu = estado == RECUSADO or desfecho == "falhou" or (desfecho in MENSAGENS_DA_RECUSA and desfecho != "conversa_com_pessoa")
    volta = devolver_se_assumi(request, cliente, site_id, conversa_id, assumiu and nao_saiu,
                               era_encerrada=conversa.get("estado") == "encerrada")
    if estado == RECUSADO:
        return estado, "A mensageria recusou o envio" + (f": {resultado}" if resultado else ".") + volta
    if estado != OK:
        return estado, "Não conseguimos confirmar o envio. Reabra a conversa e confira antes de repetir."
    if desfecho in RESULTADOS:
        # "enviada" e "repetida" só valem como enviadas se a mensagem saiu de fato.
        saida = resultado.get("mensagem") if isinstance(resultado.get("mensagem"), dict) else {}
        if saida.get("estado_envio") in SAIU:
            return OK, RESULTADOS[desfecho]
        return INCERTO, NAO_CONFIRMADA
    if desfecho in MENSAGENS_DA_RECUSA:
        return RECUSADO, MENSAGENS_DA_RECUSA[desfecho] + volta
    detalhe = resultado.get("detalhe") or (resultado.get("mensagem") or {}).get("erro") or ""
    frase = "O envio falhou" + (f": {detalhe}" if detalhe else ".")
    return RECUSADO, frase + (volta or " Confira a conversa antes de tentar de novo.")


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
        if not cursor_valido(antes_de):
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
            acompanhar_no_crm(
                request, cliente, site_id, conversa_id, gesto, referencia_do_pedido(request),
                {"atendido_por": pessoa_atende(request) if gesto == "assumir" else {"tipo": "agente", "nome": NOME_DO_AGENTE}},
            )
            return HttpResponseRedirect(reverse("crm_conversa", args=[conversa_id]) + ("?feito=1" if gesto == "assumir" else "?feito=2"))
        if estado == NAO_EXISTE:
            raise Http404("Conversa não encontrada")
        erro = (detalhe or "A mensageria recusou o pedido.") if estado == RECUSADO else "Não conseguimos confirmar a mudança. Reabra a conversa antes de tentar de novo."
    elif gesto == "responder":
        lido = {}
        estado, erro = responder(request, cliente, site_id, conversa_id, autor, lido)
        if estado == NAO_EXISTE:
            raise Http404("Conversa não encontrada")
        if estado in (OK, INCERTO):
            # Saiu, ou pode ter saído: a conversa está com a pessoa. Só o que saiu de fato
            # conta como contato e tira o "aguardando resposta" do cartão.
            campos = {"atendido_por": pessoa_atende(request)}
            if estado == OK:
                campos.update(ultimo_contato_em=timezone.now().isoformat(), aguardando_resposta=False)
            acompanhar_no_crm(request, cliente, site_id, conversa_id, "responder", referencia_do_pedido(request),
                              campos, lead_id=lido.get("lead_id") or "")
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
