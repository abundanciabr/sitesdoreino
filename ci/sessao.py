"""BOOTSTRAP DE SESSÃO — o RITOS.md §1 inteiro em UM comando.

    make sessao CELULA=quiz TAREFA=fuso-horario TAR=178
    ==  python ci/sessao.py --celula quiz --tarefa fuso-horario --tar 178

    make sessao CELULA=ci TAREFA=custo-por-chamada SEM_CONTAINER=1
    ==  python ci/sessao.py --celula ci --tarefa custo-por-chamada --sem-container

Separação semântica com os irmãos, e é ela que decide o que este arquivo pode
fazer:

    doctor  ->  "o ambiente consegue executar o trabalho?"   (READ-ONLY)
    ci      ->  "a mudança respeita as invariantes?"          (READ-ONLY)
    sessao  ->  "prepare o ambiente para o trabalho começar"  (ESCREVE)

O `ci/doctor.py` continua sendo o único diagnóstico, e continua não consertando
nada. Este script é o **único** lugar do repositório que cria worktree, venv e
container — e ele nunca é o comportamento padrão de outro alvo: ninguém sobe um
Postgres por acidente rodando `make doctor`.

O que ele faz, nesta ordem, e de forma IDEMPOTENTE (rodar duas vezes não
duplica nada — o que já existe é reusado, e reusar não é falhar):

     1. confere o repositório e a célula (ou a ÁREA, com --sem-container)
     2. git fetch origin
     3. worktree ../wt-<celula>-<tarefa> na branch agent/<celula>/<tarefa>
     4. balcão: `ci/fila.py pegar TAR-NNN`, quando --tar vem — e é o PRIMEIRO
        gesto depois de a pasta existir (`armadilhas/357`), rodado pelo
        `fila.py` DA BANCADA para o comprovante não nascer órfão no clone
        principal (`armadilhas/192`)
     5. `ci/indice_de_armadilhas.py` DENTRO da bancada: o índice é gerado, não
        viaja no Git, e num checkout novo simplesmente não existe
     6. venv FORA do worktree (`armadilhas/008`: dentro é risco de commit)
     7. pip install -r services/<celula>/requirements.txt
     8. Postgres (e Redis, quando a célula usa) em Docker, com nome e porta
        DERIVADOS da célula — nunca a 55432 fixa da partida rápida, que em lote
        faria cinco despachos colidirem no mesmo container
     9. .env de sessão, fora do worktree, com caminhos absolutos no formato
        desta máquina (`armadilhas/006`: `/tmp` aqui não é `/tmp`)
    10. python ci/doctor.py
    11. baseline: `make ci` da célula, com a saída INTEIRA num log em disco
    e então imprime a Declaração de Abertura do RITOS §1 já preenchida, e
    fecha com `BANCADA PRONTA: <caminho absoluto>` para o robô copiar.

Cada passo diz `PASS` quando termina, e o número `[n/N]` conta os passos DESTA
execução: pular passo calado seria o robô achar que perdeu algo no caminho.

**`--sem-container` é o caminho de quem não tem célula.** Trabalho em `ci/`,
`painel/`, `armadilhas/`, `documentos/` ou `fila/` não tem `services/<x>` para
testar nem Postgres para subir, e esperar por um container que ninguém vai usar
era justamente o atrito que fazia o robô abrir a bancada à mão. Sem ambiente o
rito para no passo 5, e a Declaração diz `Baseline: não medido` em vez de
afirmar um verde que ninguém mediu.

**Fail-closed, e alto.** Qualquer passo que não dê certo PARA o script, diz qual
passo foi, mostra o comando exato para reproduzir e **não imprime a Declaração**.
Não existe `|| true` aqui: terminar com "pronto!" depois de um `pip install` que
falhou é o falso-verde que este repositório inteiro existe para eliminar.

Exit codes, na mesma semântica do resto da CI:

    0  a sessão está pronta — a Declaração foi impressa
    1  o baseline REPROVOU (main vermelha, workspace sujo) — pare e reporte
    2  não foi possível preparar (ferramenta ausente, Docker desligado, rede…)

`python`, nunca `python3`: o shim de `python3` desta máquina resolve um problema
local e não pode virar requisito arquitetural (mesma regra do Makefile da raiz).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _nucleo import (  # noqa: E402
    ErroDeInstrumentacao,
    configurar_saida,
    raiz_declarada,
    raiz_do_repo,
    recortar,
)

# ---------------------------------------------------------------------------
# Constantes declaradas — cada uma com o motivo do número
# ---------------------------------------------------------------------------

IMAGEM_POSTGRES = "postgres:17"
IMAGEM_REDIS = "redis:7"

# A faixa de portas do bootstrap. Ela é escolhida por EXCLUSÃO das que este
# repositório já usa: 55432 (partida rápida do ARMADILHAS §2), 55433–55441
# (containers de sessões antigas e os docker-compose.dev.yml de sugestoes e
# identidade) e 55450–55459 (reservada aos testes deste próprio script).
PORTA_POSTGRES_BASE = 55460
PORTA_POSTGRES_TETO = 55479
PORTA_REDIS_BASE = 16460
PORTA_REDIS_TETO = 16479

USUARIO_DO_BANCO = "dev"
SENHA_DO_BANCO = "dev"

# Os mesmos valores que .github/workflows/ci-celula.yml declara. São FALSOS de
# propósito e a igualdade é o ponto: `make ci` local que roda com um ambiente
# diferente do CI é um verde que não prova nada (`armadilhas/037`).
SEGREDO_DE_DESENVOLVIMENTO = "ci-apenas-nunca-em-producao"
TOKEN_FALSO_DO_MERCADO_PAGO = (
    "TEST-ci-0000000000000000-000000-fake000000000000000000000000000-000000000"
)

# Ferramentas que o `ci/doctor.py` exige de TODA sessão e que nem toda célula
# pina no requirements.txt (quiz e mensageria não pinam PyYAML). O venv da
# sessão não é a imagem de produção da célula: é célula + portões da raiz. Sem
# isto, `make sessao CELULA=quiz` morreria no passo 8 por um buraco que não é
# da tarefa de ninguém.
FERRAMENTAS_DE_PORTAO = ("PyYAML==6.0.2",)

# Um único padrão que satisfaz os TRÊS consumidores do nome ao mesmo tempo:
# nome de branch do git, nome de container do Docker e nome de diretório. Vale
# recusar antes de agir — meio worktree criado é pior que nenhum.
PADRAO_DE_NOME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LIMITE_DE_NOME = 40

# Os exit codes que `correr_de_verdade` inventa quando o comando NÃO chegou a
# rodar (ausente, timeout, erro de SO). Só eles significam "não foi possível
# medir" — qualquer outro número veio do programa e é veredito dele.
SENTINELAS_DE_INSTRUMENTACAO = frozenset({124, 126, 127})

PASSOS = (
    "conferir o repositório e a célula",
    "git fetch origin",
    "worktree da sessão",
    "balcão: pegar a tarefa da fila",
    "armadilhas/INDICE.md na bancada",
    "venv FORA do worktree",
    "dependências da célula",
    "serviços em Docker",
    ".env de sessão",
    "ci/doctor.py",
    "baseline: make ci da célula",
)

# Nome, nunca índice. `PASSOS[5]` calado vira o passo errado no dia em que
# alguém insere um passo no meio — e o erro sairia apontando para o lugar
# errado, que é pior do que não apontar.
(
    P_CONFERIR,
    P_FETCH,
    P_WORKTREE,
    P_BALCAO,
    P_INDICE,
    P_VENV,
    P_DEPS,
    P_SERVICOS,
    P_ENV,
    P_DOCTOR,
    P_BASELINE,
) = PASSOS

# Os passos que só existem quando a bancada sobe ambiente. Quem vai mexer em
# `ci/`, `painel/`, `armadilhas/`, `documentos/` ou `fila/` não tem célula para
# testar nem container para subir, e esperar 4 minutos por um Postgres que
# ninguém vai usar é o atrito que fazia o robô abrir a bancada à mão.
PASSOS_DO_AMBIENTE = (P_VENV, P_DEPS, P_SERVICOS, P_ENV, P_DOCTOR, P_BASELINE)

# `178`, `TAR-178` e `tar-178` são a mesma tarefa. O balcão só conhece a forma
# canônica, e adivinhar na hora da chamada daria `RECUSADO: tar-178 não existe`
# para quem digitou certo.
PADRAO_DA_TAREFA_DA_FILA = re.compile(r"^(?:TAR-)?([0-9]{1,4})$", re.IGNORECASE)


# ---------------------------------------------------------------------------
# O erro — carrega SEMPRE como reproduzir
# ---------------------------------------------------------------------------


class ErroDeSessao(Exception):
    """Um passo do bootstrap não deu certo.

    Carrega o passo, o comando exato de reprodução e o diagnóstico cru. Quem
    captura imprime tudo e devolve `codigo` — nunca 0, nunca a Declaração.
    """

    def __init__(
        self,
        passo: str,
        resumo: str,
        *,
        comando: str = "",
        detalhe: str = "",
        codigo: int = 2,
    ) -> None:
        super().__init__(resumo)
        self.passo = passo
        self.resumo = resumo
        self.comando = comando
        self.detalhe = detalhe
        self.codigo = codigo

    def render(self) -> str:
        linhas = [
            "",
            "=" * 72,
            f"FAIL — PAROU POR SEGURANÇA — passo: {self.passo}",
            "=" * 72,
            f"Motivo: {self.resumo}",
        ]
        if self.comando:
            linhas += ["", "Reproduza exatamente com:", f"  {self.comando}"]
        if self.detalhe:
            linhas += ["", self.detalhe.rstrip()]
        linhas += [
            "",
            "A sessão NÃO está pronta, e a Declaração de Abertura NÃO foi impressa.",
            "Corrija o passo acima e rode o MESMO comando de novo: este script é",
            "idempotente — o que já ficou pronto não é refeito.",
            "",
        ]
        return "\n".join(linhas)


# ---------------------------------------------------------------------------
# Decisão pura — tudo daqui até o Plano roda sem tocar disco, rede ou Docker
# ---------------------------------------------------------------------------


def _normalizar(caminho: Path) -> str:
    """Forma comparável de um caminho, sem exigir que ele exista."""
    return os.path.normcase(os.path.normpath(str(caminho)))


def validar_nome(valor: str, rotulo: str) -> str:
    """Aceita só o que serve para branch, container e diretório ao mesmo tempo.

    Recusar AQUI é o ponto: um nome com `/`, `..`, espaço ou maiúscula produz
    um `git worktree add` que funciona pela metade, ou um `docker run` que
    recusa depois de o worktree já existir.
    """
    valor = (valor or "").strip()
    ajuda = (
        "Regra: minúsculas, dígitos e hífen no meio (ex.: `fuso-horario`),\n"
        f"até {LIMITE_DE_NOME} caracteres.\n"
        "O mesmo texto vira nome de branch (`agent/<celula>/<tarefa>`), nome de\n"
        "diretório (`../wt-<celula>-<tarefa>`) e nome de container do Docker —\n"
        "e as três gramáticas juntas não aceitam `/`, `\\`, `..`, `:`, `~`, `^`,\n"
        "`@{`, espaço, acento nem maiúscula."
    )
    if not valor:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"{rotulo} não informado",
            detalhe=ajuda,
        )
    if len(valor) > LIMITE_DE_NOME:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"{rotulo}='{valor}' tem {len(valor)} caracteres",
            detalhe=ajuda,
        )
    if not PADRAO_DE_NOME.match(valor):
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"{rotulo}='{valor}' não é um nome utilizável",
            detalhe=ajuda,
        )
    return valor


def normalizar_tarefa_da_fila(valor: str) -> str:
    """`178`, `TAR-178` ou `tar-178` viram `TAR-178`. O resto recusa AQUI.

    Recusar antes de qualquer efeito é o ponto: um identificador torto só seria
    descoberto pelo balcão depois de a bancada já existir, e a essa altura o
    robô já teria uma pasta para remover.
    """
    achado = PADRAO_DA_TAREFA_DA_FILA.match((valor or "").strip())
    if not achado:
        raise ErroDeSessao(
            P_CONFERIR,
            f"--tar='{valor}' não é uma tarefa da fila",
            detalhe="Formas aceitas: `178`, `TAR-178` ou `tar-178`.\n"
            "O quadro de agora: python ci/fila.py listar --ao-vivo",
        )
    return f"TAR-{int(achado.group(1))}"


def celulas_declaradas(raiz: Path) -> list[str]:
    """As células do manifesto, em ordem. Não conseguir ler é ERROR, não lista vazia."""
    manifesto = raiz / "ci" / "manifesto-de-contratos.json"
    if not manifesto.is_file():
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            "manifesto de contratos não encontrado",
            detalhe=f"Esperado em:\n  {manifesto}\n\n"
            "Sem o manifesto não há lista de células — e não ter a lista NÃO é o\n"
            "mesmo que a célula pedida não existir.",
        )
    try:
        dados = json.loads(manifesto.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            "manifesto de contratos ilegível",
            detalhe=f"{manifesto}\n{exc}",
        ) from exc
    celulas = sorted(dados.get("celulas", {}))
    if not celulas:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            "manifesto de contratos não declara nenhuma célula",
            detalhe=str(manifesto),
        )
    return celulas


def validar_celula(
    celula: str, celulas: Sequence[str], raiz: Path | None = None
) -> str:
    """Célula tem de estar declarada NO MANIFESTO e existir em disco."""
    celula = validar_nome(celula, "CELULA")
    if celula not in celulas:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"célula '{celula}' não existe",
            detalhe="Declaradas em ci/manifesto-de-contratos.json:\n"
            + "\n".join(f"  - {c}" for c in celulas)
            + "\n\nSe você vai mexer em `ci/`, `painel/`, `armadilhas/`,\n"
            "`documentos/` ou `fila/`, não existe célula para testar: rode com\n"
            "--sem-container (ou `make sessao ... SEM_CONTAINER=1`) e a bancada\n"
            "nasce sem venv, sem Docker e sem baseline.",
        )
    if raiz is not None and not (raiz / "services" / celula).is_dir():
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"célula '{celula}' está no manifesto mas não em disco",
            detalhe=f"Esperada em:\n  {raiz / 'services' / celula}",
        )
    return celula


def derivar_porta(celula: str, celulas: Sequence[str], base: int, teto: int) -> int:
    """Porta DERIVADA da célula: índice na lista declarada, somado à base.

    Índice em vez de hash porque índice não colide: duas células diferentes
    nunca recebem a mesma porta, que é justamente o que quebra num lote de
    cinco despachos paralelos usando a 55432 fixa da partida rápida.
    """
    if celula not in celulas:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"célula '{celula}' fora da lista declarada",
            detalhe="\n".join(f"  - {c}" for c in celulas),
        )
    porta = base + sorted(celulas).index(celula)
    if porta > teto:
        raise ErroDeSessao(
            "conferir o repositório e a célula",
            f"a faixa de portas {base}–{teto} acabou ({len(celulas)} células)",
            detalhe="Alargue PORTA_*_BASE/TETO em ci/sessao.py — mas confira antes\n"
            "quais portas já estão tomadas por outros caminhos do repositório.",
        )
    return porta


def celula_usa_redis(destino: Path) -> bool:
    """A célula fala com Redis? A resposta vem do CÓDIGO, não de uma tabela.

    Tabela de "quem usa Redis" envelhece em silêncio no dia em que uma célula
    ganha outbox. Aqui a fonte é o mesmo texto que o Django lê.
    """
    for arquivo in sorted(destino.rglob("*.py")):
        try:
            texto = arquivo.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "REDIS_STREAMS_URL" in texto or "HUEY_REDIS_URL" in texto:
            return True
    return False


@dataclass(frozen=True)
class Plano:
    """Tudo o que a sessão vai criar, decidido ANTES de qualquer efeito."""

    celula: str
    tarefa: str
    frase: str
    sobe_ambiente: bool
    tarefa_da_fila: str
    raiz: Path
    worktree: Path
    branch: str
    scratch: Path
    venv: Path
    arquivo_env: Path
    postgres: str
    porta_postgres: int
    redis: str
    porta_redis: int

    @property
    def banco(self) -> str:
        return f"{self.celula}_db"

    @property
    def log_do_baseline(self) -> Path:
        """A saída INTEIRA do baseline, fora do worktree, ao lado do .env."""
        return self.scratch / f"baseline-{self.celula}.log"

    @property
    def quem_no_balcao(self) -> str:
        """Quem está pegando a tarefa, no vocabulário do RITOS §5 peça 1."""
        return f"despacho-{self.celula}-{self.tarefa}"

    @property
    def usa_redis(self) -> bool:
        return bool(self.redis)

    @property
    def celula_no_worktree(self) -> Path:
        return self.worktree / "services" / self.celula

    @property
    def requisitos(self) -> Path:
        return self.celula_no_worktree / "requirements.txt"

    @property
    def bin_do_venv(self) -> Path:
        return self.venv / ("Scripts" if os.name == "nt" else "bin")

    @property
    def python_do_venv(self) -> Path:
        return self.bin_do_venv / ("python.exe" if os.name == "nt" else "python")


def base_de_scratch_padrao() -> Path:
    """O scratch da máquina, perguntado ao Python — nunca `/tmp` escrito à mão.

    `armadilhas/006`: `/tmp` no Git Bash não é o `/tmp` que o Python enxerga.
    `tempfile.gettempdir()` devolve o caminho REAL desta máquina, absoluto e no
    formato dela.
    """
    return Path(tempfile.gettempdir()) / "sitesdoreino-sessoes"


def derivar_plano(
    celula: str,
    tarefa: str,
    *,
    raiz: Path,
    celulas: Sequence[str],
    usa_redis: bool,
    frase: str = "",
    sobe_ambiente: bool = True,
    tarefa_da_fila: str = "",
    base_de_scratch: Path | None = None,
    porta_postgres: int | None = None,
    porta_redis: int | None = None,
    prefixo: str = "sessao",
) -> Plano:
    """Deriva nomes, caminhos e portas. Puro: não toca disco, rede nem Docker."""
    # Sem ambiente, o nome não é uma célula: é a ÁREA do trabalho (`ci`,
    # `painel`, `armadilhas`). Ele continua tendo de servir de branch e de
    # diretório, mas não precisa estar no manifesto de contratos.
    celula = (
        validar_celula(celula, celulas)
        if sobe_ambiente
        else validar_nome(celula, "CELULA")
    )
    tarefa = validar_nome(tarefa, "TAREFA")
    prefixo = validar_nome(prefixo, "PREFIXO")
    usa_redis = usa_redis and sobe_ambiente
    base = (base_de_scratch or base_de_scratch_padrao()).absolute()
    scratch = base / f"{celula}-{tarefa}"
    if not sobe_ambiente:
        return Plano(
            celula=celula,
            tarefa=tarefa,
            frase=frase.strip(),
            sobe_ambiente=False,
            tarefa_da_fila=tarefa_da_fila,
            raiz=raiz,
            worktree=(raiz.parent / f"wt-{celula}-{tarefa}").absolute(),
            branch=f"agent/{celula}/{tarefa}",
            scratch=scratch,
            venv=scratch / "venv",
            arquivo_env=scratch / ".env",
            postgres="",
            porta_postgres=0,
            redis="",
            porta_redis=0,
        )
    return Plano(
        celula=celula,
        tarefa=tarefa,
        frase=frase.strip(),
        sobe_ambiente=True,
        tarefa_da_fila=tarefa_da_fila,
        raiz=raiz,
        worktree=(raiz.parent / f"wt-{celula}-{tarefa}").absolute(),
        branch=f"agent/{celula}/{tarefa}",
        scratch=scratch,
        venv=scratch / "venv",
        arquivo_env=scratch / ".env",
        postgres=f"{prefixo}-{celula}-pg",
        porta_postgres=(
            porta_postgres
            if porta_postgres is not None
            else derivar_porta(
                celula, celulas, PORTA_POSTGRES_BASE, PORTA_POSTGRES_TETO
            )
        ),
        redis=f"{prefixo}-{celula}-redis" if usa_redis else "",
        porta_redis=(
            (
                porta_redis
                if porta_redis is not None
                else derivar_porta(celula, celulas, PORTA_REDIS_BASE, PORTA_REDIS_TETO)
            )
            if usa_redis
            else 0
        ),
    )


def passos_do_plano(plano: Plano) -> tuple[str, ...]:
    """Os passos que ESTA sessão vai rodar, na ordem.

    O contador `[n/N]` sai daqui. Numerar sobre a lista inteira e pular passos
    calado é a forma barata de o robô achar que perdeu um passo pelo caminho.
    """
    passos = [P_CONFERIR, P_FETCH, P_WORKTREE]
    if plano.tarefa_da_fila:
        passos.append(P_BALCAO)
    passos.append(P_INDICE)
    if plano.sobe_ambiente:
        passos.extend(PASSOS_DO_AMBIENTE)
    return tuple(passos)


def bancada_pronta(plano: Plano) -> str:
    """As duas últimas linhas da execução, feitas para o robô copiar."""
    return "\n".join(
        [
            f"RAMO: {plano.branch}",
            f"BANCADA PRONTA: {plano.worktree}",
        ]
    )


def variaveis_de_sessao(
    plano: Plano, *, porta_postgres: int, porta_redis: int = 0
) -> dict[str, str]:
    """As variáveis que todo `make ci` local precisa.

    As portas chegam por parâmetro, e não do plano, de propósito: quando um
    container é REUSADO, a porta que vale é a que ele publica de verdade — lida
    do Docker —, não a que teríamos escolhido. Prova de fora, não de dentro.
    """
    variaveis = {
        "PYTHONUTF8": "1",
        "DJANGO_SECRET_KEY": SEGREDO_DE_DESENVOLVIMENTO,
        "DATABASE_URL": (
            f"postgres://{USUARIO_DO_BANCO}:{SENHA_DO_BANCO}"
            f"@localhost:{porta_postgres}/{plano.banco}"
        ),
    }
    if plano.usa_redis:
        variaveis["REDIS_STREAMS_URL"] = f"redis://localhost:{porta_redis}/0"
        variaveis["HUEY_REDIS_URL"] = f"redis://localhost:{porta_redis}/1"
    variaveis["MP_ACCESS_TOKEN"] = TOKEN_FALSO_DO_MERCADO_PAGO
    variaveis["MP_WEBHOOK_SECRET"] = f"{SEGREDO_DE_DESENVOLVIMENTO}-webhook-secret"
    variaveis["SESSAO_SCRATCH"] = str(plano.scratch)
    variaveis["SESSAO_VENV"] = str(plano.venv)
    variaveis["SESSAO_WORKTREE"] = str(plano.worktree)
    return variaveis


def renderizar_env(plano: Plano, variaveis: dict[str, str]) -> str:
    """O texto do `.env` de sessão, com TODO valor entre aspas simples.

    As aspas não são estilo: em `sh`, `VAR=C:\\Users\\x` sem aspas come as
    contrabarras e o caminho do Windows chega mutilado do outro lado. Valor com
    aspas simples ou quebra de linha é recusado em vez de ser escapado — não há
    caso legítimo aqui, e escapar seria adivinhar.
    """
    linhas = [
        "# .env DE SESSÃO — gerado por `python ci/sessao.py`. NÃO comite este arquivo.",
        f"# Célula: {plano.celula}   Tarefa: {plano.tarefa}",
        f"# Ele mora FORA do worktree ({plano.scratch}) porque nada gerado por",
        "# sessão pode virar commit acidental (armadilhas/008).",
        "#",
        "# Git Bash:    set -a; . '<este arquivo>'; set +a",
        "# PowerShell:  Get-Content '<este arquivo>' | ForEach-Object {",
        "#                if ($_ -match \"^([A-Z_]+)='(.*)'$\") {",
        '#                  Set-Item "env:$($Matches[1])" $Matches[2] } }',
        "#",
        "# O `make sessao` já rodou o doctor e o baseline COM estas variáveis: você",
        "# só precisa carregá-las se for rodar algum comando à mão depois.",
    ]
    for chave, valor in variaveis.items():
        if "'" in valor or "\n" in valor:
            raise ErroDeSessao(
                ".env de sessão",
                f"valor de {chave} tem aspas simples ou quebra de linha",
                detalhe=f"Valor:\n  {valor!r}\n\n"
                "O .env cita todo valor com aspas simples; escapar seria adivinhar.",
            )
        linhas.append(f"{chave}='{valor}'")
    return "\n".join(linhas) + "\n"


def resumo_do_baseline(saida: str) -> str:
    """`6 passed` extraído da saída do `make ci` — ou `verde`, sem inventar."""
    achados = re.findall(r"\b\d+ passed\b", saida)
    return achados[-1] if achados else "verde"


def declaracao(plano: Plano, *, resumo: str, constituicao_da_celula: str = "") -> str:
    """A Declaração de Abertura do RITOS §1, em UMA linha, pronta para colar."""
    primeira = (
        f"Li CONSTITUICAO.md e {constituicao_da_celula}."
        if constituicao_da_celula
        else "Li CONSTITUICAO.md e RITOS.md §1."
    )
    frase = plano.frase or "<uma frase: o que este despacho vai fazer>"
    # Sem ambiente não houve baseline, e afirmar um seria assinar o que não se
    # mediu. "não medido" com o motivo é honesto; "verde" seria falso-verde.
    baseline = (
        f"Baseline: `make ci` da célula {plano.celula} = {resumo}."
        if resumo
        else "Baseline: não medido (--sem-container: esta bancada não sobe ambiente)."
    )
    return (
        f"{primeira} Worktree: {plano.worktree.name}. "
        f"Branch: {plano.branch}. git status: limpo. "
        f"{baseline} "
        f"Tarefa: {frase}."
    )


def cabecalho(plano: Plano) -> str:
    """O plano inteiro em texto, antes de qualquer efeito colateral."""
    linhas = [
        "SITE DO REINO — BOOTSTRAP DE SESSÃO (RITOS.md §1)",
        "",
        f"  célula        {plano.celula}",
        f"  tarefa        {plano.tarefa}",
        f"  worktree      {plano.worktree}",
        f"  branch        {plano.branch}",
    ]
    if plano.tarefa_da_fila:
        linhas.append(f"  fila          {plano.tarefa_da_fila} (pegar no balcão)")
    if not plano.sobe_ambiente:
        linhas += [
            "  ambiente      NENHUM (--sem-container: sem venv, Docker nem baseline)",
            "",
        ]
        return "\n".join(linhas)
    linhas += [
        f"  venv          {plano.venv}   (FORA do worktree)",
        f"  .env          {plano.arquivo_env}",
        f"  postgres      {plano.postgres} em localhost:{plano.porta_postgres}",
    ]
    if plano.usa_redis:
        linhas.append(f"  redis         {plano.redis} em localhost:{plano.porta_redis}")
    else:
        linhas.append("  redis         (esta célula não lê REDIS_*: nenhum container)")
    linhas.append("")
    return "\n".join(linhas)


def moldura_da_declaracao(texto: str) -> str:
    risca = "-" * 72
    return "\n".join(
        [
            "",
            risca,
            "DECLARAÇÃO DE ABERTURA (RITOS.md §1) — primeira linha da sua primeira",
            "resposta. Troque só a frase final pela tarefa do despacho.",
            risca,
            texto,
            risca,
            "",
        ]
    )


def esta_dentro(caminho: Path, pasta: Path) -> bool:
    """`caminho` está sob `pasta`? Comparação textual: nada precisa existir."""
    alvo = _normalizar(caminho.absolute())
    raiz = _normalizar(pasta.absolute())
    return alvo == raiz or alvo.startswith(raiz + os.sep)


def worktree_ja_existe(saida_porcelain: str, alvo: Path) -> bool:
    """Lê `git worktree list --porcelain` e diz se o alvo já está registrado."""
    alvo_normal = _normalizar(alvo)
    for linha in saida_porcelain.splitlines():
        if linha.startswith("worktree "):
            if _normalizar(Path(linha[len("worktree ") :].strip())) == alvo_normal:
                return True
    return False


def estado_do_container(saida: str, nome: str) -> str:
    """Estado do container na saída de `docker ps -a --format '{Names}\\t{State}'`.

    String vazia = não existe. `docker ps` com filtro sai 0 e sem linhas quando
    nada casa — ausência aqui é informação, não falha.
    """
    for linha in saida.splitlines():
        partes = linha.strip().split("\t")
        if len(partes) >= 2 and partes[0] == nome:
            return partes[1].strip()
    return ""


def porta_publicada(saida: str) -> int:
    """Lê `docker port <nome> 5432/tcp` -> 55460. Sem parse, é ERROR."""
    for linha in saida.splitlines():
        linha = linha.strip()
        if ":" in linha:
            candidato = linha.rsplit(":", 1)[-1].strip()
            if candidato.isdigit():
                return int(candidato)
    raise ErroDeSessao(
        "serviços em Docker",
        "não consegui ler a porta publicada pelo container",
        comando="docker port <container> <porta-interna>/tcp",
        detalhe=f"Saída recebida:\n{recortar(saida, 600)}\n\n"
        "Sem saber a porta real, o DATABASE_URL do .env seria um palpite.",
    )


# ---------------------------------------------------------------------------
# Efeito colateral — tudo daqui para baixo passa por `correr`/`escrever`
# ---------------------------------------------------------------------------


@dataclass
class Saida:
    comando: list[str]
    exit_code: int
    stdout: str
    stderr: str

    @property
    def texto(self) -> str:
        pedacos = [p for p in (self.stdout, self.stderr) if p and p.strip()]
        return "\n".join(p.strip() for p in pedacos)


def correr_de_verdade(
    comando: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: int = 1800,
) -> Saida:
    """Roda um comando. Exit != 0 é INFORMAÇÃO para quem chama, nunca engolido."""
    comando = [str(c) for c in comando]
    try:
        proc = subprocess.run(
            comando,
            cwd=str(cwd) if cwd is not None else None,
            env=env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except FileNotFoundError:
        return Saida(comando, 127, "", f"{comando[0]}: não encontrado no PATH")
    except subprocess.TimeoutExpired:
        return Saida(comando, 124, "", f"{comando[0]}: timeout após {timeout}s")
    except OSError as exc:
        return Saida(comando, 126, "", f"{comando[0]}: {exc}")
    return Saida(comando, proc.returncode, proc.stdout or "", proc.stderr or "")


def escrever_de_verdade(caminho: Path, texto: str) -> None:
    caminho.parent.mkdir(parents=True, exist_ok=True)
    caminho.write_text(texto, encoding="utf-8", newline="\n")


class Sessao:
    """Executa o plano, passo a passo, parando no primeiro que não deu certo.

    `correr`, `escrever`, `existe` e `dormir` são injetáveis para que a suíte
    consiga provar o comportamento fail-closed sem criar container nenhum. Os
    padrões são os reais — nenhum atalho de teste sobra ligado em produção.
    """

    def __init__(
        self,
        plano: Plano,
        *,
        correr: Callable[..., Saida] = correr_de_verdade,
        escrever: Callable[[Path, str], None] = escrever_de_verdade,
        existe: Callable[[Path], bool] | None = None,
        localizar: Callable[[str], str | None] = shutil.which,
        dormir: Callable[[float], None] = time.sleep,
        log: Callable[[str], None] = print,
    ) -> None:
        self.plano = plano
        self._correr = correr
        self._escrever = escrever
        self._existe = existe or (lambda caminho: Path(caminho).exists())
        self._localizar = localizar
        self._dormir = dormir
        self._log = log
        self._n = 0
        self._passos = passos_do_plano(plano)
        self._variaveis: dict[str, str] = {}

    # -- utilidades ---------------------------------------------------------

    def _abrir(self, nome: str) -> str:
        self._n += 1
        self._log(f"[{self._n}/{len(self._passos)}] {nome}")
        return nome

    def _nota(self, texto: str) -> None:
        self._log(f"        {texto}")

    def _pass(self, texto: str) -> None:
        """O veredito do passo, uma vez por passo. O do FAIL é o `render()`."""
        self._log(f"        PASS  {texto}")

    def _exigir(
        self,
        passo: str,
        comando: Sequence[str],
        *,
        cwd: Path | None = None,
        env: dict[str, str] | None = None,
        timeout: int = 1800,
        dica: str = "",
        codigo: int = 2,
    ) -> Saida:
        """Roda e FALHA FECHADO. Não existe caminho em que exit != 0 siga adiante."""
        saida = self._correr(comando, cwd=cwd, env=env, timeout=timeout)
        if saida.exit_code != 0:
            detalhe = (f"{dica}\n\n" if dica else "") + recortar(saida.texto, 3000)
            raise ErroDeSessao(
                passo,
                f"o comando saiu com exit code {saida.exit_code}",
                comando=" ".join(str(c) for c in comando),
                detalhe=detalhe,
                codigo=codigo,
            )
        return saida

    def _ferramenta(self, nome: str, passo: str, para_que: str) -> str:
        caminho = self._localizar(nome)
        if caminho is None:
            raise ErroDeSessao(
                passo,
                f"`{nome}` não está no PATH",
                detalhe=para_que,
            )
        return caminho

    def _ambiente(self) -> dict[str, str]:
        env = dict(os.environ)
        env.update(self._variaveis)
        env.pop("PYTHONHOME", None)
        env["VIRTUAL_ENV"] = str(self.plano.venv)
        env["PATH"] = str(self.plano.bin_do_venv) + os.pathsep + env.get("PATH", "")
        return env

    # -- os passos ----------------------------------------------------------

    def conferir(self) -> None:
        passo = self._abrir(P_CONFERIR)
        if esta_dentro(self.plano.worktree, self.plano.raiz):
            raise ErroDeSessao(
                passo,
                "o worktree cairia DENTRO do clone principal",
                detalhe=f"worktree: {self.plano.worktree}\nraiz:     {self.plano.raiz}",
            )
        if not self.plano.sobe_ambiente:
            self._pass(
                f"área {self.plano.celula} · --sem-container: "
                "nada de services/, venv ou Docker nesta bancada"
            )
            return
        destino = self.plano.raiz / "services" / self.plano.celula
        if not self._existe(destino):
            raise ErroDeSessao(
                passo,
                f"célula '{self.plano.celula}' não existe em disco",
                detalhe=f"Esperada em:\n  {destino}",
            )
        if not self._existe(
            self.plano.raiz / "services" / self.plano.celula / "requirements.txt"
        ):
            raise ErroDeSessao(
                passo,
                f"a célula '{self.plano.celula}' não tem requirements.txt",
                detalhe=f"Esperado em:\n  {destino / 'requirements.txt'}\n\n"
                "Sem ele não há o que instalar no venv da sessão.",
            )
        if esta_dentro(self.plano.venv, self.plano.worktree):
            raise ErroDeSessao(
                passo,
                "o venv cairia DENTRO do worktree",
                detalhe="`armadilhas/008`: o .gitignore das células não lista `.venv/`,\n"
                "então venv dentro do worktree é risco de commit acidental.",
            )
        self._pass(
            f"célula {self.plano.celula} ok · worktree e venv em lugares distintos"
        )

    def buscar(self, git: str) -> None:
        passo = self._abrir(P_FETCH)
        self._exigir(
            passo,
            [git, "-C", str(self.plano.raiz), "fetch", "origin"],
            cwd=self.plano.raiz,
            timeout=600,
            dica="Sem rede, ou sem credencial do GitHub nesta máquina. O worktree\n"
            "nasceria de um `origin/main` velho — e um baseline contra main velha\n"
            "não prova nada sobre a main de agora.",
        )
        self._pass("origin/main atualizado")

    def preparar_worktree(self, git: str) -> None:
        passo = self._abrir(P_WORKTREE)
        lista = self._exigir(
            passo,
            [git, "-C", str(self.plano.raiz), "worktree", "list", "--porcelain"],
            cwd=self.plano.raiz,
            timeout=120,
        )
        if worktree_ja_existe(lista.stdout, self.plano.worktree) and self._existe(
            self.plano.worktree / ".git"
        ):
            atual = self._exigir(
                passo,
                [
                    git,
                    "-C",
                    str(self.plano.worktree),
                    "rev-parse",
                    "--abbrev-ref",
                    "HEAD",
                ],
                cwd=self.plano.raiz,
                timeout=120,
            ).stdout.strip()
            if atual and atual != self.plano.branch:
                raise ErroDeSessao(
                    passo,
                    f"o worktree existe, mas está na branch '{atual}'",
                    detalhe=f"Esperada: {self.plano.branch}\nWorktree: {self.plano.worktree}\n\n"
                    "Reusar um worktree de OUTRA tarefa misturaria dois despachos.\n"
                    "Escolha outra TAREFA, ou remova o worktree que você mesmo criou:\n"
                    f"  git -C {self.plano.raiz} worktree remove {self.plano.worktree}",
                    codigo=1,
                )
            self._pass(f"a bancada já existia na branch certa: {self.plano.worktree}")
            return

        existe_branch = (
            self._correr(
                [
                    git,
                    "-C",
                    str(self.plano.raiz),
                    "rev-parse",
                    "--verify",
                    "--quiet",
                    f"refs/heads/{self.plano.branch}",
                ],
                cwd=self.plano.raiz,
                timeout=120,
            ).exit_code
            == 0
        )
        if existe_branch:
            comando = [
                git,
                "-C",
                str(self.plano.raiz),
                "worktree",
                "add",
                str(self.plano.worktree),
                self.plano.branch,
            ]
            self._nota(f"branch {self.plano.branch} já existia — reaproveitando")
        else:
            comando = [
                git,
                "-C",
                str(self.plano.raiz),
                "worktree",
                "add",
                str(self.plano.worktree),
                "-b",
                self.plano.branch,
                "origin/main",
            ]
        self._exigir(passo, comando, cwd=self.plano.raiz, timeout=600)
        if not self._existe(self.plano.worktree / ".git"):
            raise ErroDeSessao(
                passo,
                "o `git worktree add` saiu 0 mas o worktree não apareceu",
                comando=" ".join(comando),
                detalhe=f"Esperado:\n  {self.plano.worktree / '.git'}\n\n"
                "Exit 0 sem o artefato é exatamente o falso-verde que o INV-CI01 fecha.",
            )
        self._pass(f"bancada criada em {self.plano.worktree}")

    def pegar_a_tarefa(self) -> None:
        """Reivindica a tarefa no balcão, de DENTRO da bancada.

        `armadilhas/192`: `ci/fila.py` escreve o comprovante relativo ao
        repositório em que ELE foi executado. Chamar o `fila.py` do clone
        principal faria o evento nascer órfão no espelho, com o validador da
        fila respondendo "válida" sem ele. Por isso o caminho do script é o da
        bancada, e não o `ci/fila.py` que estamos rodando.

        `armadilhas/357`: e é o PRIMEIRO passo depois de a pasta existir. A
        trava do balcão é de TAREFA, não de pasta; entre criar a bancada e
        perguntar quem ganhou existe uma janela, e o que se pode fazer é
        encurtá-la até o único byte que ela ainda custa: um diretório vazio.
        """
        passo = self._abrir(P_BALCAO)
        tid = self.plano.tarefa_da_fila
        quem = self.plano.quem_no_balcao
        comando = [
            sys.executable,
            str(self.plano.worktree / "ci" / "fila.py"),
            "pegar",
            tid,
            "--quem",
            quem,
        ]
        saida = self._correr(comando, cwd=self.plano.worktree, timeout=600)
        if saida.exit_code != 0:
            raise ErroDeSessao(
                passo,
                f"o balcão recusou {tid} — a tarefa NÃO é sua",
                comando=f'python ci/fila.py pegar {tid} --quem "{quem}"',
                detalhe=recortar(saida.texto, 2000)
                + "\n\nA fala acima é do BALCÃO, não deste script. Quase sempre é\n"
                "outro robô que pegou a tarefa primeiro, ou ela está trancada.\n"
                "NÃO escreva um byte nesta bancada: pare e reporte à maestro.\n"
                "A bancada ficou vazia e pode ser removida com:\n"
                f"  git -C {self.plano.raiz} worktree remove {self.plano.worktree}\n"
                "O quadro de agora: python ci/fila.py listar --ao-vivo",
                codigo=1,
            )
        self._pass(f"{tid} é sua · o comprovante nasceu na bancada (commite-o no PR)")

    def _exigir_bancada_limpa(self, passo: str, git: str) -> None:
        """A Declaração afirma `git status: limpo`. Isto é o que MEDE isso.

        Mora fora dos passos porque os dois caminhos precisam dela: o baseline
        a faz no fim do `make ci`, e a bancada sem ambiente a faz no fim do
        índice. Afirmar limpeza sem medir é assinar o que não se conferiu.
        """
        sujo = self._exigir(
            passo,
            [git, "-C", str(self.plano.worktree), "status", "--porcelain"],
            cwd=self.plano.raiz,
            timeout=300,
        ).stdout.strip()
        if sujo:
            raise ErroDeSessao(
                passo,
                "a bancada NÃO está limpa",
                comando=f"git -C {self.plano.worktree} status --porcelain",
                detalhe=recortar(sujo, 2000)
                + "\n\nA Declaração de Abertura afirma `git status: limpo`. Imprimi-la\n"
                "com o workspace sujo seria assinar uma coisa que não é verdade.",
                codigo=1,
            )

    def gerar_indice(self, git: str) -> None:
        """Materializa `armadilhas/INDICE.md` DENTRO da bancada.

        O índice, o GUARDAS.json, o SINAIS.json e o GATILHOS.json são gerados e
        não viajam no Git: num checkout novo eles simplesmente não existem, e a
        chave de busca da memória de campo é a primeira coisa que o rito manda
        ler. Gerá-lo no clone principal deixaria a bancada sem ele
        (`armadilhas/148`).
        """
        passo = self._abrir(P_INDICE)
        alvo = self.plano.worktree / "armadilhas" / "INDICE.md"
        self._exigir(
            passo,
            [
                sys.executable,
                str(self.plano.worktree / "ci" / "indice_de_armadilhas.py"),
            ],
            cwd=self.plano.worktree,
            timeout=600,
            dica="Sem o índice, `armadilhas/INDICE.md` não existe nesta bancada e o\n"
            "primeiro gesto do rito (ler a entrada que casa com a tarefa) não tem\n"
            "onde acontecer.",
        )
        if not self._existe(alvo):
            raise ErroDeSessao(
                passo,
                "o gerador saiu 0 mas o INDICE.md não apareceu",
                comando="python ci/indice_de_armadilhas.py",
                detalhe=f"Esperado:\n  {alvo}\n\n"
                "Exit 0 sem o artefato é exatamente o falso-verde que o INV-CI01 fecha.",
            )
        if not self.plano.sobe_ambiente:
            # Sem baseline, este é o ÚLTIMO passo do rito: a limpeza que a
            # Declaração afirma se mede aqui, ou não se mede em lugar nenhum.
            self._exigir_bancada_limpa(passo, git)
            self._pass(f"{alvo} materializado · git status: limpo")
            return
        self._pass(f"{alvo} materializado (leia a entrada que casa com a sua tarefa)")

    def preparar_venv(self) -> None:
        passo = self._abrir(P_VENV)
        if self._existe(self.plano.python_do_venv):
            self._pass("venv já existia — sigo")
            return
        comando = [sys.executable, "-m", "venv", str(self.plano.venv)]
        self._exigir(passo, comando, cwd=self.plano.raiz, timeout=600)
        if not self._existe(self.plano.python_do_venv):
            raise ErroDeSessao(
                passo,
                "o `python -m venv` saiu 0 mas o interpretador não apareceu",
                comando=" ".join(comando),
                detalhe=f"Esperado:\n  {self.plano.python_do_venv}",
            )
        self._pass(f"venv criado em {self.plano.venv}")

    def instalar(self) -> None:
        passo = self._abrir(P_DEPS)
        comando = [
            str(self.plano.python_do_venv),
            "-m",
            "pip",
            "install",
            "--disable-pip-version-check",
            "-r",
            str(self.plano.requisitos),
            *FERRAMENTAS_DE_PORTAO,
        ]
        self._exigir(
            passo,
            comando,
            cwd=self.plano.worktree,
            timeout=3600,
            dica="Sem rede, ou uma versão pinada que o índice não serve mais.\n"
            "Este passo é idempotente: rode o mesmo comando de novo depois de\n"
            "resolver, que o pip só instala o que faltar.",
        )
        self._pass(
            f"requirements.txt de {self.plano.celula} + "
            f"{', '.join(FERRAMENTAS_DE_PORTAO)} instalados"
        )

    def _garantir_container(
        self,
        passo: str,
        docker: str,
        *,
        nome: str,
        imagem: str,
        porta: int,
        porta_interna: int,
        ambiente: dict[str, str],
        sonda: list[str],
        esperado: str,
    ) -> int:
        estado = estado_do_container(
            self._exigir(
                passo,
                [
                    docker,
                    "ps",
                    "-a",
                    "--filter",
                    f"name=^{nome}$",
                    "--format",
                    "{{.Names}}\t{{.State}}",
                ],
                cwd=self.plano.raiz,
                timeout=120,
            ).stdout,
            nome,
        )
        if not estado:
            comando = [docker, "run", "-d", "--name", nome]
            for chave, valor in ambiente.items():
                comando += ["-e", f"{chave}={valor}"]
            comando += ["-p", f"{porta}:{porta_interna}", imagem]
            self._exigir(
                passo,
                comando,
                cwd=self.plano.raiz,
                timeout=900,
                dica=f"Se a porta {porta} já estiver ocupada por outra coisa, escolha\n"
                f"outra com --porta-postgres/--porta-redis. NÃO remova container que\n"
                "não foi você quem criou: pode ser de outra sessão do lote.",
            )
            self._nota(f"{nome} criado ({imagem}) em localhost:{porta}")
        elif estado != "running":
            self._exigir(
                passo, [docker, "start", nome], cwd=self.plano.raiz, timeout=300
            )
            self._nota(f"{nome} existia parado ({estado}) — reiniciado")
        else:
            self._nota(f"{nome} já estava de pé — sigo")

        efetiva = porta_publicada(
            self._exigir(
                passo,
                [docker, "port", nome, f"{porta_interna}/tcp"],
                cwd=self.plano.raiz,
                timeout=120,
            ).stdout
        )
        if efetiva != porta:
            self._nota(
                f"ATENÇÃO: {nome} publica a porta {efetiva}, não a {porta} derivada. "
                "O .env usa a REAL."
            )
        self._esperar(passo, nome, [docker, "exec", nome, *sonda], esperado=esperado)
        return efetiva

    def _esperar(
        self,
        passo: str,
        nome: str,
        comando: list[str],
        *,
        esperado: str = "",
        tentativas: int = 60,
        intervalo: float = 1.0,
    ) -> None:
        ultima = Saida(list(comando), -1, "", "(a sonda nunca rodou)")
        for _ in range(tentativas):
            ultima = self._correr(comando, cwd=self.plano.raiz, timeout=60)
            if ultima.exit_code == 0 and (not esperado or esperado in ultima.stdout):
                return
            self._dormir(intervalo)
        raise ErroDeSessao(
            passo,
            f"{nome} não ficou pronto em {tentativas}s",
            comando=" ".join(comando),
            detalhe=recortar(ultima.texto, 1000)
            + "\n\nO container subiu mas não atende. Rodar o baseline agora daria um\n"
            "vermelho de infraestrutura disfarçado de vermelho de código.",
        )

    def preparar_servicos(self) -> tuple[int, int]:
        passo = self._abrir(P_SERVICOS)
        docker = self._ferramenta(
            "docker",
            passo,
            "O `make ci` da célula precisa de um Postgres de verdade (pytest-django\n"
            "cria o banco de teste). Instale o Docker Desktop, ou suba um Postgres\n"
            f"em localhost:{self.plano.porta_postgres} por outro caminho e rode com\n"
            "--porta-postgres apontando para ele.",
        )
        motor = self._correr(
            [docker, "info", "--format", "{{.ServerVersion}}"],
            cwd=self.plano.raiz,
            timeout=120,
        )
        if motor.exit_code != 0 or not motor.stdout.strip():
            raise ErroDeSessao(
                passo,
                "o Docker está instalado mas o motor não responde",
                comando=f"{docker} info",
                detalhe="Quase sempre é o Docker Desktop desligado (ou ainda subindo:\n"
                "`armadilhas/004` — ele leva 1 a 2 minutos frio).\n\n"
                "ABRA O DOCKER DESKTOP, espere a baleia parar de piscar e rode o MESMO\n"
                "comando de novo. Este script é idempotente: worktree e venv que já\n"
                "existem não são refeitos.\n\n" + recortar(motor.texto, 800),
            )
        self._nota(f"Docker Engine {motor.stdout.strip()}")

        porta_pg = self._garantir_container(
            passo,
            docker,
            nome=self.plano.postgres,
            imagem=IMAGEM_POSTGRES,
            porta=self.plano.porta_postgres,
            porta_interna=5432,
            ambiente={
                "POSTGRES_USER": USUARIO_DO_BANCO,
                "POSTGRES_PASSWORD": SENHA_DO_BANCO,
                "POSTGRES_DB": self.plano.banco,
            },
            sonda=["pg_isready", "-U", USUARIO_DO_BANCO, "-d", self.plano.banco],
            esperado="accepting connections",
        )
        porta_redis = 0
        if self.plano.usa_redis:
            porta_redis = self._garantir_container(
                passo,
                docker,
                nome=self.plano.redis,
                imagem=IMAGEM_REDIS,
                porta=self.plano.porta_redis,
                porta_interna=6379,
                ambiente={},
                sonda=["redis-cli", "ping"],
                esperado="PONG",
            )
        self._pass(
            f"{self.plano.postgres} atende em localhost:{porta_pg}"
            + (
                f" · {self.plano.redis} em localhost:{porta_redis}"
                if porta_redis
                else ""
            )
        )
        return porta_pg, porta_redis

    def escrever_env(self, porta_pg: int, porta_redis: int) -> None:
        passo = self._abrir(P_ENV)
        self._variaveis = variaveis_de_sessao(
            self.plano, porta_postgres=porta_pg, porta_redis=porta_redis
        )
        texto = renderizar_env(self.plano, self._variaveis)
        try:
            self._escrever(self.plano.arquivo_env, texto)
        except OSError as exc:
            raise ErroDeSessao(
                passo,
                "não consegui escrever o .env de sessão",
                detalhe=f"{self.plano.arquivo_env}\n{exc}",
            ) from exc
        self._pass(f"{len(self._variaveis)} variáveis em {self.plano.arquivo_env}")

    def rodar_doctor(self) -> None:
        passo = self._abrir(P_DOCTOR)
        env = self._ambiente()
        # `armadilhas/014`: portão que roda com o Python ERRADO fica verde e não
        # prova nada. A pergunta que interessa não é "existe um python no venv?",
        # é "que python um processo filho acha no PATH que acabei de montar?".
        sonda = self._exigir(
            passo,
            [
                str(self.plano.python_do_venv),
                "-c",
                "import shutil;print(shutil.which('python') or '')",
            ],
            cwd=self.plano.worktree,
            env=env,
            timeout=300,
        )
        achado = sonda.stdout.strip()
        if not achado or not esta_dentro(Path(achado), self.plano.bin_do_venv):
            raise ErroDeSessao(
                passo,
                "o `python` do PATH da sessão NÃO é o do venv",
                detalhe=f"`which python` respondeu:\n  {achado or '(nada)'}\n"
                f"Esperado dentro de:\n  {self.plano.bin_do_venv}\n\n"
                "`armadilhas/014`: um portão que passa com o interpretador errado é\n"
                "um verde que não mediu o que você acha que mediu.",
            )
        self._nota(f"python da sessão: {achado}")
        self._exigir(
            passo,
            [str(self.plano.python_do_venv), "ci/doctor.py"],
            cwd=self.plano.worktree,
            env=env,
            timeout=900,
            dica="O diagnóstico acima é do `ci/doctor.py`, que é READ-ONLY: ele diz o\n"
            "que falta, e de propósito não conserta.",
        )
        self._pass("doctor READY")

    def rodar_baseline(self, git: str) -> str:
        passo = self._abrir(P_BASELINE)
        make = self._ferramenta(
            "make",
            passo,
            "O `make ci` de cada célula encadeia lint/type/test/contrato-check e\n"
            "ainda não foi portado para Python (ci/ci.py delega para ele). Sem GNU\n"
            "Make não há baseline de célula — e não medir não é medir verde.",
        )
        saida = self._correr(
            [make, "-C", str(self.plano.celula_no_worktree), "ci"],
            cwd=self.plano.worktree,
            env=self._ambiente(),
            timeout=3600,
        )
        # O log INTEIRO vai para o disco ANTES do veredito, para existir tanto
        # no verde quanto no vermelho: o recorte de 4000 caracteres da mensagem
        # de erro serve para ler na tela, não para investigar.
        try:
            self._escrever(self.plano.log_do_baseline, saida.texto)
            onde_o_log = str(self.plano.log_do_baseline)
        except OSError as exc:
            onde_o_log = f"(não consegui gravar o log: {exc})"
        if saida.exit_code in SENTINELAS_DE_INSTRUMENTACAO:
            raise ErroDeSessao(
                passo,
                f"o baseline NÃO chegou a rodar (exit {saida.exit_code})",
                comando=f"make -C {self.plano.celula_no_worktree} ci",
                detalhe=recortar(saida.texto, 4000)
                + f"\n\nLog completo: {onde_o_log}"
                + "\n\nEste resultado não é um FAIL: nada foi provado sobre o código.",
            )
        if saida.exit_code != 0:
            # O GNU Make devolve 2 quando uma receita reprova (`black --check`
            # sai 1 e o make traduz para 2). Tratar o 2 como "não consegui
            # medir" mandaria quem lê investigar o lugar errado — o que reprovou
            # foi a célula, não o instrumento. Só as sentinelas do próprio
            # `correr_de_verdade` (127/126/124) significam instrumentação.
            raise ErroDeSessao(
                passo,
                f"o baseline REPROVOU (exit {saida.exit_code}) — a main está "
                "vermelha para esta célula",
                comando=f"make -C {self.plano.celula_no_worktree} ci",
                detalhe=recortar(saida.texto, 4000)
                + f"\n\nLog completo: {onde_o_log}"
                + "\n\nRITOS.md §1: consertar main quebrada NÃO é escopo de sessão de\n"
                "feature. Pare e reporte ao mantenedor.",
                codigo=1,
            )
        resumo = resumo_do_baseline(saida.texto)
        self._nota(f"make ci verde ({resumo}) · log completo: {onde_o_log}")

        self._exigir_bancada_limpa(passo, git)
        self._pass(f"make ci = {resumo} · git status: limpo · log: {onde_o_log}")
        return resumo

    # -- orquestração -------------------------------------------------------

    def rodar(self) -> str:
        git = self._ferramenta(
            "git",
            P_CONFERIR,
            "Todo o Rito de Abertura é git: fetch, worktree, branch, status.",
        )
        self.conferir()
        self.buscar(git)
        self.preparar_worktree(git)
        if self.plano.tarefa_da_fila:
            self.pegar_a_tarefa()
        self.gerar_indice(git)
        if not self.plano.sobe_ambiente:
            return declaracao(self.plano, resumo="")
        self.preparar_venv()
        self.instalar()
        porta_pg, porta_redis = self.preparar_servicos()
        self.escrever_env(porta_pg, porta_redis)
        self.rodar_doctor()
        resumo = self.rodar_baseline(git)
        constituicao = f"constituicoes/AGENTS.{self.plano.celula}.md"
        if not self._existe(self.plano.worktree / constituicao):
            constituicao = ""
        return declaracao(
            self.plano, resumo=resumo, constituicao_da_celula=constituicao
        )


# ---------------------------------------------------------------------------


def construir_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepara uma sessão de agente inteira (RITOS.md §1) em um comando."
    )
    parser.add_argument("--celula", required=True, help="nome da célula em services/")
    parser.add_argument(
        "--tarefa", required=True, help="slug da tarefa (minúsculas e hífen)"
    )
    parser.add_argument(
        "--frase", default="", help="a frase da Declaração, se já souber"
    )
    parser.add_argument(
        "--tar",
        default="",
        metavar="TAR-NNN",
        help="a tarefa da fila a reivindicar no balcão (aceita 178 ou TAR-178)",
    )
    parser.add_argument(
        "--sem-container",
        action="store_true",
        help="bancada sem venv, Docker nem baseline — para quem só toca ci/, "
        "painel/, armadilhas/, documentos/ ou fila/",
    )
    parser.add_argument(
        "--raiz", default="", help="raiz do clone principal (padrão: descoberta)"
    )
    parser.add_argument(
        "--scratch", default="", help="onde criar venv e .env (padrão: temp da máquina)"
    )
    parser.add_argument(
        "--porta-postgres", type=int, default=None, help="sobrescreve a porta derivada"
    )
    parser.add_argument(
        "--porta-redis", type=int, default=None, help="sobrescreve a porta derivada"
    )
    parser.add_argument(
        "--prefixo",
        default="sessao",
        help="prefixo dos nomes de container (padrão: sessao)",
    )
    parser.add_argument(
        "--conferir",
        action="store_true",
        help="só mostra o plano — não cria worktree, venv nem container",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    args = construir_parser().parse_args(argv)
    try:
        raiz = raiz_declarada(Path(args.raiz)) if args.raiz else raiz_do_repo()
    except ErroDeInstrumentacao as erro:
        print(f"\nPAROU POR SEGURANÇA: {erro.resumo}\n\n{erro.detalhe}")
        return 2
    try:
        celulas = celulas_declaradas(raiz)
        tarefa_da_fila = normalizar_tarefa_da_fila(args.tar) if args.tar.strip() else ""
        if args.sem_container:
            celula = validar_nome(args.celula, "CELULA")
            usa_redis = False
        else:
            celula = validar_celula(args.celula, celulas, raiz)
            usa_redis = celula_usa_redis(raiz / "services" / celula)
        plano = derivar_plano(
            celula,
            args.tarefa,
            raiz=raiz,
            celulas=celulas,
            usa_redis=usa_redis,
            frase=args.frase,
            sobe_ambiente=not args.sem_container,
            tarefa_da_fila=tarefa_da_fila,
            base_de_scratch=Path(args.scratch) if args.scratch else None,
            porta_postgres=args.porta_postgres,
            porta_redis=args.porta_redis,
            prefixo=args.prefixo,
        )
    except ErroDeSessao as erro:
        print(erro.render())
        return erro.codigo

    print(cabecalho(plano))
    if args.conferir:
        print("--conferir: nada foi criado. Tire a flag para executar o plano acima.")
        return 0

    # O ARAUTO — Onda 1 do PLANO-MESTRE-ROBOS-SEM-COLISAO.md, contra a Classe 8
    # (mapa velho). Vem ANTES de qualquer trabalho e é fail-closed: sem saber
    # quem está mexendo em quê agora, o que pousou nas últimas 24h e se alguma
    # LEI mudou, a sessão decide sobre um mundo que pode não existir mais — foi
    # assim que este projeto entregou, em 28/08/2026, uma premissa falsa a cinco
    # consultorias externas (`armadilhas/148`).
    #
    # Mora AQUI, e não dentro de `Sessao.rodar()`, de propósito: `rodar()` é
    # bootstrap de ambiente LOCAL, provado sem rede por injeção de dependências
    # (`correr`, `existe`, `localizar`). Enfiar uma leitura de rede lá dentro
    # furava essa costura e deixava 22 guardas do próprio bootstrap vermelhos —
    # a suíte reclamou, e ela estava certa.
    try:
        from boletim import coletar, montar

        print(montar(coletar(raiz)))
    except ErroDeInstrumentacao as erro:
        print(
            ErroDeSessao(
                "boletim: o que o mundo é agora",
                f"não consegui ler o estado real do projeto: {erro.resumo}",
                comando="python ci/boletim.py",
                detalhe=(
                    (erro.detalhe + "\n\n" if erro.detalhe else "")
                    + "A sessão PAROU de propósito, ANTES de criar qualquer coisa.\n"
                    "Boletim que não sai não é 'então está tudo bem': é não saber.\n"
                    "Quase sempre é o `gh` sem credencial nesta máquina, ou sem rede."
                ),
            ).render()
        )
        return 2

    try:
        texto = Sessao(plano).rodar()
    except ErroDeSessao as erro:
        print(erro.render())
        return erro.codigo
    print(moldura_da_declaracao(texto))
    if plano.sobe_ambiente:
        print(f"O .env da sessão ficou em {plano.arquivo_env} (fora do worktree).")
        print(f"A suíte da célula rodou em {plano.celula_no_worktree}.")
    print(bancada_pronta(plano))
    return 0


def _blindar(rotulo: str, funcao: Callable[..., int]) -> Callable[..., int]:
    """Exceção não prevista vira exit 2 — nunca um 0 acidental. [INV-CI01]"""

    def blindada(*args: object, **kwargs: object) -> int:
        try:
            return funcao(*args, **kwargs)
        except SystemExit:
            raise
        except BaseException:  # noqa: BLE001 - a fronteira do processo é aqui
            import traceback

            print("")
            print(f"ERROR {rotulo}: exceção não tratada dentro do próprio bootstrap.")
            print(traceback.format_exc())
            print(
                "A sessão NÃO foi preparada e a Declaração NÃO foi impressa. "
                "Parte do trabalho pode ter sido feita: rode de novo (é idempotente)."
            )
            return 2

    return blindada


if __name__ == "__main__":
    raise SystemExit(_blindar("sessao", main)())
