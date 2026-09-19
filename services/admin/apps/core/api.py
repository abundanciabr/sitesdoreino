"""A porta de MÁQUINA da área administrativa: uma pergunta, e só ela.

POR QUE ELA EXISTE
------------------
A permissão de conferir o trabalho do aluno mora numa lista só, e essa lista é
a desta célula. Antes desta porta, a `pages` só sabia quem confere lendo um
`IDS_DA_EQUIPE` escrito à mão no env da VPS: uma segunda casa do mesmo fato. No
dia em que o mantenedor promove alguém pela tela de `/admin/escola/`, aquela
lista da VPS não muda, e as duas discordam sem ninguém perceber.

A RESPOSTA VEM DA MESMA FUNÇÃO QUE A PORTA DE GENTE USA
--------------------------------------------------------
`porta._emails_autorizados()` é quem já soma `ADMIN_EMAILS` (o chão do
servidor) com os administradores ativos da tabela, normalizando `strip()` e
`lower()` dos dois lados, e é quem já trata falha de banco como "vale só o env"
em vez de "deixa entrar" (`DECISAO-administradores-e-apagar.md` §3). Um segundo
jeito de responder "esta pessoa é administradora?" seria uma segunda resposta
livre para discordar da primeira, e no dia em que discordassem ninguém saberia
qual está certa. Por isso aqui não há `filter()` próprio, nem cópia da
normalização: há uma chamada.

UMA OPERAÇÃO SÓ, E ELA SÓ LÊ
-----------------------------
Não há verbo que promova nem que remova administrador, e a ausência é decisão:
o conjunto de tokens desta casa é plano, então todo par que ganha o token para
ler ganharia junto o poder de escrever (`armadilhas/318`). Nascendo
somente-leitura, essa conta não existe. Acrescentar escrita aqui é Rito de
Contrato novo, e muda o cálculo: exigiria um segundo grau de token.

`e_administrador: false` É RESPOSTA, NUNCA ERRO
------------------------------------------------
É o que a pergunta devolve para todo aluno da escola, que é quase todo mundo.
E-mail desconhecido responde exatamente a mesma coisa, de propósito: um 404
aqui diria a quem perguntou que aquele e-mail não existe na plataforma, e esta
porta não responde essa pergunta.
"""

from ninja import Router, Schema

from .porta import _emails_autorizados

router = Router()


class PedidoDeConsulta(Schema):
    """O e-mail de quem se pergunta. Comparado sem espacos e em minusculas."""

    model_config = {"extra": "forbid"}

    email: str


class RespostaDeConsulta(Schema):
    """Sim ou nao, e nada mais. Campo novo aqui e mudanca de contrato."""

    model_config = {"extra": "forbid"}

    e_administrador: bool


DESCRICAO_DA_OPERACAO = (
    "Responde a UNICA pergunta que outra celula faz a area administrativa:\n"
    "esta pessoa e da equipe da escola?\n"
    "\n"
    "A resposta soma as duas fontes que a porta desta celula ja soma, e na\n"
    "mesma ordem: os e-mails de ADMIN_EMAILS (o chao, que o servidor declara\n"
    "e o botao de remover se recusa a tocar) e os administradores ativos que\n"
    "a tela de /admin/ promoveu. E-mail comparado sem espacos e em\n"
    "minusculas, exatamente como a porta compara.\n"
    "\n"
    "POST e nao GET, e o motivo e o mesmo das duas irmas da `identidade`:\n"
    "caminho de URL entra em log de servidor, em historico de proxy e em\n"
    "rastro de erro; corpo, nao. E-mail nao viaja em URL nesta casa.\n"
    "\n"
    "`e_administrador: false` e RESPOSTA, nunca erro: e o que a pergunta\n"
    "devolve para todo aluno da escola, que e quase todo mundo. E-mail\n"
    "desconhecido responde a mesma coisa, de proposito, porque um 404 aqui\n"
    "diria a quem perguntou que aquele e-mail nao existe na plataforma, e\n"
    "esta porta nao responde essa pergunta.\n"
    "\n"
    "O QUE ELA DELIBERADAMENTE NAO DEVOLVE: nome, papel, id de plataforma,\n"
    "data de promocao, e a lista de administradores. Quem precisa ver a\n"
    "lista abre a tela de /admin/, com sessao e com o 404 fail-closed da\n"
    "porta desta celula na frente. A resposta desta porta RECONHECE um grau,\n"
    "e nunca AUTORIZA nada: quem decide o que fazer com o sim e a celula\n"
    "dona do recurso, fail-closed, como manda\n"
    "docs/decisoes/DECISAO-onde-mora-a-sessao.md secao 4.\n"
)


@router.post(
    "/administradores/consultar",
    response=RespostaDeConsulta,
    operation_id="isAdministrator",
    summary="Esta pessoa e da equipe da escola",
    description=DESCRICAO_DA_OPERACAO,
)
def is_administrator(request, pedido: PedidoDeConsulta):
    return {"e_administrador": pedido.email.strip().lower() in _emails_autorizados()}
