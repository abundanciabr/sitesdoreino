import json
import uuid
from datetime import datetime, timezone

import pytest
from django.test import RequestFactory, override_settings

from apps.quiz import evolucao
from apps.quiz.models import (
    PropostaDeVersao,
    Question,
    Quiz,
    QuizVersion,
    Site,
    Submission,
    TelemetryEvent,
)


pytestmark = pytest.mark.django_db
TOKEN = "token-de-teste"


@pytest.fixture
def quiz():
    site = Site.objects.create(id="site-evo", host="evo.exemplo.com", name="Evolução")
    quiz = Quiz.objects.create(site=site, slug="crivo", title="Crivo")
    for chave in ("B1", "B2"):
        versao = QuizVersion.objects.create(quiz=quiz, key=chave)
        Question.objects.create(version=versao, order=1, text="Primeira")
        Question.objects.create(version=versao, order=2, text="Segunda")
    return quiz


def instante(dia, hora=15):
    return datetime(2026, 10, dia, hora, tzinfo=timezone.utc)


def evento(quiz, sessao, tipo, quando, element_id="", metadata=None, versao="B1"):
    return TelemetryEvent.objects.create(
        session_id=sessao,
        site_id=quiz.site_id,
        quiz_slug=quiz.slug,
        version_key=versao,
        event_type=tipo,
        element_id=element_id,
        metadata=metadata or {},
        occurred_at=quando,
    )


def sessoes(quiz, quantidade, versao="B1", dia=1, campanha="", ver_p2=0, concluir=0, sair=0):
    p1, p2 = [str(q.id) for q in quiz.versions.get(key=versao).questions.all()]
    meta = {"utm": {"campaign": campanha} if campanha else {}}
    for n in range(quantidade):
        sessao = uuid.uuid4()
        evento(quiz, sessao, "view_quiz", instante(dia), metadata=meta, versao=versao)
        evento(quiz, sessao, "view_question", instante(dia), p1, versao=versao)
        if n < ver_p2:
            evento(quiz, sessao, "view_question", instante(dia), p2, versao=versao)
        if n < concluir:
            Submission.objects.create(
                quiz=quiz,
                version=quiz.versions.get(key=versao),
                session_id=sessao,
                site_id=quiz.site_id,
                score=1,
                result_key="alto",
                answers={},
                lead_email="privado@exemplo.com",
            )
            if n < sair:
                evento(quiz, sessao, "checkout_exit", instante(dia, 18), "alto", {}, versao)


def achar(gargalos, tipo):
    return next(g for g in gargalos if g["tipo"] == tipo)


def test_gargalo_de_etapa_com_evidencia_numerica_e_prioridade(quiz):
    # 40 viram a pergunta 1; só 10 chegaram à 2; 8 concluíram, 4 saíram
    sessoes(quiz, 40, ver_p2=10, concluir=8, sair=4)
    leitura = evolucao.leitura_diaria(quiz)
    g = achar(leitura["gargalos"], "etapa_com_maior_perda")
    assert g["prioridade"] == "alta"
    assert (g["evidencia"]["numerador"], g["evidencia"]["denominador"]) == (30, 40)
    assert "30 de 40" in g["evidencia"]["texto"]
    assert g["inconclusivo"] is False
    saida = achar(leitura["gargalos"], "conclusoes_sem_saida")
    assert (saida["evidencia"]["numerador"], saida["evidencia"]["denominador"]) == (4, 8)
    # prioridade ordena: alta antes de inconclusiva
    ordens = [g["prioridade"] for g in leitura["gargalos"]]
    assert ordens == sorted(ordens, key=evolucao.ORDEM_PRIORIDADE.get)


def test_amostra_pequena_e_inconclusiva(quiz):
    sessoes(quiz, 5, ver_p2=1, concluir=1)
    leitura = evolucao.leitura_diaria(quiz)
    g = achar(leitura["gargalos"], "etapa_com_maior_perda")
    assert g["prioridade"] == "inconclusiva" and g["inconclusivo"] is True
    assert "inconclusiva" in g["observacao"]
    assert leitura["por_dia"][0]["gargalos"][0]["prioridade"] == "inconclusiva"


def test_dados_faltantes_versao_sem_visitas_campanha_sem_utm_e_sem_compra(quiz):
    sessoes(quiz, 3, versao="B1")  # B2 ativa, sem visitas; sessões sem utm nem cpg
    leitura = evolucao.leitura_diaria(quiz)
    tipos = {f["tipo"] for f in leitura["dados_faltantes"]}
    assert {"versao_sem_visitas", "campanha_sem_utm", "sem_dados_de_compra"} <= tipos
    sem_visitas = next(f for f in leitura["dados_faltantes"] if f["tipo"] == "versao_sem_visitas")
    assert sem_visitas["version_key"] == "B2"
    assert leitura["comercial"]["estado"] == "sem dados de compra"
    assert "compra" in next(
        f for f in leitura["dados_faltantes"] if f["tipo"] == "sem_dados_de_compra"
    )["texto"]
    assert leitura["periodo"]["fuso"] == "America/Sao_Paulo"
    assert leitura["denominador"].startswith("sessões distintas")


def test_conclusoes_so_com_demonstracao_viram_dado_faltante(quiz):
    sessoes(quiz, 2, concluir=2)
    sessao = Submission.objects.first().session_id
    evento(quiz, sessao, "checkout_exit", instante(1, 18), "alto", {"demonstracao": True})
    leitura = evolucao.leitura_diaria(quiz)
    assert any(f["tipo"] == "sem_saida_real" for f in leitura["dados_faltantes"])


def test_leitura_por_campanha_e_comparacao_nao_aleatoria(quiz):
    sessoes(quiz, 3, versao="B1", campanha="alfa")
    sessoes(quiz, 3, versao="B2", campanha="beta")
    leitura = evolucao.leitura_diaria(quiz)
    nomes = {c["nome"] for c in leitura["por_campanha"]}
    assert nomes == {"alfa", "beta"}
    assert "não aleatórias" in leitura["comparacoes"]["aviso"]
    assert "não prova" in leitura["comparacoes"]["aviso"]
    assert len(leitura["comparacoes"]["campanhas"]) == 2
    assert all(c["inconclusiva"] for c in leitura["comparacoes"]["campanhas"])
    assert len(leitura["comparacoes"]["versoes"]) == 2


def test_trafego_de_teste_nao_entra_na_leitura(quiz):
    sessao = uuid.uuid4()
    evento(quiz, sessao, "view_quiz", instante(1), metadata={"context": {"src": "teste"}})
    leitura = evolucao.leitura_diaria(quiz)
    assert leitura["visitas_elegiveis"] == 0
    assert leitura["teste"]["visitas"] == 1
    assert leitura["gargalos"] == []


# ---- propostas ------------------------------------------------------------


def pedido(caminho, metodo="get", corpo=None, token=TOKEN):
    extras = {"HTTP_AUTHORIZATION": f"Bearer {token}"} if token is not None else {}
    fabrica = RequestFactory()
    if corpo is not None:
        return getattr(fabrica, metodo)(
            caminho, data=json.dumps(corpo), content_type="application/json", **extras
        )
    return getattr(fabrica, metodo)(caminho, **extras)


BASE = "/interno/editor/quizzes/crivo/propostas?site_id=site-evo"
VALIDA = {
    "versao_base": "B1",
    "gargalo": "etapa:geral:B1:1",
    "hipotese": "Perguntas mais curtas seguram mais gente.",
    "prioridade": "alta",
    "mudanca": "Trocar a pergunta 1 por uma versão curta.",
    "key_sugerida": "B3",
}


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_api_exige_token_e_metodo(quiz):
    assert evolucao.propostas(pedido(BASE, token=None), "crivo").status_code == 401
    assert evolucao.propostas(pedido(BASE, "delete"), "crivo").status_code == 405
    assert evolucao.leitura(pedido(BASE, token="outro"), "crivo").status_code == 401
    inexistente = "/x?site_id=site-evo"
    assert evolucao.leitura(pedido(inexistente), "nao-existe").status_code == 404


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_ciclo_completo_sem_tocar_nas_versoes_existentes(quiz):
    versoes_antes = list(
        QuizVersion.objects.filter(quiz=quiz).values("id", "key", "weight", "active", "experience")
    )
    perguntas_antes = Question.objects.count()
    criada = evolucao.propostas(pedido(BASE, "post", VALIDA), "crivo")
    assert criada.status_code == 201
    dados = json.loads(criada.content)
    assert dados["estado"] == "proposta" and "criar_no_estudio" not in dados
    detalhe = f"/interno/editor/quizzes/crivo/propostas/{dados['id']}?site_id=site-evo"

    aceita = evolucao.proposta(pedido(detalhe, "patch", {"estado": "aceita"}), "crivo", dados["id"])
    corpo = json.loads(aceita.content)
    assert corpo["estado"] == "aceita" and corpo["aceita_em"]
    assert corpo["criar_no_estudio"]["key"] == "B3"
    assert "não foi alterada" in corpo["criar_no_estudio"]["mensagem"]
    # a versão sugerida ainda não existe: não dá para marcar publicada
    cedo = evolucao.proposta(pedido(detalhe, "patch", {"estado": "publicada"}), "crivo", dados["id"])
    assert cedo.status_code == 422
    QuizVersion.objects.create(quiz=quiz, key="B3")  # o estúdio criou
    pub = evolucao.proposta(pedido(detalhe, "patch", {"estado": "publicada"}), "crivo", dados["id"])
    assert json.loads(pub.content)["publicada_em"]
    sem_resultado = evolucao.proposta(pedido(detalhe, "patch", {"estado": "medida"}), "crivo", dados["id"])
    assert sem_resultado.status_code == 422
    medida = evolucao.proposta(
        pedido(
            detalhe,
            "patch",
            {
                "estado": "medida",
                "resultado_texto": "Conclusão subiu de 20% para 31%, amostra 120.",
                "resultado_json": {"taxa_antes": 0.2, "taxa_depois": 0.31},
                "decisao_seguinte": "Manter B3 e testar nova pergunta 2.",
            },
        ),
        "crivo",
        dados["id"],
    )
    final = json.loads(medida.content)
    assert final["estado"] == "medida" and final["medida_em"]
    assert final["resultado_json"]["taxa_depois"] == 0.31
    assert final["decisao_seguinte"].startswith("Manter")
    voltou = evolucao.proposta(pedido(detalhe, "patch", {"estado": "aceita"}), "crivo", dados["id"])
    assert voltou.status_code == 422

    atuais = list(
        QuizVersion.objects.filter(quiz=quiz, key__in=["B1", "B2"]).values(
            "id", "key", "weight", "active", "experience"
        )
    )
    assert atuais == versoes_antes
    assert Question.objects.count() == perguntas_antes
    listagem = json.loads(evolucao.propostas(pedido(BASE), "crivo").content)
    assert [p["estado"] for p in listagem["propostas"]] == ["medida"]


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_proposta_nao_aceita_key_de_versao_existente_nem_base_inexistente(quiz):
    repetida = evolucao.propostas(pedido(BASE, "post", {**VALIDA, "key_sugerida": "B2"}), "crivo")
    assert repetida.status_code == 422 and "não mudam" in json.loads(repetida.content)["detail"]
    sem_base = evolucao.propostas(pedido(BASE, "post", {**VALIDA, "versao_base": "Z9"}), "crivo")
    assert sem_base.status_code == 422
    sem_hipotese = evolucao.propostas(pedido(BASE, "post", {**VALIDA, "hipotese": " "}), "crivo")
    assert sem_hipotese.status_code == 422
    assert PropostaDeVersao.objects.count() == 0
    evolucao.propostas(pedido(BASE, "post", VALIDA), "crivo")
    dupla = evolucao.propostas(pedido(BASE, "post", VALIDA), "crivo")
    assert dupla.status_code == 422


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_descartar_registra_data_e_encerra(quiz):
    dados = json.loads(evolucao.propostas(pedido(BASE, "post", VALIDA), "crivo").content)
    detalhe = f"/x?site_id=site-evo"
    resposta = evolucao.proposta(pedido(detalhe, "patch", {"estado": "descartada"}), "crivo", dados["id"])
    assert json.loads(resposta.content)["descartada_em"]
    de_novo = evolucao.proposta(pedido(detalhe, "patch", {"estado": "aceita"}), "crivo", dados["id"])
    assert de_novo.status_code == 422


@override_settings(TOKEN_EDITOR_ADMIN=TOKEN)
def test_api_da_leitura_diaria(quiz):
    sessoes(quiz, 2)
    resposta = evolucao.leitura(pedido("/x?site_id=site-evo&inicio=2026-10-01&fim=2026-10-02"), "crivo")
    assert resposta.status_code == 200
    dados = json.loads(resposta.content)
    assert dados["periodo"] == {"inicio": "2026-10-01", "fim": "2026-10-02", "fuso": "America/Sao_Paulo"}
    ruim = evolucao.leitura(pedido("/x?site_id=site-evo&inicio=ontem"), "crivo")
    assert ruim.status_code == 422
