"""Quem abriu o link: pessoa ou robô de prévia? Função pura, sem banco."""

TRECHOS_DE_ROBO = (
    "whatsapp", "facebookexternalhit", "facebot", "twitterbot", "telegrambot", "slackbot",
    "discordbot", "linkedinbot", "googlebot", "bingbot", "applebot", "curl", "wget",
    "python-requests", "go-http-client", "headlesschrome", "bot/", "crawler", "spider", "preview",
)


def classificar(metodo: str, user_agent: str, accept: str) -> tuple[str, str]:
    """O WhatsApp abre o link sozinho para montar a prévia; isso não é a pessoa."""
    if (metodo or "").upper() == "HEAD":
        return "automatico", "metodo HEAD"
    agente = (user_agent or "").strip()
    if not agente:
        return "indeterminado", "sem user-agent"
    minusculo = agente.lower()
    for trecho in TRECHOS_DE_ROBO:
        if trecho in minusculo:
            return "automatico", f"user-agent de prévia/robô: {trecho}"
    if agente.startswith("Mozilla/") and "text/html" in (accept or ""):
        return "provavel", "navegador com text/html"
    return "indeterminado", "padrão não reconhecido"
