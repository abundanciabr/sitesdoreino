"""Avisos para a equipe: o atendimento comercial chama uma pessoa.

Cinco fatos pedem alguém da equipe, e cada um vira UM aviso (no painel e por
e-mail), nunca dois:

- `pessoa_pedida`: o agente passou a conversa para a equipe. Na mensageria
  isso é a conversa no estado `pessoa` com `assumida_por = "equipe"`; o fato é
  a conversa e o momento em que ela foi passada (`assumida_em`), então passar
  de novo depois de devolver ao agente é outro aviso. Conversa que uma pessoa
  assumiu pelo painel não avisa: quem assumiu já sabe.
- `venda_assistida`: venda aprovada numa oportunidade atendida pelo agente.
  Só conta o que a célula `leads` diz que foi aprovado (`aprovado_centavos`
  da receita da oportunidade, que vem do provedor de pagamento).
- `conversa_ambigua`: a mensageria não soube a qual lead a conversa pertence.
- `trabalho_parado`: trabalho que espera o provedor ou o modelo há mais de
  alguns minutos.
- `envio_incerto`: mensagem enviada cujo resultado o provedor não confirmou
  (`estado_envio = desconhecido`) há mais de alguns minutos. Um aviso por
  conversa, com a contagem no texto.

Quem gera os avisos é `varrer()`, que pergunta às células pelas APIs a cada
volta do laço de fundo dos robôs (nunca dentro de uma tela). `avisar(...)`
também pode ser chamado por quem sabe do fato na hora. Os dois caminhos caem
no mesmo `(tipo, site_id, fato)` único, e é isso que torna o aviso idempotente.

Para não virar ruído: só fato das últimas 24 horas vira aviso (na primeira
volta depois de publicar, o que já era velho fica de fora), uma volta manda no
máximo `EMAILS_POR_VOLTA` e-mails (o resto sai nas voltas seguintes) e o
trabalho parado avisa uma vez por trabalho, com teto de avisos novos por volta.

Fato de teste não vira aviso nem e-mail, em nenhum dos tipos. É teste o que o
resto do projeto já chama de teste: contato de e-mail `@example.com` ou
`@exemplo.test`, nome com "teste", "test" ou "sandbox", origem ou `utm_source`
"sandbox" (`comercial.eventos.de_teste`, o critério do coordenador, e o
`LEAD_DE_TESTE` da `leads`). A conversa só traz o `lead_id`, então quem é o
lead vem da `leads` (uma pergunta por lead, guardada por alguns minutos, com
teto por volta). Se a `leads` não responde, o aviso espera: nada é criado
naquela volta e a próxima tenta de novo. O trabalho do robô pessoal
(`trabalho_parado` de `agentes.Execucao`) não tem contato nenhum, então não há
o que classificar nele.

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

from .clients import LeadsClient, MensageriaClient, http
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
#: Fato mais velho que isto não vira aviso. É o corte da primeira volta depois
#: de publicar: sem ele, toda conversa antiga viraria aviso e e-mail de uma vez.
JANELA_DOS_FATOS = timedelta(hours=24)
#: E-mails que UMA volta pede à mensageria. O que passar disso fica
#: "aguardando envio" e sai nas voltas seguintes.
EMAILS_POR_VOLTA = 10
#: Avisos novos de trabalho parado por volta, para cada origem de trabalho.
AVISOS_DE_TRABALHO_POR_VOLTA = 10
#: Quanto vale, nesta máquina, a resposta "ainda sem pagamento aprovado" da
#: receita de uma oportunidade (para não perguntar de novo a cada volta).
VALIDADE_DA_RECEITA = timedelta(minutes=15)
#: Quanto vale a resposta "este lead é (ou não é) de teste". Nome e e-mail de lead
#: quase não mudam; só resposta certa fica guardada.
VALIDADE_DO_LEAD = timedelta(minutes=30)
#: Perguntas à `leads` que UMA volta pode fazer. O que passar disso espera a
#: volta seguinte (as respostas já dadas ficam guardadas).
PERGUNTAS_A_LEADS_POR_VOLTA = 20
#: Fim do endereço que só existe em teste (mesmos do `LEAD_DE_TESTE` da `leads`).
ENDERECOS_DE_TESTE = ("@example.com", "@exemplo.test")
#: O que a pessoa de crachá de equipe lê no lugar do nome e do valor do cliente.
VENDA_SEM_DADO_DO_CLIENTE = (
    "Venda aprovada com atendimento do agente",
    "Um pagamento foi aprovado numa oportunidade atendida pelo agente.",
)

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
    enviar_agora: bool = True,
) -> tuple[AvisoDaEquipe, bool]:
    """Registra o aviso deste fato. Devolve `(aviso, criado)`.

    O mesmo fato de novo devolve o aviso que já existe, sem e-mail novo.
    `enviar_agora=False` deixa o e-mail "aguardando envio" para quem chamou
    mandar depois, dentro do limite da volta (é o que a varredura faz)."""
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
    if enviar_agora:
        transaction.on_commit(lambda: _enviar_sem_derrubar(aviso.pk))
    return aviso, True


# ---------------------------------------------------------------------------
# O e-mail, pelo caminho que a mensageria já tem
# ---------------------------------------------------------------------------
class _Correio(MensageriaClient):
    """As duas conversas desta tela com a mensageria."""

    #: Falta variável de ambiente do par com a mensageria.
    SEM_CONFIGURACAO = "sem_configuracao"
    #: Configuração que falta ou está errada: o aviso espera, não desiste.
    ESPERAM_A_CONFIGURACAO = (SEM_CONFIGURACAO, MensageriaClient.SEM_GRAU)

    def avisar_por_email(self, *, site_id, chave, destinatario, assunto, corpo):
        config = self._configuracao()
        if config is None:
            return self.SEM_CONFIGURACAO, "a ligação com a mensageria não está configurada"
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
        if r.status_code == 403:
            return self.SEM_GRAU, (
                "o par do painel com a mensageria não tem o grau de publicação "
                "(falta o token em TOKENS_PUBLICACAO_ADMIN)"
            )
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


def administradores() -> frozenset[str]:
    """Quem administra o painel: o mesmo conjunto que a porta deixa entrar
    (`ADMIN_EMAILS` mais os administradores promovidos pela tela)."""
    from .porta import _emails_autorizados

    return frozenset(e for e in _emails_autorizados() if "@" in e)


def destinatarios(aviso: AvisoDaEquipe) -> list[str]:
    """Quem recebe o e-mail: o responsável; sem responsável, quem administra."""
    membro = aviso.responsavel
    if membro is not None and membro.ativo and membro.email and not membro.email_a_conferir:
        return [membro.email.strip().lower()]
    return sorted(administradores())


def link_para(aviso: AvisoDaEquipe, administrador: bool) -> str:
    """O link que esta pessoa consegue abrir. A pessoa de crachá de equipe só
    entra sob `/admin/equipe/`; o resto do painel responde "não existe" para
    ela, então o link não vai (um botão que leva a 404 só atrapalha)."""
    if administrador or aviso.link.startswith("/admin/equipe/"):
        return aviso.link
    return ""


def conteudo_para(aviso: AvisoDaEquipe, administrador: bool) -> tuple[str, str]:
    """Título e texto para esta pessoa. Nome e valor do cliente são dado de
    dono (ficam fora de `/equipe/`), então a pessoa de crachá lê só o fato."""
    if aviso.tipo == Tipo.VENDA_ASSISTIDA and not administrador:
        return VENDA_SEM_DADO_DO_CLIENTE
    return aviso.titulo, aviso.texto


def _corpo_do_email(aviso: AvisoDaEquipe, administrador: bool = True) -> str:
    titulo, texto = conteudo_para(aviso, administrador)
    linhas = [titulo, ""]
    if texto:
        linhas += [texto, ""]
    link = link_para(aviso, administrador)
    if link:
        linhas += ["Abrir: " + endereco_do_painel() + link, ""]
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
    quem_administra = administradores()
    erro = ""
    esperando_a_configuracao = False
    for email in para:
        situacao, detalhe = correio.avisar_por_email(
            site_id=aviso.site_id,
            chave=f"aviso-equipe-{aviso.pk}-{hashlib.sha256(email.encode()).hexdigest()[:16]}",
            destinatario=email,
            assunto=ASSUNTOS.get(aviso.tipo, "Aviso do painel"),
            corpo=_corpo_do_email(aviso, email in quem_administra),
        )
        if situacao != correio.OK:
            erro = detalhe
            esperando_a_configuracao = esperando_a_configuracao or situacao in correio.ESPERAM_A_CONFIGURACAO
    if esperando_a_configuracao:
        # O defeito é da ligação, não deste aviso: não gasta tentativa, e o
        # e-mail sai sozinho numa volta depois que a configuração for acertada.
        aviso.email_erro = erro[:300]
        aviso.save(update_fields=["email_erro"])
        return aviso.email_situacao
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


def enviar_emails_pendentes(limite: int = EMAILS_POR_VOLTA) -> int:
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


#: Receita de oportunidade já perguntada à `leads`: id -> (vale até, receita ou
#: None quando a pergunta não deu). Só serve quando o item do quadro não traz a
#: receita embutida; evita repetir a pergunta a cada volta.
_RECEITAS: dict[str, tuple] = {}
#: Conversa já lida por inteiro: "site:conversa" -> (última mensagem, quando
#: foi lida). Conversa parada, lida depois da tolerância, não é lida de novo.
_CONVERSAS_LIDAS: dict[str, tuple] = {}
_LIMITE_DAS_MEMORIAS = 1000


#: Lead já perguntado à `leads`: id -> (vale até, é de teste).
_LEADS_DE_TESTE: dict[str, tuple] = {}


def _contato_de_teste(nome="", email="", origem="", utm=None, dados=None) -> bool:
    """O critério de teste do coordenador comercial (`eventos.de_teste`), mais a
    origem "sandbox" que a `leads` também conta como teste."""
    from apps.comercial import eventos

    contato = {"nome": str(nome or ""), "email": str(email or "").strip().lower()}
    base = dict(dados) if isinstance(dados, dict) else {}
    if "utm" not in base:
        base["utm"] = utm if isinstance(utm, dict) else {}
    return bool(eventos.de_teste(contato, base) or "sandbox" in str(origem or "").lower())


class _PerguntasALeads:
    """As perguntas desta volta à `leads` sobre quem é o lead de uma conversa.

    `lead_de_teste` devolve `True` ou `False` quando sabe e `None` quando não dá
    para saber agora (a `leads` não respondeu, não está configurada ou o teto da
    volta acabou): quem recebe `None` não avisa, e a próxima volta tenta de novo.
    Depois da primeira pergunta que não deu, a volta não insiste."""

    def __init__(self) -> None:
        self.feitas = 0
        self.fora_do_ar = False

    def lead_de_teste(self, lead_id: str) -> bool | None:
        lead_id = (lead_id or "").strip()
        if not lead_id:
            return False
        agora = timezone.now()
        guardada = _LEADS_DE_TESTE.get(lead_id)
        if guardada is not None and guardada[0] > agora:
            return guardada[1]
        if self.fora_do_ar or self.feitas >= PERGUNTAS_A_LEADS_POR_VOLTA:
            return None
        self.feitas += 1
        cliente = LeadsClient()
        if cliente._configuracao() is None:
            self.fora_do_ar = True
            return None
        desfecho, lead = cliente.lead(lead_id)
        if desfecho == cliente.NAO_EXISTE:
            de_teste = False
        elif desfecho == cliente.OK and isinstance(lead, dict):
            de_teste = _contato_de_teste(lead.get("nome"), lead.get("email"), lead.get("origem"), lead.get("utm"))
        else:
            self.fora_do_ar = True
            return None
        if len(_LEADS_DE_TESTE) >= _LIMITE_DAS_MEMORIAS:
            _LEADS_DE_TESTE.clear()
        _LEADS_DE_TESTE[lead_id] = (agora + VALIDADE_DO_LEAD, de_teste)
        return de_teste

    def conversa_de_teste(self, conversa: dict) -> bool | None:
        """`True` (de teste), `False` (de verdade) ou `None` (não deu para saber)."""
        if str(conversa.get("endereco_mascarado") or "").strip().lower().endswith(ENDERECOS_DE_TESTE):
            return True
        return self.lead_de_teste(str(conversa.get("lead_id") or ""))

    def trabalho_de_teste(self, trabalho) -> bool | None:
        """O trabalho comercial que o coordenador ainda não marcou como teste: o que
        o evento trouxe (`entrada`) e, na falta, o contato na `leads`."""
        entrada = getattr(trabalho, "entrada", None)
        entrada = entrada if isinstance(entrada, dict) else {}
        contato = entrada.get("contato") if isinstance(entrada.get("contato"), dict) else {}
        if _contato_de_teste(contato.get("nome"), contato.get("email"), dados=entrada):
            return True
        return self.lead_de_teste(str(getattr(trabalho, "contato_id", "") or ""))


def _chave(site_id: str, fato: str) -> tuple[str, str]:
    """A parte do `(tipo, site_id, fato)` que `avisar` grava."""
    return (site_id or "").strip()[:100], _fato(fato)


def _ja_avisados(tipo: str, pares: list[tuple[str, str]]) -> set[tuple[str, str]]:
    """Dos pares `(site, fato)`, os que já têm aviso. Uma consulta só."""
    if not pares:
        return set()
    fatos = {_fato(fato) for _, fato in pares}
    achados = AvisoDaEquipe.objects.filter(tipo=tipo, fato__in=fatos).values_list("site_id", "fato")
    return set(achados)


def _receita_da_oportunidade(crm: CRMClient, item: dict) -> dict | None:
    embutida = item.get("receita")
    if isinstance(embutida, dict) and "aprovado_centavos" in embutida:
        return embutida
    chave = str(item.get("id") or "")
    agora = timezone.now()
    guardada = _RECEITAS.get(chave)
    if guardada is not None and guardada[0] > agora:
        return guardada[1]
    situacao, receita = crm.pedir("GET", "/" + quote(chave, safe="") + "/receita")
    receita = receita if situacao == crm.OK and isinstance(receita, dict) else None
    if len(_RECEITAS) >= _LIMITE_DAS_MEMORIAS:
        for velha in [c for c, (ate, _) in _RECEITAS.items() if ate <= agora]:
            del _RECEITAS[velha]
        if len(_RECEITAS) >= _LIMITE_DAS_MEMORIAS:
            _RECEITAS.clear()
    _RECEITAS[chave] = (agora + VALIDADE_DA_RECEITA, receita)
    return receita


def _aprovada_em(receita: dict):
    """O momento da última aprovação, quando a receita traz as compras."""
    quando = None
    for compra in receita.get("compras") or []:
        momento = _instante(compra.get("aprovado_em")) if isinstance(compra, dict) else None
        if momento is not None and (quando is None or momento > quando):
            quando = momento
    return quando


def varrer_vendas_assistidas(agora=None) -> list[dict]:
    """Oportunidades ganhas atendidas pelo agente, com pagamento aprovado."""
    agora = agora or timezone.now()
    desde = agora - JANELA_DOS_FATOS
    crm = CRMClient()
    estado, dados = crm.quadro(etapa="ganha", atendido_por="agente", testes="ocultar", pagina=1, por_pagina=100)
    if estado != crm.OK:
        return []
    itens = dados.get("itens") or []
    candidatas = []
    for item in itens:
        contato = item.get("contato") if isinstance(item.get("contato"), dict) else {}
        if item.get("registro_de_teste") or _contato_de_teste(contato.get("nome"), contato.get("email")):
            continue
        if (_atendido_por(item).get("tipo") or "") != "agente":
            continue
        oportunidade_id = str(item.get("id") or "")
        if not oportunidade_id:
            continue
        site = str((item.get("contato") or {}).get("site_id") or "")
        candidatas.append((item, oportunidade_id, site))
    # Quem já tem aviso não precisa de pergunta nenhuma à `leads`.
    ja = _ja_avisados(Tipo.VENDA_ASSISTIDA, [(site, "oportunidade:" + o) for _, o, site in candidatas])
    for item, oportunidade_id, site in candidatas:
        fato = "oportunidade:" + oportunidade_id
        if _chave(site, fato) in ja:
            continue
        receita = _receita_da_oportunidade(crm, item)
        if not isinstance(receita, dict):
            continue
        try:
            aprovado = int(receita.get("aprovado_centavos") or 0)
        except (TypeError, ValueError):
            aprovado = 0
        if aprovado <= 0:
            continue
        aprovada_em = _aprovada_em(receita)
        if aprovada_em is not None and aprovada_em < desde:
            continue
        nome = _nome_do_contato(item)
        valor = _reais(receita.get("liquido_centavos", aprovado))
        avisar(
            Tipo.VENDA_ASSISTIDA,
            site_id=site,
            fato=fato,
            responsavel=str((item.get("titular") or {}).get("id") or item.get("titular_id") or ""),
            titulo=f"Venda aprovada: {nome}",
            texto=(
                f"O pagamento de {nome} foi aprovado"
                + (f" ({valor} líquido)" if valor else "")
                + ", numa oportunidade atendida pelo agente."
            ),
            link=link_da_oportunidade(oportunidade_id),
            enviar_agora=False,
        )
    return itens


def _mensagens_ja_lidas(chave: str, ultima_texto: str, ultima) -> bool:
    """A conversa não mudou desde a última leitura, e essa leitura já foi
    depois do prazo em que uma mensagem sem confirmação viraria aviso."""
    lida = _CONVERSAS_LIDAS.get(chave)
    return (
        lida is not None
        and lida[0] == ultima_texto
        and lida[1] >= ultima + timedelta(minutes=MINUTOS_DE_TOLERANCIA)
    )


def varrer_conversas(site_id: str, agora=None, perguntas: _PerguntasALeads | None = None) -> None:
    agora = agora or timezone.now()
    perguntas = perguntas or _PerguntasALeads()
    correio = _Correio()
    if not correio.ligado():
        return
    limite = agora - timedelta(minutes=MINUTOS_DE_TOLERANCIA)
    desde = agora - JANELA_DOS_FATOS

    # Só a passagem feita pelo agente (`assumida_por = "equipe"`) avisa: quem
    # clica em Assumir no painel já sabe, e não precisa de e-mail sobre isso.
    pedidas = correio.ler("/conversas", {"site_id": site_id, "estado": "pessoa", "ligacao": "todas", "por_pagina": 100})
    for conversa in _itens(pedidas):
        if conversa.get("estado") != "pessoa":
            continue
        if str(conversa.get("assumida_por") or "").strip().lower() != "equipe":
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        quando = _instante(conversa.get("assumida_em")) or _instante(conversa.get("ultima_mensagem_em"))
        if quando is None or quando < desde:
            continue
        marca = str(conversa.get("assumida_em") or "")
        if perguntas.conversa_de_teste(conversa) is not False:
            # De teste não avisa; sem saber (a `leads` não respondeu), espera a próxima volta.
            continue
        avisar(
            Tipo.PESSOA_PEDIDA,
            site_id=site_id,
            fato=f"conversa:{conversa_id}:{marca}",
            titulo="Uma conversa foi passada para a equipe",
            texto=(
                f"A conversa por {conversa.get('canal') or 'mensagem'} está com a equipe: "
                "o agente passou o atendimento para uma pessoa. "
                "O agente não responde enquanto ela estiver com vocês."
            ),
            link=link_da_conversa(conversa),
            enviar_agora=False,
        )

    ambiguas = correio.ler("/conversas", {"site_id": site_id, "ligacao": "ambigua", "por_pagina": 100})
    for conversa in _itens(ambiguas):
        if not (conversa.get("ambigua") or conversa.get("ligacao") == "ambigua"):
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        quando = _instante(conversa.get("ultima_mensagem_em")) or _instante(conversa.get("criada_em"))
        if quando is None or quando < desde:
            continue
        if perguntas.conversa_de_teste(conversa) is not False:
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
            enviar_agora=False,
        )

    recentes = correio.ler("/conversas", {"site_id": site_id, "ligacao": "todas", "por_pagina": CONVERSAS_POR_VOLTA})
    for conversa in _itens(recentes):
        ultima_texto = str(conversa.get("ultima_mensagem_em") or "")
        ultima = _instante(ultima_texto)
        if ultima is None or ultima < desde:
            continue
        conversa_id = str(conversa.get("id") or "")
        if not conversa_id:
            continue
        lida = f"{site_id}:{conversa_id}"
        if _mensagens_ja_lidas(lida, ultima_texto, ultima):
            continue
        mensagens = correio.ler(
            "/conversas/" + quote(conversa_id, safe="") + "/mensagens",
            {"site_id": site_id, "limite": 50},
        )
        if not isinstance(mensagens, dict):
            continue
        incertas = 0
        for mensagem in mensagens.get("mensagens") or []:
            if not isinstance(mensagem, dict):
                continue
            if mensagem.get("direcao") != "saida" or mensagem.get("estado_envio") != "desconhecido":
                continue
            quando = _instante(mensagem.get("ocorrida_em"))
            if quando is None or quando > limite or quando < desde:
                continue
            incertas += 1
        # Só pergunta quem é o lead quando há mesmo o que avisar. Sem saber (a
        # `leads` não respondeu), a conversa não fica como "lida": a próxima
        # volta lê de novo e tenta de novo.
        de_teste = perguntas.conversa_de_teste(conversa) if incertas else False
        if de_teste is None:
            continue
        if len(_CONVERSAS_LIDAS) >= _LIMITE_DAS_MEMORIAS:
            _CONVERSAS_LIDAS.clear()
        _CONVERSAS_LIDAS[lida] = (ultima_texto, agora)
        if not incertas or de_teste:
            continue
        # Um aviso por conversa: uma queda do provedor deixa várias mensagens
        # da mesma conversa sem confirmação, e é um problema só.
        canal = conversa.get("canal") or "mensagem"
        avisar(
            Tipo.ENVIO_INCERTO,
            site_id=site_id,
            fato=f"conversa:{conversa_id}:envio_incerto",
            responsavel=str(conversa.get("assumida_por") or ""),
            titulo="Mensagem sem confirmação de envio",
            texto=(
                (
                    f"Uma mensagem por {canal} saiu há mais de "
                    if incertas == 1
                    else f"{incertas} mensagens por {canal} saíram há mais de "
                )
                + f"{MINUTOS_DE_TOLERANCIA} minutos e o provedor não confirmou se chegaram. "
                "Elas não serão reenviadas sozinhas: confira a conversa antes de mandar de novo."
            ),
            link=link_da_conversa(conversa),
            enviar_agora=False,
        )


def _modelo_do_trabalho_comercial():
    """`comercial.TrabalhoComercial`, do coordenador. Sem ele, nada a varrer.

    É um `import`, e não `get_model` com o rótulo numa variável: no site o app
    se chama `admin_comercial`, e quem reescreve o rótulo na hora de montar o
    site (`preparar.py`) só enxerga texto literal e `import`."""
    try:
        from apps.comercial.models import TrabalhoComercial
    except ImportError:  # pragma: no cover - célula sem a equipe comercial
        return None
    return TrabalhoComercial


def _link_do_trabalho(trabalho) -> str:
    conversa = str(getattr(trabalho, "conversa_id", "") or "")
    if conversa:
        caminho = link_da_conversa({"id": conversa, "site_id": getattr(trabalho, "site_id", "")})
        if caminho != "/admin/crm/":
            return caminho
    oportunidade = str(getattr(trabalho, "oportunidade_id", "") or "")
    return link_da_oportunidade(oportunidade) if oportunidade else "/admin/crm/"


def varrer_trabalhos_comerciais(limite, desde=None, perguntas: _PerguntasALeads | None = None) -> None:
    """Trabalho comercial esperando o provedor ou o modelo além da tolerância
    vira `trabalho_parado`; trabalho com envio sem confirmação vira
    `envio_incerto`. Um aviso por trabalho e por estado (não por tentativa),
    com teto de avisos novos por volta. A análise horária do relógio não
    avisa: ela espera pela mesma causa dos outros trabalhos. Trabalho de teste
    não avisa: o marcado `teste` fica de fora na consulta, e o que o
    coordenador ainda não marcou é visto pelo que o evento trouxe e pelo
    contato na `leads` (sem saber, espera a próxima volta)."""
    perguntas = perguntas or _PerguntasALeads()
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
    if desde is not None:
        consulta = consulta.filter(**{campo_tempo + "__gte": desde})
    if "tipo" in campos:
        consulta = consulta.exclude(tipo=Modelo.Tipo.ANALISAR_RESULTADOS)
    if "teste" in campos:
        consulta = consulta.filter(teste=False)
    candidatos = []
    for trabalho in consulta.order_by("-pk")[:100]:
        estado = getattr(trabalho, campo_estado)
        candidatos.append((trabalho, estado, str(getattr(trabalho, "site_id", "") or ""), f"trabalho_comercial:{trabalho.pk}:{estado}"))
    novos = 0
    for tipo in set(tipos.values()):
        ja = _ja_avisados(tipo, [(site, fato) for _, estado, site, fato in candidatos if tipos[estado] == tipo])
        for trabalho, estado, site, fato in candidatos:
            if tipos[estado] != tipo or _chave(site, fato) in ja:
                continue
            if novos >= AVISOS_DE_TRABALHO_POR_VOLTA:
                return
            if perguntas.trabalho_de_teste(trabalho) is not False:
                continue
            motivo = str(getattr(trabalho, "motivo", "") or "")
            if tipo == Tipo.ENVIO_INCERTO:
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
            _, criado = avisar(
                tipo,
                site_id=site,
                fato=fato,
                titulo=titulo,
                texto=texto,
                link=_link_do_trabalho(trabalho),
                enviar_agora=False,
            )
            novos += 1 if criado else 0


def varrer_trabalhos_parados(agora=None, perguntas: _PerguntasALeads | None = None) -> None:
    agora = agora or timezone.now()
    limite = agora - timedelta(minutes=MINUTOS_DE_TOLERANCIA)
    desde = agora - JANELA_DOS_FATOS
    varrer_trabalhos_comerciais(limite, desde, perguntas)

    # Os trabalhos que o executor dos robôs já roda (leitura e conferência do
    # quiz, panorama) param do mesmo jeito quando a conexão com o modelo cai.
    try:
        Execucao = django_apps.get_model("agentes", "Execucao")
    except LookupError:
        return
    esperando = Execucao.objects.filter(
        situacao=Execucao.Situacao.AGUARDANDO_DEPENDENCIA,
        atualizada_em__lte=limite,
        atualizada_em__gte=desde,
    ).exclude(tipo=Execucao.Tipo.CONVERSA)
    candidatas = list(esperando.order_by("-pk")[:100])
    ja = _ja_avisados(Tipo.TRABALHO_PARADO, [("", f"execucao:{e.pk}") for e in candidatas])
    novos = 0
    for execucao in candidatas:
        fato = f"execucao:{execucao.pk}"
        if _chave("", fato) in ja:
            continue
        if novos >= AVISOS_DE_TRABALHO_POR_VOLTA:
            return
        responsavel = str(execucao.pedido_por_membro_id or "")
        _, criado = avisar(
            Tipo.TRABALHO_PARADO,
            fato=fato,
            responsavel=responsavel,
            titulo=f"Trabalho parado: {execucao.get_tipo_display()}",
            texto=(
                f"Este trabalho espera a conexão com o modelo há mais de {MINUTOS_DE_TOLERANCIA} minutos"
                + (f": {execucao.motivo[:200]}" if execucao.motivo else ".")
                + " Ele volta sozinho quando a conexão voltar."
            ),
            link=_rota(("execucao_do_robo",), [execucao.pk]) or "/admin/equipe/robo/",
            enviar_agora=False,
        )
        novos += 1 if criado else 0


def varrer(agora=None) -> None:
    """Uma volta: cada parte falha sozinha, sem levar as outras junto."""
    agora = agora or timezone.now()
    oportunidades: list[dict] = []
    try:
        oportunidades = varrer_vendas_assistidas(agora)
    except Exception:  # noqa: BLE001
        log.exception("Avisos da equipe: vendas assistidas")
    estado, dados = CRMClient().quadro(situacao="aberta", testes="ocultar", pagina=1, por_pagina=100)
    if estado == CRMClient.OK:
        oportunidades = oportunidades + list(dados.get("itens") or [])
    perguntas = _PerguntasALeads()
    sites = sites_conhecidos(oportunidades)
    for site in AvisoDaEquipe.objects.exclude(site_id="").values_list("site_id", flat=True).distinct()[:20]:
        if site not in sites:
            sites.append(site)
    for site in sites:
        try:
            varrer_conversas(site, agora, perguntas)
        except Exception:  # noqa: BLE001
            log.exception("Avisos da equipe: conversas do site %s", site)
    try:
        varrer_trabalhos_parados(agora, perguntas)
    except Exception:  # noqa: BLE001
        log.exception("Avisos da equipe: trabalhos parados")
    enviar_emails_pendentes(EMAILS_POR_VOLTA)


# ---------------------------------------------------------------------------
# As telas
# ---------------------------------------------------------------------------
def _membro(request) -> MembroDaEquipe | None:
    from .equipe import _membro_da_sessao

    return _membro_da_sessao(request)


def _e_administrador(request) -> bool:
    """Quem entrou com crachá de equipe só enxerga o painel da equipe."""
    return not request.admin.get("equipe_apenas")


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
    administrador = _e_administrador(request)
    avisos = list(consulta.order_by("-criado_em", "-id")[:200])
    for aviso in avisos:
        # O que esta pessoa pode ler e abrir (a de crachá de equipe não vê
        # nome nem valor de cliente, e só abre o que mora sob /equipe/).
        aviso.titulo_visivel, aviso.texto_visivel = conteudo_para(aviso, administrador)
        aviso.link_visivel = link_para(aviso, administrador)
        aviso.erro_visivel = aviso.email_erro if administrador and aviso.email_situacao != Email.PEDIDO else ""
    return render(
        request,
        "admin/equipe_avisos.html",
        {
            "admin": request.admin,
            "visao": "avisos",
            "mostrar": mostrar,
            "avisos": avisos,
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
    destino = request.POST.get("abrir") == "1" and link_para(aviso, _e_administrador(request))
    return HttpResponseRedirect(destino or reverse("avisos_da_equipe"))
