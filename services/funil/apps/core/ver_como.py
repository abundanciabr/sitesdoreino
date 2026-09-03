# apps/core/ver_como.py — "ver o site como outra pessoa vê"
"""O disfarce de EXIBIÇÃO da equipe. Pedido do mantenedor em 02/09/2026.

Ele pediu "algo como aquela opção do Facebook de Ver como, daí eu posso, mesmo
sendo admin, ver como Aluno". O pedido nasceu de um defeito real: a home
oferecia "Pedir entrada" à conta dele (PR #897), e ele não tinha como conferir
a correção pelos olhos de um aluno — a conta dele entra pela porta da EQUIPE e
não tem matrícula, então o site nunca lhe mostra a tela que um aluno vê.

A LINHA QUE ESTE ARQUIVO NÃO CRUZA, E É A RAZÃO DE ELE SER PEQUENO
------------------------------------------------------------------
**O disfarce muda o que as telas MOSTRAM. Ele não muda nada do que a pessoa
PODE.** Não é uma limitação a ser removida um dia: é a `DECISAO-onde-mora-a-
sessao` §4 e a Lei 4 da constituição. Autorização é fail-closed, na célula dona
do recurso, conferindo a lista dela. Um "ver como" que mexesse nisso seria uma
vitrine passando a decidir acesso — a doença de que este projeto se vacinou.

Consequência prática, e ela precisa estar na tela (está, na tarja): vendo como
aluno, a home mostra o caminho da Caixa; CLICANDO nele, a Caixa continua
abrindo como equipe, porque é ela quem decide isso e ela não olha para este
cookie. A prévia é da TELA, não da experiência inteira.

FAIL-CLOSED EM QUEM PODE SE DISFARÇAR
--------------------------------------
O cookie só vale para quem a `identidade` já reconhece como `staff`. Para todo
o resto ele é IGNORADO, e essa guarda não é zelo excessivo — sem ela, qualquer
visitante que escrevesse `meshcraft_ver_como=aluno` no próprio navegador veria
a home oferecer o caminho da Caixa e receberia um "não" na cara ao clicar. Que
é exatamente o defeito de 28/08/2026 que a escada de categorias nasceu para
curar, ressuscitado por um cookie.

Note a direção: o cookie forjado nunca DÁ nada (a Caixa continua fail-closed);
ele só faria a tela PROMETER o que a porta desmente. Por isso a guarda é sobre
promessa, não sobre acesso.

POR QUE A `na_fila` FICOU DE FORA, DE PROPÓSITO
------------------------------------------------
As quatro categorias aqui são exatamente as que a home sabe desenhar **sem
nenhum dado inventado**. A `na_fila` precisaria de um "esperando há N dias" e de
um motivo de recusa, e não existe N verdadeiro para quem não está na fila —
seria a tela exibindo um número fabricado. Esta casa prefere dizer "não
comprovado" a mostrar dado bonito e falso, e a mesma régua vale aqui. No dia em
que o mantenedor quiser essa prévia, ela entra como decisão de produto ("estes
são números de exemplo"), não de sorrelfa.

`reembolsado` também fica fora, por outro motivo: a home não tem ramo para ela
hoje, e um disfarce que não muda nada na tela seria uma opção que mente sobre
si mesma.
"""

#: O nome do cookie. Não é assinado, e não precisa ser: ele não carrega
#: autoridade nenhuma. O pior que um valor forjado faz é piorar a própria tela
#: de quem o forjou — e só se essa pessoa já for da equipe.
COOKIE = "meshcraft_ver_como"

#: O valor que a `identidade` devolve em `papel` para quem está na
#: `IDENTIDADE_STAFF_EMAILS`. A MESMA string que `apps/core/menu.py` compara, e
#: importada de lá em vez de reescrita: duas constantes com o mesmo nome e
#: valores diferentes fariam o menu e o disfarce discordarem sobre quem é
#: equipe, e o sintoma seria alguém ver a tarja sem ver o atalho.
from apps.core.menu import PAPEL_DE_EQUIPE  # noqa: E402

#: As categorias que a home desenha sem inventar dado. Lista de PERMISSÃO, e não
#: exclusão: categoria nova que a `alunos` invente amanhã nasce FORA daqui, e
#: alguém precisa decidir explicitamente incluí-la. Com exclusão, ela viraria
#: opção de disfarce sozinha, sem ninguém ter olhado se a tela sabe desenhá-la.
DISFARCES = ("aluno", "cadastrado", "pausado", "ex_aluno")


def disfarce_valido(valor: str) -> str:
    """O disfarce pedido, ou `""` se não for um dos previstos.

    Fail-closed na palavra, como o `_plateia_confere` do menu: o que este
    arquivo não conhece não vira disfarce nenhum. Sem isso, um valor de lixo no
    cookie viraria uma categoria que a home não sabe desenhar, e a pessoa veria
    a home vazia sem entender por quê.
    """
    limpo = (valor or "").strip().lower()
    return limpo if limpo in DISFARCES else ""


def disfarce_de(papel: str, valor_do_cookie: str) -> str:
    """O disfarce EM VIGOR para quem tem este papel. `""` = nenhum.

    As duas condições são conferidas aqui, juntas e num lugar só, para que não
    exista um caminho em que uma seja lembrada e a outra esquecida.
    """
    if papel != PAPEL_DE_EQUIPE:
        return ""
    return disfarce_valido(valor_do_cookie)
