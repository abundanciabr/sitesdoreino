"""Créditos nominais da escola: R$1 por crédito, lançamentos idempotentes."""
from __future__ import annotations

import hashlib
import uuid
from django.db import transaction
from django.utils import timezone

from pagamentos.marketplace.models import Charge, WalletAccount, WalletEntry, WithdrawalRequest


class WalletConflict(ValueError):
    pass


def _valid_owner(site_id: str, owner_id: str) -> None:
    if not site_id or len(site_id) > 255 or not owner_id or len(owner_id) > 64:
        raise WalletConflict("site ou titular inválido")


def _valid_amount(amount_cents: int) -> None:
    if type(amount_cents) is not int or amount_cents <= 0 or amount_cents % 100:
        raise WalletConflict("créditos devem ter valor inteiro em reais")


def _key(kind: str, site_id: str, reference: str) -> str:
    digest = hashlib.sha256((site_id + "\x00" + reference).encode()).hexdigest()
    return kind + ":" + digest


def _account(site_id: str, owner_kind: str, owner_id: str) -> WalletAccount:
    account, _ = WalletAccount.objects.get_or_create(
        site_id=site_id, environment="sandbox", owner_kind=owner_kind, owner_id=owner_id)
    return WalletAccount.objects.select_for_update().get(pk=account.pk)


def _public(account: WalletAccount) -> dict:
    return {"site_id": account.site_id, "environment": account.environment, "owner_id": account.owner_id,
            "balance_cents": account.balance_cents, "credits": account.balance_cents // 100,
            "frozen": account.frozen}


def balance(*, site_id: str, owner_kind: str, owner_id: str) -> dict:
    _valid_owner(site_id, owner_id)
    if owner_kind not in {"client", "student"}:
        raise WalletConflict("tipo de titular inválido")
    account = WalletAccount.objects.filter(
        site_id=site_id, environment="sandbox", owner_kind=owner_kind, owner_id=owner_id).first()
    if account is None:
        return {"site_id": site_id, "environment": "sandbox", "owner_id": owner_id,
                "balance_cents": 0, "credits": 0, "frozen": False}
    return _public(account)


def _post(*, key: str, site_id: str, owner_kind: str, owner_id: str,
          kind: str, amount_cents: int, order_id: uuid.UUID | None = None,
          order_version: int | None = None, charge: Charge | None = None,
          allow_negative: bool = False, request_key: uuid.UUID | None = None) -> WalletEntry:
    account = _account(site_id, owner_kind, owner_id)
    if account.frozen and amount_cents < 0 and kind in {"spend", "withdrawal_hold"}:
        raise WalletConflict("carteira sob revisão financeira")
    if request_key:
        by_request = WalletEntry.objects.filter(request_key=request_key).first()
        if by_request is not None and by_request.operation_key != key:
            raise WalletConflict("chave de idempotência usada em outra operação")
    previous = WalletEntry.objects.filter(operation_key=key).first()
    if previous is not None:
        if (previous.account_id != account.pk or previous.kind != kind
                or previous.amount_cents != amount_cents or previous.order_id != order_id
                or previous.order_version != order_version
                or previous.request_key != request_key
                or previous.charge_id != (charge.pk if charge else None)):
            raise WalletConflict("operação de créditos divergente")
        return previous
    if not allow_negative and account.balance_cents + amount_cents < 0:
        raise WalletConflict("saldo insuficiente")
    entry = WalletEntry.objects.create(
        operation_key=key, request_key=request_key, account=account, kind=kind,
        amount_cents=amount_cents, order_id=order_id, order_version=order_version, charge=charge)
    account.balance_cents += amount_cents
    account.save(update_fields=["balance_cents", "updated_at"])
    return entry


def creditar_recarga(charge: Charge) -> None:
    if charge.status != "approved" or not charge.wallet_owner_id or charge.method != "pix":
        raise WalletConflict("recarga não aprovada")
    _valid_amount(charge.amount_cents)
    with transaction.atomic():
        _post(key=_key("topup", charge.site_id, str(charge.id)),
              site_id=charge.site_id, owner_kind="client", owner_id=charge.wallet_owner_id,
              kind="topup", amount_cents=charge.amount_cents, charge=charge)


def reverter_recarga(charge: Charge) -> None:
    if not charge.wallet_owner_id:
        return
    with transaction.atomic():
        key = _key("topup", charge.site_id, str(charge.id))
        if not WalletEntry.objects.filter(operation_key=key).exists():
            return
        if charge.status == "partially_refunded":
            account = _account(charge.site_id, "client", charge.wallet_owner_id)
            if not account.frozen:
                account.frozen = True
                account.save(update_fields=["frozen", "updated_at"])
            return
        _post(key=_key("topup_reversal", charge.site_id, str(charge.id)),
              site_id=charge.site_id, owner_kind="client", owner_id=charge.wallet_owner_id,
              kind="topup_reversal", amount_cents=-charge.amount_cents,
              charge=charge, allow_negative=True)


def spend(*, site_id: str, client_id: str, order_id: uuid.UUID,
          order_version: int, amount_cents: int, idempotency_key: uuid.UUID) -> dict:
    _valid_owner(site_id, client_id)
    _valid_amount(amount_cents)
    if order_version < 1:
        raise WalletConflict("versão do pedido inválida")
    with transaction.atomic():
        entry = _post(key=_key("spend", site_id, str(order_id)),
                      site_id=site_id, owner_kind="client", owner_id=client_id,
                      kind="spend", amount_cents=-amount_cents, order_id=order_id,
                      order_version=order_version, request_key=idempotency_key)
        return {"order_id": str(order_id), "status": "debited", "amount_cents": -entry.amount_cents,
                **_public(entry.account)}


def earn(*, site_id: str, aluno_id: str, order_id: uuid.UUID,
         order_version: int, amount_cents: int, idempotency_key: uuid.UUID) -> dict:
    _valid_owner(site_id, aluno_id)
    _valid_amount(amount_cents)
    if order_version < 1:
        raise WalletConflict("versão do pedido inválida")
    with transaction.atomic():
        debit = WalletEntry.objects.filter(operation_key=_key("spend", site_id, str(order_id))).first()
        if debit is None or debit.amount_cents != -amount_cents or debit.order_version != order_version:
            raise WalletConflict("débito do pedido não corresponde ao crédito do aluno")
        entry = _post(key=_key("earn", site_id, str(order_id)),
                      site_id=site_id, owner_kind="student", owner_id=aluno_id,
                      kind="earn", amount_cents=amount_cents, order_id=order_id,
                      order_version=order_version, request_key=idempotency_key)
        return {"order_id": str(order_id), "status": "credited", "amount_cents": entry.amount_cents,
                **_public(entry.account)}


def request_withdrawal(*, site_id: str, aluno_id: str,
                       request_id: uuid.UUID, amount_cents: int) -> dict:
    _valid_owner(site_id, aluno_id)
    _valid_amount(amount_cents)
    if amount_cents < 5000:
        raise WalletConflict("saque mínimo é R$50")
    with transaction.atomic():
        entry = _post(key=_key("withdrawal", site_id, str(request_id)),
                      site_id=site_id, owner_kind="student", owner_id=aluno_id,
                      kind="withdrawal_hold", amount_cents=-amount_cents,
                      request_key=request_id)
        request, _ = WithdrawalRequest.objects.get_or_create(
            pk=request_id, defaults={"account": entry.account, "amount_cents": amount_cents})
        if request.account_id != entry.account_id or request.amount_cents != amount_cents:
            raise WalletConflict("solicitação de saque divergente")
        return {"id": str(request.id), "status": request.status, "amount_cents": request.amount_cents,
                **_public(entry.account)}


def statement(*, site_id: str, owner_kind: str, owner_id: str) -> dict:
    result = balance(site_id=site_id, owner_kind=owner_kind, owner_id=owner_id)
    account = WalletAccount.objects.filter(site_id=site_id, environment="sandbox",
                                           owner_kind=owner_kind, owner_id=owner_id).first()
    result["entries"] = []
    result["withdrawals"] = []
    if account is None:
        return result
    result["entries"] = [{"kind": item.kind, "amount_cents": item.amount_cents,
                          "order_id": str(item.order_id) if item.order_id else None,
                          "charge_id": str(item.charge_id) if item.charge_id else None,
                          "created_at": item.created_at.isoformat()}
                         for item in account.entries.order_by("-created_at")[:100]]
    if owner_kind == "student":
        result["withdrawals"] = [_withdrawal_public(item)
                                  for item in WithdrawalRequest.objects.filter(account=account).order_by("-created_at")[:100]]
    return result


def _withdrawal_public(request: WithdrawalRequest) -> dict:
    return {"id": str(request.id), "site_id": request.account.site_id,
            "aluno_id": request.account.owner_id, "amount_cents": request.amount_cents,
            "status": request.status,
            "authorization_reference": request.authorization_reference,
            "bank_reference": request.bank_reference,
            "proof_reference": request.proof_reference,
            "created_at": request.created_at.isoformat(),
            "confirmed_at": request.confirmed_at.isoformat() if request.confirmed_at else None}


def list_withdrawals(*, site_id: str) -> list[dict]:
    if not site_id or len(site_id) > 255:
        raise WalletConflict("site inválido")
    return [_withdrawal_public(item) for item in WithdrawalRequest.objects.select_related("account").filter(
        account__site_id=site_id, account__environment="sandbox").order_by("-created_at")[:100]]


def confirm_withdrawal(*, site_id: str, request_id: uuid.UUID,
                       authorization_reference: str, bank_reference: str,
                       proof_reference: str) -> dict:
    references = (authorization_reference.strip(), bank_reference.strip(), proof_reference.strip())
    if not site_id or any(not value or len(value) > 160 for value in references):
        raise WalletConflict("confirmação bancária sem autorização e comprovantes")
    with transaction.atomic():
        request = WithdrawalRequest.objects.select_for_update().select_related("account").filter(
            pk=request_id, account__site_id=site_id, account__environment="sandbox").first()
        if request is None:
            raise WalletConflict("saque não encontrado")
        if request.status == "paid":
            if (request.authorization_reference, request.bank_reference,
                    request.proof_reference) != references:
                raise WalletConflict("comprovantes divergentes")
            return _withdrawal_public(request)
        if request.status != "requested":
            raise WalletConflict("saque não está solicitado")
        request.authorization_reference, request.bank_reference, request.proof_reference = references
        request.status = "paid"
        request.confirmed_at = timezone.now()
        request.save(update_fields=["authorization_reference", "bank_reference", "proof_reference",
                                    "status", "confirmed_at", "updated_at"])
        return _withdrawal_public(request)
