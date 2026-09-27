"""Guarda de `0029_publicar_o_manual_de_experimentacao.py`.

**Por que este arquivo fabrica DUAS causas de produção, e não uma.** O
sintoma medido é um só (`/docs/plataforma-experimentacao-e-aprendizado-de-
conversao` responde 404, e a lista de `/docs/` não mostra o manual), mas ele
tem duas causas possíveis atrás de `semear_documento` ser `get_or_create`
(`armadilhas/253` e `347`): uma linha PRIVADA que já existia quando a `0028`
rodou (ela não teria feito nada), ou a linha nunca ter existido (pasta
ausente na imagem daquele deploy). `test_publicar_manual_experimentacao.py`
já prova o caminho feliz de banco novo — e é justamente esse caminho feliz
que fica cego para as duas causas de produção. Este arquivo fabrica as duas.

Os testes usam uma pasta de documentos PRÓPRIA (`monkeypatch` em
`documentos.CANDIDATOS`), não a `documentos/` real: o corpo publicado muda a
cada revisão do manual, e casar contra o texto de hoje tornaria este teste
frágil à primeira frase reescrita. O hash do texto semeado pela `0028`
também é trocado por um fabricado, pelo mesmo motivo — comparar com o hash
real do commit `3118c765` exigiria embutir aqui o texto de ontem inteiro.
"""

import hashlib
import importlib

from django.test import Client

from apps.core import documentos
from apps.core.models import Documento

_migracao = importlib.import_module(
    "apps.core.migrations.0029_publicar_o_manual_de_experimentacao"
)

NOME = "plataforma-experimentacao-e-aprendizado-de-conversao"
TITULO_DA_SEMENTE = "Plataforma de Experimentação e Aprendizado de Conversão"
CORPO_DE_ONTEM = "# Manual\n\nTexto antigo, semeado pela 0028."
CORPO_DE_HOJE = "# Manual\n\nTexto revisado, com o capítulo novo."


class _AppsFalso:
    @staticmethod
    def get_model(app_label, model_name):
        assert (app_label, model_name) == ("core", "Documento")
        return Documento


def _semente(tmp_path, *, corpo: str = CORPO_DE_HOJE, publico: str = "true"):
    pasta = tmp_path / "documentos"
    pasta.mkdir()
    (pasta / f"{NOME}.md").write_text(
        f"---\ntitulo: {TITULO_DA_SEMENTE}\npublico: {publico}\nordem: 13\n---\n\n"
        + corpo,
        encoding="utf-8",
    )
    return pasta


def _rodar():
    _migracao.publicar_e_atualizar(_AppsFalso, None)


# ------------------------------------------------ causa 1: linha PRIVADA já existia


def test_linha_privada_pre_existente_fica_publica(db, tmp_path, monkeypatch):
    """A `0028` (`get_or_create`) encontrou uma linha privada e não mexeu nela.

    Simula um rascunho criado antes do manual ganhar `publico: true` no
    cabeçalho, ou qualquer outra origem da linha privada: o texto gravado não
    bate com o hash antigo conhecido, então só o ESTADO muda.
    """
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME, titulo="Rascunho", corpo="rascunho privado", publico=False
    )

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is True
    assert documento.arquivado is False
    # Conteúdo não reconhecido como o semeado pela 0028: fica como estava.
    assert documento.corpo == "rascunho privado"
    assert documento.titulo == "Rascunho"
    assert Client().get(f"/docs/{NOME}").status_code == 200
    assert NOME in Client().get("/docs/").content.decode()


def test_linha_arquivada_volta_ao_ar(db, tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME, titulo="Manual", corpo="texto", publico=True, arquivado=True
    )

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.arquivado is False
    assert Client().get(f"/docs/{NOME}").status_code == 200


# ------------------------------------------------ causa 2: linha nunca existiu


def test_linha_ausente_nasce_publica_com_o_texto_da_semente(db, tmp_path, monkeypatch):
    """A pasta embutida faltou num deploy anterior (`armadilhas/347`): a
    `0028` voltou `False` sem gravar nada. Com a pasta presente agora, a
    linha nasce direto no estado certo."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    Documento.objects.filter(nome=NOME).delete()

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.publico is True
    assert documento.arquivado is False
    assert documento.corpo == CORPO_DE_HOJE
    assert Client().get(f"/docs/{NOME}").status_code == 200


def test_sem_a_pasta_na_imagem_nao_estoura(db, tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "CANDIDATOS", (tmp_path / "nao-existe",))
    Documento.objects.filter(nome=NOME).delete()

    _rodar()  # não levanta

    assert not Documento.objects.filter(nome=NOME).exists()


# ------------------------------------------------ atualização do conteúdo (item 2)


def test_corpo_igual_ao_hash_antigo_e_trocado_pelo_texto_novo(
    db, tmp_path, monkeypatch
):
    """A linha já estava pública, com o texto que a 0028 semeou ontem: o
    hash bate, então o conteúdo publicado sobe para a revisão de hoje."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    hash_de_ontem = hashlib.sha256(CORPO_DE_ONTEM.encode("utf-8")).hexdigest()
    monkeypatch.setattr(_migracao, "SHA256_CORPO_SEMEADO_PELA_0028", hash_de_ontem)
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME,
        titulo="Título de ontem",
        corpo=CORPO_DE_ONTEM,
        publico=True,
        ordem=99,
    )

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.corpo == CORPO_DE_HOJE
    assert documento.titulo == TITULO_DA_SEMENTE
    assert documento.ordem == 13
    assert documento.publico is True


def test_corpo_diferente_do_hash_antigo_e_do_novo_nao_e_tocado(
    db, tmp_path, monkeypatch
):
    """O mantenedor reescreveu o manual pela tela: nem o hash antigo nem o
    texto novo batem com o que está gravado. O pior desfecho seria apagar
    essa escrita — então a migração não encosta no corpo."""
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    hash_de_ontem = hashlib.sha256(CORPO_DE_ONTEM.encode("utf-8")).hexdigest()
    monkeypatch.setattr(_migracao, "SHA256_CORPO_SEMEADO_PELA_0028", hash_de_ontem)
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(
        nome=NOME,
        titulo="Editado pelo dono",
        corpo="Ele reescreveu tudo.",
        publico=False,
    )

    _rodar()

    documento = Documento.objects.get(nome=NOME)
    assert documento.corpo == "Ele reescreveu tudo."
    assert documento.titulo == "Editado pelo dono"
    # O ESTADO continua sendo a decisão do mantenedor, mesmo com texto dele.
    assert documento.publico is True


def test_rodar_duas_vezes_nao_muda_nada_na_segunda(db, tmp_path, monkeypatch):
    monkeypatch.setattr(documentos, "CANDIDATOS", (_semente(tmp_path),))
    Documento.objects.filter(nome=NOME).delete()
    Documento.objects.create(nome=NOME, titulo="Rascunho", corpo="x", publico=False)

    _rodar()
    primeiro = (
        Documento.objects.get(nome=NOME).corpo,
        Documento.objects.get(nome=NOME).publico,
    )
    _rodar()
    segundo = (
        Documento.objects.get(nome=NOME).corpo,
        Documento.objects.get(nome=NOME).publico,
    )

    assert primeiro == segundo == ("x", True)
