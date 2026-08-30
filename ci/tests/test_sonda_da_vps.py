"""Guardas da sonda da VPS — a medição que o deploy passou a fazer sozinho.

A `armadilhas/127` manda o deploy fazer TRÊS coisas: medir a porta 22, repetir
com pausa, parar na terceira. Duas estavam no `deploy-celula.yml` desde
26/08/2026; **medir** não estava em lugar nenhum do deploy — morava no texto da
armadilha e na vacina do PC (`ci/rerun_de_deploy.py`), que só roda depois que
alguém viu o vermelho.

O que estes guardas protegem, e por que cada um existe:

- **A sonda nunca derruba entrega que ainda podia dar certo.** Ela só encurta o
  laço na direção provada: DUAS medições dizendo "porta morta". Se alguém
  afrouxar isso para uma medição só, um defeito momentâneo da própria sonda
  passaria a abortar deploys bons — e a vacina viraria arma.
- **"Não medi" nunca vira "porta morta"** [INV-CI01]. É por isso que o
  workflow lê `outputs.veredito` e não `outcome`: o `outcome` de um passo só
  tem dois valores e juntaria as duas coisas. O teste abaixo reprova quem
  trocar a leitura.
- **A medição existe DENTRO do deploy.** Este é o teste que separa esta
  entrega do estado anterior: contra a `main` de 30/08/2026, antes do conserto,
  ele reprova na asserção (o YAML carrega, os passos é que não existem) — e não
  na construção do teste (`armadilhas/195`).
- **A história do run é contada.** Um deploy salvo na 2ª tentativa era, para
  quem abre a execução, idêntico a um que passou de primeira: o padrão da VPS
  recusando ficava invisível justo nos dias em que ela mais recusou.
"""

from __future__ import annotations

import socket
import sys
import threading
from pathlib import Path

import pytest
import yaml

CI = Path(__file__).resolve().parents[1]
RAIZ = CI.parent
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import sonda_da_vps as sonda  # noqa: E402

DEPLOY = RAIZ / ".github" / "workflows" / "deploy-celula.yml"
SCRIPT_DA_ENTREGA = RAIZ / "infra" / "deploy-celula-na-vps.sh"


# ------------------------------------------------- a tabela de decisão pura --


def test_porta_viva_e_o_soluco_da_127_e_manda_repetir():
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=True, site_http=200))
    assert veredito.veredito == sonda.BLIP
    assert veredito.codigo == 0
    assert "127" in veredito.motivo, "parar sem nomear a armadilha não ensina nada"


def test_porta_morta_e_a_017_e_nao_se_cura_repetindo():
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=False, site_http=200))
    assert veredito.veredito == sonda.PERMANENTE
    assert veredito.codigo == 1
    assert "017" in veredito.motivo


def test_nao_medi_nunca_vira_porta_morta():
    """[INV-CI01]: ausência de evidência não é evidência de nada.

    Se este ramo devolvesse PERMANENTE, um defeito da própria sonda (nome que
    não resolve no runner, socket bloqueado) passaria a abortar deploys sãos.
    """
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=None))
    assert veredito.veredito == sonda.NAO_MEDI
    assert veredito.codigo == 2
    assert veredito.veredito != sonda.PERMANENTE


def test_sem_host_declarado_tambem_e_nao_medi():
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(host_declarado=False))
    assert veredito.veredito == sonda.NAO_MEDI
    assert veredito.codigo == 2


@pytest.mark.parametrize(
    "codigo, pedaco",
    [
        (200, "versão ANTERIOR"),
        (None, "não medi"),
        (503, "ATENÇÃO"),
    ],
)
def test_o_recado_do_site_diz_a_verdade_dos_tres_estados(codigo, pedaco):
    """Deploy vermelho por SSH não põe ninguém fora do ar — mas o merge não
    está em produção. Confundir os dois já fez esta casa anunciar entrega no ar
    que não estava (armadilhas/127)."""
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=True, site_http=codigo))
    assert pedaco.lower() in veredito.recado.lower()


# ------------------------------------------------------- a medição de fato --


def _servidor_falso(banner: bytes) -> tuple[str, int, threading.Thread]:
    """Um socket local que responde como (ou como não) um servidor de SSH."""
    servidor = socket.socket()
    servidor.bind(("127.0.0.1", 0))
    servidor.listen(1)
    host, porta = servidor.getsockname()

    def atender() -> None:
        try:
            conexao, _ = servidor.accept()
            with conexao:
                if banner:
                    conexao.sendall(banner)
        except OSError:
            pass
        finally:
            servidor.close()

    linha = threading.Thread(target=atender, daemon=True)
    linha.start()
    return host, porta, linha


def test_a_sonda_reconhece_o_banner_de_ssh():
    host, porta, _ = _servidor_falso(b"SSH-2.0-OpenSSH_9.6p1 Ubuntu-3\r\n")
    assert sonda.porta_22_responde(host, porta) is True


def test_quem_atende_sem_falar_ssh_nao_conta_como_porta_viva():
    """Abrir a conexão não é ser um servidor de SSH.

    É a mesma lição do "verde sem ter subido nada" (28/08/2026): a porta abrir
    não prova que o trabalho pode ser feito. Um proxy que aceita a conexão e
    fica calado faria a sonda dizer "a VPS está viva" sobre uma VPS que não
    está atrás dele.
    """
    host, porta, _ = _servidor_falso(b"HTTP/1.1 400 Bad Request\r\n")
    assert sonda.porta_22_responde(host, porta) is False


def test_porta_que_nao_atende_e_medicao_False_e_nao_None():
    """Conexão recusada é uma RESPOSTA — eu perguntei e não fui atendido.

    Devolver None aqui faria a sonda dizer "não medi" sobre a porta fechada
    mais clássica que existe, e o deploy nunca aprenderia que é a 017.
    """
    fechada = socket.socket()
    fechada.bind(("127.0.0.1", 0))
    _host, porta = fechada.getsockname()
    fechada.close()  # ninguém mais escuta nesse número
    assert sonda.porta_22_responde("127.0.0.1", porta) is False


# ---------------------------------------------------------- o que o run diz --


def test_o_resumo_conta_quando_a_vps_recusou_antes_de_aceitar():
    """O caso que era invisível: verde na 2ª tentativa."""
    texto = sonda.narrar(
        sonda.Entrega(
            celula="admin",
            tentativas=("failure", "success", "skipped"),
            sondas=(sonda.BLIP, sonda.BLIP, ""),
            marca_de_conclusao=True,
            site_http=200,
        )
    )
    assert "ESTÁ em produção" in texto
    assert "2 tentativas" in texto, "sem o número, o padrão da 127 segue invisível"
    assert "127" in texto


def test_o_resumo_nao_confunde_verde_de_primeira_com_verde_salvo():
    texto = sonda.narrar(
        sonda.Entrega(
            celula="admin",
            tentativas=("success", "skipped", "skipped"),
            sondas=(sonda.BLIP, "", ""),
            marca_de_conclusao=True,
            site_http=200,
        )
    )
    assert "de primeira" in texto
    assert "127" not in texto, "deploy normal não deve citar armadilha nenhuma"


def test_o_resumo_nomeia_a_017_quando_a_porta_ficou_muda():
    texto = sonda.narrar(
        sonda.Entrega(
            celula="admin",
            tentativas=("failure", "failure", "skipped"),
            sondas=(sonda.PERMANENTE, sonda.PERMANENTE, sonda.PERMANENTE),
            marca_de_conclusao=False,
            site_http=200,
        )
    )
    assert "NÃO subiu" in texto
    assert "017" in texto
    assert "ESTÁ em produção" not in texto


def test_o_resumo_de_falha_manda_para_a_vacina_do_pc():
    texto = sonda.narrar(
        sonda.Entrega(
            celula="admin",
            tentativas=("failure", "failure", "failure"),
            sondas=(sonda.BLIP, sonda.BLIP, sonda.BLIP),
            marca_de_conclusao=False,
            site_http=200,
        )
    )
    assert "rerun_de_deploy.py" in texto


def test_a_marca_de_conclusao_e_a_mesma_nos_tres_lugares():
    """O script imprime, o portão do workflow exige, o narrador procura.

    Três grafias diferentes fariam o resumo do run contar uma história e o
    portão contar outra sobre a MESMA entrega.
    """
    assert sonda.MARCA_DE_CONCLUSAO in SCRIPT_DA_ENTREGA.read_text(encoding="utf-8")
    assert sonda.MARCA_DE_CONCLUSAO in DEPLOY.read_text(encoding="utf-8")


# ------------------------------------------ a fiação dentro do deploy real --


def _passos_do_deploy() -> list[dict]:
    fluxo = yaml.safe_load(DEPLOY.read_text(encoding="utf-8"))
    return fluxo["jobs"]["deploy"]["steps"]


def _passos_de_sonda() -> list[dict]:
    return [
        passo
        for passo in _passos_do_deploy()
        if "sonda_da_vps.py --sondar-porta" in str(passo.get("run", ""))
    ]


def test_o_deploy_mede_a_porta_22_sozinho():
    """A terceira ordem da armadilhas/127, dentro do deploy.

    Sem estes passos, o retry repete às cegas: trata a 017 (falha permanente)
    como se fosse o soluço da 127, gasta 105 s de pausa e três conexões, e
    termina dizendo "a suspeita é a 017" — que é palpite, não medição.
    """
    sondas = _passos_de_sonda()
    assert len(sondas) >= 3, (
        "o deploy voltou a não medir a porta 22 — esperava a medição de partida "
        "e uma depois de cada recusa"
    )


def test_a_sonda_nunca_pode_derrubar_o_deploy():
    """Vacina, não arma: a sonda mede e informa; quem reprova são as tentativas."""
    for passo in _passos_de_sonda():
        assert passo.get("continue-on-error") is True, (
            f"{passo.get('name')}: sem continue-on-error, um defeito da própria "
            "sonda passa a reprovar deploys que iriam dar certo"
        )


def test_a_sonda_recebe_o_host_por_env_e_nunca_por_argumento():
    """`VPS_HOST` é segredo: argumento aparece na tabela de processos."""
    for passo in _passos_de_sonda():
        assert "VPS_HOST" in (passo.get("env") or {}), (
            f"{passo.get('name')}: o host precisa chegar por env"
        )
        assert "secrets.VPS_HOST" not in str(passo.get("run", "")), (
            f"{passo.get('name')}: o host não pode viajar na linha de comando"
        )


def _passo_de_parada() -> dict:
    parada = [
        passo
        for passo in _passos_do_deploy()
        if "outputs.veredito" in str(passo.get("if", ""))
    ]
    assert parada, (
        "nenhum passo do deploy lê o veredito da sonda — a medição existiria "
        "sem decidir nada, que é o mesmo que não medir"
    )
    return parada[0]


def test_a_parada_antecipada_exige_DUAS_medicoes():
    """Uma medição isolada pode ser defeito da sonda; duas são evidência.

    Afrouxar isto para uma medição só é a diferença entre pular uma tentativa
    condenada e abortar um deploy que ia dar certo.
    """
    condicao = str(_passo_de_parada().get("if", ""))
    assert condicao.count("== 'permanente'") >= 2, (
        "a parada antecipada passou a se contentar com UMA medição de porta morta"
    )
    assert "sonda1" in condicao and "sonda2" in condicao


def test_a_parada_le_o_veredito_e_nunca_o_outcome():
    """[INV-CI01] em uma linha de YAML.

    `outcome` só tem `success`/`failure`: ler a decisão por ele juntaria "a
    porta está morta" com "não consegui medir" — e a segunda passaria a
    abortar deploys, que é a inversão exata do fail-closed desta casa.
    """
    condicao = str(_passo_de_parada().get("if", ""))
    assert "outputs.veredito" in condicao
    for id_da_sonda in ("sonda1", "sonda2"):
        assert f"steps.{id_da_sonda}.outcome" not in condicao


def test_a_parada_antecipada_reprova_de_verdade():
    """Ela existe para PARAR, não para avisar: precisa terminar em erro."""
    corpo = str(_passo_de_parada().get("run", ""))
    assert "exit 1" in corpo
    assert not _passo_de_parada().get("continue-on-error")


def test_o_deploy_registra_no_resumo_do_run_o_que_fez():
    """A terceira parte da vacina: registrar.

    Sem isto, um deploy salvo na 2ª tentativa é indistinguível de um que passou
    de primeira para quem abre a execução — e o padrão da armadilhas/127 fica
    invisível justamente nos dias em que ela mais mordeu.
    """
    narradores = [
        passo
        for passo in _passos_do_deploy()
        if "sonda_da_vps.py --resumir" in str(passo.get("run", ""))
    ]
    assert narradores, "o deploy voltou a não registrar o que fez"
    narrador = narradores[0]
    assert "cancelled()" in str(narrador.get("if", "")), (
        "o narrador precisa rodar também quando a entrega falhou — é aí que a "
        "história importa — e NÃO quando o run foi cancelado sem rodar nada"
    )
    for variavel in ("R1", "R2", "R3", "V0", "V1", "V2"):
        assert variavel in (narrador.get("env") or {}), (
            f"sem {variavel} o resumo não sabe contar o que aconteceu"
        )
