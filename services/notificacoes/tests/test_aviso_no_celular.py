"""O aviso na tela do aparelho — o canal novo (Fase 7, 31/08/2026).

A regra que manda em tudo, e que quase todo teste aqui mede de um ângulo
diferente: **a carta gravada é a verdade durável; o push é o espelho dela.**
Servidor de push fora do ar, chave ausente, aparelho que sumiu, biblioteca
faltando: nada disso pode derrubar o consumidor do fio nem impedir a carta de
ser gravada. Um teste por modo de falha, nunca um genérico "o push quebrou".

**Nenhum teste daqui fala com um servidor de push de verdade.** O que se mede é
a DECISÃO desta célula (mandou? apagou? deixou a carta em paz?), e para isso o
`webpush` é dublado — mesma disciplina do Redis dublado no `conftest.py`.
"""

import json

import pytest

from apps.notificacoes import push
from apps.notificacoes.handlers import ao_notificacao_devida
from apps.notificacoes.models import InscricaoPush, Notificacao
from apps.notificacoes.services import (
    avisar_os_aparelhos,
    esquecer_aparelho,
    inscrever_aparelho,
)
from tests.conftest import ALGUEM, OUTRA, SITE, cabecalho_bearer

ENDERECO = "https://push.exemplo.com/aparelho/abc123"
OUTRO_ENDERECO = "https://push.exemplo.com/aparelho/xyz789"
CHAVE_DO_APARELHO = "BLc4xRz" + "P" * 80
SEGREDO_DO_APARELHO = "tBHItJI5svbpez7KI4CC" + "Q"


def inscrever(**mudancas):
    dados = {
        "site_id": SITE,
        "destinatario_id": ALGUEM,
        "endpoint": ENDERECO,
        "p256dh": CHAVE_DO_APARELHO,
        "auth": SEGREDO_DO_APARELHO,
    }
    dados.update(mudancas)
    return inscrever_aparelho(**dados)


class EnvioDublado:
    """O `webpush` da biblioteca, sem rede. Guarda o que foi mandado."""

    def __init__(self, erro=None):
        self.chamadas = []
        self.erro = erro

    def __call__(self, **kwargs):
        self.chamadas.append(kwargs)
        if self.erro is not None:
            raise self.erro


class RespostaDoServidor:
    def __init__(self, status_code):
        self.status_code = status_code


class RecusaDoServidor(Exception):
    """A forma da `WebPushException`: uma exceção com `.response.status_code`.

    Dublada pela FORMA e não importada da biblioteca, de propósito: é assim
    que `push.py` a lê (por atributo, nunca por tipo), e um dublê fiel à forma
    prova que aquela leitura funciona.
    """

    def __init__(self, status):
        super().__init__(f"servidor de push respondeu {status}")
        self.response = RespostaDoServidor(status)


@pytest.fixture
def com_chave(settings):
    """A plataforma com o segredo instalado — o estado depois do passo do
    mantenedor na VPS. Sem esta fixture, o estado é o de HOJE: sem chave."""
    settings.VAPID_PRIVATE_KEY = "chave-privada-de-teste"
    settings.VAPID_SUBJECT = "mailto:contato@exemplo.com"
    settings.VAPID_PUBLIC_KEY = "chave-publica-de-teste"


@pytest.fixture
def envio(monkeypatch, com_chave):
    dublê = EnvioDublado()
    monkeypatch.setattr("pywebpush.webpush", dublê)
    return dublê


# ---------------------------------------------------------------------------
# Guardar o aparelho
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_inscrever_o_mesmo_aparelho_de_novo_nao_cria_uma_segunda_linha():
    """O navegador reemite a inscrição sozinho, de tempos em tempos. Sem esta
    regra um mesmo celular viraria dezenas de linhas e receberia o mesmo aviso
    dezenas de vezes."""
    assert inscrever() is False  # não estava inscrito
    assert inscrever() is True  # já estava

    assert InscricaoPush.objects.count() == 1


@pytest.mark.django_db
def test_o_mesmo_aparelho_com_outra_pessoa_troca_de_dono():
    """Um celular emprestado, ou uma segunda conta no mesmo aparelho. Manter o
    dono antigo mandaria o aviso de uma pessoa para o aparelho de outra, e isso
    não é reversível depois de acontecer."""
    inscrever()
    inscrever(destinatario_id=OUTRA)

    assert InscricaoPush.objects.count() == 1
    assert InscricaoPush.objects.get().destinatario_id == OUTRA


@pytest.mark.django_db
def test_dois_aparelhos_da_mesma_pessoa_sao_duas_linhas():
    inscrever()
    inscrever(endpoint=OUTRO_ENDERECO)

    assert InscricaoPush.objects.filter(destinatario_id=ALGUEM).count() == 2


@pytest.mark.django_db
def test_esquecer_apaga_e_e_idempotente():
    inscrever()

    assert esquecer_aparelho(site_id=SITE, endpoint=ENDERECO) is True
    assert esquecer_aparelho(site_id=SITE, endpoint=ENDERECO) is False
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
def test_esquecer_nao_alcanca_o_aparelho_de_outro_site():
    """Lei 9: nada atravessa sites, nem para apagar."""
    inscrever()

    assert esquecer_aparelho(site_id="outro-site", endpoint=ENDERECO) is False
    assert InscricaoPush.objects.count() == 1


# ---------------------------------------------------------------------------
# A porta HTTP
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_porta_inscreve_e_responde_como_o_contrato_promete(client, par_autorizado):
    resposta = client.post(
        "/api/notificacoes/inscricoes-push",
        data=json.dumps(
            {
                "site_id": SITE,
                "destinatario_id": ALGUEM,
                "endpoint": ENDERECO,
                "p256dh": CHAVE_DO_APARELHO,
                "auth": SEGREDO_DO_APARELHO,
            }
        ),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"ja_estava_inscrito": False}
    assert InscricaoPush.objects.count() == 1


@pytest.mark.django_db
def test_a_porta_esquece_o_aparelho(client, par_autorizado):
    inscrever()

    resposta = client.delete(
        "/api/notificacoes/inscricoes-push",
        data=json.dumps({"site_id": SITE, "endpoint": ENDERECO}),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )

    assert resposta.status_code == 200
    assert resposta.json() == {"existia": True}
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "faltando", ["site_id", "destinatario_id", "endpoint", "p256dh", "auth"]
)
def test_campo_obrigatorio_ausente_e_422_e_nao_500(client, par_autorizado, faltando):
    corpo = {
        "site_id": SITE,
        "destinatario_id": ALGUEM,
        "endpoint": ENDERECO,
        "p256dh": CHAVE_DO_APARELHO,
        "auth": SEGREDO_DO_APARELHO,
    }
    del corpo[faltando]

    resposta = client.post(
        "/api/notificacoes/inscricoes-push",
        data=json.dumps(corpo),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )

    assert resposta.status_code == 422
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
def test_endpoint_gigante_e_recusado_antes_do_banco(client, par_autorizado):
    """O contrato declara `maxLength: 2048`. Sem a cerca na borda, o valor
    chegaria à coluna e estouraria como erro 500 — onde o contrato promete um
    422 legível."""
    resposta = client.post(
        "/api/notificacoes/inscricoes-push",
        data=json.dumps(
            {
                "site_id": SITE,
                "destinatario_id": ALGUEM,
                "endpoint": "https://push.exemplo.com/" + "a" * 3000,
                "p256dh": CHAVE_DO_APARELHO,
                "auth": SEGREDO_DO_APARELHO,
            }
        ),
        content_type="application/json",
        headers=cabecalho_bearer(),
    )

    assert resposta.status_code == 422
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
def test_a_porta_exige_o_token_do_par(client):
    resposta = client.post(
        "/api/notificacoes/inscricoes-push",
        data=json.dumps({"site_id": SITE}),
        content_type="application/json",
    )

    assert resposta.status_code == 401
    assert InscricaoPush.objects.count() == 0


# ---------------------------------------------------------------------------
# O envio
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_sem_chave_vapid_nao_sai_aviso_e_nada_quebra(settings):
    """O estado de HOJE, enquanto o segredo não está instalado no servidor: o
    canal simplesmente não existe, e a caixa funciona igual."""
    settings.VAPID_PRIVATE_KEY = ""
    settings.VAPID_SUBJECT = ""
    inscrever()

    assert (
        avisar_os_aparelhos(
            site_id=SITE, destinatario_id=ALGUEM, assunto="a", parametros={}
        )
        == 0
    )
    assert InscricaoPush.objects.count() == 1  # e o aparelho continua guardado


@pytest.mark.django_db
def test_o_aviso_vai_para_todos_os_aparelhos_daquela_pessoa(envio):
    inscrever()
    inscrever(endpoint=OUTRO_ENDERECO)
    inscrever(destinatario_id=OUTRA, endpoint="https://push.exemplo.com/de-outra")

    enviados = avisar_os_aparelhos(
        site_id=SITE,
        destinatario_id=ALGUEM,
        assunto="sugestao.status-alterado",
        parametros={"suggestion_id": "731"},
    )

    assert enviados == 2
    alvos = {c["subscription_info"]["endpoint"] for c in envio.chamadas}
    assert alvos == {ENDERECO, OUTRO_ENDERECO}


@pytest.mark.django_db
def test_o_que_viaja_e_dado_nunca_frase_pronta(envio):
    """`DECISAO-notificacoes` §5.1, medida no conteúdo que sai: assunto e
    parâmetros. A frase nasce no aparelho, no idioma de quem lê — gravar ou
    enviar texto pronto congelaria o idioma de quem escreveu."""
    inscrever()

    avisar_os_aparelhos(
        site_id=SITE,
        destinatario_id=ALGUEM,
        assunto="sugestao.status-alterado",
        parametros={"suggestion_id": "731"},
    )

    conteudo = json.loads(envio.chamadas[0]["data"])
    assert conteudo == {
        "assunto": "sugestao.status-alterado",
        "parametros": {"suggestion_id": "731"},
    }


@pytest.mark.django_db
def test_o_aviso_nao_atravessa_sites(envio):
    """Lei 9 de novo, agora no envio: a mesma pessoa em dois sites tem dois
    conjuntos de aparelhos, e um aviso de um site nunca acorda o outro."""
    inscrever()
    inscrever(site_id="outro-site", endpoint=OUTRO_ENDERECO)

    avisar_os_aparelhos(
        site_id=SITE, destinatario_id=ALGUEM, assunto="a", parametros={}
    )

    assert [c["subscription_info"]["endpoint"] for c in envio.chamadas] == [ENDERECO]


@pytest.mark.django_db
@pytest.mark.parametrize("status", [404, 410])
def test_aparelho_que_sumiu_sai_do_banco_na_hora(monkeypatch, com_chave, status):
    """A única limpeza automática desta tabela, e ela precisa existir: sem ela,
    todo celular que desinstalar o app ficaria para sempre, e o custo de cada
    carta cresceria com o número de aparelhos que já não existem."""
    inscrever()
    monkeypatch.setattr(
        "pywebpush.webpush", EnvioDublado(erro=RecusaDoServidor(status))
    )

    enviados = avisar_os_aparelhos(
        site_id=SITE, destinatario_id=ALGUEM, assunto="a", parametros={}
    )

    assert enviados == 0
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
def test_recusa_temporaria_do_servidor_nao_apaga_o_aparelho(monkeypatch, com_chave):
    """429 (peça devagar) e 500 (o servidor deles tropeçou) não são o aparelho
    dizendo que sumiu. Apagar aqui perderia a inscrição de alguém por causa de
    um mau minuto do fabricante."""
    inscrever()
    monkeypatch.setattr("pywebpush.webpush", EnvioDublado(erro=RecusaDoServidor(429)))

    assert (
        avisar_os_aparelhos(
            site_id=SITE, destinatario_id=ALGUEM, assunto="a", parametros={}
        )
        == 0
    )
    assert InscricaoPush.objects.count() == 1


@pytest.mark.django_db
def test_rede_caida_nao_levanta_e_nao_apaga_nada(monkeypatch, com_chave):
    """Falha SEM `.response` — um timeout, um DNS que não resolve. É o caso em
    que uma exceção escaparia e derrubaria o consumidor do fio."""
    inscrever()
    monkeypatch.setattr("pywebpush.webpush", EnvioDublado(erro=OSError("a rede sumiu")))

    assert (
        avisar_os_aparelhos(
            site_id=SITE, destinatario_id=ALGUEM, assunto="a", parametros={}
        )
        == 0
    )
    assert InscricaoPush.objects.count() == 1


# ---------------------------------------------------------------------------
# O elo com o fio: a carta primeiro, o espelho depois
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_a_carta_chega_e_o_aparelho_e_avisado(envio, carta):
    inscrever()
    envelope = carta(destinatario_id=ALGUEM)

    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])

    assert Notificacao.objects.count() == 1
    assert len(envio.chamadas) == 1


@pytest.mark.django_db
def test_push_quebrado_nao_impede_a_carta_de_ser_gravada(monkeypatch, com_chave, carta):
    """O guarda central deste canal. Se este teste ficar vermelho, um servidor
    de push fora do ar passa a significar aviso PERDIDO — e não é isso que esta
    plataforma promete."""
    inscrever()
    monkeypatch.setattr(
        "pywebpush.webpush", EnvioDublado(erro=RuntimeError("tudo deu errado"))
    )
    envelope = carta(destinatario_id=ALGUEM)

    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])

    assert Notificacao.objects.count() == 1


@pytest.mark.django_db
def test_sem_a_biblioteca_instalada_a_caixa_continua_funcionando(
    monkeypatch, com_chave, carta
):
    """O modo de falha que um `import` no topo do arquivo criaria: a célula
    inteira parando por causa de uma dependência que só o canal mais novo usa."""
    inscrever()

    import builtins

    original = builtins.__import__

    def sem_pywebpush(nome, *args, **kwargs):
        if nome == "pywebpush":
            raise ImportError("pywebpush não está instalado")
        return original(nome, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", sem_pywebpush)
    envelope = carta(destinatario_id=ALGUEM)

    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])

    assert Notificacao.objects.count() == 1


def test_esta_configurado_exige_as_duas_metades(settings):
    """Meia configuração é configuração nenhuma: com a chave e sem o `sub`, o
    servidor de push recusaria toda entrega, e a célula acharia que está
    enviando."""
    settings.VAPID_PRIVATE_KEY = "só a chave"
    settings.VAPID_SUBJECT = ""
    assert push.esta_configurado() is False

    settings.VAPID_SUBJECT = "mailto:contato@exemplo.com"
    assert push.esta_configurado() is True
