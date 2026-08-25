"""[INVARIANTE] Identidade apagada ⇒ o cookie deixa de valer NO MESMO INSTANTE.

Guarda repatriado: ele existia na `sugestoes` e não veio junto na mudança de
casa do login (25/08/2026). A auditoria provou por mutação que sem ele um
agente pode "otimizar" `ator_atual` para não bater no banco — e nada fica
vermelho.

**Por que este guarda é estrutural, e não um detalhe:** o cookie desta célula é
ASSINADO e SEM ESTADO (`signed_cookies`). Não existe tabela de sessão para
apagar, não existe lista de revogação. A reconferência da linha no banco a cada
leitura é a **única** revogação que existe hoje — é o que separa "posso tirar
alguém do ar agora" de "a sessão vale até o cookie expirar, e não há o que
fazer". Quem trocar isso por um cache, ou por confiar no conteúdo assinado,
está removendo o freio de mão da plataforma inteira.
"""

from apps.core import sessao as ses
from apps.identidade.models import Identidade

TOKEN = "token-do-par-funil-identidade"


def test_identidade_apagada_derruba_a_sessao_no_request_seguinte(dentro, settings):
    settings.TOKENS_ACEITOS = {TOKEN}

    def perguntar():
        return dentro.client.get(
            "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
        ).json()

    assert perguntar()["autenticado"] is True, "a pessoa deveria estar dentro"

    # A ÚNICA revogação que existe nesta célula.
    Identidade.objects.filter(pk=dentro.identidade.id).delete()

    assert perguntar() == {"autenticado": False}, (
        "o cookie continuou valendo depois de a identidade ser apagada — a "
        "revogação da plataforma inteira deixou de existir"
    )


def test_ator_atual_reconfere_no_banco_e_nao_confia_no_cookie(dentro):
    """A metade mecânica do mesmo invariante, medida sem passar pela API.

    Se alguém trocar a reconferência por leitura do conteúdo do cookie, este
    guarda cai — mesmo que a API continue respondendo certo por outro caminho.
    """
    Identidade.objects.all().delete()

    requisicao = type("R", (), {"session": dentro.client.session})()

    assert ses.ator_atual(requisicao) is None


def test_a_sessao_carrega_o_id_e_MAIS_NADA(dentro):
    """[INVARIANTE] O cookie é assinado, não cifrado — quem o tem LÊ o conteúdo.

    E-mail ou papel dentro dele viram dado pessoal legível por qualquer um com
    o cookie (ou com um log de proxy), desfazendo em silêncio a EVO-01 §3; e
    papel dentro dele quebraria a promessa "editar a variável e reiniciar"
    (EVO-01 §4), porque quem já estava dentro manteria o crachá antigo.
    """
    assert set(dentro.client.session.keys()) == {
        ses.CHAVE_IDENTIDADE
    }, "a sessão passou a carregar mais do que o identificador opaco"
