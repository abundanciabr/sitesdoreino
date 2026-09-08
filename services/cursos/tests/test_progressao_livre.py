"""A progressão livre (TAR-270), vista da cadeira do aluno.

Decisão do mantenedor em 07/09/2026 (`DECISAO-a-sala-serve-varios-cursos.md`
§2 e §3): no curso "Primeiros Dólares com Roblox" a próxima aula abre quando o
aluno termina a anterior, sem laudo; o curso do livro continua por laudo. A
regra mora em `progresso.concluir_por_gesto` (guarda em
`test_inv_p2_a_porta_so_abre_por_laudo.py`); aqui se prova a TELA e as ROTAS:

1. **O botão "Concluir esta aula" só aparece no curso livre**, com a porta com
   a pessoa e as pausas registradas; faltando pausa, a frase no lugar dele.
2. **Concluir volta ao mapa com o recado**, a próxima abre, a seguinte à
   próxima continua trancada; na última aula o recado diz que era a última.
3. **A recusa chega em português** na própria aula (pausa faltando).
4. **O curso livre não tem checkpoint**: a seção não se desenha e a rota de
   entregar recusa, sem gravar envio.
5. **O mapa** de um curso com uma Parte só não escreve o cabeçalho da Parte;
   com mais de uma, diz "Parte N" (os nomes do livro são só do livro).
6. **No curso por laudo nada muda**: a aula e o mapa do `profissional` não
   têm traço do gesto, e a rota de concluir recusa lá.
"""

from __future__ import annotations

from urllib.parse import quote

import pytest
from django.urls import reverse

from apps.cursos import progresso as portas
from apps.cursos.models import Aula, Bloco, Curso, Envio, Progresso
from tests.conftest import (
    ANA,
    COOKIE,
    PRODUTO_DE_OUTRO_CURSO,
    SITE,
    dublar_matricula,
    dublar_sessao,
    publicar,
)

pytestmark = pytest.mark.django_db

O_BOTAO = ">Concluir esta aula<"


@pytest.fixture
def roblox(db):
    """O curso 1, de progressão livre: um bloco, três aulas publicadas (cada
    uma com as duas pausas de `publicar`), a primeira com um vídeo."""
    curso = Curso.objects.create(
        site_id=SITE,
        slug="roblox",
        nome="Primeiros Dólares com Roblox",
        progressao=Curso.Progressao.LIVRE,
        produto_id=PRODUTO_DE_OUTRO_CURSO,
    )
    bloco = Bloco.objects.create(
        curso=curso, ordem=1, letra="A", parte=1, nome="Começando"
    )
    for ordem, numero in enumerate(["1", "2", "3"]):
        publicar(
            Aula.objects.create(
                curso=curso,
                bloco=bloco,
                ordem=ordem,
                numero=numero,
                titulo_exibido=f"Aula {numero}",
            )
        )
    return curso


@pytest.fixture
def aluna_do_roblox(env_dos_pares, rede, roblox):
    """Ana, matriculada SÓ no produto do Roblox: a sala tem um curso dela."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], produtos=[PRODUTO_DE_OUTRO_CURSO])
    return ANA


def abrir(client, numero: str, slug: str = "roblox"):
    return client.get(
        reverse("aula-do-curso", args=[slug, 1, numero]), HTTP_COOKIE=COOKIE
    )


def corpo_da_aula(client, numero: str, slug: str = "roblox") -> str:
    return abrir(client, numero, slug).content.decode()


def corpo_do_mapa(client, slug: str = "roblox", recado: str = "") -> str:
    endereco = reverse("curso", args=[slug])
    if recado:
        endereco = f"{endereco}?recado={recado}"
    return client.get(endereco, HTTP_COOKIE=COOKIE).content.decode()


def registrar_as_pausas(client, numero: str) -> None:
    client.post(
        reverse("registrar-pausa-do-curso", args=["roblox", 1, numero, 1]),
        {"campo_0": "um cubo"},
        HTTP_COOKIE=COOKIE,
    )
    client.post(
        reverse("registrar-pausa-do-curso", args=["roblox", 1, numero, 2]),
        {"campo_0": "tentei", "campo_1": "aconteceu"},
        HTTP_COOKIE=COOKIE,
    )


def concluir(client, numero: str):
    return client.post(
        reverse("concluir-aula-do-curso", args=["roblox", 1, numero]),
        HTTP_COOKIE=COOKIE,
    )


def secao(corpo: str, id_da_secao: str) -> str:
    inicio = corpo.index(f'id="{id_da_secao}"')
    return corpo[inicio : corpo.index("</section>", inicio)]


# ---------------------------------------------------- 1. o botão e a frase
def test_sem_as_pausas_a_aula_diz_a_frase_no_lugar_do_botao(aluna_do_roblox, client):
    corpo = corpo_da_aula(client, "1")
    concluir_a_aula = secao(corpo, "concluir")
    assert portas.SO_COM_AS_PAUSAS in concluir_a_aula
    assert O_BOTAO not in concluir_a_aula
    assert 'id="checkpoint"' not in corpo


def test_com_as_pausas_registradas_o_botao_aparece(aluna_do_roblox, client):
    abrir(client, "1")
    registrar_as_pausas(client, "1")
    concluir_a_aula = secao(corpo_da_aula(client, "1"), "concluir")
    assert O_BOTAO in concluir_a_aula
    assert (
        f'action="{reverse("concluir-aula-do-curso", args=["roblox", 1, "1"])}"'
        in concluir_a_aula
    )
    assert portas.SO_COM_AS_PAUSAS not in concluir_a_aula


def test_a_aula_concluida_mostra_o_selo_e_nao_o_botao(aluna_do_roblox, client):
    abrir(client, "1")
    registrar_as_pausas(client, "1")
    concluir(client, "1")
    concluir_a_aula = secao(corpo_da_aula(client, "1"), "concluir")
    assert "Aula concluída." in concluir_a_aula
    assert O_BOTAO not in concluir_a_aula


# ------------------------------------------- 2. concluir abre a próxima
def test_concluir_volta_ao_mapa_com_o_recado_e_a_proxima_abre(aluna_do_roblox, client):
    abrir(client, "1")
    assert abrir(client, "2").status_code == 302, "a 2 nasce trancada"
    registrar_as_pausas(client, "1")

    resposta = concluir(client, "1")
    assert resposta.status_code == 302
    assert (
        resposta["Location"]
        == f"{reverse('curso', args=['roblox'])}?recado=aula-concluida"
    )
    assert "Aula concluída. A próxima está aberta." in corpo_do_mapa(
        client, recado="aula-concluida"
    )
    assert abrir(client, "2").status_code == 200
    assert abrir(client, "3").status_code == 302, "a 3 continua trancada"


def test_na_ultima_aula_o_recado_diz_que_era_a_ultima(aluna_do_roblox, client):
    for numero in ("1", "2", "3"):
        abrir(client, numero)
        registrar_as_pausas(client, numero)
        resposta = concluir(client, numero)
    assert resposta["Location"].endswith("?recado=ultima-concluida")
    assert "Aula concluída. Era a última." in corpo_do_mapa(
        client, recado="ultima-concluida"
    )
    assert Progresso.objects.filter(estado="concluida").count() == 3


# --------------------------------------------------------- 3. a recusa
def test_sem_pausa_o_gesto_e_recusado_na_propria_aula(aluna_do_roblox, client):
    abrir(client, "1")
    resposta = concluir(client, "1")
    assert resposta.status_code == 302
    assert resposta["Location"] == (
        f"{reverse('aula-do-curso', args=['roblox', 1, '1'])}"
        f"?erro={quote(portas.SO_COM_AS_PAUSAS)}#concluir"
    )
    assert (
        f'<p class="erro">{portas.SO_COM_AS_PAUSAS}</p>'
        in client.get(resposta["Location"], HTTP_COOKIE=COOKIE).content.decode()
    )
    assert abrir(client, "2").status_code == 302


def test_concluir_e_gesto_de_post(aluna_do_roblox, client):
    assert (
        client.get(
            reverse("concluir-aula-do-curso", args=["roblox", 1, "1"]),
            HTTP_COOKIE=COOKIE,
        ).status_code
        == 405
    )


# ------------------------------------------- 4. sem checkpoint no livre
def test_entregar_o_checkpoint_e_recusado_no_curso_livre(aluna_do_roblox, client):
    abrir(client, "1")
    registrar_as_pausas(client, "1")
    resposta = client.post(
        reverse("entregar-checkpoint", args=["1"]),
        {
            "arquivo": "https://arquivos.exemplo.test/x.blend",
            "readme": "x",
            "autoavaliacao": "y",
        },
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    assert f"?erro={quote(portas.SO_NO_CURSO_LIVRE)}#concluir" in resposta["Location"]
    assert Envio.objects.count() == 0


# ------------------------------------------------------------ 5. o mapa
def test_o_mapa_de_um_curso_com_uma_parte_nao_escreve_o_cabecalho(
    aluna_do_roblox, client
):
    corpo = corpo_do_mapa(client)
    assert "<h2>Parte " not in corpo
    assert "<h3>Começando</h3>" in corpo
    assert corpo.count('<li class="porta ') == 3
    assert "Boss" not in corpo


def test_outro_curso_com_mais_de_uma_parte_diz_parte_n(aluna_do_roblox, roblox, client):
    bloco_b = Bloco.objects.create(curso=roblox, ordem=2, letra="B", parte=2)
    aula_da_parte_2 = Aula.objects.create(
        curso=roblox,
        bloco=bloco_b,
        ordem=3,
        numero="4",
        titulo_exibido="Aula 4",
        e_boss=True,
    )
    publicar(aula_da_parte_2)
    corpo = corpo_do_mapa(client)
    assert "<h2>Parte 1</h2>" in corpo and "<h2>Parte 2</h2>" in corpo
    assert "Fundação" not in corpo and "Itens que vendem" not in corpo
    assert "<h3>Bloco B</h3>" in corpo, "bloco sem nome diz a letra"
    assert corpo.count('<span class="boss">Boss</span>') == 1


# --------------------------------------- 6. no curso por laudo nada muda
def test_no_curso_por_laudo_a_aula_e_o_mapa_nao_tem_traco_do_gesto(
    aluna, aula_publicada, client
):
    corpo = corpo_da_aula(client, "E00", slug="profissional")
    assert 'id="concluir"' not in corpo
    assert O_BOTAO not in corpo
    assert reverse("concluir-aula", args=["E00"]) not in corpo
    assert 'id="checkpoint"' in corpo

    mapa = corpo_do_mapa(client, slug="profissional")
    assert mapa.count("<h2>Parte ") == 3
    assert "<h2>Parte 1 · Fundação</h2>" in mapa


def test_no_curso_por_laudo_a_rota_de_concluir_recusa(
    aluna, aula_publicada, esqueleto, client
):
    abrir(client, "E00", slug="profissional")
    resposta = client.post(
        reverse("concluir-aula-do-curso", args=["profissional", 1, "E00"]),
        HTTP_COOKIE=COOKIE,
    )
    assert resposta.status_code == 302
    assert f"?erro={quote(portas.SO_POR_LAUDO)}#concluir" in resposta["Location"]
    assert (
        portas.progresso_de(
            Progresso.objects.get(aula__numero="E00").pessoa,
            esqueleto.aulas.get(numero="E01"),
        )
        is None
    ), "a E01 continua trancada"
