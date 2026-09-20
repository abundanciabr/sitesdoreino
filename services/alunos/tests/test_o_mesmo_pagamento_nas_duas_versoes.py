# tests/test_o_mesmo_pagamento_nas_duas_versoes.py
"""O aviso de pagamento chega em DUAS versões, e a pessoa vira aluna UMA vez.

`pagamento.aprovado.v1` e `pagamento.aprovado.v2` descrevem o mesmo fato do
mundo com campos diferentes: o v1 diz `site_id` e `mp_payment_id`, o v2 diz
`platform_site_id` e o par `provider` mais `provider_reference_id`. Enquanto os
dois estiverem no ar (RITOS.md §3: o v1 só sai quando o último consumidor
migrar), a MESMA compra pode chegar aqui nas duas formas, com `event_id`
diferente em cada uma. O dedup por `event_id` não enxerga isso: para ele são
dois eventos.

O modo de falhar é silencioso, e é o pior desta célula: ninguém recebe erro,
ninguém abre chamado, e a pessoa aparece matriculada duas vezes no relatório do
mês. Por isso a identidade que vale aqui não é a do envelope, é a do FATO.

Quem dita essa identidade é o contrato, no campo `x-ponte-do-v1` de
`contracts/eventos/pagamento.aprovado.v2.json`, e ela não é a mesma para todos
os avisos da família: no `pagamento.aprovado` o fato é o par (`provider`,
`provider_reference_id`), porque o `mp_payment_id` do v1 é o mesmo valor com
`provider` implícito igual a `mercadopago`; no `pagamento.recusado` o v1 nunca
carregou referência de provedor nenhuma, e quem atravessa as duas versões é o
`payment_id`. Copiar a regra de um para o outro é o erro que este arquivo torna
impossível: `test_a_ponte_e_copia_fiel_do_contrato` compara a tabela do código
com o contrato, campo a campo.

Estes testes falam com um Redis REAL na parte de concorrência
(`REDIS_STREAMS_URL`), pelo mesmo motivo de `test_reentrega_pel.py`: duas
entregas simultâneas do mesmo fato é o caso que mais assusta, e ele não existe
em mock nenhum.
"""
import json
import threading
import uuid
from pathlib import Path

import jsonschema
import pytest
import redis
from django.db import connection

from apps.eventos.management.commands.consume_eventos import (
    CONSUMIDOR,
    GRUPO,
    HANDLERS,
    PONTE_DO_V1,
    VersaoDesconhecida,
    dados_na_forma_do_v2,
    identidade_do_fato,
    processar_envelope,
)
from apps.eventos.models import EventoProcessado
from apps.matriculas.models import Matricula

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"

SITE = "escola-a"
PEDIDO = "pedido-77"
REFERENCIA_NO_PROVEDOR = "MP-REF-77"
PRODUTO = "22222222-2222-4222-8222-222222222222"
COMPRADOR = {"email": "aluna@exemplo.com.br", "name": "Aluna Exemplo"}


def _v1(*, site=SITE, pedido=PEDIDO, referencia=REFERENCIA_NO_PROVEDOR) -> dict:
    """A MESMA compra de `_v2`, na forma antiga. Validado contra o contrato em
    `test_os_envelopes_de_exemplo_batem_com_os_contratos` — sem isso o arquivo
    inteiro poderia estar medindo um evento que ninguém emite."""
    return {
        "event": "pagamento.aprovado",
        "version": 1,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-20T12:00:00Z",
        "data": {
            "site_id": site,
            "payment_id": f"pay-{pedido}",
            "order_id": pedido,
            "amount_cents": 19700,
            "method": "card",
            "mp_payment_id": referencia,
            "product_id": PRODUTO,
            "customer": dict(COMPRADOR),
        },
    }


def _v2(*, site=SITE, pedido=PEDIDO, referencia=REFERENCIA_NO_PROVEDOR) -> dict:
    return {
        "event": "pagamento.aprovado",
        "version": 2,
        "event_id": str(uuid.uuid4()),
        "occurred_at": "2026-09-20T12:00:00Z",
        "data": {
            "platform_site_id": site,
            "payment_id": f"pay-{pedido}",
            "order_id": pedido,
            "amount_cents": 19700,
            "method": "card",
            "provider": "mercadopago",
            "provider_reference_id": referencia,
            "product_id": PRODUTO,
            "customer": dict(COMPRADOR),
        },
    }


def _contando(contador: list):
    """O handler REAL, com um contador em volta.

    Medir só `Matricula.objects.count() == 1` não prova nada aqui: `matricular()`
    já é idempotente por `order_id`, então o contador de matrículas fica em 1
    mesmo com o handler rodando duas vezes. O que esta tarefa acrescenta é o
    fato ser reconhecido como UM, e o efeito rodar UMA vez — é isso que esta
    contagem mede, e é ela que reprova quando a ponte entre as versões some.
    """

    def rodar(dados: dict) -> None:
        contador.append(dados)
        HANDLERS["pagamento.aprovado"](dados)

    return {"pagamento.aprovado": rodar}


# ---------------------------------------------------------------- o contrato


def _ponte_do_contrato(evento: str) -> dict:
    schema = json.loads((CONTRATOS / f"{evento}.v2.json").read_text(encoding="utf-8"))
    return schema["x-ponte-do-v1"]


def test_a_ponte_e_copia_fiel_do_contrato():
    """A tabela do código é uma CÓPIA do contrato, e este guarda prova que ela
    não derivou. Quem alterar `x-ponte-do-v1` sem alterar o código (ou o
    contrário) reprova aqui, em vez de deduplicar pela chave errada em
    produção."""
    for evento in PONTE_DO_V1:
        do_contrato = _ponte_do_contrato(evento)
        assert PONTE_DO_V1[evento] == {
            "chave_entre_versoes": do_contrato["chave_entre_versoes"],
            "no_v1": do_contrato["no_v1"],
        }, f"a ponte de {evento} no código não é a do contrato"


def test_todo_evento_consumido_declara_a_ponte():
    """A armadilha que este guarda fecha: alguém acrescenta
    `pagamento.recusado` a HANDLERS e herda, por descuido, a chave do
    `pagamento.aprovado`. São chaves DIFERENTES (o v1 da recusa nunca teve
    referência do provedor), e a herança silenciosa deduplicaria recusas de
    pagamentos distintos como se fossem a mesma."""
    sem_ponte = set(HANDLERS) - set(PONTE_DO_V1)
    assert not sem_ponte, (
        f"evento consumido sem ponte declarada: {sorted(sem_ponte)}. Copie o "
        "`x-ponte-do-v1` do contrato v2 desse evento para PONTE_DO_V1 — não "
        "reaproveite a chave de outro evento."
    )


def test_os_envelopes_de_exemplo_batem_com_os_contratos():
    """Controle positivo do arquivo inteiro: se os exemplos não forem eventos
    de verdade, todo o resto aqui mede uma fantasia."""
    for envelope, arquivo in (
        (_v1(), "pagamento.aprovado.v1.json"),
        (_v2(), "pagamento.aprovado.v2.json"),
    ):
        schema = json.loads((CONTRATOS / arquivo).read_text(encoding="utf-8"))
        jsonschema.validate(envelope, schema)


def test_o_v1_traduzido_carrega_os_valores_que_o_contrato_manda():
    """A ponte em forma de dado diz, para cada campo da chave, DE ONDE tirá-lo
    num evento v1: um caminho dentro do evento (`data.<campo>`) ou um valor
    literal. Este guarda executa essa instrução e confere que a tradução do
    código chegou no mesmo lugar."""
    envelope = _v1()
    do_contrato = _ponte_do_contrato("pagamento.aprovado")
    traduzido = dados_na_forma_do_v2(envelope)

    for campo in do_contrato["chave_entre_versoes"]:
        origem = do_contrato["no_v1"][campo]
        if origem.startswith("data."):
            esperado = envelope["data"][origem[len("data.") :]]
        else:
            esperado = origem
        assert traduzido[campo] == esperado, (
            f"o campo {campo} traduzido do v1 saiu {traduzido[campo]!r} e o "
            f"contrato manda {esperado!r} (origem declarada: {origem!r})"
        )


def test_o_v2_atravessa_a_traducao_sem_ser_alterado():
    envelope = _v2()
    assert dados_na_forma_do_v2(envelope) == envelope["data"]


def test_versao_desconhecida_nao_e_processada_em_silencio():
    """Um v3 tratado como se fosse v2 leria campos que podem ter mudado de nome
    e derivaria uma identidade errada: matrícula duplicada sem uma linha de log.
    A recusa sobe, a mensagem fica no PEL e o caminho da fila morta a recolhe."""
    envelope = _v2()
    envelope["version"] = 3

    with pytest.raises(VersaoDesconhecida):
        dados_na_forma_do_v2(envelope)


# ------------------------------------------------------- uma matrícula só


@pytest.mark.django_db
def test_so_o_v1_matricula_uma_vez():
    contador = []
    processar_envelope(_v1(), _contando(contador))

    assert len(contador) == 1
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1
    assert Matricula.objects.get(order_id=PEDIDO).site_id == SITE


@pytest.mark.django_db
def test_so_o_v2_matricula_uma_vez():
    contador = []
    processar_envelope(_v2(), _contando(contador))

    assert len(contador) == 1
    matricula = Matricula.objects.get(order_id=PEDIDO)
    assert matricula.site_id == SITE
    assert matricula.product_id == PRODUTO


@pytest.mark.django_db
def test_v1_e_depois_v2_do_mesmo_fato_matriculam_uma_vez():
    contador = []
    processar_envelope(_v1(), _contando(contador))
    processar_envelope(_v2(), _contando(contador))

    assert len(contador) == 1, (
        f"o efeito rodou {len(contador)} vezes para o mesmo pagamento. O v2 "
        "chegou com outro event_id e passou pelo dedup: a identidade do FATO "
        "tem que ser o par (provider, provider_reference_id), não o envelope."
    )
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1
    assert EventoProcessado.objects.count() == 1


@pytest.mark.django_db
def test_v2_e_depois_v1_do_mesmo_fato_matriculam_uma_vez():
    """Ordem invertida, e ela acontece de verdade: as duas versões saem por
    caminhos distintos e a fila não promete ordem nenhuma."""
    contador = []
    processar_envelope(_v2(), _contando(contador))
    processar_envelope(_v1(), _contando(contador))

    assert len(contador) == 1, (
        f"o efeito rodou {len(contador)} vezes. Na ordem invertida o v1 "
        "precisa ser reconhecido como o fato que o v2 já trouxe."
    )
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1
    assert EventoProcessado.objects.count() == 1


@pytest.mark.django_db
def test_reentrega_do_mesmo_v2_matricula_uma_vez():
    """Entrega at-least-once: a MESMA mensagem, com o mesmo event_id, chega de
    novo. O dedup por envelope já cobria isto no v1, e precisa continuar
    cobrindo no v2."""
    envelope = _v2()
    contador = []
    for _ in range(3):
        processar_envelope(envelope, _contando(contador))

    assert len(contador) == 1
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1
    assert EventoProcessado.objects.count() == 1


@pytest.mark.django_db
def test_pagamentos_diferentes_do_mesmo_provedor_nao_se_confundem():
    """Controle negativo: sem ele, uma identidade constante (ou vazia) deixaria
    todos os testes acima verdes e recusaria a segunda compra de verdade."""
    contador = []
    processar_envelope(
        _v1(pedido="pedido-78", referencia="MP-REF-78"), _contando(contador)
    )
    processar_envelope(
        _v2(pedido="pedido-79", referencia="MP-REF-79"), _contando(contador)
    )

    assert len(contador) == 2
    assert Matricula.objects.count() == 2
    assert EventoProcessado.objects.count() == 2


# --------------------------------------------- [INV-P11] a fronteira do site

OUTRA_ESCOLA = "escola-b"


@pytest.mark.django_db
def test_mesma_referencia_em_escolas_diferentes_sao_fatos_diferentes():
    """[INV-P11] O `provider_reference_id` é o id da cobrança NA CONTA DO
    FORNECEDOR, e cada escola tem a sua: duas podem receber a referência
    `12345` no mesmo dia, de compras que nada têm a ver uma com a outra.

    Sem o site na identidade, a segunda compra é lida como reentrega da
    primeira e descartada. A pessoa pagou, o dinheiro entrou, e a matrícula
    dela nunca acontece, sem erro em lugar nenhum.
    """
    contador = []
    processar_envelope(
        _v2(site=SITE, pedido="pedido-da-a", referencia="12345"), _contando(contador)
    )
    processar_envelope(
        _v2(site=OUTRA_ESCOLA, pedido="pedido-da-b", referencia="12345"),
        _contando(contador),
    )

    assert len(contador) == 2, (
        "a compra da segunda escola foi descartada como duplicada da primeira. "
        "A identidade do fato tem que nascer escopada pelo platform_site_id."
    )
    assert Matricula.objects.count() == 2
    assert {m.site_id for m in Matricula.objects.all()} == {SITE, OUTRA_ESCOLA}
    assert EventoProcessado.objects.count() == 2


@pytest.mark.django_db
def test_o_aviso_do_site_errado_nao_consome_a_identidade_do_certo():
    """A mesma falha pelo outro lado, e atravessando as versões: um aviso que
    chega com o site trocado (bug do publicador, ou mensagem injetada no
    stream) não pode gravar a identidade do fato verdadeiro. Se gravasse, o
    aviso legítimo que chegasse depois seria descartado como duplicado."""
    contador = []
    processar_envelope(
        _v1(site=OUTRA_ESCOLA, pedido="pedido-errado", referencia="MP-REF-99"),
        _contando(contador),
    )
    processar_envelope(
        _v2(site=SITE, pedido="pedido-certo", referencia="MP-REF-99"),
        _contando(contador),
    )

    assert len(contador) == 2, (
        "o aviso do site errado consumiu a identidade do fato certo e o "
        "legítimo foi descartado: quem pagou ficou sem matrícula."
    )
    matricula = Matricula.objects.get(order_id="pedido-certo")
    assert matricula.site_id == SITE


@pytest.mark.django_db
def test_a_identidade_comeca_pelo_site():
    """A forma da chave é combinada entre as células consumidoras deste lote
    (site, evento, campos da chave do contrato), para que o mesmo fato seja
    legível do mesmo jeito em qualquer uma."""
    dados = dados_na_forma_do_v2(_v2())

    assert (
        identidade_do_fato("pagamento.aprovado", dados)
        == f"{SITE}|pagamento.aprovado|mercadopago|{REFERENCIA_NO_PROVEDOR}"
    )


# ------------------------------------------------- concorrência, Redis real


def _redis_real() -> "redis.Redis":
    import os

    url = os.environ.get("REDIS_STREAMS_URL")
    if not url:
        pytest.fail(
            "REDIS_STREAMS_URL ausente — este guarda exige Redis REAL. "
            "Local: docker run -d --name alunos-redis -p 16381:6379 redis:7 e "
            "export REDIS_STREAMS_URL=redis://localhost:16381/0. "
            "(No CI o service de ci-celula.yml já fornece a variável.)"
        )
    cliente = redis.from_url(url)
    try:
        cliente.ping()
    except redis.exceptions.ConnectionError:
        pytest.fail(
            f"Redis real inacessível em {url} — suba o container antes de rodar."
        )
    return cliente


@pytest.fixture()
def r():
    cliente = _redis_real()
    yield cliente
    cliente.close()


@pytest.fixture()
def stream(r):
    nome = f"eventos.teste.duas-versoes.{uuid.uuid4().hex}"
    r.xgroup_create(nome, GRUPO, id="0", mkstream=True)
    yield nome
    r.delete(nome)


@pytest.mark.django_db(transaction=True)
def test_entregas_simultaneas_do_v1_e_do_v2_matriculam_uma_vez(r, stream):
    """O caso que mais assusta, e o único que precisa de Redis de verdade.

    As duas versões do MESMO pagamento estão no stream e dois workers do grupo
    pegam uma cada. Eles processam ao mesmo tempo, não em sequência: a barreira
    garante que ninguém termina antes de o outro começar. Em sequência, o
    segundo encontraria a linha de dedup já commitada; simultâneos, os dois
    tentam gravá-la, e quem perde a corrida precisa ser barrado pelo banco e
    voltar sem rodar o efeito.
    """
    v1, v2 = _v1(), _v2()
    r.xadd(stream, {"json": json.dumps(v1)})
    r.xadd(stream, {"json": json.dumps(v2)})

    entregas = []
    for worker in (f"{CONSUMIDOR}-a", f"{CONSUMIDOR}-b"):
        lido = r.xreadgroup(GRUPO, worker, {stream: ">"}, count=1)
        assert lido, "pré-condição: cada worker tinha de receber uma mensagem"
        entregas.append(lido[0][1][0])
    assert len({id for id, _ in entregas}) == 2, (
        "pré-condição: os dois workers receberam a MESMA mensagem; o teste "
        "não mediria entrega simultânea de versões diferentes"
    )

    barreira = threading.Barrier(2, timeout=10)
    erros = []

    def processar(msg_id, campos):
        try:
            envelope = json.loads(campos[b"json"])
            barreira.wait()
            processar_envelope(envelope, HANDLERS)
            r.xack(stream, GRUPO, msg_id)
        except Exception as exc:  # pragma: no cover - não engolir falha da thread
            erros.append(exc)
        finally:
            connection.close()

    threads = [
        threading.Thread(target=processar, args=(msg_id, campos))
        for msg_id, campos in entregas
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert not erros, erros
    assert not [t for t in threads if t.is_alive()], "thread travada"
    assert Matricula.objects.filter(order_id=PEDIDO).count() == 1
    assert EventoProcessado.objects.count() == 1, (
        "as duas versões do mesmo pagamento viraram dois fatos registrados; "
        "sob concorrência a unicidade da identidade lógica é o que sobra"
    )
    assert r.xpending(stream, GRUPO)["pending"] == 0
