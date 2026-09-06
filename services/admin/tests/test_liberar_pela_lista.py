"""A tela que libera em lote pela lista de turmas (02/09/2026).

Pedido do mantenedor: *"tenho uma lista com os números dos whatsapp dos alunos
e quero liberar automaticamente todos os que estão no site na fila de espera e
que estejam com os números nessa lista"*, com os dois lados que não casarem
marcados.

O que este arquivo trava, e nenhum teste de status pegaria:

1. **A conferência não muda nada.** Colar a lista é leitura pura: se um POST de
   conferência chegasse a decidir sobre alguém, a promessa de "mostro tudo antes
   de mexer" estaria quebrada, e ele descobriria depois de a pessoa já ter
   entrado.

2. **Só o que está MARCADO é liberado.** A caixa dos palpites nasce vazia, e o
   que ela decide é se um estranho entra numa turma paga.

3. **Os alvos são conferidos contra a fila de AGORA.** Um id que o formulário
   afirma mas que não está esperando não vira chamada nenhuma — é isso que
   torna o F5 inofensivo.

4. **Uma linha de auditoria por pessoa**, inclusive quando falha. Uma linha por
   leva não responderia "quem liberou a Maria?".
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
FILA = f"{ALUNOS}/pre-matriculas"
MATRICULAS = f"{ALUNOS}/matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
# [CURSO] UMA escolha para o lote inteiro, obrigatória desde 06/09/2026
# ([INV-ALU-C1]): uma turma é de um curso. Os testes daqui continuam medindo a
# leva (quem sai, quem não sai, a auditoria por pessoa); o que acontece SEM o
# curso mora em `test_liberar_com_curso.py`.
CURSO = "prod-primeiros-dolares"


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
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": email,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _texto(resposta) -> str:
    return resposta.content.decode()


def _pessoa(id_, whatsapp, nome="Maria Silva", **campos) -> dict:
    corpo = {
        "id": id_,
        "site_id": "escola-a",
        "email": f"{nome.split()[0].lower()}@exemplo.com",
        "nome_completo": nome,
        "whatsapp": whatsapp,
        "turma": None,
        "comprou_em": None,
        "status": "aguardando",
        "criada_em": "2026-08-20T10:00:00Z",
        "esperando_ha_dias": 3,
        "motivo_recusa": None,
        "ja_foi_aluno": False,
        "passagens_anteriores": 0,
        "saiu_em": None,
    }
    corpo.update(campos)
    return corpo


def _escola_responde(fila, alunos=None):
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=fila)
    )
    respx.get(MATRICULAS).mock(return_value=httpx.Response(200, json=alunos or []))


# ------------------------------------------------------- 1. a conferência


@respx.mock
def test_a_tela_abre_vazia_esperando_a_lista():
    _escola_responde([])
    r = _dentro().get(reverse("escola_turmas"))
    assert r.status_code == 200
    assert "Cole aqui" in _texto(r)


@respx.mock
def test_quem_bate_aparece_pronto_para_liberar():
    _escola_responde([_pessoa("p1", "+55 (11) 99999-8888", "Maria Silva")])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    corpo = _texto(r)
    assert "Prontos para liberar (1)" in corpo
    assert "Maria Silva" in corpo


@respx.mock
def test_conferir_nao_decide_sobre_ninguem():
    # A rota de decisão NÃO está registrada no respx: se a conferência chamar,
    # o teste estoura. É a forma mais dura de fixar "leitura pura".
    _escola_responde([_pessoa("p1", "11 99999-8888")])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    assert r.status_code == 200
    assert Registro.objects.count() == 0


@respx.mock
def test_quem_esta_na_fila_e_nao_na_lista_fica_marcado():
    _escola_responde([_pessoa("p1", "21 98888-7777", "Joao Sozinho")])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    corpo = _texto(r)
    assert "Na fila, mas não achei na sua lista (1)" in corpo
    assert "Joao Sozinho" in corpo


@respx.mock
def test_numero_sem_ninguem_no_site_fica_marcado():
    _escola_responde([])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    corpo = _texto(r)
    assert "não achei no site (1)" in corpo
    assert "11 99999-8888" in corpo


@respx.mock
def test_a_lista_colada_volta_na_caixa():
    # Sem isto, liberar uma leva apagaria a lista e ele teria de abrir o
    # arquivo de novo para ver o que sobrou.
    _escola_responde([])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    assert "11 99999-8888" in _texto(r)


@respx.mock
def test_caixa_vazia_pede_a_lista_em_vez_de_conferir_o_nada():
    _escola_responde([])
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "   "})
    assert "Cole a lista de números" in _texto(r)


@respx.mock
def test_fila_ausente_nao_vira_conferencia_vazia():
    # `None` é "não consegui perguntar". Dizer "não achei ninguém da sua lista"
    # aqui faria ele concluir que a escola está vazia.
    respx.get(FILA, params={"status": "aguardando"}).mock(
        return_value=httpx.Response(503)
    )
    respx.get(MATRICULAS).mock(return_value=httpx.Response(200, json=[]))
    r = _dentro().post(reverse("escola_turmas_conferir"), {"lista": "11 99999-8888"})
    corpo = _texto(r)
    assert "Ainda não consigo perguntar" in corpo
    assert "Prontos para liberar" not in corpo


# --------------------------------------------------------- 2. a liberação


@respx.mock
def test_libera_so_quem_foi_marcado():
    _escola_responde(
        [_pessoa("p1", "11 99999-8888"), _pessoa("p2", "21 98888-7777", "Nao Marcada")]
    )
    decidir = respx.post(f"{FILA}/p1/decisao").mock(
        return_value=httpx.Response(200, json={"status": "ativa"})
    )
    # `p2` não está registrada no respx: uma chamada a ela estoura o teste.
    r = _dentro().post(
        reverse("escola_turmas_liberar"),
        {"lista": "11 99999-8888", "alvo": ["p1"], "product_id": CURSO},
    )
    assert decidir.called
    assert "Liberei 1 pessoa" in _texto(r)


@respx.mock
def test_nada_marcado_nao_libera_ninguem():
    _escola_responde([_pessoa("p1", "11 99999-8888")])
    r = _dentro().post(reverse("escola_turmas_liberar"), {"lista": "11 99999-8888"})
    assert "Nenhuma pessoa estava marcada" in _texto(r)
    assert Registro.objects.count() == 0


@respx.mock
def test_alvo_que_nao_esta_mais_na_fila_nao_vira_chamada():
    # O F5 que reenvia o POST, e a segunda aba. Nenhuma rota de decisão está
    # registrada: qualquer chamada estoura.
    _escola_responde([_pessoa("p1", "11 99999-8888")])
    r = _dentro().post(
        reverse("escola_turmas_liberar"),
        {"lista": "11 99999-8888", "alvo": ["fantasma"], "product_id": CURSO},
    )
    assert "Liberei 0 pessoa" in _texto(r)
    assert "já não estava na fila" in _texto(r)
    assert Registro.objects.count() == 0


@respx.mock
def test_uma_linha_de_auditoria_por_pessoa():
    _escola_responde([_pessoa("p1", "11 99999-1111"), _pessoa("p2", "11 99999-2222")])
    for alvo in ("p1", "p2"):
        respx.post(f"{FILA}/{alvo}/decisao").mock(
            return_value=httpx.Response(200, json={"status": "ativa"})
        )
    _dentro().post(
        reverse("escola_turmas_liberar"),
        {
            "lista": "11 99999-1111, 11 99999-2222",
            "alvo": ["p1", "p2"],
            "product_id": CURSO,
        },
    )
    linhas = Registro.objects.order_by("alvo")
    assert [l.alvo for l in linhas] == ["p1", "p2"]
    assert all(l.acao == Registro.LIBERAR for l in linhas)
    assert all(l.desfecho == Registro.OK for l in linhas)
    assert all(l.quem_email == DONO for l in linhas)


@respx.mock
def test_a_falha_de_uma_nao_derruba_a_leva_e_fica_registrada():
    _escola_responde([_pessoa("p1", "11 99999-1111"), _pessoa("p2", "11 99999-2222")])
    respx.post(f"{FILA}/p1/decisao").mock(
        return_value=httpx.Response(200, json={"status": "ativa"})
    )
    respx.post(f"{FILA}/p2/decisao").mock(return_value=httpx.Response(503))
    r = _dentro().post(
        reverse("escola_turmas_liberar"),
        {
            "lista": "11 99999-1111, 11 99999-2222",
            "alvo": ["p1", "p2"],
            "product_id": CURSO,
        },
    )
    corpo = _texto(r)
    assert "Liberei 1 pessoa" in corpo
    assert "1 não deu para saber" in corpo
    desfechos = sorted(l.desfecho for l in Registro.objects.all())
    assert desfechos == sorted([Registro.OK, Registro.NAO_RESPONDEU])


@respx.mock
def test_depois_de_liberar_a_conferencia_volta_atualizada():
    # A pessoa saiu da fila entre o clique e a nova leitura: a tela tem de
    # mostrar a fila de DEPOIS, senão ele libera de novo quem já entrou.
    respx.get(FILA, params={"status": "aguardando"}).mock(
        side_effect=[
            httpx.Response(200, json=[_pessoa("p1", "11 99999-8888")]),
            httpx.Response(200, json=[]),
        ]
    )
    respx.get(MATRICULAS).mock(return_value=httpx.Response(200, json=[]))
    respx.post(f"{FILA}/p1/decisao").mock(
        return_value=httpx.Response(200, json={"status": "ativa"})
    )
    r = _dentro().post(
        reverse("escola_turmas_liberar"),
        {"lista": "11 99999-8888", "alvo": ["p1"], "product_id": CURSO},
    )
    assert "Prontos para liberar (0)" in _texto(r)


# ------------------------------------------------- 3. a porta e o caminho


@respx.mock
def test_quem_nao_e_administrador_nao_entra():
    # 404, e não 403: a porta desta área ESCONDE a existência das telas de
    # quem não pode vê-las (`test_poderes.py`).
    r = _dentro("estranho@exemplo.com").get(reverse("escola_turmas"))
    assert r.status_code == 404


@respx.mock
def test_a_tela_de_alunos_leva_ate_aqui():
    _escola_responde([])
    # A tela de alunos pergunta pelas DUAS filas; esta tela só pela de espera.
    respx.get(FILA, params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    r = _dentro().get(reverse("escola_alunos"))
    assert reverse("escola_turmas") in _texto(r)


def test_liberar_recusa_get():
    # Decisão que se aplica por GET é decisão que um pré-carregador de link
    # toma sozinho.
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    with respx.mock:
        respx.get(SESSAO).mock(
            return_value=httpx.Response(
                200,
                json={
                    "autenticado": True,
                    "id": "id-opaco-123",
                    "nome_exibido": "Fulano",
                    "papel": None,
                    "email": DONO,
                },
            )
        )
        assert c.get(reverse("escola_turmas_liberar")).status_code == 405
