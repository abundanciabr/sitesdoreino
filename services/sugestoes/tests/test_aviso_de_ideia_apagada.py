# tests/test_aviso_de_ideia_apagada.py
"""A ideia apagada não deixa recado para trás.

O BURACO, achado pelo MANTENEDOR em produção em 31/08/2026, minutos depois de
o esvaziamento da Caixa rodar: as ideias sumiram do quadro, e o aviso sobre
elas continuou no perfil dele. Um cartão de título VAZIO — porque `apagar`
esvazia o título — com a justificativa da equipe ainda legível ao lado, e um
link para uma ideia que ninguém mais alcança.

Isso contraria por escrito a `DECISAO-apagar-ideia.md`, que ele assinou com as
próprias palavras: *"que ela desapareça completamente do sistema, desapareça
até mesmo para quem a criou"*. Quem a criou é exatamente quem tinha o aviso.

POR QUE O CORTE É NA LEITURA, E NÃO NA ESCRITA
-----------------------------------------------
O recado que a pessoa lê hoje NÃO mora nesta célula: mora na caixa central
(`contracts/notificacoes.openapi.yaml`), e aquele contrato está congelado com
quatro operações — resumo, listar, marcar uma como lida, marcar todas. **Não
existe retirar.** Enquanto não existir (mudança de contrato é Rito §3), o que
esta célula consegue fazer sozinha é parar de MOSTRAR, na hora de ler, o
recado de uma ideia que ela sabe estar apagada. É o mesmo desenho de
`SugestaoQuerySet.visiveis()`: um corte de visibilidade num lugar só.

A cópia LOCAL do aviso, essa sim, é destruída de verdade — `Aviso` não é
append-only, então apagá-la não encosta na trava que protege a auditoria da
equipe.

O QUE ESTE ARQUIVO NÃO DEIXA VOLTAR
------------------------------------
O sumiço tem de ser CIRÚRGICO. Um filtro largo demais esconderia recado
legítimo, e o remédio seria pior: a pessoa deixaria de saber de coisas que
aconteceram de verdade. Por isso metade dos testes aqui são de coisas que
PRECISAM continuar aparecendo.
"""

import json

import httpx
import pytest
from django.urls import reverse

from apps.core.apagamento import apagar_definitivamente
from apps.core.avisos import ASSUNTO_MATRICULA, ASSUNTO_SUGESTAO
from apps.sugestoes.models import Aviso, Sugestao

pytestmark = pytest.mark.django_db

NOTA_DA_EQUIPE = "Nao entra no roadmap deste semestre."
VAZIO_DE_VERDADE = "Nenhum aviso ainda"


def _carta_de_sugestao(sugestao_id, *, id_="900", nota=NOTA_DA_EQUIPE):
    return {
        "id": id_,
        "assunto": ASSUNTO_SUGESTAO,
        "parametros": {
            "suggestion_id": str(sugestao_id),
            "status_anterior": "em_analise",
            "status_novo": "nao_planejado",
            "vinculo": "autor",
            "nota": nota,
        },
        "ator_id": None,
        "lido_em": None,
        "criado_em": "2026-08-30T09:00:00+00:00",
    }


def _responde_com(rede, cartas):
    """A caixa central respondendo o que ELA guarda.

    Injetar a resposta (em vez de deixar o dublê espelhar o `Aviso` local) é o
    que torna este arquivo fiel à produção: lá a carta continua existindo na
    caixa central mesmo depois de a cópia local ter sido destruída. Um teste
    que dependesse do espelho provaria o oposto do que precisa provar.
    """
    rede.notificacoes_avisos.mock(
        return_value=httpx.Response(200, json={"itens": cartas, "proximo_cursor": None})
    )


# ---------------------------------------------------------------------------
# 1. O buraco que o mantenedor achou
# ---------------------------------------------------------------------------


def test_o_recado_de_uma_ideia_apagada_some_da_tela(dentro, rede, sugestao):
    apagar_definitivamente(sugestao)
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert VAZIO_DE_VERDADE in corpo


def test_a_justificativa_da_equipe_nao_sobrevive_na_tela(dentro, rede, sugestao):
    """A `nota` viaja DENTRO da carta, então ela não some junto com a ideia.

    Era o pior pedaço do buraco: o texto que a equipe escreveu sobre a ideia
    continuava legível depois de a ideia ter sido destruída.
    """
    apagar_definitivamente(sugestao)
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert NOTA_DA_EQUIPE not in corpo


def test_o_contador_da_pagina_nao_conta_o_que_ela_nao_mostra(dentro, rede, sugestao):
    """Guarda de soma: lista e número saem da MESMA lista já filtrada.

    Se o corte ficasse depois da contagem, a página diria "1 não lido" com
    nada embaixo — que é a doença que esta casa persegue por toda parte.
    """
    apagar_definitivamente(sugestao)
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "1 não lido" not in corpo


def test_apagar_destroi_a_copia_local_do_recado(dentro, sugestao):
    Aviso.objects.create(
        destinatario=dentro.identidade,
        sugestao=sugestao,
        status_anterior=Sugestao.Status.EM_ANALISE,
        status_novo=Sugestao.Status.NAO_PLANEJADO,
        nota=NOTA_DA_EQUIPE,
    )

    apagar_definitivamente(sugestao)

    assert Aviso.objects.filter(sugestao=sugestao).count() == 0


# ---------------------------------------------------------------------------
# 2. O que PRECISA continuar aparecendo (o filtro não pode ser largo)
# ---------------------------------------------------------------------------


def test_o_recado_de_uma_ideia_viva_continua_aparecendo(dentro, rede, sugestao):
    """O controle. Sem ele, um filtro que escondesse TUDO passaria verde."""
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert sugestao.titulo in corpo
    assert NOTA_DA_EQUIPE in corpo


def test_recado_de_ideia_apenas_arquivada_continua_aparecendo(dentro, rede, sugestao):
    """Arquivar não é apagar, e a diferença importa aqui.

    Arquivada é reversível e o conteúdo dela está inteiro (`DECISAO-arquivar-
    ideia.md`); quem recebeu o recado tem direito de continuar lendo o que
    aconteceu. Só o apagamento definitivo, que destrói o conteúdo, tira o
    recado junto.
    """
    from django.utils import timezone

    sugestao.arquivada_em = timezone.now()
    sugestao.save(update_fields=["arquivada_em"])
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert sugestao.titulo in corpo


def test_carta_de_outro_assunto_nao_e_tocada(dentro, rede, quadro):
    """Carta sem `suggestion_id` não pode entrar no filtro por omissão.

    O `quadro` não é enfeite na assinatura: sem nenhum quadro no banco a
    página devolve 404, e um teste que só cobrasse a AUSÊNCIA de uma frase
    passaria verde lendo a tela de erro do Django. Foi o que aconteceu aqui na
    primeira rodada — por isso as asserções abaixo cobram presença, não
    ausência.
    """
    _responde_com(
        rede,
        [
            {
                "id": "901",
                "assunto": ASSUNTO_MATRICULA,
                "parametros": {"matricula_id": "7", "situacao_nova": "ativa"},
                "ator_id": None,
                "lido_em": None,
                "criado_em": "2026-08-30T09:00:00+00:00",
            }
        ],
    )

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert "Você é aluno" in corpo
    assert VAZIO_DE_VERDADE not in corpo


def test_carta_de_ideia_que_esta_caixa_nao_acha_continua_aparecendo(
    dentro, rede, quadro
):
    """Não achar a ideia é DIFERENTE de saber que ela foi apagada.

    Pode ser carta de outro quadro. Sumir com ela seria esconder um recado
    legítimo por não saber lê-lo, e a pessoa nunca saberia que existia.
    """
    _responde_com(rede, [_carta_de_sugestao(999_999)])

    resposta = dentro.client.get(reverse("avisos"))
    corpo = resposta.content.decode()

    assert resposta.status_code == 200
    assert VAZIO_DE_VERDADE not in corpo
    assert "sugestão não encontrada" in corpo


def test_uma_apagada_no_meio_nao_leva_as_outras(
    dentro, rede, sugestao, quadro, categoria, aluno
):
    """O filtro é por linha, não por página."""
    viva = Sugestao.objects.create(
        quadro=quadro,
        categoria=categoria,
        autor=aluno,
        titulo="Esta continua de pe",
        problema="E precisa continuar aparecendo.",
    )
    apagar_definitivamente(sugestao)
    _responde_com(
        rede,
        [
            _carta_de_sugestao(sugestao.pk, id_="900"),
            _carta_de_sugestao(viva.pk, id_="901"),
        ],
    )

    corpo = dentro.client.get(reverse("avisos")).content.decode()

    assert "Esta continua de pe" in corpo
    assert VAZIO_DE_VERDADE not in corpo


# ---------------------------------------------------------------------------
# 5. O sino também para de contar — o buraco que o conserto de 31/08 deixou
#
# O corte acima tira o recado da TELA. O número do sino, porém, vem da caixa
# central, que não sabe de apagamento nenhum: ele continuava dizendo "1" para
# uma lista vazia (registro `20260831-012`, achado pelo mantenedor).
#
# E o `nao_lidos` da página é somado DEPOIS do corte, então o botão "Marcar
# tudo como lido" — que só aparece `{% if nao_lidos %}` — sumia junto: a
# pessoa ficava com um número que não tinha como zerar por caminho nenhum.
#
# A cura NÃO é operação nova no contrato congelado (que era a conclusão de
# 31/08): `marcarUmaComoLida` já existe, é idempotente, e o id do recado vem
# na mesma resposta que a tela já pediu. É `armadilhas/293` — as portas
# existentes compõem o gesto.
# ---------------------------------------------------------------------------


def test_o_recado_escondido_para_de_contar_no_sino(dentro, rede, sugestao):
    """O guarda que vai do vermelho ao verde: esconder passou a incluir calar."""
    apagar_definitivamente(sugestao)
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk, id_="900")])

    dentro.client.get(reverse("avisos"))

    assert rede.notificacoes_marcar_lida.call_count == 1, (
        "a tela escondeu o recado e não o marcou como lido — o sino continua "
        "contando um recado que a pessoa não tem como ver nem zerar"
    )
    enviado = json.loads(rede.notificacoes_marcar_lida.calls[0].request.content)
    assert enviado["id"] == "900"


def test_o_recado_de_ideia_viva_nunca_e_marcado_pela_tela(dentro, rede, sugestao):
    """A contraprova, sem a qual o guarda de cima passaria com o remédio errado.

    Marcar tudo como lido ao abrir a página zeraria o sino — e apagaria, de
    quebra, o aviso legítimo que a pessoa ainda não leu. O remédio tem de ser
    cirúrgico: só o que o corte escondeu.
    """
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])

    dentro.client.get(reverse("avisos"))

    assert rede.notificacoes_marcar_lida.call_count == 0


def test_orfao_ja_lido_nao_gasta_chamada(dentro, rede, sugestao):
    """Idempotente é barato, mas não de graça: quem já está lido não se remarca."""
    apagar_definitivamente(sugestao)
    carta = _carta_de_sugestao(sugestao.pk)
    carta["lido_em"] = "2026-08-31T10:00:00+00:00"
    _responde_com(rede, [carta])

    dentro.client.get(reverse("avisos"))

    assert rede.notificacoes_marcar_lida.call_count == 0


def test_falha_ao_calar_o_sino_nao_derruba_a_pagina(dentro, rede, sugestao):
    """Fail-ABERTO: calar o sino é conforto, listar certo é a função da tela.

    Esta página fail VISÍVEL na listagem, de propósito. O efeito colateral de
    calar o sino segue a regra oposta: se a caixa central recusar, a pessoa
    continua vendo a lista certa e a próxima visita tenta de novo.
    """
    apagar_definitivamente(sugestao)
    _responde_com(rede, [_carta_de_sugestao(sugestao.pk)])
    rede.notificacoes_marcar_lida.mock(
        side_effect=httpx.ConnectError("connection refused")
    )

    resposta = dentro.client.get(reverse("avisos"))

    assert resposta.status_code == 200
    assert VAZIO_DE_VERDADE in resposta.content.decode()
