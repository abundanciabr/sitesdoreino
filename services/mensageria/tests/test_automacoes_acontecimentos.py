"""Fatos reais e falas novas que chegam à Central de automações."""
from datetime import timedelta
from types import SimpleNamespace
from uuid import uuid4

import pytest
from django.utils import timezone

from apps.conversas import entrada
from apps.jornadas import central
from apps.jornadas.acontecimentos import encaminhar
from apps.jornadas.models import EnvioDeCheckpoint, OutboxEvent
from apps.eventos.management.commands.consume_eventos import processar_envelope

pytestmark = pytest.mark.django_db(transaction=True)


def _envelope(evento, dados, ator=None, event_id=None):
    return {"event": evento, "version": 1, "event_id": str(event_id or uuid4()),
            "data": dados, "ator_id": ator}


def test_eventos_enderecados_e_escopo_de_site(monkeypatch):
    chamadas = []
    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: chamadas.append(kw))
    encaminhar(_envelope("identidade.pessoa-cadastrada", {"site_id": "s1", "pessoa_id": "p1"}))
    encaminhar(_envelope("notificacao.devida", {
        "site_id": "s2", "destinatario_id": "p2", "assunto": "matricula.situacao-alterada",
        "parametros": {"situacao_nova": "ativa", "matricula_id": "m2"},
    }))
    encaminhar(_envelope("notificacao.devida", {
        "site_id": "s2", "destinatario_id": "p2", "assunto": "gamificacao.nivel-alcancado",
        "parametros": {"nivel": 2},
    }))
    encaminhar(_envelope("notificacao.devida", {
        "site_id": "s2", "destinatario_id": "p2", "assunto": "matricula.situacao-alterada",
        "parametros": {"situacao_nova": "reembolsada"},
    }))
    assert [(c["gatilho"], c["site_id"], c["destinatario_id"]) for c in chamadas] == [
        ("identidade.pessoa-cadastrada", "s1", "p1"),
        ("matricula.ativa", "s2", "p2"),
        ("gamificacao.nivel-alcancado", "s2", "p2"),
    ]
    assert chamadas[1]["contexto"]["aluno_id"] == "p2"


def test_compra_aprovada_resolve_identidade_sem_copiar_email(monkeypatch):
    chamadas = []
    from apps.jornadas import acontecimentos

    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: chamadas.append(kw))
    monkeypatch.setattr(acontecimentos.Jornada.objects, "filter",
                        lambda **kw: SimpleNamespace(exists=lambda: True))
    monkeypatch.setattr(acontecimentos, "_pessoa_do_email", lambda email: "pessoa-real")
    conversa = SimpleNamespace(id="conversa-confirmada", site_id="s1")
    monkeypatch.setattr(acontecimentos, "_conversa_da_compra",
                        lambda **kw: (conversa, "lead-confirmado"))
    encaminhar(_envelope("pagamento.aprovado", {
        "site_id": "s1", "oportunidade_ref": "op-real",
        "customer": {"email": "privado@exemplo.test"},
    }))
    assert chamadas[0]["destinatario_id"] == "pessoa-real"
    assert chamadas[0]["conversa"] is conversa
    assert chamadas[0]["contexto"]["contato_id"] == "lead-confirmado"
    assert "privado@exemplo.test" not in str(chamadas)

    monkeypatch.setattr(acontecimentos, "_pessoa_do_email", lambda email: "")
    encaminhar(_envelope("pagamento.aprovado", {
        "site_id": "s1", "oportunidade_ref": "op-real",
        "customer": {"email": "privado@exemplo.test"},
    }))
    assert chamadas[1]["destinatario_id"] == "conversa:conversa-confirmada"


def test_prontuario_enriquece_so_passagem_ativa_exata_do_site(monkeypatch):
    from apps.jornadas import acontecimentos

    for nome in ("IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN", "ALUNOS_API_URL", "ALUNOS_API_TOKEN"):
        monkeypatch.setenv(nome, "http://interno" if nome.endswith("URL") else "token-teste")
    chamadas = []

    class Resposta:
        status_code = 200

        def __init__(self, corpo):
            self.corpo = corpo

        def json(self):
            return self.corpo

    monkeypatch.setattr(acontecimentos.httpx, "post", lambda *a, **kw: Resposta({"email": "pessoa@exemplo.test"}))

    def prontuario(*args, **kwargs):
        chamadas.append((args, kwargs))
        return Resposta({"passagens": [
            {"id": "m1", "site_id": "outro", "status": "ativa", "nome_completo": "Nome alheio"},
            {"id": "m2", "site_id": "s1", "status": "ativa", "nome_completo": "Nome Real", "turma": "Turma Azul", "product_id": "produto-real"},
            {"id": "m3", "site_id": "s1", "status": "suspensa", "nome_completo": "Nome Antigo"},
        ]})

    monkeypatch.setattr(acontecimentos.httpx, "get", prontuario)
    contexto = acontecimentos._contexto_do_prontuario(site_id="s1", pessoa_id="p1", matricula_id="m2")
    assert contexto == {"aluno_id": "p1", "nome": "Nome Real", "turma": "Turma Azul", "produto_id": "produto-real"}
    assert "/alunos/pessoa%40exemplo.test/prontuario" in chamadas[0][0][0]
    assert acontecimentos._contexto_do_prontuario(site_id="s1", pessoa_id="p1", matricula_id="m1") == {}
    assert "pessoa@exemplo.test" not in str(contexto)


def test_prontuario_ambiguo_nao_atribui_turma_de_outra_passagem(monkeypatch):
    from apps.jornadas import acontecimentos

    for nome in ("IDENTIDADE_API_URL", "IDENTIDADE_API_TOKEN", "ALUNOS_API_URL", "ALUNOS_API_TOKEN"):
        monkeypatch.setenv(nome, "http://interno" if nome.endswith("URL") else "token-teste")
    resposta = lambda corpo: SimpleNamespace(status_code=200, json=lambda: corpo)
    monkeypatch.setattr(acontecimentos.httpx, "post", lambda *a, **kw: resposta({"email": "p@exemplo.test"}))
    monkeypatch.setattr(acontecimentos.httpx, "get", lambda *a, **kw: resposta({"passagens": [
        {"id": "m1", "site_id": "s1", "status": "ativa", "turma": "Uma"},
        {"id": "m2", "site_id": "s1", "status": "ativa", "turma": "Outra"},
    ]}))
    assert acontecimentos._contexto_do_prontuario(site_id="s1", pessoa_id="p1") == {}


def test_compra_usa_conversa_so_com_contato_crm_confirmado(monkeypatch):
    from apps.conversas.models import Conversa
    from apps.jornadas import acontecimentos, crm

    numero = "5511988887777"
    cliente = {"email": "comprador@exemplo.test", "phone": numero}
    dados = {"oportunidade_ref": "op-real"}
    contato = {"id": "lead-real", "site_id": "s1", "email": cliente["email"],
               "telefone": numero}
    monkeypatch.setattr(crm, "_oportunidade", lambda ref: {
        "lead_id": contato["id"], "contato": contato,
    })
    conversa, lead_id = acontecimentos._conversa_da_compra(
        site_id="s1", dados=dados, cliente=cliente)
    assert lead_id == "lead-real"
    assert (conversa.site_id, conversa.lead_id, conversa.endereco) == (
        "s1", "lead-real", numero)
    assert Conversa.objects.count() == 1

    contato["site_id"] = "outro"
    assert acontecimentos._conversa_da_compra(
        site_id="s2", dados=dados, cliente=cliente) == (None, "")
    assert Conversa.objects.count() == 1
    contato["site_id"] = "s1"
    contato["id"] = "lead-outro"
    assert acontecimentos._conversa_da_compra(
        site_id="s1", dados=dados, cliente=cliente) == (None, "")


def test_devolucao_usa_aluno_do_envio_e_forum_distingue_post_de_resposta(monkeypatch):
    chamadas = []
    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: chamadas.append(kw))
    EnvioDeCheckpoint.objects.create(site_id="s1", envio_id="e1", aula_id="a1", aluno_id="aluno")
    encaminhar(_envelope("checkpoint.devolvido", {
        "site_id": "s1", "envio_id": "e1", "aula_id": "a1"}, ator="professor"))
    encaminhar(_envelope("forum.mensagem-criada", {
        "site_id": "s1", "topico_id": "t1", "mensagem_id": "r1"}, ator="respondente"))
    encaminhar(_envelope("forum.resposta-criada", {
        "site_id": "s1", "topico_id": "t1", "destinatario_id": "autor-topico",
        "link": "https://meshcraft.top/forum/t/1#m2",
    }, ator="respondente"))
    assert [(c["gatilho"], c["destinatario_id"]) for c in chamadas] == [
        ("checkpoint.devolvido", "aluno"),
        ("forum.mensagem-criada", "respondente"),
        ("forum.resposta-criada", "autor-topico"),
    ]


def test_consumidor_deduplica_antes_da_ponte(monkeypatch):
    chamadas = []
    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: chamadas.append(kw))
    envelope = _envelope("identidade.pessoa-cadastrada", {"site_id": "s1", "pessoa_id": "p1"})
    handler = lambda data, event_id, ator_id: None
    assert processar_envelope(envelope, handler) is True
    assert processar_envelope(envelope, handler) is False
    assert len(chamadas) == 1


def test_consumidor_preserva_pk_do_curso_mas_filtra_por_produto_real(monkeypatch):
    chamadas = []
    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: chamadas.append(kw))
    dados = {
        "site_id": "s1", "curso_id": "7", "aula_id": "21",
        "produto_id": "produto-catalogo-uuid", "curso_nome": "Modelagem 3D",
        "aula_titulo": "Primeira peça", "e_boss": False,
    }
    envelope = _envelope("aula.concluida", dados, ator="aluno-real")
    assert processar_envelope(envelope, lambda data, event_id, ator_id: None) is True
    assert chamadas[0]["contexto"] == {
        "aluno_id": "aluno-real", "curso_id": "7", "aula_id": "21",
        "produto_id": "produto-catalogo-uuid", "curso": "Modelagem 3D",
        "aula": "Primeira peça", "progresso": "aula concluída",
    }
    assert processar_envelope(envelope, lambda data, event_id, ator_id: None) is False
    assert len(chamadas) == 1


def test_fala_nova_chega_a_central_historico_audio_e_repeticao_nao(monkeypatch):
    chamadas = []
    contatos = []
    monkeypatch.setattr(entrada, "_ligar", lambda *args: None)
    monkeypatch.setattr(entrada.orientacao, "apos_receber", lambda *args, **kw: None)
    monkeypatch.setattr("apps.jornadas.tasks.relay_apos_commit", lambda: None)
    monkeypatch.setattr(central, "ao_resposta", lambda mensagem: chamadas.append(mensagem.id))
    monkeypatch.setattr(central, "inscrever_evento", lambda **kw: contatos.append(kw))
    antiga = entrada.Recebida(site_id="s1", canal="whatsapp", endereco="5511999990000",
                              id_externo="audio-antigo", midia={"tipo": "audio"},
                              ocorrida_em=timezone.now() - timedelta(days=2))
    assert entrada.receber(antiga)[1] is True
    assert chamadas == []
    atual = entrada.Recebida(site_id="s1", canal="whatsapp", endereco="5511999990000",
                             id_externo="audio-atual", midia={"tipo": "audio"})
    assert entrada.receber(atual)[1] is True
    assert entrada.receber(atual)[1] is False
    assert len(chamadas) == 1
    assert len(contatos) == 1
    assert contatos[0]["gatilho"] == "mensagem.recebida"
    assert contatos[0]["destinatario_id"].startswith("conversa:")
    assert contatos[0]["conversa"].site_id == "s1"
    assert OutboxEvent.objects.filter(event="mensagem.recebida").count() == 1


def test_falha_da_ponte_nao_apaga_entrada_nem_evento(monkeypatch):
    monkeypatch.setattr(entrada, "_ligar", lambda *args: None)
    monkeypatch.setattr(entrada.orientacao, "apos_receber", lambda *args, **kw: None)
    monkeypatch.setattr("apps.jornadas.tasks.relay_apos_commit", lambda: None)
    monkeypatch.setattr(central, "ao_resposta", lambda mensagem: (_ for _ in ()).throw(RuntimeError("teste")))
    mensagem, nova = entrada.receber(entrada.Recebida(
        site_id="s1", canal="whatsapp", endereco="5511999990000", id_externo="nova"))
    assert nova is True and mensagem.pk is not None
    assert OutboxEvent.objects.filter(event="mensagem.recebida").count() == 1
