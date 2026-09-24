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
nada. Este script cria a bancada persistente de trabalho, venv e container.
A validação do fechamento pode criar worktrees efêmeros isolados. A preparação
nunca é o comportamento padrão de outro alvo: ninguém sobe um Postgres por
acidente rodando `make doctor`.

O que ele faz, nesta ordem, e de forma IDEMPOTENTE (rodar duas vezes não
duplica nada — o que já existe é reusado, e reusar não é falhar):

     1. confere o repositório e a célula (ou a ÁREA, com --sem-container)
     2. git fetch origin
     3. worktree ../wt-<celula>-<tarefa> na branch agent/<celula>/<tarefa>
     4. balcão: `ci/fila.py pegar TAR-NNN`, quando --tar vem — e é o PRIMEIRO
        gesto depois de a pasta existir (`armadilhas/357`), chamado no mesmo
        processo e apontado para a BANCADA para o comprovante não nascer órfão
        no clone principal (`armadilhas/192`)
     5. abre e confere um PR em rascunho no primeiro minuto, antes do código,
        para anunciar a intenção e impedir trabalho duplicado invisível
     6. `ci/indice_de_armadilhas.py` DENTRO da bancada: o índice é gerado, não
        viaja no Git, e num checkout novo simplesmente não existe
     7. venv FORA do worktree (`armadilhas/008`: dentro é risco de commit)
     8. dependências por hash e Python, com uv quando disponível e trava local
     9. Postgres compartilhado com banco por tarefa; Redis separado por tarefa
        e porta livre escolhida pelo Docker
    10. .env de sessão, fora do worktree, com caminhos absolutos no formato
        desta máquina (`armadilhas/006`: `/tmp` aqui não é `/tmp`)
    11. python ci/doctor.py
    12. baseline da main isolada: `make ci` da célula, com log completo e cache
        por revisão e ambiente; as mudanças da tarefa têm validação própria
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
import io
import json
import hashlib
import platform
import secrets
from contextlib import contextmanager, redirect_stdout
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path, PureWindowsPath
from typing import Callable, Sequence

sys.path.insert(0, str(Path(__file__).resolve().parent))
if __name__ == "__main__":
    sys.modules.setdefault("sessao", sys.modules[__name__])

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

# O código desta sessão é versionado, mas estas peças vivem na máquina. Elas
# são conferidas antes do primeiro efeito para que uma sessão não crie uma
# bancada que já sabe que não conseguirá usar.
FERRAMENTAS_LOCAIS = {
    "git": "cria worktrees, atualiza origin/main e mede a limpeza da bancada",
    "gh": "lê o boletim e abre o PR draft exigido pelo rito",
}
FERRAMENTAS_LOCAIS_COM_AMBIENTE = {
    "docker": "sobe e sonda os serviços da sessão",
    "make": "roda o baseline da célula",
}
GANCHOS_VERSIONADOS = ("pre-commit", "pre-push")

# Um único padrão que satisfaz os TRÊS consumidores do nome ao mesmo tempo:
# nome de branch do git, nome de container do Docker e nome de diretório. Vale
# recusar antes de agir — meio worktree criado é pior que nenhum.
PADRAO_DE_NOME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
LIMITE_DE_NOME = 40

# Os exit codes que `correr_de_verdade` inventa quando o comando NÃO chegou a
# rodar (ausente, timeout, erro de SO). Só eles significam "não foi possível
# medir" — qualquer outro número veio do programa e é veredito dele.
SENTINELAS_DE_INSTRUMENTACAO = frozenset({124, 126, 127})
INTERVALO_CONFERENCIA_POSSE_SEGUNDOS = 30.0
TIMEOUT_EXECUTOR_SEGUNDOS = 3600

PASSOS = (
    "conferir o repositório e a célula",
    "git fetch origin",
    "worktree da sessão",
    "balcão: pegar a tarefa da fila",
    "PR em rascunho como anúncio",
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
    P_ANUNCIO,
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
    senha_banco: str = SENHA_DO_BANCO

    @property
    def banco(self) -> str:
        identidade = f"{self.celula}:{self.tarefa}:{self.raiz.resolve()}"
        sufixo = hashlib.sha256(identidade.encode()).hexdigest()[:16]
        return f"{self.celula[:24]}_{sufixo}"

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
    def requisitos_ci(self) -> Path:
        return self.worktree / "requirements-ci.txt"

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
            venv=Path.home() / ".sitesdoreino" / "venvs" / celula,
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
        venv=Path.home() / ".sitesdoreino" / "venvs" / celula,
        arquivo_env=scratch / ".env",
        postgres="sitesdoreino-postgres-shared",
        porta_postgres=porta_postgres if porta_postgres is not None else 15432,
        redis=f"{prefixo}-{celula}-{tarefa}-redis" if usa_redis else "",
        porta_redis=porta_redis if usa_redis and porta_redis is not None else 0,
    )


def passos_do_plano(plano: Plano) -> tuple[str, ...]:
    """Os passos que ESTA sessão vai rodar, na ordem.

    O contador `[n/N]` sai daqui. Numerar sobre a lista inteira e pular passos
    calado é a forma barata de o robô achar que perdeu um passo pelo caminho.
    """
    passos = [P_CONFERIR, P_FETCH, P_WORKTREE]
    if plano.tarefa_da_fila:
        passos.append(P_BALCAO)
    passos.append(P_ANUNCIO)
    passos.append(P_INDICE)
    passos.extend((P_VENV, P_DEPS, P_ENV))
    if plano.sobe_ambiente:
        passos.extend((P_SERVICOS, P_DOCTOR, P_BASELINE))
    return tuple(passos)


def bancada_pronta(plano: Plano) -> str:
    """As duas últimas linhas da execução, feitas para o robô copiar."""
    return "\n".join(
        [
            f"RAMO: {plano.branch}",
            f"BANCADA PRONTA: {plano.worktree}",
        ]
    )


def python_base_atual() -> tuple[str, str]:
    executavel = getattr(sys, "base_executable", "") or getattr(sys, "_base_executable", "") or sys.executable
    return str(executavel), sys.version


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
    }
    if plano.sobe_ambiente:
        variaveis["DATABASE_URL"] = (
            f"postgres://{plano.banco}:{plano.senha_banco}"
            f"@localhost:{porta_postgres}/{plano.banco}"
        )
        if plano.usa_redis:
            variaveis["REDIS_STREAMS_URL"] = f"redis://localhost:{porta_redis}/0"
            variaveis["HUEY_REDIS_URL"] = f"redis://localhost:{porta_redis}/1"
    variaveis["MP_ACCESS_TOKEN"] = TOKEN_FALSO_DO_MERCADO_PAGO
    variaveis["MP_WEBHOOK_SECRET"] = f"{SEGREDO_DE_DESENVOLVIMENTO}-webhook-secret"
    variaveis["SESSAO_SCRATCH"] = str(plano.scratch)
    variaveis["SESSAO_VENV"] = str(plano.venv)
    variaveis["SESSAO_WORKTREE"] = str(plano.worktree)
    python_executavel, python_versao = python_base_atual()
    variaveis["SESSAO_PYTHON_BASE_EXECUTABLE"] = python_executavel
    variaveis["SESSAO_PYTHON_BASE_VERSION"] = python_versao
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


def declaracao(plano: Plano, *, resumo: str, constituicao_da_celula: str = "", estado_git: str = "limpo", metodo_baseline: str = "`make ci`") -> str:
    """A Declaração de Abertura do RITOS §1, em UMA linha, pronta para colar."""
    primeira = (
        f"Leituras exigidas: CONSTITUICAO.md e {constituicao_da_celula}."
        if constituicao_da_celula
        else "Leituras exigidas: CONSTITUICAO.md e RITOS.md §1."
    )
    frase = plano.frase or "não informada; complete o brief antes de editar"
    # Sem ambiente não houve baseline, e afirmar um seria assinar o que não se
    # mediu. "não medido" com o motivo é honesto; "verde" seria falso-verde.
    baseline = (
        f"Baseline da BASE origin/main: {metodo_baseline} da célula {plano.celula} = {resumo}; a tarefa exige validação própria."
        if resumo
        else "Baseline: não medido (--sem-container: esta bancada não sobe ambiente)."
    )
    return (
        f"{primeira} Worktree: {plano.worktree.name}. "
        f"Branch: {plano.branch}. git status: {estado_git}. "
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
            "  ambiente      Python da sessão (--sem-container: sem Docker nem baseline)",
            f"  venv          {plano.venv}   (FORA do worktree)",
            f"  .env          {plano.arquivo_env} (FORA do worktree)",
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


@contextmanager
def trava_de_ambiente(caminho: Path, *, passo: str = P_VENV, esperar: bool = True):
    """O SO libera a trava também se o processo morrer, sem apagar lock alheio."""
    caminho.parent.mkdir(parents=True, exist_ok=True)
    with caminho.open("a+b") as arquivo:
        if arquivo.tell() == 0:
            arquivo.write(b"0")
            arquivo.flush()
        limite = time.monotonic() + 7200
        while True:
            try:
                arquivo.seek(0)
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(arquivo.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(arquivo.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except OSError as erro:
                if not esperar:
                    raise ErroDeSessao(
                        passo,
                        "bancada já tem execução em andamento",
                        detalhe=f"Outra execução segura a trava {caminho}. Trabalho preservado; nenhum filho novo executou.",
                    ) from erro
                if time.monotonic() >= limite:
                    raise ErroDeSessao(passo, "ambiente em preparação por outra sessão",
                                       detalhe=f"Aguarde e repita a abertura. Trava: {caminho}") from erro
                time.sleep(0.1)
        try:
            yield
        finally:
            arquivo.seek(0)
            if os.name == "nt":
                msvcrt.locking(arquivo.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(arquivo.fileno(), fcntl.LOCK_UN)


def _gitdir_da_bancada(bancada: Path) -> Path | None:
    """Localiza o gitdir sem executar Git nem tocar na árvore de trabalho."""
    dotgit = Path(bancada).resolve() / ".git"
    if dotgit.is_dir():
        return dotgit
    if not dotgit.is_file():
        return None
    try:
        linha = dotgit.read_text(encoding="utf-8").strip()
        prefixo = "gitdir:"
        if not linha.lower().startswith(prefixo):
            return None
        alvo = linha[len(prefixo):].strip()
        return (dotgit.parent / alvo).resolve() if not Path(alvo).is_absolute() else Path(alvo).resolve()
    except (OSError, UnicodeError):
        return None


def identidade_duravel_da_bancada(bancada: Path) -> str:
    """Identidade estável do checkout, distinta do processo que o usa."""
    caminho = str(Path(bancada).resolve())
    if platform.system() == "Windows":
        caminho = os.path.normcase(caminho)
    base = f"caminho:{caminho}"
    return hashlib.sha256(base.encode("utf-8")).hexdigest()


def caminho_da_trava_da_bancada(bancada: Path) -> Path:
    """Arquivo externo cuja trava é do SO e não um prazo escrito em disco."""
    return (
        Path.home()
        / ".sitesdoreino"
        / "sessoes"
        / "locks"
        / f"bancada-{identidade_duravel_da_bancada(bancada)[:32]}.lock"
    )


def arquivo_de_estado_inicial(bancada: Path) -> Path:
    """Metadado externo e mínimo da árvore herdada, sem conteúdo de arquivos."""
    gitdir = _gitdir_da_bancada(bancada)
    if gitdir:
        return gitdir / "codex-estado-inicial.json"
    return (
        Path.home()
        / ".sitesdoreino"
        / "sessoes"
        / "estado"
        / f"{identidade_duravel_da_bancada(bancada)}.json"
    )


_TRAVAS_DA_BANCADA_NO_PROCESSO: dict[str, int] = {}


@contextmanager
def trava_da_bancada(bancada: Path, *, passo: str = P_WORKTREE, esperar: bool = True):
    """Exclusividade ativa da bancada; arquivo antigo nunca autoriza a entrada."""
    identidade = identidade_duravel_da_bancada(bancada)
    if _TRAVAS_DA_BANCADA_NO_PROCESSO.get(identidade, 0):
        _TRAVAS_DA_BANCADA_NO_PROCESSO[identidade] += 1
        try:
            yield {
                "schema_version": 1,
                "identidade": identidade,
                "bancada": str(Path(bancada).resolve()),
                "processo": "reentrante",
                "pid": os.getpid(),
                "iniciada_em": datetime.now(timezone.utc).isoformat(),
            }
        finally:
            restante = _TRAVAS_DA_BANCADA_NO_PROCESSO.get(identidade, 1) - 1
            if restante:
                _TRAVAS_DA_BANCADA_NO_PROCESSO[identidade] = restante
            else:
                _TRAVAS_DA_BANCADA_NO_PROCESSO.pop(identidade, None)
        return
    caminho = caminho_da_trava_da_bancada(bancada)
    ativo = caminho.with_suffix(".json")
    token = uuid.uuid4().hex
    with trava_de_ambiente(caminho, passo=passo, esperar=esperar):
        ativo.parent.mkdir(parents=True, exist_ok=True)
        estado = {
            "schema_version": 1,
            "identidade": identidade_duravel_da_bancada(bancada),
            "bancada": str(Path(bancada).resolve()),
            "processo": token,
            "pid": os.getpid(),
            "iniciada_em": datetime.now(timezone.utc).isoformat(),
        }
        temporario = ativo.with_suffix(f".{token}.tmp")
        temporario.write_text(json.dumps(estado, ensure_ascii=False) + "\n", encoding="utf-8")
        temporario.replace(ativo)
        _TRAVAS_DA_BANCADA_NO_PROCESSO[identidade] = 1
        try:
            yield estado
        finally:
            restante = _TRAVAS_DA_BANCADA_NO_PROCESSO.get(identidade, 1) - 1
            if restante:
                _TRAVAS_DA_BANCADA_NO_PROCESSO[identidade] = restante
            else:
                _TRAVAS_DA_BANCADA_NO_PROCESSO.pop(identidade, None)
            try:
                atual = json.loads(ativo.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                atual = {}
            if atual.get("processo") == token:
                ativo.unlink(missing_ok=True)


def _resumo_do_status(status: str) -> dict[str, int | str]:
    entradas = [parte for parte in status.split("\0") if parte]
    staged = unstaged = untracked = 0
    indice = 0
    while indice < len(entradas):
        entrada = entradas[indice]
        codigo = entrada[:2]
        if codigo == "??":
            untracked += 1
        else:
            staged += int(len(codigo) > 0 and codigo[0] not in (" ", "?") )
            unstaged += int(len(codigo) > 1 and codigo[1] not in (" ", "?") )
        if codigo[:1] in ("R", "C") or codigo[1:2] in ("R", "C"):
            indice += 2
        else:
            indice += 1
    return {
        "staged": staged,
        "unstaged": unstaged,
        "untracked": untracked,
        "total": len(entradas),
        "status_sha256": hashlib.sha256(status.encode("utf-8")).hexdigest(),
    }


def metadados_da_bancada(plano: Plano) -> dict[str, object]:
    """Contrato mínimo para outro executor retomar sem adivinhar o ambiente."""
    return {
        "schema_version": 1,
        "celula": plano.celula,
        "tarefa": plano.tarefa,
        "frase": plano.frase,
        "sobe_ambiente": plano.sobe_ambiente,
        "tarefa_da_fila": plano.tarefa_da_fila,
        "raiz": str(plano.raiz.resolve()),
        "worktree": str(plano.worktree.resolve()),
        "branch": plano.branch,
        "scratch": str(plano.scratch.resolve()),
        "arquivo_env": str(plano.arquivo_env.resolve()),
        "venv": str(plano.venv.resolve()),
        "postgres": plano.postgres,
        "porta_postgres": plano.porta_postgres,
        "redis": plano.redis,
        "porta_redis": plano.porta_redis,
        "quem_no_balcao": plano.quem_no_balcao,
        "python_base": {
            "executable": python_base_atual()[0],
            "version": python_base_atual()[1],
            "prefix": sys.prefix,
            "platform": platform.platform(),
        },
    }


def registrar_estado_inicial(
    plano: Plano,
    git: str,
    *,
    correr: Callable[..., Saida] = correr_de_verdade,
) -> Path:
    """Registra uma vez o estado herdado, fora do repositório e sem segredos."""
    caminho = arquivo_de_estado_inicial(plano.worktree)
    identidade = identidade_duravel_da_bancada(plano.worktree)
    if caminho.exists():
        try:
            existente = json.loads(caminho.read_text(encoding="utf-8"))
        except (OSError, ValueError) as erro:
            raise ErroDeSessao(
                P_WORKTREE,
                "o registro inicial da bancada está ilegível",
                detalhe=f"Preserve a bancada e corrija {caminho} antes de retomar.",
            ) from erro
        if existente.get("identidade") != identidade:
            raise ErroDeSessao(
                P_WORKTREE,
                "o registro inicial pertence a outra bancada",
                detalhe=f"Preserve os arquivos e confira {caminho} antes de retomar.",
            )
        return caminho
    status = correr(
        [git, "-C", str(plano.worktree), "status", "--porcelain=v1", "-z"],
        cwd=plano.raiz,
        timeout=300,
    )
    if status.exit_code != 0:
        raise ErroDeSessao(
            P_WORKTREE,
            "não consegui registrar o estado inicial da bancada",
            comando="git status --porcelain=v1 -z",
            detalhe=recortar(status.texto, 2000),
        )
    head = correr(
        [git, "-C", str(plano.worktree), "rev-parse", "HEAD"], cwd=plano.raiz, timeout=300
    )
    branch = correr(
        [git, "-C", str(plano.worktree), "symbolic-ref", "--short", "HEAD"],
        cwd=plano.raiz,
        timeout=300,
    )
    if head.exit_code != 0 or branch.exit_code != 0:
        raise ErroDeSessao(
            P_WORKTREE,
            "não consegui identificar a revisão inicial da bancada",
            detalhe="Preserve os arquivos e confira o checkout antes de retomar.",
        )
    dados = {
        "schema_version": 1,
        "identidade": identidade,
        "bancada": str(plano.worktree.resolve()),
        "branch": branch.stdout.strip(),
        "head": head.stdout.strip(),
        "capturado_em": datetime.now(timezone.utc).isoformat(),
        "estado": _resumo_do_status(status.stdout),
        "plano": metadados_da_bancada(plano),
    }
    caminho.parent.mkdir(parents=True, exist_ok=True)
    temporario = caminho.with_suffix(f".{uuid.uuid4().hex}.tmp")
    temporario.write_text(json.dumps(dados, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporario.replace(caminho)
    return caminho


def requisitos_do_venv(plano: Plano) -> tuple[Path, ...]:
    arquivos = []
    if plano.sobe_ambiente:
        arquivos.append(plano.requisitos)
    arquivos.append(plano.requisitos_ci)
    return tuple(arquivos)


def identidade_do_venv(requisitos: Path | Sequence[Path], *, ler=None, python_base: tuple[str, str] | None = None) -> str:
    identidade = hashlib.sha256()
    executavel, versao = python_base or python_base_atual()
    identidade.update(repr((executavel, versao, platform.system(), platform.release(), platform.machine(),
                            FERRAMENTAS_DE_PORTAO)).encode())
    visitados = set()

    def incluir(arquivo):
        arquivo = arquivo.resolve()
        if arquivo in visitados:
            return
        visitados.add(arquivo)
        conteudo = (ler(arquivo) if ler else arquivo.read_bytes()).replace(b"\r\n", b"\n")
        identidade.update(str(arquivo.name).encode("utf-8"))
        identidade.update(len(conteudo).to_bytes(8, "big"))
        identidade.update(conteudo)
        for linha in conteudo.decode("utf-8").splitlines():
            linha = linha.split(" #", 1)[0].strip()
            referencia = re.match(r"^(?:-r\s*|-c\s*|--requirement(?:=|\s+)|--constraint(?:=|\s+))(.+)$", linha)
            if referencia:
                incluir(arquivo.parent / referencia.group(1).strip())
            elif (linha.startswith(("-e", "--editable", "-f", "--find-links", ".", "/", "\\", "file:"))
                  or PureWindowsPath(linha).drive
                  or (" @ " in linha and not linha.split(" @ ", 1)[1].startswith(("https://", "http://")))
                  or (linha.lower().endswith((".whl", ".zip", ".tar.gz")) and "://" not in linha)):
                raise ErroDeSessao(P_VENV, "dependência local sem identidade imutável",
                                   detalhe=f"Use uma versão publicada antes de reutilizar o ambiente: {linha}")
    try:
        if isinstance(requisitos, (str, Path)):
            incluir(Path(requisitos))
        else:
            for arquivo in requisitos:
                incluir(Path(arquivo))
    except (OSError, UnicodeError) as erro:
        raise ErroDeSessao(P_VENV, "não foi possível ler as dependências",
                           detalhe=f"Confira os requirements da sessão e repita a abertura: {erro}") from erro
    return identidade.hexdigest()


# ---------------------------------------------------------------------------
# Executor oficial da sessão
# ---------------------------------------------------------------------------

CHAVES_SENSIVEIS_DO_ENV = re.compile(r"(SECRET|TOKEN|PASSWORD|SENHA|DATABASE_URL|REDIS.*URL|API_KEY|PRIVATE_KEY|ACCESS_KEY|_KEY$)", re.I)



def comando_abrir_seguro(plano: Plano) -> str:
    comando = ["python", "ci/sessao.py", "abrir", "--celula", plano.celula, "--tarefa", plano.tarefa]
    if plano.tarefa_da_fila:
        comando += ["--tar", plano.tarefa_da_fila]
    if not plano.sobe_ambiente:
        comando.append("--sem-container")
    comando += ["--scratch", str(plano.scratch.parent)]
    return subprocess.list2cmdline(comando)

def carregar_env_de_sessao(arquivo: Path) -> dict[str, str]:
    try:
        linhas = arquivo.read_text(encoding="utf-8").splitlines()
    except OSError as erro:
        raise ErroDeSessao(
            "executor da sessão",
            ".env da sessão indisponível",
            detalhe=f"Esperado em {arquivo}. Trabalho preservado; nenhum filho executou. Reabra pelo comando original da sessão ou rode `python ci/sessao.py --help` para conferir a sintaxe antes de tentar de novo.",
        ) from erro
    env: dict[str, str] = {}
    for numero, linha in enumerate(linhas, 1):
        if not linha.strip() or linha.startswith("#"):
            continue
        casou = re.fullmatch(r"([A-Z0-9_]+)='([^'\n]*)'", linha)
        if not casou:
            raise ErroDeSessao(
                "executor da sessão",
                ".env da sessão tem formato inválido",
                detalhe=f"Linha {numero} não segue KEY='valor'. Preserve o arquivo e rode a abertura para regenerar.",
            )
        chave = casou.group(1)
        if chave in env:
            raise ErroDeSessao(
                "executor da sessão",
                ".env da sessão tem chave duplicada",
                detalhe=f"Linha {numero} repete {chave}. Preserve o arquivo e rode a abertura para regenerar.",
            )
        env[chave] = casou.group(2)
    return env


def _redigir_com_env(texto: str, env: dict[str, str]) -> str:
    try:
        from telemetria import redigir
        texto = redigir(texto)
    except Exception:
        pass
    for chave, valor in env.items():
        if not valor or not CHAVES_SENSIVEIS_DO_ENV.search(chave):
            continue
        texto = texto.replace(valor, f"[redigido:{chave}]")
    return texto


def _ambiente_do_executor(plano: Plano, env_sessao: dict[str, str]) -> dict[str, str]:
    base = {
        chave: valor
        for chave, valor in os.environ.items()
        if chave.upper() in {"SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT", "TEMP", "TMP", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"}
    }
    for chave in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV", "DJANGO_SETTINGS_MODULE"):
        base.pop(chave, None)
    for chave in list(base):
        if chave.startswith("PYTEST_"):
            base.pop(chave, None)
    base.update(env_sessao)
    for chave in ("PYTHONHOME", "PYTHONPATH", "VIRTUAL_ENV"):
        base.pop(chave, None)
    for chave in list(base):
        if chave.startswith("PYTEST_"):
            base.pop(chave, None)
    base["PYTHONUTF8"] = "1"
    base["PYTHONDONTWRITEBYTECODE"] = "1"
    base["VIRTUAL_ENV"] = str(plano.venv)
    resto_path = os.environ.get("PATH", "")
    base["PATH"] = str(plano.bin_do_venv) + (os.pathsep + resto_path if resto_path else "")
    return base


def _plano_do_estado(dados: dict[str, object]) -> Plano:
    bruto = dados.get("plano")
    if not isinstance(bruto, dict):
        raise ErroDeSessao("executor da sessão", "registro inicial sem plano", detalhe="Rode a abertura da sessão de novo; a bancada foi preservada.")
    try:
        return Plano(
            celula=str(bruto["celula"]), tarefa=str(bruto["tarefa"]), frase=str(bruto.get("frase") or ""),
            sobe_ambiente=bool(bruto["sobe_ambiente"]), tarefa_da_fila=str(bruto.get("tarefa_da_fila") or ""),
            raiz=Path(str(bruto["raiz"])), worktree=Path(str(bruto["worktree"])), branch=str(bruto["branch"]),
            scratch=Path(str(bruto["scratch"])), venv=Path(str(bruto["venv"])), arquivo_env=Path(str(bruto["arquivo_env"])),
            postgres=str(bruto.get("postgres") or ""), porta_postgres=int(bruto.get("porta_postgres") or 0),
            redis=str(bruto.get("redis") or ""), porta_redis=int(bruto.get("porta_redis") or 0),
        )
    except (KeyError, TypeError, ValueError) as erro:
        raise ErroDeSessao("executor da sessão", "registro inicial incompleto", detalhe="Rode a abertura da sessão de novo; a bancada foi preservada.") from erro


def _caminho_igual(a: str | Path, b: str | Path) -> bool:
    esquerda = str(Path(a))
    direita = str(Path(b))
    if platform.system() == "Windows":
        return esquerda.casefold() == direita.casefold()
    return esquerda == direita


def _python_base_da_sessao(dados: dict[str, object], env_sessao: dict[str, str]) -> tuple[str, str] | None:
    executavel = env_sessao.get("SESSAO_PYTHON_BASE_EXECUTABLE")
    versao = env_sessao.get("SESSAO_PYTHON_BASE_VERSION")
    if executavel and versao:
        return executavel, versao
    plano = dados.get("plano")
    if isinstance(plano, dict):
        base = plano.get("python_base")
        if isinstance(base, dict) and base.get("executable") and base.get("version"):
            return str(base["executable"]), str(base["version"])
    return None


def _info_do_python_da_sessao(plano: Plano) -> dict[str, str]:
    codigo = (
        "import json,sys;"
        "print(json.dumps({"
        "'executable':sys.executable,"
        "'base_executable':getattr(sys,'base_executable',getattr(sys,'_base_executable','')),"
        "'version':sys.version"
        "}, ensure_ascii=False))"
    )
    saida = correr_de_verdade(
        [str(plano.python_do_venv), "-c", codigo],
        cwd=plano.worktree,
        env=_ambiente_do_executor(plano, {}),
        timeout=30,
    )
    if saida.exit_code != 0:
        raise ErroDeSessao("executor da sessão", "Python da sessão não executa", detalhe=recortar(saida.texto, 2000))
    try:
        info = json.loads(saida.stdout.strip())
    except ValueError as erro:
        raise ErroDeSessao("executor da sessão", "Python da sessão devolveu identidade ilegível", detalhe=recortar(saida.texto, 2000)) from erro
    return {str(chave): str(valor) for chave, valor in info.items()}


def plano_da_bancada_atual(cwd: Path) -> tuple[Plano, dict[str, object], dict[str, str]]:
    git = correr_de_verdade(["git", "-C", str(cwd), "rev-parse", "--show-toplevel"], timeout=60)
    if git.exit_code != 0:
        raise ErroDeSessao("executor da sessão", "diretório atual não é uma bancada Git", detalhe=recortar(git.texto, 2000))
    worktree = Path(git.stdout.strip()).resolve()
    if (worktree / ".git").is_dir():
        raise ErroDeSessao(
            "executor da sessão",
            "execução recusada no clone principal",
            detalhe="A execução oficial exige Git worktree vinculado (.git como arquivo gitdir). Trabalho preservado; nenhum filho executou.",
        )
    estado = arquivo_de_estado_inicial(worktree)
    if not estado.exists():
        raise ErroDeSessao("executor da sessão", "esta bancada não tem registro inicial da sessão", detalhe="Trabalho preservado; nenhum filho executou. Entre no worktree impresso em `BANCADA PRONTA:` na abertura original. Para conferir a sintaxe de reabertura, rode `python ci/sessao.py --help`.")
    try:
        dados = json.loads(estado.read_text(encoding="utf-8"))
    except (OSError, ValueError) as erro:
        raise ErroDeSessao("executor da sessão", "registro inicial ilegível", detalhe=f"Preserve {estado} e repita a abertura.") from erro
    if dados.get("identidade") != identidade_duravel_da_bancada(worktree):
        raise ErroDeSessao("executor da sessão", "registro inicial pertence a outra bancada", detalhe="Preserve os arquivos e confira o worktree antes de executar.")
    plano = _plano_do_estado(dados)
    if plano.worktree.resolve() != worktree:
        raise ErroDeSessao("executor da sessão", "cwd não corresponde à bancada registrada", detalhe=f"cwd real: {worktree}\nregistro: {plano.worktree}")
    env_sessao = carregar_env_de_sessao(plano.arquivo_env)
    if env_sessao.get("SESSAO_WORKTREE") and Path(env_sessao["SESSAO_WORKTREE"]).resolve() != worktree:
        raise ErroDeSessao("executor da sessão", ".env pertence a outra bancada", detalhe="Rode a abertura da sessão nesta bancada; nada foi executado.")
    venv_env = env_sessao.get("SESSAO_VENV")
    if not venv_env:
        raise ErroDeSessao("executor da sessão", ".env sem SESSAO_VENV definitivo", detalhe=f"O snapshot inicial antecede o hash do venv. Trabalho preservado; nenhum filho executou. Reabra com: {comando_abrir_seguro(plano)}")
    plano = replace(plano, venv=Path(venv_env))
    marca = plano.venv / ".instalado"
    try:
        instalado = marca.read_text(encoding="utf-8")
    except OSError as erro:
        raise ErroDeSessao("executor da sessão", "ambiente sem marcador de instalação", detalhe=f"Esperado em {marca}. Rode a abertura para concluir a instalação.") from erro
    python_base = _python_base_da_sessao(dados, env_sessao)
    if python_base is not None:
        esperado = identidade_do_venv(requisitos_do_venv(plano), python_base=python_base)
        if plano.venv.name != esperado:
            raise ErroDeSessao("executor da sessão", "venv não corresponde aos requisitos atuais", detalhe=f"requirements, Python da abertura ou plataforma mudaram. Trabalho preservado; nenhum filho executou. Reabra com: {comando_abrir_seguro(plano)}")
        if instalado != esperado:
            raise ErroDeSessao("executor da sessão", "marcador de instalação incompatível", detalhe=f"{marca} não confirma o ambiente {esperado[:12]}.")
    elif instalado != plano.venv.name:
        raise ErroDeSessao("executor da sessão", "ambiente antigo sem identidade verificável", detalhe=f"{marca} não confirma o nome do venv. Trabalho preservado; nenhum filho executou.")
    if not plano.python_do_venv.exists():
        raise ErroDeSessao("executor da sessão", "Python da sessão não existe", detalhe=f"Esperado em {plano.python_do_venv}. Trabalho preservado; nenhum filho executou. Reabra com: {comando_abrir_seguro(plano)}")
    info = _info_do_python_da_sessao(plano)
    if not _caminho_igual(info.get("executable", ""), plano.python_do_venv):
        raise ErroDeSessao("executor da sessão", "Python executado não é o venv da sessão", detalhe=f"esperado: {plano.python_do_venv}\nmedido: {info.get('executable', '')}")
    if python_base is not None:
        if info.get("version") != python_base[1]:
            raise ErroDeSessao("executor da sessão", "versão do Python da sessão mudou", detalhe="Trabalho preservado; nenhum filho executou.")
        base_medida = info.get("base_executable")
        if base_medida and not _caminho_igual(base_medida, python_base[0]):
            raise ErroDeSessao("executor da sessão", "Python base da sessão mudou", detalhe=f"esperado: {python_base[0]}\nmedido: {base_medida}")
    return plano, dados, env_sessao


def _base_do_ci(dados: dict[str, object]) -> str:
    head = str(dados.get("head") or "")
    if not re.fullmatch(r"[0-9a-f]{40,64}", head):
        raise ErroDeSessao("executor da sessão", "registro inicial sem base Git", detalhe="Sem a revisão inicial não há como executar `ci` com --base seguro.")
    return head


def comando_do_executor(plano: Plano, dados: dict[str, object], argumentos: Sequence[str]) -> tuple[list[str], Path, str]:
    args = list(argumentos)
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        raise ErroDeSessao("executor da sessão", "comando ausente", detalhe="Use um comando completo, por exemplo `python ci/sessao.py executar -- pytest -q` ou `python ci/sessao.py executar -- ci`. Trabalho preservado; nenhum filho executou.")
    alvo, resto = args[0], args[1:]
    if alvo == "pytest":
        cwd = plano.celula_no_worktree if plano.sobe_ambiente else plano.worktree
        return [str(plano.python_do_venv), "-m", "pytest", *resto], cwd, "pytest"
    if alvo == "ci":
        if resto:
            raise ErroDeSessao(
                "executor da sessão",
                "argumento recusado no runner ci",
                detalhe="Use `python ci/sessao.py executar -- ci` para os gates oficiais; para foco manual, use `pytest` ou comando literal.",
            )
        base = _base_do_ci(dados)
        comando = [str(plano.python_do_venv), "ci/ci.py"]
        if plano.sobe_ambiente:
            comando += ["--apenas", "celula", "--celula", plano.celula]
        comando += ["--base", base, *resto]
        return comando, plano.worktree, "ci"
    return args, plano.worktree, "literal"


def _grupo_de_processos():
    if platform.system() == "Windows":
        from pr_processos_windows import GrupoWindows
        return GrupoWindows()
    if platform.system() == "Linux":
        from pr_processos_linux import GrupoLinux
        return GrupoLinux()
    raise ErroDeSessao("executor da sessão", "plataforma sem grupo de processos", detalhe="A contenção oficial existe em Windows e Linux.")


def _executavel_candidato(caminho: Path) -> bool:
    if not caminho.is_file():
        return False
    if platform.system() == "Windows":
        return True
    return os.access(caminho, os.X_OK)


def _nomes_executaveis(nome: str, env: dict[str, str]) -> list[str]:
    if platform.system() != "Windows":
        return [nome]
    sufixos = [s.lower() for s in Path(nome).suffixes]
    pathext = env.get("PATHEXT") or os.environ.get("PATHEXT") or ".COM;.EXE;.BAT;.CMD"
    extensoes = [ext for ext in pathext.split(os.pathsep) if ext]
    if sufixos and sufixos[-1] in {ext.lower() for ext in extensoes}:
        return [nome]
    return [nome, *(nome + ext for ext in extensoes)]


def _resolver_executavel_no_ambiente(comando: list[str], env: dict[str, str]) -> list[str]:
    if not comando:
        return comando
    primeiro = str(comando[0])
    if Path(primeiro).is_absolute() or any(sep in primeiro for sep in ("/", "\\")):
        return comando
    for pasta in (env.get("PATH") or os.defpath).split(os.pathsep):
        if not pasta:
            continue
        for nome in _nomes_executaveis(primeiro, env):
            candidato = Path(pasta) / nome
            if _executavel_candidato(candidato):
                return [str(candidato), *comando[1:]]
    raise ErroDeSessao(
        "executor da sessão",
        "executável não encontrado no PATH da sessão",
        detalhe=f"Comando: {primeiro}. Trabalho preservado; nenhum filho executou.",
        codigo=127,
    )


def _iniciar_no_grupo(grupo, comando: list[str], *, cwd: Path, env: dict[str, str]):
    if not hasattr(grupo, "iniciar"):
        raise ErroDeSessao(
            "executor da sessão",
            "API de grupo de processos incompatível",
            detalhe="Esta frente depende da API `GrupoWindows/GrupoLinux.iniciar(comando, raiz, ambiente)` do PR de processos; sem ela haveria janela de órfãos.",
        )
    return grupo.iniciar(comando, raiz=cwd, ambiente=env)


def _signed32(codigo: int) -> int:
    codigo = codigo & 0xFFFFFFFF
    return codigo - 0x100000000 if codigo & 0x80000000 else codigo


def _codigo_cli(codigo: int) -> int:
    if platform.system() == "Windows":
        return _signed32(codigo)
    return codigo


def sair_do_processo(codigo: int) -> int:
    codigo = _codigo_cli(codigo)
    if platform.system() == "Linux" and codigo < 0:
        os.kill(os.getpid(), -codigo)
        return 128 + (-codigo)
    return codigo


class MonitorDePosse:
    def __init__(self, plano: Plano, grupo, *, intervalo: float = INTERVALO_CONFERENCIA_POSSE_SEGUNDOS):
        self.plano = plano
        self.grupo = grupo
        self.intervalo = intervalo
        self.parar = threading.Event()
        self.perda = ""
        self.thread: threading.Thread | None = None

    def _conferir(self) -> bool:
        if not self.plano.tarefa_da_fila:
            return True
        try:
            import reservar
            leitura = reservar.ler_reserva(self.plano.worktree, f"tarefa-{self.plano.tarefa_da_fila}")
            if leitura is None:
                self.perda = "reserva da tarefa ausente"
                return False
            _, corpo = leitura
            if corpo.get("estado") == "publicacao_pendente":
                self.perda = "reserva protege publicação pendente; não autoriza nova execução"
                return False
            if corpo.get("tipo") != "intencao" or corpo.get("chave") != f"tarefa-{self.plano.tarefa_da_fila}" or corpo.get("dono") != reservar.identidade_da_bancada(self.plano.worktree):
                self.perda = "reserva da tarefa não pertence a esta bancada"
                return False
            expira = datetime.fromisoformat(str(corpo.get("expira_em") or ""))
            if expira.tzinfo is None or expira <= datetime.now(timezone.utc):
                self.perda = "reserva da tarefa expirou"
                return False
            return True
        except Exception as erro:
            if not self.perda:
                self.perda = f"não consegui reconferir a reserva durante a execução: {erro}"
            return False

    def iniciar(self) -> None:
        if not self.plano.tarefa_da_fila:
            return
        if not self._conferir():
            raise ErroDeSessao("executor da sessão", "posse da tarefa indisponível", detalhe=self.perda)

        def vigiar():
            while not self.parar.wait(self.intervalo):
                if not self._conferir():
                    try:
                        self.grupo.encerrar()
                    finally:
                        self.parar.set()
                    return

        self.thread = threading.Thread(target=vigiar, name="sessao-posse", daemon=True)
        self.thread.start()

    def encerrar(self) -> None:
        self.parar.set()
        if self.thread is not None:
            self.thread.join(timeout=1)


def executar_na_sessao(argv: Sequence[str], *, cwd: Path | None = None, intervalo_posse: float = INTERVALO_CONFERENCIA_POSSE_SEGUNDOS) -> int:
    cwd = (cwd or Path.cwd()).resolve()
    plano, dados, env_sessao = plano_da_bancada_atual(cwd)
    comando, cwd_comando, apelido = comando_do_executor(plano, dados, argv)
    env = _ambiente_do_executor(plano, env_sessao)
    comando = _resolver_executavel_no_ambiente(comando, env)
    comando_texto = subprocess.list2cmdline(comando)
    inicio = datetime.now(timezone.utc)
    pasta_logs = plano.scratch / "execucoes"
    pasta_logs.mkdir(parents=True, exist_ok=True)
    log = pasta_logs / f"{inicio.strftime('%Y%m%d-%H%M%S-%f')}-{uuid.uuid4().hex[:8]}-{apelido}.log"
    stdout = stderr = ""
    codigo = 2
    with trava_da_bancada(plano.worktree, passo="executor da sessão", esperar=False):
        grupo = _grupo_de_processos()
        monitor = MonitorDePosse(plano, grupo, intervalo=intervalo_posse)
        try:
            monitor.iniciar()
            processo = _iniciar_no_grupo(grupo, comando, cwd=cwd_comando, env=env)
            try:
                stdout, stderr = processo.communicate(timeout=TIMEOUT_EXECUTOR_SEGUNDOS)
                codigo = int(processo.returncode or 0)
            except subprocess.TimeoutExpired:
                grupo.encerrar()
                stdout, stderr = processo.communicate(timeout=5)
                stderr = (stderr or "") + f"\nTimeout de {TIMEOUT_EXECUTOR_SEGUNDOS}s; filhos encerrados pelo grupo de processos.\n"
                codigo = 124
            except KeyboardInterrupt:
                grupo.encerrar()
                stderr = "Interrompido por Ctrl+C; filhos encerrados pelo grupo de processos.\n"
                codigo = 130
            finally:
                monitor.encerrar()
            if monitor.perda:
                codigo = 2
                stderr = (stderr or "") + f"\nExecução interrompida: {monitor.perda}\n"
        finally:
            try:
                grupo.encerrar()
            except Exception as erro:
                stderr = (stderr or "") + f"\nFalha ao encerrar grupo de processos: {erro}\n"
                codigo = 2
    fim = datetime.now(timezone.utc)
    texto = "\n".join([
        f"inicio={inicio.isoformat()}", f"fim={fim.isoformat()}", f"worktree={plano.worktree}",
        f"cwd={cwd_comando}", f"python={plano.python_do_venv}", f"comando={comando_texto}", f"exit_code={codigo}",
        "--- stdout ---", stdout or "", "--- stderr ---", stderr or "",
    ])
    log.write_text(_redigir_com_env(texto, env_sessao), encoding="utf-8")
    if stdout:
        print(_redigir_com_env(stdout, env_sessao), end="")
    if stderr:
        print(_redigir_com_env(stderr, env_sessao), end="", file=sys.stderr)
    print(f"Log da execução: {log}", file=sys.stderr)
    return _codigo_cli(codigo)


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
        self._estado_git = "não medido"
        self._passos = passos_do_plano(plano)
        self._variaveis: dict[str, str] = {}
        self._servicos: dict[str, str] = {}

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

    def _conferir_ferramentas(self, ferramentas: dict[str, str]) -> dict[str, str]:
        passo = P_CONFERIR
        encontrados = {}
        ausentes = []
        for nome, para_que in ferramentas.items():
            caminho = self._localizar(nome)
            if caminho is None:
                ausentes.append(f"`{nome}` não está no PATH: {para_que}")
            else:
                encontrados[nome] = caminho
        if ausentes:
            raise ErroDeSessao(
                passo,
                "há ferramenta local necessária ausente",
                detalhe=(
                    "Resolva a instalação indicada e repita a abertura.\n\n"
                    + "\n".join(f"  - {item}" for item in ausentes)
                ),
            )
        return encontrados

    def conferir_pecas_locais(self) -> dict[str, str]:
        """Confere git/gh e hooks antes de consultar ou criar estado."""
        passo = P_CONFERIR
        encontrados = self._conferir_ferramentas(dict(FERRAMENTAS_LOCAIS))
        git = encontrados["git"]
        config = self._correr(
            [git, "-C", str(self.plano.raiz), "config", "--get", "core.hooksPath"],
            cwd=self.plano.raiz,
            timeout=120,
        )
        hooks_path = config.stdout.strip()
        if config.exit_code != 0 or not hooks_path:
            raise ErroDeSessao(
                passo,
                "os hooks versionados não estão instalados neste checkout",
                comando=f"{git} -C {self.plano.raiz} config --get core.hooksPath",
                detalhe=(
                    "O Git não apontou para os hooks versionados. Instale-os com:\n"
                    f"  git -C {self.plano.raiz} config core.hooksPath .githooks\n\n"
                    "Depois repita a abertura da sessão."
                ),
            )
        pasta_hooks = Path(hooks_path)
        if not pasta_hooks.is_absolute():
            pasta_hooks = self.plano.raiz / pasta_hooks
        faltando = [nome for nome in GANCHOS_VERSIONADOS if not self._existe(pasta_hooks / nome)]
        if faltando:
            raise ErroDeSessao(
                passo,
                "há hook versionado ausente",
                detalhe=(
                    f"Pasta configurada: {pasta_hooks}\n"
                    + "\n".join(f"  - {pasta_hooks / nome}" for nome in faltando)
                    + "\n\nRestaure os hooks versionados e repita a abertura."
                ),
            )
        return encontrados

    def conferir_pecas_do_ambiente(self) -> None:
        """Confere Docker/Make só quando a sessão vai preparar implementação."""
        if self.plano.sobe_ambiente:
            self._conferir_ferramentas(dict(FERRAMENTAS_LOCAIS_COM_AMBIENTE))

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
            if atual != self.plano.branch:
                raise ErroDeSessao(
                    passo,
                    f"o worktree existe, mas está na branch '{atual}'",
                    detalhe=f"Esperada: {self.plano.branch}\nWorktree: {self.plano.worktree}\n\n"
                    "Reusar um worktree de OUTRA tarefa misturaria dois despachos.\n"
                    "Escolha outra TAREFA ou confira a branch e o trabalho existente.\n"
                    "Nenhum arquivo foi removido ou alterado por esta conferência.",
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
        repositório informado ao comando. Chamar a fila apontando para o clone
        principal faria o evento nascer órfão no espelho, com o validador da
        fila respondendo "válida" sem ele. Por isso a raiz entregue ao balcão é
        a bancada.

        `armadilhas/357`: e é o PRIMEIRO passo depois de a pasta existir. A
        mesma trava da bancada cobre o balcão e é reentrante no processo atual,
        então a abertura não cria uma janela entre reivindicar, anunciar PR,
        gerar índice e escrever metadados de ambiente.
        """
        passo = self._abrir(P_BALCAO)
        tid = self.plano.tarefa_da_fila
        quem = self.plano.quem_no_balcao
        import fila

        buffer = io.StringIO()
        with redirect_stdout(buffer):
            codigo = fila.cmd_pegar(
                self.plano.worktree,
                argparse.Namespace(tarefa=tid, quem=quem),
            )
        texto = buffer.getvalue()
        if codigo != 0:
            raise ErroDeSessao(
                passo,
                f"o balcão recusou {tid} — a tarefa NÃO é sua",
                comando=f'python ci/fila.py pegar {tid} --quem "{quem}"',
                detalhe=recortar(texto, 2000)
                + "\n\nA fala acima é do BALCÃO, não deste script. Quase sempre é\n"
                "outro robô que pegou a tarefa primeiro, ou ela está trancada.\n"
                "NÃO escreva um byte nesta bancada: pare e informe o bloqueio ao mantenedor, com o que falta para retomar.\n"
                "A bancada e o trabalho preexistente foram preservados.\n"
                "O quadro de agora: python ci/fila.py listar --ao-vivo",
                codigo=1,
            )
        self._pass(f"{tid} é sua · o comprovante nasceu na bancada (commite-o no PR)")

    def _commit_de_anuncio(self, passo: str, eventos: Sequence[str]) -> None:
        head = self._exigir(
            passo,
            ["git", "rev-parse", "HEAD"],
            cwd=self.plano.worktree,
            timeout=120,
        ).stdout.strip()
        indice = self.plano.scratch / f"anuncio-{uuid.uuid4().hex}.index"
        env = {**os.environ, "GIT_INDEX_FILE": str(indice)}
        try:
            self._exigir(
                passo,
                ["git", "read-tree", head],
                cwd=self.plano.worktree,
                env=env,
                timeout=120,
            )
            if eventos:
                self._exigir(
                    passo,
                    ["git", "add", "--", *eventos],
                    cwd=self.plano.worktree,
                    env=env,
                    timeout=120,
                )
            arvore = self._exigir(
                passo,
                ["git", "write-tree"],
                cwd=self.plano.worktree,
                env=env,
                timeout=120,
            ).stdout.strip()
            mensagem = (
                f"chore: embarcar o comprovante de {self.plano.tarefa_da_fila}"
                if eventos
                else "chore: anunciar intenção da sessão"
            )
            commit = self._exigir(
                passo,
                [
                    "git",
                    "commit-tree",
                    arvore,
                    "-p",
                    head,
                    "-m",
                    mensagem,
                    "-m",
                    "Co-Authored-By: Codex <noreply@openai.com>",
                ],
                cwd=self.plano.worktree,
                timeout=120,
            ).stdout.strip()
            self._exigir(
                passo,
                ["git", "update-ref", f"refs/heads/{self.plano.branch}", commit, head],
                cwd=self.plano.worktree,
                timeout=120,
            )
            if eventos:
                self._exigir(
                    passo,
                    ["git", "add", "--", *eventos],
                    cwd=self.plano.worktree,
                    timeout=120,
                )
        finally:
            indice.unlink(missing_ok=True)

    def _conferir_bancada_da_entrega_integrada(self, git: str, passo: str) -> None:
        lista = self._exigir(
            passo,
            [git, "-C", str(self.plano.raiz), "worktree", "list", "--porcelain"],
            cwd=self.plano.raiz,
            timeout=120,
        )
        if not (worktree_ja_existe(lista.stdout, self.plano.worktree) and self._existe(self.plano.worktree / ".git")):
            raise ErroDeSessao(
                passo,
                "bancada da entrega integrada não está disponível",
                detalhe=(
                    f"Worktree esperado: {self.plano.worktree}\n"
                    "Sem essa identidade local, um PR achado só pelo ramo poderia ser associado à TAR errada."
                ),
            )
        atual = self._exigir(
            passo,
            [git, "-C", str(self.plano.worktree), "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=self.plano.raiz,
            timeout=120,
        ).stdout.strip()
        if atual != self.plano.branch:
            raise ErroDeSessao(
                passo,
                "bancada da entrega integrada tem identidade diferente",
                detalhe=f"Branch esperada: {self.plano.branch}\nBranch encontrada: {atual}\nWorktree: {self.plano.worktree}",
            )

    @staticmethod
    def _mesmo_pr_submetido(valor: object, numero: int, url: str) -> bool:
        texto = str(valor or "").rstrip("/")
        return texto == url.rstrip("/")

    def _conferir_submissao_da_tarefa_integrada(self, passo: str, numero: int, url: str) -> None:
        tarefa = self.plano.tarefa_da_fila
        if not tarefa:
            raise ErroDeSessao(
                passo,
                "TAR ausente para retomar entrega integrada",
                detalhe="Informe --tar TAR-NNN; PR integrado sem vínculo de fila não autoriza retomada de tarefa.",
            )
        try:
            from fila import carregar_fila_publicada_e_local

            tarefas, eventos, fonte = carregar_fila_publicada_e_local(self.plano.worktree)
        except Exception as erro:  # noqa: BLE001 - fonte de fila é externa ao bootstrap
            raise ErroDeSessao(
                passo,
                "fonte da fila indisponível para retomar entrega integrada",
                detalhe=f"Não consegui medir a fila publicada/local desta bancada. Erro: {erro}",
            ) from erro
        if fonte.get("modo") != "origin-main-mais-local" or not fonte.get("origin_main"):
            raise ErroDeSessao(
                passo,
                "fonte da fila indisponível para retomar entrega integrada",
                detalhe="A fila publicada em origin/main não foi medida; sem isso, PR por ramo vira chute.",
            )
        if tarefa not in tarefas:
            raise ErroDeSessao(
                passo,
                "TAR ausente no snapshot medido da fila",
                detalhe=f"TAR recebida: {tarefa}. Não associo PR integrado a tarefa que não está na fila medida.",
            )
        submetida = any(
            ev.get("evento") == "submetida"
            and ev.get("tarefa") == tarefa
            and self._mesmo_pr_submetido(ev.get("pr"), numero, url)
            for ev in eventos
        )
        if not submetida:
            raise ErroDeSessao(
                passo,
                "PR integrado não está submetido para a TAR recebida",
                detalhe=(
                    f"TAR recebida: {tarefa}. PR encontrado: #{numero}. "
                    "A retomada exige evento submetida dessa TAR apontando para esse PR no snapshot medido."
                ),
            )

    def retomar_entrega_integrada(self, git: str, gh: str) -> str | None:
        passo = self._abrir(P_ANUNCIO)
        consulta = self._exigir(
            passo,
            [gh, "pr", "list", "--head", self.plano.branch, "--state", "all",
             "--json", "number,url,state,isDraft"],
            cwd=self.plano.raiz,
            timeout=120,
        )
        try:
            prs = json.loads(consulta.stdout or "")
        except (TypeError, ValueError) as erro:
            raise ErroDeSessao(
                passo,
                "a consulta de PR devolveu JSON inválido",
                comando=f"gh pr list --head {self.plano.branch} --state all --json number,url,state,isDraft",
                detalhe="Confira o acesso ao GitHub e repita a abertura. Nenhum anúncio foi declarado.",
            ) from erro
        if not isinstance(prs, list) or len(prs) > 1:
            raise ErroDeSessao(
                passo,
                "o ramo tem zero ou mais de um PR aberto de forma inconclusiva",
                comando=f"gh pr list --head {self.plano.branch} --state all --json number,url,state,isDraft",
                detalhe="Confira os PRs deste ramo antes de repetir. A sessão não vai escolher um no escuro.",
            )
        if not prs:
            return None
        pr = prs[0]
        if not isinstance(pr, dict):
            raise ErroDeSessao(passo, "o PR existente não tem identidade válida", detalhe="Confira gh pr list e repita.")
        numero = pr.get("number")
        url = str(pr.get("url") or "").rstrip("/")
        estado_pr = pr.get("state")
        if not isinstance(numero, int) or not url:
            raise ErroDeSessao(passo, "o PR existente não tem identidade válida", detalhe="Confira gh pr list e repita.")
        if estado_pr == "OPEN":
            return None
        if estado_pr not in {"MERGED", "CLOSED"}:
            raise ErroDeSessao(
                passo,
                "estado do PR existente não foi medido",
                detalhe=f"PR #{numero} devolveu state={estado_pr!r}. Sem estado explícito, não retomo nem reabro tarefa.",
            )
        tarefa = self.plano.tarefa_da_fila or self.plano.tarefa
        if estado_pr == "MERGED":
            self._conferir_bancada_da_entrega_integrada(git, passo)
            self._conferir_submissao_da_tarefa_integrada(passo, numero, url)
            try:
                import estado_da_entrega

                medicao = estado_da_entrega.consultar_entrega(self.plano.raiz, numero)
            except Exception as erro:  # noqa: BLE001 - fronteira de fonte externa
                raise ErroDeSessao(
                    passo,
                    f"fonte da entrega integrada indisponível para o PR #{numero}",
                    detalhe=(
                        f"O PR #{numero} já foi integrado, mas não consegui medir estado_da_entrega. "
                        f"Sem essa fonte, a sessão não autoriza nova aquisição de {tarefa} nem declara aceite. "
                        f"Erro: {erro}"
                    ),
                ) from erro
            if (
                not isinstance(medicao, dict)
                or not isinstance(medicao.get("estado"), str)
                or not medicao["estado"].strip()
                or medicao["estado"].strip() == "NÃO MEDIDO"
            ):
                raise ErroDeSessao(
                    passo,
                    f"fonte da entrega integrada indisponível para o PR #{numero}",
                    detalhe=(
                        "estado_da_entrega não devolveu um estado medido. "
                        f"Sem essa fonte, a sessão não autoriza nova aquisição de {tarefa} nem declara aceite."
                    ),
                )
            estado_entrega = medicao["estado"].strip()
            self._pass(f"PR #{numero} integrado; entrega medida: {estado_entrega}")
            return (
                f"PR #{numero} já integrado para {tarefa}. Estado da entrega: {estado_entrega}. "
                f"Bancada preservada; nenhuma nova aquisição foi feita. "
                f"Próximo comando seguro: python ci/esperar.py --entrega {numero} --so-desfecho. "
                "Reconcilie aceite somente quando o fluxo de entrega publicar prova real."
            )
        raise ErroDeSessao(
            passo,
            f"PR fechado sem merge #{numero}",
            detalhe=(
                f"O PR #{numero} está fechado sem merge para este ramo. "
                "Ele não prova publicação nem aceite; confira a causa do fechamento antes de retomar."
            ),
        )

    def anunciar_pr(self, gh: str) -> None:
        """Publica a intenção antes de o agente começar a construir.

        O primeiro commit é vazio quando não há comprovante da fila. Quando há,
        ele embarca só o evento que o balcão acabou de criar por índice
        temporário e `update-ref` com SHA esperado. Assim o PR existe antes do
        código, sem transformar alterações herdadas em anúncio.
        """
        passo = self._abrir(P_ANUNCIO)
        titulo = f"rascunho: {self.plano.frase or self.plano.tarefa_da_fila or self.plano.tarefa}"
        corpo = (
            "# Trabalho em andamento\n\n"
            "Este PR foi aberto como rascunho no início da sessão para anunciar "
            "quem está trabalhando e evitar trabalho duplicado.\n\n"
            f"Área: {self.plano.celula}\n"
            f"Ramo: {self.plano.branch}\n"
            f"Tarefa: {self.plano.tarefa_da_fila or self.plano.tarefa}\n\n"
            "A revisão só será solicitada depois da implementação e da validação."
        )
        corpo_arquivo = self.plano.scratch / f"anuncio-{self.plano.tarefa}.md"
        self._escrever(corpo_arquivo, corpo)
        consulta = self._correr(
            [gh, "pr", "list", "--head", self.plano.branch, "--state", "all",
             "--json", "number,url,state,isDraft"],
            cwd=self.plano.worktree,
            timeout=120,
        )
        try:
            prs = json.loads(consulta.stdout or "")
        except (TypeError, ValueError) as erro:
            raise ErroDeSessao(
                passo,
                "a consulta de PR devolveu JSON inválido",
                comando=f"gh pr list --head {self.plano.branch} --state all --json number,url,state,isDraft",
                detalhe="Confira o acesso ao GitHub e repita a abertura. Nenhum anúncio foi declarado.",
            ) from erro
        if not isinstance(prs, list) or len(prs) > 1:
            raise ErroDeSessao(
                passo,
                "o ramo tem zero ou mais de um PR aberto de forma inconclusiva",
                comando=f"gh pr list --head {self.plano.branch} --state all --json number,url,state,isDraft",
                detalhe="Confira os PRs deste ramo antes de repetir. A sessão não vai escolher um no escuro.",
            )
        if prs:
            pr = prs[0]
            if not isinstance(pr, dict):
                raise ErroDeSessao(passo, "o PR existente não tem identidade válida", detalhe="Confira gh pr list e repita.")
            numero = pr.get("number")
            if not isinstance(numero, int):
                raise ErroDeSessao(passo, "o PR existente não tem número válido", detalhe="Confira gh pr list e repita.")
            estado_pr = pr.get("state")
            if estado_pr not in {"OPEN", "MERGED", "CLOSED"}:
                raise ErroDeSessao(
                    passo,
                    "estado do PR existente não foi medido",
                    detalhe=f"PR #{numero} devolveu state={estado_pr!r}. Sem estado explícito, não retomo nem reabro tarefa.",
                )
            if estado_pr != "OPEN":
                tarefa = self.plano.tarefa_da_fila or self.plano.tarefa
                if estado_pr == "MERGED":
                    try:
                        import estado_da_entrega

                        medicao = estado_da_entrega.consultar_entrega(self.plano.raiz, numero)
                        estado_entrega = medicao.get("estado", "NÃO MEDIDO")
                    except Exception as erro:  # noqa: BLE001 - diagnóstico de abertura
                        estado_entrega = f"NÃO MEDIDO ({erro})"
                    detalhe = (
                        f"O PR #{numero} já foi integrado; preserve esta bancada e continue pela entrega existente. "
                        f"Estado da entrega: {estado_entrega}. "
                        f"Confira: python ci/esperar.py --entrega {numero}. "
                        f"Quando houver aceite publicado, reconcilie {tarefa} com o registro real medido pelo fluxo de entrega."
                    )
                else:
                    detalhe = (
                        f"O PR #{numero} está fechado sem merge para este ramo. "
                        "Ele não prova publicação nem aceite; confira a causa do fechamento antes de retomar."
                    )
                raise ErroDeSessao(
                    passo,
                    f"o ramo já tem o PR fechado #{numero}",
                    detalhe=detalhe,
                )
            self._pass(f"PR #{numero} já anuncia esta sessão")
            return

        status = self._correr(
            ["git", "status", "--porcelain=v1"], cwd=self.plano.worktree, timeout=120
        )
        linhas = [linha for linha in status.stdout.splitlines() if linha.strip()]
        eventos = []
        if self.plano.tarefa_da_fila:
            eventos = [
                linha[3:]
                for linha in linhas
                if linha[3:].replace("\\", "/").startswith("fila/eventos/")
                and self.plano.tarefa_da_fila in linha
            ]
        if eventos:
            self._commit_de_anuncio(passo, eventos)
        else:
            adiante = self._correr(
                ["git", "rev-list", "--count", f"origin/main..{self.plano.branch}"],
                cwd=self.plano.worktree,
                timeout=120,
            )
            if adiante.stdout.strip() == "0":
                self._commit_de_anuncio(passo, [])
        self._exigir(
            passo,
            ["git", "push", "-u", "origin", self.plano.branch],
            cwd=self.plano.worktree,
            timeout=600,
        )
        criado = self._exigir(
            passo,
            [gh, "pr", "create", "--draft", "--base", "main", "--head", self.plano.branch,
             "--title", titulo, "--body-file", str(corpo_arquivo)],
            cwd=self.plano.worktree,
            timeout=120,
        )
        achado = re.search(r"https://\S*?/pull/(\d+)", criado.stdout)
        if not achado:
            raise ErroDeSessao(
                passo,
                "o GitHub não devolveu a URL do PR draft",
                detalhe="Confira gh pr list e repita a abertura. Sem URL, o anúncio não foi comprovado.",
            )
        conferido = self._correr(
            [gh, "pr", "view", achado.group(1), "--json", "state,isDraft,headRefOid"],
            cwd=self.plano.worktree,
            timeout=120,
        )
        try:
            estado = json.loads(conferido.stdout or "")
        except (TypeError, ValueError) as erro:
            raise ErroDeSessao(passo, "a conferência do PR draft devolveu JSON inválido", detalhe="Confira gh pr view e repita.") from erro
        if estado.get("state") != "OPEN" or estado.get("isDraft") is not True:
            raise ErroDeSessao(passo, "o GitHub não confirmou um PR aberto em rascunho", detalhe="Confira gh pr view e corrija o estado antes de trabalhar.")
        self._pass(f"PR draft #{achado.group(1)} aberto e conferido")

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
        self._estado_git = "limpo"
        if sujo and self.plano.tarefa_da_fila:
            proprios = True
            for linha in sujo.splitlines():
                relativo = linha[3:]
                try:
                    if linha[:2] not in {"??", "A "} or not relativo.startswith("fila/eventos/") or ".." in Path(relativo).parts:
                        proprios = False
                        break
                    evento = json.loads((self.plano.worktree / relativo).read_text(encoding="utf-8"))
                    if not (evento.get("tarefa") == self.plano.tarefa_da_fila
                            and evento.get("quem") == self.plano.quem_no_balcao
                            and evento.get("evento") == "reivindicada"):
                        proprios = False
                        break
                except (OSError, ValueError, AttributeError):
                    proprios = False
                    break
            if proprios:
                self._estado_git = "comprovante da reivindicação pendente de commit"
                return
        if sujo:
            total = len(sujo.splitlines())
            self._estado_git = f"alterações preexistentes preservadas ({total})"

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
            self._pass(f"{alvo} materializado · git status: {self._estado_git}")
            return
        self._pass(f"{alvo} materializado (leia a entrada que casa com a sua tarefa)")

    def preparar_venv(self) -> None:
        passo = self._abrir(P_VENV)
        chave = identidade_do_venv(requisitos_do_venv(self.plano))
        self.plano = replace(self.plano, venv=Path.home() / ".sitesdoreino" / "venvs" / self.plano.celula / chave)
        with trava_de_ambiente(self.plano.venv.with_suffix(".lock")):
            if self._existe(self.plano.python_do_venv):
                self._pass("venv já existia; dependências serão conferidas pelo hash")
                return
            (self.plano.venv / ".instalado").unlink(missing_ok=True)
            self._exigir(passo, [sys.executable, "-m", "venv", str(self.plano.venv)],
                          cwd=self.plano.raiz, timeout=600)
            if not self._existe(self.plano.python_do_venv):
                raise ErroDeSessao(passo, "o interpretador não apareceu após criar o venv",
                                   detalhe=f"Confira {self.plano.python_do_venv} e repita a abertura.")
            self._pass(f"venv criado em {self.plano.venv}")

    def ambiente_instalado(self) -> bool:
        try:
            return self._existe(self.plano.python_do_venv) and (self.plano.venv / ".instalado").read_text(encoding="utf-8") == self.plano.venv.name
        except (OSError, UnicodeError):
            return False

    def instalar(self) -> None:
        passo = self._abrir(P_DEPS)
        chave = identidade_do_venv(requisitos_do_venv(self.plano))
        if self.plano.venv.name != chave:
            raise ErroDeSessao(passo, "dependências mudaram durante a preparação",
                               detalhe="Repita a abertura para preparar o novo ambiente.")
        marca = self.plano.venv / ".instalado"
        with trava_de_ambiente(self.plano.venv.with_suffix(".lock")):
            if self.ambiente_instalado():
                self._pass("dependências intocadas; ambiente reutilizado")
                return
            uv = self._localizar("uv")
            comando = ([uv, "pip", "install", "--python", str(self.plano.python_do_venv)]
                       if uv else [str(self.plano.python_do_venv), "-m", "pip", "install",
                                   "--disable-pip-version-check"])
            for requisitos in requisitos_do_venv(self.plano):
                comando += ["-r", str(requisitos)]
            comando += list(FERRAMENTAS_DE_PORTAO)
            self._exigir(passo, comando, cwd=self.plano.worktree, timeout=3600,
                          dica="Confira o acesso ao índice de pacotes e repita a abertura.")
            temporario = marca.with_suffix(f".{uuid.uuid4().hex}.tmp")
            try:
                self._escrever(temporario, chave)
                temporario.replace(marca)
            finally:
                temporario.unlink(missing_ok=True)
            self._pass(f"dependências de {self.plano.celula} instaladas ({chave[:8]})")

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
            comando += ["-p", f"127.0.0.1:{porta or ''}:{porta_interna}", imagem]
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

        with trava_de_ambiente(Path.home() / ".sitesdoreino" / "postgres-shared.lock", passo=passo):
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
                },
                sonda=["pg_isready", "-U", USUARIO_DO_BANCO],
                esperado="accepting connections",
            )
            consulta = [docker, "exec", self.plano.postgres, "psql", "-U", USUARIO_DO_BANCO,
                        "-d", "postgres", "-v", "ON_ERROR_STOP=1", "-tAc"]
            senha_arquivo = self.plano.scratch / ".senha-banco"
            try:
                senha = senha_arquivo.read_text(encoding="utf-8").strip()
            except FileNotFoundError:
                senha = ""
            papel = self._exigir(passo, [*consulta,
                f"SELECT 1 FROM pg_roles WHERE rolname = '{self.plano.banco}'"],
                cwd=self.plano.raiz).stdout.strip()
            if papel not in ("", "1") or (papel == "1" and not senha):
                raise ErroDeSessao(passo, "credencial da tarefa indisponível",
                                   detalhe="Preserve o banco existente e recupere o scratch da tarefa ou abra uma tarefa nova.")
            if not senha:
                senha = secrets.token_hex(24)
                self._escrever(senha_arquivo, senha)
            if not re.fullmatch(r"[a-f0-9]{48}", senha):
                raise ErroDeSessao(passo, "credencial local inválida", detalhe=f"Confira {senha_arquivo} e repita a abertura.")
            if papel != "1":
                self._exigir(passo, [*consulta,
                    f"""CREATE ROLE "{self.plano.banco}" LOGIN CREATEDB NOSUPERUSER NOCREATEROLE PASSWORD '{senha}'"""],
                    cwd=self.plano.raiz)
            self.plano = replace(self.plano, senha_banco=senha)
            dono = self._exigir(passo, [*consulta,
                f"SELECT pg_get_userbyid(datdba) FROM pg_database WHERE datname = '{self.plano.banco}'"],
                cwd=self.plano.raiz).stdout.strip()
            if dono and dono != self.plano.banco:
                raise ErroDeSessao(passo, "consulta do banco devolveu resposta inesperada",
                                   detalhe="O banco pertence a outro papel. Preserve os dados e abra uma tarefa nova.")
            if not dono:
                self._exigir(passo, [*consulta,
                    f'CREATE DATABASE "{self.plano.banco}" WITH OWNER "{self.plano.banco}"'],
                    cwd=self.plano.raiz)
            self._exigir(passo, [*consulta, f'REVOKE CONNECT ON DATABASE "{self.plano.banco}" FROM PUBLIC'],
                          cwd=self.plano.raiz)
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
            for nome in (self.plano.postgres, self.plano.redis):
                if not nome:
                    continue
                identidade = self._exigir(passo, [docker, "inspect", "--format", "{{.Id}} {{.Image}}", nome],
                                           cwd=self.plano.raiz).stdout.strip()
                if not re.fullmatch(r"[0-9a-f]{64} sha256:[0-9a-f]{64}", identidade):
                    raise ErroDeSessao(passo, "identidade do serviço indisponível",
                                       detalhe=f"Confira docker inspect {nome} e repita a abertura.")
                # Cada tarefa nasce com outro Redis, mas com a mesma imagem imutável.
                if nome == self.plano.postgres:
                    self._servicos["postgres"] = identidade
                else:
                    self._servicos["redis"] = identidade.split()[1]
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

    def ambiente_da_base(self) -> dict[str, str]:
        # Metadados do agente não entram no processo de teste nem na sua identidade.
        return {k: v for k, v in self._ambiente().items()
                if not k.startswith(("CODEX_", "CLAUDE_"))
                and k not in {"PYTEST_CURRENT_TEST", "PWD", "OLDPWD", "PYTHONPATH"}}

    def chave_do_baseline(self, git: str) -> tuple[str, Path, "Sessao"]:
        revisao = self._exigir(P_BASELINE, [git, "rev-parse", "origin/main"],
                               cwd=self.plano.worktree).stdout.strip()
        if not re.fullmatch(r"[0-9a-f]{40,64}", revisao):
            raise ErroDeSessao(P_BASELINE, "revisão da main inválida",
                               detalhe="Confira git fetch origin e repita a abertura.")
        def ler_da_base(arquivo):
            relativo = arquivo.relative_to(self.plano.worktree.resolve()).as_posix()
            return self._exigir(P_BASELINE, [git, "show", f"{revisao}:{relativo}"],
                                 cwd=self.plano.worktree).stdout.encode("utf-8")
        identidade_base = identidade_do_venv(requisitos_do_venv(self.plano), ler=ler_da_base)
        plano_base = replace(self.plano, venv=Path.home() / ".sitesdoreino" / "venvs" / self.plano.celula / identidade_base)
        base = Sessao(plano_base, correr=self._correr, escrever=self._escrever,
                      existe=self._existe, localizar=self._localizar, dormir=self._dormir,
                      log=lambda texto: self._nota(texto.replace("PASS", "BASE")))
        base._variaveis = {**self._variaveis, "SESSAO_VENV": str(plano_base.venv)}
        ambiente = base.ambiente_da_base()
        for chave in ("DATABASE_URL", "REDIS_STREAMS_URL", "HUEY_REDIS_URL",
                      "SESSAO_WORKTREE", "SESSAO_SCRATCH"):
            if chave in ambiente:
                ambiente[chave] = "isolado-por-tarefa"
        identidade = repr((revisao, str(plano_base.venv), sorted(ambiente.items()), sorted(self._servicos.items()), getattr(self, "_metodo_baseline", "`make ci`")))
        chave = hashlib.sha256(identidade.encode()).hexdigest()
        return revisao, Path.home() / ".sitesdoreino" / "baselines" / self.plano.celula / f"{chave}.json", base

    def rodar_baseline(self, git: str) -> str:
        passo = self._abrir(P_BASELINE)
        make = self._ferramenta("make", passo, "Instale GNU Make e repita a abertura para medir a base.")
        shell = None
        pytest_direto = False
        if platform.system() == "Windows":
            shell = self._localizar("sh")
            if not shell:
                caminho_git = self._correr([git, "--exec-path"], cwd=self.plano.worktree)
                if caminho_git.exit_code == 0 and caminho_git.stdout.strip():
                    for ancestral in Path(caminho_git.stdout.strip()).parents:
                        candidato = ancestral / "usr" / "bin" / "sh.exe"
                        if self._existe(candidato):
                            shell = candidato.as_posix()
                            break
            pytest_direto = not shell
        self._metodo_baseline = "`make ci`"
        if pytest_direto:
            self._metodo_baseline = "por pytest direto, sem lint"
        self._exigir_bancada_limpa(passo, git)
        revisao, cache, ambiente_base = self.chave_do_baseline(git)
        with trava_de_ambiente(cache.with_suffix(".lock"), passo=passo):
            if ambiente_base.ambiente_instalado():
                try:
                    prova = json.loads(cache.read_text(encoding="utf-8"))
                    texto = prova["saida"]
                    if (prova.get("metodo") == self._metodo_baseline and prova.get("shell") == shell
                            and prova["exit_code"] == 0 and isinstance(texto, str) and texto.strip()
                            and prova["sha256"] == hashlib.sha256(texto.encode()).hexdigest()):
                        self._escrever(self.plano.log_do_baseline, texto)
                        resumo = resumo_do_baseline(texto)
                        self._pass(f"baseline da BASE {revisao[:12]} reutilizado: {resumo}; log: {self.plano.log_do_baseline}")
                        return resumo
                except (OSError, ValueError, KeyError, TypeError):
                    self._nota("baseline sem evidência válida no cache; medindo a base")
            with tempfile.TemporaryDirectory(prefix="baseline-main-") as temporario:
                base = Path(temporario).resolve() / "arvore"
                self._exigir(passo, [git, "worktree", "add", "--detach", str(base), revisao],
                              cwd=self.plano.raiz, timeout=300)
                try:
                    ambiente_base.plano = replace(ambiente_base.plano, worktree=base)
                    if not ambiente_base.ambiente_instalado():
                        ambiente_base.preparar_venv()
                        ambiente_base.instalar()
                    env = ambiente_base.ambiente_da_base()
                    env["PYTHONPATH"] = str(base)
                    env["SESSAO_WORKTREE"] = str(base)
                    celula = base / "services" / self.plano.celula
                    comando = [make, "-C", str(celula), "ci"]
                    cwd = base
                    if shell:
                        env["SHELL"] = shell
                        comando.append(f"SHELL={shell}")
                        env["PATH"] = os.pathsep.join([str(ambiente_base.plano.bin_do_venv), str(Path(shell).parent), env.get("PATH", "")])
                    if pytest_direto:
                        comando = [str(ambiente_base.plano.python_do_venv), "-m", "pytest", "-q"]
                        cwd = celula
                    comando_exato = subprocess.list2cmdline(comando)
                    self._nota(f"{self._metodo_baseline}: {comando_exato} (cwd: {cwd})")
                    saida = self._correr(comando, cwd=cwd, env=env, timeout=3600)
                    texto = f"Método: {self._metodo_baseline}\nComando: {comando_exato}\nDiretório: {cwd}\n\n{saida.texto}"
                    self._escrever(self.plano.log_do_baseline, texto)
                    dica = "Confira o instrumento e repita a abertura."
                    if pytest_direto:
                        dica = "O pytest direto falhou; confira o Python e as dependências da célula e repita a abertura."
                    if saida.exit_code in SENTINELAS_DE_INSTRUMENTACAO:
                        raise ErroDeSessao(passo, f"o baseline NÃO chegou a rodar (exit {saida.exit_code})",
                                           detalhe=f"{dica}\n{recortar(saida.texto, 4000)}\nLog completo: {self.plano.log_do_baseline}", comando=comando_exato)
                    if saida.exit_code != 0:
                        raise ErroDeSessao(passo, f"o baseline da BASE {revisao} REPROVOU (exit {saida.exit_code})",
                                           detalhe=recortar(saida.texto, 4000) + f"\n{dica}\nLog completo: {self.plano.log_do_baseline}\nPare e reporte a falha da base.", comando=comando_exato, codigo=1)
                    medida = self._exigir(passo, [git, "rev-parse", "HEAD"], cwd=base).stdout.strip()
                    sujo = self._exigir(passo, [git, "status", "--porcelain"], cwd=base).stdout.strip()
                    if medida != revisao or sujo:
                        raise ErroDeSessao(passo, "o baseline alterou a revisão isolada",
                                           detalhe="A prova não será reutilizada. Confira o log e corrija a suíte da base.")
                finally:
                    if not base.is_relative_to(Path(temporario).resolve()):
                        raise ErroDeSessao(passo, "limpeza fora da bancada temporária recusada", detalhe=str(base))
                    self._exigir(passo, [git, "worktree", "remove", "--force", str(base)],
                                  cwd=self.plano.raiz, timeout=300)
            self._exigir_bancada_limpa(passo, git)
            if ambiente_base.ambiente_instalado() and saida.texto.strip():
                prova = json.dumps({"exit_code": 0, "saida": texto, "metodo": self._metodo_baseline, "shell": shell,
                                    "sha256": hashlib.sha256(texto.encode()).hexdigest()}, ensure_ascii=False)
                temporario = cache.with_suffix(f".{uuid.uuid4().hex}.tmp")
                try:
                    self._escrever(temporario, prova)
                    temporario.replace(cache)
                except OSError as erro:
                    self._nota(f"baseline medido, mas cache não foi gravado: {erro}")
                finally:
                    temporario.unlink(missing_ok=True)
            resumo = resumo_do_baseline(saida.texto)
            self._pass(f"{self._metodo_baseline} da BASE {revisao[:12]} = {resumo}; log completo: {self.plano.log_do_baseline}")
            return resumo

    # -- orquestração -------------------------------------------------------

    def rodar(self) -> str:
        """Abre ou retoma a bancada sob a mesma trava usada pelo executor."""
        ferramentas = self.conferir_pecas_locais()
        git = ferramentas["git"]
        self.conferir()
        self.buscar(git)
        gh = ferramentas["gh"]
        with trava_da_bancada(self.plano.worktree):
            retomada = self.retomar_entrega_integrada(git, gh)
            if retomada is not None:
                return retomada
            self.conferir_pecas_do_ambiente()
            self.preparar_worktree(git)
            registrar_estado_inicial(self.plano, git, correr=self._correr)
            if self.plano.tarefa_da_fila:
                self.pegar_a_tarefa()
            self.anunciar_pr(gh)
            self.gerar_indice(git)
            self.preparar_venv()
            self.instalar()
            if not self.plano.sobe_ambiente:
                self.escrever_env(0, 0)
                return declaracao(self.plano, resumo="", estado_git=self._estado_git)
            porta_pg, porta_redis = self.preparar_servicos()
            self.escrever_env(porta_pg, porta_redis)
            self.rodar_doctor()
            resumo = self.rodar_baseline(git)
            constituicao = f"constituicoes/AGENTS.{self.plano.celula}.md"
            if not self._existe(self.plano.worktree / constituicao):
                constituicao = ""
            return declaracao(
                self.plano, resumo=resumo, constituicao_da_celula=constituicao, estado_git=self._estado_git,
                metodo_baseline=self._metodo_baseline,
            )


# ---------------------------------------------------------------------------


def caminhos_da_tarefa(tarefa: dict, celulas: Sequence[str]) -> list[str]:
    """A fila aceita nomes de área/célula em toca e caminhos em toca/cria."""
    caminhos = []
    for campo in ("toca", "cria"):
        for valor in tarefa.get(campo) or []:
            caminho = valor.strip().replace("\\", "/")
            if caminho in celulas:
                caminho = f"services/{caminho}/"
            elif PADRAO_DE_NOME.fullmatch(caminho):
                caminho += "/"
            if caminho not in caminhos:
                caminhos.append(caminho)
    return caminhos


def contexto_direcionado(
    raiz: Path, *, objetivo: str, caminhos: Sequence[str], sintoma: str = "",
    aceite: Sequence[str] = (), restricoes: Sequence[str] = (),
    decisoes: Sequence[str] = (),
) -> str:
    """Consulta os mesmos gatilhos e sinais dos ganchos, sem catálogo próprio."""
    from licao_do_caminho import licoes_do_caminho
    from sino_das_armadilhas import carregar_sinais, reconhecer, resumo_da_armadilha

    globais = [nome for nome in ("CLAUDE.md", "AGENTS.md") if (raiz / nome).is_file()]
    limites = []
    if not globais:
        limites.append("Limitação: nenhuma instrução global AGENTS.md ou CLAUDE.md encontrada; "
                       "confira o checkout e as instruções da sessão antes de editar.")
    candidatas = [*globais, "CONSTITUICAO.md", "RITOS.md",
                  "docs/decisoes/RETROSPECTIVA-FASE-D.md"]
    for caminho in caminhos:
        partes = Path(caminho.replace("\\", "/")).parts
        if len(partes) > 1 and partes[0] == "services":
            candidatas.extend([f"constituicoes/AGENTS.{partes[1]}.md",
                                 f"services/{partes[1]}/LICOES.md"])
        alvo = raiz / caminho
        if alvo.resolve().is_relative_to(raiz.resolve()):
            inicio = alvo if alvo.is_dir() else alvo.parent
            for pasta in [inicio, *inicio.parents]:
                if not pasta.is_relative_to(raiz) or pasta == raiz:
                    break
                lei = pasta / "AGENTS.md"
                if lei.is_file():
                    candidatas.append(lei.relative_to(raiz).as_posix())
    candidatas = list(dict.fromkeys(candidatas))
    obrigatorias = [nome for nome in candidatas if (raiz / nome).is_file()]
    ausentes = [nome for nome in candidatas if nome not in obrigatorias]
    if ausentes:
        limites.append("Limitação: fontes de leitura ausentes neste checkout: " + ", ".join(ausentes)
                       + ". Confira o checkout antes de assumir que a preparação está completa.")
    linhas = ["CONTEXTO DIRECIONADO", f"Objetivo: {objetivo or 'não informado; complete o brief antes de editar'}",
              "Aceite: " + ("; ".join(aceite) or "não informado; confira o brief da tarefa"),
              "Caminhos: " + ", ".join(caminhos),
              "Restrições do brief: " + ("; ".join(restricoes) or "consulte as instruções obrigatórias"),
              "Decisões do brief: " + ("; ".join(decisoes) or "não informadas; consulte as fontes abaixo"),
              "Leituras obrigatórias: " + ", ".join(dict.fromkeys(obrigatorias)),
              "Não dispensa regras globais, segurança, governança nem as leituras obrigatórias."]
    linhas.extend(limites)
    if not (raiz / "armadilhas/INDICE.md").is_file():
        linhas.append("Índice de aprofundamento ausente: gere armadilhas/INDICE.md com "
                      "python ci/indice_de_armadilhas.py quando precisar da consulta integral.")
    achados = {}
    if sintoma:
        try:
            # O sino limita toques por comando. Consultar cada assinatura mantém
            # a correspondência dele e permite contar o truncamento desta resposta.
            for sinal in carregar_sinais(raiz / "armadilhas/SINAIS.json"):
                for item, _ in reconhecer(sintoma, [sinal]):
                    achados.setdefault(item["armadilha"], item)
        except (OSError, ValueError, TypeError, KeyError):
            linhas.append("Limitação: sinais indisponíveis; rode python ci/indice_de_armadilhas.py.")
    for caminho in caminhos:
        try:
            _, itens = licoes_do_caminho(raiz, caminho.replace("\\", "/"), todos=True)
            for item in itens:
                encontrado = achados.setdefault(item["armadilha"], item)
                if item.get("licao") and not encontrado.get("licao"):
                    encontrado["licao"] = item["licao"]
        except (OSError, ValueError, TypeError, KeyError):
            linhas.append("Limitação: gatilhos indisponíveis; rode python ci/indice_de_armadilhas.py.")
            break
    if not achados:
        linhas.append("Nenhuma lição recuperada; isso não significa ausência de restrições.")
    for item in achados.values():
        arquivo = item["arquivo"]
        linhas.append(f"Lição {item['armadilha']}: {item['titulo']} (origem: {arquivo})")
        resumo = resumo_da_armadilha(raiz / arquivo, arquivo, item.get("licao", ""))
        if resumo:
            linhas.append(resumo)
        else:
            linhas.append("Limitação: resumo indisponível; leia a origem completa.")
    linhas.append("Aprofundamento: arquivos de origem, armadilhas/INDICE.md e docs/decisoes/.")
    return "\n".join(linhas)


def medir_fase(plano: Plano, tentativa: str, fase: str, resultado: str, *, contexto_bytes=None, checkout: Path | None = None) -> None:
    """A mesma telemetria da casa; ausência de medição nunca vira zero."""
    try:
        from telemetria import registrar_fase
        onde = checkout or (plano.worktree if (plano.worktree / ".git").exists() else plano.raiz)
        saida = correr_de_verdade(["git", "-C", str(onde), "rev-parse", "HEAD"])
        commit = saida.stdout.strip() if saida.exit_code == 0 else None
        branch = correr_de_verdade(["git", "-C", str(onde), "rev-parse", "--abbrev-ref", "HEAD"])
        gravado = registrar_fase(fase, resultado, tarefa=plano.tarefa_da_fila or plano.branch,
            tentativa=tentativa, branch=branch.stdout.strip() if branch.exit_code == 0 else None, commit=commit,
            contexto_bytes=contexto_bytes, cwd=str(onde))
        if gravado is None:
            print("Medição de eficiência indisponível; cobertura incompleta nesta tentativa.")
    except Exception:  # noqa: BLE001 - instrumentação não autoriza nem impede a operação
        print("Medição de eficiência indisponível; os resultados operacionais continuam separados.")


def medir_tarefa_fase4(plano: Plano, tentativa: str, *, estado: str,
                       inicio: str, fim: str | None, pr: int | None,
                       commit: str | None = None, branch: str | None = None) -> None:
    if not plano.tarefa_da_fila:
        return
    try:
        import registrar_tarefa_fase4

        checkout = plano.worktree
        if commit is None:
            commit_resultado = correr_de_verdade(["git", "-C", str(checkout), "rev-parse", "HEAD"])
            commit = commit_resultado.stdout.strip() if commit_resultado.exit_code == 0 else ""
        if branch is None:
            branch_resultado = correr_de_verdade(["git", "-C", str(checkout), "rev-parse", "--abbrev-ref", "HEAD"])
            branch = branch_resultado.stdout.strip() if branch_resultado.exit_code == 0 else ""
        registrou = registrar_tarefa_fase4.registrar_execucao_fase4(
            checkout, tarefa=plano.tarefa_da_fila, tentativa=tentativa,
            branch=branch, commit=commit, estado=estado, inicio=inicio,
            fim=fim, pr=pr,
        )
        if not registrou and registrar_tarefa_fase4.classificacao_da_tarefa(checkout, plano.tarefa_da_fila):
            print("Medição Fase 4 indisponível; confira o caderno privado e repita a coleta.")
    except Exception:
        print("Medição Fase 4 indisponível; os resultados operacionais continuam separados.")


def emitir_contexto(plano: Plano, tentativa: str, pacote: str, *, checkout=None) -> None:
    """Emite e conta os mesmos bytes, inclusive no Windows, sem converter linhas."""
    dados = (pacote + "\n").encode("utf-8")
    sys.stdout.flush()
    sys.stdout.buffer.write(dados)
    sys.stdout.buffer.flush()
    medir_fase(plano, tentativa, "contexto", "concluido", contexto_bytes=len(dados), checkout=checkout)


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
    parser.add_argument("--contexto", action="store_true", help="só recupera contexto no checkout indicado, sem preparar ambiente")
    parser.add_argument("--caminho", action="append", default=[], help="caminho afetado, repetível")
    parser.add_argument("--sintoma", default="", help="sintoma para a busca existente por sinal")
    parser.add_argument("--aceite", action="append", default=[], help="critério de aceite do brief, repetível")
    parser.add_argument("--restricao", action="append", default=[], help="restrição do brief, repetível")
    parser.add_argument("--decisao", action="append", default=[], help="referência de decisão do brief, repetível")
    return parser


def raiz_do_clone(checkout: Path) -> Path:
    """A abertura usa o clone principal mesmo quando parte de uma bancada."""
    if not (checkout / ".git").is_file():
        return checkout
    comando = ["git", "-C", str(checkout), "worktree", "list", "--porcelain"]
    saida = correr_de_verdade(comando)
    bancadas = [linha.removeprefix("worktree ") for linha in saida.stdout.splitlines()
                if linha.startswith("worktree ")]
    if saida.exit_code != 0 or not bancadas:
        raise ErroDeInstrumentacao(
            "não consegui localizar o clone principal desta bancada",
            "Confira git worktree list --porcelain antes de repetir a abertura. "
            "Nenhum arquivo foi alterado pela conferência.")
    principal = raiz_declarada(Path(bancadas[0]))
    if not (principal / ".git").is_dir():
        raise ErroDeInstrumentacao(
            "o Git não apontou um clone principal reconhecível",
            "Confira os vínculos das bancadas com git worktree list --porcelain. "
            "Não remova a bancada para corrigir o vínculo.")
    return principal


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    bruto = list(sys.argv[1:] if argv is None else argv)
    if bruto and bruto[0] == "executar":
        try:
            return executar_na_sessao(bruto[1:])
        except ErroDeSessao as erro:
            print(erro.render(), file=sys.stderr)
            return erro.codigo
    if bruto and bruto[0] == "abrir":
        bruto = bruto[1:]
    args = construir_parser().parse_args(bruto)
    try:
        raiz = raiz_declarada(Path(args.raiz)) if args.raiz else raiz_do_repo()
        if not args.contexto:
            raiz = raiz_do_clone(raiz)
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

    caminhos = args.caminho or [f"services/{celula}/" if plano.sobe_ambiente else f"{celula}/"]
    def contexto(onde):
        objetivo, aceite, origem = args.frase, args.aceite, []
        caminhos_do_contexto = caminhos
        limitacao = ""
        if tarefa_da_fila:
            from fila import carregar_tarefas
            erros = []
            tarefas = carregar_tarefas(onde, erros)
            tarefa = tarefas.get(tarefa_da_fila)
            if tarefa and not erros:
                objetivo = objetivo or tarefa["titulo"]
                aceite = aceite or [tarefa["evidencia_exigida"]]
                origem = [f"fila/tarefas/{tarefa['arquivo']}.json"]
                if not args.caminho:
                    caminhos_do_contexto = caminhos_da_tarefa(tarefa, celulas) or caminhos
            else:
                limitacao = "\nLimitação: tarefa da fila indisponível ou inválida; confira o brief original."
        return contexto_direcionado(onde, objetivo=objetivo, caminhos=caminhos_do_contexto,
            sintoma=args.sintoma, aceite=aceite, restricoes=args.restricao,
            decisoes=[*args.decisao, *origem]) + limitacao
    tentativa = uuid.uuid4().hex
    if args.contexto:
        pacote = contexto(raiz)
        emitir_contexto(plano, tentativa, pacote, checkout=raiz)
        return 0
    print(cabecalho(plano))
    if args.conferir:
        print("--conferir: nada foi criado. Tire a flag para executar o plano acima.")
        return 0

    medir_fase(plano, tentativa, "abertura", "iniciado")

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

    detalhes = []
    log_abertura = plano.scratch / f"abertura-{tentativa}.log"
    try:
        abertura = Sessao(plano, log=detalhes.append)
        texto = abertura.rodar()
        plano = abertura.plano
    except ErroDeSessao as erro:
        escrever_de_verdade(log_abertura, "\n".join(detalhes + [erro.render()]))
        print(erro.render())
        print(f"Log detalhado: {log_abertura}")
        medir_fase(plano, tentativa, "abertura", "falhou")
        return erro.codigo
    escrever_de_verdade(log_abertura, "\n".join(detalhes))
    print(f"Preparação concluída; log detalhado: {log_abertura}")
    medir_fase(plano, tentativa, "abertura", "concluido")
    print(moldura_da_declaracao(texto))
    entrega_integrada = "já integrado" in texto and "Estado da entrega:" in texto
    if entrega_integrada:
        print("Próxima ação autorizada: acompanhar a entrega integrada pelo comando acima; não execute o brief novamente sem nova tarefa.")
        return 0
    inicio_fase4 = datetime.now(timezone.utc).isoformat()
    medir_tarefa_fase4(
        plano, tentativa, estado="pendente", inicio=inicio_fase4,
        fim=None, pr=None,
    )
    if plano.sobe_ambiente:
        print(f"O .env da sessão ficou em {plano.arquivo_env} (fora do worktree).")
        print("A prova da base está no log; mudanças da tarefa ainda exigem validação própria.")
    pacote = contexto(plano.worktree)
    emitir_contexto(plano, tentativa, pacote)
    print("Próxima ação autorizada: conferir as leituras obrigatórias e executar o brief; revisão, integração e publicação não foram realizadas.")
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
    raise SystemExit(sair_do_processo(_blindar("sessao", main)()))
