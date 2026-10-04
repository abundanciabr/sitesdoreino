"""/admin/crm/condicoes/ — o mantenedor marca quais condições de compra o agente
do CRM pode oferecer.

As condições (Pix, parcelas do cartão, cupons) são as que o checkout já tem; esta
tela só deixa escolher entre elas. Nada aqui cria desconto, parcela ou prazo, e o
modelo também não: o agente recebe do checkout só o que foi marcado aqui, mais o
preço vigente da oferta. Cada site tem as suas marcas (o checkout acha o site
pelo endereço da página aberta).
"""
import os
from urllib.parse import quote

import httpx
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro
from .clients import http
from .conteudos import host_da_requisicao


class CondicoesClient:
    """Fala com o checkout (`/interno/condicoes-agente`), nunca com o banco dele."""

    OK = "ok"
    SEM_CONFIGURACAO = "sem-configuracao"
    NAO_RESPONDEU = "nao-respondeu"
    NAO_EXISTE = "nao-existe"
    RECUSADO = "recusado"

    def __init__(self, host: str):
        self.host = host

    def _pedir(self, metodo, caminho, *, params=None, corpo=None):
        base = (os.environ.get("CHECKOUT_API_URL") or "").strip().rstrip("/")
        token = (os.environ.get("CHECKOUT_API_TOKEN") or "").strip()
        if not base or not token:
            return self.SEM_CONFIGURACAO, None
        try:
            resposta = http().request(
                metodo,
                base + caminho,
                params={k: v for k, v in (params or {}).items() if v},
                json=corpo,
                headers={"Authorization": f"Bearer {token}", "Host": self.host},
                timeout=8.0,
            )
        except httpx.HTTPError:
            return self.NAO_RESPONDEU, None
        if resposta.status_code == 404:
            return self.NAO_EXISTE, None
        if resposta.status_code in (403, 409, 422):
            try:
                detalhe = resposta.json().get("detail")
            except (ValueError, AttributeError):
                detalhe = None
            return self.RECUSADO, detalhe if isinstance(detalhe, str) else "O checkout recusou a mudança."
        if resposta.status_code != 200:
            return self.NAO_RESPONDEU, None
        try:
            dados = resposta.json()
        except ValueError:
            return self.NAO_RESPONDEU, None
        return (self.OK, dados) if isinstance(dados, dict) else (self.NAO_RESPONDEU, None)

    def ofertas(self, oferta: str = ""):
        estado, dados = self._pedir("GET", "/interno/condicoes-agente", params={"oferta": oferta})
        if estado == self.OK and not isinstance(dados.get("ofertas"), list):
            return self.NAO_RESPONDEU, None
        return estado, dados

    def marcar(self, oferta: str, liberadas: list[str], autor: str):
        return self._pedir(
            "PUT",
            f"/interno/ofertas/{quote(oferta, safe='')}/condicoes-agente",
            corpo={"liberadas": liberadas, "autor": autor},
        )


def _aviso_da_fonte(estado):
    if estado == CondicoesClient.SEM_CONFIGURACAO:
        return "A conexão com o checkout ainda não está ligada neste ambiente."
    return "Não foi possível consultar o checkout agora. Tente novamente em alguns instantes."


def _legenda(item):
    """Texto simples de uma condição, só com o que o checkout informou."""
    if item.get("tipo") == "cupom":
        return f"Cupom {item.get('codigo')}"
    if item.get("metodo") == "pix":
        minutos = item.get("vencimento_minutos")
        return "Pix à vista" + (f", vence em {minutos} minutos" if minutos else "")
    parcelas = item.get("parcelas")
    if not parcelas:
        return "Cartão (parcelas não consultadas agora)"
    if parcelas == 1:
        return "Cartão à vista"
    return f"Cartão em {parcelas}x de {_reais(item.get('parcela_cents'))}"


def _reais(centavos):
    inteiro, resto = divmod(int(centavos or 0), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _preparar(oferta):
    oferta = dict(oferta)
    itens = []
    for item in oferta.get("itens") or []:
        itens.append(dict(item, legenda=_legenda(item), total=_reais(item.get("total_cents")) if item.get("total_cents") else ""))
    oferta["itens"] = itens
    return oferta


def _contexto(request, oferta_pedida="", erro="", recado=""):
    cliente = CondicoesClient(host_da_requisicao(request))
    estado, dados = cliente.ofertas(oferta_pedida)
    contexto = {"admin": request.admin, "ofertas": [], "erro": "", "recado": recado, "oferta_pedida": oferta_pedida}
    if estado != CondicoesClient.OK:
        contexto["erro"] = _aviso_da_fonte(estado)
        return contexto, 503
    contexto["ofertas"] = [_preparar(o) for o in dados["ofertas"] if isinstance(o, dict)]
    if erro:
        contexto["erro"] = erro
    return contexto, 200


@require_GET
def crm_condicoes(request):
    contexto, status = _contexto(
        request,
        request.GET.get("oferta", "").strip()[:200],
        recado="Condições salvas." if request.GET.get("salvo") == "1" else "",
    )
    return render(request, "admin/crm_condicoes.html", contexto, status=status)


@require_POST
def crm_condicoes_salvar(request):
    oferta = request.POST.get("oferta", "").strip()[:200]
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")
    if not oferta:
        contexto, status = _contexto(request, erro="Escolha a oferta que você quer ajustar.")
        return render(request, "admin/crm_condicoes.html", contexto, status=422 if status == 200 else status)
    liberadas = [i.strip() for i in request.POST.getlist("liberar") if i.strip()]
    estado, resultado = CondicoesClient(host_da_requisicao(request)).marcar(oferta, liberadas, autor)
    Registro.objects.create(
        quem_email=request.admin.get("email", ""),
        quem_id=autor[:64],
        acao=Registro.EDITAR,
        alvo=oferta[:200],
        desfecho=Registro.OK if estado == CondicoesClient.OK else Registro.RECUSADO_PELA_CELULA if estado in (CondicoesClient.RECUSADO, CondicoesClient.NAO_EXISTE) else Registro.NAO_RESPONDEU,
        detalhe="CRM: condições do agente (" + ", ".join(liberadas)[:200] + ")",
    )
    if estado == CondicoesClient.OK:
        return HttpResponseRedirect(reverse("crm_condicoes") + "?salvo=1")
    if estado == CondicoesClient.RECUSADO:
        erro = resultado
    elif estado == CondicoesClient.NAO_EXISTE:
        erro = "Essa oferta não existe ou não está publicada neste site."
    else:
        erro = "Não conseguimos confirmar que as condições foram salvas. Confira a lista antes de tentar de novo."
    contexto, status = _contexto(request, erro=erro)
    recusa = estado in (CondicoesClient.RECUSADO, CondicoesClient.NAO_EXISTE)
    return render(request, "admin/crm_condicoes.html", contexto, status=422 if recusa and status == 200 else 503)
