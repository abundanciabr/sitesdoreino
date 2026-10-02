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
5. **A segunda camada quebrando calada** (01/10/2026): objetivo desativado que
   some da tarefa que já o tinha, compromisso que conta tarefa reaberta como
   cumprida, semana passada que muda depois de fechada, comentário que entra
   vazio, e as telas novas abrindo para quem não é da casa.

A rede é dublada com `respx`, como nos irmãos desta pasta.
"""

from __future__ import annotations

from datetime import datetime, time, timedelta

import httpx
import pytest
import respx
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from apps.core import placar
from apps.core.models import (
    Comentario,
    Compromisso,
    MembroDaEquipe,
    Objetivo,
    Tarefa,
)

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
def test_sem_cookie_vai_para_a_entrada_da_equipe():
    # Desde o acesso por aparelho (01/10/2026), quem chega sem acesso ao painel
    # vai para a entrada DA EQUIPE, que oferece e-mail e senha e a conta Google.
    resposta = Client().get(reverse(PAINEL))
    assert resposta.status_code == 302
    assert resposta["Location"] == reverse("entrar_na_equipe") + "?next=/equipe/"


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
    assert "sem e-mail" in html

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


# ---------------------------------------------------------------- a segunda camada


def _segunda(dia):
    return dia - timedelta(days=dia.weekday())


def _no_meio_do_dia(dia):
    return timezone.make_aware(datetime.combine(dia, time(12, 0)))


@respx.mock
def test_quem_nao_e_da_casa_nao_alcanca_as_telas_novas():
    tarefa = Tarefa.objects.create(titulo="TESTE Qualquer")
    objetivo = Objetivo.objects.create(titulo="TESTE Objetivo")
    cliente = _cliente(DE_FORA)
    for rota, args in (
        ("objetivos_da_equipe", []),
        ("objetivo_novo", []),
        ("objetivo_editar", [objetivo.id]),
        ("semana_da_equipe", []),
    ):
        assert cliente.get(reverse(rota, args=args)).status_code == 404, rota
    for rota, args, dados in (
        ("tarefa_compromisso", [tarefa.id], {"acao": "marcar"}),
        ("tarefa_comentar", [tarefa.id], {"texto": "TESTE intruso"}),
        ("objetivo_ativo", [objetivo.id], {"ativo": "0"}),
    ):
        assert cliente.post(reverse(rota, args=args), dados).status_code == 404, rota
    assert not Compromisso.objects.exists()
    assert not Comentario.objects.exists()
    objetivo.refresh_from_db()
    assert objetivo.ativo


# ---- objetivos


@respx.mock
def test_objetivos_comecam_vazios_e_a_tela_diz_isso():
    html = _texto(_cliente().get(reverse("objetivos_da_equipe")))
    assert "Ainda não há nenhum objetivo" in html
    assert 'href="' + reverse("objetivo_novo") + '"' in html
    assert ">Objetivos</a>" in html


@respx.mock
def test_quem_e_da_equipe_cria_edita_desativa_e_reativa_um_objetivo():
    _livia()
    cliente = _cliente(LIVIA, nome="Lívia")
    resposta = cliente.post(
        reverse("objetivo_novo"),
        {"titulo": "TESTE Lançar a turma de novembro", "prazo": "2026-11-30"},
    )
    assert resposta["Location"].endswith("resultado=objetivo_criado")
    objetivo = Objetivo.objects.get()
    assert objetivo.criado_por == f"Lívia ({LIVIA})"
    assert objetivo.ativo

    cliente.post(
        reverse("objetivo_editar", args=[objetivo.id]),
        {"titulo": "TESTE Lançar a turma de dezembro", "descricao": "Com aula."},
    )
    objetivo.refresh_from_db()
    assert objetivo.titulo == "TESTE Lançar a turma de dezembro"
    assert objetivo.descricao == "Com aula."
    assert objetivo.prazo is None

    resposta = cliente.post(
        reverse("objetivo_ativo", args=[objetivo.id]), {"ativo": "0"}
    )
    assert resposta["Location"].endswith("resultado=objetivo_desativado")
    objetivo.refresh_from_db()
    assert not objetivo.ativo
    html = _texto(cliente.get(reverse("objetivos_da_equipe")))
    assert "Desativados" in html and ">Reativar</button>" in html
    assert "TESTE Lançar a turma de dezembro" not in _texto(
        cliente.get(reverse("tarefa_nova"))
    ), "objetivo desativado não se oferece a tarefa nova"

    cliente.post(reverse("objetivo_ativo", args=[objetivo.id]), {"ativo": "1"})
    objetivo.refresh_from_db()
    assert objetivo.ativo


@respx.mock
def test_objetivo_sem_titulo_ou_com_prazo_torto_nao_salva():
    resposta = _cliente().post(
        reverse("objetivo_novo"), {"titulo": "", "prazo": "31/02/2026"}
    )
    assert resposta.status_code == 400
    html = _texto(resposta)
    assert "precisa de um título" in html and "data válida" in html
    assert not Objetivo.objects.exists()


@respx.mock
def test_tarefa_ligada_a_objetivo_e_filtro_por_objetivo():
    objetivo = Objetivo.objects.create(titulo="TESTE Dobrar as matrículas")
    cliente = _cliente()
    html = _texto(cliente.get(reverse("tarefa_nova") + f"?objetivo={objetivo.id}"))
    assert f'<option value="{objetivo.id}" selected>' in html

    cliente.post(
        reverse("tarefa_nova"),
        {"titulo": "TESTE Ligada", "objetivo": objetivo.id, "situacao": "a_fazer"},
    )
    Tarefa.objects.create(titulo="TESTE Solta")
    assert Tarefa.objects.get(titulo="TESTE Ligada").objetivo == objetivo

    base = reverse(PAINEL) + "?visao=equipe"
    do_objetivo = _texto(cliente.get(f"{base}&objetivo={objetivo.id}"))
    assert "TESTE Ligada" in do_objetivo and "TESTE Solta" not in do_objetivo
    assert "Objetivo: <a" in do_objetivo

    sem = _texto(cliente.get(f"{base}&objetivo=sem"))
    assert "TESTE Solta" in sem and "TESTE Ligada" not in sem

    lista = _texto(cliente.get(reverse("objetivos_da_equipe")))
    assert "1 tarefa aberta, 0 concluídas" in lista


@respx.mock
def test_objetivo_desativado_continua_na_tarefa_que_ja_o_tinha():
    objetivo = Objetivo.objects.create(titulo="TESTE Antigo", ativo=False)
    tarefa = Tarefa.objects.create(titulo="TESTE Herdada", objetivo=objetivo)
    cliente = _cliente()

    ficha = _texto(cliente.get(reverse("tarefa_editar", args=[tarefa.id])))
    assert "TESTE Antigo (desativado)" in ficha
    cliente.post(
        reverse("tarefa_editar", args=[tarefa.id]),
        {"titulo": "TESTE Herdada", "objetivo": objetivo.id, "situacao": "a_fazer"},
    )
    tarefa.refresh_from_db()
    assert tarefa.objetivo == objetivo, "salvar a ficha largou o objetivo"

    nova = cliente.post(
        reverse("tarefa_nova"),
        {"titulo": "TESTE Nova", "objetivo": objetivo.id, "situacao": "a_fazer"},
    )
    assert nova.status_code == 400
    assert "Não conheço esse objetivo" in _texto(nova)


# ---- compromissos da semana


@respx.mock
def test_assumir_na_semana_aparece_em_esta_semana_e_concluir_cumpre():
    livia = _livia()
    tarefa = Tarefa.objects.create(titulo="TESTE Gravar a aula 4", responsavel=livia)
    cliente = _cliente(LIVIA, nome="Lívia")
    destino = reverse(PAINEL) + "?visao=minhas"

    resposta = cliente.post(
        reverse("tarefa_compromisso", args=[tarefa.id]),
        {"acao": "marcar", "next": destino},
    )
    assert resposta["Location"] == destino + "&resultado=compromisso_marcado"
    compromisso = Compromisso.objects.get()
    assert compromisso.semana == _segunda(timezone.localdate())
    assert compromisso.marcado_por == f"Lívia ({LIVIA})"
    painel = _texto(cliente.get(destino))
    assert "Compromisso desta semana" in painel
    assert ">Tirar da semana</button>" in painel

    semana = _texto(cliente.get(reverse("semana_da_equipe")))
    assert "Lívia (você)" in semana
    assert "Em aberto" in semana and "TESTE Gravar a aula 4" in semana
    assert "0 de 1" in semana

    cliente.post(
        reverse("tarefa_situacao", args=[tarefa.id]), {"situacao": "concluida"}
    )
    semana = _texto(cliente.get(reverse("semana_da_equipe")))
    assert "Cumprido" in semana and "1 de 1" in semana
    assert "Em aberto" not in semana

    # Reabrir desfaz o cumprido: cumprido é estar concluída, não ter estado.
    cliente.post(reverse("tarefa_situacao", args=[tarefa.id]), {"situacao": "a_fazer"})
    assert "0 de 1" in _texto(cliente.get(reverse("semana_da_equipe")))


@respx.mock
def test_compromisso_exige_tarefa_aberta_e_com_responsavel():
    cliente = _cliente()
    solta = Tarefa.objects.create(titulo="TESTE Sem dono")
    feita = Tarefa.objects.create(
        titulo="TESTE Já feita",
        responsavel=MembroDaEquipe.objects.get(nome="Ryan"),
        situacao="concluida",
        concluida_em=timezone.now(),
    )
    sem_dono = cliente.post(
        reverse("tarefa_compromisso", args=[solta.id]), {"acao": "marcar"}
    )
    assert sem_dono["Location"].endswith("resultado=compromisso_sem_responsavel")
    ja_feita = cliente.post(
        reverse("tarefa_compromisso", args=[feita.id]), {"acao": "marcar"}
    )
    assert ja_feita["Location"].endswith("resultado=compromisso_concluida")
    assert not Compromisso.objects.exists()
    html = _texto(cliente.get(reverse(PAINEL)))
    assert ">Assumir na semana</button>" not in html


@respx.mock
def test_tirar_da_semana_so_mexe_na_semana_corrente():
    livia = _livia()
    tarefa = Tarefa.objects.create(titulo="TESTE Campanha", responsavel=livia)
    corrente = _segunda(timezone.localdate())
    Compromisso.objects.create(tarefa=tarefa, semana=corrente - timedelta(days=7))
    Compromisso.objects.create(tarefa=tarefa, semana=corrente)
    resposta = _cliente(LIVIA, nome="Lívia").post(
        reverse("tarefa_compromisso", args=[tarefa.id]), {"acao": "tirar"}
    )
    assert resposta["Location"].endswith("resultado=compromisso_tirado")
    assert list(Compromisso.objects.values_list("semana", flat=True)) == [
        corrente - timedelta(days=7)
    ], "a semana passada é registro e não pode ser reescrita"


@respx.mock
def test_so_quem_responde_pela_tarefa_assume_ou_tira_da_semana():
    """02/10/2026: a Lívia tirou da semana uma tarefa que o Arameu assumiu."""
    livia = _livia()
    arameu = MembroDaEquipe.objects.get(nome="Arameu")
    arameu.email = DONO
    arameu.save()
    tarefa = Tarefa.objects.create(titulo="TESTE Portfólio", responsavel=arameu)
    Compromisso.objects.create(tarefa=tarefa, semana=_segunda(timezone.localdate()))
    dela = Tarefa.objects.create(titulo="TESTE Aula", responsavel=livia)
    cliente = _cliente(LIVIA, nome="Lívia")

    for rota in (reverse(PAINEL) + "?visao=equipe", reverse("semana_da_equipe")):
        html = _texto(cliente.get(rota))
        assert "TESTE Portfólio" in html
        assert ">Tirar da semana</button>" not in html, rota
    assert ">Assumir na semana</button>" in _texto(cliente.get(reverse(PAINEL)))

    tirar = cliente.post(
        reverse("tarefa_compromisso", args=[tarefa.id]), {"acao": "tirar"}
    )
    assert tirar["Location"].endswith("resultado=compromisso_de_outra_pessoa")
    assert Compromisso.objects.filter(tarefa=tarefa).exists()
    marcar = cliente.post(reverse("tarefa_compromisso", args=[dela.id]), {"acao": "marcar"})
    assert marcar["Location"].endswith("resultado=compromisso_marcado")
    Compromisso.objects.filter(tarefa=dela).delete()
    assert "só essa pessoa assume ou tira" in _texto(
        cliente.get(reverse(PAINEL) + "?resultado=compromisso_de_outra_pessoa")
    )

    # Nem a Lívia assume a tarefa do Arameu; o Arameu, sim, tira a dele.
    alheia = Tarefa.objects.create(titulo="TESTE Outra do Arameu", responsavel=arameu)
    cliente.post(reverse("tarefa_compromisso", args=[alheia.id]), {"acao": "marcar"})
    assert not Compromisso.objects.filter(tarefa=alheia).exists()
    dono = _cliente(DONO, nome="Arameu")
    assert ">Tirar da semana</button>" in _texto(dono.get(reverse("semana_da_equipe")))
    dono.post(reverse("tarefa_compromisso", args=[tarefa.id]), {"acao": "tirar"})
    assert not Compromisso.objects.exists()


@respx.mock
def test_semana_passada_mostra_o_que_foi_cumprido_e_o_que_ficou():
    ryan = MembroDaEquipe.objects.get(nome="Ryan")
    ryan.email = "ryan-conta-de-teste@exemplo.com"
    ryan.save()
    passada = _segunda(timezone.localdate()) - timedelta(days=7)
    cumprida = Tarefa.objects.create(
        titulo="TESTE Cumprida na quarta",
        responsavel=ryan,
        situacao="concluida",
        concluida_em=_no_meio_do_dia(passada + timedelta(days=2)),
    )
    atrasou = Tarefa.objects.create(
        titulo="TESTE Concluída só depois",
        responsavel=ryan,
        situacao="concluida",
        concluida_em=_no_meio_do_dia(passada + timedelta(days=8)),
    )
    parada = Tarefa.objects.create(titulo="TESTE Parada", responsavel=ryan)
    for tarefa in (cumprida, atrasou, parada):
        Compromisso.objects.create(tarefa=tarefa, semana=passada)

    html = _texto(
        _cliente(ryan.email, nome="Ryan").get(
            reverse("semana_da_equipe") + f"?semana={passada.isoformat()}"
        )
    )
    assert "Semana de " + passada.strftime("%d/%m") in html
    assert "Cumpridos: 1 de 3 compromissos" in html
    assert "Ficou" in html and "Em aberto" not in html
    assert "concluída depois, em" in html
    assert ">Tirar da semana</button>" not in html, "semana passada só se lê"
    assert "Semana seguinte" in html


@respx.mock
def test_esta_semana_mostra_toda_pessoa_e_nao_vai_para_o_futuro():
    cliente = _cliente()
    html = _texto(cliente.get(reverse("semana_da_equipe")))
    for nome in ("Arameu", "Ryan", "Lívia", "Maria"):
        assert nome in html
    assert "Nenhum compromisso assumido nesta semana" in html
    assert "Nada assumido nesta semana" in html
    assert "Semana seguinte" not in html

    futuro = _texto(cliente.get(reverse("semana_da_equipe") + "?semana=2099-01-05"))
    assert "Semana seguinte" not in futuro and "<b>Esta semana</b>" in futuro


# ---- comentários


@respx.mock
def test_comentar_mostra_texto_quem_e_quando_na_ficha_e_conta_no_cartao():
    _livia()
    tarefa = Tarefa.objects.create(titulo="TESTE Revisar a apostila")
    cliente = _cliente(LIVIA, nome="Lívia")
    resposta = cliente.post(
        reverse("tarefa_comentar", args=[tarefa.id]),
        {"texto": "TESTE Faltam as páginas 3 e 4.\r\nVejo amanhã."},
    )
    ficha = reverse("tarefa_editar", args=[tarefa.id])
    assert resposta["Location"] == ficha + "?resultado=comentado#comentarios"
    comentario = Comentario.objects.get()
    assert comentario.autor == f"Lívia ({LIVIA})"
    assert comentario.texto == "TESTE Faltam as páginas 3 e 4.\nVejo amanhã."

    html = _texto(cliente.get(ficha + "?resultado=comentado"))
    assert "Comentário publicado." in html
    assert "TESTE Faltam as páginas 3 e 4.<br>Vejo amanhã." in html
    assert "Lívia, " in html, "o comentário mostra a pessoa, pelo vínculo"
    assert "1 comentário" in _texto(cliente.get(reverse(PAINEL) + "?visao=equipe"))


@respx.mock
def test_comentario_vazio_ou_longo_nao_publica():
    tarefa = Tarefa.objects.create(titulo="TESTE Qualquer")
    cliente = _cliente()
    vazio = cliente.post(reverse("tarefa_comentar", args=[tarefa.id]), {"texto": "  "})
    assert "resultado=comentario_vazio" in vazio["Location"]
    longo = cliente.post(
        reverse("tarefa_comentar", args=[tarefa.id]), {"texto": "TESTE " + "x" * 500}
    )
    assert "resultado=comentario_longo" in longo["Location"]
    # 500 letras com quebras de linha cabem: o navegador conta cada quebra como uma.
    cabe = "TESTE" + "\r\n" * 10 + "y" * 485
    ok = cliente.post(reverse("tarefa_comentar", args=[tarefa.id]), {"texto": cabe})
    assert "resultado=comentado" in ok["Location"]
    assert Comentario.objects.count() == 1
    assert "Nenhum comentário ainda" not in _texto(
        cliente.get(reverse("tarefa_editar", args=[tarefa.id]))
    )


# ---------------------------------------------------------------- a terceira camada: o placar


ALUNOS = "http://alunos:8000/api/alunos"


def _montagem_falsa(veredito: str, esperado: int):
    """Uma `placar.montar_o_placar` de mentira, no formato da de verdade.

    A conta da meta é guardada em `test_placar.py`; aqui só se mede se o
    número CHEGA à aba e o que a equipe faz por ele. O veredito vem escrito
    para o teste não depender do dia em que roda."""

    def montar(hoje, site_id=None):
        meta, _ = placar.ler_cartao(placar.CARTAO_DA_META)
        pedidos, _ = placar.ler_cartao(placar.CARTAO_DOS_PEDIDOS)
        de48, _ = placar.ler_cartao(placar.CARTAO_DAS_48H)
        return {
            "meta": meta,
            "placar": {
                "x": 37,
                "alvo": 1000,
                "partida": 0,
                "partida_em": "2026-09-03",
                "ate": "2026-12-15",
                "esperado_hoje": esperado,
                "distancia": 963,
                "dias_restantes": 75,
                "ritmo_por_semana": 89.9,
                "veredito": veredito,
            },
            "contagem": {"ciclo": 37},
            "direcao": {
                "pedidos": {
                    "veredito": "abaixo",
                    "esta_semana": 2,
                    "meta": 5,
                    "sequencia": 0,
                },
                "liberacoes": {
                    "veredito": "cumprida",
                    "por_cento": 100,
                    "total": 3,
                    "esperando_ha_muito": 0,
                },
            },
            "cartao_pedidos": pedidos,
            "cartao_48h": de48,
        }

    return montar


def test_o_que_o_objetivo_move_aponta_para_cartoes_que_o_placar_le():
    """O valor guardado é o NOME DO CARTÃO: se o placar renomear um, a ligação
    da equipe não pode ficar apontando para um número que não existe mais."""
    assert set(Objetivo.Move.values) == {
        placar.CARTAO_DA_META,
        placar.CARTAO_DOS_PEDIDOS,
        placar.CARTAO_DAS_48H,
    }
    for nome in Objetivo.Move.values:
        cartao, recusas = placar.ler_cartao(nome)
        assert cartao is not None, (nome, recusas)


@respx.mock
def test_objetivo_escolhe_o_que_move_e_a_lista_e_o_cartao_dizem():
    cliente = _cliente()
    cliente.post(
        reverse("objetivo_novo"),
        {"titulo": "TESTE Encher a sala de espera", "move": Objetivo.Move.CHEGADAS},
    )
    objetivo = Objetivo.objects.get()
    assert objetivo.move == placar.CARTAO_DOS_PEDIDOS

    ficha = _texto(cliente.get(reverse("objetivo_editar", args=[objetivo.id])))
    assert f'value="{placar.CARTAO_DOS_PEDIDOS}" selected' in ficha
    lista = _texto(cliente.get(reverse("objetivos_da_equipe")))
    assert "Move: Medida de direção: chegadas à sala de espera" in lista

    Tarefa.objects.create(titulo="TESTE Divulgar a turma", objetivo=objetivo)
    painel = _texto(cliente.get(reverse(PAINEL) + "?visao=equipe"))
    assert "move as chegadas" in painel

    # Desligar é escolher "Nada declarado"; a tarefa continua no objetivo.
    cliente.post(
        reverse("objetivo_editar", args=[objetivo.id]),
        {"titulo": objetivo.titulo, "move": ""},
    )
    objetivo.refresh_from_db()
    assert objetivo.move == ""
    assert "move as chegadas" not in _texto(
        cliente.get(reverse(PAINEL) + "?visao=equipe")
    )


@respx.mock
def test_numero_do_placar_desconhecido_nao_salva():
    resposta = _cliente().post(
        reverse("objetivo_novo"), {"titulo": "TESTE Qualquer", "move": "faturamento"}
    )
    assert resposta.status_code == 400
    assert "Não conheço esse número do placar" in _texto(resposta)
    assert not Objetivo.objects.exists()


@respx.mock
def test_quem_nao_e_da_casa_nao_ve_o_placar_da_equipe(monkeypatch):
    monkeypatch.setattr(placar, "montar_o_placar", _montagem_falsa("ganhando", 30))
    resposta = _cliente(DE_FORA).get(reverse("placar_da_equipe"))
    assert resposta.status_code == 404
    assert "MCI" not in _texto(resposta)


@respx.mock
def test_a_aba_placar_mostra_os_numeros_e_o_que_a_equipe_faz_por_eles(monkeypatch):
    monkeypatch.setattr(placar, "montar_o_placar", _montagem_falsa("ganhando", 30))
    livia = _livia()
    mci = Objetivo.objects.create(
        titulo="TESTE Bater a meta do ciclo", move=Objetivo.Move.MCI
    )
    Objetivo.objects.create(titulo="TESTE Objetivo que não diz o que move")
    feita = Tarefa.objects.create(titulo="TESTE Feita", responsavel=livia, objetivo=mci)
    aberta = Tarefa.objects.create(
        titulo="TESTE Aberta", responsavel=livia, objetivo=mci
    )
    solta = Tarefa.objects.create(titulo="TESTE Solta", responsavel=livia)
    semana = _segunda(timezone.localdate())
    for tarefa in (feita, aberta, solta):
        Compromisso.objects.create(tarefa=tarefa, semana=semana)
    cliente = _cliente(LIVIA, nome="Lívia")
    cliente.post(reverse("tarefa_situacao", args=[feita.id]), {"situacao": "concluida"})

    resposta = cliente.get(reverse("placar_da_equipe"))
    assert resposta.status_code == 200, "o crachá de equipe abre a aba"
    html = _texto(resposta)
    assert "A meta grande (MCI nº 1)" in html
    assert ">Ganhando</span>" in html and "estamos em 37" in html
    assert "De 0 para 1000, de 03/09/2026 até 15/12/2026." in html
    assert ">Abaixo da meta</span>" in html, "a medida das chegadas"
    assert ">Na meta</span>" in html, "a medida das 48 horas"
    assert "TESTE Bater a meta do ciclo" in html
    assert "1 tarefa aberta." in html
    assert "<b>1 de 2</b> cumpridos" in html
    assert "1 não diz mover nenhum destes números (0 cumpridos)" in html
    assert "Nenhum objetivo ativo diz mover este número" in html
    assert (
        f'href="{reverse("placar")}"' not in html
    ), "o crachá de equipe não vê o link do placar inteiro, que para ele é 404"
    assert f'class="aba ativa" href="{reverse("placar_da_equipe")}"' in html

    # A semana conta igual: a mesma regra de cumprido nas duas abas.
    semana_html = _texto(cliente.get(reverse("semana_da_equipe")))
    assert "1 de 3" in semana_html
    assert "move a MCI" in semana_html


@respx.mock
def test_a_aba_placar_diz_perdendo_e_o_administrador_ve_o_placar_inteiro(
    monkeypatch,
):
    monkeypatch.setattr(placar, "montar_o_placar", _montagem_falsa("perdendo", 50))
    html = _texto(_cliente().get(reverse("placar_da_equipe")))
    assert ">Perdendo</span>" in html
    assert "deveríamos estar em 50, e estamos em 37" in html
    assert f'href="{reverse("placar")}"' in html
    assert "Nenhum compromisso assumido nesta semana" in html


@respx.mock
def test_a_aba_placar_abre_com_a_escola_fora_do_ar_e_nao_inventa_zero(monkeypatch):
    """Sem dublê na montagem: a de verdade, com a `alunos` recusando a conexão."""
    monkeypatch.setenv("ALUNOS_API_URL", ALUNOS)
    monkeypatch.setenv("ALUNOS_API_TOKEN", "token-do-par-admin-alunos")
    respx.get(url__startswith=ALUNOS).mock(side_effect=httpx.ConnectError("recusou"))
    resposta = _cliente().get(reverse("placar_da_equipe"))
    assert resposta.status_code == 200
    html = _texto(resposta)
    assert "Não consigo contar agora" in html
    assert "Não consegui medir agora" in html
    assert 'class="valor">0' not in html
