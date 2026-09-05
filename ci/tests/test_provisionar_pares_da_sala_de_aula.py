"""O script que liga as quatro conversas da sala de aula, EXECUTADO, não lido.

`infra/provisionar-pares-da-sala-de-aula.sh` (degrau 1.8b de
`docs/decisoes/PLANO-CELULA-CURSOS.md` §10) liga os quatro pares que a célula
`cursos` já consome no código (identidade com e-mail, alunos, catalogo) e o par
que a admin consome dela (o editor de aulas), escrevendo treze chaves em cinco
`env` da VPS. Ele roda **na máquina do mantenedor**, com uma linha, e um erro
ali custa o pior tipo de tempo que este projeto tem: o dele, no terminal, sem
saber o que fazer com a tela.

Por isso este guarda **roda o script de verdade**, contra uma plataforma de
mentira em `tmp_path`, em vez de afirmar coisas sobre o texto dele. É irmão de
`test_provisionar_pares_de_categorias.py` e mede as mesmas promessas:

1. **Nenhum segredo aparece na tela** (`armadilhas/090`).
2. **Rodar de novo não rotaciona**, e os tokens que a linha do banco
   (`provisionar-cursos.sh`) já abriu são REUSADOS, nunca substituídos.
3. **Os pares ficam iguais dos dois lados**, e o degrau de e-mail
   (`TOKENS_COMPLETOS_CURSOS`) é CÓPIA de `TOKENS_ACEITOS_CURSOS`: valores
   diferentes dariam 403 e a sala trataria todo mundo como visitante.
4. **Os endereços gravados são os dos contratos congelados**, lidos do
   `servers:` de cada `contracts/*.openapi.yaml`, e não de uma string fixa.
5. **Quatro tokens distintos**: token é por par.

E os caminhos de recusa, todos SEM escrever nada: pasta errada, qualquer um dos
cinco `env` faltando, e o caso próprio desta ligação: `env/cursos.env` ausente
tem de ensinar a linha do banco, porque um env criado aqui antes dela travaria
`provisionar-cursos.sh` para sempre (a trava de deriva dele).
"""

from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parents[2]
SCRIPT = RAIZ / "infra" / "provisionar-pares-da-sala-de-aula.sh"
CONTRATOS = RAIZ / "contracts"

# O que a linha do banco (`provisionar-cursos.sh`) deixa na VPS ANTES deste
# script rodar: os dois pares dela já abertos, com o MESMO valor dos dois lados.
# Longos de propósito: o script recusa token com menos de 32 caracteres.
TOK_IDENTIDADE = "tok-cursos-para-identidade-0123456789abcdef"
TOK_ALUNOS = "tok-cursos-para-alunos-0123456789abcdef"

SEMENTES = {
    "identidade.env": (
        "DJANGO_SECRET_KEY=y\nTOKENS_ACEITOS_FUNIL=tok-funil\n"
        f"TOKENS_ACEITOS_CURSOS={TOK_IDENTIDADE}\n"
    ),
    "alunos.env": (
        "DJANGO_SECRET_KEY=x\nDATABASE_URL=postgres://a\n"
        f"TOKENS_ACEITOS_CURSOS={TOK_ALUNOS}\n"
    ),
    "catalogo.env": "DJANGO_SECRET_KEY=k\nTOKENS_ACEITOS_ADMIN=tok-admin-catalogo\n",
    "cursos.env": (
        "DJANGO_SECRET_KEY=c\nDATABASE_URL=postgres://c\nDEBUG=0\n"
        "SCRIPT_NAME=/cursos\nSITE_ID=00000000-0000-0000-0000-000000000000\n"
        "IDENTIDADE_API_URL=http://identidade:8000/interno\n"
        f"IDENTIDADE_API_TOKEN={TOK_IDENTIDADE}\n"
        "ALUNOS_API_URL=http://alunos:8000/api/alunos\n"
        f"ALUNOS_API_TOKEN={TOK_ALUNOS}\n"
    ),
    # Sem quebra de linha no fim DE PROPÓSITO: é o caso que gruda a chave nova
    # no fim da última linha, e a última linha de um env é um valor.
    "admin.env": "DJANGO_SECRET_KEY=z\nADMIN_EMAILS=dono@exemplo.com",
}

# (provedor, chave no provedor, consumidor, chave no consumidor)
PARES = [
    ("identidade.env", "TOKENS_ACEITOS_CURSOS", "cursos.env", "IDENTIDADE_API_TOKEN"),
    ("alunos.env", "TOKENS_ACEITOS_CURSOS", "cursos.env", "ALUNOS_API_TOKEN"),
    ("catalogo.env", "TOKENS_ACEITOS_CURSOS", "cursos.env", "TOKEN_CATALOGO"),
    ("cursos.env", "TOKENS_ACEITOS_ADMIN", "admin.env", "CURSOS_API_TOKEN"),
]

# (contrato, consumidor, chave do endereço)
ENDERECOS = [
    ("identidade", "cursos.env", "IDENTIDADE_API_URL"),
    ("alunos", "cursos.env", "ALUNOS_API_URL"),
    ("catalogo", "cursos.env", "CATALOGO_API_URL"),
    ("cursos", "admin.env", "CURSOS_API_URL"),
]

CHAVES_ESCRITAS = {
    "identidade.env": ["TOKENS_ACEITOS_CURSOS", "TOKENS_COMPLETOS_CURSOS"],
    "alunos.env": ["TOKENS_ACEITOS_CURSOS"],
    "catalogo.env": ["TOKENS_ACEITOS_CURSOS"],
    "cursos.env": [
        "TOKENS_ACEITOS_ADMIN",
        "IDENTIDADE_API_URL",
        "IDENTIDADE_API_TOKEN",
        "ALUNOS_API_URL",
        "ALUNOS_API_TOKEN",
        "CATALOGO_API_URL",
        "TOKEN_CATALOGO",
    ],
    "admin.env": ["CURSOS_API_URL", "CURSOS_API_TOKEN"],
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


def _executar(argumentos: list[str], plataforma: str):
    """Roda o script e devolve a saída como TEXTO UTF-8.

    `text=True` sozinho decodifica pelo idioma do sistema (em Windows, cp1252)
    e estoura em `UnicodeDecodeError` na primeira mensagem acentuada. O env é
    HERDADO (com `PLATAFORMA_DIR` por cima), e não fabricado: o script usa
    `openssl`, `stat` e `date`, e um PATH inventado os esconderia.
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


def _fotografia(raiz: Path) -> dict[str, str]:
    return {p.name: p.read_text(encoding="utf-8") for p in (raiz / "env").glob("*.env")}


def _endereco_do_contrato(celula: str) -> str:
    """O primeiro `servers:` do contrato congelado, que é a fonte do endereço."""
    contrato = CONTRATOS / f"{celula}.openapi.yaml"
    assert contrato.is_file(), f"o contrato congelado sumiu: {contrato}"
    achado = re.search(
        r"^servers:\s*\n\s*-\s*url:\s*(\S+)", contrato.read_text(encoding="utf-8"), re.MULTILINE
    )
    assert achado, f"não achei o `servers:` em {contrato.name}"
    return achado.group(1)


def test_o_script_existe_e_e_executavel_por_bash():
    """[INV-CI01]: sem isto, os testes abaixo passariam medindo o nada."""
    assert SCRIPT.is_file(), SCRIPT
    texto = SCRIPT.read_text(encoding="utf-8")
    assert texto.startswith("#!/usr/bin/env bash"), "faltou o shebang"
    assert "PAROU POR SEGURANÇA" in texto, "o script não fala a língua fail-closed da casa"


# ------------------------------------------------------------ o caminho feliz


def test_liga_os_quatro_pares_e_eles_batem_dos_dois_lados(tmp_path):
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "PRONTO:" in r.stdout, r.stdout

    valores = []
    for provedor, chave, consumidor, chave2 in PARES:
        a, b = _valor(raiz, provedor, chave), _valor(raiz, consumidor, chave2)
        assert a and a == b, f"{chave} ({provedor}) != {chave2} ({consumidor})"
        assert len(a) >= 32, f"{chave} nasceu curto demais: {len(a)}"
        valores.append(a)
    assert len(set(valores)) == 4, "dois pares ficaram com o mesmo token"


def test_os_tokens_que_a_linha_do_banco_ja_abriu_sao_reusados(tmp_path):
    """`provisionar-cursos.sh` roda ANTES e deixa os pares com identidade e
    alunos abertos. Regerá-los aqui derrubaria a conversa que já funciona."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "identidade.env", "TOKENS_ACEITOS_CURSOS") == TOK_IDENTIDADE
    assert _valor(raiz, "cursos.env", "IDENTIDADE_API_TOKEN") == TOK_IDENTIDADE
    assert _valor(raiz, "alunos.env", "TOKENS_ACEITOS_CURSOS") == TOK_ALUNOS
    assert _valor(raiz, "cursos.env", "ALUNOS_API_TOKEN") == TOK_ALUNOS


def test_o_degrau_de_email_e_copia_do_token_aceito(tmp_path):
    """Dois degraus sobre o MESMO token. Valores diferentes dariam 403 em toda
    pergunta da sala, e o sintoma seria uma sala que trata todo mundo como
    visitante, sem erro em lugar nenhum."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "identidade.env", "TOKENS_COMPLETOS_CURSOS") == TOK_IDENTIDADE


def test_os_enderecos_gravados_sao_os_dos_contratos_congelados(tmp_path):
    """O `servers:` de cada contrato é a fonte; o script só copia. Mudar o
    contrato (Rito) e esquecer o script deixaria os dois lados coerentes consigo
    mesmos e incoerentes entre si."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    for celula, consumidor, chave in ENDERECOS:
        assert _valor(raiz, consumidor, chave) == _endereco_do_contrato(celula), chave


def test_nenhum_segredo_aparece_na_tela(tmp_path):
    """A `armadilhas/090` medida pelo resultado, e não pela leitura do código."""
    raiz = _plataforma(tmp_path)
    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr

    saida = r.stdout + r.stderr
    for provedor, chave, _, _ in PARES:
        segredo = _valor(raiz, provedor, chave)
        assert segredo, chave
        assert segredo not in saida, (
            f"o valor de {chave} foi impresso na tela. Ele vai parar no "
            "histórico do shell e no print que o mantenedor manda."
        )
        # Nem um pedaço grande dele: um "eco parcial" para depuração é o jeito
        # mais comum de este guarda ser contornado sem má intenção.
        assert segredo[:16] not in saida


def test_a_chave_nova_nao_gruda_na_ultima_linha_de_um_env_sem_quebra(tmp_path):
    """`admin.env` da semente termina SEM quebra de linha: o caso real."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    texto = (raiz / "env" / "admin.env").read_text(encoding="utf-8")
    assert "ADMIN_EMAILS=dono@exemplo.com\n" in texto, texto
    assert _valor(raiz, "admin.env", "ADMIN_EMAILS") == "dono@exemplo.com"


def test_rodar_de_novo_nao_rotaciona_nada(tmp_path):
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    antes = _fotografia(raiz)

    r = _rodar(raiz)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "nada: já estava tudo ligado" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "a segunda rodada mexeu em algum arquivo"


def test_nenhuma_chave_fica_repetida(tmp_path):
    """O Docker Compose usa a ÚLTIMA ocorrência: um valor velho ficaria por
    baixo do novo, sem nada acusar. Três rodadas, porque o bug apareceria na
    segunda."""
    raiz = _plataforma(tmp_path)
    for _ in range(3):
        assert _rodar(raiz).returncode == 0
    for arquivo, chaves in CHAVES_ESCRITAS.items():
        texto = (raiz / "env" / arquivo).read_text(encoding="utf-8")
        for chave in chaves:
            n = len(re.findall(rf"^{re.escape(chave)}=", texto, re.MULTILINE))
            assert n == 1, f"{chave} aparece {n} vezes em {arquivo}"


def test_o_par_dessincronizado_a_mao_e_curado_pelo_provedor(tmp_path):
    """Quem manda é o provedor; o consumidor é realinhado a ele. É o caminho da
    rotação (`armadilhas/090`): troca-se o valor na lista de aceitos e roda-se a
    linha de novo. A direção importa: alinhar pelo consumidor deixaria uma
    célula qualquer mudar o que o provedor aceita."""
    raiz = _plataforma(tmp_path)
    assert _rodar(raiz).returncode == 0
    alvo = raiz / "env" / "catalogo.env"
    novo = "x" * 40
    alvo.write_text(
        re.sub(
            r"^TOKENS_ACEITOS_CURSOS=.*$",
            f"TOKENS_ACEITOS_CURSOS={novo}",
            alvo.read_text(encoding="utf-8"),
            flags=re.MULTILINE,
        ),
        encoding="utf-8",
    )
    assert _rodar(raiz).returncode == 0
    assert _valor(raiz, "cursos.env", "TOKEN_CATALOGO") == novo


# ------------------------------------------------------- os caminhos de recusa


def test_pasta_errada_para_sem_escrever(tmp_path):
    r = _executar([_bash(), str(SCRIPT)], str(tmp_path / "nao-existe"))
    assert r.returncode != 0
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert not (tmp_path / "nao-existe").exists(), "criou a pasta que não achou"


@pytest.mark.parametrize("faltando", sorted(SEMENTES))
def test_env_faltando_para_e_nao_toca_em_nenhum_dos_outros(tmp_path, faltando):
    raiz = _plataforma(tmp_path, faltando=faltando)
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0, r.stdout
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"
    assert not (raiz / "env" / faltando).exists(), f"criou {faltando}, que não é dele"


def test_sem_o_env_da_sala_de_aula_a_recusa_ensina_a_linha_do_banco(tmp_path):
    """`env/cursos.env` nasce com o banco (`provisionar-cursos.sh`), que reescreve
    o env inteiro e PARA ao achar chave que não sabe gerar. Um env criado aqui
    antes dele o travaria para sempre; a recusa tem de dizer o que colar."""
    raiz = _plataforma(tmp_path, faltando="cursos.env")
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "provisionar-cursos.sh" in r.stdout, r.stdout
    assert "bash /tmp/c.sh meshcraft.top" in r.stdout, r.stdout


def test_dois_pares_com_o_mesmo_token_param_sem_escrever(tmp_path):
    """Token é por par. Um valor compartilhado faria a rotação de um derrubar o
    outro, e o script confere isso ANTES de tocar em qualquer arquivo."""
    raiz = _plataforma(tmp_path)
    repetido = "r" * 40
    for arquivo in ("identidade.env", "alunos.env"):
        alvo = raiz / "env" / arquivo
        alvo.write_text(
            re.sub(
                r"^TOKENS_ACEITOS_CURSOS=.*$",
                f"TOKENS_ACEITOS_CURSOS={repetido}",
                alvo.read_text(encoding="utf-8"),
                flags=re.MULTILINE,
            ),
            encoding="utf-8",
        )
    antes = _fotografia(raiz)
    r = _rodar(raiz)
    assert r.returncode != 0
    assert "MESMO token" in r.stdout, r.stdout
    assert _fotografia(raiz) == antes, "parou, mas já tinha escrito em alguém"


def test_carregado_com_source_recusa_em_vez_de_derrubar_a_sessao():
    """O modo de falha de 24/08: `exit` num shell carregado com `.` derruba a
    sessão interativa do mantenedor. Aconteceu, três vezes."""
    r = _executar(
        [_bash(), "-c", f'. "{SCRIPT}"; echo SOBREVIVI'], "/tmp/nao-existe-mesmo"
    )
    assert "PAROU POR SEGURANÇA" in r.stdout
    assert "SOBREVIVI" in r.stdout, "o `return` não protegeu a sessão de quem deu source"


# ---------------------------------------------------------- a ordem que importa


def test_o_provedor_e_escrito_antes_dos_consumidores():
    """Ordem inversa tem janela com sintoma: consumidor com token que o provedor
    ainda não aceita responde 401 para gente de verdade. Medido no texto porque
    é ordem de código: as duas ordens produzem o mesmo arquivo final."""
    texto = SCRIPT.read_text(encoding="utf-8")

    def posicao(arquivo: str, chave: str) -> int:
        return texto.index(f'garantir "$ENV_{arquivo}" {chave} ')

    assert posicao("IDENTIDADE", "TOKENS_ACEITOS_CURSOS") < posicao("CURSOS", "IDENTIDADE_API_TOKEN")
    assert posicao("IDENTIDADE", "TOKENS_COMPLETOS_CURSOS") < posicao("CURSOS", "IDENTIDADE_API_TOKEN")
    assert posicao("ALUNOS", "TOKENS_ACEITOS_CURSOS") < posicao("CURSOS", "ALUNOS_API_TOKEN")
    assert posicao("CATALOGO", "TOKENS_ACEITOS_CURSOS") < posicao("CURSOS", "TOKEN_CATALOGO")
    assert posicao("CURSOS", "TOKENS_ACEITOS_ADMIN") < posicao("ADMIN", "CURSOS_API_TOKEN")
