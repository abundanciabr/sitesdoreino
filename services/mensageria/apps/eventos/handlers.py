# apps/eventos/handlers.py  # [RECEITA:R4 v1]
"""Os handlers desta célula, e a mudança de assinatura de 02/09/2026.

**Todo handler passa a receber o `event_id` do envelope, e não só o `data`.**
Até aqui o `LICOES.md` registrava essa ausência como limitação conhecida — o
handler não sabia qual evento o tinha acordado, e a idempotência precisava de uma
segunda chave, de negócio.

O que forçou a mudança: a carta de um passo de sequência
(`notificacao.devida.v1`) exige `origem_event_id` no contrato, e é ele que torna
verdadeira a promessa *"a entrega do aviso é RASTREÁVEL"* — de qualquer aviso na
tela se chega ao acontecimento que o causou. Sem o `event_id` chegando até aqui,
a inscrição nasceria sem origem e o despachante, que é fail-closed, jamais
publicaria carta nenhuma.

O parâmetro tem default de propósito: os três handlers de pagamento não o usam, e
os testes que os chamam com um argumento só continuam valendo.

**E desde 05/09/2026 recebe também o `ator_id`**, pelo mesmo motivo de forma: em
`envio.recebido.v1` o aluno viaja SÓ no `ator_id` do envelope (o `data` tem os
ids do curso, da aula e do envio, e nada de gente), e o handler que guarda de
quem é cada envio não tinha como lê-lo. Mesmo desenho: terceiro parâmetro, com
default, e só quem precisa o usa.
"""

import logging

from django.db import transaction

from apps.jornadas import motor
from apps.jornadas.models import EnvioDeCheckpoint, Inscricao, Jornada

from .models import EnvioRegistrado
from .tasks import enviar_notificacao

log = logging.getLogger(__name__)

# O gatilho da jornada é o NOME DO EVENTO no fio, sem a versão — a mesma grafia
# que a `identidade` publica (`apps/identidade/eventos.py::PESSOA_CADASTRADA`) e
# a mesma que a chave de `STREAMS` usa. Escrever `identidade.pessoa-cadastrada.v1`
# aqui faria a jornada nunca casar com evento nenhum, em silêncio: nada erra,
# nada reclama, e a sequência simplesmente não acontece. Guarda:
# `tests/test_jornadas_primeira_sequencia.py::test_o_gatilho_da_jornada_casa_com_o_stream`.
GATILHO_CADASTRO = "identidade.pessoa-cadastrada"

# A sala de aula (célula `cursos`, degrau 2.4): o laudo devolvido dispara a
# jornada do silêncio de 14 e 30 dias; o envio recebido a cancela. Mesma regra
# de grafia: o nome no FIO, sem a versão.
GATILHO_DEVOLUCAO = "checkpoint.devolvido"
EVENTO_ENVIO_RECEBIDO = "envio.recebido"

# O convite para a Prancheta (degrau 17 do portfólio). Mesma regra de grafia: o
# nome no FIO, sem a versão. O evento chega a CADA aula cuja porta abre; quem
# separa o marco do progresso comum é `ao_aula_concluida`, logo abaixo.
GATILHO_BLOCO_FECHADO = "aula.concluida"

# Templates versionados dentro da célula (constituicoes/AGENTS.mensageria.md).
# TEMPLATES_POR_SITE é o ponto de extensão para override por site_id — vazio
# hoje porque nenhum site ainda pediu remetente/copy próprios; o fallback é
# sempre o template padrão da plataforma. [multissítio]
TEMPLATES_PADRAO = {
    "boas_vindas": {
        "versao": 1,
        "assunto": "Bem-vindo(a)!",
        "corpo": "Olá {name}, seu pagamento foi aprovado. Bem-vindo(a)!",
    },
    "recuperacao_pix": {
        "versao": 1,
        "assunto": "Seu Pix está esperando",
        "corpo": "Olá {name}, seu Pix expirou. Finalize aqui: {recovery_url}",
    },
    "recuperacao_recusado": {
        "versao": 1,
        "assunto": "Seu pagamento não foi aprovado",
        "corpo": "Olá {name}, seu pagamento foi recusado ({reason_code}). Tente novamente.",
    },
}
TEMPLATES_POR_SITE: dict[str, dict[str, dict]] = {}


def _resolver_template(tipo: str, site_id: str) -> dict:
    return TEMPLATES_POR_SITE.get(site_id, {}).get(tipo) or TEMPLATES_PADRAO[tipo]


def _registrar_e_enfileirar(
    *,
    event: str,
    site_id: str,
    order_id: str,
    tipo: str,
    canal: str,
    destinatario: str,
    tpl: dict,
    contexto: dict
) -> None:
    with transaction.atomic():
        envio, criado = EnvioRegistrado.objects.get_or_create(
            order_id=order_id,
            tipo=tipo,
            canal=canal,
            defaults=dict(
                event=event,
                site_id=site_id,
                destinatario=destinatario,
                assunto=tpl["assunto"].format(**contexto),
                corpo=tpl["corpo"].format(**contexto),
                template_versao=tpl["versao"],
            ),
        )
        if not criado:
            return  # [idempotência] este order_id+tipo+canal já tinha envio registrado
        transaction.on_commit(lambda: enviar_notificacao(envio.id))


def ao_pagamento_aprovado(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("boas_vindas", data["site_id"])
    contexto = {"name": cliente["name"]}
    _registrar_e_enfileirar(
        event="pagamento.aprovado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="boas_vindas",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pagamento.aprovado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="boas_vindas",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )


def ao_pix_expirado(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("recuperacao_pix", data["site_id"])
    contexto = {"name": cliente["name"], "recovery_url": data["recovery_url"]}
    _registrar_e_enfileirar(
        event="pix.expirado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="recuperacao_pix",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pix.expirado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="recuperacao_pix",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )


def ao_pagamento_recusado(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    cliente = data["customer"]
    tpl = _resolver_template("recuperacao_recusado", data["site_id"])
    contexto = {"name": cliente["name"], "reason_code": data["reason_code"]}
    _registrar_e_enfileirar(
        event="pagamento.recusado",
        site_id=data["site_id"],
        order_id=data["order_id"],
        tipo="recuperacao_recusado",
        canal="email",
        destinatario=cliente["email"],
        tpl=tpl,
        contexto=contexto,
    )
    if cliente.get("phone"):
        _registrar_e_enfileirar(
            event="pagamento.recusado",
            site_id=data["site_id"],
            order_id=data["order_id"],
            tipo="recuperacao_recusado",
            canal="whatsapp",
            destinatario=cliente["phone"],
            tpl=tpl,
            contexto=contexto,
        )


def ao_pessoa_cadastrada(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    """Alguém entrou no site pela primeira vez: inscreve nas jornadas do gatilho.

    O leque é por JORNADA, não por pessoa: se um dia houver duas sequências
    penduradas no cadastro, as duas inscrevem, e é a régua — uma só, por pessoa —
    que impede a soma virar três mensagens no mesmo dia.

    **Sem preenchimento retroativo** (decisão do mantenedor, §8.7.2): quem já
    estava cadastrado não é anunciado, porque este handler só roda para um evento
    de cadastro NOVO. Ele pesou contra mandar "bem-vindo" a quem usa o site há
    meses.

    Jornada desligada não inscreve ninguém — quem decide ligar é o mantenedor, e
    quem faz valer é o `motor.inscrever()`.
    """
    site_id = data["site_id"]
    pessoa_id = data["pessoa_id"]
    for jornada in Jornada.objects.filter(
        site_id=site_id, gatilho=GATILHO_CADASTRO, ativa=True
    ):
        motor.inscrever(
            jornada,
            destinatario_id=pessoa_id,
            site_id=site_id,
            origem_event_id=event_id,
        )


def ao_envio_recebido(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    """O aluno entregou um checkpoint: guarda de quem ele é, e cala o silêncio.

    Duas coisas, e a ordem não importa porque vivem na mesma transação do
    consumidor:

    1. **A correlação.** O devolvido que vier depois só carrega o `envio_id`;
       o aluno viaja AQUI, no `ator_id` do envelope, e em lugar nenhum mais.
       Sem esta linha o devolvido não sabe quem inscrever, e não chuta.
    2. **O cancelamento.** Um envio novo para a mesma (site, aluno, aula) é a
       prova de que a pessoa agiu: o episódio do silêncio que estiver andando
       para aquela aula é cancelado na hora, por evento, sem esperar a
       varredura reavaliar nada.

    O `ator_id` é lido do envelope (`processar_envelope` o repassa ao lado do
    `data`): é o id de PLATAFORMA do aluno, o único que atravessa células
    (`armadilhas/255`). Sem ele, este handler não grava nem cancela nada.
    """
    site_id = data["site_id"]
    aula_id = data["aula_id"]
    aluno_id = ator_id
    if not aluno_id:
        log.warning(
            "envio.recebido %s sem ator_id: nao sei de quem e o envio %s, entao "
            "nao guardo a correlacao nem cancelo silencio nenhum (o contrato "
            "manda o aluno no ator_id; se isto se repetir, e defeito do produtor)",
            event_id,
            data["envio_id"],
        )
        return
    EnvioDeCheckpoint.objects.get_or_create(
        site_id=site_id,
        envio_id=data["envio_id"],
        defaults={"aula_id": aula_id, "aluno_id": aluno_id},
    )
    for jornada in Jornada.objects.filter(site_id=site_id, gatilho=GATILHO_DEVOLUCAO):
        motor.cancelar(
            jornada,
            destinatario_id=aluno_id,
            site_id=site_id,
            contexto_id=aula_id,
            motivo="o aluno enviou o checkpoint de novo",
        )


def ao_checkpoint_devolvido(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    """A professora devolveu o checkpoint: o relógio do silêncio começa a contar.

    O aluno NÃO viaja neste evento (o `ator_id` é quem assinou o laudo). Ele
    vem da correlação que o `envio.recebido` do mesmo `envio_id` gravou antes.
    Se ela não existir (relay fora de ordem, ou envio anterior ao dia em que
    esta célula passou a escutar a sala de aula), ninguém é inscrito e o log
    diz por quê, com os ids: chutar o destinatário seria a pessoa fantasma da
    `armadilhas/255`, e retentar cinco vezes pela PEL derrubaria o consumidor
    cinco vezes (`_processar_e_ack` deixa a exceção subir) por um evento que,
    na prática, nunca vai encontrar o que procura.

    Um devolvido novo para a mesma (site, aluno, aula) RECOMEÇA a contagem:
    o episódio anterior é cancelado e o novo nasce ancorado agora. O mesmo
    devolvido reentregue não recomeça nada (`motor.recomecar`).

    Jornada desligada não inscreve ninguém; quem liga é o mantenedor, na tela
    dele, e quem faz valer é o `motor.inscrever()`.
    """
    site_id = data["site_id"]
    envio = EnvioDeCheckpoint.objects.filter(
        site_id=site_id, envio_id=data["envio_id"]
    ).first()
    if envio is None:
        log.warning(
            "checkpoint.devolvido %s chegou sem o envio.recebido do envio %s "
            "(site %s, aula %s): nao sei quem e o aluno, entao NAO inscrevo "
            "ninguem no silencio da devolucao. Se o envio.recebido chegar "
            "depois, este devolvido ja foi consumido e nao volta: o aluno so "
            "entra na jornada no proximo devolvido",
            event_id,
            data["envio_id"],
            site_id,
            data["aula_id"],
        )
        return
    for jornada in Jornada.objects.filter(
        site_id=site_id, gatilho=GATILHO_DEVOLUCAO, ativa=True
    ):
        motor.recomecar(
            jornada,
            destinatario_id=envio.aluno_id,
            site_id=site_id,
            contexto_id=data["aula_id"],
            origem_event_id=event_id,
            motivo="um devolvido novo recomecou a contagem",
        )


def ao_aula_concluida(
    data: dict, event_id: str | None = None, ator_id: str | None = None
) -> None:
    """A porta de uma aula abriu: se ela FECHA UM BLOCO, o convite para a
    Prancheta sai. Se for aula comum, não sai nada.

    ESTA É A LINHA QUE O DEGRAU 17 EXISTE PARA ESCREVER (`CS-PAGES-0001` AC-19).
    O convite dispara por um fato DECLARADO e nunca por inferência de progresso:
    a professora assinou o laudo que abriu a porta, e a escola declarou, na
    estrutura do curso, que aquela aula fecha um Bloco (`e_boss`). Nada aqui
    conta aulas concluídas, e a proibição é do plano (§3): a plataforma não
    serve aula e não sabe quantas existem no curso, então "ele já concluiu
    bastante coisa, deve ter terminado" seria palpite com cara de fato. O
    palpite manda "monte o seu portfólio" para quem está na terceira aula, e a
    caixa de entrada em que isso acontece uma vez deixa de ser lida.

    **O convite é UM SÓ.** Um curso com cinco Blocos convidaria cinco vezes para
    a mesma Prancheta, e a trava parcial do banco não pega isso: ela só impede
    dois episódios ANDANDO, e o segundo Bloco costuma chegar depois de o
    primeiro episódio ter concluído. Quem já foi chamado alguma vez não é
    chamado de novo.

    Sem aluno no `ator_id` ninguém é convidado: o contrato diz que ele nunca é
    nulo, e inscrever com destinatário vazio abriria um episódio de ninguém e
    endereçaria a carta ao nada (`armadilhas/255`).

    Jornada desligada não convida ninguém; quem liga é o mantenedor, na tela
    dele, e quem faz valer é o `motor.inscrever()`.
    """
    if not data["e_boss"]:
        return  # aula comum: progresso, não marco. Nada a declarar.

    site_id = data["site_id"]
    if not ator_id:
        log.warning(
            "aula.concluida %s (site %s, aula %s) chegou sem ator_id: nao sei "
            "quem fechou o bloco, entao NAO convido ninguem para a Prancheta. "
            "O contrato manda o aluno no ator_id; se isto se repetir, e defeito "
            "do produtor",
            event_id,
            site_id,
            data["aula_id"],
        )
        return

    for jornada in Jornada.objects.filter(
        site_id=site_id, gatilho=GATILHO_BLOCO_FECHADO, ativa=True
    ):
        if Inscricao.objects.filter(
            jornada=jornada, site_id=site_id, destinatario_id=ator_id
        ).exists():
            continue
        motor.inscrever(
            jornada,
            destinatario_id=ator_id,
            site_id=site_id,
            origem_event_id=event_id,
        )
