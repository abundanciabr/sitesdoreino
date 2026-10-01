"""O mesmo roteiro de manutenção alcança o módulo certo após o corte."""

from pathlib import Path
import os
import subprocess


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "infra" / "operacao-aplicacao.sh"
BASH = "C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else "bash"


def executar(trecho: str) -> str:
    programa = (
        f'. "{HELPER}"\n'
        'docker() { printf "<%s>" "$@"; }\n'
        f'{trecho}\n'
    )
    resultado = subprocess.run([BASH, "-c", programa], capture_output=True, text=True)
    assert resultado.returncode == 0, resultado.stderr
    return resultado.stdout


def test_comando_e_variavel_vão_ao_modulo_na_aplicacao():
    saida = executar(
        'aplicacao_ativa() { return 0; }; '
        'comando_servico gamificacao reconciliar_perfis --consertar; '
        'env_servico gamificacao SITE_ID'
    )
    assert '<exec><-T><aplicacao><python><-m><config.comando><gamificacao><reconciliar_perfis><--consertar>' in saida
    assert '<config.comando><gamificacao><env><SITE_ID>' in saida
    assert '<exec><-T><gamificacao>' not in saida


def test_override_do_gerador_do_quiz_fica_no_contexto_certo():
    saida = executar(
        'aplicacao_ativa() { return 0; }; '
        'comando_servico_env quiz ALVO_ID=42 ALVO_HOST=exemplo.test -- shell -c "print(42)"'
    )
    assert '<-e><ALVO_ID=42><-e><ALVO_HOST=exemplo.test><aplicacao>' in saida
    assert '<config.comando><--env><ALVO_ID><--env><ALVO_HOST><quiz><shell><-c><print(42)>' in saida


def test_topologia_recuperada_usa_comando_legado():
    saida = executar(
        'aplicacao_ativa() { return 1; }; '
        'comando_servico forum semear_areas'
    )
    assert '<exec><-T><forum><python><manage.py><semear_areas>' in saida
