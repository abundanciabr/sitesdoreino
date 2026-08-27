# tests/test_inv_carta_casa_com_o_contrato.py  # [RECEITA:R5 v1]
"""O que esta célula ACEITA do fio é exatamente o que o contrato promete.

O contrato `contracts/eventos/notificacao.devida.v1.json` foi congelado no Rito
de Contrato de 26/08/2026 (PR #243), com o mantenedor presente. Do lado de lá, a
`sugestoes` tem um guarda que prova que o que ela PUBLICA casa com o contrato.
Este é o guarda do lado de cá: o que a caixa central CONSOME casa com o mesmo
arquivo.

**Os dois lados precisam existir separados.** Um contrato provado só na origem
garante que a mensagem sai certa e não diz nada sobre o consumidor ter entendido
os campos que ela traz. Foi a lição do elo EVO-40: escada testada só por fora
prova o andar de cima e mente sobre os de baixo.

**O schema é LIDO do arquivo, nunca copiado para dentro deste teste** — uma
cópia aqui seria uma segunda verdade sobre o contrato, envelhecendo no próprio
ritmo. É a mesma regra do guarda irmão na `sugestoes`.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

from apps.notificacoes.handlers import ao_notificacao_devida
from apps.notificacoes.models import Notificacao
from tests.conftest import envelope_de_carta

pytestmark = pytest.mark.django_db

CONTRATO = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "eventos"
    / "notificacao.devida.v1.json"
)


def _validador() -> Draft202012Validator:
    assert CONTRATO.exists(), (
        f"o contrato não está em {CONTRATO} — sem ele este arquivo inteiro "
        "passaria no vazio, que é o modo de falha que [INV-CI01] existe para matar"
    )
    return Draft202012Validator(
        json.loads(CONTRATO.read_text(encoding="utf-8")), format_checker=FormatChecker()
    )


def test_o_envelope_que_os_guardas_usam_e_valido_pelo_contrato():
    """A fixture desta suíte não pode ser um envelope que o fio nunca produziria."""
    _validador().validate(envelope_de_carta())


def test_a_celula_guarda_todos_os_campos_que_o_contrato_promete():
    """Campo prometido e ignorado é campo que some sem ninguém notar."""
    envelope = envelope_de_carta()
    dados = envelope["data"]

    ao_notificacao_devida(dados, ator_id=envelope["ator_id"])

    guardada = Notificacao.objects.get()
    assert guardada.site_id == dados["site_id"]
    assert guardada.destinatario_id == dados["destinatario_id"]
    assert guardada.assunto == dados["assunto"]
    assert guardada.parametros == dados["parametros"]
    assert str(guardada.origem_event_id) == dados["origem_event_id"]
    assert guardada.ator_id == envelope["ator_id"]
    assert guardada.lido_em is None, "aviso nasce não lido"


def test_carta_sem_ator_e_aceita_e_guardada_como_sem_ator():
    """O contrato declara `ator_id` nulável — fato de máquina não tem gente.

    Guardar `""` em vez de `None` criaria duas formas de "não sei", e dois
    pedaços de código as consultariam de jeitos diferentes.
    """
    envelope = envelope_de_carta(ator_id=None)
    _validador().validate(envelope)

    ao_notificacao_devida(envelope["data"], ator_id=envelope["ator_id"])

    assert Notificacao.objects.get().ator_id is None


def test_a_celula_nao_guarda_email_porque_o_contrato_nao_deixa_entrar():
    """A trava é do contrato, e este teste prova que ela MORDE de verdade.

    O e-mail vive numa linha só, dentro da Caixa (`DECISAO-EVO-01` §3). Se um
    dia alguém "facilitar a vida do consumidor" mandando o e-mail junto, é aqui
    que se descobre — e não em produção, com o dado já espalhado.
    """
    envelope = envelope_de_carta()
    envelope["data"]["email"] = "aluno@exemplo.test"

    with pytest.raises(Exception):
        _validador().validate(envelope)

    de_carona = envelope_de_carta()
    de_carona["data"]["parametros"]["email"] = "aluno@exemplo.test"
    with pytest.raises(Exception):
        _validador().validate(de_carona)
