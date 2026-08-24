# tests/test_inv_envelope_casa_com_contrato.py  # [RECEITA:R5 v1]
"""O envelope que sai no fio casa com o CONTRATO CONGELADO — este é o guarda
que torna `contracts/` executável em vez de decorativo.

Os quatro `contracts/eventos/sugestao.*.v1.json` foram congelados pelo Rito de
Contrato (RITOS.md §3, PR #128) com o mantenedor presente. Um contrato que
ninguém executa é um documento: envelhece em silêncio, e a divergência só
aparece na célula que consome, semanas depois, como um `KeyError` sem
explicação.

**O schema é LIDO do arquivo, nunca copiado para dentro deste teste.** Uma
cópia do formato aqui passaria a ser uma segunda verdade sobre o contrato, e as
duas envelheceriam em ritmos diferentes — que é exatamente o problema que
`contracts/` existe para matar.

**E o guarda MORDE** (`test_um_campo_a_mais_no_data_e_recusado`): os quatro
contratos são `additionalProperties: false`, então um `email` que alguém
acrescente ao `data` "só para facilitar a vida do consumidor" reprova o CI. É a
decisão de privacidade do mantenedor (`DECISAO-EVO-01` §3: o e-mail vive numa
linha só, dentro da Caixa) virando trava mecânica em vez de combinado.
"""

import copy
import json
from datetime import datetime
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from apps.sugestoes import eventos
from apps.sugestoes.models import Sugestao
from apps.sugestoes.tasks import relay_outbox

pytestmark = pytest.mark.django_db

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts" / "eventos"


def _validador(evento: str) -> Draft202012Validator:
    schema = json.loads((CONTRATOS / f"{evento}.v1.json").read_text(encoding="utf-8"))
    # `FormatChecker` é o que faz `format: uuid` deixar de ser anotação e passar
    # a recusar valor. Sem ele o jsonschema ignora `format` inteiro — um teste
    # que valida sem ele diria "casa com o contrato" para um `event_id` que é a
    # string "abc".
    return Draft202012Validator(schema, format_checker=FormatChecker())


def _conferir(envelope: dict) -> None:
    _validador(envelope["event"]).validate(envelope)
    # `date-time` não está entre os checkers que o jsonschema traz sem
    # dependência extra (só `uuid`, `email`, `date`…). Em vez de arrastar o
    # `rfc3339-validator` para o requirements por um campo, o guarda o confere
    # aqui — e falha com uma mensagem legível.
    datetime.fromisoformat(envelope["occurred_at"])


@pytest.fixture
def no_fio(caixa, fio):
    """Provoca os quatro fatos e devolve o que o relay REALMENTE publicou."""
    caixa.os_quatro_fatos()
    assert relay_outbox() == 4
    return fio


# ---------------------------------------------------------------------------
# O guarda não pode passar no vazio
# ---------------------------------------------------------------------------


def test_os_quatro_contratos_existem_e_sao_os_que_a_celula_emite():
    """Sem isto, um `glob` que não achasse nada deixaria tudo abaixo verde por
    não ter o que conferir — e um contrato renomeado passaria despercebido."""
    congelados = {arquivo.name for arquivo in CONTRATOS.glob("sugestao.*.json")}

    assert congelados == {
        "sugestao.criada.v1.json",
        "sugestao.voto-adicionado.v1.json",
        "sugestao.voto-removido.v1.json",
        "sugestao.status-alterado.v1.json",
    }, "os contratos da Caixa mudaram — isso é RITOS §3, não decisão de despacho"


def test_sugestao_mesclada_continua_sem_contrato_e_sem_emissao():
    """Mesclar é V1.1 e o contrato NÃO foi congelado, de propósito. Emitir um
    evento sem contrato seria fabricar a fronteira dentro de um despacho."""
    assert not list(CONTRATOS.glob("sugestao.mesclada*.json"))

    nomes = {
        valor
        for nome, valor in vars(eventos).items()
        if nome.isupper() and isinstance(valor, str)
    }
    assert "sugestao.mesclada" not in nomes


# ---------------------------------------------------------------------------
# Os quatro envelopes, como saíram no fio
# ---------------------------------------------------------------------------


def test_os_quatro_envelopes_validam_contra_o_contrato_congelado(no_fio):
    assert len(no_fio.mensagens) == 4
    for _, envelope in no_fio.mensagens:
        _conferir(envelope)


def test_o_nome_do_stream_e_eventos_ponto_evento_e_a_versao_vai_no_envelope(no_fio):
    """`eventos.<nome>`, sem `v1` no nome — a versão viaja DENTRO.

    Pôr a versão no nome do stream faria de toda evolução de contrato uma
    migração de infraestrutura: o `v1` continua sendo emitido até o último
    consumidor migrar (RITOS §3), e seriam dois streams para o mesmo fato.
    """
    assert sorted(no_fio.streams) == [
        "eventos.sugestao.criada",
        "eventos.sugestao.status-alterado",
        "eventos.sugestao.voto-adicionado",
        "eventos.sugestao.voto-removido",
    ]
    for _, envelope in no_fio.mensagens:
        assert envelope["version"] == 1


def test_o_data_da_sugestao_criada_e_o_que_o_contrato_descreve(caixa, fio):
    sugestao = caixa.publicar()
    relay_outbox()

    dados = fio.um_envelope(eventos.CRIADA)["data"]

    assert dados == {
        "site_id": "site-de-teste",
        "suggestion_id": str(sugestao.pk),
        "quadro_id": str(sugestao.quadro_id),
        "categoria_id": str(sugestao.categoria_id),
        "autor_id": caixa.aluno.identidade.id,
    }


def test_os_votos_levam_quem_votou_e_o_total_depois_do_fato(caixa, fio, entrar_como):
    """`autor_id` é quem VOTOU, não quem sugeriu — e `total_votos` é o de
    depois. Dois atores diferentes deixam a confusão impossível de passar."""
    sugestao = caixa.publicar()
    outra_pessoa = entrar_como("maria@exemplo.test", "Maria")
    caixa.votar(sugestao)
    caixa.votar(sugestao, quem=outra_pessoa)
    caixa.desvotar(sugestao, quem=outra_pessoa)
    relay_outbox()

    adicionados = fio.envelopes(eventos.VOTO_ADICIONADO)
    removido = fio.um_envelope(eventos.VOTO_REMOVIDO)

    assert [e["data"]["autor_id"] for e in adicionados] == [
        caixa.aluno.identidade.id,
        outra_pessoa.identidade.id,
    ]
    assert [e["data"]["total_votos"] for e in adicionados] == [1, 2]
    assert removido["data"]["autor_id"] == outra_pessoa.identidade.id
    assert removido["data"]["total_votos"] == 1  # DEPOIS da remoção


def test_o_status_alterado_leva_o_autor_da_sugestao_e_a_justificativa(caixa, fio):
    """Quem SUGERIU, não quem moderou: é a esse que o EVO-21 vai avisar.

    Quem moderou fica no `HistoricoStatus`, dentro da Caixa — é auditoria
    interna e não interessa a nenhum consumidor.
    """
    sugestao = caixa.publicar()
    caixa.mudar_status(
        sugestao, Sugestao.Status.NAO_PLANEJADO, nota="Já existe no menu de aulas."
    )
    relay_outbox()

    dados = fio.um_envelope(eventos.STATUS_ALTERADO)["data"]

    assert dados["autor_da_sugestao_id"] == caixa.aluno.identidade.id
    assert dados["status_anterior"] == "em_analise"
    assert dados["status_novo"] == "nao_planejado"
    assert dados["nota"] == "Já existe no menu de aulas."


def test_sem_justificativa_o_campo_nota_nem_aparece(caixa, fio):
    """Opcional no contrato quer dizer AUSENTE, não string vazia — senão todo
    consumidor teria de distinguir "sem justificativa" de "justificativa
    vazia", que são dois nomes para a mesma coisa."""
    sugestao = caixa.publicar()
    caixa.mudar_status(sugestao, Sugestao.Status.PLANEJADO)
    relay_outbox()

    assert "nota" not in fio.um_envelope(eventos.STATUS_ALTERADO)["data"]


# ---------------------------------------------------------------------------
# A privacidade — e a prova de que este guarda MORDE
# ---------------------------------------------------------------------------


def test_nenhum_envelope_carrega_dado_pessoal_nem_texto_do_aluno(no_fio):
    """Ids opacos, contagem e status. Mais nada.

    A `DECISAO-EVO-01` §3 põe o e-mail numa linha só, dentro da Caixa. Um
    evento que o levasse junto espalharia dado pessoal por todo consumidor que
    assinasse o stream — e não haveria como recolher depois. Título e texto do
    problema ficam de fora pelo mesmo motivo: são o que a pessoa escreveu.
    """
    for _, envelope in no_fio.mensagens:
        cru = json.dumps(envelope, ensure_ascii=False)
        for vazamento in ("@", "Legendas nas aulas", "ônibus", "João", "Equipe"):
            assert vazamento not in cru, f"{vazamento!r} vazou em {envelope['event']}"


@pytest.mark.parametrize(
    "evento",
    [
        "sugestao.criada",
        "sugestao.voto-adicionado",
        "sugestao.voto-removido",
        "sugestao.status-alterado",
    ],
)
def test_um_campo_a_mais_no_data_e_recusado(no_fio, evento):
    """A prova de que o guarda morde — em cada um dos quatro contratos.

    Acrescentar `email` ao `data` é o atalho mais tentador que existe aqui
    ("assim o consumidor não precisa perguntar de volta"). Os contratos são
    `additionalProperties: false` justamente para que esse atalho vire CI
    vermelho, e não uma decisão de privacidade tomada por descuido numa
    sexta-feira.
    """
    envelope = copy.deepcopy(no_fio.um_envelope(evento))
    _conferir(envelope)  # o de verdade passa...

    envelope["data"]["email"] = "aluno@exemplo.test"

    with pytest.raises(ValidationError) as recusa:
        _conferir(envelope)  # ...e o com um campo a mais, não
    assert "email" in str(recusa.value)
