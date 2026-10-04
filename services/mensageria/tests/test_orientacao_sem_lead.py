"""Orientação fixa a quem escreve sem ser do quiz e a quem tem telefone ambíguo.

Nenhuma chamada real: o gateway do WhatsApp e a célula de leads são simulados.
"""
import json
from datetime import timedelta

import pytest
from django.test import Client
from django.utils import timezone

from apps.conversas.models import Conversa, Descadastro, MensagemDaConversa, OrientacaoDoSite
from apps.jornadas.models import OutboxEvent
from apps.whatsapp.models import ConfiguracaoWhatsApp

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-abc"
LEITURA = "token-leitura-conversas"
ESCRITA = "token-escrita-conversas"
LEAD_A = "11111111-1111-1111-1111-111111111111"
LEAD_B = "22222222-2222-2222-2222-222222222222"
LEAD_C = "33333333-3333-3333-3333-333333333333"
LEAD_D = "44444444-4444-4444-4444-444444444444"
SEGREDOS = ("Ana Souza", "Bia Lima", "Carla Dias", "Dani", "ana@exemplo.com", "bia@exemplo.com",
            "carla@exemplo.com", "dani@exemplo.com", "98888-7777", "988887777", "11 98888")


class Resposta:
    def __init__(self, status, dados):
        self.status_code = status
        self._dados = dados

    def json(self):
        return self._dados


@pytest.fixture
def mundo(settings, monkeypatch):
    settings.WHATSAPP_GATEWAY_URL = "http://evolution:8080"
    settings.WHATSAPP_GATEWAY_TOKEN = "teste-local"
    settings.WHATSAPP_WEBHOOK_TOKEN = "retorno-local"
    settings.LEADS_API_URL = "http://leads:8000/api/leads"
    settings.LEADS_API_TOKEN = "par-mensageria"
    settings.TOKENS_SOMENTE_LEITURA = {LEITURA}
    settings.TOKENS_PUBLICACAO = {ESCRITA}
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    contatos, posts = [], []

    def get(url, params=None, headers=None, timeout=None):
        assert headers == {"Authorization": "Bearer par-mensageria"}
        q = params["q"].lower()
        itens = [c for c in contatos
                 if (not params.get("site_id") or c["site_id"] == params["site_id"])
                 and (q in c["telefone"].lower() or q in c["email"].lower())]
        return Resposta(200, {"itens": itens, "tem_mais": False})

    def gateway(metodo, caminho, dados=None):
        if metodo == "GET":
            return {"instance": {"state": "open"}}
        posts.append((caminho, dados))
        return {"key": {"id": f"wamid-{len(posts)}"}}

    monkeypatch.setattr("apps.conversas.leads.httpx.get", get)
    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway)
    # A hora do agente não importa para a orientação (é resposta), mas fixo para não depender do relógio.
    ConfiguracaoWhatsApp.objects.create(site_id=SITE, instancia="inst-abc", ativo=True)
    return {"contatos": contatos, "posts": posts}


def _dois_contatos_no_mesmo_telefone(mundo):
    mundo["contatos"] += [
        {"id": LEAD_A, "site_id": SITE, "nome": "Ana Souza", "email": "ana@exemplo.com", "telefone": "(11) 98888-7777"},
        {"id": LEAD_B, "site_id": SITE, "nome": "Bia Lima", "email": "bia@exemplo.com", "telefone": "11988887777"},
        {"id": LEAD_C, "site_id": SITE, "nome": "Carla Dias", "email": "carla@exemplo.com",
         "telefone": "(21) 97777-1111"},
    ]


def _upsert(cliente, texto="Oi, vocês vendem o quê?", ident="ABC1", **extra):
    item = {"key": {"remoteJid": "5511988887777@s.whatsapp.net", "fromMe": False, "id": ident},
            "message": {"conversation": texto}, "messageType": "conversation",
            "messageTimestamp": int(timezone.now().timestamp())}
    item.update(extra)
    corpo = {"event": "messages.upsert", "instance": "inst-abc", "data": item}
    return cliente.post("/webhooks/whatsapp", json.dumps(corpo), content_type="application/json",
                        HTTP_X_WEBHOOK_TOKEN="retorno-local")


def _api(cliente, caminho, token=LEITURA):
    return cliente.get("/api/mensageria" + caminho, HTTP_AUTHORIZATION=f"Bearer {token}").json()


def _saidas():
    return list(MensagemDaConversa.objects.filter(direcao="saida").order_by("criada_em"))


def test_desconhecido_recebe_uma_orientacao_e_a_segunda_fala_em_24h_nao_gera_outra(mundo):
    mundo["contatos"].append({"id": LEAD_C, "site_id": SITE, "nome": "Carla Dias", "email": "carla@exemplo.com",
                              "telefone": "(21) 97777-1111"})
    OrientacaoDoSite.objects.create(site_id=SITE, endereco_quiz="https://meusite.exemplo/quiz",
                                    atendimento_geral="escreva para ajuda@meusite.exemplo")
    cliente = Client()
    assert _upsert(cliente, ident="D1").json() == {"recebidas": 1}
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "desconhecida" and conversa.lead_id == ""
    saidas = _saidas()
    assert len(saidas) == 1 and len(mundo["posts"]) == 1
    assert (saidas[0].autor, saidas[0].autor_id) == ("sistema", "orientacao:desconhecida")
    texto = saidas[0].texto
    assert "assistente da equipe" in texto and "quem fez o quiz" in texto
    assert "https://meusite.exemplo/quiz" in texto and "ajuda@meusite.exemplo" in texto
    assert not any(segredo in texto for segredo in SEGREDOS)
    # Segunda fala dentro de 24h: fica na caixa, sem outra orientação.
    _upsert(cliente, texto="Alô?", ident="D2")
    assert len(_saidas()) == 1 and len(mundo["posts"]) == 1
    # Etiqueta e orientação na API, sem dado de lead; fora da lista comercial; nenhum contato criado.
    detalhe = _api(cliente, f"/conversas/{conversa.id}?site_id={SITE}")
    assert detalhe["etiqueta"] == "sem_origem_quiz" and detalhe["lead_id"] is None
    assert detalhe["orientacao"]["tipo"] == "desconhecida"
    lista = _api(cliente, f"/conversas?site_id={SITE}&ligacao=desconhecida")
    assert [c["etiqueta"] for c in lista["itens"]] == ["sem_origem_quiz"]
    assert _api(cliente, f"/conversas?site_id={SITE}")["itens"] == []
    # Passadas 24h e com uma fala nova, orienta de novo (no máximo uma a cada 24h).
    Conversa.objects.filter(pk=conversa.pk).update(orientacao_enviada_em=timezone.now() - timedelta(hours=25))
    _upsert(cliente, texto="Voltei", ident="D3")
    assert len(_saidas()) == 2


def test_sem_endereco_cadastrado_a_orientacao_vai_sem_link_e_sem_inventar_contato(mundo):
    _upsert(Client(), ident="S1")
    texto = _saidas()[0].texto
    assert "http" not in texto and "no nosso site" in texto and "caixa de entrada da equipe" in texto


def test_orientacao_de_madrugada_e_resposta_e_nao_passa_pelo_horario(mundo, monkeypatch):
    madrugada = timezone.localtime(timezone.now()).replace(hour=3, minute=0, second=0, microsecond=0)
    monkeypatch.setattr("apps.conversas.envio._agora", lambda: madrugada)
    _upsert(Client(), ident="N1")
    assert len(_saidas()) == 1 and len(mundo["posts"]) == 1


def test_parar_de_desconhecido_nao_recebe_nada(mundo):
    _upsert(Client(), texto="PARAR", ident="P1")
    assert not _saidas() and not mundo["posts"]
    assert Descadastro.objects.count() == 1


def test_quem_pediu_parar_depois_de_ser_orientado_nao_recebe_mais(mundo):
    cliente = Client()
    _upsert(cliente, texto="oi", ident="P1")
    assert len(_saidas()) == 1
    _upsert(cliente, texto="Sair", ident="P2")
    assert len(_saidas()) == 1 and len(mundo["posts"]) == 1


def test_conversa_assumida_por_pessoa_nao_recebe_orientacao(mundo):
    Conversa.objects.create(site_id=SITE, canal="whatsapp", endereco="5511988887777", ligacao="desconhecida",
                            estado="pessoa", assumida_por="ana-da-equipe")
    _upsert(Client(), ident="A1")
    assert not _saidas() and not mundo["posts"]


def test_historico_antigo_nao_gera_orientacao(mundo):
    _upsert(Client(), ident="H1", messageTimestamp=int((timezone.now() - timedelta(days=3)).timestamp()))
    assert not _saidas() and not mundo["posts"]


def test_ambigua_pede_o_email_e_nunca_vaza_dado_de_outro_contato(mundo):
    _dois_contatos_no_mesmo_telefone(mundo)
    cliente = Client()
    _upsert(cliente, texto="Oi, comprei o curso", ident="B1")
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ambigua" and conversa.lead_id == ""
    saidas = _saidas()
    assert len(saidas) == 1 and saidas[0].autor_id == "orientacao:ambigua"
    assert "o e-mail que você usou no quiz" in saidas[0].texto
    api = (_api(cliente, f"/conversas/{conversa.id}?site_id={SITE}"),
           _api(cliente, f"/conversas/{conversa.id}/mensagens?site_id={SITE}"),
           _api(cliente, f"/conversas?site_id={SITE}&ligacao=ambigua"))
    cru = " ".join(d["text"] for _, d in mundo["posts"]) + saidas[0].texto + json.dumps(api, ensure_ascii=False)
    assert not [s for s in SEGREDOS if s in cru], [s for s in SEGREDOS if s in cru]
    assert api[0]["etiqueta"] == "telefone_ambiguo" and api[0]["lead_id"] is None
    _upsert(cliente, texto="E aí?", ident="B2")  # sem e-mail, dentro de 24h: não pergunta de novo
    assert len(_saidas()) == 1


def test_email_que_casa_com_um_unico_lead_de_telefone_igual_liga_a_conversa(mundo):
    _dois_contatos_no_mesmo_telefone(mundo)
    cliente = Client()
    _upsert(cliente, texto="Oi", ident="E1")
    _upsert(cliente, texto="Meu e-mail é Ana@Exemplo.com, obrigada", ident="E2")
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ligada" and conversa.lead_id == LEAD_A and not conversa.equipe_confirma
    assert len(_saidas()) == 1  # só o pedido: agora quem responde é o atendimento, com o contexto certo
    evento = OutboxEvent.objects.filter(event="mensagem.recebida").order_by("-id").first()
    assert evento.payload["lead_ligacao"] == "ligada" and evento.payload["lead"] == LEAD_A
    assert _api(cliente, f"/conversas/{conversa.id}?site_id={SITE}")["etiqueta"] is None


def test_email_sem_casamento_deixa_a_equipe_confirmar_sem_dizer_se_existe(mundo):
    _dois_contatos_no_mesmo_telefone(mundo)
    cliente = Client()
    _upsert(cliente, texto="Oi", ident="Q1")
    _upsert(cliente, texto="é naoexiste@exemplo.com", ident="Q2")
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ambigua" and conversa.lead_id == "" and conversa.equipe_confirma
    saidas = _saidas()
    assert [m.autor_id for m in saidas] == ["orientacao:ambigua", "orientacao:confirmacao"]
    assert "equipe confirmar" in saidas[1].texto
    assert not any(segredo in s.texto for s in saidas for segredo in SEGREDOS)
    detalhe = _api(cliente, f"/conversas/{conversa.id}?site_id={SITE}")
    assert detalhe["etiqueta"] == "equipe_confirma" and detalhe["lead_id"] is None
    _upsert(cliente, texto="ana@exemplo.com", ident="Q3")  # outro e-mail depois: nada muda sozinho
    assert Conversa.objects.get().ligacao == "ambigua" and len(_saidas()) == 2


def test_email_de_outro_contato_com_telefone_diferente_nao_liga(mundo):
    """Quem digita o e-mail da Carla não vira a Carla: o telefone dela não bate com o da conversa."""
    _dois_contatos_no_mesmo_telefone(mundo)
    cliente = Client()
    _upsert(cliente, texto="Oi", ident="X1")
    _upsert(cliente, texto="carla@exemplo.com", ident="X2")
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ambigua" and conversa.lead_id == "" and conversa.equipe_confirma
    assert not any(segredo in s.texto for s in _saidas() for segredo in SEGREDOS)


def test_email_de_lead_sem_telefone_cadastrado_fica_para_a_equipe(mundo):
    _dois_contatos_no_mesmo_telefone(mundo)
    mundo["contatos"].append({"id": LEAD_D, "site_id": SITE, "nome": "Dani", "email": "dani@exemplo.com",
                              "telefone": ""})
    cliente = Client()
    _upsert(cliente, texto="Oi", ident="Y1")
    _upsert(cliente, texto="dani@exemplo.com", ident="Y2")
    conversa = Conversa.objects.get()
    assert conversa.ligacao == "ambigua" and conversa.lead_id == "" and conversa.equipe_confirma


def test_email_com_a_celula_de_leads_fora_do_ar_fica_para_a_equipe(mundo, monkeypatch):
    _dois_contatos_no_mesmo_telefone(mundo)
    cliente = Client()
    _upsert(cliente, texto="Oi", ident="Z1")
    monkeypatch.setattr("apps.conversas.leads.httpx.get", lambda *a, **k: Resposta(503, {}))
    _upsert(cliente, texto="ana@exemplo.com", ident="Z2")
    conversa = Conversa.objects.get()
    assert conversa.lead_id == "" and conversa.ligacao != "ligada"


def test_orientacao_que_nao_saiu_tenta_de_novo_na_proxima_fala(mundo, monkeypatch):
    def gateway_fora(metodo, caminho, dados=None):
        if metodo == "GET":
            return {"instance": {"state": "open"}}
        raise ConnectionError("gateway fora")

    certo = __import__("apps.whatsapp.service", fromlist=["x"])._gateway
    monkeypatch.setattr("apps.whatsapp.service._gateway", gateway_fora)
    cliente = Client()
    _upsert(cliente, ident="R1")
    assert Conversa.objects.get().orientacao_enviada_em is None
    monkeypatch.setattr("apps.whatsapp.service._gateway", certo)
    _upsert(cliente, texto="oi de novo", ident="R2")
    assert Conversa.objects.get().orientacao_enviada_em is not None
    assert len(mundo["posts"]) == 1


def test_porta_das_orientacoes_do_site(mundo):
    cliente = Client()
    corpo = {"endereco_quiz": "https://meusite.exemplo/quiz", "atendimento_geral": "ajuda@meusite.exemplo"}

    def gravar(token, dados=corpo):
        return cliente.put("/api/mensageria/orientacoes/" + SITE, json.dumps(dados),
                           content_type="application/json", HTTP_AUTHORIZATION=f"Bearer {token}")

    assert gravar(LEITURA).status_code == 403
    assert gravar(ESCRITA, {"endereco_quiz": "meusite.exemplo"}).status_code == 422
    assert gravar(ESCRITA).json() == {"site_id": SITE, **corpo}
    assert _api(cliente, "/orientacoes/" + SITE) == {"site_id": SITE, **corpo}
    assert _api(cliente, "/orientacoes/outro") == {"site_id": "outro", "endereco_quiz": "", "atendimento_geral": ""}
