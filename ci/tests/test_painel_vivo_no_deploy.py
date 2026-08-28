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
import yaml

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


def test_a_muralha_de_celula_continua_ignorando_o_painel():
    """A ASSIMETRIA entre os dois detectores é deliberada — e frágil.

    São dois, e fazem coisas diferentes:

    - `ci/ci.py::celulas_tocadas` (Python) monta a matriz do `deploy-celula` e
      o escopo do `ci-celula`. **Mapeia** `painel/` ⇒ `admin`.
    - `ci/cerca-de-celula.sh` responde por "1 PR = 1 célula". Casa apenas
      `services/*`, e portanto **ignora** `painel/`.

    O efeito é bom e é o que se quer preservar: um PR que toque `painel/` e uma
    célula continua contando como UMA célula para a muralha, então o gesto do
    `CLAUDE.md` ("ao terminar, registre") nunca esbarra nela.

    O risco é um agente ver o mapeamento no Python, achar que o shell "esqueceu"
    e acrescentar `painel/*` lá — passando a barrar PRs que hoje passam, por
    uniformidade aparente. Este guarda transforma a assimetria em decisão
    escrita: mexer nela é ficar vermelho aqui e ter de justificar.
    """
    cerca = (RAIZ / "ci" / "cerca-de-celula.sh").read_text(encoding="utf-8")
    linhas_de_casamento = [
        linha
        for linha in cerca.splitlines()
        if "painel" in linha and "CELULAS+=" in linha
    ]
    assert not linhas_de_casamento, (
        "a cerca passou a contar `painel/` como célula — isso faz a muralha "
        "'1 PR = 1 célula' barrar PRs que juntam trabalho e registro do livro:\n  "
        + "\n  ".join(linhas_de_casamento)
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
    assert (
        "cp -R painel services/admin/painel_embutido" in texto
    ), "o build da `admin` precisa copiar `painel/` para o contexto"
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
    assert (
        'RAIZ_DA_CELULA / "painel_embutido"' in fonte
    ), "o nome da pasta precisa bater com o `cp` do deploy-celula"


# ---------------------------------------------------------------------------
# A ENTREGA TENTA DE NOVO — e o script que ela roda tem de existir.
# ---------------------------------------------------------------------------
# Desde 28/08/2026 a ativação na VPS é tentada até três vezes: a VPS recusou a
# conexão do runner cinco vezes em três dias (`armadilhas/127`), e com a entrega
# vermelha o site continua servindo a imagem ANTIGA — quem não estivesse olhando
# naquele minuto acharia, no dia seguinte, que a versão nova estava no ar.
#
# O corpo da entrega saiu do YAML para `infra/deploy-celula-na-vps.sh`, porque
# repeti-lo três vezes seria a duplicação que esta casa proíbe. Isso cria uma
# dependência NOVA e silenciosa: o workflow aponta para um caminho, e se esse
# arquivo for renomeado ou movido, o deploy quebra **em produção**, no primeiro
# merge depois — sem nenhum sinal antes.


def _passos_de_ativacao() -> list[dict]:
    fluxo = yaml.safe_load(
        (RAIZ / ".github" / "workflows" / "deploy-celula.yml").read_text(
            encoding="utf-8"
        )
    )
    return [
        passo
        for passo in fluxo["jobs"]["deploy"]["steps"]
        if "ssh-action" in str(passo.get("uses", ""))
    ]


# Os parâmetros que `appleboy/ssh-action@v1` ACEITA. A lista não foi inventada:
# é a que a própria ação imprimiu ao recusar um nome errado, no run 33184186489
# de 28/08/2026. Está aqui porque um nome inválido NÃO derruba a ação — ela
# emite um `##[warning]`, ignora o parâmetro e segue. Foi assim que o deploy
# ficou verde sem executar nada: `script_file` não existe; o certo é
# `script_path`.
INPUTS_DA_ACAO_SSH = {
    "host",
    "port",
    "passphrase",
    "username",
    "password",
    "protocol",
    "sync",
    "use_insecure_cipher",
    "cipher",
    "timeout",
    "command_timeout",
    "key",
    "key_path",
    "fingerprint",
    "proxy_host",
    "proxy_port",
    "proxy_username",
    "proxy_password",
    "proxy_protocol",
    "proxy_passphrase",
    "proxy_timeout",
    "proxy_key",
    "proxy_key_path",
    "proxy_fingerprint",
    "proxy_cipher",
    "proxy_use_insecure_cipher",
    "script",
    "script_path",
    "envs",
    "envs_format",
    "debug",
    "allenvs",
    "request_pty",
    "curl_insecure",
    "capture_stdout",
    "version",
}


def test_nenhum_parametro_inventado_na_acao_de_ssh() -> None:
    """O guarda que faltava, e que custou um deploy verde sem entrega.

    Parâmetro com nome errado não reprova a ação: ela avisa e IGNORA. O
    resultado é uma conexão que abre, não executa nada e sai com sucesso — o
    falso-verde mais caro deste projeto, porque o site continua servindo a
    imagem velha com todos os sinais normais.

    Nenhum outro teste pegaria: o YAML era válido, o script existia, o caminho
    estava certo. O defeito morava só na conversa entre o workflow e a ação.
    """
    for passo in _passos_de_ativacao():
        invalidos = set(passo["with"]) - INPUTS_DA_ACAO_SSH
        assert not invalidos, (
            f"{passo.get('name')}: parâmetro(s) que a ação NÃO conhece: {sorted(invalidos)}. "
            "Ela avisa e ignora — o deploy ficaria verde sem executar nada."
        )


def test_o_script_que_a_entrega_roda_existe_de_verdade() -> None:
    """O caminho apontado no workflow tem de existir no repositório.

    Renomear o script deixaria o workflow verde no lint e vermelho no primeiro
    deploy — em produção, com o site servindo a imagem velha. Isto é barato de
    conferir e caro de descobrir do outro jeito.
    """
    passos = _passos_de_ativacao()
    assert passos, "nenhum passo de ativação na VPS — a varredura está cega"
    for passo in passos:
        caminho = passo["with"].get("script_path")
        assert caminho, f"{passo.get('name')}: sem script_path"
        assert (RAIZ / caminho).is_file(), f"{passo.get('name')}: {caminho} não existe"


def test_a_entrega_prova_que_rodou_ate_o_fim() -> None:
    """Conectar não é entregar, e o workflow tem de saber a diferença.

    O script imprime uma sentinela na última linha; um passo do workflow EXIGE
    vê-la. Sem essa dupla, uma conexão que abre e não executa nada volta a
    contar como sucesso.
    """
    script = (RAIZ / "infra" / "deploy-celula-na-vps.sh").read_text(encoding="utf-8")
    assert "ENTREGA-CONCLUIDA:" in script, "o script não imprime a marca de conclusão"

    fluxo = (RAIZ / ".github" / "workflows" / "deploy-celula.yml").read_text(
        encoding="utf-8"
    )
    assert "ENTREGA-CONCLUIDA:" in fluxo, (
        "nenhum passo exige a marca de conclusão — conectar sem executar voltaria "
        "a ser tratado como deploy bem-sucedido"
    )
    for passo in _passos_de_ativacao():
        assert (
            passo["with"].get("capture_stdout") is True
        ), f"{passo.get('name')}: sem capture_stdout, a marca não chega ao passo que a exige"


def test_a_entrega_tenta_mais_de_uma_vez() -> None:
    """Uma tentativa só é o desenho que custou cinco reruns manuais."""
    assert len(_passos_de_ativacao()) >= 2, (
        "a ativação na VPS voltou a ter uma tentativa só — a VPS recusa a conexão "
        "de forma intermitente (armadilhas/127), e sem retry o deploy fica "
        "vermelho dependendo de alguém estar olhando para pedir de novo"
    )


def test_so_a_ultima_tentativa_decide_o_veredito() -> None:
    """As primeiras não podem derrubar o job; a última não pode ser tolerada.

    Sem `continue-on-error` nas primeiras, o retry não existiria. COM ele na
    última, o deploy ficaria VERDE mesmo sem nunca ter subido a imagem — um
    falso-verde na peça mais cara de todas.
    """
    passos = _passos_de_ativacao()
    assert all(
        p.get("continue-on-error") is True for p in passos[:-1]
    ), "alguma tentativa intermediária não tolera falha — o retry não funciona"
    assert not passos[-1].get("continue-on-error"), (
        "a ÚLTIMA tentativa tolera falha: o deploy ficaria verde sem ter subido "
        "a imagem. É o falso-verde mais caro que este projeto pode ter."
    )


def test_todas_as_tentativas_rodam_o_MESMO_script() -> None:
    """Três caminhos diferentes seriam três entregas diferentes.

    É o motivo de o script ter saído do YAML: uma definição só do que a entrega
    faz, chamada N vezes.
    """
    caminhos = {p["with"].get("script_file") for p in _passos_de_ativacao()}
    assert len(caminhos) == 1, f"tentativas rodando scripts diferentes: {caminhos}"


def test_a_celula_chega_ao_script_por_variavel() -> None:
    """O script aborta com CELULA vazia; o workflow precisa mesmo passá-la.

    Sem isto, `docker compose up -d` sem argumento subiria a plataforma
    inteira — e é justamente contra isso que o script tem a trava de parada.
    """
    for passo in _passos_de_ativacao():
        assert "CELULA" in str(
            passo["with"].get("envs", "")
        ), f"{passo.get('name')}: não repassa CELULA"
        assert "CELULA" in (
            passo.get("env") or {}
        ), f"{passo.get('name')}: não define CELULA"
