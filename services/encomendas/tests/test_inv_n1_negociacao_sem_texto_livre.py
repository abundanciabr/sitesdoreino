"""[INV-ENC-N1] Nenhum texto entre cliente e aluno fora dos campos estruturados.

Produto: `PLANO-AREA-DE-NEGOCIACAO.md` §4.1 e §8. Reforça o [INV-ENC-S1], que
**não foi revogado**: a negociação não abriu uma exceção no invariante de
segurança, ela mostrou que a exceção era desnecessária. Negociar não é
conversar: negociar é trocar formulários.

O guarda mede a FORMA, e não só o comportamento, e essa é a parte que importa.
Um teste que só encenasse propostas ficaria verde no dia em que alguém
acrescentasse um campo `mensagem` à tabela e não o usasse ainda; o campo entra
no PR, a tela seguinte o preenche, e o invariante cai sem nenhum vermelho pelo
caminho. Por isso a lista de campos da `Proposta` é medida inteira, nome por
nome.
"""

from datetime import datetime, timezone as fuso

from django.db import models

from apps.encomendas import negociacao
from apps.encomendas.models import Acordo, Parametro, Proposta

SITE = "escola-a"

# A LISTA COMPLETA, nome por nome. Cresce só com decisão escrita, e crescer é
# diff: quem acrescentar um campo aqui tem de explicar, no mesmo PR, por que ele
# não é uma caixa de mensagem com outro nome.
OS_CAMPOS_DA_PROPOSTA = {
    "id",
    "site_id",
    "encomenda",
    "aluno",
    "de_quem",
    "rodada",
    "valor_cents",
    "prazo_dias",
    "entregaveis",
    "correcoes_inclusas",
    "justificativa",
    "valida_ate",
    "criada_em",
    "resultado",
    "respondida_em",
}

OS_CAMPOS_DO_ACORDO = {
    "id",
    "site_id",
    "encomenda",
    "proposta",
    "aluno",
    "de_quem",
    "aceito_por",
    "aceito_em",
    "criado_em",
}


def _agora():
    return datetime.now(tz=fuso.utc)


# ---------------------------------------------------------------------------
# 1. A FORMA: a tabela não tem onde esconder uma conversa
# ---------------------------------------------------------------------------


def test_a_proposta_tem_exatamente_estes_campos_e_nenhum_a_mais():
    assert {campo.name for campo in Proposta._meta.concrete_fields} == (
        OS_CAMPOS_DA_PROPOSTA
    )


def test_o_acordo_tem_exatamente_estes_campos_e_nenhum_a_mais():
    assert {campo.name for campo in Acordo._meta.concrete_fields} == OS_CAMPOS_DO_ACORDO


def test_a_justificativa_e_o_unico_texto_livre_das_duas_tabelas():
    """`TextField` é a forma de guardar conversa, e só há um em toda a negociação."""
    textos = {
        campo.name
        for tabela in (Proposta, Acordo)
        for campo in tabela._meta.concrete_fields
        if isinstance(campo, models.TextField)
        and not isinstance(campo, models.CharField)
    }
    assert textos == {"justificativa"}


def test_nenhum_campo_com_cara_de_caixa_de_mensagem():
    """A segunda peneira, por NOME, e ela pega o que a de cima deixaria passar.

    Um `CharField(max_length=500)` chamado `mensagem` não é `TextField`, e
    guardaria conversa do mesmo jeito. As duas peneiras juntas custam quatro
    linhas e fecham a porta pelos dois lados.
    """
    proibidos = ("mensagem", "comentario", "texto", "anexo", "chat", "recado", "obs")
    nomes = [
        campo.name
        for tabela in (Proposta, Acordo)
        for campo in tabela._meta.concrete_fields
    ]
    assert [nome for nome in nomes if any(p in nome for p in proibidos)] == []


# ---------------------------------------------------------------------------
# 2. O COMPORTAMENTO: o único texto é curto por parâmetro, e o plantão vê tudo
# ---------------------------------------------------------------------------


def test_a_justificativa_e_limitada_pelo_parametro(projeto_pego, formulario):
    projeto, _ = projeto_pego
    agora = _agora()
    limite = Parametro.inteiro_vigente("limite_da_justificativa", agora, site_id=SITE)

    demais = negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(justificativa="x" * (limite + 1)),
    )
    assert demais.razao == negociacao.JUSTIFICATIVA_LONGA_DEMAIS
    assert not Proposta.objects.filter(encomenda=projeto).exists()

    no_limite = negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(justificativa="x" * limite),
    )
    assert no_limite.feito


def test_o_limite_muda_no_banco_sem_PR(projeto_pego, formulario):
    """O parâmetro é DADO: uma linha nova muda a régua, e o guarda a acompanha."""
    projeto, _ = projeto_pego
    agora = _agora()
    Parametro.objects.create(
        site_id=SITE,
        chave="limite_da_justificativa",
        valor="10",
        desde=agora,
        motivo="O piloto de papel mostrou que a justificativa longa ninguem le.",
        quem="dono-1",
    )
    curta = negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(justificativa="x" * 11),
    )
    assert curta.razao == negociacao.JUSTIFICATIVA_LONGA_DEMAIS


def test_entregavel_fora_do_briefing_e_recusado(projeto_pego, formulario):
    """Lista FECHADA: inventar um entregável é texto livre com outro nome."""
    projeto, _ = projeto_pego
    recusa = negociacao.propor(
        projeto.pk,
        _agora(),
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(entregaveis=["um_video_de_apresentacao"]),
    )
    assert recusa.razao == negociacao.ENTREGAVEL_FORA_DO_BRIEFING
    assert not Proposta.objects.filter(encomenda=projeto).exists()


def test_o_plantao_ve_todas_as_rodadas_e_todos_os_campos(projeto_pego, formulario):
    """A segunda metade do invariante: *todos* visíveis ao plantão.

    Inclusive as rodadas mortas. Uma negociação em que o plantão só visse a
    proposta de pé não seria julgável, e julgar é para o que o registro existe.
    """
    projeto, _ = projeto_pego
    agora = _agora()
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(justificativa="modelagem, uv e duas texturas"),
    ).feito
    assert negociacao.propor(
        projeto.pk,
        agora,
        site_id=SITE,
        de_quem=Proposta.DeQuem.CLIENTE,
        **formulario(valor_cents=18_000, justificativa="o orcamento do mes e menor"),
    ).feito

    visto = negociacao.para_o_plantao(projeto)
    assert len(visto) == 2
    for linha in visto:
        assert set(Proposta.CAMPOS_DO_FORMULARIO) <= set(linha)
    assert [linha["de_quem"] for linha in visto] == ["aluno", "cliente"]
    assert [linha["resultado"] for linha in visto] == ["superada", "pendente"]
    assert visto[0]["justificativa"] == "modelagem, uv e duas texturas"
    assert visto[1]["justificativa"] == "o orcamento do mes e menor"


def test_a_leitura_do_plantao_nao_esquece_campo_novo(projeto_pego, formulario):
    """A lista do plantão sai de `CAMPOS_DO_FORMULARIO`, e não de uma cópia.

    Sem esta asserção, um campo novo no formulário nasceria invisível ao
    plantão, que é um pedaço de conversa escondido com aparência de detalhe de
    tela.
    """
    projeto, _ = projeto_pego
    assert negociacao.propor(
        projeto.pk,
        _agora(),
        site_id=SITE,
        de_quem=Proposta.DeQuem.ALUNO,
        **formulario(),
    ).feito
    (linha,) = negociacao.para_o_plantao(projeto)
    assert set(linha) == set(Proposta.CAMPOS_DO_FORMULARIO) | {
        "de_quem",
        "rodada",
        "resultado",
        "criada_em",
    }
