# apps/notificacoes/handlers.py  # [RECEITA:R4 v1]
"""O que a célula faz quando uma carta chega no fio.

Tradutor e nada mais: tira do envelope o que o contrato
`contracts/eventos/notificacao.devida.v1.json` promete e chama a porta de
escrita. Regra de negócio aqui dentro seria regra escondida num tradutor.

`ator_id` vem do ENVELOPE, não do `data` — foi assim que o Rito de Contrato de
26/08/2026 o colocou, para que qualquer célula leia "quem fez isto" sem conhecer
o formato do assunto.
"""

from .services import guardar


def ao_notificacao_devida(data: dict, *, ator_id: str | None = None) -> None:
    guardar(
        site_id=data["site_id"],
        destinatario_id=data["destinatario_id"],
        ator_id=ator_id,
        assunto=data["assunto"],
        parametros=data["parametros"],
        origem_event_id=data["origem_event_id"],
    )
