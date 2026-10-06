"""Acompanhamento com matrículas e CRM fictícios, sem consultar serviços reais."""

from django.test import RequestFactory
from django.utils import timezone

from apps.core import acompanhamento_alunos as tela
from apps.core.acompanhamento_modelo import RegistroAcompanhamentoAluno as Registro
from apps.core.clients import LeadsClient
from apps.core.crm_client import CRMClient


MATRICULAS = [
    {"id": "m1", "site_id": "escola-a", "email": "ana@example.test", "nome_completo": "Ana", "product_id": "curso-a", "status": "ativa", "turma": "A"},
    {"id": "m2", "site_id": "escola-a", "email": "ana@example.test", "nome_completo": "Ana", "product_id": "curso-b", "status": "ativa", "turma": "B"},
    {"id": "m3", "site_id": "escola-a", "email": "bia@example.test", "nome_completo": "Bia", "product_id": "curso-a", "status": "ativa"},
]


def _pedido(metodo, caminho, dados=None):
    fabrica = RequestFactory()
    request = getattr(fabrica, metodo)(caminho, data=dados or {})
    request.admin = {"email": "dono@example.test", "nome": "Dono"}
    return request


def test_lista_agrupa_matriculas_e_nao_interpreta_ausencia_como_abandono(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    resposta = tela.acompanhamento_alunos(_pedido("get", "/escola/alunos/acompanhamento/"))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "2 pessoas" in html
    assert "2 matrículas" in html
    assert "Sem acompanhamento registrado" in html
    assert "não indica abandono" in html


def test_post_acrescenta_historico_sem_substituir_registro_anterior(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    anterior = Registro.objects.create(
        site_id="escola-a", email="ana@example.test", product_id="curso-a",
        status=Registro.Status.EM_ANDAMENTO,
        situacao_curso=Registro.SituacaoCurso.SEM_INFORMACAO,
        registrado_por="dono@example.test",
    )
    resposta = tela.acompanhamento_aluno(_pedido("post", "/escola/alunos/acompanhamento/ficha/", {
        "site_id": "escola-a", "email": "ana@example.test", "product_id": "curso-b",
        "status": "esperando_resposta", "situacao_curso": "dificuldade",
        "progresso_externo": "Módulo 2 na Herospark", "fonte": "Aluno por mensagem",
        "dificuldade": "Dúvida na tarefa", "responsavel": "Professora",
        "proximo_contato": "Retomar por e-mail", "prazo": "2099-10-10",
        "resultado": "Material enviado",
    }))
    assert resposta.status_code == 302
    assert Registro.objects.count() == 2
    assert Registro.objects.get(pk=anterior.pk).situacao_curso == Registro.SituacaoCurso.SEM_INFORMACAO
    novo = Registro.objects.exclude(pk=anterior.pk).get()
    assert novo.product_id == "curso-b"
    assert novo.progresso_externo == "Módulo 2 na Herospark"
    assert novo.fonte == "Aluno por mensagem"
    assert novo.responsavel == "Professora"


def test_prazo_vencido_filtra_sem_perder_sem_registro(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    Registro.objects.create(
        site_id="escola-a", email="ana@example.test", status="em_andamento",
        situacao_curso="dificuldade", prazo=timezone.localdate() - timezone.timedelta(days=1),
        registrado_por="dono@example.test",
    )
    html = tela.acompanhamento_alunos(_pedido("get", "/escola/alunos/acompanhamento/", {"atraso": "sim"})).content.decode()
    assert "Ana" in html and "Bia" not in html
    assert "1 com prazo vencido" in html
    html_sem = tela.acompanhamento_alunos(_pedido("get", "/escola/alunos/acompanhamento/", {"sem_registro": "sim"})).content.decode()
    assert "Bia" in html_sem and "Ana" not in html_sem


def test_curso_resolvido_nao_apaga_prazo_do_outro_curso(monkeypatch):
    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    Registro.objects.create(site_id="escola-a", email="ana@example.test", product_id="curso-a",
                           status="em_andamento", situacao_curso="dificuldade",
                           prazo=timezone.localdate() - timezone.timedelta(days=1),
                           dificuldade="Precisa rever aula", responsavel="Professora",
                           proximo_contato="Escrever amanhã", registrado_por="dono@example.test")
    Registro.objects.create(site_id="escola-a", email="ana@example.test", product_id="curso-b",
                           status="resolvido", situacao_curso="atividade_observada",
                           fonte="Herospark", registrado_por="dono@example.test")
    html = tela.acompanhamento_alunos(_pedido("get", "/escola/alunos/acompanhamento/", {"atraso": "sim"})).content.decode()
    assert "Ana" in html and "Prazo vencido" in html
    assert "Curso curso-a" in html and "Curso curso-b" in html
    assert "Precisa rever aula" in html and "Professora" in html and "Escrever amanhã" in html
    assert "1 em andamento" in html and "0 resolvidos" in html


def test_crm_fallback_confere_email_e_escola_e_consulta_so_existentes(monkeypatch):
    chamadas = []

    def listar(self, **filtros):
        chamadas.append(("listar", filtros))
        return LeadsClient.OK, {"itens": [
            {"id": "id-ana", "email": "ana@example.test", "site_id": "escola-a"},
            {"id": "id-outra", "email": "ana@example.test", "site_id": "outra"},
        ]}

    def ficha(self, lead_id):
        chamadas.append(("ficha", lead_id))
        return LeadsClient.OK, {"id": lead_id, "email": "ana@example.test", "site_id": "escola-a"}

    def quadro(self, **filtros):
        chamadas.append(("quadro", filtros))
        return CRMClient.OK, {"itens": [
            {"id": "atendimento", "contato": {"id": "id-ana"}},
            {"id": "outro", "contato": {"id": "id-outra"}},
        ]}

    monkeypatch.setattr(LeadsClient, "listar", listar)
    monkeypatch.setattr(LeadsClient, "ficha", ficha)
    monkeypatch.setattr(CRMClient, "quadro", quadro)
    contatos, estado, atendimentos, estado_crm = tela._fontes_externas("escola-a", "ana@example.test", MATRICULAS[:2])
    assert estado == LeadsClient.OK and estado_crm == CRMClient.OK
    assert [c["id"] for c in contatos] == ["id-ana"]
    assert [a["id"] for a in atendimentos] == ["atendimento"]
    assert chamadas[0][1]["q"] == "ana@example.test"
    assert not any(chamada[0] in ("criar", "post", "alterar") for chamada in chamadas)


def test_ficha_reune_cursos_historico_e_fontes_sem_expor_outro_aluno(monkeypatch):
    from apps.core import acompanhamento_fontes

    monkeypatch.setattr(tela.AlunosClient, "alunos", lambda self: MATRICULAS)
    monkeypatch.setattr(tela.CatalogoClient, "listar_produtos", lambda self: [
        {"id": "curso-a", "name": "Curso de arte"}, {"id": "curso-b", "name": "Curso de criação"},
    ])
    monkeypatch.setattr(tela, "_fontes_externas", lambda *args: ([], "sem_vinculo", [], "sem_vinculo"))
    monkeypatch.setattr(acompanhamento_fontes, "consultar_fontes", lambda *args: {})
    Registro.objects.create(site_id="escola-a", email="ana@example.test", status="resolvido",
                           situacao_curso="dificuldade", dificuldade="Precisava de exemplo",
                           resultado="Exemplo entregue", registrado_por="dono@example.test")
    resposta = tela.acompanhamento_aluno(_pedido("get", "/escola/alunos/acompanhamento/ficha/", {
        "site_id": "escola-a", "email": "ana@example.test",
    }))
    html = resposta.content.decode()
    assert resposta.status_code == 200
    assert "Curso de arte" in html and "Curso de criação" in html
    assert "Precisava de exemplo" in html and "Exemplo entregue" in html
    assert "Bia" not in html
