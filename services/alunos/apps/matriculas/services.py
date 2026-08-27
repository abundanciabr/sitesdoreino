# apps/matriculas/services.py
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import Matricula


class OrderIdReservado(ValueError):
    """[FILA] Um pedido REAL tentou usar o prefixo reservado às linhas da fila.

    Sobe como 422 no reprocesso manual e mata o processamento do evento (que é o
    certo: envelope com `order_id` assim é mensagem envenenada, e o caminho da
    PEL/fila morta existe exatamente para ela).
    """


def matriculas_que_valem(email: str):
    """[FILA] As matrículas que RESPONDEM "esta pessoa é aluna" — a consulta que
    decide acesso, e a única que a Caixa de Sugestões enxerga.

    Existe como função (e não como `.filter()` solto no handler) porque é um
    JUÍZO, não uma leitura: quem chama herda a lista de permissão de
    `STATUS_QUE_VALEM` sem escolher nada. Até 27/08/2026 o handler filtrava só
    por e-mail, sem status — no instante em que `aguardando` passasse a existir,
    quem estivesse na fila entraria na Caixa na hora, que é o oposto exato do
    que a fila quer (lei §3).
    """
    return Matricula.objects.filter(
        email=email, status__in=Matricula.STATUS_QUE_VALEM
    ).order_by("enrolled_at")


def matricular(
    *, site_id: str, order_id: str, product_id: str, email: str, name: str
) -> tuple[Matricula, bool]:
    """[INV-P5] Matrícula sob select_for_update() + transaction.atomic(), idempotente
    por order_id. Chamada tanto pelo consumer do evento (R4) quanto pelo reprocesso
    manual (POST /matriculas) — as duas portas usam a MESMA idempotência.

    select_for_update() não trava linha que ainda não existe, então a corrida de
    criação é fechada pela unicidade de order_id: quem perde o INSERT recebe
    IntegrityError e lê a linha do vencedor sob lock (bloqueia até o commit dele).
    """
    # [FILA] Fail-closed na borda: este é o ÚNICO lugar por onde entra um
    # `order_id` vindo de fora (evento de pagamento e reprocesso manual). Sem a
    # recusa, um provedor que mandasse `pre:qualquer-coisa` criaria uma matrícula
    # PAGA disfarçada de linha da fila — e `POST /pre-matriculas/{id}/decisao`,
    # que reconhece a fila pelo prefixo, passaria a poder decidir sobre ela.
    if order_id.startswith(Matricula.PREFIXO_DA_FILA):
        raise OrderIdReservado(
            f"order_id não pode começar com {Matricula.PREFIXO_DA_FILA!r}: "
            "esse prefixo é reservado às linhas da fila de liberação"
        )
    with transaction.atomic():
        existente = (
            Matricula.objects.select_for_update().filter(order_id=order_id).first()
        )
        if existente is not None:
            return existente, False
        try:
            with transaction.atomic():
                nova = Matricula.objects.create(
                    site_id=site_id,
                    order_id=order_id,
                    product_id=product_id,
                    email=email,
                    name=name,
                )
            return nova, True
        except IntegrityError:
            return Matricula.objects.select_for_update().get(order_id=order_id), False


def entrar_na_fila(
    *,
    site_id: str,
    email: str,
    nome_completo: str,
    whatsapp: str,
    comprou_em=None,
    turma: str = "",
) -> tuple[Matricula | None, bool]:
    """[FILA] Alguém pede entrada e fica AGUARDANDO decisão humana.

    Devolve `(None, False)` quando o e-mail JÁ tem matrícula que vale — quem já
    entra na Caixa não precisa de fila (vira 409 na porta). A conferência usa
    exatamente `matriculas_que_valem()`, a MESMA consulta que decide o acesso:
    se as duas divergissem, existiria gente recusada na fila por "você já tem
    acesso" que a Caixa não deixa entrar.

    Idempotente por (site_id, email): reenviar atualiza os dados e devolve
    `(linha, False)`. Quem foi recusado e reenvia volta para `aguardando` com o
    motivo da recusa limpo — é o caminho de correção previsto pela lei §7 (V1
    não edita dados: o admin recusa e a pessoa reenvia).
    """
    # A Caixa pergunta por `email.strip().lower()` (sessao.py). Uma linha
    # gravada com maiúsculas seria liberada pelo mantenedor e continuaria
    # invisível para ela — a pessoa veria "não encontramos matrícula" DEPOIS
    # de ter sido aprovada, que é o pior desfecho possível desta fila.
    email = email.strip().lower()

    campos = {
        "name": nome_completo,
        "whatsapp": whatsapp,
        "comprou_em": comprou_em,
        "turma": turma,
        "status": Matricula.STATUS_AGUARDANDO,
        # A linha volta a ser um pedido em aberto: a decisão anterior não pode
        # continuar pendurada nela, ou o painel mostra "recusada em X por Y"
        # numa linha que está esperando.
        "decidido_em": None,
        "decidido_por": "",
        "motivo_recusa": "",
    }

    def _atualizar(linha: Matricula) -> Matricula:
        for campo, valor in campos.items():
            setattr(linha, campo, valor)
        linha.save(update_fields=list(campos))
        return linha

    with transaction.atomic():
        if matriculas_que_valem(email).exists():
            return None, False

        na_fila = (
            Matricula.objects.select_for_update()
            .filter(site_id=site_id, email=email, status__in=Matricula.STATUS_DA_FILA)
            .first()
        )
        if na_fila is not None:
            return _atualizar(na_fila), False

        try:
            with transaction.atomic():
                nova = Matricula.objects.create(
                    site_id=site_id,
                    order_id=f"{Matricula.PREFIXO_DA_FILA}{uuid.uuid4()}",
                    product_id="",
                    email=email,
                    **campos,
                )
            return nova, True
        except IntegrityError:
            # Perdeu a corrida contra outra requisição da mesma pessoa: quem
            # decide é a constraint parcial (site_id, email) na fila, não o
            # "já existe?" acima. O savepoint aninhado existe porque um
            # IntegrityError solto aborta a transação inteira (armadilhas/027).
            existente = (
                Matricula.objects.select_for_update()
                .filter(
                    site_id=site_id, email=email, status__in=Matricula.STATUS_DA_FILA
                )
                .get()
            )
            return _atualizar(existente), False


def decidir_na_fila(
    *, id_da_linha: str, decisao: str, decidido_por: str, motivo: str = ""
) -> tuple[Matricula | None, str]:
    """[FILA] Liberar ou recusar quem está na fila.

    Devolve `(linha, "ok")`, `(None, "nao-encontrada")` ou `(None, "ja-decidida")`.

    Só enxerga linhas nascidas na fila (prefixo `pre:` no order_id). Uma matrícula
    PAGA é `nao-encontrada` aqui de propósito: esta porta não é caminho para
    mexer no status de quem comprou — para isso existiria outra, com outro rito.
    """
    with transaction.atomic():
        try:
            linha = (
                Matricula.objects.select_for_update()
                .filter(order_id__startswith=Matricula.PREFIXO_DA_FILA)
                .get(pk=id_da_linha)
            )
        except (Matricula.DoesNotExist, ValueError, TypeError):
            # ValueError/TypeError: id que nem número é
            # (`/pre-matriculas/abc/decisao`) — "não existe linha com este id" é
            # a resposta honesta, não um 500.
            return None, "nao-encontrada"

        if linha.status != Matricula.STATUS_AGUARDANDO:
            return None, "ja-decidida"

        liberou = decisao == "liberar"
        linha.status = Matricula.STATUS_ATIVA if liberou else Matricula.STATUS_RECUSADA
        linha.decidido_em = timezone.now()
        linha.decidido_por = decidido_por
        linha.motivo_recusa = "" if liberou else motivo
        linha.save(
            update_fields=["status", "decidido_em", "decidido_por", "motivo_recusa"]
        )
        return linha, "ok"
