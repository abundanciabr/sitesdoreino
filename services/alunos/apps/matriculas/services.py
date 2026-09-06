# apps/matriculas/services.py
import uuid

from django.db import IntegrityError, transaction
from django.utils import timezone

from .eventos import carta_de_situacao, fato_de_situacao
from .models import Matricula
from .tasks import relay_apos_commit


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
                # [FATO] Nasceu ativa: e a matricula que a compra criou, e o
                # unico caminho pelo qual uma VENDA chega ao livro de fatos.
                fato_de_situacao(nova)
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

    Devolve `(None, False)` quando o e-mail não pode entrar na fila (vira 409
    na porta). São DUAS razões, e a distinção é a decisão:

    · **já tem matrícula que vale** — quem já entra na Caixa não precisa de
      fila. Esta metade continua derivando de `STATUS_QUE_VALEM`: se as duas
      divergissem, existiria gente recusada na fila por "você já tem acesso"
      que a Caixa não deixa entrar.
    · **foi reembolsado** (31/08/2026,
      `docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`) — o mantenedor
      decidiu que quem recebeu o dinheiro de volta não pede para voltar
      sozinho. Aqui a pessoa realmente não entra e realmente não pede, e isso
      NÃO é o beco que o parágrafo acima teme: a tela dela nomeia o reembolso e
      diz o que fazer (comprar de novo, ou falar com a escola). Beco explicado
      é decisão; beco mudo é defeito.

    A recusa mora aqui, e não só na tela que esconde o formulário: um POST
    direto na porta furaria uma regra que só existisse em template.

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
        antes = linha.status
        for campo, valor in campos.items():
            setattr(linha, campo, valor)
        linha.save(update_fields=list(campos))
        # [FATO] Quem foi recusado e reenvia volta para `aguardando`, e isso e
        # uma mudanca de situacao como qualquer outra. Mora AQUI e nao nos dois
        # chamadores (o caminho normal e o de perder a corrida) para nenhum dos
        # dois poder esquecer.
        fato_de_situacao(linha, anterior=antes)
        return linha

    with transaction.atomic():
        if Matricula.objects.filter(
            email=email, status__in=Matricula.STATUS_QUE_BARRAM_A_FILA
        ).exists():
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
                # [FATO] Nasceu aguardando: alguem pediu entrada pela sala de
                # espera. E o caminho dos alunos das turmas anteriores.
                fato_de_situacao(nova)
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


#: [AVISO] Os estados que DÃO acesso — a lista que decide se uma mudança merece
#: carta. É a mesma pergunta de `STATUS_QUE_VALEM`, e por isso ela é reusada em
#: vez de reescrita: duas listas do que "dá acesso" divergiriam no primeiro
#: estado novo, e o efeito seria alguém virar aluno sem ser avisado.
#:
#: **A regra é uma só: avisa quando a pessoa PASSA a ter acesso e antes não
#: tinha.** Foi a escolha do mantenedor em 29/08/2026 ("liberei você"), e ela
#: cobre os dois caminhos que levam ao mesmo lugar — a decisão da fila e o
#: religar de quem estava pausado. Perder acesso NÃO gera carta: quem está
#: pausado ou encerrado não consegue abrir a página de avisos (ela mora dentro
#: da Caixa, e a Caixa só abre para aluno), então a carta seria escrita e nunca
#: lida. Está registrado no livro, com a bifurcação, para o dia em que a página
#: de avisos mudar de casa.
def ganhou_acesso(anterior: str, novo: str) -> bool:
    return novo in Matricula.STATUS_QUE_VALEM and anterior not in (
        Matricula.STATUS_QUE_VALEM
    )


def decidir_na_fila(
    *,
    id_da_linha: str,
    decisao: str,
    decidido_por: str,
    motivo: str = "",
    product_id: str = "",
    destinatario_id: str = "",
) -> tuple[Matricula | None, str]:
    """[FILA] Liberar ou recusar quem está na fila.

    Devolve `(linha, "ok")`, `(None, "nao-encontrada")`, `(None, "ja-decidida")`
    ou `(None, "sem-curso")`.

    Só enxerga linhas nascidas na fila (prefixo `pre:` no order_id). Uma matrícula
    PAGA é `nao-encontrada` aqui de propósito: esta porta não é caminho para
    mexer no status de quem comprou — para isso existiria outra, com outro rito.

    [INV-ALU-C1] LIBERAR EXIGE O CURSO, E A RECUSA MORA AQUI
    --------------------------------------------------------
    `docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md` (06/09/2026): ninguém é
    aluno do site, todo mundo é aluno de UM curso, e a matrícula é o que diz
    qual. Liberar sem dizer o curso cria a matrícula ativa que obriga a próxima
    tela a adivinhar, e o palpite mais provável ("o primeiro curso do site") é
    exatamente o defeito que a lei existe para impedir.

    A recusa mora nesta função, e não só na porta HTTP, porque esta é a ÚNICA
    passagem por onde uma linha da fila vira `ativa`: um chamador novo dentro da
    célula herda a exigência sem escolher nada. A checagem de `motivo`, que fica
    na porta, é de outra natureza — aquela traduz o `required` do payload; esta
    sustenta um invariante da tabela.

    Ela vem ANTES de procurar a linha, de propósito: "faltou dizer o curso" é
    verdade sobre o PEDIDO, não sobre a linha, então não depende de a linha
    existir. E o efeito colateral é bom: um id inexistente com pedido incompleto
    é respondido sem confirmar se aquele id existe.

    `recusar` não pede curso: ninguém vira aluno, e exigir a escolha de um curso
    para dizer "não" seria burocracia sem fato por trás. `product_id` mandado
    junto de uma recusa é ignorado, do mesmo jeito que `motivo` numa liberação.

    O QUE ESTE GUARDA NÃO ALCANÇA, e está dito na cara: a matrícula que nasce do
    EVENTO de pagamento. `pagamento.aprovado.v1` não carrega `product_id`
    (`contracts/eventos/`), então `handlers.py` grava `""` — e essa linha nasce
    `ativa` sem curso sem passar por aqui. Fechar isso é Rito de Contrato no
    evento, que é de outra célula. Ver [INV-ALU-C1] em `INVARIANTES.md`.
    """
    if decisao == "liberar" and not product_id:
        return None, "sem-curso"

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
        antes = linha.status
        linha.status = Matricula.STATUS_ATIVA if liberou else Matricula.STATUS_RECUSADA
        linha.decidido_em = timezone.now()
        linha.decidido_por = decidido_por
        linha.motivo_recusa = "" if liberou else motivo
        # [INV-ALU-C1] O curso entra JUNTO com o status que dá acesso, na mesma
        # transação e no mesmo `save`: uma segunda escrita depois abriria uma
        # janela, por menor que fosse, em que a linha está `ativa` sem curso.
        # Recusa não grava curso — quem foi recusado não é aluno de nada.
        if liberou:
            linha.product_id = product_id
        linha.save(
            update_fields=[
                "status",
                "decidido_em",
                "decidido_por",
                "motivo_recusa",
                "product_id",
            ]
        )

        # [AVISO] A carta nasce na MESMA transação do fato — é o que a outbox
        # garante e o que `emitir()` recusa fazer de outro jeito. Sem
        # `destinatario_id` não há para quem endereçar (a pessoa nunca entrou
        # com o Google, ou a `identidade` não respondeu), e a ausência da carta
        # é o comportamento correto: o acesso foi liberado do mesmo jeito, e ela
        # vê a mudança na próxima vez que abrir o site.
        # [FATO] SEMPRE, e antes da carta: liberar e recusar sao os dois
        # desfechos da fila, e o livro precisa dos dois. A carta so sai num
        # deles, e so para quem tem identidade da plataforma.
        fato_de_situacao(linha, anterior=antes, ator_id=decidido_por)

        if destinatario_id and ganhou_acesso(antes, linha.status):
            carta_de_situacao(
                site_id=linha.site_id,
                destinatario_id=destinatario_id,
                matricula_id=str(linha.pk),
                situacao_nova=linha.status,
                situacao_anterior=antes,
                decidido_por=decidido_por,
            )
            transaction.on_commit(relay_apos_commit)

        return linha, "ok"


def apagar_recusado(*, id_da_linha: str) -> str:
    """[APAGAR-RECUSADO] Apaga de vez um pedido RECUSADO — nunca quem ja foi aluno.

    `docs/decisoes/DECISAO-apagar-recusado-definitivamente.md` (03/09/2026):
    reverte, SO para esta fatia, a `DECISAO-a-ficha-nao-se-apaga.md`. Devolve
    `"ok"`, `"nao-encontrada"` ou `"nao-recusada"`.

    A MESMA fronteira de `decidir_na_fila`: so enxerga linhas nascidas na fila
    (prefixo `pre:` no order_id). Uma matricula REAL e `"nao-encontrada"` aqui
    de proposito — o filtro por prefixo a exclui antes mesmo de olhar o
    status, entao esta funcao NUNCA chega perto de quem ja teve acesso.

    `"nao-recusada"` cobre quem ainda esta `aguardando`: apagar antes da
    decisao apagaria a propria decisao, e nao so o pedido.
    """
    with transaction.atomic():
        try:
            linha = (
                Matricula.objects.select_for_update()
                .filter(order_id__startswith=Matricula.PREFIXO_DA_FILA)
                .get(pk=id_da_linha)
            )
        except (Matricula.DoesNotExist, ValueError, TypeError):
            # ValueError/TypeError: id que nem numero e — "nao existe linha com
            # este id" e a resposta honesta, nao um 500.
            return "nao-encontrada"

        if linha.status != Matricula.STATUS_RECUSADA:
            return "nao-recusada"

        linha.delete()
        return "ok"


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
# [EX-ALUNO] Acrescentadas em 28/08/2026
# (`docs/decisoes/DECISAO-ex-aluno-e-a-porta-que-explica.md`). Os ESTADOS já
# existiam e já bloqueavam desde a manhã; o que faltava era o sistema saber
# DIZÊ-LOS. Até então os dois voltavam como `cadastrado` — mentira sobre a
# pessoa, e a causa de quem saiu da escola ver o formulário de pedir entrada
# como se nunca tivesse pedido nada.
CATEGORIA_PAUSADO = "pausado"
CATEGORIA_EX_ALUNO = "ex_aluno"
# [REEMBOLSO] Acrescentada em 31/08/2026
# (`docs/decisoes/DECISAO-reembolso-tira-o-acesso.md`), pela MESMA razao das
# duas de cima: sem ela o reembolsado voltaria como `cadastrado`, e veria o
# formulário de pedir entrada como se nunca tivesse tido ficha nenhuma.
CATEGORIA_REEMBOLSADO = "reembolsado"

#: Ficha que não dá acesso ⇒ a categoria que a tela precisa mostrar. Não é o
#: mesmo que `STATUS_SEM_ACESSO`: aquele responde "pode entrar?", este responde
#: "o que eu digo para a pessoa?". A fila fica de fora porque tem resposta
#: própria (com dias de espera e motivo).
_CATEGORIA_POR_STATUS_SEM_ACESSO = {
    Matricula.STATUS_SUSPENSA: CATEGORIA_PAUSADO,
    Matricula.STATUS_ENCERRADA: CATEGORIA_EX_ALUNO,
    Matricula.STATUS_REEMBOLSADA: CATEGORIA_REEMBOLSADO,
}


def situacao_de(email: str) -> dict:
    """[CATEGORIAS] Em que categoria esta pessoa está — a resposta ÚNICA.

    Existe para que a home, a Caixa e o painel parem de adivinhar cada um do
    seu jeito: até 28/08/2026 eram quatro respostas para a mesma pergunta, e
    três erravam em pelo menos um caso.

    **A ordem é a decisão, e ela é "o mais acionável primeiro":** aluno, fila,
    pausado, ex-aluno, cadastrado. Quem está esperando uma decisão do
    mantenedor vem antes de quem já recebeu uma — na fila há algo acontecendo
    do outro lado; em "pausado" e "ex-aluno", não.

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
        # [EX-ALUNO] Ninguém na fila — mas pode haver uma ficha que existe e
        # não dá acesso. A ORDEM é "o mais acionável primeiro": quem está
        # esperando uma decisão sua vem antes de quem já recebeu uma, porque é
        # a fila que tem algo acontecendo do outro lado.
        parada = (
            Matricula.objects.filter(
                email=email, status__in=list(_CATEGORIA_POR_STATUS_SEM_ACESSO)
            )
            .order_by("-enrolled_at")
            .first()
        )
        if parada is not None:
            return {
                "categoria": _CATEGORIA_POR_STATUS_SEM_ACESSO[parada.status],
                "na_fila": None,
            }
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
        # DERIVADO do prefixo, nunca de um campo proprio. A regra mora no
        # MODELO desde 05/09/2026, porque o evento `matricula.situacao-alterada`
        # tambem a le: duas derivacoes discordariam no primeiro backfill.
        "origem": matricula.origem(),
        "criada_em": matricula.enrolled_at.isoformat(),
        "virou_aluno_em": matricula.virou_aluno_em(),
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
    *, id_da_linha: str, mudancas: dict, decidido_por: str, destinatario_id: str = ""
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
        antes = linha.status
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

        # [FATO] SEMPRE: suspender, encerrar e reembolsar sao mudancas que
        # NUNCA geram carta (a pessoa perde acesso, e a pagina de avisos mora
        # dentro da Caixa) e sao exatamente as que o livro de fatos precisa
        # para contar a vida de um aluno ao longo do tempo.
        fato_de_situacao(linha, anterior=antes, ator_id=decidido_por)

        # [AVISO] O MESMO gesto da fila, pelo outro caminho: religar quem estava
        # pausado também é "liberei você", e a pessoa precisa saber disso do
        # mesmo jeito. A regra é uma só (`ganhou_acesso`) e mora num lugar só —
        # duas cópias divergiriam no primeiro estado novo, e o efeito seria
        # alguém virar aluno por uma porta e não ser avisado.
        if destinatario_id and ganhou_acesso(antes, linha.status):
            carta_de_situacao(
                site_id=linha.site_id,
                destinatario_id=destinatario_id,
                matricula_id=str(linha.pk),
                situacao_nova=linha.status,
                situacao_anterior=antes,
                decidido_por=decidido_por,
            )
            transaction.on_commit(relay_apos_commit)

        return linha, "ok"


# --------------------------------------------------------------- [PRONTUARIO]
# `docs/decisoes/DECISAO-a-ficha-nao-se-apaga.md`, 29/08/2026. A lei que tirou do
# sistema a capacidade de apagar uma ficha decidiu, na mesma frase, que quem sai e
# volta ganha uma ficha NOVA a cada passagem — a antiga fica `encerrada`, com a
# data e o motivo da saida intactos.
#
# O ganho e a historia. O preco e que a mesma pessoa passa a ter mais de uma
# linha, e estas funcoes sao a resposta a esse preco: elas juntam por e-mail o
# que as fichas contam separadas.
#
# `apagar_matricula` MORREU AQUI no mesmo dia. Nao ha caminho, em lugar nenhum
# desta celula, que apague uma Matricula que ja deu acesso — e a porta
# `DELETE /matriculas/{id}` saiu do contrato junto. Guarda:
# `tests/test_a_ficha_nao_se_apaga.py`.
#
# [APAGAR-RECUSADO] Excecao aberta em 03/09/2026
# (`docs/decisoes/DECISAO-apagar-recusado-definitivamente.md`), que reverte a
# lei acima SO para quem nunca chegou a ser aluno: um pedido RECUSADO pode ser
# apagado de vez, pela funcao `apagar_recusado` abaixo. `apagar_matricula`
# continua sem existir — esta e uma funcao NOVA, com fronteira propria.


def como_o_prontuario_ve(matricula: Matricula) -> dict:
    """Uma PASSAGEM pela escola, como o prontuario a mostra.

    Reusa `como_o_painel_ve` em vez de remontar a forma: os campos comuns tem
    uma fonte so, e o dia em que um deles mudar de nome nao deixa duas telas
    discordando sobre a mesma ficha.

    O `email` sai da passagem de proposito: ele e da PESSOA, e no prontuario
    aparece uma vez, no topo. Repeti-lo em cada linha sugeriria que ele poderia
    ser diferente entre elas — e a porta que edita ficha recusa mexer nele
    exatamente porque ele e a identidade.
    """
    forma = como_o_painel_ve(matricula)
    forma.pop("email")
    forma.update(
        {
            "decidido_em": (
                matricula.decidido_em.isoformat() if matricula.decidido_em else None
            ),
            "decidido_por": matricula.decidido_por,
            "motivo_recusa": matricula.motivo_recusa,
        }
    )
    return forma


def prontuario_de(email: str) -> dict:
    """A historia inteira de uma pessoa nesta escola — a resposta agrupada.

    Ordem CRESCENTE, ao contrario das outras listas desta celula: aqui se le uma
    historia, e historia se conta na ordem em que aconteceu.

    A `categoria` NAO e recalculada aqui: e a mesma `situacao_de` que responde
    `GET /alunos/{email}/situacao` para a plataforma inteira. Uma segunda conta
    divergiria no primeiro status novo, e o prontuario passaria a dizer uma coisa
    enquanto a porta da Caixa diz outra sobre a MESMA pessoa.

    Sem ficha nenhuma devolve `passagens: []` e os campos vazios — nunca um erro.
    "Nao conheco esta pessoa" e uma resposta, e quem chama precisa poder mostra-la
    sem traduzir exceçao em tela.
    """
    email = email.strip().lower()
    # A MESMA string normalizada vai para as duas consultas. Se uma normalizasse
    # e a outra nao, existiria o caso de um prontuario com fichas listadas e
    # `categoria: cadastrado` — a tela diria "nunca esteve aqui" logo acima da
    # historia dela.
    fichas = list(Matricula.objects.filter(email=email).order_by("enrolled_at"))
    recente = fichas[-1] if fichas else None
    return {
        "email": email,
        "categoria": situacao_de(email)["categoria"],
        # Da passagem MAIS RECENTE, e nao da primeira: quem volta anos depois
        # pode ter mudado de nome ou de telefone, e o que o mantenedor precisa
        # para falar com a pessoa e o dado de hoje.
        "nome_completo": recente.name if recente else "",
        "whatsapp": recente.whatsapp if recente else "",
        "turma": (recente.turma or None) if recente else None,
        "comprou_em": (
            recente.comprou_em.isoformat() if recente and recente.comprou_em else None
        ),
        "passagens": [como_o_prontuario_ve(m) for m in fichas],
    }


def passado_de_quem_espera(linhas) -> dict:
    """Para cada linha da fila, o que a pessoa JA VIVEU aqui antes dela.

    Devolve `{pk_da_linha: {ja_foi_aluno, passagens_anteriores, saiu_em}}`.

    UMA consulta para a fila inteira, e nao uma por linha: a fila e uma tela que
    o mantenedor abre o dia todo, e um N+1 aqui e o tipo de lentidao que so
    aparece quando a fila cresce — ou seja, exatamente quando ela importa.

    "Ja foi aluno" NAO e "tem outra ficha": quem foi recusado tres vezes tem tres
    fichas e nunca entrou. A pergunta e respondida por
    `STATUS_QUE_JA_DERAM_ACESSO`, uma lista de permissao.
    """
    linhas = list(linhas)
    if not linhas:
        return {}

    emails = {m.email for m in linhas}
    ids_agora = {m.pk for m in linhas}
    anteriores = Matricula.objects.filter(email__in=emails).exclude(pk__in=ids_agora)

    # `saiu_em` viaja como DATETIME por dentro e vira texto so na saida.
    # Comparar as datas em ISO funcionaria hoje — todas vem do banco em UTC, com
    # o mesmo formato — e e o tipo de coisa que a proxima sessao copia para um
    # lugar onde os formatos NAO sao iguais. Ordenar tempo comparando texto e
    # correto por acidente; comparar datetime e correto por construcao.
    por_email: dict[str, dict] = {}
    for m in anteriores:
        resumo = por_email.setdefault(
            m.email,
            {"ja_foi_aluno": False, "passagens_anteriores": 0, "saiu_em": None},
        )
        resumo["passagens_anteriores"] += 1
        if m.status in Matricula.STATUS_QUE_JA_DERAM_ACESSO:
            resumo["ja_foi_aluno"] = True
        if m.status == Matricula.STATUS_ENCERRADA and m.decidido_em:
            # A MAIS RECENTE das saidas: quem entrou e saiu tres vezes precisa
            # aparecer com a ultima, nao com a primeira.
            anterior = resumo["saiu_em"]
            if anterior is None or m.decidido_em > anterior:
                resumo["saiu_em"] = m.decidido_em

    vazio = {"ja_foi_aluno": False, "passagens_anteriores": 0, "saiu_em": None}
    resumos = {m.pk: dict(por_email.get(m.email, vazio)) for m in linhas}
    for resumo in resumos.values():
        if resumo["saiu_em"] is not None:
            resumo["saiu_em"] = resumo["saiu_em"].isoformat()
    return resumos
