"""A moderação depois da mudança de casa (30/08/2026): os cinco endereços.

Até 30/08/2026 este arquivo media a superfície da equipe DENTRO desta célula —
a fila, a página de moderação, a avaliação interna. Essas telas foram
aposentadas (TAR-023 degrau 4, fechando a decisão
`docs/decisoes/DECISAO-a-gestao-da-caixa-mora-no-admin.md`): quem conduz as
ideias é `/admin/caixa/`, e os comportamentos que estes testes mediam mudaram de
célula junto com as telas — hoje estão em
`services/admin/tests/test_caixa_no_admin.py` e `test_caixa_acoes.py`.

**O que ficou aqui é o que continua sendo desta célula**, e é o assunto novo do
arquivo: os cinco endereços antigos NÃO foram apagados, e este arquivo é o
guarda do que eles fazem agora.

Os três fatos que ele mede, e por que cada um importa:

1. **GET redireciona (301), não some.** Um 404 puniria quem salvou o endereço —
   e quem salvou foi justamente quem mais usava a tela.
2. **POST RECUSA (410) e diz que nada foi salvo.** Um 301 num POST vira um GET
   silencioso no destino: a pessoa veria a página nova e leria aquilo como
   "salvou". É falso-verde de produto (`RETROSPECTIVA-FASE-D` §1), e é o modo de
   falha que só existe porque estas cinco rotas incluíam ESCRITA — as três abas
   aposentadas em 28/08 eram todas de leitura.
3. **O crachá continua na frente.** Quem não é da equipe leva 403 e não descobre
   nem para onde a gestão foi. Redirecionamento é cortesia para quem já tinha
   acesso, nunca mapa para quem não tem.

Os invariantes continuam nos `test_inv_*` deste diretório — e eles agora
percorrem a jornada REAL (o contrato, `conftest.Gestao`), não uma view morta.
"""

import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db

# A casa nova. Escrita por extenso de propósito: se alguém mudar o destino em
# `apps/core/mudou_de_casa.py`, este guarda tem de reprovar, e não seguir a
# constante de mansinho.
CASA_NOVA = "/admin/caixa/"

# Os CINCO endereços aposentados, com o método que cada um servia. É a lista da
# auditoria de paridade do registro `20260830-019`.
ENDERECOS = [
    ("fila", (), "get"),
    ("moderar", (1,), "get"),
    ("mudar_status", (1,), "post"),
    ("avaliar", (1,), "post"),
    ("changespecs", (1,), "get"),
]


@pytest.mark.parametrize("nome,args,_metodo", ENDERECOS)
def test_todo_endereco_antigo_leva_a_equipe_para_a_casa_nova(
    equipe, sugestao, nome, args, _metodo
):
    """GET em qualquer um dos cinco: 301 permanente para `/admin/caixa/`."""
    resposta = equipe.client.get(reverse(nome, args=args))

    assert resposta.status_code == 301, f"{nome}: {resposta.content[:200]}"
    assert resposta["Location"] == CASA_NOVA


@pytest.mark.parametrize("nome,args", [(n, a) for n, a, m in ENDERECOS if m == "post"])
def test_um_POST_de_aba_velha_e_RECUSADO_dizendo_que_nada_foi_salvo(
    equipe, sugestao, nome, args
):
    """O caso que só existe aqui: uma aba aberta desde antes da mudança.

    Ela ainda tem o formulário na tela. Se o POST dela virasse 301, o navegador
    faria um GET no destino, a pessoa cairia na tela nova e leria aquilo como
    confirmação — teria "movido a ideia" sem nada ter acontecido.
    """
    resposta = equipe.client.post(reverse(nome, args=args), {"status": "planejado"})

    assert resposta.status_code == 410
    corpo = resposta.content.decode()
    assert "NÃO foi guardado" in corpo
    assert CASA_NOVA in corpo


@pytest.mark.parametrize("nome,args,_metodo", ENDERECOS)
def test_quem_nao_e_da_equipe_nem_descobre_para_onde_a_gestao_foi(
    dentro, sugestao, nome, args, _metodo
):
    """403 ANTES do redirecionamento — a ordem dos decoradores é o guarda."""
    resposta = dentro.client.get(reverse(nome, args=args))

    assert resposta.status_code == 403
    assert CASA_NOVA not in resposta.content.decode()


# ---------------------------------------------------------------------------
# O caminho até a gestão, no topo de toda página
# ---------------------------------------------------------------------------


def test_a_equipe_tem_link_para_a_fila_no_topo_de_toda_pagina(equipe, sugestao):
    """O link ficou: ele é o atalho de quem tem crachá para a casa nova.

    Apagá-lo obrigaria a equipe a decorar `/admin/caixa/`; mantê-lo custa um
    salto de redirecionamento e nenhuma decoreba.
    """
    corpo = equipe.client.get(reverse("quadro")).content.decode()

    assert reverse("fila") in corpo


def test_o_aluno_nao_ve_esse_link(dentro, sugestao):
    corpo = dentro.client.get(reverse("quadro")).content.decode()

    assert reverse("fila") not in corpo
    assert "moderação" not in corpo
