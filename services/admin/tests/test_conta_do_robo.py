"""A conta do robô: entra com a credencial vigente, e só faz o que tem volta."""

import io
import datetime as dt

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import Client

from apps.auditoria.models import Registro
from apps.core.models import Administrador, Documento, CartaoDoPlacar, FechamentoDoCiclo

DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def ambiente(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", "http://identidade:8000/interno")
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


def emitir() -> str:
    saida, erro = io.StringIO(), io.StringIO()
    call_command("conta_do_robo", "emitir", stdout=saida, stderr=erro)
    credencial = saida.getvalue().strip()
    assert credencial and "\n" not in credencial
    assert credencial not in erro.getvalue()
    return credencial


def robo(credencial: str) -> Client:
    # CSRF LIGADO de propósito: o robô tem de passar sem token de formulário.
    return Client(enforce_csrf_checks=True, HTTP_AUTHORIZATION=f"Robo {credencial}")


def test_robo_entra_com_a_credencial_vigente():
    resposta = robo(emitir()).get("/documentos/")
    assert resposta.status_code == 200


def test_credencial_errada_nao_entra():
    emitir()
    assert robo("outra-credencial").get("/documentos/").status_code == 404


def test_sem_emissao_nenhuma_credencial_vale():
    assert robo("qualquer").get("/documentos/").status_code == 404
    assert robo("").get("/documentos/").status_code == 404


def test_reemitir_invalida_a_anterior():
    antiga = emitir()
    nova = emitir()
    assert antiga != nova
    assert robo(antiga).get("/documentos/").status_code == 404
    assert robo(nova).get("/documentos/").status_code == 200


def test_revogar_fecha_ate_a_proxima_emissao():
    credencial = emitir()
    call_command("conta_do_robo", "revogar", stdout=io.StringIO())
    assert robo(credencial).get("/documentos/").status_code == 404
    saida = io.StringIO()
    call_command("conta_do_robo", "conferir", stdout=saida)
    assert "nenhuma credencial vigente" in saida.getvalue()


def test_o_servidor_guarda_so_a_impressao():
    credencial = emitir()
    for linha in Registro.objects.values_list("quem_email", "alvo", "detalhe"):
        assert all(credencial not in campo for campo in linha)
    saida = io.StringIO()
    call_command("conta_do_robo", "conferir", stdout=saida)
    assert "vigente" in saida.getvalue() and credencial not in saida.getvalue()


def test_emitir_recusa_imprimir_na_tela():
    class Tela(io.StringIO):
        def isatty(self):
            return True

    tela = Tela()
    with pytest.raises(CommandError):
        call_command("conta_do_robo", "emitir", stdout=tela)
    assert tela.getvalue() == ""
    assert not Registro.objects.filter(acao=Registro.EMITIR_CREDENCIAL_DO_ROBO).exists()


def test_robo_cria_rascunho_invisivel_e_desfaz_arquivando():
    cliente = robo(emitir())
    criou = cliente.post(
        "/documentos/criar",
        {"titulo": "Rascunho do robô", "nome": "rascunho-do-robo", "corpo": "x"},
    )
    assert criou.status_code == 302
    documento = Documento.objects.get(nome="rascunho-do-robo")
    assert documento.publico is False
    assert Registro.objects.filter(
        acao=Registro.CRIAR_DOCUMENTO, quem_email="robo@conta-do-robo.invalid"
    ).exists()
    assert cliente.get("/documentos/rascunho-do-robo").status_code == 200
    assert Client().get("/docs/rascunho-do-robo").status_code == 404

    assert cliente.post("/documentos/rascunho-do-robo/arquivar").status_code == 302
    documento.refresh_from_db()
    assert documento.arquivado is True
    assert Client().get("/docs/rascunho-do-robo").status_code == 404


@pytest.mark.parametrize(
    "caminho, dados",
    [
        ("/documentos/alvo/apagar", {"confirmacao": "alvo"}),
        ("/livro/alvo/apagar", {"confirmacao": "alvo"}),
        ("/caixa/ideia/1/apagar", {"confirmacao": "1"}),
        ("/menu/versao/apagar", {}),
        ("/escola/alunos/recusados/apagar", {}),
        ("/escola/alunos/resetar-senha", {"email": "aluno@exemplo.com"}),
        ("/escola/administradores/publicar", {"email": "novo@exemplo.com"}),
        ("/equipe/pessoas/associar", {}),
        ("/placar/fechamento/", {"acao": "analista"}),
    ],
)
def test_robo_recusado_em_gesto_sem_volta(caminho, dados):
    Documento.objects.create(nome="alvo", titulo="Alvo", corpo="fica")
    resposta = robo(emitir()).post(caminho, dados)
    assert resposta.status_code == 403
    assert Documento.objects.filter(nome="alvo").exists()
    assert not Administrador.objects.exists()


def test_admin_continua_fechado_a_anonimo():
    emitir()
    sem_nada = Client().get("/documentos/")
    assert sem_nada.status_code == 302
    assert "/entrar/google" in sem_nada["Location"]
    outro_esquema = Client(HTTP_AUTHORIZATION="Bearer qualquer").get("/documentos/")
    assert outro_esquema.status_code == 302
    criar = Client().post("/documentos/criar", {"titulo": "Anônimo", "nome": "anon"})
    assert criar.status_code == 302
    assert not Documento.objects.filter(nome="anon").exists()


def test_robo_salva_fechamento_sem_analista_nem_proxima_meta(monkeypatch):
    from apps.core import fechamento

    meta = CartaoDoPlacar.objects.get(nome="compras-no-ciclo").dados
    resultado = {"x": 5, "alvo": meta["alvo"], "ate": meta["ate"]}
    contexto = {"meta": meta, "placar": resultado, "direcao": None, "recusas": []}
    dados = {
        "estado": "correndo", "partida_em": dt.date(2026, 9, 3),
        "resultado": resultado, "veredito": "perdendo",
        "previsao": {"veredito": "ainda-nao-da", "porque": "teste"},
        "fase": {"fase": "provando"},
    }
    monkeypatch.setattr(fechamento, "montar_o_placar", lambda *_: contexto)
    monkeypatch.setattr(fechamento, "montar", lambda **_: dados)
    monkeypatch.setattr(fechamento, "site_de", lambda _: None)
    analista_pedido = []

    def analista(**kwargs):
        analista_pedido.append(kwargs["pediram"])
        return {"estado": "desligado"}

    monkeypatch.setattr(fechamento.analista_, "para_a_tela", analista)
    cliente = robo(emitir())
    for _ in range(2):
        resposta = cliente.post("/placar/fechamento/", {"por_que": "Resultado conferido"})
        assert resposta.status_code == 200
    encerrado = FechamentoDoCiclo.objects.get(partida_em="2026-09-03")
    assert encerrado.dados["por_que"] == "Resultado conferido"
    assert encerrado.dados["responsavel"] == "conta-do-robo"
    assert encerrado.dados["proximo_alvo"] is None
    assert analista_pedido == [False, False]
    assert CartaoDoPlacar.objects.get(nome="compras-no-ciclo").dados == meta
    assert FechamentoDoCiclo.objects.filter(partida_em="2026-09-03").count() == 1


def test_a_credencial_recusada_nao_vai_para_o_log(caplog):
    emitir()
    with caplog.at_level("WARNING", logger="admin.porta"):
        robo("credencial-que-nao-vale-123").get("/documentos/")
    assert "credencial de robô recusada" in caplog.text
    assert "credencial-que-nao-vale-123" not in caplog.text
