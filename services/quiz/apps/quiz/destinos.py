"""Conecta checkouts reais a ofertas de quizzes já importados."""

from copy import deepcopy
from urllib.parse import urlsplit

from django.db import transaction

from apps.quiz.models import Quiz, QuizVersion, ResultBand


def _conferir_url(url, oferta_id):
    if not isinstance(url, str) or not url or len(url) > 500 or url != url.strip():
        raise ValueError(
            f"{oferta_id}: checkout_url precisa ser URL HTTPS de até 500 caracteres"
        )
    if any(ord(char) < 33 for char in url):
        raise ValueError(f"{oferta_id}: checkout_url contém espaço ou controle")
    try:
        parsed = urlsplit(url)
        host = parsed.hostname
        parsed.port  # valida porta malformada
    except ValueError as erro:
        raise ValueError(f"{oferta_id}: checkout_url inválida") from erro
    if parsed.scheme != "https" or not host or parsed.username or parsed.password:
        raise ValueError(f"{oferta_id}: checkout_url precisa ser HTTPS sem credenciais")


@transaction.atomic
def conectar_checkouts(quiz: Quiz, destinos: dict[str, str]) -> Quiz:
    """Atualiza somente URLs de ofertas e botões, preservando o documento original."""
    quiz = Quiz.objects.select_for_update().get(pk=quiz.pk)
    if not quiz.directed:
        raise ValueError("quiz não é campanha direcionada")
    if not isinstance(destinos, dict) or len(destinos) != 2:
        raise ValueError("informe os dois IDs de oferta e seus URLs HTTPS")
    for oferta_id, url in destinos.items():
        if not isinstance(oferta_id, str) or not oferta_id:
            raise ValueError("ID de oferta inválido")
        _conferir_url(url, oferta_id)

    versoes = list(QuizVersion.objects.select_for_update().filter(quiz=quiz))
    if not versoes:
        raise ValueError("quiz não tem versões")
    planos = []
    for versao in versoes:
        experiencia = versao.experience
        if not isinstance(experiencia, dict):
            raise ValueError(f"versão {versao.key} sem experiência")
        ofertas = experiencia.get("ofertas")
        documento = experiencia.get("documento")
        band_offers = experiencia.get("band_offers")
        if not isinstance(ofertas, dict) or set(ofertas) != set(destinos):
            raise ValueError(
                f"versão {versao.key}: os dois IDs de oferta não correspondem"
            )
        if not isinstance(documento, dict) or not isinstance(
            documento.get("versao"), dict
        ):
            raise ValueError(f"versão {versao.key}: documento original ausente")
        faixas = documento["versao"].get("faixas")
        if not isinstance(faixas, list) or not isinstance(band_offers, dict):
            raise ValueError(f"versão {versao.key}: faixas originais ausentes")
        bandas = {
            b.key: b
            for b in ResultBand.objects.select_for_update().filter(version=versao)
        }
        if set(bandas) != {f.get("key") for f in faixas if isinstance(f, dict)}:
            raise ValueError(f"versão {versao.key}: faixas divergentes do documento")
        if band_offers != {f["key"]: f.get("oferta_id") for f in faixas}:
            raise ValueError(f"versão {versao.key}: ofertas das faixas divergentes")
        for oferta_id, oferta in ofertas.items():
            if not isinstance(oferta, dict) or oferta.get("id") != oferta_id:
                raise ValueError(f"versão {versao.key}: oferta {oferta_id} inválida")
        for faixa in faixas:
            rotulo = faixa.get("botao_rotulo")
            if not isinstance(rotulo, str) or not rotulo or len(rotulo) > 80:
                raise ValueError(
                    f"versão {versao.key}: rótulo da faixa {faixa['key']} inválido"
                )
            if faixa.get("oferta_id") not in destinos:
                raise ValueError(f"versão {versao.key}: oferta da faixa desconhecida")
        planos.append((versao, experiencia, faixas, bandas))

    for versao, experiencia, faixas, bandas in planos:
        nova = deepcopy(experiencia)
        for oferta_id, url in destinos.items():
            nova["ofertas"][oferta_id]["checkout_url"] = url
        versao.experience = nova
        versao.save(update_fields=["experience"])
        for faixa in faixas:
            banda = bandas[faixa["key"]]
            banda.botao_destino = destinos[faixa["oferta_id"]]
            banda.botao_rotulo = faixa["botao_rotulo"]
            banda.save(update_fields=["botao_destino", "botao_rotulo"])
    return quiz
