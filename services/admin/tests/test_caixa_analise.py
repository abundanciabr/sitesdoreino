"""A aba da análise da Caixa (05/09/2026).

O que estes guardas protegem, em ordem de quanto dói perder:

1. **Nenhum número desta tela é cópia congelada.** É a propriedade que faz a
   página valer mais que o documento que ela substituiu: mudou o voto na Caixa,
   mudou a tela, sem ninguém reescrever nada. Um número cravado no template
   passaria em qualquer teste de "a página abre" e mentiria em silêncio a
   partir do primeiro voto novo.
2. **Ideia que chega depois da leitura não some.** O laço é sobre o que a Caixa
   responde, nunca sobre o dicionário escrito à mão; ideia sem análise aparece
   dizendo que não foi lida.
3. **Análise de ideia que morreu não aparece.** Arquivar é dizer que aquilo saiu
   do quadro, e a tela obedece à Caixa.
4. **Nome de aluno não aparece**, nem de quem escreveu nem de quem comentou.
5. **A página não tem JavaScript.** A porta manda `script-src 'self'`, e o modal
   abre por CSS (`:target`). Um script aqui custaria exceção na política.
6. **Fail-OPEN:** a Caixa fora do ar deixa a página abrir com um aviso honesto,
   nunca com uma lista vazia que se leria como "ninguém escreveu nada".

A rede é dublada com `respx`, como nos irmãos desta pasta: além de isolar, é
prova mecânica de que nada aqui sai para a internet.
"""

import re

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
CAIXA = "http://sugestoes:8000/interno"
IDEIAS = f"{CAIXA}/gestao/ideias"
PREVIAS = f"{CAIXA}/gestao/fusoes/previas"
FUSOES = f"{CAIXA}/gestao/fusoes"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"

AUTOR = "Larissa Mendonca"
QUEM_COMENTOU = "Rafael Guimaraes"

# Duas ideias REAIS do quadro, e a escolha não é decorativa: 20 e 21 são as que
# têm análise escrita, então elas provam a junção. Um id inventado provaria só
# que a página abre.
ACESSORIOS = 20
PORTFOLIO = 21


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


def ideia(**campos) -> dict:
    """Uma ideia na forma EXATA que o contrato promete."""
    base = {
        "id": ACESSORIOS,
        "titulo": "tutorial de chapéu / acessórios",
        "problema": "No curso não tem uma aula especifica sobre isso.",
        "solucao_proposta": "",
        "categoria": "Curso e aulas",
        "status": "planejado",
        "votos": 40,
        "comentarios": 0,
        "pessoas": 41,
        "autor": AUTOR,
        "criada_em": "2026-08-31T10:00:00+00:00",
        "parada_desde": "2026-09-04T10:00:00+00:00",
        "ja_ouviram": False,
        "tem_avaliacao": False,
        "tem_changespec": False,
        "motivo_da_saida": "",
        "avaliacao": None,
        "conversa": [],
    }
    base.update(campos)
    return base


def a_caixa_responde(ideias, **topo):
    corpo = {
        "quadro": "Meshcraft",
        "pode_assinar": True,
        "pessoas_esperando": 0,
        "silencio_medio_em_dias": None,
        "pessoas_em_silencio_demais": 0,
        "ideias": ideias,
    }
    corpo.update(topo)
    respx.get(IDEIAS).mock(return_value=httpx.Response(200, json=corpo))
    # As duas conversas que a tela passou a ter em 05/09/2026, quando o botão
    # de juntar nasceu (`DECISAO-fundir-ideias.md`). Aqui elas respondem VAZIO
    # de propósito: os guardas deste arquivo são sobre a leitura da análise, e
    # o dublê da junção mora em `test_caixa_fusao.py`. Sem estas duas linhas o
    # `respx` estoura em toda abertura de página — o que é ele fazendo o
    # trabalho dele: nenhuma requisição sai daqui sem estar declarada.
    respx.post(PREVIAS).mock(return_value=httpx.Response(200, json={"previas": []}))
    respx.get(FUSOES).mock(return_value=httpx.Response(200, json={"fusoes": []}))


RE_ESTILO = re.compile("<style\\b[^>]*>.*?</style\\s*>", re.DOTALL | re.IGNORECASE)


def texto(resposta) -> str:
    """A página SEM a folha de estilo embutida.

    Sem esta poda, um `assert "40" not in pagina` casaria com um `padding: 40px`
    e o teste falharia por um motivo que não tem nada a ver com o que ele mede.
    """
    return RE_ESTILO.sub("", resposta.content.decode())


def _analise(cliente):
    return cliente.get(reverse("caixa_analise"))


# ---------------------------------------------------------------------------
# 1. Os números são lidos, nunca guardados
# ---------------------------------------------------------------------------


@respx.mock
def test_o_voto_que_muda_na_caixa_muda_na_tela():
    """O guarda principal: a mesma ideia, dois números, duas telas diferentes.

    Se alguém um dia cravar "40 votos" no template ou na análise escrita à mão,
    é aqui que o projeto descobre — e descobre antes do mantenedor abrir a
    página e ler um número que não é mais verdade.
    """
    cliente = _dentro()

    a_caixa_responde([ideia(votos=40, pessoas=41)])
    primeira = texto(_analise(cliente))

    a_caixa_responde([ideia(votos=97, pessoas=99)])
    segunda = texto(_analise(cliente))

    assert "40 votos" in primeira
    assert "97 votos" in segunda
    assert "40 votos" not in segunda


@respx.mock
def test_a_soma_da_familia_e_a_conta_do_que_esta_vivo():
    """Família é soma calculada. Duas ideias de cabelo, uma conta só."""
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(id=ACESSORIOS, votos=40),
            ideia(id=31, titulo="Anatomia de cabelo", votos=9, pessoas=9),
        ]
    )

    pagina = texto(_analise(cliente))

    # 40 + 9, na coluna de votos da família "Cabelos e acessórios".
    assert "Cabelos e acessórios" in pagina
    assert ">49<" in pagina


@respx.mock
def test_a_ordem_e_por_voto_e_o_numero_da_posicao_acompanha():
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(id=PORTFOLIO, titulo="Guia de portifolio", votos=31, pessoas=31),
            ideia(id=ACESSORIOS, votos=40, pessoas=41),
        ]
    )

    pagina = texto(_analise(cliente))

    assert pagina.index("tutorial de chapéu") < pagina.index("Guia de portifolio")


# ---------------------------------------------------------------------------
# 2. O quadro manda; o dicionário escrito à mão obedece
# ---------------------------------------------------------------------------


@respx.mock
def test_ideia_que_chegou_depois_da_leitura_aparece_dizendo_que_nao_foi_lida():
    """O contrário disto seria a tela escondendo uma ideia por não conhecê-la."""
    cliente = _dentro()
    a_caixa_responde(
        [ideia(id=987, titulo="Uma ideia nascida amanhã", votos=3, pessoas=3)]
    )

    pagina = texto(_analise(cliente))

    assert "Uma ideia nascida amanhã" in pagina
    assert "Chegaram depois desta leitura" in pagina
    assert "sem análise ainda" in pagina


@respx.mock
def test_analise_de_ideia_que_saiu_do_quadro_nao_desenha_nada():
    """Arquivada ou apagada some da Caixa, e some daqui junto."""
    cliente = _dentro()
    a_caixa_responde([ideia(id=ACESSORIOS)])

    pagina = texto(_analise(cliente))

    # A ideia 21 tem análise escrita, mas a Caixa não a respondeu nesta abertura.
    assert "Guia de portfólio" not in pagina
    assert "CS-PAGES-0001" not in pagina


@respx.mock
def test_o_quadro_vazio_nao_estoura_e_nao_mente():
    cliente = _dentro()
    a_caixa_responde([])

    resposta = _analise(cliente)

    assert resposta.status_code == 200
    assert "0 ideia" in texto(resposta)


# ---------------------------------------------------------------------------
# 3. Privacidade, política de script e fail-OPEN
# ---------------------------------------------------------------------------


@respx.mock
def test_nome_de_quem_escreveu_e_de_quem_comentou_nunca_aparece():
    cliente = _dentro()
    a_caixa_responde(
        [
            ideia(
                comentarios=1,
                conversa=[{"texto": "achei ótima a ideia", "autor": QUEM_COMENTOU}],
            )
        ]
    )

    pagina = texto(_analise(cliente))

    assert "achei ótima a ideia" in pagina
    assert AUTOR not in pagina
    assert QUEM_COMENTOU not in pagina


@respx.mock
def test_a_pagina_nao_tem_javascript():
    """O modal abre por `:target`. Script aqui custaria exceção no CSP da porta."""
    cliente = _dentro()
    a_caixa_responde([ideia()])

    pagina = _analise(cliente).content.decode()

    assert "<script" not in pagina.lower()
    assert "onclick" not in pagina.lower()


@respx.mock
def test_o_modal_de_cada_ideia_existe_e_o_titulo_leva_ate_ele():
    cliente = _dentro()
    a_caixa_responde([ideia()])

    pagina = texto(_analise(cliente))

    assert f'id="ideia-{ACESSORIOS}"' in pagina
    assert f'href="#ideia-{ACESSORIOS}"' in pagina
    # Fechar volta para o cartão, não para o topo da página.
    assert f'href="#ficha-{ACESSORIOS}"' in pagina


@respx.mock
def test_a_caixa_fora_do_ar_abre_a_pagina_dizendo_isso():
    cliente = _dentro()
    respx.get(IDEIAS).mock(return_value=httpx.Response(503))

    resposta = _analise(cliente)

    assert resposta.status_code == 200
    pagina = texto(resposta)
    assert "Não consegui perguntar à Caixa agora" in pagina
    # E a honestidade que a lista vazia destruiria: nada de "0 ideias".
    assert "Os agrupamentos" not in pagina


@respx.mock
def test_texto_de_aluno_nao_vira_marcacao():
    cliente = _dentro()
    a_caixa_responde([ideia(problema="<b>oi</b> <script>alert(1)</script>")])

    pagina = _analise(cliente).content.decode()

    assert "<script>alert(1)</script>" not in pagina
    assert "&lt;b&gt;oi&lt;/b&gt;" in pagina
