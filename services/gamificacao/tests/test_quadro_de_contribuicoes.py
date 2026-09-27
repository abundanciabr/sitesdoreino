"""O quadro de contribuições da Comunidade (dossiê §6 e §12).

A escola publica o que precisa, o aluno lê a exigência inteira ANTES de
assumir, assume dentro das vagas, manda o link, e a equipe aceita ou devolve
com motivo e orientação. O aceite é reconhecimento, nunca pagamento: sem
pontos, sem créditos (dossiê §7 e §17).

O QUE ESTE ARQUIVO TRAVA:

1. **A tarefa mostra os cinco campos antes do gesto**: o que entregar, quem
   pode, como se avalia, o reconhecimento e quem aceita.
2. **Vaga é teto**, e desistir devolve a vaga.
3. **Um compromisso ativo por pessoa e tarefa**, garantido pelo BANCO.
4. **Ninguém aceita a própria contribuição** (dossiê §12).
5. **Aceitar concede uma vez só**: reaceite e reentrega não duplicam o fato
   nem a medalha; devolução não concede nada.
6. **Devolver exige motivo da lista e orientação por escrito.**
7. **Só a equipe publica e decide**, fail-CLOSED, com CSRF.
8. **Estados ditos em texto**, sem ranking e sem contagem pública.
"""

from __future__ import annotations

import importlib
from datetime import timedelta
from io import StringIO

import pytest
from django.apps import apps as registro_de_apps
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import Client

from apps.core import equipe as porta_da_equipe
from apps.gamificacao import contribuicoes
from apps.gamificacao.contribuicoes import ContribuicaoRecusada
from apps.gamificacao.interruptores import impedimentos_da_conquista
from apps.gamificacao.management.commands.semear_economia import CONQUISTAS
from apps.gamificacao.models import (
    CompromissoDeContribuicao,
    Concessao,
    ConquistaDefinicao,
    ContribuicaoAceita,
    LancamentoDeXP,
    MovimentoDeCristais,
    Pessoa,
    TarefaComunitaria,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNA = "pes-aluna"
COLEGA = "pes-colega"
PROFESSORA = "pes-professora"
MONITOR = "pes-monitor"
MEDALHA = "primeira-contribuicao"

migracao = importlib.import_module(
    "apps.gamificacao.migrations.0008_quadro_de_contribuicoes"
)


@pytest.fixture(autouse=True)
def site_e_sessao(monkeypatch):
    """O site vem do env; quem é a pessoa vem da identidade. Os dois em dublê."""
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, f"{PROFESSORA},{MONITOR}")
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False
    # A matrícula tem arquivo próprio (`test_quadro_exige_matricula.py`); aqui
    # quem assume pela tela é sempre aluno com matrícula ativa.
    monkeypatch.setattr(
        "apps.core.views.categoria_de_quem_pede", lambda request: "aluno"
    )


def _entrar_como(monkeypatch, pessoa_id: str | None):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa_id)


def _pessoa(pessoa_id: str) -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=pessoa_id, defaults={"email": f"{pessoa_id}@exemplo.test"}
    )
    return pessoa


def _semear_e_ligar() -> None:
    call_command("semear_economia", "--site", SITE, stdout=StringIO())
    ConquistaDefinicao.objects.filter(site_id=SITE, slug=MEDALHA).update(ativa=True)


def _tarefa(**campos) -> TarefaComunitaria:
    dados = {
        "site_id": SITE,
        "autor_id": PROFESSORA,
        "titulo": "Estudo de caso de uma peça de Roblox",
        "o_que_entregar": "Um documento com o antes, o depois e o que mudou.",
        "quem_pode": "Quem já concluiu o primeiro módulo.",
        "criterios": ["Mostra o antes e o depois", "Explica cada decisão"],
        "responsavel_id": PROFESSORA,
        "responsavel_nome": "Professora Ana",
        "vagas": 2,
    }
    dados.update(campos)
    return contribuicoes.publicar(**dados)


def _assumir(tarefa, pessoa_id=ALUNA) -> CompromissoDeContribuicao:
    return contribuicoes.assumir(
        tarefa=tarefa, pessoa=_pessoa(pessoa_id), categoria="aluno"
    )


def _enviar(tarefa, pessoa_id=ALUNA, link="https://exemplo.test/estudo"):
    return contribuicoes.enviar(tarefa=tarefa, pessoa=_pessoa(pessoa_id), link=link)


def _aceitar(compromisso, quem=PROFESSORA):
    return contribuicoes.aceitar(compromisso=compromisso, validador_id=quem)


# ------------------------------------------- 1. o quadro antes do gesto


def test_o_quadro_mostra_os_cinco_campos_antes_de_assumir(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)
    _tarefa()

    pagina = Client().get("/contribuicoes").content.decode()

    assert "Estudo de caso de uma peça de Roblox" in pagina
    assert "Um documento com o antes, o depois e o que mudou." in pagina
    assert "Quem já concluiu o primeiro módulo." in pagina
    assert "Mostra o antes e o depois" in pagina
    assert "Explica cada decisão" in pagina
    assert "Quem aceita: Professora Ana" in pagina
    assert "Reconhecimento:" in pagina
    assert "Não dá pontos nem créditos." in pagina
    assert "Assumir esta tarefa" in pagina


def test_quadro_vazio_diz_que_nao_ha_tarefa(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/contribuicoes").content.decode()

    assert "Nenhuma tarefa aberta agora" in pagina


def test_visitante_ve_convite_e_nunca_erro(monkeypatch):
    _entrar_como(monkeypatch, None)
    _tarefa()

    resposta = Client().get("/contribuicoes")

    assert resposta.status_code == 200
    assert "Entrar na escola" in resposta.content.decode()
    assert "Estudo de caso" not in resposta.content.decode()


def test_sem_site_no_env_a_tela_nao_quebra(monkeypatch):
    monkeypatch.setattr("apps.core.views.site_atual", lambda: None)
    _entrar_como(monkeypatch, ALUNA)

    assert Client().get("/contribuicoes").status_code == 200


def test_a_tela_de_medalhas_leva_ao_quadro(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/medalhas").content.decode()

    assert 'href="/contribuicoes"' in pagina


# ------------------------------------------- 2. vagas e compromisso


def test_vaga_e_teto_e_o_quadro_diz_sem_vaga(monkeypatch):
    tarefa = _tarefa(vagas=1)
    _assumir(tarefa, COLEGA)

    with pytest.raises(ContribuicaoRecusada, match="vagas"):
        _assumir(tarefa, ALUNA)

    _entrar_como(monkeypatch, ALUNA)
    pagina = Client().get("/contribuicoes").content.decode()
    assert "Sem vaga agora" in pagina
    assert "Assumir esta tarefa" not in pagina


def test_desistir_devolve_a_vaga(monkeypatch):
    tarefa = _tarefa(vagas=1)
    _assumir(tarefa, COLEGA)
    contribuicoes.desistir(tarefa=tarefa, pessoa=_pessoa(COLEGA))

    compromisso = _assumir(tarefa, ALUNA)

    assert compromisso.estado == CompromissoDeContribuicao.Estado.ASSUMIDA
    assert CompromissoDeContribuicao.objects.get(pessoa_id=COLEGA).estado == (
        CompromissoDeContribuicao.Estado.CANCELADA
    )


@pytest.mark.parametrize(
    "campos",
    [
        {"vagas": 0},
        {"vagas": 1000},
        {"titulo": "x" * 121},
        {"responsavel_nome": "x" * 121},
        {"criterios": ["", "   "]},
        {"o_que_entregar": "  "},
    ],
)
def test_tarefa_incompleta_ou_fora_da_medida_nao_nasce(campos):
    """A recusa vira frase antes do banco: coluna estourada seria um 500."""
    with pytest.raises(ContribuicaoRecusada):
        _tarefa(**campos)

    assert TarefaComunitaria.objects.count() == 0


def test_assumir_duas_vezes_vira_frase_e_nao_erro():
    tarefa = _tarefa()
    _assumir(tarefa)

    with pytest.raises(ContribuicaoRecusada, match="já assumiu"):
        _assumir(tarefa)


def test_um_compromisso_ativo_por_pessoa_e_tarefa_mora_no_banco():
    """A conferência em Python perde a corrida de dois cliques; o banco não."""
    tarefa = _tarefa()
    linha = {"tarefa": tarefa, "pessoa": _pessoa(ALUNA), "site_id": SITE}
    CompromissoDeContribuicao.objects.create(**linha)

    with pytest.raises(IntegrityError), transaction.atomic():
        CompromissoDeContribuicao.objects.create(**linha)


def test_tarefa_encerrada_nao_aceita_compromisso_novo_mas_honra_o_assumido(
    monkeypatch,
):
    tarefa = _tarefa()
    _assumir(tarefa, COLEGA)
    contribuicoes.encerrar(tarefa=tarefa)

    with pytest.raises(ContribuicaoRecusada, match="encerrada"):
        _assumir(tarefa, ALUNA)
    assert _enviar(tarefa, COLEGA).estado == CompromissoDeContribuicao.Estado.ENVIADA

    _entrar_como(monkeypatch, COLEGA)
    pagina = Client().get("/contribuicoes").content.decode()
    assert "A escola encerrou esta tarefa para novos compromissos." in pagina


@pytest.mark.parametrize(
    "link", ["", "não é link", "javascript:alert(1)", "ftp://exemplo.test/x"]
)
def test_o_envio_exige_um_link_da_web(link):
    tarefa = _tarefa()
    _assumir(tarefa)

    with pytest.raises(ContribuicaoRecusada, match="link"):
        _enviar(tarefa, link=link)


def test_enviar_sem_ter_assumido_e_recusado():
    with pytest.raises(ContribuicaoRecusada, match="assumir"):
        _enviar(_tarefa())


# ------------------------------------------- 3. a avaliação


def test_ninguem_aceita_a_propria_contribuicao():
    """Dossiê §12: um membro não aprova a própria contribuição."""
    _semear_e_ligar()
    tarefa = _tarefa(responsavel_id=MONITOR)
    _assumir(tarefa, PROFESSORA)
    compromisso = _enviar(tarefa, PROFESSORA)

    with pytest.raises(ContribuicaoRecusada, match="própria"):
        _aceitar(compromisso, quem=PROFESSORA)

    compromisso.refresh_from_db()
    assert compromisso.estado == CompromissoDeContribuicao.Estado.ENVIADA
    assert ContribuicaoAceita.objects.count() == 0
    assert Concessao.objects.count() == 0


def test_ninguem_devolve_a_propria_contribuicao():
    tarefa = _tarefa()
    _assumir(tarefa, MONITOR)
    compromisso = _enviar(tarefa, MONITOR)

    with pytest.raises(ContribuicaoRecusada, match="própria"):
        contribuicoes.devolver(
            compromisso=compromisso,
            validador_id=MONITOR,
            motivo=CompromissoDeContribuicao.MotivoDaDevolucao.FORA_DO_CRITERIO,
            orientacao="Refaça a parte dois.",
        )


def test_aceitar_registra_o_fato_e_concede_a_medalha_com_quem_aceitou():
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    compromisso = _aceitar(_enviar(tarefa))

    assert compromisso.estado == CompromissoDeContribuicao.Estado.ACEITA
    fato = ContribuicaoAceita.objects.get()
    assert (fato.pessoa_id, fato.aceita_por) == (ALUNA, PROFESSORA)
    concessao = Concessao.objects.get()
    assert concessao.conquista.slug == MEDALHA
    assert concessao.pessoa_id == ALUNA
    assert concessao.validador_id == PROFESSORA
    assert concessao.validador_papel == Concessao.PapelDoValidador.PROFESSOR
    assert concessao.origem_event_id == contribuicoes.ORIGEM.format(id=fato.pk)
    assert LancamentoDeXP.objects.count() == 0, "reconhecimento não paga ponto"
    assert MovimentoDeCristais.objects.count() == 0, "nem crédito"


def test_reaceite_e_reentrega_nao_concedem_duas_vezes():
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    compromisso = _aceitar(_enviar(tarefa))

    with pytest.raises(ContribuicaoRecusada, match="já foi aceita"):
        _aceitar(compromisso, quem=MONITOR)
    with pytest.raises(ContribuicaoRecusada, match="já foi aceita"):
        _enviar(tarefa, link="https://exemplo.test/de-novo")

    assert ContribuicaoAceita.objects.count() == 1
    assert Concessao.objects.count() == 1


def test_a_unicidade_do_fato_mora_no_banco():
    tarefa = _tarefa()
    compromisso = _assumir(tarefa)
    linha = {
        "pessoa": compromisso.pessoa,
        "site_id": SITE,
        "compromisso": compromisso,
        "aceita_por": PROFESSORA,
    }
    ContribuicaoAceita.objects.create(**linha)

    with pytest.raises(IntegrityError), transaction.atomic():
        ContribuicaoAceita.objects.create(**linha)


def test_devolver_exige_motivo_da_lista_e_orientacao_e_nao_concede():
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    compromisso = _enviar(tarefa)

    with pytest.raises(ContribuicaoRecusada, match="motivo"):
        contribuicoes.devolver(
            compromisso=compromisso,
            validador_id=PROFESSORA,
            motivo="porque sim",
            orientacao="Refaça.",
        )
    with pytest.raises(ContribuicaoRecusada, match="orientação"):
        contribuicoes.devolver(
            compromisso=compromisso,
            validador_id=PROFESSORA,
            motivo=CompromissoDeContribuicao.MotivoDaDevolucao.FORA_DO_CRITERIO,
            orientacao="   ",
        )

    devolvida = contribuicoes.devolver(
        compromisso=compromisso,
        validador_id=PROFESSORA,
        motivo=CompromissoDeContribuicao.MotivoDaDevolucao.FORA_DO_CRITERIO,
        orientacao="Falta explicar a decisão da iluminação.",
    )

    assert devolvida.estado == CompromissoDeContribuicao.Estado.DEVOLVIDA
    assert ContribuicaoAceita.objects.count() == 0
    assert Concessao.objects.count() == 0


def test_o_banco_recusa_devolucao_sem_motivo_ou_sem_orientacao():
    compromisso = _assumir(_tarefa())
    compromisso.estado = CompromissoDeContribuicao.Estado.DEVOLVIDA

    with pytest.raises(IntegrityError), transaction.atomic():
        compromisso.save()


def test_devolvida_ajusta_reenvia_e_so_entao_e_aceita():
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    contribuicoes.devolver(
        compromisso=_enviar(tarefa),
        validador_id=PROFESSORA,
        motivo=CompromissoDeContribuicao.MotivoDaDevolucao.LINK_NAO_ABRE,
        orientacao="O link pede senha. Abra o acesso para qualquer pessoa.",
    )

    reenviada = _enviar(tarefa, link="https://exemplo.test/estudo-aberto")

    assert reenviada.estado == CompromissoDeContribuicao.Estado.ENVIADA
    assert reenviada.link == "https://exemplo.test/estudo-aberto"
    assert reenviada.motivo_da_devolucao == ""
    _aceitar(reenviada)
    assert Concessao.objects.get().conquista.slug == MEDALHA


def test_a_medalha_opcional_da_tarefa_cai_uma_vez_com_quem_aceitou():
    _semear_e_ligar()
    ConquistaDefinicao.objects.filter(site_id=SITE, slug="fundador").update(ativa=True)
    fundador = ConquistaDefinicao.objects.get(site_id=SITE, slug="fundador")
    primeira = _tarefa(medalha=fundador)
    segunda = _tarefa(medalha=fundador, titulo="Outra tarefa")

    for tarefa in (primeira, segunda):
        _assumir(tarefa)
        _aceitar(_enviar(tarefa))

    assert ContribuicaoAceita.objects.count() == 2, "duas tarefas, dois fatos"
    slugs = sorted(Concessao.objects.values_list("conquista__slug", flat=True))
    assert slugs == ["fundador", MEDALHA], "a medalha é uma só por pessoa"
    assert Concessao.objects.get(conquista=fundador).validador_id == PROFESSORA


def test_a_medalha_da_tarefa_so_pode_ser_de_concessao_manual():
    """Medalha de conta automática cai pela conta; dar por tarefa mentiria o critério."""
    _semear_e_ligar()
    ConquistaDefinicao.objects.filter(site_id=SITE, slug="mao-amiga").update(ativa=True)

    with pytest.raises(ContribuicaoRecusada, match="equipe"):
        _tarefa(medalha=ConquistaDefinicao.objects.get(site_id=SITE, slug="mao-amiga"))


def test_a_fila_da_equipe_vem_por_prazo():
    tarefa = _tarefa()
    _assumir(tarefa, ALUNA)
    _assumir(tarefa, COLEGA)
    primeiro = _enviar(tarefa, COLEGA)
    segundo = _enviar(tarefa, ALUNA)
    CompromissoDeContribuicao.objects.filter(pk=segundo.pk).update(
        prazo_ate=primeiro.prazo_ate - timedelta(days=1)
    )

    fila = list(contribuicoes.para_avaliar(SITE))

    assert [c.pk for c in fila] == [segundo.pk, primeiro.pk]


# ------------------------------------------- 4. a medalha como dado


def test_a_medalha_nasce_desligada_como_dado_e_vale_zero():
    call_command("semear_economia", "--site", SITE, stdout=StringIO())

    medalha = ConquistaDefinicao.objects.get(site_id=SITE, slug=MEDALHA)

    assert medalha.nome == "Primeira contribuição aceita"
    assert medalha.criterio == {"tipo": "contribuicoes_aceitas", "alvo": 1}
    assert medalha.familia == ConquistaDefinicao.Familia.COMUNIDADE
    assert medalha.ativa is False, "ligar é gesto do mantenedor"
    assert (medalha.pontos, medalha.cristais) == (0, 0)
    assert impedimentos_da_conquista(medalha) == []


def test_a_migracao_leva_a_medalha_a_toda_escola_ja_semeada_sem_pisar_em_edicao():
    ConquistaDefinicao.objects.create(
        slug="fundador",
        site_id="escola-em-producao",
        nome="Fundador",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.EPOCA,
        criterio={"tipo": "manual"},
    )
    ConquistaDefinicao.objects.create(
        slug=MEDALHA,
        site_id="escola-que-ja-editou",
        nome="Nome que o mantenedor escolheu",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.COMUNIDADE,
        criterio={"tipo": "contribuicoes_aceitas", "alvo": 1},
        ativa=True,
    )

    migracao.levar_a_medalha(registro_de_apps, None)
    migracao.levar_a_medalha(registro_de_apps, None)

    semeada = {linha[0]: linha for linha in CONQUISTAS}[MEDALHA]
    _, nome, descricao, classe, familia, criterio, *_, pontos, cristais = semeada
    linha = ConquistaDefinicao.objects.get(site_id="escola-em-producao", slug=MEDALHA)
    assert (linha.nome, linha.descricao, linha.criterio) == (nome, descricao, criterio)
    assert (linha.classe, linha.familia) == (classe, familia)
    assert (linha.pontos, linha.cristais, linha.ativa) == (pontos, cristais, False)
    editada = ConquistaDefinicao.objects.get(
        site_id="escola-que-ja-editou", slug=MEDALHA
    )
    assert (editada.nome, editada.ativa) == ("Nome que o mantenedor escolheu", True)


# ------------------------------------------- 5. as telas e os gestos


def test_o_aluno_assume_envia_e_ve_aguardando_com_prazo(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)
    tarefa = _tarefa()
    cliente = Client()

    resposta = cliente.post(
        "/contribuicoes/gesto", {"gesto": "assumir", "tarefa": tarefa.pk}
    )
    assert resposta.status_code == 302
    cliente.post(
        "/contribuicoes/gesto",
        {"gesto": "enviar", "tarefa": tarefa.pk, "link": "https://exemplo.test/e"},
    )

    pagina = cliente.get("/contribuicoes").content.decode()
    compromisso = CompromissoDeContribuicao.objects.get()
    assert compromisso.estado == CompromissoDeContribuicao.Estado.ENVIADA
    assert "Aguardando avaliação. A escola responde até" in pagina
    assert compromisso.prazo_ate.strftime("%d/%m/%Y") in pagina


def test_o_aluno_ve_a_devolucao_com_data_motivo_e_orientacao(monkeypatch):
    tarefa = _tarefa()
    _assumir(tarefa)
    contribuicoes.devolver(
        compromisso=_enviar(tarefa),
        validador_id=PROFESSORA,
        motivo=CompromissoDeContribuicao.MotivoDaDevolucao.FORA_DO_CRITERIO,
        orientacao="Falta explicar a decisão da iluminação.",
    )
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/contribuicoes").content.decode()

    assert "Devolvida para ajuste em" in pagina
    assert "Ainda não cumpre um dos critérios" in pagina
    assert "Falta explicar a decisão da iluminação." in pagina
    assert "Mandar de novo" in pagina


def test_o_aluno_ve_a_aceita(monkeypatch):
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    _aceitar(_enviar(tarefa))
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/contribuicoes").content.decode()

    assert "Aceita pela escola em" in pagina


def test_a_recusa_do_gesto_vira_frase_e_nunca_500(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)
    tarefa = _tarefa(vagas=1)
    _assumir(tarefa, COLEGA)

    resposta = Client().post(
        "/contribuicoes/gesto", {"gesto": "assumir", "tarefa": tarefa.pk}, follow=True
    )

    assert resposta.status_code == 200
    assert "vagas" in resposta.content.decode()


def test_o_gesto_do_aluno_nunca_alcanca_o_compromisso_de_outra_pessoa(monkeypatch):
    tarefa = _tarefa()
    _assumir(tarefa, COLEGA)
    _entrar_como(monkeypatch, ALUNA)

    Client().post("/contribuicoes/gesto", {"gesto": "desistir", "tarefa": tarefa.pk})

    assert CompromissoDeContribuicao.objects.get(pessoa_id=COLEGA).estado == (
        CompromissoDeContribuicao.Estado.ASSUMIDA
    )


def test_o_gesto_do_aluno_exige_csrf(monkeypatch):
    _entrar_como(monkeypatch, ALUNA)
    tarefa = _tarefa()

    resposta = Client(enforce_csrf_checks=True).post(
        "/contribuicoes/gesto", {"gesto": "assumir", "tarefa": tarefa.pk}
    )

    assert resposta.status_code == 403
    assert CompromissoDeContribuicao.objects.count() == 0


@pytest.mark.parametrize("quem", [None, ALUNA])
def test_so_a_equipe_abre_o_bastidor_e_publica(monkeypatch, quem):
    _entrar_como(monkeypatch, quem)

    assert Client().get("/interno/contribuicoes").status_code == 403
    resposta = Client().post(
        "/interno/contribuicoes/gesto",
        {"gesto": "publicar", "titulo": "Tarefa pirata", "vagas": 1},
    )

    assert resposta.status_code == 403
    assert TarefaComunitaria.objects.count() == 0


def test_lista_vazia_da_equipe_recusa_todo_mundo(monkeypatch):
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, "")
    _entrar_como(monkeypatch, PROFESSORA)

    assert Client().get("/interno/contribuicoes").status_code == 403


def test_a_equipe_publica_pela_tela_com_csrf(monkeypatch):
    _entrar_como(monkeypatch, PROFESSORA)
    cliente = Client(enforce_csrf_checks=True)
    cliente.get("/interno/contribuicoes")
    token = cliente.cookies["gamificacao_csrf"].value

    resposta = cliente.post(
        "/interno/contribuicoes/gesto",
        {
            "csrfmiddlewaretoken": token,
            "gesto": "publicar",
            "titulo": "Organizar uma referência técnica",
            "o_que_entregar": "Uma página com os links comentados.",
            "quem_pode": "Qualquer aluno com matrícula ativa.",
            "criterios": "Cada link tem um comentário\n\nNada de link quebrado\n",
            "responsavel_id": MONITOR,
            "responsavel_nome": "Monitor Beto",
            "vagas": "3",
        },
    )

    assert resposta.status_code == 302
    tarefa = TarefaComunitaria.objects.get()
    assert tarefa.autor_id == PROFESSORA
    assert tarefa.responsavel_id == MONITOR
    assert tarefa.criterios == ["Cada link tem um comentário", "Nada de link quebrado"]
    assert tarefa.vagas == 3 and tarefa.aberta


def test_o_responsavel_precisa_ser_da_equipe(monkeypatch):
    _entrar_como(monkeypatch, PROFESSORA)

    resposta = Client().post(
        "/interno/contribuicoes/gesto",
        {
            "gesto": "publicar",
            "titulo": "Tarefa",
            "o_que_entregar": "Algo.",
            "quem_pode": "Todos.",
            "criterios": "Um critério",
            "responsavel_id": ALUNA,
            "responsavel_nome": "Aluna",
            "vagas": "1",
        },
        follow=True,
    )

    assert "equipe" in resposta.content.decode()
    assert TarefaComunitaria.objects.count() == 0


def test_a_equipe_ve_a_fila_com_responsavel_e_prazo_e_devolve(monkeypatch):
    tarefa = _tarefa()
    _assumir(tarefa)
    compromisso = _enviar(tarefa)
    _entrar_como(monkeypatch, MONITOR)
    cliente = Client()

    pagina = cliente.get("/interno/contribuicoes").content.decode()
    assert "Estudo de caso de uma peça de Roblox" in pagina
    assert "Responde: Professora Ana" in pagina
    assert compromisso.prazo_ate.strftime("%d/%m/%Y") in pagina
    assert "https://exemplo.test/estudo" in pagina

    cliente.post(
        "/interno/contribuicoes/gesto",
        {
            "gesto": "devolver",
            "compromisso": compromisso.pk,
            "motivo": CompromissoDeContribuicao.MotivoDaDevolucao.FORA_DO_ENTREGAVEL,
            "orientacao": "A tarefa pede um documento; veio um vídeo.",
        },
    )

    compromisso.refresh_from_db()
    assert compromisso.estado == CompromissoDeContribuicao.Estado.DEVOLVIDA
    assert compromisso.decidida_por == MONITOR


def test_a_equipe_aceita_pela_tela(monkeypatch):
    _semear_e_ligar()
    tarefa = _tarefa()
    _assumir(tarefa)
    compromisso = _enviar(tarefa)
    _entrar_como(monkeypatch, MONITOR)

    Client().post(
        "/interno/contribuicoes/gesto",
        {"gesto": "aceitar", "compromisso": compromisso.pk},
    )

    assert Concessao.objects.get().validador_id == MONITOR


def test_a_fila_de_uma_escola_nao_alcanca_a_contribuicao_de_outra(monkeypatch):
    tarefa = _tarefa(site_id="outra-escola")
    compromisso = _assumir(tarefa)
    compromisso = _enviar(tarefa)
    _entrar_como(monkeypatch, PROFESSORA)

    Client().post(
        "/interno/contribuicoes/gesto",
        {"gesto": "aceitar", "compromisso": compromisso.pk},
    )

    compromisso.refresh_from_db()
    assert compromisso.estado == CompromissoDeContribuicao.Estado.ENVIADA


def test_a_equipe_encerra_e_reabre(monkeypatch):
    tarefa = _tarefa()
    _entrar_como(monkeypatch, PROFESSORA)

    Client().post(
        "/interno/contribuicoes/gesto", {"gesto": "encerrar", "tarefa": tarefa.pk}
    )
    tarefa.refresh_from_db()
    assert tarefa.aberta is False

    Client().post(
        "/interno/contribuicoes/gesto", {"gesto": "reabrir", "tarefa": tarefa.pk}
    )
    tarefa.refresh_from_db()
    assert tarefa.aberta is True


def test_a_fila_de_marcos_leva_ao_bastidor_das_contribuicoes(monkeypatch):
    _entrar_como(monkeypatch, PROFESSORA)

    pagina = Client().get("/interno").content.decode()

    assert 'href="/interno/contribuicoes"' in pagina


def test_nenhuma_tela_do_aluno_mostra_ranking_nem_contagem_de_outros(monkeypatch):
    tarefa = _tarefa(vagas=5)
    _assumir(tarefa, COLEGA)
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/contribuicoes").content.decode()

    assert COLEGA not in pagina
    assert "1 de 5" not in pagina
    assert "Há vaga" in pagina
