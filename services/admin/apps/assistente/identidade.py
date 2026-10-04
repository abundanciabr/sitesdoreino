"""A identidade do assistente de um site, pronta para quem precisar dela.

* `identidade_do_site(site_id)` devolve sempre uma `Identidade`, configurada ou
  não: sem linha no banco vale o padrão ("assistente da equipe", tom
  acolhedor, só texto);
* `Identidade.trecho_das_instrucoes()` é o parágrafo que o coordenador
  acrescenta às instruções de cada papel;
* `deve_responder_em_voz(site_id, lead_mandou_audio)` diz se uma resposta deve
  ir em áudio (quem gera o áudio é outra frente; aqui só a preferência do
  site).

Nada aqui deixa o assistente se passar pelo criador do curso ou por uma pessoa:
o nome é do ASSISTENTE e a apresentação sempre diz que ele é da equipe.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass

from .models import IdentidadeAssistente

TONS = {
    "acolhedor": "Acolhedor e objetivo: simpático, sem rodeios, uma ideia por mensagem.",
    "direto": "Direto e curto: vá ao ponto, frases curtas, sem enfeite.",
    "descontraido": "Descontraído: conversa leve e próxima, sem gíria pesada e sem exagero de emoji.",
    "formal": "Formal: tratamento respeitoso, sem gírias nem emojis.",
}

ROTULO_PADRAO = "Assistente da equipe"


def _linha(valor, limite: int) -> str:
    """Uma linha só, sem quebra nem espaço duplo, no tamanho do campo."""
    return " ".join(str(valor or "").split())[:limite]


@dataclass(frozen=True)
class Identidade:
    site_id: str
    nome_do_site: str
    nome: str
    apresentacao: str
    assinatura: str
    tom: str
    tom_descricao: str
    resposta_em_voz: str
    configurada: bool

    def como_dict(self) -> dict:
        return asdict(self)

    def trecho_das_instrucoes(self) -> str:
        voz = {
            "texto": "Responda sempre em texto.",
            "espelhar": "Responda em voz só quando a pessoa mandar áudio; nos demais casos, em texto.",
            "sempre": "Responda em voz sempre que o canal permitir.",
        }[self.resposta_em_voz]
        return (
            "Identidade neste site:\n"
            f"- Apresentação: \"{self.apresentacao}\". Use-a na primeira resposta e quando perguntarem com "
            "quem a pessoa fala. Você é um assistente, não o criador do curso nem uma pessoa específica, "
            "e não diga que alguém da equipe está escrevendo ou gravando cada mensagem.\n"
            f"- Assinatura: \"{self.assinatura}\" (use ao fechar a primeira mensagem de uma conversa, "
            "sem repeti-la em toda resposta).\n"
            f"- Tom: {self.tom_descricao}\n"
            f"- Voz: {voz}"
        )


def _montar(site_id: str, linha: IdentidadeAssistente | None, nome_do_site: str = "") -> Identidade:
    site = _linha(nome_do_site or (linha.nome_do_site if linha else ""), 200)
    nome = _linha(linha.nome if linha else "", 80)
    de_site = f" de {site}" if site else ""
    quem = f"{nome}, assistente da equipe{de_site}" if nome else f"assistente da equipe{de_site}"

    def preencher(texto: str, padrao: str) -> str:
        texto = _linha(texto, 300)
        if not texto:
            return padrao
        return texto.replace("{site}", site or "nossa equipe").replace("{nome}", nome or ROTULO_PADRAO)

    tom = linha.tom if linha and linha.tom in TONS else "acolhedor"
    voz = linha.resposta_em_voz if linha and linha.resposta_em_voz in ("texto", "espelhar", "sempre") else "texto"
    return Identidade(
        site_id=str(site_id or ""),
        nome_do_site=site,
        nome=nome,
        apresentacao=preencher(linha.apresentacao if linha else "", quem[:1].upper() + quem[1:]),
        assinatura=preencher(linha.assinatura if linha else "", f"— {nome or ROTULO_PADRAO}{de_site}"),
        tom=tom,
        tom_descricao=TONS[tom],
        resposta_em_voz=voz,
        configurada=linha is not None,
    )


def identidade_do_site(site_id, nome_do_site: str = "") -> Identidade:
    """A identidade do site; o padrão se ninguém configurou. Nunca levanta."""
    chave = str(site_id or "")
    linha = IdentidadeAssistente.objects.filter(site_id=chave).first() if chave else None
    return _montar(chave, linha, nome_do_site)


def salvar(
    site_id,
    *,
    nome_do_site: str = "",
    nome: str = "",
    apresentacao: str = "",
    assinatura: str = "",
    tom: str = "acolhedor",
    resposta_em_voz: str = "texto",
    quem: str = "",
) -> Identidade:
    chave = str(site_id or "").strip()
    if not chave:
        raise ValueError("site_id é obrigatório")
    linha, _ = IdentidadeAssistente.objects.update_or_create(
        site_id=chave,
        defaults={
            "nome_do_site": _linha(nome_do_site, 200),
            "nome": _linha(nome, 80),
            "apresentacao": _linha(apresentacao, 300),
            "assinatura": _linha(assinatura, 200),
            "tom": tom if tom in TONS else "acolhedor",
            "resposta_em_voz": resposta_em_voz if resposta_em_voz in ("texto", "espelhar", "sempre") else "texto",
            "atualizado_por": _linha(quem, 200),
        },
    )
    return _montar(chave, linha)


def trecho_das_instrucoes(site_id) -> str:
    """O parágrafo de identidade para as instruções dos papéis; vazio sem site."""
    if not str(site_id or "").strip():
        return ""
    return identidade_do_site(site_id).trecho_das_instrucoes()


def deve_responder_em_voz(site_id, lead_mandou_audio: bool) -> bool:
    voz = identidade_do_site(site_id).resposta_em_voz
    return voz == "sempre" or (voz == "espelhar" and bool(lead_mandou_audio))
