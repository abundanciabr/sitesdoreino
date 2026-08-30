#!/usr/bin/env python3
"""A VACINA DO DEPLOY QUE NÃO CHEGOU — armadilhas/127 e armadilhas/188.

Duas doenças, o mesmo desfecho para o mantenedor: o merge está na `main` e
NÃO está em produção, em silêncio. A 127 é o deploy que FALHOU no SSH; a 188
é o deploy que foi CANCELADO por push — expulso da vaga de pendente do grupo
`deploy` pelo merge seguinte. Esta vacina cuida das duas.

Por que ela existe (29/08/2026): a `armadilhas/127` é o MAIOR sangramento
medido deste catálogo. A contagem de citações no livro de ocorrências deu 5
registros, com frases como "quinta vez em três dias" e "sexta vez"; e ela mordeu
mais uma vez em 29/08/2026, durante a própria auditoria que a elegeu campeã.

Cada queda custava a mesma coisa: um robô relia a entrada, media a porta 22 à
mão, decidia se era blip ou a `armadilhas/017`, repetia o deploy e conferia o
veredito — um diagnóstico do zero, no modelo caro, para um procedimento que é
inteiramente DECIDIDO. Documentar não bastou: a lição estava escrita, completa e
correta, e mesmo assim era re-executada à mão toda vez.

Este script é o degrau 2 da hierarquia da vacina (o procedimento vira
mecanismo), e não o degrau 6 (documentar). O que ele faz, na ordem exata que a
entrada manda:

  1. Colhe o veredito REAL do run por `gh run view --json status,conclusion` —
     nunca pelo exit de um pipe (armadilhas/045).
  2. Se o run não falhou, não faz nada. Repetir o que passou é ruído.
  3. Lê o log do run: a falha É de SSH (`dial tcp ...:22: i/o timeout`)?
     Se não for, PARA. Repetir uma falha de código não conserta código, e
     tratar toda falha como blip é a receita para esconder defeito real.
  4. Mede a porta 22 da VPS, do PC — é a medição que separa a 127 (blip
     intermitente entre o runner e a VPS) da 017 (falha PERMANENTE de
     configuração, território do mantenedor). Porta morta ⇒ PARA e reporta.
  5. Repete o deploy. Entre a segunda e a terceira tentativa, espera —
     em 26/08/2026 duas tentativas falharam a 80 s uma da outra e a terceira,
     depois da pausa, passou. Reruns emendados batem na mesma janela ruim.
  6. Regra de parada: três reruns vermelhos com a porta respondendo ⇒ para,
     e escreve o texto do registro de pendência para o livro. Uma quarta
     tentativa não é diagnóstico.

E diz sempre a frase que o mantenedor precisa ouvir: deploy vermelho por SSH
significa que a imagem NOVA não subiu — a antiga continua servindo, ninguém fica
fora do ar, mas o merge não está em produção até o verde. É fácil esquecer disso
e anunciar a entrega como no ar.

--------------------------------------------------------------------------
O SEGUNDO CASO — `cancelled` de PUSH (armadilhas/188, TAR-017, 30/08/2026)

Até 30/08/2026 esta vacina devolvia "NADA" para QUALQUER `conclusion`
`cancelled`, com a orientação da `armadilhas/173`: *cancelamento tem causa
própria e não se cura repetindo*. Isso está certo para o disparo MANUAL da
173 — a cura lá é dar grupo de concorrência próprio ao workflow, e repetir só
perde a cadeira outra vez. E está ERRADO para o deploy de PUSH, que **tem** de
ficar no grupo `deploy`: ali o expulso é um merge que ficou fora do ar, e a
vacina mandava o agente fechar a tarefa achando que não havia nada a fazer.

Para o `cancelled` de push, o que decide é ANCESTRALIDADE — e ela se mede no
Actions e no Git, nunca perguntando à VPS (o agente não tem SSH, Lei 5):

  a. Qual SHA a última publicação VERDE do `deploy-celula` pôs no ar?
     (`gh run list --workflow deploy-celula.yml --branch main --json
     headSha,conclusion`)
  b. Esse SHA é ancestral do SHA deste run? Um rerun publica o SHA DAQUELE
     run, não o topo da `main` — se o publicado for ancestral, republicar só
     AVANÇA. Se não for, repetir seria um **rollback silencioso**: PARA.
  c. Se o SHA deste run já está contido no publicado, o merge JÁ está no ar
     por uma publicação mais nova: nada a repetir (e repetir faria voltar).
  d. Quantos commits da `main` ficam de fora do rerun, e algum deles toca os
     `paths:` do `deploy-celula`? Se tocam, cada um terá o próprio deploy e
     não há o que perder. Se NENHUM toca, nenhum deploy novo vai nascer
     sozinho — e repetir é a única saída.

--------------------------------------------------------------------------
O TERCEIRO CASO — o `deploy-infra` cancelado (TAR-029, 30/08/2026)

Até 30/08/2026 esta vacina só sabia falar de UM workflow: `WORKFLOW_DO_DEPLOY`
= `deploy-celula.yml` era constante, e `sha_do_ultimo_deploy_verde()` era
chamada SEM argumento também quando o run cancelado era do `deploy-infra`. Ou
seja, ela media o SHA de um `deploy-infra` cancelado contra a última publicação
verde do `deploy-CELULA` — duas esteiras que publicam coisas DIFERENTES (a
imagem de uma célula e o `docker-compose.yml`/`traefik` da VPS).

Isso não é detalhe: as duas referências divergem o tempo todo, porque o
`deploy-celula` dispara em `painel/**` e TODO PR deste projeto carrega um
registro obrigatório ali. MEDIDO em 30/08/2026, nos dois últimos verdes do dia:
o do `deploy-celula` (`00952d43`) continha o do `deploy-infra` (`8848f1f7`) e
mais **47 commits**, nenhum deles tocando `infra/`. Um `deploy-infra` cancelado
em qualquer ponto dessa faixa receberia da vacina antiga o veredito
`head_ja_publicado = True` — *"o commit dele JÁ está no ar, nada a repetir"* —
sobre uma infraestrutura que NUNCA foi sincronizada. É o falso-verde da
RETROSPECTIVA-FASE-D §1 dentro da própria vacina.

Desde a TAR-029 a esteira é lida do run (`workflowName`) e todas as medidas —
qual publicação está no ar, quais `paths:` fazem nascer deploy novo — usam o
workflow DAQUELE run. Sem esteira sabida, o cancelado de push vira ERROR: não
há como dizer se um rerun avança sem saber contra o que comparar.

--------------------------------------------------------------------------
A REGRA DE PARADA PRECISA SOBREVIVER AO PROCESSO (TAR-029)

`MAXIMO_DE_TENTATIVAS` sempre existiu, mas contava em memória: cada execução do
script começava do zero. Isso bastava enquanto um humano rodava a vacina — e
deixa de bastar no minuto em que ela é chamada por GATILHO
(`.github/workflows/vacina-do-deploy.yml`), porque o desfecho de um rerun
cancelado dispara o gatilho DE NOVO: vacina → rerun → cancelado → vacina →
rerun, para sempre, cada volta com o contador em zero.

A conta durável já existe e mora no GitHub: o `attempt` do próprio run. Ela é
colhida junto com o veredito e vira o PISO de `tentativas_feitas`, então a
regra de parada passa a valer entre processos. Medido no dia: o run
33325108776 estava em `attempt: 4` — três repetições feitas à mão, antes de
existir automatismo nenhum.

--------------------------------------------------------------------------
O QUARTO CASO — o `failure` por timeout, com GATILHO (TAR-041, 30/08/2026)

A tabela sempre soube decidir o `failure` por timeout da porta 22: é o caso
ORIGINAL desta vacina, a `armadilhas/127`. O que faltava era o GATILHO —
`vacina-do-deploy.yml` só acordava no `cancelled`, com a justificativa escrita
de que *"`failure` na `main` já tem dono: o agente que mergeou, avisado pelo
vermelho"*. Medido em 30/08/2026, essa justificativa não se sustentou:

  - 14 dos 41 deploys vermelhos dos últimos 30 dias morreram no timeout da
    porta 22 — e 13 deles nos últimos 7 dias. TRÊS num único dia (PRs #610,
    #622 e #635), que é a régua que a própria 127 declara: *"dois episódios em
    24h ainda são blip; três viram estrutura"*.
  - A escada de 3 tentativas DENTRO do deploy quase não salva: das 18 vezes em
    que a VPS recusou a 1ª conexão, 17 chegaram à 3ª tentativa e as 17
    morreram. A janela ruim dura mais que os 105 s de pausa do workflow.
  - O `gh run rerun --failed`, minutos depois, curou em todas elas.

Ou seja: o dono existia, e o trabalho dele era apertar um botão que uma
máquina podia apertar. Desde a TAR-041 o gatilho cobre as duas conclusões.

E COBRIR O `failure` OBRIGOU A TRAZER O PORTÃO DA 188 PARA CÁ. Enquanto quem
rodava a vacina era um robô, do PC, minutos depois do próprio merge, "repetir
faz voltar alguma coisa?" tinha resposta óbvia. Com gatilho, não tem: um
`gh run rerun --failed` reconstrói a imagem do SHA DAQUELE run, e a 188 escreve
a frase inteira — *"nunca repita o run FALHADO de um commit mais velho para
curar o seu: ele publica o mundo sem o seu merge"*. Por isso o `failure` passou
a atravessar exatamente o mesmo `_a_republicacao_avanca` do cancelado, e a
recusar disparo que não seja `push`.

E OBRIGOU A SEPARAR "VEREDITO" DE "ALARME". Com o gatilho no `cancelled`,
`codigo != 0` e "acorde um humano" eram a mesma coisa. Não são mais: 27 dos 41
vermelhos são defeito de código, que já está vermelho e já tem dono. Quem
responde essa segunda pergunta é `Decisao.precisa_de_alarme`, num canal próprio
(`$GITHUB_OUTPUT`), sem torcer o sentido do código de saída.

--------------------------------------------------------------------------
Uso:
    python ci/rerun_de_deploy.py --run <id>        # cuida deste run
    python ci/rerun_de_deploy.py --ultimo          # o último deploy-celula
    python ci/rerun_de_deploy.py --ultimo --workflow deploy-infra.yml
    python ci/rerun_de_deploy.py --run <id> --so-diagnosticar   # não repete

Semântica de saída [INV-CI01]: 0 PASS (verde, ou nada a fazer) · 1 FAIL (parou
por regra: é a 017, é outra falha, ou estourou a regra de parada) · 2 ERROR
(não consegui medir — e não medir nunca vira "deu certo").
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _nucleo import configurar_saida, raiz_do_repo  # noqa: E402

# A MEDIÇÃO DA PORTA 22 MORA EM UM LUGAR SÓ (TAR-013, 30/08/2026). Desde que o
# `deploy-celula.yml` passou a medir a porta de dentro do próprio deploy, a
# mesma pergunta — "a VPS está alcançável agora?" — é feita de dois lugares: o
# runner, entre as tentativas, e o PC, depois do fato. Se cada um tivesse a sua
# cópia, bastaria alguém afinar o tempo de espera de um deles para as duas
# vacinas passarem a discordar sobre o MESMO fato — e ninguém perceberia até o
# dia em que a discordância decidisse um deploy. É a lei anti-duplicação do
# `CLAUDE.md` aplicada a uma medição.
from sonda_da_vps import VPS_PADRAO, http_do_site, porta_22_responde  # noqa: E402

MAXIMO_DE_TENTATIVAS = 3
PAUSA_ENTRE_TENTATIVAS_S = 60
INTERVALO_DE_CONFERENCIA_S = 15
TETO_PADRAO_MIN = 15

WORKFLOW_DO_DEPLOY = "deploy-celula.yml"
PASTA_DOS_WORKFLOWS = Path(".github") / "workflows"
ARQUIVO_DO_WORKFLOW = PASTA_DOS_WORKFLOWS / WORKFLOW_DO_DEPLOY
RUNS_OLHADOS_ATRAS = 30
REF_DO_TOPO = "origin/main"

RE_TIMEOUT_SSH = re.compile(r"dial tcp [^\n]*:22: i/o timeout")
# Outras falhas de SSH que NÃO são a 127 — não se resolvem repetindo.
RE_SSH_AUTENTICACAO = re.compile(
    r"ssh: handshake failed|permission denied|unable to authenticate", re.IGNORECASE
)
# `paths: ['services/**', 'painel/**', ...]` — a forma EM LINHA, do deploy-celula.
RE_PATHS_DO_GATILHO = re.compile(r"^\s*paths:\s*\[(?P<lista>[^\]]*)\]", re.MULTILINE)
# `paths:` seguido de `  - 'infra/...'` — a forma EM BLOCO, do deploy-infra. As
# duas são YAML válido e as duas existem neste repositório: uma vacina que só
# soubesse ler a primeira acharia que o gatilho do `deploy-infra` mudou de forma
# e devolveria ERROR onde a resposta era simples (TAR-029).
RE_PATHS_EM_BLOCO = re.compile(r"^(?P<recuo>\s*)paths:\s*$", re.MULTILINE)
RE_ITEM_DE_LISTA = re.compile(r"^\s*-\s*(?P<item>\S.*?)\s*$")
# O `name:` do topo de um workflow — é ele que o `workflowName` de um run diz.
RE_NOME_DO_WORKFLOW = re.compile(r"^name:\s*(?P<nome>\S.*?)\s*$", re.MULTILINE)


class ErroDeMedicao(Exception):
    """Não consegui medir — vira ERROR (2), nunca um veredito otimista."""


@dataclass
class Fatos:
    """Tudo o que se sabe do mundo. Colher e decidir são separados de propósito:
    a tabela de decisão inteira fica testável sem rede, sem `gh` e sem VPS."""

    run: str
    status: str = ""
    conclusion: str = ""
    tem_timeout_ssh: bool = False
    tem_falha_de_autenticacao: bool = False
    porta22_viva: bool | None = None
    site_http: int | None = None
    tentativas_feitas: int = 0
    # A ESTEIRA DESTE RUN (`workflowName`), e não uma constante (TAR-029). Ela
    # decide contra QUAL publicação a ancestralidade é medida: `deploy-celula` e
    # `deploy-infra` publicam coisas diferentes, e comparar um com o outro
    # devolve "já está no ar" sobre algo que nunca subiu.
    workflow: str = ""
    # --- o cancelado de PUSH (armadilhas/188). `None` = NÃO MEDIDO, sempre ---
    event: str = ""
    head_sha: str = ""
    sha_publicado: str = ""
    publicado_e_ancestral: bool | None = None
    head_ja_publicado: bool | None = None
    commits_de_fora: int | None = None
    commits_de_fora_tocam_o_deploy: bool | None = None


@dataclass
class Decisao:
    acao: str  # "nada" | "repetir" | "parar"
    codigo: int
    motivo: str
    recado: str = ""
    pendencia: str = field(default="")
    # Um run CANCELADO não tem job falhado para `--failed` repetir: ele precisa
    # do rerun inteiro. Quem decide o QUE repetir é a mesma tabela que decide
    # SE repete — senão a escolha viraria improviso do main() (armadilhas/188).
    rerun_apenas_falhados: bool = True
    # ESTE DESFECHO PRECISA ACORDAR UM HUMANO? (TAR-041, 30/08/2026)
    #
    # Até aqui a pergunta não existia porque o gatilho automático só acordava no
    # `cancelled`, e TODO cancelado que a vacina não cura é um merge invisível
    # fora do ar — ou seja, `codigo != 0` e "precisa de alarme" eram a mesma
    # coisa. Com o gatilho cobrindo também o `failure`, deixam de ser: a maioria
    # esmagadora dos deploys vermelhos é defeito de código, que **já tem dono** —
    # o run está VERMELHO, quem mergeou foi avisado, e o `alarme-main` existe
    # para isso. Abrir uma issue `deploy-fora-do-ar` para cada um deles seria o
    # alarme que se aprende a ignorar, e aí ele deixa de servir no caso em que
    # importa (o mesmo argumento que o próprio `vacina-do-deploy.yml` escreve
    # sobre não gritar em todo cancelamento).
    #
    # `True` por padrão de propósito: ramo novo nasce BARULHENTO, e o silêncio
    # tem de ser escrito à mão, com o motivo do lado. O contrário — nascer mudo
    # e alguém lembrar de ligar o alarme — é a garantia sem mecanismo da
    # RETROSPECTIVA-FASE-D §2. Só é consultado quando `codigo != 0`.
    precisa_de_alarme: bool = True


def decidir(fatos: Fatos) -> Decisao:
    """A tabela de decisão das armadilhas 127 e 188, pura e completa."""
    if fatos.status != "completed":
        return Decisao(
            "nada", 2,
            f"o run {fatos.run} ainda está '{fatos.status}' — não terminou de "
            "ser medido, e medir pela metade não vira veredito (INV-CI01)",
        )
    if fatos.conclusion == "success":
        return Decisao("nada", 0, f"o run {fatos.run} está VERDE — nada a repetir")
    if fatos.conclusion == "skipped":
        return Decisao(
            "nada", 1,
            f"o run {fatos.run} terminou 'skipped', não 'failure' — ele nem "
            "chegou a rodar, e um run que foi pulado não se cura repetindo: "
            "quem decide isso é a condição do workflow, não uma tentativa nova",
            precisa_de_alarme=False,
        )
    if fatos.conclusion == "cancelled":
        return _decidir_o_cancelado(fatos)
    if fatos.tem_falha_de_autenticacao:
        return Decisao(
            "parar", 1,
            "a falha de SSH é de AUTENTICAÇÃO, não de alcance — chave ou "
            "usuário, território do mantenedor. Repetir não conserta credencial.",
        )
    if not fatos.tem_timeout_ssh:
        return Decisao(
            "parar", 1,
            f"o run {fatos.run} falhou, mas NÃO com o timeout de SSH da "
            "armadilhas/127. Repetir uma falha de código não conserta código — "
            "e trataria um defeito real como blip. Veja o log: "
            f"gh run view {fatos.run} --log-failed",
            # SEM ALARME, e é o ramo que torna o gatilho no `failure` viável
            # (TAR-041): este deploy está VERMELHO na `main`, quem mergeou já
            # foi avisado pelo próprio vermelho e o `alarme-main` cuida da
            # `main` vermelha. Medido em 30/08/2026: dos 41 deploys vermelhos
            # dos últimos 30 dias, 27 são deste ramo. Uma issue por cada um
            # afogaria as 14 que interessam.
            precisa_de_alarme=False,
        )
    if fatos.porta22_viva is False:
        return Decisao(
            "parar", 1,
            "a porta 22 da VPS NÃO respondeu do PC. Isso não é o blip da "
            "armadilhas/127: é a armadilhas/017 (falha permanente — o que o "
            "VPS_HOST resolve? há Cloudflare na frente?). Repetir só gasta "
            "tempo; o conserto é de configuração e passa pelo mantenedor.",
            pendencia=_texto_da_pendencia(fatos, permanente=True),
        )
    if fatos.porta22_viva is None:
        return Decisao(
            "nada", 2,
            "não consegui medir a porta 22 — e sem essa medição não dá para "
            "separar o blip da armadilhas/127 da falha permanente da 017. "
            "'Não medi' não vira 'pode repetir'." + _o_medidor_estava_cego(fatos),
        )
    # ------------------------------------------------------------------
    # DAQUI PARA BAIXO É O MESMO PORTÃO QUE O CANCELADO JÁ ATRAVESSAVA — e ele
    # não era exigido do `failure` até a TAR-041 (30/08/2026).
    #
    # Por que ele NÃO fazia falta antes: quem rodava a vacina num `failure` era
    # um robô, do PC, minutos depois do PRÓPRIO merge. O run que ele repetia era
    # o dele, o SHA era o mais novo do mundo, e a pergunta "isto faz voltar
    # alguma coisa?" tinha resposta óbvia.
    #
    # Por que ele passa a fazer: desde a TAR-041 o gatilho automático acorda
    # também no `failure`, e aí ninguém garante que o run doente é o mais novo.
    # `gh run rerun --failed` reconstrói a imagem a partir do SHA DAQUELE run —
    # a armadilhas/188 escreve a frase inteira: *"Nunca repita o run FALHADO de
    # um commit mais velho para curar o seu: ele publica o mundo sem o seu
    # merge."* Sem este portão, o gatilho novo publicaria um mundo mais velho
    # sozinho, sem ninguém pedir e sem nada ficar vermelho. Seria a vacina
    # virando a doença.
    # ------------------------------------------------------------------
    if fatos.event != "push":
        return Decisao(
            "nada", 1,
            f"o run {fatos.run} falhou no timeout da porta 22, mas o disparo "
            f"foi '{fatos.event or 'desconhecido'}', não 'push'. A vacina "
            "automática cura deploy de MERGE: um disparo manual tem um humano "
            "que apertou o botão e sabe o que queria publicar, e repeti-lo "
            "sozinho publicaria o SHA daquele disparo sem que ninguém tivesse "
            "pedido. Rode `gh run rerun` à mão se for isso que você quer.",
            precisa_de_alarme=False,
        )
    barreira = _a_republicacao_avanca(fatos, o_que_houve="falhou no timeout da porta 22")
    if barreira is not None:
        return barreira
    if fatos.tentativas_feitas >= MAXIMO_DE_TENTATIVAS:
        return Decisao(
            "parar", 1,
            f"{fatos.tentativas_feitas} tentativas vermelhas com a porta 22 "
            "respondendo. A regra de parada da armadilhas/127 é justamente "
            "esta: a quarta tentativa não é diagnóstico, é teimosia.",
            pendencia=_texto_da_pendencia(fatos, permanente=False),
        )
    return Decisao(
        "repetir", 0,
        "a porta 22 respondeu e o site está de pé: é o blip intermitente entre "
        "o runner e a VPS (armadilhas/127), não a 017. E o que "
        f"`{fatos.workflow or 'esta esteira'}` tem publicado "
        f"({_curto(fatos.sha_publicado)}) É ancestral do SHA deste run "
        f"({_curto(fatos.head_sha)}): republicar só AVANÇA. Repetindo o deploy.",
        recado=_recado_do_que_fica_de_fora(fatos),
    )


def _o_medidor_estava_cego(fatos: Fatos) -> str:
    """A testemunha que separa "a VPS sumiu" de "EU não enxergo nada".

    Não muda veredito nenhum — muda o que o humano lê na issue. Quando a porta
    22 fica muda E o site público (que serve 200 para o mundo) também não
    responde de onde a vacina está medindo, quem está cego é o MEDIDOR, não a
    VPS. Foi exatamente isso que o log do run 33330434813 gravou, do runner do
    deploy: *"e daqui eu também NÃO alcancei o site público"*.

    Sem esta frase, a issue diz "não consegui medir a porta 22" e o mantenedor
    lê "a minha VPS está com problema" — que é a leitura errada, e a cara da
    `armadilhas/209` (o falso-vermelho categórico).
    """
    if fatos.site_http == 200:
        return (
            " Vale saber: daqui o site público respondeu 200, então esta máquina "
            "enxerga a internet — o silêncio é da porta 22 mesmo."
        )
    if fatos.site_http is None:
        return (
            " E daqui eu também NÃO alcancei o site público, que serve 200 para "
            "o mundo: quem está cego é a máquina que mediu, não necessariamente "
            "a VPS (armadilhas/209)."
        )
    return f" (o site público respondeu {fatos.site_http} daqui.)"


def _decidir_o_cancelado(fatos: Fatos) -> Decisao:
    """O cancelamento tem DUAS causas, e elas pedem coisas OPOSTAS.

    `armadilhas/173` — disparo MANUAL expulso da vaga de pendente do grupo
    `deploy`. A cura é grupo de concorrência próprio; repetir só perde a
    cadeira outra vez, e num dia movimentado perde sempre.

    `armadilhas/188` — deploy de PUSH expulso pelo merge seguinte. Aqui o
    grupo `deploy` é obrigatório (dois donos do mesmo `docker compose up` é
    pior que um disparo perdido), o merge ficou na `main` sem chegar ao ar, e
    **repetir É a cura** — depois de provar que republicar aquele SHA não faz
    nada voltar.
    """
    if fatos.event != "push":
        return Decisao(
            "nada", 1,
            f"o run {fatos.run} terminou 'cancelled' e o disparo foi "
            f"'{fatos.event or 'desconhecido'}', não 'push' — cancelamento de "
            "disparo manual tem causa própria (armadilhas/173: a vaga de "
            "pendente do grupo `deploy` é cadeira musical) e não se cura "
            "repetindo. A cura é dar grupo de concorrência próprio ao workflow.",
            precisa_de_alarme=False,
        )
    barreira = _a_republicacao_avanca(fatos, o_que_houve="foi cancelado")
    if barreira is not None:
        return barreira
    if fatos.tentativas_feitas >= MAXIMO_DE_TENTATIVAS:
        return Decisao(
            "parar", 1,
            f"{fatos.tentativas_feitas} tentativas e o deploy segue sendo "
            "cancelado — a vaga de pendente do grupo `deploy` está sendo "
            "tomada a cada volta (armadilhas/173+188). A regra de parada é a "
            "mesma da 127: a quarta tentativa não é diagnóstico, é teimosia.",
            pendencia=_pendencia_do_cancelado(fatos, divergente=False),
        )
    return Decisao(
        "repetir", 0,
        f"o run {fatos.run} é um deploy de PUSH cancelado (armadilhas/188) de "
        f"`{fatos.workflow}` e o que essa esteira tem publicado "
        f"({_curto(fatos.sha_publicado)}) É ancestral do SHA "
        f"deste run ({_curto(fatos.head_sha)}): republicar só AVANÇA, nada "
        "volta. Repetindo o deploy.",
        recado=_recado_do_que_fica_de_fora(fatos),
        rerun_apenas_falhados=False,
    )


def _a_republicacao_avanca(fatos: Fatos, o_que_houve: str) -> Decisao | None:
    """Repetir este run AVANÇA, ou faz voltar? `None` = pode repetir.

    Este é o portão que a `armadilhas/188` descreve em três medidas, e ele vale
    para os DOIS jeitos de um deploy não chegar ao ar — o cancelado (188) e o
    que falhou no timeout da porta 22 (127). Era código do ramo do cancelado até
    a TAR-041; virou função porque a segunda porta passou a precisar dele, e
    duplicá-lo seria assinar que um dia os dois discordariam sobre a mesma
    conta (a lei anti-duplicação do CLAUDE.md, aplicada a uma decisão).

    `o_que_houve` é só a metade da frase que muda entre os dois casos ("foi
    cancelado" / "falhou no timeout da porta 22"): a mensagem precisa dizer ao
    humano o que aconteceu com AQUELE run, e um texto genérico foi exatamente o
    que fez um agente fechar a tarefa com o merge fora do ar (188).

    O BURACO QUE ESTA FUNÇÃO NÃO FECHA, e não é ela que fecha: para o
    `deploy-celula`, "o publicado é ancestral do meu SHA" é uma resposta de RUN
    a uma pergunta de CÉLULA. Um verde mais novo pode conter este commit no Git
    e ainda assim não ter publicado a célula que morreu aqui, porque cada run
    publica só as células que o push DELE tocou (armadilhas/215, e a 220 já
    declara este buraco aberto). O ramo `head_ja_publicado` herda isso — dizer
    "já está no ar" pode ser grosso demais. Declarado, não silencioso.
    """
    if not fatos.workflow:
        return Decisao(
            "nada", 2,
            f"o run {fatos.run} {o_que_houve} (deploy de PUSH que não chegou ao "
            "ar), mas eu não sei de QUAL esteira ele é. `deploy-celula` e "
            "`deploy-infra` publicam coisas diferentes, e a única pergunta que "
            "decide o caso — 'o que está publicado é ancestral deste SHA?' — não "
            "tem resposta sem saber contra qual publicação comparar. Medir "
            "contra a esteira errada devolve 'já está no ar' sobre algo que "
            "nunca subiu (TAR-029).",
        )
    if not fatos.head_sha or not fatos.sha_publicado:
        return Decisao(
            "nada", 2,
            f"o run {fatos.run} {o_que_houve} (armadilhas/188) "
            f"na esteira `{fatos.workflow}`, mas não consegui descobrir os dois "
            "SHAs que decidem o caso — o "
            f"deste run ({fatos.head_sha or 'ausente'}) e o da última "
            f"publicação verde ({fatos.sha_publicado or 'ausente'}). Sem eles "
            "não dá para saber se um rerun avança ou faz voltar, e 'não medi' "
            "nunca vira 'pode repetir' (INV-CI01).",
        )
    if fatos.publicado_e_ancestral is None or fatos.head_ja_publicado is None:
        return Decisao(
            "nada", 2,
            "não consegui medir a ancestralidade entre o SHA publicado "
            f"({_curto(fatos.sha_publicado)}) e o deste run "
            f"({_curto(fatos.head_sha)}) — provavelmente o commit não existe "
            "neste checkout (clone raso ou fetch faltando, armadilhas/159). "
            "Sem essa medição, repetir seria apostar num rollback.",
        )
    if fatos.head_ja_publicado:
        iguais = fatos.publicado_e_ancestral
        return Decisao(
            "nada", 0,
            f"o run {fatos.run} {o_que_houve}, mas o commit dele JÁ está no ar "
            f"por `{fatos.workflow}`: "
            + (
                f"a última publicação verde é exatamente {_curto(fatos.head_sha)}."
                if iguais
                else f"a última publicação verde ({_curto(fatos.sha_publicado)}) "
                f"já contém {_curto(fatos.head_sha)}."
            )
            + " Nada a repetir — e repetir agora republicaria um mundo mais "
            "VELHO, que é o rollback silencioso da armadilhas/188.",
        )
    if not fatos.publicado_e_ancestral:
        return Decisao(
            "parar", 1,
            f"PARAR: o que `{fatos.workflow}` tem publicado "
            f"({_curto(fatos.sha_publicado)}) NÃO é "
            f"ancestral do SHA deste run ({_curto(fatos.head_sha)}), e também "
            "não o contém — as duas linhas divergiram. Um rerun publica o SHA "
            "DAQUELE run, então repetir aqui seria um rollback silencioso "
            "(armadilhas/188). Isto se trata à mão, com o histórico na frente.",
            pendencia=_pendencia_do_cancelado(fatos, divergente=True),
        )
    return None


def _curto(sha: str) -> str:
    return sha[:12] if sha else "?"


def _recado_do_que_fica_de_fora(fatos: Fatos) -> str:
    """Um rerun publica o SHA DAQUELE run, não o topo da `main`.

    O que fica de fora não muda a decisão — muda o que o agente precisa saber
    depois dela, e é a diferença entre "espere o próximo deploy" e "repetir é
    a única saída" (armadilhas/188).
    """
    alvo = f"{REF_DO_TOPO} (o topo da `main`)"
    if fatos.commits_de_fora is None:
        return (
            f"não consegui contar quantos commits de {alvo} ficam de fora deste "
            "rerun — ele publica o SHA daquele run, não o topo. Confira à mão "
            f"com: git rev-list --count {_curto(fatos.head_sha)}..{REF_DO_TOPO}"
        )
    if fatos.commits_de_fora == 0:
        return f"o SHA deste run é {alvo}: o rerun publica tudo o que existe."
    quantos = f"{fatos.commits_de_fora} commit(s) de {alvo} ficam de fora deste rerun"
    if fatos.commits_de_fora_tocam_o_deploy is None:
        return (
            f"{quantos}, e não consegui medir se algum deles toca os `paths:` do "
            f"{WORKFLOW_DO_DEPLOY} — sem isso não dá para dizer se eles terão "
            "deploy próprio."
        )
    if fatos.commits_de_fora_tocam_o_deploy:
        return (
            f"{quantos} — mas eles TOCAM os `paths:` do {WORKFLOW_DO_DEPLOY}, "
            "então cada um terá o próprio deploy e não há o que perder."
        )
    try:
        quais = ", ".join(paths_do_deploy())
    except ErroDeMedicao:  # o recado é texto, não veredito: nunca derruba a decisão
        quais = f"os declarados em {ARQUIVO_DO_WORKFLOW.as_posix()}"
    return (
        f"{quantos} e NENHUM deles toca os `paths:` do {WORKFLOW_DO_DEPLOY} "
        f"({quais}) — ou seja, nenhum deploy novo vai nascer sozinho para "
        "carregar este merge ao ar. Repetir este run é a única saída "
        "(armadilhas/188)."
    )


def _pendencia_do_cancelado(fatos: Fatos, divergente: bool) -> str:
    """O que o mantenedor precisa saber — em linguagem de resultado.

    A primeira frase olha o `conclusion` desde a TAR-041: a divergência de
    histórico pode barrar tanto um cancelado quanto um `failure` por timeout, e
    escrever "foi CANCELADO antes de começar" sobre um run que RODOU e morreu no
    SSH mandaria o mantenedor procurar a doença errada.
    """
    site = (
        "o site continua no ar (a versão ANTIGA está servindo)"
        if fatos.site_http == 200
        else f"ATENÇÃO: a sonda do site respondeu {fatos.site_http} — confira o ar"
    )
    o_que_houve = (
        "foi CANCELADO antes de começar, não falhou"
        if fatos.conclusion == "cancelled"
        else "RODOU e morreu na conexão com a VPS (o timeout da porta 22)"
    )
    causa = (
        "o histórico divergiu do que está publicado, e repetir o deploy faria "
        "voltar uma versão mais velha — precisa de olho humano"
        if divergente
        else "o deploy foi cancelado repetidamente: a vaga de espera do canal "
        "de publicação é tomada por cada merge novo"
    )
    return (
        f"O deploy do run {fatos.run} {o_que_houve}: "
        f"{causa}. Enquanto isso, {site} — ninguém ficou fora do ar, mas o que "
        "foi mergeado ainda NÃO está em produção. "
        f"Tentativas feitas: {fatos.tentativas_feitas}."
    )


def _texto_da_pendencia(fatos: Fatos, permanente: bool) -> str:
    """O que o mantenedor precisa saber — em linguagem de resultado."""
    site = (
        "o site continua no ar (a versão ANTIGA está servindo)"
        if fatos.site_http == 200
        else f"ATENÇÃO: a sonda do site respondeu {fatos.site_http} — confira o ar"
    )
    causa = (
        "a VPS não está aceitando conexão na porta 22 — é configuração, e o "
        "conserto passa por você"
        if permanente
        else "a rede entre o GitHub e a VPS falhou repetidamente"
    )
    return (
        f"O deploy do run {fatos.run} não conseguiu subir a versão nova: {causa}. "
        f"Enquanto isso, {site} — ninguém ficou fora do ar, mas o que foi "
        "mergeado ainda NÃO está em produção. "
        f"Tentativas feitas: {fatos.tentativas_feitas}."
    )


# --------------------------------------------------------------- o mundo ----


def _rodar(comando: list[str], teto_s: int = 120) -> tuple[int, str]:
    try:
        proc = subprocess.run(
            comando, capture_output=True, text=True, timeout=teto_s,
            encoding="utf-8", errors="replace",
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as erro:
        raise ErroDeMedicao(f"{' '.join(comando[:3])}…: {erro}") from erro
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def dados_do_run(run: str) -> dict:
    """O veredito vem da fonte estruturada, nunca do exit de um pipe (045).

    `event` entra aqui porque é ele que separa as duas causas de cancelamento:
    `workflow_dispatch` é a armadilhas/173 (não se cura repetindo) e `push` é a
    armadilhas/188 (repetir é a cura). `headSha` é o que a ancestralidade mede.

    `workflowName` e `attempt` entraram na TAR-029, e nenhum dos dois é enfeite:
    o primeiro diz contra QUAL publicação medir (célula e infra publicam coisas
    diferentes) e o segundo é a única conta de tentativas que sobrevive ao fim
    do processo — sem ela, um gatilho automático repete para sempre.
    """
    codigo, saida = _rodar(
        ["gh", "run", "view", run, "--json",
         "status,conclusion,event,headSha,workflowName,attempt"]
    )
    if codigo != 0:
        raise ErroDeMedicao(f"gh run view {run} falhou: {saida.strip()[:200]}")
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeMedicao(f"resposta do gh não é JSON: {erro}") from erro
    if not isinstance(dados, dict):
        raise ErroDeMedicao(f"resposta do gh não é um objeto JSON: {saida[:120]}")
    return dados


def veredito_do_run(run: str) -> tuple[str, str]:
    dados = dados_do_run(run)
    return str(dados.get("status") or ""), str(dados.get("conclusion") or "")


def arquivo_do_workflow(nome: str, raiz: Path | None = None) -> Path:
    """O arquivo `.yml` cujo `name:` é `nome` — descoberto, nunca adivinhado.

    O `workflowName` de um run é o `name:` do topo do YAML, e nada garante que
    ele case com o nome do arquivo. Casar por convenção funcionaria hoje e
    quebraria calado no dia em que alguém renomeasse um dos dois — bem na hora
    em que a vacina precisa saber contra qual esteira medir. Zero ou mais de um
    candidato é ERRO de medição, jamais um palpite (INV-CI01, TAR-029).
    """
    raiz = raiz or raiz_do_repo()
    pasta = raiz / PASTA_DOS_WORKFLOWS
    achados = []
    for arquivo in sorted(pasta.glob("*.yml")) + sorted(pasta.glob("*.yaml")):
        try:
            texto = arquivo.read_text(encoding="utf-8")
        except OSError:
            continue
        casou = RE_NOME_DO_WORKFLOW.search(texto)
        if casou and casou.group("nome").strip("'\"") == nome:
            achados.append(arquivo)
    if len(achados) != 1:
        raise ErroDeMedicao(
            f"procurei em {PASTA_DOS_WORKFLOWS} o workflow chamado '{nome}' e "
            f"achei {len(achados)} — precisava de exatamente 1. Sem o arquivo "
            "não dá para ler os `paths:` do gatilho, e adivinhar a lista é pior "
            "que não saber."
        )
    return achados[0]


def sha_do_ultimo_deploy_verde(
    workflow: str = WORKFLOW_DO_DEPLOY, limite: int = RUNS_OLHADOS_ATRAS
) -> str:
    """Que SHA está publicado, segundo a única fonte que o CI alcança.

    NÃO se pergunta à VPS: o agente não tem SSH (Lei 5), e o harness bloqueia a
    tentativa. O Actions sabe qual foi o último run VERDE daquela esteira na
    `main`, e é esse `headSha` que está servindo.

    `workflow` é parâmetro e não constante DESDE A TAR-029, porque a resposta
    muda com a esteira: o último verde do `deploy-celula` não diz nada sobre o
    que o `deploy-infra` sincronizou, e vice-versa.
    """
    codigo, saida = _rodar(
        ["gh", "run", "list", "--workflow", workflow, "--branch", "main",
         "--limit", str(limite), "--json", "headSha,conclusion"]
    )
    if codigo != 0:
        raise ErroDeMedicao(f"gh run list falhou: {saida.strip()[:200]}")
    try:
        dados = json.loads(saida)
    except json.JSONDecodeError as erro:
        raise ErroDeMedicao(f"resposta do gh não é JSON: {erro}") from erro
    for item in dados if isinstance(dados, list) else []:
        if isinstance(item, dict) and item.get("conclusion") == "success":
            return str(item.get("headSha") or "")
    raise ErroDeMedicao(
        f"nenhum run VERDE de {workflow} entre os {limite} últimos da main — "
        "sem saber o que está publicado, não dá para dizer se um rerun avança"
    )


def e_ancestral(anterior: str, posterior: str) -> bool | None:
    """`anterior` é ancestral de (ou igual a) `posterior`? `None` = não medi.

    O exit 1 do `git merge-base --is-ancestor` é "provei que NÃO"; qualquer
    outro código é "não consegui medir" — commit ausente do checkout, clone
    raso (armadilhas/159). Confundir os dois transforma "não medi" em
    permissão para repetir, que é exatamente o rollback silencioso da 188.
    """
    try:
        codigo, _saida = _rodar(
            ["git", "merge-base", "--is-ancestor", anterior, posterior]
        )
    except ErroDeMedicao:
        return None
    if codigo == 0:
        return True
    if codigo == 1:
        return False
    return None


def _itens_em_bloco(texto: str) -> list[str]:
    """`paths:` seguido de `  - 'infra/...'` — a forma do `deploy-infra`.

    Lê só os itens MAIS RECUADOS que a chave, e para no primeiro que não é item
    de lista: assim um `paths:` no fim de um bloco `on:` não engole a chave
    seguinte (`permissions:`, `jobs:`) e transforma "não achei" em "achei
    lixo" — que seria pior, porque lixo decide sem levantar suspeita.
    """
    linhas = texto.splitlines()
    for indice, linha in enumerate(linhas):
        casou = RE_PATHS_EM_BLOCO.match(linha)
        if not casou:
            continue
        recuo = len(casou.group("recuo"))
        itens: list[str] = []
        for seguinte in linhas[indice + 1:]:
            if not seguinte.strip() or seguinte.lstrip().startswith("#"):
                continue
            if len(seguinte) - len(seguinte.lstrip()) <= recuo:
                break
            item = RE_ITEM_DE_LISTA.match(seguinte)
            if not item:
                break
            bruto = item.group("item").split("#", 1)[0].strip()
            if bruto:
                itens.append(bruto)
        if itens:
            return itens
    return []


def paths_do_deploy(
    raiz: Path | None = None, arquivo: Path | None = None
) -> tuple[str, ...]:
    """Os `paths:` do gatilho de uma esteira de deploy, LIDOS do workflow.

    Nenhum fato do projeto mora em dois lugares (CLAUDE.md). Se esta lista
    fosse uma constante copiada e alguém acrescentasse uma pasta ao gatilho, a
    vacina passaria a afirmar "nenhum deploy novo vai nascer" sobre um merge
    que nasce COM deploy — errado, e caro exatamente na hora em que se decide
    repetir ou não. Guarda: `ci/tests/test_rerun_de_deploy.py`.

    `arquivo` é parâmetro desde a TAR-029: o `deploy-infra` tem gatilho próprio
    (e escrito na forma EM BLOCO), e ler o do `deploy-celula` para decidir sobre
    ele responderia a pergunta de outro workflow.
    """
    raiz = raiz or raiz_do_repo()
    alvo = arquivo or (raiz / ARQUIVO_DO_WORKFLOW)
    rotulo = alvo.name
    try:
        texto = alvo.read_text(encoding="utf-8")
    except OSError as erro:
        raise ErroDeMedicao(f"não consegui ler {rotulo}: {erro}") from erro
    achado = RE_PATHS_DO_GATILHO.search(texto)
    if achado:
        brutos = [pedaco for pedaco in achado.group("lista").split(",")]
    else:
        brutos = _itens_em_bloco(texto)
    if not brutos:
        raise ErroDeMedicao(
            f"não achei a linha `paths:` em {rotulo} — o gatilho "
            "mudou de forma, e adivinhar a lista seria pior que não saber"
        )
    prefixos = []
    for pedaco in brutos:
        limpo = pedaco.strip().strip("'\"").strip()
        if limpo:
            prefixos.append(limpo.removesuffix("**").removesuffix("*"))
    if not prefixos:
        raise ErroDeMedicao(f"a linha `paths:` de {rotulo} está vazia")
    return tuple(prefixos)


def commits_que_ficam_de_fora(
    sha: str, ref: str = REF_DO_TOPO, raiz: Path | None = None,
    arquivo: Path | None = None,
) -> tuple[int | None, bool | None]:
    """Quantos commits de `ref` o rerun deixa de fora, e se algum dispara deploy.

    Um rerun publica o SHA DAQUELE run, não o topo da `main`. Isto não decide
    nada — informa o agente sobre a única coisa que ele não veria sozinho: se
    NENHUM dos commits de fora toca os `paths:` do deploy, nenhum deploy novo
    vai nascer, e repetir deixa de ser opção para virar a única saída (188).
    """
    codigo, saida = _rodar(["git", "rev-list", "--count", f"{sha}..{ref}"])
    if codigo != 0:
        return None, None
    linhas = [linha.strip() for linha in saida.splitlines() if linha.strip()]
    try:
        quantos = int(linhas[-1])
    except (IndexError, ValueError):
        return None, None
    if quantos == 0:
        return 0, False
    try:
        prefixos = paths_do_deploy(raiz, arquivo)
    except ErroDeMedicao:
        return quantos, None
    # `git log --name-only` (e não `git diff --name-only`): o diff mostra só o
    # DESTINO de um rename e cegaria a conta (armadilhas/174).
    codigo, saida = _rodar(["git", "log", "--format=", "--name-only", f"{sha}..{ref}"])
    if codigo != 0:
        return quantos, None
    tocados = [linha.strip() for linha in saida.splitlines() if linha.strip()]
    toca = any(caminho.startswith(prefixos) for caminho in tocados)
    return quantos, toca


def log_da_falha(run: str) -> str:
    _codigo, saida = _rodar(["gh", "run", "view", run, "--log-failed"], teto_s=180)
    return saida  # exit != 0 é normal aqui: o run falhou


# `porta_22_responde` e `http_do_site` moraram aqui até 30/08/2026 (TAR-013).
# Hoje vêm de `ci/sonda_da_vps.py`, que é a MESMA medição que o deploy passou a
# fazer de dentro do runner — ver o comentário do import, no topo.


def escrever_saida_do_passo(decisao: Decisao) -> None:
    """`acao=`, `codigo=` e `alarmar=` em `$GITHUB_OUTPUT` — o canal do workflow.

    O MESMO desenho de `ci/sonda_da_vps.py::_escrever_saida_do_passo`, e pela
    MESMA razão (TAR-041): o workflow precisa distinguir mais respostas do que
    um código de saída carrega. Até aqui ele lia só `codigo != 0` para decidir
    se abria a issue, e isso bastava porque o gatilho só via cancelamento —
    todo desfecho não-zero ali era um merge invisível fora do ar. Com o
    `failure` no gatilho, `codigo != 0` passou a incluir o deploy que falhou
    por DEFEITO DE CÓDIGO, que já está vermelho e já tem dono.

    O código de saída continua sendo o veredito [INV-CI01] e não muda de
    sentido: 0 PASS · 1 FAIL · 2 ERROR. `alarmar` é uma pergunta DIFERENTE — "e
    isto precisa acordar alguém?" — e ela ganha um canal próprio em vez de
    torcer o significado do exit code, que é como um contrato apodrece.

    Falha de escrita NÃO derruba nada: fora do Actions a variável não existe, e
    a vacina precisa continuar rodando na mão, do PC.
    """
    caminho = os.environ.get("GITHUB_OUTPUT")
    if not caminho:
        return
    try:
        with open(caminho, "a", encoding="utf-8") as arquivo:
            arquivo.write(f"acao={decisao.acao}\n")
            arquivo.write(f"codigo={decisao.codigo}\n")
            arquivo.write(
                "alarmar="
                + ("true" if decisao.codigo != 0 and decisao.precisa_de_alarme
                   else "false")
                + "\n"
            )
    except OSError as erro:
        print(f"(não consegui escrever em GITHUB_OUTPUT: {erro})", file=sys.stderr)


def ultimo_run(workflow: str = "deploy-celula.yml") -> str:
    codigo, saida = _rodar(
        ["gh", "run", "list", "--workflow", workflow, "--limit", "1",
         "--json", "databaseId"]
    )
    if codigo != 0:
        raise ErroDeMedicao(f"gh run list falhou: {saida.strip()[:200]}")
    dados = json.loads(saida)
    if not dados:
        raise ErroDeMedicao(f"nenhum run de {workflow} encontrado")
    return str(dados[0]["databaseId"])


def tentativas_ja_feitas(dados: dict, em_memoria: int) -> int:
    """A conta de tentativas que SOBREVIVE ao fim do processo (TAR-029).

    `attempt` é 1 no run original e sobe a cada rerun — é a conta que o próprio
    GitHub guarda, e a única que continua valendo quando quem chama a vacina é
    um gatilho: cada cancelamento acorda um processo NOVO, com o contador de
    memória em zero. Sem este piso, `MAXIMO_DE_TENTATIVAS` viraria decoração
    exatamente no modo de uso em que ela mais importa (vacina → rerun →
    cancelado → vacina, sem fim).

    Piso, e não substituição: dentro de uma execução o laço conta as suas
    próprias voltas, e o maior dos dois é o que a regra de parada enxerga.
    """
    bruto = dados.get("attempt")
    try:
        attempt = int(bruto)
    except (TypeError, ValueError):
        return em_memoria
    return max(em_memoria, attempt - 1) if attempt >= 1 else em_memoria


def colher(run: str, host: str, tentativas: int) -> Fatos:
    dados = dados_do_run(run)
    status = str(dados.get("status") or "")
    conclusion = str(dados.get("conclusion") or "")
    fatos = Fatos(run=run, status=status, conclusion=conclusion,
                  event=str(dados.get("event") or ""),
                  head_sha=str(dados.get("headSha") or ""),
                  workflow=str(dados.get("workflowName") or ""),
                  tentativas_feitas=tentativas_ja_feitas(dados, tentativas))
    if status != "completed":
        return fatos
    if conclusion == "cancelled":
        _colher_a_ancestralidade(fatos)
    elif conclusion not in ("success", "skipped"):
        log = log_da_falha(run)
        fatos.tem_timeout_ssh = bool(RE_TIMEOUT_SSH.search(log))
        fatos.tem_falha_de_autenticacao = bool(RE_SSH_AUTENTICACAO.search(log))
        if fatos.tem_timeout_ssh:
            try:
                fatos.porta22_viva = porta_22_responde(host)
            except Exception:
                fatos.porta22_viva = None
            fatos.site_http = http_do_site()
            # SÓ QUANDO É A 127 (TAR-041). A ancestralidade custa um `gh run
            # list`, um `git fetch` e dois `merge-base`; gastar isso num deploy
            # que morreu por defeito de código seria pagar rede para responder
            # uma pergunta cuja decisão já está tomada duas linhas acima.
            _colher_a_ancestralidade(fatos)
    return fatos


def _colher_a_ancestralidade(fatos: Fatos) -> None:
    """As medidas que a armadilhas/188 exige — todas fora da VPS (Lei 5).

    Só faz sentido para o deploy de PUSH: no disparo manual a decisão já está
    tomada pelo `event`, e medir ancestralidade ali seria gastar rede para
    responder uma pergunta que ninguém fez.

    Chamada pelos DOIS caminhos desde a TAR-041 — o cancelado (188) e o
    `failure` por timeout da porta 22 (127) —, porque a pergunta que ela
    responde é a mesma nos dois: *repetir este run avança ou faz voltar?*
    """
    if fatos.event != "push" or not fatos.head_sha or not fatos.workflow:
        return
    # O `origin/main` local envelhece em silêncio (armadilhas/148). Melhor
    # esforço: se o fetch falhar, a conta abaixo devolve None e vira "não medi".
    try:
        _rodar(["git", "fetch", "origin", "main", "--quiet"], teto_s=120)
    except ErroDeMedicao:
        pass
    # A ESTEIRA DO RUN, não uma constante (TAR-029): perguntar ao
    # `deploy-celula` o que o `deploy-infra` publicou devolve a resposta de
    # outra pergunta, e ela chega com cara de certeza.
    arquivo: Path | None = None
    try:
        arquivo = arquivo_do_workflow(fatos.workflow)
    except ErroDeMedicao:
        arquivo = None
    try:
        fatos.sha_publicado = sha_do_ultimo_deploy_verde(
            arquivo.name if arquivo else fatos.workflow
        )
    except ErroDeMedicao:
        fatos.sha_publicado = ""
    fatos.site_http = http_do_site()
    if not fatos.sha_publicado:
        return
    fatos.publicado_e_ancestral = e_ancestral(fatos.sha_publicado, fatos.head_sha)
    fatos.head_ja_publicado = e_ancestral(fatos.head_sha, fatos.sha_publicado)
    fatos.commits_de_fora, fatos.commits_de_fora_tocam_o_deploy = (
        commits_que_ficam_de_fora(fatos.head_sha, arquivo=arquivo)
    )


def esperar_o_run(run: str, teto_min: int) -> str:
    """Espera com TETO e com VOZ — espera muda é a armadilhas/161."""
    limite = time.time() + teto_min * 60
    while time.time() < limite:
        status, conclusion = veredito_do_run(run)
        if status == "completed":
            return conclusion
        restam = int((limite - time.time()) / 60)
        print(f"   … o run {run} ainda roda (restam ~{restam} min de teto)",
              flush=True)
        time.sleep(INTERVALO_DE_CONFERENCIA_S)
    raise ErroDeMedicao(
        f"o run {run} não terminou em {teto_min} min — parei de esperar e "
        "não vou adivinhar o resultado"
    )


def main(argv: list[str] | None = None) -> int:
    configurar_saida()
    parser = argparse.ArgumentParser(
        description="Cuida do deploy que não chegou ao ar: recusado pela VPS "
                    "(armadilhas/127) ou cancelado por push (armadilhas/188)."
    )
    alvo = parser.add_mutually_exclusive_group(required=True)
    alvo.add_argument("--run", help="id do run de deploy")
    alvo.add_argument("--ultimo", action="store_true",
                      help="o último run da esteira de --workflow")
    parser.add_argument("--workflow", default=WORKFLOW_DO_DEPLOY,
                        help="a esteira de --ultimo (padrão: deploy-celula.yml)."
                             " Com --run, a esteira é lida do próprio run.")
    parser.add_argument("--host", default=VPS_PADRAO)
    parser.add_argument("--teto", type=int, default=TETO_PADRAO_MIN)
    parser.add_argument("--so-diagnosticar", action="store_true",
                        help="decide e explica, mas não repete nada")
    args = parser.parse_args(argv)

    try:
        run = args.run or ultimo_run(args.workflow)
        tentativas = 0
        while True:
            fatos = colher(run, args.host, tentativas)
            decisao = decidir(fatos)
            print(f"\nrun {run}: esteira={fatos.workflow or '?'}"
                  f" · status={fatos.status} conclusion={fatos.conclusion}"
                  f" · tentativas={fatos.tentativas_feitas}"
                  f" · event={fatos.event or '?'}"
                  f" · timeout-ssh={fatos.tem_timeout_ssh}"
                  f" · porta22={fatos.porta22_viva} · site={fatos.site_http}")
            if fatos.conclusion == "cancelled" and fatos.event == "push":
                print(f"   armadilhas/188: publicado={_curto(fatos.sha_publicado)}"
                      f" · run={_curto(fatos.head_sha)}"
                      f" · publicado-é-ancestral={fatos.publicado_e_ancestral}"
                      f" · já-no-ar={fatos.head_ja_publicado}"
                      f" · ficam de fora={fatos.commits_de_fora}"
                      f" (tocam o deploy: {fatos.commits_de_fora_tocam_o_deploy})")
            print(f"{decisao.acao.upper()}: {decisao.motivo}")
            if decisao.recado:
                print(f"   ↳ {decisao.recado}")

            if decisao.acao != "repetir" or args.so_diagnosticar:
                if args.so_diagnosticar and decisao.acao == "repetir":
                    print("(--so-diagnosticar: não repeti nada)")
                if decisao.pendencia:
                    print("\n--- para o livro (registro de pendência) ---")
                    print(decisao.pendencia)
                escrever_saida_do_passo(decisao)
                print(f"\nRESULTADO  {'PASS' if decisao.codigo == 0 else 'FAIL'}"
                      if decisao.codigo != 2 else "\nRESULTADO  ERROR")
                return decisao.codigo

            if tentativas >= 1:
                print(f"   pausa de {PAUSA_ENTRE_TENTATIVAS_S}s antes da próxima "
                      "(reruns emendados batem na mesma janela ruim)", flush=True)
                time.sleep(PAUSA_ENTRE_TENTATIVAS_S)

            tentativas += 1
            print(f"   repetindo o deploy (tentativa {tentativas} de "
                  f"{MAXIMO_DE_TENTATIVAS})…", flush=True)
            # Run CANCELADO não tem job falhado: `--failed` não teria o que
            # repetir. Quem decide isso é a tabela, não este laço (188).
            comando = ["gh", "run", "rerun", run]
            if decisao.rerun_apenas_falhados:
                comando.append("--failed")
            codigo, saida = _rodar(comando)
            if codigo != 0:
                raise ErroDeMedicao(f"gh run rerun falhou: {saida.strip()[:200]}")
            time.sleep(INTERVALO_DE_CONFERENCIA_S)
            conclusion = esperar_o_run(run, args.teto)
            if conclusion == "success":
                site = http_do_site()
                print(f"\n✅ o deploy do run {run} FICOU VERDE na tentativa "
                      f"{tentativas} — a versão nova subiu. Sonda do site: {site}.")
                escrever_saida_do_passo(
                    Decisao("nada", 0, "o rerun subiu", precisa_de_alarme=False)
                )
                print("RESULTADO  PASS")
                return 0
    except ErroDeMedicao as erro:
        # ERROR SEMPRE ALARMA: "não consegui medir" é o desfecho em que ninguém
        # mais vai olhar, e é exatamente onde o INV-CI01 manda ser barulhento.
        escrever_saida_do_passo(Decisao("nada", 2, str(erro)))
        print(f"\n🧱 PAROU POR SEGURANÇA: {erro}\n"
              "'Não consegui medir' nunca vira 'deu certo' (INV-CI01).",
              file=sys.stderr)
        print("RESULTADO  ERROR", file=sys.stderr)
        return 2
    except Exception as erro:  # pragma: no cover - rede/ambiente
        escrever_saida_do_passo(Decisao("nada", 2, str(erro)))
        print(f"\n🧱 PAROU POR SEGURANÇA: erro inesperado "
              f"({erro.__class__.__name__}: {erro})", file=sys.stderr)
        print("RESULTADO  ERROR", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
