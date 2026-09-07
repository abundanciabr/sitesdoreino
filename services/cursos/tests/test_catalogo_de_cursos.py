"""A raiz da célula (`/cursos/`) é o CATÁLOGO dos cursos, e nunca um 301.

Decisão do mantenedor em 07/09/2026, com as palavras dele: *"eu quero que em
/cursos/ mostre um catalogo ou uma landing page com os cursos que existem no
site e ao clicar nos cursos a pessoa entre no curso por exemplo em
/cursos/profissional/ e não como está hoje sendo redirecionado
automaticamente"*.

O que este arquivo protege, e por que cada coisa:

1. **A raiz responde 200 com um cartão por curso e um link para o endereço de
   cada um.** Até aqui, com um curso só, ela respondia 301 para o mapa dele:
   o aluno do curso que ainda não tem sala era levado ao curso do livro sem
   pedir, e nenhuma tela explicava por quê.
2. **O catálogo MOSTRA todos os cursos; a porta decide quem entra.** O cartão
   do curso alheio aparece com o nome e sem botão, e a frase diz o motivo.
   Esconder o cartão seria a sala fingindo que o curso não existe.
3. **Cada estado da pessoa tem a sua frase**, dizendo o que houve E o que
   fazer: visitante, aluna do curso, aluna de outro, matrícula sem sala
   (o estado dos 132 alunos de hoje), `alunos` fora do ar, e escola sem curso.
4. **A contagem de aulas abertas é calculada do banco**, e só conta o que
   está publicado: rascunho não existe para o aluno.
5. **O 301 do link antigo de AULA fica** (`/E00`, TAR-216): é o link de
   checkpoint já compartilhado. Só o 301 da raiz morre.

Prova por mutação: recolocar o 301 da raiz em `catalogo` deixa vermelho o
teste 1 (`a_raiz_nunca_responde_301`) e todos os que leem o corpo dela.
"""

from __future__ import annotations

import httpx
import pytest
from django.urls import reverse

from apps.cursos.models import Aula, Curso
from tests.conftest import (
    ANA,
    COOKIE,
    PRODUTO_DE_OUTRO_CURSO,
    PRODUTO_DO_CURSO,
    SITE,
    dublar_matricula,
    dublar_sessao,
    publicar,
    url_das_matriculas,
)
from tests.test_sala_so_do_curso_matriculado import o_outro_curso

pytestmark = pytest.mark.django_db

O_TITULO = "Os cursos da Meshcraft Academy"
O_BOTAO = "Entrar no curso"
A_FRASE_SEM_SALA = "ainda não tem sala de aula neste site"
A_FRASE_DE_CURSO_ALHEIO = "Você não está matriculado neste curso."
A_FRASE_SEM_CURSO = "Esta escola ainda não tem curso ligado."


def corpo_de(resposta) -> str:
    if resposta.streaming:
        return b"".join(resposta.streaming_content).decode("utf-8")
    return resposta.content.decode("utf-8")


def a_raiz(client, *, cookie: str = COOKIE):
    return client.get(reverse("catalogo"), HTTP_COOKIE=cookie)


def cartoes(corpo: str) -> int:
    return corpo.count('<article class="curso')


# ----------------------------------------------- 1. a raiz é o catálogo
def test_a_raiz_nunca_responde_301_mesmo_com_um_curso_so(aluna, client):
    """O guarda que dá nome à tarefa. Um curso só era a condição do 301, e é
    exatamente com um curso só que a raiz tem de responder a página."""
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    assert "Location" not in resposta
    corpo = corpo_de(resposta)
    assert O_TITULO in corpo
    assert 'href="/profissional/"' in corpo


def test_o_link_antigo_da_aula_continua_mudando_de_casa(aluna, aula_publicada, client):
    """O 301 que FICA: o link de checkpoint já compartilhado (TAR-216)."""
    resposta = client.get(reverse("aula", args=["E00"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 301
    assert resposta["Location"] == reverse(
        "aula-do-curso", args=["profissional", 1, "E00"]
    )


# -------------------------------------------------- 2. um estado por pessoa
def test_o_visitante_ve_o_cartao_com_o_botao_e_o_convite_para_entrar(
    env_dos_pares, esqueleto, client
):
    """Sem cookie, o botão leva à porta do curso, e a porta pede login: é o
    caminho honesto. E a linha "Já é aluno?" leva à entrada da escola."""
    resposta = a_raiz(client, cookie="")
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert cartoes(corpo) == 1
    assert esqueleto.nome in corpo
    assert O_BOTAO in corpo
    assert 'href="/profissional/"' in corpo
    assert "Já é aluno?" in corpo
    assert "Entrar na escola" in corpo


def test_a_aluna_do_curso_ve_o_selo_de_seu_curso_e_o_botao(aluna, client):
    corpo = corpo_de(a_raiz(client))
    assert "Seu curso" in corpo
    assert O_BOTAO in corpo
    assert 'href="/profissional/"' in corpo
    assert "Já é aluno?" not in corpo
    assert A_FRASE_SEM_SALA not in corpo


def test_o_curso_alheio_aparece_pelo_nome_mas_sem_botao(aluna, client):
    """Item 2: o catálogo mostra, a porta decide. Ana é aluna do
    `profissional`; o `avancado` aparece, sem link e com a frase."""
    outro = o_outro_curso()
    corpo = corpo_de(a_raiz(client))
    assert cartoes(corpo) == 2
    assert outro.nome in corpo
    assert 'href="/avancado/"' not in corpo
    assert A_FRASE_DE_CURSO_ALHEIO in corpo
    assert 'href="/profissional/"' in corpo
    assert "SEGREDO-DO-CURSO-2" not in corpo


def test_a_matricula_sem_sala_neste_site_ganha_o_aviso_e_nenhum_botao(
    env_dos_pares, rede, esqueleto, client
):
    """O estado dos 132 alunos de hoje: matrícula ativa num produto que não
    tem `Curso` neste site. O aviso diz isso e diz que a escola avisa."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], produtos=[PRODUTO_DE_OUTRO_CURSO])
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert A_FRASE_SEM_SALA in corpo
    assert O_BOTAO not in corpo
    assert 'href="/profissional/"' not in corpo
    assert A_FRASE_DE_CURSO_ALHEIO in corpo


def test_quem_entrou_sem_matricula_le_o_aviso_e_nao_ve_botao(
    env_dos_pares, rede, esqueleto, client
):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    corpo = corpo_de(a_raiz(client))
    assert "não encontramos uma matrícula ativa no seu nome" in corpo
    assert O_BOTAO not in corpo
    assert cartoes(corpo) == 1


def test_o_curso_sem_produto_apontado_diz_que_ninguem_entra(
    env_dos_pares, rede, esqueleto, client
):
    esqueleto.produto_id = ""
    esqueleto.save(update_fields=["produto_id"])
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    corpo = corpo_de(a_raiz(client))
    assert "ainda não está ligado às matrículas" in corpo
    assert "Fale com a escola" in corpo
    assert O_BOTAO not in corpo
    # O aviso do topo cala: esse curso pode ser o dela, e o cartão já explicou.
    # Com as duas frases, a tela diria "não tem sala" e "tem sala, mas está
    # fechada" uma embaixo da outra.
    assert A_FRASE_SEM_SALA not in corpo


def test_com_a_alunos_fora_do_ar_o_aviso_explica_e_nenhum_cartao_convida(
    env_dos_pares, rede, esqueleto, client
):
    """Não conseguir conferir a matrícula nunca é "pode entrar": o cartão sai
    sem botão, e o aviso do topo diz o que houve e o que fazer.

    E o cartão sai SEM a frase de curso alheio: dizer "você não está
    matriculado" a quem não foi conferido seria mentira com cara de resposta.
    É esta linha que a prova por mutação exige (sabotar o ramo `sem-resposta`
    do cartão deixa o botão fora do mesmo jeito, mas a frase errada entra)."""
    dublar_sessao(rede, ANA)
    rede.get(url_das_matriculas(ANA["email"])).mock(
        side_effect=httpx.ConnectError("alunos caiu")
    )
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert "Não conseguimos conferir sua matrícula agora" in corpo
    assert cartoes(corpo) == 1
    assert O_BOTAO not in corpo
    assert 'href="/profissional/"' not in corpo
    assert A_FRASE_DE_CURSO_ALHEIO not in corpo


def test_o_site_sem_configurar_diz_que_nao_ha_curso_em_vez_de_quebrar(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """Sem `SITE_ID` no env a célula não sabe de que escola é: o catálogo sai
    vazio com a frase, e não com um erro 500 nem com o curso de outro site."""
    monkeypatch.delenv("SITE_ID")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert A_FRASE_SEM_CURSO in corpo
    assert cartoes(corpo) == 0


def test_a_recusa_sem_resposta_no_curso_tenta_de_novo_no_mesmo_curso(
    env_dos_pares, rede, esqueleto, client
):
    """Efeito colateral do catálogo, e a guarda dele: o "tente de novo" da
    recusa `sem-resposta` aponta para a página que falhou. Antes do catálogo a
    raiz era o próprio curso; agora é outra página, e mandar a pessoa para lá
    seria trocar "tente de novo" por "vá para outro lugar"."""
    dublar_sessao(rede, ANA)
    rede.get(url_das_matriculas(ANA["email"])).mock(
        side_effect=httpx.ConnectError("alunos caiu")
    )
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
    corpo = corpo_de(resposta)
    assert "tente de novo" in corpo
    assert 'href="/profissional/">tente de novo' in corpo


def test_o_site_sem_configurar_diz_que_nao_ha_curso_em_vez_de_quebrar(
    env_dos_pares, rede, esqueleto, client, monkeypatch
):
    """Sem `SITE_ID` no env a célula não sabe de que escola é: o catálogo sai
    vazio com a frase, e não com um erro 500 nem com o curso de outro site."""
    monkeypatch.delenv("SITE_ID")
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert A_FRASE_SEM_CURSO in corpo
    assert cartoes(corpo) == 0


def test_a_recusa_sem_resposta_no_curso_tenta_de_novo_no_mesmo_curso(
    env_dos_pares, rede, esqueleto, client
):
    """Efeito colateral do catálogo, e a guarda dele: o "tente de novo" da
    recusa `sem-resposta` aponta para a página que falhou. Antes do catálogo a
    raiz era o próprio curso; agora é outra página, e mandar a pessoa para lá
    seria trocar "tente de novo" por "vá para outro lugar"."""
    dublar_sessao(rede, ANA)
    rede.get(url_das_matriculas(ANA["email"])).mock(
        side_effect=httpx.ConnectError("alunos caiu")
    )
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
    corpo = corpo_de(resposta)
    assert "tente de novo" in corpo
    assert 'href="/profissional/">tente de novo' in corpo


def test_a_escola_sem_curso_diz_isso_em_vez_de_uma_pagina_vazia(
    env_dos_pares, rede, client
):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"])
    assert not Curso.objects.exists()
    resposta = a_raiz(client)
    assert resposta.status_code == 200
    corpo = corpo_de(resposta)
    assert A_FRASE_SEM_CURSO in corpo
    assert cartoes(corpo) == 0


# ------------------------------------- 3. as aulas abertas, contadas do banco
def test_a_contagem_de_aulas_abertas_vem_do_banco_e_so_conta_publicadas(
    aluna, esqueleto, client
):
    assert "Nenhuma aula aberta ainda" in corpo_de(a_raiz(client))

    publicar(esqueleto.aulas.get(numero="E00"))
    assert "1 aula aberta" in corpo_de(a_raiz(client))

    publicar(esqueleto.aulas.get(numero="E01"))
    publicar(esqueleto.aulas.get(numero="E02"))
    corpo = corpo_de(a_raiz(client))
    assert "3 aulas abertas" in corpo
    assert "1 aula aberta" not in corpo


def test_uma_aula_em_rascunho_nao_entra_na_conta(aluna, esqueleto, client):
    rascunho = esqueleto.aulas.get(numero="E00")
    assert rascunho.estado == Aula.Estado.RASCUNHO
    assert "Nenhuma aula aberta ainda" in corpo_de(a_raiz(client))


# ------------------------------------------------- 4. a ordem e a moldura
def test_os_cartoes_saem_na_ordem_de_slug_e_a_faixa_aponta_para_o_catalogo(
    env_dos_pares, rede, esqueleto, client
):
    dublar_sessao(rede, ANA)
    dublar_matricula(
        rede, ANA["email"], produtos=[PRODUTO_DO_CURSO, PRODUTO_DE_OUTRO_CURSO]
    )
    Curso.objects.create(
        site_id=SITE,
        slug="avancado",
        nome="Avançado",
        produto_id=PRODUTO_DE_OUTRO_CURSO,
    )
    corpo = corpo_de(a_raiz(client))
    assert corpo.index("Avançado") < corpo.index(esqueleto.nome)
    assert corpo.count(O_BOTAO) == 2
    assert f'<a href="{reverse("catalogo")}">Cursos</a>' in corpo
    assert "<title>Cursos | Meshcraft Academy</title>" in corpo


def test_o_mapa_de_um_curso_volta_ao_catalogo_pela_faixa_padrao_da_moldura(
    aluna, client
):
    """A moldura aponta para o catálogo, e o mapa aponta para o próprio curso:
    nenhum link da sala leva mais ao endereço que redirecionava."""
    corpo = corpo_de(
        client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    )
    assert f'<a href="{reverse("catalogo")}">Cursos</a>' in corpo


def test_a_aula_aponta_para_o_mapa_do_proprio_curso(aluna, aula_publicada, client):
    """Sem isto, depois da mudança o link "Mapa das portas" levaria ao
    catálogo, e não ao mapa do curso da aula: um passo a mais para o aluno."""
    corpo = corpo_de(
        client.get(
            reverse("aula-do-curso", args=["profissional", 1, "E00"]),
            HTTP_COOKIE=COOKIE,
        )
    )
    assert 'href="/profissional/">Mapa das portas</a>' in corpo
    assert 'href="/">Mapa das portas</a>' not in corpo
