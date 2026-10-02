"""Teste-guarda do acesso da equipe por aparelho (01/10/2026).

O link conecta o aparelho à pessoa que já existe na equipe, pelo
identificador dela, sem e-mail nem senha. O que este arquivo existe para
impedir:

1. **O link virando senha escrita numa conversa.** Vale uma vez, tem prazo,
   e o banco guarda só hash — do código e da credencial do aparelho.
2. **O aparelho virando administração geral.** Quem entra por aparelho tem o
   crachá de equipe: só `/equipe/`, sem a ficha nem a lista de pessoas.
3. **A pessoa perdendo o trabalho ao se cadastrar.** Nome, e-mail e senha em
   "Meu perfil" complementam a entrada; tarefas e comentários continuam dela.
4. **Desconectar um aparelho derrubando os outros**, e retirar alguém da
   equipe apagando o histórico.
5. **E-mail digitado pela própria pessoa abrindo a conta Google de outra.**
6. **A porta se abrindo além das duas entradas.**

A rede é dublada com `respx`, como nos irmãos desta pasta.
"""

from __future__ import annotations

import base64
import re
from datetime import timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.equipe_acesso import COOKIE_DO_APARELHO
from apps.core.models import (
    AparelhoDaEquipe,
    Comentario,
    LinkDeAcesso,
    MembroDaEquipe,
    Tarefa,
)

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
EMAIL_DO_RYAN = "ryan-conta-de-teste@exemplo.com"
SENHA = "TESTE-senha-longa"
PAINEL = "painel_da_equipe"
LINK = re.compile(
    r"/equipe/magic-link\?client=(desktop_app|mobile_app)#([0-9a-f]{32}):([A-Za-z0-9_-]+)"
)


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _sessao(email: str, nome: str = "Fulano"):
    # O dublê responde pela ÚLTIMA sessão registrada, e responde a qualquer
    # cookie: cada troca de quem está do outro lado registra de novo.
    return respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": nome,
                "papel": None,
                "email": email,
            },
        )
    )


def _sem_sessao():
    return respx.get(SESSAO).mock(
        return_value=httpx.Response(200, json={"autenticado": False})
    )


def _dono() -> Client:
    _sessao(DONO, "Dono")
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _ryan() -> MembroDaEquipe:
    return MembroDaEquipe.objects.get(nome="Ryan")


def _texto(resposta) -> str:
    return resposta.content.decode()


def _gerar_link(pessoa: MembroDaEquipe) -> re.Match:
    resposta = _dono().post(reverse("ficha_gerar_link", args=[pessoa.id]))
    assert resposta.status_code == 200
    achado = LINK.search(_texto(resposta))
    assert achado, "a tela não mostrou o link no formato combinado"
    return achado


def _abrir(codigo: str, cliente_do_link: str = "desktop_app"):
    """Um navegador novo abrindo o link: o script entrega o código por POST."""
    navegador = Client()
    resposta = navegador.post(
        reverse("magic_link") + f"?client={cliente_do_link}", {"codigo": codigo}
    )
    return navegador, resposta


def _conectado(pessoa: MembroDaEquipe) -> Client:
    navegador, resposta = _abrir(_gerar_link(pessoa).group(2))
    assert resposta.status_code == 302, _texto(resposta)
    return navegador


# ---------------------------------------------------------------- a porta


def test_as_entradas_sem_cracha_sao_exatamente_estas():
    from apps.core.porta import ENTRADAS_DA_EQUIPE

    assert ENTRADAS_DA_EQUIPE == {"/equipe/magic-link", "/equipe/entrar"}


@respx.mock
def test_sem_acesso_o_painel_manda_para_a_entrada_e_o_resto_para_o_google():
    painel = Client().get(reverse("objetivos_da_equipe"))
    assert painel["Location"] == (
        reverse("entrar_na_equipe") + "?next=" + reverse("objetivos_da_equipe")
    )
    assert Client().get(reverse("escola"))["Location"].startswith("/entrar/google")


@respx.mock
def test_a_pagina_do_link_abre_sem_cracha_e_so_libera_o_proprio_script():
    resposta = Client().get(reverse("magic_link") + "?client=desktop_app")
    assert resposta.status_code == 200
    html = _texto(resposta)
    assert "<script>" in html and "Conectando este aparelho" in html
    csp = resposta["Content-Security-Policy"]
    assert "script-src 'self' 'sha256-" in csp
    assert "unsafe-inline" not in csp
    assert "style-src 'self' 'sha256-" in csp, "o estilo da casa continua valendo"


# ---------------------------------------------------------------- o percurso


@respx.mock
def test_o_link_conecta_o_aparelho_a_pessoa_e_cai_nas_tarefas_dela():
    ryan = _ryan()
    Tarefa.objects.create(titulo="TESTE Do Ryan", responsavel=ryan)
    Tarefa.objects.create(
        titulo="TESTE Da Maria", responsavel=MembroDaEquipe.objects.get(nome="Maria")
    )
    achado = _gerar_link(ryan)
    cliente_do_link, codigo, dados = achado.groups()
    assert cliente_do_link == "desktop_app"
    preenchido = dados + "=" * (-len(dados) % 4)
    assert (
        base64.urlsafe_b64decode(preenchido).decode() == "Ryan"
    ), "sem e-mail, os dados do link levam o nome da pessoa"

    navegador, resposta = _abrir(codigo)
    assert resposta["Location"] == (
        reverse(PAINEL) + "?visao=minhas&resultado=aparelho_conectado"
    )
    cookie = resposta.cookies[COOKIE_DO_APARELHO]
    assert cookie["httponly"] and cookie["samesite"] == "Lax"
    assert cookie["path"] == reverse(PAINEL)
    assert int(cookie["max-age"]) >= 399 * 24 * 3600

    # Sem cookie de sessão do site, a porta nem pergunta à identidade.
    identidade = _sem_sessao()
    antes = identidade.call_count  # a rota guarda a chamada do dono, acima
    html = _texto(navegador.get(resposta["Location"]))
    assert identidade.call_count == antes
    assert "TESTE Do Ryan" in html and "TESTE Da Maria" not in html
    assert "Pronto: este aparelho ficou conectado a você" in html
    assert ">Conectar meu celular</button>" in html

    aparelho = AparelhoDaEquipe.objects.get()
    assert aparelho.membro == ryan and aparelho.tipo == "computador"
    assert aparelho.chave_hash != cookie.value, "o banco guarda só o hash"
    assert not LinkDeAcesso.objects.filter(codigo_hash=codigo).exists()


@respx.mock
def test_o_link_vale_uma_vez_e_copiar_depois_nao_abre_nada():
    codigo = _gerar_link(_ryan()).group(2)
    primeiro, _ = _abrir(codigo)
    segundo, resposta = _abrir(codigo)
    assert resposta.status_code == 400
    assert "Este link não vale mais" in _texto(resposta)
    assert COOKIE_DO_APARELHO not in resposta.cookies
    assert AparelhoDaEquipe.objects.count() == 1


@respx.mock
def test_link_vencido_cancelado_ou_de_quem_saiu_nao_conecta():
    ryan = _ryan()
    codigo = _gerar_link(ryan).group(2)
    LinkDeAcesso.objects.update(expira_em=timezone.now() - timedelta(minutes=1))
    assert _abrir(codigo)[1].status_code == 400

    velho = _gerar_link(ryan).group(2)
    novo = _gerar_link(ryan).group(2)
    assert _abrir(velho)[1].status_code == 400, "gerar outro cancela o anterior"

    ryan.ativo = False
    ryan.save()
    assert _abrir(novo)[1].status_code == 400
    assert _abrir("0" * 32)[1].status_code == 400
    assert not AparelhoDaEquipe.objects.exists()


@respx.mock
def test_o_aparelho_so_abre_o_painel_e_nao_a_gestao_de_pessoas():
    ryan = _ryan()
    navegador = _conectado(ryan)
    assert navegador.get(reverse("pessoas_da_equipe")).status_code == 404
    assert navegador.get(reverse("ficha_da_pessoa", args=[ryan.id])).status_code == 404
    gerou = navegador.post(reverse("ficha_gerar_link", args=[ryan.id]))
    assert gerou.status_code == 404
    # Fora de `/equipe/` o aparelho não vale nada: sem sessão, vai ao login.
    _sem_sessao()
    assert navegador.get(reverse("escola"))["Location"].startswith("/entrar/google")


@respx.mock
def test_o_aparelho_entra_mesmo_com_a_identidade_fora_do_ar():
    navegador = _conectado(_ryan())
    respx.get(SESSAO).mock(side_effect=httpx.ConnectError("recusou"))
    navegador.cookies["meshcraft_sessao"] = "de-aluno"
    assert navegador.get(reverse(PAINEL)).status_code == 200


@respx.mock
def test_a_credencial_se_renova_com_o_uso():
    navegador = _conectado(_ryan())
    AparelhoDaEquipe.objects.update(ultimo_uso_em=timezone.now() - timedelta(days=3))
    resposta = navegador.get(reverse(PAINEL))
    assert COOKIE_DO_APARELHO in resposta.cookies, "um dia de uso renova o cookie"
    assert AparelhoDaEquipe.objects.get().ultimo_uso_em > timezone.now() - timedelta(
        minutes=1
    )
    assert COOKIE_DO_APARELHO not in navegador.get(reverse(PAINEL)).cookies


# ---------------------------------------------------------------- meu celular


@respx.mock
def test_conectar_meu_celular_da_outra_credencial_a_mesma_pessoa():
    ryan = _ryan()
    computador = _conectado(ryan)
    resposta = computador.post(reverse("conectar_meu_celular"))
    html = _texto(resposta)
    achado = LINK.search(html)
    assert achado and achado.group(1) == "mobile_app"
    assert "<svg" in html, "o QR code vem desenhado na página"
    link = LinkDeAcesso.objects.get(origem="proprio")
    assert link.expira_em < timezone.now() + timedelta(minutes=31)

    celular, entrou = _abrir(achado.group(2), "mobile_app")
    assert entrou.status_code == 302
    tipos = sorted(AparelhoDaEquipe.objects.values_list("tipo", flat=True))
    assert tipos == ["celular", "computador"]
    assert (
        celular.cookies[COOKIE_DO_APARELHO].value
        != computador.cookies[COOKIE_DO_APARELHO].value
    ), "cada navegador tem a própria credencial"
    assert set(AparelhoDaEquipe.objects.values_list("membro", flat=True)) == {ryan.id}


@respx.mock
def test_desconectar_o_aparelho_perdido_nao_derruba_os_outros():
    ryan = _ryan()
    computador = _conectado(ryan)
    celular = _conectado(ryan)
    perdido = AparelhoDaEquipe.objects.order_by("-id").first()
    resposta = _dono().post(
        reverse("ficha_desconectar", args=[ryan.id]), {"aparelho": perdido.id}
    )
    assert resposta["Location"].endswith("resultado=aparelho_desconectado")
    _sem_sessao()
    assert celular.get(reverse(PAINEL))["Location"].startswith(
        reverse("entrar_na_equipe")
    )
    assert computador.get(reverse(PAINEL)).status_code == 200


@respx.mock
def test_aparelho_desconectado_vai_a_entrada_sem_perguntar_a_identidade():
    """Achado na conferência no navegador: com a identidade fora, o aparelho
    desconectado caía na tela de "indisponível" em vez da entrada da equipe."""
    navegador = _conectado(_ryan())
    AparelhoDaEquipe.objects.update(desconectado_em=timezone.now())
    rota = respx.get(SESSAO).mock(side_effect=httpx.ConnectError("recusou"))
    antes = rota.call_count
    resposta = navegador.get(reverse(PAINEL))
    assert resposta.status_code == 302
    assert resposta["Location"].startswith(reverse("entrar_na_equipe"))
    assert rota.call_count == antes


@respx.mock
def test_sair_deste_aparelho():
    navegador = _conectado(_ryan())
    resposta = navegador.post(reverse("sair_da_equipe"))
    assert resposta["Location"] == reverse("entrar_na_equipe") + "?resultado=saiu"
    assert resposta.cookies[COOKIE_DO_APARELHO].value == ""
    assert AparelhoDaEquipe.objects.get().desconectado_em is not None


@respx.mock
def test_retirar_da_equipe_encerra_os_aparelhos_e_guarda_o_historico():
    ryan = _ryan()
    navegador = _conectado(ryan)
    tarefa = Tarefa.objects.create(titulo="TESTE Histórico", responsavel=ryan)
    navegador.post(reverse("tarefa_comentar", args=[tarefa.id]), {"texto": "TESTE ok"})
    pendente = _gerar_link(ryan).group(2)

    resposta = _dono().post(reverse("ficha_ativo", args=[ryan.id]), {"ativo": "0"})
    assert resposta["Location"].endswith("resultado=pessoa_retirada")
    ryan.refresh_from_db()
    assert not ryan.ativo
    _sem_sessao()
    assert navegador.get(reverse(PAINEL)).status_code == 302
    assert _abrir(pendente)[1].status_code == 400
    tarefa.refresh_from_db()
    assert tarefa.responsavel == ryan
    assert Comentario.objects.get().autor_membro == ryan

    _dono().post(reverse("ficha_ativo", args=[ryan.id]), {"ativo": "1"})
    ryan.refresh_from_db()
    assert ryan.ativo


# ---------------------------------------------------------------- meu perfil


@respx.mock
def test_o_perfil_completa_a_entrada_sem_mudar_quem_responde():
    ryan = _ryan()
    navegador = _conectado(ryan)
    tarefa = Tarefa.objects.create(titulo="TESTE Campanha", responsavel=ryan)
    navegador.post(reverse("tarefa_comentar", args=[tarefa.id]), {"texto": "TESTE vou"})
    comentario = Comentario.objects.get()
    assert comentario.autor_membro == ryan and comentario.autor == "Ryan"

    resposta = navegador.post(
        reverse("meu_perfil"),
        {
            "nome": "Ryan Teste",
            "email": EMAIL_DO_RYAN,
            "senha": SENHA,
            "confirmacao": SENHA,
        },
    )
    assert resposta["Location"].endswith("resultado=perfil_salvo")
    ryan.refresh_from_db()
    assert ryan.nome == "Ryan Teste" and ryan.email == EMAIL_DO_RYAN
    assert ryan.email_a_conferir
    assert ryan.senha and ryan.senha != SENHA
    tarefa.refresh_from_db()
    assert tarefa.responsavel_id == ryan.id
    ficha = _texto(navegador.get(reverse("tarefa_ver", args=[tarefa.id])))
    assert "Ryan Teste, " in ficha, "o comentário acompanha a pessoa, não o texto"
    assert navegador.get(reverse(PAINEL)).status_code == 200


@respx.mock
def test_o_perfil_recusa_senha_curta_diferente_ou_sem_email():
    navegador = _conectado(_ryan())
    curta = navegador.post(
        reverse("meu_perfil"),
        {"nome": "Ryan", "email": EMAIL_DO_RYAN, "senha": "123", "confirmacao": "123"},
    )
    assert curta.status_code == 400 and "pelo menos 8" in _texto(curta)
    diferente = navegador.post(
        reverse("meu_perfil"),
        {"nome": "Ryan", "email": EMAIL_DO_RYAN, "senha": SENHA, "confirmacao": "x"},
    )
    assert "não são iguais" in _texto(diferente)
    sem_email = navegador.post(
        reverse("meu_perfil"), {"nome": "Ryan", "senha": SENHA, "confirmacao": SENHA}
    )
    assert "informe também o e-mail" in _texto(sem_email)
    assert not _ryan().senha


@respx.mock
def test_email_escrito_pela_pessoa_so_abre_o_google_depois_de_conferido():
    ryan = _ryan()
    navegador = _conectado(ryan)
    navegador.post(reverse("meu_perfil"), {"nome": "Ryan", "email": EMAIL_DO_RYAN})

    _sessao(EMAIL_DO_RYAN, "Ryan")
    pelo_google = Client()
    pelo_google.defaults["HTTP_COOKIE"] = COOKIE
    assert pelo_google.get(reverse(PAINEL)).status_code == 404

    ficha = _texto(_dono().get(reverse("ficha_da_pessoa", args=[ryan.id])))
    assert "ainda não conferido" in ficha
    _dono().post(
        reverse("pessoas_da_equipe_associar"),
        {"pessoa": ryan.id, "email": EMAIL_DO_RYAN},
    )
    _sessao(EMAIL_DO_RYAN, "Ryan")
    assert pelo_google.get(reverse(PAINEL)).status_code == 200


# ---------------------------------------------------------------- e-mail e senha


@respx.mock
def test_entrar_com_email_e_senha_conecta_outro_aparelho():
    navegador = _conectado(_ryan())
    navegador.post(
        reverse("meu_perfil"),
        {"nome": "Ryan", "email": EMAIL_DO_RYAN, "senha": SENHA, "confirmacao": SENHA},
    )
    outro = Client()
    assert "Entrar com Google" in _texto(outro.get(reverse("entrar_na_equipe")))
    errada = outro.post(
        reverse("entrar_na_equipe"), {"email": EMAIL_DO_RYAN, "senha": "errada!!"}
    )
    assert errada.status_code == 400 and "não conferem" in _texto(errada)
    certa = outro.post(
        reverse("entrar_na_equipe"),
        {"email": EMAIL_DO_RYAN, "senha": SENHA, "next": reverse("semana_da_equipe")},
    )
    assert certa["Location"].startswith(reverse("semana_da_equipe"))
    assert outro.get(reverse(PAINEL)).status_code == 200
    assert AparelhoDaEquipe.objects.filter(como_entrou="senha").count() == 1


@respx.mock
def test_cinco_senhas_erradas_travam_o_email_por_um_tempo():
    ryan = _ryan()
    ryan.email = EMAIL_DO_RYAN
    ryan.save()
    navegador = _conectado(ryan)
    navegador.post(
        reverse("meu_perfil"),
        {"nome": "Ryan", "email": EMAIL_DO_RYAN, "senha": SENHA, "confirmacao": SENHA},
    )
    cliente = Client()
    for _ in range(5):
        cliente.post(
            reverse("entrar_na_equipe"), {"email": EMAIL_DO_RYAN, "senha": "x" * 9}
        )
    travada = cliente.post(
        reverse("entrar_na_equipe"), {"email": EMAIL_DO_RYAN, "senha": SENHA}
    )
    assert travada.status_code == 429
    assert "Espere 15 minutos" in _texto(travada)


@respx.mock
def test_entrar_nao_aceita_next_para_fora_do_painel():
    resposta = Client().get(
        reverse("entrar_na_equipe") + "?next=https://outro-site.exemplo/"
    )
    assert 'value="' + reverse(PAINEL) + '"' in _texto(resposta)


# ---------------------------------------------------------------- a ficha


@respx.mock
def test_a_ficha_mostra_aparelhos_e_a_lista_leva_a_ela():
    ryan = _ryan()
    _conectado(ryan)
    lista = _texto(_dono().get(reverse("pessoas_da_equipe")))
    assert 'href="' + reverse("ficha_da_pessoa", args=[ryan.id]) + '"' in lista
    assert "1 aparelho conectado" in lista
    ficha = _texto(_dono().get(reverse("ficha_da_pessoa", args=[ryan.id])))
    assert "Computador, entrou pelo link" in ficha
    assert ">Desconectar</button>" in ficha
    assert ">Gerar link de acesso</button>" in ficha
