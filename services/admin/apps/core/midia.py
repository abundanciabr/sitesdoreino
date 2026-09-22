"""As imagens e os vídeos dos documentos: guardar no disco e servir de volta.

Pedido do mantenedor em 21/09/2026, com autorização expressa para guardar
arquivo no disco da VPS (TAR-597). Até aqui a plataforma não guardava arquivo
nenhum: um documento só podia falar de uma imagem hospedada fora de casa.

## O tipo sai do CONTEÚDO, nunca do nome nem do que o navegador disse

Quem envia escolhe o nome do arquivo e escolhe o `Content-Type` do formulário.
Os dois são texto que veio de fora, e confiar neles é o buraco clássico: um
`foto.png` que na verdade é HTML, guardado e devolvido como HTML, executa na
origem da área administrativa e passa a ser a própria pessoa que o abriu.

Então o tipo é LIDO dos primeiros bytes, e é o tipo lido que decide três
coisas: se o arquivo entra, com que extensão ele é gravado, e com que
`Content-Type` ele volta. O nome que veio de fora não sobrevive à passagem: ele
vira apelido aparado, e a extensão é reescrita a partir da assinatura.

## O SVG entra, e o que o segura é cabeçalho, não confiança

SVG é XML e pode trazer `<script>` dentro. Das três saídas possíveis (limpar o
arquivo, servi-lo com política de segurança própria, ou recusá-lo), esta serve
com política própria: limpar XML de terceiro é um filtro com lista de exceções
que envelhece em silêncio, e `default-src 'none'` é uma tranca do navegador que
não depende de o próximo autor lembrar de nada. Ver `_CSP_DO_SVG`.

## O endereço é um sorteio, e o disco não é alcançado pela URL

Cada arquivo nasce com um sorteio de 32 dígitos e mora em `<sorteio>/<nome>`.
A rota que serve NÃO monta caminho a partir da URL: ela procura a linha no
banco pelo sorteio e lê o caminho de lá. Travessia de diretório deixa de ser
uma coisa a filtrar e passa a ser uma coisa que não tem por onde entrar.
"""

from __future__ import annotations

import hashlib
import re
import secrets
import shutil
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, Http404
from django.views.decorators.http import require_GET

from .models import Midia

#: O teto por arquivo, conferido ANTES de escrever no disco.
#:
#: 25 MB porque o maior caso previsto é um vídeo curto de demonstração dentro
#: de um documento, e não um filme: acima disso o lugar do vídeo é uma
#: hospedagem de vídeo, não o disco da VPS que também guarda o banco.
TETO_POR_ARQUIVO = 25 * 1024 * 1024

#: O que a política de segurança precisa dizer numa resposta que é SVG.
#:
#: `default-src 'none'` mata script, fetch, iframe e todo carregamento externo
#: de dentro do desenho; `style-src 'unsafe-inline'` devolve só o estilo
#: embutido, sem o qual praticamente todo SVG de verdade chega sem cor.
_CSP_DO_SVG = "default-src 'none'; style-src 'unsafe-inline'"

#: Os tipos aceitos: assinatura lida no conteúdo, `Content-Type` de volta e a
#: extensão com que o arquivo é gravado. Nome de fora não entra nesta conta.
PNG = "image/png"
JPEG = "image/jpeg"
WEBP = "image/webp"
GIF = "image/gif"
MP4 = "video/mp4"
SVG = "image/svg+xml"
WEBM = "video/webm"
QUICKTIME = "video/quicktime"
AVIF = "image/avif"
HEIC = "image/heic"
OGG = "audio/ogg"

EXTENSOES = {
    PNG: "png",
    JPEG: "jpg",
    WEBP: "webp",
    GIF: "gif",
    MP4: "mp4",
    SVG: "svg",
    WEBM: "webm",
    QUICKTIME: "mov",
    AVIF: "avif",
    HEIC: "heic",
    OGG: "ogg",
}

#: O que a tela diz que aceita. Sai daqui para não haver duas listas.
ACEITOS_EM_PORTUGUES = (
    "PNG, JPEG, WebP, GIF, AVIF, HEIC, SVG, MP4, WebM, MOV e OGG"
)

#: Endereços `/midia/...` com estas extensões viram `<video>` no renderizador.
EXTENSOES_DE_VIDEO = frozenset({"mp4", "webm", "mov"})

#: Endereços `/midia/...` com estas extensões viram `<audio>`.
EXTENSOES_DE_AUDIO = frozenset({"ogg"})

EMAIL_DA_SEMENTE = "semente@repositorio"

#: Uma linha de imagem ou vídeo na semente: `![legenda](anexo:apelido)`.
#: O arquivo mora em `documentos/anexos/<nome-do-doc>/<apelido>.<ext>`.
_REFERENCIA_ANEXO = re.compile(
    r"!\[([^\]]*)\]\(anexo:([a-z0-9-]+)\)"
)

_APELIDO = re.compile(r"[^a-z0-9]+")
_ABERTURA_DE_SVG = re.compile(rb"<svg[\s>/]", re.IGNORECASE)


def tipo_do_conteudo(cabeca: bytes) -> str | None:
    """O tipo lido dos primeiros bytes, ou `None` quando não é nenhum aceito.

    Quem chama passa o começo do arquivo (1 KB basta para todos os casos). A
    ordem não importa: as assinaturas não se confundem entre si.
    """
    if cabeca.startswith(b"\x89PNG\r\n\x1a\n"):
        return PNG
    if cabeca.startswith(b"\xff\xd8\xff"):
        return JPEG
    if cabeca.startswith((b"GIF87a", b"GIF89a")):
        return GIF
    # WebP e MP4 têm a assinatura DEPOIS do tamanho do primeiro bloco, e é por
    # isso que os dois olham a partir do byte 4 em vez do byte 0.
    if cabeca[:4] == b"RIFF" and cabeca[8:12] == b"WEBP":
        return WEBP
    if cabeca.startswith(b"\x1aE\xdf\xa3"):
        return WEBM
    if cabeca.startswith(b"OggS"):
        return OGG
    ftyp = _tipo_ftyp(cabeca)
    if ftyp is not None:
        return ftyp
    if _e_svg(cabeca):
        return SVG
    return None


def _tipo_ftyp(cabeca: bytes) -> str | None:
    """ISO BMFF (`ftyp`): MP4, MOV, AVIF ou HEIC, lido da marca principal."""
    if len(cabeca) < 12 or cabeca[4:8] != b"ftyp":
        return None
    marca = cabeca[8:12]
    if marca in (b"avif", b"avis"):
        return AVIF
    if marca in (b"heic", b"heix", b"mif1", b"msf1"):
        return HEIC
    if marca == b"qt  ":
        return QUICKTIME
    return MP4


def _e_svg(cabeca: bytes) -> bool:
    """XML que abre um `<svg>` logo no começo. HTML não passa por aqui.

    A exigência dupla é o que separa um desenho de uma página: o arquivo tem de
    COMEÇAR como XML ou como SVG (um `<!DOCTYPE html>` ou um `<html>` morre na
    primeira condição) e tem de abrir a etiqueta `<svg>` antes do fim do
    primeiro quilobyte (um XML qualquer morre na segunda).
    """
    nu = cabeca.lstrip(b"\xef\xbb\xbf").lstrip()
    comeco = nu[:14].lower()
    if not comeco.startswith((b"<?xml", b"<svg", b"<!doctype svg")):
        return False
    return bool(_ABERTURA_DE_SVG.search(nu[:1024]))


def _apelido(nome_de_fora: str, tipo: str) -> str:
    """O nome com que o arquivo é gravado e servido.

    O nome que veio de fora vira letras, números e hífen, e a extensão é
    REESCRITA a partir do tipo lido: é isso que impede um `.html` de sobreviver
    à passagem e é isso que faz o endereço servido dizer a verdade.
    """
    sem_extensao = Path(nome_de_fora or "").stem.lower()
    apelido = _APELIDO.sub("-", sem_extensao).strip("-")[:60]
    return f"{apelido or 'arquivo'}.{EXTENSOES[tipo]}"


def raiz() -> Path:
    """Onde os arquivos moram. Lida a cada chamada, nunca no import.

    No servidor é um volume próprio, fora da imagem: o disco do contêiner é
    remontado a cada atualização da plataforma, e um arquivo gravado dentro da
    imagem sumiria no deploy seguinte, em silêncio.
    """
    return Path(settings.MEDIA_ROOT)


class Recusa(Exception):
    """O envio não entrou, e a mensagem é o que o mantenedor vai ler."""


def sorteio_deterministico(documento_nome: str, apelido: str) -> str:
    """O mesmo sorteio em todo ambiente, para o mesmo documento e apelido."""
    materia = f"{documento_nome}:{apelido}".encode("utf-8")
    return hashlib.sha256(materia).hexdigest()[:32]


def endereco_publico(sorteio: str, nome: str) -> str:
    """O caminho que o Markdown do banco usa e que `midia_servir` entrega."""
    return f"/midia/{sorteio}/{nome}"


def pasta_de_anexos(documento_nome: str) -> Path | None:
    """`documentos/anexos/<documento>/`, ou `None` se a semente não veio."""
    from .documentos import diretorio

    raiz_docs = diretorio()
    if raiz_docs is None:
        return None
    pasta = raiz_docs / "anexos" / documento_nome
    return pasta if pasta.is_dir() else None


def _arquivo_do_anexo(pasta: Path, apelido: str) -> Path | None:
    """O arquivo cujo stem é o apelido, qualquer extensão aceita."""
    for candidato in sorted(pasta.iterdir()):
        if candidato.is_file() and candidato.stem == apelido:
            return candidato
    return None


def gravar_bytes(
    documento,
    conteudo: bytes,
    nome_de_fora: str,
    quem_email: str,
    *,
    sorteio: str | None = None,
) -> Midia:
    """Grava bytes já conferidos, ou levanta `Recusa`. Idempotente por sorteio."""
    if not conteudo:
        raise Recusa(
            "Nenhum arquivo chegou. Escolha uma imagem ou um vídeo no botão de "
            "escolher arquivo e aperte enviar de novo."
        )
    if len(conteudo) > TETO_POR_ARQUIVO:
        raise Recusa(
            f"Este arquivo tem {_em_megabytes(len(conteudo))} e o limite por "
            f"arquivo é {_em_megabytes(TETO_POR_ARQUIVO)}. Reduza o tamanho da "
            "imagem, ou corte o vídeo, e envie de novo."
        )

    tipo = tipo_do_conteudo(conteudo[:1024])
    if tipo is None:
        raise Recusa(
            f"Este arquivo não é uma imagem nem um vídeo dos que eu aceito "
            f"({ACEITOS_EM_PORTUGUES}). Eu confiro o conteúdo, e não o nome do "
            "arquivo, então renomear não resolve. Envie o arquivo original da "
            "imagem ou do vídeo."
        )

    sorteio = sorteio or secrets.token_hex(16)
    nome = _apelido(nome_de_fora, tipo)
    pasta = raiz() / sorteio
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        (pasta / nome).write_bytes(conteudo)
    except OSError as erro:
        shutil.rmtree(pasta, ignore_errors=True)
        raise Recusa(
            "Não consegui gravar o arquivo no disco do servidor, que pode "
            "estar cheio. O texto do documento está a salvo. Avise o "
            f"responsável pelo servidor e tente de novo depois. Detalhe: {erro}"
        ) from erro

    midia, _ = Midia.objects.update_or_create(
        sorteio=sorteio,
        defaults={
            "documento": documento,
            "nome": nome,
            "tipo": tipo,
            "tamanho": len(conteudo),
            "enviado_por": quem_email,
        },
    )
    return midia


def publicar_anexos_referenciados(documento, corpo: str) -> str:
    """Troca `anexo:…` por `/midia/…` e grava os arquivos da pasta-semente.

    Referência sem pasta ou sem arquivo correspondente deixa a linha como
    está: o renderizador mostra o Markdown cru e quem escreveu percebe.
    """
    pasta = pasta_de_anexos(documento.nome)
    if pasta is None or "anexo:" not in corpo:
        return corpo

    def substituir(match: re.Match[str]) -> str:
        legenda, apelido = match.group(1), match.group(2)
        caminho = _arquivo_do_anexo(pasta, apelido)
        if caminho is None:
            return match.group(0)
        sorteio = sorteio_deterministico(documento.nome, apelido)
        guardada = gravar_bytes(
            documento,
            caminho.read_bytes(),
            caminho.name,
            EMAIL_DA_SEMENTE,
            sorteio=sorteio,
        )
        return f"![{legenda}]({endereco_publico(guardada.sorteio, guardada.nome)})"

    return _REFERENCIA_ANEXO.sub(substituir, corpo)


def aplicar_anexos_ao_documento(documento) -> bool:
    """Grava no banco o corpo com `/midia/…` no lugar de `anexo:…`. Devolve se mudou."""
    if "anexo:" not in documento.corpo:
        return False
    novo = publicar_anexos_referenciados(documento, documento.corpo)
    if novo == documento.corpo:
        return False
    documento.corpo = novo
    documento.save(update_fields=["corpo"])
    return True


def guardar(documento, enviado, quem_email: str) -> Midia:
    """Grava um arquivo enviado, ou levanta `Recusa` dizendo o que fazer.

    As três conferências acontecem nesta ordem de propósito: existir, caber e
    ser do tipo certo. Ler a assinatura de um arquivo de 900 MB antes de olhar
    o tamanho seria pagar o preço do arquivo grande para depois recusá-lo.
    """
    if enviado is None or not getattr(enviado, "size", 0):
        raise Recusa(
            "Nenhum arquivo chegou. Escolha uma imagem ou um vídeo no botão de "
            "escolher arquivo e aperte enviar de novo."
        )

    if enviado.size > TETO_POR_ARQUIVO:
        raise Recusa(
            f"Este arquivo tem {_em_megabytes(enviado.size)} e o limite por "
            f"arquivo é {_em_megabytes(TETO_POR_ARQUIVO)}. Reduza o tamanho da "
            "imagem, ou corte o vídeo, e envie de novo."
        )

    return gravar_bytes(
        documento,
        enviado.read(),
        enviado.name,
        quem_email,
    )


def apagar_os_arquivos(documento) -> None:
    """Tira do disco os arquivos deste documento, antes de a linha sumir.

    Chamado por quem apaga o documento. A linha do banco vai embora por cascata
    e não deixa rastro; o arquivo no disco ficaria para sempre, sem ninguém
    para citá-lo. `ignore_errors` porque um arquivo que já não está lá é o
    resultado desejado, não um erro a reportar.
    """
    for midia in documento.midias.all():
        shutil.rmtree(raiz() / midia.sorteio, ignore_errors=True)


def _em_megabytes(bytes_: int) -> str:
    return f"{bytes_ / (1024 * 1024):.1f} MB".replace(".", ",")


@require_GET
def midia_servir(request, sorteio, nome):
    """Devolve o arquivo, com o tipo que NÓS conferimos na hora do envio.

    O `Content-Type` sai da coluna `tipo`, que foi escrita a partir da
    assinatura do conteúdo; o `nosniff` impede o navegador de adivinhar outro
    quando não gostar desse. O nome na URL existe para o arquivo ter nome ao
    ser baixado, e é conferido contra o banco justamente para não haver dois
    endereços para o mesmo arquivo.

    Quem não passou pela porta só recebe arquivo de documento no ar. Documento
    privado, arquivado ou inexistente responde 404, nunca 403: o sorteio não
    confirma que o arquivo existe.
    """
    midia = (
        Midia.objects.filter(sorteio=sorteio, nome=nome)
        .select_related("documento")
        .first()
    )
    if midia is None:
        raise Http404("arquivo não encontrado")
    if not getattr(request, "admin", None) and not midia.documento.no_ar:
        raise Http404("arquivo não encontrado")

    caminho = raiz() / midia.sorteio / midia.nome
    if not caminho.is_file():
        raise Http404("arquivo não encontrado")

    resposta = FileResponse(caminho.open("rb"), content_type=midia.tipo)
    resposta["X-Content-Type-Options"] = "nosniff"
    if midia.tipo == SVG:
        resposta["Content-Security-Policy"] = _CSP_DO_SVG
    return resposta
