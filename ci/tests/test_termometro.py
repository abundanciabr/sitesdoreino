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
from datetime import datetime, timedelta
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
MOTIVO_ANTES_DA_LICAO = (
    "a licao entrou no repositorio DEPOIS deste run: e a queda que a escreveu, "
    "e nao uma reincidencia dela (item 3 da secao 18)"
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
        natureza='ERROR_anterior_a_licao',
        desfecho='desconhecida',
        causa=CAUSA_127,
        motivo_de_exclusao=MOTIVO_ANTES_DA_LICAO,
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
        natureza='ERROR_anterior_a_licao',
        desfecho='desconhecida',
        causa=CAUSA_088,
        motivo_de_exclusao=MOTIVO_ANTES_DA_LICAO,
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


def apos(carimbo: str, horas: int) -> str:
    """O mesmo instante, tantas horas depois, no formato do Actions."""
    quando = _instante(carimbo) + timedelta(hours=horas)
    return quando.isoformat().replace("+00:00", "Z")


def janelas_esperadas_de(armadilha: str) -> tuple[Janela, ...]:
    """Pelo GABARITO. O nome diz de onde vem para ninguem ler como saida."""
    return tuple(j for j in JANELAS if j.armadilha_esperada == armadilha)


def janelas_que_reincidem(armadilha: str) -> tuple[Janela, ...]:
    """As do gabarito que a licao JA explicava quando o run rodou.

    A queda que escreveu a licao nao reincide nela (item 3 da secao 18): ela
    continua no registro, com o motivo dito, e fora do custo da candidata.
    """
    return tuple(
        j for j in janelas_esperadas_de(armadilha)
        if j.natureza == "ocorrencia_operacional"
    )


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


def ranking_esperado_do_corpus() -> list[str]:
    """A ordem que o gabarito manda, por tempo comprovado ate a celula publicar.

    Derivada, nunca digitada: uma janela mexida no registro move esta lista e
    a do quadro juntas, que e o unico jeito de o teste continuar valendo.
    """
    medidos = {
        "armadilhas/088": celula_minutos_esperados(janelas_que_reincidem("088")),
        "armadilhas/127": celula_minutos_esperados(janelas_que_reincidem("127")),
        f"causa/{CAUSA_GATEWAY}": celula_minutos_esperados(
            janelas_com_causa(CAUSA_GATEWAY)
        ),
    }
    return sorted(medidos, key=lambda chave: -medidos[chave])


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
        len(janelas_com_natureza(n)) for n in NATUREZA_DA_FASE_3
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
            assert j.desfecho == "desconhecida"
            # A queda que ESCREVEU a licao e a unica forma de ERROR que sabe de
            # qual armadilha ela e: e exatamente por saber a armadilha que da
            # para ver que a licao e mais nova que o run.
            if j.natureza == "ERROR_anterior_a_licao":
                assert j.armadilha_esperada and j.causa
            else:
                assert j.armadilha_esperada is None and j.causa is None
        if j.armadilha_esperada is None or j.natureza == "ERROR_anterior_a_licao":
            assert j.motivo_de_exclusao, (
                f"a janela de {j.celula} no run {j.abre_run} sai do custo de "
                "alguma candidata e precisa dizer por que"
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
    for j in janelas_que_reincidem("088"):
        assert (j.natureza, j.desfecho, j.causa) == (
            "ocorrencia_operacional",
            "interceptada",
            CAUSA_088,
        )
    for j in janelas_que_reincidem("127"):
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


# ==========================================================================
# F2: a coleta terminal. Tudo offline, por costura injetada.
#
# O que a Fase 2 existe para impedir, e o que cada teste daqui para baixo
# prende:
#
#   1. A API do Actions entrega no MAXIMO 1000 runs por consulta e TRUNCA
#      CALADA. A janela medida tem 1379 runs de `deploy-celula`. Uma consulta
#      so devolveria 1000 e pareceria completa. Por isso a coleta fatia por
#      DATA, e uma fatia que anuncia mais de 1000 vira ERROR em vez de medir
#      pela metade.
#   2. Fatias vizinhas compartilham a data da borda de proposito: sobreposicao
#      nao deixa buraco entre fatias. O preco e o run repetido, e ele tem de
#      virar UM run e UM download.
#   3. Log indisponivel e ERROR, nunca ausencia de problema (INV-R08).
#   4. A medicao sai do SHA publicado. Arvore local suja nao pode mover
#      resultado nenhum: foi ler o worktree que reprovou
#      `celulas_sem_publicacao` para este uso.
# ==========================================================================

import pytest  # noqa: E402

import termometro  # noqa: E402


def _run(
    identificador: int,
    *,
    sha: str,
    conclusao: str | None = "success",
    criado: str = "2026-08-18T10:00:00Z",
    atualizado: str | None = None,
    tentativa: int = 1,
    estado: str = "completed",
) -> dict:
    """Um run como a API do Actions o devolve, com a identidade completa.

    `node_id` e `run_attempt` nao sao enfeite: `consultar_jobs_em_lote` recusa
    o lote sem eles, e e por eles que a triagem barata acontece.
    """
    return {
        "id": identificador,
        "node_id": f"WFR_{identificador}",
        "run_attempt": tentativa,
        "head_sha": sha,
        "created_at": criado,
        "updated_at": atualizado or criado,
        "status": estado,
        "conclusion": conclusao,
    }


def _job(identificador: int, nome: str, conclusao: str) -> dict:
    return {"id": identificador, "name": nome, "conclusion": conclusao,
            "status": "completed"}


class Bancada:
    """As quatro costuras, sem rede, anotando cada chamada.

    Ela nao imita o GitHub por gosto: cada campo aqui existe porque a coleta
    de verdade depende dele. `anunciado` mente o `total_count` para provar
    truncamento e paginacao incompleta sem precisar de 1000 runs de mentira.
    """

    def __init__(
        self,
        *,
        runs: dict[tuple[str, str], list[dict]],
        jobs: dict[int, list[dict]] | None = None,
        logs: dict[int, object] | None = None,
        ancestrais: tuple[tuple[str, str], ...] = (),
        anunciado: dict[tuple[str, str], int] | None = None,
        por_pagina: int = 100,
        sujeira: str = "",
        base_sha: str = "",
        runs_por_data: list[dict] | None = None,
    ) -> None:
        self.runs = runs
        self.jobs = jobs or {}
        self.logs = logs or {}
        self.ancestrais = set(ancestrais)
        self.anunciado = anunciado or {}
        self.por_pagina = por_pagina
        self.sujeira = sujeira
        self.base_sha = base_sha or sha_desta_bancada()
        # O gatilho terminal CALCULA a janela que vai medir, entao ele pede
        # fatias que nenhum teste digitou. Com esta lista, a bancada responde
        # por data, como a API faz, em vez de por uma chave combinada antes.
        self.runs_por_data = runs_por_data
        self.caminhos: list[str] = []
        self.lotes: list[list[dict]] = []
        self.logs_baixados: list[int] = []
        self.comandos_git: list[tuple[str, ...]] = []

    # -- costura 1: a porta REST -------------------------------------------
    def api(self, caminho: str) -> dict:
        self.caminhos.append(caminho)
        if "actions/workflows/" in caminho:
            casou = re.search(r"created=([0-9-]+)\.\.([0-9-]+)", caminho)
            assert casou, f"consulta sem recorte de data: {caminho}"
            chave = (casou.group(1), casou.group(2))
            pagina = int(re.search(r"[?&]page=(\d+)", caminho).group(1))
            lista = self.runs.get(chave)
            if lista is None and self.runs_por_data is not None:
                lista = [
                    r for r in self.runs_por_data
                    if chave[0] <= r["created_at"][:10] <= chave[1]
                ]
            lista = lista or []
            inicio = (pagina - 1) * self.por_pagina
            return {
                "total_count": self.anunciado.get(chave, len(lista)),
                "workflow_runs": lista[inicio:inicio + self.por_pagina],
            }
        avulso = re.fullmatch(r"actions/runs/(\d+)", caminho)
        if avulso:
            procurado = int(avulso.group(1))
            todos = [r for lista in self.runs.values() for r in lista]
            todos += list(self.runs_por_data or ())
            achados = [r for r in todos if r["id"] == procurado]
            assert achados, f"run {procurado} nao existe nesta bancada"
            return dict(achados[0])
        casou = re.search(r"actions/runs/(\d+)/jobs", caminho)
        assert casou, f"caminho REST inesperado: {caminho}"
        lista = self.jobs.get(int(casou.group(1)), [])
        return {"total_count": len(lista), "jobs": lista}

    # -- costura 2: a triagem barata em lote -------------------------------
    def jobs_em_lote(self, runs: list[dict]) -> dict[int, list[dict]]:
        if not 1 <= len(runs) <= 8:
            raise AssertionError(
                f"lote de {len(runs)} runs: o GraphQL desta casa so aceita de "
                "1 a 8, e estourar isso e a recusa que o teste existe para pegar"
            )
        self.lotes.append(list(runs))
        return {r["id"]: list(self.jobs.get(r["id"], [])) for r in runs}

    # -- costura 3: o log cru ----------------------------------------------
    def baixar_log(self, id_do_job: int):
        self.logs_baixados.append(id_do_job)
        valor = self.logs.get(id_do_job)
        if isinstance(valor, Exception):
            raise valor
        return valor

    # -- costura 4: o git, e SO pelo banco de objetos ----------------------
    def git(self, args: list[str]) -> tuple[int, str]:
        self.comandos_git.append(tuple(args))
        if args[:2] == ["merge-base", "--is-ancestor"]:
            return (0 if (args[2], args[3]) in self.ancestrais else 1, "")
        if args[0] == "rev-parse":
            return (0, self.base_sha) if self.base_sha else (128, "ref ausente")
        return 0, self.sujeira


def _coletar(bancada: Bancada, **extras) -> dict:
    padrao = dict(
        desde="2026-08-18", ate="2026-08-21", api=bancada.api,
        baixar_log=bancada.baixar_log, git=bancada.git,
        jobs_em_lote=bancada.jobs_em_lote,
    )
    padrao.update(extras)
    return termometro.coletar(**padrao)


# -- a) teto de 1000 -------------------------------------------------------


def test_fatia_que_anuncia_mais_de_mil_runs_e_ERROR_e_nao_baixa_log_nenhum():
    """1379 runs na janela: uma consulta so devolveria 1000 e mentiria verde.

    O teto nao pode virar "medi o que deu": a fatia estourada para a coleta
    INTEIRA antes de qualquer download, porque um denominador truncado
    contamina todo numero que sai depois dele.
    """
    fatia = ("2026-08-18", "2026-08-21")
    # A bancada SERVE os 1001 runs que anuncia. Se ela mentisse o total e
    # entregasse um, quem recusaria seria a regra de paginacao incompleta, e
    # este teste ficaria verde mesmo com o teto removido: um teste que nao
    # testa nada.
    demais = [_run(n, sha=f"sha{n}") for n in range(2, termometro.TETO_DA_API + 2)]
    bancada = Bancada(
        runs={fatia: [_run(1, sha="aaa", conclusao="failure")] + demais},
        jobs={1: [_job(10, "deploy (mensageria)", "failure")]},
        logs={10: "qualquer coisa"},
    )
    assert len(bancada.runs[fatia]) == termometro.TETO_DA_API + 1
    with pytest.raises(termometro.ErroDeColeta) as erro:
        _coletar(bancada)
    assert "1001" in str(erro.value)
    assert bancada.logs_baixados == [], (
        "a coleta baixou log depois de saber que o denominador estava "
        "truncado; medida parcial que parece inteira e exatamente o falso "
        "verde que a fatia por data existe para impedir"
    )


def test_o_teto_e_o_limite_real_da_api_e_nao_um_numero_generoso():
    assert termometro.TETO_DA_API == 1000
    assert RUNS_ENUMERADOS > termometro.TETO_DA_API, (
        "se a janela medida coubesse em uma consulta, o fatiamento por data "
        "seria enfeite; ela nao cabe, e e por isso que ele existe"
    )


# -- b) log indisponivel ---------------------------------------------------


def test_log_indisponivel_vira_ERROR_e_nunca_ausencia_de_problema():
    """INV-R08: nao consegui ler nao e nada aconteceu.

    As duas formas de indisponibilidade caem no mesmo estado: a costura que
    devolve None (o `gh` saiu com codigo diferente de zero) e a que explode
    (rede caiu no meio). Nenhuma das duas pode fechar a janela nem sumir do
    relatorio.
    """
    fatia = ("2026-08-18", "2026-08-21")
    for valor in (None, RuntimeError("gh api saiu 1")):
        bancada = Bancada(
            runs={fatia: [_run(1, sha="aaa", conclusao="failure")]},
            jobs={1: [_job(10, "deploy (mensageria)", "failure")]},
            logs={10: valor},
        )
        resultado = _coletar(bancada)
        assert resultado["logs_indisponiveis"], (
            f"log {valor!r} sumiu do relatorio: ausencia de leitura virou "
            "ausencia de problema"
        )
        assert resultado["logs_lidos"] == 0
        assert [j["estado_do_log"] for j in resultado["janelas"]] == ["ERROR"]
        assert resultado["janelas"][0]["celula"] == "mensageria"


# -- c) arvore local suja --------------------------------------------------


def test_arvore_local_suja_nao_muda_o_resultado():
    """A medicao sai do SHA publicado, nao do worktree.

    Foi ler o worktree que desqualificou `celulas_sem_publicacao` para este
    uso. Duas coletas identicas, uma delas com a bancada respondendo sujeira
    a qualquer comando fora do banco de objetos, tem de dar o MESMO resultado
    e nao podem ter perguntado nada ao worktree.
    """
    fatia = ("2026-08-18", "2026-08-21")

    def monta(sujeira: str) -> Bancada:
        return Bancada(
            runs={fatia: [
                _run(1, sha="aaa", conclusao="failure",
                     criado="2026-08-18T10:00:00Z"),
                _run(2, sha="bbb", conclusao="success",
                     criado="2026-08-18T12:00:00Z"),
            ]},
            jobs={1: [_job(10, "deploy (mensageria)", "failure")],
                  2: [_job(20, "deploy (mensageria)", "success")]},
            logs={10: "recusa"},
            ancestrais=(("aaa", "bbb"),),
            sujeira=sujeira,
        )

    limpa, suja = monta(""), monta(" M services/mensageria/app.py\n?? lixo.txt")
    assert _coletar(limpa) == _coletar(suja)
    assert limpa.comandos_git, "sem pergunta de ancestralidade nao ha cobertura medida"
    for comando in limpa.comandos_git + suja.comandos_git:
        assert comando[:2] == ("merge-base", "--is-ancestor"), (
            f"a coleta perguntou {comando!r} ao git: qualquer leitura do "
            "worktree coloca o estado da bancada dentro da medicao"
        )


# -- d) borda entre fatias -------------------------------------------------


def test_run_repetido_na_borda_de_duas_fatias_vira_um_run_e_um_download():
    """Fatias vizinhas compartilham a data da borda de proposito.

    Sobrepor e barato e nao deixa buraco; o preco e o run que aparece duas
    vezes, e ele nao pode virar dois runs, dois jobs nem dois downloads do
    mesmo log.
    """
    primeira, segunda = ("2026-08-18", "2026-08-21"), ("2026-08-21", "2026-08-24")
    repetido = _run(1, sha="aaa", conclusao="failure",
                    criado="2026-08-21T09:00:00Z")
    bancada = Bancada(
        runs={primeira: [dict(repetido)], segunda: [dict(repetido)]},
        jobs={1: [_job(10, "deploy (mensageria)", "failure")]},
        logs={10: "recusa"},
    )
    resultado = _coletar(bancada, ate="2026-08-24")
    assert termometro.fatias_de_data("2026-08-18", "2026-08-24", 3) == (
        primeira, segunda
    ), "as fatias tem de encostar na borda; um buraco entre elas perde runs"
    assert resultado["runs_unicos"] == 1
    assert bancada.logs_baixados == [10]
    assert resultado["logs_lidos"] == 1
    assert len(resultado["janelas"]) == 1


def test_o_mesmo_run_com_tentativa_diferente_entre_fatias_e_ERROR():
    """Deduplicar nao pode virar "fico com o primeiro que vi".

    Se o run mudou de tentativa entre uma fatia e outra, a medicao andou
    debaixo da coleta: escolher em silencio qual das duas vale e inventar
    resultado.
    """
    primeira, segunda = ("2026-08-18", "2026-08-21"), ("2026-08-21", "2026-08-24")
    bancada = Bancada(runs={
        primeira: [_run(1, sha="aaa", criado="2026-08-21T09:00:00Z")],
        segunda: [_run(1, sha="aaa", criado="2026-08-21T09:00:00Z", tentativa=2)],
    })
    with pytest.raises(termometro.ErroDeColeta) as erro:
        _coletar(bancada, ate="2026-08-24")
    assert "tentativa" in str(erro.value)


# -- paginacao, conclusao e lote -------------------------------------------


def test_paginacao_incompleta_vira_ERROR_e_nao_medida_parcial():
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [_run(1, sha="aaa"), _run(2, sha="bbb")]},
        anunciado={fatia: 5},
        por_pagina=2,
    )
    with pytest.raises(termometro.ErroDeColeta) as erro:
        _coletar(bancada)
    assert "2 de 5" in str(erro.value)


def test_a_paginacao_junta_todas_as_paginas_da_fatia():
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [_run(n, sha=f"sha{n}") for n in range(1, 6)]},
        por_pagina=2,
    )
    assert _coletar(bancada)["runs_unicos"] == 5
    assert len([c for c in bancada.caminhos if "workflows" in c]) == 3


def test_conclusao_ausente_ou_desconhecida_vira_ERROR():
    fatia = ("2026-08-18", "2026-08-21")
    for conclusao in (None, "", "sei_la"):
        bancada = Bancada(runs={fatia: [_run(1, sha="aaa", conclusao=conclusao)]})
        with pytest.raises(termometro.ErroDeColeta) as erro:
            _coletar(bancada)
        assert "conclus" in str(erro.value).lower()


def test_run_que_ainda_nao_terminou_nao_e_terminal_e_fica_de_fora():
    """Nao terminal nao e ERROR nem queda: e fato que ainda nao aconteceu."""
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(runs={fatia: [
        _run(1, sha="aaa", conclusao=None, estado="in_progress"),
        _run(2, sha="bbb", conclusao="success"),
    ]})
    assert _coletar(bancada)["runs_unicos"] == 1


def test_a_triagem_em_lote_respeita_o_limite_de_oito_runs():
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(runs={fatia: [_run(n, sha=f"sha{n}") for n in range(1, 20)]})
    resultado = _coletar(bancada)
    assert resultado["runs_unicos"] == 19
    assert [len(lote) for lote in bancada.lotes] == [8, 8, 3]
    for lote in bancada.lotes:
        for run in lote:
            assert isinstance(run["node_id"], str) and run["node_id"]
            assert type(run["run_attempt"]) is int


def test_a_triagem_em_lote_recusa_tamanho_fora_da_faixa():
    """A costura aqui RESPONDE certo: a unica razao de recusar e o tamanho.

    Com uma costura que devolve vazio, a recusa viria da checagem de lote
    incompleto e o teste ficaria verde mesmo sem a faixa de 1 a 8.
    """
    runs = tuple(_run(n, sha=f"sha{n}") for n in range(1, 10))

    def respondeu(lote):
        return {r["id"]: [] for r in lote}

    assert termometro.jobs_dos_runs(
        runs, jobs_em_lote=respondeu, tamanho_do_lote=8
    ).keys() == {r["id"] for r in runs}
    for fora_da_faixa in (0, 9):
        with pytest.raises(termometro.ErroDeColeta) as erro:
            termometro.jobs_dos_runs(
                runs, jobs_em_lote=respondeu, tamanho_do_lote=fora_da_faixa
            )
        assert "1 a 8" in str(erro.value)


def test_lote_que_nao_devolve_todos_os_runs_vira_ERROR():
    with pytest.raises(termometro.ErroDeColeta) as erro:
        termometro.jobs_dos_runs(
            (_run(1, sha="aaa"), _run(2, sha="bbb")),
            jobs_em_lote=lambda runs: {runs[0]["id"]: []},
        )
    assert "2" in str(erro.value)


def test_o_mesmo_log_nao_e_baixado_duas_vezes_na_mesma_execucao():
    """Baixar log e a chamada cara da coleta; a segunda vez sai do cache.

    O fracasso tambem entra no cache: repetir um download que ja falhou gasta
    rede para receber a mesma resposta.
    """
    baixados: list[int] = []

    def baixar(id_do_job):
        baixados.append(id_do_job)
        return "recusa" if id_do_job == 10 else None

    cache: dict = {}
    assert termometro.log_do_job(10, baixar_log=baixar, cache=cache) == "recusa"
    assert termometro.log_do_job(10, baixar_log=baixar, cache=cache) == "recusa"
    assert termometro.log_do_job(11, baixar_log=baixar, cache=cache) is None
    assert termometro.log_do_job(11, baixar_log=baixar, cache=cache) is None
    assert baixados == [10, 11]


# -- cobertura por celula --------------------------------------------------


def test_celulas_cobertas_saem_do_nome_do_job_e_so_do_verde():
    cobertas = termometro.celulas_cobertas([
        _job(1, "deploy (mensageria)", "success"),
        _job(2, "deploy (funil)", "failure"),
        _job(3, "portao", "success"),
        _job(4, "deploy (admin)", "success"),
    ])
    assert cobertas == ("admin", "mensageria")


def test_janela_sem_verde_que_cubra_a_celula_continua_aberta():
    """Um verde de OUTRA celula nao publica a que caiu."""
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [
            _run(1, sha="aaa", conclusao="failure", criado="2026-08-18T10:00:00Z"),
            _run(2, sha="bbb", conclusao="success", criado="2026-08-18T12:00:00Z"),
        ]},
        jobs={1: [_job(10, "deploy (mensageria)", "failure")],
              2: [_job(20, "deploy (funil)", "success")]},
        logs={10: "recusa"},
        ancestrais=(("aaa", "bbb"),),
    )
    janela = _coletar(bancada)["janelas"][0]
    assert janela["fechamento"] is None
    assert janela["run_de_fechamento"] is None


def test_o_verde_que_fecha_a_janela_precisa_carregar_o_sha_que_caiu():
    """Deploy anterior ao commit nao publicou o que o commit trouxe."""
    fatia = ("2026-08-18", "2026-08-21")

    def monta(ancestrais):
        return Bancada(
            runs={fatia: [
                _run(1, sha="aaa", conclusao="failure",
                     criado="2026-08-18T10:00:00Z",
                     atualizado="2026-08-18T10:30:00Z"),
                _run(2, sha="bbb", conclusao="success",
                     criado="2026-08-18T12:00:00Z",
                     atualizado="2026-08-18T12:30:00Z"),
            ]},
            jobs={1: [_job(10, "deploy (mensageria)", "failure")],
                  2: [_job(20, "deploy (mensageria)", "success")]},
            logs={10: "recusa"},
            ancestrais=ancestrais,
        )

    fechada = _coletar(monta((("aaa", "bbb"),)))["janelas"][0]
    assert fechada["fechamento"] == "2026-08-18T12:30:00Z"
    assert fechada["run_de_fechamento"] == 2
    aberta = _coletar(monta(()))["janelas"][0]
    assert aberta["fechamento"] is None


def test_a_celula_que_cai_DE_NOVO_sem_verde_no_meio_fica_na_MESMA_janela():
    """A janela e da CELULA, nao do job (INV-R07).

    Tres merges da mesma celula reprovando pela mesma causa, sem nenhum verde
    entre eles, sao UMA indisponibilidade de tres horas. Uma janela por job
    daria tres janelas sobrepostas, e `candidatas` somaria 3h + 2h + 1h = 6h
    de custo onde a celula ficou 3h fora do ar.

    O corpus congelado ja diz isso: 37 janelas para 76 jobs vermelhos.
    """
    fatia = ("2026-09-01", "2026-09-04")
    bancada = Bancada(
        runs={fatia: [
            _run(1, sha="a1", conclusao="failure", criado="2026-09-01T10:00:00Z"),
            _run(2, sha="a2", conclusao="failure", criado="2026-09-01T11:00:00Z"),
            _run(3, sha="a3", conclusao="failure", criado="2026-09-01T12:00:00Z"),
            _run(4, sha="a4", conclusao="success", criado="2026-09-01T13:00:00Z"),
        ]},
        jobs={1: [_job(11, "deploy (sugestoes)", "failure")],
              2: [_job(12, "deploy (sugestoes)", "failure")],
              3: [_job(13, "deploy (sugestoes)", "failure")],
              4: [_job(14, "deploy (sugestoes)", "success")]},
        logs={11: "recusa", 12: "recusa", 13: "recusa"},
        ancestrais=(("a1", "a2"), ("a1", "a3"), ("a2", "a3"),
                    ("a1", "a4"), ("a2", "a4"), ("a3", "a4")),
    )
    medida = _coletar(bancada, desde=fatia[0], ate=fatia[1])
    janelas = medida["janelas"]
    assert len(janelas) == 1, (
        f"{len(janelas)} janelas para uma indisponibilidade continua: cada "
        "sobreposicao soma o mesmo intervalo outra vez no custo"
    )
    janela = janelas[0]
    assert janela["abertura"] == "2026-09-01T10:00:00Z"
    assert janela["fechamento"] == "2026-09-01T13:00:00Z"
    assert janela["run_de_abertura"] == 1
    assert janela["job_de_abertura"] == 11
    assert janela["jobs_vermelhos"] == [11, 12, 13], (
        "a janela tem de dizer TODOS os jobs que cairam nela, senao o rastro "
        "some junto com as janelas duplicadas"
    )
    assert bancada.logs_baixados == [11], (
        "o log que classifica a janela e o do job que a abriu; baixar os "
        "outros e rede gasta para reler a mesma causa"
    )
    custo = um_quadro(termometro.fatos_da_coleta(
        medida, sinais_do_job=lambda job: ("088",),
    ))
    assert custo["ranking"][0]["segundos_ate_cobertura"] == 3 * 3600, (
        "tres janelas sobrepostas somariam 3h + 2h + 1h para uma queda de 3h"
    )


def test_o_verde_no_meio_separa_DUAS_janelas_da_mesma_celula():
    """Publicou, caiu de novo: sao duas quedas, e as duas contam."""
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [
            _run(1, sha="a1", conclusao="failure", criado="2026-08-18T10:00:00Z"),
            _run(2, sha="a2", conclusao="success", criado="2026-08-18T11:00:00Z"),
            _run(3, sha="a3", conclusao="failure", criado="2026-08-18T12:00:00Z"),
            _run(4, sha="a4", conclusao="success", criado="2026-08-18T13:00:00Z"),
        ]},  # o custo nao entra neste caso: aqui se conta JANELA, nao minuto
        jobs={1: [_job(11, "deploy (cursos)", "failure")],
              2: [_job(12, "deploy (cursos)", "success")],
              3: [_job(13, "deploy (cursos)", "failure")],
              4: [_job(14, "deploy (cursos)", "success")]},
        logs={11: "recusa", 13: "recusa"},
        ancestrais=(("a1", "a2"), ("a1", "a3"), ("a1", "a4"),
                    ("a2", "a3"), ("a2", "a4"), ("a3", "a4")),
    )
    janelas = _coletar(bancada)["janelas"]
    assert [j["run_de_abertura"] for j in janelas] == [1, 3]
    assert [j["run_de_fechamento"] for j in janelas] == [2, 4]
    assert [j["jobs_vermelhos"] for j in janelas] == [[11], [13]]


def test_a_janela_so_fecha_no_verde_que_carrega_TODOS_os_commits_que_cairam():
    """Fechar no primeiro commit declararia publicado o trabalho dos merges
    seguintes, que continuam fora do ar."""
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [
            _run(1, sha="a1", conclusao="failure", criado="2026-08-18T10:00:00Z"),
            _run(2, sha="a2", conclusao="failure", criado="2026-08-18T11:00:00Z"),
            _run(3, sha="a3", conclusao="success", criado="2026-08-18T12:00:00Z"),
        ]},
        jobs={1: [_job(11, "deploy (forum)", "failure")],
              2: [_job(12, "deploy (forum)", "failure")],
              3: [_job(13, "deploy (forum)", "success")]},
        logs={11: "recusa", 12: "recusa"},
        # O verde carrega o commit da PRIMEIRA queda, e nao o da segunda.
        ancestrais=(("a1", "a2"), ("a1", "a3")),
    )
    janela = _coletar(bancada)["janelas"][0]
    assert janela["fechamento"] is None
    assert janela["jobs_vermelhos"] == [11, 12]


def test_o_registro_congelado_conta_JANELA_e_nao_JOB_vermelho():
    """A regua da Fase 0 ja separava as duas contagens; a coleta passou a
    respeitar isso."""
    assert len(JANELAS) == 37
    assert sum(len(j.jobs_vermelhos) for j in JANELAS) == JOBS_DE_CELULA_FALHOS
    assert JOBS_DE_CELULA_FALHOS > len(JANELAS), (
        "sem janela com mais de um job vermelho este teste nao prova nada"
    )
    for janela in JANELAS:
        assert janela.abre_job in janela.jobs_vermelhos


def test_o_cancelado_nao_abre_janela_na_coleta_tambem():
    """A mesma regra do corpus congelado, agora na coleta.

    O caso que separa e o run CANCELADO que carrega job de celula VERMELHO:
    a cancelada chegou depois de um job ja ter morrido. Quem decide e a
    conclusao do RUN. Se o vermelho de dentro abrisse janela, a contagem
    sairia das 37 e o corpus da Fase 0 nao fecharia mais.
    """
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [_run(1, sha="aaa", conclusao="cancelled")]},
        jobs={1: [_job(10, "deploy (mensageria)", "failure"),
                  _job(11, "deploy (funil)", "cancelled")]},
        logs={10: "recusa"},
    )
    resultado = _coletar(bancada)
    assert resultado["janelas"] == []
    assert bancada.logs_baixados == []
    assert termometro.CONCLUSAO_QUE_ABRE_JANELA == CONCLUSOES_QUE_ABREM_JANELA[0]


def test_jobs_truncados_na_porta_REST_viram_ERROR():
    """A mesma regra de `consultar_jobs`: menos jobs que o anunciado e ERROR."""
    with pytest.raises(termometro.ErroDeColeta) as erro:
        termometro.jobs_com_id(
            {"id": 1},
            api=lambda caminho: {"total_count": 3, "jobs": [_job(10, "x", "failure")]},
        )
    assert "truncad" in str(erro.value)


def test_o_relatorio_da_coleta_conta_as_chamadas_que_fez():
    """Evidencia para auditoria: quantas chamadas, nao "foi rapido"."""
    fatia = ("2026-08-18", "2026-08-21")
    bancada = Bancada(
        runs={fatia: [_run(1, sha="aaa", conclusao="failure")]},
        jobs={1: [_job(10, "deploy (mensageria)", "failure")]},
        logs={10: "recusa"},
    )
    contagem = _coletar(bancada)["chamadas"]
    assert contagem == {"api": 2, "jobs_em_lote": 1, "log": 1, "git": 0}


# -- as fatias -------------------------------------------------------------


def test_fatias_de_data_recusam_data_torta_e_intervalo_invertido():
    with pytest.raises(termometro.ErroDeColeta):
        termometro.fatias_de_data("18/08/2026", "2026-09-18")
    with pytest.raises(termometro.ErroDeColeta):
        termometro.fatias_de_data("2026-09-18", "2026-08-18")
    with pytest.raises(termometro.ErroDeColeta):
        termometro.fatias_de_data("2026-08-18", "2026-09-18", 0)


def test_a_janela_medida_inteira_cabe_em_fatias_que_se_encostam():
    fatias = termometro.fatias_de_data(JANELA_INICIO[:10], JANELA_FIM[:10])
    assert fatias[0][0] == JANELA_INICIO[:10]
    assert fatias[-1][1] == JANELA_FIM[:10]
    for anterior, seguinte in zip(fatias, fatias[1:]):
        assert anterior[1] == seguinte[0]


# -- o comportamento antigo ------------------------------------------------


def test_a_coleta_nao_entrou_no_caminho_de_sempre():
    """`python ci/termometro.py` continua lendo so a telemetria local.

    A coleta custa rede e so roda sob bandeira explicita; se ela vazar para o
    caminho padrao, o relatorio de todo dia passa a depender do GitHub.
    """
    assert termometro.resumir([])["eventos"] == 0
    assert set(termometro.resumir([])) == {
        "eventos", "por_armadilha", "por_modo", "sessoes", "reincidencias"
    }
    assert termometro.quer_coleta([]) is False
    assert termometro.quer_coleta(["--json"]) is False
    for bandeira in ("--historico", "--desde=2026-08-18", "--ate=2026-09-18"):
        assert termometro.quer_coleta([bandeira]) is True


def test_o_modulo_nao_importa_yaml_no_topo():
    """`estado_da_entrega` puxa PyYAML; no topo daqui ele quebra maquina sem.

    O termometro de todo dia depende so de `telemetria`, e e por isso que os
    imports da coleta moram DENTRO das funcoes.
    """
    fonte = (CI / "termometro.py").read_text(encoding="utf-8")
    topo = fonte.split("\ndef ", 1)[0]
    for proibido in ("import yaml", "import estado_da_entrega",
                     "import mapa_de_celulas", "import rerun_de_deploy"):
        assert proibido not in topo, (
            f"{proibido!r} no topo do modulo: quem so quer o relatorio local "
            "passa a precisar de PyYAML instalado"
        )


# ---------------------------------------------------------------------------
# A COSTURA ENTRE O WORKFLOW E O INSTRUMENTO.
#
# `.github/workflows/vacina-do-deploy.yml` chama `ci/termometro.py --run <id>`.
# Enquanto a medicao por run nao existir, essa bandeira TEM de recusar alto.
# Antes deste guarda ela caia no relatorio de telemetria local e saia 0: o job
# ficaria verde sem ter medido nada, que e o falso verde que este instrumento
# inteiro existe para acabar.
# ---------------------------------------------------------------------------


def _bandeira_que_o_workflow_chama() -> str:
    """Le do YAML, nao de uma copia digitada: se o job trocar de bandeira,
    este teste tem de mudar junto."""
    yml = (
        RAIZ / ".github" / "workflows" / "vacina-do-deploy.yml"
    ).read_text(encoding="utf-8")
    chamadas = [
        linha for linha in yml.splitlines() if "ci/termometro.py" in linha
    ]
    assert len(chamadas) == 1, (
        f"esperava uma unica chamada ao termometro no workflow, achei "
        f"{len(chamadas)}"
    )
    for palavra in chamadas[0].split():
        if palavra.startswith("--"):
            return palavra.split("=")[0]
    raise AssertionError(f"chamada sem bandeira: {chamadas[0]!r}")


def test_a_bandeira_que_o_workflow_chama_nunca_sai_zero_sem_medir():
    import subprocess as _sp

    bandeira = _bandeira_que_o_workflow_chama()
    saida = _sp.run(
        [sys.executable, str(RAIZ / "ci" / "termometro.py"), bandeira, "12345"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert saida.returncode == 2, (
        f"`{bandeira}` saiu {saida.returncode}: bandeira reconhecida que nao "
        "mede e nao recusa deixa o job verde sem medicao nenhuma"
    )
    texto = saida.stdout + saida.stderr
    assert "NAO MEDI" in texto or "PAROU POR SEGURAN" in texto
    assert "O QUE FAZER" in texto, "toda recusa diz o que fazer"


def test_a_bandeira_sem_valor_tambem_recusa():
    """Sem numero nao ha run: isso e RECUSA (1), e nao erro de medicao (2).

    O dialeto de saida da casa separa os dois de proposito: 1 e chamada
    errada, que quem chamou conserta; 2 e "nao consegui medir", que manda
    olhar o instrumento.
    """
    import subprocess as _sp

    saida = _sp.run(
        [sys.executable, str(RAIZ / "ci" / "termometro.py"), "--run"],
        cwd=RAIZ,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    assert saida.returncode == 1
    texto = saida.stdout + saida.stderr
    assert "RECUSADO" in texto
    assert "O QUE FAZER" in texto, "toda recusa diz o que fazer"


# ==========================================================================
# F3: classificação, custo e ranking.
#
# ONDE COLAR: ao fim de `ci/tests/test_termometro.py`, depois do bloco da
# Fase 2. Estes testes usam o corpus congelado da Fase 0 como fixture — as 37
# janelas REAIS, com run, job, tentativa e carimbo conferíveis na API — em vez
# de dados inventados. Quando um caso precisa de algo que não aconteceu (a 127
# que não foi recuperada, por exemplo), ele parte de uma janela real e diz, no
# nome e no docstring, o que tirou dela.
#
# O que cada bloco daqui prende:
#
#   1. Os dois eixos não se misturam (INV-R11). O teste grande compara as 37
#      janelas contra o GABARITO auditado: natureza e desfecho, os dois, para
#      todas. Se alguém trocar a regra da 088 para "interceptada, logo não é
#      ocorrência", 8 janelas divergem de uma vez.
#   2. Menção não é queda (INV-R02) e prova não é dor: a 195 tem 37 citações
#      em origin/main e ZERO janelas, e continua fora do ranking mesmo com as
#      citações todas na entrada.
#   3. Deduplicação na ordem do plano, inclusive o caso feio: a citação que
#      chega ANTES da queda medida.
#   4. Custo sem peso inventado: minuto só existe entre dois carimbos reais, e
#      o fim da janela de consulta nunca vira resolução.
#   5. Um só objeto: mexer no JSON move a tabela junto, e o teste mexe.
# ==========================================================================

import ast  # noqa: E402
import json  # noqa: E402
import random  # noqa: E402

# O gabarito da Fase 0 nomeia as duas formas de ERROR separadamente, porque
# ambiguidade e ausência de casamento pedem conserto diferente. No vocabulário
# da Fase 3 as duas são `nao_classificada` — o MOTIVO é que as separa, e o
# teste confere motivo por motivo mais abaixo.
NATUREZA_DA_FASE_3 = {
    "ocorrencia_operacional": "ocorrencia_operacional",
    "ERROR_ambiguidade": "nao_classificada",
    "ERROR_sem_casamento": "nao_classificada",
    "ERROR_anterior_a_licao": "nao_classificada",
}

_CATALOGO_VIVO: dict = {}


def sha_desta_bancada() -> str:
    """O HEAD commitado desta bancada, que e a base que a suite mede."""
    fim = subprocess.run(
        ["git", "rev-parse", "--verify", "HEAD^{commit}"], cwd=RAIZ,
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )
    return fim.stdout.strip()


def git_desta_bancada(args: list[str]) -> tuple[int, str]:
    """A costura de git real da suite: le o banco de objetos, nunca a arvore."""
    fim = subprocess.run(
        ["git", *args], cwd=RAIZ, capture_output=True, text=True,
        encoding="utf-8", errors="replace",
    )
    return fim.returncode, (fim.stdout or "") + (fim.stderr or "")


def catalogo_vivo() -> dict:
    """O catálogo lido do frontmatter VIVO, uma vez por execução da suíte.

    Ele é fixture de propósito: se alguém trocar `guarda.tipo` da 088 de
    `teste` para `sino`, a 088 deixa de ser interceptada e este arquivo fica
    vermelho — que é o alarme certo, porque o desfecho teria mudado de fato.
    """
    if not _CATALOGO_VIVO:
        _CATALOGO_VIVO.update(termometro.catalogo_das_armadilhas(
            RAIZ, git=git_desta_bancada, ref="HEAD",
        ))
    return _CATALOGO_VIVO


def fato_da_janela(janela: Janela, **extras):
    """Uma janela real do corpus vira fato bruto, sem inventar nada.

    O `sinais` entra como a saída de um detector CORRETO — a armadilha do
    gabarito —, e não como a saída defeituosa de hoje: consertar o detector é
    a Fase 1, e medir o defeito dela aqui mediria a fase errada. A exceção é a
    janela ambígua, onde os dois sinais concorrentes são o fato medido e a
    ambiguidade é justamente o que a Fase 3 tem de recusar (INV-R03).
    """
    dados = dict(
        fonte="actions",
        workflow=WORKFLOW_MEDIDO,
        run=janela.abre_run,
        job=janela.abre_job,
        celula=janela.celula,
        tentativa=janela.abre_attempt,
        conclusao=CONCLUSOES_QUE_ABREM_JANELA[0],
        inicio=janela.inicio,
        fim=janela.fim,
        fechada_por=janela.fecha_run,
        evidencia=janela.evidencia_do_rotulo,
        causa=janela.causa,
        sinais=(
            tuple(janela.sinais_observados_pelo_detector_atual)
            if janela.natureza == "ERROR_ambiguidade"
            else ((janela.armadilha_esperada,) if janela.armadilha_esperada else ())
        ),
    )
    dados.update(extras)
    return termometro.Fato(**dados)


def quadro_do_corpus(extra=(), **kw):
    """O quadro calculado sobre as 37 janelas reais, mais o que o teste pedir."""
    fatos = [fato_da_janela(j) for j in JANELAS] + list(extra)
    return termometro.montar_quadro(
        fatos, catalogo=catalogo_vivo(), desde=JANELA_INICIO[:10],
        ate=JANELA_FIM[:10], workflow=WORKFLOW_MEDIDO, **kw
    )


def um_quadro(fatos, **kw):
    return termometro.montar_quadro(list(fatos), catalogo=catalogo_vivo(), **kw)


# -- a) os dois eixos ------------------------------------------------------


def test_o_vocabulario_dos_dois_eixos_e_o_do_plano():
    """Palavra trocada aqui é relatório que diz outra coisa lá."""
    assert termometro.NATUREZAS == (
        "mencao", "ocorrencia_operacional", "prova", "nao_classificada"
    )
    assert termometro.ATUACOES == (
        "sem_guarda", "interceptada", "mitigada", "escape", "desconhecida"
    )
    assert set(termometro.PROMOCAO_POR_ATUACAO) == set(termometro.ATUACOES)


def test_a_guarda_de_cada_armadilha_sai_do_frontmatter_vivo():
    """A casa da guarda declarada é o arquivo rastreado (INV-R05).

    `armadilhas/GUARDAS.json` é derivado e está no .gitignore: usá-lo como
    fonte de decisão seria medir uma cópia.
    """
    catalogo = catalogo_vivo()
    assert catalogo["088"]["guarda"] == "teste"
    # `dono` e o TESTE e `detector` e o nome dele la dentro, que e a convencao
    # das outras 440 entradas. O arquivo protegido nao mora aqui: ele se
    # declara no marcador `# guarda:` de dentro do teste, e apontar o protegido
    # em `dono` deixava a prova de mutacao impossivel de rodar (medido em
    # 18/09/2026 na propria 088).
    assert catalogo["088"]["dono"] == "ci/tests/test_chaves_do_gateway_no_deploy.py"
    assert catalogo["088"]["detector"] == (
        "test_celula_sem_servico_continua_dizendo_exatamente_isso"
    )
    assert catalogo["127"]["guarda"] == "vacina"
    assert catalogo["127"]["dono"] == "ci/rerun_de_deploy.py"
    assert catalogo["088"]["guarda"] in termometro.GUARDAS_QUE_BLOQUEIAM
    assert catalogo["127"]["guarda"] in termometro.GUARDAS_QUE_RECUPERAM


def test_as_37_janelas_reais_saem_com_o_PAR_do_gabarito():
    """O teste grande: natureza E desfecho, para todas as 37 janelas reais.

    Ele existe em vez de 37 asserções soltas porque o defeito que a Fase 3
    tem de impedir é exatamente o de classificar certo "no caso que o autor
    lembrou". Aqui não há caso escolhido: é o registro inteiro, com as duas
    formas de ERROR mapeadas para `nao_classificada` e nada mais.
    """
    quadro = quadro_do_corpus()
    calculados = quadro["classificados"]
    assert len(calculados) == len(JANELAS), (
        "cada janela real é uma ocorrência independente; sobrar ou faltar "
        "linha aqui é deduplicação comendo fato que não era duplicata"
    )
    divergentes = [
        (j.celula, j.abre_run, (NATUREZA_DA_FASE_3[j.natureza], j.desfecho),
         (f["natureza"], f["atuacao"]))
        for j, f in zip(JANELAS, calculados)
        if (NATUREZA_DA_FASE_3[j.natureza], j.desfecho) != (f["natureza"], f["atuacao"])
    ]
    assert not divergentes, divergentes


def test_a_088_e_ocorrencia_E_interceptada_ao_mesmo_tempo():
    """INV-R11 e INV-R12 no caso de aceitação.

    A muralha impediu o `up -d` sem argumento — o pior dano não aconteceu — e
    a célula ficou sem publicação do mesmo jeito. Os dois eixos dizem coisas
    diferentes sobre o MESMO fato, e é por isso que são dois.
    """
    quadro = quadro_do_corpus()
    oito = [f for f in quadro["classificados"] if f["armadilha"] == "088"]
    assert len(oito) == len(janelas_que_reincidem("088")) == 7, (
        "a oitava janela da 088 e a queda que escreveu a licao, e ela nao "
        "reincide nela mesma (item 3 da secao 18)"
    )
    for fato in oito:
        assert fato["natureza"] == "ocorrencia_operacional"
        assert fato["atuacao"] == "interceptada"
        assert fato["causa"] == CAUSA_088
    campea = termometro.campea(quadro)
    assert campea["chave"] == "armadilhas/088"
    assert campea["interceptadas"] == len(janelas_que_reincidem("088"))
    assert campea["minutos_ate_cobertura"] > 0, (
        "interceptação com custo continua no ranking: guarda que funciona não "
        "apaga o tempo em que a célula não publicou (INV-R12)"
    )


def test_a_127_separa_mitigada_de_escape():
    """A mesma janela real, com e sem o verde que a cobriu.

    A vacina RECUPERA; ela não impede a causa. Quando o verde que cobre a
    célula existe, a atuação medida é `mitigada`. Quando não existe — ou
    quando quem cobriu foi uma reversão —, a guarda aplicável estava lá e o
    dano atravessou: `escape`, que pede consertar alcance, não criar uma
    segunda guarda.
    """
    quadro = quadro_do_corpus()
    mitigadas = [f for f in quadro["classificados"] if f["armadilha"] == "127"]
    assert len(mitigadas) == len(janelas_que_reincidem("127")) == 23
    assert {f["atuacao"] for f in mitigadas} == {"mitigada"}

    real = janelas_que_reincidem("127")[0]
    sem_verde = um_quadro([fato_da_janela(
        real, fim=None, fechada_por=None,
    )])["classificados"][0]
    assert sem_verde["natureza"] == "ocorrencia_operacional"
    assert sem_verde["atuacao"] == "escape"
    assert sem_verde["janela"]["aberta"] is True

    revertida = um_quadro([fato_da_janela(
        real, intervencao="rollback-celula",
    )])["classificados"][0]
    assert revertida["atuacao"] == "escape"
    assert revertida["janela"]["aberta"] is True, (
        "reverter não é publicar: o run de rollback não pode fechar a janela"
    )


def test_a_195_e_prova_e_nunca_ocorrencia_nem_entra_no_ranking():
    """37 citações em origin/main, zero janelas — e zero linhas no ranking.

    Contar menção como reincidência foi o erro que este laço existe para
    desfazer, e a 195 é a prova viva dele: o texto que ela cita é uma PROVA de
    mutação, não uma queda.
    """
    citacoes = [
        termometro.Fato(
            fonte="registro", artefato="registro", armadilha="195",
            tarefa=f"TAR-{400 + i}",
            evidencia=LOG_195_CITACAO_COMO_PROVA,
        )
        for i in range(37)
    ]
    quadro = quadro_do_corpus(extra=citacoes)
    assert quadro["provas"] == 37
    assert quadro["ocorrencias"] == len(
        janelas_com_natureza("ocorrencia_operacional")
    ), (
        "as ocorrências continuam sendo as do registro real: prova não cria "
        "queda nenhuma"
    )
    for fato in quadro["classificados"]:
        if fato["armadilha_citada"] == "195":
            assert fato["natureza"] == "prova"
            assert fato["natureza"] != "ocorrencia_operacional"
    assert "armadilhas/195" not in {c["chave"] for c in quadro["ranking"]}
    fora = {c["chave"]: c for c in quadro["fora_do_ranking"]}
    assert fora["armadilhas/195"]["provas"] == 37
    assert fora["armadilhas/195"]["ocorrencias_operacionais_confirmadas"] == 0
    assert "195" not in {j.armadilha_esperada for j in JANELAS}


def test_citacao_sem_queda_e_mencao_e_nao_aumenta_reincidencia():
    """INV-R02, medido: 20 citações da 088 não movem um minuto sequer."""
    so_quedas = um_quadro(fato_da_janela(j) for j in janelas_que_reincidem("088"))
    citacoes = [
        termometro.Fato(
            fonte="registro", artefato="registro", armadilha="088",
            tarefa=f"TAR-{500 + i}",
            evidencia=f"https://github.com/abundanciabr/sitesdoreino/pull/{i}",
        )
        for i in range(20)
    ]
    com_citacoes = um_quadro(
        [fato_da_janela(j) for j in janelas_que_reincidem("088")] + citacoes
    )
    antes, depois = so_quedas["ranking"][0], com_citacoes["ranking"][0]
    assert depois["mencoes"] == 20
    assert com_citacoes["mencoes"] == 20
    quantas = len(janelas_que_reincidem("088"))
    assert antes["ocorrencias_operacionais_confirmadas"] == quantas
    assert depois["ocorrencias_operacionais_confirmadas"] == quantas, (
        "citar uma armadilha 20 vezes não a faz morder 20 vezes: reincidência "
        "só cresce com queda terminal medida (INV-R02)"
    )
    assert depois["minutos_ate_cobertura"] == antes["minutos_ate_cobertura"]
    assert depois["runs_afetados"] == antes["runs_afetados"]
    assert all(
        f["natureza"] == "mencao"
        for f in com_citacoes["classificados"] if f["celula"] is None
    )


# -- b) deduplicação -------------------------------------------------------


def test_a_ordem_da_deduplicacao_e_a_do_plano():
    """A ordem é contrato, não detalhe de implementação."""
    assert termometro.ORDEM_DA_DEDUPLICACAO == (
        "workflow+run+job+celula+tentativa",
        "url_do_run",
        "pr+celula+conclusao",
        "tarefa+evidencia",
        "sem_identidade_suficiente",
    )
    quadro = quadro_do_corpus()
    assert quadro["ordem_da_deduplicacao"] == list(
        termometro.ORDEM_DA_DEDUPLICACAO
    ), "o JSON publica a mesma ordem que o código usa"


def test_duas_citacoes_do_mesmo_run_contam_UMA_ocorrencia():
    """Registro e evento do mesmo run só sabem dizer a URL — e a URL é uma."""
    real = janelas_que_reincidem("127")[0]
    url = (
        "https://github.com/abundanciabr/sitesdoreino/actions/runs/"
        f"{real.abre_run}"
    )
    quadro = um_quadro([
        termometro.Fato(fonte="registro", artefato="registro", armadilha="127",
                        url_do_run=url, evidencia="o registro do painel"),
        termometro.Fato(fonte="evento", artefato="evento", armadilha="127",
                        url_do_run=url, evidencia="o disparo do caderninho"),
    ])
    assert len(quadro["classificados"]) == 1
    assert len(quadro["descartes"]) == 1
    assert quadro["descartes"][0]["por"] == "url_do_run"
    assert quadro["mencoes"] == 1


def test_evento_e_registro_do_mesmo_run_nao_dobram_a_queda():
    """O caso de regressão nomeado no plano.

    A queda medida sabe workflow, run, job, célula e tentativa; o registro e o
    evento só sabem a URL. Se os três contassem, a mesma queda valeria três —
    e o ranking premiaria quem relata melhor.
    """
    real = janelas_que_reincidem("088")[0]
    url = (
        "https://github.com/abundanciabr/sitesdoreino/actions/runs/"
        f"{real.abre_run}"
    )
    quadro = um_quadro([
        fato_da_janela(real),
        termometro.Fato(fonte="registro", artefato="registro", armadilha="088",
                        url_do_run=url, tarefa="TAR-600",
                        evidencia="https://github.com/a/b/pull/7"),
        termometro.Fato(fonte="evento", artefato="evento", armadilha="088",
                        url_do_run=url, evidencia="disparo da muralha"),
    ])
    assert quadro["ocorrencias"] == 1
    assert len(quadro["descartes"]) == 2
    campea = termometro.campea(quadro)
    assert campea["ocorrencias_operacionais_confirmadas"] == 1
    assert campea["registros_produzidos"] == 1
    assert campea["eventos_produzidos"] == 1
    assert campea["artefatos"] == 2, (
        "o registro e o evento continuam contando como ARTEFATO produzido — o "
        "que eles não podem é virar uma segunda queda"
    )


def test_a_citacao_que_chega_ANTES_da_queda_nao_cria_segunda_ocorrencia():
    """O caso feio da ordem de leitura.

    Se a varredura fosse na ordem de chegada, a citação criaria o grupo pela
    URL e a queda medida — que sabe run, job e célula — entraria como SEGUNDA
    ocorrência do mesmo run. A deduplicação varre do mais específico para o
    menos justamente por isso.
    """
    real = janelas_que_reincidem("127")[0]
    url = (
        "https://github.com/abundanciabr/sitesdoreino/actions/runs/"
        f"{real.abre_run}"
    )
    citacao = termometro.Fato(
        fonte="registro", artefato="registro", armadilha="127",
        url_do_run=url, evidencia="citado antes de a coleta rodar",
    )
    primeiro = um_quadro([citacao, fato_da_janela(real)])
    depois = um_quadro([fato_da_janela(real), citacao])
    assert primeiro["ocorrencias"] == depois["ocorrencias"] == 1
    assert len(primeiro["descartes"]) == len(depois["descartes"]) == 1
    assert primeiro["ranking"][0]["registros_produzidos"] == 1
    assert [c["chave"] for c in primeiro["ranking"]] == (
        [c["chave"] for c in depois["ranking"]]
    )


def test_jobs_distintos_do_mesmo_run_contam_separado():
    """Duas células caídas no mesmo run são duas indisponibilidades."""
    real = janelas_que_reincidem("127")[0]
    outra = fato_da_janela(real)._replace(
        job=real.abre_job + 1, celula="uma-outra-celula",
    )
    quadro = um_quadro([fato_da_janela(real), outra])
    assert quadro["ocorrencias"] == 2
    assert quadro["descartes"] == []


def test_rerun_usa_a_tentativa_e_o_fato_repetido_nao():
    """A tentativa faz parte da identidade; o fato idêntico repetido, não.

    O rerun mantém o `run_id` e muda a tentativa: contar uma só esconderia a
    segunda queda. Já o MESMO fato lido duas vezes (duas fatias de data que se
    encostam, por exemplo) é uma ocorrência e não duas.
    """
    real = janelas_que_reincidem("127")[0]
    primeira = fato_da_janela(real)
    segunda = primeira._replace(tentativa=(real.abre_attempt or 1) + 1)
    assert um_quadro([primeira, segunda])["ocorrencias"] == 2
    assert um_quadro([primeira, primeira])["ocorrencias"] == 1
    assert um_quadro([primeira, primeira])["descartes"][0]["por"] == (
        "workflow+run+job+celula+tentativa"
    )


def test_fato_sem_identidade_suficiente_nao_e_classificavel():
    """Passo 5 da ordem: sem identidade, não se acusa nem se conta."""
    orfao = termometro.Fato(
        fonte="registro", armadilha="088", evidencia="um texto solto",
    )
    quadro = um_quadro([orfao])
    assert quadro["ocorrencias"] == 0
    assert quadro["ranking"] == []
    assert len(quadro["nao_classificadas"]) == 1
    assert quadro["nao_classificadas"][0]["identidade"] == (
        "sem_identidade_suficiente"
    )
    assert "identidade suficiente" in quadro["nao_classificadas"][0]["motivo"]


# -- c) custo, sem peso inventado ------------------------------------------


def test_deploy_verde_sem_cobertura_da_celula_NAO_encerra_a_janela():
    """Verde de outra célula não publica a que caiu (INV-R07).

    A lista de coberturas aqui é a de um dia real de merges: três verdes
    depois da queda, e só um deles tocou a célula que estava fora do ar.
    """
    real = janelas_que_reincidem("127")[0]
    so_outras = fato_da_janela(real, fim=None, fechada_por=None, coberturas=(
        {"quando": "2026-08-19T11:00:00Z", "celulas": ("pagamentos",),
         "run": 1, "workflow": WORKFLOW_MEDIDO},
        {"quando": "2026-08-19T11:30:00Z", "celulas": ("alunos", "forum"),
         "run": 2, "workflow": WORKFLOW_MEDIDO},
    ))
    fato = um_quadro([so_outras])["classificados"][0]
    assert fato["janela"]["aberta"] is True
    assert fato["janela"]["fim"] is None
    assert fato["janela"]["segundos"] is None


def test_o_PRIMEIRO_verde_que_cobre_a_celula_encerra_a_janela():
    """E o rollback no meio do caminho não conta como o primeiro."""
    real = janelas_que_reincidem("127")[0]
    com_coberturas = fato_da_janela(real, fim=None, fechada_por=None, coberturas=(
        {"quando": apos(real.inicio, 1), "celulas": ("pagamentos",),
         "run": 1, "workflow": WORKFLOW_MEDIDO},
        {"quando": apos(real.inicio, 2), "celulas": (real.celula,),
         "run": 2, "workflow": "rollback-celula"},
        {"quando": apos(real.inicio, 3), "celulas": (real.celula,),
         "run": 3, "workflow": WORKFLOW_MEDIDO},
        {"quando": apos(real.inicio, 4), "celulas": (real.celula,),
         "run": 4, "workflow": WORKFLOW_MEDIDO},
    ))
    janela = um_quadro([com_coberturas])["classificados"][0]["janela"]
    assert janela["fim"] == apos(real.inicio, 3)
    assert janela["run_de_fechamento"] == 3
    assert janela["aberta"] is False
    assert janela["segundos"] == termometro.segundos_entre(
        real.inicio, apos(real.inicio, 3)
    )


def test_run_de_rollback_nao_e_resolucao():
    """Reverter devolve a plataforma; não publica o que caiu."""
    real = janelas_que_reincidem("127")[0]
    revertida = um_quadro([
        fato_da_janela(real, intervencao="rollback-celula")
    ])["classificados"][0]
    assert revertida["janela"]["aberta"] is True
    assert revertida["janela"]["fim"] is None
    assert revertida["janela"]["intervencao"] == "rollback-celula"
    assert "reverter não é publicar" in revertida["janela"]["motivo"]
    quadro = um_quadro([fato_da_janela(real, intervencao="rollback-celula")])
    assert quadro["sem_tempo_comparavel"][0]["intervencoes_detectadas"] == 1
    assert quadro["ranking"] == [], (
        "sem tempo comprovado a candidata sai SEPARADA, e não com minuto "
        "emprestado da intervenção"
    )
    for nome in ("rollback", "reversao", "volta-atras"):
        assert termometro.e_intervencao(f"deploy-{nome}-celula") is True
    assert termometro.e_intervencao(WORKFLOW_MEDIDO) is False


def test_janela_sem_resolucao_permanece_aberta_e_a_consulta_nao_a_fecha():
    """A única janela aberta do corpus continua aberta, e o `--ate` não mente.

    Mover o fim da consulta para 2099 não pode inventar minuto nenhum: o fim
    da janela de consulta não é resolução, é só até onde a pergunta foi.
    """
    aberta = [j for j in JANELAS if j.fim is None]
    assert len(aberta) == 1
    curto = um_quadro([fato_da_janela(aberta[0])], ate="2026-09-18")
    longo = um_quadro([fato_da_janela(aberta[0])], ate="2099-01-01")
    for quadro in (curto, longo):
        assert quadro["ranking"] == []
        candidata = quadro["sem_tempo_comparavel"][0]
        assert candidata["minutos_ate_cobertura"] is None
        assert candidata["janelas_abertas"] == 1
        assert candidata["tempo_comparavel"] is False
        assert "não é inventado" in candidata["motivo"] or (
            "minuto nenhum é inventado" in candidata["motivo"]
        )
    assert curto["sem_tempo_comparavel"] == longo["sem_tempo_comparavel"]


def test_o_custo_bate_com_o_corpus_congelado_minuto_a_minuto():
    """Os totais saem do registro da Fase 0, não de número digitado aqui.

    O arredondamento acontece UMA vez, sobre a soma dos segundos — arredondar
    janela por janela daria outro número, e o outro número não fecha com
    `celula_minutos_esperados`.
    """
    quadro = quadro_do_corpus()
    por_chave = {c["chave"]: c for c in quadro["ranking"]}
    assert por_chave["armadilhas/088"]["minutos_ate_cobertura"] == (
        celula_minutos_esperados(janelas_que_reincidem("088"))
    )
    assert por_chave["armadilhas/127"]["minutos_ate_cobertura"] == (
        celula_minutos_esperados(janelas_que_reincidem("127"))
    )
    gateway = por_chave[f"causa/{CAUSA_GATEWAY}"]
    assert gateway["minutos_ate_cobertura"] == (
        celula_minutos_esperados(janelas_com_causa(CAUSA_GATEWAY))
    )
    assert gateway["janelas_abertas"] == 1, (
        "a janela do gateway que nunca fechou continua aberta e fora da soma"
    )
    assert gateway["armadilha"] is None, (
        "nenhuma armadilha do catálogo cobre esta causa hoje, e a Fase 3 não "
        "inventa número para ela"
    )


def codigo_sem_docstring(fonte: str) -> str:
    """O CÓDIGO do módulo, sem docstring nem comentário.

    A proibição de peso vale para o que calcula, não para o texto que explica
    a proibição. Mas ela precisa enxergar STRING: um peso inventado costuma
    morar exatamente numa chave de dicionário, `{"alto": 10}`, e um exame que
    jogasse fora todo literal de texto não veria nenhum deles.
    """
    arvore = ast.parse(fonte)
    for no in ast.walk(arvore):
        corpo = getattr(no, "body", None)
        if not isinstance(
            no, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ) or not corpo:
            continue
        primeiro = corpo[0]
        if (
            isinstance(primeiro, ast.Expr)
            and isinstance(getattr(primeiro, "value", None), ast.Constant)
            and isinstance(primeiro.value.value, str)
        ):
            corpo.pop(0)
    return ast.unparse(arvore)


def test_nao_existe_peso_inventado_no_modulo():
    """`alto = 10, medio = 5, baixo = 1` é proibido pelo plano.

    Custo se mede em tempo medido entre dois carimbos reais. Multiplicar
    registro por gravidade declarada devolveria o ranking a quem escreve
    melhor a ficha da armadilha, que é o defeito que este laço desfaz.
    """
    limpo = codigo_sem_docstring((CI / "termometro.py").read_text(encoding="utf-8"))
    for palavra in ("alto", "medio", "médio", "baixo", "custo_por_queda"):
        assert palavra not in limpo, (
            f"{palavra!r} no código do termômetro: custo se mede em tempo "
            "medido, nunca em peso arbitrário por gravidade declarada"
        )
    # O exame precisa mesmo pegar o peso escondido numa chave de dicionário.
    with pytest.raises(AssertionError):
        sujo = codigo_sem_docstring(
            'PESOS = {"alto": 10, "medio": 5, "baixo": 1}'
        )
        assert "alto" not in sujo


def test_as_dimensoes_do_plano_estao_todas_em_cada_candidata():
    """Dimensão que some do JSON é linha que some do relatório sem aviso."""
    assert termometro.DIMENSOES == (
        "ocorrencias_operacionais_confirmadas", "interceptadas", "mitigadas",
        "escapes", "runs_afetados", "jobs_afetados", "celulas_afetadas",
        "minutos_ate_cobertura", "registros_produzidos", "eventos_produzidos",
        "intervencoes_detectadas",
    )
    quadro = quadro_do_corpus()
    prateleiras = (
        quadro["ranking"] + quadro["sem_tempo_comparavel"]
        + quadro["fora_do_ranking"]
    )
    assert prateleiras
    for candidata in prateleiras:
        faltando = [d for d in termometro.DIMENSOES if d not in candidata]
        assert not faltando, (candidata["chave"], faltando)


# -- d) ranking, campeã e promoção -----------------------------------------


def test_o_ranking_ordena_por_tempo_comprovado_e_a_088_vence():
    """O portão da Fase 3, medido sobre o registro real.

    A 088 vence, a 127 fica em segundo e a causa do gateway em terceiro. Os
    números não estão digitados aqui: saem do corpus, e uma janela mexida lá
    move a ordem daqui.
    """
    quadro = quadro_do_corpus()
    assert [c["chave"] for c in quadro["ranking"]] == ranking_esperado_do_corpus()
    tempos = [c["minutos_ate_cobertura"] for c in quadro["ranking"]]
    assert tempos == sorted(tempos, reverse=True)
    assert quadro["campea"] == "armadilhas/088"
    assert tempos[0] > 5 * tempos[1], (
        "a 088 vence por folga mesmo sem as duas janelas do gateway, e é por "
        "isso que ela é a fatia vertical desta entrega"
    )
    assert [c["posicao"] for c in quadro["ranking"]] == [1, 2, 3]


def test_a_ordem_nao_depende_da_ordem_de_entrada():
    """Desempate estável: embaralhar a entrada não move o relatório."""
    fatos = [fato_da_janela(j) for j in JANELAS]
    direto = termometro.montar_quadro(fatos, catalogo=catalogo_vivo())
    embaralhado = list(fatos)
    random.Random(1708).shuffle(embaralhado)
    trocado = termometro.montar_quadro(embaralhado, catalogo=catalogo_vivo())
    assert [c["chave"] for c in direto["ranking"]] == (
        [c["chave"] for c in trocado["ranking"]]
    )
    assert direto["campea"] == trocado["campea"]
    assert [c["minutos_ate_cobertura"] for c in direto["ranking"]] == (
        [c["minutos_ate_cobertura"] for c in trocado["ranking"]]
    )


def test_o_desempate_final_e_o_numero_da_armadilha():
    """Empate em tempo, ocorrências e artefatos: decide o menor número.

    Aqui as candidatas são montadas à mão de propósito — o empate perfeito não
    existe no registro real, e o que está sob teste é a regra de desempate,
    não os dados.
    """
    empatadas = [
        {"chave": "armadilhas/300", "armadilha": "300",
         "minutos_ate_cobertura": 10, "tempo_comparavel": True,
         "ocorrencias_operacionais_confirmadas": 2, "artefatos": 1},
        {"chave": "armadilhas/127", "armadilha": "127",
         "minutos_ate_cobertura": 10, "tempo_comparavel": True,
         "ocorrencias_operacionais_confirmadas": 2, "artefatos": 1},
        {"chave": f"causa/{CAUSA_GATEWAY}", "armadilha": None,
         "minutos_ate_cobertura": 10, "tempo_comparavel": True,
         "ocorrencias_operacionais_confirmadas": 2, "artefatos": 1},
    ]
    ordenadas = [c["chave"] for c in termometro.ordenar(empatadas)["ranking"]]
    assert ordenadas == [
        "armadilhas/127", "armadilhas/300", f"causa/{CAUSA_GATEWAY}",
    ], "numeradas por número, e a candidata sem número depois, sem ganhar um"


def test_candidata_sem_tempo_comparavel_sai_SEPARADA_e_sem_minutos():
    """Sem janela fechada não há tempo comprovado — e não há minuto emprestado."""
    aberta = [j for j in JANELAS if j.fim is None][0]
    quadro = um_quadro([fato_da_janela(aberta)])
    assert quadro["ranking"] == []
    assert quadro["campea"] is None
    assert quadro["promocao"] is None, (
        "sem candidata com tempo comprovado não há campeã, e sem campeã não "
        "há promoção: relatório que promove no escuro é o que se quer evitar"
    )
    separada = quadro["sem_tempo_comparavel"][0]
    assert separada["minutos_ate_cobertura"] is None
    assert separada["ocorrencias_operacionais_confirmadas"] == 1


def test_uma_execucao_promove_no_maximo_UMA_campea():
    """Três candidatas no ranking, uma promoção — e ela é a primeira."""
    quadro = quadro_do_corpus()
    assert len(quadro["ranking"]) == 3
    eleitas = [c for c in quadro["ranking"] if c["chave"] == quadro["campea"]]
    assert len(eleitas) == 1
    promocao = quadro["promocao"]
    assert isinstance(promocao, dict), (
        "promoção é uma, não uma lista: a fila da Fase 5 não pode receber duas "
        "campeãs da mesma execução"
    )
    assert promocao["chave"] == quadro["campea"] == eleitas[0]["chave"]
    assert promocao["origem"] == "ci/termometro.py:armadilhas/088", (
        "a identidade idempotente do INV-R06 sai daqui pronta para a fila"
    )
    assert termometro.promocao_da_campea(quadro) == promocao, (
        "chamar de novo não elege uma segunda"
    )


def test_a_interceptada_cara_nao_manda_criar_guarda():
    """INV-R11 e INV-R12: a guarda funcionou; criar outra seria trabalho falso.

    O que a promoção pede é impedir a causa mais cedo e PRESERVAR a guarda que
    interceptou — nunca uma segunda muralha em cima da primeira.
    """
    promocao = quadro_do_corpus()["promocao"]
    assert promocao["atuacao"] == "interceptada"
    assert promocao["acao"] == "prevenir a causa mais cedo e preservar a guarda"
    assert promocao["nao_criar_guarda"] is True
    assert promocao["acao"] != termometro.PROMOCAO_POR_ATUACAO["sem_guarda"]


def test_a_promocao_de_causa_sem_armadilha_nao_inventa_numero():
    """A causa do gateway não tem armadilha: quem dá número é o almoxarife."""
    gateway = [fato_da_janela(j) for j in janelas_com_causa(CAUSA_GATEWAY)]
    quadro = um_quadro(gateway)
    promocao = quadro["promocao"]
    assert promocao["chave"] == f"causa/{CAUSA_GATEWAY}"
    assert promocao["armadilha"] is None
    assert promocao["origem"] is None
    assert promocao["precisa_de_numero"] is True
    assert promocao["acao"] == termometro.PROMOCAO_POR_ATUACAO["sem_guarda"]


# -- e) um só objeto para o humano e para o `--json` ------------------------


def test_o_relatorio_humano_e_o_JSON_saem_do_MESMO_objeto():
    """Mexer num campo do JSON move a tabela junto. O teste mexe.

    Não existe segundo caminho de serialização: o que o `--json` imprime é o
    próprio quadro, e a tabela humana é leitura dele. Um renderizador que
    recalculasse qualquer número poderia continuar mostrando a história antiga
    depois de o JSON mudar — e é esse o falso verde que este teste impede.
    """
    quadro = quadro_do_corpus()
    assert json.loads(json.dumps(quadro, ensure_ascii=False)) == quadro, (
        "o quadro tem de ser dado puro de JSON: objeto escondido lá dentro é "
        "um segundo caminho por onde texto e JSON podem divergir"
    )
    esperado = celula_minutos_esperados(janelas_que_reincidem("088"))
    antes = termometro.linhas_do_quadro(quadro)
    assert any(f"{esperado} célula-minutos" in linha for linha in antes)

    quadro["ranking"][0]["minutos_ate_cobertura"] = 7
    quadro["ranking"][0]["ocorrencias_operacionais_confirmadas"] = 99
    quadro["promocao"]["acao"] = "uma ação que ninguém escreveu no código"
    depois = termometro.linhas_do_quadro(quadro)
    assert any("7 célula-minutos" in linha for linha in depois)
    assert any("99 ocorrência(s)" in linha for linha in depois)
    assert any(
        "uma ação que ninguém escreveu no código" in linha for linha in depois
    )
    assert not any(f"{esperado} célula-minutos" in linha for linha in depois)
    assert termometro.campea(quadro)["minutos_ate_cobertura"] == 7, (
        "a campeã é resolvida no ranking pela chave; se fosse cópia, o JSON "
        "teria dois lugares para o mesmo número e um deles ficaria velho"
    )


def test_a_tabela_humana_le_um_quadro_e_nao_o_mundo():
    """A tabela funciona sobre um dicionário montado à mão.

    Se ela precisasse de estado escondido, de rede ou de arquivo, o `--json` e
    o texto teriam fontes diferentes — e a Fase 3 existe para eles terem uma
    só.
    """
    linhas = termometro.linhas_do_quadro({
        "janela": {"desde": "2026-08-18", "ate": "2026-09-18",
                   "workflow": WORKFLOW_MEDIDO},
        "fatos": 1, "ocorrencias": 1, "mencoes": 0, "provas": 0,
        "ranking": [{
            "posicao": 1, "chave": "armadilhas/999",
            "minutos_ate_cobertura": 42,
            "ocorrencias_operacionais_confirmadas": 1,
            "atuacao": "escape", "celulas_afetadas": 1, "artefatos": 0,
            "janelas_abertas": 0, "intervencoes_detectadas": 0,
        }],
        "campea": "armadilhas/999", "promocao": None,
        "sem_tempo_comparavel": [], "fora_do_ranking": [],
        "nao_classificadas": [], "descartes": [], "medicao": None,
    })
    texto = "\n".join(linhas)
    assert "armadilhas/999" in texto and "42 célula-minutos" in texto
    assert "CAMPEÃ" in texto


# -- f) ERROR continua visível ---------------------------------------------


def test_as_janelas_nao_classificadas_ficam_SEPARADAS_e_visiveis():
    """ERROR não é ausência de problema (INV-R08): sai do ranking, não do
    relatório.

    São a ambígua, que casou dois sinais (INV-R03), as duas que não casaram
    sinal nenhum (as mesmas do relatório-plano) e as duas quedas que ESCREVERAM
    a lição que as explica, que não reincidem nela (item 3 da seção 18).
    """
    quadro = quadro_do_corpus()
    assert len(quadro["nao_classificadas"]) == sum(
        len(janelas_com_natureza(n)) for n in NATUREZA_DA_FASE_3
        if n != "ocorrencia_operacional"
    ) == 5
    nasceram_depois = [
        n["motivo"] for n in quadro["nao_classificadas"] if "nasceu em" in n["motivo"]
    ]
    assert len(nasceram_depois) == len(
        janelas_com_natureza("ERROR_anterior_a_licao")
    ) == 2
    motivos = [n["motivo"] for n in quadro["nao_classificadas"]]
    ambiguas = [m for m in motivos if "INV-R03" in m]
    sem_casamento = [m for m in motivos if "INV-R08" in m]
    assert len(ambiguas) == len(janelas_com_natureza("ERROR_ambiguidade")) == 1
    assert len(sem_casamento) == 2 == (
        TABELA_DO_RELATORIO["janelas_nao_classificadas"]
    )
    chaves = {c["chave"] for c in quadro["ranking"]}
    for nao_classificada in quadro["nao_classificadas"]:
        assert nao_classificada["chave"] not in chaves
    texto = "\n".join(termometro.linhas_do_quadro(quadro))
    assert "ERROR" in texto
    assert "ausência de problema" in texto


def test_a_licao_escrita_NA_BANCADA_nao_entra_no_universo_medido():
    """INV-R01: a base e um ref do git, e a arvore de trabalho fica de fora.

    Enquanto o catalogo saia da pasta, bastava escrever um arquivo aqui para
    criar uma armadilha, mudar a classificacao de um run e, com ela, a campea
    que vira tarefa. O arquivo abaixo existe no disco e nao existe no `ref`.
    """
    intrusa = RAIZ / "armadilhas" / "999-licao-que-so-existe-nesta-bancada.md"
    assert not intrusa.exists(), "deixe a bancada limpa antes de rodar a suite"
    intrusa.write_text(
        """---
schema_version: 2
armadilha: 999
estado: observada
degrau: 1
confianca: baixa
guarda:
  tipo: nenhum
  motivo: entrada de teste, nao commitada
---

# Licao que so existe nesta bancada
""",
        encoding="utf-8",
    )
    try:
        catalogo = termometro.catalogo_das_armadilhas(
            RAIZ, git=git_desta_bancada, ref="HEAD",
        )
    finally:
        intrusa.unlink()
    assert "999" not in catalogo, (
        "a arvore local nao participa do universo: quem decide o catalogo e o "
        "SHA medido (INV-R01)"
    )
    assert catalogo == catalogo_vivo()


def test_o_quadro_PUBLICA_a_base_e_o_sha_que_mediu():
    """Medicao sem base publicada nao se repete, e o que nao se repete nao se
    audita."""
    quadro = quadro_do_corpus(base="origin/main", sha="f" * 40)
    assert quadro["janela"]["base"] == "origin/main"
    assert quadro["janela"]["sha"] == "f" * 40
    assert "base" in termometro.montar_quadro([])["janela"]
    assert f"Base: origin/main em {'f' * 40}." in termometro.linhas_do_quadro(quadro)
    assert termometro.BASE_DA_MEDICAO == indice.REF_DA_VERDADE, (
        "duas bases diferentes para a mesma pergunta divergem no primeiro dia "
        "em que alguem mexer numa so"
    )


def test_o_nascimento_das_licoes_custa_UMA_pergunta_ao_git():
    """Uma pergunta por licao eram 444 processos antes do primeiro log.

    O lote tem de dar exatamente a mesma resposta que a pergunta avulsa, e a
    conferencia e feita contra o `git log` de uma entrada de verdade.
    """
    perguntas: list = []

    def contando(args):
        perguntas.append(tuple(args))
        return git_desta_bancada(args)

    nascimentos = termometro._nascimento_das_licoes(contando, "HEAD")
    assert len(perguntas) == 1, perguntas
    assert len(nascimentos) >= 400
    nome = "armadilhas/088-celula-nova-deixa-o-deploy-celula-vermelho-ate-o.md"
    avulsa = git_desta_bancada(
        ["log", "--diff-filter=A", "--format=%cI", "-1", "HEAD", "--", nome]
    )[1].strip()
    assert nascimentos[nome] == avulsa


def test_base_que_o_git_nao_resolve_vira_ERROR_e_nao_medicao_sem_base():
    codigo, _ = git_desta_bancada(["rev-parse", "--verify", "nao-existe^{commit}"])
    assert codigo != 0
    with pytest.raises(termometro.ErroDeColeta) as erro:
        termometro._sha_da_base(git_desta_bancada, "nao-existe")
    assert "git fetch origin" in str(erro.value)


def test_log_ilegivel_vira_ERROR_e_nunca_ausencia_de_problema():
    """INV-R08 do lado da classificação: sem log não há causa medida."""
    real = janelas_que_reincidem("088")[0]
    cego = um_quadro([fato_da_janela(real, log_lido=False, sinais=())])
    assert cego["ranking"] == []
    assert cego["ocorrencias"] == 0
    assert "não pôde ser lido" in cego["nao_classificadas"][0]["motivo"]


def test_sinal_que_aponta_armadilha_fora_do_catalogo_e_ERROR():
    """Detector e catálogo discordando é medição inconsistente, não queda."""
    real = janelas_que_reincidem("127")[0]
    quadro = termometro.montar_quadro(
        [fato_da_janela(real)._replace(sinais=("999",))],
        catalogo={"127": catalogo_vivo()["127"]},
    )
    assert quadro["ocorrencias"] == 0
    assert "não está no catálogo" in quadro["nao_classificadas"][0]["motivo"]


def test_a_licao_que_nasceu_DEPOIS_do_run_nao_conta_reincidencia():
    """Ocorrência operacional exige lição existente antes do run.

    Quem caiu antes de a lição existir não reincidiu nela: contar essa queda
    inflaria a reincidência da armadilha com o passado que ela veio explicar.
    """
    real = janelas_que_reincidem("127")[0]
    catalogo = dict(catalogo_vivo())
    catalogo["127"] = dict(catalogo["127"], nascida_em="2026-12-01T00:00:00Z")
    quadro = termometro.montar_quadro([fato_da_janela(real)], catalogo=catalogo)
    assert quadro["ocorrencias"] == 0
    assert "nasceu em" in quadro["nao_classificadas"][0]["motivo"]
    catalogo["127"] = dict(catalogo["127"], nascida_em="2026-08-01T00:00:00Z")
    assert termometro.montar_quadro(
        [fato_da_janela(real)], catalogo=catalogo
    )["ocorrencias"] == 1


def test_a_coleta_da_fase_2_atravessa_para_o_quadro_sem_detector_chutado():
    """A ponte com a Fase 2, e a recusa que ela carrega.

    `fatos_da_coleta` traduz as janelas medidas em fatos; sem a saída do
    detector ela RECUSA, em vez de dizer "nenhum sinal" por não ter olhado.
    """
    real = janelas_que_reincidem("088")[0]
    medida = {
        "desde": JANELA_INICIO[:10], "ate": JANELA_FIM[:10],
        "workflow": WORKFLOW_MEDIDO,
        "janelas": [{
            "celula": real.celula, "run_de_abertura": real.abre_run,
            "job_de_abertura": real.abre_job, "tentativa": real.abre_attempt,
            "abertura": real.inicio, "fechamento": real.fim,
            "run_de_fechamento": real.fecha_run, "estado_do_log": "lido",
        }],
    }
    fatos = termometro.fatos_da_coleta(medida, sinais_do_job=lambda job: ("088",))
    quadro = termometro.montar_quadro(
        fatos, catalogo=catalogo_vivo(), medicao=medida,
    )
    assert quadro["janela"]["workflow"] == WORKFLOW_MEDIDO
    assert quadro["ranking"][0]["chave"] == "armadilhas/088"
    assert quadro["ranking"][0]["atuacao"] == "interceptada"
    assert quadro["medicao"] is medida

    with pytest.raises(termometro.ErroDeClassificacao) as erro:
        termometro.fatos_da_coleta(medida, sinais_do_job=None)
    assert "detector" in str(erro.value)

    ilegivel = json.loads(json.dumps(medida))
    ilegivel["janelas"][0]["estado_do_log"] = "ERROR"
    cego = termometro.montar_quadro(
        termometro.fatos_da_coleta(ilegivel, sinais_do_job=lambda job: None),
        catalogo=catalogo_vivo(),
    )
    assert cego["ranking"] == []
    assert len(cego["nao_classificadas"]) == 1

# ==========================================================================
# F4: o laco fecha ponta a ponta.
#
# Ate aqui a Fase 2 media a janela e a Fase 3 sabia classificar, mas ninguem
# ligava uma na outra: `fatos_da_coleta` exigia um `sinais_do_job` que nao
# existia, e o CLI imprimia a coleta crua. O vao entre as duas era o lugar
# exato onde o falso verde nasceria, porque a saida mais barata de "nao tenho
# detector" e devolver tupla vazia e chamar isso de "nenhum sinal".
#
# O que este bloco prende:
#
#   1. O TEXTO do log chega a quem classifica, e nao entra na medida que vai
#      para o `--json` (log e evidencia, nao medicao).
#   2. O detector casa o log executado da 088 e recusa o ECO do script.
#   3. Sinal que casa deploy VERDE nao vota (INV-R04).
#   4. Dois sinais chegam como DOIS ao classificador, que devolve ambiguidade
#      (INV-R03) - escolher o primeiro aqui esconderia o problema de quem tem
#      de recusa-lo.
#   5. `--json` e tabela saem do MESMO objeto, agora do CLI de verdade.
#   6. Uma execucao promove UMA campea.
#   7. Detector que nao pode ser construido RECUSA com codigo 2 e diz o que
#      fazer, em vez de medir com um instrumento que nao existe.
# ==========================================================================


def _bancada_do_laco() -> Bancada:
    """Duas quedas em miniatura, com o verde que cobre cada celula.

    Nada e inventado do nada: os dois logs sao as fixtures reais do corpus, e
    a 088 fica 120 minutos sem publicacao contra 60 da 127 - duas candidatas
    no ranking, que e o que faz a promocao unica ser prova de alguma coisa.
    """
    return Bancada(
        runs={("2026-09-01", "2026-09-04"): [
            _run(1, sha="aaa", conclusao="failure",
                 criado="2026-09-01T10:00:00Z"),
            _run(2, sha="bbb", criado="2026-09-01T12:00:00Z"),
            _run(3, sha="ccc", conclusao="failure",
                 criado="2026-09-02T10:00:00Z"),
            _run(4, sha="ddd", criado="2026-09-02T11:00:00Z"),
        ]},
        jobs={
            1: [_job(11, "deploy (encomendas)", "failure")],
            2: [_job(21, "deploy (encomendas)", "success")],
            3: [_job(31, "deploy (admin)", "failure")],
            4: [_job(41, "deploy (admin)", "success")],
        },
        logs={11: LOG_088_EXECUTADO, 31: LOG_127_SOLUCO_DE_REDE},
        ancestrais=(("aaa", "bbb"), ("ccc", "ddd")),
    )


ARGV_DO_LACO = ["--desde=2026-09-01", "--ate=2026-09-04"]


def _rodar_o_cli(monkeypatch, bancada, argv):
    """`_medir_historico` de verdade, com as quatro costuras da bancada.

    O catalogo NAO e falsificado: ele sai do frontmatter vivo de armadilhas/,
    porque e a autoridade da 088 e da 127 declarada la que decide interceptada
    e mitigada. So a rede sai de cena.
    """
    monkeypatch.chdir(RAIZ)
    monkeypatch.setattr(termometro, "_costuras_reais", lambda raiz: dict(
        api=bancada.api, baixar_log=bancada.baixar_log, git=bancada.git,
        jobs_em_lote=bancada.jobs_em_lote,
    ))
    return termometro._medir_historico(list(argv))


def test_a_coleta_entrega_o_TEXTO_do_log_a_quem_classifica():
    """Sem o texto, o detector da Fase 1 nao tem o que ler.

    E o texto fica FORA da medida: ela viaja dentro do quadro ate o `--json`,
    e log e evidencia de megabytes, nao medicao. Quem quiser a linha literal
    abre o job.
    """
    bancada = Bancada(
        runs={("2026-08-18", "2026-08-21"): [
            _run(1, sha="aaa", conclusao="failure",
                 criado="2026-08-18T10:00:00Z"),
        ]},
        jobs={1: [_job(11, "deploy (encomendas)", "failure")]},
        logs={11: LOG_088_EXECUTADO},
    )
    guardados: dict = {}
    medida = _coletar(bancada, cache_de_log=guardados)

    assert guardados == {11: LOG_088_EXECUTADO}
    assert medida["logs_lidos"] == 1
    assert set(medida) == {
        "desde", "ate", "workflow", "runs_unicos", "logs_lidos",
        "logs_indisponiveis", "celulas_cobertas", "janelas", "chamadas",
    }, (
        "a medida nao ganha campo nenhum: ela vai inteira para o `--json` "
        "dentro do quadro, e megabytes de log ali afogam a medicao"
    )

    detector = termometro.detector_dos_logs(guardados, catalogo=catalogo_vivo())
    assert detector(11) == ("088",)
    assert detector(99) is None, (
        "job sem log lido devolve None, nunca tupla vazia: 'nao olhei' e "
        "'olhei e nao achei' sao respostas diferentes (INV-R08)"
    )


def test_o_detector_sem_instrumento_RECUSA_em_vez_de_devolver_tupla_vazia():
    """Tres buracos de instrumento, e nenhum deles sai como "nenhum sinal".

    Catalogo vazio, licao com frontmatter ilegivel e sinal que nao compila sao
    a MESMA falta: nao ha detector para aquela licao. Devolver () seria dizer
    que se olhou, e ninguem olhou (INV-R08).
    """
    with pytest.raises(termometro.ErroDeClassificacao) as vazio:
        termometro.sinais_do_log(LOG_088_EXECUTADO, catalogo={})
    assert "O QUE FAZER" in str(vazio.value)

    ilegivel = dict(catalogo_vivo())
    ilegivel["088"] = dict(ilegivel["088"], erro="frontmatter ilegivel: x")
    with pytest.raises(termometro.ErroDeClassificacao) as torto:
        termometro.sinais_do_log(LOG_088_EXECUTADO, catalogo=ilegivel)
    assert "armadilhas/088" in str(torto.value)

    quebrado = dict(catalogo_vivo())
    quebrado["088"] = dict(quebrado["088"], sinal=("(sem fechar",))
    with pytest.raises(termometro.ErroDeClassificacao) as regex:
        termometro.sinais_do_log(LOG_088_EXECUTADO, catalogo=quebrado)
    assert "compila" in str(regex.value)
    assert catalogo_vivo()["088"].get("erro") is None, (
        "o teste nao pode sujar o catalogo vivo que os outros usam"
    )


def test_o_log_da_088_casa_UM_sinal_e_o_ECO_do_script_nao_casa_nenhum():
    """O sinal vivo da 088 separa a recusa EXECUTADA do eco que so a imprime.

    A terceira assercao e a mentira da chave do gateway: a recusa da 088
    aparece no log, mas o compose reclamou variavel obrigatoria antes dela, e
    essas duas janelas nunca foram da 088.
    """
    catalogo = catalogo_vivo()
    assert termometro.sinais_do_log(LOG_088_EXECUTADO, catalogo=catalogo) == (
        "088",
    )
    assert termometro.sinais_do_log(LOG_088_SO_ECO, catalogo=catalogo) == ()
    assert termometro.sinais_do_log(
        LOG_088_MENTIRA_DA_CHAVE_DO_GATEWAY, catalogo=catalogo
    ) == ()


def test_sinal_que_casa_deploy_VERDE_nao_vota_no_detector():
    """INV-R04: `already exists` e `django-ninja` saem em todo deploy que da
    certo, entao nao podem acusar reincidencia em cima de sucesso.

    A regua e a mesma do compilador do catalogo (`CORPUS_FELIZ_DO_ACTIONS`),
    e nao uma segunda lista de perdoados que alguem esqueceria de atualizar.
    """
    catalogo = catalogo_vivo()
    assert termometro.sinais_do_log(LOG_SAUDAVEL, catalogo=catalogo) == ()
    ainda_casam = [
        numero for numero, regexes in SINAIS_GENERICOS_MEDIDOS.items()
        if any(
            re.search(regex, LOG_SAUDAVEL)
            for regex in regexes if regex in sinais_declarados(numero)
        )
    ]
    assert ainda_casam, (
        "nenhum sinal do catalogo casa mais o log saudavel: sem isso o teste "
        "acima passa por falta de adversario, nao por acerto do detector"
    )


def test_dois_sinais_no_mesmo_log_chegam_como_DOIS_e_viram_ambiguidade():
    """INV-R03: a sonda da 209 cita o soluco da 127 ao negar que seja ele.

    O detector devolve a tupla INTEIRA. Escolher o primeiro aqui esconderia a
    ambiguidade justamente de `natureza_do_fato`, que e quem tem de recusa-la.
    """
    catalogo = catalogo_vivo()
    sinais = termometro.sinais_do_log(LOG_209_SONDA_MAIS_127, catalogo=catalogo)
    assert sinais == ("127", "209")

    real = janelas_que_reincidem("127")[0]
    quadro = um_quadro([fato_da_janela(real, sinais=sinais)])
    assert quadro["ocorrencias"] == 0
    assert quadro["ranking"] == []
    assert "INV-R03" in quadro["nao_classificadas"][0]["motivo"]


def test_o_CLI_imprime_o_QUADRO_e_o_json_e_a_tabela_saem_do_MESMO_objeto(
    monkeypatch, capsys
):
    """O laco fechado: coleta, detector, classificacao e ranking numa execucao.

    E a prova do objeto unico feita onde ela importa, no CLI: o texto impresso
    e, letra por letra, `linhas_do_quadro` do JSON impresso. Mexer num campo do
    JSON move a tabela junto - se houvesse um segundo caminho de calculo, a
    tabela continuaria contando a historia antiga.
    """
    assert _rodar_o_cli(monkeypatch, _bancada_do_laco(), ARGV_DO_LACO) == 0
    texto = capsys.readouterr().out
    assert _rodar_o_cli(
        monkeypatch, _bancada_do_laco(), ARGV_DO_LACO + ["--json"]
    ) == 0
    quadro = json.loads(capsys.readouterr().out)

    assert quadro["ranking"][0]["chave"] == "armadilhas/088"
    assert quadro["ranking"][0]["minutos_ate_cobertura"] == 120
    assert quadro["ranking"][0]["atuacao"] == "interceptada"
    assert quadro["ranking"][1]["chave"] == "armadilhas/127"
    assert quadro["ranking"][1]["atuacao"] == "mitigada"
    assert texto.strip() == "\n".join(
        termometro.linhas_do_quadro(quadro)
    ).strip(), "a tabela impressa tem de ser leitura do JSON impresso"
    assert "COLETA DO DEPLOY-CELULA" in texto, (
        "o relatorio da coleta continua no rodape: o quadro acrescenta, nao "
        "substitui o que a Fase 2 media"
    )

    quadro["ranking"][0]["minutos_ate_cobertura"] = 7
    depois = termometro.linhas_do_quadro(quadro)
    assert any("7 célula-minutos" in linha for linha in depois)
    assert not any("120 célula-minutos" in linha for linha in depois)


def test_uma_execucao_do_CLI_promove_no_maximo_UMA_campea(monkeypatch, capsys):
    """Duas candidatas no ranking, uma promocao - e ela e a primeira."""
    assert _rodar_o_cli(
        monkeypatch, _bancada_do_laco(), ARGV_DO_LACO + ["--json"]
    ) == 0
    quadro = json.loads(capsys.readouterr().out)

    assert len(quadro["ranking"]) == 2
    assert isinstance(quadro["promocao"], dict), (
        "promocao e uma, nao uma lista: a fila da Fase 5 nao pode receber duas "
        "campeas da mesma execucao"
    )
    assert quadro["promocao"]["chave"] == quadro["campea"] == "armadilhas/088"
    assert quadro["promocao"]["origem"] == "ci/termometro.py:armadilhas/088"
    anunciadas = [
        linha for linha in termometro.linhas_do_quadro(quadro)
        if linha.startswith("PROMOÇÃO")
    ]
    assert len(anunciadas) == 1


def test_o_CLI_RECUSA_com_codigo_2_quando_o_detector_nao_pode_ser_construido(
    monkeypatch, capsys
):
    """Sem detector nao ha medicao: tupla vazia seria dizer 'nenhum sinal' sem
    ter olhado, e e assim que buraco de instrumento vira saude (INV-R08).

    A janela deste teste NAO tem queda nenhuma, e e de proposito: a recusa tem
    de acontecer na CONSTRUCAO do detector. Um detector que so falhasse ao ler
    o primeiro log deixaria uma janela limpa sair 0, com relatorio bonito
    saido de um instrumento que nao existe.
    """
    monkeypatch.setattr(
        termometro, "catalogo_das_armadilhas", lambda raiz, git=None, ref=None: {}
    )
    so_verde = Bancada(
        runs={("2026-09-01", "2026-09-04"): [
            _run(1, sha="aaa", criado="2026-09-01T10:00:00Z"),
        ]},
        jobs={1: [_job(11, "deploy (encomendas)", "success")]},
    )
    codigo = _rodar_o_cli(monkeypatch, so_verde, ARGV_DO_LACO)

    assert codigo == 2, (
        "janela sem queda nenhuma nao pode sair 0 com detector inexistente"
    )
    assert so_verde.caminhos == [], (
        "a recusa acontece ANTES da rede: gastar a janela inteira em chamadas "
        "para so entao descobrir que nao ha com que classificar e desperdicio"
    )
    fim = capsys.readouterr()
    assert fim.out.strip() == "", (
        "recusa nao imprime relatorio: quadro pela metade e falso verde"
    )
    assert "detector" in fim.err
    assert "O QUE FAZER" in fim.err, "toda recusa desta casa diz o que fazer"


# ==========================================================================
# F6 e F7: o gatilho terminal mede o run que acabou e abre UMA tarefa.
#
# O que este bloco prende, que e o portao F6 do plano:
#
#   1. Run saudavel nao cria tarefa, e nao gasta nem um download de log.
#   2. Run ambiguo nao cria tarefa (INV-R03).
#   3. Falha desconhecida nao vira ausencia de problema (INV-R08).
#   4. Log ilegivel nao vira ausencia de problema (INV-R08).
#   5. Falha reconhecida mede a janela e abre a tarefa da CAMPEA, com o
#      despacho minimo da secao 11.
#   6. Evento repetido manda a MESMA origem, que e a chave com que a fila
#      recusa a segunda tarefa (INV-R06).
#   7. Causa sem armadilha no catalogo nao inventa numero.
# ==========================================================================


def _bancada_do_gatilho(**extras) -> Bancada:
    """Uma queda da 088 e uma da 127 dentro da janela que o gatilho vai medir.

    As datas ficam DEPOIS do nascimento das duas licoes de proposito: queda
    anterior a licao nao reincide nela, e uma bancada montada antes disso
    mediria zero sem dizer por que.
    """
    padrao = dict(
        runs={},
        runs_por_data=[
            _run(1, sha="aaa", conclusao="failure", criado="2026-09-01T10:00:00Z"),
            _run(2, sha="bbb", criado="2026-09-01T13:00:00Z"),
            _run(3, sha="ccc", conclusao="failure", criado="2026-08-30T10:00:00Z"),
            _run(4, sha="ddd", criado="2026-08-30T11:00:00Z"),
        ],
        jobs={
            1: [_job(11, "deploy (encomendas)", "failure")],
            2: [_job(21, "deploy (encomendas)", "success")],
            3: [_job(31, "deploy (admin)", "failure")],
            4: [_job(41, "deploy (admin)", "success")],
        },
        logs={11: LOG_088_EXECUTADO, 31: LOG_127_SOLUCO_DE_REDE},
        ancestrais=(("aaa", "bbb"), ("ccc", "ddd")),
    )
    padrao.update(extras)
    return Bancada(**padrao)


def _rodar_o_gatilho(monkeypatch, bancada, run_id: int, abertas: list) -> int:
    """`_medir_um_run` de verdade, sem rede e sem escrever na fila.

    `_abrir_tarefa` e a unica costura falsificada: o que ela recebe e o argv
    que iria para `ci/fila.py criar`, e e ele que os testes leem. Quem recusa
    a tarefa repetida continua sendo a fila, e isso se prova la.
    """
    monkeypatch.chdir(RAIZ)
    monkeypatch.setattr(termometro, "_costuras_reais", lambda raiz: dict(
        api=bancada.api, baixar_log=bancada.baixar_log, git=bancada.git,
        jobs_em_lote=bancada.jobs_em_lote,
    ))
    monkeypatch.setattr(
        termometro, "_abrir_tarefa",
        lambda raiz, argumentos: (abertas.append(list(argumentos)), 0)[1],
    )
    return termometro._medir_um_run(["--run", str(run_id)])


def _valor_do_argv(argv: list, bandeira: str) -> str:
    return argv[argv.index(bandeira) + 1]


def test_o_gatilho_no_run_VERDE_nao_abre_tarefa_e_nao_baixa_log(monkeypatch, capsys):
    """O verde tambem passa pelo gatilho, e nao pode custar nem um download.

    Sao cerca de cem deploys saudaveis por dia: um log baixado em cada um
    seria rede gasta para confirmar saude.
    """
    abertas: list = []
    bancada = _bancada_do_gatilho()
    assert _rodar_o_gatilho(monkeypatch, bancada, 2, abertas) == 0
    assert abertas == []
    assert bancada.logs_baixados == []
    assert "Nada a medir" in capsys.readouterr().out


def test_o_gatilho_no_vermelho_SEM_celula_vermelha_nao_abre_tarefa(
    monkeypatch, capsys
):
    """Run vermelho por outra coisa que nao um `deploy (<celula>)`."""
    abertas: list = []
    bancada = _bancada_do_gatilho(
        jobs={1: [_job(11, "muralhas", "failure")]},
    )
    assert _rodar_o_gatilho(monkeypatch, bancada, 1, abertas) == 0
    assert abertas == []
    assert bancada.logs_baixados == []
    assert "sem nenhum job" in capsys.readouterr().out


def test_o_gatilho_com_log_ILEGIVEL_sai_ERROR_e_nao_abre_tarefa(
    monkeypatch, capsys
):
    """INV-R08 no gatilho: nao consegui ler nunca e nada aconteceu."""
    abertas: list = []
    bancada = _bancada_do_gatilho(logs={11: None})
    assert _rodar_o_gatilho(monkeypatch, bancada, 1, abertas) == 2
    assert abertas == []
    erro = capsys.readouterr().err
    assert "NÃO MEDI" in erro and "O QUE FAZER" in erro


def test_o_gatilho_com_DOIS_sinais_no_mesmo_log_sai_ERROR_e_nao_abre_tarefa(
    monkeypatch, capsys
):
    """INV-R03 no gatilho: escolher o primeiro esconderia a ambiguidade de
    quem tem de resolve-la."""
    abertas: list = []
    bancada = _bancada_do_gatilho(
        logs={11: LOG_209_SONDA_MAIS_127}
    )
    assert _rodar_o_gatilho(monkeypatch, bancada, 1, abertas) == 2
    assert abertas == []
    erro = capsys.readouterr().err
    assert "INV-R03" in erro and "O QUE FAZER" in erro


def test_o_gatilho_sem_licao_reconhecida_sai_ERROR_e_diz_o_que_fazer(
    monkeypatch, capsys
):
    """Falha que o catalogo nao cobre e ERROR, e a saida manda escrever a
    licao: e assim que o catalogo cresce sem ninguem inventar numero."""
    abertas: list = []
    bancada = _bancada_do_gatilho(logs={11: "uma falha que ninguem documentou"})
    assert _rodar_o_gatilho(monkeypatch, bancada, 1, abertas) == 2
    assert abertas == []
    erro = capsys.readouterr().err
    assert "INV-R08" in erro
    assert "armadilhas/" in erro and "Nenhuma tarefa foi aberta" in erro


def test_o_gatilho_reconhecido_MEDE_a_janela_e_abre_a_tarefa_da_campea(
    monkeypatch, capsys
):
    """O laco fechado, do run terminal ate o comando da fila.

    O run que dispara e o da 088; a medicao da janela e quem decide a campea,
    e o despacho carrega o minimo da secao 11: base medida, custo, celulas,
    guarda declarada, comando de mutacao e evidencia de encerramento.
    """
    abertas: list = []
    bancada = _bancada_do_gatilho()
    assert _rodar_o_gatilho(monkeypatch, bancada, 1, abertas) == 0
    assert len(abertas) == 1, "uma execucao promove no maximo UMA campea"
    argv = abertas[0]
    assert argv[0] == "criar"
    assert _valor_do_argv(argv, "--origem") == "ci/termometro.py:armadilhas/088"
    assert _valor_do_argv(argv, "--move") == "manutencao"
    assert _valor_do_argv(argv, "--responsabilidade") == "operacao-tecnica"
    assert "088" in _valor_do_argv(argv, "--titulo")
    assert _valor_do_argv(argv, "--importancia") == str(
        termometro.IMPORTANCIA_DA_CAMPEA
    )
    despacho = _valor_do_argv(argv, "--despacho")
    assert sha_desta_bancada() in despacho, "o despacho publica a base medida"
    assert "encomendas" in despacho, "as celulas afetadas estao no despacho"
    assert "python ci/provar_guardas.py" in despacho
    assert "EVIDÊNCIA DE ENCERRAMENTO" in despacho
    assert "nunca criar uma segunda guarda" in despacho, (
        "a 088 e interceptada: a promocao preserva a guarda (INV-R11, INV-R12)"
    )
    assert "TERMÔMETRO" in capsys.readouterr().out


def test_o_gatilho_REPETIDO_manda_a_MESMA_origem_e_nao_uma_segunda(monkeypatch):
    """INV-R06: o evento repetido nao cria tarefa nova.

    A identidade e a `origem`, e e ela que a fila confere antes de gastar
    numero do almoxarife. Duas execucoes tem de mandar exatamente a mesma.
    """
    import fila

    abertas: list = []
    _rodar_o_gatilho(monkeypatch, _bancada_do_gatilho(), 1, abertas)
    _rodar_o_gatilho(monkeypatch, _bancada_do_gatilho(), 1, abertas)
    origens = {_valor_do_argv(a, "--origem") for a in abertas}
    assert len(abertas) == 2 and len(origens) == 1
    assert fila.RE_ORIGEM_AUTOMATICA.fullmatch(origens.pop()), (
        "a origem tem de casar a chave que a fila usa para deduplicar"
    )
    assert abertas[0] == abertas[1], (
        "mesmo fato, mesmo comando: qualquer campo que mude por execucao "
        "faria a fila ver duas tarefas diferentes"
    )


def test_a_causa_sem_armadilha_no_catalogo_nao_vira_tarefa_automatica():
    """Quem da numero e o almoxarife.

    A causa do gateway venceria por tempo num quadro so dela, e ainda assim
    nao pode virar `armadilhas/NNN` inventado aqui.
    """
    gateway = janelas_com_causa(CAUSA_GATEWAY)
    quadro = um_quadro([fato_da_janela(j) for j in gateway])
    assert quadro["campea"] == f"causa/{CAUSA_GATEWAY}"
    assert quadro["promocao"]["precisa_de_numero"] is True
    assert termometro.argumentos_da_tarefa(quadro, catalogo_vivo()) is None


def test_o_despacho_de_armadilha_SEM_guarda_manda_construir_a_guarda():
    """Campea sem guarda mecanica nao recebe um comando de mutacao vazio.

    `python ci/provar_guardas.py ` sem arquivo nenhum e instrucao quebrada, e
    instrucao quebrada e pior que instrucao ausente: quem le tenta rodar.
    """
    real = janelas_que_reincidem("088")[0]
    catalogo = dict(catalogo_vivo())
    catalogo["088"] = dict(
        catalogo["088"], guarda="nenhum", dono=None, detector=None,
    )
    quadro = termometro.montar_quadro(
        [fato_da_janela(real)], catalogo=catalogo, base="origin/main", sha="f" * 40,
    )
    argv = termometro.argumentos_da_tarefa(quadro, catalogo)
    despacho = argv[argv.index("--despacho") + 1]
    vazio = "python ci/provar_guardas.py" + chr(10)
    assert vazio not in despacho + chr(10)
    assert "ainda não existe" in despacho
    assert "guarda que esta tarefa vai construir" in despacho


def test_erros_de_medicao_separam_buraco_de_instrumento_de_resposta_medida():
    """O codigo de saida so fica vermelho por ERRO, e nunca por resultado.

    A queda que escreveu a licao e uma resposta com data e motivo; log
    ilegivel, ambiguidade e ausencia de casamento sao buraco de instrumento.
    Misturar os dois faria o comando gritar todo mes por ter acertado.
    """
    quadro = quadro_do_corpus()
    cegas = termometro.erros_de_medicao(quadro)
    assert len(quadro["nao_classificadas"]) == 5
    assert len(cegas) == 3, [c["motivo"][:40] for c in cegas]
    assert all("nasceu em" not in c["motivo"] for c in cegas)
