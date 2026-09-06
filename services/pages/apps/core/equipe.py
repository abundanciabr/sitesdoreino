"""Quem é da EQUIPE da escola nesta casa, e por que a resposta vem de fora.

**A FONTE MUDOU EM 06/09/2026, e a escolha é do mantenedor.** Até aqui, quem
conferia o portfólio era quem estivesse numa lista de ids colada à mão no env da
VPS (`IDS_DA_EQUIPE`). Ele pediu o contrário, com estas palavras: *"ao invés de
colar isso na VPS, podemos alterar para que todo admin possa fazer isso, para
agilizar?"*. Recebeu numa caixa de pergunta a objeção da fresta (administrador
desta casa vê a economia e os capítulos do livro não lançado dele), com as duas
saídas na mesa, e escolheu **"simplesmente todo admin confere"**, sem lista
separada de conferentes.

**O QUE ISSO CURA.** A lista da VPS era uma segunda casa do mesmo fato: no dia
em que ele promovia alguém pela tela de `/admin/escola/`, a lista do env não
mudava, e as duas discordavam sem ninguém perceber. Agora promover alguém lá
abre esta fila sozinho, e não sobra lista para alguém esquecer de atualizar.

**"RECONHECER NÃO É AUTORIZAR", e a lição fica INTEIRA.** A `identidade`
devolve um `papel` junto com o id de quem está logado, e usá-lo para abrir a
fila continua sendo confortável e errado: aquele campo é de EXIBIÇÃO
(`apps/core/menu.py` já diz isso de si mesmo). O que mudou não foi a lei, foi
QUEM responde: a pergunta vai à `admin`, de propósito, pelo contrato congelado,
porque é lá que a permissão mora. Quem decide o que fazer com o sim continua
sendo esta célula, fail-CLOSED.

**A CHAVE É E-MAIL, e ela já está na mão.** A porta pergunta `getSessionFull` à
`identidade`, e o e-mail vem nessa resposta. Agora ele serve a duas perguntas em
vez de uma, e continua sem ser guardado e sem ser exibido em lugar nenhum. Id de
plataforma não serviria: a porta da `admin` decide por e-mail normalizado, e
traduzir no meio custaria um salto de rede a mais e uma segunda forma de a mesma
pessoa existir.

**NÃO CONSEGUIR PERGUNTAR NÃO É "ENTÃO PODE ENTRAR", E TAMBÉM NÃO DERRUBA A
CASA.** As duas variáveis do par são lidas no ponto de uso, nunca no import
(`armadilhas/097`): sem elas, a Prancheta, a estante e o pedido de conferência
do aluno continuam respondendo normalmente, e só a fila da equipe fica
indisponível, com 503 e `Retry-After`. Fail-closed sem fail-hard, o mesmo
desenho de `TOKENS_ACEITOS` em `config/settings.py`.
"""

from __future__ import annotations

from .clients import AdminClient

# Um cliente por processo, como os outros dois que a porta guarda. Ele não lê
# env nenhum ao nascer: quem lê é a chamada, no ponto de uso.
_admin = AdminClient()


def e_da_equipe(email: str | None) -> bool:
    """Esta pessoa pode conferir o portfólio de outra?

    Sem e-mail devolve `False` sem tocar a rede, e a ordem importa: perguntar
    primeiro gastaria um salto para receber a resposta que já se sabe, e mandaria
    uma cadeia vazia a uma porta que compara e-mails.

    Levanta `AdminIndisponivel` ou `ConfiguracaoAusente` quando não deu para
    perguntar. **Quem chama trata as duas FECHANDO a fila com 503**, e nunca
    devolvendo `False`: um `False` aqui diria a um professor de verdade que ele
    não é da equipe, e o mandaria pedir uma promoção que ele já tem.
    """
    if not email:
        return False
    return _admin.e_administrador(email)
