"""Captura parcial e quiz completo da mesma sessão são a mesma pessoa.

Os eventos seguem o formato do quiz (ramo quiz-respostas): a captura traz
`captura_id`, `sessao` e `lead`; o completo traz `sessao` e, quando houve
captura, `captura_parcial_id`.
"""

import uuid

import pytest

from apps.core.handlers import ao_quiz_captura_parcial, ao_quiz_completado
from apps.core.models import (
    Lead, Oportunidade, QuizDoLead, RegistroHistoricoOportunidade, TimelineEvent,
)


pytestmark = pytest.mark.django_db

SESSAO = "8d0e3c1e-1111-4a4a-9b9b-000000000001"
CAPTURA = "5f1c2d3e-2222-4b4b-8c8c-000000000002"
RESPOSTAS = [
    {"pergunta_id": 1, "pergunta": "Quanto tempo você tem por semana?",
     "respostas": [{"id": 2, "texto": "Menos de 2 horas"}], "valor_livre": None},
]


def captura(email="", telefone="", nome="Maria", sessao=SESSAO, captura_id=CAPTURA,
            slug="crivo", site="a"):
    lead = {}
    if email:
        lead["email"] = email
    if nome:
        lead["name"] = nome
    if telefone:
        lead["phone"] = telefone
    event_id = str(uuid.uuid4())
    ao_quiz_captura_parcial(event_id, {
        "captura_id": captura_id, "site_id": site, "sessao": sessao, "quiz_slug": slug,
        "version_key": "v2", "lead": lead, "respostas": RESPOSTAS,
        "utm": {"utm_campaign": "outubro"},
    })
    return event_id


def completo(email, telefone="", sessao=SESSAO, captura_id=CAPTURA, slug="crivo", site="a"):
    lead = {"email": email, "name": "Maria"}
    if telefone:
        lead["phone"] = telefone
    data = {
        "site_id": site, "quiz_slug": slug, "result_key": "iniciante", "score": 7,
        "version_key": "v2", "lead": lead, "utm": {"utm_campaign": "outubro"},
        "submissao_id": str(uuid.uuid4()), "sessao": sessao, "respostas": RESPOSTAS,
    }
    if captura_id:
        data["captura_parcial_id"] = captura_id
    event_id = str(uuid.uuid4())
    ao_quiz_completado(event_id, data)
    return event_id


def abertas():
    return Oportunidade.objects.filter(desfecho_encerrada_em__isnull=True)


def test_email_corrigido_entre_captura_e_conclusao_fica_um_contato_e_uma_oferta():
    captura(email="maria@gmial.com", telefone="11999990000")
    completo("maria@gmail.com")
    assert list(Lead.objects.values_list("email", flat=True)) == ["maria@gmail.com"]
    assert abertas().count() == 1
    quiz = QuizDoLead.objects.get()
    assert quiz.situacao == "completo" and quiz.captura_id == CAPTURA
    corrigido = TimelineEvent.objects.get(event="lead.contato_corrigido")
    assert corrigido.payload["email_anterior"] == "maria@gmial.com"


def test_completo_acha_a_captura_pelo_id_mesmo_sem_sessao():
    captura(email="maria@gmial.com")
    completo("maria@gmail.com", sessao=None)
    assert Lead.objects.count() == 1
    assert QuizDoLead.objects.get().situacao == "completo"


def test_email_corrigido_para_contato_ja_conhecido_leva_tentativa_e_oferta():
    Lead.objects.create(site_id="a", email="maria@gmail.com", name="Maria")
    captura(email="maria@gmial.com")
    completo("maria@gmail.com")
    maria = Lead.objects.get(email="maria@gmail.com")
    assert abertas().count() == 1
    assert abertas().get().lead == maria
    assert QuizDoLead.objects.get().lead == maria
    errado = Lead.objects.get(email="maria@gmial.com")
    assert TimelineEvent.objects.filter(lead=errado,
                                        event="quiz.continuou_em_outro_contato").exists()
    assert RegistroHistoricoOportunidade.objects.filter(
        descricao__contains="corrigiu o contato").exists()


def test_email_corrigido_para_contato_que_ja_tem_a_oferta_encerra_a_duplicada():
    completo("maria@gmail.com", sessao="antiga", captura_id=None)  # já fez o quiz antes
    captura(email="maria@gmial.com")
    completo("maria@gmail.com")
    assert abertas().count() == 1
    assert abertas().get().lead.email == "maria@gmail.com"
    duplicada = Oportunidade.objects.get(lead__email="maria@gmial.com")
    assert duplicada.desfecho_resultado == "desqualificada"


def test_captura_atrasada_com_outro_email_depois_do_completo_e_ignorada():
    completo("maria@gmail.com")
    captura(email="maria@gmial.com")
    assert list(Lead.objects.values_list("email", flat=True)) == ["maria@gmail.com"]
    assert Oportunidade.objects.count() == 1
    assert not TimelineEvent.objects.filter(event="quiz.captura_parcial").exists()


def test_captura_so_com_telefone_novo_vira_contato_e_abre_oferta():
    captura(telefone="(11) 99999-0000", nome="")
    lead = Lead.objects.get()
    assert lead.email == "" and lead.phone == "(11) 99999-0000"
    assert lead.source == "quiz:crivo"
    assert abertas().get().lead == lead
    assert QuizDoLead.objects.get().lead == lead


def test_dois_contatos_so_com_telefone_no_mesmo_site():
    captura(telefone="11999990000", sessao="s-1", captura_id="c-1")
    captura(telefone="21988887777", sessao="s-2", captura_id="c-2")
    assert Lead.objects.filter(email="").count() == 2


def test_so_telefone_e_depois_conclui_com_email_preenche_o_mesmo_contato():
    captura(telefone="11999990000", nome="")
    completo("maria@gmail.com")
    lead = Lead.objects.get()
    assert lead.email == "maria@gmail.com" and lead.phone == "11999990000"
    assert Oportunidade.objects.count() == 1
    assert QuizDoLead.objects.get().situacao == "completo"


def test_captura_so_telefone_de_contato_conhecido_em_outro_formato():
    Lead.objects.create(site_id="a", email="maria@gmail.com", phone="+55 11 99999-0000")
    captura(telefone="(11) 99999-0000")
    assert Lead.objects.count() == 1
    assert Oportunidade.objects.get().lead.email == "maria@gmail.com"


def test_telefone_dividido_por_dois_contatos_nao_vai_para_a_ficha_de_nenhum():
    Lead.objects.create(site_id="a", email="pai@gmail.com", phone="11966665555")
    Lead.objects.create(site_id="a", email="filha@gmail.com", phone="+55 (11) 96666-5555")
    captura(telefone="11966665555", nome="")
    nova = QuizDoLead.objects.get().lead
    assert nova.email == "" and nova.phone == "11966665555"
    assert not Lead.objects.get(email="pai@gmail.com").quizzes.exists()
    # Ao concluir com o e-mail da filha, tudo vai para a ficha dela.
    completo("filha@gmail.com")
    filha = Lead.objects.get(email="filha@gmail.com")
    assert QuizDoLead.objects.get().lead == filha
    assert abertas().get().lead == filha


def test_telefone_de_outro_site_nao_identifica():
    Lead.objects.create(site_id="b", email="maria@gmail.com", phone="11999990000")
    captura(telefone="11999990000", nome="")
    assert QuizDoLead.objects.get().lead.site_id == "a"


def test_historico_da_captura_nao_diz_que_respondeu_e_a_conclusao_atualiza_o_passo():
    captura(email="maria@gmail.com")
    oferta = Oportunidade.objects.get()
    primeiro = oferta.historico.get()
    assert "sem concluir" in primeiro.descricao
    assert "Respondeu" not in primeiro.descricao
    assert "não chegou ao resultado" in oferta.passo_descricao
    completo("maria@gmail.com")
    oferta.refresh_from_db()
    assert oferta.passo_descricao == "Oferecer o produto indicado pelo quiz crivo (resultado: iniciante)"
    assert oferta.historico.filter(descricao__startswith="Concluiu o quiz crivo").count() == 1


def test_mesma_conclusao_com_dois_event_ids_aparece_uma_vez_na_linha_do_tempo():
    completo("maria@gmail.com", captura_id="")
    completo("maria@gmail.com", captura_id="")
    lead = Lead.objects.get()
    assert lead.timeline.filter(event="quiz.completado").count() == 1
    assert QuizDoLead.objects.count() == 1 and Oportunidade.objects.count() == 1


def test_mesma_submissao_reenviada_sem_sessao_nao_duplica():
    data = {
        "site_id": "a", "quiz_slug": "crivo", "result_key": "iniciante", "score": 7,
        "version_key": "v2", "lead": {"email": "maria@gmail.com"},
        "submissao_id": str(uuid.uuid4()), "respostas": RESPOSTAS,
    }
    ao_quiz_completado(str(uuid.uuid4()), data)
    ao_quiz_completado(str(uuid.uuid4()), data)
    assert TimelineEvent.objects.filter(event="quiz.completado").count() == 1


def test_sessoes_diferentes_do_mesmo_quiz_seguem_como_conclusoes_diferentes():
    completo("maria@gmail.com", sessao="s-1", captura_id="")
    completo("maria@gmail.com", sessao="s-2", captura_id="")
    assert TimelineEvent.objects.filter(event="quiz.completado").count() == 2


def test_oferta_reconstruida_de_quem_so_deixou_o_contato_nao_diz_que_respondeu():
    from apps.core.oferta import abrir_oferta_do_quiz

    lead = Lead.objects.create(site_id="a", email="ana@gmail.com", source="quiz:crivo")
    oferta = abrir_oferta_do_quiz(lead, {"quiz_slug": "crivo"}, "captura:1", origem="captura")
    historico = oferta.historico.get()
    assert historico.descricao == "Começou o quiz crivo e deixou o contato; oferta aberta."
    assert "não chegou ao resultado" in oferta.passo_descricao


def test_passo_mudado_pela_equipe_nao_e_trocado_na_conclusao():
    captura(email="maria@gmail.com")
    oferta = Oportunidade.objects.get()
    oferta.passo_descricao = "Ligar na terça"
    oferta.save()
    completo("maria@gmail.com")
    oferta.refresh_from_db()
    assert oferta.passo_descricao == "Ligar na terça"
