from io import BytesIO
import warnings
from PIL import Image, ImageOps, UnidentifiedImageError
LIMITE_ORIGINAL=5*1024*1024
LIMITE_PIXELS=20_000_000
LIMITE_LADO=1920
LIMITE_WEBP=2*1024*1024
FORMATOS=frozenset({"JPEG","PNG","WEBP"})
class ImagemRecusada(ValueError):
    """Recusa apresentável ao aluno, sem detalhes do decodificador."""

def _normalizar(arquivo) -> tuple[bytes, int, int]:
    if arquivo is None:
        raise ImagemRecusada("Escolha uma imagem JPEG, PNG ou WebP.")
    if getattr(arquivo, "size", 0) > LIMITE_ORIGINAL:
        raise ImagemRecusada("A imagem deve ter até 5 MiB.")

    conteudo = bytearray()
    try:
        pedacos = (
            arquivo.chunks()
            if hasattr(arquivo, "chunks")
            else iter(lambda: arquivo.read(64 * 1024), b"")
        )
        for pedaco in pedacos:
            conteudo.extend(pedaco)
            if len(conteudo) > LIMITE_ORIGINAL:
                raise ImagemRecusada("A imagem deve ter até 5 MiB.")
    except ImagemRecusada:
        raise
    except (OSError, ValueError) as erro:
        raise ImagemRecusada("Não foi possível ler a imagem enviada.") from erro
    if not conteudo:
        raise ImagemRecusada("Escolha uma imagem JPEG, PNG ou WebP.")

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(conteudo)) as origem:
                if origem.format not in FORMATOS or getattr(origem, "n_frames", 1) != 1:
                    raise ImagemRecusada(
                        "Envie uma imagem JPEG, PNG ou WebP sem animação."
                    )
                largura, altura = origem.size
                if not largura or not altura or largura * altura > LIMITE_PIXELS:
                    raise ImagemRecusada(
                        "A imagem deve ter no máximo 20 milhões de pixels."
                    )
                origem.verify()
            with Image.open(BytesIO(conteudo)) as origem:
                origem.load()
                imagem = ImageOps.exif_transpose(origem)
                imagem.thumbnail((LIMITE_LADO, LIMITE_LADO), Image.Resampling.LANCZOS)
                imagem = imagem.convert(
                    "RGBA"
                    if "A" in imagem.getbands() or "transparency" in imagem.info
                    else "RGB"
                )
                saida = BytesIO()
                imagem.save(saida, format="WEBP", quality=85, method=6)
                dados = saida.getvalue()
                largura, altura = imagem.size
    except ImagemRecusada:
        raise
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        Image.DecompressionBombWarning,
        Image.DecompressionBombError,
    ) as erro:
        raise ImagemRecusada(
            "O arquivo não é uma imagem válida JPEG, PNG ou WebP."
        ) from erro
    if len(dados) > LIMITE_WEBP:
        raise ImagemRecusada(
            "A imagem processada ultrapassou 2 MiB. Envie outra imagem."
        )
    return dados, largura, altura
