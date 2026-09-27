"""O rastro de cada reconhecimento (dossiê da Comunidade §5 e §12).

"Cada reconhecimento deverá registrar origem, evidência, avaliador, data e
versão dos critérios. Uma correção posterior preserva o histórico." Até aqui a
concessão guardava quem validou e quando, e nada da regra: mudar o critério de
uma medalha apagava a resposta de "sob que regra ela foi dada?".

O QUE ESTE ARQUIVO TRAVA:

1. **A concessão guarda a regra do dia**: a versão, uma cópia do critério e a
   frase dele, e a referência da origem, nunca o texto da prova privada.
2. **Mudar o critério sobe a versão**, por qualquer caminho, e a concessão
   antiga continua dizendo a regra antiga.
3. **Revogar, corrigir e restaurar são gestos da equipe, com motivo**, e cada
   um vira uma linha nova no histórico. A concessão nunca é apagada, e o
   histórico não se edita nem se apaga (quem recusa é o banco).
4. **Revogar estorna o XP por linha negativa**, não reabre concessão
   automática, e a reentrega do mesmo evento continua sem duplicar.
5. **As telas contam a história**: a medalha retirada não aparece como
   conquistada, e diz que existiu.
"""

from __future__ import annotations

import importlib

import pytest
from django.db import DatabaseError, transaction
from django.test import Client

from apps.core import equipe as porta_da_equipe
from apps.core.api import _conquistas_por_pessoa
from apps.gamificacao import contribuicoes
from apps.gamificacao.criterios import _valor_familia, avaliar
from apps.gamificacao.models import (
    Concessao,
    ConquistaDefinicao,
    HistoricoDaConcessao,
    LancamentoDeXP,
    PedidoDeValidacao,
    PerfilJogador,
    Pessoa,
)
from apps.gamificacao.validacao import (
    ValidacaoRecusada,
    aceitar,
    conceder,
    corrigir,
    marcos_da_pessoa,
    pedir_validacao,
    restaurar,
    revogar,
)

pytestmark = pytest.mark.django_db

SITE = "site-de-teste"
ALUNA = "pes-aluna"
COLEGA = "pes-colega"
PROFESSORA = "pes-professora"

Estado = Concessao.Estado
Gesto = HistoricoDaConcessao.Gesto

migracao = importlib.import_module(
    "apps.gamificacao.migrations.0009_rastro_do_reconhecimento"
)


@pytest.fixture(autouse=True)
def site_e_sessao(monkeypatch):
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, PROFESSORA)
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False


def _entrar_como(monkeypatch, pessoa_id: str | None):
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: pessoa_id)


def _pessoa(pessoa_id: str = ALUNA) -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=pessoa_id, defaults={"email": f"{pessoa_id}@exemplo.test"}
    )
    return pessoa


def _mao_amiga(**campos) -> ConquistaDefinicao:
    dados = {
        "site_id": SITE,
        "slug": "mao-amiga",
        "nome": "Mão amiga",
        "classe": ConquistaDefinicao.Classe.MEDALHA,
        "familia": ConquistaDefinicao.Familia.COMUNIDADE,
        "criterio": {"tipo": "respostas_aceitas", "alvo": 5},
        "pontos": 40,
        "ativa": True,
    }
    dados.update(campos)
    return ConquistaDefinicao.objects.create(**dados)


def _marco() -> ConquistaDefinicao:
    return ConquistaDefinicao.objects.create(
        site_id=SITE,
        slug="primeiro-cliente",
        nome="Primeiro cliente",
        classe=ConquistaDefinicao.Classe.MARCO,
        familia=ConquistaDefinicao.Familia.CARREIRA,
        ativa=True,
    )


def _conceder(conquista, pessoa_id=ALUNA, origem="evt-1") -> Concessao:
    concessao, _ = conceder(
        pessoa=_pessoa(pessoa_id),
        site_id=SITE,
        conquista=conquista,
        origem_event_id=origem,
    )
    return concessao


def _xp(pessoa_id=ALUNA) -> int:
    return PerfilJogador.objects.get(pessoa_id=pessoa_id, site_id=SITE).xp_total


# ------------------------------------------- 1. a regra do dia na concessão


def test_a_concessao_guarda_versao_copia_e_frase_do_criterio_e_a_origem():
    concessao = _conceder(_mao_amiga(), origem="evt-da-quinta-ajuda")

    concessao.refresh_from_db()
    assert concessao.criterio_versao == 1
    assert concessao.criterio == {"tipo": "respostas_aceitas", "alvo": 5}
    assert concessao.criterio_em_texto == (
        "Ter 5 respostas suas aceitas no fórum como as que resolveram a dúvida."
    )
    assert concessao.origem_event_id == "evt-da-quinta-ajuda"
    assert concessao.estado == Estado.CONCEDIDA


def test_a_concessao_nasce_com_a_primeira_linha_do_historico():
    concessao = _conceder(_mao_amiga(), origem="evt-9")

    (linha,) = concessao.historico.all()
    assert linha.gesto == Gesto.CONCEDIDA
    assert linha.estado_anterior == ""
    assert linha.estado_novo == Estado.CONCEDIDA
    assert linha.origem_nova == "evt-9"
    assert linha.registrado_em == concessao.concedida_em


def test_mudar_o_criterio_sobe_a_versao_e_nao_muda_a_concessao_antiga():
    medalha = _mao_amiga()
    antiga = _conceder(medalha, ALUNA)

    medalha.criterio = {"tipo": "respostas_aceitas", "alvo": 10}
    medalha.save()
    nova = _conceder(medalha, COLEGA, origem="evt-2")

    medalha.refresh_from_db()
    antiga.refresh_from_db()
    assert medalha.versao == 2
    assert antiga.criterio_versao == 1
    assert antiga.criterio == {"tipo": "respostas_aceitas", "alvo": 5}
    assert "Ter 5 respostas" in antiga.criterio_em_texto
    assert nova.criterio_versao == 2
    assert nova.criterio == {"tipo": "respostas_aceitas", "alvo": 10}


def test_a_versao_sobe_por_qualquer_caminho_ate_um_update_direto():
    medalha = _mao_amiga()

    ConquistaDefinicao.objects.filter(pk=medalha.pk).update(
        criterio={"tipo": "respostas_aceitas", "alvo": 7}
    )

    medalha.refresh_from_db()
    assert medalha.versao == 2


def test_salvar_sem_mudar_o_criterio_nao_gasta_versao():
    medalha = _mao_amiga()

    medalha.nome = "Mão amiga da escola"
    medalha.save()

    medalha.refresh_from_db()
    assert medalha.versao == 1


def test_o_marco_aceito_aponta_para_o_pedido_e_nunca_carrega_a_prova():
    marco = _marco()
    pedido = pedir_validacao(
        pessoa=_pessoa(),
        site_id=SITE,
        conquista=marco,
        evidencia="print do pix de R$ 300 do cliente Fulano",
    )

    concessao = aceitar(
        pedido=pedido,
        validador_id=PROFESSORA,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
    )

    concessao.refresh_from_db()
    assert concessao.origem_event_id == f"pedido:{pedido.pk}"
    guardado = f"{concessao.origem_event_id} {concessao.criterio} {concessao.criterio_em_texto}"
    assert "Fulano" not in guardado
    assert "Fulano" not in " ".join(
        f"{h.origem_nova} {h.motivo}" for h in concessao.historico.all()
    )


def test_a_contribuicao_aceita_deixa_a_regra_e_a_origem_na_medalha():
    medalha = ConquistaDefinicao.objects.create(
        site_id=SITE,
        slug="primeira-contribuicao",
        nome="Primeira contribuição aceita",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.COMUNIDADE,
        criterio={"tipo": "contribuicoes_aceitas", "alvo": 1},
        ativa=True,
    )
    tarefa = contribuicoes.publicar(
        site_id=SITE,
        autor_id=PROFESSORA,
        titulo="Organizar os erros de UV",
        o_que_entregar="Um tópico com os cinco erros.",
        quem_pode="Qualquer aluno.",
        criterios=["Um exemplo por erro"],
        responsavel_id=PROFESSORA,
        responsavel_nome="Professora Ana",
        vagas=1,
    )
    contribuicoes.assumir(tarefa=tarefa, pessoa=_pessoa(), categoria="aluno")
    compromisso = contribuicoes.enviar(
        tarefa=tarefa, pessoa=_pessoa(), link="https://exemplo.test/uv"
    )
    contribuicoes.aceitar(compromisso=compromisso, validador_id=PROFESSORA)

    concessao = Concessao.objects.get(conquista=medalha)
    assert concessao.origem_event_id == f"contribuicao:{compromisso.aceite.pk}"
    assert concessao.criterio == {"tipo": "contribuicoes_aceitas", "alvo": 1}
    assert concessao.criterio_versao == 1
    assert concessao.validador_id == PROFESSORA


# ------------------------------------------- 2. revogar


def test_revogar_exige_motivo_e_nao_muda_nada_sem_ele():
    concessao = _conceder(_mao_amiga())

    with pytest.raises(ValidacaoRecusada, match="motivo"):
        revogar(concessao=concessao, quem_id=PROFESSORA, motivo="   ")

    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA
    assert concessao.historico.count() == 1


def test_revogar_preserva_a_linha_e_escreve_o_historico_com_quem_e_motivo():
    concessao = _conceder(_mao_amiga())

    revogar(
        concessao=concessao,
        quem_id=PROFESSORA,
        motivo="As respostas eram da mesma conversa, contadas duas vezes.",
    )

    concessao = Concessao.objects.get(pk=concessao.pk)
    assert concessao.estado == Estado.REVOGADA
    assert concessao.criterio_versao == 1
    concedida, revogada = concessao.historico.order_by("id")
    assert concedida.gesto == Gesto.CONCEDIDA
    assert revogada.gesto == Gesto.REVOGADA
    assert revogada.quem_id == PROFESSORA
    assert revogada.estado_anterior == Estado.CONCEDIDA
    assert revogada.estado_novo == Estado.REVOGADA
    assert revogada.motivo.startswith("As respostas eram")
    assert revogada.registrado_em >= concedida.registrado_em


def test_revogar_estorna_o_xp_com_linha_negativa_e_recalcula_o_perfil():
    concessao = _conceder(_mao_amiga(pontos=40))
    assert _xp() == 40

    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Concedida por engano.")

    linhas = sorted(
        LancamentoDeXP.objects.filter(pessoa_id=ALUNA).values_list("pontos", flat=True)
    )
    assert linhas == [-40, 40]
    assert _xp() == 0


def test_revogar_de_novo_e_recusado_e_nao_estorna_duas_vezes():
    concessao = _conceder(_mao_amiga(pontos=40))
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Engano.")

    with pytest.raises(ValidacaoRecusada, match="já foi retirada"):
        revogar(concessao=concessao, quem_id=PROFESSORA, motivo="De novo.")

    assert LancamentoDeXP.objects.filter(pessoa_id=ALUNA, pontos__lt=0).count() == 1


def test_revogar_nao_reabre_a_conta_automatica_nem_a_reentrega():
    from apps.gamificacao.models import AjudaAceita
    from django.utils import timezone

    medalha = _mao_amiga(criterio={"tipo": "respostas_aceitas", "alvo": 1})
    AjudaAceita.objects.create(
        pessoa=_pessoa(),
        site_id=SITE,
        mensagem_id="m1",
        topico_id="t1",
        marcada_por="autor",
        occurred_at=timezone.now(),
    )
    (concessao,) = avaliar(ALUNA, SITE, origem_event_id="evt-ajuda")
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Ajuda combinada.")

    assert avaliar(ALUNA, SITE, origem_event_id="evt-ajuda") == []
    _, nova = conceder(
        pessoa=_pessoa(), site_id=SITE, conquista=medalha, origem_event_id="evt-ajuda"
    )

    assert nova is False
    assert Concessao.objects.filter(conquista=medalha).count() == 1
    assert Concessao.objects.get(conquista=medalha).estado == Estado.REVOGADA


def test_ninguem_mexe_na_propria_medalha():
    concessao = _conceder(_mao_amiga(), pessoa_id=PROFESSORA)

    with pytest.raises(ValidacaoRecusada, match="própria"):
        revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Quero tirar.")


def test_a_medalha_revogada_nao_conta_na_familia():
    concessao = _conceder(_mao_amiga())
    perfil = PerfilJogador.objects.get(pessoa_id=ALUNA, site_id=SITE)
    assert _valor_familia(_pessoa(), SITE, perfil, "comunidade") == 1

    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Engano.")

    assert _valor_familia(_pessoa(), SITE, perfil, "comunidade") == 0


def test_o_quadro_do_mantenedor_nao_lista_a_medalha_revogada():
    concessao = _conceder(_mao_amiga())
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Engano.")

    assert _conquistas_por_pessoa(SITE, [ALUNA]) == {}


# ------------------------------------------- 3. restaurar e corrigir


def test_restaurar_volta_o_estado_anterior_e_devolve_o_xp():
    concessao = _conceder(_mao_amiga(pontos=40))
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Engano.")

    restaurar(
        concessao=concessao, quem_id=PROFESSORA, motivo="Conferido: as ajudas valem."
    )

    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA
    assert [h.gesto for h in concessao.historico.order_by("id")] == [
        Gesto.CONCEDIDA,
        Gesto.REVOGADA,
        Gesto.RESTAURADA,
    ]
    assert _xp() == 40


def test_so_se_restaura_o_que_foi_retirado():
    concessao = _conceder(_mao_amiga())

    with pytest.raises(ValidacaoRecusada, match="não foi retirada"):
        restaurar(concessao=concessao, quem_id=PROFESSORA, motivo="Nada.")


def test_corrigir_troca_a_origem_e_a_antiga_fica_no_historico():
    concessao = _conceder(_mao_amiga(), origem="contribuicao:12")

    corrigir(
        concessao=concessao,
        quem_id=PROFESSORA,
        origem_nova="contribuicao:15",
        motivo="A contribuição aceita era a 15; a 12 foi de outra tarefa.",
    )

    concessao.refresh_from_db()
    assert concessao.estado == Estado.CORRIGIDA
    assert concessao.origem_event_id == "contribuicao:15"
    correcao = concessao.historico.get(gesto=Gesto.CORRIGIDA)
    assert correcao.origem_anterior == "contribuicao:12"
    assert correcao.origem_nova == "contribuicao:15"
    assert correcao.quem_id == PROFESSORA


@pytest.mark.parametrize(
    ("origem_nova", "motivo", "trecho"),
    [
        ("", "Troca.", "referência"),
        ("contribuicao:12", "Troca.", "mesma"),
        ("contribuicao:15", "", "motivo"),
        ("x" * 65, "Troca.", "64"),
    ],
)
def test_corrigir_recusa_o_que_nao_corrige_nada(origem_nova, motivo, trecho):
    concessao = _conceder(_mao_amiga(), origem="contribuicao:12")

    with pytest.raises(ValidacaoRecusada, match=trecho):
        corrigir(
            concessao=concessao,
            quem_id=PROFESSORA,
            origem_nova=origem_nova,
            motivo=motivo,
        )

    assert concessao.historico.count() == 1


def test_a_medalha_retirada_nao_se_corrige():
    concessao = _conceder(_mao_amiga())
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Engano.")

    with pytest.raises(ValidacaoRecusada, match="retirada"):
        corrigir(
            concessao=concessao,
            quem_id=PROFESSORA,
            origem_nova="evt-2",
            motivo="Troca.",
        )


# ------------------------------------------- 4. o banco guarda a história


def test_o_historico_nao_se_apaga():
    concessao = _conceder(_mao_amiga())

    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            HistoricoDaConcessao.objects.filter(concessao=concessao).delete()

    assert concessao.historico.count() == 1


def test_o_historico_nao_se_edita():
    concessao = _conceder(_mao_amiga())

    with pytest.raises(DatabaseError, match="append-only"):
        with transaction.atomic():
            HistoricoDaConcessao.objects.filter(concessao=concessao).update(
                motivo="reescrito"
            )


def test_a_concessao_nunca_e_apagada_nem_por_sql_solto():
    from django.db import connection

    concessao = _conceder(_mao_amiga())

    with pytest.raises(DatabaseError, match="nunca"):
        with transaction.atomic(), connection.cursor() as cursor:
            cursor.execute(
                "DELETE FROM gamificacao_concessao WHERE id = %s", [concessao.pk]
            )

    assert Concessao.objects.filter(pk=concessao.pk).exists()


def test_a_migracao_da_historia_as_concessoes_que_ja_existiam():
    from django.apps import apps as registro

    antiga = Concessao.objects.create(
        pessoa=_pessoa(),
        site_id=SITE,
        conquista=_mao_amiga(),
        origem_event_id="evt-antigo",
    )

    migracao.dar_historia_ao_que_ja_existia(registro, None)
    migracao.dar_historia_ao_que_ja_existia(registro, None)

    (linha,) = antiga.historico.all()
    assert linha.gesto == Gesto.CONCEDIDA
    assert linha.estado_novo == Estado.CONCEDIDA
    assert linha.origem_nova == "evt-antigo"
    assert linha.registrado_em == antiga.concedida_em
    assert antiga.criterio_versao is None


# ------------------------------------------- 5. as telas


def test_a_tela_de_medalhas_diz_a_regra_e_a_versao_da_conquista(monkeypatch):
    medalha = _mao_amiga()
    _conceder(medalha)
    medalha.criterio = {"tipo": "respostas_aceitas", "alvo": 10}
    medalha.save()
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/medalhas").content.decode()

    assert "Como ganhar:</strong> Ter 10 respostas" in pagina
    assert "Concedida pela regra da versão 1: Ter 5 respostas" in pagina


def test_a_medalha_retirada_nao_aparece_como_conquistada(monkeypatch):
    concessao = _conceder(_mao_amiga())
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Concedida por engano.")
    _entrar_como(monkeypatch, ALUNA)

    pagina = Client().get("/medalhas").content.decode()

    assert "Conquistada em" not in pagina
    assert "medalha conquistada" not in pagina
    assert "Retirada pela equipe em" in pagina
    assert "Concedida por engano." in pagina


def test_o_marco_retirado_diz_que_existiu_e_nao_pede_prova_de_novo(monkeypatch):
    marco = _marco()
    concessao, _ = conceder(
        pessoa=_pessoa(),
        site_id=SITE,
        conquista=marco,
        validador_id=PROFESSORA,
        validador_papel=Concessao.PapelDoValidador.PROFESSOR,
        origem_event_id="pedido:1",
    )
    revogar(concessao=concessao, quem_id=PROFESSORA, motivo="Cliente não confirmou.")

    (linha,) = marcos_da_pessoa(_pessoa(), SITE)
    assert linha["estado"] == "revogado"
    with pytest.raises(ValidacaoRecusada, match="retirou"):
        pedir_validacao(pessoa=_pessoa(), site_id=SITE, conquista=marco)

    _entrar_como(monkeypatch, ALUNA)
    pagina = Client().get("/marcos").content.decode()
    assert "Retirado pela equipe em" in pagina
    assert "Cliente não confirmou." in pagina


@pytest.mark.parametrize("quem", [None, ALUNA])
def test_so_a_equipe_ve_os_reconhecimentos_e_mexe_neles(monkeypatch, quem):
    concessao = _conceder(_mao_amiga())
    _entrar_como(monkeypatch, quem)

    assert Client().get("/interno/reconhecimentos").status_code == 403
    resposta = Client().post(
        "/interno/reconhecimentos/gesto",
        {"gesto": "revogar", "concessao": concessao.pk, "motivo": "Pirata."},
    )

    assert resposta.status_code == 403
    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA


def test_o_gesto_da_equipe_exige_csrf(monkeypatch):
    concessao = _conceder(_mao_amiga())
    _entrar_como(monkeypatch, PROFESSORA)

    resposta = Client(enforce_csrf_checks=True).post(
        "/interno/reconhecimentos/gesto",
        {"gesto": "revogar", "concessao": concessao.pk, "motivo": "Sem token."},
    )

    assert resposta.status_code == 403
    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA


def test_a_equipe_ve_o_rastro_e_revoga_pela_tela(monkeypatch):
    concessao = _conceder(_mao_amiga(), origem="evt-da-quinta-ajuda")
    _entrar_como(monkeypatch, PROFESSORA)
    cliente = Client(enforce_csrf_checks=True)

    pagina = cliente.get("/interno/reconhecimentos").content.decode()
    assert "Mão amiga" in pagina
    assert ALUNA in pagina
    assert "evt-da-quinta-ajuda" in pagina
    assert "versão 1" in pagina
    assert "Ter 5 respostas" in pagina

    token = cliente.cookies["gamificacao_csrf"].value
    resposta = cliente.post(
        "/interno/reconhecimentos/gesto",
        {
            "csrfmiddlewaretoken": token,
            "gesto": "revogar",
            "concessao": concessao.pk,
            "motivo": "Ajudas contadas duas vezes.",
        },
    )

    assert resposta.status_code == 302
    concessao.refresh_from_db()
    assert concessao.estado == Estado.REVOGADA
    depois = cliente.get(resposta["Location"]).content.decode()
    assert "Retirada. A história ficou guardada." in depois
    assert "Ajudas contadas duas vezes." in depois


def test_a_recusa_volta_para_a_tela_em_portugues(monkeypatch):
    concessao = _conceder(_mao_amiga())
    _entrar_como(monkeypatch, PROFESSORA)

    resposta = Client().post(
        "/interno/reconhecimentos/gesto",
        {"gesto": "revogar", "concessao": concessao.pk, "motivo": ""},
        follow=True,
    )

    assert resposta.status_code == 200
    assert "motivo" in resposta.content.decode()
    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA


def test_a_equipe_filtra_por_pessoa_e_a_lista_vazia_explica(monkeypatch):
    _conceder(_mao_amiga(), ALUNA)
    _entrar_como(monkeypatch, PROFESSORA)

    pagina = (
        Client().get("/interno/reconhecimentos?pessoa=pes-ninguem").content.decode()
    )

    assert "Mão amiga" not in pagina
    assert "Nenhum reconhecimento" in pagina


def test_concessao_de_outra_escola_nao_existe_para_o_gesto(monkeypatch):
    medalha = _mao_amiga(site_id="outra-escola")
    concessao, _ = conceder(
        pessoa=_pessoa(), site_id="outra-escola", conquista=medalha, origem_event_id="e"
    )
    _entrar_como(monkeypatch, PROFESSORA)

    Client().post(
        "/interno/reconhecimentos/gesto",
        {"gesto": "revogar", "concessao": concessao.pk, "motivo": "De fora."},
    )

    concessao.refresh_from_db()
    assert concessao.estado == Estado.CONCEDIDA
