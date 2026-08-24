# tests/test_inv_aviso_nasce_com_o_status.py  # [RECEITA:R5 v1]
"""INV-SUG08 — o aviso do autor e a mudança de status são UMA transação.

O EVO-21 acrescenta um terceiro par ao `transaction.atomic()` que o EVO-13
abriu, e o invariante tem as duas metades de sempre — só que aqui a segunda é a
que ninguém escreve:

1. **Rollback não deixa aviso órfão.** É a metade fácil, e ela continua verde
   mesmo se alguém mover a criação do aviso para DEPOIS do `with`.
2. **Aviso que não pode nascer desfaz a mudança.** É a metade que pega esse
   erro: com a escrita do aviso explodindo, a única coisa que separa "status
   mudado e aluno sem saber" de "nada aconteceu" é o `atomic`.

**Por que isto não passa pelo Redis, embora o `sugestao.status-alterado` já
exista (EVO-20) e carregue o `autor_da_sugestao_id`.** Consumir o próprio evento
para escrever na própria tabela mandaria o fato dar uma volta pela rede para
voltar ao ponto de partida — e traria de graça um modo de falha ("Redis fora do
ar ⇒ status mudado e aluno sem aviso, sem nada indicando a falta"), atraso e,
pior, a possibilidade de status e aviso divergirem. O evento existe para o mundo
de FORA (gamificação, analytics, que nascem depois); o aviso é de dentro. Há
guarda para essa independência aqui embaixo:
`test_o_aviso_nasce_mesmo_sem_redis_nenhum`.
"""

import pytest
from django.db import transaction
from django.urls import reverse

from apps.core.avisos import AvisoForaDaTransacao, avisar_o_autor
from apps.sugestoes import eventos
from apps.sugestoes.models import Aviso, HistoricoStatus, Sugestao

pytestmark = pytest.mark.django_db


def _mudar(equipe, sugestao, status, nota=""):
    return equipe.client.post(
        reverse("mudar_status", args=[sugestao.id]), {"status": status, "nota": nota}
    )


def test_mudar_o_status_deixa_exatamente_um_aviso_para_o_autor(equipe, sugestao):
    resposta = _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "entra na trilha 2")

    assert resposta.status_code == 302, resposta.content
    aviso = Aviso.objects.get()
    assert aviso.destinatario_id == sugestao.autor_id
    assert aviso.sugestao_id == sugestao.id
    assert aviso.status_anterior == Sugestao.Status.EM_ANALISE
    assert aviso.status_novo == Sugestao.Status.PLANEJADO
    assert aviso.nota == "entra na trilha 2"
    assert aviso.lido_em is None


def test_o_aviso_nao_vai_para_quem_moderou(equipe, sugestao):
    """Quem recebe é quem SUGERIU. Quem moderou fica no `HistoricoStatus`."""
    _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "saiu na v1.4")

    destinatarios = list(Aviso.objects.values_list("destinatario_id", flat=True))
    assert destinatarios == [sugestao.autor_id]
    assert equipe.identidade.id not in destinatarios


def test_toda_linha_do_historico_tem_o_aviso_dela(equipe, sugestao):
    """A igualdade sem ressalva: uma mudança registrada ⇒ um aviso.

    Inclusive quando o status escolhido é o MESMO de agora — o EVO-13 aceita
    esse caso de propósito (metade do valor do formulário é a nota), e o aluno
    precisa receber justamente essa nota.
    """
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO)
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "seguimos analisando")
    _mudar(equipe, sugestao, Sugestao.Status.NAO_PLANEJADO, "não cabe na trilha")

    assert HistoricoStatus.objects.count() == 3
    passos = list(Aviso.objects.order_by("id").values_list("status_novo", "nota"))
    assert passos == [
        (Sugestao.Status.PLANEJADO, ""),
        (Sugestao.Status.PLANEJADO, "seguimos analisando"),
        (Sugestao.Status.NAO_PLANEJADO, "não cabe na trilha"),
    ]


def test_se_o_AVISO_nao_puder_nascer_o_status_nao_muda(equipe, sugestao, monkeypatch):
    """A metade que ninguém escreve: aviso impossível ⇒ mudança desfeita.

    `Aviso.save` é o ponto exato onde `objects.create()` toca o banco. Com ele
    explodindo, um aviso criado FORA do `atomic` — ou depois dele — deixaria o
    status já commitado e o aluno sem saber de nada. É esse desenho que este
    teste falsifica.
    """

    def explodir(self, *args, **kwargs):
        raise RuntimeError("o banco caiu no meio da gravação do aviso")

    monkeypatch.setattr(Aviso, "save", explodir)

    with pytest.raises(RuntimeError):
        _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "vai dar errado")

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE, (
        "o status mudou sem o aviso nascer — as duas escritas precisam estar na "
        "MESMA transação."
    )
    assert HistoricoStatus.objects.count() == 0
    assert Aviso.objects.count() == 0


def test_o_rollback_da_transacao_nao_deixa_aviso_orfao(equipe, sugestao, monkeypatch):
    """A outra ponta: o que falha é a emissão do evento, DEPOIS do aviso.

    Se o aviso estivesse fora da transação (ou ela não existisse), ele
    sobreviveria a este rollback e a Caixa passaria a dizer ao aluno que a ideia
    dele andou quando ela não andou.
    """

    def explodir(*args, **kwargs):
        raise RuntimeError("a outbox caiu depois de o aviso ser gravado")

    monkeypatch.setattr(eventos, "emitir", explodir)

    with pytest.raises(RuntimeError):
        _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "vai dar errado")

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert Aviso.objects.count() == 0, "sobrou aviso de uma transação revertida"


@pytest.mark.django_db(transaction=True)
def test_avisar_o_autor_recusa_ser_chamada_fora_de_uma_transacao(sugestao):
    """Lei 1: em vez de confiar que todo ponto futuro lembre do `atomic`, a
    própria função recusa a escrita — como `eventos.emitir()` desde o EVO-20.

    `transaction=True` é obrigatório aqui: no `django_db` padrão TODO teste já
    roda dentro de um atomic, a recusa nunca dispararia e o guarda ficaria verde
    sem medir nada (é a `armadilhas/057` pelo avesso, a mesma pegadinha que o
    EVO-20 pagou).
    """
    with pytest.raises(AvisoForaDaTransacao):
        avisar_o_autor(
            sugestao=sugestao,
            status_anterior=Sugestao.Status.EM_ANALISE,
            status_novo=Sugestao.Status.PLANEJADO,
        )

    assert Aviso.objects.count() == 0

    # E dentro da transação a mesma chamada grava normalmente — sem isto, o
    # guarda acima passaria também se a função tivesse virado um `raise` seco.
    with transaction.atomic():
        avisar_o_autor(
            sugestao=sugestao,
            status_anterior=Sugestao.Status.EM_ANALISE,
            status_novo=Sugestao.Status.PLANEJADO,
        )
    assert Aviso.objects.count() == 1


@pytest.mark.django_db(transaction=True)
def test_o_aviso_nasce_mesmo_sem_redis_nenhum(equipe, sugestao, monkeypatch):
    """A independência do fio, medida — não argumentada.

    `transaction=True` porque é a única forma de o `on_commit` do relay disparar
    de verdade (`armadilhas/057`); sem `REDIS_STREAMS_URL`, o relay estoura, o
    `relay_apos_commit` engole e o evento fica PENDENTE na outbox. Se o aviso
    dependesse do fio, ele não existiria — e é isso que se falsifica aqui.
    """
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)

    assert _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO).status_code == 302

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.PLANEJADO
    assert Aviso.objects.filter(destinatario_id=sugestao.autor_id).count() == 1
