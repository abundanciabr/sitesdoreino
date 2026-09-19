"""PARIDADE DO CONTRATO DAS CHAVES DO GATEWAY entre o deploy e o rollback.

O compose da plataforma exige duas chaves no serviço `traefik`. Sem elas
exportadas, NENHUM comando `docker compose` roda: a interpolação falha, e
`docker compose config --services` devolve vazio.

O `infra/deploy-celula-na-vps.sh` cumpria esse contrato. O
`infra/reverter-celula-na-vps.sh` NÃO, e por isso todo rollback abortava com
"'<celula>' não tem serviço algum em /opt/plataforma/docker-compose.yml" — para
qualquer célula. Medido em 19/09/2026 (TAR-486) em quatro disparos reais do
workflow. A mensagem parecia acusar a VPS de estar sem segredo; o que faltava
era código, e essa confusão custou uma noite. A prova de que as chaves existiam
lá: sete deploys reais terminaram VERDES naquele mesmo dia, rodando o código
que lê essas duas chaves daquele mesmo arquivo.

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

As três mutações que precisam ficar vermelhas, uma a uma: remover uma chave,
deixar de exportar uma chave lida, e chamar Compose antes da leitura.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[2]
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

    # Chaves lidas: as do laço cuja variável é usada num `grep` do arquivo de
    # ambiente, mais as lidas literalmente por nome.
    for achado in LACO.finditer(texto):
        variavel, chaves = achado.group(1), achado.group(2).split()
        inicio = texto[: achado.start()].count("\n")
        corpo = "\n".join(linhas[inicio : inicio + 30])
        if f'grep -m1 "^${variavel}=' not in corpo:
            continue
        lidas.update(chaves)
        if linha_da_leitura is None or inicio < linha_da_leitura:
            linha_da_leitura = inicio
        if f'export "${variavel}=' in corpo:
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
    janela = "\n".join(linhas[(linha_da_leitura or 0) : (linha_da_leitura or 0) + 30])
    falha_fechada = bool(re.search(r"-z\s+\"\$\w+\"", janela)) and "exit 1" in janela

    primeiro_compose = next(
        (n for n, linha in enumerate(linhas) if COMPOSE.search(linha) and not linha.lstrip().startswith("#")),
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


# ---------------------------------------------------------------------------
# Cláusula 1 e a paridade: as MESMAS chaves, lidas do mesmo arquivo
# ---------------------------------------------------------------------------


def test_os_dois_roteiros_leem_exatamente_as_mesmas_chaves() -> None:
    """A cláusula que impede a PRÓXIMA divergência.

    Presença não basta: se alguém acrescentar uma terceira chave ao deploy e
    esquecer do rollback, os conjuntos deixam de bater e este teste reprova.
    Foi assim que este defeito nasceu.
    """
    deploy, rollback = _contratos()
    assert deploy.lidas, "o deploy deixou de ler chaves do gateway; o guarda cegou"
    assert deploy.lidas == rollback.lidas, (
        "os dois roteiros divergiram sobre as chaves do gateway.\n"
        f"  {deploy.nome}:   {sorted(deploy.lidas)}\n"
        f"  {rollback.nome}: {sorted(rollback.lidas)}\n\n"
        "Sem uma chave exportada, a interpolação do compose falha e NENHUM "
        "comando roda na VPS. Copie o contrato inteiro para os dois."
    )


def test_as_chaves_saem_do_arquivo_de_ambiente_do_admin() -> None:
    for caminho in (DEPLOY, ROLLBACK):
        texto = caminho.read_text(encoding="utf-8")
        assert "env/admin.env" in texto, (
            f"{caminho.name} não lê as chaves de env/admin.env."
        )


# ---------------------------------------------------------------------------
# Cláusula 2: falha fechada
# ---------------------------------------------------------------------------


def test_os_dois_param_quando_a_chave_esta_ausente_ou_vazia() -> None:
    """Seguir sem a chave deixaria o compose falhar depois, com outra cara."""
    for contrato in _contratos():
        assert contrato.falha_fechada, (
            f"{contrato.nome} não para quando a chave está ausente ou vazia."
        )


# ---------------------------------------------------------------------------
# Cláusula 3: toda chave lida é exportada
# ---------------------------------------------------------------------------


def test_toda_chave_lida_e_exportada_nos_dois_roteiros() -> None:
    """Ler sem exportar é o defeito com roupa nova: o compose não a enxerga."""
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
        for numero, linha in enumerate(caminho.read_text(encoding="utf-8").splitlines(), 1):
            if "echo" in linha and "$VALOR_DO_GATEWAY" in linha:
                raise AssertionError(
                    f"{caminho.name}:{numero} imprime o valor da chave na tela."
                )
