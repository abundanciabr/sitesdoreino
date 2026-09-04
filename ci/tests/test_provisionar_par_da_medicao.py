"""O script que liga o painel na medição, EXECUTADO — não lido.

`infra/provisionar-par-da-medicao.sh` liga o par `admin→metricas`
(`docs/decisoes/PLANO-PAINEL-DE-GESTAO.md` §6.2, degrau 7) escrevendo três
chaves em dois `env` da VPS. Ele roda **na máquina do mantenedor**, com uma
linha, e um erro ali custa o pior tipo de tempo que este projeto tem: o dele, no
terminal, sem saber o que fazer com a tela — a lição de 24/08/2026, quando um
passo entregue como texto falhou três vezes seguidas com ele.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_par_da_caixa.py` e mede as mesmas promessas, porque são as
mesmas que, quebradas, ele descobre tarde:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`) — o que vai para o
   terminal vai para o print que ele manda para provar que funcionou.
2. **Rodar de novo não rotaciona** — trocar um token em uso dá 401 intermitente,
   o mais caro de diagnosticar daqui.
3. **O par fica igual dos dois lados** — valor diferente é 401 silencioso, e do
   lado de dentro é indistinguível de "esta pessoa não tem acesso".
4. **Recusa fail-closed de verdade**: pasta errada ou `env` faltando param
   **sem escrever nada**, e não com aviso seguido de escrita.

E uma quinta, própria desta ligação: **o endereço gravado é o do contrato
congelado**. Se alguém mudar o `servers:` de `contracts/metricas.openapi.yaml`
sem mudar este script, os dois lados continuam "certos" cada um por si e a
ligação quebra em silêncio.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-par-da-medicao.sh"
CONTRATO = RAIZ / "contracts" / "metricas.openapi.yaml"

MEDICAO_URL = "http://metricas:8000/api/metricas"

SEMENTES = {
    "metricas.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\nDEBUG=0\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "admin.env": "DJANGO_SECRET_KEY=z\nADMIN_EMAILS=dono@exemplo.com",
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
    assert "curl -fsSL" in texto and "provisionar-par-da-medicao.sh" in texto


# ------------------------------------------------------------ o caminho feliz


def test_liga_o_par_e_ele_bate_dos_dois_lados(tmp_path):
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO:" in r.stdout, r.stdout
    provedor = _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN")
    consumidor = _valor(raiz, "admin.env", "METRICAS_API_TOKEN")
    assert provedor and provedor == consumidor, "o par não bate — daria 401 silencioso"
    assert len(provedor) >= 32, f"o token nasceu curto demais: {len(provedor)}"
    assert _valor(raiz, "admin.env", "METRICAS_API_URL") == MEDICAO_URL


def test_o_endereco_gravado_e_o_do_contrato_congelado(tmp_path):
    """O `servers:` do contrato é a fonte; este script só o copia.

    Sem este guarda, mudar o endereço no contrato (Rito) e esquecer o script
    deixaria os dois lados coerentes consigo mesmos e incoerentes entre si — a
    quebra mais silenciosa que existe numa ligação entre células.
    """
    assert CONTRATO.is_file(), f"o contrato congelado sumiu: {CONTRATO}"
    assert MEDICAO_URL in CONTRATO.read_text(encoding="utf-8"), (
        f"o endereço {MEDICAO_URL} não está no `servers:` de {CONTRATO.name}. "
        "Um dos dois mudou sem o outro."
    )

    raiz = _plataforma(tmp_path)
    _rodar(raiz)

    assert _valor(raiz, "admin.env", "METRICAS_API_URL") == MEDICAO_URL


def test_a_chave_nova_nao_gruda_na_ultima_linha_de_um_env_sem_quebra(tmp_path):
    """`admin.env` da semente termina SEM quebra de linha — o caso que gruda."""
    raiz = _plataforma(tmp_path)

    _rodar(raiz)

    assert _valor(raiz, "admin.env", "ADMIN_EMAILS") == "dono@exemplo.com"
    assert _valor(raiz, "admin.env", "METRICAS_API_TOKEN")


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """A `armadilhas/090` medida pelo resultado, e não pela leitura do código."""
    raiz = _plataforma(tmp_path)

    r = _rodar(raiz)

    gravado = _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN")
    assert gravado
    assert gravado not in r.stdout, "o token gravado VAZOU para a tela"
    assert gravado not in r.stderr, "o token gravado VAZOU para o stderr"


def test_rodar_de_novo_nao_rotaciona_nada(tmp_path):
    """Trocar um token em uso derruba as chamadas até o outro lado reiniciar."""
    raiz = _plataforma(tmp_path)
    _rodar(raiz)
    antes = _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN")

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN") == antes
    assert _valor(raiz, "admin.env", "METRICAS_API_TOKEN") == antes


def test_um_token_ja_existente_no_provedor_e_reusado_e_nao_substituido(tmp_path):
    """O caso real de quem roda o script DEPOIS de já ter ligado à mão."""
    raiz = _plataforma(tmp_path)
    ja_existia = "x" * 64
    caminho = raiz / "env" / "metricas.env"
    caminho.write_text(
        caminho.read_text(encoding="utf-8") + f"TOKENS_ACEITOS_ADMIN={ja_existia}\n",
        encoding="utf-8",
    )

    r = _rodar(raiz)

    assert r.returncode == 0, r.stdout + r.stderr
    assert _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN") == ja_existia
    assert _valor(raiz, "admin.env", "METRICAS_API_TOKEN") == ja_existia


# ------------------------------------------------------------- as recusas


def test_pasta_errada_para_sem_escrever_nada(tmp_path):
    inexistente = tmp_path / "nao-existe"
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = str(inexistente)

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
    assert not inexistente.exists(), "criou a pasta que devia ter recusado"


def test_env_da_medicao_faltando_para_e_nao_escreve_no_do_admin(tmp_path):
    raiz = _plataforma(tmp_path, faltando="metricas.env")

    r = _rodar(raiz)

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "provisionar-metricas.sh" in r.stdout, "a recusa não ensinou o caminho"
    assert _valor(raiz, "admin.env", "METRICAS_API_TOKEN") is None, (
        "escreveu no consumidor mesmo sem o provedor existir: é a janela de 401 "
        "que a ordem provedor-primeiro existe para evitar"
    )


def test_env_do_admin_faltando_para_e_nao_escreve_no_da_medicao(tmp_path):
    raiz = _plataforma(tmp_path, faltando="admin.env")

    r = _rodar(raiz)

    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert _valor(raiz, "metricas.env", "TOKENS_ACEITOS_ADMIN") is None, (
        "gravou meio par: o provedor passaria a aceitar um token que ninguém "
        "tem, e a conferência do fim nunca rodaria"
    )
