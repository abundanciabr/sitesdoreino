# apps/gamificacao/criterios.py
"""O motor de critérios: as medalhas que a escola concede sozinha.

O marco real se PEDE (o aluno manda a prova, a equipe confere — `validacao.py`).
A medalha, não: ela cai quando a conta bate. Este arquivo é quem faz a conta.

**NÃO É UM MOTOR DE REGRAS, e a diferença é o critério de morte nº 1 da lei**
(`DECISAO-gamificacao.md` §10): *"a célula virar motor de regras genérico ou
ganhar uma DSL"* obriga a parar e reabrir a decisão com o mantenedor. Aqui não há
expressão, não há operador, não há campo livre: há um `dict` de funções, uma por
palavra de `CRITERIOS_ACEITOS`, e uma palavra que não estiver nele não é
avaliada. Acrescentar um critério é escrever uma função e acrescentar a palavra —
um diff que aparece. Se o que faltar um dia for uma EXPRESSÃO, pare.

**Ligar uma medalha RECONHECE quem já cumpriu**, e isso é decisão do mantenedor
no Rito de Contrato de 01/09/2026. É por isso que a avaliação olha o ESTADO
atual da pessoa (quanto XP ela tem, quantas medalhas de ofício já ganhou) e não
um fluxo de acontecimentos desde o clique. Quem já tinha 500 XP quando a medalha
dos 300 foi ligada a recebe na primeira vez em que o motor rodar para ela.

O QUE ESTE ARQUIVO CONSEGUE ALIMENTAR HOJE, MEDIDO E NÃO SUPOSTO
-----------------------------------------------------------------
Quatro dos nove critérios têm dado de verdade por trás: `xp_acumulado`,
`nivel_alcancado`, `conquistas_da_familia` e — desde 01/09/2026, quando o fórum
ganhou voz — `respostas_aceitas`. Os outros leem tabelas que **nenhum código
desta plataforma escreve ainda** — uma varredura por `.objects.create` em
`services/gamificacao` não acha ninguém criando `Forja`, `Sequencia` ou
`ProgressoDeMissao`.

Isso não é defeito deste arquivo e não se conserta aqui: é a escada ainda não ter
chegado nesses degraus. O que ele faz é ler a tabela de verdade e devolver o que
ela diz — zero, quando ela está vazia. **A tela do mantenedor avisa isso antes do
clique** (`interruptores.impedimentos_da_conquista`), para ligar uma medalha e
não ver nada acontecer nunca parecer defeito da tela.

E vale dizer em voz alta o que a medição significa para as QUATRO medalhas que a
escola tem semeadas hoje: nenhuma delas dispara. `fundador` é manual;
`primeira-obra` espera uma obra que o sistema ainda não sabe registrar;
`dez-forjas` espera a Forja. `mao-amiga` DEIXOU essa lista em 01/09/2026: com o
fórum falando, ela é a primeira medalha automática que a escola consegue
conceder de verdade.
"""

from __future__ import annotations

import logging
import threading

from .models import (
    AjudaAceita,
    Concessao,
    ConquistaDefinicao,
    Forja,
    PerfilJogador,
    Pessoa,
    ProgressoDeMissao,
    Sequencia,
)

logger = logging.getLogger(__name__)

# O estado de "já estou avaliando", por thread. Conceder uma medalha credita XP,
# creditar XP recalcula o perfil, e recalcular chama a avaliação de novo: sem
# esta trava, a primeira medalha que pagasse pontos entraria numa recursão. A
# saída não é proibir a cadeia (ela é legítima — uma medalha PODE destravar a
# seguinte), e sim resolvê-la no LAÇO de quem começou, uma rodada por vez.
_reentrancia = threading.local()


def _valor_xp(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    return perfil.xp_total


def _valor_nivel(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    return perfil.nivel


def _valor_semanas(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    """Semanas fechadas na Sequência. A tabela existe e ninguém a escreve (degrau 10)."""
    linha = Sequencia.objects.filter(pessoa=pessoa, site_id=site_id).first()
    return linha.semanas if linha else 0


def _valor_missoes(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    """Missões cumpridas. A tabela existe e ninguém a escreve (degrau 11)."""
    return ProgressoDeMissao.objects.filter(
        pessoa=pessoa, site_id=site_id, cumprida=True
    ).count()


def _valor_forjas(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    """Peças seladas no medidor de esforço. A Forja é o degrau 14."""
    return Forja.objects.filter(
        pessoa=pessoa, site_id=site_id, selada_em__isnull=False
    ).count()


def _valor_respostas(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    """Respostas aceitas no fórum. Passou a contar de verdade em 01/09/2026.

    **Conta `AjudaAceita`, e não o ledger de XP**, e a diferença é a que importa:
    a medalha não pode depender de a regra de pontuação estar LIGADA.
    Reconhecimento é uma coisa, pagamento é outra — se contasse pelo ledger, o
    mantenedor desligaria a regra por uma semana e a medalha pararia de existir
    junto, sem ninguém entender por quê.

    A linha é idempotente pela MENSAGEM: marcar, desmarcar e remarcar conta uma
    vez só.
    """
    return AjudaAceita.objects.filter(pessoa=pessoa, site_id=site_id).count()


def _valor_primeira_vez(pessoa: Pessoa, site_id: str, perfil: PerfilJogador) -> int:
    """A estreia num assunto (a primeira obra, o primeiro quiz).

    Mesmo caso do de cima, e pela mesma razão: a plataforma ainda não afirma "uma
    obra ficou pronta" em lugar nenhum. A galeria é o degrau 19. Devolver 0 aqui
    é a resposta honesta; devolver 1 porque a pessoa tem XP seria confundir
    "fez alguma coisa" com "terminou a primeira peça dela".
    """
    return 0


def _valor_familia(
    pessoa: Pessoa, site_id: str, perfil: PerfilJogador, familia: str = ""
) -> int:
    """Quantas conquistas de uma família esta pessoa já tem. Funciona HOJE."""
    if not familia:
        return 0
    return Concessao.objects.filter(
        pessoa=pessoa, site_id=site_id, conquista__familia=familia
    ).count()


# O VOCABULÁRIO, ligado uma palavra a uma função. É o oposto de uma DSL: a lista
# inteira se lê em cinco segundos, e o que não está aqui não é avaliado.
#
# `manual` não aparece de propósito — uma medalha manual não tem conta nenhuma
# para bater, e é a equipe que a concede. Deixá-la fora é o que garante que o
# motor nunca conceda o Fundador a alguém por engano.
CONTAS = {
    "xp_acumulado": _valor_xp,
    "nivel_alcancado": _valor_nivel,
    "semanas_de_sequencia": _valor_semanas,
    "missoes_cumpridas": _valor_missoes,
    "forjas_seladas": _valor_forjas,
    "respostas_aceitas": _valor_respostas,
    "primeira_vez": _valor_primeira_vez,
    "conquistas_da_familia": _valor_familia,
}


def cumpre(
    conquista: ConquistaDefinicao, pessoa: Pessoa, site_id: str, perfil: PerfilJogador
) -> bool:
    """Esta pessoa alcançou o critério desta conquista?

    Critério fora do vocabulário devolve `False` com aviso no log, nunca exceção:
    o `save()` da `ConquistaDefinicao` já recusa uma palavra desconhecida na
    porta de entrada, então chegar aqui significaria uma linha gravada antes
    daquela trava existir. Fail-closed é não conceder.
    """
    criterio = conquista.criterio or {}
    tipo = criterio.get("tipo", "manual")
    conta = CONTAS.get(tipo)
    if conta is None:
        if tipo != "manual":
            logger.warning(
                "conquista %s tem critério %r fora do vocabulário: não concedo",
                conquista.slug,
                tipo,
            )
        return False

    alvo = int(criterio.get("alvo") or 1)
    if tipo == "conquistas_da_familia":
        valor = conta(pessoa, site_id, perfil, criterio.get("familia", ""))
    else:
        valor = conta(pessoa, site_id, perfil)
    return valor >= alvo


def avaliar(pessoa_id: str, site_id: str) -> list[Concessao]:
    """Concede tudo o que esta pessoa passou a cumprir. Devolve o que foi novo.

    **É um LAÇO, e não uma passada**, porque uma medalha pode destravar a
    seguinte: ganhar a de ofício paga XP, o XP sobe o nível, e o nível pode
    alcançar outra medalha. O laço termina sozinho — cada conquista é única por
    pessoa (`Unique(pessoa, conquista)`), então há um teto natural igual ao
    número de conquistas ativas da escola.

    **Reentrância bloqueada:** conceder chama `recalcular`, que chama esta função
    de novo. A chamada de dentro devolve lista vazia na hora; quem resolve tudo é
    o laço de fora, que roda outra rodada e enxerga o estado já atualizado.
    """

    if getattr(_reentrancia, "dentro", False):
        return []

    # Import tardio, e ele é deliberado: `validacao` importa `motor`, que importa
    # este arquivo. Trazer `conceder` no topo fecharia o ciclo e quebraria o
    # carregamento da célula. O ciclo em si é honesto — conceder É parte de
    # avaliar —, e o import dentro da função é a forma padrão de expressá-lo.
    from .validacao import conceder

    _reentrancia.dentro = True
    concedidas: list[Concessao] = []
    try:
        for _ in range(len(CONTAS) + 1):  # teto de segurança, nunca alcançado
            pessoa = Pessoa.objects.filter(id_da_plataforma=pessoa_id).first()
            if pessoa is None:
                break
            # O PERFIL NASCE AO SER OLHADO, e aqui isso deixou de ser detalhe em
            # 01/09/2026: com o fórum falando, existe gente que AJUDOU e nunca
            # ganhou XP nenhum — a regra de pontuação pode estar desligada. Com
            # um `filter().first()`, essa pessoa não tinha perfil, não era
            # avaliada, e a medalha "Mão amiga" não caía para exatamente quem
            # mais a merecia. Foi um teste que pegou.
            perfil, _ = PerfilJogador.objects.get_or_create(
                pessoa=pessoa, site_id=site_id
            )

            ja_tem = set(
                Concessao.objects.filter(pessoa=pessoa, site_id=site_id).values_list(
                    "conquista_id", flat=True
                )
            )
            # Só MEDALHA, e só ATIVA. Marco real nunca cai por conta: ele passa
            # pela fila de validação, e conceder um por cálculo seria a escola
            # afirmando que alguém conseguiu um cliente sem ninguém ter olhado.
            candidatas = [
                c
                for c in ConquistaDefinicao.objects.filter(
                    site_id=site_id,
                    ativa=True,
                    classe=ConquistaDefinicao.Classe.MEDALHA,
                )
                if c.pk not in ja_tem and cumpre(c, pessoa, site_id, perfil)
            ]
            if not candidatas:
                break

            # A TRAVA FICA LIGADA DURANTE AS CONCESSÕES, e isto é o coração do
            # desenho: conceder chama `recalcular`, que chama esta função de
            # novo. Com a trava ligada, a chamada de dentro devolve lista vazia
            # na hora e quem resolve tudo é a rodada seguinte deste laço, que
            # enxerga o estado já atualizado.
            #
            # Desligar a trava aqui (como esteve na primeira versão) fazia a
            # chamada de dentro conceder o resto e devolver a lista para
            # NINGUÉM: as medalhas caíam certas no banco, e a resposta desta
            # função saía com uma só. Um retorno incompleto que ninguém nota é
            # pior que um erro — quem chamar para saber "o que ela ganhou?"
            # recebe metade.
            for conquista in candidatas:
                concessao, nova = conceder(
                    pessoa=pessoa, site_id=site_id, conquista=conquista
                )
                if nova:
                    concedidas.append(concessao)
    finally:
        _reentrancia.dentro = False

    if concedidas:
        logger.info(
            "criterios: %s ganhou %s medalha(s) por conta automática: %s",
            pessoa_id,
            len(concedidas),
            ", ".join(c.conquista.slug for c in concedidas),
        )
    return concedidas
