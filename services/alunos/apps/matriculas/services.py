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


# ---------------------------------------------------------------- [CATEGORIAS]
# As cinco categorias de usuário (`docs/decisoes/DECISAO-categorias-de-usuario.md`)
# — mas só TRÊS delas são calculáveis aqui, e a ausência das outras duas é a
# decisão, não esquecimento:
#
# · `visitante` não chega até esta função — não há e-mail para perguntar;
# · `administrador` mora na lista da célula `admin`, conferida na hora, na
#   porta. Se esta célula pudesse respondê-lo, a autorização da área
#   administrativa passaria a depender de uma célula de produto — o inverso do
#   invariante *reconhecer não é autorizar*.
CATEGORIA_CADASTRADO = "cadastrado"
CATEGORIA_NA_FILA = "na_fila"
CATEGORIA_ALUNO = "aluno"


def situacao_de(email: str) -> dict:
    """[CATEGORIAS] Em que categoria esta pessoa está — a resposta ÚNICA.

    Existe para que a home, a Caixa e o painel parem de adivinhar cada um do
    seu jeito: até 28/08/2026 eram quatro respostas para a mesma pergunta, e
    três erravam em pelo menos um caso.

    **`aluno` é conferido PRIMEIRO, e a ordem é a decisão.** Quem já é aluno
    não fica "na fila" para efeito de tela, mesmo que exista uma linha antiga
    de espera — o que ele precisa ver é o que a matrícula dele abre. A pergunta
    "é aluno?" é delegada a `matriculas_que_valem`, e nunca reescrita aqui: uma
    segunda lista de status seriam duas verdades sobre quem é aluno, e elas
    divergiriam no primeiro status novo.

    **Sem `site_id`, deliberadamente.** A fila é única por `(site_id, email)`,
    mas quem decide acesso hoje — `matriculas_que_valem`, a consulta que a
    Caixa enxerga — é por e-mail só. Esta função casa com ELA: duas noções
    diferentes de "quem é aluno" na mesma plataforma é exatamente a divergência
    que a lei da fila §2 recusou. No dia em que houver duas escolas de verdade,
    esta porta ganha o parâmetro — e isso é mudança de contrato, com rito.
    """
    if matriculas_que_valem(email).exists():
        return {"categoria": CATEGORIA_ALUNO, "na_fila": None}

    # A MAIS RECENTE, e não a primeira: quem foi recusado e pediu de novo tem
    # duas linhas na história, e o que importa para a tela é onde a pessoa está
    # agora. (A constraint parcial impede duas linhas ABERTAS no mesmo site,
    # não duas ao longo do tempo em sites diferentes.)
    linha = (
        Matricula.objects.filter(email=email, status__in=Matricula.STATUS_DA_FILA)
        .order_by("-enrolled_at")
        .first()
    )
    if linha is None:
        return {"categoria": CATEGORIA_CADASTRADO, "na_fila": None}

    aguardando = linha.status == Matricula.STATUS_AGUARDANDO
    return {
        "categoria": CATEGORIA_NA_FILA,
        "na_fila": {
            "estado": linha.status,
            # `null` depois de decidida: ninguém espera mais, e um número que
            # continuasse subindo seria lido como "meu pedido está parado".
            "esperando_ha_dias": (
                max((timezone.now() - linha.enrolled_at).days, 0)
                if aguardando
                else None
            ),
            "motivo_recusa": None if aguardando else (linha.motivo_recusa or None),
        },
    }


# ------------------------------------------------------------------- [GESTAO]
# A gestão de quem JÁ é aluno (`docs/decisoes/DECISAO-gestao-de-alunos.md`).
# Até 28/08/2026 não existia, em lugar nenhum, como listar quem é aluno — a
# célula só sabia responder sobre um e-mail por vez.


def alunos_do_painel(*, site_id: str = None, status: str = None):
    """Quem já passou da fila — a lista que o painel administrativo mostra.

    NUNCA devolve quem está na fila, e o filtro é por lista de PERMISSÃO
    (`STATUS_DE_GESTAO`), não por exclusão dos status da fila: estado novo
    inventado amanhã nasce FORA desta lista, e alguém precisa decidir
    explicitamente incluí-lo. Com exclusão, ele apareceria sozinho na tela do
    mantenedor sem ninguém ter escolhido isso.
    """
    consulta = Matricula.objects.filter(status__in=Matricula.STATUS_DE_GESTAO)
    if site_id:
        # Aplicado só quando VEIO: `.filter(site_id=None)` casaria com
        # `site_id IS NULL` e devolveria lista vazia — "nenhum aluno" para quem
        # tem alunos. É o mesmo erro que a fila já recusou.
        consulta = consulta.filter(site_id=site_id)
    if status:
        consulta = consulta.filter(status=status)
    return consulta.order_by("-enrolled_at")


def como_o_painel_ve(matricula: Matricula) -> dict:
    """A forma que as duas portas do painel devolvem — uma função só.

    Duas montagens à mão da mesma forma divergem no primeiro campo novo, e o
    contrato declara as duas idênticas de propósito.
    """
    return {
        "id": str(matricula.pk),
        "site_id": matricula.site_id,
        "email": matricula.email,
        "nome_completo": matricula.name,
        "whatsapp": matricula.whatsapp,
        "turma": matricula.turma or None,
        "comprou_em": (
            matricula.comprou_em.isoformat() if matricula.comprou_em else None
        ),
        "status": matricula.status,
        # DERIVADO do prefixo, nunca de um campo próprio: um campo "origem"
        # gravado seria um segundo lugar guardando o que o `order_id` já diz, e
        # os dois discordariam no primeiro backfill.
        "origem": (
            "liberado"
            if matricula.order_id.startswith(Matricula.PREFIXO_DA_FILA)
            else "comprou"
        ),
        "criada_em": matricula.enrolled_at.isoformat(),
    }


#: Os campos que o formulário do painel pode corrigir — e SÓ eles.
#: `email` fica de fora porque é a IDENTIDADE da linha: trocá-lo moveria a
#: matrícula, em silêncio, para outra pessoa. `site_id`/`order_id`/`product_id`
#: vêm do fato que criou a linha, e editá-los seria reescrever o que aconteceu.
CAMPOS_CORRIGIVEIS = {
    "nome_completo": "name",
    "whatsapp": "whatsapp",
    "turma": "turma",
    "comprou_em": "comprou_em",
}


def atualizar_matricula(
    *, id_da_linha: str, mudancas: dict, decidido_por: str
) -> "tuple[Matricula | None, str]":
    """Muda o estado de um aluno, ou corrige os dados dele.

    Devolve `(linha, "ok")`, `(None, "nao-encontrada")`, `(None, "na-fila")` ou
    `(None, "nada-a-mudar")`.

    **Linha da FILA responde `na-fila`, e a recusa é o desenho.** Aquelas se
    decidem por `POST /pre-matriculas/{id}/decisao`, que confere se a decisão
    já foi tomada e grava o motivo da recusa. Deixar esta porta mexer nelas
    daria dois caminhos para o mesmo fato, com regras diferentes — e o segundo
    caminho não saberia nada sobre motivo nem sobre "já decidida".
    """
    with transaction.atomic():
        try:
            linha = Matricula.objects.select_for_update().get(pk=id_da_linha)
        except (Matricula.DoesNotExist, ValueError, TypeError):
            # ValueError/TypeError: id que nem número é — "não existe linha com
            # este id" é a resposta honesta, não um 500.
            return None, "nao-encontrada"

        if linha.status in Matricula.STATUS_DA_FILA:
            return None, "na-fila"

        campos = []
        novo_status = mudancas.get("status")
        if novo_status and novo_status != linha.status:
            linha.status = novo_status
            campos.append("status")

        for nome_no_contrato, nome_no_modelo in CAMPOS_CORRIGIVEIS.items():
            if nome_no_contrato not in mudancas:
                continue
            valor = mudancas[nome_no_contrato]
            if nome_no_modelo in ("turma", "whatsapp", "name"):
                valor = (valor or "").strip()
            if getattr(linha, nome_no_modelo) == valor:
                continue
            setattr(linha, nome_no_modelo, valor)
            campos.append(nome_no_modelo)

        if not campos:
            # 422 e não 200: um formulário que não mudou nada quase sempre é um
            # formulário que não chegou como a pessoa achou que chegou.
            return None, "nada-a-mudar"

        linha.decidido_em = timezone.now()
        linha.decidido_por = decidido_por
        campos += ["decidido_em", "decidido_por"]
        linha.save(update_fields=campos)
        return linha, "ok"
