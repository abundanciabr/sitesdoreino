"""Jornada WhatsApp: endereço por site, intenção durável e resultado honesto."""

from types import SimpleNamespace

import pytest

from apps.jornadas import despacho, motor
from apps.jornadas.models import Entrega, JornadaVersao, TextoDoPasso

from test_jornadas_motor import PESSOA, SITE, quando, uma_jornada


def _entrega():
    jornada = uma_jornada(canais=("whatsapp",), publicar=False)
    passo = jornada.versoes.get().passos.get()
    TextoDoPasso.objects.create(
        passo=passo, idioma="pt-br", assunto_visivel="Passo", corpo="Mensagem do passo"
    )
    JornadaVersao.objects.filter(pk=passo.jornada_versao_id).update(
        publicada_em=quando(15)
    )
    inscricao = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        momento=quando(16),
    )
    return Entrega.objects.create(
        inscricao=inscricao,
        passo=passo,
        canal="whatsapp",
        resultado="pendente",
        whatsapp_intencao=True,
        previsto_para=quando(16),
    )


def _liberar(monkeypatch):
    monkeypatch.setattr(
        despacho.regua, "avaliar", lambda **kwargs: SimpleNamespace(barrada=False)
    )


@pytest.mark.django_db
def test_motor_grava_intencao_sem_tocar_gateway_na_transacao(
    monkeypatch,
    django_capture_on_commit_callbacks,
):
    jornada = uma_jornada(canais=("whatsapp",), classe="transacional")
    inscricao = motor.inscrever(
        jornada,
        destinatario_id=PESSOA,
        site_id=SITE,
        momento=quando(16),
    )
    monkeypatch.setattr(
        despacho, "processar_entrega", lambda **kwargs: pytest.fail("antes do commit")
    )
    with django_capture_on_commit_callbacks(execute=False) as callbacks:
        passada = motor.varrer(despachar=despacho.despachar, momento=quando(16))
    linha = Entrega.objects.get(inscricao=inscricao, canal="whatsapp")
    assert linha.resultado == "pendente"
    assert linha.whatsapp_intencao is True
    assert linha.enviado_em is None
    assert passada.pendentes == 1 and passada.entregues == 0
    assert len(callbacks) == 1


def test_telefone_so_da_passagem_do_site_correto(monkeypatch):
    for nome in ("IDENTIDADE_API_URL", "ALUNOS_API_URL"):
        monkeypatch.setenv(nome, f"http://{nome.lower()}.test")
    for nome in ("IDENTIDADE_API_TOKEN", "ALUNOS_API_TOKEN"):
        monkeypatch.setenv(nome, "token-teste")

    def post(url, **kwargs):
        assert url.endswith("/pessoas/por-id")
        assert kwargs["json"] == {"id": PESSOA}
        return SimpleNamespace(
            status_code=200,
            json=lambda: {"email": "aluna+curso@example.test", "idioma": "pt-br"},
        )

    def get(url, **kwargs):
        assert "aluna%2Bcurso%40example.test" in url
        return SimpleNamespace(
            status_code=200,
            json=lambda: {
                "passagens": [
                    {"site_id": SITE, "whatsapp": "+55 11 90000-0001"},
                    {"site_id": "outro-site", "whatsapp": "+55 11 90000-9999"},
                ]
            },
        )

    monkeypatch.setattr(despacho.httpx, "post", post)
    monkeypatch.setattr(despacho.httpx, "get", get)
    assert despacho._telefone_da_pessoa(pessoa_id=PESSOA, site_id=SITE) == (
        "+55 11 90000-0001",
        "pt-br",
        "",
    )


@pytest.mark.django_db
def test_telefone_ausente_deixa_falha_visivel_sem_enviar(monkeypatch):
    entrega = _entrega()
    _liberar(monkeypatch)
    monkeypatch.setattr(
        despacho,
        "_telefone_da_pessoa",
        lambda **kwargs: (None, None, "telefone ausente neste site"),
    )
    from apps.whatsapp import service

    monkeypatch.setattr(service, "consultar_mensagem", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "enviar_mensagem", lambda **kwargs: pytest.fail("nao enviar")
    )
    despacho.processar_entrega(
        inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id
    )
    entrega.refresh_from_db()
    assert entrega.resultado == "falhou"
    assert entrega.enviado_em is None
    assert "telefone ausente" in entrega.motivo


@pytest.mark.django_db
def test_desconexao_e_resultado_desconhecido_nao_duplicam(monkeypatch):
    entrega = _entrega()
    _liberar(monkeypatch)
    monkeypatch.setattr(
        despacho,
        "_telefone_da_pessoa",
        lambda **kwargs: ("+55 11 90000-0001", "pt-br", ""),
    )
    from apps.whatsapp import service

    mensagens = []
    estados = iter(("falhou", "desconhecido"))
    existente = []
    monkeypatch.setattr(
        service,
        "consultar_mensagem",
        lambda **kwargs: existente[0] if existente else None,
    )

    def enviar_mensagem(**kwargs):
        mensagens.append(kwargs)
        return SimpleNamespace(status=next(estados), erro="conexao indisponivel")

    monkeypatch.setattr(service, "enviar_mensagem", enviar_mensagem)
    for _ in range(2):
        despacho.processar_entrega(
            inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id
        )
    entrega.refresh_from_db()
    assert entrega.resultado == "resultado_desconhecido"
    assert entrega.enviado_em is None
    assert len(mensagens) == 2
    assert mensagens[0]["referencia"] == mensagens[1]["referencia"]
    assert mensagens[0]["origem"] == "jornada"

    existente.append(SimpleNamespace(status="desconhecido", erro=""))
    despacho.processar_entrega(
        inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id
    )
    assert len(mensagens) == 2
    existente[0].status = "entregue"
    despacho.processar_entrega(
        inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id
    )
    entrega.refresh_from_db()
    assert entrega.resultado == "entregue"
    assert entrega.enviado_em is not None


@pytest.mark.django_db
def test_cancelamento_antes_do_worker_impede_envio(monkeypatch):
    entrega = _entrega()
    entrega.inscricao.estado = "concluida"
    entrega.inscricao.save(update_fields=["estado"])
    assert motor.cancelar(
        entrega.inscricao.jornada, destinatario_id=PESSOA, site_id=SITE,
        motivo="pessoa agiu antes do envio",
    ) == 1
    from apps.whatsapp import service

    monkeypatch.setattr(service, "consultar_mensagem", lambda **kwargs: None)
    monkeypatch.setattr(
        service, "enviar_mensagem", lambda **kwargs: pytest.fail("nao enviar")
    )
    despacho.processar_entrega(
        inscricao_id=entrega.inscricao_id, passo_id=entrega.passo_id
    )
    entrega.refresh_from_db()
    assert entrega.resultado == "pulada"


@pytest.mark.django_db
def test_historico_anterior_nao_e_reenviado(monkeypatch):
    entrega = _entrega()
    entrega.resultado = "enviada"
    entrega.whatsapp_intencao = False
    entrega.save(update_fields=["resultado", "whatsapp_intencao"])
    monkeypatch.setattr(
        despacho, "processar_entrega", lambda **kwargs: pytest.fail("historico")
    )
    assert despacho.processar_pendentes() == 0
