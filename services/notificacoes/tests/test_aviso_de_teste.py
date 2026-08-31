"""O comando de diagnóstico do canal — o que o mantenedor roda na VPS.

Ele fala com o celular de outra pessoa, então a ordem importa: **ver antes de
agir**. Sem argumento nenhum ele conta quem está inscrito e não envia nada;
enviar exige escrever `--para` ou `--todos` à mão.

Os quatro modos de falha que este arquivo mede são os que fariam o mantenedor
tirar a conclusão errada de uma tela de terminal:

1. mandar sem querer (o comando "só de olhar" enviando de verdade);
2. dizer que enviou quando não há chave configurada — o canal inteiro está
   desligado e a tela precisa dizer isso, não ficar em silêncio;
3. dizer que enviou quando o servidor de push recusou;
4. deixar no banco um aparelho que o fabricante já declarou morto.
"""

import pytest
from django.core.management import call_command
from io import StringIO

from apps.notificacoes.models import InscricaoPush
from tests.conftest import ALGUEM, OUTRA, SITE

# Comprido de propósito: um endereço curto caberia inteiro no corte da tela
# e o guarda do fim deste arquivo passaria sem medir nada. Os endereços
# reais dos fabricantes têm bem mais que 40 caracteres.
ENDERECO = "https://fcm.googleapis.com/fcm/send/" + "k" * 120


def inscrever(destinatario=ALGUEM, endpoint=ENDERECO, site=SITE):
    return InscricaoPush.objects.create(
        site_id=site,
        destinatario_id=destinatario,
        endpoint=endpoint,
        p256dh="BLc4xRz" + "P" * 80,
        auth="tBHItJI5svbpez7KI4CCQ",
    )


def rodar(*args, **kwargs):
    saida = StringIO()
    call_command("aviso_de_teste", *args, stdout=saida, **kwargs)
    return saida.getvalue()


class EnvioDublado:
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
    def __init__(self, status):
        super().__init__(f"servidor de push respondeu {status}")
        self.response = RespostaDoServidor(status)


@pytest.fixture
def com_chave(settings):
    settings.VAPID_PRIVATE_KEY = "chave-privada-de-teste"
    settings.VAPID_SUBJECT = "mailto:contato@exemplo.com"


@pytest.mark.django_db
def test_sem_ninguem_inscrito_ele_diz_isso_com_todas_as_letras():
    """A resposta à pergunta que motivou o comando: um aviso de teste não
    chega a lugar nenhum quando ninguém ligou os avisos."""
    saida = rodar()

    assert "nenhum" in saida
    assert "ligou os avisos" in saida


@pytest.mark.django_db
def test_so_de_olhar_ele_nao_envia(monkeypatch, com_chave):
    """O modo padrão é contar, nunca disparar: quem roda um comando para ver
    quem está inscrito não pode acordar o celular de ninguém por isso."""
    inscrever()
    envio = EnvioDublado()
    monkeypatch.setattr("pywebpush.webpush", envio)

    saida = rodar()

    assert envio.chamadas == []
    assert "NADA FOI ENVIADO" in saida


@pytest.mark.django_db
def test_com_para_ele_envia_so_para_aquela_pessoa(monkeypatch, com_chave):
    inscrever(destinatario=ALGUEM)
    inscrever(destinatario=OUTRA, endpoint="https://push.exemplo.com/de-outra")
    envio = EnvioDublado()
    monkeypatch.setattr("pywebpush.webpush", envio)

    saida = rodar("--para", ALGUEM)

    assert [c["subscription_info"]["endpoint"] for c in envio.chamadas] == [ENDERECO]
    assert "enviados: 1" in saida


@pytest.mark.django_db
def test_sem_chave_ele_avisa_em_vez_de_fingir(monkeypatch, settings):
    """O canal inteiro está desligado. Silêncio aqui faria o mantenedor
    concluir que o problema é o celular do aluno."""
    settings.VAPID_PRIVATE_KEY = ""
    settings.VAPID_SUBJECT = ""
    inscrever()
    envio = EnvioDublado()
    monkeypatch.setattr("pywebpush.webpush", envio)

    saida = rodar("--todos")

    assert envio.chamadas == []
    assert "NADA FOI ENVIADO" in saida
    assert "provisionar-aviso-no-celular.sh" in saida


@pytest.mark.django_db
def test_recusa_do_servidor_aparece_como_nao_saiu(monkeypatch, com_chave):
    inscrever()
    monkeypatch.setattr("pywebpush.webpush", EnvioDublado(erro=RecusaDoServidor(429)))

    saida = rodar("--todos")

    assert "NÃO saiu" in saida
    assert "enviados: 0" in saida
    assert InscricaoPush.objects.count() == 1  # 429 não é aparelho morto


@pytest.mark.django_db
def test_aparelho_morto_sai_do_banco_tambem_no_teste(monkeypatch, com_chave):
    """A mesma limpeza da entrega real. Um comando de diagnóstico que deixasse
    lixo para trás criaria a diferença entre 'o que o teste vê' e 'o que a
    entrega faz', que é o pior defeito possível numa ferramenta de teste."""
    inscrever()
    monkeypatch.setattr("pywebpush.webpush", EnvioDublado(erro=RecusaDoServidor(410)))

    saida = rodar("--todos")

    assert "aparelho sumiu" in saida
    assert InscricaoPush.objects.count() == 0


@pytest.mark.django_db
def test_o_teste_nao_grava_carta_na_caixa_de_ninguem(monkeypatch, com_chave):
    """Teste de canal não pode sujar a caixa de avisos de quem recebe."""
    from apps.notificacoes.models import Notificacao

    inscrever()
    monkeypatch.setattr("pywebpush.webpush", EnvioDublado())

    rodar("--todos")

    assert Notificacao.objects.count() == 0


@pytest.mark.django_db
def test_o_endereco_do_aparelho_sai_cortado_na_tela(monkeypatch, com_chave):
    """O que vai para o terminal vai para o print que o mantenedor manda e
    para o histórico do shell (`armadilhas/090`). O endereço do aparelho é
    opaco, mas ainda é um identificador."""
    inscrever()

    saida = rodar()

    assert ENDERECO not in saida
    assert ENDERECO[:40] in saida
