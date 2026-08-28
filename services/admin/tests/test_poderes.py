"""Administrador por botão, e apagar de vez — `DECISAO-administradores-e-apagar`.

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

E `test_apagar_exige_a_palavra_digitada`: é a única ação da tela sem desfazer,
e esta área não tem JavaScript (o CSP bloqueia script inline), então a
confirmação tem de ser algo que funcione sem ele.
"""

import httpx
import pytest
import respx
from django.db import DatabaseError
from django.test import Client
from django.urls import reverse

from apps.auditoria.models import Registro
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


# ------------------------------------------------------------- apagar de vez


def _apagar_responde(status=204):
    return respx.delete(f"{ALUNOS}/matriculas/{ALVO}").mock(
        return_value=httpx.Response(status)
    )


@pytest.mark.django_db
@respx.mock
def test_apagar_com_a_palavra_certa_apaga_e_registra():
    rota = _apagar_responde()
    r = _dentro().post(
        reverse("escola_aluno_apagar"), {"alvo": ALVO, "confirmacao": "APAGAR"}
    )

    assert rota.called
    assert r["Location"].endswith("?resultado=apagado")
    linha = Registro.objects.get()
    assert linha.acao == Registro.APAGAR
    assert linha.alvo == ALVO


@pytest.mark.django_db
@respx.mock
@pytest.mark.parametrize("palavra", ["", "apagar tudo", "sim", "APAGA"])
def test_apagar_exige_a_palavra_digitada(palavra):
    """A única ação da tela sem desfazer.

    E a confirmação NÃO pode ser um `confirm()` do navegador: esta área serve
    com `script-src 'self'` e sem arquivo de JS — um `onclick` inline
    simplesmente não roda, e o botão apagaria no primeiro clique.
    """
    rota = _apagar_responde()
    r = _dentro().post(
        reverse("escola_aluno_apagar"), {"alvo": ALVO, "confirmacao": palavra}
    )

    assert not rota.called, f"apagou com a confirmação {palavra!r}"
    assert Registro.objects.count() == 0
    assert r["Location"].endswith("?resultado=confirme")


@pytest.mark.django_db
@respx.mock
def test_a_palavra_aceita_minuscula_e_espaco():
    """Exigir a palavra é proteção contra clique errado, não pegadinha."""
    rota = _apagar_responde()
    _dentro().post(
        reverse("escola_aluno_apagar"), {"alvo": ALVO, "confirmacao": " apagar "}
    )
    assert rota.called


@pytest.mark.django_db
@respx.mock
def test_a_auditoria_do_apagar_nao_guarda_nada_da_pessoa():
    """O que sobra de alguém que pediu para sumir do sistema.

    Uma linha dizendo que a ficha X foi apagada, por quem e quando — e mais
    nada. É o máximo que o direito da pessoa permite e o mínimo para a
    auditoria continuar respondendo "o que foi feito nesta área?".
    """
    _apagar_responde()
    _dentro().post(
        reverse("escola_aluno_apagar"), {"alvo": ALVO, "confirmacao": "APAGAR"}
    )

    linha = Registro.objects.get()
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
    assert linha.detalhe == ""


@pytest.mark.django_db
@respx.mock
def test_apagar_que_nao_chegou_e_registrado_como_nao_respondeu():
    """Irreversível do outro lado ⇒ "talvez tenha acontecido" precisa de nome.

    Dizer "não deu certo" faria o mantenedor tentar de novo achando que a
    primeira não valeu.
    """
    respx.delete(f"{ALUNOS}/matriculas/{ALVO}").mock(
        side_effect=httpx.ConnectError("recusou")
    )
    r = _dentro().post(
        reverse("escola_aluno_apagar"), {"alvo": ALVO, "confirmacao": "APAGAR"}
    )

    assert Registro.objects.get().desfecho == Registro.NAO_RESPONDEU
    assert r["Location"].endswith("?resultado=nao-deu")


@respx.mock
@pytest.mark.parametrize(
    "rota", ["escola_aluno_apagar", "escola_admin_promover", "escola_admin_remover"]
)
def test_as_tres_rotas_novas_nao_atendem_GET(rota):
    assert _dentro().get(reverse(rota)).status_code == 405
