"""O RECONHECIMENTO — e as três formas de ele mentir para quem vai planejar.

Este script responde "a casa sabe fazer isto?" antes de alguém escrever um
plano. As respostas erradas não são simétricas:

    dizer NÃO onde há SIM   custa um PR desnecessário, e alguém percebe cedo
                            (o molde estava lá, o agente acha no caminho);
    dizer SIM onde há NÃO   APAGA do plano o trabalho que sustenta a entrega,
                            e ninguém percebe até o meio da construção.

A primeira versão deste script errou do segundo jeito, duas vezes, na primeira
vez que rodou de verdade (01/09/2026):

    "SIM, a casa guarda arquivo"   porque `minio` casa dentro de "doMINIOs";
    "SIM, a casa serve vídeo"      porque um aluno de mentira escreveu
                                   "YouTube" num semeador de demonstração.

Metade desta suíte encena exatamente esses dois enganos. A outra metade prova
que instrumento quebrado (ref que não existe, mapa do site ausente) vira ERRO
em voz alta, nunca um dossiê limpo dizendo que não há nada.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "ci"))

import reconhecer  # noqa: E402
from _nucleo import ErroDeInstrumentacao  # noqa: E402


def _git(*args: str, cwd: Path) -> None:
    subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
    )


@pytest.fixture()
def repo(tmp_path):
    """Um repositório descartável com a forma mínima que o script lê."""

    def montar(arquivos: dict[str, str]) -> Path:
        raiz = tmp_path / "repo"
        raiz.mkdir(exist_ok=True)
        _git("init", "-b", "main", cwd=raiz)
        _git("config", "user.email", "teste@teste", cwd=raiz)
        _git("config", "user.name", "teste", cwd=raiz)
        for caminho, conteudo in arquivos.items():
            destino = raiz / caminho
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_text(conteudo, encoding="utf-8")
        _git("add", "-A", cwd=raiz)
        _git("commit", "-m", "cenario", cwd=raiz)
        return raiz

    return montar


MAPA_VAZIO = '{"_doc": "teste", "enderecos": []}'


# ---------------------------------------------------------------------------
# Os dois falsos SIM que aconteceram de verdade.
# ---------------------------------------------------------------------------
def test_pedaco_de_palavra_nao_acende_capacidade(repo):
    """`minio` dentro de "domínios" não prova que a casa guarda arquivo."""
    raiz = repo(
        {
            "painel/mapa-do-site.json": MAPA_VAZIO,
            "services/admin/apps/core/views.py": (
                "# a lista de dominios servidos por esta celula\n"
                "DOMINIOS = ('meshcraft.top',)\n"
            ),
        }
    )
    medidas = dict(
        (cap.nome, achados) for cap, achados in reconhecer.medir_capacidades(ref="HEAD", raiz=raiz)
    )
    guardar_arquivo = next(nome for nome in medidas if nome.startswith("Guardar um arquivo"))
    assert medidas[guardar_arquivo] == [], (
        "a palavra 'dominios' acendeu a capacidade de guardar arquivo: a busca "
        "voltou a casar pedaço de palavra, e o plano seguinte vai nascer sem o "
        "trabalho de armazenamento que ele precisa."
    )


def test_texto_de_teste_e_de_semeador_nao_e_mecanismo(repo):
    """Aluno de mentira falando de YouTube não põe vídeo no ar."""
    raiz = repo(
        {
            "painel/mapa-do-site.json": MAPA_VAZIO,
            "services/sugestoes/apps/sugestoes/management/commands/semear_demo.py": (
                'IDEIAS = [("Ninguem explica aprovacao no YouTube", "curso")]\n'
            ),
            "services/gamificacao/tests/test_economia.py": 'ACOES = ("videoaula", "quiz")\n',
        }
    )
    medidas = dict(
        (cap.nome, achados) for cap, achados in reconhecer.medir_capacidades(ref="HEAD", raiz=raiz)
    )
    video = next(nome for nome in medidas if nome.startswith("Servir aula"))
    assert medidas[video] == [], (
        "texto dentro de teste ou de semeador foi contado como mecanismo: o "
        "dossiê vai afirmar que o curso mora no site, e ele não mora."
    )


def test_o_mecanismo_de_verdade_acende(repo):
    """A outra metade: quando existe mesmo, o dossiê diz SIM e mostra onde."""
    raiz = repo(
        {
            "painel/mapa-do-site.json": MAPA_VAZIO,
            "services/portfolio/apps/pecas/models.py": (
                "from django.db import models\n\n"
                "class Peca(models.Model):\n"
                "    imagem = models.ImageField(upload_to='pecas/')\n"
            ),
        }
    )
    medidas = dict(
        (cap.nome, achados) for cap, achados in reconhecer.medir_capacidades(ref="HEAD", raiz=raiz)
    )
    guardar_arquivo = next(nome for nome in medidas if nome.startswith("Guardar um arquivo"))
    assert medidas[guardar_arquivo] == ["services/portfolio/apps/pecas/models.py"], (
        "o campo de imagem existe no código de produção e a capacidade não "
        "acendeu: um portão cego dá falso NÃO, e falso NÃO ensina a ignorá-lo."
    )


# ---------------------------------------------------------------------------
# Instrumento quebrado nunca vira página limpa.
# ---------------------------------------------------------------------------
def test_ref_inexistente_e_erro_e_nao_dossie_vazio(repo):
    raiz = repo({"painel/mapa-do-site.json": MAPA_VAZIO})
    with pytest.raises(ErroDeInstrumentacao) as erro:
        reconhecer.montar(["portfolio"], ref="origin/nao-existe", raiz=raiz)
    assert "não existe" in erro.value.resumo


def test_mapa_do_site_ausente_e_erro(repo):
    """Sem o mapa, "nenhuma rota casa" seria mentira com cara de resposta."""
    raiz = repo({"services/funil/apps/core/views.py": "# vazio\n"})
    with pytest.raises(ErroDeInstrumentacao):
        reconhecer.enderecos_que_casam(["portfolio"], ref="HEAD", raiz=raiz)


def test_git_ausente_nao_vira_silencio(repo, monkeypatch):
    raiz = repo({"painel/mapa-do-site.json": MAPA_VAZIO})

    def _sem_git(*args, **kwargs):
        raise FileNotFoundError("git")

    monkeypatch.setattr(reconhecer.subprocess, "run", _sem_git)
    with pytest.raises(ErroDeInstrumentacao) as erro:
        reconhecer.conferir_ref("HEAD", raiz)
    assert "git" in erro.value.resumo


# ---------------------------------------------------------------------------
# O dossiê em si.
# ---------------------------------------------------------------------------
def test_o_dossie_acha_o_tema_e_declara_de_onde_leu(repo):
    raiz = repo(
        {
            "painel/mapa-do-site.json": (
                '{"_doc": "teste", "enderecos": ['
                '{"celula": "gamificacao", "rota": "estudio", "titulo": "Meu Estudio"}]}'
            ),
            "docs/decisoes/DECISAO-gamificacao.md": "# DECISAO — a vitrine do aluno\n\nportfolio.\n",
            "services/gamificacao/apps/core/views.py": "# o estudio do aluno\n",
        }
    )
    dossie = reconhecer.montar(["portfolio", "estudio"], ref="HEAD", raiz=raiz)

    assert "docs/decisoes/DECISAO-gamificacao.md" in dossie
    assert "DECISAO — a vitrine do aluno" in dossie, (
        "o dossiê listou o caminho sem o título do documento: quem lê precisa "
        "saber o que tem lá dentro sem abrir os doze arquivos."
    )
    assert "`gamificacao` · `estudio`" in dossie
    assert "Lido de:" in dossie, "o dossiê precisa dizer de qual ref e commit ele saiu."


def test_sem_termos_ele_ainda_retrata_as_capacidades(repo):
    raiz = repo({"painel/mapa-do-site.json": MAPA_VAZIO})
    dossie = reconhecer.montar([], ref="HEAD", raiz=raiz)
    assert "O que a casa sabe fazer" in dossie
    assert "Onde o tema já aparece" not in dossie
