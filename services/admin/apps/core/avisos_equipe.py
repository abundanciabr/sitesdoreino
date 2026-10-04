"""Avisos para a equipe: o atendimento comercial chama uma pessoa.

Cinco fatos pedem alguém da equipe, e cada um vira UM aviso (no painel e por
e-mail), nunca dois:

- `pessoa_pedida`: o lead pediu uma pessoa ou o agente passou a conversa. Na
  mensageria isso é a conversa no estado `pessoa`; o fato é a conversa e o
  momento em que ela foi passada (`assumida_em`), então passar de novo depois
  de devolver ao agente é outro aviso.
- `venda_assistida`: venda aprovada numa oportunidade atendida pelo agente.
  Só conta o que a célula `leads` diz que foi aprovado (`aprovado_centavos`
  da receita da oportunidade, que vem do provedor de pagamento).
- `conversa_ambigua`: a mensageria não soube a qual lead a conversa pertence.
- `trabalho_parado`: trabalho que espera o provedor ou o modelo há mais de
  alguns minutos.
- `envio_incerto`: mensagem enviada cujo resultado o provedor não confirmou
  (`estado_envio = desconhecido`) há mais de alguns minutos.

Os fatos chegam de dois jeitos: quem sabe na hora chama `avisar(...)` (o
coordenador, as ferramentas), e `varrer()` pergunta às células pelas APIs a
cada volta do executor dos robôs. Os dois caminhos caem no mesmo
`(tipo, site_id, fato)` único, e é isso que torna o aviso idempotente.

O e-mail usa o caminho que já existe para e-mail: a mensageria, que registra o
envio com chave própria e fala com o provedor. Mensagem do lead não entra no
aviso: o aviso diz o que aconteceu e leva o link, e quem abre lê a conversa lá.
"""

from __future__ import annotations

import hashlib
import logging
import os
from datetime import timedelta, timezone as dt_timezone
from urllib.parse import quote

import httpx
from django.apps import apps as django_apps
from django.conf import settings
from django.db import IntegrityError, transaction
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import NoReverseMatch, reverse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST

from .clients import MensageriaClient, http
from .crm_client import CRMClient
from .models import AvisoDaEquipe, MembroDaEquipe

log = logging.getLogger(__name__)

Tipo = AvisoDaEquipe.Tipo
Email = AvisoDaEquipe.Email

#: Quanto um trabalho ou um envio pode ficar sem resposta antes de virar aviso.
MINUTOS_DE_TOLERANCIA = 10
#: Depois de tantas tentativas o e-mail desiste; o aviso continua no painel.
MAXIMO_DE_TENTATIVAS = 10
#: Conversas recentes em que procurar envio incerto, por site e por volta.
CONVERSAS_POR_VOLTA = 30

ASSUNTOS = {
    Tipo.PESSOA_PEDIDA: "Uma conversa precisa de você",
    Tipo.VENDA_ASSISTIDA: "Venda aprovada com atendimento do agente",
    Tipo.CONVERSA_AMBIGUA: "Conversa sem contato definido",
    Tipo.TRABALHO_PARADO: "Trabalho comercial parado",
    Tipo.ENVIO_INCERTO: "Mensagem sem confirmação de envio",
}


# ---------------------------------------------------------------------------
# O aviso
# ---------------------------------------------------------------------------
def _fato(texto: str) -> str:
    texto = (texto or "").strip()
    if len(texto) <= 200:
        return texto
    return "h:" + hashlib.sha256(texto.encode("utf-8")).hexdigest()


def resolver_responsavel(informado: str) -> MembroDaEquipe | None:
    """A pessoa da equipe a partir do que a outra célula guardou.

    O CRM e a mensageria guardam um texto (e-mail, id da pessoa ou nome). Só
    vira pessoa quando bate com alguém ativo; senão o aviso é da equipe."""
    texto = (informado or "").strip()
    if not texto:
        return None
    ativos = MembroDaEquipe.objects.filter(ativo=True)
    if "@" in texto:
        return ativos.filter(email__iexact=texto).first()
    if texto.isdigit():
        membro = ativos.filter(pk=int(texto)).first()
        if membro is not None:
            return membro
    if texto.startswith("membro-") and texto[7:].isdigit():
        return ativos.filter(pk=int(texto[7:])).first()
    return ativos.filter(nome__iexact=texto).first()


def avisar(
    tipo: str,
    *,
    fato: str,
    titulo: str,
    site_id: str = "",
    responsavel: str = "",
    texto: str = "",
    link: str = "",
) -> tuple[AvisoDaEquipe, bool]:
    """Registra o aviso deste fato. Devolve `(aviso, criado)`.

    O mesmo fato de novo devolve o aviso que já existe, sem e-mail novo."""
    if tipo not in Tipo.values:
        raise ValueError(f"tipo de aviso desconhecido: {tipo}")
    chave = dict(tipo=tipo, site_id=(site_id or "").strip()[:100], fato=_fato(fato))
    existente = AvisoDaEquipe.objects.filter(**chave).first()
    if existente is not None:
        return existente, False
    dados = dict(
        responsavel=resolver_responsavel(responsavel),
        responsavel_informado=(responsavel or "").strip()[:200],
        titulo=(titulo or ASSUNTOS.get(tipo, "Aviso"))[:200],
        texto=texto or "",
        link=(link or "")[:500],
    )
    try:
        with transaction.atomic():
            aviso = AvisoDaEquipe.objects.create(**chave, **dados)
    except IntegrityError:
        return AvisoDaEquipe.objects.get(**chave), False
    transaction.on_commit(lambda: _enviar_sem_derrubar(aviso.pk))
    return aviso, True


# ---------------------------------------------------------------------------
# O e-mail, pelo caminho que a mensageria já tem
# ---------------------------------------------------------------------------
class _Correio(MensageriaClient):
    """As duas conversas desta tela com a mensageria."""

    def avisar_por_email(self, *, site_id, chave, destinatario, assunto, corpo):
        config = self._configuracao()
        if config is None:
            return self.NAO_RESPONDEU, "a ligação com a mensageria não está configurada"
        base, token = config
        try:
            r = http().post(
                base + "/avisos-equipe",
                json={
                    "site_id": site_id,
                    "chave": chave,
                    "destinatario": destinatario,
                    "assunto": assunto,
                    "corpo": corpo,
                },
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError:
            return self.NAO_RESPONDEU, "a mensageria não respondeu"
        if r.status_code == 200:
            return self.OK, ""
        if r.status_code == 422:
            return self.RECUSADO, "a mensageria recusou o endereço"
        return self.NAO_RESPONDEU, f"a mensageria respondeu HTTP {r.status_code}"

    def ler(self, caminho: str, parametros: dict) -> dict | None:
        config = self._configuracao()
        if config is None:
            return None
        base, token = config
        try:
            r = http().get(
                base + caminho,
                params=parametros,
                headers={"Authorization": "Bearer " + token},
                timeout=self.TIMEOUT,
            )
        except httpx.HTTPError:
            return None
        if r.status_code != 200:
            return None
        try:
            corpo = r.json()
        except ValueError:
            return None
        return corpo if isinstance(corpo, dict) else None


def endereco_do_painel() -> str:
    return (os.environ.get("ENDERECO_DO_PAINEL") or "https://meshcraft.top").rstrip("/")


def destinatarios(aviso: AvisoDaEquipe) -> list[str]:
    """Quem recebe o e-mail: o responsável; sem responsável, quem administra."""
    membro = aviso.responsavel
    if membro is not None and membro.ativo and membro.email and not membro.email_a_conferir:
        return [membro.email.strip().lower()]
    cru = getattr(settings, "ADMIN_EMAILS", "") or ""
    vistos: list[str] = []
    for email in cru.split(","):
        email = email.strip().lower()
        if "@" in email and email not in vistos:
            vistos.append(email)
    return vistos


def _corpo_do_email(aviso: AvisoDaEquipe) -> str:
    linhas = [aviso.titulo, ""]
    if aviso.texto:
        linhas += [aviso.texto, ""]
    if aviso.link:
        linhas += ["Abrir: " + endereco_do_painel() + aviso.link, ""]
    linhas.append(
        "Aviso automático do painel. Todos os avisos: "
        + endereco_do_painel()
        + "/admin/equipe/avisos/"
    )
    return "\n".join(linhas)


def enviar_email(aviso_id: int) -> str:
    """Pede o e-mail deste aviso. Devolve a situação do e-mail depois disso."""
    aviso = AvisoDaEquipe.objects.select_related("responsavel").get(pk=aviso_id)
    if aviso.email_situacao != Email.PENDENTE:
        return aviso.email_situacao
    para = destinatarios(aviso)
    if not para:
        aviso.email_situacao = Email.SEM_DESTINATARIO
        aviso.save(update_fields=["email_situacao"])
        return aviso.email_situacao
    correio = _Correio()
    erro = ""
    for email in para:
        situacao, detalhe = correio.avisar_por_email(
            site_id=aviso.site_id,
            chave=f"aviso-equipe-{aviso.pk}-{hashlib.sha256(email.encode()).hexdigest()[:16]}",
            destinatario=email,
            assunto=ASSUNTOS.get(aviso.tipo, "Aviso do painel"),
            corpo=_corpo_do_email(aviso),
        )
        if situacao != correio.OK:
            erro = detalhe
    aviso.email_tentativas += 1
    if not erro:
        aviso.email_situacao = Email.PEDIDO
        aviso.email_erro = ""
    else:
        aviso.email_erro = erro[:300]
        if aviso.email_tentativas >= MAXIMO_DE_TENTATIVAS:
            aviso.email_situacao = Email.DESISTIU
    aviso.save(update_fields=["email_situacao", "email_tentativas", "email_erro"])
    return aviso.email_situacao


def _enviar_sem_derrubar(aviso_id: int) -> None:
    try:
        enviar_email(aviso_id)
    except Exception:  # noqa: BLE001 - o e-mail não derruba quem avisou
        log.exception("Avisos da equipe: e-mail do aviso %s falhou", aviso_id)


def enviar_emails_pendentes(limite: int = 50) -> int:
    n = 0
    for pk in AvisoDaEquipe.objects.filter(email_situacao=Email.PENDENTE).order_by("pk").values_list("pk", flat=True)[:limite]:
        _enviar_sem_derrubar(pk)
        n += 1
    return n


# ---------------------------------------------------------------------------
# Links
# ---------------------------------------------------------------------------
def _rota(nomes: tuple[str, ...], args: list) -> str:
    for nome in nomes:
        try:
            caminho = reverse(nome, args=args)
        except NoReverseMatch:
            continue
        return caminho if caminho.startswith("/admin/") else "/admin" + caminho
    return ""


def link_da_conversa(conversa: dict) -> str:
    conversa_id = str(conversa.get("id") or "")
    site_id = str(conversa.get("site_id") or "")
    caminho = _rota(("conversa", "conversa_detalhe", "crm_conversa"), [conversa_id]) if conversa_id else ""
    if caminho:
        return caminho + ("?site_id=" + quote(site_id) if site_id else "")
    lead_id = str(conversa.get("lead_id") or "")
    if lead_id:
        return "/admin/contatos/" + quote(lead_id, safe="") + "/"
    return "/admin/crm/"


def link_da_oportunidade(oportunidade_id: str) -> str:
    return "/admin/crm/" + quote(str(oportunidade_id), safe="") + "/"


# ---------------------------------------------------------------------------
# A varredura: pergunta às células e transforma fato em aviso
# ---------------------------------------------------------------------------
def _instante(texto):
    from django.utils.dateparse import parse_datetime

    try:
        valor = parse_datetime(texto) if isinstance(texto, str) else None
    except (TypeError, ValueError):
        return None
    if valor is not None and timezone.is_naive(valor):
        valor = timezone.make_aware(valor, dt_timezone.utc)
    return valor


def _itens(corpo) -> list[dict]:
    if not isinstance(corpo, dict):
        return []
    itens = corpo.get("itens")
    return [i for i in itens if isinstance(i, dict)] if isinstance(itens, list) else []


def sites_conhecidos(oportunidades: list[dict] | None = None) -> list[str]:
    sites: list[str] = []
    extra = os.environ.get("AVISOS_EQUIPE_SITES") or ""
    candidatos = [s.strip() for s in extra.split(",")]
    for item in oportunidades or []:
        contato = item.get("contato") if isinstance(item.get("contato"), dict) else {}
        candidatos.append(str(contato.get("site_id") or item.get("site_id") or ""))
    for site in candidatos:
        if site and site not in sites:
            sites.append(site)
    return sites


def _nome_do_contato(item: dict) -> str:
    contato = item.get("contato") if isinstance(item.get("contato"), dict) else {}
    return str(contato.get("nome") or "o contato")


def _atendido_por(item: dict) -> dict:
    valor = item.get("atendido_por")
    if valor is None and isinstance(item.get("acompanhamento"), dict):
        valor = item["acompanhamento"].get("atendido_por")
    return valor if isinstance(valor, dict) else {}


def _reais(centavos) -> str:
    try:
        valor = int(centavos) / 100
    except (TypeError, ValueError):
        return ""
    return ("R$ %.2f" % valor).replace(".", ",")


def varrer_vendas_assistidas() -> list[dict]:
    """Oportunidades ganhas atendidas pelo agente, com pagamento aprovado."""
    crm = CRMClient()
    estado, dados = crm.quadro(etapa="ganha", atendido_por="agente", testes="ocultar", pagina=1, por_pagina=100)
    if estado != crm.OK:
        return []
    itens = dados.get("itens") or []
    for item in itens:
        if item.get("registro_de_teste"):
            continue
        if (_atendido_por(item).get("tipo") or "") != "agente":
            continue
        oportunidade_id = str(item.get("id") or "")
        if not oportunidade_id:
            continue
        situacao, receita = crm.pedir("GET", "/" + quote(oportunidade_id, safe="") + "/receita")
        if situacao != crm.OK or not isinstance(receita, dict):
            continue
        try:
            aprovado = int(receita.get("aprovado_centavos") or 0)
        except (TypeError, ValueError):
            aprovado = 0
        if aprovado <= 0:
            continue
        nome = _nome_do_contato(item)
        valor = _reais(receita.get("liquido_centavos", aprovado))
        avisar(
            Tipo.VENDA_ASSISTIDA,
            site_id=str((item.get("contato") or {}).get("site_id") or ""),
            fato="oportunidade:" + oportunidade_id,
            responsavel=str((item.get("titular") or {}).get("id") or item.get("titular_id") or ""),
            titulo=f"Venda aprovada: {nome}",
            texto=(
                f"O pagamento de {nome} foi aprovado"
                + (f" ({valor} líquido)" if valor else "")
                + ", numa oportunidade atendida pelo agente."
            ),
            link=link_da_oportunidade(oportunidade_id),
        )
    return itens


def varrer_conversas(site_id: str, agora=None) -> None:
    agora = agora or timezone.now()
    correio = _Correio()
    if not correio.ligado():
        return
    limite = agora - timedelta(minutes=MINUTOS_DE_TOLERANCIA)

    pedidas = correio.ler("/conversas", {"site_id": site_id, "estado": "pessoa", "ligacao": "todas", "por_pagina": 100})
    for conversa in _itens(pedidas):
        if conversa.get("estado") != "pessoa":
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        marca = str(conversa.get("assumida_em") or "")
        avisar(
            Tipo.PESSOA_PEDIDA,
            site_id=site_id,
            fato=f"conversa:{conversa_id}:{marca}",
            responsavel=str(conversa.get("assumida_por") or ""),
            titulo="Uma conversa foi passada para a equipe",
            texto=(
                f"A conversa por {conversa.get('canal') or 'mensagem'} está com a equipe: "
                "o contato pediu uma pessoa ou o agente passou o atendimento. "
                "O agente não responde enquanto ela estiver com vocês."
            ),
            link=link_da_conversa(conversa),
        )

    ambiguas = correio.ler("/conversas", {"site_id": site_id, "ligacao": "ambigua", "por_pagina": 100})
    for conversa in _itens(ambiguas):
        if not (conversa.get("ambigua") or conversa.get("ligacao") == "ambigua"):
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        avisar(
            Tipo.CONVERSA_AMBIGUA,
            site_id=site_id,
            fato=f"conversa:{conversa_id}",
            titulo="Conversa sem contato definido",
            texto=(
                f"Uma conversa por {conversa.get('canal') or 'mensagem'} pode ser de mais de um contato. "
                "O agente não usa dados de nenhum deles até alguém da equipe confirmar quem é."
            ),
            link=link_da_conversa(conversa),
        )

    recentes = correio.ler("/conversas", {"site_id": site_id, "ligacao": "todas", "por_pagina": CONVERSAS_POR_VOLTA})
    for conversa in _itens(recentes):
        ultima = _instante(conversa.get("ultima_mensagem_em"))
        if ultima is None or ultima < agora - timedelta(days=2):
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        mensagens = correio.ler(
            "/conversas/" + quote(conversa_id, safe="") + "/mensagens",
            {"site_id": site_id, "limite": 50},
        )
        if not isinstance(mensagens, dict):
            continue
        for mensagem in mensagens.get("mensagens") or []:
            if not isinstance(mensagem, dict):
                continue
            if mensagem.get("direcao") != "saida" or mensagem.get("estado_envio") != "desconhecido":
                continue
            quando = _instante(mensagem.get("ocorrida_em"))
            if quando is None or quando > limite:
                continue
            avisar(
                Tipo.ENVIO_INCERTO,
                site_id=site_id,
                fato="mensagem:" + str(mensagem.get("id") or ""),
                responsavel=str(conversa.get("assumida_por") or ""),
                titulo="Mensagem sem confirmação de envio",
                texto=(
                    f"Uma mensagem por {conversa.get('canal') or 'mensagem'} saiu há mais de "
                    f"{MINUTOS_DE_TOLERANCIA} minutos e o provedor não confirmou se chegou. "
                    "Ela não será reenviada sozinha: confira a conversa antes de mandar de novo."
                ),
                link=link_da_conversa(conversa),
            )


def _modelo_do_trabalho_comercial():
    """`comercial.TrabalhoComercial`, do coordenador. Sem ele, nada a varrer."""
    for app in ("comercial", "agentes"):
        try:
            return django_apps.get_model(app, "TrabalhoComercial")
        except LookupError:
            continue
    return None


def _link_do_trabalho(trabalho) -> str:
    conversa = str(getattr(trabalho, "conversa_id", "") or "")
    if conversa:
        caminho = link_da_conversa({"id": conversa, "site_id": getattr(trabalho, "site_id", "")})
        if caminho != "/admin/crm/":
            return caminho
    oportunidade = str(getattr(trabalho, "oportunidade_id", "") or "")
    return link_da_oportunidade(oportunidade) if oportunidade else "/admin/crm/"


def varrer_trabalhos_comerciais(limite) -> None:
    """Trabalho comercial esperando o provedor ou o modelo além da tolerância
    vira `trabalho_parado`; trabalho com envio sem confirmação vira
    `envio_incerto`. Um aviso por trabalho e por estado."""
    Modelo = _modelo_do_trabalho_comercial()
    if Modelo is None:
        return
    campos = {f.name for f in Modelo._meta.get_fields()}
    campo_estado = "estado" if "estado" in campos else "situacao" if "situacao" in campos else None
    campo_tempo = next((c for c in ("atualizado_em", "atualizada_em", "criado_em", "criada_em") if c in campos), None)
    if campo_estado is None or campo_tempo is None:
        return
    tipos = {
        "aguardando_dependencia": Tipo.TRABALHO_PARADO,
        "envio_incerto": Tipo.ENVIO_INCERTO,
    }
    consulta = Modelo.objects.filter(
        **{campo_estado + "__in": list(tipos), campo_tempo + "__lte": limite}
    )
    if "teste" in campos:
        consulta = consulta.filter(teste=False)
    for trabalho in consulta.order_by("-pk")[:100]:
        estado = getattr(trabalho, campo_estado)
        motivo = str(getattr(trabalho, "motivo", "") or "")
        if tipos[estado] == Tipo.ENVIO_INCERTO:
            titulo = "Mensagem do agente sem confirmação de envio"
            texto = (
                f"O agente mandou uma mensagem há mais de {MINUTOS_DE_TOLERANCIA} minutos e o provedor "
                "não confirmou se ela saiu. Ela não será reenviada sozinha: confira a conversa."
            )
        else:
            titulo = "Trabalho comercial parado"
            texto = (
                f"Um trabalho comercial espera o provedor ou o modelo há mais de {MINUTOS_DE_TOLERANCIA} minutos"
                + (f": {motivo[:200]}" if motivo else ".")
                + " Ele volta sozinho quando o serviço responder."
            )
        avisar(
            tipos[estado],
            site_id=str(getattr(trabalho, "site_id", "") or ""),
            fato=f"trabalho_comercial:{trabalho.pk}:{estado}:{getattr(trabalho, 'tentativas', 0)}",
            titulo=titulo,
            texto=texto,
            link=_link_do_trabalho(trabalho),
        )


def varrer_trabalhos_parados(agora=None) -> None:
    agora = agora or timezone.now()
    limite = agora - timedelta(minutes=MINUTOS_DE_TOLERANCIA)
    varrer_trabalhos_comerciais(limite)

    # Os trabalhos que o executor dos robôs já roda (leitura e conferência do
    # quiz, panorama) param do mesmo jeito quando a conexão com o modelo cai.
    try:
        Execucao = django_apps.get_model("agentes", "Execucao")
    except LookupError:
        return
    esperando = Execucao.objects.filter(
        situacao=Execucao.Situacao.AGUARDANDO_DEPENDENCIA, atualizada_em__lte=limite
    ).exclude(tipo=Execucao.Tipo.CONVERSA)
    for execucao in esperando.order_by("-pk")[:100]:
        responsavel = str(execucao.pedido_por_membro_id or "")
        avisar(
            Tipo.TRABALHO_PARADO,
            fato=f"execucao:{execucao.pk}:{execucao.tentativas}",
            responsavel=responsavel,
            titulo=f"Trabalho parado: {execucao.get_tipo_display()}",
            texto=(
                f"Este trabalho espera a conexão com o modelo há mais de {MINUTOS_DE_TOLERANCIA} minutos"
                + (f": {execucao.motivo[:200]}" if execucao.motivo else ".")
                + " Ele volta sozinho quando a conexão voltar."
            ),
            link=_rota(("execucao_do_robo",), [execucao.pk]) or "/admin/equipe/robo/",
        )


def varrer(agora=None) -> None:
    """Uma volta: cada parte falha sozinha, sem levar as outras junto."""
    agora = agora or timezone.now()
    oportunidades: list[dict] = []
    try:
        oportunidades = varrer_vendas_assistidas()
    except Exception:  # noqa: BLE001
        log.exception("Avisos da equipe: vendas assistidas")
    estado, dados = CRMClient().quadro(situacao="aberta", testes="ocultar", pagina=1, por_pagina=100)
    if estado == CRMClient.OK:
        oportunidades = oportunidades + list(dados.get("itens") or [])
    sites = sites_conhecidos(oportunidades)
    for site in AvisoDaEquipe.objects.exclude(site_id="").values_list("site_id", flat=True).distinct()[:20]:
        if site not in sites:
            sites.append(site)
    for site in sites:
        try:
            varrer_conversas(site, agora)
        except Exception:  # noqa: BLE001
            log.exception("Avisos da equipe: conversas do site %s", site)
    try:
        varrer_trabalhos_parados(agora)
    except Exception:  # noqa: BLE001
        log.exception("Avisos da equipe: trabalhos parados")
    enviar_emails_pendentes()


# ---------------------------------------------------------------------------
# As telas
# ---------------------------------------------------------------------------
def _membro(request) -> MembroDaEquipe | None:
    from .equipe import _membro_da_sessao

    return _membro_da_sessao(request)


def _avisos_de(request):
    """O mantenedor vê todos; a pessoa da equipe vê os dela e os da equipe."""
    consulta = AvisoDaEquipe.objects.select_related("responsavel")
    if request.admin.get("equipe_apenas"):
        membro = _membro(request)
        if membro is None:
            return consulta.filter(responsavel__isnull=True)
        return consulta.filter(responsavel__isnull=True) | consulta.filter(responsavel=membro)
    return consulta


def nao_vistos(request) -> int:
    try:
        return _avisos_de(request).filter(visto_em__isnull=True).count()
    except Exception:  # noqa: BLE001 - contador não derruba tela
        return 0


@require_GET
def avisos_da_equipe(request):
    mostrar = request.GET.get("mostrar", "novos")
    if mostrar not in ("novos", "todos"):
        mostrar = "novos"
    consulta = _avisos_de(request)
    if mostrar == "novos":
        consulta = consulta.filter(visto_em__isnull=True)
    return render(
        request,
        "admin/equipe_avisos.html",
        {
            "admin": request.admin,
            "visao": "avisos",
            "mostrar": mostrar,
            "avisos": list(consulta.order_by("-criado_em", "-id")[:200]),
            "nao_vistos": nao_vistos(request),
        },
    )


@require_POST
def aviso_visto(request, id: int):
    aviso = _avisos_de(request).filter(pk=id).first()
    if aviso is None:
        raise Http404("Aviso não encontrado")
    if aviso.visto_em is None:
        aviso.visto_em = timezone.now()
        aviso.visto_por = str(request.admin.get("nome") or request.admin.get("email") or "")[:200]
        aviso.save(update_fields=["visto_em", "visto_por"])
    destino = request.POST.get("abrir") == "1" and aviso.link
    return HttpResponseRedirect(destino or reverse("avisos_da_equipe"))
