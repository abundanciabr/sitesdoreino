"""Carteira e comprovacao manual de Pix dos trabalhos aprovados da fila real.

Este modulo registra pedidos e fatos informados por pessoas. Nao aciona banco,
provedor de pagamento nem altera a carteira mantida pela celula pagamentos.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import re
from uuid import UUID

from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import validate_email
from django.db import IntegrityError, transaction
from django.db.models import Sum
from django.utils import timezone
from django.views.decorators.debug import sensitive_variables

from .marketplace import ErroMarketplace, acesso_aluno
from .models import (
    ClienteFila, ParcelaSaqueFila, PerfilProfissional, RecebivelMarketplace,
    SaqueManualFila,
)


MINIMO_SAQUE_CENTS = 5000


def _cpf_valido(cpf: str) -> bool:
    if len(cpf) != 11 or cpf == cpf[0] * 11:
        return False
    numeros = [int(digito) for digito in cpf]
    for tamanho in (9, 10):
        resto = sum(numeros[i] * (tamanho + 1 - i) for i in range(tamanho)) % 11
        verificador = 0 if resto < 2 else 11 - resto
        if numeros[tamanho] != verificador:
            return False
    return True


def _fernet() -> Fernet:
    # Chave separada por contexto da usada para qualquer outra cifra do site.
    digest = hashlib.sha256(
        b'meshcraft-fila-saque-manual-v1:' + settings.SECRET_KEY.encode()
    ).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


@sensitive_variables('valor')
def _cifrar(valor: str) -> str:
    return _fernet().encrypt(valor.encode()).decode()


@sensitive_variables('valor')
def _decifrar(valor: str) -> str:
    try:
        return _fernet().decrypt(valor.encode()).decode()
    except (InvalidToken, ValueError, UnicodeError):
        raise ErroMarketplace('Os dados do Pix nao puderam ser lidos.') from None


def pode_acessar_carteira(*, site_id: str, pessoa_id: str) -> bool:
    """O direito a um valor aprovado sobrevive ao fechamento da fila."""
    if not site_id or not pessoa_id:
        return False
    perfil = PerfilProfissional.objects.filter(site_id=site_id, pessoa_id=pessoa_id).first()
    if perfil is None:
        return False
    return bool(
        acesso_aluno(site_id=site_id, pessoa_id=pessoa_id)
        or RecebivelMarketplace.objects.filter(
            site_id=site_id, aluno=perfil, pedido__site_id=site_id,
            pedido__aluno=perfil, pedido__fila_cliente__isnull=False,
            pedido__status='aprovado',
        ).exists()
        or SaqueManualFila.objects.filter(site_id=site_id, aluno=perfil).exists()
    )


def _perfil(site_id: str, pessoa_id: str, *, trava: bool = False) -> PerfilProfissional:
    if not pessoa_id:
        raise ErroMarketplace('Carteira indisponivel para esta conta.')
    consulta = PerfilProfissional.objects.filter(site_id=site_id, pessoa_id=pessoa_id)
    if trava:
        consulta = consulta.select_for_update()
    perfil = consulta.first()
    if perfil is None or not pode_acessar_carteira(site_id=site_id, pessoa_id=pessoa_id):
        raise ErroMarketplace('Carteira indisponivel para esta conta.')
    return perfil


def _recebiveis(perfil: PerfilProfissional, *, trava: bool = False):
    consulta = RecebivelMarketplace.objects.filter(
        site_id=perfil.site_id, aluno=perfil, pedido__site_id=perfil.site_id,
        pedido__aluno=perfil, pedido__fila_cliente__isnull=False,
        pedido__status='aprovado', status=RecebivelMarketplace.Status.PENDENTE,
        creditado_em__isnull=True, recebido_em__isnull=True,
    ).select_related('pedido').order_by('pk')
    if trava:
        consulta = consulta.select_for_update(of=('self',))
    return list(consulta)


def _valor_recebivel(recebivel: RecebivelMarketplace) -> int:
    valor = recebivel.valor_liquido_cents
    return int(valor if valor is not None else recebivel.pedido.valor_cents)


def _total_alocado(recebiveis) -> dict[int, int]:
    ids = [item.pk for item in recebiveis]
    return {
        item['recebivel_id']: item['total']
        for item in ParcelaSaqueFila.objects.filter(recebivel_id__in=ids).values(
            'recebivel_id'
        ).annotate(total=Sum('valor_cents'))
    }


def _publico(saque: SaqueManualFila) -> dict:
    return {
        'id': str(saque.pk), 'valor_cents': saque.valor_cents,
        'status': saque.status, 'nome_recebedor': saque.nome_recebedor,
        'solicitado_em': saque.solicitado_em.isoformat() if saque.solicitado_em else None,
        'pago_em': saque.pago_em.isoformat() if saque.pago_em else None,
        'referencia_pix': saque.referencia_pix,
    }


def carteira(*, site_id: str, pessoa_id: str) -> dict:
    perfil = _perfil(site_id, pessoa_id)
    recebiveis = _recebiveis(perfil)
    alocado = _total_alocado(recebiveis)
    disponivel = sum(max(0, _valor_recebivel(r) - alocado.get(r.pk, 0)) for r in recebiveis)
    saques = list(SaqueManualFila.objects.filter(site_id=site_id, aluno=perfil).order_by('-solicitado_em'))
    return {
        'saldo_disponivel_cents': disponivel,
        'saldo_solicitado_cents': sum(s.valor_cents for s in saques if s.status == SaqueManualFila.Status.SOLICITADO),
        'total_pago_cents': sum(s.valor_cents for s in saques if s.status == SaqueManualFila.Status.PAGO),
        'saques': [_publico(s) for s in saques],
    }


@sensitive_variables('dados', 'chave_pix')
def solicitar(*, site_id: str, pessoa_id: str, dados: dict) -> dict:
    if not isinstance(dados, dict):
        raise ErroMarketplace('Confira os dados do saque.')
    try:
        valor = dados.get('valor_cents')
        if isinstance(valor, bool):
            raise ValueError
        valor = int(valor)
        chave_idempotencia = UUID(str(dados.get('chave_idempotencia')))
    except (TypeError, ValueError, AttributeError):
        raise ErroMarketplace('Confira o valor e a identificacao do saque.') from None
    chave_pix = str(dados.get('chave_pix') or '').strip()
    nome = str(dados.get('nome_recebedor') or '').strip()
    if valor < MINIMO_SAQUE_CENTS:
        raise ErroMarketplace('O saque minimo e R$ 50,00.')
    if not chave_pix or len(chave_pix) > 180 or not nome or len(nome) > 160:
        raise ErroMarketplace('Informe a chave Pix e o nome de quem recebera.')
    with transaction.atomic():
        perfil = _perfil(site_id, pessoa_id, trava=True)
        existente = SaqueManualFila.objects.select_for_update().filter(
            chave_idempotencia=chave_idempotencia
        ).first()
        if existente:
            if (existente.site_id != site_id or existente.aluno_id != perfil.pk
                or existente.valor_cents != valor or existente.nome_recebedor != nome
                or not hmac.compare_digest(_decifrar(existente.chave_pix_cifrada).encode(), chave_pix.encode())):
                raise ErroMarketplace('Esta solicitacao ja foi usada com outros dados.')
            return _publico(existente)
        recebiveis = _recebiveis(perfil, trava=True)
        alocado = _total_alocado(recebiveis)
        sobras = [(r, max(0, _valor_recebivel(r) - alocado.get(r.pk, 0))) for r in recebiveis]
        if valor > sum(sobra for _, sobra in sobras):
            raise ErroMarketplace('O valor supera o saldo disponivel para saque.')
        try:
            with transaction.atomic():
                saque = SaqueManualFila.objects.create(
                    site_id=site_id, aluno=perfil, chave_idempotencia=chave_idempotencia,
                    valor_cents=valor, chave_pix_cifrada=_cifrar(chave_pix),
                    nome_recebedor=nome,
                )
        except IntegrityError:
            raise ErroMarketplace('Esta solicitação já foi utilizada. Confira a carteira antes de tentar novamente.') from None
        restante = valor
        for recebivel, sobra in sobras:
            if restante == 0:
                break
            fatia = min(restante, sobra)
            if fatia:
                ParcelaSaqueFila.objects.create(saque=saque, recebivel=recebivel, valor_cents=fatia)
                restante -= fatia
        return _publico(saque)


@sensitive_variables('resultado')
def listar_admin(*, site_id: str) -> dict:
    saques = SaqueManualFila.objects.filter(site_id=site_id).select_related('aluno__pessoa').order_by('-solicitado_em')
    resultado = []
    for saque in saques:
        resultado.append({
            **_publico(saque), 'aluno_id': saque.aluno.pessoa_id,
            'aluno_nome': saque.aluno.pessoa.nome_exibido,
            'chave_pix': _decifrar(saque.chave_pix_cifrada),
            'pagador_nome': saque.pagador_nome,
            'pagador_email': saque.pagador_email,
            'confirmado_por': saque.confirmado_por,
        })
    return {'saques': resultado}


@sensitive_variables('dados', 'cpf')
def confirmar(*, site_id: str, saque_id, ator_id: str, dados: dict) -> dict:
    """Registra o Pix ja executado manualmente; nunca envia dinheiro."""
    if not ator_id or not isinstance(dados, dict):
        raise ErroMarketplace('Confirmacao manual incompleta.')
    referencia = str(dados.get('referencia_pix') or '').strip()
    nome = str(dados.get('pagador_nome') or '').strip()
    cpf = re.sub(r'\D', '', str(dados.get('pagador_cpf') or ''))
    email = str(dados.get('pagador_email') or '').strip().lower()
    if not referencia or len(referencia) > 160 or len(nome.split()) < 2 or len(nome) > 160 or not _cpf_valido(cpf):
        raise ErroMarketplace('Informe referencia Pix, nome completo e CPF do pagador.')
    try:
        if len(email) > 254:
            raise ValidationError('email')
        validate_email(email)
    except ValidationError:
        raise ErroMarketplace('Informe o e-mail do pagador.') from None
    with transaction.atomic():
        saque = SaqueManualFila.objects.select_for_update().filter(pk=saque_id, site_id=site_id).first()
        if saque is None:
            raise ErroMarketplace('Saque nao encontrado neste site.')
        if saque.status == SaqueManualFila.Status.PAGO:
            if (saque.referencia_pix != referencia or saque.pagador_nome != nome
                or saque.pagador_email != email or saque.confirmado_por != ator_id
                or not hmac.compare_digest(_decifrar(saque.pagador_cpf_cifrado), cpf)):
                raise ErroMarketplace('Este saque ja foi confirmado com outros dados.')
            return _publico(saque)
        if SaqueManualFila.objects.filter(referencia_pix=referencia).exclude(pk=saque.pk).exists():
            raise ErroMarketplace('Esta referencia Pix ja foi usada.')
        saque.status = SaqueManualFila.Status.PAGO
        saque.referencia_pix = referencia
        saque.pagador_nome = nome
        saque.pagador_cpf_cifrado = _cifrar(cpf)
        saque.pagador_email = email
        saque.confirmado_por = ator_id
        saque.pago_em = timezone.now()
        try:
            with transaction.atomic():
                saque.save(update_fields=[
                    'status', 'referencia_pix', 'pagador_nome', 'pagador_cpf_cifrado',
                    'pagador_email', 'confirmado_por', 'pago_em',
                ])
        except IntegrityError:
            raise ErroMarketplace('Esta referencia Pix ja foi usada.') from None
        return _publico(saque)


def pendente_cliente(cliente: ClienteFila) -> int:
    """Valor aprovado de pedidos do cliente ainda sem Pix manual registrado."""
    recebiveis = list(RecebivelMarketplace.objects.filter(
        site_id=cliente.site_id, pedido__site_id=cliente.site_id,
        pedido__fila_cliente__cliente=cliente, pedido__status='aprovado',
        status=RecebivelMarketplace.Status.PENDENTE,
        creditado_em__isnull=True, recebido_em__isnull=True,
    ))
    if not recebiveis:
        return 0
    pagos = {
        item['recebivel_id']: item['total']
        for item in ParcelaSaqueFila.objects.filter(
            recebivel__in=recebiveis, saque__status=SaqueManualFila.Status.PAGO,
        ).values('recebivel_id').annotate(total=Sum('valor_cents'))
    }
    return sum(max(0, _valor_recebivel(r) - pagos.get(r.pk, 0)) for r in recebiveis)
