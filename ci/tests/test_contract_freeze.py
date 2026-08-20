"""TESTAR O TESTADOR — [INV-CI01] portão crítico é fail-closed.

Estes testes não checam o código da plataforma: checam o INSTRUMENTO que checa
a plataforma. Cada um corresponde a uma forma conhecida (ou plausível) de fazer
o freeze imprimir sucesso sem ter comparado contrato nenhum.

O caso nº 1 da lista é a ferida original, em forma de regressão permanente:
ferramenta ausente ⇒ as duas pontas viram vazio ⇒ `vazio == vazio` ⇒ "OK".
Aqui isso é ERROR, e um ERROR que não pode ser confundido com FAIL.

A suíte valida SEMÂNTICA (estado + exit code), não formato de mensagem.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

import contract_freeze
from _nucleo import ErroDeInstrumentacao, Estado, Relatorio, Resultado, raiz_do_repo
from conftest import AUTENTICACAO_MINIMA, BASH, CONTRATO_MINIMO, RepoFalso

CI = Path(__file__).resolve().parents[1]
RAIZ_REAL = CI.parent


def _rodar(repo: RepoFalso, celula: str | None = "falsa", **kwargs) -> Relatorio:
    return contract_freeze.rodar(
        celula=celula, raiz=repo.raiz, manifesto=repo.manifesto, **kwargs
    )


# ---------------------------------------------------------------------------
# 1 e 2 — os controles positivo e negativo
# ---------------------------------------------------------------------------


def test_contrato_identico_passa(celula_ok: RepoFalso) -> None:
    relatorio = _rodar(celula_ok)
    assert relatorio.estado is Estado.PASS
    assert relatorio.exit_code == 0


def test_contrato_divergente_reprova(repo: RepoFalso) -> None:
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    vivo = {**CONTRATO_MINIMO, "info": {"title": "Falsa API", "version": "2.0.0"}}
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador_que_imprime("falsa", vivo),
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.FAIL
    assert relatorio.exit_code == 1
    # FAIL precisa vir com a evidência que o sustenta, não só com o veredito.
    assert "2.0.0" in relatorio.resultados[0].detalhe


# ---------------------------------------------------------------------------
# 3 a 5, 9 e 10 — instrumentação quebrada: sempre ERROR, jamais PASS
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "corpo_do_exportador,motivo",
    [
        ("import sys; sys.exit(1)", "exportador falha com exit code"),
        ("pass", "exportador silencioso: exit 0 e stdout vazio"),
        ("print('<html>nao sou json</html>')", "exportador cospe conteúdo inválido"),
        ("import sys; sys.stdout.write('null')", "exportador devolve documento nulo"),
        ("import sys; sys.stdout.write('{}')", "exportador devolve objeto sem OpenAPI"),
    ],
)
def test_exportador_quebrado_da_error(
    repo: RepoFalso, corpo_do_exportador: str, motivo: str
) -> None:
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador("falsa", corpo_do_exportador),
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR, motivo
    assert relatorio.exit_code == 2


def test_ferramenta_ausente_da_error(repo: RepoFalso) -> None:
    """A ferida original: o exportador não existe como executável."""
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": ["interpretador-que-nao-existe", "manage.py"],
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR
    assert relatorio.exit_code == 2


def test_vazio_contra_vazio_nunca_e_pass(repo: RepoFalso) -> None:
    """O falso positivo em estado puro: os DOIS lados vazios.

    Era assim que `diff <(norm A) <(norm B)` declarava igualdade quando python3
    não existia. Um portão que compara dois nadas mediu nada.
    """
    repo.criar_celula("falsa")
    repo.congelar("falsa", "")
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador("falsa", "pass"),
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR
    assert relatorio.estado is not Estado.PASS


# ---------------------------------------------------------------------------
# 6 a 8 — congelado ausente, malformado, e o SKIP declarado
# ---------------------------------------------------------------------------


def test_contrato_obrigatorio_ausente_da_error(repo: RepoFalso) -> None:
    """Arquivo ausente NÃO é 'nada a checar' quando o manifesto o exige."""
    repo.criar_celula("falsa")
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_MINIMO),
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR
    assert relatorio.exit_code == 2


@pytest.mark.parametrize(
    "conteudo",
    [
        "isto: [nao é yaml valido\n",
        "   \n\n",
        "# só comentário\n",
        "- uma\n- lista\n",
        "openapi: 3.1.0\n",  # sem 'paths': não tem forma de OpenAPI
    ],
)
def test_congelado_malformado_da_error(repo: RepoFalso, conteudo: str) -> None:
    repo.criar_celula("falsa")
    repo.congelar("falsa", conteudo)
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_MINIMO),
            }
        }
    )
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR


def test_not_applicable_declarado_da_skip(repo: RepoFalso) -> None:
    repo.criar_celula("esqueleto")
    repo.declarar(
        {
            "esqueleto": {
                "freeze": "not-applicable",
                "reason": "célula só expõe /healthz",
            }
        }
    )
    relatorio = _rodar(repo, celula="esqueleto")
    assert relatorio.estado is Estado.SKIP
    assert relatorio.exit_code == 0
    assert "healthz" in relatorio.resultados[0].resumo


def test_not_applicable_sem_motivo_da_error(repo: RepoFalso) -> None:
    """SKIP sem motivo declarado é SKIP inferido — e SKIP inferido é proibido."""
    repo.criar_celula("esqueleto")
    repo.declarar({"esqueleto": {"freeze": "not-applicable"}})
    relatorio = _rodar(repo, celula="esqueleto")
    assert relatorio.estado is Estado.ERROR


def test_not_applicable_com_contrato_em_disco_da_error(repo: RepoFalso) -> None:
    """Declaração e realidade discordando não pode passar despercebido."""
    repo.criar_celula("esqueleto")
    repo.congelar("esqueleto", CONTRATO_MINIMO)
    repo.declarar(
        {"esqueleto": {"freeze": "not-applicable", "reason": "supostamente sem API"}}
    )
    relatorio = _rodar(repo, celula="esqueleto")
    assert relatorio.estado is Estado.ERROR


# ---------------------------------------------------------------------------
# Manifesto — a declaração explícita não pode divergir do disco em silêncio
# ---------------------------------------------------------------------------


def test_celula_nao_declarada_da_error(celula_ok: RepoFalso) -> None:
    """Célula nova em services/ que ninguém declarou não nasce sem veredito."""
    celula_ok.criar_celula("recem-nascida")
    relatorio = _rodar(celula_ok)
    assert relatorio.estado is Estado.ERROR


def test_contrato_orfao_da_error(celula_ok: RepoFalso) -> None:
    celula_ok.congelar("fantasma", CONTRATO_MINIMO)
    relatorio = _rodar(celula_ok)
    assert relatorio.estado is Estado.ERROR


@pytest.mark.parametrize(
    "escrever",
    [
        lambda p: None,  # manifesto ausente
        lambda p: p.write_text("{ isto nao e json", encoding="utf-8"),
        lambda p: p.write_text("{}", encoding="utf-8"),  # sem 'celulas'
        lambda p: p.write_text('{"celulas": {}}', encoding="utf-8"),  # vazio
    ],
)
def test_manifesto_invalido_da_error(repo: RepoFalso, escrever) -> None:
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    escrever(repo.manifesto)
    relatorio = _rodar(repo)
    assert relatorio.estado is Estado.ERROR


def test_celula_desconhecida_na_linha_de_comando_da_error(celula_ok: RepoFalso) -> None:
    relatorio = _rodar(celula_ok, celula="celula-que-nao-existe")
    assert relatorio.estado is Estado.ERROR


# ---------------------------------------------------------------------------
# Resolução de raiz — sem git, sem marcas, sem PASS
# ---------------------------------------------------------------------------


def test_raiz_nao_resolvida_da_error(tmp_path: Path) -> None:
    """Um diretório sem as marcas da raiz nunca é aceito como raiz.

    A segunda falha da ferida original: sem git, a resolução caía para "." e o
    contrato "não era encontrado" — o que o script lia como "nada a checar".
    """
    vazio = tmp_path / "lugar-nenhum"
    vazio.mkdir()
    relatorio = contract_freeze.rodar(celula="falsa", raiz=vazio)
    assert relatorio.estado is Estado.ERROR
    assert relatorio.exit_code == 2


def test_raiz_declarada_sem_marcas_nao_sobe_ate_outra_raiz(tmp_path: Path) -> None:
    """Buraco encontrado no red team da própria implementação, agora fechado.

    `--raiz <dir sem marcas>` subia a árvore, encontrava o repositório de
    verdade e media OUTRA coisa — devolvendo PASS para um caminho que nunca foi
    inspecionado. Raiz declarada agora é verificada, não descoberta.
    """
    dentro_do_repo_real = RAIZ_REAL / "ci" / "tests"
    relatorio = contract_freeze.rodar(celula="catalogo", raiz=dentro_do_repo_real)
    assert relatorio.estado is Estado.ERROR

    fora = tmp_path / "sem-marcas"
    fora.mkdir()
    assert contract_freeze.rodar(celula="catalogo", raiz=fora).estado is Estado.ERROR


def test_celula_nova_sem_makefile_ainda_precisa_ser_declarada(
    celula_ok: RepoFalso,
) -> None:
    """Diretório novo em services/ conta como célula mesmo antes do Makefile."""
    (celula_ok.raiz / "services" / "acabou-de-nascer").mkdir(parents=True)
    assert _rodar(celula_ok).estado is Estado.ERROR


def test_raiz_sem_git_ainda_resolve_por_marcas(celula_ok: RepoFalso) -> None:
    """Sem git a raiz ainda é PROVADA por marcas — não chutada."""
    resolvida = raiz_do_repo(celula_ok.raiz)
    assert resolvida == celula_ok.raiz.resolve()


def test_raiz_real_do_repositorio_e_resolvida() -> None:
    assert raiz_do_repo(CI) == RAIZ_REAL.resolve()


# ---------------------------------------------------------------------------
# O núcleo — agregação e exit codes
# ---------------------------------------------------------------------------


def test_relatorio_vazio_e_error() -> None:
    """Um portão que não mediu nada não provou nada. Este é o INV-CI01 nu."""
    assert Relatorio("nada").estado is Estado.ERROR
    assert Relatorio("nada").exit_code == 2


@pytest.mark.parametrize(
    "estados,esperado",
    [
        ([Estado.PASS, Estado.SKIP], Estado.PASS),
        ([Estado.PASS, Estado.FAIL], Estado.FAIL),
        ([Estado.FAIL, Estado.ERROR], Estado.ERROR),
        ([Estado.SKIP, Estado.ERROR], Estado.ERROR),
    ],
)
def test_pior_estado_vence(estados: list[Estado], esperado: Estado) -> None:
    r = Relatorio("agregado")
    for i, e in enumerate(estados):
        r.registrar(Resultado(f"c{i}", e, ""))
    assert r.estado is esperado


def test_exit_codes_distinguem_violacao_de_impossibilidade() -> None:
    assert Estado.PASS.exit_code == 0
    assert Estado.SKIP.exit_code == 0
    assert Estado.FAIL.exit_code == 1
    assert Estado.ERROR.exit_code == 2


# ---------------------------------------------------------------------------
# Idempotência e ausência de efeito colateral
# ---------------------------------------------------------------------------


def test_freeze_e_read_only_e_idempotente(celula_ok: RepoFalso) -> None:
    def impressao_digital() -> dict[str, bytes]:
        return {
            str(p.relative_to(celula_ok.raiz)): p.read_bytes()
            for p in sorted(celula_ok.raiz.rglob("*"))
            if p.is_file()
        }

    antes = impressao_digital()
    primeiro = _rodar(celula_ok).estado
    segundo = _rodar(celula_ok).estado
    assert primeiro is segundo is Estado.PASS
    assert impressao_digital() == antes, "o freeze não pode escrever no repositório"


# ---------------------------------------------------------------------------
# O wrapper de shell — a camada que já produziu o falso positivo
# ---------------------------------------------------------------------------

WRAPPER = CI / "freeze-de-contrato.sh"
bash_disponivel = pytest.mark.skipif(
    BASH is None, reason="nenhum bash utilizável foi encontrado neste ambiente"
)


def _shell(args: list[str], env: dict[str, str] | None = None):
    return subprocess.run(
        [BASH, str(WRAPPER), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
        timeout=300,
        check=False,
    )


@bash_disponivel
def test_wrapper_sem_python_no_path_da_error(tmp_path: Path) -> None:
    """Sem interpretador, o wrapper morre com ERROR — não com sucesso.

    É a ferida original reproduzida na camada de shell: era exatamente aqui que
    `python3: command not found` convivia com `✅ Freeze de contrato: OK`.
    """
    proc = _shell(["catalogo"], env={**os.environ, "PATH": str(tmp_path)})
    assert proc.returncode == 2, proc.stdout + proc.stderr
    assert "ERROR" in proc.stdout
    assert "RESULTADO  PASS" not in proc.stdout


@bash_disponivel
def test_wrapper_delega_e_preserva_exit_code(celula_ok: RepoFalso) -> None:
    proc = _shell(
        [
            "falsa",
            "--raiz",
            str(celula_ok.raiz),
            "--manifesto",
            str(celula_ok.manifesto),
        ]
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "PASS" in proc.stdout


@bash_disponivel
def test_wrapper_propaga_fail_como_exit_1(repo: RepoFalso) -> None:
    """FAIL do Python precisa chegar ao shell como 1, não virar 0 nem 2."""
    repo.criar_celula("falsa")
    repo.congelar("falsa", CONTRATO_MINIMO)
    vivo = {**CONTRATO_MINIMO, "info": {"title": "Falsa API", "version": "7.7.7"}}
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "sonda_auth": repo.sonda_auth("falsa", AUTENTICACAO_MINIMA),
                "exportador": repo.exportador_que_imprime("falsa", vivo),
            }
        }
    )
    proc = _shell(
        ["falsa", "--raiz", str(repo.raiz), "--manifesto", str(repo.manifesto)]
    )
    assert proc.returncode == 1, proc.stdout + proc.stderr


def test_scripts_de_ci_nao_escondem_erro() -> None:
    """Nenhum portão em ci/ pode voltar a mascarar falha com `|| true`.

    §12 da auditoria, mecanizado: o padrão que transforma "o comando falhou" em
    "não havia nada a fazer" não volta ao diretório dos portões sem que um teste
    fique vermelho.
    """
    proibidos = ("|| true", "|| echo .", "set +e")
    ofensas = []
    for script in sorted(CI.glob("*.sh")):
        texto = script.read_text(encoding="utf-8")
        for linha_n, linha in enumerate(texto.splitlines(), 1):
            if linha.lstrip().startswith("#"):
                continue
            for padrao in proibidos:
                if padrao in linha:
                    ofensas.append(f"{script.name}:{linha_n}: {linha.strip()}")
    assert not ofensas, "padrão de falso positivo em portão de CI:\n" + "\n".join(
        ofensas
    )


# ---------------------------------------------------------------------------
# O manifesto REAL contra o repositório REAL
# ---------------------------------------------------------------------------


def test_manifesto_real_e_coerente_com_o_repositorio() -> None:
    """Não roda exportador: só confere declaração × disco.

    É o teste que fica vermelho quando alguém cria uma célula, apaga um
    contrato ou introduz contrato numa célula declarada sem ele.
    """
    raiz = raiz_do_repo(CI)
    celulas = contract_freeze.carregar_manifesto(
        raiz / contract_freeze.MANIFESTO_PADRAO
    )
    contract_freeze.auditar_manifesto(raiz, celulas)


def test_manifesto_real_declara_todas_as_celulas_em_disco() -> None:
    raiz = raiz_do_repo(CI)
    celulas = contract_freeze.carregar_manifesto(
        raiz / contract_freeze.MANIFESTO_PADRAO
    )
    # Mesma regra da auditoria: qualquer diretório em services/ é célula a
    # declarar. Se o teste usasse um critério mais frouxo que o portão, ele
    # poderia ficar verde para um estado que o portão reprova.
    em_disco = {
        d.name
        for d in (raiz / "services").iterdir()
        if d.is_dir() and not d.name.startswith((".", "__"))
    }
    assert em_disco == set(celulas)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(pytest.main([__file__, "-q"] + sys.argv[1:]))


# ---------------------------------------------------------------------------
# Manifesto bidirecional — disco <-> declaração, nos dois sentidos
# ---------------------------------------------------------------------------


def test_celula_declarada_que_nao_existe_no_disco_da_error(
    celula_ok: RepoFalso,
) -> None:
    """(A) Declaração órfã: o manifesto aponta para uma célula que sumiu.

    Sem isto, o manifesto envelheceria exibindo SKIPs de células removidas —
    exatamente o SKIP fossilizado que ele existe para impedir.
    """
    celulas = json.loads(celula_ok.manifesto.read_text(encoding="utf-8"))["celulas"]
    celulas["celula-que-foi-removida"] = {
        "freeze": "not-applicable",
        "reason": "declarada, mas o diretório não existe mais",
    }
    celula_ok.declarar(celulas)
    assert _rodar(celula_ok, celula=None).estado is Estado.ERROR


def test_required_sem_congelado_e_pego_pela_auditoria(repo: RepoFalso) -> None:
    """(C) required + congelado ausente é ERROR já na auditoria, não só na
    comparação — é a auditoria que o `doctor` consulta."""
    repo.criar_celula("falsa")
    repo.declarar(
        {
            "falsa": {
                "freeze": "required",
                "frozen": "contracts/falsa.openapi.yaml",
                "exportador": repo.exportador_que_imprime("falsa", CONTRATO_MINIMO),
            }
        }
    )
    celulas = contract_freeze.carregar_manifesto(repo.manifesto)
    with pytest.raises(contract_freeze.ErroDeInstrumentacao):
        contract_freeze.auditar_manifesto(repo.raiz, celulas)


# ---------------------------------------------------------------------------
# Detecção de escopo — a medição que decide o que a CI vai testar
# ---------------------------------------------------------------------------


def test_deteccao_de_celulas_falha_fechada() -> None:
    """Base inválida é ERROR, jamais lista vazia.

    Era este o bypass do workflow: `git diff | ... || true` devolvia string
    vazia quando o git falhava, e vazio significava "nenhuma célula tocada".
    """
    import ci as runner

    with pytest.raises(ErroDeInstrumentacao):
        runner.celulas_tocadas(RAIZ_REAL, "origin/ref-que-nao-existe")


def test_deteccao_de_celulas_com_base_valida_mede() -> None:
    import ci as runner

    tocadas = runner.celulas_tocadas(RAIZ_REAL, "origin/main")
    assert isinstance(tocadas, list)
    assert all(isinstance(c, str) and c for c in tocadas)


# ---------------------------------------------------------------------------
# Blindagem de fronteira — bug nosso não pode virar veredito sobre o código
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("modulo", ["contract_freeze", "ci", "doctor"])
def test_excecao_inesperada_vira_error_e_nao_fail(modulo: str) -> None:
    """Exceção não tratada dentro do portão sai com 2 (ERROR), não 1 (FAIL).

    Sem a blindagem, um TypeError nosso derrubava o processo com o exit 1 do
    Python — que neste repositório significa "violação detectada". Um bug do
    instrumento chegava disfarçado de veredito sobre o código sob teste.
    """
    import importlib

    alvo = importlib.import_module(modulo)

    def estoura() -> int:
        raise TypeError("bug dentro do próprio portão")

    assert alvo._blindar(modulo, estoura)() == 2


def test_blindagem_nao_engole_saida_normal() -> None:
    assert contract_freeze._blindar("x", lambda: 0)() == 0
    assert contract_freeze._blindar("x", lambda: 1)() == 1
