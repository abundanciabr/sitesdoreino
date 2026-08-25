"""A suíte do bootstrap de sessão (`ci/sessao.py`).

Três camadas, e a divisão é deliberada:

1. **Decisão pura** — derivação de nomes/portas, validação de argumentos,
   conteúdo do `.env`, texto da Declaração. Nada disso toca disco, rede ou
   Docker: é função pura, e o script foi desenhado assim justamente para poder
   ser provado sem criar container nenhum.

2. **Fail-closed passo a passo** — com `correr`, `existe`, `localizar` e
   `dormir` injetados, cada passo é forçado a devolver != 0 e a suíte exige que
   o script PARE ali, nomeie o passo e **não produza a Declaração**. Guarda que
   não fica vermelha quando deveria é decoração.

3. **Guardas de fronteira** — o `ci/doctor.py` continua read-only e o Makefile
   continua sem lógica. As duas coisas são fáceis de desfazer sem querer.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import sessao  # noqa: E402

CELULAS = [
    "alunos",
    "catalogo",
    "checkout",
    "funil",
    "identidade",
    "leads",
    "mensageria",
    "pagamentos",
    "quiz",
    "sugestoes",
]


def _n(caminho: Path | str) -> str:
    return os.path.normcase(os.path.normpath(str(caminho)))


def plano_de_teste(**extra) -> sessao.Plano:
    padrao = dict(
        raiz=Path("C:/repo") if os.name == "nt" else Path("/repo"),
        celulas=CELULAS,
        usa_redis=True,
        base_de_scratch=Path("C:/scratch") if os.name == "nt" else Path("/scratch"),
    )
    padrao.update(extra)
    celula = padrao.pop("celula", "quiz")
    tarefa = padrao.pop("tarefa", "fuso-horario")
    return sessao.derivar_plano(celula, tarefa, **padrao)


# ---------------------------------------------------------------------------
# 1. Decisão pura — derivação
# ---------------------------------------------------------------------------


def test_deriva_worktree_branch_e_containers_a_partir_de_celula_e_tarefa():
    plano = plano_de_teste()
    assert plano.worktree.name == "wt-quiz-fuso-horario"
    assert plano.branch == "agent/quiz/fuso-horario"
    assert plano.postgres == "sessao-quiz-pg"
    assert plano.redis == "sessao-quiz-redis"
    assert plano.banco == "quiz_db"
    # O worktree nasce IRMÃO do clone principal, nunca dentro dele (RITOS §1).
    assert not sessao.esta_dentro(plano.worktree, plano.raiz)


def test_venv_e_env_ficam_fora_do_worktree():
    """`armadilhas/008`: o .gitignore das células não lista `.venv/`."""
    plano = plano_de_teste()
    assert not sessao.esta_dentro(plano.venv, plano.worktree)
    assert not sessao.esta_dentro(plano.arquivo_env, plano.worktree)


def test_scratch_padrao_e_absoluto_e_no_formato_da_maquina():
    """`armadilhas/006`: `/tmp` escrito à mão não é o `/tmp` desta máquina."""
    base = sessao.base_de_scratch_padrao()
    assert base.is_absolute()
    if os.name == "nt":
        assert base.drive, "no Windows o scratch precisa de letra de unidade"
        assert not str(base).startswith("/")


def test_porta_derivada_da_celula_nunca_colide_com_as_ja_tomadas():
    """55432 é a fixa da partida rápida; 55440/55441 são dos compose de dev."""
    portas = {plano_de_teste(celula=c).porta_postgres for c in CELULAS}
    assert portas.isdisjoint({55432, 55440, 55441})
    # 55450–55459 está reservada aos testes do próprio bootstrap
    assert portas.isdisjoint(set(range(55450, 55460)))


def test_portas_nao_colidem_entre_celulas():
    """O motivo do requisito: em lote, cinco despachos rodam ao mesmo tempo."""
    pg = [plano_de_teste(celula=c).porta_postgres for c in CELULAS]
    redis = [plano_de_teste(celula=c).porta_redis for c in CELULAS]
    assert len(set(pg)) == len(CELULAS)
    assert len(set(redis)) == len(CELULAS)
    assert set(pg).isdisjoint(redis)


def test_porta_nao_depende_da_ordem_em_que_a_lista_chega():
    a = sessao.derivar_porta("quiz", CELULAS, 55460, 55479)
    b = sessao.derivar_porta("quiz", list(reversed(CELULAS)), 55460, 55479)
    assert a == b


def test_faixa_de_portas_esgotada_e_erro_declarado_e_nao_um_numero_errado():
    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.derivar_porta("sugestoes", CELULAS, 55460, 55462)
    assert "faixa de portas" in erro.value.resumo


def test_celula_sem_redis_nao_ganha_container_de_redis():
    plano = plano_de_teste(usa_redis=False)
    assert plano.redis == ""
    assert plano.porta_redis == 0
    assert plano.usa_redis is False


def test_celula_usa_redis_le_o_codigo_e_nao_uma_tabela(tmp_path: Path):
    seca = tmp_path / "seca"
    (seca / "config").mkdir(parents=True)
    (seca / "config" / "settings.py").write_text("DATABASES = {}", encoding="utf-8")
    molhada = tmp_path / "molhada"
    (molhada / "config").mkdir(parents=True)
    (molhada / "config" / "huey.py").write_text(
        'os.environ.get("HUEY_REDIS_URL")', encoding="utf-8"
    )
    assert sessao.celula_usa_redis(seca) is False
    assert sessao.celula_usa_redis(molhada) is True


# ---------------------------------------------------------------------------
# 1b. Decisão pura — validação ANTES de qualquer efeito
# ---------------------------------------------------------------------------


def test_celula_inexistente_recusa_com_a_lista_do_manifesto():
    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.validar_celula("naoexiste", CELULAS)
    assert "não existe" in erro.value.resumo
    assert "pagamentos" in erro.value.detalhe  # a lista real, não "veja o manifesto"


@pytest.mark.parametrize(
    "ruim",
    [
        "",
        "   ",
        "Minha Tarefa",  # espaço e maiúscula
        "com/barra",  # quebraria agent/<celula>/<tarefa>
        "com\\contrabarra",
        "..",  # subiria um diretório
        "../fuga",
        "MAIUSCULA",  # Docker aceita, git aceita, diretório do Windows confunde
        "acentuação",
        "-comeca-com-hifen",
        "termina-com-hifen-",
        "dois--hifens",
        "com:dois-pontos",
        "com~til",
        "com^acento",
        "com@{chave",
        "com.ponto",  # `.lock`/`..` no git; ponto não entra na gramática comum
        "x" * 41,
    ],
)
def test_nome_que_quebraria_branch_ou_container_e_recusado(ruim: str):
    with pytest.raises(sessao.ErroDeSessao):
        sessao.validar_nome(ruim, "TAREFA")


@pytest.mark.parametrize("bom", ["a", "quiz", "fuso-horario", "evo-31", "x1-y2-z3"])
def test_nomes_legitimos_passam(bom: str):
    assert sessao.validar_nome(bom, "TAREFA") == bom


def test_tarefa_invalida_para_antes_de_derivar_qualquer_caminho():
    """A recusa acontece na derivação — nada é criado nem consultado."""
    with pytest.raises(sessao.ErroDeSessao) as erro:
        plano_de_teste(tarefa="Minha Tarefa")
    assert "TAREFA" in erro.value.resumo
    assert "agent/<celula>/<tarefa>" in erro.value.detalhe


def test_manifesto_ausente_e_erro_e_nao_lista_vazia(tmp_path: Path):
    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.celulas_declaradas(tmp_path)
    assert "não encontrado" in erro.value.resumo
    assert "não ter a lista" in erro.value.detalhe


def test_manifesto_do_repositorio_de_verdade_declara_as_celulas_em_disco():
    raiz = CI.parent
    declaradas = sessao.celulas_declaradas(raiz)
    em_disco = sorted(p.name for p in (raiz / "services").iterdir() if p.is_dir())
    assert declaradas == em_disco


# ---------------------------------------------------------------------------
# 1c. Decisão pura — o conteúdo do .env
# ---------------------------------------------------------------------------


def test_env_traz_as_tres_variaveis_que_todo_make_ci_local_precisa():
    plano = plano_de_teste()
    variaveis = sessao.variaveis_de_sessao(
        plano, porta_postgres=55468, porta_redis=16468
    )
    assert variaveis["PYTHONUTF8"] == "1"
    assert variaveis["DJANGO_SECRET_KEY"] == "ci-apenas-nunca-em-producao"
    assert variaveis["DATABASE_URL"] == "postgres://dev:dev@localhost:55468/quiz_db"


def test_env_usa_a_porta_REAL_do_container_e_nao_a_derivada():
    """Container reusado publica a porta dele; o .env segue o mundo, não o plano."""
    plano = plano_de_teste()
    variaveis = sessao.variaveis_de_sessao(plano, porta_postgres=55999, porta_redis=1)
    assert ":55999/" in variaveis["DATABASE_URL"]
    assert plano.porta_postgres != 55999


def test_env_so_declara_redis_quando_a_celula_usa():
    com = sessao.variaveis_de_sessao(plano_de_teste(), porta_postgres=1, porta_redis=2)
    sem = sessao.variaveis_de_sessao(plano_de_teste(usa_redis=False), porta_postgres=1)
    assert com["REDIS_STREAMS_URL"] == "redis://localhost:2/0"
    assert com["HUEY_REDIS_URL"] == "redis://localhost:2/1"
    assert "REDIS_STREAMS_URL" not in sem


def test_env_carrega_o_scratch_absoluto_no_formato_da_maquina():
    plano = plano_de_teste()
    variaveis = sessao.variaveis_de_sessao(plano, porta_postgres=1, porta_redis=2)
    assert variaveis["SESSAO_SCRATCH"] == str(plano.scratch)
    assert Path(variaveis["SESSAO_SCRATCH"]).is_absolute()
    assert variaveis["SESSAO_VENV"] == str(plano.venv)


def test_env_cita_todo_valor_com_aspas_simples():
    """Sem aspas, `sh` come a contrabarra de `C:\\Users\\...` na hora do source."""
    plano = plano_de_teste()
    variaveis = sessao.variaveis_de_sessao(plano, porta_postgres=1, porta_redis=2)
    texto = sessao.renderizar_env(plano, variaveis)
    for chave, valor in variaveis.items():
        assert f"{chave}='{valor}'" in texto
    for linha in texto.splitlines():
        if linha.startswith("#") or not linha.strip():
            continue
        assert linha.split("=", 1)[1].startswith("'")
        assert linha.endswith("'")


def test_env_recusa_valor_que_teria_de_ser_escapado():
    plano = plano_de_teste()
    with pytest.raises(sessao.ErroDeSessao):
        sessao.renderizar_env(plano, {"X": "tem 'aspas' dentro"})


def test_env_avisa_que_nao_deve_ser_comitado():
    plano = plano_de_teste()
    texto = sessao.renderizar_env(
        plano, sessao.variaveis_de_sessao(plano, porta_postgres=1, porta_redis=2)
    )
    assert "NÃO comite" in texto


# ---------------------------------------------------------------------------
# 1d. Decisão pura — a Declaração e os parsers
# ---------------------------------------------------------------------------


def test_declaracao_traz_todas_as_pecas_que_o_RITOS_1_exige():
    plano = plano_de_teste(frase="fechar a peça C3 do PLANO-10X")
    texto = sessao.declaracao(
        plano, resumo="6 passed", constituicao_da_celula="constituicoes/AGENTS.quiz.md"
    )
    assert texto.startswith("Li CONSTITUICAO.md e constituicoes/AGENTS.quiz.md.")
    assert "Worktree: wt-quiz-fuso-horario." in texto
    assert "Branch: agent/quiz/fuso-horario." in texto
    assert "git status: limpo." in texto
    assert "6 passed" in texto
    assert "Tarefa: fechar a peça C3 do PLANO-10X." in texto
    assert texto.count("\n") == 0  # uma linha só, para colar


def test_declaracao_sem_constituicao_de_celula_cita_o_RITOS():
    plano = plano_de_teste(celula="identidade")
    texto = sessao.declaracao(plano, resumo="verde")
    assert texto.startswith("Li CONSTITUICAO.md e RITOS.md §1.")


def test_declaracao_sem_frase_deixa_um_buraco_visivel_em_vez_de_inventar():
    texto = sessao.declaracao(plano_de_teste(), resumo="verde")
    assert "<uma frase" in texto


@pytest.mark.parametrize(
    "saida,esperado",
    [
        ("6 passed in 3.21s", "6 passed"),
        ("1 passed, 2 skipped in 1s\n270 passed in 28.95s", "270 passed"),
        ("✅ quiz: Definição de Pronto local atingida", "verde"),
        ("", "verde"),
    ],
)
def test_resumo_do_baseline_le_o_que_esta_la_e_nao_inventa(saida, esperado):
    assert sessao.resumo_do_baseline(saida) == esperado


@pytest.mark.parametrize(
    "saida,esperado",
    [
        ("0.0.0.0:55468", 55468),
        ("0.0.0.0:55468\n[::]:55468", 55468),
        ("[::]:16468", 16468),
    ],
)
def test_porta_publicada_le_a_saida_do_docker_port(saida, esperado):
    assert sessao.porta_publicada(saida) == esperado


def test_porta_publicada_ilegivel_e_erro_e_nao_um_palpite():
    with pytest.raises(sessao.ErroDeSessao) as erro:
        sessao.porta_publicada("")
    assert "palpite" in erro.value.detalhe


def test_estado_do_container_distingue_ausente_de_parado():
    saida = "sessao-quiz-pg\trunning\noutro-pg\texited"
    assert sessao.estado_do_container(saida, "sessao-quiz-pg") == "running"
    assert sessao.estado_do_container(saida, "outro-pg") == "exited"
    assert sessao.estado_do_container(saida, "sessao-leads-pg") == ""
    assert sessao.estado_do_container("", "sessao-quiz-pg") == ""


def test_worktree_ja_existe_le_a_saida_porcelain():
    alvo = Path("C:/x/wt-quiz-a") if os.name == "nt" else Path("/x/wt-quiz-a")
    porcelain = (
        f"worktree {alvo.as_posix()}\nHEAD abc\nbranch refs/heads/agent/quiz/a\n"
    )
    assert sessao.worktree_ja_existe(porcelain, alvo) is True
    assert sessao.worktree_ja_existe("", alvo) is False
    assert sessao.worktree_ja_existe("worktree /outro/lugar\n", alvo) is False


# ---------------------------------------------------------------------------
# 2. Fail-closed — o mundo inteiro dublado
# ---------------------------------------------------------------------------


class MundoFalso:
    """Um mundo de mentira: registra chamadas, e falha onde eu mandar falhar.

    `falhar` é {fragmento-do-comando: exit_code}. Tudo que não casar sai 0 com
    a stdout plausível daquele comando — é assim que dá para provar que o
    script para NO passo escolhido, e só nele.
    """

    def __init__(self, plano: sessao.Plano, falhar: dict | None = None, **saidas):
        self.plano = plano
        self.falhar = dict(falhar or {})
        self.saidas = saidas
        self.chamadas: list[str] = []
        self.escritos: dict[str, str] = {}
        self.log: list[str] = []
        self.dormiu = 0.0
        self.existentes = {
            _n(plano.raiz / "services" / plano.celula),
            _n(plano.raiz / "services" / plano.celula / "requirements.txt"),
            _n(plano.worktree / "constituicoes" / f"AGENTS.{plano.celula}.md"),
        }

    # -- as quatro injeções ------------------------------------------------

    def correr(self, comando, *, cwd=None, env=None, timeout=1800) -> sessao.Saida:
        comando = [str(c) for c in comando]
        linha = " ".join(comando)
        self.chamadas.append(linha)
        for fragmento, codigo in self.falhar.items():
            if fragmento in linha:
                return sessao.Saida(comando, codigo, "", f"falha simulada: {fragmento}")
        if "worktree add" in linha:
            self.existentes.add(_n(self.plano.worktree / ".git"))
        if "-m venv" in linha:
            self.existentes.add(_n(self.plano.python_do_venv))
        return sessao.Saida(comando, 0, self._stdout(linha), "")

    def existe(self, caminho) -> bool:
        return _n(caminho) in self.existentes

    def localizar(self, nome: str) -> str | None:
        return (
            None
            if nome in self.saidas.get("sem_ferramenta", ())
            else f"/usr/bin/{nome}"
        )

    def dormir(self, segundos: float) -> None:
        self.dormiu += segundos

    def escrever(self, caminho: Path, texto: str) -> None:
        self.escritos[_n(caminho)] = texto

    def anotar(self, texto: str = "") -> None:
        self.log.append(str(texto))

    # -- as saídas plausíveis ----------------------------------------------

    def _stdout(self, linha: str) -> str:
        if "worktree list" in linha:
            return self.saidas.get("worktree_list", "")
        if "rev-parse --abbrev-ref" in linha:
            return self.saidas.get("branch_atual", self.plano.branch)
        if "docker info" in linha:
            return "29.7.2"
        if "docker ps" in linha:
            return self.saidas.get("docker_ps", "")
        if "docker port" in linha:
            nome = linha.split()[2]
            porta = (
                self.plano.porta_postgres
                if nome == self.plano.postgres
                else self.plano.porta_redis
            )
            return f"0.0.0.0:{porta}"
        if "pg_isready" in linha:
            return "accepting connections"
        if "redis-cli ping" in linha:
            return "PONG"
        if "shutil.which" in linha:
            return str(self.plano.bin_do_venv / "python")
        if linha.startswith("/usr/bin/make"):
            return self.saidas.get("baseline", "6 passed in 1.23s\n✅ quiz: ok")
        if "status --porcelain" in linha:
            return self.saidas.get("porcelain", "")
        return ""

    # -- montagem -----------------------------------------------------------

    def sessao(self) -> sessao.Sessao:
        return sessao.Sessao(
            self.plano,
            correr=self.correr,
            escrever=self.escrever,
            existe=self.existe,
            localizar=self.localizar,
            dormir=self.dormir,
            log=self.anotar,
        )


def test_caminho_feliz_termina_na_declaracao_e_cria_tudo_uma_vez():
    mundo = MundoFalso(plano_de_teste(), falhar={"rev-parse --verify": 1})
    texto = mundo.sessao().rodar()
    assert texto.startswith("Li CONSTITUICAO.md e constituicoes/AGENTS.quiz.md.")
    assert "6 passed" in texto
    juntas = "\n".join(mundo.chamadas)
    assert "fetch origin" in juntas
    assert (
        "worktree add" in juntas and "-b agent/quiz/fuso-horario origin/main" in juntas
    )
    assert "-m venv" in juntas
    assert "pip install" in juntas and "PyYAML==6.0.2" in juntas
    assert "docker run -d --name sessao-quiz-pg" in juntas
    assert "docker run -d --name sessao-quiz-redis" in juntas
    assert "ci/doctor.py" in juntas
    assert _n(mundo.plano.arquivo_env) in mundo.escritos


def test_segunda_execucao_nao_recria_nada_idempotencia():
    plano = plano_de_teste()
    porcelain = (
        f"worktree {plano.worktree.as_posix()}\nbranch refs/heads/{plano.branch}\n"
    )
    mundo = MundoFalso(
        plano,
        worktree_list=porcelain,
        docker_ps=f"{plano.postgres}\trunning\n{plano.redis}\trunning",
    )
    mundo.existentes.add(_n(plano.worktree / ".git"))
    mundo.existentes.add(_n(plano.python_do_venv))
    texto = mundo.sessao().rodar()
    juntas = "\n".join(mundo.chamadas)
    assert "worktree add" not in juntas
    assert "-m venv" not in juntas
    assert "docker run" not in juntas
    assert "docker start" not in juntas
    assert "6 passed" in texto  # e mesmo assim o baseline foi medido de novo
    assert any("já existia" in linha for linha in mundo.log)


def test_container_parado_e_reiniciado_e_nao_recriado():
    plano = plano_de_teste(usa_redis=False)
    mundo = MundoFalso(
        plano,
        falhar={"rev-parse --verify": 1},
        docker_ps=f"{plano.postgres}\texited",
    )
    mundo.sessao().rodar()
    juntas = "\n".join(mundo.chamadas)
    assert f"docker start {plano.postgres}" in juntas
    assert "docker run" not in juntas


@pytest.mark.parametrize(
    "fragmento,passo_esperado",
    [
        ("fetch origin", "git fetch origin"),
        ("worktree add", "worktree da sessão"),
        ("-m venv", "venv FORA do worktree"),
        ("pip install", "dependências da célula"),
        ("docker info", "serviços em Docker"),
        ("docker run", "serviços em Docker"),
        ("ci/doctor.py", "ci/doctor.py"),
    ],
)
def test_passo_que_falha_para_o_script_ali_e_nao_imprime_a_declaracao(
    fragmento, passo_esperado
):
    mundo = MundoFalso(plano_de_teste(), falhar={"rev-parse --verify": 1, fragmento: 3})
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.passo == passo_esperado
    assert erro.value.codigo == 2
    # o comando exato de reprodução viaja junto com o erro
    assert fragmento.split()[0] in erro.value.comando
    texto = erro.value.render()
    assert "PAROU POR SEGURANÇA" in texto
    assert "Li CONSTITUICAO.md" not in texto
    assert "Li CONSTITUICAO.md" not in "\n".join(mundo.log)


def test_falha_num_passo_nao_deixa_os_passos_seguintes_rodarem():
    mundo = MundoFalso(plano_de_teste(), falhar={"pip install": 1})
    with pytest.raises(sessao.ErroDeSessao):
        mundo.sessao().rodar()
    juntas = "\n".join(mundo.chamadas)
    assert "docker" not in juntas
    assert "doctor.py" not in juntas
    assert mundo.escritos == {}


@pytest.mark.parametrize("codigo_do_make", [1, 2])
def test_baseline_vermelho_e_FAIL_exit_1_e_manda_parar_e_reportar(codigo_do_make):
    """O GNU Make devolve 2 quando a receita reprova — e 2 aqui não é ERROR.

    Foi medido ao vivo: `black --check` sai 1, o make traduz para 2. Chamar
    isso de "não consegui medir" mandaria quem lê investigar o instrumento em
    vez do código que reprovou.
    """
    mundo = MundoFalso(
        plano_de_teste(),
        falhar={"rev-parse --verify": 1, "/usr/bin/make": codigo_do_make},
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.passo == "baseline: make ci da célula"
    assert erro.value.codigo == 1
    assert "REPROVOU" in erro.value.resumo
    assert "Pare e reporte" in erro.value.detalhe


@pytest.mark.parametrize("sentinela", sorted(sessao.SENTINELAS_DE_INSTRUMENTACAO))
def test_baseline_que_nem_rodou_e_ERROR_exit_2_e_nao_FAIL(sentinela):
    """Não conseguir medir nunca pode chegar disfarçado de reprovação."""
    mundo = MundoFalso(
        plano_de_teste(), falhar={"rev-parse --verify": 1, "/usr/bin/make": sentinela}
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.codigo == 2
    assert "NÃO chegou a rodar" in erro.value.resumo


def test_worktree_sujo_depois_do_baseline_recusa_a_declaracao():
    mundo = MundoFalso(
        plano_de_teste(),
        falhar={"rev-parse --verify": 1},
        porcelain=" M services/quiz/config/settings.py",
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.codigo == 1
    assert "git status: limpo" in erro.value.detalhe


def test_worktree_existente_em_OUTRA_branch_recusa_em_vez_de_misturar_despachos():
    plano = plano_de_teste()
    porcelain = f"worktree {plano.worktree.as_posix()}\n"
    mundo = MundoFalso(plano, worktree_list=porcelain, branch_atual="agent/quiz/outra")
    mundo.existentes.add(_n(plano.worktree / ".git"))
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.passo == "worktree da sessão"
    assert "agent/quiz/outra" in erro.value.resumo


def test_comando_que_sai_0_sem_criar_o_artefato_e_falso_verde_e_e_barrado():
    """`git worktree add` exit 0 e nenhum worktree: exit 0 não é evidência."""

    class SemArtefato(MundoFalso):
        def correr(self, comando, *, cwd=None, env=None, timeout=1800):
            linha = " ".join(str(c) for c in comando)
            self.chamadas.append(linha)
            if "worktree add" in linha:
                return sessao.Saida([str(c) for c in comando], 0, "", "")
            return super().correr(comando, cwd=cwd, env=env, timeout=timeout)

    mundo = SemArtefato(plano_de_teste(), falhar={"rev-parse --verify": 1})
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "não apareceu" in erro.value.resumo


def test_docker_desligado_da_mensagem_acionavel_e_nao_traceback():
    mundo = MundoFalso(
        plano_de_teste(), falhar={"rev-parse --verify": 1, "docker info": 1}
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "motor não responde" in erro.value.resumo
    assert "ABRA O DOCKER DESKTOP" in erro.value.detalhe
    assert "idempotente" in erro.value.detalhe


def test_docker_ausente_do_PATH_para_com_instrucao_em_vez_de_seguir():
    mundo = MundoFalso(
        plano_de_teste(), falhar={"rev-parse --verify": 1}, sem_ferramenta=("docker",)
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "`docker` não está no PATH" in erro.value.resumo


def test_make_ausente_para_no_baseline_e_nao_finge_verde():
    mundo = MundoFalso(
        plano_de_teste(), falhar={"rev-parse --verify": 1}, sem_ferramenta=("make",)
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert erro.value.passo == "baseline: make ci da célula"
    assert "não medir não é medir verde" in erro.value.detalhe


def test_python_do_PATH_fora_do_venv_e_barrado_armadilha_014():
    """Portão que roda com o Python errado fica verde e não mede nada."""

    class PythonErrado(MundoFalso):
        def _stdout(self, linha: str) -> str:
            if "shutil.which" in linha:
                return r"C:\Python312\python.exe"
            return super()._stdout(linha)

    mundo = PythonErrado(plano_de_teste(), falhar={"rev-parse --verify": 1})
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "NÃO é o do venv" in erro.value.resumo
    assert "armadilhas/014" in erro.value.detalhe


def test_sonda_do_servico_que_nunca_responde_impede_o_baseline():
    mundo = MundoFalso(
        plano_de_teste(), falhar={"rev-parse --verify": 1, "pg_isready": 1}
    )
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "não ficou pronto" in erro.value.resumo
    assert mundo.dormiu > 0
    assert "doctor.py" not in "\n".join(mundo.chamadas)


def test_venv_dentro_do_worktree_e_recusado_antes_de_agir():
    plano = plano_de_teste()
    dentro = sessao.Plano(**{**plano.__dict__, "venv": plano.worktree / ".venv"})
    mundo = MundoFalso(dentro)
    with pytest.raises(sessao.ErroDeSessao) as erro:
        mundo.sessao().rodar()
    assert "DENTRO do worktree" in erro.value.resumo
    assert "armadilhas/008" in erro.value.detalhe
    assert not any("fetch" in c for c in mundo.chamadas)


# ---------------------------------------------------------------------------
# 3. Guardas de fronteira
# ---------------------------------------------------------------------------


def _comandos_de(texto: str) -> list[list[str]]:
    """Os comandos que o módulo EXECUTA, lidos da árvore sintática.

    Busca textual não serve aqui: o `ci/doctor.py` cita `pip install -r ...`
    numa mensagem de ajuda, e citar não é executar. O que interessa é a lista
    que vai para o subprocesso — variável vira o próprio nome (`docker`), o
    resto vira `?`.
    """
    import ast

    comandos = []
    for no in ast.walk(ast.parse(texto)):
        if not isinstance(no, ast.List) or not no.elts:
            continue
        tokens = []
        for elemento in no.elts:
            if isinstance(elemento, ast.Constant) and isinstance(elemento.value, str):
                tokens.append(elemento.value)
            elif isinstance(elemento, ast.Name):
                tokens.append(elemento.id)
            else:
                tokens.append("?")
        comandos.append(tokens)
    return comandos


def _executa(texto: str, par: tuple[str, ...]) -> bool:
    alvo = list(par)
    for tokens in _comandos_de(texto):
        for i in range(len(tokens) - len(alvo) + 1):
            if tokens[i : i + len(alvo)] == alvo:
                return True
    return False


MUTACOES = (
    ("docker", "run"),
    ("worktree", "add"),
    ("-m", "venv"),
    ("pip", "install"),
)


def test_doctor_continua_read_only_e_nao_virou_instalador():
    """Regra 1 do despacho: ninguém pode criar container rodando `make doctor`."""
    texto = (CI / "doctor.py").read_text(encoding="utf-8")
    for par in MUTACOES:
        assert not _executa(texto, par), f"ci/doctor.py passou a executar `{par}`"
    assert "import sessao" not in texto
    assert "read-only" in texto


def test_a_guarda_do_doctor_tem_dentes():
    """A mesma varredura ACHA as mutações em ci/sessao.py — senão não prova nada."""
    texto = (CI / "sessao.py").read_text(encoding="utf-8")
    for par in MUTACOES:
        assert _executa(texto, par), f"a varredura não achou `{par}` em ci/sessao.py"


def test_makefile_tem_o_alvo_sessao_e_ele_nao_contem_logica():
    texto = (CI.parent / "Makefile").read_text(encoding="utf-8")
    assert "sessao:" in texto
    assert "$(PYTHON) ci/sessao.py" in texto
    assert "make sessao CELULA=" in texto  # a linha da ajuda
    corpo = texto.split("sessao:", 1)[1].split("\n\n", 1)[0]
    for proibido in ("docker", "git worktree", "pip install"):
        assert proibido not in corpo, f"o Makefile ganhou lógica: {proibido}"


def test_bootstrap_e_alvo_explicito_e_nunca_padrao_de_outro():
    """`sessao` não pode ser dependência de `ci`, `doctor` ou do alvo padrão."""
    texto = (CI.parent / "Makefile").read_text(encoding="utf-8")
    for linha in texto.splitlines():
        if linha.startswith(("ci:", "doctor:", "ajuda:", "muralhas:", "testador:")):
            assert "sessao" not in linha
