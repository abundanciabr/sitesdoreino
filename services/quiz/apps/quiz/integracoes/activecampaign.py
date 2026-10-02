"""ActiveCampaign (API v3). Variáveis: AC_API_URL, AC_API_TOKEN, AC_LIST_ID
(opcional).

contact/sync por e-mail (não duplica) + tags quiz:<slug>, versao:<v>, seg:<seg>,
oferta:<id> + nota com o contexto. Idempotência por e-mail no sync; o registro
`IntegracaoEnvio` impede reenvio por tentativa.
"""

from urllib.parse import quote

from .nucleo import Evento, Requisicao, executar, parametros_contexto

SERVICO = "activecampaign"
VARIAVEIS = ("AC_API_URL", "AC_API_TOKEN")
TIPOS = ("quiz_complete",)
USA_DADO_PESSOAL = True


def tags(evento: Evento) -> list[str]:
    ctx = evento.contexto or {}
    saida = [f"quiz:{evento.quiz_slug}", f"versao:{evento.version_key}"]
    if ctx.get("seg"):
        saida.append(f"seg:{ctx['seg']}")
    if evento.oferta:
        saida.append(f"oferta:{evento.oferta}")
    return saida


def nota(evento: Evento) -> str:
    linhas = [f"Quiz concluído: {evento.quiz_slug}", f"resultado: {evento.result_key}"]
    linhas += [f"{k}: {v}" for k, v in parametros_contexto(evento).items()]
    if evento.oferta:
        linhas.append(f"oferta: {evento.oferta}")
    return "\n".join(linhas)


def montar_contato(evento: Evento) -> dict:
    contato = {"email": evento.email.strip().lower()}
    if evento.nome:
        partes = evento.nome.split(None, 1)
        contato["firstName"] = partes[0]
        if len(partes) > 1:
            contato["lastName"] = partes[1]
    return {"contact": contato}


def _base(env) -> str:
    return env["AC_API_URL"].rstrip("/") + "/api/3"


def _cab(env) -> dict:
    return {"Api-Token": env["AC_API_TOKEN"], "accept": "application/json"}


def requisicoes(evento: Evento, env) -> list[Requisicao]:
    """Só o passo inicial é conhecido de antemão; o resto depende de ids."""
    return [Requisicao("POST", f"{_base(env)}/contact/sync", _cab(env), montar_contato(evento))]


def _id_da_tag(nome, env, transporte):
    base, cab = _base(env), _cab(env)
    _, achadas = executar(
        Requisicao("GET", f"{base}/tags?search={quote(nome)}", cab), transporte, env
    )
    for tag in (achadas or {}).get("tags", []) if isinstance(achadas, dict) else []:
        if tag.get("tag") == nome:
            return tag["id"]
    _, criada = executar(
        Requisicao(
            "POST", f"{base}/tags", cab,
            {"tag": {"tag": nome, "tagType": "contact", "description": "quiz"}},
        ),
        transporte,
        env,
    )
    return criada["tag"]["id"]


def enviar(evento: Evento, env, transporte) -> dict:
    base, cab = _base(env), _cab(env)
    _, sync = executar(requisicoes(evento, env)[0], transporte, env)
    contato_id = str(sync["contact"]["id"])
    for nome in tags(evento):
        tag_id = _id_da_tag(nome, env, transporte)
        executar(
            Requisicao(
                "POST", f"{base}/contactTags", cab,
                {"contactTag": {"contact": contato_id, "tag": str(tag_id)}},
            ),
            transporte,
            env,
            aceitar=(422,),  # tag já aplicada
        )
    executar(
        Requisicao(
            "POST", f"{base}/notes", cab,
            {"note": {"note": nota(evento), "relid": contato_id, "reltype": "Subscriber"}},
        ),
        transporte,
        env,
    )
    lista = (env.get("AC_LIST_ID") or "").strip()
    if lista:
        executar(
            Requisicao(
                "POST", f"{base}/contactLists", cab,
                {"contactList": {"list": lista, "contact": contato_id, "status": 1}},
            ),
            transporte,
            env,
        )
    return {"contato": contato_id, "tags": len(tags(evento))}
