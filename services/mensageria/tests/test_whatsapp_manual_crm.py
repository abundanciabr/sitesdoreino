from datetime import timedelta
import pytest
from django.test import Client
from django.utils import timezone
from apps.conversas.models import Conversa, Descadastro
from apps.whatsapp.service import normalizar_telefone
from tests.test_conversas import base, meio_dia, _conversa_ligada, _gateway_aberto, _api, SITE

pytestmark = pytest.mark.django_db(transaction=True)


@pytest.mark.parametrize("transporte,autor,esperado", [
    ("WHATSAPP-BAILEYS", "pessoa", "enviada"),
    ("WHATSAPP-BAILEYS", "agente", "fora_da_janela"),
    ("WHATSAPP-BUSINESS", "pessoa", "fora_da_janela"),
])
def test_inicio_manual_usa_transporte_sem_alterar_automacao(base, monkeypatch, transporte, autor, esperado):
    base["config"].transporte = transporte
    base["config"].save()
    conv = _conversa_ligada(base)
    Conversa.objects.filter(pk=conv.pk).update(janela_aberta_ate=None, ultima_entrada_em=None)
    posts = []
    _gateway_aberto(monkeypatch, posts)
    resultado = _api(Client(), "POST", f"/conversas/{conv.id}/mensagens", {
        "site_id": SITE, "texto": "Contato individual", "chave_idempotencia": "manual",
        "autor": autor, "autor_id": "admin"}).json()
    assert resultado["resultado"] == esperado
    assert bool(posts) == (esperado == "enviada")


def test_manual_continua_respeitando_pedido_de_parar(base, monkeypatch):
    conv = _conversa_ligada(base)
    Conversa.objects.filter(pk=conv.pk).update(janela_aberta_ate=None, ultima_entrada_em=None)
    Descadastro.objects.create(site_id=SITE, canal="whatsapp", endereco=conv.endereco, registrado_em=timezone.now())
    posts = []
    _gateway_aberto(monkeypatch, posts)
    resultado = _api(Client(), "POST", f"/conversas/{conv.id}/mensagens", {
        "site_id": SITE, "texto": "Oi", "chave_idempotencia": "manual",
        "autor": "pessoa", "autor_id": "admin"}).json()
    assert resultado["resultado"] == "descadastrado" and not posts


@pytest.mark.parametrize("numero", ["+12025550199", "0012025550199"])
def test_preserva_ddi_explicito(numero):
    assert normalizar_telefone(numero) == "12025550199"


def test_resposta_sem_nono_digito_fica_na_conversa_aberta(base):
    from apps.conversas.entrada import receber, Recebida
    conv = _conversa_ligada(base)
    ConvAntes = Conversa.objects.count()
    numero = conv.endereco[:4] + conv.endereco[-8:]
    recebida, nova = receber(Recebida(site_id=SITE, canal="whatsapp", endereco=numero,
                                    texto="Resposta individual", id_externo="retorno-sem-nove"))
    assert nova and recebida.conversa_id == conv.pk
    assert Conversa.objects.count() == ConvAntes
    assert _api(Client(), "POST", "/conversas", {"site_id": SITE, "canal": "whatsapp",
        "lead_id": conv.lead_id, "endereco": numero}).json()["id"] == str(conv.pk)
