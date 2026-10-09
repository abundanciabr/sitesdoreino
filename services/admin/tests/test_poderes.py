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

import httpx
import pytest
import respx
from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
from apps.core.models import Administrador, AlunoRemovidoDaLista, RascunhoDeConfiguracao
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

    assert r["Location"].endswith("?resultado=rascunho")
    assert OUTRO not in _emails_autorizados()
    r = _dentro().post(reverse("escola_admin_publicar"), {"email": OUTRO})
    assert r["Location"].endswith("?resultado=publicado")
    assert OUTRO in _emails_autorizados()
    linha = Registro.objects.get()
    assert linha.acao == Registro.PROMOVER
    assert linha.alvo == OUTRO
    assert linha.quem_email == DONO


@respx.mock
def test_tornar_admin_aplica_na_ficha_e_nao_duplica_o_cadastro():
    cliente = _dentro()
    for _ in range(2):
        resposta = cliente.post(
            reverse("escola_admin_promover"), {"email": OUTRO, "aplicar": "1"}
        )
        assert resposta["Location"].endswith("?resultado=publicado")
    assert OUTRO in _emails_autorizados()
    assert Administrador.objects.filter(email=OUTRO, ativo=True).count() == 1
    assert not RascunhoDeConfiguracao.objects.filter(tipo="permissao", alvo=OUTRO).exists()
    assert Registro.objects.filter(acao=Registro.PROMOVER, alvo=OUTRO, quem_email=DONO).count() == 2


@respx.mock
def test_tornar_admin_reativa_quem_ja_foi_removido():
    Administrador.objects.create(email=OUTRO, ativo=False)
    resposta = _dentro().post(
        reverse("escola_admin_promover"), {"email": OUTRO, "aplicar": "1"}
    )
    assert resposta.status_code == 302
    assert OUTRO in _emails_autorizados()
    assert Administrador.objects.filter(email=OUTRO).count() == 1


@pytest.mark.parametrize("robo", [False, True])
def test_aplicar_na_ficha_preserva_a_autorizacao_do_mantenedor(robo):
    from django.test import RequestFactory
    from apps.core.views import escola_admin_promover

    request = RequestFactory().post(
        reverse("escola_admin_promover"), {"email": "nova@exemplo.com", "aplicar": "1"}
    )
    request.admin = {"email": DONO if robo else OUTRO, "robo": robo}
    assert escola_admin_promover(request).status_code == 403
    assert not Administrador.objects.filter(email="nova@exemplo.com").exists()
    assert Registro.objects.count() == 0


@pytest.mark.django_db
@respx.mock
def test_promover_duas_vezes_nao_cria_duas_linhas():
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    assert Administrador.objects.filter(email=OUTRO).count() == 0
    _dentro().post(reverse("escola_admin_publicar"), {"email": OUTRO})
    assert Administrador.objects.filter(email=OUTRO).count() == 1


@pytest.mark.django_db
@respx.mock
def test_promover_de_novo_quem_foi_removido_reativa():
    Administrador.objects.create(email=OUTRO, ativo=False)
    _dentro().post(reverse("escola_admin_promover"), {"email": OUTRO})
    assert OUTRO not in _emails_autorizados()
    _dentro().post(reverse("escola_admin_publicar"), {"email": OUTRO})
    assert OUTRO in _emails_autorizados()


@pytest.mark.django_db
@respx.mock
def test_remover_tira_o_cracha_e_deixa_rastro():
    Administrador.objects.create(email=OUTRO)
    r = _dentro().post(reverse("escola_admin_remover"), {"email": OUTRO})

    assert r["Location"].endswith("?resultado=rascunho")
    assert OUTRO in _emails_autorizados()
    r = _dentro().post(reverse("escola_admin_publicar"), {"email": OUTRO})
    assert r["Location"].endswith("?resultado=publicado")
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


@pytest.mark.django_db
@respx.mock
def test_editor_pode_rascunhar_mas_nao_publicar_ou_se_promover():
    Administrador.objects.create(email=OUTRO)
    editor = _dentro(OUTRO)
    propria = editor.post(reverse("escola_admin_promover"), {"email": OUTRO})
    assert propria["Location"].endswith("?resultado=voce-mesmo")
    assert not RascunhoDeConfiguracao.objects.filter(alvo=OUTRO).exists()
    alvo = "nova@exemplo.com"
    assert (
        editor.post(reverse("escola_admin_promover"), {"email": alvo}).status_code
        == 302
    )
    assert alvo not in _emails_autorizados()
    assert (
        editor.post(reverse("escola_admin_publicar"), {"email": alvo}).status_code
        == 403
    )
    assert alvo not in _emails_autorizados()
    assert RascunhoDeConfiguracao.objects.filter(alvo=alvo).exists()


@pytest.mark.django_db
def test_robo_rejeitado_explicitamente_mesmo_que_a_rota_nao_o_bloqueie():
    from django.test import RequestFactory
    from apps.core.views import escola_admin_publicar

    rascunho = RascunhoDeConfiguracao.objects.create(
        tipo="permissao",
        site_id="",
        alvo="nova@exemplo.com",
        conteudo={"ativo": True},
        base={"ativo": False},
    )
    request = RequestFactory().post(
        reverse("escola_admin_publicar"), {"email": rascunho.alvo}
    )
    request.admin = {"email": DONO, "robo": True}
    assert escola_admin_publicar(request).status_code == 403
    assert not Administrador.objects.filter(email=rascunho.alvo).exists()


# ------------------------------------------------------- a ficha NAO se apaga
#
# `DECISAO-a-ficha-nao-se-apaga.md`, 29/08/2026: *"Eu quero que o cadastro do
# aluno NUNCA SEJA APAGADO"*. Os testes abaixo medem uma AUSÊNCIA, e por isso
# eles existem: o que foi removido daqui — uma rota, um método, um formulário —
# volta com uma linha em cada arquivo, e nenhum teste comum notaria.


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

    assert "Tornar ADMIN" in html
    assert "Remover aluno" in html
    assert reverse("escola_aluno_remover") in html
    assert 'name="aplicar" value="1"' in html
    assert "Perfil: <b>ALUNO</b>" in html
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
@pytest.mark.parametrize("rota", ["escola_admin_promover", "escola_admin_remover", "escola_aluno_remover", "escola_aluno_restaurar"])
def test_as_rotas_de_poder_nao_atendem_GET(rota):
    assert _dentro().get(reverse(rota)).status_code == 405


@respx.mock
@pytest.mark.django_db
def test_remover_aluno_encerra_todos_seus_cursos_na_mesma_escola(monkeypatch):
    from apps.core.clients import AlunosClient
    matriculas = [
        {"id": "7", "site_id": "a", "email": OUTRO, "status": "ativa"},
        {"id": "8", "site_id": "a", "email": OUTRO.upper(), "status": "suspensa"},
        {"id": "9", "site_id": "a", "email": OUTRO, "status": "encerrada"},
        {"id": "10", "site_id": "b", "email": OUTRO, "status": "ativa"},
        {"id": "11", "site_id": "a", "email": DONO, "status": "ativa"},
    ]
    chamadas = []
    monkeypatch.setattr(AlunosClient, "alunos", lambda self: matriculas)
    monkeypatch.setattr(AlunosClient, "atualizar_aluno", lambda self, **kw: (chamadas.append(kw) or (AlunosClient.OK, "")))
    administrador = Administrador.objects.create(email=OUTRO)
    resposta = _dentro().post(reverse("escola_aluno_remover"), {"alvo": "7"})
    assert resposta.url.endswith("?resultado=aluno-removido")
    assert chamadas == [
        {"alvo": "7", "mudancas": {"status": "encerrada"}, "decidido_por": ID_DO_DONO},
        {"alvo": "8", "mudancas": {"status": "encerrada"}, "decidido_por": ID_DO_DONO},
    ]
    administrador.refresh_from_db()
    assert administrador.ativo
    assert AlunoRemovidoDaLista.objects.get(site_id="a", email=OUTRO).removido
    assert AlunoRemovidoDaLista.objects.count() == 1
    registro = Registro.objects.get()
    assert registro.acao == Registro.EDITAR
    assert registro.alvo == "7"
    assert registro.quem_email == DONO


@respx.mock
@pytest.mark.django_db
@pytest.mark.parametrize("matriculas,resultado", [(None, "nao-deu"), ([], "nao-valeu"), ([{"id": "7", "site_id": "a", "email": OUTRO, "status": "encerrada"}], "aluno-removido")])
def test_remover_aluno_sem_alterar_outros_cadastros(monkeypatch, matriculas, resultado):
    from apps.core.clients import AlunosClient
    monkeypatch.setattr(AlunosClient, "alunos", lambda self: matriculas)
    def inesperada(self, **kw):
        pytest.fail("Nenhuma matrícula deveria ser alterada")
    monkeypatch.setattr(AlunosClient, "atualizar_aluno", inesperada)
    assert _dentro().post(reverse("escola_aluno_remover"), {"alvo": "7"}).url.endswith(f"?resultado={resultado}")


@respx.mock
@pytest.mark.django_db
def test_remover_aluno_informa_quando_nao_conseguiu_encerrar(monkeypatch):
    from apps.core.clients import AlunosClient
    monkeypatch.setattr(AlunosClient, "alunos", lambda self: [
        {"id": "7", "site_id": "a", "email": OUTRO, "status": "ativa"},
        {"id": "8", "site_id": "a", "email": OUTRO, "status": "ativa"},
    ])
    chamadas = []
    monkeypatch.setattr(AlunosClient, "atualizar_aluno", lambda self, **kw: (chamadas.append(kw) or (AlunosClient.NAO_RESPONDEU, "indisponível")))
    resposta = _dentro().post(reverse("escola_aluno_remover"), {"alvo": "7"})
    assert resposta.url.endswith("?resultado=nao-deu")
    assert len(chamadas) == 1
    assert "indisponível" in Registro.objects.get().detalhe
    assert not AlunoRemovidoDaLista.objects.exists()


@respx.mock
@pytest.mark.django_db
def test_remover_aluno_exige_admin(monkeypatch):
    from apps.core.clients import AlunosClient
    def inesperada(self):
        pytest.fail("Não deveria consultar matrículas sem autorização")
    monkeypatch.setattr(AlunosClient, "alunos", inesperada)
    assert _dentro("aluno@exemplo.com").post(reverse("escola_aluno_remover"), {"alvo": "7"}).status_code == 404


def _lista_para_remocao(monkeypatch):
    from apps.core.clients import AlunosClient, CatalogoClient
    rows = [
        {"id": "7", "site_id": "a", "email": OUTRO, "status": "encerrada", "nome_completo": "Teste removido", "matriculas": []},
        {"id": "8", "site_id": "a", "email": OUTRO, "status": "encerrada", "nome_completo": "Teste removido", "matriculas": []},
        {"id": "9", "site_id": "b", "email": OUTRO, "status": "encerrada", "nome_completo": "Outra escola", "matriculas": []},
        {"id": "10", "site_id": "a", "email": "historico@exemplo.com", "status": "encerrada", "nome_completo": "Ex-aluno mantido", "matriculas": []},
    ]
    monkeypatch.setattr(AlunosClient, "alunos", lambda self: rows)
    monkeypatch.setattr(AlunosClient, "fila", lambda self, status: [])
    monkeypatch.setattr(CatalogoClient, "listar_produtos", lambda self: [])
    return rows


@respx.mock
def test_removido_some_da_lista_normal_e_da_busca_mas_o_historico_continua(monkeypatch):
    rows = _lista_para_remocao(monkeypatch)
    AlunoRemovidoDaLista.objects.create(site_id="a", email=OUTRO)
    cliente = _dentro()
    resposta = cliente.get(reverse("escola_alunos"))
    assert {p["nome_completo"] for p in resposta.context["alunos"]} == {"Outra escola", "Ex-aluno mantido"}
    assert resposta.context["total_de_alunos"] == 2
    assert resposta.context["quantidade_removidos"] == 1
    assert cliente.get(reverse("escola_alunos"), {"q": "Teste removido"}).context["alunos"] == []
    assert len(rows) == 4
    removidos = cliente.get(reverse("escola_alunos"), {"removidos": "1"})
    assert len(removidos.context["alunos"]) == 1
    assert removidos.context["alunos"][0]["nome_completo"] == "Teste removido"
    assert "Restaurar à lista" in removidos.content.decode()
    assert "Tornar ADMIN" not in removidos.content.decode().split('Quem é administrador desta área:')[0]


@respx.mock
def test_restaurar_ficha_reaparece_sem_liberar_acesso(monkeypatch):
    from apps.core.clients import AlunosClient
    rows = _lista_para_remocao(monkeypatch)
    removido = AlunoRemovidoDaLista.objects.create(site_id="a", email=OUTRO)
    def inesperada(self, **kw):
        pytest.fail("Restaurar à lista não altera o acesso")
    monkeypatch.setattr(AlunosClient, "atualizar_aluno", inesperada)
    cliente = _dentro()
    assert cliente.post(reverse("escola_aluno_restaurar"), {"alvo": "7"}).url.endswith("?resultado=aluno-restaurado")
    removido.refresh_from_db()
    assert not removido.removido
    assert len(cliente.get(reverse("escola_alunos")).context["alunos"]) == 3
    assert all(r["status"] == "encerrada" for r in rows)
    assert Registro.objects.get().detalhe == "restaurar aluno à lista; acesso mantido"
