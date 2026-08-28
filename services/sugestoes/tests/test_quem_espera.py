"""Quem está esperando (aba 3, 28/08/2026): a unidade da tela é a PESSOA.

O que esta aba mede e nenhuma outra mede é **o silêncio** — não o tempo que a
tarefa levou, mas o tempo que alguém passou sem ouvir nada sobre a ideia dela.

Três coisas que os guardas aqui protegem, e cada uma já foi decidida errado em
algum produto:

* **recusada conta como respondida** (um não explicado é resposta);
* **"nunca ouviram nada" é diferente de "ouviram há muito"** — são frases
  diferentes na tela, e o caso pior é o primeiro;
* **quem está atrás de várias ideias conta uma vez**, pela notícia MAIS RECENTE
  que ouviu — não pela mais parada.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.gestao import (
    DIAS_DE_SILENCIO_DEMAIS,
    em_aberto,
    filas_do_silencio,
    silencio_por_pessoa,
)
from apps.sugestoes.models import Sugestao


def abrir(quem):
    resposta = quem.client.get(reverse("quem_espera"))
    assert resposta.status_code == 200, resposta.content
    return resposta.content.decode()


def envelhecer(sugestao, dias):
    """Só o `criado_em` — o histórico é append-only nos três degraus."""
    Sugestao.objects.filter(pk=sugestao.pk).update(
        criado_em=timezone.now() - timedelta(days=dias)
    )


# ---------------------------------------------------------------------------
# A conta do silêncio
# ---------------------------------------------------------------------------


def test_quem_esta_atras_de_duas_ideias_conta_uma_vez_pela_mais_recente(
    caixa, dentro, quadro, sugestao
):
    """O silêncio de uma pessoa é desde a última notícia dela, não a mais velha.

    É a diferença entre contar tarefas e contar gente: quem votou numa ideia
    parada há 40 dias e noutra que andou ontem **não** está há 40 dias sem
    notícia.
    """
    recente = caixa.publicar("Ideia que andou ontem")
    caixa.votar(recente)
    caixa.votar(sugestao)
    envelhecer(sugestao, 40)

    silencio = silencio_por_pessoa(list(em_aberto(quadro)), timezone.now())

    assert (
        silencio[dentro.identidade.id] == 0
    ), "a pessoa votou nas duas; o silêncio dela é o da notícia mais recente"


def test_uma_ideia_recusada_nao_deixa_ninguem_esperando(
    caixa, equipe, quadro, sugestao
):
    """Um não explicado é resposta — e a tela para de cobrar essa dívida."""
    caixa.mudar_status(
        sugestao, Sugestao.Status.NAO_PLANEJADO, nota="o material é licenciado"
    )

    assert list(em_aberto(quadro)) == []


def test_uma_ideia_entregue_tambem_sai_da_conta(caixa, quadro, sugestao, changespec):
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO, nota="vai")
    caixa.mudar_status(sugestao, Sugestao.Status.EM_DESENVOLVIMENTO, nota="começou")
    caixa.mudar_status(sugestao, Sugestao.Status.IMPLEMENTADO, nota="no ar")

    assert list(em_aberto(quadro)) == []


def test_os_baldes_da_espera_somam_toda_a_gente(
    caixa, equipe, aprovador, entrar_como, quadro, categoria, sugestao, plateia
):
    """A soma dos quatro motivos tem de ser o total de quem espera.

    Sem este guarda, um motivo novo entraria e uma parte das pessoas sumiria da
    conta sem ninguém notar — a tela continuaria bonita e menos gente apareceria
    esperando do que de fato espera.

    **Os quatro baldes precisam estar CHEIOS**, e o teste cobra isso antes de
    somar: com um balde vazio, apagá-lo do código mantém a soma batendo e a
    mutação passa verde. Foi o que aconteceu em 28/08/2026, na primeira versão
    deste guarda — a mesma armadilha que a aba "A travessia" já tinha ensinado
    uma hora antes, e que eu repeti.
    """
    assinar_ainda = caixa.publicar("Ideia aprovada sem documento")
    caixa.mudar_status(assinar_ainda, Sugestao.Status.PLANEJADO, nota="vai")

    em_obra = caixa.publicar("Ideia em obra")
    resposta = aprovador.client.post(
        reverse("changespecs", args=[em_obra.id]),
        {
            "change_id": "CS-SUGESTOES-0007",
            "documento": "docs/changespecs/CS-SUGESTOES-0007.md",
            "aprovado_por": "Davi (mantenedor)",
            "aprovado_em": "2026-08-28",
        },
    )
    assert resposta.status_code == 302, resposta.content
    caixa.mudar_status(em_obra, Sugestao.Status.PLANEJADO, nota="vai")
    caixa.mudar_status(em_obra, Sugestao.Status.EM_DESENVOLVIMENTO, nota="começou")

    na_fila = entrar_como("outro.aluno@exemplo.test", nome="Outro")
    resposta = na_fila.client.post(
        reverse("nova_sugestao"),
        {
            "titulo": "Ideia já lida pela equipe",
            "problema": "Assisto no ônibus e não dá para ouvir.",
            "categoria": "curso",
            "publicar": "1",
        },
    )
    assert resposta.status_code == 302, resposta.content
    lida = Sugestao.objects.get(titulo="Ideia já lida pela equipe")
    equipe.client.post(
        reverse("avaliar", args=[lida.id]),
        {
            "impacto_educacional": "3",
            "impacto_comercial": "3",
            "esforco_tecnico": "3",
            "notas": "cabe",
            "decisao_produto": "vamos fazer",
        },
    )

    plateia(sugestao, votantes=5, comentaristas=2, marca="ninguem-olhou")
    plateia(assinar_ainda, votantes=3, marca="assinar")
    plateia(em_obra, votantes=4, marca="construindo")
    plateia(lida, votantes=2, marca="fila")

    abertas = list(em_aberto(quadro))
    agora = timezone.now()
    total = len(silencio_por_pessoa(abertas, agora))
    filas = filas_do_silencio(abertas, agora)

    vazios = [fila["chave"] for fila in filas if fila["pessoas"] == 0]
    assert not vazios, (
        "cenário fraco: os baldes %s estão vazios, e apagar um balde vazio do "
        "código não derruba a soma" % vazios
    )
    assert (
        sum(fila["pessoas"] for fila in filas) == total
    ), "alguém espera por um motivo que a tela não conta"


# ---------------------------------------------------------------------------
# O que a tela diz
# ---------------------------------------------------------------------------


def test_a_tela_separa_nunca_ouvi_nada_de_ouvi_ha_muito(caixa, equipe, sugestao):
    """São dois estados diferentes, e o primeiro é o pior — a tela não os junta."""
    andou = caixa.publicar("Ideia que já andou")
    caixa.mudar_status(andou, Sugestao.Status.PLANEJADO, nota="vai")

    pagina = abrir(equipe)

    assert "ainda não ouviram nada" in pagina
    assert "última notícia" in pagina


def test_o_silencio_longo_e_denunciado(caixa, equipe, sugestao):
    pagina_curta = abrir(equipe)
    assert "não ouve nada há mais de" not in pagina_curta

    envelhecer(sugestao, DIAS_DE_SILENCIO_DEMAIS + 5)
    pagina = abrir(equipe)

    assert "não ouve nada há mais de" in pagina


def test_a_tela_vazia_diz_que_ninguem_espera(equipe, quadro):
    pagina = abrir(equipe)

    assert "Ninguém está esperando" in pagina


def test_a_coluna_de_respondidas_conta_a_plateia_avisada(
    caixa, equipe, sugestao, plateia
):
    """O número de avisados É a plateia — não uma segunda contagem.

    Ele se apoia no `[INV-SUG13]`: a plateia que a tela mostra é exatamente quem
    recebeu o aviso quando a ideia andou.
    """
    plateia(sugestao, votantes=4, marca="avisados")
    caixa.mudar_status(sugestao, Sugestao.Status.NAO_PLANEJADO, nota="não dá")

    pagina = abrir(equipe)

    assert "Respondidas nos últimos 7 dias" in pagina
    # Cinco: a autora da ideia mais os quatro que votaram. O número está cravado
    # de propósito — derivá-lo da mesma função que a tela usa faria o teste
    # concordar com qualquer coisa que ela mostrasse.
    assert "5 pessoas avisadas" in pagina


def test_a_ordem_e_pelo_tamanho_da_plateia(caixa, equipe, quadro, plateia, sugestao):
    grande = caixa.publicar("Ideia de muita gente")
    plateia(grande, votantes=20, marca="muitos")
    plateia(sugestao, votantes=2, marca="poucos")
    envelhecer(sugestao, 60)

    pagina = abrir(equipe)

    assert pagina.index("Ideia de muita gente") < pagina.index(sugestao.titulo)


@pytest.mark.parametrize("metodo", ["post", "put", "delete"])
def test_a_aba_e_somente_leitura(equipe, quadro, metodo):
    resposta = getattr(equipe.client, metodo)(reverse("quem_espera"))

    assert resposta.status_code == 405
