"""Prova no navegador: o quadro de contribuições e as medalhas, no celular e só com o teclado.

TAR-915 prova LOCALMENTE, com dados de teste, a parte da rodada 3 da Comunidade
que não depende de produção: 390 px sem rolagem lateral e navegação inteira por
Tab em `/conquistas/contribuicoes` e `/conquistas/medalhas`. Não substitui a
TAR-828 (a prova em produção, que espera as contas de teste do mantenedor).

Molde: `services/quiz/tests/e2e_browser.py` (pytest com `live_server` e
`django_db(transaction=True)`, que cria os dados e chama um roteiro Node) e
`services/quiz/tests/quiz_browser.js` (Playwright via `require("playwright")`,
com mensagem clara quando falta instalar).

O nome `e2e_*.py` fica fora da coleta padrão do pytest (que só recolhe
`test_*.py`): este arquivo roda por caminho explícito, e a CI da célula não
precisa de Node para o resto da suíte.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from contextlib import contextmanager
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles import finders
from django.test import override_settings

from apps.core import equipe as porta_da_equipe
from apps.gamificacao import contribuicoes as quadro
from apps.gamificacao.models import Concessao, ConquistaDefinicao, Pessoa

pytestmark = pytest.mark.django_db(transaction=True)

SITE = "site-e2e-comunidade"
ALUNO = "pes-e2e-aluno"
COLEGA = "pes-e2e-colega"
PROFESSORA = "pes-e2e-professora"
MEDALHA = "medalha-e2e-comunidade"

# A tarefa nasce com DUAS vagas e a colega ocupa uma: sobra vaga livre para o
# gesto de assumir, e o nome dela vira o marcador de que a tela NÃO lista quem
# mais assumiu (lei §8, sem ranking nem contagem alheia).
VAGAS_DA_TAREFA = 2

# Teto MEDIDO de passos de Tab até o alvo, com os dados deste teste (a faixa
# de navegação mais o alvo). `passos_ate_o_alvo > 0` sozinho deixaria passar
# até 15 tabstops a mais que o roteiro tolera (MAXIMO_DE_PASSOS do JS): o
# número certo é o TETO, não só "encontrou".
PASSOS_ATE_ASSUMIR = 4
PASSOS_ATE_QUADRO_DE_CONTRIBUICOES = 5


def _pessoa(pessoa_id: str) -> Pessoa:
    pessoa, _ = Pessoa.objects.get_or_create(
        id_da_plataforma=pessoa_id, defaults={"email": f"{pessoa_id}@exemplo.test"}
    )
    return pessoa


def _preparar_dados(monkeypatch) -> None:
    """A sessão de teste nasce do jeito que os testes de tela da célula já fazem."""
    monkeypatch.setattr("apps.core.views.site_atual", lambda: SITE)
    monkeypatch.setattr("apps.core.views.quem_e", lambda request: ALUNO)
    monkeypatch.setenv("URL_DE_ENTRADA", "https://exemplo.test/entrar")
    monkeypatch.setenv("URL_DA_CAPA", "https://exemplo.test/")
    monkeypatch.setenv(porta_da_equipe.VARIAVEL, PROFESSORA)
    porta_da_equipe._ja_avisei_que_a_lista_esta_vazia = False

    tarefa = quadro.publicar(
        site_id=SITE,
        autor_id=PROFESSORA,
        titulo="Gravar um tour do primeiro projeto",
        o_que_entregar="Um vídeo curto mostrando o que foi construído.",
        quem_pode="Quem já concluiu o primeiro módulo.",
        criterios=["Mostra a tela inteira", "Explica em português"],
        responsavel_id=PROFESSORA,
        responsavel_nome="Professora E2E",
        vagas=VAGAS_DA_TAREFA,
    )
    quadro.assumir(tarefa=tarefa, pessoa=_pessoa(COLEGA))

    medalha = ConquistaDefinicao.objects.create(
        slug=MEDALHA,
        site_id=SITE,
        nome="Primeira contribuição da turma",
        classe=ConquistaDefinicao.Classe.MEDALHA,
        familia=ConquistaDefinicao.Familia.COMUNIDADE,
        criterio={"tipo": "contribuicoes_aceitas", "alvo": 1},
        ativa=True,
    )
    Concessao.objects.create(pessoa=_pessoa(ALUNO), site_id=SITE, conquista=medalha)


@contextmanager
def _servindo_o_css():
    """Sob `live_server`, o `django.contrib.staticfiles` embutido do
    pytest-django intercepta `/static/…` ANTES do urlconf desta célula e serve
    pelos finders padrão, que só olham a pasta `static/` DENTRO de cada app.
    O CSS desta célula mora na raiz do projeto (`static/gamificacao.css`,
    servido em produção por `servir_estatico`), então o finder não o acha e a
    tela abre sem estilo: SEM esta correção, o teste veria uma página sem
    contorno de foco e sem a folha que limita a largura em 390 px, e passaria
    por engano. `STATICFILES_DIRS` aqui é só do PROCESSO DE TESTE (nenhuma
    linha de produção muda) e o `cache_clear` é necessário porque o finder de
    arquivos é memorizado por processo."""
    with override_settings(STATICFILES_DIRS=[Path(settings.BASE_DIR) / "static"]):
        finders.get_finder.cache_clear()
        yield
    finders.get_finder.cache_clear()


def _rodar_no_navegador(
    live_server_url: str,
    caminho: str,
    tag_alvo: str,
    texto_alvo: str,
    nome_da_captura: str,
) -> dict:
    node = shutil.which("node")
    assert (
        node
    ), "Node.js não está instalado; instale o runtime adotado pelo E2E do projeto."
    roteiro = Path(__file__).with_name("comunidade_browser.js")
    ambiente = {
        chave: os.environ[chave]
        for chave in (
            "PATH",
            "SYSTEMROOT",
            "WINDIR",
            "USERPROFILE",
            "LOCALAPPDATA",
            "APPDATA",
            "TEMP",
            "TMP",
            "PLAYWRIGHT_BROWSERS_PATH",
            "NODE_PATH",
        )
        if os.environ.get(chave)
    }
    argumentos = [node, str(roteiro), live_server_url, caminho, tag_alvo, texto_alvo]
    # A pasta de capturas é OPCIONAL e só existe na bancada de quem roda a prova
    # localmente (`%TEMP%\sitesdoreino-sessoes\<célula>-<tarefa>\capturas\`); a
    # CI não declara a variável, e o teste prova a mesma coisa sem a imagem.
    pasta_de_capturas = os.environ.get("TAR915_CAPTURAS_DIR")
    if pasta_de_capturas:
        argumentos.append(str(Path(pasta_de_capturas) / nome_da_captura))
    resultado = subprocess.run(
        argumentos,
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=120,
        env=ambiente,
    )
    assert (
        resultado.returncode == 0
    ), f"Playwright falhou em {caminho}.\n{resultado.stdout}\n{resultado.stderr}"
    saida = resultado.stdout.strip().splitlines()
    print(resultado.stdout)  # colado no PR, como o rito exige
    return json.loads(saida[-1])


def test_quadro_de_contribuicoes_cabe_no_celular_e_se_navega_so_com_teclado(
    monkeypatch, live_server
):
    _preparar_dados(monkeypatch)

    with _servindo_o_css():
        dados = _rodar_no_navegador(
            live_server.url,
            "/contribuicoes",
            "button",
            "Assumir esta tarefa",
            "contribuicoes-390px.png",
        )

    assert (
        dados["scroll_width"] <= dados["inner_width"]
    ), f"390 px de rolagem lateral: scrollWidth {dados['scroll_width']} > innerWidth {dados['inner_width']}"
    assert dados["alvo_encontrado"], (
        f"Tab não chegou ao botão 'Assumir esta tarefa' em {dados['passos_maximos']} passos; "
        f"sequência: {dados['sequencia']}"
    )
    assert dados["passos_ate_o_alvo"] <= PASSOS_ATE_ASSUMIR, (
        f"Tab levou {dados['passos_ate_o_alvo']} passos até 'Assumir esta tarefa'; "
        f"o teto medido é {PASSOS_ATE_ASSUMIR}. Sequência: {dados['sequencia']}"
    )
    assert dados[
        "foco_visivel_em_todos_os_passos"
    ], f"Algum elemento focado antes do alvo não mostrou contorno visível: {dados['sequencia']}"

    texto = dados["texto_da_pagina"]
    assert COLEGA not in texto, "o id da colega que já assumiu vazou para a tela"
    assert (
        f"1 de {VAGAS_DA_TAREFA}" not in texto
    ), "contagem de vagas é ranking (lei §8)"
    assert "Há vaga." in texto


def test_medalhas_cabem_no_celular_e_se_navegam_so_com_teclado(
    monkeypatch, live_server
):
    _preparar_dados(monkeypatch)

    with _servindo_o_css():
        dados = _rodar_no_navegador(
            live_server.url,
            "/medalhas",
            "a",
            "quadro de contribuições",
            "medalhas-390px.png",
        )

    assert (
        dados["scroll_width"] <= dados["inner_width"]
    ), f"390 px de rolagem lateral: scrollWidth {dados['scroll_width']} > innerWidth {dados['inner_width']}"
    assert dados["alvo_encontrado"], (
        f"Tab não chegou ao primeiro link de conteúdo em {dados['passos_maximos']} passos; "
        f"sequência: {dados['sequencia']}"
    )
    assert dados["passos_ate_o_alvo"] <= PASSOS_ATE_QUADRO_DE_CONTRIBUICOES, (
        f"Tab levou {dados['passos_ate_o_alvo']} passos até 'quadro de contribuições'; "
        f"o teto medido é {PASSOS_ATE_QUADRO_DE_CONTRIBUICOES}. Sequência: {dados['sequencia']}"
    )
    assert dados[
        "foco_visivel_em_todos_os_passos"
    ], f"Algum elemento focado antes do alvo não mostrou contorno visível: {dados['sequencia']}"

    texto = dados["texto_da_pagina"]
    assert "Conquistada em" in texto
    assert COLEGA not in texto
