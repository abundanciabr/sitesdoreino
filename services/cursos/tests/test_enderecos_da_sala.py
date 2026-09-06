"""O endereço da sala de aula diz o curso e a parte, como o livro.

Decisão do mantenedor em 05/09/2026, com as palavras dele: *"quero que ao
compartilhar uma aula o link da mesma seja útil para o aluno entender
exatamente em qual parte do curso ele está"*, e o motivo que decide tudo:
*"precisamos ajustar o curso ao livro porque o aluno terá o livro em mãos
durante o curso"*.

O que este arquivo protege, e por que cada coisa:

1. **O mapa de um curso responde em `/<curso>/`**, e a aula em
   `/<curso>/parte-N/<numero>`. São os endereços que o aluno copia da barra do
   navegador e manda para um colega.
2. **A parte é GUARDA, não enfeite.** Parte que não casa com o bloco da aula
   RECUSA, em vez de mostrar a aula: um endereço que aponta certo para a aula
   ERRADA é pior do que um endereço quebrado, e é justamente essa recusa que
   torna o número do endereço confiável para quem está com o livro aberto. A
   regra é a MESMA da porta de máquina (`apps/cursos/enderecos.py`), e este
   arquivo prova as duas contra ela.
3. **O curso se resolve pelo par site+slug, nunca por "o primeiro do site".**
   Era assim que a sala resolvia até aqui, e no dia do segundo curso o site
   inteiro continuaria servindo o primeiro, sem erro, sem aviso e sem tela
   quebrada. Slug desconhecido vira uma tela que EXPLICA e mostra os cursos
   que existem; site com mais de um curso pede para escolher.
4. **O mapa agrupa pelas três Partes do livro, com o título de cada uma**, e
   pelos blocos dentro delas, na ordem do livro: é assim que o aluno acha a
   encomenda com o livro na mão.
"""

from __future__ import annotations

import pytest
from django.urls import reverse

from django.utils import timezone

from apps.cursos import enderecos
from apps.cursos.models import Aula, Bloco, Curso
from tests.conftest import SITE, COOKIE

pytestmark = pytest.mark.django_db


def abrir(client, endereco):
    return client.get(endereco, HTTP_COOKIE=COOKIE)


def corpo_de(resposta) -> str:
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


def um_segundo_curso_com_a_propria_E00() -> Curso:
    """Um segundo curso no site, com uma E00 PUBLICADA dele também.

    A numeração das encomendas é POR CURSO, e por isso a E00 existe em todos.
    É esse detalhe que faz o chute doer, e um segundo curso vazio esconderia
    o defeito: quem chutasse o curso errado não acharia aula nenhuma lá e
    cairia de volta na tela certa por acidente, com o teste verde.
    """
    curso = Curso.objects.create(site_id=SITE, slug="avancado", nome="Avançado")
    bloco = Bloco.objects.create(curso=curso, ordem=1, letra="A", parte=1)
    Aula.objects.create(
        curso=curso,
        bloco=bloco,
        ordem=0,
        numero="E00",
        titulo_exibido="Encomenda 00 do avançado",
        estado=Aula.Estado.PUBLICADA,
        publicada_em=timezone.now(),
    )
    return curso


# ------------------------------------------------- 1. os endereços do livro
def test_o_mapa_do_curso_responde_no_endereco_do_slug(aluna, client):
    endereco = reverse("curso", args=["profissional"])
    assert endereco.endswith("/profissional/")
    resposta = abrir(client, endereco)
    assert resposta.status_code == 200
    assert "Entre. Entregue. Receba." in corpo_de(resposta)


def test_a_aula_responde_com_o_curso_e_a_parte_no_endereco(
    aluna, aula_publicada, client
):
    endereco = reverse("aula-do-curso", args=["profissional", 1, "E00"])
    assert endereco.endswith("/profissional/parte-1/E00")
    resposta = abrir(client, endereco)
    assert resposta.status_code == 200
    assert aula_publicada.titulo_exibido in corpo_de(resposta)


def test_o_mapa_aponta_para_a_aula_no_endereco_com_curso_e_parte(
    aluna, aula_publicada, client
):
    corpo = corpo_de(abrir(client, reverse("curso", args=["profissional"])))
    assert 'href="/profissional/parte-1/E00"' in corpo
    assert 'href="/E00"' not in corpo


# --------------------------------------------------- 2. a parte é a GUARDA
def test_parte_que_nao_casa_recusa_em_vez_de_mostrar_a_aula(
    aluna, aula_publicada, client
):
    """A E00 está na parte 1. Pedida na parte 2, a resposta é recusa."""
    resposta = abrir(client, reverse("aula-do-curso", args=["profissional", 2, "E00"]))
    assert resposta.status_code == 404
    corpo = corpo_de(resposta)
    assert aula_publicada.titulo_exibido not in corpo
    assert "parte 1" in corpo
    assert 'href="/profissional/parte-1/E00"' in corpo


def test_a_parte_certa_da_aula_abre_normalmente(aluna, esqueleto, client):
    """A E11 está na parte 2 (bloco E): o mesmo número que recusaria na 1."""
    from tests.conftest import publicar

    aula = publicar(esqueleto.aulas.get(numero="E11"))
    assert aula.bloco.parte == 2
    negada = abrir(client, reverse("aula-do-curso", args=["profissional", 1, "E11"]))
    assert negada.status_code == 404


def test_a_guarda_da_parte_e_a_mesma_regra_da_porta_de_maquina(esqueleto):
    """Uma regra só, no mesmo lugar: a sala e a porta de máquina a chamam."""
    e00 = esqueleto.aulas.select_related("bloco").get(numero="E00")
    assert enderecos.parte_errada(esqueleto, e00, None) is None
    assert enderecos.parte_errada(esqueleto, e00, 1) is None
    recusa = enderecos.parte_errada(esqueleto, e00, 3)
    assert recusa is not None
    assert "ela está na parte 1" in recusa


# ------------------------------- 3. o curso pelo slug, nunca "o primeiro"
def test_curso_que_nao_existe_explica_e_nao_serve_o_primeiro(
    aluna, aula_publicada, client
):
    resposta = abrir(client, reverse("curso", args=["nao-existe"]))
    assert resposta.status_code == 404
    corpo = corpo_de(resposta)
    assert aula_publicada.titulo_exibido not in corpo
    assert "Entre. Entregue. Receba." not in corpo
    # A tela EXPLICA: diz o que aconteceu e mostra os cursos que existem.
    assert "nao-existe" in corpo
    assert 'href="/profissional/"' in corpo


def test_com_dois_cursos_no_site_o_endereco_antigo_nao_escolhe_por_voce(
    aluna, aula_publicada, client
):
    """O defeito que esta tarefa cura, medido: até aqui a sala respondia
    `Curso.objects.filter(site_id=site).order_by("id").first()`, e o segundo
    curso do site nunca apareceria para ninguém.

    E é aqui que o 301 PARA: o endereço antigo não diz qual curso o aluno
    quer, e com dois no site mandá-lo para um deles seria um chute com cara
    de certeza (o navegador guarda o 301 e nunca mais pergunta). A tela que
    PERGUNTA é a resposta certa, e ela responde 200.
    """
    um_segundo_curso_com_a_propria_E00()
    resposta = abrir(client, reverse("mapa"))
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert "Entre. Entregue. Receba." not in corpo
    assert aula_publicada.titulo_exibido not in corpo
    assert 'href="/profissional/"' in corpo
    assert 'href="/avancado/"' in corpo


def test_com_dois_cursos_no_site_o_endereco_antigo_da_aula_tambem_pergunta(
    aluna, aula_publicada, client
):
    """A mesma parada, no endereço antigo da AULA: com dois cursos no site,
    `/E00` não sabe de qual curso é a E00, e perguntar é honesto."""
    um_segundo_curso_com_a_propria_E00()
    resposta = abrir(client, reverse("aula", args=["E00"]))
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert aula_publicada.titulo_exibido not in corpo
    assert 'href="/profissional/"' in corpo
    assert 'href="/avancado/"' in corpo


def test_com_um_curso_so_o_endereco_antigo_muda_de_casa(aluna, client):
    """Nenhum link já compartilhado morre, e nenhum deles fica: 301.

    Enquanto os dois endereços servissem a mesma sala com 200, um link antigo
    já compartilhado levaria o aluno a uma página que não diz em que parte do
    curso ele está, que é exatamente o que o endereço novo veio resolver.
    """
    resposta = abrir(client, reverse("mapa"))
    assert resposta.status_code == 301
    assert resposta["Location"] == reverse("curso", args=["profissional"])
    assert abrir(client, resposta["Location"]).status_code == 200


def test_o_endereco_antigo_da_aula_muda_de_casa_para_a_parte_certa(
    aluna, aula_publicada, client
):
    """O checkpoint desta escola é POR LINK: o link antigo não morre, ele
    ENSINA o endereço novo, com a parte do livro dentro."""
    resposta = abrir(client, reverse("aula", args=["E00"]))
    assert resposta.status_code == 301
    assert resposta["Location"] == reverse(
        "aula-do-curso", args=["profissional", 1, "E00"]
    )
    seguida = abrir(client, resposta["Location"])
    assert seguida.status_code == 200
    assert aula_publicada.titulo_exibido in corpo_de(seguida)


def test_o_endereco_do_curso_sem_a_barra_final_muda_de_casa(aluna, client):
    """`/profissional` (sem a barra) é o mapa do curso, e não uma aula.

    Quem digita o endereço a partir do livro come a barra final, e sem esta
    regra o segmento cairia em `<str:numero>` e responderia "essa aula não
    existe" a quem pediu o mapa. 301 porque o endereço com barra é o
    definitivo.
    """
    resposta = abrir(client, "/profissional")
    assert resposta.status_code == 301
    assert resposta["Location"] == reverse("curso", args=["profissional"])


# -------------------------------------------- 4. as Partes do livro no mapa
def test_o_mapa_agrupa_pelas_tres_partes_do_livro_com_o_titulo_de_cada_uma(
    aluna, client
):
    """O número da Parte é o MESMO do endereço (`parte-1`), e o título é o do
    livro: é assim que a barra do navegador e o sumário se reconhecem."""
    corpo = corpo_de(abrir(client, reverse("curso", args=["profissional"])))
    assert "<h2>Parte 1 · Fundação</h2>" in corpo
    assert "<h2>Parte 2 · Itens que vendem</h2>" in corpo
    assert "<h2>Parte 3 · Profissional</h2>" in corpo
    assert (
        corpo.index("Parte 1 ·") < corpo.index("Parte 2 ·") < corpo.index("Parte 3 ·")
    )
    # E os blocos dentro de cada Parte, na ordem do livro (A, B, C na Parte 1).
    parte_1 = corpo[corpo.index("Parte 1 ·") : corpo.index("Parte 2 ·")]
    assert parte_1.index("Bloco A") < parte_1.index("Bloco B")
