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

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import sonda_da_vps as sonda  # noqa: E402



# ------------------------------------------------- a tabela de decisão pura --


def test_porta_viva_e_o_soluco_da_127_e_manda_repetir():
    veredito = sonda.decidir_pela_sonda(sonda.Medicao(porta22=True, site_http=200))
    assert veredito.veredito == sonda.BLIP
    assert veredito.codigo == 0
    assert "intermitente" in veredito.motivo


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
    assert "Falha persistente de alcance" in veredito.motivo


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
    assert "falha de rede do runner" in veredito.motivo


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
        (200, "respondeu 200"),
        (None, "Não consegui medir"),
        (503, "respondeu 503"),
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
    assert "ESTÁ em produção" not in texto
    assert "sonda de rede não registra aprovação" in texto
    assert "2 tentativas" in texto, "sem o número, o padrão da 127 segue invisível"
    assert "rede intermitente" in texto


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
    assert "rede intermitente" not in texto


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
    assert "sem conclusão confirmada" in texto
    assert "não estava alcançável" in texto
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
    assert "não estava alcançável" not in desfecho, (
        "uma medição discordando da outra e o desfecho já acusa falha permanente"
    )
    assert "sem conclusão confirmada" in desfecho
    assert "logs da aplicação e da recuperação" in desfecho
    assert desfecho in sonda.narrar(entrega)


def test_o_resumo_de_falha_encaminha_para_os_logs_da_recuperacao():
    texto = sonda.narrar(
        sonda.Entrega(
            celula="admin",
            tentativas=("failure", "failure", "failure"),
            sondas=(sonda.BLIP, sonda.BLIP, sonda.BLIP),
            marca_de_conclusao=False,
            site_http=200,
        )
    )
    assert "logs da aplicação e da recuperação" in texto


@pytest.mark.parametrize(
    "sinais, site_http, codigo, veredito",
    [
        ((sonda.ATENDEU,), 200, 0, sonda.BLIP),
        ((sonda.RECUSOU, sonda.RECUSOU), 200, 1, sonda.PERMANENTE),
        ((sonda.SEM_RESPOSTA, sonda.SEM_RESPOSTA), None, 2, sonda.NAO_MEDI),
        ((sonda.RECUSOU,), 200, 2, sonda.NAO_MEDI),
    ],
)
def test_comando_publica_veredito_contagem_e_codigo_sem_expor_host(
    monkeypatch, tmp_path, capsys, sinais, site_http, codigo, veredito
):
    host = "host-operacional-sigiloso.invalid"
    output = tmp_path / "output"
    resumo = tmp_path / "resumo"
    alvos = []
    monkeypatch.setenv("VPS_HOST", host)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    monkeypatch.delenv("MOMENTO", raising=False)
    monkeypatch.setattr(sonda, "configurar_saida", lambda: None)
    monkeypatch.setattr(sonda, "medir_a_porta", lambda alvo: alvos.append(alvo) or sinais)
    monkeypatch.setattr(sonda, "http_do_site", lambda _url: site_http)
    assert sonda.main(["--sondar-porta"]) == codigo
    assert alvos == [host]
    assert output.read_text(encoding="utf-8") == (
        f"veredito={veredito}\nsondagens={len(sinais)}\n"
    )
    assert host not in capsys.readouterr().out
    assert host not in resumo.read_text(encoding="utf-8")


def test_comando_sem_host_nao_tenta_medicao_e_informa_erro(monkeypatch, tmp_path):
    output = tmp_path / "output"
    monkeypatch.delenv("VPS_HOST", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(output))
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sonda, "configurar_saida", lambda: None)
    def nao_medir(*_args):
        pytest.fail("A sonda tentou rede sem um host declarado")
    monkeypatch.setattr(sonda, "medir_a_porta", nao_medir)
    monkeypatch.setattr(sonda, "http_do_site", nao_medir)
    assert sonda.main(["--sondar-porta"]) == 2
    assert output.read_text(encoding="utf-8") == "veredito=nao_medi\nsondagens=0\n"


@pytest.mark.parametrize("momento, trecho", [("partida", "antes de qualquer tentativa"), ("recusa", "Repetir é exatamente o certo")])
def test_comando_distingue_partida_de_diagnostico(monkeypatch, capsys, momento, trecho):
    monkeypatch.setenv("VPS_HOST", "host.invalid")
    monkeypatch.setenv("MOMENTO", momento)
    monkeypatch.delenv("GITHUB_OUTPUT", raising=False)
    monkeypatch.delenv("GITHUB_STEP_SUMMARY", raising=False)
    monkeypatch.setattr(sonda, "configurar_saida", lambda: None)
    monkeypatch.setattr(sonda, "medir_a_porta", lambda _host: (sonda.ATENDEU,))
    monkeypatch.setattr(sonda, "http_do_site", lambda _url: 200)
    assert sonda.main(["--sondar-porta"]) == 0
    assert trecho in capsys.readouterr().out


@pytest.mark.parametrize("concluida", [True, False])
def test_comando_resumir_grava_evidencia_sem_registrar_aprovacao(
    monkeypatch, tmp_path, concluida
):
    resumo = tmp_path / "resumo"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(resumo))
    for nome in ("R2", "R3", "V0", "V1", "V2", "SAIDA_2", "SAIDA_3"):
        monkeypatch.delenv(nome, raising=False)
    monkeypatch.setenv("CELULA", "admin")
    monkeypatch.setenv("R1", "success" if concluida else "failure")
    monkeypatch.setenv("SAIDA_1", "ENTREGA-CONCLUIDA: admin" if concluida else "erro de aplicação")
    monkeypatch.setattr(sonda, "configurar_saida", lambda: None)
    monkeypatch.setattr(sonda, "http_do_site", lambda _url: 200)
    assert sonda.main(["--resumir"]) == 0
    texto = resumo.read_text(encoding="utf-8")
    assert "admin" in texto
    assert "não identifica a imagem em uso" in texto
    assert "ESTÁ em produção" not in texto
    if concluida:
        assert "script de aplicação concluiu de primeira" in texto
        assert "sonda de rede não registra aprovação" in texto
    else:
        assert "sem conclusão confirmada" in texto


@pytest.mark.parametrize("site_http", [200, 503, None])
def test_conclusao_tecnica_nao_aprova_imagem_nem_garante_disponibilidade(site_http):
    entrega = sonda.Entrega(
        tentativas=("success",),
        marca_de_conclusao=True,
        site_http=site_http,
    )
    texto = sonda._desfecho(entrega)
    assert "sonda de rede não registra aprovação" in texto
    assert "ESTÁ em produção" not in texto
    if site_http == 200:
        assert "não identifica a imagem em uso" in texto
    elif site_http is None:
        assert "Não consegui medir" in texto
    else:
        assert "respondeu 503" in texto


def test_http_saudavel_sem_conclusao_nao_identifica_a_versao_ativa():
    texto = sonda._desfecho(sonda.Entrega(site_http=200))
    assert "sem conclusão confirmada" in texto
    assert "não identifica a imagem em uso" in texto
    assert "versão anterior" not in texto.lower()
