# tests/test_inv_aviso_nasce_com_o_status.py  # [RECEITA:R5 v1]
"""INV-SUG08 — os avisos dos interessados e a mudança de status são UMA transação.

**A igualdade mudou de forma no EVO-42, e o guarda passou a morder na forma nova
em vez de ser afrouxado para caber nela.** O EVO-21 protegia *"uma linha de
`HistoricoStatus` ⇒ um `Aviso`"*; a decisão do mantenedor de 25/08/2026
(`docs/caixa-de-sugestoes/DECISAO-EVO-40-quem-aprova-e-quem-e-avisado.md` §2) a
transforma em *"⇒ um `Aviso` por interessado DISTINTO"* — autor, quem votou e
quem comentou. Tudo o que era exigido do aviso único continua exigido do leque
inteiro: mesma transação, mesmo rollback, mesma recusa fora do `atomic`. E há
duas exigências novas, que só existem porque o leque existe: **ninguém recebe
duas vezes** e **o aviso diz de onde veio**.

O EVO-21 acrescenta um terceiro par ao `transaction.atomic()` que o EVO-13
abriu, e o invariante tem as duas metades de sempre — só que aqui a segunda é a
que ninguém escreve:

1. **Rollback não deixa aviso órfão.** É a metade fácil, e ela continua verde
   mesmo se alguém mover a criação do aviso para DEPOIS do `with`.
2. **Aviso que não pode nascer desfaz a mudança.** É a metade que pega esse
   erro: com a escrita do aviso explodindo, a única coisa que separa "status
   mudado e aluno sem saber" de "nada aconteceu" é o `atomic`.

O custo de consultas do leque — que não pode crescer com o tamanho da plateia —
tem arquivo próprio: `tests/test_volume_dos_avisos.py`. Ele não é invariante de
correção, é de desenho, e misturá-lo aqui esconderia qual dos dois quebrou.

**Por que isto não passa pelo Redis, embora o `sugestao.status-alterado` já
exista (EVO-20) e carregue o `autor_da_sugestao_id`.** Consumir o próprio evento
para escrever na própria tabela mandaria o fato dar uma volta pela rede para
voltar ao ponto de partida — e traria de graça um modo de falha ("Redis fora do
ar ⇒ status mudado e aluno sem aviso, sem nada indicando a falta"), atraso e,
pior, a possibilidade de status e aviso divergirem. O evento existe para o mundo
de FORA (gamificação, analytics, que nascem depois); o aviso é de dentro. Há
guarda para essa independência aqui embaixo:
`test_os_avisos_nascem_mesmo_sem_redis_nenhum`.
"""

import pytest
from django.db import transaction
from django.urls import reverse

from apps.core.avisos import AvisoForaDaTransacao, avisar_os_interessados
from apps.sugestoes import eventos
from apps.sugestoes.models import Aviso, HistoricoStatus, Sugestao, Voto

pytestmark = pytest.mark.django_db


def _mudar(equipe, sugestao, status, nota=""):
    """A jornada de moderação de hoje: o Admin, pelo contrato.

    As telas de `/moderacao` desta célula foram aposentadas em 30/08/2026
    (TAR-023). O que este guarda mede não mudou uma vírgula — o aviso continua
    nascendo dentro da MESMA transação do status —, mas ele mede pelo caminho
    que existe, e não por uma view que ninguém mais alcança.
    """
    return equipe.gestao.mudar_status(equipe, sugestao, status, nota=nota)


def _vinculos_por_pessoa(sugestao=None) -> dict[str, str]:
    """Quem recebeu → com que vínculo. Erra alto se alguém recebeu duas vezes.

    A dedução da duplicata mora AQUI, e não em cada teste, porque é o modo de
    falha mais fácil de um leque: montar um `dict` a partir de linhas duplicadas
    esconderia a segunda em silêncio, e o guarda ficaria verde exatamente no
    caso que ele existe para reprovar.
    """
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
    """Sem plateia, o leque tem uma pessoa só — e ela é o autor, como no EVO-21."""
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


# ---------------------------------------------------------------------------
# [EVO-42] O leque: todos os que interagiram, uma vez cada, dizendo de onde veio
# ---------------------------------------------------------------------------


def test_o_leque_alcanca_o_autor_quem_votou_e_quem_comentou(equipe, sugestao, plateia):
    """A forma nova da igualdade, medida nos três papéis de uma vez.

    Três votantes e dois comentaristas, mais o autor: **seis** avisos, seis
    pessoas diferentes, cada um dizendo por que chegou. Antes do EVO-42 este
    número era 1 — e os outros cinco não sabiam que a ideia deles tinha andado.
    """
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
    """Sem duplicata — e o vínculo é o mais forte, não o último a ser lido.

    O autor da fixture `sugestao` também vota e também comenta. São três motivos
    para receber e **um** aviso: interessados são distintos. Um `list` no lugar
    do `dict` do fan-out passaria em todos os outros testes deste arquivo e
    reprovaria só aqui.
    """
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
    """A precedência entre os dois papéis de plateia, cravada.

    Quem comentou pôs palavra na conversa; quem votou pôs um clique. Se os dois
    vínculos empatassem, a etiqueta do cartão passaria a depender da ordem em que
    o fan-out leu as tabelas — que é a definição de resultado instável.
    """
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
    """A metade que a fixture `plateia` não prova: o CLIQUE entra no leque.

    A `plateia` escreve `Voto`/`Comentario` pelo ORM — é o certo para medir
    volume, e continuaria verde no dia em que o endpoint de votar parasse de
    gravar a linha que o fan-out lê. Este teste percorre a jornada real (POST em
    `votar` e em `comentarios`, com sessão de verdade) e é o que amarra as duas
    pontas. É a lição do elo anterior: falsifique cada degrau isoladamente.
    """
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
    """A MEDIÇÃO que decidiu coluna × derivação na leitura.

    A pessoa vota, a ideia anda, ela recebe o recado — e depois tira o voto. Com
    o vínculo derivado na leitura, o aviso de ontem passaria a não ter mais
    explicação nenhuma (ou, pior, cairia no ramo do "sua ideia"): o retrato do
    passado mudaria por causa de um clique de hoje. Com a coluna, ele continua
    dizendo o que era verdade no instante em que nasceu, que é a mesma promessa
    de `status_novo` e `nota` desde o EVO-21.

    É por isto que o `Aviso` ganhou coluna e não um `select_related` esperto.
    """
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
    corpo = votante.client.get(reverse("avisos")).content.decode()
    assert "Ideia em que você votou" in corpo


def test_a_pagina_mostra_de_onde_veio_cada_aviso(equipe, dentro, sugestao, plateia):
    """A tela distingue "sua ideia" de "ideia em que você votou/comentou".

    Medido no corpo renderizado, e não no contexto: vazamento e ausência não
    escolhem a variável que o teste imaginou (armadilhas/087).
    """
    Voto.objects.create(sugestao=sugestao, autor=dentro.identidade)
    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "vamos fazer")

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Ideia em que você votou" in corpo, corpo[-1500:]
    assert "Sua ideia" not in corpo, "o aviso de plateia se apresentou como do autor"


def test_moderar_nao_e_interagir_e_o_aviso_nao_vai_por_isso(equipe, sugestao):
    """Quem recebe é quem INTERAGIU. Quem moderou fica no `HistoricoStatus`.

    O crachá não é um vínculo com a ideia: mexer no status de dez ideias por dia
    não pode encher a própria caixa de avisos. Quem tem crachá **e** votou entra
    pelo voto, como qualquer um — é o teste logo abaixo.
    """
    _mudar(equipe, sugestao, Sugestao.Status.IMPLEMENTADO, "saiu na v1.4")

    destinatarios = list(Aviso.objects.values_list("destinatario_id", flat=True))
    assert destinatarios == [sugestao.autor_id]
    assert equipe.identidade.id not in destinatarios


def test_quem_modera_E_votou_recebe_pelo_voto(equipe, sugestao):
    """Sem ressalva, como no EVO-21: nenhum ramo especial para quem moderou.

    Suprimir este caso seria uma exceção que o guarda de atomicidade teria de
    conhecer — e a igualdade deixaria de ser uma igualdade.
    """
    Voto.objects.create(sugestao=sugestao, autor=equipe.identidade)

    _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO, "eu mesmo pedi isso")

    vinculos = _vinculos_por_pessoa()
    assert vinculos[equipe.identidade.id] == Aviso.Vinculo.VOTO


def test_toda_linha_do_historico_tem_o_aviso_de_CADA_interessado(
    equipe, sugestao, plateia
):
    """A igualdade na forma do EVO-42: uma mudança ⇒ um aviso POR interessado.

    Inclusive quando o status escolhido é o MESMO de agora — o EVO-13 aceita
    esse caso de propósito (metade do valor do formulário é a nota), e todo mundo
    que participou precisa receber justamente essa nota.

    Três mudanças e uma plateia de dois: 3 × 3 = 9 avisos, e cada rodada entrega
    a MESMA nota às mesmas três pessoas.
    """
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
    """A metade que ninguém escreve: leque impossível ⇒ mudança desfeita.

    `Aviso.objects.bulk_create` é o ponto exato onde o leque toca o banco desde o
    EVO-42 — antes era `Aviso.save`, que o `bulk_create` **não** chama. Trocar o
    alvo do monkeypatch junto com o desenho não é conveniência: um guarda que
    continuasse mirando o `save()` ficaria verde sem nunca disparar, que é a
    forma mais discreta de um portão ser desligado.

    Com a escrita explodindo, um aviso criado FORA do `atomic` — ou depois dele —
    deixaria o status já commitado e a plateia inteira sem saber de nada.
    """
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
    """A outra ponta: o que falha é a emissão do evento, DEPOIS dos avisos.

    Com plateia, e não com o autor sozinho: um leque escrito fora da transação
    (ou depois dela) deixaria **quatro** órfãos aqui, não um — e a Caixa passaria
    a dizer a quatro pessoas que a ideia andou quando ela não andou.
    """
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
    """Lei 1: em vez de confiar que todo ponto futuro lembre do `atomic`, a
    própria função recusa a escrita — como `eventos.emitir()` desde o EVO-20.

    `transaction=True` é obrigatório aqui: no `django_db` padrão TODO teste já
    roda dentro de um atomic, a recusa nunca dispararia e o guarda ficaria verde
    sem medir nada (é a `armadilhas/057` pelo avesso, a mesma pegadinha que o
    EVO-20 pagou).

    A plateia entra para que o par verde meça o LEQUE, e não uma linha: o
    invariante do EVO-42 é sobre as três pessoas nascerem juntas ou nenhuma.
    """
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
    """A independência do fio, medida — não argumentada.

    `transaction=True` porque é a única forma de o `on_commit` do relay disparar
    de verdade (`armadilhas/057`); sem `REDIS_STREAMS_URL`, o relay estoura, o
    `relay_apos_commit` engole e o evento fica PENDENTE na outbox. Se o leque
    dependesse do fio, ele não existiria — e é isso que se falsifica aqui.

    Vale mais no EVO-42 do que valia no EVO-21: o caminho pelo evento seria o
    jeito "natural" de alguém implementar o fan-out (o `status-alterado` já
    existe), e é justamente o que a decisão descartou.
    """
    monkeypatch.delenv("REDIS_STREAMS_URL", raising=False)
    plateia(sugestao, votantes=2, comentaristas=1)

    assert _mudar(equipe, sugestao, Sugestao.Status.PLANEJADO).status_code == 200

    sugestao.refresh_from_db()
    assert sugestao.status == Sugestao.Status.PLANEJADO
    assert Aviso.objects.filter(destinatario_id=sugestao.autor_id).count() == 1
    assert Aviso.objects.count() == 4
