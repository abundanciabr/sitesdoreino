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

EXTENSOES = {
    PNG: "png",
    JPEG: "jpg",
    WEBP: "webp",
    GIF: "gif",
    MP4: "mp4",
    SVG: "svg",
}

#: O que a tela diz que aceita. Sai daqui para não haver duas listas.
ACEITOS_EM_PORTUGUES = "PNG, JPEG, WebP, GIF, MP4 e SVG"

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
    if cabeca[4:8] == b"ftyp":
        return MP4
    if _e_svg(cabeca):
        return SVG
    return None


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

    cabeca = enviado.read(1024)
    enviado.seek(0)
    tipo = tipo_do_conteudo(cabeca)
    if tipo is None:
        raise Recusa(
            f"Este arquivo não é uma imagem nem um vídeo dos que eu aceito "
            f"({ACEITOS_EM_PORTUGUES}). Eu confiro o conteúdo, e não o nome do "
            "arquivo, então renomear não resolve. Envie o arquivo original da "
            "imagem ou do vídeo."
        )

    sorteio = secrets.token_hex(16)
    nome = _apelido(enviado.name, tipo)
    pasta = raiz() / sorteio
    try:
        pasta.mkdir(parents=True, exist_ok=True)
        with (pasta / nome).open("wb") as destino:
            for pedaco in enviado.chunks():
                destino.write(pedaco)
    except OSError as erro:
        # Disco cheio, disco somente-leitura, pasta sem permissão: de fora são
        # a mesma coisa (não consegui gravar) e têm a mesma saída (é o dono do
        # servidor quem resolve). O arquivo pela metade sai junto — meia
        # gravação servida depois é uma imagem quebrada sem explicação.
        shutil.rmtree(pasta, ignore_errors=True)
        raise Recusa(
            "Não consegui gravar o arquivo no disco do servidor, que pode "
            "estar cheio. O texto do documento está a salvo. Avise o "
            f"responsável pelo servidor e tente de novo depois. Detalhe: {erro}"
        ) from erro

    return Midia.objects.create(
        documento=documento,
        sorteio=sorteio,
        nome=nome,
        tipo=tipo,
        tamanho=enviado.size,
        enviado_por=quem_email,
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
    """
    midia = Midia.objects.filter(sorteio=sorteio, nome=nome).first()
    if midia is None:
        raise Http404("arquivo não encontrado")

    caminho = raiz() / midia.sorteio / midia.nome
    if not caminho.is_file():
        raise Http404("arquivo não encontrado")

    resposta = FileResponse(caminho.open("rb"), content_type=midia.tipo)
    resposta["X-Content-Type-Options"] = "nosniff"
    if midia.tipo == SVG:
        resposta["Content-Security-Policy"] = _CSP_DO_SVG
    return resposta
