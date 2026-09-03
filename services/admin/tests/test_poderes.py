"""Administrador por botão — `DECISAO-administradores-e-apagar`.

O mantenedor pediu as duas em 28/08/2026, **contra a recomendação do agente e
com o preço apresentado antes da escolha**. A lei §2 escreve o que se perdeu:

> Até então, para alguém virar administrador da plataforma, era preciso ter as
> chaves do servidor. Com o botão, isso deixa de ser verdade.

**As quatro travas do §3 são o que torna a troca aceitável — e são elas que
este arquivo mede.** Uma trava que não tem teste é uma promessa, e a lei foi
escrita justamente porque promessa não basta aqui:

1. `test_o_env_e_o_chao_e_o_botao_nao_o_alcanca` — não existe sequência de
   cliques que tranque todo mundo para fora.
2. `test_banco_fora_do_ar_vale_so_o_env` — erro nunca AMPLIA quem entra.
3. `test_promover_e_remover_deixam_rastro` — o que mexer no servidor deixava
   de outro jeito.
4. `test_ninguem_se_remove_sozinho` — um clique errado do único administrador
   deixaria a casa sem dono.

**A OUTRA metade daquela lei foi revertida em 29/08/2026** pela
`DECISAO-a-ficha-nao-se-apaga.md`: o botão que apagava a ficha de vez saiu, e
com ele a rota, o método de cliente e a porta da `alunos`. Os testes que
mediam o apagar deram lugar a `test_nao_existe_caminho_para_apagar` — o que
precisa de guarda agora é a AUSÊNCIA, porque um botão removido volta com uma
linha de template e ninguém percebe.

**03/09/2026 — a guarda ficou mais ESTREITA, por decisão do mantenedor, não
por engano.** `DECISAO-apagar-recusado-definitivamente.md` abriu uma exceção:
`AlunosClient` ganhou um método que fala DELETE de verdade
(`apagar_recusado`), o primeiro desde 29/08. `test_nao_existe_caminho_para_apagar`
não pôde mais dizer "nenhum DELETE nesta classe" — passou a dizer "nenhum
DELETE mira uma matrícula REAL", que é a garantia que sempre importou. A
ausência de `escola_aluno_apagar` e de `AlunosClient.apagar_aluno` continua
sendo medida linha a linha, sem mudança nenhuma.
"""

import inspect
import re

import httpx
import pytest
import respx
from django.db import DatabaseError
from django.test import Client
from django.urls import NoReverseMatch, reverse

from apps.auditoria.models import Registro
from apps.core.clients import AlunosClient
from apps.core.models import Administrador
from apps.core.porta import _emails_autorizados

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
ALUNOS = "http://alunos:8000/api/alunos"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
ID_DO_DONO = "id-opaco-123"
OUTRO = "outro@exemplo.com"
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


# ---------------------------------------------- as duas metades da lista


@pytest.mark.django_db
def test_a_lista_efetiva_soma_o_env_e_o_banco():
    assert _emails_autorizados() == frozenset({DONO})
    Administrador.objects.create(email=OUTRO)
    assert _emails_autorizados() == frozenset({DONO, OUTRO})


@pytest.mark.django_db
def test_removido_do_banco_sai_da_lista_mas_a_linha_fica():
    """Remover é DESATIVAR: a linha dá contexto às linhas de auditoria."""
    Administrador.objects.create(email=OUTRO)
    Administrador.objects.filter(email=OUTRO).update(ativo=False)

    assert OUTRO not in _emails_autorizados()
    assert Administrador.objects.filter(email=OUTRO).exists()


@pytest.mark.django_db
def test_o_email_e_guardado_normalizado():
    """Uma linha com maiúscula seria uma promoção que não vale nada — e que
    ninguém consegue explicar olhando a tela."""
    Administrador.objects.create(email="  MAIUSCULA@Exemplo.COM ")
    assert "maiuscula@exemplo.com" in _emails_autorizados()


@pytest.mark.django_db
def test_banco_fora_do_ar_vale_so_o_env(monkeypatch):
    """Trava §3.2: erro nunca AMPLIA quem entra.

    A direção do fail é o que separa uma indisponibilidade de uma brecha. E o
    env continuar valendo é o que impede o banco fora do ar de trancar o
    mantenedor para fora da ferramenta que ele usa quando algo está errado.
    """
    Administrador.objects.create(email=OUTRO)

    def explode(*args, **kwargs):
        raise DatabaseError("banco caiu")

    monkeypatch.setattr(
        "apps.core.porta.Administrador.objects", type("X", (), {"filter": explode})()
    )
    assert _emails_autorizados() == frozenset({DONO})


# ------------------------------------------------- promover e remover


@pytest.mark.django_db
@respx.mock
def test_promover_deixa_a_pessoa_entrar_e_deixa_rastro():
    r = _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})

    assert r["Location"].endswith("?resultado=promovido")
    assert OUTRO in _emails_autorizados()
    linha = Registro.objects.get()
    assert linha.acao == Registro.PROMOVER
    assert linha.alvo == OUTRO
    assert linha.quem_email == DONO


@pytest.mark.django_db
@respx.mock
def test_promover_duas_vezes_nao_cria_duas_linhas():
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    assert Administrador.objects.filter(email=OUTRO).count() == 1


@pytest.mark.django_db
@respx.mock
def test_promover_de_novo_quem_foi_removido_reativa():
    Administrador.objects.create(email=OUTRO, ativo=False)
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    assert OUTRO in _emails_autorizados()


@pytest.mark.django_db
@respx.mock
def test_remover_tira_o_cracha_e_deixa_rastro():
    Administrador.objects.create(email=OUTRO)
    r = _dentro().post(reverse("escola_admin_remover"), {"email": OUTRO})

    assert r["Location"].endswith("?resultado=despromovido")
    assert OUTRO not in _emails_autorizados()
    assert Registro.objects.get().acao == Registro.DESPROMOVER


@pytest.mark.django_db
@respx.mock
def test_o_env_e_o_chao_e_o_botao_nao_o_alcanca():
    """Trava §3.1: não existe sequência de cliques que tranque todo mundo fora.

    Se o botão pudesse remover quem está no servidor, a única saída seria o
    servidor — que é justamente o que o botão veio evitar.
    """
    r = _dentro().post(reverse("escola_admin_remover"), {"email": DONO})

    assert r["Location"].endswith("?resultado=so-no-servidor")
    assert DONO in _emails_autorizados()
    assert Registro.objects.count() == 0


@pytest.mark.django_db
@respx.mock
def test_ninguem_se_remove_sozinho():
    """Trava §3.4. Medido com alguém que NÃO está no env, para provar que a
    recusa é por ser você mesmo — e não pela trava anterior."""
    from django.test import Client as C

    Administrador.objects.create(email=OUTRO)
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-do-outro",
                "nome_exibido": "Outro",
                "papel": None,
                "email": OUTRO,
            },
        )
    )
    cliente = C()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    r = cliente.post(reverse("escola_admin_remover"), {"email": OUTRO})

    assert r["Location"].endswith("?resultado=voce-mesmo")
    assert OUTRO in _emails_autorizados()


@pytest.mark.django_db
@respx.mock
def test_quem_nao_e_admin_nao_promove_ninguem():
    r = _dentro("estranho@exemplo.com").post(
        reverse("escola_admin_promover"), {"email": OUTRO}
    )
    assert r.status_code == 404
    assert Administrador.objects.count() == 0


# ------------------------------------------------------- a ficha NAO se apaga
#
# `DECISAO-a-ficha-nao-se-apaga.md`, 29/08/2026: *"Eu quero que o cadastro do
# aluno NUNCA SEJA APAGADO"*. Os testes abaixo medem uma AUSÊNCIA, e por isso
# eles existem: o que foi removido daqui — uma rota, um método, um formulário —
# volta com uma linha em cada arquivo, e nenhum teste comum notaria.


def test_nao_existe_caminho_para_apagar():
    """As TRÊS camadas, e não só o botão.

    Tirar só o `<form>` do template deixaria a rota viva para quem soubesse o
    endereço; tirar a rota deixaria o método do cliente pronto para a próxima
    view que alguém escrevesse. A capacidade sai inteira ou não sai.

    03/09/2026: `AlunosClient` passou a ter UM método que fala DELETE de
    verdade — `apagar_recusado`, a exceção aberta por
    `DECISAO-apagar-recusado-definitivamente.md`. Por isso esta guarda não
    pode mais dizer "nenhum DELETE nesta classe"; ela diz o que sempre
    importou: nenhuma chamada DELETE mira uma matrícula REAL
    (`/matriculas/{id}`). A exceção só alcança `/pre-matriculas/{id}` — a
    fila, nunca quem já foi aluno.
    """
    with pytest.raises(NoReverseMatch):
        reverse("escola_aluno_apagar")

    assert not hasattr(AlunosClient, "apagar_aluno")

    fonte = inspect.getsource(AlunosClient)
    chamadas_delete = re.findall(r'\.delete\(\s*f"([^"]*)"', fonte)
    assert chamadas_delete, (
        "esperava pelo menos uma chamada DELETE nesta classe "
        "(apagar_recusado) — se ela sumiu, esta asserção precisa mudar "
        "de volta para a forma antiga"
    )
    for endereco in chamadas_delete:
        assert endereco.startswith("{base}/pre-matriculas/"), (
            f"chamada DELETE para {endereco!r} não é /pre-matriculas/ — "
            "isto reabriria o caminho de apagar uma matrícula real"
        )


@respx.mock
def test_a_tela_nao_oferece_apagar_e_explica_a_ausencia():
    """A tela não fica só sem o botão: ela CONTA o que aconteceu com ele.

    Sem essa linha, o mantenedor procuraria por um botão que ele mesmo pediu na
    véspera — e a explicação é onde mora a única coisa que ele precisa saber:
    que um pedido formal de exclusão de dados existe e passa por mim.
    """
    respx.get(f"{ALUNOS}/pre-matriculas", params={"status": "aguardando"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/pre-matriculas", params={"status": "recusada"}).mock(
        return_value=httpx.Response(200, json=[])
    )
    respx.get(f"{ALUNOS}/matriculas").mock(
        return_value=httpx.Response(
            200,
            json=[
                {
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
            ],
        )
    )
    html = _dentro().get("/escola/alunos/").content.decode()

    assert "escola/alunos/apagar" not in html
    assert "Apagar esta ficha" not in html
    assert "Nenhuma ficha se apaga por aqui" in html
    # O caminho que SUBSTITUI o botão continua na tela, com a palavra do
    # mantenedor: tirar o acesso é o estado "Ex-aluno" do seletor.
    assert "Ex-aluno" in html


@pytest.mark.django_db
def test_a_auditoria_nunca_ganha_campo_de_dado_da_pessoa():
    """A regra do `DECISAO-administradores-e-apagar` §4 que SOBREVIVEU.

    Esta tabela é append-only por trigger: um campo novo que guardasse nome ou
    telefone não teria como ser corrigido depois. O teste morava junto do
    apagar; sem ele, a única prova da regra iria embora com o botão.
    """
    campos = {c.name for c in Registro._meta.get_fields()}
    assert campos == {
        "id",
        "quando",
        "quem_email",
        "quem_id",
        "acao",
        "alvo",
        "desfecho",
        "detalhe",
    }


def test_o_verbo_apagar_continua_no_vocabulario_da_auditoria():
    """A tabela não se edita — nem para tirar um verbo de circulação.

    Se alguma linha antiga usou `apagar`, ela precisa continuar legível. O
    verbo fica; o que não existe mais é o caminho que o produzia.
    """
    assert Registro.APAGAR in dict(Registro.ACOES)


@respx.mock
@pytest.mark.parametrize("rota", ["escola_admin_promover", "escola_admin_remover"])
def test_as_rotas_de_poder_nao_atendem_GET(rota):
    assert _dentro().get(reverse(rota)).status_code == 405
