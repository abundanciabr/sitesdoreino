# apps/core/pendencias.py — a Central de Pendências
"""`/admin/pendencias/` — a portaria: tudo que espera pelo mantenedor, numa tela.

Plano aprovado: `documentos/pendencias-e-conferencia-por-pares.md`, degrau 1.

## O problema, medido

Em 06/09/2026 o mantenedor abriu `/conquistas/interno` e disse *"que eu nem
sabia que isso existia"*. Não era memória fraca: era desenho. O trabalho que
espera por ele mora em SEIS endereços diferentes, nenhum deles avisa nada, e
uma fila que alguém precisa lembrar de abrir é uma fila que não existe.

Esta tela não resolve nada por dentro, e isso é a decisão central: cada fila
continua morando na própria casa, que é onde a regra dela é conferida. Aqui só
se pergunta *"quantos estão esperando aí, e o mais antigo é de quando?"*, e se
oferece a porta.

## Duas filas neste degrau, e a tela DIZ que são duas

O degrau 1 traz só o que esta célula já sabe perguntar hoje, sem credencial
nova nenhuma: quem quer entrar na escola e as decisões paradas no painel do
sistema. As outras três (portfólios, marcos, laudos) chegam no degrau 3.

Eram TRÊS até 06/09/2026: a terceira era "ideias esperando a sua assinatura",
e ela saiu no dia em que o mantenedor mandou tirar a assinatura de obra da
Caixa. Uma ideia em "Planejado" não espera mais por ninguém — ela já pode
começar —, e uma linha que mostrasse 0 para sempre é exatamente o tipo de
ruído que ensina alguém a ignorar esta tela.

Uma portaria que enxerga metade das filas e não avisa é pior que portaria
nenhuma: ela ensina o mantenedor a confiar num "nada esperando você" que não é
verdade. Por isso `FILAS_QUE_AINDA_NAO_VEJO` existe e vai para a tela.

## "Não consegui perguntar" NUNCA vira zero

É a regra mais dura deste arquivo, e a única cujo custo se mede em pessoas: um
zero na linha de quem quer entrar faria o mantenedor concluir que ninguém está
esperando aprovação, e deixar nove pessoas de fora por causa de um tempo
estourado na rede. Um "não sei" mostrado como 0 é o falso-verde de produto da
`RETROSPECTIVA-FASE-D.md` §1, e a célula inteira já o paga com `None`
(`views.contar_a_escola` e `AlunosClient`).

Aqui `Fila.quantidade is None` significa *não consegui perguntar*, e o template
tem de distinguir os dois casos por listas separadas, nunca por um `{% if %}`
cru: zero é falso em template, e um zero legítimo cairia no ramo do "não sei".

## Fail-OPEN por linha, e não pela página

A fila que não responde perde a própria linha, e as outras duas continuam
valendo. Uma tela de operação que não abre é inútil justamente no dia em que
alguém precisa dela.

## O número do painel não se recalcula aqui, e isso é lei

"Quantas decisões estão paradas" é uma REGRA (`precisa_do_dono: true` sem um
registro que responda), e ela mora em `painel/logica.js::caixaDeEntrada`, a
mesma função que desenha a caixa "Precisa de você" na tela dele. Escrever essa
regra de novo em Python já custou uma divergência medida nesta casa: o Python
dizia 6 e o painel dizia 7 (`ci/metricas_da_fabrica.py::pedidos_ao_dono` conta
o episódio inteiro).

A imagem desta célula não tem Node. Então quem conta é o gerador do painel, no
deploy, e aqui só se LÊ o número que ele carimbou em `painel.html`, os mesmos
bytes que `apps/core/painel.py` já serve. Uma conta, um lugar.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone as tz

from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .caixa import _dias
from .clients import AlunosClient
from .painel import diretorio_do_painel

# O carimbo que o gerador do painel deixa na página, em forma rígida e numa
# linha só (`painel/gerar_manifesto.js`). Ler por padrão, em vez de executar o
# JavaScript, é o que permite a esta célula viver sem Node. Guarda dos dois
# lados: `painel/testes/teste_gerador.js` prova que o carimbo é a fila de
# verdade, e `tests/test_central_de_pendencias.py` prova que este padrão casa
# com a página REAL que o gerador produz.
_CARIMBO_DA_FILA = re.compile(
    r'pedidosDoDono: \{ quantidade: (\d+), maisAntigoQuando: (null|"[^"]*") \}'
)

# As filas que este degrau ainda NÃO enxerga, com o endereço de cada uma. Elas
# entram na tela por escrito: sem isso, "nada esperando você" seria uma frase
# que a tela não tem como sustentar. Saem daqui uma a uma no degrau 3, e a
# lista vazia é o sinal de que a portaria ficou completa.
FILAS_QUE_AINDA_NAO_VEJO = (
    ("Portfólios pedindo conferência", "/pages/equipe"),
    ("Provas de marco enviadas pelos alunos", "/conquistas/interno"),
    ("Checkpoints de aula esperando laudo", "/cursos/plantao"),
)


# A Central lê o cadastro publicado, em vez de repetir quem responde por cada
# processo. Sem o cadastro, a tela confessa a falha e não atribui trabalho por
# suposição.
FUNCOES_DA_CENTRAL = (
    "estrategia-conteudo",
    "operacoes-trafego",
    "ensino-comunidade",
    "comercial-relacionamento",
)

DESTINOS_DAS_FUNCOES = {
    "estrategia-conteudo": ("placar", "Ver o placar e preparar a revisão semanal."),
    "operacoes-trafego": ("painel", "Ver os pedidos e incidentes do sistema."),
    "ensino-comunidade": ("escola", "Abrir a operação da escola."),
    "comercial-relacionamento": (
        "escola_alunos",
        "Abrir pessoas aguardando acesso e acompanhar o desfecho.",
    ),
}

LACUNAS_DO_ENSINO = (
    "A fonte ainda não oferece uma lista de portfólios para conferir.",
    "A fonte de marcos ainda não tem contrato de leitura para a Central.",
    "A fonte ainda não oferece uma lista de checkpoints esperando laudo.",
)


@dataclass(frozen=True)
class Fila:
    """Uma linha da portaria.

    `quantidade is None` é *não consegui perguntar*, e nunca zero. `espera_ha`
    é em dias, e só existe quando há alguém esperando de verdade.
    """

    titulo: str
    quantidade: "int | None"
    espera_ha: "int | None"
    href: str
    o_que_e: str
    onde_mora: str


@dataclass(frozen=True)
class VisaoDeResponsabilidade:
    """Uma das quatro leituras da Central, sem virar uma segunda fila."""

    nome: str
    pessoa: str
    fontes: tuple[str, ...]
    aprovacoes: tuple[str, ...]
    destino: str
    destino_texto: str
    fila_de_hoje: "Fila | None"
    lacunas: tuple[str, ...]


def _cadastro_de_responsabilidades() -> dict | None:
    """Lê a publicação versionada das responsabilidades, ou confessa a falta."""
    pasta = diretorio_do_painel()
    arquivo = pasta / "responsabilidades.json" if pasta is not None else None
    if arquivo is None or not arquivo.is_file():
        return None
    try:
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(dados, dict):
        return None
    funcoes = dados.get("funcoes")
    unidades = dados.get("unidades")
    if not isinstance(funcoes, dict) or not isinstance(unidades, list):
        return None
    return dados


def visoes_de_responsabilidade(
    fila_de_entrada: Fila,
) -> tuple[VisaoDeResponsabilidade, ...] | None:
    """Monta as quatro visões a partir do cadastro, sem inferir titularidade.

    Hoje só a fila de entrada possui uma leitura que permite contar trabalho
    individualmente. As outras fontes continuam declaradas no cartão da função
    para que a ausência de integração não pareça uma fila vazia.
    """
    cadastro = _cadastro_de_responsabilidades()
    if cadastro is None:
        return None
    funcoes = cadastro["funcoes"]
    unidades = cadastro["unidades"]
    visoes = []
    for chave in FUNCOES_DA_CENTRAL:
        funcao = funcoes.get(chave)
        destino = DESTINOS_DAS_FUNCOES.get(chave)
        if not isinstance(funcao, dict) or destino is None:
            return None
        nome = funcao.get("nome")
        pessoa = funcao.get("pessoa")
        if not isinstance(nome, str) or not isinstance(pessoa, str):
            return None
        unidades_da_funcao = [
            unidade
            for unidade in unidades
            if isinstance(unidade, dict) and unidade.get("titular_funcao") == chave
        ]
        fontes = tuple(
            fonte
            for unidade in unidades_da_funcao
            if isinstance((fonte := unidade.get("fonte")), str)
        )
        aprovacoes = tuple(
            finalidade
            for unidade in unidades_da_funcao
            if unidade.get("aprova") == nome
            and isinstance((finalidade := unidade.get("finalidade")), str)
        )
        visoes.append(
            VisaoDeResponsabilidade(
                nome=nome,
                pessoa=pessoa,
                fontes=fontes,
                aprovacoes=aprovacoes,
                destino=reverse(destino[0]),
                destino_texto=destino[1],
                fila_de_hoje=(
                    fila_de_entrada if chave == "comercial-relacionamento" else None
                ),
                lacunas=LACUNAS_DO_ENSINO if chave == "ensino-comunidade" else (),
            )
        )
    return tuple(visoes)


def _mais_antiga(datas: list, agora: datetime) -> "int | None":
    """Há quantos dias espera o mais velho da lista, ou `None` se ela é vazia.

    Reusa `caixa._dias`, que já resolve as duas bordas que mordem aqui: data
    sem fuso (comparar um instante ingênuo com um consciente estoura
    `TypeError` e derrubaria a página inteira por causa de um campo mal
    formado) e data no futuro, que acontece de verdade quando um relógio está
    fora de hora.
    """
    dias = [_dias(quando, agora) for quando in datas if quando]
    return max(dias) if dias else None


def quem_quer_entrar(cliente: AlunosClient, agora: datetime) -> Fila:
    """Quem pediu para entrar na escola e ainda não teve resposta.

    A `alunos` já conta há quantos dias cada pessoa espera
    (`esperando_ha_dias`, do contrato), e este módulo não reconta: a idade é
    dela, que é quem tem a data de verdade.
    """
    fila = cliente.fila("aguardando")
    return Fila(
        titulo="Pessoas querendo entrar na escola",
        quantidade=None if fila is None else len(fila),
        espera_ha=(
            max((p.get("esperando_ha_dias") or 0) for p in fila) if fila else None
        ),
        href=reverse("escola_alunos"),
        o_que_e="Alguém pediu entrada e fica sem acesso a nada até você liberar.",
        onde_mora="a lista de alunos",
    )


def decisoes_paradas_no_painel(agora: datetime) -> Fila:
    """As decisões que os robôs pediram a você e ninguém respondeu.

    Lida do carimbo que o gerador do painel deixa em `painel.html`. O porquê de
    a conta não ser refeita aqui está no cabeçalho deste arquivo.

    Sem painel na imagem, ou com uma página que este padrão não reconhece, a
    linha diz "não consegui perguntar" em vez de zero. Um zero aqui afirmaria
    que ele está em dia com os robôs, que é o contrário do que se sabe.
    """
    pasta = diretorio_do_painel()
    achado = None
    if pasta is not None:
        achado = _CARIMBO_DA_FILA.search(
            (pasta / "painel.html").read_text(encoding="utf-8")
        )
    mais_antigo = achado.group(2).strip('"') if achado else "null"
    return Fila(
        titulo="Decisões suas paradas no painel do sistema",
        quantidade=int(achado.group(1)) if achado else None,
        espera_ha=(
            _mais_antiga([mais_antigo], agora) if mais_antigo != "null" else None
        ),
        href=reverse("painel"),
        o_que_e=(
            "Perguntas que os robôs fizeram a você durante a construção da "
            "plataforma e ficaram sem resposta. Cada uma trava alguma coisa."
        ),
        onde_mora="o painel do sistema",
    )


@require_GET
def pendencias(request):
    """A portaria. Abre sempre, mesmo com as duas filas mudas."""
    agora = datetime.now(tz.utc)
    fila_de_entrada = quem_quer_entrar(AlunosClient(), agora)
    filas = [fila_de_entrada, decisoes_paradas_no_painel(agora)]
    esperando = [f for f in filas if f.quantidade]
    return render(
        request,
        "admin/pendencias.html",
        {
            "admin": request.admin,
            "esperando": esperando,
            # Vazias e mudas viajam separadas porque são frases diferentes na
            # tela: "não há nada aqui" e "não deu para perguntar" só se parecem
            # de dentro do código.
            "vazias": [f for f in filas if f.quantidade == 0],
            "mudas": [f for f in filas if f.quantidade is None],
            "total": sum(f.quantidade for f in esperando),
            # `any`, e não `all`: com UMA fila muda o total já é um piso, e
            # apresentá-lo como conta fechada seria a mesma mentira do zero.
            "total_e_um_piso": any(f.quantidade is None for f in filas),
            "ainda_nao_vejo": FILAS_QUE_AINDA_NAO_VEJO,
            "visoes": visoes_de_responsabilidade(fila_de_entrada),
        },
    )
