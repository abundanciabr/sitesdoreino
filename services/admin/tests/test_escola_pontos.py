"""A tela `/admin/escola/pontos/` — o quadro de pontos da turma.

O que estes guardas protegem:

1. **Esta tela não guarda nada.** Cruza `AlunosClient().alunos()`,
   `GamificacaoClient().quadro()` e `IdentidadeClient().pessoa_por_id()` na
   hora — nenhuma tabela nova nasce por causa dela.
2. **A resolução de e-mail é limitada a quem já tem ponto.** Um aluno sem
   nenhuma entrada no quadro NUNCA gera uma chamada a `/pessoas/por-id`.
3. **Zero, "nunca pontuou" e "parou" são três respostas diferentes.**
4. **Cada pergunta pode falhar sozinha**, sem derrubar as outras duas.
5. **A porta continua sendo a porta**: sem crachá, nada disto responde.
"""

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
POR_ID = f"{IDENTIDADE}/pessoas/por-id"
GAMIFICACAO = "http://gamificacao:8000/api/gamificacao"
ALUNOS = "http://alunos:8000/api/alunos"
MATRICULAS = f"{ALUNOS}/matriculas"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


def _aluno(id_, **campos):
    base = {
        "id": id_,
        "site_id": "site-a",
        "email": f"{id_}@exemplo.com",
        "nome_completo": id_.capitalize(),
        "whatsapp": "5511999990000",
        "turma": "turma-a",
        "comprou_em": "2026-08-01",
        "status": "ativa",
        "origem": "comprou",
        "criada_em": "2026-08-01T10:00:00Z",
    }
    base.update(campos)
    return base


def _entrada(pessoa_id, **campos):
    base = {
        "pessoa_id": pessoa_id,
        "xp": 100,
        "nivel": 2,
        "ultima_atividade_em": "2026-09-02T10:00:00Z",
        "conquistas": [],
    }
    base.update(campos)
    return base


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    monkeypatch.setenv("GAMIFICACAO_API_URL", GAMIFICACAO)
    monkeypatch.setenv("TOKEN_GAMIFICACAO", "token-do-par-admin-gamificacao")
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-do-dono",
                "nome_exibido": "Dono",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


def _mundo(*, alunos=None, quadro=None, degraus=None, conquistas=None, emails=None):
    """Monta os dublês das três células. `emails` é `{pessoa_id: email|None}`
    — cada chave vira UMA mock de `/pessoas/por-id`, e uma ausência na lista
    de `quadro` não gera chamada nenhuma (é o que os testes de limite provam).
    """
    respx.get(MATRICULAS, params={"status": "ativa"}).mock(
        return_value=httpx.Response(200, json=alunos if alunos is not None else [])
    )
    respx.get(f"{GAMIFICACAO}/quadro").mock(
        return_value=httpx.Response(200, json=quadro if quadro is not None else [])
    )
    respx.get(f"{GAMIFICACAO}/economia/degraus").mock(
        return_value=httpx.Response(200, json=degraus if degraus is not None else [])
    )
    respx.get(f"{GAMIFICACAO}/economia/conquistas").mock(
        return_value=httpx.Response(
            200, json=conquistas if conquistas is not None else []
        )
    )
    for pessoa_id, email in (emails or {}).items():
        respx.post(POR_ID, json={"id": pessoa_id}).mock(
            return_value=httpx.Response(200, json={"email": email, "idioma": None})
        )


# ---------------------------------------------------------------------------
# A porta
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_sem_cracha_a_tela_nao_responde():
    respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )

    resposta = Client().get(reverse("escola_pontos"))

    assert resposta.status_code in (302, 403)


# ---------------------------------------------------------------------------
# O cruzamento
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_ordena_por_pontos_com_nivel_e_titulo():
    alunos = [_aluno("ana"), _aluno("bia")]
    quadro = [
        _entrada("p-ana", xp=50, nivel=1),
        _entrada("p-bia", xp=300, nivel=3),
    ]
    _mundo(
        alunos=alunos,
        quadro=quadro,
        degraus=[
            {
                "nivel": 1,
                "titulo": "Aprendiz",
                "titulo_feminino": "",
                "xp_necessario": 0,
                "ativa": True,
                "versao": 1,
                "impedimentos": [],
            },
            {
                "nivel": 3,
                "titulo": "Mestre de Ateliê",
                "titulo_feminino": "",
                "xp_necessario": 200,
                "ativa": True,
                "versao": 1,
                "impedimentos": [],
            },
        ],
        emails={"p-ana": "ana@exemplo.com", "p-bia": "bia@exemplo.com"},
    )

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    pos_bia = html.index("Bia")
    pos_ana = html.index("Ana")
    assert pos_bia < pos_ana, "quem tem mais pontos precisa vir primeiro"
    assert "300 pontos" in html
    assert "Mestre de Ateliê" in html


@respx.mock
@pytest.mark.django_db
def test_aluno_sem_entrada_no_quadro_aparece_com_zero_e_nunca_pontuou():
    """`PerfilJogador` é preguiçoso: sem XP nenhum, sem linha na porta."""
    _mundo(alunos=[_aluno("carlos")], quadro=[])

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    assert "Carlos" in html
    assert "0 pontos" in html
    assert "Nunca pontuou" in html


@respx.mock
@pytest.mark.django_db
def test_resolucao_de_email_nao_chama_a_identidade_por_quem_nao_tem_ponto():
    """O limite que faz esta tela escalar com o USO, não com a matrícula: só
    quem está no quadro gera uma chamada a `/pessoas/por-id`."""
    _mundo(alunos=[_aluno("ana"), _aluno("carlos")], quadro=[_entrada("p-ana")])
    chamada = respx.post(POR_ID, json={"id": "p-ana"}).mock(
        return_value=httpx.Response(
            200, json={"email": "ana@exemplo.com", "idioma": None}
        )
    )
    nunca_chamada = respx.post(POR_ID, json={"id": "p-carlos"})

    _dentro().get(reverse("escola_pontos"))

    assert chamada.called
    assert not nunca_chamada.called


@respx.mock
@pytest.mark.django_db
def test_email_que_a_identidade_nao_reconhece_fica_como_zero():
    """`email: null` é RESPOSTA no contrato da identidade, não erro — a linha
    do aluno simplesmente não casa com nenhuma entrada do quadro."""
    _mundo(alunos=[_aluno("ana")], quadro=[_entrada("p-orfa", xp=999)])
    respx.post(POR_ID, json={"id": "p-orfa"}).mock(
        return_value=httpx.Response(200, json={"email": None, "idioma": None})
    )

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    assert "999" not in html, "o XP de um id não resolvido vazou para outra pessoa"
    assert "0 pontos" in html


@respx.mock
@pytest.mark.django_db
def test_quem_parou_e_quem_esta_jogando_sao_rotulos_diferentes():
    import datetime

    from django.utils import timezone

    recente = (
        (timezone.now() - datetime.timedelta(days=1)).isoformat().replace("+00:00", "Z")
    )
    antigo = (
        (timezone.now() - datetime.timedelta(days=30))
        .isoformat()
        .replace("+00:00", "Z")
    )
    _mundo(
        alunos=[_aluno("ana"), _aluno("bia")],
        quadro=[
            _entrada("p-ana", ultima_atividade_em=recente),
            _entrada("p-bia", ultima_atividade_em=antigo),
        ],
        emails={"p-ana": "ana@exemplo.com", "p-bia": "bia@exemplo.com"},
    )

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    assert "Jogando" in html
    assert "Parado" in html


@respx.mock
@pytest.mark.django_db
def test_conquistas_aparecem_traduzidas_pelo_nome_da_definicao():
    _mundo(
        alunos=[_aluno("ana")],
        quadro=[
            _entrada(
                "p-ana",
                conquistas=[
                    {
                        "slug": "primeira-obra",
                        "classe": "medalha",
                        "concedida_em": "2026-09-01T10:00:00Z",
                    }
                ],
            )
        ],
        conquistas=[
            {
                "slug": "primeira-obra",
                "nome": "Primeira obra",
                "descricao": "",
                "classe": "medalha",
                "familia": "oficio",
                "pontos": 10,
                "cristais": 0,
                "envolve_dinheiro": False,
                "exige_validador_da_equipe": False,
                "ativa": True,
                "versao": 1,
                "impedimentos": [],
            }
        ],
        emails={"p-ana": "ana@exemplo.com"},
    )

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    assert "Primeira obra" in html


@respx.mock
@pytest.mark.django_db
def test_o_link_do_prontuario_usa_o_email_do_aluno():
    _mundo(alunos=[_aluno("ana")], quadro=[])

    html = _dentro().get(reverse("escola_pontos")).content.decode()

    assert "escola/alunos/prontuario?email=ana%40exemplo.com" in html


# ---------------------------------------------------------------------------
# Fail-open por metade
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.django_db
def test_sem_lista_de_alunos_a_tela_avisa_e_nao_quebra(monkeypatch):
    monkeypatch.delenv("ALUNOS_API_TOKEN", raising=False)
    respx.get(f"{GAMIFICACAO}/quadro").mock(return_value=httpx.Response(200, json=[]))
    respx.get(f"{GAMIFICACAO}/economia/degraus").mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{GAMIFICACAO}/economia/conquistas").mock(
        return_value=httpx.Response(200, json=[])
    )

    resposta = _dentro().get(reverse("escola_pontos"))

    assert resposta.status_code == 200
    assert "Ainda não consigo ver a lista de alunos" in resposta.content.decode()


@respx.mock
@pytest.mark.django_db
def test_sem_o_par_da_gamificacao_a_lista_de_alunos_continua_completa(monkeypatch):
    """Fail-OPEN por tile: a metade que responde não cai junto."""
    monkeypatch.delenv("TOKEN_GAMIFICACAO", raising=False)
    respx.get(MATRICULAS, params={"status": "ativa"}).mock(
        return_value=httpx.Response(200, json=[_aluno("ana")])
    )

    resposta = _dentro().get(reverse("escola_pontos"))
    html = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Ana" in html
    assert "Ainda não consigo ver os pontos" in html
