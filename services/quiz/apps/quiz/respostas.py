"""Respostas legíveis do quiz: o que a pessoa leu e o que ela escolheu.

`Submission.answers` e `CapturaParcial.answers` guardam só ids
({pergunta_id: opcao_id}). O CRM e os agentes precisam do texto. Como uma
versão publicada nunca é editada (o editor cria versão nova), ler os textos da
versão na hora devolve exatamente o que a pessoa viu.

Formato combinado com as outras células (CRM com agentes, onda 1):

    [{"pergunta_id": 12, "pergunta": "Qual o seu objetivo?",
      "respostas": [{"id": 40, "texto": "Vender online"}],
      "valor_livre": None}]

`respostas` é lista porque uma pergunta pode vir a aceitar mais de uma opção;
`valor_livre` existe para resposta digitada, que o quiz ainda não tem.
"""

from __future__ import annotations

from .models import OutboxEvent


def _como_int(valor):
    try:
        return int(valor)
    except (TypeError, ValueError):
        return None


def respostas_legiveis(versao, answers) -> list[dict]:
    """Perguntas respondidas, na ordem do quiz, com o texto da opção escolhida.

    Pergunta sem resposta fica de fora (captura parcial). Opção que não
    pertence mais à pergunta é ignorada em vez de inventar texto.
    """
    if not isinstance(answers, dict) or not answers:
        return []
    escolhidas = {}
    for pergunta_id, opcao_id in answers.items():
        chave = _como_int(pergunta_id)
        if chave is None:
            continue
        ids = opcao_id if isinstance(opcao_id, list) else [opcao_id]
        escolhidas[chave] = [i for i in (_como_int(x) for x in ids) if i is not None]
    saida = []
    for pergunta in versao.questions.prefetch_related("options"):
        ids = escolhidas.get(pergunta.id)
        if not ids:
            continue
        opcoes = {opcao.id: opcao.text for opcao in pergunta.options.all()}
        respostas = [{"id": i, "texto": opcoes[i]} for i in ids if i in opcoes]
        if not respostas:
            continue
        saida.append(
            {
                "pergunta_id": pergunta.id,
                "pergunta": pergunta.text,
                "respostas": respostas,
                "valor_livre": None,
            }
        )
    return saida


def lead_do_contato(email: str, nome: str, telefone: str) -> dict:
    """O bloco `lead` dos eventos do quiz: só o que veio preenchido."""
    lead = {}
    if email:
        lead["email"] = email
    if nome:
        lead["name"] = nome
    if telefone:
        lead["phone"] = telefone
    return lead


def emitir_quiz_completado(quiz, submissao) -> OutboxEvent:
    """Grava `quiz.completado` na outbox (mesma transação de quem chama).

    Campos antigos ficam como eram (consumidores atuais leem `lead`,
    `result_key`, `utm`...). Novos: `submissao_id`, `sessao`, `respostas` e,
    quando a pessoa já tinha sido capturada antes de concluir,
    `captura_parcial_id` — com ele o consumidor junta as duas coisas na mesma
    pessoa em vez de abrir outra.
    """
    from .consentimento import bloco_da_sessao
    from .models import CapturaParcial

    payload = {
        "site_id": submissao.site_id,
        "quiz_slug": quiz.slug,
        "result_key": submissao.result_key,
        "score": submissao.score,
        "version_key": submissao.version.key,
        "lead": lead_do_contato(
            submissao.lead_email, submissao.lead_name, submissao.lead_phone
        ),
        "utm": submissao.utm,
        "submissao_id": str(submissao.id),
        "sessao": str(submissao.session_id) if submissao.session_id else None,
        "respostas": respostas_legiveis(submissao.version, submissao.answers),
    }
    if submissao.context:
        payload["context"] = submissao.context
    payload["consentimento"] = bloco_da_sessao(quiz, submissao.session_id)
    if submissao.session_id:
        captura = CapturaParcial.objects.filter(
            quiz=quiz, session_id=submissao.session_id
        ).first()
        if captura is not None:
            if captura.submissao_id is None:
                captura.submissao = submissao
                captura.save(update_fields=["submissao", "atualizada_em"])
            payload["captura_parcial_id"] = str(captura.id)
    return OutboxEvent.objects.create(event="quiz.completado", payload=payload)
