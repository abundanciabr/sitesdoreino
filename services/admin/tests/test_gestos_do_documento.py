"""Arquivar, apagar e voltar atrás — `DECISAO-o-editor-de-documentos.md` §4 e §6.

O mantenedor escolheu, com as três opções na mesa: **arquivar e apagar existem,
e são gestos separados**. O que este arquivo trava:

1. **Arquivar tira do ar de verdade, e é reversível.** Sai do site na hora, o
   texto fica inteiro, e desarquivar devolve o documento ao estado em que ele
   estava — inclusive o "era público", que ele não precisa lembrar.

2. **Apagar de vez pede o nome digitado.** É o único gesto desta tela que não se
   desfaz. Uma confirmação que só pergunta "tem certeza?" vira reflexo em uma
   semana; digitar o nome obriga a olhar para o que vai ser destruído.

3. **O histórico é o que entrou no lugar do `git log`.** Ao tirar o texto do
   Git, a plataforma perdeu a memória do que estava escrito antes. Voltar para
   uma versão antiga não apaga nada: escreve mais uma.

4. **Nenhum destes gestos acontece por GET.** Decisão que se aplica por GET é
   decisão que um pré-carregador de link toma sozinho, e um deles aqui destrói
   um texto.
"""

import httpx
import pytest
import respx
from django.test import Client

from apps.auditoria.models import Registro
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


@pytest.fixture
def guia():
    return Documento.objects.create(
        nome="guia", titulo="O guia", corpo="# Oi\n\ntexto do guia", publico=True
    )


# ------------------------------------------- 1. arquivar, e a volta dele


@respx.mock
def test_arquivar_tira_do_site_na_hora(guia):
    _dentro().post("/documentos/guia/arquivar")

    assert Client().get("/docs/guia").status_code == 404
    assert "O guia" not in Client().get("/docs/").content.decode()


@respx.mock
def test_arquivar_NAO_apaga_o_texto(guia):
    """A diferença inteira entre arquivar e apagar cabe nesta asserção."""
    _dentro().post("/documentos/guia/arquivar")

    assert Documento.objects.get(nome="guia").corpo == "# Oi\n\ntexto do guia"


@respx.mock
def test_desarquivar_devolve_o_documento_ao_estado_em_que_ele_estava(guia):
    """Arquivar não é despublicar: `publico` continua gravado como estava.

    Se arquivar zerasse a bandeira, desarquivar exigiria que o mantenedor
    lembrasse se aquele documento era público antes, meses depois. A memória
    fica no banco, não nele.
    """
    cliente = _dentro()
    cliente.post("/documentos/guia/arquivar")
    cliente.post("/documentos/guia/desarquivar")

    documento = Documento.objects.get(nome="guia")
    assert documento.arquivado is False
    assert documento.publico is True
    assert Client().get("/docs/guia").status_code == 200


@respx.mock
def test_o_arquivado_aparece_na_lista_de_dentro_para_dar_para_voltar(guia):
    """Escondido de vez, desarquivar seria impossível — e o texto ficaria preso
    num lugar de que ninguém tem a chave."""
    cliente = _dentro()
    cliente.post("/documentos/guia/arquivar")

    corpo = cliente.get("/documentos/").content.decode()

    assert "Arquivados" in corpo
    assert "O guia" in corpo


@respx.mock
def test_arquivar_nao_grava_versao_nova(guia):
    """O histórico guarda o TEXTO, e nada no texto mudou. Uma linha "arquivou"
    no meio das versões faria "voltar para esta" significar também "e tire do ar
    de novo", que é outra decisão."""
    _dentro().post("/documentos/guia/arquivar")

    assert VersaoDoDocumento.objects.count() == 0
    assert Registro.objects.get().acao == Registro.ARQUIVAR_DOCUMENTO


# ------------------------------------------------- 2. apagar de vez


@respx.mock
def test_apagar_sem_escrever_o_nome_nao_apaga_nada(guia):
    """Uma confirmação que só pergunta "tem certeza?" vira reflexo em uma
    semana, e no dia do clique errado ela não terá parado nada."""
    resposta = _dentro().post("/documentos/guia/apagar", {"confirmacao": ""})

    assert Documento.objects.filter(nome="guia").exists()
    assert "recado=confirmacao" in resposta["Location"]


@respx.mock
def test_apagar_com_o_nome_errado_tambem_nao_apaga(guia):
    _dentro().post("/documentos/guia/apagar", {"confirmacao": "outro-nome"})

    assert Documento.objects.filter(nome="guia").exists()


@respx.mock
def test_apagar_com_o_nome_certo_destroi_o_documento(guia):
    resposta = _dentro().post("/documentos/guia/apagar", {"confirmacao": "guia"})

    assert not Documento.objects.filter(nome="guia").exists()
    assert Client().get("/docs/guia").status_code == 404
    assert "recado=apagado" in resposta["Location"]


@respx.mock
def test_apagar_leva_o_historico_junto(guia):
    """ "Sem volta" que deixa cópia não é sem volta: guardar as versões de um
    documento apagado seria guardar o texto de quem mandou apagá-lo."""
    VersaoDoDocumento.objects.create(documento=guia, titulo="O guia", corpo="antigo")

    _dentro().post("/documentos/guia/apagar", {"confirmacao": "guia"})

    assert VersaoDoDocumento.objects.count() == 0


@respx.mock
def test_o_que_foi_apagado_fica_na_auditoria(guia):
    """A linha é escrita ANTES de apagar, e é o único lugar do sistema em que o
    documento continua existindo. A tabela é append-only por trigger no banco."""
    _dentro().post("/documentos/guia/apagar", {"confirmacao": "guia"})

    registro = Registro.objects.get()
    assert registro.acao == Registro.APAGAR_DOCUMENTO
    assert registro.alvo == "guia"
    assert registro.quem_email == DONO


# ------------------------------------------------ 3. voltar atrás


@respx.mock
def test_voltar_para_uma_versao_antiga_traz_o_texto_de_volta():
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "a primeira versao"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "a segunda"})

    primeira = VersaoDoDocumento.objects.order_by("id").first()
    cliente.post("/documentos/guia/restaurar", {"versao": primeira.id})

    assert Documento.objects.get(nome="guia").corpo == "a primeira versao"


@respx.mock
def test_voltar_atras_NAO_apaga_historia_nenhuma():
    """Ela escreve mais uma. Desfazer uma restauração é restaurar de novo, e
    nenhuma linha some no caminho — que é a diferença entre um histórico e um
    rascunho."""
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "primeira"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "segunda"})
    primeira = VersaoDoDocumento.objects.order_by("id").first()

    cliente.post("/documentos/guia/restaurar", {"versao": primeira.id})

    corpos = list(
        VersaoDoDocumento.objects.order_by("id").values_list("corpo", flat=True)
    )
    assert corpos == ["primeira", "segunda", "primeira"]
    assert (
        "voltou para a versão" in VersaoDoDocumento.objects.order_by("id").last().gesto
    )


@respx.mock
def test_voltar_para_uma_versao_de_OUTRO_documento_nao_funciona():
    """O alvo é filtrado dentro do documento da rota. Sem isso, um POST montado
    à mão copiaria o texto de um documento para dentro de outro."""
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "texto do guia"})
    cliente.post("/documentos/criar", {"titulo": "Outro", "corpo": "texto do outro"})
    do_outro = VersaoDoDocumento.objects.get(corpo="texto do outro")

    cliente.post("/documentos/guia/restaurar", {"versao": do_outro.id})

    assert Documento.objects.get(nome="guia").corpo == "texto do guia"


@respx.mock
def test_a_tela_de_historico_mostra_as_versoes_da_mais_nova_para_a_mais_velha():
    cliente = _dentro()
    cliente.post("/documentos/criar", {"titulo": "Guia", "corpo": "a mais velha"})
    cliente.post("/documentos/guia/salvar", {"titulo": "Guia", "corpo": "a mais nova"})

    corpo = cliente.get("/documentos/guia/versoes").content.decode()

    assert corpo.index("a mais nova") < corpo.index("a mais velha")
    assert "é a que está no ar" in corpo


@respx.mock
def test_o_historico_de_um_documento_recem_semeado_diz_que_esta_vazio(guia):
    """Os documentos que vieram da pasta nunca passaram por uma gravação, então
    não têm versão. A tela diz isso, em vez de mostrar uma lista vazia sem
    explicação."""
    corpo = _dentro().get("/documentos/guia/versoes").content.decode()

    assert "não foi salvo nenhuma vez" in corpo


# ------------------------------- 4. nenhum gesto acontece por GET nem sem crachá


@respx.mock
@pytest.mark.parametrize(
    "caminho",
    [
        "/documentos/guia/arquivar",
        "/documentos/guia/desarquivar",
        "/documentos/guia/apagar",
        "/documentos/guia/restaurar",
    ],
)
def test_os_gestos_recusam_GET(caminho, guia):
    """Um pré-carregador de link, um antivírus corporativo ou um crawler
    autenticado disparam GET sozinhos — e um destes destrói um texto."""
    assert _dentro().get(caminho).status_code == 405


@pytest.mark.parametrize(
    "caminho",
    [
        "/documentos/guia/arquivar",
        "/documentos/guia/desarquivar",
        "/documentos/guia/apagar",
        "/documentos/guia/versoes",
        "/documentos/guia/restaurar",
    ],
)
def test_nenhum_gesto_responde_sem_cracha(caminho):
    resposta = Client().post(caminho, {})
    assert resposta.status_code in (302, 303), caminho


@respx.mock
def test_gesto_em_documento_que_nao_existe_e_404():
    assert _dentro().post("/documentos/fantasma/arquivar").status_code == 404
    assert _dentro().get("/documentos/fantasma/versoes").status_code == 404


# --------------------------------- 5. a porta na sala de comando


@respx.mock
def test_a_visao_geral_tem_a_porta_para_os_documentos():
    """O pedido dele foi "uma parte no PAINEL do admin".

    A area de documentos existia desde 29/08/2026, mas so de leitura e sem
    porta na visao geral: quem nao soubesse o endereco de cor nao chegava nela.
    Um botao que ninguem encontra e uma funcionalidade que nao existe.
    """
    corpo = _dentro().get("/").content.decode()

    assert "/documentos/" in corpo
    assert "documentos do site" in corpo
