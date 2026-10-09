"""Escolhas do atendimento; texto legível acompanha todo componente nativo."""
from __future__ import annotations

import json
import re

BOTOES = (
    ("meshcraft:cursos", "Conhecer cursos"),
    ("meshcraft:duvidas", "Tirar dúvidas"),
    ("meshcraft:aluno", "Já sou aluno"),
)
ASSUNTOS = BOTOES + (
    ("meshcraft:acesso", "Acesso às aulas"),
    ("meshcraft:compra", "Compra e matrícula"),
    ("meshcraft:equipe", "Falar com a equipe"),
)
TITULOS = dict(ASSUNTOS)


def preparar(tipo: str | None, texto: str) -> tuple[str, dict | None]:
    if tipo not in {"botoes", "lista", "links"}:
        return texto, None
    if tipo == "links":
        links = list(dict.fromkeys(re.findall(r"https://[^\s<>]+", texto)))[:2]
        if not links:
            return texto, None
        return texto, {"tipo": "botoes", "title": "Links da conversa", "description": texto,
                       "buttons": [{"type": "url", "displayText": "Abrir link" if len(links) == 1
                                    else f"Abrir link {i}", "url": link.rstrip(').,;')}
                                   for i, link in enumerate(links, 1)]}
    itens = BOTOES if tipo == "botoes" else ASSUNTOS
    legenda = "\n\n" + "\n".join(f"{i}. {titulo}" for i, (_, titulo) in enumerate(itens, 1))
    legenda += "\nEscolha uma opção ou escreva/mande áudio com sua dúvida."
    corpo = texto + legenda
    if tipo == "botoes":
        return corpo, {"tipo": "botoes", "title": "Como podemos ajudar?", "description": corpo,
                       "buttons": [{"type": "reply", "displayText": titulo, "id": ident}
                                   for ident, titulo in itens]}
    return corpo, {"tipo": "lista", "title": "Assuntos do atendimento", "description": corpo,
                   "buttonText": "Escolher assunto", "footerText": "Equipe Meshcraft",
                   "sections": [{"title": "Como podemos ajudar?", "rows": [
                       {"title": titulo, "description": f"Conversar sobre: {titulo}", "rowId": ident}
                       for ident, titulo in itens]}]}


def resposta(conteudo: dict) -> tuple[str, str]:
    """Converte cliques clássicos e native-flow em fala, preservando a citação."""
    for nome in ("buttonsResponseMessage", "templateButtonReplyMessage", "listResponseMessage",
                 "interactiveResponseMessage"):
        dados = conteudo.get(nome)
        if not isinstance(dados, dict):
            continue
        escolhido = dados.get("singleSelectReply") or {}
        ident = dados.get("selectedButtonId") or dados.get("selectedId") or escolhido.get("selectedRowId")
        titulo = dados.get("selectedDisplayText") or dados.get("selectedDisplayText") or dados.get("title")
        if nome == "interactiveResponseMessage":
            nativo = dados.get("nativeFlowResponseMessage") or {}
            try:
                parametros = json.loads(str(nativo.get("paramsJson") or "{}")[:8192])
            except (ValueError, TypeError):
                parametros = {}
            if not isinstance(parametros, dict):
                parametros = {}
            ident = parametros.get("id") or parametros.get("selectedRowId") or ident
            titulo = parametros.get("title") or (dados.get("body") or {}).get("text") or titulo
        texto = TITULOS.get(str(ident or "")) or str(titulo or ident or "Escolhi uma opção")[:500]
        contexto = dados.get("contextInfo") or {}
        return texto, str(contexto.get("stanzaId") or "")[:300]
    return "", ""


def desembrulhar(conteudo: dict) -> dict:
    for _ in range(5):
        interno = next((conteudo[n].get("message") for n in
                        ("ephemeralMessage", "viewOnceMessage", "viewOnceMessageV2", "documentWithCaptionMessage")
                        if isinstance(conteudo.get(n), dict) and isinstance(conteudo[n].get("message"), dict)), None)
        if interno is None:
            break
        conteudo = interno
    return conteudo
