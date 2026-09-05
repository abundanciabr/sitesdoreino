"""A derivação dos marcos: de fato guardado a conquista com data (degrau 9).

`PLANO-PAINEL-DE-GESTAO.md` §6.4. Um marco é uma conquista com data, e todos
os que nascem aqui são AUTOMÁTICOS: cada um sai de um fato que já está no
livro e cita o `event_id` dele. Marco assinado por gente não passa por aqui.

## As três decisões que valem a leitura

**1. A derivação nunca levanta, e nunca desfaz o fato.** `receber` guarda o
evento primeiro e chama esta função depois, fora da transação do fato. O que
esta célula valida na porta é o ENVELOPE, nunca o miolo (`recepcao.py`); logo,
um `data` fora do formato do contrato é possível, e a resposta certa a ele é
marco nenhum. Fato guardado e marco ausente é honesto; fato recusado porque o
marco não deu para calcular seria o livro perdendo história por causa de uma
leitura.

**2. A conquista guarda a PRIMEIRA vez, e um fato mais antigo puxa a data para
trás.** O consumidor lê um stream por vez, então uma fila represada de fórum
pode chegar depois de uma matrícula de ontem. Se o marco já existisse com a
data mais nova e ela nunca fosse corrigida, a coorte poria a pessoa no mês
errado sem erro em lugar nenhum. Quando a data recua, o `event_id` recua
junto: a linhagem tem de apontar para o fato que fixou a data que está lá.

**3. Só há marco onde há id opaco de quem conquistou, e vindo do próprio
fato.** Perguntar a outra célula quem é o dono de um fato é proibido nesta
casa (`AGENTS.metricas.md`, Fronteiras) e transformaria o livro num espelho do
presente. Por isso `quiz.completado` não gera marco nenhum: ele identifica a
pessoa por e-mail, e e-mail nunca é identidade de pessoa nesta plataforma
(DECISAO-EVO-01 §3). Os assuntos da Caixa de Sugestões também ficam de fora:
sugerir e votar são participação, e a régua do plano é conquista.
"""

from __future__ import annotations

import datetime as dt

from django.db import IntegrityError, transaction

from .models import Evento, Marco, dia_em_sao_paulo

PESSOA = Marco.Sujeito.PESSOA
MATRICULA = Marco.Sujeito.MATRICULA

#: Qual conquista cada situação de matrícula é. `origem` separa a VENDA do
#: aluno das turmas anteriores, e é a distinção que a meta do ciclo conta:
#: sem ela o livro somaria como a mesma coisa quem comprou e quem foi
#: liberado pela sala de espera (`matricula.situacao-alterada.v1`, campo
#: `origem`). Os outros quatro estados (recusada, suspensa, encerrada,
#: reembolsada) não são conquista, e ficam de fora de propósito.
VIROU_ALUNO_POR_ORIGEM = {
    "comprou": Marco.Tipo.VIROU_ALUNO_COMPRANDO,
    "liberado": Marco.Tipo.VIROU_ALUNO_LIBERADO,
}


def _id_opaco(valor: object) -> str:
    """O id, se ele serve como chave de sujeito. Caso contrário, texto vazio.

    Mais longo que a coluna é recusado em vez de cortado: cortar juntaria dois
    sujeitos diferentes no mesmo marco, e a contagem encolheria sem avisar.
    """
    if not isinstance(valor, str):
        return ""
    valor = valor.strip()
    return valor if 0 < len(valor) <= 120 else ""


def _instante(valor: object) -> dt.datetime | None:
    """Uma data e hora COM fuso, ou nada. Sem fuso o dia é um chute (`099`)."""
    if not isinstance(valor, str):
        return None
    try:
        quando = dt.datetime.fromisoformat(valor)
    except ValueError:
        return None
    return quando if quando.tzinfo is not None else None


def _entrou_no_site(evento: Evento) -> list[tuple]:
    pessoa = _id_opaco(evento.dados.get("pessoa_id"))
    if not pessoa:
        return []
    return [(PESSOA, pessoa, Marco.Tipo.ENTROU_NO_SITE, evento.ocorrido_em)]


def _vida_da_matricula(evento: Evento) -> list[tuple]:
    matricula = _id_opaco(evento.dados.get("matricula_id"))
    if not matricula:
        return []
    situacao = evento.dados.get("situacao_nova")
    if situacao == "aguardando":
        return [(MATRICULA, matricula, Marco.Tipo.PEDIU_ENTRADA, evento.ocorrido_em)]
    if situacao != "ativa":
        return []
    tipo = VIROU_ALUNO_POR_ORIGEM.get(evento.dados.get("origem"))
    if tipo is None:
        return []
    # `virou_aluno_em` é a regra da célula DONA, e o contrato manda usá-la em
    # vez de recalcular: para quem veio da sala de espera é a liberação, para
    # quem comprou é a confirmação do pagamento. Nulo enquanto ninguém decidiu.
    quando = _instante(evento.dados.get("virou_aluno_em")) or evento.ocorrido_em
    return [(MATRICULA, matricula, tipo, quando)]


def _escreveu_no_forum(evento: Evento) -> list[tuple]:
    autor = _id_opaco(evento.ator_id)
    if not autor:
        return []
    return [(PESSOA, autor, Marco.Tipo.ESCREVEU_NO_FORUM, evento.ocorrido_em)]


def _ajudou_alguem(evento: Evento) -> list[tuple]:
    # Quem conquista é quem ESCREVEU a resposta aceita, nunca quem a marcou —
    # o `ator_id` do envelope aqui é o de quem marcou, e premiar por ele
    # daria o marco à pessoa errada (`forum.resposta-aceita.v1`).
    autor = _id_opaco(evento.dados.get("autor_da_resposta_id"))
    if not autor:
        return []
    return [(PESSOA, autor, Marco.Tipo.AJUDOU_ALGUEM, evento.ocorrido_em)]


#: Assunto do evento e a conquista que ele produz. Assunto que não está aqui
#: entra no livro como fato e não vira marco, que é o desenho da célula.
REGRAS = {
    "identidade.pessoa-cadastrada": _entrou_no_site,
    "matricula.situacao-alterada": _vida_da_matricula,
    "forum.topico-criado": _escreveu_no_forum,
    "forum.mensagem-criada": _escreveu_no_forum,
    "forum.resposta-aceita": _ajudou_alguem,
}


def derivar(evento: Evento) -> list[Marco]:
    """Os marcos que este fato conquista, gravados. Nunca levanta.

    Devolve os marcos escritos nesta chamada — vazio quando o fato não produz
    conquista nenhuma, quando ela já estava lá com data igual ou mais antiga,
    ou quando o miolo do evento não traz o que a regra precisa.
    """
    regra = REGRAS.get(evento.tipo)
    if regra is None or not isinstance(evento.dados, dict):
        return []
    escritos = []
    for sujeito_tipo, sujeito_id, tipo, quando in regra(evento):
        marco = _gravar(sujeito_tipo, sujeito_id, tipo, quando, evento.event_id)
        if marco is not None:
            escritos.append(marco)
    return escritos


def _gravar(sujeito_tipo, sujeito_id, tipo, quando, event_id) -> Marco | None:
    dia = dia_em_sao_paulo(quando)
    try:
        with transaction.atomic():
            marco, nasceu = Marco.objects.get_or_create(
                sujeito_tipo=sujeito_tipo,
                sujeito_id=sujeito_id,
                tipo=tipo,
                defaults={"dia": dia, "event_id": event_id},
            )
    except IntegrityError:
        # Dois processos derivando a mesma conquista no mesmo instante. O marco
        # existe, que é o que a contagem precisa; quem perdeu a corrida não
        # tem o que escrever.
        return None
    if nasceu:
        return marco
    if dia < marco.dia:
        marco.dia = dia
        marco.event_id = event_id
        marco.save(update_fields=["dia", "event_id"])
        return marco
    return None
