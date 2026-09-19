"""PARIDADE DO CONTRATO DAS CHAVES DO GATEWAY entre o deploy e o rollback.

O compose da plataforma exige duas chaves no serviço `traefik`. Sem elas
exportadas, NENHUM comando `docker compose` roda: a interpolação falha, e
`docker compose config --services` devolve vazio.

O `infra/deploy-celula-na-vps.sh` cumpria esse contrato. O
`infra/reverter-celula-na-vps.sh` NÃO, e por isso todo rollback abortava com
"'<celula>' não tem serviço algum em /opt/plataforma/docker-compose.yml" — para
qualquer célula. Medido em 19/09/2026 (TAR-486) em disparos reais do workflow.
A mensagem parecia acusar a VPS de estar sem segredo; o que faltava era código,
e essa confusão custou uma noite. A prova de que as chaves existiam lá: naquele
mesmo dia houve QUATRO runs de deploy verdes, com CINCO ativações reais na VPS,
rodando o código que lê essas duas chaves daquele mesmo arquivo. (Primeiro eu
escrevi "sete deploys", contando workflows verdes em vez de runs: o número
estava errado, a conclusão continua de pé.)

POR QUE CÓPIA, E NÃO UM TRECHO COMPARTILHADO: a `appleboy/ssh-action` envia o
CONTEÚDO de UM arquivo por SSH, e /opt/plataforma não tem o repositório. Um
`source` de irmão não existiria na VPS e quebraria os dois roteiros. A cópia é
imposta pelo transporte; este guarda é a defesa contra ela divergir.

O QUE ESTE GUARDA MEDE, E NADA ALÉM: as quatro cláusulas do contrato, nos dois
roteiros. Os dois fazem coisas diferentes e devem continuar podendo: aqui não
se compara estrutura, tamanho nem texto fora do contrato.

    1. as duas chaves são LIDAS de `env/admin.env`
    2. falha FECHADA se qualquer uma estiver ausente ou vazia
    3. as duas são EXPORTADAS
    4. tudo isso ANTES do primeiro `docker compose`

E a cláusula 1 é provada RODANDO o bloco recortado do roteiro de verdade, com a
raiz apontada para um diretório de teste onde o arquivo existe em UM lugar só.
Ler o texto e ver "env/admin.env" escrito ali não prova nada: foi exatamente a
confusão entre texto escrito e leitura feita que produziu o diagnóstico falso
da VPS. Aqui, se o roteiro abrisse outro caminho, não acharia valor e pararia.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import ci  # noqa: E402

RAIZ = Path(__file__).resolve().parents[2]
CHAVES_ESPERADAS = {"ALUNOS_API_TOKEN", "TOKEN_CATALOGO"}
DEPLOY = RAIZ / "infra" / "deploy-celula-na-vps.sh"
ROLLBACK = RAIZ / "infra" / "reverter-celula-na-vps.sh"

# `for CHAVE_DO_GATEWAY in A B; do` — a forma que o deploy usa e que o rollback
# copiou. Um bloco por chave também é aceito: o que vale é a chave ser lida do
# arquivo de ambiente, não a forma do laço.
LACO = re.compile(r"^\s*for\s+(\w+)\s+in\s+([A-Z0-9_ ]+);\s*do\s*$", re.MULTILINE)
LEITURA_LITERAL = re.compile(r'grep\s+-m1\s+"\^([A-Z][A-Z0-9_]*)=')
COMPOSE = re.compile(r"\bdocker\s+compose\b")


@dataclass
class Contrato:
    """O que um roteiro promete sobre as chaves do gateway."""

    nome: str
    lidas: set[str]
    exportadas: set[str]
    falha_fechada: bool
    linha_da_leitura: int | None
    linha_do_primeiro_compose: int | None


def _ler(caminho: Path) -> Contrato:
    texto = caminho.read_text(encoding="utf-8")
    linhas = texto.splitlines()

    lidas: set[str] = set()
    exportadas: set[str] = set()
    linha_da_leitura: int | None = None

    for achado in LACO.finditer(texto):
        variavel, chaves = achado.group(1), achado.group(2).split()
        inicio = texto[: achado.start()].count("\n")
        corpo = "\n".join(linhas[inicio : inicio + 30])
        if 'grep -m1 "^$' + variavel + "=" not in corpo:
            continue
        lidas.update(chaves)
        if linha_da_leitura is None or inicio < linha_da_leitura:
            linha_da_leitura = inicio
        if 'export "$' + variavel + "=" in corpo:
            exportadas.update(chaves)

    for numero, linha in enumerate(linhas):
        literal = LEITURA_LITERAL.search(linha)
        if literal:
            lidas.add(literal.group(1))
            if linha_da_leitura is None or numero < linha_da_leitura:
                linha_da_leitura = numero
        exportacao = re.search(r'export\s+"?([A-Z][A-Z0-9_]*)=', linha)
        if exportacao:
            exportadas.add(exportacao.group(1))

    # Falha fechada: dentro das linhas da leitura, um teste de vazio que sai
    # com erro. `exit 0` ali seria "segue sem a chave", que é o oposto.
    inicio_janela = linha_da_leitura or 0
    janela = "\n".join(linhas[inicio_janela : inicio_janela + 30])
    falha_fechada = bool(re.search(r'-z\s+"\$\w+"', janela)) and "exit 1" in janela

    primeiro_compose = next(
        (
            n
            for n, linha in enumerate(linhas)
            if COMPOSE.search(linha) and not linha.lstrip().startswith("#")
        ),
        None,
    )
    return Contrato(
        nome=caminho.name,
        lidas=lidas,
        exportadas=exportadas,
        falha_fechada=falha_fechada,
        linha_da_leitura=linha_da_leitura,
        linha_do_primeiro_compose=primeiro_compose,
    )


def _contratos() -> tuple[Contrato, Contrato]:
    return _ler(DEPLOY), _ler(ROLLBACK)


def _bloco_do_contrato(caminho: Path) -> str:
    """O trecho executável do contrato, RECORTADO do roteiro de verdade.

    Recorta, não reescreve: um teste que rodasse uma cópia sua do bloco provaria
    a cópia, e não o roteiro que vai para a VPS.
    """
    linhas = caminho.read_text(encoding="utf-8").splitlines()
    inicio = next(i for i, l in enumerate(linhas) if l.startswith("ENV_DO_ADMIN="))
    fim = next(i for i, l in enumerate(linhas[inicio:], inicio) if l.strip() == "done")
    cabeca = 'RAIZ="${PLATAFORMA_DIR:-/opt/plataforma}"'
    return "\n".join([cabeca, *linhas[inicio : fim + 1]])


def _rodar_o_contrato(caminho: Path, raiz: Path) -> subprocess.CompletedProcess:
    """Roda o bloco de verdade, com a raiz apontada para um diretório de teste."""
    provas = "\n".join(
        'printf "%s=%s\\n" ' + chave + ' "$' + chave + '"'
        for chave in sorted(CHAVES_ESPERADAS)
    )
    return subprocess.run(
        [ci._bash(), "-c", _bloco_do_contrato(caminho) + "\n" + provas],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
        env={**os.environ, "PLATAFORMA_DIR": str(raiz).replace("\\", "/")},
    )


# ---------------------------------------------------------------------------
# Cláusula 1 e a paridade: as MESMAS chaves, lidas do arquivo REALMENTE aberto
# ---------------------------------------------------------------------------


def test_os_dois_roteiros_leem_exatamente_as_mesmas_chaves() -> None:
    """A cláusula que impede a PRÓXIMA divergência.

    Presença não basta: se alguém acrescentar uma terceira chave ao deploy e
    esquecer do rollback, os conjuntos deixam de bater e este teste reprova.
    Foi assim que este defeito nasceu.
    """
    # guarda: infra/reverter-celula-na-vps.sh:60
    deploy, rollback = _contratos()
    assert deploy.lidas, "o deploy deixou de ler chaves do gateway; o guarda cegou"
    assert deploy.lidas == rollback.lidas, (
        "os dois roteiros divergiram sobre as chaves do gateway.\n"
        f"  {deploy.nome}:   {sorted(deploy.lidas)}\n"
        f"  {rollback.nome}: {sorted(rollback.lidas)}\n\n"
        "Sem uma chave exportada, a interpolação do compose falha e NENHUM "
        "comando roda na VPS. Copie o contrato inteiro para os dois."
    )


@pytest.mark.parametrize("caminho", [DEPLOY, ROLLBACK], ids=lambda p: p.name)
def test_o_roteiro_abre_mesmo_o_arquivo_de_ambiente_do_admin(caminho, tmp_path) -> None:
    """Prova o caminho ABERTO, não o caminho escrito no texto.

    O arquivo existe em UM lugar só. Se o roteiro abrisse qualquer outro
    caminho, não acharia valor nenhum e pararia.
    """
    (tmp_path / "env").mkdir()
    (tmp_path / "env" / "admin.env").write_text(
        "ALUNOS_API_TOKEN=valor-de-mentira-alunos\nTOKEN_CATALOGO=valor-de-mentira-catalogo\n",
        encoding="utf-8",
    )
    saida = _rodar_o_contrato(caminho, tmp_path)
    assert saida.returncode == 0, saida.stdout + saida.stderr
    for chave in sorted(CHAVES_ESPERADAS):
        assert chave + "=valor-de-mentira-" in saida.stdout, (
            f"{caminho.name} não exportou {chave} lida do arquivo aberto.\n" + saida.stdout
        )


@pytest.mark.parametrize("caminho", [DEPLOY, ROLLBACK], ids=lambda p: p.name)
def test_o_roteiro_para_quando_o_arquivo_aberto_nao_tem_a_chave(caminho, tmp_path) -> None:
    """Cláusula 2, provada rodando: ausente e vazia param igual."""
    (tmp_path / "env").mkdir()
    (tmp_path / "env" / "admin.env").write_text(
        "ALUNOS_API_TOKEN=\nTOKEN_CATALOGO=valor-de-mentira-catalogo\n", encoding="utf-8"
    )
    saida = _rodar_o_contrato(caminho, tmp_path)
    assert saida.returncode != 0, (
        f"{caminho.name} seguiu adiante com a chave vazia: " + saida.stdout
    )
    assert "PAROU POR SEGURAN" in saida.stdout, saida.stdout
    assert "valor-de-mentira-catalogo" not in saida.stdout, (
        "o roteiro imprimiu o valor de uma chave na tela"
    )


# ---------------------------------------------------------------------------
# Cláusula 2: falha fechada, também na forma
# ---------------------------------------------------------------------------


def test_os_dois_param_quando_a_chave_esta_ausente_ou_vazia() -> None:
    """Seguir sem a chave deixaria o compose falhar depois, com outra cara."""
    # guarda: infra/reverter-celula-na-vps.sh:69
    for contrato in _contratos():
        assert contrato.falha_fechada, (
            f"{contrato.nome} não para quando a chave está ausente ou vazia."
        )


# ---------------------------------------------------------------------------
# Cláusula 3: toda chave lida é exportada
# ---------------------------------------------------------------------------


def test_toda_chave_lida_e_exportada_nos_dois_roteiros() -> None:
    """Ler sem exportar é o defeito com roupa nova: o compose não a enxerga."""
    # guarda: infra/reverter-celula-na-vps.sh:71
    for contrato in _contratos():
        faltando = contrato.lidas - contrato.exportadas
        assert not faltando, (
            f"{contrato.nome} lê {sorted(faltando)} e NÃO exporta. O compose só "
            "enxerga o que está no ambiente; ler para o nada não interpola nada."
        )


# ---------------------------------------------------------------------------
# Cláusula 4: antes do primeiro compose
# ---------------------------------------------------------------------------


def test_a_leitura_vem_antes_do_primeiro_comando_compose() -> None:
    """Depois do primeiro compose já é tarde: aquele comando já falhou."""
    # guarda: infra/reverter-celula-na-vps.sh:60
    for contrato in _contratos():
        assert contrato.linha_da_leitura is not None, (
            f"{contrato.nome} não lê chave nenhuma do gateway."
        )
        assert contrato.linha_do_primeiro_compose is not None, (
            f"{contrato.nome} não chama docker compose; o guarda aponta para o "
            "arquivo errado."
        )
        assert contrato.linha_da_leitura < contrato.linha_do_primeiro_compose, (
            f"{contrato.nome} chama docker compose na linha "
            f"{contrato.linha_do_primeiro_compose + 1}, ANTES da leitura das "
            f"chaves na linha {contrato.linha_da_leitura + 1}. Esse comando roda "
            "sem o ambiente que ele exige."
        )


# ---------------------------------------------------------------------------
# O cuidado que o deploy já tinha, e que a cópia precisa manter
# ---------------------------------------------------------------------------


def test_nenhum_dos_dois_imprime_o_valor_da_chave() -> None:
    """Log de run é lido por gente; segredo nele é incidente."""
    for caminho in (DEPLOY, ROLLBACK):
        for numero, linha in enumerate(
            caminho.read_text(encoding="utf-8").splitlines(), 1
        ):
            if "echo" in linha and "$VALOR_DO_GATEWAY" in linha:
                raise AssertionError(
                    f"{caminho.name}:{numero} imprime o valor da chave na tela."
                )
