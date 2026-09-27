"""Prova no navegador: celular (390 px) e teclado nas telas da Comunidade.

TAR-914 — frente A4 da rodada 3 da Comunidade. Prova LOCALMENTE, com dados de
teste, a parte que não precisa de produção (TAR-828 prova o resto, em
produção, quando as contas de teste do mantenedor existirem): as telas da
Comunidade não têm rolagem lateral em 390 px e se navegam só com o teclado.

Molde: `services/quiz/tests/e2e_browser.py` + `quiz_browser.js` (pytest com
`live_server` chamando um roteiro Node de Playwright). O nome `e2e_*.py` fica
fora da coleta padrão da suíte (roda por caminho explícito), e a CI não
precisa de Node.

A rede é dublada como em `tests/test_grupo_de_pratica.py`: nenhum teste desta
célula fala com a `identidade` ou a `alunos` de verdade.
"""

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
from django.conf import settings
from django.contrib.staticfiles.finders import get_finder
from django.test import override_settings

from apps.forum.models import Area, MembroDoGrupo, Pessoa

pytestmark = pytest.mark.django_db(transaction=True)

COOKIE = "cookie-de-teste-opaco"

# Sem e-mail nem nome real nas capturas (o brief exige isso): as duas pessoas
# de teste têm só um identificador de teste, nunca um dado de gente de verdade.
EMAIL_DA_ALUNA = "aluna-e2e@exemplo.test"
EMAIL_DA_PROFESSORA = "professora-e2e@exemplo.test"


@pytest.fixture
def env(monkeypatch):
    for nome, valor in [
        ("IDENTIDADE_API_URL", "http://identidade:8000/interno"),
        ("IDENTIDADE_API_TOKEN", "tok-id"),
        ("ALUNOS_API_URL", "http://alunos:8000/api/alunos"),
        ("ALUNOS_API_TOKEN", "tok-al"),
        ("FORUM_PROFESSORES", ""),
        ("ADMIN_EMAILS", ""),
    ]:
        monkeypatch.setenv(nome, valor)


def dublar_a_sessao_de(monkeypatch, aluna: Pessoa) -> None:
    """A `identidade` reconhece a aluna; a `alunos` confirma a matrícula.

    O mesmo padrão de `tests/test_grupo_de_pratica.py::dublar`: nenhuma
    chamada sai para a rede de verdade, e o cookie que o navegador manda não
    precisa ser um segredo — só precisa existir, porque é a PRESENÇA do
    cookie que `apps/core/sessao.py::_resolver` confere antes de perguntar.
    """
    import httpx

    sessao = {
        "autenticado": True,
        "id": aluna.id_da_plataforma,
        "email": aluna.email,
        "nome_exibido": aluna.nome_exibido,
    }

    def falso_get(self, url, **kwargs):
        endereco = str(url)
        if "identidade" in endereco:
            return httpx.Response(200, json=sessao)
        return httpx.Response(200, json={"categoria": "aluno"})

    monkeypatch.setattr(httpx.Client, "get", falso_get)


def test_as_telas_da_comunidade_funcionam_no_celular_e_so_com_teclado(
    live_server, env, monkeypatch, tmp_path
):
    professora = Pessoa.objects.create(
        id_da_plataforma="p_professora_e2e",
        email=EMAIL_DA_PROFESSORA,
        nome_exibido="Professora E2E",
    )
    aluna = Pessoa.objects.create(
        id_da_plataforma="p_aluna_e2e",
        email=EMAIL_DA_ALUNA,
        nome_exibido="Aluna E2E",
    )
    grupo = Area.objects.create(
        slug="grupo-e2e-comunidade",
        nome="Grupo E2E da Comunidade",
        visibilidade=Area.Visibilidade.TURMA,
        quem_escreve=Area.QuemEscreve.ALUNO,
        curso_id="modelagem-e2e",
        responsavel=professora,
        vagas=10,
    )
    MembroDoGrupo.objects.create(
        grupo=grupo, pessoa=aluna, adicionado_por=professora, motivo="turma de teste"
    )

    dublar_a_sessao_de(monkeypatch, aluna)

    node = shutil.which("node")
    assert node, "Node.js não está instalado; instale o runtime adotado pelo E2E do projeto."

    # As capturas vivem na pasta exclusiva da bancada — nunca no scratchpad
    # compartilhado da sessão (armadilha 538) — e nenhum e-mail ou nome real
    # aparece nelas: a aluna e a professora de teste só têm identificador de
    # teste (EMAIL_DA_ALUNA / EMAIL_DA_PROFESSORA acima).
    pasta_de_capturas = (
        Path(os.environ.get("TEMP") or os.environ.get("TMP") or str(tmp_path))
        / "sitesdoreino-sessoes"
        / "forum-comunidade-celular-e-teclado-no-forum"
        / "capturas"
    )
    pasta_de_capturas.mkdir(parents=True, exist_ok=True)

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
    # `pytest-django` envolve o `live_server` com `StaticFilesHandler` sempre
    # que `django.contrib.staticfiles` está instalado (esta célula está): esse
    # invólucro intercepta `/static/...` ANTES do `urlconf` e serve pelos
    # localizadores do Django, que não conhecem `services/forum/static/` sem
    # `STATICFILES_DIRS` — e a produção nunca passa por este invólucro (é só
    # do teste). Sem isto, `forum.css` e `forum.js` respondem 404 só aqui
    # (medido com `urllib` puro contra o `live_server`, sem Playwright: a
    # mesma resposta), e o navegador real seria o único a notar
    # (`RETROSPECTIVA-FASE-D.md` §8 — não afirme viabilidade sem ler a
    # configuração real).
    with override_settings(STATICFILES_DIRS=[str(Path(settings.BASE_DIR) / "static")]):
        get_finder.cache_clear()
        try:
            resultado = subprocess.run(
                [
                    node,
                    str(roteiro),
                    live_server.url,
                    "localhost",
                    grupo.slug,
                    COOKIE,
                    str(pasta_de_capturas),
                ],
                cwd=Path(__file__).resolve().parents[1],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=120,
                env=ambiente,
            )
        finally:
            get_finder.cache_clear()
    assert resultado.returncode == 0, f"Playwright falhou.\n{resultado.stdout}\n{resultado.stderr}"
    dados = json.loads(resultado.stdout.splitlines()[-1])

    # TELA 1: /comunidade — 390 px sem rolagem lateral, e o Tab a partir do
    # topo chega ao link que leva a pedir ajuda ao grupo, com foco sempre
    # visível pelo caminho.
    assert dados["comunidade"]["scrollOk"] is True, "a Comunidade rolou de lado em 390 px"
    assert dados["comunidade"]["focoSempreVisivel"] is True, (
        "algum elemento focado por Tab na Comunidade ficou sem contorno visível"
    )
    assert dados["comunidade"]["alvo"] == "Apresente-se ao grupo ou peça ajuda"
    assert 1 <= dados["comunidade"]["passosDeTab"] <= 25

    # TELA 2 e 3: a área do grupo (TURMA) e, nela, o pedido de ajuda — mesma
    # URL, mesma tela, a caixa "Abrir uma conversa". 390 px sem rolagem
    # lateral, rótulo acessível nos dois campos do formulário, e o Tab a
    # partir do topo chega ao botão "Publicar" com foco sempre visível.
    assert dados["grupo"]["scrollOk"] is True, "a área do grupo rolou de lado em 390 px"
    assert dados["grupo"]["focoSempreVisivel"] is True, (
        "algum elemento focado por Tab na área do grupo ficou sem contorno visível"
    )
    assert dados["grupo"]["alvo"] == "Publicar"
    assert 1 <= dados["grupo"]["passosDeTab"] <= 25
    assert dados["grupo"]["rotulos"] == {"titulo": True, "texto": True}

    capturas = sorted(p.name for p in pasta_de_capturas.glob("*.png"))
    assert capturas == ["comunidade.png", "grupo.png", "pedir_ajuda.png"], (
        f"capturas esperadas ausentes em {pasta_de_capturas}: encontradas {capturas}"
    )
