"""A resposta da equipe numa ideia implementada, reduzida a HTML que não executa nada.

Pedido do mantenedor (29/09/2026): ao mover uma ideia para Implementado, a
equipe escreve na própria ideia uma resposta que pode ser texto, HTML, vídeo ou
imagem. Quem lê é o aluno, na página da ideia; por isso o que a equipe escreve
passa por uma LISTA DE PERMISSÃO, nunca por uma lista de proibição: etiqueta ou
atributo que não está aqui simplesmente não sai.

Sem dependência nova: `html.parser` da biblioteca padrão faz a leitura, e este
módulo decide o que reescrever. Três regras que a página depende:

* **O resultado é sempre bem formado.** Etiqueta aberta e esquecida é fechada
  aqui, e fechamento sem abertura some; senão um `<blockquote>` sem fim
  engoliria o resto da página.
* **Endereço só http(s), e mídia só https.** `javascript:`, `data:` e qualquer
  esquema disfarçado com entidade ou tabulação perdem o endereço.
* **Filtrar duas vezes dá o mesmo resultado.** O formulário do Admin devolve o
  que já foi gravado, e repassar não pode deformar a resposta.
"""

import re
from html import escape
from html.parser import HTMLParser
from urllib.parse import parse_qs, urlsplit

SEM_ATRIBUTOS = {
    "p",
    "br",
    "b",
    "strong",
    "i",
    "em",
    "u",
    "ul",
    "ol",
    "li",
    "h2",
    "h3",
    "h4",
    "blockquote",
    "hr",
}
COM_ATRIBUTOS = {"a", "img", "video", "source", "iframe"}
SEM_FECHAMENTO = {"br", "hr", "img", "source"}
# O conteúdo destas sai junto com a etiqueta: código de script ou estilo
# mostrado como texto não é resposta para ninguém, e o que mora dentro de um
# iframe é só o texto reserva de navegador antigo.
CONTEUDO_DESCARTADO = {"script", "style", "iframe"}

ID_DO_YOUTUBE = re.compile(r"^[A-Za-z0-9_-]{11}$")
ID_DO_VIMEO = re.compile(r"^[0-9]+$")
TIPO_DE_MIDIA = re.compile(r"^[a-z]+/[a-z0-9.+-]+$")
MEDIDA = re.compile(r"^[0-9]{1,4}$")
EXTENSOES_DE_IMAGEM = (".png", ".jpg", ".jpeg", ".gif", ".webp")
# Uma etiqueta de verdade: nome só com letras e dígitos ASCII. "<parágrafo>"
# escrito num texto puro continua texto, e aparece escapado.
PARECE_HTML = re.compile(r"</?[A-Za-z][A-Za-z0-9]*(\s[^>]*)?/?>")


def _endereco(valor: str | None, esquemas: tuple[str, ...]) -> str:
    """O endereço, se ele é de um dos esquemas aceitos; vazio se não é."""
    valor = (valor or "").strip()
    if not valor or any(ord(c) < 33 for c in valor):
        return ""
    partes = urlsplit(valor)
    if partes.scheme.lower() not in esquemas or not partes.netloc:
        return ""
    return valor


def endereco_do_player(valor: str | None) -> str:
    """O endereço do player embutido de um link do YouTube ou do Vimeo.

    Sempre o endereço canônico, montado aqui a partir do identificador: o que
    a equipe colou nunca vai para o `src` como veio.
    """
    endereco = _endereco(valor, ("https", "http"))
    if not endereco:
        return ""
    partes = urlsplit(endereco)
    host = (partes.hostname or "").removeprefix("www.").removeprefix("m.")
    segmentos = [s for s in partes.path.split("/") if s]
    candidato = ""
    if host == "youtu.be" and segmentos:
        candidato = segmentos[0]
    elif host in ("youtube.com", "youtube-nocookie.com"):
        if segmentos[:1] == ["watch"]:
            candidato = parse_qs(partes.query).get("v", [""])[0]
        elif len(segmentos) >= 2 and segmentos[0] in ("embed", "shorts", "live"):
            candidato = segmentos[1]
    if ID_DO_YOUTUBE.match(candidato):
        return f"https://www.youtube-nocookie.com/embed/{candidato}"
    if host == "vimeo.com" and segmentos and ID_DO_VIMEO.match(segmentos[0]):
        return f"https://player.vimeo.com/video/{segmentos[0]}"
    if (
        host == "player.vimeo.com"
        and len(segmentos) >= 2
        and segmentos[0] == "video"
        and ID_DO_VIMEO.match(segmentos[1])
    ):
        return f"https://player.vimeo.com/video/{segmentos[1]}"
    return ""


def _atributos(pares) -> str:
    return "".join(
        f' {nome}="{escape(valor)}"' if valor is not None else f" {nome}"
        for nome, valor in pares
    )


class _Filtro(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.saida: list[str] = []
        self.abertas: list[str] = []
        self.descartando: list[str] = []

    def _permitida(self, etiqueta: str, attrs: dict) -> list | None:
        """Os atributos que saem, ou `None` quando a etiqueta inteira sai."""
        if etiqueta in SEM_ATRIBUTOS:
            return []
        if etiqueta == "a":
            href = _endereco(attrs.get("href"), ("https", "http"))
            if not href:
                return None
            return [
                ("href", href),
                ("rel", "noopener noreferrer"),
                ("target", "_blank"),
            ]
        if etiqueta == "img":
            src = _endereco(attrs.get("src"), ("https",))
            if not src:
                return None
            pares = [("src", src)]
            if attrs.get("alt"):
                pares.append(("alt", attrs["alt"]))
            pares += [
                (medida, attrs[medida])
                for medida in ("width", "height")
                if MEDIDA.match(attrs.get(medida) or "")
            ]
            return pares
        if etiqueta == "video":
            pares = []
            if src := _endereco(attrs.get("src"), ("https",)):
                pares.append(("src", src))
            pares.append(("controls", None))
            if poster := _endereco(attrs.get("poster"), ("https",)):
                pares.append(("poster", poster))
            return pares
        if etiqueta == "source":
            src = _endereco(attrs.get("src"), ("https",))
            if not src:
                return None
            pares = [("src", src)]
            if TIPO_DE_MIDIA.match(attrs.get("type") or ""):
                pares.append(("type", attrs["type"]))
            return pares
        if etiqueta == "iframe":
            src = endereco_do_player(attrs.get("src"))
            return [("src", src), ("allowfullscreen", None)] if src else None
        return None

    def handle_starttag(self, etiqueta, attrs):
        if self.descartando:
            if etiqueta in CONTEUDO_DESCARTADO:
                self.descartando.append(etiqueta)
            return
        pares = self._permitida(etiqueta, dict(attrs))
        if etiqueta == "iframe" and pares:
            self.saida.append(f"<iframe{_atributos(pares)}></iframe>")
        if etiqueta in CONTEUDO_DESCARTADO:
            self.descartando.append(etiqueta)
            return
        if pares is None:
            return
        self.saida.append(f"<{etiqueta}{_atributos(pares)}>")
        if etiqueta not in SEM_FECHAMENTO:
            self.abertas.append(etiqueta)

    def handle_endtag(self, etiqueta):
        if self.descartando:
            if etiqueta == self.descartando[-1]:
                self.descartando.pop()
            return
        if etiqueta not in self.abertas:
            return
        while self.abertas:
            aberta = self.abertas.pop()
            self.saida.append(f"</{aberta}>")
            if aberta == etiqueta:
                return

    def handle_data(self, dados):
        if not self.descartando:
            self.saida.append(escape(dados, quote=False))

    def resultado(self) -> str:
        self.close()
        self.saida.extend(f"</{aberta}>" for aberta in reversed(self.abertas))
        return "".join(self.saida).strip()


def _linha_solta(linha: str) -> str:
    """Um link sozinho na linha vira player ou imagem; outra coisa, vazio."""
    link = linha.strip()
    if " " in link:
        return ""
    if player := endereco_do_player(link):
        return f'<iframe src="{player}" allowfullscreen></iframe>'
    imagem = _endereco(link, ("https",))
    if imagem and urlsplit(imagem).path.lower().endswith(EXTENSOES_DE_IMAGEM):
        return f'<img src="{escape(imagem)}">'
    return ""


def resposta_em_html_seguro(texto: str | None) -> str:
    """A resposta da equipe pronta para a página do aluno.

    Texto sem nenhuma etiqueta vira parágrafos (linha em branco separa, quebra
    simples vira `<br>`). Com etiqueta, o HTML é mantido no que a lista permite.
    Nos dois casos, um link do YouTube, do Vimeo ou de imagem sozinho na linha
    vira o player ou a imagem.
    """
    texto = (texto or "").replace("\r\n", "\n").strip()
    if not texto:
        return ""
    if PARECE_HTML.search(texto):
        bruto = "\n".join(_linha_solta(l) or l for l in texto.split("\n"))
    else:
        bruto = "".join(
            "<p>"
            + "<br>".join(
                _linha_solta(l) or escape(l, quote=False)
                for l in bloco.strip().split("\n")
            )
            + "</p>"
            for bloco in re.split(r"\n\s*\n", texto)
        )
    filtro = _Filtro()
    filtro.feed(bruto)
    return filtro.resultado()
