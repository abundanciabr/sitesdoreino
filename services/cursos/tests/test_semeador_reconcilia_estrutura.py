"""O semeador reconcilia a ESTRUTURA do livro, e nunca toca na obra.

Decisão do mantenedor em 05/09/2026, com o motivo dele: *"precisamos ajustar o
curso ao livro porque o aluno terá o livro em mãos durante o curso"*. Se o
aluno navega com o livro aberto ao lado da tela, a estrutura das duas precisa
ser a mesma — e precisa CONTINUAR a mesma quando o livro mudar.

Até 05/09/2026 o semeador não atualizava nada do que já existia, e isso deixava
um buraco medido: o curso nasceu na VPS naquele dia, e corrigir a receita não
mudava o bolo já assado. Este arquivo é o guarda da fronteira nova:

    ESTRUTURA (o semeador escreve)  →  slug e nome do curso, letra e parte do
                                       bloco, bloco/ordem/e_boss/banca_nivel
                                       da aula. Fatos do livro.
    OBRA (o semeador nunca toca)    →  tudo o que o mantenedor escreve pela
                                       tela. [INV-CUR-C2], `armadilhas/331`.

Sem este guarda, a reconciliação seria uma porta aberta para o semeador
sobrescrever, num `docker compose exec` distraído, meses de trabalho que só
existem no banco e em lugar nenhum mais.
"""

from io import StringIO

import pytest
from django.core.management import call_command

from apps.cursos.models import Aula, Bloco, Curso, Peca

SITE = "escola-a"


def _semear():
    call_command("semear_esqueleto", site=SITE, stdout=StringIO())


# --------------------------------------------------- a estrutura vem do livro


def test_o_boss_esta_nas_doze_encomendas_que_o_livro_diz(esqueleto):
    """§3 da hierarquia: o Boss vive na última encomenda de cada bloco, e a
    bônus EB fecha a lista do bloco L sem ser o Boss dele."""
    com_boss = sorted(
        Aula.objects.filter(curso=esqueleto, e_boss=True).values_list(
            "numero", flat=True
        )
    )
    assert com_boss == [
        "E02",
        "E05",
        "E08",
        "E10",
        "E14",
        "E16",
        "E18",
        "E21",
        "E25",
        "E27",
        "E30",
        "E32",
    ]
    assert Aula.objects.get(curso=esqueleto, numero="EB").e_boss is False


def test_a_banca_fecha_cada_parte_no_nivel_da_parte(esqueleto):
    """§2 da hierarquia: E10 fecha a Parte I, E21 a II, E32 a III."""
    bancas = dict(
        Aula.objects.filter(curso=esqueleto, banca_nivel__isnull=False).values_list(
            "numero", "banca_nivel"
        )
    )
    assert bancas == {"E10": 1, "E21": 2, "E32": 3}


def test_os_doze_blocos_batem_com_a_tabela_do_livro(esqueleto):
    """§3 da hierarquia: as doze letras, a Parte de cada uma e o tamanho."""
    medido = [
        (b.letra, b.parte, b.aulas.count())
        for b in Bloco.objects.filter(curso=esqueleto).order_by("ordem")
    ]
    assert medido == [
        ("A", 1, 3),
        ("B", 1, 3),
        ("C", 1, 3),
        ("D", 1, 2),
        ("E", 2, 4),
        ("F", 2, 2),
        ("G", 2, 2),
        ("H", 2, 3),
        ("I", 3, 4),
        ("J", 3, 2),
        ("K", 3, 3),
        ("L", 3, 3),
    ]


# ------------------------------------------------- a reconciliação, e o limite


def test_o_curso_antigo_meshcraft_passa_a_ser_o_profissional(db):
    """O curso que nasceu na VPS em 05/09/2026 tinha o slug `meshcraft`.

    Ele precisa virar `profissional` ANTES de o slug entrar no endereço da sala
    de aula, senão nasceriam links com o nome errado — e o checkpoint desta
    escola é por link.
    """
    Curso.objects.create(site_id=SITE, slug="meshcraft", nome="Meshcraft")
    _semear()
    assert not Curso.objects.filter(site_id=SITE, slug="meshcraft").exists()
    curso = Curso.objects.get(site_id=SITE)
    assert (curso.slug, curso.nome) == ("profissional", "Profissional")
    assert curso.aulas.count() == 34, "as aulas nasceram no curso renomeado"


def test_estrutura_errada_e_corrigida_na_segunda_semeadura(esqueleto):
    """A prova de que reconciliar funciona: estrago a estrutura e semeio."""
    aula = Aula.objects.get(curso=esqueleto, numero="E32")
    aula.e_boss = False
    aula.banca_nivel = None
    aula.save(update_fields=["e_boss", "banca_nivel"])

    _semear()

    aula.refresh_from_db()
    assert (aula.e_boss, aula.banca_nivel) == (True, 3)


def test_semear_de_novo_nao_toca_em_nada_que_o_mantenedor_escreveu(esqueleto):
    """A metade mais importante deste arquivo.

    O texto das aulas não existe em lugar nenhum além deste banco (o
    repositório é público, [INV-CUR-C2]). Um semeador que sobrescrevesse obra
    seria a forma mais rápida de perder meses de trabalho.
    """
    aula = Aula.objects.get(curso=esqueleto, numero="E22")
    aula.titulo_exibido = "Quero que ela exista inteira."
    aula.pedido = "O pedido da Bia, escrito pela tela."
    aula.cliente = "Bia"
    aula.minimo = "um corpo que dobra"
    aula.aceito_quando = ["três loops por articulação"]
    aula.quiz = [{"pergunta": "quantas cabeças?", "resposta_modelo": "sete"}]
    aula.video_url = "https://exemplo.invalid/bia"
    aula.estado = Aula.Estado.PUBLICADA
    aula.versao = 7
    aula.save()
    Peca.objects.create(aula=aula, tipo=Peca.Tipo.PEDIDO, texto="a mensagem dela")

    bloco = aula.bloco
    bloco.nome = "A Personagem"
    bloco.boss_titulo = "A Personagem"
    bloco.save(update_fields=["nome", "boss_titulo"])

    curso = esqueleto
    curso.nome = "Profissional (edição de 2026)"
    curso.save(update_fields=["nome"])

    _semear()

    aula.refresh_from_db()
    assert aula.titulo_exibido == "Quero que ela exista inteira."
    assert aula.pedido == "O pedido da Bia, escrito pela tela."
    assert aula.cliente == "Bia"
    assert aula.minimo == "um corpo que dobra"
    assert aula.aceito_quando == ["três loops por articulação"]
    assert aula.quiz == [{"pergunta": "quantas cabeças?", "resposta_modelo": "sete"}]
    assert aula.video_url == "https://exemplo.invalid/bia"
    assert aula.estado == Aula.Estado.PUBLICADA
    assert aula.versao == 7
    assert aula.pecas.count() == 1
    assert aula.pecas.first().texto == "a mensagem dela"

    bloco.refresh_from_db()
    assert (bloco.nome, bloco.boss_titulo) == ("A Personagem", "A Personagem")

    curso.refresh_from_db()
    assert curso.nome == "Profissional (edição de 2026)", (
        "o nome do curso só é escrito na criação e no renomeamento de "
        "`meshcraft`; uma vez editado, é obra"
    )


def test_semear_tres_vezes_nao_duplica_nada(esqueleto):
    _semear()
    _semear()
    assert Curso.objects.filter(site_id=SITE).count() == 1
    assert Bloco.objects.filter(curso=esqueleto).count() == 12
    assert Aula.objects.filter(curso=esqueleto).count() == 34


@pytest.mark.parametrize("numero", ["E00", "E22", "EB"])
def test_toda_aula_continua_com_bloco_e_ordem(esqueleto, numero):
    aula = Aula.objects.get(curso=esqueleto, numero=numero)
    assert aula.bloco_id is not None
    assert aula.curso_id == esqueleto.id
