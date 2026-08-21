# tests/test_inv_pontuacao_servidor_e_outbox.py  # [RECEITA:R5 v1]
# [INV] pontuação calculada só no servidor; emissão de quiz.completado.v1 é
# transacional (outbox), e o envelope emitido bate com o contrato congelado.
import json
from pathlib import Path

import jsonschema
import pytest

from apps.quiz.models import Option, OutboxEvent, Question, Quiz, Submission
from tests.test_smoke import HOST_A, quiz_a, site_a, site_b  # noqa: F401 (fixtures)

pytestmark = pytest.mark.django_db

CONTRATO = json.loads(
    (
        Path(__file__).resolve().parents[3]
        / "contracts"
        / "eventos"
        / "quiz.completado.v1.json"
    ).read_text(encoding="utf-8")
)


def test_cliente_nao_pode_enviar_pontuacao_o_servidor_recalcula(client, quiz_a):
    pergunta = quiz_a.questions.get(order=1)
    opcao_zero = pergunta.options.get(points=0)

    resp = client.post(
        f"/quiz/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": opcao_zero.id,
            "score": "999",  # tentativa de injetar pontuação direto no payload
            "email": "lead@exemplo.com",
        },
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 302
    submissao = Submission.objects.get()
    assert submissao.score == 0  # veio da OPÇÃO escolhida, nunca do payload
    assert submissao.result_key == "baixo"


def test_opcao_que_nao_pertence_a_pergunta_e_rejeitada(client, quiz_a, site_b):
    outro_quiz = Quiz.objects.create(site=site_b, slug="outro", title="Outro")
    outra_pergunta = Question.objects.create(quiz=outro_quiz, order=1, text="X")
    opcao_de_fora = Option.objects.create(
        question=outra_pergunta, order=1, text="Y", points=999
    )

    pergunta = quiz_a.questions.get(order=1)
    resp = client.post(
        f"/quiz/{quiz_a.slug}/",
        {f"pergunta_{pergunta.id}": opcao_de_fora.id, "email": "lead@exemplo.com"},
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 404
    assert Submission.objects.count() == 0


def test_evento_vai_para_outbox_na_mesma_transacao_do_resultado(client, quiz_a):
    pergunta = quiz_a.questions.get(order=1)
    opcao_dez = pergunta.options.get(points=10)

    resp = client.post(
        f"/quiz/{quiz_a.slug}/",
        {f"pergunta_{pergunta.id}": opcao_dez.id, "email": "lead@exemplo.com"},
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 302

    eventos = OutboxEvent.objects.filter(event="quiz.completado")
    assert eventos.count() == 1  # [INV-P6]
    submissao = Submission.objects.get()
    dados = eventos.get().payload
    assert dados["site_id"] == submissao.site_id
    assert dados["quiz_slug"] == quiz_a.slug
    assert dados["result_key"] == submissao.result_key
    assert dados["score"] == submissao.score
    assert dados["lead"]["email"] == "lead@exemplo.com"


def test_envelope_do_evento_valida_contra_o_contrato_congelado(client, quiz_a):
    pergunta = quiz_a.questions.get(order=1)
    opcao_dez = pergunta.options.get(points=10)

    resp = client.post(
        f"/quiz/{quiz_a.slug}/",
        {
            f"pergunta_{pergunta.id}": opcao_dez.id,
            "email": "lead@exemplo.com",
            "nome": "Lead",
            "telefone": "11999999999",
        },
        HTTP_HOST=HOST_A,
    )
    assert resp.status_code == 302

    ev = OutboxEvent.objects.get(event="quiz.completado")
    envelope = {
        "event": ev.event,
        "version": ev.version,
        "event_id": str(ev.event_id),
        "occurred_at": ev.occurred_at.isoformat(),
        "data": ev.payload,
    }
    jsonschema.validate(
        instance=envelope, schema=CONTRATO, format_checker=jsonschema.FormatChecker()
    )
