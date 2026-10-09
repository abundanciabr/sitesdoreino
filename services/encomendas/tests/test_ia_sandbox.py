from contextlib import nullcontext
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.utils import timezone

from apps.core import ia_sandbox
from apps.encomendas.models import MensagemSandbox, ParticipacaoSandbox, ProjetoSandbox


@pytest.fixture
def participacao(db):
    projeto = ProjetoSandbox.objects.create(
        site_id="escola-a", slug="arte", titulo="Arte de prática",
        briefing="Desenhe uma árvore.", referencias=["foto de uma árvore"],
        entregaveis=["imagem PNG"], criterios="Tronco visível.",
    )
    return ParticipacaoSandbox.objects.create(
        site_id="escola-a", pessoa_id="aluno-1", projeto=projeto,
        termos={"prazo_dias": 3, "recompensa": "5", "titulo": "Arte de prática",
                "briefing": "Desenhe uma árvore.", "referencias": ["foto de uma árvore"],
                "entregaveis": ["imagem PNG"], "criterios": "Tronco visível."},
        aceite_em=timezone.now(), prazo_ate=timezone.now() + timedelta(days=3),
    )


@pytest.mark.django_db
def test_orienta_com_retrato_e_historico_sem_alterar_condicoes(participacao, monkeypatch):
    MensagemSandbox.objects.create(
        site_id="escola-a", participacao=participacao, ator_id="aluno-1", papel="aluno",
        texto="Como faço o tronco?",
    )
    captura = {}

    def consulta(retrato, historico):
        captura.update(retrato=retrato, historico=historico)
        return "Comece por um cilindro simples para o tronco."

    monkeypatch.setattr(ia_sandbox, "_consultar_modelo", consulta)
    resposta = ia_sandbox.responder(participacao)
    repetida = ia_sandbox.responder(participacao)
    participacao.refresh_from_db()

    assert resposta.pk == repetida.pk
    assert resposta.papel == "ia"
    assert resposta.ator_id == ia_sandbox.ATOR_IA
    assert "cilindro" in resposta.texto
    assert captura["retrato"]["termos_aceitos"] == participacao.termos
    assert captura["retrato"]["projeto"]["briefing"] == "Desenhe uma árvore."
    assert captura["retrato"]["projeto"]["criterios"] == "Tronco visível."
    assert captura["historico"][-1]["texto"] == "Como faço o tronco?"
    assert participacao.status == "em_producao"
    assert participacao.termos["recompensa"] == "5"
    assert not participacao.aprovado_em


@pytest.mark.django_db
def test_briefing_editado_nao_substitui_snapshot_aceito(participacao, monkeypatch):
    projeto = participacao.projeto
    projeto.briefing = "Briefing posterior diferente."
    projeto.save(update_fields=["briefing"])
    MensagemSandbox.objects.create(site_id="escola-a", participacao=participacao, ator_id="aluno-1",
                                   papel="aluno", texto="Qual é a tarefa?")
    vistos = {}

    def consulta(retrato, _historico):
        vistos.update(retrato)
        return "A tarefa aceita é desenhar uma árvore."

    monkeypatch.setattr(ia_sandbox, "_consultar_modelo", consulta)
    ia_sandbox.responder(participacao)
    assert vistos["projeto"]["briefing"] == "Desenhe uma árvore."


@pytest.mark.django_db
def test_falha_explicita_preserva_mensagem_do_aluno(participacao, monkeypatch):
    fala = MensagemSandbox.objects.create(
        site_id="escola-a", participacao=participacao, ator_id="aluno-1", papel="aluno",
        texto="Pode aprovar minha entrega?",
    )

    def falha(*_args):
        raise RuntimeError("segredo que não pode aparecer")

    monkeypatch.setattr(ia_sandbox, "_consultar_modelo", falha)
    resposta = ia_sandbox.responder(participacao)

    assert MensagemSandbox.objects.filter(pk=fala.pk).exists()
    assert "indisponível" in resposta.texto
    assert "escola" in resposta.texto
    assert "segredo" not in resposta.texto
    assert ParticipacaoSandbox.objects.get(pk=participacao.pk).status == "em_producao"


def test_executor_existente_recebe_prompt_sem_ferramentas(monkeypatch):
    chamadas = {}

    def responder_modelo(**kwargs):
        chamadas.update(kwargs)
        return SimpleNamespace(completa=True, chamadas=[], texto="Tente primeiro um esboço.")

    executor = SimpleNamespace(
        autorizacao_ativa=lambda: SimpleNamespace(pk=7),
        conexao=lambda: SimpleNamespace(modelo_rapido="modelo-configurado"),
        responder=responder_modelo,
    )
    real_import = ia_sandbox.importlib.import_module

    def importar(nome):
        if nome == "config.runtime":
            return SimpleNamespace(serving=lambda _servico: nullcontext())
        if nome == "modules.admin.apps.agentes.modelo":
            return executor
        return real_import(nome)

    monkeypatch.setattr(ia_sandbox.importlib, "import_module", importar)
    texto = ia_sandbox._consultar_modelo(
        {"termos_aceitos": {"prazo": "amanhã"}, "projeto": {"briefing": "Árvore"}},
        [{"papel": "aluno", "texto": "Por onde começo?"}],
    )

    assert texto == "Tente primeiro um esboço."
    assert chamadas["modelo"] == "modelo-configurado"
    assert chamadas["autorizacao_id"] == 7
    assert chamadas["ferramentas"] is None
    assert "Não aprove entregas" in chamadas["instrucoes"]
    assert "prazo" in chamadas["itens"][0]["content"]
