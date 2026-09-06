"""A sala abre pela MATRÍCULA ATIVA, perguntada à `alunos`, e falha FECHADA.

O que este arquivo protege: (1) a E00 nasce `disponivel` na primeira visita de
quem tem matrícula, e a segunda visita é inerte; (2) NINGUÉM entra sem
matrícula: `cadastrado`, `na_fila`, `pausado`, `ex_aluno` e `reembolsado` são
reconhecidos e recebem 403 com a frase; (3) a `alunos` fora do ar, respondendo
500, sem `categoria` ou com o env do par ausente é 403 com a frase certa, nunca
"então pode entrar" e nunca 500; (4) a URL chamada é a do contrato inteiro.
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
from django.urls import reverse

from apps.cursos.models import Pessoa, Progresso

from tests.conftest import ANA, COOKIE, dublar_matricula, dublar_sessao, url_da_situacao

pytestmark = pytest.mark.django_db

A_FRASE_DE_SEM_MATRICULA = "Não encontramos uma matrícula ativa no seu nome"
A_FRASE_DE_SEM_RESPOSTA = "Não conseguimos conferir sua matrícula agora"


# -------------------------------------------------------- a E00 nasce
def test_a_e00_nasce_disponivel_na_primeira_visita(aluna, esqueleto, client):
    assert Progresso.objects.count() == 0
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 200

    progresso = Progresso.objects.get()
    assert progresso.aula.numero == "E00"
    assert progresso.estado == Progresso.Estado.DISPONIVEL
    assert progresso.pessoa.id_da_plataforma == ANA["id"]


def test_a_segunda_visita_nao_cria_nada(aluna, esqueleto, client):
    client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert Progresso.objects.count() == 1
    assert Pessoa.objects.count() == 1


def test_so_a_e00_nasce_e_as_outras_33_ficam_trancadas(aluna, esqueleto, client):
    corpo = client.get(
        reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE
    ).content.decode()
    assert Progresso.objects.count() == 1
    # 33 portas fechadas no mapa, com o rótulo de trancada.
    assert corpo.count("estado-trancada") == 33


# ------------------------------------------------- ninguém entra sem ela
@pytest.mark.parametrize(
    "categoria", ["cadastrado", "na_fila", "pausado", "ex_aluno", "reembolsado"]
)
def test_quem_nao_tem_matricula_ativa_recebe_403_com_a_frase(
    env_dos_pares, rede, esqueleto, client, categoria
):
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], categoria)

    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403, categoria
    assert A_FRASE_DE_SEM_MATRICULA in resposta.content.decode()
    assert Progresso.objects.count() == 0, "sem matrícula, nenhuma porta nasce"


def test_visitante_nao_recebe_403_recebe_o_convite(env_dos_pares, esqueleto, client):
    resposta = client.get(reverse("curso", args=["profissional"]))
    assert resposta.status_code == 200
    assert "Entre para ver o curso" in resposta.content.decode()
    assert Progresso.objects.count() == 0


# ------------------------------------------------ a alunos fora do ar FECHA
def _cenarios_de_alunos_fora_do_ar():
    return [
        ("fora do ar", httpx.ConnectError("alunos caiu")),
        ("500", httpx.Response(500)),
        ("404", httpx.Response(404)),
        ("sem categoria", httpx.Response(200, json={"x": 1})),
        ("200 sem json", httpx.Response(200, text="<html>")),
    ]


@pytest.mark.parametrize("nome, falha", _cenarios_de_alunos_fora_do_ar())
def test_alunos_fora_do_ar_e_403_com_frase_em_portugues_e_nunca_entra(
    env_dos_pares, rede, esqueleto, client, nome, falha
):
    """**O guarda mais importante do arquivo.** Não conseguir conferir a
    matrícula é diferente de conferir e dar positivo. Se este teste ficar verde
    com 200, a sala passou a abrir para qualquer pessoa logada sempre que a
    célula `alunos` piscar."""
    dublar_sessao(rede, ANA)
    rota = rede.get(url_da_situacao(ANA["email"]))
    if isinstance(falha, Exception):
        rota.mock(side_effect=falha)
    else:
        rota.mock(return_value=falha)

    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 403, nome
    assert A_FRASE_DE_SEM_RESPOSTA in resposta.content.decode(), nome
    assert Progresso.objects.count() == 0, nome


@pytest.mark.parametrize("ausente", ["ALUNOS_API_URL", "ALUNOS_API_TOKEN"])
def test_env_do_par_com_alunos_ausente_fecha_sem_derrubar(
    env_dos_pares, rede, esqueleto, client, monkeypatch, ausente
):
    """`armadilhas/097`: env ausente é 403 explicado, não 500 em toda página."""
    monkeypatch.delenv(ausente)
    dublar_sessao(rede, ANA)
    resposta = client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    assert resposta.status_code == 403
    assert A_FRASE_DE_SEM_RESPOSTA in resposta.content.decode()


def test_a_aula_tambem_fecha_sem_matricula(env_dos_pares, rede, aula_publicada, client):
    """A mesma porta guarda as duas telas: nenhum caminho entra por `/E00`."""
    dublar_sessao(rede, ANA)
    dublar_matricula(rede, ANA["email"], "cadastrado")
    resposta = client.get(
        reverse("aula-do-curso", args=["profissional", 1, "E00"]), HTTP_COOKIE=COOKIE
    )
    assert resposta.status_code == 403
    assert "SEGREDO" not in resposta.content.decode()


# ---------------------------------------------------- a URL do contrato
def test_a_url_da_alunos_carrega_o_segmento_do_contrato():
    """Prova de FORA: a URL montada tem de existir no contrato congelado.
    `ALUNOS_API_URL` é o `servers:` e o caminho da operação se SOMA a ele
    (`armadilhas/111`); o dublê só responde à soma exata."""
    contrato = (
        Path(__file__).resolve().parents[3] / "contracts" / "alunos.openapi.yaml"
    ).read_text(encoding="utf-8")
    assert "url: http://alunos:8000/api/alunos" in contrato
    assert "  /alunos/{email}/situacao:" in contrato
    assert url_da_situacao("ana@exemplo.com") == (
        "http://alunos:8000/api/alunos/alunos/ana%40exemplo.com/situacao"
    )


def test_a_matricula_e_perguntada_pelo_email_e_o_email_nao_e_guardado(
    aluna, esqueleto, client
):
    client.get(reverse("curso", args=["profissional"]), HTTP_COOKIE=COOKIE)
    pessoa = Pessoa.objects.get()
    assert not hasattr(pessoa, "email")
