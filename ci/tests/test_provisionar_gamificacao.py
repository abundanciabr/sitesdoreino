"""O provisionamento da gamificação, EXECUTADO — não lido.

`infra/provisionar-gamificacao.sh` é o ÚNICO passo manual que a célula
`gamificacao` pede do mantenedor (`PLANO-CELULA-GAMIFICACAO.md` §6, passo H).
Ele roda na VPS, com uma linha, e um erro ali custa o pior tipo de tempo que
este projeto tem: o dele, no terminal, sem saber o que fazer com a tela — a
lição de 24/08/2026, quando um passo entregue como texto falhou três vezes
seguidas com ele.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path` (com um `docker` de mentira no PATH), em vez de afirmar
coisas sobre o texto dele. É irmão de `test_provisionar_par_da_caixa.py`.

A PROMESSA QUE ESTE ARQUIVO EXISTE PARA MEDIR: `SITE_ID` NUNCA FICA VAZIO
--------------------------------------------------------------------------
O contrato congelado não tem `site_id` em nenhuma operação e a célula não tem
middleware para resolver o site pelo Host: quem responde "de que site é este
perfil?" é o env, lido em `apps/core/sessao.py::site_atual()`.

Ausente, a porta responde SEM etiqueta e a página fica sem selo, **sem quebrar
nada** — é a falha ABERTA que o contrato manda. E é por ser aberta que ela se
esconde: o nível e o título de TODOS os alunos da escola somem de uma vez e
nenhuma tela avisa. Um provisionamento que terminasse "com sucesso" deixando o
campo vazio entregaria exatamente esse silêncio.

Então a régua aqui não é "o script menciona SITE_ID". É: **quando o catálogo não
dá uma resposta única, o script sai diferente de zero e não escreve env nenhum.**
Meia-instalação com etiqueta apagada é pior do que instalação nenhuma.

FAIL-CLOSED DE INSTRUMENTAÇÃO ([INV-CI01])
------------------------------------------
Sem `bash`, sem o script, ou com o script vazio, estes testes **reprovam** em vez
de passar por não ter o que medir. "Não consegui olhar" nunca é "está limpo".
"""

from __future__ import annotations

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-gamificacao.sh"

ENV_IDENTIDADE = "DJANGO_SECRET_KEY=z\nTOKENS_ACEITOS_FUNIL=abc\n"

UM_SITE = "11111111-1111-1111-1111-111111111111\tmeshcraft.top\n"
DOIS_SITES = UM_SITE + "22222222-2222-2222-2222-222222222222\tbasileiatoutheou.org\n"

# O `docker` de mentira. Ele responde às quatro perguntas que o script faz e é
# governado por variáveis de ambiente, para cada teste montar o seu cenário sem
# reescrever o stub.
DOCKER_FALSO = """#!/usr/bin/env bash
[ "${1:-}" = "compose" ] || exit 0
shift
case "${1:-}" in
  ps)
    if [ "${2:-}" = "--status" ]; then
      printf 'postgres\\n'
      [ "${FAKE_CATALOGO_RODANDO:-1}" = "1" ] && printf 'catalogo\\n'
      printf 'identidade\\n'
    fi
    exit 0
    ;;
  config)
    printf 'postgres\\ncatalogo\\nidentidade\\n'
    exit 0
    ;;
  up)
    exit 0
    ;;
  exec)
    for arg in "$@"; do
      case "$arg" in
        catalogo)
          [ "${FAKE_CATALOGO_FALHA:-0}" = "1" ] && exit 1
          printf '%b' "${FAKE_SITES:-}"
          exit 0
          ;;
        postgres)
          # `-tAc` é a consulta "o banco já existe?"; vazio = não existe.
          exit 0
          ;;
      esac
    done
    exit 0
    ;;
esac
exit 0
"""


def _escrever(caminho: Path, conteudo: str) -> None:
    """Sempre com LF: um shebang seguido de CRLF não roda em Linux."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with open(caminho, "w", encoding="utf-8", newline="\n") as arquivo:
        arquivo.write(conteudo)


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


@pytest.fixture
def plataforma(tmp_path: Path) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    _escrever(raiz / "docker-compose.yml", "services: {}\n")
    _escrever(raiz / "env" / "identidade.env", ENV_IDENTIDADE)

    binario = tmp_path / "bin"
    _escrever(binario / "docker", DOCKER_FALSO)
    (binario / "docker").chmod((binario / "docker").stat().st_mode | stat.S_IEXEC)
    return raiz


def _rodar(raiz: Path, *args: str, **cenario: str):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `encoding` explícito: `text=True` sozinho decodifica pelo idioma do sistema
    — em Windows, cp1252 — e estoura na primeira mensagem acentuada do script.
    O env é HERDADO (com o `docker` falso na FRENTE do PATH) porque o script usa
    `openssl`, `stat`, `sed` e `date`; um PATH inventado mediria a ausência das
    ferramentas, não o script.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(raiz)
    ambiente["PATH"] = str(raiz.parent / "bin") + os.pathsep + ambiente["PATH"]
    ambiente.setdefault("FAKE_SITES", UM_SITE)
    ambiente.update(cenario)
    return subprocess.run(
        [_bash(), str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _valor(raiz: Path, arquivo: str, chave: str) -> str | None:
    texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip() if achado else None


# ------------------------------------------------------- [INV-CI01]: há o quê


def test_o_script_existe_e_e_executavel_por_bash():
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.strip(), "o script está vazio"
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert "PAROU POR SEGURANÇA" in texto, "o script não fala a língua fail-closed da casa"
    # A UMA LINHA que o mantenedor vai colar tem de estar no cabeçalho: é ela
    # que faz este passo não ser um texto para digitar.
    assert "curl -fsSL" in texto and "provisionar-gamificacao.sh" in texto
    saida = subprocess.run([_bash(), "-n", str(SCRIPT)], capture_output=True, text=True)
    assert saida.returncode == 0, saida.stderr


# ------------------------------------------------------------ o caminho feliz


def test_escreve_o_env_com_o_site_id_do_catalogo(plataforma):
    r = _rodar(plataforma)

    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO." in r.stdout, r.stdout
    assert _valor(plataforma, "gamificacao.env", "SITE_ID") == (
        "11111111-1111-1111-1111-111111111111"
    )
    assert _valor(plataforma, "gamificacao.env", "SCRIPT_NAME") == "/conquistas"
    assert "gamificacao_db" in (_valor(plataforma, "gamificacao.env", "DATABASE_URL") or "")


def test_o_par_com_a_identidade_bate_dos_dois_lados(plataforma):
    r = _rodar(plataforma)

    assert r.returncode == 0, r.stdout + r.stderr
    consumidor = _valor(plataforma, "gamificacao.env", "IDENTIDADE_API_TOKEN")
    provedor = _valor(plataforma, "identidade.env", "TOKENS_ACEITOS_GAMIFICACAO")
    assert provedor and provedor == consumidor, "o par não bate — daria 401 silencioso"
    assert len(provedor) >= 32, f"o token nasceu curto demais: {len(provedor)}"
    # O degrau do e-mail NÃO é concedido: esta célula pede só o id opaco.
    assert _valor(plataforma, "identidade.env", "TOKENS_COMPLETOS_GAMIFICACAO") is None


def test_nenhum_segredo_aparece_na_tela(plataforma):
    """O que vai para o terminal vai para o print que ele manda (`armadilhas/090`)."""
    r = _rodar(plataforma)

    assert r.returncode == 0, r.stdout + r.stderr
    for chave in ("DJANGO_SECRET_KEY", "IDENTIDADE_API_TOKEN", "DATABASE_URL"):
        segredo = _valor(plataforma, "gamificacao.env", chave)
        assert segredo, chave
        assert segredo not in r.stdout, f"{chave} vazou para a tela"


def test_rodar_de_novo_nao_rotaciona_o_token_do_par(plataforma):
    """Trocar um token em uso dá 401 intermitente, o mais caro de diagnosticar daqui."""
    _rodar(plataforma)
    primeiro = _valor(plataforma, "identidade.env", "TOKENS_ACEITOS_GAMIFICACAO")

    r = _rodar(plataforma)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(plataforma, "identidade.env", "TOKENS_ACEITOS_GAMIFICACAO") == primeiro
    assert _valor(plataforma, "gamificacao.env", "IDENTIDADE_API_TOKEN") == primeiro


def test_com_dois_sites_o_host_pedido_manda(plataforma):
    r = _rodar(plataforma, "basileiatoutheou.org", FAKE_SITES=DOIS_SITES)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(plataforma, "gamificacao.env", "SITE_ID") == (
        "22222222-2222-2222-2222-222222222222"
    )


# -------------------------------------- a recusa: SITE_ID vazio nunca acontece


def _nao_escreveu_nada(plataforma: Path) -> None:
    assert not (plataforma / "env" / "gamificacao.env").exists(), (
        "o script escreveu o env mesmo tendo parado — meia-instalação com "
        "etiqueta apagada é pior do que instalação nenhuma."
    )
    assert (plataforma / "env" / "identidade.env").read_text(
        encoding="utf-8"
    ) == ENV_IDENTIDADE, "o script mexeu no env da identidade mesmo tendo parado"


def test_recusa_quando_o_catalogo_nao_tem_site_ativo(plataforma):
    """A prova central: sem número de site, o script para e não escreve nada."""
    r = _rodar(plataforma, FAKE_SITES="")

    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout, r.stdout
    assert "NENHUM site ativo" in r.stdout, r.stdout
    _nao_escreveu_nada(plataforma)


def test_recusa_quando_ha_varios_sites_e_ninguem_escolheu(plataforma):
    r = _rodar(plataforma, FAKE_SITES=DOIS_SITES)

    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout, r.stdout
    assert "meshcraft.top" in r.stdout, "não listou os sites para ele escolher"
    _nao_escreveu_nada(plataforma)


def test_recusa_quando_o_host_pedido_nao_existe(plataforma):
    r = _rodar(plataforma, "site-que-nao-existe.top", FAKE_SITES=DOIS_SITES)

    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout, r.stdout
    _nao_escreveu_nada(plataforma)


def test_recusa_quando_o_catalogo_esta_parado(plataforma):
    r = _rodar(plataforma, FAKE_CATALOGO_RODANDO="0")

    assert r.returncode != 0, r.stdout
    assert "catalogo" in r.stdout, r.stdout
    _nao_escreveu_nada(plataforma)


def test_recusa_quando_o_catalogo_nao_responde(plataforma):
    r = _rodar(plataforma, FAKE_CATALOGO_FALHA="1")

    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout, r.stdout
    _nao_escreveu_nada(plataforma)


# ------------------------------------------------------- as outras duas recusas


def test_recusa_sem_o_env_da_identidade(plataforma):
    (plataforma / "env" / "identidade.env").unlink()

    r = _rodar(plataforma)

    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout, r.stdout
    assert not (plataforma / "env" / "gamificacao.env").exists()


def test_a_trava_de_deriva_para_antes_de_apagar_variavel_alheia(plataforma):
    """`armadilhas/111`: o script reescreve o arquivo inteiro."""
    vivo = "SITE_ID=x\nTOKENS_ACEITOS_FORUM=segredo-do-degrau-18\n"
    _escrever(plataforma / "env" / "gamificacao.env", vivo)

    r = _rodar(plataforma)

    assert r.returncode != 0, r.stdout
    assert "TOKENS_ACEITOS_FORUM" in r.stdout, "não disse QUAL variável apagaria"
    assert (plataforma / "env" / "gamificacao.env").read_text(encoding="utf-8") == vivo
