"""[INVARIANTE] O papel é DERIVADO a cada requisição — nunca gravado.

A promessa da EVO-01 §4, que esta célula herda por escrito
(DECISAO-onde-mora-a-sessao §5.3): trocar quem é staff é editar uma variável e
reiniciar — sem migração, sem deploy. Papel gravado na linha ou no cookie
quebraria isso em silêncio: tirar alguém da lista não tiraria o crachá de quem
já estava dentro.
"""

from apps.identidade.models import Identidade

TOKEN = "token-do-par-funil-identidade"


def _papel(porta, settings) -> str:
    settings.TOKENS_ACEITOS = {TOKEN}
    resposta = porta.client.get(
        "/interno/sessao", headers={"authorization": f"Bearer {TOKEN}"}
    )
    return resposta.json()["papel"]


def test_entrar_na_lista_vale_sem_novo_login(dentro, lista_da_staff, settings):
    assert _papel(dentro, settings) == "aluno"
    lista_da_staff("joao.silva@exemplo.test")
    assert _papel(dentro, settings) == "staff"


def test_sair_da_lista_derruba_o_cracha_na_hora(
    entrar_como, lista_da_staff, settings, monkeypatch
):
    lista_da_staff("chefe@exemplo.test")
    pessoa = entrar_como(email="chefe@exemplo.test", nome="Chefe")
    assert _papel(pessoa, settings) == "staff"
    monkeypatch.setenv("IDENTIDADE_STAFF_EMAILS", "")
    assert _papel(pessoa, settings) == "aluno"


def test_o_modelo_nao_tem_coluna_de_papel():
    """A metade estrutural: não existe onde gravar papel — e é assim que fica."""
    campos = {campo.name for campo in Identidade._meta.get_fields()}
    assert campos == {"id", "email", "provedor", "nome_exibido", "criada_em"}
