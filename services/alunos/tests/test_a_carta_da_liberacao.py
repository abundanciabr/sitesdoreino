"""A célula ganhou VOZ: ela avisa quem foi liberado.

Até 29/08/2026 esta célula só ESCUTAVA — o consumer de pagamento, e nada mais.
Ela passou a afirmar um fato ao resto da plataforma para poder cumprir uma
promessa que o mantenedor escolheu: *"você é avisado quando eu te liberar"*.

**As cinco coisas que este arquivo trava:**

1. **A carta nasce DENTRO da transação do fato.** Fora dela, um rollback
   deixaria uma carta no fio para uma liberação que não aconteceu — o modo de
   falha mais caro que uma outbox existe para impedir. `emitir()` recusa a
   escrita fora de `atomic`, e o guarda prova que a recusa é real.

2. **A carta NUNCA impede a liberação.** A `identidade` fora do ar, o par não
   provisionado, a pessoa que nunca entrou com o Google: em todos os casos a
   liberação acontece e a carta simplesmente não existe. É fail-ABERTO, e a
   direção é a decisão — o mantenedor clicar em "Liberar" e nada acontecer, por
   causa de uma peça de notificação, seria muito pior que um aviso a menos.

3. **Só quem GANHA acesso recebe carta.** Recusar não avisa; encerrar não
   avisa; pausar não avisa. Não por esquecimento: quem perde o acesso não
   consegue abrir a página de avisos (ela mora dentro da Caixa, e a Caixa só
   abre para aluno), então a carta seria escrita e nunca lida.

4. **A carta casa com o contrato congelado**, validada contra o ARQUIVO —
   nunca contra uma cópia do formato dentro do teste.

5. **Nenhuma PII no fio.** Nem nome, nem e-mail, nem telefone.
"""

import json
import uuid
from pathlib import Path

import httpx
import pytest
import respx
from django.db import transaction

from apps.matriculas.eventos import (
    ASSUNTO_MATRICULA,
    NOTIFICACAO_DEVIDA,
    EventoForaDaTransacao,
    carta_de_situacao,
)
from apps.matriculas.models import Matricula, OutboxEvent
from apps.matriculas.services import (
    atualizar_matricula,
    decidir_na_fila,
    entrar_na_fila,
)

pytestmark = pytest.mark.django_db

# [INV-ALU-C1] Desde 06/09/2026 liberar exige dizer o produto
# (`docs/decisoes/DECISAO-cursos-matriculas-e-alunos.md`). Aqui vale qualquer
# texto opaco: o valor de verdade e um id de produto do `catalogo`, e quem prova
# a exigencia e `tests/test_inv_alu_c1_a_matricula_diz_o_curso.py`.
CURSO = "produto-do-curso-1"

IDENTIDADE = "http://identidade:8000/interno"
PESSOA = "quem.espera@exemplo.test"
ID_DA_PLATAFORMA = "idt-opaco-abc123"
CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)


@pytest.fixture(autouse=True)
def par_com_a_identidade(monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", IDENTIDADE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-alunos-identidade")


def _identidade_responde(id_da_plataforma=ID_DA_PLATAFORMA):
    return respx.post(f"{IDENTIDADE}/pessoas/por-email").mock(
        return_value=httpx.Response(200, json={"id": id_da_plataforma})
    )


def _na_fila(email=PESSOA):
    linha, _ = entrar_na_fila(
        site_id="escola-a",
        email=email,
        nome_completo="Quem Espera",
        whatsapp="(96) 99999-0000",
    )
    return linha


def _cartas():
    """So as CARTAS, e nao tudo que esta na caixa de saida.

    Desde 05/09/2026 a mesma outbox carrega dois tipos de evento: a CARTA
    (`notificacao.devida`, que avisa uma pessoa) e o FATO
    (`matricula.situacao-alterada`, que conta o que aconteceu com a
    matricula). Sem este filtro, todo teste desta suite mediria os dois e
    reprovaria por causa de um evento que ele nem esta olhando.
    """
    return list(OutboxEvent.objects.filter(event=NOTIFICACAO_DEVIDA))


def _envelope(carta: OutboxEvent) -> dict:
    """O envelope como o relay o montaria — a forma que vai para o fio."""
    envelope = {
        "event": carta.event,
        "version": carta.version,
        "event_id": str(carta.event_id),
        "occurred_at": carta.occurred_at.isoformat(),
        "data": carta.payload,
    }
    envelope.update(carta.envelope_extra)
    return envelope


# ------------------------------------------- 1. a carta nasce com o fato


@respx.mock
def test_liberar_alguem_da_fila_escreve_a_carta():
    _identidade_responde()
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    (carta,) = _cartas()
    assert carta.event == "notificacao.devida"
    assert carta.payload["assunto"] == ASSUNTO_MATRICULA
    assert carta.payload["destinatario_id"] == ID_DA_PLATAFORMA
    assert carta.payload["parametros"]["situacao_nova"] == "ativa"
    assert carta.payload["parametros"]["situacao_anterior"] == "aguardando"
    assert carta.envelope_extra == {"ator_id": "idt-do-mantenedor"}


@pytest.mark.django_db(transaction=True)
def test_emitir_fora_de_transacao_e_recusado():
    """A Lei 1 aplicada: em vez de confiar que todo ponto de emissão futuro se
    lembre do `atomic`, a própria função recusa a escrita.

    `transaction=True` é o que torna este guarda possível: o `django_db` normal
    envolve cada teste numa transação, e dentro dela `in_atomic_block` é sempre
    verdadeiro — a recusa nunca dispararia, e o teste passaria por acidente
    medindo outra coisa.
    """
    with pytest.raises(EventoForaDaTransacao):
        carta_de_situacao(
            site_id="escola-a",
            destinatario_id=ID_DA_PLATAFORMA,
            matricula_id="1",
            situacao_nova="ativa",
        )


def test_o_rollback_do_fato_leva_a_carta_junto():
    """O guarda que carrega o padrão inteiro.

    Se a carta sobrevivesse ao rollback, a plataforma passaria a avisar sobre
    uma liberação que não aconteceu — e ninguém teria como saber.
    """
    with pytest.raises(RuntimeError):
        with transaction.atomic():
            carta_de_situacao(
                site_id="escola-a",
                destinatario_id=ID_DA_PLATAFORMA,
                matricula_id="1",
                situacao_nova="ativa",
            )
            raise RuntimeError("o fato deu errado")

    assert _cartas() == []


def test_o_origem_event_id_e_o_id_da_propria_carta():
    """A rastreabilidade que o campo promete: de qualquer aviso na tela se chega
    ao acontecimento que o causou. Cunhar os dois separados faria os dois
    discordarem, em silêncio."""
    with transaction.atomic():
        carta = carta_de_situacao(
            site_id="escola-a",
            destinatario_id=ID_DA_PLATAFORMA,
            matricula_id="1",
            situacao_nova="ativa",
        )
    assert carta.payload["origem_event_id"] == str(carta.event_id)
    uuid.UUID(carta.payload["origem_event_id"])  # é um uuid de verdade


# --------------------------------- 2. a carta nunca impede a liberação


@respx.mock
def test_a_identidade_fora_do_ar_libera_do_mesmo_jeito_e_nao_escreve_carta():
    """Fail-ABERTO, e a direção é a decisão: o mantenedor clicar em "Liberar" e
    nada acontecer por causa de uma peça de notificação seria muito pior que um
    aviso a menos."""
    respx.post(f"{IDENTIDADE}/pessoas/por-email").mock(
        side_effect=httpx.ConnectError("recusou")
    )
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    decidida, resultado = decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    assert resultado == "ok"
    assert decidida.status == "ativa"
    assert _cartas() == []


@respx.mock
def test_quem_nunca_entrou_com_o_google_e_liberado_sem_carta():
    """`id: null` é RESPOSTA, não erro — é o caso de quem o painel cadastrou à
    mão e ainda não abriu o site."""
    _identidade_responde(id_da_plataforma=None)
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    _, resultado = decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    assert resultado == "ok"
    assert _cartas() == []


def test_sem_o_par_provisionado_nao_ha_carta_nem_salto_de_rede(monkeypatch):
    """O estado de HOJE, e ele é o caminho NORMAL — não uma falha. Enquanto o
    par `alunos→identidade` não estiver no env da VPS, a célula se comporta
    como antes desta mudança."""
    monkeypatch.delenv("IDENTIDADE_API_URL", raising=False)
    monkeypatch.delenv("IDENTIDADE_API_TOKEN", raising=False)
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    assert _para_quem_avisar(str(linha.pk)) == ""

    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
        destinatario_id="",
    )
    assert _cartas() == []


# --------------------------------------- 3. só quem GANHA acesso é avisado


@respx.mock
def test_recusar_nao_escreve_carta():
    _identidade_responde()
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="recusar",
        decidido_por="idt-do-mantenedor",
        motivo="não achei sua compra",
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    assert _cartas() == []


@respx.mock
def test_religar_quem_estava_pausado_TAMBEM_avisa():
    """O mesmo gesto, pelo outro caminho: "liberei você" é a mesma notícia,
    venha ela da fila ou do formulário do painel."""
    _identidade_responde()
    linha = Matricula.objects.create(
        site_id="escola-a",
        order_id="pedido-real-1",
        email=PESSOA,
        name="Quem Espera",
        status=Matricula.STATUS_SUSPENSA,
    )

    from apps.core.api import _para_quem_avisar

    atualizar_matricula(
        id_da_linha=str(linha.pk),
        mudancas={"status": "ativa"},
        decidido_por="idt-do-mantenedor",
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    (carta,) = _cartas()
    assert carta.payload["parametros"] == {
        "matricula_id": str(linha.pk),
        "situacao_nova": "ativa",
        "situacao_anterior": "suspensa",
    }


@respx.mock
@pytest.mark.parametrize("destino", ["suspensa", "encerrada"])
def test_perder_acesso_NAO_escreve_carta(destino):
    """Não é esquecimento: quem perde o acesso não consegue abrir a página de
    avisos — ela mora dentro da Caixa, e a Caixa só abre para aluno. A carta
    seria escrita e nunca lida. A bifurcação está registrada no livro."""
    _identidade_responde()
    linha = Matricula.objects.create(
        site_id="escola-a",
        order_id=f"pedido-real-{destino}",
        email=PESSOA,
        name="Quem Espera",
        status=Matricula.STATUS_ATIVA,
    )

    from apps.core.api import _para_quem_avisar

    atualizar_matricula(
        id_da_linha=str(linha.pk),
        mudancas={"status": destino},
        decidido_por="idt-do-mantenedor",
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    assert _cartas() == []


@respx.mock
def test_corrigir_o_telefone_de_um_aluno_nao_escreve_carta():
    """Quem já é aluno não "ganhou acesso" — e um aviso a cada correção de
    cadastro faria o sino virar barulho."""
    _identidade_responde()
    linha = Matricula.objects.create(
        site_id="escola-a",
        order_id="pedido-real-2",
        email=PESSOA,
        name="Quem Espera",
        status=Matricula.STATUS_ATIVA,
    )

    from apps.core.api import _para_quem_avisar

    atualizar_matricula(
        id_da_linha=str(linha.pk),
        mudancas={"whatsapp": "(96) 98888-1111"},
        decidido_por="idt-do-mantenedor",
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    assert _cartas() == []


# ------------------------------------ 4. o envelope casa com o CONTRATO


def test_o_envelope_casa_com_o_contrato_congelado():
    """Validado contra o ARQUIVO, nunca contra uma cópia do formato aqui dentro.

    Uma cópia envelhece: no dia em que o contrato mudar, o teste continuaria
    verde contra a versão antiga — e o consumidor quebraria em produção com a
    suíte no verde.
    """
    import jsonschema

    with transaction.atomic():
        carta = carta_de_situacao(
            site_id="escola-a",
            destinatario_id=ID_DA_PLATAFORMA,
            matricula_id="7",
            situacao_nova="ativa",
            situacao_anterior="aguardando",
            decidido_por="idt-do-mantenedor",
        )

    schema = json.loads(CONTRATO.read_text(encoding="utf-8"))
    jsonschema.validate(_envelope(carta), schema)


def test_uma_carta_sem_situacao_anterior_tambem_casa_com_o_contrato():
    """O campo é opcional no contrato, e ausência é "não registrado" — nunca
    uma string vazia, que o `enum` recusaria."""
    import jsonschema

    with transaction.atomic():
        carta = carta_de_situacao(
            site_id="escola-a",
            destinatario_id=ID_DA_PLATAFORMA,
            matricula_id="7",
            situacao_nova="ativa",
        )

    schema = json.loads(CONTRATO.read_text(encoding="utf-8"))
    jsonschema.validate(_envelope(carta), schema)
    assert "situacao_anterior" not in carta.payload["parametros"]


# ------------------------------------------------- 5. nenhuma PII no fio


@respx.mock
def test_a_carta_nao_leva_nome_email_nem_telefone():
    """Só ids opacos e estados. Quem precisa falar com a pessoa pergunta a esta
    célula, que é onde esse dado mora e quem decide quem pode vê-lo."""
    _identidade_responde()
    linha = _na_fila()

    from apps.core.api import _para_quem_avisar

    decidir_na_fila(
        id_da_linha=str(linha.pk),
        decisao="liberar",
        decidido_por="idt-do-mantenedor",
        product_id=CURSO,
        destinatario_id=_para_quem_avisar(str(linha.pk)),
    )

    (carta,) = _cartas()
    cru = json.dumps(_envelope(carta), ensure_ascii=False)
    assert PESSOA not in cru
    assert "Quem Espera" not in cru
    assert "99999-0000" not in cru
