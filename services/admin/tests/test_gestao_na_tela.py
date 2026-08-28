"""O formulário de gestão de alunos — `DECISAO-gestao-de-alunos.md`.

O mantenedor pediu, com estas palavras: *"um formulário completo com vários
campos para alterar o status, a situação, tipo (mudar de aluno para
administrador, por exemplo), e etc; excluir, remover, e etc"*.

**Os três testes que carregam o arquivo**, e nenhum deles é "o formulário
salva":

1. `test_o_email_nao_viaja_nem_se_alguem_o_postar`. O e-mail é a IDENTIDADE da
   linha; mudá-lo moveria a matrícula, em silêncio, para outra pessoa. A
   proteção é uma lista de PERMISSÃO de campos — um `<input name="email">`
   acrescentado ao template amanhã não passa daqui, e nem o campo que ninguém
   previu.

2. `test_a_auditoria_registra_ate_o_que_nao_deu_certo`. Mesma disciplina da
   decisão da fila: a linha é gravada depois de saber o desfecho e antes de
   responder, inclusive quando falhou — porque uma mudança que não chegou não
   deixa rastro nenhum do outro lado.

3. `test_a_tela_explica_por_que_nao_ha_campo_de_administrador`. É o único item
   do pedido que ficou de fora, e a tela **diz isso** em vez de deixar o
   mantenedor procurando o campo. Guarda de que a explicação não some numa
   limpeza de template.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
LISTA = f"{ALUNOS}/matriculas"
FILA = f"{ALUNOS}/pre-matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
ALVO = "7"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro(email: str = DONO) -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _aluno(**campos) -> dict:
    corpo = {
        "id": ALVO,
        "site_id": "escola-a",
        "email": "aluno@exemplo.com",
        "nome_completo": "Aluno Exemplo",
        "whatsapp": "(96) 99999-0000",
        "turma": None,
        "comprou_em": None,
        "status": "ativa",
        "origem": "liberado",
        "criada_em": "2026-08-20T10:00:00Z",
    }
    corpo.update(campos)
    return corpo


def _tela_responde(alunos=None):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(LISTA).mock(
        return_value=httpx.Response(200, json=alunos if alunos is not None else [])
    )


def _salvar_responde(resposta=None):
    return respx.patch(f"{ALUNOS}/matriculas/{ALVO}").mock(
        return_value=resposta or httpx.Response(200, json=_aluno())
    )


def _salvar(client, **campos):
    corpo = {"alvo": ALVO}
    corpo.update(campos)
    return client.post(reverse("escola_aluno_salvar"), corpo)


# ------------------------------------------------------------------- a tela


@respx.mock
def test_a_tela_lista_os_alunos_com_o_formulario():
    _tela_responde([_aluno(turma="Turma A")])
    html = _dentro().get("/escola/alunos/").content.decode()

    assert "Aluno Exemplo" in html
    assert "aluno@exemplo.com" in html
    assert "(96) 99999-0000" in html
    # Os cinco campos que a lei §3 deixa mexer, e o botão.
    for campo in ("status", "nome_completo", "whatsapp", "turma", "comprou_em"):
        assert f'name="{campo}"' in html, campo
    assert reverse("escola_aluno_salvar") in html


@respx.mock
def test_a_tela_diz_quem_comprou_e_quem_voce_liberou():
    """Distinção que só o painel tem, e que muda como o mantenedor lê a lista."""
    _tela_responde(
        [
            _aluno(id="1", email="a@x.com", origem="comprou"),
            _aluno(id="2", email="b@x.com", origem="liberado"),
        ]
    )
    html = _dentro().get("/escola/alunos/").content.decode()
    assert "Comprou pelo site" in html
    assert "Você liberou" in html


@respx.mock
def test_o_aluno_que_tambem_e_administrador_aparece_marcado():
    """A informação vem da lista DESTA célula, nunca da `alunos` (§2.1)."""
    _tela_responde([_aluno(email=DONO)])
    assert "também é administrador" in _dentro().get("/escola/alunos/").content.decode()


@respx.mock
def test_a_tela_explica_por_que_nao_ha_campo_de_administrador():
    """O único item do pedido que ficou de fora — e a tela diz isso.

    Sem esta explicação, o mantenedor procuraria o campo, não acharia, e
    concluiria que faltou fazer. A tela também mostra quem é administrador
    hoje, para a resposta ser útil e não só uma negativa.
    """
    _tela_responde([_aluno()])
    html = _dentro().get("/escola/alunos/").content.decode()
    assert "tornar administrador" in html
    assert "acesso ao servidor" in html
    assert DONO in html


@respx.mock
def test_a_alunos_fora_do_ar_nao_derruba_a_tela():
    """Fail-OPEN por tile: a página abre e o número some — nunca vira zero."""
    respx.get(FILA).mock(return_value=httpx.Response(200, json=[]))
    respx.get(LISTA).mock(side_effect=httpx.ConnectError("recusou"))
    r = _dentro().get("/escola/alunos/")

    assert r.status_code == 200
    html = r.content.decode()
    assert "Ainda não consigo ver a lista de alunos" in html


@respx.mock
def test_lista_vazia_medida_e_um_zero_e_nao_um_traco():
    _tela_responde([])
    html = _dentro().get("/escola/alunos/").content.decode()
    assert "Ainda não há nenhum aluno" in html
    assert "medido, não suposto" in html


# ------------------------------------------------------------ o formulário


@pytest.mark.django_db
@respx.mock
def test_salvar_manda_os_campos_e_quem_mudou():
    rota = _salvar_responde()
    _tela_responde([_aluno()])
    r = _salvar(
        _dentro(),
        status="suspensa",
        nome_completo="Aluno Corrigido",
        whatsapp="(11) 91234-5678",
        turma="Turma B",
        comprou_em="2026-08-01",
    )

    assert r.status_code == 302
    assert r["Location"].endswith("?resultado=salvo")
    enviado = json.loads(rota.calls.last.request.read())
    assert enviado["status"] == "suspensa"
    assert enviado["nome_completo"] == "Aluno Corrigido"
    assert enviado["turma"] == "Turma B"
    assert enviado["comprou_em"] == "2026-08-01"
    assert enviado["decidido_por"] == ID_DO_DONO


@pytest.mark.django_db
@respx.mock
def test_o_email_nao_viaja_nem_se_alguem_o_postar():
    """Lista de PERMISSÃO de campos, e não um `if` que alguém esquece.

    Hoje o template não tem um campo de e-mail. O guarda existe para o dia em
    que alguém acrescentar um — ou para um POST fabricado à mão: o e-mail é a
    IDENTIDADE da linha, e mudá-lo moveria a matrícula para outra pessoa.
    """
    rota = _salvar_responde()
    _salvar(_dentro(), status="suspensa", email="outra@exemplo.com", site_id="outra")

    enviado = json.loads(rota.calls.last.request.read())
    assert "email" not in enviado
    assert "site_id" not in enviado


@pytest.mark.django_db
@respx.mock
def test_data_em_branco_vira_nulo_e_nao_string_vazia():
    """ "Não sei quando comprou" tem representação própria no contrato.

    Mandar `""` seria pedir para o outro lado gravar uma data vazia — e o
    campo é justamente uma PISTA opcional de conferência.
    """
    rota = _salvar_responde()
    _salvar(_dentro(), comprou_em="")
    assert json.loads(rota.calls.last.request.read())["comprou_em"] is None


@pytest.mark.django_db
@respx.mock
def test_formulario_sem_campo_nenhum_nao_sai_para_a_rede():
    rota = _salvar_responde()
    r = _dentro().post(reverse("escola_aluno_salvar"), {"alvo": ALVO})
    assert not rota.called
    assert Registro.objects.count() == 0
    assert r.status_code == 302


# --------------------------------------------------------------- a auditoria


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize(
    "resposta,desfecho,recado",
    [
        (httpx.Response(200, json={}), Registro.OK, "salvo"),
        (httpx.Response(409), Registro.RECUSADO_PELA_CELULA, "nao-valeu"),
        (httpx.Response(404), Registro.RECUSADO_PELA_CELULA, "nao-valeu"),
        (httpx.Response(500), Registro.NAO_RESPONDEU, "nao-deu"),
    ],
)
def test_a_auditoria_registra_ate_o_que_nao_deu_certo(resposta, desfecho, recado):
    _salvar_responde(resposta)
    r = _salvar(_dentro(), status="encerrada")

    linha = Registro.objects.get()
    assert linha.acao == Registro.EDITAR
    assert linha.desfecho == desfecho
    assert linha.quem_email == DONO
    assert linha.alvo == ALVO
    assert r["Location"].endswith(f"?resultado={recado}")


@pytest.mark.django_db
@respx.mock
def test_a_auditoria_diz_O_QUE_foi_pedido():
    """ "editar" sem o que mudou responde metade da pergunta."""
    _salvar_responde()
    _salvar(_dentro(), status="suspensa", turma="Turma C")

    detalhe = Registro.objects.get().detalhe
    assert "status=suspensa" in detalhe
    assert "turma=Turma C" in detalhe


@pytest.mark.django_db
@respx.mock
def test_editar_tem_verbo_proprio_e_nao_reusa_liberar():
    """Quem ler esta tabela em meses precisa distinguir "deixei entrar" de
    "mexi no cadastro"."""
    _salvar_responde()
    _salvar(_dentro(), status="ativa")
    assert Registro.objects.get().acao == "editar"
    assert Registro.EDITAR not in (Registro.LIBERAR, Registro.RECUSAR)


# ------------------------------------------------------------------- a borda


@respx.mock
def test_salvar_nao_atende_GET():
    assert _dentro().get(reverse("escola_aluno_salvar")).status_code == 405


@respx.mock
def test_salvar_sem_csrf_e_recusado():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": ID_DO_DONO,
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    rigoroso = Client(enforce_csrf_checks=True)
    rigoroso.defaults["HTTP_COOKIE"] = COOKIE
    resposta = rigoroso.post(
        reverse("escola_aluno_salvar"), {"alvo": ALVO, "status": "suspensa"}
    )
    assert resposta.status_code == 403


@pytest.mark.django_db
@respx.mock
def test_quem_nao_esta_na_lista_nao_salva_nada():
    r = _salvar(_dentro("estranho@exemplo.com"), status="encerrada")
    assert r.status_code == 404
    assert Registro.objects.count() == 0
