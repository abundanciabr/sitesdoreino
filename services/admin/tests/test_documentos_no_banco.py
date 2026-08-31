"""O texto dos documentos mora no BANCO — `DECISAO-o-editor-de-documentos.md`.

O mantenedor pediu em 31/08/2026 uma tela para gerenciar e editar os
documentos. A frase parece de tela, mas decide onde o dado mora: o disco do
container é remontado a cada atualização da plataforma, então uma edição
gravada no arquivo embutido some no deploy seguinte, **em silêncio**.

Este arquivo trava as quatro consequências dessa mudança:

1. **A fonte é a tabela, e mais nada.** Mexer no `.md` da pasta depois da
   semeadura não muda o que o site publica. É o guarda que fica vermelho se
   alguém "consertar" a leitura de volta para o disco e desfizer a decisão sem
   perceber.

2. **A semeadura acontece, e acontece UMA vez.** Ela é a migração `0003`, e
   nunca sobrescreve o que já está lá: um documento editado pelo mantenedor não
   é desfeito, e um documento apagado por ele não volta do túmulo.

3. **Arquivar tira do ar de verdade.** Um documento com `publico=True` e
   `arquivado=True` responde 404 na área pública e some da lista de lá.

4. **`publico` continua fail-CLOSED**, agora no default da coluna: um documento
   criado sem dizer nada nasce privado.
"""

import pytest
from django.test import Client

from apps.core import documentos
from apps.core.models import Documento


# --------------------------------- 1. a fonte é a tabela, e mais nada


def test_a_migracao_ja_semeou_os_documentos_do_repositorio():
    """A carga inicial roda no `migrate` do boot, sem passo manual nenhum.

    Se ela virar um `manage.py semear_documentos` disparado à mão, este teste
    fica vermelho — e o que ele está protegendo é `meshcraft.top/docs/`, uma
    página PÚBLICA que já existe, ficando vazia no ar até alguém apertar um
    botão que ninguém lembra que existe.
    """
    assert Documento.objects.filter(nome="como-funciona-a-entrada").exists()
    assert Documento.objects.filter(nome="jornada-do-aluno").exists()


def test_mexer_no_arquivo_da_pasta_NAO_muda_o_que_o_site_publica(tmp_path, monkeypatch):
    """O guarda central desta decisão, escrito pelo avesso.

    Depois da semeadura, a pasta é história: ela diz de onde o texto partiu, não
    o que ele é hoje. Se este teste ficar vermelho, alguém religou a leitura ao
    disco — e o efeito disso em produção é o mantenedor editar pela tela, ver a
    mudança, e ela sumir sozinha na próxima atualização da plataforma.
    """
    Documento.objects.create(nome="aviso", titulo="No banco", publico=True)
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path,))
    (tmp_path / "aviso.md").write_text(
        "---\ntitulo: No arquivo\npublico: true\n---\ntexto do disco",
        encoding="utf-8",
    )

    documento = documentos.ler("aviso")

    assert documento.titulo == "No banco"
    assert "texto do disco" not in documento.corpo


def test_um_nome_fora_do_padrao_nao_existe():
    """A coluna é `SlugField` e aceita maiúscula e sublinhado; a ROTA não casa
    nenhum dos dois. Um documento assim seria inalcançável, existindo só na
    lista — então ele não é encontrado nem por quem perguntar direto."""
    Documento.objects.create(nome="Nome_Torto", titulo="X")
    assert documentos.ler("Nome_Torto") is None


# --------------------------------- 2. a semeadura, e o que ela nunca faz


def test_semear_duas_vezes_nao_duplica_nem_sobrescreve(tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path,))
    Documento.objects.all().delete()
    (tmp_path / "guia.md").write_text(
        "---\ntitulo: Do arquivo\n---\noriginal", encoding="utf-8"
    )

    assert documentos.importar_da_pasta(Documento) == 1
    Documento.objects.filter(nome="guia").update(titulo="Editado pelo dono")
    assert documentos.importar_da_pasta(Documento) == 0

    assert Documento.objects.filter(nome="guia").count() == 1
    assert Documento.objects.get(nome="guia").titulo == "Editado pelo dono"


def test_a_semeadura_sem_a_pasta_na_imagem_nao_estoura(monkeypatch, tmp_path):
    """Ela não faz nada, e a subida continua.

    Falhar aqui deixaria a célula inteira em crashloop no `migrate` (a lição
    H18) por causa de um passo de conteúdo. Uma lista vazia é visível na hora; a
    célula fora do ar leva o site junto.
    """
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))
    assert documentos.importar_da_pasta(Documento) == 0


# --------------------------------- 3. arquivar tira do ar de verdade


@pytest.fixture
def so_o_arquivado():
    Documento.objects.all().delete()
    return Documento.objects.create(
        nome="antigo",
        titulo="Aviso Velho",
        corpo="texto que saiu do ar",
        publico=True,
        arquivado=True,
    )


def test_o_arquivado_responde_404_mesmo_sendo_publico(so_o_arquivado):
    """`publico` sozinho não responde "está no ar?", e é por isso que existe o
    `no_ar`. Arquivar não é despublicar: a decisão anterior fica gravada, para
    desarquivar devolver o documento ao estado em que ele estava."""
    resposta = Client().get("/docs/antigo")

    assert resposta.status_code == 404
    assert "texto que saiu do ar" not in resposta.content.decode()


def test_o_arquivado_some_da_lista_publica(so_o_arquivado):
    assert "Aviso Velho" not in Client().get("/docs/").content.decode()
    assert documentos.listar(so_publicos=True) == []


def test_o_arquivado_continua_existindo_para_quem_administra(so_o_arquivado):
    """Ele precisa aparecer em algum lugar, senão desarquivar seria impossível.

    E `com_arquivados` tem default `False` de propósito: esquecer o argumento
    ESCONDE um documento, o que é barulhento e o dono reclama. Esquecer o
    `so_publicos` publicaria um texto interno, que é silencioso.
    """
    assert documentos.ler("antigo") is not None
    assert documentos.listar(so_publicos=False) == []
    assert [
        d.nome for d in documentos.listar(so_publicos=False, com_arquivados=True)
    ] == ["antigo"]


def test_pedir_publicos_vence_pedir_arquivados(so_o_arquivado):
    """Nenhuma tela mostra ao visitante o que foi tirado do ar, então esta
    combinação não responde a pergunta de ninguém. Ela existe só como caminho
    possível de chamada, e o que ela NÃO pode fazer é vazar o arquivado."""
    assert documentos.listar(so_publicos=True, com_arquivados=True) == []


# --------------------------------- 4. `publico` continua fail-CLOSED


def test_um_documento_criado_sem_dizer_nada_nasce_privado():
    """A lei do §2 da `DECISAO-a-area-de-documentos`, agora no default da
    coluna. Enquanto o texto morava em arquivo, quem garantia isto era a
    igualdade exata com "true" no cabeçalho."""
    novo = Documento.objects.create(nome="rascunho", titulo="Rascunho")

    assert novo.publico is False
    assert novo.no_ar is False
    assert Client().get("/docs/rascunho").status_code == 404
