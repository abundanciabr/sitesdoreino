"""A travessia (aba 2, 28/08/2026): as ideias em colunas, do pedido ao ar.

O guarda que carrega esta tela é o **aritmético**: as seis colunas mais o que
está fora do trilho somam exatamente o quadro inteiro. Ele existe porque a
partição é a parte fácil de errar — dois dos seis status viram duas colunas cada
(`em_analise` parte por ter avaliação; `planejado` parte por ter ChangeSpec), e
basta um filtro novo esquecer um caso para um punhado de ideias sumir da tela
sem ninguém notar. É o mesmo guarda que o EVO-31 pôs na faixa do aluno
(`zonas + saídas == quadro`), aplicado à tela da equipe.

Como em `test_a_mesa.py`, o crachá não é medido aqui: `test_inv_so_staff_modera.py`
deriva a lista de rotas protegidas do urlconf e pegou esta sozinho.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.gestao import colunas_da_travessia, fora_do_trilho
from apps.sugestoes.models import Sugestao


def abrir(quem):
    resposta = quem.client.get(reverse("travessia"))
    assert resposta.status_code == 200, resposta.content
    return resposta.content.decode()


def publicar_por_gente_diferente(entrar_como, titulos):
    """Publica cada ideia por um aluno diferente — o freio da Caixa é por PESSOA.

    O limite de 3 sugestões a cada 7 dias (spec §10) é do produto, não do teste:
    montar seis ideias com um aluno só devolve 429 na quarta, e é isso mesmo que
    tem de acontecer. Um cenário que precise de seis ideias precisa de seis
    alunos — e passar por cima disso escrevendo pelo ORM tiraria da tela a única
    prova de que a jornada de verdade alimenta estas colunas.
    """
    publicadas = []
    for n, titulo in enumerate(titulos):
        aluno = entrar_como("aluno%d@exemplo.test" % n, nome="Aluno %d" % n)
        resposta = aluno.client.post(
            reverse("nova_sugestao"),
            {
                "titulo": titulo,
                "problema": "Assisto no ônibus e não dá para ouvir.",
                "categoria": "curso",
                "publicar": "1",
            },
        )
        assert resposta.status_code == 302, resposta.content
        publicadas.append(Sugestao.objects.get(titulo=titulo))
    return publicadas


def assinar(aprovador, sugestao, n):
    """Registra um ChangeSpec aprovado pela jornada real — nunca por `create()`."""
    resposta = aprovador.client.post(
        reverse("changespecs", args=[sugestao.id]),
        {
            "change_id": "CS-SUGESTOES-%04d" % n,
            "documento": "docs/changespecs/CS-SUGESTOES-%04d.md" % n,
            "aprovado_por": "Davi (mantenedor)",
            "aprovado_em": "2026-08-28",
        },
    )
    assert resposta.status_code == 302, resposta.content


def avaliar(equipe, sugestao, decisao="Vamos fazer."):
    resposta = equipe.client.post(
        reverse("avaliar", args=[sugestao.id]),
        {
            "impacto_educacional": "4",
            "impacto_comercial": "3",
            "esforco_tecnico": "2",
            "notas": "cabe",
            "decisao_produto": decisao,
        },
    )
    assert resposta.status_code == 302, resposta.content


# ---------------------------------------------------------------------------
# O guarda que carrega a tela
# ---------------------------------------------------------------------------


def cenario_das_seis_colunas(entrar_como, equipe, aprovador):
    """Uma ideia em CADA uma das seis colunas, mais uma fora do trilho.

    Encher as seis não é capricho de cobertura: com uma coluna vazia, apagá-la do
    código deixa a soma batendo do mesmo jeito, e o guarda aritmético fica verde
    sem medir nada. Foi exatamente o que a mutação mostrou em 28/08/2026 — a
    primeira versão deste cenário não tinha nada em "No ar", e esvaziar aquela
    coluna passou despercebido.
    """
    ideias = publicar_por_gente_diferente(
        entrar_como,
        [
            "Ideia que ninguém leu",
            "Ideia que a equipe leu",
            "Ideia aprovada sem documento",
            "Ideia assinada esperando robô",
            "Ideia em obra",
            "Ideia entregue",
            "Ideia recusada",
        ],
    )
    chegando, lendo, sem_doc, assinada, em_obra, entregue, recusada = ideias

    avaliar(equipe, lendo)
    for numero, ideia in enumerate((assinada, em_obra, entregue), start=1):
        assinar(aprovador, ideia, numero)
    for ideia in (sem_doc, assinada, em_obra, entregue):
        equipe.client.post(
            reverse("mudar_status", args=[ideia.id]),
            {"status": Sugestao.Status.PLANEJADO, "nota": "vai"},
        )
    for ideia in (em_obra, entregue):
        equipe.client.post(
            reverse("mudar_status", args=[ideia.id]),
            {"status": Sugestao.Status.EM_DESENVOLVIMENTO, "nota": "começou"},
        )
    equipe.client.post(
        reverse("mudar_status", args=[entregue.id]),
        {"status": Sugestao.Status.IMPLEMENTADO, "nota": "no ar"},
    )
    equipe.client.post(
        reverse("mudar_status", args=[recusada.id]),
        {
            "status": Sugestao.Status.NAO_PLANEJADO,
            "nota": "quebra o acordo com os autores",
        },
    )
    return {
        "chegando": chegando,
        "lendo": lendo,
        "assinar": sem_doc,
        "pode-comecar": assinada,
        "construindo": em_obra,
        "no-ar": entregue,
        "recusada": recusada,
    }


def test_as_colunas_mais_as_saidas_somam_o_quadro_inteiro(
    entrar_como, equipe, aprovador, quadro, categoria
):
    """Nenhuma ideia pode ficar sem coluna. Este é O guarda desta aba."""
    cenario_das_seis_colunas(entrar_como, equipe, aprovador)

    colunas = colunas_da_travessia(quadro, timezone.now())
    saidas = fora_do_trilho(quadro)

    nas_colunas = sum(coluna["total"] for coluna in colunas)
    assert (
        nas_colunas + len(saidas) == Sugestao.objects.filter(quadro=quadro).count()
    ), (
        "alguma ideia não caiu em coluna nenhuma nem na faixa de fora do trilho — "
        "a partição das seis colunas esqueceu um caso"
    )


def test_cada_coluna_recebe_exatamente_a_ideia_dela(
    entrar_como, equipe, aprovador, quadro, categoria
):
    """A soma bateria com as ideias trocadas de coluna. Aqui cada uma é nomeada.

    É este guarda que morde quando alguém apaga uma coluna: sem ele, esvaziar
    "No ar" mantém a soma certa se nada estiver lá.
    """
    esperado = cenario_das_seis_colunas(entrar_como, equipe, aprovador)

    colunas = {c["chave"]: c for c in colunas_da_travessia(quadro, timezone.now())}

    for chave, ideia in esperado.items():
        if chave == "recusada":
            continue
        assert [s.id for s in colunas[chave]["sugestoes"]] == [ideia.id], (
            "a coluna %r não está com a ideia que deveria" % chave
        )


def test_nenhuma_ideia_cai_em_duas_colunas(caixa, equipe, quadro, sugestao):
    """A soma bateria também se uma ideia contasse duas vezes e outra sumisse."""
    lendo = caixa.publicar("Ideia lida")
    avaliar(equipe, lendo)

    colunas = colunas_da_travessia(quadro, timezone.now())
    vistas = [s.id for coluna in colunas for s in coluna["sugestoes"]]

    assert len(vistas) == len(set(vistas)), "uma ideia apareceu em mais de uma coluna"


# ---------------------------------------------------------------------------
# A partição — onde cada ideia cai, e por quê
# ---------------------------------------------------------------------------


def test_em_analise_parte_em_duas_pela_avaliacao(caixa, equipe, quadro, sugestao):
    """ "Chegando" e "a equipe está lendo" são o MESMO status, partido pela leitura."""
    lida = caixa.publicar("Ideia que a equipe leu")
    avaliar(equipe, lida)

    colunas = {c["chave"]: c for c in colunas_da_travessia(quadro, timezone.now())}

    assert [s.id for s in colunas["chegando"]["sugestoes"]] == [sugestao.id]
    assert [s.id for s in colunas["lendo"]["sugestoes"]] == [lida.id]


def test_planejado_parte_em_duas_pela_assinatura(caixa, quadro, sugestao, changespec):
    """ "Esperando você assinar" e "pode começar" são o mesmo status, partido pelo corredor."""
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="vai")
    sem_assinatura = caixa.publicar("Ideia sem documento")
    caixa.mudar_status(sem_assinatura, Sugestao.Status.PLANEJADO, nota="vai")

    colunas = {c["chave"]: c for c in colunas_da_travessia(quadro, timezone.now())}

    assert [s.id for s in colunas["pode-comecar"]["sugestoes"]] == [sugestao.id]
    assert [s.id for s in colunas["assinar"]["sugestoes"]] == [sem_assinatura.id]


def test_a_saida_carrega_o_motivo_que_o_aluno_recebeu(caixa, quadro, sugestao):
    """Duas frases diferentes para o aluno e para a equipe seriam duas verdades."""
    caixa.mudar_status(
        sugestao,
        Sugestao.Status.NAO_PLANEJADO,
        nota="O material é licenciado por aluno.",
    )

    (saida,) = fora_do_trilho(quadro)

    assert saida.motivo_da_saida == "O material é licenciado por aluno."


# ---------------------------------------------------------------------------
# O que a tela diz
# ---------------------------------------------------------------------------


def test_a_conta_do_gargalo_aponta_a_coluna_mais_lenta(caixa, quadro, sugestao):
    """O gargalo é a maior espera média — calculado, nunca cravado.

    O tempo passa pelo RELÓGIO INJETADO, e não envelhecendo linhas: o
    `HistoricoStatus` é append-only nos três degraus (Python, QuerySet e um
    trigger no Postgres), então não existe — nem deve existir — jeito de reescrever
    a data em que uma ideia mudou de fase. `colunas_da_travessia` recebe `agora`
    de fora exatamente por isso, como `sugestoes_ordenadas` já fazia para a aba
    "Em alta": é o que torna a medição falsificável sem depender do calendário da
    máquina.
    """
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="vai")

    daqui_a_vinte_dias = timezone.now() + timedelta(days=20)
    colunas = colunas_da_travessia(quadro, daqui_a_vinte_dias)
    com_gente = [c for c in colunas if c["parada_media"] is not None]

    gargalo = max(com_gente, key=lambda c: c["parada_media"])
    assert gargalo["chave"] == "assinar"
    assert gargalo["parada_media"] == 20


def test_a_tela_aponta_a_coluna_entupida(caixa, equipe, sugestao):
    """A conta do gargalo, vista de fora — com DUAS colunas para escolher.

    Duas, e não uma: com uma coluna só, o maior e o menor são a mesma coisa, e
    trocar `max` por `min` no código passaria despercebido. A mutação mostrou isso
    em 28/08/2026, e é por isso que este cenário tem uma ideia velha em "Chegando"
    e uma recém-aprovada em "Esperando você assinar".
    """
    recente = caixa.publicar("Ideia aprovada agorinha")
    caixa.mudar_status(recente, Sugestao.Status.PLANEJADO, nota="vai")
    Sugestao.objects.filter(pk=sugestao.pk).update(
        criado_em=timezone.now() - timedelta(days=20)
    )

    pagina = abrir(equipe)

    assert "Onde está entupido hoje" in pagina
    assert "A coluna <strong>Chegando</strong>" in pagina


def test_sem_nada_parado_a_tela_nao_inventa_gargalo(caixa, equipe, sugestao):
    """Tudo que entrou hoje não é entupimento — e a tela cala em vez de apontar.

    Sem esta calada, a faixa apareceria todo dia dizendo que alguma coluna é a
    pior, mesmo num quadro inteiramente em dia. Alarme que toca sempre não é
    alarme.
    """
    pagina = abrir(equipe)

    assert "Onde está entupido hoje" not in pagina


def test_a_saida_sem_motivo_escrito_e_denunciada(caixa, equipe, quadro, sugestao):
    """Mesclar não exige justificativa; a tela mostra o buraco em vez de escondê-lo."""
    Sugestao.objects.filter(pk=sugestao.pk).update(status=Sugestao.Status.MESCLADO)

    pagina = abrir(equipe)

    assert "juntada a outra" in pagina
    assert "ficou sem explicação" in pagina


def test_a_travessia_leva_para_a_ideia_pelo_endereco_da_casa(caixa, equipe, sugestao):
    """`{% url %}` e não caminho à mão — sob prefixo público o segundo quebra só lá."""
    pagina = abrir(equipe)

    assert reverse("moderar", args=[sugestao.id]) in pagina


def test_a_faixa_de_abas_marca_onde_a_pessoa_esta(caixa, equipe, sugestao):
    """A faixa descobre a aba atual pelo nome da rota — nenhuma tela passa isso."""
    na_travessia = abrir(equipe)
    na_mesa = equipe.client.get(reverse("mesa")).content.decode()

    assert 'href="' + reverse("mesa") + '" class="aba"' in na_travessia
    assert 'href="' + reverse("travessia") + '" class="aba ativa"' in na_travessia
    assert 'href="' + reverse("mesa") + '" class="aba ativa"' in na_mesa


@pytest.mark.parametrize("metodo", ["post", "put", "delete"])
def test_a_travessia_e_somente_leitura(equipe, quadro, metodo):
    resposta = getattr(equipe.client, metodo)(reverse("travessia"))

    assert resposta.status_code == 405
