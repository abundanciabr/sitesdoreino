"""A vitrine pública do aluno: o endereço, o opt-in e o que a página mostra.

ci:texto-publicado

A MARCA ACIMA LIGA O PORTÃO DO TRAVESSÃO neste arquivo inteiro
(`ci/travessao.py`, terceira regra de alcance no `CLAUDE.md`), pelo mesmo motivo
do `semaforo.py` e do `conferencia.py` ao lado: as recusas daqui são frases que
o ALUNO lê na estante dele, e elas não estão numa `templates/` nem num rótulo de
`TextChoices`, que são as duas regras que pegam sozinhas.

Lei: `docs/changespecs/CS-PAGES-0001.md`, critérios AC-13, AC-14 e AC-15, e
`docs/decisoes/PLANO-PORTFOLIO-DO-ALUNO.md` §4, §5 (degrau 13) e §7. Este módulo
é a regra do degrau 13 inteiro, tirando as telas.

O PADRÃO É PRIVADO, E ISSO É O CENTRO DO DEGRAU
------------------------------------------------
A vitrine só existe se o aluno LIGAR. O banco já defende isso desde o degrau 02
(`Portfolio.vitrine_publicada` nasce `False`, e a restrição
`vitrine_publicada_tem_apelido_e_data` recusa os meios-termos); o que este
módulo acrescenta é o gesto, e a garantia de que quem não ligou não existe para
a internet.

**Quem não ligou responde 404, e nunca 403.** Um 403 responderia uma pergunta
que ninguém tem o direito de fazer: *este apelido existe?* Com 404, tentar
`/estudio/ana` no escuro devolve exatamente a mesma coisa que tentar
`/estudio/quem-nao-existe`, e a página desligada some junto com a que nunca foi
criada. Guarda:
`tests/test_a_vitrine_publica.py::test_a_vitrine_desligada_responde_o_MESMO_que_o_apelido_que_nunca_existiu`.

O ENDEREÇO NÃO SAI DE `{% url %}`, E É O ÚNICO DESTA CASA QUE NÃO SAI
----------------------------------------------------------------------
A regra desta casa é que endereço sai de `{% url %}`, senão o prefixo público
some em produção (`armadilhas/029` e `/081`). Aqui a situação é o INVERSO, e a
`admin` já a mediu de fora em 29/08/2026 (`armadilhas/102`, e a constante
`documentos.PREFIXO_PUBLICO` que nasceu dela): `reverse()` monta
`/pages/estudio/ana` porque `FORCE_SCRIPT_NAME` vale para a célula inteira, e a
vitrine **não mora sob `/pages`**. Aquele endereço até chega aqui, mas seria um
SEGUNDO endereço para a mesma página, e ele iria parar no chat de um cliente
pagante, que é justamente onde o endereço curto foi escolhido para estar
(plano §4).

Uma constante só, aqui, é o que impede a correção de virar caminho cravado
espalhado por dois templates. Ela casa com o `PathPrefix(/estudio)` do gateway
(`infra/traefik/dynamic/plataforma.yml`, roteador `estudio`, sem `StripPrefix`)
e é a MESMA que a porta da casa lê para isentar a vitrine
(`apps/core/porta.py`), importada de cá em vez de copiada: duas cadeias
`"/estudio"` livres para divergir fechariam a vitrine ou abririam a casa.
"""

from __future__ import annotations

import re
import unicodedata

from django.db import IntegrityError, transaction
from django.utils import timezone

from apps.portfolio.models import EstadoDoLink, Peca, Portfolio

#: O prefixo do endereço PÚBLICO. Leia o cabeçalho deste módulo antes de mexer.
PREFIXO_PUBLICO = "/estudio"

#: O tamanho do apelido é o da coluna (`Portfolio.apelido`), e não um número
#: novo: dois limites para o mesmo fato divergem no dia em que um deles mudar.
LIMITE_DO_APELIDO = Portfolio._meta.get_field("apelido").max_length


class VitrineRecusada(Exception):
    """O gesto não pode acontecer, e o motivo é regra, não erro de programa.

    Uma exceção, e não um `return None`, pelo mesmo motivo do
    `conferencia.ConferenciaRecusada`: quem chama é uma tela, e uma tela que
    recebe `None` mostra "nada aconteceu", que é o que uma pessoa recusada NÃO
    pode ver. A mensagem é escrita para ser lida por gente.
    """


SEM_LETRA_NEM_NUMERO = (
    "Escolha um endereço com letras e números, por exemplo ana-3d. Ele é o "
    "final do link que você manda ao cliente."
)

JA_E_DE_OUTRO = (
    "Este endereço já é de outro aluno da escola. Escolha outro, por exemplo "
    "com o seu sobrenome ou com o nome do seu estúdio."
)


def endereco(apelido: str) -> str:
    """O endereço público completo desta vitrine, do jeito que o aluno o copia."""
    return f"{PREFIXO_PUBLICO}/{apelido}"


def apelido_de(texto: str) -> str:
    """O que a pessoa digitou vira o endereço que a máquina liga.

    O aluno escreve "Ana 3D" e o endereço precisa de `ana-3d`. Pedir os dois
    seria pedir a ele que entendesse a diferença, e recusar o que ele digitou
    seria fazê-lo adivinhar o formato. O resultado aparece inteiro na tela, para
    ele conferir antes de mandar o link a alguém.

    O formato é o mesmo que o banco exige em `apelido_e_endereco_web`, e o vazio
    é a resposta para o que não tem nenhuma letra nem número aproveitável.
    """
    limpo = unicodedata.normalize("NFKD", texto or "")
    limpo = "".join(c for c in limpo if not unicodedata.combining(c)).lower()
    limpo = re.sub(r"[^a-z0-9]+", "-", limpo).strip("-")
    return limpo[:LIMITE_DO_APELIDO].strip("-")


def publicar(*, site_id: str, aluno_id: str, texto: str) -> Portfolio:
    """O aluno liga a vitrine, com o endereço que ele escolheu.

    **Cria o portfólio se ele ainda não existir**, do mesmo jeito que guardar a
    primeira peça cria: publicar antes de colar obra é caminho normal, e a
    página diz ao visitante que ainda não há obras. Trancar aqui seria inventar
    uma regra que ninguém pediu, e a lista desta casa orienta, nunca tranca
    (plano §7).

    **A colisão é decidida pelo BANCO**, e não por uma consulta antes da
    escrita: entre o `exists()` e o `save()` cabe o pedido de outro aluno, e a
    restrição `um_apelido_por_site` é a única régua que não tem essa fresta.
    """
    apelido = apelido_de(texto)
    if not apelido:
        raise VitrineRecusada(SEM_LETRA_NEM_NUMERO)

    try:
        with transaction.atomic():
            portfolio, _ = Portfolio.objects.get_or_create(
                site_id=site_id, aluno_id=aluno_id
            )
            portfolio.apelido = apelido
            portfolio.vitrine_publicada = True
            portfolio.publicada_em = timezone.now()
            portfolio.save(
                update_fields=["apelido", "vitrine_publicada", "publicada_em"]
            )
    except IntegrityError as erro:
        raise VitrineRecusada(JA_E_DE_OUTRO) from erro
    return portfolio


def despublicar(portfolio: Portfolio) -> None:
    """Tira a página do ar. Imediatamente, e no pedido seguinte já não existe.

    **O apelido FICA.** Desligar não é perder o endereço: quem religa amanhã
    precisa do mesmo link que já mandou ao cliente, e apagar o apelido aqui
    entregaria esse endereço ao próximo aluno que o pedisse.
    """
    portfolio.vitrine_publicada = False
    portfolio.publicada_em = None
    portfolio.save(update_fields=["vitrine_publicada", "publicada_em"])


def publicada(*, site_id: str, apelido: str) -> Portfolio | None:
    """O portfólio que este endereço mostra, ou `None` quando não há página.

    `None` responde por TODOS os casos de uma vez, e essa é a economia que faz o
    404 não vazar nada: apelido que nunca existiu, aluno que nunca ligou, aluno
    que desligou hoje de manhã e escola diferente saem por aqui com a mesma
    resposta, e quem chama não tem como tratá-los diferente sem querer.

    **A fronteira de site entra na consulta** (Lei 9): o apelido é único por
    escola, e sem o `site_id` duas alunas chamadas `ana` em escolas diferentes
    disputariam a mesma página.
    """
    return Portfolio.objects.filter(
        site_id=site_id, apelido=apelido, vitrine_publicada=True
    ).first()


def obras(portfolio: Portfolio) -> list[Peca]:
    """As peças que a vitrine mostra, na ordem que o aluno escolheu.

    **A peça com o link QUEBRADO fica de fora**, e isso não é filtro de
    qualidade nem opinião sobre a obra (o plano §7 proíbe as duas coisas): é o
    fato medido de que o endereço parou de responder. Mostrá-la renderia um
    quadrado vazio na página que o aluno manda a um cliente pagante, e quem
    pareceria ruim seria a obra dele.

    **Sair da vitrine não é ser apagada** (critério AC-09). A peça continua na
    estante, marcada, com a data da quebra e a frase que diz o que fazer, e ela
    volta sozinha para cá no minuto em que o endereço responder de novo.

    O `nao_conferido` ENTRA, pela assimetria que o degrau 08 já escreveu em
    `conferencia_do_link.py`: daqui não dá para separar "o site dele caiu" de "a
    nossa rede caiu", e esconder a obra do aluno por causa de uma tosse da nossa
    rede seria a mesma injustiça que aquele módulo recusou.
    """
    return list(
        portfolio.pecas.exclude(estado_do_link=EstadoDoLink.QUEBRADO).order_by("ordem")
    )
