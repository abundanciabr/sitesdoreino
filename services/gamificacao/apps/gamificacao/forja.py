# apps/gamificacao/forja.py
"""A FORJA: o medidor de tentativas por peça, e o selo que sai dele.

É o único medidor desta escola que celebra a INSISTÊNCIA. Todo o resto do
sistema conta acerto: XP por evento, medalha por marco alcançado, nível por
total. Aqui a conta é outra, e ela é o oposto de esconder o esforço: a pessoa
mostra que errou treze vezes antes de acertar, e o prêmio é o selo
*"forjada em 13 tentativas"*.

AS SEIS DECISÕES QUE ESTE ARQUIVO CARREGA, E QUE NÃO SE REABREM
---------------------------------------------------------------
1. **O nome é FORJA, não Têmpera** (decisão 2 do mantenedor na Sessão A). Onde
   o plano e o VEREDITO dizem Têmpera, leia Forja.

2. **Zero XP, e não existe onde guardar XP.** Nenhum `LancamentoDeXP` nasce
   neste caminho, e a ausência é a decisão: pagar insistência em pontos
   ensinaria a inflar o número de tentativas, que é exatamente o número que o
   selo existe para tornar honesto. A medalha `dez-forjas` paga o XP DELA
   quando cai, e isso é da medalha, nunca da forja.

3. **Não existe catálogo de desafios na plataforma, e esta célula não é dona
   dele.** `desafio_ref` é opaco de propósito. Por isso quem cria a forja é o
   próprio aluno, nomeando a peça em que está trabalhando: o texto que ele
   escreve vira a CHAVE, de forma estável, e nada aqui puxa dependência de
   outra célula nem espera a Galeria (degrau 19).

4. **O medidor só cresce, e o teto é do banco.** Não existe "diminuir uma
   tentativa" e não existe função para isso. A conferência acontece antes de
   gravar; a `CheckConstraint` é o ÚLTIMO cinto, nunca o primeiro.

5. **Selar é caminho só de ida.** Uma forja selada não volta a crescer, e o
   `selo` é escrito no momento do selamento com o número congelado. Reabrir
   apagaria a prova de insistência que a coisa toda existe para guardar.

6. **O selo é atributo da peça**, e o degrau 19 (a Galeria) vai lê-lo. Este
   arquivo só o deixa pronto e visível.

POR QUE O NOME LEGÍVEL É DERIVADO DA CHAVE, E NÃO GUARDADO
-----------------------------------------------------------
O modelo `Forja` não tem coluna de nome, e isso é congelado: mexer nele é
migração, não sessão de tela. Então a chave preserva o que dá para preservar
(acento incluído, por `slugify(..., allow_unicode=True)`) e a exibição a
devolve com a primeira letra maiúscula. O que se perde é a capitalização do
meio da frase: quem escreve "Chapéu de Mago" lê depois "Chapéu de mago".

A troca é deliberada, e paga por duas coisas que valem mais: a chave é
INSENSÍVEL a maiúsculas e a espaço sobrando, então "Chapéu de Mago" e
"chapéu de mago" são a MESMA peça (a restrição do banco pega as duas), e o
acento sobrevive, que numa escola brasileira é o que a pessoa nota primeiro.

O QUE ESTE ARQUIVO NÃO FAZ
---------------------------
**Não escreve regra de medalha nenhuma.** `criterios._valor_forjas` já conta
forjas seladas e a medalha `dez-forjas` já espera por ele desde o degrau 12.
O que `selar()` faz é CHAMAR o motor, porque a Forja não passa pelo motor de
XP (ela vale zero) e sem essa chamada a medalha só cairia na próxima vez que
algum outro número da pessoa mudasse.
"""

from __future__ import annotations

import logging

from django.db import IntegrityError, transaction
from django.utils import timezone
from django.utils.text import slugify

from . import criterios
from .models import Forja, Pessoa

logger = logging.getLogger(__name__)

# O tamanho da chave sai do MODELO, nunca de um número repetido aqui. Duas
# expressões do mesmo limite divergem no primeiro dia em que alguém mexe numa
# delas, e divergir aqui significaria o serviço aceitar um nome que o banco
# recusa depois, com 500 na cara do aluno.
LIMITE_DA_CHAVE = Forja._meta.get_field("desafio_ref").max_length


class ForjaRecusada(ValueError):
    """O gesto não vale, e a mensagem é escrita para ser lida por gente.

    Recusa NUNCA vira 500 na tela: a view a transforma em frase e devolve a
    página. Um erro de servidor diria ao aluno que a escola quebrou quando o
    que aconteceu foi ele tentar selar duas vezes.
    """


# ---------------------------------------------------------------------------
# A chave da peça, e o nome que a pessoa lê
# ---------------------------------------------------------------------------
def chave_do_desafio(texto: str) -> str:
    """O texto do aluno vira a chave estável da peça. Recusa o que não vira.

    `allow_unicode=True` de propósito: sem ele "chapéu" viraria "chapeu" e a
    escola devolveria ao aluno brasileiro um nome que ele não escreveu.

    **Nome grande demais é RECUSADO, nunca cortado em silêncio.** Cortar em 64
    faria duas peças diferentes que só divergem no fim virarem a mesma linha,
    e o aluno veria as tentativas de uma somadas às da outra sem nada avisando.
    """
    chave = slugify(texto or "", allow_unicode=True).strip("-")
    if not chave:
        raise ForjaRecusada(
            "Diga o nome da peça que você está forjando, com pelo menos uma "
            "letra ou um número."
        )
    if len(chave) > LIMITE_DA_CHAVE:
        raise ForjaRecusada(
            "Esse nome ficou grande demais. Escreva um apelido curto para a "
            "peça, com no máximo "
            f"{LIMITE_DA_CHAVE} letras."
        )
    return chave


def nome_da_peca(desafio_ref: str) -> str:
    """A chave de volta em português, para a tela. Ver a docstring do módulo."""
    legivel = (desafio_ref or "").replace("-", " ").strip()
    if not legivel:
        return ""
    return legivel[0].upper() + legivel[1:]


def texto_do_selo(tentativas: int) -> str:
    """A frase que fica gravada na peça, com o número congelado.

    Singular e plural, porque *"forjada em 1 tentativas"* numa página que o
    aluno mostra para os outros é a escola escrevendo errado o orgulho dele.
    """
    if tentativas == 1:
        return "forjada em 1 tentativa"
    return f"forjada em {tentativas} tentativas"


# ---------------------------------------------------------------------------
# Os três gestos: abrir, martelar, selar
# ---------------------------------------------------------------------------
def abrir(*, pessoa: Pessoa, site_id: str, nome: str) -> Forja:
    """Começa uma forja, ou devolve a que já existe com esse nome.

    **Abrir JÁ é a primeira tentativa** (`medidor=1`). Ninguém forja uma peça
    em zero tentativas, e um selo dizendo *"forjada em 0 tentativas"* seria uma
    frase falsa impressa com orgulho, na página que o aluno mostra aos outros.

    **Quem decide que não há duas é o BANCO**, pelo
    `Unique(pessoa, site_id, desafio_ref)`. `get_or_create` perde a corrida com
    elegância: o segundo clique simultâneo leva `IntegrityError` do banco,
    volta e lê a linha que o primeiro gravou. Uma conferência em Python antes
    do `create` seria a corrida que se perde em silêncio.

    **Abrir de novo uma peça que já está na bancada NÃO mexe nela.** É o gesto
    mais comum de todos (o aluno digita o apelido sem lembrar que já começou), e
    é também o caminho mais fácil de o medidor encolher. `get_or_create` devolve
    a linha como ela está, e é só isso que este caminho faz.

    ESTA FUNÇÃO TEM UMA CAUSA SÓ PARA O MEDIDOR NASCER EM 1, E ISSO É DELIBERADO
    ---------------------------------------------------------------------------
    A primeira versão tinha duas: o `defaults` abaixo e um bloco que subia para
    1 qualquer linha encontrada com o medidor zerado, defendendo de "uma linha
    nascida por outro caminho". Esse outro caminho não existe (nada mais nesta
    célula escreve `Forja`), e a defesa especulativa custou caro: com ela no
    lugar, trocar o `defaults` por zero deixava o guarda VERDE, porque o bloco
    consertava a mutação. A asserção tinha duas causas suficientes, que é a
    forma mais comum de falso-verde nesta casa (`RETROSPECTIVA-FASE-D` §1).
    Achado por mutação em 01/09/2026, e a cura foi apagar a segunda causa.
    """
    chave = chave_do_desafio(nome)
    with transaction.atomic():
        forja, _ = Forja.objects.get_or_create(
            pessoa=pessoa,
            site_id=site_id,
            desafio_ref=chave,
            defaults={"medidor": 1},
        )
    return forja


def mais_uma_tentativa(*, pessoa: Pessoa, site_id: str, desafio_ref: str) -> Forja:
    """Soma UMA tentativa. Só cresce, e o teto segura.

    `select_for_update` porque duas abas do mesmo aluno somando ao mesmo tempo
    leriam o mesmo número e gravariam o mesmo número: a tentativa de uma delas
    desapareceria sem erro nenhum. O lock faz a segunda esperar e ler o mundo
    já somado.

    A ordem das recusas é a ordem da verdade: forja selada não aceita nada, e
    só depois disso o teto tem o que dizer.
    """
    try:
        with transaction.atomic():
            forja = _minha(pessoa=pessoa, site_id=site_id, desafio_ref=desafio_ref)
            if forja.selada_em is not None:
                raise ForjaRecusada(
                    "Esta peça já está selada. O número de tentativas dela "
                    "ficou guardado como estava, e isso não volta atrás."
                )
            if forja.medidor >= forja.teto:
                raise ForjaRecusada(
                    f"Esta peça chegou ao limite de {forja.teto} tentativas. "
                    "O contador para por aqui, e o seu trabalho não: quando "
                    'ela ficar pronta, é só dizer "terminei".'
                )
            forja.medidor += 1
            forja.save(update_fields=["medidor", "atualizada_em"])
    except IntegrityError as erro:
        # O ÚLTIMO CINTO, e ele existe para o caso que a conferência acima não
        # alcança: alguém baixou o teto por fora enquanto esta transação
        # corria. Chegar aqui é raro; virar 500 na tela do aluno não pode ser.
        logger.warning("o banco recusou a tentativa em %s: %s", desafio_ref, erro)
        raise ForjaRecusada(
            "Esta peça chegou ao limite de tentativas. O contador para por "
            'aqui, e o seu trabalho não: quando ela ficar pronta, é só dizer "terminei".'
        ) from erro
    return forja


def selar(*, pessoa: Pessoa, site_id: str, desafio_ref: str) -> Forja:
    """A peça ficou pronta. Congela o número e escreve o selo. Só de ida.

    **O selo é escrito AQUI, com o número deste instante**, e não calculado na
    tela toda vez. Se fosse calculado, mexer no medidor depois reescreveria o
    passado, e o selo deixaria de ser prova de coisa nenhuma.

    **Selar de novo é recusa, e não um segundo selo.** Fosse idempotente em
    silêncio, um F5 depois de selar pareceria um gesto novo; sendo recusa com
    frase, a página conta o que aconteceu.
    """
    with transaction.atomic():
        forja = _minha(pessoa=pessoa, site_id=site_id, desafio_ref=desafio_ref)
        if forja.selada_em is not None:
            raise ForjaRecusada(
                f"Esta peça já foi selada, e o selo dela diz: {forja.selo}."
            )
        forja.selada_em = timezone.now()
        forja.selo = texto_do_selo(forja.medidor)
        forja.save(update_fields=["selada_em", "selo", "atualizada_em"])

    # A MEDALHA DAS DEZ FORJAS CAI DAQUI, e este é o único ponto de chamada
    # possível: a Forja vale zero XP, então ela nunca passa por
    # `motor.recalcular`, que é onde todo o resto do sistema avalia critérios.
    # Sem esta linha, `forjas_seladas` teria fato e mesmo assim a medalha só
    # cairia na próxima vez que algum OUTRO número da pessoa mudasse.
    #
    # Protegido porque o SELO é o fato e a medalha é consequência: um tropeço
    # no motor não pode desfazer, nem esconder, a prova de insistência que a
    # pessoa acabou de ganhar. O log grita, e a próxima avaliação recupera.
    try:
        criterios.avaliar(pessoa.id_da_plataforma, site_id)
    except Exception:  # noqa: BLE001 — o selo já está gravado; ver acima
        logger.exception(
            "a forja %s foi selada, mas o motor de medalhas tropeçou", desafio_ref
        )
    return forja


def _minha(*, pessoa: Pessoa, site_id: str, desafio_ref: str) -> Forja:
    """A forja DESTA pessoa nesta escola, travada para escrita.

    **A pessoa e o site entram na consulta, sempre.** É por isso que nenhum
    gesto desta célula recebe o `id` de uma linha: um formulário que mandasse
    `forja=317` seria um número que qualquer um edita no navegador, e a defesa
    passaria a depender de alguém lembrar de conferir o dono. Aqui não há o que
    lembrar, porque não há caminho: o dono é quem a sessão diz que é, e a linha
    de outra pessoa simplesmente não existe para esta consulta.
    """
    forja = (
        Forja.objects.select_for_update()
        .filter(pessoa=pessoa, site_id=site_id, desafio_ref=desafio_ref)
        .first()
    )
    if forja is None:
        raise ForjaRecusada("Não encontrei essa peça entre as suas.")
    return forja


# ---------------------------------------------------------------------------
# O que a tela mostra
# ---------------------------------------------------------------------------
def abertas_de(pessoa: Pessoa, site_id: str) -> list[Forja]:
    """As peças em que a pessoa está trabalhando, a mexida mais recente em cima."""
    return list(
        Forja.objects.filter(
            pessoa=pessoa, site_id=site_id, selada_em__isnull=True
        ).order_by("-atualizada_em", "desafio_ref")
    )


def seladas_de(pessoa: Pessoa, site_id: str) -> list[Forja]:
    """As peças que ficaram prontas, a mais recente em cima."""
    return list(
        Forja.objects.filter(
            pessoa=pessoa, site_id=site_id, selada_em__isnull=False
        ).order_by("-selada_em", "desafio_ref")
    )
