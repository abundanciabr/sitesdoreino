"""O botão de juntar ideias, o modal da prévia e o desfazer (05/09/2026).

Pedido do mantenedor: *"Coloque o botão de fundir que mostra o modal de como
ficaria se fossem fundidas, e pede a confirmação da fusão, com a opção de
desfazer tudo"*. Lei: `docs/decisoes/DECISAO-fundir-ideias.md`.

O que estes guardas protegem, em ordem de quanto dói perder:

1. **Sem prévia não há botão.** É a regra que dá sentido ao pedido: o modal
   existe para ele VER antes de decidir. Se a Caixa não respondeu a prévia, a
   análise continua na tela (leitura vale sem o botão) e o gesto de juntar
   desaparece. Fail-open na leitura, fail-closed na ação.
2. **A tela mostra o número menor e explica por quê.** Depois da junção o total
   de votos quase nunca é a soma, e um número que encolhe sem explicação parece
   defeito — ou pior, parece que alguém perdeu o voto.
3. **O impedimento aparece escrito, e o botão de confirmar não.** Motivo em
   português ensina; botão que some, não.
4. **Juntar e desfazer são POST**, e cada um deixa rastro na auditoria nos três
   desfechos.
"""

import json
import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
PREVIAS = f"{CAIXA}/gestao/fusoes/previas"
FUSOES = f"{CAIXA}/gestao/fusoes"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

# As três ideias da primeira fusão proposta pela análise: 31 fica de pé, 27 e 42
# entram nela.
CANONICA, ABSORVIDA_A, ABSORVIDA_B = 31, 27, 42


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("SUGESTOES_API_URL", CAIXA)
    monkeypatch.setenv("SUGESTOES_API_TOKEN", "token-do-par-admin-sugestoes")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
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
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def ideia(id, titulo, votos=3, pessoas=3):
    return {
        "id": id,
        "titulo": titulo,
        "problema": "texto do aluno",
        "solucao_proposta": "",
        "categoria": "Blender e modelagem 3D",
        "status": "em_analise",
        "votos": votos,
        "comentarios": 0,
        "pessoas": pessoas,
        "autor": "Alguem",
        "criada_em": "2026-09-01T10:00:00+00:00",
        "parada_desde": "2026-09-01T10:00:00+00:00",
        "ja_ouviram": False,
        "tem_avaliacao": False,
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
        "conversa": [],
    }


AS_TRES = [
    ideia(CANONICA, "Anatomia de cabelo e estilos variados para Roblox UGC", votos=9),
    ideia(ABSORVIDA_A, "Tutorial de base de cabelo", votos=2),
    ideia(ABSORVIDA_B, "Tutorial de cabelos cacheados", votos=3),
]


def a_caixa_responde(ideias=None, previas=None, fusoes=None):
    respx.get(IDEIAS).mock(
        return_value=httpx.Response(
            200,
            json={
                "quadro": "Meshcraft",
                "pode_assinar": True,
                "pessoas_esperando": 0,
                "silencio_medio_em_dias": None,
                "pessoas_em_silencio_demais": 0,
                "ideias": AS_TRES if ideias is None else ideias,
            },
        )
    )
    if previas is None:
        respx.post(PREVIAS).mock(return_value=httpx.Response(503))
    else:
        respx.post(PREVIAS).mock(
            return_value=httpx.Response(200, json={"previas": previas})
        )
    respx.get(FUSOES).mock(
        return_value=httpx.Response(200, json={"fusoes": fusoes or []})
    )


def previa(impedimento="", em_comum=1):
    return {
        "canonica": {
            "id": CANONICA,
            "titulo": "Anatomia de cabelo e estilos variados para Roblox UGC",
            "votos": 9,
            "pessoas": 9,
            "comentarios": 0,
        },
        "absorvidas": [
            {
                "id": ABSORVIDA_A,
                "titulo": "Tutorial de base de cabelo",
                "votos": 2,
                "pessoas": 3,
                "comentarios": 0,
            },
            {
                "id": ABSORVIDA_B,
                "titulo": "Tutorial de cabelos cacheados",
                "votos": 3,
                "pessoas": 3,
                "comentarios": 0,
            },
        ],
        "votos_hoje": 14,
        "votos_depois": 13,
        "votos_em_comum": em_comum,
        "pessoas_depois": 13,
        "comentarios_depois": 0,
        "impedimento": impedimento,
    }


RE_ESTILO = re.compile("<style\\b[^>]*>.*?</style\\s*>", re.DOTALL | re.IGNORECASE)


def texto(resposta) -> str:
    return RE_ESTILO.sub("", resposta.content.decode())


def _abrir(cliente):
    return cliente.get(reverse("caixa_analise"))


# ---------------------------------------------------------------------------
# 1. O botão só existe quando dá para ver antes
# ---------------------------------------------------------------------------


@respx.mock
def test_sem_previa_a_analise_abre_e_o_botao_de_juntar_nao_aparece():
    """Fail-open na leitura, fail-closed na ação."""
    cliente = _dentro()
    a_caixa_responde(previas=None)

    pagina = texto(_abrir(cliente))

    assert "As junções que eu proporia" in pagina
    # O que tem de sumir é o BOTÃO, não a explicação da seção.
    assert f'href="#fundir-{CANONICA}"' not in pagina
    assert "Ver como ficaria" not in pagina
    assert "Juntar de verdade" not in pagina
    assert "a Caixa não respondeu" in pagina


@respx.mock
def test_com_previa_o_botao_aparece_e_o_modal_existe():
    cliente = _dentro()
    a_caixa_responde(previas=[previa()])

    pagina = texto(_abrir(cliente))

    assert "Ver como ficaria" in pagina
    assert f'id="fundir-{CANONICA}"' in pagina
    assert f'href="#fundir-{CANONICA}"' in pagina
    assert "Juntar de verdade" in pagina


# ---------------------------------------------------------------------------
# 2. O modal diz a verdade sobre o número que encolhe
# ---------------------------------------------------------------------------


@respx.mock
def test_o_modal_mostra_o_total_depois_e_explica_por_que_ele_e_menor():
    cliente = _dentro()
    a_caixa_responde(previas=[previa(em_comum=1)])

    pagina = texto(_abrir(cliente))

    assert "13" in pagina and "14" in pagina
    assert "votos depois da junção" in pagina
    assert "é quanto seria se fosse soma" in pagina
    assert "votou em mais de uma destas ideias" in pagina
    assert "ninguém perde nada" in pagina


@respx.mock
def test_sem_voto_em_comum_a_tela_nao_explica_o_que_nao_aconteceu():
    cliente = _dentro()
    a_caixa_responde(previas=[previa(em_comum=0)])

    pagina = texto(_abrir(cliente))

    assert "votou em mais de uma destas ideias" not in pagina


@respx.mock
def test_o_impedimento_aparece_escrito_e_o_confirmar_some():
    cliente = _dentro()
    a_caixa_responde(
        previas=[previa(impedimento="Uma das ideias já foi juntada a outra.")]
    )

    pagina = texto(_abrir(cliente))

    assert "Uma das ideias já foi juntada a outra." in pagina
    assert "não dá agora" in pagina
    assert "Juntar de verdade" not in pagina


# ---------------------------------------------------------------------------
# 3. Confirmar e desfazer
# ---------------------------------------------------------------------------


@respx.mock
def test_confirmar_manda_juntar_e_volta_dizendo(db):
    cliente = _dentro()
    a_caixa_responde(previas=[previa()])
    escrita = respx.post(FUSOES).mock(return_value=httpx.Response(200, json={}))

    resposta = cliente.post(
        reverse("caixa_fundir"),
        {
            "canonica": CANONICA,
            "absorvidas": f"{ABSORVIDA_A},{ABSORVIDA_B}",
            "nota": "de uma vez",
        },
    )

    assert resposta.status_code == 302
    assert "recado=" in resposta["Location"]
    corpo = json.loads(escrita.calls.last.request.content)
    assert corpo["canonica"] == CANONICA
    assert corpo["absorvidas"] == [ABSORVIDA_A, ABSORVIDA_B]
    assert corpo["nota"] == "de uma vez"
    # E quem agiu viaja junto: sem isso a Caixa recusa a escrita ([INV-SUG12]).
    assert corpo["por_email"] == DONO
    assert Registro.objects.filter(acao=Registro.FUNDIR_IDEIAS).exists()


@respx.mock
def test_a_recusa_da_caixa_chega_inteira_na_tela(db):
    cliente = _dentro()
    a_caixa_responde(previas=[previa()])
    respx.post(FUSOES).mock(
        return_value=httpx.Response(
            422, json={"erro": "Uma das ideias já foi juntada a outra."}
        )
    )

    resposta = cliente.post(
        reverse("caixa_fundir"),
        {"canonica": CANONICA, "absorvidas": f"{ABSORVIDA_A}"},
    )

    assert "erro=" in resposta["Location"]
    assert "juntada" in resposta["Location"]
    registro = Registro.objects.get(acao=Registro.FUNDIR_IDEIAS)
    assert registro.desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
def test_desfazer_manda_desfazer_e_deixa_rastro(db):
    cliente = _dentro()
    a_caixa_responde(previas=[previa()])
    respx.post(f"{FUSOES}/7/desfazer").mock(return_value=httpx.Response(200, json={}))

    resposta = cliente.post(reverse("caixa_desfazer_fusao", args=[7]))

    assert resposta.status_code == 302
    assert "recado=" in resposta["Location"]
    assert Registro.objects.filter(acao=Registro.DESFAZER_FUSAO).exists()


@respx.mock
def test_juntar_por_get_nao_existe():
    """Gesto que muda coisa é POST: um GET seria disparado por pré-carregamento."""
    cliente = _dentro()
    a_caixa_responde(previas=[previa()])

    assert cliente.get(reverse("caixa_fundir")).status_code == 405
    assert cliente.get(reverse("caixa_desfazer_fusao", args=[7])).status_code == 405


# ---------------------------------------------------------------------------
# 4. O que já foi juntado, e o desfazer à mão
# ---------------------------------------------------------------------------


@respx.mock
def test_a_juncao_feita_aparece_com_o_botao_de_desfazer():
    cliente = _dentro()
    a_caixa_responde(
        previas=[previa()],
        fusoes=[
            {
                "id": 7,
                "canonica": {
                    "id": CANONICA,
                    "titulo": "Anatomia de cabelo",
                    "votos": 13,
                    "pessoas": 13,
                    "comentarios": 0,
                },
                "absorvidas": [
                    {
                        "id": ABSORVIDA_A,
                        "titulo": "Base de cabelo",
                        "votos_movidos": 2,
                        "votos_descartados": 1,
                        "comentarios_movidos": 0,
                    }
                ],
                "nota": "",
                "feita_em": "2026-09-05T12:00:00+00:00",
                "em_vigor": True,
            }
        ],
    )

    pagina = texto(_abrir(cliente))

    assert "As junções já feitas" in pagina
    assert "Desfazer esta junção" in pagina
    assert reverse("caixa_desfazer_fusao", args=[7]) in pagina
    # E a tela conta o que aconteceu com os votos, sem eufemismo.
    assert "2 votos" in pagina
    assert "já tinha votado nas duas" in pagina


@respx.mock
def test_sem_juncao_feita_a_secao_nao_aparece():
    cliente = _dentro()
    a_caixa_responde(previas=[previa()], fusoes=[])

    assert "As junções já feitas" not in texto(_abrir(cliente))
