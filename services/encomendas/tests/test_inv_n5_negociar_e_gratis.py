"""[INV-ENC-N5] Propor, ser recusado, deixar vencer ou desistir são gratuitos.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.2 e §8; lei
`DECISAO-fila-do-primeiro-dolar.md` §5 ([INV-ENC-J4]). Nenhum desses quatro
gestos muda a data de entrada na fila: **só o abandono muda o lugar**.

O guarda tem duas metades, e a segunda é a que sobrevive ao tempo. A primeira
encena os quatro gestos e mede a coluna. A segunda VARRE o código da negociação
procurando qualquer escrita em `data_entrada_fila`, e existe porque um caminho
novo escrito daqui a três meses não estaria em cenário nenhum encenado hoje.
"""

import ast
from datetime import datetime, timedelta, timezone as fuso
from pathlib import Path

from apps.encomendas import negociacao, tique
from apps.encomendas.models import Encomenda, PerfilProfissional, Proposta

SITE = "escola-a"
CAMPO = "data_entrada_fila"
NEGOCIACAO = Path(negociacao.__file__)


def _agora():
    return datetime.now(tz=fuso.utc)


def _propor(projeto, lado, formulario, agora, **mudancas):
    return negociacao.propor(
        projeto.pk, agora, site_id=SITE, de_quem=lado, **formulario(**mudancas)
    )


# ---------------------------------------------------------------------------
# 1. A VARREDURA: nenhuma linha da negociação escreve o lugar na fila
# ---------------------------------------------------------------------------


class _Varredor(ast.NodeVisitor):
    """As três formas de gravar a coluna: atribuição, `update()` e `update_fields`."""

    def __init__(self):
        self.achados: list[str] = []

    def visit_Assign(self, no):
        for alvo in no.targets:
            if isinstance(alvo, ast.Attribute) and alvo.attr == CAMPO:
                self.achados.append(f"atribuicao na linha {no.lineno}")
        self.generic_visit(no)

    def visit_Call(self, no):
        for chave in getattr(no, "keywords", []):
            if chave.arg == CAMPO:
                self.achados.append(f"argumento nomeado na linha {no.lineno}")
        for item in ast.walk(no):
            if isinstance(item, ast.Constant) and item.value == CAMPO:
                self.achados.append(f"nome literal na linha {no.lineno}")
        self.generic_visit(no)


def test_a_negociacao_nao_toca_no_lugar_da_fila():
    varredor = _Varredor()
    varredor.visit(ast.parse(NEGOCIACAO.read_text(encoding="utf-8")))
    assert varredor.achados == []


def test_o_varredor_enxerga_de_verdade():
    """O par vermelho da varredura: um varredor cego passaria no teste de cima."""
    varredor = _Varredor()
    varredor.visit(
        ast.parse(
            "def punir(perfil, agora):\n"
            "    perfil.data_entrada_fila = agora\n"
            "    perfil.save(update_fields=['data_entrada_fila'])\n"
        )
    )
    assert len(varredor.achados) >= 2


# ---------------------------------------------------------------------------
# 2. OS QUATRO GESTOS, encenados, com a coluna medida antes e depois
# ---------------------------------------------------------------------------


def test_propor_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, _agora()).feito
    ana.refresh_from_db()
    assert ana.data_entrada_fila == antes


def test_ser_recusado_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    """O cliente desiste: o projeto vai ao plantão, e o aluno não perde nada."""
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert negociacao.desistir(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.CLIENTE
    ).feito

    ana.refresh_from_db()
    projeto.refresh_from_db()
    assert ana.data_entrada_fila == antes
    assert projeto.status == Encomenda.Status.PARA_RECLASSIFICAR


def test_deixar_vencer_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert _propor(
        projeto, Proposta.DeQuem.CLIENTE, formulario, agora, valor_cents=18_000
    ).feito
    Proposta.objects.filter(encomenda=projeto).update(
        valida_ate=agora - timedelta(hours=1)
    )

    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)
    ana.refresh_from_db()
    assert ana.data_entrada_fila == antes


def test_desistir_nao_muda_o_lugar_na_fila(projeto_pego, formulario):
    projeto, ana = projeto_pego
    antes = ana.data_entrada_fila
    agora = _agora()
    assert _propor(projeto, Proposta.DeQuem.ALUNO, formulario, agora).feito
    assert negociacao.desistir(
        projeto.pk, agora, site_id=SITE, de_quem=Proposta.DeQuem.ALUNO
    ).feito

    ana.refresh_from_db()
    projeto.refresh_from_db()
    assert ana.data_entrada_fila == antes
    assert projeto.status == Encomenda.Status.NO_MURAL
    assert projeto.aluno_id is None


def test_a_negociacao_que_morre_devolve_o_aluno_as_ofertas(
    semeado, criar_perfil, criar_encomenda, formulario
):
    """A outra metade de "negociar é gratuito", e a que dói quando falta.

    Um cliente que some não pode deixar o aluno fora da fila por uma demora que
    não foi dele. A negociação viva já não muda a disponibilidade, e a morte da
    negociação conserva o lugar para a próxima oferta.
    """
    from apps.encomendas import gestos, motor

    agora = _agora()
    zeca = criar_perfil("pes-zeca", entrada=agora - timedelta(days=5))
    encomenda = criar_encomenda()
    antes = zeca.data_entrada_fila

    rodada = motor.rodar(agora, site_id=SITE)
    assert rodada.quantas_ofertas == 1
    assert gestos.aceitar(rodada.ofertas_criadas[0], zeca.pk, agora, site_id=SITE).feito
    zeca.refresh_from_db()
    assert zeca.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL

    assert negociacao.propor(
        encomenda.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    Proposta.objects.filter(encomenda=encomenda).update(
        valida_ate=agora - timedelta(hours=1)
    )
    assert tique.expirar_propostas_vencidas(agora, site_id=SITE)

    zeca.refresh_from_db()
    encomenda.refresh_from_db()
    assert zeca.disponibilidade == PerfilProfissional.Disponibilidade.DISPONIVEL
    assert zeca.data_entrada_fila == antes
    assert encomenda.status == Encomenda.Status.PARA_RECLASSIFICAR
