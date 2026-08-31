"""A tela `/admin/economia/` — onde o mantenedor liga e desliga cada regra.

O que estes guardas protegem:

1. **Esta tela não guarda nada.** Ela lê e liga na `gamificacao`, que é a dona da
   economia. Uma cópia aqui seria o mesmo fato em dois lugares, e no dia em que
   as duas discordassem a tela mostraria uma coisa e o motor pagaria outra.
2. **Os avisos aparecem ANTES do clique.** Uma regra pode estar ligada e ainda
   assim não fazer número nenhum se mexer; sem o aviso, o mantenedor ligaria a
   primeira, veria zero, e o zero pareceria defeito da tela.
3. **A quarentena é dita em português**, porque é a parte que mais confunde quem
   olha o número: o ponto é creditado na hora e só entra no perfil depois.
4. **Cada gesto vira linha de auditoria**, inclusive quando a gamificação
   recusa. É metade do "anunciado" que a lei §10.5 exige — a outra metade é a
   `vigente_desde`, que mora na gamificação.
5. **Par de tokens ausente abre a tela mesmo assim**, dizendo o que falta.
   Fail-OPEN na leitura: uma tela de operação que não abre é inútil justamente
   quando você precisa dela.
6. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

import json

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
GAMIFICACAO = "http://gamificacao:8000/api/gamificacao"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


def _regra(slug, **campos):
    base = {
        "slug": slug,
        "evento_gatilho": "sugestao.criada.v1",
        "beneficiario": "ator",
        "pontos": 10,
        "cristais": 0,
        "acoes_cheias_por_dia": 0,
        "quarentena_horas": 0,
        "ativa": False,
        "versao": 1,
        "vigente_desde": None,
        "impedimentos": [],
    }
    base.update(campos)
    return base


REGRAS = [
    _regra("sugestao-criada", quarentena_horas=24),
    _regra("quiz-aprovado", pontos=30, impedimentos=["sem-credito"]),
    _regra("aula-concluida", pontos=25, impedimentos=["sem-produtor"]),
    _regra(
        "sugestao-implementada",
        pontos=40,
        cristais=5,
        impedimentos=["cristais-sem-efeito"],
    ),
]


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "token-do-par-admin-gamificacao")
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


def _gamificacao(regras=None, resposta_do_gesto=None):
    respx.get(f"{GAMIFICACAO}/economia/regras").mock(
        return_value=httpx.Response(200, json=regras if regras is not None else REGRAS)
    )
    return respx.post(url__startswith=f"{GAMIFICACAO}/economia/regras/").mock(
        return_value=resposta_do_gesto
        or httpx.Response(200, json=_regra("sugestao-criada", ativa=True, versao=2))
    )


# ---------------------------------------------------------------------------
# A porta
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_sem_cracha_a_tela_nao_responde():
    """A porta desta área vem antes da tela, como em toda rota do `/admin/`."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )

    resposta = Client().get(reverse("economia"))

    assert resposta.status_code in (302, 403)


@respx.mock
@pytest.mark.django_db
def test_sem_cracha_ninguem_liga_regra_nenhuma():
    """A ESCRITA é a que mais importa: ela muda a economia da escola."""
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )
    gesto = _gamificacao()

    resposta = Client().post(
        reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "1"}
    )

    assert resposta.status_code in (302, 403)
    assert not gesto.called, "a tela chamou a gamificação sem crachá"


# ---------------------------------------------------------------------------
# A leitura
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_a_tela_mostra_as_regras_traduzidas_para_portugues():
    """Slug, nunca frase pronta — a frase em português é DESTA tela."""
    _gamificacao()

    html = _dentro().get(reverse("economia")).content.decode()

    assert "Mandar uma sugestão" in html
    assert "Terminar o quiz" in html
    assert "Ter a própria sugestão feita" in html


@respx.mock
@pytest.mark.django_db
def test_a_tela_diz_quantas_estao_ligadas_e_hoje_e_nenhuma():
    """O estado que ele precisa ver de longe: ninguém está ganhando ponto."""
    _gamificacao()

    html = _dentro().get(reverse("economia")).content.decode()

    assert "Nenhuma regra está ligada" in html


@respx.mock
@pytest.mark.django_db
def test_a_regra_que_nao_vai_adiantar_avisa_antes_do_clique():
    """O guarda que evita o zero que parece defeito da tela.

    `sem-produtor` (nada no site avisa aquilo ainda) e `sem-credito` (o aviso
    chega sem dizer de quem é o ponto) são fatos que a gamificação mede; a frase
    é daqui.
    """
    _gamificacao()

    html = _dentro().get(reverse("economia")).content.decode()

    assert "nada no site avisa quando isso acontece" in html
    assert "sem dizer de quem é o ponto" in html


@respx.mock
@pytest.mark.django_db
def test_a_regra_de_cristais_avisa_que_os_cristais_nao_saem():
    """O XP sai; o Cristal não. E a tela diz isso ANTES, não depois.

    Mexer no vocabulário de origens de Cristal é decisão do mantenedor, e é a
    trava que garante que Cristal não se compra ([INV-GAM1]).
    """
    _gamificacao()

    html = _dentro().get(reverse("economia")).content.decode()

    assert "os Cristais NÃO" in html


@respx.mock
@pytest.mark.django_db
def test_a_espera_da_quarentena_e_dita_em_portugues():
    """A parte que mais confunde: o ponto é pago na hora e aparece depois.

    Sem esta frase ele liga, faz a ação, não vê o número mexer e conclui que
    está quebrado — quando é a janela de estorno funcionando como projetada.
    """
    _gamificacao()

    html = _dentro().get(reverse("economia")).content.decode()

    assert "24 horas depois" in html


@respx.mock
@pytest.mark.django_db
def test_sem_o_par_de_tokens_a_tela_ABRE_e_diz_o_que_falta(monkeypatch):
    """Fail-OPEN: tela de operação que não abre é inútil quando se precisa dela."""
    monkeypatch.delenv("TOKEN_GAMIFICACAO", raising=False)

    resposta = _dentro().get(reverse("economia"))

    assert resposta.status_code == 200
    html = resposta.content.decode()
    assert "Ainda não consigo falar com a parte das conquistas" in html
    assert "continua desligada" in html


# ---------------------------------------------------------------------------
# O gesto
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_ligar_manda_o_pedido_certo_e_volta_para_a_tela():
    gesto = _gamificacao()

    resposta = _dentro().post(
        reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "1"}
    )

    assert resposta.status_code == 302
    assert resposta["Location"].endswith("?recado=ligada")
    assert gesto.calls.last.request.url.path.endswith(
        "/economia/regras/sugestao-criada"
    )
    assert json.loads(gesto.calls.last.request.content) == {"ativa": True}


@respx.mock
@pytest.mark.django_db
def test_desligar_manda_o_contrario():
    gesto = _gamificacao()

    resposta = _dentro().post(
        reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "0"}
    )

    assert resposta.status_code == 302
    assert json.loads(gesto.calls.last.request.content) == {"ativa": False}


@respx.mock
@pytest.mark.django_db
def test_ligar_deixa_linha_de_auditoria_com_verbo_proprio():
    """Metade do "anunciado" da lei §10.5: QUEM mandou e QUANDO pediu.

    A outra metade é a `vigente_desde`, na gamificação, que guarda DESDE QUANDO
    a regra vale. Fatos diferentes, nenhum cópia do outro.
    """
    _gamificacao()

    _dentro().post(reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "1"})

    registro = Registro.objects.latest("id")
    assert registro.acao == Registro.LIGAR_REGRA
    assert registro.alvo == "sugestao-criada"
    assert registro.desfecho == Registro.OK


@respx.mock
@pytest.mark.django_db
def test_desligar_usa_o_OUTRO_verbo():
    """Dois verbos, e não um "mudar_regra": "desde quando paga?" se responde
    lendo os LIGAR, e um verbo só tornaria essa leitura impossível."""
    _gamificacao()

    _dentro().post(reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "0"})

    assert Registro.objects.latest("id").acao == Registro.DESLIGAR_REGRA


@respx.mock
@pytest.mark.django_db
def test_regra_desconhecida_vira_frase_na_tela_e_nao_500():
    _gamificacao(resposta_do_gesto=httpx.Response(404, json={"detail": "não há"}))

    resposta = _dentro().post(
        reverse("economia_mudar"), {"slug": "regra-que-nao-existe", "ativa": "1"}
    )

    assert resposta.status_code == 422
    assert "essa regra não existe nesta escola" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_a_recusa_tambem_deixa_linha_de_auditoria():
    """Gesto que não pegou também é fato — e é o que se procura depois."""
    _gamificacao(resposta_do_gesto=httpx.Response(404, json={"detail": "não há"}))

    _dentro().post(reverse("economia_mudar"), {"slug": "nao-existe", "ativa": "1"})

    registro = Registro.objects.latest("id")
    assert registro.acao == Registro.LIGAR_REGRA
    assert registro.desfecho == Registro.RECUSADO_PELA_CELULA


@respx.mock
@pytest.mark.django_db
def test_gamificacao_muda_e_a_tela_mostra_o_que_esta_GRAVADO():
    """Nunca o rascunho recusado: a página não pode discordar do motor.

    É sobre este número que ele vai confiar depois, e uma tela que mostra o
    gesto que não pegou é pior que uma tela que diz "não deu".
    """
    _gamificacao(resposta_do_gesto=httpx.Response(503))

    resposta = _dentro().post(
        reverse("economia_mudar"), {"slug": "sugestao-criada", "ativa": "1"}
    )

    assert resposta.status_code == 503
    html = resposta.content.decode()
    # As regras vieram da leitura, e nelas `sugestao-criada` continua DESLIGADA.
    assert "Nenhuma regra está ligada" in html
