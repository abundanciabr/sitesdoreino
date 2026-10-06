"""`/admin/contatos/` e `/admin/contatos/<id>/` — quem são as pessoas da casa.

A primeira tela de CRM do painel (03/10/2026), só de LEITURA: a lista de
contatos, do mais novo para o mais antigo, com procura por nome, e-mail ou
telefone; e a ficha de cada um, com os dados, de onde veio, o que aceitou
receber e tudo o que fez na casa, em português.

## De onde sai cada dado

Da `leads`, pela API (`LeadsClient`), e nunca do banco dela: célula não lê
banco de outra. Esta tela não grava nada; contato, tag e histórico continuam
nascendo onde nasciam.

## Três respostas que só a primeira vista confunde

- **A `leads` não respondeu:** a tela diz o que houve e nenhuma lista aparece.
  Uma lista vazia ali diria que não há ninguém cadastrado.
- **Sem configuração:** o par de senhas entre esta célula e a `leads` ainda não
  foi escrito na VPS. A tela diz qual script roda e não finge lista vazia.
- **Vazio verdadeiro:** a `leads` respondeu e não há contato (ou nenhum casou
  com a procura). Esse zero é medido, e a frase diz qual dos dois é.

## A linha do tempo fala a língua da casa

O histórico da `leads` guarda o NOME TÉCNICO de cada evento (`pix.expirado`).
Aqui ele vira "Pix venceu sem pagar". Eventos ainda desconhecidos aparecem como
"Outra atividade", sem expor códigos internos ou o payload completo.

## Acesso

Nenhum código a mais: `apps/core/porta.py` é fail-CLOSED e tudo o que não está
nas exceções dela é só de administrador. `contatos/` fica DE FORA de `equipe/`
de propósito: a lista de contatos tem e-mail e telefone de cliente, e o
crachá da equipe não chega aqui.
"""

from __future__ import annotations

import uuid
from urllib.parse import urlencode

from django.http import Http404, HttpResponseRedirect
from django.shortcuts import render
from django.urls import reverse
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.views.decorators.http import require_GET, require_POST

from apps.auditoria.models import Registro

from . import ficha_do_contato as ficha_completa
from .clients import LeadsClient
from .nps_client import NPSClient
from .nps import preparar_avaliacoes

#: Quantos contatos por página. Cinquenta cabem em uma rolagem de celular sem
#: a tela virar um muro, e é o padrão que a própria `leads` usa.
POR_PAGINA = 50

#: Teto da página pedida no endereço: `?pagina=999999999999` não pode virar
#: conta absurda de deslocamento do outro lado.
PAGINA_MAXIMA = 10000

#: Nome do evento, como a `leads` o guarda, para o que a pessoa lê.
ROTULOS_DOS_EVENTOS = {
    "pedido.criado": "Fez pedido",
    "pagamento.aprovado": "Pagou",
    "pagamento.recusado": "Pagamento recusado",
    "pix.expirado": "Pix venceu sem pagar",
    "quiz.completado": "Respondeu o quiz",
    "quiz.captura_parcial": "Começou o quiz e deixou o contato",
    "lead.upsert": "Deixou o contato",
    "pagamento.reversao_confirmada": "Pagamento devolvido ou contestado",
    "aluno.matricula": "Matrícula na escola",
}

#: Forma de pagamento, como o checkout a manda.
ROTULOS_DAS_FORMAS = {"pix": "Pix", "card": "Cartão"}

#: O que a pessoa aceitou receber, como a `leads` guarda.
ROTULOS_DO_CONSENTIMENTO = {
    "email_marketing": "Novidades por e-mail",
    "whatsapp": "Mensagens por WhatsApp",
}

#: Quantos nomes de produto aparecem em um pedido antes do "e mais N".
PRODUTOS_VISIVEIS = 3


def rotulo_do_evento(nome) -> str:
    """O nome do evento em português, sem exibir códigos internos."""
    if not isinstance(nome, str) or not nome:
        return "Evento sem nome"
    return ROTULOS_DOS_EVENTOS.get(nome, "Outra atividade")


def _e_numero(valor) -> bool:
    # `bool` é subclasse de `int`: `True` não é um valor em dinheiro.
    return isinstance(valor, (int, float)) and not isinstance(valor, bool)


def dinheiro(centavos: int) -> str:
    """`49700` vira `R$ 497,00`; ponto nos milhares e vírgula nos centavos."""
    inteiro, resto = divmod(centavos, 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def valor_do_payload(payload) -> str:
    """O valor do evento já escrito, ou `""` se ele não traz nenhum.

    `total_cents` (pedido) e `amount_cents` (pagamento) são CENTAVOS inteiros,
    como o resto da casa guarda dinheiro. `valor`, quando aparece, é em REAIS:
    é como o lead escrito à mão pela API o traz. Negativo não é valor.
    """
    if not isinstance(payload, dict):
        return ""
    for chave in ("total_cents", "amount_cents"):
        centavos = payload.get(chave)
        if _e_numero(centavos) and centavos >= 0:
            return dinheiro(round(centavos))
    reais = payload.get("valor")
    if _e_numero(reais) and reais >= 0:
        return dinheiro(round(reais * 100))
    return ""


def produto_do_payload(payload) -> str:
    """O produto do evento, ou `""`: `produto`, os nomes dos itens, ou o código."""
    if not isinstance(payload, dict):
        return ""
    produto = payload.get("produto")
    if isinstance(produto, str) and produto.strip():
        return produto.strip()
    itens = payload.get("items")
    if isinstance(itens, list):
        nomes = [
            item["name"].strip()
            for item in itens
            if isinstance(item, dict)
            and isinstance(item.get("name"), str)
            and item["name"].strip()
        ]
        if nomes:
            texto = ", ".join(nomes[:PRODUTOS_VISIVEIS])
            sobram = len(nomes) - PRODUTOS_VISIVEIS
            return f"{texto} e mais {sobram}" if sobram > 0 else texto
    codigo = payload.get("product_id")
    if isinstance(codigo, str) and codigo.strip():
        return codigo.strip()
    return ""


def _forma_do_payload(payload) -> str:
    if not isinstance(payload, dict):
        return ""
    metodo = payload.get("method")
    if not isinstance(metodo, str) or not metodo:
        return ""
    return ROTULOS_DAS_FORMAS.get(metodo, "Outra forma")


def _data(texto):
    """A data ISO da `leads` como `datetime`, ou `None` se não for uma data."""
    if not isinstance(texto, str) or not texto:
        return None
    try:
        data = parse_datetime(texto)
        if data is None:
            return None
        if timezone.is_naive(data):
            data = timezone.make_aware(data, timezone.get_default_timezone())
        return timezone.localtime(data)
    except ValueError:
        return None


def _id(valor):
    """O id como UUID, ou `None`: id torto não vira link para uma ficha que 404."""
    try:
        return uuid.UUID(str(valor))
    except (ValueError, AttributeError):
        return None


def _texto(valor) -> str:
    return valor.strip() if isinstance(valor, str) else ""


def _tags(valor) -> list:
    if not isinstance(valor, list):
        return []
    return [tag for tag in valor if isinstance(tag, str) and tag]


def _pagina(texto) -> int:
    """A página pedida no endereço; lixo, zero ou negativo viram a primeira."""
    try:
        numero = int(texto)
    except (TypeError, ValueError):
        return 1
    return min(max(numero, 1), PAGINA_MAXIMA)


def _endereco(**parametros) -> str:
    """O link relativo da lista, só com o que foi pedido (`?q=ana&pagina=2`)."""
    pedidos = {nome: valor for nome, valor in parametros.items() if valor}
    return "?" + urlencode(pedidos) if pedidos else "?"


def montar_lista(
    desfecho, resposta, *, procurado="", pagina=1, site_id="", tag=""
) -> dict:
    """O que a lista mostra. Função pura: o desfecho entra, o dicionário sai.

    Qualquer desfecho que não seja `ok` devolve só o veredito: sem lista
    nenhuma, porque lista vazia aqui seria "não há ninguém".
    """
    if desfecho != LeadsClient.OK or resposta is None:
        return {"veredito": desfecho}
    itens = []
    for bruto in resposta.get("itens", []):
        if not isinstance(bruto, dict):
            continue
        nome = _texto(bruto.get("nome"))
        itens.append(
            {
                "id": _id(bruto.get("id")),
                "nome": nome or "Sem nome",
                "email": _texto(bruto.get("email")),
                "telefone": _texto(bruto.get("telefone")),
                "origem": _texto(bruto.get("origem")),
                "site_id": _texto(bruto.get("site_id")),
                "tags": _tags(bruto.get("tags")),
                "criado_em": _data(bruto.get("criado_em")),
                "ultimo_rotulo": (
                    rotulo_do_evento(bruto.get("ultimo_evento"))
                    if bruto.get("ultimo_evento")
                    else ""
                ),
                "ultimo_em": _data(bruto.get("ultimo_evento_em")),
            }
        )
    por_pagina = resposta.get("por_pagina")
    if not isinstance(por_pagina, int) or por_pagina < 1:
        por_pagina = POR_PAGINA
    total = resposta["total"]
    tem_mais = bool(resposta.get("tem_mais"))
    de = (pagina - 1) * por_pagina + 1
    filtros = {"q": procurado, "site_id": site_id, "tag": tag}
    return {
        "veredito": "ok",
        "itens": itens,
        "total": total,
        "pagina": pagina,
        "por_pagina": por_pagina,
        "tem_mais": tem_mais,
        "de": de,
        "ate": de + len(itens) - 1,
        # Página depois do fim: há contatos, mas não nesta página.
        "alem_do_fim": pagina > 1 and not itens and total > 0,
        "link_anterior": _endereco(**filtros, pagina=pagina - 1 if pagina > 2 else 0)
        if pagina > 1
        else "",
        "link_proxima": _endereco(**filtros, pagina=pagina + 1) if tem_mais else "",
        "link_primeira": _endereco(**filtros),
    }


def montar_ficha(resposta) -> dict:
    """O que a ficha mostra: dados, origem, consentimento e linha do tempo."""
    eventos = []
    for bruto in resposta.get("linha_do_tempo", []):
        if not isinstance(bruto, dict):
            continue
        payload = bruto.get("payload")
        eventos.append(
            {
                "rotulo": rotulo_do_evento(bruto.get("evento")),
                "quando": _data(bruto.get("ocorrido_em")),
                "valor": valor_do_payload(payload),
                "produto": produto_do_payload(payload),
                "forma": _forma_do_payload(payload),
            }
        )
    consentimento = resposta.get("consentimento")
    total = resposta.get("linha_do_tempo_total")
    if not isinstance(total, int):
        total = len(eventos)
    nome = _texto(resposta.get("nome"))
    return {
        "veredito": "ok",
        "id": _id(resposta.get("id")),
        "nome": nome or "Sem nome",
        "email": _texto(resposta.get("email")),
        "telefone": _texto(resposta.get("telefone")),
        "origem": _texto(resposta.get("origem")),
        "origem_identificada": resposta.get("origem_identificada") or {},
        "site_id": _texto(resposta.get("site_id")),
        "tags": _tags(resposta.get("tags")),
        "matriculas": [
            dict(m, situacao_nome={"ativa": "Aluno ativo", "encerrada": "Ex-aluno",
                                  "suspensa": "Acesso suspenso", "reembolsada": "Compra reembolsada"}.get(m.get("status"), ""))
            for m in resposta.get("matriculas", []) if isinstance(m, dict)
        ],
        "consentimento": [
            (ROTULOS_DO_CONSENTIMENTO[k], "Sim" if v is True else "Não")
            for k, v in sorted(consentimento.items())
            if k in ROTULOS_DO_CONSENTIMENTO and isinstance(v, bool)
        ]
        if isinstance(consentimento, dict)
        else [],
        "criado_em": _data(resposta.get("criado_em")),
        "atualizado_em": _data(resposta.get("atualizado_em")),
        "eventos": eventos,
        "total_eventos": total,
        # A `leads` entrega os mais recentes; o resto existe, e a tela diz.
        "eventos_cortados": total > len(eventos),
    }


@require_GET
def contatos(request):
    """A lista. Fail-OPEN, como o funil: ela abre e DIZ o que faltou."""
    procurado = (request.GET.get("q") or "").strip()[:120]
    site_id = (request.GET.get("site_id") or "").strip()[:100]
    tag = (request.GET.get("tag") or "").strip()[:100]
    pagina = _pagina(request.GET.get("pagina"))
    desfecho, resposta = LeadsClient().listar(
        q=procurado,
        site_id=site_id,
        tag=tag,
        pagina=pagina,
        por_pagina=POR_PAGINA,
    )
    if desfecho == LeadsClient.OK and resposta is None:
        desfecho = LeadsClient.NAO_RESPONDEU
    return render(
        request,
        "admin/contatos.html",
        {
            "admin": request.admin,
            "tela": montar_lista(
                desfecho,
                resposta,
                procurado=procurado,
                pagina=pagina,
                site_id=site_id,
                tag=tag,
            ),
            "procurado": procurado,
            "site_id": site_id,
            "tag": tag,
            "peneirando": bool(procurado or site_id or tag),
        },
        status=200 if desfecho == LeadsClient.OK else 503,
    )


@require_GET
def contato(request, lead_id):
    """A ficha de UMA pessoa. Id que não existe é 404; a `leads` fora do ar, não."""
    desfecho, resposta = LeadsClient().ficha(lead_id)
    if desfecho == LeadsClient.NAO_EXISTE:
        raise Http404("Contato inexistente")
    if desfecho == LeadsClient.OK and resposta is None:
        desfecho = LeadsClient.NAO_RESPONDEU
    if desfecho != LeadsClient.OK or resposta is None:
        tela = {"veredito": desfecho}
    else:
        tela = ficha_completa.completar_ficha(
            montar_ficha(resposta), resposta, host=request.get_host().split(":")[0].lower()
        )
    satisfacao_estado, satisfacao = ("sem-aluno", None)
    if tela.get("veredito") == "ok" and tela.get("site_id") and tela.get("email"):
        satisfacao_estado, satisfacao = NPSClient().historico(
            tela["site_id"], email=tela["email"]
        )
        if satisfacao_estado == NPSClient.OK and isinstance(satisfacao, dict) and isinstance(satisfacao.get("avaliacoes"), list):
            satisfacao = preparar_avaliacoes(satisfacao)
        else:
            satisfacao_estado, satisfacao = NPSClient.INDISPONIVEL, None
    recados = {
        "assumida": "Você assumiu a conversa. O assistente parou de responder.",
        "devolvida": "Conversa devolvida ao assistente da equipe. "
        "O robô responde a partir da próxima mensagem da pessoa.",
    }
    return render(
        request,
        "admin/contato.html",
        {
            "admin": request.admin,
            "tela": tela,
            "satisfacao_estado": satisfacao_estado,
            "satisfacao": satisfacao or {},
            "recado": recados.get(request.GET.get("atendimento", ""), ""),
            "aviso": _AVISO_DO_ESPELHO if request.GET.get("espelho") == "falhou" else "",
            "erro": _ERROS_DO_ATENDIMENTO.get(request.GET.get("erro", ""), ""),
        },
        status=200 if desfecho == LeadsClient.OK else 503,
    )


#: O que a ficha avisa quando a conversa mudou, mas o CRM não registrou quem atende.
_AVISO_DO_ESPELHO = (
    "A conversa mudou, mas o CRM não registrou quem atende agora. "
    "O quadro do CRM pode mostrar o atendente anterior."
)

#: O que a ficha diz quando assumir ou devolver não deu certo.
_ERROS_DO_ATENDIMENTO = {
    "conversa": "Esta conversa não é deste contato ou não existe mais.",
    "sem-configuracao": "A administração ainda não está ligada às conversas.",
    "sem-grau": "A administração ainda não tem permissão para mudar o atendimento.",
    "indisponivel": "A troca de atendimento ainda não está disponível.",
    "recusado": "As conversas recusaram a troca de atendimento.",
    "nao-respondeu": "As conversas não responderam. Recarregue e tente de novo.",
}


@require_POST
def contato_atendimento(request, lead_id):
    """Assumir ou devolver o atendimento da conversa deste contato.

    Quem decide se o agente fala é a `mensageria`. A conversa precisa ser
    deste contato: a lista é pedida de novo, aqui, com o site e o id da ficha.
    """
    gesto = request.POST.get("gesto", "")
    conversa_id = (request.POST.get("conversa_id") or "").strip()
    voltar = reverse("contato", args=[lead_id])
    if gesto not in ("assumir", "devolver"):
        return HttpResponseRedirect(voltar + "?erro=recusado")
    desfecho, resposta = LeadsClient().ficha(lead_id)
    if desfecho == LeadsClient.NAO_EXISTE:
        raise Http404("Contato inexistente")
    if desfecho != LeadsClient.OK or resposta is None:
        return HttpResponseRedirect(voltar + "?erro=nao-respondeu")
    site_id = _texto(resposta.get("site_id"))
    cliente = ficha_completa.ConversasClient()
    estado, conversas = cliente.conversas(site_id, str(lead_id))
    if estado != ficha_completa.OK:
        return HttpResponseRedirect(voltar + "?erro=" + estado)
    if conversa_id not in {str(c["id"]) for c in conversas}:
        return HttpResponseRedirect(voltar + "?erro=conversa")
    quem = str(request.admin.get("email") or request.admin.get("id") or "equipe")
    if gesto == "assumir":
        estado, _ = cliente.assumir(conversa_id, site_id, quem)
    else:
        estado, _ = cliente.devolver(conversa_id, site_id)
    Registro.objects.create(
        quem_email=request.admin.get("email", ""),
        quem_id=str(request.admin.get("id") or quem)[:64],
        acao=Registro.EDITAR,
        alvo=str(lead_id),
        desfecho=Registro.OK if estado == ficha_completa.OK
        else Registro.RECUSADO_PELA_CELULA if estado in (ficha_completa.RECUSADO, ficha_completa.SEM_GRAU)
        else Registro.NAO_RESPONDEU,
        detalhe=f"Atendimento: {gesto} a conversa {conversa_id}",
    )
    if estado != ficha_completa.OK:
        erro = {ficha_completa.NAO_EXISTE: "conversa"}.get(estado, estado)
        return HttpResponseRedirect(voltar + "?erro=" + erro)
    estado_crm, oportunidades = ficha_completa.oportunidades_do_contato(str(lead_id))
    espelhou = estado_crm == ficha_completa.OK and ficha_completa.marcar_atendimento_no_crm(
        oportunidades,
        tipo="pessoa" if gesto == "assumir" else "agente",
        nome=quem if gesto == "assumir" else "Assistente da equipe",
        autor=quem,
    )
    return HttpResponseRedirect(
        voltar + "?atendimento=" + ("assumida" if gesto == "assumir" else "devolvida")
        + ("" if espelhou else "&espelho=falhou")
    )
