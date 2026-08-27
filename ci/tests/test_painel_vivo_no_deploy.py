"""A CARONA DO PAINEL: três peças que só funcionam juntas.

O QUE ISTO GUARDA
-----------------
Desde o PR do painel vivo, a célula `admin` serve `painel/painel.html` +
`painel/registros/` atrás do login do mantenedor. Para que o painel ONLINE
acompanhe o livro, três peças precisam concordar:

1. `ci/ci.py::celulas_tocadas` mapeia `painel/**` ⇒ célula `admin`
   (é ele quem monta a matriz do `deploy-celula` e o escopo do `ci-celula`);
2. o `deploy-celula` escuta `painel/**` no `paths:`
   (sem isso o workflow nem começa, e a peça 1 nunca é consultada);
3. o build da `admin` COPIA `painel/` para dentro do contexto
   (sem isso a imagem sobe sem painel — e o deploy fica verde).

POR QUE UM TESTE, E NÃO UM COMENTÁRIO
--------------------------------------
Porque a falha de qualquer uma das três é **silenciosa e idêntica**: o painel
online simplesmente para no tempo, sem erro em lugar nenhum — nem no CI, nem no
deploy, nem na tela. O mantenedor descobriria do pior jeito possível, que é
olhando um painel velho achando que é o atual. Foi exatamente esse o atrito que
originou o trabalho ("a versão que eu estou vendo ainda está desatualizada").

É o padrão 2 da `docs/decisoes/RETROSPECTIVA-FASE-D.md` — *garantia sem
mecanismo*: uma promessa escrita em comentário não é uma garantia. Aqui a
promessa vira mecanismo.
"""

import re
import subprocess
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
DEPLOY = RAIZ / ".github" / "workflows" / "deploy-celula.yml"

sys.path.insert(0, str(RAIZ / "ci"))


def test_um_arquivo_do_painel_conta_como_a_celula_admin(tmp_path):
    """A peça 1, medida no comportamento real de `celulas_tocadas`.

    O teste monta um repositório de mentira com um commit que só toca
    `painel/registros/`, e pergunta ao código o que ele detectou. Ler o
    `ci.py` atrás da string "painel" não provaria nada: o mapeamento poderia
    estar num ramo morto.
    """
    from ci import celulas_tocadas  # noqa: E402  (depende do sys.path acima)

    def git(*args):
        subprocess.run(
            ["git", *args], cwd=tmp_path, check=True, capture_output=True, text=True
        )

    git("init", "-q", "-b", "main")
    git("config", "user.email", "teste@exemplo.com")
    git("config", "user.name", "teste")
    (tmp_path / "leia.md").write_text("base", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "base")
    base = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    registros = tmp_path / "painel" / "registros"
    registros.mkdir(parents=True)
    (registros / "20260101-001-exemplo.js").write_text("//", encoding="utf-8")
    git("add", "-A")
    git("commit", "-qm", "livro: um registro novo")

    assert celulas_tocadas(tmp_path, base) == ["admin"], (
        "um registro novo no livro precisa contar como a célula `admin` — "
        "senão o merge não dispara deploy e o painel online congela"
    )


def test_o_deploy_escuta_a_pasta_do_painel():
    """A peça 2: sem `painel/**` no `paths:`, o workflow nem começa."""
    texto = DEPLOY.read_text(encoding="utf-8")
    linha = re.search(r"^\s*paths:\s*\[(.+)\]\s*$", texto, re.MULTILINE)
    assert linha, "não achei o `paths:` do gatilho do deploy-celula"
    assert "painel/**" in linha.group(1), (
        "o deploy-celula precisa disparar quando `painel/` muda — "
        f"paths atual: {linha.group(1)}"
    )


def test_o_build_da_admin_embute_o_painel():
    """A peça 3: a cópia para dentro do contexto do build.

    O contexto é `services/admin`, que não alcança `painel/` na raiz. Sem o
    passo de cópia a imagem é publicada sem o painel, a rota responde a tela
    "o painel não veio nesta versão" — e o deploy fica VERDE, porque nada
    falhou. Falso-verde é o padrão 1 da retrospectiva.
    """
    texto = DEPLOY.read_text(encoding="utf-8")
    assert "cp -R painel services/admin/painel_embutido" in texto, (
        "o build da `admin` precisa copiar `painel/` para o contexto"
    )
    assert "test -f painel/painel.html" in texto, (
        "a cópia precisa ser fail-closed: pasta ausente tem de PARAR o build, "
        "nunca publicar uma imagem sem painel"
    )


def test_a_copia_do_painel_nunca_entra_no_repositorio():
    """A lei anti-duplicação, do lado do Git.

    A pasta embutida é gerada no CI. Commitá-la criaria um segundo livro de
    ocorrências dentro do repositório — dois lugares com os mesmos fatos, que é
    o que o `CLAUDE.md` proíbe, e o dia em que divergissem ninguém saberia qual
    vale.
    """
    ignore = (RAIZ / "services" / "admin" / ".gitignore").read_text(encoding="utf-8")
    assert "painel_embutido/" in ignore

    embutido = RAIZ / "services" / "admin" / "painel_embutido"
    if embutido.exists():
        rastreado = subprocess.run(
            ["git", "ls-files", "services/admin/painel_embutido"],
            cwd=RAIZ,
            capture_output=True,
            text=True,
        ).stdout.strip()
        assert not rastreado, f"a cópia do painel foi commitada: {rastreado[:200]}"


def test_a_celula_admin_serve_o_painel_da_raiz():
    """O outro lado da carona: a célula procura a pasta nos dois lugares certos.

    Guarda de leitura, e assumida como tal — o comportamento em si é provado de
    fora por `services/admin/tests/test_painel_vivo.py`, com requisição real.
    O que se trava aqui é o CONTRATO entre o workflow e o código: o nome da
    pasta embutida é o mesmo dos dois lados.
    """
    fonte = (RAIZ / "services" / "admin" / "apps" / "core" / "painel.py").read_text(
        encoding="utf-8"
    )
    assert 'RAIZ_DA_CELULA / "painel_embutido"' in fonte, (
        "o nome da pasta precisa bater com o `cp` do deploy-celula"
    )
