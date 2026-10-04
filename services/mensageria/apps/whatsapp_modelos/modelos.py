"""Modelos aprovados do WhatsApp oficial: sincronizar, preencher e enviar.

Uso pela abordagem e pelas jornadas:

    from apps.whatsapp_modelos.modelos import enviar_modelo
    envio = enviar_modelo(site_id=..., chave_idempotencia="abordagem:<oportunidade_ref>",
                          destinatario="+55 11 9...", modelo="primeiro_contato",
                          variaveis={"nome": "Ana", "quiz": "...", "oferta": "..."},
                          origem="abordagem", referencia="<oportunidade_ref>")

A mesma chave nunca gera duas mensagens. Resultado incerto (sem resposta da
Meta) fica `desconhecido` e não é repetido às cegas; recusa comprovada (4xx,
credencial ausente, dado faltando) fica `falhou` com `retomavel=True` e a mesma
chave pode tentar de novo.
"""
from __future__ import annotations

import re

from django.db import connection, transaction
from django.utils import timezone

from apps.whatsapp.service import mascarar_telefone, normalizar_telefone

from . import cloud
from .models import EnvioDeModelo, ModeloWhatsApp, RetornoDeModelo

# Os dados do lead que um modelo pode receber. A chave é o que a abordagem e as
# jornadas entregam em `variaveis`; o texto é o que a tela mostra.
VARIAVEIS_DO_LEAD = {
    "nome": "Nome do contato",
    "quiz": "Quiz respondido",
    "oferta": "Oferta indicada",
    "link": "Link de compra",
}

_APELIDOS = {
    "nome": "nome", "name": "nome", "first_name": "nome", "primeiro_nome": "nome",
    "customer_name": "nome", "cliente": "nome", "lead": "nome",
    "quiz": "quiz", "quiz_nome": "quiz", "nome_quiz": "quiz", "teste": "quiz",
    "oferta": "oferta", "offer": "oferta", "produto": "oferta", "curso": "oferta",
    "link": "link", "url": "link", "link_compra": "link",
}
_PADRAO_POSICIONAL = {"1": "nome", "2": "quiz", "3": "oferta"}

ESTADOS_DA_META = {
    "APPROVED": "aprovado", "PENDING": "pendente", "IN_APPEAL": "pendente",
    "REJECTED": "rejeitado", "PAUSED": "pausado", "FLAGGED": "pausado",
    "DISABLED": "desativado", "DELETED": "desativado", "ARCHIVED": "desativado",
    "PENDING_DELETION": "desativado", "LIMIT_EXCEEDED": "desativado",
}

ORDEM = {"reservado": 0, "desconhecido": 0, "aceito": 1, "enviado": 2, "entregue": 3, "lido": 4}
STATUS_DA_META = {"accepted": "aceito", "sent": "enviado", "delivered": "entregue",
                  "read": "lido", "played": "lido", "failed": "falhou"}

_PARAM = re.compile(r"\{\{\s*([A-Za-z0-9_]+)\s*\}\}")


# --------------------------------------------------------------------------- modelos
def _parametros(texto: str) -> list[str]:
    vistos: list[str] = []
    for achado in _PARAM.findall(texto or ""):
        if achado not in vistos:
            vistos.append(achado)
    return vistos


def ler_componentes(componentes: list, categoria: str = "") -> tuple[list[dict], bool, str]:
    """Devolve (variaveis, suportado, motivo) a partir dos componentes da Meta."""
    variaveis: list[dict] = []
    motivo = ""
    if str(categoria).upper() == "AUTHENTICATION":
        motivo = "modelo de autenticacao nao serve para primeiro contato"
    for comp in componentes if isinstance(componentes, list) else []:
        if not isinstance(comp, dict):
            continue
        tipo = str(comp.get("type") or "").upper()
        if tipo == "HEADER":
            formato = str(comp.get("format") or "TEXT").upper()
            if formato != "TEXT":
                motivo = motivo or "cabecalho com midia ainda nao e enviado automaticamente"
                continue
            for p in _parametros(comp.get("text", "")):
                variaveis.append({"chave": f"header:{p}", "componente": "header", "parametro": p})
        elif tipo == "BODY":
            for p in _parametros(comp.get("text", "")):
                variaveis.append({"chave": f"body:{p}", "componente": "body", "parametro": p})
        elif tipo == "BUTTONS":
            for indice, botao in enumerate(comp.get("buttons") or []):
                if not isinstance(botao, dict):
                    continue
                btipo = str(botao.get("type") or "").upper()
                if btipo == "URL" and _parametros(botao.get("url", "")):
                    variaveis.append({"chave": f"button.{indice}:1", "componente": f"button.{indice}",
                                      "parametro": "1"})
                elif btipo not in ("URL", "QUICK_REPLY", "PHONE_NUMBER"):
                    motivo = motivo or "botao deste tipo ainda nao e preenchido automaticamente"
    return variaveis, not motivo, motivo


def _mapa_padrao(variavel: dict) -> str:
    p = variavel["parametro"]
    if variavel["componente"].startswith("button."):
        return "link"
    if p.isdigit():
        return _PADRAO_POSICIONAL.get(p, "") if variavel["componente"] == "body" else (
            "nome" if p == "1" else "")
    return _APELIDOS.get(p.lower(), "")


def _corpo(componentes: list) -> str:
    for comp in componentes if isinstance(componentes, list) else []:
        if isinstance(comp, dict) and str(comp.get("type") or "").upper() == "BODY":
            return str(comp.get("text") or "")
    return ""


def sincronizar_modelos() -> dict:
    """Copia da Cloud API os modelos da conta. Nada é apagado; o que sumiu fica marcado."""
    c = cloud.credenciais()
    campos = "id,name,language,status,category,components,parameter_format,rejected_reason"
    vistos: set[int] = set()
    depois = ""
    agora = timezone.now()
    paginas = 0
    while True:
        params = {"fields": campos, "limit": "100"}
        if depois:
            params["after"] = depois
        resposta = cloud.pedir("GET", f"{c['conta']}/message_templates", params=params)
        dados = resposta.get("data")
        if not isinstance(dados, list):
            raise cloud.CloudSemResposta("meta respondeu formato invalido")
        for item in dados:
            if not isinstance(item, dict) or not item.get("name") or not item.get("language"):
                continue
            componentes = item.get("components") if isinstance(item.get("components"), list) else []
            variaveis, suportado, motivo = ler_componentes(componentes, item.get("category", ""))
            estado_cru = str(item.get("status") or "").upper()
            modelo, _ = ModeloWhatsApp.objects.get_or_create(
                conta=c["conta"], nome=str(item["name"])[:512], idioma=str(item["language"])[:20])
            anterior = modelo.mapeamento if isinstance(modelo.mapeamento, dict) else {}
            modelo.modelo_id = str(item.get("id") or "")[:64]
            modelo.categoria = str(item.get("category") or "")[:30]
            modelo.estado_no_provedor = estado_cru[:40]
            modelo.estado = ESTADOS_DA_META.get(estado_cru, "outro")
            modelo.formato_parametros = "named" if str(item.get("parameter_format") or "").upper() == "NAMED" else "positional"
            modelo.componentes = componentes
            modelo.corpo = _corpo(componentes)
            modelo.variaveis = variaveis
            modelo.mapeamento = {v["chave"]: anterior.get(v["chave"]) or _mapa_padrao(v) for v in variaveis}
            modelo.suportado = suportado
            rejeicao = str(item.get("rejected_reason") or "")
            modelo.motivo = (motivo or (rejeicao if rejeicao and rejeicao.upper() != "NONE" else ""))[:300]
            modelo.presente_no_provedor = True
            modelo.sincronizado_em = agora
            modelo.save()
            vistos.add(modelo.pk)
        paginas += 1
        cursores = (resposta.get("paging") or {}).get("cursors") or {}
        depois = cursores.get("after") if (resposta.get("paging") or {}).get("next") else ""
        if not depois or paginas >= 50:
            break
    sumidos = ModeloWhatsApp.objects.filter(conta=c["conta"]).exclude(pk__in=vistos).update(
        presente_no_provedor=False)
    return {"modelos": len(vistos), "sumidos": sumidos, "sincronizado_em": agora.isoformat()}


def atualizar_estado_de_modelo(valor: dict) -> bool:
    """Aplica `message_template_status_update` recebido pelo webhook da Meta."""
    if not isinstance(valor, dict):
        return False
    estado_cru = str(valor.get("event") or "").upper()
    modelo_id = str(valor.get("message_template_id") or "")
    filtro = ModeloWhatsApp.objects.filter(modelo_id=modelo_id) if modelo_id else None
    if not filtro or not filtro.exists():
        filtro = ModeloWhatsApp.objects.filter(nome=str(valor.get("message_template_name") or ""),
                                               idioma=str(valor.get("message_template_language") or ""))
    if not estado_cru or not filtro.exists():
        return False
    motivo = str(valor.get("reason") or "")
    filtro.update(estado=ESTADOS_DA_META.get(estado_cru, "outro"), estado_no_provedor=estado_cru[:40],
                  motivo=(motivo if motivo.upper() != "NONE" else "")[:300], atualizado_em=timezone.now())
    return True


def definir_mapeamento(modelo_id: int, mapeamento: dict) -> ModeloWhatsApp:
    modelo = ModeloWhatsApp.objects.get(pk=modelo_id)
    validas = {v["chave"] for v in modelo.variaveis}
    novo = dict(modelo.mapeamento or {})
    for chave, dado in (mapeamento or {}).items():
        if chave not in validas:
            raise ValueError(f"lugar desconhecido neste modelo: {chave}")
        if dado and dado not in VARIAVEIS_DO_LEAD:
            raise ValueError(f"dado desconhecido: {dado}")
        novo[chave] = dado or ""
    modelo.mapeamento = novo
    modelo.save(update_fields=["mapeamento", "atualizado_em"])
    return modelo


def faltando_no_mapeamento(modelo: ModeloWhatsApp) -> list[str]:
    return [v["chave"] for v in modelo.variaveis if not (modelo.mapeamento or {}).get(v["chave"])]


def escolher_modelo(nome: str, idioma: str = "") -> ModeloWhatsApp | None:
    conta = cloud.credenciais()["conta"]
    qs = ModeloWhatsApp.objects.filter(conta=conta, nome=nome, estado="aprovado", presente_no_provedor=True)
    if idioma:
        return qs.filter(idioma=idioma).first()
    return qs.filter(idioma="pt_BR").first() or qs.order_by("idioma").first()


# --------------------------------------------------------------------------- envio
def _texto(valor) -> str:
    # A Meta recusa parâmetro com quebra de linha, tabulação ou 4+ espaços seguidos.
    return re.sub(r"\s+", " ", str(valor or "")).strip()[:1000]


def montar_componentes(modelo: ModeloWhatsApp, variaveis: dict) -> list[dict]:
    """Preenche os lugares do modelo com os dados do lead, na ordem que a Meta espera."""
    mapa = modelo.mapeamento or {}
    grupos: dict[str, list[tuple[str, dict]]] = {}
    faltando = []
    for v in modelo.variaveis:
        dado = mapa.get(v["chave"], "")
        valor = _texto((variaveis or {}).get(dado)) if dado else ""
        if not valor:
            faltando.append(VARIAVEIS_DO_LEAD.get(dado, v["chave"]) if dado else v["chave"])
            continue
        parametro = {"type": "text", "text": valor}
        if modelo.formato_parametros == "named" and not v["componente"].startswith("button."):
            parametro["parameter_name"] = v["parametro"]
        grupos.setdefault(v["componente"], []).append((v["parametro"], parametro))
    if faltando:
        raise ValueError("faltam dados para o modelo: " + ", ".join(faltando))
    componentes = []
    for componente in sorted(grupos, key=lambda c: (c != "header", c != "body", c)):
        itens = grupos[componente]
        if modelo.formato_parametros != "named":
            itens = sorted(itens, key=lambda i: int(i[0]) if i[0].isdigit() else 0)
        parametros = [p for _, p in itens]
        if componente.startswith("button."):
            componentes.append({"type": "button", "sub_type": "url", "index": componente.split(".", 1)[1],
                                "parameters": parametros})
        else:
            componentes.append({"type": componente, "parameters": parametros})
    return componentes


def preparar_modelo(nome: str, variaveis: dict | None = None, idioma: str = "") -> dict:
    """Modelo aprovado já preenchido, no formato `modelo` do envio da conversa.

    Devolve {"nome", "idioma", "componentes"}; ValueError quando não há modelo
    aprovado com esse nome ou falta dado do lead.
    """
    escolhido = escolher_modelo(nome, idioma)
    if escolhido is None:
        raise ValueError("modelo nao aprovado ou nao sincronizado")
    if not escolhido.suportado:
        raise ValueError(escolhido.motivo or "modelo ainda nao suportado")
    limpas = {k: _texto(v) for k, v in (variaveis or {}).items() if k in VARIAVEIS_DO_LEAD and v}
    return {"nome": escolhido.nome, "idioma": escolhido.idioma,
            "componentes": montar_componentes(escolhido, limpas)}


def _descadastrado(site_id: str, numero: str) -> bool:
    """Quem pediu PARAR/SAIR no WhatsApp deste site não recebe primeiro contato."""
    from apps.conversas.models import Descadastro

    candidatos = {numero}
    # O WhatsApp entrega alguns números brasileiros sem o nono dígito.
    if numero.startswith("55") and len(numero) == 13 and numero[4] == "9":
        candidatos.add(numero[:4] + numero[5:])
    elif numero.startswith("55") and len(numero) == 12:
        candidatos.add(numero[:4] + "9" + numero[4:])
    return Descadastro.objects.filter(site_id=site_id, canal="whatsapp", endereco__in=candidatos).exists()


def _falhar(envio: EnvioDeModelo, erro: str, *, codigo: str = "", retomavel: bool = True) -> EnvioDeModelo:
    envio.estado = "falhou"
    envio.erro = erro[:300]
    envio.erro_codigo = codigo[:20]
    envio.retomavel = retomavel
    envio.save(update_fields=["estado", "erro", "erro_codigo", "retomavel", "atualizado_em"])
    return envio


def enviar_modelo(*, site_id: str, chave_idempotencia: str, destinatario: str, modelo: str,
                  variaveis: dict | None = None, idioma: str = "", origem: str = "abordagem",
                  referencia: str = "") -> EnvioDeModelo:
    """Envia um modelo aprovado. A reserva da chave é gravada antes da chamada à Meta."""
    if connection.in_atomic_block:
        raise RuntimeError("envio de modelo exige transacao externa concluida")
    site_id = (site_id or "").strip()
    chave = (chave_idempotencia or "").strip()
    if not site_id or not chave or not (modelo or "").strip():
        raise ValueError("site_id, chave_idempotencia e modelo sao obrigatorios")
    try:
        numero = normalizar_telefone(destinatario)
    except ValueError:
        numero = ""
    variaveis = {k: _texto(v) for k, v in (variaveis or {}).items() if k in VARIAVEIS_DO_LEAD and v}
    with transaction.atomic():
        envio, criado = EnvioDeModelo.objects.select_for_update().get_or_create(
            site_id=site_id, chave_idempotencia=chave[:200],
            defaults={"origem": origem[:40], "referencia": (referencia or "")[:200],
                      "modelo_nome": modelo[:512], "idioma": (idioma or "")[:20],
                      "destinatario": numero, "variaveis": variaveis},
        )
        if not criado and not (envio.estado == "falhou" and envio.retomavel):
            return envio
        envio.tentativas += 1
        envio.estado = "reservado"
        envio.erro = "aguardando resposta da meta"
        envio.erro_codigo = ""
        envio.retomavel = False
        envio.modelo_nome, envio.idioma = modelo[:512], (idioma or "")[:20]
        envio.destinatario, envio.variaveis = numero, variaveis
        envio.save()
    if not cloud.configurado():
        return _falhar(envio, "canal oficial do WhatsApp ainda nao ligado")
    if not numero:
        return _falhar(envio, "telefone invalido")
    if _descadastrado(site_id, numero):
        return _falhar(envio, "contato pediu para nao receber mensagens", retomavel=False)
    escolhido = escolher_modelo(modelo, idioma)
    if escolhido is None:
        return _falhar(envio, "modelo nao aprovado ou nao sincronizado")
    if not escolhido.suportado:
        return _falhar(envio, escolhido.motivo or "modelo ainda nao suportado")
    try:
        componentes = montar_componentes(escolhido, variaveis)
    except ValueError as exc:
        return _falhar(envio, str(exc))
    if envio.idioma != escolhido.idioma:
        envio.idioma = escolhido.idioma
        envio.save(update_fields=["idioma", "atualizado_em"])
    template = {"name": escolhido.nome, "language": {"code": escolhido.idioma}}
    if componentes:
        template["components"] = componentes
    corpo = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": numero,
             "type": "template", "template": template}
    provider_id = ""
    try:
        resposta = cloud.pedir("POST", f"{cloud.credenciais()['numero_id']}/messages", dados=corpo)
    except cloud.CloudNaoConfigurado as exc:
        return _falhar(envio, str(exc))
    except cloud.CloudRecusou as exc:
        return _falhar(envio, str(exc), codigo=exc.codigo)
    except cloud.CloudSemResposta as exc:
        estado, erro = "desconhecido", str(exc)
    else:
        mensagens = resposta.get("messages")
        primeira = mensagens[0] if isinstance(mensagens, list) and mensagens and isinstance(mensagens[0], dict) else {}
        provider_id = primeira.get("id") if isinstance(primeira.get("id"), str) else ""
        estado, erro = ("aceito", "") if provider_id else ("desconhecido", "meta aceitou sem identificador")
    with transaction.atomic():
        atual = EnvioDeModelo.objects.select_for_update().get(pk=envio.pk)
        atual.estado, atual.erro = estado, erro
        if provider_id:
            atual.provider_id = provider_id[:200]
            retorno = RetornoDeModelo.objects.filter(provider_id=atual.provider_id).first()
            if retorno:
                _aplicar(atual, retorno.estado, retorno.erro_codigo)
        atual.save(update_fields=["estado", "erro", "erro_codigo", "retomavel", "provider_id", "atualizado_em"])
    return atual


# --------------------------------------------------------------------------- retornos
def _aplicar(envio: EnvioDeModelo, estado: str, codigo: str = "") -> bool:
    if estado == "falhou":
        if envio.estado in ("entregue", "lido", "falhou"):
            return False
        envio.estado = "falhou"
        envio.erro = "meta informou falha na entrega"
        envio.erro_codigo = (codigo or "")[:20]
        envio.retomavel = False  # a mensagem existiu na Meta; repetir seria outra mensagem
        return True
    if ORDEM.get(estado, 0) > ORDEM.get(envio.estado, 0) and envio.estado != "falhou":
        envio.estado = estado
        envio.erro = ""
        return True
    return False


def aplicar_status(status: dict) -> bool:
    """Aplica um item de `statuses` do webhook da Meta. Nunca regride o estado."""
    if not isinstance(status, dict):
        return False
    provider_id = status.get("id")
    estado = STATUS_DA_META.get(str(status.get("status") or "").lower())
    if not isinstance(provider_id, str) or not provider_id or not estado:
        return False
    erros = status.get("errors") if isinstance(status.get("errors"), list) else []
    codigo = str((erros[0] or {}).get("code") or "") if erros and isinstance(erros[0], dict) else ""
    with transaction.atomic():
        retorno, criado = RetornoDeModelo.objects.select_for_update().get_or_create(
            provider_id=provider_id[:200], defaults={"estado": estado, "erro_codigo": codigo[:20]})
        if not criado:
            if estado == "falhou" and retorno.estado not in ("entregue", "lido"):
                retorno.estado, retorno.erro_codigo = estado, codigo[:20]
                retorno.save(update_fields=["estado", "erro_codigo", "atualizado_em"])
            elif estado != "falhou" and ORDEM.get(estado, 0) > ORDEM.get(retorno.estado, 0):
                retorno.estado = estado
                retorno.save(update_fields=["estado", "atualizado_em"])
        envio = EnvioDeModelo.objects.select_for_update().filter(provider_id=provider_id[:200]).first()
        if envio is None or not _aplicar(envio, estado, codigo):
            return False
        envio.save(update_fields=["estado", "erro", "erro_codigo", "retomavel", "atualizado_em"])
    return True


# --------------------------------------------------------------------------- leitura
def resumo_de_modelo(modelo: ModeloWhatsApp) -> dict:
    return {
        "id": modelo.pk, "modelo_id": modelo.modelo_id, "nome": modelo.nome, "idioma": modelo.idioma,
        "categoria": modelo.categoria, "estado": modelo.estado,
        "estado_no_provedor": modelo.estado_no_provedor, "corpo": modelo.corpo,
        "variaveis": modelo.variaveis, "mapeamento": modelo.mapeamento,
        "faltando": faltando_no_mapeamento(modelo), "suportado": modelo.suportado,
        "motivo": modelo.motivo, "presente_no_provedor": modelo.presente_no_provedor,
        "sincronizado_em": modelo.sincronizado_em.isoformat() if modelo.sincronizado_em else None,
    }


def resumo_de_envio(envio: EnvioDeModelo) -> dict:
    return {
        "id": envio.pk, "chave_idempotencia": envio.chave_idempotencia, "origem": envio.origem,
        "referencia": envio.referencia, "modelo": envio.modelo_nome, "idioma": envio.idioma,
        "estado": envio.estado, "provider_id": envio.provider_id,
        "numero_mascarado": mascarar_telefone(envio.destinatario), "erro": envio.erro,
        "erro_codigo": envio.erro_codigo, "retomavel": envio.retomavel, "tentativas": envio.tentativas,
        "criado_em": envio.criado_em.isoformat(), "atualizado_em": envio.atualizado_em.isoformat(),
    }


def painel(site_id: str) -> dict:
    conta = cloud.credenciais()["conta"]
    modelos = ModeloWhatsApp.objects.filter(conta=conta).order_by("-presente_no_provedor", "nome", "idioma") if conta else []
    envios = EnvioDeModelo.objects.filter(site_id=site_id).order_by("-id")[:50]
    return {
        "canal_oficial": "ligado" if cloud.configurado() else "nao_ligado",
        "variaveis_do_lead": VARIAVEIS_DO_LEAD,
        "modelos": [resumo_de_modelo(m) for m in modelos],
        "envios": [resumo_de_envio(e) for e in envios],
    }
