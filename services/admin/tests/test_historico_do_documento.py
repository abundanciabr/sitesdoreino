"""O histórico de um documento — `DECISAO-o-editor-de-documentos.md` §6.

**O que este arquivo protege, em uma frase:** ao tirar o texto dos documentos do
Git para o mantenedor poder edita-los por uma tela, a plataforma perdeu o
`git log` deles. Nao ha mais como ver quem mudou uma frase, nem como voltar
atras. Esta tabela e esta tela sao o que entra no lugar, e por isso entram junto
com a primeira escrita — nunca depois: "a versao anterior" so existe se alguem a
guardou ANTES de sobrescrever.

As quatro coisas medidas aqui:

1. **Toda escrita guarda um retrato.** Criar e editar gravam uma versao, sempre,
   sem condicao nenhuma. Uma escrita que esquecesse de passar por ali abriria um
   buraco silencioso no historico, e ninguem descobriria ate precisar dele.

2. **Voltar atras nao apaga historia: escreve mais uma.** Desfazer uma
   restauracao e restaurar de novo, e nenhuma linha some no caminho. E a
   diferenca entre um historico e um rascunho.

3. **Uma versao pertence a UM documento.** Um POST montado a mao nao copia o
   texto de um documento para dentro de outro.

4. **A recusa nao deixa rastro.** Uma gravacao que o portao do travessao
   recusou nao inventa versao nenhuma: aquele texto nunca esteve no ar.
"""

import httpx
import pytest
import respx
from django.test import Client

from apps.core.models import Documento, VersaoDoDocumento

BASE = "http://identidade:8000/interno"
SESSAO = f"{BASE}/sessao/completa"
COOKIE = "meshcraft_sessao=qualquer-coisa-assinada"
DONO = "dono@exemplo.com"


@pytest.fixture(autouse=True)
def env(settings, monkeypatch):
    monkeypatch.setenv("IDENTIDADE_API_URL", BASE)
    monkeypatch.setenv("IDENTIDADE_API_TOKEN", "token-do-par-admin")
    settings.ADMIN_EMAILS = DONO
    settings.URL_DE_ENTRADA = "/entrar/google"


@pytest.fixture(autouse=True)
def sem_os_semeados():
    """A migração `0003` semeia os documentos de verdade quando o banco de teste
    nasce, e o rollback volta para o estado SEMEADO."""
    Documento.objects.all().delete()


def _dentro() -> Client:
    respx.get(SESSAO).mock(
        return_value=httpx.Response(
            200,
            json={
                "autenticado": True,
                "id": "id-opaco-123",
                "nome_exibido": "Fulano",
                "papel": None,
                "email": DONO,
            },
        )
    )
    c = Client()
    c.defaults["HTTP_COOKIE"] = COOKIE
    return c


# ------------------------------------- 1. toda escrita guarda um retrato


@respx.mock
def test_criar_guarda_a_primeira_versao():
    _dentro().post("/documentos/criar", {"titulo": "Guia", "corpo": "primeiro texto"})

    versao = VersaoDoDocumento.objects.get()
    assert versao.corpo == "primeiro texto"
    assert versao.titulo == "Guia"
    assert versao.salvo_por == DONO
    assert versao.gesto == "criou o documento"


@respx.mock
def test_editar_guarda_a_versao_ANTERIOR_para_dar_para_voltar():
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "primeira versao"})

    cliente.post(
        "/documentos/guia/salvar", {"titulo": "Guia", "corpo": "segunda versao"}
    )

    corpos = list(
        VersaoDoDocumento.objects.order_by("id").values_list("corpo", flat=True)
    )
    assert corpos == ["primeira versao", "segunda versao"]


@respx.mock
def test_a_tela_mostra_as_versoes_da_mais_nova_para_a_mais_velha():
    """É como uma pessoa lê um histórico: o de hoje primeiro, e o de hoje é o
    que está no ar."""
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "a mais velha"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "a mais nova"})

    corpo = cliente.get("/documentos/guia/versoes").content.decode()

    assert corpo.index("a mais nova") < corpo.index("a mais velha")
    assert "é a que está no ar" in corpo


@respx.mock
def test_o_historico_de_um_documento_semeado_diz_que_esta_vazio():
    """Os documentos que vieram da pasta nunca passaram por uma gravação, então
    não têm versão. A tela diz isso, em vez de mostrar uma lista vazia sem
    explicação — vazio sem frase é lido como defeito."""
    Documento.objects.create(nome="antigo", titulo="Antigo", corpo="x")

    corpo = _dentro().get("/documentos/antigo/versoes").content.decode()

    assert "não foi salvo nenhuma vez" in corpo


# ------------------------------------------- 2. voltar atrás escreve mais uma


@respx.mock
def test_voltar_para_uma_versao_antiga_traz_o_texto_de_volta():
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "a primeira"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "a segunda"})
    primeira = VersaoDoDocumento.objects.order_by("id").first()

    cliente.post("/documentos/guia/restaurar", {"versao": primeira.id})

    assert Documento.objects.get(nome="guia").corpo == "a primeira"


@respx.mock
def test_voltar_atras_NAO_apaga_historia_nenhuma():
    """Desfazer uma restauração é restaurar de novo, e nenhuma linha some no
    caminho. É a diferença entre um histórico e um rascunho."""
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "primeira"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "segunda"})
    primeira = VersaoDoDocumento.objects.order_by("id").first()

    cliente.post("/documentos/guia/restaurar", {"versao": primeira.id})

    corpos = list(
        VersaoDoDocumento.objects.order_by("id").values_list("corpo", flat=True)
    )
    assert corpos == ["primeira", "segunda", "primeira"]
    ultima = VersaoDoDocumento.objects.order_by("id").last()
    assert "voltou para a versão" in ultima.gesto


@respx.mock
def test_voltar_atras_devolve_tambem_o_titulo_e_a_publicacao():
    """A versão é um RETRATO, não só o corpo: se voltar trouxesse o texto antigo
    com o título de hoje, o documento ficaria num estado que nunca existiu."""
    cliente = _dentro()
    cliente.post(
        "/documentos/criar", {"titulo": "Nome Antigo", "corpo": "x", "publico": "sim"}
    )
    cliente.post(
        "/documentos/nome-antigo/salvar", {"titulo": "Nome Novo", "corpo": "y"}
    )
    primeira = VersaoDoDocumento.objects.order_by("id").first()

    cliente.post("/documentos/nome-antigo/restaurar", {"versao": primeira.id})

    documento = Documento.objects.get(nome="nome-antigo")
    assert documento.titulo == "Nome Antigo"
    assert documento.publico is True


# --------------------------------- 3. uma versão pertence a UM documento


@respx.mock
def test_voltar_para_uma_versao_de_OUTRO_documento_nao_funciona():
    """O alvo é filtrado dentro do documento da rota. Sem isso, um POST montado
    à mão copiaria o texto de um documento para dentro de outro."""
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "texto do guia"})
    cliente.post("/documentos/criar", {"titulo": "Outro", "corpo": "texto do outro"})
    do_outro = VersaoDoDocumento.objects.get(corpo="texto do outro")

    resposta = cliente.post("/documentos/guia/restaurar", {"versao": do_outro.id})

    assert Documento.objects.get(nome="guia").corpo == "texto do guia"
    assert "recado=sumiu" in resposta["Location"]


# ------------------------------------------- 4. a recusa não deixa rastro


@respx.mock
def test_uma_gravacao_recusada_nao_inventa_versao():
    """Aquele texto nunca esteve no ar: uma versão dele contaria uma história
    que não aconteceu."""
    _dentro().post("/documentos/criar", {"titulo": "Guia", "corpo": "frase — recusada"})

    assert VersaoDoDocumento.objects.count() == 0


# ----------------------------------------------- a porta, como em tudo aqui


@respx.mock
@pytest.mark.parametrize(
    "metodo,caminho",
    [("get", "/documentos/guia/versoes"), ("post", "/documentos/guia/restaurar")],
)
def test_o_historico_nao_responde_sem_cracha(metodo, caminho):
    resposta = getattr(Client(), metodo)(caminho, {})
    assert resposta.status_code in (302, 303), caminho


@respx.mock
def test_voltar_atras_recusa_GET():
    """Um pré-carregador de link não pode reescrever uma página pública."""
    Documento.objects.create(nome="guia", titulo="Guia")
    assert _dentro().get("/documentos/guia/restaurar").status_code == 405


@respx.mock
def test_o_historico_de_um_documento_que_nao_existe_e_404():
    assert _dentro().get("/documentos/fantasma/versoes").status_code == 404
