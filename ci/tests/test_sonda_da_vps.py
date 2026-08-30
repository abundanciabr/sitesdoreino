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


def test_a_medicao_de_partida_nao_afirma_que_algo_falhou():
    """A mesma medição, momentos diferentes, frases diferentes.

    Na partida nada falhou ainda. Reaproveitar ali o texto do diagnóstico —
    "o que falhou foi a rede" — poria uma frase FALSA no log de todo deploy
    saudável, e mensagem que mente gasta a confiança de que a mensagem certa
    precisa (é a lição da mensagem alarmante errada do run 33260367237).
    """
    partida = sonda.decidir_pela_sonda(
        sonda.Medicao(porta22=True, site_http=200, apos_recusa=False)
    )
    assert partida.veredito == sonda.BLIP
    assert "falhou" not in partida.motivo
    assert "linha de base" in partida.motivo


def test_a_medicao_de_partida_com_porta_morta_nao_interrompe_sozinha():
    """Ela nomeia a suspeita e diz, no próprio texto, que não decide nada.

    Quem interrompe é o PAR de medições tomadas depois de recusas reais; uma
    leitura isolada da partida derrubaria deploys por um blip da própria sonda.

    A ENTRADA FICOU MAIS EXIGENTE EM 30/08/2026 (TAR-026), não a asserção: até
    ali bastava `porta22=False` — o resumo de UMA sondagem — para a sonda dizer
    `permanente`, e foi assim que ela acusou a 017 com a VPS viva. Hoje o
    veredito exige as sondagens que o sustentam; o que este teste protege
    continua sendo o mesmo.
    """
    partida = sonda.decidir_pela_sonda(
        sonda.Medicao(
            porta22=False,
            sinais=(sonda.RECUSOU,) * 3,
            site_http=200,
            apos_recusa=False,
        )
    )
    assert partida.veredito == sonda.PERMANENTE
    assert "NÃO interrompe" in partida.motivo


def test_porta_morta_e_a_017_e_nao_se_cura_repetindo():
    """A 017 é real, e desistir DELA é o certo — isto não pode ser afrouxado.

    O conserto da TAR-026 estreitou o caminho para `permanente`; ele não pode
    ter FECHADO o caminho, senão o deploy nunca mais desiste de nada e a vacina
    troca um erro por outro. Três recusas seguidas da rede continuam sendo a
    assinatura da 017.
    """
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(porta22=False, sinais=(sonda.RECUSOU,) * 3, site_http=200)
    )
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


# ------------------- o falso `permanente` de 30/08/2026 (TAR-026 · a/209) --
#
# O run 33312655853 (deploy da `admin`, PR #589) mediu a porta 22 três vezes,
# disse `permanente` nas três, e o deploy DESISTIU — enquanto a mesma porta,
# sondada do PC na mesma janela, devolvia `SSH-2.0-OpenSSH_9.6p1`. A VPS estava
# viva; `gh run rerun --failed` subiu em 1min02s. Era a 127, não a 017.
#
# O log entrega a causa sem palpite: cada medição durou 25 s (10 s de estouro de
# tempo na porta + 15 s de estouro de tempo no site) e NENHUMA conexão foi
# recusada. Duas confusões, uma em cima da outra:
#   1. "estourou o tempo" caía no mesmo `except` de "recusou a conexão";
#   2. o site público não respondia DAQUI — prova de que o cego era o runner —
#      e esse número só virava um recado no fim, nunca entrava na decisão.


def test_uma_medicao_sozinha_nunca_manda_o_deploy_desistir():
    """O CASO MEDIDO, no vocabulário do código ANTIGO (armadilhas/195).

    Este teste é construtível nas duas versões do módulo — ele não usa nenhum
    símbolo novo — e por isso o vermelho dele morre na ASSERÇÃO, não no
    `TypeError`: contra a `main` de 30/08/2026 ele devolve `permanente`, que é
    exatamente o veredito que abandonou a entrega do PR #589.
    """
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=False, site_http=None))
    assert veredito.veredito != sonda.PERMANENTE, (
        "uma medição sozinha voltou a mandar o deploy desistir — é o falso "
        "`permanente` da armadilhas/209 de volta"
    )
    assert veredito.veredito == sonda.NAO_MEDI
    assert veredito.codigo == 2


def test_o_silencio_com_o_runner_cego_e_nao_medi_e_o_retry_segue():
    """O caso medido, agora com o detalhe das sondagens.

    Três estouros de tempo na porta 22 E o site público inalcançável daqui:
    isso é evidência sobre o RUNNER, não sobre a VPS. Fail-closed aqui significa
    CONTINUAR TENTANDO — repetir à toa custa 45 s, desistir à toa custa a
    entrega, em silêncio.
    """
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(sinais=(sonda.SEM_RESPOSTA,) * 3, site_http=None)
    )
    assert veredito.veredito == sonda.NAO_MEDI
    assert veredito.codigo == 2
    assert "127" in veredito.motivo, (
        "sem nomear o soluço, quem lê continua achando que é a 017"
    )


def test_o_silencio_vira_permanente_quando_o_site_responde_daqui():
    """E a 017 continua acontecendo — este é o teste que impede o conserto de

    virar o erro oposto. Se o runner alcança o site público mas não a porta 22,
    a saída dele funciona e o buraco é a porta: é a forma exata da 017 (CDN na
    frente, firewall recusando a faixa dos runners).
    """
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(sinais=(sonda.SEM_RESPOSTA,) * 3, site_http=200)
    )
    assert veredito.veredito == sonda.PERMANENTE
    assert veredito.codigo == 1


def test_uma_sondagem_negativa_isolada_tambem_nao_basta():
    """Nem mesmo uma RECUSA — a resposta mais categórica que a rede dá — decide
    sozinha. A régua é a mesma em todo lugar: nunca uma medição só."""
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(sinais=(sonda.RECUSOU,), site_http=200)
    )
    assert veredito.veredito == sonda.NAO_MEDI
    assert "sondagem" in veredito.motivo


def test_defeito_do_proprio_instrumento_nunca_vira_veredito():
    """`NAO_PERGUNTEI` é a sonda falhando antes de perguntar. Misturado com
    respostas reais, ele contamina a medição inteira [INV-CI01]."""
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(
            sinais=(sonda.RECUSOU, sonda.RECUSOU, sonda.NAO_PERGUNTEI),
            site_http=200,
        )
    )
    assert veredito.veredito == sonda.NAO_MEDI


def test_uma_sondagem_viva_no_meio_de_muitas_mortas_ja_e_blip():
    """Ninguém fica vivo por acidente: um banner de SSH encerra a dúvida.

    É a assimetria que torna a sonda uma vacina — ela precisa de corroboração
    para DESISTIR, nunca para continuar tentando.
    """
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(
            sinais=(sonda.SEM_RESPOSTA, sonda.ATENDEU, sonda.SEM_RESPOSTA),
            site_http=200,
        )
    )
    assert veredito.veredito == sonda.BLIP
    assert veredito.codigo == 0


def test_os_tres_vereditos_dizem_em_quantas_medicoes_se_baseiam():
    """O pedido literal da TAR-026, e ele vale para os TRÊS vereditos.

    Quem lê "falha permanente" tem direito de saber se isso foi medido uma vez
    ou três. Sem o número, a mensagem é categórica — e mensagem categórica é
    acreditada.

    Os casos são montados DENTRO do teste, não num `parametrize`, de propósito:
    decorador roda na importação, e um símbolo novo ali derrubaria a COLETA do
    módulo inteiro contra a `main` antiga — o vermelho que a `armadilhas/195`
    proíbe aceitar como prova. Assim cada teste vive ou morre sozinho.
    """
    casos = [
        ((sonda.RECUSOU,) * 3, sonda.PERMANENTE, 3),
        ((sonda.SEM_RESPOSTA,) * 3, sonda.NAO_MEDI, 3),
        ((sonda.ATENDEU,), sonda.BLIP, 1),
    ]
    for sinais, esperado, medicoes in casos:
        veredito = sonda.decidir_pela_sonda(
            sonda.Medicao(sinais=sinais, site_http=None)
        )
        assert veredito.veredito == esperado, f"sinais={sinais}"
        assert veredito.medicoes == medicoes, f"sinais={sinais}"


def test_a_mensagem_do_permanente_diz_o_numero_e_o_que_cada_sondagem_viu():
    veredito = sonda.decidir_pela_sonda(
        sonda.Medicao(sinais=(sonda.RECUSOU,) * 3, site_http=200)
    )
    assert veredito.medicoes == 3
    assert "3 sondagens" in veredito.motivo, (
        "a desistência precisa mostrar em quantas medições se apoia"
    )
    assert "recusou a conexão em 3" in veredito.motivo, (
        "sem o detalhe, a mensagem volta a ser categórica em vez de falsificável"
    )


def test_estourar_o_tempo_nao_e_a_mesma_coisa_que_recusar(monkeypatch):
    """A confusão que causou o falso `permanente`, isolada em quatro linhas.

    Até 30/08/2026 as três primeiras caíam no MESMO `except` e viravam `False` =
    "porta morta". Mas o estouro de tempo é a assinatura literal do soluço da
    127 (`dial tcp ***:22: i/o timeout`) — a sonda reproduzia o próprio engasgo
    que existe para diagnosticar e depois o declarava permanente.
    """
    casos = [
        (TimeoutError, sonda.SEM_RESPOSTA),
        (ConnectionRefusedError, sonda.RECUSOU),
        (socket.gaierror, sonda.NOME_NAO_RESOLVE),
        (PermissionError, sonda.NAO_PERGUNTEI),
    ]
    for estouro, sinal_esperado in casos:

        def explodir(*_args, _erro=estouro, **_kwargs):
            raise _erro("encenado")

        monkeypatch.setattr(socket, "create_connection", explodir)
        assert sonda.sondar_uma_vez("nao-importa", 22) == sinal_esperado, (
            f"{estouro.__name__} deixou de ser {sinal_esperado}"
        )


def test_o_estouro_de_tempo_sozinho_nunca_devolve_porta_morta(monkeypatch):
    """A regressão exata, medida na função que a vacina do PC também importa.

    Construtível no código antigo (nenhum símbolo novo) — lá ela devolve
    `False`, e `False` é o que `rerun_de_deploy.py` lê como "é a 017, pare".
    """
    monkeypatch.setattr(sonda, "PAUSA_ENTRE_SONDAGENS_S", 0, raising=False)

    def estourar(*_args, **_kwargs):
        raise TimeoutError("encenado")

    monkeypatch.setattr(socket, "create_connection", estourar)
    assert sonda.porta_22_responde("nao-importa", 22) is None, (
        "silêncio voltou a valer como 'porta morta' — é a armadilhas/209"
    )


def test_a_medicao_pergunta_varias_vezes_e_para_cedo_quando_a_porta_atende(
    monkeypatch,
):
    """Três sondagens no caminho duvidoso; UMA no caminho feliz.

    Se ela não parasse cedo, todo deploy saudável pagaria as pausas — e uma
    vacina que custa caro no caso normal acaba desligada por alguém com pressa.
    """
    monkeypatch.setattr(sonda, "PAUSA_ENTRE_SONDAGENS_S", 0, raising=False)
    perguntas: list[str] = []

    def responder(_host, _porta=22):
        perguntas.append("?")
        return sonda.RECUSOU if len(perguntas) < 3 else sonda.ATENDEU

    monkeypatch.setattr(sonda, "sondar_uma_vez", responder)
    assert sonda.medir_a_porta("nao-importa") == (
        sonda.RECUSOU,
        sonda.RECUSOU,
        sonda.ATENDEU,
    )
    assert len(perguntas) == 3

    perguntas.clear()
    monkeypatch.setattr(sonda, "sondar_uma_vez", lambda *_a, **_k: (
        perguntas.append("?") or sonda.ATENDEU
    ))
    assert sonda.medir_a_porta("nao-importa") == (sonda.ATENDEU,)
    assert len(perguntas) == 1, "a porta atendeu e a sonda continuou perguntando"


def test_a_sonda_nunca_decide_permanente_com_menos_de_duas_medicoes():
    """A lei em uma linha, e ela é do MÓDULO, não do workflow.

    O workflow já exigia duas medições e mesmo assim desistiu errado, porque
    cada uma delas era uma sondagem só. A régua precisa morar onde a decisão é
    tomada.
    """
    assert sonda.MEDICOES_MINIMAS_PARA_PERMANENTE >= 2
    assert sonda.SONDAGENS_POR_MEDICAO >= sonda.MEDICOES_MINIMAS_PARA_PERMANENTE
    for quantas in range(0, sonda.MEDICOES_MINIMAS_PARA_PERMANENTE):
        veredito = sonda.decidir_pela_sonda(
            sonda.Medicao(sinais=(sonda.RECUSOU,) * quantas, site_http=200)
        )
        assert veredito.veredito != sonda.PERMANENTE, (
            f"{quantas} sondagem(ns) bastaram para mandar o deploy desistir"
        )


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


def test_quem_atende_sem_falar_ssh_nao_conta_como_porta_viva(monkeypatch):
    """Abrir a conexão não é ser um servidor de SSH.

    É a mesma lição do "verde sem ter subido nada" (28/08/2026): a porta abrir
    não prova que o trabalho pode ser feito. Um proxy que aceita a conexão e
    fica calado faria a sonda dizer "a VPS está viva" sobre uma VPS que não
    está atrás dele.
    """
    monkeypatch.setattr(sonda, "PAUSA_ENTRE_SONDAGENS_S", 0, raising=False)
    host, porta, _ = _servidor_falso(b"HTTP/1.1 400 Bad Request\r\n")
    assert sonda.porta_22_responde(host, porta) is False


def test_porta_que_nao_atende_e_medicao_False_e_nao_None(monkeypatch):
    """Conexão recusada é uma RESPOSTA — eu perguntei e não fui atendido.

    Devolver None aqui faria a sonda dizer "não medi" sobre a porta fechada
    mais clássica que existe, e o deploy nunca aprenderia que é a 017. É o
    contraponto do `test_o_estouro_de_tempo_sozinho_nunca_devolve_porta_morta`:
    a TAR-026 estreitou o `False` ao caso da RESPOSTA, e não pode tê-lo
    abolido.
    """
    monkeypatch.setattr(sonda, "PAUSA_ENTRE_SONDAGENS_S", 0, raising=False)
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


def test_o_resumo_nao_acusa_a_017_com_uma_medicao_discordando():
    """A régua do resumo é a mesma do passo de parada (TAR-026).

    A página que o mantenedor abre primeiro dizia "é a armadilhas/017, passa
    pelo mantenedor" quando UMA medição gritava `permanente`, mesmo com a outra
    dizendo que a porta estava viva. Mensagem categórica na vitrine é pior que
    no log: ela vira o encaminhamento.
    """
    entrega = sonda.Entrega(
        celula="admin",
        tentativas=("failure", "failure", "failure"),
        sondas=(sonda.BLIP, sonda.PERMANENTE, sonda.BLIP),
        marca_de_conclusao=False,
        site_http=200,
    )
    # Cada medição continua contando o que ELA viu — inclusive citando a 017.
    # O que não pode é o DESFECHO, que é o encaminhamento, ser decidido por uma
    # medição contra a outra.
    desfecho = sonda._desfecho(entrega)
    assert "017" not in desfecho, (
        "uma medição discordando da outra e o desfecho já acusa falha permanente"
    )
    assert "NÃO subiu" in desfecho
    assert "rerun_de_deploy.py" in desfecho
    assert desfecho in sonda.narrar(entrega)


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


def test_so_a_medicao_de_partida_se_declara_partida():
    """As medições de recusa NÃO podem herdar o texto neutro da partida.

    Se alguém marcasse todas como `MOMENTO: partida`, o run pararia de dizer
    "repetir é exatamente o certo" no único momento em que essa frase é a
    conclusão — e a medição voltaria a ser decoração.
    """
    partidas = [
        passo
        for passo in _passos_de_sonda()
        if (passo.get("env") or {}).get("MOMENTO") == "partida"
    ]
    assert len(partidas) == 1, (
        f"esperava exatamente uma medição de linha de base, achei {len(partidas)}"
    )
    assert not partidas[0].get("if"), (
        "a medição de partida é a única que roda SEMPRE — condicioná-la faria o "
        "deploy saudável deixar de registrar qualquer medição"
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


def test_a_parada_diz_no_log_em_quantas_sondagens_ela_se_baseia():
    """A mensagem que manda desistir tem de mostrar a conta (TAR-026).

    Em 30/08/2026 este passo escreveu "a porta 22 não respondeu em NENHUMA das
    duas medições" sobre uma VPS viva, e quem leu acreditou — porque a frase era
    categórica e não mostrava em quantas sondagens se apoiava. Número que só o
    script conhece e o run não repete é número que ninguém confere.
    """
    parada = _passo_de_parada()
    ambiente = parada.get("env") or {}
    citados = " ".join(str(valor) for valor in ambiente.values())
    assert "outputs.sondagens" in citados, (
        "a parada voltou a não citar quantas sondagens sustentam a desistência"
    )
    for id_da_sonda in ("sonda1", "sonda2"):
        assert f"steps.{id_da_sonda}.outputs.sondagens" in citados
    corpo = str(parada.get("run", ""))
    assert "sondagens" in corpo, (
        "o número chega no ambiente do passo e não aparece na mensagem"
    )


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
