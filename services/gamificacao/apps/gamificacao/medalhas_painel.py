"""Concessão manual, idempotente e sem bônus de XP ou moedas."""
import hashlib

from django.db import transaction

from apps.core.perfil import perfil_de
from .models import CelebracaoDeMedalha, Concessao, ConquistaDefinicao
from .validacao import conceder, ValidacaoRecusada


def colecao(pessoa_id, site_id):
    return CelebracaoDeMedalha.objects.select_related("concessao").filter(
        concessao__pessoa_id=pessoa_id, concessao__site_id=site_id,
    ).exclude(concessao__estado=Concessao.Estado.REVOGADA).order_by("-concessao__concedida_em")


def representar(item):
    return {
        "id": item.pk, "nome": item.nome, "mensagem": item.mensagem,
        "concedida_em": item.concessao.concedida_em.isoformat(),
        "vista": item.vista_em is not None,
    }


@transaction.atomic
def dar(*, site_id, pessoa_id, nome, mensagem, quem_id, referencia=""):
    nome, mensagem = " ".join(nome.split()), mensagem.strip()
    if not nome or len(nome) > 120 or not mensagem or len(mensagem) > 1000 or not quem_id.strip():
        raise ValueError("Preencha o nome da medalha e uma mensagem para o aluno.")
    chave = hashlib.sha256(nome.casefold().encode()).hexdigest()[:32]
    conquista, _ = ConquistaDefinicao.objects.get_or_create(
        site_id=site_id, slug="painel-" + chave,
        defaults={
            "nome": nome, "descricao": "Reconhecimento concedido pela equipe.",
            "classe": "medalha", "familia": "comunidade", "criterio": {"tipo": "manual"},
            "pontos": 0, "cristais": 0, "ativa": True,
        },
    )
    if conquista.pontos or conquista.cristais or conquista.classe != "medalha" or conquista.criterio != {"tipo": "manual"}:
        raise ValueError("Esta medalha não está disponível para concessão pelo painel.")
    perfil = perfil_de(pessoa_id, site_id)
    concessao, nova = conceder(
        pessoa=perfil.pessoa, site_id=site_id, conquista=conquista,
        validador_id=quem_id, validador_papel=Concessao.PapelDoValidador.ADMIN,
    )
    if concessao.estado == Concessao.Estado.REVOGADA:
        raise ValidacaoRecusada("Esta medalha foi retirada. Consulte o histórico de reconhecimentos.")
    item, _ = CelebracaoDeMedalha.objects.get_or_create(
        concessao=concessao, defaults={"nome": nome, "mensagem": mensagem, "referencia": referencia},
    )
    return item, nova
