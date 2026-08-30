#!/usr/bin/env python3
"""A SONDA DA VPS — a medição que faltava DENTRO do deploy (armadilhas/127).

A `armadilhas/127` é a campeã de reincidência deste catálogo: 6 quedas em 3
dias. O deploy morre em `dial tcp ***:22: i/o timeout`, a VPS está viva, o site
responde 200 o tempo inteiro — é um soluço de rede entre o runner do GitHub e a
VPS. A entrada manda fazer três coisas, nesta ordem: **medir a porta 22**,
**repetir com pausa**, **parar na terceira**.

O QUE JÁ EXISTIA, E O QUE FALTAVA (TAR-013, 30/08/2026)
------------------------------------------------------
Duas das três já estavam no `deploy-celula.yml` desde 26/08/2026: três
tentativas, com 45 s e 60 s de pausa, e só a última decide o veredito. A
terceira — **medir** — não existia em lugar nenhum do deploy. Ela morava em dois
lugares fora dele: no texto da armadilha (um comando para o agente colar) e em
`ci/rerun_de_deploy.py`, que é a vacina do PC, rodada DEPOIS do fato, por um
robô que já percebeu o vermelho.

Sem a medição, o retry do deploy repete às cegas: ele trata TODO timeout de SSH
como o soluço da 127, inclusive quando é a `armadilhas/017` — a falha
PERMANENTE de configuração, em que nenhuma tentativa vai passar nunca. Gasta 105
segundos de pausa e três conexões para chegar a "a suspeita é a 017", que é um
palpite. Este módulo troca o palpite por uma medição, feita no lugar certo: **do
runner**, que é exatamente a ponta da conexão que engasga.

AS DUAS CARAS DESTE ARQUIVO
---------------------------
    python ci/sonda_da_vps.py --sondar-porta   # mede e decide (VPS_HOST no env)
    python ci/sonda_da_vps.py --resumir        # narra o que o deploy fez

A primeira roda no `deploy-celula.yml` entre as tentativas. A segunda roda no
fim do job e escreve, no resumo do run, o que aconteceu — em português de
resultado, não de processo. É o "registrando o que fez" da vacina: até aqui, um
deploy que se salvou na 2ª tentativa era indistinguível, para quem olha de fora,
de um deploy que passou de primeira, e o padrão da VPS recusando continuava
invisível.

POR QUE O `veredito` SAI POR `$GITHUB_OUTPUT`, E NÃO PELO EXIT CODE
-------------------------------------------------------------------
O workflow precisa distinguir TRÊS respostas — porta viva, porta morta, não
consegui medir — e o `outcome` de um passo do GitHub só tem duas
(`success`/`failure`). Ler a decisão do `outcome` juntaria "a porta está morta"
com "não consegui medir", que é precisamente a confusão que o [INV-CI01] existe
para proibir: **não medir nunca vira veredito**. Por isso o passo é
`continue-on-error: true` (o exit code não derruba o job) e o workflow lê
`steps.<id>.outputs.veredito`, nunca `steps.<id>.outcome`.

O exit code continua valendo para quem roda isto na mão, com a semântica da casa:

    0  PASS   a porta 22 respondeu — é o soluço da 127, repetir é o certo
    1  FAIL   a porta 22 NÃO respondeu — é a 017, e repetir é teatro
    2  ERROR  não consegui medir — e "não medi" nunca vira "pode repetir"

O QUE ESTA SONDA NUNCA FAZ
--------------------------
**Ela nunca reprova um deploy que ainda poderia dar certo.** A única direção em
que ela encurta o laço é a provada: quando as DUAS medições (depois da 1ª e
depois da 2ª tentativa) disserem que a porta está morta, o workflow pula a 3ª —
duas medições independentes concordando é evidência; uma é ruído. Porta viva ou
"não medi" mantêm o retry inteiro, exatamente como antes desta entrega. Uma
sonda que pudesse derrubar entrega boa seria uma arma, não uma vacina.

O DIA EM QUE ELA FOI ARMA MESMO ASSIM (TAR-026, 30/08/2026)
-----------------------------------------------------------
Horas depois de nascer, esta sonda gritou `permanente` — o único veredito que
faz o deploy DESISTIR — sobre uma VPS que estava **viva**. Run 33312655853,
tentativa 1, deploy da `admin` (PR #589): as três medições disseram "porta
morta"; o mantenedor sondou a porta 22 do PC na MESMA janela e recebeu
`SSH-2.0-OpenSSH_9.6p1`; `gh run rerun --failed` subiu em 1min02s. Era a 127,
não a 017 — e a mensagem categórica dizia o contrário, com encaminhamento e
tudo. É o irmão do falso-verde: o **falso-vermelho categórico**, pior de um
jeito, porque parece diagnóstico em vez de dúvida.

O log daquele run entrega a causa em duas linhas, e nenhuma delas é palpite:

1. **Cada medição durou 25 s: 10 s de estouro de tempo na porta 22 + 15 s de
   estouro de tempo no site.** Nenhuma conexão foi recusada — todas ficaram
   MUDAS. E o código antigo jogava `socket.timeout` no MESMO `except` de
   `ConnectionError`, devolvendo `False` = "porta morta" para as duas coisas.
   Só que "estourou o tempo" é a assinatura LITERAL da 127 (`i/o timeout`): a
   sonda reproduzia o próprio soluço que existe para diagnosticar e então o
   declarava permanente. Circular.
2. **A testemunha estava do lado e era ignorada.** As três medições também não
   alcançaram `https://meshcraft.top/healthz` — que servia 200 para o mundo
   inteiro naquele minuto. Quem estava cego era o RUNNER, não a porta. O
   `site_http` só era usado para escrever um recado no fim; nunca entrava na
   decisão.

AS TRÊS REGRAS QUE SAÍRAM DISSO
-------------------------------
- **Silêncio não é resposta.** `sondar_uma_vez` devolve SEIS sinais, não um
  booleano: `ATENDEU` · `NAO_E_SSH` · `RECUSOU` · `NOME_NAO_RESOLVE` ·
  `SEM_RESPOSTA` (estourou o tempo) · `NAO_PERGUNTEI`. Os três do meio são
  respostas NEGATIVAS da rede — alguém do outro lado falou. `SEM_RESPOSTA` é
  silêncio, e silêncio vindo de um runner cujo cabo é justamente o suspeito não
  prova nada sobre a VPS.
- **`permanente` exige mais de UMA sondagem.** Cada chamada da sonda mede
  `SONDAGENS_POR_MEDICAO` vezes (parando cedo se a porta atender, que é o caso
  feliz e barato). Uma sondagem sozinha nunca produz `permanente`, em lugar
  nenhum — a lição que o desenho da TAR-013 já aplicava ao workflow, agora
  aplicada dentro da própria medição.
- **Na dúvida, `nao_medi`.** Aqui fail-closed significa CONTINUAR TENTANDO:
  repetir à toa custa 45 s; desistir à toa custa uma entrega que não chega ao
  site, em silêncio. Só o silêncio CORROBORADO pela testemunha do site (o
  runner alcança a internet pública, mas não a porta 22) vira `permanente` —
  que é exatamente a forma da 017, e é por isso que ela continua acontecendo.

O host vem por `env`, nunca por argumento: `VPS_HOST` é segredo do repositório,
e argumento aparece na tabela de processos e em qualquer eco de comando. Nada
aqui imprime o host — nem no acerto, nem no erro.
"""

from __future__ import annotations

import argparse
import os
import socket
import sys
import time
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import configurar_saida  # noqa: E402

# O IP da VPS (`reference_vps_acesso_estado`): serve de padrão para quem roda
# isto na mão, do PC. No runner o valor vem do segredo `VPS_HOST`.
VPS_PADRAO = "217.196.62.220"
BANNER_SSH = "SSH-2.0"
SONDA_DO_SITE = "https://meshcraft.top/healthz"
ESPERA_DO_SOCKET_S = 10

# Quantas vezes UMA chamada da sonda pergunta pela porta 22 antes de concluir
# qualquer coisa (TAR-026). Três, e não uma, porque a medição que mentiu no run
# 33312655853 era uma só, repetida às cegas pelo workflow. A sonda para cedo
# quando a porta ATENDE — no deploy saudável isto custa milissegundos, que é o
# caso de quase todo run. Pior caso: 3 × 10 s + 2 × 2 s = 34 s, um teto fixo e
# conferível, nunca uma espera aberta (RITOS §2 peça 6).
SONDAGENS_POR_MEDICAO = 3
PAUSA_ENTRE_SONDAGENS_S = 2
# Nenhuma sondagem sozinha decide `permanente`. Em lugar nenhum.
MEDICOES_MINIMAS_PARA_PERMANENTE = 2

BLIP = "blip"
PERMANENTE = "permanente"
NAO_MEDI = "nao_medi"

# OS SEIS SINAIS DE UMA SONDAGEM — e por que um booleano não bastava.
#
# Até 30/08/2026 a medição era `bool | None`, e `socket.timeout` caía no MESMO
# `except` de `ConnectionError`: as duas viravam `False` = "porta morta". Mas
# "recusou a conexão" e "estourou o tempo" são fatos DIFERENTES sobre o mundo:
#
#   recusa  ⇒ o pacote chegou em algum lugar e voltou um "não" — é RESPOSTA.
#   estouro ⇒ ninguém disse nada — é SILÊNCIO, e é a assinatura literal do
#             soluço da armadilhas/127 (`dial tcp ***:22: i/o timeout`).
#
# Dar o mesmo veredito às duas fazia a sonda declarar PERMANENTE justamente no
# sintoma da falha INTERMITENTE (`armadilhas/209`).
ATENDEU = "atendeu"                      # falou o banner de SSH: a porta está viva
NAO_E_SSH = "nao_e_ssh"                  # a conexão abriu, mas quem está lá não é SSH
RECUSOU = "recusou"                      # levou um "não" da rede: resposta negativa
NOME_NAO_RESOLVE = "nome_nao_resolve"    # o DNS respondeu "não existe": resposta negativa
SEM_RESPOSTA = "sem_resposta"            # estourou o tempo: SILÊNCIO, não resposta
NAO_PERGUNTEI = "nao_perguntei"          # a sonda falhou antes de perguntar

# As que provam que alguém do outro lado existe e disse "não". Duas delas
# concordando bastam para `permanente`: são a assinatura da armadilhas/017.
RESPOSTAS_NEGATIVAS = frozenset({NAO_E_SSH, RECUSOU, NOME_NAO_RESOLVE})

# A sentinela que `infra/deploy-celula-na-vps.sh` imprime na última linha e que
# o passo "A entrega rodou mesmo?" EXIGE ver — a cura do verde que não subiu
# nada (28/08/2026). O narrador procura a mesma marca, e não uma variação dela:
# `ci/tests/test_sonda_da_vps.py` reprova se as três cópias divergirem, porque
# duas grafias diferentes fariam o resumo do run contar uma história e o portão
# do workflow contar outra sobre a mesma entrega.
MARCA_DE_CONCLUSAO = "ENTREGA-CONCLUIDA:"


@dataclass
class Medicao:
    """O mundo, medido. Separado da decisão para que a tabela inteira seja
    testável sem rede, sem VPS e sem runner — as três coisas que não se
    produzem sob encomenda."""

    porta22: bool | None = None  # None = NÃO MEDI, sempre
    site_http: int | None = None
    host_declarado: bool = True
    # A MESMA medição responde a DUAS perguntas diferentes conforme o momento.
    # Depois de uma recusa: "o que acabou de falhar foi a rede?" — e aí "repetir
    # é o certo" é a conclusão. Na partida, ANTES de qualquer tentativa, nada
    # falhou: dizer ali "o que falhou foi a rede" seria uma frase falsa no log
    # de TODO deploy saudável, e mensagem que mente gasta a confiança de que a
    # mensagem certa precisa.
    apos_recusa: bool = True
    # O DETALHE DE CADA SONDAGEM, em ordem (TAR-026). `porta22` continua sendo o
    # resumo de uma linha — é o que a vacina do PC consome —, mas o resumo perde
    # justamente a informação que separa a 127 da 017: se a porta ficou MUDA ou
    # se ela RESPONDEU "não". Quem decide precisa dos dois.
    #
    # Vazio significa "não sei em quantas sondagens este resumo se baseia", e a
    # tabela trata isso como o que é: falta de corroboração, nunca licença para
    # dizer `permanente`.
    sinais: tuple[str, ...] = ()


def resumo_dos_sinais(sinais: tuple[str, ...] | list[str]) -> bool | None:
    """As N sondagens, resumidas na tri-estado que o resto da casa consome.

    `True`  — alguma sondagem ouviu o banner. Uma basta: ninguém fica vivo por
              acidente, e a porta não precisa de corroboração para estar viva.
    `False` — TODAS as sondagens levaram resposta negativa da rede, e foram pelo
              menos duas. Só aqui a palavra "morta" é honesta.
    `None`  — qualquer outra coisa: silêncio, mistura, sondagem única, defeito
              da própria sonda. É o `nao_medi`, e ele nunca vira `permanente`.
    """
    sinais = tuple(sinais)
    if not sinais:
        return None
    if ATENDEU in sinais:
        return True
    negativas = sum(1 for sinal in sinais if sinal in RESPOSTAS_NEGATIVAS)
    if negativas == len(sinais) and negativas >= MEDICOES_MINIMAS_PARA_PERMANENTE:
        return False
    return None


@dataclass
class Veredito:
    veredito: str  # BLIP | PERMANENTE | NAO_MEDI
    codigo: int  # 0 PASS · 1 FAIL · 2 ERROR
    motivo: str
    recado: str = ""
    # Em quantas sondagens este veredito se baseia. Vai na mensagem e no
    # `$GITHUB_OUTPUT`: quem lê "a porta está morta" tem direito de saber se
    # isso foi medido uma vez ou três (TAR-026).
    medicoes: int = 0


def decidir_pela_sonda(medicao: Medicao) -> Veredito:
    """A tabela de decisão da sonda — pura, completa e sem rede.

    Ela responde uma pergunta só, e é a pergunta que a `armadilhas/127` manda
    fazer antes de repetir: *o problema é a rede engasgando (a 127) ou a porta
    fechada (a 017)?* Confundir as duas custa nos dois sentidos — repetir uma
    falha permanente é teatro, e desistir de um soluço é deixar o merge fora do
    ar por nada.

    A ORDEM DAS PERGUNTAS É A LEI DESTA TABELA (TAR-026):

    1. Tenho alvo? Não ⇒ `nao_medi`.
    2. Alguma sondagem ouviu o banner? Sim ⇒ `blip`. Uma basta: viva é viva.
    3. Tenho pelo menos DUAS sondagens? Não ⇒ `nao_medi`. Uma medição sozinha
       não manda o deploy desistir de nada, nunca.
    4. Alguma sondagem falhou por defeito da própria sonda? Sim ⇒ `nao_medi`.
    5. TODAS levaram resposta negativa da rede (recusa, DNS, quem atendeu não é
       SSH)? Sim ⇒ `permanente`. Alguém do outro lado disse "não", N vezes.
    6. Sobrou o silêncio — e aí a testemunha decide: se o site público responde
       DESTE runner, a saída dele funciona e o buraco é a porta 22 ⇒
       `permanente`. Se nem o site responde, quem está cego é o runner ⇒
       `nao_medi`, e o retry segue inteiro.
    """
    sinais = tuple(medicao.sinais)
    quantas = len(sinais)
    viva = medicao.porta22 is True or ATENDEU in sinais
    negativas = sum(1 for sinal in sinais if sinal in RESPOSTAS_NEGATIVAS)
    silencios = sum(1 for sinal in sinais if sinal == SEM_RESPOSTA)

    if not medicao.host_declarado:
        return Veredito(
            NAO_MEDI, 2,
            "não recebi o endereço da VPS (`VPS_HOST` vazio) — sem alvo não há "
            "o que sondar, e 'não medi' nunca vira 'a porta está morta'.",
            "O retry segue inteiro, como se esta sonda não existisse.",
            medicoes=quantas,
        )
    if viva and not medicao.apos_recusa:
        return Veredito(
            BLIP, 0,
            "a porta 22 da VPS RESPONDEU o banner de SSH deste runner, antes de "
            "qualquer tentativa. É a linha de base do deploy: no minuto em que "
            "ele começou, a VPS estava alcançável daqui.",
            medicoes=quantas,
        )
    if viva:
        return Veredito(
            BLIP, 0,
            "a porta 22 da VPS RESPONDEU o banner de SSH agora, deste runner. "
            "A VPS está viva e alcançável: o que falhou foi a rede no momento "
            "da tentativa — é o soluço intermitente da armadilhas/127, não a "
            "017. Repetir é exatamente o certo.",
            _recado_do_site(medicao.site_http),
            medicoes=quantas,
        )

    # Daqui para baixo a porta não atendeu. A pergunta deixa de ser "a porta
    # está morta?" e passa a ser a única honesta: **isto é evidência sobre a
    # VPS, ou sobre o runner?** (TAR-026 — foi confundir as duas que fez a sonda
    # gritar 017 com a VPS viva, no run 33312655853.)
    if quantas < MEDICOES_MINIMAS_PARA_PERMANENTE:
        return Veredito(
            NAO_MEDI, 2,
            _porque_nao_bastou(quantas)
            + " Sem corroboração não dá para separar a armadilhas/127 da 017, e "
            "a ausência de evidência não é evidência de nada [INV-CI01].",
            "O retry segue inteiro: uma sonda que não mediu — ou que mediu uma "
            "vez só — não tira tentativa de ninguém.",
            medicoes=quantas,
        )
    if negativas + silencios < quantas:
        return Veredito(
            NAO_MEDI, 2,
            f"{_quantas(quantas)} pela porta 22, e "
            f"{quantas - negativas - silencios} delas nem chegaram a perguntar "
            "(a sonda falhou antes da conexão: socket bloqueado pelo próprio "
            "runner). Defeito do instrumento não vira veredito sobre a VPS "
            "[INV-CI01].",
            "O retry segue inteiro.",
            medicoes=quantas,
        )
    if negativas == quantas:
        return _permanente(
            medicao, quantas,
            f"a porta 22 da VPS RESPONDEU 'não' nas {_quantas(quantas)} feitas "
            f"deste runner ({_detalhe(sinais)}). Não é silêncio de rede: em "
            "todas elas alguém do outro lado respondeu, e não era SSH.",
        )
    if medicao.site_http is not None:
        return _permanente(
            medicao, quantas,
            f"a porta 22 da VPS ficou MUDA nas {_quantas(quantas)} feitas deste "
            f"runner ({_detalhe(sinais)}) — mas o site público respondeu "
            f"{medicao.site_http} DAQUI, na mesma janela. A saída do runner "
            "está funcionando; o buraco é a porta 22, e só ela.",
        )
    return Veredito(
        NAO_MEDI, 2,
        f"a porta 22 da VPS ficou MUDA nas {_quantas(quantas)} feitas deste "
        f"runner ({_detalhe(sinais)}) — e daqui eu também NÃO alcancei o site "
        "público, que serve 200 para o mundo. Quem está cego é o runner, não a "
        "porta: estouro de tempo é a assinatura literal do soluço da "
        "armadilhas/127 (`i/o timeout`), e chamar isso de 017 seria a sonda "
        "diagnosticar o próprio engasgo como defeito da VPS (armadilhas/209).",
        "O retry segue inteiro — e é isso que fail-closed significa aqui: "
        "repetir à toa custa 45 s, desistir à toa custa a entrega.",
        medicoes=quantas,
    )


def _permanente(medicao: Medicao, quantas: int, medido: str) -> Veredito:
    """A única mensagem que manda o deploy desistir — e ela diz em quantas
    medições se baseia, porque quem lê "falha permanente" tem direito de saber
    se isso foi medido uma vez ou três (TAR-026)."""
    if not medicao.apos_recusa:
        return Veredito(
            PERMANENTE, 1,
            f"{medido} Isto é a linha de base — foi medido ANTES da primeira "
            "tentativa. Se a entrega falhar a seguir, a causa já está nomeada: "
            "é a assinatura da armadilhas/017 (falha permanente de alcance), "
            "não o soluço da 127. Esta medição sozinha NÃO interrompe nada: "
            "quem decide é o par de medições tomadas depois das recusas reais.",
            _recado_do_site(medicao.site_http),
            medicoes=quantas,
        )
    return Veredito(
        PERMANENTE, 1,
        f"{medido} Isso não é o soluço da armadilhas/127 — é a assinatura da "
        "017: falha PERMANENTE de alcance (o que o VPS_HOST resolve? há CDN na "
        "frente? o firewall passou a recusar a faixa dos runners?). Nenhuma "
        "tentativa nova vai passar, e o conserto é de configuração — território "
        "do mantenedor (Lei 5).",
        _recado_do_site(medicao.site_http),
        medicoes=quantas,
    )


def _quantas(quantas: int) -> str:
    return "1 sondagem" if quantas == 1 else f"{quantas} sondagens seguidas"


def _porque_nao_bastou(quantas: int) -> str:
    if quantas == 0:
        return (
            "não consegui medir a porta 22 da VPS — não sobrou nenhuma sondagem "
            "utilizável, e a sonda não sabe em quantas medições se apoiaria."
        )
    return (
        "a porta 22 da VPS não atendeu, mas isto foi UMA sondagem só — e uma "
        "sondagem sozinha nunca manda o deploy desistir. Um engasgo momentâneo "
        f"do próprio runner produz exatamente esta leitura (mínimo exigido: "
        f"{MEDICOES_MINIMAS_PARA_PERMANENTE})."
    )


_NOME_DO_SINAL = {
    ATENDEU: "atendeu falando SSH",
    NAO_E_SSH: "atendeu sem falar SSH",
    RECUSOU: "recusou a conexão",
    NOME_NAO_RESOLVE: "o nome não resolve",
    SEM_RESPOSTA: "estourou o tempo",
    NAO_PERGUNTEI: "nem cheguei a perguntar",
}


def _detalhe(sinais: tuple[str, ...]) -> str:
    """O que cada sondagem viu, contado — para que a mensagem seja falsificável
    em vez de categórica."""
    vistos: dict[str, int] = {}
    for sinal in sinais:
        vistos[sinal] = vistos.get(sinal, 0) + 1
    return "; ".join(
        f"{_NOME_DO_SINAL.get(sinal, sinal)} em {contagem}"
        for sinal, contagem in vistos.items()
    ) or "sem detalhe"


def _recado_do_site(codigo: int | None) -> str:
    """A frase que o mantenedor precisa ouvir, e que é fácil esquecer.

    Deploy vermelho por SSH significa que a imagem NOVA não subiu — a ANTIGA
    continua servindo. Ninguém fica fora do ar, mas o merge não está em
    produção até o verde. Anunciar a entrega como "no ar" nesse estado já
    aconteceu nesta casa mais de uma vez (armadilhas/127).
    """
    if codigo == 200:
        return (
            "O site continua no ar servindo a versão ANTERIOR — ninguém ficou "
            "fora do ar. Mas o que foi mergeado NÃO está em produção enquanto "
            "este deploy não ficar verde."
        )
    if codigo is None:
        return (
            "Não consegui medir o site pela internet pública daqui — o que não "
            "significa que ele esteja fora do ar; significa que não medi."
        )
    return (
        f"ATENÇÃO: a sonda pública do site respondeu {codigo}, não 200. Isso é "
        "outra coisa, além do deploy — confira o ar."
    )


# ------------------------------------------------------------------ o mundo --


def sondar_uma_vez(host: str, porta: int = 22) -> str:
    """UMA pergunta à porta 22, respondida com o SINAL exato (TAR-026).

    Esta função não devolve booleano de propósito. O que ela sabe é *como* a
    conversa terminou, e é essa distinção que separa a `armadilhas/127` da
    `017`:

    - `ATENDEU` — falou o banner. A porta está viva; acabou a discussão.
    - `NAO_E_SSH` — a conexão ABRIU e quem estava lá não falou SSH (calou-se ou
      falou outra coisa). É resposta negativa: existe alguém na porta 22, e não
      é a VPS que queremos. Assinatura de CDN/proxy na frente — a 017.
    - `RECUSOU` — a rede devolveu um "não". Resposta negativa.
    - `NOME_NAO_RESOLVE` — o DNS disse "não existe". Resposta negativa, e a 017
      clássica (`VPS_HOST` com nome em vez de IP).
    - `SEM_RESPOSTA` — estourou o tempo. **Silêncio, não resposta.** É a
      assinatura literal do soluço da 127 (`dial tcp ***:22: i/o timeout`), e
      tratá-la como "porta morta" foi exatamente o que fez a sonda declarar
      falha permanente sobre uma VPS viva (run 33312655853).
    - `NAO_PERGUNTEI` — a sonda falhou antes de perguntar (socket bloqueado
      pelo próprio runner). Defeito do instrumento.

    `porta` existe para que o guarda possa apontar a sonda para um servidor de
    mentira e provar as respostas em milissegundos, sem rede e sem VPS. Em
    produção ela nunca é passada: a única porta que interessa é a 22.
    """
    try:
        conexao = socket.create_connection((host, porta), timeout=ESPERA_DO_SOCKET_S)
    except (socket.timeout, TimeoutError):
        return SEM_RESPOSTA  # ninguém disse nada: SILÊNCIO, e silêncio não decide
    except socket.gaierror:
        return NOME_NAO_RESOLVE  # o DNS respondeu, e a resposta foi "não existe"
    except ConnectionError:
        return RECUSOU  # levei um "não" da rede: isso é resposta
    except OSError:
        return NAO_PERGUNTEI  # a sonda falhou antes de perguntar: NÃO MEDI
    with conexao:
        # A conexão ABRIU: alguém existe na porta 22. Se ele não fala SSH — nem
        # que seja ficando mudo —, isso É resposta sobre quem está lá.
        conexao.settimeout(ESPERA_DO_SOCKET_S)
        try:
            banner = conexao.recv(64).decode("utf-8", "replace")
        except OSError:
            return NAO_E_SSH
    return ATENDEU if BANNER_SSH in banner else NAO_E_SSH


def medir_a_porta(
    host: str,
    porta: int = 22,
    sondagens: int = 0,
) -> tuple[str, ...]:
    """A MEDIÇÃO — `sondagens` perguntas seguidas, não uma (TAR-026).

    Ela para cedo quando a porta ATENDE, porque uma resposta positiva encerra a
    dúvida e porque esse é o caminho de quase todo deploy: no run saudável isto
    custa milissegundos. O caminho caro é justamente o duvidoso, e nele gastar
    34 s para não abandonar uma entrega é troca óbvia.
    """
    sondagens = sondagens or SONDAGENS_POR_MEDICAO
    sinais: list[str] = []
    for numero in range(1, max(1, sondagens) + 1):
        sinal = sondar_uma_vez(host, porta)
        sinais.append(sinal)
        if sinal == ATENDEU:
            break
        if numero < sondagens and PAUSA_ENTRE_SONDAGENS_S:
            time.sleep(PAUSA_ENTRE_SONDAGENS_S)
    return tuple(sinais)


def porta_22_responde(host: str, porta: int = 22) -> bool | None:
    """A porta 22 da VPS responde? `None` = não consegui medir. A MESMA medição
    que o deploy faz de dentro do runner — a vacina do PC (`rerun_de_deploy.py`)
    consome esta, para que as duas não possam discordar sobre o mesmo fato.

    A distinção entre `False` e `None` é o coração do arquivo, e desde a TAR-026
    ela ficou mais estreita de propósito: `False` só sai quando **todas** as
    sondagens (mínimo de {MEDICOES_MINIMAS_PARA_PERMANENTE}) levaram resposta
    negativa da rede. Silêncio — estouro de tempo — devolve `None`, porque
    silêncio é o sintoma da falha INTERMITENTE, e lê-lo como porta morta fazia a
    vacina virar arma.
    """
    return resumo_dos_sinais(medir_a_porta(host, porta))


def http_do_site(url: str = SONDA_DO_SITE) -> int | None:
    """O site responde pela internet pública? `None` = não consegui medir.

    A prova de que algo funciona em produção se mede do lado do usuário
    (RETROSPECTIVA-FASE-D §3), não perguntando ao container.
    """
    import urllib.error
    import urllib.request

    try:
        with urllib.request.urlopen(url, timeout=15) as resposta:
            return int(resposta.status)
    except urllib.error.HTTPError as erro:
        return int(erro.code)
    except Exception:
        return None


def _escrever_saida_do_passo(veredito: str, medicoes: int) -> None:
    """`veredito=...` e `sondagens=...` em `$GITHUB_OUTPUT` — o canal do workflow.

    O `sondagens` existe desde a TAR-026 para que a mensagem de PARADA do
    `deploy-celula.yml` possa dizer, ela também, em quantas medições a desistência
    se baseia. Número que só o script conhece e o run não repete é número que
    ninguém confere.

    Falha de escrita aqui NÃO derruba nada: fora do Actions a variável não
    existe, e este script precisa continuar rodando na mão.
    """
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"veredito={veredito}\n")
            arquivo.write(f"sondagens={medicoes}\n")
    except OSError as erro:
        print(f"(não consegui escrever em GITHUB_OUTPUT: {erro})", file=sys.stderr)


def _escrever_no_resumo(texto: str) -> None:
    """O resumo do run — a página que se abre sem cavar log."""
    caminho = os.environ.get("GITHUB_STEP_SUMMARY")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(texto.rstrip() + "\n\n")
    except OSError as erro:
        print(f"(não consegui escrever no resumo do run: {erro})", file=sys.stderr)


# ----------------------------------------------------------------- a narrativa --

# Como cada tentativa aparece no resumo. `skipped` é o caso normal e feliz: a
# 2ª e a 3ª nem existem quando a 1ª atende.
_FALA_DA_TENTATIVA = {
    "success": "a VPS **atendeu**",
    "failure": "a VPS **recusou a conexão**",
    "skipped": "não foi preciso",
    "": "não foi preciso",
}

_FALA_DO_VEREDITO = {
    BLIP: (
        "a porta 22 **respondeu** deste runner — a VPS está viva, foi soluço de "
        "rede (armadilhas/127)"
    ),
    PERMANENTE: (
        "a porta 22 **não respondeu** deste runner — isto não é soluço; é falha "
        "de alcance (armadilhas/017)"
    ),
    NAO_MEDI: "**não consegui medir** a porta 22 — e não medir não é veredito",
    "": "",
}

# A medição de PARTIDA fala outra língua, de propósito. Ela acontece antes de
# qualquer tentativa, então não há falha para diagnosticar: ela é a linha de
# base ("a porta estava alcançável às HH:MM?"), e chamá-la de soluço citaria uma
# armadilha em deploys perfeitamente normais — alarme que grita no caso certo é
# alarme que se aprende a ignorar.
_FALA_DA_PARTIDA = {
    BLIP: "a porta 22 da VPS estava alcançável deste runner",
    PERMANENTE: (
        "a porta 22 da VPS **já não respondia** deste runner antes mesmo da "
        "primeira tentativa"
    ),
    NAO_MEDI: "**não consegui medir** a porta 22 antes de começar",
    "": "",
}


@dataclass
class Entrega:
    """O que o job fez, do jeito que o YAML sabe contar."""

    celula: str = ""
    tentativas: tuple[str, ...] = ()
    sondas: tuple[str, ...] = ()  # a de antes de tudo vem primeiro
    marca_de_conclusao: bool = False
    site_http: int | None = None


def narrar(entrega: Entrega) -> str:
    """O registro do que o deploy fez, em português de resultado.

    Por que isto existe: até esta entrega, um deploy que se salvou na 2ª
    tentativa era, para quem olha de fora, idêntico a um que passou de primeira
    — o padrão da VPS recusando ficava invisível justamente nos dias em que ela
    mais recusou. O log preservava as tentativas; ninguém lê log. O resumo do
    run é a primeira coisa que aparece ao abrir a execução.
    """
    linhas = [f"## Deploy da célula `{entrega.celula or '?'}` — o que aconteceu"]

    antes = entrega.sondas[0] if entrega.sondas else ""
    if antes:
        linhas.append(f"- **Antes de começar:** {_FALA_DA_PARTIDA.get(antes, antes)}.")

    depois = list(entrega.sondas[1:])
    for indice, resultado in enumerate(entrega.tentativas, start=1):
        fala = _FALA_DA_TENTATIVA.get(resultado, f"terminou `{resultado}`")
        linhas.append(f"- **{indice}ª tentativa de ativar na VPS:** {fala}.")
        if indice <= len(depois) and depois[indice - 1]:
            veredito = depois[indice - 1]
            linhas.append(
                f"  - Medição logo depois: {_FALA_DO_VEREDITO.get(veredito, veredito)}."
            )

    linhas.append(
        "- **A entrega rodou mesmo na VPS?** "
        + (
            "Sim — a marca de conclusão do script apareceu."
            if entrega.marca_de_conclusao
            else "**Não** — nenhuma tentativa produziu a marca de conclusão."
        )
    )
    if entrega.site_http is not None:
        linhas.append(
            f"- **O site, medido daqui pela internet pública:** {entrega.site_http}."
        )
    else:
        linhas.append("- **O site:** não consegui medir daqui (não é 'está fora').")

    linhas.append("")
    linhas.append(_desfecho(entrega))
    return "\n".join(linhas)


def _desfecho(entrega: Entrega) -> str:
    vitoriosa = next(
        (i for i, r in enumerate(entrega.tentativas, start=1) if r == "success"), 0
    )
    if entrega.marca_de_conclusao and vitoriosa == 1:
        return (
            "**Resultado: a versão nova ESTÁ em produção**, e a VPS atendeu de "
            "primeira — nada de anormal neste deploy."
        )
    if entrega.marca_de_conclusao and vitoriosa:
        return (
            f"**Resultado: a versão nova ESTÁ em produção** — mas foram precisas "
            f"{vitoriosa} tentativas. A VPS recusou a conexão antes de aceitar: é "
            "a armadilhas/127 mordendo de novo, e o deploy sobreviveu sozinho, "
            "sem ninguém pedir rerun. Registre a ocorrência em `painel/registros/`."
        )
    # O resumo só acusa a 017 quando TODAS as medições de recusa concordaram, e
    # foram pelo menos duas — a mesma régua do passo de parada do workflow
    # (TAR-026). Antes bastava UMA dizer `permanente` para o resumo do run
    # declarar "falha de alcance, passa pelo mantenedor": a mensagem categórica
    # de novo, agora na página que o mantenedor abre primeiro.
    depois = [sonda for sonda in entrega.sondas[1:] if sonda]
    if len(depois) >= MEDICOES_MINIMAS_PARA_PERMANENTE and all(
        sonda == PERMANENTE for sonda in depois
    ):
        return (
            "**Resultado: a versão nova NÃO subiu, e não é soluço de rede.** A "
            f"porta 22 não respondeu deste runner em NENHUMA das {len(depois)} "
            "medições, cada uma tomada depois de uma recusa real — é a "
            "armadilhas/017, falha de alcance. O site continua servindo a versão "
            "anterior; repetir o run não vai adiantar enquanto a porta não "
            "voltar. Isto passa pelo mantenedor (Lei 5)."
        )
    return (
        "**Resultado: a versão nova NÃO subiu.** O site continua servindo a "
        "versão anterior — ninguém ficou fora do ar —, mas o que foi mergeado "
        "não está em produção. Diagnóstico e repetição: "
        "`python ci/rerun_de_deploy.py --run <id>`."
    )


def _tupla_do_env(*nomes: str) -> tuple[str, ...]:
    return tuple((os.environ.get(nome) or "").strip() for nome in nomes)


# --------------------------------------------------------------------- main --


def _sondar(args: argparse.Namespace) -> int:
    host = (os.environ.get("VPS_HOST") or "").strip()
    # `MOMENTO=partida` é a medição de linha de base, antes de qualquer
    # tentativa. Sem a variável, o padrão é "depois de uma recusa" — que é o
    # caso de quem roda isto na mão, do PC, diagnosticando um vermelho.
    medicao = Medicao(
        host_declarado=bool(host),
        apos_recusa=(os.environ.get("MOMENTO") or "").strip() != "partida",
    )
    if host:
        medicao.sinais = medir_a_porta(host)
        medicao.porta22 = resumo_dos_sinais(medicao.sinais)
        # A TESTEMUNHA, e ela é obrigatória (TAR-026). O site público responde
        # DESTE runner? É o que separa "a porta 22 está morta" de "eu estou
        # cego": no run 33312655853 as três medições da porta estouraram o tempo
        # e o site TAMBÉM não respondeu daqui, servindo 200 para o mundo — e a
        # sonda, que só usava este número para um recado no fim, culpou a VPS.
        medicao.site_http = http_do_site(args.site)
    decisao = decidir_pela_sonda(medicao)

    _escrever_saida_do_passo(decisao.veredito, decisao.medicoes)
    marca = {BLIP: "🌐", PERMANENTE: "🧱", NAO_MEDI: "❓"}[decisao.veredito]
    corpo = f"{marca} **A porta 22 da VPS, medida do runner:** {decisao.motivo}"
    if decisao.recado:
        corpo += f"\n\n{decisao.recado}"
    print(corpo.replace("**", ""))
    _escrever_no_resumo(corpo)
    estado = {0: "PASS", 1: "FAIL", 2: "ERROR"}[decisao.codigo]
    print(f"RESULTADO  {estado}")
    return decisao.codigo


def _resumir(args: argparse.Namespace) -> int:
    # A marca é procurada nas MESMAS saídas capturadas que o passo "A entrega
    # rodou mesmo?" examina — e não num sinalizador que aquele passo teria
    # passado adiante. Motivo: quando a 3ª tentativa falha, aquele passo NEM
    # RODA (o job já morreu), e um sinalizador vindo dele estaria vazio
    # justamente no caso em que a narrativa mais importa.
    saidas = "\n".join(_tupla_do_env("SAIDA_1", "SAIDA_2", "SAIDA_3"))
    entrega = Entrega(
        celula=(os.environ.get("CELULA") or "").strip(),
        tentativas=_tupla_do_env("R1", "R2", "R3"),
        sondas=_tupla_do_env("V0", "V1", "V2"),
        marca_de_conclusao=MARCA_DE_CONCLUSAO in saidas,
        site_http=http_do_site(args.site),
    )
    texto = narrar(entrega)
    print(texto)
    _escrever_no_resumo(texto)
    return 0  # o narrador conta o que houve; quem reprova são os passos acima


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="A sonda da VPS dentro do deploy (armadilhas/127): mede a "
                    "porta 22 do runner e narra o que o deploy fez."
    )
    acao = parser.add_mutually_exclusive_group(required=True)
    acao.add_argument("--sondar-porta", action="store_true",
                      help="mede a porta 22 (host em VPS_HOST) e decide")
    acao.add_argument("--resumir", action="store_true",
                      help="narra o que o deploy fez, para o resumo do run")
    parser.add_argument("--site", default=SONDA_DO_SITE)
    args = parser.parse_args(argv)
    if args.sondar_porta:
        return _sondar(args)
    return _resumir(args)


if __name__ == "__main__":
    sys.exit(main())
