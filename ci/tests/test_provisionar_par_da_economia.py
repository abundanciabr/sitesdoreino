"""O script que liga a tela dos interruptores da economia, EXECUTADO — não lido.

`infra/provisionar-par-da-economia.sh` liga o par `admin→gamificacao` escrevendo
três chaves em dois `env` da VPS. Ele roda **na máquina do mantenedor**, com uma
linha, e um erro ali custa o pior tipo de tempo que este projeto tem: o dele, no
terminal, sem saber o que fazer com a tela — a lição de 24/08/2026, quando um
passo entregue como texto falhou três vezes seguidas com ele.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_par_da_caixa.py` e mede as mesmas promessas, mais uma que só
existe aqui:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`).
2. **Rodar de novo não rotaciona** — trocar um token em uso dá 401 intermitente.
3. **O par fica igual dos dois lados** — valor diferente é 401 silencioso.
4. **Recusa fail-closed de verdade**: `env` faltando para **sem escrever nada**.
5. **O token NÃO é o mesmo do par com o catálogo** — o `admin.env` já carrega um
   `TOKEN_CATALOGO`, e reusá-lo faria a rotação de um derrubar o outro sem
   aviso. É a promessa que este par tem e o da Caixa não tinha o que ter.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-par-da-economia.sh"

GAMIFICACAO_URL = "http://gamificacao:8000/api/gamificacao"
TOKEN_DO_MENU = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"

SEMENTES = {
    "gamificacao.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\nSITE_ID=abc\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor. E COM o
    # `TOKEN_CATALOGO` do par do menu, que é o vizinho que não pode ser reusado.
    "admin.env": f"DJANGO_SECRET_KEY=z\nTOKEN_CATALOGO={TOKEN_DO_MENU}\nADMIN_EMAILS=dono@exemplo.com",
}


def _bash() -> str:
    caminho = shutil.which("bash")
    assert caminho, (
        "não achei `bash` nesta máquina. Este guarda EXECUTA o script; sem "
        "interpretador ele não tem o que medir, e isso não é um OK ([INV-CI01])."
    )
    return caminho


def _plataforma(tmp_path: Path, faltando: str | None = None) -> Path:
    raiz = tmp_path / "plataforma"
    (raiz / "env").mkdir(parents=True)
    for nome, conteudo in SEMENTES.items():
        if nome == faltando:
            continue
        (raiz / "env" / nome).write_text(conteudo, encoding="utf-8")
    return raiz


def _rodar(raiz: Path):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `encoding` explícito: `text=True` sozinho decodifica pelo idioma do sistema
    — em Windows, cp1252 — e estoura na primeira mensagem acentuada do script.
    O env é HERDADO (com `PLATAFORMA_DIR` por cima) porque o script usa
    `openssl`, `stat` e `date`; um PATH inventado mediria a ausência das
    ferramentas, não o script.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(raiz)
    return subprocess.run(
        [_bash(), str(SCRIPT)],
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


def test_o_script_existe_e_e_executavel_por_bash():
    """[INV-CI01] — sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert (
        "PAROU POR SEGURANÇA" in texto
    ), "o script não fala a língua fail-closed da casa"
    # A linha de UMA LINHA que o mantenedor vai colar tem de estar no cabeçalho:
    # é ela que faz este passo não ser um texto para digitar.
    assert "curl -fsSL" in texto and "provisionar-par-da-economia.sh" in texto


# ------------------------------------------------------------ o caminho feliz


def test_liga_o_par_e_ele_bate_dos_dois_lados(tmp_path):
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    provedor = _valor(raiz, "gamificacao.env", "TOKENS_ACEITOS_ADMIN")
    consumidor = _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO")
    assert provedor and provedor == consumidor, "o par não bate — daria 401 silencioso"
    assert len(provedor) >= 32, f"o token nasceu curto demais: {len(provedor)}"
    assert _valor(raiz, "admin.env", "GAMIFICACAO_API_URL") == GAMIFICACAO_URL


def test_o_token_da_economia_nao_e_o_mesmo_do_menu(tmp_path):
    """Token é POR PAR. Um valor só faria a rotação de um derrubar o outro.

    O `admin.env` já carrega o `TOKEN_CATALOGO` do par do menu, e é justamente
    o valor que alguém copiaria "para simplificar" um dia.
    """
    raiz = _plataforma(tmp_path)

    _rodar(raiz)

    assert _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO") != TOKEN_DO_MENU
    assert _valor(raiz, "admin.env", "TOKEN_CATALOGO") == TOKEN_DO_MENU, (
        "o script mexeu no par do MENU, que não é dele"
    )


def test_a_chave_nova_nao_gruda_na_ultima_linha_de_um_env_sem_quebra(tmp_path):
    """`admin.env` da semente termina SEM quebra de linha — o caso que gruda."""
    raiz = _plataforma(tmp_path)

    _rodar(raiz)

    assert _valor(raiz, "admin.env", "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO")


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """A `armadilhas/090` medida pelo resultado, e não pela leitura do código."""
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    gravado = _valor(raiz, "gamificacao.env", "TOKENS_ACEITOS_ADMIN")
    assert gravado
    assert gravado not in r.stdout, "o token VAZOU para a tela do mantenedor"
    assert gravado not in r.stderr, "o token VAZOU para a saída de erro"


def test_rodar_de_novo_nao_rotaciona(tmp_path):
    """Rotacionar um token em uso dá 401 até o outro lado reiniciar.

    E é o sintoma mais caro de diagnosticar daqui: intermitente, e do lado de
    dentro indistinguível de "esta pessoa não tem acesso".
    """
    raiz = _plataforma(tmp_path)

    _rodar(raiz)
    primeiro = _valor(raiz, "gamificacao.env", "TOKENS_ACEITOS_ADMIN")
    segunda = _rodar(raiz)

    assert segunda.returncode == 0, segunda.stdout + segunda.stderr
    assert _valor(raiz, "gamificacao.env", "TOKENS_ACEITOS_ADMIN") == primeiro
    assert _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO") == primeiro


# ------------------------------------------------------------- as recusas


def test_pasta_errada_para_sem_escrever_nada(tmp_path):
    """O erro mais provável dele: rodar no PC em vez de rodar na VPS."""
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(tmp_path / "nao-existe")
    r = subprocess.run(
        [_bash(), str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "VPS" in r.stdout, "a recusa não ensina o caminho"


def test_env_faltando_para_antes_de_escrever_qualquer_coisa(tmp_path):
    """Fail-closed de verdade: para ANTES, não avisa e escreve mesmo assim."""
    raiz = _plataforma(tmp_path, faltando="gamificacao.env")

    r = _rodar(raiz)

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    # E o env que EXISTE ficou intacto: nada de meio-caminho.
    assert _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO") is None
    assert _valor(raiz, "admin.env", "GAMIFICACAO_API_URL") is None


def test_o_provedor_e_escrito_antes_do_consumidor():
    """A ordem é deliberada, e a inversa tem janela ruim.

    Consumidor com token que o provedor ainda não aceita responde 401 para gente
    de verdade. Provedor que aceita um token que ninguém usa ainda não faz nada.
    Medido no texto porque a ordem entre duas escritas não tem como ser
    observada de fora depois que as duas terminaram.
    """
    texto = SCRIPT.read_text(encoding="utf-8")
    provedor = texto.index('garantir "$ENV_GAMIFICACAO" TOKENS_ACEITOS_ADMIN')
    consumidor = texto.index('garantir "$ENV_ADMIN" TOKEN_GAMIFICACAO')
    assert provedor < consumidor, "o consumidor foi escrito antes do provedor"


def test_o_veredito_do_reinicio_vem_do_comando_e_nao_do_pipe(tmp_path):
    """ARMADILHAS §5.10: `if cmd | tail` mede o `tail`, que dá 0 quase sempre.

    Este guarda existe porque o defeito É INVISÍVEL no caminho feliz — e o
    caminho feliz é o único que roda numa máquina de teste. Aqui o `docker` é
    garantidamente ausente (PATH vazio, um diretório só), então o reinício
    FALHA de verdade; com o `if cmd | tail -5` o script diria PRONTO assim
    mesmo, e o mantenedor abriria uma tela morta sem nada explicando por quê.

    O que se mede: com o reinício falhando, a palavra PRONTO **não** aparece, e
    a saída ENSINA o próximo passo em vez de mentir.
    """
    raiz = _plataforma(tmp_path)
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(raiz)
    # PATH com um diretório vazio: some `docker`, ficam `openssl`/`stat`/`date`
    # como builtins do bash? Não — por isso o teste só afirma sobre o DESFECHO
    # do reinício, que é a última etapa, depois de tudo já estar gravado.
    vazio = tmp_path / "sem-ferramentas"
    vazio.mkdir()
    ambiente["PATH"] = f"{vazio}{os.pathsep}{ambiente.get('PATH', '')}"
    ambiente["DOCKER_HOST"] = "tcp://127.0.0.1:1"  # não há daemon aqui

    r = subprocess.run(
        [_bash(), str(SCRIPT)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )

    # O par TEM de ficar gravado: a falha é do reinício, não da escrita.
    provedor = _valor(raiz, "gamificacao.env", "TOKENS_ACEITOS_ADMIN")
    assert provedor and provedor == _valor(raiz, "admin.env", "TOKEN_GAMIFICACAO")
    assert "PRONTO." not in r.stdout, (
        "o script anunciou PRONTO com o reinicio FALHANDO — e o ramo de erro "
        "virou codigo morto (ARMADILHAS §5.10). Saida: " + r.stdout
    )
    assert "FALHOU" in r.stdout, r.stdout
    assert "docker compose up -d" in r.stdout, "a recusa nao ensina o proximo passo"
