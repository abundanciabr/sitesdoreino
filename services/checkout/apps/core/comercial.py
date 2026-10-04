# apps/core/comercial.py
# O que o atendimento (admin/agentes do CRM) consulta e prepara no checkout:
# condições de compra que EXISTEM, link de compra rastreável e o estado
# confirmado do pagamento de um pedido.
#
# Tudo aqui é servidor a servidor, sob /interno/: o token público das páginas
# não alcança nenhuma destas rotas (apps/core/auth.py). O site vem do Host,
# como no resto da célula; pedido, link ou oferta de outro site é 404.
#
# Nada aqui cria preço, desconto ou prazo: preço vem do catálogo, parcelas da
# cotação do provedor, e o pedido só vira "pago" pelo aviso do provedor.
import json
import logging
import re
import uuid

import httpx
from django.conf import settings
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.http import JsonResponse
from ninja import Router
from ninja.errors import HttpError

from apps.core.clients import CatalogoClient, PagamentosClient
from apps.pedidos.atribuicao import separar_atribuicao
from apps.pedidos.models import CondicaoDoAgente, LinkDeCompra
from apps.pedidos.models import Order as OrderModel
from apps.pedidos.models import Session as SessionModel

router = Router()
logger = logging.getLogger(__name__)

MOEDA = "BRL"
# A cotação de parcelas do provedor é refeita no máximo a cada 2 minutos por
# (site, valor): o agente consulta as condições várias vezes por conversa.
CACHE_COTACAO_SEGUNDOS = 120
# O Pix que nasce pela Appmax ou com a segunda empresa ligada vence em 30 min
# (services/pagamentos: methods/pix/appmax.py e methods/pix/service.py). Fora
# dessas listas, quem define o prazo é o provedor, e aqui ele não é inventado.
PRAZO_PIX_MINUTOS = 30
# Hoje não existe cupom em lugar nenhum do site (catálogo, checkout ou
# pagamentos). A lista sai vazia até existir um de verdade.
CUPONS_EXISTENTES: tuple = ()


def valor_em_reais(centavos: int) -> str:
    inteiro, resto = divmod(int(centavos), 100)
    return f"R$ {inteiro:,}".replace(",", ".") + f",{resto:02d}"


def _corpo(request) -> dict:
    try:
        corpo = json.loads(request.body or b"{}")
    except ValueError:
        raise HttpError(422, "corpo não é JSON válido") from None
    if not isinstance(corpo, dict):
        raise HttpError(422, "corpo deve ser um objeto JSON")
    return corpo


def _texto(valor, campo: str, *, maximo: int, obrigatorio: bool = True) -> str:
    if valor is None and not obrigatorio:
        return ""
    if not isinstance(valor, str) or (obrigatorio and not valor.strip()):
        raise HttpError(422, f"{campo} é obrigatório (texto)")
    valor = valor.strip()
    if len(valor) > maximo:
        raise HttpError(422, f"{campo} aceita no máximo {maximo} caracteres")
    return valor


def _pix_minutos(site_id: str) -> int | None:
    listas = settings.APPMAX_PIX_ENABLED_SITES | settings.APPMAX_PIX_FALLBACK_SITES
    return PRAZO_PIX_MINUTOS if site_id in listas else None


def _cotacao_do_cartao(site_id: str, preco_cents: int) -> list | None:
    """As opções que o provedor do cartão cota para o preço. None quando a
    cotação não respondeu ou veio incoerente: "não sei" não vira opção.

    Só cotação boa fica guardada (120 s, por site e valor): a que falhou é
    tentada de novo na próxima consulta."""
    chave = f"checkout:cotacao:{site_id}:{preco_cents}"
    guardada = cache.get(chave)
    if guardada is not None:
        return [tuple(opcao) for opcao in guardada]
    opcoes = _cotar_no_provedor(preco_cents)
    if opcoes is not None:
        cache.set(chave, opcoes, CACHE_COTACAO_SEGUNDOS)
    return opcoes


def _cotar_no_provedor(preco_cents: int) -> list | None:
    try:
        cotacao = PagamentosClient().cotar_parcelas(amount_cents=preco_cents)
        if not isinstance(cotacao, dict) or cotacao.get("amount_cents") != preco_cents:
            return None
        opcoes = []
        for opcao in cotacao.get("options") or []:
            quantidade = opcao.get("installments") if isinstance(opcao, dict) else None
            total = opcao.get("total_cents") if isinstance(opcao, dict) else None
            if (
                type(quantidade) is not int
                or not 1 <= quantidade <= 12
                or type(total) is not int
                or total < preco_cents
            ):
                return None
            opcoes.append((quantidade, total))
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return None
    return sorted(set(opcoes)) or None


def condicoes_da_oferta(site: dict, oferta: dict) -> dict:
    """As condições de compra que existem agora para esta oferta neste site."""
    preco = int(oferta["price_cents"])
    pix_minutos = _pix_minutos(site["id"])
    condicoes = [
        {
            "id": "pix",
            "metodo": "pix",
            "parcelas": 1,
            "total_cents": preco,
            "parcela_cents": preco,
            "vencimento_minutos": pix_minutos,
        }
    ]
    metodos = ["pix"]
    consulta_parcelas = "sem_cartao"
    if site["id"] in settings.APPMAX_CARD_ENABLED_SITES:
        metodos.append("card")
        cotacao = _cotacao_do_cartao(site["id"], preco)
        if cotacao is None:
            consulta_parcelas = "indisponivel"
            # Sem cotação não há parcela que se possa prometer: fica só o
            # cartão à vista, cujo total é o próprio preço da oferta.
            cotacao = [(1, preco)]
        else:
            consulta_parcelas = "ok"
        for quantidade, total in cotacao:
            condicoes.append(
                {
                    "id": f"card_{quantidade}x",
                    "metodo": "card",
                    "parcelas": quantidade,
                    "total_cents": total,
                    "parcela_cents": (total + quantidade // 2) // quantidade,
                    "vencimento_minutos": None,
                }
            )
    maximo = max(
        (c["parcelas"] for c in condicoes if c["metodo"] == "card" and c["parcelas"]),
        default=None,
    )
    return {
        "site_id": site["id"],
        "oferta": {
            "slug": oferta["slug"],
            "oferta_ref": oferta["slug"],
            "versao": oferta.get("version"),
            "produto": oferta["product"]["name"],
            "preco_cents": preco,
            "preco": valor_em_reais(preco),
            "moeda": MOEDA,
            "bumps": [
                {
                    "id": str(bump["id"]),
                    "nome": bump["name"],
                    "preco_cents": int(bump["price_cents"]),
                }
                for bump in oferta.get("bumps") or []
            ],
        },
        "metodos": metodos,
        "condicoes": condicoes,
        "parcelas": {"consulta": consulta_parcelas, "maximo": maximo},
        "cupons": list(CUPONS_EXISTENTES),
        "vencimento_padrao": {"pix_minutos": pix_minutos, "card": None},
    }


def _oferta_ou_404(site: dict, slug: str) -> dict:
    oferta = CatalogoClient().obter_oferta(site["id"], slug)
    if oferta is None:
        raise HttpError(404, "oferta inexistente ou despublicada neste site")
    return oferta


@router.get(
    "/interno/ofertas/{slug}/condicoes",
    operation_id="getOfferPurchaseConditions",
    summary="Condições de compra que existem agora para uma oferta",
    include_in_schema=False,
)
def get_offer_purchase_conditions(request, slug: str):
    site = request.site
    return JsonResponse(condicoes_da_oferta(site, _oferta_ou_404(site, slug[:200])))


def _contato(bruto) -> dict:
    if bruto is None:
        return {}
    if not isinstance(bruto, dict):
        raise HttpError(422, "contato deve ser um objeto {nome, email, telefone}")
    contato = {}
    nome = _texto(bruto.get("nome"), "contato.nome", maximo=200, obrigatorio=False)
    if nome:
        contato["nome"] = " ".join(nome.split())
    email = _texto(bruto.get("email"), "contato.email", maximo=254, obrigatorio=False)
    if email:
        try:
            validate_email(email)
        except ValidationError:
            raise HttpError(422, "contato.email inválido") from None
        contato["email"] = email
    telefone = re.sub(r"\D", "", str(bruto.get("telefone") or ""))
    if telefone:
        if not 10 <= len(telefone) <= 13:
            raise HttpError(422, "contato.telefone deve ter DDD")
        contato["telefone"] = telefone
    return contato


def _resposta_existente(
    link: LinkDeCompra, *, oferta_ref: str, oportunidade_ref: str, condicao_id: str
) -> JsonResponse:
    """A mesma chave com o mesmo pedido devolve o link de sempre. A mesma chave
    com outra oferta, oportunidade ou condição é uso errado da chave: devolver o
    link antigo faria o atendimento mandar ao cliente algo diferente do que
    pediu."""
    if (
        link.oferta_ref != oferta_ref
        or link.oportunidade_ref != oportunidade_ref
        or (link.condicao or {}).get("id") != condicao_id
    ):
        raise HttpError(
            409,
            "chave_idempotencia já foi usada para outro link "
            f"(oferta {link.oferta_ref!r}, oportunidade {link.oportunidade_ref!r}, "
            f"condição {(link.condicao or {}).get('id')!r}); use uma chave nova",
        )
    return JsonResponse(link.resposta, status=200)


@router.post(
    "/interno/links-de-compra",
    operation_id="createPurchaseLink",
    summary="Prepara um link de compra rastreável para uma oportunidade",
    include_in_schema=False,
)
def create_purchase_link(request):
    site = request.site
    corpo = _corpo(request)
    chave = _texto(corpo.get("chave_idempotencia"), "chave_idempotencia", maximo=200)
    slug = _texto(corpo.get("oferta"), "oferta", maximo=200)
    oportunidade_ref = _texto(corpo.get("oportunidade_ref"), "oportunidade_ref", maximo=100)
    condicao_id = _texto(corpo.get("condicao"), "condicao", maximo=40)
    # O contato só é conferido (formato) e não é guardado: nada no checkout o
    # lê, e dado pessoal que ninguém usa não fica parado no banco.
    _contato(corpo.get("contato"))
    estrategia = _texto(corpo.get("estrategia"), "estrategia", maximo=100, obrigatorio=False)
    quiz = _texto(corpo.get("quiz"), "quiz", maximo=100, obrigatorio=False)
    tentativa = _texto(corpo.get("tentativa"), "tentativa", maximo=100, obrigatorio=False)
    mesmo_pedido = {
        "oferta_ref": slug,
        "oportunidade_ref": oportunidade_ref,
        "condicao_id": condicao_id,
    }
    existente = LinkDeCompra.objects.filter(
        site_id=site["id"], chave_idempotencia=chave
    ).first()
    if existente is not None:
        return _resposta_existente(existente, **mesmo_pedido)

    oferta = _oferta_ou_404(site, slug)
    condicoes = condicoes_da_oferta(site, oferta)
    condicao = next((c for c in condicoes["condicoes"] if c["id"] == condicao_id), None)
    if condicao is None:
        validas = ", ".join(c["id"] for c in condicoes["condicoes"])
        raise HttpError(
            422, f"condição {condicao_id!r} não existe agora para esta oferta; existem: {validas}"
        )
    # O agente só oferece o que o mantenedor marcou em /admin/crm/condicoes/.
    # A trava mora aqui, no servidor: a lista que o modelo viu pode estar velha
    # ou ele pode pedir um id que existe e não foi marcado.
    liberadas = set(
        CondicaoDoAgente.objects.filter(
            site_id=site["id"], oferta_slug=oferta["slug"]
        ).values_list("condicao_id", flat=True)
    )
    if condicao_id not in liberadas:
        raise HttpError(
            422,
            f"condição {condicao_id!r} não foi liberada para esta oferta; "
            f"liberadas: {', '.join(sorted(liberadas)) or 'nenhuma'}",
        )

    # A venda que sai deste link carrega de onde veio: a oportunidade (op), a
    # estratégia (est) e, quando o atendimento souber, o quiz (qz) e a
    # tentativa (qa) em `contexto`, que o pedido copia; e a origem (crm,
    # whatsapp, campanha) em `utm`.
    _, contexto = separar_atribuicao(
        {"op": oportunidade_ref, "est": estrategia, "qz": quiz, "qa": tentativa}
    )
    utm = {
        "src": "crm",
        "med": "whatsapp",
        "cpg": contexto.get("est") or oferta["slug"],
    }
    try:
        with transaction.atomic():
            sessao = SessionModel.objects.create(
                site_id=site["id"],
                offer_slug=oferta["slug"],
                offer=oferta,
                utm=utm,
                contexto=contexto,
            )
            link = LinkDeCompra.objects.create(
                site_id=site["id"],
                chave_idempotencia=chave,
                session=sessao,
                oferta_ref=oferta["slug"],
                oportunidade_ref=oportunidade_ref,
                condicao=condicao,
            )
            valor = condicao["total_cents"] or condicoes["oferta"]["preco_cents"]
            link.resposta = {
                "link_id": str(link.id),
                "url": f"https://{site['host']}/checkout/{oferta['slug']}/?link={link.id}",
                "pedido_id": str(link.pedido_id),
                "status": "aguardando_dados",
                "valor_cents": valor,
                "valor": valor_em_reais(valor),
                "moeda": MOEDA,
                # O link em si não vence. O Pix só nasce quando a pessoa
                # confirma os dados na página, e então vale o prazo abaixo.
                "vencimento": None,
                "vencimento_pix_minutos": condicao["vencimento_minutos"],
                "condicao": condicao,
                "oferta_ref": link.oferta_ref,
                "oportunidade_ref": oportunidade_ref,
                "criado_em": link.criado_em.isoformat(),
            }
            link.save(update_fields=["resposta"])
    except IntegrityError:
        # Duas chamadas com a mesma chave ao mesmo tempo: a segunda devolve o
        # link da primeira.
        existente = LinkDeCompra.objects.filter(
            site_id=site["id"], chave_idempotencia=chave
        ).first()
        if existente is None:
            raise
        return _resposta_existente(existente, **mesmo_pedido)
    return JsonResponse(link.resposta, status=201)


def registrar_divergencia_de_valor(link: LinkDeCompra, total_do_pedido_cents: int) -> bool:
    """O link anuncia um valor e o pedido nasce com o total do catálogo. Os dois
    nem sempre são iguais (cartão parcelado com juros do provedor, bump marcado
    na página). Quando diferem, fica no log, com os dois números rotulados."""
    valor_do_link = (link.resposta or {}).get("valor_cents")
    if valor_do_link == total_do_pedido_cents:
        return False
    logger.warning(
        "valor do link difere do total do pedido: link=%s oportunidade=%s "
        "condicao=%s valor_do_link_cents=%s total_do_pedido_cents=%s",
        link.id,
        link.oportunidade_ref,
        (link.condicao or {}).get("id"),
        valor_do_link,
        total_do_pedido_cents,
    )
    return True


def _estado_do_pedido(pedido: OrderModel, link: LinkDeCompra | None = None) -> dict:
    # `valor_cents` é o total do pedido (o que o catálogo cobra, com os bumps
    # marcados). O valor que o link anunciou ao cliente pode ser outro, por
    # exemplo o total do cartão parcelado: por isso os dois vêm rotulados.
    return {
        "pedido_id": str(pedido.id),
        "existe": True,
        "status": pedido.status,
        # Só o aviso do provedor põe o pedido em "pago" (consume_eventos).
        "confirmado": pedido.status in ("pago", "reembolsado"),
        "reembolsado": pedido.status == "reembolsado",
        "metodo": pedido.method,
        "valor_cents": pedido.total_cents,
        "total_do_pedido_cents": pedido.total_cents,
        "valor_do_link_cents": link.resposta.get("valor_cents") if link is not None else None,
        "moeda": MOEDA,
        "oportunidade_ref": pedido.oportunidade_ref,
        "oferta_ref": pedido.oferta_ref,
        "em_teste": pedido.em_teste,
        "criado_em": pedido.created_at.isoformat(),
        "pago_em": pedido.pago_em.isoformat() if pedido.pago_em else None,
    }


def _estado_do_link(link: LinkDeCompra) -> dict:
    return {
        "pedido_id": str(link.pedido_id),
        "existe": False,
        "status": "aguardando_dados",
        "confirmado": False,
        "reembolsado": False,
        "metodo": link.condicao.get("metodo"),
        "valor_cents": link.resposta.get("valor_cents"),
        # Ainda não há pedido: só existe o valor que o link anunciou.
        "valor_do_link_cents": link.resposta.get("valor_cents"),
        "total_do_pedido_cents": None,
        "moeda": MOEDA,
        "oportunidade_ref": link.oportunidade_ref,
        "oferta_ref": link.oferta_ref,
        "criado_em": link.criado_em.isoformat(),
        "pago_em": None,
        "url": link.resposta.get("url"),
    }


@router.get(
    "/interno/pedidos/{pedido_id}/pagamento",
    operation_id="getOrderPaymentState",
    summary="Estado do pagamento de um pedido, confirmado pelo provedor",
    include_in_schema=False,
)
def get_order_payment_state(request, pedido_id: str):
    site = request.site
    try:
        chave = uuid.UUID(pedido_id)
    except ValueError:
        raise HttpError(404, "pedido inexistente neste site") from None
    link = LinkDeCompra.objects.filter(pedido_id=chave, site_id=site["id"]).first()
    if link is not None:
        # O id do link responde pelo link inteiro: se a 1ª tentativa venceu e a
        # pessoa fez outra, vale a que o provedor confirmou, senão a última.
        tentativas = link.tentativas()
        if not tentativas:
            return JsonResponse(_estado_do_link(link))
        atual = next((p for p in reversed(tentativas) if p.status == "pago"), tentativas[-1])
        estado = _estado_do_pedido(atual, link)
        estado["pedido_id"] = str(chave)
        estado["pedido_atual_id"] = str(atual.id)
        return JsonResponse(estado)
    pedido = OrderModel.objects.filter(pk=chave, site_id=site["id"]).first()
    if pedido is not None:
        return JsonResponse(_estado_do_pedido(pedido))
    raise HttpError(404, "pedido inexistente neste site")


@router.get(
    "/interno/pedidos",
    operation_id="listOrdersByOpportunity",
    summary="Pedidos e links de uma oportunidade, com o total confirmado",
    include_in_schema=False,
)
def list_orders_by_opportunity(request, oportunidade_ref: str = ""):
    site = request.site
    referencia = oportunidade_ref.strip()[:100]
    if not referencia:
        raise HttpError(422, "oportunidade_ref é obrigatório")
    pedidos = list(
        OrderModel.objects.filter(site_id=site["id"], oportunidade_ref=referencia)
        .order_by("created_at")
    )
    com_pedido = {pedido.id for pedido in pedidos}
    todos_os_links = list(
        LinkDeCompra.objects.filter(
            site_id=site["id"], oportunidade_ref=referencia
        ).order_by("criado_em")
    )
    link_por_pedido = {link.pedido_id: link for link in todos_os_links}
    link_por_sessao = {link.session_id: link for link in todos_os_links}
    for reaberta in SessionModel.objects.filter(link_origem__in=todos_os_links):
        link_por_sessao[reaberta.pk] = reaberta.link_origem
    links = [link for link in todos_os_links if link.pedido_id not in com_pedido]
    # Pedido de sandbox/teste aparece na lista (marcado `em_teste`), mas não
    # entra no que foi recebido: só aparece contado em `testes_fora`.
    reais = [p for p in pedidos if not p.em_teste]
    aprovado = sum(p.total_cents for p in reais if p.status in ("pago", "reembolsado"))
    estornado = sum(p.total_cents for p in reais if p.status == "reembolsado")
    return JsonResponse(
        {
            "oportunidade_ref": referencia,
            "pedidos": [
                _estado_do_pedido(p, link_por_pedido.get(p.id) or link_por_sessao.get(p.session_id))
                for p in pedidos
            ]
            + [_estado_do_link(link) for link in links],
            "resumo": {
                "aprovado_cents": aprovado,
                "estornado_cents": estornado,
                "liquido_cents": aprovado - estornado,
                "testes_fora": len(pedidos) - len(reais),
                "moeda": MOEDA,
            },
        }
    )
