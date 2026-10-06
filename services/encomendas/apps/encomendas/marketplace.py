"""Percurso de termos fechados da Fila do Dólar.

As operações recebem sempre o site e a identidade autenticada pelo chamador.
Esta modalidade não altera encomendas antigas nem executa uma cobrança.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta
import re
from uuid import UUID

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from . import motor, relogio
from .models import (
    AcordoMarketplace,
    AjusteMarketplace,
    ArquivoMarketplace,
    AutorizacaoMarketplaceAluno,
    AutorizacaoMarketplaceCliente,
    Encomenda,
    EntregaMarketplace,
    EventoMarketplace,
    FaseMarketplace,
    MensagemMarketplace,
    OfertaMarketplace,
    Oferta,
    OutboxMarketplace,
    PedidoMarketplace,
    PerfilProfissional,
    RecebivelMarketplace,
)


class ErroMarketplace(ValueError):
    """Gesto recusado sem modificar o pedido."""


def acesso_aluno(*, site_id: str, pessoa_id: str) -> bool:
    return (
        FaseMarketplace.objects.filter(site_id=site_id, alunos_liberados=True).exists()
        and AutorizacaoMarketplaceAluno.objects.filter(
            site_id=site_id, pessoa_id=pessoa_id, ativa=True
        ).exists()
    )


def acesso_cliente(*, site_id: str, cliente_id: str) -> bool:
    return (
        FaseMarketplace.objects.filter(site_id=site_id, clientes_liberados=True).exists()
        and AutorizacaoMarketplaceCliente.objects.filter(
            site_id=site_id, cliente_id=cliente_id, ativa=True
        ).exists()
    )


def autorizar_aluno(*, site_id: str, pessoa_id: str, ativa: bool, quem: str):
    """Seleção explícita da escola, independente de título e portfólio."""
    from .models import Pessoa

    if not Pessoa.objects.filter(pk=pessoa_id).exists():
        raise ErroMarketplace("pessoa desconhecida")
    with transaction.atomic():
        autorizacao, _ = AutorizacaoMarketplaceAluno.objects.select_for_update().get_or_create(
            site_id=site_id, pessoa_id=pessoa_id
        )
        autorizacao.ativa = bool(ativa)
        autorizacao.autorizada_por = quem
        autorizacao.autorizada_em = timezone.now()
        autorizacao.save()
        return autorizacao


def autorizar_cliente(*, site_id: str, cliente_id: str, ativa: bool, quem: str):
    if not cliente_id:
        raise ErroMarketplace("cliente obrigatório")
    with transaction.atomic():
        autorizacao, _ = AutorizacaoMarketplaceCliente.objects.select_for_update().get_or_create(
            site_id=site_id, cliente_id=cliente_id
        )
        autorizacao.ativa = bool(ativa)
        autorizacao.autorizada_por = quem
        autorizacao.autorizada_em = timezone.now()
        autorizacao.save()
        return autorizacao


def configurar_fase(
    *, site_id: str, quem: str, alunos_liberados: bool | None = None,
    clientes_liberados: bool | None = None,
):
    """Uso administrativo; nenhum participante é selecionado por esta função."""
    if not quem:
        raise ErroMarketplace("autor administrativo obrigatório")
    with transaction.atomic():
        fase, _ = FaseMarketplace.objects.select_for_update().get_or_create(site_id=site_id)
        if alunos_liberados is not None:
            fase.alunos_liberados = bool(alunos_liberados)
        if clientes_liberados is not None:
            fase.clientes_liberados = bool(clientes_liberados)
        fase.save()
        return fase


def _pedido(site_id: str, pedido_id, *, trava: bool = False) -> PedidoMarketplace:
    consulta = PedidoMarketplace.objects.filter(pk=pedido_id, site_id=site_id)
    if trava:
        consulta = consulta.select_for_update()
    pedido = consulta.first()
    if pedido is None:
        raise ErroMarketplace("pedido não encontrado neste site")
    return pedido


def _cliente(pedido: PedidoMarketplace, cliente_id: str):
    if pedido.cliente_id != cliente_id or not acesso_cliente(
        site_id=pedido.site_id, cliente_id=cliente_id
    ):
        raise ErroMarketplace("cliente sem acesso a este pedido")


def _aluno(pedido: PedidoMarketplace, pessoa_id: str):
    if (
        pedido.aluno_id is None
        or pedido.aluno.pessoa_id != pessoa_id
        or not acesso_aluno(site_id=pedido.site_id, pessoa_id=pessoa_id)
    ):
        raise ErroMarketplace("aluno sem acesso a este pedido")


def _evento(pedido: PedidoMarketplace, tipo: str, sufixo: str, dados: dict | None = None):
    with transaction.atomic():
        evento, criado = EventoMarketplace.objects.get_or_create(
            chave=f"{pedido.pk}:{tipo}:{sufixo}",
            defaults={
                "site_id": pedido.site_id,
                "pedido": pedido,
                "tipo": tipo,
                "dados": dados or {},
            },
        )
        if criado:
            assunto, versao = tipo.rsplit(".v", 1)
            OutboxMarketplace.objects.create(
                site_id=pedido.site_id, evento=evento,
                event=assunto, version=int(versao),
                payload={
                    "site_id": pedido.site_id,
                    "pedido_id": str(pedido.pk),
                    **(dados or {}),
                },
            )
        return evento


_CAMPOS_RASCUNHO = {
    "cartao", "categoria", "titulo", "briefing", "valor_cents", "moeda",
    "prazo_quantidade", "prazo_unidade", "ajustes_inclusos", "ambiente",
}
_CAMPOS_DO_BRIEFING = {
    "quantidade", "modelos", "variacoes", "destino", "plataforma", "entregaveis",
    "observacoes", "referencias", "estilo",
}


def salvar_rascunho(
    *, site_id: str, cliente_id: str, dados: dict, pedido_id=None
) -> PedidoMarketplace:
    if not acesso_cliente(site_id=site_id, cliente_id=cliente_id):
        raise ErroMarketplace("cliente não autorizado neste site")
    if not isinstance(dados, dict):
        raise ErroMarketplace("dados inválidos")
    with transaction.atomic():
        pedido = (
            _pedido(site_id, pedido_id, trava=True)
            if pedido_id else PedidoMarketplace(site_id=site_id, cliente_id=cliente_id)
        )
        if pedido.cliente_id != cliente_id or pedido.status != PedidoMarketplace.Status.RASCUNHO:
            raise ErroMarketplace("rascunho indisponível")
        briefing = dict(pedido.briefing or {})
        if "briefing" in dados:
            if not isinstance(dados["briefing"], dict):
                raise ErroMarketplace("briefing inválido")
            briefing.update(dados["briefing"])
        briefing.update({k: dados[k] for k in _CAMPOS_DO_BRIEFING if k in dados})
        pedido.briefing = briefing
        for campo in _CAMPOS_RASCUNHO - {"briefing"}:
            if campo in dados:
                setattr(pedido, campo, dados[campo])
        if pedido.cartao:
            pedido.nivel = Encomenda.NIVEL_DO_CARTAO.get(pedido.cartao, "")
        pedido.versao += 1 if pedido_id else 0
        pedido.full_clean()
        pedido.save()
        return pedido


def repetir_pedido(*, site_id: str, cliente_id: str, pedido_id) -> PedidoMarketplace:
    original = _pedido(site_id, pedido_id)
    _cliente(original, cliente_id)
    return salvar_rascunho(
        site_id=site_id, cliente_id=cliente_id,
        dados={
            "cartao": original.cartao, "categoria": original.categoria,
            "titulo": original.titulo, "briefing": original.briefing,
            "valor_cents": original.valor_cents, "moeda": original.moeda,
            "prazo_quantidade": original.prazo_quantidade,
            "prazo_unidade": original.prazo_unidade,
            "ajustes_inclusos": original.ajustes_inclusos,
            "ambiente": original.ambiente,
        },
    )


def _validar_publicacao(pedido: PedidoMarketplace):
    b = pedido.briefing
    if pedido.cartao not in Encomenda.NIVEL_DO_CARTAO:
        raise ErroMarketplace("cartão obrigatório")
    if pedido.categoria not in {"espadas_objetos", "pets", "cabelos", "chapeus", "personagens"} or not pedido.titulo.strip():
        raise ErroMarketplace("categoria e título obrigatórios")
    if not isinstance(b, dict) or not isinstance(b.get("quantidade"), int) or b["quantidade"] < 1:
        raise ErroMarketplace("quantidade obrigatória")
    if not isinstance(b.get("modelos"), list) or not b["modelos"]:
        raise ErroMarketplace("modelos obrigatórios")
    if not isinstance(b.get("entregaveis"), list) or not b["entregaveis"]:
        raise ErroMarketplace("entregáveis obrigatórios")
    if "animacao" in b["entregaveis"]:
        raise ErroMarketplace("animação não está disponível nesta fila")
    if not isinstance(pedido.valor_cents, int) or pedido.valor_cents < 100 or pedido.valor_cents % 100:
        raise ErroMarketplace("valor oferecido deve ser em créditos inteiros de R$ 1")
    if pedido.moeda != "BRL" or pedido.ambiente != "sandbox":
        raise ErroMarketplace("moeda ou ambiente indisponível")
    if pedido.prazo_quantidade < 1 or pedido.prazo_unidade not in PedidoMarketplace.PrazoUnidade.values:
        raise ErroMarketplace("prazo de produção inválido")
    if pedido.ajustes_inclusos < 0:
        raise ErroMarketplace("ajustes inválidos")


def publicar_pedido(
    *, site_id: str, cliente_id: str, pedido_id, versao: int
) -> PedidoMarketplace:
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        _cliente(pedido, cliente_id)
        if pedido.versao != versao:
            raise ErroMarketplace("versão do pedido mudou")
        if pedido.status != PedidoMarketplace.Status.RASCUNHO:
            return pedido  # repetição do mesmo clique; nenhuma segunda cobrança
        _validar_publicacao(pedido)
        pedido.status = PedidoMarketplace.Status.AGUARDANDO_PAGAMENTO
        pedido.publicado_em = timezone.now()
        pedido.save(update_fields=["status", "publicado_em", "atualizado_em"])
        _evento(pedido, "marketplace.pedido_publicado.v1", str(versao), {
            "valor_cents": pedido.valor_cents, "moeda": pedido.moeda,
            "ambiente": pedido.ambiente,
        })
        return pedido


def confirmar_pagamento(
    *, site_id: str, pedido_id, versao: int, valor_cents: int,
    moeda: str, ambiente: str, referencia: str,
) -> PedidoMarketplace:
    """Porta interna chamada somente após o adaptador verificar o provedor."""
    if not referencia or len(referencia) > 160:
        raise ErroMarketplace("referência de pagamento inválida")
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        if (
            pedido.versao != versao or pedido.valor_cents != valor_cents
            or pedido.moeda != moeda or pedido.ambiente != ambiente
        ):
            raise ErroMarketplace("confirmação não corresponde aos termos publicados")
        if pedido.pagamento_referencia:
            if pedido.pagamento_referencia != referencia:
                raise ErroMarketplace("pedido já tem outra confirmação")
            return pedido
        if pedido.status != PedidoMarketplace.Status.AGUARDANDO_PAGAMENTO:
            raise ErroMarketplace("pedido não aguarda pagamento")
        if PedidoMarketplace.objects.filter(pagamento_referencia=referencia).exclude(pk=pedido.pk).exists():
            raise ErroMarketplace("referência já usada em outro pedido")
        pedido.pagamento_referencia = referencia
        pedido.pagamento_confirmado_em = timezone.now()
        pedido.status = PedidoMarketplace.Status.NA_FILA
        pedido.save(update_fields=[
            "pagamento_referencia", "pagamento_confirmado_em", "status", "atualizado_em"
        ])
        _evento(pedido, "marketplace.pagamento_confirmado.v1", referencia, {
            "referencia": referencia, "valor_cents": valor_cents,
            "moeda": moeda, "ambiente": ambiente,
        })
        return pedido


def _candidatos_v2(site_id: str):
    permitidos = set(AutorizacaoMarketplaceAluno.objects.select_for_update().filter(
        site_id=site_id, ativa=True,
    ).values_list("pessoa_id", flat=True))
    perfis = dict(PerfilProfissional.objects.filter(site_id=site_id).values_list("id", "pessoa_id"))
    pendentes = set(OfertaMarketplace.objects.filter(
        site_id=site_id, status=OfertaMarketplace.Status.PENDENTE,
    ).values_list("aluno_id", flat=True))
    return tuple(
        replace(c, tem_oferta_pendente=c.tem_oferta_pendente or c.perfil_id in pendentes)
        for c in motor.candidatos_do_banco(site_id)
        if perfis.get(c.perfil_id) in permitidos
    )


def distribuir_pedido(
    *, site_id: str, pedido_id, agora: datetime | None = None
) -> OfertaMarketplace | None:
    agora = agora or timezone.now()
    with transaction.atomic():
        fase = FaseMarketplace.objects.select_for_update().filter(site_id=site_id).first()
        if not fase or not fase.alunos_liberados:
            return None
        pedido = _pedido(site_id, pedido_id, trava=True)
        if pedido.status == PedidoMarketplace.Status.OFERECIDO:
            return OfertaMarketplace.objects.filter(
                pedido=pedido, status=OfertaMarketplace.Status.PENDENTE,
            ).first()
        if pedido.status != PedidoMarketplace.Status.NA_FILA or not pedido.pagamento_confirmado_em:
            return None
        vistos = frozenset(OfertaMarketplace.objects.filter(pedido=pedido).values_list("aluno_id", flat=True))
        vaga = motor.Vaga(encomenda_id=pedido.pk, nivel=pedido.nivel, ja_ofertada_a=vistos)
        regras = motor.Regras.do_banco(agora, site_id=site_id)
        escolha = motor.escolher(vaga, _candidatos_v2(site_id), regras, agora)
        if escolha.escolhido is None:
            return None
        perfil = PerfilProfissional.objects.select_for_update().get(
            pk=escolha.escolhido.perfil_id, site_id=site_id,
        )
        if (
            not acesso_aluno(site_id=site_id, pessoa_id=perfil.pessoa_id)
            or Oferta.objects.filter(
                site_id=site_id, aluno=perfil, resultado=Oferta.Resultado.PENDENTE,
            ).exists()
            or OfertaMarketplace.objects.filter(
                site_id=site_id, aluno=perfil, status=OfertaMarketplace.Status.PENDENTE,
            ).exists()
        ):
            return None
        candidato_atual = next(
            (c for c in motor.candidatos_do_banco(site_id) if c.perfil_id == perfil.pk), None
        )
        if candidato_atual is None or motor.por_que_nao(vaga, candidato_atual, regras, agora):
            return None
        expira_em = relogio.calcular_expiracao(agora, site_id=site_id)
        try:
            with transaction.atomic():
                oferta = OfertaMarketplace.objects.create(
                    site_id=site_id, pedido=pedido, aluno_id=escolha.escolhido.perfil_id,
                    versao_pedido=pedido.versao, oferecida_em=agora, expira_em=expira_em,
                )
        except IntegrityError:
            # Outra encomenda reservou a única oferta pendente do aluno.
            return None
        pedido.status = PedidoMarketplace.Status.OFERECIDO
        pedido.save(update_fields=["status", "atualizado_em"])
        _evento(pedido, "marketplace.oferta_criada.v1", str(oferta.pk), {
            "oferta_id": str(oferta.pk), "aluno_id": oferta.aluno_id,
        })
        return oferta


def rodar_marketplace(*, site_id: str, agora: datetime | None = None) -> int:
    agora = agora or timezone.now()
    expirar_ofertas(site_id=site_id, agora=agora)
    total = 0
    ids = list(PedidoMarketplace.objects.filter(
        site_id=site_id, status=PedidoMarketplace.Status.NA_FILA,
        pagamento_confirmado_em__isnull=False,
    ).order_by("criado_em").values_list("pk", flat=True))
    for pedido_id in ids:
        if distribuir_pedido(site_id=site_id, pedido_id=pedido_id, agora=agora):
            total += 1
    return total


def expirar_ofertas(*, site_id: str, agora: datetime | None = None) -> int:
    agora = agora or timezone.now()
    ids = list(OfertaMarketplace.objects.filter(
        site_id=site_id, status=OfertaMarketplace.Status.PENDENTE, expira_em__lte=agora,
    ).values_list("pk", flat=True))
    expiradas = 0
    for oferta_id in ids:
        with transaction.atomic():
            pedido_id = OfertaMarketplace.objects.filter(
                pk=oferta_id, site_id=site_id,
            ).values_list("pedido_id", flat=True).first()
            if pedido_id is None:
                continue
            pedido = _pedido(site_id, pedido_id, trava=True)
            oferta = OfertaMarketplace.objects.select_for_update().filter(
                pk=oferta_id, site_id=site_id,
            ).first()
            if not oferta or oferta.status != OfertaMarketplace.Status.PENDENTE:
                continue
            oferta.status = OfertaMarketplace.Status.EXPIROU
            oferta.respondida_em = agora
            oferta.save(update_fields=["status", "respondida_em"])
            if pedido.status == PedidoMarketplace.Status.OFERECIDO:
                pedido.status = PedidoMarketplace.Status.NA_FILA
                pedido.save(update_fields=["status", "atualizado_em"])
            _evento(pedido, "marketplace.oferta_expirou.v1", str(oferta.pk))
            expiradas += 1
    return expiradas


def _prazo_final(pedido: PedidoMarketplace, inicio: datetime) -> datetime:
    dias = pedido.prazo_quantidade
    if pedido.prazo_unidade == PedidoMarketplace.PrazoUnidade.DIAS_CORRIDOS:
        return inicio + timedelta(days=dias)
    if pedido.prazo_unidade != PedidoMarketplace.PrazoUnidade.DIAS_UTEIS:
        raise ErroMarketplace("unidade de prazo inválida")
    # Dias úteis aqui são segunda a sexta. O acordo conserva a unidade original.
    fim = inicio
    while dias:
        fim += timedelta(days=1)
        if fim.weekday() < 5:
            dias -= 1
    return fim


def aceitar_oferta(
    *, site_id: str, pessoa_id: str, oferta_id, agora: datetime | None = None
) -> AcordoMarketplace:
    agora = agora or timezone.now()
    with transaction.atomic():
        pedido_id = OfertaMarketplace.objects.filter(
            pk=oferta_id, site_id=site_id,
        ).values_list("pedido_id", flat=True).first()
        if pedido_id is None:
            raise ErroMarketplace("oferta indisponível")
        pedido = _pedido(site_id, pedido_id, trava=True)
        oferta = OfertaMarketplace.objects.select_for_update().filter(pk=oferta_id, site_id=site_id).first()
        if oferta is None or oferta.aluno.pessoa_id != pessoa_id:
            raise ErroMarketplace("oferta indisponível")
        if not acesso_aluno(site_id=site_id, pessoa_id=pessoa_id):
            raise ErroMarketplace("aluno sem autorização")
        if oferta.status == OfertaMarketplace.Status.ACEITA:
            return AcordoMarketplace.objects.get(oferta=oferta)
        if (
            oferta.status != OfertaMarketplace.Status.PENDENTE
            or pedido.status != PedidoMarketplace.Status.OFERECIDO
            or oferta.expira_em <= agora or oferta.versao_pedido != pedido.versao
            or not pedido.pagamento_confirmado_em
        ):
            raise ErroMarketplace("oferta encerrada ou termos alterados")
        perfil = PerfilProfissional.objects.select_for_update().get(pk=oferta.aluno_id, site_id=site_id)
        if perfil.disponibilidade != PerfilProfissional.Disponibilidade.DISPONIVEL:
            raise ErroMarketplace("aluno indisponível")
        candidatos = motor.candidatos_do_banco(site_id)
        candidato = next((c for c in candidatos if c.perfil_id == perfil.pk), None)
        pendente_alheia = (
            Oferta.objects.filter(
                site_id=site_id, aluno=perfil, resultado=Oferta.Resultado.PENDENTE,
            ).exists()
            or OfertaMarketplace.objects.filter(
                site_id=site_id, aluno=perfil, status=OfertaMarketplace.Status.PENDENTE,
            ).exclude(pk=oferta.pk).exists()
        )
        if candidato is None:
            raise ErroMarketplace("perfil indisponível")
        candidato = replace(candidato, tem_oferta_pendente=pendente_alheia)
        vaga = motor.Vaga(encomenda_id=pedido.pk, nivel=pedido.nivel)
        if motor.por_que_nao(
            vaga, candidato, motor.Regras.do_banco(agora, site_id=site_id), agora,
        ):
            raise ErroMarketplace("aluno não está tecnicamente elegível")
        termos = {
            "cartao": pedido.cartao, "categoria": pedido.categoria,
            "titulo": pedido.titulo, "briefing": pedido.briefing,
            "valor_cents": pedido.valor_cents, "moeda": pedido.moeda,
            "prazo_quantidade": pedido.prazo_quantidade,
            "prazo_unidade": pedido.prazo_unidade,
            "ajustes_inclusos": pedido.ajustes_inclusos,
        }
        acordo = AcordoMarketplace.objects.create(
            site_id=site_id, pedido=pedido, oferta=oferta, aluno=perfil,
            versao_pedido=pedido.versao, termos=termos, aceito_em=agora,
        )
        oferta.status = OfertaMarketplace.Status.ACEITA
        oferta.respondida_em = agora
        oferta.save(update_fields=["status", "respondida_em"])
        pedido.aluno = perfil
        pedido.status = PedidoMarketplace.Status.EM_PRODUCAO
        pedido.producao_iniciada_em = agora
        pedido.producao_prazo_ate = _prazo_final(pedido, agora)
        pedido.save(update_fields=[
            "aluno", "status", "producao_iniciada_em", "producao_prazo_ate", "atualizado_em"
        ])
        perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.TRABALHANDO)
        _evento(pedido, "marketplace.acordo_aceito.v1", str(oferta.pk), {
            "oferta_id": str(oferta.pk), "versao": pedido.versao,
        })
        return acordo


def passar_oferta(
    *, site_id: str, pessoa_id: str, oferta_id, motivo: str = "",
    agora: datetime | None = None,
) -> PedidoMarketplace:
    agora = agora or timezone.now()
    with transaction.atomic():
        pedido_id = OfertaMarketplace.objects.filter(
            pk=oferta_id, site_id=site_id,
        ).values_list("pedido_id", flat=True).first()
        if pedido_id is None:
            raise ErroMarketplace("oferta indisponível")
        pedido = _pedido(site_id, pedido_id, trava=True)
        oferta = OfertaMarketplace.objects.select_for_update().filter(pk=oferta_id, site_id=site_id).first()
        if oferta is None or oferta.aluno.pessoa_id != pessoa_id:
            raise ErroMarketplace("oferta indisponível")
        if not acesso_aluno(site_id=site_id, pessoa_id=pessoa_id):
            raise ErroMarketplace("aluno sem autorização")
        if oferta.status == OfertaMarketplace.Status.PASSOU:
            return pedido
        if oferta.status != OfertaMarketplace.Status.PENDENTE:
            raise ErroMarketplace("oferta encerrada")
        if oferta.expira_em <= agora:
            oferta.status = OfertaMarketplace.Status.EXPIROU
            oferta.respondida_em = agora
            oferta.save(update_fields=["status", "respondida_em"])
            pedido.status = PedidoMarketplace.Status.NA_FILA
            pedido.save(update_fields=["status", "atualizado_em"])
            _evento(pedido, "marketplace.oferta_expirou.v1", str(oferta.pk))
            return pedido
        oferta.status = OfertaMarketplace.Status.PASSOU
        oferta.motivo = motivo[:160]
        oferta.respondida_em = agora
        oferta.save(update_fields=["status", "motivo", "respondida_em"])
        pedido.status = PedidoMarketplace.Status.NA_FILA
        pedido.save(update_fields=["status", "atualizado_em"])
        _evento(pedido, "marketplace.oferta_passada.v1", str(oferta.pk))
        return pedido


def _acesso_pedido(pedido: PedidoMarketplace, ator_id: str, papel: str):
    if papel == "cliente":
        _cliente(pedido, ator_id)
    elif papel == "aluno":
        _aluno(pedido, ator_id)
    elif papel == "equipe":
        if not ator_id:
            raise ErroMarketplace("equipe sem identidade")
    else:
        raise ErroMarketplace("papel inválido")


def adicionar_arquivo(
    *, site_id: str, pedido_id, ator_id: str, papel: str,
    nome: str, chave: str, versao_entrega=None, legenda: str = "",
    ator_papel: str | None = None,
    tamanho_bytes: int | None = None, tipo_mime: str = "",
    sha256: str = "", versao_exportacao: str = "",
) -> ArquivoMarketplace:
    pedido = _pedido(site_id, pedido_id)
    if papel not in {"referencia", "final", "previa"}:
        raise ErroMarketplace("tipo de arquivo inválido")
    if ator_papel is None:
        ator_papel = (
            "cliente" if pedido.cliente_id == ator_id else "aluno"
        )
    _acesso_pedido(pedido, ator_id, ator_papel)
    if (
        not nome or not chave or "/" in nome or "\\" in nome
        or "\\" in chave or ":" in chave or chave.startswith("/")
        or any(parte in {"", ".", ".."} for parte in chave.split("/"))
    ):
        raise ErroMarketplace("nome ou chave de arquivo inválida")
    if not isinstance(legenda, str) or not isinstance(versao_exportacao, str):
        raise ErroMarketplace("metadados do arquivo inválidos")
    if tamanho_bytes is not None and (
        not isinstance(tamanho_bytes, int) or tamanho_bytes < 0
    ):
        raise ErroMarketplace("tamanho do arquivo inválido")
    if tipo_mime and not re.fullmatch(r"[a-zA-Z0-9.+-]+/[a-zA-Z0-9.+-]+", tipo_mime):
        raise ErroMarketplace("tipo MIME inválido")
    if sha256 and not re.fullmatch(r"[a-fA-F0-9]{64}", sha256):
        raise ErroMarketplace("resumo SHA-256 inválido")
    if ator_papel == "aluno" and pedido.status not in (
        PedidoMarketplace.Status.EM_PRODUCAO, PedidoMarketplace.Status.EM_AJUSTE,
    ):
        raise ErroMarketplace("pedido fora da produção")
    if ator_papel == "cliente" and papel != "referencia":
        raise ErroMarketplace("cliente só anexa referências")
    if ator_papel == "aluno" and papel == "referencia":
        raise ErroMarketplace("aluno anexa prévias ou arquivos finais")
    entrega = None
    if versao_entrega is not None:
        entrega = EntregaMarketplace.objects.filter(
            pedido=pedido, site_id=site_id, versao=versao_entrega,
        ).first()
        if entrega is None:
            raise ErroMarketplace("versão de entrega não encontrada")
    with transaction.atomic():
        arquivo = ArquivoMarketplace.objects.create(
            site_id=site_id, pedido=pedido, entrega=entrega, ator_id=ator_id,
            papel=papel, nome=nome, chave=chave, legenda=legenda,
            tamanho_bytes=tamanho_bytes, tipo_mime=tipo_mime,
            sha256=sha256.lower(), versao_exportacao=versao_exportacao,
        )
        _evento(pedido, "marketplace.arquivo_adicionado.v1", str(arquivo.pk), {
            "arquivo_id": str(arquivo.pk), "papel": papel,
        })
        return arquivo


def arquivo_autorizado(
    *, site_id: str, arquivo_id, ator_id: str, papel: str,
) -> ArquivoMarketplace:
    arquivo = ArquivoMarketplace.objects.select_related("pedido").filter(
        pk=arquivo_id, site_id=site_id,
    ).first()
    if arquivo is None:
        raise ErroMarketplace("arquivo não encontrado")
    _acesso_pedido(arquivo.pedido, ator_id, papel)
    return arquivo


def registrar_mensagem(
    *, site_id: str, pedido_id, ator_id: str, papel: str,
    texto: str, entrega_id=None,
) -> MensagemMarketplace:
    pedido = _pedido(site_id, pedido_id)
    _acesso_pedido(pedido, ator_id, papel)
    if not texto.strip():
        raise ErroMarketplace("mensagem vazia")
    entrega = None
    if entrega_id:
        entrega = EntregaMarketplace.objects.filter(
            pk=entrega_id, pedido=pedido, site_id=site_id,
        ).first()
        if entrega is None:
            raise ErroMarketplace("entrega não encontrada")
    with transaction.atomic():
        mensagem = MensagemMarketplace.objects.create(
            site_id=site_id, pedido=pedido, entrega=entrega,
            ator_id=ator_id, papel=papel, texto=texto.strip(),
        )
        _evento(pedido, "marketplace.mensagem.v1", str(mensagem.pk))
        return mensagem


def enviar_entrega(
    *, site_id: str, pedido_id, pessoa_id: str,
    arquivos_ids, comentario: str = "",
) -> EntregaMarketplace:
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        _aluno(pedido, pessoa_id)
        ids = [UUID(str(i)) for i in arquivos_ids]
        if not ids or len(set(ids)) != len(ids):
            raise ErroMarketplace("arquivos finais obrigatórios")
        arquivos = list(ArquivoMarketplace.objects.select_for_update().filter(
            pk__in=ids, site_id=site_id, pedido=pedido, ator_id=pessoa_id,
        ))
        if len(arquivos) != len(ids) or any(a.papel not in {"final", "previa"} for a in arquivos):
            raise ErroMarketplace("arquivos fora deste pedido")
        entregas_anteriores = {a.entrega_id for a in arquivos if a.entrega_id}
        if len(entregas_anteriores) == 1 and all(a.entrega_id for a in arquivos):
            entrega = EntregaMarketplace.objects.get(pk=next(iter(entregas_anteriores)))
            if set(entrega.arquivos.values_list("pk", flat=True)) == set(ids):
                return entrega
        if pedido.status not in (
            PedidoMarketplace.Status.EM_PRODUCAO, PedidoMarketplace.Status.EM_AJUSTE,
        ) or any(a.entrega_id for a in arquivos):
            raise ErroMarketplace("entrega indisponível")
        proxima = (EntregaMarketplace.objects.filter(pedido=pedido)
                   .order_by("-versao").values_list("versao", flat=True).first() or 0) + 1
        entrega = EntregaMarketplace.objects.create(
            site_id=site_id, pedido=pedido, versao=proxima, comentario=comentario,
        )
        ArquivoMarketplace.objects.filter(pk__in=ids).update(entrega=entrega)
        pedido.status = PedidoMarketplace.Status.ENTREGUE
        pedido.save(update_fields=["status", "atualizado_em"])
        _evento(pedido, "marketplace.entrega_enviada.v1", str(entrega.pk), {
            "entrega_id": str(entrega.pk), "versao": proxima,
        })
        return entrega


def pedir_ajuste(
    *, site_id: str, pedido_id, cliente_id: str, entrega_id, texto: str,
) -> AjusteMarketplace:
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        _cliente(pedido, cliente_id)
        entrega = EntregaMarketplace.objects.filter(
            pk=entrega_id, site_id=site_id, pedido=pedido,
        ).first()
        if entrega is None:
            raise ErroMarketplace("entrega não encontrada")
        if entrega.versao != (
            EntregaMarketplace.objects.filter(pedido=pedido).order_by("-versao")
            .values_list("versao", flat=True).first()
        ):
            raise ErroMarketplace("escolha a entrega mais recente")
        existente = AjusteMarketplace.objects.filter(entrega=entrega).first()
        if existente:
            return existente
        if pedido.status != PedidoMarketplace.Status.ENTREGUE:
            raise ErroMarketplace("pedido fora da conferência")
        if not texto.strip():
            raise ErroMarketplace("descreva o ajuste")
        limite = pedido.acordo.termos["ajustes_inclusos"]
        if AjusteMarketplace.objects.filter(pedido=pedido).count() >= limite:
            raise ErroMarketplace("ajustes combinados esgotados")
        ajuste = AjusteMarketplace.objects.create(
            site_id=site_id, pedido=pedido, entrega=entrega, texto=texto.strip(),
        )
        pedido.status = PedidoMarketplace.Status.EM_AJUSTE
        pedido.save(update_fields=["status", "atualizado_em"])
        _evento(pedido, "marketplace.ajuste_pedido.v1", str(ajuste.pk))
        return ajuste


def aprovar_entrega(
    *, site_id: str, pedido_id, cliente_id: str, entrega_id,
) -> RecebivelMarketplace:
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        _cliente(pedido, cliente_id)
        entrega = EntregaMarketplace.objects.filter(
            pk=entrega_id, site_id=site_id, pedido=pedido,
        ).first()
        if entrega is None:
            raise ErroMarketplace("entrega não encontrada")
        if pedido.status == PedidoMarketplace.Status.APROVADO and entrega.aprovada_em:
            return RecebivelMarketplace.objects.get(pedido=pedido)
        if pedido.status != PedidoMarketplace.Status.ENTREGUE or entrega.versao != (
            EntregaMarketplace.objects.filter(pedido=pedido).order_by("-versao")
            .values_list("versao", flat=True).first()
        ):
            raise ErroMarketplace("entrega não está pronta para aprovação")
        agora = timezone.now()
        entrega.aprovada_em = agora
        entrega.save(update_fields=["aprovada_em"])
        pedido.status = PedidoMarketplace.Status.APROVADO
        pedido.aprovado_em = agora
        pedido.save(update_fields=["status", "aprovado_em", "atualizado_em"])
        perfil = PerfilProfissional.objects.select_for_update().get(pk=pedido.aluno_id, site_id=site_id)
        PerfilProfissional.objects.filter(pk=perfil.pk).update(entregas_aprovadas=F("entregas_aprovadas") + 1)
        if perfil.disponibilidade == PerfilProfissional.Disponibilidade.TRABALHANDO:
            perfil.mudar_disponibilidade(PerfilProfissional.Disponibilidade.DISPONIVEL)
        recebivel = RecebivelMarketplace.objects.create(
            site_id=site_id, pedido=pedido, aluno=perfil,
        )
        _evento(pedido, "marketplace.entrega_aprovada.v1", str(entrega.pk), {
            "entrega_id": str(entrega.pk), "recebivel_id": recebivel.pk,
        })
        return recebivel


def registrar_recebimento(
    *, site_id: str, pedido_id, valor_liquido_cents: int,
    referencia: str, ambiente: str,
) -> RecebivelMarketplace:
    """Confirma fato externo de repasse; nunca inicia transferência."""
    if not referencia or not isinstance(valor_liquido_cents, int) or valor_liquido_cents < 0:
        raise ErroMarketplace("confirmação de recebimento inválida")
    with transaction.atomic():
        pedido = _pedido(site_id, pedido_id, trava=True)
        if pedido.ambiente != ambiente or pedido.status != PedidoMarketplace.Status.APROVADO:
            raise ErroMarketplace("recebimento não corresponde ao pedido")
        recebivel = RecebivelMarketplace.objects.select_for_update().get(pedido=pedido)
        if recebivel.status == RecebivelMarketplace.Status.RECEBIDO:
            if recebivel.referencia_repasse != referencia or recebivel.valor_liquido_cents != valor_liquido_cents:
                raise ErroMarketplace("recebível já confirmado com outros dados")
            return recebivel
        recebivel.status = RecebivelMarketplace.Status.RECEBIDO
        recebivel.valor_liquido_cents = valor_liquido_cents
        recebivel.referencia_repasse = referencia
        recebivel.recebido_em = timezone.now()
        recebivel.save(update_fields=[
            "status", "valor_liquido_cents", "referencia_repasse", "recebido_em"
        ])
        _evento(pedido, "marketplace.recebimento_confirmado.v1", referencia)
        return recebivel
