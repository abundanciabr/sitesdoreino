import json
from datetime import timedelta
from types import SimpleNamespace
import pytest
from django.utils import timezone
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import entrar_na_fila, decidir_na_fila
from apps.core.api import confirm_access_whatsapp_number, get_access_notice

pytestmark = pytest.mark.django_db

def pedido(**extra):
    return entrar_na_fila(site_id="meshcraft", email="aluno@example.test",
        nome_completo="Pessoa de Teste", whatsapp="11987654321", **extra)[0]

def confirmar(linha, **extra):
    dados = dict(site_id=linha.site_id, codigo=linha.whatsapp_confirmacao_codigo,
        whatsapp="5511987654321")
    dados.update(extra)
    return confirm_access_whatsapp_number(SimpleNamespace(body=json.dumps(dados).encode()))

def test_sem_autorizacao_nao_pede_confirmacao():
    linha = pedido()
    assert not linha.whatsapp_pedido_id
    assert not OutboxEvent.objects.filter(event="escola.whatsapp-solicitado").exists()

def test_confirmacao_pelo_numero_correto_nao_libera_acesso():
    linha = pedido(whatsapp_avisos=True)
    assert linha.whatsapp_avisos
    assert len(linha.whatsapp_confirmacao_codigo) == 10
    from apps.core.api import _chave_numero_aviso
    assert _chave_numero_aviso(linha.whatsapp) == _chave_numero_aviso("5511987654321")
    assert confirmar(linha).status_code == 200
    linha.refresh_from_db()
    assert linha.whatsapp_confirmado_em
    assert linha.status == "aguardando"
    evento = OutboxEvent.objects.get(event="escola.whatsapp-solicitado")
    assert set(evento.payload) == {"site_id", "matricula_id"}

def test_numero_ou_site_errado_nao_confirma():
    linha = pedido(whatsapp_avisos=True)
    assert confirmar(linha, whatsapp="5511966660000").status_code == 404
    assert confirmar(linha, site_id="outra-escola").status_code == 404
    linha.refresh_from_db()
    assert linha.whatsapp_confirmado_em is None

def test_codigo_expirado_nao_confirma():
    linha = pedido(whatsapp_avisos=True)
    Matricula.objects.filter(pk=linha.pk).update(whatsapp_consentido_em=timezone.now()-timedelta(days=8))
    assert confirmar(linha).status_code == 404

def test_reenvio_identico_preserva_confirmacao_e_nao_duplica():
    linha = pedido(whatsapp_avisos=True)
    assert confirmar(linha).status_code == 200
    outra = pedido(whatsapp_avisos=True)
    assert outra.whatsapp_confirmado_em
    assert outra.whatsapp_pedido_id == linha.whatsapp_pedido_id
    assert OutboxEvent.objects.filter(event="escola.whatsapp-solicitado").count() == 1

def test_troca_numero_retira_confirmacao():
    linha = pedido(whatsapp_avisos=True)
    confirmar(linha)
    outra, _ = entrar_na_fila(site_id=linha.site_id, email=linha.email,
        nome_completo=linha.name, whatsapp="11999990000", whatsapp_avisos=True)
    assert not outra.whatsapp_confirmado_em
    assert outra.whatsapp_pedido_id != linha.whatsapp_pedido_id

@pytest.mark.parametrize("decisao,status", [("liberar","ativa"),("recusar","recusada")])
def test_os_dois_resultados_identificam_aviso_sem_reativar_historico(decisao,status):
    linha = pedido()
    assert get_access_notice(None, str(linha.pk), linha.site_id, "00000000-0000-4000-8000-000000000000").status_code == 404
    decidida, resultado = decidir_na_fila(id_da_linha=str(linha.pk), decisao=decisao,
        decidido_por="admin", product_id="curso", motivo="Conferir com a equipe")
    assert resultado == "ok"
    resposta = get_access_notice(None, str(linha.pk), linha.site_id, str(decidida.aviso_event_id))
    assert resposta.status_code == 200
    assert json.loads(resposta.content)["status"] == status

