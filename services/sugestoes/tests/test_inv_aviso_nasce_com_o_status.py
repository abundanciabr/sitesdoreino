# tests/test_inv_aviso_nasce_com_o_status.py  # [RECEITA:R5 v1]
"""Os avisos dos interessados e a mudança de status são uma só transação.
Rollback não deixa aviso órfão e aviso que falha desfaz a mudança."""

import pytest
from django.db import transaction
from django.urls import reverse

from apps.core.avisos import AvisoForaDaTransacao, avisar_os_interessados
from apps.sugestoes import eventos
from apps.sugestoes.models import Aviso, HistoricoStatus, OutboxEvent, Sugestao, Voto

pytestmark = pytest.mark.django_db


def _mudar(equipe, sugestao, status, nota=""):
    """Muda o status pelo contrato do Admin, como a jornada de moderação de hoje."""
    return equipe.gestao.mudar_status(equipe, sugestao, status, nota=nota)


def _vinculos_por_pessoa(sugestao=None) -> dict[str, str]:
    """Quem recebeu → com que vínculo; erra alto se alguém recebeu duas vezes."""
    linhas = Aviso.objects.all()
    if sugestao is not None:
        linhas = linhas.filter(sugestao=sugestao)
    pares = list(linhas.values_list("destinatario_id", "vinculo"))
    quem = [destinatario_id for destinatario_id, _ in pares]
    assert len(quem) == len(set(quem)), (
        f"alguém recebeu mais de um aviso da MESMA mudança de status: {quem}. "
        "Interessados são DISTINTOS — quem é autor, votou e comentou recebe um."
    )
    return dict(pares)


def test_mudar_o_status_deixa_exatamente_um_aviso_para_o_autor(equipe, sugestao):
    """Sem plateia, o único aviso é do autor."""
    resposta = _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "entra na trilha 2")

    assert resposta.status_code == 200, resposta.content
    aviso = Aviso.objects.get()
    assert aviso.destinatario_id == sugestao.autor_id
    assert aviso.sugestao_id == sugestao.id
    assert aviso.status_anterior == Sugestao.Status.EM_ANALISE
    assert aviso.status_novo == Sugestao.Status.PLANEJADO
    assert aviso.nota == "entra na trilha 2"
    assert aviso.lido_em is None
    assert aviso.vinculo == Aviso.Vinculo.AUTOR


# O leque: todos os que interagiram, uma vez cada, dizendo de onde veio


def test_o_leque_alcanca_o_autor_quem_votou_e_quem_comentou(equipe, sugestao, plateia):
    """Três votantes, dois comentaristas e o autor: seis avisos, um por pessoa."""
    gente = plateia(sugestao, votantes=3, comentaristas=2)

    assert (
        _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "vai sair").status_code
        == 200
    )

    vinculos = _vinculos_por_pessoa()
    assert len(vinculos) == 6, vinculos
    assert vinculos[sugestao.autor_id] == Aviso.Vinculo.AUTOR
    for pessoa in gente["votaram"]:
        assert vinculos[pessoa.id] == Aviso.Vinculo.VOTO
    for pessoa in gente["comentaram"]:
        assert vinculos[pessoa.id] == Aviso.Vinculo.COMENTARIO

    # E a nota da equipe alcança TODO mundo — é o ponto da decisão: o "não vamos
    # fazer, e por quê" é para quem se importou, não só para quem escreveu.
    assert set(Aviso.objects.values_list("nota", flat=True)) == {"vai sair"}


def test_quem_acumula_os_tres_papeis_recebe_UM_aviso_so(equipe, sugestao, plateia):
    """Quem é autor, votou e comentou recebe um aviso só, com o vínculo mais forte."""
    from apps.sugestoes.models import Comentario

    Voto.objects.create(sugestao=sugestao, autor_id=sugestao.autor_id)
    Comentario.objects.create(
        sugestao=sugestao, autor_id=sugestao.autor_id, texto="reforçando"
    )
    plateia(sugestao, votantes=2)

    assert (
        _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "saiu").status_code
        == 200
    )

    vinculos = _vinculos_por_pessoa()
    assert len(vinculos) == 3, vinculos
    assert vinculos[sugestao.autor_id] == Aviso.Vinculo.AUTOR


def test_quem_votou_E_comentou_recebe_um_aviso_com_o_vinculo_do_comentario(
    equipe, sugestao
):
    """Quem votou e comentou recebe um aviso, com o vínculo do comentário."""
    from apps.sugestoes.models import Comentario, Identidade

    pessoa = Identidade.objects.create(email="ambos@exemplo.test", nome_exibido="Ambos")
    Voto.objects.create(sugestao=sugestao, autor=pessoa)
    Comentario.objects.create(sugestao=sugestao, autor=pessoa, texto="isso mesmo")

    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO)

    vinculos = _vinculos_por_pessoa()
    assert len(vinculos) == 2, vinculos
    assert vinculos[pessoa.id] == Aviso.Vinculo.COMENTARIO


def test_a_jornada_de_verdade_bota_quem_votou_e_quem_comentou_no_leque(
    equipe, entrar_como, sugestao
):
    """O clique real de votar e comentar entra no leque."""
    quem_votou = entrar_como(email="votante@exemplo.test", nome="Votante")
    quem_comentou = entrar_como(email="comentarista@exemplo.test", nome="Comentarista")

    assert (
        quem_votou.client.post(reverse("votar", args=[sugestao.id])).status_code == 302
    )
    assert (
        quem_comentou.client.post(
            reverse("comentar", args=[sugestao.id]), {"texto": "Também preciso disso."}
        ).status_code
        == 302
    )

    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "boa ideia")

    vinculos = _vinculos_por_pessoa()
    assert vinculos[quem_votou.identidade.id] == Aviso.Vinculo.VOTO
    assert vinculos[quem_comentou.identidade.id] == Aviso.Vinculo.COMENTARIO


def test_o_vinculo_sobrevive_ao_desvoto(equipe, entrar_como, sugestao):
    """O vínculo é gravado na linha: tirar o voto depois não muda o aviso."""
    votante = entrar_como(email="voltou-atras@exemplo.test", nome="Voltou Atrás")
    votante.client.post(reverse("votar", args=[sugestao.id]))
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "entrou na trilha")

    aviso = Aviso.objects.get(destinatario_id=votante.identidade.id)
    assert aviso.vinculo == Aviso.Vinculo.VOTO

    assert (
        votante.client.post(reverse("desvotar", args=[sugestao.id])).status_code == 302
    )
    assert not Voto.objects.filter(autor_id=votante.identidade.id).exists()

    aviso.refresh_from_db()
    assert aviso.vinculo == Aviso.Vinculo.VOTO, (
        "o aviso mudou de explicação porque a pessoa desvotou — o `Aviso` é "
        "snapshot, nunca espelho de estado mutável."
    )


def test_o_aviso_e_a_carta_dizem_de_onde_veio_cada_um(equipe, dentro, sugestao):
    """O vínculo vai na linha `Aviso` e na carta: voto para quem votou."""
    Voto.objects.create(sugestao=sugestao, autor=dentro.identidade)
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "vamos fazer")

    aviso = Aviso.objects.get(destinatario=dentro.identidade)
    assert aviso.vinculo == Aviso.Vinculo.VOTO
    assert not Aviso.objects.filter(
        destinatario=dentro.identidade, vinculo=Aviso.Vinculo.AUTOR
    ).exists()
    carta = OutboxEvent.objects.get(
        event=eventos.NOTIFICACAO_DEVIDA,
        payload__destinatario_id=dentro.identidade.id_da_plataforma,
    )
    assert carta.payload["parametros"]["vinculo"] == Aviso.Vinculo.VOTO


def test_moderar_nao_e_interagir_e_o_aviso_nao_vai_por_isso(equipe, sugestao):
    """Quem recebe é quem interagiu; quem moderou fica só no `HistoricoStatus`."""
    _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "saiu na v1.4")

    destinatarios = list(Aviso.objects.values_list("destinatario_id", flat=True))
    assert destinatarios == [sugestao.autor_id]
    assert equipe.identidade.id not in destinatarios


def test_quem_modera_E_votou_recebe_pelo_voto(equipe, sugestao):
    """Sem ramo especial: quem moderou e votou recebe pelo voto."""
    Voto.objects.create(sugestao=sugestao, autor=equipe.identidade)

    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "eu mesmo pedi isso")

    vinculos = _vinculos_por_pessoa()
    assert vinculos[equipe.identidade.id] == Aviso.Vinculo.VOTO


def test_toda_linha_do_historico_tem_o_aviso_de_CADA_interessado(
    equipe, sugestao, plateia
):
    """Uma mudança dá um aviso por interessado, até com o mesmo status.
    Três mudanças e três pessoas dão 9 avisos."""
    plateia(sugestao, votantes=1, comentaristas=1)

    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO)
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "seguimos analisando")
    _mudar(equipe, sugestao, Sugestao.Status.NAO_PLANEJADO, "não cabe na trilha")

    assert HistoricoStatus.objects.count() == 3
    assert Aviso.objects.count() == 9

    passos = sorted((nota, quantos) for nota, quantos in _contar_por_nota().items())
    assert passos == [
        ("", 3),
        ("não cabe na trilha", 3),
        ("seguimos analisando", 3),
    ]
    # E cada rodada foi para as três pessoas — não três vezes para a mesma.
    for nota in ("", "seguimos analisando", "não cabe na trilha"):
        quem = list(
            Aviso.objects.filter(nota=nota).values_list("destinatario_id", flat=True)
        )
        assert len(set(quem)) == 3, (nota, quem)


def _contar_por_nota() -> dict[str, int]:
    from django.db.models import Count

    return {
        linha["nota"]: linha["quantos"]
        for linha in Aviso.objects.values("nota").annotate(quantos=Count("id"))
    }


def test_se_os_AVISOS_nao_puderem_nascer_o_status_nao_muda(
    equipe, sugestao, plateia, monkeypatch
):
    """Se o `bulk_create` dos avisos falha, status e histórico não mudam."""
    plateia(sugestao, votantes=2, comentaristas=1)

    def explodir(*args, **kwargs):
        raise RuntimeError("o banco caiu no meio da gravação dos avisos")

    monkeypatch.setattr(Aviso.objects, "bulk_create", explodir)

    with pytest.raises(RuntimeError):
        _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "vai dar errado")

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE, (
        "o status mudou sem os avisos nascerem — as duas escritas precisam estar "
        "na MESMA transação."
    )
    assert HistoricoStatus.objects.count() == 0
    assert Aviso.objects.count() == 0


def test_o_rollback_da_transacao_nao_deixa_NENHUM_aviso_orfao(
    equipe, sugestao, plateia, monkeypatch
):
    """Se a emissão do evento falha depois dos avisos, nenhum aviso sobra."""
    plateia(sugestao, votantes=2, comentaristas=1)

    def explodir(*args, **kwargs):
        raise RuntimeError("a outbox caiu depois de os avisos serem gravados")

    monkeypatch.setattr(eventos, "emitir", explodir)

    with pytest.raises(RuntimeError):
        _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "vai dar errado")

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.EM_ANALISE
    assert Aviso.objects.count() == 0, "sobrou aviso de uma transação revertida"


@pytest.mark.django_db(transaction=True)
def test_avisar_os_interessados_recusa_ser_chamada_fora_de_uma_transacao(
    sugestao, plateia
):
    """A função recusa a escrita fora do `atomic` e grava normalmente dentro dele.
    `transaction=True` é preciso porque o `django_db` padrão já roda num atomic."""
    plateia(sugestao, votantes=1, comentaristas=1)

    with pytest.raises(AvisoForaDaTransacao):
        avisar_os_interessados(
            sugestao=sugestao,
            status_anterior=Sugestao.Status.EM_ANALISE,
            status_novo=Sugestao.Status.PLANEJADO,
        )

    assert Aviso.objects.count() == 0

    # E dentro da transação a mesma chamada grava normalmente — sem isto, o
    # guarda acima passaria também se a função tivesse virado um `raise` seco.
    with transaction.atomic():
        avisar_os_interessados(
            sugestao=sugestao,
            status_anterior=Sugestao.Status.EM_ANALISE,
            status_novo=Sugestao.Status.PLANEJADO,
        )
    assert Aviso.objects.count() == 3


@pytest.mark.django_db(transaction=True)
def test_os_avisos_nascem_mesmo_sem_redis_nenhum(
    equipe, sugestao, plateia, monkeypatch
):
    """Sem `REDIS_STREAMS_URL` os avisos nascem do mesmo jeito: o leque não depende do
    fio."""
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    plateia(sugestao, votantes=2, comentaristas=1)

    assert _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO).status_code == 200

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.PLANEJADO
    assert Aviso.objects.filter(destinatario_id=sugestao.autor_id).count() == 1
    assert Aviso.objects.count() == 4
