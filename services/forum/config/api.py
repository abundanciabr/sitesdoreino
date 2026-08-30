# config/api.py  # [RECEITA:R1 v1]
from ninja import NinjaAPI

from apps.core.api import router as forum_router
from apps.core.auth import bearerAuth

# `servers` aponta para a REDE INTERNA do Docker, nunca para a borda pública —
# é o endereço que outra célula porá no env dela. O caminho `/interno` NÃO tem
# router no Traefik de propósito: o Traefik roteia `/forum`, que é a superfície
# de GENTE desta célula.
#
# Ressalva honesta, herdada da `identidade`: nada em `/interno` resolve pela
# borda pública hoje (o Traefik só manda `/forum/*` para cá), mas quem fecha a
# porta em qualquer topologia futura é o Bearer do par — 401 sem token, e o
# conjunto de tokens nasce VAZIO.
api = NinjaAPI(
    title="Forum — API interna",
    version="1.0.0",
    description=(
        "Superficie de MAQUINA do forum da escola. Existe para que o resto da\n"
        "plataforma dependa do CONTRATO e nunca do motor do forum — foi o\n"
        "ponto 4 do veredito da consultoria de 28/08/2026, e e o que mantem\n"
        "aberta a porta de trocar o motor um dia.\n"
        "\n"
        "Lei do assunto: docs/decisoes/DECISAO-forum-da-escola.md.\n"
        "\n"
        "ESTA PORTA SO RESPONDE SOBRE AREA PUBLICA. Nao ha cookie aqui e nao ha\n"
        "pessoa a reconhecer: o Bearer prova QUEM CHAMA, nunca quem e o\n"
        "visitante. Sem pessoa, o unico recorte honesto e o que qualquer um ja\n"
        "veria de graca. Area de aluno e area de turma nao aparecem por aqui —\n"
        "nem o conteudo, nem a contagem, nem a existencia.\n"
        "\n"
        "E nao sai dado pessoal: nem e-mail, nem quem leu o que. O publico\n"
        "desta escola e majoritariamente menor de idade.\n"
    ),
    servers=[{"url": "http://forum:8000/interno"}],
    auth=bearerAuth(),
    openapi_extra={"security": [{"bearerAuth": []}]},
)
api.add_router("", forum_router)
