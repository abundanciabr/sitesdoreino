"""O script que o mantenedor cola no terminal, EXECUTADO — não lido.

`infra/provisionar-pares-de-categorias.sh` liga as cinco categorias de usuário
(`docs/decisoes/DECISAO-categorias-de-usuario.md`) escrevendo sete chaves em
quatro `env` da VPS. Ele roda **na máquina do mantenedor**, com uma linha, e um
erro ali custa o pior tipo de tempo que este projeto tem: o dele, no terminal,
sem saber o que fazer com a tela.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. As três
promessas medidas são as três que, quebradas, o mantenedor descobre tarde:

1. **Nenhum segredo aparece na tela.** É a `armadilhas/090`: o que vai para o
   terminal vai para o `~/.bash_history`, para o `ps aux` e — o caminho que mais
   pega — para o print que ele manda para provar que funcionou. O teste gera a
   plataforma, roda, e procura o token GRAVADO dentro da saída.

2. **Rodar de novo não rotaciona.** Trocar um token em uso derruba as chamadas
   até o outro lado reiniciar, e o sintoma é 401 intermitente em duas células ao
   mesmo tempo — de longe o mais caro de diagnosticar daqui.

3. **Os pares ficam iguais dos dois lados.** Valor diferente entre
   `TOKENS_ACEITOS_<PAR>` e o `*_API_TOKEN` do consumidor é 401/403 silencioso,
   e do lado de dentro isso é indistinguível de "esta pessoa não tem acesso".

E os caminhos de recusa: pasta errada, `env` faltando, `identidade` sem o token
do funil. Em todos, o script tem de **parar sem escrever nada** — fail-closed de
verdade, não mensagem de aviso seguida de escrita.
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-pares-de-categorias.sh"

# Os quatro env e o mínimo que cada um precisa ter para o script aceitar rodar.
SEMENTES = {
    "alunos.env": "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n",
    # O token do par funil→identidade JÁ existe hoje; é dele que o script copia
    # o degrau de e-mail, e é por isso que ele não pode ser inventado aqui.
    "identidade.env": "DJANGO_SECRET_KEY=y\nTOKENS_ACEITOS_FUNIL=tok-funil-identidade\n",
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "admin.env": "DJANGO_SECRET_KEY=z\nADMIN_EMAILS=dono@exemplo.com",
    "funil.env": "DJANGO_SECRET_KEY=w\nIDENTIDADE_API_TOKEN=tok-funil-identidade\n",
}

PARES = [
    ("alunos.env", "TOKENS_ACEITOS_ADMIN", "admin.env", "ALUNOS_API_TOKEN"),
    ("alunos.env", "TOKENS_ACEITOS_FUNIL", "funil.env", "ALUNOS_API_TOKEN"),
]


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


def _executar(argumentos: list[str], plataforma: str):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `text=True` sozinho decodifica pelo idioma do sistema — em Windows, cp1252 —
    e estoura em `UnicodeDecodeError` na primeira mensagem acentuada do script.
    O `encoding` explícito é o que faz este guarda medir a mesma coisa no PC do
    mantenedor e no runner Linux do CI.

    O env é HERDADO (com `PLATAFORMA_DIR` por cima), e não fabricado: o script
    usa `openssl`, `stat` e `date`, e um PATH inventado os esconderia — o teste
    passaria a medir a ausência das ferramentas, não o script.
    """
    ambiente = dict(os.environ)
    ambiente["PLATAFORMA_DIR"] = plataforma
    return subprocess.run(
        argumentos,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=ambiente,
    )


def _rodar(raiz: Path):
    return _executar([_bash(), str(SCRIPT)], str(raiz))


def _valor(raiz: Path, arquivo: str, chave: str) -> str | None:
    texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
    achado = re.search(rf"^{re.escape(chave)}=(.*)$", texto, re.MULTILINE)
    return achado.group(1).strip() if achado else None


def test_o_script_existe_e_e_executavel_por_bash():
    """[INV-CI01] — sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert "PAROU POR SEGURANÇA" in texto, "o script não fala a língua fail-closed da casa"


# ------------------------------------------------------------ o caminho feliz


def test_liga_os_sete_valores_e_os_pares_batem(tmp_path):
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO:" in r.stdout, r.stdout

    for arquivo, chave, arquivo2, chave2 in PARES:
        a, b = _valor(raiz, arquivo, chave), _valor(raiz, arquivo2, chave2)
        assert a and a == b, f"{chave} ({arquivo}) != {chave2} ({arquivo2})"
        assert len(a) >= 32, f"{chave} nasceu curto demais: {len(a)}"

    # O degrau de e-mail é CÓPIA, nunca um valor novo: dois degraus sobre o
    # mesmo token. Valores diferentes dariam 403 em toda página da home, e o
    # sintoma seria a home abrindo sem saber quem é ninguém.
    assert _valor(raiz, "identidade.env", "TOKENS_COMPLETOS_FUNIL") == "tok-funil-identidade"
    assert _valor(raiz, "identidade.env", "TOKENS_ACEITOS_FUNIL") == "tok-funil-identidade"

    for arquivo in ("admin.env", "funil.env"):
        assert _valor(raiz, arquivo, "ALUNOS_API_URL") == "http://alunos:8000/api/alunos"


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """A `armadilhas/090` medida pelo resultado, e não pela leitura do código."""
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr

    saida = r.stdout + r.stderr
    for arquivo, chave, _, _ in PARES:
        segredo = _valor(raiz, arquivo, chave)
        assert segredo, chave
        assert segredo not in saida, (
            f"o valor de {chave} foi impresso na tela. Ele vai parar no "
            "histórico do shell e no print que o mantenedor manda."
        )
        # Nem um pedaço grande dele: um "eco parcial" para depuração é o jeito
        # mais comum de este guarda ser contornado sem má intenção.
        assert segredo[:16] not in saida


def test_a_chave_nova_nao_gruda_na_ultima_linha_de_um_env_sem_quebra(tmp_path):
    """`admin.env` da semente termina SEM quebra de linha — o caso real."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    texto = (raiz / "env" / "admin.env").read_text(encoding="utf-8")
    assert "ADMIN_EMAILS=dono@exemplo.com\n" in texto, texto
    assert _valor(raiz, "admin.env", "ADMIN_EMAILS") == "dono@exemplo.com"


def test_rodar_de_novo_nao_rotaciona_nada(tmp_path):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    antes = {(a, c): _valor(raiz, a, c) for a, c, _, _ in PARES}

    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nada: já estava tudo ligado" in r.stdout, r.stdout

    depois = {(a, c): _valor(raiz, a, c) for a, c, _, _ in PARES}
    assert antes == depois, "o script rotacionou um token que já estava em uso"


def test_nenhuma_chave_fica_repetida(tmp_path):
    """Chave repetida é o modo de falha mais traiçoeiro de um env.

    O Docker Compose usa a ÚLTIMA ocorrência: um valor velho ficaria por baixo
    do novo, sem nada acusar. Três rodadas, porque o bug apareceria na segunda.
    """
    raiz = _plataforma(tmp_path)
    for _ in range(3):
        assert _rodar(raiz).returncode == 0
    esperado = {
        "alunos.env": ["TOKENS_ACEITOS_ADMIN", "TOKENS_ACEITOS_FUNIL"],
        "identidade.env": ["TOKENS_COMPLETOS_FUNIL"],
        "admin.env": ["ALUNOS_API_URL", "ALUNOS_API_TOKEN"],
        "funil.env": ["ALUNOS_API_URL", "ALUNOS_API_TOKEN"],
    }
    for arquivo, chaves in esperado.items():
        texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
        for chave in chaves:
            n = len(re.findall(rf"^{re.escape(chave)}=", texto, re.MULTILINE))
            assert n == 1, f"{chave} aparece {n} vezes em {arquivo}"


def test_o_par_dessincronizado_a_mao_e_curado_pelo_provedor(tmp_path):
    """Quem manda é a `alunos` — o provedor. O consumidor é realinhado a ela.

    A direção importa: alinhar pelo consumidor deixaria uma célula qualquer
    capaz de mudar o que o provedor aceita.
    """
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    alvo = raiz / "env" / "alunos.env"
    novo = "x" * 40
    alvo.write_text(
        re.sub(
            r"^TOKENS_ACEITOS_ADMIN=.*$",
            f"TOKENS_ACEITOS_ADMIN={novo}",
            alvo.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
    )
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "admin.env", "ALUNOS_API_TOKEN") == novo


# ------------------------------------------------------- os caminhos de recusa


def test_pasta_errada_para_sem_escrever(tmp_path):
    r = _executar([_bash(), str(SCRIPT)], str(tmp_path / "nao-existe"))
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert not (tmp_path / "nao-existe").exists(), "criou a pasta que não achou"


@pytest.mark.parametrize("faltando", sorted(SEMENTES))
def test_env_faltando_para_e_nao_toca_em_nenhum_dos_outros(tmp_path, faltando):
    raiz = _plataforma(tmp_path, faltando=faltando)
    antes = {
        p.name: p.read_text(encoding="utf-8") for p in (raiz / "env").glob("*.env")
    }
    r = _rodar(raiz)
    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout
    depois = {
        p.name: p.read_text(encoding="utf-8") for p in (raiz / "env").glob("*.env")
    }
    assert antes == depois, "parou, mas já tinha escrito em alguém"


def test_identidade_sem_o_token_do_funil_para(tmp_path):
    """Não há de onde copiar o degrau de e-mail — e inventar seria pior.

    Um valor novo em `TOKENS_COMPLETOS_FUNIL` que não casasse com o
    `TOKENS_ACEITOS_FUNIL` daria 403 em toda pergunta da home, e o sintoma seria
    uma home que abre sem reconhecer ninguém.
    """
    raiz = _plataforma(tmp_path)
    alvo = raiz / "env" / "identidade.env"
    alvo.write_text("DJANGO_SECRET_KEY=y\n", encoding="utf-8")
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "TOKENS_ACEITOS_FUNIL" in r.stdout
    assert _valor(raiz, "alunos.env", "TOKENS_ACEITOS_ADMIN") is None, (
        "parou por causa da identidade, mas já tinha escrito na alunos"
    )


def test_carregado_com_source_recusa_em_vez_de_derrubar_a_sessao():
    """O modo de falha de 24/08: `set -e`/`exit` num shell carregado com `.`
    derruba a sessão interativa do mantenedor. Aconteceu, três vezes."""
    r = _executar(
        [_bash(), "-c", f'. "{SCRIPT}"; echo SOBREVIVI'], "/tmp/nao-existe-mesmo"
    )
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "SOBREVIVI" in r.stdout, "o `return` não protegeu a sessão de quem deu source"


# ---------------------------------------------------------- a ordem que importa


def test_o_provedor_e_escrito_antes_dos_consumidores():
    """Ordem inversa tem janela com sintoma: consumidor com token que o provedor
    ainda não aceita responde 401 para gente de verdade. A ordem certa tem
    janela sem sintoma — provedor aceitando um token que ninguém usa ainda.

    Medido no texto porque é ordem de código, não comportamento observável: as
    duas ordens produzem o mesmo arquivo final.
    """
    texto = SCRIPT.read_text(encoding="utf-8")
    pos = {
        alvo: texto.index(f'garantir "$ENV_{alvo}"')
        for alvo in ("ALUNOS", "IDENTIDADE", "ADMIN", "FUNIL")
    }
    assert pos["ALUNOS"] < pos["ADMIN"], "o consumidor admin foi escrito antes do provedor"
    assert pos["ALUNOS"] < pos["FUNIL"], "o consumidor funil foi escrito antes do provedor"
    assert pos["IDENTIDADE"] < pos["FUNIL"], (
        "o funil ganhou o par de alunos antes de a identidade poder lhe dar o e-mail"
    )
