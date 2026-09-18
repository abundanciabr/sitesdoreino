"""F0 do laco de melhoria continua: a regua e o corpus congelados.

Plano: docs/decisoes/RELATORIO-LACO-DE-MELHORIA-CONTINUA.md, Fase 0.

Este arquivo NAO mede nada em rede e NAO exercita ci/termometro.py. Ate F1 ele
e corpus congelado, nao teste do modulo. O que ele guarda e o REGISTRO das 37
janelas de indisponibilidade por celula colhidas da API do Actions em
18/09/2026. Nenhum total e digitado: duracao, soma e ranking saem de funcao
sobre o registro, e uma janela mexida move a conta.

Cada janela carrega as suas proprias ancoras: run, job e tentativa de
ABERTURA, os mesmos tres de FECHAMENTO, a lista dos jobs vermelhos de dentro
e, quando nao houve atribuicao, o motivo da exclusao. E carrega DOIS EIXOS
que nao se misturam: o GABARITO auditado a mao (`armadilha_esperada`, com a
linha literal que o sustenta em `evidencia_do_rotulo`) e a SAIDA DO DETECTOR
DE HOJE (`sinais_observados_pelo_detector_atual`), que e o defeito que a
Fase 1 existe para consertar. Todo total sai do gabarito, e o nome da funcao
diz isso: `celula_minutos_esperados`.
Duracao nao e campo: ela se deriva dos carimbos, para nao existir um segundo
lugar onde o mesmo fato possa divergir.

A classificacao anda em quatro eixos separados, como manda o INV-R11, em vez
de um campo so misturando id de armadilha, ambiguidade, ausencia e causa nao
catalogada:

  armadilha   o numero do catalogo, ou None quando nenhum responde pelo fato
  natureza    ocorrencia_operacional, ERROR_ambiguidade, ERROR_sem_casamento
  desfecho    interceptada, mitigada, sem_guarda, desconhecida
  causa       o que aconteceu, em palavras, mesmo sem armadilha que a cubra

Quatro fatos medidos que o relatorio-plano nao tinha:

1. O log do Actions guarda o texto em UTF-8 DUPLAMENTE codificado. A palavra
   "nao" com til vira os bytes C3 83 C2 A3. Um sinal escrito com acento casa
   ZERO dos 48 logs que contem a recusa da 088.

2. O eco tem DUAS formas, e so uma carrega ANSI. Um passo `run:` ecoa a fonte
   em ciano-negrito (ESC[36;1m ... ESC[0m); a ssh-action, ate 28/08/2026,
   ecoava `script:` CRU, sem cor nenhuma. A marca que pega as duas e a
   variavel NAO EXPANDIDA: o eco imprime `'$CELULA'` e a execucao imprime o
   nome da celula. O carimbo de tempo nao separa nada no log bruto da API,
   porque eco e execucao o tem; a tabela da armadilha 114 vale para outra
   fonte, a visao do `gh run view --log-failed`.

3. A recusa da 088 MENTE quando o compose nao interpola uma variavel
   obrigatoria: a versao antiga do script caia no mesmo ramo. Duas das dez
   janelas que a assinatura exata capturava tem essa outra causa, que o
   catalogo nao cobre. Elas saem do custo da 088, que cai para 14.091.

4. O sinal so tem autoridade se NAO casar log saudavel (INV-R04). Rodando os
   414 sinais do catalogo contra um deploy VERDE de verdade, dois caem:
   `already exists` (armadilha 357), que e linha de push de imagem, e
   `django-ninja` (armadilha 351), que e linha de `pip install`. O gabarito
   precisa ser um log real: o gabarito fino que eu tinha antes nao pegava o
   `django-ninja`, e ele sozinho acusava quatro janelas que nao eram dele.
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

CI = Path(__file__).resolve().parents[1]
if str(CI) not in sys.path:
    sys.path.insert(0, str(CI))

import indice_de_armadilhas as indice  # noqa: E402
from _nucleo import raiz_do_repo  # noqa: E402

RAIZ = raiz_do_repo()

# --------------------------------------------------------------------------
# A regua congelada.
# --------------------------------------------------------------------------

BASE = "cc6cab993d312e1ba788bb6fec5c67cae2b92fc4"
JANELA_INICIO = "2026-08-18T00:00:00Z"
JANELA_FIM = "2026-09-18T00:00:00Z"
WORKFLOW_MEDIDO = "deploy-celula"
RUNS_ENUMERADOS = 1379
JOBS_DE_CELULA = 1447
JOBS_DE_CELULA_FALHOS = 76
JOBS_DE_CELULA_CANCELADOS = 9

# `cancelled` tem classe propria e NAO abre janela. Com ele abrindo, a
# contagem vai a 44/43/1 e nao fecha com a tabela historica.
CONCLUSOES_QUE_ABREM_JANELA = ("failure",)

CAUSA_088 = "celula_sem_servico_no_compose_da_vps"
CAUSA_127 = "soluco_de_rede_na_porta_22"
CAUSA_GATEWAY = "chave_do_gateway_ausente_no_compose"

MOTIVO_GATEWAY = (
    "a recusa da 088 aparece, mas o compose reclamou variavel obrigatoria "
    "antes dela: causa identificada e sem armadilha no catalogo, entao nao "
    "entra no custo da 088"
)
MOTIVO_AMBIGUIDADE = (
    "mais de um sinal especifico casou o mesmo log: sinais concorrentes "
    "exigem ERROR, nunca o primeiro (INV-R03)"
)
MOTIVO_SEM_CASAMENTO = (
    "nenhum sinal com autoridade casou; ausencia de casamento nao e ausencia "
    "de problema (INV-R08)"
)


class Janela(NamedTuple):
    """Uma janela em que uma celula ficou sem publicacao.

    Dois eixos que NAO podem se misturar, e foi misturá-los que reprovou a
    versao anterior deste corpus:

      GABARITO, auditado a mao sobre o log cru
        armadilha_esperada    o numero do catalogo, ou None
        evidencia_do_rotulo   a linha LITERAL que sustenta o rotulo
        natureza / desfecho / causa / motivo_de_exclusao

      SAIDA DO DETECTOR DE HOJE, que e o defeito que F1 vai consertar
        sinais_observados_pelo_detector_atual
        estado_inicial_do_detector
        linhas_de_eco_descartadas

    Sem campo de duracao de proposito: ela se calcula de `inicio` e `fim`.
    """

    celula: str
    abre_run: int
    abre_job: int
    abre_attempt: int
    inicio: str
    fecha_run: int | None
    fecha_job: int | None
    fecha_attempt: int | None
    fim: str | None
    jobs_vermelhos: tuple[int, ...]
    armadilha_esperada: str | None
    evidencia_do_rotulo: str | None
    natureza: str
    desfecho: str
    causa: str | None
    motivo_de_exclusao: str | None
    sinais_observados_pelo_detector_atual: tuple[str, ...]
    estado_inicial_do_detector: str
    linhas_de_eco_descartadas: int


# --------------------------------------------------------------------------
# O REGISTRO AUDITAVEL, na ordem em que as janelas abriram. Cada run confere
# em https://github.com/abundanciabr/sitesdoreino/actions/runs/<run> e cada
# job em .../actions/jobs/<job>.
# --------------------------------------------------------------------------

JANELAS: tuple[Janela, ...] = (
    Janela(
        celula='checkout',
        abre_run=32242003033, abre_job=96034451817, abre_attempt=1,
        inicio='2026-08-19T10:19:27Z',
        fecha_run=32433215806, fecha_job=96629110042, fecha_attempt=1,
        fim='2026-08-21T00:36:03Z',
        jobs_vermelhos=(96034451817,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/19 10:19:24 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='sugestoes',
        abre_run=32715926069, abre_job=97397238376, abre_attempt=1,
        inicio='2026-08-24T10:17:34Z',
        fecha_run=32738154898, fecha_job=97466266068, fecha_attempt=1,
        fim='2026-08-24T14:23:21Z',
        jobs_vermelhos=(97397238376, 97404246281, 97416166996, 97424176662, 97435304289, 97437182591, 97453112809,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'sugestoes' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=14,
    ),
    Janela(
        celula='identidade',
        abre_run=32837381030, abre_job=97769470319, abre_attempt=1,
        inicio='2026-08-25T10:30:08Z',
        fecha_run=33020269151, fecha_job=98348864453, fecha_attempt=1,
        fim='2026-08-26T22:39:45Z',
        jobs_vermelhos=(97769470319, 97800650012, 97801205916,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'identidade' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='mal_classificada',
        linhas_de_eco_descartadas=6,
    ),
    Janela(
        celula='forum',
        abre_run=33213227804, abre_job=98991216757, abre_attempt=1,
        inicio='2026-08-28T21:39:08Z',
        fecha_run=33285964121, fecha_job=99189236201, fecha_attempt=1,
        fim='2026-08-30T01:36:25Z',
        jobs_vermelhos=(98991216757, 98995397553, 99000529510, 99185072624,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'forum' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33262537759, abre_job=99128175892, abre_attempt=1,
        inicio='2026-08-29T16:32:32Z',
        fecha_run=33262938954, fecha_job=99128745455, fecha_attempt=1,
        fim='2026-08-29T16:34:09Z',
        jobs_vermelhos=(99128175892,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/29 16:29:13 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33267007247, abre_job=99138885008, abre_attempt=1,
        inicio='2026-08-29T18:04:07Z',
        fecha_run=33267103615, fecha_job=99139464722, fecha_attempt=1,
        fim='2026-08-29T18:05:35Z',
        jobs_vermelhos=(99138885008,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/29 18:00:49 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33279359245, abre_job=99171902513, abre_attempt=1,
        inicio='2026-08-29T22:51:12Z',
        fecha_run=33279807568, fecha_job=99173072835, fecha_attempt=1,
        fim='2026-08-29T22:59:44Z',
        jobs_vermelhos=(99171902513,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/29 22:47:53 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33282141644, abre_job=99179090597, abre_attempt=1,
        inicio='2026-08-30T00:02:11Z',
        fecha_run=33284270544, fecha_job=99184787435, fecha_attempt=1,
        fim='2026-08-30T00:53:19Z',
        jobs_vermelhos=(99179090597,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/29 23:58:52 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33286302573, abre_job=99190088618, abre_attempt=1,
        inicio='2026-08-30T01:48:26Z',
        fecha_run=33286390331, fecha_job=99190708258, fecha_attempt=2,
        fim='2026-08-30T01:51:43Z',
        jobs_vermelhos=(99190088618,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 01:45:05 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33287178661, abre_job=99192460612, abre_attempt=1,
        inicio='2026-08-30T02:12:03Z',
        fecha_run=33287509662, fecha_job=99193306866, fecha_attempt=1,
        fim='2026-08-30T02:16:44Z',
        jobs_vermelhos=(99192460612,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 02:08:43 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33289248456, abre_job=99198008626, abre_attempt=1,
        inicio='2026-08-30T03:05:48Z',
        fecha_run=33289415484, fecha_job=99198489542, fecha_attempt=1,
        fim='2026-08-30T03:07:32Z',
        jobs_vermelhos=(99198008626,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 03:02:28 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33312250929, abre_job=99259481224, abre_attempt=1,
        inicio='2026-08-30T12:49:30Z',
        fecha_run=33312655853, fecha_job=99261339887, fecha_attempt=2,
        fim='2026-08-30T13:02:07Z',
        jobs_vermelhos=(99259481224,),
        armadilha_esperada=None,
        evidencia_do_rotulo=None,
        natureza='ERROR_ambiguidade',
        desfecho='desconhecida',
        causa=None,
        motivo_de_exclusao=MOTIVO_AMBIGUIDADE,
        sinais_observados_pelo_detector_atual=('127', '209'),
        estado_inicial_do_detector='acusa_sem_rotulo',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='forum',
        abre_run=33317845264, abre_job=99274623116, abre_attempt=1,
        inicio='2026-08-30T14:58:06Z',
        fecha_run=33318197852, fecha_job=99275716115, fecha_attempt=1,
        fim='2026-08-30T14:59:47Z',
        jobs_vermelhos=(99274623116,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 14:52:53 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33320640868, abre_job=99282084295, abre_attempt=1,
        inicio='2026-08-30T15:59:18Z',
        fecha_run=33321089830, fecha_job=99283317875, fecha_attempt=1,
        fim='2026-08-30T16:12:58Z',
        jobs_vermelhos=(99282084295,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 15:54:05 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33328262902, abre_job=99302352564, abre_attempt=1,
        inicio='2026-08-30T18:39:02Z',
        fecha_run=33328736510, fecha_job=99303552724, fecha_attempt=1,
        fim='2026-08-30T18:42:58Z',
        jobs_vermelhos=(99302352564,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 18:33:50 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='gamificacao',
        abre_run=33330434813, abre_job=99314994712, abre_attempt=2,
        inicio='2026-08-30T20:17:37Z',
        fecha_run=33412064640, fecha_job=99554268357, fecha_attempt=1,
        fim='2026-08-31T16:08:33Z',
        jobs_vermelhos=(99314994712, 99321526667, 99328719313, 99340057584, 99543857608,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'gamificacao' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33334467510, abre_job=99318938815, abre_attempt=1,
        inicio='2026-08-30T20:52:22Z',
        fecha_run=33335290673, fecha_job=99321188776, fecha_attempt=1,
        fim='2026-08-30T21:05:02Z',
        jobs_vermelhos=(99318938815,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 20:47:12 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33341697458, abre_job=99338545489, abre_attempt=1,
        inicio='2026-08-30T23:32:07Z',
        fecha_run=33342050908, fecha_job=99339519701, fecha_attempt=1,
        fim='2026-08-30T23:34:15Z',
        jobs_vermelhos=(99338545489,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/30 23:26:53 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='gamificacao',
        abre_run=33414322799, abre_job=99561686570, abre_attempt=1,
        inicio='2026-08-31T16:38:31Z',
        fecha_run=33443883250, fecha_job=99658755725, fecha_attempt=1,
        fim='2026-08-31T22:01:03Z',
        jobs_vermelhos=(99561686570,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/31 16:33:20 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33414532018, abre_job=99568747853, abre_attempt=3,
        inicio='2026-08-31T17:01:10Z',
        fecha_run=33417059376, fecha_job=99570956269, fecha_attempt=1,
        fim='2026-08-31T17:02:37Z',
        jobs_vermelhos=(99568747853,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/31 16:55:58 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33424218350, abre_job=99594226753, abre_attempt=1,
        inicio='2026-08-31T18:26:41Z',
        fecha_run=33424833038, fecha_job=99596546863, fecha_attempt=1,
        fim='2026-08-31T18:28:01Z',
        jobs_vermelhos=(99594226753,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/31 18:21:29 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33445194165, abre_job=99663017283, abre_attempt=1,
        inicio='2026-08-31T22:22:08Z',
        fecha_run=33445877252, fecha_job=99665177156, fecha_attempt=1,
        fim='2026-08-31T22:26:16Z',
        jobs_vermelhos=(99663017283,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/08/31 22:16:57 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33512647511, abre_job=99872483447, abre_attempt=1,
        inicio='2026-09-01T13:28:05Z',
        fecha_run=33513292447, fecha_job=99874977493, fecha_attempt=1,
        fim='2026-09-01T13:31:26Z',
        jobs_vermelhos=(99872483447,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/01 13:22:52 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33643186745, abre_job=100298524059, abre_attempt=4,
        inicio='2026-09-02T15:03:47Z',
        fecha_run=33645642546, fecha_job=100304940514, fecha_attempt=3,
        fim='2026-09-02T15:05:24Z',
        jobs_vermelhos=(100298524059,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/02 14:58:35 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33766884841, abre_job=100687608267, abre_attempt=1,
        inicio='2026-09-03T14:29:50Z',
        fecha_run=33767681878, fecha_job=100690342088, fecha_attempt=1,
        fim='2026-09-03T14:38:11Z',
        jobs_vermelhos=(100687608267,),
        armadilha_esperada=None,
        evidencia_do_rotulo=None,
        natureza='ERROR_sem_casamento',
        desfecho='desconhecida',
        causa=None,
        motivo_de_exclusao=MOTIVO_SEM_CASAMENTO,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='calada_sem_rotulo',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33816081134, abre_job=100850893359, abre_attempt=2,
        inicio='2026-09-03T23:23:38Z',
        fecha_run=33817387581, fecha_job=100852911027, fecha_attempt=1,
        fim='2026-09-03T23:26:39Z',
        jobs_vermelhos=(100850893359,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/03 23:18:27 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='encomendas',
        abre_run=33830235534, abre_job=100893721477, abre_attempt=3,
        inicio='2026-09-04T02:53:38Z',
        fecha_run=34296014117, fecha_job=102293187944, fecha_attempt=1,
        fim='2026-09-09T00:44:11Z',
        jobs_vermelhos=(100893721477, 101053523714, 101083831146, 101616208560, 101628121329, 101629167386, 101636948325, 101648753758, 101651002539,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'encomendas' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='metricas',
        abre_run=33875813629, abre_job=101033001875, abre_attempt=1,
        inicio='2026-09-04T13:08:26Z',
        fecha_run=33882846095, fecha_job=101056220333, fecha_attempt=1,
        fim='2026-09-04T14:22:07Z',
        jobs_vermelhos=(101033001875, 101036643912, 101041268231,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'metricas' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='cursos',
        abre_run=33940422044, abre_job=101236779662, abre_attempt=1,
        inicio='2026-09-05T03:00:03Z',
        fecha_run=33973556599, fecha_job=101326456448, fecha_attempt=1,
        fim='2026-09-05T15:04:55Z',
        jobs_vermelhos=(101236779662, 101243692223, 101248322833, 101251276327, 101253596228, 101305530119,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'cursos' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='pages',
        abre_run=33991320699, abre_job=101374133613, abre_attempt=1,
        inicio='2026-09-05T20:56:47Z',
        fecha_run=34033367455, fecha_job=101487107007, fecha_attempt=1,
        fim='2026-09-06T12:35:28Z',
        jobs_vermelhos=(101374133613, 101400556719, 101404261758,),
        armadilha_esperada='088',
        evidencia_do_rotulo="ERRO: 'pages' nÃ£o tem serviÃ§o algum em /opt/plataforma/docker-compose.yml.",
        natureza='ocorrencia_operacional',
        desfecho='interceptada',
        causa=CAUSA_088,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='invisivel',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=33995099105, abre_job=101385494561, abre_attempt=2,
        inicio='2026-09-05T22:28:23Z',
        fecha_run=33996054279, fecha_job=101386906889, fecha_attempt=1,
        fim='2026-09-05T22:32:46Z',
        jobs_vermelhos=(101385494561,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/05 22:23:09 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=34001330286, abre_job=101403257599, abre_attempt=5,
        inicio='2026-09-06T00:58:24Z',
        fecha_run=34002534439, fecha_job=101404261677, fecha_attempt=3,
        fim='2026-09-06T00:59:46Z',
        jobs_vermelhos=(101403257599,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/06 00:53:12 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=34045726757, abre_job=101521201085, abre_attempt=3,
        inicio='2026-09-06T16:44:54Z',
        fecha_run=34046214232, fecha_job=101522242783, fecha_attempt=1,
        fim='2026-09-06T16:46:31Z',
        jobs_vermelhos=(101521201085,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/06 16:39:41 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=34046999896, abre_job=101524806014, abre_attempt=4,
        inicio='2026-09-06T17:11:20Z',
        fecha_run=34047801160, fecha_job=101526072321, fecha_attempt=1,
        fim='2026-09-06T17:13:39Z',
        jobs_vermelhos=(101524806014,),
        armadilha_esperada='127',
        evidencia_do_rotulo='2026/09/06 17:06:08 dial tcp ***:22: i/o timeout',
        natureza='ocorrencia_operacional',
        desfecho='mitigada',
        causa=CAUSA_127,
        motivo_de_exclusao=None,
        sinais_observados_pelo_detector_atual=('127',),
        estado_inicial_do_detector='reconhecida',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='cursos',
        abre_run=34291988385, abre_job=102593204308, abre_attempt=7,
        inicio='2026-09-09T18:34:04Z',
        fecha_run=34433902392, fecha_job=102735962902, fecha_attempt=2,
        fim='2026-09-10T03:39:10Z',
        jobs_vermelhos=(102593204308, 102724243652,),
        armadilha_esperada=None,
        evidencia_do_rotulo=None,
        natureza='ERROR_sem_casamento',
        desfecho='desconhecida',
        causa=None,
        motivo_de_exclusao=MOTIVO_SEM_CASAMENTO,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='calada_sem_rotulo',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='admin',
        abre_run=35036738411, abre_job=104608405716, abre_attempt=1,
        inicio='2026-09-15T23:47:54Z',
        fecha_run=35233425707, fecha_job=105243986004, fecha_attempt=1,
        fim='2026-09-17T14:29:22Z',
        jobs_vermelhos=(104608405716, 104611180648, 104642907818, 104648152631, 105054589721, 105230399333, 105237578373,),
        armadilha_esperada=None,
        evidencia_do_rotulo='error while interpolating services.traefik.environment.ALUNOS_API_TOKEN: required variable ALUNOS_API_TOKEN is missing a value: defina ALUNOS_API_TOKEN em env/admin.env',
        natureza='ocorrencia_operacional',
        desfecho='sem_guarda',
        causa=CAUSA_GATEWAY,
        motivo_de_exclusao=MOTIVO_GATEWAY,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='calada_sem_rotulo',
        linhas_de_eco_descartadas=0,
    ),
    Janela(
        celula='alunos',
        abre_run=35175171472, abre_job=105055584221, abre_attempt=1,
        inicio='2026-09-17T02:43:03Z',
        fecha_run=None, fecha_job=None, fecha_attempt=None,
        fim=None,
        jobs_vermelhos=(105055584221,),
        armadilha_esperada=None,
        evidencia_do_rotulo='error while interpolating services.traefik.environment.ALUNOS_API_TOKEN: required variable ALUNOS_API_TOKEN is missing a value: defina ALUNOS_API_TOKEN em env/admin.env',
        natureza='ocorrencia_operacional',
        desfecho='sem_guarda',
        causa=CAUSA_GATEWAY,
        motivo_de_exclusao=MOTIVO_GATEWAY,
        sinais_observados_pelo_detector_atual=(),
        estado_inicial_do_detector='calada_sem_rotulo',
        linhas_de_eco_descartadas=0,
    ),
)

# O relatorio-plano publicou estes numeros. Ficam aqui para a comparacao ser
# explicita, nunca como fonte: quem manda e o registro acima.
TABELA_DO_RELATORIO = {
    "janelas": 37,
    "janelas_fechadas": 36,
    "janelas_abertas": 1,
    "janelas_088": 10,
    "janelas_127": 24,
    "janelas_ambiguas_127_209": 1,
    "janelas_nao_classificadas": 2,
    "celula_minutos_088": 16410,
    "celula_minutos_127": 2754,
}

# O ESTADO INICIAL DA 088, declarado. E o vermelho que F1 tem de virar verde:
# das 8 janelas cujo gabarito diz 088, o detector de hoje NAO reconhece
# nenhuma. Sete ele nao ve, e uma ele acusa errado.
ESTADO_INICIAL_DA_088 = {
    "janelas_esperadas": 8,
    "reconhecidas_hoje": 0,
    "invisiveis_hoje": 7,
    "mal_classificadas_hoje": 1,
}

# O caso adversarial nomeado: mesma janela, gabarito 088, detector acusando
# 127. Ele nao pode passar como atribuicao correta, porque nao e uma: e o
# falso positivo que o detector de hoje produz, e a prova de que o corpus
# distingue gabarito de saida.
ADVERSARIAL_IDENTIDADE = {
    "celula": "identidade",
    "abre_run": 32837381030,
    "armadilha_esperada": "088",
    "detector_atual_acusa": ("127",),
}


def _instante(carimbo: str) -> datetime:
    return datetime.fromisoformat(carimbo.replace("Z", "+00:00"))


def duracao_em_segundos(janela: Janela) -> int | None:
    """Derivada dos carimbos. Janela aberta nao tem duracao, tem None."""
    if janela.fim is None:
        return None
    return int((_instante(janela.fim) - _instante(janela.inicio)).total_seconds())


def minutos(segundos: int) -> int:
    return round(segundos / 60)


def janelas_esperadas_de(armadilha: str) -> tuple[Janela, ...]:
    """Pelo GABARITO. O nome diz de onde vem para ninguem ler como saida."""
    return tuple(j for j in JANELAS if j.armadilha_esperada == armadilha)


def janelas_com_causa(causa: str) -> tuple[Janela, ...]:
    return tuple(j for j in JANELAS if j.causa == causa)


def janelas_com_natureza(natureza: str) -> tuple[Janela, ...]:
    return tuple(j for j in JANELAS if j.natureza == natureza)


def janelas_com_estado(estado: str) -> tuple[Janela, ...]:
    """Pela SAIDA DO DETECTOR DE HOJE, que e o defeito, nao o gabarito."""
    return tuple(j for j in JANELAS if j.estado_inicial_do_detector == estado)


def celula_minutos_esperados(janelas: tuple[Janela, ...]) -> int:
    """Soma os segundos das FECHADAS e arredonda uma vez so.

    `esperados` no nome porque o agrupamento vem do gabarito. Ate F1 rodar,
    o detector atual nao produz nada parecido com isto, e apresentar este
    numero como saida dele seria falso verde.
    """
    return minutos(
        sum(duracao_em_segundos(j) for j in janelas if j.fim is not None)
    )


def causas_medidas() -> tuple[str, ...]:
    return tuple(sorted({j.causa for j in JANELAS if j.causa}))


def sinais_declarados(numero: str) -> tuple[str, ...]:
    """Le o `sinal:` do frontmatter VIVO da armadilha, nao uma copia.

    A fonte e o arquivo rastreado em armadilhas/, como manda o INV-R05.
    `armadilhas/SINAIS.json` e derivado e esta no .gitignore, entao nao serve
    de fonte para um portao.
    """
    achados = sorted(RAIZ.glob(f"armadilhas/{numero}-*.md"))
    if len(achados) != 1:
        raise AssertionError(
            f"esperava exatamente uma armadilha {numero} em armadilhas/, "
            f"achei {len(achados)}: medicao ambigua nao vira ausencia de "
            "problema"
        )
    linhas = achados[0].read_text(encoding="utf-8").splitlines()
    frente = indice.ler_frontmatter(linhas, achados[0].name) or {}
    sinal = frente.get("sinal") or []
    return tuple(sinal) if isinstance(sinal, list) else (sinal,)


# --------------------------------------------------------------------------
# Corpus adversarial. Trechos redigidos dos logs da janela, com o job de
# origem em cada um; a excecao e LOG_088_SO_ECO, construida e marcada como
# tal. O segredo ja vem mascarado pelo proprio Actions como `***`.
# --------------------------------------------------------------------------

ESC = "\x1b"
CIANO = ESC + "[36;1m"
FIM_DA_COR = ESC + "[0m"

# Mojibake real: "nao"/"servico"/"proposito" com acento, em UTF-8 duplo.
NAO = "nÃ£o"
SERVICO = "serviÃ§o"
PROPOSITO = "propÃ³sito"

# A recusa da 088 como ela REALMENTE aparece: mojibake, sem envelope ciano.
# Origem: job 100893721477, celula `encomendas`, 2026-09-04.
LOG_088_EXECUTADO = (
    f"2026-09-04T02:51:45.1818315Z ERRO: 'encomendas' {NAO} tem {SERVICO} "
    "algum em /opt/plataforma/docker-compose.yml.\n"
    f"2026-09-04T02:51:45.1819382Z Abortado de {PROPOSITO}: 'up -d' sem "
    "argumento subiria a plataforma inteira.\n"
    "2026-09-04T02:51:45.1820062Z 2026/09/04 02:51:45 Process exited with "
    "status 1\n"
    "2026-09-04T02:51:45.1845618Z ##[error]Process completed with exit code 1.\n"
)

# UNICA FIXTURE CONSTRUIDA do arquivo, e ela diz isso. As duas primeiras
# linhas sao verbatim do job 100298524059; o texto da recusa foi colocado
# dentro do mesmo envelope ciano-negrito de proposito. Desde 28/08/2026 o deploy-celula.yml usa
# `script_path:`, entao a ssh-action nao ecoa mais o corpo do script e um log
# assim nao existe mais em campo. Ela fica porque o detector precisa recusar
# esse caso: qualquer passo `run:` que cite a recusa volta a produzi-lo.
LOG_088_SO_ECO = (
    f"2026-09-02T14:56:53.7517837Z {CIANO}set -eu{FIM_DA_COR}\n"
    f"2026-09-02T14:56:53.7518402Z {CIANO}  echo \"ERRO: '$CELULA' {NAO} tem "
    f"{SERVICO} algum em /opt/plataforma/docker-compose.yml.\"{FIM_DA_COR}\n"
    f"2026-09-02T14:56:53.7519001Z {CIANO}  echo \"Abortado de {PROPOSITO}: "
    f"'up -d' sem argumento subiria a plataforma inteira.\"{FIM_DA_COR}\n"
    "2026-09-02T14:56:53.7520113Z ##[endgroup]\n"
    "2026-09-02T14:57:10.1120440Z Deploy da celula concluido.\n"
)

# A falha VIZINHA que a recusa da 088 disfarcava antes do conserto de
# infra/deploy-celula-na-vps.sh. Origem: job 104608405716, celula `admin`,
# 2026-09-15. Duas janelas sao desta causa, nao da 088.
LOG_088_MENTIRA_DA_CHAVE_DO_GATEWAY = (
    "2026-09-15T23:45:59.5303015Z error while interpolating "
    "services.traefik.environment.ALUNOS_API_TOKEN: required variable "
    "ALUNOS_API_TOKEN is missing a value: defina ALUNOS_API_TOKEN em "
    "env/admin.env\n"
    "2026-09-15T23:45:59.5303962Z error while interpolating "
    "services.traefik.environment.TOKEN_CATALOGO: required variable "
    "TOKEN_CATALOGO is missing a value: defina TOKEN_CATALOGO em "
    "env/admin.env\n"
    f"2026-09-15T23:45:59.5422724Z ERRO: 'admin' {NAO} tem {SERVICO} algum em "
    "/opt/plataforma/docker-compose.yml.\n"
    f"2026-09-15T23:45:59.5423470Z Abortado de {PROPOSITO}: 'up -d' sem "
    "argumento subiria a plataforma inteira.\n"
)

# Origem: job 100298524059, celula `admin`, 2026-09-02.
LOG_127_SOLUCO_DE_REDE = (
    "2026-09-02T14:58:35.0667081Z 2026/09/02 14:58:35 dial tcp ***:22: "
    "i/o timeout\n"
    "2026-09-02T14:58:35.0679383Z ##[error]Process completed with exit code 1.\n"
)

# A 209 coocorre com a 127 POR DESENHO: a sonda cita o soluco ao negar que
# seja ele. Dois sinais no mesmo log exigem ERROR, nunca o primeiro (INV-R03).
LOG_209_SONDA_MAIS_127 = LOG_127_SOLUCO_DE_REDE + (
    "2026-09-02T14:58:36.1100221Z PAROU POR SEGURANÃA: a porta 22 "
    f"da VPS {NAO} respondeu deste runner\n"
    "2026-09-02T14:58:36.1101004Z    Isto NAO e o soluco da armadilhas/127: "
    "e a armadilhas/017, falha PERMANENTE de alcance.\n"
)

# Log SAUDAVEL: trecho REAL do deploy verde da celula `pagamentos`, job
# 96033856977, 2026-08-19. E o gabarito do INV-R04, e ele precisa ser real:
# o gabarito fino que eu tinha antes deixava passar `django-ninja`, que
# acusava quatro janelas de reincidencia que nao eram dele.
LOG_SAUDAVEL = (
    "2026-08-19T10:16:10.4231338Z #9 1.489 Collecting django-ninja==1.3.0 "
    "(from -r requirements.txt (line 2))\n"
    "2026-08-19T10:16:18.3314653Z #9 9.475 Successfully installed "
    "Django-5.0.9 PyYAML-6.0.2 annotated-types-0.8.0\n"
    "2026-08-19T10:16:23.0951423Z 5f70bf18a086: Layer already exists\n"
    "2026-08-19T10:16:35.8805333Z 4a3a923292e3: Layer already exists\n"
)

# A armadilha 195 e a prova viva de que citacao nao e queda: ela aparece em
# 37 registros e eventos de origin/main e em ZERO das 37 janelas.
# Origem: painel/registros/, evidencia do PR #582.
LOG_195_CITACAO_COMO_PROVA = (
    "PROVA VERMELHO->VERDE: com a cura, ci/tests/test_fila.py = 38 passed em "
    "3.27s; com so o ci/fila.py revertido para origin/main e os testes novos "
    "mantidos = 7 failed, 31 passed. Os 7 vermelhos morreram na ASSERCAO, "
    "nao na construcao do teste (armadilhas/195).\n"
)

# O vermelho que a 195 ensina a RECUSAR: morreu montando o objeto, entao nao
# prova decisao nenhuma. Origem: armadilhas/195, linha 20.
LOG_195_VERMELHO_DE_CONSTRUCAO = (
    "E   TypeError: Fatos.__init__() got an unexpected keyword argument "
    "'event'\n"
    "ci/tests/test_rerun_de_deploy.py:112: TypeError\n"
)

# Sinais NUS que o catalogo declara hoje e que o INV-R04 desqualifica.
# Medido rodando os 414 sinais do catalogo contra LOG_SAUDAVEL: estes dois
# sao os unicos que casam um deploy verde de verdade.
SINAIS_GENERICOS_MEDIDOS = {
    "357": ("already exists",),
    "351": ("django-ninja",),
}

# --------------------------------------------------------------------------
# O que o corpus PROVA. Estas assercoes sao o contrato das fases seguintes.
# --------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# O que o corpus PROVA. Estas assercoes sao o contrato das fases seguintes.
# ---------------------------------------------------------------------------


def test_o_registro_tem_37_janelas_e_os_totais_saem_dele():
    assert len(JANELAS) == 37
    fechadas = [j for j in JANELAS if j.fim is not None]
    assert len(fechadas) == 36
    assert len(JANELAS) - len(fechadas) == 1
    naturezas = sum(
        len(janelas_com_natureza(n))
        for n in (
            "ocorrencia_operacional",
            "ERROR_ambiguidade",
            "ERROR_sem_casamento",
        )
    )
    assert naturezas == len(JANELAS), "toda janela tem exatamente uma natureza"


def test_gabarito_e_saida_do_detector_sao_campos_DIFERENTES():
    """O defeito que reprovou a rodada anterior.

    `armadilha_esperada` e verdade auditada; `sinais_observados_pelo_detector_
    atual` e o que o catalogo de hoje produz. Guardar os dois no mesmo campo
    faz o corpus aceitar como correta a atribuicao que ele deveria denunciar.
    """
    assert "armadilha_esperada" in Janela._fields
    assert "sinais_observados_pelo_detector_atual" in Janela._fields
    assert "armadilha" not in Janela._fields, (
        "um campo chamado so `armadilha` volta a misturar gabarito com saida"
    )
    divergentes = [
        j
        for j in JANELAS
        if j.armadilha_esperada is not None
        and tuple(j.sinais_observados_pelo_detector_atual)
        != (j.armadilha_esperada,)
    ]
    assert divergentes, (
        "se gabarito e detector coincidissem em TODAS as janelas, nao haveria "
        "F1 a fazer, e este corpus seria uma foto do detector, nao um gabarito"
    )


def test_todo_rotulo_esperado_carrega_a_EVIDENCIA_que_o_sustenta():
    """`causa` e conclusao. Evidencia e a linha literal do log."""
    for j in JANELAS:
        if j.armadilha_esperada is None and j.causa is None:
            assert j.evidencia_do_rotulo is None
            continue
        assert j.evidencia_do_rotulo, (
            f"a janela de {j.celula} no run {j.abre_run} afirma um rotulo sem "
            "mostrar a linha do log que o sustenta"
        )
        assert j.evidencia_do_rotulo != j.causa, (
            "repetir a causa no lugar da evidencia e trocar prova por rotulo"
        )
        assert not j.evidencia_do_rotulo.startswith("2026-"), (
            "a evidencia guarda o TEXTO da linha, sem o carimbo de tempo"
        )


def test_a_evidencia_da_088_e_linha_EXECUTADA_e_nunca_eco():
    """O eco tem DUAS formas e so uma delas tem ANSI.

    Ate 28/08/2026 a ssh-action ecoava `script:` CRU, sem cor nenhuma. Nas
    janelas de `sugestoes` e `identidade` a primeira ocorrencia da frase no log
    e esse eco. A marca que pega as duas formas e a variavel NAO EXPANDIDA: o
    eco imprime `'$CELULA'` e a execucao imprime o nome da celula.
    """
    for j in janelas_esperadas_de("088"):
        assert "$CELULA" not in j.evidencia_do_rotulo, (
            f"a evidencia de {j.celula} e o eco do script, nao a execucao"
        )
        assert "echo " not in j.evidencia_do_rotulo
        assert CIANO not in j.evidencia_do_rotulo
        assert f"'{j.celula}'" in j.evidencia_do_rotulo, (
            "a linha executada imprime o nome da celula ja expandido, e e isso "
            "que prova que o ramo rodou"
        )
        assert "algum em /opt/plataforma/docker-compose.yml" in (
            j.evidencia_do_rotulo
        )
    com_eco = [j for j in JANELAS if j.linhas_de_eco_descartadas]
    assert {j.celula for j in com_eco} == {"sugestoes", "identidade"}, (
        "so as duas janelas anteriores a 28/08/2026 tem eco a descartar"
    )


def test_o_estado_inicial_da_088_e_zero_reconhecidas(subtests=None):
    """O vermelho declarado que F1 tem de virar verde.

    Das oito janelas cujo gabarito diz 088, o detector de hoje nao reconhece
    NENHUMA. Sete ele nao ve (sinal ausente do catalogo) e uma ele acusa
    errado. Enquanto este numero for 0, a 088 e invisivel aos instrumentos.
    """
    esperadas = janelas_esperadas_de("088")
    assert len(esperadas) == ESTADO_INICIAL_DA_088["janelas_esperadas"] == 8

    por_estado = {}
    for j in esperadas:
        por_estado.setdefault(j.estado_inicial_do_detector, []).append(j.celula)

    assert len(por_estado.get("reconhecida", [])) == (
        ESTADO_INICIAL_DA_088["reconhecidas_hoje"]
    ) == 0
    assert len(por_estado.get("invisivel", [])) == (
        ESTADO_INICIAL_DA_088["invisiveis_hoje"]
    ) == 7
    assert len(por_estado.get("mal_classificada", [])) == (
        ESTADO_INICIAL_DA_088["mal_classificadas_hoje"]
    ) == 1


def test_a_janela_identidade_e_o_caso_adversarial_do_falso_positivo():
    """Gabarito 088, detector acusando 127. Nomeada, nao silenciosa.

    Passar esta janela como atribuicao correta foi exatamente o defeito que
    reprovou a rodada anterior: o corpus estava guardando o erro do detector
    como se fosse o gabarito.
    """
    achadas = [
        j
        for j in JANELAS
        if j.celula == ADVERSARIAL_IDENTIDADE["celula"]
        and j.abre_run == ADVERSARIAL_IDENTIDADE["abre_run"]
    ]
    assert len(achadas) == 1
    janela = achadas[0]

    assert janela.armadilha_esperada == ADVERSARIAL_IDENTIDADE["armadilha_esperada"]
    assert tuple(janela.sinais_observados_pelo_detector_atual) == (
        ADVERSARIAL_IDENTIDADE["detector_atual_acusa"]
    )
    assert janela.estado_inicial_do_detector == "mal_classificada"
    assert janela.armadilha_esperada not in (
        janela.sinais_observados_pelo_detector_atual
    ), (
        "se o detector tambem acusasse 088 aqui, isto deixaria de ser falso "
        "positivo e o caso adversarial perderia o sentido"
    )
    assert "'identidade'" in janela.evidencia_do_rotulo, (
        "o rotulo 088 desta janela precisa da linha executada que o sustenta, "
        "justamente porque o detector diz outra coisa"
    )


def test_a_duracao_e_derivada_dos_carimbos_e_nao_existe_em_dobro():
    assert "segundos" not in Janela._fields, (
        "duracao nao pode ser campo: dois lugares para o mesmo fato e um "
        "lugar para eles divergirem"
    )
    for j in JANELAS:
        if j.fim is None:
            assert duracao_em_segundos(j) is None
            continue
        assert duracao_em_segundos(j) >= 0, (
            f"a janela de {j.celula} no run {j.abre_run} termina antes de "
            "comecar: isso e erro de medicao, nao um fato"
        )


def test_cada_janela_tem_as_ancoras_de_abertura_e_de_fechamento():
    for j in JANELAS:
        assert j.abre_run > 0 and j.abre_job > 0 and j.abre_attempt >= 1
        assert j.abre_job == j.jobs_vermelhos[0], (
            "o job que abriu a janela e o primeiro vermelho dela"
        )
        assert len(j.jobs_vermelhos) == len(set(j.jobs_vermelhos)), (
            f"a janela de {j.celula} repete job vermelho: o mesmo job nao "
            "pode contar duas vezes (deduplicacao por job)"
        )
        if j.fim is None:
            assert (j.fecha_run, j.fecha_job, j.fecha_attempt) == (
                None,
                None,
                None,
            ), "janela aberta nao tem quem a feche"
        else:
            assert j.fecha_run > 0 and j.fecha_job > 0 and j.fecha_attempt >= 1
            assert j.fecha_run != j.abre_run, (
                "o run que fecha a janela nao pode ser o mesmo que a abriu"
            )


def test_os_quatro_eixos_do_gabarito_nao_se_misturam():
    for j in JANELAS:
        if j.natureza == "ocorrencia_operacional":
            assert j.causa, "ocorrencia sem causa nomeada nao explica nada"
            assert j.desfecho in ("interceptada", "mitigada", "sem_guarda")
        else:
            assert j.natureza.startswith("ERROR_")
            assert j.armadilha_esperada is None and j.causa is None
            assert j.desfecho == "desconhecida"
        if j.armadilha_esperada is None:
            assert j.motivo_de_exclusao, (
                f"a janela de {j.celula} no run {j.abre_run} nao tem armadilha "
                "e precisa dizer por que"
            )
        else:
            assert j.armadilha_esperada in ("088", "127")
            assert j.motivo_de_exclusao is None


def test_a_causa_do_gateway_nao_tem_armadilha_e_sai_do_custo_da_088():
    gateway = janelas_com_causa(CAUSA_GATEWAY)
    assert len(gateway) == 2
    for j in gateway:
        assert j.armadilha_esperada is None, (
            "nenhuma armadilha do catalogo cobre esta causa hoje"
        )
        assert j.natureza == "ocorrencia_operacional"
        assert j.desfecho == "sem_guarda"
        assert j.motivo_de_exclusao == MOTIVO_GATEWAY
        assert "is missing a value" in j.evidencia_do_rotulo
    assert celula_minutos_esperados(gateway) == 2321
    assert len(janelas_esperadas_de("088")) == 8
    assert celula_minutos_esperados(janelas_esperadas_de("088")) == 14091


def test_a_088_e_interceptada_e_a_127_mitigada():
    """INV-R11: ocorrencia e atuacao da guarda sao eixos independentes."""
    for j in janelas_esperadas_de("088"):
        assert (j.natureza, j.desfecho, j.causa) == (
            "ocorrencia_operacional",
            "interceptada",
            CAUSA_088,
        )
    for j in janelas_esperadas_de("127"):
        assert (j.natureza, j.desfecho, j.causa) == (
            "ocorrencia_operacional",
            "mitigada",
            CAUSA_127,
        )
        assert "dial tcp" in j.evidencia_do_rotulo


def test_a_088_continua_campea_pelo_gabarito():
    por_causa = {
        c: celula_minutos_esperados(janelas_com_causa(c)) for c in causas_medidas()
    }
    assert max(por_causa, key=por_causa.get) == CAUSA_088
    assert por_causa[CAUSA_088] > 5 * por_causa[CAUSA_127], (
        "a 088 vence por folga mesmo perdendo as duas janelas de gateway, e e "
        "por isso que ela continua sendo a fatia vertical desta entrega"
    )


def test_a_ambiguidade_e_a_ausencia_de_casamento_sao_ERROR_separados():
    ambiguas = janelas_com_natureza("ERROR_ambiguidade")
    assert len(ambiguas) == 1
    assert {"127", "209"} <= set(
        ambiguas[0].sinais_observados_pelo_detector_atual
    )
    assert ambiguas[0].motivo_de_exclusao == MOTIVO_AMBIGUIDADE

    sem_casamento = janelas_com_natureza("ERROR_sem_casamento")
    assert len(sem_casamento) == 2
    for j in sem_casamento:
        assert not j.sinais_observados_pelo_detector_atual
        assert j.motivo_de_exclusao == MOTIVO_SEM_CASAMENTO


def test_os_cinco_estados_do_detector_cobrem_as_37_janelas():
    """A saida de hoje, medida, sem embelezamento."""
    estados = {
        "reconhecida": 24,
        "invisivel": 7,
        "mal_classificada": 1,
        "acusa_sem_rotulo": 1,
        "calada_sem_rotulo": 4,
    }
    for nome, quantas in estados.items():
        assert len(janelas_com_estado(nome)) == quantas, nome
    assert sum(estados.values()) == len(JANELAS)
    assert {j.estado_inicial_do_detector for j in JANELAS} == set(estados)


def test_a_divergencia_contra_o_relatorio_esta_declarada_e_e_pequena():
    assert len(JANELAS) == TABELA_DO_RELATORIO["janelas"]
    assert len([j for j in JANELAS if j.fim]) == (
        TABELA_DO_RELATORIO["janelas_fechadas"]
    )
    assert len([j for j in JANELAS if not j.fim]) == (
        TABELA_DO_RELATORIO["janelas_abertas"]
    )
    assert len(janelas_esperadas_de("127")) == TABELA_DO_RELATORIO["janelas_127"]
    assert len(janelas_com_natureza("ERROR_ambiguidade")) == (
        TABELA_DO_RELATORIO["janelas_ambiguas_127_209"]
    )
    assert len(janelas_com_natureza("ERROR_sem_casamento")) == (
        TABELA_DO_RELATORIO["janelas_nao_classificadas"]
    )
    assert (
        abs(
            celula_minutos_esperados(janelas_esperadas_de("127"))
            - TABELA_DO_RELATORIO["celula_minutos_127"]
        )
        <= 5
    )
    # O relatorio nao separava a causa de gateway, entao a contagem da 088
    # diverge em 2. O bloco somado ainda reconstitui o numero publicado.
    assert len(janelas_esperadas_de("088")) == (
        TABELA_DO_RELATORIO["janelas_088"] - 2
    )
    bloco = celula_minutos_esperados(
        janelas_esperadas_de("088")
    ) + celula_minutos_esperados(janelas_com_causa(CAUSA_GATEWAY))
    assert abs(bloco - TABELA_DO_RELATORIO["celula_minutos_088"]) <= 5, (
        f"as duas partes somam {bloco} e o relatorio publicou "
        f"{TABELA_DO_RELATORIO['celula_minutos_088']}"
    )


def test_a_regua_congelada_prende_o_registro():
    assert (
        RAIZ / ".github" / "workflows" / f"{WORKFLOW_MEDIDO}.yml"
    ).is_file(), (
        f"a regua diz medir o workflow {WORKFLOW_MEDIDO}, que precisa existir"
    )
    conferido = subprocess.run(
        ["git", "cat-file", "-e", f"{BASE}^{{commit}}"],
        cwd=RAIZ,
        capture_output=True,
    )
    assert conferido.returncode == 0, (
        f"a base declarada {BASE} nao existe neste repositorio, entao a "
        "medicao nao e reproduzivel"
    )
    for j in JANELAS:
        assert JANELA_INICIO <= j.inicio < JANELA_FIM, (
            f"a janela de {j.celula} no run {j.abre_run} abre em {j.inicio}, "
            "fora do intervalo declarado: medicao fora da regua nao conta"
        )
    celulas = len([d for d in (RAIZ / "services").iterdir() if d.is_dir()])
    assert len(JANELAS) <= JOBS_DE_CELULA <= RUNS_ENUMERADOS * celulas
    assert len({j.abre_run for j in JANELAS}) == len(JANELAS)


def test_so_o_vermelho_abre_janela_e_o_cancelado_fica_de_fora():
    assert CONCLUSOES_QUE_ABREM_JANELA == ("failure",)
    dentro = sum(len(j.jobs_vermelhos) for j in JANELAS)
    assert dentro == JOBS_DE_CELULA_FALHOS, (
        "todo job vermelho de celula da janela cai dentro de alguma janela"
    )
    assert dentro != JOBS_DE_CELULA_FALHOS + JOBS_DE_CELULA_CANCELADOS, (
        "se `cancelled` abrisse janela, os 9 jobs cancelados entrariam na "
        "conta e a tabela historica deixaria de fechar"
    )


def test_assinatura_da_088_com_acento_nao_casa_nenhum_log_real():
    """O acento e o motivo de a 088 ser invisivel: 48 de 48 logs sao mojibake."""
    acentuado = "não tem serviço algum"
    for log in (
        LOG_088_EXECUTADO,
        LOG_088_SO_ECO,
        LOG_088_MENTIRA_DA_CHAVE_DO_GATEWAY,
    ):
        assert acentuado not in log, (
            "um sinal com acento casaria este log, e nos 76 logs vermelhos "
            "medidos em 18/09/2026 ele casa ZERO. O log vem em UTF-8 "
            "duplamente codificado. Escreva o sinal no trecho sem acento."
        )
    for j in janelas_esperadas_de("088"):
        assert acentuado not in j.evidencia_do_rotulo


def test_o_trecho_sem_acento_casa_os_tres_logs_que_contem_a_recusa():
    ancora = "algum em /opt/plataforma/docker-compose.yml"
    assert ancora in LOG_088_EXECUTADO
    assert ancora in LOG_088_SO_ECO
    assert ancora in LOG_088_MENTIRA_DA_CHAVE_DO_GATEWAY
    assert ancora not in LOG_SAUDAVEL


def test_o_eco_do_codigo_tem_DUAS_formas_e_so_uma_tem_ansi():
    """A correcao do que eu havia afirmado antes: ANSI nao e a marca unica."""
    linhas_eco = [
        l for l in LOG_088_SO_ECO.splitlines() if "algum em /opt" in l
    ]
    assert linhas_eco, "a fixture do eco precisa conter a frase"
    for linha in linhas_eco:
        assert CIANO in linha, "eco de passo `run:` vem em ciano-negrito"
        assert "$CELULA" in linha, (
            "e ele tambem traz a variavel NAO expandida, que e a marca que "
            "pega tambem o eco cru da ssh-action anterior a 28/08/2026"
        )

    linhas_exec = [
        l for l in LOG_088_EXECUTADO.splitlines() if "algum em /opt" in l
    ]
    assert linhas_exec, "a fixture da execucao precisa conter a frase"
    for linha in linhas_exec:
        assert CIANO not in linha and "$CELULA" not in linha
        assert "'encomendas'" in linha, "a execucao imprime a celula expandida"

    for log in (LOG_088_SO_ECO, LOG_088_EXECUTADO):
        for linha in log.splitlines():
            if "algum em /opt" in linha:
                assert linha.startswith("2026-"), (
                    "no log bruto da API eco e execucao tem carimbo de tempo, "
                    "entao aqui o carimbo nao discrimina; a tabela da "
                    "armadilha 114 vale para a visao do `gh run view "
                    "--log-failed`, que e outra fonte"
                )


def test_a_recusa_da_088_pode_mentir_quando_o_compose_nao_interpola():
    assert "is missing a value" in LOG_088_MENTIRA_DA_CHAVE_DO_GATEWAY
    assert "is missing a value" not in LOG_088_EXECUTADO, (
        "a ocorrencia legitima da 088 nao carrega a falha de interpolacao; "
        "quem carrega tem outra causa e nao pode entrar no custo da 088"
    )


def test_a_209_coocorre_com_a_127_por_desenho():
    assert "dial tcp" in LOG_209_SONDA_MAIS_127
    assert "PAROU POR SEGURAN" in LOG_209_SONDA_MAIS_127, (
        "a sonda cita o soluco da 127 ao negar que seja ele, entao os dois "
        "sinais casam o mesmo texto: isso exige ERROR, nao o primeiro"
    )


def test_sinal_que_casa_log_saudavel_perde_autoridade():
    """INV-R04 aplicado ao catalogo VIVO, nunca a uma copia digitada."""
    for numero, medidos in SINAIS_GENERICOS_MEDIDOS.items():
        vivos = sinais_declarados(numero)
        assert vivos, f"a armadilha {numero} precisa declarar `sinal:`"
        for regex in medidos:
            if regex not in vivos:
                continue  # o catalogo apertou o sinal: e conserto, nao falha
            assert re.search(regex, LOG_SAUDAVEL), (
                f"o sinal {regex!r} da armadilha {numero} ainda esta declarado "
                "e casava log saudavel em 18/09/2026; se deixou de casar, "
                "atualize LOG_SAUDAVEL, porque o gabarito ficou fraco"
            )
    for especifico in ("algum em /opt/plataforma", "dial tcp"):
        assert not re.search(especifico, LOG_SAUDAVEL), (
            f"o sinal especifico {especifico!r} nao pode casar log saudavel"
        )
    # A desqualificacao e por regex, nao por armadilha: a 351 tem cinco sinais
    # e so um caiu. O registro so pode ATRIBUIR a quem tem autoridade.
    for j in JANELAS:
        assert j.armadilha_esperada not in SINAIS_GENERICOS_MEDIDOS


def test_a_195_e_prova_e_nunca_ocorrencia():
    """Citacao nao e queda: 37 mencoes em origin/main e zero janelas."""
    assert "195" not in {j.armadilha_esperada for j in JANELAS}, (
        "a 195 nao abriu nenhuma janela de indisponibilidade; contar suas "
        "mencoes como reincidencia foi o erro que este plano existe para "
        "desfazer"
    )
    assert "PROVA VERMELHO->VERDE" in LOG_195_CITACAO_COMO_PROVA
    assert "morreram na ASSERCAO" in LOG_195_CITACAO_COMO_PROVA
    assert "TypeError" in LOG_195_VERMELHO_DE_CONSTRUCAO, (
        "o vermelho que morre montando o objeto nao prova decisao nenhuma, e "
        "e esse o caso que a 195 manda recusar"
    )
