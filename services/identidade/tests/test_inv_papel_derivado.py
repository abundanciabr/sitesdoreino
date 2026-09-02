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
    """A metade estrutural: não existe onde gravar papel — e é assim que fica.

    `senha_hash` (DECISAO-login-por-senha.md) entrou na lista em 31/08/2026 —
    é o segundo jeito de provar QUEM É, não um papel; continua fora daqui
    qualquer coluna que guardasse o QUE a pessoa pode fazer.

    `idioma` entrou em 02/09/2026, pelo Rito de Contrato do e-mail de verdade,
    e a régua que o admite é a mesma: ele descreve COMO FALAR com a pessoa, não
    o que ela pode fazer. Nenhuma porta desta plataforma consulta o idioma para
    decidir se alguém entra — e o dia em que uma consultar, este teste não vai
    pegar, porque ele mede o modelo e não o uso. O que ele garante é o mais
    barato de garantir e o mais caro de perder: que a coluna não exista.

    A lista é branca DE PROPÓSITO, e é por isso que ela dá trabalho: campo novo
    obriga quem o cria a vir aqui e escrever por que ele não é um papel. Uma
    lista negra (`"papel" not in campos`) passaria batido no dia em que alguém
    chamasse a coluna de `nivel_de_acesso`.
    """
    campos = {campo.name for campo in Identidade._meta.get_fields()}
    assert campos == {
        "id",
        "email",
        "provedor",
        "nome_exibido",
        "criada_em",
        "senha_hash",
        "idioma",
    }
