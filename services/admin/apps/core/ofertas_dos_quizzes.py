"""Qual oferta cada quiz e cada resultado levam, e o ajuste dessa ligação.

A ligação mora na célula do quiz (botão de cada faixa de resultado; nas
campanhas direcionadas, também o endereço de compra de cada oferta). Aqui só se
lê e se grava por ela: nenhuma cópia local. O nome e o preço da oferta vêm do
catálogo, perguntados a cada abertura da tela.
"""
import re
from urllib.parse import urlsplit

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro
from .clients import CatalogoClient
from .conteudos import _pedir, host_da_requisicao

APELIDO = re.compile(r"^[a-z0-9][a-z0-9-]{0,254}$")
CHECKOUT = re.compile(r"^/checkout/([a-z0-9-]+)/?$")
ROTULO_PADRAO = "Quero saber mais"


def _apelido_do_checkout(destino, host=""):
    """O apelido da oferta quando o botão leva ao checkout da plataforma.

    Endereço completo só conta se for do próprio site; o de outro domínio é externo,
    mesmo que o caminho se pareça com /checkout/<apelido>.
    """
    if not destino:
        return ""
    partes = urlsplit(destino)
    if partes.netloc and (not host or (partes.hostname or "").lower() != host):
        return ""
    achou = CHECKOUT.match(partes.path)
    return achou.group(1) if achou else ""


class _Ofertas:
    """Perguntas ao catálogo, uma vez por apelido e por abertura de tela."""

    def __init__(self, site_id, host=""):
        self.site_id = site_id
        self.host = (host or "").lower()
        self.vistas = {}

    def apelido(self, destino):
        return _apelido_do_checkout(destino, self.host)

    def consultar(self, apelido):
        if apelido not in self.vistas:
            if not self.site_id:
                self.vistas[apelido] = (CatalogoClient.NAO_RESPONDEU, None)
            else:
                self.vistas[apelido] = CatalogoClient().oferta_do_site(self.site_id, apelido)
        return self.vistas[apelido]


def _dinheiro(centavos):
    if not isinstance(centavos, int) or isinstance(centavos, bool):
        return ""
    reais, resto = divmod(centavos, 100)
    return "R$ " + f"{reais:,}".replace(",", ".") + f",{resto:02d}"


def _descrever(destino, ofertas):
    """O que o destino do botão significa, em palavras para a equipe."""
    if not destino:
        return {"tipo": "sem_oferta"}
    apelido = ofertas.apelido(destino)
    if not apelido:
        return {"tipo": "externa"}
    estado, dados = ofertas.consultar(apelido)
    if estado == CatalogoClient.OK:
        return {
            "tipo": "oferta", "apelido": apelido,
            "produto": dados["product"].get("name", ""),
            "preco": _dinheiro(dados.get("price_cents")),
        }
    if estado == "nao_existe":
        return {"tipo": "inexistente", "apelido": apelido}
    return {"tipo": "nao_conferida", "apelido": apelido}


def _preparar(quiz, ofertas, rascunho=None):
    quiz = dict(quiz)
    campos = (rascunho or {}).get(quiz["slug"], {})
    nome_das_ofertas = {o["id"]: o.get("nome", "") for o in quiz.get("ofertas", [])}
    faixas = []
    for numero, faixa in enumerate(quiz.get("faixas", [])):
        faixa = dict(faixa)
        faixa["numero"] = numero
        faixa["oferta"] = _descrever(faixa.get("destino", ""), ofertas)
        faixa["oferta_nome"] = nome_das_ofertas.get(faixa.get("oferta_id"), "")
        digitado = campos.get(faixa["key"])
        faixa["campo_destino"] = digitado[0] if digitado else faixa.get("destino", "")
        faixa["campo_rotulo"] = digitado[1] if digitado else faixa.get("rotulo", "")
        faixas.append(faixa)
    quiz["faixas"] = faixas
    quiz["sem_oferta"] = [f for f in faixas if f["oferta"]["tipo"] == "sem_oferta"]
    quiz["com_problema"] = [f for f in faixas if f["oferta"]["tipo"] == "inexistente"]
    quiz["precisa_de_atencao"] = bool(quiz["sem_oferta"] or quiz["com_problema"] or not faixas)
    quiz["publicado_sem_faixas"] = quiz.get("published") and not faixas
    quiz["ofertas_campanha"] = [
        dict(o, campo=campos.get(o["id"], (o.get("checkout_url", ""),))[0])
        for o in quiz.get("ofertas", [])
    ]
    return quiz


def _contexto(request, *, erro="", recado="", rascunho=None, com_erro=""):
    contexto = {"admin": request.admin, "erro": erro, "recado": recado, "quizzes": [],
                "site": {}, "resumo": {}, "com_erro": com_erro}
    status, dados = _pedir(request, "quiz", "GET", "ofertas")
    itens = dados.get("items") if isinstance(dados, dict) else None
    if status != 200 or not isinstance(itens, list):
        contexto["erro"] = erro or "Não consegui consultar os quizzes agora. Tente novamente em alguns instantes."
        contexto["indisponivel"] = True
        return contexto, 503
    site = CatalogoClient().site_por_host(host_da_requisicao(request)) or {}
    contexto["site"] = {"id": site.get("id", ""), "nome": site.get("name", ""), "host": host_da_requisicao(request)}
    ofertas = _Ofertas(site.get("id", ""), host_da_requisicao(request))
    quizzes = [_preparar(q, ofertas, rascunho) for q in itens if isinstance(q, dict) and q.get("slug")]
    contexto["quizzes"] = quizzes
    contexto["resumo"] = {
        "quizzes": len(quizzes),
        "sem_oferta": sum(1 for q in quizzes if q["precisa_de_atencao"]),
        "resultados_sem_oferta": sum(len(q["sem_oferta"]) for q in quizzes),
    }
    return contexto, 200


@require_GET
def ofertas_dos_quizzes(request):
    recado = "Ligação com a oferta salva." if request.GET.get("salvo") else ""
    contexto, status = _contexto(request, recado=recado)
    return render(request, "admin/crm_ofertas_dos_quizzes.html", contexto, status=status)


def _destino_digitado(texto):
    """Apelido da oferta vira o caminho do checkout; endereço completo fica como está."""
    texto = texto.strip()
    if APELIDO.match(texto):
        return f"/checkout/{texto}/"
    return texto


def _ler_faixas(request, quiz):
    """Lê o formulário de um quiz comum. Devolve (corpo, digitado, erro).

    Cada linha traz a chave da faixa (chave_<n>): a ligação vai para a faixa certa mesmo
    que o quiz tenha mudado depois de a tela abrir. Faixa que sumiu é ignorada e a que
    surgiu depois fica como está, sem ser esvaziada.
    """
    por_chave = {faixa["key"]: faixa for faixa in quiz["faixas"]}
    corpo, digitado = [], {}
    n = 0
    while f"chave_{n}" in request.POST:
        chave = request.POST[f"chave_{n}"]
        bruto = request.POST.get(f"destino_{n}", "").strip()
        rotulo = request.POST.get(f"rotulo_{n}", "").strip()
        n += 1
        faixa = por_chave.get(chave)
        if faixa is None or chave in digitado:
            continue
        destino = _destino_digitado(bruto)
        digitado[chave] = (bruto, rotulo)
        if destino and not rotulo:
            rotulo = ROTULO_PADRAO
        if rotulo and not destino:
            return None, digitado, f"O resultado “{faixa['titulo']}” tem texto de botão, mas falta a oferta. Preencha a oferta ou apague o texto."
        corpo.append({"key": chave, "destino": destino, "rotulo": rotulo})
    if not corpo:
        return None, digitado, "Este quiz mudou desde que a tela abriu. Nada foi alterado: recarregue a página e ajuste de novo."
    return {"faixas": corpo}, digitado, ""


def _ler_ofertas_da_campanha(request, quiz):
    corpo, digitado = {}, {}
    for oferta in quiz["ofertas_campanha"]:
        valor = request.POST.get(f"oferta_{oferta['id']}", "").strip()
        digitado[oferta["id"]] = (valor,)
        if not valor:
            return None, digitado, f"Informe o endereço de compra da oferta “{oferta.get('nome') or oferta['id']}”. Esta campanha precisa dos dois endereços."
        corpo[oferta["id"]] = valor
    return {"ofertas": corpo}, digitado, ""


def _conferir_no_catalogo(corpo, site_id, host=""):
    """Recusa só o que o catálogo confirma que não existe; falha de consulta não trava."""
    ofertas = _Ofertas(site_id, host)
    for faixa in corpo.get("faixas", []):
        apelido = ofertas.apelido(faixa["destino"])
        if apelido and ofertas.consultar(apelido)[0] == "nao_existe":
            return f"A oferta “{apelido}” não existe neste site. Confira o apelido no catálogo."
    return ""


@require_POST
def ofertas_dos_quizzes_salvar(request, slug):
    status, dados = _pedir(request, "quiz", "GET", slug, "ofertas")
    if status == 404:
        raise Http404("Quiz não encontrado")
    if status != 200 or not isinstance(dados, dict) or not isinstance(dados.get("faixas"), list):
        contexto, estado = _contexto(request, erro="Não consegui ler este quiz agora. Nada foi alterado.", com_erro=slug)
        return render(request, "admin/crm_ofertas_dos_quizzes.html", contexto, status=503)
    quiz = _preparar(dados, _Ofertas(""))
    if dados.get("directed"):
        corpo, digitado, erro = _ler_ofertas_da_campanha(request, quiz)
    else:
        corpo, digitado, erro = _ler_faixas(request, quiz)
    if not erro:
        site = CatalogoClient().site_por_host(host_da_requisicao(request)) or {}
        erro = _conferir_no_catalogo(corpo, site.get("id", ""), host_da_requisicao(request))
    if erro:
        contexto, estado = _contexto(request, erro=erro, rascunho={slug: digitado}, com_erro=slug)
        return render(request, "admin/crm_ofertas_dos_quizzes.html", contexto, status=422 if estado == 200 else estado)
    status, retorno = _pedir(request, "quiz", "PUT", slug, "ofertas", corpo=corpo)
    autor = str(request.admin.get("id") or request.admin.get("email") or "mantenedor")
    Registro.objects.create(
        quem_email=request.admin.get("email", ""), quem_id=autor[:64], acao=Registro.EDITAR,
        alvo=slug[:64],
        desfecho=Registro.OK if status == 200 else Registro.RECUSADO_PELA_CELULA if status == 422 else Registro.NAO_RESPONDEU,
        detalhe="CRM: oferta dos resultados do quiz",
    )
    if status == 200:
        return HttpResponseRedirect(reverse("crm_ofertas_dos_quizzes") + f"?salvo={slug}")
    if status == 422 and isinstance(retorno, dict) and isinstance(retorno.get("detail"), str):
        mensagem = retorno["detail"]
    elif status == 404:
        raise Http404("Quiz não encontrado")
    else:
        mensagem = "Não consegui confirmar que a alteração foi salva. Reabra a tela antes de tentar de novo."
    contexto, estado = _contexto(request, erro=mensagem, rascunho={slug: digitado}, com_erro=slug)
    return render(request, "admin/crm_ofertas_dos_quizzes.html", contexto, status=422 if status == 422 and estado == 200 else 503)
