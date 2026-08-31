# tests/test_esvaziar_caixa.py
"""O comando que esvazia a Caixa precisa provar duas coisas opostas.

Que ele APAGA — do jeito que a `DECISAO-apagar-ideia.md` mandou, e não de um
jeito parecido inventado aqui. E que ele RECUSA quando o mundo não é o que
quem disparou pensava que era, porque um comando sem volta que erra o alvo é
pior do que comando nenhum.

A segunda é a que este arquivo defende com mais testes. A primeira já tem
dono: a função que ele chama é a mesma do botão do Admin, e quem a cobre é o
`test_api_gestao.py`. O que se testa aqui é que ele CHAMA aquela, e não uma
segunda versão da regra.
"""

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from apps.sugestoes.models import Comentario, Quadro, Sugestao, Voto

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"


def esvaziar(quantas: int, site: str = SITE):
    call_command("esvaziar_caixa", site_id=site, confirmo=quantas, verbosity=0)


@pytest.fixture
def ideia_com_gente(sugestao, aluno, outro_aluno):
    """Uma ideia com voto e comentário de OUTRA pessoa, não só do autor.

    A decisão promete destruir o que qualquer participante escreveu, não só o
    texto de quem abriu a ideia. Uma ideia solitária deixaria essa metade da
    promessa sem prova.
    """
    Voto.objects.create(sugestao=sugestao, autor=outro_aluno)
    Comentario.objects.create(sugestao=sugestao, autor=outro_aluno, texto="Isso!")
    return sugestao


# ---------------------------------------------------------------------------
# 1. A trava: o número tem de bater com a realidade
# ---------------------------------------------------------------------------


def test_numero_menor_que_a_realidade_recusa_sem_apagar_nada(ideia_com_gente, quadro):
    """O caso que a trava existe para pegar.

    Alguém dispara com o número de ontem, e hoje o quadro tem mais gente
    dentro. A recusa precisa vir ANTES de qualquer linha ser tocada.
    """
    with pytest.raises(CommandError, match="PAROU POR SEGURANCA"):
        esvaziar(0)

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_em is None
    assert ideia_com_gente.titulo == "Legendas nas aulas"
    assert Voto.objects.count() == 1
    assert Comentario.objects.count() == 1


def test_numero_maior_que_a_realidade_tambem_recusa(ideia_com_gente):
    """Errar para cima é o mesmo sintoma: quem disparou não sabe o estado."""
    with pytest.raises(CommandError, match="PAROU POR SEGURANCA"):
        esvaziar(5)

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_em is None


def test_a_recusa_diz_os_dois_numeros(ideia_com_gente):
    """A mensagem tem de ensinar, não só barrar: quanto eu disse, quanto há."""
    with pytest.raises(CommandError) as erro:
        esvaziar(7)

    assert "7" in str(erro.value)
    assert "1" in str(erro.value)


def test_site_inexistente_recusa(ideia_com_gente):
    """Apagar no quadro errado não tem volta, então o site errado para aqui."""
    with pytest.raises(CommandError, match="PAROU POR SEGURANCA"):
        esvaziar(1, site="site-que-nao-existe")

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_em is None


# ---------------------------------------------------------------------------
# 2. O apagamento, quando o número bate
# ---------------------------------------------------------------------------


def test_apaga_o_conteudo_e_os_votos_e_comentarios_de_todos(ideia_com_gente):
    esvaziar(1)

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_em is not None
    assert ideia_com_gente.titulo == ""
    assert ideia_com_gente.problema == ""
    assert ideia_com_gente.solucao_proposta == ""
    assert Voto.objects.count() == 0
    assert Comentario.objects.count() == 0


def test_apagada_e_sempre_arquivada_entao_some_do_quadro_do_aluno(ideia_com_gente):
    """`visiveis()` é o único corte de visibilidade do aluno (INV do arquivar).

    Se o comando apagasse sem arquivar, o aluno alcançaria uma ideia de título
    vazio pelo quadro, que é pior do que a ideia continuar lá.
    """
    esvaziar(1)

    assert Sugestao.objects.visiveis().count() == 0


def test_nao_e_quem_apagou_porque_o_pipeline_nao_e_uma_pessoa(ideia_com_gente):
    """`apagada_por` nulo é a resposta honesta, e não uma identidade de fachada.

    Cunhar uma pessoa falsa para preencher a coluna criaria uma linha em
    `Identidade` que nenhuma pessoa reivindica, no mesmo banco onde toda
    identidade existe para endereçar avisos.
    """
    esvaziar(1)

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_por is None
    assert ideia_com_gente.arquivada_por is None


def test_quadro_ja_vazio_aceita_zero_e_nao_reclama(quadro):
    """Rodar de novo depois de esvaziar não pode virar erro."""
    esvaziar(0)

    assert Sugestao.objects.count() == 0


def test_rodar_duas_vezes_pede_zero_na_segunda(ideia_com_gente):
    """A ideia já apagada sai da conta: a segunda rodada espera zero.

    Se a conta olhasse todas as linhas em vez de só as que ainda têm conteúdo,
    a mesma intenção exigiria números diferentes a cada rodada, e a trava
    viraria um enigma em vez de uma proteção.
    """
    esvaziar(1)
    esvaziar(0)

    assert Sugestao.objects.count() == 1


# ---------------------------------------------------------------------------
# 3. O que ele NÃO pode fazer
# ---------------------------------------------------------------------------


def test_nao_encosta_no_quadro_de_outro_site(ideia_com_gente, categoria, aluno):
    """Um comando de apagar em massa que erra a fronteira do site é o pesadelo.

    Aqui o segundo quadro tem UMA ideia, e o comando roda no primeiro dizendo
    esperar uma. Se a fronteira não existisse, ele apagaria duas.
    """
    outro = Quadro.objects.create(site_id="outro-site", nome="Quadro alheio")
    de_fora = Sugestao.objects.create(
        quadro=outro,
        categoria=categoria,
        autor=aluno,
        titulo="Ideia de outro site",
        problema="Nao deve ser tocada.",
    )

    esvaziar(1)

    de_fora.refresh_from_db()
    assert de_fora.apagada_em is None
    assert de_fora.titulo == "Ideia de outro site"


def test_nao_toca_o_historico_append_only(ideia_com_gente, aluno):
    """O histórico é imortal por trigger; o comando não pode esbarrar nele.

    Uma ideia que já andou de fase tem linha de histórico com `PROTECT`
    apontando para ela. Se o comando tentasse apagar a LINHA da sugestão em
    vez de esvaziar o conteúdo, isto aqui estouraria no Postgres.
    """
    from apps.sugestoes.models import HistoricoStatus

    HistoricoStatus.objects.create(
        sugestao=ideia_com_gente,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.PLANEJADO,
        alterado_por=aluno,
        nota="mudou de fase antes de ser apagada",
    )

    esvaziar(1)

    ideia_com_gente.refresh_from_db()
    assert ideia_com_gente.apagada_em is not None
    assert HistoricoStatus.objects.filter(sugestao=ideia_com_gente).count() == 1


def test_usa_a_funcao_do_botao_e_nao_uma_copia_da_regra(ideia_com_gente, monkeypatch):
    """O guarda contra a regra duplicada.

    Se alguém "simplificar" o comando escrevendo a sequência de apagamento
    dentro dele, a função compartilhada deixa de ser chamada e este teste
    reprova. É a única forma de o comando continuar herdando por construção o
    que o botão do Admin fizer amanhã.
    """
    from apps.sugestoes.management.commands import esvaziar_caixa

    chamadas = []
    original = esvaziar_caixa.apagar_definitivamente

    def espiao(sugestao, *args, **kwargs):
        chamadas.append(sugestao.pk)
        return original(sugestao, *args, **kwargs)

    monkeypatch.setattr(esvaziar_caixa, "apagar_definitivamente", espiao)
    esvaziar(1)

    assert chamadas == [ideia_com_gente.pk]
