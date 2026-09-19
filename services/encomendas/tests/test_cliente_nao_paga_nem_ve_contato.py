"""As três fronteiras da jornada: o caixa, o contato e a porta.

Definição de pronto da TAR-387, itens 2 e 3.

1. **Não existe rota de pagar** ([lei §3.4], a pausa financeira de 22/08/2026).
   Uma tela que respondesse "ainda não" seria uma promessa com data; uma rota que
   não existe é 404, e 404 não promete nada.
2. **Dado de contato não atravessa papel nenhum** ([INV-ENC-S1], [INV-ENC-S3]).
   O `models.Encomenda.briefing` anotava desde a TAR-120 que *"o guarda deles
   nasce na Fase 3"*. É este arquivo.
3. **A porta é fail-closed duas vezes**: visitante não é ninguém, e quem entrou
   sem a escola ter liberado também não.

POR QUE O TESTE DE CONTATO OLHA OS DOIS LADOS
----------------------------------------------
"Vazar por papel" quer dizer: nada do ALUNO chega ao papel do cliente, e nada
que o cliente escreve chega ao papel da máquina. Medir um lado só deixaria o
outro aberto, e os dois foram abertos por acidente em produtos de verdade.
"""

import httpx
import pytest
import respx

from apps.encomendas import cardapio
from apps.encomendas.models import Encomenda, Pessoa
from tests.conftest import SITE_PADRAO
from tests.test_jornada_do_cliente import (
    BRIEFING,
    CARTAO,
    CLIENTE,
    IDENTIDADE,
    agora,
    entrar,
    env,
    pedido_do_cliente,
    pedir,
)

__all__ = ["env"]

TOKEN_DE_LEITURA = "token-do-par-que-le"


# ---------------------------------------------------------------------------
# 1. NÃO EXISTE ROTA DE PAGAR
# ---------------------------------------------------------------------------


@respx.mock
@pytest.mark.parametrize(
    "caminho",
    [
        "/pagar",
        "/checkout",
        "/pedidos/pagar",
        "/pagamentos",
        "/cobranca",
    ],
)
def test_os_enderecos_de_pagar_nao_existem(client, env, semeado, caminho):
    """Os endereços que alguém escreveria por instinto, um por um."""
    entrar(client)
    assert client.get(caminho).status_code == 404
    assert client.post(caminho).status_code == 404


@respx.mock
def test_um_cartao_inventado_nao_vira_tela_nem_pedido(client, env, semeado):
    """`/cardapio/<qualquer coisa>` casa com a rota do briefing, e por isso ela
    tem de recusar o que não é cartão. A recusa manda de volta ao cardápio
    dizendo o que fazer, e nada nasce no banco."""
    entrar(client)
    resposta = client.get("/cardapio/pagar")
    assert resposta["Location"].endswith(f"recado={cardapio.CARTAO_DESCONHECIDO}")
    assert client.post("/cardapio/pagar/pedir", BRIEFING)["Location"].endswith(
        f"recado={cardapio.CARTAO_DESCONHECIDO}"
    )
    assert not Encomenda.objects.exists()


@respx.mock
def test_o_pedido_de_um_cliente_nao_tem_rota_de_pagar(client, env, semeado):
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    for gesto in ("pagar", "checkout", "cobranca", "pix"):
        assert client.post(f"/pedidos/{projeto.pk}/{gesto}").status_code == 404


@respx.mock
def test_a_tela_do_pedido_nao_convida_a_pagar(client, env, semeado):
    """A palavra que o cliente lê é "a escola confirma", e nunca "pague"."""
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    pagina = client.get(f"/pedidos/{projeto.pk}").content.decode().lower()
    for palavra in ("pagar", "checkout", "cartao de credito", "pix", "boleto"):
        assert palavra not in pagina


# ---------------------------------------------------------------------------
# 2. O BRIEFING BLINDADO
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto",
    [
        "me chama no ana@exemplo.com",
        "whatsapp 11 98765-4321",
        "me acha em @meuperfil",
        "referencias em https://exemplo.com/pasta",
        "fala comigo no www.exemplo.com",
    ],
)
def test_a_peneira_pega_as_quatro_formas_de_contato(texto):
    assert not cardapio.sem_contato(texto)


@pytest.mark.parametrize(
    "texto",
    [
        "Dourado fosco, sem arranhoes, referencia medieval.",
        "Quero 2 variacoes de cor: uma clara e uma escura.",
        "Estilo parecido com o capacete da fase 3 do jogo.",
    ],
)
def test_a_peneira_deixa_passar_um_briefing_de_verdade(texto):
    """Uma peneira que recusasse texto legítimo viraria ruído até alguém a
    desligar, e aí ela não protegeria mais ninguém."""
    assert cardapio.sem_contato(texto)


@respx.mock
def test_o_briefing_com_contato_e_recusado_e_nada_e_gravado(client, env, semeado):
    entrar(client)
    resposta = pedir(client, observacoes="me manda no meu@email.com que eu explico")
    assert resposta["Location"].endswith(f"recado={cardapio.CONTATO_NO_BRIEFING}")
    assert not Encomenda.objects.exists()


@respx.mock
def test_o_teto_do_texto_vem_do_parametro_e_nao_do_codigo(client, env, semeado):
    """O teto é DADO (lei §3.8). Quem o muda é o mantenedor, numa tela, e a
    linha nova passa a valer para o briefing seguinte sem PR nenhum."""
    teto = cardapio.teto_do_texto(agora(), site_id=SITE_PADRAO)
    entrar(client)
    assert pedir(client, observacoes="a" * (teto + 1))["Location"].endswith(
        f"recado={cardapio.OBSERVACOES_LONGAS_DEMAIS}"
    )
    assert not Encomenda.objects.exists()
    assert pedir(client, observacoes="a" * teto).status_code == 302


@respx.mock
def test_o_ajuste_com_contato_e_recusado(client, env, semeado):
    """O segundo e último campo livre do cliente passa pela MESMA peneira:
    deixá-lo aberto teria tornado a peneira do briefing um teatro."""
    from apps.encomendas import acompanhamento

    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    resposta = client.post(
        f"/pedidos/{projeto.pk}/ajuste",
        {"o_que_ajustar": "me liga no 11 91234-5678 que eu explico"},
    )
    assert resposta["Location"].endswith(f"recado={acompanhamento.CONTATO_NO_AJUSTE}")


@respx.mock
def test_campo_a_mais_no_formulario_nao_vira_campo_a_mais_no_banco(
    client, env, semeado
):
    """O briefing é MONTADO pela célula, chave por chave, e não copiado do que
    chegou. É essa montagem que faz "sem campo de contato" valer."""
    entrar(client)
    campos = dict(BRIEFING)
    campos["telefone"] = "11999999999"
    campos["email_do_cliente"] = "eu@exemplo.com"
    assert client.post(f"/cardapio/{CARTAO}/pedir", campos).status_code == 302

    projeto = pedido_do_cliente()
    assert sorted(projeto.briefing) == [
        "entregaveis",
        "estilo",
        "nome_da_peca",
        "observacoes",
        "onde_vai_ser_usada",
    ]


# ---------------------------------------------------------------------------
# 3. O CONTATO NÃO ATRAVESSA PAPEL NENHUM
# ---------------------------------------------------------------------------


@respx.mock
def test_o_cliente_nao_ve_nome_nem_id_do_modelador(client, env, semeado, dois_no_mural):
    """[INV-ENC-S3]. A tela nomeia "o modelador" e o título de Banca dele, e
    mais nada: nem nome exibido, nem e-mail, nem o id opaco."""
    from apps.encomendas import mural

    ana = dois_no_mural[0]
    Pessoa.objects.filter(pk=ana.pessoa_id).update(nome_exibido="Ana Sobrenome Dela")
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()
    assert mural.pegar(projeto.pk, ana.pk, agora(), site_id=SITE_PADRAO).feito

    pagina = client.get(f"/pedidos/{projeto.pk}").content.decode()
    assert "Ana Sobrenome Dela" not in pagina
    assert ana.pessoa_id not in pagina
    assert "modelador" in pagina


@respx.mock
def test_o_que_o_cliente_escreve_nao_sai_pela_porta_de_maquina(
    client, env, semeado, settings
):
    """O outro lado da fronteira: a porta de peças aprovadas devolve o nome da
    peça, e nada mais do que o cliente escreveu ([INV-ENC-S3])."""
    settings.TOKENS_ACEITOS = frozenset({TOKEN_DE_LEITURA})
    entrar(client)
    assert (
        pedir(client, observacoes="Dourado fosco, prazo apertado.").status_code == 302
    )
    projeto = pedido_do_cliente()

    resposta = client.get(
        f"/api/encomendas/perfis/{CLIENTE}/pecas-aprovadas",
        headers={"Authorization": f"Bearer {TOKEN_DE_LEITURA}"},
    )
    assert resposta.status_code == 200
    corpo = resposta.content.decode()
    assert "Dourado fosco" not in corpo
    assert CLIENTE not in corpo
    assert projeto.briefing["observacoes"] == "Dourado fosco, prazo apertado."


# ---------------------------------------------------------------------------
# 4. A PORTA
# ---------------------------------------------------------------------------


@respx.mock
def test_visitante_nao_ve_o_cardapio(client, env):
    assert client.get("/cardapio").status_code == 403


@respx.mock
def test_quem_entrou_sem_a_escola_liberar_tambem_nao_ve(client, env, semeado):
    """Reconhecer não é autorizar, e a resposta é a mesma do visitante.

    O banco entra neste guarda de propósito, e ele é o único da seção em que
    isso importa: sem banco, tirar a porta faria o teste morrer com um erro de
    fixture, e um vermelho por motivo alheio não prova porta nenhuma.
    """
    entrar(client, quem="pes-alguem-qualquer")
    assert client.get("/cardapio").status_code == 403
    assert client.post(f"/cardapio/{CARTAO}/pedir", BRIEFING).status_code == 403
    assert not Encomenda.objects.exists()


@respx.mock
def test_lista_vazia_fecha_a_porta_para_todo_mundo(client, env, monkeypatch):
    """Env ausente não derruba o boot e não quebra tela nenhuma: fecha a porta."""
    monkeypatch.delenv("IDS_DO_PLANTAO")
    entrar(client)
    assert client.get("/cardapio").status_code == 403


@respx.mock
def test_o_pedido_de_outra_pessoa_responde_404(client, env, semeado):
    """A mesma resposta do pedido que não existe: um 403 contaria a um curioso
    que aquele identificador existe e é de alguém."""
    entrar(client)
    assert pedir(client).status_code == 302
    projeto = pedido_do_cliente()

    entrar(client, quem="pes-professora")
    assert client.get(f"/pedidos/{projeto.pk}").status_code == 404
    assert client.post(f"/pedidos/{projeto.pk}/cancelar").status_code == 404
    projeto.refresh_from_db()
    assert projeto.status != Encomenda.Status.CANCELADA
