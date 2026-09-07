"""O vigia do pouso, provado com inventários montados à mão — sem rede.

POR QUE SEM REDE. O vigia decide quem é ACUSADO de estar esquecido. Um teste
que pergunta ao GitHub só prova que o GitHub respondeu hoje: ele não consegue
montar, na hora em que eu preciso, um PR que esteja verde há exatamente sete
horas, outro verde há uma, um rascunho e um com check ainda rodando. Aqui cada
inventário é escrito à mão, e um deles é a fotografia REAL de 07/09/2026, o dia
em que a TAR-167 foi feita — três PRs verdes e esquecidos ao mesmo tempo.

O QUE ESTES TESTES PROTEGEM, em uma frase: **o PR verde que ninguém pediu para
pousar é denunciado, e nenhum outro é.** A segunda metade dessa frase vale
tanto quanto a primeira: um vigia que grita por qualquer PR aberto ensina a
casa a ignorar o grito, e aí ele deixa de servir para o caso que importa.

A RÉGUA DA `armadilhas/374` está aplicada de propósito: nenhum valor esperado
aqui é importado do módulo sob julgamento. As horas, os motivos e os números
estão escritos por extenso. Um teste que assere contra a própria constante que
deveria vigiar sobrevive à mutação dela, e vira decoração.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

import pytest

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import vigia_do_pouso  # noqa: E402

AGORA = dt.datetime(2026, 9, 7, 3, 0, 0, tzinfo=dt.timezone.utc)

# Os caminhos com dono, escritos aqui e não lidos do CODEOWNERS pelo mesmo
# motivo das horas: o teste precisa de uma expectativa própria.
DONOS = ("contracts/", "infra/", "ci/", ".github/", "RITOS.md")


def _quando(horas_atras: float) -> str:
    return (AGORA - dt.timedelta(hours=horas_atras)).strftime("%Y-%m-%dT%H:%M:%SZ")


def pr(
    numero: int,
    *,
    verde_ha: float | None = 8,
    etiquetas: tuple[str, ...] = (),
    rascunho: bool = False,
    conclusao: str = "SUCCESS",
    checks: tuple[str, ...] = ("muralhas", "ci-celula-gate", "espelho-da-main"),
    arquivos: tuple[str, ...] = ("services/forum/apps/core/views.py",),
    sem_hora: bool = False,
    titulo: str = "um pull request qualquer",
) -> dict:
    """Um PR no formato cru do `gh pr list --json ...`.

    O padrão é o caso da doença — verde, sem etiqueta, velho —, e cada teste
    muda UMA coisa. Assim a diferença entre denunciar e dispensar fica visível
    na chamada, e não escondida num dicionário grande.
    """
    rollup = []
    for nome in checks:
        entrada: dict[str, object] = {
            "__typename": "CheckRun",
            "name": nome,
            "status": "COMPLETED" if conclusao != "IN_PROGRESS" else "IN_PROGRESS",
            "conclusion": conclusao if conclusao != "IN_PROGRESS" else None,
        }
        if not sem_hora and verde_ha is not None:
            entrada["completedAt"] = _quando(verde_ha)
            entrada["startedAt"] = _quando(verde_ha + 0.05)
        rollup.append(entrada)
    return {
        "number": numero,
        "title": titulo,
        "url": f"https://github.com/abundanciabr/sitesdoreino/pull/{numero}",
        "isDraft": rascunho,
        "createdAt": _quando((verde_ha or 0) + 0.5),
        "labels": [{"name": n} for n in etiquetas],
        "files": [{"path": p} for p in arquivos],
        "statusCheckRollup": rollup,
    }


def motivo(pr_dict: dict, horas: int = 6) -> str:
    return vigia_do_pouso.julgar(pr_dict, AGORA, DONOS, horas).motivo


# ---------------------------------------------------------------------------
# A ACUSAÇÃO — o caso que a TAR-167 existe para pegar.
# ---------------------------------------------------------------------------
def test_pr_verde_sem_pedido_de_pouso_e_mais_velho_que_a_paciencia_e_denunciado():
    vereditos = vigia_do_pouso.varrer([pr(741, verde_ha=7)], AGORA, DONOS, 6)

    assert len(vereditos) == 1
    acusado = vereditos[0]
    assert acusado.esquecido, (
        "um PR verde há 7 h, sem a etiqueta `pousar`, com a paciência em 6 h, "
        f"tinha de ser denunciado — veio '{acusado.motivo}'"
    )
    assert acusado.motivo == "esquecido"
    assert 6.9 < acusado.horas_de_verde < 7.1


def test_o_verde_se_conta_do_check_e_nao_da_abertura_do_pr():
    """Um PR aberto há dias e reverdecido agora está VIVO, não esquecido.

    É a diferença entre "está aberto há muito tempo" (não é defeito: gente
    empurra código) e "está VERDE e parado há muito tempo" (é o defeito). O
    push novo derruba os checks e reinicia o relógio sozinho.
    """
    antigo = pr(900, verde_ha=0.5)
    antigo["createdAt"] = _quando(72)

    assert motivo(antigo) == "recente"


def test_a_denuncia_diz_o_numero_o_instante_e_o_comando():
    vereditos = vigia_do_pouso.varrer([pr(741, verde_ha=9)], AGORA, DONOS, 6)
    corpo = vigia_do_pouso.corpo_da_denuncia(vereditos, 6)

    assert "#741" in corpo
    # AGORA é 07/09 03:00 UTC; nove horas antes é 06/09 18:00 UTC.
    assert "06/09 18:00 UTC" in corpo
    assert "python ci/mergear.py 741 --pousar" in corpo, (
        "a denúncia precisa trazer o comando pronto: um aviso que não diz o "
        "que fazer vira aviso que ninguém segue"
    )


def test_o_corpo_nao_muda_so_porque_o_relogio_andou():
    """O quadro só muda quando a LISTA muda — nunca só porque o tempo passou.

    Medido na primeira passagem real (07/09/2026, run 34081787250): com as
    horas decorridas na tabela, o corpo mudava a cada varredura e a issue era
    reescrita doze vezes por dia com a mesma notícia. "Reescrevo quando muda"
    virava "reescrevo sempre", e a promessa quebrava em silêncio.
    """
    inventario = [pr(741, verde_ha=9)]

    agora = vigia_do_pouso.corpo_da_denuncia(
        vigia_do_pouso.varrer(inventario, AGORA, DONOS, 6), 6
    )
    tres_horas_depois = vigia_do_pouso.corpo_da_denuncia(
        vigia_do_pouso.varrer(
            inventario, AGORA + dt.timedelta(hours=3), DONOS, 6
        ),
        6,
    )

    assert agora == tres_horas_depois, (
        "o corpo mudou sem a lista mudar — a issue seria reescrita a cada "
        "passagem do relógio, e o aviso vira ruído"
    )


def test_denuncia_sem_ninguem_esquecido_e_recusada():
    """Issue que acusa lista vazia é ruído, e ruído mata este vigia."""
    vereditos = vigia_do_pouso.varrer([pr(1, verde_ha=1)], AGORA, DONOS, 6)

    with pytest.raises(vigia_do_pouso.ErroDeInstrumentacao):
        vigia_do_pouso.corpo_da_denuncia(vereditos, 6)


# ---------------------------------------------------------------------------
# OS ALARMES FALSOS — cada um com o nome da dispensa escrito por extenso.
#
# "Se o vigia gritar por qualquer PR aberto, a casa aprende a ignorar o grito"
# (despacho da TAR-167). Estes testes são a metade do trabalho, não o resto
# dele: sem eles, um vigia que denuncia TUDO passaria no teste de cima.
# ---------------------------------------------------------------------------
def test_pr_que_ja_pediu_pouso_nao_vira_alarme():
    # Esse é o problema da TAR-165 (o pouso foi pedido e a pista não dá conta),
    # e consertar uma doença não pode fazer a outra gritar.
    assert motivo(pr(1080, verde_ha=30, etiquetas=("pousar",))) == "ja-pediu-pouso"


def test_pr_em_rascunho_nao_vira_alarme():
    assert motivo(pr(1081, verde_ha=48, rascunho=True)) == "rascunho"


def test_pr_com_check_vermelho_nao_vira_alarme():
    # Esse tem dono e tem conserto: quem o abriu vê o vermelho na cara do PR.
    assert motivo(pr(1082, verde_ha=20, conclusao="FAILURE")) == "nao-esta-verde"


def test_pr_com_check_ainda_rodando_nao_vira_alarme():
    assert motivo(pr(1083, verde_ha=20, conclusao="IN_PROGRESS")) == (
        "verde-nao-confirmado"
    )


def test_pr_sem_check_obrigatorio_nao_vira_alarme_e_diz_qual_faltou():
    # `armadilhas/198`: PR com conflito não dispara os workflows, e ausência de
    # check nunca é aprovação. O nome do que faltou vai no log — o dia em que
    # um obrigatório for renomeado, todo PR cairia aqui, e o log tem de gritar
    # em vez de o vigia morrer parecendo saudável.
    veredito = vigia_do_pouso.julgar(
        pr(1084, verde_ha=20, checks=("espelho-da-main",)), AGORA, DONOS, 6
    )

    assert veredito.motivo == "verde-nao-confirmado"
    assert "muralhas" in veredito.detalhe and "ci-celula-gate" in veredito.detalhe


def test_pr_sem_nenhum_check_nao_vira_alarme():
    assert motivo(pr(1085, verde_ha=20, checks=())) == "sem-conferencia"


def test_pr_verde_sem_hora_nenhuma_nao_vira_alarme():
    # Sem relógio não há idade, e a idade é a acusação inteira.
    assert motivo(pr(1086, sem_hora=True)) == "sem-hora-do-verde"


def test_pr_verde_ha_pouco_tempo_nao_vira_alarme():
    # A sessão que o abriu pode estar viva, esperando os checks para pedir
    # pouso sozinha (`ci/esperar.py --e-pousar`). Acusar quem trabalha é como
    # um vigia destes morre.
    assert motivo(pr(1087, verde_ha=2)) == "recente"


def test_a_fronteira_da_paciencia_e_medida_dos_dois_lados():
    """5h59 cala, 6h01 grita — com a paciência escrita por extenso."""
    assert motivo(pr(10, verde_ha=5.99), horas=6) == "recente"
    assert motivo(pr(11, verde_ha=6.01), horas=6) == "esquecido"


# ---------------------------------------------------------------------------
# QUEM PRECISA DE MANDATO — lido do CODEOWNERS, nunca copiado para dentro.
# ---------------------------------------------------------------------------
def test_pr_que_toca_caminho_com_dono_e_nomeado_na_denuncia():
    veredito = vigia_do_pouso.julgar(
        pr(1216, verde_ha=10, arquivos=("ci/pr.py", "painel/registros/x.js")),
        AGORA,
        DONOS,
        6,
    )

    assert veredito.esquecido
    assert veredito.caminho_com_dono == "ci/"

    corpo = vigia_do_pouso.corpo_da_denuncia([veredito], 6)
    assert "sim (`ci/`)" in corpo


def test_pr_que_nao_toca_caminho_com_dono_nao_pede_mandato():
    veredito = vigia_do_pouso.julgar(
        pr(1300, verde_ha=10, arquivos=("services/forum/apps/core/views.py",)),
        AGORA,
        DONOS,
        6,
    )

    assert veredito.esquecido
    assert veredito.caminho_com_dono is None


def test_os_caminhos_com_dono_saem_do_codeowners_de_verdade():
    """A lista mora no `.github/CODEOWNERS`, e o vigia lê de lá.

    Copiá-la para dentro do vigia criaria um segundo lugar para o mesmo fato:
    caminho novo protegido passaria a ser anunciado errado, e ninguém veria.
    """
    texto = (CI.parent / ".github" / "CODEOWNERS").read_text(encoding="utf-8")
    padroes = vigia_do_pouso.caminhos_com_dono(texto)

    assert "ci/" in padroes and ".github/" in padroes and "contracts/" in padroes
    assert not any(p.startswith("@") or p.startswith("#") for p in padroes)


def test_codeowners_vazio_e_erro_de_instrumentacao():
    # Sem a lista, a denúncia não sabe dizer quem precisa de mandato — e
    # "não consegui ler" jamais pode virar "ninguém precisa".
    with pytest.raises(vigia_do_pouso.ErroDeInstrumentacao):
        vigia_do_pouso.caminhos_com_dono("# só comentário\n\n")


# ---------------------------------------------------------------------------
# A FOTOGRAFIA REAL DE 07/09/2026 — o dia em que a TAR-167 foi construída.
#
# Copiada de `gh pr list --state open --json ...` às 03:13 UTC. Três PRs
# verdes, sem etiqueta, entre 8 e 10 horas parados; um com check vermelho e um
# recém-aberto. É o inventário que a régua tem de acertar inteiro.
# ---------------------------------------------------------------------------
def test_a_fotografia_de_07_09_2026_acusa_os_tres_e_so_os_tres():
    inventario = [
        pr(1216, verde_ha=10.09, arquivos=("ci/pr.py",), titulo="ci: do commit ao PR"),
        pr(1224, verde_ha=9.94, arquivos=("ci/cobranca_do_checklist.py",)),
        pr(1244, verde_ha=8.02, arquivos=("infra/provisionar-email.sh",)),
        pr(1275, verde_ha=0.11, arquivos=("armadilhas/328-x.md",)),
        pr(1276, verde_ha=0.13, conclusao="FAILURE", arquivos=("services/cursos/a.py",)),
    ]

    vereditos = vigia_do_pouso.varrer(inventario, AGORA, DONOS, 6)
    acusados = [v.numero for v in vereditos if v.esquecido]

    assert acusados == [1216, 1224, 1244], (
        "a fotografia real do dia tem exatamente três PRs esquecidos, e o mais "
        f"velho vem primeiro — veio {acusados}"
    )
    dispensados = {v.numero: v.motivo for v in vereditos if not v.esquecido}
    assert dispensados == {1275: "recente", 1276: "nao-esta-verde"}


# ---------------------------------------------------------------------------
# O DIALETO DE SAÍDA — é por ele que o workflow decide abrir, reescrever ou
# fechar a issue. Se ele mudar sem o YAML mudar junto, o vigia fica mudo.
# ---------------------------------------------------------------------------
def _rodar(tmp_path: Path, inventario: list[dict], *extra: str):
    arquivo = tmp_path / "inventario.json"
    arquivo.write_text(json.dumps(inventario), encoding="utf-8")
    return subprocess.run(
        [
            sys.executable,
            str(CI / "vigia_do_pouso.py"),
            "--inventario",
            str(arquivo),
            "--agora",
            AGORA.isoformat(),
            "--horas",
            "6",
            *extra,
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )


def test_saida_3_e_o_corpo_escrito_quando_ha_esquecido(tmp_path: Path):
    corpo = tmp_path / "denuncia.md"
    saida = _rodar(tmp_path, [pr(741, verde_ha=9)], "--corpo", str(corpo))

    assert saida.returncode == 3, saida.stdout + saida.stderr
    assert "ESQUECIDOS=1" in saida.stdout
    assert "#741" in corpo.read_text(encoding="utf-8")


def test_saida_0_e_nenhum_corpo_quando_a_fila_anda(tmp_path: Path):
    corpo = tmp_path / "denuncia.md"
    saida = _rodar(tmp_path, [pr(1, verde_ha=1)], "--corpo", str(corpo))

    assert saida.returncode == 0, saida.stdout + saida.stderr
    assert "ESQUECIDOS=0" in saida.stdout
    assert not corpo.exists(), (
        "sem ninguém esquecido não existe denúncia — um corpo escrito aqui "
        "faria o workflow abrir issue de lista vazia"
    )


def test_inventario_ilegivel_e_ERROR_nunca_fila_limpa(tmp_path: Path):
    arquivo = tmp_path / "inventario.json"
    arquivo.write_text("isto não é JSON", encoding="utf-8")
    saida = subprocess.run(
        [sys.executable, str(CI / "vigia_do_pouso.py"), "--inventario", str(arquivo)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert saida.returncode == 2, saida.stdout + saida.stderr
    assert "ERROR" in saida.stdout
    assert "ESQUECIDOS=0" not in saida.stdout, (
        "não conseguir varrer jamais pode ser dito como 'nenhum PR esquecido'"
    )


def test_data_ilegivel_vira_frase_e_ERROR_nunca_traceback(tmp_path: Path):
    """Formato novo do GitHub tem de sair como frase, não como traceback.

    Traceback não diz o que fazer, e quem lê o log de um vigia às 3 da manhã
    precisa da frase. O exit continua sendo 2 — ERROR, nunca 'está tudo limpo'.
    """
    podre = pr(9)
    for check in podre["statusCheckRollup"]:
        check["completedAt"] = "ontem de tarde"
        check.pop("startedAt", None)
    saida = _rodar(tmp_path, [podre])

    assert saida.returncode == 2, saida.stdout + saida.stderr
    assert "data ou formato que eu não sei ler" in saida.stdout
    assert "Traceback" not in saida.stderr


def test_sem_repo_e_sem_inventario_e_ERROR():
    saida = subprocess.run(
        [sys.executable, str(CI / "vigia_do_pouso.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )

    assert saida.returncode == 2
    assert "--repo" in saida.stdout
