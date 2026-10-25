"""Retirada administrativa reversível: evidências e créditos são preservados."""
from django.db import transaction
from .models import JornadaPessoal, RegistroDaJornada


def cortes(pessoa_id, site_id, caminho):
    resultado = {}
    for registro in RegistroDaJornada.objects.filter(
        pessoa_id=pessoa_id, site_id=site_id, acao="admin_remover",
    ).order_by("id"):
        dados = registro.dados
        if dados.get("caminho") in ("comum", caminho):
            ordens = range(7, 14) if dados.get("tipo") == "faixa" and dados["ordem"] == 7 else (dados["ordem"],)
            for ordem in ordens:
                resultado[ordem] = registro.criado_em
    return resultado


def remover(pessoa_id, site_id, ordem, tipo, ator, revisao):
    from .jornada import situacao
    if tipo not in ("etapa", "faixa") or type(ordem) is not int or not 2 <= ordem <= 13:
        raise ValueError("Escolha uma faixa ou etapa conquistada. A branca é o início da Trilha.")
    with transaction.atomic():
        j = JornadaPessoal.objects.select_for_update().filter(pessoa_id=pessoa_id, site_id=site_id).first()
        if not j:
            raise ValueError("Este aluno ainda não tem uma jornada registrada.")
        if j.revisao != revisao:
            raise ValueError("A Trilha mudou. Recarregue a página antes de remover.")
        antes = situacao(pessoa_id, site_id)
        if tipo == "faixa" and ordem >= 7:
            ordem = 7
        etapa = next((p for p in antes["lista"] if p["ordem"] == ordem), None)
        if not etapa or not etapa["alcancada"]:
            raise ValueError("Esta conquista já está ausente ou não pertence ao caminho atual.")
        registro = RegistroDaJornada.objects.create(pessoa_id=pessoa_id, site_id=site_id,
            acao="admin_remover", dados={"ordem": ordem, "tipo": tipo,
                "caminho": "comum" if ordem <= 4 else antes["caminho"],
                "ator": str(ator), "antes": antes["atual"]["ordem"]})
        j.revisao += 1
        j.celebracao_pendente = {}
        j.save(update_fields=["revisao", "celebracao_pendente", "atualizada_em"])
        depois = situacao(pessoa_id, site_id)
        return {"registro_id": registro.pk, "atual_ordem": depois["atual"]["ordem"]}
