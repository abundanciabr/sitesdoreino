"""Teste-guarda do painel da equipe (`/admin/equipe/`), 01/10/2026.

O que este arquivo existe para impedir:

1. **O painel abrindo para quem não é da casa.** Quem não é administrador nem
   tem a conta associada a alguém da equipe recebe 404, como em toda a área.
2. **O crachá de equipe virando administração geral.** Quem entra pela conta
   associada abre SÓ `/equipe/`; o resto da área continua não existindo, e a
   tela de pessoas (que decide quem é da equipe) também.
3. **O percurso quebrando no meio.** Criar, atribuir, editar, bloquear com
   impedimento, concluir, reabrir e reencontrar depois de recarregar: cada
   degrau é medido pela tela, não pelo modelo.
4. **Bloquear sem dizer por quê.** A situação Bloqueada exige impedimento, e a
   recusa chega como frase, não como 500.

A rede é dublada com `respx`, como nos irmãos desta pasta.
"""

from __future__ import annotations

from datetime import timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core.models import MembroDaEquipe, Tarefa

IDENTIDADE = "http://identidade:8000/interno"
SESSAO = f"{IDENTIDADE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"
LIVIA = "livia-conta-de-teste@exemplo.com"
DE_FORA = "estranho@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def _cliente(email: str = DONO, nome: str = "Fulano") -> Client:
    respx.get(SESSAO).mock(
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
    cliente = Client()
    cliente.defaults["HTTP_COOKIE"] = COOKIE
    return cliente


def _texto(resposta) -> str:
    return resposta.content.decode()


def _livia() -> MembroDaEquipe:
    pessoa = MembroDaEquipe.objects.get(nome="Lívia")
    pessoa.email = LIVIA
    pessoa.save()
    return pessoa


PAINEL = "painel_da_equipe"


# ---------------------------------------------------------------- a semente


def test_as_quatro_pessoas_existem_sem_conta():
    nomes = list(MembroDaEquipe.objects.values_list("nome", flat=True))
    assert nomes == ["Arameu", "Ryan", "Lívia", "Maria"]
    assert not MembroDaEquipe.objects.exclude(
        email=""
    ).exists(), "a migração não pode inventar a conta de ninguém"


# ---------------------------------------------------------------- a porta


@respx.mock
def test_sem_cookie_vai_para_o_login():
    resposta = Client().get(reverse(PAINEL))
    assert resposta.status_code == 302
    assert resposta["Location"].startswith("/entrar/google?next=")


@respx.mock
def test_quem_nao_e_da_casa_recebe_404():
    resposta = _cliente(DE_FORA).get(reverse(PAINEL))
    assert resposta.status_code == 404
    assert "Equipe" not in _texto(resposta)


@respx.mock
def test_quem_e_da_equipe_entra_so_no_painel():
    _livia()
    cliente = _cliente(LIVIA, nome="Lívia")
    assert cliente.get(reverse(PAINEL)).status_code == 200
    assert cliente.get(reverse("tarefa_nova")).status_code == 200
    assert cliente.get(reverse("escola")).status_code == 404
    assert cliente.get(reverse("visao_geral")).status_code == 404
    assert cliente.get(reverse("pendencias")).status_code == 404


@respx.mock
def test_quem_e_da_equipe_nao_decide_quem_e_da_equipe():
    _livia()
    cliente = _cliente(LIVIA, nome="Lívia")
    assert cliente.get(reverse("pessoas_da_equipe")).status_code == 404
    resposta = cliente.post(
        reverse("pessoas_da_equipe_associar"),
        {"pessoa": MembroDaEquipe.objects.get(nome="Ryan").id, "email": DE_FORA},
    )
    assert resposta.status_code == 404
    assert MembroDaEquipe.objects.get(nome="Ryan").email == ""


@respx.mock
def test_o_menu_de_quem_e_so_da_equipe_tem_so_o_painel():
    _livia()
    html = _texto(_cliente(LIVIA, nome="Lívia").get(reverse(PAINEL)))
    assert ">Equipe</a>" in html
    assert ">Ver o site</a>" in html
    assert ">Escola</a>" not in html
    assert ">Pendências</a>" not in html
    assert "Pessoas e contas" not in html


@respx.mock
def test_conta_desativada_nao_entra():
    pessoa = _livia()
    pessoa.ativo = False
    pessoa.save()
    assert _cliente(LIVIA).get(reverse(PAINEL)).status_code == 404


@respx.mock
def test_o_administrador_ve_o_painel_no_menu_e_na_visao_geral():
    cliente = _cliente()
    assert ">Equipe</a>" in _texto(cliente.get(reverse("escola")))
    html = _texto(cliente.get(reverse("visao_geral")))
    assert 'href="' + reverse(PAINEL) + '"' in html
    assert "Abrir o painel da equipe" in html


# ---------------------------------------------------------------- o percurso


@respx.mock
def test_primeiro_uso_diz_que_nao_ha_tarefa_e_oferece_criar():
    html = _texto(_cliente().get(reverse(PAINEL)))
    assert "Ainda não há nenhuma tarefa" in html
    assert 'href="' + reverse("tarefa_nova") + '"' in html
    assert (
        "ainda não está associada a ninguém da equipe" not in html
    ), "o administrador sem conta associada cai na visão Equipe, sem aviso"


@respx.mock
def test_criar_atribuir_e_reencontrar_depois_de_recarregar():
    cliente = _cliente(nome="Dono")
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    amanha = (timezone.localdate() + timedelta(days=1)).isoformat()
    resposta = cliente.post(
        reverse("tarefa_nova"),
        {
            "titulo": "TESTE Subir a campanha de outubro",
            "descricao": "Criativos já aprovados.",
            "responsavel": ryan.id,
            "prazo": amanha,
            "situacao": "a_fazer",
        },
    )
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse(PAINEL) + "?resultado=criada"

    tarefa = Tarefa.objects.get()
    assert tarefa.responsavel == ryan
    assert tarefa.criada_por == f"Dono ({DONO})"
    assert tarefa.concluida_em is None

    # Recarregar: a tarefa está lá, com quem criou e o responsável.
    html = _texto(_cliente(nome="Dono").get(reverse(PAINEL)))
    assert "Tarefa criada." in _texto(cliente.get(resposta["Location"]))
    assert "TESTE Subir a campanha de outubro" in html
    assert "Ryan" in html
    assert f"Criada por Dono ({DONO})" in html


@respx.mock
def test_sem_titulo_nao_salva_e_explica():
    cliente = _cliente()
    resposta = cliente.post(reverse("tarefa_nova"), {"titulo": "", "descricao": "x"})
    assert resposta.status_code == 400
    assert "Não deu para salvar" in _texto(resposta)
    assert "precisa de um título" in _texto(resposta)
    assert not Tarefa.objects.exists()


@respx.mock
def test_prazo_invalido_nao_salva_e_mantem_o_que_foi_escrito():
    cliente = _cliente()
    resposta = cliente.post(
        reverse("tarefa_nova"), {"titulo": "TESTE Prazo torto", "prazo": "31/02/2026"}
    )
    assert resposta.status_code == 400
    assert "data válida" in _texto(resposta)
    assert 'value="TESTE Prazo torto"' in _texto(resposta)


@respx.mock
def test_editar_muda_responsavel_e_registra_quem_alterou():
    _livia()
    maria = MembroDaEquipe.objects.get(nome="Maria")
    tarefa = Tarefa.objects.create(titulo="TESTE Ligar para os leads", criada_por="x")
    resposta = _cliente(LIVIA, nome="Lívia").post(
        reverse("tarefa_editar", args=[tarefa.id]),
        {
            "titulo": "TESTE Ligar para os leads quentes",
            "responsavel": maria.id,
            "situacao": "em_andamento",
        },
    )
    assert resposta.status_code == 302
    cliente = _cliente(nome="Dono")
    tarefa.refresh_from_db()
    assert tarefa.titulo == "TESTE Ligar para os leads quentes"
    assert tarefa.responsavel == maria
    assert tarefa.situacao == "em_andamento"
    assert tarefa.alterada_por == f"Lívia ({LIVIA})"
    html = _texto(cliente.get(reverse("tarefa_editar", args=[tarefa.id])))
    assert "Última alteração: Lívia" in html


@respx.mock
def test_bloquear_exige_impedimento_e_o_mostra_no_cartao():
    cliente = _cliente()
    tarefa = Tarefa.objects.create(titulo="TESTE Gravar a aula 3")
    destino = reverse(PAINEL) + "?visao=equipe"

    sem = cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]),
        {"situacao": "bloqueada", "impedimento": "", "next": destino},
    )
    assert sem["Location"] == destino + "&resultado=sem_impedimento"
    assert "escreva o impedimento" in _texto(cliente.get(sem["Location"]))
    tarefa.refresh_from_db()
    assert tarefa.situacao == "a_fazer"

    com = cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]),
        {"situacao": "bloqueada", "impedimento": "Falta o microfone.", "next": destino},
    )
    tarefa.refresh_from_db()
    assert tarefa.situacao == "bloqueada"
    assert tarefa.impedimento == "Falta o microfone."
    html = _texto(cliente.get(com["Location"]))
    assert "Falta o microfone." in html
    assert "Situação atualizada." in html


@respx.mock
def test_concluir_marca_a_hora_e_reabrir_limpa():
    cliente = _cliente()
    tarefa = Tarefa.objects.create(titulo="TESTE Fechar o mês")

    cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]), {"situacao": "concluida"}
    )
    tarefa.refresh_from_db()
    assert tarefa.situacao == "concluida"
    assert tarefa.concluida_em is not None
    html = _texto(cliente.get(reverse(PAINEL)))
    assert "Concluída em" in html
    assert ">Reabrir</button>" in html

    cliente.post(reverse("tarefa_situacao", args=[tarefa.id]), {"situacao": "a_fazer"})
    tarefa.refresh_from_db()
    assert tarefa.situacao == "a_fazer"
    assert tarefa.concluida_em is None
    html = _texto(cliente.get(reverse(PAINEL) + "?resultado=reaberta"))
    assert "Tarefa reaberta" in html
    assert ">Concluir</button>" in html


@respx.mock
def test_situacao_desconhecida_nao_muda_nada():
    cliente = _cliente()
    tarefa = Tarefa.objects.create(titulo="TESTE Qualquer")
    resposta = cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]), {"situacao": "voando"}
    )
    assert resposta["Location"].endswith("resultado=situacao_desconhecida")
    tarefa.refresh_from_db()
    assert tarefa.situacao == "a_fazer"


@respx.mock
def test_o_next_so_volta_para_dentro_do_painel():
    cliente = _cliente()
    tarefa = Tarefa.objects.create(titulo="TESTE Qualquer")
    resposta = cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]),
        {"situacao": "em_andamento", "next": "https://outro-site.exemplo/"},
    )
    assert resposta["Location"] == reverse(PAINEL) + "?resultado=situacao"


# ---------------------------------------------------------------- as visões


@respx.mock
def test_minhas_tarefas_e_so_as_da_pessoa_da_sessao():
    livia = _livia()
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    Tarefa.objects.create(titulo="TESTE Da Lívia", responsavel=livia)
    Tarefa.objects.create(titulo="TESTE Do Ryan", responsavel=ryan)

    cliente = _cliente(LIVIA, nome="Lívia")
    minhas = _texto(cliente.get(reverse(PAINEL)))
    assert "TESTE Da Lívia" in minhas
    assert "TESTE Do Ryan" not in minhas

    equipe = _texto(cliente.get(reverse(PAINEL) + "?visao=equipe"))
    assert "TESTE Da Lívia" in equipe and "TESTE Do Ryan" in equipe


@respx.mock
def test_administrador_sem_conta_associada_cai_na_equipe_e_e_avisado_em_minhas():
    Tarefa.objects.create(titulo="TESTE Solta")
    cliente = _cliente()
    assert "TESTE Solta" in _texto(cliente.get(reverse(PAINEL)))
    html = _texto(cliente.get(reverse(PAINEL) + "?visao=minhas"))
    assert "ainda não está associada a ninguém da equipe" in html
    assert "TESTE Solta" not in html


@respx.mock
def test_filtro_por_responsavel_e_por_prazo_e_destaque_de_atrasada():
    livia = _livia()
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    hoje = timezone.localdate()
    Tarefa.objects.create(
        titulo="TESTE Atrasada do Ryan",
        responsavel=ryan,
        prazo=hoje - timedelta(days=2),
    )
    Tarefa.objects.create(
        titulo="TESTE Da Lívia para a semana",
        responsavel=livia,
        prazo=hoje + timedelta(days=3),
    )
    Tarefa.objects.create(titulo="TESTE Sem prazo")
    Tarefa.objects.create(
        titulo="TESTE Concluída no passado",
        prazo=hoje - timedelta(days=9),
        situacao="concluida",
        concluida_em=timezone.now(),
    )
    cliente = _cliente()
    base = reverse(PAINEL) + "?visao=equipe"

    do_ryan = _texto(cliente.get(f"{base}&responsavel={ryan.id}"))
    assert "TESTE Atrasada do Ryan" in do_ryan
    assert "TESTE Da Lívia" not in do_ryan
    assert 'class="tarefa atrasada"' in do_ryan
    assert "1 atrasada" in do_ryan

    atrasadas = _texto(cliente.get(f"{base}&prazo=atrasadas"))
    assert "TESTE Atrasada do Ryan" in atrasadas
    assert (
        "TESTE Concluída no passado" not in atrasadas
    ), "concluída com prazo vencido não é atrasada"
    assert "TESTE Sem prazo" not in atrasadas

    semana = _texto(cliente.get(f"{base}&prazo=semana"))
    assert "TESTE Da Lívia para a semana" in semana
    assert "TESTE Atrasada do Ryan" not in semana

    sem = _texto(cliente.get(f"{base}&responsavel=sem"))
    assert "TESTE Sem prazo" in sem
    assert "TESTE Atrasada do Ryan" not in sem

    nada = _texto(cliente.get(f"{base}&responsavel={livia.id}&prazo=atrasadas"))
    assert "Nenhuma tarefa com esses filtros" in nada


# ---------------------------------------------------------------- as pessoas


@respx.mock
def test_o_administrador_associa_uma_conta_e_a_pessoa_passa_a_entrar():
    # O dublê da identidade responde pela ÚLTIMA sessão registrada, então cada
    # troca de pessoa é um `_cliente()` novo.
    livia = MembroDaEquipe.objects.get(nome="Lívia")
    assert _cliente(LIVIA).get(reverse(PAINEL)).status_code == 404

    cliente = _cliente()
    html = _texto(cliente.get(reverse("pessoas_da_equipe")))
    assert "Sem conta associada." in html

    resposta = cliente.post(
        reverse("pessoas_da_equipe_associar"), {"pessoa": livia.id, "email": LIVIA}
    )
    assert resposta["Location"].endswith("resultado=associada")
    livia.refresh_from_db()
    assert livia.email == LIVIA
    assert _cliente(LIVIA).get(reverse(PAINEL)).status_code == 200

    # E-mail já de outra pessoa é recusado; torto também.
    cliente = _cliente()
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    em_uso = cliente.post(
        reverse("pessoas_da_equipe_associar"), {"pessoa": ryan.id, "email": LIVIA}
    )
    assert em_uso["Location"].endswith("resultado=email_em_uso")
    torto = cliente.post(
        reverse("pessoas_da_equipe_associar"), {"pessoa": ryan.id, "email": "nao-e"}
    )
    assert torto["Location"].endswith("resultado=email_invalido")
    ryan.refresh_from_db()
    assert ryan.email == ""

    # Vazio desassocia.
    cliente.post(
        reverse("pessoas_da_equipe_associar"), {"pessoa": livia.id, "email": ""}
    )
    livia.refresh_from_db()
    assert livia.email == ""
