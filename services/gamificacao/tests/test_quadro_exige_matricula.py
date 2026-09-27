"""Só quem tem matrícula ativa assume tarefa no quadro de contribuições.

Decisão do mantenedor de 27/09/2026: o quadro segue a mesma regra do grupo e do
desafio. Ver o quadro continua livre; ASSUMIR exige a categoria `aluno`, que só
a célula `alunos` responde (`getStudentStanding`).

O QUE ESTE ARQUIVO TRAVA:

1. **A regra mora na porta única** (`contribuicoes.assumir`): categoria que não
   é `aluno` recebe a frase que diz o que fazer, e nenhum compromisso nasce.
2. **O e-mail vem da identidade na hora do gesto** (`getSessionFull`), nunca do
   espelho `Pessoa`: lá ele nasce `<id>@desconhecido.invalid`, e perguntar à
   `alunos` com ele recusaria todo aluno de verdade.
3. **Fail-closed**: par ausente, identidade ou alunos fora do ar, status fora de
   200 ou resposta fora do contrato viram "não consegui conferir agora", e nada
   é criado. Não conseguir perguntar nunca é "pode assumir".
4. **A tela nunca mostra e-mail**, nem na recusa.

Os dublês trocam o TRANSPORTE (`respx`), nunca a função que pergunta: a prova é
o comportamento diante do que as duas células respondem.
"""

from __future__ import annotations

import httpx
import pytest
import respx
from django.test import Client, RequestFactory

from apps.core import matricula
from apps.gamificacao import contribuicoes
from apps.gamificacao.contribuicoes import ContribuicaoRecusada
from apps.gamificacao.models import CompromissoDeContribuicao, Pessoa

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNA = "pes-aluna"
PROFESSORA = "pes-professora"
# `/` e `?` no nome são válidos em e-mail e quebram a URL se não forem
# codificados: o `/` vira outro segmento, e o `?` corta o caminho em consulta.
EMAIL = "aluna+quadro/2026?turma@exemplo.test"
EMAIL_NA_URL = "aluna%2Bquadro%2F2026%3Fturma%40exemplo.test"
COOKIE = "meshcraft_sessao=opaco"
IDENTIDADE = "http://identidade:8000/interno"
ALUNOS = "http://alunos:8000/api/alunos"
SESSAO_COMPLETA = f"{IDENTIDADE}/sessao/completa"
SITUACAO = f"{ALUNOS}/alunos/{EMAIL_NA_URL}/situacao"

SEM_MATRICULA = "matrícula ativa"
NAO_CONFERIU = "Não consegui conferir a sua matrícula agora"


@pytest.fixture(autouse=True)
def escola(monkeypatch):
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ALUNA)
    monkeypatch.setenv("IDS_DA_EQUIPE", PROFESSORA)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-gamificacao-identidade")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-gamificacao-alunos")


def _tarefa():
    return contribuicoes.publicar(
        site_id=SITE,
        autor_id=PROFESSORA,
        titulo="Estudo de caso de uma peça de Roblox",
        o_que_entregar="Um documento com o antes, o depois e o que mudou.",
        quem_pode="Quem tem matrícula ativa.",
        criterios=["Mostra o antes e o depois"],
        responsavel_id=PROFESSORA,
        responsavel_nome="Professora Ana",
        vagas=2,
    )


def _pessoa() -> Pessoa:
    # O espelho como a gamificação o cria de verdade: sem e-mail real.
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=ALUNA, defaults={"email": f"{ALUNA}@desconhecido.invalid"}
    )
    return pessoa


def _identidade_responde(mock, **corpo):
    resposta = {"autenticado": True, "id": ALUNA, "email": EMAIL, **corpo}
    return mock.get(SESSAO_COMPLETA).mock(
        return_value=httpx.Response(200, json=resposta)
    )


def _alunos_responde(mock, categoria):
    return mock.get(SITUACAO).mock(
        return_value=httpx.Response(200, json={"categoria": categoria})
    )


def _pedido():
    return RequestFactory().post("/contribuicoes/gesto", HTTP_COOKIE=COOKIE)


def _assumir_pela_tela(tarefa):
    return Client().post(
        "/contribuicoes/gesto",
        {"gesto": "assumir", "tarefa": tarefa.pk},
        HTTP_COOKIE=COOKIE,
        follow=True,
    )


# ------------------------------------------- 1. a regra na porta única


@pytest.mark.parametrize("categoria", ["visitante", "cadastrado", "na_fila", ""])
def test_quem_nao_e_aluno_nao_assume_e_le_o_que_fazer(categoria):
    tarefa = _tarefa()

    with pytest.raises(ContribuicaoRecusada) as recusa:
        contribuicoes.assumir(tarefa=tarefa, pessoa=_pessoa(), categoria=categoria)

    assert SEM_MATRICULA in str(recusa.value)
    assert "matrícula" in str(recusa.value) and "volte" in str(recusa.value)
    assert CompromissoDeContribuicao.objects.count() == 0


def test_aluno_com_matricula_ativa_assume():
    compromisso = contribuicoes.assumir(
        tarefa=_tarefa(), pessoa=_pessoa(), categoria="aluno"
    )

    assert compromisso.estado == CompromissoDeContribuicao.Estado.ASSUMIDA


# ------------------------------------------- 2. a pergunta às duas células


def test_o_email_vem_da_identidade_e_a_categoria_da_alunos():
    with respx.mock as mock:
        sessao = _identidade_responde(mock)
        situacao = _alunos_responde(mock, "aluno")
        categoria = matricula.categoria_de_quem_pede(_pedido())

    assert categoria == "aluno"
    pedido_a_identidade = sessao.calls.last.request
    assert pedido_a_identidade.headers["Authorization"] == (
        "Bearer token-gamificacao-identidade"
    )
    assert pedido_a_identidade.headers["Cookie"] == COOKIE
    assert situacao.calls.last.request.headers["Authorization"] == (
        "Bearer token-gamificacao-alunos"
    )
    assert situacao.calls.last.request.url.raw_path == (
        f"/api/alunos/alunos/{EMAIL_NA_URL}/situacao".encode()
    )


def test_sem_o_grau_completo_na_identidade_o_motivo_diz_o_nome_do_grau():
    with respx.mock as mock:
        mock.get(SESSAO_COMPLETA).mock(return_value=httpx.Response(403))
        with pytest.raises(matricula.MatriculaNaoConferida) as erro:
            matricula.categoria_de_quem_pede(_pedido())

    assert "TOKENS_COMPLETOS_GAMIFICACAO" in str(erro.value)


@pytest.mark.parametrize(
    "variavel",
    [
        "IDENTIDADE_API_URL",
        "IDENTIDADE_API_TOKEN",
        "ALUNOS_API_URL",
        "ALUNOS_API_TOKEN",
    ],
)
def test_par_ausente_fecha_sem_tocar_a_rede(monkeypatch, variavel):
    monkeypatch.delenv(variavel)

    with respx.mock:
        with pytest.raises(matricula.MatriculaNaoConferida) as erro:
            matricula.categoria_de_quem_pede(_pedido())

    assert variavel in str(erro.value)


def test_sem_cookie_nao_ha_quem_conferir():
    with respx.mock:
        with pytest.raises(matricula.MatriculaNaoConferida):
            matricula.categoria_de_quem_pede(RequestFactory().post("/"))


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.Response(500),
        httpx.Response(200, text="<html>proxy</html>"),
        httpx.Response(200, json={"autenticado": False, "id": None, "email": None}),
        httpx.Response(200, json={"autenticado": False, "id": None, "email": EMAIL}),
        httpx.Response(200, json={"autenticado": True, "id": ALUNA, "email": None}),
        httpx.Response(200, json=["fora", "do", "contrato"]),
    ],
)
def test_identidade_fora_do_contrato_fecha(resposta):
    with respx.mock as mock:
        mock.get(SESSAO_COMPLETA).mock(return_value=resposta)
        with pytest.raises(matricula.MatriculaNaoConferida):
            matricula.categoria_de_quem_pede(_pedido())


@pytest.mark.parametrize(
    "resposta",
    [
        httpx.ConnectError("alunos fora do ar"),
        httpx.Response(500),
        httpx.Response(200, text="<html>proxy</html>"),
        httpx.Response(200, json={"outra_coisa": 1}),
        httpx.Response(200, json={"categoria": ""}),
    ],
)
def test_alunos_fora_do_ar_ou_do_contrato_fecha(resposta):
    with respx.mock as mock:
        _identidade_responde(mock)
        rota = mock.get(SITUACAO)
        if isinstance(resposta, Exception):
            rota.mock(side_effect=resposta)
        else:
            rota.mock(return_value=resposta)
        with pytest.raises(matricula.MatriculaNaoConferida):
            matricula.categoria_de_quem_pede(_pedido())


# ------------------------------------------- 3. da cadeira do aluno


def test_pela_tela_quem_nao_tem_matricula_le_a_frase_sem_email():
    tarefa = _tarefa()

    with respx.mock as mock:
        _identidade_responde(mock)
        _alunos_responde(mock, "cadastrado")
        resposta = _assumir_pela_tela(tarefa)

    pagina = resposta.content.decode()
    assert resposta.status_code == 200
    assert SEM_MATRICULA in pagina
    assert EMAIL not in pagina and "desconhecido.invalid" not in pagina
    assert CompromissoDeContribuicao.objects.count() == 0


def test_pela_tela_alunos_fora_do_ar_fecha_e_nada_e_criado():
    tarefa = _tarefa()

    with respx.mock as mock:
        _identidade_responde(mock)
        mock.get(SITUACAO).mock(side_effect=httpx.ConnectError("fora do ar"))
        resposta = _assumir_pela_tela(tarefa)

    pagina = resposta.content.decode()
    assert resposta.status_code == 200
    assert NAO_CONFERIU in pagina
    assert "tente de novo" in pagina.lower()
    assert CompromissoDeContribuicao.objects.count() == 0


def test_pela_tela_o_aluno_assume():
    tarefa = _tarefa()

    with respx.mock as mock:
        _identidade_responde(mock)
        _alunos_responde(mock, "aluno")
        resposta = _assumir_pela_tela(tarefa)

    assert resposta.status_code == 200
    compromisso = CompromissoDeContribuicao.objects.get()
    assert compromisso.pessoa_id == ALUNA


def test_ver_o_quadro_nao_pergunta_matricula():
    _tarefa()

    with respx.mock:
        resposta = Client().get("/contribuicoes", HTTP_COOKIE=COOKIE)

    assert resposta.status_code == 200
    assert "Estudo de caso de uma peça de Roblox" in resposta.content.decode()


# ------------------------------------------- 4. o e-mail não fica em lugar nenhum


@pytest.mark.parametrize("celula_que_cai", ["identidade", "alunos"])
def test_a_falha_de_rede_nao_leva_o_email_para_o_log(caplog, celula_que_cai):
    """O erro do httpx pode trazer a URL, e a URL da alunos carrega o e-mail."""
    tarefa = _tarefa()

    with respx.mock as mock:
        if celula_que_cai == "identidade":
            mock.get(SESSAO_COMPLETA).mock(
                side_effect=httpx.ConnectError(f"falhou {SESSAO_COMPLETA} {EMAIL}")
            )
        else:
            _identidade_responde(mock)
            mock.get(SITUACAO).mock(
                side_effect=httpx.ConnectError(f"falhou {SITUACAO} {EMAIL}")
            )
        with caplog.at_level("DEBUG"):
            _assumir_pela_tela(tarefa)

    assert "matrícula não conferida" in caplog.text
    assert EMAIL not in caplog.text and EMAIL_NA_URL not in caplog.text


def test_assumir_nao_guarda_o_email_da_identidade():
    tarefa = _tarefa()
    _pessoa()

    with respx.mock as mock:
        _identidade_responde(mock)
        _alunos_responde(mock, "aluno")
        _assumir_pela_tela(tarefa)

    assert CompromissoDeContribuicao.objects.count() == 1
    assert Pessoa.objects.get(id_da_plataforma=ALUNA).email == (
        f"{ALUNA}@desconhecido.invalid"
    )
    assert not Pessoa.objects.filter(email=EMAIL).exists()
